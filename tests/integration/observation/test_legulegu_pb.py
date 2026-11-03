"""原供应商PB口径、公开会话及旧历史保留的必要回归。"""
from types import SimpleNamespace
import json,time
import pytest
from guanheng_app.observation.legulegu_source import history
from guanheng_app.observation.refresh_models import merge
from guanheng_app.observation.source_fetch import Fetcher,CollectionBudget,SourceFailure
from guanheng_app.observation.storage import ContentStore
from guanheng_app.observation.breadth_trends import attach_benchmark


def test_provider_values_keep_original_fields_and_old_latest_observation():
    calls=[]
    def get(url,params=None,referer=None,**kwargs):
        calls.append((url,params,kwargs))
        if len(calls)==1:return b'<meta name="_csrf" content="public-session">'
        return json.dumps(dict(data=[dict(date='2026-10-30',equalWeightAveragePB=3.4,middlePB=2.3,close=3600.),
            dict(date='2026-11-02',equalWeightAveragePB=3.45,middlePB=2.39,close=3614.31)])).encode()
    source=dict(url='https://legulegu.com/api/stock-data/market-index-pb',referer='https://legulegu.com/stockdata/all-pb')
    result=history(SimpleNamespace(get=get),source,'2026-10-09','2026-11-02')['pb_all']
    previous=dict(date='2026-10-16',equal_pb=3.2,median_pb=2.2,reference=3500.,available_at=None)
    merged,revisions=merge([previous],result)
    assert merged==[previous,*result] and revisions==[]
    assert result[-1]['equal_pb']==3.45 and result[-1]['median_pb']==2.39
    assert calls[1][1]['marketId']=='ALL'
    assert calls[1][2]['public_headers']=={'X-CSRF-Token':'public-session'}
    assert all(set(row)=={'date','equal_pb','median_pb','reference','available_at'} for row in result)


def test_missing_public_session_does_not_query_api():
    calls=[]
    def get(url,*args,**kwargs):calls.append(url);return b'<html>no session metadata</html>'
    with pytest.raises(SourceFailure) as caught:history(SimpleNamespace(get=get),dict(referer='https://legulegu.com/stockdata/all-pb',url='https://legulegu.com/api/stock-data/market-index-pb'),'2026-11-02','2026-11-02')
    assert caught.value.code=='pb_all_public_session_missing' and len(calls)==1


def test_source_cutoff_does_not_accept_future_latest_point():
    count=[0]
    def get(*args,**kwargs):
        count[0]+=1
        if count[0]==1:return b'<meta content="public-session" name="_csrf">'
        return json.dumps(dict(data=[dict(date='2026-11-02',equalWeightAveragePB=3.45,middlePB=2.39,close=3614.31),
            dict(date='2026-11-03',equalWeightAveragePB=3.5,middlePB=2.4,close=3620.)])).encode()
    source=dict(url='https://legulegu.com/api/stock-data/market-index-pb',referer='https://legulegu.com/stockdata/all-pb')
    assert [row['date'] for row in history(SimpleNamespace(get=get),source,'2026-11-02','2026-11-02')['pb_all']]==['2026-11-02']


def test_unrelated_refresh_preserves_benchmark_collector_freshness():
    observed=dict(loaded_end='2026-11-02',source_results=[dict(source_id='wondertrader.indices',status='success')])
    definitions={'market.sh000001':dict(freshness=observed)};datasets={}
    attach_benchmark(datasets,definitions,{'market.sh000001':[dict(date='2026-11-02',close=3638.03)]})
    assert definitions['market.sh000001']['freshness']==observed
    assert datasets['market.sh000001'][0]['close']==3638.03


@pytest.mark.parametrize('headers',[{'Authorization':'account-secret'},{'X-CSRF-Token':'bad\r\nInjected: x'},{'X-CSRF-Token':''}])
def test_public_read_headers_reject_account_auth_and_injection_before_transport(tmp_path,headers):
    fetch=Fetcher(ContentStore(tmp_path),['example.invalid'],timeout=1,budget=CollectionBudget(time.monotonic()+1))
    try:
        with pytest.raises(SourceFailure) as caught:fetch.get('https://example.invalid/',public_headers=headers)
        assert caught.value.code=='source_public_headers_invalid' and fetch.budget.requests==0
    finally:fetch.close()
