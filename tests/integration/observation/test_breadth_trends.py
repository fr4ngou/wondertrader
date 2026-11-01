"""可手算EMA、累计起点、真实交易日缺口和基准独立尾部。"""
from datetime import date, timedelta

import pytest

from guanheng_app.observation.breadth_trends import attach_benchmark, attach_trends, trend_rows
from guanheng_app.observation.contracts import ObservationError


def samples(count=41):
    days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(count)]
    breadth = [dict(date=day, advancing_count=5 if i < 39 else 9, declining_count=5 if i < 39 else 1,
        market_count=10, unclassified_count=0) for i, day in enumerate(days)]
    rana = [dict(date=day, rana=0 if i < 39 else 800) for i, day in enumerate(days)]
    return days, breadth, rana


def test_full_history_seeds_and_cumulative_anchor_are_hand_checkable():
    days, breadth, rana = samples()
    rows = trend_rows(breadth, rana, trading_days=days)
    assert rows[37]['msi'] is None and rows[38]['msi'] == 0
    assert rows[38]['cumulative_start'] == days[38]
    assert rows[39]['msi'] == pytest.approx(40)
    assert rows[40]['msi'] == pytest.approx(114)
    assert rows[8]['breadth_thrust'] is None and rows[9]['breadth_thrust'] == .5
    assert rows[39]['breadth_thrust'] == pytest.approx(.5 + .4 * 2 / 11)
    assert rows[-1]['seed_start'] == days[0]


def test_canonical_calendar_gap_resets_warmup_and_cumulative_origin():
    days, breadth, rana = samples(43)
    del breadth[40]
    datasets = {'breadth.shsz': breadth, 'rana.shsz': rana}
    attach_trends(datasets, {}, {'source.cn_calendar': [dict(date=day, is_open=1) for day in days]})
    row = datasets['msi.shsz'][-2]
    assert row['date'] == days[41] and row['msi'] is None
    assert row['warmup_observations'] == 1 and row['seed_start'] == days[41]
    assert row['cumulative_start'] is None


def test_unknown_ratio_breaks_segment_and_mismatched_scale_is_rejected():
    days, breadth, rana = samples()
    rana[39]['rana'] = None
    rows = trend_rows(breadth, rana, trading_days=days)
    assert rows[39]['msi'] is None and rows[40]['warmup_observations'] == 1
    rana[39]['rana'] = .8
    with pytest.raises(ObservationError, match='RANA'):
        trend_rows(breadth, rana, trading_days=days)


def test_benchmark_exposes_known_calendar_without_inventing_source_observations():
    datasets, definitions = {}, {}
    attach_benchmark(datasets, definitions, {'market.sh000001': [dict(date='2026-10-26', close=3000),
        dict(date='2026-10-28', close=3020)], 'source.cn_calendar': [dict(date='2026-10-25', is_open=0),
        *[dict(date=f'2026-10-{day}', is_open=1) for day in (26, 27, 28)]]})
    assert len(datasets['market.sh000001']) == 2
    assert definitions['market.sh000001']['trading_days'] == ['2026-10-26', '2026-10-27', '2026-10-28']
