"""Source续接的固定源码owner集合；合成安装/材料，无Source或金融调用。"""
from copy import deepcopy
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from guanheng_wt_runtime import execution_process as process, execution_recovery as recovery
from guanheng_wt_runtime import strategy_profiles as profiles
from guanheng_wt_runtime.execution_dependency_handoff import FIELDS, SOURCE_FIELDS


def native(root, source=True):
    value = dict(strategies=[dict(id=profiles.RETAINED_ID,parameters=dict(python_strategy=dict(schema=profiles.RETAINED_PROFILE))),
                            dict(id=profiles.ORIGINAL_ID,parameters=dict(python_strategy=dict(schema=profiles.ORIGINAL_PROFILE,shared_account={'path':'E:/frozen.json','sha256':'a'*64})))])
    proof = {key: None for key in FIELDS}
    proof.update(schema='guanheng.strategy-dependency-handoff.v1',
                 source_extension={key: None for key in SOURCE_FIELDS} if source else None)
    path=root/'dependencies.json';raw=json.dumps(proof).encode();path.write_bytes(raw)
    value['strategy_extension_origin']=dict(dependency_handoff=dict(file=str(path),sha256=sha256(raw).hexdigest()))
    return value


def binding(site, files):
    return dict(site_root=str(site),python=str(site.parent/'Scripts/python.exe'),
                files=[(str(site/path),value)for path,value in files.items()])


def test_fixed_selection_and_original_no_source_sets(tmp_path):
    value=native(tmp_path)
    assert process._python_packages(value)==profiles.SOURCE_HANDOFF_PACKAGES
    assert profiles.PACKAGE_DISTRIBUTIONS['guanheng_qmt_shm']=='guanheng-qmt-shm-host'
    assert process._python_packages(native(tmp_path,False))==profiles.SHARED_PACKAGES
    value.pop('strategy_extension_origin');assert process._python_packages(value)==profiles.SHARED_PACKAGES
    value['strategies']=value['strategies'][:1]
    assert process._python_packages(value)==profiles.RETAINED_PACKAGES


def test_source_selection_rejects_changed_proof_and_unlisted_profile(tmp_path):
    value=native(tmp_path);path=Path(value['strategy_extension_origin']['dependency_handoff']['file'])
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError):process._python_packages(value)
    value=native(tmp_path);value['strategies']=value['strategies'][:1]
    with pytest.raises(ValueError):process._python_packages(value)


def test_only_explicit_new_source_owners_may_be_added(tmp_path):
    old=binding(tmp_path,{'guanheng_strategy_core/__init__.py':'a'*64})
    additions={'guanheng_qmt_shm/trade_deployment_identity.py':'b'*64,
               'guanheng_qmt_shm_host-0.1.dist-info/METADATA':'c'*64,
               'guanheng_qmt_shm_agent/protocol.py':'d'*64,
               'guanheng_qmt_shm_agent-0.1.dist-info/METADATA':'e'*64}
    new=binding(tmp_path,{'guanheng_strategy_core/__init__.py':'a'*64,**additions})
    with pytest.raises(ValueError):recovery._compatible_python(old,new,strategy_extension=True)
    recovery._compatible_python(old,new,strategy_extension=True,source_handoff=True)
    # 既有owner不得借新增依赖资格换码、删码或替换METADATA。
    changed=deepcopy(new);changed['files'][-1]=(changed['files'][-1][0],'f'*64)
    with pytest.raises(ValueError):recovery._compatible_python(new,changed,strategy_extension=True,source_handoff=True)
    with pytest.raises(ValueError):recovery._compatible_python(new,old,strategy_extension=True,source_handoff=True)
    wrong=binding(tmp_path,{'unlisted_source/__init__.py':'f'*64})
    with pytest.raises(ValueError):recovery._compatible_python(old,wrong,strategy_extension=True,source_handoff=True)
    # 前代已有该owner任一文件时，新增源码、第二发行元数据或补全半绑定均拒绝。
    for extra in ('guanheng_qmt_shm/new_module.py','guanheng_qmt_shm_host-9.9.dist-info/METADATA',
                  'guanheng_qmt_shm_agent/new_module.py'):
        expanded=deepcopy(new);expanded['files'].append((str(tmp_path/extra),'f'*64))
        with pytest.raises(ValueError):recovery._compatible_python(new,expanded,strategy_extension=True,source_handoff=True)
    partial=binding(tmp_path,{'guanheng_strategy_core/__init__.py':'a'*64,
                              'guanheng_qmt_shm/trade_deployment_identity.py':'b'*64})
    with pytest.raises(ValueError):recovery._compatible_python(partial,new,strategy_extension=True,source_handoff=True)
    # 两个owner分别首次补入；已有另一个owner完整清单保持相同。
    host_only=binding(tmp_path,{'guanheng_strategy_core/__init__.py':'a'*64,
                              **{k:v for k,v in additions.items()if not k.startswith('guanheng_qmt_shm_agent')}})
    agent_only=binding(tmp_path,{'guanheng_strategy_core/__init__.py':'a'*64,
                               **{k:v for k,v in additions.items()if k.startswith('guanheng_qmt_shm_agent')}})
    recovery._compatible_python(host_only,new,strategy_extension=True,source_handoff=True)
    recovery._compatible_python(agent_only,new,strategy_extension=True,source_handoff=True)


@pytest.mark.parametrize('source',[False,True],ids=['original-shared-set','explicit-source-set'])
def test_real_python_config_loader_binds_correct_dist_and_source_inventory(tmp_path,monkeypatch,source):
    site=tmp_path/'site';site.mkdir()
    value=native(tmp_path,source);config=tmp_path/'execution.json';config.write_text(json.dumps(value))
    requests=[]
    for package in profiles.SOURCE_HANDOFF_PACKAGES:
        folder=site/package;folder.mkdir();(folder/'__init__.py').write_text('# synthetic owner\n')
        dist=profiles.PACKAGE_DISTRIBUTIONS[package];meta=site/(dist.replace('-','_')+'-0.1.dist-info');meta.mkdir()
        (meta/'METADATA').write_text('Metadata-Version: 2.1\nName: '+dist+'\nVersion: 0.1\n')
        rows=[package+'/__init__.py',meta.name+'/METADATA']
        if package=='guanheng_wt_runtime':
            (folder/'execution_process.py').write_text('# synthetic fixed-entry source\n');rows.append(package+'/execution_process.py')
        (meta/'RECORD').write_text(''.join(row+',,\n'for row in rows))
    def distribution(name):
        requests.append(name)
        return importlib.metadata.PathDistribution(site/(name.replace('-','_')+'-0.1.dist-info'))
    monkeypatch.setattr(importlib.metadata,'distribution',distribution)
    # 隔离原Native安装owner；真实Python配置收集/哈希/元数据/目录闭包继续执行。
    monkeypatch.setattr(process.ExecutionProcessConfig,'load',lambda *args:SimpleNamespace(configuration=config))
    monkeypatch.setattr(process,'__file__',str(site/'guanheng_wt_runtime/execution_process.py'))
    admitted=process.PythonExecutionProcessConfig.load(tmp_path,config,tmp_path)
    assert admitted.packages==(profiles.SOURCE_HANDOFF_PACKAGES if source else profiles.SHARED_PACKAGES)
    if source:assert requests[-2:]==['guanheng-qmt-shm-host','guanheng-qmt-shm-agent']
    else:assert not any(name.startswith('guanheng-qmt-shm')for name in requests)
    identities=dict(admitted.python_files)
    for package in profiles.SOURCE_OWNER_PACKAGES:
        assert (str(site/package/'__init__.py')in identities)==source
    assert len(admitted.python_files)<=512
    # 删除任一owner元数据或增加未绑定源码，原目录校验均拒绝。
    selected=admitted.packages[-1];distribution_name=profiles.PACKAGE_DISTRIBUTIONS[selected]
    missing={name:h for name,h in identities.items()if distribution_name.replace('-','_')+'-'not in name}
    with pytest.raises(ValueError):process._python_inventory(site,missing,packages=admitted.packages)
    (site/selected/'extra.py').write_text('# unbound source\n')
    with pytest.raises(ValueError):process._python_inventory(site,identities,packages=admitted.packages)
    (site/selected/'extra.py').unlink()
    metadata=site/(distribution_name.replace('-','_')+'-0.1.dist-info')/'METADATA'
    metadata.write_text('Metadata-Version: 2.1\nName: unlisted-owner\nVersion: 0.1\n')
    with pytest.raises(ValueError):process.PythonExecutionProcessConfig.load(tmp_path,config,tmp_path)
