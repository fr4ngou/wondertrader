"""从永久声明源码离线构建观衡；只组合既有Flit、角色和独立包原语。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import zipfile

from . import account_runtime_install as roles
from . import role_artifact_composition as composition
from . import system_runtime as files


CONFIG = 'config/observer-source.json'
TEMPLATE = 'scripts/runtime_templates/observer-install.py'
SUPPORT = ('scripts/observer_source.py', 'scripts/native_support/observer_source.py',
           'scripts/native_support/role_artifact_composition.py', TEMPLATE,
           'config/python-build-dependencies.json', 'docs/runbooks/observer-runtime.md',
           'tests/integration/qmt_shm_account/scan/runtime_identity.py',
           'tests/integration/qmt_shm_account/scan/fixture_control.py', *files.TOOL_FILES)


def inputs(root: Path):
    """永久声明是唯一输入域；项目成员新增/删除同样改变本次源码身份。"""
    declaration = files._load(root / CONFIG)
    roles._require(set(declaration) == {'schema', 'projects', 'extras', 'registry_lock', 'frontend'}
                   and declaration['schema'] == 'guanheng.observer-source.v1', 'observer source declaration')
    projects = [roles._project(root, name) for name in declaration['projects']]
    roles._require(len(projects) == 6 and len({p['name'] for p in projects}) == 6
                   and projects[0]['name'] == 'guanheng-app', 'observer six-project scope')
    paths = {files._path(root, name) for name in (*SUPPORT, CONFIG, declaration['registry_lock'])}
    paths.update(path for project in projects for path in project['files'])
    paths.add(files._path(root, 'apps/guanheng/uv.lock'))
    frontend = declaration['frontend']
    roles._require(set(frontend) == {'project', 'files', 'shared_files'} and len(frontend['files']) <= 2000
                   and len(set(frontend['files'])) == len(frontend['files']), 'frontend source scope')
    front_root = roles._within(root, root / frontend['project'])
    for name in frontend['files']:
        path = files._path(root, name)
        roles._require(path.is_relative_to(front_root), 'frontend input outside project')
        paths.add(path)
    for name in frontend['shared_files']:
        paths.add(files._path(root, name))
    identities = {p.relative_to(root).as_posix(): roles._sha(p) for p in sorted(paths)}
    return declaration, projects, identities


def build(root: Path, work: Path, *, python: Path, backend: Path, wheelhouse: Path,
          node: Path, npm_cli: Path, npm_cache: Path, deadline: float, run):
    """调用方持有原D；每条外部命令使用原native.run的隐藏Job和完整回收。"""
    root = files._root(root)
    declaration, projects, before = inputs(root)
    roles._require(callable(run) and time.monotonic() < deadline, 'finite source build owner')
    for path in (python, backend, node, npm_cli):
        roles._unlinked(path)
    python, backend, node, npm_cli = (path.resolve(strict=True) for path in (python, backend, node, npm_cli))
    tools = {str(path): roles._sha(path) for path in (python, backend, node, npm_cli)}
    expected_backend = files._load(root / 'config/python-build-dependencies.json')['dependencies'][0]
    roles._require(backend.name == expected_backend['filename'] and tools[str(backend)] == expected_backend['sha256'],
                   'locked Flit backend required')
    wheelhouse, npm_cache = files._root(wheelhouse), files._root(npm_cache)
    registry_raw = roles._read(root / declaration['registry_lock'])
    registry = roles._requirements(registry_raw)
    public = roles._wheelhouse(wheelhouse, registry, {})
    roles._require(len(public) == len(registry) == 24
                   and {r['name'] for r in registry} == set(public), 'complete observer third-party wheels')
    public_shas = {p.name: roles._sha(p) for p in wheelhouse.iterdir()}
    npm_root = files._root(npm_cli.parent.parent)
    npm_tools = files._files(npm_root)
    roles._separate_paths((work,), (root, wheelhouse, npm_cache, npm_root))
    work = files._fresh(work)
    logs, temporary = work / 'logs', work / 'temp'
    logs.mkdir();temporary.mkdir()
    (work / 'npm-user.conf').write_bytes(b'')
    (work / 'npm-global.conf').write_bytes(b'')
    environment = {key: value for key, value in os.environ.items()
                   if key not in ('NODE_OPTIONS', 'NODE_PATH', 'NODE_ENV', 'PYTHONPATH', 'PYTHONHOME')
                   and not key.lower().startswith('npm_config_')
                   and not key.startswith(('GUANHENG_', 'VITE_', 'CONSOLE_BFF_', 'OBSERVATION_BFF_'))}
    environment.update(TEMP=str(temporary), TMP=str(temporary), SOURCE_DATE_EPOCH='315532800',
        PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8',
        PATH=str(node.parent) + os.pathsep + environment.get('PATH', ''),
        NPM_CONFIG_USERCONFIG=str(work / 'npm-user.conf'), NPM_CONFIG_GLOBALCONFIG=str(work / 'npm-global.conf'))
    commands = []

    def checked(argv, *, cwd, label, maximum):
        roles._require(inputs(root)[2] == before, 'permanent sources changed during build')
        roles._require(all(roles._sha(Path(name)) == digest for name, digest in tools.items()), 'build tool changed')
        remaining = deadline - time.monotonic()
        roles._require(remaining > 0, 'source build deadline exhausted')
        _, elapsed = run(tuple(map(str, argv)), cwd=cwd, env=environment,
            log=logs / (label + '.log'), timeout=min(maximum, remaining),
            private_console=True, max_output_bytes=4 * 1024**2)
        commands.append(dict(name=label, elapsed=elapsed, original_job_tree_eof_join=True))
        roles._require(time.monotonic() < deadline and inputs(root)[2] == before, 'source build identity/deadline')

    checked((python, '-I', '-B', '-c',
        "import sys,os,struct;assert sys.implementation.name=='cpython' and sys.version_info[:2]==(3,12) and os.name=='nt' and struct.calcsize('P')==8;print(sys.version)"),
        cwd=work, label='python', maximum=30)
    checked((node, '--version'), cwd=work, label='node', maximum=30)
    checked((node, npm_cli, '--version'), cwd=work, label='npm', maximum=30)
    driver = work / 'flit-build.py';driver.write_text(roles._BUILD, encoding='utf8')
    source_roles = work / 'source-roles';source_roles.mkdir()
    role_root = source_roles / 'app';role_root.mkdir()
    wheel_output = role_root / 'wheels';wheel_output.mkdir()
    built = {}
    for index, project in enumerate(projects):
        stage = work / ('flit-' + str(index));stage.mkdir()
        wheels, metadata, scratch = (stage / name for name in ('wheels', 'metadata', 'temp'))
        for path in (wheels, metadata, scratch):path.mkdir()
        checked((python, '-I', '-B', driver, backend, wheels, metadata, scratch),
                cwd=project['directory'], label='flit-' + str(index), maximum=120)
        artifacts = list(wheels.iterdir());prepared = list(metadata.glob('*.dist-info/METADATA'))
        roles._require(len(artifacts) == len(prepared) == 1, 'one Flit output required')
        project['prepared_metadata'] = prepared[0]
        info = roles._wheel_info(artifacts[0], project)
        built[info['name']] = info
        shutil.copyfile(artifacts[0], wheel_output / artifacts[0].name)
    for info in public.values():shutil.copyfile(info['path'], wheel_output / info['path'].name)
    lock = roles._role_lock(registry_raw, built, {'guanheng-app': tuple(declaration['extras'])})
    (role_root / 'requirements.lock').write_bytes(lock)
    roles._json_write(role_root / 'local-projects.json', dict(role='app', extras=declaration['extras'],
        projects=[{key: p[key] for key in ('name', 'version', 'module', 'relative')} for p in projects]))
    wheel_infos = roles._wheelhouse(wheel_output, registry, built)
    roles._require(len(wheel_infos) == 30, 'App30 closure required')
    qa = source_roles / 'qa';qa.mkdir()
    for name in ('runtime_identity.py', 'fixture_control.py'):
        shutil.copyfile(root / 'tests/integration/qmt_shm_account/scan' / name, qa / name)
    shutil.copyfile(root / 'scripts/native_support/account_runtime_install.py', source_roles / 'runtime-generator.py')
    origin = dict(schema='guanheng.observer-source-build.v1', sources=before, tools=tools,
        source_root=str(root), projects=[p['relative'] for p in projects], installed=False,
        npm_tool_files=npm_tools, commands=commands)
    roles._json_write(source_roles / 'source-installation.json', origin)
    document = dict(schema='qar.role-artifacts.v1',
        source_installation_sha256=roles._sha(source_roles / 'source-installation.json'),
        roles={'app': dict(lock_sha256=hashlib.sha256(lock).hexdigest(), wheels={name: {
            'file': info['path'].name, 'version': info['version'], 'sha256': info['sha256'],
            'metadata_sha256': info['metadata_sha256'], 'prepared_metadata_sha256': info.get('prepared_metadata_sha256')}
            for name, info in sorted(wheel_infos.items())})},
        extras={'app': declaration['extras']}, files=roles._artifact_files(source_roles))
    roles._json_write(source_roles / roles.ARTIFACT_MANIFEST, document)
    source_identity = roles._sha(source_roles / roles.ARTIFACT_MANIFEST)
    roles.verify_artifacts(source_roles, source_identity)
    selection = dict(schema='qar.role-artifact-selection.v1',
        roles={'app': dict(root=str(source_roles), sha256=source_identity)},
        runtime_tools=dict(root=str(source_roles), sha256=source_identity))
    roles._json_write(work / 'ROLE-SELECTION.json', selection)
    composed = composition.compose(work / 'ROLE-SELECTION.json', roles._sha(work / 'ROLE-SELECTION.json'), work / 'roles')
    frontend_stage = work / 'frontend';frontend_stage.mkdir()
    frontend = declaration['frontend'];front_root = root / frontend['project']
    for name in (*frontend['files'], *frontend['shared_files']):
        source = root / name;target = frontend_stage / name
        target.parent.mkdir(parents=True, exist_ok=True);shutil.copyfile(source, target)
    console = frontend_stage / frontend['project']
    checked((node, npm_cli, 'ci', '--offline', '--cache', npm_cache, '--no-audit', '--no-fund'),
            cwd=console, label='frontend-ci', maximum=300)
    checked((node, npm_cli, 'run', 'build'), cwd=console, label='frontend-build', maximum=300)
    for name in (*frontend['files'], *frontend['shared_files']):
        roles._require(roles._sha(frontend_stage / name) == before[name], 'frontend source changed')
    assets = files._files(console / 'dist')
    package = work / 'package';package.mkdir()
    shutil.copytree(work / 'roles', package / 'roles')
    shutil.copytree(console / 'dist', package / 'spa')
    for name in files.TOOL_FILES:
        target = package / 'tools' / name;target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    shutil.copyfile(root / TEMPLATE, package / 'observer-install.py')
    shutil.copyfile(root / 'docs/runbooks/observer-runtime.md', package / 'README.md')
    manifest = dict(schema='guanheng.observer-runtime.v1', development=True,
        role_manifest_sha256=composed['manifest_sha256'],
        spa_files={name: record['sha256'] for name, record in assets.items()}, files=files._files(package))
    roles._json_write(package / 'OBSERVER-RUNTIME.json', manifest)
    manifest_sha = roles._sha(package / 'OBSERVER-RUNTIME.json')
    checked((python, '-I', '-B', package / 'observer-install.py', 'verify', '--root', package,
             '--manifest-sha256', manifest_sha), cwd=work, label='verify-package', maximum=60)
    archive = work / ('observer-' + projects[0]['version'] + '-windows-x64.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        for name, path in files._inventory(package).items():output.write(path, name)
    roles._require(inputs(root)[2] == before and files._files(npm_root) == npm_tools
                   and all(roles._sha(Path(name)) == digest for name, digest in tools.items()), 'final source/tool identity')
    roles._require({p.name: roles._sha(p) for p in wheelhouse.iterdir()} == public_shas, 'third-party inputs changed')
    roles._require(time.monotonic() < deadline, 'source build publication deadline')
    result = dict(schema='guanheng.observer-source-result.v1', status='built', App=projects[0]['version'],
        source_root=str(root), source_inputs=before, tools=tools, commands=commands,
        role_root=str(work / 'roles'), role_manifest_sha256=composed['manifest_sha256'],
        package=str(package), manifest_sha256=manifest_sha, archive=str(archive), archive_sha256=roles._sha(archive),
        distributions=30, frontend_sources=len(frontend['files'])+len(frontend['shared_files']), SPA_files=len(assets),
        business_processes_started=0, installed=False, production=False)
    roles._publish_installation(work / 'SOURCE-BUILD.json', result, deadline)
    roles._require(time.monotonic() < deadline, 'source build publication completed after deadline')
    return result
