# -*- coding: utf-8 -*-
"""原base control读循环；I/O投递内存队列，QMT原线程独占券商调用。"""
import queue
import time
from .control_peer import ControlPeer


class AgentControlLoop(object):
    def __init__(self, agent, session):
        self.agent, self.session = agent, session
        self.peer = ControlPeer("agent", session.generation, agent.control_profile)
        self.pending = {}
        self._tick_batch = None
        self._tick_received = False

    def poll(self, connection, credit):
        """原peer/队列的非阻塞周期；待发送batch保留，期限归同一connection。

        默认run仍沿原线程路径。显式来源驱动只替换等待方式，所有派发、
        完成缓存、ACK和子类交接继续调用下面的同一实现。
        """
        while not self.agent._stop.is_set():
            if self._tick_batch is None:
                if not self._tick_received:
                    packet = connection.receive(credit)
                    self.peer.receive(packet)
                    self._dispatch_available()
                    self._tick_received = True
                # 显式tick把同一原帧保留到本次SDK步骤后，再准备原回复。
                # SDK仍在外层tick执行，原业务异常沿原边界传播。
                if getattr(self.agent, '_tick_yield_before_reply', False):
                    return
                self._complete_pending()
                self._tick_batch = self.peer.prepare(self.agent.last_tick)
                self._tick_received = False
            connection.send(self._tick_batch.packet, credit)
            self.peer.sent(self._tick_batch)
            self._tick_batch = None
            self._after_cycle()

    def _dispatch(self, call):
        number, operation = call["call_seq"], call["operation"]
        try:
            if operation == "agent.read":
                unused_request, future = self.agent._enqueue_read(call["payload"])
                self.pending[number] = future
            else:
                # 原base grammar包含observation；本发行没有对应业务owner。
                self.peer.reply(number, error={"code": "capability_unavailable",
                    "message": "read-only capability unavailable"})
        except queue.Full:
            self.peer.reply(number, error={"code": "queue_full", "message": "native read queue full"})
        except (ValueError, TypeError):
            self.peer.reply(number, error={"code": "invalid_arguments", "message": "invalid original read arguments"})

    def _complete_pending(self):
        for number, future in list(self.pending.items()):
            result = future.poll()
            if result is not None:
                self.peer.reply(number, result)
                del self.pending[number]

    def _dispatch_available(self):
        while True:
            call = self.peer.take_call()
            if call is None:
                return
            self._dispatch(call)

    def _after_cycle(self):
        """显式交易子类在同一I/O owner完成关闭交接；旧读循环保持无附加动作。"""

    def run(self):
        while not self.agent._stop.is_set():
            packet = self.session.receive(time.monotonic() + self.agent.budget.io_seconds)
            self.peer.receive(packet)
            self._dispatch_available()
            self._complete_pending()
            batch = self.peer.prepare(self.agent.last_tick)
            self.session.send(batch.packet, time.monotonic() + self.agent.budget.io_seconds)
            self.peer.sent(batch)
            self._after_cycle()

    def close(self):
        self.peer.close()
        for future in self.pending.values():
            future.cancel()
        self.pending.clear()
