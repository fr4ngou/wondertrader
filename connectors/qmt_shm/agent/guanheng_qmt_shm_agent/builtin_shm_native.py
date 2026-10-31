# -*- coding: utf-8 -*-
"""Host-only secure creation for the builtin-mmap business transport.

迁自已交接builtin_shm_native.py；原安全对象与单owner语义保留。
本仓改动限定新配对版本、原截止检查及释放失败的字段保留；Agent禁止导入本模块。
"""
import ctypes
from ctypes import wintypes as w
import mmap
import threading
import time
from uuid import uuid4

from .builtin_shm import MAGIC, HEADER_BYTES, CLOSE_OFFSETS, BuiltinMemoryFramer, _mac, authenticated_header
from .windows_security import (SecurityAttributes, check, current_session, libraries,
    private_descriptor, verify_private_object, SecurityResources)


class BuiltinMemoryListener(object):
    """One private Host owner; unqualified existing mappings are never reset."""
    def __init__(self, profile, secret, stop=None):
        if type(secret) is not bytes or len(secret) < 32:
            raise ValueError('builtin SHM requires private IPC credentials')
        self.profile, self.secret = profile, secret
        self._owner = threading.get_ident()
        self._stop = stop if stop is not None else threading.Event()
        self._mutex, self._mapping, self._view = None, None, None
        self._rendezvous, self._data_mapping = None, None
        self._owned, self._accepted, self._closed = False, False, False
        self._failed_framer = None
        self.kernel, self.security = libraries()
        self._security_resources = SecurityResources(self.kernel)
        k = self.kernel
        k.CreateMutexW.argtypes, k.CreateMutexW.restype = [ctypes.POINTER(SecurityAttributes), w.BOOL, w.LPCWSTR], w.HANDLE
        k.ReleaseMutex.argtypes, k.ReleaseMutex.restype = [w.HANDLE], w.BOOL
        k.CreateFileMappingW.argtypes, k.CreateFileMappingW.restype = [w.HANDLE, ctypes.POINTER(SecurityAttributes),
            w.DWORD, w.DWORD, w.DWORD, w.LPCWSTR], w.HANDLE

    def _check(self, deadline):
        if self._stop.is_set() or time.monotonic() >= deadline:
            raise TimeoutError('builtin SHM protected mapping creation expired')

    @property
    def io_resources_closed(self):
        return self._closed and self._failed_framer is None and self._security_resources.closed

    def _create(self, function, attribute, deadline, owns_mutex=False):
        self._check(deadline)
        if getattr(self, attribute) is not None or not self._security_resources.closed:
            raise RuntimeError('builtin SHM creation cannot replace an owned resource')
        with self._security_resources.scope():
            descriptor = private_descriptor(self.kernel, self.security, resources=self._security_resources)
            self._check(deadline)
            attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
            ctypes.set_last_error(0)
            handle = function(ctypes.byref(attributes))
            if handle:
                setattr(self, attribute, handle)
            error = ctypes.get_last_error()
            check(handle)
            if owns_mutex and error != 183:
                self._owned = True
            self._check(deadline)
        self._check(deadline)
        return error == 183

    def accept(self, deadline):
        if self._accepted or self._stop.is_set() or threading.get_ident() != self._owner:
            raise OSError('builtin SHM listener has one original owner')
        self._accepted = True
        framer = None
        try:
            self._check(deadline)
            if current_session(self.kernel) != self.profile.session_id:
                raise OSError('builtin SHM Windows session differs')
            exists = self._create(lambda attrs: self.kernel.CreateMutexW(
                attrs, True, self.profile.name+'-host'), '_mutex', deadline, owns_mutex=True)
            if exists:
                raise OSError('builtin SHM Host is already owned')
            verify_private_object(self.kernel, self.security, self._mutex, 0x100001, resources=self._security_resources)
            while True:
                self._check(deadline)
                existing = self._create(lambda attrs: self.kernel.CreateFileMappingW(
                    w.HANDLE(-1), attrs, 4, 0, HEADER_BYTES, self.profile.name), '_mapping', deadline)
                try:
                    verify_private_object(self.kernel, self.security, self._mapping, 0xF001F, resources=self._security_resources)
                    self._check(deadline)
                    self._view = mmap.mmap(-1, HEADER_BYTES, tagname=self.profile.name)
                    self._check(deadline)
                    if existing:
                        authenticated_header(self._view, self.profile, self.secret)
                    break
                except (OSError, ValueError):
                    # mmap探测缺名字可能短暂产生空mapping；不初始化/采用未认证对象。
                    # 清理失败先保留owner并上抛，不能覆盖尚未释放的字段开始下一次探测。
                    if self._view is not None:
                        self._view.close()
                        self._view = None
                    check(self.kernel.CloseHandle(self._mapping))
                    self._mapping = None
                    self._stop.wait(min(self.profile.poll_seconds, max(0, deadline-time.monotonic())))
            self._check(deadline)
            generation = uuid4().bytes
            self._rendezvous, self._view = self._view, None
            data_name = self.profile.name+'-'+generation.hex()
            existing = self._create(lambda attrs: self.kernel.CreateFileMappingW(
                w.HANDLE(-1), attrs, 4, 0, self.profile.mapped_bytes, data_name), '_data_mapping', deadline)
            if existing:
                raise OSError('builtin SHM data generation is already owned')
            verify_private_object(self.kernel, self.security, self._data_mapping, 0xF001F, resources=self._security_resources)
            self._check(deadline)
            self._view = mmap.mmap(-1, self.profile.mapped_bytes, tagname=data_name)
            self._check(deadline)
            self._view[:] = b'\0' * self.profile.mapped_bytes
            header = MAGIC + generation + self.profile.profile_hash
            self._view[8:88] = header[8:] + _mac(self.secret, b'header', header)
            self._check(deadline)
            self._view[:8] = MAGIC
            # 先发布完整受保护data，再发布固定rendezvous；Agent不写后者。
            self._rendezvous[:] = b'\0' * HEADER_BYTES
            self._rendezvous[8:88] = header[8:] + _mac(self.secret, b'header', header)
            self._check(deadline)
            self._rendezvous[:8] = MAGIC
            framer = BuiltinMemoryFramer(self._view, self.profile, self.secret, generation,
                'host', self._stop, self._dispose)
            self._view = None  # 先把实际view转给framer，再检查最终原截止。
            self._check(deadline)
            return framer
        except BaseException:
            if framer is not None:
                try:
                    framer.close()
                except BaseException:
                    # listener保留失败framer；跨线程close仍只请求，禁止释放活跃I/O。
                    self._failed_framer = framer
            try:
                self.close()
            except BaseException:
                pass
            raise

    def _dispose(self):
        if threading.current_thread() is not self._security_resources.owner:
            raise RuntimeError('builtin SHM resources belong to the original Host worker')
        if self._closed:
            return
        failure = None
        for attribute in ('_view', '_rendezvous'):
            view = getattr(self, attribute)
            if view is not None:
                if attribute == '_rendezvous':
                    try:
                        view[CLOSE_OFFSETS['host']:CLOSE_OFFSETS['host']+8] = b'\x01'+b'\0'*7
                    except BaseException as exc:
                        if failure is None:
                            failure = exc
                try:
                    view.close()
                except BaseException as exc:
                    if failure is None:
                        failure = exc
                else:
                    setattr(self, attribute, None)
        if self._owned:
            try:
                check(self.kernel.ReleaseMutex(self._mutex))
            except BaseException as exc:
                if failure is None:
                    failure = exc
            else:
                self._owned = False
        for attribute in ('_data_mapping', '_mapping', '_mutex'):
            handle = getattr(self, attribute)
            if handle is not None and not (attribute == '_mutex' and self._owned):
                try:
                    check(self.kernel.CloseHandle(handle))
                except BaseException as exc:
                    if failure is None:
                        failure = exc
                else:
                    setattr(self, attribute, None)
        try:
            self._security_resources.close()
        except BaseException as exc:
            if failure is None:
                failure = exc
        self._closed = not self._owned and all(getattr(self, name) is None for name in (
            '_view', '_rendezvous', '_data_mapping', '_mapping', '_mutex')) and self._security_resources.closed
        if failure is not None:
            raise failure

    def close(self):
        self._stop.set()
        if threading.current_thread() is self._security_resources.owner:
            failure = None
            framer = getattr(self, '_failed_framer', None)
            if framer is not None:
                try:
                    framer.close()
                except BaseException as exc:
                    failure = exc
                else:
                    self._failed_framer = None
            try:
                self._dispose()
            except BaseException as exc:
                if failure is None:
                    failure = exc
            if failure is not None:
                raise failure
