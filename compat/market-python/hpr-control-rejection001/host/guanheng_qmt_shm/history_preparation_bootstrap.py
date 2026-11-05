"""默认关闭的缓存补齐工厂；仅显式v6复用原Host/Journal/重连服务。"""
from pathlib import Path
from guanheng_qmt_shm_agent.history_preparation import OPERATION, validate_configuration
from guanheng_qmt_shm_agent.protocol import canonical
from .bootstrap import (_snapshot_credentials, _validate_launch_configuration,
                        agent_settings as read_agent_settings)
from .bulk_clock import WindowsBulkUptimeClock
from .history_preparation_journal import HistoryPreparationJournal
from .read_service import ReconnectingReadService
from .runtime import HostReadRuntime


def agent_settings(config, policies, secret):
    settings = read_agent_settings(config, policies, secret)
    settings['max_pending'] = config['operation_profiles'][OPERATION]['limits']['max_queued']
    return settings


def validate_launch(config, *, credentials, policy_registry=None):
    config, policies, public = _validate_launch_configuration(config, credentials=credentials,
        trading=False, preparation=True, policy_registry=policy_registry)
    scope = config['operation_profiles'][OPERATION]['limits']
    policy = policies.require('qmt.history-preparation.v1', OPERATION)
    if (config['max_records'] > scope['max_tasks'] or policy.max_attempts != 1
            or policy.retryable_error_codes or policy.retry_backoff_initial_ms or policy.retry_backoff_max_ms
            or policy.queue_timeout_ms + policy.execution_timeout_ms > scope['total_timeout_ms']):
        raise ValueError('preparation requires finite single-attempt deployment budgets')
    return config, policies, public


def _build_runtime(config, policies, public, credentials, *, clock, wait_for_agent=False, failed_owners=None):
    if failed_owners is not None and (len(failed_owners) != 1 or failed_owners[0] is not None):
        raise ValueError('one reserved construction owner required')
    profile = validate_configuration(agent_settings(config, policies, credentials['ipc_secret'])).profile
    journal_type, runtime_type = HistoryPreparationJournal, HostReadRuntime
    if 'read_retention' in config:
        from .read_retention_journal import RetainedPreparationJournal
        from .read_retention_runtime import RetainedReadRuntime
        journal_type, runtime_type = RetainedPreparationJournal, RetainedReadRuntime
    from .journal import construct_journal
    journal = construct_journal(journal_type, Path(config['journal_path']), config['route'],failed_owners=failed_owners,
        max_records=config['max_records'], max_result_bytes=config['max_result_bytes'],
        max_request_bytes=public['max_request_bytes'], max_journal_bytes=config['max_journal_bytes'],
        read_profile=profile, clock=clock)
    if failed_owners is not None:
        failed_owners[0] = journal
    try:
        runtime = runtime_type(journal, secret=credentials['ipc_secret'], max_frame=config['max_frame'],
            policies=policies, transport=config['transport'], control_profile=config['control_profile'],
            connect_seconds=config['connect_seconds'], io_seconds=config['io_seconds'],
            max_http_inflight=config['max_http_inflight'], read_profile=profile, wait_for_agent=wait_for_agent)
        runtime.listen_host, runtime.listen_port = config['listen_host'], config['listen_port']
        if failed_owners is not None:
            failed_owners[0] = None
        return runtime
    except BaseException:
        try:
            journal.close()
        except BaseException:
            if failed_owners is None:
                raise
        else:
            if failed_owners is not None:
                failed_owners[0] = None
        raise


def build_runtime(config, *, credentials, clock=None):
    """新显式入口；创建原Journal及Host，调用start才连接认证SHM。"""
    credentials = _snapshot_credentials(credentials)
    config, policies, public = validate_launch(config, credentials=credentials)
    return _build_runtime(config, policies, public, credentials,
        clock=WindowsBulkUptimeClock() if clock is None else clock)


def build_read_service(config, *, credentials, reconnect_seconds, clock=None):
    credentials = _snapshot_credentials(credentials)
    config, policies, public = validate_launch(config, credentials=credentials)
    return _build_read_service(config, policies, public, credentials,
        reconnect_seconds=reconnect_seconds, clock=clock)


def _build_read_service(config, policies, public, credentials, *, reconnect_seconds, clock=None,
                        service_type=None):
    """消费同次离线核验的快照；不重读policy或创建第二套运输。"""
    credentials = _snapshot_credentials(credentials)
    clock = WindowsBulkUptimeClock() if clock is None else clock
    frozen = canonical(config)
    profile = validate_configuration(agent_settings(config, policies, credentials['ipc_secret'])).profile
    owners = [None]
    def factory(candidate, *, credentials):
        if canonical(candidate) != frozen:
            raise ValueError('preparation deployment changed')
        return _build_runtime(candidate, policies, public, credentials, clock=clock,
            wait_for_agent=True, failed_owners=owners)
    service_type = ReconnectingReadService if service_type is None else service_type
    return service_type(factory, configuration=config, credentials=credentials,
        profile=profile, reconnect_seconds=reconnect_seconds, construction_owners=owners)
