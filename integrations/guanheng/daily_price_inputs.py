"""同一日线owner内的全类别价格输入；复用原缓存/HPR，指标股票池独立。"""
from datetime import datetime,timedelta
import hashlib
import math
from pathlib import Path
import time
import uuid

from ..guanheng_market_client import API_VERSION,strict_json
from ..guanheng_market_client.security import validate_security_identity
from .market_generation import encode,read_fixed
from .daily_data_update import _save,_load,_descriptor
from .daily_data_stages import prepare_directory
from .analysis_price_capture import load_price_capture,price_batches,original_price_quality
from .daily_gap_update import prepare_gap_plan,advance_gap_plan,freeze_gap_progress
from .daily_gap_plan import load_gap_plan, restore_gap_plan
from .security_reference import SecurityReference,trade_day_state
from .source_market import create_native_source_market


def prepare_price_inputs(request,directory,*,deadline,cancelled=lambda:False,environ=None,daily_facts=None):
    """调用方持同一publication租约；同步完成缓存先读、实际缺口续补和回读。

    request固定价格池、旧价格版本、授权起日及原保护槽；不修改指标股票池。
    本函数只保存原件/计划/覆盖，Native与CURRENT由原更新链随后统一发布。
    目录恢复沿原capture_id、slot和已完成阶段；截止/取消不重置源端责任。
    """
    required={'schema','universe','current_configuration','snapshot_id','reference','calendar',
              'connections','protected_slots','authorized_from','source_kind'}
    if (type(request)is not dict or not required<=set(request)
            or set(request)-required-{'cache_seed','index_fallback','local_qmt_dat_root','local_helper'}
            or request['schema']!='guanheng.daily-price-inputs.v1'):
        raise ValueError('daily price input request invalid')
    if ('local_qmt_dat_root' in request) != ('local_helper' in request):
        raise ValueError('daily price local source configuration incomplete')
    if request.get('index_fallback')not in(None,'official-publishers'):
        raise ValueError('daily price official fallback invalid')
    if (not callable(cancelled)or type(deadline)not in(int,float)or not math.isfinite(deadline)
            or request['source_kind']not in('actual-qmt','sdk-synthetic')):
        raise ValueError('daily price input cancellation or finite deadline invalid')
    def check():
        if cancelled():raise InterruptedError('daily price inputs stopped')
        if time.monotonic()>=deadline:raise TimeoutError('daily price inputs deadline')
    check();root=Path(directory).absolute();root.mkdir(parents=False,exist_ok=True)
    original=root/'REQUEST.json'
    if original.exists():
        if strict_json(read_fixed(original,maximum=16777216))!=request:
            raise ValueError('daily price original input differs')
    else:_save(original,request)
    final=root/'INPUTS.json'
    if final.exists():return _descriptor(final)
    universe=_load(request['universe']);members=universe['securities'];day=universe['observation_date']
    if (universe.get('schema')!='guanheng.price-universe.v1'or type(members)is not dict
            or not 1<=len(members)<=20000):raise ValueError('daily price universe invalid')
    target=datetime.strptime(day,'%Y-%m-%d').date();authorized=datetime.strptime(request['authorized_from'],'%Y%m%d').date()
    if authorized>target:raise ValueError('daily price authorization outside target')
    source=create_native_source_market(_load(request['current_configuration'],1048576))
    bounds={};previous={};archived_raw_dates={};locally_covered_target=set()
    capture_from=authorized.strftime('%Y%m%d');last=target.strftime('%Y%m%d')
    try:
        for symbol,identity in members.items():
            check()
            validate_security_identity(identity)
            if identity['symbol']!=symbol or identity['security_type']not in ('stock','etf','index','unknown'):
                raise ValueError('daily price universe member invalid')
            exchange,code=symbol.split('.')
            query=dict(exchange=exchange,code=code,**{'from':int(capture_from),'to':int(last),'limit':2000},
                adjustment='none',view='archive',include_archive=True)
            if request['snapshot_id']is not None:query['snapshot_id']=request['snapshot_id']
            reply=source.call(dict(api_version=API_VERSION,action='history.source-daily-query',request=query))
            if reply['status']['code']not in ('Ok','Unavailable'):
                raise ValueError('daily price previous history unavailable')
            archive=reply['data'].get('archive')
            qmt=code+'.'+{'SSE':'SH','SZSE':'SZ','BSE':'BJ'}[exchange]
            archived_raw_dates[qmt]={str(bar['date']) for bar in reply['data'].get('bars',[])
                if original_price_quality({key:value for key,value in bar.items() if key not in ('date','symbol')})=='qualified'}
            if last in archived_raw_dates[qmt]:
                locally_covered_target.add(symbol)
            # 原尾日边界只用于验明已创建的旧计划，仍沿其固定任务身份。
            archive_tail=datetime.strptime(str(archive['last_date']),'%Y%m%d').date() if archive else None
            first=max(authorized,min(target,archive_tail+timedelta(days=1))) if archive_tail is not None else authorized
            bounds[qmt]=first.strftime('%Y%m%d');previous[symbol]=archive
    finally:source.close()
    calendar=_load(request['calendar'])
    from guanheng_app.observation.calendars import official_calendar
    from .daily_batch_source import seed_local_analysis_batches, seed_unaffected_readback_batches
    from guanheng_qmt_shm.market_daily_preparation import MarketDailyPreparation
    from .source_history_transport import BoundHistorySource
    rows,_=official_calendar(calendar)
    needed=sum(r['is_open']==1 and capture_from<=r['date'].replace('-','')<=last for r in rows)
    if not 1<=needed<=2000:raise ValueError('daily price cache window exceeds capacity')
    reference=SecurityReference(request['reference'],request['calendar'])
    raw_ranges=None
    def capture(name, *, previous=None, changed_symbols=None):
        check();seed=request.get('cache_seed')if name=='cache'else None
        if seed is not None:
            original=load_price_capture(seed);selection=original['request']
            if (original['source_kind']==request['source_kind']and selection['symbols']==sorted(bounds)
                    and selection['start_date']<=capture_from and selection['end_date']==last
                    and selection['max_rows']>=needed
                    and (selection.get('raw_ranges') is None or selection.get('raw_ranges') == raw_ranges)):
                # 原捕获身份保持；本轮名称/类别/分母由独立universe与reference拥有。
                return seed
        request_file=root/(name+'-REQUEST.json')
        if not request_file.exists():
            intent=dict(
                schema='qab.request-plan.v1',  # 原批读捕获合同。
                capture_id=str(uuid.uuid4()),  # 本阶段一次生成，恢复沿原身份。
                source_kind=request['source_kind'],  # 真实QMT与替身显式区分。
                symbols=sorted(bounds),  # 全类别规范QMT证券，非指标分母。
                start_date=capture_from,  # 完整已授权窗口保留供应商前复权参考；HPR仍只补bounds之后的原价缺口。
                end_date=last,  # 原闭合目标日，不借接收时刻推进。
                max_rows=needed,  # 全部所需官方交易日；公开响应额度仍沿原协议。
                universe=request['universe'])  # 独立价格池正文身份。
            if raw_ranges is not None:
                intent['raw_ranges']=raw_ranges  # 原价各证券仍缺的请求区间，前复权沿原整体窗口。
            _save(request_file,intent)
        capture_request=strict_json(read_fixed(request_file,maximum=16777216))
        output=root/name
        if not(output/'manifest.json').exists():
            if seed is not None and 'raw_ranges' not in capture_request:
                seed_local_analysis_batches(root,capture_request,[seed],{},check=check)
            if previous is not None:
                captured = load_price_capture(previous)
                actual = captured['request']
                # 只有原QMT参数相同的批次沿用已核slot；本轮股票池元数据不参与。
                keys = ('source_kind','symbols','start_date','end_date','max_rows')
                if all(actual[key] == capture_request[key] for key in keys):
                    adjustments=('none','front_ratio') if actual.get('raw_ranges') == capture_request.get('raw_ranges') else ('front_ratio',)
                    seed_unaffected_readback_batches(output,previous['directory'],captured,changed_symbols,
                                                     check=check,adjustments=adjustments)
            from .daily_price_capture import capture_price_window
            capture_price_window(capture_request,output,request['connections']['batch'],deadline=deadline,
                cancelled=cancelled,environ=environ)
        descriptor=dict(directory=str(output),sha256=_descriptor(output/'manifest.json')['sha256'])
        load_price_capture(descriptor)
        return descriptor
    try:
        snapshot=dict(snapshot_id=hashlib.sha256(encode(request)).hexdigest(),observation_date=day,basics={})
        local=None
        if 'local_qmt_dat_root' in request:
            from .daily_local_prices import local_price_groups, prepare_local_prices
            open_days={row['date'] for row in rows if row['is_open']==1 and int(capture_from)<=int(row['date'].replace('-',''))<=int(last)}
            local_wanted={}
            qmt_to_symbol={}
            for symbol in members:
                check()
                exchange,code=symbol.split('.')
                qmt=code+'.'+{'SSE':'SH','SZSE':'SZ','BSE':'BJ'}[exchange]
                qmt_to_symbol[qmt]=symbol
                basic=reference.security(snapshot,symbol)
                local_wanted[qmt]={date for date in open_days if (basic['listed_on'] or date)<=date<=(basic['expires_on'] or date)
                                   and date.replace('-','') not in archived_raw_dates[qmt]}
            if daily_facts is not None:
                for date in sorted(open_days):
                    check()
                    for qmt,symbol in qmt_to_symbol.items():
                        if date in local_wanted[qmt] and trade_day_state(daily_facts.security_state(date,symbol))=='source_halted_no_trade':
                            local_wanted[qmt].remove(date)
            def build_local(output):
                return prepare_local_prices(request['local_qmt_dat_root'],local_wanted,output,request['local_helper'],
                                            deadline=deadline,cancelled=cancelled)
            local=prepare_directory(root,'local-price','catalog.json',build_local,
                                    lambda output: _descriptor(output/'catalog.json'),recover_prior=True)
            for qmt,_,prices in local_price_groups(local,check=check):
                dates={row['date'] for row in prices}
                local_wanted[qmt].difference_update(dates)
                archived_raw_dates[qmt].update(date.replace('-','') for date in dates)
                if day in dates:
                    locally_covered_target.add(qmt_to_symbol[qmt])
            raw_ranges={}
            for qmt,dates in local_wanted.items():
                if dates:
                    start,end=min(dates),max(dates)
                    raw_ranges[qmt]=dict(start_date=start.replace('-',''),end_date=end.replace('-',''),
                        max_rows=sum(start<=date<=end for date in open_days))
        initial=capture('cache')
        def restore(output):
            return restore_gap_plan(output/'PLAN.json',capture=initial,snapshot_id=snapshot['snapshot_id'],
                authorized_from=capture_from,authorized_to=last,protected_slots=request['protected_slots'],
                required_adjustments=('none',),required_from={},legacy_window=(min(bounds.values()),bounds),
                deadline=deadline,cancelled=cancelled)
        plan=prepare_directory(root,'gap-plan','PLAN.json',lambda output:prepare_gap_plan(initial,reference,snapshot,output,
            protected_slots=request['protected_slots'],daily_facts=daily_facts,
            authorized_from=capture_from,authorized_to=last,deadline=deadline,
            required_adjustments=('none',),archived_raw_dates=archived_raw_dates,cancelled=cancelled),restore,recover_prior=True)
        del archived_raw_dates  # 逐日集合用于本地计划，释放后再物化QMT回读。
        plan_value=load_gap_plan(plan,deadline=deadline,cancelled=cancelled);progress=None;selected=initial
        if plan_value['tasks']:
            readback_progress=root/'READBACK-PROGRESS.json'
            if (root/'readback'/'manifest.json').exists()and not readback_progress.exists():
                # 已完成旧回读缺时点凭据时保守保留责任，不把恢复后的返回配给旧缓存。
                _save(readback_progress,freeze_gap_progress(plan,None,deadline=deadline,cancelled=cancelled))
            batch=BoundHistorySource(request['connections']['batch'],environ=environ,reuse_connections=True)
            try:
                owner=MarketDailyPreparation(lambda:BoundHistorySource(request['connections']['hpr'],environ=environ,
                    reuse_connections=True),batch,concurrency=4)  # 复用原SDK默认四worker上限，仅并行终端外HPR通信。
                progress=advance_gap_plan(plan,root/'gap-work',owner,deadline=deadline,max_tasks=10000,cancelled=cancelled)
            finally:batch.close()
            if not readback_progress.exists():
                _save(readback_progress,freeze_gap_progress(plan,progress,root/'gap-work'/'observations',
                    deadline=deadline,cancelled=cancelled))
            progress=_load(_descriptor(readback_progress))  # 与原readback共同恢复，完整SDK记录仍在原gap-work。
            selected=capture('readback',previous=initial,changed_symbols={task['symbol'] for task in plan_value['tasks']})
        manifest=load_price_capture(selected);data={}
        for _,items in price_batches(selected,manifest,deadline=deadline,cancelled=cancelled):
            for symbol,item in items.items():data[symbol]=item
        source_days={};counts={kind:dict(
            known_scope_count=0,  # 实际价格输入名单数量，不代替动态全市场应覆盖数。
            target_in_cache=0,  # 原回包实际含目标日的证券数。
            target_native_qualified=0,  # 目标行满足原价Native字段及OHLC准入的数量。
            target_absent=0)  # 目标日未在缓存出现，具体原因另列。
            for kind in ('stock','etf','index','unknown')}
        for symbol,identity in members.items():
            check();exchange,code=symbol.split('.');qmt=code+'.'+{'SSE':'SH','SZSE':'SZ','BSE':'BJ'}[exchange]
            item=data.get(qmt,dict(status='not_requested',data={}))
            dates=sorted(item['data']);present=last in item['data'];count=counts[identity['security_type']]
            quality={d:original_price_quality(bar)for d,bar in item['data'].items()}
            qualified=present and quality[last]=='qualified'
            count['known_scope_count']+=1;count['target_in_cache']+=present;count['target_absent']+=not present
            count['target_native_qualified']+=qualified
            basic=reference.security(snapshot,symbol)
            reason=('available'if qualified else quality[last]if present else'before_listing'if basic['listed_on']is not None and day<basic['listed_on']else
                    'after_expiry'if basic['expires_on']is not None and day>basic['expires_on']else
                    'source_unavailable'if item['status']in('invalid','requires_partition')else'target_not_in_cache')
            source_days[symbol]=dict(
                security_type=identity['security_type'],  # 原价格池分类，unknown保留。
                source_state=item['status'],  # 原SDK逐证券状态，不从缓存缺日推造不支持。
                source_error_code=item.get('error_code'),  # 原Source逐证券失败码，保留无效值和空结果的区别。
                first=dates[0]if dates else None,  # 实际原价缓存首日，未知不填0。
                last=dates[-1]if dates else None,  # 实际原价缓存尾日，区别目标日。
                target_in_cache=present,  # 实际原回包是否包含闭合目标日。
                target_native_qualified=qualified,  # 缓存有行与完整Native可写分别表达。
                unqualified_dates={d:r for d,r in quality.items()if r!='qualified'},  # 原缺字段/零价/矛盾保留具体日期，未填0。
                reason=reason,  # 缺项/上市前/到期/供应商状态分别表达。
                previous_archive=previous[symbol])  # 已有Native实际范围，后续合并保留全历史。
        supplement=None
        if request.get('index_fallback')=='official-publishers':
            selected_indices={symbol:identity for symbol,identity in members.items()
                if identity['security_type']=='index'and not source_days[symbol]['target_native_qualified']
                and symbol not in locally_covered_target
                and source_days[symbol]['reason']not in('before_listing','after_expiry')}
            if selected_indices:
                from .official_index_prices import prepare_official_index_prices
                supplement=prepare_official_index_prices(selected_indices,capture_from,last,root/'official-indices',
                    deadline=deadline,cancelled=cancelled)
        result=dict(
            schema='guanheng.daily-price-input-result.v1',  # 价格输入事实，不代表Native发布成功。
            observation_date=day,  # 本轮闭合市场目标日。
            universe=request['universe'],  # 独立价格池来源，指标股票池保持原值。
            cache=selected,  # 实读回包的原manifest/slot身份。
            plan=plan,  # 原不可变缺口计划，未知任务沿原槽。
            preparation=progress,  # 原调用观察，call_returned不提升覆盖资格。
            expected_counts=universe.get('expected_counts'),  # 动态分母未知保持None。
            counts=counts,  # 已知范围逐类缓存数量，不宣称全市场分母。
            securities=source_days,  # 每证券实际日期/原因，缺失不填0。
            supplemental_prices=supplement)  # 显式官方原价原件；不修改原QMT捕获事实。
        if local is not None:
            result['local_prices']=local  # 已核DAT与WT派生日线的独立原价目录。
        _save(final,result);return _descriptor(final)
    finally:reference.close()
