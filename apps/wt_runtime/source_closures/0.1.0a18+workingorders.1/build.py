"""从固定Git及三个已验覆盖重建Runtime；离线构建，不读取运行安装或账户。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


def exact(raw, digest):
    """Git换行可配置；产物恢复为已验成员的原字节。"""
    normalized = raw.replace(b'\r\n', b'\n')
    for value in (raw, normalized, normalized.replace(b'\n', b'\r\n')):
        if hashlib.sha256(value).hexdigest() == digest:
            return value
    raise ValueError('closure_source_identity')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--backend', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    closure = Path(__file__).resolve().parent
    manifest = json.loads((closure / 'SOURCE-MANIFEST.json').read_bytes())
    repository = args.repository.resolve(strict=True)
    work, output = args.work.resolve(), args.output.resolve()
    if work.exists() or output.exists() or work.is_relative_to(output) or output.is_relative_to(work):
        raise ValueError('new_distinct_build_roots_required')
    if manifest['schema'] != 'wt.runtime-source-closure.v2' or len(manifest['modules']) != 46:
        raise ValueError('closure_manifest')
    backend = args.backend.resolve(strict=True)
    if hashlib.sha256(backend.read_bytes()).hexdigest() != manifest['backend_sha256']:
        raise ValueError('closure_backend_identity')
    admitted = {}
    for name, row in manifest['modules'].items():
        if Path(name).name != name or not name.endswith('.py'):
            raise ValueError('closure_member')
        if row['source'] == 'git':
            command = ['git', '-C', str(repository), 'show', manifest['source_commit'] +
                       ':apps/wt_runtime/guanheng_wt_runtime/' + name]
            result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                timeout=30, creationflags=0x08000000 if os.name == 'nt' else 0)
            if result.returncode:
                raise ValueError('closure_git_source')
            raw = result.stdout
        elif row['source'] == 'overlay':
            raw = (closure / 'overlays' / name).read_bytes()
        else:
            raise ValueError('closure_source_kind')
        admitted[name] = exact(raw, row['sha256'])
    metadata = exact((closure / 'pyproject.toml').read_bytes(), manifest['pyproject_sha256'])
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    package = work / 'guanheng_wt_runtime'
    package.mkdir()
    for name, raw in admitted.items():
        (package / name).write_bytes(raw)
    (work / 'pyproject.toml').write_bytes(metadata)
    with zipfile.ZipFile(backend) as archive:
        archive.extractall(work / 'backend')
    command = [sys.executable, '-I', '-B', '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from flit_core.buildapi import build_wheel;build_wheel(sys.argv[2])',
        str(work / 'backend'), str(output)]
    result = subprocess.run(command, cwd=work, stdin=subprocess.DEVNULL, capture_output=True, timeout=120,
        creationflags=0x08000000 if os.name == 'nt' else 0,
        env=dict(os.environ, SOURCE_DATE_EPOCH='315532800', PYTHONDONTWRITEBYTECODE='1'))
    if result.returncode:
        raise ValueError('closure_build_failed')
    wheel = next(output.glob('*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        for name, raw in admitted.items():
            if archive.read('guanheng_wt_runtime/' + name) != raw:
                raise ValueError('closure_wheel_identity')
    record = dict(source_commit=manifest['source_commit'], wheel=str(wheel),
        sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(), modules=len(admitted))
    (output / 'BUILD.json').write_text(json.dumps(record, indent=2), encoding='utf8')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
