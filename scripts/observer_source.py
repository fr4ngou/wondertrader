"""从永久源码与显式离线依赖生成独立观衡App/读取角色制品。"""
import argparse
import json
from pathlib import Path
import sys
from time import monotonic

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from native import run
from native_support.observer_source import build, inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('command', choices=('inputs', 'build'))
    parser.add_argument('--work', type=Path)
    for name in ('python', 'backend', 'wheelhouse', 'node', 'npm-cli', 'npm-cache'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--seconds', type=float, default=900)
    args = parser.parse_args()
    if args.command == 'inputs':
        print(json.dumps(inputs(ROOT)[2], ensure_ascii=False))
        return 0
    required = (args.work, args.python, args.backend, args.wheelhouse, args.node, args.npm_cli, args.npm_cache)
    if not all(required) or not 0 < args.seconds <= 3600:
        parser.error('build需要全新work、显式离线工具/依赖及0至3600秒预算')
    result = build(ROOT, args.work, python=args.python, backend=args.backend, wheelhouse=args.wheelhouse,
        node=args.node, npm_cli=args.npm_cli, npm_cache=args.npm_cache, deadline=monotonic() + args.seconds, run=run)
    print(json.dumps({key: result[key] for key in ('App', 'archive', 'archive_sha256', 'role_root', 'role_manifest_sha256')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
