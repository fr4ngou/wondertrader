"""同名源表/投影归属及中证全指真实收盘缺口的根因回归。"""
import copy
from time import monotonic
from types import SimpleNamespace
import pytest
from test_observation import admitted
from guanheng_app.observation import collection
from guanheng_app.observation.publication import adopt_snapshot
from guanheng_app.observation.query import parquet_bytes
from guanheng_app.observation.storage import digest, encode
from guanheng_app.observation.source_fetch import SourceFailure
from guanheng_app.observation.wondertrader_source import history, prepare_table


def test_declared_source_table_keeps_ownership_when_projection_has_same_id(admitted, monkeypatch):
    reader, original, version=admitted
    manifest=copy.deepcopy(original)
    manifest['source_tables']={'spread.test':reader.objects.put(parquet_bytes([dict(date='2026-10-01',close=10.)]))}
    identity=digest(encode(manifest))
    adopt_snapshot(reader,manifest,identity,version,monotonic()+30)
    class Fetch:
        def __init__(self,*args,**kwargs):self.records=[]
        def close(self):pass
    monkeypatch.setitem(collection.PARSERS,'fixture',lambda *args:{'spread.test':[dict(date='2026-10-01',close=11.)]})
    config=dict(timeout_seconds=1,allowed_hosts=[],max_days_per_batch=2,models={},
        sources=[dict(id='fixture',kind='fixture',tables=['spread.test'],replace_tables=True)],
        budget=dict(seconds=30,max_requests=2,max_bytes=1024*1024,response_bytes=1024*1024))
    run=collection.refresh(reader,config,as_of='2026-10-02',deadline=monotonic()+30,fetcher_factory=Fetch)
    assert run['status']=='success',run
    current=reader.repository.get(run['current_snapshot'])
    assert reader.rows(current['source_tables']['spread.test'])==[dict(date='2026-10-01',close=11.)]
    assert current['datasets']['spread.test']['partition']==original['datasets']['spread.test']['partition']


def test_close_reference_retains_real_old_date_and_accepts_current_revision():
    old=[dict(date='2018-06-18',close=4380.58,available_at=None),dict(date='2026-11-02',close=6000.,available_at=None)]
    new=[dict(date='2026-11-02',close=6001.,available_at=None)]
    rows,revisions,retained=prepare_table('source.csi_all',old,new,'2026-11-02')
    assert rows==[old[0],new[0]] and retained==['2018-06-18']
    assert revisions==[dict(date='2026-11-02',fields=['close'])]
    assert old[1]['close']==6000.


def test_ohlc_volume_table_still_requires_complete_old_coverage():
    with pytest.raises(SourceFailure) as caught:
        prepare_table('market.sh000001',[dict(date='2018-06-18',close=1.)],[dict(date='2026-11-02',close=2.)],'2026-11-02')
    assert caught.value.code=='market_existing_coverage_missing'


def test_close_reference_ignores_unused_ohlc_and_volume_unit():
    # 收盘消费不要求OHLC或量，原值0/缺失不被改造成有效日K或已核量额。
    response=dict(status=dict(code='Ok'),data=dict(metadata=dict(volume_unit='unused'),bars=[dict(date=20261102,close=6001.)]))
    fetch=SimpleNamespace(timeout=1,records=[],objects=SimpleNamespace(put=lambda raw:digest(raw)),
        budget=SimpleNamespace(request=lambda:None,consume=lambda size:None,remaining=lambda:1))
    rows=history(fetch,dict(symbols=['sh000985']),'2026-11-02','2026-11-02',lambda seconds:SimpleNamespace(source_daily_history_query=lambda request:response))
    assert rows=={'source.csi_all':[dict(date='2026-11-02',close=6001.,available_at=None)]}
