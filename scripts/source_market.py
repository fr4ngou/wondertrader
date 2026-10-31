"""冻结固定上游与自有查询闭包，构建独立GuanhengMarket安装组件；不接运行服务。"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import time
import zipfile

import native

ROOT = Path(__file__).resolve().parents[1]
BASE = '08b230dd05facf6d650d949bfe51054115a2ecb1'
PYTHON_ROOTS = ('integrations/guanheng', 'integrations/guanheng_market_client',
                'connectors/qmt_shm/agent/guanheng_qmt_shm_agent',
                'connectors/qmt_shm/host/guanheng_qmt_shm')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required_files():
    lock = json.loads((ROOT / 'config/native-dependencies.json').read_text(encoding='utf8'))
    return {'app/GuanhengNativeBarFile.dll', 'app/WtDtHelper.dll',
        'integrations/guanheng/source_market_service.py', 'licenses/WonderTrader-MIT.txt',
        *('licenses/' + entry['name'] + '.txt' for entry in lock['dependencies'])}


def verify_previous(previous):
    """先核完整文件集合和规范相对路径，再允许复制已冻结的原生候选。"""
    prior = previous / 'installed'
    receipt = json.loads((prior / 'INSTALLATION.json').read_text(encoding='utf8'))
    if (receipt['schema'] != 'guanheng.source-market-installation.v1'
            or receipt['component'] != 'GuanhengMarket' or receipt['framework_changes']):
        raise ValueError('source market native provenance differs')
    old_inputs = previous / 'INPUTS.json'
    inputs = json.loads(old_inputs.read_text(encoding='utf8'))
    if (digest(old_inputs) != receipt['input_sha256'] or inputs.get('upstream_base') != BASE
            or inputs.get('framework_changes') != []):
        raise ValueError('source market native inputs differ')
    for name in receipt['files']:
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or path.as_posix() != name
                or any(part in ('.', '..') or ':' in part or chr(92) in part for part in path.parts)
                or not (prior / name).resolve().is_relative_to(prior.resolve())):
            raise ValueError('source market installation path differs')
    actual = set()
    for path in prior.rglob('*'):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('source market installation has linked input')
        if path.is_file():
            actual.add(path.relative_to(prior).as_posix())
    if actual != set(receipt['files']) | {'INSTALLATION.json'}:
        raise ValueError('source market installation file set differs')
    # 旧候选允许缺静态许可证，以便补齐；两枚原生库和正式入口必须原本存在。
    if not {'app/GuanhengNativeBarFile.dll', 'app/WtDtHelper.dll',
            'integrations/guanheng/source_market_service.py', 'licenses/WonderTrader-MIT.txt'} <= set(receipt['files']):
        raise ValueError('source market installation required input missing')
    for name, expected in receipt['files'].items():
        if digest(prior / name) != expected:
            raise ValueError('source market native installation changed')
    return prior, receipt


def python_source(work, component):
    """显式兼容版本来自永久成员表；缺省保持仓库当前源码选择。"""
    if component is None:
        return ROOT, None
    if component != 'market/history':
        raise ValueError('GuanhengMarket requires market/history Python contract')
    from market_python_components import materialize
    root = work / 'python-component'
    receipt = materialize(component, root)
    return root, dict(component=component, receipt_sha256=digest(root / 'PYTHON-COMPONENT.json'),
                      inputs=receipt['inputs'])


def verify_python_install(installed, python_root, identity):
    """原CMake过滤Python文件；显式切片另带数据契约，按同一成员表补齐并核验。"""
    if identity is None:
        return
    receipt_path = python_root / 'PYTHON-COMPONENT.json'
    raw = receipt_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != identity['receipt_sha256']:
        raise ValueError('source market Python receipt changed')
    receipt = json.loads(raw)
    if receipt['component'] != identity['component'] or receipt['inputs'] != identity['inputs']:
        raise ValueError('source market Python identity changed')
    for member, expected in receipt['files'].items():
        if digest(python_root / member) != expected:
            raise ValueError('source market Python source changed')
        target = installed / member
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(python_root / member, target)
        if digest(target) != expected:
            raise ValueError('source market Python installation changed')
    if digest(receipt_path) != identity['receipt_sha256']:
        raise ValueError('source market Python receipt changed during installation')


def build(work, baseline, deadline, *, python_component=None):
    """仅使用固定基线的C++源码；共享工作树提供明确列出的Python和安装规则。"""
    work, baseline = work.resolve(), baseline.resolve(strict=True)
    if work.exists():
        raise ValueError('fresh source market build root required')
    manifest = json.loads((baseline / 'SOURCE-MANIFEST.json').read_text(encoding='utf8'))
    if manifest['baseline'] != BASE:
        raise ValueError('fixed baseline differs')
    upstream = baseline / 'snapshot'
    for name, expected in manifest['upstream_files'].items():
        if digest(upstream / name) != expected:
            raise ValueError('fixed upstream content differs')
    work.mkdir(parents=True)
    python_root, python_identity = python_source(work, python_component)
    snapshot = work / 'snapshot'
    shutil.copytree(upstream, snapshot, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # 只替换自有Python闭包；原生金融框架始终来自已经核过摘要的固定来源。
    for name in PYTHON_ROOTS:
        destination = snapshot / name
        if destination.exists():
            # 目标先验证为本次fresh快照内的明确子目录；不触及原基线/共享树。
            if not destination.resolve().is_relative_to(snapshot.resolve()):
                raise ValueError('snapshot destination escapes build root')
            shutil.rmtree(destination)
        shutil.copytree(python_root / name, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(ROOT / 'cmake/native/market_install.cmake', snapshot / 'cmake/native/market_install.cmake')
    cmake_source = snapshot / 'cmake/native/CMakeLists.txt'
    text = cmake_source.read_text(encoding='utf8')
    if 'market_install.cmake' not in text:
        text += '\ninclude("${CMAKE_CURRENT_LIST_DIR}/market_install.cmake")\n'
    # 沿既有原生构建的Windows头前置/宏配置；不修改上游任何C++文件。
    if '/FIobjbase.h' not in text:
        text = text.replace('add_compile_options(/utf-8 /EHsc /W3)',
            'add_compile_options(/utf-8 /EHsc /W3 "$<$<COMPILE_LANGUAGE:CXX>:/FIobjbase.h>")\n'
            '  add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN)')
    cmake_source.write_text(text, encoding='utf8')
    for name, expected in manifest['upstream_files'].items():
        if digest(snapshot / name) != expected:
            raise ValueError('source market unexpectedly changes framework')
    files = {p.relative_to(snapshot).as_posix(): digest(p) for p in snapshot.rglob('*') if p.is_file()}
    inputs = dict(schema='guanheng.source-market-build.v1', upstream_base=BASE,
        framework_changes=[], source_identity_kind='frozen-uncommitted-inputs', files=files,
        driver_sha256=digest(Path(__file__)), python_component=python_identity)
    (work / 'INPUTS.json').write_text(json.dumps(inputs, indent=2, sort_keys=True), encoding='utf8')
    env, tools = native.environment(work)
    (work / 'TOOLS.json').write_text(json.dumps(tools, indent=2), encoding='utf8')

    def run(argv, name, maximum):
        remaining = deadline - time.monotonic() - 10
        if remaining <= 0:
            raise TimeoutError('original source market build deadline')
        with contextlib.redirect_stdout(io.StringIO()):
            native.run(argv, cwd=snapshot, env=env, log=work / (name + '.log'),
                timeout=min(maximum, remaining), private_console=True, max_output_bytes=8388608)
        print(json.dumps(dict(stage=name, status='passed')), flush=True)

    cmake = work / 'cmake'
    run([tools['cmake'], '-S', snapshot / 'cmake/native', '-B', cmake, '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DWT_DEPS_DIR=' + str(ROOT / 'build/native/deps'),
         '-DCMAKE_MAKE_PROGRAM=' + tools['ninja'], '-DPython3_EXECUTABLE=' + str(Path(sys.executable).resolve()),
         '-DBUILD_TESTING=OFF'], 'configure', 150)
    run([tools['cmake'], '--build', cmake, '--target', 'GuanhengNativeBarFile', 'WtDtHelper',
         '--parallel', '2'], 'build', 900)
    installed = work / 'installed'
    run([tools['cmake'], '--install', cmake, '--prefix', installed, '--component', 'GuanhengMarket'], 'install', 90)
    verify_python_install(installed, python_root, python_identity)
    for name, expected in files.items():
        if digest(snapshot / name) != expected:
            raise ValueError('frozen source changed during build')
    packaged = {p.relative_to(installed).as_posix(): digest(p) for p in installed.rglob('*') if p.is_file()}
    if not required_files() <= set(packaged):
        raise ValueError('source market installation incomplete')
    installation = dict(schema='guanheng.source-market-installation.v1', component='GuanhengMarket',
        input_sha256=digest(work / 'INPUTS.json'), files=packaged, framework_changes=[], production_switch=False)
    (installed / 'INSTALLATION.json').write_text(json.dumps(installation, sort_keys=True, indent=2), encoding='utf8')
    archive = work / 'GuanhengMarket.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(installed.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(installed).as_posix())
    result = dict(status='passed', component='GuanhengMarket', install_root=str(installed),
        file_count=len(packaged), zip_sha256=digest(archive), input_sha256=digest(work / 'INPUTS.json'))
    (work / 'BUILT.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result), flush=True)


def repackage(work, previous, *, python_component=None):
    """复用逐文件核验的原生安装，只更新本仓明确Python闭包；原候选保持不可变。"""
    work, previous = work.resolve(), previous.resolve(strict=True)
    if work.exists():
        raise ValueError('fresh source market package root required')
    prior, receipt = verify_previous(previous)
    installed = work / 'installed'
    shutil.copytree(prior, installed)
    python_root, python_identity = python_source(work, python_component)
    source_files = {}
    for name in PYTHON_ROOTS:
        destination = installed / name
        if not destination.resolve().is_relative_to(installed.resolve()):
            raise ValueError('package destination escapes fresh root')
        shutil.rmtree(destination)
        shutil.copytree(python_root / name, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        source_files.update({p.relative_to(installed).as_posix(): digest(p)
                             for p in destination.rglob('*') if p.is_file()})
    verify_python_install(installed, python_root, python_identity)
    lock_path = ROOT / 'config/native-dependencies.json'
    lock = json.loads(lock_path.read_text(encoding='utf8'))
    license_files = {}
    for entry in lock['dependencies']:
        source = ROOT / 'build/native/deps' / entry['name'] / entry['license_file']
        target = installed / 'licenses' / (entry['name'] + '.txt')
        shutil.copyfile(source, target)
        license_files[target.relative_to(installed).as_posix()] = digest(source)
    inputs = dict(schema='guanheng.source-market-repackage.v1', upstream_base=BASE,
        framework_changes=[], previous_input_sha256=receipt['input_sha256'],
        previous_installation_sha256=digest(prior / 'INSTALLATION.json'),
        source_identity_kind='frozen-uncommitted-inputs', python_files=source_files,
        dependency_lock_sha256=digest(lock_path), license_files=license_files,
        driver_sha256=digest(Path(__file__)), python_component=python_identity)
    (work / 'INPUTS.json').write_text(json.dumps(inputs, indent=2, sort_keys=True), encoding='utf8')
    packaged = {p.relative_to(installed).as_posix(): digest(p) for p in installed.rglob('*')
                if p.is_file() and p.name != 'INSTALLATION.json'}
    if not required_files() <= set(packaged):
        raise ValueError('source market installation incomplete')
    for name, expected in receipt['files'].items():
        if name.startswith('app/') and packaged.get(name) != expected:
            raise ValueError('source market repackage changes native binary')
    receipt = dict(schema='guanheng.source-market-installation.v1', component='GuanhengMarket',
        input_sha256=digest(work / 'INPUTS.json'), files=packaged, framework_changes=[], production_switch=False)
    (installed / 'INSTALLATION.json').write_text(json.dumps(receipt, sort_keys=True, indent=2), encoding='utf8')
    archive = work / 'GuanhengMarket.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(installed.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(installed).as_posix())
    result = dict(status='passed', component='GuanhengMarket', install_root=str(installed),
        file_count=len(packaged), zip_sha256=digest(archive), input_sha256=digest(work / 'INPUTS.json'),
        native_rebuilt=False)
    (work / 'BUILT.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--baseline', type=Path)
    sources.add_argument('--reuse-native', type=Path)
    parser.add_argument('--deadline', type=float, required=True)
    parser.add_argument('--python-component', choices=['market/history'])
    arguments = parser.parse_args()
    if arguments.reuse_native:
        repackage(arguments.work, arguments.reuse_native, python_component=arguments.python_component)
    else:
        build(arguments.work, arguments.baseline, arguments.deadline, python_component=arguments.python_component)
