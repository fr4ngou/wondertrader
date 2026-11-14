"""用已安装的交易 Host 解释器制作同一绑定的迁盘配对，不连接柜台。"""
from argparse import ArgumentParser
import json
from pathlib import Path
import subprocess
import sys

from guanheng_qmt_shm.trade_pair import (
    _decode_reference_deployment, _hash, _read, _verified, create_product_pair, decode, verify_product_pair,
)


def _require(value):
    if not value:
        raise ValueError('WT QMT journal migration identity differs')


def relocate_product_pair_journal(directory, output, journal, *, installed_agent=None, origin_python=None):
    """用原配对构建器重制同一配对，唯一业务变化为通信库路径。"""
    directory = Path(directory)
    journal = Path(journal)
    _require(journal.is_absolute() and journal.drive.upper() in ('D:', 'E:') and journal.is_file())
    if origin_python is None:
        verified, _ = _verified(directory, installed_agent)
    else:
        # 原配对清单绑定原 Host 源码和解释器，由原安装核原件；新安装生成并复核后继。
        origin_python = Path(origin_python)
        _require(origin_python.is_absolute() and origin_python.name.lower() == 'python.exe')
        result = subprocess.run([str(origin_python), '-I', '-B', str(Path(__file__).absolute()),
                                 '--pair', str(directory), '--verify-origin'], capture_output=True,
                                timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        _require(result.returncode == 0)
        verified = json.loads(result.stdout)
    manifest_raw = _read(directory / 'manifest.json')
    deployment_raw = _read(directory / 'deployment.json')
    _require(_hash(manifest_raw) == verified['pair_manifest_sha256']
          and _hash(deployment_raw) == verified['pair_config_sha256'])
    manifest = decode(manifest_raw)
    host, credentials, interval, market, account, runtime, analysis, batch, securities = (
        _decode_reference_deployment(deployment_raw))
    _require(Path(host['journal_path']) != journal)
    host['journal_path'] = str(journal)
    license_bytes = _read(directory / 'CPYTHON-LICENSE.txt')
    _require(_hash(license_bytes) == manifest['files']['CPYTHON-LICENSE.txt']
          and _hash(_read(directory / 'policy.json')) == manifest['files']['policy.json'])
    result = create_product_pair(host, credentials=credentials, output=output,
        sdk_metadata=manifest['memory_runtime']['sdk'], stdlib_license=license_bytes,
        reconnect_seconds=interval, installed_agent=installed_agent, market=market, account_read=account,
        source_runtime=runtime, analysis_read=analysis, analysis_batch_read=batch,
        security_reference_read=securities)
    _require(verify_product_pair(output, installed_agent=installed_agent) == result
          and _hash(_read(Path(output) / 'strategy.py')) == manifest['files']['strategy.py']
          and _hash(_read(Path(output) / 'policy.json')) == manifest['files']['policy.json'])
    return result


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--origin-python', type=Path)
    parser.add_argument('--verify-origin', action='store_true', help='使用原安装核配对，只返回两项摘要')
    args = parser.parse_args()
    if args.verify_origin:
        _require(args.output is None and args.journal is None and args.origin_python is None)
        identity, _ = _verified(args.pair)
        result = {key: identity[key] for key in ('pair_manifest_sha256', 'pair_config_sha256')}
    else:
        _require(args.output is not None and args.journal is not None)
        result = relocate_product_pair_journal(args.pair, args.output, args.journal, origin_python=args.origin_python)
    print(json.dumps(result, ensure_ascii=True))
