"""终端外持久消费方；原 ID 先落盘，完整原结果落盘后才确认消费。"""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
from uuid import uuid4
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_capabilities import validate_read_profile, validate_read_request
from guanheng_qmt_shm_agent.read_retention import (retention, content_id, validate_identity,
    now_ms, TICKET, ENVELOPE, LOOKUP, CONSUMED, result_confirmed)
from . import bound
from .bulk_clock import WindowsBulkUptimeClock


class RetainedReadPending(RuntimeError):
    """原责任尚未确认；沿同一 slot/ID 继续查询，调用方保留发布旧值。"""


class RetainedReadFailure(RuntimeError):
    """已保存明确受理拒绝或确定原终态失败；后续观察归业务 owner 决定。"""


class RetainedReadBindingChanged(RetainedReadFailure):
    """新请求尚未受理或旧责任已确认，完整来源身份与业务capture不同。"""


def _save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 同目录短UUID临时名保留128位唯一性；不重复长SHA目的名，避免有效目的路径的临时名越过Windows路径预算。
    temporary = path.with_name('.' + uuid4().hex + '.tmp')
    raw = canonical(value)
    with temporary.open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('read receipt write incomplete')
        stream.flush()
        os.fsync(stream.fileno())
    _replace_receipt(temporary, path)


def _replace_receipt(candidate, target):
    """单写者提交完整临时回执；共享删除读者可持有原完整快照。

    Windows MoveFileEx（os.replace）仍会与打开的旧目标冲突；已有目标沿
    ReplaceFileW提交。首次发布独占rename，单写者冲突直接交还调用方。
    失败保留原异常、原目标及临时文件，原请求身份和业务截止保持。
    """
    try:
        os.lstat(target)
    except FileNotFoundError:
        os.rename(candidate, target)
        return
    if os.name != 'nt':
        os.replace(candidate, target)
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.ReplaceFileW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
    kernel.ReplaceFileW.restype = wintypes.BOOL
    if not kernel.ReplaceFileW(os.fspath(target), os.fspath(candidate), None, 0, None, None):
        raise ctypes.WinError(ctypes.get_last_error())


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _validate_saved_record(record, operation, arguments):
    request = record['request']
    if request['operation_id'] != operation or request['arguments'] != arguments:
        raise ValueError('retained_read_original_request_changed')
    raw = canonical(request)
    if bound.digest(raw) != record['request_body_sha256']:
        raise ValueError('retained_read_original_bytes_changed')
    validate_identity(request, record['ticket'])
    validate_read_request(request, record['profile'], max_result_bytes=record['limits']['max_result_bytes'])
    if (bound.binding(record['binding']) != record['binding']
            or bound.digest(canonical(record['profile'])) != record['binding']['capability_sha256']
            or record['ticket']['epoch'] != record['binding']['host_instance_id']):
        raise ValueError('retained_read_original_source_changed')
    retention(record['profile'].get('read_retention'))
    return raw


def _validate_saved_result(record, value):
    bound.validate_response(value, max_result_bytes=record['limits']['max_result_bytes'], request=record['request'])
    if (value['request_body_sha256'] != record['request_body_sha256']
            or value['admitted_binding'] != record['binding']):
        raise ValueError('retained_read_result_source_changed')


def inspect_saved_result(record):
    """只读核验已消费原结果；未知返回None，损坏显式失败，无网络、确认或文件写入。

    沿原read相同的请求/票据、profile、绑定、完整响应及业务投影校验，返回原reply。
    consumed仅表示完整结果已交接；是否成功、SDK是否已返回和数据覆盖由业务owner判断。
    本函数不以当前Source代际/时钟替换原身份，未消费原件保持原owner责任。
    """
    if type(record) is not dict:
        raise ValueError('retained_read_saved_record_invalid')
    if set(record)=={'request'}:
        # 原有仅请求登记没有执行证明；保持未知保护，不具备解除责任的资格。
        return None
    request = record['request']
    _validate_saved_record(record, request['operation_id'], request['arguments'])
    value = record.get('result')
    if value is not None:
        _validate_saved_result(record, value)
    if record.get('consumed') is not True:
        return None
    if type(value) is not dict or value.get('state') != 'terminal':
        raise ValueError('retained_read_consumed_without_terminal')
    return decode(bound.unb64(value['result_body_b64'], record['limits']['max_result_bytes']))


class RetainedReadClient:
    """transport 沿现有 exchange/plan/rpc_budget；本类不创建线程或 SDK。

    一个 slot 永远对应一个原请求。业务产生下一次观察时使用新 slot；
    本类只续核尚未确认的原 ID。调用方持有并归档 slot 中的完整原结果。
    一个客户端及其原运输由一个调用线程持有；并行读取使用独立客户端。
    """
    def __init__(self, transport, *, clock=None, lifetime_ms=3000, poll_seconds=.02, wait_for_active_capacity=False):
        if (not callable(getattr(transport, 'exchange', None)) or not callable(getattr(transport, 'plan', None))
                or not callable(getattr(transport, 'rpc_budget', None))
                or type(lifetime_ms) is not int or not 100 <= lifetime_ms <= 300000
                or type(wait_for_active_capacity) is not bool
                or type(poll_seconds) not in (int, float) or not .001 <= poll_seconds <= 1):
            raise ValueError('explicit retained read transport and finite budgets required')
        self.transport, self.clock = transport, WindowsBulkUptimeClock() if clock is None else clock
        self.lifetime_ms, self.poll_seconds = lifetime_ms, poll_seconds
        self.wait_for_active_capacity = wait_for_active_capacity

    def _binding(self, deadline, *, require_retention=True):
        code, value = self.transport.exchange('GET', '/internal/v1/read-binding', b'', deadline)
        if code != 200:
            raise RetainedReadPending('read_source_waiting')
        checked = bound.binding(value['binding'])
        raw = bound.unb64(value['read_profile_body_b64'], 4096)
        if (value['schema_version'] != bound.SCHEMA or value['order_ready'] is not False
                or bound.digest(canonical(checked)) != value['binding_sha256']
                or bound.digest(raw) != value['read_profile_body_sha256']
                or bound.digest(raw) != checked['capability_sha256']):
            raise ValueError('retained_read_binding')
        profile = validate_read_profile(decode(raw), max_result_bytes=value['limits']['max_result_bytes'])
        if require_retention:
            retention(profile.get('read_retention'))
        return dict(value, profile=profile)

    def metadata(self, *, deadline):
        """只读已认证能力metadata；缺少新能力时消费方可明确等待，不生成请求或slot。"""
        with self._rpc_budget(deadline):
            return self._binding(deadline, require_retention=False)

    @contextmanager
    def _rpc_budget(self, deadline):
        """读取与准入等待共用逐I/O预算和运输未知转换；同一绝对D保持。"""
        try:
            with self.transport.rpc_budget(min(30., max(.1, deadline-time.monotonic()))):
                yield
        except RuntimeError as exc:
            # 原transport的Pending保留网络未知；协议/数据错误继续显式失败。
            if type(exc).__name__ != 'SourcePending':
                raise
            import http.client
            if isinstance(exc.__context__, http.client.HTTPException) and not isinstance(exc.__context__, OSError):
                raise ValueError('retained_read_http_protocol') from None
            raise RetainedReadPending('read_transport_unresolved') from None

    def wait_capacity(self, deadline):
        """新准入及明确503后的容量等待；只查询元数据，不生成或重交请求。"""
        with self._rpc_budget(deadline):
            self._wait_capacity(deadline)

    def _wait_capacity(self, deadline):
        while time.monotonic() < deadline:
            code, value = self.transport.exchange('GET', '/internal/v1/read-retention-status', b'', deadline)
            if code != 200:
                # 显式批准备模式可等Host认证nonce容量自然释放；该拒绝发生在
                # 应用/Journal准入之前。原容量、认证及同一绝对D均保持。
                if (self.wait_for_active_capacity and code == 503
                        and value.get('error_code') == 'nonce_cache_full'):
                    time.sleep(min(self.poll_seconds, max(0, deadline-time.monotonic())))
                    continue
                raise RetainedReadPending('read_retention_capacity_unavailable')
            if value['retained'] < value['capacity']:
                return
            # MDP可在原准入D内等待正常在途/消费；未知责任始终立即交回原owner。
            # 默认消费者保持原即刻Pending行为，不改变票据或SDK截止。
            if value['held_unknown'] or (not self.wait_for_active_capacity and
                    (value['awaiting_consumer'] or value['queued_or_running'])):
                raise RetainedReadPending('read_retention_held_responsibility')
            time.sleep(min(self.poll_seconds, max(0, deadline-time.monotonic())))
        raise RetainedReadPending('read_retention_awaiting_ticket_end')

    def _validate_record(self, record, operation, arguments):
        return _validate_saved_record(record, operation, arguments)

    def _result(self, record, value):
        _validate_saved_result(record, value)

    def read(self, operation, arguments, slot, *, deadline, expected_binding=None, minimum_new_request_seconds=0, new_request_observation_deadline=None):
        """minimum_new_request_seconds为新槽准入所需外部剩余秒数；默认0保持旧消费者；new_request_observation_deadline为外部单调截止秒值，缺省沿deadline，已有槽不受新准入门限影响。"""
        slot = Path(slot)
        if expected_binding is not None:
            expected_binding = bound.binding(expected_binding)
        try:
            with self._rpc_budget(deadline):
                if slot.exists():
                    record = json.loads(slot.read_bytes())
                else:
                    # 只有尚未准入的新观察才受余量限制；没有生成ID、票据或slot时可正常暂停。
                    observation_deadline=deadline if new_request_observation_deadline is None else new_request_observation_deadline
                    if minimum_new_request_seconds and observation_deadline-time.monotonic() < minimum_new_request_seconds:
                        raise RetainedReadPending('read_new_request_budget_exhausted')
                    self._wait_capacity(deadline)
                    # 新slot是一项新观察，必须准入当前认证；父目录BINDING归业务owner，
                    # 保留其原值用于整次capture一致性，不能拿它替代当前Host身份。
                    metadata = self._binding(deadline)
                    if expected_binding is not None and metadata['binding'] != expected_binding:
                        raise RetainedReadBindingChanged('read_source_binding_changed')
                    # 当前绑定/容量核验可能消耗观察时间，生成原SDK正文前再次检查完整余量。
                    if minimum_new_request_seconds and observation_deadline-time.monotonic() < minimum_new_request_seconds:
                        raise RetainedReadPending('read_new_request_budget_exhausted')
                    record = self.transport.plan(operation, arguments, metadata, deadline)
                    capability = retention(record['profile'].get('read_retention'))
                    expires = now_ms(self.clock) + min(self.lifetime_ms, capability['max_lifetime_ms'])
                    if operation == 'market.history_prepare':
                        expires = arguments['deadline_ms']
                    record['ticket'] = dict(schema=TICKET, epoch=record['binding']['host_instance_id'], expires_ms=expires)
                    record['request']['request_id'] = content_id(record['request'], record['ticket'])
                    record['request_body_sha256'] = bound.digest(canonical(record['request']))
                    record.update(requested_at=_utc(), received_at=None, consumed=False)
                    _save(slot, record)
                raw = self._validate_record(record, operation, arguments)
                rid = record['request']['request_id']
                rejected = record.get('admission_rejection')
                if rejected is not None:
                    if (type(rejected) is not dict or set(rejected) != {'schema','request_id','request_body_sha256',
                            'status','error_code','observed_at'} or rejected['schema'] != 'qmt.read-admission-rejection.v1'
                            or rejected['request_id'] != rid or rejected['request_body_sha256'] != record['request_body_sha256']
                            or rejected['status'] != 400 or rejected['error_code'] not in ('invalid_arguments','read_ticket_ended')
                            or type(rejected['observed_at']) is not str or record['result'] is not None):
                        raise ValueError('retained_read_admission_rejection_identity')
                    raise RetainedReadFailure('read_admission_rejected')
                if record['result'] is None:
                    if not record['attempted']:
                        record['attempted'] = True
                        _save(slot, record)
                        body = canonical(dict(schema_version=ENVELOPE,
                            binding_sha256=bound.digest(canonical(record['binding'])), ticket=record['ticket'],
                            request_body_b64=bound.b64(raw), request_body_sha256=bound.digest(raw)))
                        code, value = self.transport.exchange('POST', '/internal/v1/bound-operations/'+operation, body, deadline)
                        if code == 400 and value.get('error_code') in ('invalid_arguments','read_ticket_ended'):
                            # Host 已明确拒绝本次受理；保存独立事实，不把无终态伪装为原生结果。
                            record['admission_rejection'] = dict(schema='qmt.read-admission-rejection.v1',
                                request_id=rid,request_body_sha256=record['request_body_sha256'],status=400,
                                error_code=value['error_code'],observed_at=_utc())
                            _save(slot,record)
                            raise RetainedReadFailure('read_admission_rejected')
                        # 明确受理前容量拒绝允许原身份重交；通信未知始终保持 attempted。
                        if code == 503 and (value.get('error_code') in ('queue_full', 'read_retention_capacity_exhausted')
                                or self.wait_for_active_capacity and value.get('error_code') == 'nonce_cache_full'):
                            record['attempted'] = False
                            _save(slot, record)
                            raise RetainedReadPending('read_retention_capacity_rejected')
                    else:
                        lookup = canonical(dict(schema=LOOKUP, ticket=record['ticket'],
                            request_body_b64=bound.b64(raw), request_body_sha256=bound.digest(raw)))
                        code, value = self.transport.exchange('POST', '/internal/v1/read-results/'+rid+'/lookup', lookup, deadline)
                    while True:
                        if code not in (200, 202):
                            raise RetainedReadPending('read_original_request_unresolved')
                        self._result(record, value)
                        if value['state'] == 'terminal':
                            record.update(result=value, received_at=_utc())
                            # FULL 原结果先落盘；此行失败时绝不发送 consumed。
                            _save(slot, record)
                            break
                        if time.monotonic()+self.poll_seconds >= deadline:
                            raise RetainedReadPending('read_original_request_pending')
                        time.sleep(self.poll_seconds)
                        code, value = self.transport.exchange('GET', '/internal/v1/bound-results/'+rid, b'', deadline)
                self._result(record, record['result'])
                if record['consumed'] is not True:
                    ack = canonical(dict(schema=CONSUMED, request_body_sha256=record['request_body_sha256'],
                        result_body_sha256=record['result']['result_body_sha256']))
                    code, value = self.transport.exchange('POST', '/internal/v1/read-results/'+rid+'/consumed', ack, deadline)
                    if code == 200:
                        if (value.get('schema') != 'qmt.read-consumed-result.v1' or value.get('request_id') != rid
                                or value.get('consumed') is not True):
                            raise ValueError('retained_read_consumed_receipt')
                    elif code != 410 or value.get('error_code') != 'read_result_unretained':
                        raise RetainedReadPending('read_consumption_unconfirmed')
                    record['consumed'] = True
                    _save(slot, record)
                reply = decode(bound.unb64(record['result']['result_body_b64'], record['limits']['max_result_bytes']))
                if reply['ok'] is not True:
                    if not result_confirmed(reply):
                        raise RetainedReadPending('read_original_terminal_unknown')
                    raise RetainedReadFailure('read_original_terminal_failure')
                # 旧slot先完成原ID/原结果的责任交接；未知路径在此前已返回Pending。
                # 确认后才允许业务owner因来源换代放弃该capture，原slot仍完整保留。
                if expected_binding is not None and record['binding'] != expected_binding:
                    raise RetainedReadBindingChanged('read_source_binding_changed')
                return dict(request_id=rid, requested_at=record['requested_at'], received_at=record['received_at'], reply=reply)
        except (RetainedReadPending, RetainedReadFailure):
            raise

    def prepare(self, operation, arguments, slot, *, deadline, expected_binding=None, minimum_new_request_seconds=0, new_request_observation_deadline=None):
        """HPR 与普通读取共用原身份和结果持久交接，不生成重试请求。"""
        if operation != 'market.history_prepare':
            raise ValueError('history preparation operation required')
        return self.read(operation, arguments, slot, deadline=deadline, expected_binding=expected_binding,
            minimum_new_request_seconds=minimum_new_request_seconds,
            new_request_observation_deadline=new_request_observation_deadline)
