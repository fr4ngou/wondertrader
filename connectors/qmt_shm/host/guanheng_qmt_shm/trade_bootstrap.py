"""显式交易配置与组合工厂；准入先于存储 owner，构造不启动运输。"""
import math
from pathlib import Path
from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
from guanheng_qmt_shm_agent.trade_clock import SharedUptimeClock
from .bootstrap import agent_settings, _validate_launch_configuration, _snapshot_credentials
from .bound import MAX_METADATA_BYTES
from .trading_journal import HostTradingJournal, validate_trade_journal_configuration
from .trade_event_records import validate_trade_event_storage


def trade_agent_settings(config, policies, secret):
    """从受信 Host 配置产生完整私有 bootstrap，不隐式开启任何字段。"""
    value = agent_settings(config, policies, secret)
    value.update(trade_profile=config['trade_profile'],
                 trade_binding=config['trade_binding'],
                 writes_enabled=config['writes_enabled'])
    return value


def validate_trade_storage(config, admitted):
    """复用存储身份算法，另外保证至少能保存一条最大命令及完整回执。"""
    limits = admitted.profile['trade_profile']['limits']
    unused, identity_bytes = validate_trade_journal_configuration(admitted.trade_binding,
        max_trade_commands=limits['max_commands'], max_trade_bytes=config['max_trade_bytes'],
        max_trade_result_bytes=limits['max_call_result_bytes'])
    minimum = (len(identity_bytes) + limits['max_command_bytes']
               + limits['max_call_result_bytes'] + MAX_METADATA_BYTES)
    if config['max_trade_bytes'] < minimum:
        raise ValueError('trade Journal cannot reserve one complete maximum command')
    if 'event_storage' in config:
        storage, unused, unused_identity, unused_sha = validate_trade_event_storage(
            admitted.profile, admitted.trade_binding, config['event_storage'],
            max_result_bytes=config['max_result_bytes'])
        interval = config['event_poll_seconds']
        if (type(interval) not in (int, float) or not math.isfinite(interval)
                or not .01 <= interval <= min(60, admitted.control_profile.max_call_seconds)):
            raise ValueError('invalid explicit trade event poll interval')
        maximum = max(config['max_result_bytes'] + MAX_METADATA_BYTES,
            limits['max_call_result_bytes'] + MAX_METADATA_BYTES,
            4*((limits['max_command_bytes']+2)//3) + MAX_METADATA_BYTES,
            4*((storage['max_page_bytes']+2)//3) + MAX_METADATA_BYTES)
        if maximum > 4194304:
            raise ValueError('trade domain payload exceeds capacity')


def validate_trade_launch(config, *, credentials):
    """显式读取终端外 policy 并统一校验；不授真实交易或工厂运行资格。"""
    return _validate_launch_configuration(config, credentials=credentials, trading=True)


def build_trade_runtime(config, *, credentials, business_clock=None,
                        wait_for_agent=False, failed_owners=None, connection_continuity=None):
    """显式交易入口；源 Agent 仍只接原 R16 字段，Host 复用唯一通信文件。"""
    credentials = _snapshot_credentials(credentials)
    config, policies, public = validate_trade_launch(config, credentials=credentials)
    return _build_trade_runtime(config, policies, public, credentials,
        business_clock=business_clock, wait_for_agent=wait_for_agent, failed_owners=failed_owners,
        connection_continuity=connection_continuity)


def _build_trade_runtime(config, policies, public, credentials, *, business_clock=None,
                         wait_for_agent=False, failed_owners=None, connection_continuity=None):
    """复用已冻结准入；显式常驻产品保留构造期 owner，原入口默认仍是单代。"""
    if failed_owners is not None and (type(failed_owners) is not list
            or len(failed_owners) != 1 or failed_owners[0] is not None):
        raise ValueError('construction owner requires one empty reserved slot')
    if not {'event_storage', 'event_poll_seconds'} <= set(config):
        raise ValueError('explicit event storage and polling configuration required')
    if business_clock is None:
        business_clock = SharedUptimeClock().seconds
    if not callable(business_clock):
        raise ValueError('shared business clock required')
    admitted = validate_trade_configuration(trade_agent_settings(config, policies, credentials['ipc_secret']))
    limits = admitted.profile['trade_profile']['limits']
    from .trade_runtime import HostTradingRuntime
    journal_type, runtime_type, journal_extra = HostTradingJournal, HostTradingRuntime, {}
    if 'read_retention' in config:
        from .read_retention_journal import RetainedTradingJournal
        from .read_retention_runtime import RetainedTradingRuntime
        from .bulk_clock import WindowsBulkUptimeClock
        journal_type, runtime_type = RetainedTradingJournal, RetainedTradingRuntime
        journal_extra = {'retention_clock': WindowsBulkUptimeClock()}
    elif 'http_read_retention' in config:
        from .read_retention_journal import HttpRetainedTradingJournal
        from .read_retention_runtime import HttpRetainedTradingRuntime
        from .bulk_clock import WindowsBulkUptimeClock
        journal_type,runtime_type=HttpRetainedTradingJournal,HttpRetainedTradingRuntime
        journal_extra={'retention_clock':WindowsBulkUptimeClock(),'http_retention':config['http_read_retention']}
    from .journal import construct_journal
    journal = construct_journal(journal_type, Path(config['journal_path']), config['route'],failed_owners=failed_owners,
        max_records=config['max_records'], max_result_bytes=config['max_result_bytes'],
        max_request_bytes=public['max_request_bytes'], max_journal_bytes=config['max_journal_bytes'],
        trade_binding=admitted.trade_binding, max_trade_commands=limits['max_commands'],
        max_trade_bytes=config['max_trade_bytes'], max_trade_result_bytes=limits['max_call_result_bytes'],
        read_profile=admitted.profile, event_storage=config['event_storage'], clock=business_clock,
        connection_continuity=connection_continuity, trade_binding_extension=config.get('trade_binding_extension'), **journal_extra)
    if failed_owners is not None:
        failed_owners[0] = journal
    try:
        runtime = runtime_type(journal, secret=credentials['ipc_secret'], max_frame=config['max_frame'],
            policies=policies, transport=config['transport'], control_profile=config['control_profile'],
            connect_seconds=config['connect_seconds'], io_seconds=config['io_seconds'],
            max_http_inflight=config['max_http_inflight'], read_profile=admitted.profile,
            writes_enabled=config['writes_enabled'], event_storage=config['event_storage'],
            event_poll_seconds=config['event_poll_seconds'], business_clock=business_clock,
            wait_for_agent=wait_for_agent, connection_continuity=connection_continuity)
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
            # 与原只读工厂相同：清理未确认时原槽仍持有Journal，保留构造首因。
        else:
            if failed_owners is not None:
                failed_owners[0] = None
        raise
