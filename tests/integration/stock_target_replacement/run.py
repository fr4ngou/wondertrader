"""固定源码/已批准覆盖干净构建公开工厂，重放冻结形态；真实交易调用0。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from execution_product import git_blobs,write_snapshot,verify_snapshot,source_files,save,digest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--toolchain',type=Path,required=True)
    parser.add_argument('--dependencies',type=Path,required=True)
    args=parser.parse_args()
    if not args.work.is_absolute() or args.work.exists():raise ValueError('new absolute work required')
    args.work.mkdir(parents=True)
    recipe=json.loads((ROOT/'config/execution-product-build.json').read_text(encoding='utf-8'))
    up=args.work/'upstream';entries=git_blobs(ROOT,recipe['upstream_commit'],tuple(recipe['upstream_roots']))
    write_snapshot(up,entries,commit=recipe['upstream_commit'])
    for name,row in recipe['patched_files'].items():
        assert digest((up/name).read_bytes())==row['baseline_sha256']
        (up/name).write_bytes((up/name).read_bytes().replace(b'\r\n',b'\n'))
    commands=[]
    env=os.environ.copy();toolchain=json.loads(args.toolchain.read_text(encoding='utf-8'));env.update(toolchain['environment'])
    def run(argv,label,cwd=None):
        commands.append([str(x)for x in argv]);save(args.work/'COMMANDS.json',commands)
        process=subprocess.run(list(map(str,argv)),cwd=cwd or args.work,env=env,capture_output=True,timeout=600)
        (args.work/(label+'.log')).write_bytes(process.stdout+process.stderr)
        if process.returncode:raise RuntimeError(label+' failed: '+str(process.returncode))
        return process.stdout.decode('utf-8',errors='replace')
    for index,row in enumerate(recipe['overlays']):
        patch=ROOT/row['path'];assert digest(patch.read_bytes())==row['sha256']
        run(['git','-c','core.autocrlf=false','-c','core.safecrlf=false','apply','--no-index','--check',patch],'overlay-check-'+str(index),up)
        run(['git','-c','core.autocrlf=false','-c','core.safecrlf=false','apply','--no-index',patch],'overlay-apply-'+str(index),up)
    manifest=json.loads((up/'input.json').read_text(encoding='utf-8'))
    for name,row in recipe['patched_files'].items():
        assert digest((up/name).read_bytes())==row['normalized_result_sha256']
        manifest['files'][name]=dict(sha256=row['normalized_result_sha256'])
    save(up/'input.json',manifest);verify_snapshot(up)
    # 自有源码独立快照，Root继续编辑现场日志入口不会改变此工厂/准入测试的输入。
    own=args.work/'owned';owned=source_files(recipe)
    test_root=Path(__file__).resolve().parent
    for path in test_root.glob('*.cpp'):
        name=path.relative_to(ROOT).as_posix();raw=path.read_bytes();owned[name]=dict(data=raw,sha256=digest(raw))
    for name in entries:
        raw=(up/name).read_bytes();owned[name]=dict(data=raw,sha256=digest(raw))
    write_snapshot(own,owned)
    save(args.work/'SOURCE.json',dict(upstream_commit=recipe['upstream_commit'],
        overlays=recipe['overlays'],upstream_manifest_sha256=digest((up/'input.json').read_bytes()),
        owned_manifest_sha256=digest((own/'input.json').read_bytes()),
        compiler_environment_sha256=digest(args.toolchain.read_bytes()),prior_project_binary_inputs=0))
    cmake=args.work/'project';cmake.mkdir()
    text='''cmake_minimum_required(VERSION 3.24)
project(StockTargetRegression LANGUAGES C CXX)
set(GH_STANDARD_CTA_HOST ON CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory("${GH_FIXED_OWN_ROOT}/cmake/native/qmt_standard_product" product EXCLUDE_FROM_ALL)
add_executable(TargetFactoryProbe "${GH_FIXED_OWN_ROOT}/tests/integration/stock_target_replacement/factory_probe.cpp")
guanheng_configure_standard_target(TargetFactoryProbe)
add_executable(TargetAdmissionProbe "${GH_FIXED_OWN_ROOT}/tests/integration/stock_target_replacement/host_admission_probe.cpp")
guanheng_configure_standard_target(TargetAdmissionProbe)
target_compile_options(TargetAdmissionProbe PRIVATE /Gy /Gw)
target_link_options(TargetAdmissionProbe PRIVATE /OPT:REF)
target_sources(TargetAdmissionProbe PRIVATE $<TARGET_OBJECTS:NqpAdapterHost>
  "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtLocalExecuter.cpp"
  "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtExecuterFactory.cpp")
target_link_libraries(TargetAdmissionProbe PRIVATE GuanhengBrokerQueryContext)
'''
    (cmake/'CMakeLists.txt').write_text(text,encoding='utf-8')
    compiler=Path(env['VCTOOLSINSTALLDIR'])/'bin/HostX64/x64/cl.exe'
    tools=toolchain['tools'];build=args.work/'cmake'
    run([tools['cmake'],'-S',cmake,'-B',build,'-G','Ninja','-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_MAKE_PROGRAM='+tools['ninja'],'-DCMAKE_CXX_COMPILER='+str(compiler),'-DCMAKE_C_COMPILER='+str(compiler),
        '-DWT_DEPS_DIR='+str(args.dependencies),'-DPython3_EXECUTABLE='+sys.executable,
        '-DGH_FIXED_UPSTREAM_ROOT='+str(up),'-DGH_FIXED_OWN_ROOT='+str(own)],'configure')
    run([tools['cmake'],'--build',build,'--target','GuanhengOriginalExecutionFactory','TargetFactoryProbe','TargetAdmissionProbe','--parallel','2'],'build')
    dll=build/'bin/executers/WtExeFact.dll';probe=build/'TargetFactoryProbe.exe'
    admission=run([build/'TargetAdmissionProbe.exe'],'admission')
    assert 'host_config_admission=passed' in admission
    cases=[('159780','SZSE.ETF.159780',220700,22000,22000,22000,0,1000,0,False),
        ('512100','SSE.ETF.512100',76400,76200,76200,76200,0,200,0,False),
        ('515080','SSE.ETF.515080',136800,136800,136800,136700,0,0,100,False),
        ('fresh','SZSE.ETF.159780',-1,22000,22000,22000,0,0,0,False),
        ('pending','SZSE.ETF.159780',220700,22000,22000,22000,1000,0,0,False),
        ('separate_available','SZSE.ETF.159780',220700,23000,22000,22000,0,1000,0,False),
        ('two_steps','SZSE.ETF.159780',220700,22000,22000,22000,0,2000,0,True)]
    results=[]
    for mode in ('default','false','true'):
        for selected in ('WtStockMinImpactExeUnit','WtStockMinImpactBorrowedExeUnit'):
            for name,code,old,total,available,new,undone,buy,sell,two in cases:
                output=run([probe,dll,code,old,total,available,new,undone,mode,selected,*(['two']if two else [])],selected+'-'+mode+'-'+name)
                result=json.loads(next(s[7:]for s in output.splitlines()if s.startswith('RESULT ')))
                if mode=='true':
                    buy=0;sell=1000 if name=='separate_available'else sell
                assert result['buy_quantity']==buy and result['sell_quantity']==sell,(mode,name,result,buy,sell)
                assert result['undone_unchanged']==undone and result['cancel_calls']==0
                assert result['original_order_retained']==bool(undone)
                results.append(dict(mode=mode,algorithm=selected,case=name,result=result))
    verify_snapshot(up);verify_snapshot(own)
    save(args.work/'RESULT.json',dict(passed=True,dll=str(dll),dll_sha256=digest(dll.read_bytes()),
        source_commit=recipe['upstream_commit'],overlay=recipe['overlays'][1],cases=results,
        host_admission_passed=True,real_sdk_calls=0,financial_files_written=0,previous_binary_inputs=0))
    print(json.dumps(dict(passed=True,cases=len(results),dll=str(dll),dll_sha256=digest(dll.read_bytes()))))

if __name__=='__main__':main()
