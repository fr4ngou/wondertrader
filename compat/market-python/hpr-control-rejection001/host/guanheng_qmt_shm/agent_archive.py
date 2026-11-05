"""Agent白名单源ZIP发行/安装；不执行源码、不启动终端、不改变Python环境。"""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
import zipfile
import guanheng_qmt_shm_agent
from guanheng_qmt_shm_agent.protocol import canonical, decode
from .private_files import create_private_directory, write_private_new

PACKAGE='guanheng_qmt_shm_agent'
MAX_FILES=64
MAX_FILE_BYTES=2097152
MAX_TOTAL_BYTES=16777216


def export_agent(output):
    root=Path(guanheng_qmt_shm_agent.__file__).resolve().parent
    entries={}
    total=0
    for path in root.iterdir():
        if path.suffix!='.py' or not path.is_file():
            continue
        if path.is_symlink() or len(entries)>=MAX_FILES or path.stat().st_size>MAX_FILE_BYTES:
            raise ValueError('Agent source whitelist exceeds budget')
        raw=path.read_bytes();total+=len(raw)
        if total>MAX_TOTAL_BYTES:
            raise ValueError('Agent total source budget exceeded')
        entries[PACKAGE+'/'+path.name]=raw
    if PACKAGE+'/__init__.py' not in entries:
        raise ValueError('Agent source origin unavailable')
    manifest={'schema_version':'qmt.shm-agent-source.v1','private':True,
        'files':{name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(entries.items())}}
    output=Path(output)
    if not output.is_absolute() or output.drive.upper()!='E:':
        raise ValueError('explicit managed E source ZIP output required')
    with output.open('xb') as stream:
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,raw in sorted(entries.items()):
                info=zipfile.ZipInfo(name,date_time=(2026,10,22,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,raw)
            archive.writestr('source-manifest.json',canonical(manifest))
    return {'exported':True,'private':True,'files':len(entries),'qualified_in_qmt':False,
        'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}


def install_agent(archive_path, *, output):
    archive_path=Path(archive_path)
    if archive_path.stat().st_size>MAX_TOTAL_BYTES:
        raise ValueError('Agent archive byte budget exceeded')
    entries={};total=0
    with zipfile.ZipFile(archive_path) as archive:
        infos=archive.infolist()
        if not 2<=len(infos)<=MAX_FILES+1 or len({x.filename.casefold() for x in infos})!=len(infos):
            raise ValueError('Agent archive file count/identity differs')
        for info in infos:
            parts=info.filename.split('/')
            if info.filename=='source-manifest.json':
                pass
            elif (len(parts)!=2 or parts[0]!=PACKAGE or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.py',parts[1])
                    or info.is_dir()):
                raise ValueError('Agent archive contains non-whitelisted path')
            if info.file_size>MAX_FILE_BYTES:
                raise ValueError('Agent archive file budget exceeded')
            total+=info.file_size
            if total>MAX_TOTAL_BYTES:
                raise ValueError('Agent archive total expansion budget exceeded')
            with archive.open(info) as stream:
                raw=stream.read(MAX_FILE_BYTES+1)
            if len(raw)!=info.file_size or len(raw)>MAX_FILE_BYTES:
                raise ValueError('Agent archive expansion differs')
            entries[info.filename]=raw
    manifest=decode(entries.pop('source-manifest.json',b''))
    if (not isinstance(manifest,dict) or set(manifest)!={'schema_version','private','files'}
            or manifest['schema_version']!='qmt.shm-agent-source.v1' or manifest['private'] is not True
            or manifest['files']!={name:hashlib.sha256(raw).hexdigest() for name,raw in entries.items()}
            or PACKAGE+'/__init__.py' not in entries):
        raise ValueError('Agent source manifest differs')
    target=create_private_directory(output)
    package=create_private_directory(target/PACKAGE)
    for name,raw in entries.items():
        write_private_new(package/name.split('/')[1],raw)
    write_private_new(target/'installation.json',canonical(manifest))
    return {'installed':True,'private':True,'files':len(entries),'qualified_in_qmt':False,'order_ready':False}
