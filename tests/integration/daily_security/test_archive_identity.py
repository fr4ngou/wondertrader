"""同一原Reader选源才复用核读事实；不连接Source，Native Codec另有普通包主链。"""
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from copy import deepcopy
from time import monotonic
from types import SimpleNamespace

import pytest

from integrations.guanheng.daily_overlay import DailyOverlayMarket
from integrations.guanheng.market_snapshot import SnapshotSourceMarket
from integrations.guanheng.source_archive_identity import archive_entry_identity,PreloadedArchiveRows
from integrations.guanheng import daily_archive_merge as merge
from integrations.guanheng.daily_archive_prepare import price_rows_identity
from integrations.guanheng.analysis_price_capture import capture_metadata
from integrations.guanheng.market_generation import encode


def digest(raw):return hashlib.sha256(raw).hexdigest()


def fixture(tmp_path,basis="none",name="old"):
    metadata=capture_metadata(dict(source_kind="actual-qmt",request=dict(
        capture_id="00000000-0000-4000-8000-000000000001")),"a"*64,basis)
    file=tmp_path/(name+".dsb");file.write_bytes(("synthetic "+name+" file").encode())
    entry=dict(symbol="SSE.510300",path=file.name,sha256=digest(file.read_bytes()),rows=1,
        first=20261105,last=20261105,provenance=[dict(offset=0,count=1,metadata=metadata)])
    path=tmp_path/(name+".json");path.write_bytes(encode(dict(entries=[entry])))
    descriptor=dict(path=str(path),sha256=digest(path.read_bytes()))
    return descriptor,entry,metadata


def layer(descriptor,entry,base=None,shape="segments"):
    """只替代Native构造边界，调用真正首层选源实现。"""
    value=object.__new__(DailyOverlayMarket);value._owner=threading.get_ident();value._closed=False
    value._shape=shape;value._archive_descriptor=descriptor
    value._entries={(entry["symbol"],entry["provenance"][0]["metadata"]["adjustment"]):entry}
    value._base=base
    return value


def test_source_owner_retains_first_matching_layer_and_projection_boundary(tmp_path):
    old,e,_=fixture(tmp_path,name="old")
    new,n,_=fixture(tmp_path,name="new")
    base=layer(old,e);top=layer(new,n,base)
    assert top.static_archive_identity("SSE.510300","none")==archive_entry_identity(new,n)
    assert top.static_archive_identity("SSE.510300","front_ratio") is None
    top._shape="dataset"
    assert top.static_archive_identity("SSE.510300","none") is None  # 不越过不可复用首层取旧来源。
    top._closed=True
    with pytest.raises(ValueError):top.static_archive_identity("SSE.510300","none")


def test_fixed_snapshot_delegates_only_its_admitted_identity(tmp_path):
    desc,entry,_=fixture(tmp_path)
    market=object.__new__(SnapshotSourceMarket)
    market._owner=threading.get_ident();market._closed=False;market._snapshot_ids={"a"*64};market._base=layer(desc,entry)
    assert market.static_archive_identity("SSE.510300","none",snapshot_id="a"*64)==archive_entry_identity(desc,entry)
    assert market.static_archive_identity("SSE.510300","none",snapshot_id="b"*64) is None


@pytest.mark.parametrize("new_first_layer",[False,True])
def test_raw_cache_avoids_same_native_decode_and_preserves_new_stock_priority(tmp_path,monkeypatch,new_first_layer):
    desc,entry,meta=fixture(tmp_path)
    identity=archive_entry_identity(desc,entry)
    row=lambda value:dict(date=20261105,open=value,high=value,low=value,close=value,volume=3.,amount=10.)
    old=row(1.);preload=PreloadedArchiveRows(identity,{20261105:(old,meta)},price_rows_identity([old]),tuple(entry["provenance"]))
    selected=identity
    if new_first_layer:
        new,n,_=fixture(tmp_path,name="new");selected=archive_entry_identity(new,n)
    calls=[]
    class Market:
        def static_archive_identity(self,*args,**kwargs):return selected
        def call(self,request):
            calls.append(request)
            assert new_first_layer,"identical already decoded archive must not read again"
            return dict(status=dict(code="Ok"),data=dict(metadata=meta,bars=[row(9.)],
                archive=dict(first_date=20261105,last_date=20261105,count=1)))
    seen={}
    def prepare(rows,metadata,*args,**kwargs):seen.update(rows);return {"completed":True}
    monkeypatch.setattr(merge,"prepare_daily_archive",prepare)
    addition=dict(row(2.),date=20261106)
    merge.merge_original_price_rows(Market(),{"SSE.510300":[addition]},meta,tmp_path/"out","helper","b"*64,
        deadline=__import__("time").monotonic()+5,retain_unchanged=True,
        preloaded_previous_rows={"SSE.510300":preload})
    assert seen["SSE.510300"][0]["close"]==(9. if new_first_layer else 1.)
    assert seen["SSE.510300"][-1]["date"]==20261106
    assert len(calls)==(1 if new_first_layer else 0)


@pytest.mark.parametrize("damage",["file","metadata","range"])
def test_cached_proof_damage_rejected_before_publish(tmp_path,monkeypatch,damage):
    desc,entry,meta=fixture(tmp_path);identity=archive_entry_identity(desc,entry)
    row=dict(date=20261105,open=1.,high=1.,low=1.,close=1.,volume=3.,amount=10.)
    rows={20261105:(row,deepcopy(meta))}
    if damage=="metadata":rows[20261105][1]["price_unit"]="CNY"
    if damage=="range":rows={20261104:(dict(row,date=20261104),meta)}
    prior=PreloadedArchiveRows(identity,rows,price_rows_identity([r for _,(r,_)in sorted(rows.items())]),tuple(entry["provenance"]))
    if damage=="file":Path(identity.path).write_bytes(b"changed")
    class Market:
        def static_archive_identity(self,*args,**kw):return identity
        def call(self,*args):raise AssertionError("damaged proof is not normal fallback")
    monkeypatch.setattr(merge,"prepare_daily_archive",lambda *a,**kw:pytest.fail("damaged proof published"))
    with pytest.raises(ValueError):
        merge.merge_original_price_rows(Market(),{"SSE.510300":[]},meta,tmp_path/"out","helper","b"*64,
            deadline=__import__("time").monotonic()+5,retain_unchanged=True,preloaded_previous_rows={"SSE.510300":prior})


@pytest.mark.parametrize("basis",["none","front_ratio"])
def test_same_count_different_first_file_is_not_equal_source(tmp_path,basis):
    a,x,_=fixture(tmp_path,basis,name="old")
    b,y,_=fixture(tmp_path,basis,name="new")
    assert archive_entry_identity(a,x)!=layer(b,y,layer(a,x)).static_archive_identity("SSE.510300",basis)


def test_front_same_count_new_first_layer_uses_current_rows_without_old_file_hint(tmp_path,monkeypatch):
    from integrations.guanheng import daily_front_archive as front
    old,entry,_=fixture(tmp_path,'front_ratio',name='old')
    new,other,meta=fixture(tmp_path,'front_ratio',name='new')
    current=layer(new,other,layer(old,entry))
    inputs=tmp_path/'inputs.json';inputs.write_bytes(encode(dict(cache=dict(directory='unused',sha256='a'*64))))
    descriptor=dict(path=str(inputs),sha256=digest(inputs.read_bytes()))
    monkeypatch.setattr(front,'load_price_capture',lambda d:{})
    monkeypatch.setattr(front,'capture_metadata',lambda *a,**kw:meta)
    monkeypatch.setattr(front,'price_batches',lambda *a,**kw:iter([]))
    row=dict(date=20261105,open=9.,high=9.,low=9.,close=9.,volume=3.,amount=10.)
    monkeypatch.setattr(front,'read_price_history',lambda *a,**kw:{20261105:(row,meta)})
    seen={}
    def prepare(rows,metadata,out,*a,**kw):
        seen.update(rows=rows,hints=kw['reusable_files']);out.mkdir(parents=True)
        path=out/'archive.json';path.write_bytes(encode(dict(entries=[])))
        return dict(path=str(path),sha256=digest(path.read_bytes()))
    monkeypatch.setattr(front,'prepare_daily_archive',prepare)
    front.prepare_front_archive(descriptor,current,[old],tmp_path/'front',dict(path='helper',sha256='b'*64),
        deadline=__import__('time').monotonic()+5,maximum_history_rows=10000,cancelled=lambda:False)
    assert seen['rows']['SSE.510300'][0]['close']==9.
    assert seen['hints']=={}  # 同条数不授旧DSB复用；正常Helper编码当前9元数据。


@pytest.mark.parametrize('mismatch', [None, 'amount', 'close', 'provider', 'known-unit'])
def test_same_date_qmt_unit_proof_survives_compaction(tmp_path,monkeypatch,mismatch):
    _,_,old=fixture(tmp_path)
    prior=dict(old,dataset_version='qmt.batch-native-day.v2:qmt-contextinfo-day-etf-index.v1:'+'c'*64,
               price_unit='CNY',volume_unit='lot')
    row=dict(date=20261105,open=1.,high=1.,low=1.,close=1.,volume=3.,amount=10.)
    candidate=dict(row)
    if mismatch=='amount':candidate['amount']=11.
    if mismatch=='close':candidate.update(close=2.,high=2.)
    if mismatch=='provider':old=dict(old,source=dict(old['source'],provider='SSE'))
    if mismatch=='known-unit':old=dict(old,volume_unit='share')
    monkeypatch.setattr(merge,'read_price_history',lambda *a,**kw:{row['date']:(row,old)})
    def archive(rows,metadata,*args,provenance,**kwargs):
        assert rows['SSE.510300']==[row]
        actual=provenance['SSE.510300'][0]['metadata']
        assert actual==(prior if mismatch is None else old)
        return {'completed':True}
    monkeypatch.setattr(merge,'prepare_daily_archive',archive)
    merge.merge_original_price_rows(object(),{'SSE.510300':[candidate]},prior,tmp_path/'out','helper','b'*64,
        deadline=__import__('time').monotonic()+5,retain_unchanged=True)


@pytest.mark.parametrize("different_value", [False, True])
def test_raw_archive_keeps_same_value_unit_upgrade_after_loading_old_archive(tmp_path, monkeypatch, different_value):
    from integrations.guanheng import daily_price_archive as raw

    descriptor, entry, old = fixture(tmp_path)
    archive = Path(descriptor["path"])
    archive.write_bytes(encode(dict(schema="guanheng.daily-native-archive.v1", entries=[entry])))
    descriptor["sha256"] = digest(archive.read_bytes())
    symbol = entry["symbol"]
    market = layer(descriptor, entry)
    row = dict(date=20261105, open=2., high=2., low=2., close=2., volume=3., amount=6.)
    bar = SimpleNamespace(occurred_at=datetime(2026, 11, 5),
                          **{key: value for key, value in row.items() if key != "date"})

    class Reader:
        def __init__(self, *args, **kwargs):
            pass

        def read_source_file(self, *args):
            return SimpleNamespace(bars=[bar])

        def close(self):
            pass

    proven = dict(old, dataset_version="qmt.batch-native-day.v2:qmt-contextinfo-day-etf-index.v1:" + "c"*64,
                  price_unit="CNY", volume_unit="lot")
    captured = {key: value for key, value in row.items() if key != "date"}
    if different_value:
        captured["amount"] = 7.
    cache = dict(directory="cache", sha256="b"*64)
    inputs = tmp_path/"inputs.json"
    inputs.write_bytes(encode(dict(schema="guanheng.daily-price-input-result.v1", cache=cache)))
    fixed_inputs = dict(path=str(inputs), sha256=digest(inputs.read_bytes()))
    monkeypatch.setattr(raw, "NativeHistory", Reader)
    monkeypatch.setattr(raw, "source_file_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(raw, "load_price_capture", lambda _: {})
    monkeypatch.setattr(raw, "price_batches", lambda *args, **kwargs: iter(
        [(None, {"510300.SH": {"data": {"20261105": captured}}})]))
    monkeypatch.setattr(raw, "capture_metadata", lambda *args, **kwargs: proven if kwargs else old)

    def prepare(rows, metadata, *args, provenance, **kwargs):
        assert rows[symbol] == [row]
        selected = provenance[symbol][0]["metadata"]
        assert selected == (old if different_value else proven)
        return {"completed": True}

    monkeypatch.setattr(merge, "prepare_daily_archive", prepare)
    completed = raw.materialize_price_archive(fixed_inputs, market, [descriptor], tmp_path/"out",
        dict(path="helper", sha256="d"*64), dict(library="reader", sha256="e"*64),
        deadline=monotonic()+5, unit_evidence_by_capture={cache["sha256"]: object()})
    assert completed == {"completed": True}
