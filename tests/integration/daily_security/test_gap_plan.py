"""计划文档容量、原责任资格与纯本地marker恢复；无Source或账户调用。"""
from copy import deepcopy
import hashlib
from pathlib import Path
from time import monotonic
from uuid import uuid4
from threading import Event, Lock, enumerate as threads
from time import sleep

import pytest

from integrations.guanheng import daily_gap_plan as plans
from integrations.guanheng.daily_data_stages import prepare_directory
from integrations.guanheng.market_generation import encode


def fixture(tmp_path):
    slot = tmp_path/'slot.json'
    original = dict(request_id=str(uuid4()),operation_id='market.history_prepare',
                    arguments=dict(symbol='510300.SH',period='1d',start_time='20261105',end_time='20261105'))
    slot.write_bytes(encode(dict(request=original)))  # 原兼容裸请求保持unknown，无完成资格。
    protected = plans.read_protected_request(slot,deadline=monotonic()+5)
    value = dict(schema=plans.SCHEMA,capture=dict(directory=str(tmp_path/'capture'),sha256='a'*64),
                 snapshot_id='b'*64,authorized_from='20261106',authorized_to='20261106',
                 protected_requests=[protected],tasks=[dict(index=0,symbol='510300.SH',
                    start_date='20261106',end_date='20261106',dates=['20261106'],reason='calendar_expected_cache_gap')],
                 exclusions=[])
    return slot,value


def restore(directory,value):
    return plans.restore_gap_plan(directory/'PLAN.json',capture=value['capture'],snapshot_id=value['snapshot_id'],
        authorized_from=value['authorized_from'],authorized_to=value['authorized_to'],
        protected_slots=[row['slot']for row in value['protected_requests']],deadline=monotonic()+10)


def legacy_marker(tmp_path):
    """旧writer的精确五字段v1原件；执行结果未记录，绝不补造已返回资格。"""
    slot,value=fixture(tmp_path)
    del value['protected_requests'][0]['execution_state']
    root=tmp_path/'legacy';root.mkdir()
    raw=encode(value);path=root/'PLAN.json';path.write_bytes(raw)
    return slot,value,dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest())


def test_historical_five_field_plan_load_restore_and_freeze_keep_unknown_identity(tmp_path):
    slot,value,descriptor=legacy_marker(tmp_path)
    raw=Path(descriptor['path']).read_bytes();slot_raw=slot.read_bytes()
    loaded=plans.load_gap_plan(descriptor,deadline=monotonic()+5)
    assert loaded['protected_requests'][0]==dict(value['protected_requests'][0],execution_state='unknown')
    assert restore(Path(descriptor['path']).parent,value)==descriptor
    from integrations.guanheng.daily_gap_update import freeze_gap_progress
    freeze_gap_progress(descriptor,None,deadline=monotonic()+5)
    assert Path(descriptor['path']).read_bytes()==raw and slot.read_bytes()==slot_raw
    assert 'execution_state'not in value['protected_requests'][0]


def test_new_writer_requires_explicit_execution_state_before_creating_marker(tmp_path):
    _slot,value,_descriptor=legacy_marker(tmp_path)
    with pytest.raises(ValueError,match='protected identity'):
        plans.write_gap_plan(tmp_path/'new',value,deadline=monotonic()+5)
    assert not (tmp_path/'new').exists()


@pytest.mark.parametrize('change',['missing_identity','extra_key','invalid_state','overlap'])
def test_legacy_decode_keeps_exact_identity_schema_and_unknown_protection(tmp_path,change):
    _slot,value,descriptor=legacy_marker(tmp_path)
    row=value['protected_requests'][0]
    if change=='missing_identity':del row['request_sha256']
    elif change=='extra_key':row['legacy_guess']=True
    elif change=='invalid_state':row['execution_state']=None
    else:row['arguments'].update(start_time='20261106',end_time='20261106')
    raw=encode(value);Path(descriptor['path']).write_bytes(raw)
    with pytest.raises(ValueError):
        plans.load_gap_plan(dict(descriptor,sha256=hashlib.sha256(raw).hexdigest()),deadline=monotonic()+5)


def test_historical_plan_does_not_upgrade_later_slot_result_and_checks_changed_request(tmp_path,monkeypatch):
    slot,value,descriptor=legacy_marker(tmp_path)
    original=plans.read_protected_request
    def later(*args,**kwargs):return dict(original(*args,**kwargs),execution_state='call_returned')
    monkeypatch.setattr(plans,'read_protected_request',later)
    assert restore(Path(descriptor['path']).parent,value)==descriptor
    assert plans.load_gap_plan(descriptor)['protected_requests'][0]['execution_state']=='unknown'
    import json
    changed=json.loads(slot.read_bytes());changed['request']['request_id']=str(uuid4())
    slot.write_bytes(encode(changed))
    with pytest.raises(plans.GapPlanReferenceError):restore(Path(descriptor['path']).parent,value)


def test_prepare_update_consumes_historical_plan_and_preserves_all_original_identities(tmp_path,monkeypatch):
    """自然后继先读原计划再完成UPDATE；只替换公开事实/来源边界，真实输入owner写QA根。"""
    import importlib.util
    import json
    from integrations.guanheng import daily_data_inputs as inputs
    fixture_path=Path(__file__).parents[1]/'market_supplement'/'test_daily_owner.py'
    spec=importlib.util.spec_from_file_location('historical_plan_daily_owner_fixture',fixture_path)
    dependency=importlib.util.module_from_spec(spec);spec.loader.exec_module(dependency)
    config,pool,facts,original_request=dependency.owner_fixture(tmp_path)
    config['inputs'].pop('supplement_facts')
    dependency.patch_owner_dependencies(monkeypatch,config,pool,facts,original_request)
    slot,value,descriptor=legacy_marker(tmp_path)
    value.update(authorized_from='20261104',authorized_to='20261104')
    value['tasks'][0].update(start_date='20261104',end_date='20261104',dates=['20261104'])
    original=json.loads(slot.read_bytes());original['request']['arguments'].update(start_time='20261103',end_time='20261103')
    slot.write_bytes(encode(original))
    identity=plans.read_protected_request(slot,deadline=monotonic()+5);identity.pop('execution_state')
    value['protected_requests']=[identity]
    raw=encode(value);Path(descriptor['path']).write_bytes(raw);descriptor['sha256']=hashlib.sha256(raw).hexdigest()
    previous=tmp_path/'previous';(previous/'work').mkdir(parents=True)
    request=previous/'REQUEST.json';request.write_bytes(encode(dict(protected_slots=[str(slot)])))
    (previous/'work/STATE.json').write_bytes(encode(dict(stages=dict(gap_plan=descriptor))))
    before={path:path.read_bytes()for path in (slot,request,Path(descriptor['path']))}
    observed=[];load=inputs.load_gap_plan
    def read(*args,**kwargs):
        result=load(*args,**kwargs);observed.append(result['protected_requests'][0]);return result
    monkeypatch.setattr(inputs,'load_gap_plan',read)
    result=inputs.prepare_update(config,pool['date'],tmp_path/'next-inputs',
        previous_requests=[str(request)],deadline=monotonic()+20)
    fixed=json.loads(Path(result['path']).read_bytes())
    assert observed==[dict(identity,execution_state='unknown')]
    assert str(slot)in fixed['protected_slots']
    assert all(path.read_bytes()==raw for path,raw in before.items())
    assert inputs.prepare_update(config,pool['date'],tmp_path/'next-inputs',
        previous_requests=[str(request)],deadline=monotonic()+20)==result


def test_large_plan_writer_descriptor_and_consumer_share_one_capacity(tmp_path):
    _slot,value=fixture(tmp_path)
    row=deepcopy(value['protected_requests'][0]);row['slot']=str(tmp_path/('long-reference-'+'x'*1000))
    value['protected_requests']=[row]*16000
    descriptor=plans.write_gap_plan(tmp_path/'large',value,deadline=monotonic()+15)
    assert 16777216 < Path(descriptor['path']).stat().st_size < plans.MAX_GAP_PLAN_BYTES
    loaded=plans.load_gap_plan(descriptor,deadline=monotonic()+15)
    assert len(loaded['protected_requests'])==16000 and loaded['tasks']==value['tasks']


def test_write_capacity_is_checked_before_marker_or_output_exists(tmp_path,monkeypatch):
    _slot,value=fixture(tmp_path)
    monkeypatch.setattr(plans,'MAX_GAP_PLAN_BYTES',len(encode(value))-1)
    with pytest.raises(ValueError,match='capacity'):
        plans.write_gap_plan(tmp_path/'small',value,deadline=monotonic()+5)
    assert not (tmp_path/'small').exists()


@pytest.mark.parametrize('change', ['outside','unordered','protected','requirements','exclusion'])
def test_plan_dates_and_price_mode_cannot_escape_original_contract(tmp_path,change):
    _slot,value=fixture(tmp_path)
    if change=='outside':
        value['tasks'][0].update(start_date='20261109',end_date='20261109',dates=['20261109'])
    elif change=='unordered':
        value['tasks'][0]['dates']=['20261106','20261106']
    elif change=='protected':
        value['protected_requests'][0]['arguments'].update(start_time='20261106',end_time='20261106')
    elif change=='requirements':
        value['required_adjustments']=['unqualified-mode']
    else:
        value['exclusions']=[dict(symbol='510300.SH',date='20260230',reason='before_listing')]
    with pytest.raises(ValueError):
        plans.write_gap_plan(tmp_path/'invalid',value,deadline=monotonic()+5)
    assert not (tmp_path/'invalid').exists()


def test_bad_digest_and_missing_original_slot_keep_marker_and_do_not_rebuild(tmp_path):
    slot,value=fixture(tmp_path)
    descriptor=plans.write_gap_plan(tmp_path/'candidate',value,deadline=monotonic()+5)
    with pytest.raises(ValueError):
        plans.load_gap_plan(dict(descriptor,sha256='c'*64),deadline=monotonic()+5)
    raw=Path(descriptor['path']).read_bytes();slot.unlink()
    with pytest.raises(plans.GapPlanReferenceError):restore(tmp_path/'candidate',value)
    assert Path(descriptor['path']).read_bytes()==raw


def test_restoration_checks_full_original_request_and_all_protected_paths(tmp_path):
    slot,value=fixture(tmp_path)
    plans.write_gap_plan(tmp_path/'candidate',value,deadline=monotonic()+5)
    changed=deepcopy(value);changed['protected_requests']=[]
    with pytest.raises(ValueError,match='input differs'):restore(tmp_path/'candidate',changed)
    original=dict(request_id=str(uuid4()),operation_id='market.history_prepare',arguments=value['protected_requests'][0]['arguments'])
    slot.write_bytes(encode(dict(request=original)))
    with pytest.raises(plans.GapPlanReferenceError):restore(tmp_path/'candidate',value)


def test_known_execution_state_cannot_be_downgraded_on_marker_adoption(tmp_path,monkeypatch):
    slot,value=fixture(tmp_path)
    from guanheng_qmt_shm import read_retention_client
    binding=dict(identity='fixed-original')
    original=dict(request_id=value['protected_requests'][0]['request_id'],operation_id='market.history_prepare',
                  arguments=value['protected_requests'][0]['arguments'])
    record=dict(request=original,binding=binding,result=dict(admitted_binding=binding,
                dispatch_binding=binding,result_binding=binding))
    monkeypatch.setattr(read_retention_client,'inspect_saved_result',lambda _record:dict(ok=True,data=dict(effect='call_returned')))
    slot.write_bytes(encode(record));value['protected_requests']=[plans.read_protected_request(slot,deadline=monotonic()+5)]
    assert value['protected_requests'][0]['execution_state']=='call_returned'
    plans.write_gap_plan(tmp_path/'candidate',value,deadline=monotonic()+5)
    record['result']['dispatch_binding']=None;slot.write_bytes(encode(record))
    with pytest.raises(plans.GapPlanReferenceError):restore(tmp_path/'candidate',value)


def test_restore_cancellation_and_original_deadline_leave_marker_unchanged(tmp_path):
    _slot,value=fixture(tmp_path)
    descriptor=plans.write_gap_plan(tmp_path/'candidate',value,deadline=monotonic()+5)
    before=Path(descriptor['path']).read_bytes()
    with pytest.raises(InterruptedError):plans.load_gap_plan(descriptor,deadline=monotonic()+5,cancelled=lambda:True)
    with pytest.raises(TimeoutError):plans.load_gap_plan(descriptor,deadline=monotonic()-1)
    assert Path(descriptor['path']).read_bytes()==before


def test_only_explicit_local_stage_can_adopt_earlier_complete_marker(tmp_path):
    _slot,value=fixture(tmp_path)
    root=tmp_path/'work';root.mkdir();old,new=uuid4().hex,uuid4().hex
    plans.write_gap_plan(root/('gap-plan-'+old),value,deadline=monotonic()+5)
    phase=dict(schema='guanheng.daily-immutable-stage.v1',name='gap-plan',attempts=[old,new],result=None)
    (root/'PHASE-gap-plan.json').write_bytes(encode(phase))
    called=[]
    def build(output):called.append(output);raise AssertionError('local plan rebuilt')
    descriptor=prepare_directory(root,'gap-plan','PLAN.json',build,lambda output:restore(output,value),recover_prior=True)
    assert not called and Path(descriptor['path']).parent.name=='gap-plan-'+old
    import json
    committed=json.loads((root/'PHASE-gap-plan.json').read_bytes())
    assert committed['attempts']==[old,new] and committed['result_attempt']==old
    assert prepare_directory(root,'gap-plan','PLAN.json',build,lambda output:restore(output,value),recover_prior=True)==descriptor


def test_default_stage_never_skips_later_unfinished_attempt(tmp_path):
    root=tmp_path/'work';root.mkdir();old,new=uuid4().hex,uuid4().hex
    previous=root/('facts-'+old);previous.mkdir();(previous/'catalog.json').write_bytes(b'known-old-local-marker')
    (root/'PHASE-facts.json').write_bytes(encode(dict(schema='guanheng.daily-immutable-stage.v1',
        name='facts',attempts=[old,new],result=None)))
    called=[]
    def build(output):called.append(output);raise InterruptedError('later responsibility retained')
    with pytest.raises(InterruptedError):
        prepare_directory(root,'facts','catalog.json',build,lambda _:pytest.fail('old marker crossed later attempt'))
    assert len(called)==1 and (previous/'catalog.json').read_bytes()==b'known-old-local-marker'


def test_local_reference_reads_are_bounded_ordered_and_joined(monkeypatch):
    lock=Lock();active=0;peak=0
    def read(index,**kwargs):
        nonlocal active,peak
        with lock:active+=1;peak=max(peak,active)
        try:
            sleep(.002*(index%3));return dict(request_id=str(index))
        finally:
            with lock:active-=1
    monkeypatch.setattr(plans,'read_protected_request',read)
    result=plans.collect_protected_requests(range(40),deadline=monotonic()+5)
    assert [row['request_id']for row in result]==list(map(str,range(40)))
    assert 1<=peak<=4 and active==0
    assert not any(t.name.startswith('daily-gap-reference')for t in threads())


def test_local_reference_cancel_joins_every_inflight_reader(monkeypatch):
    entered=Event();finished=[]
    def read(index,**kwargs):
        entered.set()
        try:
            while not kwargs['cancelled']():sleep(.001)
            raise InterruptedError('local read stopped')
        finally:finished.append(index)
    monkeypatch.setattr(plans,'read_protected_request',read)
    with pytest.raises(InterruptedError):
        plans.collect_protected_requests(range(100),deadline=monotonic()+5,cancelled=entered.is_set)
    assert 1<=len(finished)<=4
    assert not any(t.name.startswith('daily-gap-reference')for t in threads())


def test_local_reference_error_cancels_queue_preserves_error_and_joins(monkeypatch):
    failed=ValueError('original local error');finished=[]
    def read(index,**kwargs):
        try:
            if index==0:
                sleep(.01);raise failed
            while not kwargs['cancelled']():sleep(.001)
            raise InterruptedError('inflight closed')
        finally:finished.append(index)
    monkeypatch.setattr(plans,'read_protected_request',read)
    with pytest.raises(ValueError)as caught:
        plans.collect_protected_requests(range(100),deadline=monotonic()+5)
    assert caught.value is failed and len(finished)<=4
    assert not any(t.name.startswith('daily-gap-reference')for t in threads())
