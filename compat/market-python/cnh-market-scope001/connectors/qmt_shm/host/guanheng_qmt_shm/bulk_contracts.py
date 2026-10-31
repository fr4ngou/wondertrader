"""HC1/HC2纯值边界；原body固定身份和D，结果只含有界产物引用。"""
from datetime import date, datetime, timezone
import hashlib
import re
from uuid import UUID

from guanheng_qmt_shm_agent.bulk_capabilities import BULK_OPERATION, profile_descriptor
from guanheng_qmt_shm_agent.read_capabilities import BULK_READ_PROFILE_VERSION
from guanheng_qmt_shm_agent.history_1m import arguments, HistoryError
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.results import RESULT_DEFAULTS, finalize_result
from guanheng_qmt_shm_agent.trade_clock import CLOCK_SCHEMA, deadline_seconds
from .bound import binding

ERRORS = ('operation_interrupted','source_binding_changed','queue_timeout','expired',
          'source_failed','storage_failed','invalid_page')
MESSAGE = '批量历史读取未完成；保留原请求标识核查'
REQUEST_FIELDS = ('schema_version request_id correlation_id operation_id policy_id policy_version '
                  'arguments snapshot_id clock_schema deadline_ms queue_deadline_ms priority_class read_profile_version')


def _need(value):
    if not value: raise ValueError('invalid_bulk_contract')


def _fields(value, keys):
    _need(type(value) is dict and all(type(k) is str for k in value) and set(value)==set(keys.split()))


def _uuid(value):
    _need(type(value) is str and len(value)==36)
    try: _need(str(UUID(value))==value)
    except (TypeError,AttributeError): raise ValueError('invalid_bulk_contract') from None
    return value


def _integer(value, maximum=None):
    _need(type(value) is int and value>=0 and (maximum is None or value<=maximum))


def _text(value, maximum):
    _need(type(value) is str and 0<len(value)<=maximum and bool(value.strip())
          and not any(ord(c)<32 or 127<=ord(c)<=159 or 0xd800<=ord(c)<=0xdfff for c in value))


def _identity(value):
    _fields(value,'range_id session_id snapshot_id symbol start_time end_time')
    _uuid(value['range_id']); _uuid(value['snapshot_id'])
    _need(type(value['session_id']) is str and re.fullmatch('[0-9a-f]{32}',value['session_id']) is not None)
    try:
        arguments(dict(symbol=value['symbol'],start_time=value['start_time'],end_time=value['end_time'],max_rows=1),
                  date(2100,1,1),36600,1)
    except HistoryError: raise ValueError('invalid_bulk_contract') from None


def validate_bulk_request(value, profile, *, max_result_bytes):
    descriptor=profile_descriptor(profile,max_result_bytes=max_result_bytes)
    _fields(value,REQUEST_FIELDS)
    expected=dict(schema_version='qmt.history-bulk-request.v1',operation_id=BULK_OPERATION,
                  policy_id=descriptor['policy_id'],policy_version=descriptor['policy_version'],
                  clock_schema=CLOCK_SCHEMA,priority_class='normal',read_profile_version=BULK_READ_PROFILE_VERSION)
    for key,item in expected.items(): _need(type(value[key]) is str and value[key]==item)
    for key in ('request_id','correlation_id','snapshot_id'): _uuid(value[key])
    deadline_seconds(value['deadline_ms']); deadline_seconds(value['queue_deadline_ms'])
    _need(value['queue_deadline_ms']<=value['deadline_ms'])
    # 只核固定历史域及结构；实际上海今日由SDK准入owner检查，不读取当前时间。
    try:
        arguments(value['arguments'],date(2100,1,1),descriptor['limits']['max_calendar_days'],descriptor['limits']['max_rows'])
    except HistoryError: raise ValueError('invalid_bulk_contract') from None
    return decode(canonical(value))


def bulk_source_session(actual_binding):
    actual=binding(actual_binding,control_version='3.0')
    return dict(provider='Qmt',instance_id=actual['host_instance_id'],
                session_id=actual['transport_generation'],generation=actual['route']['route_epoch']+1)


def bulk_identity(request, actual_binding):
    source=bulk_source_session(actual_binding)
    result=dict(range_id=_uuid(request['request_id']),snapshot_id=_uuid(request['snapshot_id']),
        session_id=source['session_id'],symbol=request['arguments']['symbol'],
        start_time=request['arguments']['start_time'],end_time=request['arguments']['end_time'])
    _identity(result)
    return result


def bulk_open_payload(request, actual_binding):
    identity=bulk_identity(request,actual_binding)
    deadline_seconds(request['deadline_ms']); deadline_seconds(request['queue_deadline_ms'])
    _need(request['queue_deadline_ms']<=request['deadline_ms'] and request['clock_schema']==CLOCK_SCHEMA)
    return decode(canonical(dict(request_id=request['request_id'],identity=identity,arguments=request['arguments'],
        clock_schema=CLOCK_SCHEMA,deadline_ms=request['deadline_ms'],queue_deadline_ms=request['queue_deadline_ms'])))


def _source_profile(value):
    _fields(value,'dataset_version source_license input_kind asset_class timezone minute_boundary adjustment factor_version value_semantics price_unit volume_unit amount_unit')
    for key in ('dataset_version','source_license'): _text(value[key],256)
    allowed=dict(input_kind=('synthetic','qmt_export'),asset_class=('cash-equity',),timezone=('Asia/Shanghai',),
        minute_boundary=('left','right','unknown'),adjustment=('none',),factor_version=('',),value_semantics=('source',),
        price_unit=('CNY','unknown'),volume_unit=('share','lot','unknown'),amount_unit=('CNY','unknown'))
    for key,items in allowed.items(): _need(type(value[key]) is str and value[key] in items)


def validate_bulk_source_profile(value):
    """HC2与部署配置共用BF十二字段边界，返回无别名的小快照。"""
    _source_profile(value)
    return decode(canonical(value))


def _artifact(data, request, actual_binding):
    _fields(data,'schema identity source_session source_profile artifact_root_id relative_root manifest_path manifest_sha256 rows pages bytes importable')
    _need(data['schema']=='qmt.history-bulk-artifact.v1')
    identity=data['identity']; _identity(identity)
    source=data['source_session']; _fields(source,'provider instance_id session_id generation')
    _need(source['provider']=='Qmt')
    for key in ('instance_id','session_id'):
        _need(type(source[key]) is str and re.fullmatch('[0-9a-f]{32}',source[key]) is not None)
    _integer(source['generation'],2**53); _need(source['generation']>=1)
    _need(source['session_id']==identity['session_id'])
    if actual_binding is not None: _need(source==bulk_source_session(actual_binding))
    validate_bulk_source_profile(data['source_profile']); _uuid(data['artifact_root_id'])
    _need(data['relative_root']==identity['range_id']+'--'+identity['snapshot_id'])
    _integer(data['rows'],1000000); _integer(data['pages'],10000); _need(data['pages']>=1)
    _integer(data['bytes'],(data['pages']+1)*2097152)
    _need(type(data['importable']) is bool and data['importable']==(data['rows']>0))
    if data['rows']==0:
        _need(data['manifest_path'] is None and data['manifest_sha256'] is None and data['bytes']==0)
    else:
        _need(data['manifest_path']=='qmi-manifest.json' and data['bytes']>0)
        _need(type(data['manifest_sha256']) is str and re.fullmatch('[0-9a-f]{64}',data['manifest_sha256']) is not None)
    if request is not None:
        _need(identity['range_id']==request['request_id'] and identity['snapshot_id']==request['snapshot_id'])
        for key in ('symbol','start_time','end_time'): _need(identity[key]==request['arguments'][key])
        _need(data['rows']<=request['arguments']['max_rows'])


def validate_bulk_result(value, request=None, *, max_result_bytes, actual_binding=None):
    _integer(max_result_bytes,2097152); _need(max_result_bytes>0)
    _fields(value,' '.join(tuple(RESULT_DEFAULTS)+('request_id','operation_id','ok','completed_at','result_sha256')))
    _uuid(value['request_id']); _need(value['operation_id']==BULK_OPERATION and type(value['ok']) is bool)
    _need(value['observation'] is None)
    label=value['completed_at']; _need(type(label) is str)
    try:
        moment=datetime.fromisoformat(label.replace('Z','+00:00'))
        _need(moment.tzinfo is not None and moment.utcoffset() is not None)
        _need(moment.astimezone(timezone.utc).isoformat().replace('+00:00','Z')==label)
    except (TypeError,OverflowError): raise ValueError('invalid_bulk_contract') from None
    for key in ('request_admission_ms','result_persistence_ms','response_wakeup_ms','response_handler_ms'):
        _integer(value[key])
    for key in ('queue_wait_ms','execution_ms'):
        if value[key] is not None: _integer(value[key])
    if request is not None: _need(value['request_id']==request['request_id'])
    if value['ok']:
        _need(value['error_code'] is None and value['error_message'] is None)
        _artifact(value['data'],request,actual_binding)
        _need(value['data']['identity']['range_id']==value['request_id'])
    else:
        _need(value['data'] is None and type(value['error_code']) is str and value['error_code'] in ERRORS
              and value['error_message']==MESSAGE)
    unsigned=dict(value); sha=unsigned.pop('result_sha256')
    _need(type(sha) is str and sha==hashlib.sha256(canonical(unsigned)).hexdigest())
    raw=canonical(value); _need(len(raw)<=max_result_bytes)
    return decode(raw)


def make_bulk_result(request_id, *, data=None, error_code=None, completed_at=None, max_result_bytes):
    _uuid(request_id)
    _need((data is not None and error_code is None) or (data is None and error_code in ERRORS))
    if completed_at is None: completed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    result=finalize_result(dict(request_id=request_id,operation_id=BULK_OPERATION,ok=error_code is None,
        data=data,error_code=error_code,error_message=None if error_code is None else MESSAGE,
        completed_at=completed_at),max_result_bytes)
    return validate_bulk_result(result,max_result_bytes=max_result_bytes)
