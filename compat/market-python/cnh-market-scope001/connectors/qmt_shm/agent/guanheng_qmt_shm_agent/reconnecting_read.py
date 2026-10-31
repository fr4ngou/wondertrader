# -*- coding: utf-8 -*-
"""显式只读重连：tick独占代际推进，原Agent独占每代队列与I/O资源。"""
import math
import threading
import time

from .read_configuration import validate_read_configuration
from .restricted import RestrictedReadAgent


class ReconnectingReadAgent(object):
    def __init__(self, context, *, trusted_bootstrap, reconnect_seconds,
                 enabled=False, trade_detail_query=None):
        if enabled is not True:
            raise ValueError("read reconnect requires explicit enabled=True")
        if (type(reconnect_seconds) not in (int, float)
                or not math.isfinite(reconnect_seconds)
                or not 0.1 <= reconnect_seconds <= 300.0):
            raise ValueError("read reconnect interval must be 0.1..300 seconds")
        # 默认沿原只读准入；显式子类先冻结自己的版本，SDK入口仍归单代agent。
        self._configuration = self._admit_configuration(trusted_bootstrap)
        if self._configuration.value['transport']['kind'] != 'builtin-shm':
            raise ValueError("read reconnect requires builtin-shm transport")
        self._bootstrap = dict(self._configuration.value)
        self._bootstrap['secret'] = self._configuration.secret
        self._context, self._read = context, trade_detail_query
        self._interval = float(reconnect_seconds)
        self._owner = threading.get_ident()
        self._condition = threading.Condition(threading.RLock())
        self._started = self._stopped = self._busy = self._blocked = False
        self._agent = None
        self._close_actor = None
        self._next_at = 0.0
        self.generation = 0
        self.failure = self.cleanup_failure = None

    @property
    def profile(self):
        return self._configuration.profile

    def _admit_configuration(self, trusted_bootstrap):
        """默认仍只准入原只读配置；显式子类拥有自己的版本选择。"""
        return validate_read_configuration(trusted_bootstrap)

    def _make_agent(self):
        """每代沿原构造入口，子类复用相同退休和停止顺序。"""
        return RestrictedReadAgent(self._context,
            trusted_bootstrap=self._bootstrap, trade_detail_query=self._read)

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError("read reconnect tick belongs to the QMT strategy thread")

    def start(self):
        self._check_owner()
        with self._condition:
            if self._started or self._stopped:
                raise RuntimeError("read reconnect service starts once")
            # 首次tick才创建原Agent；start本身不连接、不执行SDK。
            self._started = True

    def tick(self, allow_heavy=True):
        self._check_owner()
        if type(allow_heavy) is not bool:
            raise ValueError("native read heavy-task permission must be a literal bool")
        with self._condition:
            if self._busy:
                raise RuntimeError("read reconnect tick is not reentrant")
            if not self._started or self._stopped or self._blocked:
                return False
            self._busy = True
        try:
            return self._advance(allow_heavy)
        except BaseException as exc:
            # 同步异常可能已经进入SDK/start；保首因并保owner，不能自动重放。
            with self._condition:
                self._blocked = True
                if self.failure is None:
                    self.failure = type(exc).__name__
            raise
        finally:
            with self._condition:
                self._busy = False
                self._condition.notify_all()

    def _advance(self, allow_heavy):
        agent = self._agent
        if agent is not None and agent.close_requested:
            if not agent.io_exited:
                return False
            with self._condition:
                self.failure = agent.failure
                if not agent.retryable_failure:
                    self._blocked = True
            # 已退出才调用原close；当前绝对D保证join(0)，不占用QMT tick等待I/O。
            try:
                agent.close(time.monotonic())
            except BaseException as exc:
                with self._condition:
                    self.cleanup_failure = type(exc).__name__
                raise
            with self._condition:
                self._agent = None
                self._next_at = time.monotonic() + self._interval
            return False
        if agent is None:
            with self._condition:
                if self._stopped or time.monotonic() < self._next_at:
                    return False
                # tick已持有busy；此处只认领创建，不跨构造/Thread.start持管理锁。
            agent = self._make_agent()
            with self._condition:
                self._agent = agent
                self.generation += 1
                start_claimed = not self._stopped
            if start_claimed:
                # stop可与已认领start交错；原Agent保持未知start所有权及停止语义。
                agent.start()
            else:
                # stop发生于锁外构造期间：接住owner但不再认领start。
                agent.request_close()
            return False
        # SDK只能进入原tick，并在管理锁之外；stop可在SDK回调内请求关闭。
        return agent.tick(allow_heavy=allow_heavy)

    def request_close(self):
        with self._condition:
            self._stopped = True
            agent = self._agent
        if agent is not None:
            agent.request_close()

    def close(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError("close requires an absolute monotonic deadline")
        actor = threading.get_ident()
        with self._condition:
            if self._close_actor == actor:
                raise RuntimeError("read reconnect close is not reentrant")
            if self._busy and actor == self._owner:
                self._stopped = True
                raise RuntimeError("active QMT tick cannot close itself")
            while self._close_actor is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("read reconnect close is busy; retain owner")
                self._condition.wait(remaining)
            self._close_actor = actor
            self._stopped = True
        acquired = False
        try:
            # 关闭全过程都有actor，原request/close重入不能等待自己；锁外执行原操作。
            self.request_close()
            with self._condition:
                while self._busy:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("read reconnect tick is busy; retain owner")
                    self._condition.wait(remaining)
                self._busy = True
                acquired = True
                agent = self._agent
            if agent is not None:
                agent.close(deadline)
                with self._condition:
                    self._agent = None
        finally:
            with self._condition:
                if acquired:
                    self._busy = False
                self._close_actor = None
                self._condition.notify_all()
