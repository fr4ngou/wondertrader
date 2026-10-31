"""Windows独占进程树。沿已验process_job的Job限制，创建时通过JobList指定归属。

来源：scripts/native_support/process_job.py（冻结SHA c6ede7a2...3b3bb72ae）。
使用STARTUPINFOEX Job列表填补CreateProcess返回前父死亡窗口，随后在挂起态
再次核成员身份，再Resume；只持有并终止本对象创建的进程。
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import io
import math
import msvcrt
import os
import subprocess
import time


class _Basic(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64),
                ("flags", W.DWORD), ("minimum", C.c_size_t), ("maximum", C.c_size_t),
                ("active", W.DWORD), ("affinity", C.c_size_t), ("priority", W.DWORD),
                ("scheduling", W.DWORD)]


class _Limits(C.Structure):
    _fields_ = [("basic", _Basic), ("io", C.c_uint64 * 6),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]


class _Security(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p), ("inherit", W.BOOL)]


class _Startup(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR),
                ("title", W.LPWSTR), ("x", W.DWORD), ("y", W.DWORD),
                ("xsize", W.DWORD), ("ysize", W.DWORD), ("xchars", W.DWORD),
                ("ychars", W.DWORD), ("fill", W.DWORD), ("flags", W.DWORD),
                ("show", W.WORD), ("reserved_size", W.WORD), ("reserved2", C.c_void_p),
                ("stdin", W.HANDLE), ("stdout", W.HANDLE), ("stderr", W.HANDLE)]


class _StartupEx(C.Structure):
    _fields_ = [("startup", _Startup), ("attributes", C.c_void_p)]


class _Information(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE),
                ("pid", W.DWORD), ("tid", W.DWORD)]



class _Accounting(C.Structure):
    # Windows SDK JOBOBJECT_BASIC_ACCOUNTING_INFORMATION；Query信息类1。
    _fields_ = [("user_time", C.c_int64), ("kernel_time", C.c_int64),
                ("period_user_time", C.c_int64), ("period_kernel_time", C.c_int64),
                ("page_faults", W.DWORD), ("total", W.DWORD),
                ("active", W.DWORD), ("terminated", W.DWORD)]


class ProcessJob:
    """一个创建期Job归属和真实整树回收owner。

    close_job请求停止并私有保留Job句柄；wait核Job ActiveProcesses=0及root。
    close_reaped在调用者已排空管道后逐项关资源，成功才清引用；失败可续核。
    构造不创建OS资源，start先登记所有权再分配，避免构造抛出丢失句柄。
    """

    def __init__(self):
        if os.name != "nt":
            raise OSError("策略宿主需要Windows Job")
        self.api = C.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
            "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
            "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
            "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
            "IsProcessInJob": ([W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
            "InitializeProcThreadAttributeList": ([C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)], W.BOOL),
            # Win32第七参数lpReturnSize是PSIZE_T；两个保留输出均传NULL，声明仍须完整。
            "UpdateProcThreadAttribute": ([C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p, C.c_size_t, C.c_void_p, C.POINTER(C.c_size_t)], W.BOOL),
            "DeleteProcThreadAttributeList": ([C.c_void_p], None),
            "CreatePipe": ([C.POINTER(W.HANDLE), C.POINTER(W.HANDLE), C.POINTER(_Security), W.DWORD], W.BOOL),
            "SetHandleInformation": ([W.HANDLE, W.DWORD, W.DWORD], W.BOOL),
            "CreateFileW": ([W.LPCWSTR, W.DWORD, W.DWORD, C.POINTER(_Security), W.DWORD, W.DWORD, W.HANDLE], W.HANDLE),
            "CreateProcessW": ([W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.c_void_p, C.POINTER(_Information)], W.BOOL),
            "OpenProcess": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            "ResumeThread": ([W.HANDLE], W.DWORD),
            "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
            "GetExitCodeProcess": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
            "CloseHandle": ([W.HANDLE], W.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = arguments, result
        self.handle = self._closing_job = None
        self._information = _Information()
        self.stdout = self.stderr = None
        self.member_before_resume = False
        self._started = self._closed = False
        # OS输出指针预先归owner；CreatePipe部分失败也保留实际写出的句柄。
        self._pipe_handles = [(W.HANDLE(), W.HANDLE()), (W.HANDLE(), W.HANDLE())]
        self._pipe_fds = [None, None]
        self._stdin = W.HANDLE()

    @property
    def process(self):
        return self._information.process

    @process.setter
    def process(self, value):
        self._information.process = value

    @property
    def thread(self):
        return self._information.thread

    @thread.setter
    def thread(self, value):
        self._information.thread = value

    @property
    def pid(self):
        return self._information.pid or None

    def _close_handle(self, value):
        if value is not None and not self.api.CloseHandle(value):
            raise C.WinError(C.get_last_error())

    def _close_start_handles(self):
        # 即使某项失败仍尝试其他独立项；失败项身份原位保留，wait会重试。
        failure = None
        for slot in [self._stdin, *(slot for pair in self._pipe_handles for slot in pair)]:
            if slot.value not in (None, C.c_void_p(-1).value):
                try:
                    self._close_handle(slot.value)
                    slot.value = None
                except BaseException as exc:
                    failure = failure or exc
        if self.thread:
            try:
                self._close_handle(self.thread)
                self.thread = None
            except BaseException as exc:
                failure = failure or exc
        if failure is not None:
            raise failure

    @staticmethod
    def _check_start(deadline, clock):
        if deadline is not None and clock() >= deadline:
            raise TimeoutError("原创建期限已耗尽，保持挂起或不再创建")

    def _membership(self):
        inside = W.BOOL()
        if not self.api.IsProcessInJob(self.process, self.handle, C.byref(inside)) or not inside.value:
            raise OSError("子进程尚未归入本轮Job")
        self.member_before_resume = True

    def _resume(self):
        if self.api.ResumeThread(self.thread) != 1:
            raise OSError("子进程挂起计数或Resume失败")

    def start(self, argv: tuple[str, ...], cwd: str, *, deadline=None, clock=time.monotonic):
        """可选deadline沿调用者原单调钟域；省略保持旧调用形状。

        CreateProcess成功晚回时_information已经属于owner，禁止Resume，交原回收链。
        """
        if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
            raise ValueError("创建期限必须为有限单调时刻")
        if self._started or self._closed:
            raise OSError("Job只允许创建一次进程")
        self._check_start(deadline, clock)
        self._started = True
        attributes = None
        initialized = False
        try:
            self.handle = self.api.CreateJobObjectW(None, None)
            if not self.handle:
                self.handle = None
                raise C.WinError(C.get_last_error())
            self._check_start(deadline, clock)
            limits = _Limits()
            limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE，含父进程死亡。
            if not self.api.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)):
                raise C.WinError(C.get_last_error())
            self._check_start(deadline, clock)
            security = _Security(C.sizeof(_Security), None, True)
            for read, write in self._pipe_handles:
                if not self.api.CreatePipe(C.byref(read), C.byref(write), C.byref(security), 0):
                    raise C.WinError(C.get_last_error())
                self._check_start(deadline, clock)
                if not self.api.SetHandleInformation(read, 1, 0):
                    raise C.WinError(C.get_last_error())
                self._check_start(deadline, clock)
            self._stdin.value = self.api.CreateFileW("NUL", 0x80000000, 3, C.byref(security), 3, 0x80, None)
            if self._stdin.value in (None, C.c_void_p(-1).value):
                self._stdin.value = None
                raise C.WinError(C.get_last_error())
            self._check_start(deadline, clock)
            size = C.c_size_t()
            self.api.InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
            self._check_start(deadline, clock)
            attributes = C.create_string_buffer(size.value)
            if not self.api.InitializeProcThreadAttributeList(attributes, 2, 0, C.byref(size)):
                raise C.WinError(C.get_last_error())
            initialized = True
            self._check_start(deadline, clock)
            jobs = (W.HANDLE * 1)(self.handle)
            inherited = (W.HANDLE * 3)(self._stdin.value, *(pair[1].value for pair in self._pipe_handles))
            for key, values in ((0x2000D, jobs), (0x20002, inherited)):
                if not self.api.UpdateProcThreadAttribute(attributes, 0, key, values, C.sizeof(values), None, None):
                    raise C.WinError(C.get_last_error())
                self._check_start(deadline, clock)
            startup = _StartupEx()
            startup.startup.cb = C.sizeof(_StartupEx)
            startup.startup.flags = 0x100
            startup.startup.stdin = self._stdin.value
            startup.startup.stdout, startup.startup.stderr = (pair[1].value for pair in self._pipe_handles)
            startup.attributes = C.cast(attributes, C.c_void_p)
            command = C.create_unicode_buffer(subprocess.list2cmdline(argv))
            self._check_start(deadline, clock)
            if not self.api.CreateProcessW(argv[0], command, None, None, True, 4 | 0x80000 | 0x08000000,
                                          None, cwd, C.byref(startup), C.byref(self._information)):
                raise C.WinError(C.get_last_error())
            self._check_start(deadline, clock)
            self._membership()
            self._check_start(deadline, clock)
            for index, name in enumerate(("stdout", "stderr")):
                read = self._pipe_handles[index][0]
                self._pipe_fds[index] = msvcrt.open_osfhandle(read.value, os.O_RDONLY | os.O_BINARY)
                read.value = None  # CRT fd接管，之后只由_pipe_fds关闭。
                self._check_start(deadline, clock)
                # 不把fd所有权再隐式转给FileIO，构造失败仍由明确槽负责。
                setattr(self, name, io.FileIO(self._pipe_fds[index], "rb", closefd=False))
                self._check_start(deadline, clock)
            self._check_start(deadline, clock)
            self._resume()
            self._check_start(deadline, clock)
        finally:
            try:
                if initialized:
                    self.api.DeleteProcThreadAttributeList(attributes)
            finally:
                self._close_start_handles()

    def poll(self):
        if self.process is None:
            return None
        state = self.api.WaitForSingleObject(self.process, 0)
        if state == 0x102:
            return None
        if state != 0:
            raise C.WinError(C.get_last_error())
        value = W.DWORD()
        if not self.api.GetExitCodeProcess(self.process, C.byref(value)):
            raise C.WinError(C.get_last_error())
        return value.value

    def active_processes(self):
        """持有Job时查询OS整树活动计数，包含root；不枚举PID快照。"""
        handle = self.handle if self.handle is not None else self._closing_job
        if handle is None:
            return 0
        value = _Accounting()
        if not self.api.QueryInformationJobObject(handle, 1, C.byref(value), C.sizeof(value), None):
            raise C.WinError(C.get_last_error())
        return value.active

    def wait(self, seconds: float):
        if type(seconds) not in (int, float) or not math.isfinite(seconds):
            raise ValueError("等待预算必须有限")
        deadline = time.monotonic() + max(0, seconds)
        self._close_start_handles()
        while self.active_processes():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("同一总期限内尚未确认Job整树退出")
            time.sleep(min(.01, remaining))
        if self.process is not None:
            remaining = max(0, deadline - time.monotonic())
            state = self.api.WaitForSingleObject(self.process, min(0xfffffffe, int(remaining * 1000)))
            if state == 0x102:
                raise TimeoutError("同一总期限内尚未确认root退出")
            if state != 0:
                raise C.WinError(C.get_last_error())
        return self.poll()

    def close_job(self):
        # 不关闭唯一Job OS句柄来猜测终止完成；保留它查询整树计数直到close_reaped。
        if self.handle is not None:
            if not self.api.TerminateJobObject(self.handle, 1):
                raise C.WinError(C.get_last_error())
            self._closing_job = self.handle
            self.handle = None
        self._close_start_handles()

    def close_reaped(self):
        """调用者须先join管道线程；每项关闭失败原位保留，下次可续核。"""
        if self._closed:
            return
        # 即便root已经退出也核整个Job；未知计数/失败均不清除任何活进程身份。
        self.wait(0)
        self.close_job()
        self.wait(0)
        for index, name in enumerate(("stdout", "stderr")):
            pipe = getattr(self, name)
            if pipe is not None:
                pipe.close()
                setattr(self, name, None)
            if self._pipe_fds[index] is not None:
                os.close(self._pipe_fds[index])
                self._pipe_fds[index] = None
        if self.process is not None:
            self._close_handle(self.process)
            self.process = None
        if self._closing_job is not None:
            self._close_handle(self._closing_job)
            self._closing_job = None
        self._closed = True
