"""Typed skill manifests, integrity checks and explicit legacy migration."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

MANIFEST = ".agents/skills/manifest.json"
LEGACY = ".agents/skills/upstream-lock.json"


def safe_path(root: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or ":" in relative or Path(relative).is_absolute()
            or any(part in {".", ".."} for part in relative.split("/"))):
        raise ValueError(f"unsafe relative path: {relative}")
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"path escapes target: {relative}")
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError(f"redirected path: {relative}")
        if current.exists():
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
                raise ValueError(f"redirected path: {relative}")
        current = current.parent
    return path


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def rows_from(data: dict, *, versioned: bool = True) -> list:
    if versioned and (type(data.get("schema_version")) is not int or data["schema_version"] != 1):
        raise ValueError("unsupported skill manifest schema; migrate explicitly")
    rows = data.get("skills")
    if not isinstance(rows, list):
        raise ValueError("skills must be an array")
    return rows


def text_field(row: dict, key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{row.get('name', 'skill')}: {key} required")
    return value


def metadata(row: dict) -> dict:
    if not isinstance(row, dict):
        raise ValueError("skill entry must be an object")
    name = text_field(row, "name")
    if (not re.fullmatch(r"[a-z0-9-]{1,64}", name)
            or re.fullmatch(r"con|prn|aux|nul|com[0-9]|lpt[0-9]", name)):
        raise ValueError(f"invalid skill name: {name}")
    kind = text_field(row, "kind")
    installed = f".agents/skills/{name}"
    if row.get("installed", installed) != installed:
        raise ValueError(f"{name}: invalid install path")
    entry = {"name": name, "kind": kind, "installed": installed}
    if kind == "local":
        for key in ("owner", "source"):
            entry[key] = text_field(row, key)
    elif kind == "upstream":
        for key in ("repository", "commit", "source_path", "license", "adaptation"):
            entry[key] = text_field(row, key)
        if not re.fullmatch(r"https://github.com/[^/\s?#]+/[^/\s?#]+", entry["repository"]):
            raise ValueError(f"{name}: original GitHub repository required")
        if not re.fullmatch(r"[0-9a-f]{40}", entry["commit"]):
            raise ValueError(f"{name}: full upstream commit required")
    else:
        raise ValueError(f"{name}: kind must be local or upstream")
    return entry


def inventory(root: Path) -> set[str]:
    directory = safe_path(root, ".agents/skills")
    if not directory.exists():
        return set()
    names = set()
    for path in directory.iterdir():
        safe_path(root, path.relative_to(root).as_posix())
        if path.is_dir():
            names.add(path.name)
    return names


def skill_files(root: Path, entry: dict) -> dict[str, str]:
    directory = safe_path(root, entry["installed"])
    if not directory.is_dir():
        raise ValueError(f"{entry['name']}: missing installed skill directory")
    files = {}
    for path in sorted(directory.rglob("*")):
        safe_path(root, path.relative_to(root).as_posix())
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            files[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if "SKILL.md" not in files:
        raise ValueError(f"{entry['name']}: missing SKILL.md")
    # Packaged references may contain other SKILL.md files; only the actual skill root is installed.
    if any(path.endswith("/SKILL.md") for path in files):
        raise ValueError(f"{entry['name']}: multiple nested SKILL.md entrypoints")
    content = (directory / "SKILL.md").read_text(encoding="utf-8-sig")
    front = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|\s*$)", content, re.S)
    if not front:
        raise ValueError(f"{entry['name']}: missing frontmatter")
    name_pattern = rf"^name:\s*[\"']?{re.escape(entry['name'])}[\"']?\s*$"
    if not re.search(name_pattern, front[1], re.M):
        raise ValueError(f"{entry['name']}: frontmatter name mismatch")
    if not re.search(r"^description:\s*\S", front[1], re.M):
        raise ValueError(f"{entry['name']}: frontmatter description required")
    return files


def validate(root: Path, data: dict, *, complete: bool = True) -> list[str]:
    errors, names = [], set()
    for row in rows_from(data):
        try:
            entry = metadata(row)
            name = entry["name"]
            if name in names:
                raise ValueError(f"duplicate skill name: {name}")
            names.add(name)
            if row.get("installed") != entry["installed"]:
                raise ValueError(f"{name}: installed required in manifest")
            actual = skill_files(root, entry)
            if entry["kind"] == "upstream":
                files = row.get("files")
                if not isinstance(files, dict) or "SKILL.md" not in files:
                    raise ValueError(f"{name}: missing SKILL.md manifest entry")
                if set(actual) != set(files):
                    errors.append(f"{name}: file set differs from manifest")
                for relative, digest in files.items():
                    safe_path(root, entry["installed"] + "/" + relative)
                    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                        errors.append(f"{name}: invalid digest {relative}")
                    elif actual.get(relative) != digest:
                        errors.append(f"{name}: hash mismatch {relative}")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(str(exc))
    if complete:
        actual_names = inventory(root)
        errors.extend(f"unregistered skill: {name}; classify with skills record" for name in sorted(actual_names - names))
        errors.extend(f"missing skill: {name}" for name in sorted(names - actual_names))
    return errors


def prepare(root: Path, source: dict) -> dict:
    entries = []
    for row in rows_from(source, versioned=False):
        entry = metadata(row)
        files = skill_files(root, entry)
        if entry["kind"] == "upstream":
            entry["files"] = files
        entries.append(entry)
    result = {"schema_version": 1, "skills": sorted(entries, key=lambda entry: entry["name"])}
    errors = validate(root, result)
    if errors:
        raise ValueError("\n".join(errors))
    return result


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, prefix=".manifest-", suffix=".tmp", delete=False) as out:
            temporary = Path(out.name)
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def record(root: Path, source_path: Path) -> dict:
    root = root.resolve()
    if safe_path(root, LEGACY).exists():
        raise ValueError("legacy lock exists; run skills migrate first")
    target = safe_path(root, MANIFEST)
    if target.exists():
        rows_from(read_json(target))
    result = prepare(root, read_json(source_path))
    atomic_json(target, result)
    return {"manifest": str(target), "skills": [entry["name"] for entry in result["skills"]]}


def migrate(root: Path) -> dict:
    root = root.resolve()
    old, target = safe_path(root, LEGACY), safe_path(root, MANIFEST)
    archive = safe_path(root, LEGACY + ".migrated")
    original = read_json(old)
    entries = []
    for row in rows_from(original):
        if not isinstance(row, dict):
            raise ValueError("legacy skill entry must be an object")
        entries.append(dict(row, kind="upstream"))
    result = {"schema_version": 1, "skills": entries}
    errors = validate(root, result, complete=False)
    if errors:
        raise ValueError("\n".join(errors))
    if archive.exists():
        raise ValueError("legacy migration archive already exists; inspect before proceeding")
    if target.exists():
        if read_json(target) != result:
            raise ValueError("manifest conflicts with legacy lock; preserve both and inspect")
    else:
        atomic_json(target, result)
    # A failed rename leaves both original and manifest; the same command resumes safely.
    old.rename(archive)
    return {"manifest": str(target), "archived": str(archive),
            "next": "update old documentation links to manifest.json; run check and classify unregistered skills"}


def check_skills(root: Path) -> list[str]:
    try:
        root = root.resolve()
        if safe_path(root, LEGACY).exists():
            return ["legacy lock exists; run skills migrate, then update documentation links"]
        return validate(root, read_json(safe_path(root, MANIFEST)))
    except (OSError, ValueError, TypeError) as exc:
        return [f"invalid skill manifest: {exc}"]
