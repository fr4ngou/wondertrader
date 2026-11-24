"""已校验逐股PB的历史重算；不重复联网，不创建第二份逐股数据。"""
import copy
import io
from datetime import datetime, timezone

from . import breaknet
from .admission import admit_dataset, register_standard_assets
from .contracts import ObservationError
from .metadata import computation_identity
from .publication import validate_manifest, check_deadline
from .stock_partitions import validate_stock_partitions
from .stock_universe import shsz_listings, listed_codes
from .provider_tables import load_table
from .storage import digest, encode


def derive_archive(reader, expected, basic_sha, deadline):
    """按原目录lease/CAS发布全历史破净统计；保留原对象、其他指标和所有来源配置。"""
    import pyarrow.parquet as pq

    check = lambda: check_deadline(deadline)
    with reader.repository.collection_lease() as acquired:
        if not acquired:
            raise ObservationError('another_owner_running', '其他观察写入者正在运行', 409)
        if reader.repository.current() != expected:
            raise ObservationError('publication_conflict', '观察版本已更新，请重新核对', 409)
        _, original = reader.snapshot(expected)
        if not any(asset['sha256'] == basic_sha for asset in original['assets'].values()):
            raise ObservationError('breaknet_listing_unregistered', '证券表原件未在当前观察目录登记', 503)
        basic = load_table(reader.objects.get(basic_sha), ('code','type','ipoDate','outDate'), check=check)
        listings = shsz_listings(basic.fields, basic.rows, check=check)
        index = original.get('stock_pb_partitions')
        if not index:
            raise ObservationError('breaknet_archive_missing', '缺少逐股PB归档', 503)
        hashes = {p['sha256'] for p in index['partitions'].values()}
        assets = {key: asset for key, asset in original['assets'].items()
                  if asset.get('group') == 'standard.stock-pb' and asset['sha256'] in hashes}
        validate_stock_partitions(reader.objects, index, assets, deadline, validated_assets=assets)
        by_day = {}; raw_counts = {}; markets = {}; eligible = {}
        for part in index['partitions'].values():
            check()
            seen = {}  # 同一市场/年份分区内逐日去重；分区切换即释放，不累积全历史股票身份。
            parquet = pq.ParquetFile(io.BytesIO(reader.objects.get(part['sha256'])))
            for batch in parquet.iter_batches(batch_size=65536, columns=['date','code','pbMRQ']):
                check()
                for row in batch.to_pylist():
                    day = row['date']
                    codes = seen.setdefault(day, set())
                    if row['code'] in codes:
                        raise ObservationError('breaknet_stock_day', '破净统计日期不符或股票重复', 503)
                    codes.add(row['code'])
                    raw_counts[day] = raw_counts.get(day, 0)+1
                    markets.setdefault(day, set()).add(part['market'])
                    result = by_day.setdefault(day, breaknet.empty_day(day))
                    if day not in eligible:
                        eligible[day] = listed_codes(listings, day, check=check)
                    if row['code'] in eligible[day]:
                        breaknet.add_stock(result, row['code'], row['pbMRQ'])
                        eligible[day].remove(row['code'])
        parent = original['datasets']['pb_shsz_daily']
        expected_counts = {r['date']: r['universe_count'] for r in reader.rows(parent['partition'])}
        calendar_sha = original['source_tables']['source.cn_official_calendar']
        calendar = reader.rows(calendar_sha)
        first, last = min(expected_counts), max(expected_counts)
        rows = []
        for session in calendar:
            day = session['date']
            if not session['is_open'] or not first <= day <= last:
                continue
            check()
            complete = (markets.get(day) == {'sh','sz'} and raw_counts.get(day) == expected_counts.get(day)
                        and not eligible.get(day, {None}))
            rows.append(by_day[day] if complete else dict(date=day, **{
                f'{s}_{key}': None for s in breaknet.SEGMENTS for key in breaknet.COUNTS}))
        if not rows:
            raise ObservationError('breaknet_archive_missing', '逐股PB归档缺少可核日期', 503)
        candidate = copy.deepcopy(original)
        definition = breaknet.definition()
        breaknet.update_history(definition, rows)
        definition['archive_source_snapshot'] = expected
        definition['listing_source_sha256'] = basic_sha
        candidate['datasets'][breaknet.METRIC] = admit_dataset(reader.objects, definition, rows,
                                                             [*hashes, parent['partition'], calendar_sha, basic_sha])
        breaknet.attach_board(candidate)
        register_standard_assets(reader.objects, candidate)
        candidate.update(parent_snapshot=expected, published_at=datetime.now(timezone.utc).isoformat(),
                         computation_identity=computation_identity())
        validation = validate_manifest(reader, candidate, deadline, previous_snapshot=expected)
        receipt = dict(status='snapshot_derived', previous_snapshot=expected,
                       current_snapshot=digest(encode(candidate)), completed_at=candidate['published_at'],
                       validation=validation)
        reader.repository.publish(candidate, expected, receipt=receipt, deadline=deadline)
        return receipt
