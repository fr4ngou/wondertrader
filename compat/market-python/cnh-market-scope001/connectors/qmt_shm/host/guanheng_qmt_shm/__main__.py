"""本仓独立Host/配对/检查工具；错误回执去敏，帮助不启动任何组件。"""
import argparse
from pathlib import Path
import sys
from guanheng_qmt_shm_agent.protocol import decode
from .bootstrap import build_runtime, validate_launch, credentials_from_environment

HELP='guanheng-qmt-shm: run | run-pair | check | pair | verify | export-agent | install-agent\nPrivate read-only Host/Agent tools; explicit read operations: market.full_tick / market.history_1m / account.trade_detail; source qualification is separate.\n'


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('invalid CLI arguments')


def _raw_file(path, maximum=2097152):
    with Path(path).open('rb') as stream:
        raw=stream.read(maximum+1)
    if len(raw)>maximum:
        raise ValueError('material byte budget exceeded')
    return raw


def _json_file(path):
    with Path(path).open('rb') as stream:
        raw=stream.read(2097153)
    if len(raw)>2097152:
        raise ValueError('configuration byte budget exceeded')
    return decode(raw)


def main(argv=None):
    import json
    args=list(sys.argv[1:] if argv is None else argv)
    if args in (['--help'],['-h']):
        print(HELP,end='');return 0
    try:
        parser=_Parser(add_help=False)
        sub=parser.add_subparsers(dest='command',required=True,parser_class=_Parser)
        for name in ('run','check','pair'):
            entry=sub.add_parser(name,add_help=False);entry.add_argument('--config',required=True,type=Path)
            entry.add_argument('--connection-lifecycle',type=Path)
            if name=='pair':
                entry.add_argument('--agent-config',required=True,type=Path)
                entry.add_argument('--installed-agent',required=True,type=Path)
                entry.add_argument('--output',required=True,type=Path)
                entry.add_argument('--memory-sdk-manifest',type=Path)
                entry.add_argument('--stdlib-license',type=Path)
        paired=sub.add_parser('run-pair',add_help=False)
        paired.add_argument('--directory',required=True,type=Path)
        paired.add_argument('--installed-agent',required=True,type=Path)
        paired.add_argument('--control-directory',type=Path)
        paired.add_argument('--control-id')
        entry=sub.add_parser('verify',add_help=False)
        entry.add_argument('--directory',required=True,type=Path);entry.add_argument('--installed-agent',required=True,type=Path)
        entry=sub.add_parser('export-agent',add_help=False);entry.add_argument('--output',required=True,type=Path)
        entry=sub.add_parser('install-agent',add_help=False)
        entry.add_argument('--archive',required=True,type=Path);entry.add_argument('--output',required=True,type=Path)
        options=parser.parse_args(args)
        if options.command in ('run','check','pair'):
            config=_json_file(options.config);credentials=credentials_from_environment(config)
            from .lifecycle import validate_connection_lifecycle
            lifecycle=validate_connection_lifecycle(_json_file(options.connection_lifecycle)
                if options.connection_lifecycle is not None else None)
            if lifecycle is not None and config.get('transport',{}).get('kind')!='builtin-shm':
                raise ValueError('resident lifecycle requires builtin SHM')
        if options.command=='run':
            from .server import run_server
            if lifecycle is None:
                runtime=build_runtime(config,credentials=credentials)
            else:
                from .bootstrap import build_read_service
                runtime=build_read_service(config,credentials=credentials,
                    reconnect_seconds=lifecycle['reconnect_seconds'])
            run_server(runtime,http_keys=credentials['http_keys'])
            result={'stopped':True,'order_ready':False}
        elif options.command=='run-pair':
            from .paired_control import serve_paired
            result=serve_paired(options.directory,installed_agent=options.installed_agent,
                control_directory=options.control_directory,control_id=options.control_id)
        elif options.command=='check':
            validate_launch(config,credentials=credentials)
            result={'configuration_valid':True,'started':False,'qualified_in_qmt':False,'order_ready':False}
        elif options.command=='pair':
            from .pair import create_pair
            result=create_pair(config,_json_file(options.agent_config),installed_agent=options.installed_agent,
                credentials=credentials,output=options.output,connection_lifecycle=lifecycle,
                sdk_metadata=(_json_file(options.memory_sdk_manifest)
                    if options.memory_sdk_manifest is not None else None),
                stdlib_license=(_raw_file(options.stdlib_license,65536)
                    if options.stdlib_license is not None else None))
        elif options.command=='verify':
            from .pair import verify_pair
            result=verify_pair(options.directory,installed_agent=options.installed_agent)
        elif options.command=='export-agent':
            from .agent_archive import export_agent
            result=export_agent(options.output)
        else:
            from .agent_archive import install_agent
            result=install_agent(options.archive,output=options.output)
        print(json.dumps({'schema_version':'qmt.shm-cli.v1','ok':True,'result':result},ensure_ascii=True,separators=(',',':')))
        return 0
    except KeyboardInterrupt:
        print('{"schema_version":"qmt.shm-cli.v1","ok":false,"error_code":"interrupted","order_ready":false}')
        return 130
    except Exception:
        print(json.dumps({'schema_version':'qmt.shm-cli.v1','ok':False,
            'error_code':'admission_or_operation_failed','error_message':'只读工具未完成；请核对受管配置和配对身份',
            'order_ready':False},ensure_ascii=True,separators=(',',':')))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
