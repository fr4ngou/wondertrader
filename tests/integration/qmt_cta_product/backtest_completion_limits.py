"""原完成目录在精确容量边界幂等确认；首次写按原NBW另留空间。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from time import monotonic
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    from guanheng_wt_runtime import backtest_completion as B
    from guanheng_wt_runtime.strategy_host import HostResult, HostError, _encode
    args.work.mkdir()
    directory = args.work/args.run.name
    shutil.copytree(args.run, directory)
    raw = (directory/B.RECEIPT).read_bytes()
    proof = json.loads(raw)
    report = _encode(json.loads((directory/'result.json').read_bytes())['report']).decode('ascii')
    entries = list(directory.rglob('*'))
    total = sum(p.stat().st_size for p in entries if p.is_file())
    result = HostResult(proof['run_id'], 'completed', 'QA original parent facts',
        proof['request_sha256'], proof['installation_sha256'], str(directory), report, proof['pid'],
        0, False, True, True, proof['elapsed_ms'])
    configuration = proof['configuration']
    kw = dict(label=configuration['label'], max_seconds=configuration['max_seconds'], deadline=monotonic()+30)
    # 副本仅替代已在真实主链通过的路径绑定校验，容量和写入路径均为产品实现。
    with patch.object(B.StrategyHost, '_result', return_value=report), \
         patch.object(B, 'MAX_ENTRIES', len(entries)), patch.object(B, 'MAX_RUN_BYTES', total):
        assert B.publish_completed(result, args.work, **kw) == hashlib.sha256(raw).hexdigest()
        assert (directory/B.RECEIPT).read_bytes() == raw
        (directory/B.RECEIPT).unlink()
        try:
            B.publish_completed(result, args.work, **kw)
        except HostError as error:
            assert '容量' in str(error)
        else:
            raise AssertionError('first publication requires additional capacity')
        assert not list(directory.glob('.archive-*.pending'))
    value = dict(passed=True, existing_exact_entry_and_byte_limits=True,
        first_write_requires_reserve=True, entries=len(entries), bytes=total, new_native_calls=0)
    (args.work/'RESULT.json').write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')
    print(json.dumps(value))


if __name__ == '__main__':
    main()
