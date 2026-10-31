"""NAC 显式来源选择；原 native.py 继续拥有执行和收据。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import qmt_readonly_fixed as fixed
from .artifact import normal_path, sha256

PROFILE = "account-scan"
SELECTION = "config/account-scan-build.json"


def _owned_path(root: Path, name: str) -> Path:
    """在同一仓根内读取规范路径；中间目录也不能重定向来源。"""
    relative = normal_path(name)
    path = root.joinpath(*relative.parts)
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("owned source escaped repository: " + name)
    current = path
    while current != root:
        information = current.lstat()
        if current.is_symlink() or getattr(information, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked owned input: " + name)
        current = current.parent
    return path


def _unique_fields(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate account scan source field")
        result[name] = value
    return result


def _selection(root: Path) -> tuple[dict, bytes]:
    path = _owned_path(root, SELECTION)
    fixed._regular(path)
    raw = path.read_bytes()
    selection = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_fields)
    required = {"schema_version", "profile", "upstream_commit", "owned_directories", "owned_files"}
    if (type(selection) is not dict or not required <= set(selection)
            or set(selection) - required - {"required_ctests", "frame_tests", "installation_roles", "installation_extras"}
            or type(selection["schema_version"]) is not int or selection["schema_version"] != 1
            or selection["profile"] != PROFILE):
        raise ValueError("invalid account scan source selection")
    if selection["upstream_commit"] != fixed.WT_COMMIT:
        raise ValueError("account scan upstream differs from fixed original WT")
    for field in ("owned_directories", "owned_files"):
        values = selection[field]
        if type(values) is not list or any(type(value) is not str for value in values):
            raise ValueError("invalid owned source paths")
        for value in values:
            normal_path(value)
        if len(values) != len({value.casefold() for value in values}):
            raise ValueError("duplicate owned source path")
    if "required_ctests" in selection:
        tests = selection["required_ctests"]
        if (type(tests) is not list or not tests or any(type(name) is not str or not name for name in tests)
                or len(tests) != len(set(tests))):
            raise ValueError("invalid required account scan tests")
    frame_tests = selection.get("frame_tests", False)
    if type(frame_tests) is not bool:
        raise ValueError("invalid frame test selection")
    tests = selection.get("required_ctests", [])
    if frame_tests != ("account-frame-io" in tests):
        raise ValueError("frame test flag and required CTest set differ")
    if "installation_roles" in selection:
        roles = selection["installation_roles"]
        if (type(roles) is not list or not roles or any(type(role) is not str for role in roles)
                or len(roles) != len(set(roles))):
            raise ValueError("invalid installation roles")
    if "installation_extras" in selection:
        extras = selection["installation_extras"]
        if ("installation_roles" not in selection or type(extras) is not dict
                or not set(extras) <= set(selection["installation_roles"])
                or any(type(values) is not list or any(type(value) is not str for value in values)
                       for values in extras.values())):
            raise ValueError("invalid installation extras")
    return selection, raw


def own_files(root: Path) -> dict:
    """组合原生/QA显式输入与安装器声明闭包，原字节共同进入快照指纹。"""
    root = root.resolve(strict=True)
    selection, selection_raw = _selection(root)
    names = set(selection["owned_files"])
    installation = {}
    if "installation_roles" in selection:
        # 延迟加载保留旧source-only配置的工具环境；依赖枚举由普通安装器唯一拥有。
        from .account_runtime_install import source_inputs
        extras = {role: tuple(values) for role, values in selection.get("installation_extras", {}).items()}
        installation = source_inputs(root, tuple(selection["installation_roles"]), extras=extras)
        names.update(installation)
    for name in selection["owned_directories"]:
        base = _owned_path(root, name)
        if not base.is_dir():
            raise ValueError("owned source directory unavailable: " + name)
        for path in base.rglob("*"):
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            relative = path.relative_to(root).as_posix()
            _owned_path(root, relative)
            if path.is_file():
                names.add(relative)
    entries, folded = {}, set()
    for name in sorted(names):
        if name.casefold() in folded:
            raise ValueError("duplicate owned source path")
        folded.add(name.casefold())
        path = _owned_path(root, name)
        fixed._regular(path)
        data = selection_raw if name == SELECTION else path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if name in installation and digest != installation[name]:
            raise ValueError("installation source changed during account scan selection: " + name)
        entries[name] = {"sha256": digest, "data": data}
    if SELECTION not in entries:
        raise ValueError("source selection must select itself")
    return entries


def prepare_inputs(root: Path, work: Path) -> dict:
    """分别冻结原 Git blob 与自有输入，来源不含旧 QMT 根目录。"""
    upstream = fixed.write_snapshot(work / "inputs/upstream", fixed.git_blobs(root, fixed.WT_COMMIT, fixed.WT_PATHS), commit=fixed.WT_COMMIT)
    owned = fixed.write_snapshot(work / "inputs/owned", own_files(root))
    current = {name: {key: value for key, value in entry.items() if key != "data"}
               for name, entry in own_files(root).items()}
    if current != owned["files"]:
        raise ValueError("account scan owned inputs changed during preparation")
    lock = sha256(root / "config/native-dependencies.json")
    if owned["files"]["config/native-dependencies.json"]["sha256"] != lock:
        raise ValueError("dependency lock changed during account scan preparation")
    identity = {"profile": PROFILE, "wt_commit": fixed.WT_COMMIT,
                "upstream": upstream, "owned": owned, "lock_sha256": lock}
    return {**identity, "input_sha256": fixed.fingerprint(identity)}


def require_identity(actual: dict, expected: dict):
    if actual != expected or actual.get("profile") != PROFILE:
        raise ValueError("account scan inputs changed; use a new work directory")



def build_options(work: Path, identity: dict) -> dict:
    """只采用本次已冻结selection原bytes；构建/CTest不再各自读取新配置。"""
    selected, raw = _selection(work / "inputs/owned")
    expected = identity["owned"]["files"][SELECTION]["sha256"]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("frozen account scan selection changed")
    if "required_ctests" not in selected:
        raise ValueError("account scan build requires explicit CTest set")
    return {"frame_tests": selected.get("frame_tests", False),
            "required_ctests": tuple(selected["required_ctests"])}


def cmake_arguments(work: Path, *, frame_tests: bool = False) -> list[str]:
    if type(frame_tests) is not bool:
        raise ValueError("invalid frame test selection")
    return ["-DGH_FIXED_UPSTREAM_ROOT=" + (work / "inputs/upstream").as_posix(),
            "-DGH_FIXED_OWN_ROOT=" + (work / "inputs/owned").as_posix(),
            "-DGH_ACCOUNT_FRAME_TESTS=" + ("ON" if frame_tests else "OFF")]
