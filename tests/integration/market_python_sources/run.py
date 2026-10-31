"""验证永久市场Python切片和历史包构建；纯导入阶段禁止业务副作用。"""
from pathlib import Path
import argparse
import json
import runpy
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import market_python_components as product
from native_support.process_startup import background_process_options


def probe(args):
    forbidden = []

    def audit(event, values):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system', 'mmap.__new__', 'sqlite3.connect'):
            forbidden.append(event)
            raise RuntimeError('business side effect during import-only verification')

    sys.addaudithook(audit)
    if args.component == 'market/hpr':
        projects = product.configuration()['legacy_projects']
        for name in ('guanheng-qmt-shm-agent', 'guanheng-qmt-shm-host'):
            sys.path.insert(0, str(ROOT / projects[name]['directory']))
        runpy.run_module('guanheng_qmt_shm.history_preparation_cli', run_name='market_import_only')
    else:
        runpy.run_path(str(args.slice / 'integrations/guanheng/source_market_service.py'), run_name='market_import_only')
    modules = {}
    for name, module in tuple(sys.modules.items()):
        file = getattr(module, '__file__', None)
        if file and name.startswith(('integrations.', 'guanheng_', 'guanheng.')) and Path(file).is_file():
            modules[name] = dict(path=str(file), sha256=product.digest(file))
    assert modules and not forbidden
    if args.component != 'market/hpr':
        expected = args.slice / 'connectors/qmt_shm/host/guanheng_qmt_shm/__init__.py'
        assert modules['guanheng_qmt_shm']['sha256'] == product.digest(expected)
        assert Path(modules['guanheng_qmt_shm']['path']).resolve() == expected.resolve()
    result = dict(passed=True, component=args.component, modules=modules, forbidden_events=forbidden,
                  executable=sys.executable, base_prefix=sys.base_prefix, SDK_calls=0, services_started=0,
                  hpr_legacy_own_modules_only=args.component == 'market/hpr')
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2), 'utf8')


def main(args):
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    before = product.source_inputs()
    runner_inputs = {member: product.digest(ROOT / member) for member in
                     ('scripts/source_market.py', Path(__file__).resolve().relative_to(ROOT).as_posix())}
    hpr_members = product.configuration()['components']['market/hpr']['files'].values()
    dependency_wheels = {row['wheel'] for row in hpr_members if 'wheel' in row}
    attributed_wheels = {row['wheel'] for row in hpr_members if row['kind'] == 'third-party-wheel-attribution'
                         and not row['member'].endswith('.dist-info/METADATA')}
    assert dependency_wheels == attributed_wheels
    slices = {}
    for name in product.configuration()['components']:
        target = work / name.replace('/', '-')
        receipt = product.materialize(name, target, wheel_dirs=args.wheel_dir)
        assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()} == set(receipt['files']) | {'PYTHON-COMPONENT.json'}
        assert all(product.digest(target / member) == sha for member, sha in receipt['files'].items())
        slices[name] = dict(path=str(target), files=len(receipt['files']), receipt_sha256=product.digest(target / 'PYTHON-COMPONENT.json'))
    first = product.build_legacy(work / 'build1', args.backend)
    second = product.build_legacy(work / 'build2', args.backend)
    assert {k: v['sha256'] for k, v in first['wheels'].items()} == {k: v['sha256'] for k, v in second['wheels'].items()}
    imports = {}
    for component, info in slices.items():
        target = work / (component.replace('/', '-') + '-import.json')
        command = [str(args.host_pythonw.resolve(strict=True)), '-I', '-B', str(Path(__file__).resolve()),
                   '--probe', '--component', component, '--slice', info['path'], '--output', str(target)]
        result = subprocess.run(command, capture_output=True, timeout=45, **background_process_options())
        (target.with_suffix('.log')).write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0, str(target.with_suffix('.log'))
        imported = json.loads(target.read_bytes())
        assert imported['passed'] and imported['SDK_calls'] == 0 and imported['services_started'] == 0
        imports[component] = dict(path=str(target), sha256=product.digest(target), modules=len(imported['modules']))
    # 原生历史入口仅核显式选择接线；原生编译由其组件验证承担。
    from source_market import python_source, verify_python_install
    assert python_source(work, None) == (ROOT, None)
    selected, identity = python_source(work / 'source-market-selection', 'market/history')
    assert identity['component'] == 'market/history'
    selected_receipt = json.loads((selected / 'PYTHON-COMPONENT.json').read_bytes())
    expected_members = {member: row['sha256'] for member, row in product.configuration()['components']['market/history']['files'].items()}
    assert selected_receipt['files'] == expected_members
    assert identity['receipt_sha256'] == product.digest(selected / 'PYTHON-COMPONENT.json')
    installed = work / 'source-market-installed-python'
    verify_python_install(installed, selected, identity)
    assert {p.relative_to(installed).as_posix(): product.digest(p) for p in installed.rglob('*') if p.is_file()} == expected_members
    verify_python_install(installed, selected, identity)
    failures = {}
    changed_receipt = work / 'changed-install-receipt'
    shutil.copytree(selected, changed_receipt)
    receipt_path = changed_receipt / 'PYTHON-COMPONENT.json'
    changed_body = json.loads(receipt_path.read_bytes())
    del changed_body['files']['integrations/guanheng/upstream-contracts.json']
    receipt_path.write_text(json.dumps(changed_body), 'utf8')
    try:
        verify_python_install(work / 'changed-install-output', changed_receipt, identity)
    except ValueError as exc:
        failures['changed_install_receipt_rejected'] = 'Python receipt changed' in str(exc)
    assert not (work / 'changed-install-output').exists()
    try:
        product.materialize('market/history', Path(slices['market/history']['path']))
    except FileExistsError:
        failures['existing_output_retained'] = True
    try:
        product.materialize('market/hpr', work / 'missing-wheel')
    except ValueError as exc:
        failures['missing_pinned_wheel_rejected'] = 'pinned third-party wheel required' in str(exc)
    original = product.CONFIG
    try:
        value = product.configuration()
        row = next(iter(value['components']['market/history']['files'].values()))
        row['sha256'] = '0' * 64
        changed = work / 'changed-config.json'
        changed.write_text(json.dumps(value), 'utf8')
        product.CONFIG = changed
        try:
            product.source_inputs('market/history')
        except ValueError as exc:
            failures['changed_source_identity_rejected'] = 'permanent source changed' in str(exc)
    finally:
        product.CONFIG = original
    try:
        product.relative('../outside.py')
    except ValueError:
        failures['escaping_member_rejected'] = True
    assert len(failures) == 5 and all(failures.values())
    assert before == product.source_inputs()
    assert all(product.digest(ROOT / member) == expected for member, expected in runner_inputs.items())
    result = dict(passed=True, slices=slices, imports=imports, boundary_checks=failures,
                  third_party_distributions_with_legal_files=len(attributed_wheels),
                  wheels=first['wheels'], reproducible=True, inputs_unchanged=True, inputs=dict(before, **runner_inputs),
                  SDK_calls=0, services_started=0, native_build_invoked=False, actual004_roles_reinstalled=False,
                  python=dict(executable=sys.executable, sha256=product.digest(sys.executable), base_prefix=sys.base_prefix,
                              version=sys.version),
                  host_pythonw=dict(path=str(args.host_pythonw), sha256=product.digest(args.host_pythonw)))
    (work / 'RESULT.json').write_text(json.dumps(result, sort_keys=True, indent=2), 'utf8')
    print(json.dumps(dict(passed=True, result=str(work / 'RESULT.json'), slices=slices)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--backend', type=Path)
    parser.add_argument('--wheel-dir', type=Path, action='append', default=[])
    parser.add_argument('--host-pythonw', type=Path)
    parser.add_argument('--component')
    parser.add_argument('--slice', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.probe:
        probe(args)
    else:
        if not all((args.work, args.backend, args.host_pythonw)):
            parser.error('--work, --backend and --host-pythonw required')
        main(args)
