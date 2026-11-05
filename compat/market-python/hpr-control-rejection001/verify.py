"""正常安装环境验兼容闭包、真实原件后继配对和同owner主链；不启动任何来源服务。"""
import argparse
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import unittest


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-pair',type=Path,required=True)
    parser.add_argument('--candidate-pair',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent;repo=root.parents[2]
    identity=json.loads((root/'SOURCE-IDENTITY.json').read_bytes())
    import guanheng_qmt_shm
    import guanheng_qmt_shm_agent
    from guanheng_qmt_shm.history_preparation_product import (
        _read,_decode_deployment,create_product_pair,verify_product_pair)
    from guanheng_qmt_shm_agent.protocol import decode
    host=Path(guanheng_qmt_shm.__file__).parent;agent=Path(guanheng_qmt_shm_agent.__file__).parent
    if (importlib.metadata.version('guanheng-qmt-shm-host')!=identity['compatible_version']
            or importlib.metadata.version('guanheng-qmt-shm-agent')!=identity['agent_version']
            or {p.name:digest(p)for p in host.glob('*.py')}!=identity['compatible_files']
            or {'guanheng_qmt_shm_agent/'+p.name:digest(p)for p in agent.glob('*.py')}!=identity['agent_wheel']['package_files']):
        raise ValueError('installed HPR closure differs')
    original=args.original_pair.absolute();candidate=args.candidate_pair.absolute()
    if candidate==original or candidate.is_relative_to(original)or original.is_relative_to(candidate):
        raise ValueError('successor pair must be an independent directory')
    manifest_raw=_read(original/'manifest.json');manifest=decode(manifest_raw)
    if manifest['host_sources']!=identity['installed_baseline_files']:
        raise ValueError('original pair host baseline differs')
    originals={name:sha for name,sha in manifest['files'].items()}
    for name,sha in originals.items():
        if digest(original/name)!=sha:raise ValueError('original pair material differs')
    if not candidate.exists():
        config,quotes,credentials,interval=_decode_deployment(_read(original/'deployment.json'))
        create_product_pair(config,quotes,credentials=credentials,output=candidate,
            sdk_metadata=manifest['memory_runtime']['sdk'],stdlib_license=_read(original/'CPYTHON-LICENSE.txt',65536),
            reconnect_seconds=interval,installed_agent=agent)
    verified=verify_product_pair(candidate,installed_agent=agent)
    original_config,original_quotes,original_credentials,original_interval=_decode_deployment(_read(original/'deployment.json'))
    candidate_config,candidate_quotes,candidate_credentials,candidate_interval=_decode_deployment(_read(candidate/'deployment.json'))
    original_config.pop('operation_policies_path');candidate_config.pop('operation_policies_path')
    if ((original_config,original_quotes,original_credentials,original_interval)
            !=(candidate_config,candidate_quotes,candidate_credentials,candidate_interval)
            or _read(original/'policy.json')!=_read(candidate/'policy.json')):
        raise ValueError('original HPR business configuration differs')
    if _read(original/'strategy.py')!=_read(candidate/'strategy.py'):
        raise ValueError('QMT strategy body changed')
    for name,sha in originals.items():
        if digest(original/name)!=sha:raise ValueError('original pair changed during preparation')
    if _read(original/'manifest.json')!=manifest_raw:raise ValueError('original manifest changed')
    test=repo/identity['verification_test']['path']
    if digest(test)!=identity['verification_test']['sha256']:raise ValueError('fixed verification test differs')
    tree=ast.parse(test.read_text(encoding='utf-8'))
    # 原类只定义测试；去掉其源码sys.path注入，所有业务模块必须来自本环境已核wheel。
    tree.body=[n for n in tree.body if not(isinstance(n,ast.Assign)and any(
        isinstance(t,ast.Subscript)and isinstance(t.value,ast.Attribute)
        and isinstance(t.value.value,ast.Name)and t.value.value.id=='sys'and t.value.attr=='path'for t in n.targets))]
    namespace={'__name__':'installed_hpr_tests','__file__':str(test)}
    exec(compile(tree,str(test),'exec'),namespace)
    run=unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(namespace['ControlRejectionTests']))
    if not run.wasSuccessful():return 1
    report=dict(
        schema='guanheng.hpr-compatible-installation.v1',  # 仅工程制品与配对验证，不授真实来源资格。
        host_version=identity['compatible_version'],  # 正常安装的兼容Host发行版本。
        agent_version=identity['agent_version'],  # 原Agent精确发行，60个源码成员原字节核验。
        installed_host_sources_verified=True,  # 已核全部63个安装源码，未从仓库导入业务模块。
        original_pair_unchanged=True,  # 原manifest和五个原材料前后SHA一致。
        original_business_configuration_preserved=True,  # 原配置/路由/额度/权限/凭据/原Journal定位不变；只重定位已核policy文件。
        original_pair_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),  # 原私有pair的内容身份，不含凭据。
        successor_pair_manifest_sha256=verified['pair_manifest_sha256'],  # 经原正常产品verify验证的新安装身份。
        strategy_bytes_unchanged=True,  # 实际原QMT正文与新配对正文逐字节一致。
        strategy_sha256=digest(candidate/'strategy.py'),  # 只记录正文SHA，不复制正文到普通报告。
        isolated_tests_run=run.testsRun,  # 实际安装类的主链/异常测试数，来源SDK是明确替身。
        real_qmt_invocations=0,  # 此验证不构造实际来源runtime、不打开现场通信Journal。
        service_operations=0)  # 本脚本没有启动/停止服务或操作QMT。
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
    return 0


if __name__=='__main__':raise SystemExit(main())
