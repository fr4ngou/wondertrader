# -*- coding: utf-8 -*-
"""R16 原线程交易服务；队列只拥有规范值，SDK/时钟/回报getter均在短锁外。"""
import base64
from collections import deque
import math
from threading import Lock
from _thread import get_ident
from time import monotonic as _monotonic
from uuid import uuid4

from .completion import MemoryCompletion
from .protocol import canonical, decode
from .trade_clock import CLOCK_SCHEMA, SharedUptimeClock, deadline_seconds
from .trade_events import TradeEventBuffer
from .trade_capabilities import SOURCE_STATUS_V2
from .trading_configuration import TradeConfiguration
from .trading_contract import validate_trade_command, validate_call_result, command_digest, _result
from .trading_kernel import TradingKernel, trade_admission_error


class SourceTradingError(ValueError):
    """固定安全码；SDK对象、账户和异常原文不进入消息。"""


def _fail(code):
    raise SourceTradingError(code) from None


def _fields(value, fields):
    if (type(value) is not dict or len(value) != len(fields)
            or any(type(key) is not str for key in value) or set(value) != set(fields)):
        _fail('invalid_payload')


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except (OverflowError, ValueError):
        return False


class SourceTradingService(object):
    """同会话交易 owner；构造/tick 属于原策略线程，其余入口可跨线程。

    enqueue 返回共享完成，成功值是规范结果 bytes；错误只含固定安全码。
    本服务不创建线程或 I/O，关闭保留原身份及未确认事实供外层交接。
    """
    def __init__(self, context, admitted, *, passorder, cancel, clock=None,
                 monotonic=None, session_id=None):
        if (type(admitted) is not TradeConfiguration
                or not callable(passorder) or not callable(cancel)):
            _fail('invalid_configuration')
        if admitted.value['transport']['kind'] != 'builtin-shm':
            _fail('unsupported_transport')
        try:
            self._clock = SharedUptimeClock().seconds if clock is None else clock
        except BaseException:
            _fail('clock_failed')
        self._mono = _monotonic if monotonic is None else monotonic
        if not callable(self._clock) or not callable(self._mono):
            _fail('invalid_configuration')
        self._binding = admitted.trade_binding
        account_limits = admitted.profile['operation_profiles']['account.trade_detail']['limits']
        self._account_binding = dict(account_limits['account_binding'], origin='trusted_bootstrap_argument')
        self._descriptor = admitted.profile['trade_profile']
        self._limits = self._descriptor['limits']
        self._queue_limit = admitted.value['max_pending']
        self._requested = admitted.writes_enabled
        self._context, self._owner = context, get_ident()
        # 原属性恰好读取一次。只有精确False表示live；未知/异常保持关闭。
        try:
            mode = context.do_back_test
        except BaseException:
            mode = None
        self._live = mode is False
        self._enabled = self._requested and self._live
        self._lock, self._queue, self._entries = Lock(), deque(), {}
        self._closing, self._executing, self._fault = False, False, None
        self._unknown_fenced = False
        self._active = None
        self._session_id = uuid4().hex if session_id is None else session_id
        try:
            self._events = TradeEventBuffer(self._session_id, self._binding['binding_id'],
                max_events=self._limits['max_events'], max_event_bytes=self._limits['max_event_bytes'],
                max_total_bytes=self._limits['max_total_event_bytes'], on_gap=self._on_gap,
                account_id=self._binding['account_id'])
            self._kernel = TradingKernel(context, binding=self._binding, passorder=passorder,
                cancel=cancel, writes_enabled=self._enabled, clock=self._kernel_clock,
                reserve_call=self._reserve_sdk_call, release_call=self._release_sdk_call)
        except BaseException:
            _fail('invalid_configuration')

    @property
    def session_id(self):
        return self._session_id

    def _stop_writes(self, code):
        with self._lock:
            if code == 'source_unknown':
                self._unknown_fenced = True
            elif self._fault is None:
                self._fault = {'code': code}
        if code == 'source_unknown':
            self._kernel.fence_unknown()
        else:
            self._kernel.request_fault(code)

    def _admission(self, operation, events=None):
        # 调用方持service锁；同时核事件owner，覆盖gap发布与通知之间的窗口。
        if events is None:
            try:
                events = self._events.status()
            except BaseException:
                if self._fault is None:
                    self._fault = {'code': 'event_status_failed'}
                self._kernel.request_fault('event_status_failed')
                return 'admission_closed'
        return trade_admission_error(operation, self._enabled,
                                     self._closing or events['closed'] or events['gap'] is not None,
                                     self._fault, self._unknown_fenced)

    def _on_gap(self, unused):
        self._stop_writes('event_gap')

    def observe_account_result(self, data):
        """实际账户适配器在原线程完成完整投影后调用；不创建查询或修改原SDK结果。"""
        if get_ident() != self._owner:
            _fail('wrong_thread')
        if (type(data) is not dict or data.get('schema_version') != 'qmt.account-batch.v2'
                or data.get('query') != {'account_type': 'stock', 'datatype': 'order',
                                         'scope': 'account', 'strategy_name': None}):
            return
        rows = data.get('rows')
        complete = data.get('completeness')
        if (data.get('account_binding') != self._account_binding
                or type(rows) is not list or type(complete) is not dict
                or set(complete) != {'complete', 'truncated', 'row_count', 'coverage'}
                or complete['complete'] is not True or complete['truncated'] is not False
                or type(complete['row_count']) is not int or complete['row_count'] != len(rows)
                or complete['coverage'] != 'sdk_returned_list'):
            return
        with self._lock:
            if self._executing or not self._unknown_fenced:
                return
            self._unknown_fenced = self._kernel.observe_order_query(
                [item['command'] for item in self._entries.values() if item['state'] == 'completed'], rows)

    def _reserve_sdk_call(self, operation):
        """Kernel预检之后的唯一SDK票据准入；锁序service→event，锁内无外部调用。"""
        try:
            with self._lock:
                if (not self._executing or self._active is None
                        or self._active['command']['operation'] != operation):
                    _fail('execution_owner_missing')
                if trade_admission_error(operation, self._enabled, self._closing,
                                         self._fault, self._unknown_fenced) is not None:
                    return None
                return self._events.reserve_call()
        except BaseException:
            self._stop_writes('sdk_admission_failed')
            raise

    def _release_sdk_call(self, ticket):
        try:
            with self._lock:
                self._events.release_call(ticket)
        except BaseException:
            self._stop_writes('sdk_release_failed')
            raise

    def _clocks(self):
        try:
            # 先取业务now再取local now，投影只会收紧，不借调用耗时扩大D。
            business = self._clock()
            local = self._mono()
            if not _number(business) or not _number(local):
                raise ValueError()
            return business, local
        except BaseException:
            self._stop_writes('clock_failed')
            _fail('clock_failed')

    def _kernel_clock(self):
        business, local = self._clocks()
        with self._lock:
            active = self._active
        if active is None:
            _fail('execution_owner_missing')
        # 同一local D也覆盖SDK晚回；不能仅靠业务时钟推进才识别RPC超时。
        if local >= active['rpc_deadline']:
            return max(business, active['effective_deadline'])
        return business

    def _decode_command(self, payload):
        _fields(payload, ('kind', 'body', 'clock_schema', 'deadline_ms'))
        if (type(payload['kind']) is not str or payload['kind'] != 'trade'
                or type(payload['clock_schema']) is not str or payload['clock_schema'] != CLOCK_SCHEMA):
            _fail('invalid_payload')
        try:
            business_deadline = deadline_seconds(payload['deadline_ms'])
        except BaseException:
            _fail('invalid_deadline')
        body, maximum = payload['body'], self._limits['max_command_bytes']
        if type(body) is not str or not 1 <= len(body) <= 4 * ((maximum + 2) // 3):
            _fail('invalid_command_bytes')
        try:
            raw = base64.b64decode(body.encode('ascii'), validate=True)
            if (not 1 <= len(raw) <= maximum
                    or base64.b64encode(raw).decode('ascii') != body):
                raise ValueError()
            command = validate_trade_command(decode(raw))
            if canonical(command) != raw:
                raise ValueError()
        except BaseException:
            _fail('invalid_command_bytes')
        if any(command[key] != self._binding[key] for key in ('binding_id', 'account_id', 'account_type')):
            _fail('binding_mismatch')
        return raw, command, business_deadline

    def _terminal(self, entry, code):
        return _result(entry['command'], entry['digest'], 'definitely_not_called', False, code)

    def _publish(self, entry, result):
        try:
            raw = canonical(validate_call_result(result, entry['command']))
            if len(raw) > self._limits['max_call_result_bytes']:
                raise ValueError()
            # 先保存原结果，发布失败仍保留身份/事实；不会重新调用SDK。
            with self._lock:
                entry['result'] = raw
            entry['completion'].publish(raw)
            if entry['completion'].poll() != raw:
                raise ValueError()
            with self._lock:
                entry['state'] = 'completed'
        except BaseException:
            with self._lock:
                entry['state'] = 'publication_failed'
            self._stop_writes('result_publication_failed')
            _fail('result_publication_failed')

    def enqueue(self, payload, rpc_deadline):
        """验证原 bytes 并占有限身份；rpc_deadline 是首次映射的本地秒 D。"""
        raw, command, business_deadline = self._decode_command(payload)
        if not _number(rpc_deadline) or rpc_deadline <= 0:
            _fail('invalid_deadline')
        cid = command['command_id']
        with self._lock:
            old = self._entries.get(cid)
            if old is not None:
                if old['raw'] != raw:
                    _fail('command_conflict')
                return old['completion']
        try:
            completion = MemoryCompletion()
            digest = command_digest(command)
        except BaseException:
            self._stop_writes('result_publication_failed')
            _fail('result_publication_failed')
        entry = {'raw': raw, 'command': command, 'digest': digest, 'completion': completion,
            'state': 'preparing', 'business_deadline': business_deadline,
            'rpc_deadline': rpc_deadline, 'effective_deadline': None, 'result': None}
        with self._lock:
            # 其他I/O调用可能在锁外准入期间占了相同身份，始终复用原完成与原D。
            old = self._entries.get(cid)
            if old is not None:
                if old['raw'] != raw:
                    _fail('command_conflict')
                return old['completion']
            if len(self._entries) >= self._limits['max_commands']:
                _fail('capacity_exhausted')
            pending = sum(item['state'] in ('preparing', 'queued') for item in self._entries.values())
            self._entries[cid] = entry
            code = self._admission(command['operation'])
            if code is None and pending >= self._queue_limit:
                code = 'capacity_exhausted'
            if code is not None:
                entry['state'] = 'publishing'
        if code is not None:
            self._publish(entry, self._terminal(entry, code))
            return completion
        try:
            business, local = self._clocks()
            if business_deadline - business > self._limits['max_command_ttl_ms'] / 1000:
                code = 'not_admitted'
            else:
                code = None
            effective = min(business_deadline, business + max(0, rpc_deadline - local))
            if business >= effective or local >= rpc_deadline:
                code = 'deadline_expired'
        except SourceTradingError:
            effective, code = business_deadline, 'clock_failed'
        with self._lock:
            # close可在时钟回调里同步完成此条；不得重入队或覆盖其原完成。
            if entry['state'] != 'preparing':
                return completion
            code = code or self._admission(command['operation'])
            entry['effective_deadline'] = effective
            if code is None:
                entry['state'] = 'queued'
                self._queue.append(entry)
            else:
                entry['state'] = 'publishing'
        if code is not None:
            self._publish(entry, self._terminal(entry, code))
        return completion

    def tick(self, phase='live_drain'):
        """原线程同步执行至多一条，返回是否处理；SDK 回报允许锁外重入。"""
        if get_ident() != self._owner:
            _fail('wrong_thread')
        if type(phase) is not str or phase != 'live_drain':
            _fail('invalid_phase')
        with self._lock:
            if self._executing:
                _fail('reentrant_call')
            if not self._queue:
                return False
            entry = self._queue.popleft()
            entry['state'] = 'executing'
            self._executing, self._active = True, entry
            admission_error = self._admission(entry['command']['operation'])
        try:
            if admission_error is not None:
                result = self._terminal(entry, admission_error)
            else:
                try:
                    business, local = self._clocks()
                    expired = (business >= entry['business_deadline']
                        or business >= entry['effective_deadline'] or local >= entry['rpc_deadline'])
                    result = (self._terminal(entry, 'deadline_expired') if expired else
                        self._kernel.execute(entry['command'], deadline=entry['effective_deadline'], phase=phase))
                except SourceTradingError:
                    result = self._terminal(entry, 'clock_failed')
                except BaseException:
                    # Kernel未给出可验证结果时不伪造SDK进入事实，保留未完成身份。
                    self._stop_writes('execution_failed')
                    with self._lock:
                        entry['state'] = 'execution_failed'
                    _fail('execution_failed')
            if result['stage'] == 'unknown':
                self._stop_writes('source_unknown')
            self._publish(entry, result)
            return True
        finally:
            with self._lock:
                self._executing, self._active = False, None
                seal_events = self._closing
            # 已进入SDK的同步回报先随原调用返回，再封新票据；晚异步回报仍报gap。
            if seal_events:
                self._events.request_close()

    def request_close(self):
        with self._lock:
            self._closing = True
            seal_events = not self._executing
            pending = [item for item in self._entries.values() if item['state'] in ('preparing', 'queued')]
            for entry in pending:
                entry['state'] = 'publishing'
            self._queue.clear()
        self._kernel.request_close()
        # 执行中的SDK继续拥有同步回报，封口由原tick finally负责。
        if seal_events:
            self._events.request_close()
        failed = False
        for entry in pending:
            try:
                self._publish(entry, self._terminal(entry, 'admission_closed'))
            except SourceTradingError:
                failed = True
        if failed:
            _fail('result_publication_failed')

    def _capture(self, context, kind, source, message=None):
        if context is not self._context:
            self._stop_writes('context_mismatch')
            _fail('context_mismatch')
        try:
            return self._events.capture(kind, source, message)
        except BaseException:
            self._stop_writes('event_gap')
            _fail('event_capture_failed')

    def on_order(self, context, obj):
        return self._capture(context, 'order', obj)

    def on_deal(self, context, obj):
        return self._capture(context, 'deal', obj)

    def on_error(self, context, args, msg):
        return self._capture(context, 'error', args, msg)

    def events(self, payload):
        _fields(payload, ('session_id', 'after_seq', 'limit', 'max_bytes'))
        if type(payload['session_id']) is not str or payload['session_id'] != self._session_id:
            _fail('session_mismatch')
        if (type(payload['limit']) is not int or not 1 <= payload['limit'] <= self._limits['max_events']
                or type(payload['max_bytes']) is not int
                or not 1 <= payload['max_bytes'] <= self._limits['max_event_page_bytes']):
            _fail('invalid_page_budget')
        try:
            return self._events.page(payload['after_seq'], limit=payload['limit'], max_bytes=payload['max_bytes'])
        except BaseException:
            _fail('invalid_event_page')

    def acknowledge(self, payload):
        _fields(payload, ('session_id', 'through_seq'))
        if type(payload['session_id']) is not str or payload['session_id'] != self._session_id:
            _fail('session_mismatch')
        try:
            through = self._events.acknowledge(payload['through_seq'])
            return {'session_id': self._session_id, 'through_seq': through}
        except BaseException:
            _fail('invalid_event_acknowledgement')

    def status(self):
        """返回普通副本；write_admission 表示当前可写状态，队列额度由 enqueue 实际占用。"""
        with self._lock:
            # event通知从其锁外进入service；该固定锁顺序不会持锁运行getter/SDK。
            events = self._events.status()
            gap = events['gap']
            available = (not events['closed'] and gap is None)
            return {'schema_version': SOURCE_STATUS_V2, 'session_id': self._session_id,
                'binding_id': self._binding['binding_id'], 'binding_sha256': self._descriptor['binding_sha256'],
                'writes_enabled': self._requested,
                'source_mode_live': self._live,
                'write_admission': available and self._admission('order.insert', events) is None,
                'cancel_admission': available and self._admission('order.cancel', events) is None,
                'unknown_fenced': self._unknown_fenced,
                'hard_fault': None if self._fault is None else dict(self._fault),
                'closing': self._closing, 'gap': None if gap is None else dict(gap),
                'queued': sum(item['state'] in ('preparing', 'queued') for item in self._entries.values()),
                'executing': self._executing, 'commands': len(self._entries),
                'completed': sum(item['state'] == 'completed' for item in self._entries.values()),
                'events': events}

    def try_local_drained(self):
        """最终关闭提交的非阻塞事实查询；锁忙即False，不构造状态副本。

        service→event锁内观察是本次排空的线性化点；晚回报仍可产生gap。
        此处只读自有普通值，保持身份和票据，不调用时钟、SDK或外部回调。
        """
        if not self._lock.acquire(False):
            return False
        try:
            # event检查必须最后执行；同时持有两个owner锁时核实际排空。
            return self._completed_locked() and self._events.try_drained()
        finally:
            self._lock.release()

    def _completed_locked(self):
        if (not self._closing or self._executing or self._active is not None
                or self._queue or self._fault is not None):
            return False
        for entry in self._entries.values():
            if entry['state'] != 'completed':
                return False
        return True

    @property
    def local_drained(self):
        # 物理借用与unknown业务事实独立；实际call/capture票据均由event owner核验。
        with self._lock:
            return self._completed_locked() and self._events.drained()
