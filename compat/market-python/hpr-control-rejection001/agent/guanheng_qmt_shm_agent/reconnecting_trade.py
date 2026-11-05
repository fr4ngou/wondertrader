# -*- coding: utf-8 -*-
"""显式常驻交易owner：同一业务会话借用串行认证运输代际。

SDK仍由原策略线程的原service.tick执行。运输退休保留命令、原截止和
事件前沿；失去真实回复ACK的责任长期保留，最终关闭仍报告未确认。
"""
import math
import time

from .control_trade_agent import TradingControlLoop
from .reconnecting_read import ReconnectingReadAgent
from .trade_service import SourceTradingService
from .trading_agent import RestrictedTradingAgent
from .trading_configuration import validate_trade_configuration


class _ResidentTradingControlLoop(TradingControlLoop):
    """原ControlPeer提供ACK收据；本代只跟踪尚未确认的有界CALL窗口。"""
    def __init__(self, agent, session):
        TradingControlLoop.__init__(self, agent, session)
        self._trade_handoffs = {}

    def _trade_enqueued(self, number, future):
        self._trade_handoffs[number] = (future, None)

    def _trade_reply_retained(self, number, payload):
        receipt = self.peer.observe_reply_ack(number, payload)
        if receipt is None:
            raise RuntimeError('original trade reply acknowledgement is unavailable')
        future, unused = self._trade_handoffs[number]
        self._trade_handoffs[number] = (future, receipt)

    def _reap_trade_handoffs(self):
        # receive与本方法归同一I/O线程；最终管理close只在join后观察。
        for number, item in list(self._trade_handoffs.items()):
            if item[1] is not None and item[1].state == 'acknowledged':
                del self._trade_handoffs[number]

    def _after_cycle(self):
        self._reap_trade_handoffs()
        TradingControlLoop._after_cycle(self)

    def _before_close(self):
        self._reap_trade_handoffs()
        pending = self._trade_handoffs or dict(
            (number, (future, None)) for number, future in self.pending_trade.items())
        if pending:
            number = min(pending)
            future, receipt = pending[number]
            self.agent._resident._retain_handoff({
                'generation': self.peer.generation, 'call_seq': number,
                'completion': future, 'receipt': receipt})


class _TradingConnection(RestrictedTradingAgent):
    """借用唯一service；本对象只拥有一代运输、读队列及控制循环。"""
    def __init__(self, resident):
        self._resident = resident
        RestrictedTradingAgent.__init__(self, resident._context,
            trusted_bootstrap=resident._bootstrap, trade_detail_query=resident._read,
            passorder=resident._passorder, cancel=resident._cancel,
            monotonic=resident._monotonic)
        self._subscribed = resident._subscribed

    def _make_trade_service(self, context, admitted, **kwargs):
        return self._resident.trade

    def _make_control(self, session):
        return _ResidentTradingControlLoop(self, session)

    def _fail_trade_handoff(self):
        with self._trade_close_lock:
            self._trade_handoff_failed = True
        self._resident._retain_handoff()

    def _connection_finished(self):
        # 未确认CALL已由控制循环移交长期owner；单纯运输退出不产生业务故障。
        # stop可能恰好与退休交错，只有service已封口/排空才提交最终确认。
        if self._resident._stopped:
            self._try_confirm_close(self._close_now())

    @property
    def trading_close_confirmed(self):
        return (not self._resident.handoff_unconfirmed
                and RestrictedTradingAgent.trading_close_confirmed.fget(self))

    def _try_confirm_close(self, now=None, **kwargs):
        if self._resident.handoff_unconfirmed:
            return False
        control = self._control
        if control is not None:
            control._reap_trade_handoffs()
            if control._trade_handoffs:
                return False
        return RestrictedTradingAgent._try_confirm_close(self, now, **kwargs)

    def request_close(self):
        if not self._resident._stopped:
            self._request_transport_close()
            return
        with self._trade_close_lock:
            deadline = self._resident._final_deadline
            if self._trade_close_deadline is None:
                self._trade_close_deadline = deadline
            else:
                self._trade_close_deadline = min(self._trade_close_deadline, deadline)
        RestrictedTradingAgent.request_close(self)

    def close(self, deadline):
        # stop可在旧I/O退出之后到达；先封唯一service，再沿原D核已有事实。
        # 这里不提交RPC、不执行SDK，原close仍负责join和资源证明。
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('close requires an absolute monotonic deadline')
        self.request_close()
        if self._resident.handoff_unconfirmed:
            # 长期owner已保留旧代未确认责任，业务成功确认已不可取得。
            # 本代仍须按原D退休运输；I/O finally把本代未确认CALL继续交回
            # 同一长期owner，resident.close随后如实报告业务unconfirmed。
            self._close_transport(deadline)
            return
        if self.io_exited:
            self._try_confirm_close(self._close_now())
        RestrictedTradingAgent.close(self, deadline)


class ReconnectingTradingAgent(ReconnectingReadAgent):
    """显式enabled=True启用；构造/订阅/start/tick属于原QMT策略线程。

    subscribe_account恰好尝试一次，callback始终归本owner。每代认证后才
    调用原tick，失联期间暂停SDK；队列及未知结果仍沿原service契约保留。
    close使用绝对monotonic截止。io_resources_closed只报告运输回收，
    closed_complete/trading_close_confirmed还要求真实业务交接及事件排空。
    clock、monotonic与session_id仅供可信装配或隔离验证显式注入。
    """
    def __init__(self, context, *, trusted_bootstrap, reconnect_seconds,
                 enabled=False, trade_detail_query=None, passorder, cancel,
                 clock=None, monotonic=None, session_id=None):
        ReconnectingReadAgent.__init__(self, context,
            trusted_bootstrap=trusted_bootstrap, reconnect_seconds=reconnect_seconds,
            enabled=enabled, trade_detail_query=trade_detail_query)
        self._bootstrap.update(trade_binding=self._configuration.trade_binding,
                               writes_enabled=self._configuration.writes_enabled)
        self._monotonic = time.monotonic if monotonic is None else monotonic
        if not callable(self._monotonic):
            raise ValueError('explicit source monotonic clock required')
        self._passorder, self._cancel = passorder, cancel
        self._subscription_attempted = self._subscribed = False
        self._final_deadline = None
        self._handoff_unconfirmed = False
        self._first_unconfirmed_handoff = None
        self._closed_complete = False
        self.trade = SourceTradingService(context, self._configuration,
            passorder=passorder, cancel=cancel, clock=clock,
            monotonic=self._monotonic, session_id=session_id)

    def _admit_configuration(self, trusted_bootstrap):
        return validate_trade_configuration(trusted_bootstrap)

    def _make_agent(self):
        return _TradingConnection(self)

    def _retire_agent(self, agent, deadline):
        agent._close_transport(deadline)

    def _retain_handoff(self, detail=None):
        with self._condition:
            self._handoff_unconfirmed = True
            # 保存首个未确认原完成；其他命令原值仍由唯一service.entries拥有。
            if self._first_unconfirmed_handoff is None and detail is not None:
                self._first_unconfirmed_handoff = detail

    @property
    def handoff_unconfirmed(self):
        with self._condition:
            return self._handoff_unconfirmed

    @property
    def io_resources_closed(self):
        with self._condition:
            agent = self._agent
            return (not self._busy and (agent is None or
                (agent.io_exited and agent._io_resources_closed
                 and agent.cleanup_failure is None)))

    @property
    def trading_close_confirmed(self):
        with self._condition:
            confirmed = self._closed_complete and not self._handoff_unconfirmed
        return confirmed and self.trade.local_drained

    @property
    def closed_complete(self):
        return self.trading_close_confirmed

    def subscribe_account(self):
        self._check_owner()
        with self._condition:
            if self._subscription_attempted or self._started or self._stopped:
                raise RuntimeError('source account subscription requires original initialization')
            self._subscription_attempted = True
        try:
            setter = getattr(self._context, 'set_account')
            if not callable(setter):
                raise ValueError('account subscription callable required')
            setter(self._configuration.trade_binding['account_id'])
            self._subscribed = True
        except BaseException:
            self.request_close()
            raise RuntimeError('source account subscription failed') from None

    def start(self):
        if not self._subscribed:
            raise RuntimeError('source requires completed account initialization')
        ReconnectingReadAgent.start(self)

    def on_order(self, context, source):
        return self.trade.on_order(context, source)

    def on_deal(self, context, source):
        return self.trade.on_deal(context, source)

    def on_error(self, context, source, error):
        return self.trade.on_error(context, source, error)

    def _now(self):
        now = self._monotonic()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ValueError('invalid source monotonic clock')
        return now

    def request_close(self):
        try:
            now = self._now()
        except BaseException:
            self._retain_handoff()
            with self._condition:
                self._stopped = True
                agent = self._agent
            try:
                self.trade.request_close()
            finally:
                if agent is not None:
                    agent._request_transport_close()
            raise
        with self._condition:
            self._stopped = True
            if self._final_deadline is None:
                self._final_deadline = (now + self._configuration.control_profile.max_call_seconds
                    + self._configuration.budget.io_seconds)
            agent = self._agent
        try:
            self.trade.request_close()
        except BaseException:
            self._retain_handoff()
            if agent is not None:
                agent._request_transport_close()
            raise
        if agent is not None:
            agent.request_close()

    def close(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('close requires an absolute monotonic deadline')
        with self._condition:
            if self._closed_complete:
                if self._handoff_unconfirmed or not self.trade.try_local_drained():
                    raise RuntimeError('source trade handoff is unconfirmed; retain its owner')
                return
            if self._final_deadline is None:
                self._final_deadline = deadline
            else:
                self._final_deadline = min(self._final_deadline, deadline)
            deadline = self._final_deadline
        ReconnectingReadAgent.close(self, deadline)
        if (self._now() >= deadline or self.handoff_unconfirmed
                or not self.trade.try_local_drained()):
            raise RuntimeError('source trade handoff is unconfirmed; retain its owner')
        with self._condition:
            self._closed_complete = True
