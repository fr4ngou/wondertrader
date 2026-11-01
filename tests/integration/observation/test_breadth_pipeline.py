"""股票原字符串→唯一计算/快照→HTTP；供应商协议替身与实际来源资格分开。"""
from datetime import datetime,timezone
from time import monotonic

from fastapi.testclient import TestClient
import pytest

from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from guanheng_app.observation.breadth_archive import derive_archive
from guanheng_app.observation.breadth_models import METRICS as ALL_METRICS
METRICS={key:value for key,value in ALL_METRICS.items() if key.endswith('.shsz')}
from guanheng_app.observation.collection import refresh
from guanheng_app.observation.collection_config import validate_configuration
from guanheng_app.observation.contracts import ObservationError,SeriesQuery
from guanheng_app.observation.metadata import asset_contract
from guanheng_app.observation.publication import adopt_snapshot
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure
from guanheng_app.observation.stock_partitions import extend_daily_partitions
from guanheng_app.observation.storage import digest,encode

DAY='2026-10-29'
FIELDS=['date','code','close','preclose','volume','turn','tradestatus','pbMRQ','peTTM']
ROWS=[[DAY,'sh.600001','11','10','100','5','1','2','10'],
      [DAY,'sh.600002','12','10','300','5.0001','1','2','10'],
      [DAY,'sz.000001','8','10','400','10','1','2','10'],
      [DAY,'sz.000002','10','10','10','0','1','2','10'],
      [DAY,'sz.000003','','','0','','0','2','10']]
BASIC_FIELDS=['code','type','ipoDate','outDate']
BASIC=[[row[1],'1','2020-01-01',''] for row in ROWS]


def empty():
    return dict(schema_version='market-observation/1',published_at=datetime.now(timezone.utc).isoformat(),
                boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})


def publish(reader,manifest):
    identity=digest(encode(manifest))
    adopt_snapshot(reader,manifest,identity,reader.repository.current(),monotonic()+10)
    return identity


def reader_at(path):
    reader=build_reader(path);reader.repository.initialize()
    return reader


def archived(path,ambiguous=False):
    reader=reader_at(path);manifest=empty();manifest['stock_pb_partitions']=dict(partitions={},rows=0)
    basic=reader.objects.put(encode(dict(fields=BASIC_FIELDS,rows=BASIC)))
    day=reader.objects.put(encode(dict(fields=FIELDS,rows=ROWS)))
    records=[dict(kind='stock_basic',sha256=basic,retrieved_at='2026-10-29T08:01:00+00:00'),
             dict(kind='stock_daily_batch',sha256=day,retrieved_at='2026-10-29T08:02:00+00:00')]
    extend_daily_partitions(reader.objects,manifest,records)
    variants=[records]
    if ambiguous:
        changed=reader.objects.put(encode(dict(fields=BASIC_FIELDS,rows=BASIC+[['sh.600003','1','2020-01-01','']])))
        variants.append([dict(kind='stock_basic',sha256=changed),dict(kind='stock_daily_batch',sha256=day)])
    for index,record in enumerate(variants):
        capture=reader.objects.put(encode(record));identity='capture-'+str(index)
        for item in record:
            identity='capture-'+str(index)+'-'+item['kind']
            manifest['assets'][identity]=asset_contract(dict(asset_id=identity,sha256=item['sha256'],
                bytes=len(reader.objects.get(item['sha256'])),group='source.capture',capture_id=capture,
                source_ref='fixture.baostock',ingested_at='2026-10-29T08:03:00+00:00'),
                source=dict(id='fixture.baostock'),record=item)
    return reader,publish(reader,manifest)


def configuration(metrics=True):
    source=dict(id='fixture.baostock',kind='baostock',minimum_universe=1,overlap_days=0,
        datasets=['pb_shsz_daily',*(METRICS if metrics else [])],
        tables=['source.cn_calendar',*(['source.shsz_universe'] if metrics else [])])
    return dict(schema_version='guanheng.observation-sources.v1',timeout_seconds=15,max_days_per_batch=31,
        allowed_hosts=['www.baostock.com'],models={},schedule=dict(timezone='Asia/Shanghai',times=['09:00'],poll_seconds=5),
        retry_seconds=60,max_window_attempts=2,
        budget=dict(seconds=30,max_requests=32,max_bytes=16777216,response_bytes=4194304),sources=[source])


class RecordedFetcher:
    def __init__(self,objects,hosts,*,timeout,budget):
        self.objects,self.timeout,self.budget,self.records=objects,timeout,budget,[]
    def close(self):pass


class RecordedClient:
    failed=False
    def __init__(self,fetch,timeout):self.fetch=fetch
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def table(self,kind,start=None,end=None):
        self.fetch.budget.request('sdk')
        if kind=='stock_basic':fields,rows=BASIC_FIELDS,BASIC
        elif kind=='calendar':fields,rows=['calendar_date','is_trading_day'],[[DAY,'1']]
        else:
            if self.failed:raise SourceFailure('fixture_source_failed')
            fields,rows=FIELDS,ROWS
        self.fetch.records.append(dict(kind=kind if kind!='calendar' else 'provider_protocol',
            sha256=self.fetch.objects.put(encode(dict(fields=fields,rows=rows)))))
        return fields,rows


def test_recorded_provider_first_publish_actual_http_and_legacy_mode(tmp_path,monkeypatch):
    from guanheng_app.observation import providers
    monkeypatch.setattr(providers,'BaostockClient',RecordedClient)
    reader=reader_at(tmp_path);publish(reader,empty())
    config=configuration();validate_configuration(config)
    result=refresh(reader,config,as_of=DAY,deadline=monotonic()+15,fetcher_factory=RecordedFetcher)
    assert result['status']=='success' and result['sdk_requests']==3
    catalog=reader.catalog();assert {row['id'] for row in catalog['datasets']}==set(METRICS)|{'msi.shsz','breadth.thrust.shsz'}
    app=create_app(ConsoleSettings(observation_root=str(tmp_path)))
    with TestClient(app) as client:
        page=client.get('/v1/ui/market-observation/series',params=dict(metric_id='turnover.gt5.shsz')).json()
        assert page['rows'][0]['turnover_gt5_pct']==40
        assert page['rows'][0]['turnover_gt5_count']==2
        assert page['definition']['universe_version']==reader.snapshot()[1]['source_tables']['source.shsz_universe']
    assert app.state.shutdown_complete and app.state.reader.live_threads==0
    legacy=RecordedFetcher(reader.objects,[],timeout=15,budget=CollectionBudget(monotonic()+10))
    assert set(providers.baostock_daily(legacy,configuration(False)['sources'][0],DAY,DAY))=={'pb_shsz_daily','source.cn_calendar'}


def test_source_failure_keeps_catalog_and_definitions_unpublished(tmp_path,monkeypatch):
    from guanheng_app.observation import providers
    class Failed(RecordedClient):failed=True
    monkeypatch.setattr(providers,'BaostockClient',Failed)
    reader=reader_at(tmp_path);before=publish(reader,empty())
    result=refresh(reader,configuration(),as_of=DAY,deadline=monotonic()+10,fetcher_factory=RecordedFetcher)
    assert result['status']=='failed' and reader.repository.current()==before
    assert reader.catalog()['datasets']==[]


def test_archive_uses_original_strings_and_cas(tmp_path):
    source,snapshot=archived(tmp_path/'source');target=reader_at(tmp_path/'target')
    result=derive_archive(source,target,snapshot,DAY,DAY,None,monotonic()+10)
    assert result['datasets']==4 and result['rows']==4
    from guanheng_app.observation.metadata import computation_identity
    assert target.snapshot()[1]['computation_identity']==computation_identity()
    row=next(target.all_rows(SeriesQuery(metric_id='trin.shsz')))
    assert row['trin']==2 and row['advancing_count']==2 and row['declining_count']==1
    before=target.repository.current()
    with pytest.raises(ObservationError) as error:
        derive_archive(source,target,snapshot,DAY,DAY,None,monotonic()+10)
    assert error.value.code=='publication_conflict' and target.repository.current()==before


def test_archive_preserves_original_capture_times_across_roots_and_http(tmp_path):
    source,snapshot=archived(tmp_path/'source');target=reader_at(tmp_path/'target')
    derive_archive(source,target,snapshot,DAY,DAY,None,monotonic()+10)
    original=source.snapshot(snapshot)[1];adopted=target.snapshot()[1]
    for key,asset in original['assets'].items():
        if asset.get('group')!='source.capture':continue
        assert adopted['assets'][key]==asset
        assert target.objects.get(asset['capture_id'])==source.objects.get(asset['capture_id'])
        assert asset['capture_id'] in adopted['datasets']['trin.shsz']['parents']
    app=create_app(ConsoleSettings(observation_root=str(tmp_path/'target')))
    with TestClient(app) as client:
        response=client.get('/v1/market-observation/lineage/capture-0-stock_daily_batch')
        assert response.status_code==200
        provenance=response.json()
        assert provenance['retrieved_at']=='2026-10-29T08:02:00+00:00'
        assert provenance['ingested_at']=='2026-10-29T08:03:00+00:00'
        assert provenance['available_at'] is None
    assert app.state.shutdown_complete and app.state.reader.live_threads==0


def test_ambiguous_universe_and_expired_deadline_preserve_target(tmp_path):
    source,snapshot=archived(tmp_path/'source',True);target=reader_at(tmp_path/'target')
    with pytest.raises(ObservationError) as error:
        derive_archive(source,target,snapshot,DAY,DAY,None,monotonic()+10)
    assert error.value.code=='stock_universe_ambiguous' and target.repository.current() is None
    with pytest.raises(ObservationError) as error:
        derive_archive(source,target,snapshot,DAY,DAY,None,monotonic()-1)
    assert error.value.code=='observation_timeout' and target.repository.current() is None


def test_new_metrics_require_universe_and_calendar_registration():
    config=configuration();config['sources'][0]['tables'].remove('source.shsz_universe')
    with pytest.raises(ObservationError):validate_configuration(config)


def test_spread_model_updates_only_registered_outputs():
    from guanheng_app.observation.refresh_models import spread_and_bond
    inputs={'source.gov10y':[dict(date=DAY,gov10y_pct=2)],
            'source.shenwan':[dict(date=DAY,pe=20,weighted_pb=1.5,reference=3000)]}
    breadth={'breadth.shsz':[]}
    spread_and_bond(inputs,breadth,{})
    assert breadth=={'breadth.shsz':[]}
    requested={'spread_sw':[],'pb_sw_daily':[]}
    spread_and_bond(inputs,requested,{})
    assert requested['spread_sw'][0]['spread']==3
    assert requested['pb_sw_daily'][0]['weighted_pb']==1.5
    assert 'bond.erp_rank756' not in requested


@pytest.mark.parametrize('first,last,code', [
    ('', '', 'stock_listing_date_unknown'),
    ('2020-02-30', '', 'stock_listing_dates_invalid'),
    ('20200101', '', 'stock_listing_dates_invalid'),
    ('2020-01-01', '2019-12-31', 'stock_listing_dates_invalid'),
])
def test_unknown_or_bad_listing_dates_keep_online_and_archive_heads(tmp_path, monkeypatch, first, last, code):
    from guanheng_app.observation import providers
    changed = [list(row) for row in BASIC]
    changed[0][2:4] = [first, last]
    monkeypatch.setitem(globals(), 'BASIC', changed)
    monkeypatch.setattr(providers, 'BaostockClient', RecordedClient)
    online = reader_at(tmp_path/'online'); before = publish(online, empty())
    result = refresh(online, configuration(), as_of=DAY, deadline=monotonic()+10,
                     fetcher_factory=RecordedFetcher)
    assert result['status'] == 'failed' and online.repository.current() == before
    assert result['sources'][0]['error_code'] == code
    source, snapshot = archived(tmp_path/'source'); target = reader_at(tmp_path/'target')
    with pytest.raises(ObservationError) as error:
        derive_archive(source, target, snapshot, DAY, DAY, None, monotonic()+10)
    assert error.value.code == code and target.repository.current() is None


def test_listing_and_delisting_boundaries_agree_online_and_archive(tmp_path, monkeypatch):
    from guanheng_app.observation import providers
    changed = [list(row) for row in BASIC]
    changed[0][2] = DAY
    changed[1][2] = '2026-10-30'
    changed[2][3] = DAY
    changed[3][3] = '2026-10-30'
    monkeypatch.setitem(globals(), 'BASIC', changed)
    monkeypatch.setattr(providers, 'BaostockClient', RecordedClient)
    online = reader_at(tmp_path/'online'); publish(online, empty())
    result = refresh(online, configuration(), as_of=DAY, deadline=monotonic()+10,
                     fetcher_factory=RecordedFetcher)
    assert result['status'] == 'success'
    source, snapshot = archived(tmp_path/'source'); target = reader_at(tmp_path/'target')
    derive_archive(source, target, snapshot, DAY, DAY, None, monotonic()+10)
    for metric in METRICS:
        rows = list(online.all_rows(SeriesQuery(metric_id=metric)))
        assert rows == list(target.all_rows(SeriesQuery(metric_id=metric)))
        assert rows[0]['market_count'] == 3
    assert list(online.all_rows(SeriesQuery(metric_id='breadth.shsz')))[0]['advancing_pct'] == 50
