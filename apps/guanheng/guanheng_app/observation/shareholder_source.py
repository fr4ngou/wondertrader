from collections import defaultdict
from datetime import date, datetime, timedelta

from .provider_reports import report_pages
from .shareholder_archive import FIRST, INDEXES, MARKETS, METRIC, REPORT_KEY, aggregate, positive_price, report_price
from .source_fetch import SourceFailure
from .wondertrader_source import query_daily


URL = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
INDEX_TABLES = {
    '000985.SH': 'source.csi_all', '000001.SH': 'market.sh000001',
    '399006.SZ': 'market.sz399006', '000688.SH': 'market.sh000688',
}
EVENT_FIELDS = ('net_amount_cny', 'priced_trade_count', 'estimated_count', 'unpriced_count',
                'timing_conflict_count', 'issuer_excluded_count')


def _reference_prices(fetch, events, client_factory):
    missing = defaultdict(set)
    for event in events:
        fetch.budget.remaining()
        trade_day = date.fromisoformat(event['TRADE_DATE'][:10])
        if trade_day <= date.fromisoformat(event['NOTICE_DATE'][:10]) and not any(report_price(event)):
            missing[event['SECURITY_CODE']].add(trade_day)

    if missing and client_factory is None:
        raise SourceFailure('market_source_not_configured')
    stocks = {}
    for code, days in missing.items():
        exchange = 'SSE' if code.startswith('6') else 'SZSE' if code.startswith(('00', '30')) else 'BSE'
        # 只查询实际缺价证券的已知变动日及其前30个自然日；分开远隔的变动区间。
        spans = []
        for day in sorted(days):
            first = day - timedelta(days=30)
            if spans and first <= spans[-1][1]:
                spans[-1] = spans[-1][0], day
            else:
                spans.append((first, day))
        closes = {}
        for first, last in spans:
            data = query_daily(fetch, exchange, code, first.isoformat(), last.isoformat(), client_factory)
            metadata = data['metadata']
            if metadata['adjustment'] != 'none' or metadata['factor_version'] != '':
                raise SourceFailure('shareholder_adjusted_reference')
            for bar in data['bars']:
                day = datetime.strptime(str(bar['date']), '%Y%m%d').date()
                close = positive_price(bar['close'])
                if first <= day <= last and close is not None:
                    closes[day.isoformat()] = close
        stocks[code] = sorted(closes), closes
    return stocks


def history(fetch, source, start, end, prior, tables, client_factory):
    """自然日公告查询与 WT 归档行情生成原历史指标的可修订尾部。"""
    start = max(start, FIRST.isoformat())
    if start > end:
        return []
    markets = ','.join(f'"{market}"' for market in sorted(MARKETS))
    events = report_pages(fetch, source['url'], report='RPT_SHARE_HOLDER_INCREASE', columns='ALL',
        filters=f"(NOTICE_DATE>='{start}')(NOTICE_DATE<='{end}')(MARKET in ({markets}))",
        sort=','.join(REPORT_KEY), max_pages=source['max_pages'], allow_empty=True,
        empty_error=(9201, '返回数据为空'), decimal_numbers=True, error_prefix='shareholder_report')
    if any(not start <= event['NOTICE_DATE'][:10] <= end for event in events):
        raise SourceFailure('shareholder_notice_outside_window')

    old = {row['date']: row for row in prior if start <= row['date'] <= end}
    indexes = {}
    for symbol, field in INDEXES.items():
        closes = {day: row[field] for day, row in old.items() if row.get(field) is not None}
        closes.update({row['date']: close for row in tables.get(INDEX_TABLES[symbol], ())
            if start <= row['date'] <= end and (close := positive_price(row['close'])) is not None})
        indexes[symbol] = closes

    stocks = _reference_prices(fetch, events, client_factory)
    rows = aggregate(events, date.fromisoformat(start), date.fromisoformat(end), indexes, stocks,
                     fetch.budget.remaining)
    for row in rows:
        previous = old.get(row['date'])
        if previous and (previous['issuer_excluded_count'] or row['unpriced_count'] > previous['unpriced_count']):
            # 保留公司原公告已核除的金额和现有计价覆盖；指数仍可随 WT 收盘补齐。
            row.update({key: previous[key] for key in EVENT_FIELDS})
    return rows
