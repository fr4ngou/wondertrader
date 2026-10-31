# -*- coding: utf-8 -*-
"""原认证运输的回调驱动：每次只推进已就绪帧，所有期限跨回调保留。"""
import mmap
import struct
import threading
import time

from .builtin_shm import (BuiltinMemoryConnector, BuiltinMemoryFramer, PendingIO,
    HEADER_BYTES, CLOSE_OFFSETS, authenticated_header)
from .protocol import ProtocolError, canonical, decode


class TickCredit(object):
    """一个owner的一次tick最多四个原完整帧；字节上限沿原max_frame。"""
    def __init__(self, maximum):
        self.frames, self.bytes, self.maximum = 4, 0, maximum

    def require(self):
        if not self.frames:
            raise PendingIO()

    def used(self, value):
        size = len(canonical(value))
        if not 1 <= size <= self.maximum:
            raise ProtocolError('source tick packet exceeds original frame budget')
        self.frames -= 1
        self.bytes += size


class _TickConnector(BuiltinMemoryConnector):
    """借用原映射/认证/关闭owner；缺少对端时立即返回同一个连接尝试。"""
    def poll(self, deadline):
        self._check(deadline)
        if self._framer is not None:
            self._framer.try_join(deadline)
            return self._framer
        self._rendezvous = mmap.mmap(-1, HEADER_BYTES, tagname=self.profile.name)
        try:
            try:
                generation = authenticated_header(self._rendezvous, self.profile, self.secret)
                if struct.unpack('<Q', self._rendezvous[CLOSE_OFFSETS['host']:CLOSE_OFFSETS['host']+8])[0]:
                    raise ProtocolError('builtin SHM Host rendezvous is closing')
            except ProtocolError:
                raise PendingIO()
        finally:
            self._release('_rendezvous')
        self._check(deadline)
        self._view = mmap.mmap(-1, self.profile.mapped_bytes,
            tagname=self.profile.name+'-'+generation.hex())
        try:
            if authenticated_header(self._view, self.profile, self.secret) != generation:
                raise PendingIO()
        except (ProtocolError, PendingIO):
            self._release('_view')
            raise PendingIO()
        self._check(deadline)
        self._framer = BuiltinMemoryFramer(self._view, self.profile, self.secret,
            generation, 'agent', self._stop)
        self._view = None
        self._framer.begin_join(deadline)
        raise PendingIO()


class SourceConnection(object):
    """同一策略线程拥有一代连接；没有线程、等待、文件、网络或业务重放。

    连接、一次握手和每次发送/接收各持一个原绝对D。PendingIO只表示该
    动作未完成，调用者持有原动作/帧继续；真正超期或异常退出同一代。
    """
    def __init__(self, transport, budget, stop):
        if transport.transport_kind != 'builtin-shm':
            raise ValueError('strategy tick requires builtin SHM')
        self.transport, self.budget, self.stop = transport, budget, stop
        self.owner = threading.get_ident()
        self.connector = _TickConnector(transport.shm_profile, transport.secret, stop)
        self.session = None
        self.phase = 'connect'
        # 原thread路径在worker真正开始connect时建立D；显式tick路径同样在
        # 第一次实际推进时建立一次D，构造到首个timer之间不冒充连接耗时。
        self.deadline = None
        self.steps = self.action = self.pending = None
        self.receive_deadline = self.send_deadline = None
        self.closed = False

    def _check(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError('source transport belongs to original strategy thread')
        if self.closed or self.stop.is_set():
            raise OSError('source transport is closing')

    def poll(self, credit):
        self._check()
        if self.phase == 'connect':
            if self.deadline is None:
                self.deadline = time.monotonic() + self.budget.connect_seconds
            framer = self.connector.poll(self.deadline)
            self.session = self.transport._channel(framer, 'agent')
            self.steps = self.session.handshake_steps()
            self.action = next(self.steps)
            self.deadline = time.monotonic() + self.budget.io_seconds
            self.phase = 'handshake'
        while self.phase == 'handshake':
            credit.require()
            operation, value = self.action
            if operation == 'send':
                self.session.framer.try_send(value, self.deadline)
                credit.used(value)
                response = None
            else:
                response = self.session.framer.try_receive(self.deadline)
                credit.used(response)
            try:
                self.action = self.steps.send(response)
            except StopIteration as completed:
                if canonical(completed.value) != canonical(decode(self.transport._profile)):
                    raise ProtocolError('source authenticated profile differs')
                self.steps = self.action = None
                self.phase = 'live'
                self.receive_deadline = time.monotonic() + self.budget.io_seconds
        return self.session

    def receive(self, credit):
        self._check()
        credit.require()
        raw = self.session.framer.try_receive(self.receive_deadline)
        credit.used(raw)
        return self.session.incoming(raw)

    def send(self, packet, credit):
        self._check()
        credit.require()
        if self.pending is None:
            self.pending = (canonical(packet), self.session.outgoing(packet))
            self.send_deadline = time.monotonic() + self.budget.io_seconds
        elif self.pending[0] != canonical(packet):
            raise ProtocolError('pending original source frame differs')
        self.session.framer.try_send(self.pending[1], self.send_deadline)
        credit.used(self.pending[1])
        self.session._sent += 1
        self.pending = None
        self.send_deadline = None
        self.receive_deadline = time.monotonic() + self.budget.io_seconds

    def close(self):
        if threading.get_ident() != self.owner:
            self.stop.set()
            raise RuntimeError('retain source resources for original strategy owner')
        if self.closed:
            return
        self.stop.set()
        first = None
        for resource in (self.session, self.connector):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    if first is None:
                        first = error
        if first is not None:
            raise first
        self.closed = True
        self.pending = self.steps = self.action = None
