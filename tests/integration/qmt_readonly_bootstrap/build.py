"""Build only fixed upstream blobs and NQB self-owned code; no downloads/network."""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys, shutil, uuid, io, re
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import native
COMMIT = "08b230dd05facf6d650d949bfe51054115a2ecb1"
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path);parser.add_argument('--rebuild',action='store_true');parser.add_argument('--probe-source',type=Path);parser.add_argument('--drain-testing',action='store_true');args=parser.parse_args()
    work=args.work or ROOT/'build/native/capability-audit/native-qmt-readonly-bootstrap'/str(uuid.uuid4())
    work.mkdir(parents=True,exist_ok=args.rebuild)
    source=work/'snapshot';source.mkdir(exist_ok=args.rebuild)
    paths=subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',COMMIT,'src/Includes','src/Share','src/FasterLibs','src/Common','src/WtCore','src/WTSTools','src/WTSUtils'],timeout=30,**native.background_process_options()).decode().splitlines()
    # cat-file批量读取原blob，避免git archive按工作树属性进行CRLF转换。
    raw=subprocess.check_output(['git','-C',str(ROOT),'cat-file','--batch'],input=('\n'.join(COMMIT+':'+p for p in paths)+'\n').encode(),timeout=30,**native.background_process_options())
    stream=io.BytesIO(raw);blobs={}
    for name in paths:
        header=stream.readline().split();assert len(header)==3 and header[1]==b'blob',name
        data=stream.read(int(header[2]));assert stream.read(1)==b'\n';blobs[name]=data
    assert not stream.read()
    previous=json.loads((work/"manifest.json").read_text(encoding="utf-8")) if args.rebuild and (work/"manifest.json").exists() else {}
    hashes={}
    for name in paths:
        p=source/name
        if previous.get('commit')==COMMIT and p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==previous.get('source_files',{}).get(name):
            hashes[name]=previous['source_files'][name];continue
        data=blobs[name];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    for folder in ('src/GuanhengQmtBootstrap','src/TraderQMTReadOnly','src/GuanhengCommon','tests/integration/qmt_http_bootstrap','tests/integration/qmt_readonly_bootstrap'):
        shutil.copytree(ROOT/folder,source/folder,dirs_exist_ok=args.rebuild)
    helper="tests/integration/http/test_qmt_http.py"
    (source/helper).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/helper,source/helper)
    env,_=native.environment(work);env['VSLANG']='1033'
    incs=[source/'src',ROOT/'build/native/deps/rapidjson/include',ROOT/'build/native/deps/spdlog/include']+list((ROOT/'build/native/deps/boost/libs').glob('*/include'))+list((ROOT/'build/native/deps/boost/libs').glob('*/*/include'))
    old=ROOT/'build/native/upstream-audit/original-build'
    manifest=json.loads((old/'manifest.json').read_text());assert manifest['commit']==COMMIT
    for name,digest in manifest['source_files'].items():
        assert hashlib.sha256(blobs[name] if name in blobs else subprocess.check_output(['git','-C',str(ROOT),'show',COMMIT+':'+name],timeout=30,**native.background_process_options())).hexdigest()==digest,name
    libs=[old/'cmake/lib/WTSTools.lib',old/'cmake/lib/WTSUtils.lib']+list((old/'cmake/deps/boost/libs').glob('*/*.lib'))
    common=(['/DGH_QMT_HTTP_DRAIN_TESTING'] if args.drain_testing else [])+['/showIncludes','/nologo','/std:c++17','/EHsc','/MD','/O2','/utf-8','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DBOOST_ALL_NO_LIB','/DBOOST_BIND_GLOBAL_PLACEHOLDERS','/D_CRT_SECURE_NO_WARNINGS','/FIobjbase.h']+['/I'+str(p) for p in incs]
    system=['ws2_32.lib','psapi.lib','dbghelp.lib','version.lib','user32.lib','shell32.lib','advapi32.lib','winhttp.lib','bcrypt.lib']
    (work/'traders').mkdir(exist_ok=args.rebuild)
    def compile(name,sources,output,dll=False):
        obj=work/name;obj.mkdir(exist_ok=args.rebuild);argv=common+(['/LD','/DNQB_BUILD_DLL'] if dll else [])+[str(s) for s in sources]+['/Fe'+str(output),'/link','/verbose:lib']+[str(p) for p in libs]+system
        rsp=obj/'compile.rsp';rsp.write_text(subprocess.list2cmdline(argv),encoding='utf-8')
        run=subprocess.run([shutil.which('cl.exe',path=env['PATH']),'@'+str(rsp)],cwd=obj,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,**native.background_process_options(private_console=True))
        (obj/'compile.log').write_bytes(run.stdout);native.display(str(name)+' '+str(run.returncode)+' '+run.stdout.decode(errors='replace')[-3000:]);return run.returncode
    probe_source=(source/args.probe_source.resolve().relative_to(ROOT)) if args.probe_source else source/'tests/integration/qmt_readonly_bootstrap/probe.cpp'
    # 与固定CMake目标保持完整当前定义闭包；配置选fixture/http也会链接SHM门面的引用。
    plugin_sources = ["src/GuanhengQmtBootstrap/ReadOnlyTrader.cpp","src/GuanhengQmtBootstrap/HttpMapping.cpp","src/GuanhengQmtBootstrap/AccountMapping.cpp","src/GuanhengQmtBootstrap/ShmAccountMapping.cpp","src/GuanhengCommon/QmtBoundReadCore.cpp","src/GuanhengCommon/QmtHostAccountClient.cpp","src/GuanhengCommon/QmtHostHistoryClient.cpp","src/GuanhengCommon/QmtHostReadClient.cpp","src/GuanhengCommon/BoundedSignedHttp.cpp","src/GuanhengCommon/QmtReadTransport.cpp","src/TraderQMTReadOnly/Factory.cpp"]
    r=compile('plugin',[source/name for name in plugin_sources],work/'traders/TraderQMTReadOnly.dll',True)
    if not r:
        sources=[source/('src/WtCore/'+f+'.cpp') for f in ['TraderAdapter','WtHelper','ActionPolicyMgr','EventNotifier']]
        r=compile('host',sources+[probe_source],work/'probe.exe')
    inputs={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['src/GuanhengQmtBootstrap','src/TraderQMTReadOnly','src/GuanhengCommon','tests/integration/qmt_http_bootstrap','tests/integration/qmt_readonly_bootstrap'] for p in (source/folder).glob('*') if p.is_file()}
    inputs[helper]=hashlib.sha256((source/helper).read_bytes()).hexdigest()
    drift=[name for name,h in inputs.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h]
    dependencies={}
    for log in work.glob('*/compile.log'):
        # 本地化前缀和源码诊断可混用ANSI/UTF8；只解码路径原字节并核对真实文件。
        for line in log.read_bytes().splitlines():
            match=re.search(rb'([A-Za-z]:[\\/].*)$',line)
            if match:
                candidates=set()
                for encoding in ('utf-8','mbcs'):
                    try:p=Path(match.group(1).strip().decode(encoding,errors='strict'))
                    except UnicodeDecodeError:continue
                    if p.is_file():candidates.add(p.resolve())
                if len(candidates)>1:raise ValueError('ambiguous compiler dependency path')
                for p in candidates:
                    identity=str(p)
                    if identity not in dependencies:dependencies[identity]=hashlib.sha256(p.read_bytes()).hexdigest()
    tools={}
    for name in ('cl.exe','link.exe','c1xx.dll','c2.dll'):
        found=shutil.which(name,path=env['PATH'])
        if not found:
            nearby=Path(shutil.which('cl.exe',path=env['PATH'])).parent/name
            if nearby.is_file():found=str(nearby)
        if found:tools[str(Path(found).resolve())]=hashlib.sha256(Path(found).read_bytes()).hexdigest()
    (work/'actual-tools.json').write_text(json.dumps(tools,indent=2),encoding='utf-8')
    (work/'actual-dependencies.json').write_text(json.dumps(dependencies,indent=2),encoding='utf-8')
    (work/'manifest.json').write_text(json.dumps({'commit':COMMIT,'drain_testing':args.drain_testing,'source_files':hashes,'self_owned':inputs,'libraries':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in libs},'compile_exit':r,'inputs_changed_during_build':drift,'artifacts':{str(p.relative_to(work)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [work/'probe.exe',work/'traders/TraderQMTReadOnly.dll'] if p.exists()},'http_spec_sha256':hashlib.sha256((ROOT/'docs/specs/native-qmt-http-bootstrap.md').read_bytes()).hexdigest(),'read_transport_spec_sha256':hashlib.sha256((ROOT/'docs/specs/qmt-shared-read-transport.md').read_bytes()).hexdigest(),'spec_sha256':hashlib.sha256((ROOT/'docs/specs/native-qmt-readonly-bootstrap.md').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
    native.display('WORK '+str(work));return r or bool(drift)
if __name__=='__main__':raise SystemExit(main())
