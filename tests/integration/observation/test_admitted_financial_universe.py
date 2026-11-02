"""已准入年末事实的真实refresh入口、资格撤回与原件冲突回归。"""
from copy import deepcopy
from time import monotonic
from types import SimpleNamespace

import pytest

from guanheng_app.observation import financial_source
from guanheng_app.observation.collection import refresh
from guanheng_app.observation.financial_universe import universes_for_reports
from guanheng_app.observation.publication import adopt_snapshot
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure
from guanheng_app.observation.storage import digest,encode
from test_financial_annual import CapturedClient,CapturedFetcher,configuration
from test_bse_financial import BseSource,ashare_configuration


def seed(tmp_path,monkeypatch,scope='ashare'):
    monkeypatch.setattr(financial_source,'BaostockClient',CapturedClient)
    reader=build_reader(tmp_path);reader.repository.initialize()
    manifest=dict(schema_version='market-observation/1',published_at='2026-10-30T00:00:00+00:00',boards=[],
        preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    adopt_snapshot(reader,manifest,digest(encode(manifest)),None,monotonic()+10)
    config=ashare_configuration() if scope=='ashare' else configuration()
    factory=BseSource if scope=='ashare' else CapturedFetcher
    run=refresh(reader,config,as_of='2026-10-30',deadline=monotonic()+30,fetcher_factory=factory)
    assert run['status']=='success',run
    _,current=reader.snapshot();key='source.financial_'+scope+'_universe'
    return reader,config,reader.rows(current['source_tables'][key])


class ReportsOnly(BseSource):
    def post_readonly(self,*args,**kwargs):raise AssertionError('已准入年末事实不重取当前股票名单')
    def get(self,url,params=None):
        assert not url.startswith('https://www.bse.cn/')
        return super().get(url,params)


@pytest.mark.parametrize('scope',['shsz','ashare'])
def test_original_refresh_uses_admitted_year_after_capture_date_without_promoting_qualification(tmp_path,monkeypatch,scope):
    reader,config,rows=seed(tmp_path,monkeypatch,scope);before,original=reader.snapshot()
    key='source.financial_'+scope+'_universe';metric='earnings.eps.'+scope
    factory=ReportsOnly if scope=='ashare' else CapturedFetcher
    run=refresh(reader,config,as_of='2026-11-01',deadline=monotonic()+30,fetcher_factory=factory)
    assert run['status']=='success',run
    assert run['sdk_requests']==0
    _,current=reader.snapshot()
    assert current['source_tables'][key]==original['source_tables'][key]
    old=reader.rows(original['datasets'][metric]['partition']);new=reader.rows(current['datasets'][metric]['partition'])
    assert old==new
    if scope=='ashare':assert new[0]['universe_confirmed_through']=='2026-10-30'


def context(reader):
    return SimpleNamespace(objects=reader.objects,records=[],timeout=15,
        budget=CollectionBudget(monotonic()+30,max_bytes=16*1024*1024,response_bytes=4*1024*1024))


def reject(*args,**kwargs):raise AssertionError('错误原件不能回退网络重建')


@pytest.mark.parametrize('fault',['version','members','future_period','through','alias_missing'])
def test_admitted_fact_identity_and_horizon_are_verified(tmp_path,monkeypatch,fault):
    reader,config,rows=seed(tmp_path,monkeypatch);source=config['sources'][0]
    rows=deepcopy(rows);row=rows[0];period=row['date'];source=deepcopy(source)
    if fault=='version':row['universe_version']='0'*64
    if fault=='members':
        row['members'].remove('bj.920001');row['market_count']-=1;row['bse_market_count']-=1
        row['universe_version']=digest(encode(dict(date=period,codes=sorted(row['members']))))
    if fault=='future_period':
        period='2026-12-31';row['date']=period
        row['universe_version']=digest(encode(dict(date=period,codes=sorted(row['members']))))
    if fault=='through':row['history_confirmed_through']='2026-11-01'
    if fault=='alias_missing':
        import json
        value=json.loads(reader.objects.get(row['source_bse_sha256']));value['aliases']={}
        row['source_bse_sha256']=reader.objects.put(encode(value))
    with pytest.raises(SourceFailure):
        universes_for_reports(context(reader),source,[period],'2027-01-01',rows,basic_client=reject)


@pytest.mark.parametrize('fault',['withdraw','correct_exit','backdated_exit'])
def test_current_configuration_can_withdraw_or_correct_previous_qualification(tmp_path,monkeypatch,fault):
    reader,config,rows=seed(tmp_path,monkeypatch);source=deepcopy(config['sources'][0])
    if fault=='withdraw':source['bse_history']['verified_through']='2026-10-28'
    if fault=='correct_exit':source['bse_history']['exits'][0]['source_sha256']='f'*64
    if fault=='backdated_exit':
        item=deepcopy(source['bse_history']['exits'][0]);item.update(code='832318');source['bse_history']['exits'].append(item)
    with pytest.raises(SourceFailure):
        universes_for_reports(context(reader),source,[rows[0]['date']],'2026-11-01',rows,basic_client=reject)


def test_new_later_qualification_keeps_original_fact_cutoff(tmp_path,monkeypatch):
    reader,config,rows=seed(tmp_path,monkeypatch);source=deepcopy(config['sources'][0])
    source['bse_history']['verified_through']='2026-11-02'
    item=deepcopy(source['bse_history']['exits'][0]);item.update(code='832318',delisted_on='2026-11-02')
    source['bse_history']['exits'].append(item)
    facts=universes_for_reports(context(reader),source,[rows[0]['date']],'2026-11-03',rows,basic_client=reject)
    assert facts[rows[0]['date']]['row']==rows[0]
    facts[rows[0]['date']]['row']['members'].clear()
    assert rows[0]['members']


def test_missing_year_uses_original_bootstrap_and_keeps_expiry_failure(tmp_path,monkeypatch):
    reader,config,rows=seed(tmp_path,monkeypatch);source=config['sources'][0]
    with pytest.raises(SourceFailure,match='bse_history_coverage_expired'):
        universes_for_reports(context(reader),source,['2022-12-31'],'2026-11-01',rows,basic_client=CapturedClient)


@pytest.mark.parametrize('scope',['shsz','ashare'])
def test_mixed_year_refresh_keeps_admitted_fact_when_new_basic_changes_old_interval(tmp_path,monkeypatch,scope):
    import json
    import re
    reader,config,rows=seed(tmp_path,monkeypatch,scope);_,original=reader.snapshot()
    config['sources'][0]['reports']=[2021,2022]
    class ChangedBasic(CapturedClient):
        def table(self,kind):
            fields,values=super().table(kind)
            values=deepcopy(values)
            next(row for row in values if row[0]=='sh.600001')[2]='2022-01-01'
            self.fetch.records[-1]['sha256']=self.fetch.objects.put(encode(dict(fields=fields,rows=values)))
            return fields,values
    class MultiYearReports(BseSource):
        def get(self,url,params=None):
            body=super().get(url,params)
            if params and 'filter' in params:
                period=re.search(r"REPORT_DATE='([0-9-]+)'",params['filter']).group(1)
                payload=json.loads(body)
                for row in payload['result']['data']:
                    row['REPORT_DATE']=period+' 00:00:00'
                    if period=='2022-12-31':
                        row['NOTICE_DATE']='2023-03-01 00:00:00'
                        row['UPDATE_DATE']='2023-03-01 00:00:00'
                self.records.pop();return self.capture(encode(payload))
            return body
    monkeypatch.setattr(financial_source,'BaostockClient',ChangedBasic)
    run=refresh(reader,config,as_of='2026-10-30',deadline=monotonic()+30,fetcher_factory=MultiYearReports)
    assert run['status']=='success',run
    _,current=reader.snapshot();key='source.financial_'+scope+'_universe'
    updated=reader.rows(current['source_tables'][key]);old,new=updated
    assert old==rows[0]
    assert 'sh.600001' in old['members'] and 'sh.600001' in new['members']
    assert new['source_basic_sha256']!=old['source_basic_sha256']
    metric='earnings.eps.'+scope
    assert reader.rows(current['datasets'][metric]['partition'])[0]==reader.rows(original['datasets'][metric]['partition'])[0]


def test_mixed_year_after_cutoff_preserves_snapshot_on_missing_year_expiry(tmp_path,monkeypatch):
    reader,config,rows=seed(tmp_path,monkeypatch);before,_=reader.snapshot()
    config['sources'][0]['reports']=[2021,2022]
    run=refresh(reader,config,as_of='2026-11-01',deadline=monotonic()+30,fetcher_factory=BseSource)
    assert run['status']=='failed' and reader.repository.current()==before


def test_report_failure_preserves_same_snapshot_and_universe(tmp_path,monkeypatch):
    reader,config,rows=seed(tmp_path,monkeypatch);before,original=reader.snapshot()
    class Failed(ReportsOnly):
        def get(self,*args,**kwargs):raise SourceFailure('source_request_timeout')
    run=refresh(reader,config,as_of='2026-11-01',deadline=monotonic()+30,fetcher_factory=Failed)
    assert run['status']=='failed' and reader.repository.current()==before
    assert reader.rows(original['source_tables']['source.financial_ashare_universe'])==rows
