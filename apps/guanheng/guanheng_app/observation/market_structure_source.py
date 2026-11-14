"""官方指数和全市场日终横截面的只读观察输入。"""
from datetime import date, datetime, timezone
import json
import math
import os
import re
from statistics import median
from time import monotonic

from guanheng_market_client import MarketHTTPError, MarketUnavailable
from guanheng_market_client.supplement_facts import INDEX_TURNOVER, SMALL_CAP_INDEX

from .calendars import official_calendar
from .source_fetch import SourceFailure
from .storage import encode

CSI_URL = 'https://www.csindex.com.cn/csindex-home/perf/index-perf'
TUSHARE_URL = 'https://api.tushare.pro'
INDEX_TABLES = {code: 'source.market_structure.' + code for code in ('000688', '000300', '932000')}
STOCK_TABLE = 'source.market_structure.stock'
STOCK_FIELDS = ['ts_code', 'trade_date', 'pct_chg', 'amount']
A_SHARE = re.compile(r'(?:(?:600|601|603|605|688)\d{3}\.SH|(?:00[0-3]|30[01])\d{3}\.SZ|(?:43|8[2378]|92)\d{4}\.BJ)')
CSI_KIND = 'market_structure_csi'
STOCK_KIND = 'market_structure_stock'
WT_STOCK_KIND = 'wt_market_structure_stock'
WT_INDEX_KIND = 'wt_market_structure_index'
INDEX_SYMBOLS = {'SSE.' + code: table for code, table in INDEX_TABLES.items()}
SMALL_CAP_TABLE = INDEX_TABLES['932000']
FIRST_DAY = '2023-08-11'
# 已实测当前供应商日线额度为每分钟50次。为同一账号其他读者保留余量。
STOCK_REQUEST_INTERVAL = 1.5


def wt_snapshot(request, snapshot_dates):
    """查询已知发布候选，固定返回的 WT 版本供整批读取。"""
    for day in snapshot_dates:
        snapshot = request(day)
        if snapshot is None:
            continue
        if snapshot['observation_date'] != day:
            raise SourceFailure('wt_market_snapshot_date_differs')
        return snapshot
    raise SourceFailure('wt_market_snapshot_unavailable')


def wt_index_history(fetch, start, end, calendar, client_factory, *, snapshot_dates):
    """固定 WT 版本读指数点位，按原来源元数据接纳可核的成交额。"""
    check = fetch.budget.remaining
    if not calendar['coverage_start'] <= start <= end <= min(snapshot_dates) <= max(snapshot_dates) <= calendar['coverage_end']:
        raise SourceFailure('official_calendar_outside_coverage')
    sessions, _ = official_calendar(calendar, check=check)
    days = {int(row['date'].replace('-', '')): row['date']
            for row in sessions if row['is_open'] and start <= row['date'] <= end}
    results = {table: [] for table in INDEX_TABLES.values()}
    if not days:
        return results

    def request(kind, call, *, absent=()):
        fetch.budget.request(kind='sdk')
        try:
            response = call(client_factory(min(fetch.timeout, check())))
        except MarketHTTPError as error:
            response = error.response
            if response['status']['code'] not in absent:
                raise
        body = encode(response)
        fetch.budget.consume(len(body))
        fetch.records.append(dict(kind=kind, sha256=fetch.objects.put(body), source_host='wondertrader',
                                  status=200, retrieved_at=datetime.now(timezone.utc).isoformat(),
                                  media_type='application/json'))
        if response['status']['code'] in absent:
            return None
        if response['status']['code'] != 'Ok':
            raise SourceFailure('wt_market_index_unavailable')
        return response['data']

    snapshot = wt_snapshot(lambda day: request('wt_market_structure_snapshot',
        lambda client: client.source_market_snapshot_query(day), absent=('Unavailable',)), snapshot_dates)
    identity = snapshot['snapshot_id']
    batch = request('wt_source_daily_history_batch', lambda client: client.source_daily_history_batch_query(dict(
        symbols=sorted(INDEX_SYMBOLS), **{'from': min(days), 'to': max(days)}, limit=len(days),
        adjustment='none', snapshot_id=identity)))
    for item in batch['results']:
        if item['status']['code'] == 'Unavailable':
            continue
        if item['status']['code'] != 'Ok':
            raise SourceFailure('wt_market_index_unavailable')
        data = item['data']
        if data['source_snapshot_id'] != identity or data['metadata']['adjustment'] != 'none':
            raise SourceFailure('wt_market_snapshot_price_differs')
        bars = data['bars']
        parts = data.get('provenance', [dict(offset=0, count=len(bars), metadata=data['metadata'])])
        rows = results[INDEX_SYMBOLS[item['symbol']]]
        for part in parts:
            yuan = part['metadata']['amount_unit'] == 'CNY'
            for bar in bars[part['offset']:part['offset'] + part['count']]:
                day = days.get(bar['date'])
                if day is None:
                    continue
                row = dict(date=day, close=bar['close'])  # 交易日及原始指数点位。
                if yuan and finite(bar['amount']) and bar['amount'] > 0:
                    row['amount_billion'] = bar['amount'] / 100_000_000  # 成交额，亿元。
                rows.append(row)
    missing = {row['date']: row for row in results[SMALL_CAP_TABLE] if 'amount_billion' not in row}
    supplement_id = snapshot.get('provenance', {}).get('supplement_facts_sha256')
    if missing and supplement_id:
        first, last = min(missing), max(missing)
        offset = 0
        while offset is not None:
            try:
                supplements = request('wt_supplement_index_turnover', lambda client: client.source_supplement_query(dict(
                    snapshot_id=identity, metric=INDEX_TURNOVER, symbols=[SMALL_CAP_INDEX],
                    **{'from': first, 'to': last}, offset=offset, limit=2000)),
                    absent=('Unavailable', 'NotSupported', 'InvalidInput', 'IoError'))
            except MarketUnavailable as error:
                if isinstance(error, MarketHTTPError) and error.response['status']['code'] not in (
                        'Unavailable', 'NotSupported', 'InvalidInput', 'IoError'):
                    raise
                break
            if supplements is None:
                break
            if supplements['source_snapshot_id'] != identity or supplements['source_sha256'] != supplement_id:
                raise SourceFailure('wt_market_snapshot_price_differs')
            for row in supplements['rows']:
                if row['date'] in missing and row['unit'] == 'CNY':
                    amount = float(row['value'])
                    if finite(amount) and amount > 0:
                        missing[row['date']]['amount_billion'] = amount / 100_000_000
            offset = supplements['selection']['next_offset']
    return results


def index_row_complete(table, row):
    """只有小盘事件需要指数成交额；其余市场结构输入只依赖点位。"""
    return row.get('close') is not None and (table != SMALL_CAP_TABLE or row.get('amount_billion') is not None)


def wt_stock_history(fetch, start, end, calendar, client_factory, *, snapshot_dates):
    """整日聚合由 WT 随同日事实归档，观衡固定市场版本后仅读取。"""

    def query(kind, call):
        fetch.budget.request(kind='sdk')
        try:
            response = call(client_factory(min(fetch.timeout, fetch.budget.remaining())))
        except MarketHTTPError as error:
            response = error.response
            if response['status']['code'] != 'Unavailable':
                raise
        if response['status']['code'] == 'Unavailable':
            return None
        if response['status']['code'] != 'Ok':
            raise SourceFailure('wt_market_daily_facts_unavailable')
        data = response['data']
        # 日事实的完整原件由 WT 服务持有，观察保留实际查询结果的谱系投影。
        if kind == 'wt_market_structure_facts':
            evidence = {key: data[key] for key in ('date', 'source_snapshot_id', 'source_sha256', 'provenance')}
            evidence['stock_cross_section'] = data.get('stock_cross_section')
        else:
            evidence = {key: data[key] for key in ('snapshot_id', 'observation_date')}
        body = encode(evidence)
        fetch.budget.consume(len(body))
        sha = fetch.objects.put(body)
        fetch.records.append(dict(kind=kind, sha256=sha, source_host='wondertrader', status=200,
                                  retrieved_at=datetime.now(timezone.utc).isoformat(), media_type='application/json'))
        return data

    if not calendar['coverage_start'] <= start <= end <= min(snapshot_dates) <= max(snapshot_dates) <= calendar['coverage_end']:
        raise SourceFailure('official_calendar_outside_coverage')
    snapshot = wt_snapshot(lambda day: query('wt_market_structure_snapshot',
        lambda client: client.source_market_snapshot_query(day)), snapshot_dates)
    days, _ = official_calendar(calendar, check=fetch.budget.remaining)
    results = []
    for row in days:
        day = row['date']
        if not row['is_open'] or not start <= day <= end:
            continue
        facts = query('wt_market_structure_facts', lambda client: client.source_day_facts_query(
            day, snapshot['snapshot_id'], include_stock_cross_section=True))
        section = facts.get('stock_cross_section', {}) if facts else {}
        if 'provider' in section:
            results.append(dict(date=day, **{key: section[key] for key in
                                            ('sample_count', 'top5_pct', 'median_return_pct', 'provider', 'source_sha256')}))
    return {STOCK_TABLE: results}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _json(body):
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        raise SourceFailure('market_structure_source_schema') from None
    if not isinstance(value, dict):
        raise SourceFailure('market_structure_source_schema')
    return value


def _csi_rows(body, code, open_days, check):
    payload = _json(body)
    records = payload.get('data')
    if str(payload.get('code')) != '200' or not isinstance(records, list):
        raise SourceFailure('market_structure_csi_schema')
    rows = {}
    for row in records:
        check()
        if not isinstance(row, dict) or row.get('indexCode') != code:
            raise SourceFailure('market_structure_csi_identity')
        stamp = row.get('tradeDate')
        if not isinstance(stamp, str) or not re.fullmatch(r'[0-9]{8}', stamp):
            raise SourceFailure('market_structure_csi_identity')
        try:
            day = date.fromisoformat(stamp).isoformat()
        except ValueError:
            raise SourceFailure('market_structure_csi_identity') from None
        close, amount = row.get('close'), row.get('tradingValue')
        if day not in open_days or day in rows or not finite(close) or close <= 0:
            raise SourceFailure('market_structure_csi_identity')
        # 官方同一字段以亿元展示。零成交额不具备接力比较资格。
        rows[day] = dict(date=day, close=close, amount_billion=amount if finite(amount) and amount > 0 else None)
    return [rows[day] for day in sorted(rows)]


def _stock_row(body, day, check, minimum_sample_count):
    payload = _json(body)
    if payload.get('code') != 0:
        error = 'market_structure_stock_rate_limit' if '频率' in str(payload.get('msg', '')) else 'market_structure_stock_access'
        raise SourceFailure(error, diagnostic=dict(
            provider='tushare', stage='daily', provider_code=payload.get('code')
            if type(payload.get('code')) is int else None, observation_date=day))
    data = payload.get('data')
    if not isinstance(data, dict) or data.get('fields') != STOCK_FIELDS or data.get('has_more') is not False:
        raise SourceFailure('market_structure_stock_schema')
    rows = data.get('items')
    if not isinstance(rows, list) or not 0 < len(rows) < 6000:
        raise SourceFailure('market_structure_stock_incomplete')
    amounts, changes, seen = [], [], set()
    stamp = day.replace('-', '')
    for row in rows:
        check()
        if not isinstance(row, list) or len(row) != 4:
            raise SourceFailure('market_structure_stock_schema')
        symbol, row_day, change, amount = row
        if not isinstance(symbol, str) or row_day != stamp or symbol in seen:
            raise SourceFailure('market_structure_stock_identity')
        seen.add(symbol)
        if not A_SHARE.fullmatch(symbol):
            continue
        if not finite(amount) or amount < 0:
            raise SourceFailure('market_structure_stock_schema')
        if amount == 0:
            continue
        if not finite(change):
            raise SourceFailure('market_structure_stock_schema')
        amounts.append(amount)
        changes.append(change)
    if len(amounts) < minimum_sample_count:
        raise SourceFailure('market_structure_stock_incomplete')
    top = (len(amounts) + 19) // 20
    concentration = 100 * math.fsum(sorted(amounts, reverse=True)[:top]) / math.fsum(amounts)
    return dict(date=day, sample_count=len(amounts), top5_pct=concentration, median_return_pct=median(changes))


def history(fetch, source, start, end, calendar, *, existing=()):
    check = fetch.budget.remaining
    if not calendar['coverage_start'] <= start <= end <= calendar['coverage_end']:
        raise SourceFailure('market_structure_calendar_range')
    calendar_rows, _ = official_calendar(calendar, check=check)
    days = {r['date'] for r in calendar_rows if r['is_open'] == 1 and start <= r['date'] <= end}
    if source['kind'] == CSI_KIND:
        output = {}
        for code, key in INDEX_TABLES.items():
            body = fetch.get(CSI_URL, dict(indexCode=code, startDate=start.replace('-', ''), endDate=end.replace('-', '')))
            output[key] = _csi_rows(body, code, days, check)
        return output
    token = os.environ.get('TUSHARE_TOKEN')
    if not token:
        raise SourceFailure('market_structure_stock_access')
    rows = []
    next_request = monotonic()
    for day in sorted(days):
        delay = next_request - monotonic()
        if delay > 0:
            fetch.wait(delay)
        next_request = monotonic() + STOCK_REQUEST_INTERVAL
        try:
            body = fetch.post_private_query(TUSHARE_URL, dict(api_name='daily', token=token,
                params=dict(trade_date=day.replace('-', '')), fields=','.join(STOCK_FIELDS)),
                observation_date=day)
            row = _stock_row(body, day, check, source['minimum_sample_count'])
        except SourceFailure as error:
            if error.code == 'market_structure_stock_rate_limit' and rows:
                fetch.records[-1]['diagnostic_code'] = error.code
                break
            if error.code not in ('market_structure_stock_incomplete', 'market_structure_stock_schema',
                                  'market_structure_stock_identity'):
                raise
            # 原有效截面遇异常修订时保留。全新日期留空，后续批次继续补核。
            if day not in existing:
                rows.append(dict(date=day, sample_count=None, top5_pct=None, median_return_pct=None))
            fetch.records[-1]['diagnostic_code'] = error.code
        else:
            rows.append(row)
    return {STOCK_TABLE: rows}
