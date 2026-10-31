# -*- coding: utf-8 -*-
"""原Session与SHM组合；构造只准入，I/O owner显式创建/释放内核对象。"""
import threading
from .protocol import Session, canonical, decode, identity
from .transport_profile import validate_transport_profile


class LocalTransport(object):
    def __init__(self, *, route, secret, max_frame, profile, transport):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("local transport requires private IPC credentials")
        if type(max_frame) is not int or not 1024 <= max_frame <= 4194304:
            raise ValueError("invalid unchanged Session packet budget")
        self.route, self.secret, self.max_frame = identity(route), secret, max_frame
        self._profile = canonical(profile)
        self._config = canonical(transport)
        self.shm_profile = validate_transport_profile(decode(self._config), self.route,
            max_frame, decode(self._profile))
        self.transport_kind = decode(self._config)["kind"]
        self._connector = None
        self._legacy_resources = None

    def listen(self, *, wait_for_peer=False):
        return _Listener(self, wait_for_peer=wait_for_peer)

    def _channel(self, framer, role):
        return Session(framer, self.secret, self.route, role, generation=framer.generation)

    def connect(self, deadline, stop=None):
        if self.transport_kind == "builtin-shm":
            if self._connector is not None:
                raise OSError("builtin transport has one owned connection attempt")
            from .builtin_shm import BuiltinMemoryConnector, connect
            self._connector = BuiltinMemoryConnector(self.shm_profile, self.secret, stop)
            framer = connect(self.shm_profile, self.secret, deadline, stop, _owner=self._connector)
            return self._channel(framer, "agent")
        else:
            from .shm import connect
        framer = connect(self.shm_profile, self.secret, deadline, stop, resource_owner=self._own_legacy_resources)
        return self._channel(framer, "agent")


    def _own_legacy_resources(self, resources):
        if self._legacy_resources is not None and not self._legacy_resources._disposed:
            raise RuntimeError("cannot replace unreleased legacy transport resources")
        self._legacy_resources = resources

    def close(self):
        """Agent原I/O线程收口半连接；管理线程只通过原stop发出请求。"""
        if self._connector is not None:
            self._connector.close()
        if self._legacy_resources is not None:
            self._legacy_resources.stop.set()
            if threading.current_thread() is self._legacy_resources._security_resources.owner:
                self._legacy_resources.dispose()


class _Listener(object):
    def __init__(self, transport, *, wait_for_peer=False):
        if type(wait_for_peer) is not bool or (wait_for_peer and transport.transport_kind != "builtin-shm"):
            raise ValueError("persistent peer wait requires explicit builtin SHM")
        self._wait_for_peer = wait_for_peer
        self.transport = transport
        self._raw, self._framer, self._accepted = None, None, False
        self._cleanup_failure = None
        self._stop, self._guard = threading.Event(), threading.Lock()
        self._ready, self._failure = threading.Event(), None
        self._owner_thread = None
        self._constructing = False
        self._closing = False

    @property
    def io_resources_closed(self):
        """join后核资源；构造/释放尚在原线程进行时不能发布已闭。"""
        if self._constructing or self._closing or self._cleanup_failure is not None:
            return False
        if self.transport.transport_kind == "builtin-shm":
            return (self._framer is None or self._framer._closed) and (
                self._raw is None or self._raw.io_resources_closed)
        return self._raw is None or self._raw.io_resources_closed

    def wait_ready(self, deadline):
        import time
        if not self._ready.wait(max(0, deadline - time.monotonic())):
            self.request_close()
            raise TimeoutError("local transport did not establish its owned listener")
        if self._failure is not None:
            raise self._failure

    def accept(self, deadline):
        framer = None
        try:
            # 只认领状态；import/构造/映射/关闭都不能跨此锁。
            with self._guard:
                if self._accepted or self._stop.is_set():
                    raise OSError("local listener has one generation")
                self._accepted = True
                self._owner_thread = threading.current_thread()
                self._constructing = True
            try:
                if self.transport.transport_kind == "builtin-shm":
                    from .builtin_shm_native import BuiltinMemoryListener as Listener
                else:
                    from .shm import SharedMemoryListener as Listener
                self._raw = Listener(self.transport.shm_profile, self.transport.secret, stop=self._stop)
            finally:
                self._constructing = False
            if self._stop.is_set():
                raise OSError("local listener is closing")
            framer = self._raw.accept(deadline)
            self._framer = framer
            self._ready.set()
            if self._wait_for_peer:
                framer.wait_peer(deadline, wait_for_peer=True)
            else:
                framer.wait_peer(deadline)
            return self.transport._channel(framer, "host")
        except BaseException as exc:
            self._failure = exc
            self._ready.set()
            if threading.current_thread() is self._owner_thread:
                try:
                    self._close_owned()
                except BaseException:
                    pass  # 原异常保持；失败字段和_cleanup_failure仍归此listener。
            raise

    def request_close(self):
        """所有actor均只发布内存stop；不等构造/释放锁，不调用后端或WinAPI。"""
        self._stop.set()

    def _close_owned(self):
        if threading.current_thread() is not self._owner_thread:
            raise RuntimeError("listener resources belong to their original I/O thread")
        self._closing = True
        failure = None
        try:
            for resource in (self._framer, self._raw):
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as exc:
                        if failure is None:
                            failure = exc
        finally:
            self._closing = False
        if failure is not None:
            if self._cleanup_failure is None:
                self._cleanup_failure = failure
            raise failure

    def close(self):
        self.request_close()
        if threading.current_thread() is self._owner_thread:
            self._close_owned()
