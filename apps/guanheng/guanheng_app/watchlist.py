"""单根个人观察偏好owner；OS单写者锁、版本比较和原子文件保存。

所有实际I/O由应用既有BoundedReader调用。短状态锁只管理准入和资源引用，
序列锁拥有一次读取/比较/提交；关闭先停准入，在途结束后才释放OS锁。
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import math
# 保留原文件IO故障注入接缝；共享helper与此处引用同一个标准库对象。
import os as os
from pathlib import Path as Path
from threading import Lock
from time import monotonic
from uuid import uuid4

from .local_document_io import LocalDocumentIO, Publication

from .contracts.watchlist import (
    MAX_ITEMS, MAX_STATE_BYTES, MAX_VERSION, WatchlistReplacement, WatchlistSnapshot,
    decode_snapshot, encode_public_snapshot, encode_replacement_result, encode_snapshot,
)


UNAVAILABLE = "个人观察暂不可用，请稍后重新读取"
UNCONFIGURED = "个人观察尚未配置，仍可直接查询分钟线"
MAINTENANCE = "个人观察资料需要维护，当前暂不能编辑"
UNKNOWN = "个人观察保存结果尚未确认，请重新读取核实"
CONFLICT = "个人观察列表已在其他页面更新，请重新读取后确认"
_MAIN, _LOCK, _TEMP = "watchlist.json", ".watchlist.lock", "watchlist.tmp"
_LIMITS = {_MAIN: MAX_STATE_BYTES, _LOCK: 16, _TEMP: MAX_STATE_BYTES}


class WatchlistError(RuntimeError):
    """公开错误只保留固定中文与HTTP状态；底层内容由私有owner保留。"""

    def __init__(self, reason=UNAVAILABLE, *, code=503):
        super().__init__(reason)
        self.code = code


class WatchlistOwner(LocalDocumentIO):
    _document_main, _document_lock, _document_temp = _MAIN, _LOCK, _TEMP
    _document_limits = _LIMITS
    _io_error, _io_maintenance = WatchlistError, MAINTENANCE

    def _open_file(self, name, mode):
        return open(self._root / name, mode)

    def __init__(self, root, *, clock=monotonic):
        # 构造只分配值；应用先发布owner，再在受保护生命周期内初始化。
        self._root_text = root
        self._clock = clock
        self._state = Lock()
        self._serial = Lock()
        self._close_serial = Lock()
        self._root = None
        self._root_key = None
        self._attempted = self._initialized = self._ready = False
        self._accepting, self._closed = True, False
        self._inflight = 0
        self._resources = []
        self._lease = None
        self._lease_key = None
        self._native = None
        self._snapshot = None
        self._blocked = False
        self._reason = UNCONFIGURED if root == "" else UNAVAILABLE
        self._last_error = None

    def _check(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise WatchlistError()
        if self._clock() >= deadline:
            raise WatchlistError()
        with self._state:
            if not self._accepting:
                raise WatchlistError()

    def _call(self, deadline, function, *args, **kwargs):
        self._check(deadline)
        result = function(*args, **kwargs)
        self._check(deadline)
        return result

    @contextmanager
    def _operation(self, deadline, *, starting=False):
        self._check(deadline)
        with self._state:
            if not self._accepting or (not starting and not self._initialized):
                raise WatchlistError(self._reason)
            self._inflight += 1
        acquired = False
        try:
            remaining = max(0, deadline - self._clock())
            acquired = self._serial.acquire(timeout=remaining)
            if not acquired:
                raise WatchlistError()
            self._check(deadline)
            if self._resources:
                raise WatchlistError(MAINTENANCE)
            yield
            self._check(deadline)
        finally:
            try:
                if acquired:
                    self._serial.release()
            finally:
                with self._state:
                    self._inflight -= 1

    def _invalidate(self, reason):
        with self._state:
            self._ready = False
            self._reason = reason

    def _now(self, deadline):
        return self._call(deadline, lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def _retire(self, resource):
        try:
            resource.close()
        except BaseException as exc:
            self._last_error = exc
            with self._state:
                self._blocked = True
            return exc
        with self._state:
            self._resources = [item for item in self._resources if item is not resource]
        return None

    @contextmanager
    def _owned(self, resource, deadline):
        # open/scandir返回后先接管，动作晚回也一定经过关闭；失败资源不丢引用。
        with self._state:
            self._resources.append(resource)
        primary = None
        try:
            self._check(deadline)
            yield resource
        except BaseException as exc:
            primary = exc
            raise
        finally:
            cleanup = self._retire(resource)
            if cleanup is not None:
                if primary is not None:
                    primary.add_note("个人观察资源关闭未确认，owner保留引用供后继关闭")
                else:
                    raise cleanup
            elif primary is None:
                self._check(deadline)

    def _read_state(self, deadline):
        names, raw = self._read_bytes(deadline)
        snapshot = self._call(deadline, decode_snapshot, raw)
        with self._state:
            self._snapshot = snapshot
            self._ready = True
            self._blocked = _TEMP in names
            self._reason = MAINTENANCE if self._blocked else None
        return snapshot, raw

    def _commit(self, snapshot, deadline):
        raw = self._call(deadline, encode_snapshot, snapshot)
        publication = Publication()
        try:
            self._publish_bytes(raw, deadline, publication)
            reread, confirmed = self._read_state(deadline)
            if confirmed != raw or reread != snapshot or self._blocked:
                raise WatchlistError(UNKNOWN)
            return reread
        except BaseException as exc:
            self._last_error = exc
            self._invalidate(UNKNOWN if publication.replacing else UNAVAILABLE)
            if publication.replacing or publication.blocked:
                with self._state:
                    self._blocked = True
            if isinstance(exc, Exception):
                raise WatchlistError(self._reason) from None
            raise

    def start(self, deadline):
        """既有读池中初始化一次；坏配置只降级本功能，失败owner仍须关闭。"""
        try:
            with self._operation(deadline, starting=True):
                if self._attempted:
                    raise WatchlistError()
                self._attempted = True
                self._prepare_root(deadline)
                initial = self._names(deadline)
                self._acquire_lease(deadline, create=_LOCK not in initial)
                locked_names = self._names(deadline)
                if not initial and locked_names == {_LOCK}:
                    stamp = self._now(deadline)
                    identity = self._call(deadline, lambda: str(uuid4()))
                    snapshot = self._call(deadline, WatchlistSnapshot, identity, 1, (), stamp)
                    self._commit(snapshot, deadline)
                else:
                    self._read_state(deadline)
            return self.capability()
        except Exception as exc:
            self._last_error = exc
            self._invalidate(str(exc) if isinstance(exc, WatchlistError) else UNAVAILABLE)
            return self.capability()

    def read(self, deadline):
        try:
            with self._operation(deadline):
                snapshot, _raw = self._read_state(deadline)
                return self._call(deadline, encode_public_snapshot, snapshot,
                                  editable=not self._blocked, reason=self._reason)
        except WatchlistError as exc:
            self._invalidate(str(exc))
            raise
        except Exception as exc:
            self._last_error = exc
            self._invalidate(UNAVAILABLE)
            raise WatchlistError() from None

    def replace(self, replacement, deadline):
        """锁内完整比较并保存；ID/版本失配409，精确no-op保持原时间与版本。"""
        attempted_save = False
        try:
            with self._operation(deadline):
                if type(replacement) is not WatchlistReplacement:
                    raise WatchlistError("个人观察保存请求格式无效", code=422)
                try:
                    request = self._call(deadline, replacement.validated)
                except (ValueError, TypeError, UnicodeError):
                    raise WatchlistError("个人观察保存请求格式无效", code=422) from None
                old, _raw = self._read_state(deadline)
                if self._blocked:
                    raise WatchlistError(MAINTENANCE)
                if old.watchlist_id != request.watchlist_id or old.version != request.expected_version:
                    raise WatchlistError(CONFLICT, code=409)
                if old.symbols == request.symbols:
                    current = old
                else:
                    if old.version == MAX_VERSION:
                        raise WatchlistError("个人观察版本已达上限，当前暂不能保存变更")
                    stamp = self._now(deadline)
                    current = self._call(deadline, WatchlistSnapshot, old.watchlist_id,
                                         old.version + 1, request.symbols, stamp)
                    attempted_save = True
                    current = self._commit(current, deadline)
                return self._call(deadline, encode_replacement_result, snapshot=current,
                                  previous=old, request=request)
        except WatchlistError as exc:
            if exc.code >= 500:
                self._invalidate(UNKNOWN if attempted_save else str(exc))
                if attempted_save:
                    raise WatchlistError(UNKNOWN) from None
            raise
        except Exception as exc:
            self._last_error = exc
            self._invalidate(UNAVAILABLE)
            raise WatchlistError() from None

    def capability(self):
        with self._state:
            available = self._ready and self._initialized and self._accepting and not self._resources
            editable = available and not self._blocked
            reason = None if editable else self._reason or UNAVAILABLE
            return {"available": bool(available), "editable": bool(editable), "max_items": MAX_ITEMS,
                    "scope": "personal-observation", "affects_strategy": False, "reason": reason}

    def close(self, timeout=0):
        """停止准入且不轮询等在途；已拥有资源逐项尝试关闭，OS调用不可抢占。

        timeout沿应用owner接口保留；读池承担等待预算。本方法并发调用时只有
        一位关闭者推进，其他调用返回未确认，允许稍后按原owner续核。
        """
        if not self._close_serial.acquire(blocking=False):
            return False
        try:
            return self._close_owned()
        finally:
            self._close_serial.release()

    def _close_owned(self):
        with self._state:
            self._accepting = False
            self._ready = False
            if self._closed:
                return True
            if self._inflight:
                return False
            resources = tuple(self._resources)
        errors = []
        for resource in resources:
            error = self._retire(resource)
            if error is not None:
                errors.append(error)
        if not self._resources and self._lease is not None:
            lease = self._lease
            try:
                lease.close()
                self._lease = None
                self._lease_key = None
            except BaseException as exc:
                errors.append(exc)
        with self._state:
            self._closed = not self._resources and self._lease is None
        if errors:
            self._last_error = errors[-1]
            if len(errors) == 1:
                raise errors[0]
            raise BaseExceptionGroup("个人观察关闭异常", errors)
        return self._closed
