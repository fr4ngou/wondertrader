"""同一观察调度器核对覆盖，只通过已接入的 WT 来源补齐。"""

from datetime import date, datetime, timedelta
from time import monotonic

from guanheng_market_client.supplement_facts import MARGIN_SUMMARY_FIELDS, SHENWAN_FIELDS

from . import wt_margin_summary, wt_shenwan_source, wt_shsz_pb
from .contracts import ObservationError
from .collection_config import WT_DERIVED
from .etf_flow import CAP_KIND, ETF_KINDS, cap_row_complete
from .gov10y_source import WT_KIND as WT_GOV10Y
from .market_structure_source import WT_INDEX_KIND, WT_STOCK_KIND, index_row_complete
from .schedule_policy import closed_market_day, source_as_of
from .source_fetch import SourceFailure

WT_SOURCES = frozenset(('wondertrader', 'wt_breadth', 'wt_t2108', WT_GOV10Y, wt_margin_summary.KIND, wt_shsz_pb.KIND,
                        wt_shenwan_source.KIND,
                        *ETF_KINDS, WT_INDEX_KIND, WT_STOCK_KIND, *WT_DERIVED))


def _coverage_by_input(reader, manifest, source, target, check):
    """按实际表或指标核对缺日，保留输入身份。"""
    tables = manifest.get('source_tables', {})
    calendar = tables.get('source.cn_official_calendar')
    if not calendar:
        raise SourceFailure('official_calendar_required')
    open_days = sorted(row['date'] for row in reader.rows(calendar)
                       if row['is_open'] and row['date'] <= target)
    if target not in open_days:
        raise SourceFailure('official_calendar_outside_coverage')
    if source['kind'] == wt_shsz_pb.KIND:
        gaps = {}
        for key in wt_shsz_pb.coverage_tables(source):
            check()
            partition = tables.get(key)
            observed = {row['date'] for row in reader.rows(partition)} if partition else set()
            missing = [day for day in open_days if day >= source['history_from'] and day not in observed]
            if missing:
                gaps[key] = missing
        return gaps
    if source['kind'] in (wt_margin_summary.KIND, wt_shenwan_source.KIND):
        check()
        margin = source['kind'] == wt_margin_summary.KIND
        partition = tables.get(wt_margin_summary.TABLE if margin else wt_shenwan_source.TABLE)
        fields = (MARGIN_SUMMARY_FIELDS if margin else
                  {metric: field for metric, (field, _, _) in SHENWAN_FIELDS.items()})
        rows = reader.rows(partition) if partition else ()
        by_day = {row['date']: row for row in rows}
        expected = [day for day in open_days if day >= source['history_from']]
        return {metric: missing for metric, field in fields.items()
                if (missing := [day for day in expected if by_day.get(day, {}).get(field) is None])}
    if source['kind']=='wt_t2108':
        # 同一指标及其定日股池须在同一历史区间内均有归档。
        inputs={}
        for key in source.get('tables', []):
            check()
            inputs[key]=reader.rows(tables[key]) if key in tables else ()
        for key in source.get('datasets', []):
            check()
            dataset=manifest['datasets'].get(key)
            inputs[key]=reader.rows(dataset['partition']) if dataset else ()
        observed={key:{row['date'] for row in rows if row['date']<=target} for key,rows in inputs.items()}
        first=min((day for dates in observed.values() for day in dates),default=target)
        expected={day for day in open_days if day>=first}
        return {key:sorted(expected-dates) for key,dates in observed.items() if expected-dates}
    missing = {}
    for key in source.get('tables', []):
        check()
        rows = reader.rows(tables[key]) if key in tables else ()
        observed = {row['date'] for row in rows if row['date'] <= target
                    and (source['kind'] != WT_GOV10Y or row.get('gov10y_pct') is not None)
                    and (source['kind'] != WT_STOCK_KIND or row.get('sample_count') is not None)
                    and (source['kind'] != WT_INDEX_KIND or index_row_complete(key, row))}
        lower = source.get('history_from', min(observed, default=target))
        missing[key] = [day for day in open_days if day >= lower and day not in observed]
    for key in source.get('datasets', []):
        check()
        item = manifest['datasets'].get(key)
        if item is None:
            if source['kind'] in (*ETF_KINDS,*WT_DERIVED):
                missing[key] = [day for day in open_days if day >= source['history_from']]
            else:
                missing[key] = [target]
            continue
        rows = reader.rows(item['partition'])
        if source['kind'] in WT_DERIVED:
            derived = WT_DERIVED[source['kind']]
            by_day = {row['date']:row for row in rows}
            for day in open_days:
                if day < source['history_from']:
                    continue
                row = by_day.get(day)
                if row is None:
                    missing.setdefault(key, []).append(day)
                elif not derived.row_complete(row):
                    for input_id in derived.missing_inputs(row):
                        missing.setdefault(input_id, []).append(day)
            continue
        if source['kind'] in ETF_KINDS:
            lower = source['history_from']
            observed = {row['date'] for row in rows if (cap_row_complete(row) if source['kind']==CAP_KIND
                                                       else row.get('flow') is not None)}
            missing[key] = [day for day in open_days if day >= lower and day not in observed]
            continue
        # 例如 TRIN 在全涨或全跌日按指标定义留空，交易日覆盖由原日表核对。
        if not any(row['date'] == target for row in rows):
            missing[key] = [target]
    return {key: dates for key, dates in missing.items() if dates}


def _coverage(reader, manifest, source, target, check, *, item=None):
    by_input = _coverage_by_input(reader, manifest, source, target, check)
    missing = sorted({day for dates in by_input.values() for day in dates})
    if item is not None:
        item['missing_count'] = len(missing)
        item['inputs'] = [dict(
            id=key,  # 缺口所属源表或指标，沿稳定登记 ID。
            missing_count=len(dates),  # 该输入缺失的交易日数。
            first_missing=dates[0],  # 实际最早缺日，ISO 交易日。
            last_missing=dates[-1],  # 实际最晚缺日，ISO 交易日。
        ) for key, dates in by_input.items()]
    return missing


def repair(reader, config, job, now, *, lease, deadline, cancelled, refresh, market_client_factory, window=None):
    """重启后以最新快照重新核对同一任务，已发布结果直接通过覆盖检查。"""
    repository = reader.repository
    upstream = job.get('wt_receipt', {}).get('state')
    if job.get('wt_request') and upstream not in ('published', 'failed'):
        # WT 可跨多轮完成。长时间无终态的请求以遗留缺口退出，让用户能够重新触发。
        age = (now - datetime.fromisoformat(job['wt_request']['requested_at'])).total_seconds()
        if age < 86400:
            return
        upstream = 'failed'
    from .source_fetch import CollectionBudget
    check = CollectionBudget(deadline, cancelled=cancelled).remaining
    # 跨进程恢复继续原候选进度，逐项从新发布版本重新核对。
    start_after = job.get('start_after')
    if start_after:
        first = next((i for i, source in enumerate(config['sources']) if source['id'] == start_after), 0)
    else:
        first = 0
    previous_items = {item['source_id']: item for item in job['items']}
    if 'scan_clock' not in job:
        job.setdefault('window', window)  # 旧活动任务保留原计划窗口。
        original = job.get('wt_request', {}).get('requested_at')
        if original is None and job['state'] == 'running':
            original = job.get('window') or job['requested_at']
        scheduled = job['window'] if job['trigger'] == 'scheduled' else None
        job['scan_clock'] = scheduled or original or now.isoformat()
    scan_clock = datetime.fromisoformat(job['scan_clock'])
    job['state'] = 'running'
    job['items'] = [
        previous_items.get(source['id'], dict(source_id=source['id'], state='pending', missing_count=None, reason=None))
        if index < first else dict(source_id=source['id'], state='pending', missing_count=None, reason=None)
        for index, source in enumerate(config['sources'])
    ]
    repository.record_data_repair(job, lease=lease)
    try:
        as_of = closed_market_day(scan_clock, 'cn', config['models'], check=check)
    except SourceFailure as error:
        job.update(state='failed', reason=error.code)
        repository.record_data_repair(job, lease=lease)
        return

    items = job['items']
    sources = config['sources']
    timed_out = False
    for source, item in zip(sources[first:], items[first:]):
        if cancelled():
            return
        if monotonic() >= deadline:
            job['start_after'] = source['id']
            timed_out = True
            break
        if source['kind'] not in WT_SOURCES:
            item.update(state='waiting_for_wt', reason='wt_source_not_registered')
            continue
        item['state'] = 'checking'
        repository.record_data_repair(job, lease=lease)
        try:
            target = source_as_of(source, as_of, config, scan_clock, check=check)
            missing = _coverage(reader, reader.snapshot()[1], source, target, check, item=item)
            scan = job.setdefault('scan', {})  # 本任务的来源扫描位置，跨调度循环恢复。
            checkpoint = scan.get(source['id'])
            if checkpoint is None or checkpoint['phase'] != upstream:
                requested_start = job.get('wt_request', {}).get('source_starts', {}).get(source['id'])
                first_day = requested_start or (missing[0] if missing else None)
                checkpoint = dict(phase=upstream, first=first_day, next=first_day)
                scan[source['id']] = checkpoint
            selected = next((day for day in missing if checkpoint['next'] and day >= checkpoint['next']), None)
            while selected is not None:
                if cancelled():
                    return
                if monotonic() >= deadline:
                    job['start_after'] = source['id']
                    timed_out = True
                    break
                cap = checkpoint.get('end')
                if cap and selected > cap:
                    checkpoint.pop('end')
                    cap = None
                item['state'] = 'repairing'
                repository.record_data_repair(job, lease=lease)
                window_args = {'repair_history_end': cap} if cap else {}
                result = refresh(reader, config, as_of=target, now=now, source_ids=[source['id']],
                                 deadline=deadline, cancelled=cancelled, market_client_factory=market_client_factory,
                                 repair_history_start=selected, **window_args)
                receipt = next(iter(result.get('sources', [])), {})
                last = receipt.get('requested_end')
                error = receipt.get('error_code') or result.get('error_code')
                if cancelled():
                    return
                if (source['kind'] in (WT_STOCK_KIND, 'wt_breadth') and error in (
                        'collection_timeout', 'request_budget_exceeded', 'capture_budget_exceeded',
                        'wt_market_history_capacity')
                        and last and last > selected):
                    first_day, last_day = date.fromisoformat(selected), date.fromisoformat(last)
                    checkpoint['end'] = (first_day + timedelta(days=(last_day-first_day).days//2)).isoformat()
                    checkpoint['next'] = selected
                    repository.record_data_repair(job, lease=lease)
                    continue
                if (monotonic() >= deadline or result.get('status') in ('another_owner_running', 'publication_unknown')
                        or result.get('error_code') in ('publication_conflict', 'write_outcome_unknown')
                        or (error == 'collection_timeout' and (not last or source['kind']=='wt_t2108'))):
                    job['start_after'] = source['id']
                    timed_out = True
                    break
                missing = _coverage(reader, reader.snapshot()[1], source, target, check, item=item)
                item['reason'] = (error or 'wt_history_incomplete') if missing else None
                selected = next((day for day in missing if last and last >= selected and day > last), None)
                checkpoint['next'] = selected
                checkpoint.pop('end', None)
                repository.record_data_repair(job, lease=lease)
            if timed_out:
                break
            if missing and upstream is None and config.get('schedule', {}).get('wt_repair_enabled'):
                item['state'] = 'waiting_for_wt_repair'
                item['wt_target'] = target  # 该来源实际要求的闭合交易日。
                item['wt_start'] = checkpoint['first'] or missing[0]  # 收到回执后复核本扫描窗口。
                continue
            if missing:
                item['reason'] = 'wt_repair_failed' if upstream == 'failed' else item['reason'] or 'wt_history_incomplete'
            item['state'] = 'missing' if missing else 'complete'
        except (SourceFailure, ObservationError) as error:
            if error.code == 'collection_timeout':
                job['start_after'] = source['id']
                timed_out = True
                break
            item.update(state='missing', reason=error.code)
    if not cancelled():
        if not timed_out:
            job.pop('start_after', None)
            targets = sorted({item['wt_target'] for item in items if item['state'] == 'waiting_for_wt_repair'})
            if targets:
                job['wt_request'] = dict(
                    dates=targets,  # 各来源闭合目标日证据，授权范围由 WT 配置拥有。
                    source_starts={item['source_id']: item['wt_start'] for item in items
                                   if item['state'] == 'waiting_for_wt_repair'},  # 观衡复查的窗口起日。
                    requested_at=now.isoformat(),  # 进入 WT 队列时间，供等待过期及恢复判定。
                )
            else:
                job['state'] = 'complete' if all(item['state'] == 'complete' for item in items) else 'partial'
                job.pop('scan', None)
        repository.record_data_repair(job, lease=lease)
