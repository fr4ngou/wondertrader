# -*- coding: utf-8 -*-
"""原读owner上的显式交易组合；关闭通知与实际交易交接分开确认。"""
import math
import threading
import time

from .restricted import RestrictedReadAgent
from .trading_configuration import validate_trade_configuration
from .trade_service import SourceTradingService
from .control_trade_agent import TradingControlLoop


class RestrictedTradingAgent(RestrictedReadAgent):
    def __init__(self, context, *, trusted_bootstrap, trade_detail_query,
                 passorder, cancel, clock=None,
                 monotonic=None, session_id=None):
        admitted = validate_trade_configuration(trusted_bootstrap)
        if admitted.value['transport']['kind'] != 'builtin-shm':
            raise ValueError('trade strategy requires explicit builtin SHM')
        self._trade_context = context
        self._trade_account = admitted.trade_binding['account_id']
        self._trade_thread = threading.get_ident()
        self._trade_mono = time.monotonic if monotonic is None else monotonic
        if not callable(self._trade_mono):
            raise ValueError('explicit source monotonic clock required')
        self._trade_close_lock = threading.Lock()
        self._trade_close_deadline = None
        self._trade_close_confirmed = False
        self._trade_close_verified = False
        self._trade_handoff_failed = False
        self._subscription_attempted = self._subscribed = False
        self.trade = SourceTradingService(context, admitted, passorder=passorder, cancel=cancel,
            clock=clock, monotonic=self._trade_mono,
            session_id=session_id)
        self._initialize(context, admitted, trade_detail_query)

    @property
    def trading_close_confirmed(self):
        # 晚到callback可能使先前drain快照失效，最终查询始终再核已知gap。
        with self._trade_close_lock:
            confirmed = self._trade_close_confirmed and not self._trade_handoff_failed
        return confirmed and self.trade.local_drained

    def _fail_trade_handoff(self):
        with self._trade_close_lock:
            self._trade_handoff_failed = True
        self.trade._stop_writes('handoff_failed')

    def _now(self):
        value = self._trade_mono()
        try:
            valid = type(value) in (int, float) and math.isfinite(value)
        except (OverflowError, ValueError):
            valid = False
        if not valid:
            raise ValueError('invalid source monotonic clock')
        return value

    def subscribe_account(self):
        """init原线程只尝试一次账户订阅；先由生成入口发布callback owner。"""
        if (threading.get_ident() != self._trade_thread or self._subscription_attempted
                or self._trade_close_deadline is not None or self._worker is not None):
            raise RuntimeError('source account subscription requires original initialization')
        self._subscription_attempted = True
        try:
            setter = getattr(self._trade_context, 'set_account')
            if not callable(setter):
                raise ValueError('account subscription callable required')
            setter(self._trade_account)
            self._subscribed = True
        except BaseException:
            self.request_close()
            raise RuntimeError('source account subscription failed') from None

    def _make_control(self, session):
        return TradingControlLoop(self, session)

    def start(self):
        if not self._subscribed or self._trade_close_deadline is not None:
            raise RuntimeError('source requires completed account initialization')
        try:
            return RestrictedReadAgent.start(self)
        except BaseException:
            self._fail_trade_handoff()
            self.request_close()
            raise

    def _run(self):
        try:
            RestrictedReadAgent._run(self)
        finally:
            if not self.trading_close_confirmed:
                self._fail_trade_handoff()
                self.trade.request_close()

    def tick(self, allow_heavy=True):
        if threading.get_ident() != self._trade_thread:
            raise RuntimeError('source execution belongs to original strategy thread')
        if type(allow_heavy) is not bool:
            raise ValueError('native task permission must be a literal bool')
        if allow_heavy and not self._stop.is_set() and self.connected.is_set():
            if self.trade.tick(phase='live_drain'):
                self.last_tick = time.time()
                return True
        return RestrictedReadAgent.tick(self, allow_heavy)

    def on_order(self, context, source):
        return self.trade.on_order(context, source)

    def on_deal(self, context, source):
        return self.trade.on_deal(context, source)

    def on_error(self, context, source, error):
        return self.trade.on_error(context, source, error)

    def request_close(self):
        """策略stop只冻结截止与源准入；I/O保留原结果/事件有限交接窗口。"""
        try:
            now = self._now()
        except BaseException:
            self._fail_trade_handoff()
            try:
                self.trade.request_close()
            finally:
                RestrictedReadAgent.request_close(self)
            raise
        with self._trade_close_lock:
            if self._trade_close_deadline is None:
                self._trade_close_deadline = now + self.control_profile.max_call_seconds + self.budget.io_seconds
        # 先固定原截止；发布排队命令的拒绝结果也可能失败，不能让I/O无期限等待。
        try:
            self.trade.request_close()
        except BaseException:
            self._fail_trade_handoff()
            RestrictedReadAgent.request_close(self)
            raise

    def _close_expired(self):
        now = self._close_now()
        # 时钟替身及调度可让管理线程收紧D；取完时间再核当前截止。
        with self._trade_close_lock:
            deadline = self._trade_close_deadline
            expired = deadline is not None and now >= deadline
        if expired:
            self._fail_trade_handoff()
            RestrictedReadAgent.request_close(self)
            return True
        return False

    def _close_now(self):
        try:
            return self._now()
        except BaseException:
            self._fail_trade_handoff()
            RestrictedReadAgent.request_close(self)
            raise

    def _try_confirm_close(self, now=None, *, verify_resources=False, repeated=False):
        """最终提交只观察自有事实；锁忙保留未确认，不等待、不运行时钟或SDK。"""
        if not self._trade_close_lock.acquire(False):
            return False
        try:
            if self._trade_handoff_failed:
                return False
            if repeated:
                if not self._trade_close_verified:
                    return False
            elif self._trade_close_deadline is None or now >= self._trade_close_deadline:
                self._trade_handoff_failed = True
                return False
            if verify_resources and not self._trade_close_confirmed:
                return False
            # service→event的非阻塞查询是排空事实的线性化点；之后晚回报仍报gap。
            if not self.trade.try_local_drained():
                return False
            self._trade_close_confirmed = True
            if verify_resources:
                self._trade_close_verified = True
            return True
        finally:
            self._trade_close_lock.release()

    def _advance_trade_close(self, loop):
        with self._trade_close_lock:
            deadline = self._trade_close_deadline
        if deadline is None:
            return
        if self._close_expired():
            return
        drained = (not loop.handoff_failed and not loop.pending_trade
                and not loop.peer.has_incoming('agent.trade'))
        now = self._close_now()
        if drained and self._try_confirm_close(now):
            RestrictedReadAgent.request_close(self)
        elif self._trade_handoff_failed or now >= deadline:
            self._fail_trade_handoff()
            RestrictedReadAgent.request_close(self)

    def close(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('close requires an absolute monotonic deadline')
        if self._trade_close_verified:
            # 已完成资源回收，只查询当前交接事实；重复关闭不重开通知和时钟路径。
            if not self._try_confirm_close(verify_resources=True, repeated=True):
                raise RuntimeError('source trade handoff is unconfirmed; retain its owner')
            return
        self.request_close()
        with self._trade_close_lock:
            self._trade_close_deadline = min(self._trade_close_deadline, deadline)
        self._close_expired()
        if self._worker is None:
            self._try_confirm_close(self._close_now())
            RestrictedReadAgent.request_close(self)
        RestrictedReadAgent.close(self, deadline)
        # join/句柄释放后仍须在同一截止内，资源已关闭不能替代按期交接。
        if not self._try_confirm_close(self._close_now(), verify_resources=True):
            if self._trade_handoff_failed:
                self._fail_trade_handoff()
            raise RuntimeError('source trade handoff is unconfirmed; retain its owner')
