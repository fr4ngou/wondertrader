# -*- coding: utf-8 -*-
"""一代只读长窗服务：原线程独占采集，I/O只处理脱离来源的有限页。"""
import base64
from functools import wraps
import math
import re
import threading
import time
from uuid import UUID

from .bulk_capabilities import profile_descriptor
from .bulk_history_1m import BulkHistory1mAdapter
from .bulk_snapshot import BulkSnapshotError
from .completion import MemoryCompletion
from .history_1m import arguments, HistoryError
from .protocol import canonical, decode
from .read_capabilities import shanghai_date
from .trade_clock import CLOCK_SCHEMA, SharedUptimeClock, deadline_seconds, TradeClockError


_TERMINAL = ('completed', 'failed', 'expired', 'closed')
_EXTRA = ('invalid_request', 'identity_mismatch', 'range_limit', 'not_found',
          'page_limit', 'queue_expired', 'clock_unavailable')


class BulkServiceError(Exception):
    """安全固定码；外部异常正文和traceback不进入结果或记录。"""
    def __init__(self, code):
        self.code = code if type(code) is str and code in _EXTRA else BulkSnapshotError(code).code
        Exception.__init__(self, self.code)


def _fail(code):
    raise BulkServiceError(code) from None


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except (ValueError, OverflowError):
        return False


def _uuid(value):
    if type(value) is not str or len(value) != 36:
        _fail('invalid_request')
    try:
        if str(UUID(value)) != value:
            _fail('invalid_request')
    except ValueError:
        _fail('invalid_request')


def _owned_work(method):
    """覆盖服务自身编码/发布的整个调用栈，包括已退休记录的状态查询。"""
    @wraps(method)
    def owned(self, *args, **kwargs):
        with self._lock:
            self._work_count += 1
        try:
            return method(self, *args, **kwargs)
        finally:
            args = kwargs = None
            with self._lock:
                self._work_count -= 1
    return owned


class SourceBulkHistoryService(object):
    """只持一个活动快照和有限终态记录；关闭在途工作保留原owner。

    clock是可信SharedUptimeClock同接口对象，monotonic只映射首次控制D。
    MemoryCompletion发布小bytes；page/status返回独立安全dict。
    """
    def __init__(self, context, profile, max_result_bytes, clock=None,
                 monotonic=None, as_of_date_provider=None):
        self._descriptor = profile_descriptor(profile, max_result_bytes=max_result_bytes)
        self._limits = self._descriptor['limits']
        self._context = context
        self._clock = SharedUptimeClock() if clock is None else clock
        self._mono = time.monotonic if monotonic is None else monotonic
        self._date = shanghai_date if as_of_date_provider is None else as_of_date_provider
        if not callable(getattr(self._clock, 'seconds', None)) or not callable(self._mono) or not callable(self._date):
            _fail('invalid_contract')
        self._owner = threading.get_ident()
        self._lock = threading.Lock()
        self._work_count = 0
        self._clock_failed = threading.Event()
        self._generation = None
        self._closed = False
        self._records, self._active = {}, None

    def _now(self, transport=False):
        try:
            value = self._mono() if transport else self._clock.seconds()
            if not _finite(value):
                raise ValueError()
            return value
        except BaseException:
            self._clock_failed.set()
            _fail('clock_unavailable')

    def _snapshot_clock(self):
        # BS保留自身失败处理；服务另锁存clock_unavailable并冻结后继准入。
        try:
            return self._now()
        except BulkServiceError:
            raise BulkSnapshotError('source_failed') from None

    def bind_generation(self, generation):
        if type(generation) is not str or not re.fullmatch(r'[0-9a-f]{32}', generation):
            _fail('invalid_request')
        with self._lock:
            if self._generation is not None and self._generation != generation:
                _fail('identity_mismatch')
            if self._closed:
                _fail('closed')
            self._generation = generation

    def _identity(self, value, request_id):
        _uuid(request_id)
        fields = ('range_id', 'session_id', 'snapshot_id', 'symbol', 'start_time', 'end_time')
        if type(value) is not dict or set(value) != set(fields):
            _fail('invalid_request')
        _uuid(value['range_id'])
        _uuid(value['snapshot_id'])
        if any(type(value[key]) is not str or len(value[key]) > 36 for key in fields):
            _fail('invalid_request')
        with self._lock:
            generation = self._generation
        if generation is None or value['session_id'] != generation or value['range_id'] != request_id:
            _fail('identity_mismatch')
        return dict(value)

    def _open_payload(self, payload):
        fields = ('request_id', 'identity', 'arguments', 'clock_schema', 'deadline_ms', 'queue_deadline_ms')
        if type(payload) is not dict or set(payload) != set(fields):
            _fail('invalid_request')
        identity = self._identity(payload['identity'], payload['request_id'])
        args = payload['arguments']
        if type(args) is not dict or set(args) != set(('symbol', 'start_time', 'end_time', 'max_rows')):
            _fail('invalid_request')
        if any(type(args[key]) is not str or args[key] != identity[key] for key in ('symbol', 'start_time', 'end_time')):
            _fail('identity_mismatch')
        if type(args['max_rows']) is not int or not 1 <= args['max_rows'] <= self._limits['max_rows']:
            _fail('invalid_request')
        try:
            deadline_seconds(payload['deadline_ms'])
            deadline_seconds(payload['queue_deadline_ms'])
        except TradeClockError:
            _fail('invalid_request')
        if (payload['clock_schema'] != CLOCK_SCHEMA or type(payload['clock_schema']) is not str
                or payload['queue_deadline_ms'] > payload['deadline_ms']):
            _fail('invalid_request')
        value = dict(payload, identity=identity, arguments=dict(args))
        raw = canonical(value)
        if len(raw) > 2048:
            _fail('invalid_request')
        return value, raw

    def _synthetic(self, record):
        return dict(state='capturing' if record['inflight'] else 'new',
                    ownership_pending=bool(record['inflight']), inflight_kind='construct' if record['inflight'] else None,
                    close_requested=self._closed, rows_captured=0, rows_acked=0, pages_acked=0,
                    snapshot_bytes=0, emitted_bytes=0, failure_code=record['code'], identity=dict(record['identity']))

    def _refresh(self, record):
        """锁外询问快照；构造/采集/封装在途时绝不退休其引用。"""
        with self._lock:
            snapshot, terminal = record['snapshot'], record['stage'] == 'terminal'
        state = snapshot.status() if snapshot is not None else None
        terminal = terminal or (state is not None and state['state'] in _TERMINAL)
        now = None
        if not terminal:
            try:
                now = self._now()
            except BulkServiceError:
                pass
        with self._lock:
            if state is not None and state['state'] in _TERMINAL and state['failure_code'] and record['code'] is None:
                record['code'] = ('clock_unavailable' if self._clock_failed.is_set()
                                  and state['failure_code'] == 'source_failed' else state['failure_code'])
            if not terminal and record['code'] is None:
                if self._clock_failed.is_set():
                    record['code'] = 'clock_unavailable'
                elif self._closed:
                    record['code'] = 'closed'
                elif record['stage'] == 'queued' and now >= record['queue_deadline']:
                    record['code'] = 'queue_expired'
                elif now >= record['deadline']:
                    record['code'] = 'expired'
            stop = record['code'] is not None or self._closed
        if snapshot is not None:
            if stop:
                snapshot.close()
            state = snapshot.status()
            if self._clock_failed.is_set() and not stop:
                snapshot.close()
                state = snapshot.status()
        with self._lock:
            if self._clock_failed.is_set() and record['code'] is None and not terminal:
                record['code'] = 'clock_unavailable'
            if state is not None:
                record['safe'] = state
                if state['state'] in _TERMINAL and state['state'] != 'completed' and record['code'] is None:
                    record['code'] = state['failure_code'] or state['state']
            done = record['code'] is not None or (state is not None and state['state'] in _TERMINAL)
            if done and not record['inflight'] and (state is None or not state['ownership_pending']):
                record['stage'] = 'terminal'
                record['snapshot'] = None
                if self._active is record:
                    self._active = None
            elif record['inflight']:
                record['stage'] = 'capturing' if record['capture_work'] else 'snapshot'
            elif state is not None and state['state'] not in _TERMINAL:
                record['stage'] = 'snapshot'

    @_owned_work
    def _envelope(self, record, kind):
        # 成功编码仍消费原D；首因只会从None锁存一次，至多再取一个安全终态。
        for unused in range(2):
            with self._lock:
                state = record['safe']
                if record['inflight']:
                    state = dict(state) if state is not None else self._synthetic(record)
                    work_kind = ('capture' if record['snapshot'] is not None else 'construct') if record['capture_work'] else 'delivery'
                    state.update(ownership_pending=True, inflight_kind=work_kind)
                value = dict(schema='qmt.history-bulk-' + kind + '.v1', request_id=record['id'],
                             identity=dict(record['identity']), stage=record['stage'], snapshot=state, error_code=record['code'])
            copied = decode(canonical(value))
            self._refresh(record)
            with self._lock:
                if (record['stage'], record['code']) == (copied['stage'], copied['error_code']):
                    return copied
            state = value = copied = None
        _fail('busy')

    @_owned_work
    def _publish(self, record):
        # 编码锁外完成；跨原D或关闭只收紧一次首因，最多重取一次。
        for unused in range(2):
            with self._lock:
                if record['published'] or record['publishing']:
                    return
                code, stage = record['code'], record['stage']
            if stage not in ('snapshot', 'terminal'):
                return
            value = dict(schema='qmt.history-bulk-error.v1', code=code) if code else self._envelope(record, 'open')
            raw = canonical(value)
            # 内层封套检查之后，这次最终bytes编码也可能跨D；认领发布前再核。
            self._refresh(record)
            if len(raw) > 4096:
                _fail('invalid_contract')
            with self._lock:
                if (record['code'], record['stage']) != (code, stage):
                    continue
                if record['published'] or record['publishing']:
                    return
                record['publishing'] = True
            published = False
            try:
                # 结果身份在上锁比较处固定；实际发布在锁外，工作计数持续保owner。
                record['future'].publish(raw)
                published = True
            except BaseException:
                with self._lock:
                    if record['code'] is None:
                        record['code'] = 'source_failed'
                _fail('source_failed')
            finally:
                value = raw = None
                with self._lock:
                    record['publishing'] = False
                    record['published'] = published
            return
        _fail('busy')

    @_owned_work
    def enqueue_open(self, payload, control_deadline):
        value, raw = self._open_payload(payload)
        with self._lock:
            old = self._records.get(value['request_id'])
            if old is not None:
                if old['raw'] != raw:
                    _fail('identity_mismatch')
                return old['future']
        if not _finite(control_deadline):
            _fail('invalid_request')
        try:
            arguments(value['arguments'], self._date(), self._limits['max_calendar_days'], self._limits['max_rows'])
        except (HistoryError, ValueError, TypeError):
            _fail('invalid_request')
        now, transport_now = self._now(), self._now(True)
        if (value['deadline_ms'] - now*1000 > self._descriptor['total_timeout_ms']
                or value['queue_deadline_ms'] - now*1000 > self._descriptor['queue_timeout_ms']):
            _fail('invalid_request')
        deadline = math.floor(min(value['deadline_ms']/1000.0,
                                  now + max(0, control_deadline-transport_now))*1000)/1000.0
        queue_deadline = min(value['queue_deadline_ms']/1000.0, deadline)
        if now >= deadline:
            _fail('expired')
        if now >= queue_deadline:
            _fail('queue_expired')
        self.expire()
        record = dict(id=value['request_id'], identity=value['identity'], raw=raw, arguments=value['arguments'],
                      deadline=deadline, queue_deadline=queue_deadline, future=MemoryCompletion(), stage='queued',
                      snapshot=None, safe=None, inflight=0, capture_work=False, code=None,
                      publishing=False, published=False)
        with self._lock:
            if self._closed:
                _fail('closed')
            if self._clock_failed.is_set():
                _fail('clock_unavailable')
            old = self._records.get(record['id'])
            if old is not None:
                if old['raw'] != raw:
                    _fail('identity_mismatch')
                return old['future']
            if self._active is not None:
                _fail('busy')
            if len(self._records) >= self._limits['max_ranges']:
                _fail('range_limit')
            self._records[record['id']] = self._active = record
        return record['future']

    @_owned_work
    def tick(self, allow_heavy=True):
        if threading.get_ident() != self._owner:
            _fail('owner_required')
        if type(allow_heavy) is not bool:
            _fail('invalid_request')
        self.expire()
        with self._lock:
            record = self._active
            if not allow_heavy or self._closed or record is None or record['stage'] != 'queued':
                return False
            record.update(stage='capturing', inflight=1, capture_work=True)
        adapter = None
        try:
            limits = {key: value for key, value in self._limits.items() if key not in ('max_pages', 'max_ranges')}
            adapter = BulkHistory1mAdapter(self._context, record['arguments'], record['identity'], limits,
                record['deadline'], clock=self._snapshot_clock, as_of_date_provider=self._date)
            now = self._now()
            with self._lock:
                record['snapshot'] = adapter.snapshot
                if now >= record['queue_deadline'] and record['code'] is None:
                    record['code'] = 'queue_expired'
                stop = self._closed or record['code'] is not None
            if stop:
                adapter.snapshot.close()
            adapter.capture()
        except BaseException as error:
            code = 'clock_unavailable' if self._clock_failed.is_set() else (
                error.code if isinstance(error, (BulkSnapshotError, BulkServiceError)) else 'source_failed')
            with self._lock:
                if record['code'] is None:
                    record['code'] = BulkServiceError(code).code
        finally:
            # adapter/供应商局部引用由原采集线程释放后才清在途事实。
            adapter = None
            with self._lock:
                record['capture_work'] = False
                record['inflight'] -= 1
            self._refresh(record)
            self._publish(record)
        return True

    def _lookup(self, payload, page=False):
        fields = ('request_id', 'identity', 'page_index') if page else ('request_id', 'identity')
        if type(payload) is not dict or set(payload) != set(fields):
            _fail('invalid_request')
        identity = self._identity(payload['identity'], payload['request_id'])
        if page and (type(payload['page_index']) is not int or not 0 <= payload['page_index'] < self._limits['max_pages']):
            _fail('invalid_request')
        with self._lock:
            record = self._records.get(payload['request_id'])
            if record is None:
                _fail('not_found')
            if identity != record['identity']:
                _fail('identity_mismatch')
        self._refresh(record)
        return record

    @_owned_work
    def status(self, payload):
        record = self._lookup(payload)
        self._publish(record)
        return self._envelope(record, 'status')

    def _work(self, record):
        with self._lock:
            if record['code'] is not None:
                _fail(record['code'])
            if record['snapshot'] is None or record['capture_work']:
                _fail('not_ready')
            if record['inflight']:
                _fail('busy')
            record['inflight'] += 1
            return record['snapshot']

    @_owned_work
    def page(self, payload):
        record = self._lookup(payload, True)
        snapshot = self._work(record)
        page = metadata = value = None
        try:
            if snapshot.status()['pages_acked'] != payload['page_index']:
                _fail('ack_mismatch')
            page = snapshot.page()
            metadata = snapshot.pending_page_metadata()
            if (metadata['page_index'], metadata['page_sha256']) != (page['page_index'], page['page_sha256']):
                _fail('ack_mismatch')
            if page['page_index'] + 1 == self._limits['max_pages'] and not metadata['final']:
                with self._lock:
                    if record['code'] is None:
                        record['code'] = 'page_limit'
                _fail('page_limit')
            value = dict(schema='qmt.history-bulk-delivery.v1', request_id=record['id'], identity=dict(record['identity']),
                         page_index=page['page_index'], page_sha256=page['page_sha256'],
                         body=base64.b64encode(page['payload']).decode('ascii'))
            if self._now() >= record['deadline']:
                _fail('expired')
            with self._lock:
                if self._closed:
                    _fail('closed')
            return value
        except BulkSnapshotError as error:
            _fail('clock_unavailable' if self._clock_failed.is_set() else error.code)
        except BulkServiceError:
            raise
        except BaseException:
            with self._lock:
                if record['code'] is None:
                    record['code'] = 'source_failed'
            _fail('source_failed')
        finally:
            # 编码临时原页/字符串引用先退休，再释放外层工作责任。
            page = metadata = value = snapshot = None
            with self._lock:
                record['inflight'] -= 1
            self._refresh(record)

    @_owned_work
    def acknowledge(self, payload, page_sha256):
        record = self._lookup(payload, True)
        snapshot = self._work(record)
        try:
            return snapshot.ack(payload['page_index'], page_sha256)
        except BulkSnapshotError as error:
            _fail('clock_unavailable' if self._clock_failed.is_set() else error.code)
        finally:
            snapshot = None
            with self._lock:
                record['inflight'] -= 1
            self._refresh(record)

    @_owned_work
    def expire(self):
        with self._lock:
            record = self._active
        if record is not None:
            self._refresh(record)
            self._publish(record)

    def request_close(self):
        with self._lock:
            self._closed = True
        self.expire()

    @property
    def drained(self):
        self.expire()
        with self._lock:
            return self._active is None and self._work_count == 0
