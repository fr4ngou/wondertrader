"""长窗口属于原数据owner：真实Source另有主链，合成故障定位恢复和整档选择。"""
from copy import deepcopy
import hashlib
from pathlib import Path
import time

import pytest

from integrations.guanheng import daily_strategy_history as history
from integrations.guanheng.daily_data_update import _save, _load, _descriptor
from integrations.guanheng.market_generation import encode


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);_save(path,value);return _descriptor(path)


def setup_owner(tmp_path,monkeypatch):
    """模拟两日已上市ETF；协议层替身不改变Source/HPR责任恢复接口。"""
    calendar=write(tmp_path/'calendar.json',dict(coverage_start='2026-11-05',coverage_end='2026-11-06',closed_dates=[]))
    reference=write(tmp_path/'reference.json',{})
    request=dict(policy={'symbols':['SSE.510300'],'from':'20261105','seconds':2},day='2026-11-06',
        calendar=calendar,reference=reference,connections={'batch':{},'hpr':{}},protected_slots=[],
        source_kind='sdk-synthetic',snapshot_id='a'*64,previous_requests=[])
    monkeypatch.setattr('guanheng_app.observation.calendars.official_calendar',
        lambda c:([dict(date='2026-11-05',is_open=1),dict(date='2026-11-06',is_open=1)],None))
    class Reference:
        def __init__(self,*args):pass
        def security(self,*args):return dict(listed_on='2020-01-01',expires_on=None)
        def close(self):pass
    monkeypatch.setattr(history,'SecurityReference',Reference)
    coverage={'SSE.510300':{basis:dict(state='observed',actual_rows=2,missing_dates=[])for basis in('none','front_ratio')}}
    monkeypatch.setattr(history,'_coverage',lambda *a:deepcopy(coverage))
    return request,coverage


def fake_capture(request,directory,connection,**kwargs):
    root=Path(directory);root.mkdir(exist_ok=True)
    path=root/'manifest.json'
    if path.exists():assert _load(_descriptor(path))['request']==request
    else:write(path,dict(request=request))
    return dict(directory=str(root),sha256=_descriptor(path)['sha256'])


def test_whole_window_ready_and_same_intent_restores_without_source(tmp_path,monkeypatch):
    request,_=setup_owner(tmp_path,monkeypatch);calls=[]
    def capture(*args,**kwargs):calls.append(deepcopy(args[0]));return fake_capture(*args,**kwargs)
    monkeypatch.setattr(history,'capture_price_window',capture)
    root=tmp_path/'owner';result=history.prepare_strategy_history(request,root,deadline=time.monotonic()+5,cancelled=lambda:False)
    assert _load(result)['state']=='ready' and not _load(result)['continuation_required']
    assert calls[0]['start_date']=='20261105' and calls[0]['max_rows']==2
    assert history.prepare_strategy_history(request,root,deadline=time.monotonic()+5,cancelled=lambda:False)==result
    assert len(calls)==1


def test_source_budget_keeps_original_capture_uuid_and_next_revision_continues(tmp_path,monkeypatch):
    request,_=setup_owner(tmp_path,monkeypatch);calls=[]
    def capture(req,root,*args,**kwargs):
        calls.append(req['capture_id'])
        if len(calls)==1:raise TimeoutError('synthetic optional observation budget')
        return fake_capture(req,root,*args,**kwargs)
    monkeypatch.setattr(history,'capture_price_window',capture)
    old=tmp_path/'old';root=old/'work/prices/sh';root.parent.mkdir(parents=True)
    write(old/'REQUEST.json',{'owner':'synthetic'})
    first=history.prepare_strategy_history(request,root,deadline=time.monotonic()+5,cancelled=lambda:False)
    assert _load(first)['state']=='source_budget_pending' and _load(first)['continuation_required']
    revised=deepcopy(request);revised['previous_requests']=[str(old/'REQUEST.json')]
    second=history.prepare_strategy_history(revised,tmp_path/'next',deadline=time.monotonic()+5,cancelled=lambda:False)
    assert _load(second)['state']=='ready' and calls[0]==calls[1]
    assert _load(second)['workflow']==_descriptor(root/'REQUEST.json')


def test_late_normative_facts_requalify_original_pending_source_instead_of_using_first_policy(tmp_path,monkeypatch):
    """旧原槽已固定；后到停牌/日历/资料各代留证，新资格核同一Source结果。"""
    request,_=setup_owner(tmp_path,monkeypatch);calls=[]
    from integrations.guanheng.source_history_transport import SourcePending
    def capture(req,root,*args,**kwargs):
        calls.append(req['capture_id'])
        if len(calls)==1:
            write(Path(root)/'slots/original.json',{'synthetic_original_request_id':req['capture_id']})
            raise SourcePending('synthetic original receipt unavailable')
        return fake_capture(req,root,*args,**kwargs)
    monkeypatch.setattr(history,'capture_price_window',capture)
    old=tmp_path/'old';root=old/'work/prices/sh';root.parent.mkdir(parents=True)
    write(old/'REQUEST.json',{'owner':'synthetic'})
    first=history.prepare_strategy_history(request,root,deadline=time.monotonic()+5,cancelled=lambda:False)
    old_request_body=(root/'REQUEST.json').read_bytes()
    assert _load(first)['state']=='pending_source'
    revised=deepcopy(request);revised['previous_requests']=[str(old/'REQUEST.json')]
    revised['calendar']=write(tmp_path/'new-calendar.json',dict(coverage_start='2026-11-05',coverage_end='2026-11-06',closed_dates=[],revision='corrected'))
    revised['reference']=write(tmp_path/'new-reference.json',{'listed_on':'2026-11-05'})
    revised['policy']['seconds']=3
    revised['policy']['trading_exceptions']=write(tmp_path/'new-exceptions.json',{})
    monkeypatch.setattr(history,'load_trading_exceptions',lambda d:{('SSE.510300','2026-11-06'):dict(no_trade=True)}if d==revised['policy']['trading_exceptions']else{})
    viewed=[]
    class Reference:
        def __init__(self,r,c):viewed.append((r,c))
        def close(self):pass
    monkeypatch.setattr(history,'SecurityReference',Reference)
    def qualified(cache,ref,cal,policy,day,exceptions,*args):
        assert cal['revision']=='corrected' and exceptions=={('SSE.510300','2026-11-06'):dict(no_trade=True)}
        return {'SSE.510300':{basis:dict(state='observed',actual_rows=1,missing_dates=[])for basis in('none','front_ratio')}}
    monkeypatch.setattr(history,'_coverage',qualified)
    second=_load(history.prepare_strategy_history(revised,tmp_path/'new',deadline=time.monotonic()+5,cancelled=lambda:False))
    assert second['state']=='ready' and calls[0]==calls[1]
    assert viewed==[(revised['reference'],revised['calendar'])]
    assert second['qualification']==dict(calendar=revised['calendar'],reference=revised['reference'],
        trading_exceptions=revised['policy']['trading_exceptions'])
    assert (root/'REQUEST.json').read_bytes()==old_request_body


def test_late_hpr_changes_readback_generation_without_reusing_stale_snapshot(tmp_path,monkeypatch):
    """首轮HPR未知但回读已结束；晚到返回后必须新回读，不能复用旧manifest授覆盖。"""
    request,coverage=setup_owner(tmp_path,monkeypatch)
    for row in coverage['SSE.510300'].values():row['missing_dates']=['20261106'];row['actual_rows']=1
    import integrations.guanheng.daily_gap_update as gaps
    import integrations.guanheng.daily_gap_plan as plans
    import integrations.guanheng.source_history_transport as transport
    import guanheng_qmt_shm.market_daily_preparation as preparation
    counter={'advances':0};captures=[]
    def capture(req,root,*args,**kwargs):
        captures.append((str(root),req['capture_id']))
        return fake_capture(req,root,*args,**kwargs)
    monkeypatch.setattr(history,'capture_price_window',capture)
    monkeypatch.setattr(gaps,'prepare_gap_plan',lambda c,r,s,o,**k:write(o/'PLAN.json',{'tasks':[{'index':0}]}))
    monkeypatch.setattr(plans,'restore_gap_plan',lambda p,**k:_descriptor(p))
    monkeypatch.setattr(plans,'load_gap_plan',lambda p,**k:_load(p))
    def advance(plan,directory,owner,**kwargs):
        counter['advances']+=1;state='pending'if counter['advances']==1 else'call_returned'
        work=Path(directory);work.mkdir(exist_ok=True)
        write(work/'preparation/000000.json',{'request_id':'retained-source-id'})
        row=dict(index=0,state=state,request_id='retained-source-id')
        write(work/'observations/000000.json',dict(row=row))
        return dict(plan_sha256=plan['sha256'],rows=[row])
    monkeypatch.setattr(gaps,'advance_gap_plan',advance)
    monkeypatch.setattr(gaps,'freeze_gap_progress',lambda p,v,*a,**k:deepcopy(v))
    class Transport:
        def __init__(self,*a,**k):pass
        def close(self):pass
    monkeypatch.setattr(transport,'BoundHistorySource',Transport)
    monkeypatch.setattr(preparation,'MarketDailyPreparation',lambda *a,**k:None)
    old=tmp_path/'old';root=old/'work/prices/sh';root.parent.mkdir(parents=True)
    write(old/'REQUEST.json',{'owner':'synthetic'})
    first=history.prepare_strategy_history(request,root,deadline=time.monotonic()+5,cancelled=lambda:False)
    assert _load(first)['state']=='pending_source'
    first_readback=next((root/'work/rb').iterdir())/'capture/manifest.json';first_body=first_readback.read_bytes()
    # 原缓存仍缺一天，HPR返回后的新回读才补到该日。
    def live_coverage(*args):
        result=deepcopy(coverage)
        if counter['advances']>=2 and len(captures)>=4:
            for row in result['SSE.510300'].values():row['missing_dates']=[];row['actual_rows']=2
        return result
    monkeypatch.setattr(history,'_coverage',live_coverage)
    revised=deepcopy(request);revised['previous_requests']=[str(old/'REQUEST.json')]
    second=history.prepare_strategy_history(revised,tmp_path/'next',deadline=time.monotonic()+5,cancelled=lambda:False)
    assert _load(second)['state']=='ready',_load(second)
    rounds=list((root/'work/rb').iterdir())
    assert len(rounds)==2 and first_readback.read_bytes()==first_body
    readback_ids=[identifier for path,identifier in captures if 'rb'in path]
    assert len(readback_ids)==2 and len(set(readback_ids))==2
    assert len(history.strategy_slots([old/'REQUEST.json']))==1
    assert len(list(history.strategy_prior_plans([old/'REQUEST.json'])))==1


def test_optional_failure_and_global_cancellation_keep_different_semantics(tmp_path,monkeypatch):
    request,_=setup_owner(tmp_path,monkeypatch)
    def missing(*a,**k):raise ValueError('synthetic malformed optional capture')
    monkeypatch.setattr(history,'capture_price_window',missing)
    descriptor=history.prepare_strategy_history(request,tmp_path/'bad',deadline=time.monotonic()+5,cancelled=lambda:False)
    assert _load(descriptor)['state']=='invalid_optional_history' and _load(descriptor)['cache']is None
    with pytest.raises(InterruptedError):
        history.prepare_strategy_history(request,tmp_path/'stopped',deadline=time.monotonic()+5,cancelled=lambda:True)


@pytest.mark.parametrize('change',[lambda p:p.update(seconds=0),lambda p:p.update(seconds=float('nan')),
    lambda p:p.update(symbols=['SSE.510300','SSE.510300']),lambda p:p.update({'from':'20260230'})])
def test_strategy_configuration_rejects_invalid_unit_or_identity(change):
    value=dict(symbols=['SSE.510300'],**{'from':'20190101'});change(value)
    with pytest.raises(ValueError):history.validate_strategy_history(value)


def test_front_chooses_complete_hot_reference_and_retains_unselected_and_incomplete(tmp_path,monkeypatch):
    from integrations.guanheng import daily_front_archive as front
    def item(dates,value):return {'status':'observed','data':{str(d):dict(open=value,high=value,low=value,close=value,volume=5.,amount=7.)for d in dates}}
    ordinary={'510300.SH':item([20261106],2),'510050.SH':item([20261106],4)}
    hot={'510300.SH':item([20261105,20261106],3),'510050.SH':item([20261105,20261106],6)}
    old={s:{d:(dict(date=d,open=v,high=v,low=v,close=v,volume=5.,amount=7.),{'reference':'old'})for d in(20261105,20261106)}for s,v in[('SSE.510300',1),('SSE.510050',4),('SZSE.159780',8)]}
    monkeypatch.setattr(front,'load_price_capture',lambda c:c)
    monkeypatch.setattr(front,'capture_metadata',lambda m,sha,b:{'reference':sha})
    monkeypatch.setattr(front,'price_batches',lambda c,m,**k:iter([(None,hot if c['sha256']=='b'*64 else ordinary)]))
    monkeypatch.setattr(front,'read_price_history',lambda m,s,b,**k:old[s])
    captured={}
    def prepare(rows,metadata,out,*a,**kwargs):
        captured.update(rows=rows,provenance=kwargs['provenance']);return write(out/'archive.json',{'synthetic':True})
    monkeypatch.setattr(front,'prepare_daily_archive',prepare)
    previous=write(tmp_path/'old.json',{'entries':[{'symbol':s,'provenance':[{'metadata':{'adjustment':'front_ratio'}}]}for s in old]})
    inputs=write(tmp_path/'inputs.json',{'cache':{'directory':'ordinary','sha256':'a'*64}})
    result=front.prepare_front_archive(inputs,None,[previous],tmp_path/'front',{'path':'unused','sha256':'a'*64},
        deadline=time.monotonic()+5,maximum_history_rows=10000,cancelled=lambda:False,
        strategy_capture={'directory':'hot','sha256':'b'*64},strategy_coverage={
            'SSE.510300':{'front_ratio':dict(missing_dates=[],actual_rows=2)},
            'SSE.510050':{'front_ratio':dict(missing_dates=['20261104'],actual_rows=2)}})
    assert set(captured['rows'])==set(old)
    assert {r['close']for r in captured['rows']['SSE.510300']}=={3}
    assert captured['provenance']['SSE.510300'][0]['metadata']=={'reference':'b'*64}
    assert {r['close']for r in captured['rows']['SSE.510050']}=={4}
    assert {r['close']for r in captured['rows']['SZSE.159780']}=={8}
    assert result['securities']['SSE.510050']['selected_capture']=='retained'


def test_continuation_reads_hot_fixed_observation_even_when_today_native_is_available(tmp_path):
    from integrations.guanheng.daily_price_continuation import requires_price_continuation
    result=dict(inputs=None,securities={})
    hot=write(tmp_path/'hot.json',dict(continuation_required=True))
    assert requires_price_continuation(dict(result,strategy_history=hot))
    write(tmp_path/'done.json',dict(continuation_required=False))
    assert not requires_price_continuation(dict(result,strategy_history=_descriptor(tmp_path/'done.json')))


@pytest.mark.parametrize('hot_failure',[False,True])
def test_price_update_full_main_chain_runs_ordinary_first_and_binds_hot_to_both_archives(tmp_path,monkeypatch,hot_failure):
    """运行真正price_update/长窗口owner；Native编码和已验证Source通信在此为明确替身。"""
    from integrations.guanheng import daily_price_update as update
    request,_=setup_owner(tmp_path,monkeypatch);order=[]
    def capture(*a,**k):
        order.append('hot')
        if hot_failure:raise ValueError('synthetic optional source invalid')
        return fake_capture(*a,**k)
    monkeypatch.setattr(history,'capture_price_window',capture)
    symbols=request['policy']['symbols'];identities={s:dict(security_type='etf')for s in symbols}
    universe=write(tmp_path/'universe.json',dict(securities=identities))
    scope=write(tmp_path/'scope.json',dict(universe=universe,securities=identities,
        reference=request['reference'],observation_date=request['day'],source_members=symbols,groups=[]))
    source=write(tmp_path/'source.json',dict(mode='synthetic-owner-boundary'))
    maintenance=dict(scope=scope,current_configuration=source,snapshot_id='a'*64,
        calendar=request['calendar'],connections=request['connections'],protected_slots=[],authorized_from='20261106',
        source_kind='sdk-synthetic',maximum_history_rows=10000,previous_archives=[],helper={},
        strategy_history=request['policy'],strategy_history_previous_requests=[])
    def ordinary(req,root,**kwargs):
        order.append('ordinary');return write(root/'INPUTS.json',dict(cache={'ordinary':True},securities={s:dict(
            reason='available',source_state='observed')for s in symbols}))
    monkeypatch.setattr(update,'prepare_price_inputs',ordinary)
    class Market:
        def call(self,request):return dict(status={'code':'Ok'},data=dict(archive={'last_date':20261106},bars=[{'date':20261106}]))
        def close(self):pass
    class Reference:
        def __init__(self,*args):pass
        def assess(self,*args):return dict(no_trade_dates=[],before_listing_dates=[],after_expiry_dates=[],missing_dates=[])
        def close(self):pass
    monkeypatch.setattr(update,'create_native_source_market',lambda c:Market())
    monkeypatch.setattr(update,'SecurityReference',Reference)
    monkeypatch.setattr(update,'_catalog',lambda b:{'native_reader':{}})
    monkeypatch.setattr(update,'compose_static_archive',lambda b,a,r,**k:dict(base=b,archive=a))
    observations={}
    def raw(inputs,market,old,out,*args,**kwargs):
        observations['raw']=kwargs['additional_captures'];return write(out/'archive.json',{'boundary':'full-raw'})
    monkeypatch.setattr(update,'materialize_price_archive',raw)
    def front(inputs,market,old,out,*args,**kwargs):
        observations['front']=kwargs['strategy_capture']
        value=dict(archive=write(out/'data/archive.json',{'boundary':'full-front'}))
        write(out/'RESULT.json',value);return value
    monkeypatch.setattr(update,'prepare_front_archive',front)
    result=_load(update.prepare_price_update(maintenance,None,source,tmp_path/'main',deadline=time.monotonic()+10,cancelled=lambda:False))
    hot=_load(result['strategy_history'])
    assert order==['ordinary','hot'] and hot['state']==('invalid_optional_history'if hot_failure else'ready')
    assert observations['raw']==(()if hot_failure else(hot['cache'],)) and observations['front']==hot['cache']
    assert len(result['additional_archives'])==2 and result['securities']['SSE.510300']['target_readable']


def test_raw_hot_only_fills_missing_dates_and_preserves_ordinary_values(tmp_path,monkeypatch):
    from integrations.guanheng import daily_price_archive as raw
    bar=lambda v:dict(open=v,high=v,low=v,close=v,volume=2.,amount=9.)
    ordinary={'510300.SH':{'data':{'20261106':bar(2)}}}
    hot={'510300.SH':{'data':{'20261105':bar(3),'20261106':bar(4)}}}
    monkeypatch.setattr(raw,'load_price_capture',lambda c:c)
    monkeypatch.setattr(raw,'capture_metadata',lambda m,sha,b:{'reference':sha})
    monkeypatch.setattr(raw,'price_batches',lambda c,m,**k:iter([(None,hot if c['sha256']=='b'*64 else ordinary)]))
    got={}
    def merge(market,rows,metadata,out,*args,**kwargs):
        got.update(rows=rows,parts=kwargs['addition_provenance']);return write(out/'archive.json',{'synthetic':True})
    monkeypatch.setattr(raw,'merge_original_price_rows',merge)
    inputs=write(tmp_path/'input.json',{'schema':'guanheng.daily-price-input-result.v1','cache':{'directory':'ordinary','sha256':'a'*64}})
    raw.materialize_price_archive(inputs,None,[],tmp_path/'raw',{'path':'unused','sha256':'a'*64},{},
        deadline=time.monotonic()+5,additional_captures=({'directory':'hot','sha256':'b'*64},))
    assert [(r['date'],r['close'])for r in got['rows']['SSE.510300']]==[(20261105,3),(20261106,2)]
    assert [p['metadata']['reference']for p in got['parts']['SSE.510300']]==['b'*64,'a'*64]


def test_no_trade_evidence_is_bound_and_only_excludes_that_security_day(tmp_path,monkeypatch):
    from integrations.guanheng.price_trading_exceptions import load_trading_exceptions
    from integrations.guanheng.daily_gap_update import prepare_gap_plan
    from guanheng_qmt_shm import analysis_batch_source as sdk
    raw=tmp_path/'original.body';raw.write_bytes(b'synthetic primary disclosure, not actual production evidence')
    evidence=dict(path=str(raw),sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),bytes=raw.stat().st_size,
        url='https://www.sse.com.cn/synthetic.pdf',status=200,received_at='2026-11-06T10:00:00Z')
    descriptor=write(tmp_path/'exceptions.json',dict(schema='guanheng.price-trading-exceptions.v1',records=[
        dict(symbol='SSE.510300',date='2026-11-06',no_trade=True,evidence=[evidence])]))
    exceptions=load_trading_exceptions(descriptor)
    assert set(exceptions)=={('SSE.510300','2026-11-06')}
    request=dict(symbols=['510050.SH','510300.SH'],start_date='20261105',end_date='20261106')
    manifest=dict(request=request,comparison={s:dict(common_dates=['20261105'])for s in request['symbols']})
    root=tmp_path/'capture';write(root/'manifest.json',manifest)
    monkeypatch.setattr(sdk,'read_capture',lambda r:deepcopy(manifest))
    class Reference:
        _calendar=dict(coverage_start='2026-11-05',coverage_end='2026-11-06',closed_dates=[])
        def security(self,*args):return dict(listed_on='2020-01-01',expires_on=None)
    plan=_load(prepare_gap_plan(dict(directory=str(root),sha256=_descriptor(root/'manifest.json')['sha256']),
        Reference(),dict(snapshot_id='a'*64,observation_date='2026-11-06'),tmp_path/'plan',
        authorized_from='20261105',authorized_to='20261106',deadline=time.monotonic()+5,trading_exceptions=exceptions))
    assert [(t['symbol'],t['dates'])for t in plan['tasks']]==[('510050.SH',['20261106'])]
    assert plan['exclusions']==[dict(symbol='510300.SH',date='20261106',reason='official_security_no_trade')]
    raw.write_bytes(b'changed')
    with pytest.raises(ValueError):load_trading_exceptions(descriptor)


def test_invalid_manifest_never_reenters_native_through_optional_fallback(tmp_path,monkeypatch):
    request,_=setup_owner(tmp_path,monkeypatch)
    def wrong(req,root,*args,**kwargs):
        bad=dict(req,capture_id='different-original-id');fake_capture(bad,root,*args,**kwargs)
        raise ValueError('original manifest request differs')
    monkeypatch.setattr(history,'capture_price_window',wrong)
    monkeypatch.setattr(history,'load_price_capture',lambda d:_load(_descriptor(Path(d['directory'])/'manifest.json')))
    result=_load(history.prepare_strategy_history(request,tmp_path/'owner',deadline=time.monotonic()+5,cancelled=lambda:False))
    assert result['state']=='invalid_optional_history' and result['cache']is None


def test_real_profile_byte_limit_is_resource_pending_not_business_unsupported(tmp_path,monkeypatch):
    from integrations.guanheng import daily_price_capture as capture
    from types import SimpleNamespace
    closed=[];called=[]
    class Transport:
        def __init__(self,*a,**k):pass
        def close(self):closed.append(True)
    def batch(*a,**k):
        metadata=dict(profile=dict(operation_profiles={'market.market_data':{'limits':dict(
            max_rows=4096,max_calendar_days=3660,max_data_bytes=520192,max_symbols=32)}}))
        return SimpleNamespace(client=SimpleNamespace(metadata=lambda **k:metadata),capture=lambda *a,**k:called.append(True))
    monkeypatch.setattr(capture,'BoundHistorySource',Transport)
    monkeypatch.setattr(capture,'DailyBatchAnalysisSource',batch)
    with pytest.raises(capture.PriceWindowResource,match='source_result_bytes_requires_partition'):
        capture.capture_price_window(dict(symbols=['510300.SH'],start_date='20190101',end_date='20261106',max_rows=3000),
            tmp_path/'capture',{},deadline=time.monotonic()+5,cancelled=lambda:False,verify_resources=True)
    assert closed==[True] and called==[]
