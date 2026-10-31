"""固定只读 profile 的输入快照；执行、依赖、测试和归档仍由 native.py 拥有。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

from .artifact import normal_path, sha256
from .process_startup import background_process_options

PROFILE = "qmt-readonly-fixed"
WT_COMMIT = "08b230dd05facf6d650d949bfe51054115a2ecb1"
QMT_COMMIT = "34777db5eab144d6fe8a2f259b9f2c0de167435a"
WT_PATHS = (
    "src/Includes", "src/Share", "src/FasterLibs", "src/Common",
    "src/WTSTools", "src/WTSUtils", "src/WtCore", "LICENSE",
)
QMT_PATHS = ("qmt_agent", "src/qmt_platform/common", "docs/contracts", "config")
OWN_DIRS = (
    "src/GuanhengQmtBootstrap", "src/TraderQMTReadOnly", "src/GuanhengCommon",
    "tests/integration/qmt_readonly_bootstrap", "tests/integration/qmt_http_bootstrap",
    "scripts/native_support", "cmake/native/qmt_readonly_fixed", "tests/build_pipeline",
    "integrations/guanheng_market_client",
)
OWN_FILES = (
    "scripts/native.py", "tests/integration/http/test_qmt_http.py",
    "docs/specs/native-readonly-package.md", "docs/specs/native-qmt-readonly-bootstrap.md",
    "docs/specs/native-qmt-http-bootstrap.md", "docs/specs/qmt-shared-read-transport.md",
    "config/native-dependencies.json",
    ".github/workflows/native.yml",
    "scripts/client_sdk.py", "config/python-build-dependencies.json",
    "integrations/pyproject.toml", "integrations/LICENSE",
)


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _regular(path: Path):
    info = path.lstat()
    if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400 or not stat.S_ISREG(info.st_mode):
        raise ValueError(f"linked or non-regular source: {path}")


def _git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args], input=data, stderr=subprocess.PIPE, timeout=60, **background_process_options())
    except subprocess.CalledProcessError as error:
        raise ValueError("fixed Git object unavailable or invalid") from error


def git_blobs(repo: Path, commit: str, paths: tuple[str, ...]) -> dict[str, dict]:
    """按显式路径取得原 blob 字节，独立核 Git 对象摘要，拒绝链接/子模块。"""
    if _git(repo, "cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("fixed object is not a commit")
    tree = _git(repo, "ls-tree", "-rz", commit, "--", *paths)
    entries = []
    for item in tree.split(b"\0"):
        if not item:
            continue
        metadata, name = item.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        name = name.decode("utf-8")
        normal_path(name)
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError(f"unsupported fixed source entry: {name}")
        entries.append((name, oid))
    if not entries or any(not any(name == root or name.startswith(root + "/") for name, _ in entries) for root in paths):
        raise ValueError("fixed source path missing")
    raw = _git(repo, "cat-file", "--batch", data=("\n".join(oid for _, oid in entries) + "\n").encode("ascii"))
    from io import BytesIO
    stream, result = BytesIO(raw), {}
    for name, oid in entries:
        header = stream.readline().split()
        if len(header) != 3 or header[0].decode() != oid or header[1] != b"blob":
            raise ValueError("fixed blob response mismatch")
        content = stream.read(int(header[2]))
        if stream.read(1) != b"\n" or hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest() != oid:
            raise ValueError(f"fixed blob checksum mismatch: {name}")
        result[name] = {"git_blob": oid, "sha256": hashlib.sha256(content).hexdigest(), "data": content}
    if stream.read():
        raise ValueError("extra fixed blob response")
    return result


def own_files(root: Path) -> dict[str, dict]:
    files = set(OWN_FILES)
    for relative in OWN_DIRS:
        base = root / relative
        if not base.is_dir() or base.is_symlink() or getattr(base.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError(f"owned source directory unavailable: {relative}")
        for path in base.rglob("*"):
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
                raise ValueError(f"linked owned input: {path}")
            if path.is_file():
                files.add(path.relative_to(root).as_posix())
    result = {}
    for name in sorted(files):
        normal_path(name)
        path = root / name
        _regular(path)
        content = path.read_bytes()
        result[name] = {"sha256": hashlib.sha256(content).hexdigest(), "data": content}
    return result


def write_snapshot(destination: Path, entries: dict[str, dict], *, commit: str | None = None) -> dict:
    for name in entries:
        normal_path(name)
    if "input.json" in entries:
        raise ValueError("reserved snapshot manifest path")
    manifest = {"files": {name: {key: value for key, value in item.items() if key != "data"} for name, item in sorted(entries.items())}}
    if commit:
        manifest["commit"] = commit
    if destination.exists():
        verify_snapshot(destination, manifest)
        return manifest
    destination.mkdir(parents=True)
    for name, item in entries.items():
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item["data"])
    (destination / "input.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    verify_snapshot(destination, manifest)
    return manifest


def verify_snapshot(root: Path, expected: dict | None = None) -> dict:
    from .artifact import regular_files
    files = regular_files(root)
    if "input.json" not in files:
        raise ValueError("snapshot manifest missing")
    manifest = json.loads(files.pop("input.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict) or not manifest["files"]:
        raise ValueError("invalid snapshot manifest")
    if "commit" in manifest and not re.fullmatch("[0-9a-f]{40}", str(manifest["commit"])):
        raise ValueError("invalid snapshot commit")
    for name, entry in manifest["files"].items():
        normal_path(name)
        if not isinstance(entry, dict) or set(entry) not in ({"sha256"}, {"sha256", "git_blob"}):
            raise ValueError("invalid snapshot file identity")
        for key, size in (("sha256", 64), ("git_blob", 40)):
            if key in entry and not re.fullmatch("[0-9a-f]{" + str(size) + "}", str(entry[key])):
                raise ValueError("invalid snapshot file digest")
    if expected is not None and manifest != expected:
        raise ValueError("snapshot identity changed; use a new work directory")
    if set(files) != set(manifest["files"]):
        raise ValueError("snapshot file set changed")
    for name, path in files.items():
        entry = manifest["files"][name]
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(f"snapshot content changed: {name}")
        if "git_blob" in entry and hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest() != entry["git_blob"]:
            raise ValueError(f"snapshot Git blob changed: {name}")
    return manifest


def prepare_inputs(root: Path, work: Path, *, qmt_source: Path | None = None, require_qmt: bool = False) -> dict:
    """创建或严格复核独占快照；外部 QMT 源只留在 work，调用者禁止安装它。"""
    if require_qmt and qmt_source is None:
        raise ValueError("qmt-readonly-fixed requires an explicit controlled --qmt-source")
    upstream = write_snapshot(work / "inputs/upstream", git_blobs(root, WT_COMMIT, WT_PATHS), commit=WT_COMMIT)
    owned = write_snapshot(work / "inputs/owned", own_files(root))
    qmt = write_snapshot(work / "inputs/qmt", git_blobs(qmt_source, QMT_COMMIT, QMT_PATHS), commit=QMT_COMMIT) if qmt_source else None
    current_owned = {name: {key: value for key, value in item.items() if key != "data"}
                     for name, item in own_files(root).items()}
    if current_owned != owned["files"]:
        raise ValueError("owned inputs changed during snapshot preparation")
    lock_digest = sha256(root / "config/native-dependencies.json")
    if owned["files"]["config/native-dependencies.json"]["sha256"] != lock_digest:
        raise ValueError("dependency lock changed during snapshot preparation")
    identity = {"profile": PROFILE, "wt_commit": WT_COMMIT, "qmt_commit": QMT_COMMIT,
                "upstream": upstream, "owned": owned, "qmt": qmt,
                "lock_sha256": lock_digest}
    return {**identity, "input_sha256": fingerprint(identity)}


def require_identity(actual: dict, expected: dict):
    if actual != expected or actual.get("profile") != PROFILE:
        raise ValueError("fixed profile inputs changed; configure and rebuild in a new work directory")


def cmake_arguments(work: Path) -> list[str]:
    # Untyped -D strings are embedded by install(DIRECTORY). Forward slashes
    # preserve literal Windows paths when CMake writes its install script.
    return ["-DGH_FIXED_UPSTREAM_ROOT=" + (work / "inputs/upstream").as_posix(),
            "-DGH_FIXED_OWN_ROOT=" + (work / "inputs/owned").as_posix(),
            "-DGH_FIXED_QMT_ROOT=" + (work / "inputs/qmt").as_posix()]


def claim_work(work: Path, profile: str):
    """Reject cross-profile reuse before replacing any previous receipt/cache."""
    marker = work / 'profile.json'
    if marker.exists():
        if json.loads(marker.read_text(encoding='utf-8')) != {'profile': profile}:
            raise ValueError('work directory belongs to another profile')
    elif profile != 'native' and any((work / name).exists() for name in ('cmake/CMakeCache.txt', 'configured.json', 'built-source.json')):
        raise ValueError('existing unmarked work belongs to native; use a new work directory')
    else:
        work.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({'profile': profile}) + '\n', encoding='utf-8')


def source_identity(root: Path, identity: dict) -> dict:
    inputs = {prefix + '/' + name: item['sha256']
              for prefix in ('upstream', 'owned', 'qmt') if identity.get(prefix)
              for name, item in identity[prefix]['files'].items()}
    return {'source_commit': _git(root, 'rev-parse', 'HEAD').decode().strip(),
            'source_dirty': bool(_git(root, 'status', '--porcelain').strip()),
            'inputs': inputs, 'input_sha256': fingerprint(inputs)}
