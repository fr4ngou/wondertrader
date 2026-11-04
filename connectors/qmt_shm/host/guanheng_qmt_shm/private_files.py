"""Host-only private material creation with access control present at creation.

The explicit managed parent is trusted. Each new directory/file has the existing
IPC security owner's current-user protected DACL; files never pass through a
world-readable temporary name. Existing targets are retained on every failure.
"""
import ctypes
from ctypes import wintypes as w
import math
from pathlib import Path
import time

from guanheng_qmt_shm_agent.windows_security import SecurityAttributes, check, libraries, private_descriptor, SecurityResources


def create_private_directory(path):
    """Create one new absolute E: directory; its existing parent must resolve.

    E: is the host's generated-storage policy, not a QMT runtime path default.
    A failed/incomplete bundle remains private and cannot be silently replaced.
    """
    path = Path(path)
    if not path.is_absolute() or path.drive.upper() != "E:":
        raise ValueError("private bootstrap output requires an explicit absolute E: path")
    parent = path.parent.resolve(strict=True)
    if parent.drive.upper() != "E:" or not parent.is_dir():
        raise ValueError("private bootstrap parent must be an existing managed E: directory")
    target = parent / path.name
    kernel, security = libraries()
    kernel.CreateDirectoryW.argtypes, kernel.CreateDirectoryW.restype = [w.LPCWSTR, ctypes.POINTER(SecurityAttributes)], w.BOOL
    resources = SecurityResources(kernel)
    with resources.scope(implicit=True):
        descriptor = private_descriptor(kernel, security, resources=resources)
        attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
        check(kernel.CreateDirectoryW(str(target), ctypes.byref(attributes)))
    return target


def write_private_new(path, content, *, maximum_bytes=2097152):
    """独占创建私有bytes材料；默认2MiB，显式投影预算最大16MiB。

    No replace/retry/cleanup occurs. The caller writes the manifest last so a
    partial directory never qualifies as a complete paired bundle.
    """
    try:
        return _write_private_new(path, content, maximum_bytes=maximum_bytes)
    finally:
        content = None


def write_private_durable_new(path, content, deadline, clock=time.monotonic):
    """在同一原截止内独占写入、FlushFileBuffers并确认资源关闭。

    仅供终端外Host持久页使用；普通配对材料仍走原write_private_new行为。
    失败保留原位置及不确定的资源owner，不覆盖/重试/删除，也不授业务ACK。
    文件flush成功只声明该文件写入边界，不承诺断电后的目录事务原子性。
    Win32调用不可抢占；晚回按原D失败，调用者仍拥有正在执行的线程。
    """
    try:
        valid_deadline = type(deadline) in (int, float) and math.isfinite(deadline)
    except (OverflowError, ValueError):
        valid_deadline = False
    if not valid_deadline or not callable(clock):
        raise ValueError('durable private write requires an original finite deadline')

    def check_deadline():
        now = clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ValueError('durable private write requires a finite trusted clock')
        if now >= deadline:
            raise TimeoutError('original private write deadline elapsed')

    try:
        return _write_private_new(path, content, check_deadline)
    finally:
        content = None


def _write_private_new(path, content, check_deadline=None, *, maximum_bytes=2097152):
    """共用既有创建期DACL及SecurityResources；显式持久入口才执行flush。"""
    buffer = None
    try:
        if (type(maximum_bytes) is not int or not 1 <= maximum_bytes <= 16777216
                or not isinstance(content, bytes) or not 1 <= len(content) <= maximum_bytes):
            raise ValueError("private material exceeds its explicit bounded file budget")
        if check_deadline is not None:
            check_deadline()
        kernel, security = libraries()
        kernel.CreateFileW.argtypes, kernel.CreateFileW.restype = [w.LPCWSTR, w.DWORD, w.DWORD,
            ctypes.POINTER(SecurityAttributes), w.DWORD, w.DWORD, w.HANDLE], w.HANDLE
        kernel.WriteFile.argtypes, kernel.WriteFile.restype = [w.HANDLE, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID], w.BOOL
        if check_deadline is not None:
            kernel.FlushFileBuffers.argtypes, kernel.FlushFileBuffers.restype = [w.HANDLE], w.BOOL
        resources = SecurityResources(kernel)
        # scope持有输出slot及原异常；失败材料保持原位置，不能因释放失败假报成功。
        with resources.scope(implicit=True) as owned:
            descriptor = private_descriptor(kernel, security, resources=resources)
            handle = owned.handle(w.HANDLE())
            attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
            if check_deadline is not None:
                check_deadline()
            handle.value = kernel.CreateFileW(str(path), 0x40000000, 0, ctypes.byref(attributes), 1, 0x80, None)
            if handle.value == w.HANDLE(-1).value:
                # INVALID_HANDLE_VALUE从未授资源，避免关闭不属于caller的伪句柄。
                handle.value = None
                raise ctypes.WinError(ctypes.get_last_error())
            check(handle)
            if check_deadline is not None:
                check_deadline()
            buffer, count = ctypes.create_string_buffer(content), w.DWORD()
            if check_deadline is not None:
                check_deadline()
            check(kernel.WriteFile(handle, buffer, len(content), ctypes.byref(count), None))
            if check_deadline is not None:
                check_deadline()
            if count.value != len(content):
                raise OSError("private material write was incomplete")
            if check_deadline is not None:
                check(kernel.FlushFileBuffers(handle))
                check_deadline()
        # CloseHandle/LocalFree也必须成功，且不能把flush之后的晚回当作可ACK。
        if check_deadline is not None:
            check_deadline()
    finally:
        # 所有同步WinAPI和资源scope已返回；异常owner继续保句柄，不需保行情缓冲。
        content = buffer = None
