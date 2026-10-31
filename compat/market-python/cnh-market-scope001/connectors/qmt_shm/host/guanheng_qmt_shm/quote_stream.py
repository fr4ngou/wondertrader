"""独立行情流接收；唯一I/O线程拥有认证代与同步消费回调，不使用HTTP或Journal。"""
from __future__ import annotations

import math
import threading
import time

from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.transport import LocalTransport
from guanheng_qmt_shm_agent.quote_stream_contract import (
    validate_settings, validate_batch, validate_heartbeat)


class QuoteStreamReceiver:
    """start等待listener就绪；on_batch(ticks, kind)只在本对象I/O线程同步调用。

    消费回调抛异常时停止整条流，保留未知消费结果；连接中断可在原代确认关闭后
    重新认证。close接收原monotonic绝对截止，超期仍由本对象持有线程及运输资源。
    """
    def __init__(self, *, settings, on_batch):
        self._settings = validate_settings(settings)
        if not callable(on_batch):
            raise ValueError("quote stream callback required")
        self._on_batch = on_batch
        self._guard = threading.Lock()
        self._stop = threading.Event()
        self._entered = threading.Event()
        self.connected = threading.Event()
        self._thread = self._listener = self._session = self._transport = None
        self._close_deadline = None
        self._failure = self._cleanup_failure = None
        self.retained_error = None
        self._resources_closed = True
        self._phase = "new"
        self._generation = self._batches = self._ticks = self._heartbeats = 0
        self._heartbeat = None

    def _deadline(self, seconds):
        candidate = time.monotonic() + seconds
        with self._guard:
            return min(candidate, self._close_deadline) if self._close_deadline is not None else candidate

    def start(self):
        with self._guard:
            if self._thread is not None or self._stop.is_set():
                raise RuntimeError("quote stream receiver is single use")
            self._resources_closed = False
            self._phase = "starting"
            self._thread = threading.Thread(target=self._run, name="qmt-quote-stream-receiver", daemon=False)
            self._thread.start()
        deadline = time.monotonic() + self._settings["connect_seconds"]
        if not self._entered.wait(max(0., deadline - time.monotonic())):
            self.request_close()
            raise TimeoutError("quote stream listener startup deadline")
        with self._guard:
            listener = self._listener
        if listener is None:
            raise RuntimeError("quote stream listener startup failed")
        try:
            listener.wait_ready(deadline)
        except BaseException:
            self.request_close()
            raise
        return self

    def request_close(self):
        self._stop.set()
        self.connected.clear()
        # 只发布原运输stop，内核对象仍由原I/O线程关闭。
        with self._guard:
            listener, session = self._listener, self._session
        if listener is not None:
            listener.request_close()
        if session is not None:
            session.framer.request_close()

    def close(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError("finite absolute close deadline required")
        with self._guard:
            if self._close_deadline is None or deadline < self._close_deadline:
                self._close_deadline = deadline
            original = self._close_deadline
            thread = self._thread
        self.request_close()
        if thread is threading.current_thread():
            raise RuntimeError("receiver cannot join its own callback thread")
        if thread is not None:
            thread.join(max(0., original - time.monotonic()))
            if thread.is_alive():
                raise TimeoutError("quote stream receiver close deadline")
        if not self.io_resources_closed:
            raise RuntimeError("quote stream receiver resources unresolved")
        return True

    @property
    def io_resources_closed(self):
        with self._guard:
            return self._resources_closed and (self._thread is None or not self._thread.is_alive())

    @property
    def closed_complete(self):
        return self._stop.is_set() and self.io_resources_closed

    def status(self):
        with self._guard:
            return {"phase": self._phase, "generation": self._generation,
                    "connected": self.connected.is_set(), "batches": self._batches,
                    "received_ticks": self._ticks, "heartbeats": self._heartbeats,
                    "failure": self._failure, "cleanup_failure": self._cleanup_failure,
                    "owner_pending": not self._resources_closed,
                    "heartbeat": None if self._heartbeat is None else dict(self._heartbeat)}

    def _run(self):
        settings = self._settings
        try:
            while not self._stop.is_set():
                listener = session = transport = None
                consumer_failed = False
                try:
                    transport = LocalTransport(route=settings["route"], secret=settings["secret"],
                        max_frame=settings["max_frame"], profile=settings["profile"], transport=settings["transport"])
                    listener = transport.listen(wait_for_peer=True)
                    with self._guard:
                        self._transport, self._listener = transport, listener
                        self._phase = "listening"
                    self._entered.set()
                    if self._stop.is_set():
                        listener.request_close()
                    session = listener.accept(self._deadline(settings["connect_seconds"]))
                    with self._guard:
                        self._session = session
                    authenticated = session.handshake(self._deadline(settings["io_seconds"]), profile=settings["profile"])
                    if canonical(authenticated) != canonical(settings["profile"]):
                        raise ValueError("quote stream authenticated profile differs")
                    with self._guard:
                        self._generation += 1
                        self._phase = "receiving"
                        if not self._stop.is_set():
                            self.connected.set()
                    while not self._stop.is_set():
                        packet = session.receive(self._deadline(settings["io_seconds"]))
                        if type(packet) is dict and packet.get("schema_version") == "qmt.quote-heartbeat.v1":
                            heartbeat = validate_heartbeat(packet, settings["profile"])
                            with self._guard:
                                self._heartbeat = heartbeat
                                self._heartbeats += 1
                        else:
                            batch = validate_batch(packet, settings["profile"], settings["symbols"])
                            if self._stop.is_set():
                                break
                            tick_count = len(batch["ticks"])
                            try:
                                self._on_batch(batch["ticks"], batch["kind"])
                            except BaseException:
                                consumer_failed = True
                                raise
                            with self._guard:
                                self._batches += 1
                                self._ticks += tick_count
                except BaseException as exc:
                    if consumer_failed:
                        with self._guard:
                            if self._failure is None:
                                self._failure = "consumer_failed"
                            self.retained_error = exc
                        self._stop.set()
                    elif not self._stop.is_set():
                        with self._guard:
                            self._failure = "connection_ended"
                finally:
                    self.connected.clear()
                    cleanup = None
                    # Session、listener和半构造transport始终在创建它们的原线程收口。
                    for owned in (session, listener, transport):
                        if owned is not None:
                            try:
                                owned.close()
                            except BaseException as exc:
                                if cleanup is None:
                                    cleanup = exc
                    closed = listener is None or listener.io_resources_closed
                    with self._guard:
                        if cleanup is not None or not closed:
                            self._cleanup_failure = "transport_close_unconfirmed"
                            if self.retained_error is None:
                                self.retained_error = cleanup
                            self._stop.set()
                        else:
                            self._session = self._listener = self._transport = None
                    if cleanup is not None or not closed:
                        break
                if not self._stop.is_set():
                    self._stop.wait(.05)
        finally:
            self.connected.clear()
            self._entered.set()
            with self._guard:
                self._resources_closed = self._cleanup_failure is None and self._listener is None and self._session is None
                self._phase = "closed" if self._resources_closed else "owner_pending"
