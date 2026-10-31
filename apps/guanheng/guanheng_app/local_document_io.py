"""应用本地文档的共享文件机制；业务CAS、快照、启动和关闭归各owner。

复用原个人观察的Windows单写者、根/文件身份、有界IO和原子替换。
混入方提供_check/_call/_owned以及原资源字段；本模块不创建线程或业务状态。
"""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
from .watchlist_lock import WindowsLease

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass
class Publication:
    """一次文件发布的实际阶段，异常后供业务owner判结果未知和维护边界。"""
    created: bool = False
    replacing: bool = False
    identity: tuple | None = None
    blocked: bool = False


class LocalDocumentIO:
    """固定文件布局的本机IO复用，期限与资源引用始终归调用owner。"""
    def _root_info(self, deadline):
        self._check(deadline)
        for path in reversed((self._root, *self._root.parents)):
            info = self._call(deadline, path.lstat)
            if not stat.S_ISDIR(info.st_mode) or info.st_file_attributes & _REPARSE:
                raise self._io_error(self._io_maintenance)
        info = self._call(deadline, self._root.lstat)
        identity = (info.st_dev, info.st_ino)
        if self._root_key is not None and identity != self._root_key:
            raise self._io_error(self._io_maintenance)
        return identity

    def _prepare_root(self, deadline):
        value = self._root_text
        if os.name != "nt" or type(value) is not str or not value or value != value.strip():
            raise self._io_error(self._reason)
        if len(value) > 4096 or len(value.encode("utf-8")) > 4096 or chr(0) in value:
            raise self._io_error(self._io_maintenance)
        root = Path(value)
        if not root.is_absolute() or not re.fullmatch(r"[A-Za-z]:", root.drive) or root.parent == root:
            raise self._io_error(self._io_maintenance)
        self._native = WindowsLease()
        if not self._native.local_drive(root.drive, lambda: self._check(deadline)):
            raise self._io_error(self._io_maintenance)
        self._root = root
        self._root_key = self._root_info(deadline)
        canonical = self._call(deadline, self._root.resolve, strict=True)
        # 原输入合法不授解析后目标资格；映射盘、UNC/device与未知盘均在此拒绝。
        if (not canonical.is_absolute() or not re.fullmatch(r"[A-Za-z]:", canonical.drive)
                or canonical.parent == canonical):
            raise self._io_error(self._io_maintenance)
        if not self._native.local_drive(canonical.drive, lambda: self._check(deadline)):
            raise self._io_error(self._io_maintenance)
        self._root = canonical
        self._root_info(deadline)

    def _file_info(self, name, deadline):
        info = self._call(deadline, (self._root / name).lstat)
        if (not stat.S_ISREG(info.st_mode) or info.st_file_attributes & _REPARSE
                or info.st_nlink != 1 or not 0 <= info.st_size <= self._document_limits[name]):
            raise self._io_error(self._io_maintenance)
        return info

    def _names(self, deadline):
        self._root_info(deadline)
        self._check(deadline)
        directory = os.scandir(self._root)
        names = set()
        with self._owned(directory, deadline):
            while True:
                self._check(deadline)
                try:
                    entry = next(directory)
                except StopIteration:
                    self._check(deadline)
                    break
                self._check(deadline)
                if entry.name not in self._document_limits or entry.name in names:
                    raise self._io_error(self._io_maintenance)
                names.add(entry.name)
                self._file_info(entry.name, deadline)
        if self._lease_key is not None:
            lease_info = self._file_info(self._document_lock, deadline)
            if (lease_info.st_dev, lease_info.st_ino) != self._lease_key:
                raise self._io_error(self._io_maintenance)
        return names

    def _write_all(self, stream, raw, deadline):
        offset = 0
        while offset < len(raw):
            written = self._call(deadline, stream.write, raw[offset:])
            if type(written) is not int or not 0 < written <= len(raw) - offset:
                raise self._io_error(self._io_maintenance)
            offset += written
        self._call(deadline, stream.flush)
        descriptor = self._call(deadline, stream.fileno)
        self._call(deadline, os.fsync, descriptor)

    def _acquire_lease(self, deadline, *, create):
        # CreateFile share_mode=0将首次创建和成为排他owner合为同一OS动作。
        # wrapper在open之前归owner，晚返回/CRT转换失败均保留原句柄供关闭。
        self._check(deadline)
        self._lease = self._native
        self._lease.open(self._root / self._document_lock, create=create, check=lambda: self._check(deadline))
        lease = self._lease
        self._file_info(self._document_lock, deadline)
        size = self._call(deadline, lease.seek, 0, os.SEEK_END)
        if size == 0:
            self._write_all(lease, bytes((0,)), deadline)
        self._call(deadline, lease.seek, 0)
        descriptor = self._call(deadline, lease.fileno)
        info = self._call(deadline, os.fstat, descriptor)
        path_info = self._file_info(self._document_lock, deadline)
        if (info.st_dev, info.st_ino) != (path_info.st_dev, path_info.st_ino):
            raise self._io_error(self._io_maintenance)
        self._lease_key = (info.st_dev, info.st_ino)
        with self._state:
            self._initialized = True
        self._check(deadline)

    def _read_bytes(self, deadline):
        names = self._names(deadline)
        name = self._document_main
        if name not in names:
            raise self._io_error(self._io_maintenance)
        before = self._file_info(name, deadline)
        self._check(deadline)
        stream = self._open_file(name, "rb")
        with self._owned(stream, deadline):
            descriptor = self._call(deadline, stream.fileno)
            opened = self._call(deadline, os.fstat, descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise self._io_error(self._io_maintenance)
            raw = self._call(deadline, stream.read, self._document_limits[name] + 1)
            if type(raw) is not bytes or not raw or len(raw) > self._document_limits[name]:
                raise self._io_error(self._io_maintenance)
            after = self._file_info(name, deadline)
            if (opened.st_dev, opened.st_ino) != (after.st_dev, after.st_ino):
                raise self._io_error(self._io_maintenance)
        return names, raw

    def _publish_bytes(self, raw, deadline, publication):
        """只发布已编码值；实际replace后任何失败由业务owner保留未知状态。"""
        name, temporary = self._document_main, self._document_temp
        try:
            self._check(deadline)
            stream = self._open_file(temporary, "xb")
            publication.created = True
            with self._owned(stream, deadline):
                descriptor = self._call(deadline, stream.fileno)
                info = self._call(deadline, os.fstat, descriptor)
                publication.identity = (info.st_dev, info.st_ino)
                self._file_info(temporary, deadline)
                self._write_all(stream, raw, deadline)
            info = self._file_info(temporary, deadline)
            if publication.identity != (info.st_dev, info.st_ino):
                raise self._io_error(self._io_maintenance)
            self._root_info(deadline)
            self._check(deadline)
            publication.replacing = True
            os.replace(self._root / temporary, self._root / name)
            self._check(deadline)
        except BaseException as exc:
            publication.blocked = publication.replacing
            if not publication.replacing and publication.created:
                try:
                    if self._resources or publication.identity is None:
                        raise self._io_error(self._io_maintenance)
                    info = (self._root / temporary).lstat()
                    if (publication.identity != (info.st_dev, info.st_ino)
                            or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                        raise self._io_error(self._io_maintenance)
                    (self._root / temporary).unlink()
                except BaseException as cleanup:
                    self._last_error = cleanup
                    publication.blocked = True
                    exc.add_note("本次文档临时文件清理未确认，原件保留供维护")
            raise
