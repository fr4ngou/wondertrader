"""来源晚到的运行装配；原执行owner仍单独拥有原生进程及金融责任。"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import math
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
from uuid import uuid4

from guanheng_market_client import _DeadlineConnection, _DeadlineReader

from .managed_local_process import _json, _read, _require, _sha
from .thread_owner import ThreadOwner


class TradeSourceProbe:
    """有界读取原交易Host状态；凭据只在构造时从原配置指定环境读取。

    GET仅观察Host已经持有的认证/通道状态，不触发券商查询，不解释持仓和委托。
    False代表可以继续等待的来源缺席；协议或认证错误由调用方终止本地监督。
    """
    def __init__(self, descriptor, expected_sha256):
        raw = _read(Path(descriptor), 65536)
        _require(hashlib.sha256(raw).hexdigest() == _sha(expected_sha256))
        deployment = _json(raw)
        raw = _read(Path(deployment['configuration']), 256 * 1024)
        _require(hashlib.sha256(raw).hexdigest() == _sha(deployment['configuration_sha256']))
        trader = _json(raw)['trader']
        url = urlsplit(trader['base_url'])
        _require(url.scheme == 'http' and url.hostname is not None and url.port is not None
                 and not url.username and not url.password and url.path in ('', '/')
                 and not url.query and not url.fragment)
        self.host, self.port = url.hostname, url.port
        self._address = ipaddress.ip_address(self.host)
        # 此装配只等待本实例的本地HTTP Host；沿原Native的明文连接边界。
        _require(self._address.is_loopback)
        self.seconds = trader['timeout_ms'] / 1000.
        self.maximum = trader['max_response_bytes']
        _require(.001 <= self.seconds <= 30 and type(self.maximum) is int
                 and 8192 <= self.maximum <= 16 * 1024 * 1024)
        self._key, self._secret = os.environ[trader['key_id_env']], os.environ[trader['hmac_secret_env']]
        _require(type(self._key) is str and 0 < len(self._key) <= 128
                 and type(self._secret) is str and 0 < len(self._secret) <= 4096
                 and '\r' not in self._key and '\n' not in self._key)

    def __call__(self, deadline):
        """单次monotonic截止内返回来源通道就绪；返回值不授予交易权限。"""
        path, stamp, nonce = '/internal/v1/trade-status', str(time.time()), str(uuid4())
        digest = hashlib.sha256(b'').hexdigest()
        signature = hmac.new(self._secret.encode(), '\n'.join(
            ('GET', path, stamp, nonce, digest)).encode(), hashlib.sha256).hexdigest()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        maximum = self.maximum
        class Response(http.client.HTTPResponse):
            def __init__(self, sock, *args, **kwargs):
                super().__init__(sock, *args, **kwargs)
                try:
                    self.fp = _DeadlineReader(self.fp, sock, deadline, maximum + 32768)
                except BaseException:
                    self.close()
                    raise
        # 复用固定SDK的绝对截止TCP/头部/正文读取，包含Connection:close后的socket。
        connection = _DeadlineConnection(self.host, self.port, self._address, deadline, None)
        connection.response_class = Response
        response = None
        try:
            connection.request('GET', path, headers={
                'X-QMT-Key-Id': self._key, 'X-QMT-Timestamp': stamp, 'X-QMT-Nonce': nonce,
                'X-QMT-Content-SHA256': digest, 'X-QMT-Signature': signature})
            response = connection.getresponse()
            raw = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                chunk = response.read1(min(8192, self.maximum + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                _require(len(raw) <= self.maximum)
            if time.monotonic() >= deadline:
                return False
            value = _json(bytes(raw))
            _require(response.status in (200, 503) and type(value) is dict
                     and value.get('schema_version') == 'qmt.trade-host-status.v2'
                     and value.get('failure') is None and value.get('hard_fault') is None
                     and value.get('closing') is False)
            if response.status == 503:
                return False
            _require(type(value.get('binding')) is dict and type(value.get('source_status')) is dict)
            return True
        except OSError:
            # TCP断开/超时可继续等待；BadStatusLine等HTTP协议错误交监督者报失败。
            # RemoteDisconnected同时属于ConnectionResetError，沿此连接分支处理。
            return False
        finally:
            try:
                if response is not None:
                    response.close()
            finally:
                connection.close()


class SourceWaitingExecution:
    """一个本地等待线程包装一个原执行owner；取得认证后只允许一次原start。

    本层的ready证明本地监督已启动；execution_ready沿原owner真实状态。
    状态读取无IO。request_close可来自控制线程，close在锁外沿首次停止D join。
    """
    def __init__(self, owner, probe, *, clock=time.monotonic):
        self._owner, self._probe, self._clock = owner, probe, clock
        self._lock, self._stop = threading.RLock(), threading.Event()
        self._condition = threading.Condition(self._lock)
        self._monitor = None
        self._attempted = self._starting = self._execution_claimed = False
        self._state, self._phase, self._error = 'new', 'waiting_source', None
        self._stop_deadline = None

    def status(self):
        """只组合原安全DTO；来源等待期间不虚构PID或策略结果。"""
        with self._lock:
            value = dict(self._owner.status())
            native_ready = value['ready']
            if self._state in ('new', 'ready', 'stopping', 'closed', 'faulted'):
                value['state'] = self._state
            local_ready = self._state == 'ready' and not self._stop.is_set()
            if self._phase == 'execution_started':
                local_ready = local_ready and native_ready
                if not native_ready and value.get('error_code') is not None:
                    value['state'] = 'faulted'
            value.update(ready=local_ready,
                         pending=value['pending'] or bool(self._monitor and self._monitor.pending),
                         error_code=self._error or value.get('error_code'),
                         execution_ready=native_ready, source_wait_state=self._phase)
            return value

    def start(self, deadline):
        """启动本地等待监督；原native启动预算从来源认证后开始，不重复启动。"""
        _require(type(deadline) in (int, float) and math.isfinite(deadline))
        with self._lock:
            if self._attempted or self._stop.is_set() or self._clock() >= deadline:
                return False
            self._attempted, self._starting = True, True
            self._monitor = ThreadOwner(target=self._run, name='execution-source-wait', daemon=True)
        try:
            self._monitor.start()
            with self._lock:
                if self._error is None and not self._stop.is_set() and self._clock() < deadline:
                    self._state = 'ready'
                    return True
            return False
        except BaseException:
            with self._lock:
                self._state, self._error = 'faulted', 'source_wait_start'
            self.request_close()
            return False
        finally:
            with self._condition:
                self._starting = False
                self._condition.notify_all()

    def _run(self):
        try:
            while not self._stop.is_set():
                if not self._probe(self._clock() + self._probe.seconds):
                    self._stop.wait(.2)
                    continue
                with self._lock:
                    if self._stop.is_set():
                        return
                    self._execution_claimed, self._phase = True, 'starting_execution'
                # 原owner处理启动与关闭竞态；已领取的这一次启动仍归原owner回收。
                started = self._owner.start(self._clock() + self._owner.startup_seconds)
                with self._lock:
                    if started:
                        self._phase = 'execution_started'
                    elif not self._stop.is_set():
                        self._state, self._error = 'faulted', 'execution_start'
                return
        except BaseException:
            with self._lock:
                self._state, self._error = 'faulted', 'source_wait_failed'
            self._owner.request_close()

    def request_close(self):
        """只通知原owner与本地等待；尚未接入来源时保持零次原执行启动。"""
        with self._lock:
            if self._stop_deadline is None:
                self._stop_deadline = self._clock() + self._owner.shutdown_seconds
            if self._state != 'closed':
                self._state = 'stopping'
            self._stop.set()
        self._owner.request_close()

    def close(self, timeout):
        """首次共用停止截止内先join本地线程，再由原owner证明原生资源关闭。"""
        _require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 <= timeout <= 120)
        self.request_close()
        with self._condition:
            self._stop_deadline = min(self._stop_deadline, self._clock() + timeout)
            deadline = self._stop_deadline
            # ThreadOwner还没尝试start时join可直接返回；等待这一次启动交接完成。
            while self._starting:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            monitor = self._monitor
        if monitor is not None and not monitor.join_until(deadline, clock=self._clock):
            return False
        if not self._owner.close(max(0, deadline - self._clock())):
            return False
        with self._lock:
            self._state = 'closed'
        return True
