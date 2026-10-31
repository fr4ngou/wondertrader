"""有限原生账户子进程及单轮共享owner；取消只释放各自等待席位。"""

import asyncio
import hashlib
import json
import math
import struct
import subprocess
from concurrent.futures import Future
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4

from .account_projection import AccountProtocolError, integer, project_account, require, text, unavailable_account, validate_observation
from .contracts.account import AccountClose
from .thread_owner import ThreadOwner
from .account_scan_config import validate_account_scan_configuration

FRAME_BYTES = 20 * 1024 * 1024
STDERR_BYTES = 64 * 1024
ERROR_CODES = {"ok", "configuration", "source", "close", "internal"}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def decode_json(data):
    """长度由调用者先准入；解析前限制嵌套深度，JSON只接收有限值。"""
    depth, quoted, escaped = 0, False, False
    for byte in data:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            require(depth <= 32)
        elif byte in (93, 125):
            depth -= 1
            require(depth >= 0)
    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                            parse_constant=lambda _value: require(False))
    except (ValueError, UnicodeError, RecursionError):
        raise AccountProtocolError("invalid_protocol") from None
    pending = [result]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, float):
            require(math.isfinite(value))
    require(isinstance(result, dict))
    return result


@dataclass(frozen=True)
class AccountScanConfig:
    """旧六字段构造兼容；新来源事实只取递归不可变configuration快照。

    配置事实只由不可变快照拥有；schema2的原body摘要在准入时一次捕获。
    安装句柄/SHA归native，进程回收归运行owner，每轮父端不重读配置文件。
    schema2运行由应用唯一ManagedAccountScan持有；来源可用性以本轮查询结果为准。
    """

    executable: str
    config_path: str
    account: str
    environment: str
    total_seconds: float = 15.0
    max_rows: int = 4096
    configuration: object = field(default=None, repr=False)
    raw_configuration: InitVar[bytes | None] = field(default=None, repr=False)
    configuration_sha256: str | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_paths(cls, executable, config_path):
        if not executable and not config_path:
            return None
        executable_path, binding_path = Path(executable), Path(config_path)
        require(executable_path.is_absolute() and binding_path.is_absolute() and executable_path.is_file() and binding_path.is_file())
        try:
            with binding_path.open("rb") as stream:
                data = stream.read(65537)
        except OSError:
            raise AccountProtocolError("invalid_configuration") from None
        require(len(data) <= 65536)
        binding = validate_account_scan_configuration(decode_json(data))
        trader, budget = binding["trader"], binding["budget"]
        return cls(str(executable_path), str(binding_path), trader["expected_account"], trader["environment"],
                   budget.get("total_ms", 15000) / 1000, trader.get("max_rows", 4096), binding, raw_configuration=data)

    def __post_init__(self, raw_configuration):
        if self.configuration is not None:
            # 新快照的兼容字段只接普通标量，等值运算不接受自定义转换/比较。
            require(type(self.executable) is str and type(self.config_path) is str
                    and type(self.account) is str and type(self.environment) is str
                    and type(self.total_seconds) in (int, float))
        require(Path(self.executable).is_absolute() and Path(self.config_path).is_absolute())
        require(text(self.account) and text(self.environment) and not isinstance(self.total_seconds, bool)
                and 1 <= self.total_seconds <= 30 and integer(self.max_rows, 1, 4096))
        if self.configuration is not None:
            snapshot = validate_account_scan_configuration(self.configuration)
            trader, budget = snapshot["trader"], snapshot["budget"]
            require(self.account == trader["expected_account"] and self.environment == trader["environment"]
                    and self.max_rows == trader.get("max_rows", 4096)
                    and self.total_seconds == budget.get("total_ms", 15000) / 1000)
            if snapshot["schema_version"] == 2:
                # 原文件body只参与本次纯准入；不存raw，不接受调用方自报digest。
                require(type(raw_configuration) is bytes and 0 < len(raw_configuration) <= 65536)
                from_raw = validate_account_scan_configuration(decode_json(raw_configuration))
                require(from_raw == snapshot)
                object.__setattr__(self, "configuration_sha256", hashlib.sha256(raw_configuration).hexdigest())
            object.__setattr__(self, "configuration", snapshot)

    @property
    def schema_version(self):
        return self.configuration["schema_version"] if self.configuration is not None else 1

    @property
    def source(self):
        return self.configuration["trader"]["source"] if self.configuration is not None else "qmt_http"

    @property
    def read_profile_version(self):
        return self.configuration["trader"]["read_profile_version"] if self.schema_version == 2 else None

    @property
    def ipc_schema(self):
        return "guanheng.account-scan.v2" if self.schema_version == 2 else "guanheng.account-scan.v1"

    @property
    def inspection_version(self):
        return 3 if self.schema_version == 2 else 2

    @property
    def public_schema_version(self):
        return "2.0" if self.schema_version == 2 else "1.0"

    @property
    def runtime_available(self):
        """已实现的配置版本；真实账户是否可读取由本轮有界查询确认。"""
        return self.schema_version in (1, 2)

def _read_exact(stream, size):
    parts, remaining = [], size
    while remaining:
        part = stream.read(min(remaining, 65536))
        require(bool(part))
        parts.append(part)
        remaining -= len(part)
    return b"".join(parts)


def _completion(frame, scan_id, *, schema="guanheng.account-scan.v1"):
    require(schema in ("guanheng.account-scan.v1", "guanheng.account-scan.v2"))
    require(set(frame) == {"schema", "scan_id", "kind", "closed", "joined", "worker_live", "queued", "elapsed_ms", "error_code"})
    require(frame["schema"] == schema and frame["scan_id"] == scan_id and frame["kind"] == "completion")
    require(all(type(frame[key]) is bool for key in ("closed", "joined", "worker_live")))
    require(integer(frame["queued"]) and integer(frame["elapsed_ms"], maximum=60000) and frame["error_code"] in ERROR_CODES)
    return frame


def run_account_scan(config, scan_id, deadline, stop, *, runtime=None):
    """唯一owner创建/终止/wait本轮进程；双管道线程仅传有界验证值，stderr不保留正文。"""
    if config.schema_version == 2:
        # 新来源只能交给应用持有的完整生命周期owner；直接临时调用不能丢失未回收资源。
        from .account_scan_runtime import ManagedAccountScan
        if not isinstance(runtime, ManagedAccountScan):
            return unavailable_account("受管账户owner尚未装配，请等待同版运行入口", scan_id, schema_version="2.0")
        return runtime.run(config, scan_id, deadline, stop)
    observation, completion, protocol_error = None, None, Event()
    process = None
    readers = []
    forced = False
    forced_reason = None
    try:
        if stop.is_set() or deadline <= monotonic():
            return unavailable_account("账户读取预算已耗尽或应用已关闭，请稍后刷新", scan_id)
        process = subprocess.Popen([config.executable, "--config", config.config_path, "--scan-id", scan_id],
                                   cwd=str(Path(config.executable).parent), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)

        def stdout():
            nonlocal observation, completion
            try:
                count = 0
                while True:
                    header = process.stdout.read(4)
                    if not header:
                        break
                    require(len(header) == 4 and count < 2 and completion is None)
                    length = struct.unpack(">I", header)[0]
                    require(0 < length <= FRAME_BYTES)
                    frame = decode_json(_read_exact(process.stdout, length))
                    if frame.get("kind") == "observation":
                        require(count == 0)
                        observation = validate_observation(frame, scan_id, config)
                    else:
                        completion = _completion(frame, scan_id)
                    count += 1
                require(completion is not None)
            except BaseException:
                protocol_error.set()
            finally:
                # 错误后仍消费到EOF，避免子进程阻于写管道；owner看到错误会立即回收。
                try:
                    while process.stdout.read(65536):
                        pass
                except (OSError, ValueError):
                    pass

        def stderr():
            total = 0
            try:
                while True:
                    part = process.stderr.read(4096)
                    if not part:
                        return
                    total += len(part)
                    if total > STDERR_BYTES:
                        protocol_error.set()
            except (OSError, ValueError):
                protocol_error.set()

        readers = [Thread(target=stdout, name="guanheng-account-stdout"), Thread(target=stderr, name="guanheng-account-stderr")]
        for thread in readers:
            thread.start()
        stop_grace_deadline = None
        while process.poll() is None:
            now = monotonic()
            if stop.is_set() and stop_grace_deadline is None:
                # CLI没有取消控制帧；在原绝对预算内给宿主有限自然收尾机会。
                stop_grace_deadline = min(deadline, now + 0.25)
            if protocol_error.is_set() or now >= deadline or (stop_grace_deadline is not None and now >= stop_grace_deadline):
                forced = True
                forced_reason = "protocol" if protocol_error.is_set() else "stopped" if stop.is_set() else "timeout"
                process.terminate()
                break
            protocol_error.wait(min(0.01, max(0, deadline - now)))
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            forced = True
            forced_reason = forced_reason or "timeout"
            process.kill()
            process.wait(timeout=0.5)
        # 管道仅由本轮产品宿主持有。进程已wait后EOF使读取线程真实退出。
        for thread in readers:
            thread.join(0.5)
        require(not any(thread.is_alive() for thread in readers))
        code = forced_reason if forced else "protocol" if protocol_error.is_set() else "missing_completion"
        normal = False
        if completion is not None and not forced and not protocol_error.is_set():
            code = completion["error_code"]
            normal = (process.returncode == 0 and code == "ok" and completion["closed"] and completion["joined"]
                      and not completion["worker_live"] and completion["queued"] == 0 and observation is not None
                      and observation[2] and all(group.status == "complete" for group in observation[0].values()))
            # 退出码和完成帧分别核对；关闭失败/来源失败不能授完整观察。
            consistent_exit = {"ok": 0, "configuration": 2, "internal": 2, "source": 3, "close": 4}[code]
            if process.returncode != consistent_exit:
                code, normal = "protocol", False
            if code == "ok" and not normal:
                code = "protocol"
        close = AccountClose(status="complete" if normal else "forced" if forced else "failed",
                             closed=bool(completion and completion["closed"] and not forced),
                             joined=bool(completion and completion["joined"] and not forced),
                             worker_live=bool(completion and completion["worker_live"]), queued=completion["queued"] if completion else 0,
                             exit_code=process.returncode, error_code=code)
        return project_account(scan_id, observation, close)
    except BaseException:
        return project_account(scan_id, observation, AccountClose(status="forced" if process else "failed", error_code="internal"))
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=1)
            for thread in readers:
                thread.join(1)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


class AccountCapacityError(RuntimeError):
    pass


class AccountScanOwner:
    """每轮一个进程、最多16个等待者；HTTP取消/超时不会取消共享Future或延长本轮预算。"""

    def __init__(self, config=None):
        self.config = config
        self._lock, self._stop = Lock(), Event()
        self._managed = None
        if config is not None and config.schema_version == 2:
            from .account_scan_runtime import ManagedAccountScan
            self._managed = ManagedAccountScan()
        self._accepting, self._waiters, self._thread, self._future, self._scan_id = True, 0, None, None, None

    async def read(self, deadline=None):
        if self.config is None:
            return unavailable_account()
        with self._lock:
            if not self._accepting:
                return unavailable_account("账户读取已停止，请等待应用恢复后刷新", schema_version=self.config.public_schema_version)
            if self._waiters >= 16:
                raise AccountCapacityError("账户读取繁忙，当前等待人数已达16，请稍后刷新")
            if deadline is None:
                deadline = monotonic() + self.config.total_seconds
            if deadline <= monotonic():
                return unavailable_account("账户读取预算已耗尽，请稍后刷新", schema_version=self.config.public_schema_version)
            if self._thread is not None:
                # 只在锁内零等待收集join证明；启动未知/退出未知均保留原owner。
                joined = self._thread.join_until(monotonic(), clock=monotonic)
                if not joined and self._future.done():
                    raise AccountCapacityError("上一轮账户工作线程回收尚未确认，请稍后刷新")
            if self._thread is None or not self._thread.pending:
                if self._managed is not None and not self._managed.reap(monotonic()):
                    raise AccountCapacityError("上一轮账户子树或管道回收尚未确认，请稍后刷新")
                self._scan_id, self._future = str(uuid4()), Future()
                # 采集预算归owner；首个等待者较短的HTTP截止也不撤销其他认领者。
                scan_deadline = monotonic() + self.config.total_seconds
                self._thread = None
                try:
                    self._thread = ThreadOwner(target=self._work, args=(self._scan_id, self._future, scan_deadline),
                                               name="guanheng-account-owner", thread_factory=Thread)
                    self._thread.start()
                except BaseException:
                    # start异常仍由先保存的ThreadOwner持有；晚target受原Future门禁。
                    # 不用ident/is_alive或业务target结束推断OS线程已回收。
                    result = unavailable_account("账户读取工作线程未能正常启动，请稍后刷新", self._scan_id,
                                                 AccountClose(status="failed", error_code="internal"),
                                                 schema_version=self.config.public_schema_version)
                    if not self._future.done():
                        self._future.set_result(result)
                    return result
            future, scan_id = self._future, self._scan_id
            self._waiters += 1
        wrapped = asyncio.wrap_future(future)
        wrapped.add_done_callback(lambda completed: None if completed.cancelled() else completed.exception())
        try:
            return await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline - monotonic()))
        except TimeoutError:
            return unavailable_account("本次等待已超时，本轮读取仍按原预算回收，请稍后刷新", scan_id, schema_version=self.config.public_schema_version)
        finally:
            with self._lock:
                self._waiters -= 1

    def _work(self, scan_id, future, deadline):
        # read持同一锁完成start准入；start失败的已完成Future封住晚到的target。
        with self._lock:
            if future.done():
                return
            if not self._accepting or self._stop.is_set():
                future.set_result(unavailable_account("账户读取已停止，请等待应用恢复后刷新", scan_id,
                                                      schema_version=self.config.public_schema_version))
                return
        try:
            if self._managed is not None:
                result = run_account_scan(self.config, scan_id, deadline, self._stop, runtime=self._managed)
            else:
                result = run_account_scan(self.config, scan_id, deadline, self._stop)
            future.set_result(result)
        except BaseException:
            future.set_result(unavailable_account("本轮账户读取内部失败，请稍后刷新", scan_id, schema_version=self.config.public_schema_version))

    def close(self, timeout=2.0):
        # schema2关闭沿本次调用唯一截止续核；旧runner保持原关闭语义。
        if self._managed is not None and (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout < 0):
            with self._lock:
                self._accepting = False
                self._stop.set()
            return False
        close_deadline = monotonic() + max(0, timeout)
        with self._lock:
            self._accepting = False
            self._stop.set()
            thread = self._thread
        # 预算等待在业务锁外，ThreadOwner独占标准启动/真实join证明。
        stopped = thread is None or thread.join_until(close_deadline, clock=monotonic)
        if self._managed is not None:
            return stopped and self._managed.reap(close_deadline)
        return stopped

    @property
    def active_waiters(self):
        with self._lock:
            return self._waiters

    @property
    def live_threads(self):
        with self._lock:
            if self._thread is not None:
                self._thread.join_until(monotonic(), clock=monotonic)  # 零等待，不阻塞target所需锁。
            pending = self._thread is not None and self._thread.pending
        return int(pending) + (self._managed.live_threads if self._managed else 0)
