"""Fixed-profile stage assembly, invoked only by the original native.py owner."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

from . import qmt_readonly_fixed as fixed
from .artifact import archive, sha256, verify_archive, write_manifest


def read_record(path, fields):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or not set(fields).issubset(value):
        raise ValueError('invalid fixed build record: ' + path.name)
    return value


def build_outputs(work):
    root = work / 'cmake'
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(root.rglob('*'))
            if path.is_file() and path.suffix.lower() in {'.obj', '.lib', '.dll', '.exe'}}


def compiled_inputs(work, *, source_root=None):
    commands = json.loads((work / 'cmake/compile_commands.json').read_text(encoding='utf-8'))
    dependencies = {}
    for line in (work / 'logs/native-dependencies.log').read_text(encoding='utf-8').splitlines():
        if line.startswith('    '):
            path = Path(line.strip())
            # Ninja -C records project headers relative to its build directory.
            # Resolve against that owner, never the Python process CWD.
            if not path.is_absolute():path = work / 'cmake' / path
            path = path.resolve()
            if str(path) not in dependencies and path.is_file():
                if source_root is not None and path.is_relative_to(source_root.resolve()) and not path.is_relative_to(work.resolve()):
                    raise ValueError('actual compiler dependency escaped fixed snapshots into current source')
                dependencies[str(path)] = sha256(path)
    if not dependencies or not commands:
        raise ValueError('actual compiler dependency records are missing')
    link_log = work / 'logs/native-link-commands.log'
    link_commands = [line for line in link_log.read_text(encoding='utf-8').splitlines()
                     if 'vs_link_' in line or '/out:' in line.lower()]
    if not link_commands:raise ValueError('actual generated link commands are missing')
    return {'translation_units': commands, 'dependencies': dependencies, 'link_commands': link_commands,
            'link_log_sha256': sha256(link_log)}


def require_tests(path: Path):
    root = ET.parse(path).getroot()
    cases = root.findall('.//testcase')
    if not cases or any(case.find(tag) is not None for case in cases for tag in ('failure', 'error', 'skipped')):
        raise ValueError('fixed profile requires nonempty passing CTest results without skips')
    expected = {'nqp-' + name for name in ('fixture', 'regression', 'supplemental', 'http', 'drain', 'abi', 'no-connect', 'cng')}
    if {case.attrib.get('name') for case in cases} != expected:
        raise ValueError('fixed profile CTest set differs from required qualification')


def execute(owner, args, work, env, tools, receipt, stage, save):
    """Use the original runner/receipt/install/archive; no standalone publisher."""
    command = args.command
    if args.calendar_owner_source:
        raise ValueError('calendar owner is outside qmt-readonly-fixed profile')
    if command in ('doctor', 'deps'):
        return
    controlled = args.qmt_source.resolve(strict=True) if args.qmt_source else None
    selected_source = os.path.normcase(str(controlled)) if controlled else None
    actual_tools = {name: {'path': str(Path(path).resolve()), 'sha256': sha256(Path(path))} for name, path in tools.items()}
    compiler_path = shutil.which('cl', path=env.get('PATH'))
    if compiler_path:
        actual_tools['compiler'] = {'path': str(Path(compiler_path).resolve()), 'sha256': sha256(Path(compiler_path))}
    for name in ('link', 'lib', 'rc', 'mt'):
        path = shutil.which(name, path=env.get('PATH'))
        if path:actual_tools[name] = {'path': str(Path(path).resolve()), 'sha256': sha256(Path(path))}

    def inputs(required=True):
        return fixed.prepare_inputs(owner.ROOT, work, qmt_source=controlled, require_qmt=required)

    def bind_current(expected):
        fixed.require_identity(inputs(), expected)
        for name in ('upstream', 'owned', 'qmt'):
            fixed.verify_snapshot(work / 'inputs' / name, expected[name])

    def require_built():
        built = read_record(work / 'built-source.json', ('fixed_identity', 'tools', 'controlled_source', 'build_cache_sha256', 'build_outputs', 'compiled_inputs_sha256'))
        if built.get('tools') != actual_tools or built.get('controlled_source') != selected_source:
            raise ValueError('fixed toolchain or external source selection changed; use the configured inputs')
        bind_current(built['fixed_identity'])
        if built['build_cache_sha256'] != sha256(work / 'cmake/CMakeCache.txt') or built['build_outputs'] != build_outputs(work):
            raise ValueError('fixed build cache or outputs changed; rebuild')
        if built['compiled_inputs_sha256'] != sha256(work / 'compiled-inputs.json'):
            raise ValueError('compiler input evidence changed; rebuild')
        recorded = read_record(work / 'compiled-inputs.json', ('dependencies',))
        if not isinstance(recorded['dependencies'], dict) or not recorded['dependencies']:
            raise ValueError('compiler input evidence is empty')
        if any(not Path(path).is_file() or sha256(Path(path)) != digest for path, digest in recorded['dependencies'].items()):
            raise ValueError('actual compiler dependency changed; rebuild')
        return built

    if command == 'verify':
        if not args.archive or not args.sha256:
            raise ValueError('verify requires --archive and trusted --sha256')
        extracted = work / 'verified' / uuid.uuid4().hex
        manifest = verify_archive(args.archive.resolve(), args.sha256, extracted)
        if manifest['provenance'].get('profile') != fixed.PROFILE:
            raise ValueError('archive profile differs from requested profile')
        relocated(owner, work, env, stage, extracted, controlled, expected=manifest['provenance']['fixed_sources'])
        receipt['artifact'] = {'path': str(args.archive.resolve()), 'sha256': args.sha256,
                               'qualification': 'binary-and-http' if controlled else 'archive-and-binary'}
        return

    identity = inputs(command in ('test', 'package', 'all'))
    receipt['source'] = fixed.source_identity(owner.ROOT, identity)
    receipt['fixed_identity'] = identity
    save()
    if command in ('configure', 'build', 'all'):
        compiler = shutil.which('cl', path=env.get('PATH'))
        if not compiler:raise RuntimeError('MSVC compiler is missing')
        compiler = Path(compiler).as_posix()
        cache = work / 'cmake/CMakeCache.txt'
        if cache.exists():
            previous = owner.configured_compiler(work)
            if os.path.normcase(os.path.normpath(previous)) != os.path.normcase(os.path.normpath(compiler)):
                raise ValueError('fixed profile compiler changed; use a new work directory')
            compiler = previous
        owned = work / 'inputs/owned'
        argv = [tools['cmake'], '-S', owned / 'cmake/native/qmt_readonly_fixed', '-B', work / 'cmake', '-G', 'Ninja',
                '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=' + ('ON' if identity['qmt'] else 'OFF'),
                '-DCMAKE_CXX_COMPILER:FILEPATH=' + compiler, '-DCMAKE_C_COMPILER:FILEPATH=' + compiler,
                '-DCMAKE_MAKE_PROGRAM=' + tools['ninja'], '-DWT_DEPS_DIR=' + str(work / 'deps'),
                '-DPython3_EXECUTABLE=' + sys.executable, *fixed.cmake_arguments(work)]
        stage('configure', argv)
        fixed.require_identity(inputs(required=False), identity)
        (work / 'configured.json').write_text(json.dumps({'fixed_identity': identity, 'tools': actual_tools, 'controlled_source': selected_source}, sort_keys=True), encoding='utf-8')
    if command in ('build', 'all'):
        configured = read_record(work / 'configured.json', ('fixed_identity', 'tools', 'controlled_source'))
        fixed.require_identity(configured['fixed_identity'], identity)
        if configured.get('tools') != actual_tools or configured.get('controlled_source') != selected_source:
            raise ValueError('fixed configure toolchain or source selection changed')
        argv = [tools['cmake'], '--build', work / 'cmake', '--parallel', str(args.jobs)]
        if args.clean_first:argv.append('--clean-first')
        stage('build', argv)
        stage('native-dependencies', [tools['ninja'], '-C', work / 'cmake', '-t', 'deps'], 60)
        stage('native-link-commands', [tools['ninja'], '-C', work / 'cmake', '-t', 'commands'], 60)
        (work / 'compiled-inputs.json').write_text(json.dumps(compiled_inputs(work, source_root=owner.ROOT), indent=2), encoding='utf-8')
        fixed.require_identity(inputs(required=False), identity)
        built = {'profile': fixed.PROFILE, 'fixed_identity': identity, 'tools': actual_tools, 'controlled_source': selected_source,
                 'build_cache_sha256': sha256(work / 'cmake/CMakeCache.txt'), 'build_outputs': build_outputs(work),
                 'compiled_inputs_sha256': sha256(work / 'compiled-inputs.json')}
        (work / 'built-source.json').write_text(json.dumps(built, sort_keys=True), encoding='utf-8')
    if command in ('test', 'package', 'all'):
        require_built()
        stage('ctest', [tools['ctest'], '--test-dir', work / 'cmake', '--output-on-failure', '--output-junit', work / 'ctest.xml'], 900)
        require_tests(work / 'ctest.xml')
        # Existing pipeline regressions execute a real pinned wheel backend.
        # This isolated fixture is not installed or granted runtime SDK status.
        fixture_output = work / 'pipeline-sdk-fixture' / uuid.uuid4().hex
        argv = [sys.executable, '-B', work / 'inputs/owned/scripts/client_sdk.py', '--work', work / 'pipeline-sdk', '--output', fixture_output]
        if args.offline:argv.append('--offline')
        stage('pipeline-sdk-fixture', argv, 120)
        fixture = json.loads((fixture_output / 'receipt.json').read_text(encoding='utf-8'))
        env['GH_CLIENT_BACKEND_WHEEL'] = fixture['backend']
        stage('pipeline-tests', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', work / 'inputs/owned/tests/build_pipeline', '-v'], 240)
        require_built()
    if command in ('package', 'all'):
        identifier = 'dev-qmt-readonly-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        package = work / 'packages' / identifier
        stage('install', [tools['cmake'], '--install', work / 'cmake', '--prefix', package])
        lock = json.loads((owner.ROOT / 'config/native-dependencies.json').read_text(encoding='utf-8'))
        for dependency in lock['dependencies']:
            shutil.copyfile(work / 'deps' / dependency['name'] / dependency['license_file'], package / 'licenses' / (dependency['name'] + '.txt'))
        compiler = owner.configured_compiler(work)
        version = subprocess.run([compiler], env=env, capture_output=True, text=True, errors='replace', timeout=30)
        provenance = {**fixed.source_identity(owner.ROOT, identity), 'profile': fixed.PROFILE,
                      'upstream_base_commit': fixed.WT_COMMIT, 'fixed_sources': {'wt_commit': fixed.WT_COMMIT, 'qmt_commit': fixed.QMT_COMMIT,
                      'qmt_manifest_sha256': sha256(work / 'inputs/qmt/input.json'), 'identity_sha256': identity['input_sha256']},
                      'platform': sys.platform, 'architecture': 'AMD64', 'dependencies': lock,
                      'toolchain': {'compiler': compiler, 'compiler_version': (version.stdout + version.stderr).splitlines()[:2],
                      'cmake': subprocess.check_output([tools['cmake'], '--version'], text=True).splitlines()[0],
                      'ninja': subprocess.check_output([tools['ninja'], '--version'], text=True).strip()},
                      'tests': receipt['stages'], 'build_cache_sha256': sha256(work / 'cmake/CMakeCache.txt'),
                      'tools': actual_tools, 'compiled_inputs_sha256': sha256(work / 'compiled-inputs.json')}
        require_built()
        write_manifest(package, provenance)
        bundle = work / 'packages' / (identifier + '.zip')
        digest = archive(package, bundle)
        extracted = work / 'package-smoke' / identifier
        verify_archive(bundle, digest, extracted)
        relocated(owner, work, env, stage, extracted, controlled, expected=provenance['fixed_sources'])
        require_built()
        receipt['artifact'] = {'path': str(bundle), 'sha256': digest, 'qualification': 'binary-and-http'}


def relocated(owner, work, env, stage, extracted, controlled, *, expected):
    """Use only extracted tooling/binaries; private fixed input stays external."""
    app = extracted / 'app'
    validation = extracted / 'validation'
    run_id = uuid.uuid4().hex
    output = work / 'relocation' / run_id
    previous = env.copy()
    try:
        # Leave only package/system DLL lookup roots. Python uses its explicit
        # interpreter path and all test source comes from validation in the ZIP.
        system = Path(os.environ.get('SystemRoot', 'C:/Windows'))
        env['PATH'] = os.pathsep.join(map(str, (app, system / 'System32', system)))
        env.pop('PYTHONPATH', None)
        env.pop('GH_QMT_SOURCE_ROOT', None)
        env.pop('GH_CALENDAR_OWNER_SOURCE', None)
        dispatch = validation / 'tests/integration/qmt_readonly_bootstrap/fixed_checks.py'
        common = ['--owned-root', validation, '--bin-root', app, '--work', output, '--installed']
        stage('package-binary-' + run_id, [sys.executable, '-S', '-B', dispatch, '--kind', 'binary', *common], 180, cwd=app)
        if controlled is not None:
            fixture = output / 'external-qmt'
            entries = fixed.git_blobs(controlled, fixed.QMT_COMMIT, fixed.QMT_PATHS)
            fixed.write_snapshot(fixture, entries, commit=fixed.QMT_COMMIT)
            if sha256(fixture / 'input.json') != expected['qmt_manifest_sha256']:
                raise ValueError('relocated external QMT input differs from package qualification')
            stage('package-http-' + run_id, [sys.executable, '-S', '-B', dispatch, '--kind', 'http', '--qmt-fixture', fixture, *common], 420, cwd=app)
            fixed.verify_snapshot(fixture)
    finally:
        env.clear()
        env.update(previous)
