"""Freeze owned sources, use ordinary Flit and original Runtime closure, install four pinned wheels.
No running installation is a product source; copied third-party dependencies are verified separately.
"""
import argparse,base64,csv,hashlib,io,json,os,shutil,sys,tomllib,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import native
from source_packages import owned,append_core_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--backend',type=Path,required=True)
    parser.add_argument('--python',type=Path,required=True)
    args=parser.parse_args();work=args.work.resolve();work.mkdir(exist_ok=False,parents=True)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    backend=args.backend.resolve();expected=json.loads((ROOT/'config/python-build-dependencies.json').read_bytes())['dependencies'][0]
    assert sha(backend)==expected['sha256']
    stage=work/'source';stage.mkdir();wheels=work/'wheels';wheels.mkdir()
    files={};commands=[]
    def admit(relative,target):
        source=owned(relative);files[relative]=sha(source);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
    for role,relative,module in [('v1','apps/guanheng/strategy_v1','guanheng_strategy_v1'),('awp','apps/analysis_window_producer','guanheng_analysis_window_producer')]:
        project=stage/role
        for name in ['pyproject.toml','README.md']:admit(relative+'/'+name,project/name)
        for p in (ROOT/relative/module).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                admit(p.relative_to(ROOT).as_posix(),project/p.relative_to(ROOT/relative))
    core_config=json.loads((ROOT/'config/source-packages.json').read_bytes())
    files['config/source-packages.json']=sha(ROOT/'config/source-packages.json')
    core=stage/'core'
    for name in ['pyproject.toml','README.md']:admit('packages/native-analysis-core/'+name,core/name)
    export={};origins={}
    for member,relative in core_config['core_members'].items():
        if member.startswith('integrations/'):admit(relative,core/member)
        else:
            source=owned(relative);files[relative]=sha(source);export[member]=source.read_bytes()
        origins[member]=dict(source=relative,sha256=files[relative])
    (core/'integrations/ORIGINS.json').write_text(json.dumps(dict(schema='guanheng.native-core-permanent-sources.v1',members=origins),sort_keys=True,separators=(',',':')),encoding='utf8')
    closure=ROOT/'apps/wt_runtime/source_closures/0.1.0a15+currentaux.1'
    for p in closure.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:admit(p.relative_to(ROOT).as_posix(),stage/'runtime-closure'/p.relative_to(closure))
    for name in ['scripts/source_packages.py','scripts/client_sdk.py','scripts/native_support/process_startup.py','scripts/native.py','tests/integration/current_auxiliary/build_candidate.py']:
        files[name]=sha(ROOT/name)
    frozen=dict(schema='guanheng.current-auxiliary-frozen-source.v1',files=files,backend_sha256=sha(backend),build_python=str(args.python.resolve()),production_sources=False)
    (work/'FROZEN-SOURCE.json').write_text(json.dumps(frozen,indent=2),encoding='utf8')
    environment=dict(os.environ,SOURCE_DATE_EPOCH='315532800',PYTHONDONTWRITEBYTECODE='1')
    def run(command,name,cwd=work):
        commands.append([str(v) for v in command]);native.run(commands[-1],cwd=cwd,env=environment,log=work/name,timeout=120,private_console=True)
    for role in ['v1','awp','core']:
        run([args.python,'-I','-B','-c','import sys;sys.path.insert(0,sys.argv[1]);from flit_core.buildapi import build_wheel;build_wheel(sys.argv[2])',backend,wheels],role+'-build.log',stage/role)
    core_wheel=next(wheels.glob('guanheng_native_analysis_core-*.whl'));append_core_export(core_wheel,export)
    run([args.python,'-I','-B',stage/'runtime-closure/build.py','--repository',ROOT,'--backend',backend,'--work',work/'runtime-project','--output',work/'runtime-wheels'],'runtime-build.log')
    runtime=next((work/'runtime-wheels').glob('*.whl'));shutil.copy2(runtime,wheels/runtime.name)
    assert all(sha(ROOT/name)==digest for name,digest in files.items()),'product source changed during build'
    products={}
    from email import message_from_bytes
    for wheel in wheels.glob('*.whl'):
        with zipfile.ZipFile(wheel) as archive:
            names=archive.namelist();assert len(names)==len(set(names))
            record=next(n for n in names if n.endswith('.dist-info/RECORD'))
            for member,checksum,size in csv.reader(io.StringIO(archive.read(record).decode())):
                if member==record:continue
                raw=archive.read(member);assert len(raw)==int(size)
                assert checksum=='sha256='+base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
            meta=message_from_bytes(archive.read(next(n for n in names if n.endswith('.dist-info/METADATA'))))
            products[meta['Name']]=dict(version=meta['Version'],path=str(wheel),sha256=sha(wheel),requires_dist=meta.get_all('Requires-Dist') or [],members={n:hashlib.sha256(archive.read(n)).hexdigest() for n in names if not n.endswith('/')})
    assert len(products)==4
    lock=work/'INSTALL.lock';lock.write_text(''.join(name+'=='+item['version']+' --hash=sha256:'+item['sha256']+'\n' for name,item in sorted(products.items())),encoding='ascii')
    uv=Path('C:/Users/frangou/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe/uv.exe')
    run([uv,'pip','install','--python',args.python,'--offline','--no-config','--no-index','--no-deps','--reinstall','--require-hashes','--find-links',wheels,'-r',lock],'install.log')
    run([uv,'pip','check','--python',args.python],'pip-check.log')
    site=args.python.resolve().parent.parent/'Lib/site-packages'
    for name,item in products.items():
        for member,digest in item['members'].items():
            if member.endswith('.dist-info/RECORD'):continue
            assert sha(site/member)==digest,(name,member)
    assert all(sha(ROOT/name)==digest for name,digest in files.items()),'product source changed before qualification'
    result=dict(passed=True,products=products,commands=commands,python=str(args.python.resolve()),source_manifest_sha256=sha(work/'FROZEN-SOURCE.json'),backend_sha256=sha(backend),services_started=0,SDK_calls=0,production_writes=0)
    (work/'BUILD.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=True,products={name:dict(version=item['version'],sha256=item['sha256']) for name,item in products.items()},python=result['python']),indent=2))
if __name__=='__main__':main()
