"""从固定Git、版本化overlay和普通纯策略/QNA源码重建fresh cash.5三包。

仅在新的work/output目录组装与构建；不导入产品模块、不读账户或已安装角色。
显式离线Flit后端由摘要绑定，历史wheel只在清单中保留比对身份，不参与构建。
"""
from __future__ import annotations

import argparse
from email import message_from_bytes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile


VERSION='0.1.0a12+integrated.2.market.35.3.service.9.resonance121.fresh.1.cash.5'
BASE_COMMIT='9a0b3f9a36a991a1bfc74af8d1fa315dbf4798b3'
BACKEND_SHA256='e7a0304069ea895172e3c7bb703292e992c5d1555dd1233ab7b5621b5b69e62c'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def exact_value(raw, expected, label):
    """Git换行设置可以不同；交付内容最终恢复为清单绑定的原产品字节。"""
    normalized=raw.replace(b'\r\n',b'\n')
    for value in (raw,normalized,normalized.replace(b'\n',b'\r\n')):
        if digest(value)==expected:return value
    raise ValueError('source_sha256:'+label)


def relative_path(value):
    """清单路径仅可指向所属树内普通相对文件，拒绝盘符、上跳和反斜线。"""
    if type(value)is not str or not value or '\\'in value or ':'in value:
        raise ValueError('source_path')
    name=PurePosixPath(value)
    if name.is_absolute()or '..'in name.parts or str(name)!=value:
        raise ValueError('source_path')
    return value


def owned(root, name):
    path=root/relative_path(name)
    if not path.is_file()or any(p.is_symlink()or getattr(p.lstat(),'st_file_attributes',0)&0x400
            for p in (path,*path.parents)if p.is_relative_to(root)):
        raise ValueError('regular_source_required:'+name)
    return path


def read_committed(repository, name):
    result=subprocess.run(['git','-C',str(repository),'show',
        BASE_COMMIT+':apps/wt_runtime/guanheng_wt_runtime/'+name],
        stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
    if result.returncode:raise ValueError('base_commit_source:'+name)
    return result.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--backend',type=Path,required=True)
    parser.add_argument('--base-repository',type=Path)
    args=parser.parse_args();closure=Path(__file__).resolve().parent;repository=closure.parents[3]
    base_repository=(args.base_repository or repository).resolve(strict=True)
    work=args.work.resolve();output=args.output.resolve()
    if work==output or work.is_relative_to(output)or output.is_relative_to(work):raise ValueError('distinct_build_directories')
    if work.exists()or output.exists():raise FileExistsError('work_and_output_must_be_new')
    backend_source=args.backend.resolve(strict=True);backend_raw=backend_source.read_bytes()
    if digest(backend_raw)!=BACKEND_SHA256:raise ValueError('build_backend_identity')
    raw_manifest=owned(closure,'SOURCE-MANIFEST.json').read_bytes();manifest=json.loads(raw_manifest)
    if manifest['schema']!='wt.runtime-source-closure.v1'or manifest['base_commit']!=BASE_COMMIT or manifest['version']!=VERSION:
        raise ValueError('source_manifest')
    modules=manifest['modules'];names=[row['name']for row in modules]
    if len(names)!=44 or len(set(names))!=44 or names!=sorted(names)or any(
            re.fullmatch(r'(?:[a-z][a-z0-9_]*|__init__|__main__)\.py',name)is None for name in names):
        raise ValueError('module_set')
    overlays=closure/'overlays/guanheng_wt_runtime'
    if {p.name for p in overlays.iterdir()}!={r['name']for r in modules if r['source']=='overlay'}:
        raise ValueError('overlay_set')
    # 先准入全部永久源码；任何漂移均在创建新构建树之前报错。
    admitted={}
    required_tools={'scripts/source_packages.py','scripts/client_sdk.py','scripts/native_support/__init__.py',
        'scripts/native_support/process_startup.py',(closure/'build.py').relative_to(repository).as_posix()}
    if type(manifest.get('build_tools'))is not dict or set(manifest['build_tools'])!=required_tools:
        raise ValueError('build_tool_set')
    for name,expected in manifest['build_tools'].items():
        exact_value(owned(repository,name).read_bytes(),expected,name)
    runtime={}
    for row in modules:
        if row['source']=='overlay':raw=owned(overlays,row['name']).read_bytes()
        elif row['source']=='base':raw=read_committed(base_repository,row['name'])
        else:raise ValueError('module_source')
        runtime['guanheng_wt_runtime/'+row['name']]=exact_value(raw,row['sha256'],row['name'])
    runtime['pyproject.toml']=exact_value(owned(closure,'pyproject.toml').read_bytes(),manifest['pyproject_sha256'],'runtime metadata')
    admitted['runtime']=runtime
    for role in ('strategy','qna'):
        selected={}
        for member,row in manifest['companions'][role]['sources'].items():
            selected[relative_path(member)]=exact_value(owned(repository,row['source']).read_bytes(),row['sha256'],row['source'])
        admitted[role]=selected
    work.mkdir(parents=True);output.mkdir(parents=True)
    backend_copy=work/'deps/flit_core-3.12.0-py3-none-any.whl';backend_copy.parent.mkdir()
    backend_copy.write_bytes(backend_raw)
    environment=dict(os.environ,SOURCE_DATE_EPOCH='315532800',PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
    results=[]
    for role in ('runtime','strategy','qna'):
        project=work/role;project.mkdir();additions={}
        for member,raw in admitted[role].items():
            if role=='qna'and member not in ('pyproject.toml','README.md')and not member.startswith('integrations/'):
                additions[member]=raw;continue
            target=project/member;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        role_output=output/role;role_output.mkdir()
        command=[sys.executable,'-I','-B','-c',
            'import sys;sys.path.insert(0,sys.argv[1]);from flit_core.buildapi import build_wheel;build_wheel(sys.argv[2])',
            str(backend_copy),str(role_output)]
        completed=subprocess.run(command,cwd=project,env=environment,capture_output=True,timeout=120)
        (work/(role+'-build.log')).write_bytes(completed.stdout+completed.stderr)
        if completed.returncode:raise RuntimeError('wheel_build_failed:'+role)
        wheels=list(role_output.glob('*.whl'))
        if len(wheels)!=1:raise ValueError('wheel_count:'+role)
        wheel=wheels[0]
        if additions:
            # 沿仓库原Core公开重导出映射和RECORD实现，不重写第二套打包算法。
            sys.path.insert(0,str(repository/'scripts'))
            from source_packages import append_core_export
            append_core_export(wheel,additions)
        descriptor=manifest if role=='runtime'else manifest['companions'][role]
        with zipfile.ZipFile(wheel)as archive:
            payload={name:archive.read(name)for name in archive.namelist()if '.dist-info/'not in name and not name.endswith('/')}
            expected=descriptor['payload_sha256']
            if set(payload)!=set(expected):raise ValueError('wheel_payload_set:'+role)
            if any(digest(raw)!=expected[name]for name,raw in payload.items()):raise ValueError('wheel_payload_sha256:'+role)
            metadata=archive.read(next(n for n in archive.namelist()if n.endswith('.dist-info/METADATA')))
            if digest(metadata)!=descriptor['metadata_sha256']:raise ValueError('wheel_metadata:'+role)
            parsed=message_from_bytes(metadata)
        results.append(dict(
            role=role,  # 构建角色：runtime、strategy或qna；分别拥有固定来源和元数据。
            name=parsed['Name'],version=parsed['Version'],  # 实际产物METADATA中的发行名和版本。
            wheel=str(wheel),wheel_sha256=digest(wheel.read_bytes()),  # 新制品路径和整个wheel的SHA256。
            payload_files=len(payload),  # 非dist-info产品文件数；含Python和包内资源，单位个。
            all_payload_bytes_match_reference=True,  # 完整文件集合及每成员原字节已与固定参考摘要一致。
            metadata_matches_reference=True,  # 完整METADATA原字节一致，包含版本、依赖及描述。
            reference_wheel_sha256=descriptor['installed_wheel_sha256']))  # 参考制品身份；未用作构建输入。
    if owned(closure,'SOURCE-MANIFEST.json').read_bytes()!=raw_manifest:raise ValueError('manifest_changed_during_build')
    if backend_source.read_bytes()!=backend_raw or backend_copy.read_bytes()!=backend_raw:
        raise ValueError('build_backend_changed_during_build')
    # 构建后再次核对所有可变工作树输入；固定Git仍由同一commit提供。
    for row in modules:
        if row['source']=='overlay':exact_value(owned(overlays,row['name']).read_bytes(),row['sha256'],row['name'])
    exact_value(owned(closure,'pyproject.toml').read_bytes(),manifest['pyproject_sha256'],'runtime metadata')
    for role in ('strategy','qna'):
        for row in manifest['companions'][role]['sources'].values():
            exact_value(owned(repository,row['source']).read_bytes(),row['sha256'],row['source'])
    for name,expected in manifest['build_tools'].items():
        exact_value(owned(repository,name).read_bytes(),expected,name)
    receipt=dict(
        schema='wt.runtime-source-rebuild.v1',  # 既有源码重建收据模式；只作为构建证据。
        version=VERSION,base_commit=BASE_COMMIT,  # 固定Runtime发行与不可变Git来源。
        module_count=44,all_module_bytes_match_deployment=True,  # Runtime模块数及与固定部署参考的逐字结论。
        wheels=results,  # 本次构建拥有的三包结果；字段含义见上方逐包收据。
        build_backend='flit_core==3.12.0',backend_sha256=BACKEND_SHA256,  # 固定离线后端及原字节SHA256。
        source_manifest_sha256=digest(raw_manifest),  # 本次消费的清单原字节SHA256；用于输入复核。
        source_date_epoch=315532800,  # UTC Unix秒；1980-01-01，统一ZIP时间元数据。
        prebuilt_product_wheels_used=False,  # 产品完全从源码生成；参考wheel未参与输入。
        services_started=0,sdk_calls=0)  # 本构建不启动业务服务，不访问SDK；单位次。
    (output/'REBUILD-RESULT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(receipt,ensure_ascii=True))


if __name__=='__main__':main()
