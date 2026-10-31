"""Build, test and package SDK-independent native components; Python 3.10+."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import uuid
import zipfile

from native_support.artifact import archive, sha256, verify_archive, write_manifest
# 保留既有公开入口，窗口选项由同一工具模块拥有。
from native_support.process_startup import background_process_options

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config/native-dependencies.json"


def display(message: str, *, file=None):
    """按目标流编码展示日志；完整 UTF-8 文件和子命令状态由 run 独立保存。"""
    stream = sys.stdout if file is None else file
    if stream is None:
        return
    encoding = getattr(stream, "encoding", None)
    if encoding:
        # Windows 控制台可能使用 GBK；不可编码字符以可追溯转义显示，避免
        # 显示失败遮住命令的真实退出状态。文件/管道的写入错误继续交给调用者。
        message = message.encode(encoding, errors="backslashreplace").decode(encoding)
    print(message, file=stream, flush=True)


def run(argv, *, env=None, cwd=None, log=None, timeout=1200, private_console=False,
        max_output_bytes=8 * 1024 * 1024):
    """在单一总D内收集第一层合流输出；额度按解码前raw bytes计算。

    成功仍返回完整文本与秒数。工作D预留min(5s,timeout/5)给同一次收尾；
    溢出/未知关闭均失败，不把有限前缀当作完整成功输出。
    """
    started = time.monotonic()
    try:
        valid_timeout = type(timeout) in (int, float) and math.isfinite(timeout) and timeout > 0
    except OverflowError:
        valid_timeout = False
    if (not valid_timeout or type(max_output_bytes) is not int
            or not 1 <= max_output_bytes <= 64 * 1024 * 1024):
        raise ValueError("finite positive timeout and output budget (1..64MiB) required")
    total_deadline = started + timeout
    if not math.isfinite(total_deadline):
        raise ValueError("finite native command deadline required")
    work_deadline = total_deadline - min(5.0, timeout / 5.0)
    command = [str(arg) for arg in argv]
    lock, changed, entered = threading.Lock(), threading.Event(), threading.Event()
    state = {"primary": None, "secondary": [], "raw": bytearray(), "eof": False,
             "done": False, "overflow": False}
    job = process = reader = None
    attempted = returned = joined = reaped = tree_zero = False
    resources_closed = True

    def remember(error):
        with lock:
            if state["primary"] is None:
                state["primary"] = error
            elif error is not state["primary"] and len(state["secondary"]) < 8:
                try:
                    state["secondary"].append(error)
                except MemoryError:
                    pass  # 首因槽不依赖次异常集合再次分配成功。
        changed.set()

    def primary():
        with lock:
            return state["primary"]

    def remaining():
        return max(0.0, total_deadline - time.monotonic())

    def check_work():
        if time.monotonic() >= work_deadline:
            raise subprocess.TimeoutExpired(command, timeout)

    def drain():
        entered.set()
        try:
            while True:
                block = process.stdout.read(8192)
                if not block:
                    with lock:
                        state["eof"] = True
                    return
                overflow = False
                with lock:
                    available = max_output_bytes - len(state["raw"])
                    state["raw"].extend(block[:available])
                    if len(block) > available and not state["overflow"]:
                        state["overflow"] = overflow = True
                if overflow:
                    remember(RuntimeError(f"command output limit exceeded ({max_output_bytes} raw bytes); log={log}"))
                # 超额后仍只读固定scratch并丢弃；owner终止Job，EOF后真实join。
        except BaseException as error:
            remember(error)
        finally:
            with lock:
                state["done"] = True
            changed.set()

    try:
        display("+ " + subprocess.list2cmdline(command))
        check_work()
        if os.name == "nt":
            from native_support.process_job import ProcessJob
            job = ProcessJob()
        check_work()
        reader = threading.Thread(target=drain, name="native-command-output", daemon=True)
        process = subprocess.Popen(command, cwd=cwd or ROOT, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0, **background_process_options(suspended=bool(job), private_console=private_console))
        check_work()
        if job:
            job.attach_and_resume(process, deadline=work_deadline)
        check_work()
        attempted = True
        reader.start()
        returned = True
        while primary() is None:
            code = process.poll()
            if code is not None and code != 0:
                remember(RuntimeError(f"command failed ({code}); log={log}"))
                break
            with lock:
                done, eof = state["done"], state["eof"]
            # poll/调度可能晚回；完成事实也须在原workD内接受。
            check_work()
            if code is not None and done and eof:
                break
            changed.wait(max(0.0, min(.05, work_deadline - time.monotonic())))
            changed.clear()
    except BaseException as error:
        if isinstance(error, TimeoutError) and time.monotonic() >= work_deadline:
            expired = subprocess.TimeoutExpired(command, timeout)
            expired.__cause__ = error
            remember(expired)
        else:
            remember(error)
    finally:
        # 每个owner逐项收口；任何secondary都不能跳过其余资源或替换首因。
        terminated = False
        if job:
            try:
                job.terminate()
                terminated = job.assigned
            except BaseException as error:
                remember(error)
        if process is not None:
            try:
                if process.poll() is None and not terminated:
                    process.kill()
            except BaseException as error:
                remember(error)
            try:
                process.wait(timeout=remaining())
                reaped = True
            except BaseException as error:
                remember(error)
        if job:
            try:
                while job.active_processes():
                    left = remaining()
                    if left <= 0:
                        raise TimeoutError("native command Job tree remains unconfirmed at original deadline")
                    time.sleep(min(.01, left))
                tree_zero = True
            except BaseException as error:
                remember(error)
        else:
            tree_zero = process is None or reaped  # 非Windows不宣称整棵后代树已核。
        if not attempted:
            joined = True
        elif reader is not None:
            try:
                # start可能在OS线程已建但未正常返回时抛错，entry缺席保持未知。
                if not returned and not entered.wait(remaining()):
                    raise RuntimeError("native output thread start remains unconfirmed")
                reader.join(remaining())
                joined = not reader.is_alive()
                if not joined:
                    raise RuntimeError("native output thread remains borrowed at original deadline")
            except BaseException as error:
                remember(error)
        if process is not None and joined:
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except BaseException as error:
                        resources_closed = False
                        remember(error)
        if process is not None and reaped and os.name == "nt":
            try:
                process._handle.Close()  # Popen拥有；Job仅借用该handle，整树计数仍用Job handle。
            except BaseException as error:
                resources_closed = False
                remember(error)
        if job and tree_zero:
            try:
                job.close()
            except BaseException as error:
                resources_closed = False
                remember(error)

    raw, output = b"", ""
    with lock:
        eof, overflow = state["eof"], state["overflow"]
    try:
        with lock:
            raw = bytes(state["raw"]) if joined else b""
        output = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    except BaseException as secondary:
        remember(secondary)
    if process is not None and not (reaped and tree_zero and joined):
        resources_closed = False
    if process is not None and not (reaped and tree_zero and joined and (eof or not attempted)):
        remember(RuntimeError("native command cleanup remains unconfirmed"))
    if time.monotonic() >= total_deadline:
        remember(subprocess.TimeoutExpired(command, timeout))
    error = primary()
    marker = "\nTIMEOUT\n" if isinstance(error, subprocess.TimeoutExpired) else (
        "\nOUTPUT_LIMIT_EXCEEDED\n" if overflow else "")
    if log and remaining() > 0:
        try:
            Path(log).parent.mkdir(parents=True, exist_ok=True)
            if remaining() <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            Path(log).write_text(output + marker, encoding="utf-8")
        except BaseException as secondary:
            remember(secondary)
    if remaining() > 0:
        try:
            display(output[-12000:] if primary() is not None else output[-2500:])
        except BaseException as secondary:
            remember(secondary)
    if time.monotonic() >= total_deadline:
        remember(subprocess.TimeoutExpired(command, timeout))
    error = primary()
    if error is not None:
        # 日志/展示晚回也可能首次形成TimeoutExpired；只补最终首因的已收有限raw。
        if isinstance(error, subprocess.TimeoutExpired):
            error.output = raw
        try:
            nested_owner = getattr(error, "_native_cleanup_owner", None)
            if nested_owner is not None:
                resources_closed = False  # 构造尚未把job交回run，原owner仍有未确认资源。
            error._native_cleanup_status = {
                "root_created": process is not None, "root_reaped": reaped,
                "job_tree_zero_observed": bool(job) and tree_zero,
                "member_before_resume": bool(job) and job.member_before_resume,
                "resumed": bool(job) and job.resumed,
                "reader_attempted": attempted, "reader_join_confirmed": joined,
                "pipe_eof": eof, "resource_closure_confirmed": resources_closed,
                "total_deadline": total_deadline, "work_deadline": work_deadline}
            prior = tuple(getattr(error, "_native_cleanup_errors", ()))
            error._native_cleanup_errors = (prior + tuple(state["secondary"]))[:8]
            if not (reaped or process is None) or not tree_zero or not joined or not resources_closed:
                # 错误调用者必须退出其受管driver；未确认owner留到outer Job收口。
                if nested_owner is None:
                    error._native_cleanup_owner = (process, job, reader)
                elif any(value is not None for value in (process, job, reader)):
                    error._native_cleanup_owner = (nested_owner, (process, job, reader))
                # 本地均为None时原构造owner原位保持，禁止用空tuple归属覆盖它。
        except BaseException:
            pass
        raise error.with_traceback(error.__traceback__)
    return output, round(time.monotonic() - started, 3)


def environment(work: Path):
    if os.name != "nt" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        raise RuntimeError("this native profile requires Windows x64")
    env = os.environ.copy()
    temporary = work / "temp"
    temporary.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(temporary), TMP=str(temporary), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", VSLANG="1033")
    vs = None
    if os.name == "nt":
        where = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
        vs = subprocess.check_output([str(where), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True, timeout=30, **background_process_options()).strip()
        if not vs:
            raise RuntimeError("MSVC x64 tools are required; install separately")
        script = Path(vs) / "VC/Auxiliary/Build/vcvars64.bat"
        # Capture the developer environment privately; never write its secrets to logs.
        environment_script = temporary / "native-msvc-environment.cmd"
        environment_script.write_text(f'@echo off\r\ncall "{script}" >nul\r\nif errorlevel 1 exit /b 1\r\nset\r\n', encoding="utf-8")
        output = subprocess.check_output(["cmd.exe", "/d", "/c", "call", str(environment_script)], env=env, text=True, errors="replace", timeout=60, **background_process_options())
        for line in output.splitlines():
            if "=" in line and not line.startswith("="):
                key, value = line.split("=", 1)
                env[key.upper()] = value
        env["VSLANG"] = "1033"
    def tool(name):
        candidate = shutil.which(name, path=env.get("PATH"))
        if not candidate and vs:
            folder = "Ninja/ninja.exe" if name == "ninja" else "CMake/bin/" + name + ".exe"
            candidate = str(Path(vs) / "Common7/IDE/CommonExtensions/Microsoft/CMake" / folder)
        if not candidate or not Path(candidate).is_file():
            raise RuntimeError(f"missing native tool: {name}")
        return candidate
    return env, {name: tool(name) for name in ("cmake", "ctest", "ninja")}


def source_identity():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, **background_process_options()).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True, **background_process_options()).strip())
    files = set(subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "src", "cmake/native", "scripts/native.py", "scripts/client_sdk.py", "scripts/native_support", "tests/native", "tests/build_pipeline", "tests/integration", "integrations", ".github/workflows/native.yml", "config/native-dependencies.json", "config/python-build-dependencies.json", "config/upstream-baseline.json"], cwd=ROOT, text=True, **background_process_options()).splitlines())
    inputs = {name: sha256(ROOT / name) for name in sorted(files) if (ROOT / name).is_file()}
    fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return {"source_commit": commit, "source_dirty": dirty, "input_sha256": fingerprint, "inputs": inputs}


def require_built_inputs(work: Path):
    built = json.loads((work / "built-source.json").read_text(encoding="utf-8"))
    if built["input_sha256"] != source_identity()["input_sha256"]:
        raise ValueError("native inputs changed since successful build")
    if built.get("build_cache_sha256") != sha256(work / "cmake/CMakeCache.txt") or built.get("build_outputs") != build_outputs(work):
        raise ValueError("native build cache or outputs changed; rebuild")
    return built


def build_outputs(work: Path):
    return {path.relative_to(work / "cmake").as_posix(): sha256(path)
            for folder in ("bin", "lib") for path in sorted((work / "cmake" / folder).rglob("*")) if path.is_file()}


def configured_compiler(work: Path):
    cache = (work / "cmake/CMakeCache.txt").read_text(encoding="utf-8")
    for line in cache.splitlines():
        if line.startswith(("CMAKE_CXX_COMPILER:FILEPATH=", "CMAKE_CXX_COMPILER:STRING=", "CMAKE_CXX_COMPILER:UNINITIALIZED=")):
            return line.split("=", 1)[1]
    raise ValueError("configured C++ compiler identity is missing")


def require_configured_source(work: Path, requested: str, key: str):
    # CTest pins this source at configure time. Reject a different request rather
    # than silently testing the old private core (or skipping the requested one).
    cache = (work / "cmake/CMakeCache.txt").read_text(encoding="utf-8")
    configured = None
    for line in cache.splitlines():
        if line.startswith(key + ":") and "=" in line:
            configured = line.split("=", 1)[1]
            break
    if configured is None:
        raise ValueError("configured external source identity is missing; run build/all")
    def identity(value):
        return os.path.normcase(os.path.normpath(str(Path(value).resolve()))) if value else ""
    if identity(configured) != identity(requested):
        raise ValueError("requested external source differs from CTest configuration; run build/all with the same source selection")


def require_configured_qmt_source(work: Path, requested: str):
    require_configured_source(work, requested, "GH_QMT_SOURCE_ROOT")


def calendar_owner_identity(root: str):
    """Bind actual producer inputs independently of the consumer build identity."""
    if not root:
        return None
    base = Path(root).resolve(strict=True)
    sources = (
        "common/contracts.py", "common/market_calendar.py", "common/exchange_calendar.py",
        "common/replenishment.py", "common/replenishment_clock.py",
        "common/auth.py", "common/settings.py", "common/fact_store.py",
        "services/market_data/calendar_projection.py", "services/market_data/app.py",
    )
    inputs = {"src/qmt_platform/" + name: sha256(base / "src/qmt_platform" / name)
              for name in sources}
    return {"root": str(base), "inputs": inputs,
            "input_sha256": hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()}


def dependencies(work: Path, *, offline=False, audit=False):
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    sources, downloads = work / "deps", work / "downloads"
    sources.mkdir(parents=True, exist_ok=True)
    downloads.mkdir(parents=True, exist_ok=True)
    for entry in lock["dependencies"]:
        name = entry["name"]
        target, blob = sources / name, downloads / entry["archive"]
        marker = target / ".native-source.json"
        if blob.exists() and sha256(blob) != entry["sha256"]:
            raise ValueError(f"dependency checksum mismatch: {blob}")
        if not blob.exists():
            if offline:
                raise ValueError(f"offline dependency missing: {name}")
            # A developer may supply an already downloaded official archive.
            prefetched = ROOT / ".tmp/native-downloads" / entry["archive"]
            partial = downloads / (entry["archive"] + ".partial-" + uuid.uuid4().hex)
            if prefetched.exists() and sha256(prefetched) == entry["sha256"]:
                shutil.copyfile(prefetched, partial)
            else:
                with urllib.request.urlopen(entry["url"], timeout=60) as src, partial.open("xb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
            if sha256(partial) != entry["sha256"]:
                raise ValueError(f"download checksum mismatch: {name}")
            partial.rename(blob)
        excluded = {"doc", "docs", "test", "tests", "example", "examples", "bench", "benchmark", "performance"} if name == "boost" else set()
        def included(relative):
            return not any(part in excluded for part in Path(relative).parts)
        if not target.exists():
            temporary = sources / (name + "-extract-" + uuid.uuid4().hex)
            temporary.mkdir()
            with tarfile.open(blob) as source:
                members = [member for member in source.getmembers() if included(member.name)]
                for member in members:
                    if Path(member.name).is_absolute() or ".." in Path(member.name).parts or ":" in member.name or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                        raise ValueError(f"unsafe dependency archive member: {member.name}")
                if hasattr(tarfile, "data_filter"):
                    source.extractall(temporary, members=members, filter="data")
                else:
                    source.extractall(temporary, members=members)
            children = list(temporary.iterdir())
            if len(children) != 1 or not children[0].is_dir():
                raise ValueError(f"unexpected dependency root: {name}")
            children[0].rename(target)
            temporary.rmdir()
        if not marker.exists():
            # Derive expected source bytes from the verified archive, including
            # interrupted-cache recovery; never trust an unmarked directory.
            tree = {}
            with tarfile.open(blob, "r|*") as source:
                for member in source:
                    relative = "/".join(member.name.split("/")[1:])
                    if member.isfile() and relative and included(relative):
                        tree[relative] = hashlib.sha256(source.extractfile(member).read()).hexdigest()
            marker.write_text(json.dumps({"archive_sha256": entry["sha256"], "filter_version": 1, "files": tree}, sort_keys=True), encoding="utf-8")
        recorded = json.loads(marker.read_text(encoding="utf-8"))
        if recorded["archive_sha256"] != entry["sha256"] or recorded.get("filter_version") != 1:
            raise ValueError(f"source marker identity mismatch: {name}")
        if hashlib.sha256(json.dumps(recorded["files"], sort_keys=True).encode()).hexdigest() != entry.get("source_files_sha256"):
            raise ValueError(f"source marker map mismatch: {name}")
        actual = {}
        for directory, folders, files in os.walk(target):
            folders[:] = [folder for folder in folders if folder not in excluded]
            for filename in files:
                path = Path(directory) / filename
                if path != marker:
                    actual[path.relative_to(target).as_posix()] = path
        metadata = {rel: [p.stat().st_size, p.stat().st_mtime_ns] for rel, p in actual.items()}
        previous_metadata = recorded.get("verified_metadata", {})
        if set(actual) != set(recorded["files"]) or any(p.is_symlink() or ((audit or previous_metadata.get(rel) != metadata[rel]) and sha256(p) != recorded["files"][rel]) for rel, p in actual.items()):
            raise ValueError(f"dependency source changed: {name}")
        recorded["verified_metadata"] = metadata
        marker.write_text(json.dumps(recorded, sort_keys=True), encoding="utf-8")
        display(f"verified dependency {name} {entry['version']}")
    return lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "deps", "configure", "build", "test", "package", "verify", "all"])
    parser.add_argument("--profile", choices=("native", "qmt-readonly-fixed", "account-scan"), default="native")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--clean-first", action="store_true", help="Clean generated native targets before rebuilding")
    parser.add_argument("--qmt-source", type=Path, help="Optional external QMT business source for pinned pure-strategy qualification; no terminal access")
    parser.add_argument("--calendar-owner-source", type=Path, help="Optional controlled calendar producer source for cross-release HTTP qualification")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--audit-deps", action="store_true", help="Rehash every source file instead of reusing unchanged verified metadata")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    from native_support.qmt_readonly_fixed import claim_work
    profile_work = {"native": "build/native", "qmt-readonly-fixed": "build/native/qmt-readonly-fixed/default",
                    "account-scan": "build/native/account-scan/default"}
    work = (args.work or ROOT / profile_work[args.profile]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    try:
        claim_work(work, args.profile)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    logs = work / "logs"
    logs.mkdir(exist_ok=True)
    receipt = {"status": "running", "profile": args.profile,
               "scope": {"native": "development-sdk-independent", "qmt-readonly-fixed": "development-fixed-readonly",
                         "account-scan": "development-account-scan"}[args.profile],
               "source": source_identity() if args.profile == "native" else {}, "stages": {}}
    receipt_path = work / "receipt.json"
    owner_identity = None
    def save():
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    def stage(name, argv, timeout=1200, *, cwd=None):
        receipt["stages"][name] = {"status": "running", "argv": [str(arg) for arg in argv]}
        save()
        try:
            _, elapsed = run(argv, env=env, cwd=cwd, log=logs / (name + ".log"), timeout=timeout)
            if owner_identity != calendar_owner_identity(env.get("GH_CALENDAR_OWNER_SOURCE", "")):
                raise ValueError("calendar producer inputs changed during qualification")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            receipt["stages"][name]["status"] = "failed"
            save()
            raise
        receipt["stages"][name] = {"status": "passed", "seconds": elapsed}
        save()
    save()
    try:
        command = args.command
        if args.profile == "qmt-readonly-fixed" and command in {"test", "package", "all"} and args.qmt_source is None:
            raise ValueError("qmt-readonly-fixed requires an explicit controlled --qmt-source")
        env, tools = environment(work) if command not in {"deps", "verify"} else (os.environ.copy(), {})
        selected_qmt_source = str(args.qmt_source) if args.qmt_source else (env.get("GH_QMT_SOURCE_ROOT", "") if args.profile == "native" else "")
        if selected_qmt_source:
            qmt_source = Path(selected_qmt_source).resolve(strict=True)
            env["GH_QMT_SOURCE_ROOT"] = str(qmt_source)
            receipt["external_qmt_source"] = str(qmt_source)
        selected_owner = str(args.calendar_owner_source) if args.calendar_owner_source else (env.get("GH_CALENDAR_OWNER_SOURCE", "") if args.profile == "native" else "")
        if args.profile != "native":
            env.pop("GH_CALENDAR_OWNER_SOURCE", None)
            if not selected_qmt_source:
                env.pop("GH_QMT_SOURCE_ROOT", None)
        if selected_owner:
            env["GH_CALENDAR_OWNER_SOURCE"] = str(Path(selected_owner).resolve(strict=True))
        owner_identity = calendar_owner_identity(env.get("GH_CALENDAR_OWNER_SOURCE", ""))
        receipt["calendar_owner_source"] = owner_identity
        if command == "doctor":
            for name, exe in tools.items():
                stage(name, [exe, "--version"], 30)
            display(json.dumps({"platform": platform.platform(), "tools": tools}, indent=2))
        if command in {"deps", "configure", "build", "test", "package", "all"}:
            # 固定来源资格由锁定内容摘要授予；可改的大小/mtime缓存不能替代内容校验。
            # 普通native保留既有显式audit选项，固定profile在同一owner中始终核内容。
            receipt["dependencies"] = dependencies(work, offline=args.offline or command in {"build", "test", "package"}, audit=args.audit_deps or args.profile in {"qmt-readonly-fixed", "account-scan"})
            save()
        if args.profile in {"qmt-readonly-fixed", "account-scan"}:
            if args.profile == "account-scan":
                from native_support.account_scan_flow import execute
            else:
                from native_support.qmt_readonly_flow import execute
            execute(sys.modules[__name__], args, work, env, tools, receipt, stage, save)
            receipt["status"] = "passed"
            save()
            display(json.dumps({"receipt": str(receipt_path), "artifact": receipt.get("artifact"), "status": "passed"}, ensure_ascii=False))
            return 0
        if command in {"configure", "build", "all"}:
            if receipt["source"]["input_sha256"] != source_identity()["input_sha256"]:
                raise ValueError("native inputs changed during preparation; restart the pipeline")
            compiler = shutil.which("cl", path=env.get("PATH"))
            if not compiler:
                raise RuntimeError("MSVC compiler is missing from the configured environment")
            compiler = Path(compiler).as_posix()
            if (work / "cmake/CMakeCache.txt").exists():
                cached_compiler = configured_compiler(work)
                if os.path.normcase(os.path.normpath(cached_compiler)) != os.path.normcase(os.path.normpath(compiler)):
                    raise ValueError("cached compiler differs from this MSVC environment; use a new --work directory")
                # Preserve CMake's exact spelling: changing path case/separators
                # can reset its cache and discard other configuration arguments.
                compiler = cached_compiler
            stage("configure", [tools["cmake"], "-S", ROOT / "cmake/native", "-B", work / "cmake", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=ON", "-DCMAKE_CXX_COMPILER:FILEPATH=" + compiler, "-DCMAKE_C_COMPILER:FILEPATH=" + compiler, "-DCMAKE_MAKE_PROGRAM=" + tools["ninja"], "-DWT_DEPS_DIR=" + str(work / "deps"), "-DPython3_EXECUTABLE=" + sys.executable, "-DGH_QMT_SOURCE_ROOT=" + env.get("GH_QMT_SOURCE_ROOT", ""), "-DGH_CALENDAR_OWNER_SOURCE=" + env.get("GH_CALENDAR_OWNER_SOURCE", "")])
            (work / "configured.json").write_text(json.dumps({"lock_sha256": sha256(LOCK), "entry_sha256": sha256(ROOT / "cmake/native/CMakeLists.txt")}), encoding="utf-8")
        if command in {"build", "all"}:
            configured = json.loads((work / "configured.json").read_text(encoding="utf-8"))
            if configured != {"lock_sha256": sha256(LOCK), "entry_sha256": sha256(ROOT / "cmake/native/CMakeLists.txt")}:
                raise ValueError("build configuration inputs changed; run configure")
            before_build = source_identity()
            build_command = [tools["cmake"], "--build", work / "cmake", "--parallel", str(args.jobs)]
            if args.clean_first:
                build_command.append("--clean-first")
            stage("build", build_command)
            if before_build["input_sha256"] != source_identity()["input_sha256"]:
                raise ValueError("native inputs changed during build; rebuild the final inputs")
            before_build.update(build_cache_sha256=sha256(work / "cmake/CMakeCache.txt"), build_outputs=build_outputs(work))
            (work / "built-source.json").write_text(json.dumps(before_build, sort_keys=True), encoding="utf-8")
        if command in {"test", "package", "all"}:
            require_built_inputs(work)
            require_configured_qmt_source(work, env.get("GH_QMT_SOURCE_ROOT", ""))
            require_configured_source(work, env.get("GH_CALENDAR_OWNER_SOURCE", ""), "GH_CALENDAR_OWNER_SOURCE")
            sdk_output = work / "client-sdk" / "artifacts" / uuid.uuid4().hex
            sdk_command = [sys.executable, "-B", ROOT / "scripts/client_sdk.py", "--work", work / "client-sdk", "--output", sdk_output]
            if args.offline:
                sdk_command.append("--offline")
            stage("client-sdk", sdk_command, 120)
            sdk_receipt = json.loads((sdk_output / "receipt.json").read_text(encoding="utf-8"))
            env["GH_MARKET_CLIENT_WHEEL"] = sdk_receipt["wheel"]
            env["GH_CLIENT_BACKEND_WHEEL"] = sdk_receipt["backend"]
            stage("ctest", [tools["ctest"], "--test-dir", work / "cmake", "--output-on-failure", "--output-junit", work / "ctest.xml"], 600)
            stage("pipeline-tests", [sys.executable, "-B", "-m", "unittest", "discover", "-s", ROOT / "tests/build_pipeline", "-v"], 120)
            require_built_inputs(work)
        if command in {"package", "all"}:
            identifier = "dev-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
            package_root = work / "packages" / identifier
            package_root.mkdir(parents=True)
            stage("install", [tools["cmake"], "--install", work / "cmake", "--prefix", package_root])
            (package_root / "clients").mkdir()
            shutil.copyfile(sdk_receipt["wheel"], package_root / "clients" / Path(sdk_receipt["wheel"]).name)
            shutil.copyfile(sdk_output / "receipt.json", package_root / "clients/receipt.json")
            lock = json.loads(LOCK.read_text(encoding="utf-8"))
            for entry in lock["dependencies"]:
                shutil.copyfile(work / "deps" / entry["name"] / entry["license_file"], package_root / "licenses" / (entry["name"] + ".txt"))
            compiler = configured_compiler(work)
            compiler_version = subprocess.run([compiler] if os.name == "nt" else [compiler, "--version"], env=env, capture_output=True, text=True, errors="replace", timeout=30, **background_process_options())
            toolchain = {"compiler": compiler, "compiler_version": (compiler_version.stdout + compiler_version.stderr).splitlines()[:2], "cmake": subprocess.check_output([tools["cmake"], "--version"], text=True, **background_process_options()).splitlines()[0], "ninja": subprocess.check_output([tools["ninja"], "--version"], text=True, **background_process_options()).strip()}
            provenance = {**source_identity(), "upstream_base_commit": json.loads((ROOT / "config/upstream-baseline.json").read_text(encoding="utf-8"))["commit"], "platform": platform.platform(), "architecture": platform.machine(), "toolchain": toolchain, "dependencies": lock, "tests": receipt["stages"], "build_cache_sha256": sha256(work / "cmake/CMakeCache.txt")}
            provenance["calendar_owner_source"] = owner_identity
            write_manifest(package_root, provenance)
            bundle = work / "packages" / (identifier + ".zip")
            digest = archive(package_root, bundle)
            extracted = work / "package-smoke" / identifier
            verify_archive(bundle, digest, extracted)
            runner = extracted / "app" / ("WtRunner.exe" if os.name == "nt" else "WtRunner")
            stage("package-smoke", [runner, "--help"], 30)
            backtest_library = extracted / "app" / ("WtBtPorter.dll" if os.name == "nt" else "libWtBtPorter.so")
            stage("package-backtest", [sys.executable, "-B", extracted / "examples/backtest_flow.py", "--library", backtest_library, "--work", work / "package-smoke" / (identifier + "-replay")], 90)
            stage("package-qmt-minute-strategy", [sys.executable, "-B", extracted / "examples/qmt_minute_replay.py",
                  "--library", backtest_library, "--helper", extracted / "app/WtDtHelper.dll",
                  "--work", work / "package-smoke" / (identifier + "-qmt-minute-strategy"), "--module-root", extracted], 120)
            stage("package-adapters", [extracted / "app/GuanhengPluginProbe.exe", extracted / "app"], 30)
            stage("package-qmt-polling", [sys.executable, "-B", extracted / "examples/polling_flow.py",
                  "--probe", extracted / "app/GuanhengPollingHostProbe.exe", "--module-root", extracted,
                  "--work", work / "package-smoke" / (identifier + "-polling")], 180)
            runtime_work = work / "package-smoke" / (identifier + "-runtime")
            runtime_work.mkdir()
            stage("package-runtime", [extracted / "app/GuanhengRuntimeProbe.exe", "--self-test"], 60, cwd=runtime_work)
            stage("package-minute", [extracted / "app/GuanhengMinuteProbe.exe", "--storage", extracted / "app/WtDataStorage.dll",
                  "--work", work / "package-smoke" / (identifier + "-minute")], 60, cwd=runtime_work)
            env["GH_NATIVE_HISTORY_FIXTURE"] = str(work / "package-smoke" / (identifier + "-history"))
            stage("package-history", [extracted / "app/GuanhengDataFixture.exe", env["GH_NATIVE_HISTORY_FIXTURE"]], 30)
            stage("package-business", [sys.executable, "-B", extracted / "examples/package_probe.py", "--package-root", extracted, "--work", work / "package-smoke" / (identifier + "-business")], 120)
            stage("package-market-service", [sys.executable, "-B", extracted / "examples/market_service_flow.py",
                  "--library", extracted / "app/GuanhengMarketBridge.dll", "--module-root", extracted,
                  "--client-wheel", extracted / "clients" / Path(sdk_receipt["wheel"]).name,
                  "--work", work / "package-smoke" / (identifier + "-http-service")], 60)
            env["GH_MARKET_LIBRARY"] = str(extracted / "app/GuanhengMarketBridge.dll")
            try:
                stage("package-reader-host", [sys.executable, "-B", extracted / "examples/reader_host_flow.py",
                      "--probe", extracted / "app/GuanhengReaderHostProbe.exe", "--module-root", extracted,
                      "--work", work / "package-smoke" / (identifier + "-reader-host")], 180)
            finally:
                env.pop("GH_MARKET_LIBRARY", None)
            worker_site = work / "package-smoke" / (identifier + "-worker-client")
            stage("package-history-worker-install", [sys.executable, "-B", "-m", "pip", "--disable-pip-version-check",
                  "--no-cache-dir", "install", "--no-index", "--no-deps", "--no-compile", "--target", worker_site,
                  extracted / "clients" / Path(sdk_receipt["wheel"]).name], 60)
            env["GH_HISTORY_WORKER_SITE"] = str(worker_site)
            try:
                stage("package-history-worker", [sys.executable, "-B", "-m", "unittest", "discover",
                      "-s", ROOT / "tests/integration/history_worker", "-v"], 180)
            finally:
                env.pop("GH_HISTORY_WORKER_SITE", None)
            if owner_identity:
                env["GH_CALENDAR_FLOW_SITE"] = str(worker_site)
                env["GH_CALENDAR_MODULE_ROOT"] = str(extracted)
                env["GH_MARKET_LIBRARY"] = str(extracted / "app/GuanhengMarketBridge.dll")
                try:
                    stage("package-history-calendar", [sys.executable, "-B", "-m", "unittest", "discover",
                          "-s", ROOT / "tests/integration/calendar_flow", "-v"], 180)
                    stage("package-history-factory", [sys.executable, "-B", "-m", "unittest", "discover",
                          "-s", ROOT / "tests/integration/history_factory_flow", "-v"], 180)
                finally:
                    env.pop("GH_CALENDAR_FLOW_SITE", None)
                    env.pop("GH_CALENDAR_MODULE_ROOT", None)
                    env.pop("GH_MARKET_LIBRARY", None)
            else:
                receipt["stages"]["package-history-calendar"] = {"status": "skipped", "reason": "controlled calendar producer source not configured"}
                receipt["stages"]["package-history-factory"] = {"status": "skipped", "reason": "controlled calendar producer source not configured"}
                save()
            if env.get("GH_QMT_SOURCE_ROOT"):
                stage("package-strategy-market", [sys.executable, "-B", extracted / "examples/strategy_market_flow.py",
                      "--library", extracted / "app/GuanhengMarketBridge.dll", "--helper", extracted / "app/WtDtHelper.dll",
                      "--work", work / "package-smoke" / (identifier + "-strategy-market"), "--module-root", extracted,
                      "--client-wheel", extracted / "clients" / Path(sdk_receipt["wheel"]).name], 120)
                stage("package-retained-strategy", [sys.executable, "-B", extracted / "examples/wt_strategy_replay.py",
                      "--library", backtest_library, "--helper", extracted / "app/WtDtHelper.dll", "--history-library", extracted / "app/GuanhengNativeBarFile.dll",
                      "--work", work / "package-smoke" / (identifier + "-strategy"), "--module-root", extracted], 120)
            else:
                receipt["stages"]["package-strategy-market"] = {"status": "skipped", "reason": "controlled original minute consumer source unavailable; SDK-independent service qualified separately"}
                receipt["stages"]["package-retained-strategy"] = {"status": "skipped", "reason": "external controlled business core not configured"}
                save()
            require_built_inputs(work)
            receipt["artifact"] = {"path": str(bundle), "sha256": digest}
        if command == "verify":
            if not args.archive or not args.sha256:
                raise ValueError("verify requires --archive and trusted --sha256")
            verify_archive(args.archive.resolve(), args.sha256, work / "verified" / uuid.uuid4().hex)
        receipt["status"] = "passed"
        save()
        display(json.dumps({"receipt": str(receipt_path), "artifact": receipt.get("artifact"), "status": "passed"}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, tarfile.TarError, zipfile.BadZipFile) as error:
        receipt.update(status="failed", error=str(error))
        save()
        display(f"FAILED: {error}; receipt={receipt_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
