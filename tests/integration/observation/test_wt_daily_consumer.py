"""统一WT消费者：正式更新主链完成后覆盖日期、版本、缺口与失败保旧。"""
import copy
from datetime import date,datetime,timedelta,timezone
from time import monotonic
from types import SimpleNamespace

import pytest
from guanheng_market_client import MarketHTTPError, MarketUnavailable

from guanheng_app.observation import broker_heat,collection,etf_flow,ipo_supply,market_structure_source,wt_breadth_source,wt_t2108_source
from guanheng_app.observation.breadth_models import ASHARE_METRICS
from guanheng_app.observation.collection_config import validate_configuration
from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.data_repair import _coverage
from guanheng_app.observation.publication import adopt_snapshot
from guanheng_app.observation.refresh_models import source_window
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.schedule_policy import source_as_of
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure
from guanheng_app.observation.storage import digest,encode
from guanheng_app.observation.query import parquet_bytes


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


def test_broker_heat_warmup_and_boolean_transition():
    days=[(date(2025,1,1)+timedelta(days=i)).isoformat() for i in range(257)]
    flat=dict.fromkeys(days,100)
    prices={broker_heat.CSI300_INDEX:dict(flat),broker_heat.BROKER:dict(flat),broker_heat.ETF:dict(flat)}
    prices[broker_heat.BROKER][days[251]]=99
    purchases={day:i+1 for i,day in enumerate(days)}
    del purchases[days[254]]
    rows=broker_heat.calculate(days,prices,purchases,days[250])
    assert [row['event_state'] for row in rows]==[None,0,1,1,None,None,None]
    assert [row['event_code'] for row in rows]==[None,0,1,0,None,None,None]
    assert rows[2]['heat']==1
    assert rows[-1]['close']==100


def test_broker_heat_new_source_publishes_chart_and_reports_missing_warmup(tmp_path):
    reader,_=fetch_at(tmp_path)
    config=configuration()
    day='2026-10-30'
    source=dict(id='wt.broker_heat',kind=broker_heat.KIND,date_policy='cn-prior-day',
        history_from=day,overlap_days=0,datasets=[broker_heat.METRIC])
    config['sources']=[source]
    validate_configuration(config)
    manifest=dict(schema_version='market-observation/1',published_at='2026-10-29T00:00:00+00:00',
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    adopt_snapshot(reader,manifest,digest(encode(manifest)),None,monotonic()+10)
    class Client:
        def source_market_snapshot_query(self, requested):
            assert requested==day
            return dict(status=dict(code='Ok'),data=dict(snapshot_id='version',observation_date=day,
                provenance=dict(supplement_facts_sha256='catalog')))
        def source_daily_history_batch_query(self, request):
            adjustment='none' if request['symbols']==[broker_heat.CSI300_INDEX] else 'front_ratio'
            assert request['adjustment']==adjustment and request['to']==20261030
            return dict(status=dict(code='Ok'),data=dict(results=[
                dict(symbol=symbol,status=dict(code='Ok'),data=dict(source_snapshot_id='version',
                    metadata=dict(adjustment=adjustment),bars=[dict(date=20261030,close=100)]))
                for symbol in request['symbols']]))
        def source_supplement_query(self,request):
            assert request['metric']=='margin_purchase' and request['snapshot_id']=='version'
            return dict(status=dict(code='Ok'),data=dict(source_snapshot_id='version',source_sha256='catalog',
                rows=[dict(date=day,value='173379043429',unit='CNY')]))
    result=collection.refresh(reader,config,as_of='2026-10-31',deadline=monotonic()+10,
        now=datetime(2026,10,31,1,tzinfo=timezone.utc),market_client_factory=lambda _:Client())
    assert result['sources'][0]['status']=='partial'
    _,published=reader.snapshot()
    assert published['preferences']['default_datasets'][broker_heat.METRIC]==broker_heat.METRIC
    row,=reader.rows(published['datasets'][broker_heat.METRIC]['partition'])
    assert row['close']==100 and row['heat'] is None and row['event_code'] is None
    repair = {}
    assert _coverage(reader,published,source,day,lambda:None,item=repair)==[day]
    assert repair['missing_count']==1
    assert repair['inputs']==[dict(id=f'{broker_heat.METRIC}.{field}',missing_count=1,
        first_missing=day,last_missing=day) for field in ('purchase','relative','support')]


@pytest.mark.parametrize('buyback,missing,ratio',[(0,False,3),(200_000_000,False,1.5),(0,True,None)])
def test_ipo_supply_publishes_two_chart_series_and_counts_ratio_coverage(tmp_path,monkeypatch,buyback,missing,ratio):
    from guanheng_app.observation.calendars import official_calendar

    reader,_=fetch_at(tmp_path)
    config=configuration()
    day='2026-10-30'
    source=dict(id='wt.ipo_supply',kind=ipo_supply.KIND,date_policy='cn-prior-day',
        history_from=day,overlap_days=0,datasets=[ipo_supply.METRIC],tables=list(ipo_supply.SOURCE_TABLES))
    config['sources']=[source]
    validate_configuration(config)
    sessions,_=official_calendar(config['models']['calendars']['cn'])
    days=[row['date'] for row in sessions if row['is_open'] and row['date']<=day][-20:]
    def announced(fetch,calendar_days,*,existing=()):
        return [dict(date=d,amount_cny=buyback if d in days else 0,announcement_count=1)
                for d in calendar_days if not (missing and d==days[0])]
    monkeypatch.setattr(ipo_supply.buyback_announced,'history',announced)
    manifest=dict(schema_version='market-observation/1',published_at='2026-10-29T00:00:00+00:00',
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    adopt_snapshot(reader,manifest,digest(encode(manifest)),None,monotonic()+10)

    class Client:
        def source_market_snapshot_query(self,requested):
            return dict(status=dict(code='Ok'),data=dict(snapshot_id='version',observation_date=requested,
                provenance=dict(supplement_facts_sha256='catalog')))

        def source_daily_history_batch_query(self,request):
            assert request['symbols']==[ipo_supply.STAR50] and request['adjustment']=='none'
            return dict(status=dict(code='Ok'),data=dict(results=[dict(symbol=ipo_supply.STAR50,status=dict(code='Ok'),
                data=dict(source_snapshot_id='version',metadata=dict(adjustment='none'),bars=[dict(date=20261030,close=1300)]))]))

        def source_supplement_query(self,request):
            assert request['from']==days[0] and request['to']==day and request['snapshot_id']=='version'
            a,b,c=ipo_supply.INPUTS.values()
            amounts={a:100_000_000,b:200_000_000,c:buyback}
            rows=days[1:] if missing and request['metric']==c else days
            return dict(status=dict(code='Ok'),data=dict(source_snapshot_id='version',source_sha256='catalog',
                rows=[dict(date=d,value=str(amounts[request['metric']]),unit='CNY') for d in rows]))

    result=collection.refresh(reader,config,as_of='2026-10-31',deadline=monotonic()+10,
        now=datetime(2026,10,31,1,tzinfo=timezone.utc),market_client_factory=lambda _:Client())
    assert result['sources'][0]['status']==('partial' if missing else 'success')
    _,published=reader.snapshot()
    assert published['preferences']['default_datasets'][ipo_supply.METRIC]==ipo_supply.METRIC
    row,=reader.rows(published['datasets'][ipo_supply.METRIC]['partition'])
    assert row['close']==1300 and row['ratio']==ratio
    assert row['buyback']==buyback/100_000_000
    assert row['buyback_window_missing']==int(missing)
    assert [line['key'] for line in ipo_supply.definition()['lines']]==['close','ratio']
    repair = {}
    assert _coverage(reader,published,source,day,lambda:None,item=repair)==([day] if missing else [])
    assert repair['inputs']==([dict(id=f'{ipo_supply.METRIC}.buyback',missing_count=1,
        first_missing=day,last_missing=day)] if missing else [])


@pytest.mark.parametrize('failure',['collection_timeout','choice_public_query_incomplete','source_network_timeout'])
def test_choice_partial_inputs_publish_and_resume_without_waiting_for_wt(tmp_path,monkeypatch,failure):
    import json,re
    from guanheng_app.observation.calendars import official_calendar
    reader,_=fetch_at(tmp_path);config=configuration();day='2026-10-30'
    source=dict(id='wt.ipo_supply',kind=ipo_supply.KIND,date_policy='cn-prior-day',history_from=day,
        overlap_days=0,datasets=[ipo_supply.METRIC],tables=list(ipo_supply.SOURCE_TABLES))
    config['sources']=[source];config['allowed_hosts']=['ai-saas.eastmoney.com'];validate_configuration(config)
    sessions,_=official_calendar(config['models']['calendars']['cn'])
    days=[r['date']for r in sessions if r['is_open'] and r['date']<=day][-20:]
    manifest=dict(schema_version='market-observation/1',published_at='2026-10-29T00:00:00+00:00',
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    adopt_snapshot(reader,manifest,digest(encode(manifest)),None,monotonic()+10)
    class Client:
        def source_market_snapshot_query(self,requested):
            return dict(status=dict(code='Ok'),data=dict(snapshot_id='v',observation_date=requested,
                provenance=dict(supplement_facts_sha256='s')))
        def source_daily_history_batch_query(self,request):
            return dict(status=dict(code='Ok'),data=dict(results=[dict(symbol=ipo_supply.STAR50,status=dict(code='Ok'),
                data=dict(source_snapshot_id='v',metadata=dict(adjustment='none'),bars=[dict(date=20261030,close=1300)]))]))
        def source_supplement_query(self,request):
            return dict(status=dict(code='Ok'),data=dict(source_snapshot_id='v',source_sha256='s',
                rows=[dict(date=d,value='100000000',unit='CNY')for d in days]))
    calls=[];expire=[failure=='collection_timeout'];nested_fail=[failure=='source_network_timeout'];known_zero=[]
    class Capture:
        def __init__(self,objects,hosts,timeout,*,budget):self.objects,self.records,self.timeout,self.budget=objects,[],timeout,budget
        def close(self):pass
        def wait(self,seconds):self.budget.remaining()
        def post_private_query(self,url,payload):
            self.budget.request()
            if failure=='choice_public_query_incomplete':return encode(dict(code='502',data=None))
            bounds=re.findall(r'(\d{4})年(\d{2})月(\d{2})日',payload['keyWord']);first,last=['-'.join(parts)for parts in bounds];calls.append((first,last))
            if nested_fail[0] and first==last:
                if known_zero:raise SourceFailure('source_network_timeout')
                known_zero.append(first)
            dates=[(date.fromisoformat(first)+timedelta(days=i)).isoformat()for i in range((date.fromisoformat(last)-date.fromisoformat(first)).days+1)]
            key='DIM{'+first+'|'+last+'|5|天}已回购金额求和'
            listed=dates[-1:]if failure=='source_network_timeout'else dates
            total=0 if nested_fail[0]and first==last else 1
            body=encode(dict(code='100'if total else '201',data=dict(result=dict(total=total,
                columns=[dict(title='回购',key=key)],dataList=[dict(SECURITY_CODE='600001',**{
                    'MTM_EXTRA|'+key:json.dumps([dict(colHeads=[dict(colProp='DIM_REPURAMOUNT',unit='元'),dict(colProp='DIM_UPDATEDATE',unit='')],
                        data=[dict(DIM_UPDATEDATE=d,DIM_REPURAMOUNT='1亿',SUM=str(100000000*len(listed)))for d in listed])])})]if total else []))))
            self.records.append(dict(kind='http_body',sha256=self.objects.put(body),source_host='np-tjxg-g.eastmoney.com',
                status=200,retrieved_at='2026-10-31T01:00:00+00:00',media_type='application/json'))
            if expire[0]:self.budget.deadline=monotonic()-1
            return body
    def run():return collection.refresh(reader,config,as_of='2026-10-31',deadline=monotonic()+20,
        now=datetime(2026,10,31,1,tzinfo=timezone.utc),market_client_factory=lambda _:Client(),fetcher_factory=Capture)
    result=run();assert result['status']=='partial' and result['sources'][0]['error_code']==failure
    _,published=reader.snapshot();rows=reader.rows(published['source_tables'][ipo_supply.buyback_announced.TABLE])
    assert len(rows)==(5 if expire[0] else 2 if nested_fail[0] else 0)
    repair={};assert _coverage(reader,published,source,day,lambda:None,item=repair)==[day]
    assert [item['id']for item in repair['inputs']]==[ipo_supply.METRIC+'.buyback']
    if expire[0]:
        first_last=calls[0][1];calls.clear();expire[0]=False
        assert run()['status']=='success'
        assert calls and all(first>first_last for first,last in calls)
    elif nested_fail[0]:
        cached={row['date']for row in rows};calls.clear();nested_fail[0]=False
        assert run()['status']=='success'
        assert not any(first==last and first in cached for first,last in calls)


@pytest.mark.parametrize('missing_denominator',[False,True])
def test_csi300_etf_cap_is_published_and_checks_both_chart_series(tmp_path, missing_denominator):
    from guanheng_market_client import MarketUnavailable
    from guanheng_market_client.supplement_facts import CSI300_INDEX, INDEX_FREE_FLOAT_CAP
    reader,_=fetch_at(tmp_path)
    config=configuration()
    source=dict(id='wt.csi300_etf_cap',kind=etf_flow.CAP_KIND,date_policy='cn-prior-day',
        history_from='2026-10-30',overlap_days=0,symbols=list(etf_flow.CAP_FUNDS),datasets=[etf_flow.CAP_METRIC])
    config['sources']=[source]
    validate_configuration(config)
    manifest=dict(schema_version='market-observation/1',published_at='2026-10-29T00:00:00+00:00',
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    adopt_snapshot(reader,manifest,digest(encode(manifest)),None,monotonic()+10)
    class Client:
        def source_market_snapshot_query(self,day):
            assert day=='2026-10-30'
            return dict(status=dict(code='Ok'),data=dict(snapshot_id='version',observation_date=day,
                provenance=dict(supplement_facts_sha256='catalog')))
        def source_daily_history_batch_query(self,request):
            assert request['symbols']==[CSI300_INDEX,*etf_flow.CAP_FUNDS]
            return dict(status=dict(code='Ok'),data=dict(results=[
                dict(symbol=symbol,status=dict(code='Ok'),data=dict(source_snapshot_id='version',
                    metadata=dict(adjustment='none',price_unit='unknown' if symbol==CSI300_INDEX else 'CNY'),
                    bars=[dict(date=20261030,close=4016.29 if symbol==CSI300_INDEX else 4)]))
                for symbol in request['symbols']]))
        def source_supplement_query(self,request):
            assert request['snapshot_id']=='version'
            cap=request['metric']==INDEX_FREE_FLOAT_CAP
            if cap and missing_denominator:
                raise MarketUnavailable('isolated test')
            return dict(status=dict(code='Ok'),data=dict(source_snapshot_id='version',source_sha256='catalog',
                rows=[dict(date='2026-10-30',symbol=symbol,value='80000000000' if cap else '100000000',
                          unit='CNY' if cap else 'share') for symbol in request['symbols']],
                selection=dict(next_offset=None)))
    result=collection.refresh(reader,config,as_of='2026-10-31',deadline=monotonic()+10,
        now=datetime(2026,10,31,1,tzinfo=timezone.utc),market_client_factory=lambda _:Client())
    assert result['sources'][0]['status']==('partial' if missing_denominator else 'success')
    _,published=reader.snapshot()
    assert any(board['id']==etf_flow.CAP_BOARD for board in published['boards'])
    rows=reader.rows(published['datasets'][etf_flow.CAP_METRIC]['partition'])
    assert rows[0]['index_close']==4016.29 and rows[0]['ratio']==(None if missing_denominator else 2)
    assert _coverage(reader,published,source,'2026-10-30',lambda:None)==(['2026-10-30'] if missing_denominator else [])


@pytest.mark.parametrize('qualified_day,current,fallback', [
    (20261102,'2026-11-03',None),(20261103,'2026-11-04',None),(20261102,'2026-11-04','available'),
    (20261102,'2026-11-04','broken'),(20261102,'2026-11-04','timeout')])
def test_wt_index_refresh_keeps_verified_amount_and_reports_a_real_gap(tmp_path, qualified_day, current, fallback):
    reader,_=fetch_at(tmp_path)
    config=configuration()
    config['sources']=[dict(id='wt.indices',kind=market_structure_source.WT_INDEX_KIND,
        date_policy='cn-prior-day',overlap_days=2,history_from='2026-10-30',
        tables=list(market_structure_source.INDEX_TABLES.values()))]
    validate_configuration(config)
    small=market_structure_source.SMALL_CAP_TABLE
    prior=reader.objects.put(parquet_bytes([dict(date='2026-10-30',close=2800,amount_billion=1234)]))
    manifest=dict(schema_version='market-observation/1',published_at='2026-10-30T00:00:00+00:00',
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={},
        source_tables={small:prior})
    adopt_snapshot(reader,manifest,digest(encode(manifest)),None,monotonic()+10)

    class Client:
        def source_market_snapshot_query(self, day):
            assert day in ('2026-11-03','2026-11-04')
            if day!=current:
                return dict(status=dict(code='Unavailable'),data={})
            return dict(status=dict(code='Ok'),data=dict(observation_date=day,snapshot_id='test-index-version',
                provenance={'supplement_facts_sha256':'test'} if fallback else {}))

        def source_daily_history_batch_query(self, request):
            assert request==dict(symbols=['SSE.000300','SSE.000688','SSE.932000'],
                adjustment='none',snapshot_id='test-index-version',limit=3,**{'from':20261030,'to':20261103})
            results=[]
            for symbol in request['symbols']:
                bars=[dict(date=day,close=2801+index,amount=345_000_000_000)
                      for index,day in enumerate((20261030,20261102,20261103))]
                data=dict(source_snapshot_id=request['snapshot_id'],metadata=dict(adjustment='none',amount_unit='unknown'),
                    bars=bars,provenance=[dict(offset=index,count=1,
                        metadata=dict(amount_unit='CNY' if bar['date']==qualified_day else 'unknown'))
                        for index,bar in enumerate(bars)])
                results.append(dict(symbol=symbol,status=dict(code='Ok'),data=data))
            return dict(status=dict(code='Ok'),data=dict(results=results))

        def source_supplement_query(self, request):
            assert fallback
            assert request==dict(snapshot_id='test-index-version',metric='index_turnover',symbols=['SSE.932000'],
                offset=0,limit=2000,**{'from':'2026-10-30','to':'2026-11-03'})
            if fallback=='broken':
                raise MarketHTTPError(500,dict(status=dict(code='IoError')))
            if fallback=='timeout':
                raise MarketUnavailable('transport unavailable')
            return dict(status=dict(code='Ok'), data=dict(source_snapshot_id=request['snapshot_id'],source_sha256='test',
                rows=[dict(date=day,unit='CNY',value='320000000000') for day in ('2026-11-02','2026-11-03')],
                selection=dict(next_offset=None)))

    run=collection.refresh(reader,config,as_of='2026-11-04',deadline=monotonic()+30,
        now=datetime(2026,11,4,9,tzinfo=timezone.utc),market_client_factory=lambda seconds:Client(),
        source_ids=['wt.indices'],repair_history_start='2026-10-30')
    completed=fallback=='available'
    assert run['sources'][0]['status']==('success' if completed else 'partial')
    qualified='2026-11-02' if qualified_day==20261102 else '2026-11-03'
    gap='2026-11-03' if qualified_day==20261102 else '2026-11-02'
    assert run['sources'][0]['latest_period']==('2026-11-03' if completed else qualified)
    _,published=reader.snapshot()
    rows=reader.rows(published['source_tables'][small])
    assert [(row['close'],row['amount_billion']) for row in rows]==[
        (2801,1234),(2802,3450 if qualified_day==20261102 else None),
        (2803,3450 if qualified_day==20261103 else 3200 if completed else None)]
    assert _coverage(reader,published,config['sources'][0],'2026-11-03',lambda:None)==([] if completed else [gap])


@pytest.mark.parametrize('repair,expected', [
    ({},('2026-10-31','2026-11-02')),
    ({'repair_history_start':'2026-10-27','repair_history_end':'2026-10-28'},('2026-10-27','2026-10-28')),
])
def test_wt_index_refresh_uses_its_latest_or_explicit_repair_window(tmp_path, monkeypatch, repair, expected):
    reader,_=fetch_at(tmp_path)
    config=configuration()
    config['max_days_per_batch']=3
    config['sources']=[dict(id='wt.indices',kind=market_structure_source.WT_INDEX_KIND,
        date_policy='cn-prior-day',overlap_days=2,history_from='2026-09-01',
        tables=list(market_structure_source.INDEX_TABLES.values()))]
    manifest=dict(schema_version='market-observation/1',published_at='2026-10-30T00:00:00+00:00',
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    adopt_snapshot(reader,manifest,digest(encode(manifest)),None,monotonic()+10)

    def unavailable(fetch, start, end, calendar, factory, *, snapshot_dates):
        assert (start,end)==expected
        assert snapshot_dates==['2026-11-03','2026-11-02']
        raise SourceFailure('wt_market_index_unavailable')

    monkeypatch.setattr(market_structure_source,'wt_index_history',unavailable)
    run=collection.refresh(reader,config,as_of='2026-11-03',deadline=monotonic()+30,
        now=datetime(2026,11,3,9,tzinfo=timezone.utc),market_client_factory=lambda seconds:None,
        source_ids=['wt.indices'],**repair)
    assert run['sources'][0]['error_code']=='wt_market_index_unavailable'


@pytest.mark.parametrize('as_of,expected',[('2026-11-04','2026-11-03'),('2026-10-29','2026-10-29')])
def test_manual_selected_date_and_failed_read_keep_original_publication(tmp_path,monkeypatch,as_of,expected):
    reader,_=fetch_at(tmp_path)
    manifest=dict(schema_version='market-observation/1',published_at='2026-10-29T00:00:00+00:00',
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    previous=digest(encode(manifest));adopt_snapshot(reader,manifest,previous,None,monotonic()+10)
    calls=[]
    def unavailable(fetch,source,start,end,client_factory,*,calendar,snapshot_dates):
        calls.append((end,snapshot_dates));raise SourceFailure('wt_market_snapshot_price_differs')
    monkeypatch.setattr(collection,'wt_breadth_history',unavailable)
    run=collection.refresh(reader,configuration(),as_of=as_of,deadline=monotonic()+30,source_ids=['wt.breadth'],
        now=datetime(2026,11,4,1,tzinfo=timezone.utc),market_client_factory=lambda seconds:None)
    assert calls==[(expected,sorted({'2026-11-03',expected},reverse=True))]
    assert run['status']=='failed' and run['sources'][0]['error_code']=='wt_market_snapshot_price_differs'
    assert reader.repository.current()==previous and reader.repository.runs()[0]['previous_snapshot']==previous


@pytest.mark.parametrize('provider',[wt_breadth_source,wt_t2108_source])
def test_wrong_snapshot_date_stops_before_any_price_request(tmp_path,provider):
    _,fetch=fetch_at(tmp_path)
    client=SimpleNamespace(source_market_snapshot_query=lambda day:dict(status=dict(code='Ok'),data=dict(observation_date='2026-10-29')))
    kwargs=dict(calendar=calendar())
    if provider is wt_breadth_source:kwargs['snapshot_dates']=['2026-10-30']
    with pytest.raises(SourceFailure,match='wt_market_snapshot_date_differs'):
        provider.history(fetch,{},'2026-10-30','2026-10-30',lambda seconds:client,**kwargs)
    assert fetch.budget.requests==1


@pytest.mark.parametrize('provider',[wt_breadth_source,wt_t2108_source])
def test_price_from_another_snapshot_is_rejected_before_calculation(tmp_path,provider):
    _,fetch=fetch_at(tmp_path);members=['SSE.600001'];sid='1'*64
    snapshot=dict(observation_date='2026-10-30',members=members,snapshot_id=sid,
        source_received_at='2026-10-30T08:00:00Z',provenance=dict(universe_sha256='3'*64))
    facts=dict(members=members)
    adjustment='none' if provider is wt_breadth_source else 'front_ratio'
    bad=dict(results=[dict(symbol=members[0],status=dict(code='Ok'),data=dict(
        source_snapshot_id='2'*64,metadata=dict(adjustment=adjustment),bars=[]))])
    client=SimpleNamespace(source_market_snapshot_query=lambda day:dict(status=dict(code='Ok'),data=snapshot),
        source_day_facts_query=lambda day,identity:dict(status=dict(code='Ok'),data=facts),
        source_daily_history_batch_query=lambda request:dict(status=dict(code='Ok'),data=bad))
    kwargs=dict(calendar=calendar())
    if provider is wt_breadth_source:kwargs['snapshot_dates']=['2026-10-30']
    with pytest.raises(SourceFailure,match='wt_market_snapshot_price_differs'):
        provider.history(fetch,{},'2026-10-30','2026-10-30',lambda seconds:client,**kwargs)


@pytest.mark.parametrize('mode',['same_day','historical','historical_qmt','unqualified','missing'])
def test_t2108_preserves_stale_and_insufficient_samples_and_snapshot_binding(tmp_path,mode):
    _,fetch=fetch_at(tmp_path);seen=[];sid='1'*64
    snapshot=dict(observation_date='2026-10-30',members=['SSE.600001','SSE.600002','SZSE.000001'],snapshot_id=sid,
        source_kind='actual-qmt',source_received_at='2026-10-30T08:00:00Z',
        provenance=dict(source_binding_sha256='2'*64,universe_sha256='3'*64))
    universe=list(snapshot['members'])
    if mode!='same_day':
        snapshot.update(observation_date='2026-11-03',members=['SSE.600999'])
    def facts(day,identity):
        assert day=='2026-10-30' and identity==sid
        if mode=='missing':
            return dict(status=dict(code='Unavailable'),data={})
        method = {'unqualified': 'listing_intervals_latest_identity', 'historical_qmt': 'same_day_qmt'}.get(
            mode, 'same_day_public')
        return dict(status=dict(code='Ok'),data=dict(date=day,members=universe,source_snapshot_id=sid,
            qualification=dict(membership_method=method,membership_as_of=day),
            provenance=dict(universe_sha256='4'*64,source_received_at='2026-10-30T08:00:00Z')))
    def batch(request):
        assert request['symbols']==universe and request['to']==20261030
        seen.append(copy.deepcopy(request));results=[]
        for index,symbol in enumerate(request['symbols']):
            end=date(2026,10,30)-timedelta(days=int(index==2));count=39 if index==1 else 40
            bars=[dict(date=int((end-timedelta(days=n)).strftime('%Y%m%d')),close=12 if n==0 else 10) for n in reversed(range(count))]
            results.append(dict(symbol=symbol,status=dict(code='Ok'),data=dict(source_snapshot_id=sid,metadata=dict(adjustment='front_ratio'),bars=bars)))
        return dict(status=dict(code='Ok'),data=dict(results=results))
    client=SimpleNamespace(source_market_snapshot_query=lambda day:dict(status=dict(code='Ok'),data=snapshot),
                           source_daily_history_batch_query=batch,source_day_facts_query=facts)
    def read():
        return wt_t2108_source.history(fetch,{},'2026-10-30','2026-10-30',lambda seconds:client,
            calendar=calendar(),snapshot_dates=[snapshot['observation_date']])
    if mode in ('unqualified','missing'):
        with pytest.raises(SourceFailure,match='wt_t2108_historical_universe_'+mode):
            read()
        assert not seen
        return
    output=read()
    row=output['t2108.ashare'][0]
    assert (row['eligible_count'],row['above_count'],row['insufficient_count'],row['stale_count'])==(1,1,1,1)
    assert row['above_sma40_pct']==100 and row['market_above_sma40_pct'] is None and row['available_at'] is None
    assert seen[0]['snapshot_id']==sid and seen[0]['limit']==40 and seen[0]['adjustment']=='front_ratio'
    assert output['source.t2108_ashare_universe'][0]['universe_version'] == ('3' if mode == 'same_day' else '4')*64
    assert row.get('reconstruction_as_of') == (None if mode == 'same_day' else '2026-11-03')
    assert fetch.budget.requests == (2 if mode == 'same_day' else 3)
