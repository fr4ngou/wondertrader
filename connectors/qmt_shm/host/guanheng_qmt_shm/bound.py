"""QSW认证只读外层DTO；原请求/终态字节由原owner保存。

外层只关联通信来源，不授账户、历史、券商会话或交易资格。所有公开
入口使用同一有界JSON/base64准入；完整profile只按原字节校验摘要。
"""
from __future__ import annotations
import base64
import hashlib
import re
from uuid import UUID
from guanheng_qmt_shm_agent.control_messages import validate_host_binding
from guanheng_qmt_shm_agent.protocol import ProtocolError, canonical, decode
from guanheng_qmt_shm_agent.read_capabilities import (validate_read_request,
    validate_read_result_projection)

SCHEMA = 'qmt.bound-read.v1'
MAX_BINDING_BYTES = 4096
MAX_PROFILE_BYTES = 4096
MAX_REQUEST_BYTES = 65536
MAX_METADATA_BYTES = 16384


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ProtocolError('invalid SHA256 identity')
    return value


def request_id(value):
    if not isinstance(value, str) or len(value)!=36:
        raise ProtocolError('invalid request identity')
    try:
        if str(UUID(value)) != value:
            raise ValueError('noncanonical UUID')
    except (ValueError, TypeError, AttributeError):
        raise ProtocolError('invalid request identity') from None
    return value


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


def unb64(value, maximum):
    if (not isinstance(value,str) or not value or len(value) > 4*((maximum+2)//3)
            or not re.fullmatch(r'[A-Za-z0-9+/]*={0,2}',value)):
        raise ProtocolError('invalid bounded base64')
    try:
        data=base64.b64decode(value,validate=True)
    except ValueError:
        raise ProtocolError('invalid bounded base64') from None
    if len(data)>maximum or b64(data)!=value:
        raise ProtocolError('noncanonical bounded base64')
    return data


def binding(value, *, control_version='1.0'):
    try:
        raw=canonical(value)
        if len(raw)>MAX_BINDING_BYTES or not isinstance(value,dict):
            raise ProtocolError('binding exceeds capacity')
        if value.get('journal_generation') is not None or value.get('observation_identity') is not None:
            raise ProtocolError('unsupported read binding owner')
        sha256_text(value.get('capability_sha256'))
        checked=validate_host_binding(value, route=value.get('route'), generation=value.get('transport_generation'),
            capability_sha256=value.get('capability_sha256'), observation_identity=None,
            schema_version=control_version)
        return checked
    except (TypeError, KeyError, RecursionError, UnicodeError, ValueError):
        raise ProtocolError('invalid read binding') from None


def metadata_bytes(value, body_field):
    """计入完整metadata编码，只有base64字符体从联合大小中分开计量。"""
    raw=canonical(value)
    body=value.get(body_field)
    size=len(raw)-(len(body) if isinstance(body,str) else 0)
    if size>MAX_METADATA_BYTES:
        raise ProtocolError('bound metadata exceeds capacity')
    return raw


def decode_submission(raw, *, max_http_bytes, max_request_bytes, profile, operation, max_result_bytes=None):
    if not isinstance(raw,bytes) or len(raw)>max_http_bytes:
        raise ProtocolError('bound HTTP request exceeds capacity')
    value=decode(raw)
    fields={'schema_version','binding_sha256','request_body_b64','request_body_sha256'}
    if (not isinstance(value,dict) or not fields <= set(value) <= fields|{'execution_deadline_uptime_ms'}
            or value['schema_version']!=SCHEMA):
        raise ProtocolError('invalid bound read request')
    metadata_bytes(value,'request_body_b64')
    sha256_text(value['binding_sha256']);sha256_text(value['request_body_sha256'])
    body=unb64(value['request_body_b64'],max_request_bytes)
    if digest(body)!=value['request_body_sha256']:
        raise ProtocolError('request byte identity differs')
    request=decode(body)
    validate_read_request(request,profile,max_result_bytes=max_result_bytes)
    if request['operation_id']!=operation:
        raise ProtocolError('request path differs')
    if 'execution_deadline_uptime_ms' in value:
        end=value['execution_deadline_uptime_ms']
        # 此绝对毫秒只约束Host首次排队；不进入原SDK正文或重写来源能力。
        if operation!='account.trade_detail' or type(end)is not int or not 1<=end<=2**53-1:
            raise ProtocolError('invalid original account read deadline')
    return value,body,request


def limits(*, max_frame, max_result_bytes, native_body_limit):
    return {'max_request_bytes':min(MAX_REQUEST_BYTES,(max_frame-4096)*3//4,native_body_limit),
        'max_result_bytes':max_result_bytes,'max_http_request_bytes':max_frame,
        'max_http_response_bytes':4*((max_result_bytes+2)//3)+MAX_METADATA_BYTES}


def validate_response(value, *, max_result_bytes, control_version='1.0', request=None, result_projection=None):
    fields={'schema_version','request_id','operation_id','request_sha256','request_body_sha256',
        'binding_status','admitted_binding','dispatch_binding','result_binding','state',
        'result_body_b64','result_body_sha256'}
    if (not isinstance(value,dict) or set(value)!=fields or value['schema_version']!=SCHEMA
            or not isinstance(value['operation_id'],str) or not value['operation_id']
            or value['state'] not in ('queued','executing','terminal')
            or value['binding_status'] not in ('recorded','legacy_unqualified')):
        raise ProtocolError('invalid bound result envelope')
    request_id(value['request_id']);sha256_text(value['request_sha256'])
    if value['request_body_sha256'] is not None:
        sha256_text(value['request_body_sha256'])
    a,d,r=(value[k] for k in ('admitted_binding','dispatch_binding','result_binding'))
    if value['binding_status']=='legacy_unqualified':
        if a is not None or d is not None or r is not None:
            raise ProtocolError('legacy record cannot acquire a current binding')
    else:
        binding(a,control_version=control_version)
        if value['request_body_sha256'] is None:
            raise ProtocolError('recorded request needs original byte identity')
        if d is not None and binding(d,control_version=control_version)!=a:
            raise ProtocolError('dispatch binding differs from admission')
        if r is not None and (d is None or binding(r,control_version=control_version)!=d):
            raise ProtocolError('result binding differs from dispatch')
        if value['state']=='queued' and (d is not None or r is not None):
            raise ProtocolError('queued record cannot claim dispatch/result')
        if value['state']=='executing' and (d is None or r is not None):
            raise ProtocolError('executing record has invalid channel provenance')
    metadata_bytes(value,'result_body_b64')
    if value['state']!='terminal':
        if value['result_body_b64'] is not None or value['result_body_sha256'] is not None:
            raise ProtocolError('pending record cannot have terminal bytes')
        return value
    sha256_text(value['result_body_sha256'])
    raw=unb64(value['result_body_b64'],max_result_bytes)
    if digest(raw)!=value['result_body_sha256']:
        raise ProtocolError('terminal byte identity differs')
    result=decode(raw)
    if (not isinstance(result,dict) or result.get('request_id')!=value['request_id']
            or result.get('operation_id')!=value['operation_id'] or type(result.get('ok')) is not bool):
        raise ProtocolError('inner native identity differs')
    unsigned=dict(result);sha=unsigned.pop('result_sha256',None)
    sha256_text(sha)
    if digest(canonical(unsigned))!=sha:
        raise ProtocolError('inner native content identity differs')
    if request is not None:
        if (request['request_id'] != result['request_id']
                or request['operation_id'] != result['operation_id']):
            raise ProtocolError('terminal differs from original native request')
        # 校验器由可信owner注入；wire字段不能选择或放宽结果合同。
        projection=validate_read_result_projection if result_projection is None else result_projection
        projection(request, result)
    return value
