"""来源归一化及资产登记；沿原计算实现，不包含旧环境导入入口。"""
import copy
from .contracts import USAGE
from .query import parquet_bytes, validate_rows
from .storage import digest, encode
from .metadata import validate_fields, asset_contract

def admit_dataset(objects, definition, rows, parents):
    validate_rows(rows, tenor=definition.get('axis_type') == 'tenor')
    definition = copy.deepcopy(definition)
    definition['field_schema']=validate_fields(definition,rows)
    dates = [r['date'] for r in rows]
    definition['coverage'] = dict(start=min(dates) if dates else None, end=max(dates) if dates else None,
                                  observations=len(rows))
    if definition.get('frequency_audit'):
        audit=definition['frequency_audit']
        audit.update(observed_dates=len(rows),first_actual_date=min(dates) if dates else None,
                     last_actual_date=max(dates) if dates else None)
        for field in audit.get('fields',[]):
            if not field.get('computed_on_query'):
                field['valid_dates']=sum(row.get(field['key']) is not None for row in rows)
    partition = objects.put(parquet_bytes(rows), kind='standard')
    return dict(definition=definition, partition=partition, rows=len(rows), parents=sorted(set(parents)-{partition}),
                usage=USAGE, parser_version='observation-admission/2')

def register_standard_assets(objects,manifest):
    """Make every query partition and source table addressable through the same asset API."""
    for key,item in manifest['datasets'].items():
        definition=item['definition']
        register_standard_asset(objects,manifest,key,item['partition'],item['parents'],'standard.metric',rows=item['rows'],
            dataset_id=key,dataset_version=item['partition'],definition_id=key,definition_version=definition.get('definition_version'),definition_hash=digest(encode(definition)),
            media_type='application/vnd.apache.parquet',compression='zstd',observation_start=definition['coverage']['start'],observation_end=definition['coverage']['end'])
    for key,sha in manifest.get('source_tables',{}).items():
        register_standard_asset(objects,manifest,key,sha,manifest.get('source_table_parents',{}).get(key,[]),'standard.source-table',dataset_id=key,dataset_version=sha,media_type='application/vnd.apache.parquet',compression='zstd')
    manifest['assets']={key:asset_contract(asset) for key,asset in manifest['assets'].items()}

def register_standard_asset(objects,manifest,key,sha,parents,group,**metadata):
    parents=sorted(set(parents)-{sha})
    identity=digest(encode(dict(dataset=key,sha256=sha,parents=parents)))
    manifest['assets'][identity]=dict(asset_id=identity,sha256=sha,bytes=len(objects.get(sha)),
        group=group,source_ref=key,parent_assets=parents,qualification='verified_content',usage=USAGE,**metadata)
    return identity
