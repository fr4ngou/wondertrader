"""显式扩展实际原金融文件准入；合成账户，不发送Source或委托。"""
from copy import deepcopy
from hashlib import sha256
import json,os,subprocess
from pathlib import Path
import pytest
from guanheng_wt_runtime import execution_recovery as recovery

OLD='resonance-regime-v1'
NEW='resonance-original-wt-351f9d5-stable'

def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=recovery.canonical(value);path.write_bytes(raw)
    return dict(file=str(path),sha256=sha256(raw).hexdigest())

def fixture(root):
    previous=dict(budget=dict(run_ms=0),output_directory=str(root/'financial'),
        trader=dict(account='SYNTHETIC',writes_enabled=False),
        strategies=[dict(id=OLD,parameters=dict(python_strategy=dict(schema='guanheng.retained-cta.v1',input_sha256='b'*64)))],
        recovery=dict(mode='record_clean'))
    reference=put(root/'old'/'execution.json',previous)
    added=dict(id=NEW,parameters=dict(python_strategy=dict(schema='guanheng.original-live-cta.v1',
        strategy_version='0.2.0a1',initial_capital_cny='1000000',state_mode='new',activation_mode='signals-from-activation')))
    frozen=put(root/'added.json',added)
    current=deepcopy(previous);current['strategies'].append(added)
    current['recovery']=dict(mode='resume_reconciled')
    current['strategy_extension_origin']=dict(schema='guanheng.strategy-extension-origin.v1',**reference,added_strategy=frozen)
    output=Path(previous['output_directory'])
    for relative,value in (('stradata/'+OLD+'.json',dict(positions=[dict(code='SSE.ETF.510300',volume=1700)],fund=dict(total_profit=123))),
                           ('userdata/ud_'+OLD+'.json',dict(quantity_state='OLD-CASH-AND-CYCLES')),
                           ('portfolio/datas.json',dict(fund=dict(total_fees=7)))):
        put(output/relative,value)
    return previous,current

def native(request,root,success=True):
    binary=os.environ.get('GH_STRATEGY_EXTENSION_PROBE')
    if not binary:pytest.skip('显式Native探针未提供')
    path=root/'request.json';put(path,request)
    result=subprocess.run([binary,str(path)],capture_output=True,text=True,timeout=20)
    assert (result.returncode==0)==success,(result.stdout,result.stderr)
    assert json.loads(result.stdout)['ok']==success

def test_explicit_extension_main_and_native_state(tmp_path):
    before,after=fixture(tmp_path);files={str(p):p.read_bytes()for p in Path(before['output_directory']).rglob('*.json')}
    assert recovery.compatible_business_configuration(after,before)
    assert recovery.market_origin_configuration(after)=={**before,'recovery':after['recovery']}
    native(dict(mode='compare',previous=before,current=before),tmp_path)
    native(dict(mode='compare',previous=before,current=after),tmp_path)
    native(dict(mode='state',previous=before,current=after,output=before['output_directory']),tmp_path)
    assert files=={str(p):p.read_bytes()for p in Path(before['output_directory']).rglob('*.json')}

@pytest.mark.parametrize('tamper',[None,'state_sha','old_missing'])
def test_native_actual_fault_admission_preserves_files(tmp_path,tamper):
    before,current=fixture(tmp_path);previous=tmp_path/'old';control=tmp_path/'new-control';control.mkdir()
    config=put(previous/'execution.json',before)
    # 该合成PID在Windows不存在；原Native仍执行原OpenProcess退出核查。
    identity=dict(control_id=previous.name,config_sha256=config['sha256'],pid=4294967294)
    put(previous/'ready.json',dict(schema='guanheng.execution.ready.v1',**identity))
    put(previous/'failure.json',dict(schema='guanheng.execution.failure.v1',**identity))
    put(previous/'close-prepared.json',dict(schema='guanheng.execution.close-prepared.v1',**identity,closed=True,ok=False,recovery_ready=False))
    put(previous/'installation-identity.json',dict(schema='guanheng.execution-installation.v1',**identity,installation_sha256='a'*64))
    binding=put(previous/'python-binding.json',dict(schema='guanheng.cta-python-binding.v1',files=[]))
    output=Path(before['output_directory']);original={p.relative_to(output).as_posix():p.read_bytes()for p in output.rglob('*.json')}
    transition=dict(schema='guanheng.execution-recovery-transition.v1',predecessor_configuration=config['file'],
        predecessor_configuration_sha256=config['sha256'],predecessor_control_directory=str(previous),
        predecessor_installation_sha256='a'*64,successor_installation_sha256='b'*64,
        predecessor_python_binding_sha256=binding['sha256'],successor_python_code_identity='c'*64,
        state_files={name:sha256(raw).hexdigest()for name,raw in original.items()})
    current['recovery']['transition']=put(tmp_path/'transition.json',transition)
    old_file=output/'stradata'/f'{OLD}.json'
    if tamper=='state_sha':old_file.write_bytes(old_file.read_bytes()+b' ')
    elif tamper=='old_missing':old_file.unlink()
    native(dict(mode='admit',current=current,installation='b'*64,id='synthetic-new',configuration='d'*64,control=str(control)),tmp_path,tamper is None)
    if tamper is not None:
        assert not(control/'reconciled.json').exists()
        assert not list(output.glob('.cta-reconciled-*.json'))
        return
    admitted=json.loads((control/'reconciled.json').read_bytes())
    assert admitted['state_files']==transition['state_files']
    assert recovery.strategy_state_mode(current,NEW)=='new'
    assert original=={p.relative_to(output).as_posix():p.read_bytes()for p in output.rglob('*.json')if p.parent.name in ('stradata','userdata','portfolio')}
    assert not(output/'stradata'/f'{NEW}.json').exists()

@pytest.mark.parametrize('change',['account','old_row','added_row','drop','marker_sha','row_sha','old_origin_added'])
def test_identity_changes_rejected(tmp_path,change):
    old,current=fixture(tmp_path);changed=deepcopy(current)
    if change=='account':changed['trader']['account']='OTHER'
    elif change=='old_row':changed['strategies'][0]['parameters']['python_strategy']['input_sha256']='f'*64
    elif change=='added_row':changed['strategies'][1]['parameters']['python_strategy']['initial_capital_cny']='2000000'
    elif change=='drop':changed=deepcopy(old);old=current
    elif change=='marker_sha':changed['strategy_extension_origin']['sha256']='f'*64
    elif change=='row_sha':changed['strategy_extension_origin']['added_strategy']['sha256']='f'*64
    else:
        raw=deepcopy(old);raw['strategy_extension_origin']={};reference=put(tmp_path/'bad'/'execution.json',raw)
        changed['strategy_extension_origin'].update(reference)
    with pytest.raises(ValueError):recovery.compatible_business_configuration(changed,old)
    native(dict(mode='compare',previous=old,current=changed),tmp_path,False)

def test_two_context_resume_and_extra_files_rejected(tmp_path):
    old,current=fixture(tmp_path)
    assert recovery.compatible_business_configuration(current,current)
    native(dict(mode='compare',previous=current,current=current),tmp_path)
    native(dict(mode='state',previous=current,current=current,output=old['output_directory']),tmp_path,False)
    for folder,name in (('stradata',NEW+'.json'),('userdata','ud_'+NEW+'.json'),('stradata',NEW.upper()+'.json')):
        path=Path(old['output_directory'])/folder/name;put(path,{})
        native(dict(mode='state',previous=old,current=current,output=old['output_directory']),tmp_path,False)
        path.unlink()
    put(Path(old['output_directory'])/'stradata'/f'{NEW}.json',{})
    native(dict(mode='state',previous=current,current=current,output=old['output_directory']),tmp_path)

def test_only_explicit_additional_python_packages(tmp_path):
    def binding(files):return dict(site_root='E:/site',python='E:/env/Scripts/pythonw.exe',files=[('E:/site/'+k,v)for k,v in files.items()])
    old=binding({'guanheng_strategy_core/__init__.py':'a'*64})
    new=binding({'guanheng_strategy_core/__init__.py':'a'*64,'guanheng_strategy_original/reference.py':'b'*64,'guanheng_market_client/__init__.py':'c'*64})
    with pytest.raises(ValueError):recovery._compatible_python(old,new,strategy_upgrade=True)
    recovery._compatible_python(old,new,strategy_upgrade=True,strategy_extension=True)
    new['files'][0]=(new['files'][0][0],'d'*64)
    with pytest.raises(ValueError):recovery._compatible_python(old,new,strategy_upgrade=True,strategy_extension=True)

def test_mode_uses_verified_owner_not_new_config(monkeypatch,tmp_path):
    old,current=fixture(tmp_path);transition=dict(state_files={'stradata/'+OLD+'.json':'f'*64})
    monkeypatch.setattr(recovery,'load_transition',lambda *a,**k:(transition,'a'*64))
    monkeypatch.setattr(recovery,'state_origin_configuration',lambda *a,**k:old)
    assert recovery.strategy_state_mode(current,NEW)=='new'
    transition['state_files']['stradata/'+NEW+'.json']='a'*64
    with pytest.raises(ValueError):recovery.strategy_state_mode(current,NEW)
    monkeypatch.setattr(recovery,'state_origin_configuration',lambda *a,**k:current)
    assert recovery.strategy_state_mode(current,NEW)=='resume'
    current['recovery']['mode']='resume_clean'
    assert recovery.strategy_state_mode(current,NEW)=='resume'
