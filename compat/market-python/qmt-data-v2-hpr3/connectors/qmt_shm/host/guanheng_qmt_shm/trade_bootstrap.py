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


def build_trade_runtime(config, *, credentials, business_clock=None):
    """显式交易入口；源 Agent 仍只接原 R16 字段，Host 复用唯一通信文件。"""
    credentials = _snapshot_credentials(credentials)
    config, policies, public = validate_trade_launch(config, credentials=credentials)
    if not {'event_storage', 'event_poll_seconds'} <= set(config):
        raise ValueError('explicit event storage and polling configuration required')
    if business_clock is None:
        business_clock = SharedUptimeClock().seconds
    if not callable(business_clock):
        raise ValueError('shared business clock required')
    admitted = validate_trade_configuration(trade_agent_settings(config, policies, credentials['ipc_secret']))
    limits = admitted.profile['trade_profile']['limits']
    journal = HostTradingJournal(Path(config['journal_path']), config['route'],
        max_records=config['max_records'], max_result_bytes=config['max_result_bytes'],
        max_request_bytes=public['max_request_bytes'], max_journal_bytes=config['max_journal_bytes'],
        trade_binding=admitted.trade_binding, max_trade_commands=limits['max_commands'],
        max_trade_bytes=config['max_trade_bytes'], max_trade_result_bytes=limits['max_call_result_bytes'],
        read_profile=admitted.profile, event_storage=config['event_storage'], clock=business_clock)
    try:
        from .trade_runtime import HostTradingRuntime
        runtime = HostTradingRuntime(journal, secret=credentials['ipc_secret'], max_frame=config['max_frame'],
            policies=policies, transport=config['transport'], control_profile=config['control_profile'],
            connect_seconds=config['connect_seconds'], io_seconds=config['io_seconds'],
            max_http_inflight=config['max_http_inflight'], read_profile=admitted.profile,
            writes_enabled=config['writes_enabled'], event_storage=config['event_storage'],
            event_poll_seconds=config['event_poll_seconds'], business_clock=business_clock)
        runtime.listen_host, runtime.listen_port = config['listen_host'], config['listen_port']
        return runtime
    except BaseException:
        journal.close()
        raise
