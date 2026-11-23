"""数据进程的有界私有失败旁证；不拥有业务收据、行情或恢复决策。"""
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import UUID


_ROOT = Path(__file__).parent
_PHASES = frozenset(('control_directory', 'configuration', 'credential', 'native_start',
    'daily_update_start', 'http_start', 'ready_publish', 'daily_update_check', 'daily_update_stop', 'daily_update_close',
    'stop_read', 'serving', 'close', 'receipt_publish', 'data_serve', 'data_resources_close',
    'data_close_receipt_publish'))
_TYPES = (TimeoutError, PermissionError, FileNotFoundError, ConnectionError, BrokenPipeError,
          OSError, ValueError, TypeError, KeyError, RuntimeError, AssertionError, OverflowError,
          MemoryError, Exception, BaseException)


def _number(value):
    return value if type(value) is int and -(2**31) <= value < 2**32 else None


def _exception(error):
    """只选择标准类别、系统码和本包位置；不格式化异常或读取源代码/局部变量。"""
    frames = deque(maxlen=8)
    cursor = error.__traceback__
    while cursor is not None:
        source = Path(cursor.tb_frame.f_code.co_filename)
        if source.parent == _ROOT and re.fullmatch(r'[a-z][a-z0-9_]{0,63}\.py', source.name):
            frames.append(dict(file=source.name, line=cursor.tb_lineno))
        cursor = cursor.tb_next
    return dict(
        exception_type=next(kind.__name__ for kind in _TYPES if isinstance(error, kind)),  # 有限内置异常类别。
        errno=_number(getattr(error, 'errno', None)) if isinstance(error, OSError) else None,  # 原系统errno。
        winerror=_number(getattr(error, 'winerror', None)) if isinstance(error, OSError) else None,  # 原Windows错误码。
        frames=list(frames))  # 最近8处本包文件名与行号，路径和源码行保持私有。


def _context(phase, error):
    result = dict(phase=phase if type(phase) is str and phase in _PHASES else 'unknown',  # 固定失败阶段。
                  captured_at=datetime.now(timezone.utc).isoformat(),  # 本次捕获的UTC时刻。
                  **_exception(error))
    causes, seen = [], {id(error)}
    for _ in range(2):
        cause = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
        if cause is None or id(cause) in seen:
            break
        seen.add(id(cause))
        causes.append(_exception(cause))
        error = cause
    result['causes'] = causes  # 原异常链最多2层，循环引用停止；不保存原异常对象。
    return result


class DataFailureDiagnostic:
    """本owner线程先存首错，关闭后更新同一旁证；不跨线程共享写入权。"""
    def __init__(self, publish, *, control_id, configuration_sha256, role):
        self._publish = publish  # 本owner已有的原子替换发布者，只接收diagnostic.json。
        self._identity = dict(control_id=None,  # 本控制代UUID，以下核后再填写。
            configuration_sha256=None,  # 本代配置摘要，以下核后再填写。
            pid=os.getpid(),  # 捕获进程的实际PID。
            role=role if role in ('source_market', 'daily_data') else 'unknown')  # 固定数据角色。
        try:
            if str(UUID(control_id)) == control_id:
                self._identity['control_id'] = control_id  # 控制代UUID，非法值保持未知且不阻断业务。
            if type(configuration_sha256) is str and re.fullmatch('[a-f0-9]{64}', configuration_sha256):
                self._identity['configuration_sha256'] = configuration_sha256  # 原配置摘要，不保存配置正文。
        except (ValueError, TypeError, AttributeError):
            pass
        self._failure = None  # 首次终止异常的去敏纯值；不保留异常对象或traceback引用。
        self._failure_id = None  # 仅在本轮异常传播中区分原异常与资源收口错误，不落盘、不保留对象。
        self._cleanup = {}  # 固定关闭阶段到第一次错误；重复阶段不累积历史。
        self._published = None  # 最近成功写入的规范字节，用于跳过同值重复写入。
        self._finished = False  # 收口只尝试一次，原发布者失败不会形成后台重试或额外线程。

    def _flush(self):
        if self._failure is None:
            return
        value = dict(schema='guanheng.data-process-diagnostic.v1',  # 私有诊断协议，独立于业务关闭收据。
            **self._identity,
            failure=self._failure,  # 原首错，不被后续发布或清理错误覆盖。
            cleanup_errors=list(self._cleanup.values()))  # 逐关闭阶段第一次错误，正常收尾为空。
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        if raw != self._published:
            self._publish('diagnostic.json', value)
            self._published = raw

    def capture(self, phase, error):
        """清理前保存首错，返回是否为同一原异常；诊断失败继续原异常传播。"""
        try:
            if self._failure is None:
                self._failure = _context(phase, error)
                self._failure_id = id(error)
                self._flush()
        except BaseException:
            pass
        return self._failure_id == id(error)

    @contextmanager
    def capture_scope(self, phase):
        """放在资源with的最后一项，在资源析构前固定原业务异常。"""
        try:
            yield
        except BaseException as error:
            self.capture(phase, error)
            raise

    def cleanup(self, phase, error):
        """只在内存收集固定关闭阶段，最终收口一次合并发布。"""
        try:
            if self._failure is None:
                self.capture(phase, error)
            else:
                value = _context(phase, error)
                self._cleanup.setdefault(value['phase'], value)
        except BaseException:
            pass

    def finish(self):
        """收口保存新增清理信息，或补存首次未写成的首错；正常路径零写入。"""
        if self._finished:
            return
        self._finished = True
        try:
            self._flush()
        except BaseException:
            pass
