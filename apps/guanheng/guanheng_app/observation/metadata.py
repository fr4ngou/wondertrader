"""Strict semantic admission, with explicit unknown provenance for legacy assets."""
import math
from pathlib import Path
from datetime import date,datetime
from pydantic import ValidationError
from .contracts import ObservationError,ObservationField,ObservationAsset,USAGE,SCHEMA_VERSION,SeriesQuery
from .storage import digest

NUMERIC_UNITS={'%','0/1','万亿元','亿元','倍','元','只','基准100','对数偏离','年','张','手','指数点','无量纲','条','条，未认证为去重组合数','标准化压力','源数值，异常时单位待核','百分点','笔','绝对单位待核','股','页'}


def computation_identity():
    """所有观察发布入口记录本次实际安装的同一计算闭包。"""
    return {path.name:digest(path.read_bytes()) for path in sorted(Path(__file__).parent.glob('*.py'))}

def field_contract(definition):
    schema=definition.get('field_schema',{})
    if not schema or 'date' not in schema or definition.get('primary_field') and definition['primary_field'] not in schema:raise ObservationError('invalid_schema','观察字段契约尚未登记或缺少主字段')
    try:SeriesQuery(metric_id=definition['id'],**definition.get('calculation_defaults',{}))
    except (ValidationError,TypeError) as exc:raise ObservationError('invalid_schema','默认计算参数不符合允许范围') from exc
    units={line['key']:line.get('unit') for line in definition.get('lines',[])}
    computed={field['key'] for field in definition.get('frequency_audit',{}).get('fields',[]) if field.get('computed_on_query')}
    result={}
    for key,item in schema.items():
        unit=item.get('unit',units.get(key,'日期' if key=='date' else '时间，未知留空' if key=='available_at' else None))
        if unit=='日期':kind='date'
        elif unit and unit.startswith('时间'):kind='datetime'
        elif unit and (unit.startswith('文本') or unit in ('合约代码','期限','文件名')):kind='string'
        elif unit is None or unit in NUMERIC_UNITS:kind='number'
        else:raise ObservationError('invalid_unit','字段单位未登记，须核对来源定义')
        declared=item.get('data_type',kind)
        if unit is not None and (declared not in ('number','integer') if kind=='number' else declared!=kind):raise ObservationError('invalid_schema','字段类型与登记单位不符')
        try:result[key]=ObservationField.model_validate(dict(item,unit=unit,data_type=item.get('data_type',kind),required=item.get('required',key=='date' or key==definition.get('primary_field') and key not in computed),computed_on_query=key in computed)).model_dump()
        except ValidationError as exc:raise ObservationError('invalid_schema','字段定义不完整') from exc
    return result

def validate_fields(definition,rows):
    schema=field_contract(definition)
    for row in rows:
        if set(row)-set(schema):raise ObservationError('unknown_field','观察含未登记字段，须更新字段契约')
        for key,field in schema.items():
            if key not in row:
                if field['required']:raise ObservationError('missing_field',f"{definition.get('id','观察')} 缺少必需字段：{key}")
                continue
            value=row[key]
            if value is None:
                if not field['nullable']:raise ObservationError('null_field','必需数值存在空值')
                continue
            kind=field['data_type'];valid=True
            if kind in ('number','integer'):valid=isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and (kind!='integer' or float(value).is_integer())
            elif kind=='string':valid=isinstance(value,str)
            else:
                try:
                    if not isinstance(value,str):raise ValueError()
                    (date.fromisoformat if kind=='date' else datetime.fromisoformat)(value.replace('Z','+00:00'))
                except ValueError:valid=False
            if not valid:raise ObservationError('invalid_field_type','观察值与登记字段类型不符')
    return schema

def asset_contract(asset,*,source=None,record=None,capture_id=None):
    source=source or {};record=record or {}
    raw=dict(asset)
    raw.update(byte_size=asset.get('byte_size',asset.get('bytes')),source_id=asset.get('source_id',source.get('id')),
        capture_id=asset.get('capture_id',capture_id),object_ref='sha256:'+asset['sha256'],
        media_type=asset.get('media_type',record.get('media_type')),encoding=asset.get('encoding',record.get('encoding')),
        compression=asset.get('compression',record.get('compression')),published_at=asset.get('published_at'),available_at=asset.get('available_at'),
        retrieved_at=asset.get('retrieved_at',record.get('retrieved_at')),ingested_at=asset.get('ingested_at'),
        source_timezone=asset.get('source_timezone',source.get('timezone')),calendar_id=asset.get('calendar_id',source.get('calendar_id')),
        calendar_version=asset.get('calendar_version',source.get('calendar_version')),license_ref=asset.get('license_ref',source.get('license_ref')),
        provider_symbol=asset.get('provider_symbol'),instrument_id=asset.get('instrument_id'),market=asset.get('market'),
        dataset_id=asset.get('dataset_id'),dataset_version=asset.get('dataset_version'),definition_id=asset.get('definition_id'),
        definition_version=asset.get('definition_version'),definition_hash=asset.get('definition_hash'),schema_version=asset.get('schema_version',SCHEMA_VERSION),
        revision_id=asset.get('revision_id'),observation_start=asset.get('observation_start'),observation_end=asset.get('observation_end'),
        internal_use=asset.get('internal_use','rights_unverified_restricted_research'),redistribution_allowed=False,
        quality=asset.get('quality',dict(content='sha256_verified',parsed='unknown',semantic='unknown',independent_reconciliation='unknown',freshness='unknown')),
        usage=asset.get('usage',dict(USAGE)))
    try:return ObservationAsset.model_validate(raw).model_dump()
    except ValidationError as exc:raise ObservationError('invalid_asset_metadata','资产元数据与契约不符') from exc
