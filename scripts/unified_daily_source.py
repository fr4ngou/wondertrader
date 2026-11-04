"""按永久显式成员和固定Flit构建WT数据角色；不启动来源、服务或原生导入。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import time
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
from source_packages import append_core_export
import native

ROOT = Path(__file__).resolve().parents[1]
CONFIG = 'config/unified-daily-data-source.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def owned(relative):
    name = PurePosixPath(relative)
    if name.is_absolute() or name.as_posix() != relative or '..' in name.parts or '\\' in relative or ':' in relative:
        raise ValueError('daily source regular relative path required')
    path = ROOT / relative
    if not path.is_file() or any(p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400
            for p in (path, *path.parents) if p.is_relative_to(ROOT)):
        raise ValueError('daily source file is missing or linked')
    return path


def source_inputs():
    """源码身份包含声明、构建/安装入口、角色项目及每个原模块，不读取历史安装。"""
    declaration = json.loads(owned(CONFIG).read_bytes())
    if declaration['schema'] != 'guanheng.daily-data-source.v1':
        raise ValueError('daily source declaration invalid')
    files = {CONFIG: sha(owned(CONFIG))}
    for relative in declaration['support']:
        files[relative] = sha(owned(relative))
    project = ROOT / declaration['project']
    for path in project.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            relative = path.relative_to(ROOT).as_posix()
            files[relative] = sha(owned(relative))
    for member, row in declaration['members'].items():
        name = PurePosixPath(member)
        if name.is_absolute() or name.as_posix() != member or '..' in name.parts or ':' in member or '\\' in member:
            raise ValueError('daily source wheel member invalid')
        if sha(owned(row['source'])) != row['sha256']:
            raise ValueError('daily permanent source changed: ' + row['source'])
        files[row['source']] = row['sha256']
    return declaration, files


def build(work, *, python, backend, wheelhouse, native_directory, seconds):
    """同一总D内完成源轮子/依赖/原生组合；输出保留固定清单，失败根不复用。"""
    from native_support import account_runtime_install as roles
    declaration, before = source_inputs()
    python, backend = Path(python).resolve(strict=True), Path(backend).resolve(strict=True)
    if sha(python) != declaration['runtime']['python_sha256']:
        raise ValueError('daily fixed base interpreter differs')
    expected = json.loads(owned('config/python-build-dependencies.json').read_bytes())['dependencies'][0]
    if sha(backend) != expected['sha256']:
        raise ValueError('daily fixed build backend differs')
    registry = roles._requirements(owned(declaration['registry_lock']).read_bytes())
    required = {row['name']: row for row in registry}
    public = {}
    for path in Path(wheelhouse).iterdir():
        if path.suffix != '.whl':
            continue
        info = roles._wheel_info(path)
        row = required.get(info['name'])
        if row is None:
            continue
        if info['name'] in public or info['version'] != row['version'] or info['sha256'] not in row['hashes']:
            raise ValueError('daily fixed wheel identity differs')
        public[info['name']] = info
    if set(public) != set(required):
        raise ValueError('daily complete third-party wheel closure required')
    work = Path(work).absolute()
    work.mkdir(parents=False, exist_ok=False)
    deadline = time.monotonic() + seconds
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError('daily source build deadline')
        return value
    stage = work / 'project'
    shutil.copytree(ROOT / declaration['project'], stage, ignore=shutil.ignore_patterns('__pycache__'))
    requirements = ['guanheng-market-client==0.16.0'] + [row['name'] + '==' + row['version'] for row in registry]
    metadata = stage / 'pyproject.toml'
    # 同一固定registry是角色依赖正文，Flit元数据与离线安装锁使用同一精确集合。
    text = metadata.read_text('utf8').replace('dynamic = []', 'dependencies = ' + json.dumps(requirements))
    metadata.write_text(text, 'utf8')
    (stage / 'LICENSE').write_bytes(owned('LICENSE').read_bytes())
    output = work / 'private-wheels'
    output.mkdir()
    environment = dict(os.environ, SOURCE_DATE_EPOCH='315532800', PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    native.run([python, '-I', '-B', '-c', 'import sys;sys.path.insert(0,sys.argv[1]);from flit_core.buildapi import build_wheel;build_wheel(sys.argv[2])',
        backend, output], cwd=stage, env=environment, timeout=remaining(), log=work / 'core-build.log', private_console=True)
    wheels = list(output.glob('*.whl'))
    if len(wheels) != 1:
        raise ValueError('daily core wheel count differs')
    wheel = wheels[0]
    additions = {member: owned(row['source']).read_bytes() for member, row in declaration['members'].items()}
    if any(hashlib.sha256(additions[member]).hexdigest() != row['sha256']
           for member, row in declaration['members'].items()):
        raise ValueError('daily source changed while copying')
    origins = {name: dict(source=row['source'], sha256=row['sha256']) for name, row in declaration['members'].items()}
    additions['guanheng_daily_data/ORIGINS.json'] = json.dumps(origins, sort_keys=True, separators=(',', ':')).encode('utf8')
    append_core_export(wheel, additions)
    with zipfile.ZipFile(wheel) as archive:
        for member, data in additions.items():
            if archive.read(member) != data:
                raise ValueError('daily wheel source bytes differ')
    sdk_work = work / 'sdk'
    (sdk_work / 'deps').mkdir(parents=True)
    shutil.copyfile(backend, sdk_work / 'deps' / backend.name)
    sdk_code='import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from client_sdk import build_sdk;build_sdk(Path(sys.argv[2]),output=Path(sys.argv[3]),offline=True)'
    native.run([python, '-I', '-B', '-c',sdk_code, ROOT / 'scripts',sdk_work,sdk_work/'wheels'], cwd=ROOT, env=environment,
        timeout=remaining(), log=work / 'sdk-build.log', private_console=True)
    sdk = json.loads((sdk_work / 'wheels/receipt.json').read_bytes())
    artifact = work / 'artifact'
    (artifact / 'wheels').mkdir(parents=True)
    selected = [dict(name='guanheng-daily-data', version=declaration['version'], path=wheel, sha256=sha(wheel)),
                dict(name='guanheng-market-client', version='0.16.0', path=Path(sdk['wheel']), sha256=sdk['sha256']), *public.values()]
    lines = []
    for info in selected:
        target=artifact / 'wheels' / Path(info['path']).name
        shutil.copyfile(info['path'],target)
        if sha(target)!=info['sha256']:
            raise ValueError('daily copied wheel differs')
        lines.append(info['name'] + '==' + info['version'] + ' --hash=sha256:' + info['sha256'])
    (artifact / 'requirements.lock').write_text('\n'.join(sorted(lines)) + '\n', 'utf8')
    (artifact / 'native').mkdir()
    for name, expected_sha in declaration['native'].items():
        path = Path(native_directory) / name
        if sha(path) != expected_sha:
            raise ValueError('daily native binary identity differs')
        shutil.copyfile(path, artifact / 'native' / name)
        if sha(artifact / 'native' / name)!=expected_sha or sha(path)!=expected_sha:
            raise ValueError('daily native changed while copying')
    for member, source in declaration['installer'].items():
        target = artifact / member
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(owned(source), target)
    remaining()
    files = {p.relative_to(artifact).as_posix(): sha(p) for p in artifact.rglob('*') if p.is_file()}
    manifest = dict(
        schema='guanheng.daily-data-artifact.v1',  # 独立数据角色离线制品合同，不代表已部署。
        version=declaration['version'],  # 本次明确发行身份，区别数据目录版本。
        files=files,  # 包内每个普通文件的SHA；清单本身由调用者外部固定摘要。
        runtime=declaration['runtime'],  # 已验证基础CPython身份，安装时显式提供，不采用当前全局解释器。
        source_inputs=before)  # 完整本仓库源码/工具摘要，源成员来自永久声明。
    (artifact / 'ARTIFACT.json').write_text(json.dumps(manifest, sort_keys=True, indent=2), 'utf8')
    if source_inputs()[1] != before:
        raise ValueError('daily source changed during build')
    if any(sha(info['path']) != info['sha256'] for info in selected):
        raise ValueError('daily input wheel changed during build')
    receipt = dict(
        passed=True,  # 本次离线构建与输入身份核对全部通过。
        artifact=str(artifact),  # 可独立安装的离线制品绝对目录。
        manifest_sha256=sha(artifact / 'ARTIFACT.json'),  # 由安装调用方固定的制品清单身份。
        wheels=len(selected),  # 实际封装的程序、SDK及第三方wheel数量。
        module_members=len(additions),  # 程序wheel附加的原模块及来源清单成员数。
        inputs=before,  # 构建前后核同的永久源码及工具摘要。
        source_calls=0,  # 离线构建没有行情或外部披露来源调用。
        services_started=0)  # 构建不启动WT、QMT或观衡服务。
    (work / 'BUILD.json').write_text(json.dumps(receipt, indent=2), 'utf8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--backend', required=True)
    parser.add_argument('--wheelhouse', required=True)
    parser.add_argument('--native-directory', required=True)
    parser.add_argument('--seconds', type=float, default=600)
    args = parser.parse_args()
    result = build(args.work, python=args.python, backend=args.backend, wheelhouse=args.wheelhouse,
                   native_directory=args.native_directory, seconds=args.seconds)
    print(json.dumps(dict(passed=True, artifact=result['artifact'], manifest_sha256=result['manifest_sha256'])))


if __name__ == '__main__':
    main()
