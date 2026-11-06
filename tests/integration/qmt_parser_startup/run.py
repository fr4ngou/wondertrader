"""Replay frozen read-result data through original C++ parser with a client SDK substitute.
No socket/server or installed runtime is used. Private input remains in --work.
"""
import argparse, base64, contextlib, hashlib, io, json, os, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import native

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--deps',type=Path,required=True);a=p.parse_args()
    work=a.work.resolve();work.mkdir(exist_ok=False,parents=True)
    stage=work/'source';stage.mkdir()
    for name in ('Includes','Share','FasterLibs'):
        shutil.copytree(ROOT/'src'/name,stage/name)
    variant=ROOT/'config/native-data-variants/parser_retained_v6/src'
    for name in ('GuanhengCommon','GuanhengData','ParserQMTHostRetainedV6'):
        shutil.copytree(variant/name,stage/name)
    shutil.copy2(Path(__file__).with_name('replay.cpp'),stage/'replay.cpp')
    frozen={}
    for name,out in [('current-slot.json','early.json'),('native-source-slot.json','late.json')]:
        raw=(a.fixtures/name).read_bytes();frozen[name]=hashlib.sha256(raw).hexdigest()
        slot=json.loads(raw);body=json.loads(base64.b64decode(slot['result']['result_body_b64']))
        assert body['ok'] and len(body['data'])==8
        (work/out).write_text(json.dumps(body['data'],ensure_ascii=False),encoding='utf8')
    env,_=native.environment(work)
    cl=shutil.which('cl.exe',path=env['PATH']);link=shutil.which('link.exe',path=env['PATH'])
    inc=[stage,a.deps/'rapidjson/include',a.deps/'spdlog/include']+list((a.deps/'boost/libs').glob('*/include'))
    flags=['/nologo','/std:c++17','/EHsc','/MD','/O2','/utf-8','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DBOOST_ALL_NO_LIB','/D_CRT_SECURE_NO_WARNINGS','/FIobjbase.h']+['/I'+str(x) for x in inc]
    sources=['replay.cpp','GuanhengData/QmtTickMapping.cpp','GuanhengData/QmtPollingParser.cpp','GuanhengData/QmtHostEndpoint.cpp','GuanhengData/MarketParser.cpp','GuanhengData/QmtHttpEndpoint.cpp','GuanhengData/QmtHttpClient.cpp','GuanhengCommon/QmtReadTransport.cpp','GuanhengCommon/BoundedSignedHttp.cpp']
    commands=[];objects=[]
    for n,s in enumerate(sources):
        obj=work/(Path(s).stem+'.obj');objects.append(str(obj));rsp=work/(str(n)+'.rsp')
        rsp.write_text(' '.join('"'+x+'"' for x in flags+['/c',str(stage/s),'/Fo'+str(obj)]),encoding='utf8')
        cmd=[cl,'@'+str(rsp)];commands.append(cmd)
        with contextlib.redirect_stdout(io.StringIO()):native.run(cmd,env=env,cwd=work,log=work/(str(n)+'.log'),timeout=60,private_console=True)
    cmd=[link,'/nologo','/out:'+str(work/'replay.exe')]+objects+['winhttp.lib','bcrypt.lib','rpcrt4.lib','ole32.lib','ws2_32.lib'];commands.append(cmd)
    with contextlib.redirect_stdout(io.StringIO()):native.run(cmd,env=env,cwd=work,log=work/'link.log',timeout=60,private_console=True)
    cmd=[str(work/'replay.exe'),str(work/'early.json'),str(work/'late.json')];commands.append(cmd)
    native.run(cmd,env=env,cwd=work,log=work/'run.log',timeout=10,private_console=True)
    # 正式工厂和完整原Common闭包独立链接，SDK替身对象不进入DLL。
    common=['QmtHostReadClient','QmtHostCodec','QmtHostTradeClient','QmtBoundReadCore','QmtHostHistoryClient','QmtHostAccountClient']
    dll_objects=objects[1:]
    for n,s in enumerate(['GuanhengCommon/'+x+'.cpp' for x in common]+['ParserQMTHostRetainedV6/Factory.cpp'],100):
        obj=work/(Path(s).stem+'.obj');dll_objects.append(str(obj));rsp=work/(str(n)+'.rsp')
        rsp.write_text(' '.join('"'+x+'"' for x in flags+['/c',str(stage/s),'/Fo'+str(obj)]),encoding='utf8')
        cmd=[cl,'@'+str(rsp)];commands.append(cmd)
        with contextlib.redirect_stdout(io.StringIO()):native.run(cmd,env=env,cwd=work,log=work/(str(n)+'.log'),timeout=60,private_console=True)
    dll=work/'ParserQMTHostRetainedV6.dll'
    cmd=[link,'/nologo','/DLL','/out:'+str(dll)]+dll_objects+['winhttp.lib','bcrypt.lib','rpcrt4.lib','ole32.lib','ws2_32.lib'];commands.append(cmd)
    with contextlib.redirect_stdout(io.StringIO()):native.run(cmd,env=env,cwd=work,log=work/'dll-link.log',timeout=60,private_console=True)
    result=dict(passed=True,dll_sha256=hashlib.sha256(dll.read_bytes()).hexdigest(),fixture_sha256=frozen,source_sha256={str(x.relative_to(stage)):hashlib.sha256(x.read_bytes()).hexdigest() for x in stage.rglob('*') if x.is_file()},commands=commands,result=(work/'run.log').read_text(encoding='utf8'))
    (work/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(result['result'])
if __name__=='__main__':main()
