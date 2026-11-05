"""组合制品对照当前源码；保留旧发行成员须逐件给出固定摘要和理由。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import TypedDict


class PreservedSource(TypedDict):
    sha256: str  # 明确保留的既有发行成员字节摘要，不能以可变路径代替。
    reason: str  # 本次保留旧实现的依据；新改动必须明确分类。


def _files(root):
    result = {}
    for path in Path(root).rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix not in ('.py', '.json'):
            continue
        if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400 or path.stat().st_size > 32*1024*1024:
            raise ValueError('composition_regular_source_required')
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        if len(result) > 512:
            raise ValueError('composition_source_capacity')
    if not result:
        raise ValueError('composition_source_empty')
    return result


def verify_composition(source: Path, candidate: Path, preserved: dict[str, PreservedSource]):
    """逐件核当前源码或显式旧版本；未知差异一次完整报告，防止遗漏既有修复。"""
    desired, actual = _files(source), _files(candidate)
    if not set(preserved) <= set(desired) or any(not row.get('reason') for row in preserved.values()):
        raise ValueError('composition_preservation_contract')
    missing, extra = sorted(set(desired)-set(actual)), sorted(set(actual)-set(desired))
    unresolved, kept = [], []
    for name in sorted(set(desired) & set(actual)):
        if actual[name] == desired[name]:
            continue
        declaration = preserved.get(name)
        if declaration is not None and actual[name] == declaration['sha256']:
            kept.append(dict(name=name, **declaration))
        else:
            unresolved.append(dict(name=name, source_sha256=desired[name], candidate_sha256=actual[name]))
    return dict(schema='guanheng.runtime-composition-check.v1', passed=not (missing or extra or unresolved),
        source_count=len(desired), candidate_count=len(actual), missing=missing, extra=extra,
        unresolved=unresolved, preserved=kept)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--preserved', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify_composition(args.source, args.candidate, json.loads(args.preserved.read_bytes()))
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
