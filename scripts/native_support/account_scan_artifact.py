"""账户开发制品的专属来源与安装闭包准入；通用归档仍由 artifact 拥有。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .artifact import normal_path, regular_files, sha256
from .qmt_readonly_fixed import WT_COMMIT

REQUIRED_FILES = {
    "app/GuanhengAccountScan.exe", "app/traders/TraderQMTReadOnly.dll",
    "validation/tests/integration/native_account_scan/run.py",
    "validation/connectors/qmt/guanheng_qmt/__init__.py",
    "validation/connectors/qmt/guanheng_qmt/runtime.py",
    "validation/connectors/qmt/guanheng_qmt/http_server.py",
    "provenance/upstream-input.json", "provenance/owned-input.json", "provenance/runtime-inputs.json",
    "licenses/WonderTrader-MIT.txt",
}



# source-identity-only只证明冻结原件的安装映射，不授双环境或原生运行资格。
SCAN_SOURCE = "tests/integration/qmt_shm_account/scan"
HELPER_SOURCE = "apps/guanheng/guanheng_app/thread_owner.py"
HELPER_TARGET = "validation/helpers/thread_owner.py"
SOURCE_MANIFEST = "validation/test-sources.json"
SOURCE_SCHEMA = "qar.test-sources.v1"
SOURCE_RECORD_SCHEMA = "qar.validation-source-identity.v1"
DIRECT_SOURCES = ("tests/integration/qmt_shm_account/test_bootstrap_wiring.py",
                  "tests/integration/qmt_shm_package/support.py",
                  "tests/integration/qmt_shm_account/projection/test_projection_v3.py")
REQUIRED_TEST_SOURCES = {SCAN_SOURCE + "/" + name for name in (
    "run_schema2.py", "managed_fixture.py", "host_fixture.py", "runtime_identity.py",
    "fixture_control.py", "fixture_values.py", "case_oracles.py", "black_box_cases.py",
    "smoke_ipc.py", "registry.json", "native-main-cases.json")}
REQUIRED_TEST_SOURCES.update(DIRECT_SOURCES)
REQUIRED_TEST_SOURCES.add("helpers/thread_owner.py")
REQUIRED_TEST_SOURCES = frozenset(REQUIRED_TEST_SOURCES)
MAX_SOURCE_FILES = 1024
MAX_SOURCE_FILE_BYTES = 4 * 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 16 * 1024 * 1024
MAX_SOURCE_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_OWNED_MANIFEST_BYTES = 16 * 1024 * 1024


def _digest(value):
    return type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None


def _source_raw(path, maximum):
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("account validation source byte limit")
    return raw


def _source_json(path, maximum, expected=None):
    """同次有限bytes核身份并解析本owner的资料，避免二次读取路径套新内容。"""
    raw = _source_raw(path, maximum)
    digest = hashlib.sha256(raw).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError("account validation metadata identity changed")
    def fields(pairs):
        result = {}
        for name, item in pairs:
            if name in result:
                raise ValueError("duplicate account validation metadata field")
            result[name] = item
        return result
    def nonfinite(value):
        raise ValueError("nonfinite account validation metadata")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=fields, parse_constant=nonfinite), digest


def _source_origins(owned):
    """source清单决定scan整目录的成员；helper唯一映射到canonical App原件。"""
    if type(owned) is not dict or set(owned) != {"files"} or type(owned["files"]) is not dict:
        raise ValueError("invalid account validation owned input")
    origins = {}
    for source, entry in owned["files"].items():
        normal_path(source)
        if (type(entry) is not dict or set(entry) not in ({"sha256"}, {"sha256", "git_blob"})
                or not _digest(entry.get("sha256"))):
            raise ValueError("invalid account validation source digest")
        if source.startswith(SCAN_SOURCE + "/") or source in DIRECT_SOURCES:
            target = "validation/" + source
        elif source == HELPER_SOURCE:
            target = HELPER_TARGET
        else:
            continue
        origins[target] = {"source": source, "sha256": entry["sha256"]}
        if len(origins) > MAX_SOURCE_FILES:
            raise ValueError("account validation source count limit")
    if not {"validation/" + name for name in REQUIRED_TEST_SOURCES}.issubset(origins):
        raise ValueError("account validation required source missing")
    return origins


def _new_source_member(name):
    # Windows目录大小写别名同属保留命名空间，归档仍须匹配唯一规范拼写。
    folded = name.casefold()
    return (folded == SOURCE_MANIFEST or folded.startswith("validation/helpers/")
            or folded.startswith("validation/tests/integration/qmt_shm_account/")
            or folded.startswith("validation/tests/integration/qmt_shm_package/"))


def _check_product_overlays(files):
    # 旧格式无新来源记录也必须执行；避免兼容分支提前返回绕过产品来源边界。
    products = {"guanheng_app", "guanheng_qmt_shm", "guanheng_qmt_shm_agent"}
    for name in files:
        parts = normal_path(name).parts
        if parts[0].casefold() != "validation":
            continue
        modules = {part.casefold() for part in parts[1:]}
        leaf = parts[-1].casefold()
        if leaf.endswith((".py", ".pyi", ".pyc", ".pyd", ".so")):
            modules.add(leaf.split(".", 1)[0])
        if products.intersection(modules):
            raise ValueError("product source overlay cannot enter account validation")


def _check_installed_sources(files, origins):
    _check_product_overlays(files)
    actual = {name for name in files if _new_source_member(name) and name != SOURCE_MANIFEST}
    if actual != set(origins):
        raise ValueError("account validation source member set differs from owned input")
    total = 0
    for name, origin in origins.items():
        maximum = min(MAX_SOURCE_FILE_BYTES, MAX_SOURCE_TOTAL_BYTES - total)
        if name == HELPER_TARGET:
            maximum = min(maximum, 65536)
        raw = _source_raw(files[name], maximum)
        total += len(raw)
        if name == HELPER_TARGET and not raw:
            raise ValueError("account validation helper is empty")
        if hashlib.sha256(raw).hexdigest() != origin["sha256"]:
            raise ValueError("account validation installed bytes differ from owned source")


def _source_record(value, owned_sha):
    required = {"schema", "qualification", "role", "manifest", "manifest_sha256", "owned_manifest_sha256", "helper"}
    if (type(value) is not dict or set(value) != required or value["schema"] != SOURCE_RECORD_SCHEMA
            or value["qualification"] != "source-identity-only" or value["role"] != "test-only"
            or value["manifest"] != SOURCE_MANIFEST or not _digest(value["manifest_sha256"])
            or value["owned_manifest_sha256"] != owned_sha or not _digest(owned_sha)):
        raise ValueError("invalid account validation source provenance")
    helper = value["helper"]
    if (type(helper) is not dict or set(helper) != {"source", "target", "sha256"}
            or helper["source"] != HELPER_SOURCE or helper["target"] != HELPER_TARGET or not _digest(helper["sha256"])):
        raise ValueError("invalid account validation helper provenance")


def validate_validation_sources(files, provenance):
    """归档复核原owned-input→安装成员；旧schema1无此新命名空间时保持原准入。"""
    _check_product_overlays(files)
    present = any(_new_source_member(name) for name in files)
    if "validation_sources" not in provenance:
        if present:
            raise ValueError("account validation source provenance missing")
        return
    record = provenance["validation_sources"]
    owned_sha = provenance["fixed_sources"]["owned_manifest_sha256"]
    _source_record(record, owned_sha)
    if SOURCE_MANIFEST not in files:
        raise ValueError("account validation source manifest missing")
    # 复用通用常规文件/REPARSE准入，不另造目录扫描器；文件集须来自同一包。
    package = files["provenance/owned-input.json"].parent.parent
    actual = regular_files(package)
    actual.pop("manifest.json", None)
    if actual != files:
        raise ValueError("account validation package file map differs")
    owned, unused = _source_json(files["provenance/owned-input.json"], MAX_OWNED_MANIFEST_BYTES, owned_sha)
    origins = _source_origins(owned)
    _check_installed_sources(files, origins)
    manifest, unused = _source_json(files[SOURCE_MANIFEST], MAX_SOURCE_MANIFEST_BYTES, record["manifest_sha256"])
    expected = {name[len("validation/"):]: origin["sha256"] for name, origin in origins.items()}
    if type(manifest) is not dict or set(manifest) != {"schema", "files"} or manifest != {"schema": SOURCE_SCHEMA, "files": expected}:
        raise ValueError("account validation test manifest differs from owned input")
    if record["helper"]["sha256"] != origins[HELPER_TARGET]["sha256"]:
        raise ValueError("account validation helper source identity differs")


def record_validation_sources(package, owned_root, owned_identity):
    """安装后从同一冻结输入产生源码身份清单；不导入fixture或生成运行/安装收据。"""
    from .qmt_readonly_fixed import verify_snapshot
    verify_snapshot(owned_root, owned_identity)
    owned, owned_sha = _source_json(owned_root / "input.json", MAX_OWNED_MANIFEST_BYTES)
    if owned != owned_identity:
        raise ValueError("account validation owned identity changed")
    files = regular_files(package)
    if SOURCE_MANIFEST in files or "manifest.json" in files:
        raise ValueError("account validation source manifest already exists")
    if "provenance/owned-input.json" not in files:
        raise ValueError("account validation installed owned manifest missing")
    _source_json(files["provenance/owned-input.json"], MAX_OWNED_MANIFEST_BYTES, owned_sha)
    origins = _source_origins(owned)
    _check_installed_sources(files, origins)
    manifest = {"schema": SOURCE_SCHEMA, "files": {name[len("validation/"):]: origin["sha256"]
                for name, origin in sorted(origins.items())}}
    raw = (json.dumps(manifest, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    if len(raw) > MAX_SOURCE_MANIFEST_BYTES:
        raise ValueError("account validation source manifest byte limit")
    target = package / SOURCE_MANIFEST
    with target.open("xb") as stream:
        if stream.write(raw) != len(raw):
            raise ValueError("account validation source manifest write incomplete")
    record = {"schema": SOURCE_RECORD_SCHEMA, "qualification": "source-identity-only", "role": "test-only",
        "manifest": SOURCE_MANIFEST, "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "owned_manifest_sha256": owned_sha,
        "helper": {"source": HELPER_SOURCE, "target": HELPER_TARGET, "sha256": origins[HELPER_TARGET]["sha256"]}}
    validate_validation_sources(regular_files(package), {"fixed_sources": {"owned_manifest_sha256": owned_sha}, "validation_sources": record})
    return record


def validate_provenance(value: dict):
    source = value.get("fixed_sources")
    required = {"wt_commit", "upstream_manifest_sha256", "owned_manifest_sha256", "identity_sha256"}
    if not isinstance(source, dict) or set(source) != required or source.get("wt_commit") != WT_COMMIT:
        raise ValueError("invalid account scan fixed source provenance")
    for key in required - {"wt_commit"}:
        if not re.fullmatch("[0-9a-f]{64}", str(source.get(key, ""))):
            raise ValueError("invalid account scan source digest")
    if value.get("real_terminal_access") is not False or value.get("old_project_runtime_dependency") is not False:
        raise ValueError("account scan development package requires explicit synthetic owned-source qualification")
    if not isinstance(value.get("source_qualification"), str) or not value["source_qualification"].strip():
        raise ValueError("account scan source qualification is missing")
    if not re.fullmatch("[0-9a-f]{64}", str(value.get("runtime_inputs_sha256", ""))):
        raise ValueError("account scan runtime source evidence digest is missing")
    if "validation_sources" in value:
        _source_record(value["validation_sources"], source["owned_manifest_sha256"])
    stages = value.get("tests", {})
    if not isinstance(stages, dict) or any(not isinstance(stages.get(name), dict) or stages[name].get("status") != "passed"
            for name in ("build", "native-dependencies", "native-link-commands", "ctest", "pipeline-tests")):
        raise ValueError("account scan package requires actual build, compiler evidence and tests")


def validate_files(files: dict[str, Path], provenance: dict):
    if not REQUIRED_FILES.issubset(files):
        raise ValueError("account scan package is missing required product/owned validation files")
    for name in files:
        path = normal_path(name)
        if path.parts[0] not in {"app", "validation", "provenance", "licenses"}:
            raise ValueError("unexpected account scan package root")
        if any(part.casefold() in {"drain", "qmt_agent", "qmt_platform", "qmt-source", "external-qmt"} for part in path.parts):
            raise ValueError("legacy QMT or test gate source cannot enter account scan package")
        if path.suffix.casefold() in {".dll", ".exe"}:
            if any(token in path.name.casefold() for token in ("probe", "drain")):
                raise ValueError("test probe or gate binary cannot enter account scan package")
            runtime = path.parts[0] == "app" and len(path.parts) == 2 and path.suffix.casefold() == ".dll"
            if name not in {"app/GuanhengAccountScan.exe", "app/traders/TraderQMTReadOnly.dll"} and not runtime:
                raise ValueError("unexpected account scan executable; test probes cannot be products")
    for label in ("upstream", "owned"):
        if sha256(files["provenance/" + label + "-input.json"]) != provenance["fixed_sources"][label + "_manifest_sha256"]:
            raise ValueError("account scan installed source manifest differs from build qualification")
    if sha256(files["provenance/runtime-inputs.json"]) != provenance.get("runtime_inputs_sha256"):
        raise ValueError("account scan runtime source evidence differs from build qualification")
    validate_validation_sources(files, provenance)
