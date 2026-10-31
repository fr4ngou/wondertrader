"""独立观衡development制品的核验和普通离线安装；不启动WT或观衡。"""
import argparse
import json
import math
from pathlib import Path
import sys
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'tools/scripts'))
from native_support import account_runtime_install as roles
from native_support import system_runtime as files

MANIFEST='OBSERVER-RUNTIME.json'


def verify(root,expected):
    """先核外部固定清单，再核原App角色、SPA和精确文件集；全程只读。"""
    root=files._root(root)
    value=files._load(root/MANIFEST,expected)
    files._require(set(value)=={'schema','development','role_manifest_sha256','spa_files','files'}
        and value['schema']=='guanheng.observer-runtime.v1' and value['development'] is True,'observer artifact schema')
    actual=files._files(root);actual.pop(MANIFEST)
    files._require(actual==value['files'],'observer artifact contents changed')
    files._require({'observer-install.py','README.md',*('tools/'+name for name in files.TOOL_FILES)} <= actual.keys(),
        'observer installer tool closure missing')
    declared=roles.verify_artifacts(root/'roles',files._sha(value['role_manifest_sha256']))
    files._require(set(declared['roles'])=={'app'},'observer artifact requires only app role')
    static=files._mapping(value['spa_files'])
    files._require('index.html' in static and {name:record['sha256'] for name,record in files._files(root/'spa').items()}==static,
        'observer SPA identity mismatch')
    return value


def install(root,expected,target,python,uv,deadline):
    """全新目标只接收预建制品；原角色owner持有安装子树，收据最后发布。"""
    import native
    files._require(type(deadline) in (int,float) and math.isfinite(deadline) and deadline>time.monotonic(),
        'finite observer installation deadline')
    root=files._root(root);value=verify(root,expected)
    roles._separate_paths((target,),(root,))
    target=files._fresh(target);payload=target/'payload';payload.mkdir()
    files._copy(root,{name:record['sha256'] for name,record in files._files(root).items()},payload)
    verify(payload,expected)
    def command(argv,**options):
        return native.run(argv,private_console=True,max_output_bytes=4*1024**2,**options)
    installed=roles.install_artifacts(payload/'roles',value['role_manifest_sha256'],target/'runtime',python,uv,
        command,deadline=deadline)
    verify(root,expected);verify(payload,expected)
    files._require(time.monotonic()<deadline,'observer installation deadline exhausted')
    record=dict(schema='guanheng.observer-installation.v1',root=str(target),manifest_sha256=expected,
        role_installation_sha256=roles._sha(target/'runtime/installation.json'),development=True)
    digest=roles._publish_installation(target/'OBSERVER-INSTALLATION.json',record,deadline)
    files._require(time.monotonic()<deadline,'observer publication completed after deadline')
    return dict(installation_sha256=digest,python=installed['roles']['app']['executable'],
        module='guanheng_app',static_directory=str(payload/'spa'),development=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('command',choices=('verify','install'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--manifest-sha256',required=True)
    for name in ('target','python','uv'):parser.add_argument('--'+name,type=Path)
    budget=parser.add_mutually_exclusive_group()
    budget.add_argument('--deadline',type=float)
    budget.add_argument('--seconds',type=float,default=300)
    args=parser.parse_args();began=time.monotonic()
    if args.command=='verify':
        value=verify(args.root,args.manifest_sha256);result=dict(verified=True,files=len(value['files']))
    else:
        if not all((args.target,args.python,args.uv)):parser.error('install requires target, python and uv')
        if not math.isfinite(args.seconds) or not 0<args.seconds<=3600:parser.error('seconds must be 0..3600')
        deadline=args.deadline if args.deadline is not None else began+args.seconds
        result=install(args.root,args.manifest_sha256,args.target,args.python,args.uv,deadline)
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
