"""数据侧准备统一行情快照；复用已导入原生根和真实证券原件，不访问外部来源。"""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path

from ..guanheng_market_client import strict_json
from ..guanheng_market_client.market_snapshot import snapshot_identity,validate_market_snapshot


def _catalog(config):
    """沿既有包装寻找唯一原生目录；不修改或重新解释包装的业务状态。"""
    while config.get('mode')!='source-catalog':
        if type(config.get('base'))is not dict:raise ValueError('market snapshot needs the original source catalog')
        config=config['base']
    return config


def compose_archive_catalog(base_config,index_archive_config):
    """复用当前固定基准及指数静态归档，保留真实采集配置，排除旧准备物的动态尾部。

    base_config由运行owner提供固定原配置；index_archive_config仅贡献已绑定SHA的
    原生指数商店和静态归档包装，不替代当前采集身份。后继快照复用同一固定基准。
    """
    base=deepcopy(base_config);catalog=_catalog(base)
    if (index_archive_config.get('mode')!='source-daily-overlay'
            or index_archive_config.get('archive')is None or index_archive_config.get('snapshots')is not None):
        raise ValueError('market index static archive configuration invalid')
    seen={s['import_receipt_sha256']for s in catalog['stores']}
    for store in _catalog(index_archive_config)['stores']:
        if store['import_receipt_sha256']not in seen:
            catalog['stores'].append(deepcopy(store));seen.add(store['import_receipt_sha256'])
    wrapper=deepcopy(index_archive_config);wrapper['base']=base
    return wrapper


def compose_static_archive(base_config,archive,native_reader,*,max_file_bytes=268435456,max_bars=2000):
    """把独立、不可变的原生缺口归档接回原Reader链，动态尾部仍归原owner。"""
    if (type(archive)is not dict or set(archive)!={'path','sha256'}
            or type(native_reader)is not dict or set(native_reader)!={'library','sha256'}):
        raise ValueError('static daily archive composition invalid')
    return dict(mode='source-daily-overlay',base=deepcopy(base_config),archive=deepcopy(archive),
        native_reader=deepcopy(native_reader),snapshots=None,max_file_bytes=max_file_bytes,
        max_bars=max_bars,response_shape='segments')


def compose_native_import(base_config,imported):
    """同一新股票Native读取视图供价格合并和最终快照复用；旧根保持只读。"""
    base=deepcopy(base_config);catalog=_catalog(base)
    catalog['stores'].extend(imported['stores'])
    from .market_generation import read_fixed
    for store in imported['stores']:
        read_fixed(Path(store['store_root'])/'qmt-import.json',maximum=16777216,
                   identity=store['import_receipt_sha256'])
    if imported['schema']=='guanheng.qmt-analysis-native-import.v2':
        base=compose_static_archive(base,imported['archive'],catalog['native_reader'])
    return base


def load_snapshot_basics(members,basic_capture):
    """返回同一原QMT资料的(basics,行原件SHA)供缺口计划和快照复用；缺项保持None。"""
    from .market_generation import read_fixed
    read=lambda p:strict_json(Path(p).read_bytes())
    basic_capture=Path(basic_capture);basic_result=read(basic_capture/'RESULT.json');raw=basic_capture/'rows.jsonl'
    if basic_result['state']!='completed':
        raise ValueError('market snapshot basic originals differ')
    body=read_fixed(raw,maximum=67108864,identity=basic_result['rows_sha256'])
    by_symbol={}
    for line in body.splitlines():
        value=strict_json(line)
        if value['symbol']in by_symbol:raise ValueError('market snapshot basic identity repeated')
        by_symbol[value['symbol']]=value
    basics={}
    def day(value):
        if not value:return None
        return datetime.strptime(str(value),'%Y%m%d').date().isoformat()
    for member in members:
        exchange,code=member.split('.');symbol=code+'.'+{'SSE':'SH','SZSE':'SZ','BSE':'BJ'}[exchange]
        original=by_symbol.get(symbol);value=original['value']if original else None
        if not value:basics[member]=None;continue
        if value.get('InstrumentID')!=code or value.get('ExchangeID')!=symbol[-2:]:
            raise ValueError('market snapshot basic security differs')
        basics[member]=dict(
            name=value['InstrumentName'],  # 当次QMT资料的证券简称。
            market=exchange,  # 定日证券池已确认的交易市场，保持WT市场标识。
            security_type='stock',  # 定日普通A股池成员资格，不由代码前缀猜测。
            listed_on=day(value['OpenDate']),  # 原IPO日期；零日期保持未知None。
            expires_on=day(value['ExpireDate']),  # 原到期字段；未来哨兵保留原日期，不推断已退市。
            float_volume=value['FloatVolumn'],  # 原流通股本数值，单位由volume_unit独立声明。
            total_volume=value['TotalVolumn'],  # 原总股本数值；不作为过去日期的股本。
            volume_unit='unknown',  # 本资料批次尚无股数单位的独立校准资格。
            observed_at=datetime.fromtimestamp(original['received_wall_ms']/1000,timezone.utc).isoformat())  # 原资料实收时刻。
    return basics,basic_result['rows_sha256']


def prepare_market_snapshot(base_config,native_import,universe,basic_capture,output,*,daily_facts=None,security_reference=None,calendar=None,additional_archives=(),maximum_history_rows=2000):
    """独占新输出，返回原服务配置；调用方负责现有服务的统一版本切换。

    universe必须是同次QAB原请求绑定的定日股票池。basic_capture是已完成的
    原qmt_api资料归档；其接收时刻分别保留，当前股本不赋予历史股本资格。
    """
    read=lambda p:strict_json(Path(p).read_bytes())
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    canonical=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
    native_import=Path(native_import);imported=read(native_import)
    lineage=read(native_import.parent/'PROVENANCE.json');universe=Path(universe);pool=read(universe)
    if (imported.get('schema')not in ('guanheng.qmt-analysis-native-import.v1','guanheng.qmt-analysis-native-import.v2')
            or imported['state']!='completed' or imported['capture_sha256']!=lineage['capture_sha256']
            or lineage['request']['universe']['sha256']!=sha(universe)
            or imported['securities']!=pool['market_count']or pool['unresolved_identity_count']!=0
            or imported['observation_date']!=pool['date'].replace('-','')):
        raise ValueError('market snapshot original universe differs')
    base=compose_native_import(base_config,imported);catalog=_catalog(base)
    bindings={hashlib.sha256(canonical(b['binding'])).hexdigest()for b in lineage['batches']}
    if len(bindings)!=1:raise ValueError('market snapshot source bindings differ')
    original_binding=read(Path(lineage['capture'])/'BINDING.json')
    if original_binding['binding_sha256']not in bindings:raise ValueError('market snapshot original binding differs')
    if type(additional_archives)not in(tuple,list)or len(additional_archives)>32:
        raise ValueError('market snapshot additional archives invalid')
    for archive in additional_archives:
        base=compose_static_archive(base,archive,catalog['native_reader'],max_bars=maximum_history_rows)
    markets={'sh':'SSE','sz':'SZSE','bj':'BSE'}
    members=sorted(markets[s[:2]]+'.'+s[3:]for s in pool['members'])
    basics,basics_sha256=load_snapshot_basics(members,basic_capture)
    value=dict(
        schema='guanheng.market-source-snapshot.v1',  # 固定快照事实合同。
        snapshot_id='0'*64,  # 计算正文摘要后替换；后续价格批次精确绑定本身份。
        observation_date=pool['date'],  # 原股票池及日线观察日期。
        members=members,  # 已确认的定日普通A股池，保留缺日线/资料的证券。
        source_kind=imported['source_kind'],  # 实际QMT与SDK替身明确区分。
        source_received_at=imported['source_received_at'],  # 原日线输入收齐时刻。
        price_bases=['none','front_ratio'],  # 两种已落盘的来源价格口径。
        price_reference=dict(
            kind='supplier_current_front_ratio',  # 直接保存供应商返回的分析价。
            capture_sha256=imported['capture_sha256'],  # 固定当次参考原件，随价格版本一起冻结。
            requested_from=lineage['request']['start_date'],  # 请求来源日期YYYYMMDD，独立于实际首日。
            requested_to=lineage['request']['end_date'],  # 请求来源日期YYYYMMDD，独立于实际末日。
            reference_date=None,  # 原API响应没有明确复权锚定日期，保持未知。
            independent_factors=None),  # 本捕获没有独立因子事件，不能推导成全1或授因果回测。
        basics=basics,  # 当前证券资料及其自身可见时刻，缺失保持None。
        provenance=dict(
            capture_sha256=imported['capture_sha256'],  # 原QAB完整捕获身份。
            source_binding_sha256=next(iter(bindings)),  # 原QMT批次来源绑定；不以WT快照身份冒充来源会话。
            universe_sha256=sha(universe),  # 请求绑定的原定日股票池。
            basics_sha256=basics_sha256,  # 同一已校验资料字节的原件身份。
            base_configuration_sha256=hashlib.sha256(canonical(base)).hexdigest()))  # 原Reader完整配置身份。
    if daily_facts is not None:
        from .day_facts import DayFactsStore
        facts=DayFactsStore(daily_facts);facts.close()
        value['provenance']['daily_facts_sha256']=daily_facts['sha256']  # 固定定日补充事实目录，随资料及价格一起换代。
    if security_reference is not None or calendar is not None:
        from .security_reference import SecurityReference
        reference=SecurityReference(security_reference,calendar);reference.close()
        for key,descriptor in (('security_reference',security_reference),('calendar',calendar)):
            if descriptor is not None:
                value['provenance'][key+'_sha256']=descriptor['sha256']  # 同版本资料/日历原件摘要，分别保留。
    value['snapshot_id']=snapshot_identity(value);validate_market_snapshot(value)
    output=Path(output);output.mkdir(parents=False,exist_ok=False)
    path=output/'snapshot.json';path.write_bytes(canonical(value))
    config=dict(mode='source-market-snapshot',base=base,snapshot=dict(path=str(path.absolute()),sha256=sha(path)))
    if daily_facts is not None:config['daily_facts']=deepcopy(daily_facts)
    if security_reference is not None:config['security_reference']=deepcopy(security_reference)
    if calendar is not None:config['calendar']=deepcopy(calendar)
    target=output/'source.json';target.write_bytes(canonical(config))
    receipt=dict(schema='guanheng.market-source-snapshot-prepared.v1',snapshot_id=value['snapshot_id'],
        observation_date=value['observation_date'],market_count=len(members),basic_count=sum(v is not None for v in basics.values()),
        configuration=str(target.absolute()),configuration_sha256=sha(target),SDK_calls=0,service_changed=False)
    (output/'PREPARED.json').write_bytes(canonical(receipt))
    return receipt
