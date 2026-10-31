"""分析读取的停止准入；原 HTTP、请求身份和结果持久化继续归原客户端。"""
import math
import threading

from integrations.guanheng.source_history_transport import BoundHistorySource


def admit_read(transport, deadline):
    """部署运输在 slot 读取前准入；自定义同步运输继续原接口。"""
    admit = getattr(transport, 'admit_read', None)
    if admit is not None:
        admit(deadline)


class AnalysisReadTransport(BoundHistorySource):
    """发布线程独占运输，关闭线程仅发布停止事件及首次截止。

    每个 slot 读取前检查停止，已准入 slot 保留一次原首次 POST 权利，
    避免公共客户端先保存 attempted 后被截成实际上未派发的未知责任。
    其余交换/plan 检查停止；已进入的 HTTP 沿原有界 RPC 返回。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._closing = threading.Event()
        self._close_guard = threading.Lock()
        self._close_deadline = None
        self._dispatch_admitted = False

    def request_close(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('analysis_close_deadline')
        with self._close_guard:
            self._close_deadline = (deadline if self._close_deadline is None else
                                   min(deadline, self._close_deadline))
            self._closing.set()

    def _admit(self, deadline, *, begin=False, dispatch=False):
        with self._close_guard:
            if dispatch and self._dispatch_admitted:
                self._dispatch_admitted = False
                return min(deadline, self._close_deadline) if self._close_deadline is not None else deadline
            if self._closing.is_set():
                from .source import SourcePending
                raise SourcePending('analysis_refresh_interrupted')
            if begin:
                self._dispatch_admitted = True
            return deadline

    def admit_read(self, deadline):
        self._admit(deadline, begin=True)

    def exchange(self, method, path, body, deadline):
        first_post = method == 'POST' and path.startswith('/internal/v1/bound-operations/')
        return super().exchange(method, path, body, self._admit(deadline, dispatch=first_post))

    def plan(self, operation, arguments, metadata, deadline):
        return super().plan(operation, arguments, metadata, self._admit(deadline))
