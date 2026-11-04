"""统一WT消费者：正式更新主链完成后覆盖日期、版本、缺口与失败保旧。"""
import copy
from datetime import date,datetime,timedelta,timezone
from time import monotonic
from types import SimpleNamespace

import pytest

from guanheng_app.observation import collection,wt_breadth_source,wt_t2108_source
from guanheng_app.observation.breadth_models import ASHARE_METRICS
from guanheng_app.observation.collection_config import validate_configuration
from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.publication import adopt_snapshot
from guanheng_app.observation.refresh_models import source_window
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.schedule_policy import source_as_of
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure
from guanheng_app.observation.storage import digest,encode


def calendar(closed=()):
    start=date(2026,9,1);end=date(2026,11,10)
    days=[(start+timedelta(days=n)).isoformat() for n in range((end-start).days+1)
        if (start+timedelta(days=n)).weekday()<5 and (start+timedelta(days=n)).isoformat() not in closed]
    return dict(kind='official-exchange-calendar/v1',id='consumer-test-calendar',method='explicit test dates',evidence=[],
        coverage_start=start.isoformat(),coverage_end=end.isoformat(),
        verified_through=end.isoformat(),closed_dates=list(closed),verified_open_dates_sha256=digest(encode(days)))


def configuration():
    return dict(schema_version='guanheng.observation-sources.v1',timeout_seconds=30,max_days_per_batch=40,
        allowed_hosts=[],models=dict(calendars=dict(cn=calendar())),
        schedule=dict(timezone='Asia/Shanghai',times=['09:00','17:30','21:00'],poll_seconds=2,date_policy='source-aware-v1'),
        retry_seconds=60,max_window_attempts=2,budget=dict(seconds=60,max_requests=792,max_bytes=268435456,response_bytes=16777216),
        sources=[dict(id='wt.breadth',kind='wt_breadth',date_policy='cn-prior-day',overlap_days=7,
            datasets=list(ASHARE_METRICS),tables=['source.ashare_day_universe']),
            dict(id='wt.t2108',kind='wt_t2108',date_policy='cn-prior-day',overlap_days=0,
                datasets=['t2108.ashare'],tables=['source.t2108_ashare_universe'])])


@pytest.mark.parametrize('clock,expected',[
    ('2026-11-04T09:00:00+08:00','2026-11-03'),
    ('2026-11-04T17:30:00+08:00','2026-11-03'),
    ('2026-11-04T21:00:00+08:00','2026-11-03'),
    ('2026-11-02T09:00:00+08:00','2026-10-30'),
])
def test_all_windows_follow_producer_previous_trading_day(clock,expected):
    config=configuration();validate_configuration(config)
    assert source_as_of(config['sources'][0],clock[:10],config,datetime.fromisoformat(clock))==expected


def test_official_holiday_and_other_source_clock_remain_independent():
    config=configuration();config['models']['calendars']['cn']=calendar(['2026-11-03'])
    clock=datetime.fromisoformat('2026-11-04T17:30:00+08:00')
    assert source_as_of(config['sources'][0],'2026-11-04',config,clock)=='2026-11-02'
    assert source_as_of(dict(date_policy='cn-closed-day'),'2026-11-04',config,clock)=='2026-11-04'


@pytest.mark.parametrize('field,value',[('symbols',['sh000001']),('window_mode','report_latest'),('input_directory','E:/fixture')])
def test_wt_source_cannot_acquire_another_price_or_capture_owner(field,value):
    config=configuration();config['sources'][0][field]=value
    with pytest.raises(ObservationError):validate_configuration(config)


def test_prior_day_policy_is_limited_to_its_actual_wt_owner():
    config=configuration();config['sources']=[dict(id='disclosure',kind='disclosure',date_policy='cn-prior-day',datasets=[],tables=[])]
    with pytest.raises(ObservationError):validate_configuration(config)


def test_live_40_day_batch_advances_and_t2108_recovers_long_stoppage():
    config=configuration()
    assert source_window('2026-11-02','2026-11-03',config['sources'][0],config)==('2026-10-26','2026-11-03')
    assert source_window('2026-09-01','2026-11-03',config['sources'][1],config)==('2026-09-01','2026-11-03')


def fetch_at(path):
    reader=build_reader(path);reader.repository.initialize()
    fetch=SimpleNamespace(objects=reader.objects,records=[],timeout=30,budget=CollectionBudget(monotonic()+20))
    return reader,fetch


@pytest.mark.parametrize('as_of,expected',[('2026-11-04','2026-11-03'),('2026-10-29','2026-10-29')])
def test_manual_selected_date_and_failed_read_keep_original_publication(tmp_path,monkeypatch,as_of,expected):
    reader,_=fetch_at(tmp_path)
    manifest=dict(schema_version='market-observation/1',published_at='2026-10-29T00:00:00+00:00',
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    previous=digest(encode(manifest));adopt_snapshot(reader,manifest,previous,None,monotonic()+10)
    calls=[]
    def unavailable(fetch,source,start,end,client_factory,*,calendar,snapshot_date):
        calls.append((end,snapshot_date));raise SourceFailure('wt_market_snapshot_price_differs')
    monkeypatch.setattr(collection,'wt_breadth_history',unavailable)
    run=collection.refresh(reader,configuration(),as_of=as_of,deadline=monotonic()+30,source_ids=['wt.breadth'],
        now=datetime(2026,11,4,1,tzinfo=timezone.utc),market_client_factory=lambda seconds:None)
    assert calls==[(expected,expected)]
    assert run['status']=='failed' and run['sources'][0]['error_code']=='wt_market_snapshot_price_differs'
    assert reader.repository.current()==previous and reader.repository.runs()[0]['previous_snapshot']==previous


@pytest.mark.parametrize('provider',[wt_breadth_source,wt_t2108_source])
def test_wrong_snapshot_date_stops_before_any_price_request(tmp_path,provider):
    _,fetch=fetch_at(tmp_path)
    client=SimpleNamespace(source_market_snapshot_query=lambda day:dict(status=dict(code='Ok'),data=dict(observation_date='2026-10-29')))
    kwargs=dict(calendar=calendar())
    if provider is wt_breadth_source:kwargs['snapshot_date']='2026-10-30'
    with pytest.raises(SourceFailure,match='wt_market_snapshot_date_differs'):
        provider.history(fetch,{},'2026-10-30','2026-10-30',lambda seconds:client,**kwargs)
    assert fetch.budget.requests==1


@pytest.mark.parametrize('provider',[wt_breadth_source,wt_t2108_source])
def test_price_from_another_snapshot_is_rejected_before_calculation(tmp_path,provider):
    _,fetch=fetch_at(tmp_path);members=['SSE.600001'];sid='1'*64
    snapshot=dict(observation_date='2026-10-30',members=members,snapshot_id=sid)
    facts=dict(members=members)
    adjustment='none' if provider is wt_breadth_source else 'front_ratio'
    bad=dict(results=[dict(symbol=members[0],status=dict(code='Ok'),data=dict(
        source_snapshot_id='2'*64,metadata=dict(adjustment=adjustment),bars=[]))])
    client=SimpleNamespace(source_market_snapshot_query=lambda day:dict(status=dict(code='Ok'),data=snapshot),
        source_day_facts_query=lambda day,identity:dict(status=dict(code='Ok'),data=facts),
        source_daily_history_batch_query=lambda request:dict(status=dict(code='Ok'),data=bad))
    kwargs=dict(calendar=calendar())
    if provider is wt_breadth_source:kwargs['snapshot_date']='2026-10-30'
    with pytest.raises(SourceFailure,match='wt_market_snapshot_price_differs'):
        provider.history(fetch,{},'2026-10-30','2026-10-30',lambda seconds:client,**kwargs)


def test_t2108_preserves_stale_and_insufficient_samples_and_snapshot_binding(tmp_path):
    _,fetch=fetch_at(tmp_path);seen=[];sid='1'*64
    snapshot=dict(observation_date='2026-10-30',members=['SSE.600001','SSE.600002','SZSE.000001'],snapshot_id=sid,
        source_kind='actual-qmt',source_received_at='2026-10-30T08:00:00Z',
        provenance=dict(source_binding_sha256='2'*64,universe_sha256='3'*64))
    def batch(request):
        seen.append(copy.deepcopy(request));results=[]
        for index,symbol in enumerate(request['symbols']):
            end=date(2026,10,30)-timedelta(days=int(index==2));count=39 if index==1 else 40
            bars=[dict(date=int((end-timedelta(days=n)).strftime('%Y%m%d')),close=12 if n==0 else 10) for n in reversed(range(count))]
            results.append(dict(symbol=symbol,status=dict(code='Ok'),data=dict(source_snapshot_id=sid,metadata=dict(adjustment='front_ratio'),bars=bars)))
        return dict(status=dict(code='Ok'),data=dict(results=results))
    client=SimpleNamespace(source_market_snapshot_query=lambda day:dict(status=dict(code='Ok'),data=snapshot),source_daily_history_batch_query=batch)
    output=wt_t2108_source.history(fetch,{},'2026-10-30','2026-10-30',lambda seconds:client,calendar=calendar())
    row=output['t2108.ashare'][0]
    assert (row['eligible_count'],row['above_count'],row['insufficient_count'],row['stale_count'])==(1,1,1,1)
    assert row['above_sma40_pct']==100 and row['market_above_sma40_pct'] is None and row['available_at'] is None
    assert seen[0]['snapshot_id']==sid and seen[0]['limit']==40 and seen[0]['adjustment']=='front_ratio'
    assert fetch.budget.requests==2
