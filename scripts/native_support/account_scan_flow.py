"""原 native.py 调用的账户 profile 阶段，复用原执行与制品 owner。"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

from . import account_scan as selection
from . import qmt_readonly_fixed as fixed
from .qmt_readonly_flow import build_outputs, compiled_inputs, read_record
from .artifact import archive, sha256, verify_archive, write_manifest
from .account_scan_artifact import record_validation_sources


def require_tests(path: Path, expected: set[str]):
    cases = ET.parse(path).getroot().findall(".//testcase")
    if not cases or any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")):
        raise ValueError("account scan requires nonempty passing CTest results without skips")
    if len(cases) != len(expected) or {case.attrib.get("name") for case in cases} != expected:
        raise ValueError("account scan CTest set differs from required qualification")


def tool_identity(env, tools):
    paths = dict(tools)
    for name in ("cl", "link", "lib", "rc", "mt"):
        path = shutil.which(name, path=env.get("PATH"))
        if path:
            paths[name] = path
    return {name: {"path": str(Path(path).resolve()), "sha256": sha256(Path(path))}
            for name, path in paths.items()}


def runtime_inputs(work, package):
    """逐个核实际CMake运行库来源；本机运行证据与外发许可资格分别登记。"""
    install = work / "cmake/cmake_install.cmake"
    candidates = [Path(name) for name in re.findall(r'"([A-Za-z]:/[^"\r\n]+\.dll)"', install.read_text(encoding="utf-8"))]
    entries = {}
    for installed in sorted((package / "app").glob("*.dll")):
        sources = {str(path): path for path in candidates if path.name.casefold() == installed.name.casefold()}
        if len(sources) != 1:
            raise ValueError("runtime library does not have one explicit CMake install source: " + installed.name)
        source = next(iter(sources.values()))
        digest = sha256(source)
        if sha256(installed) != digest:
            raise ValueError("installed runtime differs from its actual toolchain source")
        entries[installed.name] = {"source": str(source), "sha256": digest, "size": source.stat().st_size}
    if not entries:
        raise ValueError("account scan runtime install source evidence is empty")
    return {"qualification": "local development and isolated relocation only", "files": entries,
            "license_status": "gap", "license_basis": "MSVC/Windows SDK local redist directories; grants not audited in this profile",
            "unverified": ["exact MSVC redistribution grant", "exact Windows SDK/UCRT redistribution grant", "production/outbound distribution approval"]}


def relocated(work, env, stage, extracted):
    """在独立 CWD 用包内产品与自有 QTS 验证安装闭包。"""
    token = uuid.uuid4().hex
    location = work / "relocation" / token
    location.mkdir(parents=True)
    app = extracted / "app"
    previous = env.copy()
    try:
        system = Path(os.environ.get("SystemRoot", "C:/Windows"))
        env["PATH"] = os.pathsep.join(map(str, (app, system / "System32", system)))
        for name in ("PYTHONPATH", "GH_QMT_SOURCE_ROOT", "GH_CALENDAR_OWNER_SOURCE"):
            env.pop(name, None)
        stage("package-account-scan-" + token, [sys.executable, "-S", "-B",
              extracted / "validation/tests/integration/native_account_scan/run.py",
              "--host", app / "GuanhengAccountScan.exe", "--library", app / "traders/TraderQMTReadOnly.dll",
              "--output", location / "results"], 420, cwd=location)
    finally:
        env.clear()
        env.update(previous)


def execute(owner, args, work, env, tools, receipt, stage, save):
    if args.qmt_source or args.calendar_owner_source:
        raise ValueError("account-scan accepts repository-owned sources only; external source options are outside this profile")
    command = args.command
    if command in ("doctor", "deps"):
        return
    if command == "verify":
        if not args.archive or not args.sha256:
            raise ValueError("verify requires --archive and trusted --sha256")
        extracted = work / "verified" / uuid.uuid4().hex
        manifest = verify_archive(args.archive.resolve(), args.sha256, extracted)
        if manifest["provenance"].get("profile") != selection.PROFILE:
            raise ValueError("archive profile differs from requested profile")
        relocated(work, env, stage, extracted)
        receipt["artifact"] = {"path": str(args.archive.resolve()), "sha256": args.sha256,
                               "qualification": "synthetic-owned-qts-product-chain"}
        return

    def inputs():
        return selection.prepare_inputs(owner.ROOT, work)

    identity = inputs()
    build_options = selection.build_options(work, identity)
    receipt["frame_io_tests"] = {"enabled": build_options["frame_tests"],
                                 "scope": "frame-owner-only; native/SDK/installation qualifications remain separate"}
    actual_tools = tool_identity(env, tools)
    receipt["source"] = fixed.source_identity(owner.ROOT, identity)
    receipt["fixed_identity"] = identity
    receipt["source_qualification"] = "synthetic owned QTS; original WT Adapter; ordinary production DLL"
    save()

    def require_built():
        built = read_record(work / "built-source.json", ("fixed_identity", "tools", "build_cache_sha256", "build_outputs", "compiled_inputs_sha256"))
        selection.require_identity(inputs(), built["fixed_identity"])
        if built["tools"] != actual_tools:
            raise ValueError("account scan toolchain changed")
        if built["build_cache_sha256"] != sha256(work / "cmake/CMakeCache.txt") or built["build_outputs"] != build_outputs(work):
            raise ValueError("account scan cache or outputs changed; rebuild")
        if built["compiled_inputs_sha256"] != sha256(work / "compiled-inputs.json"):
            raise ValueError("compiler input evidence changed; rebuild")
        dependencies = read_record(work / "compiled-inputs.json", ("dependencies",))["dependencies"]
        if not dependencies or any(not Path(path).is_file() or sha256(Path(path)) != digest for path, digest in dependencies.items()):
            raise ValueError("actual compiler dependency changed; rebuild")

    if command in ("configure", "build", "all"):
        compiler = shutil.which("cl", path=env.get("PATH"))
        if not compiler:
            raise RuntimeError("MSVC compiler is missing")
        compiler = Path(compiler).as_posix()
        if (work / "cmake/CMakeCache.txt").exists():
            previous = owner.configured_compiler(work)
            if os.path.normcase(os.path.normpath(previous)) != os.path.normcase(os.path.normpath(compiler)):
                raise ValueError("account scan compiler changed; use a new work directory")
            compiler = previous
        stage("configure", [tools["cmake"], "-S", work / "inputs/owned/cmake/native/account_scan",
              "-B", work / "cmake", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=ON",
              "-DCMAKE_CXX_COMPILER:FILEPATH=" + compiler, "-DCMAKE_C_COMPILER:FILEPATH=" + compiler,
              "-DCMAKE_MAKE_PROGRAM=" + tools["ninja"], "-DWT_DEPS_DIR=" + str(work / "deps"),
              "-DPython3_EXECUTABLE=" + sys.executable, *selection.cmake_arguments(work, frame_tests=build_options["frame_tests"])])
        selection.require_identity(inputs(), identity)
        (work / "configured.json").write_text(json.dumps({"fixed_identity": identity, "tools": actual_tools}, sort_keys=True), encoding="utf-8")
    if command in ("build", "all"):
        configured = read_record(work / "configured.json", ("fixed_identity", "tools"))
        selection.require_identity(configured["fixed_identity"], identity)
        if configured["tools"] != actual_tools:
            raise ValueError("account scan configured toolchain changed")
        targets = ["GuanhengAccountScan", "NqpTraderReadOnly"]
        if build_options["frame_tests"]:
            targets.append("GuanhengAccountFrameProbe")
        argv = [tools["cmake"], "--build", work / "cmake", "--target", *targets, "--parallel", str(args.jobs)]
        if args.clean_first:
            argv.append("--clean-first")
        stage("build", argv)
        stage("native-dependencies", [tools["ninja"], "-C", work / "cmake", "-t", "deps"], 60)
        stage("native-link-commands", [tools["ninja"], "-C", work / "cmake", "-t", "commands"], 60)
        (work / "compiled-inputs.json").write_text(json.dumps(compiled_inputs(work, source_root=owner.ROOT), indent=2), encoding="utf-8")
        selection.require_identity(inputs(), identity)
        (work / "built-source.json").write_text(json.dumps({"profile": selection.PROFILE,
            "fixed_identity": identity, "tools": actual_tools,
            "build_cache_sha256": sha256(work / "cmake/CMakeCache.txt"), "build_outputs": build_outputs(work),
            "compiled_inputs_sha256": sha256(work / "compiled-inputs.json")}, sort_keys=True), encoding="utf-8")
    if command in ("test", "package", "all"):
        require_built()
        stage("ctest", [tools["ctest"], "--test-dir", work / "cmake", "--output-on-failure", "--output-junit", work / "ctest.xml"], 600)
        required = set(build_options["required_ctests"])
        require_tests(work / "ctest.xml", required)
        stage("pipeline-tests", [sys.executable, "-B", "-m", "unittest", "discover", "-s",
              work / "inputs/owned/tests/tools/account_scan_build", "-v"], 120)
        require_built()
    if command in ("package", "all"):
        token = "dev-account-scan-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        package = work / "packages" / token
        stage("install", [tools["cmake"], "--install", work / "cmake", "--prefix", package])
        lock = json.loads((owner.ROOT / "config/native-dependencies.json").read_text(encoding="utf-8"))
        for dependency in lock["dependencies"]:
            shutil.copyfile(work / "deps" / dependency["name"] / dependency["license_file"], package / "licenses" / (dependency["name"] + ".txt"))
        runtime = runtime_inputs(work, package)
        for destination in (work / "runtime-inputs.json", package / "provenance/runtime-inputs.json"):
            destination.write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")
        # 仅为同一owned输入的test-only源码安装封存；schema2运行资格另由后继门禁拥有。
        validation_sources = record_validation_sources(package, work / "inputs/owned", identity["owned"])
        compiler = owner.configured_compiler(work)
        version = subprocess.run([compiler], env=env, capture_output=True, text=True, errors="replace", timeout=30, **owner.background_process_options())
        provenance = {**fixed.source_identity(owner.ROOT, identity), "profile": selection.PROFILE,
            "upstream_base_commit": fixed.WT_COMMIT, "fixed_sources": {
                "wt_commit": fixed.WT_COMMIT, "upstream_manifest_sha256": sha256(work / "inputs/upstream/input.json"),
                "owned_manifest_sha256": sha256(work / "inputs/owned/input.json"), "identity_sha256": identity["input_sha256"]},
            "source_qualification": receipt["source_qualification"], "platform": sys.platform,
            "real_terminal_access": False, "old_project_runtime_dependency": False,
            "architecture": "AMD64", "dependencies": lock, "tools": actual_tools,
            "toolchain": {"compiler": compiler, "compiler_version": (version.stdout + version.stderr).splitlines()[:2],
                "cmake": subprocess.check_output([tools["cmake"], "--version"], text=True, **owner.background_process_options()).splitlines()[0],
                "ninja": subprocess.check_output([tools["ninja"], "--version"], text=True, **owner.background_process_options()).strip()},
            "tests": receipt["stages"], "build_cache_sha256": sha256(work / "cmake/CMakeCache.txt"),
            "compiled_inputs_sha256": sha256(work / "compiled-inputs.json"),
            "runtime_inputs_sha256": sha256(work / "runtime-inputs.json"),
            "validation_sources": validation_sources,
            "runtime_distribution_qualification": "development only; production CRT/UCRT licensing remains separately qualified"}
        require_built()
        write_manifest(package, provenance)
        bundle = work / "packages" / (token + ".zip")
        digest = archive(package, bundle)
        extracted = work / "package-smoke" / token
        verify_archive(bundle, digest, extracted)
        relocated(work, env, stage, extracted)
        require_built()
        receipt["artifact"] = {"path": str(bundle), "sha256": digest,
                               "qualification": "synthetic-owned-qts-product-chain"}
