"""Build a standalone pure-Python client with the hash-pinned PEP 517 backend.

No build dependency is installed globally: flit_core runs directly from its
verified wheel in an isolated interpreter. Base runtime dependencies remain empty;
optional integrations are checked against the same explicit dependency lock.
"""
from __future__ import annotations

import argparse
from email import message_from_bytes
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import urllib.request
from uuid import uuid4
import zipfile

from native_support.process_startup import background_process_options


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config/python-build-dependencies.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def backend(work: Path, *, offline=False):
    entries = json.loads(LOCK.read_text(encoding="utf-8"))["dependencies"]
    if len(entries) != 1 or entries[0]["name"] != "flit_core":
        raise ValueError("client backend lock is unsupported")
    entry = entries[0]
    path = work / "deps" / entry["filename"]
    if not path.is_file():
        if offline:
            raise ValueError("locked client backend is missing in offline mode")
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(entry["url"], headers={"User-Agent": "GuanhengClientBuild/1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("client backend download identity mismatch")
        # Competing first builders cannot replace an existing cache entry.
        try:
            with path.open("xb") as stream:
                stream.write(data)
        except FileExistsError:
            pass
    if digest(path) != entry["sha256"]:
        raise ValueError("locked client backend was modified")
    return path


def source_inputs():
    """Enumerate an explicit distribution scope on every check, including adds."""
    declared = json.loads(LOCK.read_text(encoding="utf-8"))["client_sources"]
    if (type(declared) is not list or not declared or len(set(declared)) != len(declared)
            or any(type(name) is not str or "/" in name or "\\" in name or not name.endswith(".py")
                   or name.startswith(".") for name in declared)):
        raise ValueError("client source declaration invalid")
    package = ROOT / "integrations/guanheng_market_client"
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*")
              if p.is_file() and "__pycache__" not in p.relative_to(package).parts}
    if actual != set(declared):
        raise ValueError("client package has missing or undeclared material")
    files = [ROOT / "integrations/pyproject.toml", ROOT / "integrations/LICENSE", LOCK]
    files += [package / name for name in declared]
    if any(p.is_symlink() for p in files):
        raise ValueError("client sources must be regular owned files")
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in files}


def build_sdk(work: Path, *, output: Path | None = None, offline=False):
    work = work.resolve()
    tool = backend(work, offline=offline)
    output = (output or work / "artifacts" / uuid4().hex).resolve()
    output.mkdir(parents=True, exist_ok=False)
    temporary = work / "temp"
    temporary.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(TEMP=str(temporary), TMP=str(temporary), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    identities = source_inputs()
    code = (
        "import json,sys;sys.path.insert(0,sys.argv[1]);"
        "from flit_core.buildapi import build_wheel;"
        "print(json.dumps({'wheel':build_wheel(sys.argv[2])}))"
    )
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(tool), str(output)],
                            cwd=ROOT / "integrations", env=environment, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120, **background_process_options())
    if result.returncode:
        raise RuntimeError("isolated client build failed: " + result.stderr[-2000:])
    if identities != source_inputs():
        raise ValueError("client inputs changed during build")
    wheels = list(output.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("client build did not produce one wheel")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        source_names = {"guanheng_market_client/" + Path(name).name: ROOT / name for name in identities
                        if name.startswith("integrations/guanheng_market_client/")}
        metadata_paths = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise ValueError("client wheel metadata scope invalid")
        dist = metadata_paths[0].removesuffix("METADATA")
        generated = {dist + name for name in ("METADATA", "WHEEL", "RECORD", "licenses/LICENSE")}
        if (len(names) != len(set(names)) or set(names) != set(source_names) | generated
                or any(".." in name.split("/") or "\\" in name or ":" in name for name in names)):
            raise ValueError("client wheel contains unexpected package material")
        for name, path in source_names.items():
            if archive.read(name) != path.read_bytes():
                raise ValueError("client wheel source bytes differ from declared inputs")
        if archive.read(dist + "licenses/LICENSE") != (ROOT / "integrations/LICENSE").read_bytes():
            raise ValueError("client wheel license changed")
        optional = json.loads(LOCK.read_text(encoding="utf-8")).get("client_optional_dependencies", {})
        if (type(optional) is not dict or any(type(extra) is not str or not re.fullmatch(r"[a-z][a-z0-9-]*", extra)
                or type(requirements) is not list
                or any(type(req) is not str or not re.fullmatch(r"[a-z][a-z0-9-]*==[0-9]+(?:\.[0-9]+){1,3}", req)
                       for req in requirements) or len(requirements) != len(set(requirements))
                for extra, requirements in optional.items())):
            raise ValueError("client optional dependency declaration invalid")
        expected_requirements = {req + ';extra=="' + extra + '"'
                                 for extra, requirements in optional.items() for req in requirements}
        metadata = message_from_bytes(archive.read(metadata_paths[0]))
        actual_requirements = [req.replace(" ", "").replace("'", '"') for req in metadata.get_all("Requires-Dist", [])]
        if (metadata.get_all("Name") != ["guanheng-market-client"]
                or len(actual_requirements) != len(expected_requirements) or set(actual_requirements) != expected_requirements
                or set(metadata.get_all("Provides-Extra", [])) != set(optional)):
            raise ValueError("client wheel runtime dependency scope changed")
    receipt = {"status": "passed", "wheel": str(wheel), "sha256": digest(wheel),
               "runtime_dependencies": [], "optional_dependencies": optional,
               "inputs": identities, "backend": str(tool), "backend_sha256": digest(tool)}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=ROOT / "build/native/client-sdk")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(build_sdk(args.work, output=args.output, offline=args.offline)))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
