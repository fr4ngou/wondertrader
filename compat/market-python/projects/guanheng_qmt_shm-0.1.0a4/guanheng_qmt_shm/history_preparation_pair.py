"""显式补齐开发配对；只生成私有材料，终端安装和真实运行由操作owner负责。"""
from pathlib import Path
import sys
from guanheng_qmt_shm_agent.history_preparation import validate_configuration
from guanheng_qmt_shm_agent.protocol import canonical, decode
from .bootstrap import _snapshot_credentials
from .history_preparation_bootstrap import agent_settings, validate_launch
from .contracts import OperationPolicy
from .lifecycle import validate_connection_lifecycle
from .material_integrity import source_manifest
from .memory_runtime import _prepare_runtime
from .pair import (_hash, _read, _configuration_sha, _resident_callbacks,
                   _render_memory_entry, _render_launcher)
from .policy import OperationPolicyRegistry
from .private_files import create_private_directory, write_private_new


def render_strategy(settings, memory_source, reconnect_seconds):
    """固定全局函数白名单，沿原回调模板及原内存加载器装配。"""
    validate_configuration(settings)
    lifecycle = validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
        mode='resident-read', reconnect_seconds=reconnect_seconds))
    body = _resident_callbacks(lifecycle)
    original = 'from {namespace}.reconnecting_read import ReconnectingReadAgent as _Agent'
    injection = 'trade_detail_query=globals().get("get_trade_detail_data"), enabled=True'
    if body.count(original) != 1 or body.count(injection) != 1:
        raise ValueError('original resident callbacks changed')
    body = body.replace(original, 'from {namespace}.history_preparation_agent import ReconnectingHistoryPreparationAgent as _Agent')
    body = body.replace(injection, 'download_history_data=globals().get("download_history_data"), ' + injection)
    return _render_memory_entry(settings, memory_source, body.format(namespace='guanheng_qmt_shm_agent'),
        ('get_trade_detail_data', 'download_history_data'), ('init', 'agent_tick', 'handlebar', 'stop'))


def create_pair(config, *, agent_root, credentials, output, sdk_metadata, stdlib_license, reconnect_seconds):
    credentials = _snapshot_credentials(credentials)
    config = decode(canonical(config))
    policy_bytes = _read(config['operation_policies_path'], 1048576)
    material = decode(policy_bytes)
    if type(material) is not dict or set(material) != {'schema_version', 'policies'} or material['schema_version'] != '1.0':
        raise ValueError('invalid original policy material')
    policies = OperationPolicyRegistry([OperationPolicy.model_validate(item) for item in material['policies']])
    config, unused_policies, unused_limits = validate_launch(config, credentials=credentials, policy_registry=policies)
    settings = agent_settings(config, policies, credentials['ipc_secret'])
    admitted = validate_configuration(settings)
    lifecycle = validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
        mode='resident-read', reconnect_seconds=reconnect_seconds))
    agent, host = Path(agent_root).resolve(strict=True), Path(__file__).resolve().parent
    agent_sources, host_sources = source_manifest(agent), source_manifest(host)
    memory_source, memory_identity = _prepare_runtime(agent, sdk_metadata, stdlib_license,
        ('guanheng_qmt_shm_agent.history_preparation_agent',))
    strategy = render_strategy(settings, memory_source, reconnect_seconds)
    target = Path(output)
    if not target.is_absolute():
        raise ValueError('new absolute private pair directory required')
    target = target.parent.resolve(strict=True) / target.name
    config['operation_policies_path'] = str(target / 'policy.json')
    config_sha = _configuration_sha(config, settings, lifecycle)
    launcher = _render_launcher(config, credentials, agent, host, host_sources, agent_sources,
        policy_bytes, connection_lifecycle=lifecycle).decode('utf8')
    original = '    from guanheng_qmt_shm.bootstrap import build_read_service\n'
    if launcher.count(original) != 1:
        raise ValueError('original Host launcher changed')
    launcher = launcher.replace(original,
        '    sys.path.insert(0, ' + repr(str(agent.parent)) + ')\n'
        '    sys.path.insert(0, ' + repr(str(host.parent)) + ')\n'
        '    from guanheng_qmt_shm.history_preparation_bootstrap import build_read_service\n').encode('utf8')
    if source_manifest(agent) != agent_sources or source_manifest(host) != host_sources:
        raise ValueError('preparation pairing source changed during generation')
    files = {'host.py': _hash(launcher), 'strategy.py': _hash(strategy), 'policy.json': _hash(policy_bytes),
        'CPYTHON-LICENSE.txt': _hash(stdlib_license)}
    manifest = dict(schema_version='qmt.history-preparation-pair.v1', source_mode='repository',
        strategy_name='GH_WT_MEMORY_VERIFY', config_sha256=config_sha, host_python=sys.executable,
        host_package=str(host), host_sources=host_sources, agent_package=str(agent), agent_sources=agent_sources,
        memory_runtime=memory_identity, connection_lifecycle=lifecycle, files=files,
        capabilities=admitted.profile['read_operations'], qualified_in_qmt=False, order_ready=False)
    materials = [('policy.json', policy_bytes), ('host.py', launcher), ('strategy.py', strategy),
        ('CPYTHON-LICENSE.txt', stdlib_license), ('manifest.json', canonical(manifest))]
    if any(not 1 <= len(raw) <= 2097152 for unused, raw in materials):
        raise ValueError('preparation pair exceeds original file budget')
    created = create_private_directory(target)
    for name, raw in materials:
        write_private_new(created / name, raw)
    return dict(paired=True, development_only=True, qualified_in_qmt=False, order_ready=False,
        config_sha256=config_sha, strategy_name='GH_WT_MEMORY_VERIFY', files=files,
        capabilities=admitted.profile['read_operations'])
