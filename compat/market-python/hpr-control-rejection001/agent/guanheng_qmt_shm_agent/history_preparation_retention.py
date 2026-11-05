# -*- coding: utf-8 -*-
"""显式 HPR 责任交接；原线程调用保持，I/O 只确认内存完成缓存。"""
from .history_preparation_agent import PreparationTasks
from .history_preparation import now_ms
from .control_agent import AgentControlLoop


class RetiringPreparationTasks(PreparationTasks):
    """确定完成且 Host 已持久 ACK，或原截止结束后，释放内存责任。"""
    def __init__(self, *args, **kwargs):
        PreparationTasks.__init__(self, *args, **kwargs)
        self._high_watermark = self._acked = self._expired = 0

    def _confirmed(self, entry):
        result = entry['future'].poll()
        return (entry['terminal'] and not entry['running'] and result is not None
            and (result.get('ok') is True or result.get('error_code') == 'preparation_not_executed'))

    def release_confirmed(self, rid):
        with self._lock:
            entry = self._entries.get(rid)
            if entry is not None and self._confirmed(entry):
                del self._entries[rid]
                self._acked += 1
                return True
            return False

    def expire_confirmed(self):
        with self._lock:
            now = now_ms(self.clock)
            for rid, entry in list(self._entries.items()):
                if self._confirmed(entry) and now >= entry['future'].request['arguments']['deadline_ms']:
                    del self._entries[rid]
                    self._expired += 1

    def admit(self, request, body=None):
        self.expire_confirmed()
        with self._lock:
            value = PreparationTasks.admit(self, request, body)
            self._high_watermark = max(self._high_watermark, len(self._entries))
            return value

    def retention_status(self):
        """SDK替身/运维内存快照；不调用SDK、不清理状态、不暴露请求身份。"""
        with self._lock:
            running = sum(not entry['terminal'] or entry['running'] for entry in self._entries.values())
            confirmed = sum(self._confirmed(entry) for entry in self._entries.values())
            return dict(schema='qmt.history-preparation-retention-status.v1', enabled=True,
                capacity=self.scope['max_tasks'], retained=len(self._entries), queued_or_running=running,
                awaiting_handoff=confirmed, held_unknown=len(self._entries)-running-confirmed,
                high_watermark=self._high_watermark, acknowledged=self._acked, expired_confirmed=self._expired)


class RetiringPreparationControl(AgentControlLoop):
    """沿原 ControlPeer 实收 ACK；本容器最多保存原 max_pending_calls 项。"""
    def __init__(self, agent, session):
        AgentControlLoop.__init__(self, agent, session)
        self._completion_receipts = {}

    def _complete_pending(self):
        for number, future in list(self.pending.items()):
            result = future.poll()
            if result is not None:
                if self.peer.reply(number, result) and getattr(future, 'book', None) is self.agent.preparation:
                    receipt = self.peer.observe_reply_ack(number, result)
                    if receipt is not None:
                        self._completion_receipts[number] = (receipt, future.request['request_id'])
                del self.pending[number]

    def _after_cycle(self):
        for number, (receipt, rid) in list(self._completion_receipts.items()):
            if receipt.state == 'pending':
                continue
            del self._completion_receipts[number]
            if receipt.state == 'acknowledged':
                self.agent.preparation.release_confirmed(rid)
        self.agent.preparation.expire_confirmed()

    def close(self):
        try:
            AgentControlLoop.close(self)
        finally:
            self._completion_receipts.clear()
