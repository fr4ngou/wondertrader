"""从永久源码构建独立Host/Agent/Core；临时组装只选择声明的Core namespace。

算法由原源码维护，Flit及标准wheel映射负责发行。此工具不启动服务或访问QMT。
"""
from __future__ import annotations

import argparse
import ast
import base64
import csv
from email import message_from_bytes
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tomllib
import zipfile

from client_sdk import backend, digest
from native_support.process_startup import background_process_options


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/source-packages.json'


def owned(relative):
    """构建输入仅为仓库普通文件；声明使用仓库相对路径。"""
    name = PurePosixPath(relative)
    if name.is_absolute() or '..' in name.parts or '\\' in relative or ':' in relative:
        raise ValueError('source package input path')
    path = ROOT / relative
    if not path.is_file() or any(
            p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400
            for p in (path, *path.parents) if p != ROOT.parent and p.is_relative_to(ROOT)):
        raise ValueError('source package regular owned input required')
    return path


def sources():
    """元数据与成员分别固定；新增Host/Agent文件也进入本次身份。"""
    config = json.loads(CONFIG.read_bytes())
    projects, inputs, members = {}, {CONFIG.relative_to(ROOT).as_posix(): digest(CONFIG)}, {}
    for role, relative in config['projects'].items():
        project = ROOT / relative
        metadata = tomllib.loads(owned(relative + '/pyproject.toml').read_text('utf8'))
        if metadata['build-system'] != dict(requires=['flit_core==3.12.0'], **{'build-backend': 'flit_core.buildapi'}):
            raise ValueError('source package backend differs')
        projects[role] = (project, metadata)
        selected = [owned(relative + '/pyproject.toml'), owned(relative + '/README.md')]
        if role != 'core':
            module = metadata['tool']['flit']['module']['name']
            package = project / module
            files = sorted(p for p in package.rglob('*') if p.is_file()
                           and '__pycache__' not in p.parts and p.suffix != '.pyc')
            members[role] = {p.relative_to(project).as_posix(): p for p in files}
            selected += files
        else:
            members[role] = {name: owned(path) for name, path in config['core_members'].items()}
            selected += list(members[role].values())
        for path in selected:
            key = path.relative_to(ROOT).as_posix()
            inputs[key] = digest(owned(key))
    inputs['scripts/source_packages.py'] = digest(Path(__file__))
    inputs['scripts/client_sdk.py'] = digest(ROOT / 'scripts/client_sdk.py')
    inputs['scripts/native_support/process_startup.py'] = digest(ROOT / 'scripts/native_support/process_startup.py')
    inputs['config/python-build-dependencies.json'] = digest(ROOT / 'config/python-build-dependencies.json')
    return projects, inputs, members


def append_core_export(wheel, additions):
    """按既有发行契约补写显式映射的wheel成员，并重算RECORD。"""
    with zipfile.ZipFile(wheel) as archive:
        payload = {n: archive.read(n) for n in archive.namelist()}
    record = next(n for n in payload if n.endswith('.dist-info/RECORD'))
    del payload[record]
    if set(additions) & set(payload):
        raise ValueError('core export collides with Flit member')
    payload.update(additions)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    for name, raw in sorted(payload.items()):
        value = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
        writer.writerow((name, 'sha256=' + value, len(raw)))
    writer.writerow((record, '', ''))
    payload[record] = stream.getvalue().encode()
    candidate = wheel.with_suffix('.new')
    with candidate.open('xb') as output, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, raw)
    os.replace(candidate, wheel)


def build(work, *, offline=False, backend_wheel=None):
    """新目录内普通构建；前后源码固定，失败保留日志和原输入。"""
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=False)
    projects, before, members = sources()
    if backend_wheel is not None:
        declaration = json.loads((ROOT / 'config/python-build-dependencies.json').read_bytes())['dependencies'][0]
        if digest(backend_wheel) != declaration['sha256']:
            raise ValueError('source build backend identity differs')
        target = work / 'deps' / declaration['filename']
        target.parent.mkdir()
        shutil.copyfile(backend_wheel, target)
    tool = backend(work, offline=offline)
    artifact = work / 'wheels'
    artifact.mkdir()
    environment = dict(os.environ, SOURCE_DATE_EPOCH='315532800', PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    results, commands = {}, []
    for role in ('agent', 'host', 'core'):
        project, metadata = projects[role]
        if role == 'agent':
            for name, path in members[role].items():
                if name.endswith('.py'):
                    ast.parse(path.read_text('utf-8-sig'), filename=name, feature_version=(3, 6))
        if role == 'core':
            stage = work / 'core-project'
            stage.mkdir()
            for name in ('pyproject.toml', 'README.md'):
                shutil.copyfile(project / name, stage / name)
            for name, path in members[role].items():
                if not name.startswith('integrations/'):
                    raise ValueError('native core members must belong to its package')
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            provenance = dict(schema='guanheng.native-core-permanent-sources.v1',
                              members={name: dict(source=path.relative_to(ROOT).as_posix(), sha256=digest(path))
                                       for name, path in members[role].items()})
            (stage / 'integrations/ORIGINS.json').write_text(json.dumps(provenance, sort_keys=True, separators=(',', ':')), 'utf8')
            project = stage
        output = work / role
        output.mkdir()
        command = [sys.executable, '-I', '-B', '-c',
                   'import sys;sys.path.insert(0,sys.argv[1]);from flit_core.buildapi import build_wheel;build_wheel(sys.argv[2])',
                   str(tool), str(output)]
        result = subprocess.run(command, cwd=project, env=environment, capture_output=True,
                                timeout=120, **background_process_options())
        log = output / 'build.log'
        log.write_bytes(result.stdout + result.stderr)
        commands.append(dict(role=role, argv=list(map(str, command)), cwd=str(project),
                             returncode=result.returncode,
                             log=dict(path=str(log), sha256=digest(log))))
        (work / 'COMMANDS.json').write_text(json.dumps(commands, sort_keys=True, indent=2), 'utf8')
        if result.returncode:
            raise RuntimeError('source package Flit build failed: ' + role)
        wheels = list(output.glob('*.whl'))
        if len(wheels) != 1:
            raise ValueError('source package wheel count')
        wheel = wheels[0]
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError('source package duplicate wheel members')
            for name, path in members[role].items():
                if archive.read(name) != path.read_bytes():
                    raise ValueError('source package wheel differs from permanent source')
            meta = message_from_bytes(archive.read(next(n for n in names if n.endswith('.dist-info/METADATA'))))
            if meta['Name'] != metadata['project']['name'] or meta['Version'] != metadata['project']['version']:
                raise ValueError('source package metadata differs')
        shutil.copyfile(wheel, artifact / wheel.name)
        results[role] = dict(path=str(artifact / wheel.name), sha256=digest(wheel), members=len(members[role]),
                             name=meta['Name'], version=meta['Version'])
    if before != sources()[1]:
        raise ValueError('permanent source changed during build')
    receipt = dict(schema='guanheng.permanent-source-build.v1', passed=True, inputs=before,
                   backend=dict(path=str(tool), sha256=digest(tool)), wheels=results, commands=commands,
                   python=dict(executable=sys.executable, sha256=digest(sys.executable), version=sys.version,
                               base_prefix=sys.base_prefix), source_date_epoch=315532800,
                   prebuilt_product_wheels_used=False, services_started=0, SDK_calls=0)
    (work / 'BUILD.json').write_text(json.dumps(receipt, sort_keys=True, indent=2), 'utf8')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['build'])
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--backend', type=Path)
    args = parser.parse_args()
    result = build(args.work, offline=args.offline, backend_wheel=args.backend)
    print(json.dumps(dict(passed=True,receipt=str(args.work / 'BUILD.json'),wheels=result['wheels'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
