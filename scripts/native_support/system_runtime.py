"""SRI系统候选：制品装配、ZIP搬迁及普通离线角色安装，不拥有业务进程。"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import time
import zipfile

from . import account_runtime_install as roles
from . import market_runtime as market
from .artifact import normal_path

MANIFEST = 'SYSTEM-RUNTIME.json'
RECEIPT = 'SYSTEM-INSTALLATION.json'
MAX_FILES, MAX_FILE, MAX_TOTAL = 20000, 256*1024**2, 1024**3
TOOL_FILES = ('scripts/system-runtime.py', 'scripts/native.py',
    *(f'scripts/native_support/{name}.py' for name in
      ('__init__','system_runtime','account_runtime_install','market_runtime','artifact','process_job','process_startup')))


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _sha(value):
    _require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value), 'SHA256 required')
    return value


def _pairs(pairs):
    result = {}
    for key,value in pairs:
        _require(key not in result,'duplicate JSON field')
        result[key] = value
    return result


def _load(path, expected=None):
    raw = roles._read(path,4*1024**2)
    if expected is not None:
        _require(hashlib.sha256(raw).hexdigest() == _sha(expected),'JSON identity mismatch')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs)


def _root(path):
    _require(isinstance(path,Path) and path.is_absolute(),'absolute Path root required')
    roles._unlinked(path)
    result = path.resolve(strict=True)
    _require(result.is_dir(),'directory required')
    return result


def _path(root,name):
    return roles._within(root,root/normal_path(name))


def _fresh(path):
    _require(isinstance(path,Path) and path.is_absolute() and not path.exists()
             and not path.is_symlink(),'fresh absolute directory required')
    _root(path.parent)
    path.mkdir()
    return _root(path)


def _inventory(root):
    root = _root(root)
    members,folded,stack,total,visits = {},set(),[root],0,0
    while stack:
        with os.scandir(stack.pop()) as children:
            for child in children:
                visits += 1
                _require(visits <= MAX_FILES*2,'system entry capacity exceeded')
                path = Path(child.path)
                roles._unlinked(path)
                info = path.lstat()
                name = path.relative_to(root).as_posix()
                normal_path(name)
                _require(name.casefold() not in folded,'case-colliding system path')
                folded.add(name.casefold())
                if stat.S_ISDIR(info.st_mode):
                    stack.append(path)
                    continue
                roles._regular(path)
                total += info.st_size
                _require(info.st_size <= MAX_FILE and total <= MAX_TOTAL
                         and len(members) < MAX_FILES,'system byte/file capacity exceeded')
                members[name] = path
    return members


def _files(root):
    return {name:{'sha256':roles._sha(path),'bytes':path.stat().st_size}
            for name,path in sorted(_inventory(root).items())}


def _mapping(value):
    _require(type(value) is dict and 0 < len(value) <= MAX_FILES,'nonempty file map required')
    folded = set()
    for name,digest in value.items():
        normal_path(name);_sha(digest)
        _require(name.casefold() not in folded,'case-colliding file map')
        folded.add(name.casefold())
    return value


def _copy(root,files,output):
    """只复制已核原字节；捕获前后核身份，不写来源，不覆盖目标。"""
    _mapping(files)
    for name,digest in files.items():
        source = _path(root,name)
        _require(roles._sha(source) == digest,'source file identity mismatch')
        target = output/normal_path(name)
        target.parent.mkdir(parents=True,exist_ok=True)
        with source.open('rb') as src,target.open('xb') as dst:
            shutil.copyfileobj(src,dst,1024**2)
        _require(roles._sha(target) == digest and roles._sha(source) == digest,'copied source changed')


def verify(root: Path, manifest_sha256: str) -> dict:
    """纯读取整包、角色制品、行情及SPA；外部可信摘要绑定唯一候选。"""
    root = _root(root)
    document = _load(root/MANIFEST,manifest_sha256)
    _require(set(document) == {'schema','platform','development','inputs_sha256','roles','market',
                              'static','components','tools','files','qualifications'}
             and document['schema'] in ('guanheng.system-runtime.v1','guanheng.system-runtime.v2')
             and document['platform'] == 'Windows-x64' and document['development'] is True,'system manifest schema')
    _sha(document['inputs_sha256'])
    actual = _files(root)
    actual.pop(MANIFEST)
    _require(actual == document['files'],'system file set or content mismatch')
    role = document['roles']
    roles.verify_artifacts(_path(root,role['directory']),role['manifest_sha256'])
    component = document['market']
    market.verify(_path(root,component['directory']),component['manifest_sha256'])
    static = document['static']
    _require(static is not None or document['schema'] == 'guanheng.system-runtime.v2',
             'v1 requires observer static resources')
    records = list(document['components'].values())
    if static is not None:
        records.insert(0,static)
    for record in records:
        directory = _path(root,record['directory'])
        _require({name:item['sha256'] for name,item in _files(directory).items()} == _mapping(record['files']),
                 'static/component file identity mismatch')
        for name in record.get('entries',{}).values():
            _require(name in record['files'],'component entry missing')
    if static is not None:
        _require('index.html' in static['files'],'SPA index missing')
    _require(document['tools']['entry'] == 'tools/scripts/system-runtime.py'
             and set(document['tools']['files']) == {'tools/'+name for name in TOOL_FILES},'tool closure differs')
    for name,digest in document['tools']['files'].items():
        _require(actual[name]['sha256'] == digest,'tool identity mismatch')
    return document


def create(inputs: Path, inputs_sha256: str, output: Path, archive: Path) -> dict:
    """固定输入制品组成development候选及ZIP；不构建、安装或启动产品。"""
    selected = _load(inputs,inputs_sha256)
    _require(set(selected) == {'schema','development','roles','market','static','additional_components'}
             and selected['schema'] in ('guanheng.system-runtime-inputs.v1','guanheng.system-runtime-inputs.v2')
             and selected['development'] is True,'system input schema')
    _require(type(selected['additional_components']) is list and len(selected['additional_components']) <= 16,
             'additional component capacity')
    origin = selected['roles']
    static = selected['static']
    _require(static is not None or selected['schema'] == 'guanheng.system-runtime-inputs.v2',
             'v1 requires observer static resources')
    _require(type(origin) is dict and set(origin) in ({'installation','sha256'},{'artifacts','sha256'}),
             'explicit ordinary installation or role artifacts required')
    role_source = (Path(origin['installation']).parent if 'installation' in origin else Path(origin['artifacts']))
    source_roots = [role_source,Path(selected['market']['root']),
                    *([Path(static['root'])] if static is not None else []),
                    *(Path(item['root']) for item in selected['additional_components'])]
    roles._separate_paths((output,archive),source_roots)
    _require(archive.is_absolute() and not archive.exists(),'fresh archive required')
    _root(archive.parent)
    output = _fresh(output)
    if 'installation' in origin:
        role_stage = roles.stage_artifacts(Path(origin['installation']),origin['sha256'],output/'roles')
    else:
        # 各角色可以独立发行；预建组合继续保留自己的wheel/锁，安装期无需合并依赖版本。
        role_root = _root(Path(origin['artifacts']))
        roles.verify_artifacts(role_root,origin['sha256'])
        role_dir = output/'roles';role_dir.mkdir()
        _copy(role_root,{name:item['sha256'] for name,item in _files(role_root).items()},role_dir)
        roles.verify_artifacts(role_dir,origin['sha256'])
        role_stage = dict(manifest_sha256=origin['sha256'])
    market_input = selected['market']
    market_root = _root(Path(market_input['root']))
    market.verify(market_root,market_input['sha256'])
    market_dir = output/'market';market_dir.mkdir()
    _copy(market_root,{name:item['sha256'] for name,item in _files(market_root).items()},market_dir)
    if static is not None:
        static_root = _root(Path(static['root']))
        _require({name:item['sha256'] for name,item in _files(static_root).items()} == _mapping(static['files']),
                 'SPA input file set differs')
        static_dir = output/'spa';static_dir.mkdir()
        _copy(static_root,static['files'],static_dir)
    components = {}
    for item in selected['additional_components']:
        _require(set(item) == {'name','root','files','entries'} and type(item['name']) is str
                 and re.fullmatch('[a-z][a-z0-9_]{0,63}',item['name']) and item['name'] not in components,
                 'additional component declaration')
        source = _root(Path(item['root']))
        _require({name:value['sha256'] for name,value in _files(source).items()} == _mapping(item['files']),
                 'additional component file set differs')
        _require(type(item['entries']) is dict and all(type(key) is str and value in item['files']
                 for key,value in item['entries'].items()),'additional component entries')
        directory = 'components/'+item['name']
        (output/directory).mkdir(parents=True)
        _copy(source,item['files'],output/directory)
        components[item['name']] = dict(directory=directory,files=item['files'],entries=item['entries'])
    repository = Path(__file__).resolve().parents[2]
    for relative in TOOL_FILES:
        target = output/'tools'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(repository/relative,target)
    for source,target in ((repository/'docs/runbooks/system-installation.md',output/'安装说明.md'),
                          (repository/'LICENSE',output/'licenses/REPOSITORY-LICENSE')):
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    files = _files(output)
    version = selected['schema'].rsplit('.',1)[1]
    document = dict(schema='guanheng.system-runtime.'+version,platform='Windows-x64',development=True,
        inputs_sha256=inputs_sha256,roles=dict(directory='roles',manifest_sha256=role_stage['manifest_sha256']),
        market=dict(directory='market',manifest_sha256=market_input['sha256']),
        static=(dict(directory='spa',files=static['files']) if static is not None else None),components=components,
        tools=dict(entry='tools/scripts/system-runtime.py',files={'tools/'+name:files['tools/'+name]['sha256'] for name in TOOL_FILES}),
        files=files,qualifications=['development component installation',
            'WT owns trading/data children; observer and installer own no trading runtime',
            'external Python/uv and declared HPR Python anchor required',
            'full M3, real QMT and production activation separately qualified'])
    roles._json_write(output/MANIFEST,document)
    identity = roles._sha(output/MANIFEST)
    verify(output,identity)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as bundle:
        for name,path in sorted(_inventory(output).items()):
            bundle.write(path,name)
    archive_sha = roles._sha(archive,MAX_TOTAL)
    verify(output,identity)
    return dict(manifest_sha256=identity,archive_sha256=archive_sha,files=len(files)+1)


def extract(archive: Path, archive_sha256: str, manifest_sha256: str, output: Path) -> dict:
    """以外部ZIP及manifest摘要准入到全新根；路径/展开额度在写入前核验。"""
    roles._unlinked(archive);roles._regular(archive)
    _require(roles._sha(archive,MAX_TOTAL) == _sha(archive_sha256),'archive identity mismatch')
    with archive.open('rb') as stream:
        stream.seek(max(0,archive.stat().st_size-65557));tail = stream.read(65557)
        end = tail.rfind(b'PK\x05\x06')
        _require(end >= 0 and len(tail)-end >= 22,'ZIP end record missing')
        _,disk,first,local,count,size,start,comment = struct.unpack_from('<4s4H2LH',tail,end)
        _require(disk == first == 0 and local == count and 0 < count <= MAX_FILES
                 and size <= 8*1024**2 and end+22+comment == len(tail),'ZIP central capacity')
        stream.seek(0)
        with zipfile.ZipFile(stream) as bundle:
            entries,folded,total = bundle.infolist(),set(),0
            _require(len(entries) == count,'ZIP member count differs')
            for entry in entries:
                name = normal_path(entry.filename).as_posix()
                mode = stat.S_IFMT(entry.external_attr >> 16)
                total += entry.file_size
                _require(name.casefold() not in folded and not entry.is_dir() and mode in (0,stat.S_IFREG)
                         and not entry.flag_bits & 1 and not entry.external_attr & 0x400
                         and entry.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)
                         and entry.file_size <= MAX_FILE and total <= MAX_TOTAL,'ZIP member/path/capacity')
                folded.add(name.casefold())
            output = _fresh(output)
            for entry in entries:
                target = output/normal_path(entry.filename)
                target.parent.mkdir(parents=True,exist_ok=True)
                with bundle.open(entry) as src,target.open('xb') as dst:
                    used = 0
                    while block := src.read(1024**2):
                        used += len(block)
                        _require(used <= entry.file_size,'ZIP expanded bytes differ')
                        dst.write(block)
                    _require(used == entry.file_size,'ZIP truncated member')
    _require(roles._sha(archive,MAX_TOTAL) == archive_sha256,'archive changed during extraction')
    return verify(output,manifest_sha256)


def install(root: Path, manifest_sha256: str, target: Path, python: Path, uv: Path, run,
            *, deadline: float) -> dict:
    """从候选安装到另一新目录；所有外部命令消费原总D，成功收据最后发布。"""
    _require(type(deadline) in (int,float) and math.isfinite(deadline) and deadline > time.monotonic(),
             'finite system installation deadline')
    root = _root(root)
    roles._separate_paths((target,),(root,))
    document = verify(root,manifest_sha256)
    target = _fresh(target)
    payload = target/'payload';payload.mkdir()
    _copy(root,{name:entry['sha256'] for name,entry in _files(root).items()},payload)
    verify(payload,manifest_sha256)
    installed = roles.install_artifacts(payload/document['roles']['directory'],document['roles']['manifest_sha256'],
        target/'roles',python,uv,run,deadline=deadline)
    verify(root,manifest_sha256);verify(payload,manifest_sha256)
    _require(time.monotonic() < deadline,'system installation deadline exhausted')
    result = dict(schema='guanheng.system-installation.v1',status='installed',root=str(target),
        manifest_sha256=manifest_sha256,role_installation_sha256=roles._sha(target/'roles/installation.json'),
        roles=installed['roles'],tools=installed['tools'],development=document['development'])
    digest = roles._publish_installation(target/RECEIPT,result,deadline)
    return dict(installation_sha256=digest,manifest_sha256=manifest_sha256,
                root=str(target))


def resolve(root: Path, installation_sha256: str) -> dict:
    """核已安装角色/RECORD与候选后返回公开路径；不启动或切换实例。"""
    root = _root(root)
    receipt = _load(root/RECEIPT,installation_sha256)
    _require(receipt['schema'] == 'guanheng.system-installation.v1' and receipt['status'] == 'installed'
             and receipt['root'] == str(root),'system installation binding')
    document = verify(root/'payload',receipt['manifest_sha256'])
    declared = roles.verify_artifacts(root/'payload'/document['roles']['directory'],
                                      document['roles']['manifest_sha256'])
    _require(set(receipt['roles']) == set(declared['roles']),'installed role selection differs')
    _require(roles._sha(root/'roles/installation.json') == receipt['role_installation_sha256'],
             'role installation receipt changed')
    paths = {}
    for role,record in receipt['roles'].items():
        _require(record['wheels'] == declared['roles'][role]['wheels']
                 and record['lock_sha256'] == declared['roles'][role]['lock_sha256'],
                 'installed role differs from selected artifacts')
        directory = _path(root,'roles/'+role)
        runtime = _load(directory/'runtime-receipt.json',record['receipt_sha256'])
        _require(runtime['root'] == str(directory) and runtime['role'] == role and runtime['pip_check'],
                 'installed role root mismatch')
        for name,digest in _mapping(runtime['files']).items():
            _require(roles._sha(_path(directory,name)) == digest,'installed role bytes changed')
        _require(roles._sha(Path(runtime['base_executable'])) == runtime['base_sha256'],'external Python changed')
        executable = _path(directory,runtime['executable'])
        pythonw = _path(directory,executable.with_name('pythonw.exe').relative_to(directory).as_posix())
        _require(roles._sha(pythonw) == record['pythonw_sha256'],'installed pythonw changed')
        paths[role] = dict(executable=str(executable),executable_sha256=roles._sha(executable),
            pythonw=str(pythonw),pythonw_sha256=record['pythonw_sha256'],
            argv=['-I','-B','-m',{'app':'guanheng_app','host':'guanheng_qmt_shm',
                                 'wt':'guanheng_wt_runtime'}[role]],
            receipt_sha256=record['receipt_sha256'])
        if role == 'app' and document['static'] is not None:
            paths[role]['argv'].extend(('--static-directory',str(root/'payload'/document['static']['directory'])))
    native = market.resolve(root/'payload'/document['market']['directory'],document['market']['manifest_sha256'])
    path_schema = ('guanheng.system-paths.v2' if document['schema'].endswith('.v2')
                   else 'guanheng.system-paths.v1')
    return dict(schema=path_schema,installation_sha256=installation_sha256,roles=paths,
        market=native,spa=(str(root/'payload'/document['static']['directory'])
                           if document['static'] is not None else None),
        components={key:{name:dict(path=str(root/'payload'/record['directory']/relative),
            sha256=record['files'][relative]) for name,relative in record['entries'].items()}
            for key,record in document['components'].items()},development=receipt['development'])
