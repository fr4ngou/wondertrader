"""原历史服务内的显式数据生产者；复用持续入口，读取线程继续独占原Reader。"""
import os
from pathlib import Path
import threading
import time
import uuid

from ..guanheng_market_client import strict_json
from .daily_data_service import serve
from .daily_data_update import _save
from .market_generation import read_fixed


class MarketDailyOwner:
    """外层SMP/WT Job拥有本线程及最终物理截止；本对象只管理独有控制代。"""
    def __init__(self, configuration, parent_directory):
        self.configuration = dict(configuration)  # 固定数据配置path/sha256，凭据沿原环境。
        self.control_id = str(uuid.uuid4())  # 本次线程owner独立控制UUID，重启不复用旧stop。
        parent = Path(parent_directory) / 'daily-update'
        parent.mkdir(exist_ok=False)
        self.directory = parent / self.control_id  # 控制回执归SMP本代目录；持久数据任务在配置指定根。
        self.thread = None  # 原持续入口的唯一数据线程；close确认join，硬阻塞归父Job。
        self.error_type = None  # 线程终止的固定异常类型，成功为空，不保存来源或凭据正文。
        self._stop_deadline = None  # 已请求的最早关闭截止（单调秒），重复关闭不延长。
        self._written_deadline = None  # 已成功保存stop的截止；目录尚未出现时由close继续保存同一原D。

    def _run(self):
        try:
            serve(self.configuration, self.directory, self.control_id)
        except BaseException as error:
            self.error_type = type(error).__name__

    def start(self, deadline, stop_request=lambda: None):
        """当前SMP线程启动并等待数据owner真正取得发布租约；超期交外层统一收束。"""
        if self.thread is not None:
            raise RuntimeError('market daily owner already started')
        self.thread = threading.Thread(target=self._run, name='wt-daily-data-owner', daemon=False)
        self.thread.start()
        ready = self.directory / 'ready.json'
        while time.monotonic() < deadline:
            requested = stop_request()
            if requested is not None:
                self.request_close(requested)
                raise InterruptedError('market daily startup stopped')
            if ready.exists():
                value = strict_json(read_fixed(ready, maximum=65536))
                if (value.get('control_id') != self.control_id or value.get('pid') != os.getpid()
                        or value.get('configuration_sha256') != self.configuration['sha256']):
                    raise ValueError('market daily ready identity differs')
                return
            if not self.thread.is_alive():
                raise RuntimeError('market daily owner failed before ready')
            time.sleep(.02)
        raise TimeoutError('market daily owner startup deadline')

    def check(self):
        """日轮次来源失败由原入口保旧重试；整个owner意外退出由SMP显式上报。"""
        if self.thread is not None and not self.thread.is_alive():
            raise RuntimeError('market daily owner stopped unexpectedly')

    def request_close(self, deadline):
        if self.thread is None or not self.thread.is_alive():
            return
        self._stop_deadline = deadline if self._stop_deadline is None else min(self._stop_deadline, deadline)
        if self.directory.exists() and self._written_deadline != self._stop_deadline:
            _save(self.directory / 'stop.json', dict(
                schema='guanheng.daily-data-stop.v1',  # 原持续入口停止协议。
                control_id=self.control_id,  # 只控制本轮数据线程，不影响其他服务代。
                deadline=self._stop_deadline))  # 沿原最早关闭截止的单调秒值。
            self._written_deadline = self._stop_deadline

    def close(self, deadline):
        """使用调用者原D；线程仍活跃时抛超时，SMP不得发布成功closed回执。"""
        self.request_close(deadline)
        if self._stop_deadline is not None:deadline=min(deadline,self._stop_deadline)
        if self.thread is None:
            return
        while self.thread.is_alive() and time.monotonic() < deadline:
            self.request_close(deadline)
            self.thread.join(min(.05, max(0., deadline - time.monotonic())))
        if self.thread.is_alive():
            raise TimeoutError('market daily owner remains active')
        closed = strict_json(read_fixed(self.directory / 'closed.json', maximum=65536))
        if (self.error_type is not None or closed.get('control_id') != self.control_id
                or closed.get('pid') != os.getpid() or closed.get('owner_closed') is not True
                or closed.get('error_type') is not None or closed.get('close_deadline_exceeded') is not False):
            raise RuntimeError('market daily owner did not close cleanly')
