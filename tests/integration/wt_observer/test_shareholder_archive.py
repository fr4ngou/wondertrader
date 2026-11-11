from datetime import date
from decimal import Decimal

import pytest

from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.shareholder_archive import INDEXES, aggregate


def event(*, code='600100', announcement='2018-01-03', traded='2018-01-02',
          quantity=-20, average=None, close=None):
    return dict(NOTICE_DATE=announcement, SECURITY_CODE=code, HOLDER_NAME='合成股东',
        END_DATE=traded, START_DATE=traded, TRADE_DATE=traded, EITIME=announcement,
        CHANGE_NUM_SYMBOL=quantity, CHANGE_NUM=abs(quantity), MARKET='二级市场',
        DIRECTION='减持' if quantity < 0 else '增持', TRADE_AVERAGE_PRICE=average, CLOSE_PRICE=close)


def test_announcement_dates_price_hierarchy_and_missing_trade():
    rows = [
        event(average=Decimal('3.15'), close=7),
        event(code='600200', quantity=10, close=2),
        event(code='600300', quantity=-1),
        event(code='600400', quantity=-10),
        event(code='600500', traded='2018-01-04', average=4),
    ]
    indexes = {symbol: {'2018-01-02': Decimal('3100.5')} for symbol in INDEXES if symbol != '000688.SH'}
    indexes['000688.SH'] = {}
    history = {'600300': (['2018-01-01'], {'2018-01-01': Decimal('10.9')}),
               '600400': (['2017-11-30'], {'2017-11-30': Decimal('9')})}
    first, second, third = aggregate(rows, date(2018, 1, 1), date(2018, 1, 3), indexes, history)
    assert first['net_amount_cny'] == 0 and second['csi_close'] == 3100.5 and second['star_close'] is None
    assert third['net_amount_cny'] == -539000
    assert [third[key] for key in ('priced_trade_count', 'estimated_count', 'unpriced_count', 'timing_conflict_count')] == [1, 2, 1, 1]


def test_issuer_reconciliation_excludes_exact_event_without_hiding_other_trades():
    row = event(quantity=-20, average=4)
    other = event(code='600200', quantity=-10, average=4)
    indexes = {symbol: {} for symbol in INDEXES}
    key = ('2018-01-03', '600100', '合成股东', Decimal(-20))
    (_, _, day) = aggregate([row, other], date(2018, 1, 1), date(2018, 1, 3), indexes, {}, excluded={key})
    assert day['net_amount_cny'] == -400000
    assert day['issuer_excluded_count'] == day['priced_trade_count'] == 1
    with pytest.raises(ObservationError, match='身份不匹配'):
        aggregate([other], date(2018, 1, 1), date(2018, 1, 3), indexes, {}, excluded={key})


def test_repeated_source_rows_stop_publication():
    indexes = {symbol: {} for symbol in INDEXES}
    row = event()
    with pytest.raises(ObservationError, match='分页身份重复'):
        aggregate([row, row], date(2018, 1, 1), date(2018, 1, 3), indexes, {})


def test_scheduled_tail_reuses_wt_prices_and_preserves_published_values():
    import json
    from types import SimpleNamespace

    from guanheng_app.observation.shareholder_source import INDEX_TABLES, URL, history
    from guanheng_app.observation.source_fetch import SourceFailure

    events = [
        event(code='600100', announcement='2026-11-11', traded='2026-11-10', quantity=-2),
        event(code='600200', announcement='2026-11-11', traded='2026-11-10', average=3, quantity=1),
    ]
    request = []
    calls = []
    report = dict(success=True, result=dict(count=2, pages=1, data=events))

    def get(url, params):
        assert url == URL
        calls.append(params)
        return json.dumps(report).encode()

    def query(payload):
        request.append(payload)
        return dict(status=dict(code='Ok'), data=dict(metadata=dict(adjustment='none', factor_version=''),
            bars=[dict(date=20261110, close=4)]))

    fetch = SimpleNamespace(get=get, timeout=10, records=[], objects=SimpleNamespace(put=lambda body: 'a'*64),
        budget=SimpleNamespace(remaining=lambda: 10, request=lambda **_: None, consume=lambda _: None))
    start, end = '2026-11-10', '2026-11-11'
    old = aggregate([], date.fromisoformat(start), date.fromisoformat(start),
                    {symbol: {start: 2000} for symbol in INDEXES}, {})
    old[0].update(net_amount_cny=100, issuer_excluded_count=1)
    tables = {table: [dict(date=end, close=3000)] for table in INDEX_TABLES.values()}
    source = dict(url=URL, max_pages=16)
    retained, new = history(fetch, source, start, end, old, tables,
                            lambda _: SimpleNamespace(source_daily_history_query=query))
    assert retained == old[0]
    assert new['net_amount_cny'] == -50000
    assert new['estimated_count'] == new['priced_trade_count'] == 1
    assert all(new[field] == 3000 for field in INDEXES.values())
    assert request == [dict(exchange='SSE', code='600100', **{'from': 20261011, 'to': 20261110, 'limit': 2000})]
    assert calls[0]['filter'].startswith("(NOTICE_DATE>='2026-11-10')(NOTICE_DATE<='2026-11-11')")

    report.update(success=False, result=None, code=9201, message='返回数据为空')
    _, empty = history(fetch, source, start, end, old, tables, None)
    assert empty['net_amount_cny'] == 0 and empty['csi_close'] == 3000
    report['code'] = 500
    with pytest.raises(SourceFailure, match='shareholder_report_unavailable'):
        history(fetch, source, start, end, old, tables, None)
