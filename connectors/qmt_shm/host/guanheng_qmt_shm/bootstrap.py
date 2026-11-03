"""受管配置先统一准入，再获取独占通信Journal；不读取旧工程默认配置。"""
from __future__ import annotations
import os
from pathlib import Path
import re
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_configuration import validate_read_configuration
from guanheng_qmt_shm_agent.read_capabilities import operation_descriptor, explicit_profile_version
from .bound import limits
from .bound_journal import BoundReadJournal
from .policy import OperationPolicyRegistry
from .runtime import HostReadRuntime

FIELDS=frozenset(('route','ipc_secret_env','http_secret_env','http_key_id','journal_path',
    'max_records','max_result_bytes','max_journal_bytes','max_frame','max_http_inflight','read_operations',
    'operation_policies_path','listen_host','listen_port','connect_seconds','io_seconds',
    'transport','control_profile'))


def _snapshot_credentials(credentials):
    """公开入口先捕获不可变凭证值；后续I/O不再读取调用者dict。

    HTTP key映射复制为单角色新dict，IPC secret为精确bytes。该快照只在
    私有owner内使用，不进入返回值/日志，配对两端和Runtime共用同次值。
    """
    message='private deployment credentials required'
    try:
        if type(credentials) is not dict or set(credentials)!={'ipc_secret','http_keys'}:
            raise ValueError(message)
        secret,keys=credentials['ipc_secret'],credentials['http_keys']
        if type(secret) is not bytes or len(secret)<32 or type(keys) is not dict or len(keys)!=1:
            raise ValueError(message)
        # 只捕获一项；精确dict无自定义迭代钩子，读取失败沿同一错误边界拒绝。
        key,value=next(iter(keys.items()))
        if (len(keys)!=1 or type(key) is not str or not 1<=len(key)<=128
                or type(value) is not str or not value or value.encode('utf-8')==secret):
            raise ValueError(message)
    except (KeyError,StopIteration,RuntimeError,UnicodeError):
        raise ValueError(message) from None
    return {'ipc_secret':secret,'http_keys':{key:value}}


def agent_settings(config,policies,secret):
    """受管Host配置到同版Agent字段；不推断或自动启用能力。"""
    ops=config['read_operations']
    if ops==['market.full_tick']:
        timeout=policies.require('qmt.standard-read.v1','market.full_tick').execution_timeout_ms
    else:
        entries=config['operation_profiles']
        if type(entries) is not dict or set(entries)!=set(ops):
            raise ValueError('operation profiles differ from explicit operations')
        timeouts=[entries[op].get('execution_timeout_ms') if type(entries[op]) is dict else None for op in ops]
        if any(type(value) is not int for value in timeouts):
            raise ValueError('explicit execution policy required')
        timeout=max(timeouts)
    value={'route':config['route'],'secret':secret,'allowed_operations':ops,'execution_timeout_ms':timeout,
        'max_frame':config['max_frame'],'max_pending':1,'max_result_bytes':config['max_result_bytes'],
        'connect_seconds':config['connect_seconds'],'io_seconds':config['io_seconds'],
        'transport':config['transport'],'control_profile':config['control_profile']}
    if ops!=['market.full_tick']:
        value.update(read_profile_version=config['read_profile_version'],operation_profiles=config['operation_profiles'])
    if 'read_retention' in config:
        value['read_retention']=config['read_retention']
    return value


def validate_launch(config, *, credentials):
    """旧只读部署入口保持原字段及版本；不会选择交易配置。"""
    return _validate_launch_configuration(config, credentials=credentials, trading=False)


def _validate_launch_configuration(config, *, credentials, trading, policy_registry=None, bulk=False, preparation=False):
    """同一配置/凭证/policy owner；新交易分支只由显式入口选择。"""
    credentials=_snapshot_credentials(credentials)
    if preparation and (bulk or trading):
        raise ValueError('exclusive history preparation deployment required')
    if bulk:
        if trading:
            raise ValueError('exclusive managed profile required')
        accepted=(FIELDS|{'read_profile_version','operation_profiles','bulk_profile','bulk_settings'},)
    elif trading:
        fields=FIELDS|{'read_profile_version','operation_profiles','trade_profile',
            'trade_binding','writes_enabled','max_trade_bytes'}
        accepted=(fields,fields|{'event_storage','event_poll_seconds'})
    elif preparation:
        accepted=(FIELDS|{'read_profile_version','operation_profiles'},)
    else:
        accepted=(FIELDS,FIELDS|{'read_profile_version','operation_profiles'})
    if type(config) is dict and 'read_retention' in config:
        if bulk:
            raise ValueError('read retirement requires an independent read owner')
        accepted=tuple(fields|{'read_retention'} for fields in accepted)
    if type(config) is dict and 'http_read_retention' in config:
        # 仅交易Host的HTTP结果生命周期；不加入agent_settings或Source profile。
        if not trading or 'read_retention' in config:
            raise ValueError('HTTP read retirement requires a distinct v4 Host capability')
        from guanheng_qmt_shm_agent.read_retention import retention
        retention(config['http_read_retention'])
        accepted=tuple(fields|{'http_read_retention'} for fields in accepted)
    if type(config) is not dict or set(config) not in accepted:
        raise ValueError('managed Host config has missing or unsupported fields')
    config=decode(canonical(config))
    if type(config['max_http_inflight']) is not int or not 1<=config['max_http_inflight']<=128:
        raise ValueError('invalid explicit HTTP concurrency budget')
    for name in ('ipc_secret_env','http_secret_env'):
        if not isinstance(config[name],str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',config[name]):
            raise ValueError('invalid credential environment reference')
    keys=credentials['http_keys']
    if (type(config['http_key_id']) is not str or not 1<=len(config['http_key_id'])<=128
            or set(keys)!={config['http_key_id']}):
        raise ValueError('distinct private HTTP credential required')
    ops=config['read_operations']
    if bulk:
        if config['read_profile_version']!='qmt.read-profile.v5':
            raise ValueError('explicit bulk read profile version required')
    elif trading:
        if config['read_profile_version']!='qmt.read-profile.v4':
            raise ValueError('explicit trade read profile version required')
    elif preparation:
        if config['read_profile_version']!='qmt.read-profile.v6':
            raise ValueError('explicit preparation profile required')
    else:
        version=explicit_profile_version(ops, config.get('operation_profiles'))
        base_fields=set(config)-({'read_retention'} if 'read_retention' in config else set())
        if (version is None and base_fields!=FIELDS or version is not None
                and (base_fields!=FIELDS|{'read_profile_version','operation_profiles'} or config['read_profile_version']!=version)):
            raise ValueError('explicit read profile version required')
    if type(config['listen_port']) is not int or not 1024<=config['listen_port']<=65535:
        raise ValueError('invalid explicit Host listen port')
    if not isinstance(config['listen_host'],str) or not config['listen_host']:
        raise ValueError('explicit Host listen address required')
    for name in ('journal_path','operation_policies_path'):
        if not isinstance(config[name],str) or not Path(config[name]).is_absolute():
            raise ValueError('explicit absolute managed path required')
    if policy_registry is None:
        policy_path=Path(config['operation_policies_path'])
        if policy_path.stat().st_size>1048576:
            raise ValueError('policy file exceeds installation budget')
        policies=OperationPolicyRegistry.load(policy_path)
    else:
        # 配对已拥有核SHA的原policy bytes，纯准入沿同一算法，不再打开可变路径。
        if type(policy_registry) is not OperationPolicyRegistry:
            raise ValueError('admitted policy registry required')
        policies=policy_registry
    if bulk:
        from .bulk_bootstrap import bulk_agent_settings, validate_bulk_settings
        from guanheng_qmt_shm_agent.bulk_configuration import validate_bulk_configuration
        probe=validate_bulk_configuration(bulk_agent_settings(config,credentials['ipc_secret']))
        validate_bulk_settings(config['bulk_settings'],probe.profile,max_result_bytes=config['max_result_bytes'])
    elif trading:
        from .trade_bootstrap import trade_agent_settings, validate_trade_storage
        from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
        agent=trade_agent_settings(config,policies,credentials['ipc_secret'])
        probe=validate_trade_configuration(agent)
        validate_trade_storage(config,probe)
    elif preparation:
        from .history_preparation_bootstrap import agent_settings as preparation_settings
        from guanheng_qmt_shm_agent.history_preparation import validate_configuration
        probe=validate_configuration(preparation_settings(config,policies,credentials['ipc_secret']))
    else:
        agent=agent_settings(config,policies,credentials['ipc_secret'])
        # 只校验完整配置；Host不构造Agent，也不声明任何SDK已可用。
        probe=validate_read_configuration(agent)
    for operation in probe.profile['read_operations']:
        if bulk and operation=='market.history_1m.bulk':
            continue
        desc=operation_descriptor(probe.profile,operation,max_result_bytes=config['max_result_bytes'])
        policy=policies.require(desc['policy_id'],operation)
        if policy.execution_timeout_ms!=desc['execution_timeout_ms']:
            raise ValueError('operation execution policy differs')
        probe.control_profile.require_roundtrip(policy.queue_timeout_ms,policy.execution_timeout_ms)
    public=limits(max_frame=config['max_frame'],max_result_bytes=config['max_result_bytes'],
        native_body_limit=probe.control_profile.native_body_limit)
    records,maximum=config['max_records'],config['max_journal_bytes']
    unit=public['max_request_bytes']+config['max_result_bytes']+16384
    if (type(records) is not int or not 1<=records<=1000000 or type(maximum) is not int
            or not unit<=maximum<=records*unit or config['max_result_bytes']>2097152):
        raise ValueError('invalid explicit Journal joint budget')
    return config,policies,public


def _validate_launch_snapshot(config, *, credentials, policy_bytes):
    """配对核心使用已核原字节；不读取文件、不构造Journal或通信owner。"""
    if type(policy_bytes) is not bytes or not 1<=len(policy_bytes)<=1048576:
        raise ValueError('frozen policy byte budget differs')
    value=decode(policy_bytes)
    if (type(value) is not dict or set(value)!={'schema_version','policies'}
            or value['schema_version']!='1.0' or type(value['policies']) is not list):
        raise ValueError('frozen policy fields differ')
    from .contracts import OperationPolicy
    registry=OperationPolicyRegistry([OperationPolicy.model_validate(item) for item in value['policies']])
    return _validate_launch_configuration(config,credentials=credentials,trading=False,
        policy_registry=registry)


def credentials_from_environment(config):
    """CLI只解析所列两项环境引用；错误消息不包含名称、值或原异常。"""
    try:
        return {'ipc_secret':bytes.fromhex(os.environ[config['ipc_secret_env']]),
            'http_keys':{config['http_key_id']:os.environ[config['http_secret_env']]}}
    except (KeyError,ValueError,TypeError):
        raise ValueError('private deployment credential unavailable') from None


def build_runtime(config, *, credentials):
    credentials=_snapshot_credentials(credentials)
    config,policies,public=validate_launch(config,credentials=credentials)
    return _build_read_runtime(config,policies,public,credentials)


def _build_read_runtime(config,policies,public,credentials, *, wait_for_agent=False, failed_owners=None):
    """已准入快照复用原Journal；常驻模式预留单槽持有未确认关闭的构造资源。"""
    if failed_owners is not None and (type(failed_owners) is not list
            or len(failed_owners)!=1 or failed_owners[0] is not None):
        raise ValueError('construction owner requires one empty reserved slot')
    journal_type,runtime_type,journal_extra=BoundReadJournal,HostReadRuntime,{}
    if 'read_retention' in config:
        from .read_retention_journal import RetainedReadJournal, RetainedAccountJournal
        from .read_retention_runtime import RetainedReadRuntime
        from .bulk_clock import WindowsBulkUptimeClock
        journal_type = (RetainedAccountJournal if config.get('read_profile_version') == 'qmt.read-profile.v3'
            else RetainedReadJournal)
        runtime_type=RetainedReadRuntime
        journal_extra={'clock':WindowsBulkUptimeClock()}
    from .journal import construct_journal
    journal=construct_journal(journal_type,Path(config['journal_path']),config['route'],failed_owners=failed_owners,
        max_records=config['max_records'],max_result_bytes=config['max_result_bytes'],
        max_request_bytes=public['max_request_bytes'],max_journal_bytes=config['max_journal_bytes'],
        read_profile=validate_read_configuration(agent_settings(config,policies,credentials['ipc_secret'])).profile,
        **journal_extra)
    if failed_owners is not None:
        # 取得owner后先登记，双异常清理路径无需append或创建额外容器。
        failed_owners[0]=journal
    try:
        runtime=runtime_type(journal,secret=credentials['ipc_secret'],max_frame=config['max_frame'],
            policies=policies,transport=config['transport'],control_profile=config['control_profile'],
            connect_seconds=config['connect_seconds'],io_seconds=config['io_seconds'],
            max_http_inflight=config['max_http_inflight'],read_profile=journal.admission_profile,
            wait_for_agent=wait_for_agent)
        runtime.listen_host,runtime.listen_port=config['listen_host'],config['listen_port']
        if failed_owners is not None:
            failed_owners[0]=None
        return runtime
    except BaseException:
        try:
            journal.close()
        except BaseException:
            if failed_owners is None:
                raise
            # 固定槽继续持有未确认关闭的Journal，bare raise保留Runtime构造首因。
            pass
        else:
            if failed_owners is not None:
                failed_owners[0]=None
        raise


def build_read_service(config, *, credentials, reconnect_seconds):
    """显式只读常驻入口；构造只准入，start才取得通信存储和内核资源。

    凭证、配置和policy在构造时冻结；重连保持同一Journal文件及原请求身份，
    每代复用原Runtime的关闭确认。修改运行配置应重建整个服务。
    """
    credentials=_snapshot_credentials(credentials)
    config,policies,public=validate_launch(config,credentials=credentials)
    return _build_read_service(config,policies,public,credentials,reconnect_seconds=reconnect_seconds)


def _build_read_service(config,policies,public,credentials, *, reconnect_seconds):
    """配对共用的已准入工厂：同一配置/policy快照，构造不再读部署文件。"""
    credentials=_snapshot_credentials(credentials)
    if config['transport']['kind']!='builtin-shm':
        raise ValueError('persistent read service requires explicit builtin SHM')
    configuration_bytes=canonical(config)
    profile=validate_read_configuration(agent_settings(config,policies,credentials['ipc_secret'])).profile
    construction_owners=[None]
    def factory(candidate, *, credentials):
        if canonical(candidate)!=configuration_bytes:
            raise ValueError('read service configuration changed')
        return _build_read_runtime(candidate,policies,public,credentials,wait_for_agent=True,
            failed_owners=construction_owners)
    from .read_service import ReconnectingReadService
    return ReconnectingReadService(factory,configuration=config,credentials=credentials,
        profile=profile,reconnect_seconds=reconnect_seconds,construction_owners=construction_owners)
