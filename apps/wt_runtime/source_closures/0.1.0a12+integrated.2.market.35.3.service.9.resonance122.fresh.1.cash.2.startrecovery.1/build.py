"""固定原45模块加单一Controller覆盖的普通离线wheel；不操作任何服务。"""
from __future__ import annotations
import argparse
from email import message_from_bytes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile


def sha(raw): return hashlib.sha256(raw).hexdigest()


def exact(raw, expected):
    normalized = raw.replace(b'\r\n', b'\n')
    for value in (raw, normalized, normalized.replace(b'\n', b'\r\n')):
        if sha(value) == expected:return value
    raise ValueError('fixed source identity differs')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parent;repo=root.parents[3]
    identity_raw=(root/'SOURCE-MANIFEST.json').read_bytes();identity=json.loads(identity_raw)
    exact(Path(__file__).read_bytes(),identity['builder_sha256'])
    baseline=root.parent/identity['baseline_closure']
    baseline_raw=exact((baseline/'SOURCE-MANIFEST.json').read_bytes(),identity['baseline_manifest_sha256'])
    parent=json.loads(baseline_raw)
    payload={}
    for row in parent['modules']:
        name=row['name']
        if re.fullmatch(r'(?:[a-z][a-z0-9_]*|__init__|__main__)\.py',name)is None:raise ValueError('module name')
        if name in identity['overrides']:
            raw=(root/'overlays/guanheng_wt_runtime'/name).read_bytes()
            expected=identity['overrides'][name]
        elif row['source']=='overlay':
            raw=(baseline/'overlays/guanheng_wt_runtime'/name).read_bytes();expected=row['sha256']
        elif row['source']=='base':
            result=subprocess.run(['git','-C',str(repo),'show',parent['base_commit']+':apps/wt_runtime/guanheng_wt_runtime/'+name],
                capture_output=True,timeout=30,check=True)
            raw=result.stdout;expected=row['sha256']
        else:raise ValueError('fixed source origin')
        payload['guanheng_wt_runtime/'+name]=exact(raw,expected)
    if len(payload)!=45:raise ValueError('fixed module set')
    project=exact((root/'pyproject.toml').read_bytes(),identity['pyproject_sha256'])
    work=args.work.absolute();output=args.output.absolute()
    if work==output or work.is_relative_to(output)or output.is_relative_to(work):raise ValueError('separate new paths')
    work.mkdir();output.mkdir()
    for name,raw in payload.items():
        path=work/name;path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    (work/'pyproject.toml').write_bytes(project)
    options={'creationflags':subprocess.CREATE_NO_WINDOW}if os.name=='nt'else{}
    completed=subprocess.run(['uv','build','--offline','--wheel','--out-dir',str(output),str(work)],
        capture_output=True,timeout=120,env=dict(os.environ,SOURCE_DATE_EPOCH='315532800',PYTHONDONTWRITEBYTECODE='1'),**options)
    if completed.returncode:sys.stderr.buffer.write(completed.stderr);return completed.returncode
    wheels=list(output.glob('*.whl'))
    if len(wheels)!=1:raise ValueError('one Runtime wheel required')
    with zipfile.ZipFile(wheels[0])as wheel:
        members={n:wheel.read(n)for n in wheel.namelist()if '.dist-info/'not in n}
        metadata=message_from_bytes(wheel.read(next(n for n in wheel.namelist()if n.endswith('.dist-info/METADATA'))))
    if members!=payload or metadata['Name']!='guanheng-wt-runtime'or metadata['Version']!=identity['version']:
        raise ValueError('built wheel differs')
    if (root/'SOURCE-MANIFEST.json').read_bytes()!=identity_raw:raise ValueError('source identity drift')
    for name,expected in identity['overrides'].items():exact((root/'overlays/guanheng_wt_runtime'/name).read_bytes(),expected)
    exact((root/'pyproject.toml').read_bytes(),identity['pyproject_sha256'])
    report=dict(schema='wt.runtime-preexecution-rebuild.v1',  # 本模块工程制品身份，不授线上运行资格。
        version=identity['version'],module_count=45,  # 实际普通wheel发行与固定源码成员数。
        baseline_manifest_sha256=sha(baseline_raw),  # 继承的原cash.2闭包原字节摘要。
        source_manifest_sha256=sha(identity_raw),  # 本代覆盖清单原字节摘要。
        wheel=str(wheels[0]),wheel_sha256=sha(wheels[0].read_bytes()),  # 新普通发行路径及整个ZIP身份。
        all_payload_bytes_verified=True,services_started=0,sdk_calls=0)  # 原45个产品成员逐字节核验，无线上副作用。
    (output/'REBUILD-RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report));return 0


if __name__=='__main__':raise SystemExit(main())
