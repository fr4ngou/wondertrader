"""原输入owner→原更新发布→固定snapshot→真实回环HTTP/SDK；不运行原生DLL。"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).parent))
from msf_fixture import DAYS,FrozenFetch,QmtTransport,encode,plan,query,write,capture_metadata
import pytest

from integrations.guanheng import daily_data_inputs as inputs,daily_data_update as update
from integrations.guanheng.market_generation import GenerationPublisher
from integrations.guanheng.market_service import MarketHTTPServer
from integrations.guanheng.market_snapshot import SnapshotSourceMarket
from integrations.guanheng.market_supplement_capture import SupplementPending
from integrations.guanheng_market_client import API_VERSION,MarketClient
from integrations.guanheng_market_client.daily_facts import FIELDS,STATS


class ReferenceStub:
    """证券资料是无关边界；本用例实际验证新增市场事实的完整生产/发布链。"""
    def __init__(self,*args):self.closed=False
    def close(self):self.closed=True


class BaseMarket:
    def __init__(self):self.closed=False
    def close(self):self.closed=True


def owner_fixture(root):
    from integrations.guanheng.day_facts_prepare import prepare_facts_catalog
    pool=dict(date=DAYS[-1],members=['sh.600000'],market_count=1,unresolved_identity_count=0)
    universe=write(root/'seed-universe.json',pool)
    facts=dict(schema='guanheng.daily-source-facts.v1',date=DAYS[-1],members=['SSE.600000'],
        fields=FIELDS,rows=[[DAYS[-1],'SSE.600000','1','1','100','1','1','qualified']],
        units=dict(close_reference='CNY',preclose='CNY',volume='share',turn='percent_of_float'),
        stats={k:0 for k in STATS},provenance=dict(packet_sha256='a'*64,universe_sha256=universe['sha256'],
                                               source_received_at='2026-11-06T00:00:00+00:00'))
    day_facts=prepare_facts_catalog([facts],root/'old-facts')
    calendar=write(root/'calendar.json',dict(coverage_start='2026-01-01',coverage_end='2026-12-31'))
    reference=write(root/'reference.json',{})
    base=write(root/'base.json',dict(mode='source-catalog',stores=[],native_reader={}))
    basic=root/'basic';basic.mkdir()
    raw=encode(dict(symbol='600000.SH',value=None))+b'\n';(basic/'rows.jsonl').write_bytes(raw)
    write(basic/'RESULT.json',dict(state='completed',rows_sha256=hashlib.sha256(raw).hexdigest()))
    capture=root/'seed';capture.mkdir()
    original_request=dict(universe=universe,start_date='20261104',end_date='20261105',
                          source_kind='sdk-synthetic', symbols=['600000.SH'], max_rows=40)
    manifest=write(capture/'manifest.json',dict(request=original_request,source_kind='sdk-synthetic', batches=[dict(requested_at='2026-11-06T00:00:00+00:00',symbols=['600000.SH'])], generated_at='2026-11-06T00:01:00+00:00'))
    metadata=capture_metadata()
    binding=metadata['binding']
    write(capture/'BINDING.json',metadata)
    native=root/'native';native.mkdir()
    archive=write(root/'archive.json',{})
    imported=write(native/'IMPORT.json',dict(schema='guanheng.qmt-analysis-native-import.v1',state='completed',
        capture_sha256=manifest['sha256'],helper_sha256='d'*64,archive=archive,securities=1,
        observation_date='20261105',stores=[],source_kind='sdk-synthetic',source_received_at='2026-11-06T00:00:00+00:00'))
    write(native/'PROVENANCE.json',dict(capture_sha256=manifest['sha256'],capture=str(capture),
        request=original_request,batches=[dict(binding=binding)]))
    template=dict(schema='guanheng.daily-data-update.v1',publication_directory=str(root/'publication'),
        daily_facts=day_facts,security_reference=reference,calendar=calendar,base_configuration=base,
        basic_capture=str(basic),helper=dict(path=str(root/'not-invoked-helper'),sha256='d'*64),
        previous_stores=[],previous_archives=[],protected_slots=[],additional_archives=[],prepared_native=imported)
    config=dict(schema='guanheng.daily-data-service.v1',directory=str(root/'tasks'),raw_store=str(root/'raw'),
        template=template,inputs=dict(connections=dict(batch={},hpr={}),cache_from='20261104',max_rows=40,
            source_kind='sdk-synthetic',cache_seed=dict(directory=str(capture),sha256=manifest['sha256']),
            supplement_facts=plan(('etf_total_shares','SSE.510300')),
            public_facts=dict(source={},allowed_hosts=[],seconds=30,max_requests=100,max_bytes=4*1024*1024,
                response_bytes=1024*1024,timeout_seconds=1)),schedule=dict(timezone='Asia/Shanghai',at='09:00',poll_seconds=1),
        cycle_seconds=60,retry_seconds=1)
    return config,pool,facts,original_request


def patch_owner_dependencies(monkeypatch,config,pool,facts,original_request):
    fetches=[];transports=[];healthy={'value':False}
    def make_fetch(*args,**kwargs):
        value=FrozenFetch(bad_day=None if healthy['value'] else DAYS[-1]);fetches.append(value);return value
    def make_transport(*args,**kwargs):
        value=QmtTransport();transports.append(value);return value
    def public_packet(reader,fetch,source,day,**kwargs):
        sha=reader.objects.put(encode(pool));return dict(universe=dict(sha256=sha)),deepcopy(facts)
    monkeypatch.setattr('guanheng_app.observation.source_fetch.Fetcher',make_fetch)
    monkeypatch.setattr('integrations.guanheng.source_history_transport.BoundHistorySource',make_transport)
    monkeypatch.setattr('integrations.guanheng.day_facts_capture.capture_day_facts',public_packet)
    monkeypatch.setattr('guanheng_app.observation.calendars.official_calendar',lambda c:([dict(date=d,is_open=1) for d in DAYS],None))
    monkeypatch.setattr('guanheng_qmt_shm.analysis_batch_source.read_capture',lambda p:dict(request=original_request))
    monkeypatch.setattr('integrations.guanheng.security_reference.SecurityReference',ReferenceStub)
    monkeypatch.setattr('guanheng_qmt_shm.market_daily_cache.assess',lambda p:dict(full_coverage=True))
    def gap_plan(cache,reference,snapshot,output,**kwargs):
        return write(Path(output)/'PLAN.json',dict(schema='guanheng.daily-gap-plan.v1',snapshot_id=snapshot['snapshot_id'],
            capture=cache,authorized_from=kwargs['authorized_from'],authorized_to=kwargs['authorized_to'],
            protected_requests=[],exclusions=[],tasks=[]))
    monkeypatch.setattr('integrations.guanheng.daily_gap_update.prepare_gap_plan',gap_plan)
    monkeypatch.setattr('integrations.guanheng.source_market.create_native_source_market',lambda *a,**k:BaseMarket())
    return fetches,transports,healthy


@pytest.mark.parametrize('legacy_intent', [False, True])
def test_complete_update_uses_published_security_reference_and_keeps_input_binding(tmp_path, monkeypatch, legacy_intent):
    config, pool, facts, request = owner_fixture(tmp_path)
    _, _, healthy = patch_owner_dependencies(monkeypatch, config, pool, facts, request)
    healthy['value'] = True
    directory = tmp_path/'inputs'
    directory.mkdir()
    publication = Path(config['template']['publication_directory'])
    publication.mkdir()
    (publication/'CURRENT.json').touch()
    old = config['template']['security_reference']
    published = write(tmp_path/'price-reference.json', {'listing_date':'2026-11-05'})
    later = write(tmp_path/'later-reference.json', {'listing_date':'2026-11-06'})
    descriptor = lambda reference: write(tmp_path/'current-config.json', dict(
        daily_facts=config['template']['daily_facts'], base={}, security_reference=reference))
    current = dict(configuration=descriptor(published))
    monkeypatch.setattr(inputs,'read_generation',lambda *_: (current, '1'*64))

    from integrations.guanheng import day_facts_capture
    fetch_facts = day_facts_capture.capture_day_facts
    intent = directory/'INPUTS.json'
    if legacy_intent:
        write(intent, dict(configuration=config, day=DAYS[-1], previous_requests=[]))
    else:
        def interrupted(*args, **kwargs):
            raise InterruptedError('source stopped after input binding')
        monkeypatch.setattr(day_facts_capture,'capture_day_facts',interrupted)
        with pytest.raises(InterruptedError):
            inputs.prepare_update(config,DAYS[-1],directory,deadline=time.monotonic()+20)
        assert json.loads(intent.read_bytes())['security_reference'] == published
        monkeypatch.setattr(day_facts_capture,'capture_day_facts',fetch_facts)
    original_intent = intent.read_bytes()
    current['configuration'] = descriptor(later)
    prepared = inputs.prepare_update(config,DAYS[-1],directory,deadline=time.monotonic()+20)
    assert inputs._load(prepared)['security_reference'] == (old if legacy_intent else published)
    assert intent.read_bytes() == original_intent


@pytest.mark.parametrize('with_readback', [False, True])
def test_same_day_revision_reuses_the_committed_analysis_capture(tmp_path, monkeypatch, with_readback):
    config, pool, facts, request = owner_fixture(tmp_path)
    _, _, healthy = patch_owner_dependencies(monkeypatch, config, pool, facts, request)
    healthy['value'] = True
    (tmp_path/'first').mkdir()
    (tmp_path/'next').mkdir()
    original = inputs.prepare_update(config, DAYS[-1], tmp_path/'first'/'inputs',
                                     deadline=time.monotonic()+20)
    previous = write(tmp_path/'first'/'REQUEST.json', inputs._load(original))
    capture = inputs._load(original)['cache']
    stages = {}
    if with_readback:
        manifest = write(tmp_path/'readback'/'manifest.json', dict(request=request, source_kind='sdk-synthetic', batches=[dict(requested_at='2026-11-06T00:00:00+00:00',symbols=['600000.SH'])], generated_at='2026-11-06T00:01:00+00:00'))
        capture = dict(directory=str(Path(manifest['path']).parent), sha256=manifest['sha256'])
        stages['readback'] = capture
    write(tmp_path/'first'/'work'/'STATE.json', dict(status='published', stages=stages))

    old_seed = tmp_path/'old-seed'/'manifest.json'
    write(old_seed, dict(request=dict(request, end_date='20261103')))
    config['inputs']['cache_seed'] = dict(directory=str(old_seed.parent),
                                         sha256=hashlib.sha256(old_seed.read_bytes()).hexdigest())

    def unexpected_capture(*args, **kwargs):
        pytest.fail('same-day continuation repeated the QMT capture')

    monkeypatch.setattr('integrations.guanheng.daily_batch_source.DailyBatchAnalysisSource.capture', unexpected_capture)
    next_input = inputs.prepare_update(config, DAYS[-1], tmp_path/'next'/'inputs',
                                       previous_requests=[previous['path']], deadline=time.monotonic()+20)
    assert inputs._load(next_input)['cache'] == capture
    assert not (tmp_path/'next'/'inputs'/'CAPTURE-REQUEST.json').exists()
    bound = request['universe']['sha256']
    assert inputs.reusable_analysis_capture([capture], DAYS[-1], request['symbols'], bound,
                                            config['inputs'], 41, check=lambda: None) == (None, None)
    from datetime import datetime
    assert inputs.reusable_analysis_capture([capture], DAYS[-1], request['symbols'], bound,
        config['inputs'], 40, check=lambda: None,
        read_after={'600000.SH':datetime.fromisoformat('2026-11-06T00:00:01+00:00')}) == (None, None)
    adopted, _ = inputs.reusable_analysis_capture([capture], DAYS[-1], request['symbols'], bound,
        config['inputs'], 40, check=lambda: None,
        read_after={'000001.SZ':datetime.fromisoformat('2026-11-06T00:00:01+00:00')})
    assert adopted == capture


def test_required_pending_then_real_owner_publish_and_http_sdk(tmp_path,monkeypatch):
    config,pool,facts,original_request=owner_fixture(tmp_path)
    from integrations.guanheng.day_facts_prepare import prepare_facts_catalog
    older = deepcopy(facts)
    older['date'] = DAYS[0]
    older['rows'][0][0] = DAYS[0]
    valuation = dict(equal_pb=3, median_pb=3, sample_count=1, excluded_count=0, universe_count=1,
        profitable_equal_pb=None, profitable_median_pb=None, profitable_sample_count=0,
        profitable_excluded_count=1, stock_basic_sha256='6'*64, stock_daily_sha256='7'*64)
    breadth = dict(market_count=2, reported_count=2, excluded_count=0, suspended_count=0, missing_price_count=0,
        advancing_count=1, declining_count=1, flat_count=0, advancing_volume=150, declining_volume=100,
        missing_volume_count=0, turnover_known_count=2, turnover_gt5_count=1,
        universe_version='8'*64, stock_basic_sha256='6'*64, stock_daily_sha256='7'*64)
    facts['shsz_valuation'] = valuation
    facts['shsz_breadth'] = breadth
    config['template']['daily_facts'] = prepare_facts_catalog([older, facts], tmp_path/'history-facts')
    config['inputs']['stock_cross_section'] = dict(bigquant_python=sys.executable, timeout_seconds=5,
        minimum_sample_count=1, history_from=DAYS[0], history_days_per_cycle=1)
    section_calls = []
    def query_stock(*args, **kwargs):
        section_calls.append(args)
        return [dict(date=args[1], instrument='600000.SH', close=1, pre_close=1, amount=100)]
    monkeypatch.setattr('integrations.guanheng.stock_cross_section.acquire_bigquant', query_stock)
    config['inputs']['supplement_facts']=plan(('etf_total_shares','SSE.510300'),
        ('etf_total_shares','SZSE.159780'),('margin_balance','CN.MARGIN_REPORT'),
        ('market_turnover','CN.SH_SZ'),('market_turnover_proxy','CN.SH_SZ'))
    from integrations.guanheng.daily_data_service import validate_configuration
    validate_configuration(config)
    fetches,transports,healthy=patch_owner_dependencies(monkeypatch,config,pool,facts,original_request)
    work=tmp_path/'inputs'
    with pytest.raises(SupplementPending):inputs.prepare_update(config,DAYS[-1],work,deadline=time.monotonic()+20)
    assert not (work/'UPDATE.json').exists()
    assert fetches[-1].closed and transports[-1].closed
    assert len(json.loads((work/'supplement/STATE.json').read_bytes())['rows'])==8
    healthy['value']=True
    original_save = inputs._save
    def interrupted(path, value):
        if path.name == 'UPDATE.json':
            raise InterruptedError('after facts phase committed')
        original_save(path, value)
    with monkeypatch.context() as crash:
        crash.setattr(inputs, '_save', interrupted)
        with pytest.raises(InterruptedError, match='facts phase'):
            inputs.prepare_update(config,DAYS[-1],work,deadline=time.monotonic()+20)
    descriptor=inputs.prepare_update(config,DAYS[-1],work,deadline=time.monotonic()+20)
    assert [args[1] for args in section_calls] == [DAYS[-1], DAYS[0]]
    request=json.loads(Path(descriptor['path']).read_bytes())
    assert request['supplement_facts']['path'].endswith('catalog.json')
    assert fetches[-1].closed and transports[-1].closed
    assert len(fetches[-2].calls)==2 and not fetches[-1].calls
    # 已固定输入再次读取不构造任何新来源对象。
    before=len(fetches)
    assert inputs.prepare_update(config,DAYS[-1],work,deadline=time.monotonic()+20)==descriptor
    assert len(fetches)==before
    stages = []
    result=update.run_update(request,tmp_path/'update',deadline=time.monotonic()+20,on_stage=stages.append)
    assert stages[-3:] == ['native', 'snapshot', 'publishing']
    assert 'parent' not in stages
    assert result['status']=='published'
    current=json.loads((tmp_path/'publication/CURRENT.json').read_bytes())
    published=json.loads(Path(current['configuration']['path']).read_bytes())
    snapshot=json.loads(Path(published['snapshot']['path']).read_bytes())
    assert published['supplement_facts']==request['supplement_facts']
    assert snapshot['provenance']['supplement_facts_sha256']==request['supplement_facts']['sha256']
    ready=queue.Queue();stop=threading.Event();errors=[];bases=[]
    def serve():
        server=None
        try:
            market=SnapshotSourceMarket(published,max_response_bytes=4*1024*1024)
            bases.append(market._base)
            server=MarketHTTPServer(('127.0.0.1',0),market,'synthetic-msf-http-token');server.timeout=.05
            ready.put(server.server_port)
            while not stop.is_set():server.handle_request()
        except BaseException as exc:errors.append(type(exc).__name__);ready.put(None)
        finally:
            if server is not None:server.server_close()
    thread=threading.Thread(target=serve);thread.start()
    try:
        port=ready.get(timeout=5);assert port is not None,errors
        client=MarketClient(f'http://127.0.0.1:{port}','synthetic-msf-http-token')
        legacy=client.source_day_facts_query(DAYS[-1],snapshot['snapshot_id'])
        assert legacy['status']['code']=='Ok' and 'stock_cross_section' not in legacy['data']
        assert 'rows' in legacy['data'] and not {'shsz_valuation', 'shsz_breadth'} & legacy['data'].keys()
        pb = client.source_day_facts_query(DAYS[-1], snapshot['snapshot_id'],
                                           include_shsz_valuation=True)['data']
        assert set(pb) == {'date', 'source_snapshot_id', 'source_sha256', 'shsz_valuation'}
        assert pb['shsz_valuation'] == valuation
        combined = client.source_day_facts_query(DAYS[-1], snapshot['snapshot_id'],
            include_shsz_valuation=True, include_shsz_breadth=True)['data']
        assert combined == dict(pb, shsz_breadth=breadth)
        previous = client.source_day_facts_query(DAYS[0], snapshot['snapshot_id'],
                                                 include_shsz_valuation=True)['data']
        assert 'shsz_valuation' not in previous
        from guanheng_app.observation import wt_shsz_pb
        from guanheng_app.observation.source_fetch import CollectionBudget
        from guanheng_app.observation.runtime import build_reader
        from types import SimpleNamespace
        monkeypatch.setattr('guanheng_app.observation.wt_shsz_pb.official_calendar',
                            lambda *_args, **_kwargs: ([dict(date=d, is_open=1) for d in DAYS], None))
        target = build_reader(tmp_path/'breadth-observation')
        target.repository.initialize()
        breadth_fetch = SimpleNamespace(objects=target.objects, budget=CollectionBudget(time.monotonic()+5),
                                        records=[], timeout=2)
        shsz = wt_shsz_pb.history(breadth_fetch, dict(tables=wt_shsz_pb.FULL_TABLES, minimum_universe=1),
            DAYS[0], DAYS[-1], lambda _: client, calendar=dict(coverage_start=DAYS[0], coverage_end=DAYS[-1]),
            snapshot_dates=[DAYS[-1]])
        assert shsz['breadth.shsz'][0]['advancing_pct'] == 50
        assert shsz['trin.shsz'][0]['trin'] == 2/3
        assert shsz['rana.shsz'][0]['rana'] == 0
        assert shsz['turnover.gt5.shsz'][0]['turnover_gt5_pct'] == 50
        assert [row['date'] for row in shsz[wt_shsz_pb.BREADTH_TABLE]] == [DAYS[-1]]
        assert shsz[wt_shsz_pb.UNIVERSE_TABLE][0]['market_count'] == 2
        assert len(shsz[wt_shsz_pb.CALENDAR_TABLE]) == len(DAYS)
        section=client.source_day_facts_query(DAYS[-1],snapshot['snapshot_id'],
                                               include_stock_cross_section=True)['data']['stock_cross_section']
        assert section['provider']=='BigQuant' and section['sample_count']==1 and section['top5_pct']==100
        from guanheng_app.observation.market_structure_source import STOCK_TABLE, wt_stock_history
        monkeypatch.setattr('guanheng_app.observation.market_structure_source.official_calendar',
                            lambda *_args, **_kwargs: ([dict(date=day, is_open=1) for day in DAYS], None))
        observer = build_reader(tmp_path/'observation')
        observer.repository.initialize()
        fetch = SimpleNamespace(objects=observer.objects, budget=CollectionBudget(time.monotonic()+5),
                                records=[], timeout=2)
        rows = wt_stock_history(fetch, DAYS[0], DAYS[-1],
            dict(coverage_start=DAYS[0],coverage_end=DAYS[-1]), lambda _: client, snapshot_dates=[DAYS[-1]])
        assert [row['date'] for row in rows[STOCK_TABLE]] == [DAYS[0], DAYS[-1]]
        assert rows[STOCK_TABLE][-1] == dict(date=DAYS[-1], **section)
        assert len(fetch.records) == 3
        reply=client.source_supplement_query(query(snapshot['snapshot_id']))
        assert reply['status']['code']=='Ok'
        assert [r['value'] for r in reply['data']['rows']]==['1750001250','1750001250']
        assert reply['data']['source_sha256']==request['supplement_facts']['sha256']
        for metric,symbol,value,unit in [('etf_total_shares','SZSE.159780','4037248583','share'),
                ('margin_balance','CN.MARGIN_REPORT','12345678900','CNY'),
                ('market_turnover','CN.SH_SZ','2120874000000','CNY'),
                ('market_turnover_proxy','CN.SH_SZ','301','unknown')]:
            selected=client.source_supplement_query(query(snapshot['snapshot_id'],metric=metric,symbols=[symbol]))
            assert selected['status']['code']=='Ok'
            assert len(selected['data']['rows'])==2 and selected['data']['gaps']==[]
            assert {Decimal(r['value']) for r in selected['data']['rows']}=={Decimal(value)}
            assert {r['unit'] for r in selected['data']['rows']}=={unit}
        assert client.source_supplement_query(query('9'*64))['status']['code']=='Conflict'
    finally:stop.set();thread.join(5)
    assert not thread.is_alive() and not errors
    assert bases[0].closed
    # 同日成功重入保持同CURRENT，而非另发一个generation。
    before=(tmp_path/'publication/CURRENT.json').read_bytes()
    update.run_update(request,tmp_path/'update',deadline=time.monotonic()+20)
    assert (tmp_path/'publication/CURRENT.json').read_bytes()==before


def test_input_owner_closes_sources_when_qmt_binding_unresolved(tmp_path,monkeypatch):
    config,pool,facts,original_request=owner_fixture(tmp_path)
    fetches,transports,healthy=patch_owner_dependencies(monkeypatch,config,pool,facts,original_request)
    healthy['value']=True
    def pending(*a,**k):
        value=QmtTransport(binding_pending=True);transports.append(value);return value
    monkeypatch.setattr('integrations.guanheng.source_history_transport.BoundHistorySource',pending)
    from guanheng_qmt_shm.read_retention_client import RetainedReadPending
    with pytest.raises(RetainedReadPending):inputs.prepare_update(config,DAYS[-1],tmp_path/'inputs',deadline=time.monotonic()+20)
    assert fetches[-1].closed and transports[-1].closed
    assert fetches[-1].calls==[]
    assert not (tmp_path/'inputs/UPDATE.json').exists()


def test_optional_supplement_public_budget_timeout_keeps_latest_and_publishes(tmp_path,monkeypatch):
    """旧缺口耗尽公共预算后仍发布已得最新事实；原owner总D继续有效。"""
    from guanheng_app.observation.source_fetch import SourceFailure
    config,pool,facts,original_request=owner_fixture(tmp_path)
    config['inputs']['supplement_facts']=plan(('etf_total_shares','SSE.510300'),
        ('margin_balance','CN.MARGIN_REPORT'),required=False)
    fetches,transports,healthy=patch_owner_dependencies(monkeypatch,config,pool,facts,original_request)
    healthy['value']=True
    class TimeoutOld(FrozenFetch):
        def get(self,url,params=None,referer=None):
            # 先让最新日两项成功，旧日期触发生产CollectionBudget的真实超时分类。
            if params.get('STAT_DATE')==DAYS[0]:self.budget.deadline=time.monotonic()-1
            return super().get(url,params,referer)
    created=[]
    def make_fetch(*args,**kwargs):
        result=TimeoutOld();created.append(result);return result
    monkeypatch.setattr('guanheng_app.observation.source_fetch.Fetcher',make_fetch)
    descriptor=inputs.prepare_update(config,DAYS[-1],tmp_path/'inputs',deadline=time.monotonic()+20)
    request=json.loads(Path(descriptor['path']).read_bytes())
    result=update.run_update(request,tmp_path/'update',deadline=time.monotonic()+20)
    assert result['status']=='published' and result['supplement_complete'] is False
    catalog=json.loads(Path(request['supplement_facts']['path']).read_bytes())
    assert len(catalog['rows'])==2 and {r['date'] for r in catalog['rows']}=={DAYS[-1]}
    assert len(catalog['gaps'])==2 and any(r['reason']=='collection_timeout' for r in catalog['gaps'])
    assert (tmp_path/'publication/CURRENT.json').exists() and created[-1].closed


def test_committed_snapshot_resume_rechecks_proof_before_publication(tmp_path,monkeypatch):
    config,pool,facts,original_request=owner_fixture(tmp_path)
    fetches,transports,healthy=patch_owner_dependencies(monkeypatch,config,pool,facts,original_request)
    healthy['value']=True
    descriptor=inputs.prepare_update(config,DAYS[-1],tmp_path/'inputs',deadline=time.monotonic()+20)
    request=json.loads(Path(descriptor['path']).read_bytes())
    def interrupt(*args,**kwargs):raise InterruptedError('after committed snapshot, before CURRENT')
    with monkeypatch.context() as scoped:
        scoped.setattr(GenerationPublisher,'publish',interrupt)
        with pytest.raises(InterruptedError):update.run_update(request,tmp_path/'update',deadline=time.monotonic()+20)
    assert not (tmp_path/'publication/CURRENT.json').exists()
    state=json.loads((tmp_path/'update/STATE.json').read_bytes())
    assert 'snapshot' in state['stages']
    from integrations.guanheng.market_supplement_store import MarketSupplementStore
    store=MarketSupplementStore(request['supplement_facts'])
    try:
        row=store.catalog['rows'][0]
        proof=json.loads(store._objects.get(row['source_sha256']))
        parent=store._objects.path(proof['parents'][0]);before=parent.read_bytes()
        parent.write_bytes(b'corrupted after snapshot commit')
        with pytest.raises(ValueError):update.run_update(request,tmp_path/'update',deadline=time.monotonic()+20)
        assert not (tmp_path/'publication/CURRENT.json').exists()
        parent.write_bytes(before)
    finally:store.close()
    result=update.run_update(request,tmp_path/'update',deadline=time.monotonic()+20)
    assert result['status']=='published'


def test_snapshot_proof_walk_obeys_original_owner_cancel_before_output(tmp_path,monkeypatch):
    config,pool,facts,original_request=owner_fixture(tmp_path)
    fetches,transports,healthy=patch_owner_dependencies(monkeypatch,config,pool,facts,original_request)
    healthy['value']=True
    descriptor=inputs.prepare_update(config,DAYS[-1],tmp_path/'inputs',deadline=time.monotonic()+20)
    request=json.loads(Path(descriptor['path']).read_bytes())
    calls=0
    def check():
        nonlocal calls
        calls+=1
        if calls>=3:raise InterruptedError('cancel during added source-proof traversal')
    from integrations.guanheng.market_snapshot_prepare import prepare_market_snapshot
    output=tmp_path/'cancelled-snapshot'
    with pytest.raises(InterruptedError):
        prepare_market_snapshot(json.loads(Path(request['base_configuration']['path']).read_bytes()),
            request['prepared_native']['path'],request['universe']['path'],request['basic_capture'],output,
            supplement_facts=request['supplement_facts'],check=check)
    assert calls>=3
    assert not output.exists()
