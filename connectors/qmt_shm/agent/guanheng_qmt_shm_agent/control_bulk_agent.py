# -*- coding: utf-8 -*-
"""显式3.0原I/O循环；业务采集留在QMT tick，页释放依真实ACK收据。"""
import math
import time

from .control_agent import AgentControlLoop
from .bulk_service import BulkServiceError
from .protocol import decode


class BulkAgentControlLoop(AgentControlLoop):
    """一份待确认页交接，不创建运输线程或另一套RPC缓存。"""
    def __init__(self, agent, session, monotonic=None):
        if agent.control_profile.version != '3.0':
            raise ValueError('bulk control requires explicit version 3.0')
        self._mono = time.monotonic if monotonic is None else monotonic
        if not callable(self._mono):
            raise ValueError('bulk control requires a trusted monotonic clock')
        self._pending_limit = agent.control_profile.max_pending_calls
        AgentControlLoop.__init__(self, agent, session)
        self.service = agent.bulk
        self.service.bind_generation(session.generation)
        self._opens, self._page = {}, None

    def _now(self):
        try:
            value = self._mono()
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError()
            return value
        except BaseException:
            raise ValueError('bulk control clock unavailable') from None

    def _retire_opens(self):
        # 本CALL订阅随其原控制D结束；共享future/SDK继续由服务持有。
        now = self._now()
        for number, (unused_future, deadline) in list(self._opens.items()):
            if now >= deadline:
                del self._opens[number]

    def _error(self, number, code):
        self.peer.reply(number, {'schema': 'qmt.history-bulk-error.v1', 'code': code})

    def _observe_page(self):
        handoff = self._page
        if handoff is None:
            return
        receipt, payload, page_sha = handoff
        if receipt.state == 'pending':
            return
        self._page = None
        if receipt.state == 'acknowledged':
            try:
                self.service.acknowledge(payload, page_sha)
            except BulkServiceError:
                # 已确认的运输事实不能重授业务D；服务保留自身首因/终态。
                self.service.expire()
        else:
            self.service.request_close()

    def _dispatch_bulk(self, call, deadline):
        number, operation, payload = call['call_seq'], call['operation'], call['payload']
        try:
            if operation == 'agent.bulk.open':
                self._retire_opens()
                if self._now() >= deadline:
                    return
                if len(self._opens) >= self._pending_limit:
                    self._error(number, 'busy')
                    return
                self._opens[number] = (self.service.enqueue_open(payload, deadline), deadline)
            elif operation == 'agent.bulk.status':
                self.peer.reply(number, self.service.status(payload))
            else:
                if self._page is not None:
                    self._error(number, 'busy')
                    return
                value = self.service.page(payload)
                if self.peer.reply(number, value):
                    receipt = self.peer.observe_reply_ack(number, value)
                    if receipt is not None:
                        self._page = (receipt, payload, value['page_sha256'])
        except BulkServiceError as error:
            if error.code in ('invalid_request', 'identity_mismatch', 'not_found'):
                self.peer.reply(number, error={'code': 'invalid_arguments', 'message': 'invalid bulk arguments'})
            else:
                self._error(number, error.code)

    def _dispatch_available(self):
        # 父run在完整peer.receive提交后才调用本方法，先推进前页再领取新页。
        self._observe_page()
        self._retire_opens()
        self.service.expire()
        while True:
            item = self.peer.take_call_with_deadline()
            if item is None:
                return
            call, deadline = item
            if call['operation'] in ('agent.bulk.open', 'agent.bulk.page', 'agent.bulk.status'):
                self._dispatch_bulk(call, deadline)
            else:
                AgentControlLoop._dispatch(self, call)

    def _complete_pending(self):
        AgentControlLoop._complete_pending(self)
        self._retire_opens()
        for number, (future, deadline) in list(self._opens.items()):
            if self._now() >= deadline:
                del self._opens[number]
                continue
            value = future.poll()
            if self._now() >= deadline:
                del self._opens[number]
                continue
            if value is not None:
                payload = decode(value)
                if self._now() >= deadline:
                    del self._opens[number]
                    continue
                # 同一I/O owner中尚未进入下一次receive，原seq此刻仍有其缓存owner。
                self.peer.reply(number, payload)
                del self._opens[number]

    def close(self):
        try:
            self.service.request_close()
        finally:
            AgentControlLoop.close(self)
            # close同样只丢本循环订阅；原服务完成结果不得被别的CALL取消。
            self._opens.clear()
            self._page = None
