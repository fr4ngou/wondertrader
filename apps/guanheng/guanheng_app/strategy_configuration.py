"""App配置版本owner：CAS/请求回执归本层，原生生效状态归运行宿主。"""

from contextlib import contextmanager
import math
from threading import Lock
from time import monotonic
from uuid import uuid4

from guanheng_strategy_core import KernelValidationError
from guanheng_strategy_v1 import RetainedValidationError

from .contracts.strategy_configuration import (
    ConfigurationValueError, MAX_STATE_BYTES, MAX_VERSIONS, PREFIX, STATE_SCHEMA, WORKSPACE_SCHEMA,
    catalog, decode, encode, identity, save_request, state, utc_now, validation,
)
from .local_document_io import LocalDocumentIO, Publication

UNAVAILABLE = "策略配置暂不可用，请重新读取或检查配置目录"
UNCONFIGURED = "策略配置保存尚未配置；可先查看版本和校验业务参数"
MAINTENANCE = "策略配置原件需要维护，当前暂停编辑，请停止全部写入者后核查"
UNKNOWN = "策略配置保存结果尚未确认，请沿原请求编号重新读取核实"
CONFLICT = "策略配置版本已变化，请重新读取并确认当前版本"


class StrategyConfigurationError(RuntimeError):
    """固定公开说明与HTTP状态；底层异常保留于owner私有字段。"""

    def __init__(self, reason=UNAVAILABLE, *, code=503):
        super().__init__(reason)
        self.code = code


class StrategyConfigurationOwner(LocalDocumentIO):
    """构造零IO；lifespan发布后在原读池start，所有文件操作串行且有界。"""

    _document_main = "strategy-configurations.json"
    _document_lock = ".strategy-configurations.lock"
    _document_temp = "strategy-configurations.tmp"
    _document_limits = {_document_main: MAX_STATE_BYTES, _document_lock: 16, _document_temp: MAX_STATE_BYTES}
    _io_error, _io_maintenance = StrategyConfigurationError, MAINTENANCE

    def __init__(self, root="", *, clock=monotonic):
        self.owner_id = uuid4().hex
        self._root_text, self._clock = root, clock
        self._state, self._serial, self._close_serial = Lock(), Lock(), Lock()
        self._root = self._root_key = self._native = self._lease = self._lease_key = None
        self._attempted = self._initialized = self._ready = self._closed = self._blocked = self._full = False
        self._accepting, self._inflight, self._resources = True, 0, []
        self._reason = UNCONFIGURED if root == "" else UNAVAILABLE
        self._last_error = None

    def _check(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or self._clock() >= deadline:
            raise StrategyConfigurationError()
        with self._state:
            if not self._accepting:
                raise StrategyConfigurationError()

    def _call(self, deadline, function, *args, **kwargs):
        self._check(deadline)
        result = function(*args, **kwargs)
        self._check(deadline)
        return result

    def _open_file(self, name, mode):
        return open(self._root / name, mode)

    def _invalidate(self, reason):
        with self._state:
            self._ready, self._reason = False, reason

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
            error = self._retire(resource)
            if error is not None:
                if primary is not None:
                    primary.add_note("策略配置资源关闭未确认，owner保留引用供后继关闭")
                else:
                    raise error
        self._check(deadline)

    @contextmanager
    def _operation(self, deadline, *, starting=False):
        self._check(deadline)
        with self._state:
            if not self._accepting or not starting and not self._initialized:
                raise StrategyConfigurationError(self._reason)
            self._inflight += 1
        acquired = False
        try:
            acquired = self._serial.acquire(timeout=max(0, deadline - self._clock()))
            if not acquired:
                raise StrategyConfigurationError()
            self._check(deadline)
            if self._resources:
                raise StrategyConfigurationError(MAINTENANCE)
            yield
            self._check(deadline)
        finally:
            if acquired:
                self._serial.release()
            with self._state:
                self._inflight -= 1

    def _read_state(self, deadline):
        names, raw = self._read_bytes(deadline)
        snapshot = self._call(deadline, state, decode(raw, MAX_STATE_BYTES))
        with self._state:
            self._ready, self._blocked = True, self._document_temp in names
            self._full = snapshot["revision"] == MAX_VERSIONS
            self._reason = MAINTENANCE if self._blocked else "策略配置已达32个版本，现有原件保留，当前暂停新增" if self._full else None
        return snapshot, raw

    def _commit(self, snapshot, deadline):
        raw = self._call(deadline, encode, snapshot)
        publication = Publication()
        try:
            self._publish_bytes(raw, deadline, publication)
            reread, confirmed = self._read_state(deadline)
            if confirmed != raw or self._blocked:
                raise StrategyConfigurationError(UNKNOWN)
            return reread
        except BaseException as exc:
            self._last_error = exc
            self._invalidate(UNKNOWN if publication.replacing else UNAVAILABLE)
            if publication.replacing or publication.blocked:
                with self._state:
                    self._blocked = True
            if isinstance(exc, Exception):
                raise StrategyConfigurationError(self._reason) from None
            raise

    def start(self, deadline):
        """坏根只降级配置保存；所有取得的锁/资源仍由本owner关闭。"""
        if self._root_text == "":
            return self.capability()
        try:
            with self._operation(deadline, starting=True):
                if self._attempted:
                    raise StrategyConfigurationError()
                self._attempted = True
                self._prepare_root(deadline)
                initial = self._names(deadline)
                self._acquire_lease(deadline, create=self._document_lock not in initial)
                locked = self._names(deadline)
                if not initial and locked == {self._document_lock}:
                    self._commit({"schema": STATE_SCHEMA, "store_id": uuid4().hex, "revision": 0, "versions": []}, deadline)
                else:
                    self._read_state(deadline)
        except Exception as exc:
            self._last_error = exc
            self._invalidate(str(exc) if isinstance(exc, StrategyConfigurationError) else UNAVAILABLE)
        return self.capability()

    def capability(self):
        with self._state:
            available = bool(self._ready and self._initialized and self._accepting and not self._resources)
            editable = available and not self._blocked and not self._full
            return {"available": available, "editable": editable, "max_versions": MAX_VERSIONS,
                    "scope": "app-configuration-versions", "runtime_effect": False,
                    "reason": None if editable else self._reason or UNAVAILABLE}

    def read(self, deadline):
        """重新读持久原件；失败返回明确不可用工作区，历史缓存不成为可编辑依据。"""
        snapshot = None
        if self._root_text != "":
            try:
                with self._operation(deadline):
                    snapshot, _raw = self._read_state(deadline)
            except Exception as exc:
                self._last_error = exc
                self._invalidate(str(exc) if isinstance(exc, StrategyConfigurationError) else MAINTENANCE)
        self._check(deadline)
        capability = self.capability()
        return encode({"schema": WORKSPACE_SCHEMA, "owner_id": self.owner_id,
            **{key: capability[key] for key in ("available", "editable", "reason")},
            "catalog": catalog(), "store": snapshot, "max_versions": MAX_VERSIONS, "runtime_effect": False})

    def validate(self, value, deadline):
        """纯配置校验独立于保存根；当前时间记录校验时点，实际计算准入仍归原核。"""
        self._check(deadline)
        try:
            result = validation(value, utc_now())
        except (KernelValidationError, RetainedValidationError, ConfigurationValueError):
            raise StrategyConfigurationError("策略参数未通过正式1.1.2校验，请检查策略预算与固定参数", code=422) from None
        self._check(deadline)
        return encode(result)

    def save(self, value, deadline):
        """同ID先返回原receipt；CAS和追加在同锁内，落盘后重读再发布成功。"""
        attempted = False
        try:
            request, config_sha, request_sha = save_request(value)
            with self._operation(deadline):
                current, _raw = self._read_state(deadline)
                if current["store_id"] != request["store_id"]:
                    raise StrategyConfigurationError(CONFLICT, code=409)
                previous = next((row for row in current["versions"] if row["request_id"] == request["request_id"]), None)
                if previous is not None:
                    if previous["request_sha256"] != request_sha:
                        raise StrategyConfigurationError("原请求编号已绑定另一份配置，请核查原回执", code=409)
                    return self._saved(current["store_id"], previous)
                if self._blocked:
                    raise StrategyConfigurationError(MAINTENANCE)
                if current["revision"] != request["expected_revision"]:
                    raise StrategyConfigurationError(CONFLICT, code=409)
                if current["revision"] >= MAX_VERSIONS:
                    raise StrategyConfigurationError("策略配置已达32个版本，现有原件保留，当前暂停新增")
                receipt = {"revision": current["revision"] + 1, "request_id": request["request_id"],
                    "request_sha256": request_sha, "configuration_sha256": config_sha,
                    "configuration": request["configuration"], "saved_at": utc_now()}
                updated = {**current, "revision": receipt["revision"], "versions": [*current["versions"], receipt]}
                attempted = True
                confirmed = self._commit(updated, deadline)
                return self._saved(confirmed["store_id"], confirmed["versions"][-1])
        except (KernelValidationError, RetainedValidationError, ConfigurationValueError):
            raise StrategyConfigurationError("策略配置保存请求未通过业务校验", code=422) from None
        except StrategyConfigurationError as exc:
            if attempted:
                raise StrategyConfigurationError(UNKNOWN) from None
            raise exc
        except Exception as exc:
            self._last_error = exc
            self._invalidate(UNKNOWN if attempted else UNAVAILABLE)
            raise StrategyConfigurationError(UNKNOWN if attempted else UNAVAILABLE) from None

    @staticmethod
    def _saved(store_id, receipt):
        return encode({"schema": PREFIX + "saved.v1", "store_id": store_id, "receipt": receipt, "runtime_effect": False})

    def lookup(self, store_id, request_id, deadline):
        try:
            identity(store_id)
            identity(request_id)
            with self._operation(deadline):
                current, _raw = self._read_state(deadline)
                if current["store_id"] != store_id:
                    raise StrategyConfigurationError(CONFLICT, code=409)
                receipt = next((row for row in current["versions"] if row["request_id"] == request_id), None)
                return encode({"schema": PREFIX + "request.v1", "store_id": store_id, "request_id": request_id,
                               "status": "saved" if receipt is not None else "absent", "receipt": receipt})
        except ConfigurationValueError:
            raise StrategyConfigurationError("策略配置请求身份无效", code=422) from None
        except StrategyConfigurationError:
            raise
        except Exception as exc:
            self._last_error = exc
            self._invalidate(MAINTENANCE)
            raise StrategyConfigurationError(MAINTENANCE) from None

    def close(self, timeout=0):
        """先停准入；在途继续归原worker，读池排空后续核并释放原OS锁。"""
        if not self._close_serial.acquire(blocking=False):
            return False
        try:
            with self._state:
                self._accepting, self._ready = False, False
                if self._inflight:
                    return False
                resources = tuple(self._resources)
            errors = [error for resource in resources if (error := self._retire(resource)) is not None]
            if not self._resources and self._lease is not None:
                try:
                    self._lease.close()
                    self._lease = self._lease_key = None
                except BaseException as exc:
                    errors.append(exc)
            self._closed = not self._resources and self._lease is None
            if errors:
                raise BaseExceptionGroup("策略配置资源关闭未确认", errors)
            return self._closed
        finally:
            self._close_serial.release()
