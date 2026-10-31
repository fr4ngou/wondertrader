"""公开来源归档所有权、日期和字段缺口回归；全部使用隔离数据根。"""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from time import monotonic
from types import SimpleNamespace

import pytest
from guanheng_app.observation.ashare_public import Archive
from guanheng_app.observation.ashare_source import bse_numbers,validate_daily
from guanheng_app.observation.ashare_pool import current_pool
from guanheng_app.observation.breadth_models import admit_definition,definition
from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure
from guanheng_app.observation.storage import encode

DAY='2026-10-30'

def owner(tmp_path,now=None):
    reader=build_reader(tmp_path);reader.repository.initialize()
    fetch=SimpleNamespace(objects=reader.objects,records=[],budget=CollectionBudget(monotonic()+20))
    return Archive(reader,fetch,{'id':'public-test'},now=now),reader

def test_dated_archives_survive_ui_run_limit_and_other_policy(tmp_path):
    archive,reader=owner(tmp_path)
    archive.record('ashare_capture',DAY,'success',packet_sha256='1'*64)
    for _ in range(105):archive.record('ashare_capture','2026-11-01','failed')
    archive.record('ashare_capture',DAY,'failed')
    other=Archive(reader,archive.fetch,{'id':'public-test','new_policy':True})
    other.record('ashare_capture',DAY,'success',packet_sha256='2'*64)
    result=reader.repository.source_archives('ashare_capture','public-test',DAY,DAY,
        deadline=monotonic()+10,policy=archive.policy)
    assert len(result)==1 and result[0]['packet_sha256']=='1'*64

def test_retry_budget_reopens_next_natural_day_for_same_trading_day(tmp_path):
    now=datetime.now(timezone.utc)
    archive,reader=owner(tmp_path,now)
    archive.max_attempts=1;archive.attempt('ashare_capture',DAY)
    with pytest.raises(SourceFailure,match='ashare_capture_retries_exhausted'):
        archive.attempt('ashare_capture',DAY)
    tomorrow=Archive(reader,archive.fetch,archive.source,now=now+timedelta(days=1),max_attempts=1)
    tomorrow.attempt('ashare_capture',DAY)
    assert reader.repository.current() is None

def test_invalid_part_does_not_become_reusable_success(tmp_path):
    archive,reader=owner(tmp_path)
    def invalid():
        bse_numbers(dict(xxhbzl='人民币',hqcjsl=-1),{})
    with pytest.raises(SourceFailure):archive.part(DAY,'bse_close',invalid)
    assert not archive.receipts('ashare_part',DAY,status='success',part='bse_close')
    assert reader.repository.current() is None

@pytest.mark.parametrize('value',[True,-1,Decimal('1e999999'),Decimal('NaN'),Decimal('1.2')])
def test_invalid_share_quantities_rejected_before_archive(value):
    with pytest.raises(SourceFailure):bse_numbers(dict(xxhbzl='人民币',hqcjsl=value),{})

def test_order_increment_is_independent_of_market_volume_unit():
    quote=dict(xxhbzl='人民币',hqcjsl=100,hqzjcj=10,hqzrsp=9)
    assert bse_numbers(quote,dict(xxhbzl='00',xxsldw=100,xxfxsgb=1000,xxzgb=2000))==(100,1000,10,9)

def test_missing_float_retains_price_and_actual_volume():
    assert bse_numbers(dict(xxhbzl='人民币',hqcjsl=100,hqzjcj=10,hqzrsp=9),{})==(100,None,10,9)

@pytest.mark.parametrize('value',['NaN','1e999999','-1','1.5'])
def test_daily_invalid_volume_is_not_cached(value):
    fields=['date','code','close','preclose','volume','turn','tradestatus']
    with pytest.raises((ValueError,SourceFailure)):
        validate_daily(dict(fields=fields,rows=[[DAY,'sh.600001','10','9',value,'2','1']]),DAY,lambda:None)

def test_unknown_security_categories_remain_candidates():
    basic=dict(fields=['code','type','ipoDate','outDate'],rows=[
        ['sh.600001','?','2020-01-01',''],['sz.000001','2','2020-01-01','']])
    pool=current_pool(basic,dict(fields=['code','date'],rows=[]),
        {'920001':dict(xxzqjb='?',fxssrq='20200101')},{},[],['2025-12-31'],{},DAY,check=lambda:None)
    assert pool['members']==['bj.920001','sh.600001']
    assert pool['known_market_count']==0 and pool['unresolved_identity_count']==2
    assert pool['excluded_members']=={'sz.000001':'source_nonstock'}

def test_listing_boundaries_remove_unverified_candidates():
    basic=dict(fields=['code','type','ipoDate','outDate'],rows=[
        ['sh.600001','?','2099-01-01',''],['sz.000001','?','2020-01-01','2026-10-29']])
    pool=current_pool(basic,dict(fields=['code','date'],rows=[]),
        {'920001':dict(xxzqjb='?',fxssrq='20990101')},{},[],['2025-12-31'],{},DAY,check=lambda:None)
    assert pool['members']==[] and pool['unverified_members']=={}
    assert pool['known_market_count']==pool['unresolved_identity_count']==0

def test_full_market_definition_explains_missing_primary_and_separate_bound():
    item=definition('turnover.gt5.ashare')
    assert item['primary_field']=='turnover_gt5_pct'
    assert '主值留空' in item['reading'] and '缺口说明' in item['lines'][0]['reading']
    assert '主图显示下界' not in encode(item).decode('utf-8')

def test_same_method_persisted_description_is_corrected_without_data_contract_change():
    import copy
    metric='turnover.gt5.ashare';prior=definition(metric)
    prior.update(reading='分类尚缺时主图显示下界',formula='旧说明',custom_lineage='keep')
    prior['lines'][0].update(reading=prior['reading'],formula=prior['formula'])
    original=copy.deepcopy(prior)
    admitted=admit_definition(metric,prior,[dict(date=DAY)],[dict(date=DAY)])
    assert '主值留空' in admitted['reading'] and '主值留空' in admitted['lines'][0]['reading']
    assert prior==original
    for key in ('id','definition_version','field_schema','primary_field','custom_lineage'):
        assert admitted[key]==prior[key]

def test_method_upgrade_requires_every_prior_date():
    metric='turnover.gt5.ashare';old=definition(metric);old['definition_version']=metric+'/1'
    prior=[dict(date='2026-10-29'),dict(date=DAY)]
    with pytest.raises(ObservationError,match='完整历史'):
        admit_definition(metric,old,prior,[dict(date=DAY)])
    assert admit_definition(metric,old,prior,prior)['definition_version']==metric+'/2'

@pytest.mark.parametrize('mode',['same','other','missing_cookie','default','repeat'])
def test_get_public_session_is_explicit_bounded_and_same_url_only(tmp_path,mode):
    import httpx,json
    from guanheng_app.observation.source_fetch import Fetcher
    url='https://example.invalid/mapping';seen=[]
    def handle(request):
        seen.append(request)
        if len(seen)>1 and mode!='repeat':return httpx.Response(200,stream=httpx.ByteStream(b'mapping'))
        headers={'Location':url if mode!='other' else 'https://other.invalid/mapping'}
        if mode!='missing_cookie':headers['Set-Cookie']='session=ephemeral-test; Path=/'
        return httpx.Response(302,headers=headers,stream=httpx.ByteStream(b'initialize'))
    client=httpx.Client(transport=httpx.MockTransport(handle));archive,_reader=owner(tmp_path)
    fetch=Fetcher(archive.fetch.objects,['example.invalid'],budget=archive.fetch.budget,client=client)
    try:
        if mode=='same':
            assert fetch.get(url,session_handoff=True)==b'mapping'
            assert seen[1].headers['cookie']=='session=ephemeral-test'
        else:
            with pytest.raises(SourceFailure,match='source_http_302'):
                fetch.get(url,session_handoff=mode!='default')
        assert len(seen)==(2 if mode in ('same','repeat') else 1)
        assert 'ephemeral-test' not in json.dumps(fetch.records)
    finally:fetch.close()
    assert client.is_closed

def test_get_session_reuses_original_request_deadline(tmp_path,monkeypatch):
    import httpx
    from guanheng_app.observation.source_fetch import Fetcher
    clock=[monotonic()];url='https://example.invalid/mapping'
    monkeypatch.setattr('guanheng_app.observation.source_fetch.time.monotonic',lambda:clock[0])
    def handle(request):
        clock[0]+=.08
        return httpx.Response(302,headers={'Location':url,'Set-Cookie':'session=test'},stream=httpx.ByteStream(b'x'))
    archive,_reader=owner(tmp_path);client=httpx.Client(transport=httpx.MockTransport(handle))
    fetch=Fetcher(archive.fetch.objects,['example.invalid'],timeout=.12,budget=archive.fetch.budget,client=client)
    try:
        with pytest.raises(SourceFailure,match='source_request_timeout'):fetch.get(url,session_handoff=True)
        assert fetch.budget.requests==2
    finally:fetch.close()

def test_original_scheduler_loop_reaches_archive_and_closes(tmp_path,monkeypatch):
    import threading
    from guanheng_app.observation import scheduler
    archive,reader=owner(tmp_path)
    manifest=dict(schema_version='market-observation/1',published_at=datetime.now(timezone.utc).isoformat(),
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    reader.repository.publish(manifest,None)
    calls=[]
    monkeypatch.setattr(scheduler,'tick',lambda *args,**kwargs:None)
    monkeypatch.setattr(scheduler,'capture_due',lambda *args,**kwargs:calls.append(reader.repository.scheduler_status()['phase']))
    class Stop(threading.Event):
        def wait(self,seconds):self.set();return True
    scheduler.run(reader,dict(sources=[dict(kind='ashare_public')],
        budget=dict(seconds=60),schedule=dict(timezone='Asia/Shanghai',times=['09:00'],poll_seconds=30)),Stop())
    assert calls==['archiving']
    status=reader.repository.scheduler_status()
    assert status['phase']=='stopped' and status['enabled'] is False
