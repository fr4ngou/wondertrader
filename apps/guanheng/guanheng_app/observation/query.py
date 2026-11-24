"""Bounded, snapshot-pinned queries shared by UI, exports and research clients."""
import base64
import copy
import io
import json
import math
from collections import OrderedDict
from datetime import date, datetime, timezone
from threading import RLock
from concurrent.futures import Future,TimeoutError as FutureTimeout
from time import monotonic
from .contracts import ObservationError, SeriesQuery, USAGE,ObservationAsset,ObservationField
from .calculations import derive, quantile
from .storage import digest, encode
from .pcr_daily import definition_view

def parquet_bytes(rows):
    import pyarrow as pa
    import pyarrow.parquet as pq
    keys = list(dict.fromkeys(key for row in rows for key in row))
    normalized = [{key:row.get(key) for key in keys} for row in rows]
    sink = io.BytesIO(); pq.write_table(pa.Table.from_pylist(normalized), sink, compression='zstd')
    return sink.getvalue()

def read_parquet(body):
    import pyarrow.parquet as pq
    source = pq.ParquetFile(io.BytesIO(body), thrift_string_size_limit=16*1024*1024, thrift_container_size_limit=100000)
    if (source.metadata.num_rows > 100000 or source.metadata.num_columns > 256
            or sum(source.metadata.row_group(i).total_byte_size for i in range(source.metadata.num_row_groups)) > 256*1024*1024):
        raise ObservationError('partition_budget_exceeded','观察分区超过读取容量',503)
    return source.read().to_pylist()


def prepare_parquet_runtime():
    """Check the required codec before readiness, without reading business assets."""
    if read_parquet(parquet_bytes([])) != []:
        raise RuntimeError('observation Parquet codec failed its startup check')

def validate_rows(rows, *, tenor=False):
    keys = []
    for row in rows:
        date.fromisoformat(row['date'])
        for value in row.values():
            if isinstance(value, float) and not math.isfinite(value):
                raise ObservationError('invalid_value', '数据含无效数值')
        keys.append((row['date'], float(row['tenor_years'])) if tenor else row['date'])
    if len(keys) != len(set(keys)) or keys != sorted(keys):
        raise ObservationError('invalid_order', '观察日期须唯一且按升序排列')


def calculation_query(definition,query):
    defaults=dict(window=20,k=2,method='sma',pcr_type='oi')
    defaults.update(definition.get('calculation_defaults',{}))
    return query.model_copy(update={key:value for key,value in defaults.items() if getattr(query,key) is None})

class ObservationReader:
    def __init__(self, repository, objects):
        self.repository, self.objects = repository, objects
        self.cache = OrderedDict(); self.lock = RLock()
        self.manifests = OrderedDict()
        self.calculations=OrderedDict();self.inflight={}

    def snapshot(self, version=None):
        version = version or self.repository.current()
        if not version: raise ObservationError('not_initialized', '观察数据尚未接纳', 503)
        with self.lock:
            if version in self.manifests:
                self.manifests.move_to_end(version)
                return version,self.manifests[version]
        manifest=self.repository.get(version)
        if digest(encode(manifest))!=version:
            raise ObservationError('corrupt_snapshot','数据目录版本校验失败',503)
        with self.lock:
            self.manifests[version]=manifest
            while len(self.manifests)>4: self.manifests.popitem(last=False)
        return version,manifest

    def catalog(self, version=None):
        pinned = version is not None
        version, manifest = self.snapshot(version)
        return dict(schema_version=manifest['schema_version'], snapshot_id=version,
                    published_at=manifest['published_at'], boards=manifest['boards'],
                    recent_events=self.recent_events(manifest, as_of=None if pinned else datetime.now(timezone.utc)),
                    preferences=manifest['preferences'], datasets=[dict(id=d['id'], board=d['board'],
                    label=d['label'], source=d.get('source',''), frequency=d['frequency'], coverage=d['coverage'],
                    dataset_version=v['partition'], quality=d.get('quality', {}),
                    definition_version=d['definition_version'], **({'default_preset':'all'} if d.get('default_preset')=='all' else {}))
                    for v in manifest['datasets'].values() for d in [definition_view(copy.deepcopy(v['definition']))]],
                    contract_schemas=dict(asset=ObservationAsset.model_json_schema(),field=ObservationField.model_json_schema()),
                    usage=USAGE, execution_enabled=False)

    def recent_events(self, manifest, *, as_of=None):
        """以实时或显式快照时钟取得闭合交易日，只使用当前目录内的事件值。"""
        from .calendars import closed_day_cutoff

        # 历史指标也保存固定日期标注；只有逐日事件规则提供触发状态。
        items = [item for item in manifest['datasets'].values()
                 if isinstance(item['definition'].get('event_markers'), dict)]
        if not items:
            return {}
        calendar = manifest.get('source_tables', {}).get('source.cn_official_calendar')
        cutoff = closed_day_cutoff(as_of or datetime.fromisoformat(manifest['published_at'].replace('Z', '+00:00')))
        calendar_rows = self.rows(calendar) if calendar else []
        days = set(sorted(row['date'] for row in calendar_rows
                          if row.get('is_open') == 1 and row['date'] <= cutoff)[-5:])
        calendar_complete = bool(calendar_rows) and max(row['date'] for row in calendar_rows) >= cutoff
        result = {}
        for item in items:
            definition = item['definition']
            config = definition['event_markers']
            labels = {event['code']: event['label'] for event in config['values']}
            status = result.setdefault(definition['board'], dict(state='complete', events=[]))
            known = set()
            for row in self.rows(item['partition']):
                if row['date'] not in days or row.get(config['field']) is None:
                    continue
                known.add(row['date'])
                label = labels.get(row[config['field']])
                if label is not None:
                    status['events'].append(dict(date=row['date'], label=label))
            if not calendar_complete or len(days) != 5 or known != days:
                status['state'] = 'incomplete'
        for status in result.values():
            status['events'].sort(key=lambda event: (event['date'], event['label']), reverse=True)
        return result

    def definition(self, metric, version=None):
        version, manifest = self.snapshot(version)
        try: item = manifest['datasets'][metric]
        except KeyError as exc:
            raise ObservationError('unknown_metric', '观察口径未登记', 404) from exc
        return version, definition_view(copy.deepcopy(item['definition'])), item

    def rows(self, partition):
        with self.lock:
            if partition in self.cache:
                self.cache.move_to_end(partition)
                return self.cache[partition]
        rows = read_parquet(self.objects.get(partition))
        if len(rows)>100000:
            raise ObservationError('row_budget_exceeded','观察分区超过读取容量',503)
        with self.lock:
            self.cache[partition] = rows
            while len(self.cache) > 8: self.cache.popitem(last=False)
        return rows

    def series(self, query: SeriesQuery, deadline=None):
        if query.as_of:
            raise ObservationError('historical_availability_unverified', '历史当时可得时点尚未认证', 422)
        version, definition, item = self.definition(query.metric_id, query.snapshot_id)
        query=calculation_query(definition,query)
        if definition['board']=='pcr':
            for line in definition['lines']:
                if line['key'] in ('call_count','put_count'):
                    side = '认购' if line['key']=='call_count' else '认沽'
                    line['name'] = ('盘后'+side+'持仓') if query.pcr_type=='oi' else ('当日'+side+'累计成交')
        if definition.get('parameters'):
            definition['calculation']=dict(window=query.window,k=query.k,method=query.method,pcr_type=query.pcr_type,include_current=True,population_ddof=0,warmup='使用完整已归档历史预热后选择日期；显式空值重置状态')
            center=f'{query.window}个有效观察算术均值' if query.method=='sma' else f'EMA{query.window}'
            sigma='EMA二阶矩标准差' if query.method=='ema_moments' else '同窗口总体标准差'
            for line in definition['lines']:
                band_key = line['key'].removeprefix('reference_')
                if band_key in ('upper','middle','lower'):
                    basis = '日终PCR；' if definition['board']=='pcr' else ''
                    line['formula']=basis+center+(f" {'+' if band_key=='upper' else '−'} {query.k} × {sigma}" if band_key!='middle' else '')
        if query.dataset_version and query.dataset_version != item['partition']:
            raise ObservationError('version_mismatch', '数据版本与快照不匹配', 409)
        fields = query.fields.split(',') if query.fields else None
        permitted = set(definition['field_schema']) | {'date', 'available_at'}
        if fields and (len(fields) != len(set(fields)) or set(fields)-permitted):
            raise ObservationError('invalid_fields', '字段未登记或重复', 422)
        # Full-history derivation prevents moving window warmup and PB percentile drift.
        rows = self.derived(item,definition,query,deadline)
        if definition.get('quantile_policy'):
            field = definition['quantile_policy']['field']
            sample = [r.get(field) for r in rows if not query.end or r['date'] <= str(query.end)]
            definition['reference_levels'] = [dict(level, value=quantile(sample, level['probability']))
                                               for level in definition.get('reference_levels', [])]
            definition['quantile_sample'] = dict(count=sum(v is not None for v in sample), cutoff=str(query.end) if query.end else definition['coverage']['end'])
        rows = [r for r in rows if (not query.start or r['date'] >= str(query.start))
                and (not query.end or r['date'] <= str(query.end))]
        if definition.get('axis_type')=='tenor' and rows:
            latest=max(r['date'] for r in rows)
            rows=[r for r in rows if r['date']==latest]
        identity = query.model_dump(mode='json', exclude={'cursor', 'limit', 'snapshot_id'})
        identity['snapshot_id'] = version
        signature = digest(encode(identity)); offset = 0
        if query.cursor:
            try:
                cursor = json.loads(base64.urlsafe_b64decode(query.cursor))
                if cursor['query'] != signature or cursor['version'] != version: raise ValueError()
                offset = cursor['offset']
                if type(offset) is not int or not 0 <= offset <= len(rows): raise ValueError()
                if cursor['last'] != (rows[offset-1]['date'] if offset else None): raise ValueError()
            except Exception as exc:
                raise ObservationError('invalid_cursor', '游标与查询或固定版本不匹配', 422) from exc
        end = min(len(rows), offset+query.limit)
        cursor = base64.urlsafe_b64encode(encode(dict(query=signature, version=version,
                  offset=end, last=rows[end-1]['date']))).decode() if end < len(rows) else None
        output = rows[offset:end]
        if fields: output = [{k: r.get(k) for k in ['date', *fields] if k in r} for r in output]
        return dict(metric_id=query.metric_id, snapshot_id=version, dataset_version=item['partition'],
                    definition=definition, rows=output, next_cursor=cursor, total=len(rows),
                    coverage=dict(loaded_start=definition['coverage']['start'],
                    loaded_end=definition['coverage']['end'], requested_start=str(query.start) if query.start else None,
                    requested_end=str(query.end) if query.end else None, actual_dates=len(rows),
                    missing_dates=definition.get('history_audit', {}).get('missing_dates', [])), usage=USAGE)

    def derived(self,item,definition,query,deadline=None):
        query=calculation_query(definition,query)
        # Visible dates, fields and pagination never alter full-history calculations.
        key=(item['partition'],digest(encode(definition)),query.window,query.k,query.method,query.pcr_type,query.segments)
        with self.lock:
            if key in self.calculations:
                self.calculations.move_to_end(key);return self.calculations[key]
            future=self.inflight.get(key);compute=future is None
            if compute:
                if len(self.inflight)>=8:raise ObservationError('query_busy','观察计算繁忙，请稍后重试',503)
                future=Future();self.inflight[key]=future
        if not compute:
            try:return future.result(timeout=15 if deadline is None else max(0,deadline-monotonic()))
            except FutureTimeout as exc:raise ObservationError('query_busy','观察计算等待超时，请稍后重试',503) from exc
        def check():
            if deadline is not None and monotonic()>=deadline:
                raise ObservationError('observation_timeout','观察计算超过本次时间，请重新读取',503)
        try:rows=derive(self.rows(item['partition']),definition,query,check=check)
        except BaseException as exc:
            with self.lock:self.inflight.pop(key,None)
            future.set_exception(exc);raise
        with self.lock:
            self.calculations[key]=rows
            while len(self.calculations)>8:self.calculations.popitem(last=False)
            self.inflight.pop(key,None)
        future.set_result(rows)
        return rows

    def all_rows(self, query, deadline=None):
        version, _ = self.snapshot(query.snapshot_id)
        query = query.model_copy(update={'snapshot_id': version, 'limit': 1000, 'cursor': None})
        while True:
            page = self.series(query,deadline)
            yield from page['rows']
            if not page['next_cursor']: break
            query = query.model_copy(update={'cursor': page['next_cursor']})
