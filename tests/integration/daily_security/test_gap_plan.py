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
