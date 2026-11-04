"""运行边界的最小失败诊断；不复制异常正文、路径、参数或金融状态。"""
from __future__ import annotations


_PHASES = frozenset((
    'runtime_construct', 'signal_register', 'runtime_start',
    'initial_status_snapshot', 'initial_status_publish', 'ready_publish',
    'stop_poll', 'loop_status_snapshot', 'loop_status_publish',
    'stop_read', 'stop_validate', 'component_check', 'close_request', 'cycle_wait',
    'runtime_close', 'final_status_snapshot', 'final_status_publish',
    'signal_restore', 'receipt_publish',
))
_TYPES = (FileNotFoundError, PermissionError, FileExistsError, TimeoutError,
          BrokenPipeError, ConnectionError, OSError, ValueError, TypeError,
          KeyError, RuntimeError, AssertionError, OverflowError, MemoryError, Exception)


def _integer(value):
    return value if type(value) is int and -(2**31) <= value < 2**31 else None


def _event(phase, error):
    # 类型只取有限内置类别；自定义类名、args/filename/cause/traceback均可能携带秘密。
    return dict(phase=phase if phase in _PHASES else 'unknown',
        exception_type=next((kind.__name__ for kind in _TYPES if isinstance(error, kind)), 'Exception'),
        errno=_integer(getattr(error, 'errno', None)) if isinstance(error, OSError) else None,
        winerror=_integer(getattr(error, 'winerror', None)) if isinstance(error, OSError) else None)


class FailureDiagnostic:
    """先纯值记录，原收口结束后另写版本化旁证；诊断写失败保持原异常和退出结果。"""
    def __init__(self, directory, identity, publish):
        self.directory = directory  # 本代原控制目录；只发布固定diagnostic.json，不采集或输出目录正文。
        self.identity = identity  # 原control/instance/PID/config摘要；不含凭证、账户或业务结果。
        self.publish = publish  # 原严格发布接缝；旁证写入失败不改变原异常、清理及退出结果。
        self.phase = 'runtime_construct'  # 当前边界固定阶段，捕获时只认_PHASES白名单。
        self.failure = None  # 首次异常的纯值分类；None表示未观察异常，后续清理错误独立保存。

    def __enter__(self):
        return self

    def capture(self, error):
        if self.failure is None:
            try:
                self.failure = _event(self.phase, error)
            except Exception:
                pass

    def __exit__(self, kind, error, traceback):
        secondary = None
        if isinstance(error, Exception):
            if self.failure is None:
                self.capture(error)
            else:
                try:
                    secondary = _event(self.phase, error)
                except Exception:
                    pass
        if self.failure is not None:
            try:
                self.publish(self.directory, 'diagnostic.json', dict(
                    schema='guanheng.wt-runtime-diagnostic.v1', **self.identity,
                    failure=self.failure, cleanup_failure=secondary))
            except Exception:
                pass
        return False
