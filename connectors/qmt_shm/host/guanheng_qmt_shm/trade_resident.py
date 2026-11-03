"""显式交易产品复用原常驻管理器；单代交易/Journal仍由原工厂拥有。"""
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_capabilities import validate_read_profile
from guanheng_qmt_shm_agent.trade_capabilities import validate_trade_profile_binding
from .bootstrap import _snapshot_credentials
from .read_service import ReconnectingReadService
from .trade_bootstrap import _build_trade_runtime
from .trade_event_records import CONTINUITY_VERSION


class ReconnectingTradingService(ReconnectingReadService):
    """只选择显式交易准入与原交易窗口，管理/退休/引用计数沿父实现。"""
    trade_requests_enabled = True

    def __init__(self, *args, **kwargs):
        self._first_fault = None
        super().__init__(*args, **kwargs)

    @staticmethod
    def _reason(value):
        # 只输出原固定类别；异常正文/外部字符串保留在原owner内。
        values = {'OSError', 'TimeoutError', 'BrokenPipeError', 'ConnectionResetError',
            'AuthenticationError', 'PermissionError', 'ProtocolError', 'GatewayError',
            'ValueError', 'TypeError', 'KeyError', 'RuntimeError', 'OperationalError',
            'DatabaseError', 'IntegrityError', 'journal_unavailable',
            'trade_shutdown_unconfirmed', 'control_interrupt_unconfirmed'}
        return None if value is None else value if type(value) is str and value in values else 'other'

    def _fault(self, category, *, cleanup=False):
        with self._condition:
            if self._first_fault is None:
                runtime = self._runtime
                control = None if runtime is None else runtime._control
                stages = {'idle', 'status', 'stream', 'ack', 'page', 'finish', 'retiring'}
                categories = {stage + '_' + kind for stage in ('factory', 'startup', 'runtime')
                    for kind in ('transport', 'authentication_or_protocol', 'configuration', 'journal', 'fault')}
                categories.update(('startup_timeout', 'manager_start_unconfirmed', 'retirement_unconfirmed'))
                stage = None if control is None else control._poll_stage
                read_future = None if control is None else control._read_commit
                read_done = read_future is not None and read_future.done()
                read_failure = None
                if read_done and not read_future.cancelled():
                    read_error = read_future.exception()
                    read_failure = self._reason(None if read_error is None else type(read_error).__name__)
                self._first_fault = dict(category=category if category in categories else 'other',
                    cleanup=bool(cleanup), generation=self._generation,
                    runtime_failure=self._reason(None if runtime is None else runtime.failure),
                    runtime_cleanup=self._reason(None if runtime is None else runtime.cleanup_failure),
                    runtime_interruption=self._reason(None if runtime is None else runtime.interruption_failure),
                    poll_stage=stage if stage in stages else None,
                    domain_jobs=0 if control is None else len(control._jobs),
                    runtime_present=runtime is not None,
                    read_commit_present=read_future is not None,  # 原只读持久任务是否仍保留；与交易jobs分开。
                    read_commit_done=read_done,  # 原Future是否完成，区分域仍运行和已结束异常。
                    read_commit_failure=read_failure)  # 原Future固定异常类别；不输出结果或账户正文。
        # 诊断只捕获纯值；管理器、停止和原截止行为仍由父实现执行。
        super()._fault(category, cleanup=cleanup)

    @property
    def fault_snapshot(self):
        with self._condition:
            return None if self._first_fault is None else dict(self._first_fault)

    def _admit_configuration(self, configuration, profile):
        if (configuration.get('transport', {}).get('kind') != 'builtin-shm'
                or type(configuration.get('writes_enabled')) is not bool):
            raise ValueError('explicit builtin SHM trade configuration required')
        checked = validate_read_profile(profile, max_result_bytes=configuration['max_result_bytes'])
        if (checked.get('read_profile_version') != 'qmt.read-profile.v4'
                or checked['read_operations'] != configuration['read_operations']):
            raise ValueError('explicit trade profile differs')
        validate_trade_profile_binding(checked['trade_profile'], configuration['trade_binding'])
        return checked

    def _close_budget_seconds(self):
        configuration = decode(self._configuration)
        return configuration['control_profile']['max_call_seconds'] + 2 * self.budget.io_seconds + 1

    def _validate_runtime(self, runtime):
        configuration = decode(self._configuration)
        if (getattr(runtime, 'trade_requests_enabled', False) is not True
                or canonical(runtime.profile) != self._profile
                or runtime.writes_enabled != configuration['writes_enabled']
                or runtime.max_frame != self.max_frame or runtime.max_http_inflight != self.max_http_inflight
                or runtime.listen_host != self.listen_host or runtime.listen_port != self.listen_port
                or runtime.budget.connect_seconds != self.budget.connect_seconds
                or runtime.budget.io_seconds != self.budget.io_seconds):
            raise ValueError('trade runtime generation differs from frozen service')
        limits = canonical(runtime.public_limits)
        with self._condition:
            if self._limits is not None and self._limits != limits:
                raise ValueError('trade public limits changed across generations')
            self._limits = limits

    def health(self):
        value = super().health()
        value['profile'] = 'restricted-shm-trading'
        # 单代trade.status负责实际下单/撤单准入；健康只报告常驻和来源连接。
        return value


def build_service(config, credentials, policies, public, profile, reconnect_seconds):
    """消费一次已准入快照；各代仅重开同一通信Journal，不重新读policy文件。"""
    credentials = _snapshot_credentials(credentials)
    configuration = canonical(config)
    owners = [None]

    def factory(candidate, *, credentials):
        if canonical(candidate) != configuration:
            raise ValueError('trade service configuration changed')
        return _build_trade_runtime(candidate, policies, public, credentials,
            wait_for_agent=True, failed_owners=owners, connection_continuity=CONTINUITY_VERSION)

    return ReconnectingTradingService(factory, configuration=config, credentials=credentials,
        profile=profile, reconnect_seconds=reconnect_seconds, construction_owners=owners)
