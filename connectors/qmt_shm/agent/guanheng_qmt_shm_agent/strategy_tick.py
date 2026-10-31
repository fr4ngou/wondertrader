# -*- coding: utf-8 -*-
"""原策略timer上的四owner通信；原业务对象/队列/完成责任保持唯一。"""
import threading
import time

from .builtin_shm import PendingIO
from .history_preparation_agent import (RestrictedHistoryPreparationAgent,
    ReconnectingHistoryPreparationAgent)
from .reconnecting_read import ReconnectingReadAgent
from .reconnecting_trade import ReconnectingTradingAgent, _TradingConnection
from .restricted import RestrictedReadAgent
from .source_connection import SourceConnection, TickCredit
from .transport import LocalTransport
from .protocol import TransportBudget
from .quote_stream import QuoteStreamAgent, WarmupBarrier
from .quote_stream_contract import BATCH_SCHEMA, WARMUP_READY_SCHEMA, validate_warmup_marker


class _TickAgent(object):
    def __init__(self, *args, **kwargs):
        super(_TickAgent, self).__init__(*args, **kwargs)
        self._tick_io = None
        self._tick_started = False
        self._tick_finishing = False

    def start(self):
        if threading.get_ident() != self._thread_id or self._tick_started or self._stop.is_set():
            raise RuntimeError('source tick connection starts once on original strategy thread')
        if hasattr(self, 'trade') and not self._subscribed:
            raise RuntimeError('source account subscription required before connection')
        self._tick_started = True
        self._io_resources_closed = False
        self._tick_io = SourceConnection(self._transport, self.budget, self._stop)

    def _finish_tick_io(self):
        if self._tick_finishing:
            return
        if threading.get_ident() != self._thread_id:
            raise RuntimeError('retain source tick resources for strategy owner')
        self._tick_finishing = True
        self.connected.clear()
        self._stop.set()
        failed = False
        try:
            for resource in (self._control, self._tick_io):
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as error:
                        failed = True
                        self.cleanup_failure = self.cleanup_failure or type(error).__name__
            self._io_resources_closed = not failed
            if hasattr(self, '_connection_finished'):
                self._connection_finished()
        finally:
            self._tick_finishing = False

    def _pump_tick_io(self, credit):
        if self._stop.is_set():
            self._finish_tick_io()
            return
        try:
            session = self._tick_io.poll(credit)
            self._channel = session
            if self._control is None:
                self._control = self._make_control(session)
                self.connected.set()
            self._control.poll(self._tick_io, credit)
        except PendingIO:
            pass
        except Exception as error:
            self.failure = type(error).__name__
            self._retryable_failure = type(error) in (OSError, TimeoutError, BrokenPipeError, ConnectionResetError)
            self._finish_tick_io()

    def tick(self, allow_heavy=True):
        if threading.get_ident() != self._thread_id:
            raise RuntimeError('source tick belongs to original strategy thread')
        credit = TickCredit(self._max_frame)
        self._tick_yield_before_reply = True
        self._pump_tick_io(credit)
        self._tick_yield_before_reply = False
        result = super(_TickAgent, self).tick(allow_heavy)
        self._pump_tick_io(credit)
        return result

    def _request_transport_close(self):
        super(_TickAgent, self)._request_transport_close()
        if threading.get_ident() == self._thread_id:
            self._finish_tick_io()

    def request_close(self):
        super(_TickAgent, self).request_close()
        if hasattr(self, 'trade') and self._control is not None and not self._stop.is_set():
            # QMT stop之后不保证再有timer。只观察原排空/真实ACK，不等待peer；
            # 尚未交接的原完成由resident保留，运输关闭不授业务成功。
            self._advance_trade_close(self._control)
        if not self._stop.is_set():
            self._request_transport_close()

    def _join_transport(self, deadline):
        self._finish_tick_io()
        if not self._io_resources_closed or self.cleanup_failure is not None:
            raise RuntimeError('source tick resource release remains unconfirmed')

    @property
    def io_exited(self):
        return self._stop.is_set() and self._io_resources_closed


class _ReadConnection(_TickAgent, RestrictedReadAgent):
    pass


class TickSingleReadAgent(_ReadConnection):
    """单代只读正文的原策略线程运输入口；SDK与连接都由同一timer推进。"""


class _PreparationConnection(_TickAgent, RestrictedHistoryPreparationAgent):
    pass


class _TradeConnection(_TickAgent, _TradingConnection):
    pass


class _TickResident(object):
    def _advance(self, allow_heavy):
        agent = self._agent
        if agent is not None and agent.close_requested:
            # 同线程关闭可以已释放全部资源；重连分类取决于运行中的运输
            # 结束，不能取决于是否还需执行finally。原命令/未确认业务仍
            # 由resident保留，最终业务stop继续使用原关闭路径。
            if not self._stopped and agent.failure is None:
                agent.failure = 'OSError'
                agent._retryable_failure = True
            if not agent._io_resources_closed:
                agent._finish_tick_io()
        return super(_TickResident, self)._advance(allow_heavy)


class TickReadAgent(_TickResident, ReconnectingReadAgent):
    def _make_agent(self):
        return _ReadConnection(self._context, trusted_bootstrap=self._bootstrap, trade_detail_query=self._read)


class TickPreparationAgent(_TickResident, ReconnectingHistoryPreparationAgent):
    def _make_agent(self):
        return _PreparationConnection(self._context, trusted_bootstrap=self._bootstrap,
            download_history_data=self._download_history_data, trade_detail_query=self._read, tasks=self._tasks)


class TickTradingAgent(_TickResident, ReconnectingTradingAgent):
    def _make_agent(self):
        return _TradeConnection(self)


class TickQuoteAgent(QuoteStreamAgent):
    def _start_io(self):
        self._io_resources_closed = False
        self._tick_io = self._tick_packets = self._tick_packet = None
        self._next_at = 0.0

    def _close_generation(self):
        self.connected.clear()
        with self._condition:
            self._online = False
            self._pending.clear()
        if self._tick_io is not None:
            try:
                self._tick_io.close()
            except BaseException:
                self.cleanup_failure = 'quote_io_close_failed'
                raise
        self._tick_io = self._tick_packets = self._tick_packet = None
        self._channel = self._transport = None
        self._io_resources_closed = True

    def tick(self):
        self._check_owner()
        if self._stop.is_set():
            self._close_generation()
            return False
        if time.monotonic() < self._next_at or self.cleanup_failure:
            return False
        credit = TickCredit(self._settings['max_frame'])
        try:
            if self._tick_io is None:
                value = self._settings
                self._generation_stop = threading.Event()
                self._transport = LocalTransport(route=value['route'], secret=value['secret'],
                    max_frame=value['max_frame'], profile=self._profile, transport=value['transport'])
                self._tick_io = SourceConnection(self._transport,
                    TransportBudget(value['connect_seconds'], value['io_seconds']), self._generation_stop)
                self._io_resources_closed = False
            channel = self._tick_io.poll(credit)
            self._channel = channel
            if self._tick_packets is None:
                self.generation += 1
                self._tick_packets = self._stream_packets(self._generation_stop)
            while credit.frames:
                if self._tick_packet is None:
                    self._tick_packet = next(self._tick_packets)
                    if self._tick_packet is None:
                        return False
                if isinstance(self._tick_packet, WarmupBarrier):
                    actual = self._tick_io.receive(credit)
                    validate_warmup_marker(actual, WARMUP_READY_SCHEMA, self._tick_packet.symbols)
                    self._tick_packet = None
                    continue
                self._tick_io.send(self._tick_packet, credit)
                self._sent_packet(self._tick_packet)
                self._tick_packet = None
        except PendingIO:
            pass
        except StopIteration:
            # 原packet生成器在关闭/溢出撤销本代时正常结束；沿原thread
            # 的for结束语义退休运输并重连，保留原queue_overflow事实。
            self._close_generation()
            self._next_at = time.monotonic() + .1
        except (OSError, TimeoutError):
            self.failure = self.failure or 'transport_disconnected'
            self._close_generation()
            self._next_at = time.monotonic() + .1
        except BaseException:
            self.failure = self.failure or 'quote_stream_fault'
            self._close_generation()
            self._next_at = float('inf')
            raise
        return False

    def request_close(self):
        try:
            return QuoteStreamAgent.request_close(self)
        finally:
            # 退订失败仍沿同owner释放运输；订阅收据保持未确认，原close
            # 继续如实失败，不会把运输关闭转授整个行情owner成功。
            self._close_generation()
            self._exited.set()
