"""实际Standard/提交门/owner桥的只读等待红绿回放；无worker、网络或SDK调用。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from native_support.qmt_readonly_fixed import verify_snapshot
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--baseline',action='store_true')
    args=parser.parse_args();build=args.build.resolve();work=args.work.resolve()
    work.mkdir(parents=True,exist_ok=False)
    frozen=build/'inputs/owned';upstream=build/'inputs/upstream'
    verify_snapshot(frozen);verify_snapshot(upstream)
    recipe=json.loads((frozen/'config/execution-product-build.json').read_text(encoding='utf-8'))
    headers={}
    for directory in recipe['owned_directories']:
        for old in (frozen/directory).rglob('*'):
            if old.is_file() and old.suffix in ('.h','.hpp'):
                relative=old.relative_to(frozen);current=ROOT/relative
                if not current.is_file() or sha(old)!=sha(current):raise ValueError('reused dependency header changed')
                headers[relative.as_posix()]=sha(old)
    tools=json.loads((build/'TOOLCHAIN.json').read_text(encoding='utf-8'));env=os.environ.copy();env.update(tools['environment'])
    compiler=Path(env['VCTOOLSINSTALLDIR'])/'bin/HostX64/x64/cl.exe'
    stage=work/'source';(stage/'TraderQMT').mkdir(parents=True)
    source=(build/'inputs/owned'if args.baseline else ROOT)/'src/TraderQMT/StandardQmtTrader.cpp'
    if args.baseline:
        assert sha(source)==recipe['owned_standard_source_sha256']
    (stage/'TraderQMT/StandardQmtTrader.cpp').write_bytes(source.read_bytes())
    probe=Path(__file__).with_name('read_wait_submission_probe.cpp');(stage/'probe.cpp').write_bytes(probe.read_bytes())
    owner=ROOT/'src/GuanhengExecution/OwnerExecCommand.cpp';(stage/'OwnerExecCommand.cpp').write_bytes(owner.read_bytes())
    # 当前实现、probe与Owner的实际stage字节都只包含同一冻结闭包的头；ROOT不进入include路径。
    inc=[stage,frozen/'src',frozen/'src/TraderQMT',frozen/'src/GuanhengExecution',upstream/'src',build/'deps/spdlog/include',build/'deps/rapidjson/include']
    inc+=list((build/'deps/boost/libs').glob('*/include'))
    flags=['/nologo','/std:c++17','/EHsc','/MD','/O2','/utf-8','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DBOOST_ALL_NO_LIB','/D_CRT_SECURE_NO_WARNINGS','/D_SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS','/FIobjbase.h']+['/I'+str(p)for p in inc]
    commands=[]
    def run(argv,label):
        commands.append(list(map(str,argv)))
        process=subprocess.run(commands[-1],env=env,capture_output=True,timeout=120)
        (work/(label+'.log')).write_bytes(process.stdout+process.stderr)
        if process.returncode:raise RuntimeError(label+' failed; inspect private build log')
        return process.stdout.decode('utf-8',errors='replace')
    objects=[]
    for name in ('probe','OwnerExecCommand'):
        obj=work/(name+'.obj');objects.append(obj)
        run([compiler,*flags,'/c',stage/(name+'.cpp'),'/Fo'+str(obj)],name+'-compile')
    reused=list((build/'cmake/product/CMakeFiles/GuanhengStandardTrader.dir').rglob('*.obj'))
    reused=[p for p in reused if p.name!='StandardQmtTrader.cpp.obj']
    # 复用的Common/映射/工厂对象逐一核永久源码与原构建快照一致；当前Standard单独重新编译。
    source_matches={}
    for obj in reused:
        matches=list((build/'inputs/owned/src').rglob(obj.name.removesuffix('.obj')))
        if len(matches)!=1:raise ValueError('ambiguous reused source')
        old=matches[0];relative=old.relative_to(build/'inputs/owned');current=ROOT/relative
        if sha(old)!=sha(current):raise ValueError('reused dependency source changed')
        source_matches[relative.as_posix()]=sha(current)
    libraries=[build/'cmake/lib/WTSTools.lib',build/'cmake/lib/WTSUtils.lib']+list((build/'cmake/product/readonly-support/deps/boost').rglob('*.lib'))
    exe=work/'probe.exe'
    run([compiler.with_name('link.exe'),'/nologo','/out:'+str(exe),*objects,*reused,*libraries,
        'winhttp.lib','bcrypt.lib','synchronization.lib','ws2_32.lib','psapi.lib','dbghelp.lib','version.lib','user32.lib','shell32.lib','advapi32.lib','ole32.lib'],'link')
    output=run([exe,*(['--expect-regression']if args.baseline else [])],'run')
    verify_snapshot(frozen);verify_snapshot(upstream)
    result=dict(passed=True,baseline=args.baseline,output=output,standard_source_sha256=sha(stage/'TraderQMT/StandardQmtTrader.cpp'),
        probe_source_sha256=sha(stage/'probe.cpp'),owner_source_sha256=sha(stage/'OwnerExecCommand.cpp'),executable_sha256=sha(exe),
        frozen_owned_manifest_sha256=sha(frozen/'input.json'),frozen_upstream_manifest_sha256=sha(upstream/'input.json'),
        reused_header_identity=headers,
        reused_binary_inputs={str(p):sha(p)for p in reused+libraries},reused_source_identity=source_matches,
        commands=commands,real_sdk_calls=0,financial_files_written=0)
    (work/'RESULT.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(output)

if __name__=='__main__':main()
