"""WT数据更新的原输入生产者；复用唯一公开事实适配器和原QMT批读通道。"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace
import uuid

from .daily_data_update import _save, _load, _descriptor
from .market_generation import read_fixed, read_generation
from ..guanheng_market_client import strict_json


def observe_prior_plans(plans, owner, *, deadline, cancelled):
    """旧来源换代/暂不可达时保留原责任，继续其他计划及本轮缓存读取。"""
    from guanheng_qmt_shm.read_retention_client import RetainedReadPending, RetainedReadFailure
    from .source_history_transport import SourcePending
    from .daily_gap_update import advance_gap_plan
    observations=[]
    for plan, work, indices in plans:
        if cancelled():
            raise InterruptedError('daily prior observation stopped')
        if time.monotonic()>=deadline:
            raise TimeoutError('daily prior observation deadline')
        try:
            result=advance_gap_plan(plan,work,owner,deadline=deadline,max_tasks=10000,
                                    task_indices=indices,cancelled=cancelled)
            for row in result['rows']:
                if row['state'] in ('pending','source_unavailable'):
                    observations.append(dict(
                        plan_sha256=plan['sha256'],  # 原不可变计划身份，与分项观察凭据一致。
                        state=row['state'],  # 原执行器逐项等待/暂不可达结果，不赋予覆盖资格。
                        task_indices=[row['index']],  # 本次实际观察的原计划索引。
                        reason_code=row['reason_code'],  # 原固定原因码，无来源异常正文。
                        slot=row['slot'],  # 原持久责任路径；未准入时保持None。
                        request_id=row['request_id'],  # 原请求身份；续核不产生新身份。
                        coverage=row['coverage']))  # 准备状态与真实缓存覆盖分别记录。
        except (RetainedReadPending,RetainedReadFailure,SourcePending) as error:
            observations.append(dict(
                plan_sha256=plan['sha256'],  # 原不可变计划身份，原请求/slot继续保持。
                state='original_responsibility_unavailable',  # 原来源暂不可续核，不授新请求或覆盖资格。
                error_type=type(error).__name__,  # 固定异常分类，无来源原文或凭据。
                task_indices=list(indices)))  # 只记录已有原slot的索引，其他证券由本轮计划处理。
    return observations


def prepare_update(configuration, day, directory, *, deadline, cancelled=lambda: False,
                   environ=None, previous_requests=()):
    """调用方持publication锁；同目录输入请求及原slot固定，恢复不改capture_id。

    configuration.template为单轮更新静态配置，inputs为公开事实/原批读的有限预算。
    日事实、股票池、原缓存都实际保存后才写UPDATE.json；其摘要供单轮owner固定。
    旧任务的原HPR槽全部加入保护；只有已有未返回槽由原执行器续核。
    """
    from .day_facts_capture import capture_day_facts
    from .day_facts_prepare import extend_facts_catalog
    from .source_history_transport import BoundHistorySource
    from .daily_data_stages import prepare_directory
    from guanheng_app.observation.storage import ContentStore, SnapshotRepository
    from guanheng_app.observation.source_fetch import Fetcher, CollectionBudget, BoundedContentStore
    from guanheng_qmt_shm.analysis_batch_source import BatchAnalysisSource
    from guanheng_qmt_shm.market_daily_preparation import MarketDailyPreparation

    def check():
        if cancelled():
            raise InterruptedError('daily inputs stopped')
        if time.monotonic() >= deadline:
            raise TimeoutError('daily inputs deadline expired')

    root = Path(directory).absolute()
    root.mkdir(parents=False, exist_ok=True)
    intent = root / 'INPUTS.json'
    bound = dict(configuration=configuration, day=day, previous_requests=list(previous_requests))
    if intent.exists():
        if strict_json(read_fixed(intent, maximum=16777216)) != bound:
            raise ValueError('daily input original configuration differs')
    else:
        _save(intent, bound)
    final = root / 'UPDATE.json'
    if final.exists():
        return _descriptor(final)
    check()
    template = deepcopy(configuration['template'])
    inputs = configuration['inputs']
    # 运行指针只贡献成功日事实和上次原生版本；固定基准/旧价格根持续保留。
    current = Path(template['publication_directory']) / 'CURRENT.json'
    if current.exists():
        current_value, _ = read_generation(current)
        current_config = _load(current_value['configuration'], 1048576)
        template['daily_facts'] = current_config['daily_facts']
        base = current_config['base'];additional_selected=False;current_additional=[]
        while isinstance(base, dict):
            archive = base.get('archive')
            if archive is not None:
                schema=_load(archive).get('schema')
                if schema=='guanheng.daily-native-archive.v1'and not additional_selected:
                    current_additional.append(archive);additional_selected=True
                if schema=='guanheng.daily-native-archive.v2':
                    entries=_load(archive)['entries']
                    if entries and all(row['provenance'][0]['metadata']['adjustment']=='front_ratio'for row in entries):
                        current_additional.append(archive);base=base.get('base');continue
                    template.update(previous_archives=[archive], previous_stores=[])
                    break
            base = base.get('base')
        if current_additional:
            # 当前成功档优先；显式采用的已核原生补充档仍进入同一按日合并，不被指针抹掉。
            selected={(item['path'],item['sha256']):item for item in current_additional}
            for item in template.get('additional_archives',[]):selected.setdefault((item['path'],item['sha256']),item)
            template['additional_archives']=list(selected.values())
    protected = set(template['protected_slots'])
    plans = [];scope_history=[]
    for request_path in previous_requests:
        request_path = Path(request_path)
        previous = strict_json(read_fixed(request_path, maximum=16777216))
        protected.update(previous['protected_slots'])
        if previous.get('price_maintenance')is not None:
            scope_history=[previous['price_maintenance']['scope']]
            protected.update(previous['price_maintenance']['protected_slots'])
        state_path = request_path.parent / 'work' / 'STATE.json'
        if not state_path.exists():
            continue
        state = strict_json(read_fixed(state_path, maximum=16777216))
        prior_plans=[]
        if state['stages'].get('gap_plan')is not None:
            prior_plans.append((state['stages']['gap_plan'],state_path.parent/'gap-work'))
        price_root=state_path.parent/'prices'/'inputs'
        phase=price_root/'PHASE-gap-plan.json'
        if phase.exists():
            price_plan=strict_json(read_fixed(phase,maximum=65536))['result']
            if price_plan is not None:prior_plans.append((price_plan,price_root/'gap-work'))
        for plan,gap_work in prior_plans:
            value=_load(plan);pending=[]
            for task in value['tasks']:
                slot=gap_work/'preparation'/('%06d.json'%task['index'])
                if not slot.exists():continue
                protected.add(str(slot));observed=gap_work/'observations'/('%06d.json'%task['index'])
                if not observed.exists()or strict_json(read_fixed(observed,maximum=1048576))['row']['state']!='call_returned':
                    pending.append(task['index'])
            if pending:plans.append((plan,gap_work,pending))
    if len(protected) > 100000:
        raise ValueError('daily protected request capacity')
    # 先观察原未知身份；所有非原槽的计划项交本日缓存计划判定，不在旧计划里重派。
    prior_observations=[]
    if plans:
        batch = BoundHistorySource(inputs['connections']['batch'], environ=environ, reuse_connections=True)
        try:
            owner = MarketDailyPreparation(lambda: BoundHistorySource(inputs['connections']['hpr'], environ=environ,
                reuse_connections=True), batch, concurrency=1)
            prior_observations=observe_prior_plans(plans,owner,deadline=deadline,cancelled=cancelled)
        finally:
            batch.close()
    check()
    reader = SimpleNamespace(
        repository=SnapshotRepository(configuration['raw_store']),  # 数据owner的原采集回执事务库，每次操作沿原短连接生命周期。
        objects=ContentStore(configuration['raw_store']))  # 唯一原件对象库；该角色没有观察查询/指标发布接口。
    reader.repository.initialize()
    public = inputs['public_facts']
    budget = CollectionBudget(min(deadline, time.monotonic() + public['seconds']), max_requests=public['max_requests'],
        max_bytes=public['max_bytes'], response_bytes=public['response_bytes'], cancelled=cancelled)
    fetch = Fetcher(BoundedContentStore(reader.objects, budget), public['allowed_hosts'],
        timeout=public['timeout_seconds'], budget=budget)
    try:
        packet, facts = capture_day_facts(reader, fetch, public['source'], day)
    finally:
        fetch.close()
    check()
    universe = root / 'UNIVERSE.json'
    body = reader.objects.get(packet['universe']['sha256'])
    if universe.exists():
        if universe.read_bytes() != body:
            raise ValueError('daily input original universe differs')
    else:
        universe.write_bytes(body)
    pool = strict_json(body)
    if pool['date'] != day:
        raise ValueError('daily input universe date differs')
    def restore_catalog(output):
        from .day_facts import DayFactsStore
        descriptor = _descriptor(output / 'catalog.json')
        value = _load(descriptor)
        catalog = DayFactsStore(descriptor)
        try:
            for entry in value['days']:
                check()
                result = catalog.query(entry['date'], '0' * 64)
                if entry['date'] == day:
                    for key, expected in facts.items():
                        if result[key] != expected:
                            raise ValueError('daily input restored current facts differ')
            if day not in {entry['date'] for entry in value['days']}:
                raise ValueError('daily input restored facts day missing')
        finally:
            catalog.close()
        return descriptor
    catalog = prepare_directory(root, 'facts', 'catalog.json',
        lambda output: extend_facts_catalog(template['daily_facts'], [facts], output, deadline=deadline), restore_catalog)
    seed = inputs.get('cache_seed')
    adopted = None
    if seed is not None:
        from guanheng_qmt_shm.analysis_batch_source import read_capture
        original = strict_json(read_fixed(Path(seed['directory']) / 'manifest.json', maximum=16777216,
                                         identity=seed['sha256']))
        if (original['request']['end_date'] == day.replace('-', '')
                and original['request']['start_date'] == inputs['cache_from']
                and original['request']['universe']['sha256'] == _descriptor(universe)['sha256']):
            read_capture(seed['directory'])
            adopted = original
    capture_request = root / 'CAPTURE-REQUEST.json'
    if adopted is None and not capture_request.exists():
        from guanheng_app.observation.calendars import official_calendar
        calendar = _load(template['calendar'])
        calendar_rows, _ = official_calendar(calendar)
        first = datetime.strptime(inputs['cache_from'], '%Y%m%d').date().isoformat()
        if not calendar['coverage_start'] <= first <= day <= calendar['coverage_end']:
            raise ValueError('daily input price window outside calendar coverage')
        complete_rows = sum(row['is_open'] == 1 and first <= row['date'] <= day for row in calendar_rows)
        rows = max(inputs['max_rows'], complete_rows)
        if rows > 2000:
            raise ValueError('daily input complete price window capacity')
        convert = lambda s: s[3:] + '.' + {'sh': 'SH', 'sz': 'SZ', 'bj': 'BJ'}[s[:2]]
        _save(capture_request, dict(
            schema='qab.request-plan.v1',  # 原BatchAnalysisSource请求计划版本。
            capture_id=str(uuid.uuid4()),  # 本任务首次生成的原捕获UUID；恢复沿原值。
            source_kind=inputs['source_kind'],  # actual-qmt或显式SDK替身，沿原来源合同。
            symbols=sorted(convert(s) for s in pool['members']),  # 本日真实股票池；资料缺项仍保留。
            start_date=inputs['cache_from'],  # 已授权的来源读取起日YYYYMMDD。
            end_date=day.replace('-', ''),  # 本次闭合市场日期，独立于接收时刻。
            max_rows=rows,  # 至少覆盖固定起日至目标日全部官方交易日；上限2000，避免滑窗截掉旧历史。
            ticket_lifetime_ms=30000,  # 原单请求30秒截止；恢复不重置原slot。
            universe=_descriptor(universe)))  # 原定日池正文身份。
    if adopted is None:
        request = strict_json(read_fixed(capture_request, maximum=16777216))
        completed_capture = root / 'cache' / 'manifest.json'
        if completed_capture.exists():
            from guanheng_qmt_shm.analysis_batch_source import read_capture
            read_capture(root / 'cache')
        else:
            batch = BoundHistorySource(inputs['connections']['batch'], environ=environ, reuse_connections=True)
            try:
                BatchAnalysisSource(batch, lifetime_ms=30000).capture(request, root / 'cache', deadline=deadline,
                    minimum_new_request_seconds=30, on_result=lambda *args: check())
            finally:
                batch.close()
        cache = dict(directory=str(root / 'cache'), sha256=_descriptor(root / 'cache' / 'manifest.json')['sha256'])
        selected_universe = _descriptor(universe)
    else:
        cache = seed
        selected_universe = adopted['request']['universe']
        # 原捕获的请求路径身份保持原值，正文须与本次同日股票池逐字相同。
        if _load(selected_universe) != pool:
            raise ValueError('daily input adopted universe differs')
    check()
    template.update(cache=cache,
        universe=selected_universe, daily_facts=catalog, protected_slots=sorted(protected),
        authorized_from=inputs['cache_from'], authorized_to=day.replace('-', ''), connections=inputs['connections'])
    if configuration.get('price_scope')is not None:
        from .daily_price_scope import prepare_price_scope
        current_value,current_sha=read_generation(current)
        scope=prepare_price_scope(configuration['price_scope'],day,selected_universe,current_value,root/'prices',
            deadline=deadline,cancelled=cancelled,environ=environ,previous_scopes=scope_history)
        template['price_maintenance']=dict(
            scope=scope,  # 全类别动态/保留价格池，普通A股指标池保持独立。
            current_configuration=current_value['configuration'],  # 固定旧价格读版本，恢复不跟随后继指针。
            snapshot_id=current_value['snapshot_id'],  # 原旧快照身份，不冒充来源catalog_id。
            calendar=template['calendar'],  # 原日历范围及验证资格。
            connections=inputs['connections'],  # 同一数据角色的原Batch/HPR通信，凭据不写入。
            protected_slots=sorted(protected),  # 跨股票及额外价格旧任务的原槽全部保护。
            authorized_from=configuration['price_scope']['authorized_from'],  # 全类别已授权历史起日。
            source_kind=inputs['source_kind'],  # 真源与SDK替身分别标识。
            maximum_history_rows=configuration['price_scope']['maximum_history_rows'],  # 每证券完整历史预算。
            previous_archives=template['additional_archives'],  # 最新完整补充原价，保留原独立来源。
            helper=template['helper'])  # 同一固定原Helper，未引入独立导入owner。
        if inputs.get('price_cache_seed')is not None and not plans:
            template['price_maintenance']['cache_seed']=inputs['price_cache_seed']  # 同名单/闭合日的已完成原缓存，目录及原UUID保持。
        if configuration['price_scope'].get('index_fallback')is not None:
            template['price_maintenance']['index_fallback']=configuration['price_scope']['index_fallback']  # 显式官方指数来源；读侧仍只读WT。
        by_plan={descriptor['sha256']:_load(descriptor)for descriptor,_,_ in plans}
        pending=set()
        for observation in prior_observations:
            for index in observation['task_indices']:
                qmt=by_plan[observation['plan_sha256']]['tasks'][index]['symbol'];code,market=qmt.split('.')
                pending.add({'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[market]+'.'+code)
        template['prior_pending_symbols']=sorted(pending)  # 原身份仍待核的证券集合，已可读Native不因此失去价格资格。
    if 'prepared_native' in template and _load(template['prepared_native'])['capture_sha256'] != cache['sha256']:
        template.pop('prepared_native')
    _save(final, template)
    _save(root / 'INPUT-RECEIPT.json', dict(
        date=day,  # 原输入共同的市场日期YYYY-MM-DD。
        packet_sha256=hashlib.sha256(json.dumps(
        packet, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')).hexdigest(),
        # packet_sha256为唯一公开输入原件包规范JSON身份，区别原价捕获SHA。
        http_requests=budget.http_requests,  # 本次实际公开HTTP请求数；复用为0。
        sdk_requests=budget.sdk_requests,  # 本次公开SDK请求数，与QMT原批读分别计数。
        captured_bytes=budget.captured_bytes,  # 本轮实际接收原字节数，不是RSS/缓存峰值。
        prior_request_observations=prior_observations))  # 暂不可续核的原来源责任，原ID与保护区间继续保留。
    return _descriptor(final)
