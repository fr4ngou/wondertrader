"""Strict development artifact creation and verification (standard library only)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
import stat
import zipfile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_provenance(value: dict):
    if not isinstance(value, dict):
        raise ValueError("invalid provenance")
    for field, length in (("source_commit", 40), ("upstream_base_commit", 40), ("input_sha256", 64), ("build_cache_sha256", 64)):
        if not isinstance(value.get(field), str) or not re.fullmatch("[0-9a-f]{" + str(length) + "}", value[field]):
            raise ValueError(f"invalid provenance {field}")
    if type(value.get("source_dirty")) is not bool:
        raise ValueError("invalid provenance source_dirty")
    inputs = value.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("missing provenance inputs")
    for name, digest in inputs.items():
        normal_path(name)
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("invalid provenance input digest")
    if hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest() != value["input_sha256"]:
        raise ValueError("provenance input fingerprint mismatch")
    toolchain = value.get("toolchain")
    if not isinstance(toolchain, dict) or any(not isinstance(toolchain.get(k), str) or not toolchain[k].strip() for k in ("compiler", "cmake", "ninja")):
        raise ValueError("invalid provenance toolchain")
    if not isinstance(toolchain.get("compiler_version"), list) or not toolchain["compiler_version"] or any(not isinstance(line, str) for line in toolchain["compiler_version"]):
        raise ValueError("missing compiler version")
    if any(not isinstance(value.get(k), str) or not value[k].strip() for k in ("platform", "architecture")):
        raise ValueError("missing provenance platform")
    dependencies = value.get("dependencies")
    if not isinstance(dependencies, dict) or not isinstance(dependencies.get("dependencies"), list) or not dependencies["dependencies"]:
        raise ValueError("missing provenance dependencies")
    for dependency in dependencies["dependencies"]:
        if not isinstance(dependency, dict) or any(not isinstance(dependency.get(k), str) or not dependency[k].strip() for k in ("name", "version", "url", "license")) or not re.fullmatch("[0-9a-f]{64}", str(dependency.get("sha256", ""))):
            raise ValueError("invalid provenance dependency")
    tests = value.get("tests")
    if not isinstance(tests, dict) or any(not isinstance(tests.get(k), dict) or tests[k].get("status") != "passed" for k in ("ctest", "pipeline-tests")):
        raise ValueError("missing passing test provenance")
    profile = value.get('profile', 'native')
    if profile not in ('native', 'qmt-readonly-fixed', 'account-scan'):
        raise ValueError('unsupported artifact profile')
    if profile == 'qmt-readonly-fixed':
        fixed = value.get('fixed_sources')
        if not isinstance(fixed, dict) or set(fixed) != {'wt_commit', 'qmt_commit', 'qmt_manifest_sha256', 'identity_sha256'}:
            raise ValueError('missing fixed profile source provenance')
        for name, length in (('wt_commit', 40), ('qmt_commit', 40), ('qmt_manifest_sha256', 64), ('identity_sha256', 64)):
            if not re.fullmatch('[0-9a-f]{' + str(length) + '}', str(fixed.get(name, ''))):
                raise ValueError('invalid fixed profile source provenance')
        if fixed['wt_commit'] != '08b230dd05facf6d650d949bfe51054115a2ecb1' or fixed['qmt_commit'] != '34777db5eab144d6fe8a2f259b9f2c0de167435a':
            raise ValueError('unexpected fixed profile source commits')
    elif profile == 'account-scan':
        from .account_scan_artifact import validate_provenance as validate_account_provenance
        validate_account_provenance(value)


def validate_profile_files(files, provenance):
    if provenance.get('profile') == 'account-scan':
        from .account_scan_artifact import validate_files as validate_account_files
        validate_account_files(files, provenance)
        return
    if provenance.get('profile', 'native') != 'qmt-readonly-fixed':
        return
    required = {'app/traders/TraderQMTReadOnly.dll', 'validation/bin/NqpFixtureProbe.exe',
                'validation/bin/NqpHttpProbe.exe', 'validation/bin/NqpNoConnectProbe.exe',
                'validation/tests/integration/qmt_readonly_bootstrap/fixed_checks.py',
                'provenance/upstream-input.json', 'provenance/owned-input.json'}
    if not required.issubset(files):
        raise ValueError('fixed profile package is missing required production/validation files')
    for name in files:
        path = normal_path(name)
        if path.parts[0] not in {'app', 'validation', 'provenance', 'licenses', 'examples'}:
            raise ValueError('unexpected fixed profile package root')
        if any(part.casefold() in {'drain', 'qmt_agent', 'qmt-source', 'external-qmt'} for part in path.parts):
            raise ValueError('test DLL or controlled private source cannot be packaged')
        if path.name in {'build.py', 'source_projection.py', 'cng_lifetime.py'}:
            raise ValueError('historical build/diagnostic and local-only CNG tools cannot be packaged')
        if path.suffix.casefold() in {'.dll', '.exe'} and name not in required and not (path.parts[0] == 'app' and len(path.parts) == 2 and path.suffix.casefold() == '.dll'):
            raise ValueError('unexpected fixed profile executable')


def normal_path(value: str) -> PurePosixPath:
    if not isinstance(value, str):
        raise ValueError("artifact path must be text")
    path = PurePosixPath(value)
    reserved = {"CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(1, 10)}, *{f"LPT{i}" for i in range(1, 10)}}
    if (not value or "\\" in value or ":" in value or path.is_absolute()
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or any(part.endswith((".", " ")) or part.split(".")[0].upper() in reserved for part in path.parts)
            or any(ord(char) < 32 or char in '<>"|?*' for char in value)
            or value != path.as_posix()):
        raise ValueError(f"unsafe artifact path: {value!r}")
    return path


def regular_files(root: Path) -> dict[str, Path]:
    info = root.lstat()
    if root.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("linked artifact root")
    root = root.resolve(strict=True)
    files = {}
    for path in root.rglob("*"):
        info = path.lstat()
        # Reject directory junctions as well as file links before opening bytes.
        if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"linked artifact entry: {path.name}")
        if path.is_file():
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"non-regular artifact entry: {path.name}")
            relative = path.relative_to(root).as_posix()
            normal_path(relative)
            files[relative] = path
    return files


def write_manifest(root: Path, provenance: dict) -> dict:
    validate_provenance(provenance)
    files = regular_files(root)
    if "manifest.json" in files:
        raise ValueError("manifest already exists")
    validate_profile_files(files, provenance)
    manifest = {
        "schema_version": 1,
        "release_type": "development",
        "example": False,
        "provenance": provenance,
        "files": [{"path": name, "sha256": sha256(path), "size": path.stat().st_size}
                  for name, path in sorted(files.items())],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_directory(root: Path) -> dict:
    files = regular_files(root)
    if "manifest.json" not in files:
        raise ValueError("missing manifest")
    manifest = json.loads(files.pop("manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 1 or manifest.get("example") is not False:
        raise ValueError("invalid or example manifest")
    if manifest.get("release_type") != "development" or not isinstance(manifest.get("provenance"), dict):
        raise ValueError("unsupported artifact identity")
    validate_provenance(manifest["provenance"])
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("empty file manifest")
    expected = {}
    folded = set()
    for entry in entries:
        if not isinstance(entry, dict) or "path" not in entry:
            raise ValueError("invalid manifest file entry")
        name = normal_path(entry["path"]).as_posix()
        if name == "manifest.json" or name.casefold() in folded:
            raise ValueError(f"duplicate or reserved path: {name}")
        folded.add(name.casefold())
        expected[name] = entry
    if set(files) != set(expected):
        raise ValueError(f"file set mismatch; missing={sorted(set(expected)-set(files))}, extra={sorted(set(files)-set(expected))}")
    validate_profile_files(files, manifest['provenance'])
    for name, path in files.items():
        entry = expected[name]
        if type(entry.get("size")) is not int or path.stat().st_size != entry["size"] or sha256(path) != entry.get("sha256"):
            raise ValueError(f"artifact content mismatch: {name}")
    return manifest


def archive(root: Path, destination: Path) -> str:
    verify_directory(root)
    if destination.exists():
        raise ValueError(f"refusing to overwrite artifact: {destination}")
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for name, path in sorted(regular_files(root).items()):
            output.write(path, name)
    digest = sha256(destination)
    destination.with_suffix(destination.suffix + ".sha256").write_text(f"{digest}  {destination.name}\n", encoding="ascii")
    return digest


def verify_archive(path: Path, expected_sha256: str, destination: Path) -> dict:
    if len(expected_sha256) != 64 or sha256(path) != expected_sha256.lower():
        raise ValueError("archive checksum mismatch")
    if destination.exists():
        raise ValueError("extraction destination must be new")
    destination.mkdir(parents=True)
    with zipfile.ZipFile(path) as source:
        names = set()
        total = 0
        for entry in source.infolist():
            if entry.is_dir():
                raise ValueError("directory entries are not produced by this packager")
            name = normal_path(entry.filename).as_posix()
            if name.casefold() in names or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("duplicate or linked archive entry")
            names.add(name.casefold())
            total += entry.file_size
            if total > 2 * 1024**3 or len(names) > 10000:
                raise ValueError("artifact extraction budget exceeded")
        for entry in source.infolist():
            target = destination.joinpath(*PurePosixPath(entry.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as src, target.open("xb") as dst:
                while block := src.read(1024 * 1024):
                    dst.write(block)
    return verify_directory(destination)
