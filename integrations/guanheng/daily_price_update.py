"""原更新事务中的全类别价格阶段；同一owner、同一写租约、同一CURRENT。"""
from copy import deepcopy
from pathlib import Path
import time

from .daily_data_update import _save,_load,_descriptor
from .daily_data_stages import prepare_directory
from .daily_price_inputs import prepare_price_inputs
from .daily_price_archive import materialize_price_archive
from .daily_front_archive import prepare_front_archive
from .market_snapshot_prepare import compose_native_import,compose_static_archive,_catalog
from .source_market import create_native_source_market
from .security_reference import SecurityReference,trade_day_state
from ..guanheng_market_client import API_VERSION,strict_json
from .market_generation import read_fixed


def compact_price_base(base,retired):
    """完整合并新档替换已知旧补充层；原文件、主Native及采集包装保持。"""
    identities={(item['path'],item['sha256'])for item in retired}
    value=deepcopy(base)
    def visit(node):
        archive=node.get('archive')
        if (node.get('mode')=='source-daily-overlay'and node.get('snapshots')is None
                and archive is not None and(archive['path'],archive['sha256'])in identities):
            return visit(node['base'])
        if isinstance(node.get('base'),dict):node['base']=visit(node['base'])
        return node
    return visit(value)


def _coverage_count():
    return dict(
        known_scope_count=0,  # 本市场/类别全部已知保留身份，独立于当前Source名册。
        native_target_count=0,  # 实际Native可读闭合目标日的数量，停牌无条目保持未计入。
        source_observed_count=0,  # 当前Source实际名册成员数量，旧保留集不冒充当前分母。
        source_native_target_count=0,  # 当前Source成员中目标日Native实际可读数。
        expected_count=None,  # 完整动态组才赋整数；未知和未支持保持None。
        known_price_eligible_count=0,  # 已知身份中需要核价的数量，排除有官方用途依据的非价格记录。
        source_price_eligible_count=0,  # 当前Source成员中需要核价的数量。
        price_excluded_count=0,  # 已知非价格身份数；原身份和规则证据仍在scope。
        source_price_excluded_count=0,  # 当前Source非价格成员数，不减少原Source分组应有数。
        price_expected_count=None,  # 完整原Source组扣除有据非价格用途后的价格应核数；未知保持None。
        tails={},  # 真实原生末日到证券数量；无原生历史单列unknown。
        gap_reasons={})  # 当前目标不可读的逐原因数量；有合格事实才确认停牌等分类。


def prepare_price_update(request,native,base_configuration,directory,*,deadline,cancelled,environ=None,daily_facts=None):
    """先完成原股票Native，再合并额外价格和旧补充档，返回快照所需唯一补充版本。

    调用者持同一发布租约；本函数串行持有和关闭读取实例。失败保留价格输入原槽
    和不可变输出尝试；成功阶段按完整描述符恢复，最终CURRENT由原run_update发布。
    """
    root=Path(directory).absolute();root.mkdir(exist_ok=True)
    binding=dict(request=request,native=native,base_configuration=base_configuration)
    intent=root/'REQUEST.json'
    if intent.exists():
        if strict_json(read_fixed(intent,maximum=16777216))!=binding:raise ValueError('daily price update original differs')
    else:_save(intent,binding)
    final=root/'RESULT.json'
    if final.exists():return _descriptor(final)
    def check():
        if cancelled():raise InterruptedError('daily price update stopped')
        if time.monotonic()>=deadline:raise TimeoutError('daily price update deadline')
    check();scope=_load(request['scope']);universe=_load(scope['universe'])
    inputs=None
    if universe['securities']:
        price_request=dict(schema='guanheng.daily-price-inputs.v1',
            universe=scope['universe'],current_configuration=request['current_configuration'],
            snapshot_id=request['snapshot_id'],reference=scope['reference'],calendar=request['calendar'],
            connections=request['connections'],protected_slots=request['protected_slots'],
            authorized_from=request['authorized_from'],source_kind=request['source_kind'])
        if request.get('cache_seed')is not None:price_request['cache_seed']=request['cache_seed']
        if request.get('index_fallback')is not None:price_request['index_fallback']=request['index_fallback']
        inputs=prepare_price_inputs(price_request,root/'inputs',
            deadline=deadline,cancelled=cancelled,environ=environ)
    base=_load(base_configuration,1048576)
    if native is not None:
        base=compose_native_import(base,_load(native))
    elif base.get('mode')=='source-market-snapshot':
        # 价格先行沿上一成功Reader链合并；日事实/指标池仍由原快照保留真实日期。
        base=base['base']
    base=compact_price_base(base,request.get('replaced_archives',()))
    reader=_catalog(base)['native_reader'];limit=request['maximum_history_rows'];archive=None
    strategy_history=None;strategy_capture=None;strategy_coverage=None
    if request.get('strategy_history')is not None:
        if not set(request['strategy_history']['symbols'])<=set(scope['securities']):
            raise ValueError('strategy history outside declared price identities')
        from .daily_strategy_history import prepare_strategy_history
        strategy_history=prepare_strategy_history(dict(policy=request['strategy_history'],day=scope['observation_date'],
            reference=scope['reference'],calendar=request['calendar'],connections=request['connections'],
            protected_slots=request['protected_slots'],source_kind=request['source_kind'],snapshot_id=request['snapshot_id'],
            previous_requests=request.get('strategy_history_previous_requests',())),root/'sh',
            deadline=deadline,cancelled=cancelled,environ=environ)
        strategy_observation=_load(strategy_history)
        strategy_capture=strategy_observation['cache'];strategy_coverage=strategy_observation['coverage']
    if inputs is not None:
        market=create_native_source_market(base)
        try:
            def restore(output):
                result=_descriptor(output/'archive.json');_load(result)
                return result
            archive=prepare_directory(root,'price-archive','archive.json',lambda output:
                materialize_price_archive(inputs,market,request['previous_archives'],output,request['helper'],reader,
                    deadline=deadline,maximum_history_rows=limit,cancelled=cancelled,
                    additional_captures=(strategy_capture,)if strategy_capture is not None else()),restore)
        finally:market.close()
    # 即使本次无额外证券，也保持已有补充价格；旧整档遮蔽股票新尾日的情况在有补充输入时统一收敛。
    additional=[archive]if archive is not None else request['previous_archives']
    front=None
    if inputs is not None:
        previous_view=base
        for item in request['previous_archives']:
            previous_view=compose_static_archive(previous_view,item,reader,max_bars=limit)
        market=create_native_source_market(previous_view)
        try:
            def restore_front(output):
                descriptor=_descriptor(output/'RESULT.json');value=_load(descriptor)
                if value['archive']is not None:_load(value['archive'])
                return descriptor
            def build_front(output):
                prepare_front_archive(inputs,market,request['previous_archives'],output,request['helper'],
                    deadline=deadline,maximum_history_rows=limit,cancelled=cancelled,strategy_capture=strategy_capture,
                    strategy_coverage=strategy_coverage)
                return restore_front(output)
            front=prepare_directory(root,'price-front','RESULT.json',build_front,restore_front)
            front_value=_load(front)
            if front_value['archive']is not None:additional=[front_value['archive']]+additional
        finally:market.close()
    for item in additional:base=compose_static_archive(base,item,reader,max_bars=limit)
    input_values=_load(inputs)if inputs is not None else None
    supplement=None
    if input_values is not None and input_values.get('supplemental_prices')is not None:
        from .official_index_prices import load_official_index_prices
        supplement=load_official_index_prices(input_values['supplemental_prices'])
    market=create_native_source_market(base);coverage={};counts={};reference=None
    source_members=set(scope['source_members']);target=int(scope['observation_date'].replace('-',''))
    try:
        reference=SecurityReference(scope['reference'],request['calendar'])
        for symbol,identity in sorted(scope['securities'].items()):
            check();exchange,code=symbol.split('.')
            reply=market.call(dict(api_version=API_VERSION,action='history.source-daily-query',request=dict(
                exchange=exchange,code=code,**{'from':10000101,'to':target,'limit':1},
                adjustment='none',view='archive',include_archive=True)))
            if reply['status']['code']not in ('Ok','Unavailable'):raise ValueError('daily price coverage read failed')
            data=reply['data'];header=data.get('archive');last=header['last_date']if header else None
            present=any(bar['date']==target for bar in data.get('bars',[]));kind=identity['security_type'];key=exchange+'.'+kind
            excluded=symbol in scope.get('price_exclusions',{})
            if excluded and present:raise ValueError('non-price business role conflicts with readable Native price')
            count=counts.setdefault(key,_coverage_count())
            count['known_scope_count']+=1;count['native_target_count']+=present
            count['source_observed_count']+=symbol in source_members
            count['source_native_target_count']+=present and symbol in source_members
            count['known_price_eligible_count']+=not excluded
            count['source_price_eligible_count']+=symbol in source_members and not excluded
            count['price_excluded_count']+=excluded
            count['source_price_excluded_count']+=symbol in source_members and excluded
            label=str(last)if last is not None else'unknown';count['tails'][label]=count['tails'].get(label,0)+1
            detail=input_values['securities'].get(symbol)if input_values is not None else None
            reason=('available'if present else detail['reason']if detail is not None and detail['reason']!='available'
                    else'native_target_unavailable')
            if excluded:reason='not_price_instrument'
            assessment=reference.assess(dict(symbol=symbol,**{'from':target,'to':target}),identity,
                [bar['date']for bar in data.get('bars',[])],daily_facts)
            if not present and not excluded:
                if assessment['no_trade_dates']:reason='source_halted_no_trade'
                elif assessment['before_listing_dates']:reason='before_listing'
                elif assessment['after_expiry_dates']:reason='after_expiry'
                elif assessment['missing_dates']:reason='confirmed_missing_native'
                elif daily_facts is not None:
                    status=trade_day_state(daily_facts.security_state(scope['observation_date'],symbol))
                    if status in('source_halted_quantity_unknown','source_trade_state_inconsistent'):reason=status
            if not present:count['gap_reasons'][reason]=count['gap_reasons'].get(reason,0)+1
            attempts=[]
            if detail is not None:attempts.append(dict(provider='Qmt',state=detail['source_state'],reason=detail.get('source_error_code')))
            if supplement is not None and symbol in supplement['securities']:
                extra=supplement['securities'][symbol]
                attempts.append(dict(provider=extra['metadata']['source']['provider'],state=extra['state'],reason=extra['reason']))
            coverage[symbol]=dict(
                security_type=kind,  # 本轮价格身份分类，保留unknown。
                last_date=last,  # 实际完整原生档尾日，无历史为None。
                target_readable=present,  # 只由原Reader真实目标日条目确认。
                reason=reason,  # 可读、原Source缺项或合格日事实分类，未推造价格。
                source_member=symbol in source_members,  # 当前动态名册与历史保留范围分别计数。
                assessment=assessment,  # 同一原日事实/日历准入，停牌无成交不补0。
                source_attempts=attempts)  # 原QMT状态及可选官方补充状态，各自不改写对方事实。
    finally:
        try:market.close()
        finally:
            if reference is not None:reference.close()
    markets={'SH':'SSE','SZ':'SZSE','BJ':'BSE'}
    for group in scope['groups']:
        key=markets[group['market']]+'.'+group['security_type']
        count=counts.setdefault(key,_coverage_count())
        count['expected_count']=group['expected_count'];count['source_state']=group['state']
        count['price_expected_count']=(group['expected_count']-count['source_price_excluded_count']
            if group['expected_count']is not None else None)
        count['source_reason']=group['reason_code']
    result=dict(
        schema='guanheng.daily-price-update.v1',  # 同一原更新事务的全类别价格阶段结果。
        scope=request['scope'],  # 动态资料/价格名单原件及未知分母。
        inputs=inputs,  # 实际缓存/HPR/回读；无额外证券时为空。
        reference=scope['reference'],  # 最终快照消费同一资料版本。
        additional_archives=additional,  # 完整补充原价及独立前复权键，不同参考保持其原归属。
        front=front,  # 当前前复权参考/旧完整参考的逐证券选择，缺项不阻断原价。
        maximum_history_rows=limit,  # 显式每证券历史容量，公开单次查询仍为2000。
        counts=counts,  # 逐组Source应有/实际Native覆盖及真实尾日分布。
        securities=coverage)  # 每证券来源成员、实际尾日及缺口原因。
    if strategy_history is not None:
        result['strategy_history']=strategy_history  # 显式长窗口来源/缺口观察；未配置时保持原协议形状。
    _save(final,result);return _descriptor(final)
