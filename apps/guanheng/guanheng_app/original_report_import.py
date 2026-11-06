"""维护者显式导入ORR原件；共享既有归档目录，HTTP及策略执行保持只读。"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from time import monotonic

from . import original_reports as original
from .backtest_archive import _Read, _path, RECEIPT, MAX_RECEIPT


def import_report(manifest_path, archive_root, *, deadline=None):
    """核三份显式绝对原件后独占新run；完成证明最后写入，失败原件留存待核。"""
    read = _Read(monotonic() + 30 if deadline is None else deadline)
    manifest_path = Path(manifest_path)
    original.require(manifest_path.is_absolute())
    manifest = original.decode(read.raw(manifest_path, MAX_RECEIPT))
    original.require(type(manifest) is dict and set(manifest) == {'schema', 'run_id', 'label',
        'report_path', 'input_path', 'source_manifest_path', 'report_sha256', 'input_file_sha256',
        'source_manifest_file_sha256'} and manifest['schema'] == 'guanheng.original-report-import.v1')
    originals = []
    for key, checksum in (('report_path', 'report_sha256'), ('input_path', 'input_file_sha256'),
                          ('source_manifest_path', 'source_manifest_file_sha256')):
        original.require(type(manifest[key]) is str and Path(manifest[key]).is_absolute())
        raw = read.raw(Path(manifest[key]), original.MAX_BYTES)
        original.require(sha256(raw).hexdigest() == manifest[checksum])
        originals.append(raw)
    report = original.validate_report(*(original.decode(raw) for raw in originals), check=read.check)
    receipt = original.receipt(report, manifest['label'], manifest['run_id'], *originals)
    original.validate_receipt(receipt, manifest['run_id'])
    root = Path(archive_root)
    original.require(root.is_absolute())
    root = read.directory(root)
    # 目录容量沿统一owner；预留1个run，不引入第二个报告索引或数据库。
    with os.scandir(root) as entries:
        count, directories = 0, 0
        for entry in entries:
            read.check()
            path = _path(Path(entry.path))
            info = path.lstat()
            original.require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
            count += 1
            directories += int(stat.S_ISDIR(info.st_mode))
            original.require(count < 256 and directories < 128, '归档根目录容量不足')
    run = root / receipt['run_id']
    read.check()
    run.mkdir()  # 排他创建；同身份存在时拒绝，绝不覆盖完成或未知结果。
    for name, raw in zip(('original-report.json', 'original-input.json', 'source-manifest.json'), originals):
        read.check()
        with (run / name).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    # 发布前再经正式只读接缝复核，冻结原件和后续页面使用相同准入。
    original.load(read, run, receipt)
    encoded = original.canonical(receipt)
    original.require(len(encoded) <= MAX_RECEIPT)
    pending = run / '.original-archive.pending'
    with pending.open('xb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    read.check()
    _path(run)
    original.require(os.name == 'nt', '此导入入口采用Windows本机归档发布语义')
    os.rename(pending, run / RECEIPT)  # Windows目标存在时拒绝，完成证明最后出现。
    original.require(read.raw(run / RECEIPT, MAX_RECEIPT) == encoded)
    return dict(schema='guanheng.original-report-import-result.v1',  # 导入结果协议。
                run_id=receipt['run_id'],  # 唯一归档身份。
                receipt_sha256=sha256(encoded).hexdigest(),  # 页面固定读取身份。
                report_sha256=receipt['report_sha256'],  # 原报告字节摘要。
                report_family=original.FAMILY)  # 只读原版family。


def main(argv=None):
    parser = argparse.ArgumentParser(description='导入固定原版共振研究报告，不执行回测或交易')
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--archive-root', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = import_report(args.manifest, args.archive_root)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps(dict(status='failed', reason='原版导入未完成，请保留目录并核对manifest及原件'), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
