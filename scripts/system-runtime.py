"""观衡系统候选装配、验证、搬迁、离线安装与入口解析。"""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from native_support import system_runtime as runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    commands = parser.add_subparsers(dest='command',required=True)
    create = commands.add_parser('create')
    for name in ('inputs','output','archive'):
        create.add_argument('--'+name,type=Path,required=True)
    create.add_argument('--inputs-sha256',required=True)
    for name in ('verify','install'):
        sub = commands.add_parser(name)
        sub.add_argument('--root',type=Path,required=True)
        sub.add_argument('--manifest-sha256',required=True)
        if name == 'install':
            for option in ('target','python','uv'):
                sub.add_argument('--'+option,type=Path,required=True)
            sub.add_argument('--deadline',type=float,required=True,help='原调用方time.monotonic绝对截止')
    extract = commands.add_parser('extract')
    for name in ('archive','output'):
        extract.add_argument('--'+name,type=Path,required=True)
    for name in ('archive-sha256','manifest-sha256'):
        extract.add_argument('--'+name,required=True)
    resolve = commands.add_parser('resolve')
    resolve.add_argument('--root',type=Path,required=True)
    resolve.add_argument('--installation-sha256',required=True)
    args = parser.parse_args()
    if args.command == 'create':
        result = runtime.create(args.inputs,args.inputs_sha256,args.output,args.archive)
    elif args.command == 'verify':
        document = runtime.verify(args.root,args.manifest_sha256)
        result = dict(status='verified',files=len(document['files']),development=document['development'])
    elif args.command == 'extract':
        runtime.extract(args.archive,args.archive_sha256,args.manifest_sha256,args.output)
        result = dict(status='extracted',manifest_sha256=args.manifest_sha256)
    elif args.command == 'resolve':
        result = runtime.resolve(args.root,args.installation_sha256)
    else:
        import native
        def run(argv,**options):
            return native.run(argv,private_console=True,max_output_bytes=4*1024**2,**options)
        result = runtime.install(args.root,args.manifest_sha256,args.target,args.python,args.uv,run,deadline=args.deadline)
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
