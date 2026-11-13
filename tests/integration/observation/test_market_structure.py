import json
from datetime import date, timedelta
from statistics import fmean, pstdev
from time import monotonic

import httpx
import pytest

from guanheng_app.observation.market_structure import SMALL, STAR, calculate, definition
from guanheng_app.observation.market_structure_source import STOCK_FIELDS, _stock_row
from guanheng_app.observation.metadata import validate_fields
from guanheng_app.observation.source_fetch import CollectionBudget, Fetcher, SourceFailure
from guanheng_app.observation.storage import ContentStore


def days(count):
    return [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(count)]


def test_small_cap_ignores_prior_volume_in_recent_window_and_marks_first_event():
    dates = days(31)
    price = [100] * 25 + [103] * 6
    benchmark = [100] * 31
    amounts = [100] * 20 + [80] * 11
    rows = calculate(SMALL, dates, price, benchmark, amounts=amounts)
    assert rows[23]['event_state'] is None
    assert rows[24]['amount_ratio'] == 0.8
    assert rows[25]['amount_ratio'] == pytest.approx(80 / 99)
    assert rows[25]['event_code'] == 1
    assert rows[26]['event_code'] == 0
    assert rows[30]['event_state'] == 0
    validate_fields(definition(SMALL), rows)


def test_star_score_uses_three_equal_zscores_and_a_gap_breaks_the_window():
    dates = days(280)
    stocks = {day: dict(top5_pct=40 + i % 7, median_return_pct=i % 11 - 5, sample_count=5000)
              for i, day in enumerate(dates)}
    price = [100 + i + i % 13 for i in range(len(dates))]
    benchmark = [100 + i for i in range(len(dates))]
    rows = calculate(STAR, dates, price, benchmark, stocks=stocks)
    def score(field):
        sample = [row[field] for row in rows[-252:]]
        return (sample[-1] - fmean(sample)) / pstdev(sample)
    assert rows[270]['score'] is None
    assert rows[-1]['score'] == pytest.approx(fmean(score(field) for field in
                                                  ('top5_pct', 'median_return_pct', 'relative_pp')))
    validate_fields(definition(STAR), rows)
    del stocks[dates[80]]
    rows = calculate(STAR, dates, price, benchmark, stocks=stocks)
    assert rows[-1]['score'] is None and rows[-1]['event_code'] is None


def test_stock_sample_excludes_no_trade_and_rejects_truncation_or_duplicate():
    rows = [[f'600{i:03}.SH', '20260105', i - 10, i] for i in range(1, 21)]
    rows.extend([['920001.BJ', '20260105', 5, 30], ['600023.SH', '20260105', None, 0],
                 ['510300.SH', '20260105', 999, 999]])
    data = dict(fields=STOCK_FIELDS, items=rows, has_more=False)
    def parse():
        return _stock_row(json.dumps(dict(code=0, data=data)), '2026-01-05', lambda: None, 20)
    assert parse()['sample_count'] == 21
    assert parse()['top5_pct'] == pytest.approx(100 * (30 + 20) / 240)
    assert parse()['median_return_pct'] == 1
    data['has_more'] = True
    with pytest.raises(SourceFailure, match='market_structure_stock_schema'):
        parse()
    data['has_more'] = False
    rows.append(rows[0])
    with pytest.raises(SourceFailure, match='market_structure_stock_identity'):
        parse()


def test_supplier_token_is_sent_only_in_the_https_query(tmp_path):
    echoed = False
    def handle(request):
        assert json.loads(request.content)['token'] == 'fixture-token'
        response = b'{"code":0,"echo":"fixture-token"}' if echoed else b'{"code":0}'
        return httpx.Response(200, stream=httpx.ByteStream(response))

    client = httpx.Client(transport=httpx.MockTransport(handle))
    fetch = Fetcher(ContentStore(tmp_path), ['api.tushare.pro'],
                    budget=CollectionBudget(monotonic() + 5), client=client)
    try:
        body = fetch.post_private_query('https://api.tushare.pro', dict(token='fixture-token'))
        assert body == b'{"code":0}'
        assert len(fetch.records) == 2
        assert 'fixture-token' not in json.dumps(fetch.records)
        echoed = True
        with pytest.raises(SourceFailure, match='source_private_response_rejected'):
            fetch.post_private_query('https://api.tushare.pro', dict(token='fixture-token'))
        assert len(fetch.records) == 2
        with pytest.raises(SourceFailure, match='source_private_query_requires_https'):
            fetch.post_private_query('http://api.tushare.pro', dict(token='fixture-token'))
    finally:
        fetch.close()
