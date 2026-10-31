"""CTest/relocation dispatch into the original explicit integration test owners."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', required=True, choices=('fixture', 'regression', 'supplemental', 'http', 'drain', 'abi', 'no-connect', 'cng', 'binary'))
    parser.add_argument('--owned-root', type=Path, required=True)
    parser.add_argument('--bin-root', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--qmt-fixture', type=Path)
    parser.add_argument('--installed', action='store_true')
    args = parser.parse_args()
    owned = args.owned_root.resolve(strict=True)
    binaries = args.bin_root.resolve(strict=True)
    root = args.work.resolve() / (args.kind + '-' + uuid.uuid4().hex)
    root.mkdir(parents=True)
    reports = []

    def call(relative, parameters, timeout=180):
        # Installed validation uses only stdlib and explicitly located package
        # helpers. Skip unrelated machine site/.pth initialization in children.
        argv = [sys.executable, '-S', '-B', owned / 'tests/integration' / relative, *parameters]
        result = subprocess.run([str(v) for v in argv], cwd=binaries, capture_output=True, timeout=timeout)
        log = root / ('command-' + str(len(reports)) + '.log')
        log.write_bytes(result.stdout + result.stderr)
        reports.append({'argv': [str(v) for v in argv], 'cwd': str(binaries), 'exit': result.returncode,
                        'log': str(log), 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()})
        print(result.stdout.decode('utf-8', errors='replace'), end='', flush=True)
        if result.returncode:
            print(result.stderr.decode('utf-8', errors='replace'), file=sys.stderr)
            raise RuntimeError('integration command failed: ' + str(log))

    probe_root = binaries.parent / 'validation/bin' if args.installed else binaries
    library = binaries / 'traders/TraderQMTReadOnly.dll'
    def fixture_parameters(probe, cwd=binaries):
        return ['--probe', probe_root / probe, '--library', cwd / 'traders/TraderQMTReadOnly.dll', '--cwd', cwd, '--work', root / 'cases']
    if args.kind in ('fixture', 'binary'):
        parameters = fixture_parameters('NqpFixtureProbe.exe')
        if args.kind == 'binary':
            parameters += ['--only', 'happy', 'empty', 'source-failure-positions']
        call('qmt_readonly_bootstrap/run.py', parameters)
        if args.kind == 'fixture':
            summary = list((root / 'cases').glob('cases-*/summary.json'))
            if len(summary) != 1:raise ValueError('fixture summary missing or ambiguous')
            args.work.mkdir(parents=True, exist_ok=True)
            (args.work / 'fixture-result.json').write_text(json.dumps({'path': str(summary[0]), 'sha256': hashlib.sha256(summary[0].read_bytes()).hexdigest()}), encoding='utf-8')
    if args.kind == 'regression':
        call('qmt_readonly_bootstrap/repair_regressions.py', fixture_parameters('NqpFixtureProbe.exe'))
    if args.kind == 'supplemental':
        previous = json.loads((args.work / 'fixture-result.json').read_text(encoding='utf-8'))
        path = Path(previous['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != previous['sha256']:raise ValueError('fixture result changed')
        call('qmt_readonly_bootstrap/supplemental.py', fixture_parameters('NqpFixtureProbe.exe') + ['--main-results', path])
    if args.kind in ('http', 'drain'):
        if args.qmt_fixture is None:raise ValueError('controlled fixed QMT fixture required')
        cwd = binaries / 'drain' if args.kind == 'drain' else binaries
        parameters = ['--probe', probe_root / 'NqpHttpProbe.exe', '--library', cwd / 'traders/TraderQMTReadOnly.dll',
                      '--cwd', cwd, '--owned-root', owned, '--qmt-fixture', args.qmt_fixture, '--work', root / 'http']
        if args.kind == 'drain':parameters += ['--drain']
        call('qmt_http_bootstrap/run.py', parameters, 360)
    if args.kind in ('abi', 'binary'):
        call('qmt_http_bootstrap/abi.py', ['--library', library, '--output', root / 'abi.json'], 30)
    if args.kind in ('no-connect', 'binary'):
        call('qmt_http_bootstrap/no_connect.py', ['--probe', probe_root / 'NqpNoConnectProbe.exe', '--library', library, '--work', root / 'no-connect'], 30)
    if args.kind == 'cng':
        call('qmt_http_bootstrap/cng_lifetime.py', ['--probe', probe_root / 'NqpCngProbe.exe', '--work', root / 'cng'], 30)
    (root / 'receipt.json').write_text(json.dumps({'kind': args.kind, 'status': 'passed', 'commands': reports}, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
