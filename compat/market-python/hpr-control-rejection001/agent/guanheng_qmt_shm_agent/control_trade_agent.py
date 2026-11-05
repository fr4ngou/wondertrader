# -*- coding: utf-8 -*-
"""显式control2源分派；SDK仅由service在原策略线程执行。"""
from .control_agent import AgentControlLoop
from .protocol import canonical, decode


class TradingControlLoop(AgentControlLoop):
    def __init__(self, agent, session):
        AgentControlLoop.__init__(self, agent, session)
        self.pending_trade = {}
        self.handoff_failed = False
        self._max_result = agent.profile['trade_profile']['limits']['max_call_result_bytes']

    def _fail_handoff(self):
        self.handoff_failed = True
        self.agent._fail_trade_handoff()
        self.agent.request_close()

    def _dispatch_available(self):
        while True:
            taken = self.peer.take_call_with_deadline()
            if taken is None:
                return
            call, deadline = taken
            number, operation, payload = call['call_seq'], call['operation'], call['payload']
            if not operation.startswith('agent.trade'):
                self._dispatch(call)
                continue
            try:
                if operation == 'agent.trade':
                    self.pending_trade[number] = self.agent.trade.enqueue(payload, deadline)
                    self._trade_enqueued(number, self.pending_trade[number])
                    continue
                if operation == 'agent.trade.status':
                    if type(payload) is not dict or payload:
                        raise ValueError('invalid source status arguments')
                    result = self.agent.trade.status()
                elif operation == 'agent.trade.events':
                    result = self.agent.trade.events(payload)
                elif operation == 'agent.trade.ack':
                    acknowledged = self.agent.trade.acknowledge(payload)
                    result = dict(acknowledged, schema_version='qmt.trade-event-ack.v1')
                else:
                    raise ValueError('unsupported source operation')
                self.peer.reply(number, result)
            except (ValueError, TypeError):
                self.peer.reply(number, error={'code': 'invalid_arguments',
                                              'message': 'invalid source trade arguments'})

    def _complete_pending(self):
        AgentControlLoop._complete_pending(self)
        if self.handoff_failed:
            return
        for number, future in list(self.pending_trade.items()):
            try:
                raw = future.poll()
                if raw is None:
                    continue
                if type(raw) is not bytes or len(raw) > self._max_result:
                    raise ValueError('invalid source trade completion')
                payload = decode(raw)
                if canonical(payload) != raw:
                    raise ValueError('invalid source trade completion')
                self.peer.reply(number, payload)
                # reply也可能缓存过期错误；只有实际原结果缓存才授待ACK交接。
                if not self.peer.retained_reply_matches(number, payload):
                    self._fail_handoff()
                    return
                self._trade_reply_retained(number, payload)
                del self.pending_trade[number]
            except BaseException:
                # future及原bytes仍由service拥有，错误不能变成新SDK调用。
                self._fail_handoff()
                raise

    def _after_cycle(self):
        try:
            self.agent._advance_trade_close(self)
        except BaseException:
            self._fail_handoff()
            raise

    def _trade_enqueued(self, number, future):
        """显式常驻子类登记原完成责任；默认路径保持原pending交接。"""

    def _trade_reply_retained(self, number, payload):
        """显式常驻子类观察同一回复ACK；默认路径不分配额外收据。"""

    def _before_close(self):
        # 异常关闭会清空peer，必须在它发生前锁存交接失败。
        if not self.agent.trading_close_confirmed:
            self._fail_handoff()

    def close(self):
        self._before_close()
        # 父类只取消原读future；交易future/原结果继续由service保留。
        AgentControlLoop.close(self)
