"""核对覆盖、任务合并与快照事件聚合的回归。"""

from datetime import datetime, timezone
from decimal import Decimal
from time import monotonic

import pytest
from fastapi.testclient import TestClient
from guanheng_market_client import MarketHTTPError

from guanheng_app.observation import collection, data_repair, etf_flow, wt_margin_summary
from guanheng_app.observation.metadata import validate_fields
from guanheng_app.observation.query import ObservationReader
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.source_fetch import CollectionBudget, SourceFailure
from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from integrations.guanheng.stock_cross_section import project
from integrations.guanheng.daily_data_service import pending_observation_repair, report_observation_repair
from integrations.guanheng_market_client.daily_facts import FIELDS

DAY = '2026-11-13'
NOW = datetime.fromisoformat('2026-11-14T09:00:00+08:00')
DATES = ['2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12', DAY]


def test_margin_summary_checks_wt_fields_instead_of_legacy_chart_dates():
    reader = ObservationReader(None, None)
    reader.rows = {
        'calendar': [dict(date=day, is_open=1) for day in DATES],
        'margin': [dict(date=day, fin_balance=0, fin_buy=1, fin_net_reported=-1,
                        fin_repay=2, short_balance=None if day == DAY else 0, total_balance=0) for day in DATES],
        'legacy': [dict(date=day, short_balance=9) for day in DATES],
    }.__getitem__
    manifest = dict(source_tables={'source.cn_official_calendar':'calendar', wt_margin_summary.TABLE:'margin'},
                    datasets={'leverage_margin':dict(partition='legacy')})
    source = dict(kind=wt_margin_summary.KIND, history_from=DATES[0])
    assert data_repair._coverage_by_input(reader, manifest, source, DAY, lambda: None) == {
        'margin_summary_short_balance': [DAY],
    }


def test_margin_backfill_window_does_not_follow_recent_legacy_chart(tmp_path, monkeypatch):
    reader = build_reader(tmp_path)
    reader.repository.initialize()
    legacy = dict(datasets={'leverage_margin':dict(definition={'primary_field':'fin_balance'}, partition='legacy')})
    monkeypatch.setattr(ObservationReader, 'snapshot', lambda *args: (None, legacy))
    monkeypatch.setattr(ObservationReader, 'rows', lambda *args: [dict(date=DAY, fin_balance=1234)])
    monkeypatch.setattr(collection, 'last_open_day', lambda *args, **kwargs: DAY)
    requests = []

    def history(fetch, start, end, client_factory, *, snapshot_dates):
        requests.append((start, end))
        raise SourceFailure('wt_margin_summary_unavailable')

    monkeypatch.setattr(wt_margin_summary, 'history', history)
    config = dict(timeout_seconds=1, max_days_per_batch=2, allowed_hosts=[],
                  models={'calendars':{'cn':{'coverage_start':DATES[0]}}},
                  budget=dict(seconds=3, max_requests=10, max_bytes=1024, response_bytes=1024),
                  sources=[dict(id='eastmoney.margin', kind=wt_margin_summary.KIND, history_from=DATES[0],
                                overlap_days=1, tables=[wt_margin_summary.TABLE], datasets=['leverage_margin'])])
    receipt = collection.refresh(reader, config, as_of=DAY, now=NOW, deadline=monotonic()+5,
                                 source_ids=['eastmoney.margin'], repair_history_start=DATES[0],
                                 market_client_factory=lambda _: None)['sources'][0]
    assert requests == [(DATES[0], DATES[1])]
    assert receipt['requested_start'] == DATES[0] and receipt['requested_end'] == DATES[1]


@pytest.mark.parametrize('later',['metric','universe'])
def test_t2108_checks_metric_and_universe_over_same_dates(later):
    reader=ObservationReader(None,None)
    reader.rows={
        'calendar':[dict(date=day,is_open=1) for day in DATES],
        'metric':[dict(date=day) for day in DATES[2 if later=='metric' else 0:]],
        'universe':[dict(date=day) for day in DATES[2 if later=='universe' else 0:]],
    }.__getitem__
    manifest=dict(source_tables={'source.cn_official_calendar':'calendar','universe':'universe'},
                  datasets={'metric':dict(partition='metric')})
    source=dict(kind='wt_t2108',tables=['universe'],datasets=['metric'])
    assert data_repair._coverage_by_input(reader,manifest,source,DAY,lambda:None)=={later:DATES[:2]}


def test_t2108_collection_timeout_keeps_the_unread_day_pending(tmp_path,monkeypatch):
    reader=build_reader(tmp_path)
    repo=reader.repository
    repo.initialize()
    repo.publish(dict(source_tables={'source.cn_official_calendar':'calendar'},datasets={}),None)
    monkeypatch.setattr(reader,'rows',{'calendar':[dict(date=DAY,is_open=1)]}.__getitem__)
    monkeypatch.setattr(data_repair,'closed_market_day',lambda *args,**kwargs:DAY)
    config=dict(models={},sources=[dict(id='t2108',kind='wt_t2108',datasets=['t2108.ashare'])])
    def refresh(*args,**kwargs):
        assert kwargs['repair_history_start']==DAY
        return dict(status='failed',sources=[dict(requested_end=DAY,error_code='collection_timeout')])
    job=repo.request_data_repair('manual')
    with repo.scheduler_lease() as lease:
        data_repair.repair(reader,config,job,NOW,lease=lease,deadline=monotonic()+10,
            cancelled=lambda:False,refresh=refresh,market_client_factory=None)
    saved=repo.data_repair()
    assert saved['id']==job['id'] and saved['state']=='running'
    assert saved['scan']['t2108']['next']==DAY


def test_running_job_resumes_and_checks_published_coverage(tmp_path, monkeypatch):
    reader = build_reader(tmp_path)
    reader.repository.initialize()
    manifest = {'source_tables': {'source.cn_official_calendar': 'calendar', 'market.sample': 'market'},
                'datasets': {}}
    reader.repository.publish(manifest, None)
    rows = {'calendar': [dict(date=day, is_open=1) for day in DATES],
            'market': [dict(date=day) for day in DATES[:-1]]}
    monkeypatch.setattr(reader, 'rows', rows.__getitem__)
    monkeypatch.setattr(data_repair, 'closed_market_day', lambda *args, **kwargs: DAY)
    first = reader.repository.request_data_repair('startup')
    assert reader.repository.request_data_repair('manual')['id'] == first['id']
    source = dict(id='wt', kind='wondertrader', tables=['market.sample'])
    config = dict(models={}, sources=[source, dict(id='legacy', kind='disclosure')])

    def refresh(*args, **kwargs):
        repairing=reader.repository.data_repair()['items'][0]
        assert repairing['state'] == 'repairing'
        assert repairing['inputs'] == [dict(id='market.sample',missing_count=1,first_missing=DAY,last_missing=DAY)]
        assert kwargs['source_ids'] == ['wt']
        assert kwargs['repair_history_start'] == DAY
        rows['market'].append(dict(date=DAY))
        return dict(status='success')

    with reader.repository.scheduler_lease() as lease:
        first['state'] = 'running'
        reader.repository.record_data_repair(first, lease=lease)
    with reader.repository.scheduler_lease() as lease:
        resumed = reader.repository.request_data_repair('startup')
        assert resumed['id'] == first['id']
        data_repair.repair(reader, config, resumed, NOW, lease=lease, deadline=monotonic()+10,
                           cancelled=lambda: False, refresh=refresh, market_client_factory=None)
    final = reader.repository.data_repair()
    assert final['id'] == first['id'] and final['state'] == 'partial'
    assert [(item['state'], item['missing_count']) for item in final['items']] == [
        ('complete', 0), ('waiting_for_wt', None)]
    assert final['items'][0]['inputs'] == []
    assert reader.repository.request_data_repair('manual')['id'] != first['id']


def test_wt_receipt_replays_from_index_then_observation_rechecks_coverage(tmp_path, monkeypatch):
    reader = build_reader(tmp_path)
    repo = reader.repository
    repo.initialize()
    repo.publish({'source_tables': {'source.cn_official_calendar': 'calendar', 'market.sample': 'market'},
                  'datasets': {}}, None)
    rows = {'calendar': [dict(date=DAY, is_open=1)], 'market': []}
    monkeypatch.setattr(reader, 'rows', rows.__getitem__)
    monkeypatch.setattr(data_repair, 'closed_market_day', lambda *args, **kwargs: DAY)
    job = repo.request_data_repair('manual')
    config = dict(models={}, schedule=dict(wt_repair_enabled=True),
                  sources=[dict(id='wt', kind='wondertrader', tables=['market.sample'])])
    reads = []
    def refresh(*args, **kwargs):
        reads.append(kwargs['repair_history_start'])
        return dict(status='success')

    def run(lease):
        data_repair.repair(reader, config, repo.data_repair(), NOW, lease=lease, deadline=monotonic()+5,
                           cancelled=lambda: False, refresh=refresh, market_client_factory=None)

    with repo.scheduler_lease() as lease:
        run(lease)
        waiting = repo.data_repair()
        assert waiting['items'][0]['state'] == 'waiting_for_wt_repair'
        assert pending_observation_repair(repo, {}, DAY, NOW) == (job['id'], DAY)
        report_observation_repair(repo, dict(id=job['id'], state='running', phase='readback'), DAY)
        # 观衡读取旧状态后晚到的写入不能覆盖 WT 进度。
        repo.record_data_repair(waiting, lease=lease)
        assert repo.data_repair()['wt_receipt']['state'] == 'running'
        assert repo.data_repair()['wt_receipt']['phase'] == 'readback'
        running = {DAY: dict(observation_repair=dict(id=job['id'], state='running', phase='retry_wait'))}
        assert pending_observation_repair(repo, running, '2026-11-16', NOW) == (job['id'], DAY)
        report_observation_repair(repo, running[DAY]['observation_repair'], DAY)
        assert repo.data_repair()['wt_receipt']['phase'] == 'retry_wait'
        run(lease)
        assert reads == [DAY]
        index = {DAY: dict(observation_repair=dict(id=job['id'], state='published', current_sha256='8'*64))}
        assert pending_observation_repair(repo, index, DAY, NOW) is None
        assert repo.data_repair()['wt_receipt']['current_sha256'] == '8'*64
        report_observation_repair(repo, running[DAY]['observation_repair'], DAY)
        assert repo.data_repair()['wt_receipt']['state'] == 'published'
        assert 'phase' not in repo.data_repair()['wt_receipt']
        waiting['state'] = 'partial'
        repo.record_data_repair(waiting, lease=lease)
        assert repo.data_repair()['state'] == 'running'
        rows['market'].append(dict(date=DAY))
        run(lease)
    final = repo.data_repair()
    assert final['state'] == 'complete' and final['items'][0]['missing_count'] == 0


def test_one_repair_scans_multiple_windows_even_when_first_has_a_permanent_gap(tmp_path, monkeypatch):
    reader = build_reader(tmp_path)
    repo = reader.repository
    repo.initialize()
    repo.publish({'source_tables': {'source.cn_official_calendar': 'calendar', 'market.sample': 'market'},
                  'datasets': {}}, None)
    rows = {'calendar': [dict(date=day, is_open=1) for day in DATES], 'market': []}
    monkeypatch.setattr(reader, 'rows', rows.__getitem__)
    monkeypatch.setattr(data_repair, 'closed_market_day', lambda *args, **kwargs: DAY)
    config = dict(models={}, sources=[dict(id='wt', kind='wondertrader',
        tables=['market.sample'], history_from=DATES[0])])
    ranges = {DATES[0]: DATES[1], DATES[2]: DATES[3], DAY: DAY}
    starts = []

    def refresh(*args, **kwargs):
        first = kwargs['repair_history_start']
        starts.append(first)
        end = ranges[first]
        rows['market'].extend(dict(date=day) for day in DATES[1:] if first <= day <= end)
        return dict(sources=[dict(requested_end=end)])

    with repo.scheduler_lease() as lease:
        data_repair.repair(reader, config, repo.request_data_repair('manual'), NOW,
            lease=lease, deadline=monotonic()+5,cancelled=lambda:False,refresh=refresh,market_client_factory=None)
    status = repo.data_repair()
    assert starts == list(ranges)
    assert status['state'] == 'partial'
    assert status['items'][0]['inputs']==[
        dict(id='market.sample',missing_count=1,first_missing=DATES[0],last_missing=DATES[0])]


@pytest.mark.parametrize('legacy',[False,True])
def test_wt_receipt_replays_multiple_windows_after_restart_without_advancing_target(tmp_path, monkeypatch, legacy):
    reader=build_reader(tmp_path)
    repo=reader.repository
    repo.initialize()
    repo.publish({'source_tables':{'source.cn_official_calendar':'calendar','market.sample':'market'},
                  'datasets':{}},None)
    next_day='2026-11-16'
    initial=datetime.fromisoformat(DAY+'T21:00:00+08:00')
    replay_at=datetime.fromisoformat('2026-11-14T09:00:00+08:00')
    later=datetime.fromisoformat(next_day+'T16:00:00+08:00')
    rows={'calendar':[dict(date=day,is_open=1) for day in [*DATES,next_day]],'market':[]}
    monkeypatch.setattr(data_repair,'closed_market_day',lambda now,*args,**kwargs:
        DAY if now==initial else next_day)
    config=dict(models={},schedule=dict(wt_repair_enabled=True),sources=[
        dict(id='wt',kind='wondertrader',tables=['market.sample'],history_from=DATES[0])])
    windows={DATES[0]:DATES[1],DATES[2]:DATES[3],DAY:DAY}
    initial_window=initial.isoformat()
    reads=[]

    def reopen_and_repair(now,window,refresh):
        reopened=build_reader(tmp_path)
        monkeypatch.setattr(reopened,'rows',rows.__getitem__)
        with reopened.repository.scheduler_lease() as lease:
            data_repair.repair(reopened,config,reopened.repository.data_repair(),now,lease=lease,
                deadline=monotonic()+10,cancelled=lambda:False,refresh=refresh,
                market_client_factory=None,window=window)

    def refresh(*args, **kwargs):
        first=kwargs['repair_history_start']
        assert kwargs['now']==(initial if len(reads)<3 else later)
        reads.append((first,kwargs['as_of']))
        if len(reads)==5:
            return dict(status='another_owner_running')
        end=windows[first]
        if len(reads)>3:
            rows['market'].extend(dict(date=day) for day in DATES if first<=day<=end)
        return dict(sources=[dict(requested_end=end)])

    job=repo.request_data_repair('manual')
    reopen_and_repair(initial,initial_window,refresh)
    assert reads==[(day,DAY) for day in windows]
    if legacy:
        with repo.scheduler_lease() as lease:
            old=repo.data_repair()
            del old['scan_clock']
            repo.record_data_repair(old,lease=lease)
    assert pending_observation_repair(repo,{},DAY,replay_at)==(job['id'],DAY)
    index={DAY:dict(observation_repair=dict(id=job['id'],state='published',current_sha256='8'*64))}
    assert pending_observation_repair(repo,index,DAY,replay_at) is None
    reopen_and_repair(later,later.isoformat(),refresh)
    mid=repo.data_repair()
    assert mid['id']==job['id'] and mid['window']==initial_window
    assert mid['scan']['wt']['phase']=='published' and mid['scan']['wt']['next']==DATES[2]
    reopen_and_repair(later,later.isoformat(),refresh)
    final=repo.data_repair()
    assert reads==[(day,DAY) for day in [*windows,DATES[0],DATES[2],DATES[2],DAY]]
    assert final['id']==job['id'] and final['state']=='complete' and final['window']==initial_window


def test_repair_resumes_checkpoint_after_budget_expires(tmp_path, monkeypatch):
    reader = build_reader(tmp_path)
    repo = reader.repository
    repo.initialize()
    repo.publish({'source_tables': {'source.cn_official_calendar': 'calendar', 'market.sample': 'market'},
                  'datasets': {}}, None)
    rows = {'calendar': [dict(date=day, is_open=1) for day in DATES], 'market': []}
    monkeypatch.setattr(reader, 'rows', rows.__getitem__)
    monkeypatch.setattr(data_repair, 'closed_market_day', lambda *args, **kwargs: DAY)
    config = dict(models={}, sources=[dict(id='wt',kind='wondertrader',tables=['market.sample'],history_from=DATES[0])])
    job = repo.request_data_repair('startup')
    starts = []
    expire_at = None
    queries = 0

    def clock():
        # 第一窗口后覆盖核对完成，在调度继续下一窗口前耗尽预算。
        nonlocal queries
        if expire_at is not None and len(starts) == 1:
            queries += 1
            if queries == 2:
                return expire_at
        return 0

    def refresh(*args, **kwargs):
        first = kwargs['repair_history_start']
        starts.append(first)
        end = DATES[1] if first == DATES[0] else DAY
        rows['market'].extend(dict(date=day) for day in DATES if first <= day <= end)
        return dict(sources=[dict(requested_end=end)])

    monkeypatch.setattr(data_repair, 'monotonic', clock)
    with repo.scheduler_lease() as lease:
        expire_at = monotonic()+10
        data_repair.repair(reader,config,job,NOW,lease=lease,deadline=expire_at,
            cancelled=lambda:False,refresh=refresh,market_client_factory=None)
    mid=repo.data_repair()
    assert mid['state']=='running' and starts==[DATES[0]]
    assert mid['start_after']=='wt' and mid['scan']['wt']['next']==DATES[2]
    with repo.scheduler_lease() as lease:
        expire_at=None
        data_repair.repair(reader,config,mid,NOW,lease=lease,deadline=monotonic()+10,
            cancelled=lambda:False,refresh=refresh,market_client_factory=None)
    assert starts==[DATES[0],DATES[2]]
    assert repo.data_repair()['state']=='complete'


def test_busy_collection_retains_window_and_oversized_stock_window_is_split(tmp_path, monkeypatch):
    reader=build_reader(tmp_path)
    repo=reader.repository
    repo.initialize()
    repo.publish({'source_tables':{'source.cn_official_calendar':'calendar','source.stock':'stock'},
                  'datasets':{}},None)
    rows={'calendar':[dict(date=day,is_open=1) for day in DATES],'stock':[]}
    monkeypatch.setattr(reader,'rows',rows.__getitem__)
    monkeypatch.setattr(data_repair,'closed_market_day',lambda *args,**kwargs:DAY)
    config=dict(models={},sources=[dict(id='wt',kind=data_repair.WT_STOCK_KIND,
        tables=['source.stock'],history_from=DATES[0])])
    calls=[]
    def refresh(*args, **kwargs):
        start=kwargs['repair_history_start']
        end=kwargs.get('repair_history_end',DAY)
        calls.append((start,end))
        if len(calls)==1:
            return dict(status='another_owner_running')
        if len(calls)==2:
            return dict(status='failed',sources=[dict(requested_end=end,error_code='request_budget_exceeded')])
        rows['stock'].extend(dict(date=day,sample_count=5000) for day in DATES if start<=day<=end)
        return dict(status='success',sources=[dict(requested_end=end)])
    job=repo.request_data_repair('manual')
    for _ in range(2):
        with repo.scheduler_lease() as lease:
            data_repair.repair(reader,config,repo.data_repair(),NOW,lease=lease,deadline=monotonic()+5,
                cancelled=lambda:False,refresh=refresh,market_client_factory=None)
    assert calls==[(DATES[0],DAY),(DATES[0],DAY),(DATES[0],DATES[2]),(DATES[3],DAY)]
    assert repo.data_repair()['state']=='complete' and repo.data_repair()['id']==job['id']


@pytest.mark.parametrize('gap', [False, True])
def test_recent_events_use_closed_dates_and_keep_unknown_state(gap):
    reader = ObservationReader(None, None)
    reader.rows = {
        'calendar': [dict(date='2026-11-06', is_open=1)] +
                    [dict(date=day, is_open=1) for day in DATES] + [dict(date='2026-11-14', is_open=0)],
        'data': [dict(date='2026-11-06', event=1)] +
                [dict(date=day, event=None if gap and day == DAY else int(day == '2026-11-10')) for day in DATES],
    }.__getitem__
    manifest = dict(published_at=NOW.isoformat(), source_tables={'source.cn_official_calendar': 'calendar'},
                    datasets={'event': dict(partition='data', definition=dict(board='a',
                        event_markers=dict(field='event', values=[dict(code=1, label='触发')]))),
                        'legacy': dict(partition='fixed-notes', definition=dict(board='legacy',
                            event_markers=[dict(date=DAY, key='close', name='历史坐标标注',
                                                position='top', value=100)]))})
    assert reader.recent_events(manifest) == {
        'a': dict(state='incomplete' if gap else 'complete', events=[dict(date='2026-11-10', label='触发')])}


def test_etf_flow_uses_only_qualified_price_segment_from_current_snapshot(tmp_path, monkeypatch):
    from types import SimpleNamespace
    sessions = [dict(date=day, is_open=1) for day in DATES]
    monkeypatch.setattr(etf_flow, 'official_calendar', lambda *args, **kwargs: (sessions, None))
    reader = build_reader(tmp_path)
    fetch = SimpleNamespace(objects=reader.objects, records=[], timeout=10, budget=CollectionBudget(monotonic()+10))
    symbol = 'SSE.510300'

    class Client:
        def source_market_snapshot_query(self, day):
            if day == DAY:
                raise MarketHTTPError(503, dict(status=dict(code='Unavailable')))
            assert day == DATES[-2]
            return dict(status=dict(code='Ok'), data=dict(snapshot_id='version', observation_date=day,
                provenance=dict(supplement_facts_sha256='shares')))

        def source_daily_history_batch_query(self, request):
            assert request['to'] == 20261111 and request['snapshot_id'] == 'version'
            bars = [dict(date=20261109+i, close=4.0) for i in range(3)]
            return dict(status=dict(code='Ok'), data=dict(results=[dict(symbol=symbol, status=dict(code='Ok'),
                data=dict(bars=bars,source_snapshot_id='version',metadata=dict(adjustment='none',price_unit='unknown'),
                    provenance=[dict(offset=0,count=2,metadata=dict(price_unit='CNY')),
                                dict(offset=2,count=1,metadata=dict(price_unit='unknown'))]))]))

        def source_supplement_query(self, request):
            assert request['to'] == DATES[2] and request['snapshot_id'] == 'version'
            return dict(status=dict(code='Ok'),data=dict(source_snapshot_id='version',source_sha256='shares',
                rows=[dict(date=day,symbol=symbol,value=str(100_000_000*(1+i)),unit='share')
                      for i,day in enumerate(DATES[:3])],selection=dict(next_offset=None)))

    result = etf_flow.history(fetch,dict(symbols=[symbol]),DATES[1],DATES[2],lambda _:Client(),
        calendar=dict(coverage_start=DATES[0],coverage_end=DAY),snapshot_dates=[DAY,DATES[-2]])
    assert [(row['date'],row['close'],row['flow']) for row in result[etf_flow.metric(symbol)]] == [
        (DATES[1],4.0,4.0),(DATES[2],None,None)]
    assert len(fetch.records)==4


def test_etf_flow_retains_real_zero_and_keeps_gap_on_the_next_day():
    rows = etf_flow.calculate(DATES, DATES[1], dict.fromkeys(DATES, 4.0),
                              {DATES[0]: Decimal(100_000_000), DATES[1]: Decimal(100_000_000),
                               DATES[3]: Decimal(125_000_000), DATES[4]: Decimal(100_000_000)})
    assert [row['flow'] for row in rows] == [0, None, None, -1]
    validate_fields(etf_flow.definition('SSE.510300'), rows)


def test_csi300_etf_cap_keeps_index_line_when_fund_or_denominator_is_missing():
    from guanheng_market_client.supplement_facts import CSI300_INDEX
    days=DATES[:3]
    close={symbol:dict.fromkeys(days,4.0) for symbol in etf_flow.CAP_FUNDS}
    close[CSI300_INDEX]=dict.fromkeys(days,4016.29)
    shares={symbol:dict.fromkeys(days,Decimal(100_000_000)) for symbol in etf_flow.CAP_FUNDS}
    del shares[etf_flow.CAP_FUNDS[0]][days[1]]
    denominator={day:Decimal(80_000_000_000) for day in days[:2]}
    rows=etf_flow.cap_rows(days,close,shares,denominator)
    validate_fields(etf_flow.cap_definition(),rows)
    assert [row['index_close'] for row in rows]==[4016.29]*3
    assert [row['etf_cap'] for row in rows]==[16,None,16]
    assert [row['ratio'] for row in rows]==[2,None,None]


def test_repair_post_is_local_same_origin_and_deduplicated(tmp_path):
    reader = build_reader(tmp_path)
    reader.repository.initialize()
    with reader.repository.scheduler_lease() as lease:
        reader.repository.record_scheduler(dict(enabled=True, state='running', phase='waiting',
            last_heartbeat=datetime.now(timezone.utc).isoformat(), heartbeat_max_age_seconds=60,
            schedule=dict(timezone='Asia/Shanghai', times=['09:00']), error_code=None), lease=lease)
        first = reader.repository.request_data_repair('startup')
    app = create_app(settings=ConsoleSettings(observation_root=str(tmp_path)))
    with TestClient(app, client=('127.0.0.1', 1234), base_url='http://127.0.0.1') as client:
        path = '/v1/ui/market-observation/data-repair'
        assert client.post(path).status_code == 403
        assert client.post(path, headers={'origin': 'https://example.test', 'sec-fetch-site': 'cross-site'}).status_code == 403
        headers = {'origin': 'http://127.0.0.1', 'sec-fetch-site': 'same-origin'}
        assert client.post(path, headers=headers | {'x-forwarded-host': 'example.test'}).status_code == 403
        response = client.post(path, headers=headers)
        assert response.status_code == 202
        assert response.json()['id'] == first['id']
        assert client.post('/v1/market-observation/data-repair', headers=headers).status_code == 405


def test_bigquant_projection_uses_the_wt_trading_universe():
    symbols = ['SSE.600000', 'SZSE.000001', 'SZSE.000002']
    facts = dict(
        schema='guanheng.daily-source-facts.v1', date=DAY, members=symbols, fields=FIELDS,
        rows=[[DAY, symbols[0], '11', '10', '100', '', '1', 'qualified'],
              [DAY, symbols[1], '9', '10', '200', '', '1', 'qualified'],
              [DAY, symbols[2], '', '', '', '', '0', 'qualified']],
        units=dict(close_reference='CNY', preclose='CNY', volume='share', turn='percent_of_float'),
        stats=dict(identity_unverified_count=0, state_unverified_count=0, missing_float_count=0,
                   special_reference_count=0, halted_with_trades_count=0),
        provenance=dict(packet_sha256='a'*64, universe_sha256='b'*64, source_received_at=datetime.now(timezone.utc).isoformat()),
        source_sha256='c'*64, source_snapshot_id='d'*64,
    )
    quote = lambda symbol, close, amount: dict(date=DAY, instrument=symbol, close=close, pre_close=10, amount=amount)
    records = [quote('600000.SH', 11, 100), quote('000001.SZ', 9, 300),
               quote('000002.SZ', 10, None), quote('000003.SZ', 10, 100_000)]
    row = project(facts, records)
    assert row['sample_count'] == 2 and row['top5_pct'] == 75
    assert row['median_return_pct'] == pytest.approx(0)
    with pytest.raises(ValueError, match='members_missing'):
        project(facts, records[:2])
    with pytest.raises(ValueError, match='price_mismatch'):
        project(facts, [quote('600000.SH', 12, 100), *records[1:]])
