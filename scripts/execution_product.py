"""从永久自有源码、固定WT及已批准覆盖干净构建模块B执行组件。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shlex
import shutil
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import native
from native_support.qmt_readonly_fixed import git_blobs, verify_snapshot, write_snapshot
from native_support.artifact import normal_path

_TOOLCHAIN_ENV = {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP',
    'INCLUDE', 'LIB', 'LIBPATH', 'VCTOOLSINSTALLDIR', 'VCINSTALLDIR', 'VSINSTALLDIR',
    'WINDOWSSDKDIR', 'WINDOWSSDKVERSION', 'UNIVERSALCRTSDKDIR', 'UCRTVERSION', 'VSLANG'}
_LINK_TARGETS = {'GuanhengCtaHost', 'GuanhengCtaRuntime', 'GuanhengStandardTrader',
                 'GuanhengOriginalExecutionFactory', 'GuanhengManagedStrategy'}
_EXTERNAL_BUILD_ROOT = Path('D:/wt-build')  # 显式D盘干净构建根；仅接收直属新叶，默认E盘ROOT/build保留。


def validate_workspace(work, *, prepared=False):
    """核本次工作根及所有现存父目录；拒C盘、上跳、重解析与重复新建。

    prepared仅供原Job内阶段重读已准备根，不授任意已有目录构建资格；
    阶段还需核PREPARED及源码快照身份。返回原绝对路径，不跟随链接改写根。
    """
    if (not work.is_absolute() or '..' in work.parts
            or not ((work.drive.upper() == 'E:' and work.is_relative_to(ROOT / 'build'))
                    or (work.drive.upper() == 'D:' and work.parent == _EXTERNAL_BUILD_ROOT))):
        raise ValueError('execution workspace must be under ROOT/build on E or a direct D:/wt-build leaf')
    if not prepared:
        try:
            work.lstat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError('execution build requires a new workspace directory')
    parent = work if prepared else work.parent
    while True:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('execution workspace directory is missing or linked')
        if parent == parent.parent:
            break
        parent = parent.parent
    return work


def prepared_identity(work, owned):
    """绑定原入口、来源根及永久自有输入；上游镜像不改变原自有身份。"""
    return dict(
        schema='guanheng.execution-build-prepared.v1',  # 仅构建准备证明，不授安装或业务运行资格。
        source_root=str(ROOT),  # 本次永久源码根，阶段必须从同一入口重读。
        work_directory=str(work),  # 已核物理构建根，禁止复制凭证到另一工作目录。
        entry_sha256=digest(regular(Path(__file__))),  # 实际构建入口原字节；中途改入口须重新构建。
        recipe_sha256=digest(regular(ROOT / 'config/execution-product-build.json')),  # 原声明字节，与源码集合一起固定。
        owned={name: row['sha256'] for name, row in sorted(owned.items())})  # 自有/覆盖原件SHA，不含后来镜像的WT头。


def verify_prepared(work):
    """阶段先核快照及当前永久来源；完整复用原快照校验，不调用构建工具。"""
    validate_workspace(work, prepared=True)
    path = work / 'PREPARED.json'
    if path.lstat().st_size > 4 * 1024 * 1024:
        raise ValueError('execution prepared receipt size')
    value = json.loads(regular(path))
    recipe = json.loads(regular(ROOT / 'config/execution-product-build.json'))
    owned = source_files(recipe)
    for row in recipe['overlays']:
        normal_path(row['path'])
        raw = regular(ROOT / row['path'])
        if digest(raw) != row['sha256']:
            raise ValueError('execution prepared overlay source changed')
        owned[row['path']] = dict(sha256=digest(raw))
    if value != prepared_identity(work, owned):
        raise ValueError('execution prepared source identity changed')
    snapshot = verify_snapshot(work / 'inputs/owned')
    if any(snapshot['files'].get(name, {}).get('sha256') != row['sha256'] for name, row in owned.items()):
        raise ValueError('execution prepared snapshot identity changed')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('execution build requires regular source files')
    return path.read_bytes()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def source_files(recipe, check=lambda: None):
    """只收声明的永久源码；拒绝重解析路径与二进制构建输入。"""
    names = set(recipe['owned_files'])
    suffixes = {'.cpp', '.c', '.h', '.hpp', '.cmake', '.txt', '.py', '.json'}
    for name in recipe['owned_directories']:
        normal_path(name)
        directory = ROOT / name
        if not directory.is_dir() or directory.lstat().st_file_attributes & 0x400:
            raise ValueError('invalid execution source directory')
        for path in directory.rglob('*'):
            check()
            if '__pycache__' in path.parts:
                continue
            if path.lstat().st_file_attributes & 0x400:
                raise ValueError('linked execution source')
            if path.is_file() and path.suffix in suffixes:
                names.add(path.relative_to(ROOT).as_posix())
    if not 1 <= len(names) <= 8192:
        raise ValueError('execution source closure capacity')
    result = {}
    for name in sorted(names):
        check()
        normal_path(name)
        raw = regular(ROOT / name)
        check()
        result[name] = dict(sha256=digest(raw), data=raw)
    standard = result.get('src/TraderQMT/StandardQmtTrader.cpp')
    if standard is None or standard['sha256'] != recipe['owned_standard_source_sha256']:
        raise ValueError('reviewed permanent Standard source mismatch')
    return result


def audit_link_inputs(directory, build, system_roots, trace):
    """同时核显式输入与实际库搜索；默认库和响应文件不能绕过来源检查。"""
    receipts = list(directory.glob('*.rsp'))
    if {p.stem for p in receipts} != _LINK_TARGETS:
        raise ValueError('execution actual linker receipt closure incomplete')
    build = build.resolve()
    roots = tuple(Path(p).resolve() for p in system_roots)
    inputs, bindings, project = {}, {}, set()

    def inspect(path):
        if not path.is_absolute():
            raise ValueError('execution linker receipt has a non-absolute input')
        path = path.resolve()
        own = path.is_relative_to(build)
        system = any(path.is_relative_to(p) for p in roots)
        if not own and not (system and path.suffix.lower() in ('.lib', '.obj')):
            raise ValueError('project binary input is outside the new build')
        if str(path) not in inputs:
            inputs[str(path)] = digest(regular(path))
        if own:
            project.add(str(path))

    for receipt in receipts:
        raw = regular(receipt)
        if not raw or len(raw) > 4 * 1024 * 1024:
            raise ValueError('execution linker receipt size')
        bindings[str(receipt)] = digest(raw)
        text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        for token in shlex.split(text, posix=False):
            token = token.strip('"')
            if token.lower().startswith('/def:'):
                token = token[5:].strip('"')
            inspect(Path(token))
    raw = regular(trace)
    if not raw or len(raw) > 32 * 1024 * 1024:
        raise ValueError('execution linker library trace size')
    bindings[str(trace)] = digest(raw)
    # MSVC搜索行以完整库路径和冒号结尾；标签可由本机语言决定。
    pattern = re.compile(r'^\s*[^:\r\n]*?\s([A-Za-z]:[\\/][^\r\n]+\.lib)\s*:\s*$', re.MULTILINE | re.IGNORECASE)
    searched = set(pattern.findall(raw.decode('utf-8', errors='replace')))
    if not searched:
        raise ValueError('execution actual library search trace is missing')
    for name in searched:
        inspect(Path(name))
    if not project:
        raise ValueError('missing execution link input evidence')
    return dict(receipts=bindings, actual_files=inputs, project_files=sorted(project),
                system_roots=[str(p) for p in roots], actual_library_search_files=sorted(searched))


def toolchain_inputs(env):
    """仅接受本次VC/SDK搜索根；移除外部编译/链接选项和CLR附加搜索。"""
    compiler = shutil.which('cl.exe', path=env['PATH'])
    if compiler is None:
        raise ValueError('execution build requires the MSVC compiler')
    vc = Path(compiler).resolve().parents[3]
    sdk = Path(env['WINDOWSSDKDIR']).resolve()
    if vc.parent.name.upper() != 'MSVC' or sdk.parent.name.lower() != 'windows kits':
        raise ValueError('execution compiler or SDK root mismatch')
    roots = (vc, sdk.parent)
    for name in ('INCLUDE', 'LIB'):
        allowed = (*roots, vc.parents[2] / 'Auxiliary/VS/include') if name == 'INCLUDE' else roots
        for value in env.get(name, '').split(';'):
            if value and not any(Path(value).resolve().is_relative_to(p) for p in allowed):
                raise ValueError('external execution toolchain search root')
    env['LIBPATH'] = ''
    for name in ('CL', '_CL_', 'LINK', '_LINK_', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS',
                 'RCFLAGS', 'CMAKE_TOOLCHAIN_FILE', 'CMAKE_PREFIX_PATH', 'LINK_REPRO'):
        env.pop(name, None)
    return compiler, roots


def phase(name, work):
    """不具业务能力的构建阶段；外层入口的Job拥有本阶段全部探测/解压后代。"""
    verify_prepared(work)
    if name == '_toolchain':
        env, tools = native.environment(work)
        env = {k.upper(): v for k, v in env.items() if k.upper() in _TOOLCHAIN_ENV}
        env.update(TEMP=str(work / 'temp'), TMP=str(work / 'temp'))
        save(work / 'TOOLCHAIN.json', dict(environment=env, tools=tools))
    elif name == '_git':
        recipe = json.loads(regular(work / 'inputs/owned/config/execution-product-build.json'))
        entries = git_blobs(ROOT, recipe['upstream_commit'], tuple(recipe['upstream_roots']))
        write_snapshot(work / 'inputs/upstream', entries, commit=recipe['upstream_commit'])
    elif name == '_dependencies':
        native.LOCK = work / 'inputs/owned/config/native-dependencies.json'
        native.dependencies(work, offline=True, audit=True)
    else:
        raise ValueError('unknown execution build phase')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True,
                        help='new ROOT/build directory on E, or explicit D:/wt-build/<new-leaf>')
    parser.add_argument('--archives', type=Path, required=True)
    parser.add_argument('--seconds', type=float, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 3600 or not 1 <= args.jobs <= 8:
        raise ValueError('invalid execution build budget')
    deadline = time.monotonic() + args.seconds
    work = validate_workspace(args.work)
    work.mkdir()
    (work / 'temp').mkdir()
    env = {k: v for k, v in os.environ.items() if k.upper() in
           {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PROGRAMDATA',
            'ALLUSERSPROFILE', 'PROGRAMFILES', 'PROGRAMFILES(X86)', 'PROGRAMW6432',
            'USERPROFILE', 'LOCALAPPDATA', 'APPDATA'}}
    env.update(TEMP=str(work / 'temp'), TMP=str(work / 'temp'),
               PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    commands = []

    def remaining():
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('execution clean build deadline')
        return left

    def run(argv, label, cwd=work):
        commands.append(dict(argv=[str(x) for x in argv], log=label + '.log'))
        save(work / 'COMMANDS.json', commands)
        result = native.run(argv, cwd=cwd, env=env, timeout=remaining(),
                            log=work / (label + '.log'), private_console=True)
        remaining()
        return result[0]

    remaining()
    recipe_raw = regular(ROOT / 'config/execution-product-build.json')
    recipe = json.loads(recipe_raw)
    if recipe['schema'] != 'guanheng.standard-execution-source-build.v1' or recipe['old_binary_inputs_allowed'] is not False:
        raise ValueError('unsupported execution source recipe')
    owned = source_files(recipe, remaining)
    overlay_paths = set()
    overlays = []
    for row in recipe['overlays']:
        normal_path(row['path'])
        raw = regular(ROOT / row['path'])
        if digest(raw) != row['sha256']:
            raise ValueError('approved execution overlay mismatch')
        old, new = set(), set()
        for line in raw.decode('utf-8').splitlines():
            if line.startswith('--- '): old.add(line[4:].split('\t')[0].removeprefix('a/'))
            if line.startswith('+++ '): new.add(line[4:].split('\t')[0].removeprefix('b/'))
        if old != set(row['files']) or new != old or overlay_paths & old:
            raise ValueError('approved execution overlay scope mismatch')
        overlay_paths.update(old)
        owned[row['path']] = dict(data=raw, sha256=digest(raw))
        overlays.append((row, raw))
    if overlay_paths != set(recipe['patched_files']):
        raise ValueError('execution overlay identity set mismatch')
    write_snapshot(work / 'inputs/owned', owned)
    save(work / 'PREPARED.json', prepared_identity(work, owned))
    remaining()
    entry = [sys.executable, '-I', '-B', Path(__file__).resolve()]
    run([*entry, '_toolchain', work], 'toolchain')
    toolchain = json.loads(regular(work / 'TOOLCHAIN.json'))
    env.update(toolchain['environment'])
    env.update(GIT_CEILING_DIRECTORIES=str(work / 'inputs'),
               UV_CACHE_DIR=str(work / 'temp/uv'), PIP_CACHE_DIR=str(work / 'temp/pip'),
               VERBOSE='1')
    tools = toolchain['tools']
    compiler, system_roots = toolchain_inputs(env)
    run([*entry, '_git', work], 'fixed-git')
    original = verify_snapshot(work / 'inputs/upstream')
    up = work / 'inputs/upstream'
    for name, identity in recipe['patched_files'].items():
        remaining()
        if original['files'][name]['sha256'] != identity['baseline_sha256']:
            raise ValueError('execution overlay baseline mismatch')
        # 既有批准覆盖以LF维护；规范化只发生在本次隔离快照的覆盖文件。
        (up / name).write_bytes(regular(up / name).replace(b'\r\n', b'\n'))
    for index, (row, raw) in enumerate(overlays):
        patch = work / ('overlay-' + str(index) + '.patch')
        patch.write_bytes(raw)
        for mode in (['--check'], []):
            run(['git', '-c', 'core.autocrlf=false', '-c', 'core.safecrlf=false',
                 'apply', '--no-index', *mode, patch],
                'overlay-' + str(index) + ('-check' if mode else '-apply'), up)
    manifest = original
    for name, identity in recipe['patched_files'].items():
        actual = digest(regular(up / name))
        if actual != identity['normalized_result_sha256']:
            raise ValueError('execution approved overlay result mismatch')
        manifest['files'][name] = dict(sha256=actual)
    save(up / 'input.json', manifest)
    verify_snapshot(up)
    own = work / 'inputs/owned'
    # 原自有模块使用../Includes等相邻头；镜像同一已验证WT快照，保持唯一来源。
    owned_manifest = verify_snapshot(own)
    save(work / 'OWNED-PERMANENT.json', owned_manifest)
    for name, identity in manifest['files'].items():
        remaining()
        if name in owned_manifest['files']:
            raise ValueError('owned and upstream execution source paths overlap')
        target = own / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(regular(up / name))
        owned_manifest['files'][name] = identity
    save(own / 'input.json', owned_manifest)
    verify_snapshot(own)
    save(work / 'SOURCE.json', dict(recipe_sha256=digest(recipe_raw), upstream_commit=recipe['upstream_commit'],
         owned={n: x['sha256'] for n, x in owned.items()}, overlays=recipe['overlays'],
         existing_approved_behavior_only=True, prior_build_source_inputs=0, prior_binary_inputs=0))
    downloads = work / 'downloads'; downloads.mkdir()
    lock = json.loads(regular(own / 'config/native-dependencies.json'))
    for dep in lock['dependencies']:
        raw = regular(args.archives / dep['archive'])
        if digest(raw) != dep['sha256']:
            raise ValueError('execution dependency archive mismatch')
        (downloads / dep['archive']).write_bytes(raw)
        remaining()
    run([*entry, '_dependencies', work], 'dependencies')
    build = work / 'cmake'
    if build.exists():
        raise ValueError('execution build directory must be absent')
    run([tools['cmake'], '-S', own / recipe['source_cmake'], '-B', build, '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=OFF', '-DGH_STANDARD_CTA_HOST=ON',
         '-DCMAKE_MAKE_PROGRAM=' + tools['ninja'], '-DCMAKE_CXX_COMPILER=' + compiler,
         '-DCMAKE_C_COMPILER=' + compiler, '-DWT_DEPS_DIR=' + str(work / 'deps'),
         '-DPython3_EXECUTABLE=' + sys.executable, '-DGH_FIXED_UPSTREAM_ROOT=' + str(up),
         '-DGH_FIXED_OWN_ROOT=' + str(own)], 'configure')
    # configure自己的编译器探针可以生成新对象；本次目录在configure前不存在。
    run([tools['cmake'], '--build', build, '--target', recipe['target'], '--parallel', str(args.jobs)], 'build')
    run([tools['ninja'], '-C', build, '-t', 'commands', recipe['target']], 'target-commands')
    binaries = audit_link_inputs(build / 'link-inputs', build, system_roots, work / 'build.log')
    install = work / 'installation'
    run([tools['cmake'], '--install', build, '--prefix', install], 'install')
    for name in ('TraderQMTStandard', 'WtExeFact'):
        for suffix in ('.lib', '.exp'):
            matches = list(build.rglob(name + suffix))
            if len(matches) != 1:
                raise ValueError('execution fresh import library missing or ambiguous')
            target = install / 'lib' / (name + suffix)
            if target.exists() and regular(target) != regular(matches[0]):
                raise ValueError('execution installed library mismatch')
            shutil.copyfile(matches[0], target)
    verify_snapshot(up); verify_snapshot(own)
    if any(digest(regular(ROOT / n)) != x['sha256'] for n, x in owned.items()):
        raise ValueError('permanent execution source changed during build')
    run([*entry, '_dependencies', work], 'dependencies-after')
    outputs = {p.relative_to(install).as_posix(): digest(regular(p)) for p in install.rglob('*') if p.is_file()}
    required = {'app/GuanhengCtaHost.exe', 'app/GuanhengCtaRuntime.dll',
                'app/traders/TraderQMTStandard.dll', 'app/executers/WtExeFact.dll',
                'app/strategies/GuanhengManagedStrategy.dll'}
    if not required <= outputs.keys():
        raise ValueError('execution installed product closure incomplete')
    save(work / 'RESULT.json', dict(schema='guanheng.standard-execution-clean-build.v1', passed=True,
         source=str(work / 'SOURCE.json'), source_sha256=digest(regular(work / 'SOURCE.json')),
         installation=str(install), outputs=outputs, fresh_project_binary_inputs=binaries,
         build_directory_preexisted=False, previous_object_or_library_inputs=0,
         business_runtime_started=False, real_orders=0, real_cancels=0))
    print(json.dumps(dict(passed=True, installed_files=len(outputs), prior_binary_inputs=0)))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] in ('_toolchain', '_git', '_dependencies'):
        phase(sys.argv[1], Path(sys.argv[2]))
    else:
        main()
