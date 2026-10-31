"""Windows个人偏好锁：创建和独占打开是同一OS动作，句柄仅归一个owner。"""

import ctypes
from ctypes import wintypes
import os


class WindowsLease:
    """构造无OS调用；部分转换失败仍持有原handle/descriptor供close续核。

    share_mode=0同时排除第二个打开者与锁文件替换。CRT stream借用descriptor，
    closefd=False使fdopen失败或stream关闭均不能悄悄转移descriptor所有权。
    """

    def __init__(self):
        self._kernel = None
        self._raw = None
        self._descriptor = None
        self._stream = None

    def _api(self, check):
        if self._kernel is None:
            check()
            self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            check()
            api = self._kernel
            api.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
            api.CreateFileW.restype = wintypes.HANDLE
            api.CloseHandle.argtypes = (wintypes.HANDLE,)
            api.CloseHandle.restype = wintypes.BOOL
            api.GetDriveTypeW.argtypes = (wintypes.LPCWSTR,)
            api.GetDriveTypeW.restype = wintypes.UINT
            check()
        return self._kernel

    def local_drive(self, drive, check):
        api = self._api(check)
        check()
        kind = api.GetDriveTypeW(drive + "\\")
        check()
        # REMOVABLE/FIXED/CDROM/RAMDISK均属本地；远程、未知和无根一律拒绝。
        return kind in (2, 3, 5, 6)

    def open(self, path, *, create, check):
        if not self.closed:
            raise RuntimeError("个人观察锁已被本owner接管")
        api = self._api(check)
        check()
        import msvcrt
        check()
        handle = api.CreateFileW(str(path), 0xC0000000, 0, None, 1 if create else 3, 0x80, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise ctypes.WinError(ctypes.get_last_error())
        # 先接管再核迟到；CreateFile已经提供排他性，没有create→locking空隙。
        self._raw = handle
        check()
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
        if type(descriptor) is not int or descriptor < 0:
            raise OSError("个人观察锁descriptor转换失败")
        self._descriptor, self._raw = descriptor, None
        check()
        self._stream = os.fdopen(descriptor, "r+b", closefd=False)
        check()

    @property
    def closed(self):
        return self._raw is None and self._descriptor is None and self._stream is None

    def fileno(self):
        if self._descriptor is None:
            raise ValueError("个人观察锁尚无descriptor")
        return self._descriptor

    def seek(self, *args):
        return self._stream.seek(*args)

    def write(self, raw):
        return self._stream.write(raw)

    def flush(self):
        return self._stream.flush()

    def close(self):
        """已持有资源的清理不受工作截止短路；失败的原owner继续保留引用。"""
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None
        if self._raw is not None:
            if not self._kernel.CloseHandle(self._raw):
                raise ctypes.WinError(ctypes.get_last_error())
            self._raw = None
