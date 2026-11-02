"""计划身份、网络前持久尝试、取消及停止监视的业务约束。"""
from datetime import datetime,timedelta,timezone
from time import monotonic
import json
import threading
import pytest
from guanheng_app.observation.collection import refresh
from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.schedule_policy import due_windows,window_as_of
from guanheng_app.observation.source_fetch import BoundedContentStore,CollectionBudget,SourceFailure
from guanheng_app.observation_service import StopController
from guanheng_app.observation import scheduler

SCHEDULE=dict(timezone='Asia/Shanghai',times=['09:00'],poll_seconds=1)
KEY='2026-10-29T09:00:00+08:00'
NOW=datetime.fromisoformat(KEY)


def test_due_windows_use_shanghai_midnight_and_bounded_commissioning():
    before=datetime.fromisoformat('2026-10-29T00:59:59+00:00')
    assert [key for key,_ in due_windows(before,SCHEDULE)]==['2026-10-28T09:00:00+08:00']
    assert [key for key,_ in due_windows(NOW,SCHEDULE)]==['2026-10-28T09:00:00+08:00',KEY]
    assert due_windows(before,SCHEDULE|{'start_date':'2026-10-29'})==[]
    assert [key for key,_ in due_windows(NOW,SCHEDULE,completed=[KEY])]==['2026-10-28T09:00:00+08:00']
    assert window_as_of(KEY,NOW)=='2026-10-28'
    with pytest.raises(ObservationError,match='时钟'):due_windows(NOW.replace(tzinfo=None),SCHEDULE)


@pytest.mark.parametrize('key',[
    '2026-10-29T09:00:00','2026-10-29T09:00:00+00:00','2026-10-29T09:00:01+08:00',
    '2026-10-30T09:00:00+08:00','2026-10-27T09:00:00+08:00','bad',
])
def test_window_rejects_future_old_naive_and_different_clock(key):
    with pytest.raises(ObservationError):window_as_of(key,NOW)


def test_reserved_attempt_survives_new_reader_without_receipt_and_obeys_backoff(tmp_path):
    reader=build_reader(tmp_path);reader.repository.initialize()
    first=reader.repository.reserve_window_attempt(KEY,NOW,2,60)
    assert first==dict(status='reserved',window_key=KEY,attempt_number=1,started_at=NOW.isoformat())
    resumed=build_reader(tmp_path)
    assert resumed.repository.runs()==[]
    assert resumed.repository.reserve_window_attempt(KEY,NOW+timedelta(seconds=59),2,60)['status']=='window_backoff'
    second=resumed.repository.reserve_window_attempt(KEY,NOW+timedelta(seconds=60),2,60)
    assert second['attempt_number']==2
    assert resumed.repository.reserve_window_attempt(KEY,NOW+timedelta(days=1),2,60)['status']=='window_attempts_exhausted'
    assert resumed.repository.window_attempt(KEY)[0]==2


@pytest.mark.parametrize('stopped',[True,False])
def test_stopped_or_expired_caller_consumes_no_attempt_and_no_source(tmp_path,stopped):
    reader=build_reader(tmp_path);reader.repository.initialize();calls=[]
    with pytest.raises(SourceFailure) as caught:
        refresh(reader,dict(max_window_attempts=2,retry_seconds=60),as_of='2026-10-28',
            deadline=monotonic()+(10 if stopped else -1),cancelled=lambda:stopped,window_key=KEY,now=NOW,
            fetcher_factory=lambda *args,**kwargs:calls.append(1))
    assert caught.value.code==('collection_stopped' if stopped else 'collection_timeout')
    assert reader.repository.window_attempt(KEY)==(0,None) and not calls


def test_content_cancellation_preserves_original_objects(tmp_path):
    reader=build_reader(tmp_path);reader.repository.initialize();sha=reader.objects.put(b'retained')
    stopped=threading.Event();store=BoundedContentStore(reader.objects,CollectionBudget(monotonic()+10,cancelled=stopped.is_set))
    assert store.get(sha)==b'retained';stopped.set()
    with pytest.raises(SourceFailure):store.get(sha)
    with pytest.raises(SourceFailure):store.put(b'not-published')
    assert reader.objects.get(sha)==b'retained'


@pytest.mark.parametrize('invalid',[False,True])
def test_stop_monitor_requires_matching_identity_and_joins(tmp_path,invalid):
    stop=StopController(tmp_path,'identity');stop.monitor.start()
    deadline=monotonic()+3
    (tmp_path/'stop.json').write_text(json.dumps(dict(schema='guanheng.observation-stop.v1',
        control_id='different' if invalid else 'identity',deadline=deadline)),encoding='utf8')
    try:
        assert stop.wait(2)
        assert (stop.error=='stop_control') is invalid
        assert stop.deadline==(None if invalid else deadline)
    finally:assert stop.close()
    assert not stop.monitor.pending


@pytest.mark.parametrize('offset',[-1000,30,60,1000])
def test_stale_and_future_heartbeat_has_no_liveness_claim(tmp_path,offset):
    reader=build_reader(tmp_path);reader.repository.initialize()
    now=datetime.now(timezone.utc)+timedelta(seconds=offset)
    with reader.repository.scheduler_lease() as lease:
        reader.repository.record_scheduler(dict(enabled=True,state='running',phase='waiting',
            last_heartbeat=now.isoformat(),heartbeat_max_age_seconds=10,
            schedule=dict(timezone='Asia/Shanghai',times=['09:00']),error_code=None),lease=lease)
    assert reader.repository.scheduler_status()['state']=='not_running_or_stale'


@pytest.mark.parametrize('field,value',[('enabled','true'),('state','ready'),('phase','unknown'),
    ('last_heartbeat','2026-10-29T00:00:00'),('heartbeat_max_age_seconds',float('nan')),
    ('schedule',{'timezone':'UTC','times':['09:00']}),('error_code','private-error')])
def test_bad_scheduler_state_rejected_on_write_and_read(tmp_path,field,value):
    reader=build_reader(tmp_path);reader.repository.initialize()
    status=dict(enabled=True,state='running',phase='waiting',last_heartbeat=datetime.now(timezone.utc).isoformat(),
        heartbeat_max_age_seconds=10,schedule=dict(timezone='Asia/Shanghai',times=['09:00']),error_code=None)
    status[field]=value
    with reader.repository.scheduler_lease() as lease:
        with pytest.raises(ObservationError):reader.repository.record_scheduler(status,lease=lease)
    with reader.repository.connect(writing=True) as db:
        db.execute('INSERT INTO scheduler_state VALUES(1,?)',(json.dumps(status).encode(),))
    with pytest.raises(ObservationError):reader.repository.scheduler_status()


@pytest.mark.parametrize('age',[60,1000,86400])
def test_explicit_normal_stop_remains_stopped_after_heartbeat_age(tmp_path,age):
    reader=build_reader(tmp_path);reader.repository.initialize()
    with reader.repository.scheduler_lease() as lease:
        reader.repository.record_scheduler(dict(enabled=False,state='stopped',phase='stopped',
            last_heartbeat=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
            heartbeat_max_age_seconds=10,schedule=dict(timezone='Asia/Shanghai',times=['09:00']),
            error_code=None),lease=lease)
    actual=reader.repository.scheduler_status()
    assert actual['state']=='stopped' and actual['enabled'] is False and actual['phase']=='stopped'


def test_second_scheduler_cannot_override_active_root_or_write_stopped(tmp_path,monkeypatch):
    reader=build_reader(tmp_path);reader.repository.initialize();reader.repository.publish({'fixture':True},None)
    entered=threading.Event();release=threading.Event();stop_a=threading.Event();stop_b=threading.Event();errors=[];ready_b=[]
    def tick(*args,**kwargs):
        if threading.current_thread().name=='scheduler-a':entered.set();release.wait(5)
        else:stop_b.set()
        return {}
    monkeypatch.setattr(scheduler,'tick',tick)
    config=dict(budget=dict(seconds=10),schedule=SCHEDULE)
    def first():
        try:scheduler.run(reader,config,stop_a)
        except BaseException as exc:errors.append(exc)
    thread=threading.Thread(target=first,name='scheduler-a');thread.start();assert entered.wait(2)
    try:
        with pytest.raises(ObservationError) as caught:
            scheduler.run(build_reader(tmp_path),config,stop_b,on_ready=lambda:ready_b.append(True))
        assert caught.value.code=='scheduler_already_running' and not ready_b
        state=reader.repository.scheduler_status()
        assert state['enabled'] and state['state']=='running' and state['phase']=='collecting'
    finally:stop_a.set();release.set();thread.join(3)
    assert not thread.is_alive() and not errors
    stop_b.set();scheduler.run(build_reader(tmp_path),config,stop_b,on_ready=lambda:ready_b.append(True))
    assert ready_b==[True] and reader.repository.scheduler_status()['state']=='stopped'


def test_scheduler_lease_cannot_be_reused_after_release_or_by_another_thread(tmp_path):
    reader=build_reader(tmp_path);reader.repository.initialize();errors=[]
    status=dict(enabled=True,state='running',phase='waiting',last_heartbeat=datetime.now(timezone.utc).isoformat(),
        heartbeat_max_age_seconds=10,schedule=dict(timezone='Asia/Shanghai',times=['09:00']),error_code=None)
    with reader.repository.scheduler_lease() as lease:
        # 调度存续期锁和单批采集锁分别拥有职责，允许本调度启动采集。
        with reader.repository.collection_lease() as acquired:assert acquired
        def foreign_write():
            try:reader.repository.record_scheduler(status,lease=lease)
            except ObservationError as exc:errors.append(exc.code)
        thread=threading.Thread(target=foreign_write);thread.start();thread.join(2)
        assert not thread.is_alive() and errors==['scheduler_owner_required']
        reader.repository.record_scheduler(status,lease=lease)
    with pytest.raises(ObservationError) as caught:reader.repository.record_scheduler(status,lease=lease)
    assert caught.value.code=='scheduler_owner_required'


def test_heartbeat_atomic_replace_failure_preserves_previous_complete_state(tmp_path,monkeypatch):
    from guanheng_app.observation import storage
    reader=build_reader(tmp_path);reader.repository.initialize()
    status=dict(enabled=True,state='running',phase='waiting',last_heartbeat=datetime.now(timezone.utc).isoformat(),
        heartbeat_max_age_seconds=602,schedule=dict(timezone='Asia/Shanghai',times=['09:00']),error_code=None)
    with reader.repository.scheduler_lease() as lease:
        reader.repository.record_scheduler(status,lease=lease)
        before=(tmp_path/'scheduler-status.json').read_bytes()
        def fail(*_args):raise OSError('fixture atomic replace failure')
        monkeypatch.setattr(storage,'replace_readable_file',fail)
        with pytest.raises(OSError):reader.repository.record_scheduler(status|{'phase':'collecting'},lease=lease)
        assert (tmp_path/'scheduler-status.json').read_bytes()==before
        assert reader.repository.scheduler_status()==status
        assert not list(tmp_path.glob('.incoming-*'))


@pytest.mark.parametrize('raw',[b'private-invalid',b' '*4097,b'['*1500+b']'*1500])
def test_corrupt_current_heartbeat_does_not_fall_back_to_legacy_status(tmp_path,raw):
    reader=build_reader(tmp_path);reader.repository.initialize()
    (tmp_path/'scheduler-status.json').write_bytes(raw)
    with pytest.raises(ObservationError) as caught:reader.repository.scheduler_status()
    assert caught.value.code in ('invalid_scheduler_status','scheduler_budget_exceeded')



def test_heartbeat_writer_preserves_legitimate_open_old_snapshot(tmp_path):
    """Windows共享DELETE读者保持旧代时，心跳仍可原子发布新代。"""
    from guanheng_app.managed_local_process import _open_read
    reader=build_reader(tmp_path);reader.repository.initialize()
    status=dict(enabled=True,state='running',phase='waiting',last_heartbeat=NOW.isoformat(),
        heartbeat_max_age_seconds=602,schedule=dict(timezone='Asia/Shanghai',times=['09:00']),error_code=None)
    with reader.repository.scheduler_lease() as lease:
        reader.repository.record_scheduler(status,lease=lease)
        with _open_read(tmp_path/'scheduler-status.json') as original:
            reader.repository.record_scheduler(status|{'phase':'collecting'},lease=lease)
            assert json.loads(original.read())==status
            assert reader.repository.scheduler_status()['phase']=='collecting'
    assert not list(tmp_path.glob('.incoming-*'))


def test_owner_failure_metadata_preserves_code_location_and_omits_message():
    from guanheng_app.observation_service import _failure_metadata
    try:
        raise PermissionError(13,'synthetic-private-response-must-not-appear')
    except OSError as error:
        value=_failure_metadata(error,'scheduler')
    assert value['stage']=='scheduler'
    assert value['exceptions'][0]['error_type']=='PermissionError' and value['exceptions'][0]['errno']==13
    assert 'synthetic-private' not in json.dumps(value)


def test_failure_metadata_has_fixed_numeric_fields_and_global_position_budget():
    from guanheng_app.observation_service import _failure_metadata
    namespace={'__name__':'guanheng_app.synthetic_diagnostic'}
    exec("def nested(n):\n    if n: return nested(n-1)\n    raise OSError(13,'synthetic-private-response')",namespace)
    chain=[]
    for i in range(3):
        try:namespace['nested'](6)
        except OSError as error:
            error.errno=['synthetic-private-response',2**40,True][i]
            error.winerror='synthetic-private-response'
            if chain:error.__cause__=chain[-1]
            chain.append(error)
    value=_failure_metadata(chain[-1],'scheduler')
    assert len(value['exceptions'])==3 and sum(len(e['frames']) for e in value['exceptions'])<=4
    assert all(e['errno'] is None and e['winerror'] is None for e in value['exceptions'])
    body=json.dumps(value).encode()
    assert b'synthetic-private-response' not in body and len(body)<4096


@pytest.mark.parametrize('close_failure',[False,True])
def test_service_logical_stop_failures_keep_bounded_diagnostic(tmp_path,monkeypatch,close_failure):
    from guanheng_app import observation_service as service
    from uuid import uuid4
    control=tmp_path/'control';control.mkdir();identity=str(uuid4());directory=control/identity
    monkeypatch.setattr(service,'load_service_configuration',lambda *_:dict(root=str(tmp_path/'data'),sources_file='SDK',sources_sha256='a'*64))
    monkeypatch.setattr(service,'load_configuration',lambda *_:dict(sources=[]))
    def run(_reader,_config,stop,**_kwargs):
        if close_failure:stop.deadline=monotonic()+2;stop.event.set()
    monkeypatch.setattr(service,'run',run)
    if close_failure:
        original=service.StopController
        class Stop(original):
            def close(self):
                assert super().close()
                return False
        monkeypatch.setattr(service,'StopController',Stop)
    assert service.serve('SDK','a'*64,directory,identity)==1
    failure=json.loads((directory/'failure.json').read_bytes())
    assert failure['error_code']==('close' if close_failure else 'stop_missing')
    diagnostic=json.loads((directory/'diagnostic.json').read_bytes())
    assert diagnostic['stage']=='shutdown' and diagnostic['exceptions']==[]
    assert not (directory/'closed.json').exists()
