"""R20认证HTTP的纯交易DTO与编解码；业务执行和持久所有权属于runtime。"""
from dataclasses import dataclass, field
import math
import time

from guanheng_qmt_shm_agent.protocol import ProtocolError, canonical, decode
from guanheng_qmt_shm_agent.trade_clock import CLOCK_SCHEMA, deadline_seconds
from guanheng_qmt_shm_agent.trading_contract import (
    validate_trade_command, command_digest, validate_call_result, _text)
from .bound import (b64, unb64, digest, sha256_text, request_id, binding,
                    metadata_bytes, MAX_METADATA_BYTES)
from .trade_order_links import validate_lookup_identity, ASSOCIATION_ERRORS, _broker


_SUBMIT_FIELDS = ('schema_version', 'binding_sha256', 'command_body_b64',
                  'command_body_sha256', 'clock_schema', 'deadline_ms')
_RECORD_FIELDS = ('schema_version', 'command_id', 'command_sha256', 'body', 'state',
                  'admitted_binding', 'dispatch_binding', 'result_binding',
                  'source_result', 'result_sha256', 'host_reason', 'queued_at',
                  'expires_at', 'started_at')
_EVENT_FIELDS = ('schema_version', 'source', 'after_seq', 'limit', 'max_bytes')
_STATES = ('queued', 'dispatching', 'definitely_not_called', 'sdk_returned', 'unknown')
_HOST_REASONS = ('owner_restarted', 'deadline_expired', 'source_binding_changed',
                 'deadline_unavailable', 'interrupted')
_MAX_SEQUENCE = 2 ** 53 - 1


def _reject():
    raise ProtocolError('invalid bounded trade message') from None


def _fields(value, names):
    if (type(value) is not dict or len(value) != len(names)
            or any(type(key) is not str for key in value) or set(value) != set(names)):
        _reject()


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        _reject()
    return value


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _raw(raw, maximum):
    _integer(maximum, 1, _MAX_SEQUENCE)
    if type(raw) is not bytes or not 1 <= len(raw) <= maximum:
        _reject()
    return decode(raw)


def _command(body, maximum):
    value = validate_trade_command(_raw(body, maximum))
    if canonical(value) != body:
        _reject()
    return value


@dataclass(frozen=True)
class HostTradeRequest:
    """进入线程池前冻结接收时刻；worker只能使用该原I/O截止。"""
    operation: str
    body: bytes = field(default=b'', repr=False)
    command_id: str | None = None
    received_at: float = field(init=False, repr=False)

    def __post_init__(self):
        try:
            received = time.monotonic()
            if not _finite(received) or received < 0:
                _reject()
            if type(self.operation) is not str or type(self.body) is not bytes:
                _reject()
            if self.operation == 'trade.status':
                valid = not self.body and self.command_id is None
            elif self.operation in ('trade.submit', 'trade.events', 'trade.lookup', 'trade.cancel_lookup'):
                valid = bool(self.body) and self.command_id is None
            elif self.operation == 'trade.result':
                if type(self.command_id) is not str:
                    _reject()
                request_id(self.command_id)
                valid = not self.body
            else:
                valid = False
            if not valid:
                _reject()
            object.__setattr__(self, 'received_at', received)
        except (ValueError, TypeError, OverflowError, RecursionError):
            _reject()


def decode_trade_submission(raw, *, max_http_bytes, max_command_bytes):
    """返回封套、原命令bytes与共同契约副本；不读取业务时钟或刷新D。"""
    try:
        _integer(max_command_bytes, 1, _MAX_SEQUENCE)
        value = _raw(raw, max_http_bytes)
        _fields(value, _SUBMIT_FIELDS)
        if value['schema_version'] != 'qmt.trade-submit.v1' or value['clock_schema'] != CLOCK_SCHEMA:
            _reject()
        metadata_bytes(value, 'command_body_b64')
        sha256_text(value['binding_sha256'])
        sha256_text(value['command_body_sha256'])
        body = unb64(value['command_body_b64'], max_command_bytes)
        if digest(body) != value['command_body_sha256']:
            _reject()
        command = _command(body, max_command_bytes)
        deadline_seconds(value['deadline_ms'])
        return value, body, command
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        _reject()


def encode_trade_record(record, *, max_command_bytes, max_result_bytes, control_version='2.0'):
    """只编码已保存记录；HTTP终态不代表柜台已接受或WT已应用。"""
    try:
        _integer(max_command_bytes, 1, _MAX_SEQUENCE)
        _integer(max_result_bytes, 1, _MAX_SEQUENCE)
        _fields(record, _RECORD_FIELDS)
        if (record['schema_version'] != 'qmt.trade-record.v1'
                or type(record['state']) is not str or record['state'] not in _STATES):
            _reject()
        command = _command(record['body'], max_command_bytes)
        if (record['command_id'] != command['command_id']
                or record['command_sha256'] != command_digest(command)):
            _reject()
        admitted = binding(record['admitted_binding'], control_version=control_version)
        dispatched = (None if record['dispatch_binding'] is None else
                      binding(record['dispatch_binding'], control_version=control_version))
        received = (None if record['result_binding'] is None else
                    binding(record['result_binding'], control_version=control_version))
        if ((dispatched is not None and dispatched != admitted)
                or (received is not None and (dispatched is None or received != dispatched))):
            _reject()
        state, reason = record['state'], record['host_reason']
        if (not _finite(record['queued_at']) or not _finite(record['expires_at'])
                or (dispatched is None and record['started_at'] is not None)
                or (dispatched is not None and not _finite(record['started_at']))):
            _reject()
        if ((state == 'queued' and dispatched is not None)
                or (state in ('dispatching', 'sdk_returned', 'unknown') and dispatched is None)):
            _reject()
        source_result = record['source_result']
        if source_result is None:
            if received is not None or record['result_sha256'] is not None:
                _reject()
            if state in ('queued', 'dispatching'):
                if reason is not None:
                    _reject()
            elif (state == 'sdk_returned' or type(reason) is not str or reason not in _HOST_REASONS):
                _reject()
        else:
            source_result = validate_call_result(source_result, command)
            result_raw = canonical(source_result)
            if (len(result_raw) > max_result_bytes or digest(result_raw) != record['result_sha256']
                    or received is None or state != source_result['stage'] or reason is not None):
                _reject()
        value = dict(record)
        value.pop('body')
        value.update(schema_version='qmt.bound-trade.v1', command_body_b64=b64(record['body']),
                     admitted_binding=admitted, dispatch_binding=dispatched,
                     result_binding=received, source_result=source_result)
        metadata_bytes(value, 'command_body_b64')
        raw = canonical(value)
        if len(raw) > 4 * ((max_command_bytes + 2) // 3) + max_result_bytes + MAX_METADATA_BYTES:
            _reject()
        return raw
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        _reject()


def decode_trade_event_request(raw, *, max_http_bytes, max_page_bytes, max_events):
    """校验历史流请求；来源是否实际保留由同一Journal判断，不发源ACK。"""
    try:
        _integer(max_page_bytes, 1, _MAX_SEQUENCE)
        _integer(max_events, 1, _MAX_SEQUENCE)
        value = _raw(raw, max_http_bytes)
        _fields(value, _EVENT_FIELDS)
        if value['schema_version'] != 'qmt.persisted-trade-events-request.v1':
            _reject()
        source = value['source']
        _fields(source, ('host_binding', 'session_id'))
        session = source['session_id']
        if (type(session) is not str or not 1 <= len(session) <= 128 or not session.strip()
                or any(not 32 <= ord(char) < 127 for char in session)):
            _reject()
        source['host_binding'] = binding(source['host_binding'], control_version='2.0')
        _integer(value['after_seq'], 0, _MAX_SEQUENCE)
        _integer(value['limit'], 1, max_events)
        _integer(value['max_bytes'], 1, max_page_bytes)
        # decode只产生新普通值；再规范复制隔离binding返回的任何内部引用。
        return decode(canonical(value))
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        _reject()


def decode_trade_order_lookup(raw, *, max_http_bytes):
    """只接受原 WT 二元身份或完整 token；不接收账户或裸 broker 查询。"""
    try:
        value = _raw(raw, max_http_bytes)
        _fields(value, ('schema_version', 'identity'))
        if value['schema_version'] != 'qmt.trade-order-lookup.v1':
            _reject()
        return validate_lookup_identity(value['identity'])
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        _reject()


def encode_trade_order_reference(reference, *, max_command_bytes, max_result_bytes, control_version='2.0'):
    """编码原 insert 及实际观察来源；关联成功不代表 WT 已应用或当前可撤。"""
    try:
        names = ('schema_version', 'insert', 'broker_order_id', 'source',
            'source_sequence', 'source_event_sha256', 'association_error')
        is_query = reference.get('schema_version') == 'qmt.trade-order-reference.v2'
        _fields(reference, names + (('query_observation',) if is_query else ()))
        if reference['schema_version'] not in ('qmt.trade-order-reference.v1', 'qmt.trade-order-reference.v2'):
            _reject()
        original = reference['insert']
        command = _command(original['body'], max_command_bytes)
        if command['operation'] != 'order.insert':
            _reject()
        insert = decode(encode_trade_record(original, max_command_bytes=max_command_bytes,
            max_result_bytes=max_result_bytes, control_version=control_version))
        proof = [reference[k] for k in ('source', 'source_sequence', 'source_event_sha256')]
        if any(v is None for v in proof) and not all(v is None for v in proof):
            _reject()
        if not is_query and (reference['broker_order_id'] is None) != (proof[0] is None):
            _reject()
        if reference['broker_order_id'] is not None and _broker(reference['broker_order_id']) != reference['broker_order_id']:
            _reject()
        source = reference['source']
        if source is not None:
            if _broker(reference['broker_order_id']) != reference['broker_order_id']:
                _reject()
            _fields(source, ('host_binding', 'session_id'))
            _text(source['session_id'], 128, 'invalid_command', True)
            source = {'host_binding': binding(source['host_binding'], control_version=control_version),
                      'session_id': source['session_id']}
            _integer(reference['source_sequence'], 1, _MAX_SEQUENCE)
            sha256_text(reference['source_event_sha256'])
        if is_query:
            observation = reference['query_observation']
            _fields(observation, ('request_id', 'result_sha256', 'row_index', 'host_binding'))
            request_id(observation['request_id']); sha256_text(observation['result_sha256'])
            _integer(observation['row_index'], 0, 4095)
            binding(observation['host_binding'], control_version=control_version)
            if original['dispatch_binding'] is None:
                _reject()
            if reference['broker_order_id'] is None and reference['association_error'] is None:
                _reject()
        if reference['association_error'] not in ASSOCIATION_ERRORS | {None}:
            _reject()
        value = dict(reference, insert=insert, source=source)
        raw = canonical(value)
        if (len(raw) - len(insert['command_body_b64']) > MAX_METADATA_BYTES
                or len(raw) > 4 * ((max_command_bytes + 2) // 3) + max_result_bytes + MAX_METADATA_BYTES):
            _reject()
        return raw
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        _reject()


def decode_trade_cancel_lookup(raw, *, max_http_bytes):
    """只读目标取消恢复；只接受原insert UUID/SHA，不接受准入或别名字段。"""
    try:
        value = _raw(raw, max_http_bytes)
        _fields(value, ('schema_version', 'original_command_id', 'original_command_sha256'))
        if value['schema_version'] != 'qmt.trade-cancel-lookup.v1':
            _reject()
        request_id(value['original_command_id'])
        sha256_text(value['original_command_sha256'])
        return dict(value)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        _reject()


def encode_trade_cancel_reference(reference, *, max_command_bytes, max_result_bytes, control_version='2.0'):
    """返回实际原cancel记录；null只表示当前无记录，不追认其他请求成功。"""
    try:
        _fields(reference, ('schema_version','original_command_id','original_command_sha256','cancel'))
        if reference['schema_version'] != 'qmt.trade-cancel-reference.v1':
            _reject()
        request_id(reference['original_command_id']); sha256_text(reference['original_command_sha256'])
        cancel = reference['cancel']
        if cancel is not None:
            command = _command(cancel['body'], max_command_bytes)
            if (command['operation'] != 'order.cancel'
                    or command['original_command_id'] != reference['original_command_id']):
                _reject()
            cancel = decode(encode_trade_record(cancel, max_command_bytes=max_command_bytes,
                max_result_bytes=max_result_bytes, control_version=control_version))
        raw = canonical(dict(reference, cancel=cancel))
        if len(raw) > 4*((max_command_bytes+2)//3) + max_result_bytes + 2*MAX_METADATA_BYTES:
            _reject()
        return raw
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        _reject()
