"""常驻同owner的跨日补缺；保留真实采集/原ID客户端和来源证明，原生转换另有主链。"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

import pytest

sys.path.insert(0,str(Path(__file__).parent))
from msf_fixture import DAYS,ContentStore,FrozenFetch,QmtTransport,plan,write
from test_daily_owner import owner_fixture
from integrations.guanheng import daily_data_service as service
from integrations.guanheng import market_supplement_capture as capture
from integrations.guanheng.daily_data_update import _load,_save
from integrations.guanheng.market_supplement_store import MarketSupplementStore


def collect_at(plan_value,day,dates,work,objects,fetch,transport,previous=None):
    return capture.collect_supplement(plan_value,day,dates,work,objects=objects,fetch=fetch,
        qmt_transport=transport,calendar_coverage=(DAYS[0],DAYS[-1]),previous=previous,
        deadline=time.monotonic()+20)


def test_next_day_proxy_reads_only_missing_tail_and_keeps_receipt(tmp_path):
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch();transport=QmtTransport()
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    previous=collect_at(targets,DAYS[0],[DAYS[0]],tmp_path/'first',objects,fetch,transport)
    first=_load(previous)['rows'][0]
    current=collect_at(targets,DAYS[1],DAYS,tmp_path/'next',objects,fetch,transport,previous)
    rows=_load(current)['rows']
    assert rows[0]==first and len(rows)==2
    assert len(transport.sdk_calls)==4
    assert all(r['arguments']['start_date']==DAYS[1].replace('-','')
               and r['arguments']['end_date']==DAYS[1].replace('-','') for r in transport.sdk_calls[2:])
    assert {r['unit'] for r in rows}=={'unknown'}


def test_partial_proxy_partition_resume_keeps_every_original_request(tmp_path,monkeypatch):
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch();transport=QmtTransport(max_rows=1)
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    original=capture._save;interrupted=False
    def stop_after_first(path,value):
        nonlocal interrupted
        original(path,value)
        if path.name=='STATE.json' and len(value.get('rows',{}))==1 and not interrupted:
            interrupted=True;raise InterruptedError('after first partition committed')
    with monkeypatch.context() as local:
        local.setattr(capture,'_save',stop_after_first)
        with pytest.raises(InterruptedError):collect_at(targets,DAYS[1],DAYS,tmp_path/'work',objects,fetch,transport)
    identities=[r['request_id'] for r in transport.sdk_calls]
    assert len(identities)==2
    descriptor=collect_at(targets,DAYS[1],DAYS,tmp_path/'work',objects,fetch,transport)
    assert len(_load(descriptor)['rows'])==2
    assert len(transport.sdk_calls)==4 and [r['request_id'] for r in transport.sdk_calls[:2]]==identities


def test_pending_day_rolls_to_next_day_with_successful_facts_preserved(tmp_path,monkeypatch):
    """实际serve跨闭合日：前日未发布成功行进入新日完整目录；Native发布边界显式替身。"""
    config,*_=owner_fixture(tmp_path)
    config['schedule']['poll_seconds']=.1
    config['inputs']['supplement_facts']=plan(('etf_total_shares','SSE.510300'),('margin_balance','CN.MARGIN_REPORT'))
    descriptor=write(tmp_path/'daily.json',config)
    control_id=str(uuid4());controls=tmp_path/'controls';controls.mkdir();control=controls/control_id
    fetches=[];published=[];clocks=0
    objects=ContentStore(config['raw_store'])
    def calendar(value):return [dict(date=d,is_open=1) for d in DAYS],None
    monkeypatch.setattr('guanheng_app.observation.calendars.official_calendar',calendar)
    def prepare(configuration,day,directory,**kwargs):
        work=Path(directory);work.mkdir(exist_ok=True)
        _save(work/'INPUTS.json',dict(configuration=configuration,day=day,previous_requests=kwargs['previous_requests']))
        fetch=FrozenFetch(bad_day=DAYS[0] if day==DAYS[0] else None);fetches.append(fetch)
        prior=capture.prior_supplement_catalogs(None,config['directory'],work,day,objects=objects,check=lambda:None)
        transport=QmtTransport()
        try:catalog=collect_at(configuration['inputs']['supplement_facts'],day,DAYS,work/'supplement',objects,fetch,transport,prior)
        finally:transport.close();fetch.close()
        return write(work/'UPDATE.json',dict(day=day,supplement_facts=catalog))
    def publish(request,directory,**kwargs):
        with_store=MarketSupplementStore(request['supplement_facts'])
        try:with_store.verify_sources();published.append(with_store.catalog)
        finally:with_store.close()
        # 关闭同一个持续owner；不创建第二个调度器或变更运行环境。
        _save(control/'stop.json',dict(schema='guanheng.daily-data-stop.v1',control_id=control_id,deadline=time.monotonic()+10))
        return dict(current_sha256='e'*64,supplement_complete=True)
    started=time.monotonic()
    def clock():
        nonlocal clocks
        assert time.monotonic()-started<8, 'daily owner failed to publish bounded synthetic next day'
        clocks+=1
        return datetime.fromisoformat((DAYS[0] if clocks==1 else DAYS[1])+'T16:00:00+08:00')
    monkeypatch.setattr(service,'prepare_update',prepare)
    monkeypatch.setattr(service,'run_update',publish)
    service.serve(descriptor,control,control_id,clock=clock)
    index=json.loads((Path(config['directory'])/'INDEX.json').read_bytes())
    assert index[DAYS[0]]['state']=='failed' and index[DAYS[1]]['state']=='published'
    assert len(published)==1 and published[0]['complete'] and len(published[0]['rows'])==4
    old=json.loads((Path(config['directory'])/DAYS[0]/'inputs/supplement/STATE.json').read_bytes())['rows']
    old_margin=next(iter(old.values()))
    assert old_margin in published[0]['rows']
    assert not any(p.get('reportName')=='RPTA_WEB_MARGIN_DAILYTRADE' and DAYS[0] in p['filter'] for _,p in fetches[-1].calls)
    assert json.loads((control/'closed.json').read_bytes())['owner_closed'] is True


def test_source_date_at_1530_is_shared_with_daily_owner(monkeypatch):
    monkeypatch.setattr('guanheng_app.observation.calendars.official_calendar',
        lambda config:([dict(date=d,is_open=1) for d in DAYS],None))
    calendar=dict(coverage_start=DAYS[0],coverage_end=DAYS[-1])
    assert service.target_date(calendar,datetime.fromisoformat(DAYS[1]+'T15:29:59+08:00'))==DAYS[0]
    assert service.target_date(calendar,datetime.fromisoformat(DAYS[1]+'T15:30:00+08:00'))==DAYS[1]


def test_prior_success_proof_damage_blocks_reuse_before_new_source(tmp_path):
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch(bad_day=DAYS[0]);transport=QmtTransport()
    targets=plan(('etf_total_shares','SSE.510300'),('margin_balance','CN.MARGIN_REPORT'))
    task=tmp_path/'tasks';old=task/DAYS[0]/'inputs/supplement'
    with pytest.raises(capture.SupplementPending):collect_at(targets,DAYS[0],DAYS,old,objects,fetch,transport)
    write(task/'INDEX.json',{DAYS[0]:dict(state='failed',request=str(task/DAYS[0]/'REQUEST.json'))})
    state=json.loads((old/'STATE.json').read_bytes());row=next(iter(state['rows'].values()))
    objects.path(row['source_sha256']).write_bytes(b'corrupt')
    current=task/DAYS[1]/'inputs';current.mkdir(parents=True)
    with pytest.raises(ValueError):capture.prior_supplement_catalogs(None,task,current,DAYS[1],objects=objects,check=lambda:None)
    assert not (current/'SUPPLEMENT-PRIORS.json').exists()


def test_partial_refresh_once_after_0900_next_civil_day(tmp_path,monkeypatch):
    """晚到来源在次自然日09:00修订同市场日，partial再次发布后当日不空转。"""
    config,*_=owner_fixture(tmp_path)
    config['schedule']['poll_seconds']=.1
    config['inputs']['supplement_facts']=plan(('etf_total_shares','SSE.510300'),required=False)
    descriptor=write(tmp_path/'daily.json',config)
    control_id=str(uuid4());(tmp_path/'controls').mkdir();control=tmp_path/'controls'/control_id
    objects=ContentStore(config['raw_store']);published=[];clocks=0;attempts=[]
    monkeypatch.setattr('guanheng_app.observation.calendars.official_calendar',
        lambda value:([dict(date=d,is_open=1) for d in DAYS],None))
    def prepare(configuration,day,directory,**kwargs):
        attempts.append(day);root=Path(directory);root.mkdir(exist_ok=True)
        _save(root/'INPUTS.json',dict(configuration=configuration,day=day,previous_requests=kwargs['previous_requests']))
        fetch=FrozenFetch(bad_day=DAYS[-1]);transport=QmtTransport()
        try:catalog=collect_at(configuration['inputs']['supplement_facts'],day,DAYS,root/'supplement',objects,
                fetch,transport,published[-1] if published else None)
        finally:fetch.close();transport.close()
        return write(root/'UPDATE.json',dict(supplement_facts=catalog))
    def publish(request,directory,**kwargs):
        published.append(request['supplement_facts'])
        return dict(current_sha256='b'*64,supplement_complete=_load(request['supplement_facts'])['complete'])
    started=time.monotonic()
    def clock():
        nonlocal clocks
        assert time.monotonic()-started<8
        clocks+=1
        if clocks==1:return datetime.fromisoformat(DAYS[-1]+'T16:00:00+08:00')
        if clocks==2:return datetime.fromisoformat('2026-11-06T08:59:00+08:00')
        if clocks>=6:
            _save(control/'stop.json',dict(schema='guanheng.daily-data-stop.v1',control_id=control_id,deadline=time.monotonic()+10))
        return datetime.fromisoformat('2026-11-06T09:01:00+08:00')
    monkeypatch.setattr(service,'prepare_update',prepare);monkeypatch.setattr(service,'run_update',publish)
    service.serve(descriptor,control,control_id,clock=clock)
    assert attempts==[DAYS[-1],DAYS[-1]] and len(published)==2
    index=json.loads((Path(config['directory'])/'INDEX.json').read_bytes())[DAYS[-1]]
    assert index['state']=='published' and index['revision']==1 and len(index['history_requests'])==1
    assert index['supplement_attempt_date']=='2026-11-06' and index['supplement_complete'] is False


def test_supplement_pending_read_slots_join_original_discovery(tmp_path):
    from integrations.guanheng.daily_input_recovery import _slot_candidates
    root=tmp_path/'inputs';slots=root/'supplement/qmt-slots';slots.mkdir(parents=True)
    slot=slots/'000001.SH.p0001.json';slot.write_text('{}',encoding='utf8')
    original=dict(inputs=dict(connections=dict(batch={'fixture':'original-batch'})))
    assert (slot,original['inputs']['connections']['batch']) in list(_slot_candidates(root,original))


def test_price_first_current_survives_public_source_timeout(tmp_path,monkeypatch):
    """原价格发布边界先成功，随后公共预算超时只使完整任务失败，价格CURRENT保持。"""
    from guanheng_app.observation.source_fetch import SourceFailure
    config,*_=owner_fixture(tmp_path)
    config['inputs']['supplement_facts']['required']=False
    config['price_scope']=dict(baseline_reference=config['template']['security_reference'],
        reference_connection={},scope={},authorized_from='20261104',maximum_history_rows=2000)
    descriptor=write(tmp_path/'daily.json',config)
    current=Path(config['template']['publication_directory'])/'CURRENT.json'
    current.parent.mkdir(exist_ok=True);current.write_bytes(b'old verified price boundary')
    control_id=str(uuid4());(tmp_path/'controls').mkdir();control=tmp_path/'controls'/control_id
    order=[]
    import integrations.guanheng.daily_price_refresh as price
    def price_ready(configuration,day,directory,**kwargs):
        order.append('price_published')
        current.write_bytes(b'new verified price boundary')  # Native/CAS边界替身，完整数据发布另由owner主链测试。
        root=Path(directory);root.mkdir(parents=True)
        result=write(root/'prices.json',{})
        return dict(current_sha256='a'*64,price_result=result,continuation_required=False,auxiliary_observation_date=DAYS[0])
    def source_timeout(*args,**kwargs):
        order.append('public_timeout')
        raise SourceFailure('collection_timeout')
    monkeypatch.setattr(price,'price_refresh',price_ready)
    monkeypatch.setattr(service,'prepare_update',source_timeout)
    with pytest.raises(RuntimeError,match='one cycle failed'):
        service.serve(descriptor,control,control_id,once=True,as_of=DAYS[-1])
    assert order==['price_published','public_timeout']
    assert current.read_bytes()==b'new verified price boundary'
    state=json.loads((Path(config['directory'])/'INDEX.json').read_bytes())[DAYS[-1]]
    assert state['price_state']=='published' and state['state']=='failed'
    assert json.loads((control/'failure.json').read_bytes())['owner_closed'] is True


def test_stage_request_share_keeps_original_total_and_next_round_continues(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'),('margin_balance','CN.MARGIN_REPORT'),required=False)
    targets['max_requests']=2  # 本轮metadata+最新份额，融资/旧缺口留在后继轮次。
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch();transport=QmtTransport()
    original_max=fetch.budget.max_requests
    descriptor=collect_at(targets,DAYS[-1],DAYS,tmp_path/'first',objects,fetch,transport)
    first=_load(descriptor)
    assert fetch.budget.requests==2 and fetch.budget.max_requests==original_max
    assert len(first['rows'])==1 and first['rows'][0]['date']==DAYS[-1]
    assert first['complete'] is False and len(first['gaps'])==3
    # 未取消日更；新轮额度按原总账继续扣，seed行不重抓。
    targets=deepcopy(targets);targets['max_requests']=8
    result=collect_at(targets,DAYS[-1],DAYS,tmp_path/'next',objects,fetch,transport,descriptor)
    assert _load(result)['complete'] and len(_load(result)['rows'])==4
    assert first['rows'][0] in _load(result)['rows']
    assert fetch.budget.max_requests==original_max


def test_unmaterialized_request_keeps_original_input_slot_reference(tmp_path):
    from integrations.guanheng.daily_input_recovery import observe_input_reads
    # 只有INPUTS及尚未尝试原槽，外层REQUEST尚未写入；恢复禁止借机派发。
    root=tmp_path/'legacy/inputs';slot=root/'supplement/qmt-slots/000001.SH.json'
    slot.parent.mkdir(parents=True)
    slot.write_text('{"request":{}}',encoding='utf8')
    intent=write(root/'INPUTS.json',dict(day=DAYS[0],configuration=dict(inputs=dict(connections=dict(batch={}))),previous_requests=[]))
    state=dict(consumed=set(),pending=set(),checked={},slots={},roots=set(),discovery={},discovered=set())
    result=observe_input_reads({},state,target_day=DAYS[-1],deadline=time.monotonic()+2,cancelled=lambda:False,
                               prior_inputs=[intent])
    assert str(slot) in state['pending'] and result['pending']==1
    assert not (root.parent/'REQUEST.json').exists()


def test_proxy_plan_drift_rejected_before_unknown_original_is_reissued(tmp_path):
    from guanheng_qmt_shm.read_retention_client import RetainedReadPending
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch();transport=QmtTransport(lose_first=True)
    target=plan(('market_turnover_proxy','CN.SH_SZ'));work=tmp_path/'work'
    with pytest.raises(RetainedReadPending):collect_at(target,DAYS[-1],DAYS,work,objects,fetch,transport)
    assert len(transport.sdk_calls)==1
    state=json.loads((work/'STATE.json').read_bytes())
    state['proxy_plan'][0]['requests'][0]['arguments']['symbol']='600000.SH'
    _save(work/'STATE.json',state)
    with pytest.raises(ValueError,match='original arguments'):
        collect_at(target,DAYS[-1],DAYS,work,objects,fetch,transport)
    assert len(transport.sdk_calls)==1
