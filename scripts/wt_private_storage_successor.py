"""从已核停机收据生成 WT 跨盘后继配置，仅准备文件。"""
from argparse import ArgumentParser
import json
from pathlib import Path

from guanheng_wt_runtime.service_control import ServiceConfig, ServiceController


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    for name in ('service-config', 'storage-receipt', 'storage-sha256', 'pair', 'native-template',
                 'native-sha256', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--no-order', action='store_true', help='使用原权限交接，关闭候选原生委托与撤单')
    parser.add_argument('--successor-pythonw', type=Path, help='显式选择已安装的新 WT 解释器')
    args = parser.parse_args()
    service = ServiceController(ServiceConfig.from_path(args.service_config))
    reference = {'file': args.storage_receipt, 'sha256': args.storage_sha256}
    result = service.prepare_private_successor(reference, Path(args.pair), Path(args.native_template),
                                               args.native_sha256, Path(args.output), no_order=args.no_order,
                                               successor_pythonw=args.successor_pythonw)
    print(json.dumps(result, ensure_ascii=True))
