"""同一 Host 读/交易运行 owner；源事实与通信持久状态共同决定写就绪。

HTTP 线程只提交原命令；唯一 I/O/域 worker 负责派发和持久回报。
关闭先停业务准入，再让已有交接沿首次截止完成，最后释放原父类资源。
"""
from __future__ import annotations

import math
import sqlite3
import time

from guanheng_qmt_shm_agent.protocol import ProtocolError, canonical, decode
from guanheng_qmt_shm_agent.trade_clock import deadline_seconds
from guanheng_qmt_shm_agent.trade_capabilities import SOURCE_STATUS_V1, SOURCE_STATUS_V2
from .bound import binding, digest, b64, MAX_METADATA_BYTES
from .control_trading import HostTradingControlLoop
from .journal import JournalConflict, JournalFull
from .runtime import HostReadRuntime, HostResponse, response
from .trade_bound import (HostTradeRequest, decode_trade_submission,
    encode_trade_record, decode_trade_event_request, decode_trade_order_lookup,
    encode_trade_order_reference, decode_trade_cancel_lookup, encode_trade_cancel_reference)
from .trading_journal import CancelPending
from .trade_order_links import OrderSourceUnavailable
from .trade_event_records import validate_trade_event_storage, CONTINUITY_VERSION
from .trade_status import validate_source_status


def _error(status, code):
    return response(status, {'error_code': code,
        'error_message': '交易接入请求未完成；请保留原命令标识查询结果'})


class HostTradingRuntime(HostReadRuntime):
    """显式 v4 运行器；不创建第二套运输、存储 owner 或资格审批。"""
    trade_requests_enabled = True

    def __init__(self, journal, *, writes_enabled, event_storage,
                 event_poll_seconds, business_clock, connection_continuity=None, **kwargs):
        if type(writes_enabled) is not bool or not callable(business_clock):
            raise ValueError('explicit trade deployment switch and clock required')
        storage, limits, unused, profile_sha = validate_trade_event_storage(
            journal.admission_profile, journal.trade_binding, event_storage,
            max_result_bytes=journal.max_result_bytes)
        if journal.events is None:
            raise ValueError('explicit event communication storage required')
        if (connection_continuity not in (None, CONTINUITY_VERSION)
                or journal.events.connection_continuity != connection_continuity):
            raise ValueError('explicit event connection continuity differs from Journal')
        self._connection_continuity = connection_continuity
        # 与 Journal 同次事件配置，禁止 runtime 在已开库身份外另选保留额度。
        if journal.events.storage != storage:
            raise ValueError('runtime event storage differs from Journal')
        super().__init__(journal, **kwargs)
        if (type(event_poll_seconds) not in (int, float) or not math.isfinite(event_poll_seconds)
                or not .01 <= event_poll_seconds <= min(60, self.control_profile.max_call_seconds)):
            raise ValueError('invalid explicit trade event poll interval')
        maximum = max(journal.max_result_bytes + MAX_METADATA_BYTES,
            limits['max_call_result_bytes'] + MAX_METADATA_BYTES,
            4 * ((limits['max_command_bytes'] + 2) // 3) + MAX_METADATA_BYTES,
            4 * ((storage['max_page_bytes'] + 2) // 3) + MAX_METADATA_BYTES)
        if maximum > 4194304 or digest(self._profile_bytes) != profile_sha:
            raise ValueError('trade domain payload or profile differs')
        self._trade_limits_bytes, self._event_storage_bytes = canonical(limits), canonical(storage)
        self._writes_enabled = writes_enabled
        self._business_clock = business_clock
        self._event_poll_seconds = float(event_poll_seconds)
        self._source_status_bytes = None
        self._trade_session = None
        self._trade_unknown = None
        self._trade_problem = None
        self._trade_hard_fault = None
        self._stream_checked = False

    @property
    def trade_limits(self):
        return decode(self._trade_limits_bytes)

    @property
    def event_storage(self):
        return decode(self._event_storage_bytes)

    @property
    def event_poll_seconds(self):
        return self._event_poll_seconds

    @property
    def writes_enabled(self):
        return self._writes_enabled

    @property
    def connection_continuity(self):
        """只由新常驻产品显式选择，原默认认证绑定严格路径保持。"""
        return self._connection_continuity

    def business_seconds(self):
        try:
            value = self._business_clock()
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError()
            return value
        except Exception:
            with self._binding_lock:
                self._trade_hard_fault = self._trade_hard_fault or 'clock_unavailable'
            raise ValueError('shared business clock unavailable') from None

    def _make_control(self, session, actual_binding):
        return HostTradingControlLoop(self, session, actual_binding)

    def _interrupt_control(self):
        # 两条原身份均须收尾；一条通知失败不能跳过另一条。
        first = None
        for notify in (self._control.interrupt_trade, self._control.interrupt_read):
            try:
                notify()
            except BaseException as error:
                if first is None:
                    first = error
                elif error is not first:
                    first.__cause__ = error
        if first is not None:
            raise first

    def _finalize_control(self):
        # runtime finally已撤准入；只有原I/O能在关闭domain前完成交易交接。
        if self._control is not None:
            self._control.finalize_interrupt()

    def validate_source_status(self, value):
        private = self.journal.trade_binding
        return validate_source_status(value, binding_id=private['binding_id'],
            binding_sha256=self.profile['trade_profile']['binding_sha256'],
            writes_enabled=self.writes_enabled, limits=self.trade_limits)

    def _operation_admission_locked(self, operation):
        if operation not in ('order.insert', 'order.cancel'):
            return False
        if (not self.connected.is_set() or self.admission_stopped or self._binding_bytes is None
                or not self.writes_enabled or self.failure is not None
                or not self._stream_checked or self._trade_unknown is None
                or self._trade_hard_fault is not None or self._trade_problem is not None
                or self._source_status_bytes is None):
            return False
        status = decode(self._source_status_bytes)
        if (status['events']['closed'] or status['closing'] or status['gap'] is not None
                or status.get('hard_fault') is not None):
            return False
        if operation == 'order.cancel' and status['schema_version'] == SOURCE_STATUS_V2:
            return status['cancel_admission']
        return status['write_admission'] and self._trade_unknown is False

    def _accepting_locked(self):
        return self._operation_admission_locked('order.insert')

    @property
    def accepting_cancels(self):
        with self._binding_lock:
            return self._operation_admission_locked('order.cancel')

    def _observe_admission_locked(self, facts):
        if (type(facts) is not dict or set(facts) != {'unknown_fenced', 'hard_fault'}
                or type(facts['unknown_fenced']) is not bool):
            raise ProtocolError('invalid trade admission observation')
        hard = facts['hard_fault']
        if hard is not None:
            if (type(hard) is not dict or set(hard) != {'code'} or type(hard['code']) is not str
                    or not 1 <= len(hard['code']) <= 128
                    or any(not 32 <= ord(c) < 127 for c in hard['code'])):
                raise ProtocolError('invalid trade hard fault observation')
            if self._trade_hard_fault is None:
                self._trade_hard_fault = hard['code']
        self._trade_unknown = self._trade_unknown is True or facts['unknown_fenced']

    @property
    def accepting_commands(self):
        with self._binding_lock:
            return self._accepting_locked()

    def observe_source(self, status, receipt, facts, *, continuity=None):
        checked = self.validate_source_status(status)
        with self._binding_lock:
            if self._binding_bytes is None:
                raise ProtocolError('trade observation lacks authenticated binding')
            if self._trade_session is not None and self._trade_session != checked['session_id']:
                raise ProtocolError('source trade session changed')
            if (self._source_status_bytes is not None
                    and decode(self._source_status_bytes)['schema_version'] != checked['schema_version']):
                raise ProtocolError('source trade status version changed')
            if receipt is None:
                durable = 0
            else:
                fields = {'schema_version', 'session_id', 'binding_id', 'host_binding_sha256',
                    'durable_through', 'ack_intended_through', 'source_ack_through',
                    'observed_published_through', 'gap'}
                if (type(receipt) is not dict or set(receipt) != fields
                        or receipt['schema_version'] != 'qmt.trade-event-receipt.v1'
                        or receipt['session_id'] != checked['session_id']
                        or receipt['binding_id'] != checked['binding_id']):
                    raise ProtocolError('trade receipt identity differs')
                expected = digest(self._binding_bytes)
                if self.connection_continuity is not None:
                    # 证明来自原domain对附属关系的查询；旧receipt仍引用创世binding，原字节不改。
                    keys = {'schema_version', 'session_id', 'binding_id', 'current_host_binding_sha256',
                            'origin_host_binding_sha256', 'authenticated'}
                    if (type(continuity) is not dict or set(continuity) != keys
                            or continuity['schema_version'] != 'qmt.trade-source-continuity.v1'
                            or continuity['session_id'] != checked['session_id']
                            or continuity['binding_id'] != checked['binding_id']
                            or continuity['current_host_binding_sha256'] != expected
                            or continuity['origin_host_binding_sha256'] != receipt['host_binding_sha256']
                            or continuity['authenticated'] is not True):
                        raise ProtocolError('trade receipt connection continuity differs')
                elif receipt['host_binding_sha256'] != expected:
                    raise ProtocolError('trade receipt identity differs')
                frontiers = [receipt[key] for key in ('source_ack_through',
                    'ack_intended_through', 'durable_through', 'observed_published_through')]
                if (any(type(value) is not int or not 0 <= value <= 2**53-1 for value in frontiers)
                        or not frontiers[0] <= frontiers[1] == frontiers[2] <= frontiers[3]):
                    raise ProtocolError('trade receipt frontier differs')
                durable = receipt['durable_through']
            if checked['events']['acknowledged_through'] > durable:
                raise ProtocolError('source acknowledged beyond Host durable prefix')
            previous = self._operation_admission_locked('order.cancel')
            self._trade_session = checked['session_id']
            self._source_status_bytes = canonical(checked)
            self._stream_checked = True
            self._observe_admission_locked(facts)
            if checked['schema_version'] == SOURCE_STATUS_V2:
                self._observe_admission_locked({key: checked[key] for key in ('unknown_fenced','hard_fault')})
            if checked['gap'] is not None or receipt is not None and receipt['gap'] is not None:
                self._trade_problem = self._trade_problem or 'source_gap'
                self._trade_hard_fault = self._trade_hard_fault or 'source_gap'
            if not previous and self._operation_admission_locked('order.cancel') and self._control is not None:
                self._control.notify_trade()

    def note_trade_record(self, record, *, deadline=None):
        if record['state'] == 'unknown':
            if deadline is None:
                with self._binding_lock:
                    self._trade_unknown = True
                return
            self._acquire(deadline)
            try:
                self._trade_unknown = True
            finally:
                self._binding_lock.release()

    def _acquire(self, deadline):
        if time.monotonic() >= deadline or not self._binding_lock.acquire(
                timeout=max(0, deadline - time.monotonic())):
            raise TimeoutError('original Host request deadline elapsed')
        if time.monotonic() >= deadline:
            self._binding_lock.release()
            raise TimeoutError('original Host request deadline elapsed')

    def claim_trade(self, actual_binding, *, deadline):
        encoded = canonical(binding(actual_binding, control_version=self.binding_control_version))
        self._acquire(deadline)
        try:
            if encoded != self._binding_bytes or not self._operation_admission_locked('order.cancel'):
                return None
            return self.journal.claim_trade(actual_binding, deadline=deadline,
                cancel_admission=decode(self._source_status_bytes)['schema_version'] == SOURCE_STATUS_V2,
                current_session=self._trade_session)
        finally:
            self._binding_lock.release()

    def _record_response(self, record, deadline):
        self.note_trade_record(record, deadline=deadline)
        limits = self.trade_limits
        raw = encode_trade_record(record, max_command_bytes=limits['max_command_bytes'],
            max_result_bytes=limits['max_call_result_bytes'], control_version=self.binding_control_version)
        return HostResponse(202 if record['state'] in ('queued', 'dispatching') else 200, raw)

    def _trade_status(self, deadline):
        self._acquire(deadline)
        try:
            current = None if not self.connected.is_set() else self._binding_bytes
            ready = current is not None and self._stream_checked and self._source_status_bytes is not None
            limits = self.trade_limits
            public = {key: limits[key] for key in ('max_command_bytes', 'max_call_result_bytes',
                'max_command_ttl_ms', 'max_events')}
            public.update(max_event_page_bytes=self.event_storage['max_page_bytes'],
                max_http_trade_response_bytes=4*((limits['max_command_bytes']+2)//3)
                    + limits['max_call_result_bytes'] + MAX_METADATA_BYTES)
            self._observe_admission_locked(self.journal.trade_admission(deadline=deadline))
            value = {'schema_version': 'qmt.trade-host-status.v2',
                'binding': None if current is None else decode(current),
                'binding_sha256': None if current is None else digest(current),
                'read_profile_body_b64': None if current is None else b64(self._profile_bytes),
                'read_profile_body_sha256': None if current is None else digest(self._profile_bytes),
                'source_status': (None if current is None or self._source_status_bytes is None
                    else decode(self._source_status_bytes)),
                'writes_enabled': self.writes_enabled, 'accepting_commands': self._accepting_locked(),
                'closing': self.admission_stopped, 'failure': self.failure or self._trade_problem,
                'limits': public, 'unknown_fenced': self._trade_unknown is True,
                'hard_fault': (None if self._trade_hard_fault is None and self.failure is None
                    else {'code': self._trade_hard_fault or self.failure}),
                'cancel_admission': self._operation_admission_locked('order.cancel')}
            return response(200 if ready else 503, value)
        finally:
            self._binding_lock.release()

    def _trade_submit(self, raw, deadline):
        limits = self.trade_limits
        envelope, body, command = decode_trade_submission(raw, max_http_bytes=self.max_frame,
            max_command_bytes=limits['max_command_bytes'])
        original_deadline = deadline_seconds(envelope['deadline_ms'])
        self._acquire(deadline)
        try:
            prior = self.journal.get_trade(command['command_id'], deadline=deadline)
            if prior is not None:
                if prior['body'] != body:
                    return _error(409, 'idempotency_conflict')
                return self._record_response(prior, deadline)
            if not self.writes_enabled:
                return _error(403, 'writes_disabled')
            if self._binding_bytes is not None and envelope['binding_sha256'] != digest(self._binding_bytes):
                return _error(409, 'source_binding_changed')
            if not self._operation_admission_locked(command['operation']):
                return _error(503, 'source_unavailable')
            now = self.business_seconds()
            if original_deadline <= now:
                return _error(408, 'request_timeout')
            ttl_ms = limits['max_command_ttl_ms']
            if original_deadline - now > ttl_ms / 1000:
                return _error(400, 'invalid_arguments')
            record = self.journal.submit_trade(body, decode(self._binding_bytes), ttl_ms=ttl_ms,
                deadline=deadline, business_deadline=original_deadline,
                cancel_admission=decode(self._source_status_bytes)['schema_version'] == SOURCE_STATUS_V2,
                current_session=self._trade_session)
            value = self._record_response(record, deadline)
            # COMMIT 已返回才通知唯一 I/O owner；通知失败也保留原命令供 GET。
            if self._control is not None:
                self._control.notify_trade()
            return value
        finally:
            self._binding_lock.release()

    def request(self, request):
        if not isinstance(request, HostTradeRequest):
            return super().request(request)
        deadline = request.received_at + self.budget.io_seconds
        try:
            if time.monotonic() >= deadline:
                raise TimeoutError('original HTTP worker deadline elapsed')
            if request.operation == 'trade.status':
                result = self._trade_status(deadline)
            elif request.operation == 'trade.submit':
                result = self._trade_submit(request.body, deadline)
            elif request.operation == 'trade.lookup':
                identity = decode_trade_order_lookup(request.body, max_http_bytes=self.max_frame)
                reference = self.journal.lookup_trade_order(identity, deadline=deadline)
                if reference is None:
                    result = _error(404, 'unknown_order')
                else:
                    limits = self.trade_limits
                    raw = encode_trade_order_reference(reference,
                        max_command_bytes=limits['max_command_bytes'],
                        max_result_bytes=limits['max_call_result_bytes'],
                        control_version=self.binding_control_version)
                    result = HostResponse(409 if reference['association_error'] is not None else 200, raw)
            elif request.operation == 'trade.cancel_lookup':
                value = decode_trade_cancel_lookup(request.body, max_http_bytes=self.max_frame)
                reference = self.journal.lookup_trade_cancel(value['original_command_id'],
                    value['original_command_sha256'], deadline=deadline)
                if reference is None:
                    result = _error(404, 'unknown_order')
                else:
                    limits = self.trade_limits
                    raw = encode_trade_cancel_reference(reference,
                        max_command_bytes=limits['max_command_bytes'],
                        max_result_bytes=limits['max_call_result_bytes'],
                        control_version=self.binding_control_version)
                    result = HostResponse(200, raw)
            elif request.operation == 'trade.result':
                record = self.journal.get_trade(request.command_id, deadline=deadline)
                result = _error(404, 'unknown_command') if record is None else self._record_response(record, deadline)
            else:
                value = decode_trade_event_request(request.body, max_http_bytes=self.max_frame,
                    max_page_bytes=self.event_storage['max_page_bytes'], max_events=self.trade_limits['max_events'])
                raw = self.journal.events.read(value['source'], after_seq=value['after_seq'],
                    limit=value['limit'], max_bytes=value['max_bytes'], deadline=deadline)
                result = _error(404, 'unknown_stream') if raw is None else HostResponse(200, raw)
        except TimeoutError:
            result = _error(408, 'request_timeout')
        except CancelPending:
            result = response(409, {'error_code': 'cancel_pending',
                'error_message': '原委托已有未决取消；请查询实际原取消记录'})
        except OrderSourceUnavailable:
            result = _error(503, 'order_source_unavailable')
        except JournalFull:
            result = _error(503, 'queue_full')
        except JournalConflict:
            result = _error(409, 'identity_conflict')
        except (sqlite3.Error, RuntimeError):
            self.fail('journal_unavailable')
            result = _error(503, 'journal_unavailable')
        except (ValueError, TypeError, KeyError, OverflowError):
            result = _error(400, 'invalid_arguments')
        # 所有业务/异常响应都在事务rollback、close及原锁释放后核接收时的同一I/O D。
        if time.monotonic() >= deadline:
            return _error(408, 'request_timeout')
        return result

    def begin_shutdown(self):
        candidate = time.monotonic() + self.control_profile.max_call_seconds + 2*self.budget.io_seconds + 1
        return self._shutdown_state.setdefault('deadline', candidate)

    def request_close(self):
        self.begin_shutdown()
        self._admission_stopped = True
        self._wake.set()
        # 尚未建成控制循环时没有交接可排空；唤醒原 listener/handshake。
        if self._control is None or self._stop.is_set():
            super().request_close()

    def advance_trade_shutdown(self, drained):
        if type(drained) is not bool:
            raise ValueError('explicit drain observation required')
        deadline = self._shutdown_deadline
        if deadline is not None and (drained or time.monotonic() >= deadline):
            if not drained and self.failure is None:
                self.failure = 'trade_shutdown_unconfirmed'
            super().request_close()

    def close(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('close requires absolute monotonic deadline')
        if self._closed_complete:
            return
        original = self.begin_shutdown()
        self._acquire(deadline)
        try:
            self._shutdown_state['deadline'] = min(original, self._shutdown_deadline, deadline)
        finally:
            self._binding_lock.release()
        super().close(min(deadline, self._shutdown_deadline))

    def health(self):
        value = super().health()
        value['profile'] = 'restricted-shm-trading'
        return value
