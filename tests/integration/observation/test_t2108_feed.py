"""定日封存包的发布/消费与原refresh回归；全部使用显式协议替身。"""
import json
import os
import subprocess
from contextlib import contextmanager
from datetime import date,timedelta
from pathlib import Path
from time import monotonic

import pytest

from guanheng_app.observation import t2108_feed as feed
from guanheng_app.observation.calendars import official_calendar
from guanheng_app.observation.collection import refresh
from guanheng_app.observation.collection_config import validate_configuration
from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.source_fetch import SourceFailure
from guanheng_app.observation.storage import SnapshotRepository,digest,encode
from guanheng_app.observation.t2108_feed_cli import main as publish_main
from test_t2108 import DAY,Fetch,config,inputs,legacy_snapshot,reader_at,rewrite


def calendar():
    days=[(date(2026,10,26)+timedelta(days=n)).isoformat() for n in range(5)]
    return dict(kind='official-exchange-calendar/v1',id='explicit-test-calendar',
        coverage_start=days[0],coverage_end='2026-11-03',verified_through=DAY,
        closed_dates=[],verified_open_dates_sha256=digest(encode(days)),
        method='explicit test calendar only',evidence=[])


def setup(tmp_path):
    root=tmp_path/'feed';root.mkdir()
    (root/'packets').mkdir()
    fixed,files=inputs(root/'packets'/'original')
    reader=reader_at(tmp_path/'reader')
    return root,fixed,files,reader


def publish(root,fixed,reader):
    return feed.publish_ready(Fetch(reader),root,fixed['input_manifest'],fixed['input_sha256'],
        calendar=calendar(),start='2026-10-26',end='2026-11-01')


def test_sealed_packet_weekend_publication_and_original_refresh(tmp_path):
    root,fixed,_,reader=setup(tmp_path);legacy_snapshot(reader,fixed)
    old=reader.repository.current()
    result=publish(root,fixed,reader)
    assert result['status']=='published' and result['observation_date']==DAY
    assert reader.repository.current()==old
    source={key:value for key,value in fixed.items() if key not in ('input_manifest','input_sha256')}
    source['input_directory']=str(root)
    configuration=config(source);configuration['models']['calendars']={'cn':calendar()}
    assert validate_configuration(configuration)==configuration
    run=refresh(reader,configuration,as_of='2026-11-01',deadline=monotonic()+60)
    assert run['status']=='success'
    _,manifest=reader.snapshot();rows=reader.rows(manifest['datasets']['t2108.ashare']['partition'])
    assert [row['date'] for row in rows]==['2026-10-29',DAY]
    assert rows[0]['market_count']==2 and rows[1]['market_count']==1
    assert publish(root,fixed,reader)['status']=='already_published'


def test_target_day_missing_never_consumes_previous_date(tmp_path):
    root,fixed,_,reader=setup(tmp_path);publish(root,fixed,reader)
    source=dict(input_directory=str(root))
    with pytest.raises(SourceFailure,match='t2108_ready_not_available'):
        feed.history(Fetch(reader),source,'2026-10-26','2026-11-02',calendar=calendar())
    assert not (root/'2026-11-02/CURRENT.json').exists()


def test_calendar_coverage_missing_and_holiday_dates(tmp_path):
    local=calendar();local['closed_dates']=[DAY]
    local['verified_open_dates_sha256']=digest(encode(['2026-10-26','2026-10-27','2026-10-28','2026-10-29']))
    assert feed.observation_day(local,'2026-10-26','2026-11-01')=='2026-10-29'
    for cal,start,end in [(None,DAY,DAY),(calendar(),DAY,'2026-11-04'),(calendar(),'2026-10-31','2026-11-01')]:
        with pytest.raises(SourceFailure):feed.observation_day(cal,start,end)


def test_invalid_packet_keeps_existing_ready_marker(tmp_path):
    root,fixed,files,reader=setup(tmp_path);publish(root,fixed,reader)
    path=root/DAY/'CURRENT.json';before=path.read_bytes()
    rewrite(fixed,files,'CAPTURE.json',lambda value:value.update(observation_date='2026-10-29'))
    with pytest.raises(SourceFailure):publish(root,fixed,reader)
    assert path.read_bytes()==before


@pytest.mark.parametrize('case',['absolute','escape','unknown_field','wrong_day','sha'])
def test_marker_identity_and_path_validation(tmp_path,case):
    root,fixed,_,reader=setup(tmp_path);publish(root,fixed,reader)
    path=root/DAY/'CURRENT.json';value=json.loads(path.read_bytes())
    if case=='absolute':value['input']['path']=fixed['input_manifest']
    if case=='escape':value['input']['path']='../../reader/catalog.sqlite3'
    if case=='unknown_field':value['extra']=True
    if case=='wrong_day':value['observation_date']='2026-10-29'
    if case=='sha':value['input']['sha256']='a'*64
    path.write_bytes(encode(value))
    with pytest.raises(SourceFailure):
        feed.history(Fetch(reader),dict(input_directory=str(root)),DAY,'2026-11-01',calendar=calendar())


def test_other_publisher_retains_marker_and_original_lease(tmp_path):
    root,fixed,_,reader=setup(tmp_path);publish(root,fixed,reader)
    path=root/DAY/'CURRENT.json';before=path.read_bytes()
    with SnapshotRepository(root/'.publisher').collection_lease() as acquired:
        assert acquired
        assert publish(root,fixed,reader)['status']=='another_owner_running'
    assert path.read_bytes()==before


def test_sealed_revision_uses_new_identity_and_original_numeric_parser(tmp_path):
    root,fixed,_,reader=setup(tmp_path);first=publish(root,fixed,reader)
    revision,_=inputs(root/'packets'/'revision',last=8)
    second=publish(root,revision,reader)
    assert second['status']=='published' and second['input_sha256']!=first['input_sha256']
    rows=feed.history(Fetch(reader),dict(input_directory=str(root)),DAY,'2026-11-01',calendar=calendar())
    assert rows['t2108.ashare'][0]['below_count']==1
    assert rows['t2108.ashare'][0]['above_count']==0


def test_deadline_after_atomic_commit_preserves_same_identity_for_recheck(tmp_path,monkeypatch):
    root,fixed,_,reader=setup(tmp_path);context=Fetch(reader)
    original=feed.replace_readable_file
    def commit_then_expire(source,target):
        original(source,target)
        if getattr(target,'name',None)=='CURRENT.json':context.budget.deadline=monotonic()-1
    # 原子切换已完成，但原D过期：必须保留同标记并报告未知，不能当未发布重生身份。
    monkeypatch.setattr(feed,'replace_readable_file',commit_then_expire)
    with pytest.raises(SourceFailure,match='t2108_ready_publication_unknown'):
        feed.publish_ready(context,root,fixed['input_manifest'],fixed['input_sha256'],
            calendar=calendar(),start=DAY,end='2026-11-01')
    monkeypatch.setattr(feed,'replace_readable_file',original)
    assert publish(root,fixed,reader)['status']=='already_published'


def test_expired_original_deadline_never_replaces_existing_marker(tmp_path):
    root,fixed,_,reader=setup(tmp_path);publish(root,fixed,reader)
    marker=root/DAY/'CURRENT.json';before=marker.read_bytes()
    with pytest.raises(SourceFailure,match='collection_timeout'):
        feed.publish_ready(Fetch(reader,deadline=monotonic()-1),root,fixed['input_manifest'],fixed['input_sha256'],
            calendar=calendar(),start=DAY,end='2026-11-01')
    assert marker.read_bytes()==before


def test_public_cli_uses_pinned_configuration_and_only_stores_original_objects(tmp_path,capsys):
    root,fixed,_,_=setup(tmp_path)
    source={key:value for key,value in fixed.items() if key not in ('input_manifest','input_sha256')}
    source['input_directory']=str(root)
    configuration=config(source);configuration['models']['calendars']={'cn':calendar()}
    path=tmp_path/'sources.json';path.write_bytes(encode(configuration))
    objects=tmp_path/'publication-objects'
    args=['--root',str(objects),'--config',str(path),'--config-sha256',digest(path.read_bytes()),
        '--source-id',source['id'],'--input-manifest',fixed['input_manifest'],'--input-sha256',fixed['input_sha256'],
        '--as-of','2026-11-01','--seconds','60']
    assert publish_main(args)==0
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='published' and result['http_requests']==result['sdk_requests']==0
    assert (objects/'objects/sha256').is_dir() and not (objects/'catalog.sqlite3').exists()
    args[args.index('--config-sha256')+1]='a'*64
    assert publish_main(args)==1
    assert json.loads(capsys.readouterr().out)['error_code']=='invalid_collection_configuration'


def test_repeated_publication_rechecks_deadline_after_marker_read(tmp_path,monkeypatch):
    root,fixed,_,reader=setup(tmp_path);publish(root,fixed,reader);context=Fetch(reader)
    original=feed._open_read
    @contextmanager
    def late(path):
        with original(path) as stream:yield stream
        context.budget.deadline=monotonic()-1
    monkeypatch.setattr(feed,'_open_read',late)
    with pytest.raises(SourceFailure,match='collection_timeout'):
        feed.publish_ready(context,root,fixed['input_manifest'],fixed['input_sha256'],
            calendar=calendar(),start=DAY,end='2026-11-01')


def test_repeated_publication_rechecks_deadline_after_lease_release(tmp_path,monkeypatch):
    root,fixed,_,reader=setup(tmp_path);publish(root,fixed,reader);context=Fetch(reader)
    original=SnapshotRepository.collection_lease
    @contextmanager
    def late(repository):
        with original(repository) as acquired:yield acquired
        context.budget.deadline=monotonic()-1
    monkeypatch.setattr(SnapshotRepository,'collection_lease',late)
    with pytest.raises(SourceFailure,match='t2108_ready_publication_unknown'):
        feed.publish_ready(context,root,fixed['input_manifest'],fixed['input_sha256'],
            calendar=calendar(),start=DAY,end='2026-11-01')


def test_consumer_open_marker_allows_real_atomic_revision_and_keeps_old_bytes(tmp_path,monkeypatch):
    root,fixed,_,reader=setup(tmp_path);publish(root,fixed,reader)
    revision,_=inputs(root/'packets'/'revision',last=8)
    original=feed._open_read;entered=[]
    @contextmanager
    def concurrent(path):
        with original(path) as stream:
            if not entered:
                entered.append(True)
                assert publish(root,revision,reader)['status']=='published'
            yield stream
    # 在消费方真实Windows读句柄仍打开时切换标记；旧流完整，下一次读取完整新版本。
    monkeypatch.setattr(feed,'_open_read',concurrent)
    old=feed.history(Fetch(reader),dict(input_directory=str(root)),DAY,'2026-11-01',calendar=calendar())
    assert entered and old['t2108.ashare'][0]['above_count']==1
    monkeypatch.setattr(feed,'_open_read',original)
    new=feed.history(Fetch(reader),dict(input_directory=str(root)),DAY,'2026-11-01',calendar=calendar())
    assert new['t2108.ashare'][0]['below_count']==1


def test_wide_calendar_uses_bounded_selection_and_original_calendar_rows():
    wide=calendar();wide.update(coverage_start='1900-01-01',coverage_end='9998-12-31',
        verified_through='1900-01-01',verified_open_dates_sha256=digest(encode(['1900-01-01'])))
    checks=[]
    def check():
        checks.append(True)
        assert len(checks)<16
    assert feed.observation_day(wide,DAY,'2026-11-01',check=check)==DAY
    rows,_=official_calendar(calendar())
    assert [row['date'] for row in rows if row['is_open']]==[
        '2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30','2026-11-02','2026-11-03']


def test_long_calendar_verification_obeys_original_cancellation():
    wide=calendar();wide.update(coverage_start='1900-01-01',coverage_end='9998-12-31',
        verified_through='9998-12-31',verified_open_dates_sha256='0'*64)
    checks=[]
    def stop():
        checks.append(True)
        if len(checks)==6:raise SourceFailure('collection_stopped')
    with pytest.raises(SourceFailure,match='collection_stopped'):
        feed.observation_day(wide,DAY,'2026-11-01',check=stop)
    assert len(checks)==6


@pytest.mark.parametrize('where',['marker','control'])
def test_publisher_and_cli_reject_mutable_control_input_without_changing_bytes(tmp_path,capsys,where):
    root,source,_,reader=setup(tmp_path)
    location=root/DAY if where=='marker' else root/'.publisher'
    fixed,_=inputs(location)
    path=Path(fixed['input_manifest'])
    if where=='marker':
        target=location/'CURRENT.json';path.rename(target);fixed['input_manifest']=str(target);path=target
    original=path.read_bytes()
    with pytest.raises(SourceFailure,match='t2108_ready_path'):publish(root,fixed,reader)
    assert path.read_bytes()==original
    feed_source={key:value for key,value in source.items() if key not in ('input_manifest','input_sha256')}
    feed_source['input_directory']=str(root)
    configuration=config(feed_source);configuration['models']['calendars']={'cn':calendar()}
    settings=tmp_path/'sources.json';settings.write_bytes(encode(configuration))
    assert publish_main(['--root',str(tmp_path/'objects'),'--config',str(settings),'--config-sha256',digest(settings.read_bytes()),
        '--source-id',feed_source['id'],'--input-manifest',str(path),'--input-sha256',fixed['input_sha256'],
        '--as-of','2026-11-01'])==1
    assert json.loads(capsys.readouterr().out)['error_code']=='t2108_ready_path'
    assert path.read_bytes()==original


@pytest.mark.parametrize('where',['day','publisher'])
def test_real_control_junction_never_writes_into_sealed_packet(tmp_path,capsys,where):
    root,source,_,reader=setup(tmp_path)
    packet=Path(source['input_manifest']).parent
    if where=='day':
        current=packet/'CURRENT.json';Path(source['input_manifest']).rename(current)
        source['input_manifest']=str(current)
    before={path.name:path.read_bytes() for path in packet.iterdir() if path.is_file()}
    alias=root/(DAY if where=='day' else '.publisher')
    assert packet.resolve().is_relative_to(tmp_path.resolve())
    assert alias.parent.resolve().is_relative_to(tmp_path.resolve())
    if os.name=='nt':
        subprocess.run(['cmd','/c','mklink','/J',str(alias),str(packet)],check=True,capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
    else:alias.symlink_to(packet,target_is_directory=True)
    # 控制目录解析到封存版本时，原件校验/租约/写入前即拒绝；不以root内作为充分条件。
    with pytest.raises(SourceFailure,match='t2108_ready_path'):publish(root,source,reader)
    assert {path.name:path.read_bytes() for path in packet.iterdir() if path.is_file()}==before
    if where=='day':assert not (root/'.publisher').exists()
    feed_source={key:value for key,value in source.items() if key not in ('input_manifest','input_sha256')}
    feed_source['input_directory']=str(root)
    configuration=config(feed_source);configuration['models']['calendars']={'cn':calendar()}
    settings=tmp_path/'sources.json';settings.write_bytes(encode(configuration))
    assert publish_main(['--root',str(tmp_path/'objects'),'--config',str(settings),'--config-sha256',digest(settings.read_bytes()),
        '--source-id',feed_source['id'],'--input-manifest',source['input_manifest'],'--input-sha256',source['input_sha256'],
        '--as-of','2026-11-01'])==1
    assert json.loads(capsys.readouterr().out)['error_code']=='t2108_ready_path'
    assert {path.name:path.read_bytes() for path in packet.iterdir() if path.is_file()}==before


@pytest.mark.parametrize('case',['both','relative','calendar_missing','other_kind'])
def test_feed_configuration_contract(tmp_path,case):
    root,fixed,_,_=setup(tmp_path)
    source={key:value for key,value in fixed.items() if key not in ('input_manifest','input_sha256')}
    source['input_directory']=str(root)
    value=config(source);value['models']['calendars']={'cn':calendar()}
    if case=='both':source.update(input_manifest=fixed['input_manifest'],input_sha256=fixed['input_sha256'])
    if case=='relative':source['input_directory']='relative'
    if case=='calendar_missing':value['models']={}
    if case=='other_kind':source.update(kind='disclosure',url='https://www.baostock.com/')
    with pytest.raises(ObservationError):validate_configuration(value)
