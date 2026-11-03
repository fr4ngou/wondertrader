"""MDP显式缓存优先编排；资格版本沿原T2108/2，SDK/slot/重试仍归原实现。"""
from datetime import datetime,timedelta,timezone
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import time
import uuid

from guanheng_qmt_shm_agent.protocol import decode
from guanheng_qmt_shm_agent.history_preparation import OPERATION
from .analysis_batch_source import read_capture
from .market_daily_preparation import _load, _original
from .read_retention_client import RetainedReadClient,RetainedReadFailure,RetainedReadPending,_save

SCHEMA='guanheng.market-daily-preparation.v2'  # 新请求/流程结果协议版本；v1仍由原入口独立恢复。
QUALIFICATION='t2108.ashare/2'  # 原消费口径版本；40期含当期，不授因果/因子独立验证资格。
MIN_ROWS=40  # 实际前复权收盘记录数，来源为原T2108/2固定定义，不是证券池或配置额度。
_FIELDS={'open','high','low','close','volume','amount'}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _day(value):
    if type(value)is not str or re.fullmatch('[0-9]{8}',value)is None:raise ValueError('market_daily_cache_date')
    return datetime.strptime(value,'%Y%m%d').date()


def _shift(value,days):
    return (_day(value)+timedelta(days=days)).strftime('%Y%m%d')


def assess(directory):
    """只读原完整批次；原日期/实收/绑定保留，返回逐证券实际资格，不请求来源。

    持久QUALITY各字段单位、来源时点与空值见唯一规格MDP6字段表。
    调用线程持有返回纯值；这里不计算指标，不改变原批次或消费事实。
    """
    manifest=read_capture(directory);request=manifest['request'];first,last=request['start_date'],request['end_date'];_day(first);_day(last)
    data={s:{}for s in request['symbols']}
    for batch in manifest['batches']:
        slot=_load(Path(directory)/batch['slot']);native=decode(base64.b64decode(slot['result']['result_body_b64'],validate=True))
        for symbol,item in native['data']['securities'].items():
            values=item['data'];dates=sorted(values)
            if item['status']!='observed' and values:raise ValueError('market_daily_cache_status')
            if symbol not in data or batch['adjustment'] in data[symbol]:raise ValueError('market_daily_cache_projection')
            if len(dates)>request['max_rows']:raise ValueError('market_daily_cache_rows')
            for day,bar in values.items():
                _day(day)
                if not first<=day<=last or type(bar)is not dict or set(bar)!=_FIELDS:raise ValueError('market_daily_cache_data')
                if any(type(v)not in (int,float)or (not math.isfinite(v)or v<0)for v in bar.values()):raise ValueError('market_daily_cache_data')
            data[symbol][batch['adjustment']]=dict(
                status=item['status'],  # 原v8该证券状态；observed也须实际有行才具备数据。
                dates=dates,  # 原SDK返回的有序市场日YYYYMMDD；空数组表示本次没有缓存行。
                closes={d:values[d]['close']for d in dates},  # 当次指定复权模式的原收盘价；零值保留供资格判断。
                received_at=batch['received_at'])  # 原批次实收时间（带时区字符串），沿原receipt而非本地评估时间。
    rows={};counts={k:0 for k in [
        'eligible',  # 合格证券数（只）：目标日存在且最后40条原前复权收盘均为正。
        'missing',  # 来源状态非observed或没有缓存行的证券数（只）；不等同运输未知。
        'stale',  # 有前复权行但没有目标观察日的证券数（只），仍保留真实缓存尾日。
        'insufficient',  # 已有目标日但前复权实际记录不足40条的证券数（只）。
        'nonpositive',  # 已有目标日和40条记录，但最后40条含非正收盘的证券数（只）。
        'source_unavailable']}  # 来源原状态invalid/requires_partition的证券数（只）；不以HPR绕过。
    for symbol,pair in data.items():
        if set(pair)!={'none','front_ratio'}:raise ValueError('market_daily_cache_adjustments')
        front=pair['front_ratio'];dates=front['dates'];closes=front['closes'];recent=dates[-MIN_ROWS:]
        common=sorted(set(pair['none']['dates'])&set(dates))
        expected=dict(
            common_dates=common,  # 原none/front_ratio共同市场日YYYYMMDD，空数组表示没有共同记录。
            basis=common[-1]if common else None,  # 共同日期尾日；None表示没有共同日，运输未知沿原Pending返回；不代表复权因子已验。
            rows=len(common),  # 共同日期记录数（条）；0仅表示没有共同记录。
            at_least_40=len(common)>=40,  # 共同记录数量是否达到40条；与前复权最终资格分别判断。
            adjustment_qualified=False,  # 原包没有独立因子资格证明；保留原声明，不由HPR返回升级。
            closed_basis_qualified=False,  # 原包没有独立闭合基准资格证明；共同尾日不提供此项证明。
            factors='not_requested')  # 原捕获未请求复权因子；不以空值或价格比推造因子。
        if manifest['comparison'][symbol]!=expected:raise ValueError('market_daily_cache_basis_identity')
        if front['status']in ('invalid','requires_partition'):reason='source_unavailable'
        elif front['status']!='observed'or not dates:reason='missing'
        elif last not in closes:reason='stale'
        elif len(dates)<MIN_ROWS:reason='insufficient'
        elif any(closes[d]<=0 for d in recent):reason='nonpositive'
        else:reason='eligible'
        counts[reason]+=1
        # 每项为原捕获的实际行与时间；参考尾日是SDK请求end_date，不伪造因子资格。
        rows[symbol]=dict(
            reason=reason,  # 按原T2108顺序产生的互斥原因；描述此捕获数据，未表示HPR调用阶段。
            eligible=reason=='eligible',  # 此证券本次数据是否满足目标日及最后40条正收盘；False保留具体原因。
            status=front['status'],  # 原v8前复权证券状态；来源状态与本地reason分别保存。
            rows=len(dates),  # 实际前复权市场日记录数（条）；0表示没有行，不是未知记录数。
            first_date=dates[0]if dates else None,  # 原前复权首日YYYYMMDD；无行时None。
            last_date=dates[-1]if dates else None,  # 原前复权尾日YYYYMMDD；无行时None，不填目标日。
            bad_close_dates=[d for d in recent if closes[d]<=0],  # 最后至多40条中的非正收盘日；空数组表示未发现此类值。
            warmup_insufficient=len(dates)<MIN_ROWS,  # 实际前复权行数不足40条；新股等业务事实仍由原消费链解释。
            source_received_at=front['received_at'],  # 原front_ratio receipt实收时刻（带时区），不使用评估/封存时间。
            adjustment='front_ratio',  # 本资格使用原QMT前复权序列；未新增复权计算算法。
            reference_end_date=last,  # 原SDK请求end_date（YYYYMMDD），表示请求参考尾日，不保证数据已到该日。
            original_common_basis=manifest['comparison'][symbol]['basis'])  # 原none/front共同尾日；None表示无共同日，因子资格仍未授予。
    return dict(
        schema='guanheng.market-daily-cache-quality.v1',  # 本地质量索引格式；初读与回读共用此结构。
        qualification=QUALIFICATION,  # 原T2108/2数据口径版本；不表示SDK/准备阶段完成。
        observation_date=last,  # 业务观察目标日YYYYMMDD，沿原capture.end_date。
        minimum_rows=MIN_ROWS,  # 固定40条实际前复权记录（含当期），来源为原消费口径。
        securities=len(rows),  # 本次请求证券总数（只），包含不合格证券。
        counts=counts,  # 各互斥原因对应证券数（只）；零表示该原因下没有证券，合计等于securities。
        eligible_count=counts['eligible'],  # 本次实读合格证券数（只）；0沿原不可用类处理，不表示未知。
        full_coverage=counts['eligible']==len(rows),  # 全部请求证券均合格；部分覆盖保留False及各证券原因。
        rows=rows,  # 证券代码到上述实际质量记录的完整映射；每只请求证券均有一项。
        capture_sha256=_sha(Path(directory)/'manifest.json'))  # 当前被评估原manifest完整字节SHA256，绑定质量来源。



def _plan(quality,request):
    """仅计划授权范围内缺口；暖机/尾日/坏值最多三个区间，交原单证券HPR。"""
    lower,upper=request['preparation']['start_date'],request['preparation']['end_date'];tasks=[]
    for symbol in request['capture']['symbols']:
        row=quality['rows'][symbol];ranges=[]
        if row['eligible']or row['reason']=='source_unavailable':continue
        if not row['first_date']:ranges=[(lower,upper,'missing')]
        else:
            if row['warmup_insufficient']:ranges.append((lower,_shift(row['first_date'],-1),'warmup'))
            if row['last_date']<upper:ranges.append((_shift(row['last_date'],1),upper,'tail'))
            if row['bad_close_dates']:ranges.append((min(row['bad_close_dates']),max(row['bad_close_dates']),'nonpositive'))
        merged=[]
        for start,end,reason in sorted(ranges):
            start,end=max(start,lower),min(end,upper)
            if start>end:continue
            if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]),'combined')
            else:merged.append((start,end,reason))
        for start,end,reason in merged:
            # index固定原slot名；证券、起止日为业务授权值，deadline由原执行器首次准入固定。
            tasks.append(dict(
                index=len(tasks),  # 零基任务序号，固定映射preparation/%06d.json；同根恢复时保持原slot身份。
                symbol=symbol,  # 原请求证券代码；同一证券可有多个不相交缺口任务，任务数不等于证券数。
                start_date=start,  # 本缺口允许准备的起日YYYYMMDD（含），由真实缓存缺口与授权窗口相交取得。
                end_date=end,  # 本缺口允许准备的止日YYYYMMDD（含）；不是SDK执行截止时刻。
                reason=reason))  # missing/warmup/tail/nonpositive/combined描述初次缓存缺口，不证明HPR或回读已完成。
    return dict(
        schema='guanheng.market-daily-cache-plan.v1',  # 固定缺口计划格式，属于本次新观察目录。
        qualification=QUALIFICATION,  # 生成缺口时使用的原T2108数据口径版本。
        cache_sha256=quality['capture_sha256'],  # 初次原v8 manifest字节摘要；恢复时不会换成后续回读摘要。
        tasks=tasks)  # 固定有限任务数组；空数组表示无需可执行的HPR缺口，仍需看QUALITY判数据资格。


def run_cache_first(owner,request,directory,*,deadline,max_preparations,on_progress,connection_identity):
    """同一原MDP owner，单次总D；不创建服务，不改变原HPR/批读恢复规则。"""
    if type(deadline)not in (int,float):raise ValueError('market_daily_finite_deadline')
    try:finite=math.isfinite(deadline)
    except OverflowError:finite=False
    if not finite:raise ValueError('market_daily_finite_deadline')
    if set(request)!={
        'schema',  # 新请求协议版本v2；只由原MDP.run显式分派，不迁移v1原目录。
        'mode',  # 新必填编排选择cache-first；决定先实读缓存，未声明数据已齐或已准备。
        'capture',  # 原v8捕获请求对象：证券/日期/行额度/来源及捕获ID，原单位与语义保持。
        'preparation',  # 原HPR可准备日期授权窗口（YYYYMMDD，含起止日）；不是要求全窗下载。
        'source_association',  # 原材料冻结的来源/连接摘要关联；不能替代当前绑定或本轮实收凭证。
    }or request['mode']!='cache-first'or type(request['source_association'])is not dict:raise ValueError('market_daily_cache_request')
    # request.source_association：准备材料冻结的来源/连接摘要关联对象；沿原请求保存，不能替代本轮signed binding或实收receipt。
    capture=request['capture'];symbols=capture['symbols'];prep=request['preparation']
    if type(symbols)is not list or not symbols or len(set(symbols))!=len(symbols):raise ValueError('market_daily_symbols')
    if set(prep)!={'start_date','end_date'}or not _day(capture['start_date'])<=_day(prep['start_date'])<=_day(prep['end_date'])==_day(capture['end_date']):raise ValueError('market_daily_cache_authorization')
    if max_preparations is not None and(type(max_preparations)is not int or max_preparations<1):raise ValueError('market_daily_request')
    if connection_identity is not None and type(connection_identity)is not dict:raise ValueError('market_daily_connection_identity')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);_original(directory/'REQUEST.json',request)
    config=directory/'CONNECTIONS.json'
    if connection_identity is not None:_original(config,connection_identity)
    elif config.exists():raise ValueError('market_daily_connection_identity_required')
    completed=directory/'RESULT.json'
    if completed.exists():
        result=_load(completed);read_capture(directory/result['capture'])
        if _sha(directory/result['capture']/'manifest.json')!=result['capture_sha256']or _sha(directory/'QUALITY.json')!=result['quality_sha256']:raise ValueError('market_daily_completed_capture_digest')
        owner._verify_preparations(directory,result['preparations'])
        return result
    if time.monotonic()>=deadline:raise RetainedReadPending('market_daily_workflow_deadline')
    batch_binding=directory/'cache/BINDING.json';batch=owner._pinned(owner.batch.client,batch_binding,'qmt.read-profile.v8','market.market_data',deadline);_original(batch_binding,batch)
    cache_request=dict(capture,
        capture_id=str(uuid.uuid5(uuid.UUID(capture['capture_id']),'cache-first-observation')))  # 由原外层capture_id确定性派生的初读ID；与最终回读ID分开，同根恢复不换身份。
    cache=directory/'cache'
    if not(cache/'manifest.json').exists():owner.batch.capture(cache_request,cache,deadline=deadline)
    quality=assess(cache);_original(directory/'CACHE-QUALITY.json',quality);plan=_plan(quality,request);_original(directory/'PLAN.json',plan)
    tasks=plan['tasks'];records=[]
    if tasks:
        client=RetainedReadClient(owner.factory(),lifetime_ms=30000);binding_file=directory/'HPR-BINDING.json';metadata=owner._pinned(client,binding_file,'qmt.read-profile.v6',OPERATION,deadline)
        scope=metadata['profile']['operation_profiles'][OPERATION]['limits']
        if scope['schema_version']!='qmt.history-preparation-limits.v3':raise ValueError('market_daily_explicit_hpr_v3_required')
        _original(binding_file,metadata)
        existing=[t for t in tasks if(directory/'preparation'/('%06d.json'%t['index'])).exists()];fresh=[t for t in tasks if t not in existing]
        selected=existing+fresh[:max_preparations]if max_preparations is not None else tasks
        items=[(t['index'],t['symbol'],t['start_date'],t['end_date'],directory/'preparation'/('%06d.json'%t['index']))for t in selected]
        records=owner._prepare_items(items,directory,metadata,scope,deadline,on_progress,len(tasks))
        if len(records)!=len(tasks):
            progress=dict(
                schema=SCHEMA,  # v2流程进度格式；不重标旧v1进度。
                state='paused',  # 本阶段新准备额度已用完；全计划/最终回读尚未完成。
                securities=len(symbols),  # 原请求证券总数（只），不是已准备任务数。
                preparations=records,  # 原HPR已确认call_returned且consumed的任务记录；不作为数据覆盖证明。
                required_preparations=len(tasks),  # 固定PLAN缺口区间总数（项），同一证券可能占多项。
                cache_eligible_count=quality['eligible_count'])  # 初次实读已合格证券数（只），不是本阶段后的最终资格。
            _save(directory/'PROGRESS.json',progress);return progress
        final=directory/'capture';final_binding=final/'BINDING.json';_original(final_binding,batch)
        owner._pinned(owner.batch.client,batch_binding,'qmt.read-profile.v8','market.market_data',deadline)
        if not(final/'manifest.json').exists():owner.batch.capture(capture,final,deadline=deadline)
    else:final=cache  # 无副作用时初次实际缓存捕获即最终观察，避免重复SDK读取。
    quality=assess(final);_original(directory/'QUALITY.json',quality)
    if quality['eligible_count']==0:raise RetainedReadFailure('market_daily_cache_no_qualified_observations')
    result=dict(
        schema=SCHEMA,  # 新v2流程结果格式；与旧v1原件分开。
        state='completed',  # 本次计划责任和最终实读已封存；部分数据覆盖仍可能存在。
        mode='cache-first',  # 本观察显式选择的编排模式，不授予独立行情/因子资格。
        preparations=records,  # 原HPR已确认且consumed的任务记录；无需准备时为空数组，不表示没有市场数据。
        capture=final.relative_to(directory).as_posix(),  # 最终原捕获的相对目录cache或capture；无HPR时复用本次初读。
        capture_sha256=_sha(final/'manifest.json'),  # 最终原manifest完整字节SHA256，绑定结果与实际捕获。
        quality_sha256=_sha(directory/'QUALITY.json'),  # 最终QUALITY原件完整字节SHA256，绑定本地数据资格索引。
        securities=len(symbols),  # 请求全池证券数（只），包含所有实际缺失/过期/不足期证券。
        batches=len(read_capture(final)['batches']),  # 最终捕获的原v8批次结果数（份），none/front分别计数；不是HPR调用数。
        source_kind=capture['source_kind'],  # 沿原捕获请求的actual-qmt或sdk-synthetic来源标记，二者证据资格分别保留。
        generated_at=datetime.now(timezone.utc).isoformat(),  # 本地结果封存UTC时刻；不替代Source实收时刻或市场观察日。
        coverage_qualified=quality['full_coverage'],  # 全池每只证券按实际回读均合格才为True；completed不隐含该条件。
        eligible_count=quality['eligible_count'],  # 最终实读合格证券数（只）；此结果只在至少1只合格时生成。
        required_preparations=len(tasks),  # 初次固定PLAN的缺口区间总数（项）；无缺口为0，不是证券数。
        qualification=QUALIFICATION)  # 本次数据资格使用的原T2108/2口径版本，仍由原消费入口验证/计算指标。
    _save(completed,result);return result
