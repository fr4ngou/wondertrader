"""同一数据owner内维护价格名单；Source完整性与历史保留范围分别表达。"""
from pathlib import Path
import time

from .daily_data_update import _save,_load,_descriptor
from .market_generation import read_fixed
from ..guanheng_market_client import strict_json
from ..guanheng_market_client.security import validate_security_identity


def prepare_price_scope(configuration,day,stock_universe,current,directory,*,deadline,cancelled,environ=None,previous_scopes=()):
    """固定本轮名单原件，返回额外价格输入；调用者持原publication写租约。

    baseline_reference保留已有身份；动态名册逐组声明当前分母，缺详情仍在名单。
    股票指标池由其原公开日事实拥有，此处只从额外价格捕获中排除同日已处理成员。
    reference_connection为空或原能力未到时保存等待事实，已知证券继续价格推进。
    """
    from .security_reference import SecurityReference
    from .source_reference_capture import capture_reference
    from .source_history_transport import BoundHistorySource,SourcePending
    from guanheng_qmt_shm.read_retention_client import RetainedReadPending,RetainedReadFailure
    from guanheng_qmt_shm.security_reference_source import SecurityReferenceSource
    required={'baseline_reference','reference_connection','scope','authorized_from','maximum_history_rows'}
    if type(configuration)is not dict or set(configuration)!=required:
        raise ValueError('daily price scope configuration invalid')
    root=Path(directory).absolute();root.mkdir(exist_ok=True)
    intent=root/'REQUEST.json'
    request=dict(configuration=configuration,day=day,stock_universe=stock_universe,current=current,previous_scopes=list(previous_scopes))
    if intent.exists():
        if strict_json(read_fixed(intent,maximum=16777216))!=request:raise ValueError('daily price scope original differs')
    else:_save(intent,request)
    final=root/'SCOPE.json'
    if final.exists():return _descriptor(final)
    def check():
        if cancelled():raise InterruptedError('daily price scope stopped')
        if time.monotonic()>=deadline:raise TimeoutError('daily price scope deadline')
    check();baseline=configuration['baseline_reference']
    reader=SecurityReference(baseline)
    try:members=dict(reader._rows)
    finally:reader.close()
    previous_reference=_load(current['configuration'],1048576).get('security_reference')
    if previous_reference is not None:
        reader=SecurityReference(previous_reference)
        try:members.update(reader._rows)
        finally:reader.close()
    # 最新固定价格池已包含此前的历史保留集；Source局部失败或退出名册不删除已知身份。
    for descriptor in previous_scopes:
        prior=_load(descriptor)
        for symbol,identity in prior['securities'].items():
            validate_security_identity(identity)
            if symbol not in members:members[symbol]=identity
    groups=[dict(market=m,security_type=k,state='unavailable',expected_count=None,observed_count=0,
                 source_groups=[],reason_code='reference_capability_unavailable')
            for m in configuration['scope']['markets']for k in configuration['scope']['security_types']]
    reference=previous_reference or baseline;source_members=[];connection=configuration['reference_connection']
    state=dict(state='waiting_reference_capability',membership_complete=False,expected_count=None,groups=groups)
    if connection is not None:
        transport=BoundHistorySource(connection,environ=environ,reuse_connections=True)
        try:
            source=SecurityReferenceSource(transport)
            try:
                state=capture_reference(source,configuration['scope'],root/'source',deadline=deadline,cancelled=cancelled)
            except (SourcePending,RetainedReadPending,RetainedReadFailure)as failure:
                # 保存原slot；价格可用性不取决于本轮资料通信状态。
                state=dict(state='reference_source_unavailable',membership_complete=False,expected_count=None,
                           groups=groups,error_type=type(failure).__name__)
            if state.get('reference')is not None:
                reference=state['reference'];dynamic=_load(reference)
                members.update(dynamic['securities']);source_members=sorted(dynamic['securities'])
            groups=state.get('groups',groups)
        finally:transport.close()
    check();pool=_load(stock_universe);primary={}
    for raw in pool['members']:
        symbol={'sh':'SSE','sz':'SZSE','bj':'BSE'}[raw[:2]]+'.'+raw[3:]
        identity=members.get(symbol,dict(symbol=symbol,name=None,market=symbol.split('.')[0],
            security_type='stock',listed_on=None,expires_on=None,observed_at=None))
        # 原指标池声明普通A股；保留Source分类原件，价格身份以当次股票池事实准入。
        identity=dict(identity,security_type='stock');primary[symbol]=validate_security_identity(identity)
    all_members=dict(members);all_members.update(primary)
    if not 1<=len(all_members)<=20000:raise ValueError('daily price universe capacity')
    expected={kind:(sum(g['expected_count']for g in groups if g['security_type']==kind)
                    if all(g['state']=='complete'for g in groups if g['security_type']==kind)else None)
              for kind in configuration['scope']['security_types']}
    universe=dict(
        schema='guanheng.price-universe.v1',  # 价格范围独立于普通A股指标池。
        observation_date=day,  # 同一闭合市场日期。
        securities={s:v for s,v in all_members.items()if s not in primary},  # 额外价格仅处理原股票链之外成员。
        expected_counts=expected)  # 动态Source各组完整才给全类别分母；旧名册数量不替代。
    _save(root/'UNIVERSE.json',universe)
    result=dict(
        schema='guanheng.daily-price-scope.v1',  # 本轮动态资料及价格名单固定结果。
        observation_date=day,  # 原闭合日期，与资料捕获时刻分开。
        universe=_descriptor(root/'UNIVERSE.json'),  # 本轮额外价格捕获身份。
        reference=reference,  # 可用资料版本；资料通信异常继续原可用版本。
        groups=groups,  # 逐市场/类别完整性、未知及原原因。
        source_members=source_members,  # 动态当前名册成员；历史保留集不混入当前分母。
        securities=all_members,  # 完整可追溯价格范围，含本轮股票及旧证券。
        primary_members=sorted(primary),  # 原指标股票池，仅用于归属和覆盖汇总。
        reference_state=state)  # 资料准备完成与价格覆盖分别保存。
    _save(final,result);return _descriptor(final)
