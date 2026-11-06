"""终端外采集沪深交易所辅助事实，按来源/日期保存可重用的原文。

本入口只读公开数据，不操作QMT、账户或策略；不推定历史首次发布时间。
实际采集时刻与来源统计日分别落盘，派生与使用资格由消费者明确声明。
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from decimal import Decimal, DecimalException
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .source import write_json
from .auxiliary_store import (SOURCES, MAX_BODY_BYTES, read_capture, commit_capture, validate_key,
    capture_signature)

MAX_RESPONSE = MAX_BODY_BYTES


def source_request(source, day):
    """固定公开报表及日期参数；单位和结果日期在解析边界再次核对。"""
    validate_key(source, day)
    if source.startswith('sse-'):
        origin = 'https://query.sse.com.cn'
        referer = 'https://www.sse.com.cn/'
        if source == 'sse-margin':
            path = '/marketdata/tradedata/queryMargin.do'
            params = dict(isPagination='true', beginDate=day.replace('-', ''), endDate=day.replace('-', ''))
        else:
            path = '/commonQuery.do'
            params = {'isPagination': 'true', 'pageHelp.pageSize': '10000', 'pageHelp.pageNo': '1'}
            if source == 'sse-shares':
                params.update(sqlId='COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L', STAT_DATE=day)
            else:
                params.update(sqlId='COMMON_SSE_SJ_GPSJ_CJGK_MRGK_C', PRODUCT_CODE='01,02,03,11,17',
                              type='inParams', SEARCH_DATE=day)
    else:
        origin, path, referer = 'https://www.szse.cn', '/api/report/ShowReport/data', 'https://www.szse.cn/'
        params = dict(SHOWTYPE='JSON', TABKEY='tab1')
        if source == 'szse-turnover':
            params.update(CATALOGID='1803_sczm', txtQueryDate=day)
        elif source == 'szse-margin':
            params.update(CATALOGID='1837_xxpl', txtDate=day)
        else:
            raise ValueError('unknown_auxiliary_source')
    return origin+path+'?'+urlencode(params), referer


def positive(value):
    number = Decimal(str(value).replace(',', '').strip())
    if number == 0:
        raise ValueError('auxiliary_source_zero')
    if not number.is_finite() or number < 0:
        raise ValueError('auxiliary_source_number')
    return number


def unique(rows):
    if len(rows) != 1:
        raise ValueError('auxiliary_source_unique_row')
    return rows[0]


def parse_source(source, day, body, symbols):
    """返回来源规范值：份额亿份，成交额/融资余额亿元；不混用融资融券合计。"""
    validate_key(source, day)
    try:
        return _parse_source(source, day, body, symbols)
    except (KeyError, TypeError, AttributeError, DecimalException, json.JSONDecodeError):
        raise ValueError('auxiliary_source_schema') from None


def _parse_source(source, day, body, symbols):
    """唯一报表字段解释；单位/日期不符与尚未发布分别保持可定位原因。"""
    value = json.loads(body)
    if source.startswith('sse-'):
        rows = value.get('result')
        if type(rows) is not list:
            raise ValueError('auxiliary_source_schema')
        if not rows:
            raise ValueError('auxiliary_source_not_published')
        if source == 'sse-shares':
            found = {}
            for row in rows:
                symbol = str(row.get('SEC_CODE', ''))+'.SH'
                if symbol not in symbols:
                    continue
                if row.get('STAT_DATE') != day or symbol in found:
                    raise ValueError('auxiliary_source_date_or_duplicate')
                # 交易所规模表TOT_VOL为万份；保留十进制，转换成原策略亿份。
                found[symbol] = str(positive(row['TOT_VOL'])/Decimal(10000))
            if not found:
                raise ValueError('auxiliary_source_symbols_missing')
            return found
        if source == 'sse-turnover':
            row = unique([r for r in rows if str(r.get('PRODUCT_CODE')) == '17'])
            if row.get('TRADE_DATE') != day.replace('-', ''):
                raise ValueError('auxiliary_source_date')
            return str(positive(row['TRADE_AMT']))
        row = unique(rows)
        if row.get('opDate') != day.replace('-', ''):
            raise ValueError('auxiliary_source_date')
        return str(positive(row['rzye'])/Decimal(100000000))
    tab = unique([t for t in value if t.get('metadata', {}).get('tabkey') == 'tab1'])
    meta = tab['metadata']
    name = 'txtQueryDate' if source == 'szse-turnover' else 'txtDate'
    condition = unique([c for c in meta.get('conditions', []) if c.get('name') == name])
    if condition.get('defaultValue') != day:
        raise ValueError('auxiliary_source_date')
    field = 'cjje' if source == 'szse-turnover' else 'jrrzye'
    if '亿元' not in meta.get('cols', {}).get(field, ''):
        raise ValueError('auxiliary_source_unit')
    rows = tab['data']
    if not rows:
        raise ValueError('auxiliary_source_not_published')
    row = unique([r for r in rows if r.get('lbmc') == '股票']) if source == 'szse-turnover' else unique(rows)
    return str(positive(row[field]))


def source_failure(error):
    """只输出固定原因及异常类型，服务器正文与URL不进入诊断。"""
    known = {'auxiliary_source_schema', 'auxiliary_source_not_published',
        'auxiliary_source_date_or_duplicate', 'auxiliary_source_symbols_missing',
        'auxiliary_source_date', 'auxiliary_source_unit', 'auxiliary_source_unique_row',
        'auxiliary_source_number', 'auxiliary_source_zero', 'auxiliary_source_http', 'auxiliary_source_response_capacity',
        'auxiliary_cache_identity', 'auxiliary_cache_values', 'auxiliary_source_clock'}
    reason = str(error) if type(error) is ValueError and str(error) in known else 'request_failed'
    return dict(type=type(error).__name__, reason=reason)


def capture(source, day, root, symbols, *, timeout=15, refresh=False, seed_root=None):
    """取得或重核某日来源；修订保留原文，失败保持上次有效值及原时钟。"""
    url, referer = source_request(source, day)
    record = read_capture(root, source, day, parse_source)
    if record is None and seed_root is not None:
        record = read_capture(seed_root, source, day, parse_source)
    if record is not None:
        if record.get('url') != url:
            raise ValueError('auxiliary_cache_identity')
        if not refresh:
            return record
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': referer})
    deadline = time.monotonic()+timeout
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError('auxiliary_source_http')
        blocks, size = [], 0
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('auxiliary_source_deadline')
            block = response.read1(min(65536, MAX_RESPONSE+1-size))
            if not block:
                break
            blocks.append(block)
            size += len(block)
            if size > MAX_RESPONSE:
                raise ValueError('auxiliary_source_response_capacity')
        body = b''.join(blocks)
    if len(body) > MAX_RESPONSE:
        raise ValueError('auxiliary_source_response_capacity')
    received = datetime.now(timezone.utc).isoformat()
    values = parse_source(source, day, body, symbols)
    return commit_capture(root, source, day, body, values, received, record, url=url)


def capture_dates(days, symbols, root, *, workers=2):
    """有限补齐独占同一辅助根；常驻Owner运行时CLI不能竞争写入该根。"""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    from guanheng_wt_runtime.__main__ import _InstanceLease
    with _InstanceLease(root, 'auxiliary'):
        return _capture_dates(days, symbols, root, workers=workers)


def _capture_dates(days, symbols, root, *, workers):
    """有界并行有限补齐；每个日期线程串行访问五来源，成功回执持续提交。"""
    days = sorted(set(days))
    if workers not in (1, 2, 3, 4) or len(days) > 4096:
        raise ValueError('auxiliary_capture_capacity')
    completed, failures = {}, {}

    def one(day):
        records, errors = {}, {}
        for source in SOURCES:
            try:
                records[source] = capture(source, day, root, symbols)
            except Exception as error:
                # 不输出服务器正文；精确来源及异常类别足以重试同一只读日期。
                errors[source] = source_failure(error)
            time.sleep(.15)
        return day, records, errors

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, day) for day in sorted(set(days), reverse=True)]
        for future in as_completed(futures):
            day, records, errors = future.result()
            completed[day] = records
            if errors:
                failures[day] = errors
            # 仅日期/成功计数写进度，完整数据按独立日期保留，内存与磁盘均有输入上界。
            write_json(root/'PROGRESS.json', dict(schema='guanheng.auxiliary-capture-progress.v1',
                planned_days=len(days), processed_days=len(completed), complete_days=sum(len(v) == len(SOURCES) for v in completed.values()),
                failed_days=len(failures), last_day=day, updated_at=datetime.now(timezone.utc).isoformat(),
                finished=len(completed) == len(days)))
    write_json(root/'FAILURES.json', failures)
    return completed


def observed_publications(root, days, *, cache=None, seed_root=None):
    """从已提交原文重建可用于后续决策的事实，使用本系统实际取得时刻。

    历史首次可知未知的记录不会回填历史available_at。一次补齐过去多年数据时，
    历史数值可作为分位计算前缀；策略生效仍在真实采集时刻之后。
    """
    from guanheng_strategy_v1.auxiliary import AuxiliaryPublication
    result = []
    root = Path(root)
    for day in sorted(set(days)):
        records = {}
        for source in SOURCES:
            path = root/source/(day+'.json')
            if not path.exists() and seed_root is not None:
                path = Path(seed_root)/source/(day+'.json')
            if not path.exists():
                continue
            cached = cache.get(str(path)) if cache is not None else None
            if cached is not None and cached[0] == capture_signature(path.parent.parent, source, day, cached[1]):
                records[source] = cached[1]
                continue
            record = read_capture(path.parent.parent, source, day, parse_source)
            if record['url'] != source_request(source, day)[0]:
                raise ValueError('auxiliary_cache_identity')
            records[source] = record
            if cache is not None:
                cache[str(path)] = (capture_signature(path.parent.parent, source, day, record), record)
        statistic_date = date.fromisoformat(day)
        shares = records.get('sse-shares')
        if shares:
            received = datetime.fromisoformat(shares.get('effective_received_at', shares['received_at']))
            for symbol, number in shares['values'].items():
                result.append(AuxiliaryPublication('shares', statistic_date, float(number),
                    None, received, shares['body_sha256'], symbol))
        for kind in ('turnover', 'margin'):
            pair = [records.get(exchange+'-'+kind) for exchange in ('sse', 'szse')]
            if not all(pair):
                continue
            received = max(datetime.fromisoformat(r.get('effective_received_at', r['received_at'])) for r in pair)
            identity = hashlib.sha256(json.dumps([r['body_sha256'] for r in pair], separators=(',', ':')).encode()).hexdigest()
            total = sum(Decimal(r['values']) for r in pair)
            result.append(AuxiliaryPublication(kind, statistic_date, float(total), None, received, identity))
    if cache is not None:
        # 缓存属于该发布Owner，仅保留本次历史范围内的最多5*4096个原件摘要。
        roots = (root,) if seed_root is None else (root, Path(seed_root))
        active = {str(base/source/(day+'.json')) for base in roots for day in days for source in SOURCES}
        for key in tuple(cache):
            if key not in active:
                del cache[key]
    return tuple(result)


def enrich_window(window, root, *, cache=None, seed_root=None, history_snapshot=None):
    """将已实际取得的辅助值合并到原值历史；前复权行情保持原Owner结果。"""
    from copy import deepcopy
    from guanheng_strategy_core.models import DailyObservation
    from guanheng_strategy_v1.auxiliary import merge_auxiliary, auxiliary_coverage
    from guanheng_strategy_v1.current_auxiliary import build_current_auxiliary
    rows = window['history']['observations']
    days = sorted({r['trade_date'] for r in rows})
    publications = (observed_publications(root, days, cache=cache, seed_root=seed_root)
                    if root is not None else ())
    history_report = None
    if history_snapshot is not None:
        from .auxiliary_history import fill_history
        publications, history_report = fill_history(publications, history_snapshot,
            days={date.fromisoformat(day) for day in days}, symbols={row['symbol'] for row in rows})

    def observation(raw):
        value = dict(raw)
        value['trade_date'] = date.fromisoformat(value['trade_date'])
        for key in ('market_available_at', 'auxiliary_available_at'):
            if value.get(key):
                value[key] = datetime.fromisoformat(value[key])
        for key in ('auxiliary_source_dates', 'evidence_refs'):
            if key in value:
                value[key] = tuple(date.fromisoformat(d) for d in value[key]) if key.endswith('dates') else tuple(value[key])
        return DailyObservation(**value)

    before = tuple(observation(row) for row in rows)
    after = merge_auxiliary(before, publications)
    names = ('shares_delta_yi', 'share_probability', 'turnover_percentile', 'margin_percentile',
             'auxiliary_available_at', 'auxiliary_source_dates', 'auxiliary_source_sha256', 'evidence_refs')
    updated = deepcopy(window)
    count = 0
    for original, merged, target in zip(before, after, updated['history']['observations']):
        if original == merged:
            continue
        count += 1
        for name in names:
            value = getattr(merged, name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, tuple):
                value = [str(v) for v in value]
            target[name] = value
    report = dict(schema='guanheng.auxiliary-window-merge.v1', publications=len(publications), enriched_rows=count,
        availability_basis='actually-received', historical_first_available='unknown',
        first_received_at=min((p.received_at.isoformat() for p in publications), default=None),
        fields=auxiliary_coverage(after, publications))
    if history_report is not None:
        report['history_snapshot'] = history_report
    if count:
        identity = hashlib.sha256(json.dumps(updated['history'], sort_keys=True, separators=(',', ':'),
                                            allow_nan=False).encode()).hexdigest()
        updated['references'].append(dict(report, history_sha256=identity))
        updated['qualification'] = ('current-visible native price analysis; auxiliary facts actually received; '
                                    'historical first visibility unknown')
    # 独立当前视图只携带已取得的事实；历史行保留原逐bar收盘因果。
    # 身份由数据、依赖及实际行情基准构成，周期轮询时间不制造事实修订。
    current = build_current_auxiliary(publications, [date.fromisoformat(day) for day in days])
    updated['current_auxiliary'] = current.to_dict()
    report['current_auxiliary'] = dict(schema=current.schema, sha256=current.sha256,
        basis_date=current.basis_date.isoformat(), values=len(current.values))
    # input_sha256专属于原Native价格/因子输入，Reader须与NATIVE-READ收据逐值核对。
    # 辅助修订由current.sha256、历史reference及完整publication/纯核规范输入摘要承担。
    return updated, report


def main():
    parser = argparse.ArgumentParser(description='只读采集沪深交易所策略辅助数据')
    parser.add_argument('--market-window', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--recent-days', type=int)
    args = parser.parse_args()
    window = json.loads(args.market_window.read_bytes())
    rows = window['history']['observations']
    days = sorted({row['trade_date'] for row in rows})
    if args.recent_days is not None:
        if args.recent_days < 1:
            parser.error('recent-days需要正整数')
        days = days[-args.recent_days:]
    symbols = {row['symbol'] for row in rows if row['symbol'].endswith('.SH')}
    capture_dates(days, symbols, args.directory, workers=args.workers)


if __name__ == '__main__':
    main()
