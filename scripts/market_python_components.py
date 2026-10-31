"""从版本化永久源码组装市场组件的Python切片，并构建其历史兼容发行。

原生组件与解释器由各自安装入口提供。本工具保留组件原有导入布局及包版本，
输出新目录，不接运行服务、证券接口或原数据目录。
"""
from __future__ import annotations

import argparse
import configparser
from email import message_from_bytes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tomllib
import zipfile

from native_support.process_startup import background_process_options
from source_packages import owned


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/market-python-components.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(value):
    """组件成员使用规范相对路径，解包和复制共用同一边界。"""
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or path.as_posix() != value
            or any(p in ('.', '..') or ':' in p or '\\' in p for p in path.parts)):
        raise ValueError('market Python component relative member required')
    return path


def configuration():
    value = json.loads(CONFIG.read_bytes())
    if value['schema'] != 'guanheng.market-python-components.v1':
        raise ValueError('market Python source schema differs')
    return value


def source_inputs(component=None):
    """固定配置、组装器及所选源码；历史原安装仅作溯源，不作为构建依赖。"""
    value = configuration()
    selected = value['components'] if component is None else {component: value['components'][component]}
    result = {CONFIG.relative_to(ROOT).as_posix(): digest(CONFIG),
              'scripts/market_python_components.py': digest(Path(__file__)),
              'scripts/source_packages.py': digest(ROOT / 'scripts/source_packages.py'),
              'scripts/client_sdk.py': digest(ROOT / 'scripts/client_sdk.py'),
              'scripts/native_support/process_startup.py': digest(ROOT / 'scripts/native_support/process_startup.py')}
    for spec in selected.values():
        for member, row in spec['files'].items():
            relative(member)
            if 'source' in row:
                path = owned(row['source'])
                if digest(path) != row['sha256']:
                    raise ValueError('market Python permanent source changed: ' + row['source'])
                result[row['source']] = row['sha256']
            else:
                relative(row['wheel'])
                relative(row['member'])
    return result


def materialize(component, output, *, wheel_dirs=()):
    """组装确切Python闭包；第三方模块只从完整hash固定的标准wheel读取。"""
    before = source_inputs(component)
    spec = configuration()['components'][component]
    output = Path(output).resolve()
    # fresh输出是组装事务的所有权边界；失败目录保留，调用者选择新目录继续。
    output.mkdir(parents=True, exist_ok=False)
    wheels, members = {}, {}
    for member, row in spec['files'].items():
        if 'source' in row:
            data = owned(row['source']).read_bytes()
        else:
            name = row['wheel']
            if name not in wheels:
                candidates = [Path(folder) / name for folder in wheel_dirs]
                wheel = next((p for p in candidates if p.is_file() and digest(p) == row['wheel_sha256']), None)
                if wheel is None:
                    raise ValueError('pinned third-party wheel required: ' + name)
                wheels[name] = dict(path=str(wheel.resolve()), sha256=digest(wheel))
            with zipfile.ZipFile(wheels[name]['path']) as archive:
                if archive.namelist().count(row['member']) != 1:
                    raise ValueError('third-party wheel member differs')
                data = archive.read(row['member'])
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('market Python component member changed: ' + member)
        target = output / member
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        members[member] = row['sha256']
    if before != source_inputs(component):
        raise ValueError('market Python inputs changed during assembly')
    if any(digest(row['path']) != row['sha256'] for row in wheels.values()):
        raise ValueError('pinned third-party wheel changed during assembly')
    result = dict(schema='guanheng.market-python-slice.v1', component=component,
                  version=spec['version'], files=members, inputs=before, third_party_wheels=wheels,
                  native_binaries_included=False, interpreter_included=False, services_started=0, SDK_calls=0)
    (output / 'PYTHON-COMPONENT.json').write_text(json.dumps(result, sort_keys=True, indent=2), 'utf8')
    return result


def build_legacy(work, backend):
    """普通Flit构建保留旧发行元数据及每个包成员；运行角色保持独立。"""
    work, backend = Path(work).resolve(), Path(backend).resolve(strict=True)
    declaration = json.loads((ROOT / 'config/python-build-dependencies.json').read_bytes())['dependencies'][0]
    if digest(backend) != declaration['sha256']:
        raise ValueError('locked Flit backend required')
    before = source_inputs()
    before['config/python-build-dependencies.json'] = digest(ROOT / 'config/python-build-dependencies.json')
    work.mkdir(parents=True, exist_ok=False)
    artifacts = work / 'wheels'
    artifacts.mkdir()
    results = {}
    for name, spec in configuration()['legacy_projects'].items():
        source = ROOT / spec['directory']
        actual = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
        if actual != set(spec['files']):
            raise ValueError('legacy project undeclared or missing source')
        stage = work / name
        stage.mkdir()
        for member, expected in spec['files'].items():
            relative(member)
            path = owned(spec['directory'] + '/' + member)
            if digest(path) != expected:
                raise ValueError('legacy project source changed')
            before[path.relative_to(ROOT).as_posix()] = expected
            target = stage / member
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        command = [sys.executable, '-I', '-B', '-c',
                   'import sys;sys.path.insert(0,sys.argv[1]);from flit_core.buildapi import build_wheel;build_wheel(sys.argv[2])',
                   str(backend), str(artifacts)]
        environment = dict(os.environ, SOURCE_DATE_EPOCH='315532800', PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run(command, cwd=stage, env=environment, capture_output=True,
                                timeout=120, **background_process_options())
        (stage / 'build.log').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('legacy market package build failed: ' + name)
        wheel = artifacts / spec['original_wheel']['filename']
        with zipfile.ZipFile(wheel) as archive:
            members = archive.namelist()
            if len(members) != len(set(members)):
                raise ValueError('duplicate legacy wheel member')
            wanted = {m for m in spec['files'] if m.startswith(spec['module'] + '/')}
            if {m for m in members if m.startswith(spec['module'] + '/')} != wanted:
                raise ValueError('legacy wheel source set differs')
            for member in wanted:
                if hashlib.sha256(archive.read(member)).hexdigest() != spec['files'][member]:
                    raise ValueError('legacy wheel module changed')
            metadata = message_from_bytes(archive.read(next(m for m in members if m.endswith('.dist-info/METADATA'))))
            headers = {k: metadata.get_all(k) for k in metadata.keys() if k != 'Metadata-Version'}
            if headers != spec['expected_metadata']:
                raise ValueError('legacy wheel metadata changed: ' + name)
            project = tomllib.loads((source / 'pyproject.toml').read_text('utf8'))['project']
            entry_file = next((m for m in members if m.endswith('.dist-info/entry_points.txt')), None)
            entries = configparser.ConfigParser()
            if entry_file:
                entries.read_string(archive.read(entry_file).decode('utf8'))
            expected_entries = dict(project.get('entry-points', {}))
            if project.get('scripts'):
                expected_entries['console_scripts'] = project['scripts']
            if {section: dict(entries.items(section)) for section in entries.sections()} != expected_entries:
                raise ValueError('legacy wheel entry points changed')
            for license_file in metadata.get_all('License-File') or []:
                matches = [m for m in members if m.endswith('.dist-info/licenses/' + license_file)]
                if len(matches) != 1 or hashlib.sha256(archive.read(matches[0])).hexdigest() != spec['files'][license_file]:
                    raise ValueError('legacy wheel license changed')
            # Flit在README末尾补换行；描述正文按统一行尾核对，源码原字节独立固定。
            description = metadata.get_payload().replace('\r\n', '\n').rstrip('\n')
            if hashlib.sha256(description.encode()).hexdigest() != spec['description_sha256']:
                raise ValueError('legacy wheel description changed')
        results[name] = dict(path=str(wheel), sha256=digest(wheel), version=spec['version'],
                             original_wheel_sha256=spec['original_wheel']['sha256'], module_members=len(wanted),
                             module_bytes_and_metadata_preserved=True)
    for member, expected in before.items():
        if digest(owned(member)) != expected:
            raise ValueError('market package source changed during build')
    if digest(backend) != declaration['sha256']:
        raise ValueError('locked Flit backend changed during build')
    receipt = dict(schema='guanheng.market-python-build.v1', passed=True, inputs=before, wheels=results,
                   backend=dict(path=str(backend), sha256=digest(backend)),
                   python=dict(executable=sys.executable, sha256=digest(sys.executable), base_prefix=sys.base_prefix,
                               version=sys.version), old_embedded_interpreter_used=False, SDK_calls=0, services_started=0)
    (work / 'BUILD.json').write_text(json.dumps(receipt, sort_keys=True, indent=2), 'utf8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    assemble = commands.add_parser('materialize')
    assemble.add_argument('--component', required=True, choices=list(configuration()['components']))
    assemble.add_argument('--output', type=Path, required=True)
    assemble.add_argument('--wheel-dir', type=Path, action='append', default=[])
    build = commands.add_parser('build-legacy')
    build.add_argument('--work', type=Path, required=True)
    build.add_argument('--backend', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'materialize':
        result = materialize(args.component, args.output, wheel_dirs=args.wheel_dir)
        print(json.dumps(dict(passed=True, files=len(result['files']), output=str(args.output))))
    else:
        result = build_legacy(args.work, args.backend)
        print(json.dumps(dict(passed=True, wheels=result['wheels'])))


if __name__ == '__main__':
    main()
