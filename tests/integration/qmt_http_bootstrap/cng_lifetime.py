"""实际映射TU的CNG backing-store顺序回归；只运行独立合成子进程。"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"scripts"))
import native
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-build',type=Path);parser.add_argument('--probe',type=Path);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--expect-red',action='store_true');args=parser.parse_args();work=args.work.resolve();work.mkdir(parents=True,exist_ok=False)
    metadata={}
    if args.probe is not None:
        executable=args.probe.resolve(strict=True)
    else:
        if args.source_build is None:raise ValueError('provide explicit --probe or legacy --source-build')
        build=args.source_build.resolve();source=Path(__file__).with_suffix('.cpp');snapshot=work/source.name;snapshot.write_bytes(source.read_bytes());manifest=json.loads((build/'manifest.json').read_text(encoding='utf-8'));mapping=build/'snapshot/src/GuanhengQmtBootstrap/AccountMapping.cpp';assert sha(mapping)==manifest['self_owned'][str(mapping.relative_to(build/'snapshot'))]
        env,_=native.environment(work);env['VSLANG']='1033';rsp=(build/'host/compile.rsp').read_text(encoding='utf-8');rsp=re.sub(r'(?::?"[^\"]+\.cpp"|\S+\.cpp)','',rsp);rsp=re.sub(r'/Fe\S+',lambda _: '/Fe'+str(work/'probe.exe'),rsp);rsp=str(snapshot)+' '+rsp;(work/'compile.rsp').write_text(rsp,encoding='utf-8')
        proc=subprocess.run([shutil.which('cl.exe',path=env['PATH']),'@'+str(work/'compile.rsp')],cwd=work,env=env,capture_output=True,timeout=120,**native.background_process_options(private_console=True));(work/'compile.log').write_bytes(proc.stdout+proc.stderr);assert proc.returncode==0,'compile failed: '+str(work/'compile.log')
        executable=work/'probe.exe';metadata=dict(source_build=str(build),source_build_manifest_sha256=sha(build/'manifest.json'),mapping_sha256=sha(mapping),probe_source_sha256=sha(snapshot),host_response_sha256=sha(build/'host/compile.rsp'),compile_exit=0)
    binary_digest=sha(executable)
    results=[]
    for mode in ('success','hash-data-failure','finish-failure'):
        argv=[str(executable),mode];proc=subprocess.run(argv,cwd=work,capture_output=True,timeout=5,**native.background_process_options());(work/(mode+'.log')).write_bytes(proc.stdout+proc.stderr);value=json.loads(proc.stdout)
        assert proc.returncode==(1 if args.expect_red else 0),(mode,proc.returncode,value)
        assert value['fixed_vector_or_expected_failure'] and value['created']==value['destroyed']==value['closed']==value['backing_deleted']==1
        assert value['early_backing_release']==args.expect_red and value['test_deferred_physical_free']==args.expect_red
        results.append(dict(case=mode,passed=not args.expect_red,expected_red=args.expect_red,argv=argv,result=value))
    assert sha(executable)==binary_digest
    report=dict(passed=0 if args.expect_red else 3,failed=3 if args.expect_red else 0,expected_red=args.expect_red,runner_sha256=sha(Path(__file__)),probe_sha256=binary_digest,cases=results,**metadata)
    (work/'summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');print('EXPECTED RED' if args.expect_red else 'PASS',3,work);return 0
if __name__=='__main__':raise SystemExit(main())
