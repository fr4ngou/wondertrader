"""完整分钟角色配置准备；原实例保持，正式启停与Source采用交运行owner。"""
from copy import deepcopy
import ast
import base64
from pathlib import Path
from uuid import uuid4

from guanheng_qmt_shm.private_files import create_private_directory, write_private_new
from guanheng_qmt_shm_agent.protocol import canonical, decode
from .collection_installation import descriptor, verify_program
from .market_generation import read_fixed
from .source_history_transport import require


def load(value, maximum=16777216):
    require(type(value) is dict and set(value) == {'path', 'sha256'})
    return decode(read_fixed(value['path'], maximum=maximum, identity=value['sha256']))


def prepare_configuration(request):
    """固定原/新CAS并新建全部私有配置；只读旧配置，继续使用同一Writer数据根。

    request的program、roster、data_runtime、hpr_pair_manifest、source_cas均为固定描述符；
    hpr_pair_manifest指向已由原产品工厂生成并验证的最终路径。metadata沿唯一资料owner。
    返回供Root启动/停止/回退的完整清单，不启动进程、不更改任何CURRENT或QMT文件。
    """
    require(type(request) is dict and set(request) == {'schema', 'output', 'program', 'roster',
        'data_runtime', 'hpr_pair_manifest', 'source_cas', 'metadata', 'priority_symbols', 'daily_base', 'history_credential'}
        and request['schema'] == 'qmt.minute-collection-configuration-request.v1')
    root = Path(request['output'])
    require(root.is_absolute() and root.resolve().drive.upper() == 'E:' and not root.exists())
    program_manifest = verify_program(request['program'])
    program = Path(request['program']['path']).parent
    roster = load(request['roster'])
    require(roster['schema'] == 'qmt.collection-roster-candidate.v1')
    original = load(request['data_runtime'])
    require(set(original['components']) == {'host', 'history', 'collection'})
    source_cas = load(request['source_cas'])
    for key in ('source_before', 'source_after'):
        read_fixed(source_cas[key]['path'], maximum=2097152, identity=source_cas[key]['sha256'])
    pair_manifest = load(request['hpr_pair_manifest'])
    require(pair_manifest['schema_version'] == 'qmt.history-preparation-product-pair.v1')
    pair = Path(request['hpr_pair_manifest']['path']).parent
    components = original['components']
    def component(name):
        value = components[name]
        return load(dict(path=value['descriptor'], sha256=value['sha256']))
    old_collection, old_history, old_hpr = component('collection'), component('history'), component('host')
    worker_descriptor = dict(path=old_collection['configuration'], sha256=old_collection['configuration_sha256'])
    worker = load(worker_descriptor)
    native_descriptor = dict(path=worker['native']['configuration'], sha256=worker['native']['configuration_sha256'])
    native = load(native_descriptor)
    old_service_descriptor = dict(path=old_history['configuration'], sha256=old_history['configuration_sha256'])
    old_service = load(old_service_descriptor)
    old_source = load(old_service['source_configuration'])
    require(old_source['mode'] == 'source-collected')
    create_private_directory(root)
    def save(name, value):
        path = root / name
        write_private_new(path, canonical(value))
        return descriptor(path)
    files = {}
    for name in ('contracts', 'commodities'):
        files[name] = save(name + '.json', load(roster['files'][name]))
    session = Path(native['basefiles']['session'])
    files['sessions'] = save('sessions.json', decode(read_fixed(session, maximum=16777216)))
    native['basefiles'].update(session=files['sessions']['path'], commodity=files['commodities']['path'],
                               contract=files['contracts']['path'])
    if native.get('allday') is not True:
        monitor = Path(native['statemonitor'])
        files['statemonitor'] = save('statemonitor.json', decode(read_fixed(monitor, maximum=1048576)))
        native['statemonitor'] = files['statemonitor']['path']
    files['native'] = save('native.json', native)
    files['connection'] = save('connection.json', load(roster['files']['connection']))
    collection_symbols = []
    for symbol in load(files['connection'])['symbols']:
        code, suffix = symbol.split('.')
        collection_symbols.append({'SH': 'SSE', 'SZ': 'SZSE'}[suffix] + '.' + code)
    source = deepcopy(old_source)
    require(Path(source['collection']['storage_root']).resolve() == Path(native['writer']['path']).resolve())
    source['collection']['symbols'] = sorted(collection_symbols)
    source['minute_native'] = dict(
        library=descriptor(program / 'native/reader/app/GuanhengCollectionReader.dll'),
        reader=descriptor(program / 'native/reader/app/GuanhengRealtimeReader.dll'),
        storage_root=native['writer']['path'], basefiles=dict(session=files['sessions'],
            commodity=files['commodities'], contract=files['contracts']))
    deployment = decode(read_fixed(pair / 'deployment.json', maximum=2097152))
    host = deployment['host']
    helper = program / 'native/collection/app/WtDtHelper.dll'
    producer = dict(mode='source-preparing', base=source, preparation=dict(
        enabled=True, retained_reads=True, closed_day_recovery=True, partitioned_receipts=True,
        workspace=str(root.parent / 'recovery'),
        host=dict(base_url='http://' + host['listen_host'] + ':' + str(host['listen_port']),
                  key_id=host['http_key_id'], secret_env=host['http_secret_env'], timeout=10),
        helper=dict(library=str(helper), sha256=descriptor(helper)['sha256']),
        source_profile=dict(dataset_version='qmt-minute-closed-day-v1', source_license='local-authorized-qmt-terminal',
            input_kind='qmt_export', timezone='Asia/Shanghai', minute_boundary='unknown', adjustment='none',
            factor_version='', value_semantics='source', price_unit='unknown', volume_unit='unknown', amount_unit='unknown'),
        timeout_seconds=30, max_windows=1000000, max_window_minutes=7200, max_pages=128,
        max_rows=2000, max_bytes=8388608, overlay_cache_bars=20000, max_import_attempts=16,
        # 首次发布加15次有界只读后继，覆盖同一窗口至多16份冻结导入；下载仍至多一次。
        follow_up=dict(enabled=True,max_attempts=15,interval_seconds=60,total_seconds=86400,
            rpc_timeout_seconds=10,journal_records=host['max_records'],journal_bytes=host['max_journal_bytes'])))
    files['producer'] = save('producer.json', producer)
    recovered = dict(mode='source-recovered', base=source, producer=files['producer'])
    files['source'] = save('source.json', recovered)
    maintenance = dict(schema='qmt.collection-maintenance.v1', producer=files['producer'], metadata=request['metadata'],
        lookback_trading_days=2, batch_size=64, interval_seconds=1, retry_seconds=60,
        priority_symbols=request['priority_symbols'])
    files['maintenance'] = save('maintenance.json', maintenance)
    worker['connection'].update(files['connection'])
    worker['native'].update(configuration=files['native']['path'], configuration_sha256=files['native']['sha256'],
        directory=str(program / 'native/collection/app'),
        session_library_sha256=descriptor(program / 'native/collection/app/GuanhengDataKitSession.dll')['sha256'])
    worker['maintenance'] = files['maintenance']
    files['worker'] = save('worker.json', worker)
    create_private_directory(root / 'collection-controls')
    entry = descriptor(program / 'integrations/guanheng/quote_collection_service.py')
    collection = dict(old_collection, configuration=files['worker']['path'], configuration_sha256=files['worker']['sha256'],
        entry=entry['path'], entry_sha256=entry['sha256'], control_root=str(root / 'collection-controls'),
        startup_seconds=90, stop_seconds=60)
    files['collection_process'] = save('collection-process.json', collection)
    service = dict(old_service, source_configuration=files['source'])
    files['service'] = save('history-service.json', service)
    # 凭据只在新私有环境文件内，公开plan仅保存固定描述符；完整Source字面量通过AST读取。
    tree = ast.parse(read_fixed(source_cas['source_after']['path'], maximum=2097152,
        identity=source_cas['source_after']['sha256']).decode('ascii'))
    settings = ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == '_settings' for target in node.targets)))
    secret = settings['quotes']['secret']
    encoding = worker['connection'].get('secret_encoding', 'utf8')
    require(encoding in ('utf8', 'base64') and type(secret) is bytes)
    environment = {
        worker['connection']['secret_env']: base64.b64encode(secret).decode('ascii') if encoding == 'base64' else secret.decode('utf8'),
        producer['preparation']['host']['secret_env']: deployment['credentials']['http_keys'][host['http_key_id']],
        service['token_env']: load(request['history_credential'])['token']}
    require(len(environment) == 3)
    files['environment'] = save('environment.json', environment)
    del environment, secret, settings
    create_private_directory(root / 'history-controls')
    entry = descriptor(program / 'integrations/guanheng/source_market_service.py')
    history = dict(old_history, configuration=files['service']['path'], configuration_sha256=files['service']['sha256'],
        entry=entry['path'], entry_sha256=entry['sha256'], control_root=str(root / 'history-controls'))
    files['history_process'] = save('history-process.json', history)
    create_private_directory(root / 'hpr-controls')
    hpr = dict(old_hpr, pair_directory=str(pair), pair_manifest_sha256=request['hpr_pair_manifest']['sha256'],
               control_root=str(root / 'hpr-controls'))
    files['host_process'] = save('hpr-process.json', hpr)
    runtime = deepcopy(original)
    runtime.update(instance_id=str(uuid4()), startup_seconds=180, stop_seconds=90)
    for key in ('collection', 'history', 'host'):
        selected = files[key + '_process']
        runtime['components'][key].update(descriptor=selected['path'], sha256=selected['sha256'])
    files['runtime'] = save('data-runtime.json', runtime)
    # 统一日线仅读取base配置采用此叶；生产者、已发布版本及UI保持由原owner维护。
    daily = load(request['daily_base'])
    def replace_leaf(value):
        if value.get('mode') == 'source-collected':
            require(value['collection']['storage_root'] == source['collection']['storage_root'])
            selected = deepcopy(value)
            selected['collection'] = source['collection']
            selected['minute_native'] = source['minute_native']
            return dict(mode='source-recovered', base=selected, producer=files['producer'])
        require('base' in value)
        value = deepcopy(value); value['base'] = replace_leaf(value['base'])
        return value
    files['daily_base_candidate'] = save('daily-base-candidate.json', replace_leaf(daily))
    plan = dict(
        schema='qmt.minute-collection-deployment.v1',  # 完整候选及回退固定引用，不代表已切换。
        request=request, program=request['program'],  # 本次程序闭包与输入请求身份。
        source=source_cas, hpr_pair_manifest=request['hpr_pair_manifest'],  # 完整Source与原产品配对的独立CAS。
        originals=dict(runtime=request['data_runtime'], worker=worker_descriptor, native=native_descriptor,
                       history_service=old_service_descriptor, daily_base=request['daily_base']),  # 原件仅读保留。
        files=dict(files), quote_count=len(collection_symbols),  # 同一QST/基础资料/Reader声明集合。
        source_current_unchanged=True, runtime_started=False, trading_changed=False)  # Root后续正式采用。
    files['plan'] = save('DEPLOYMENT.json', plan)
    return files['plan']
