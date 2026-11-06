"""WT数据侧单轮更新：原缓存、真实缺口、原生版本和原子发布共用一个持久任务。"""
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import time

from ..guanheng_market_client import strict_json
from .market_generation import GenerationPublisher, encode, read_fixed, read_generation, _replace_pointer


def _save(path, value):
    pending = path.with_suffix(path.suffix + '.pending')
    with pending.open('wb') as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    _replace_pointer(pending, path)


def _descriptor(path, maximum=16777216):
    """固定原文件摘要；maximum为该类合同允许的字节上界，默认保持原16MiB。"""
    path = Path(path).absolute()
    return dict(path=str(path), sha256=hashlib.sha256(read_fixed(path, maximum=maximum)).hexdigest())


def _load(descriptor, maximum=16777216):
    if (type(descriptor) is not dict or set(descriptor) != {'path', 'sha256'}
            or type(descriptor['path']) is not str or not Path(descriptor['path']).is_absolute()):
        raise ValueError('daily update descriptor invalid')
    return strict_json(read_fixed(descriptor['path'], maximum=maximum, identity=descriptor['sha256']))


def verify_supplement_configuration(config, expected, day, check):
    """每次发布前核原请求的补充事实闭包，已提交snapshot阶段恢复也沿本入口。

    expected是UPDATE固定目录descriptor；原owner的check贯穿逐件IO。
    没有配置时保持旧行为，避免给旧snapshot增加字段或身份。
    """
    if config.get('supplement_facts') != expected:
        raise ValueError('daily update supplement configuration differs')
    if expected is None:
        return
    from .market_supplement_store import MarketSupplementStore
    snapshot = _load(config['snapshot'])
    if snapshot['provenance'].get('supplement_facts_sha256') != expected['sha256']:
        raise ValueError('daily update supplement provenance differs')
    store = MarketSupplementStore(expected, observation_date=day)
    try:
        store.verify_sources(check=check)
        return store.catalog['complete']
    finally:
        store.close()


def run_update(request, directory, *, deadline, cancelled=lambda: False, environ=None, publisher=None):
    """持同一publication排他锁运行；directory仅供本次固定请求恢复。

    输入为数据侧已完成的原缓存、日事实和资料，网络捕获由同一数据角色先行保存。
    prepared_native为已核复用候选；实际capture/Helper相同时复用，否则沿实际回读转换。
    失败保留阶段、原slot及当前版本；同任务恢复沿原slot，首次成功阶段保持只读。
    原SDK及DLL的物理硬截止由外层WT进程Job负责，返回前关闭本轮全部Reader/连接。
    """
    from .daily_gap_update import prepare_gap_plan, advance_gap_plan,freeze_gap_progress
    from .daily_gap_plan import restore_gap_plan, load_gap_plan
    from .day_facts import DayFactsStore
    from .security_reference import SecurityReference
    from .source_history_transport import BoundHistorySource
    from .qmt_analysis_import import prepare_analysis_capture
    from .daily_generation import materialize_generation
    from .market_snapshot_prepare import prepare_market_snapshot, load_snapshot_basics, _catalog
    from .daily_data_stages import prepare_directory
    from guanheng_qmt_shm.analysis_batch_source import read_capture
    from .daily_batch_source import DailyBatchAnalysisSource
    from guanheng_qmt_shm.market_daily_preparation import MarketDailyPreparation
    from guanheng_qmt_shm.market_daily_cache import assess

    required = {'schema', 'publication_directory', 'cache', 'universe', 'daily_facts', 'security_reference',
                'calendar', 'base_configuration', 'basic_capture', 'helper', 'previous_stores',
                'previous_archives', 'protected_slots', 'authorized_from', 'authorized_to', 'additional_archives'}
    if (type(request) is not dict or not required <= set(request)
            or set(request) - required - {'connections', 'prepared_native', 'price_maintenance', 'prior_pending_symbols', 'supplement_facts'}
            or request['schema'] != 'guanheng.daily-data-update.v1'):
        raise ValueError('daily update request invalid')
    if (type(deadline) not in (int, float) or not math.isfinite(deadline)
            or not callable(cancelled)):
        raise ValueError('daily update deadline invalid')

    def check():
        if cancelled():
            raise InterruptedError('daily update stopped')
        if time.monotonic() >= deadline:
            raise TimeoutError('daily update deadline expired')

    transport = reference = facts = None
    from contextlib import nullcontext
    if publisher is not None and (not isinstance(publisher, GenerationPublisher) or publisher._lock is None
            or publisher.directory != Path(request['publication_directory']).absolute()):
        raise ValueError('daily update writer lease differs')
    lease = nullcontext(publisher) if publisher is not None else GenerationPublisher(request['publication_directory'])
    with lease as publisher:
        root = Path(directory).absolute()
        root.mkdir(parents=False, exist_ok=True)
        intent = root / 'REQUEST.json'
        identity = hashlib.sha256(encode(request)).hexdigest()
        if intent.exists():
            if strict_json(read_fixed(intent, maximum=16777216)) != request:
                raise ValueError('daily update original request differs')
        else:
            _save(intent, request)
        journal = root / 'STATE.json'
        state = strict_json(read_fixed(journal, maximum=16777216)) if journal.exists() else dict(
            schema='guanheng.daily-data-update-state.v1',  # 同一固定请求的阶段结果，恢复沿原任务根。
            request_sha256=identity,  # 完整公开配置/路径引用身份，凭据值不写入。
            stages={},  # 已成功阶段的固定输出；恢复前逐项核摘要，原成功根不改。
            status='created')  # 本地工作流状态，独立于源SDK是否返回和行情覆盖。
        if state['request_sha256'] != identity:
            raise ValueError('daily update journal identity differs')

        def stage(name, action):
            check()
            if name not in state['stages']:
                state.update(status='running', active_stage=name)
                _save(journal, state)
                state['stages'][name] = action()
                _save(journal, state)
            return state['stages'][name]

        try:
            parent = stage('parent', lambda: dict(
                current_sha256=read_generation(publisher.current_file)[1]
                if publisher.current_file.exists() else None))  # 首次原指针SHA；空仅用于首次发布，恢复不重取父版本。
            cache = request['cache']
            if type(cache) is not dict or set(cache) != {'directory', 'sha256'}:
                raise ValueError('daily update cache invalid')
            capture = Path(cache['directory'])
            read_fixed(capture / 'manifest.json', maximum=16777216, identity=cache['sha256'])
            manifest = read_capture(capture)
            universe = _load(request['universe'])
            if manifest['request']['universe'] != request['universe']:
                raise ValueError('daily update universe binding differs')
            day = datetime.strptime(request['authorized_to'], '%Y%m%d').date().isoformat()
            if universe['date'] != day:
                raise ValueError('daily update universe date differs')
            facts = DayFactsStore(request['daily_facts'])
            reference = SecurityReference(request['security_reference'], request['calendar'])
            # 计划只用定日池和原资料，价格版本在真正落盘后构造。
            current_facts = facts.query(day, identity)
            if current_facts is None:
                raise ValueError('daily update current facts missing')
            snapshot = dict(snapshot_id=identity, observation_date=day,
                            basics=load_snapshot_basics(current_facts['members'], request['basic_capture'])[0])
            def restore_plan(output):
                return restore_gap_plan(output/'PLAN.json',capture=cache,snapshot_id=identity,
                    authorized_from=request['authorized_from'],authorized_to=request['authorized_to'],
                    protected_slots=request['protected_slots'],deadline=deadline,cancelled=cancelled)
            plan = stage('gap_plan', lambda: prepare_directory(root, 'gap-plan', 'PLAN.json',
                lambda output: prepare_gap_plan(cache, reference, snapshot, output,
                    protected_slots=request['protected_slots'], daily_facts=facts,
                    authorized_from=request['authorized_from'], authorized_to=request['authorized_to'], deadline=deadline,
                    cancelled=cancelled),
                restore_plan,recover_prior=True))  # 已捕获QAB/原槽的纯本地计划，不跨Source执行阶段。
            plan_value = load_gap_plan(plan,deadline=deadline,cancelled=cancelled)
            if plan_value['tasks']:
                prior_progress=state.get('gap_readback_progress')
                has_readback='readback'in state['stages']or(root/'readback'/'manifest.json').exists()
                if ('gap_readback_progress'in state or has_readback)and (
                        prior_progress is None or prior_progress.get('schema')!='guanheng.daily-gap-readback-progress.v1'):
                    # 已存在回读的旧时点缺项保持未推进；较晚磁盘观察只归后继修订。
                    state['gap_readback_progress']=freeze_gap_progress(plan,None,
                        deadline=deadline,cancelled=cancelled)
                    _save(journal,state)
                if 'connections' not in request:
                    raise ValueError('daily update gaps require original connections')
                connections = request['connections']
                transport = BoundHistorySource(connections['batch'], environ=environ, reuse_connections=True)
                owner = MarketDailyPreparation(lambda: BoundHistorySource(connections['hpr'], environ=environ,
                    reuse_connections=True), transport, concurrency=1)
                # 本阶段每次恢复都续核原slot；call_returned在advance内跳过，不重新派发。
                progress = advance_gap_plan(plan, root / 'gap-work', owner, deadline=deadline,
                    max_tasks=10000, cancelled=cancelled)
                state['gap_progress'] = progress  # 原调用结果，coverage仍由后续实际批读确认。
                _save(journal, state)
                check()
                source = DailyBatchAnalysisSource(transport, lifetime_ms=30000)
                if 'gap_readback_progress'not in state:
                    state['gap_readback_progress']=freeze_gap_progress(plan,progress,root/'gap-work'/'observations',
                        deadline=deadline,cancelled=cancelled)  # 此次回读前完整责任，随阶段恢复保持。
                    _save(journal,state)
                reread = stage('readback', lambda: _capture(source, manifest['request'], root / 'readback', deadline,check))
                capture = Path(reread['directory'])
                read_fixed(capture / 'manifest.json', maximum=16777216, identity=reread['sha256'])
            else:
                reread = cache
            quality = stage('quality', lambda: assess(capture))
            # 已成功原生结果经capture完整身份绑定，避免重复转换或重导5576只原价。
            def native_version():
                prepared = request.get('prepared_native')
                if prepared is not None:
                    result = _load(prepared)
                    if result['state'] != 'completed':
                        raise ValueError('daily update prepared native is not completed')
                    _load(result['archive'])
                    if (result['capture_sha256'] == reread['sha256']
                            and result['helper_sha256'] == request['helper']['sha256']):
                        return prepared
                conversion_path = root / 'conversion' / 'CONVERSION.json'
                conversion = _descriptor(conversion_path) if conversion_path.exists() else prepare_analysis_capture(
                    capture, root / 'conversion', request['helper']['sha256'], deadline=deadline,
                    resume=(root / 'conversion').exists(),cancelled=cancelled)
                materialize_generation(conversion, request['previous_stores'], root / 'native',
                    request['helper']['path'], request['helper']['sha256'], deadline=deadline,
                    resume=(root / 'native').exists(), previous_archives=request['previous_archives'],
                    native_reader=_catalog(_load(request['base_configuration'],1048576))['native_reader'],cancelled=cancelled)
                return _descriptor(root / 'native' / 'RESULT.json')
            native = stage('native', native_version)
            imported = _load(native)
            if imported['capture_sha256'] != reread['sha256']:
                raise ValueError('daily update restored native capture differs')
            price_result=None
            if 'price_maintenance'in request:
                from .daily_price_update import prepare_price_update
                price_descriptor=stage('prices',lambda:prepare_price_update(request['price_maintenance'],native,
                    request['base_configuration'],root/'prices',deadline=deadline,cancelled=cancelled,environ=environ,daily_facts=facts))
                price_result=_load(price_descriptor)
            def restore_snapshot(output):
                result = strict_json(read_fixed(output / 'PREPARED.json', maximum=65536))
                descriptor = dict(path=result['configuration'], sha256=result['configuration_sha256'])
                if Path(descriptor['path']) != output / 'source.json' or result['observation_date'] != day:
                    raise ValueError('daily update restored snapshot output differs')
                config = _load(descriptor, 1048576)
                if Path(config['snapshot']['path']) != output / 'snapshot.json':
                    raise ValueError('daily update restored snapshot path differs')
                if _load(config['snapshot'])['snapshot_id'] != result['snapshot_id']:
                    raise ValueError('daily update restored snapshot identity differs')
                return descriptor
            def prepare_snapshot(output):
                prepare_market_snapshot(_load(request['base_configuration'], 1048576), native['path'],
                    request['universe']['path'], request['basic_capture'], output,
                    daily_facts=request['daily_facts'], security_reference=(price_result['reference']
                        if price_result is not None else request['security_reference']),
                    calendar=request['calendar'], additional_archives=(price_result['additional_archives']
                        if price_result is not None else request['additional_archives']),
                    maximum_history_rows=price_result['maximum_history_rows']if price_result is not None else 2000,
                    supplement_facts=request.get('supplement_facts'), check=check)
                return restore_snapshot(output)
            configuration = stage('snapshot', lambda: prepare_directory(root, 'snapshot', 'PREPARED.json',
                prepare_snapshot, restore_snapshot))
            candidate = _load(configuration, 1048576)
            supplement_complete = verify_supplement_configuration(candidate, request.get('supplement_facts'), day, check)
            current = read_generation(publisher.current_file) if publisher.current_file.exists() else (None, None)
            # 处理CURRENT成功、工作流回执尚未保存的窗口；沿实际指针确认，避免二次发布。
            if current[0] is not None and current[0]['configuration'] == configuration:
                published = current
            else:
                check()
                published = publisher.publish(configuration, expected_current_sha256=parent['current_sha256'])
            state.update(
                status='published',  # 实际CURRENT已成功采用本候选。
                active_stage=None,  # 本轮阶段已收束，空表示无正在执行的阶段。
                generation=published[0],  # 原发布记录，保留父SHA、配置及股票池日期。
                current_sha256=published[1],  # 同一次原子指针字节SHA。
                coverage_qualified=quality['full_coverage'],  # 实际缓存的全池资格；部分覆盖明确为False。
                completed_at=datetime.now(timezone.utc).isoformat())  # 本地完成UTC时刻，区别来源交易日期。
            if price_result is not None:
                from .daily_price_continuation import requires_price_continuation
                state['continuation_required']=requires_price_continuation(price_result,request.get('prior_pending_symbols',()),
                    stock_plan=plan,stock_progress=state.get('gap_readback_progress'),deadline=deadline,cancelled=cancelled)
                # 原HPR未闭合且相关目标Native仍缺，后继同日修订沿原槽接续；发布成功独立保存。
            if supplement_complete is not None:
                state['supplement_complete'] = supplement_complete  # 补充要求窗口是否齐全，供原owner次自然日09:00修订。
            _save(journal, state)
            return state
        except BaseException as error:
            state.update(status='stopped' if isinstance(error, InterruptedError) else 'failed',
                         error_type=type(error).__name__)
            _save(journal, state)
            raise
        finally:
            if transport is not None:
                transport.close()
            if reference is not None:
                reference.close()
            if facts is not None:
                facts.close()


def _capture(source, request, directory, deadline,check=lambda:None):
    """同一原BatchAnalysisSource及原slot续核；完成manifest才成为价格输入。"""
    source.capture(request, directory, deadline=deadline, minimum_new_request_seconds=30,on_result=lambda *args:check())
    descriptor = _descriptor(directory / 'manifest.json')
    return dict(directory=str(directory), sha256=descriptor['sha256'])
