"""HC1 Host专用uptime域；导入不加载DLL或读取时钟。"""
import sys
from guanheng_qmt_shm_agent.trade_clock import deadline_seconds


class WindowsBulkUptimeClock:
    def __init__(self, *, read_milliseconds=None, platform=None):
        if (sys.platform if platform is None else platform) != 'win32':
            raise ValueError('bulk_clock_unavailable')
        if read_milliseconds is not None and not callable(read_milliseconds):
            raise ValueError('bulk_clock_unavailable')
        self._library = None
        if read_milliseconds is None:
            try:
                import ctypes
                self._library = ctypes.WinDLL('kernel32', use_last_error=True)
                read_milliseconds = self._library.GetTickCount64
                read_milliseconds.argtypes = []
                read_milliseconds.restype = ctypes.c_uint64
            except Exception:
                raise ValueError('bulk_clock_unavailable') from None
        self._read = read_milliseconds

    def seconds(self):
        try:
            value = self._read()
            if type(value) is not int or value < 0:
                raise ValueError('invalid clock scalar')
            if value == 0:
                return 0.0
            return deadline_seconds(value)
        except Exception:
            raise ValueError('bulk_clock_unavailable') from None
