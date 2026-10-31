"""受管安装的隔离回测父owner；HTTP只传有界值，所有原生代码在独占Job内。

一次run从准入到关闭共用monotonic期限。结果是不可变投影；旧目录、失败目录
和合成回放分别保留原资格。默认预算容纳多日研究回放，部署可以逐项收紧。
"""
from __future__ import annotations

from dataclasses import dataclass
import ctypes as C
from functools import lru_cache
import hashlib
import json
import math
import msvcrt
from pathlib import Path
import re
import stat
from threading import Event, Lock, Thread
import time
import uuid

from .strategy_job import ProcessJob
from .thread_owner import ThreadOwner

SCHEMA = "nsh-run-v1"
INSTALL_SCHEMA = "nsh-install-v1"
# 报告业务schema由session唯一validator拥有；不保留旧DTO兼容分支。
REPORT_SCHEMA = "nsb-report-v2"
HISTORICAL_REPORT_SCHEMA = "nsb-historical-report-v1"
V2_REPORT_SCHEMA = 'nsb-v2-report-v1'
RETAINED_REPORT_SCHEMA = 'guanheng.retained-replay-report.v1'
_BASES = ("sessions", "commodities", "contracts", "holidays", "fees")
_LIB_SHA = "4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e"
_PROBE_SHA = "a7fdb6ecd763ebdd395d4b0d11d78a1f6d30bbb57f23a63630c2410c243b71b6"
_PENDING_LOCK = Lock()
_PENDING_OWNERS = {}  # 未确认回收的句柄/OS锁保留至确认；替换Host对象也不能跳过。
_JSON_MARKERS = re.compile(rb'["\\\[\]{}]')


class HostError(ValueError):
    """准入/容量/协议/期限失败；保留本轮目录供处理。"""


def _check(deadline):
    if time.monotonic() >= deadline:
        raise HostError("回测总期限耗尽")


def _reason(exc):
    try:
        return (type(exc).__name__ + ": " + str(exc))[:512]
    except BaseException:
        return "异常诊断不可表示"


@lru_cache(maxsize=26)
def _fixed_drive(anchor):
    api = C.WinDLL("kernel32", use_last_error=True)
    api.GetDriveTypeW.argtypes, api.GetDriveTypeW.restype = [C.c_wchar_p], C.c_uint
    return api.GetDriveTypeW(anchor) == 3


def _path(value):
    path = Path(value)
    if (not path.is_absolute() or ".." in path.parts or not re.fullmatch(r"[A-Za-z]:", path.drive)
            or any(":" in part or part.endswith((" ", ".")) for part in path.parts[1:])
            or not _fixed_drive(path.anchor)):
        raise HostError("需要本机固定盘上无逃逸、无ADS的绝对受管路径")
    for item in (*reversed(path.parents), path):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise HostError("受管路径包含symlink或Windows重解析点")
    return path


def _bytes(path, maximum, deadline):
    path = _path(path)
    if not path.is_file() or not 0 <= path.stat().st_size <= maximum:
        raise HostError("受管文件缺失或超过字节预算")
    output = bytearray()
    with path.open("rb") as stream:
        while True:
            _check(deadline)
            chunk = stream.read(min(65536, maximum + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > maximum:
                raise HostError("受管文件读取超过字节预算")
    return bytes(output)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _keys(value, required, optional=()):
    if type(value) is not dict or set(value) - set(required) - set(optional) or not set(required) <= set(value):
        raise HostError("JSON字段缺失、重复或结构未知")
    return value


def _json(data, maximum, deadline):
    if type(data) is not bytes or len(data) > maximum:
        raise HostError("JSON输入类型或字节预算不合格")
    # 在解析器递归/分配之前限制结构深度；引号中的括号不计入结构。
    depth, quoted, escaped_at = 0, False, -1
    for start in range(0, len(data), 65536):
        _check(deadline)
        # 原字节窗口检查截止；C扫描仅筛结构标记，跨窗引号/转义状态保持。
        for token in _JSON_MARKERS.finditer(data, start, min(start + 65536, len(data))):
            index = token.start()
            char = data[index]
            if index == escaped_at:
                continue
            if quoted:
                if char == 92:
                    escaped_at = index + 1
                elif char == 34:
                    quoted = False
            elif char == 34:
                quoted = True
            elif char in (91, 123):
                depth += 1
                if depth > 24:
                    raise HostError("JSON嵌套超过预算")
            elif char in (93, 125):
                depth -= 1
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise HostError("JSON含重复字段")
            result[key] = value
        return result
    def invalid(value):
        raise HostError("JSON含非有限值")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise HostError("JSON格式无效") from exc
    nodes = 0
    def visit(item):
        nonlocal nodes
        nodes += 1
        if nodes > 2097152:
            raise HostError("JSON节点超过预算")
        if type(item) is float and not math.isfinite(item):
            raise HostError("JSON数值溢出")
        if type(item) is dict:
            for child in item.values():
                visit(child)
        elif type(item) is list:
            for child in item:
                visit(child)
    visit(value); _check(deadline)
    return value


def _encode(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _write(path, data):
    with path.open("xb") as stream:
        stream.write(data)


def _tree(root, maximum, max_files, deadline, *, transient=False):
    files, total = [], 0
    def visit(directory):
        nonlocal total
        try:
            entries = sorted(directory.iterdir())
        except FileNotFoundError:
            if transient:
                return
            raise
        for entry in entries:
            _check(deadline)
            try:
                info = entry.lstat(); _path(entry)
                if stat.S_ISDIR(info.st_mode):
                    visit(entry)
                elif stat.S_ISREG(info.st_mode):
                    total += info.st_size
                    files.append(entry)
                    if total > maximum or len(files) > max_files:
                        raise HostError("保留目录或原生输出超过容量，需要人工处理")
                else:
                    raise HostError("受管目录含未知文件类型")
            except FileNotFoundError:
                # 运行中的native/runner会原子替换临时文件。只在实时容量巡检容许
                # 已消失条目；子wait后的完整清单与hash核对保持严格。
                if not transient:
                    raise
    visit(_path(root))
    return files, total


def _artifact(value, maximum, deadline):
    _keys(value, ("path", "sha256"))
    if type(value["sha256"]) is not str or not re.fullmatch("[0-9a-f]{64}", value["sha256"]):
        raise HostError("安装制品摘要格式无效")
    data = _bytes(value["path"], maximum, deadline)
    if _digest(data) != value["sha256"]:
        raise HostError("安装/基础资料身份漂移")
    return data


def verify_install(data, expected, deadline):
    """固定安装清单来自受管配置；清单覆盖整个site和native目录，无隐式扩展。"""
    if _digest(data) != expected:
        raise HostError("受信安装清单身份漂移")
    value = _json(data, 2 * 1024 * 1024, deadline)
    _keys(value, ("schema", "python", "python_config", "python_runtime", "site_root", "site_files", "native_root", "native_files", "library", "abi_probe", "basefiles", "report_schema"))
    if value["schema"] != INSTALL_SCHEMA or value["report_schema"] not in (REPORT_SCHEMA,V2_REPORT_SCHEMA,HISTORICAL_REPORT_SCHEMA,RETAINED_REPORT_SCHEMA):
        raise HostError("安装schema未知")
    _artifact(value["python"], 16 * 1024 * 1024, deadline)
    for root_key, files_key in (("site_root", "site_files"), ("native_root", "native_files")):
        root = _path(value[root_key]); items = value[files_key]
        if type(items) is not dict or not 1 <= len(items) <= 8192:
            raise HostError("安装文件集合容量无效")
        actual, _ = _tree(root, 512 * 1024 * 1024, 8192, deadline)
        if {p.relative_to(root).as_posix() for p in actual} != set(items):
            raise HostError("安装目录含遗漏、额外文件或缓存")
        for name, digest in items.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in name:
                raise HostError("安装清单相对路径逃逸")
            if root_key == "site_root" and (relative.suffix.lower() in (".pth", ".pyc") or relative.name in ("sitecustomize.py", "usercustomize.py")):
                raise HostError("隔离安装禁止隐式Python启动代码或字节码")
            _artifact({"path": str(root / relative), "sha256": digest}, 64 * 1024 * 1024, deadline)
    required = {"guanheng_app/" + name + ".py" for name in ("__init__", "strategy_host", "strategy_runner", "strategy_job", "strategy_porter", "strategy_session")}
    required |= {"guanheng_strategy_core/__init__.py", "guanheng_strategy_native/__init__.py"}
    if value['report_schema'] == RETAINED_REPORT_SCHEMA:
        required |= {'guanheng_app/'+name+'.py' for name in ('retained_replay', 'retained_report',
            'retained_evaluation', 'strategy_replay_facts', 'backtest_reports')}
        required |= {'guanheng_strategy_v1/__init__.py', 'guanheng_strategy_v1/latest.py', 'guanheng_strategy_v1/historical.py'}
    if value['report_schema']==V2_REPORT_SCHEMA:
        required|={'guanheng_app/strategy_evaluation.py'}
        required|={name+'/__init__.py' for name in ('guanheng_strategy_v2','guanheng_strategy_signals','guanheng_strategy_variants')}
    if not required <= set(value["site_files"]):
        raise HostError("安装缺少固定runner、会话或独立核")
    python = _path(value["python"]["path"])
    venv = python.parent.parent
    if python.name.lower() != "python.exe" or Path(value["site_root"]) != venv / "Lib/site-packages":
        raise HostError("固定解释器和非editable隔离安装目录失配")
    if _path(value["python_config"]["path"]) != venv / "pyvenv.cfg":
        raise HostError("Python环境配置路径失配")
    cfg = _artifact(value["python_config"], 16384, deadline).decode("utf-8")
    if not re.search(r"(?im)^include-system-site-packages\s*=\s*false\s*$", cfg):
        raise HostError("隔离Python不能继承system site packages")
    runtime = value["python_runtime"]
    if type(runtime) is not list or not 2 <= len(runtime) <= 8:
        raise HostError("需要venv redirector背后的实际Python解释器和运行库身份")
    home = re.search(r"(?im)^home\s*=\s*(.+?)\s*$", cfg)
    if home is None:
        raise HostError("Python环境缺少明确home")
    runtime_root = _path(home.group(1))
    names = set()
    for artifact in runtime:
        path = _path(artifact["path"])
        if path.parent != runtime_root or path.name in names or not (path.name == "python.exe" or re.fullmatch(r"python3[0-9]*\.dll", path.name)):
            raise HostError("实际Python运行库目录/名称/唯一性失配")
        names.add(path.name); _artifact(artifact, 67108864, deadline)
    if "python.exe" not in names or not any(re.fullmatch(r"python3[0-9]+\.dll", name) for name in names):
        raise HostError("实际Python解释器或版本运行库缺失")
    if value["library"]["sha256"] != _LIB_SHA or value["abi_probe"]["sha256"] != _PROBE_SHA:
        raise HostError("当前会话仅授固定原BtPorter及header探针")
    library = _path(value["library"]["path"])
    if library.parent != _path(value["native_root"]) or library.name != "WtBtPorter.dll":
        raise HostError("固定原生目录/库路径失配")
    _artifact(value["library"], 128 * 1024 * 1024, deadline)
    _artifact(value["abi_probe"], 1024 * 1024, deadline)
    _keys(value["basefiles"], _BASES)
    for name in _BASES:
        payload = _artifact(value["basefiles"][name], 1024 * 1024, deadline)
        if type(_json(payload, 1024 * 1024, deadline)) is not dict:
            raise HostError("基础资料必须是明确JSON对象")
    return value


@dataclass(frozen=True, slots=True)
class InstallationBinding:
    """只由受管配置构造；HTTP/行情请求不能提供或覆盖此绑定。"""
    manifest: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class HostBudgets:
    max_seconds: float = 1800.0
    input_bytes: int = 16 * 1024 * 1024
    native_bytes: int = 128 * 1024 * 1024
    result_bytes: int = 32 * 1024 * 1024
    stdout_bytes: int = 512 * 1024
    stderr_bytes: int = 256 * 1024
    retained_bytes: int = 1024 * 1024 * 1024
    retained_runs: int = 128
    max_files: int = 8192

    def __post_init__(self):
        if type(self.max_seconds) not in (int, float) or not math.isfinite(self.max_seconds) or not .1 <= self.max_seconds <= 7200:
            raise HostError("父宿主期限需要0.1至7200秒")
        for name, maximum in (("input_bytes", 16777216), ("native_bytes", 536870912),
                              ("result_bytes", 67108864), ("stdout_bytes", 8388608),
                              ("stderr_bytes", 8388608), ("retained_bytes", 17179869184),
                              ("retained_runs", 4096), ("max_files", 65536)):
            if type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= maximum:
                raise HostError("宿主字节/数量预算超出允许范围：" + name)


@dataclass(frozen=True, slots=True)
class HostResult:
    run_id: str
    status: str
    reason: str
    request_sha256: str | None
    installation_sha256: str
    directory: str | None
    report_json: str | None
    pid: int | None
    exit_code: int | None
    forced: bool
    pid_reaped: bool
    pipes_joined: bool
    elapsed_ms: int
    scope: str = "isolated-raw-BT; real-source/RT/broker/production-unqualified"


class _RootLock:
    def __init__(self, root):
        path = _path(root / ".strategy-host.lock")
        if path.exists() and (not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > 16):
            raise HostError("运行根OS锁文件类型、链接或容量异常")
        self.stream = path.open("a+b")
        try:
            if path.stat().st_size == 0:
                self.stream.write(b"0"); self.stream.flush()
            self.stream.seek(0)
            try:
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BlockingIOError("同一运行根已有排他OS锁") from exc
        except BaseException:
            self.stream.close(); raise

    def close(self):
        if not self.stream.closed:
            try:
                self.stream.seek(0); msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self.stream.close()


class StrategyHost:
    """同步运行owner，1活动/零队列；cancel为owner发出的显式停止事件。

    子wait尚未确认时保留进程句柄与OS锁。下一次准入只做非阻塞回收核查，仍
    活动则busy；绝不把未知回收写成成功或释放同根并发资格。
    """

    def __init__(self, binding: InstallationBinding, work_root: Path, *, budgets: HostBudgets = HostBudgets()):
        if type(binding) is not InstallationBinding or type(budgets) is not HostBudgets:
            raise HostError("需要明确受管绑定和预算")
        self.binding, self.work_root, self.budgets = binding, _path(work_root), budgets
        if not self.work_root.is_dir():
            raise HostError("受管运行根必须由部署预先建立")
        self._lock = Lock(); self._pending = None; self._active_id = ""

    def run(self, session_json: bytes, *, start: int, end: int, name: str = "configured", cancel: Event | None = None):
        began = time.monotonic(); deadline = began + self.budgets.max_seconds
        if not self._lock.acquire(blocking=False):
            return HostResult(self._active_id, "busy", "已有活动运行，零隐式排队", None, self.binding.sha256, None, None, None, None, False, False, False, 0)
        lease = job = directory = None; threads = []; req_sha = report = None
        forced = reaped = joined = False; code = None; reason = ""; status = "incomplete"; run_id = uuid.uuid4().hex
        self._active_id = run_id
        reserve = min(2.0, self.budgets.max_seconds * .2)
        work_deadline = deadline - reserve
        try:
            with _PENDING_LOCK:
                self._pending = _PENDING_OWNERS.get(self.work_root)
                if self._pending:
                    old_job, old_lease, old_threads = self._pending
                    try:
                        if old_job is not None:
                            old_job.close_job()
                            old_job.wait(0)
                        # 零等待续核仍须取得标准join证明，目标返回和ident均不足以释放依赖。
                        pending_now = time.monotonic()
                        old_joined = [owner.join_until(pending_now, clock=time.monotonic) for owner in old_threads]
                        if not all(old_joined):
                            raise HostError("此前管道线程尚未排空")
                        if old_job is not None:
                            old_job.close_reaped()
                        if old_lease is not None:
                            old_lease.close()
                    except BaseException:
                        status, reason = "busy", "此前运行资源关闭尚未确认"
                        return HostResult(run_id, status, reason, None, self.binding.sha256, None, None,
                                          old_job.pid if old_job else None, None, True, False, False,
                                          int((time.monotonic()-began)*1000))
                    del _PENDING_OWNERS[self.work_root]; self._pending = None
            try:
                lease = _RootLock(self.work_root)
            except BlockingIOError:
                status = "busy"; raise HostError("同一运行根已有其他进程持锁")
            self._capacity(work_deadline)
            installation_bytes = _bytes(self.binding.manifest, 2097152, work_deadline)
            install = verify_install(installation_bytes, self.binding.sha256, work_deadline)
            payload = _json(session_json, self.budgets.input_bytes, work_deadline)
            if type(payload) is not dict or payload.get('schema') != 'guanheng.retained-replay-input.v1':
                raise HostError('当前只接受唯一正式1.1.2策略回放输入；旧报告可从归档读取')
            self._payload_shape(payload)
            from .backtest_reports import report_schema_for_input, normalize_session
            payload = normalize_session(payload)
            report_schema=report_schema_for_input(payload)
            if install['report_schema']!=report_schema:raise HostError('安装与业务会话种类失配')
            if type(start) is not int or type(end) is not int or type(name) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,30}", name):
                raise HostError("回放范围或名称格式无效")
            if cancel is not None and cancel.is_set():
                raise HostError("owner已主动取消")
            directory = self.work_root / run_id; directory.mkdir(exist_ok=False); _path(directory)
            base = directory / "basefiles"; base.mkdir()
            for key in _BASES:
                _write(base / (key + ".json"), _artifact(install["basefiles"][key], 1048576, work_deadline))
            _write(directory / "installation.json", installation_bytes)
            request = {"schema": SCHEMA, "run_id": run_id, "installation_sha256": self.binding.sha256,
                       "deadline_monotonic": deadline, "report_schema": report_schema, "session": payload, "session_sha256": _digest(_encode(payload)),
                       "backtest": {"start": start, "end": end, "name": name},
                       "budgets": {"input_bytes": self.budgets.input_bytes, "native_bytes": self.budgets.native_bytes,
                                   "result_bytes": self.budgets.result_bytes, "max_files": self.budgets.max_files}}
            request_bytes = _encode(request)
            if len(request_bytes) > self.budgets.input_bytes:
                raise HostError("冻结请求封包超过输入预算")
            req_sha = _digest(request_bytes); _write(directory / "request.json", request_bytes)
            _check(work_deadline)
            job = ProcessJob()
            argv = (install["python"]["path"], "-I", "-B", "-m", "guanheng_app.strategy_runner",
                    "--request", str(directory / "request.json"), "--request-sha", req_sha,
                    "--binding-sha", self.binding.sha256, "--deadline", repr(deadline))
            job.start(argv, str(directory), deadline=work_deadline)
            _check(work_deadline)
            overflow = Event(); drain_errors = []
            def drain(label, pipe, maximum):
                size = 0
                try:
                    with (directory / (label + ".log")).open("xb") as stream:
                        while True:
                            data = pipe.read(4096)
                            if not data:
                                return
                            take = min(len(data), max(0, maximum - size))
                            if take:
                                stream.write(data[:take])
                            size += len(data)
                            if size > maximum:
                                overflow.set()
                except BaseException as exc:
                    drain_errors.append(_reason(exc)); overflow.set()
            for label, pipe, maximum in (("stdout", job.stdout, self.budgets.stdout_bytes), ("stderr", job.stderr, self.budgets.stderr_bytes)):
                owner = ThreadOwner(target=drain, args=(label, pipe, maximum),
                                    name="strategy-host-" + label, daemon=True, thread_factory=Thread)
                threads.append(owner)
                owner.start()
            # root与后代共享原工作截止；整树归零前持续执行同一组运行守卫。
            while True:
                code = job.poll()
                if code is not None and code != 0:
                    raise HostError("策略runner以异常退出码结束")
                if overflow.is_set():
                    raise HostError("子进程管道超过预算或排空失败")
                if cancel is not None and cancel.is_set():
                    raise HostError("owner主动取消，本轮中断")
                _check(work_deadline)
                _tree(directory, self.budgets.input_bytes + self.budgets.native_bytes + self.budgets.result_bytes + self.budgets.stdout_bytes + self.budgets.stderr_bytes + 16 * 1048576, self.budgets.max_files, work_deadline, transient=True)
                native = directory / "outputs"
                if native.exists():
                    _tree(native, self.budgets.native_bytes, self.budgets.max_files, work_deadline, transient=True)
                if code == 0 and job.active_processes() == 0:
                    break
                time.sleep(min(.02, max(0, work_deadline - time.monotonic())))
            job.close_job(); reaped = False
            code = job.wait(max(0, work_deadline - time.monotonic())); reaped = True
            join_results = [owner.join_until(work_deadline, clock=time.monotonic) for owner in threads]
            joined = all(join_results)
            if forced or not joined or overflow.is_set() or drain_errors or code != 0:
                raise HostError("子退出/管道结束条件未满足")
            _tree(directory, self.budgets.input_bytes + self.budgets.native_bytes + self.budgets.result_bytes
                  + self.budgets.stdout_bytes + self.budgets.stderr_bytes + 16 * 1048576,
                  self.budgets.max_files, work_deadline)
            if (_digest(_bytes(directory / "request.json", self.budgets.input_bytes, work_deadline)) != req_sha
                    or _digest(_bytes(directory / "installation.json", 2097152, work_deadline)) != self.binding.sha256):
                raise HostError("本轮冻结请求或安装副本身份漂移")
            for base in _BASES:
                for folder in ("basefiles", "session-basefiles"):
                    if _digest(_bytes(directory / folder / (base + ".json"), 1048576, work_deadline)) != install["basefiles"][base]["sha256"]:
                        raise HostError("本轮基础资料冻结副本身份漂移")
            result_data = _bytes(directory / "result.json", self.budgets.result_bytes, work_deadline)
            value = _json(result_data, self.budgets.result_bytes, work_deadline)
            report = self._result(value, directory, run_id, req_sha, install, request, work_deadline)
            verify_install(installation_bytes, self.binding.sha256, work_deadline)
            _check(work_deadline)
            status, reason = "completed", "完整回放、身份、原生输出与进程回收已核实"
        except BaseException as exc:
            reason = _reason(exc); report = None
        finally:
            # 关闭异常同样保留原Job/lease；任何路径最终都释放本实例准入锁。
            cleanup_failed = False
            try:
                if job is not None:
                    if job.handle is not None:
                        forced = True
                    try:
                        job.close_job()
                    except BaseException as exc:
                        cleanup_failed = True; reason += "; " + _reason(exc)
                    try:
                        code = job.wait(max(0, deadline - time.monotonic())); reaped = True
                    except BaseException as exc:
                        reaped = False; cleanup_failed = True; reason += "; " + _reason(exc)
                    joined = True
                    for owner in threads:
                        try:
                            if not owner.join_until(deadline, clock=time.monotonic):
                                joined = False
                        except BaseException as exc:
                            joined = False
                            cleanup_failed = True; reason += "; " + _reason(exc)
                    if reaped and joined:
                        try:
                            job.close_reaped()
                        except BaseException as exc:
                            cleanup_failed = True; reason += "; " + _reason(exc)
                    else:
                        cleanup_failed = True
                if not cleanup_failed and lease is not None:
                    try:
                        lease.close()
                        lease = None
                    except BaseException as exc:
                        cleanup_failed = True; reason += "; " + _reason(exc)
                if cleanup_failed:
                    status, report = "incomplete", None
                    self._pending = (job, lease, threads)
                    with _PENDING_LOCK:
                        _PENDING_OWNERS[self.work_root] = self._pending
                    lease = None
            finally:
                self._active_id = ""
                self._lock.release()
        return HostResult(run_id, status, reason[:1024], req_sha, self.binding.sha256,
                          str(directory) if directory else None, report, job.pid if job else None,
                          code, forced, reaped, joined, int((time.monotonic() - began) * 1000))

    def _capacity(self, deadline):
        files, total = _tree(self.work_root, self.budgets.retained_bytes, self.budgets.max_files * self.budgets.retained_runs, deadline)
        runs = sum(1 for p in self.work_root.iterdir() if p.is_dir())
        reserve = self.budgets.input_bytes + self.budgets.native_bytes + self.budgets.result_bytes + self.budgets.stdout_bytes + self.budgets.stderr_bytes + 16 * 1048576
        if runs >= self.budgets.retained_runs or total + reserve > self.budgets.retained_bytes:
            raise HostError("累计保留容量已满，处理后再运行；宿主保留全部原件")

    @staticmethod
    def _payload_shape(value):
        if type(value) is dict and value.get('schema') == 'guanheng.retained-replay-input.v1':
            from .retained_replay import RetainedReplayInput
            RetainedReplayInput.from_dict(value)
            return
        v2=type(value) is dict and value.get('schema')=='nsb-v2-input-v1'
        _keys(value, (("schema","strategy") if v2 else ('config',)) + ("history", "native_mapping", "series", "policy", "fee_reserve_cny", "fee_source", "market_manifest_source"),
              ("price_adjustment", "price_unit", "volume_unit", "amount_unit", "daily_close", "historical_model"))
        if type(value["series"]) is not list or not 1 <= len(value["series"]) <= 16:
            raise HostError("原生日线集合容量无效")
        for series in value["series"]:
            _keys(series, ("symbol", "bars"))
            if type(series["bars"]) is not list or len(series["bars"]) > 4096:
                raise HostError("原生日线条数超过预算")

    def _result(self, value, directory, run_id, request_sha, install, request, deadline):
        _keys(value, ("schema", "run_id", "request_sha256", "installation_sha256", "report", "native_outputs", "report_schema"))
        if (value["schema"], value["run_id"], value["request_sha256"], value["installation_sha256"], value["report_schema"]) != (SCHEMA, run_id, request_sha, self.binding.sha256, request['report_schema']):
            raise HostError("结果run/请求/安装身份失配")
        report = value["report"]
        # 唯一schema与有界展开校验归业务session；父端仅核运行绑定和实际输出。
        from .backtest_reports import validate_report_dict
        validate_report_dict(report, check=lambda: _check(deadline))
        if report["schema"] != request['report_schema'] or request['report_schema']!=install['report_schema']:
            raise HostError("会话报告schema未获本安装接线资格")
        counts = dict(report["callback_counts"])
        if counts.get("init") != 1 or counts.get("calculate") != len(report["records"]) or counts.get("calc_done") != 0:
            raise HostError("会话report回调集合不完整")
        retained = report['schema'] == RETAINED_REPORT_SCHEMA
        if retained:
            from guanheng_strategy_core.contracts import canonical_bytes
            from .retained_replay import ORIGINAL_BT_SHA256, ABI_PROBE_SHA256
            need_input = _digest(canonical_bytes(request['session']))
            if (report['input_sha256'] != need_input or report['policy'] != request['session']['policy']
                    or report['historical_model'] != request['session']['model']
                    or report['configuration_sha256'] != _digest(canonical_bytes(request['session']['request']['configuration']))):
                raise HostError('唯一策略报告未绑定本次配置、模型和策略资本')
            expected_session = _digest(_encode((need_input, str(directory), request['backtest']['start'],
                request['backtest']['end'], request['backtest']['name'], report['native_files'], ORIGINAL_BT_SHA256, ABI_PROBE_SHA256)))
            if report['session_id'] != expected_session:
                raise HostError('唯一策略报告原生会话身份失配')
            expected_days = sorted({int(row['trade_date'].replace('-', ''))
                for row in request['session']['request']['history']['observations']})[1:]
        else:
            expected_days = sorted({row["date"] for series in request["session"]["series"] for row in series["bars"]})[1:]
        expected_days = [day for day in expected_days if day >= request["backtest"]["start"] // 10000]
        if [record["trading_date"] for record in report["records"]] != expected_days:
            raise HostError("会话闭合计算日期集合缺失或越界")
        if dict(report["native_files"]) != {name: install["basefiles"][name]["sha256"] for name in _BASES}:
            raise HostError("会话原生基础资料身份失配")
        files, _ = _tree(directory / "outputs", self.budgets.native_bytes, self.budgets.max_files, deadline)
        expected = {p.relative_to(directory).as_posix(): _digest(_bytes(p, self.budgets.native_bytes, deadline)) for p in files}
        if value["native_outputs"] != expected or not any(name.endswith("trades.csv") for name in expected):
            raise HostError("原生输出缺失、身份或完整集合失配")
        if retained and any(expected.get('outputs/'+request['backtest']['name']+'/'+name) != sha
                for name, sha in report['native_outputs']):
            raise HostError('唯一策略报告原生输出绑定失配')
        return _encode(report).decode("ascii")
