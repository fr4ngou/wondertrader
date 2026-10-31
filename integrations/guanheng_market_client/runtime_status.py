"""采集状态唯一读取接缝；读者允许发布者原子替换，旧句柄保留完整旧快照。"""
from contextlib import contextmanager
import json
import os
import stat
from typing import NamedTuple


_ERROR = 'collection_status_unavailable'
_REASONS = frozenset(('file_type', 'capacity', 'link_count', 'reparse',
                      'identity', 'read_size', 'json', 'io'))


class CollectionStatusPending(OSError):
    """发布者短暂占用名字；消费者只能在原业务截止内读取下一快照。"""
    def __init__(self):
        super().__init__('collection_status_pending')


class CollectionStatusError(ValueError):
    """固定消息与有限诊断；仅包含同句柄stat白名单，不含路径、正文或原异常消息。"""
    def __init__(self, reason, before_stat=None, after_stat=None):
        super().__init__(_ERROR)
        self.reason = reason if reason in _REASONS else 'io'
        self.before_stat = before_stat
        self.after_stat = after_stat


def _stat_projection(info):
    if info is None:
        return None
    return {name: getattr(info, name, None) for name in
            ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_nlink',
             'st_mode', 'st_file_attributes')}


def _identity(info):
    # Windows原子替换可改变旧文件链接数；身份只核同句柄数据，不核当前路径。
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _check(info, maximum):
    if not stat.S_ISREG(info.st_mode):
        raise CollectionStatusError('file_type')
    if not 0 < info.st_size <= maximum:
        raise CollectionStatusError('capacity')
    if info.st_nlink > 1:
        raise CollectionStatusError('link_count')
    if getattr(info, 'st_file_attributes', 0) & 0x400:
        raise CollectionStatusError('reparse')


@contextmanager
def _open_status_file(path):
    """内部资源owner：yield期间持有唯一读句柄，退出确认关闭；测试可控制替换时点。

    Windows共享读、写和删除以兼容系统替换；本句柄访问权限仍为只读。
    发布者合同保持另写新文件再原子替换，同句柄前后身份检查拒绝可观察的就地修改。
    句柄移交给fd后只由Python流关闭，移交失败仍由本函数关闭原HANDLE。
    """
    fd = None
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        import msvcrt
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        # OPEN_REPARSE_POINT保留目标本身，随后按句柄属性拒绝重解析文件。
        handle = kernel.CreateFileW(os.fspath(path), 0x80000000, 1 | 2 | 4, None, 3, 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            class AttributeTag(ctypes.Structure):
                _fields_ = [('attributes', wintypes.DWORD), ('tag', wintypes.DWORD)]
            kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                wintypes.LPVOID, wintypes.DWORD]
            kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
            attributes = AttributeTag()
            if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
                raise ctypes.WinError(ctypes.get_last_error())
            if attributes.attributes & 0x400:
                raise CollectionStatusError('reparse')
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            handle = None
        finally:
            if handle is not None and not kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
    else:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        stream = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with stream:
        yield stream


class StatusSnapshot(NamedTuple):
    """同一读句柄的JSON值和文件修改epoch纳秒；后者仅描述文件，不代表行情时钟。"""
    value: dict
    modified_epoch_ns: int


def read_status_snapshot(path, max_bytes=65536):
    """返回有限JSON对象；允许同句柄旧快照，缺文件保持FileNotFoundError供轮询。

    首stat前WinError32抛CollectionStatusPending，消费者沿原D取下一快照。
    其他读入/格式失败统一ValueError固定原因，原字节及路径不进入错误消息。
    同一文件被就地修改将失败；本接口不将新路径身份与旧句柄混比。
    """
    raw = None
    before = after = None
    stage = 'io'
    try:
        if type(max_bytes) is not int or not 1 <= max_bytes <= 65536:
            raise CollectionStatusError('capacity')
        with _open_status_file(path) as stream:
            before = os.fstat(stream.fileno())
            _check(before, max_bytes)
            raw = stream.read(max_bytes + 1)
            after = os.fstat(stream.fileno())
            _check(after, max_bytes)
            if len(raw) != before.st_size:
                raise CollectionStatusError('read_size')
            if _identity(before) != _identity(after):
                raise CollectionStatusError('identity')
        stage = 'json'
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError(_ERROR)
                result[key] = value
            return result
        def invalid(_value):
            raise ValueError(_ERROR)
        value = json.loads(raw.decode('utf8'), object_pairs_hook=pairs, parse_constant=invalid)
        if type(value) is not dict:
            raise ValueError(_ERROR)
        return StatusSnapshot(value, before.st_mtime_ns)
    except FileNotFoundError:
        raise FileNotFoundError(_ERROR) from None
    except CollectionStatusError as exc:
        raise CollectionStatusError(exc.reason, _stat_projection(before), _stat_projection(after)) from None
    except Exception as exc:
        # 仅尚未采得首stat的系统共享冲突可暂缺；helper不重试或续期。
        if before is None and isinstance(exc, OSError) and getattr(exc, 'winerror', None) == 32:
            raise CollectionStatusPending() from None
        raise CollectionStatusError(stage, _stat_projection(before), _stat_projection(after)) from None
    finally:
        raw = None


def read_status(path, max_bytes=65536):
    """兼容只取JSON值的调用者；完整校验及Windows共享删除由同一实现承担。"""
    return read_status_snapshot(path, max_bytes).value


def replace_status(candidate, target):
    """唯一发布者提交已完整关闭的临时文件；读者可继续持有旧快照句柄。

    首次发布使用独占rename；已有Windows目标使用ReplaceFileW保留读者兼容性。
    失败原样保留OS错误及临时文件，不重试、不删除目标、不修改访问权限。
    """
    try:
        os.lstat(target)
    except FileNotFoundError:
        os.rename(candidate, target)
        return
    if os.name != 'nt':
        os.replace(candidate, target)
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.ReplaceFileW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
    kernel.ReplaceFileW.restype = wintypes.BOOL
    if not kernel.ReplaceFileW(os.fspath(target), os.fspath(candidate), None, 0, None, None):
        raise ctypes.WinError(ctypes.get_last_error())
