"""Offline Reader build from fixed Git, approved overlays and locked archives.

The work directory must be new. Historical build trees and prebuilt WT libraries
are never inputs. Default storage, explicit NRC and optional WLC stay separate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import native
from native_support.artifact import normal_path, sha256
from native_support.qmt_readonly_fixed import git_blobs, write_snapshot, verify_snapshot, _regular


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def remaining(deadline, phase):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError("original build deadline exceeded: " + phase)
    return seconds


def source(root, name, digest=None):
    normal_path(name)
    path = root / name
    for parent in [path, *path.parents]:
        if parent == root.parent:
            break
        if parent.is_symlink() or getattr(parent.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("linked input: " + name)
    _regular(path)
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if digest is not None and actual != digest:
        raise ValueError("source identity mismatch: " + name)
    return {"sha256": actual, "data": raw}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--toolchain-lock", type=Path, required=True)
    parser.add_argument("--writer-lifecycle", action="store_true")
    parser.add_argument("--data-components", action="store_true")
    parser.add_argument("--seconds", type=float, default=1800)
    args = parser.parse_args()
    if args.data_components and not args.writer_lifecycle:
        raise ValueError("data components require explicit --writer-lifecycle")
    if not 1 <= args.seconds <= 7200:
        raise ValueError("build budget must be 1..7200 seconds")
    work = args.work.resolve()
    # 深工作树加Boost源码路径会超过Windows原生工具路径额度；允许独立E盘构建根。
    # 输入始终从ROOT核验和快照，输出位置不改变任何源码身份或选择。
    if not work.is_absolute() or work.drive.upper() != 'E:':
        raise ValueError("reader build requires an absolute E: work directory")
    if work.exists():
        raise ValueError("use a new work directory")
    work.mkdir(parents=True)
    deadline = time.monotonic() + args.seconds
    expected_tools = json.loads(args.toolchain_lock.read_bytes())
    git = shutil.which("git")
    if not git or {"path": str(Path(git).resolve()), "sha256": sha256(Path(git))} != expected_tools.get("git"):
        raise ValueError("Git differs from explicit toolchain lock")
    # A partial clone must fail on missing objects instead of fetching during an offline build.
    os.environ["GIT_NO_LAZY_FETCH"] = "1"
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    remaining(deadline, "source declaration")
    lock_raw = (ROOT / "config/native-reader-sources.json").read_bytes()
    lock = json.loads(lock_raw)
    extra_roots = ()
    if args.data_components:
        data_lock = json.loads(source(ROOT, "config/native-data-sources.json")["data"])
        if data_lock["commit"] != lock["commit"]:
            raise ValueError("data component Git identity mismatch")
        extra_roots = tuple(data_lock["extra_upstream_roots"])
    entries = git_blobs(ROOT, lock["commit"], tuple(lock["upstream_roots"]) + extra_roots)
    remaining(deadline, "fixed Git returned")
    for row in lock["runtime_overlays"]:
        if entries[row["target"]]["sha256"] != row["baseline_sha256"]:
            raise ValueError("overlay base mismatch")
        entries[row["target"]] = source(ROOT, row["source"], row["sha256"])
    remaining(deadline, "upstream snapshot")
    upstream = write_snapshot(work / "inputs/upstream", entries, commit=lock["commit"])
    nrc_entries = dict(entries)
    row = lock["nrc"]
    nrc_entries[row["target"]] = source(ROOT, row["source"], row["sha256"])
    write_snapshot(work / "inputs/nrc", nrc_entries, commit=lock["commit"])
    remaining(deadline, "NRC snapshot returned")
    # A separate translation unit gives the embedded original factory private
    # names without changing the independently built original DLL's exports.
    write_snapshot(work / "inputs/embedded", entries, commit=lock["commit"])
    remaining(deadline, "embedded snapshot returned")
    names = set(lock["owned_sources"])
    names.update(["scripts/native.py", "config/native-dependencies.json", "config/native-reader-sources.json"])
    if args.writer_lifecycle:
        names.update(["cmake/native/writer_lifecycle.cmake", lock["wlc"]["source"]])
    names.update("scripts/native_support/" + n for n in ("__init__.py", "reader_product.py", "artifact.py",
        "qmt_readonly_fixed.py", "process_startup.py", "process_job.py"))
    for directory in ("cmake/native/reader_product",):
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / directory).rglob("*")
                     if p.is_file() and p.suffix in (".py", ".cmake", ".txt"))
    names.update("tests/integration/" + n for n in ("native_minute_reader/probe.cpp",
        "native_minute_reader/boundary.cpp", "native_minute_reader/host.cpp", "native_daily_publication/probe.cpp"))
    names.update(x["source"] for x in lock["runtime_overlays"])
    names.add(lock["nrc"]["source"])
    names.update(x["source"] for x in lock["license_materials"])
    own = {n: source(ROOT, n, lock["owned_sources"].get(n)) for n in sorted(names)}
    data_directories = []
    if args.data_components:
        from native_support import data_components
        material, data_directories = data_components.prepare(ROOT, work, entries, source, write_snapshot, data_lock)
        own.update(material)
        own["scripts/native_support/data_components.py"] = source(ROOT, "scripts/native_support/data_components.py")
        for name in ("cmake/native/qmt_shm_quotes.cmake", "tests/integration/native_data_components/probe.py"):
            own[name] = source(ROOT, name)
    if own["config/native-reader-sources.json"]["data"] != lock_raw:
        raise ValueError("source declaration changed during snapshot preparation")
    for row in lock["license_materials"]:
        if own[row["source"]]["sha256"] != row["sha256"]:
            raise ValueError("license material identity mismatch")
    # Relative includes in the unchanged owned Reader use adjacent WT headers.
    owned = write_snapshot(work / "inputs/owned", {**entries, **own})
    remaining(deadline, "owned snapshot returned")
    env, tools = native.environment(work)
    remaining(deadline, "tool environment returned")
    tools.update({name: shutil.which(name, path=env["PATH"]) for name in ("cl", "link", "lib", "rc", "mt")})
    tools["python"] = sys.executable
    tools["git"] = git
    actual_tools = {n: {"path": str(Path(p).resolve()), "sha256": sha256(Path(p))} for n, p in tools.items()}
    if actual_tools != expected_tools:
        raise ValueError("toolchain differs from explicit toolchain lock")
    save(work / "TOOLCHAIN.json", actual_tools)
    commands = []

    def run(argv, name):
        remaining(deadline, "command admission: " + name)
        argv = [str(x) for x in argv]
        commands.append(dict(argv=argv, log=name))
        save(work / "COMMANDS.json", commands)
        native.run(argv, env=env, cwd=work, log=work / name,
                   timeout=remaining(deadline, "command launch: " + name), private_console=True)
        remaining(deadline, "command returned: " + name)

    if args.writer_lifecycle:
        remaining(deadline, "WLC preparation")
        wlc = work / "inputs/wlc"
        shutil.copytree(work / "inputs/upstream", wlc)
        patch = source(ROOT, lock["wlc"]["source"], lock["wlc"]["sha256"])
        patch_path = work / "writer-lifecycle.patch"
        patch_path.write_bytes(patch["data"])
        env["GIT_CEILING_DIRECTORIES"] = str(work)
        for mode in (["--check"], []):
            run(["git", "-C", wlc, "apply", "--no-index", *mode, patch_path], "wlc-" + ("check" if mode else "apply") + ".log")
        changed = {p.relative_to(wlc).as_posix(): source(wlc, p.relative_to(wlc).as_posix())
                   for p in wlc.rglob("*") if p.is_file() and p.name != "input.json"}
        permitted = {"src/WtDataStorage/WtDataWriter.cpp", "src/WtDataStorage/WtDataWriter.h"}
        if {n for n in changed if changed[n]["sha256"] != entries[n]["sha256"]} != permitted:
            raise ValueError("WLC scope mismatch")
        save(wlc / "input.json", {"commit": lock["commit"], "files": {n: {"sha256": x["sha256"]} for n,x in changed.items()}})
        verify_snapshot(wlc)
        remaining(deadline, "WLC verification returned")
    # Only explicitly supplied, checksum-locked source archives enter this run.
    dep_lock = json.loads((work / "inputs/owned/config/native-dependencies.json").read_bytes())
    (work / "downloads").mkdir()
    for dep in dep_lock["dependencies"]:
        remaining(deadline, "archive admission: " + dep["name"])
        item = source(args.archives.resolve(), dep["archive"], dep["sha256"])
        (work / "downloads" / dep["archive"]).write_bytes(item["data"])
    native.LOCK = work / "inputs/owned/config/native-dependencies.json"
    remaining(deadline, "dependency extraction admission")
    native.dependencies(work, offline=True, audit=True)
    remaining(deadline, "dependency extraction returned")
    configure = [tools["cmake"], "-S", work / "inputs/owned/cmake/native/reader_product", "-B", work / "cmake",
                 "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_MAKE_PROGRAM=" + tools["ninja"],
                 "-DWT_DEPS_DIR=" + (work / "deps").as_posix(),
                 "-DGH_FIXED_UPSTREAM_ROOT=" + (work / "inputs/upstream").as_posix(),
                 "-DGH_FIXED_OWN_ROOT=" + (work / "inputs/owned").as_posix(),
                 "-DGH_NRC_ROOT=" + (work / "inputs/nrc").as_posix(),
                 "-DGH_EMBEDDED_READER_ROOT=" + (work / "inputs/embedded").as_posix(),
                 "-DGH_BUILD_WRITER_LIFECYCLE=" + ("ON" if args.writer_lifecycle else "OFF"),
                 "-DGH_BUILD_DATA_COMPONENTS=" + ("ON" if args.data_components else "OFF"),
                 "-DGH_DATA_COMPONENT_ROOT=" + (work / "inputs/data").as_posix(),
                 "-DGH_WRITER_LIFECYCLE_SOURCE_ROOT=" + (work / "inputs/wlc/src").as_posix()]
    run(configure, "configure.log")
    run([tools["cmake"], "--build", work / "cmake", "--parallel", "2"], "build.log")
    run([tools["cmake"], "--install", work / "cmake", "--prefix", work / "installed"], "install.log")
    directories = ("upstream", "owned", "nrc", "embedded", *(("wlc",) if args.writer_lifecycle else ()), *data_directories)
    for directory in directories:
        remaining(deadline, "source verification: " + directory)
        verify_snapshot(work / "inputs" / directory)
    if any(source(ROOT,n)["sha256"] != x["sha256"] for n,x in own.items()):
        raise ValueError("owned source changed during build")
    if any(sha256(Path(x["path"])) != x["sha256"] for x in actual_tools.values()):
        raise ValueError("toolchain changed during build")
    remaining(deadline, "dependency audit admission")
    native.dependencies(work, offline=True, audit=True)
    remaining(deadline, "dependency audit returned")
    licenses = work / "installed/licenses"
    for dep in dep_lock["dependencies"]:
        shutil.copyfile(work / "deps" / dep["name"] / dep["license_file"], licenses / (dep["name"] + ".txt"))
    for row in lock["license_materials"]:
        shutil.copyfile(work / "inputs/owned" / row["source"], licenses / Path(row["source"]).name)
    provenance = work / "installed/provenance"
    provenance.mkdir()
    for filename in ("TOOLCHAIN.json", "COMMANDS.json"):
        shutil.copyfile(work / filename, provenance / filename)
    for directory in directories:
        shutil.copyfile(work / "inputs" / directory / "input.json", provenance / (directory.replace("/", "-") + ".json"))
    shutil.copyfile(native.LOCK, provenance / "dependencies.json")
    shutil.copyfile(work / "inputs/owned/config/native-reader-sources.json", provenance / "reader-sources.json")
    if args.data_components:
        shutil.copyfile(work / "inputs/owned/config/native-data-sources.json", provenance / "data-sources.json")
        data_components.package(work / "installed", save, sha256)
    result = dict(schema="guanheng.native-reader-build.v1", passed=True, commit=lock["commit"],
                  runtime_overlays=len(lock["runtime_overlays"]), writer_lifecycle=args.writer_lifecycle,
                  data_components=args.data_components,
                  outputs={p.relative_to(work / "installed").as_posix():sha256(p)
                           for p in (work / "installed").rglob("*") if p.is_file()},
                  upstream_input_sha256=sha256(work / "inputs/upstream/input.json"),
                  owned_input_sha256=sha256(work / "inputs/owned/input.json"))
    remaining(deadline, "success staging")
    save(work / "BUILT.pending.json", result)
    remaining(deadline, "success publication")
    (work / "BUILT.pending.json").replace(work / "BUILT.json")
    try:
        remaining(deadline, "success publication returned")
    except TimeoutError:
        # Only this attempt's fresh success receipt is withdrawn. Inputs and
        # failed-build diagnostics remain available for inspection.
        (work / "BUILT.json").unlink()
        raise
    print(json.dumps(dict(passed=True, installed=str(work / "installed"), files=len(result["outputs"]))))


if __name__ == "__main__":
    main()
