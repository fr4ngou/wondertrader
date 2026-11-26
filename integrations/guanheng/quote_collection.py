"""QST6 受管装配：唯一接收线程将已校验报价直接交给原生 DataKit。"""
from __future__ import annotations

import math
import threading
import time

from .datakit import NativeDataKitSession
from .quote_counter_observation import QuoteCounterObservation


class QuoteCollection:
    """构造不创建原生或运输资源；start 所在线程拥有此实例的管理生命周期。

    start 只等待 listener 就绪。request_close 可跨线程发布停止；close 接收
    monotonic 秒数表示的绝对截止，先确认接收线程和运输已关闭，再关闭原生会话。
    原生 I/O 无 Python 中断保证，外层进程 owner 必须沿同一截止管理阻塞。
    显式 archive_session 要求原生实例支持排空归档；文件正确性另由 Helper 回读。
    工厂分别遵循 NativeDataKitSession(config, directory) 和
    QuoteStreamReceiver(settings=..., on_batch=...) 的公开契约。
    """

    def __init__(self, settings, datakit_config, native_directory, archive_session=None,
                 *, native_factory=None, receiver_factory=None,
                 clock=time.monotonic, wall_clock=time.time, coverage=None):
        self._settings = settings
        self._datakit_config = datakit_config
        self._native_directory = native_directory
        self._archive_session = archive_session
        self._native_factory = native_factory or NativeDataKitSession
        self._receiver_factory = receiver_factory
        self._clock, self._wall_clock = clock, wall_clock
        self._coverage = coverage  # 可选纯时间投影；成功交付后更新，管理线程读取独立有界快照。
        self._counter_observation = QuoteCounterObservation(settings['symbols'])  # 原锁拥有；原计数修订不改变交付数据。
        self._guard = threading.Lock()
        self._owner = None
        self._operation = None
        self._receiver = self._native = None
        self._phase = "new"
        self._stop_requested = False
        self._close_deadline = None
        self._native_close_started = False
        self._archive_started = False
        self._closed_complete = False
        self._error = None
        self._received_batches = self._received_ticks = self._pushed_ticks = 0
        self._latest_source_time_ms = self._observed_wall_time = None
        self._native_counts = {"subscribed": 0, "delivered": 0, "writer_processed": 0}

    def _fail(self, code):
        with self._guard:
            if self._error is None:
                self._error = code
            if not self._closed_complete:
                self._phase = "failed"

    def _cache_counts(self, native):
        # 仅 start、唯一消费线程或 join 后的管理线程读取；status 从不碰原生句柄。
        values = native.counts()
        counts = {key: values[key] for key in self._native_counts}
        with self._guard:
            self._native_counts = counts

    def start(self):
        """唯一一次启动；失败仍保留 owner 和已创建资源，由该 owner 调用 close。"""
        with self._guard:
            if self._phase != "new" or self._operation is not None:
                raise RuntimeError("quote_collection_single_use")
            self._owner = threading.current_thread()
            self._operation, self._phase = "start", "starting"
        stage = "receiver_configuration_failed"
        try:
            factory = self._receiver_factory
            if factory is None:
                from guanheng_qmt_shm.quote_stream import QuoteStreamReceiver
                factory = QuoteStreamReceiver
            # Receiver 构造先校验共享合同，非法运输配置不会创建原生 Writer。
            receiver = factory(settings=self._settings, on_batch=self._on_batch)
            with self._guard:
                self._receiver = receiver
                stopping = self._stop_requested
            if stopping:
                raise RuntimeError("quote_collection_stop_requested")
            stage = "archive_configuration_failed"
            if self._archive_session is not None:
                sid = self._archive_session
                if (type(sid) is not str or not sid or len(sid) > 15
                        or not sid.isascii() or "\x00" in sid):
                    raise ValueError("quote_collection_archive_session")
            stage = "native_initialization_failed"
            native = self._native_factory(self._datakit_config, self._native_directory)
            with self._guard:
                self._native = native
            stage = "archive_capability_required"
            if self._archive_session is not None and not native.supports_draining_archive:
                raise RuntimeError("quote_collection_archive_capability_required")
            stage = "native_counts_failed"
            self._cache_counts(native)
            with self._guard:
                stopping = self._stop_requested
            if stopping:
                stage = "start_cancelled"
                raise RuntimeError("quote_collection_stop_requested")
            stage = "receiver_start_failed"
            receiver.start()
            with self._guard:
                failed = self._error is not None
                if not failed:
                    self._phase = "stop_requested" if self._stop_requested else "running"
            if failed:
                stage = "consumer_failed"
                raise RuntimeError("quote_collection_consumer_failed")
            return self
        except BaseException:
            self._fail(stage)
            self.request_close()
            raise RuntimeError("quote_collection_" + stage) from None
        finally:
            with self._guard:
                self._operation = None

    def _on_batch(self, ticks, kind):
        # Receiver 已整包校验且独占此回调；不复制/换算行情，不跨代创建第二个 Writer。
        # 已进入的回调允许完成，关闭方以 Receiver 的实际 join 为释放前置条件。
        stage = "native_push_failed"
        try:
            observed = self._wall_clock()
            source = max(row["time"] for row in ticks.values())
            with self._guard:
                native = self._native
                self._counter_observation.observe(ticks, kind)
                self._received_batches += 1
                self._received_ticks += len(ticks)
                self._observed_wall_time = observed
                if self._latest_source_time_ms is None or source > self._latest_source_time_ms:
                    self._latest_source_time_ms = source
            pushed = native.push(ticks, kind)
            if pushed != len(ticks):
                raise RuntimeError("quote_collection_batch_result_unknown")
            if self._coverage is not None:
                self._coverage.accept(ticks, observed)
            with self._guard:
                self._pushed_ticks += pushed
            stage = "native_counts_failed"
            self._cache_counts(native)
        except BaseException:
            # 本包可能已部分生效；保留计数和固定错误，停止流，不安排重放。
            self._fail(stage)
            self.request_close()
            raise RuntimeError("quote_collection_" + stage) from None

    def request_close(self):
        """任意线程可调用；仅通知运输停止，原生资源仍归管理 owner。"""
        with self._guard:
            self._stop_requested = True
            receiver = self._receiver
            if self._phase not in ("failed", "closed", "closing_receiver", "closing_native"):
                self._phase = "stop_requested"
        if receiver is not None:
            receiver.request_close()

    def current_days(self):
        """管理owner读取实际订阅的原Writer副本；与status缓存及交易策略独立。"""
        with self._guard:
            if self._owner is not threading.current_thread() or self._operation is not None:
                raise RuntimeError('quote_collection_management_owner_required')
            native=self._native
            if native is None or self._closed_complete:
                raise RuntimeError('quote_collection_current_day_unavailable')
        return native.current_days(self._settings['symbols'])

    def check_health(self):
        """管理线程检查原生错误闩锁；即使来源空闲也能停止已失败的Writer。"""
        with self._guard:
            if self._owner is not threading.current_thread() or self._operation is not None:
                raise RuntimeError("quote_collection_management_owner_required")
            native = self._native
            closed = self._closed_complete
        if native is None or closed:
            return
        try:
            native.check_health()
        except BaseException:
            self._fail("native_writer_failed")
            self.request_close()
            raise RuntimeError("quote_collection_native_writer_failed") from None

    def _failed_close(self, stage, receiver, native):
        self._fail(stage)
        # 原生close可能已释放资源并报告Writer业务失败；保留错误且确认真实释放。
        # 资源未确认时继续由本实例及外层进程持有，目录锁随同保留。
        if ((receiver is None or receiver.closed_complete)
                and (native is None or native.closed)):
            with self._guard:
                self._closed_complete = True
                self._phase = "closed"

    def close(self, deadline):
        """沿首次绝对截止收束；接收未闭时抛错并保留原生会话，重复调用不续期。

        归档调用一旦进入，异常后只继续原生 close，避免重复提交未知归档。
        成功返回只确认公开关闭契约；原 DLL 的内部行为由所选模块负责。
        """
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError("quote_collection_finite_absolute_deadline_required")
        with self._guard:
            if self._owner is not None and self._owner is not threading.current_thread():
                raise RuntimeError("quote_collection_management_owner_required")
            if self._operation is not None:
                raise RuntimeError("quote_collection_management_operation_active")
            if self._closed_complete:
                return True
            if self._close_deadline is None:
                self._close_deadline = deadline
            original = self._close_deadline
            self._operation, self._phase = "close", "closing_receiver"
            receiver, native = self._receiver, self._native
        stage = "receiver_close_failed"
        try:
            self.request_close()
            if receiver is not None:
                receiver.close(original)
                if not receiver.closed_complete:
                    raise RuntimeError("quote_collection_receiver_close_unconfirmed")
            if native is not None and not native.closed:
                # 接收已 join，counts 与释放没有并发；先保留最后一次有效快照。
                # 观测失败不能阻断资源回收，错误仍记录在公开状态中。
                try:
                    self._cache_counts(native)
                except BaseException:
                    self._fail("native_counts_failed")
                stage = "native_close_deadline"
                if self._clock() >= original:
                    raise TimeoutError("quote_collection_native_close_deadline")
                supports_archive = native.supports_draining_archive
                with self._guard:
                    self._phase = "closing_native"
                    self._native_close_started = True
                    archive = (self._archive_session is not None and not self._archive_started
                               and supports_archive)
                    if archive:
                        self._archive_started = True
                stage = "native_close_failed"
                # 不持状态锁进入 C++；实际阻塞由外层进程沿 original 收口。
                if archive:
                    native.archive_and_close(self._archive_session)
                else:
                    native.close()
                if not native.closed:
                    raise RuntimeError("quote_collection_native_close_unconfirmed")
            with self._guard:
                self._closed_complete = True
                self._phase = "closed"
            return True
        except TimeoutError:
            self._failed_close(stage, receiver, native)
            raise TimeoutError("quote_collection_" + stage) from None
        except BaseException:
            self._failed_close(stage, receiver, native)
            raise RuntimeError("quote_collection_" + stage) from None
        finally:
            with self._guard:
                self._operation = None

    @property
    def closed_complete(self):
        """接收线程/运输已确认关闭，且已创建的原生会话完成公开 close。"""
        with self._guard:
            return self._closed_complete

    def status(self):
        """脱敏快照；received 为进入消费回调数，pushed 为整包成功返回数。

        source 为所见最大源 epoch 毫秒，observed 为最近回调的本机 epoch 秒；
        两者独立记录。native_counts 为最近有效快照，无法据此宣称归档文件完整。
        Receiver 投影和本对象快照分别取锁，代际/计数允许反映相邻观察时点。
        """
        with self._guard:
            receiver = self._receiver
            result = {
                "phase": self._phase, "error": self._error,
                "received_batches": self._received_batches,
                "received_ticks": self._received_ticks, "pushed_ticks": self._pushed_ticks,
                "native_counts": dict(self._native_counts),
                "latest_source_time_ms": self._latest_source_time_ms,
                "observed_wall_time": self._observed_wall_time,
                "close_deadline": self._close_deadline,
                "native_close_started": self._native_close_started,
                "closed_complete": self._closed_complete,
                "source_counter_observation": self._counter_observation.snapshot(),  # 原来源计数的有界摘录，不授分钟质量资格。
            }
        received = {} if receiver is None else receiver.status()
        heartbeat = received.get("heartbeat")
        if heartbeat is not None:
            from guanheng_qmt_shm_agent.quote_stream_contract import COUNTER_FIELDS
            heartbeat = {key: heartbeat[key] for key in COUNTER_FIELDS}
        # 只投影合同字段；市场计数仅保上述16条摘录，凭据、配置、账户和完整报价不进入状态。
        failure = received.get("failure")
        cleanup = received.get("cleanup_failure")
        result.update(
            generation=received.get("generation", 0),
            connected=received.get("connected", False),
            receiver_batches=received.get("batches", 0),
            receiver_received_ticks=received.get("received_ticks", 0),
            receiver_heartbeats=received.get("heartbeats", 0),
            source_heartbeat=heartbeat,
            receiver_failure=failure if failure in (None, "consumer_failed", "connection_ended") else "receiver_failed",
            receiver_cleanup_failure=None if cleanup is None else "transport_close_unconfirmed",
            recent_disconnects=received.get("recent_disconnects", []),  # 原接收线程的有界断线证据，不授分钟完整性。
        )
        return result
