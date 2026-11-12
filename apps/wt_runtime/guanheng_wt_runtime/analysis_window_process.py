"""WT 持有持续分析发布者；复用原 owner，状态与原关闭截止适配到 WRI。"""
from __future__ import annotations

import hashlib
import math
import threading
import time

from .managed_local_process import _duration, _json, _path, _read, _require, _sha


class AnalysisWindowProcess:
    """构造只装配，start 启动原发布线程；数据暂缺保留 owner 和上次窗口。

    ready 表示服务可运行，data_ready 单独表示已发布；来源等待错误只作状态展示。
    request_close 固定首次截止，close 只收紧，实际回收由原 producer 负责。
    """

    def __init__(self, owner, stop_seconds, *, clock=time.monotonic):
        _duration(stop_seconds, 120)
        self.owner, self.stop_seconds, self.clock = owner, stop_seconds, clock
        self._lock = threading.RLock()
        self._started, self._starting, self._closing, self._closed = False, False, False, False
        self._deadline = None

    @property
    def shutdown_seconds(self):
        """发布者原停止预算，供WT在组件换代时复用。"""
        return self.stop_seconds

    def start(self, deadline):
        _require(type(deadline) in (int, float) and math.isfinite(deadline))
        with self._lock:
            if self._started or self._closing or self.clock() >= deadline:
                return False
            self._started = self._starting = True
        try:
            self.owner.start(deadline=deadline)
        finally:
            with self._lock:
                self._starting = False
                if self._closing:
                    self.owner.request_close(deadline=self._deadline)
        with self._lock:
            return not self._closing and self.owner.status()['phase'] not in ('failed', 'stopped')

    def status(self):
        with self._lock:
            source = (dict(phase='constructed', last_success=None, published_count=0, error=None)
                      if self._starting else self.owner.status())
            failed = source['phase'] == 'failed'
            ready = self._started and not self._starting and not self._closing and not failed and source['phase'] != 'stopped'
            state = ('closed' if self._closed else 'stopping' if self._closing else 'starting' if self._starting else
                     'faulted' if failed or self._started and source['phase'] == 'stopped' else
                     'ready' if ready else 'new')
            return dict(schema='guanheng.analysis-window-process-status.v1',
                # 沿 WRI 公共状态字段供独立只读消费者显示；数据就绪仍单独表达。
                state=state, ready=ready, pending=self._starting or self._closing and not self._closed, forced=False,
                error_code='analysis_window_failed' if failed else None,
                phase=source['phase'], data_ready=source['last_success'] is not None,
                published_count=source['published_count'], last_success=source['last_success'],
                source_error=source['error'], closed=self._closed)

    def request_close(self):
        with self._lock:
            self._closing = True
            if self._deadline is None:
                self._deadline = self.clock() + self.stop_seconds
            if not self._starting:
                self.owner.request_close(deadline=self._deadline)

    def close(self, seconds):
        _require(type(seconds) in (int, float) and math.isfinite(seconds) and 0 <= seconds <= 120)
        with self._lock:
            if self._closed:
                return True
            self._closing = True
            end = self.clock() + min(seconds, self.stop_seconds)
            self._deadline = end if self._deadline is None else min(end, self._deadline)
            if self._starting:
                return False
            deadline = self._deadline
            self.owner.request_close(deadline=deadline)
        # join 放在包装层锁外；发布线程不需要通过本层来更新自己的状态。
        closed = self.owner.close(max(0., deadline-self.clock()))
        with self._lock:
            self._closed = closed
        return closed


def create_process(path, expected_sha256):
    """核原 descriptor 字节后组合固定 AWP 工厂；没有任意模块入口和网络探测。"""
    raw = _read(_path(path), 65536)
    _require(hashlib.sha256(raw).hexdigest() == _sha(expected_sha256))
    value = _json(raw)
    _require(type(value) is dict and set(value) == {'schema', 'configuration', 'stop_seconds'}
             and value['schema'] == 'guanheng.analysis-window-deployment.v1')
    _duration(value['stop_seconds'], 120)
    from guanheng_analysis_window_producer.runtime import create_producer
    return AnalysisWindowProcess(create_producer(value['configuration']), value['stop_seconds'])
