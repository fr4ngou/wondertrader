"""ATI双角色普通安装装配；只通过调用方run执行有限命令，不拥有子进程。

工具解释器须为本仓已验证且有pip的Windows CPython3.12。run必须在外层
Job及私有隐藏console中执行（pip/uv可能再启解释器），控制TEMP/TMP、输出和
总期限；本模块不Popen、不修改宿主环境、不上传包。每个命令还有独立有限上限。
root须包含本工具及固定QA来源。旧冻结树缺工具时，调用方另复制安装专用输入树，
仅加入本工具并单独记录新树身份；产品包原字节保持，旧冻结原件保持。
"""
from __future__ import annotations

import argparse
import ast
import base64
import csv
from email.parser import BytesParser
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
import sysconfig
import time
import tomllib
import zipfile

ROLE_ROOTS = {"app": "apps/guanheng", "host": "connectors/qmt_shm/host",
              "wt": "apps/wt_runtime"}
ROLE_MODULES = {
    "app": ("guanheng_app", "guanheng_app.strategy_job", "guanheng_app.thread_owner", "pydantic"),
    "host": ("guanheng_qmt_shm", "guanheng_qmt_shm.bootstrap", "guanheng_qmt_shm.server",
             "guanheng_qmt_shm_agent", "guanheng_qmt_shm_agent.restricted", "pydantic"),
    "wt": ("guanheng_wt_runtime", "guanheng_wt_runtime.runtime"),
}
MAX_LOCAL_PROJECTS = 16


def _roles(roles):
    # 角色按发行声明的稳定顺序选择；WT可与Host独立安装，App仍沿原默认选择。
    _require(type(roles) is tuple and bool(roles)
             and roles == tuple(role for role in ROLE_ROOTS if role in roles),
             "explicit ordered installation roles required")


def _selected_extras(roles, extras):
    _roles(roles)
    extras = {} if extras is None else extras
    _require(type(extras) is dict and set(extras) <= set(roles), 'explicit extra roles')
    selected = {}
    for role in roles:
        values = extras.get(role, ())
        _require(type(values) in (tuple, list) and len(values) <= 64, 'explicit role extras')
        _require(all(type(value) is str and len(value) <= 128 for value in values), 'explicit extra name')
        normalized = tuple(sorted(_name(value) for value in values))
        _require(len(set(normalized)) == len(normalized), 'duplicate normalized extra')
        selected[role] = normalized
    return selected


def _dependencies(project, extras=()):
    dependencies = project['dependencies']
    _require(type(dependencies) is list and len(dependencies) <= 1024, 'declared dependency capacity')
    optional = project.get('optional_dependencies', {})
    _require(type(optional) is dict and len(optional) <= 256, 'optional dependency declarations')
    groups = {}
    for key, requirements in optional.items():
        name = _name(key)
        _require(name not in groups, 'duplicate normalized optional dependency')
        groups[name] = requirements
    result = list(dependencies)
    for name in extras:
        _require(name in groups and type(groups[name]) is list, 'undeclared project extra')
        result.extend(groups[name])
    _require(len(result) <= 1024, 'selected dependency capacity')
    return result


def _dependency_name(requirement):
    _require(type(requirement) is str and len(requirement) <= 4096
             and '\n' not in requirement and '\r' not in requirement, 'declared dependency')
    match = re.match('('+_NAME+r')(?=\s|[<>=!~;\[@]|$)', requirement)
    _require(match is not None, 'named dependency required')
    return _name(match[1])


def _role_projects(root, roles, local_sources=None, extras=None):
    """角色根声明拥有选择；原锁/显式调用方映射只补充旧输入缺失的来源。"""
    _roles(roles)
    extra_selection = _selected_extras(roles, extras)
    local_sources = {} if local_sources is None else local_sources
    _require(type(local_sources) is dict and set(local_sources) <= set(roles), "local source roles")
    plans, all_projects = {}, {}
    for role in roles:
        relative = ROLE_ROOTS[role]
        entry = _project(root, relative)
        directory = entry['directory']
        document = tomllib.loads(_read(directory/'pyproject.toml').decode('utf-8'))
        declarations = document.get('tool', {}).get('uv', {}).get('sources', {})
        _require(type(declarations) is dict and len(declarations) <= 256, 'local source declarations')
        sources, seen_declarations = {}, set()

        def retain(name, value):
            name = _name(name)
            _require(type(value) is str and value and len(value) <= 1024
                     and not Path(value).is_absolute() and not Path(value).drive,
                     'relative local source required')
            lexical = directory/value
            path = _within(root, lexical, strict=False)
            _require(name not in sources or sources[name][1] == path, 'conflicting local source')
            sources[name] = (lexical, path)

        # 只解释path来源；registry/git/workspace等声明在实际依赖被选择时明确拒绝。
        for name, value in declarations.items():
            normalized = _name(name)
            _require(normalized not in seen_declarations, 'duplicate normalized local source')
            seen_declarations.add(normalized)
            if type(value) is dict and set(value) <= {'path', 'editable'} and 'path' in value:
                _require('editable' not in value or type(value['editable']) is bool, 'local editable declaration')
                retain(name, value['path'])
        lock = directory/'uv.lock'
        if lock.exists():
            locked = tomllib.loads(_read(lock).decode('utf-8'))
            packages = locked.get('package', [])
            _require(type(packages) is list and len(packages) <= 1024, 'locked package capacity')
            for package in packages:
                source = package.get('source', {})
                if type(source) is dict and len(source) == 1 and next(iter(source), None) in ('directory', 'editable'):
                    if _name(package['name']) != entry['name']:
                        retain(package['name'], next(iter(source.values())))
        overrides = local_sources.get(role, {})
        _require(type(overrides) is dict and len(overrides) <= 256, 'explicit local source declarations')
        for name, value in overrides.items():
            retain(name, value)
        selected, visiting = [], set()

        def visit(project):
            name = project['name']
            previous = all_projects.get(name)
            _require(previous is None or previous['directory'] == project['directory'], 'local distribution collision')
            all_projects[name] = project
            _require(len(all_projects) <= MAX_LOCAL_PROJECTS, 'local project capacity')
            if name in visiting:
                return
            visiting.add(name)
            selected.append(project['relative'])
            dependencies = _dependencies(project, extra_selection[role] if project['relative'] == relative else ())
            for requirement in dependencies:
                dependency = _dependency_name(requirement)
                if dependency in sources:
                    pinned = re.fullmatch('('+_NAME+r')\s*==\s*('+_VERSION+')', requirement)
                    _require(pinned is not None, 'plain exact local dependency required')
                    target = _within(root, sources[dependency][0])
                    child = _project(root, target.relative_to(root).as_posix())
                    _require(child['name'] == dependency and child['version'] == pinned[2], 'local dependency identity')
                    visit(child)
                else:
                    _require(dependency not in seen_declarations and not dependency.startswith('guanheng-'),
                             'declared private dependency has no local path source')
        visit(entry)
        if role == 'wt':
            _require(all(project['module'] != 'guanheng_app' and project['name'] != 'guanheng-app'
                         for project in all_projects.values() if project['relative'] in selected),
                     'WT role must be independent of observer')
        plans[role] = tuple(selected)
    return plans


def selected_projects(root, roles, local_sources=None, extras=None):
    """显式角色所需本地闭包，跨角色公共源只构建一次。"""
    _unlinked(root)
    plans = _role_projects(root.resolve(strict=True), roles, local_sources, extras)
    return tuple(dict.fromkeys(path for role in roles for path in plans[role]))
MAX_FILES, MAX_FILE, MAX_RECEIPT = 20000, 256 * 1024 * 1024, 4 * 1024 * 1024
_NAME = r"[A-Za-z0-9][A-Za-z0-9._-]*"
_VERSION = r"[A-Za-z0-9][A-Za-z0-9.!+_-]*"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _name(value):
    _require(type(value) is str and re.fullmatch(_NAME, value) is not None, "distribution name")
    return re.sub(r"[-_.]+", "-", value).lower()


def _regular(path):
    info = path.lstat()
    _require(not path.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400
             and stat.S_ISREG(info.st_mode), "regular input required")
    return info


def _read(path, maximum=MAX_RECEIPT):
    _require(_regular(path).st_size <= maximum, "file capacity")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    _require(len(raw) <= maximum, "file capacity")
    return raw


def _sha(path, maximum=MAX_FILE):
    _require(_regular(path).st_size <= maximum, "file capacity")
    value, used = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            used += len(block)
            _require(used <= maximum, "file capacity")
            value.update(block)
    return value.hexdigest()


def _json_write(path, value):
    raw = (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    _require(len(raw) <= MAX_RECEIPT, "JSON capacity")
    with path.open("xb") as stream:
        _require(stream.write(raw) == len(raw), "short JSON write")


def _unlinked(path, *, allow_missing=False):
    """在resolve丢失别名身份之前，逐级检查调用者提供的真实词法路径。"""
    _require(path.is_absolute(), 'absolute source path required')
    current = None
    for part in path.parts:
        current = Path(part) if current is None else current/part
        _require(not current.is_symlink(), 'linked/reparse source path')
        try:
            info = current.lstat()
        except FileNotFoundError:
            if allow_missing:
                continue
            raise
        _require(not getattr(info, 'st_file_attributes', 0) & 0x400, 'linked/reparse source path')


def _within(root, path, *, strict=True):
    _unlinked(path, allow_missing=not strict)
    result = path.resolve(strict=strict)
    _require(result.is_relative_to(root), "path outside owned root")
    return result


def _module_files(directory):
    result, pending, visited = [], [directory], 0
    while pending:
        current = pending.pop()
        for path in sorted(current.iterdir()):
            visited += 1
            _require(visited <= MAX_FILES, "source member capacity")
            info = path.lstat()
            _require(not path.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400,
                     "source reparse member")
            if stat.S_ISDIR(info.st_mode):
                if path.name != "__pycache__":
                    pending.append(path)
            else:
                _regular(path)
                if path.suffix != ".pyc":
                    result.append(path)
    return result


def _project(root, relative):
    directory = _within(root, root / relative)
    data = tomllib.loads(_read(directory / "pyproject.toml").decode("utf-8"))
    build = data["build-system"]
    _require(build == {"requires": ["flit_core==3.12.0"], "build-backend": "flit_core.buildapi"},
             "unsupported build backend")
    project, flit = data["project"], data["tool"]["flit"]
    _require("Private :: Do Not Upload" in project.get("classifiers", []), "private wheel required")
    _require("external-data" not in flit, "external build data needs explicit source contract")
    module = flit["module"]["name"]
    _require(type(module) is str and module.isidentifier(), "module scope")
    package = directory / module
    entry = package / "__init__.py"
    _require(package.is_dir(), "ordinary package required")
    version = project.get("version")
    if version is None:
        _require(project.get("dynamic") == ["version"], "dynamic version scope")
        tree = ast.parse(_read(entry).decode("utf-8"))
        values = [node.value.value for node in tree.body
                  if isinstance(node, ast.Assign) and len(node.targets) == 1
                  and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "__version__"
                  and isinstance(node.value, ast.Constant) and type(node.value.value) is str]
        _require(len(values) == 1, "literal declared dynamic version required")
        version = values[0]
    _require(type(version) is str and len(version) <= 128 and re.fullmatch(_VERSION, version),
             "project version")
    files = [directory / "pyproject.toml", *_module_files(package)]
    readme = project.get("readme")
    if readme:
        files.append(_within(root, directory / (readme if type(readme) is str else readme["file"])))
    # Flit默认license候选与本仓显式license-files均在项目根，不能漏出源码身份。
    patterns = project.get("license-files", ["LICENSE*", "COPYING*"])
    for pattern in patterns:
        _require(type(pattern) is str and "/" not in pattern and "\\" not in pattern, "license scope")
        files.extend(directory.glob(pattern))
    return {"name": _name(project["name"]), "version": version, "module": module,
            "relative": relative, "directory": directory, "package": package,
            "dependencies": project.get("dependencies", []),
            'optional_dependencies': project.get('optional-dependencies', {}), "files": sorted(set(files))}


def _inputs(root, projects):
    paths = {path for project in projects
             for path in _project(root, project["relative"])["files"]}
    paths.update(root / path for path in (
        "config/python-build-dependencies.json",
        "tests/integration/qmt_shm_account/scan/runtime_identity.py",
        "tests/integration/qmt_shm_account/scan/fixture_control.py",
        "scripts/native_support/account_runtime_install.py"))
    for role, relative in ROLE_ROOTS.items():
        lock = root/relative/'uv.lock'
        if any(project['relative'] == relative for project in projects) and (role == 'app' or lock.exists()):
            paths.add(lock)
    _require(len(paths) <= MAX_FILES, "source file capacity")
    return {path.relative_to(root).as_posix(): _sha(_within(root, path)) for path in sorted(paths)}


def source_inputs(root: Path, roles, *, extras=None, local_sources=None) -> dict[str, str]:
    """只读选择与原普通安装完全相同的源输入，返回仓库相对路径和原字节SHA。"""
    _require(root.is_absolute(), 'absolute source root required')
    _unlinked(root)
    root = root.resolve(strict=True)
    plans = _role_projects(root, roles, local_sources, extras)
    paths = tuple(dict.fromkeys(path for role in roles for path in plans[role]))
    inputs = _inputs(root, [_project(root, path) for path in paths])
    _require(_role_projects(root, roles, local_sources, extras) == plans, 'local selection changed')
    return inputs


def _requirements(raw, *, allow_empty=False):
    """只校hash requirements的装配域；marker选择和Requires-Dist解析归标准工具。"""
    _require(type(raw) is bytes and len(raw) <= MAX_RECEIPT, "requirements capacity")
    result, pending = [], ""
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pending += " " + (line[:-1] if line.endswith("\\") else line)
        _require(len(pending) <= 65536, "requirement line capacity")
        if line.endswith("\\"):
            continue
        hashes = re.findall(r"\s+--hash=sha256:([0-9a-f]{64})(?=\s|$)", pending)
        body = re.sub(r"\s+--hash=sha256:[0-9a-f]{64}(?=\s|$)", "", pending).strip()
        match = re.fullmatch('(?P<name>'+_NAME+r')(?:\[(?P<extras>'+_NAME+r'(?:,'+_NAME+r')*)\])?==(?P<version>'
                             +_VERSION+r')(?:\s*;\s*([^\\\r\n]+))?', body)
        _require(match is not None and hashes and "--" not in body and "@" not in body,
                 "exact hashed registry requirement required")
        result.append({"name": _name(match['name']), "version": match['version'], "hashes": set(hashes),
                       'extras': tuple(_name(value) for value in (match['extras'] or '').split(',') if value)})
        pending = ""
        _require(len(result) <= 256, "requirement count")
    _require(not pending and (result or allow_empty), "complete nonempty requirements required")
    return result


def _role_lock(registry_raw, private, extras=None):
    registry = _requirements(registry_raw, allow_empty=True)
    _require(not any(item["name"] in private for item in registry), "private requirement in registry lock")
    lines = []
    extras = {} if extras is None else extras
    _require(type(extras) is dict and set(extras) <= set(private), 'private extra selection')
    for name, info in sorted(private.items()):
        _require(_name(name) == name and re.fullmatch(_VERSION, info["version"])
                 and re.fullmatch("[0-9a-f]{64}", info["sha256"]), "private requirement identity")
        selected = extras.get(name, ())
        _require(type(selected) is tuple and len(set(selected)) == len(selected)
                 and all(_name(value) == value for value in selected), 'private extra identity')
        target = name + ('['+','.join(selected)+']' if selected else '')
        lines.append(target + "==" + info["version"] + " --hash=sha256:" + info["sha256"])
    raw = registry_raw.rstrip() + b"\n" + ("\n".join(lines) + "\n").encode()
    _requirements(raw)
    _require(len(raw) <= MAX_RECEIPT, "role lock capacity")
    return raw


def _wheel_info(path, project=None):
    _regular(path)
    _require(path.suffix == ".whl" and path.stat().st_size <= MAX_FILE, "wheel capacity")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        _require(0 < len(entries) <= MAX_FILES, "wheel members")
        names = [item.filename for item in entries]
        _require(len(names) == len(set(names)), "duplicate wheel member")
        total = 0
        for item in entries:
            part = item.filename.rstrip("/")
            _require(part and "\\" not in part and ":" not in part and not part.startswith("/")
                     and all(v not in ("", ".", "..") for v in part.split("/")), "wheel path")
            _require(not stat.S_ISLNK(item.external_attr >> 16), "wheel link")
            total += item.file_size
            _require(item.file_size <= MAX_FILE and total <= MAX_FILE, "expanded wheel capacity")
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        _require(len(metadata_paths) == 1, "wheel METADATA")
        _require(archive.getinfo(metadata_paths[0]).file_size <= 1048576, "METADATA capacity")
        metadata_raw = archive.read(metadata_paths[0])
        _require(len(metadata_raw) <= 1048576, "METADATA capacity")
        prepared_sha256 = None
        metadata = BytesParser().parsebytes(metadata_raw)
        name, version = _name(metadata["Name"]), metadata["Version"]
        requires = metadata.get_all("Requires-Dist", [])
        _require(type(version) is str and len(version) <= 256 and len(requires) <= 1024,
                 "wheel metadata fields")
        if project is not None:
            _require((name, version) == (project["name"], project["version"]), "built wheel version")
            expected = {p.relative_to(project["directory"]).as_posix(): p for p in project["files"]
                        if p.is_relative_to(project["package"])}
            actual = {n for n in names if n.startswith(project["module"] + "/") and not n.endswith("/")}
            _require(actual == set(expected), "built wheel module scope")
            for member, source in expected.items():
                _require(archive.read(member) == _read(source, MAX_FILE), "built wheel source bytes")
            prepared = project.get("prepared_metadata")
            if prepared is not None:
                prepared_raw = _read(prepared, 1048576)
                prepared_metadata = BytesParser().parsebytes(prepared_raw)
                # Flit的普通文件与ZIP输出可分别采用CRLF/LF；只归一换行，完整正文仍相等。
                fields = ("Name", "Version", "Requires-Dist")
                _require(all(prepared_metadata.get_all(field, []) == metadata.get_all(field, [])
                             for field in fields)
                         and prepared_raw.replace(b"\r\n", b"\n") == metadata_raw.replace(b"\r\n", b"\n"),
                         "prepared Requires-Dist metadata drift")
                prepared_sha256 = hashlib.sha256(prepared_raw).hexdigest()
    return {"name": name, "version": version, "requires_dist": requires,
            "metadata_raw": metadata_raw, "metadata_sha256": hashlib.sha256(metadata_raw).hexdigest(),
            "prepared_metadata_sha256": prepared_sha256, "sha256": _sha(path), "path": path}


def _wheelhouse(directory, registry, private):
    """仅接纳hash锁中的公开轮子及本次Flit私有轮子；完整依赖由安装器再核。"""
    allowed = {}
    for item in registry:
        allowed.setdefault((item["name"], item["version"]), set()).update(item["hashes"])
    found = {}
    for path in sorted(directory.iterdir()):
        info = _wheel_info(path)
        _require(info["name"] not in found, "duplicate wheel distribution")
        if info["name"] in private:
            original = private[info["name"]]
            _require((info["version"], info["sha256"]) == (original["version"], original["sha256"]),
                     "private wheel identity")
            info["prepared_metadata_sha256"] = original.get("prepared_metadata_sha256")
        else:
            _require(info["sha256"] in allowed.get((info["name"], info["version"]), set()),
                     "wheel outside hash lock")
        found[info["name"]] = info
    _require(set(private) <= set(found) and len(found) <= 256, "private wheel missing")
    return found


def _installed_records(root, site, distributions, wheels):
    """从普通安装的公开Distribution/RECORD取事实，不自行推导依赖满足关系。"""
    found, files, owners = [], {}, {}
    seen = set()

    def retain(path):
        _require(path.is_relative_to(root), "installed path outside role")
        digest = _sha(path)
        key = path.relative_to(root).as_posix()
        _require(key not in files or files[key] == digest, "installed file drift")
        files[key] = digest
        _require(len(files) <= MAX_FILES, "installed file count")
        return digest

    for number, dist in enumerate(distributions, 1):
        _require(number <= 256, "distribution count")
        name, version = _name(dist.metadata["Name"]), dist.metadata["Version"]
        _require(name in wheels and name not in seen, "extra or duplicate installed distribution")
        seen.add(name)
        wheel = wheels[name]
        requires = dist.metadata.get_all("Requires-Dist", [])
        _require((version, requires) == (wheel["version"], wheel["requires_dist"]),
                 "installed Requires-Dist or version mismatch")
        locations = set()
        for index, item in enumerate(dist.files or (), 1):
            _require(index <= MAX_FILES, "RECORD public member count")
            locations.add(Path(dist.locate_file(item)).resolve(strict=True))
        metadata = [p for p in locations if p.name == "METADATA" and p.parent.name.endswith(".dist-info")]
        records = [p for p in locations if p.name == "RECORD" and p.parent.name.endswith(".dist-info")]
        _require(len(metadata) == len(records) == 1 and metadata[0].parent == records[0].parent,
                 "actual distribution metadata binding")
        meta, record = metadata[0], records[0]
        _require(meta.is_relative_to(site) and _read(meta, 1048576) == wheel["metadata_raw"],
                 "installed METADATA differs from wheel")
        retain(meta); retain(record)
        rows = csv.reader(_read(record).decode("utf-8").splitlines())
        row_locations = set()
        for index, row in enumerate(rows, 1):
            _require(index <= MAX_FILES and len(row) == 3, "RECORD shape")
            path = (site / row[0]).resolve(strict=True)
            _require(path.is_relative_to(root), "RECORD path escape")
            row_locations.add(path)
            if not row[1]:
                _require(path == record or path.suffix == ".pyc", "unhashed installed source")
                continue
            _require(row[1].startswith("sha256="), "unsupported RECORD hash")
            digest = retain(path)
            _require(base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b"=").decode() == row[1][7:],
                     "installed RECORD digest")
            if row[2]:
                _require(row[2].isdigit() and int(row[2]) == path.stat().st_size, "installed RECORD size")
            owners.setdefault(path, set()).add(name)
        _require(row_locations == locations, "public RECORD membership drift")
        found.append({"name": name, "version": version, "metadata": meta.relative_to(root).as_posix(),
                      "record": record.relative_to(root).as_posix(), "requires_dist": requires})
    _require(seen == set(wheels), "missing installed distribution")
    return found, files, owners


def _emit_runtime(root, role, qa):
    """仅由所属-I -B角色解释器调用；标准库采集后交唯一QA validator准入。"""
    _require(role in ROLE_MODULES and os.name == "nt" and sys.implementation.name == "cpython"
             and sys.version_info[:2] == (3, 12) and struct.calcsize("P") == 8, "CPython312 Windows64 required")
    _require(sys.flags.isolated and sys.flags.dont_write_bytecode and not sys.flags.no_site,
             "ordinary isolated site required")
    root, qa = root.resolve(strict=True), qa.resolve(strict=True)
    prefix, site = Path(sys.prefix).resolve(), Path(sysconfig.get_path("purelib")).resolve()
    _require(prefix == root / "venv" and site.is_relative_to(prefix), "role prefix binding")
    check = json.loads(_read(root / "pip-check.json").decode())
    _require(check.get("status") == "passed" and check.get("role") == role, "standard pip check required")
    wheels = {}
    for path in sorted((root / "wheels").iterdir()):
        info = _wheel_info(path)
        _require(info["name"] not in wheels, "duplicate role wheel")
        wheels[info["name"]] = info
    _require(1 <= len(wheels) <= 256, "role wheels")
    distributions, files, owners = _installed_records(
        root, site, importlib.metadata.distributions(path=[str(site)]), wheels)
    names = ROLE_MODULES[role]
    local = json.loads(_read(root/'local-projects.json').decode())
    _require(local['role'] == role and type(local['projects']) is list
             and 1 <= len(local['projects']) <= MAX_LOCAL_PROJECTS, 'installed local project declaration')
    declared_modules = {}
    for project in local['projects']:
        _require(project['name'] in wheels and wheels[project['name']]['version'] == project['version']
                 and type(project['module']) is str and project['module'].isidentifier()
                 and project['module'] not in declared_modules, 'installed local project identity')
        declared_modules[project['module']] = project['name']
    modules = {}
    for name in names:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve(strict=True)
        _require(path.is_relative_to(site) and len(owners.get(path, ())) == 1, "role module owner")
        modules[name] = path.relative_to(root).as_posix()
    local_imports = {}
    for name, owner in declared_modules.items():
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve(strict=True)
        _require(path.is_relative_to(site) and owners.get(path) == {owner}, 'declared local module owner')
        local_imports[name] = path.relative_to(root).as_posix()
    _json_write(root/'local-imports.json', dict(role=role, modules=local_imports, extras=local['extras']))
    executable, base = Path(sys.executable).resolve(), Path(sys._base_executable).resolve(strict=True)
    extras = [executable, prefix / "pyvenv.cfg", root / "requirements.lock", root / "pip-check.json",
              root/'local-projects.json', root/'local-imports.json',
              *sorted((root / "wheels").iterdir())]
    for path in extras:
        _require(path.is_relative_to(root), "receipt extra path")
        files[path.relative_to(root).as_posix()] = _sha(path)
    _require(len(files) <= MAX_FILES, "receipt file count")
    value = {"schema": "qar.test-runtime.v1", "role": role, "root": str(root), "prefix": "venv",
             "executable": executable.relative_to(root).as_posix(), "site": site.relative_to(root).as_posix(),
             "base_executable": str(base), "base_sha256": _sha(base), "version": [3, 12], "bits": 64,
             "venv_cfg": (prefix / "pyvenv.cfg").relative_to(root).as_posix(), "files": files,
             "modules": modules, "distributions": distributions, "lock": "requirements.lock",
             "wheels": [p.relative_to(root).as_posix() for p in sorted((root / "wheels").iterdir())],
             "pip_check": True}
    output = root / "runtime-receipt.json"
    _json_write(output, value)
    # 只有两个固定标准库QA模块；绝不把App/Host源树放到sys.path。
    sys.path.insert(0, str(qa))
    identity = importlib.import_module("runtime_identity")
    deadline = time.monotonic() + 120
    admitted = identity.admit(output, role, deadline)
    identity.check_current(admitted, deadline)


_BUILD = """import os,sys,tempfile
from pathlib import Path
backend,out,metadata,temporary=map(Path,sys.argv[1:])
os.environ['TEMP']=os.environ['TMP']=str(temporary)
tempfile.tempdir=str(temporary)
sys.path.insert(0,str(backend))
from flit_core.buildapi import prepare_metadata_for_build_wheel,build_wheel
name=prepare_metadata_for_build_wheel(str(metadata))
build_wheel(str(out),metadata_directory=str(metadata/name))
"""


def prepare(root: Path, work: Path, python: Path, uv: Path, backend: Path, run,
            *, offline=False, wheel_cache_dirs=(), roles=("app", "host"), local_sources=None, extras=None) -> dict:
    """构建/下载/普通离线安装两角色；失败保留fresh工作原件，不发布半完成安装。

    root是含本工具的完整专用输入树；不向已冻结旧树补文件。work须为不存在的绝对路径。
    run(argv, *, cwd, log, timeout)必须失败即抛错，并由调用方配置私有隐藏console、
    Job、TEMP/TMP及输出/总预算。每个外部命令有有限timeout；本模块不创建进程。
    """
    _require(type(offline) is bool and callable(run), "explicit installer options")
    _require(root.is_absolute(), "absolute source root required")
    _unlinked(root)
    root = root.resolve(strict=True)
    _require(work.is_absolute() and not work.exists(), "fresh absolute work required")
    work = work.resolve()
    _require(len(wheel_cache_dirs) <= 16, "cache directory count")
    caches = [Path(path).resolve(strict=True) for path in wheel_cache_dirs]
    _require(all(path.is_dir() for path in caches), "wheel cache directory")
    for path in (python, uv, backend):
        _require(path.is_absolute(), "absolute tool required"); _regular(path)
    local_sources = None if local_sources is None else json.loads(json.dumps(local_sources, allow_nan=False))
    extra_selection = _selected_extras(roles, extras)
    plans = _role_projects(root, roles, local_sources, extra_selection)
    selection = tuple(dict.fromkeys(path for role in roles for path in plans[role]))
    projects = [_project(root, path) for path in selection]
    _require(len({p["name"] for p in projects}) == len(selection), "local distribution collision")
    local_names = {p["name"] for p in projects}
    inputs = source_inputs(root, roles, extras=extra_selection, local_sources=local_sources)
    _require(_role_projects(root, roles, local_sources, extra_selection) == plans, 'local selection changed')
    lock = json.loads(_read(root / "config/python-build-dependencies.json").decode())
    entries = lock["dependencies"]
    _require(len(entries) == 1 and entries[0]["name"] == "flit_core"
             and backend.name == entries[0]["filename"] and _sha(backend) == entries[0]["sha256"],
             "locked Flit backend required")
    tools = {str(path): _sha(path) for path in (python, uv, backend)}
    _require(not any(work.is_relative_to(p["directory"]) for p in projects), "work inside build source")
    work.mkdir()
    logs, cache, temp, qa = (work / name for name in ("logs", "cache", "temp", "qa"))
    for path in (logs, cache, temp, qa): path.mkdir()
    _json_write(work / "source-identity.json", {"files": inputs, "tools": tools, 'local_projects': plans,
                                              'local_sources': local_sources, 'extras': extra_selection})
    for name in ("runtime_identity.py", "fixture_control.py"):
        shutil.copyfile(root / "tests/integration/qmt_shm_account/scan" / name, qa / name)
    generator = work / "runtime-generator.py"
    own = root / "scripts/native_support/account_runtime_install.py"
    _require(_read(own) == _read(Path(__file__)), "installer source owner mismatch")
    shutil.copyfile(own, generator)
    driver = work / "flit-build.py"; driver.write_text(_BUILD, encoding="utf-8", newline="\n")
    pinned = {str(path): _sha(path) for path in (generator, driver, qa / "runtime_identity.py", qa / "fixture_control.py",
                                               work/'source-identity.json')}
    command_count = 0

    def checked(argv, cwd, label, timeout):
        nonlocal command_count
        _require(_inputs(root, projects) == inputs and all(_sha(Path(p)) == h for p, h in {**tools, **pinned}.items()),
                 "installer inputs changed")
        command_count += 1
        _require(command_count <= 32 and 0 < timeout <= 600, "command budget")
        run(tuple(str(item) for item in argv), cwd=Path(cwd), log=logs / (label + ".log"), timeout=timeout)
        _require(_inputs(root, projects) == inputs and all(_sha(Path(p)) == h for p, h in {**tools, **pinned}.items()),
                 "installer inputs changed")

    checked((python, "-I", "-B", "-c",
             "import sys,os,struct;assert sys.implementation.name=='cpython' and sys.version_info[:2]==(3,12) and os.name=='nt' and struct.calcsize('P')==8"),
            work, "tool-python", 30)
    built = {}
    for index, project in enumerate(projects):
        directory = work / ("build-" + str(index)); directory.mkdir()
        wheels, metadata, temporary = (directory / name for name in ("wheels", "metadata", "temp"))
        for path in (wheels, metadata, temporary): path.mkdir()
        checked((python, "-I", "-B", driver, backend, wheels, metadata, temporary),
                project["directory"], "flit-" + str(index), 120)
        candidates = list(wheels.iterdir())
        prepared = list(metadata.glob("*.dist-info/METADATA"))
        _require(len(candidates) == len(prepared) == 1, "Flit output scope")
        project["prepared_metadata"] = prepared[0]
        built[project["name"]] = _wheel_info(candidates[0], project)
        pinned[str(prepared[0])] = built[project["name"]]["prepared_metadata_sha256"]

    installed_roles = {}
    by_relative = {project["relative"]: project for project in projects}
    for role in roles:
        selected = [by_relative[path] for path in plans[role]]
        directory = work / role; directory.mkdir()
        local_path = directory/'local-projects.json'
        _json_write(local_path, dict(role=role, extras=extra_selection[role], projects=[
            {key: project[key] for key in ('name', 'version', 'module', 'relative')} for project in selected]))
        pinned[str(local_path)] = _sha(local_path)
        wheel_dir = directory / "wheels"; wheel_dir.mkdir()
        private = {p["name"]: built[p["name"]] for p in selected}
        for info in private.values(): shutil.copyfile(info["path"], wheel_dir / info["path"].name)
        registry_path = directory / "registry.lock"
        source = selected[0]["directory"]
        if role == "app" or (source / "uv.lock").exists():
            argv = [uv, "export", "--frozen", "--no-dev", "--no-emit-local", "--no-header", "--no-annotate",
                    "--python", python, "--format", "requirements.txt", "--output-file", registry_path,
                    "--no-python-downloads", "--no-config", "--cache-dir", cache / "uv"]
            for name in private: argv.extend(("--no-emit-package", name))
            for extra in extra_selection[role]: argv.extend(('--extra', extra))
        else:
            public = []
            for project in selected:
                for requirement in _dependencies(project, extra_selection[role] if project is selected[0] else ()):
                    name = _dependency_name(requirement)
                    if name in local_names:
                        _require(name in private, "local dependency role")
                    else:
                        _require(not name.startswith("guanheng-"), "private index dependency")
                        public.append(requirement)
            public_path = directory / "public.in"
            public_path.write_text("\n".join(public) + "\n", encoding="utf-8", newline="\n")
            if public:
                argv = [uv, "pip", "compile", public_path, "--python", python, "--only-binary", ":all:",
                        "--generate-hashes", "--no-header", "--no-annotate", "--output-file", registry_path,
                        "--no-python-downloads", "--no-config", "--cache-dir", cache / "uv"]
                for path in caches: argv.extend(("--find-links", path))
                if offline: argv.append("--no-index")
                else: argv.extend(("--index-url", "https://pypi.org/simple"))
            else:
                # 全部依赖均为已构建的本地wheel时，registry集合自然为空。
                # 最终requirements仍由_role_lock写入每个私有wheel的精确摘要。
                registry_path.write_bytes(b'')
                argv = None
        if argv is not None:
            if offline: argv.append("--offline")
            checked(argv, source, role + "-registry-lock", 300)
        registry_raw = _read(registry_path)
        registry = _requirements(registry_raw, allow_empty=True)
        pinned[str(registry_path)] = _sha(registry_path)
        _require(not any(item["name"] in local_names for item in registry), "local source leaked into registry lock")
        download = [python, "-I", "-B", "-m", "pip", "--cache-dir", cache / "pip", "download",
                    "--require-hashes", "--only-binary", ":all:", "--dest", wheel_dir, "-r", registry_path,
                    "--disable-pip-version-check"]
        for path in caches: download.extend(("--find-links", path))
        if offline: download.append("--no-index")
        else: download.extend(("--index-url", "https://pypi.org/simple"))
        if registry:
            checked(download, work, role + "-download", 600)
        wheel_infos = _wheelhouse(wheel_dir, registry, private)
        full_lock = _role_lock(registry_raw, private, {selected[0]['name']: extra_selection[role]})
        (directory / "requirements.lock").write_bytes(full_lock)
        for path in (directory / "requirements.lock", *wheel_dir.iterdir()):
            pinned[str(path)] = _sha(path)
        target = directory / "venv"
        checked((python, "-I", "-B", "-m", "venv", "--without-pip", target), work, role + "-venv", 120)
        executable = target / "Scripts/python.exe"
        # 安装后的代码独立于可变缓存；普通复制也满足Host对单链接正文的身份核验。
        checked((uv, "pip", "install", "--link-mode", "copy", "--python", executable, "--no-index", "--find-links", wheel_dir,
                 "--require-hashes", "--only-binary", ":all:", "-r", directory / "requirements.lock",
                 "--no-python-downloads", "--no-config", "--cache-dir", cache / "uv"),
                work, role + "-install", 600)
        check_argv = (python, "-I", "-B", "-m", "pip", "--disable-pip-version-check",
                      "--python", executable, "check")
        checked(check_argv, work, role + "-pip-check", 120)
        _json_write(directory / "pip-check.json", {"schema": "qar.pip-check.v1", "role": role,
                    "status": "passed", "argv": [str(item) for item in check_argv],
                    "tool_sha256": tools[str(python)]})
        pinned[str(directory / "pip-check.json")] = _sha(directory / "pip-check.json")
        checked((executable, "-I", "-B", generator, "--root", directory, "--role", role, "--qa", qa),
                work, role + "-receipt", 180)
        receipt = directory / "runtime-receipt.json"
        _read(receipt)
        installed_roles[role] = {"root": str(directory), "runtime_receipt": str(receipt), "executable": str(executable),
                       "receipt_sha256": _sha(receipt), "lock_sha256": _sha(directory / "requirements.lock"),
                       "wheels": {name: {"file": info["path"].name, "sha256": info["sha256"],
                                         "version": info["version"], "metadata_sha256": info["metadata_sha256"],
                                         "prepared_metadata_sha256": info["prepared_metadata_sha256"]}
                                  for name, info in sorted(wheel_infos.items())}}
    _require(_inputs(root, projects) == inputs and all(_sha(Path(p)) == h
             for p, h in {**tools, **pinned}.items()), "final installer identity changed")
    result = {"schema": "qar.test-runtime-install.v1", "status": "roles-installed",
              "roles": installed_roles, "sources": inputs, "tools": tools,
              'local_projects': plans, 'local_sources': local_sources, 'extras': extra_selection,
              "generated_inputs": {Path(p).relative_to(work).as_posix(): h for p, h in pinned.items()},
              "scope": "ATI installed-role validation; native45/SDK/product-unqualified",
              "product_qualified": False}
    _json_write(work / "installation.json", result)
    return result


ARTIFACT_MANIFEST = "ROLE-ARTIFACTS.json"


def _separate_paths(outputs, sources):
    """写目标与来源及其他写目标互不包含，失败现场只留在独占输出根。"""
    destinations, origins = [], []
    for sequence, result in ((outputs,destinations),(sources,origins)):
        for path in sequence:
            _require(isinstance(path,Path) and path.is_absolute(), 'absolute ownership path required')
            _unlinked(path,allow_missing=True)
            result.append(path.resolve(strict=False))
    for index,target in enumerate(destinations):
        for source in (*origins,*destinations[:index]):
            _require(not target.is_relative_to(source) and not source.is_relative_to(target),
                     'output overlaps read-only source or another output')


def _publish_installation(path, value, deadline):
    """完整待发布原件先落盘和核摘要；原D耗尽时保留pending，成功名最后发布。"""
    pending = path.with_name(path.name+'.pending')
    _json_write(pending,value)
    digest = _sha(pending)
    _require(time.monotonic() < deadline, 'installation deadline exhausted before publication')
    _require(not path.exists(), 'installation receipt already exists')
    pending.rename(path)
    return digest


def _artifact_files(root):
    """发行输入只接纳普通文件；运行目录和产品源码不参与制品安装。"""
    _unlinked(root)
    root = root.resolve(strict=True)
    result, folded, total = {}, set(), 0
    for path in root.rglob('*'):
        _unlinked(path)
        if path.is_dir():
            continue
        _regular(path)
        key = path.relative_to(root).as_posix()
        _require(key.casefold() not in folded and len(result) < MAX_FILES, 'artifact member identity')
        folded.add(key.casefold())
        total += path.stat().st_size
        _require(total <= 1024**3, 'artifact total capacity')
        result[key] = _sha(path)
    return result


def _artifact_role(root, role, expected):
    directory = _within(root, root/role)
    _require(set(expected) == {'wheels', 'lock_sha256'}, 'artifact role fields')
    _require(_sha(directory/'requirements.lock') == expected['lock_sha256'], 'artifact lock identity')
    wheels = _wheelhouse(directory/'wheels', _requirements(_read(directory/'requirements.lock')), {})
    _require(set(wheels) == set(expected['wheels']), 'artifact wheel set')
    for name, info in wheels.items():
        record = expected['wheels'][name]
        _require(info['path'].name == record['file'] and all(info[key] == record[key]
                 for key in ('sha256', 'version', 'metadata_sha256')), 'artifact wheel identity')
    local = json.loads(_read(directory/'local-projects.json').decode())
    _require(local['role'] == role and type(local['projects']) is list, 'artifact local project roles')
    return wheels


def verify_artifacts(root: Path, expected_sha256: str) -> dict:
    """核预建角色wheel、普通精确锁及原收据来源；无环境创建或子进程。"""
    _unlinked(root)
    root = root.resolve(strict=True)
    raw = _read(root/ARTIFACT_MANIFEST)
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'artifact manifest identity')
    document = json.loads(raw.decode())
    _require(set(document) == {'schema', 'source_installation_sha256', 'roles', 'extras', 'files'}
             and document['schema'] == 'qar.role-artifacts.v1', 'artifact schema')
    roles = tuple(document['roles'])
    _roles(roles)
    _selected_extras(roles, document['extras'])
    files = _artifact_files(root)
    files.pop(ARTIFACT_MANIFEST)
    _require(files == document['files'], 'artifact file identity')
    _require(_sha(root/'source-installation.json') == document['source_installation_sha256'], 'artifact origin')
    for role in roles:
        _artifact_role(root, role, document['roles'][role])
    return document


def stage_artifacts(installation: Path, expected_sha256: str, output: Path) -> dict:
    """从已验普通安装提取可分发输入；输出全新目录，不复制venv/源码或构建。"""
    _unlinked(installation)
    _require(_sha(installation) == expected_sha256, 'source installation identity')
    original = json.loads(_read(installation).decode())
    _require(original['schema'] == 'qar.test-runtime-install.v1' and original['status'] == 'roles-installed',
             'ordinary role installation required')
    roles = tuple(original['roles'])
    _roles(roles)
    base = installation.parent.resolve(strict=True)
    _separate_paths((output,),(base,))
    selected = {}
    for role in roles:
        record = original['roles'][role]
        _artifact_role(base, role, {key:record[key] for key in ('wheels','lock_sha256')})
        for name in (f'{role}/requirements.lock', f'{role}/local-projects.json',
                     *(f'{role}/wheels/{value["file"]}' for value in record['wheels'].values())):
            _require(name in original['generated_inputs'], 'unregistered installation artifact')
            selected[name] = original['generated_inputs'][name]
    for name in ('qa/runtime_identity.py','qa/fixture_control.py','runtime-generator.py'):
        selected[name] = original['generated_inputs'][name]
    _require(output.is_absolute() and not output.exists(), 'fresh artifact output required')
    _unlinked(output.parent)
    output.mkdir()
    output = output.resolve(strict=True)
    for name, digest in selected.items():
        source = _within(base, base/name)
        _require(_sha(source) == digest, 'source artifact changed')
        target = output/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        _require(_sha(target) == digest, 'copied artifact identity')
    shutil.copyfile(installation,output/'source-installation.json')
    document = {'schema':'qar.role-artifacts.v1','source_installation_sha256':expected_sha256,
        'roles':{role:{key:original['roles'][role][key] for key in ('wheels','lock_sha256')} for role in roles},
        'extras':original['extras'],'files':_artifact_files(output)}
    _json_write(output/ARTIFACT_MANIFEST,document)
    identity = _sha(output/ARTIFACT_MANIFEST)
    verify_artifacts(output,identity)
    return {'manifest_sha256':identity,'roles':document['roles'],'extras':document['extras']}


def install_artifacts(root: Path, expected_sha256: str, work: Path, python: Path, uv: Path, run,
                      *, deadline: float) -> dict:
    """在同一有限总截止内离线普通安装预建角色；失败留现场且不发布成功收据。

    run拥有隐藏创建期外层Job、输出/内存上限和真实关闭证明。本入口只传剩余预算。
    Python3.12 x64及带pip的工具解释器、uv均为显式外部前置；绝不重建wheel或联网。
    """
    import math
    _require(type(deadline) in (int,float) and math.isfinite(deadline)
             and deadline > time.monotonic() and callable(run), 'finite installation deadline')
    document = verify_artifacts(root,expected_sha256)
    root = root.resolve(strict=True)
    _separate_paths((work,),(root,))
    _require(work.is_absolute() and not work.exists(), 'fresh role installation directory required')
    _unlinked(work.parent)
    tools = {}
    for tool in (python,uv):
        _require(tool.is_absolute(), 'absolute installation tool required')
        _unlinked(tool)
        tools[str(tool)] = _sha(tool)
    work.mkdir()
    work = work.resolve(strict=True)
    for name in document['files']:
        target = work/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(_within(root,root/name),target)
    logs, cache = work/'logs', work/'cache'
    logs.mkdir();cache.mkdir()
    commands = 0

    def checked(argv,label,maximum):
        nonlocal commands
        _require(all(_sha(Path(p)) == digest for p,digest in tools.items())
                 and all(_sha(root/name) == digest and _sha(work/name) == digest
                         for name,digest in document['files'].items()), 'installation artifact changed')
        commands += 1
        _require(commands <= 16, 'installation command capacity')
        # 哈希也消费同一D；派发前最后取剩余量，不能沿用读取前的预算。
        remaining = deadline-time.monotonic()
        _require(remaining > 0, 'installation deadline exhausted')
        run(tuple(str(item) for item in argv),cwd=work,log=logs/(label+'.log'),timeout=min(maximum,remaining))
        _require(time.monotonic() < deadline, 'installation deadline exhausted')
        _require(all(_sha(Path(p)) == digest for p,digest in tools.items())
                 and all(_sha(root/name) == digest and _sha(work/name) == digest
                         for name,digest in document['files'].items()), 'installation artifact changed')
        _require(time.monotonic() < deadline, 'installation deadline exhausted')

    checked((python,'-I','-B','-c',"import sys,os,struct;assert sys.implementation.name=='cpython' and sys.version_info[:2]==(3,12) and os.name=='nt' and struct.calcsize('P')==8"),'python',30)
    installed = {}
    for role in document['roles']:
        directory = work/role
        executable = directory/'venv/Scripts/python.exe'
        checked((python,'-I','-B','-m','venv','--without-pip',directory/'venv'),role+'-venv',120)
        # 离线搬迁与源码构建安装沿用同一复制语义，避免与uv缓存共享文件实体。
        checked((uv,'pip','install','--link-mode','copy','--python',executable,'--no-index','--find-links',directory/'wheels',
                 '--require-hashes','--only-binary',':all:','-r',directory/'requirements.lock',
                 '--offline','--no-python-downloads','--no-config','--cache-dir',cache/'uv'),role+'-install',600)
        argv = (python,'-I','-B','-m','pip','--disable-pip-version-check','--python',executable,'check')
        checked(argv,role+'-pip-check',120)
        _json_write(directory/'pip-check.json',{'schema':'qar.pip-check.v1','role':role,'status':'passed',
                    'argv':[str(item) for item in argv],'tool_sha256':tools[str(python)]})
        checked((executable,'-I','-B',work/'runtime-generator.py','--root',directory,'--role',role,
                 '--qa',work/'qa'),role+'-receipt',180)
        receipt = directory/'runtime-receipt.json'
        _read(receipt)
        installed[role] = {'root':str(directory),'executable':str(executable),'runtime_receipt':str(receipt),
            'receipt_sha256':_sha(receipt),'lock_sha256':document['roles'][role]['lock_sha256'],
            'pythonw_sha256':_sha(_within(work,executable.with_name('pythonw.exe'))),
            'wheels':document['roles'][role]['wheels']}
    verify_artifacts(root,expected_sha256)
    result = {'schema':'qar.artifact-runtime-install.v1','status':'roles-installed','roles':installed,
              'extras':document['extras'],'artifact_sha256':expected_sha256,'tools':tools,'commands':commands}
    _publish_installation(work/'installation.json',result,deadline)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Emit one installed ATI role receipt", allow_abbrev=False)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--role", choices=tuple(ROLE_ROOTS), required=True)
    parser.add_argument("--qa", type=Path, required=True)
    args = parser.parse_args()
    _emit_runtime(args.root, args.role, args.qa)
