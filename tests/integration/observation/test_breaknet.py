"""破净口径、交易日预热、板块缓存与原归档合约回归。"""
from datetime import date, timedelta
import pytest
from pydantic import ValidationError

from guanheng_app.observation import breaknet
from guanheng_app.observation.contracts import SeriesQuery, ObservationError
from guanheng_app.observation.metadata import validate_fields


def test_stock_threshold_denominator_and_market_segments():
    fields = ['date','code','pbMRQ']
    rows = [["2026-11-20", code, pb] for code, pb in [
        ('sh.600000','0.8'),('sz.000001','1'),('sh.601000','-0.2'),('sh.603000',''),
        ('sz.300001','0.5'),('sz.301001','101'),('sz.302001','2'),('sh.688001','0.9'),
        ('sh.689009','0.2'),('sh.900001','0.3')]]
    raw = breaknet.stock_day(fields, rows, '2026-11-20')
    result = breaknet.project([raw], 'main,chinext')[0]
    assert (raw['main_universe'], raw['main_valid'], raw['main_broken']) == (4,2,1)
    assert (result['sample_count'], result['broken_count'], result['ratio']) == (5,2,40)
    assert result['missing_count'] == result['excluded_count'] == 1
    assert raw['star_broken'] == 1
    validate_fields(breaknet.definition(), [raw])
    validate_fields(breaknet.definition(), [result])
    with pytest.raises(ObservationError):
        breaknet.stock_day(fields, rows+rows[:1], '2026-11-20')
    with pytest.raises(ObservationError):
        breaknet.stock_day(fields, [['2026-11-20','sh.600000','nan']], '2026-11-20')


def test_five_actual_sessions_warmup_and_unknown_gap():
    dates = ['2026-11-13','2026-11-16','2026-11-17','2026-11-18','2026-11-19','2026-11-20','2026-11-23']
    rows = [dict(breaknet.empty_day(day), main_valid=100, main_universe=100, main_broken=i+10)
            for i, day in enumerate(dates)]
    result = breaknet.project(rows, 'main')
    assert all(r['change5'] is None for r in result[:5])
    assert result[5]['change5'] == pytest.approx(5)
    assert result[6]['change5'] == pytest.approx(5)
    rows[3]['main_valid'] = None
    result = breaknet.project(rows, 'main')
    assert result[3]['ratio'] is None
    assert result[5]['change5'] is result[6]['change5'] is None
    calendar = [dict(date=day,is_open=1) for day in dates]
    padded = breaknet.calendar_rows(rows[:3]+rows[4:], calendar)
    assert len(padded) == 7 and padded[3]['main_valid'] is None
    assert breaknet.project(padded,'main')[6]['change5'] is None


def test_query_normalizes_and_rejects_empty_duplicate_or_unknown_segments():
    assert SeriesQuery(metric_id=breaknet.METRIC).segments == 'main'
    assert SeriesQuery(metric_id=breaknet.METRIC,segments='star,main').segments == 'main,star'
    for value in ('', 'main,main', 'other', 'main,'):
        with pytest.raises(ValidationError):SeriesQuery(metric_id=breaknet.METRIC,segments=value)


def test_reader_cache_and_pagination_keep_selected_denominator_and_warmup(tmp_path):
    from guanheng_app.observation.runtime import build_reader
    from guanheng_app.observation.query import parquet_bytes
    reader = build_reader(str(tmp_path))
    rows = [dict(breaknet.empty_day((date(2026,11,1)+timedelta(days=i)).isoformat()),
                 main_valid=10,main_broken=2+i,main_universe=10,
                 star_valid=90,star_broken=1,star_universe=90) for i in range(6)]
    definition = breaknet.definition()
    item = dict(partition=reader.objects.put(parquet_bytes(rows)))
    main = reader.derived(item,definition,SeriesQuery(metric_id=breaknet.METRIC))
    combined = reader.derived(item,definition,SeriesQuery(metric_id=breaknet.METRIC,segments='main,star'))
    assert main[-1]['ratio'] == 70
    assert combined[-1]['ratio'] == 8
    assert combined[-1]['change5'] == 5
    assert reader.derived(item,definition,SeriesQuery(metric_id=breaknet.METRIC))[-1]['ratio'] == 70


def test_archive_and_daily_share_listing_dates_and_keep_gap_audit(tmp_path, monkeypatch):
    import json
    from contextlib import nullcontext
    from types import SimpleNamespace
    from time import monotonic
    from guanheng_app.observation import breaknet_archive
    from guanheng_app.observation.runtime import build_reader
    from guanheng_app.observation.query import parquet_bytes
    from guanheng_app.observation.stock_universe import shsz_listings, listed_codes
    reader = build_reader(str(tmp_path))
    basic_fields = ['code','type','ipoDate','outDate']
    basic_rows = [['sh.600000','1','2000-01-01',''],['sz.000001','1','2000-01-01',''],
                  ['sh.600001','1','2000-01-01','2026-11-19']]
    basic_sha = reader.objects.put(json.dumps(dict(fields=basic_fields,rows=basic_rows)).encode())
    fields = ['date','code','pbMRQ']
    rows = [['2026-11-20','sh.600000','2'],['2026-11-20','sh.600001','0.5'],['2026-11-20','sz.000001','2']]
    parts = {market: dict(market=market,sha256=reader.objects.put(parquet_bytes([
        dict(zip(fields,r)) for r in rows if r[1].startswith(market)]))) for market in ('sh','sz')}
    calendar_sha = reader.objects.put(parquet_bytes([dict(date='2026-11-20',is_open=1)]))
    parent = reader.objects.put(parquet_bytes([dict(date='2026-11-20',universe_count=3)]))
    manifest = dict(stock_pb_partitions=dict(partitions=parts),assets={'basic':dict(sha256=basic_sha)},
                    datasets={'pb_shsz_daily':dict(partition=parent)},
                    source_tables={'source.cn_official_calendar':calendar_sha},boards=[],preferences=dict(default_datasets={}))
    published = []
    reader.repository = SimpleNamespace(current=lambda:'fixed', collection_lease=lambda:nullcontext(True),
                                         publish=lambda m,*a,**k:published.append(m))
    reader.snapshot = lambda version:('fixed',manifest)
    monkeypatch.setattr(breaknet_archive,'validate_stock_partitions',lambda *a,**k:None)
    monkeypatch.setattr(breaknet_archive,'register_standard_assets',lambda *a:None)
    monkeypatch.setattr(breaknet_archive,'validate_manifest',lambda *a,**k:{})
    breaknet_archive.derive_archive(reader,'fixed',basic_sha,monotonic()+30)
    candidate = published[0]
    item = candidate['datasets'][breaknet.METRIC]
    archived = reader.rows(item['partition'])[0]
    eligible = listed_codes(shsz_listings(basic_fields,basic_rows),'2026-11-20')
    daily = breaknet.stock_day(fields,rows,'2026-11-20',eligible=eligible)
    assert archived == daily
    assert breaknet.project([archived],'main')[0]['ratio'] == 0
    definition = dict(breaknet.definition(),archive_source_snapshot='fixed')
    gap = dict(archived,main_valid=None)
    breaknet.update_history(definition,[gap])
    assert definition['history_audit']['missing_dates'] == ['2026-11-20']
    assert definition['archive_source_snapshot'] == 'fixed'
    parts['sh']['sha256'] = reader.objects.put(parquet_bytes([
        dict(zip(fields,['2026-11-20','sh.600000','0.5'])),
        dict(zip(fields,['2026-11-20','sh.600000','2']))]))
    with pytest.raises(ObservationError, match='股票重复'):
        breaknet_archive.derive_archive(reader,'fixed',basic_sha,monotonic()+30)
