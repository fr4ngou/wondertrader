"""冻结行情组件的有界装配；只产生候选和公开路径，不启动任何运行组件。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import zipfile

from .artifact import normal_path

SCHEMA = 'guanheng.market-runtime.v1'
MANIFEST = 'MARKET-RUNTIME.json'
COMPONENTS = {'history', 'sdk', 'hpr', 'collection', 'minute_reader', 'parser_v6'}
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_MANIFEST = 2 * 1024 * 1024
VERSIONS = dict(history='RS14-package005', sdk='0.15.0', hpr='HPR-e',
                collection='collection005-native', minute_reader='NMR001', parser_v6='v6-001')
ORIGINS = {
    'history': '48e907ccfca84d6eb65eb07cdaacb1ee876dc19fdb80a4380228735826ddaf73',
    'sdk': '34579862be4dc777bf2f10cceff64d0df2a242a7ee78f368c06e9a4c744287ab',
    'hpr': '5c3e3ffb082f09c2965c70336664f81b1816b951c8c676d58d397c35d4623ad3',
    'collection': '11cfb6725e327285b26be85c84ab201ae7c39dbd0e00550605738256e056e2a9',
    'minute_reader': 'aee1e7c6615172e82a62dd8ef56d96fc05da03d7a07fa9f35735cce467b1f5fe',
    'parser_v6': 'b0a105513e0ea2f6aaec9d3c6d68c8548ec4d6eaa4274a0072cb482b2cf250ea',
}
# 已登记后继按原清单摘要明确选择；旧候选沿同一映射继续核验。
# 新源清单只有登记到这里后才能装配，版本文字不能代替原字节身份。
FROZEN_COMPONENTS = {key: {ORIGINS[key]: VERSIONS[key]} for key in COMPONENTS}
FROZEN_COMPONENTS['history']['225791a042473d5aa669bf8f56aa09a3ed2d3e06cb3d8864db4270e102167903'] = 'CNH-package002'
FROZEN_COMPONENTS['history']['199c3eb662d135b6866a5bc21b19d98393fdeb8cf720194e98597042af24542e'] = 'CNH-market-scope001'
FROZEN_COMPONENTS['hpr']['819ae7497b765f4005afc230f3d6bc46d5c58c70d47fcb615173d4c62af45ba1'] = 'HPR-market-scope001'
FROZEN_COMPONENTS['parser_v6']['348508d29f0928a49cbfba38b9f1439685ae7b4f5c0aa1eeab5f984d5031f93a'] = 'v6-market-scope001'
QUALIFICATIONS = ['component assembly only; App owns processes', 'HPR retains declared external Python runtime anchor',
                  'data/credentials/QMT strategy/runtime state excluded', 'full M3 and real trading unqualified']
CONSUMERS = {
    'parser_v6': dict(module='ParserQMTHostV6', entry='parser_v6', selection='explicit'),
    'minute_reader': dict(module='GuanhengRealtimeReader', entry='native_minute_reader', selection='minute_native object'),
    'history': dict(owner='App SourceMarketProcess', entry='history_service', schema='guanheng.source-market-service.v1'),
    'hpr': dict(owner='App HistoryPreparationProcess', entry='hpr_pythonw', schema='qmt.history-preparation-process.v1'),
    'collection': dict(owner='App QuoteCollectionProcess', entry='collection_service', schema='qmt.quote-collector.v1'),
    'sdk': dict(distribution='guanheng-market-client', version='0.15.0', entry='sdk_wheel', installation='ordinary pip wheel'),
}
CRITICAL = {
    'history': ['integrations/guanheng/source_market_service.py', 'app/GuanhengNativeBarFile.dll', 'app/WtDtHelper.dll'],
    'hpr': ['host/Scripts/python.exe', 'host/Scripts/pythonw.exe',
            'host/Lib/site-packages/guanheng_qmt_shm_agent/__init__.py',
            'host/Lib/site-packages/guanheng_qmt_shm/history_preparation_cli.py',
            'app_adapter/guanheng_app/history_preparation_process.py'],
    'collection': ['app/GuanhengDataKitSession.dll', 'app/WtDataStorage.dll', 'app/WtDataStorageLifecycle.dll', 'app/WtDtHelper.dll'],
    'minute_reader': ['GuanhengRealtimeReader.dll'],
    'parser_v6': ['ParserQMTHostV6.dll', 'GuanhengQmtHostParserProbe.exe', 'CONFIG-EXAMPLE.json'],
    'sdk': ['guanheng_market_client-0.15.0-py3-none-any.whl'],
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf8')


def _sha(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('SHA256 required')
    return value


def _json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate JSON field')
            value[key] = item
        return value
    if len(raw) > MAX_MANIFEST:
        raise ValueError('manifest byte budget exceeded')
    return json.loads(raw, object_pairs_hook=unique)


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError('manifest fields invalid')


def _plain(path, directory=False):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('linked/reparse installation input')
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('installation directory required')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('single-link regular input required')
    return info


def _absolute(path):
    value = Path(path)
    if '..' in value.parts:
        raise ValueError('parent traversal in installation path')
    return Path(os.path.abspath(value))


def _root(path):
    path = _absolute(path)
    # 先检查原路径的每个父节点，resolve不会丢掉junction身份。
    for part in reversed((path, *path.parents)):
        _plain(part, True)
    return path.resolve(strict=True)


def read(path, maximum=MAX_FILE):
    path = Path(path)
    _root(path.parent)
    before = _plain(path)
    if before.st_size > maximum:
        raise ValueError('file byte budget exceeded')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(maximum + 1)
    after = _plain(path)
    if len(raw) > maximum or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino) or (
            opened.st_dev, opened.st_ino) != (after.st_dev, after.st_ino):
        raise ValueError('growing/replaced installation input')
    return raw


class Budget:
    """一次装配共用原字节/枚举额度；每个文件在打开前受剩余额度限制。"""
    def __init__(self):
        self.remaining = MAX_TOTAL
        self.entries = 0

    def charge(self, raw):
        if len(raw) > self.remaining:
            raise ValueError('installation total byte budget exceeded')
        self.remaining -= len(raw)
        return raw

    def read(self, path, maximum=MAX_FILE):
        return self.charge(read(path, min(maximum, self.remaining)))


def inventory(root, budget=None):
    root = _root(root)
    budget = budget or Budget()
    result, folded, stack = {}, set(), [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as children:
            for entry in children:
                budget.entries += 1
                if budget.entries > MAX_ENTRIES:
                    raise ValueError('installation entry budget exceeded')
                path = Path(entry.path)
                info = _plain(path, entry.is_dir(follow_symlinks=False))
                name = path.relative_to(root).as_posix()
                normal_path(name)
                if name.casefold() in folded:
                    raise ValueError('case-colliding installation member')
                folded.add(name.casefold())
                if stat.S_ISDIR(info.st_mode):
                    stack.append(path)
                else:
                    result[name] = path
    return result


def snapshot(root, preloaded=None, budget=None, expected=None):
    budget = budget or Budget()
    members = inventory(root, budget)
    if expected is not None and set(members) != set(expected):
        raise ValueError('component file set differs')
    result = {}
    for name, path in members.items():
        # preloaded来自本次同一Budget的首读，直接消费该快照，不再次读取或计费。
        maximum = MAX_MANIFEST if Path(name).name in {MANIFEST,'INSTALLATION.json','MANIFEST.json','ORIGIN-INSTALLED.json'} else MAX_FILE
        raw = preloaded[name] if preloaded and name in preloaded else budget.read(path,maximum)
        if expected is not None and digest(raw) != expected[name]:
            raise ValueError('component payload SHA differs')
        result[name] = raw
    return result


def _file_map(value):
    if type(value) is not dict or not value or len(value) > MAX_ENTRIES:
        raise ValueError('component file set required')
    folded = set()
    for name, sha in value.items():
        normal_path(name)
        _sha(sha)
        if name.casefold() in folded:
            raise ValueError('case-colliding component manifest')
        folded.add(name.casefold())
    return value


def _check_component(key, record, payload):
    _fields(record, 'directory version manifest manifest_sha256 scope')
    if record['directory'] != 'components/' + key or record['version'] not in FROZEN_COMPONENTS[key].values():
        raise ValueError('component identity invalid')
    prefix = record['directory'] + '/'
    files = {name[len(prefix):]: raw for name, raw in payload.items() if name.startswith(prefix)}
    normal_path(record['manifest'])
    raw = files[record['manifest']]
    if digest(raw) != _sha(record['manifest_sha256']):
        raise ValueError('component manifest SHA differs')
    document = _json(raw)
    scope = {'sdk':'standalone-wheel','collection':'native-app-only'}.get(key,'complete-original-installation')
    if record['scope'] != scope:
        raise ValueError('component scope differs')
    if key in {'sdk','collection'}:
        _fields(document, 'schema scope origin_sha256 files')
        if document['schema'] != 'guanheng.market-component-subset.v1' or document['scope'] != scope or document['origin_sha256'] != ORIGINS[key]:
            raise ValueError('component subset origin differs')
    elif FROZEN_COMPONENTS[key].get(record['manifest_sha256']) != record['version']:
        raise ValueError('frozen component origin differs')
    expected = _file_map(document if key == 'parser_v6' else document['files'])
    if set(files) != set(expected) | {record['manifest']}:
        raise ValueError('component file set differs')
    for name, sha in expected.items():
        if digest(files[name]) != sha:
            raise ValueError('component payload SHA differs')
    if any(name not in expected for name in CRITICAL[key]):
        raise ValueError('component entry absent')
    if key == 'sdk' and (set(expected) != set(CRITICAL[key]) or expected[CRITICAL[key][0]] != ORIGINS[key]):
        raise ValueError('frozen SDK wheel differs')
    if key == 'collection':
        if digest(files['ORIGIN-INSTALLED.json']) != ORIGINS[key]:
            raise ValueError('collection source receipt differs')
        original = _file_map(_json(files['ORIGIN-INSTALLED.json'])['files'])
        subset = {name:sha for name,sha in original.items()if name.startswith(('app/','licenses/'))}
        if set(expected) != set(subset)|{'ORIGIN-INSTALLED.json'} or any(expected[name] != sha for name,sha in subset.items()):
            raise ValueError('collection native subset differs')
    return files


def _entries(payload):
    names = {
        'history_service': 'history/integrations/guanheng/source_market_service.py',
        'history_reader': 'history/app/GuanhengNativeBarFile.dll',
        'history_helper': 'history/app/WtDtHelper.dll',
        'collection_service': 'history/integrations/guanheng/quote_collection_service.py',
        'collection_session': 'collection/app/GuanhengDataKitSession.dll',
        'collection_storage': 'collection/app/WtDataStorage.dll',
        'collection_lifecycle': 'collection/app/WtDataStorageLifecycle.dll',
        'collection_helper': 'collection/app/WtDtHelper.dll',
        'native_minute_reader': 'minute_reader/GuanhengRealtimeReader.dll',
        'parser_v6': 'parser_v6/ParserQMTHostV6.dll',
        'parser_example': 'parser_v6/CONFIG-EXAMPLE.json',
        'hpr_python': 'hpr/host/Scripts/python.exe',
        'hpr_pythonw': 'hpr/host/Scripts/pythonw.exe',
        'hpr_cli': 'hpr/host/Lib/site-packages/guanheng_qmt_shm/history_preparation_cli.py',
        'hpr_agent': 'hpr/host/Lib/site-packages/guanheng_qmt_shm_agent/__init__.py',
        'hpr_app_adapter': 'hpr/app_adapter/guanheng_app/history_preparation_process.py',
        'sdk_wheel': 'sdk/guanheng_market_client-0.15.0-py3-none-any.whl',
    }
    return {key: dict(path='components/' + name, sha256=digest(payload['components/' + name]))
            for key, name in names.items()}


def validate(payload, expected_sha):
    raw = payload[MANIFEST]
    if digest(raw) != _sha(expected_sha):
        raise ValueError('runtime manifest SHA differs')
    document = _json(raw)
    _fields(document, 'schema platform inputs_sha256 components entries consumers files defaults qualifications')
    if document['schema'] != SCHEMA or document['platform'] != 'Windows-x64' or set(document['components']) != COMPONENTS:
        raise ValueError('runtime schema/platform/components invalid')
    _sha(document['inputs_sha256'])
    expected = document['files']
    if len(payload) > MAX_ENTRIES or sum(map(len, payload.values())) > MAX_TOTAL:
        raise ValueError('runtime total payload budget exceeded')
    if type(expected) is not dict or not expected or len(expected) > MAX_ENTRIES or set(payload) != set(expected) | {MANIFEST}:
        raise ValueError('runtime file set differs')
    folded = set()
    for name, item in expected.items():
        normal_path(name)
        _fields(item, 'sha256 bytes')
        if name.casefold() in folded or type(item['bytes']) is not int or not 0 <= item['bytes'] <= MAX_FILE:
            raise ValueError('runtime member invalid')
        folded.add(name.casefold())
        if len(payload[name]) != item['bytes'] or digest(payload[name]) != _sha(item['sha256']):
            raise ValueError('runtime member content differs')
    for key, record in document['components'].items():
        _check_component(key, record, payload)
    if (document['entries'] != _entries(payload) or document['defaults'] != dict(enabled=False, minute_reader='StrategyReader HTTP')
            or document['qualifications'] != QUALIFICATIONS or document['consumers'] != CONSUMERS):
        raise ValueError('runtime consumer/default fields invalid')
    return document


def verify(root, expected_sha):
    return validate(snapshot(root), expected_sha)


def _new(path):
    path = _absolute(path)
    _root(path.parent)
    if path.exists() or path.is_symlink():
        raise ValueError('fresh output directory required')
    path.mkdir()
    return path


def _write(payload, output):
    output = _new(output)
    for name, raw in payload.items():
        target = output / normal_path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)


def create(inputs_path, inputs_sha, output, archive):
    raw = read(inputs_path, MAX_MANIFEST)
    if digest(raw) != _sha(inputs_sha):
        raise ValueError('input lock SHA differs')
    inputs = _json(raw)
    _fields(inputs, 'schema components')
    if inputs['schema'] != 'guanheng.market-runtime-inputs.v1' or set(inputs['components']) != COMPONENTS:
        raise ValueError('six explicit component inputs required')
    payload, records, budget = {}, {}, Budget()
    destinations = (_absolute(output), _absolute(archive))
    for key, source in inputs['components'].items():
        _fields(source, 'root manifest sha256')
        if source['sha256'] not in FROZEN_COMPONENTS[key]:
            raise ValueError('candidate requires frozen component origin: ' + key)
        root = _root(source['root'])
        if any(target.is_relative_to(root) for target in destinations):
            raise ValueError('output cannot modify a source component')
        origin = budget.read(Path(source['manifest']), MAX_FILE if key == 'sdk' else MAX_MANIFEST)
        if digest(origin) != _sha(source['sha256']):
            raise ValueError('source manifest SHA differs: ' + key)
        manifest_name, scope = 'INSTALLATION.json', 'complete-original-installation'
        if key == 'sdk':
            name = CRITICAL[key][0]
            if Path(source['manifest']).name != name or _root(Path(source['manifest']).parent) != root:
                raise ValueError('SDK wheel location differs')
            files = {name: origin}
            scope = 'standalone-wheel'
        elif key == 'collection':
            expected = _file_map(_json(origin)['files'])
            selected = {name: sha for name, sha in expected.items() if name.startswith(('app/', 'licenses/'))}
            if len(selected) != 13:
                raise ValueError('collection native subset differs')
            if set(inventory(root/'app',budget)) != {name[4:] for name in selected if name.startswith('app/')}:
                raise ValueError('collection app file set differs')
            files = {}
            for name, sha in selected.items():
                value = budget.read(root/name)
                if digest(value) != sha:
                    raise ValueError('collection native identity differs')
                files[name] = value
            files['ORIGIN-INSTALLED.json'] = origin
            scope = 'native-app-only'
        else:
            manifest_name = 'MANIFEST.json' if key == 'parser_v6' else 'INSTALLATION.json'
            if Path(source['manifest']).name != manifest_name or _root(Path(source['manifest']).parent) != root:
                raise ValueError('source manifest location differs')
            expected = _file_map(_json(origin) if key == 'parser_v6' else _json(origin)['files'])
            if manifest_name in expected:
                raise ValueError('component manifest cannot include itself')
            files = snapshot(root, {manifest_name:origin},budget,dict(expected,**{manifest_name:source['sha256']}))
        if key in {'sdk', 'collection'}:
            files[manifest_name] = budget.charge(canonical(dict(schema='guanheng.market-component-subset.v1', scope=scope,
                origin_sha256=digest(origin), files={name: digest(value) for name, value in files.items()})))
        prefix = 'components/' + key + '/'
        payload.update({prefix + name: value for name, value in files.items()})
        records[key] = dict(directory='components/' + key, version=FROZEN_COMPONENTS[key][source['sha256']], manifest=manifest_name,
                            manifest_sha256=digest(files[manifest_name]), scope=scope)
        _check_component(key, records[key], payload)
        if sum(map(len, payload.values())) > MAX_TOTAL or len(payload) > MAX_ENTRIES:
            raise ValueError('runtime payload budget exceeded')
    script = Path(__file__).resolve()
    for source, name in [(script, 'tools/native_support/market_runtime.py'),
                         (script.with_name('artifact.py'), 'tools/native_support/artifact.py'),
                         (script.parents[1]/'package-market-runtime.py', 'tools/package-market-runtime.py')]:
        payload[name] = budget.read(source)
    payload['tools/native_support/__init__.py'] = b''
    payload['examples/SELECTION.json'] = budget.charge(canonical(dict(example=True, enabled=False,
        parser_module='ParserQMTHostV6', reader_module='GuanhengRealtimeReader', minute_native={'path':'E:/example/native-data'},
        external_required=['App Managed owner', 'private pair/config/credentials', 'base data and data roots', 'compatible Python runtime'],
        original_configuration='Each component keeps its existing configuration and lifecycle.')))
    document = dict(schema=SCHEMA, platform='Windows-x64', inputs_sha256=digest(raw), components=records,
        entries=_entries(payload), consumers=CONSUMERS, defaults=dict(enabled=False, minute_reader='StrategyReader HTTP'),
        qualifications=QUALIFICATIONS,
        files={name:dict(sha256=digest(value),bytes=len(value)) for name,value in payload.items()})
    payload[MANIFEST] = budget.charge(canonical(document))
    identity = digest(payload[MANIFEST])
    validate(payload, identity)
    archive = _absolute(archive)
    _root(archive.parent)
    if archive.exists():
        raise ValueError('fresh archive required')
    _write(payload, output)
    verify(output, identity)
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for name, value in sorted(payload.items()):
            bundle.writestr(name, value)
    archive_sha = digest(read(archive,MAX_TOTAL))
    check_archive(archive, archive_sha, identity)
    return dict(manifest_sha256=identity, archive_sha256=archive_sha, files=len(payload))


def check_archive(archive, expected_sha, manifest_sha):
    raw = read(archive, MAX_TOTAL)
    if digest(raw) != _sha(expected_sha):
        raise ValueError('archive SHA differs')
    import io
    # ZipFile会先加载整个central directory；先逐记录核其上界，避免构造期越过4096项预算。
    end = raw.rfind(b'PK\x05\x06', max(0, len(raw)-65557))
    if end < 0 or len(raw)-end < 22:
        raise ValueError('ZIP end record absent')
    _, disk, first_disk, disk_count, count, size, start, comment = struct.unpack_from('<4s4H2LH',raw,end)
    if (disk or first_disk or disk_count != count or not 0 < count <= MAX_ENTRIES or size > 8*1024*1024
            or start+size != end or end+22+comment != len(raw)):
        raise ValueError('ZIP central directory budget/shape invalid')
    cursor, actual = start, 0
    while cursor < end:
        actual += 1
        if actual > MAX_ENTRIES or cursor+46 > end or raw[cursor:cursor+4] != b'PK\x01\x02':
            raise ValueError('ZIP central directory entry invalid')
        name_size, extra_size, comment_size = struct.unpack_from('<3H',raw,cursor+28)
        cursor += 46+name_size+extra_size+comment_size
    if cursor != end or actual != count:
        raise ValueError('ZIP central directory count differs')
    payload, folded, total = {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        for entry in bundle.infolist():
            name = normal_path(entry.filename).as_posix()
            mode = entry.external_attr >> 16
            if (name.casefold() in folded or len(payload) >= MAX_ENTRIES or entry.is_dir()
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or entry.external_attr & 0x400
                    or entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or entry.file_size > MAX_FILE):
                raise ValueError('archive member invalid')
            folded.add(name.casefold())
            total += entry.file_size
            if total > MAX_TOTAL:
                raise ValueError('archive total byte budget exceeded')
            with bundle.open(entry) as stream:
                data = stream.read(entry.file_size + 1)
            if len(data) != entry.file_size:
                raise ValueError('archive member byte size differs')
            payload[name] = data
    validate(payload, manifest_sha)
    return payload


def extract(archive, archive_sha, manifest_sha, output):
    payload = check_archive(archive, archive_sha, manifest_sha)
    _write(payload, output)
    return verify(output, manifest_sha)


def resolve(root, manifest_sha):
    root = _root(root)
    document = verify(root, manifest_sha)
    return dict(schema='guanheng.market-runtime-paths.v1', manifest_sha256=manifest_sha,
        enabled=False, entries={name:dict(path=str(root/value['path']), sha256=value['sha256'])
                               for name,value in document['entries'].items()}, components=document['components'],
        consumers=document['consumers'])
