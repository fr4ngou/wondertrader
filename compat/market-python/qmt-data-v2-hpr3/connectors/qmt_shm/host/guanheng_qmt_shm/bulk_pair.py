"""显式v5开发配对；复用原内存加载器和常驻回调，不安装或启动任何入口。"""
from pathlib import Path
import sys

from guanheng_qmt_shm_agent.bulk_configuration import validate_bulk_configuration
from guanheng_qmt_shm_agent.protocol import canonical, decode
from .bootstrap import _snapshot_credentials, _validate_launch_configuration
from .bulk_bootstrap import bulk_agent_settings
from .contracts import OperationPolicy
from .lifecycle import validate_connection_lifecycle
from .material_integrity import source_manifest
from .memory_runtime import _prepare_runtime
from .pair import (_hash, _read, _configuration_sha, _resident_callbacks,
                   _render_memory_entry, _render_launcher)
from .policy import OperationPolicyRegistry
from .private_files import create_private_directory, write_private_new


def create_pair(config, *, agent_root, credentials, output, sdk_metadata,
                stdlib_license, reconnect_seconds):
    """从本仓源码生成新private目录，返回去敏摘要；根另行安装同名策略并启动。

    config为显式bulk Host配置；credentials仅进入生成的私有正文。
    sdk_metadata/stdlib_license沿原已验3.6.8运行库，agent_root显式指向
    本仓guanheng_qmt_shm_agent源码目录。函数只读源码并写新目录，不构造运行实例。
    """
    credentials=_snapshot_credentials(credentials)
    lifecycle=validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
        mode='resident-read',reconnect_seconds=reconnect_seconds))
    config=decode(canonical(config))
    policy_bytes=_read(config['operation_policies_path'],1048576)
    value=decode(policy_bytes)
    if (type(value) is not dict or set(value)!={'schema_version','policies'}
            or value['schema_version']!='1.0'):
        raise ValueError('invalid original policy material')
    policies=OperationPolicyRegistry([OperationPolicy.model_validate(item) for item in value['policies']])
    config,unused_policies,unused_limits=_validate_launch_configuration(config,
        credentials=credentials,trading=False,bulk=True,policy_registry=policies)
    settings=bulk_agent_settings(config,credentials['ipc_secret'])
    admitted=validate_bulk_configuration(settings)
    agent=Path(agent_root).resolve(strict=True)
    host=Path(__file__).resolve().parent
    agent_sources=source_manifest(agent)
    host_sources=source_manifest(host)
    memory_source,memory_identity=_prepare_runtime(agent,sdk_metadata,stdlib_license,
        ('guanheng_qmt_shm_agent.reconnecting_bulk',))

    callbacks=_resident_callbacks(lifecycle)
    original='from {namespace}.reconnecting_read import ReconnectingReadAgent as _Agent'
    if callbacks.count(original)!=1:
        raise ValueError('original resident callback entry changed')
    callbacks=callbacks.replace(original,
        'from {namespace}.reconnecting_bulk import ReconnectingBulkReadAgent as _Agent',1)
    strategy=_render_memory_entry(settings,memory_source,
        callbacks.format(namespace='guanheng_qmt_shm_agent'),('get_trade_detail_data',),
        ('init','agent_tick','handlebar','stop'))

    target=Path(output)
    if not target.is_absolute():
        raise ValueError('new absolute private pair directory required')
    target=target.parent.resolve(strict=True)/target.name
    config['operation_policies_path']=str(target/'policy.json')
    config_sha=_configuration_sha(config,settings,lifecycle)
    launcher=_render_launcher(config,credentials,agent,host,host_sources,agent_sources,
        policy_bytes,connection_lifecycle=lifecycle).decode('utf-8')
    original='    from guanheng_qmt_shm.bootstrap import build_read_service\n'
    if launcher.count(original)!=1:
        raise ValueError('original resident Host launcher changed')
    # 仍用原Python导入及来源核验；只给开发入口显式指定本仓两包父目录。
    replacement=('    sys.path.insert(0, '+repr(str(agent.parent))+')\n'
                 '    sys.path.insert(0, '+repr(str(host.parent))+')\n'
                 '    from guanheng_qmt_shm.bulk_bootstrap import build_read_service\n')
    launcher=launcher.replace(original,replacement,1).encode('utf-8')
    if source_manifest(agent)!=agent_sources or source_manifest(host)!=host_sources:
        raise ValueError('development pairing source changed during generation')
    files={'host.py':_hash(launcher),'strategy.py':_hash(strategy),
           'policy.json':_hash(policy_bytes),'CPYTHON-LICENSE.txt':_hash(stdlib_license)}
    manifest=dict(schema_version='qmt.bulk-development-pair.v1',source_mode='repository',
        strategy_name='GH_WT_MEMORY_VERIFY',config_sha256=config_sha,host_python=sys.executable,
        host_package=str(host),host_sources=host_sources,agent_package=str(agent),agent_sources=agent_sources,
        memory_runtime=memory_identity,connection_lifecycle=lifecycle,files=files,
        capabilities=admitted.profile['read_operations'],qualified_in_qmt=False,order_ready=False)
    materials=[('policy.json',policy_bytes),('host.py',launcher),('strategy.py',strategy),
               ('CPYTHON-LICENSE.txt',stdlib_license),('manifest.json',canonical(manifest))]
    if any(not 1<=len(raw)<=2097152 for unused,raw in materials):
        raise ValueError('development pair exceeds original file budget')
    created=create_private_directory(target)
    for name,raw in materials:
        write_private_new(created/name,raw)
    return dict(paired=True,development_only=True,qualified_in_qmt=False,order_ready=False,
        config_sha256=config_sha,strategy_name='GH_WT_MEMORY_VERIFY',files=files,
        capabilities=admitted.profile['read_operations'])
