"""官方指数与 Tushare 日终横截面的只读观察输入。"""
from datetime import date
import json
import math
import os
import re
from statistics import median
from time import monotonic

from .calendars import official_calendar
from .source_fetch import SourceFailure

CSI_URL = 'https://www.csindex.com.cn/csindex-home/perf/index-perf'
TUSHARE_URL = 'https://api.tushare.pro'
INDEX_TABLES = {code: 'source.market_structure.' + code for code in ('000688', '000300', '932000')}
STOCK_TABLE = 'source.market_structure.stock'
STOCK_FIELDS = ['ts_code', 'trade_date', 'pct_chg', 'amount']
A_SHARE = re.compile(r'(?:(?:600|601|603|605|688)\d{3}\.SH|(?:00[0-3]|30[01])\d{3}\.SZ|(?:43|8[2378]|92)\d{4}\.BJ)')
CSI_KIND = 'market_structure_csi'
STOCK_KIND = 'market_structure_stock'
FIRST_DAY = '2023-08-11'
# 已实测当前供应商日线额度为每分钟50次。为同一账号其他读者保留余量。
STOCK_REQUEST_INTERVAL = 1.5


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
