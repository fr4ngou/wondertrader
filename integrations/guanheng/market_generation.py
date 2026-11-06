"""数据侧独占发布已完成的行情版本；原件只读、历史记录保留。"""
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

from ..guanheng_market_client import strict_json


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf8')


@contextmanager
def _read_stream(path):
    """Windows允许原子替换已打开指针；句柄继续读原对象直到本次查询结束。"""
    if os.name != 'nt':
        with path.open('rb') as stream:
            yield stream
        return
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    handle = create(str(path), 0x80000000, 7, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        close(handle)
        raise
    with os.fdopen(descriptor, 'rb') as stream:
        yield stream


def read_fixed(path, *, maximum, identity=None):
    """小文件按真实长度读取，读前后身份/长度/时间和可选SHA同时校验。"""
    path = Path(path)
    with _read_stream(path) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise ValueError('market generation file budget exceeded')
        body = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')
    if (len(body) != before.st_size
            or any(getattr(before, k) != getattr(after, k) for k in fields)
            or identity is not None and hashlib.sha256(body).hexdigest() != identity):
        raise ValueError('market generation file changed')
    return body


def _replace_pointer(source, target):
    """同目录原子换名；Windows采用保留已打开旧对象的POSIX替换语义。"""
    if os.name != 'nt':
        os.replace(source, target)
        return
    import ctypes
    from ctypes import wintypes
    class RenameInfo(ctypes.Structure):
        _fields_ = [
            ('Flags', wintypes.DWORD),  # REPLACE_IF_EXISTS|POSIX_SEMANTICS；保持已打开旧句柄有效。
            ('RootDirectory', wintypes.HANDLE),  # 使用完整绝对路径；Win32入口要求此字段为空。
            ('FileNameLength', wintypes.DWORD),  # UTF-16目标名字节长度，排除结尾空字符。
            ('FileName', wintypes.WCHAR * 1)]  # 结构尾随变长路径，缓冲区仅本次调用有效。
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    rename = kernel.SetFileInformationByHandle
    rename.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    rename.restype = wintypes.BOOL
    if source.parent.absolute() != target.parent.absolute():
        raise ValueError('market pointer replacement must stay in one directory')
    name = str(target.absolute()).encode('utf-16-le')
    buffer = ctypes.create_string_buffer(max(ctypes.sizeof(RenameInfo), RenameInfo.FileName.offset + len(name) + 2))
    info = RenameInfo.from_buffer(buffer)
    info.Flags = 3
    info.RootDirectory = None
    info.FileNameLength = len(name)
    ctypes.memmove(ctypes.addressof(buffer) + RenameInfo.FileName.offset, name, len(name))
    handle = create(str(source), 0x10000, 7, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not rename(handle, 22, buffer, len(buffer)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        close(handle)


def read_generation(path):
    """返回本次打开的完整原子指针与其SHA；替换后的下一版留到下一请求。"""
    body = read_fixed(path, maximum=65536)
    value = strict_json(body)
    required = {'schema', 'generation_id', 'previous_sha256', 'configuration',
                'snapshot_id', 'observation_date', 'published_at'}
    if type(value) is not dict or set(value) != required or value['schema'] != 'guanheng.market-current.v1':
        raise ValueError('market generation pointer invalid')
    descriptor = value['configuration']
    if (type(descriptor) is not dict or set(descriptor) != {'path', 'sha256'}
            or type(descriptor['path']) is not str or not Path(descriptor['path']).is_absolute()):
        raise ValueError('market generation configuration invalid')
    for identity in (descriptor['sha256'], value['snapshot_id']):
        if type(identity) is not str or re.fullmatch('[0-9a-f]{64}', identity) is None:
            raise ValueError('market generation identity invalid')
    previous = value['previous_sha256']
    if previous is not None and (type(previous) is not str or re.fullmatch('[0-9a-f]{64}', previous) is None):
        raise ValueError('market generation parent invalid')
    if type(value['generation_id']) is not str or uuid.UUID(value['generation_id']).hex != value['generation_id']:
        raise ValueError('market generation id invalid')
    from datetime import date
    if date.fromisoformat(value['observation_date']).isoformat() != value['observation_date']:
        raise ValueError('market generation date invalid')
    clock = datetime.fromisoformat(value['published_at'])
    if clock.tzinfo is None or clock.utcoffset() is None or clock > datetime.now(timezone.utc):
        raise ValueError('market generation publication clock invalid')
    return value, hashlib.sha256(body).hexdigest()


def load_generation(value, *, max_response_bytes):
    """只准入冻结snapshot模式，防止动态指针递归或绕回实时Writer尾部。"""
    descriptor = value['configuration']
    config = strict_json(read_fixed(descriptor['path'], maximum=1048576,
                                    identity=descriptor['sha256']))
    if type(config) is not dict or config.get('mode') != 'source-market-snapshot':
        raise ValueError('market generation requires immutable snapshot')
    from .market_snapshot import SnapshotSourceMarket
    market = SnapshotSourceMarket(config, max_response_bytes=max_response_bytes)
    try:
        from ..guanheng_market_client import API_VERSION
        reply = market.call(dict(api_version=API_VERSION, action='market.source-snapshot-query',
                                 request=dict(date=value['observation_date'],include_supplement=True)))
        if reply['status']['code'] != 'Ok' or reply['data']['snapshot_id'] != value['snapshot_id']:
            raise ValueError('market generation snapshot differs')
    except BaseException:
        market.close()
        raise
    return market


class GenerationPublisher(AbstractContextManager):
    """控制目录锁覆盖整个写生命周期；显式close/上下文退出释放进程锁。"""
    def __init__(self, control_directory):
        self.directory = Path(control_directory).absolute()  # 私有控制根；历史generation记录由数据侧长期保留。
        self.current_file = self.directory / 'CURRENT.json'  # 小型活动版本指针；仅本owner在持锁期原子替换。
        self._lock = None  # 本进程排他锁文件句柄，close负责解锁并关闭。
        self.directory.mkdir(parents=False, exist_ok=True)
        lock = (self.directory / 'writer.lock').open('a+b')
        try:
            lock.seek(0, 2)
            if lock.tell() == 0:
                lock.write(b'\0')
                lock.flush()
            lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            lock.close()
            raise
        self._lock = lock
        try:
            (self.directory / 'generations').mkdir(exist_ok=True)
            # 取得排他锁才可回收上次尚未提交的唯一指针；已发布记录与原始数据保持。
            (self.directory / 'CURRENT.pending').unlink(missing_ok=True)
        except BaseException:
            self.close()
            raise

    def publish(self, configuration, *, expected_current_sha256, max_response_bytes=8388608):
        """发布已完成配置；expected为空仅用于初始版本，回退也使用同一CAS。"""
        if self._lock is None:
            raise RuntimeError('market generation writer closed')
        current = read_generation(self.current_file) if self.current_file.exists() else (None, None)
        if current[1] != expected_current_sha256:
            raise ValueError('market generation publication conflict')
        if type(configuration) is not dict or set(configuration) != {'path', 'sha256'}:
            raise ValueError('market generation configuration descriptor invalid')
        if (type(configuration['path']) is not str or not Path(configuration['path']).is_absolute()
                or type(configuration['sha256']) is not str
                or re.fullmatch('[0-9a-f]{64}', configuration['sha256']) is None):
            raise ValueError('market generation configuration descriptor invalid')
        config = strict_json(read_fixed(configuration['path'], maximum=1048576,
                                        identity=configuration['sha256']))
        if config.get('mode') != 'source-market-snapshot':
            raise ValueError('market generation requires immutable snapshot')
        snapshot = strict_json(read_fixed(config['snapshot']['path'], maximum=16777216,
                                          identity=config['snapshot']['sha256']))
        pending = self.directory / 'CURRENT.pending'
        value = dict(
            schema='guanheng.market-current.v1',  # 读取指针合同，与原生数据/SDK协议分别版本化。
            generation_id=uuid.uuid4().hex,  # 每次发布/回退的独立记录身份，历史不覆盖。
            previous_sha256=current[1],  # 实际旧指针SHA；首次发布为None。
            configuration=dict(configuration),  # 不可变snapshot配置绝对路径及精确SHA。
            snapshot_id=snapshot['snapshot_id'],  # 资料、价格与日事实共同版本，供消费者固定。
            observation_date=snapshot['observation_date'],  # 原股票池观察日，YYYY-MM-DD。
            published_at=datetime.now(timezone.utc).isoformat())  # 本地发布时间，带UTC时区；区别来源日期。
        if pending.exists():
            # 原子替换被外部不共享删除的读取者阻塞时，续接同一候选身份和父版本。
            prepared, _ = read_generation(pending)
            if any(prepared[key] != value[key] for key in
                   ('previous_sha256', 'configuration', 'snapshot_id', 'observation_date')):
                raise ValueError('market generation pending publication differs')
            value = prepared
        market = load_generation(value, max_response_bytes=max_response_bytes)
        market.close()
        body = encode(value)
        record = self.directory / 'generations' / (value['generation_id'] + '.json')
        if not pending.exists():
            with record.open('xb') as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            with pending.open('xb') as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
        elif read_fixed(record, maximum=65536) != body:
            raise ValueError('market generation pending record differs')
        _replace_pointer(pending, self.current_file)
        return value, hashlib.sha256(body).hexdigest()

    def close(self):
        if self._lock is not None:
            lock, self._lock = self._lock, None
            try:
                lock.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            finally:
                lock.close()

    def __exit__(self, *ignored):
        self.close()
