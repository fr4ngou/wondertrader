"""Reusable SH/SZ stock-day standard partitions, retaining provider strings and parents."""
import io
import copy
from datetime import date
from .storage import digest, encode
from .metadata import asset_contract
from .provider_tables import load_table
from .source_fetch import SourceFailure
import re
from time import monotonic

MAX_DECODE_BYTES = 256 * 1024 * 1024


def validate_stock_partitions(objects,index,assets,deadline=None):
    """Stream the registered stock-string Parquet contract before head publication."""
    from .contracts import ObservationError
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    required=['date','code','pbMRQ','tradestatus','parent_sha256']
    total=0
    try:
        registered={}
        for asset in assets.values():
            if asset.get('group')!='standard.stock-pb':continue
            key=asset['dataset_id'];identity_match=re.fullmatch(r'stock-pb\.(sh|sz)\.(\d{4})',key)
            if not identity_match or asset['market']!=identity_match.group(1) or asset['media_type']!='application/vnd.apache.parquet' or asset['dataset_version']!=asset['sha256']:
                raise ValueError('registered stock asset identity mismatch')
            part=dict(sha256=asset['sha256'],market=asset['market'],year=int(identity_match.group(2)),rows=asset['rows'],parent_assets=sorted(asset['parent_assets']),format='parquet')
            if type(part['rows']) is not int or part['rows']<0 or len(part['parent_assets'])!=len(set(part['parent_assets'])):
                raise ValueError('registered stock count or parents invalid')
            identity=(key,part['sha256'])
            if identity in registered and registered[identity]!=part:
                raise ValueError('registered stock asset declarations conflict')
            registered[identity]=part
        if index is None:
            if registered:raise ValueError('registered stock assets require their current index')
            return dict(stock_partitions=0,stock_rows=0)
        if len(index['partitions'])>128 or len(registered)>128 or index['rows']>20000000:
            raise ValueError('stock archive budget exceeded')
        for key,part in index['partitions'].items():
            if type(part['rows']) is not int or type(part['year']) is not int:
                raise ValueError('stock index counts and year require integers')
            if not 0<=part['rows']<=2000000:
                raise ValueError('stock partition row budget exceeded')
            contract=registered.get((key,part['sha256']))
            normalized={k:part[k] for k in ('sha256','market','year','rows','parent_assets','format')}
            normalized['parent_assets']=sorted(normalized['parent_assets'])
            if contract!=normalized:raise ValueError('current stock index and asset registration conflict')
            total+=part['rows']
        if total!=index['rows']:raise ValueError('stock index row count mismatch')
        # Every registered historical version is verified, including versions outside the current index.
        for (key,_),part in registered.items():
            if deadline is not None and monotonic()>=deadline:
                raise ObservationError('observation_timeout','股票归档校验超过本次时间',503)
            market,year=part['market'],part['year']
            if market not in ('sh','sz') or key!='stock-pb.'+market+'.'+str(year) or part.get('format')!='parquet':
                raise ValueError('partition identity mismatch')
            # Preserve dictionary encoding: repeated long provider strings must not expand per row.
            source=pq.ParquetFile(io.BytesIO(objects.get(part['sha256'])),read_dictionary=required,thrift_string_size_limit=16*1024*1024,thrift_container_size_limit=100000)
            if source.metadata.num_rows>2000000 or source.metadata.num_columns>64:
                raise ValueError('stock partition decode budget exceeded')
            if sum(source.metadata.row_group(i).total_byte_size for i in range(source.metadata.num_row_groups))>MAX_DECODE_BYTES:
                raise ValueError('stock partition uncompressed byte budget exceeded')
            schema=source.schema_arrow
            if not set(required)<=set(schema.names) or len(schema.names)!=len(set(schema.names)):
                raise ValueError('stock schema fields missing or duplicated')
            types=[field.type.value_type if pa.types.is_dictionary(field.type) else field.type for field in schema]
            if any(not (pa.types.is_string(kind) or pa.types.is_large_string(kind)) for kind in types):
                raise ValueError('stock source strings must retain their type')
            if source.metadata.num_rows!=part['rows']:
                raise ValueError('stock partition row count mismatch')
            count=0
            parents=pa.array(part['parent_assets'],type=pa.string())
            for batch in source.iter_batches(batch_size=65536,columns=required):
                if deadline is not None and monotonic()>=deadline:
                    raise ObservationError('observation_timeout','股票归档校验超过本次时间',503)
                if batch.nbytes>MAX_DECODE_BYTES:
                    raise ValueError('stock batch byte budget exceeded')
                columns=dict(zip(batch.schema.names,batch.columns));count+=batch.num_rows
                def invalid(column,predicate):
                    if pa.types.is_dictionary(column.type):
                        mask=pc.take(pc.fill_null(predicate(column.dictionary),True),column.indices)
                    else:
                        mask=predicate(column)
                    return pc.any(pc.fill_null(mask,True)).as_py()
                for name in ('date','code','parent_sha256'):
                    if columns[name].null_count:raise ValueError('stock identity field missing')
                if invalid(columns['date'],lambda values:pc.invert(pc.match_substring_regex(values,pattern='^'+str(year)+r'-\d{2}-\d{2}$'))):
                    raise ValueError('stock partition year mismatch')
                if invalid(columns['code'],lambda values:pc.invert(pc.match_substring_regex(values,pattern='^'+market+r'\.\d{6}$'))):
                    raise ValueError('stock partition market mismatch')
                if invalid(columns['parent_sha256'],lambda values:pc.invert(pc.is_in(values,value_set=parents))):
                    raise ValueError('stock partition parent mismatch')
            if count!=part['rows']:raise ValueError('decoded stock row count mismatch')
    except ObservationError:raise
    except (ValueError,KeyError,TypeError,OSError,pa.ArrowException) as exc:
        raise ObservationError('invalid_stock_partition','股票PB标准分区格式、行数或来源字段校验失败',503) from exc
    return dict(stock_partitions=len(index['partitions']),stock_rows=total)



def attach_partitions(objects,manifest,index):
    manifest['stock_pb_partitions']=index
    for key,part in index['partitions'].items():
        asset_id=digest(encode(dict(dataset=key,sha256=part['sha256'])))
        manifest['assets'][asset_id]=asset_contract(dict(asset_id=asset_id,sha256=part['sha256'],bytes=len(objects.get(part['sha256'])),group='standard.stock-pb',source_ref=key,qualification='source_strings_preserved',parent_assets=part['parent_assets'],rows=part['rows'],dataset_id=key,dataset_version=part['sha256'],market=part['market'],media_type='application/vnd.apache.parquet',compression='zstd'))


def extend_daily_partitions(objects,manifest,records,*,check=lambda:None):
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    index=manifest.get('stock_pb_partitions')
    if not index:return
    batches={}
    basic=next((r for r in records if r.get('kind')=='stock_basic'),None)
    if not basic:return
    source=load_table(objects.get(basic['sha256']),('code','type'),check=check)
    universe={item['code'] for values in source.rows for item in [dict(zip(source.fields,values))] if item['type']=='1' and item['code'].startswith(('sh.','sz.'))}
    if any(re.fullmatch(r'(sh|sz)\.\d{6}',code) is None for code in universe):raise SourceFailure('pb_universe_identity')
    sizes={};seen=set()
    for record in records:
        if record.get('kind')!='stock_daily_batch':continue
        raw=load_table(objects.get(record['sha256']),('date','code','pbMRQ','tradestatus'),check=check)
        if 'parent_sha256' in raw.fields:raise SourceFailure('provider_table_fields')
        for values in raw.rows:
            check();row=dict(zip(raw.fields,values));code=row['code']
            if code not in universe:continue
            try:
                if date.fromisoformat(row['date']).isoformat()!=row['date']:raise ValueError('date')
            except ValueError:raise SourceFailure('pb_date_mismatch') from None
            identity=(row['date'],code)
            if identity in seen:raise SourceFailure('pb_duplicate_stock_date')
            seen.add(identity);key='stock-pb.'+code[:2]+'.'+row['date'][:4]
            row['parent_sha256']=record['sha256'];size=sizes.get(key,0)+len(encode(row))
            if size>MAX_DECODE_BYTES or len(batches.get(key,[]))>=2000000:
                raise SourceFailure('stock_incoming_budget_exceeded')
            sizes[key]=size;batches.setdefault(key,[]).append(row)
    next_index=copy.deepcopy(index)
    for key,rows in batches.items():
        check()
        previous=index['partitions'].get(key);parents=set(previous['parent_assets'] if previous else [])
        parents.update(r['parent_sha256'] for r in rows)
        incoming=pa.Table.from_pylist(rows)
        incoming=_collection_dictionary(incoming)
        if previous:
            original=_collection_stock_table(objects.get(previous['sha256']))
            dates=pa.array(sorted({r['date'] for r in rows}),type=pa.string())
            original=original.filter(pc.invert(pc.is_in(original['date'],value_set=dates)))
            # Historical and daily responses may expose different optional columns.
            # Preserve every supplied string; absent columns stay explicit null.
            incoming=pa.concat_tables([original,incoming],promote_options='default')
        if incoming.num_rows>2000000 or incoming.num_columns>64 or incoming.nbytes>MAX_DECODE_BYTES:
            from .contracts import ObservationError
            raise ObservationError('partition_budget_exceeded','股票分区超过更新容量',503)
        # Arrow按普通字符串键排序；只展开两个身份列，其余原始字符串继续共享字典。
        keys=pa.table({name:incoming[name].cast(pa.string()) for name in ('date','code')})
        incoming=incoming.take(pc.sort_indices(keys,sort_keys=[('date','ascending'),('code','ascending')]))
        # 标准文件仍登记逻辑string；运行时用字典合并，避免反复展开历史字符串。
        sink=io.BytesIO();pq.write_table(incoming,sink,compression='zstd',store_schema=False)
        sha=objects.put(sink.getvalue(),kind='standard')
        next_index['partitions'][key]=dict(sha256=sha,market=key.split('.')[1],year=int(key.split('.')[2]),rows=incoming.num_rows,parent_assets=sorted(parents),format='parquet',source_string_precision_preserved=True)
    next_index['rows']=sum(part['rows'] for part in next_index['partitions'].values())
    staged=dict(manifest,assets=dict(manifest['assets']));attach_partitions(objects,staged,next_index);check()
    manifest.update(stock_pb_partitions=staged['stock_pb_partitions'],assets=staged['assets'])


def _collection_stock_table(body):
    """更新时先核原分区解码声明；字典字符串避免全表重复展开。"""
    import pyarrow.parquet as pq
    import pyarrow as pa
    from .contracts import ObservationError
    source=pq.ParquetFile(io.BytesIO(body))
    if (source.metadata.num_rows>2000000 or source.metadata.num_columns>64
            or sum(source.metadata.row_group(i).total_byte_size for i in range(source.metadata.num_row_groups))>MAX_DECODE_BYTES):
        raise ObservationError('partition_budget_exceeded','股票分区超过更新容量',503)
    schema=source.schema_arrow
    types=[field.type.value_type if pa.types.is_dictionary(field.type) else field.type for field in schema]
    if (len(schema.names)!=len(set(schema.names)) or not {'date','code','pbMRQ','tradestatus','parent_sha256'}<=set(schema.names)
            or any(not (pa.types.is_string(kind) or pa.types.is_large_string(kind)) for kind in types)):
        raise ObservationError('invalid_stock_partition','股票原分区字段和字符串类型无效',503)
    return _collection_dictionary(pq.read_table(io.BytesIO(body),read_dictionary=source.schema_arrow.names))


def _collection_dictionary(table):
    import pyarrow as pa
    import pyarrow.compute as pc
    return pa.Table.from_arrays([column.cast(pa.dictionary(pa.int32(),pa.string()))
        if pa.types.is_dictionary(column.type) else pc.dictionary_encode(column.cast(pa.string()))
        for column in table.columns],names=table.column_names)
