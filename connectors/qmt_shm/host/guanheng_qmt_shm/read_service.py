"""显式只读常驻门面；单一管理线程串行退休/创建原单连接runtime。"""
from __future__ import annotations

from contextlib import contextmanager
import math
import threading
import time

from guanheng_qmt_shm_agent.protocol import TransportBudget, canonical, decode
from guanheng_qmt_shm_agent.read_capabilities import validate_read_profile
from .runtime import error


_TRANSPORT = frozenset(('OSError', 'TimeoutError', 'BrokenPipeError', 'ConnectionResetError'))


def _category(reason, stage):
    # runtime的failure只用于有限分类；任何未知字符串/异常正文都不进入诊断。
    if reason in _TRANSPORT:
        return stage + '_transport'
    if reason in ('AuthenticationError', 'PermissionError', 'ProtocolError', 'GatewayError'):
        return stage + '_authentication_or_protocol'
    if reason in ('ValueError', 'TypeError', 'KeyError'):
        return stage + '_configuration'
    if reason in ('journal_unavailable', 'OperationalError', 'DatabaseError', 'IntegrityError'):
        return stage + '_journal'
    return stage + '_fault'


def _duration(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not .001 <= value <= 60:
        raise ValueError('explicit finite lifecycle interval required')
    return float(value)


class ReconnectingReadService:
    """factory(config副本, credentials=副本)每次返回一个原HostReadRuntime。

    factory负责未返回对象的构造失败收尾；一经返回，owner由本服务持有。
    factory须使用原Journal路径并显式wait_for_agent=True。profile须为部署入口
    已验证的只读profile。本服务不重放请求，不替换Journal或单请求预算。
    start等待首代listener就绪；close接收同一外层monotonic绝对截止。
    """
    trade_requests_enabled = False

    def __init__(self, factory, *, configuration, credentials, profile,
                 reconnect_seconds=.1, poll_seconds=.02, construction_owners=None):
        from .bootstrap import _snapshot_credentials
        if (construction_owners is not None
                and (type(construction_owners) is not list or len(construction_owners) != 1)):
            raise ValueError('construction owners require one explicit slot')
        # factory与服务共持预分配单槽；异常处理中不分配append空间，
        # 未确认关闭的构造期Journal持续归原owner持有。
        self._construction_owners = [None] if construction_owners is None else construction_owners
        if not callable(factory) or type(configuration) is not dict or type(profile) is not dict:
            raise ValueError('explicit read-only lifecycle inputs required')
        configuration = decode(canonical(configuration))
        profile = decode(canonical(profile))
        profile = self._admit_configuration(configuration, profile)
        self._configuration = canonical(configuration)
        self._profile = canonical(profile)
        self.read_retention_enabled = 'read_retention' in profile
        self._credentials = _snapshot_credentials(credentials)
        self._factory = factory
        self.reconnect_seconds = _duration(reconnect_seconds)
        self.poll_seconds = _duration(poll_seconds)
        self.budget = TransportBudget(configuration['connect_seconds'], configuration['io_seconds'])
        self.max_frame = configuration['max_frame']
        self.max_http_inflight = configuration['max_http_inflight']
        self.listen_host, self.listen_port = configuration['listen_host'], configuration['listen_port']
        if (type(self.max_frame) is not int or not 8192 <= self.max_frame <= 4194304
                or type(self.max_http_inflight) is not int or not 1 <= self.max_http_inflight <= 128
                or type(self.listen_host) is not str or not self.listen_host
                or type(self.listen_port) is not int or not 1024 <= self.listen_port <= 65535):
            raise ValueError('fixed HTTP service parameters required')
        self.connected = threading.Event()
        self._condition = threading.Condition()
        self._wake, self._ready, self._entered = threading.Event(), threading.Event(), threading.Event()
        self._shutdown_state = {}
        self._close_deadline = None
        self._runtime = self._thread = None
        self._start_returned = False
        self._creating = self._admitting = self._closed_complete = False
        self._active = self._generation = 0
        self._limits = None
        self._phase, self._failure, self._cleanup_failure = 'new', None, None

    def _admit_configuration(self, configuration, profile):
        """默认保持原只读准入；显式产品只复用下面的运输代际和关闭 owner。"""
        if (configuration.get('transport', {}).get('kind') != 'builtin-shm'
                or 'writes_enabled' in configuration or 'trade_profile' in configuration
                or 'trade_profile' in profile):
            raise ValueError('builtin SHM read-only configuration required')
        profile = validate_read_profile(profile, max_result_bytes=configuration['max_result_bytes'])
        if profile['read_operations'] != configuration['read_operations']:
            raise ValueError('explicit read-only operations differ')
        return profile

    @property
    def profile(self):
        return decode(self._profile)

    @property
    def public_limits(self):
        with self._condition:
            if self._limits is None:
                raise RuntimeError('first listener has not established public limits')
            return decode(self._limits)

    @property
    def failure(self):
        with self._condition:
            return self._failure

    @property
    def shutdown_started(self):
        return 'deadline' in self._shutdown_state

    @property
    def closed_complete(self):
        with self._condition:
            return self._closed_complete

    @property
    def io_resources_closed(self):
        # 服务完整关闭才授该事实；旧代尚存/manager未join时保持False。
        return self.closed_complete

    def require_http_credentials(self, keys):
        if type(keys) is not dict or keys != self._credentials['http_keys']:
            raise ValueError('service HTTP credentials differ from deployment snapshot')

    def _close_budget_seconds(self):
        """原只读关闭窗口；显式交易产品选择其原交易runtime的交接预算。"""
        return self.budget.io_seconds + 1

    def begin_shutdown(self, deadline=None):
        # 缺省信号路径保持单次dict.setdefault，不获取Python锁。
        candidate = time.monotonic() + self._close_budget_seconds()
        if deadline is None:
            return self._shutdown_state.setdefault('deadline', candidate)
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('shutdown requires finite absolute monotonic deadline')
        # 显式外部控制在普通线程调用：串行收紧，避免并发较晚写者延长更早D。
        with self._condition:
            original = self._shutdown_state.setdefault('deadline', candidate)
            selected = self._deadline(min(original, deadline))
            self._shutdown_state['deadline'] = selected
            self._close_deadline = selected
            return selected

    def request_close(self):
        self.begin_shutdown()
        self.connected.clear()
        self._wake.set()

    def _deadline(self, candidate):
        # 显式close可收紧信号形成的窗口；两个owner都只能缩短原D。
        return min(candidate, self._shutdown_state.get('deadline', candidate),
                   self._close_deadline if self._close_deadline is not None else candidate)

    def _fault(self, category, *, cleanup=False):
        with self._condition:
            if self._failure is None:
                self._failure = category
            if cleanup and self._cleanup_failure is None:
                self._cleanup_failure = category
            self._phase, self._admitting = 'faulted', False
        self.connected.clear()

    def _validate_runtime(self, runtime):
        if (getattr(runtime, 'trade_requests_enabled', False) is not False
                or canonical(runtime.profile) != self._profile
                or runtime.max_frame != self.max_frame or runtime.max_http_inflight != self.max_http_inflight
                or runtime.listen_host != self.listen_host or runtime.listen_port != self.listen_port
                or runtime.budget.connect_seconds != self.budget.connect_seconds
                or runtime.budget.io_seconds != self.budget.io_seconds):
            raise ValueError('runtime generation differs from fixed read-only service')
        limits = canonical(runtime.public_limits)
        with self._condition:
            if self._limits is not None and self._limits != limits:
                raise ValueError('runtime public limits changed across generations')
            self._limits = limits

    @contextmanager
    def _claim(self):
        # 只认领引用和计数；原request/health及任何I/O均在锁外执行。
        with self._condition:
            runtime = self._runtime if self._admitting and not self.shutdown_started else None
            if runtime is not None and runtime.connection_ended:
                runtime = None
            if runtime is not None:
                self._active += 1
        try:
            yield runtime
        finally:
            if runtime is not None:
                with self._condition:
                    self._active -= 1
                    self._condition.notify_all()
                self._wake.set()

    def request(self, request):
        with self._claim() as runtime:
            if runtime is None:
                return error(503, 'strategy_stale')
            return runtime.request(request)

    def health(self):
        last_tick, runtime_available = None, False
        with self._claim() as runtime:
            if runtime is not None:
                value = runtime.health()
                runtime_available = value.get('status') == 'available'
                tick = value.get('last_tick')
                if type(tick) in (float, int) and math.isfinite(tick):
                    last_tick = tick
        with self._condition:
            available = (runtime_available and runtime is self._runtime and self._admitting
                         and not self.shutdown_started and self.connected.is_set())
            return {'status': 'available' if available else 'unavailable', 'profile': 'restricted-read-only',
                    'order_ready': False, 'last_tick': last_tick, 'reason': self._failure,
                    'lifecycle': self._phase, 'generation': self._generation,
                    'active_calls': self._active, 'owner_pending': (self._runtime is not None
                        or self._creating or self._construction_owners[0] is not None),
                    'cleanup_reason': self._cleanup_failure}

    def _retire(self, runtime, deadline):
        with self._condition:
            self._admitting = False
            if self._failure is None:
                self._phase = 'retiring'
        self.connected.clear()
        try:
            with self._condition:
                while self._active:
                    remaining = self._deadline(deadline) - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('entered proxy calls remain owned')
                    self._condition.wait(min(remaining, self.poll_seconds))
            deadline = self._deadline(deadline)
            if time.monotonic() >= deadline:
                raise TimeoutError('original retirement deadline elapsed')
            first = None
            try:
                runtime.request_close()
            except BaseException as exc:
                first = exc
            try:
                runtime.close(deadline)
            except BaseException as exc:
                if first is None:
                    first = exc
            if first is not None:
                raise first
            if runtime.closed_complete is not True or runtime.io_resources_closed is not True:
                raise RuntimeError('generation close remains unconfirmed')
            with self._condition:
                # runtime.close可能与显式stop交错；释放owner前沿当前
                # 最早D确认，不能沿调用close前捕获的旧值报退休完成。
                deadline = self._deadline(deadline)
                if time.monotonic() >= deadline:
                    raise TimeoutError('generation close deadline elapsed')
                if self._runtime is not runtime:
                    raise RuntimeError('generation ownership differs')
                self._runtime = None
            return True
        except BaseException:
            self._fault('retirement_unconfirmed', cleanup=True)
            return False

    def _manage(self):
        self._entered.set()
        stage = 'factory'
        retirement_attempted = False
        retirement_deadline = None
        try:
            while not self.shutdown_started:
                with self._condition:
                    if self.shutdown_started:
                        break
                    self._creating, self._phase = True, 'starting'
                # 创建已在锁内认领；stop期间晚返回的owner仍接管，但绝不start。
                try:
                    runtime = self._factory(decode(self._configuration), credentials={
                        'ipc_secret': self._credentials['ipc_secret'],
                        'http_keys': dict(self._credentials['http_keys'])})
                finally:
                    with self._condition:
                        self._creating = False
                with self._condition:
                    self._runtime = runtime
                    self._generation += 1
                retirement_attempted, retirement_deadline = False, None
                if self.shutdown_started:
                    break
                stage = 'startup'
                self._validate_runtime(runtime)
                runtime.require_http_credentials(dict(self._credentials['http_keys']))
                runtime.start()  # 原start等待本代listener就绪，未改变有限handshake期限。
                self._validate_runtime(runtime)
                with self._condition:
                    if not self.shutdown_started:
                        self._admitting, self._phase = True, 'waiting'
                self._ready.set()
                stage = 'runtime'
                while not self.shutdown_started and not runtime.connection_ended:
                    connected = runtime.connected.is_set()
                    with self._condition:
                        self._phase = 'connected' if connected else 'waiting'
                    if connected and not self.shutdown_started:
                        self.connected.set()
                    else:
                        self.connected.clear()
                    self._wake.wait(self.poll_seconds)
                    self._wake.clear()
                recover = not self.shutdown_started and runtime.failure in _TRANSPORT
                if not self.shutdown_started and not recover:
                    self._fault(_category(runtime.failure, 'runtime'))
                retirement_attempted = True
                retirement_deadline = self._deadline(time.monotonic() + self._close_budget_seconds())
                if not self._retire(runtime, retirement_deadline):
                    return
                if not recover or self.shutdown_started:
                    break
                stage = 'factory'
                self._wake.wait(self.reconnect_seconds)
                self._wake.clear()
        except BaseException as exc:
            self._fault(_category(type(exc).__name__, stage))
        finally:
            # 单一manager是原runtime唯一退休者；close调用者仅请求停止和join本线程。
            runtime = self._runtime
            if runtime is not None and not retirement_attempted:
                retirement_deadline = self._deadline(time.monotonic() + self._close_budget_seconds())
                self._retire(runtime, retirement_deadline)
            self.connected.clear()
            with self._condition:
                self._admitting = False
                if self._failure is None:
                    self._phase = 'stopped'
            self._ready.set()

    def start(self):
        with self._condition:
            if self._thread is not None or self.shutdown_started:
                raise RuntimeError('read service starts once')
            self._thread = threading.Thread(target=self._manage, name='qmt-host-read-service', daemon=True)
            thread = self._thread
        deadline = time.monotonic() + self.budget.connect_seconds + self.budget.io_seconds + 1
        try:
            thread.start()
            self._start_returned = True
        except BaseException:
            self._fault('manager_start_unconfirmed')
            self.begin_shutdown(deadline)
            self._wake.set()
            raise RuntimeError('service manager start remains unconfirmed') from None
        ready = self._ready.wait(max(0, deadline - time.monotonic()))
        if ready:
            if self.failure is not None or self.shutdown_started:
                raise RuntimeError('service listener startup did not complete')
            # Event可在截止后已置位，恢复调度也可能很晚；成功以本次
            # 观测时的原绝对D为准，不因wait返回True另开启动窗口。
            if time.monotonic() < deadline:
                return
        self._fault('startup_timeout')
        self.begin_shutdown(deadline)
        self._wake.set()
        raise TimeoutError('service listener startup deadline elapsed')

    def close(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('service close requires absolute monotonic deadline')
        with self._condition:
            if self._closed_complete:
                return
            # Condition由本服务创建且使用RLock；显式close与外部stop共用
            # 同一发布函数，锁只覆盖原子最早D更新，不跨join或业务I/O。
            deadline = self.begin_shutdown(deadline)
        self.connected.clear()
        self._wake.set()
        deadline = self._deadline(deadline)
        thread = self._thread
        if thread is not None:
            if thread is threading.current_thread():
                raise RuntimeError('manager cannot join itself')
            if not self._start_returned and not self._entered.wait(max(0, deadline - time.monotonic())):
                raise TimeoutError('manager startup remains owned')
            thread.join(max(0, deadline - time.monotonic()))
            if thread.is_alive():
                raise TimeoutError('service manager remains owned')
        # manager已join，构造未返回的原Journal仍归创建槽；关闭沿同一D，
        # 失败保留该槽和原异常，实际关闭成功后才交还独占文件owner责任。
        with self._condition:
            construction_owner = self._construction_owners[0]
        if construction_owner is not None:
            construction_owner.close(self._deadline(deadline))
            with self._condition:
                if time.monotonic() >= self._deadline(deadline):
                    raise TimeoutError('construction owner close deadline elapsed')
                if self._construction_owners[0] is construction_owner:
                    self._construction_owners[0] = None
        with self._condition:
            # join期间显式stop可收紧D；与发布者共用同一锁确认完成。
            deadline = self._deadline(deadline)
            if (self._runtime is not None or self._creating or self._active
                    or self._construction_owners[0] is not None or time.monotonic() >= deadline):
                raise TimeoutError('service generation remains owned')
            self._closed_complete = True
            if self._failure is None:
                self._phase = 'stopped'
