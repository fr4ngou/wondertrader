"""为正常停止的 WT 准备跨盘迁移材料，保留原控制代和数据库。"""
from argparse import ArgumentParser
from pathlib import Path
import json

from guanheng_wt_runtime.service_control import ServiceConfig, ServiceController


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--service-config', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--private-root', type=Path)
    mode.add_argument('--abandon-receipt')
    parser.add_argument('--storage-sha256')
    args = parser.parse_args()
    if bool(args.abandon_receipt) != bool(args.storage_sha256):
        parser.error('--abandon-receipt and --storage-sha256 must be supplied together')
    service = ServiceController(ServiceConfig.from_path(args.service_config))
    if args.abandon_receipt:
        result = service.abandon_private_storage({'file': args.abandon_receipt, 'sha256': args.storage_sha256})
    else:
        result = service.prepare_private_storage(args.private_root)
    print(json.dumps(result, ensure_ascii=True))
