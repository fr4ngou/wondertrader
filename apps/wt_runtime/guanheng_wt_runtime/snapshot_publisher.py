"""运行展示快照的唯一发布owner；短暂共享冲突不改变组件生命周期。"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from uuid import uuid4


MAX_SNAPSHOT_BYTES = 65536  # 与现有Runtime状态读取上限一致，单位字节；单代仅保留一份候选。


# 保留观衡公开的文件发布时间；相同状态至多每秒刷新一次。
STATUS_HEARTBEAT_SECONDS = 1.0


def _encode(value):
    raw = json.dumps(value, ensure_ascii=True, allow_nan=False,
                     sort_keys=True, separators=(',', ':')).encode('ascii')
    if not 0 < len(raw) <= MAX_SNAPSHOT_BYTES:
        raise ValueError('runtime snapshot exceeds read capacity')
    return raw


class SnapshotPublisher:
    """串行接收最新状态，每次只尝试一次原子发布，不等待、不重试或延长原业务D。

    只有WinError32/33表示本轮暂缺；既有status保留原字节，下一正常周期提交最新值。
    所有其它编码/文件异常原样传播，由原Runtime失败收口及安全诊断处理。
    """
    def __init__(self, directory, *, replace):
        self.target = Path(directory) / 'status.json'  # 可重建展示投影；严格控制收据由原入口独立发布。
        self._candidate = Path(directory) / ('.status.json.' + str(uuid4()))  # 本owner唯一候选路径，首次独占创建。
        self._pending = False  # True表示已创建但尚未提交的自有候选；成功替换后恢复False。
        self._candidate_identity = None  # 自有候选句柄的设备/文件身份；复用前核同一文件，拒绝覆盖被换入的文件。
        self._replace = replace  # 已有SDK原子替换接缝，由调用者注入；不拥有其它文件或控制权限。

    @property
    def pending_file(self):
        """返回自有未发布文件的位置或None；不扫描目录、不承担其它owner文件的清理。"""
        return self._candidate if self._pending else None

    def publish(self, value):
        """一次提交最新值；True表示可见，False仅表示本轮32/33共享冲突。"""
        return self.publish_bytes(_encode(value))

    def publish_bytes(self, raw):
        """发布由本模块验证过的不可变快照字节。"""
        try:
            # 失败候选只在本owner下一次调用中改写，不排队旧状态或创建第二份临时文件。
            # 先完整关闭写句柄再替换；读者始终取得完整的上次或本次快照。
            with self._candidate.open('r+b' if self._pending else 'xb') as stream:
                info = os.fstat(stream.fileno())
                identity = (info.st_dev, info.st_ino)
                if self._pending:
                    if identity != self._candidate_identity or info.st_nlink != 1:
                        raise ValueError('runtime snapshot candidate owner differs')
                    stream.truncate(0)
                else:
                    self._candidate_identity = identity
                self._pending = True
                stream.write(raw)
            self._replace(self._candidate, self.target)
        except OSError as error:
            if type(getattr(error, 'winerror', None)) is int and error.winerror in (32, 33):
                return False
            raise
        self._pending = False
        self._candidate_identity = None
        return True



class BackgroundSnapshotPublisher:
    """常态只提交最新快照，首份和停止快照沿监督入口同步发布。"""
    def __init__(self, publisher, *, initial_published=None):
        self._publisher = publisher  # 初始发布结束后，普通写入只归工作线程。
        self._initial_published = None if initial_published is None else _encode(initial_published)  # 已发布的首帧。
        self._initial_time = time.monotonic()  # 首帧发布和工作线程交接时点。
        self._condition = threading.Condition()  # 只保护候选和回执；持锁期间不写盘。
        self._pending = None  # 未处理的最近一次提交字节；新状态覆盖此槽。
        self._failure = None  # 首个后台失败，由监督循环或关闭路径重新抛出。
        self._closing = False  # 关闭后后台退出，监督者在确认 join 后接管最终发布。
        self._thread = threading.Thread(target=self._run, name='wt-status-writer', daemon=True)
        self._thread.start()

    def submit(self, value):
        """在监督线程编码快照并交接，重抛已经发生的写入错误。"""
        raw = _encode(value)
        with self._condition:
            if self._failure is not None:
                raise self._failure
            self._pending = raw
            self._condition.notify()

    def _run(self):
        last_published, published_at = self._initial_published, self._initial_time
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._closing or self._pending is not None)
                    if self._closing:
                        return
                    raw, self._pending = self._pending, None
                now = time.monotonic()
                if raw == last_published and now - published_at < STATUS_HEARTBEAT_SECONDS:
                    continue
                if self._publisher.publish_bytes(raw):
                    last_published, published_at = raw, time.monotonic()
        except Exception as error:
            with self._condition:
                self._failure = error

    def stop(self, seconds):
        """在既有关闭预算内收回文件写入权；即使发生错误也先确认线程退出。"""
        with self._condition:
            self._closing = True
            self._pending = None
            self._condition.notify()
        self._thread.join(seconds)
        if self._thread.is_alive():
            raise TimeoutError('runtime snapshot writer stop deadline')
        if self._failure is not None:
            raise self._failure
