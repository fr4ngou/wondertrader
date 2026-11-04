"""独立安装交易通信入口；默认帮助，凭据只从显式环境装入私有配对。"""
import argparse
import json
from pathlib import Path
import sys
from guanheng_qmt_shm_agent.protocol import decode
from .bootstrap import credentials_from_environment
from .trade_pair import _read, _market_material, create_product_pair, verify_product_pair
from .account_read_composition import load_account_read_pair
from .analysis_read_composition import load_analysis_read_pair
from .analysis_batch_read_composition import load_analysis_batch_read_pair
from .security_reference_composition import load_security_reference_read_pair


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('trade product CLI arguments')


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        sub = parser.add_subparsers(dest='command', required=True)
        create = sub.add_parser('pair')
        create.add_argument('--config', type=Path, required=True)
        create.add_argument('--memory-sdk-manifest', type=Path, required=True)
        create.add_argument('--stdlib-license', type=Path, required=True)
        create.add_argument('--reconnect-seconds', type=float, required=True)
        create.add_argument('--output', type=Path, required=True)
        create.add_argument('--market-config', type=Path)
        create.add_argument('--account-read-pair', type=Path)
        create.add_argument('--analysis-read-pair', type=Path)
        create.add_argument('--analysis-batch-read-pair', type=Path)
        create.add_argument('--security-reference-read-pair', type=Path)
        create.add_argument('--source-mode', choices=('thread', 'strategy_tick'))
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
            result = create_product_pair(config, credentials=credentials_from_environment(config),
                output=args.output, sdk_metadata=decode(_read(args.memory_sdk_manifest, 65536)),
                stdlib_license=_read(args.stdlib_license, 65536), reconnect_seconds=args.reconnect_seconds,
                market=None if args.market_config is None else
                _market_material(decode(_read(args.market_config)), decode_secrets=True),
                account_read=None if args.account_read_pair is None else load_account_read_pair(args.account_read_pair),
                analysis_read=None if args.analysis_read_pair is None else load_analysis_read_pair(args.analysis_read_pair),
                analysis_batch_read=None if args.analysis_batch_read_pair is None else load_analysis_batch_read_pair(args.analysis_batch_read_pair),
                security_reference_read=None if args.security_reference_read_pair is None else load_security_reference_read_pair(args.security_reference_read_pair),
                source_runtime=None if args.source_mode is None else
                dict(schema_version='qmt.source-runtime.v1', mode=args.source_mode))
        elif args.command == 'verify':
            result = verify_product_pair(args.directory, installed_agent=args.installed_agent)
        else:
            from .trade_control import serve_product
            result = serve_product(args.directory, installed_agent=args.installed_agent,
                control_directory=args.control_directory, control_id=args.control_id)
        print(json.dumps(dict(schema_version='qmt.trade-cli.v1', ok=True, result=result), ensure_ascii=True))
        return 0
    except Exception:
        print('{"schema_version":"qmt.trade-cli.v1","ok":false,"error_code":"admission_or_operation_failed"}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
