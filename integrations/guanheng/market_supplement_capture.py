"""同一WT日线owner的市场事实采集阶段；缓存优先，QMT准入先于外部回退。"""

from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
from pathlib import Path
import re
import time

from .daily_data_update import _save, _descriptor, _load
from .market_generation import encode


PLAN_FIELDS = (
    'schema',  # 固定QMT优先补充采集配置版本。
    'targets',  # 最多64个唯一metric/symbol，逐项from声明历史要求。
    'policy',  # qmt_preferred，未知请求继续核原身份。
    'external_fallback',  # 显式准入的SSE/SZSE/Eastmoney子集。
    'required',  # 缺事实时等待，false允许带缺口发布且不自动同日重入。
)
TARGET_FIELDS = (
    'metric',  # 独立补充事实类别，官方与代理分开。
    'symbol',  # ETF的WT标识或明确市场报告范围。
    'from',  # 要求覆盖起日ISO日期，实际截止为本轮闭合交易日。
)
OPTIONAL_PLAN_FIELDS = ('max_requests',)  # 本阶段每轮HTTP＋SDK请求份额，仍从原总预算扣账。


class SupplementPending(RuntimeError):
    """本固定任务尚有事实缺口；成功原件/原QMT请求保持，后继只补缺。"""


def validate_plan(value):
    """统一配置准入；显式target.from代表要求区间，不推测ETF上市前日期。"""
    from ..guanheng_market_client.supplement_facts import METRICS
    required = set(PLAN_FIELDS)
    if (type(value) is not dict or not required <= set(value) or set(value) - required - set(OPTIONAL_PLAN_FIELDS)
            or value['schema'] != 'guanheng.market-supplement-plan.v1'
            or value['policy'] != 'qmt_preferred' or type(value['required']) is not bool):
        raise ValueError('supplement plan invalid')
    if 'max_requests' in value and (type(value['max_requests']) is not int or not 1 <= value['max_requests'] <= 512):
        raise ValueError('supplement request share invalid')
    fallback = value['external_fallback']
    if (type(fallback) is not list or any(type(s) is not str or s not in ('SSE', 'SZSE', 'Eastmoney') for s in fallback)
            or len(fallback) != len(set(fallback))):
        raise ValueError('supplement external source policy invalid')
    targets = value['targets']
    if type(targets) is not list or not 1 <= len(targets) <= 64:
        raise ValueError('supplement targets invalid')
    seen = set()
    for target in targets:
        if type(target) is not dict or set(target) != set(TARGET_FIELDS):
            raise ValueError('supplement target fields invalid')
        metric, symbol, start = target['metric'], target['symbol'], target['from']
        if metric not in METRICS or type(symbol) is not str or type(start) is not str:
            raise ValueError('supplement target invalid')
        if date.fromisoformat(start).isoformat() != start:
            raise ValueError('supplement target date invalid')
        valid_symbol = (re.fullmatch(r'(SSE|SZSE)\.[0-9]{6}', symbol) is not None if metric == 'etf_total_shares'
                        else symbol == ('CN.MARGIN_REPORT' if metric == 'margin_balance' else 'CN.SH_SZ'))
        if not valid_symbol or (metric, symbol) in seen:
            raise ValueError('supplement target identity invalid')
        seen.add((metric, symbol))
    return value


def _key(day, metric, symbol):
    return '|'.join((day, metric, symbol))


def _fallback_sources(metric, symbol):
    if metric == 'etf_total_shares':
        return {'SSE' if symbol.startswith('SSE.') else 'SZSE'}
    if metric == 'margin_balance':
        return {'Eastmoney'}
    if metric == 'market_turnover':
        return {'SSE', 'SZSE'}
    return set()


def prior_supplement_catalogs(previous, task_directory, input_directory, day, *, objects, check):
    """固定同owner未发布任务的成功行；跨日复用原值，不接管原QMT未决槽。

    调用方持原publication租约。已有已发布目录优先；此前pending状态只贡献经完整
    proof闭包验证的成功行，缺口保持缺口。派生seed保存在本次输入目录，恢复读取
    该固定原件，不跟随后续旧任务状态。原slot消费确认由daily_input_recovery拥有。
    """
    from ..guanheng_market_client.supplement_facts import validate_supplement_catalog
    from .market_supplement_store import MarketSupplementStore
    root = Path(input_directory).absolute()
    final = root / 'SUPPLEMENT-PRIORS.json'
    if final.exists():
        value = _load(_descriptor(final))
        if value['schema'] != 'guanheng.supplement-priors.v1' or value['day'] != day:
            raise ValueError('supplement prior snapshot identity differs')
        return value['catalogs']
    catalogs = [] if previous is None else [previous]
    task_root = Path(task_directory).absolute()
    index_path = task_root / 'INDEX.json'
    if index_path.exists():
        index = _load(_descriptor(index_path))
        seen = set()
        for previous_day, entry in sorted(index.items(), reverse=True):
            check()
            if previous_day > day or entry.get('state') == 'published':
                continue
            for request in [entry.get('request'), *entry.get('history_requests', [])]:
                if request is None:
                    continue
                origin = Path(request).parent / 'inputs'
                if not origin.resolve().is_relative_to((task_root / previous_day).resolve()):
                    raise ValueError('supplement prior task path differs')
                work = origin / 'supplement'
                if origin.resolve() == root.resolve() or work in seen:
                    continue
                seen.add(work)
                state_path = work / 'STATE.json'
                if not state_path.exists():
                    continue
                intent = _load(_descriptor(work / 'REQUEST.json'))
                state = _load(_descriptor(state_path, maximum=33554432), 33554432)
                if state['request_sha256'] != hashlib.sha256(encode(intent)).hexdigest():
                    raise ValueError('supplement prior state identity differs')
                if not state['rows']:
                    continue
                if intent['day'] != previous_day or any(d > day for d in intent['dates']):
                    raise ValueError('supplement prior state date differs')
                validate_plan(intent['plan'])
                cells = sorted((d, t['metric'], t['symbol']) for d in intent['dates']
                               for t in intent['plan']['targets'] if t['from'] <= d)
                rows = [state['rows'][_key(*c)] for c in cells if _key(*c) in state['rows']]
                if len(rows) != len(state['rows']):
                    raise ValueError('supplement prior state rows differ')
                catalog = dict(
                    schema='guanheng.market-supplement-catalog.v1',  # 只读状态的标准事实投影。
                    raw_store=str(Path(objects.root).absolute()),  # 同一原件库，源proof仍指原对象。
                    targets=intent['plan']['targets'], dates=intent['dates'], policy='qmt_preferred',
                    qmt_evidence=_load(_descriptor(work / 'QMT-EVIDENCE.json')),
                    rows=rows,
                    gaps=[dict(date=d, metric=m, symbol=s, reason='prior_task_pending')
                          for d, m, s in cells if _key(d, m, s) not in state['rows']],
                    complete=len(rows) == len(cells))
                validate_supplement_catalog(catalog)
                seeds = root / 'supplement-priors'
                seeds.mkdir(exist_ok=True)
                path = seeds / ('%03d.json' % len(catalogs))
                _save(path, catalog)
                descriptor = _descriptor(path, maximum=33554432)
                store = MarketSupplementStore(descriptor, observation_date=day)
                try:
                    store.verify_sources(check=check)
                finally:
                    store.close()
                catalogs.append(descriptor)
    value = dict(schema='guanheng.supplement-priors.v1',  # 本次输入冻结的复用目录列表。
                 day=day,  # 本次闭合交易日；不把前日时点更新为本日。
                 catalogs=catalogs)  # 已发布优先，后接同owner未发布成功事实。
    _save(final, value)
    return catalogs


def _proxy_partitions(dates, limits):
    """按原profile的两种上限分块；日期集合固定后恢复不再按剩余行缩窄。"""
    maximum_rows = limits['max_rows']
    maximum_days = limits['max_calendar_days']
    parts, current = [], []
    for day in dates:
        if current and (len(current) >= maximum_rows
                        or (date.fromisoformat(day) - date.fromisoformat(current[0])).days + 1 > maximum_days):
            parts.append(current)
            current = []
        current.append(day)
    if current:
        parts.append(current)
    return parts


def _validate_proxy_plan(parts, dates):
    """恢复前核固定分块只覆盖原目标日和两个原指数，防状态漂移改变已派发读请求。"""
    if type(parts) is not list or not 1 <= len(parts) <= 2000:
        raise ValueError('supplement proxy plan invalid')
    seen = set()
    for index, part in enumerate(parts):
        if type(part) is not dict or set(part) != {'dates', 'requests'}:
            raise ValueError('supplement proxy partition fields differ')
        selected = part['dates']
        if (type(selected) is not list or not selected or selected != sorted(set(selected))
                or not set(selected) <= set(dates) or seen & set(selected)):
            raise ValueError('supplement proxy partition dates differ')
        seen.update(selected)
        if type(part['requests']) is not list or len(part['requests']) != 2:
            raise ValueError('supplement proxy requests differ')
        for symbol, request in zip(('000001.SH', '399106.SZ'), part['requests']):
            if type(request) is not dict or set(request) != {'arguments', 'slot'}:
                raise ValueError('supplement proxy request fields differ')
            args = request['arguments']
            if (type(args) is not dict or set(args) not in (
                    {'start_date','end_date','max_rows','adjustment','symbol'},
                    {'start_date','end_date','max_rows','adjustment','symbols'})
                    or args.get('symbol', args.get('symbols')) not in (symbol, [symbol])
                    or args['start_date'] != selected[0].replace('-', '')
                    or args['end_date'] != selected[-1].replace('-', '')
                    or args['adjustment'] != 'none' or type(args['max_rows']) is not int
                    or not 1 <= args['max_rows'] <= 2000
                    or request['slot'] != symbol + ('.json' if len(parts) == 1 else '.p%04d.json' % index)):
                raise ValueError('supplement proxy original arguments differ')


def collect_supplement(plan, day, calendar_dates, directory, *, objects, fetch, qmt_transport,
                       calendar_coverage, previous=None, deadline, cancelled=lambda: False):
    """原总预算内分配本阶段请求份额；串行调用结束后恢复原预算上限。

    max_requests省略时沿原预算。实际HTTP重试和SDK调用仍由同一个CollectionBudget
    计数，字节、单请求D、总D及取消均保持；该份额仅限制本轮工作，不取消后继日更。
    """
    validate_plan(plan)
    original = fetch.budget.max_requests
    if 'max_requests' in plan:
        fetch.budget.max_requests = min(original, fetch.budget.requests + plan['max_requests'])
    try:
        return _collect_supplement(plan, day, calendar_dates, directory, objects=objects, fetch=fetch,
            qmt_transport=qmt_transport, calendar_coverage=calendar_coverage, previous=previous,
            deadline=deadline, cancelled=cancelled)
    finally:
        fetch.budget.max_requests = original


def _collect_supplement(plan, day, calendar_dates, directory, *, objects, fetch, qmt_transport,
                       calendar_coverage, previous=None, deadline, cancelled=lambda: False):
    """原data owner持发布租约调用；目录可恢复，不创建线程/调度/数据库。

    objects为原ContentStore，fetch为沿总预算创建的原Fetcher，qmt_transport复用原
    bound运输。未知QMT结果向上传播；仅已核当前profile未暴露的事实才准入外部来源。
    calendar_coverage为原官方日历(coverage_start,coverage_end)两ISO日界，
    要求窗口须全部落在该范围；calendar_dates为同原件内的开市日，不能裁掉请求前段。
    返回固定目录descriptor；required缺项抛SupplementPending，UPDATE尚不冻结。
    """
    from guanheng_qmt_shm.read_retention_client import RetainedReadClient
    from guanheng_app.observation.source_fetch import SourceFailure
    from ..guanheng_market_client.supplement_facts import validate_supplement_catalog, validate_source_proof
    from .market_supplement_sources import collect_external, SourceUnavailable

    validate_plan(plan)
    if type(day) is not str or date.fromisoformat(day).isoformat() != day:
        raise ValueError('supplement observation date invalid')
    if type(calendar_coverage) not in (tuple, list) or len(calendar_coverage) != 2:
        raise ValueError('supplement calendar coverage invalid')
    for bound in calendar_coverage:
        if type(bound) is not str or date.fromisoformat(bound).isoformat() != bound:
            raise ValueError('supplement calendar coverage invalid')
    first, last = calendar_coverage
    if not first <= day <= last or any(not first <= t['from'] <= day for t in plan['targets']):
        raise ValueError('supplement target outside calendar coverage')
    if type(calendar_dates) not in (list, tuple):
        raise ValueError('supplement calendar invalid')
    for d in calendar_dates:
        if type(d) is not str or date.fromisoformat(d).isoformat() != d or not first <= d <= last:
            raise ValueError('supplement calendar date invalid')
    dates = [d for d in calendar_dates if d <= day and any(t['from'] <= d for t in plan['targets'])]
    if dates != sorted(set(dates)) or not 1 <= len(dates) <= 2000:
        raise ValueError('supplement calendar invalid')
    for d in dates:
        if type(d) is not str or date.fromisoformat(d).isoformat() != d:
            raise ValueError('supplement calendar date invalid')
    cells = [(d, t['metric'], t['symbol']) for d in dates for t in plan['targets'] if t['from'] <= d]
    cells.sort()
    if len(cells) > 60000:
        raise ValueError('supplement fact capacity')

    def check():
        if cancelled():
            raise InterruptedError('supplement collection stopped')
        if time.monotonic() >= deadline:
            raise TimeoutError('supplement collection deadline')

    root = Path(directory).absolute()
    root.mkdir(parents=True, exist_ok=True)
    intent = dict(schema='guanheng.supplement-capture-request.v1',  # 固定任务恢复合同。
                  plan=plan,  # 首次确认的目标/策略配置，恢复不得漂移。
                  day=day,  # 本次闭合交易日期，ISO日期。
                  dates=dates,  # 本轮官方交易日，升序唯一。
                  calendar_coverage=list(calendar_coverage),  # 原官方日历完整覆盖日界，恢复不可裁剪要求窗口。
                  previous=previous)  # 上一代固定目录身份或首次为空。
    request_path = root / 'REQUEST.json'
    if request_path.exists():
        if _load(_descriptor(request_path)) != intent:
            raise ValueError('supplement original request changed')
    else:
        _save(request_path, intent)
    final = root / 'catalog.json'
    if final.exists():
        catalog = validate_supplement_catalog(_load(_descriptor(final, maximum=33554432), 33554432))
        if catalog['targets'] != plan['targets'] or catalog['dates'] != dates:
            raise ValueError('supplement committed catalog changed')
        from .market_supplement_store import MarketSupplementStore
        restored = MarketSupplementStore(_descriptor(final, maximum=33554432), observation_date=day)
        try:
            restored.verify_sources(check=check)
        finally:
            restored.close()
        return _descriptor(final, maximum=33554432)
    state_path = root / 'STATE.json'
    state = _load(_descriptor(state_path, maximum=33554432), 33554432) if state_path.exists() else dict(
        schema='guanheng.supplement-capture-state.v1',  # 本任务进度，不复制账户或策略状态。
        request_sha256=hashlib.sha256(encode(intent)).hexdigest(),  # 固定请求身份。
        rows={},  # 已确认事实按date/metric/symbol保存，来源原件仍归ContentStore。
        requests={},  # 已成功HTTP原件引用，重启不重复采集同一目标。
        status='created')  # 当前采集状态，pending不代表已发布。
    if state.get('request_sha256') != hashlib.sha256(encode(intent)).hexdigest():
        raise ValueError('supplement progress identity changed')
    if previous is not None and not state['rows']:
        from .market_supplement_store import MarketSupplementStore
        wanted = {_key(*c) for c in cells}
        for descriptor in previous if isinstance(previous, list) else [previous]:
            verified = MarketSupplementStore(descriptor, observation_date=day)
            try:
                verified.verify_sources(check=check)
            finally:
                verified.close()
            old = validate_supplement_catalog(_load(descriptor, 33554432))
            if Path(old['raw_store']).resolve() != Path(objects.root).resolve():
                raise ValueError('supplement original object store changed')
            for row in old['rows']:
                check()
                key = _key(row['date'], row['metric'], row['symbol'])
                if key in wanted:
                    if key in state['rows']:
                        if any(state['rows'][key][k] != row[k] for k in ('value', 'unit', 'source')):
                            raise ValueError('supplement prior facts conflict')
                        continue
                    objects.get(row['source_sha256'])
                    state['rows'][key] = row
    check()
    client = RetainedReadClient(qmt_transport, lifetime_ms=30000)
    # 本轮先取得实际绑定；失败/未知直接保持任务，不能解释为没有该QMT能力。
    fetch.budget.request('sdk')
    metadata = client.metadata(deadline=min(deadline, fetch.budget.deadline))
    profile = metadata['profile']
    operations = sorted(profile['read_operations'])
    projection = dict(schema='guanheng.qmt-supplement-capability.v1',  # 无凭据的本轮能力原件投影。
                      profile_version=profile['read_profile_version'],  # 当前认证能力协议版本。
                      operations=operations,  # 当前实际开放的只读operation，升序。
                      binding_sha256=metadata['binding_sha256'],  # 本次已核QMT绑定摘要。
                      read_profile_body_sha256=metadata['read_profile_body_sha256'],  # 原能力正文摘要。
                      order_ready=False)  # 本接入仅消费行情，未取得交易资格。
    evidence_sha = objects.put(encode(projection))
    metrics = sorted({t['metric'] for t in plan['targets']})
    evidence = dict(source_sha256=evidence_sha, profile_version=profile['read_profile_version'],
                    operations=operations, decisions=[dict(metric=m, reason=(
                        'qmt_market_data_proxy' if m == 'market_turnover_proxy' and 'market.market_data' in operations
                        else 'not_exposed_by_bound_profile')) for m in metrics])
    _save(root / 'QMT-EVIDENCE.json', evidence)
    state['status'] = 'collecting'
    _save(state_path, state)

    requested_keys = set()  # 当前单元调用用到的原件，解析不合格时只清请求引用，原字节仍保留。

    def get(url, params, referer):
        check()
        key = hashlib.sha256(encode(dict(url=url, params=params, referer=referer))).hexdigest()
        requested_keys.add(key)
        if key in state['requests']:
            record = state['requests'][key]
            return dict(body=objects.get(record['sha256']), **record)
        body = fetch.get(url, params=params, referer=referer)
        record = dict(sha256=objects.put(body), received_at=datetime.now(timezone.utc).isoformat())
        state['requests'][key] = record
        _save(state_path, state)
        return dict(body=body, **record)

    def record_row(d, metric, symbol, result):
        check()
        proof = dict(schema='guanheng.supplement-source-proof.v1',  # 单/双原件的可追溯派生清单。
                     date=d, metric=metric, symbol=symbol, value=result['value'], unit=result['unit'],
                     source=result['source'], parents=result['parents'])
        validate_source_proof(proof)  # 每条标准事实准入后才写进度，避免非法值成为永久已完成行。
        for sha in proof['parents']:
            objects.get(sha)
        proof_sha = objects.put(encode(proof))
        state['rows'][_key(d, metric, symbol)] = dict(
            date=d, symbol=symbol, metric=metric, value=result['value'], unit=result['unit'],
            source=result['source'], source_sha256=proof_sha, received_at=result['received_at'], available_at=None)
        _save(state_path, state)

    reasons = {}  # 逐单元固定缺口原因，不把来源未知提升为没有厂商能力。
    # QMT当前唯一可用的市场事实是双指数amount代理，原持久请求和事实名保持。
    if 'market_turnover_proxy' in metrics and 'market.market_data' in operations:
        proxy_dates = [d for d, m, s in cells if m == 'market_turnover_proxy']
        needed = [d for d, m, s in cells if m == 'market_turnover_proxy' and _key(d, m, s) not in state['rows']]
        if needed:
            descriptor = profile['operation_profiles']['market.market_data']
            if 'proxy_plan' not in state:
                # 旧任务已有slot时先保持其完整原请求；新任务只请求真实缺失日期。
                legacy = next((root / 'qmt-slots' / (s + '.json') for s in ('000001.SH', '399106.SZ')
                               if (root / 'qmt-slots' / (s + '.json')).exists()), None)
                parts = [proxy_dates] if legacy is not None else _proxy_partitions(needed, descriptor['limits'])
                original_args = _load(_descriptor(legacy))['request']['arguments'] if legacy is not None else None
                state['proxy_plan'] = []  # 首次请求前写完整参数/日期，部分落盘后仍沿原slot。
                for index, part in enumerate(parts):
                    requests = []
                    for symbol in ('000001.SH', '399106.SZ'):
                        args = dict(start_date=part[0].replace('-', ''), end_date=part[-1].replace('-', ''),
                                    max_rows=len(part), adjustment='none') if original_args is None else dict(original_args)
                        symbol_field = 'symbols' if 'symbols' in args or profile['read_profile_version'] == 'qmt.read-profile.v8' else 'symbol'
                        args[symbol_field] = [symbol] if symbol_field == 'symbols' else symbol
                        requests.append(dict(arguments=args,  # 原profile准入的固定只读请求参数。
                                             slot=symbol + ('.json' if len(parts) == 1 else '.p%04d.json' % index)))  # 原槽文件名，不复用其他块身份。
                    state['proxy_plan'].append(dict(dates=part, requests=requests))  # 只负责该块目标日；源额外行不成为事实。
                _save(state_path, state)
            _validate_proxy_plan(state['proxy_plan'], proxy_dates)
            for part in state['proxy_plan']:
                required = [d for d in part['dates'] if _key(d, 'market_turnover_proxy', 'CN.SH_SZ') not in state['rows']]
                if not required:
                    continue
                captured = []
                proxy_budget_exhausted = False
                for request in part['requests']:
                    check()
                    args = request['arguments']
                    symbol = args.get('symbol') or args['symbols'][0]
                    try:
                        fetch.budget.request('sdk')
                        result = client.read('market.market_data', args, root / 'qmt-slots' / request['slot'],
                                             deadline=min(deadline, fetch.budget.deadline), expected_binding=metadata['binding'])
                    except SourceFailure as error:
                        if error.code not in ('collection_stopped', 'collection_timeout', 'request_budget_exceeded', 'capture_budget_exceeded'):
                            raise
                        for d in needed:
                            if _key(d, 'market_turnover_proxy', 'CN.SH_SZ') not in state['rows']:
                                reasons[_key(d, 'market_turnover_proxy', 'CN.SH_SZ')] = error.code
                        proxy_budget_exhausted = True
                        break
                    body = encode(result)
                    fetch.budget.consume(len(body))
                    sha = objects.put(body)
                    data = result['reply']['data']
                    data = data['securities'][symbol]['data'] if 'securities' in data else data[symbol]
                    captured.append((data, sha, result['received_at']))
                if proxy_budget_exhausted:
                    break
                for d in required:
                    tag = d.replace('-', '')
                    if any(tag not in group[0] for group in captured):
                        continue
                    amount = sum(Decimal(str(group[0][tag]['amount'])) for group in captured)
                    record_row(d, 'market_turnover_proxy', 'CN.SH_SZ', dict(
                        value=format(amount, 'f'), unit='unknown', source='QMT', parents=[x[1] for x in captured],
                        received_at=max(x[2] for x in captured)))

    # 最新事实先取，旧官方缺口只消费剩余原预算，避免历史断连饿死每日新增份额/融资。
    for d, metric, symbol in sorted(cells, key=lambda item: (-date.fromisoformat(item[0]).toordinal(), item[1], item[2])):
        key = _key(d, metric, symbol)
        if key in state['rows']:
            continue
        check()
        if metric == 'market_turnover_proxy':
            reasons.setdefault(key, 'qmt_proxy_source_gap' if 'market.market_data' in operations else 'not_exposed_by_bound_profile')
            continue
        sources = _fallback_sources(metric, symbol)
        if not sources or not sources <= set(plan['external_fallback']):
            reasons[key] = 'qmt_fact_not_exposed_external_not_allowed'
            continue
        requested_keys.clear()
        try:
            result = collect_external(metric, symbol, d, get)
            record_row(d, metric, symbol, result)
        except SourceUnavailable as error:
            # 错日/不全等不合格响应保留原字节，下一轮允许重新读取，避免坏缓存永久封死补齐。
            for cached in requested_keys:
                state['requests'].pop(cached, None)
            reasons[key] = error.code
            _save(state_path, state)
        except SourceFailure as error:
            reasons[key] = error.code
            if error.code in ('collection_stopped', 'collection_timeout', 'request_budget_exceeded', 'capture_budget_exceeded'):
                break
    catalog = dict(
        schema='guanheng.market-supplement-catalog.v1',  # 独立于股票八字段事实。
        raw_store=str(Path(objects.root).absolute()),  # 原对象库位置，不另建第二套数据库。
        targets=plan['targets'], dates=dates, policy=plan['policy'], qmt_evidence=evidence,
        rows=[state['rows'][_key(*c)] for c in cells if _key(*c) in state['rows']],
        gaps=[dict(date=d, metric=m, symbol=s, reason=reasons.get(_key(d, m, s), 'cycle_budget_or_source_gap'))
              for d, m, s in cells if _key(d, m, s) not in state['rows']],
        complete=all(_key(*c) in state['rows'] for c in cells))
    validate_supplement_catalog(catalog)
    state['status'] = 'complete' if catalog['complete'] else 'pending'
    _save(state_path, state)
    _save(root / 'COVERAGE.json', dict(complete=catalog['complete'], expected=len(cells),
                                      observed=len(catalog['rows']), gaps=catalog['gaps']))
    # 缺口先留存，取消/总截止仍由原owner优先决定本轮终态，不能被required等待覆盖。
    check()
    if plan['required'] and not catalog['complete']:
        raise SupplementPending('supplement source history remains incomplete')
    if len(encode(catalog)) > 33554432:
        raise ValueError('supplement catalog byte capacity')
    _save(final, catalog)
    return _descriptor(final, maximum=33554432)
