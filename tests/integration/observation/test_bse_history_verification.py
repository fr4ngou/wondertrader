"""完整公告复核、资格变化及原高管refresh主链；合成来源不授真实市场资格。"""
from copy import deepcopy
from time import monotonic
from types import SimpleNamespace

import pytest

from guanheng_app.observation import executive_source
from guanheng_app.observation.bse_history_verification import URL,verify_history
from guanheng_app.observation.collection import refresh
from guanheng_app.observation.collection_config import validate_configuration
from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.publication import adopt_snapshot
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure
from guanheng_app.observation.storage import encode,digest
from test_bse_executive import Basic,Capture,config
from test_bse_financial import history,ashare_configuration


class QualifiedCapture(Capture):
    mutation=None
    instances=[]
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.closed=False;self.instances.append(self)
    def post_readonly(self,url,form,**kwargs):
        if url!=URL:return super().post_readonly(url,form,**kwargs)
        self.budget.request('http');page=int(form['page'])
        assert form['keyword']=='终止上市' and form['xxfcbj[]']=='2' and form['disclosureType[]']=='5'
        rows=[dict(companyCd='832317',disclosureCode='notice_'+str(index),
            disclosureTitle='股票终止上市'+str(index),publishDate='2022-04-25',xxfcbj='2',
            destFilePath='/disclosure/2022/'+('exit.pdf' if index==0 else 'aux-'+str(index)+'.pdf')) for index in range(21)]
        value=dict(number=page,size=20,totalElements=21,totalPages=2,firstPage=page==0,lastPage=page==1,
            numberOfElements=len(rows[page*20:(page+1)*20]),content=rows[page*20:(page+1)*20])
        if self.mutation:self.mutation(value,page)
        body=b'guanhengBseHistory('+encode([dict(status=0,listInfo=value)])+b');'
        self.budget.consume(len(body));return self.capture(body)
    def close(self):self.closed=True


def fetch_for(reader):
    return QualifiedCapture(reader.objects,budget=CollectionBudget(monotonic()+20,max_bytes=4*1024*1024))


def seed(tmp_path,monkeypatch):
    monkeypatch.setattr(executive_source,'BaostockClient',Basic)
    reader=build_reader(tmp_path);reader.repository.initialize()
    value=dict(schema_version='market-observation/1',published_at='2026-10-29T00:00:00+00:00',boards=[],
        preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    adopt_snapshot(reader,value,digest(encode(value)),None,monotonic()+10)
    configuration=config()
    run=refresh(reader,configuration,as_of='2026-10-29',deadline=monotonic()+20,fetcher_factory=Capture)
    assert run['status']=='success',run
    return reader,configuration


def test_original_refresh_extends_qualified_history_and_projects_actual_cutoff(tmp_path,monkeypatch):
    reader,configuration=seed(tmp_path,monkeypatch);before,original=reader.snapshot()
    configuration['sources'][0]['bse_verify_disclosures']=True
    run=refresh(reader,configuration,as_of='2026-10-31',deadline=monotonic()+20,fetcher_factory=QualifiedCapture)
    assert run['status']=='success',run
    _,current=reader.snapshot()
    for metric in ('executive.net.ashare','executive.ratio.ashare','executive.companies.ashare'):
        rows=reader.rows(current['datasets'][metric]['partition'])
        assert rows[-1]['date']=='2026-10-31' and rows[-1]['universe_confirmed_through']=='2026-10-31'
    universe=reader.rows(current['source_tables']['source.executive_ashare_universe'])[-1]
    assert universe['history_confirmed_through']=='2026-10-31'
    import json
    fact=json.loads(reader.objects.get(universe['source_bse_sha256']))
    proof=json.loads(reader.objects.get(fact['history_verification_sha256']))
    assert fact['verified_through']=='2026-10-31' and proof['announcements']==21
    assert configuration['sources'][0]['bse_history']['verified_through']=='2026-10-30'
    assert QualifiedCapture.instances[-1].closed


def test_static_mode_keeps_original_expiry_and_previous_snapshot(tmp_path,monkeypatch):
    reader,configuration=seed(tmp_path,monkeypatch);before,_=reader.snapshot()
    run=refresh(reader,configuration,as_of='2026-10-31',deadline=monotonic()+20,fetcher_factory=QualifiedCapture)
    assert run['status']=='failed' and run['sources'][0]['error_code']=='bse_history_coverage_expired'
    assert reader.repository.current()==before and QualifiedCapture.instances[-1].closed


@pytest.mark.parametrize('fault',['new_company','new_notice','missing_original','duplicate','total_drift','bool_total','last_page','bad_day','bad_path'])
def test_complete_query_rejects_registry_schema_or_pagination_changes(tmp_path,fault):
    reader=build_reader(tmp_path);fetch=fetch_for(reader)
    def mutate(value,page):
        if fault=='new_company':value['content'][0]['companyCd']='920999'
        elif fault=='new_notice':value['content'][0]['publishDate']='2026-10-31'
        elif fault=='missing_original' and page==0:value['content'][0]['destFilePath']='/disclosure/2022/other.pdf'
        elif fault=='duplicate' and page==1:value['content'][0]['disclosureCode']='notice_0'
        elif fault=='total_drift' and page==1:value['totalElements']=22
        elif fault=='bool_total':value['totalElements']=True
        elif fault=='last_page':value['lastPage']=True
        elif fault=='bad_day':value['content'][0]['publishDate']='2026-02-30'
        elif fault=='bad_path':value['content'][0]['destFilePath']='/disclosure/../bad.pdf'
    fetch.mutation=mutate
    with pytest.raises(SourceFailure):verify_history(fetch,history(),'2026-10-31',{})
    assert all(row['kind']!='bse_history_verification' for row in fetch.records)


def test_original_refresh_failure_keeps_snapshot_and_closes_source(tmp_path,monkeypatch):
    reader,configuration=seed(tmp_path,monkeypatch);before,_=reader.snapshot()
    configuration['sources'][0]['bse_verify_disclosures']=True
    class Changed(QualifiedCapture):
        mutation=staticmethod(lambda value,page:value['content'][0].update(companyCd='920999'))
    run=refresh(reader,configuration,as_of='2026-10-31',deadline=monotonic()+20,fetcher_factory=Changed)
    assert run['status']=='failed' and run['sources'][0]['error_code']=='bse_history_registry_changed'
    assert reader.repository.current()==before and Changed.instances[-1].closed


def test_original_alias_mapping_is_used_for_announcement_identity(tmp_path):
    reader=build_reader(tmp_path);fetch=fetch_for(reader);seed_history=history()
    def mutate(value,page):
        for row in value['content']:row['companyCd']='830317'
    fetch.mutation=mutate
    qualified,proof=verify_history(fetch,seed_history,'2026-10-31',{'830317':'832317'})
    assert qualified['verified_through']=='2026-10-31' and seed_history['verified_through']=='2026-10-30'


@pytest.mark.parametrize('fault',['future','requests','stop'])
def test_original_deadline_capacity_and_future_boundary(tmp_path,fault):
    reader=build_reader(tmp_path);fetch=fetch_for(reader);end='2026-10-31'
    if fault=='future':end='2099-01-01'
    if fault=='requests':fetch.budget.max_requests=1
    if fault=='stop':fetch.budget.cancelled=lambda:True
    with pytest.raises(SourceFailure):verify_history(fetch,history(),end,{})


@pytest.mark.parametrize('value',[True,False])
def test_valid_source_policy_is_explicit_and_bounded(value):
    configuration=config();configuration['sources'][0]['bse_verify_disclosures']=value
    validate_configuration(configuration)


@pytest.mark.parametrize('value',['true',1,None,[]])
def test_policy_rejects_wrong_types(value):
    configuration=config();configuration['sources'][0]['bse_verify_disclosures']=value
    with pytest.raises(ObservationError):validate_configuration(configuration)


def test_financial_source_cannot_enable_executive_policy():
    configuration=ashare_configuration();configuration['sources'][0]['bse_verify_disclosures']=True
    with pytest.raises(ObservationError):validate_configuration(configuration)
