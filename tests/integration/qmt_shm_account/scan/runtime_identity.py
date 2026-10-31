"""ATI安装收据的唯一测试契约；文件准入与本进程实测明确分开。"""
import base64
import csv
from email.parser import BytesParser
import hashlib
import importlib
import importlib.metadata
import math
import io
import re
import zipfile
import os
from pathlib import Path
import struct
import sys
import sysconfig
import types
from fixture_control import Deadline, check, read_value, require, decode

SCHEMA = "qar.test-runtime.v1"
MAXIMUM = 4 * 1024 * 1024


MAX_DISTRIBUTIONS = 256
MAX_REQUIRES = 1024
MAX_RECORDS = 20000
ROLE_OWNERS = {
    "app": {"guanheng_app": "guanheng-app", "pydantic": "pydantic"},
    "host": {"guanheng_qmt_shm": "guanheng-qmt-shm-host",
             "guanheng_qmt_shm_agent": "guanheng-qmt-shm-agent", "pydantic": "pydantic"},
    "wt": {"guanheng_wt_runtime": "guanheng-wt-runtime"},
}
ROLE_REQUIRED_MODULES = {
    "app": {"guanheng_app", "guanheng_app.strategy_job", "guanheng_app.thread_owner", "pydantic"},
    "host": {"guanheng_qmt_shm", "guanheng_qmt_shm.bootstrap", "guanheng_qmt_shm.server",
             "guanheng_qmt_shm_agent", "guanheng_qmt_shm_agent.restricted", "pydantic"},
    "wt": {"guanheng_wt_runtime", "guanheng_wt_runtime.runtime"},
}
ROLE_PRODUCT_PREFIXES = {
    "app": ("guanheng_app",),
    "host": ("guanheng_qmt_shm", "guanheng_qmt_shm_agent"),
    "wt": ("guanheng_wt_runtime",),
}


def bounded(values, maximum, deadline):
    """复用逐动作边界；显式传本模块check保留旧虚拟时钟回归。"""
    yield from Deadline(deadline, checker=check).iter(values, maximum)


def hash_bytes(raw, deadline):
    budget = Deadline(deadline, checker=check)
    value = budget.call(hashlib.sha256, raw)
    return budget.call(value.hexdigest)


def parse_metadata(raw, deadline):
    budget = Deadline(deadline, checker=check)
    parser = budget.call(BytesParser)
    return budget.call(parser.parsebytes, raw)


def dist_name(name):
    require(type(name) is str and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", name) is not None)
    return re.sub(r"[-_.]+", "-", name).lower()


def metadata_fields(metadata, deadline):
    budget = Deadline(deadline, checker=check)
    name = budget.call(metadata.__getitem__, "Name")
    version = budget.call(metadata.__getitem__, "Version")
    requires = budget.call(metadata.get_all, "Requires-Dist", [])
    require(type(version) is str and 0 < len(version) <= 256)
    result = []
    for item in bounded(requires, MAX_REQUIRES, deadline):
        require(type(item) is str and len(item) <= 8192)
        result.append(item)
    return dist_name(name), version, result


def wheel_versions(value, root, deadline):
    """版本来自已核wheel原件，避免测试层维护另一份产品版本表。"""
    budget = Deadline(deadline, checker=check)
    result = {}
    for name in bounded(value["wheels"], MAX_DISTRIBUTIONS, deadline):
        raw = capture(relative(root, name, deadline), deadline, 256 * 1024 * 1024)
        require(hash_bytes(raw, deadline) == value["files"][name], "wheel bytes changed")
        def read_metadata(opened):
            entries = []
            for entry in bounded(budget.call(opened.infolist), MAX_RECORDS, deadline):
                if entry.filename.endswith(".dist-info/METADATA") and len(entry.filename.split("/")) == 2:
                    entries.append(entry)
            require(len(entries) == 1 and entries[0].file_size <= 1048576, "wheel METADATA limit")
            metadata_raw = budget.call(opened.read, entries[0])
            return metadata_fields(parse_metadata(metadata_raw, deadline), deadline)
        def read_wheel(opened_buffer):
            budget.check()
            wheel = zipfile.ZipFile(opened_buffer)
            return budget._context(wheel, read_metadata)
        # 原bytes内存buffer和wheel都先接管；迟到及异常沿同一短context清理。
        budget.check()
        buffer = io.BytesIO(raw)
        fields = budget._context(buffer, read_wheel)
        require(fields[0] not in result, "duplicate wheel distribution")
        result[fields[0]] = fields[1:]
    return result


def module_owner(name, role):
    prefix = name.split(".")[0]
    require(prefix in ROLE_OWNERS[role], "module outside role whitelist")
    return ROLE_OWNERS[role][prefix]


def hex64(value):
    require(type(value) is str and len(value) == 64 and all(x in "0123456789abcdef" for x in value))
    return value


def relative(root, text, deadline=None):
    """运行准入沿原截止；原纯路径测试可省略预算参数。"""
    require(type(text) is str and text and "\\" not in text)
    part = Path(text)
    require(not part.is_absolute() and not part.drive and all(x not in (".", "..", "") for x in text.split("/")))
    if deadline is not None: check(deadline)
    result = (root / part).resolve(strict=True)
    if deadline is not None: check(deadline)
    require(result.is_relative_to(root), "receipt path outside installation")
    return result


def sha_file(path, deadline, maximum=1024 * 1024 * 1024):
    budget = Deadline(deadline, checker=check)
    require(type(maximum) is int and 0 <= maximum <= 1024 * 1024 * 1024, "identity byte limit")
    require(budget.call(path.stat).st_size <= maximum, "identity byte limit")
    digest = budget.call(hashlib.sha256)
    def consume(stream):
        total = 0
        while True:
            block = budget.call(stream.read, min(1048576, maximum - total + 1))
            require(type(block) is bytes, "identity bytes required")
            if not block:
                break
            total += len(block)
            require(total <= maximum, "identity byte limit")
            budget.call(digest.update, block)
        return budget.call(digest.hexdigest)
    # 共享短stream所有权；保留现有stat/open接口及实际累计流量检查。
    return budget._stream(path, "rb", consume)


def capture(path, deadline, maximum):
    return Deadline(deadline, checker=check).read_bytes(path, maximum)


def admit(path, role, deadline):
    """Parent只核文件；Host实际解释器/module事实由Host自身check_current取得。"""
    budget = Deadline(deadline, checker=check)
    value = read_value(path, deadline, MAXIMUM)
    budget.check()
    keys = {"schema", "role", "root", "prefix", "executable", "site", "base_executable", "base_sha256",
            "version", "bits", "venv_cfg", "files", "modules", "distributions", "lock", "wheels", "pip_check"}
    require(type(value) is dict and set(value) == keys and value["schema"] == SCHEMA and value["role"] == role)
    require(role in ROLE_OWNERS and value["version"] == [3, 12] and type(value["bits"]) is int and value["bits"] == 64)
    require(value["pip_check"] is True, "installer pip check missing")
    root = Path(value["root"]); require(root.is_absolute())
    check(deadline)
    root = root.resolve(strict=True)
    check(deadline)
    prefix = relative(root, value["prefix"], deadline); require(budget.call(prefix.is_dir))
    site = relative(root, value["site"], deadline); require(budget.call(site.is_dir) and site.is_relative_to(prefix))
    require(relative(root, value["venv_cfg"], deadline) == prefix / "pyvenv.cfg", "ordinary venv metadata missing")
    executable = relative(root, value["executable"], deadline); require(executable.is_relative_to(prefix))
    require(type(value["files"]) is dict and 1 <= len(value["files"]) <= 20000)
    for name, expected in bounded(value["files"].items(), 20000, deadline):
        require(sha_file(relative(root, name, deadline), deadline) == hex64(expected), "installed file identity")
    for name in (value["executable"], value["venv_cfg"], value["lock"]):
        require(name in value["files"], "missing required installed identity")
    require(type(value["wheels"]) is list and 1 <= len(value["wheels"]) <= 256)
    require(len(value["wheels"]) == len(set(value["wheels"])))
    require(all(x in value["files"] and x.endswith(".whl") for x in value["wheels"]), "offline wheels missing")
    base = Path(value["base_executable"]); require(base.is_absolute())
    require(sha_file(budget.call(base.resolve, strict=True), deadline) == hex64(value["base_sha256"]), "base interpreter identity")
    require(type(value["modules"]) is dict and 1 <= len(value["modules"]) <= 256)
    required = ROLE_REQUIRED_MODULES[role]
    require(required <= set(value["modules"]))
    for name, text in bounded(value["modules"].items(), 256, deadline):
        require(type(name) is str and name and all(part.isidentifier() for part in name.split(".")))
        allowed = tuple(ROLE_OWNERS[role])
        require(any(name == prefix or name.startswith(prefix + ".") for prefix in allowed), "module outside role whitelist")
        require(text in value["files"] and relative(root, text, deadline).is_relative_to(site), "module outside role site")
        require(not name.startswith("guanheng_app") if role == "host" else not name.startswith(("guanheng_qmt_shm", "guanheng_qmt_shm_agent")))
    require(type(value["distributions"]) is list and 1 <= len(value["distributions"]) <= 256)
    seen = set()
    ownership = {}
    wheels = wheel_versions(value, root, deadline)
    for dist in bounded(value["distributions"], MAX_DISTRIBUTIONS, deadline):
        require(type(dist) is dict and set(dist) == {"name", "version", "metadata", "record", "requires_dist"})
        require(type(dist["name"]) is str and dist["name"] not in seen and type(dist["version"]) is str)
        normalized = dist_name(dist["name"])
        require(normalized not in seen)
        seen.add(normalized)
        require(type(dist["requires_dist"]) is list and len(dist["requires_dist"]) <= MAX_REQUIRES)
        for requirement in bounded(dist["requires_dist"], MAX_REQUIRES, deadline):
            require(type(requirement) is str and len(requirement) <= 8192)
        for field in ("metadata", "record"):
            require(dist[field] in value["files"] and relative(root, dist[field], deadline).is_relative_to(site))
        metadata_path = relative(root, dist["metadata"], deadline)
        metadata_raw = capture(metadata_path, deadline, 1048576)
        require(hash_bytes(metadata_raw, deadline) == value["files"][dist["metadata"]])
        metadata = parse_metadata(metadata_raw, deadline)
        fields = metadata_fields(metadata, deadline)
        require(fields == (normalized, dist["version"], dist["requires_dist"]), "METADATA mismatch")
        if normalized in ROLE_OWNERS[role].values():
            require(wheels.get(normalized) == fields[1:], "required product wheel version mismatch")
        record_path = relative(root, dist["record"], deadline)
        require(metadata_path.name == "METADATA" and record_path.name == "RECORD"
                and metadata_path.parent == record_path.parent
                and metadata_path.parent.name.endswith(".dist-info"), "distribution metadata location")
        record_raw = capture(record_path, deadline, MAXIMUM)
        require(hash_bytes(record_raw, deadline) == value["files"][dist["record"]])
        record_text = budget.call(record_raw.decode, "utf-8")
        record_lines = budget.call(record_text.splitlines)
        record_rows = budget.call(csv.reader, record_lines)
        for row in bounded(record_rows, MAX_RECORDS, deadline):
            require(len(row) == 3)
            target = budget.call((site / row[0]).resolve, strict=True)
            require(target.is_relative_to(root), "RECORD escapes role root")
            if not row[1]:
                require(target == record_path or target.suffix == ".pyc", "unhashed installed source")
                continue
            require(row[1].startswith("sha256="), "unsupported RECORD digest")
            actual_sha = sha_file(target, deadline)
            require(base64.urlsafe_b64encode(bytes.fromhex(actual_sha)).rstrip(b"=").decode() == row[1][7:], "RECORD content mismatch")
            rel_target = target.relative_to(root).as_posix()
            require(value["files"].get(rel_target) == actual_sha, "installed file omitted from receipt")
            ownership.setdefault(target, set()).add(normalized)
    require(set(ROLE_OWNERS[role].values()) <= seen, "required product distribution missing")
    if role == "wt":
        # WT角色的普通安装不得通过间接依赖重新带入观衡服务。
        require('guanheng-app' not in seen, 'WT runtime depends on observer installation')
    for name, text in bounded(value["modules"].items(), 256, deadline):
        require(ownership.get(relative(root, text, deadline)) == {module_owner(name, role)}, "module RECORD owner mismatch")
    check(deadline)
    return value


def module_origin(module, site, expected, deadline=None):
    # 原纯路径断言接缝保留；生产调用始终传原deadline。
    budget = Deadline(deadline, checker=check) if deadline is not None else None
    source = budget.call(getattr, module, "__file__", None) if budget else getattr(module, "__file__", None)
    require(source is not None)
    actual = budget.call(Path(source).resolve, strict=True) if budget else Path(source).resolve(strict=True)
    require(actual.is_relative_to(site) and actual == expected, "foreign module origin")


def verify_distributions(value, root, site, deadline):
    """实际发行必须定位到收据的同一METADATA/RECORD；每项有界且不重置截止。"""
    budget = Deadline(deadline, checker=check)
    expected = {}
    for item in bounded(value["distributions"], MAX_DISTRIBUTIONS, deadline):
        name = dist_name(item["name"])
        require(name not in expected, "duplicate installed distribution")
        expected[name] = item
    require(set(ROLE_OWNERS[value["role"]].values()) <= set(expected), "required product distribution missing")
    actual = set()
    owners = {}
    check(deadline)
    distributions = budget.call(importlib.metadata.distributions, path=[str(site)])
    check(deadline)
    for dist in bounded(distributions, MAX_DISTRIBUTIONS, deadline):
        metadata = budget.call(getattr, dist, "metadata")
        check(deadline)
        name, version, requires = metadata_fields(metadata, deadline)
        require(name not in actual and name in expected, "installed distribution graph mismatch")
        item = expected[name]
        require((version, requires) == (item["version"], item["requires_dist"]), "installed distribution graph mismatch")
        actual.add(name)
        check(deadline)
        files = budget.call(getattr, dist, "files")
        check(deadline)
        require(files is not None, "installed RECORD missing")
        locations = set()
        for file in bounded(files, MAX_RECORDS, deadline):
            located = budget.call(dist.locate_file, file)
            check(deadline)
            target = budget.call(Path(located).resolve, strict=True)
            check(deadline)
            require(target.is_relative_to(root), "actual RECORD escapes role root")
            locations.add(target)
            owners.setdefault(target, set()).add(name)
        require(relative(root, item["metadata"], deadline) in locations and relative(root, item["record"], deadline) in locations,
                "actual distribution metadata binding")
        # 不能由另一个发行的RECORD冒领相同METADATA/RECORD；实际读取bytes也须同身份。
        for field in ("metadata", "record"):
            check(deadline)
            text = budget.call(dist.read_text, "METADATA" if field == "metadata" else "RECORD")
            check(deadline)
            require(type(text) is str, "actual metadata missing")
            captured = capture(relative(root, item[field], deadline), deadline, MAXIMUM)
            require(hash_bytes(captured, deadline) == value["files"][item[field]],
                    "actual distribution file identity changed")
            # stdlib read_text使用通用换行；本边界仍先复验原bytes SHA。
            decoded = budget.call(captured.decode, "utf-8")
            require(text == decoded.replace("\r\n", "\n").replace("\r", "\n"),
                    "actual distribution metadata bytes")
    require(actual == set(expected), "installed distribution graph mismatch")
    for name, text in bounded(value["modules"].items(), 256, deadline):
        require(owners.get(relative(root, text, deadline)) == {module_owner(name, value["role"])}, "actual module RECORD owner mismatch")
    check(deadline)
    return owners


def check_current(value, deadline):
    """在所属解释器中实测sys及导入来源；收据记录本身不授此事实。"""
    budget = Deadline(deadline, checker=check)
    root = budget.call(Path(value["root"]).resolve, strict=True)
    site = relative(root, value["site"], deadline)
    require(sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 12) and struct.calcsize("P") * 8 == value["bits"])
    purelib = budget.call(sysconfig.get_path, "purelib")
    actual_site = budget.call(Path(purelib).resolve, strict=True)
    require(actual_site == site, "not current installed site")
    require(sys.flags.isolated == 1 and sys.flags.no_site == 0 and sys.flags.dont_write_bytecode == 1)
    executable = budget.call(Path(sys.executable).resolve, strict=True)
    require(executable == relative(root, value["executable"], deadline))
    prefix = budget.call(Path(sys.prefix).resolve, strict=True)
    require(prefix == relative(root, value["prefix"], deadline))
    base = budget.call(Path(sys._base_executable).resolve, strict=True)
    expected_base = budget.call(Path(value["base_executable"]).resolve, strict=True)
    require(base == expected_base)
    owners = verify_distributions(value, root, site, deadline)
    verify_modules(value, root, site, owners, deadline)


def verify_modules(value, root, site, owners, deadline):
    """导入前后核同一安装文件；加载的产品子模块也须属于唯一原RECORD。"""
    budget = Deadline(deadline, checker=check)
    for name, text in bounded(value["modules"].items(), 256, deadline):
        expected = relative(root, text, deadline)
        require(sha_file(expected, deadline) == value["files"][text], "current module file identity changed")
        module = budget.call(importlib.import_module, name)
        module_origin(module, site, expected, deadline)
        require(sha_file(expected, deadline) == value["files"][text], "current module file identity changed")
    prefixes = ROLE_PRODUCT_PREFIXES[value['role']]
    budget.check()
    require(len(sys.modules) <= 20000, "loaded module item limit")
    loaded = budget.call(tuple, sys.modules.items())
    for name, module in bounded(loaded, 20000, deadline):
        if any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes):
            source = budget.call(getattr, module, "__file__", None)
            if not source:
                continue
            origin = budget.call(Path(source).resolve, strict=True)
            require(origin.is_relative_to(site), "source overlay")
            require(owners.get(origin) == {module_owner(name, value["role"])}, "loaded module RECORD owner mismatch")
            expected_sha = value["files"].get(origin.relative_to(root).as_posix())
            require(sha_file(origin, deadline) == expected_sha, "loaded module file identity changed")
    budget.check()


def load_thread_owner(path, expected, deadline):
    """同bytes先SHA后compile再exec；每步均核原D，路径只读取一次。"""
    budget = Deadline(deadline, checker=check)
    raw = capture(path, deadline, 65536)
    require(0 < len(raw) <= 65536 and hash_bytes(raw, deadline) == hex64(expected), "QA helper identity")
    module = budget.call(types.ModuleType, "_qar_qa_thread_owner")
    code = budget.call(compile, raw, str(path), "exec")
    budget.call(exec, code, module.__dict__)
    return budget.call(getattr, module, "ThreadOwner")


def admit_tests(root, manifest_path, expected, deadline):
    """验证可搬迁validation原件；清单由后继构建owner生成并固定SHA。"""
    require(root.is_absolute() and manifest_path.is_absolute())
    raw = capture(manifest_path, deadline, MAXIMUM)
    require(hash_bytes(raw, deadline) == hex64(expected))
    value = Deadline(deadline, checker=check).call(decode, raw)
    require(type(value) is dict and set(value) == {"schema", "files"} and value["schema"] == "qar.test-sources.v1")
    require(type(value["files"]) is dict and 1 <= len(value["files"]) <= 1024)
    required = {"tests/integration/qmt_shm_account/scan/" + name for name in (
        "run_schema2.py", "managed_fixture.py", "host_fixture.py", "runtime_identity.py", "fixture_control.py",
        "fixture_values.py", "source_capture.py", "case_oracles.py", "black_box_cases.py", "ordinary_matrix.py", "smoke_ipc.py", "registry.json", "native-main-cases.json")}
    required |= {"tests/integration/qmt_shm_account/test_bootstrap_wiring.py", "tests/integration/qmt_shm_package/support.py", "helpers/thread_owner.py"}
    require(required <= set(value["files"]), "test closure missing")
    for name, expected_sha in bounded(value["files"].items(), 1024, deadline):
        require(sha_file(relative(root, name, deadline), deadline) == hex64(expected_sha))
    return value
