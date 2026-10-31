"""交易产品的离线配对材料；交易规则继续由既有准入实现决定。"""
import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
import math
import os
from pathlib import Path
import stat
import sys
import time

import guanheng_qmt_shm_agent
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
from .bootstrap import _snapshot_credentials, _validate_launch_configuration
from .contracts import OperationPolicy
from .material_integrity import source_manifest
from .trade_source import render_trade_source
from .policy import OperationPolicyRegistry
from .private_files import create_private_directory, write_private_new
from .trade_bootstrap import trade_agent_settings
from .trade_event_records import CONTINUITY_VERSION
from .account_read_composition import account_read_material, admit_account_read
from .analysis_read_composition import analysis_read_material, admit_analysis_read
from .analysis_batch_read_composition import analysis_batch_read_material, admit_analysis_batch_read

SCHEMA = 'qmt.trade-product-pair.v1'
SOURCE_SCHEMA = 'qmt.trade-product-pair.v2'
ANALYSIS_SCHEMA = 'qmt.trade-product-pair.v3'
BATCH_ANALYSIS_SCHEMA = 'qmt.trade-product-pair.v4'
from guanheng_qmt_shm_agent.source_runtime import source_runtime as admit_source_runtime
FILES = frozenset(('host.py', 'strategy.py', 'deployment.json', 'policy.json', 'CPYTHON-LICENSE.txt'))
FIELDS = frozenset(('schema_version', 'config_sha256', 'host_python', 'host_python_sha256',
    'host_package', 'host_sources', 'agent_package', 'agent_sources', 'memory_runtime', 'files',
    'qualified_in_qmt', 'order_ready', 'capabilities', 'strategy_name'))

_MATERIAL_DEADLINE = ContextVar('trade_product_material_deadline', default=None)


def _check_material_deadline():
    deadline = _MATERIAL_DEADLINE.get()
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('original product material deadline elapsed')


@contextmanager
def material_deadline(deadline):
    """同一调用上下文的物理读取预算；嵌套只收紧，退出恢复调用方上下文。"""
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError('material verification requires an absolute monotonic deadline')
    original = _MATERIAL_DEADLINE.get()
    token = _MATERIAL_DEADLINE.set(deadline if original is None else min(original, deadline))
    try:
        _check_material_deadline()
        yield
        _check_material_deadline()
    finally:
        _MATERIAL_DEADLINE.reset(token)


def _need(value):
    if not value:
        raise ValueError('trade product identity differs')


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _inspect(path, directory=False):
    _need(path.is_absolute() and '..' not in path.parts)
    for item in reversed((path, *path.parents)):
        _check_material_deadline()
        info = item.lstat()
        _check_material_deadline()
        _need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400)
        if item != path:
            _need(stat.S_ISDIR(info.st_mode))
    _need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    return info


def _read(path, maximum=2097152):
    """只解释同一普通文件的完整字节；生成脚本不在材料核验期间执行。"""
    path = Path(path)
    before = _inspect(path)
    _need(0 < before.st_size <= maximum)
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    _check_material_deadline()
    with path.open('rb') as stream:
        _check_material_deadline()
        opened = os.fstat(stream.fileno())
        _check_material_deadline()
        _need(identity(opened) == identity(before))
        raw = stream.read(maximum + 1)
        _check_material_deadline()
        final = os.fstat(stream.fileno())
        _check_material_deadline()
        _need(identity(final) == identity(opened))
    _check_material_deadline()
    _need(identity(_inspect(path)) == identity(opened) and len(raw) == opened.st_size)
    return raw


def _sources(package):
    _inspect(package, True)
    if _MATERIAL_DEADLINE.get() is not None:
        return source_manifest(package, reader=_read, check_deadline=_check_material_deadline)
    return source_manifest(package, reader=_read)


def _directory_names(directory):
    if _MATERIAL_DEADLINE.get() is None:
        return {path.name for path in directory.iterdir()}
    names, paths = set(), iter(directory.iterdir())
    while True:
        _check_material_deadline()
        try:
            path = next(paths)
        except StopIteration:
            _check_material_deadline()
            return names
        _check_material_deadline()
        names.add(path.name)


def _installation(installed_agent=None):
    _check_material_deadline()
    agent = Path(guanheng_qmt_shm_agent.__file__).resolve().parent
    _check_material_deadline()
    if installed_agent is not None:
        _need(Path(installed_agent) == agent)
    return agent, Path(__file__).resolve().parent, Path(sys.executable).parent / 'pythonw.exe'


def _lifecycle(seconds):
    _need(type(seconds) in (int, float) and .1 <= seconds <= 60)
    return dict(schema_version='qmt.trade-resident.v1', reconnect_seconds=float(seconds))


def _policies(raw):
    value = decode(raw)
    _need(type(value) is dict and set(value) == {'schema_version', 'policies'}
          and value['schema_version'] == '1.0' and type(value['policies']) is list)
    policies = [OperationPolicy.model_validate(item) for item in value['policies']]
    _need(all(canonical(policy.model_dump(mode='json')) == canonical(item)
        for policy, item in zip(policies, value['policies'])))
    return OperationPolicyRegistry(policies)


def _snapshot(config, credentials, policy_raw, reconnect_seconds):
    credentials = _snapshot_credentials(credentials)
    config, policies, public = _validate_launch_configuration(config,
        credentials=credentials, trading=True, policy_registry=_policies(policy_raw))
    settings = trade_agent_settings(config, policies, credentials['ipc_secret'])
    admitted = validate_trade_configuration(settings)
    _need(config['transport']['kind'] == 'builtin-shm'
        and {'event_storage', 'event_poll_seconds'} <= set(config))
    return config, credentials, settings, policies, public, admitted, _lifecycle(reconnect_seconds)


def _market_material(market, *, decode_secrets=False):
    """私有JSON用明确hex保存两条原IPC秘密；运行快照仍传原bytes准入。"""
    _need(type(market) is dict and set(market) ==
        {'quotes', 'preparation', 'preparation_reconnect_seconds'})
    value = dict(preparation_reconnect_seconds=market['preparation_reconnect_seconds'])
    for role in ('quotes', 'preparation'):
        item = dict(market[role])
        incoming, outgoing = ('secret_hex', 'secret') if decode_secrets else ('secret', 'secret_hex')
        _need(incoming in item and outgoing not in item)
        secret = item.pop(incoming)
        if decode_secrets:
            _need(type(secret) is str and 64 <= len(secret) <= 8192 and len(secret) % 2 == 0
                and all(char in '0123456789abcdef' for char in secret))
            converted = bytes.fromhex(secret)
        else:
            _need(type(secret) is bytes and 32 <= len(secret) <= 4096)
            converted = secret.hex()
        item = decode(canonical(item))
        item[outgoing] = converted
        value[role] = item
    return value


def _deployment(config, credentials, reconnect_seconds, market=None, account_read=None, source_runtime=None, analysis_read=None, analysis_batch_read=None):
    value = dict(schema_version='qmt.trade-deployment.v1', host=config,
        credentials=dict(ipc_secret_hex=credentials['ipc_secret'].hex(), http_keys=credentials['http_keys']),
        reconnect_seconds=reconnect_seconds, connection_continuity=CONTINUITY_VERSION)
    # 组合仅由外部配对显式加入；旧产品的私有部署字段和正文保持原形状。
    if market is not None:
        value['market'] = _market_material(market)
    if account_read is not None:
        value['account_read'] = account_read_material(account_read)
    if source_runtime is not None:
        value['source_runtime'] = admit_source_runtime(source_runtime)
        value['schema_version'] = 'qmt.trade-deployment.v2'
    if analysis_read is not None:
        value['analysis_read'] = analysis_read_material(analysis_read)
        value['schema_version'] = 'qmt.trade-deployment.v3'
    if analysis_batch_read is not None:
        value['analysis_batch_read'] = analysis_batch_read_material(analysis_batch_read)
        value['schema_version'] = 'qmt.trade-deployment.v4'
    return value


def _market_credentials(market, credentials):
    """QMT持有的两种市场IPC身份继续与外部Host的HTTP身份分开。"""
    if market is not None:
        http_secrets = {value.encode('utf8') for value in credentials['http_keys'].values()}
        _need(all(market[role]['secret'] not in http_secrets for role in ('quotes', 'preparation')))


def _account_credentials(account_read, credentials):
    """原只读IPC身份只进入正文，继续与外部HTTP签名身份隔离。"""
    if account_read is not None:
        _need(account_read['agent']['secret'] not in
            {value.encode('utf8') for value in credentials['http_keys'].values()})


def _account_identity(account_read):
    unused_value, profile = admit_account_read(account_read)
    return dict(profile=profile, settings_sha256=_hash(canonical(account_read_material(account_read))))


def _decode_all_deployment(raw):
    """唯一完整解析器显式消费六连接，旧元组接口在外层拒绝新增设置。"""
    value = decode(raw)
    fields = {'schema_version', 'host', 'credentials', 'reconnect_seconds', 'connection_continuity'}
    _need(type(value) is dict and fields <= set(value) <= fields | {'market', 'account_read', 'source_runtime', 'analysis_read', 'analysis_batch_read'}
        and value['schema_version'] == ('qmt.trade-deployment.v4' if 'analysis_batch_read' in value else
            'qmt.trade-deployment.v3' if 'analysis_read' in value else
            'qmt.trade-deployment.v2' if 'source_runtime' in value else 'qmt.trade-deployment.v1')
        and value['connection_continuity'] == CONTINUITY_VERSION)
    _need('market' not in value or type(value['market']) is dict)
    credentials = value['credentials']
    _need(type(credentials) is dict and set(credentials) == {'ipc_secret_hex', 'http_keys'})
    text = credentials['ipc_secret_hex']
    _need(type(text) is str and 64 <= len(text) <= 8192 and len(text) % 2 == 0
        and all(char in '0123456789abcdef' for char in text))
    return (value['host'], dict(ipc_secret=bytes.fromhex(text), http_keys=credentials['http_keys']),
        value['reconnect_seconds'], None if 'market' not in value else
        _market_material(value['market'], decode_secrets=True),
        None if 'account_read' not in value else account_read_material(value['account_read'], decode_secrets=True),
        None if 'source_runtime' not in value else admit_source_runtime(value['source_runtime']),
        None if 'analysis_read' not in value else analysis_read_material(value['analysis_read'], decode_secrets=True),
        None if 'analysis_batch_read' not in value else analysis_batch_read_material(value['analysis_batch_read'], decode_secrets=True))


def _decode_complete_deployment(raw):
    """原 v3 七项调用者继续原形状；v4 必须显式消费完整批量连接。"""
    value = _decode_all_deployment(raw)
    _need(value[7] is None)
    return value[:7]


def _decode_source_deployment(raw):
    """原六元组调用者拒绝新增分析项；完整准入保持单一实现。"""
    value = _decode_complete_deployment(raw)
    _need(value[6] is None)
    return value[:6]


def _decode_composed_deployment(raw):
    value = _decode_source_deployment(raw)
    _need(value[5] is None)
    return value[:5]


def _decode_deployment(raw):
    """旧调用者保持四元组；新连接须由完整decoder显式消费，避免静默遗漏。"""
    value = _decode_composed_deployment(raw)
    _need(value[4] is None)
    return value[:4]


def _launcher(agent):
    return ("from pathlib import Path\nfrom guanheng_qmt_shm.trade_cli import main\n"
        "if __name__ == '__main__':\n    raise SystemExit(main(['run', '--directory', "
        "str(Path(__file__).resolve().parent), '--installed-agent', " + repr(str(agent)) + "]))\n").encode('utf8')


def _freeze(agent, metadata, license_bytes, settings, reconnect_seconds, market=None, account_read=None, source_runtime=None, analysis_read=None, analysis_batch_read=None):
    """完整依赖闭包和原正文生成器共用一次输入快照，终端运行仅加载内存。"""
    return render_trade_source(settings, agent_root=agent, sdk_metadata=metadata,
        stdlib_license=license_bytes, reconnect_seconds=reconnect_seconds, market=market,
        account_read=account_read, analysis_read=analysis_read, analysis_batch_read=analysis_batch_read,
        source_runtime=source_runtime, reader=_read)


def create_product_pair(config, *, credentials, output, sdk_metadata, stdlib_license,
                        reconnect_seconds, installed_agent=None, market=None, account_read=None, source_runtime=None, analysis_read=None, analysis_batch_read=None):
    """只生成新私有材料；不创建Journal、SHM、HTTP或QMT SDK owner。"""
    agent, host, pythonw = _installation(installed_agent)
    agent_sources, host_sources = _sources(agent), _sources(host)
    policy_raw = _read(Path(config['operation_policies_path']), 1048576)
    target = Path(output)
    _need(target.is_absolute() and target.drive.upper() == 'E:' and not target.exists())
    _inspect(target.parent, True)
    config = decode(canonical(config))
    config['operation_policies_path'] = str(target / 'policy.json')
    config, credentials, settings, unused_p, unused_public, unused_a, lifecycle = _snapshot(
        config, credentials, policy_raw, reconnect_seconds)
    market = None if market is None else _market_material(_market_material(market), decode_secrets=True)
    _market_credentials(market, credentials)
    account_read = None if account_read is None else account_read_material(account_read_material(account_read), decode_secrets=True)
    _account_credentials(account_read, credentials)
    analysis_read = None if analysis_read is None else analysis_read_material(analysis_read_material(analysis_read), decode_secrets=True)
    _account_credentials(analysis_read, credentials)
    analysis_batch_read = None if analysis_batch_read is None else analysis_batch_read_material(
        analysis_batch_read_material(analysis_batch_read), decode_secrets=True)
    _account_credentials(analysis_batch_read, credentials)
    source_runtime = admit_source_runtime(source_runtime)
    strategy, memory = _freeze(agent, sdk_metadata, stdlib_license, settings, lifecycle['reconnect_seconds'], market, account_read, source_runtime, analysis_read, analysis_batch_read)
    deployment = canonical(_deployment(config, credentials, lifecycle['reconnect_seconds'], market, account_read, source_runtime, analysis_read, analysis_batch_read))
    materials = {'deployment.json': deployment, 'policy.json': policy_raw, 'strategy.py': strategy,
        'host.py': _launcher(agent), 'CPYTHON-LICENSE.txt': stdlib_license}
    manifest = dict(schema_version=BATCH_ANALYSIS_SCHEMA if analysis_batch_read is not None else ANALYSIS_SCHEMA if analysis_read is not None else SCHEMA if source_runtime is None else SOURCE_SCHEMA, config_sha256=_hash(deployment), host_python=str(pythonw),
        host_python_sha256=_hash(_read(pythonw, 67108864)), host_package=str(host), host_sources=host_sources,
        agent_package=str(agent), agent_sources=agent_sources, memory_runtime=memory,
        files={name: _hash(raw) for name, raw in materials.items()}, qualified_in_qmt=False,
        order_ready=False, capabilities=settings['allowed_operations'], strategy_name='GH_WT_MEMORY_VERIFY')
    if account_read is not None:
        manifest['account_read'] = _account_identity(account_read)
    if analysis_read is not None:
        unused_settings, profile = admit_analysis_read(analysis_read)
        manifest['analysis_read'] = dict(profile=profile, settings_sha256=_hash(canonical(analysis_read_material(analysis_read))))
    if analysis_batch_read is not None:
        unused_settings, profile = admit_analysis_batch_read(analysis_batch_read)
        manifest['analysis_batch_read'] = dict(profile=profile,
            settings_sha256=_hash(canonical(analysis_batch_read_material(analysis_batch_read))))
    if source_runtime is not None:
        manifest['source_runtime'] = source_runtime
    _need(_sources(agent) == agent_sources and _sources(host) == host_sources)
    raw = canonical(manifest)
    _need(all(type(body) is bytes and 0 < len(body) <= 2097152 for body in (*materials.values(), raw)))
    create_private_directory(target)
    for name, body in materials.items():
        write_private_new(target / name, body)
    write_private_new(target / 'manifest.json', raw)
    return dict(schema_version=manifest['schema_version'], paired=True, qualified_in_qmt=False, order_ready=False,
        pair_manifest_sha256=_hash(raw), pair_config_sha256=manifest['config_sha256'])


def _verified(directory, installed_agent=None, *, with_schema=False, deadline=None):
    """缺省沿原核验；显式D按调用上下文贯穿材料读取，嵌套只收紧。"""
    if deadline is None:
        return _verified_material(directory, installed_agent, with_schema=with_schema)
    with material_deadline(deadline):
        return _verified_material(directory, installed_agent, with_schema=with_schema)


def _verified_material(directory, installed_agent=None, *, with_schema=False):
    directory = Path(directory)
    _inspect(directory, True)
    _need(_directory_names(directory) == FILES | {'manifest.json'})
    raw = _read(directory / 'manifest.json')
    manifest = decode(raw)
    _need(type(manifest) is dict and set(manifest) == FIELDS | ({'account_read'} if 'account_read' in manifest else set()) | ({'source_runtime'} if 'source_runtime' in manifest else set()) | ({'analysis_read'} if 'analysis_read' in manifest else set()) | ({'analysis_batch_read'} if 'analysis_batch_read' in manifest else set())
        and manifest['schema_version'] == (BATCH_ANALYSIS_SCHEMA if 'analysis_batch_read' in manifest else ANALYSIS_SCHEMA if 'analysis_read' in manifest else SOURCE_SCHEMA if 'source_runtime' in manifest else SCHEMA)
        and manifest['qualified_in_qmt'] is False and manifest['order_ready'] is False
        and manifest['strategy_name'] == 'GH_WT_MEMORY_VERIFY' and type(manifest['files']) is dict
        and set(manifest['files']) == FILES)
    agent, host, pythonw = _installation(installed_agent)
    _need(manifest['agent_package'] == str(agent) and manifest['host_package'] == str(host)
        and manifest['host_python'] == str(pythonw) and manifest['host_python_sha256'] == _hash(_read(pythonw, 67108864))
        and manifest['agent_sources'] == _sources(agent) and manifest['host_sources'] == _sources(host))
    materials = {name: _read(directory / name) for name in FILES}
    _need(all(_hash(body) == manifest['files'][name] for name, body in materials.items())
        and manifest['config_sha256'] == _hash(materials['deployment.json']) and materials['host.py'] == _launcher(agent))
    config, credentials, interval, market, account_read, source_runtime, analysis_read, analysis_batch_read = _decode_all_deployment(materials['deployment.json'])
    _need(manifest.get('source_runtime') == source_runtime)
    _need(('analysis_read' in manifest) == (analysis_read is not None))
    if analysis_read is not None:
        unused_settings, profile = admit_analysis_read(analysis_read)
        _need(manifest['analysis_read'] == dict(profile=profile, settings_sha256=_hash(canonical(analysis_read_material(analysis_read)))))
    _need(('analysis_batch_read' in manifest) == (analysis_batch_read is not None))
    if analysis_batch_read is not None:
        unused_settings, profile = admit_analysis_batch_read(analysis_batch_read)
        _need(manifest['analysis_batch_read'] == dict(profile=profile,
            settings_sha256=_hash(canonical(analysis_batch_read_material(analysis_batch_read)))))
    _need(('account_read' in manifest) == (account_read is not None))
    if account_read is not None:
        _need(manifest['account_read'] == _account_identity(account_read))
    _need(config.get('operation_policies_path') == str(directory / 'policy.json'))
    snapshot = _snapshot(config, credentials, materials['policy.json'], interval)
    config, credentials, settings, unused_p, unused_public, unused_a, lifecycle = snapshot
    _market_credentials(market, credentials)
    _account_credentials(account_read, credentials)
    _account_credentials(analysis_read, credentials)
    _account_credentials(analysis_batch_read, credentials)
    _need(manifest['capabilities'] == settings['allowed_operations']
        and canonical(_deployment(config, credentials, lifecycle['reconnect_seconds'], market, account_read, source_runtime, analysis_read, analysis_batch_read)) == materials['deployment.json'])
    strategy, memory = _freeze(agent, manifest['memory_runtime']['sdk'], materials['CPYTHON-LICENSE.txt'], settings, interval, market, account_read, source_runtime, analysis_read, analysis_batch_read)
    _need(strategy == materials['strategy.py'] and memory == manifest['memory_runtime']
        and _sources(agent) == manifest['agent_sources'] and _sources(host) == manifest['host_sources']
        and all(_read(directory / name) == body for name, body in materials.items())
        and _read(directory / 'manifest.json') == raw)
    result = (dict(pair_manifest_sha256=_hash(raw), pair_config_sha256=manifest['config_sha256']), snapshot)
    return result + (manifest['schema_version'],) if with_schema else result


def verify_product_pair(directory, *, installed_agent=None):
    identity, unused, schema = _verified(directory, installed_agent, with_schema=True)
    return dict(schema_version=schema, paired=True, qualified_in_qmt=False, order_ready=False, **identity)
