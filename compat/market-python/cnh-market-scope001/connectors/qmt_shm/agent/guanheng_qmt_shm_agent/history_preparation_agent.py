# -*- coding: utf-8 -*-
"""补齐沿原队列/策略线程执行；跨重连保留有限任务身份和未知结果。"""
import base64
from datetime import datetime, timezone
import queue
import threading
import time
from .completion import MemoryCompletion
from .errors import GatewayError
from .history_preparation import (OPERATION, arguments, limits, now_ms, require_live,
                                  returned, validate_configuration)
from .protocol import canonical, decode
from .restricted import RestrictedReadAgent
from .reconnecting_read import ReconnectingReadAgent
from .results import finalize_result
from .trade_clock import SharedUptimeClock


def _failure(request, code, maximum):
    return finalize_result(dict(request_id=request['request_id'], operation_id=OPERATION,
        ok=False, completed_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        error_code=code, error_message=('历史补齐结果未知；保留原ID并回读核查，禁止自动重试'
            if code == 'preparation_unknown' else '历史补齐在原生调用前结束，未执行下载')), maximum)


class _Completion(MemoryCompletion):
    def __init__(self, book, request):
        MemoryCompletion.__init__(self)
        self.book, self.request = book, request

    def publish(self, value):
        with self.book._lock:
            entry = self.book._entries[self.request['request_id']]
            if entry['terminal']:
                return
            # 完整结果封装也消耗原D；不能在SDK及时返回后延迟授成功。
            try:
                expired = now_ms(self.book.clock) >= self.request['arguments']['deadline_ms']
            except Exception:
                expired = True
            if value.get('ok') is not True or expired:
                value = _failure(self.request, 'preparation_unknown' if entry['entered']
                    else 'preparation_not_executed', self.book.maximum)
            entry['terminal'] = True
            MemoryCompletion.publish(self, decode(canonical(value)))

    def cancel(self):
        with self.book._lock:
            entry = self.book._entries[self.request['request_id']]
            self.publish(_failure(self.request, 'preparation_unknown' if entry['entered']
                else 'preparation_not_executed', self.book.maximum))


class PreparationTasks(object):
    """一个常驻owner跨代共持；完整ID不逐出，不承诺跨终端进程持久去重。

    Host原Journal持久保存派发事实；进程重启后原ID只查原Host结果，未知
    任务先回读核查。新身份代表新的显式副作用授权，禁止自动生成重试ID。
    """
    def __init__(self, scope, maximum, clock, monotonic=time.monotonic):
        self.scope, self.maximum = limits(scope), maximum
        if not callable(getattr(clock, 'seconds', None)) or not callable(monotonic):
            raise ValueError('history preparation requires trusted clocks')
        self.clock, self.monotonic = clock, monotonic
        self._lock, self._entries = threading.RLock(), {}
        self.owner = threading.get_ident()

    def admit(self, request, body=None):
        raw = canonical(request) if body is None else body
        if type(raw) is not bytes or decode(raw) != request:
            raise ValueError('original preparation request bytes required')
        rid = request['request_id']
        with self._lock:
            old = self._entries.get(rid)
            if old is not None:
                if old['body'] != raw:
                    raise ValueError('history preparation identity conflicts')
                return old['future'], False
            require_live(request['arguments'], self.scope, self.clock)
            if (len(self._entries) >= self.scope['max_tasks'] or
                    sum(not e['terminal'] and not e['entered'] for e in self._entries.values()) >= self.scope['max_queued']):
                raise queue.Full()
            future = _Completion(self, decode(raw))
            self._entries[rid] = dict(body=raw, future=future, entered=False, running=False, terminal=False)
            return future, True

    def abandon(self, request):
        # 原队列没有接受此任务；固定结果仍占原ID，外部不能借失败绕过去重。
        self._entries[request['request_id']]['future'].cancel()

    def execute(self, request, native, local_deadline, closed):
        if threading.get_ident() != self.owner:
            raise RuntimeError('history preparation belongs to original strategy thread')
        args = arguments(request['arguments'], self.scope)
        with self._lock:
            entry = self._entries[request['request_id']]
            if entry['terminal'] or entry['entered'] or closed():
                raise GatewayError('preparation_not_executed', '历史补齐任务未进入下载')
            if now_ms(self.clock) >= args['deadline_ms'] or self.monotonic() >= local_deadline:
                raise GatewayError('preparation_not_executed', '历史补齐在原截止前未执行')
            entry['entered'], entry['running'] = True, True
        try:
            # 固定四个位置参数；不解析任意SDK返回值、不使用外部同名SDK。
            native(args['symbol'], args['period'], args['start_time'], args['end_time'])
            if closed() or now_ms(self.clock) >= args['deadline_ms'] or self.monotonic() >= local_deadline:
                raise GatewayError('preparation_unknown', '历史补齐调用已结束，结果需要原ID核查')
            return returned(args)
        except BaseException:
            # SDK抛错可能发生在缓存已变更之后，异常正文及返回正文均不外传。
            raise GatewayError('preparation_unknown', '历史补齐结果未知；请先回读缓存核查') from None
        finally:
            with self._lock:
                entry['running'] = False

    @property
    def busy(self):
        with self._lock:
            return any(entry['running'] for entry in self._entries.values())


class RestrictedHistoryPreparationAgent(RestrictedReadAgent):
    def __init__(self, context, *, trusted_bootstrap, download_history_data,
                 trade_detail_query=None, tasks=None, clock=None):
        admitted = validate_configuration(trusted_bootstrap)
        if not callable(download_history_data):
            raise ValueError('fixed builtin download_history_data callable required')
        scope = admitted.profile['operation_profiles'][OPERATION]['limits']
        self.preparation = (PreparationTasks(scope, admitted.value['max_result_bytes'],
            SharedUptimeClock() if clock is None else clock) if tasks is None else tasks)
        if self.preparation.scope != scope or self.preparation.owner != threading.get_ident():
            raise ValueError('history preparation task owner differs')
        self._download_history_data = download_history_data
        self._initialize(context, admitted, trade_detail_query)

    def _enqueue_read(self, message):
        request, started, remaining = self._decode_read(message)
        if request['operation_id'] != OPERATION:
            return RestrictedReadAgent._enqueue_read(self, message)
        future, fresh = self.preparation.admit(request, base64.b64decode(message['body'], validate=True))
        if fresh:
            try:
                self._queue.put_nowait((request, started, remaining, future))
            except BaseException:
                self.preparation.abandon(request)
                raise
        return request, future

    def _execute_request(self, request, deadline):
        if request['operation_id'] == OPERATION:
            return self.preparation.execute(request, self._download_history_data, deadline,
                lambda: self._stop.is_set() or not self.connected.is_set())
        return RestrictedReadAgent._execute_request(self, request, deadline)

    def close(self, deadline):
        RestrictedReadAgent.close(self, deadline)
        if self.preparation.busy:
            raise RuntimeError('retain original SDK task owner until download returns')


class ReconnectingHistoryPreparationAgent(ReconnectingReadAgent):
    def __init__(self, context, *, trusted_bootstrap, reconnect_seconds, enabled=False,
                 download_history_data=None, trade_detail_query=None, clock=None):
        if not callable(download_history_data):
            raise ValueError('fixed builtin download_history_data callable required')
        admitted = validate_configuration(trusted_bootstrap)
        self._tasks = PreparationTasks(admitted.profile['operation_profiles'][OPERATION]['limits'],
            admitted.value['max_result_bytes'], SharedUptimeClock() if clock is None else clock)
        self._download_history_data = download_history_data
        ReconnectingReadAgent.__init__(self, context, trusted_bootstrap=trusted_bootstrap,
            reconnect_seconds=reconnect_seconds, enabled=enabled, trade_detail_query=trade_detail_query)

    def _admit_configuration(self, trusted_bootstrap):
        return validate_configuration(trusted_bootstrap)

    def _make_agent(self):
        return RestrictedHistoryPreparationAgent(self._context, trusted_bootstrap=self._bootstrap,
            download_history_data=self._download_history_data, trade_detail_query=self._read, tasks=self._tasks)
