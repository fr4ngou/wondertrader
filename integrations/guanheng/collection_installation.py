"""分钟角色的固定程序闭包；沿当前主线复制原模块，覆盖本次拥有的分钟接缝。"""
import hashlib
from pathlib import Path
import shutil

from guanheng_qmt_shm.private_files import create_private_directory, write_private_new
from guanheng_qmt_shm_agent.protocol import canonical, decode
from .market_generation import read_fixed
from .source_history_transport import require


OWNED = (
    'integrations/__init__.py',
    'integrations/guanheng/collection_coverage.py',
    'integrations/guanheng/collection_projection.py',
    'integrations/guanheng/collection_minute_reader.py',
    'integrations/guanheng/collection_maintenance.py',
    'integrations/guanheng/collection_roster.py',
    'integrations/guanheng/collection_installation.py',
    'integrations/guanheng/collection_deployment.py',
    'integrations/guanheng/collection_daily_connection.py',
    'integrations/guanheng/collection_source.py',
    'integrations/guanheng/collection_acceptance.py',
    'integrations/guanheng/collection_role.py',
    'scripts/minute_collection.py',
    'integrations/guanheng/quote_collection.py',
    'integrations/guanheng/quote_collection_service.py',
    'integrations/guanheng/current_day.py',
    'integrations/guanheng/datakit.py',
    'integrations/guanheng/collected_history.py',
    'integrations/guanheng/source_history_reads.py',
    'integrations/guanheng/source_history_repository.py',
    'integrations/guanheng/source_history_preparation.py',
    'integrations/guanheng/source_history_selection.py',
    'integrations/guanheng/recovered_history.py',
    'integrations/guanheng/source_market.py',
    'integrations/guanheng/source_market_service.py',
    'integrations/guanheng_market_client/exchange_calendar.py',
    'integrations/guanheng_market_client/__init__.py',
    'integrations/guanheng_market_client/source_history.py',
    'connectors/qmt_shm/host/guanheng_qmt_shm/market_source.py',
    'connectors/qmt_shm/host/guanheng_qmt_shm/private_files.py',
    'connectors/qmt_shm/host/guanheng_qmt_shm/read_retention_client.py',
)


def descriptor(path):
    path = Path(path).absolute()
    return dict(path=str(path), sha256=hashlib.sha256(read_fixed(path, maximum=268435456)).hexdigest())


def stage_program(mainline, owned, reader_build, collection_component, output):
    """新建E盘程序目录；价格、Journal、连接、凭据及运行指针均不进入程序包。

    reader_build为成功BUILT.json描述符。原collection_component提供已验Writer，
    本次新Reader及其全部依赖来自同一成功离线构建。主线数据维护模块保持当前字节。
    """
    mainline, owned, root = Path(mainline), Path(owned), Path(output)
    require(mainline.is_absolute() and owned.is_absolute() and root.is_absolute()
            and root.resolve().drive.upper() == 'E:' and not root.exists())
    built = decode(read_fixed(reader_build['path'], maximum=16777216, identity=reader_build['sha256']))
    require(built['schema'] == 'guanheng.native-reader-build.v1' and built['passed'] is True)
    reader_root = Path(reader_build['path']).parent / 'installed'
    for name, expected in built['outputs'].items():
        path = reader_root / name
        require(path.resolve().is_relative_to(reader_root.resolve()))
        read_fixed(path, maximum=268435456, identity=expected)
    require(all('app/' + name in built['outputs'] for name in
                ('GuanhengCollectionReader.dll', 'GuanhengRealtimeReader.dll')))
    create_private_directory(root)
    inputs = {}
    for directory in ('integrations', 'connectors/qmt_shm/agent/guanheng_qmt_shm_agent',
                      'connectors/qmt_shm/host/guanheng_qmt_shm'):
        for source in sorted((mainline / directory).rglob('*.py')):
            relative = source.relative_to(mainline).as_posix()
            data = read_fixed(source, maximum=16777216)
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            inputs[relative] = dict(source='mainline', sha256=hashlib.sha256(data).hexdigest())
    for relative in OWNED:
        data = read_fixed(owned / relative, maximum=16777216)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        inputs[relative] = dict(source='minute-module', sha256=hashlib.sha256(data).hexdigest())
    shutil.copytree(reader_root, root / 'native/reader')
    shutil.copytree(collection_component, root / 'native/collection')
    for required in ('GuanhengDataKitSession.dll', 'WtDataStorage.dll', 'WtDataStorageLifecycle.dll', 'WtDtHelper.dll'):
        require((root / 'native/collection/app' / required).is_file())
    write_private_new(root / 'NATIVE-BUILD.json', canonical(built))
    files = {p.relative_to(root).as_posix(): descriptor(p)['sha256'] for p in root.rglob('*') if p.is_file()}
    manifest = dict(
        schema='qmt.minute-collection-program.v1',  # 程序闭包；私有配置和历史状态分别维护。
        inputs=inputs,  # 当前主线与本次拥有的源码身份，避免回退其他模块。
        reader_build=reader_build,  # 本次成功原生构建的固定收据。
        collection_component=str(Path(collection_component).absolute()),  # 原已验Writer来源，未改变其算法或线程。
        files=files,  # 实际完整程序文件集合及SHA。
        credentials_included=False, market_data_included=False)  # 行情事实及私有角色均沿原owner。
    write_private_new(root / 'INSTALLATION.json', canonical(manifest))
    return descriptor(root / 'INSTALLATION.json')


def verify_program(installation, *, owned=None):
    """完整文件集合及字节复核；不导入程序入口或启动任何服务。"""
    path = Path(installation['path'])
    value = decode(read_fixed(path, maximum=16777216, identity=installation['sha256']))
    require(value['schema'] == 'qmt.minute-collection-program.v1')
    root = path.parent
    names = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    require(names == set(value['files']) | {'INSTALLATION.json'})
    for name, expected in value['files'].items():
        target = root / name
        require(target.resolve().is_relative_to(root.resolve()))
        read_fixed(target, maximum=268435456, identity=expected)
    if owned is not None:
        for name, record in value['inputs'].items():
            if record['source'] == 'minute-module':
                read_fixed(Path(owned) / name, maximum=16777216, identity=record['sha256'])
    return value
