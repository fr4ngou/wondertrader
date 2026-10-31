"""独立安装HPR产品工具；默认只显示帮助，异常输出固定去敏分类。"""
import argparse
import json
import os
from pathlib import Path
import sys
from guanheng_qmt_shm_agent.protocol import decode
from .bootstrap import credentials_from_environment
from .history_preparation_product import _read, create_product_pair, verify_product_pair


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('history preparation CLI arguments')


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        sub = parser.add_subparsers(dest='command', required=True)
        create = sub.add_parser('pair')
        create.add_argument('--config', type=Path, required=True)
        create.add_argument('--quote-settings', type=Path, required=True)
        create.add_argument('--quote-secret-env', required=True)
        create.add_argument('--memory-sdk-manifest', type=Path, required=True)
        create.add_argument('--stdlib-license', type=Path, required=True)
        create.add_argument('--reconnect-seconds', type=float, required=True)
        create.add_argument('--output', type=Path, required=True)
        for name in ('verify', 'run'):
            entry = sub.add_parser(name)
            entry.add_argument('--directory', type=Path, required=True)
            entry.add_argument('--installed-agent', type=Path, required=True)
            if name == 'run':
                entry.add_argument('--control-directory', type=Path)
                entry.add_argument('--control-id')
        arguments = list(sys.argv[1:] if argv is None else argv)
        if not arguments:
            parser.print_help()
            return 0
        args = parser.parse_args(arguments)
        if args.command == 'pair':
            config = decode(_read(args.config, 65536))
            quotes = decode(_read(args.quote_settings, 2097152))
            if type(quotes) is not dict or 'secret' in quotes:
                raise ValueError('quote secret role')
            quotes['secret'] = os.environ[args.quote_secret_env].encode('utf8')
            result = create_product_pair(config, quotes, credentials=credentials_from_environment(config),
                output=args.output, sdk_metadata=decode(_read(args.memory_sdk_manifest, 65536)),
                stdlib_license=_read(args.stdlib_license, 65536), reconnect_seconds=args.reconnect_seconds)
        elif args.command == 'verify':
            result = verify_product_pair(args.directory, installed_agent=args.installed_agent)
        else:
            from .history_preparation_control import serve_product
            result = serve_product(args.directory, installed_agent=args.installed_agent,
                control_directory=args.control_directory, control_id=args.control_id)
        print(json.dumps(dict(schema_version='qmt.history-preparation-cli.v1', ok=True, result=result), ensure_ascii=True))
        return 0
    except Exception:
        print('{"schema_version":"qmt.history-preparation-cli.v1","ok":false,"error_code":"admission_or_operation_failed"}')
        return 2


if __name__ == '__main__': raise SystemExit(main())
