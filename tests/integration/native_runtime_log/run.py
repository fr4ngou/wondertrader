"""Link the real fixed WT logger and exercise private bounded logging, no service."""
import argparse, contextlib, hashlib, io, json, os, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import native

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--build',type=Path,required=True);a=p.parse_args()
    work=a.work.resolve();work.mkdir(exist_ok=False,parents=True);build=a.build.resolve()
    env=os.environ.copy();env.update(json.loads((build/'TOOLCHAIN.json').read_text(encoding='utf8'))['environment'])
    temp=work/'temp';temp.mkdir();env.update(TEMP=str(temp),TMP=str(temp))
    cl=shutil.which('cl.exe',path=env['PATH']);link=shutil.which('link.exe',path=env['PATH'])
    stage=work/'source';(stage/'GuanhengExecution').mkdir(parents=True)
    shutil.copy2(ROOT/'src/GuanhengExecution/NativeRuntimeLog.h',stage/'GuanhengExecution/NativeRuntimeLog.h')
    shutil.copy2(Path(__file__).with_name('probe.cpp'),stage/'probe.cpp')
    inc=[stage,build/'inputs/upstream/src',build/'deps/spdlog/include',build/'deps/rapidjson/include']+list((build/'deps/boost/libs').glob('*/include'))
    flags=['/nologo','/std:c++17','/EHsc','/MD','/O2','/utf-8','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DBOOST_ALL_NO_LIB','/D_CRT_SECURE_NO_WARNINGS','/FIobjbase.h']+['/I'+str(x) for x in inc]
    obj=work/'probe.obj';rsp=work/'compile.rsp';rsp.write_text(' '.join('"'+x+'"' for x in flags+['/c',str(stage/'probe.cpp'),'/Fo'+str(obj)]),encoding='utf8')
    commands=[[cl,'@'+str(rsp)]]
    with contextlib.redirect_stdout(io.StringIO()):native.run(commands[-1],env=env,cwd=work,log=work/'compile.log',timeout=60,private_console=True)
    libraries=[build/'cmake/lib/WTSTools.lib',build/'cmake/lib/WTSUtils.lib']+list((build/'cmake/product/readonly-support/deps/boost').rglob('*.lib'))
    commands.append([link,'/nologo','/out:'+str(work/'probe.exe'),str(obj)]+[str(x) for x in libraries]+['synchronization.lib','ws2_32.lib','psapi.lib','dbghelp.lib','version.lib','user32.lib','shell32.lib','advapi32.lib'])
    with contextlib.redirect_stdout(io.StringIO()):native.run(commands[-1],env=env,cwd=work,log=work/'link.log',timeout=60,private_console=True)
    modes = ('normal','rotation','utf8','open-failure','write-failure','batch',
             'first-error-failure','first-error-concurrent','first-error-utf8','runtime-failure')
    for mode in modes:
        commands.append([str(work/'probe.exe'),mode,str(work/mode)])
        native.run(commands[-1],env=env,cwd=work,log=work/(mode+'.log'),timeout=20,private_console=True)
    # 按原UTF-8字节和物理文件验收，覆盖中文边界与轮转实际落盘。
    rotated=[work/'rotation'/name for name in ('native.log','native.1.log','native.2.log','native.3.log')]
    assert len(rotated)==4 and all(0<x.stat().st_size<=1048576 for x in rotated)
    assert 'rotation-tail' in (work/'rotation/native.log').read_text(encoding='utf8')
    first=work/'rotation/native-first-error.log'
    assert 'earliest-source-failure' in first.read_text(encoding='utf8')
    assert first.stat().st_size <= 8192+256
    assert (work/'first-error-failure/native-first-error.log').read_text(encoding='utf8').count('first-copy-recovered') == 1
    assert (work/'first-error-concurrent/native-first-error.log').read_text(encoding='utf8').count('concurrent-first-error') == 1
    text=(work/'first-error-utf8/native-first-error.log').read_text(encoding='utf8')
    assert text.split('] ',1)[1].strip() == 'a'*8191
    assert not (work/'batch/native-first-error.log').exists()
    contents=(work/'utf8/native.log').read_text(encoding='utf8').splitlines()
    bodies=[line.split('] ',1)[1] for line in contents]
    assert [len(x.encode('utf8')) for x in bodies]==[8191,8190,8192]
    assert bodies==['a'*8191,'b'*8190,'c'*8192]
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    result=dict(passed=True,physical_rotated_files={x.name:x.stat().st_size for x in rotated},utf8_body_bytes=[len(x.encode('utf8')) for x in bodies],results={mode:(work/(mode+'.log')).read_text(encoding='utf8') for mode in modes},commands=commands,source_sha256={str(x.relative_to(stage)):sha(x) for x in stage.rglob('*') if x.is_file()},libraries={str(x):sha(x) for x in libraries})
    (work/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf8')
if __name__=='__main__':main()
