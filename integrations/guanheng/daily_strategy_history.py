"""同一数据owner的显式长窗口；可选来源失败保留普通价格链和原请求身份。"""
from datetime import datetime
from contextlib import contextmanager
import hashlib
import math
from pathlib import Path
import time
import uuid

from .daily_data_update import _save,_load,_descriptor
from .market_generation import encode,read_fixed
from .analysis_price_capture import load_price_capture,price_batches,original_price_quality
from .daily_price_capture import capture_price_window,PriceWindowResource
from .security_reference import SecurityReference
from .price_trading_exceptions import load_trading_exceptions


def validate_strategy_history(value):
    """校验可选策略窗口；seconds只限定来源观察，缺省120秒，原slot不随预算改变。"""
    if (type(value)is not dict or not {'symbols','from'}<=set(value)
            or set(value)-{'symbols','from','seconds','trading_exceptions'}):
        raise ValueError('strategy history configuration invalid')
    symbols=value['symbols']
    if type(symbols)is not list or not symbols or any(type(s)is not str for s in symbols)or symbols!=sorted(set(symbols)):
        raise ValueError('strategy history symbols invalid')
    for symbol in symbols:
        parts=symbol.split('.')
        if len(parts)!=2 or parts[0]not in('SSE','SZSE','BSE')or len(parts[1])!=6 or not parts[1].isascii()or not parts[1].isdigit():
            raise ValueError('strategy history symbol invalid')
    if type(value['from'])is not str or datetime.strptime(value['from'],'%Y%m%d').strftime('%Y%m%d')!=value['from']:
        raise ValueError('strategy history date invalid')
    seconds=value.get('seconds',120)
    if type(seconds)not in(int,float)or not math.isfinite(seconds)or seconds<=0:
        raise ValueError('strategy history source budget invalid')
    if value.get('trading_exceptions')is not None:
        item=value['trading_exceptions']
        if (type(item)is not dict or set(item)!={'path','sha256'}or type(item['path'])is not str
                or not Path(item['path']).is_absolute()or type(item['sha256'])is not str
                or len(item['sha256'])!=64 or any(c not in'0123456789abcdef'for c in item['sha256'])):
            raise ValueError('strategy history exceptions descriptor invalid')
    return value


def strategy_history_roots(requests):
    """由原REGISTERED REQUEST定位本owner子根；旧目录保持，不递归扫描任意文件。"""
    found=[]
    for request in requests:
        root=Path(request).parent/'work'/'prices'/'sh'  # 原角色根较长；短命名为SDK64字节代次文件预留Windows路径。
        if (root/'REQUEST.json').is_file():found.append(root)
    return list(dict.fromkeys(found))


def strategy_workflow(root):
    """已引用后继根固定指向首个原工作流，引用展平，避免跨日递归链。"""
    value=_load(_descriptor(Path(root)/'REQUEST.json'))
    if value['schema']!='guanheng.strategy-history-request.v1':raise ValueError('strategy history request schema differs')
    if value.get('workflow')is not None:
        original=_load(value['workflow'])
        if original.get('workflow')is not None or original['business_key']!=value['business_key']:
            raise ValueError('strategy history workflow identity differs')
        return Path(value['workflow']['path']).parent,original
    return Path(root),value


def strategy_slots(requests):
    """保留所有旧HPR/批读槽路径；不新建请求或授已返回资格。"""
    result=set()
    for root in strategy_history_roots(requests):
        origin,_=strategy_workflow(root)
        work=origin/'work'
        for folder in _capture_roots(work):
            result.update(str(p)for p in (folder/'slots').glob('*.json'))
        for plan_root in _plan_roots(work):
            result.update(str(p)for p in (plan_root/'gap-work'/'preparation').glob('*.json'))
    return result


def strategy_read_slots(requests):
    """原input discovery消费未封存v8槽，连接沿原冻结工作流上下文。"""
    seen=set()
    for root in strategy_history_roots(requests):
        origin,value=strategy_workflow(root)
        for capture in _capture_roots(origin/'work'):
            if (capture/'manifest.json').exists():continue
            for slot in (capture/'slots').glob('*.json'):
                if slot not in seen:
                    seen.add(slot);yield slot,value['context']['connections']['batch']


def _capture_roots(work):
    """每个回读按原HPR状态快照分代；未返回槽继续原代，不覆盖已完成缓存。"""
    yield work/'cache'
    for round_root in sorted((work/'rb').glob('*')):
        if round_root.is_dir():yield round_root/'capture'


def strategy_prior_plans(requests):
    """将已派发hot HPR纳入原跨日观察；只返回既存typed计划及其原工作根。"""
    seen=set()
    for root in strategy_history_roots(requests):
        origin,_=strategy_workflow(root)
        for plan_root in _plan_roots(origin/'work'):
            phase=plan_root/'PHASE-gap-plan.json'
            if not phase.exists():continue
            descriptor=_load(_descriptor(phase)).get('result')
            if descriptor is not None and descriptor['sha256']not in seen:
                seen.add(descriptor['sha256']);yield descriptor,plan_root/'gap-work'


def _plan_roots(work):
    """资格每版固定纯计划；旧已派发HPR仍全部交原责任发现与保护。"""
    yield from sorted(p for p in(work/'p').glob('*')if p.is_dir())


def _has_pending_slots(work,deadline=None,cancelled=lambda:False):
    for folder in _capture_roots(work):
        if cancelled():raise InterruptedError('strategy history slot observation stopped')
        if deadline is not None and time.monotonic()>=deadline:raise TimeoutError('strategy history slot observation deadline')
        if not(folder/'manifest.json').exists()and any((folder/'slots').glob('*.json')):return True
    for plan_root in _plan_roots(work):
        for slot in (plan_root/'gap-work'/'preparation').glob('*.json'):
            if cancelled():raise InterruptedError('strategy history HPR observation stopped')
            if deadline is not None and time.monotonic()>=deadline:raise TimeoutError('strategy history HPR observation deadline')
            observed=plan_root/'gap-work'/'observations'/slot.name
            if not observed.exists()or _load(_descriptor(observed))['row']['state']!='call_returned':return True
    return False


def _unfinished(work,deadline=None,cancelled=lambda:False):
    return _has_pending_slots(work,deadline,cancelled)or((work/'CAPTURE-REQUEST.json').exists()and not(work/'COMPLETE.json').exists())


def _coverage(cache,reference,calendar,policy,day,exceptions,deadline,cancelled):
    from guanheng_app.observation.calendars import official_calendar
    opens={r['date'].replace('-','')for r in official_calendar(calendar)[0]
        if r['is_open']==1 and policy['from']<=r['date'].replace('-','')<=day.replace('-','')}
    manifest=load_price_capture(cache);data={}
    for basis in ('none','front_ratio'):
        for _,items in price_batches(cache,manifest,adjustment=basis,deadline=deadline,cancelled=cancelled):
            for qmt,item in items.items():data.setdefault(qmt,{})[basis]=item
    results={}
    for symbol in policy['symbols']:
        if cancelled():raise InterruptedError('strategy history coverage stopped')
        if time.monotonic()>=deadline:raise TimeoutError('strategy history coverage deadline')
        exchange,code=symbol.split('.');qmt=code+'.'+{'SSE':'SH','SZSE':'SZ','BSE':'BJ'}[exchange]
        basic=reference.security(dict(basics={}),symbol)
        expected={d for d in opens if (basic['listed_on']is None or d>=basic['listed_on'].replace('-',''))
            and(basic['expires_on']is None or d<=basic['expires_on'].replace('-',''))
            and(symbol,d[:4]+'-'+d[4:6]+'-'+d[6:])not in exceptions}
        details={}
        for basis in ('none','front_ratio'):
            item=data[qmt][basis]
            known={d for d,bar in item['data'].items()if original_price_quality(bar)=='qualified'}
            details[basis]=dict(
                state=item['status'],  # 原Source该证券/口径状态，不由空价格推造unsupported。
                missing_dates=sorted(expected-known),  # 官方开市且上市有效、排除明确证券停牌后的缺日YYYYMMDD。
                actual_rows=len(known))  # 本捕获内OHLC/数量字段合格实际行数，不授单位/PIT资格。
        results[symbol]=details
    return results


def prepare_strategy_history(request,directory,*,deadline,cancelled,environ=None):
    """完整窗口捕获→原gap/HPR→实回读；返回独立不可变观察描述符。

    调用者持原publication租约，普通价格输入已经成功。所有Source/HPR沿原SDK；
    可选失败只返回本模块诊断。停止及原总D仍传播，预算耗尽保留原槽由同日后继续核。
    """
    policy=validate_strategy_history(request['policy']);root=Path(directory);root.mkdir(exist_ok=True)
    final=root/'RESULT.json'
    remaining=float(policy.get('seconds',120))
    @contextmanager
    def source_window():
        nonlocal remaining
        if cancelled():raise InterruptedError('strategy history stopped')
        if remaining<=0:raise TimeoutError('strategy history source budget')
        started=time.monotonic()
        try:yield min(deadline,started+remaining)
        finally:remaining=max(0,remaining-(time.monotonic()-started))
    context=dict(
        day=request['day'],  # 共同闭合市场日ISO格式，不以接收时刻推进。
        reference=request['reference'],  # 固定资料原件，上市/到期日期未知继续保留未知。
        calendar=request['calendar'],  # 固定官方日历及验证范围，不由行情反推交易日。
        connections=request['connections'],  # 原batch/HPR通信描述，凭据只通过环境引用。
        protected_slots=request['protected_slots'],  # 原未知读取/准备责任的完整路径。
        source_kind=request['source_kind'],  # actual-qmt与合成来源明确区分。
        snapshot_id=request['snapshot_id'])  # 调用方冻结旧发布身份，非Source catalog_id。
    business=hashlib.sha256(encode(dict(symbols=policy['symbols'],first=policy['from'],day=request['day'],
        connections=request['connections'],source_kind=request['source_kind']))).hexdigest()
    request_path=root/'REQUEST.json'
    if request_path.exists():bound=_load(_descriptor(request_path))
    else:
        workflow=None
        for previous in reversed(strategy_history_roots(request.get('previous_requests',()))):
            origin,original=strategy_workflow(previous)
            if original['business_key']==business and _unfinished(origin/'work',deadline,cancelled):
                workflow=_descriptor(origin/'REQUEST.json');break
        bound=dict(
            schema='guanheng.strategy-history-request.v1',  # Data owner子工作流，不是daily阶段完成证明。
            business_key=business,  # 同证券/窗口/闭合日/来源路由的规范SHA，观察预算不重置Source身份。
            policy=policy,  # 固定显式symbols/from及来源seconds预算、证券例外描述符。
            context=context,  # 首次来源派发所用资料/日历/通信/保护引用。
            workflow=workflow)  # 后继续核指向首个原REQUEST；首次为None，引用保持单层。
        _save(request_path,bound)
    if bound['business_key']!=business or bound['policy']!=policy or bound['context']!=context:
        raise ValueError('strategy history original intent differs')
    if final.exists():return _descriptor(final)
    origin,original=strategy_workflow(root);work=origin/'work';work.mkdir(exist_ok=True)
    source_context=original['context'];original_policy=original['policy'];cache=None;coverage={};plan=None;progress=None
    # 本次规范事实与旧Source请求分别持有身份，晚到官方纠正不被首次上下文吞掉。
    qualification=dict(
        calendar=context['calendar'],  # 本修订准入官方日历，旧来源UUID不随修订改变。
        reference=context['reference'],  # 本修订上市/到期资料，未提升来源价格资格。
        trading_exceptions=policy.get('trading_exceptions'))  # 本修订证券例外原件；None保留无已知例外。
    state='pending_source';reason=None;continuation=True
    try:
        if cancelled():raise InterruptedError('strategy history stopped')
        calendar=_load(context['calendar'])
        if not calendar['coverage_start'].replace('-','')<=original_policy['from']<=context['day'].replace('-','')<=calendar['coverage_end'].replace('-',''):
            state='calendar_pending';reason='official_calendar_outside_strategy_window'
        else:
            from guanheng_app.observation.calendars import official_calendar
            needed=sum(r['is_open']==1 and original_policy['from']<=r['date'].replace('-','')<=context['day'].replace('-','')
                for r in official_calendar(calendar)[0])
            if needed<1:raise ValueError('strategy history no calendar dates')
            capture_request=work/'CAPTURE-REQUEST.json'
            if not capture_request.exists():
                _save(capture_request,dict(
                    schema='qab.request-plan.v1',  # 原批读Source合同，两口径由原SDK捕获。
                    capture_id=str(uuid.uuid4()),  # 派发前一次固定；截止/换代后保留原UUID。
                    source_kind=context['source_kind'],  # 实际来源或合成来源标识。
                    symbols=sorted(s.split('.')[1]+'.'+{'SSE':'SH','SZSE':'SZ','BSE':'BJ'}[s.split('.')[0]]for s in original_policy['symbols']),  # 原QMT规范代码。
                    start_date=original_policy['from'],  # 策略授权YYYYMMDD起日；上市前由资料排除。
                    end_date=context['day'].replace('-',''),  # 闭合市场日YYYYMMDD，包含当日。
                    max_rows=needed))  # 官方日历实际开市日数，来源profile决定请求分片/资源拒绝。
            capture=_load(_descriptor(capture_request))
            # 先收束原未封存回读；即使HPR状态后来改变，旧代未知请求也保持其原身份。
            for previous_capture in _capture_roots(work):
                previous_request=previous_capture.parent/'REQUEST.json'
                if (previous_capture==work/'cache'or not previous_request.exists()
                        or(previous_capture/'manifest.json').exists()):continue
                with source_window()as source_deadline:
                    capture_price_window(_load(_descriptor(previous_request)),previous_capture,
                        source_context['connections']['batch'],deadline=source_deadline,cancelled=cancelled,
                        environ=environ,verify_resources=True)
            with source_window()as source_deadline:
                cache=capture_price_window(capture,work/'cache',source_context['connections']['batch'],deadline=source_deadline,
                    cancelled=cancelled,environ=environ,verify_resources=True)
            exceptions=load_trading_exceptions(policy.get('trading_exceptions'))
            reference=SecurityReference(context['reference'],context['calendar'])
            try:
                coverage=_coverage(cache,reference,calendar,policy,context['day'],exceptions,deadline,cancelled)
                missing=any(d['missing_dates']for row in coverage.values()for d in row.values())
                if missing:
                    from .daily_gap_update import prepare_gap_plan,advance_gap_plan,freeze_gap_progress
                    from .daily_gap_plan import restore_gap_plan,load_gap_plan
                    from .daily_data_stages import prepare_directory
                    from .source_history_transport import BoundHistorySource
                    from guanheng_qmt_shm.market_daily_preparation import MarketDailyPreparation
                    snapshot=dict(snapshot_id=hashlib.sha256(encode(dict(source=original,qualification=qualification))).hexdigest(),
                        observation_date=context['day'],basics={})
                    plan_root=work/'p'/hashlib.sha256(encode(qualification)).hexdigest()[:32]
                    plan_root.mkdir(parents=True,exist_ok=True)
                    plan_context_path=plan_root/'CONTEXT.json'
                    if not plan_context_path.exists():
                        protected=set(context['protected_slots'])
                        for previous_plan in _plan_roots(work):
                            protected.update(str(p)for p in(previous_plan/'gap-work/preparation').glob('*.json'))
                        _save(plan_context_path,dict(
                            qualification=qualification,  # 纯计划所用规范事实版本，不能复用较旧停牌/上市规则。
                            protected_slots=sorted(protected)))  # 生成前全部已派发旧HPR责任；后继恢复保持原路径。
                    plan_context=_load(_descriptor(plan_context_path))
                    if plan_context['qualification']!=qualification:raise ValueError('strategy history plan qualification differs')
                    def restore(output):return restore_gap_plan(output/'PLAN.json',capture=cache,snapshot_id=snapshot['snapshot_id'],
                        authorized_from=original_policy['from'],authorized_to=context['day'].replace('-',''),
                        protected_slots=plan_context['protected_slots'],deadline=deadline,cancelled=cancelled)
                    plan=prepare_directory(plan_root,'gap-plan','PLAN.json',lambda output:prepare_gap_plan(cache,reference,snapshot,output,
                        protected_slots=plan_context['protected_slots'],authorized_from=original_policy['from'],authorized_to=context['day'].replace('-',''),
                        deadline=deadline,cancelled=cancelled,trading_exceptions=exceptions),restore,recover_prior=True)
                    value=load_gap_plan(plan,deadline=deadline,cancelled=cancelled)
                    if value['tasks']:
                        batch=BoundHistorySource(context['connections']['batch'],environ=environ,reuse_connections=True)
                        try:
                            owner=MarketDailyPreparation(lambda:BoundHistorySource(context['connections']['hpr'],environ=environ,reuse_connections=True),batch,concurrency=4)
                            with source_window()as source_deadline:
                                progress=advance_gap_plan(plan,plan_root/'gap-work',owner,deadline=source_deadline,
                                    max_tasks=len(value['tasks']),cancelled=cancelled)
                        finally:batch.close()
                        frozen_value=freeze_gap_progress(plan,progress,plan_root/'gap-work'/'observations',deadline=deadline,cancelled=cancelled)
                        # 晚到HPR返回必须触发新的真实回读；原pending代所有槽继续保护和原ID续核。
                        rounds=work/'rb';rounds.mkdir(exist_ok=True)
                        # 目录只用128位前缀缩短Windows路径；正文逐字核同，碰撞明确失败。
                        round_root=rounds/hashlib.sha256(encode(frozen_value)).hexdigest()[:32];round_root.mkdir(exist_ok=True)
                        frozen=round_root/'PROGRESS.json'
                        if not frozen.exists():_save(frozen,frozen_value)
                        elif _load(_descriptor(frozen))!=frozen_value:raise ValueError('strategy history readback progress differs')
                        readback=round_root/'REQUEST.json'
                        if not readback.exists():_save(readback,dict(capture,max_rows=needed,capture_id=str(uuid.uuid4())))
                        with source_window()as source_deadline:
                            cache=capture_price_window(_load(_descriptor(readback)),round_root/'capture',context['connections']['batch'],
                                deadline=source_deadline,cancelled=cancelled,environ=environ,verify_resources=True)
                        coverage=_coverage(cache,reference,calendar,policy,context['day'],exceptions,deadline,cancelled)
                complete=not any(d['missing_dates']for row in coverage.values()for d in row.values())
                pending=(progress is not None and any(r['state']in('pending','source_unavailable','unattempted')for r in progress['rows']))or _has_pending_slots(work,deadline,cancelled)
                state='ready'if complete and not pending else'pending_source'if pending else'observed_partial'
                continuation=pending or not complete
                if not pending:_save(work/'COMPLETE.json',dict(state=state))
            finally:reference.close()
    except PriceWindowResource as error:state='resource_pending';reason=str(error)
    except (TimeoutError,InterruptedError) as error:
        if cancelled()or time.monotonic()>=deadline:raise
        state='source_budget_pending';reason=type(error).__name__
    except Exception as error:
        from .source_history_transport import SourcePending
        from guanheng_qmt_shm.read_retention_client import RetainedReadPending,RetainedReadFailure,RetainedReadBindingChanged
        state='pending_source'if isinstance(error,(SourcePending,RetainedReadPending,RetainedReadFailure,RetainedReadBindingChanged))else'invalid_optional_history'
        reason=type(error).__name__;continuation=state=='pending_source'
    if cache is None:
        for capture_root in reversed(list(_capture_roots(work))):
            if (capture_root/'manifest.json').exists():
                descriptor=dict(directory=str(capture_root.absolute()),sha256=_descriptor(capture_root/'manifest.json')['sha256'])
                try:
                    manifest=load_price_capture(descriptor)
                    selection=work/'CAPTURE-REQUEST.json'if capture_root==work/'cache'else capture_root.parent/'REQUEST.json'
                    if manifest['request']!=_load(_descriptor(selection)):continue
                except (ValueError,OSError,KeyError,TypeError):
                    continue  # 无法绑定原请求的旧文件继续保留；可选结果不把它交给Native。
                cache=descriptor;break
    result=dict(schema='guanheng.strategy-history-observation.v1',  # 本次观察，不冒充每日阶段或Source完成。
        state=state,  # ready/来源等待/资源等待/日历缺口/明确无覆盖或无效。
        reason=reason,  # 固定原因码/异常类型，不含外部原文。
        continuation_required=continuation,  # 只控制原同日重试，原成功价格保持。
        request=_descriptor(request_path),  # 本次固定原意图。
        workflow=_descriptor(origin/'REQUEST.json'),  # 原Source/HPR工作流，续核不换UUID。
        qualification=qualification,  # 本次规范事实，和Source首次上下文分别保留。
        cache=cache,  # 已完整落盘的真实捕获；未封存为None。
        plan=plan,  # 实际有缺口才生成原typed计划；无请求时None。
        preparation=progress,  # 原HPR观察；返回不授覆盖。
        coverage=coverage)  # 逐证券两口径实际缺日/来源状态。
    _save(final,result);return _descriptor(final)
