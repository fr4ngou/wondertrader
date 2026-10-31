# -*- coding: utf-8 -*-
"""具有明确所有权的历史纯值快照；工作线程分页前结束SDK及Frame访问。"""
import hashlib
import json
import math
import re
import threading
import time
import types

from .history_1m import HistoryError, _stamp, validated_row


class BulkSnapshotError(Exception):
    def __init__(self, code):
        if type(code) is not str or code not in (
                'invalid_contract', 'owner_required', 'capture_already_started', 'busy',
                'not_ready', 'ack_mismatch', 'expired', 'closed', 'failed',
                'source_shape_invalid', 'source_value_invalid', 'row_limit',
                'row_bytes_limit', 'snapshot_bytes_limit', 'page_bytes_limit',
                'total_bytes_limit', 'source_failed'):
            code = 'source_failed'
        self.code = code
        Exception.__init__(self, code)


def _reject(code):
    raise BulkSnapshotError(code)


def _encode(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


class BulkSnapshot(object):
    """status.ownership_pending为真时，调用方持续持有本对象。

    字节预算计量规范编码长度，解释器及供应商内部堆内存另有边界。
    正在执行的可信回调须自行返回；关闭或到期时仍保留其所有权。
    """
    _TERMINAL = ('completed', 'failed', 'expired', 'closed')

    def __init__(self, identity, limits, deadline, clock=time.monotonic):
        if (type(identity) is not dict or set(identity) != set((
                'range_id', 'session_id', 'snapshot_id', 'symbol', 'start_time', 'end_time'))
                or type(limits) is not dict or set(limits) != set((
                    'max_rows', 'max_row_bytes', 'max_snapshot_bytes', 'max_page_rows',
                    'max_page_bytes', 'max_total_bytes'))):
            _reject('invalid_contract')
        for key in ('range_id', 'session_id', 'snapshot_id'):
            value = identity[key]
            if type(value) is not str or not 1 <= len(value) <= 128 or not re.fullmatch(r'[\x21-\x7e]+', value):
                _reject('invalid_contract')
        if type(identity['symbol']) is not str or not re.fullmatch(r'[0-9]{6}\.(SH|SZ)', identity['symbol']):
            _reject('invalid_contract')
        try:
            start, end = _stamp(identity['start_time']), _stamp(identity['end_time'])
        except HistoryError:
            _reject('invalid_contract')
        if start > end or any(type(n) is not int or n <= 0 for n in limits.values()):
            _reject('invalid_contract')
        if (not limits['max_page_rows'] <= limits['max_rows'] <= 1000000
                or not limits['max_row_bytes'] <= limits['max_page_bytes'] <= limits['max_total_bytes']
                or limits['max_snapshot_bytes'] > limits['max_total_bytes']):
            _reject('invalid_contract')
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or not callable(clock):
            _reject('invalid_contract')
        self._identity, self._limits = dict(identity), dict(limits)
        self._start, self._end = start.timestamp()*1000, end.timestamp()*1000
        self._deadline, self._clock, self._owner = deadline, clock, threading.get_ident()
        self._lock = threading.Lock()
        self._state, self._failure = 'new', None
        self._started = self._close_requested = False
        self._work = self._kind = None
        self._rows, self._page = [], None
        self._captured = self._acked = self._pages = self._snapshot_bytes = self._emitted = 0
        self._page_end = 0
        self._last_ack = None

    def _release_locked(self):
        if self._work is None and self._state in self._TERMINAL:
            self._rows = []
            self._page = None

    def _terminal_locked(self, state, code=None):
        if self._state not in self._TERMINAL:
            self._state, self._failure = state, code
        self._release_locked()

    def _check_locked(self):
        if self._state not in self._TERMINAL and self._clock() >= self._deadline:
            self._terminal_locked('expired', 'expired')
        if self._state in ('failed', 'expired', 'closed'):
            _reject(self._failure or self._state)

    def _check(self):
        with self._lock:
            self._check_locked()

    def _finish(self, token):
        with self._lock:
            if self._work is token:
                self._work = self._kind = None
            self._release_locked()

    def _failure_from(self, error):
        if isinstance(error, BulkSnapshotError):
            code = error.code
        elif isinstance(error, HistoryError):
            code = error.code
        else:
            code = 'source_failed'
        code = BulkSnapshotError(code).code
        with self._lock:
            self._terminal_locked('failed', code)
            code = self._failure or code
        return BulkSnapshotError(code)

    def capture(self, read_rows):
        if threading.get_ident() != self._owner:
            _reject('owner_required')
        if not callable(read_rows):
            _reject('invalid_contract')
        token = object()
        rows, iterator, source, row, raw, failure = [], None, None, None, None, None
        with self._lock:
            self._check_locked()
            if self._started:
                _reject('capture_already_started')
            self._started = True
            self._state, self._work, self._kind = 'capturing', token, 'capture'
        try:
            self._check()
            source = read_rows()
            self._check()
            iterator = iter(source)
            self._check()
            previous, size = None, 0
            for index in range(self._limits['max_rows']+1):
                self._check()
                try:
                    row = next(iterator)
                except StopIteration:
                    self._check()
                    break
                self._check()
                if index == self._limits['max_rows']:
                    _reject('row_limit')
                row = validated_row(row, self._start, self._end, previous, self._check)
                self._check()
                raw = _encode(row)
                self._check()
                if len(raw) > self._limits['max_row_bytes']:
                    _reject('row_bytes_limit')
                size += len(raw)
                if size > self._limits['max_snapshot_bytes']:
                    _reject('snapshot_bytes_limit')
                rows.append(row)
                previous = row[0]
            with self._lock:
                self._check_locked()
                self._rows, self._captured, self._snapshot_bytes = rows, len(rows), size
        except BaseException as error:
            failure = self._failure_from(error)
        finally:
            # 此处仅负责原生生成器收尾，其他对象的close钩子由其原所有者负责。
            for owned in (iterator, source if source is not iterator else None):
                if type(owned) is types.GeneratorType:
                    try:
                        owned.close()
                    except BaseException as error:
                        if failure is None:
                            failure = self._failure_from(error)
            # 包括失败路径在内，全部供应商引用均在原采集线程释放。
            owned = iterator = source = rows = row = raw = read_rows = None
            with self._lock:
                if failure is None:
                    try:
                        self._check_locked()
                        self._state = 'ready'
                    except BulkSnapshotError as error:
                        failure = BulkSnapshotError(error.code)
            self._finish(token)
        if failure is not None:
            raise failure
        return self.status()

    def _envelope(self, index, final):
        raw = _encode({'schema': 'qmt.history-bulk-page.v1', 'identity': self._identity,
                       'page_index': index, 'rows': [], 'final': final, 'total_rows': self._captured})
        before, marker, after = raw.partition(b'"rows":[]')
        if not marker:
            _reject('invalid_contract')
        return before+b'"rows":[', b']'+after

    def page(self):
        token = object()
        with self._lock:
            self._check_locked()
            if self._state == 'awaiting_ack':
                return dict(self._page)
            if self._work is not None:
                _reject('busy')
            if self._state != 'ready':
                _reject('not_ready')
            self._state, self._work, self._kind = 'encoding', token, 'encoding'
            rows, start, index = self._rows, self._acked, self._pages
        failure = answer = page = None
        pieces = prefix = suffix = final_prefix = final_suffix = raw = payload = None
        try:
            self._check()
            prefix, suffix = self._envelope(index, False)
            final_prefix, final_suffix = self._envelope(index, True)
            final_delta = len(final_prefix)+len(final_suffix)-len(prefix)-len(suffix)
            used, pieces, end = len(prefix)+len(suffix), [], start
            while end < self._captured and end-start < self._limits['max_page_rows']:
                self._check()
                raw = _encode(rows[end])
                self._check()
                added = len(raw)+(1 if pieces else 0)
                candidate_size = used+added+(final_delta if end+1 == self._captured else 0)
                if candidate_size > self._limits['max_page_bytes']:
                    if not pieces:
                        _reject('page_bytes_limit')
                    break
                pieces.append(raw)
                used += added
                end += 1
            final = end == self._captured
            if final:
                prefix, suffix = final_prefix, final_suffix
            payload = prefix+b','.join(pieces)+suffix
            self._check()
            if len(payload) > self._limits['max_page_bytes']:
                _reject('page_bytes_limit')
            if self._emitted+len(payload) > self._limits['max_total_bytes']:
                _reject('total_bytes_limit')
            page = {'page_index': index, 'page_sha256': hashlib.sha256(payload).hexdigest(), 'payload': payload}
            answer = dict(page)
            emitted = self._emitted+len(payload)
        except BaseException as error:
            failure = self._failure_from(error)
        finally:
            # 编码临时引用先退休；page/answer仅保留即将发布及返回的同一不可变payload。
            rows = pieces = prefix = suffix = final_prefix = final_suffix = raw = payload = None
        if failure is not None:
            page = answer = None
            self._finish(token)
            raise failure
        try:
            with self._lock:
                self._check_locked()
                if self._work is not token:
                    _reject('busy')
                self._emitted = emitted
                self._page, self._page_end = page, end
                page = None
                self._state = 'awaiting_ack'
                self._work = self._kind = None
        except BaseException as error:
            failure = self._failure_from(error)
        if failure is not None:
            page = answer = None
            self._finish(token)
            raise failure
        return answer

    def pending_page_metadata(self):
        """查询同一待确认页的小元数据，避免调用方解码整页行 JSON。

        返回值独立于缓存；不编码、不确认、不借出行。调用方仍须核对
        page_index/hash，且后续 ACK 继续消费原截止时间。
        """
        with self._lock:
            self._check_locked()
            if self._work is not None:
                _reject('busy')
            if self._state != 'awaiting_ack' or self._page is None:
                _reject('not_ready')
            return {'page_index': self._page['page_index'],
                    'page_sha256': self._page['page_sha256'],
                    'rows': self._page_end - self._acked,
                    'final': self._page_end == self._captured}

    def ack(self, page_index, page_sha256):
        with self._lock:
            self._check_locked()
            if type(page_index) is not int or type(page_sha256) is not str:
                _reject('ack_mismatch')
            key = (page_index, page_sha256)
            if self._last_ack == key:
                return self._status_locked()
            if (self._state != 'awaiting_ack' or self._page is None
                    or key != (self._page['page_index'], self._page['page_sha256'])):
                _reject('ack_mismatch')
            for index in range(self._acked, self._page_end):
                self._rows[index] = None
            self._acked, self._pages, self._last_ack = self._page_end, self._pages+1, key
            self._page = None
            self._state = 'completed' if self._acked == self._captured else 'ready'
            self._release_locked()
            return self._status_locked()

    def close(self):
        with self._lock:
            # 先检查原截止时间；已锁存的到期或失败状态在关闭时保持原因。
            try:
                self._check_locked()
            except BulkSnapshotError:
                pass
            self._close_requested = True
            self._terminal_locked('closed', 'closed')
            return self._status_locked()

    def _status_locked(self):
        return {'state': self._state, 'ownership_pending': self._work is not None,
                'inflight_kind': self._kind, 'close_requested': self._close_requested,
                'rows_captured': self._captured, 'rows_acked': self._acked, 'pages_acked': self._pages,
                'snapshot_bytes': self._snapshot_bytes, 'emitted_bytes': self._emitted,
                'failure_code': self._failure, 'identity': dict(self._identity)}

    def status(self):
        with self._lock:
            try:
                self._check_locked()
            except BulkSnapshotError:
                pass
            return self._status_locked()
