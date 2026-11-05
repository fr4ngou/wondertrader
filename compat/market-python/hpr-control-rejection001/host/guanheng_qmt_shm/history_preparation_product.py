"""HPR专用产品配对；有界静态重建完整正文，凭据始终留在私有快照。"""
import hashlib
import os
from pathlib import Path
import stat
import sys
import guanheng_qmt_shm_agent
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.history_preparation import OPERATION, validate_configuration
from guanheng_qmt_shm_agent.quote_stream_contract import validate_settings
from guanheng_qmt_shm_agent.transport_profile import validate_transport_profile
from .bootstrap import _snapshot_credentials
from .contracts import OperationPolicy
from .history_preparation_bootstrap import agent_settings, validate_launch, _build_read_service
from .lifecycle import validate_connection_lifecycle
from .material_integrity import source_manifest
from .policy import OperationPolicyRegistry
from .private_files import create_private_directory, write_private_new
from .quote_stream_memory import render_strategy
from .read_service import ReconnectingReadService
from .runtime import response

SCHEMA = 'qmt.history-preparation-product-pair.v1'
FILES = frozenset(('host.py', 'strategy.py', 'deployment.json', 'policy.json', 'CPYTHON-LICENSE.txt'))
FIELDS = frozenset(('schema_version', 'config_sha256', 'host_python', 'host_python_sha256',
    'host_package', 'host_sources', 'agent_package', 'agent_sources', 'memory_runtime', 'files',
    'qualified_in_qmt', 'order_ready', 'capabilities', 'strategy_name'))
MARKET = frozenset(('market.full_tick', 'market.history_1m', OPERATION))


class _ProductService(ReconnectingReadService):
    """原服务拥有全部生命周期；产品只细化原Journal满额的安全错误。"""
    def request(self, request):
        result = super().request(request)
        if (request.operation == 'bound.submit' and result.status_code == 503
                and decode(result.content).get('error_code') == 'queue_full'):
            return response(503, dict(error_code='journal_capacity_exhausted',
                error_message='通信历史容量已满；已有结果保留，请维护者核对声明任务数和字节额度'))
        return result


def _need(value):
    if not value:
        raise ValueError('history preparation product identity differs')


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _inspect(path, directory=False):
    _need(path.is_absolute() and '..' not in path.parts)
    for item in reversed((path, *path.parents)):
        info = item.lstat()
        _need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400)
        if item != path:
            _need(stat.S_ISDIR(info.st_mode))
    _need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    return info


def _read(path, maximum=2097152):
    """同一打开文件前后身份；离线读取不解释或执行生成脚本。"""
    path = Path(path)
    before = _inspect(path)
    _need(0 < before.st_size <= maximum)
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        _need(identity(opened) == identity(before))
        raw = stream.read(maximum+1)
        _need(identity(os.fstat(stream.fileno())) == identity(opened))
    _need(identity(_inspect(path)) == identity(opened) and len(raw) == opened.st_size)
    return raw


def _sources(package):
    _inspect(package, True)
    return source_manifest(package, reader=_read)


def _installation(installed_agent=None):
    agent = Path(guanheng_qmt_shm_agent.__file__).resolve().parent
    if installed_agent is not None:
        _need(Path(installed_agent) == agent)
    host = Path(__file__).resolve().parent
    pythonw = Path(sys.executable).parent/'pythonw.exe'
    return agent, host, pythonw


def _policies(raw):
    value = decode(raw)
    _need(type(value) is dict and set(value) == {'schema_version', 'policies'}
          and value['schema_version'] == '1.0' and type(value['policies']) is list)
    policies = [OperationPolicy.model_validate(item) for item in value['policies']]
    _need(all(canonical(policy.model_dump(mode='json')) == canonical(item)
              for policy, item in zip(policies, value['policies'])))
    return OperationPolicyRegistry(policies)


def _snapshot(config, quotes, credentials, policy_raw, reconnect_seconds):
    credentials = _snapshot_credentials(credentials)
    config, policies, public = validate_launch(config, credentials=credentials, policy_registry=_policies(policy_raw))
    _need({item['policy_id']: item['operation_ids'] for item in decode(policy_raw)['policies']} ==
        {descriptor['policy_id']: [operation] for operation, descriptor in config['operation_profiles'].items()})
    # 声明的任务数须有最坏请求/结果/metadata的完整预留，不使用合成夹具的零散字节额。
    _need(config['max_journal_bytes'] == config['max_records'] *
        (public['max_request_bytes'] + config['max_result_bytes'] + 16384))
    settings = agent_settings(config, policies, credentials['ipc_secret'])
    history = validate_configuration(settings)
    # 完整正文使用repr；公共嵌套dict先规范顺序，create与JSON回读重建的字节一致。
    quote = validate_settings(dict(decode(canonical({key: value for key, value in quotes.items()
        if key != 'secret'})), secret=quotes['secret']))
    lifecycle = validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
        mode='resident-read', reconnect_seconds=reconnect_seconds))
    _need(set(history.profile['read_operations']) <= MARKET
          and quote['transport']['windows_session_id'] == settings['transport']['windows_session_id']
          and validate_transport_profile(quote['transport'], quote['route'], quote['max_frame'], quote['profile']).name !=
              validate_transport_profile(settings['transport'], history.route, settings['max_frame'], history.profile).name
          and quote['secret'] != credentials['ipc_secret']
          and quote['secret'] != next(iter(credentials['http_keys'].values())).encode('utf8'))
    return config, quote, credentials, settings, policies, public, lifecycle


def _deployment(config, quotes, credentials, reconnect_seconds):
    return dict(schema_version='qmt.history-preparation-deployment.v1', host=config,
        quotes={key: value for key, value in quotes.items() if key != 'secret'},
        quote_ipc_secret_hex=quotes['secret'].hex(),
        credentials=dict(ipc_secret_hex=credentials['ipc_secret'].hex(), http_keys=credentials['http_keys']),
        reconnect_seconds=reconnect_seconds)


def _decode_deployment(raw):
    value = decode(raw)
    _need(type(value) is dict and set(value) == {'schema_version', 'host', 'quotes',
        'quote_ipc_secret_hex', 'credentials', 'reconnect_seconds'}
        and value['schema_version'] == 'qmt.history-preparation-deployment.v1')
    credentials = value['credentials']
    _need(type(credentials) is dict and set(credentials) == {'ipc_secret_hex', 'http_keys'})
    secrets = []
    for text in (credentials['ipc_secret_hex'], value['quote_ipc_secret_hex']):
        _need(type(text) is str and 64 <= len(text) <= 8192 and len(text) % 2 == 0
              and all(char in '0123456789abcdef' for char in text))
        secrets.append(bytes.fromhex(text))
    _need(type(value['quotes']) is dict and 'secret' not in value['quotes'])
    return value['host'], dict(value['quotes'], secret=secrets[1]), dict(ipc_secret=secrets[0],
        http_keys=credentials['http_keys']), value['reconnect_seconds']


def _launcher(agent):
    # 正式运行不执行这个文件；它仍是必须逐字节重建的可读独立入口。
    return ("from pathlib import Path\nfrom guanheng_qmt_shm.history_preparation_cli import main\n"
        "if __name__ == '__main__':\n    raise SystemExit(main(['run', '--directory', "
        "str(Path(__file__).resolve().parent), '--installed-agent', " + repr(str(agent)) + "]))\n").encode('utf8')


def _freeze(agent, metadata, license_bytes, quote, settings, reconnect_seconds):
    # 冻结器读到的全部SDK原件也沿同一普通文件身份核验；不启动SDK解释器。
    for root in (Path(agent), Path(metadata['stdlib_root']), Path(metadata['python_executable']).parent/'Lib'):
        _inspect(root, True)
    binaries = ((Path(metadata['python_executable']), metadata['python_sha256']),
        (Path(metadata['python_executable']).parent/'python36.dll', metadata['python_dll_sha256']))
    for path, expected in binaries:
        _need(_hash(_read(path, 67108864)) == expected)
    strategy, identity = render_strategy(quote, agent_root=agent, sdk_metadata=metadata,
        license_bytes=license_bytes, history_bootstrap=settings, history_reconnect_seconds=reconnect_seconds,
        input_reader=_read)
    for item in identity['source_files'].values():
        if item['kind'] == 'python-source':
            _need(_hash(_read(Path(item['path']))) == item['sha256'])
    for path, expected in binaries:
        _need(_hash(_read(path, 67108864)) == expected)
    return strategy, identity


def create_product_pair(config, quotes, *, credentials, output, sdk_metadata, stdlib_license,
                        reconnect_seconds, installed_agent=None):
    """严格离线产品create；只新建私有材料，返回摘要，不启动或授真实来源资格。"""
    agent, host, pythonw = _installation(installed_agent)
    agent_sources, host_sources = _sources(agent), _sources(host)
    policy_raw = _read(Path(config['operation_policies_path']), 1048576)
    target = Path(output)
    _need(target.is_absolute() and target.drive.upper() == 'E:' and not target.exists())
    _inspect(target.parent, True)
    config = decode(canonical(config))
    config['operation_policies_path'] = str(target/'policy.json')
    config, quotes, credentials, settings, unused_p, unused_l, lifecycle = _snapshot(
        config, quotes, credentials, policy_raw, reconnect_seconds)
    strategy, runtime = _freeze(agent, sdk_metadata, stdlib_license, quotes, settings, lifecycle['reconnect_seconds'])
    deployment_raw = canonical(_deployment(config, quotes, credentials, lifecycle['reconnect_seconds']))
    materials = {'deployment.json': deployment_raw, 'policy.json': policy_raw,
        'strategy.py': strategy, 'host.py': _launcher(agent), 'CPYTHON-LICENSE.txt': stdlib_license}
    manifest = dict(schema_version=SCHEMA, config_sha256=_hash(deployment_raw), host_python=str(pythonw),
        host_python_sha256=_hash(_read(pythonw, 67108864)), host_package=str(host), host_sources=host_sources,
        agent_package=str(agent), agent_sources=agent_sources, memory_runtime=runtime,
        files={name: _hash(raw) for name, raw in materials.items()}, qualified_in_qmt=False,
        order_ready=False, capabilities=settings['allowed_operations'], strategy_name='GH_WT_MEMORY_VERIFY')
    _need(_sources(agent) == agent_sources and _sources(host) == host_sources)
    manifest_raw = canonical(manifest)
    _need(all(type(raw) is bytes and 0 < len(raw) <= 2097152 for raw in (*materials.values(), manifest_raw)))
    create_private_directory(target)
    for name, raw in materials.items():
        write_private_new(target/name, raw)
    write_private_new(target/'manifest.json', manifest_raw)
    return dict(schema_version=SCHEMA, paired=True, qualified_in_qmt=False, order_ready=False,
        pair_manifest_sha256=_hash(manifest_raw), pair_config_sha256=manifest['config_sha256'])


def _verified(directory, installed_agent=None):
    directory = Path(directory)
    _inspect(directory, True)
    _need({path.name for path in directory.iterdir()} == FILES | {'manifest.json'})
    manifest_raw = _read(directory/'manifest.json')
    value = decode(manifest_raw)
    _need(type(value) is dict and set(value) == FIELDS and value['schema_version'] == SCHEMA
          and value['qualified_in_qmt'] is False and value['order_ready'] is False
          and value['strategy_name'] == 'GH_WT_MEMORY_VERIFY' and type(value['files']) is dict
          and set(value['files']) == FILES)
    agent, host, pythonw = _installation(installed_agent)
    _need(value['agent_package'] == str(agent) and value['host_package'] == str(host)
          and value['host_python'] == str(pythonw)
          and value['host_python_sha256'] == _hash(_read(pythonw, 67108864))
          and value['agent_sources'] == _sources(agent) and value['host_sources'] == _sources(host))
    materials = {name: _read(directory/name) for name in FILES}
    _need(all(_hash(raw) == value['files'][name] for name, raw in materials.items())
          and value['config_sha256'] == _hash(materials['deployment.json'])
          and materials['host.py'] == _launcher(agent))
    config, quote, credentials, interval = _decode_deployment(materials['deployment.json'])
    _need(config.get('operation_policies_path') == str(directory/'policy.json'))
    config, quote, credentials, settings, policies, public, lifecycle = _snapshot(
        config, quote, credentials, materials['policy.json'], interval)
    _need(value['capabilities'] == settings['allowed_operations']
          and canonical(_deployment(config, quote, credentials, interval)) == materials['deployment.json'])
    strategy, runtime = _freeze(agent, value['memory_runtime']['sdk'], materials['CPYTHON-LICENSE.txt'],
        quote, settings, lifecycle['reconnect_seconds'])
    _need(strategy == materials['strategy.py'] and runtime == value['memory_runtime']
          and value['agent_sources'] == _sources(agent) and value['host_sources'] == _sources(host)
          and all(_read(directory/name) == raw for name, raw in materials.items())
          and _read(directory/'manifest.json') == manifest_raw)
    identity = dict(pair_manifest_sha256=_hash(manifest_raw), pair_config_sha256=value['config_sha256'])
    return identity, (config, credentials, policies, public, lifecycle)


def verify_product_pair(directory, *, installed_agent=None):
    """离线重建全文并核安装身份；不执行生成入口或取得任何服务owner。"""
    identity, unused = _verified(directory, installed_agent)
    return dict(schema_version=SCHEMA, paired=True, qualified_in_qmt=False, order_ready=False, **identity)


def build_product_runtime(directory, *, installed_agent=None):
    """只消费同次verify私有快照；不重读policy、不执行host.py。"""
    identity, private = _verified(directory, installed_agent)
    config, credentials, policies, public, lifecycle = private
    runtime = _build_read_service(config, policies, public, credentials,
        reconnect_seconds=lifecycle['reconnect_seconds'], service_type=_ProductService)
    return runtime, dict(credentials['http_keys']), identity
