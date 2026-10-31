"""完整准入的重复正文IO及截止后回执丢失，沿实际refresh/采用调用链回归。"""
import copy
from types import SimpleNamespace
from time import monotonic, sleep
import pytest
from test_observation import admitted
from guanheng_app.observation import collection, publication, source_fetch, storage
from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.query import ObservationReader


def test_domain_reads_and_integrity_share_one_validation_pass(admitted, monkeypatch):
    reader, manifest, _ = admitted
    partition = manifest['datasets']['spread.test']['partition']
    size = len(reader.objects.get(partition))
    reader.cache.clear()
    clock = [0]
    calls = []
    original = reader.objects.get
    def metered(sha):
        body = original(sha)
        clock[0] += len(body)
        calls.append(sha)
        return body
    monkeypatch.setattr(reader.objects, 'get', metered)
    monkeypatch.setattr(publication, 'monotonic', lambda: clock[0])
    # 以实际读取字节模拟受限磁盘；原两遍读取在第二遍耗尽同一预算。
    result = publication.validate_manifest(reader, manifest, size * 1.1)
    assert result['rows'] == 6 and result['verified_objects'] == 1
    assert calls == [partition]


def test_cached_query_rows_do_not_hide_later_object_corruption(admitted):
    reader, manifest, _ = admitted
    partition = manifest['datasets']['spread.test']['partition']
    assert len(reader.rows(partition)) == 6
    reader.objects.path(partition).write_bytes(b'corrupted after query')
    with pytest.raises(ObservationError) as caught:
        publication.validate_manifest(reader, manifest, monotonic() + 3)
    assert caught.value.code == 'corrupt_object'


def test_unreferenced_registered_parent_is_still_verified(admitted):
    reader, manifest, _ = admitted
    candidate = copy.deepcopy(manifest)
    parent = reader.objects.put(b'raw parent')
    candidate['datasets']['spread.test']['parents'] = [parent]
    reader.objects.path(parent).write_bytes(b'bad parent')
    with pytest.raises(ObservationError) as caught:
        publication.validate_manifest(reader, candidate, monotonic() + 3)
    assert caught.value.code == 'corrupt_object'


def test_expired_validation_keeps_failure_receipt_and_old_current(admitted, monkeypatch):
    reader, _, previous = admitted
    class Fetch:
        def __init__(self, *args, **kwargs):self.records=[]
        def close(self):pass
    monkeypatch.setitem(collection.PARSERS, 'fixture', lambda *args: {'spread.test': []})
    def expire(reader, manifest, deadline):
        sleep(max(0, deadline - monotonic()) + .002)
        raise ObservationError('observation_timeout', '观察校验超时', 503)
    monkeypatch.setattr(collection, 'validate_manifest', expire)
    config=dict(timeout_seconds=1,allowed_hosts=[],max_days_per_batch=2,models={},
        sources=[dict(id='fixture',kind='fixture',datasets=['spread.test'])],
        budget=dict(seconds=2,max_requests=2,max_bytes=1024,response_bytes=1024))
    result=collection.refresh(reader,config,as_of='2026-10-31',deadline=monotonic()+2,fetcher_factory=Fetch)
    assert result['sources'][0]['status']=='no_new_observations', result
    assert result['status']=='failed' and result['current_snapshot']==previous
    assert reader.repository.current()==previous
    assert 'receipt_error_code' not in result
    receipt=reader.repository.runs()[0]
    assert receipt['error_code']=='observation_timeout'
    assert len(receipt['sources'])==1 and receipt['sources'][0]['status']=='no_new_observations'


def test_expired_preparation_keeps_failure_receipt_without_source_calls(admitted, monkeypatch):
    reader, _, previous = admitted
    original = ObservationReader.rows
    source_calls = []
    clock=[monotonic()]
    deadline=clock[0]+2
    monkeypatch.setattr(source_fetch,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    monkeypatch.setattr(collection,'monotonic',lambda:clock[0])
    monkeypatch.setattr(storage,'monotonic',lambda:clock[0])
    def delayed(self, partition):
        # 原D前10ms、工作D后：精确复现有收尾时间却尚无run的窗口。
        clock[0]=deadline-.01
        return original(self, partition)
    monkeypatch.setattr(ObservationReader, 'rows', delayed)
    config=dict(timeout_seconds=1,allowed_hosts=[],max_days_per_batch=2,models={},
        sources=[dict(id='fixture',kind='fixture',datasets=['spread.test'])],
        budget=dict(seconds=2,max_requests=2,max_bytes=1024,response_bytes=1024))
    result=collection.refresh(reader,config,as_of='2026-10-31',deadline=deadline,
        fetcher_factory=lambda *args,**kwargs:source_calls.append(1))
    assert result['status']=='failed' and result['error_code']=='collection_timeout'
    assert 'receipt_error_code' not in result and not source_calls
    assert reader.repository.current()==previous
    receipt=reader.repository.runs()[0]
    assert receipt['error_code']=='collection_timeout' and receipt['sources']==[]
