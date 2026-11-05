"""同一日线owner先发布真实价格；公共辅助事实独立重试并保留原时点。"""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
from pathlib import Path

from .daily_data_update import _save,_load,_descriptor
from .daily_price_scope import prepare_price_scope
from .daily_price_update import prepare_price_update,compact_price_base
from .market_generation import GenerationPublisher,encode,read_fixed,read_generation
from .market_snapshot_prepare import compose_static_archive,_catalog
from ..guanheng_market_client import strict_json
from ..guanheng_market_client.market_snapshot import snapshot_identity,validate_market_snapshot


def price_refresh(configuration,day,directory,*,publisher,deadline,cancelled,environ=None,
                  previous_requests=()):
    """原publication租约内先完成全类别价格；不伪造本日股票池、换手或其他日事实。

    本日价格请求和所有原slot固定落盘，可随原owner接续；发布后仍由原辅助事实
    任务推进完整指标快照。已有日事实快照日期不前移，实际价格日期归各原Reader行。
    """
    root=Path(directory).absolute();root.mkdir(parents=True,exist_ok=True)
    if not isinstance(publisher,GenerationPublisher)or publisher._lock is None:
        raise ValueError('daily price refresh requires original publication lease')
    if publisher.directory!=Path(configuration['template']['publication_directory']).absolute():
        raise ValueError('daily price refresh publication differs')
    final=root/'RESULT.json'
    if final.exists():
        result=strict_json(read_fixed(final,maximum=16777216))
        if (result.get('schema')!='guanheng.daily-price-refresh-result.v1'or result['price_date']!=day
                or Path(result['request'])!=root/'REQUEST.json'
                or _descriptor(root/'REQUEST.json')['sha256']!=result['request_sha256']):
            raise ValueError('daily price refresh completed request differs')
        _load(result['price_result']);_load(result['generation']['configuration'],1048576)
        return result
    parent_file=root/'PARENT.json'
    if parent_file.exists():parent=strict_json(read_fixed(parent_file,maximum=65536))
    else:
        current,current_sha=read_generation(publisher.current_file)
        parent=dict(generation=current,sha256=current_sha)  # 固定本轮旧价格版本；恢复不跟随后续指针。
        _save(parent_file,parent)
    current=parent['generation'];old_config=_load(current['configuration'],1048576)
    if old_config.get('mode')!='source-market-snapshot':raise ValueError('daily price refresh snapshot required')
    # 输入责任发现共用原目录布局，恢复只核原ID；配置及所有旧槽保留。
    inputs=root/'inputs';inputs.mkdir(exist_ok=True)
    intent=inputs/'INPUTS.json';bound=dict(configuration=configuration,day=day,previous_requests=list(previous_requests))
    if intent.exists():
        if strict_json(read_fixed(intent,maximum=16777216))!=bound:raise ValueError('daily price refresh input differs')
    else:_save(intent,bound)
    protected=set(configuration['template']['protected_slots']);previous_archives=[];retired_archives=[]
    for path in previous_requests:
        request=strict_json(read_fixed(path,maximum=16777216));protected.update(request['protected_slots'])
        if request.get('price_maintenance')is not None:protected.update(request['price_maintenance']['protected_slots'])
        # 已发出的价格HPR责任保持原slot；新缓存未确认覆盖前，后继缺口计划沿原保护区间。
        prior=Path(path).parent/'work'/'prices'/'inputs'/'gap-work'/'preparation'
        protected.update(str(slot)for slot in prior.glob('*.json'))
        completed=Path(path).parent/'work'/'prices'/'RESULT.json'
        if completed.exists():
            # 完成的同owner结果记录被后继整档合并的补充层；只收敛这些已知层，不猜原生基础档。
            retired_archives.extend(strict_json(read_fixed(completed,maximum=16777216))['additional_archives'])
    base=old_config['base']
    while isinstance(base,dict):
        archive=base.get('archive')
        if archive is not None:
            document=_load(archive)
            # 最近一次补充档优先；原价和前复权各保留一份完整原档，底层原股票仍由Reader链拥有。
            entries=document.get('entries',[])
            if entries:
                adjustment=entries[0]['provenance'][0]['metadata']['adjustment']
                if adjustment not in {kind for kind,_ in previous_archives}:previous_archives.append((adjustment,archive))
        base=base.get('base')
    retired_archives.extend(item for _,item in previous_archives)
    retired_archives=list({(item['path'],item['sha256']):item for item in retired_archives}.values())
    scope=prepare_price_scope(configuration['price_scope'],day,None,current,inputs/'prices',
        deadline=deadline,cancelled=cancelled,environ=environ)
    request_path=root/'REQUEST.json'
    maintenance=dict(scope=scope,current_configuration=current['configuration'],snapshot_id=current['snapshot_id'],
        calendar=configuration['template']['calendar'],connections=configuration['inputs']['connections'],
        protected_slots=sorted(protected),authorized_from=configuration['price_scope']['authorized_from'],
        source_kind=configuration['inputs']['source_kind'],maximum_history_rows=configuration['price_scope']['maximum_history_rows'],
        previous_archives=[item for _,item in previous_archives],helper=configuration['template']['helper'],
        replaced_archives=retired_archives)  # 新整档包含的旧补充层；活动Reader替换，旧原件永久保留原引用。
    if configuration['price_scope'].get('index_fallback')is not None:
        maintenance['index_fallback']=configuration['price_scope']['index_fallback']
    request=dict(schema='guanheng.daily-price-refresh.v1',day=day,protected_slots=sorted(protected),
                 price_maintenance=maintenance)  # 原公共日事实任务可发现此请求的HPR/批读责任。
    if request_path.exists():
        if strict_json(read_fixed(request_path,maximum=16777216))!=request:raise ValueError('daily price refresh request differs')
    else:_save(request_path,request)
    work=root/'work';work.mkdir(exist_ok=True)
    state_path=work/'STATE.json'
    if not state_path.exists():_save(state_path,dict(stages={}))  # 复用原旧计划发现接口；价格计划归原prices/inputs。
    result_path=prepare_price_update(maintenance,None,current['configuration'],work/'prices',
        deadline=deadline,cancelled=cancelled,environ=environ)
    prices=_load(result_path);new_base=compact_price_base(old_config['base'],retired_archives);reader=_catalog(new_base)['native_reader']
    for archive in prices['additional_archives']:
        new_base=compose_static_archive(new_base,archive,reader,max_bars=prices['maximum_history_rows'])
    original_snapshot=_load(old_config['snapshot']);snapshot=deepcopy(original_snapshot)
    snapshot['provenance']['base_configuration_sha256']=hashlib.sha256(encode(new_base)).hexdigest()
    snapshot['provenance']['security_reference_sha256']=prices['reference']['sha256']
    snapshot['snapshot_id']=snapshot_identity(snapshot);validate_market_snapshot(snapshot)
    candidate=root/'snapshot';candidate.mkdir(exist_ok=True)
    def fixed(path,value):
        body=encode(value)
        if path.exists():
            if read_fixed(path,maximum=16777216)!=body:raise ValueError('daily price refresh immutable candidate differs')
        else:_save(path,value)
    fixed(candidate/'snapshot.json',snapshot)
    published_config=deepcopy(old_config);published_config.update(base=new_base,snapshot=_descriptor(candidate/'snapshot.json'),
                                                               security_reference=prices['reference'])
    fixed(candidate/'source.json',published_config);descriptor=_descriptor(candidate/'source.json')
    observed,observed_sha=read_generation(publisher.current_file)
    if observed['configuration']==descriptor:published,identity=observed,observed_sha
    else:published,identity=publisher.publish(descriptor,expected_current_sha256=parent['sha256'])
    from .daily_price_continuation import requires_price_continuation
    result=dict(
        schema='guanheng.daily-price-refresh-result.v1',  # 独立价格阶段的持久结果合同。
        price_date=day,  # 本次价格维护的闭合交易日，区别辅助事实日期。
        auxiliary_observation_date=original_snapshot['observation_date'],  # 旧事实和成员资格保持原真实日期。
        request=str(request_path),  # 本次原不可变请求，后继核其批读/HPR责任。
        request_sha256=_descriptor(request_path)['sha256'],  # 原请求完整字节身份，已完成阶段不跳过原责任校验。
        price_result=result_path,  # 原Reader逐证券覆盖及按市场/类别计数的完整结果描述符。
        generation=published,  # 同一publication原子采用的新读取版本。
        current_sha256=identity,  # 原CURRENT实际字节SHA，供后继CAS及发布验真。
        continuation_required=requires_price_continuation(prices),  # 未确认来源责任保留，不将准备返回当覆盖。
        published_at=datetime.now(timezone.utc).isoformat())  # 本地实际发布时间，不替代行情日期/来源接收时刻。
    _save(final,result);return result
