# -*- coding: utf-8 -*-
"""Current-user kernel-object ownership shared by local IPC adapters.

Only normal-user TOKEN_QUERY is used. Descriptor memory is owned by the caller
until object creation completes, then released with LocalFree. Opened objects
must retain an explicit protected DACL for the same SID; a name is not trust.
"""
import ctypes
from ctypes import wintypes as w
import os
import threading
from datetime import datetime, timedelta, timezone


class SecurityAttributes(ctypes.Structure):
    _fields_ = [("nLength", w.DWORD), ("lpSecurityDescriptor", w.LPVOID), ("bInheritHandle", w.BOOL)]


class _SidAttributes(ctypes.Structure):
    _fields_ = [("Sid", w.LPVOID), ("Attributes", w.DWORD)]


class _Acl(ctypes.Structure):
    _fields_ = [("AclRevision", w.BYTE), ("Sbz1", w.BYTE), ("AclSize", w.WORD),
                ("AceCount", w.WORD), ("Sbz2", w.WORD)]


class _AceHeader(ctypes.Structure):
    _fields_ = [("AceType", w.BYTE), ("AceFlags", w.BYTE), ("AceSize", w.WORD)]


SECURITY_MAX_SID_SIZE = 68
SE_KERNEL_OBJECT = 6
OWNER_AND_DACL_SECURITY_INFORMATION = 5
SE_DACL_PRESENT_AND_PROTECTED = 0x1004
GENERIC_ALL = 0x10000000


def check(ok):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return ok


def libraries():
    if os.name != "nt":
        raise OSError("local Win32 IPC requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    for name, (arguments, result) in {
        "GetCurrentProcess": ([], w.HANDLE), "GetCurrentProcessId": ([], w.DWORD),
        "ProcessIdToSessionId": ([w.DWORD, ctypes.POINTER(w.DWORD)], w.BOOL),
        "CloseHandle": ([w.HANDLE], w.BOOL), "LocalFree": ([w.LPVOID], w.LPVOID),
    }.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = arguments, result
    for name, (arguments, result) in {
        "OpenProcessToken": ([w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL),
        "GetTokenInformation": ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)], w.BOOL),
        "ConvertSidToStringSidW": ([w.LPVOID, ctypes.POINTER(w.LPWSTR)], w.BOOL),
        "ConvertStringSecurityDescriptorToSecurityDescriptorW":
            ([w.LPCWSTR, w.DWORD, ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.DWORD)], w.BOOL),
        "GetLengthSid": ([w.LPVOID], w.DWORD), "IsValidSid": ([w.LPVOID], w.BOOL),
        "GetSecurityInfo": ([w.HANDLE, w.DWORD, w.DWORD] + [ctypes.POINTER(w.LPVOID)] * 5, w.DWORD),
        "GetSecurityDescriptorControl": ([w.LPVOID, ctypes.POINTER(w.WORD), ctypes.POINTER(w.DWORD)], w.BOOL),
        "GetAce": ([w.LPVOID, w.DWORD, ctypes.POINTER(w.LPVOID)], w.BOOL),
    }.items():
        function = getattr(security, name)
        function.argtypes, function.restype = arguments, result
    return kernel, security


def _sid_bytes(security, pointer, available=None):
    if not pointer or not security.IsValidSid(pointer):
        raise OSError("invalid kernel SID")
    size = security.GetLengthSid(pointer)
    if not 8 <= size <= SECURITY_MAX_SID_SIZE or available is not None and size > available:
        raise OSError("invalid bounded kernel SID")
    return ctypes.string_at(pointer, size)



class SecurityResourceError(OSError):
    """固定去敏失败；resources保留实际slot，original保留原异常对象。"""
    def __init__(self, resources, original=None):
        OSError.__init__(self, "Windows security resource release is unconfirmed")
        self.resources, self.original = resources, original


class SecurityResources(object):
    """原线程拥有最多16个输出slot；API成功释放才清空，不推断失败等同已释放。"""
    def __init__(self, kernel, max_slots=16):
        if type(max_slots) is not int or not 1 <= max_slots <= 16:
            raise ValueError("invalid security resource capacity")
        self.kernel, self.max_slots = kernel, max_slots
        self.owner = threading.current_thread()
        self._slots = []
        self.cleanup_failure = None

    def _owner(self):
        if threading.current_thread() is not self.owner:
            raise RuntimeError("Windows security resources belong to their original thread")

    @property
    def closed(self):
        return not self._slots

    def _track(self, slot, kind):
        self._owner()
        if len(self._slots) >= self.max_slots:
            raise RuntimeError("Windows security resource capacity exhausted")
        self._slots.append((slot, kind))
        return slot

    def _entry(self, slot):
        for entry in self._slots:
            if entry[0] is slot:
                return entry
        raise RuntimeError("Windows security resource is not owned")

    def detach(self, slot):
        """只用于旧API把成功descriptor交给原caller；新listener全程保留显式owner。"""
        self._owner()
        self._slots.remove(self._entry(slot))

    def release(self, slot):
        self._owner()
        entry = self._entry(slot)
        try:
            if bool(slot):
                if entry[1] == "handle":
                    check(self.kernel.CloseHandle(slot))
                elif entry[1] == "local":
                    if self.kernel.LocalFree(ctypes.cast(slot, w.LPVOID)):
                        raise OSError("Windows security LocalFree failed")
                else:
                    raise RuntimeError("unknown Windows security resource")
        except BaseException as exc:
            if self.cleanup_failure is None:
                self.cleanup_failure = exc
            raise
        slot.value = None
        self._slots.remove(entry)

    def close(self):
        self._owner()
        failure = None
        for slot, unused_kind in tuple(reversed(self._slots)):
            try:
                self.release(slot)
            except BaseException as exc:
                if failure is None:
                    failure = exc
        if failure is not None:
            raise SecurityResourceError(self) from failure

    def scope(self, implicit=False):
        self._owner()
        return _SecurityScope(self, implicit)


class _SecurityScope(object):
    def __init__(self, resources, implicit):
        self.resources, self.implicit = resources, implicit
        self.before = tuple(entry[0] for entry in resources._slots)
        self.retained = []

    def __enter__(self):
        return self

    def local(self, slot):
        return self.resources._track(slot, "local")

    def handle(self, slot):
        return self.resources._track(slot, "handle")

    def retain(self, slot):
        self.resources._entry(slot)
        self.retained.append(slot)

    def __exit__(self, kind, original, traceback):
        failure = None
        # 包含嵌套辅助失败后留下的slot；不触碰进入scope前已有的借用descriptor。
        for slot, unused_kind in tuple(reversed(self.resources._slots)):
            if any(slot is value for value in self.before + tuple(self.retained)):
                continue
            try:
                self.resources.release(slot)
            except BaseException as exc:
                if failure is None:
                    failure = exc
        if original is not None:
            if self.implicit and (failure is not None or not self.resources.closed):
                raise SecurityResourceError(self.resources, original) from original
            return False
        if failure is not None:
            raise SecurityResourceError(self.resources) from failure
        return False


def _resource_scope(kernel, resources):
    if resources is None:
        return SecurityResources(kernel).scope(implicit=True)
    if not isinstance(resources, SecurityResources) or resources.kernel is not kernel:
        raise ValueError("matching Windows security resource owner required")
    return resources.scope()


def current_user(kernel, security, *, resources=None):
    """复制当前SID/文本；输出slot在分配前归owner，释放失败不返回成功。"""
    with _resource_scope(kernel, resources) as owned:
        token = owned.handle(w.HANDLE())
        text = owned.local(w.LPWSTR())
        size = w.DWORD()
        check(security.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)))
        security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        maximum = ctypes.sizeof(_SidAttributes) + SECURITY_MAX_SID_SIZE + ctypes.alignment(_SidAttributes)
        if not ctypes.sizeof(_SidAttributes) <= size.value <= maximum:
            raise OSError("unexpected TOKEN_USER size")
        buffer = ctypes.create_string_buffer(size.value)
        check(security.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)))
        sid = ctypes.cast(buffer, ctypes.POINTER(_SidAttributes)).contents.Sid
        value = _sid_bytes(security, sid)
        check(security.ConvertSidToStringSidW(sid, ctypes.byref(text)))
        return value, text.value


def private_descriptor(kernel, security, *, resources=None):
    """当前用户protected DACL；显式owner保留descriptor，旧caller仍取得原指针。"""
    with _resource_scope(kernel, resources) as owned:
        unused_sid, text = current_user(kernel, security, resources=owned.resources)
        descriptor = owned.local(w.LPVOID())
        check(security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            "O:{0}D:P(A;;GA;;;{0})".format(text), 1, ctypes.byref(descriptor), None))
        if resources is None:
            owned.resources.detach(descriptor)
        else:
            owned.retain(descriptor)
        return descriptor


def verify_private_object(kernel, security, handle, required_mask, *, resources=None):
    """核原对象SID/protected DACL；临时descriptor及token均由统一owner释放。"""
    with _resource_scope(kernel, resources) as owned:
        expected, unused_text = current_user(kernel, security, resources=owned.resources)
        owner, acl = w.LPVOID(), w.LPVOID()
        descriptor = owned.local(w.LPVOID())
        error = security.GetSecurityInfo(handle, SE_KERNEL_OBJECT, OWNER_AND_DACL_SECURITY_INFORMATION,
            ctypes.byref(owner), None, ctypes.byref(acl), None, ctypes.byref(descriptor))
        if error:
            raise ctypes.WinError(error)
        control, revision = w.WORD(), w.DWORD()
        check(security.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(revision)))
        if (control.value & SE_DACL_PRESENT_AND_PROTECTED != SE_DACL_PRESENT_AND_PROTECTED
                or not acl or _sid_bytes(security, owner) != expected):
            raise OSError("kernel object owner/protected DACL differs from the trusted user")
        header = ctypes.cast(acl, ctypes.POINTER(_Acl)).contents
        if header.AclRevision not in (2, 4) or header.AceCount != 1:
            raise OSError("kernel object has unexpected user grants")
        ace = w.LPVOID()
        check(security.GetAce(acl, 0, ctypes.byref(ace)))
        entry = ctypes.cast(ace, ctypes.POINTER(_AceHeader)).contents
        if entry.AceType != 0 or entry.AceFlags != 0 or not 16 <= entry.AceSize <= 8 + SECURITY_MAX_SID_SIZE:
            raise OSError("kernel object has an unexpected access ACE")
        mask = ctypes.c_uint32.from_address(ace.value + 4).value
        copied = ctypes.create_string_buffer(ctypes.string_at(ace.value + 8, entry.AceSize - 8))
        allowed = _sid_bytes(security, copied, entry.AceSize - 8)
        if allowed != expected or not (mask & GENERIC_ALL or mask & required_mask == required_mask):
            raise OSError("kernel object access differs from the trusted user/profile")


def current_session(kernel):
    value = w.DWORD()
    check(kernel.ProcessIdToSessionId(kernel.GetCurrentProcessId(), ctypes.byref(value)))
    return value.value


def utc_now(kernel):
    """Same precise OS clock across modern Host and embedded CPython 3.6.

    Older datetime.now on Windows can lag the precise system clock by a tick.
    Using the same native clock avoids rejecting a just-issued frame as future;
    no clock-skew allowance extends its transport or business authorization.
    """
    value = w.FILETIME()
    kernel.GetSystemTimePreciseAsFileTime(ctypes.byref(value))
    ticks = (value.dwHighDateTime << 32) | value.dwLowDateTime
    return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks // 10)
