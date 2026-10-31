# -*- coding: utf-8 -*-
"""QMT全推源：原策略线程拥有订阅，SDK回调仅内存，单I/O owner拥有Session。"""
from collections import deque
import math
import threading
import time

from .protocol import ProtocolError, canonical
from .quote_stream_contract import (BATCH_SCHEMA, HEARTBEAT_SCHEMA, COUNTER_FIELDS,
    normalize_tick, validate_settings, WARMUP_PROFILE_SCHEMA, WARMUP_COMPLETE_SCHEMA,
    WARMUP_READY_SCHEMA, NATIVE_BATCH_LIMIT, warmup_marker, validate_warmup_marker)
from .transport import LocalTransport


class WarmupBarrier(object):
    """内部推进动作；同代收据确认后才允许原子切入在线队列。"""
    def __init__(self, symbols):
        self.symbols = symbols


class QuoteStreamAgent(object):
    """start/request_close仅由创建策略线程调用；close只确认已有停止及资源。

    离线latest始终有界。认证后在同锁内切snapshot并打开增量队列，避免快照
    与增量间漏窗。溢出撤销本代，原I/O关闭后重连；重建快照不授历史无缺口。
    """
    def __init__(self, context, *, settings):
        self._settings = validate_settings(settings)
        self._context, self._owner = context, threading.get_ident()
        self._symbols = frozenset(self._settings['symbols'])
        self._profile = self._settings['profile']
        self._condition = threading.Condition(threading.RLock())
        self._stop, self._entered, self._exited = threading.Event(), threading.Event(), threading.Event()
        self.connected = threading.Event()
        self._latest, self._pending = {}, deque()
        self._counts = dict((key, 0) for key in COUNTER_FIELDS if key != 'queue_depth')
        self._started = self._online = self._thread_started = self._closed = False
        self._subscription = None
        self._subscription_unknown = False
        self._thread = self._generation_stop = self._transport = self._channel = None
        self._io_resources_closed = True
        self.generation = self.overflows = 0
        self.failure = self.cleanup_failure = None
        self._startup_phase = 'waiting'

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError('quote subscription belongs to original QMT strategy thread')

    @property
    def io_exited(self):
        return self._thread is None or self._exited.is_set()

    @property
    def io_resources_closed(self):
        with self._condition:
            return self._io_resources_closed and self.cleanup_failure is None

    @property
    def closed_complete(self):
        with self._condition:
            return self._closed

    def status(self):
        with self._condition:
            value = dict(self._counts)
            value.update(queue_depth=len(self._pending), connected=self.connected.is_set(),
                generation=self.generation, overflows=self.overflows, latest_symbols=len(self._latest),
                missing_symbols=len(self._symbols)-len(self._latest),
                failure=self.failure, cleanup_failure=self.cleanup_failure, closed=self._closed)
            if self._profile['schema_version'] == WARMUP_PROFILE_SCHEMA:
                value['startup_phase'] = self._startup_phase
            return value

    def start(self):
        self._check_owner()
        with self._condition:
            if self._started or self._stop.is_set():
                raise RuntimeError('quote source starts once')
            self._started = True
            self._subscription_unknown = True
        # 订阅可能同步回调；对象及latest已发布。SDK调用不跨内存锁。
        try:
            token = self._context.subscribe_whole_quote(['SH', 'SZ'], self.on_quote)
            if type(token) is not int or token < 0:
                raise ValueError('quote subscription receipt invalid')
            with self._condition:
                self._subscription, self._subscription_unknown = token, False
            self._start_io()
            return self
        except BaseException:
            with self._condition:
                self.failure = 'source_start_failed'
            self._stop.set()
            # 已取得原token仍交原策略owner退订；未知订阅不自动重做SDK。
            raise

    def _start_io(self):
        """默认仍由原线程拥有I/O；显式策略驱动只重载此生命周期接缝。"""
        with self._condition:
            self._thread = threading.Thread(target=self._run, name='qmt-quote-stream', daemon=True)
            self._io_resources_closed = False
            thread = self._thread
        thread.start()
        self._thread_started = True

    def on_quote(self, data):
        """可由并发SDK回调调用；只复制普通数值并更新有界内存，无I/O。"""
        with self._condition:
            if self._stop.is_set():
                return
            self._counts['callbacks'] += 1
            if type(data) is not dict:
                self._counts['received_ticks'] += 1
                self._counts['rejected_ticks'] += 1
                return
            for symbol, row in data.items():
                self._counts['received_ticks'] += 1
                if symbol not in self._symbols:
                    self._counts['rejected_ticks'] += 1
                    continue
                try:
                    tick = normalize_tick(row)
                except (ValueError, TypeError, OverflowError):
                    self._counts['rejected_ticks'] += 1
                    continue
                self._latest[symbol] = tick
                self._counts['accepted_ticks'] += 1
                if self._online:
                    if len(self._pending) >= self._profile['max_pending_ticks']:
                        self.overflows += 1
                        self.failure = 'queue_overflow'
                        self._online = False
                        self._pending.clear()
                        self.connected.clear()
                        if self._generation_stop is not None:
                            self._generation_stop.set()
                    else:
                        self._pending.append((symbol, tick))
            self._condition.notify_all()

    def request_close(self):
        self._check_owner()
        with self._condition:
            self._stop.set()
            self._online = False
            self.connected.clear()
            if self._generation_stop is not None:
                self._generation_stop.set()
            self._condition.notify_all()
            token = self._subscription
        if token is not None:
            try:
                self._context.unsubscribe_quote(token)
            except BaseException:
                with self._condition:
                    self.failure = self.failure or 'unsubscribe_failed'
                raise
            with self._condition:
                self._subscription = None
        return True

    def _heartbeat(self):
        with self._condition:
            result = dict(self._counts)
            result.update(schema_version=HEARTBEAT_SCHEMA, queue_depth=len(self._pending),
                latest_symbols=len(self._latest), missing_symbols=len(self._symbols)-len(self._latest),
                overflows=self.overflows)
            return result

    def _send(self, channel, packet, generation_stop):
        if self._stop.is_set() or generation_stop.is_set():
            raise OSError('quote generation closing')
        channel.send(packet, time.monotonic() + self._settings['io_seconds'])
        self._sent_packet(packet)

    def _sent_packet(self, packet):
        if packet['schema_version'] == BATCH_SCHEMA:
            with self._condition:
                self._counts['sent_ticks'] += len(packet['ticks'])

    def _batch(self, channel, rows, kind, generation_stop):
        self._send(channel, {'schema_version': BATCH_SCHEMA, 'kind': kind, 'ticks': dict(rows)}, generation_stop)

    def _stream_packets(self, generation_stop):
        """同一快照切换/增量消费逻辑，等待方式由运输驱动拥有。"""
        last_heartbeat = 0.0
        snapshot = None
        if self._profile['schema_version'] == WARMUP_PROFILE_SCHEMA:
            # 冷初始化属于明确的离线latest阶段，尚未受理在线增量。Writer逐证券
            # 建映射的成本不会占用已开启的FIFO；Host实际消费完成才确认同代屏障。
            while not self._stop.is_set() and not generation_stop.is_set():
                with self._condition:
                    snapshot = sorted(self._latest.items()) if self._latest else None
                if snapshot:
                    break
                yield None
            if not snapshot:
                return
            self._startup_phase = 'warming'
            cold_batch = min(NATIVE_BATCH_LIMIT, self._profile['max_batch'])
            for index in range(0, len(snapshot), cold_batch):
                yield {'schema_version': BATCH_SCHEMA, 'kind': 'snapshot',
                       'ticks': dict(snapshot[index:index+cold_batch])}
            symbols = [symbol for symbol, unused in snapshot]
            yield warmup_marker(WARMUP_COMPLETE_SCHEMA, symbols)
            yield WarmupBarrier(symbols)
            # 回调在离线阶段持续刷新latest。此处重新取得最新快照，并在下方同锁
            # 开启原增量FIFO，连续流资格从这个切换点开始，初始分钟另核完整性。
            snapshot = None
            self._startup_phase = 'snapshot'
        while not self._stop.is_set() and not generation_stop.is_set():
            with self._condition:
                if snapshot is None and self._latest:
                    snapshot = sorted(self._latest.items())
                    self._pending.clear()
                    self._online = True
                    self.connected.set()
            if snapshot is not None:
                for index in range(0, len(snapshot), self._profile['max_batch']):
                    yield {'schema_version': BATCH_SCHEMA, 'kind': 'snapshot',
                           'ticks': dict(snapshot[index:index+self._profile['max_batch']])}
                self._startup_phase = 'streaming'
                break
            if time.monotonic() - last_heartbeat >= 1.0:
                yield self._heartbeat()
                last_heartbeat = time.monotonic()
            yield None
        while not self._stop.is_set() and not generation_stop.is_set():
            rows = {}
            with self._condition:
                while self._pending and len(rows) < self._profile['max_batch']:
                    symbol, tick = self._pending[0]
                    if symbol in rows:
                        break
                    self._pending.popleft()
                    rows[symbol] = tick
            if rows:
                yield {'schema_version': BATCH_SCHEMA, 'kind': 'incremental', 'ticks': rows}
            if time.monotonic() - last_heartbeat >= 1.0:
                yield self._heartbeat()
                last_heartbeat = time.monotonic()
            if not rows:
                yield None

    def _stream(self, channel, generation_stop):
        for packet in self._stream_packets(generation_stop):
            if isinstance(packet, WarmupBarrier):
                actual = channel.receive(time.monotonic() + self._settings['io_seconds'])
                validate_warmup_marker(actual, WARMUP_READY_SCHEMA, packet.symbols)
            elif packet is not None:
                self._send(channel, packet, generation_stop)
            else:
                with self._condition:
                    if not self._pending and not self._stop.is_set() and not generation_stop.is_set():
                        self._condition.wait(.1)

    def _run(self):
        self._entered.set()
        try:
            while not self._stop.is_set():
                generation_stop = threading.Event()
                transport = channel = None
                retry = True
                with self._condition:
                    self._generation_stop = generation_stop
                    if self._stop.is_set():
                        generation_stop.set()
                try:
                    value = self._settings
                    transport = LocalTransport(route=value['route'], secret=value['secret'], max_frame=value['max_frame'],
                        profile=self._profile, transport=value['transport'])
                    with self._condition:
                        self._transport = transport
                    channel = transport.connect(time.monotonic()+value['connect_seconds'], generation_stop)
                    with self._condition:
                        self._channel = channel
                    actual = channel.handshake(time.monotonic()+value['io_seconds'])
                    if canonical(actual) != canonical(self._profile):
                        raise ProtocolError('quote stream authenticated profile differs')
                    with self._condition:
                        self.generation += 1
                    self._stream(channel, generation_stop)
                except (OSError, TimeoutError):
                    with self._condition:
                        if not self._stop.is_set():
                            self.failure = self.failure or 'transport_disconnected'
                except BaseException:
                    retry = False
                    with self._condition:
                        self.failure = self.failure or 'quote_stream_fault'
                finally:
                    self.connected.clear()
                    with self._condition:
                        self._online = False
                        self._pending.clear()
                    failed = False
                    for resource in (channel, transport):
                        if resource is not None:
                            try:
                                resource.close()
                            except BaseException:
                                failed = True
                    if failed:
                        with self._condition:
                            self.cleanup_failure = 'quote_io_close_failed'
                        retry = False
                    else:
                        with self._condition:
                            self._channel = self._transport = None
                if not retry or self._stop.is_set():
                    break
                self._stop.wait(.1)
        finally:
            self.connected.clear()
            with self._condition:
                self._online = False
                self._io_resources_closed = self.cleanup_failure is None
                self._condition.notify_all()
            self._exited.set()

    def close(self, deadline):
        """管理线程仅join；原策略线程先request_close并确认原订阅撤销。"""
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('quote close requires absolute monotonic deadline')
        with self._condition:
            if self._closed:
                return True
            if not self._stop.is_set() or self._subscription is not None or self._subscription_unknown:
                raise RuntimeError('original strategy thread must confirm quote unsubscribe first')
            thread = self._thread
        if thread is threading.current_thread():
            raise RuntimeError('quote I/O cannot join itself')
        if thread is not None:
            if not self._thread_started and not self._entered.wait(max(0.0, deadline-time.monotonic())):
                raise TimeoutError('quote thread start remains owned')
            thread.join(max(0.0, deadline-time.monotonic()))
            if thread.is_alive():
                raise TimeoutError('quote I/O remains owned')
        with self._condition:
            if not self._io_resources_closed or self.cleanup_failure is not None:
                raise RuntimeError('quote I/O resource close unconfirmed')
            if time.monotonic() >= deadline:
                raise TimeoutError('quote close original deadline elapsed')
            self._closed = True
        return True
