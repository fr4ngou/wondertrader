"""从永久Git源与五份历史角色原件重建WT 35.3.service.9 wheel。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


VERSION = "0.1.0a12+integrated.2.market.35.3.service.9"
BASE_COMMIT = "757c359b00344af8ef0cae336e65c85918637946"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact_value(raw: bytes, expected: str, label: str) -> bytes:
    """允许不同Git换行设置，最终只接受清单声明的正式原字节。"""
    candidates = (raw, raw.replace(b"\r\n", b"\n"), raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    for value in candidates:
        if digest(value) == expected:
            return value
    raise ValueError(f"source_sha256:{label}")


def committed_bytes(repository: Path, name: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"{BASE_COMMIT}:apps/wt_runtime/guanheng_wt_runtime/{name}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"base_commit_source:{name}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    closure = Path(__file__).resolve().parent
    repository = closure.parents[3]
    overlays = closure / "overlays" / "guanheng_wt_runtime"
    manifest = json.loads((closure / "SOURCE-MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "wt.runtime-source-closure.v1" or manifest.get("base_commit") != BASE_COMMIT:
        raise ValueError("source_manifest")
    if args.work.exists() or args.output.exists():
        raise FileExistsError("work_and_output_must_be_new")
    project = args.work / "project"
    package = project / "guanheng_wt_runtime"
    package.mkdir(parents=True)
    args.output.mkdir(parents=True)
    entries = manifest["modules"]
    if len(entries) != 43 or len({item["name"] for item in entries}) != 43:
        raise ValueError("module_set")
    for item in entries:
        if item["source"] == "overlay":
            source = overlays / item["name"]
            raw = exact_value(source.read_bytes(), item["sha256"], str(source))
        elif item["source"] == "base":
            raw = exact_value(committed_bytes(repository, item["name"]), item["sha256"], item["name"])
        else:
            raise ValueError(f"module_source:{item['name']}")
        (package / item["name"]).write_bytes(raw)
    shutil.copyfile(closure / "pyproject.toml", project / "pyproject.toml")
    result = subprocess.run(
        ["uv", "build", "--offline", "--wheel", "--out-dir", str(args.output), str(project)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("wheel_build_failed")
    wheels = list(args.output.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("wheel_count")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = {name for name in archive.namelist() if name.startswith("guanheng_wt_runtime/") and name.endswith(".py")}
        expected_names = {"guanheng_wt_runtime/" + item["name"] for item in entries}
        if names != expected_names:
            raise ValueError("wheel_module_set")
        for item in entries:
            if digest(archive.read("guanheng_wt_runtime/" + item["name"])) != item["sha256"]:
                raise ValueError("wheel_module_sha256")
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode("utf-8")
    required = (
        f"Version: {VERSION}",
        "Requires-Dist: guanheng-market-client==0.15.0",
        'Requires-Dist: guanheng-strategy-v1==0.1.0a8 ; extra == "execution"',
        'Requires-Dist: guanheng-strategy-native==0.1.0a1 ; extra == "execution"',
    )
    if any(line not in metadata for line in required):
        raise ValueError("wheel_metadata")
    receipt = {
        "schema": "wt.runtime-source-rebuild.v1",
        "base_commit": BASE_COMMIT,
        "version": VERSION,
        "module_count": len(entries),
        "all_module_bytes_match_deployment": True,
        "wheel": str(wheel),
        "wheel_sha256": digest(wheel.read_bytes()),
        "build_backend": "flit_core==3.12.0",
        "runtime_dependency": "guanheng-market-client==0.15.0",
        "execution_dependencies": ["guanheng-strategy-v1==0.1.0a8", "guanheng-strategy-native==0.1.0a1"],
        "python": sys.version,
    }
    receipt_path = args.output / "REBUILD-RESULT.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")), encoding="ascii")
    print(json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
