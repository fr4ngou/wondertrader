"""Own one suspended Windows command tree inside the caller's outer Job.

The nested Job supplies command cancellation. An outer creation-bound Job owns
Popen's pre-assignment interval; this module does not claim atomic creation membership.
"""
import ctypes as C
from ctypes import wintypes as W
import math
import time


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64),
                ("flags", W.DWORD), ("minimum", C.c_size_t), ("maximum", C.c_size_t),
                ("active", W.DWORD), ("affinity", C.c_size_t),
                ("priority", W.DWORD), ("scheduling", W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", C.c_uint64 * 6),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]


class ThreadEntry(C.Structure):
    _fields_ = [("size", W.DWORD), ("usage", W.DWORD), ("id", W.DWORD),
                ("owner", W.DWORD), ("base_priority", W.LONG),
                ("delta_priority", W.LONG), ("flags", W.DWORD)]


class BasicAccounting(C.Structure):
    # SDK JOBOBJECT_BASIC_ACCOUNTING_INFORMATION；与既有App Job的信息类1相同。
    _fields_ = [("user_time", C.c_int64), ("kernel_time", C.c_int64),
                ("period_user_time", C.c_int64), ("period_kernel_time", C.c_int64),
                ("page_faults", W.DWORD), ("total", W.DWORD),
                ("active", W.DWORD), ("terminated", W.DWORD)]


class ProcessJob:
    def __init__(self):
        self.api = C.WinDLL("kernel32", use_last_error=True)
        self.handle = None
        self.assigned = self.member_before_resume = self.resumed = False
        self._thread = self._snapshot = None
        signatures = {
            "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
            "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
            "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
            "IsProcessInJob": ([W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
            "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
            "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
            "CreateToolhelp32Snapshot": ([W.DWORD, W.DWORD], W.HANDLE),
            "Thread32First": ([W.HANDLE, C.POINTER(ThreadEntry)], W.BOOL),
            "Thread32Next": ([W.HANDLE, C.POINTER(ThreadEntry)], W.BOOL),
            "OpenThread": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            "ResumeThread": ([W.HANDLE], W.DWORD),
            "CloseHandle": ([W.HANDLE], W.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            self.handle = None
            raise C.WinError(C.get_last_error())
        # handle一经取得就由本owner保护；布局/参数构造及FFI本身也可能抛错。
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)):
                raise C.WinError(C.get_last_error())
        except BaseException as error:
            try:
                self.close()
            except BaseException as secondary:
                self._secondary(error, secondary)
                try:
                    error._native_cleanup_owner = self
                except BaseException:
                    pass  # 原traceback仍持有__init__帧的self，不覆盖首因。
            raise

    @staticmethod
    def _secondary(first, error):
        try:
            previous = tuple(getattr(first, "_native_cleanup_errors", ()))
            first._native_cleanup_errors = (previous + (error,))[:8]
        except BaseException:
            pass

    @staticmethod
    def _check_deadline(deadline):
        if deadline is not None:
            if type(deadline) not in (int, float) or not math.isfinite(deadline):
                raise ValueError("finite absolute native start deadline required")
            if time.monotonic() >= deadline:
                raise TimeoutError("original native process start deadline elapsed")

    def _close_start_handles(self):
        first = None
        for name in ("_thread", "_snapshot"):
            handle = getattr(self, name)
            if handle is not None:
                try:
                    if not self.api.CloseHandle(handle):
                        raise C.WinError(C.get_last_error())
                    setattr(self, name, None)
                except BaseException as error:
                    if first is None:
                        first = error
                    else:
                        self._secondary(first, error)
        if first is not None:
            raise first

    def attach_and_resume(self, process, *, deadline=None):
        self._check_deadline(deadline)
        if self.assigned or not self.handle:
            raise RuntimeError("native Job attach requires its original empty owner")
        primary = None
        try:
            if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
                raise C.WinError(C.get_last_error())
            self.assigned = True
            self._check_deadline(deadline)
            inside = W.BOOL()
            if not self.api.IsProcessInJob(int(process._handle), self.handle, C.byref(inside)) or not inside.value:
                raise OSError("native command Job membership remains unconfirmed")
            self.member_before_resume = True
            self._check_deadline(deadline)
            self._snapshot = self.api.CreateToolhelp32Snapshot(0x4, 0)
            if self._snapshot == C.c_void_p(-1).value:
                self._snapshot = None
                raise C.WinError(C.get_last_error())
            self._check_deadline(deadline)
            entry = ThreadEntry()
            entry.size = C.sizeof(entry)
            available = self.api.Thread32First(self._snapshot, C.byref(entry))
            while available:
                self._check_deadline(deadline)
                if entry.owner == process.pid:
                    self._thread = self.api.OpenThread(0x2, False, entry.id)
                    if not self._thread:
                        self._thread = None
                        raise C.WinError(C.get_last_error())
                    self._check_deadline(deadline)
                    if self.api.ResumeThread(self._thread) != 1:
                        raise OSError("native command primary suspend count or Resume failed")
                    self.resumed = True
                    break
                available = self.api.Thread32Next(self._snapshot, C.byref(entry))
            if not self.resumed:
                raise RuntimeError("suspended command primary thread was not found")
        except BaseException as error:
            primary = error
        try:
            self._close_start_handles()
        except BaseException as secondary:
            if primary is None:
                primary = secondary
            else:
                self._secondary(primary, secondary)
        if primary is not None:
            raise primary.with_traceback(primary.__traceback__)

    def terminate(self):
        """只请求整树终止；保留Job handle供真实活动数/关闭续核。"""
        if self.handle and not self.api.TerminateJobObject(self.handle, 1):
            raise C.WinError(C.get_last_error())

    def active_processes(self):
        if self.handle is None:
            raise RuntimeError("native Job handle closed; active count is unavailable")
        value = BasicAccounting()
        if not self.api.QueryInformationJobObject(self.handle, 1, C.byref(value), C.sizeof(value), None):
            raise C.WinError(C.get_last_error())
        return value.active

    def close(self):
        # 失败身份原位保持；先前start-handle关闭失败也不跳过Job句柄。
        first = None
        try:
            self._close_start_handles()
        except BaseException as error:
            first = error
        if self.handle is not None:
            try:
                if not self.api.CloseHandle(self.handle):
                    raise C.WinError(C.get_last_error())
                self.handle = None
            except BaseException as error:
                if first is None:
                    first = error
                else:
                    self._secondary(first, error)
        if first is not None:
            raise first
