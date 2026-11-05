# -*- coding: utf-8 -*-
"""QST-R11 当前 Agent 会话的有界回报缓冲，不创建线程或执行 I/O。"""
from threading import Lock

from .protocol import canonical, decode
from .trading_kernel import snapshot_order, snapshot_deal, snapshot_error


_FAILED = object()
_MAX_SEQUENCE = 2 ** 53 - 1


class TradeEventError(ValueError):
    """固定安全码；源对象、账户字段和异常正文不进入错误消息。"""


def _fail(code):
    raise TradeEventError(code) from None


def _integer(value, low, high, code):
    if type(value) is not int or not low <= value <= high:
        _fail(code)
    return value


def _identity(value):
    if (type(value) is not str or not 1 <= len(value) <= 128
            or not value.strip() or any(not 32 <= ord(ch) < 127 for ch in value)):
        _fail('invalid_configuration')
    return value


class TradeEventBuffer(object):
    """回调可来自不同线程；短锁仅保护票据、序号与字节额度。

    SDK getter 与 on_gap 均在锁外调用。缓冲只拥有普通值的规范 bytes，
    回调返回后不保留 SDK 对象。Host 持久保存后才能 acknowledge。
    gap 只说明本接入丢失完整性，序号不证明券商事件连续。
    """
    def __init__(self, session_id, binding_id, *, max_events, max_event_bytes,
                 max_total_bytes, on_gap, account_id=None):
        self._session_id = _identity(session_id)
        self._binding_id = _identity(binding_id)
        if account_id is not None:
            if (type(account_id) is not str or not 1 <= len(account_id) <= 63
                    or any(ord(ch) < 32 or 127 <= ord(ch) <= 159 for ch in account_id)):
                _fail('invalid_configuration')
            try:
                if len(account_id.encode('utf-8')) > 63:
                    _fail('invalid_configuration')
            except UnicodeError:
                _fail('invalid_configuration')
        self._account_id = account_id
        self._max_events = _integer(max_events, 1, 4096, 'invalid_configuration')
        self._max_event_bytes = _integer(max_event_bytes, 256, 1048576,
                                         'invalid_configuration')
        self._max_total_bytes = _integer(max_total_bytes, max_event_bytes,
                                         16777216, 'invalid_configuration')
        if not callable(on_gap):
            _fail('invalid_configuration')
        self._on_gap = on_gap
        self._lock = Lock()
        self._tickets = {}
        self._used_bytes = 0
        self._next_sequence = 1
        self._published = self._offered = self._acknowledged = 0
        self._gap = None
        self._closed = False
        # SDK调用借用与回报capture票据分开；单原线程最多一个，不占回报容量。
        self._call_ticket = None

    def reserve_call(self):
        """与gap发布同锁的SDK准入点；只保有借用，不表示已经调用SDK。"""
        ticket = object()
        with self._lock:
            if self._closed or self._gap is not None or self._call_ticket is not None:
                return None
            self._call_ticket = ticket
            return ticket

    def release_call(self, ticket):
        """只归还本次原票；错误保持真实借用，不能用错误票据清空排空门。"""
        with self._lock:
            if ticket is None or ticket is not self._call_ticket:
                _fail('invalid_call_ticket')
            self._call_ticket = None

    def _gap_locked(self, code, sequence=None):
        if self._gap is not None:
            return None
        self._gap = {'code': code, 'sequence': sequence}
        return dict(self._gap)

    def _notify(self, gap):
        if gap is not None:
            try:
                self._on_gap(gap)
            except Exception:
                # 通知失败不会解除缺口；调用者仍可通过 page 观察停写原因。
                pass

    def _reserve(self, kind, err_msg):
        with self._lock:
            code = None
            if self._gap is not None:
                code = 'capture_gap'
            elif self._closed:
                code = 'capture_closed'
            elif type(kind) is not str or kind not in ('order', 'deal', 'error'):
                code = 'invalid_event_kind'
            elif kind != 'error' and err_msg is not None:
                code = 'invalid_error_message'
            elif self._next_sequence > _MAX_SEQUENCE:
                code = 'sequence_exhausted'
            elif len(self._tickets) >= self._max_events:
                code = 'event_capacity_exhausted'
            elif self._used_bytes + self._max_event_bytes > self._max_total_bytes:
                code = 'byte_capacity_exhausted'
            if code is not None:
                gap = self._gap_locked(code)
                sequence = None
            else:
                sequence = self._next_sequence
                self._next_sequence += 1
                self._tickets[sequence] = None
                self._used_bytes += self._max_event_bytes
                gap = None
        self._notify(gap)
        if sequence is None:
            _fail(code)
        return sequence

    def capture(self, kind, source, err_msg=None):
        """捕获一次白名单快照，返回本地序号；异常使完整性永久进入 gap。

        先保留有限票据再读取源字段，允许 getter 同步重入及并发倒序完成。
        晚完成票据只在它之前的票据全部完成时进入可发布前沿。
        """
        sequence = self._reserve(kind, err_msg)
        try:
            if kind == 'order':
                payload = snapshot_order(source)
            elif kind == 'deal':
                payload = snapshot_deal(source)
            else:
                payload = snapshot_error(source, err_msg)
            if self._account_id is not None:
                # 只检查已投影的普通值，不为账户过滤重读SDK getter。
                account = (payload['order_args'].get('accountID') if kind == 'error'
                           else payload.get('m_strAccountID'))
                if type(account) is not str or account != self._account_id:
                    _fail('account_mismatch')
            raw = canonical({'schema_version': 'qmt.trade-event.v1',
                'session_id': self._session_id, 'binding_id': self._binding_id,
                'sequence': sequence, 'kind': kind, 'payload': payload})
            if len(raw) > self._max_event_bytes:
                _fail('event_too_large')
        except BaseException as error:
            code = (str(error) if type(error) is TradeEventError
                    and str(error) in ('event_too_large', 'account_mismatch') else 'source_snapshot_failed')
            with self._lock:
                self._tickets[sequence] = _FAILED
                gap = self._gap_locked(code, sequence)
            self._notify(gap)
            if isinstance(error, Exception):
                _fail(code)
            raise
        with self._lock:
            self._tickets[sequence] = raw
            self._used_bytes -= self._max_event_bytes - len(raw)
            while type(self._tickets.get(self._published + 1)) is bytes:
                self._published += 1
        return sequence

    def page(self, after_seq, *, limit, max_bytes):
        """复制已完成连续事件；max_bytes 包含整个规范 JSON 页。

        已交付前沿防止调用者跳过未发送的事件。ACK 前仍可重取旧页；
        容量不足拒绝整条下一事件，调用者可增大其有界页预算。
        """
        _integer(after_seq, 0, _MAX_SEQUENCE, 'invalid_cursor')
        _integer(limit, 1, 4096, 'invalid_page_limit')
        _integer(max_bytes, 1, 16777216, 'invalid_page_budget')
        with self._lock:
            if not self._acknowledged <= after_seq <= self._offered:
                _fail('invalid_cursor')
            result = {'schema_version': 'qmt.trade-event-page.v1',
                'session_id': self._session_id, 'binding_id': self._binding_id,
                'acknowledged_through': self._acknowledged,
                'published_through': self._published,
                'gap': None if self._gap is None else dict(self._gap), 'events': []}
            size = len(canonical(result))
            if size > max_bytes:
                _fail('page_budget_exhausted')
            items = []
            through = after_seq
            for sequence in range(after_seq + 1, min(self._published, after_seq + limit) + 1):
                raw = self._tickets[sequence]
                next_size = size + len(raw) + (1 if items else 0)
                if next_size > max_bytes:
                    if not items:
                        _fail('page_budget_exhausted')
                    break
                items.append(raw)
                size = next_size
                through = sequence
            # 纯 bytes 解码/分配也可能失败；完整页构造成功后才授 ACK 前沿。
            # 此处只处理本 owner 的有限普通值，不调用 SDK getter 或 on_gap。
            result['events'] = [decode(raw) for raw in items]
            self._offered = max(self._offered, through)
        return result

    def acknowledge(self, through_seq):
        """仅释放已经成功交付的前缀；确认本身不证明券商状态完整。"""
        _integer(through_seq, 0, _MAX_SEQUENCE, 'invalid_acknowledgement')
        with self._lock:
            if not self._acknowledged <= through_seq <= self._offered:
                _fail('invalid_acknowledgement')
            for sequence in range(self._acknowledged + 1, through_seq + 1):
                self._used_bytes -= len(self._tickets.pop(sequence))
            self._acknowledged = through_seq
            return through_seq

    def request_close(self):
        """关闭新捕获；已保留票据可完成，既有页仍可取回和确认。"""
        with self._lock:
            self._closed = True

    def try_drained(self):
        """只读非阻塞排空查询；任何在途、失败或待ACK票据都保持False。"""
        if not self._lock.acquire(False):
            return False
        try:
            return self._drained_locked()
        finally:
            self._lock.release()

    def _drained_locked(self):
        return (self._closed and self._call_ticket is None
                and not self._tickets and self._gap is None)

    def drained(self):
        """普通状态查询沿原短锁语义；最终关闭提交使用try_drained避免等待。"""
        with self._lock:
            return self._drained_locked()

    def status(self):
        """返回有界普通副本；retained含在途/失败票据，inflight只计未完成投影。"""
        with self._lock:
            return {'closed': self._closed,
                'inflight': sum(value is None for value in self._tickets.values()),
                'retained': len(self._tickets), 'used_bytes': self._used_bytes,
                'published_through': self._published, 'offered_through': self._offered,
                'acknowledged_through': self._acknowledged,
                'gap': None if self._gap is None else dict(self._gap),
                'session_id': self._session_id, 'binding_id': self._binding_id}
