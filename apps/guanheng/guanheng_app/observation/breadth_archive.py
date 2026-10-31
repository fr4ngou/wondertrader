"""从已归档同源原件计算日终横截面；复用原采用事务，不访问供应商。"""

import copy
from datetime import date, datetime, timezone
import io
import json

from .admission import admit_dataset, register_standard_assets, register_standard_asset
from .breadth_models import SHSZ_METRICS as METRICS, admit_definition, attach_boards, definition, rows_for_metrics, universe_row
from .contracts import ObservationError, USAGE
from .market_breadth import stock_day
from .metadata import computation_identity
from .provider_tables import load_table
from .publication import adopt_snapshot, check_deadline
from .query import ObservationReader, parquet_bytes
from .refresh_models import merge
from .stock_partitions import validate_stock_partitions
from .storage import digest, encode
from .source_fetch import BoundedContentStore, CollectionBudget
from .stock_universe import shsz_listings, listed_codes


def derive_archive(source, target, snapshot, start, end, expected, deadline):
    """固定来源版本→原证券表/日线→计算→同一目录CAS；调用者显式授予目标根写入。"""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if not 0 <= (last-first).days <= 366:
        raise ObservationError('invalid_range', '股票归档计算每批需要0至366天的有效日期范围', 422)
    check=lambda:check_deadline(deadline)
    check()
    budget=CollectionBudget(deadline,max_requests=0)
    source=ObservationReader(source.repository,BoundedContentStore(source.objects,budget))
    target=ObservationReader(target.repository,BoundedContentStore(target.objects,budget))
    with target.repository.collection_lease() as acquired:
        if not acquired:
            raise ObservationError('another_owner_running', '其他观察写入者正在运行', 409)
        if target.repository.current()!=expected:
            raise ObservationError('publication_conflict', '目标观察版本已变化，请核对当前版本', 409)
        _, manifest=source.snapshot(snapshot)
        parents=_daily_parents(source,manifest,start,end,deadline)
        if not parents:
            raise ObservationError('stock_prices_missing', '所选范围缺少已归档的完整股票日线原件', 503)
        captures={identity:[] for identity in parents.values()};source_assets={}
        for asset_id,asset in manifest['assets'].items():
            check()
            if asset.get('group')=='source.capture' and asset.get('capture_id'):
                source_assets.setdefault((asset['capture_id'],asset['sha256']),[]).append((asset_id,asset))
                if asset['sha256'] in captures:captures[asset['sha256']].append(asset['capture_id'])
        updates={metric:[] for metric in METRICS};universes=[];raw_parents=set();capture_cache={};basic_cache={}
        provenance_assets={};capture_parents={}
        for day, identity in sorted(parents.items()):
            check()
            if not captures[identity]:
                raise ObservationError('stock_lineage_missing', '股票日线缺少证券表来源记录', 503)
            candidates=[]
            for capture in sorted(set(captures[identity])):
                check()
                if capture not in capture_cache:
                    capture_body=source.objects.get(capture)
                    capture_cache[capture]=json.loads(capture_body)
                    target.objects.put(capture_body);raw_parents.add(capture)
                records=capture_cache[capture]
                basics=[r['sha256'] for r in records if r.get('kind')=='stock_basic']
                if len(basics)!=1:
                    raise ObservationError('stock_lineage_invalid', '证券表原件身份存在歧义', 503)
                basic_sha=basics[0]
                capture_parents.setdefault(capture,set()).update((basic_sha,identity))
                for raw_sha in (basic_sha,identity):
                    for asset_id,asset in source_assets.get((capture,raw_sha),[]):
                        check();provenance_assets[asset_id]=copy.deepcopy(asset)
                        for parent in asset.get('parent_assets',[]):
                            target.objects.put(source.objects.get(parent));raw_parents.add(parent)
                if basic_sha not in basic_cache:
                    body=source.objects.get(basic_sha)
                    table=load_table(body,('code','type','ipoDate','outDate'),check=check)
                    basic_cache[basic_sha]=shsz_listings(table.fields,table.rows,check=check)
                    target.objects.put(body)
                codes=listed_codes(basic_cache[basic_sha],day,check=check)
                candidates.append((sorted(codes),basic_sha));raw_parents.add(basic_sha)
            if any(codes!=candidates[0][0] for codes,_ in candidates):
                raise ObservationError('stock_universe_ambiguous', '同一日线的证券表股票池不一致', 503)
            codes,basic_sha=candidates[0]
            body=source.objects.get(identity);raw=load_table(body,('date','code','close','preclose','volume','turn','tradestatus'),check=check)
            result=stock_day(raw.fields,raw.rows,codes,day,check=check)
            for metric,row in rows_for_metrics(result,METRICS).items():updates[metric].append(row)
            universes.append(universe_row(day,codes,basic_sha));target.objects.put(body);raw_parents.add(identity)
        check()
        candidate=copy.deepcopy(target.repository.get(expected)) if expected else dict(
            schema_version='market-observation/1',boards=[],preferences=dict(default_board='',default_datasets={}),
            datasets={},assets={},source_tables={},source_table_parents={})
        candidate['usage']=dict(USAGE)
        for asset_id,asset in provenance_assets.items():
            if asset_id in candidate['assets'] and candidate['assets'][asset_id]!=asset:
                raise ObservationError('stock_lineage_conflict', '同一股票来源记录的资料发生冲突', 409)
            candidate['assets'][asset_id]=asset
        for capture,capture_raw in capture_parents.items():
            register_standard_asset(target.objects,candidate,'archive.capture.'+capture,capture,
                capture_raw,'archive.capture-manifest',media_type='application/json')
        old_universe=candidate.get('source_tables',{}).get('source.shsz_universe')
        prior=[] if old_universe is None else target.rows(old_universe)
        universe_rows=merge(prior,universes)[0]
        universe_partition=target.objects.put(parquet_bytes(universe_rows),kind='standard')
        candidate.setdefault('source_tables',{})['source.shsz_universe']=universe_partition
        candidate.setdefault('source_table_parents',{})
        all_parents=sorted(raw_parents|({old_universe} if old_universe else set()))
        if len(all_parents)>256:
            raise ObservationError('stock_parent_capacity', '股票池来源版本超过本批容量，请分期核验归档', 503)
        candidate['source_table_parents']['source.shsz_universe']=all_parents
        for metric,rows in updates.items():
            check();old=candidate['datasets'].get(metric)
            prior=target.rows(old['partition']) if old else []
            metadata=admit_definition(metric,old['definition'] if old else None,prior,rows)
            rows=merge(prior,rows)[0]
            metadata.update(universe_version=universe_partition,archive_source_snapshot=snapshot)
            lineage=[*all_parents,*([old['partition'],*old['parents']] if old else [])]
            candidate['datasets'][metric]=admit_dataset(target.objects,metadata,rows,lineage)
        attach_boards(candidate,candidate['datasets']);register_standard_assets(target.objects,candidate)
        candidate['published_at']=datetime.now(timezone.utc).isoformat()
        candidate['computation_identity']=computation_identity()
        candidate['parent_snapshot']=expected
        return adopt_snapshot(target,candidate,digest(encode(candidate)),expected,deadline)


def _daily_parents(source, manifest, start, end, deadline):
    """原股票分区校验器验证所用年份；仅从身份列定位原始日线对象。"""
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    index=manifest.get('stock_pb_partitions')
    if not index:return {}
    parts={key:part for key,part in index['partitions'].items() if int(start[:4])<=part['year']<=int(end[:4])}
    selected=set(part['sha256'] for part in parts.values())
    assets={key:a for key,a in manifest['assets'].items() if a.get('group')=='standard.stock-pb' and a['sha256'] in selected}
    check_deadline(deadline)
    validate_stock_partitions(source.objects,dict(partitions=parts,rows=sum(p['rows'] for p in parts.values())),assets,deadline)
    by_day={}
    for part in parts.values():
        check_deadline(deadline)
        parquet=pq.ParquetFile(io.BytesIO(source.objects.get(part['sha256'])))
        if 'close' not in parquet.schema_arrow.names:continue
        for batch in parquet.iter_batches(batch_size=65536,columns=['date','parent_sha256','close']):
            check_deadline(deadline)
            mask=pc.and_(pc.and_(pc.greater_equal(batch.column(0),start),pc.less_equal(batch.column(0),end)),pc.is_valid(batch.column(2)))
            for row in batch.filter(mask).to_pylist():by_day.setdefault(row['date'],set()).add(row['parent_sha256'])
    if any(len(parents)!=1 for parents in by_day.values()):
        raise ObservationError('stock_source_ambiguous', '同日股票分区引用了不同原始日线，请核验修订', 503)
    return {day:next(iter(parents)) for day,parents in by_day.items()}
