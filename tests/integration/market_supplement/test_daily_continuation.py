"""常驻同owner的跨日补缺；保留真实采集/原ID客户端和来源证明，原生转换另有主链。"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
from threading import Event, get_ident
import time
from uuid import uuid4

import pytest

sys.path.insert(0,str(Path(__file__).parent))
from msf_fixture import DAYS,ContentStore,FrozenFetch,QmtTransport,plan,write
from test_daily_owner import owner_fixture
from integrations.guanheng import daily_data_service as service
from integrations.guanheng import market_supplement_capture as capture
from integrations.guanheng.daily_data_update import _load,_save
from integrations.guanheng.market_supplement_store import MarketSupplementStore


def collect_at(plan_value,day,dates,work,objects,fetch,transport,previous=None):
    return capture.collect_supplement(plan_value,day,dates,work,objects=objects,fetch=fetch,
        qmt_transport=transport,calendar_coverage=(DAYS[0],DAYS[-1]),previous=previous,
        deadline=time.monotonic()+20)


def test_next_day_proxy_reads_only_missing_tail_and_keeps_receipt(tmp_path):
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch();transport=QmtTransport()
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    previous=collect_at(targets,DAYS[0],[DAYS[0]],tmp_path/'first',objects,fetch,transport)
    first=_load(previous)['rows'][0]
    current=collect_at(targets,DAYS[1],DAYS,tmp_path/'next',objects,fetch,transport,previous)
    rows=_load(current)['rows']
    assert rows[0]==first and len(rows)==2
    assert len(transport.sdk_calls)==4
    assert all(r['arguments']['start_date']==DAYS[1].replace('-','')
               and r['arguments']['end_date']==DAYS[1].replace('-','') for r in transport.sdk_calls[2:])
    assert {r['unit'] for r in rows}=={'unknown'}


def test_partial_proxy_partition_resume_keeps_every_original_request(tmp_path,monkeypatch):
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch();transport=QmtTransport(max_rows=1)
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    original=capture._save;interrupted=False
    def stop_after_first(path,value):
        nonlocal interrupted
        original(path,value)
        if path.name=='STATE.json' and len(value.get('rows',{}))==1 and not interrupted:
            interrupted=True;raise InterruptedError('after first partition committed')
    with monkeypatch.context() as local:
        local.setattr(capture,'_save',stop_after_first)
        with pytest.raises(InterruptedError):collect_at(targets,DAYS[1],DAYS,tmp_path/'work',objects,fetch,transport)
    identities=[r['request_id'] for r in transport.sdk_calls]
    assert len(identities)==2
    descriptor=collect_at(targets,DAYS[1],DAYS,tmp_path/'work',objects,fetch,transport)
    assert len(_load(descriptor)['rows'])==2
    assert len(transport.sdk_calls)==4 and [r['request_id'] for r in transport.sdk_calls[:2]]==identities


def test_pending_day_rolls_to_next_day_with_successful_facts_preserved(tmp_path,monkeypatch):
    """实际serve跨闭合日：前日未发布成功行进入新日完整目录；Native发布边界显式替身。"""
    config,*_=owner_fixture(tmp_path)
    config['schedule']['poll_seconds']=.1
    config['inputs']['supplement_facts']=plan(('etf_total_shares','SSE.510300'),('margin_balance','CN.MARGIN_REPORT'))
    descriptor=write(tmp_path/'daily.json',config)
    control_id=str(uuid4());controls=tmp_path/'controls';controls.mkdir();control=controls/control_id
    fetches=[];published=[];clocks=0
    objects=ContentStore(config['raw_store'])
    def calendar(value):return [dict(date=d,is_open=1) for d in DAYS],None
    monkeypatch.setattr('guanheng_app.observation.calendars.official_calendar',calendar)
    def prepare(configuration,day,directory,**kwargs):
        work=Path(directory);work.mkdir(exist_ok=True)
        _save(work/'INPUTS.json',dict(configuration=configuration,day=day,previous_requests=kwargs['previous_requests']))
        fetch=FrozenFetch(bad_day=DAYS[0] if day==DAYS[0] else None);fetches.append(fetch)
        prior=capture.prior_supplement_catalogs(None,config['directory'],work,day,objects=objects,check=lambda:None)
        transport=QmtTransport()
        try:catalog=collect_at(configuration['inputs']['supplement_facts'],day,DAYS,work/'supplement',objects,fetch,transport,prior)
        finally:transport.close();fetch.close()
        return write(work/'UPDATE.json',dict(day=day,supplement_facts=catalog))
    def publish(request,directory,**kwargs):
        with_store=MarketSupplementStore(request['supplement_facts'])
        try:with_store.verify_sources();published.append(with_store.catalog)
        finally:with_store.close()
        # 关闭同一个持续owner；不创建第二个调度器或变更运行环境。
        _save(control/'stop.json',dict(schema='guanheng.daily-data-stop.v1',control_id=control_id,deadline=time.monotonic()+10))
        return dict(current_sha256='e'*64,supplement_complete=True)
    started=time.monotonic()
    def clock():
        nonlocal clocks
        assert time.monotonic()-started<8, 'daily owner failed to publish bounded synthetic next day'
        clocks+=1
        return datetime.fromisoformat((DAYS[0] if clocks==1 else DAYS[1])+'T16:00:00+08:00')
    monkeypatch.setattr(service,'prepare_update',prepare)
    monkeypatch.setattr(service,'run_update',publish)
    service.serve(descriptor,control,control_id,clock=clock)
    index=json.loads((Path(config['directory'])/'INDEX.json').read_bytes())
    assert index[DAYS[0]]['state']=='failed' and index[DAYS[1]]['state']=='published'
    assert len(published)==1 and published[0]['complete'] and len(published[0]['rows'])==4
    old=json.loads((Path(config['directory'])/DAYS[0]/'inputs/supplement/STATE.json').read_bytes())['rows']
    old_margin=next(iter(old.values()))
    assert old_margin in published[0]['rows']
    assert not any(p.get('reportName')=='RPTA_WEB_MARGIN_DAILYTRADE' and DAYS[0] in p['filter'] for _,p in fetches[-1].calls)
    assert json.loads((control/'closed.json').read_bytes())['owner_closed'] is True


def test_source_date_at_1530_is_shared_with_daily_owner(monkeypatch):
    monkeypatch.setattr('guanheng_app.observation.calendars.official_calendar',
        lambda config:([dict(date=d,is_open=1) for d in DAYS],None))
    calendar=dict(coverage_start=DAYS[0],coverage_end=DAYS[-1])
    assert service.target_date(calendar,datetime.fromisoformat(DAYS[1]+'T15:29:59+08:00'))==DAYS[0]
    assert service.target_date(calendar,datetime.fromisoformat(DAYS[1]+'T15:30:00+08:00'))==DAYS[1]


def test_observation_request_wakes_published_daily_service_and_reuses_index(tmp_path, monkeypatch):
    from guanheng_app.observation.storage import SnapshotRepository
    config, *_ = owner_fixture(tmp_path)
    config['inputs'].pop('supplement_facts')
    repository = SnapshotRepository(tmp_path/'observation')
    repository.initialize()
    config['observation_repair_root'] = str(repository.root)
    descriptor = write(tmp_path/'daily.json', config)
    now = datetime.fromisoformat(DAYS[-1]+'T16:00:00+08:00')
    monkeypatch.setattr(service, 'observe_input_reads', lambda *args, **kwargs: {})
    calls = []
    fail_once = False
    failed_phase_write = False
    break_phase_write = False
    index_path = Path(config['directory'])/'INDEX.json'
    original_save = service._save

    def save(path, value):
        nonlocal failed_phase_write
        if path == index_path and break_phase_write and not failed_phase_write and (
                value[DAYS[-1]].get('observation_repair',{}).get('phase') == 'readback'):
            failed_phase_write = True
            raise OSError('progress file temporarily busy')
        original_save(path, value)

    monkeypatch.setattr(service, '_save', save)
    def prepare(_config, day, directory, **kwargs):
        calls.append(day)
        return write(Path(directory)/'UPDATE.json', dict(day=day))
    def publish(*args, **kwargs):
        nonlocal fail_once
        kwargs['on_stage']('readback')
        if fail_once:
            fail_once = False
            raise OSError('transient source error')
        return dict(current_sha256='e'*64)
    monkeypatch.setattr(service, 'prepare_update', prepare)
    monkeypatch.setattr(service, 'run_update', publish)
    controls = tmp_path/'controls'
    controls.mkdir()
    def run():
        identity = str(uuid4())
        service.serve(descriptor, controls/identity, identity, once=True, as_of=DAYS[-1], clock=lambda: now)
    run()
    with repository.scheduler_lease() as lease:
        job = repository.request_data_repair('manual')
        job.update(state='running', wt_request=dict(dates=[DAYS[-1]], requested_at=now.isoformat()))
        repository.record_data_repair(job, lease=lease)
    fail_once = True
    with pytest.raises(RuntimeError, match='one cycle failed'):
        run()
    assert repository.data_repair()['wt_receipt']['state'] == 'running'
    assert repository.data_repair()['wt_receipt']['phase'] == 'retry_wait'
    break_phase_write = True
    run()
    assert failed_phase_write
    assert calls == [DAYS[-1], DAYS[-1]]
    assert repository.data_repair()['wt_receipt']['state'] == 'published'
    index = json.loads((Path(config['directory'])/'INDEX.json').read_bytes())
    assert index[DAYS[-1]]['revision'] == 1
    assert index[DAYS[-1]]['observation_repair']['id'] == job['id']
    run()
    assert len(calls) == 2


@pytest.mark.parametrize('input_stage', ['fresh', 'started', 'request_frozen'])
def test_manual_http_request_during_price_phase_gets_a_single_qualified_receipt(tmp_path, monkeypatch, input_stage):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timezone
    from fastapi.testclient import TestClient
    from guanheng_app.app import create_app
    from guanheng_app.observation import data_repair
    from guanheng_app.observation.runtime import build_reader
    from guanheng_app.settings import ConsoleSettings

    config, *_ = owner_fixture(tmp_path)
    config['inputs'].pop('supplement_facts')
    config['price_scope'] = dict(baseline_reference={}, reference_connection=None, scope={},
                                 authorized_from='20261104', maximum_history_rows=2000)
    reader = build_reader(tmp_path/'observation')
    repo = reader.repository
    repo.initialize()
    config['observation_repair_root'] = str(repo.root)
    descriptor = write(tmp_path/'daily.json', config)
    producer = Path(config['template']['publication_directory'])
    producer.mkdir()
    write(producer/'CURRENT.json', {})  # Native, prices and publication are deterministic stand-ins.
    day = DAYS[-1]
    now = datetime.fromisoformat(day+'T16:00:00+08:00')
    attach = input_stage == 'fresh'
    task = Path(config['directory'])/day
    if input_stage == 'started':
        (task/'inputs').mkdir(parents=True)
        write(task/'inputs'/'INPUTS.json', dict(day=day))
    elif input_stage == 'request_frozen':
        task.mkdir(parents=True)
        write(task/'REQUEST.json', dict(day=day))
    repo.publish(dict(source_tables={'source.cn_official_calendar':'calendar','market.sample':'market'},
                      datasets={}), None)
    rows = {'calendar':[dict(date=day,is_open=1)], 'market':[]}
    monkeypatch.setattr(reader, 'rows', rows.__getitem__)
    monkeypatch.setattr(data_repair, 'closed_market_day', lambda *args, **kwargs: day)
    monkeypatch.setattr(service, 'observe_input_reads', lambda *args, **kwargs: {})
    observation_config = dict(models={}, schedule=dict(wt_repair_enabled=True),
                              sources=[dict(id='wt',kind='wondertrader',tables=['market.sample'])])
    with repo.scheduler_lease() as lease:
        previous = repo.request_data_repair('startup')
        repo.record_data_repair(dict(previous,state='complete'), lease=lease)
        repo.record_scheduler(dict(enabled=True,state='running',phase='waiting',
            last_heartbeat=datetime.now(timezone.utc).isoformat(),heartbeat_max_age_seconds=60,
            schedule=dict(timezone='Asia/Shanghai',times=['09:00']),error_code=None), lease=lease)

    def repair_once():
        with repo.scheduler_lease() as lease:
            data_repair.repair(reader,observation_config,repo.data_repair(),now,lease=lease,
                deadline=time.monotonic()+10,cancelled=lambda:False,
                refresh=lambda *args, **kwargs:dict(status='success'),market_client_factory=None)

    app = create_app(settings=ConsoleSettings(observation_root=str(repo.root)))
    with TestClient(app,client=('127.0.0.1',1234),base_url='http://127.0.0.1') as client:
        path = '/v1/ui/market-observation'
        headers = {'origin':'http://127.0.0.1','sec-fetch-site':'same-origin'}
        manual = []

        def prices(*args, **kwargs):
            assert client.get(path+'/updates').json()['data_repair']['state'] == 'complete'
            response = client.post(path+'/data-repair',headers=headers)
            assert response.status_code == 202
            job = response.json()
            assert job['trigger'] == 'manual' and job['id'] != previous['id']
            manual.append(job['id'])
            assert client.post(path+'/data-repair',headers=headers).json()['id'] == job['id']
            repair_once()
            with ThreadPoolExecutor(max_workers=1) as pool:
                assert pool.submit(kwargs['cancelled']).result(timeout=5) is False
            assert 'wt_receipt' not in repo.data_repair()
            assert kwargs['cancelled']() is False
            receipt = client.get(path+'/updates').json()['data_repair'].get('wt_receipt')
            if attach:
                assert receipt['state'] == 'running' and receipt['phase'] == 'price_first'
            else:
                assert receipt is None
            return dict(current_sha256='a'*64,price_result=dict(path='synthetic',sha256='b'*64),
                        continuation_required=False,auxiliary_observation_date=DAYS[0])

        def prepare(_configuration, date, directory, **kwargs):
            assert input_stage != 'request_frozen'
            assert repo.data_repair().get('wt_receipt',{}).get('phase') == ('inputs' if attach else None)
            return write(Path(directory)/'UPDATE.json',dict(day=date))

        def publish(*args, **kwargs):
            kwargs['on_stage']('snapshot')
            assert repo.data_repair().get('wt_receipt',{}).get('phase') == ('snapshot' if attach else None)
            if attach:
                rows['market'].append(dict(date=day))
            return dict(current_sha256='e'*64)

        monkeypatch.setattr('integrations.guanheng.daily_price_refresh.price_refresh', prices)
        monkeypatch.setattr(service, 'prepare_update', prepare)
        monkeypatch.setattr(service, 'run_update', publish)
        control = str(uuid4())
        service.serve(descriptor,tmp_path/control,control,once=True,as_of=day,clock=lambda:now)
        if attach:
            repair_once()
        settled = client.get(path+'/updates').json()['data_repair']
        assert settled['id'] == manual[0]
        if attach:
            assert settled['state'] == 'complete' and settled['items'][0]['missing_count'] == 0
            assert settled['wt_receipt']['state'] == 'published' and 'phase' not in settled['wt_receipt']
        else:
            assert settled['state'] == 'running' and 'wt_receipt' not in settled


def test_new_observation_request_waits_through_failed_frozen_update(tmp_path, monkeypatch):
    from guanheng_app.observation.storage import SnapshotRepository

    config, *_ = owner_fixture(tmp_path)
    config['inputs'].pop('supplement_facts')
    repo = SnapshotRepository(tmp_path/'observation')
    repo.initialize()
    config['observation_repair_root'] = str(repo.root)
    descriptor = write(tmp_path/'daily.json',config)
    day = DAYS[-1]
    now = datetime.fromisoformat(day+'T16:00:00+08:00')
    completed = []
    fail = True
    monkeypatch.setattr(service,'observe_input_reads',lambda *args, **kwargs:{})

    def prepare(_configuration, date, directory, **kwargs):
        return write(Path(directory)/'UPDATE.json',dict(day=date, revision=len(completed)))

    def publish(request, work, **kwargs):
        if fail:
            raise OSError('retained input needs retry')
        assert repo.data_repair().get('wt_receipt') is None or request['revision'] == 1
        completed.append(request['revision'])
        return dict(current_sha256='e'*64)

    monkeypatch.setattr(service,'prepare_update',prepare)
    monkeypatch.setattr(service,'run_update',publish)

    def run():
        control = str(uuid4())
        service.serve(descriptor,tmp_path/control,control,once=True,as_of=day,clock=lambda:now)

    with pytest.raises(RuntimeError,match='one cycle failed'):
        run()
    with repo.scheduler_lease() as lease:
        manual = repo.request_data_repair('manual')
        manual.update(state='running',wt_request=dict(dates=[day],requested_at=now.isoformat()))
        repo.record_data_repair(manual,lease=lease)
    fail = False
    run()
    assert completed == [0] and repo.data_repair().get('wt_receipt') is None
    run()
    assert completed == [0,1]
    assert repo.data_repair()['wt_receipt']['state'] == 'published'


def test_price_attach_does_not_bind_when_observation_read_consumes_deadline(tmp_path, monkeypatch):
    day = DAYS[-1]
    task = {day:{}}
    path = tmp_path/'INDEX.json'
    calls = []
    def pending(repository,index,day,now,*,deadline,cancelled):
        calls.append((deadline,cancelled))
        return str(uuid4()),day
    monkeypatch.setattr(service,'pending_observation_repair',pending)
    monkeypatch.setattr(service.time,'monotonic',lambda:100)
    stopped = lambda: False
    assert service.attach_observation_during_prices(None,task,path,day,None,
        deadline=100,cancelled=stopped) is None
    assert calls == [(100,stopped)] and task == {day:{}} and not path.exists()


@pytest.mark.parametrize('prior_state', ['published', 'failed'])
def test_overtaken_observation_receipt_retires_its_running_phase(tmp_path, monkeypatch, prior_state):
    from guanheng_app.observation.storage import SnapshotRepository

    config, *_ = owner_fixture(tmp_path)
    config['inputs'].pop('supplement_facts')
    repository = SnapshotRepository(tmp_path/'observation')
    repository.initialize()
    config['observation_repair_root'] = str(repository.root)
    descriptor = write(tmp_path/'daily.json', config)
    previous, current = DAYS
    now = datetime.fromisoformat(current+'T16:00:00+08:00')
    with repository.scheduler_lease() as lease:
        job = repository.request_data_repair('startup')
        job.update(state='running', wt_request=dict(dates=[previous], requested_at=now.isoformat()))
        repository.record_data_repair(job, lease=lease)
    index_path = Path(config['directory'])/'INDEX.json'
    old_task = index_path.parent/previous
    journal = dict(status=prior_state, current_sha256='e'*64 if prior_state=='published' else None)
    write(old_task/'work'/'STATE.json', journal)
    write(index_path, {
        previous:dict(state='updating', request=str(old_task/'REQUEST.json'),
                      observation_repair=dict(id=job['id'], state='running', phase='prices')),
        current:dict(state='published'),
    })
    write(Path(config['template']['publication_directory'])/'CURRENT.json', {'fixture':True})
    monkeypatch.setattr(service, 'read_generation', lambda _: ({'observation_date':current}, '2'*64))
    monkeypatch.setattr(service, 'registered_requests', lambda _: [])
    monkeypatch.setattr(service, 'observe_input_reads', lambda *args, **kwargs: {})
    controls = tmp_path/'controls'
    controls.mkdir()
    identity = str(uuid4())
    service.serve(descriptor, controls/identity, identity, once=True, as_of=current, clock=lambda: now)
    receipt = repository.data_repair()['wt_receipt']
    assert receipt == dict(state=prior_state, observation_date=previous, current_sha256=journal['current_sha256'])
    saved = json.loads(index_path.read_bytes())[previous]['observation_repair']
    assert saved['state'] == prior_state and 'phase' not in saved


def test_manual_observation_request_revises_partial_wt_snapshot_and_fills_gap(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from guanheng_app.app import create_app
    from guanheng_app.observation import data_repair, etf_flow
    from guanheng_app.observation.runtime import build_reader
    from guanheng_app.settings import ConsoleSettings
    from integrations.guanheng.market_generation import read_generation
    from integrations.guanheng_market_client.exchange_calendar import digest, encode
    from test_daily_owner import patch_owner_dependencies

    config,pool,facts,original = owner_fixture(tmp_path)
    config['inputs']['supplement_facts']['required'] = False
    reader = build_reader(tmp_path/'observation')
    repository = reader.repository
    repository.initialize()
    config['observation_repair_root'] = str(repository.root)
    config_file = write(tmp_path/'daily.json',config)
    fetches,_,healthy = patch_owner_dependencies(monkeypatch,config,pool,facts,original)
    monkeypatch.setattr(service,'observe_input_reads',lambda *args,**kwargs:{})
    day = DAYS[-1]
    now = datetime.fromisoformat(day+'T16:00:00+08:00')
    source = dict(id='wt.etf_flow',kind=etf_flow.KIND,history_from=day,datasets=['etf_flow.510300'])
    observation_config = dict(sources=[source],schedule=dict(wt_repair_enabled=True),models={
        'calendars':{'cn':dict(kind='official-exchange-calendar/v1',coverage_start=DAYS[0],coverage_end=day,
                               verified_through=day,closed_dates=[],verified_open_dates_sha256=digest(encode(DAYS)))}})
    repository.publish(dict(datasets={},source_tables={'source.cn_official_calendar':'fixture-calendar'}),None)
    monkeypatch.setattr(reader,'rows',lambda _: [dict(date=d,is_open=1) for d in DAYS])
    controls = tmp_path/'controls'
    controls.mkdir()

    def run():
        identity = str(uuid4())
        service.serve(config_file,controls/identity,identity,once=True,as_of=day,clock=lambda:now)

    def current_catalog():
        current,sha = read_generation(Path(config['template']['publication_directory'])/'CURRENT.json')
        data = _load(current['configuration'])
        return sha,_load(data['supplement_facts'])

    run()
    first_sha,first = current_catalog()
    assert not first['complete'] and [gap['date'] for gap in first['gaps']]==[day]
    with repository.scheduler_lease() as lease:
        repository.record_scheduler(dict(enabled=True,state='running',phase='waiting',
            last_heartbeat=datetime.now(now.tzinfo).isoformat(),heartbeat_max_age_seconds=60,
            schedule=dict(timezone='Asia/Shanghai',times=['09:00']),error_code=None),lease=lease)
        startup = repository.request_data_repair('startup')
        startup.update(state='complete')
        repository.record_data_repair(startup,lease=lease)
        app = create_app(settings=ConsoleSettings(observation_root=str(repository.root)))
        with TestClient(app,client=('127.0.0.1',1234),base_url='http://127.0.0.1') as client:
            response = client.post('/v1/ui/market-observation/data-repair',
                                   headers={'origin':'http://127.0.0.1','sec-fetch-site':'same-origin'})
        assert response.status_code==202,response.json()
        job = repository.data_repair()
        assert job['trigger']=='manual' and job['id']==response.json()['id']
        data_repair.repair(reader,observation_config,job,now,lease=lease,deadline=time.monotonic()+10,
            cancelled=lambda:False,market_client_factory=None,
            refresh=lambda *args,**kwargs:dict(sources=[dict(requested_end=day,status='partial')]))
        waiting = repository.data_repair()
        assert waiting['items'][0]['state']=='waiting_for_wt_repair'
        assert waiting['wt_request']['dates']==[day]

    healthy['value'] = True
    run()
    second_sha,second = current_catalog()
    assert first_sha!=second_sha and second['complete'] and second['rows'][0]==first['rows'][0]
    assert [row['date'] for row in second['rows']]==DAYS
    assert len(fetches[-1].calls)==1 and fetches[-1].calls[0][1]['STAT_DATE']==day
    published = repository.data_repair()
    assert published['wt_receipt']['current_sha256']==second_sha

    def reread(*args,**kwargs):
        assert kwargs['repair_history_start']==day
        assert kwargs['source_ids']==[source['id']]
        assert current_catalog()[0]==second_sha
        row = next(row for row in second['rows'] if row['date']==day)
        manifest = reader.snapshot()[1]
        manifest['datasets'][source['datasets'][0]] = dict(partition='reloaded')
        reader.rows = lambda asset: ([dict(date=day,flow=int(row['value']))] if asset=='reloaded'
                                     else [dict(date=d,is_open=1) for d in DAYS])
        repository.publish(manifest,repository.current())
        return dict(sources=[dict(requested_end=day,status='success')])

    with repository.scheduler_lease() as lease:
        data_repair.repair(reader,observation_config,published,now,lease=lease,deadline=time.monotonic()+10,
            cancelled=lambda:False,market_client_factory=None,refresh=reread)
    final = repository.data_repair()
    assert final['id']==job['id'] and final['state']=='complete' and final['items'][0]['missing_count']==0


def test_prior_success_proof_damage_blocks_reuse_before_new_source(tmp_path):
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch(bad_day=DAYS[0]);transport=QmtTransport()
    targets=plan(('etf_total_shares','SSE.510300'),('margin_balance','CN.MARGIN_REPORT'))
    task=tmp_path/'tasks';old=task/DAYS[0]/'inputs/supplement'
    with pytest.raises(capture.SupplementPending):collect_at(targets,DAYS[0],DAYS,old,objects,fetch,transport)
    write(task/'INDEX.json',{DAYS[0]:dict(state='failed',request=str(task/DAYS[0]/'REQUEST.json'))})
    state=json.loads((old/'STATE.json').read_bytes());row=next(iter(state['rows'].values()))
    objects.path(row['source_sha256']).write_bytes(b'corrupt')
    current=task/DAYS[1]/'inputs';current.mkdir(parents=True)
    with pytest.raises(ValueError):capture.prior_supplement_catalogs(None,task,current,DAYS[1],objects=objects,check=lambda:None)
    assert not (current/'SUPPLEMENT-PRIORS.json').exists()


def test_partial_refresh_once_after_0900_next_civil_day(tmp_path,monkeypatch):
    """晚到来源在次自然日09:00修订同市场日，partial再次发布后当日不空转。"""
    config,*_=owner_fixture(tmp_path)
    config['schedule']['poll_seconds']=.1
    config['inputs']['supplement_facts']=plan(('etf_total_shares','SSE.510300'),required=False)
    descriptor=write(tmp_path/'daily.json',config)
    control_id=str(uuid4());(tmp_path/'controls').mkdir();control=tmp_path/'controls'/control_id
    objects=ContentStore(config['raw_store']);published=[];clocks=0;attempts=[]
    monkeypatch.setattr('guanheng_app.observation.calendars.official_calendar',
        lambda value:([dict(date=d,is_open=1) for d in DAYS],None))
    def prepare(configuration,day,directory,**kwargs):
        attempts.append(day);root=Path(directory);root.mkdir(exist_ok=True)
        _save(root/'INPUTS.json',dict(configuration=configuration,day=day,previous_requests=kwargs['previous_requests']))
        fetch=FrozenFetch(bad_day=DAYS[-1]);transport=QmtTransport()
        try:catalog=collect_at(configuration['inputs']['supplement_facts'],day,DAYS,root/'supplement',objects,
                fetch,transport,published[-1] if published else None)
        finally:fetch.close();transport.close()
        return write(root/'UPDATE.json',dict(supplement_facts=catalog))
    def publish(request,directory,**kwargs):
        published.append(request['supplement_facts'])
        return dict(current_sha256='b'*64,supplement_complete=_load(request['supplement_facts'])['complete'])
    started=time.monotonic()
    def clock():
        nonlocal clocks
        assert time.monotonic()-started<8
        clocks+=1
        if clocks==1:return datetime.fromisoformat(DAYS[-1]+'T16:00:00+08:00')
        if clocks==2:return datetime.fromisoformat('2026-11-06T08:59:00+08:00')
        if clocks>=6:
            _save(control/'stop.json',dict(schema='guanheng.daily-data-stop.v1',control_id=control_id,deadline=time.monotonic()+10))
        return datetime.fromisoformat('2026-11-06T09:01:00+08:00')
    monkeypatch.setattr(service,'prepare_update',prepare);monkeypatch.setattr(service,'run_update',publish)
    service.serve(descriptor,control,control_id,clock=clock)
    assert attempts==[DAYS[-1],DAYS[-1]] and len(published)==2
    index=json.loads((Path(config['directory'])/'INDEX.json').read_bytes())[DAYS[-1]]
    assert index['state']=='published' and index['revision']==1 and len(index['history_requests'])==1
    assert index['supplement_attempt_date']=='2026-11-06' and index['supplement_complete'] is False


def test_supplement_pending_read_slots_join_original_discovery(tmp_path):
    from integrations.guanheng.daily_input_recovery import _slot_candidates
    root=tmp_path/'inputs';slots=root/'supplement/qmt-slots';slots.mkdir(parents=True)
    slot=slots/'000001.SH.p0001.json';slot.write_text('{}',encoding='utf8')
    original=dict(inputs=dict(connections=dict(batch={'fixture':'original-batch'})))
    assert (slot,original['inputs']['connections']['batch']) in list(_slot_candidates(root,original))


@pytest.mark.parametrize('report_queue', [False, True])
def test_price_first_current_survives_public_source_timeout(tmp_path,monkeypatch,report_queue):
    """原价格发布边界先成功，随后公共预算超时只使完整任务失败，价格CURRENT保持。"""
    from guanheng_app.observation.source_fetch import SourceFailure
    config,*_=owner_fixture(tmp_path)
    config['inputs']['supplement_facts']['required']=False
    if report_queue:
        config['inputs']['supplement_facts']=plan(('margin_purchase','CN.MARGIN_REPORT'),required=False)
        def report_timeout(*args,**kwargs):
            raise SourceFailure('collection_timeout')
        monkeypatch.setattr(service,'prepare_report_inputs',report_timeout)
    config['price_scope']=dict(baseline_reference=config['template']['security_reference'],
        reference_connection={},scope={},authorized_from='20261104',maximum_history_rows=2000)
    descriptor=write(tmp_path/'daily.json',config)
    current=Path(config['template']['publication_directory'])/'CURRENT.json'
    current.parent.mkdir(exist_ok=True);current.write_bytes(b'old verified price boundary')
    control_id=str(uuid4());(tmp_path/'controls').mkdir();control=tmp_path/'controls'/control_id
    order=[]
    import integrations.guanheng.daily_price_refresh as price
    def price_ready(configuration,day,directory,**kwargs):
        order.append('price_published')
        current.write_bytes(b'new verified price boundary')  # Native/CAS边界替身，完整数据发布另由owner主链测试。
        root=Path(directory);root.mkdir(parents=True)
        result=write(root/'prices.json',{})
        return dict(current_sha256='a'*64,price_result=result,continuation_required=False,auxiliary_observation_date=DAYS[0])
    def source_timeout(*args,**kwargs):
        order.append('public_timeout')
        raise SourceFailure('collection_timeout')
    monkeypatch.setattr(price,'price_refresh',price_ready)
    monkeypatch.setattr(service,'prepare_update',source_timeout)
    with pytest.raises(RuntimeError,match='one cycle failed'):
        service.serve(descriptor,control,control_id,once=True,as_of=DAYS[-1])
    assert order==(['price_published'] if report_queue else ['price_published','public_timeout'])
    assert current.read_bytes()==b'new verified price boundary'
    state=json.loads((Path(config['directory'])/'INDEX.json').read_bytes())[DAYS[-1]]
    assert state['price_state']=='published' and state['state']=='failed'
    assert json.loads((control/'failure.json').read_bytes())['owner_closed'] is True


def test_stage_request_share_keeps_original_total_and_next_round_continues(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'),('margin_balance','CN.MARGIN_REPORT'),required=False)
    targets['max_requests']=2  # 本轮metadata+最新份额，融资/旧缺口留在后继轮次。
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch();transport=QmtTransport()
    original_max=fetch.budget.max_requests
    descriptor=collect_at(targets,DAYS[-1],DAYS,tmp_path/'first',objects,fetch,transport)
    first=_load(descriptor)
    assert fetch.budget.requests==2 and fetch.budget.max_requests==original_max
    assert len(first['rows'])==1 and first['rows'][0]['date']==DAYS[-1]
    assert first['complete'] is False and len(first['gaps'])==3
    # 未取消日更；新轮额度按原总账继续扣，seed行不重抓。
    targets=deepcopy(targets);targets['max_requests']=8
    result=collect_at(targets,DAYS[-1],DAYS,tmp_path/'next',objects,fetch,transport,descriptor)
    assert _load(result)['complete'] and len(_load(result)['rows'])==4
    assert first['rows'][0] in _load(result)['rows']
    assert fetch.budget.max_requests==original_max


def test_report_preparation_survives_restart_without_qmt_or_repeat_fetch(tmp_path):
    targets=plan(('margin_purchase','CN.MARGIN_REPORT'),('etf_total_shares','SSE.510300'))
    objects=ContentStore(tmp_path/'raw')
    work=tmp_path/'supplement'
    fetch=FrozenFetch()
    def prepare():
        capture.collect_supplement(targets,DAYS[-1],DAYS,work,objects=objects,fetch=fetch,
            qmt_transport=None,calendar_coverage=(DAYS[0],DAYS[-1]),deadline=time.monotonic()+20,reports_only=True)
    prepare()
    before=list(fetch.calls)
    assert len(before)==2 and all(params['reportName']=='RPTA_WEB_MARGIN_DAILYTRADE' for _,params in before)
    assert not (work/'QMT-EVIDENCE.json').exists() and not (work/'catalog.json').exists()
    assert json.loads((work/'STATE.json').read_bytes())['report_preparation']['observed']==2
    prepare()
    assert fetch.calls==before
    completed=collect_at(targets,DAYS[-1],DAYS,work,objects,fetch,QmtTransport())
    assert _load(completed)['complete']
    assert len(fetch.calls)==4
    assert all('reportName' not in params for _,params in fetch.calls[len(before):])


def test_report_prepares_while_price_is_in_flight_and_only_owner_publishes(tmp_path,monkeypatch):
    from integrations.guanheng import daily_price_refresh as price
    config,*_=owner_fixture(tmp_path)
    config['inputs']['supplement_facts']=plan(('margin_purchase','CN.MARGIN_REPORT'))
    config['price_scope']=dict(baseline_reference=config['template']['security_reference'],
        reference_connection={},scope={},authorized_from='20261104',maximum_history_rows=2000)
    descriptor=write(tmp_path/'daily.json',config)
    current=Path(config['template']['publication_directory'])/'CURRENT.json'
    current.parent.mkdir(exist_ok=True)
    current.write_bytes(b'previous publication')
    control_id=str(uuid4());(tmp_path/'controls').mkdir();control=tmp_path/'controls'/control_id
    price_started=Event()
    report_prepared=Event()
    owner=get_ident()
    def reports(configuration,day,directory,**kwargs):
        assert get_ident()!=owner and price_started.wait(5)
        write(directory/'proof.json',dict(day=day,phase='report_ready'))
        assert current.read_bytes()==b'previous publication'
        report_prepared.set()
    def prices(configuration,day,directory,**kwargs):
        price_started.set()
        assert report_prepared.wait(5)
        result=write(Path(directory)/'prices.json',{})
        return dict(current_sha256='a'*64,price_result=result,continuation_required=False,auxiliary_observation_date=DAYS[0])
    def prepare(configuration,day,directory,**kwargs):
        assert json.loads((directory/'proof.json').read_bytes())==dict(day=day,phase='report_ready')
        return write(directory/'UPDATE.json',dict(day=day))
    def publish(request,*args,**kwargs):
        assert get_ident()==owner and request['day']==DAYS[-1]
        return dict(current_sha256='b'*64,supplement_complete=True)
    monkeypatch.setattr(service,'prepare_report_inputs',reports)
    monkeypatch.setattr(price,'price_refresh',prices)
    monkeypatch.setattr(service,'prepare_update',prepare)
    monkeypatch.setattr(service,'run_update',publish)
    service.serve(descriptor,control,control_id,once=True,as_of=DAYS[-1])
    state=json.loads((Path(config['directory'])/'INDEX.json').read_bytes())[DAYS[-1]]
    assert state['state']=='published' and state['supplement_complete'] and state['current_sha256']=='b'*64


def test_unmaterialized_request_keeps_original_input_slot_reference(tmp_path):
    from integrations.guanheng.daily_input_recovery import observe_input_reads
    # 只有INPUTS及尚未尝试原槽，外层REQUEST尚未写入；恢复禁止借机派发。
    root=tmp_path/'legacy/inputs';slot=root/'supplement/qmt-slots/000001.SH.json'
    slot.parent.mkdir(parents=True)
    slot.write_text('{"request":{}}',encoding='utf8')
    intent=write(root/'INPUTS.json',dict(day=DAYS[0],configuration=dict(inputs=dict(connections=dict(batch={}))),previous_requests=[]))
    state=dict(consumed=set(),pending=set(),checked={},slots={},roots=set(),discovery={},discovered=set())
    result=observe_input_reads({},state,target_day=DAYS[-1],deadline=time.monotonic()+2,cancelled=lambda:False,
                               prior_inputs=[intent])
    assert str(slot) in state['pending'] and result['pending']==1
    assert not (root.parent/'REQUEST.json').exists()


def test_proxy_plan_drift_rejected_before_unknown_original_is_reissued(tmp_path):
    from guanheng_qmt_shm.read_retention_client import RetainedReadPending
    objects=ContentStore(tmp_path/'raw');fetch=FrozenFetch();transport=QmtTransport(lose_first=True)
    target=plan(('market_turnover_proxy','CN.SH_SZ'));work=tmp_path/'work'
    with pytest.raises(RetainedReadPending):collect_at(target,DAYS[-1],DAYS,work,objects,fetch,transport)
    assert len(transport.sdk_calls)==1
    state=json.loads((work/'STATE.json').read_bytes())
    state['proxy_plan'][0]['requests'][0]['arguments']['symbol']='600000.SH'
    _save(work/'STATE.json',state)
    with pytest.raises(ValueError,match='original arguments'):
        collect_at(target,DAYS[-1],DAYS,work,objects,fetch,transport)
    assert len(transport.sdk_calls)==1
