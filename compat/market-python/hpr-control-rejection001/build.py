"""核固定兼容源码后调用正常Flit构建；离线、不读取现场配置、不更改运行实例。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    identity=json.loads((root/'SOURCE-IDENTITY.json').read_bytes())
    project=root/'host';package=project/'guanheng_qmt_shm'
    actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in package.glob('*.py')}
    if actual!=identity['compatible_files']:
        raise ValueError('HPR compatible source differs')
    for name,expected in identity['project_files'].items():
        if hashlib.sha256((project/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('HPR compatible project differs')
    agent=root/'agent'
    if {'guanheng_qmt_shm_agent/'+p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (agent/'guanheng_qmt_shm_agent').glob('*.py')}!=identity['agent_wheel']['package_files']:
        raise ValueError('original HPR Agent source differs')
    for name,expected in identity['agent_project_files'].items():
        if hashlib.sha256((agent/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('original HPR Agent project differs')
    output=args.out_dir.absolute();output.mkdir(parents=True,exist_ok=True)
    environment=dict(os.environ,SOURCE_DATE_EPOCH='315532800',PYTHONDONTWRITEBYTECODE='1')
    options={'creationflags':subprocess.CREATE_NO_WINDOW}if os.name=='nt'else{}
    for source in (agent,project):
        result=subprocess.run(['uv','build','--offline','--wheel','--out-dir',str(output),str(source)],
            env=environment,capture_output=True,timeout=120,**options)
        if result.returncode:
            sys.stderr.buffer.write(result.stderr)
            return result.returncode
    print(json.dumps(dict(version=identity['compatible_version'],source_verified=True,out_dir=str(output))))
    return 0


if __name__=='__main__':raise SystemExit(main())
