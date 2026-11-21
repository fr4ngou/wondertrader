"""WT数据更新的原输入生产者；复用唯一公开事实适配器和原QMT批读通道。"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import time
from types import SimpleNamespace
import uuid

from .daily_data_update import DAILY_UPDATE_REQUEST_BYTES, _save, _load, _descriptor, price_maintenance_with_slots
from .source_archive_identity import DAILY_ARCHIVE_MANIFEST_BYTES
from .market_generation import encode, read_fixed, read_generation
from .daily_gap_plan import (committed_gap_plans, load_gap_plan, read_protected_request,
                             terminal_hpr_paths, MAX_PROTECTED_SLOTS)
from ..guanheng_market_client import strict_json


def validate_unit_evidence_descriptor(value):
    """只核可选证据引用形状；原件及业务来源由价格阶段沿原总D核验。"""
    if (type(value)is not dict or set(value)!={'path','sha256'}
            or type(value['path'])is not str or not Path(value['path']).is_absolute()
            or type(value['sha256'])is not str or re.fullmatch(r'[0-9a-f]{64}',value['sha256'])is None):
        raise ValueError('daily price unit evidence descriptor invalid')


def fixed_price_input_configuration(configuration, original):
    """已有任务拥有原价格来源及证据选择，其余配置继续按原入口完整核同。"""
    if type(configuration)is not dict or type(original)is not dict:
        raise ValueError('daily input original configuration invalid')
    selected=deepcopy(configuration)
    scope=selected.get('price_scope');prior=original.get('price_scope')
    if type(scope)is dict and type(prior)is dict:
        for key in ('unit_evidence','local_qmt_dat_root'):
            if key in prior:scope[key]=deepcopy(prior[key])
            else:scope.pop(key,None)
    return selected


def reusable_analysis_capture(candidates, day, symbols, universe_sha256, inputs, required_rows, *, check, read_after=None):
    """选择同日、同股票池和来源的已固定原批次，保留原请求及回包身份。"""
    from guanheng_qmt_shm.analysis_batch_source import read_capture

    seen = set()
    for candidate in candidates:
        if candidate is None:
            continue
        key = (candidate['directory'], candidate['sha256'])
        if key in seen:
            continue
        seen.add(key)
        check()
        manifest = strict_json(read_fixed(Path(candidate['directory']) / 'manifest.json', maximum=16777216,
                                          identity=candidate['sha256']))
        selection = manifest['request']
        if (selection['end_date'] == day.replace('-', '')
                and selection['start_date'] == inputs['cache_from']
                and selection['universe']['sha256'] == universe_sha256
                and selection['symbols'] == symbols
                and selection['max_rows'] >= required_rows
                and (not read_after or all(datetime.fromisoformat(batch['requested_at']) >= read_after[symbol]
                                           for batch in manifest['batches'] for symbol in batch['symbols']
                                           if symbol in read_after))
                and manifest['source_kind'] == inputs['source_kind']):
            read_capture(candidate['directory'])
            check()
            return candidate, manifest
    return None, None


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


def _prepared_update_descriptor(path):
    """旧未准入的双份清单原件保留，单份等价表示沿原请求预算进入当前任务。"""
    if path.stat().st_size <= DAILY_UPDATE_REQUEST_BYTES:
        return _descriptor(path)
    original = strict_json(read_fixed(path, maximum=2 * DAILY_UPDATE_REQUEST_BYTES))
    if type(original) is not dict or original.get('schema') != 'guanheng.daily-data-update.v1':
        raise ValueError('oversized daily update schema invalid')
    slots = original.get('protected_slots')
    maintenance = original.get('price_maintenance')
    if type(slots) is not list or type(maintenance) is not dict or maintenance.get('protected_slots') != slots:
        raise ValueError('oversized daily update protected slots differ')
    single = dict(maintenance)
    del single['protected_slots']
    compact = dict(original, price_maintenance=single)
    body = encode(compact)
    if len(body) > DAILY_UPDATE_REQUEST_BYTES:
        raise ValueError('compact daily update exceeds original request budget')
    destination = path.with_name('UPDATE-COMPACT.json')
    if destination.exists():
        if read_fixed(destination, maximum=DAILY_UPDATE_REQUEST_BYTES) != body:
            raise ValueError('compact daily update identity differs')
    else:
        _save(destination, compact)
    return _descriptor(destination)


def prepare_report_inputs(configuration, day, directory, *, deadline, cancelled):
    """独立报表线程写原任务的准备日志，不接触行情连接、INDEX 或 CURRENT。"""
    from guanheng_app.observation.calendars import official_calendar
    from guanheng_app.observation.source_fetch import BoundedContentStore, CollectionBudget, Fetcher
    from guanheng_app.observation.storage import ContentStore
    from .market_supplement_capture import collect_supplement, prior_supplement_catalogs

    root = Path(directory).absolute()
    root.mkdir(exist_ok=True)
    original = root / 'INPUTS.json'
    if original.exists():
        configuration = _load(_descriptor(original))['configuration']
    template = configuration['template']
    inputs = configuration['inputs']
    public = inputs['public_facts']
    budget = CollectionBudget(min(deadline,time.monotonic()+public['seconds']),max_requests=public['max_requests'],
        max_bytes=public['max_bytes'],response_bytes=public['response_bytes'],cancelled=cancelled)
    objects = ContentStore(configuration['raw_store'])
    previous = template.get('supplement_facts')
    reference_base=None
    # 本报表线程按需读已发布的本地WT日线；初次启动也可复用模板已有归档。
    current = Path(template['publication_directory'])/'CURRENT.json'
    if current.exists():
        generation,_ = read_generation(current)
        published=_load(generation['configuration'],1048576)
        previous = published.get('supplement_facts',previous)
        reference_base=published.get('base')
    elif template.get('base_configuration'):
        reference_base=template['base_configuration']
    previous = prior_supplement_catalogs(previous,configuration['directory'],root,day,
                                         objects=objects,check=budget.remaining)
    calendar = _load(template['calendar'])
    dates,_ = official_calendar(calendar,check=budget.remaining)
    fetch = Fetcher(BoundedContentStore(objects,budget),public['allowed_hosts'],
                    timeout=public['timeout_seconds'],budget=budget)
    try:
        collect_supplement(inputs['supplement_facts'],day,[row['date'] for row in dates if row['is_open']==1],
            root/'supplement',objects=objects,fetch=fetch,qmt_transport=None,
            calendar_coverage=(calendar['coverage_start'],calendar['coverage_end']),previous=previous,
            deadline=deadline,cancelled=cancelled,reports_only=True,reference_base=reference_base)
    finally:
        fetch.close()


def _published_price_result(receipt, previous_publication, day, current, current_sha):
    """按实际活动父版本选取同日已采用的价格结果。"""
    if (receipt is not None and receipt.get('schema') == 'guanheng.daily-price-refresh-result.v1'
            and receipt['price_date'] == day and receipt['current_sha256'] == current_sha):
        return receipt['price_result'], False
    if previous_publication is not None and current.get('observation_date') == day:
        state_path = Path(previous_publication).parent / 'work' / 'STATE.json'
        if state_path.exists():
            state = strict_json(read_fixed(state_path, maximum=DAILY_UPDATE_REQUEST_BYTES))
            if state['status'] == 'published' and state['current_sha256'] == current_sha:
                return state['stages'].get('prices'), True
    return None, False


def prepare_update(configuration, day, directory, *, deadline, cancelled=lambda: False,
                   environ=None, previous_requests=(), prior_price_requests=(), baostock_daily_timeout_seconds=None,
                   published_price_receipt=None, previous_publication=None):
    """调用方持publication锁；同目录输入请求及原slot固定，恢复不改capture_id。

    configuration.template为单轮更新静态配置，inputs为公开事实/原批读的有限预算。
    日事实、股票池、原缓存都实际保存后才写UPDATE.json；其摘要供单轮owner固定。
    旧任务的未决HPR槽继续保护及续核。已固定计划已证明的HPR终态沿原目录留证。
    published_price_receipt由同一租约内的独立价格阶段提供，previous_publication为上轮同日完整请求。
    新意图按实际父CURRENT固定可复用结果。
    """
    from .day_facts_capture import capture_day_facts
    from .day_facts_prepare import extend_facts_catalog
    from .source_history_transport import BoundHistorySource
    from .daily_data_stages import prepare_directory
    from guanheng_app.observation.storage import ContentStore, SnapshotRepository
    from guanheng_app.observation.source_fetch import Fetcher, CollectionBudget, BoundedContentStore
    from .daily_batch_source import DailyBatchAnalysisSource
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
    current = Path(configuration['template']['publication_directory']) / 'CURRENT.json'
    current_config = None
    if intent.exists():
        original=strict_json(read_fixed(intent, maximum=16777216))
        configuration=fixed_price_input_configuration(configuration,original.get('configuration')if type(original)is dict else None)
        bound=dict(bound,configuration=configuration)
        for field in ('security_reference', 'published_prices'):
            if field in original:
                bound[field] = original[field]
        if original != bound:
            raise ValueError('daily input original configuration differs')
    else:
        if current.exists():
            current_value, current_sha = read_generation(current)
            current_config = _load(current_value['configuration'], 1048576)
            price_result, retry_pending = _published_price_result(published_price_receipt, previous_publication,
                day, current_value, current_sha)
            if price_result is not None:
                bound['published_prices'] = dict(
                    current_sha256=current_sha,  # 已包含这些价格归档的父CURRENT身份。
                    result=price_result)  # 原价格结果描述符，包含捕获、证券资料及归档。
                if retry_pending:
                    # 从上一完整修订接续时保留仍待核的额外证券，本轮新价格发布则直接复用。
                    bound['published_prices']['retry_pending'] = True
            reference = current_config.get('security_reference')
            if reference is not None:
                bound['security_reference'] = reference  # 固定价格阶段已发布的证券资料，恢复沿本轮原件。
        _save(intent, bound)
    final = root / 'UPDATE.json'
    if final.exists():
        check()
        return _prepared_update_descriptor(final)
    check()
    template = deepcopy(configuration['template'])
    inputs = configuration['inputs']
    supplement_previous = template.pop('supplement_facts', None)  # 同一原件库的已采市场事实。
    if 'security_reference' in bound:
        template['security_reference'] = bound['security_reference']
    # 原生合并及日事实仍沿可读成功版本，证券资料由本轮输入检查点固定。
    if current_config is None and current.exists():
        current_value, _ = read_generation(current)
        current_config = _load(current_value['configuration'], 1048576)
    if current_config is not None:
        if 'supplement_facts' in inputs:
            supplement_previous = current_config.get('supplement_facts', supplement_previous)
        template['daily_facts'] = current_config['daily_facts']
        base = current_config['base'];additional_selected=False;current_additional=[]
        while isinstance(base, dict):
            archive = base.get('archive')
            if archive is not None:
                schema=_load(archive,DAILY_ARCHIVE_MANIFEST_BYTES).get('schema')
                if schema=='guanheng.daily-native-archive.v1'and not additional_selected:
                    current_additional.append(archive);additional_selected=True
                if schema=='guanheng.daily-native-archive.v2':
                    entries=_load(archive,DAILY_ARCHIVE_MANIFEST_BYTES)['entries']
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
    from .daily_strategy_history import strategy_slots
    protected.update(strategy_slots((*previous_requests,*prior_price_requests)))
    plans = [];scope_history=[]
    terminal_paths = set()  # 从已准入原PLAN读取的不可变HPR终态引用。
    committed_captures = []  # 原INDEX已发布的同日归档，沿原请求固定身份。
    latest_download = {}  # 证券的最新原HPR接收时刻；只淘汰该证券更早的行情回包。

    def returned_download(clock,symbol):
        received = datetime.fromisoformat(clock)
        latest_download[symbol] = max(latest_download.get(symbol, received), received)
    # 独立价格阶段属于同owner的原责任；不改已有INPUTS原意图，另从持久INDEX引用恢复保护。
    for request_path in (*previous_requests,*prior_price_requests):
        request_path = Path(request_path)
        previous = strict_json(read_fixed(request_path, maximum=16777216))
        protected.update(previous['protected_slots'])
        if previous.get('price_maintenance')is not None:
            scope_history=[previous['price_maintenance']['scope']]
            protected.update(price_maintenance_with_slots(previous)['protected_slots'])
        state_path = request_path.parent / 'work' / 'STATE.json'
        if not state_path.exists():
            continue
        state = strict_json(read_fixed(state_path, maximum=16777216))
        if (state.get('status') == 'published' and previous.get('schema') == 'guanheng.daily-data-update.v1'
                and previous.get('authorized_to') == day.replace('-', '')):
            committed_captures.append(previous['cache'])
            if 'readback' in state['stages']:
                committed_captures.append(state['stages']['readback'])
        prior_plans=list(committed_gap_plans(state_path.parent,state['stages']))
        from .daily_strategy_history import strategy_prior_plans
        prior_plans.extend(strategy_prior_plans((request_path,)))  # hot原HPR跨日也沿同一owner续核，后继计划保护其区间。
        for plan,gap_work in prior_plans:
            value=load_gap_plan(plan,deadline=deadline,cancelled=cancelled);pending=[]
            terminal_paths.update(terminal_hpr_paths(value))
            for task in value['tasks']:
                slot=gap_work/'preparation'/('%06d.json'%task['index'])
                if not slot.exists():continue
                protected.add(str(slot));observed=gap_work/'observations'/('%06d.json'%task['index'])
                row = strict_json(read_fixed(observed,maximum=1048576))['row'] if observed.exists() else {}
                if value['authorized_to'] >= inputs['cache_from']:
                    clock = (row.get('record') or {}).get('received_at') if row.get('state')=='call_returned' else None
                    if clock is not None:
                        returned_download(clock,task['symbol'])
                    else:
                        # HPR先持久写原slot才写观察；跨进程恢复也能看到已完成的补齐时点。
                        read_protected_request(slot,deadline=deadline,cancelled=cancelled,on_returned=returned_download)
                if row.get('state') == 'call_returned':
                    continue
                pending.append(task['index'])
            if pending:plans.append((plan,gap_work,pending))
    protected.difference_update(terminal_paths)
    if len(protected) > MAX_PROTECTED_SLOTS:
        raise ValueError('daily protected request capacity')
    # 先观察原未知身份；所有非原槽的计划项交本日缓存计划判定，不在旧计划里重派。
    prior_observations=[]
    if plans:
        batch = BoundHistorySource(inputs['connections']['batch'], environ=environ, reuse_connections=True)
        try:
            owner = MarketDailyPreparation(lambda: BoundHistorySource(inputs['connections']['hpr'], environ=environ,
                reuse_connections=True), batch)
            prior_observations=observe_prior_plans(plans,owner,deadline=deadline,cancelled=cancelled)
            for _, gap_work, indices in plans:
                for index in indices:
                    slot = gap_work/'preparation'/('%06d.json'%index)
                    read_protected_request(slot,deadline=deadline,cancelled=cancelled,on_returned=returned_download)
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
    supplement = None  # 未配置时不改变原UPDATE/快照字段或身份。
    supplement_transport = None  # 由本输入owner在finally关闭，不创建第二个采集线程。
    try:
        packet, facts = capture_day_facts(reader, fetch, public['source'], day,
            retry_window_seconds=min(86400,max(60,configuration['retry_seconds']*8)),
            baostock_daily_timeout_seconds=baostock_daily_timeout_seconds)
        if 'supplement_facts' in inputs:
            from .market_supplement_capture import collect_supplement, prior_supplement_catalogs
            from guanheng_app.observation.calendars import official_calendar
            calendar = _load(template['calendar'])
            calendar_rows, _ = official_calendar(calendar)
            supplement_previous = prior_supplement_catalogs(supplement_previous, configuration['directory'],
                root, day, objects=reader.objects, check=check)
            supplement_transport = BoundHistorySource(inputs['connections']['batch'], environ=environ,
                                                       reuse_connections=True)
            supplement = collect_supplement(inputs['supplement_facts'], day,
                [row['date'] for row in calendar_rows if row['is_open'] == 1], root / 'supplement',
                objects=reader.objects, fetch=fetch, qmt_transport=supplement_transport,
                calendar_coverage=(calendar['coverage_start'], calendar['coverage_end']),
                previous=supplement_previous, deadline=deadline, cancelled=cancelled, environ=environ,
                reference_base=(current_config.get('base')if current_config is not None
                                else template['base_configuration']))
    finally:
        try:
            if supplement_transport is not None:
                supplement_transport.close()
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
    convert = lambda s: s[3:] + '.' + {'sh': 'SH', 'sz': 'SZ', 'bj': 'BJ'}[s[:2]]
    symbols = sorted(convert(symbol) for symbol in pool['members'])
    capture_request = root / 'CAPTURE-REQUEST.json'
    adopted = None
    seed = None
    if not capture_request.exists():
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
        seed, adopted = reusable_analysis_capture(
            [*reversed(committed_captures), inputs.get('cache_seed')], day, symbols,
            _descriptor(universe)['sha256'], inputs, rows, check=check, read_after=latest_download)
        if adopted is None:
            _save(capture_request, dict(
                schema='qab.request-plan.v1',  # 原BatchAnalysisSource请求计划版本。
                capture_id=str(uuid.uuid4()),  # 本任务首次生成的原捕获UUID；恢复沿原值。
                source_kind=inputs['source_kind'],  # actual-qmt或显式SDK替身，沿原来源合同。
                symbols=symbols,  # 本日真实股票池；资料缺项仍保留。
                start_date=inputs['cache_from'],  # 已授权的来源读取起日YYYYMMDD。
                end_date=day.replace('-', ''),  # 本次闭合市场日期，独立于接收时刻。
                max_rows=rows,  # 至少覆盖固定起日至目标日全部官方交易日；上限2000。
                ticket_lifetime_ms=30000,  # 原单请求30秒截止；恢复不重置原slot。
                universe=_descriptor(universe)))  # 原定日池正文身份。
    if adopted is None:
        request = strict_json(read_fixed(capture_request, maximum=16777216))
        completed_capture = root / 'cache' / 'manifest.json'
        if completed_capture.exists():
            from guanheng_qmt_shm.analysis_batch_source import read_capture
            read_capture(root / 'cache')
        else:
            from .daily_batch_source import seed_local_analysis_batches
            seed_local_analysis_batches(root, request, [*reversed(committed_captures), inputs.get('cache_seed')],
                                        latest_download, check=check)
            batch = BoundHistorySource(inputs['connections']['batch'], environ=environ, reuse_connections=True)
            try:
                DailyBatchAnalysisSource(batch, lifetime_ms=30000).capture(request, root / 'cache', deadline=deadline,
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
    section_policy = inputs.get('stock_cross_section')
    from .day_facts_capture import restore_shsz_facts

    def enrich_existing(value):
        return restore_shsz_facts(reader.objects, value, check)

    def build_catalog(output):
        current_facts = enrich_existing(facts)
        if section_policy is None:
            return extend_facts_catalog(template['daily_facts'], [current_facts], output, deadline=deadline,
                                        enrich_existing=enrich_existing)
        from .day_facts import DayFactsStore
        from .stock_cross_section import prepare_section
        previous_facts = DayFactsStore(template['daily_facts'])
        try:
            previous = previous_facts.query(day, '0' * 64)
            section = previous.get('stock_cross_section', {}) if previous else {}
            if ('provider' not in section or previous['provenance']['universe_sha256'] != facts['provenance']['universe_sha256']
                    or previous['rows'] != facts['rows']):
                section = prepare_section(facts, cache, (configuration.get('price_scope') or {}).get('unit_evidence'),
                                          section_policy, reader.objects, deadline=deadline, cancelled=cancelled,
                                          environ=environ)
            revisions = [dict(current_facts, stock_cross_section=section)]
            if 'history_from' in section_policy:
                remaining = section_policy['history_days_per_cycle']
                # 先覆盖未处理日；当次不可用结果等自然日重试，保留精确档案日期。
                candidates = []
                for candidate in previous_facts.days():
                    if section_policy['history_from'] <= candidate < day:
                        check()
                        original = previous_facts.query(candidate, '0'*64)
                        status = original.get('stock_cross_section', {})
                        if 'provider' not in status:
                            candidates.append((bool(status), candidate))
                for _, candidate in sorted(candidates):
                    if remaining == 0 or deadline - time.monotonic() <= 2 * section_policy['timeout_seconds']:
                        break
                    check()
                    original = previous_facts.query(candidate, '0'*64)
                    original.pop('source_snapshot_id')
                    original.pop('source_sha256')
                    section = prepare_section(original, cache, None, section_policy, reader.objects,
                                              deadline=deadline, cancelled=cancelled, environ=environ)
                    revisions.append(dict(enrich_existing(original), stock_cross_section=section))
                    remaining -= 1
            return extend_facts_catalog(template['daily_facts'], revisions, output, deadline=deadline,
                                        enrich_existing=enrich_existing)
        finally:
            previous_facts.close()

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
                    if section_policy is not None:
                        section = result['stock_cross_section']
                        if 'provider' in section:
                            body = reader.objects.get(section['source_sha256'])
                            original = strict_json(body)
                            from .stock_cross_section import project
                            projection = project(facts, original['records'])
                            if (original['date'] != day or original['provider'] != section['provider']
                                    or original['universe_sha256'] != facts['provenance']['universe_sha256']
                                    or any(projection[key] != section[key] for key in projection if key != 'date')):
                                raise ValueError('daily input restored stock section differs')
                    for key, expected in facts.items():
                        if result[key] != expected:
                            raise ValueError('daily input restored current facts differ')
            if day not in {entry['date'] for entry in value['days']}:
                raise ValueError('daily input restored facts day missing')
        finally:
            catalog.close()
        return descriptor
    catalog = prepare_directory(root, 'facts', 'catalog.json',
        build_catalog, restore_catalog)
    template.update(cache=cache,
        universe=selected_universe, daily_facts=catalog, protected_slots=sorted(protected),
        authorized_from=inputs['cache_from'], authorized_to=day.replace('-', ''), connections=inputs['connections'])
    if configuration.get('price_scope')is not None:
        from .daily_price_scope import prepare_price_scope
        current_value,current_sha=read_generation(current)
        published_prices = bound.get('published_prices')
        if published_prices is not None and published_prices['current_sha256'] == current_sha:
            scope = _load(published_prices['result'])['scope']
        else:
            published_prices = None
            scope = prepare_price_scope(configuration['price_scope'],day,selected_universe,current_value,root/'prices',
                deadline=deadline,cancelled=cancelled,environ=environ,previous_scopes=scope_history)
        template['price_maintenance']=dict(
            scope=scope,  # 全类别动态/保留价格池，普通A股指标池保持独立。
            current_configuration=current_value['configuration'],  # 固定旧价格读版本，恢复不跟随后继指针。
            snapshot_id=current_value['snapshot_id'],  # 原旧快照身份，不冒充来源catalog_id。
            calendar=template['calendar'],  # 原日历范围及验证资格。
            connections=inputs['connections'],  # 同一数据角色的原Batch/HPR通信，凭据不写入。
            # 股票和额外价格复用完整任务顶层的同一保护集合。
            authorized_from=configuration['price_scope']['authorized_from'],  # 全类别已授权历史起日。
            source_kind=inputs['source_kind'],  # 真源与SDK替身分别标识。
            maximum_history_rows=configuration['price_scope']['maximum_history_rows'],  # 每证券完整历史预算。
            previous_archives=template['additional_archives'],  # 最新完整补充原价，保留原独立来源。
            helper=template['helper'])  # 同一固定原Helper，未引入独立导入owner。
        if published_prices is not None:
            template['price_maintenance']['published_prices'] = published_prices  # 本地合并沿已验证的捕获和归档。
        if inputs.get('price_cache_seed')is not None and not plans:
            template['price_maintenance']['cache_seed']=inputs['price_cache_seed']  # 同名单/闭合日的已完成原缓存，目录及原UUID保持。
        if configuration['price_scope'].get('index_fallback')is not None:
            template['price_maintenance']['index_fallback']=configuration['price_scope']['index_fallback']  # 显式官方指数来源；读侧仍只读WT。
        if configuration['price_scope'].get('unit_evidence')is not None:
            template['price_maintenance']['unit_evidence']=deepcopy(configuration['price_scope']['unit_evidence'])  # 固定本任务的证据原件SHA；旧INPUTS沿原选择。
        if 'local_qmt_dat_root' in configuration['price_scope']:
            template['price_maintenance']['local_qmt_dat_root']=configuration['price_scope']['local_qmt_dat_root']  # 固定本轮只读本地DAT输入根。
        if configuration['price_scope'].get('strategy_history')is not None:
            template['price_maintenance']['strategy_history']=configuration['price_scope']['strategy_history']  # 额外策略窗口，不改变全市场authorized_from。
            template['price_maintenance']['strategy_history_previous_requests']=list(dict.fromkeys((*previous_requests,*prior_price_requests)))  # 固定旧工作流身份，后继续核不重发。
        by_plan={descriptor['sha256']:load_gap_plan(descriptor,deadline=deadline,cancelled=cancelled)
                 for descriptor,_,_ in plans}
        pending=set()
        for observation in prior_observations:
            for index in observation['task_indices']:
                qmt=by_plan[observation['plan_sha256']]['tasks'][index]['symbol'];code,market=qmt.split('.')
                pending.add({'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[market]+'.'+code)
        template['prior_pending_symbols']=sorted(pending)  # 原身份仍待核的证券集合，已可读Native不因此失去价格资格。
        if published_prices is not None and published_prices.get('retry_pending') and pending:
            template['price_maintenance']['published_prices'] = dict(published_prices,
                prior_pending_symbols=sorted(pending))  # 原保护槽可能使继任计划不创建新HPR，保留旧证券的续核责任。
    if supplement is not None:
        template['supplement_facts'] = supplement  # 同一固定快照发布新增市场事实。
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
