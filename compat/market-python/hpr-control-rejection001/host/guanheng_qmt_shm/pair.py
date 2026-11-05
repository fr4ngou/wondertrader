"""离线配对：受保护新目录、固定安装源身份、生成字节最后封存。

生成和核验只处理部署材料，不启动Host、终端或SDK，不打开Journal。
私有凭证只进入受保护材料；返回值只含去敏身份与未授资格事实。
"""
from __future__ import annotations
import hashlib
import ast
import warnings
from pathlib import Path
import sys
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_configuration import validate_read_configuration
from .bootstrap import validate_launch, agent_settings, _snapshot_credentials
from guanheng_qmt_shm_agent.read_capabilities import operation_descriptor, known_operation
from .bound import sha256_text
from .material_integrity import source_manifest
from .private_files import create_private_directory, write_private_new
from .lifecycle import validate_connection_lifecycle


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path, maximum=2097152):
    with Path(path).open('rb') as stream:
        raw=stream.read(maximum+1)
    if len(raw)>maximum:
        raise ValueError('private material exceeds byte budget')
    return raw


_CALLBACKS = '''import threading as _threading
from datetime import datetime as _datetime, timedelta as _timedelta
from {namespace}.restricted import RestrictedReadAgent as _Agent
_agent, _context, _thread = None, None, None

def init(ContextInfo):
    global _agent, _context, _thread
    if _context is not None:
        raise RuntimeError("read entry has one native context generation")
    _context, _thread = ContextInfo, _threading.get_ident()
    # 仅注入固定只读全局函数；显式账户profile由Agent再次准入。
    _agent = _Agent(ContextInfo, trusted_bootstrap=_settings,
        trade_detail_query=globals().get("get_trade_detail_data"))
    try:
        ContextInfo.run_time("agent_tick", "1nSecond",
            (_datetime.now()+_timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"))
        _agent.start()
    except BaseException:
        _agent.request_close()
        raise

def _check(ContextInfo):
    if ContextInfo is not _context or _threading.get_ident() != _thread or _agent is None:
        raise RuntimeError("read entry requires its original strategy context/thread")

def agent_tick(ContextInfo):
    _check(ContextInfo)
    return _agent.tick()

def handlebar(ContextInfo):
    _check(ContextInfo)

def stop(ContextInfo):
    _check(ContextInfo)
    _agent.request_close()
'''


_TRADE_CALLBACKS = '''import threading as _threading
from datetime import datetime as _datetime, timedelta as _timedelta
from {namespace}.trading_agent import RestrictedTradingAgent as _Agent
_agent, _context, _thread = None, None, None

def init(ContextInfo):
    global _agent, _context, _thread
    if _context is not None:
        raise RuntimeError("trade entry has one native context generation")
    _context, _thread = ContextInfo, _threading.get_ident()
    _agent = _Agent(ContextInfo, trusted_bootstrap=_settings,
        trade_detail_query=globals().get("get_trade_detail_data"),
        passorder=globals().get("passorder"), cancel=globals().get("cancel"))
    try:
        # 先发布owner，set_account同步回调也能进入同一源会话。
        _agent.subscribe_account()
        ContextInfo.run_time("agent_tick", "1nSecond",
            (_datetime.now()+_timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"))
        _agent.start()
    except BaseException:
        _agent.request_close()
        raise

def _check_context(ContextInfo):
    if _agent is None:
        raise RuntimeError("trade entry requires its original context generation")
    if ContextInfo is not _context:
        _agent.request_close()
        raise RuntimeError("trade entry requires its original context generation")

def _check(ContextInfo):
    _check_context(ContextInfo)
    if _threading.get_ident() != _thread:
        raise RuntimeError("trade execution requires its original strategy thread")

def agent_tick(ContextInfo):
    _check(ContextInfo)
    return _agent.tick()

def handlebar(ContextInfo):
    _check(ContextInfo)

def order_callback(ContextInfo, orderInfo):
    _check_context(ContextInfo)
    return _agent.on_order(ContextInfo, orderInfo)

def deal_callback(ContextInfo, dealInfo):
    _check_context(ContextInfo)
    return _agent.on_deal(ContextInfo, dealInfo)

def orderError_callback(ContextInfo, orderArgs, errMsg):
    _check_context(ContextInfo)
    return _agent.on_error(ContextInfo, orderArgs, errMsg)

def stop(ContextInfo):
    _check_context(ContextInfo)
    _agent.request_close()
'''


def _render_memory_entry(settings, memory_source, body, injected, callbacks):
    """同一冻结加载格式，只由显式入口选择回调与SDK注入白名单。"""
    if not isinstance(memory_source, str) or not memory_source.isascii():
        raise ValueError('builtin transport requires its frozen ASCII memory runtime')
    bindings = ', '.join('"' + name + '":globals().get("' + name + '")' for name in injected)
    names = '(' + ', '.join('"' + name + '"' for name in callbacks) + ')'
    # 函数创建时继承模块名；受限解释器的原生检查会读取内部函数的模块字段。
    # 在 runtime 和 entry 定义前统一建立身份，保留宿主已有合法脚本名。
    return ('# -*- coding: utf-8 -*-\n'
        + '_memory_entry_name = globals().get("__name__", "__main__")\n'
        + 'if not isinstance(_memory_entry_name, str) or not _memory_entry_name:\n'
        + '    raise RuntimeError("memory entry requires a nonempty module name")\n'
        + 'globals()["__name__"] = _memory_entry_name\n'
        + '_memory_runtime_source = ' + ascii(memory_source)
        + '\nexec(compile(_memory_runtime_source, "<guanheng-memory-runtime>", "exec"), globals())\n'
        + '_settings = ' + ascii(settings) + '\n'
        + '_memory_entry_globals = {"__name__":_memory_entry_name, '
        + '"__builtins__":dict(_memory_original_builtins, '
        + '__import__=_memory_dispatch, open=_memory_forbidden), "_settings":_settings, '
        + bindings + '}\n'
        + 'exec(compile(' + ascii(body) + ', "<guanheng-memory-entry>", "exec"), _memory_entry_globals)\n'
        + 'for _memory_callback in ' + names + ':\n'
        + '    globals()[_memory_callback] = _memory_entry_globals[_memory_callback]\n').encode('ascii')


def render_trade_strategy(settings, *, installed_agent, config_sha256, memory_source):
    """纯生成开发入口；交易启用由正常配置控制，配对运行器仍待接通。"""
    from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
    admitted = validate_trade_configuration(settings)
    if admitted.value['transport']['kind'] != 'builtin-shm':
        raise ValueError('trade strategy requires explicit builtin SHM')
    private = dict(admitted.value, secret=admitted.secret,
                   trade_binding=admitted.trade_binding, writes_enabled=admitted.writes_enabled)
    return _render_memory_entry(private, memory_source,
        _TRADE_CALLBACKS.format(namespace='guanheng_qmt_shm_agent'),
        ('get_trade_detail_data', 'passorder', 'cancel'),
        ('init', 'agent_tick', 'handlebar', 'stop', 'order_callback', 'deal_callback', 'orderError_callback'))


def _resident_callbacks(lifecycle):
    """两个显式入口共用原回调正文，仅选择Agent类型与显式重连参数。"""
    return _CALLBACKS.replace(
        'from {namespace}.restricted import RestrictedReadAgent as _Agent',
        'from {namespace}.reconnecting_read import ReconnectingReadAgent as _Agent').replace(
        'trade_detail_query=globals().get("get_trade_detail_data"))',
        'trade_detail_query=globals().get("get_trade_detail_data"), enabled=True, reconnect_seconds='
        + repr(lifecycle['reconnect_seconds']) + ')')


def render_strategy(settings, *, installed_agent, config_sha256, memory_source=None,
                    connection_lifecycle=None):
    """生成原线程回调；加载方式由显式运输profile决定，回调实现共用。"""
    lifecycle = validate_connection_lifecycle(connection_lifecycle)
    if lifecycle is not None:
        admitted = validate_read_configuration(settings)
        if admitted.value['transport']['kind'] != 'builtin-shm':
            raise ValueError('resident read pairing requires builtin SHM')
    if settings['transport']['kind'] == 'builtin-shm':
        body = (_CALLBACKS if lifecycle is None else _resident_callbacks(lifecycle)).format(
            namespace='guanheng_qmt_shm_agent')
        if settings.get('read_profile_version') in ('qmt.read-profile.v7', 'qmt.read-profile.v8'):
            # 新分析来源显式沿原timer推进运输；默认旧profile正文保持原字节。
            original = ('restricted import RestrictedReadAgent' if lifecycle is None else
                        'reconnecting_read import ReconnectingReadAgent')
            replacement = ('strategy_tick import TickSingleReadAgent' if lifecycle is None else
                           'strategy_tick import TickReadAgent')
            if body.count(original) != 1 or body.count('"1nSecond"') != 1:
                raise ValueError('original read callback template changed')
            from guanheng_qmt_shm_agent.source_runtime import TICK_PERIOD
            body = body.replace(original, replacement).replace('"1nSecond"', repr(TICK_PERIOD))
        return _render_memory_entry(settings, memory_source, body, ('get_trade_detail_data',),
            ('init', 'agent_tick', 'handlebar', 'stop'))
    if memory_source is not None:
        raise ValueError('disk transport cannot carry memory-runtime material')
    namespace = '_guanheng_qmt_read_' + config_sha256
    loader = '''# -*- coding: utf-8 -*-
# Private paired read-only entry. No terminal HTTP or order path is installed.
import importlib.util as _util
import sys as _sys
_name = {namespace!r}
_package = _sys.modules.get(_name)
if _package is None:
    _spec = _util.spec_from_file_location(_name, {init!r}, submodule_search_locations=[{package!r}])
    _package = _util.module_from_spec(_spec)
    _sys.modules[_name] = _package
    try:
        _spec.loader.exec_module(_package)
    except BaseException:
        if _sys.modules.get(_name) is _package:
            del _sys.modules[_name]
        raise
_settings = {settings!r}
'''.format(namespace=namespace, init=str(installed_agent/'__init__.py'),
        package=str(installed_agent), settings=settings)
    return (loader + _CALLBACKS.format(namespace=namespace)).encode('utf-8')


def _validate_pair_settings(config,policies,settings,credentials):
    """生成与v3核验复用同一次Host/Agent/policy身份关系。"""
    agent=validate_read_configuration(settings)
    paired={'route':'route','allowed_operations':'read_operations','max_frame':'max_frame',
        'max_result_bytes':'max_result_bytes','connect_seconds':'connect_seconds','io_seconds':'io_seconds',
        'transport':'transport','control_profile':'control_profile'}
    if any(settings.get(k)!=config.get(v) for k,v in paired.items()):
        raise ValueError('Host and Agent pairing differs')
    expected=validate_read_configuration(agent_settings(config,policies,credentials['ipc_secret']))
    if agent.profile!=expected.profile:
        raise ValueError('paired native profile differs')
    selected={}
    for op in agent.profile['read_operations']:
        desc=operation_descriptor(agent.profile,op,max_result_bytes=config['max_result_bytes'])
        policy=policies.require(desc['policy_id'],op)
        if policy.execution_timeout_ms!=desc['execution_timeout_ms']:
            raise ValueError('paired native policy differs')
        agent.control_profile.require_roundtrip(policy.queue_timeout_ms,policy.execution_timeout_ms)
        selected[op]=policy
    return agent,selected


def _render_launcher(config,credentials,installed,host_package,host_sources,agent_sources,
                     policy_bytes, *, connection_lifecycle=None):
    """唯一launcher模板；None保原字节，v3核验重建完整正文。"""
    integrity=host_package/'material_integrity.py'
    template='''# Private paired Host launcher; installed Python only.
import sys
from pathlib import Path
import importlib.util
import hashlib
if __name__ == "__main__":
    sys.dont_write_bytecode = True
    integrity_path = Path({integrity!r})
    if hashlib.sha256(integrity_path.read_bytes()).hexdigest() != {integrity_sha!r}:
        raise RuntimeError("paired integrity source changed")
    spec = importlib.util.spec_from_file_location("_paired_integrity", str(integrity_path))
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    if audit.source_manifest(Path({host!r})) != {host_sources!r}:
        raise RuntimeError("paired Host sources changed")
    if audit.source_manifest(Path({agent!r})) != {agent_sources!r}:
        raise RuntimeError("paired Agent sources changed")
    if hashlib.sha256(Path({policy_path!r}).read_bytes()).hexdigest() != {policy_sha!r}:
        raise RuntimeError("paired policy changed")
    from guanheng_qmt_shm.bootstrap import build_runtime
    from guanheng_qmt_shm.server import run_server
    import guanheng_qmt_shm
    if Path(guanheng_qmt_shm.__file__).resolve().parent != Path({host!r}):
        raise RuntimeError("paired Host import origin changed")
    credentials = {credentials!r}
    runtime = build_runtime({config!r}, credentials=credentials)
    run_server(runtime, http_keys=credentials["http_keys"])
'''
    if connection_lifecycle is not None:
        template=template.replace('from guanheng_qmt_shm.bootstrap import build_runtime',
            'from guanheng_qmt_shm.bootstrap import build_read_service').replace(
            'runtime = build_runtime(', 'runtime = build_read_service(').replace(
            ', credentials=credentials)\n',
            ', credentials=credentials, reconnect_seconds={reconnect_seconds!r})\n')
    launcher=template.format(integrity=str(integrity),integrity_sha=_hash(integrity.read_bytes()),host=str(host_package),
        host_sources=host_sources,agent=str(installed),agent_sources=agent_sources,
        policy_path=config['operation_policies_path'],policy_sha=_hash(policy_bytes),credentials=credentials,config=config,
        reconnect_seconds=(connection_lifecycle['reconnect_seconds'] if connection_lifecycle is not None else None)).encode('utf-8')
    return launcher


def _configuration_sha(config,settings,lifecycle):
    value={'host':config,'agent':{k:v for k,v in settings.items() if k!='secret'}}
    if lifecycle is not None:
        value['connection_lifecycle']=lifecycle
    return _hash(canonical(value))


def _prepare_pair_runtime(installed, sdk_metadata, stdlib_license, lifecycle, config):
    """生成与verify共用同一来源闭包选择；分析连接带入原timer驱动实现。"""
    from .memory_runtime import prepare_runtime, prepare_read_service_runtime, _prepare_runtime
    if config.get('read_profile_version') in ('qmt.read-profile.v7', 'qmt.read-profile.v8'):
        return _prepare_runtime(installed, sdk_metadata, stdlib_license,
                                ('guanheng_qmt_shm_agent.strategy_tick',))
    prepare = prepare_runtime if lifecycle is None else prepare_read_service_runtime
    return prepare(installed, sdk_metadata, stdlib_license)


def create_pair(config, agent_config, *, installed_agent, credentials, output,
                sdk_metadata=None, stdlib_license=None, connection_lifecycle=None):
    lifecycle=validate_connection_lifecycle(connection_lifecycle)
    credentials=_snapshot_credentials(credentials)
    config,policies,unused_limits=validate_launch(config,credentials=credentials)
    if not isinstance(agent_config,dict) or set(agent_config)!={'agent'}:
        raise ValueError('pair requires read-only Agent configuration')
    settings=decode(canonical(agent_config['agent']))
    if 'secret' in settings or settings.pop('secret_env',None)!=config['ipc_secret_env']:
        raise ValueError('pair requires the same trusted credential role')
    settings['secret']=credentials['ipc_secret']
    if lifecycle is not None and config['transport']['kind'] != 'builtin-shm':
        raise ValueError('resident read pairing requires builtin SHM')
    agent,selected=_validate_pair_settings(config,policies,settings,credentials)
    installed=Path(installed_agent)
    agent_sources=source_manifest(installed)
    host_package=Path(__file__).resolve().parent
    host_sources=source_manifest(host_package)
    policy_bytes=_read(config['operation_policies_path'],1048576)
    # Freeze the exact policy bytes consumed by launch, independently from the
    # source path. Revalidate a changed policy before any pair can qualify.
    frozen=decode(policy_bytes)
    from .contracts import OperationPolicy
    from .policy import OperationPolicyRegistry
    if not isinstance(frozen,dict) or set(frozen)!={'schema_version','policies'} or frozen['schema_version']!='1.0':
        raise ValueError('invalid frozen policy')
    frozen_policies=OperationPolicyRegistry([OperationPolicy.model_validate(p) for p in frozen['policies']])
    for op,policy in selected.items():
        if frozen_policies.require(policy.policy_id,op)!=policy:
            raise ValueError('policy changed during pairing')
    memory_source, memory_identity = None, None
    if config['transport']['kind'] == 'builtin-shm':
        memory_source, memory_identity = _prepare_pair_runtime(installed, sdk_metadata, stdlib_license, lifecycle, config)
    elif sdk_metadata is not None or stdlib_license is not None:
        raise ValueError('memory SDK material requires explicit builtin transport')
    target=create_private_directory(output)
    config['operation_policies_path']=str(target/'policy.json')
    config_sha=_configuration_sha(config,settings,lifecycle)
    strategy=render_strategy(settings,installed_agent=installed,config_sha256=config_sha,
        memory_source=memory_source,connection_lifecycle=lifecycle)
    launcher=_render_launcher(config,credentials,installed,host_package,host_sources,agent_sources,
        policy_bytes,connection_lifecycle=lifecycle)
    manifest={'schema_version':'qmt.shm-pair.v1','config_sha256':config_sha,
        'host_python':sys.executable,'host_package':str(host_package),'host_sources':host_sources,
        'agent_package':str(installed),'agent_sources':agent_sources,'qualified_in_qmt':False,
        'capabilities':agent.profile['read_operations'],'order_ready':False,
        'files':{'host.py':_hash(launcher),'strategy.py':_hash(strategy),'policy.json':_hash(policy_bytes)}}
    if memory_identity is not None:
        manifest['schema_version'] = 'qmt.shm-pair.v2'
        manifest['memory_runtime'] = memory_identity
        manifest['files']['CPYTHON-LICENSE.txt'] = _hash(stdlib_license)
    if lifecycle is not None:
        manifest['schema_version'] = 'qmt.shm-pair.v3'
        manifest['connection_lifecycle'] = lifecycle
    # All bytes are preflighted before writing; manifest is the final receipt.
    values=[('policy.json',policy_bytes),('host.py',launcher),('strategy.py',strategy)]
    if memory_identity is not None:
        values.append(('CPYTHON-LICENSE.txt', stdlib_license))
    values.append(('manifest.json', canonical(manifest)))
    if any(not 1<=len(raw)<=2097152 for name,raw in values):
        raise ValueError('paired material exceeds file budget')
    for name,raw in values:
        write_private_new(target/name,raw)
    return {'paired':True,'qualified_in_qmt':False,'config_sha256':config_sha,'order_ready':False}


def _material_ast(raw):
    # 私有正文只在内存解析；SyntaxWarning不能把源码行写入stderr。
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree=ast.parse(raw.decode('utf-8'))
    pending=[(tree,0)]; count=0
    while pending:
        node,depth=pending.pop(); count+=1
        if count>32768 or depth>64:
            raise ValueError('paired material AST exceeds budget')
        pending.extend((child,depth+1) for child in ast.iter_child_nodes(node))
    return tree


def _host_literals(raw):
    """只取生成器的两个唯一字面量；完整结构由重渲染后的字节比较负责。"""
    tree=_material_ast(raw)
    found={name:[] for name in ('credentials','runtime')}
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in found:
                    found[target.id].append(node.value)
    if any(len(values)!=1 for values in found.values()):
        raise ValueError('paired Host literal owners differ')
    call=found['runtime'][0]
    if (not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name)
            or call.func.id!='build_read_service' or len(call.args)!=1):
        raise ValueError('paired Host service entry differs')
    return ast.literal_eval(call.args[0]),_snapshot_credentials(ast.literal_eval(found['credentials'][0]))


def _verify_single_callbacks(raw,config_sha):
    """v1保持原磁盘loader；核原回调tail，禁止常驻Agent混进旧版本。"""
    tree=_material_ast(raw)
    expected=ast.parse(_CALLBACKS.format(namespace='_guanheng_qmt_read_'+config_sha))
    names={'init','_check','agent_tick','handlebar','stop'}
    definitions=[node.name for node in ast.walk(tree)
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names]
    if (sorted(definitions)!=sorted(names) or len(tree.body)<len(expected.body)
            or any(ast.dump(a,include_attributes=False)!=ast.dump(b,include_attributes=False)
                for a,b in zip(tree.body[-len(expected.body):],expected.body))
            or any(isinstance(node,ast.ImportFrom) and node.module
                and 'reconnecting_read' in node.module.split('.') for node in ast.walk(tree))
            or any(isinstance(node,ast.Import) and any(
                'reconnecting_read' in alias.name.split('.') for alias in node.names)
                for node in ast.walk(tree))):
        raise ValueError('paired single-generation callbacks differ')


def _verify_resident_host(value,directory,installed,settings,materials,lifecycle):
    """v3同时绑定Host/Agent/lifecycle；只读源码和policy，不打开Journal。"""
    try:
        config,credentials=_host_literals(materials['host.py'])
        if (type(config) is not dict
                or config.get('operation_policies_path')!=str(directory.resolve()/'policy.json')
                or settings.get('secret')!=credentials['ipc_secret']):
            raise ValueError('paired Host input identity differs')
        from .bootstrap import _validate_launch_snapshot
        config,policies,public=_validate_launch_snapshot(config,credentials=credentials,
            policy_bytes=materials['policy.json'])
        if config['transport']['kind']!='builtin-shm':
            raise ValueError('resident read pairing requires builtin SHM')
        _validate_pair_settings(config,policies,settings,credentials)
        if _configuration_sha(config,settings,lifecycle)!=value['config_sha256']:
            raise ValueError('paired lifecycle configuration differs')
        expected=_render_launcher(config,credentials,installed,Path(value['host_package']),
            value['host_sources'],value['agent_sources'],materials['policy.json'],
            connection_lifecycle=lifecycle)
        if expected!=materials['host.py']:
            raise ValueError('paired Host source differs')
        return config,credentials,policies,public,lifecycle
    except (ValueError,SyntaxError,UnicodeError,RecursionError,MemoryError,TypeError,KeyError):
        raise ValueError('paired resident Host identity differs') from None


def _verify_pair_material(directory, *, installed_agent):
    directory=Path(directory)
    manifest_bytes=_read(directory/'manifest.json')
    value=decode(manifest_bytes)
    fields={'schema_version','config_sha256','host_python','host_package','host_sources','agent_package',
        'agent_sources','qualified_in_qmt','capabilities','order_ready','files'}
    resident = isinstance(value, dict) and value.get('schema_version') == 'qmt.shm-pair.v3'
    memory = isinstance(value, dict) and value.get('schema_version') in ('qmt.shm-pair.v2','qmt.shm-pair.v3')
    if resident:
        fields.add('connection_lifecycle')
    if memory:
        fields.add('memory_runtime')
    if (not isinstance(value,dict) or set(value)!=fields or value['schema_version'] not in ('qmt.shm-pair.v1', 'qmt.shm-pair.v2', 'qmt.shm-pair.v3')
            or value['qualified_in_qmt'] is not False or value['order_ready'] is not False
            or type(value['capabilities']) is not list or not 1<=len(value['capabilities'])<=3
            or any(not known_operation(op) for op in value['capabilities'])
            or value['capabilities']!=sorted(set(value['capabilities'])) or value['agent_package']!=str(Path(installed_agent))
            or set(value['files'])!=({'host.py','strategy.py','policy.json','CPYTHON-LICENSE.txt'}
                                    if memory else {'host.py','strategy.py','policy.json'})):
        raise ValueError('paired manifest identity differs')
    lifecycle=validate_connection_lifecycle(value['connection_lifecycle']) if resident else None
    if resident and lifecycle is None:
        raise ValueError('resident pairing requires explicit lifecycle')
    sha256_text(value['config_sha256'])
    if (value['host_python']!=sys.executable
            or Path(value['host_package']).resolve()!=Path(__file__).resolve().parent):
        raise ValueError('paired Host installation origin differs')
    materials={}
    for name,expected in value['files'].items():
        materials[name]=_read(directory/name)
        if _hash(materials[name])!=expected:
            raise ValueError('paired material changed')
    if (source_manifest(Path(value['host_package']))!=value['host_sources']
            or source_manifest(Path(installed_agent))!=value['agent_sources']):
        raise ValueError('paired installed sources changed')
    # 能力清单须来自已核字节的生成入口；只解析单个字面量，绝不执行策略。
    try:
        entries=[line[len('_settings = '):] for line in materials['strategy.py'].decode('utf-8').splitlines()
                 if line.startswith('_settings = ')]
        if len(entries)!=1:
            raise ValueError('missing paired bootstrap')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            settings=ast.literal_eval(entries[0])
        paired=validate_read_configuration(settings)
        if value['capabilities']!=paired.profile['read_operations']:
            raise ValueError('paired capability differs')
    except (ValueError,SyntaxError,UnicodeError,RecursionError,MemoryError,TypeError,KeyError):
        raise ValueError('paired bootstrap or capability differs') from None
    if memory:
        identity = value['memory_runtime']
        if type(identity) is not dict or 'sdk' not in identity:
            raise ValueError('paired memory-runtime identity differs')
        runtime_source, current = _prepare_pair_runtime(Path(installed_agent), identity['sdk'],
            materials['CPYTHON-LICENSE.txt'], lifecycle, settings)
        expected = render_strategy(settings, installed_agent=Path(installed_agent),
            config_sha256=value['config_sha256'], memory_source=runtime_source,
            connection_lifecycle=lifecycle)
        if current != identity or expected != materials['strategy.py']:
            raise ValueError('paired memory-runtime source closure changed')
    elif settings['transport']['kind'] != 'shm':
        raise ValueError('paired disk transport identity differs')
    else:
        try:
            _verify_single_callbacks(materials['strategy.py'],value['config_sha256'])
        except (ValueError,SyntaxError,UnicodeError,RecursionError,MemoryError,TypeError,KeyError):
            raise ValueError('paired single-generation callbacks differ') from None
    private=None
    if resident:
        private=_verify_resident_host(value,directory,Path(installed_agent),settings,materials,lifecycle)
    return ({'paired':True,'qualified_in_qmt':False,'config_sha256':value['config_sha256'],'order_ready':False},
        private, {'pair_manifest_sha256':_hash(manifest_bytes),
                  'pair_config_sha256':value['config_sha256']})


def verify_pair(directory, *, installed_agent):
    """离线核验只返回安全身份；不构造服务、不打开Journal。"""
    public,unused_private,unused_identity=_verify_pair_material(directory,installed_agent=installed_agent)
    return public


def build_paired_runtime(directory, *, installed_agent):
    """v3唯一启动准入：直接消费同次核验的私有快照，不执行或重读host.py。

    返回(runtime,http_keys,identity)；前两项仅交受管调用者，禁止序列化。
    identity仅含同次已验证manifest/config摘要。常驻服务构造只准入；
    start才取得Journal/SHM。旧v1/v2继续使用既有显式入口。
    """
    unused_public,private,identity=_verify_pair_material(directory,installed_agent=installed_agent)
    if private is None:
        raise ValueError('paired resident runtime requires qmt.shm-pair.v3')
    config,credentials,policies,public,lifecycle=private
    from .bootstrap import _build_read_service
    runtime=_build_read_service(config,policies,public,credentials,
        reconnect_seconds=lifecycle['reconnect_seconds'])
    return runtime,dict(credentials['http_keys']),identity
