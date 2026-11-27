"""WT 日常启停入口：管理运行代际和公开 CURRENT，不拥有交易业务。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from guanheng_market_client.runtime_status import (
    CollectionStatusPending,
    read_status,
    replace_status,
)

from .execution_recovery import execution_state_files, prepare_transition, require_process_exited
from .managed_local_process import _inspect, _path, _read, _require, _sha, runtime_control_path
from .runtime import RuntimeConfig, _READ_ONLY_PROCESSES


_CURRENT_FIELDS = {
    "schema",
    "wt_status_file",
    "wt_control_id",
    "wt_instance_id",
    "wt_configuration_sha256",
}
_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")


def _connect_daily_publication(runtime: dict, publication: dict) -> None:
    """正式续接由当前发布器描述符导出原生Reader实际读取的状态路径。"""
    component = runtime['components'].get('analysis_window')
    if component is None or 'source_root' not in publication:
        return
    raw, descriptor = _json_file(_path(component['descriptor'], e_drive=True), 65536)
    _require(hashlib.sha256(raw).hexdigest() == _sha(component['sha256'])
             and descriptor.get('schema') == 'guanheng.analysis-window-deployment.v1')
    producer = descriptor['configuration']['producer']
    source = _path(producer['directory'], e_drive=True)
    _require(_path(producer['publication'], e_drive=True) == _path(publication['publication_file'], e_drive=True))
    previous = _path(publication['source_root'], e_drive=True)
    _require(previous.parent == source.parent and _path(publication['status_file'], e_drive=True) == previous / 'STATUS.json')
    publication.update(status_file=str(source / 'STATUS.json'), source_root=str(source))


def _canonical(value: dict) -> bytes:
    """生成配置和收据使用同一确定性 JSON 字节；不接收 NaN。"""
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _write_exclusive(path: Path, value: dict) -> str:
    """向本代私有目录一次写入完整正文，返回原字节 SHA256。"""
    raw = _canonical(value)
    with path.open("xb") as stream:
        stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def _publish(path: Path, value: dict) -> None:
    """通过 SDK 原子替换协议发布共享 CURRENT 或停止请求。"""
    pending = path.parent / ("." + path.name + "." + str(uuid4()))
    raw = _canonical(value)
    with pending.open("xb") as stream:
        stream.write(raw)
    replace_status(pending, path)


def _json_file(path: Path, maximum: int) -> tuple[bytes, dict]:
    raw = _read(path, maximum)
    value = json.loads(raw.decode("utf-8"))
    _require(type(value) is dict)
    return raw, value


def _pinned_json(path: Path, expected_sha256: str, maximum: int) -> dict:
    raw, value = _json_file(path, maximum)
    _require(hashlib.sha256(raw).hexdigest() == _sha(expected_sha256))
    return value


def _canonical_uuid(value: str) -> str:
    _require(type(value) is str and str(UUID(value)) == value)
    return value


def _process_identity(pid: int) -> int | None:
    """读取Windows进程创建FILETIME；PID与创建时间共同排除复用。"""
    if type(pid) is not int or pid <= 0:
        return None
    if os.name == "nt":
        import ctypes

        class FileTime(ctypes.Structure):
            _fields_ = (
                ("low", ctypes.c_uint32),  # Windows FILETIME低32位，单位100纳秒；与高位组合为创建身份。
                ("high", ctypes.c_uint32),  # Windows FILETIME高32位，来源为本次打开的进程句柄。
            )

        process_query_limited_information = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetProcessTimes.argtypes = (ctypes.c_void_p,) + (ctypes.POINTER(FileTime),) * 4
        kernel32.GetProcessTimes.restype = ctypes.c_int
        kernel32.GetExitCodeProcess.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return None
        try:
            # Windows在其他owner仍持有句柄时保留已退出进程；创建时间本身不能证明存活。
            code = ctypes.c_uint32()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
                return None
            created, exited, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
            if not kernel32.GetProcessTimes(handle, *(ctypes.byref(item) for item in (created, exited, kernel, user))):
                return None
            return (created.high << 32) | created.low
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return pid
    except (OSError, ProcessLookupError):
        return None


def _process_exists(pid: int) -> bool:
    return _process_identity(pid) is not None


@dataclass(frozen=True)
class ServiceConfig:
    """日常控制私有配置；公开 CURRENT 只投影五个冻结身份字段。"""

    pythonw: Path  # 安装后 WT 无窗口解释器绝对路径；启动本代 Runtime，正文不进入公开指针。
    pythonw_sha256: str  # 上述解释器原字节 SHA256；每次真实 start 前重新核对。
    bootstrap_configuration: Path  # 首次纳管或既有正式代的 Runtime 配置绝对路径。
    bootstrap_configuration_sha256: str  # 首代配置原字节 SHA256；兼作既有代私有定位依据。
    control_root: Path  # 每代 WT control_id 子目录的父目录；旧代收据永久保留。
    generation_root: Path  # 各代新配置、恢复材料和启动收据的私有父目录。
    current_file: Path  # 严格五字段 guanheng.wt-current.v1 的稳定公开文件。
    environment_file: Path  # 启动环境私有 JSON；值只注入子进程，禁止进入输出或 CURRENT。
    environment_sha256: str  # 环境正文原字节 SHA256；防止 start 前输入漂移。
    private_control_root: Path | None = None  # 后继父运行代的目录；缺省使用原 control_root，旧收据保留原位置。

    @classmethod
    def from_path(cls, path: str | Path) -> "ServiceConfig":
        """读取严格私有配置；仅验证身份，不启动进程或读取账户事实。"""
        source = runtime_control_path(str(path))
        _, value = _json_file(source, 64 * 1024)
        result = cls.from_mapping(value)
        _require(source.drive.casefold() == result.control_root.drive.casefold())
        return result

    @classmethod
    def from_mapping(cls, value: dict) -> "ServiceConfig":
        """解析已读取并由调用者固定的私有配置，供组入口和独立入口共用。"""
        fields = {
            "schema",
            "pythonw",
            "pythonw_sha256",
            "bootstrap_configuration",
            "bootstrap_configuration_sha256",
            "control_root",
            "generation_root",
            "current_file",
            "environment_file",
            "environment_sha256",
        }
        _require(type(value) is dict and fields <= set(value) <= fields | {"private_control_root"}
                 and value["schema"] == "guanheng.wt-service.v1")
        result = cls(
            pythonw=runtime_control_path(value["pythonw"]),
            pythonw_sha256=_sha(value["pythonw_sha256"]),
            bootstrap_configuration=runtime_control_path(value["bootstrap_configuration"]),
            bootstrap_configuration_sha256=_sha(value["bootstrap_configuration_sha256"]),
            control_root=runtime_control_path(value["control_root"]),
            generation_root=runtime_control_path(value["generation_root"]),
            current_file=runtime_control_path(value["current_file"]),
            environment_file=runtime_control_path(value["environment_file"]),
            environment_sha256=_sha(value["environment_sha256"]),
            private_control_root=(runtime_control_path(value["private_control_root"])
                                  if "private_control_root" in value else None),
        )
        result.validate()
        return result

    def validate(self) -> None:
        """核固定安装和存储边界；CURRENT 本身允许首次启动前尚不存在。"""
        for path in (self.pythonw, self.bootstrap_configuration, self.environment_file):
            _inspect(path)
        for directory in (self.control_root, self.generation_root, self.current_file.parent):
            _inspect(directory, directory=True)
        if self.private_control_root is not None:
            _inspect(self.private_control_root, directory=True)
            _require(self.private_control_root not in (self.generation_root, self.current_file.parent))
        _require(self.current_file.parent != self.generation_root)
        _require(hashlib.sha256(_read(self.pythonw, 64 * 1024 * 1024)).hexdigest() == self.pythonw_sha256)
        _require(
            hashlib.sha256(_read(self.bootstrap_configuration, 64 * 1024)).hexdigest()
            == self.bootstrap_configuration_sha256
        )
        _require(
            hashlib.sha256(_read(self.environment_file, 256 * 1024)).hexdigest()
            == self.environment_sha256
        )
        runtime = RuntimeConfig.from_path(str(self.bootstrap_configuration), self.bootstrap_configuration_sha256)
        paths = (self.pythonw, self.bootstrap_configuration, self.environment_file,
                 self.generation_root, self.current_file)
        _require(all(path.drive.casefold() == self.control_root.drive.casefold() for path in paths))
        if self.control_root.drive.casefold() != 'e:':
            _require(self.private_control_root is None)
            from .trade_host_process import validate_standalone_trade_host
            validate_standalone_trade_host(runtime.components, self.control_root)


class _ServiceLease:
    """同一 CURRENT 的变更命令串行；OS 锁随 CLI 异常退出自动释放。"""

    def __init__(self, current_file: Path):
        self.path = current_file.with_name(current_file.name + ".lock")
        self.stream = None

    def __enter__(self):
        import msvcrt

        self.stream = self.path.open("a+b")
        try:
            _inspect(self.path)
            self.stream.seek(0)
            if self.stream.read(1) == b"":
                self.stream.write(b"0")
                self.stream.flush()
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        except BaseException:
            self.stream.close()
            self.stream = None
            raise
        return self

    def __exit__(self, *unused):
        import msvcrt

        try:
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.stream.close()
            self.stream = None


def validate_current(value: dict) -> dict:
    """验证公开 CURRENT 的冻结五字段；每个字段含义见 WT 服务控制规格。"""
    _require(type(value) is dict and set(value) == _CURRENT_FIELDS)
    _require(value["schema"] == "guanheng.wt-current.v1")
    status_file = runtime_control_path(value["wt_status_file"])
    control_id = _canonical_uuid(value["wt_control_id"])
    instance_id = _canonical_uuid(value["wt_instance_id"])
    configuration_sha256 = _sha(value["wt_configuration_sha256"])
    _require(status_file.name == "status.json" and status_file.parent.name == control_id)
    return {
        "schema": "guanheng.wt-current.v1",  # 公开指针协议版本；固定值，消费者据此拒绝其它正文。
        "wt_status_file": str(status_file),  # 本代 Runtime status.json 绝对路径；可在启动早期暂未出现。
        "wt_control_id": control_id,  # 本次真实 start 的控制 UUID；绑定控制目录及停止请求。
        "wt_instance_id": instance_id,  # 跨正常重启保持的逻辑实例 UUID；标识同一策略账本。
        "wt_configuration_sha256": configuration_sha256,  # 本代 Runtime 配置原字节 SHA256。
    }


def _read_current(path: Path) -> dict | None:
    try:
        return validate_current(read_status(path, 16 * 1024))
    except FileNotFoundError:
        return None


def _runtime_status(current: dict, *, allow_pending: bool = True) -> dict | None:
    try:
        value = read_status(current["wt_status_file"], 64 * 1024)
    except FileNotFoundError:
        return None
    except CollectionStatusPending:
        if not allow_pending:
            raise
        return None
    _require(
        value.get("schema") == "guanheng.wt-runtime-status.v1"
        and value.get("control_id") == current["wt_control_id"]
        and value.get("instance_id") == current["wt_instance_id"]
        and value.get("configuration_sha256") == current["wt_configuration_sha256"]
        and type(value.get("pid")) is int
    )
    return value


def _terminal(current: dict, name: str, *, allow_pending: bool = True) -> dict | None:
    path = Path(current["wt_status_file"]).parent / name
    try:
        value = read_status(path, 16 * 1024)
    except FileNotFoundError:
        return None
    except CollectionStatusPending:
        if not allow_pending:
            raise
        return None
    expected_schema = "guanheng.wt-runtime-" + ("closed" if name == "closed.json" else "failure") + ".v1"
    _require(
        value.get("schema") == expected_schema
        and value.get("control_id") == current["wt_control_id"]
        and value.get("instance_id") == current["wt_instance_id"]
        and value.get("configuration_sha256") == current["wt_configuration_sha256"]
    )
    return value


def _safe_projection(action: str, current: dict | None, status: dict | None, state: str, *, changed: bool) -> dict:
    """CLI 只输出运行身份和有限状态；配置、账户、凭证及业务正文保持私有。"""
    components = {}
    if status is not None and type(status.get("components")) is dict:
        for name, value in status["components"].items():
            if type(name) is str and type(value) is dict:
                components[name] = {
                    key: value.get(key)
                    for key in ("state", "ready", "error_code", "pid", "quote_input_state")
                    if key in value
                }
    return {
        "schema": "guanheng.wt-service-result.v1",
        "action": action,
        "state": state,
        "ready": bool(state == "ready" and status and status.get("ready")),
        "changed": changed,
        "current": current,
        "runtime_pid": status.get("pid") if status else None,
        "error_code": status.get("error_code") if status else None,
        "components": components,
    }


class ServiceController:
    """组合既有 Runtime、恢复准备器和收据；不解释或修改金融业务。"""

    def __init__(self, config: ServiceConfig, *, launcher=None, clock=time.monotonic, sleeper=time.sleep):
        self.config = config
        self._launcher = launcher or self._launch
        self._clock = clock
        self._sleep = sleeper

    def _environment(self) -> dict[str, str]:
        raw = _read(self.config.environment_file, 256 * 1024)
        _require(hashlib.sha256(raw).hexdigest() == self.config.environment_sha256)
        value = json.loads(raw.decode("utf-8"))
        _require(type(value) is dict and 1 <= len(value) <= 128)
        for name, item in value.items():
            _require(
                type(name) is str
                and _ENVIRONMENT_NAME.fullmatch(name) is not None
                and type(item) is str
                and len(item.encode("utf-8")) <= 8192
                and chr(0) not in item
            )
        result = dict(os.environ)
        result.update(value)
        return result

    @staticmethod
    def _launch(command, cwd, environment):
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        return subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
        )

    def _record_process_loss(self, current: dict) -> bool:
        """用户显式start时调用既有Runtime核查owner；核查失败保持原代不变。"""
        runtime_path, runtime_sha = self._configuration_for(current)
        control_directory = Path(current["wt_status_file"]).parent
        command = [
            str(self.config.pythonw), "-I", "-B", "-m", "guanheng_wt_runtime",
            "--config", str(runtime_path), "--config-sha256", runtime_sha,
            "--control-directory", str(control_directory), "--control-id", current["wt_control_id"],
            "--record-process-loss",
        ]
        if control_directory.parent != self.config.control_root:
            command.extend(("--instance-lease-root", str(self.config.control_root)))
        result = subprocess.run(
            command, cwd=str(runtime_path.parent), env=self._environment(), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            timeout=RuntimeConfig.from_path(str(runtime_path), runtime_sha).startup_seconds + 10,
            check=False,
        )
        return result.returncode == 0 and _terminal(current, "failure.json") is not None

    def _record_missing_execution_exit(self, current):
        """核已就绪的原执行进程退出后才生成恢复材料，保留原故障收据。"""
        failure = _terminal(current, "failure.json")
        if failure is None or failure.get("components_closed") is not False:
            return
        status = _runtime_status(current, allow_pending=False)
        reference = (status or {}).get("components", {}).get("execution", {}).get("business_observation")
        if reference is None:
            return
        _require(reference.get("schema") == "guanheng.execution-observation-reference.v1")
        child = runtime_control_path(reference["path"]).parent
        _require(runtime_control_path(reference["ready_path"]) == child / "ready.json")
        if not any(os.path.lexists(child / name) for name in ("closed.json", "close-prepared.json", "failure.json", "owner-loss.json")):
            if not self._record_process_loss(current):
                raise ValueError("execution_predecessor_exit_unconfirmed")

    def _generation_record(self, control_id: str) -> dict | None:
        path = self.config.generation_root / control_id / "generation.json"
        try:
            _, value = _json_file(path, 16 * 1024)
        except FileNotFoundError:
            return None
        fields = {
            "schema",
            "control_id",
            "runtime_configuration",
            "runtime_configuration_sha256",
            "predecessor_control_id",
            "transition_file",
            "runtime_owner_file",
        }
        _require(
            fields <= set(value) <= fields | {"runtime_status_file"}
            and value["schema"] == "guanheng.wt-service-generation.v1"
            and value["control_id"] == control_id
        )
        runtime_control_path(value["runtime_configuration"])
        _sha(value["runtime_configuration_sha256"])
        _require(value["predecessor_control_id"] is None or _canonical_uuid(value["predecessor_control_id"]))
        _require(value["transition_file"] is None or _path(value["transition_file"], e_drive=True))
        runtime_control_path(value["runtime_owner_file"])
        if "runtime_status_file" in value:
            self._generation_status_file(control_id, value)
        return value

    def _generation_status_file(self, control_id, record):
        """按代登记的目录找父回执，旧代按原控制根解释。"""
        original = self.config.control_root / control_id / "status.json"
        if record is None or "runtime_status_file" not in record:
            return original
        path = runtime_control_path(record["runtime_status_file"])
        private = self.config.private_control_root
        _require(path == original or private is not None and path == private / control_id / "status.json")
        return path

    def _runtime_owner_active(self, current: dict) -> bool | None:
        """核本代ready、私有owner身份及当前OS创建时间；None表示身份材料未知。"""
        record = self._generation_record(current["wt_control_id"])
        if record is None:
            return None
        try:
            owner = read_status(record["runtime_owner_file"], 4096)
            ready = read_status(Path(current["wt_status_file"]).parent / "ready.json", 4096)
        except (FileNotFoundError, CollectionStatusPending):
            return None
        expected = {
            "schema": "guanheng.wt-service-runtime-owner.v1",
            "control_id": current["wt_control_id"],
            "instance_id": current["wt_instance_id"],
            "configuration_sha256": current["wt_configuration_sha256"],
        }
        _require(set(owner) == {*expected, "pid", "creation_filetime"} and all(owner[k] == v for k, v in expected.items()))
        _require(ready.get("schema") == "guanheng.wt-runtime-ready.v1"
                 and all(ready.get(k) == v for k, v in expected.items() if k != "schema")
                 and ready.get("pid") == owner["pid"])
        identity = _process_identity(owner["pid"])
        return identity is not None and identity == owner["creation_filetime"]

    def _record_runtime_owner(self, current: dict) -> None:
        """在Runtime发布本代ready后冻结其真实PID与创建时间，排除启动shim。"""
        ready = read_status(Path(current["wt_status_file"]).parent / "ready.json", 4096)
        _require(ready.get("schema") == "guanheng.wt-runtime-ready.v1"
                 and ready.get("control_id") == current["wt_control_id"]
                 and ready.get("instance_id") == current["wt_instance_id"]
                 and ready.get("configuration_sha256") == current["wt_configuration_sha256"])
        identity = _process_identity(ready.get("pid"))
        _require(identity is not None)
        owner_file = self.config.generation_root / current["wt_control_id"] / "runtime-owner.json"
        if not owner_file.exists():
            _write_exclusive(owner_file, {
                "schema": "guanheng.wt-service-runtime-owner.v1",
                "control_id": current["wt_control_id"],
                "instance_id": current["wt_instance_id"],
                "configuration_sha256": current["wt_configuration_sha256"],
                "pid": ready["pid"],
                "creation_filetime": identity,
            })

    def _configuration_for(self, current: dict) -> tuple[Path, str]:
        record = self._generation_record(current["wt_control_id"])
        if record is not None:
            path = Path(record["runtime_configuration"])
            digest = record["runtime_configuration_sha256"]
        else:
            path = self.config.bootstrap_configuration
            digest = self.config.bootstrap_configuration_sha256
        _require(digest == current["wt_configuration_sha256"])
        raw = _read(path, 64 * 1024)
        _require(hashlib.sha256(raw).hexdigest() == digest)
        return path, digest

    def _owned_current(self) -> dict | None:
        """将稳定指针约束到本服务根、同一逻辑实例及已登记配置代。"""
        current = _read_current(self.config.current_file)
        if current is None:
            return None
        status_file = Path(current["wt_status_file"])
        _require(status_file == self._generation_status_file(current["wt_control_id"],
                                                            self._generation_record(current["wt_control_id"])))
        bootstrap = RuntimeConfig.from_path(
            str(self.config.bootstrap_configuration), self.config.bootstrap_configuration_sha256
        )
        _require(current["wt_instance_id"] == bootstrap.instance_id)
        self._configuration_for(current)
        return current

    def _execution_start_not_reached(self, current: dict, status: dict, runtime: RuntimeConfig) -> bool:
        """原串行启动在执行之前返回且执行owner已关闭，才证明本代未调用执行start。

        PID/观察为空本身不证明未启动；固定顺序、原错误阶段、终态收据和完整关闭
        同时成立才沿原输入继续。execution自身失败或未知资源继续原恢复核查。
        """
        names = tuple(name for name, unused in runtime.components)
        failure = _terminal(current, "failure.json")
        components = status.get("components")
        if (failure is None or type(failure.get("components_closed")) is not bool
                or failure.get("status") != "faulted" or failure.get("error_code") != "runtime_failure"
                or type(failure.get("pid")) is not int or failure["pid"] <= 0
                or failure["pid"] != status.get("pid")
                or status.get("ready") is not False or status.get("state") not in ("closed", "faulted")
                or type(components) is not dict or set(components) != set(names)):
            return False
        earlier = {"component_start_" + name for name in names[:names.index("execution")]}
        execution = components["execution"]
        required = {"state", "ready", "pid", "business_observation", "pending", "forced", "error_code"}
        return (status.get("error_code") in earlier and type(execution) is dict
                and required <= set(execution) and execution["state"] == "closed"
                and execution["ready"] is False and execution["pid"] is None
                and execution["business_observation"] is None and execution["pending"] is False
                and execution["forced"] is False and execution["error_code"] is None
                and execution.get("execution_ready", False) is False
                and execution.get("source_wait_state", "waiting_source") == "waiting_source")

    def _retained_execution_transition(self, current: dict, descriptor: dict) -> str | None:
        """只核原配置/原交接字节，保持最后实际Native身份；不读取或重写账本。"""
        native_raw, native = _json_file(_path(descriptor["configuration"], e_drive=True), 256 * 1024)
        _require(hashlib.sha256(native_raw).hexdigest() == _sha(descriptor["configuration_sha256"]))
        record = self._generation_record(current["wt_control_id"])
        _require(record is not None)
        transition_file = record["transition_file"]
        recovery = native.get("recovery", {})
        if recovery.get("mode") == "resume_reconciled":
            transition = recovery.get("transition")
            _require(type(transition) is dict and set(transition) == {"file", "sha256"})
            path = _path(transition["file"], e_drive=True)
            bootstrap = (record["predecessor_control_id"] is None
                         and record["runtime_configuration"] == str(self.config.bootstrap_configuration)
                         and record["runtime_configuration_sha256"] == self.config.bootstrap_configuration_sha256)
            _require(transition_file == str(path) or transition_file is None and bootstrap)
            # 首次纳管的bootstrap也可自带合法恢复材料；该代尚未执行，直接登记同一原引用。
            transition_file = str(path)
            raw, value = _json_file(path, 256 * 1024)
            _require(hashlib.sha256(raw).hexdigest() == _sha(transition["sha256"])
                     and value.get("schema") == "guanheng.execution-recovery-transition.v1")
        else:
            # 首次尚未启动的原库存/record_clean输入原样保留，由Native首次start正常准入。
            _require(transition_file is None)
        return transition_file

    def _pre_native_execution_origin(self, current, status, *, aborted_control=None):
        """核子进程准入前退出和原状态字节，再定位最后有效的执行观察。"""
        execution = status.get("components", {}).get("execution", {})
        if (status.get("error_code") != "component_runtime_execution"
                or execution.get("error_code") != "execution_start"
                or execution.get("pid") is not None or execution.get("business_observation") is not None):
            return None
        _require(execution.get("pending") is False and execution.get("forced") is False
                 and execution.get("execution_ready") is False
                 and execution.get("source_wait_state") == "starting_execution"
                 and all(row.get("pending") is False and row.get("forced") is False
                         for name, row in status["components"].items() if name != "execution"))
        path, digest = self._configuration_for(current)
        runtime = dict(RuntimeConfig.from_path(str(path), digest).components)
        for name, row in status["components"].items():
            if name == "execution" or row.get("state") == "closed":
                continue
            # 已退出的只读owner可以留下业务错误；其失败与执行金融准入独立。
            _require(runtime[name].kind in _READ_ONLY_PROCESSES and row.get("state") == "faulted"
                     and row.get("ready") is False)
            # pending=false 已核原Job回收；快照PID可能已被Windows分给无关进程。
        role = runtime["execution"]
        descriptor = _pinned_json(_path(role.descriptor, e_drive=True), role.sha256, 256 * 1024)
        _require(descriptor.get("python_strategies") is True)
        root = runtime_control_path(descriptor["control_root"])
        from .execution_process import ManagedExecutionProcess
        from .runtime_diagnostics import ProcessEventLog
        events = _read(root / "process-events.jsonl", ProcessEventLog.DEFAULT_MAX_BYTES).splitlines()
        records = [json.loads(row) for row in events]
        records = [row for row in records if row.get("schema") == "guanheng.process-event.v1"
                   and row.get("component") == ManagedExecutionProcess._thread_name]
        _require(bool(records))
        terminal = records[-1]
        child_id = _canonical_uuid(terminal["control_id"])
        child = root / child_id
        _inspect(child, directory=True)
        _require(terminal.get("event") == "process_closed" and terminal.get("code") == "unexpected_exit"
                 and terminal.get("exit_code") in (1, 2) and terminal.get("host_pid") is None
                 and terminal.get("host_exit_code") is None)
        def started(row):
            return (row.get("schema") == "guanheng.process-event.v1"
                    and row.get("component") == ManagedExecutionProcess._thread_name
                    and row.get("control_id") == child_id and row.get("event") == "process_started")

        if not any(started(row) for row in records[:-1]):
            # 退出附近发生轮转时，启动记录仍归同一控制代。只遍历本系列原有的三份备份。
            found = False
            for index in range(1, ProcessEventLog.DEFAULT_BACKUPS + 1):
                try:
                    rows = _read(root / f"process-events.jsonl.{index}", ProcessEventLog.DEFAULT_MAX_BYTES).splitlines()
                except FileNotFoundError:
                    break
                if any(started(json.loads(row)) for row in rows):
                    found = True
                    break
            _require(found)
        native = _pinned_json(child / "execution.json", descriptor["configuration_sha256"], 256 * 1024)
        transition_file = self._retained_execution_transition(current, descriptor)
        _require(transition_file is not None)
        reference = native["recovery"]["transition"]
        transition = _pinned_json(_path(transition_file, e_drive=True), reference["sha256"], 1024 * 1024)
        state_root = _path(native["output_directory"])
        _require(state_root.drive.lower() in ("d:", "e:"))
        if terminal["exit_code"] == 2 and not (child / "failure.json").exists():
            names = {item.name for item in child.iterdir()}
            expected = {"execution.json", "python-binding.json"}
            if "python-start-failure.json" in names:
                _, diagnostic = _json_file(child / "python-start-failure.json", 4096)
                _require(diagnostic.get("schema") == "guanheng.cta-python-start-failure.v1"
                         and diagnostic.get("control_id") == child_id
                         and diagnostic.get("config_sha256") == descriptor["configuration_sha256"]
                         and diagnostic.get("stage") in ("python_binding", "execution_configuration",
                                                         "execution_transition"))
                expected.add("python-start-failure.json")
            _require(names == expected)
        else:
            # 原生初始化可以先写完整退出收据，再返回启动失败码。
            self._verify_native_start_abort(child, child_id, descriptor["configuration_sha256"])
        claim = state_root / f'.cta-reconciled-{reference["sha256"]}.json'
        _require(not claim.exists() and not claim.with_suffix(".json.pending").exists())
        _require(execution_state_files(state_root) == transition["state_files"])
        if aborted_control is not None:
            _require("initialization_abort" in transition
                     and _path(transition["predecessor_control_directory"]) == aborted_control)
        seen = set()
        control_id = current["wt_control_id"]
        while control_id is not None:
            _require(control_id not in seen)
            seen.add(control_id)
            record = self._generation_record(control_id)
            _require(record is not None)
            control_id = record["predecessor_control_id"]
            if control_id is None:
                break
            previous = self._generation_record(control_id)
            _require(previous is not None)
            origin = validate_current(dict(current, wt_control_id=control_id,
                wt_configuration_sha256=previous["runtime_configuration_sha256"],
                wt_status_file=str(self._generation_status_file(control_id, previous))))
            origin_status = _runtime_status(origin, allow_pending=False)
            observation = origin_status["components"]["execution"]["business_observation"]
            if aborted_control is not None:
                if (origin_status.get("error_code") == "component_runtime_execution"
                        and origin_status["components"]["execution"].get("error_code") == "execution_start"
                        and observation is None):
                    origin_path, origin_sha = self._configuration_for(origin)
                    role = dict(RuntimeConfig.from_path(str(origin_path), origin_sha).components)["execution"]
                    source = _pinned_json(_path(role.descriptor), role.sha256, 256 * 1024)
                    if source["configuration_sha256"] == transition["predecessor_configuration_sha256"]:
                        _require(runtime_control_path(source["control_root"]) == aborted_control.parent
                                 and self._runtime_owner_active(origin) is False)
                        return origin
                continue
            if observation is not None:
                _require(type(observation) is dict
                         and observation["config_sha256"] == transition["predecessor_configuration_sha256"]
                         and Path(observation["ready_path"]).parent == Path(transition["predecessor_control_directory"])
                         and self._runtime_owner_active(origin) is False)
                return origin
        raise ValueError("pre_native_execution_origin_missing")

    @staticmethod
    def _verify_native_start_abort(child, child_id, digest):
        """只准入尚未建立任何执行或金融恢复责任的子进程退出。"""
        _require(all(not (child / name).exists() for name in (
            "ready.json", "reconciled.json", "lifecycle-started.json", "lifecycle-finished.json", "closed.json")))
        _, failure = _json_file(child / "failure.json", 4096)
        _, closed = _json_file(child / "close-prepared.json", 4096)
        pid = failure.get("pid")
        stage = failure.get("stage")
        _require(type(pid) is int and pid > 0 and stage in ("trader", "reconcile_orders", "cta")
                 and failure.get("schema") == "guanheng.execution.failure.v1" and failure.get("closed") is False
                 and all(row.get("control_id") == child_id and row.get("config_sha256") == digest
                         and row.get("pid") == pid for row in (failure, closed))
                 and closed.get("schema") == "guanheng.execution.close-prepared.v1"
                 and closed.get("closed") is True and closed.get("ok") is False
                 and closed.get("recovery_ready") is False and closed.get("error_code") == stage)
        queue = failure.get("execution_queue")
        _require(type(queue) is dict and queue.get("accepting") is False and queue.get("inflight") is False
                 and all(type(queue.get(key)) is int and queue[key] == 0 for key in (
                     "fault", "accepted", "entered", "delivered", "rejected", "queued_commands", "payload_bytes")))
        require_process_exited(pid)

    def _admit_bootstrap(self, previous: dict | None, status: dict | None, *, pre_native=False) -> None:
        """持原服务租约核退出证据及显式后继的作用范围。"""
        _require(previous is not None and status is not None)
        closed = _terminal(previous, "closed.json", allow_pending=False)
        failure = _terminal(previous, "failure.json", allow_pending=False)
        _require((closed is None) != (failure is None) and status.get("ready") is False)
        ready = read_status(Path(previous["wt_status_file"]).parent / "ready.json", 4096)
        terminal = closed or failure
        _require(type(terminal.get("pid")) is int and terminal["pid"] == status["pid"] == ready.get("pid"))
        _require(self._runtime_owner_active(previous) is False)
        require_process_exited(terminal["pid"])

        old_path, old_sha = self._configuration_for(previous)
        before = RuntimeConfig.from_path(str(old_path), old_sha)
        after = RuntimeConfig.from_path(str(self.config.bootstrap_configuration), self.config.bootstrap_configuration_sha256)
        _require(before.instance_id == after.instance_id == previous["wt_instance_id"])
        old_components, new_components = dict(before.components), dict(after.components)
        _require(old_components.keys() == new_components.keys())
        components = status.get("components")
        _require(type(components) is dict and components.keys() == old_components.keys())
        if "execution" in old_components:
            # 正常关闭后，只读依赖可沿其既有角色采用后继描述符。
            # 金融组件仍由下游同账恢复校验；故障代的依赖保持原件用于退出核查。
            _require(all(new_components[name] == old
                         or name in {"execution", "trade_host"}
                         or closed is not None and old.kind in _READ_ONLY_PROCESSES
                            and new_components[name].kind == old.kind
                         for name, old in old_components.items()))
        else:
            # 只读运行代在原owner完整关闭后，按既有角色工厂采用固定描述符。
            _require(closed is not None and all(old.kind in _READ_ONLY_PROCESSES
                         and new_components[name].kind == old.kind for name, old in old_components.items()))
        if closed is not None:
            _require(closed.get("status") == "stopped" and closed.get("components_closed") is True
                     and closed.get("error_code") is None and status.get("state") == "closed"
                     and status.get("error_code") is None)
            for component in components.values():
                _require(type(component) is dict and component.get("state") == "closed"
                         and component.get("ready") is False and component.get("error_code") is None)
        else:
            _require(failure.get("status") == "faulted" and failure.get("components_closed") is False
                     and status.get("state") == "faulted")
            if not pre_native:
                _require(self._record_process_loss(previous))

    @staticmethod
    def _trade_deployment_identity(component, *, include_storage_model=False):
        """从已固定的交易部署读取原Journal和绑定身份，沿Source协议解码。"""
        from guanheng_qmt_shm.trade_deployment_identity import reference_deployment_identity

        from .trade_host_process import TradeHostProcessConfig

        config = TradeHostProcessConfig.from_path(component.descriptor, component.sha256)
        pair = Path(config.pair_directory)
        manifest = _pinned_json(pair / "manifest.json", config.pair_manifest_sha256, 2 * 1024 * 1024)
        deployment = _read(pair / "deployment.json", 16 * 1024 * 1024)
        _require(hashlib.sha256(deployment).hexdigest() == _sha(manifest["config_sha256"]))
        identity = reference_deployment_identity(deployment)
        model = json.loads(deployment)
        host = model["host"]
        endpoint = (host["listen_host"], host["listen_port"])
        if include_storage_model:
            # 迁盘只改变通信库位置。其他Host、Agent、凭据与权限字段仍逐项相同。
            host.pop("journal_path")
            _require(_path(host.pop("operation_policies_path")) == pair / "policy.json")
            policies = _read(pair / "policy.json", 1024 * 1024)
            policies_sha = hashlib.sha256(policies).hexdigest()
            _require(policies_sha == _sha(manifest["files"]["policy.json"]))
            return identity, endpoint, hashlib.sha256(_canonical([model, policies_sha])).hexdigest()
        return identity, endpoint

    @staticmethod
    def _require_trade_endpoint(trader, endpoint):
        base_url = trader["base_url"]
        address = urlsplit(base_url)
        port = 80 if address.port is None else address.port
        _require(base_url == base_url.strip() and address.scheme == "http"
                 and address.username is None and address.password is None
                 and address.path in ("", "/") and not address.query and not address.fragment
                 and (address.hostname, port) == endpoint)

    @staticmethod
    def _require_trade_source_origin(native, predecessor):
        """迁移证明必须来自原Runtime实际管理的Host部署及原Journal。"""
        reference = native["strategy_extension_origin"]["dependency_handoff"]
        handoff = _pinned_json(_path(reference["file"], e_drive=True), reference["sha256"], 1024 * 1024)
        proof = handoff["source_extension"]
        _require(type(proof) is dict
                 and _sha(proof["origin_deployment"]["sha256"]) == predecessor["deployment_sha256"])
        identity = proof["origin_identity"]
        origin = _pinned_json(_path(identity["file"], e_drive=True), identity["sha256"], 65536)
        _require(origin == predecessor)

    def _require_managed_trade_handoff(self, previous_runtime, candidate, native, new_native, *,
                                       private_storage=None, predecessor_control=None, predecessor_sha=None):
        from .execution_dependency_handoff import TRANSPORT

        old_trade = dict(previous_runtime.components).get("trade_host")
        new_trade = dict(candidate.components).get("trade_host")
        old_trader, new_trader = native["trader"], new_native["trader"]
        old_binding, new_binding = old_trader["binding_sha256"], new_trader["binding_sha256"]
        if old_trade is None:
            _require(private_storage is None and new_trade is None and old_binding == new_binding)
            return
        _require(new_trade is not None)
        if private_storage is None:
            before, old_endpoint = self._trade_deployment_identity(old_trade)
            after, new_endpoint = (before, old_endpoint) if old_trade == new_trade else self._trade_deployment_identity(new_trade)
        else:
            before, old_endpoint, old_model = self._trade_deployment_identity(old_trade, include_storage_model=True)
            after, new_endpoint, new_model = self._trade_deployment_identity(new_trade, include_storage_model=True)
            _require(old_model == new_model)
        _require(before["trade_binding_sha256"] == old_binding
                 and after["trade_binding_sha256"] == new_binding)
        if private_storage is None:
            _require(before["journal_path"] == after["journal_path"])
        else:
            from .private_storage import verify_private_copy
            from .shared_account_configuration import allocation_storage

            configured = new_native.get("private_storage_origin")
            _require(native.get("private_storage_origin") is None
                     and type(configured) is dict and set(configured) == {"file", "sha256"}
                     and _path(configured["file"]) == _path(private_storage["file"])
                     and _sha(configured["sha256"]) == _sha(private_storage["sha256"])
                     and old_binding == new_binding
                     and before["journal_path"] != after["journal_path"])
            deadline = self._clock() + candidate.startup_seconds
            _, old_root, old_output = allocation_storage(native, deadline=deadline)
            _, new_root, new_output = allocation_storage(new_native, deadline=deadline)
            verify_private_copy(private_storage, control=predecessor_control,
                configuration_sha256=predecessor_sha, output=old_output,
                journal=before["journal_path"], allocation=old_root / "account-allocation.sqlite3",
                target_output=new_output, target_journal=after["journal_path"],
                target_allocation=new_root / "account-allocation.sqlite3")
        self._require_trade_endpoint(old_trader, old_endpoint)
        self._require_trade_endpoint(new_trader, new_endpoint)
        if any(old_trader.get(key) != new_trader.get(key) for key in TRANSPORT):
            self._require_trade_source_origin(new_native, before)

    def _recover_execution(self, generation, previous_status, runtime_value, descriptor, candidate, previous_runtime,
                           *, private_storage=None, aborted_control=None):
        """以实际前代为账本来源，使用普通重启与显式采用共用的执行交接。"""
        execution_status = previous_status.get("components", {}).get("execution")
        _require(type(execution_status) is dict)
        observation = execution_status.get("business_observation")
        if aborted_control is None:
            _require(type(observation) is dict and observation.get("schema") == "guanheng.execution-observation-reference.v1")
            predecessor_control = runtime_control_path(observation["path"]).parent
            _require(runtime_control_path(observation["ready_path"]) == predecessor_control / "ready.json")
            ready = read_status(predecessor_control / "ready.json", 4096)
            previous_native_sha = _sha(observation["config_sha256"])
            _require(ready.get("schema") == "guanheng.execution.ready.v1"
                     and ready.get("control_id") == observation["control_id"]
                     and ready.get("config_sha256") == previous_native_sha
                     and ready.get("pid") == observation["pid"])
        else:
            role = dict(previous_runtime.components)["execution"]
            old_descriptor = _pinned_json(_path(role.descriptor), role.sha256, 256 * 1024)
            predecessor_control = runtime_control_path(str(aborted_control))
            _require(predecessor_control.parent == runtime_control_path(old_descriptor["control_root"])
                     and _canonical_uuid(predecessor_control.name) and observation is None)
            previous_native_sha = _sha(old_descriptor["configuration_sha256"])
        previous_native = predecessor_control / "execution.json"
        native = _pinned_json(previous_native, previous_native_sha, 256 * 1024)
        if candidate is not None:
            _require(descriptor.get("python_strategies") is True)
            new_native = _pinned_json(_path(descriptor["configuration"], e_drive=True),
                                      descriptor["configuration_sha256"], 256 * 1024)
            self._require_managed_trade_handoff(previous_runtime, candidate, native, new_native,
                private_storage=private_storage, predecessor_control=predecessor_control,
                predecessor_sha=previous_native_sha)
            native = new_native
        store = native.get("data", {}).get("store", {})
        daily = store.get("daily", {})
        if store.get("module") == "GuanhengRealtimeReader" and "publication" in daily:
            # Reader独占创建本代缓存目录；其它来源继续沿原发布原件。
            cache_root = generation / "daily-cache"
            _require(not os.path.lexists(cache_root))
            daily["publication"]["cache_root"] = str(cache_root)
            _connect_daily_publication(runtime_value, daily["publication"])
        transition_path = generation / "transition.json"
        with TemporaryDirectory(dir=generation) as scratch:
            native_template = Path(scratch) / "native.json"
            _write_exclusive(native_template, native)
            transition = prepare_transition(
                native_template, previous_native, predecessor_control, transition_path,
                successor_python=self.config.pythonw, initialization_abort=aborted_control is not None,
            )
        native["recovery"] = {"mode": "resume_reconciled", "transition": transition}
        native_path = generation / "native.json"
        native_sha = _write_exclusive(native_path, native)
        descriptor["configuration"] = str(native_path)
        descriptor["configuration_sha256"] = native_sha
        descriptor.pop("initial_inventory", None)
        successor_descriptor = generation / "execution.json"
        descriptor_sha = _write_exclusive(successor_descriptor, descriptor)
        if candidate is not None:
            from .execution_process import create_process

            # 与子进程采用同一描述符校验；此处只构造未启动的执行owner。
            create_process(str(successor_descriptor), descriptor_sha)
        execution = runtime_value["components"]["execution"]
        execution["descriptor"] = str(successor_descriptor)
        execution["sha256"] = descriptor_sha
        return str(transition_path)

    def _new_generation(self, previous: dict | None, previous_status: dict | None, *, adopt_bootstrap=False,
                        execution_origin=None, private_storage=None, aborted_control=None,
                        startup_seconds=None) -> tuple[dict, Path]:
        control_id = str(uuid4())
        generation = self.config.generation_root / control_id
        generation.mkdir()
        try:
            return self._materialize_generation(control_id, generation, previous, previous_status, adopt_bootstrap,
                                                execution_origin=execution_origin, private_storage=private_storage,
                                                aborted_control=aborted_control, startup_seconds=startup_seconds)
        except Exception:
            self._discard_generation(control_id)
            raise

    def _discard_generation(self, control_id):
        """仅删除本次未启动或未创建运行控制目录的私有材料。"""
        generation = self.config.generation_root / _canonical_uuid(control_id)
        _inspect(generation, directory=True)
        for artifact in generation.iterdir():
            artifact.unlink()
        generation.rmdir()

    def _materialize_generation(self, control_id, generation, previous, previous_status, adopt_bootstrap,
                                *, execution_origin=None, private_storage=None, aborted_control=None,
                                startup_seconds=None):
        owner_file = generation / "runtime-owner.json"
        runtime_path = self.config.bootstrap_configuration
        runtime_sha = self.config.bootstrap_configuration_sha256
        transition_file = None
        if previous is None:
            runtime = RuntimeConfig.from_path(str(runtime_path), runtime_sha)
        else:
            _require(previous_status is not None and (
                _terminal(previous, "closed.json") is not None or _terminal(previous, "failure.json") is not None
            ))
            previous_path, previous_sha = self._configuration_for(previous)
            previous_runtime = RuntimeConfig.from_path(str(previous_path), previous_sha)
            if not adopt_bootstrap:
                runtime_path, runtime_sha = previous_path, previous_sha
            runtime = RuntimeConfig.from_path(str(runtime_path), runtime_sha)
            if not adopt_bootstrap or "execution" in dict(runtime.components):
                runtime_value = _pinned_json(runtime_path, runtime_sha, 64 * 1024)
                execution = runtime_value["components"].get("execution")
                if execution is not None:
                    descriptor = _pinned_json(_path(execution["descriptor"], e_drive=True),
                                              execution["sha256"], 256 * 1024)
                    if self._execution_start_not_reached(previous, previous_status, previous_runtime):
                        _require(not adopt_bootstrap)
                        # 本代没有实际Native；原交接继续绑定最后实际执行代。
                        transition_file = self._retained_execution_transition(previous, descriptor)
                        if startup_seconds is not None:
                            runtime_value["startup_seconds"] = startup_seconds
                    else:
                        origin_status, origin_runtime = previous_status, previous_runtime
                        if execution_origin is not None:
                            origin_status = _runtime_status(execution_origin, allow_pending=False)
                            origin_path, origin_sha = self._configuration_for(execution_origin)
                            origin_runtime = RuntimeConfig.from_path(str(origin_path), origin_sha)
                        transition_file = self._recover_execution(
                            generation, origin_status, runtime_value, descriptor,
                            runtime if adopt_bootstrap else None, origin_runtime, private_storage=private_storage,
                            aborted_control=aborted_control,
                        )
                runtime_path = generation / "runtime.json"
                runtime_sha = _write_exclusive(runtime_path, runtime_value)
                runtime = RuntimeConfig.from_path(str(runtime_path), runtime_sha)
            _require(runtime.instance_id == previous["wt_instance_id"])
        current = validate_current(
            {
                "schema": "guanheng.wt-current.v1",
                "wt_status_file": str((self.config.private_control_root or self.config.control_root) / control_id / "status.json"),
                "wt_control_id": control_id,
                "wt_instance_id": runtime.instance_id,
                "wt_configuration_sha256": runtime_sha,
            }
        )
        _write_exclusive(
            generation / "generation.json",
            {
                "schema": "guanheng.wt-service-generation.v1",
                "control_id": control_id,
                "runtime_configuration": str(runtime_path),
                "runtime_configuration_sha256": runtime_sha,
                "predecessor_control_id": previous["wt_control_id"] if previous else None,
                "transition_file": transition_file,
                "runtime_owner_file": str(owner_file),
                "runtime_status_file": current["wt_status_file"],  # 本代状态与日志所在的已配置控制根。
            },
        )
        return current, runtime_path

    def status(self) -> tuple[int, dict]:
        # 共享冲突只表示发布文件暂忙；完整重读重新核验CURRENT与同代状态。
        for attempt in range(3):
            try:
                return self._status_once()
            except CollectionStatusPending:
                if attempt < 2:
                    self._sleep(.02)
        return 0, _safe_projection("status", None, {"error_code": "status_file_busy"},
                                   "status_read_pending", changed=False)

    def _status_once(self) -> tuple[int, dict]:
        current = self._owned_current()
        if current is None:
            return 0, _safe_projection("status", None, None, "absent", changed=False)
        status = _runtime_status(current, allow_pending=False)
        if _terminal(current, "closed.json", allow_pending=False) is not None:
            state = "stopped"
        elif _terminal(current, "failure.json", allow_pending=False) is not None:
            state = "faulted"
        elif status is None:
            state = "starting"
        else:
            active = self._runtime_owner_active(current)
            if active is False:
                state = "process_lost"
            elif active is None:
                state = "process_identity_unknown"
            elif status.get("ready"):
                state = "ready"
            else:
                state = status.get("state", "starting")
        return 0, _safe_projection("status", current, status, state, changed=False)

    def start(self, *, startup_seconds=None) -> tuple[int, dict]:
        """默认按原代恢复；已有bootstrap变化由显式采用动作负责。"""
        return self._start(startup_seconds=startup_seconds)

    def prepare_private_storage(self, private_root: Path) -> dict:
        """在正式服务租约内制作干净关闭后的迁移候选，不启动新代。"""
        return self._stopped_storage(private_root)

    def abandon_private_storage(self, reference) -> dict:
        """退役从未认领的候选，恢复旧凭据。原服务依旧由普通 start 启动。"""
        return self._stopped_storage(None, abandon=reference)

    def _stopped_storage(self, private_root, *, abandon=None):
        from .private_storage import (abandon_private_copy, journal_owner_lease, native_output_lease,
                                      prepare_private_copy, private_copy_reference)
        from .shared_account_configuration import allocation_storage

        with _ServiceLease(self.config.current_file):
            current = self._owned_current()
            _require(current is not None)
            status = _runtime_status(current, allow_pending=False)
            restore_current = False
            if abandon is not None and _terminal(current, "closed.json", allow_pending=False) is None:
                failure = _terminal(current, "failure.json", allow_pending=False)
                _require(status is not None and failure is not None
                         and failure.get("pid") == status["pid"] and status.get("state") == "faulted"
                         and all(row.get("pending") is False and row.get("ready") is False
                                 for row in status["components"].values())
                         and status["components"]["execution"].get("business_observation") is None)
                require_process_exited(status["pid"])
                path, digest = self._configuration_for(current)
                runtime = RuntimeConfig.from_path(str(path), digest)
                role = dict(runtime.components)["execution"]
                descriptor = _pinned_json(_path(role.descriptor), role.sha256, 256 * 1024)
                native = _pinned_json(_path(descriptor["configuration"]), descriptor["configuration_sha256"], 256 * 1024)
                _, copy = private_copy_reference(abandon)
                configured = native.get("private_storage_origin")
                _require(type(configured) is dict
                         and _path(configured["file"]) == _path(abandon["file"])
                         and configured["sha256"] == abandon["sha256"]
                         and native["trader"]["writes_enabled"] is False)
                transition = self._retained_execution_transition(current, descriptor)
                _require(transition is not None)
                seen = {current["wt_control_id"]}
                predecessor = self._generation_record(current["wt_control_id"])["predecessor_control_id"]
                while True:
                    _require(predecessor is not None and predecessor not in seen)
                    seen.add(predecessor)
                    record = self._generation_record(predecessor)
                    _require(record is not None)
                    origin = validate_current(dict(current, wt_control_id=predecessor,
                        wt_configuration_sha256=record["runtime_configuration_sha256"],
                        wt_status_file=str(self._generation_status_file(predecessor, record))))
                    if _terminal(origin, "closed.json", allow_pending=False) is not None:
                        break
                    _require(record["transition_file"] == transition
                             and _terminal(origin, "failure.json", allow_pending=False) is not None)
                    predecessor = record["predecessor_control_id"]
                current = origin
                status = _runtime_status(current, allow_pending=False)
                observed = status["components"]["execution"]["business_observation"]
                _require(_path(observed["ready_path"]).parent == _path(copy["predecessor_control"]))
                restore_current = True
            _require(_terminal(current, "closed.json", allow_pending=False) is not None)
            self._admit_bootstrap(current, status)
            path, digest = self._configuration_for(current)
            runtime = RuntimeConfig.from_path(str(path), digest)
            trade = dict(runtime.components).get("trade_host")
            _require(trade is not None)
            trade_identity, _ = self._trade_deployment_identity(trade)
            reference = status["components"]["execution"]["business_observation"]
            _require(reference["schema"] == "guanheng.execution-observation-reference.v1")
            control = _path(reference["path"]).parent
            _require(_path(reference["ready_path"]) == control / "ready.json")
            native = _pinned_json(control / "execution.json", reference["config_sha256"], 256 * 1024)
            _, allocation_root, output = allocation_storage(native, deadline=self._clock() + runtime.stop_seconds)
            allocation = allocation_root / "account-allocation.sqlite3"
            if abandon is not None:
                result = abandon_private_copy(abandon, control=control, configuration_sha256=reference["config_sha256"],
                                            output=output, journal=trade_identity["journal_path"], allocation=allocation)
                if restore_current:
                    _publish(self.config.current_file, current)
                return result
            journal = _path(trade_identity["journal_path"])
            with native_output_lease(output), journal_owner_lease(journal):
                return prepare_private_copy(control, output, journal, allocation, private_root, compact_allocation=True)

    def prepare_private_successor(self, reference, pair, native_template, native_sha256, output, *, no_order=False,
                                  successor_pythonw=None) -> dict:
        """物化跨盘配置并走正式前置检查；仍由显式采用命令启动。"""
        from .execution_recovery import compatible_business_configuration
        from .private_storage import private_copy_reference

        pair, native_template, output = (_path(str(path), e_drive=True) for path in (pair, native_template, output))
        with _ServiceLease(self.config.current_file):
            current = self._owned_current()
            _require(current is not None and _terminal(current, "closed.json", allow_pending=False) is not None)
            status = _runtime_status(current, allow_pending=False)
            self._admit_bootstrap(current, status)
            runtime_path, runtime_sha = self._configuration_for(current)
            before = RuntimeConfig.from_path(str(runtime_path), runtime_sha)
            runtime = _pinned_json(runtime_path, runtime_sha, 64 * 1024)
            observation = status["components"]["execution"]["business_observation"]
            _require(observation["schema"] == "guanheng.execution-observation-reference.v1")
            control = runtime_control_path(observation["path"]).parent
            _require(runtime_control_path(observation["ready_path"]) == control / "ready.json")
            predecessor_sha = _sha(observation["config_sha256"])
            previous_native = _pinned_json(control / "execution.json", predecessor_sha, 256 * 1024)
            _, storage = private_copy_reference(reference)
            native = _pinned_json(native_template, native_sha256, 256 * 1024)
            _require("private_storage_origin" not in native)
            if no_order:
                # 使用原权限交接协议，冻结正式前代并在原生交易入口禁用委托和撤单。
                _require(type(native.get("trader", {}).get("writes_enabled")) is bool)
                if native["trader"]["writes_enabled"]:
                    _require(previous_native["trader"]["writes_enabled"] is True)
                    native["trader"]["writes_enabled"] = False
                    native["execution_permission_origin"] = {
                        "schema": "guanheng.execution-permission-origin.v1",  # 既有权限切换材料。
                        "file": str(control / "execution.json"),  # 实际前代配置，不包含凭据正文。
                        "sha256": predecessor_sha,  # 前代原始配置摘要。
                    }
            _require(compatible_business_configuration(native, previous_native))
            native.update(
                output_directory=storage["target_output"],
                shared_account_storage={"allocation_root": str(_path(storage["databases"]["allocation"]["target"]).parent)},
                private_storage_origin=reference,
                recovery={"mode": "resume_clean"},  # 采用命令生成真实前代接续材料。
            )

            trade_role = runtime["components"]["trade_host"]
            trade = _pinned_json(_path(trade_role["descriptor"]), trade_role["sha256"], 65536)
            pair_raw, pair_manifest = _json_file(pair / "manifest.json", 2 * 1024 * 1024)
            trade.update(pair_directory=str(pair), pair_manifest_sha256=hashlib.sha256(pair_raw).hexdigest(),
                         pythonw=str(_path(pair_manifest["host_python"])),
                         pythonw_sha256=_sha(pair_manifest["host_python_sha256"]),
                         installed_agent=str(_path(pair_manifest["agent_package"])))
            execution_role = runtime["components"]["execution"]
            execution = _pinned_json(_path(execution_role["descriptor"]), execution_role["sha256"], 256 * 1024)
            _require(execution.get("python_strategies") is True)
            execution.pop("initial_inventory", None)
            if "installation_root" in native:
                # Native 模板与执行描述符使用同一安装根；换代继续由原清单检查覆盖。
                installation = _path(native["installation_root"], e_drive=True)
                _require(installation.name == "app")
                _inspect(installation.parent, directory=True)
                execution["installation"] = str(installation.parent)

            _inspect(output.parent, directory=True)
            output.mkdir()
            private_control = runtime_control_path(storage["target_output"]).parent / "execution-control"
            private_control.mkdir()
            execution["control_root"] = str(private_control)
            trade_control = private_control.with_name("trade-control")
            trade_control.mkdir()
            trade["control_root"] = str(trade_control)
            runtime_control = private_control.with_name("runtime-control")
            runtime_control.mkdir()
            native_path = output / "native-template.json"
            execution.update(configuration=str(native_path), configuration_sha256=_write_exclusive(native_path, native))
            for name, role, value in (("trade-host.json", trade_role, trade), ("execution.json", execution_role, execution)):
                path = output / name
                role.update(descriptor=str(path), sha256=_write_exclusive(path, value))
            runtime_file = output / "runtime.json"
            digest = _write_exclusive(runtime_file, runtime)
            after = RuntimeConfig.from_path(str(runtime_file), digest)
            self._require_managed_trade_handoff(before, after, previous_native, native, private_storage=reference,
                                                predecessor_control=control, predecessor_sha=predecessor_sha)
            service = {"schema": "guanheng.wt-service.v1",
                       **{key: str(value) if isinstance(value, Path) else value
                          for key, value in vars(self.config).items() if value is not None},
                       "private_control_root": str(runtime_control),
                       "bootstrap_configuration": str(runtime_file), "bootstrap_configuration_sha256": digest}
            if successor_pythonw is not None:
                interpreter = _path(str(successor_pythonw), e_drive=True)
                _require(interpreter.name.casefold() == 'pythonw.exe')
                service.update(pythonw=str(interpreter),
                               pythonw_sha256=hashlib.sha256(_read(interpreter, 64 * 1024 * 1024)).hexdigest())
            service_path = output / "service.json"
            service_sha = _write_exclusive(service_path, service)
            ServiceConfig.from_path(service_path)
            result = {"file": str(service_path), "sha256": service_sha}
            if no_order:
                result["writes_enabled"] = native["trader"]["writes_enabled"]
            return result

    def adopt_bootstrap(self) -> tuple[int, dict]:
        """正常旧owner退出后采用固定新bootstrap；保持稳定CURRENT与原实例。"""
        return self._start(adopt_bootstrap=True)

    def adopt_private_storage(self, reference) -> tuple[int, dict]:
        """采用已核停止水位及新配置，保持同一服务的 CURRENT 变更租约。"""
        return self._start(adopt_bootstrap=True, private_storage=reference)

    def recover_initialization_abort(self, control) -> tuple[int, dict]:
        """按原状态、未就绪及零执行证明接续失败代，权限由原恢复owner逐项核同。"""
        return self._start(adopt_bootstrap=True, aborted_control=control)

    def _start(self, *, adopt_bootstrap=False, private_storage=None, aborted_control=None,
               startup_seconds=None) -> tuple[int, dict]:
        action = "recover-initialization-abort" if aborted_control is not None else (
            "adopt-private-storage" if private_storage is not None else (
            "adopt-bootstrap" if adopt_bootstrap else "start")
        )
        with _ServiceLease(self.config.current_file):
            previous = self._owned_current()
            previous_status = _runtime_status(previous) if previous else None
            execution_origin = None
            if startup_seconds is not None:
                _require(not adopt_bootstrap and previous is not None and previous_status is not None)
                path, digest = self._configuration_for(previous)
                runtime = RuntimeConfig.from_path(str(path), digest)
                _require("execution" in dict(runtime.components)
                         and self._execution_start_not_reached(previous, previous_status, runtime))
                require_process_exited(previous_status["pid"])
            if adopt_bootstrap:
                if aborted_control is not None:
                    _require(previous_status is not None and _terminal(previous, "failure.json") is not None
                             and previous_status.get("error_code") == "component_runtime_execution")
                    execution = previous_status["components"]["execution"]
                    _require(execution.get("error_code") == "execution_start"
                             and execution.get("business_observation") is None and execution.get("pid") is None
                             and all(row.get("pending") is False and row.get("forced") is False
                                     and row.get("ready") is False for row in previous_status["components"].values()))
                    role_path, role_sha = self._configuration_for(previous)
                    role = dict(RuntimeConfig.from_path(str(role_path), role_sha).components)["execution"]
                    descriptor = _pinned_json(_path(role.descriptor), role.sha256, 256 * 1024)
                    requested = runtime_control_path(str(aborted_control))
                    _require(requested.parent == runtime_control_path(descriptor["control_root"]))
                    # 上次重试在 Python 校验阶段退出时，沿未认领的原交接材料找已核失败代。
                    if (_sha(descriptor["configuration_sha256"]) !=
                            hashlib.sha256(_read(requested / "execution.json", 256 * 1024)).hexdigest()):
                        execution_origin = self._pre_native_execution_origin(
                            previous, previous_status, aborted_control=requested)
                        _require(execution_origin is not None)
                elif previous_status is not None:
                    execution_origin = self._pre_native_execution_origin(previous, previous_status)
                if private_storage is not None:
                    _require(previous is not None and execution_origin is None
                             and _terminal(previous, "closed.json", allow_pending=False) is not None
                             and "execution" in dict(RuntimeConfig.from_path(
                                 str(self.config.bootstrap_configuration), self.config.bootstrap_configuration_sha256).components))
                self._admit_bootstrap(previous, previous_status,
                                      pre_native=execution_origin is not None or aborted_control is not None)
                if execution_origin is not None and aborted_control is None:
                    self._record_missing_execution_exit(execution_origin)
            elif previous is not None:
                closed = _terminal(previous, "closed.json")
                if closed is None:
                    failed = _terminal(previous, "failure.json")
                    if failed is not None:
                        if previous_status is not None:
                            execution_origin = self._pre_native_execution_origin(previous, previous_status)
                        self._record_missing_execution_exit(execution_origin or previous)
                    elif previous_status is None or self._runtime_owner_active(previous) is True:
                        state = "ready" if previous_status and previous_status.get("ready") else "starting"
                        return 0, _safe_projection(action, previous, previous_status, state, changed=False)
                    elif self._runtime_owner_active(previous) is False and self._record_process_loss(previous):
                        pass
                    else:
                        return 2, _safe_projection(action, previous, previous_status, "process_lost", changed=False)
            environment = self._environment()
            current, runtime_path = self._new_generation(previous, previous_status,
                adopt_bootstrap=adopt_bootstrap, execution_origin=execution_origin, private_storage=private_storage,
                aborted_control=aborted_control, startup_seconds=startup_seconds)
            control_directory = Path(current["wt_status_file"]).parent
            command = [
                str(self.config.pythonw),
                "-I",
                "-B",
                "-m",
                "guanheng_wt_runtime",
                "--config",
                str(runtime_path),
                "--config-sha256",
                current["wt_configuration_sha256"],
                "--control-directory",
                str(control_directory),
                "--control-id",
                current["wt_control_id"],
            ]
            if control_directory.parent != self.config.control_root:
                command.extend(("--instance-lease-root", str(self.config.control_root)))
            try:
                startup_seconds = RuntimeConfig.from_path(
                    str(runtime_path), current["wt_configuration_sha256"]
                ).startup_seconds
                process = self._launcher(command, str(runtime_path.parent), environment)
            except (OSError, ValueError):
                if not control_directory.exists():
                    self._discard_generation(current["wt_control_id"])
                raise
            deadline = self._clock() + startup_seconds + 10
            published = False
            while self._clock() < deadline:
                if not published and control_directory.exists():
                    _inspect(control_directory, directory=True)
                    _publish(self.config.current_file, current)
                    published = True
                if published:
                    status = _runtime_status(current)
                    if status is not None and status.get("ready"):
                        # status先于ready收据发布；沿同一原启动截止等完整owner身份，不抢先报错。
                        try:
                            self._record_runtime_owner(current)
                        except (FileNotFoundError, CollectionStatusPending):
                            pass
                        else:
                            return 0, _safe_projection(action, current, status, "ready", changed=True)
                    if _terminal(current, "failure.json") is not None:
                        return 2, _safe_projection(action, current, status, "faulted", changed=True)
                if process.poll() is not None and not published and not control_directory.exists():
                    self._discard_generation(current["wt_control_id"])
                    return 2, _safe_projection(action, previous, previous_status, "launch_failed", changed=False)
                self._sleep(0.05)
            status = _runtime_status(current) if published else None
            return 3, _safe_projection(action, current if published else previous, status, "start_timeout", changed=published)

    def stop(self) -> tuple[int, dict]:
        with _ServiceLease(self.config.current_file):
            current = self._owned_current()
            if current is None:
                return 0, _safe_projection("stop", None, None, "absent", changed=False)
            status = _runtime_status(current)
            if _terminal(current, "closed.json") is not None:
                return 0, _safe_projection("stop", current, status, "stopped", changed=False)
            if _terminal(current, "failure.json") is not None:
                return 2, _safe_projection("stop", current, status, "faulted", changed=False)
            stop_path = Path(current["wt_status_file"]).parent / "stop.json"
            request = {
                "schema": "guanheng.wt-runtime-stop.v1",
                "control_id": current["wt_control_id"],
                "instance_id": current["wt_instance_id"],
                "configuration_sha256": current["wt_configuration_sha256"],
            }
            changed = False
            try:
                existing = read_status(stop_path, 4096)
                _require(existing == request)
            except FileNotFoundError:
                _publish(stop_path, request)
                changed = True
            runtime_path, runtime_sha = self._configuration_for(current)
            deadline = self._clock() + RuntimeConfig.from_path(str(runtime_path), runtime_sha).stop_seconds + 10
            while self._clock() < deadline:
                status = _runtime_status(current)
                if _terminal(current, "closed.json") is not None:
                    return 0, _safe_projection("stop", current, status, "stopped", changed=changed)
                if _terminal(current, "failure.json") is not None:
                    return 2, _safe_projection("stop", current, status, "faulted", changed=changed)
                self._sleep(0.05)
            return 3, _safe_projection("stop", current, status, "stop_timeout", changed=changed)


def main(argv=None) -> int:
    """安装后 CLI；标准输出只含有限公开结果，私有配置和异常正文不输出。"""
    parser = argparse.ArgumentParser(description="WT日常启停与当前实例入口")
    parser.add_argument("action", choices=("start", "stop", "status", "adopt-bootstrap", "adopt-private-storage",
                                           "recover-initialization-abort"))
    parser.add_argument("--aborted-control")
    parser.add_argument("--startup-seconds", type=float)
    parser.add_argument("--storage-receipt")
    parser.add_argument("--storage-sha256")
    parser.add_argument("--service-config", required=True)
    args = parser.parse_args(argv)
    if (args.action == "recover-initialization-abort") != bool(args.aborted_control):
        parser.error("recover-initialization-abort requires --aborted-control")
    if args.startup_seconds is not None and args.action != "start":
        parser.error("--startup-seconds requires start")
    migration = args.action == "adopt-private-storage"
    if migration != bool(args.storage_receipt and args.storage_sha256) or (
            not migration and (args.storage_receipt or args.storage_sha256)):
        parser.error("adopt-private-storage requires both storage receipt and SHA256")
    try:
        controller = ServiceController(ServiceConfig.from_path(args.service_config))
        if migration:
            code, value = controller.adopt_private_storage(
                {"file": str(_path(args.storage_receipt)), "sha256": _sha(args.storage_sha256)})
        elif args.aborted_control:
            code, value = controller.recover_initialization_abort(args.aborted_control)
        elif args.startup_seconds is not None:
            code, value = controller.start(startup_seconds=args.startup_seconds)
        else:
            code, value = getattr(controller, args.action.replace("-", "_"))()
    except Exception:
        code, value = 2, {
            "schema": "guanheng.wt-service-result.v1",
            "action": args.action,
            "state": "control_error",
            "ready": False,
            "changed": False,
            "current": None,
            "runtime_pid": None,
            "error_code": "control_error",
            "components": {},
        }
    print(json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
