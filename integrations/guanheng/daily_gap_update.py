"""数据侧原缓存缺口计划/分项推进；复用原HPR客户端，所有未知任务保持身份。"""
from datetime import date, datetime, timedelta
import hashlib
import math
from pathlib import Path
import time

from ..guanheng_market_client import strict_json
from .market_generation import read_fixed, encode
from .security_reference import SecurityReference


def _save(path, value):
    pending = path.with_suffix(path.suffix + '.pending')
    pending.write_bytes(encode(value))
    pending.replace(path)


def _day(value):
    return datetime.strptime(value, '%Y%m%d').date()


def prepare_gap_plan(capture, reference, snapshot, output, *, protected_slots=(), daily_facts=None,
                     authorized_from, authorized_to, deadline, required_adjustments=('none','front_ratio'),
                     required_from=None, cancelled=lambda:False):
    """输入为完成QAB根、已准入资料/股票池和授权日期，输出只表示需补缓存。

    capture含directory/sha256；保护slot按原业务身份读取，旧结果/消费状态不改。
    仅原HPR的重叠区间阻止新派发，普通批读未知责任另外登记、保持原身份。
    计划按交易日和实际共同日期计算；不将SDK返回或计划任务数当覆盖证据。
    required_adjustments默认保持原两口径共同日期；原价任务可显式只要求none。
    required_from按证券约束真正需要的原生尾部日期，不为已有完整旧档重下历史。
    """
    from guanheng_qmt_shm.analysis_batch_source import read_capture
    if (not callable(cancelled)or type(deadline)not in(int,float)or not math.isfinite(deadline)
            or type(required_adjustments)not in(tuple,list)):
        raise ValueError('daily gap requirements or finite deadline invalid')
    def check():
        if cancelled():raise InterruptedError('daily gap plan stopped')
        if time.monotonic() >= deadline:
            raise TimeoutError('daily gap plan deadline expired')
    check()
    if (type(capture) is not dict or set(capture) != {'directory', 'sha256'}
            or type(capture['directory']) is not str or not Path(capture['directory']).is_absolute()):
        raise ValueError('daily gap capture descriptor invalid')
    root = Path(capture['directory'])
    body = read_fixed(root / 'manifest.json', maximum=16777216, identity=capture['sha256'])
    manifest = read_capture(root)
    if manifest != strict_json(body):
        raise ValueError('daily gap capture changed')
    request = manifest['request']
    required_adjustments=tuple(required_adjustments)
    if (required_adjustments not in (('none',),('front_ratio',),('none','front_ratio'))
            or not callable(cancelled)):
        raise ValueError('daily gap price requirements invalid')
    if required_from is not None and (type(required_from)is not dict or not set(required_from)<=set(request['symbols'])):
        raise ValueError('daily gap per-security range invalid')
    first, last = _day(authorized_from), _day(authorized_to)
    if not _day(request['start_date']) <= first <= last <= _day(request['end_date']):
        raise ValueError('daily gap authorization differs')
    if last.isoformat() != snapshot['observation_date']:
        raise ValueError('daily gap target snapshot differs')
    for value in (required_from or {}).values():
        if type(value)is not str or not first<=_day(value)<=last:
            raise ValueError('daily gap per-security date invalid')
    if reference._calendar is None:
        raise ValueError('daily gap plan requires declared calendar')
    calendar = reference._calendar
    if not calendar['coverage_start'] <= first.isoformat() <= last.isoformat() <= calendar['coverage_end']:
        raise ValueError('daily gap plan outside calendar coverage')
    mappings = {'SH': 'SSE', 'SZ': 'SZSE', 'BJ': 'BSE'}
    securities = {}
    selected_dates={}
    if required_adjustments!=('none','front_ratio'):
        from .analysis_price_capture import price_batches
        for _,items in price_batches(capture,manifest,adjustment=required_adjustments[0],deadline=deadline,cancelled=cancelled):
            for symbol,item in items.items():selected_dates[symbol]=set(item['data'])
    for symbol in request['symbols']:
        code, market = symbol.split('.')
        identity = mappings[market] + '.' + code
        securities[symbol] = dict(identity=identity, basic=reference.security(snapshot, identity),
                                  dates=(set(manifest['comparison'][symbol]['common_dates'])
                                         if required_adjustments==('none','front_ratio')else selected_dates[symbol]))
    # 明确记录所有受保护业务请求；结果未知/已消费的旧未知均保持原ID。
    protected = []
    for path in protected_slots:
        check()
        slot = strict_json(read_fixed(path, maximum=1048576))
        original = slot['request']
        protected.append(dict(
            slot=str(Path(path).absolute()),  # 原持久slot绝对位置，结果和消费事实继续由原owner拥有。
            request_id=original['request_id'],  # 原UUID；本计划只引用，绝不改写或重新生成。
            operation_id=original['operation_id'],  # 原业务操作，HPR与普通批读责任分别处理。
            arguments=original['arguments'],  # 原证券/日期/截止参数，保留原值。
            request_sha256=hashlib.sha256(encode(original)).hexdigest()))  # 原请求语义摘要，不绑定后续消费状态。
    blocked = {}
    for item in protected:
        if item['operation_id'] == 'market.history_prepare' and item['arguments']['period'] == '1d':
            args = item['arguments']
            blocked.setdefault(args['symbol'], []).append((args['start_time'], args['end_time'], item['request_id']))
    gaps = {symbol: [] for symbol in securities}
    exclusions = []
    closed = set(calendar['closed_dates'])
    current = first;open_order={}
    while current <= last:
        check()
        iso, label = current.isoformat(), current.strftime('%Y%m%d')
        current += timedelta(days=1)
        if date.fromisoformat(iso).weekday() >= 5 or iso in closed:
            continue
        open_order[label]=len(open_order)
        for symbol, item in securities.items():
            if label<(required_from or {}).get(symbol,authorized_from):continue
            if label in item['dates']:
                continue
            basic = item['basic']
            if basic['listed_on'] is not None and iso < basic['listed_on']:
                reason = 'before_listing'
            elif basic['expires_on'] is not None and iso > basic['expires_on']:
                reason = 'after_expiry'
            elif any(start <= label <= end for start, end, _ in blocked.get(symbol, ())):
                reason = 'original_HPR_responsibility'
            else:
                state = daily_facts.security_state(iso, item['identity']) if daily_facts is not None else None
                if state is not None and state['qualification'] == 'qualified' and state['tradestatus'] == '0':
                    reason = 'source_halted_requires_quantity_or_original_history'
                else:
                    gaps[symbol].append(label)
                    continue
            exclusions.append(dict(
                symbol=symbol,  # 原QMT规范证券代码，与HPR参数一致。
                date=label,  # 授权窗口内未出现在共同缓存的市场日期YYYYMMDD。
                reason=reason))  # 业务排除/保护原因，均不作为已确认数据丢失。
    tasks = []
    for symbol, days in gaps.items():
        intervals = []
        for day in days:
            # 连续缺失交易日跨周末/官方休市保持同一次HPR；已缓存或保护日仍隔断区间。
            if intervals and open_order[day] == open_order[intervals[-1][-1]] + 1:
                intervals[-1].append(day)
            else:
                intervals.append([day])
        for days in intervals:
            tasks.append(dict(
                index=len(tasks),  # 固定零基任务索引，映射本任务根preparation/%06d.json。
                symbol=symbol,  # 原QMT证券身份，来源于原请求/股票池。
                start_date=days[0],  # 本次实际缓存缺口起日YYYYMMDD，含当日。
                end_date=days[-1],  # 缺口止日YYYYMMDD，含当日，未跨过已排除或已保护日期。
                dates=days,  # 原none/front_ratio共同日期中未出现的实际计划交易日。
                reason='calendar_expected_cache_gap'))  # 缓存缺口资格，不声称存在交易或数据丢失。
    value = dict(
        schema='guanheng.daily-gap-plan.v1',  # WT数据侧不可变缺口计划合同。
        capture=capture,  # 原已完成缓存及manifest SHA，旧根只读。
        snapshot_id=snapshot['snapshot_id'],  # 同日股票池、资料与日事实绑定的版本。
        authorized_from=authorized_from,  # 已授权可补日期起点YYYYMMDD。
        authorized_to=authorized_to,  # 已授权终点YYYYMMDD，与观察目标日一致。
        protected_requests=protected,  # 原未知责任完整引用，保留operation及UUID。
        tasks=tasks,  # 可独立推进的互不重叠HPR任务，调用返回不表示数据已齐。
        exclusions=exclusions)  # 业务和原责任排除日期，后续保留供审计。
    if required_adjustments!=('none','front_ratio')or required_from is not None:
        value.update(
            required_adjustments=list(required_adjustments),  # 本计划真正必需的缓存价格口径。
            required_from=required_from or {})  # 每证券已存在原生历史之后的闭合日边界。
    output = Path(output).absolute()
    output.mkdir(parents=False, exist_ok=False)
    path = output / 'PLAN.json'
    path.write_bytes(encode(value))
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def freeze_gap_progress(plan,progress,observations=None,*,deadline,cancelled=lambda:False):
    """固定本次回读前的全部计划状态；未推进项显式保存，恢复不会借较晚观察改写时点。

    observations为回读开始前仍由同一owner持有的原单项观察目录。恢复已有回读但
    缺完整状态时只采用已存进度，缺项保守标记unattempted，交后继修订重新实读。
    快照只保留状态及原请求ID；完整SDK记录继续由原slot/observations拥有。
    """
    from .daily_data_update import _load
    value=_load(plan);observed={}
    if progress is not None:
        if progress.get('plan_sha256')!=plan['sha256']:
            raise ValueError('daily readback progress plan differs')
        for row in progress['rows']:
            if row['index']in observed:raise ValueError('daily readback progress index repeated')
            observed[row['index']]=row
    tasks=value['tasks'];indices={task['index']for task in tasks}
    if len(indices)!=len(tasks)or not set(observed)<=indices:
        raise ValueError('daily readback progress indices differ')
    rows=[]
    for task in tasks:
        if cancelled():raise InterruptedError('daily readback progress stopped')
        if time.monotonic()>=deadline:raise TimeoutError('daily readback progress deadline')
        row=observed.get(task['index'])
        if row is None and observations is not None:
            path=Path(observations)/('%06d.json'%task['index'])
            if path.exists():
                original=strict_json(read_fixed(path,maximum=1048576))
                if original['plan_sha256']!=plan['sha256']or original['row']['index']!=task['index']:
                    raise ValueError('daily readback observation identity differs')
                row=original['row']
        state=row['state']if row is not None else'unattempted'
        if state not in('call_returned','pending','source_unavailable','unattempted'):
            raise ValueError('daily readback progress state invalid')
        item=dict(index=task['index'],state=state)  # 原计划索引与回读前状态，缺观察明确未推进。
        if row is not None and row.get('request_id')is not None:item['request_id']=row['request_id']  # 原未知请求UUID，不产生新身份。
        rows.append(item)
    return dict(
        schema='guanheng.daily-gap-readback-progress.v1',  # 完整时点快照，区别每次advance的稀疏增量。
        plan_sha256=plan['sha256'],  # 原不可变计划身份，防止配错回读责任。
        rows=rows)  # 每个计划索引恰好一项，包括未推进项；完整回读恢复时保持。


def advance_gap_plan(plan, directory, preparation_owner, *, deadline, max_tasks,
                     cancelled=lambda: False, on_progress=None, task_indices=None):
    """调用方持排他写锁；每项复用原执行器，Pending保留slot并让其他项推进。

    max_tasks为本轮观察条数，不改变原任务截止/UUID；取消在项间生效。
    原执行器关闭其有限客户端线程后才返回；Source SDK硬截止由外层Job拥有。
    """
    from guanheng_qmt_shm.market_daily_preparation import _original
    from guanheng_qmt_shm.market_daily_preparation_cli import _reason_code
    from guanheng_qmt_shm.read_retention_client import RetainedReadClient, RetainedReadPending, RetainedReadFailure
    from guanheng_qmt_shm_agent.history_preparation import OPERATION
    if (type(max_tasks) is not int or not 1 <= max_tasks <= 10000 or not callable(cancelled)
            or type(deadline) not in (int, float) or not math.isfinite(deadline)):
        raise ValueError('daily gap advancement budget invalid')
    value = strict_json(read_fixed(plan['path'], maximum=16777216, identity=plan['sha256']))
    if value.get('schema') != 'guanheng.daily-gap-plan.v1':
        raise ValueError('daily gap plan schema invalid')
    tasks = value['tasks']
    if task_indices is not None:
        if (type(task_indices) not in (tuple, list) or not task_indices or len(task_indices) != len(set(task_indices))
                or any(type(i) is not int or not 0 <= i < len(tasks) for i in task_indices)):
            raise ValueError('daily gap task selection invalid')
    directory = Path(directory).absolute()
    directory.mkdir(parents=False, exist_ok=True)
    _original(directory / 'PLAN-IDENTITY.json', plan)
    cursor = 0
    progress_file = directory / 'PROGRESS.json'
    if progress_file.exists():
        previous_progress = strict_json(read_fixed(progress_file, maximum=16777216))
        if previous_progress['plan_sha256'] != plan['sha256']:
            raise ValueError('daily gap progress plan differs')
        cursor = previous_progress['next_index']
        if type(cursor) is not int or not 0 <= cursor < max(1, len(tasks)):
            raise ValueError('daily gap progress cursor invalid')
    client = RetainedReadClient(preparation_owner.factory(), lifetime_ms=30000)
    try:
        metadata = preparation_owner._pinned(client, directory / 'HPR-BINDING.json', 'qmt.read-profile.v6', OPERATION, deadline)
        _original(directory / 'HPR-BINDING.json', metadata)
    finally:
        client.transport.close()
    scope = metadata['profile']['operation_profiles'][OPERATION]['limits']
    observations = directory / 'observations'
    observations.mkdir(exist_ok=True)
    rows = []
    ordered = [tasks[i] for i in task_indices] if task_indices is not None else tasks[cursor:] + tasks[:cursor]
    for task in ordered:
        if len(rows) >= max_tasks or cancelled() or time.monotonic() + 30 >= deadline:
            break
        observation = observations / ('%06d.json' % task['index'])
        if observation.exists():
            previous = strict_json(read_fixed(observation, maximum=1048576))
            if previous['plan_sha256'] != plan['sha256'] or previous['row']['index'] != task['index']:
                raise ValueError('daily gap observation identity differs')
            if previous['row']['state'] == 'call_returned':
                continue  # 已返回原任务保留单项凭据，后续只实读缓存，不再执行SDK准备。
        slot = directory / 'preparation' / ('%06d.json' % task['index'])
        try:
            records = preparation_owner._prepare_items([(task['index'], task['symbol'], task['start_date'], task['end_date'], slot)],
                directory, metadata, scope, deadline, None, len(value['tasks']), minimum_new_request_seconds=30)
            row = dict(index=task['index'], state='call_returned', record=records[0], coverage='unknown')
        except (RetainedReadPending, RetainedReadFailure) as error:
            original = strict_json(read_fixed(slot, maximum=1048576)) if slot.exists() else None
            row = dict(
                index=task['index'],  # 原计划任务索引，续核不变。
                state='pending' if isinstance(error, RetainedReadPending) else 'source_unavailable',  # 原客户分类。
                reason_code=_reason_code(error),  # 原固定原因码，未知异常正文不输出。
                slot=str(slot) if original is not None else None,  # 已有持久责任位置；未准入时None。
                request_id=original['request']['request_id'] if original is not None else None,  # 保留原请求身份。
                coverage='unknown')  # 只有后续真实批读才判断数据覆盖。
        rows.append(row)
        cursor = (task['index'] + 1) % max(1, len(tasks))
        _save(observation, dict(plan_sha256=plan['sha256'], row=row))
        _save(directory / 'PROGRESS.json', dict(schema='guanheng.daily-gap-progress.v1', plan_sha256=plan['sha256'],
            state='observing', next_index=cursor, rows=rows, coverage='unconfirmed_until_readback'))
        if on_progress is not None:
            on_progress(row)
    result = dict(
        schema='guanheng.daily-gap-progress.v1',  # 本轮分项观察结果，与原源端执行状态分别保存。
        plan_sha256=plan['sha256'],  # 不可变计划身份，同目录恢复必须一致。
        next_index=cursor,  # 下一轮从该计划索引继续，原Pending每轮最多续核一次，其他项持续推进。
        state='stopped' if cancelled() else 'observed',  # 仅描述外部本轮生命周期，未声称计划全部完成。
        rows=rows,  # 本轮实际核查/调用的原身份及固定结果。
        coverage='unconfirmed_until_readback')  # SDK准备返回独立于缓存内容覆盖。
    _save(directory / 'PROGRESS.json', result)
    return result
