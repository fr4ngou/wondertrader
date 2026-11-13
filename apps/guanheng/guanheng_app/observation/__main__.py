"""离线观察目录操作；所有写入仅在显式CLI动作中执行。"""

import argparse
import json
from datetime import date
from pathlib import Path
from time import monotonic

from .contracts import ObservationError
from .publication import adopt_snapshot, validate_manifest
from .runtime import build_reader
from .storage import MANIFEST_BYTES


def main():
    parser = argparse.ArgumentParser(description='观衡独立市场观察目录')
    parser.add_argument('command', choices=['initialize', 'import-frozen', 'verify', 'restore', 'refresh', 'derive-breadth', 'import-shareholders'])
    parser.add_argument('--root', required=True)
    parser.add_argument('--manifest')
    parser.add_argument('--snapshot')
    parser.add_argument('--expected-current')
    parser.add_argument('--config')
    parser.add_argument('--config-sha256')
    parser.add_argument('--as-of')
    parser.add_argument('--sources')
    parser.add_argument('--source-root')
    parser.add_argument('--source-snapshot')
    parser.add_argument('--start')
    parser.add_argument('--seconds', type=float, default=120)
    args = parser.parse_args()
    if not 0 < args.seconds <= 600:
        parser.error('seconds需要在0至600之间')
    deadline = monotonic() + args.seconds
    reader = build_reader(args.root)
    try:
        if args.command == 'initialize':
            reader.repository.initialize()
            result = dict(status='initialized', execution_enabled=False)
        elif args.command == 'import-shareholders':
            if not all((args.source_root, args.as_of, args.expected_current)):
                parser.error('股东历史采用需要source-root、as-of及expected-current')
            from .shareholder_archive import FIRST, publish_archive
            last = date.fromisoformat(args.as_of)
            if not FIRST <= last <= date.today():
                parser.error('as-of需在2018年1月1日至今天之间')
            result = publish_archive(reader, args.source_root, last, args.expected_current, deadline)
        elif args.command == 'derive-breadth':
            if not all((args.source_root,args.source_snapshot,args.start,args.as_of)):
                parser.error('归档计算需要source-root、source-snapshot、start及as-of')
            from .breadth_archive import derive_archive
            reader.repository.initialize()
            result=derive_archive(build_reader(args.source_root),reader,args.source_snapshot,
                args.start,args.as_of,args.expected_current,deadline)
        elif args.command == 'refresh':
            if not args.config or not args.config_sha256 or not args.as_of:
                parser.error('更新需要config、config-sha256及as-of')
            if date.fromisoformat(args.as_of).isoformat() != args.as_of:
                parser.error('as-of需要YYYY-MM-DD')
            if args.start and date.fromisoformat(args.start).isoformat() != args.start:
                parser.error('start需要YYYY-MM-DD')
            from .collection_config import load_configuration
            from .collection import refresh
            configuration = load_configuration(args.config, args.config_sha256)
            reader.repository.initialize()
            from .runtime import market_client_factory
            result = refresh(reader,configuration,as_of=args.as_of,deadline=deadline,
                source_ids=args.sources.split(',') if args.sources else None,market_client_factory=market_client_factory(),
                structure_history_start=args.start)
            result = {key:result[key] for key in ('status','as_of','previous_snapshot','current_snapshot','candidate_snapshot','error_code') if key in result}
        elif args.command == 'verify':
            version, manifest = reader.snapshot(args.snapshot)
            result = dict(snapshot_id=version, **validate_manifest(reader, manifest, deadline))
        else:
            if not args.snapshot:
                parser.error('采用或恢复需要snapshot')
            with reader.repository.collection_lease() as acquired:
                if not acquired:
                    raise ObservationError('another_owner_running', '其他观察写入者正在运行', 409)
                if args.command == 'restore':
                    manifest = reader.repository.get(args.snapshot)
                else:
                    if not args.manifest:
                        parser.error('导入需要manifest')
                    with Path(args.manifest).open('rb') as stream:
                        body = stream.read(MANIFEST_BYTES + 1)
                    if len(body) > MANIFEST_BYTES:
                        raise ObservationError('manifest_budget_exceeded', '观察目录超过容量', 422)
                    manifest = json.loads(body)
                result = adopt_snapshot(reader, manifest, args.snapshot, args.expected_current, deadline,
                                        restoring=args.command == 'restore')
    except ObservationError as exc:
        print(json.dumps(dict(code=exc.code, detail=exc.detail), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result.get('status') in ('failed','publication_unknown','attempt_unknown') else 0


if __name__ == '__main__':
    raise SystemExit(main())
