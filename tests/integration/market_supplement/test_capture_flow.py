"""采集→持久恢复→原件→标准查询；故障按业务条件注入。"""
import json
from decimal import Decimal
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).parent))
from msf_fixture import ContentStore,DAYS,FrozenFetch,QmtTransport,plan,query
import pytest

from integrations.guanheng import market_supplement_capture as capture
from integrations.guanheng import stock_cross_section
from integrations.guanheng import market_supplement_sources as public_sources
from integrations.guanheng.market_supplement_store import MarketSupplementStore
from integrations.guanheng_market_client import MarketProtocolError
from integrations.guanheng_market_client.supplement_facts import GOV10Y_SCOPE,GOV10Y_YIELD
from guanheng_qmt_shm.read_retention_client import RetainedReadPending
from guanheng_app.observation.source_fetch import SourceFailure
from guanheng_app.observation.gov10y_source import TABLE,URL
from guanheng_app.observation.wt_gov10y_source import TABLE as WT_GOV10Y_TABLE, history as read_gov10y
from guanheng_app.observation.refresh_models import spread_and_bond
from types import SimpleNamespace


def collect(root,targets,fetch,transport,**kwargs):
    return capture.collect_supplement(targets,DAYS[-1],DAYS,root/'work',objects=ContentStore(root/'raw'),
        fetch=fetch,qmt_transport=transport,calendar_coverage=(DAYS[0],DAYS[-1]),deadline=time.monotonic()+20,**kwargs)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows Job owns the SDK process tree')
@pytest.mark.parametrize('stopped', [False, True])
@pytest.mark.parametrize('termination_fails', [False, True])
def test_bigquant_waits_for_the_interpreter_tree_before_releasing_its_output(monkeypatch, stopped, termination_fails):
    events = []
    clock = [0.]

    class Job:
        assigned = False
        active = 1

        def attach_and_resume(self, process, *, deadline):
            self.assigned = True
            clock[0] = deadline

        def terminate(self):
            events.append('terminate')
            if termination_fails:
                raise OSError('fixture Job termination failed')

        def active_processes(self):
            return self.active

        def close(self):
            assert termination_fails or self.active == 0, 'SDK descendant can still hold the output file'
            events.append('close')

    job = Job()

    class Process:
        def poll(self):
            return None if job.active else 1

        def wait(self, timeout):
            assert job.active == 0
            events.append('wait')

    def sleep(seconds):
        assert events == ['terminate']
        job.active = 0
        clock[0] += seconds

    monkeypatch.setitem(sys.modules, 'integrations.guanheng._process_job', SimpleNamespace(ProcessJob=lambda: job))
    monkeypatch.setattr(stock_cross_section, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(stock_cross_section.subprocess, 'Popen', lambda *args, **kwargs: Process())
    monkeypatch.setattr(stock_cross_section, 'sleep', sleep)
    policy = dict(bigquant_python=sys.executable, timeout_seconds=1)
    with pytest.raises(InterruptedError if stopped else ValueError) as result:
        stock_cross_section.acquire_bigquant(policy, DAYS[-1], deadline=30, cancelled=lambda: stopped,
                                            environ={'GUANHENG_BIGQUANT_CREDENTIAL':'fixture'})
    if termination_fails:
        assert events == ['terminate', 'close']
        assert result.value.__notes__ == ['BigQuant cleanup: OSError']
    else:
        assert events == ['terminate', 'wait', 'close']


@pytest.mark.parametrize('failure', [
    'early', 'deadline', 'stopped', 'no-credential', 'cleanup', 'terminal-cancellation',
])
def test_daily_stock_fallback_retries_under_one_query_deadline(tmp_path, monkeypatch, failure):
    from integrations.guanheng_market_client.daily_facts import FIELDS, STATS

    day = DAYS[-1]
    facts = dict(schema='guanheng.daily-source-facts.v1', date=day, members=['SSE.600000'], fields=FIELDS,
        rows=[[day, 'SSE.600000', '2', '1', '100', '1', '1', 'qualified']],
        units=dict(close_reference='CNY', preclose='CNY', volume='share', turn='percent_of_float'),
        stats={name: 0 for name in STATS},
        provenance=dict(packet_sha256='a'*64, universe_sha256='b'*64, source_received_at='2026-11-06T00:00:00+00:00'))
    clock = [0.]
    stop_requested = [False]
    calls = []

    def acquire(policy, requested, *, deadline, cancelled, environ):
        assert requested == day
        calls.append(deadline)
        if len(calls) == 1:
            clock[0] = 15. if failure == 'deadline' else 3.
            if failure == 'stopped':
                raise InterruptedError('fixture cancellation')
            if failure in ('early', 'terminal-cancellation'):
                raise stock_cross_section.BigQuantWorkerExit('fixture SDK failure')
            if failure == 'cleanup':
                failure_with_cleanup = ValueError('fixture output cap')
                failure_with_cleanup.add_note('BigQuant cleanup: OSError')
                raise failure_with_cleanup
            raise ValueError('bigquant_unavailable')
        if failure == 'terminal-cancellation':
            stop_requested[0] = True
            raise stock_cross_section.BigQuantWorkerExit('fixture SDK failure')
        return [dict(date=day, instrument='600000.SH', close=2, pre_close=1, amount=100)]

    monkeypatch.setattr(stock_cross_section, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(stock_cross_section, 'acquire_bigquant', acquire)
    env = {} if failure == 'no-credential' else {'GUANHENG_BIGQUANT_CREDENTIAL': 'fixture'}
    arguments = dict(deadline=15., cancelled=lambda: stop_requested[0], environ=env)
    policy = dict(timeout_seconds=30, minimum_sample_count=1)
    cache = {'sha256': 'c'*64}
    objects = ContentStore(tmp_path)
    if failure in ('stopped', 'terminal-cancellation'):
        with pytest.raises(InterruptedError):
            stock_cross_section.prepare_section(facts, cache, None, policy, objects, **arguments)
        assert calls == ([15.] if failure == 'stopped' else [15., 15.])
        return
    result = stock_cross_section.prepare_section(facts, cache, None, policy, objects, **arguments)
    if failure == 'early':
        assert calls == [15., 15.]
        assert result['provider'] == 'BigQuant' and result['sample_count'] == 1
        assert json.loads(objects.get(result['source_sha256']))['date'] == day
    else:
        assert calls == [15.] and result == {'reason': 'bigquant_unavailable'}


def test_required_pending_recovers_only_missing_and_cache_extends(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'))
    fetch,transport=FrozenFetch(bad_day=DAYS[-1]),QmtTransport()
    with pytest.raises(capture.SupplementPending):collect(tmp_path,targets,fetch,transport)
    assert not (tmp_path/'work/catalog.json').exists()
    before=json.loads((tmp_path/'work/STATE.json').read_bytes())['rows']
    assert len(before)==1
    fetch.bad_day=None
    descriptor=collect(tmp_path,targets,fetch,transport)
    store=MarketSupplementStore(descriptor)
    try:
        rows=store.query(query())['rows'];assert len(rows)==2
        assert rows[0]==next(iter(before.values()))
        assert {r['value'] for r in rows}=={'1750001250'}
        assert all(r['unit']=='share' and r['available_at'] is None for r in rows)
        store.verify_sources()
    finally:store.close()
    assert len(fetch.calls)==3  # 第一天没有重抓；错日第二天原件没有成为永久负缓存。
    counts=len(fetch.calls)
    assert collect(tmp_path,targets,fetch,transport)==descriptor
    assert len(fetch.calls)==counts
    # 同对象库的新任务复用完整旧行，连原received_at也保持。
    next_root=tmp_path/'next';next_root.mkdir()
    result=capture.collect_supplement(targets,DAYS[-1],DAYS,next_root,objects=ContentStore(tmp_path/'raw'),
        fetch=fetch,qmt_transport=transport,previous=descriptor,calendar_coverage=(DAYS[0],DAYS[-1]),deadline=time.monotonic()+20)
    reused=json.loads(Path(result['path']).read_bytes())['rows']
    assert reused==rows and len(fetch.calls)==counts


def test_binding_unknown_never_enters_external_fallback(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport(binding_pending=True)
    with pytest.raises(RetainedReadPending):collect(tmp_path,plan(('etf_total_shares','SSE.510300')),fetch,transport)
    assert fetch.calls==[]
    assert not (tmp_path/'work/catalog.json').exists()
    assert transport.sdk_calls==[]


def test_margin_purchase_keeps_provider_scope_and_distinct_value(tmp_path):
    targets=plan(('margin_purchase','CN.MARGIN_REPORT'),('margin_balance','CN.MARGIN_REPORT'))
    descriptor=collect(tmp_path,targets,FrozenFetch(),QmtTransport())
    store=MarketSupplementStore(descriptor)
    try:
        purchase=store.query(query(metric='margin_purchase',symbols=['CN.MARGIN_REPORT']))
        balance=store.query(query(metric='margin_balance',symbols=['CN.MARGIN_REPORT']))
        assert {(r['value'],r['unit'],r['source']) for r in purchase['rows']}=={('125000000','CNY','Eastmoney')}
        assert {r['value'] for r in balance['rows']}=={'12345678900'}
        assert [row['metric'] for row in balance['qmt_evidence']['decisions']]==['margin_balance']
    finally:store.close()


def test_gov10y_published_facts_feed_spread_and_keep_missing_day(tmp_path):
    class ChinaBondFetch(FrozenFetch):
        def get(self, url, params, referer):
            assert url == URL
            self.budget.request()
            self.calls.append((params['startDate'], params['endDate']))
            day = params['endDate']
            # 最后一日缺国债行，仅有同日政策性金融债。前一日两个期限数值不同。
            curve = '中债国开债收益率曲线' if day == DAYS[-1] else '中债国债收益率曲线'
            body = (f'<table><tr><th>曲线</th><th>日期</th><th>5年</th><th>10年</th></tr>'
                    f'<tr><td>{curve}</td><td>{day}</td><td>1.50</td><td>1.7200</td></tr></table>').encode()
            self.budget.consume(len(body))
            return body

    targets = plan((GOV10Y_YIELD, GOV10Y_SCOPE), required=False)
    targets['external_fallback'] = ['ChinaBond']
    fetch = ChinaBondFetch()
    descriptor = collect(tmp_path, targets, fetch, QmtTransport())
    store = MarketSupplementStore(descriptor)
    identity = '1' * 64
    requested = []

    class WTClient:
        def source_market_snapshot_query(self, day):
            return dict(status={'code': 'Ok'}, data=dict(observation_date=day, snapshot_id=identity,
                provenance={'supplement_facts_sha256': descriptor['sha256']}))

        def source_supplement_query(self, request):
            requested.append(request)
            return dict(status={'code': 'Ok'}, data=store.query(request))

    try:
        store.verify_sources()
        found = store.query(query(metric=GOV10Y_YIELD, symbols=[GOV10Y_SCOPE]))
        assert [(row['date'], row['value'], row['unit'], row['source']) for row in found['rows']] == [
            (DAYS[0], '1.72', 'pct', 'ChinaBond')]
        assert [gap['date'] for gap in found['gaps']] == [DAYS[-1]]
        reader = SimpleNamespace(budget=fetch.budget, timeout=5, records=[], objects=ContentStore(tmp_path/'observer'))
        tables = read_gov10y(reader, DAYS[0], DAYS[-1], lambda _: WTClient(), snapshot_dates=[DAYS[-1]])
        assert tables == {WT_GOV10Y_TABLE: [{'date': DAYS[0], 'gov10y_pct': 1.72}]}
        assert requested == [query(metric=GOV10Y_YIELD, symbols=[GOV10Y_SCOPE])]
        assert [record['kind'] for record in reader.records] == ['wt_market_snapshot', 'wt_supplement_gov10y']
        tables[TABLE] = [dict(date=DAYS[0], gov10y_pct=1.5), dict(date=DAYS[-1], gov10y_pct=1.6)]
        datasets = {'spread_sw': [dict(date=day, pe=10) for day in DAYS]}
        spread_and_bond(tables, datasets, {})
        assert datasets['spread_sw'][0]['spread'] == pytest.approx(8.28)
        assert datasets['spread_sw'][-1]['spread'] == pytest.approx(8.4)
        assert read_gov10y(reader, DAYS[-1], DAYS[-1], lambda _: WTClient(),
                           snapshot_dates=[DAYS[-1]]) == {WT_GOV10Y_TABLE: []}
    finally:
        store.close()


def test_margin_purchase_recovers_omitted_day_from_range(tmp_path):
    days=['2026-11-02','2026-11-03',*DAYS]
    targets=plan(('margin_purchase','CN.MARGIN_REPORT'),required=False)
    targets['targets'][0]['from']=days[0]

    class HistoryFetch(FrozenFetch):
        def get(self,url,params=None,referer=None):
            if '>=' not in params['filter']:
                return super().get(url,params,referer)
            self.budget.request()
            self.calls.append((url,params.copy()))
            selected=days[:3:2]
            body=json.dumps(dict(success=True,result=dict(count=len(selected),pages=1,data=[
                dict(STATISTICS_DATE=day+' 00:00:00',FIN_BUY_AMT='1.25') for day in selected]))).encode()
            self.budget.consume(len(body))
            return body

    fetch=HistoryFetch()
    def run(directory,previous=None):
        return capture.collect_supplement(targets,days[-1],days,tmp_path/directory,objects=ContentStore(tmp_path/'raw'),
            fetch=fetch,qmt_transport=QmtTransport(),calendar_coverage=(days[0],days[-1]),deadline=time.monotonic()+20,
            previous=previous)

    previous=run('first')
    before=json.loads(Path(previous['path']).read_bytes())
    assert [row['date'] for row in before['rows']]==[days[0],days[2],days[-1]]
    assert [(gap['date'],gap['reason']) for gap in before['gaps']]==[(days[1],'source_record_missing')]
    assert len(fetch.calls)==2 and fetch.calls[1][1]['pageSize']=='500'
    store=ContentStore(tmp_path/'raw')
    assert len({json.loads(store.get(row['source_sha256']))['parents'][0] for row in before['rows'][:2]})==1
    after=json.loads(Path(run('retry',previous)['path']).read_bytes())
    assert after['complete'] and [row for row in after['rows'] if row['date']!=days[1]]==before['rows']
    assert len(fetch.calls)==3


def test_ipo_proceeds_listing_scope_and_missing_amount(tmp_path):
    days=['2026-11-02','2026-11-03',*DAYS]
    targets=plan(('ipo_gross_proceeds','CN.SH_SZ'),required=False)
    targets['targets'][0]['from']=days[0]

    class IPOFetch(FrozenFetch):
        def get(self,url,params=None,referer=None):
            assert params['reportName']=='RPTA_APP_IPOAPPLY'
            self.budget.request()
            self.calls.append((url,params))
            if days[-1] in params['filter']:
                return b'{"success":false,"code":9201,"result":null}'
            rows=[dict(LISTING_DATE=day+' 00:00:00',SECUCODE=symbol,SECURITY_TYPE_CODE='058001001',TOTAL_RAISE_FUNDS=amount)
                  for day,symbol,amount in ((days[0],'688827.SH','7.771246'),(days[0],'001381.SZ','1.228754'),
                                            (days[1],'920085.BJ',None),(days[2],'001382.SZ',None))]
            return json.dumps(dict(success=True,result=dict(count=len(rows),pages=1,data=rows))).encode()

    descriptor=capture.collect_supplement(targets,days[-1],days,tmp_path/'work',objects=ContentStore(tmp_path/'raw'),
        fetch=IPOFetch(),qmt_transport=QmtTransport(),calendar_coverage=(days[0],days[-1]),deadline=time.monotonic()+20)
    store=MarketSupplementStore(descriptor)
    try:
        page=store.query(query(metric='ipo_gross_proceeds',symbols=['CN.SH_SZ'],**{'from':days[0],'to':days[-1]}))
        assert [(row['date'],row['value']) for row in page['rows']]==[(days[0],'900000000'),(days[1],'0'),(days[-1],'0')]
        assert [(row['date'],row['reason']) for row in page['gaps']]==[(days[2],'source_record_missing')]
        store.verify_sources()
    finally:store.close()


def test_shareholder_reduction_maps_weekend_and_records_unpriced_details(tmp_path):
    calendar=['2026-11-06','2026-11-09','2026-11-10','2026-11-11']
    targets=plan(('shareholder_reduction_gross','CN.SH_SZ'),required=False)
    targets['targets'][0]['from']=calendar[1]

    def event(code,notice,quantity,price=None,reference=None):
        return dict(SECURITY_CODE=code,NOTICE_DATE=notice,TRADE_DATE='2026-11-06',HOLDER_NAME='股东',
                    CHANGE_NUM=abs(quantity),CHANGE_NUM_SYMBOL=quantity,TRADE_AVERAGE_PRICE=price,
                    CLOSE_PRICE=reference,START_DATE='2026-11-04',END_DATE='2026-11-06',EITIME=notice,
                    DIRECTION='减持' if quantity<0 else '增持',MARKET='二级市场')

    class ReductionFetch(FrozenFetch):
        def get(self,url,params=None,referer=None):
            self.budget.request()
            self.calls.append((url,params))
            assert params['reportName']=='RPT_SHARE_HOLDER_INCREASE'
            if calendar[-1] in params['filter']:
                return json.dumps(dict(success=False,code=9201,result=None,message='返回数据为空')).encode()
            assert "NOTICE_DATE>='2026-11-07'" in params['filter']
            rows=[event('688485','2026-11-07',-5,price=6),event('600003','2026-11-08',20,price=100),
                  event('000001','2026-11-09',-2,reference=10),event('920086','2026-11-09',-40),
                  event('300100','2026-11-10',-1)]
            return json.dumps(dict(success=True,result=dict(count=len(rows),pages=1,data=rows))).encode()

    descriptor=capture.collect_supplement(targets,calendar[-1],calendar,tmp_path/'work',objects=ContentStore(tmp_path/'raw'),
        fetch=ReductionFetch(),qmt_transport=QmtTransport(),calendar_coverage=(calendar[0],calendar[-1]),deadline=time.monotonic()+20)
    store=MarketSupplementStore(descriptor)
    try:
        page=store.query(query(metric='shareholder_reduction_gross',symbols=['CN.SH_SZ'],**{'from':calendar[1],'to':calendar[-1]}))
        assert [(row['date'],row['value']) for row in page['rows']]==[(calendar[1],'500000'),(calendar[-1],'0')]
        assert [(gap['date'],gap['reason'])for gap in page['gaps']]==[(calendar[2],'source_record_missing')]
        store.verify_sources()
    finally:store.close()


def test_shareholder_reduction_reuses_local_reference_and_excludes_timing_conflicts():
    import hashlib
    day='2026-11-09';calls=[]
    def event(code,trade):
        return dict(SECURITY_CODE=code,NOTICE_DATE=day,TRADE_DATE=trade,HOLDER_NAME='股东',
            CHANGE_NUM=2,CHANGE_NUM_SYMBOL=-2,TRADE_AVERAGE_PRICE=None,CLOSE_PRICE=None,
            START_DATE='2026-11-01',END_DATE=trade,EITIME=day,DIRECTION='减持',MARKET='二级市场')
    body=json.dumps(dict(success=True,result=dict(count=2,pages=1,data=[event('600001','2026-11-06'),event('600002','2026-11-10')]))).encode()
    def get(*args):return dict(body=body,sha256=hashlib.sha256(body).hexdigest(),received_at='2026-11-10T00:00:00Z')
    def reference(code,trade):calls.append((code,trade.isoformat()));return 7
    rows=public_sources.shareholder_reduction_history([day],['2026-11-06',day],get,reference_close=reference)
    assert rows[day]['value']=='140000' and calls==[('600001','2026-11-06')]
    assert rows[day]['calculation']['estimated_count']==1
    assert rows[day]['calculation']['timing_conflict_count']==1


@pytest.mark.parametrize('corrupt_input',['report','price','price_book'])
def test_normal_reduction_owner_reads_local_price_reuses_result_and_checks_inputs(tmp_path,monkeypatch,corrupt_input):
    import hashlib
    import integrations.guanheng.source_market as local_market
    import integrations.guanheng_market_client as market_client
    day='2026-11-09';calendar=['2026-11-06',day];base=dict(mode='source-catalog',fixture='local-only');native_calls=[]
    class Local:
        def call(self,request):
            native_calls.append(request)
            assert request['action']=='history.source-daily-query'and request['request']['code']=='600001'
            return dict(status=dict(code='Ok'),data=dict(metadata=dict(adjustment='none',factor_version=''),
                bars=[dict(date=20261105,close=7),dict(date=20261110,close=99)]))
        def close(self):pass
    def create(configuration):assert configuration==base;return Local()
    monkeypatch.setattr(local_market,'create_native_source_market',create)
    monkeypatch.setattr(market_client,'validate_response',lambda value,request:value)
    class Reports(FrozenFetch):
        def get(self,url,params=None,referer=None):
            self.budget.request()
            event=dict(SECURITY_CODE='600001',NOTICE_DATE=day,TRADE_DATE='2026-11-06',HOLDER_NAME='股东',
                CHANGE_NUM=2,CHANGE_NUM_SYMBOL=-2,TRADE_AVERAGE_PRICE=None,CLOSE_PRICE=None,
                START_DATE='2026-11-01',END_DATE='2026-11-06',EITIME=day,DIRECTION='减持',MARKET='二级市场')
            return json.dumps(dict(success=True,result=dict(count=1,pages=1,data=[event]))).encode()
    objects=ContentStore(tmp_path/'raw');targets=plan(('shareholder_reduction_gross','CN.SH_SZ'),required=False);targets['targets'][0]['from']=day
    def run():return capture.collect_supplement(targets,day,calendar,tmp_path/'work',objects=objects,fetch=Reports(),
        qmt_transport=QmtTransport(),calendar_coverage=(calendar[0],calendar[-1]),deadline=time.monotonic()+20,reference_base=base)
    descriptor=run();assert run()==descriptor and len(native_calls)==1
    store=MarketSupplementStore(descriptor)
    try:
        row,=store.query(query(metric='shareholder_reduction_gross',symbols=['CN.SH_SZ'],**{'from':day,'to':day}))['rows']
        assert row['value']=='140000'
        proof=json.loads(objects.get(row['source_sha256']));calculation=json.loads(objects.get(proof['parents'][0]))
        assert calculation['estimated_count']==1 and calculation['unpriced_count']==0 and len(calculation['parents'])==2
        if corrupt_input=='price_book':
            book=objects.put(json.dumps(dict(schema='guanheng.reduction-reference-prices.v1',quotes=[],parents=[calculation['parents'][1]])).encode())
            calculation['parents'][1]=book;proof['parents']=[objects.put(json.dumps(calculation).encode())]
            catalog=json.loads(Path(descriptor['path']).read_bytes());catalog['rows'][0]['source_sha256']=objects.put(json.dumps(proof).encode())
            other=tmp_path/'with-price-book.json';other.write_bytes(json.dumps(catalog).encode());store.close()
            store=MarketSupplementStore(dict(path=str(other),sha256=hashlib.sha256(other.read_bytes()).hexdigest()))
            store.verify_sources()
            target=json.loads(objects.get(book))['parents'][0]
        else:target=calculation['parents'][0 if corrupt_input=='report'else 1]
        objects.path(target).write_bytes(b'corrupt fixture input')
        with pytest.raises(ValueError,match='unavailable or corrupt'):store.verify_sources()
    finally:store.close()


def test_csi_pdf_parser_rejects_wrong_date_and_ambiguous_market_cap(monkeypatch):
    from types import SimpleNamespace
    import pypdf
    summary='沪深300指数(2026年11月5日)\n收盘点位 4016.29 指数涨幅 -0.68%'
    row='000300 沪深300 20041231 20050408 1000 508215 228573 4016.29 -0.68%'
    matrix='规模及行业指数市场数据\n指数代码 指数简称 基日 发布日期 基点 总市值 自由流通市值 收盘点位\n'
    pages=[SimpleNamespace(extract_text=lambda **kwargs: summary),
           SimpleNamespace(extract_text=lambda **kwargs: matrix+row)]
    monkeypatch.setattr(pypdf,'PdfReader',lambda *args,**kwargs:SimpleNamespace(pages=pages))
    assert public_sources._csi300_market_cap(b'%PDF-fixture',DAYS[-1])==228573
    summary=summary.replace('11月5日','11月05日')
    assert public_sources._csi300_market_cap(b'%PDF-fixture',DAYS[-1])==228573
    with pytest.raises(public_sources.SourceUnavailable,match='source_date_mismatch'):
        public_sources._csi300_market_cap(b'%PDF-fixture',DAYS[0])
    correct=matrix
    matrix=matrix.replace('自由流通市值','自由流通市值（万元）')
    with pytest.raises(public_sources.SourceUnavailable,match='source_schema_invalid'):
        public_sources._csi300_market_cap(b'%PDF-fixture',DAYS[-1])
    matrix=correct
    matrix+=row+'\n'
    with pytest.raises(public_sources.SourceUnavailable,match='source_symbol_mismatch'):
        public_sources._csi300_market_cap(b'%PDF-fixture',DAYS[-1])


def test_bigquant_index_partial_publish_and_retry_preserve_proof(tmp_path, monkeypatch):
    targets=plan(('index_turnover','SSE.932000'), required=False)
    targets['external_fallback'].append('BigQuant')
    targets['bigquant']=dict(bigquant_python=str(tmp_path/'python'),timeout_seconds=30)
    ready={DAYS[1]:342_201_380_000.0}
    calls=[]

    def query_index(policy, dataset, first, last, **kwargs):
        calls.append((dataset,first,last))
        return [dict(date=d,instrument='932000.CSI',amount=ready.get(d))
                for d in DAYS if first<=d<=last]

    monkeypatch.setattr(stock_cross_section,'query_bigquant',query_index)
    fetch,transport=FrozenFetch(),QmtTransport()
    descriptor=collect(tmp_path,targets,fetch,transport)
    selection=query(metric='index_turnover',symbols=['SSE.932000'])
    store=MarketSupplementStore(descriptor)
    try:
        data=store.query(selection)
        old=data['rows'][0]
        assert (old['source'],old['value'],old['unit'],old['available_at'])==('BigQuant','342201380000.0','CNY',None)
        assert data['gaps'][0]['reason']=='bigquant_index_amount_missing'
        store.verify_sources()
    finally:store.close()
    ready[DAYS[0]]=300_000_000_000
    descriptor=capture.collect_supplement(targets,DAYS[-1],DAYS,tmp_path/'retry',objects=ContentStore(tmp_path/'raw'),
        fetch=fetch,qmt_transport=transport,previous=descriptor,calendar_coverage=(DAYS[0],DAYS[-1]),deadline=time.monotonic()+20)
    store=MarketSupplementStore(descriptor)
    try:
        data=store.query(selection)
        assert [r['date'] for r in data['rows']]==DAYS and data['rows'][1]==old and not data['gaps']
        assert not store.query(query())['qmt_evidence']['decisions']
    finally:store.close()
    assert calls==[('small_cap_turnover',*DAYS),('small_cap_turnover',DAYS[0],DAYS[0])]
    assert fetch.calls==[] and transport.sdk_calls==[]


def test_index_history_uses_budget_after_existing_etf(tmp_path, monkeypatch):
    targets=plan(('index_turnover','SSE.932000'),('etf_total_shares','SSE.510300'),required=False)
    targets['external_fallback'].append('BigQuant')
    targets['bigquant']=dict(bigquant_python=str(tmp_path/'python'),timeout_seconds=30)
    targets['max_requests']=2  # QMT只读能力检查和最新ETF；历史按剩余预算继续。
    def unexpectedly_called(*args,**kwargs):
        pytest.fail('BigQuant should not exceed the common request budget')
    monkeypatch.setattr(stock_cross_section,'query_bigquant',unexpectedly_called)
    descriptor=collect(tmp_path,targets,FrozenFetch(),QmtTransport())
    store=MarketSupplementStore(descriptor)
    try:
        assert [row['date'] for row in store.query(query())['rows']]==[DAYS[-1]]
        assert len(store.query(query(metric='index_turnover',symbols=['SSE.932000']))['gaps'])==2
    finally:store.close()


def test_csi_turnover_fills_only_missing_bigquant_date(tmp_path,monkeypatch):
    targets=plan(('index_turnover','SSE.932000'))
    targets['external_fallback']=['BigQuant','CSI']
    targets['bigquant']=dict(bigquant_python=str(tmp_path/'python'),timeout_seconds=30)
    monkeypatch.setattr(stock_cross_section,'query_bigquant',lambda *args,**kwargs:[
        dict(date=DAYS[0],instrument='932000.CSI',amount=300_000_000_000)])

    class CSIFetch(FrozenFetch):
        def get(self,url,params=None,referer=None):
            assert url=='https://www.csindex.com.cn/csindex-home/perf/index-perf'
            stamp=DAYS[-1].replace('-','')
            assert params==dict(indexCode='932000',startDate=stamp,endDate=stamp)
            self.calls.append((url,params))
            return json.dumps(dict(code='200',success=True,data=[dict(indexCode='932000',tradeDate=stamp,
                                                                      close=3458.92,tradingValue=5560.77)])).encode()

    fetch=CSIFetch()
    store=MarketSupplementStore(collect(tmp_path,targets,fetch,QmtTransport()))
    try:
        actual=store.query(query(metric='index_turnover',symbols=['SSE.932000']))
        assert [(row['source'],Decimal(row['value'])) for row in actual['rows']]==[
            ('BigQuant',Decimal('300000000000')),('CSI',Decimal('556077000000'))]
        assert not actual['gaps'] and len(fetch.calls)==1
        store.verify_sources()
    finally:store.close()


def test_bigquant_batch_is_persisted_once_with_per_row_proofs(tmp_path,monkeypatch):
    targets=plan(('index_turnover','SSE.932000'))
    targets['external_fallback'].append('BigQuant')
    targets['bigquant']=dict(bigquant_python=str(tmp_path/'python'),timeout_seconds=30)
    monkeypatch.setattr(stock_cross_section,'query_bigquant',lambda *args,**kwargs:[
        dict(date=d,instrument='932000.CSI',amount=300_000_000_000) for d in DAYS])
    committed=[]
    save=capture._save

    def record(path,value):
        if path.name=='STATE.json' and value['status']=='collecting' and value['rows']:
            committed.append(len(value['rows']))
        return save(path,value)

    monkeypatch.setattr(capture,'_save',record)
    result=collect(tmp_path,targets,FrozenFetch(),QmtTransport())
    assert committed==[2]
    store=MarketSupplementStore(result)
    try:
        assert len(store.query(query(metric='index_turnover',symbols=['SSE.932000']))['rows'])==2
        store.verify_sources()
    finally:store.close()


def test_proxy_unknown_looks_up_original_slot_and_keeps_unit_unknown(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport(lose_first=True)
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    with pytest.raises(RetainedReadPending):collect(tmp_path,targets,fetch,transport)
    slot=tmp_path/'work/qmt-slots/000001.SH.json'
    original=json.loads(slot.read_bytes())['request']['request_id']
    descriptor=collect(tmp_path,targets,fetch,transport)
    assert len(transport.sdk_calls)==2
    assert transport.sdk_calls[0]['request_id']==original
    assert any(path.endswith('/'+original+'/lookup') for _,path in transport.calls)
    assert fetch.calls==[]
    with_store=MarketSupplementStore(descriptor)
    try:
        rows=with_store.query(query(metric='market_turnover_proxy',symbols=['CN.SH_SZ']))['rows']
        assert [Decimal(r['value']) for r in rows]==[Decimal('301'),Decimal('301')]
        assert {r['unit'] for r in rows}=={'unknown'}
        assert all(json.loads(with_store._objects.get(r['source_sha256']))['parents'] for r in rows)
    finally:with_store.close()


def test_proxy_resume_after_first_fact_keeps_original_request_range(tmp_path,monkeypatch):
    fetch,transport=FrozenFetch(),QmtTransport()
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    original_save=capture._save
    interrupted=False
    def fail_after_first(path,value):
        nonlocal interrupted
        original_save(path,value)
        if path.name=='STATE.json' and len(value.get('rows',{}))==1 and not interrupted:
            interrupted=True;raise InterruptedError('crash after one committed proxy fact')
    with monkeypatch.context() as scoped:
        scoped.setattr(capture,'_save',fail_after_first)
        with pytest.raises(InterruptedError):collect(tmp_path,targets,fetch,transport)
    assert len(transport.sdk_calls)==2
    identities=[r['request_id'] for r in transport.sdk_calls]
    descriptor=collect(tmp_path,targets,fetch,transport)
    assert len(transport.sdk_calls)==2
    assert [r['request_id'] for r in transport.sdk_calls]==identities
    assert len(json.loads(Path(descriptor['path']).read_bytes())['rows'])==2


def test_official_combination_and_financing_preserve_actual_fields(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport()
    descriptor=collect(tmp_path,plan(('market_turnover','CN.SH_SZ'),('margin_balance','CN.MARGIN_REPORT')),fetch,transport)
    store=MarketSupplementStore(descriptor)
    try:
        market=store.query(query(metric='market_turnover',symbols=['CN.SH_SZ']))['rows']
        assert {r['value'] for r in market}=={'2120874000000'}
        assert {r['source'] for r in market}=={'SSE+SZSE'}
        assert all(len(json.loads(store._objects.get(r['source_sha256']))['parents'])==2 for r in market)
        financing=store.query(query(metric='margin_balance',symbols=['CN.MARGIN_REPORT']))['rows']
        assert {r['value'] for r in financing}=={'12345678900'}
        assert all(r['unit']=='CNY' and r['available_at'] is None for r in financing)
    finally:store.close()


def test_optional_gaps_and_committed_source_damage_are_explicit(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'),required=False)
    targets['external_fallback']=[]
    fetch,transport=FrozenFetch(),QmtTransport()
    descriptor=collect(tmp_path,targets,fetch,transport)
    catalog=json.loads(Path(descriptor['path']).read_bytes())
    assert catalog['complete'] is False and len(catalog['gaps'])==2 and catalog['rows']==[]
    assert fetch.calls==[]
    objects=ContentStore(tmp_path/'raw');objects.path(catalog['qmt_evidence']['source_sha256']).write_bytes(b'corrupt')
    with pytest.raises(ValueError):collect(tmp_path,targets,fetch,transport)


def test_cancel_preserves_successful_facts_and_no_final_catalog(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport()
    checks=0
    def cancelled():
        nonlocal checks
        checks+=1
        return (tmp_path/'work/STATE.json').exists() and len(json.loads((tmp_path/'work/STATE.json').read_bytes()).get('rows',{}))==1
    with pytest.raises(InterruptedError):collect(tmp_path,plan(('etf_total_shares','SSE.510300')),fetch,transport,cancelled=cancelled)
    assert checks>0 and not (tmp_path/'work/catalog.json').exists()
    assert len(json.loads((tmp_path/'work/STATE.json').read_bytes())['rows'])==1


def test_qmt_metadata_and_proxy_share_original_public_budget(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport()
    fetch.budget.max_requests=1
    with pytest.raises(capture.SupplementPending):
        collect(tmp_path,plan(('market_turnover_proxy','CN.SH_SZ')),fetch,transport)
    assert transport.sdk_calls==[]  # 首次metadata已用额度，不能再偷偷产生SDK读取。
    assert fetch.budget.sdk_requests==1
    assert not (tmp_path/'work/catalog.json').exists()
    assert {r['reason'] for r in json.loads((tmp_path/'work/COVERAGE.json').read_bytes())['gaps']}=={'request_budget_exceeded'}


def test_profile_row_limit_partitions_history_without_truncation(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport(max_rows=1)
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    descriptor=collect(tmp_path,targets,fetch,transport)
    assert len(transport.sdk_calls)==4
    state=json.loads((tmp_path/'work/STATE.json').read_bytes())
    assert len(state['rows'])==2
    assert all(r['arguments']['max_rows']==1 for r in transport.sdk_calls)
    assert all(r['arguments']['start_date']==r['arguments']['end_date'] for r in transport.sdk_calls)
    identities=[r['request_id'] for r in transport.sdk_calls]
    assert collect(tmp_path,targets,fetch,transport)==descriptor
    assert [r['request_id'] for r in transport.sdk_calls]==identities


def test_requested_history_outside_calendar_is_rejected_before_source(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'))
    targets['targets'][0]['from']='2026-11-03'
    fetch,transport=FrozenFetch(),QmtTransport()
    with pytest.raises(ValueError):collect(tmp_path,targets,fetch,transport)
    assert fetch.calls==[] and transport.calls==[]
    assert not (tmp_path/'work/catalog.json').exists()


def test_nontrading_start_inside_official_coverage_is_admitted(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'))
    targets['targets'][0]['from']='2026-11-01'  # Sunday，真实覆盖从休市日开始。
    fetch,transport=FrozenFetch(),QmtTransport()
    descriptor=capture.collect_supplement(targets,'2026-11-03',['2026-11-02','2026-11-03'],tmp_path/'work',
        objects=ContentStore(tmp_path/'raw'),fetch=fetch,qmt_transport=transport,
        calendar_coverage=('2026-11-01','2026-11-03'),deadline=time.monotonic()+20)
    value=json.loads(Path(descriptor['path']).read_bytes())
    assert value['complete'] and [r['date'] for r in value['rows']]==['2026-11-02','2026-11-03']


def test_scaled_source_overflow_is_gap_then_recovers_without_poisoned_state(tmp_path):
    class OversizedMargin(FrozenFetch):
        oversized=True
        def get(self,url,params=None,referer=None):
            raw=super().get(url,params,referer)
            if self.oversized and params.get('reportName')=='RPTA_WEB_MARGIN_DAILYTRADE':
                value=json.loads(raw);value['result']['data'][0]['FIN_BALANCE']='1e128'
                return json.dumps(value).encode('utf8')
            return raw
    fetch,transport=OversizedMargin(),QmtTransport()
    targets=plan(('margin_balance','CN.MARGIN_REPORT'))
    with pytest.raises(capture.SupplementPending):collect(tmp_path,targets,fetch,transport)
    assert json.loads((tmp_path/'work/STATE.json').read_bytes())['rows']=={}
    assert not (tmp_path/'work/catalog.json').exists()
    fetch.oversized=False
    descriptor=collect(tmp_path,targets,fetch,transport)
    assert {r['value'] for r in json.loads(Path(descriptor['path']).read_bytes())['rows']}=={'12345678900'}


def test_invalid_qmt_value_never_enters_persistent_fact_rows(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport(amounts={'000001.SH':1e128,'399106.SZ':200.75})
    with pytest.raises(MarketProtocolError):
        collect(tmp_path,plan(('market_turnover_proxy','CN.SH_SZ')),fetch,transport)
    assert len(transport.sdk_calls)==2
    assert json.loads((tmp_path/'work/STATE.json').read_bytes())['rows']=={}
    assert not (tmp_path/'work/catalog.json').exists()

@pytest.mark.parametrize(('total', 'page_number', 'has_rows', 'reason'), [
    (0, 1, False, 'source_record_missing'),
    (0, 2, False, 'source_pagination_invalid'),
    (1, 1, False, 'source_pagination_invalid'),
    (0, 1, True, 'source_pagination_invalid'),
])
def test_sse_zero_page_latest_date_keeps_previous_share_fact_and_records_gap(
        tmp_path, total, page_number, has_rows, reason):
    class EmptyLatest(FrozenFetch):
        def get(self, url, params=None, referer=None):
            raw = super().get(url, params, referer)
            if params.get('STAT_DATE') == DAYS[-1]:
                response = json.loads(raw)
                response['pageHelp'] = dict(total=total, pageCount=0, pageNo=page_number)
                if not has_rows:
                    response['result'] = []
                return json.dumps(response).encode()
            return raw

    targets = plan(('etf_total_shares', 'SSE.510300'), required=False)
    descriptor = collect(tmp_path, targets, EmptyLatest(), QmtTransport())
    store = MarketSupplementStore(descriptor)
    try:
        result = store.query(query())
        assert [(row['date'], row['value']) for row in result['rows']] == [(DAYS[0], '1750001250')]
        assert result['gaps'] == [dict(date=DAYS[-1], metric='etf_total_shares',
                                      symbol='SSE.510300', reason=reason)]
        store.verify_sources()
    finally:
        store.close()


def test_daily_stock_uses_same_sdk_amount_ratio_without_absolute_currency_unit(tmp_path, monkeypatch):
    from integrations.guanheng_market_client.daily_facts import FIELDS, STATS
    from integrations.guanheng import analysis_price_capture, analysis_price_units

    day = DAYS[-1]
    facts = dict(schema='guanheng.daily-source-facts.v1', date=day, members=['SSE.600000'], fields=FIELDS,
        rows=[[day, 'SSE.600000', '2', '1', '100', '1', '1', 'qualified']],
        units=dict(close_reference='CNY', preclose='CNY', volume='share', turn='percent_of_float'),
        stats={name: 0 for name in STATS},
        provenance=dict(packet_sha256='a'*64, universe_sha256='b'*64, source_received_at='2026-11-06T00:00:00+00:00'))
    monkeypatch.setattr(analysis_price_units, 'load_unit_evidence', lambda *args, **kwargs: object())
    monkeypatch.setattr(analysis_price_units, 'qualify_capture_units', lambda *args, **kwargs: object())
    monkeypatch.setattr(analysis_price_units, 'capture_price_units', lambda *args, **kwargs:
                        type('UnknownAmount', (), {'amount_unit': 'unknown'})())
    monkeypatch.setattr(analysis_price_capture, 'load_price_capture', lambda *args: {'source_kind': 'actual-qmt'})
    monkeypatch.setattr(analysis_price_capture, 'price_batches', lambda *args, **kwargs:
        iter([({}, {'600000.SH': {'data': {day.replace('-', ''): {'close': 2, 'amount': 200}}}})]))
    def external(*args, **kwargs):
        pytest.fail('Qualified local amounts suffice for the dimensionless concentration ratio')
    monkeypatch.setattr(stock_cross_section, 'acquire_bigquant', external)
    store = ContentStore(tmp_path)
    result = stock_cross_section.prepare_section(facts, {'sha256': 'c'*64}, {'path': 'fixture'},
        dict(timeout_seconds=30,minimum_sample_count=1), store,
        deadline=time.monotonic()+10,cancelled=lambda:False,environ={})
    assert result['provider'] == 'QMT'
    assert result['top5_pct'] == 100
    assert result['median_return_pct'] == 100
