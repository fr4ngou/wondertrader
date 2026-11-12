"""隔离策略资金原点、持久流水和收益观察，不连接券商。"""
from hashlib import sha256
import json
from time import monotonic

import pytest

from guanheng_wt_runtime.strategy_capital import _digest
from guanheng_wt_runtime.strategy_capital_flow import (
    FILE_NAME, ReturnValuations, append_record, capital_identity, main, observe_return,
)


def stamp(day):
    return f'2025-01-{day:02d}T00:00:00+00:00'


@pytest.fixture
def strategy(tmp_path):
    origin = dict(schema='guanheng.current-capital-baseline.v1', total_cny='100', source='test',
                  baseline_at=stamp(1), historical_initial_capital_cny=None)
    anchor = dict(schema='guanheng.broker-cash-anchor.v1', baseline_sha256=_digest(origin),
                  allocated_cash_cny='100', market_value_cny='0', account_cash_cny='500',
                  account_observed_at=stamp(1), account_source_sha256='1' * 64,
                  account_binding_sha256='2' * 64, position_source_sha256='3' * 64, price_source_sha256='4' * 64)
    return tmp_path / FILE_NAME, origin, anchor


def add(strategy, item):
    path, origin, anchor = strategy
    return append_record(path, capital_identity('example', origin, anchor), origin, item, deadline=monotonic() + 2)


def capital(strategy, nav='110', valuation=5, cash=5):
    _, origin, anchor = strategy
    return dict(baseline=origin, cash_anchor=anchor, observed_at=stamp(valuation),
                account_observed_at=stamp(cash), nav_cny=nav)


def observe(strategy, nav='110', valuation=5, cash=5, name='example'):
    return observe_return(strategy[0], name, capital(strategy, nav, valuation, cash), deadline=monotonic() + 2)


def cover(strategy, direction, day):
    return add(strategy, dict(kind='coverage', id=f'{direction}-{day}', source_ref=f'audit-{direction}-{day}',
                              direction=direction, through=stamp(day)))


def flow(id, direction, day, amount, before, price_day, *, reconciled=True):
    return dict(kind='flow', id=id, source_ref=f'cash-{id}', direction=direction, amount_cny=amount,
                effective_at=stamp(day), nav_before_cny=before, nav_observed_at=stamp(price_day) if before else None,
                nav_source_ref=f'nav-{price_day}' if before else None,
                nav_cash_receipt_ref=f'cash-reconciliation-{id}' if reconciled else None)


def test_each_direction_must_cover_the_actual_cash_and_mark_inputs(strategy):
    cover(strategy, 'inflow', 5)
    assert observe(strategy)['state'] == 'coverage_pending'
    cover(strategy, 'outflow', 5)
    assert observe(strategy)['return_pct'] == '10'
    assert observe(strategy, cash=6)['state'] == 'coverage_pending'
    assert observe(strategy, name='other')['state'] == 'coverage_pending'
    cover(strategy, 'outflow', 6)
    cover(strategy, 'inflow', 6)
    assert observe(strategy, cash=6)['coverage_required_at'] == stamp(6)
    assert observe(strategy, cash=6)['return_pct'] == '10'


def test_append_retry_and_both_directions_compound(strategy):
    deposit = flow('deposit', 'inflow', 2, '50', '110', 2)
    receipt = add(strategy, deposit)
    assert add(strategy, deposit) == receipt
    assert add(strategy, dict(deposit, id='different-request')) == receipt
    with pytest.raises(ValueError, match='strategy_capital_flow_record_invalid'):
        add(strategy, dict(deposit, amount_cny='51'))
    add(strategy, flow('withdrawal', 'outflow', 4, '20', '176', 4))
    cover(strategy, 'inflow', 5)
    cover(strategy, 'outflow', 5)
    result = observe(strategy, '171.6')
    assert result['return_pct'] == '33.1'
    assert result['flow_count'] == 2
    assert [item['direction'] for item in result['flows']] == ['inflow', 'outflow']
    assert 'cash-reconciliation' not in str(result)


def test_cash_that_moves_across_input_boundaries_is_pending(strategy):
    add(strategy, flow('withdrawal', 'outflow', 6, '20', '120', 6))
    cover(strategy, 'inflow', 7)
    cover(strategy, 'outflow', 7)
    assert observe(strategy, cash=7)['state'] == 'reconciliation_pending'
    assert observe(strategy, cash=5, valuation=7)['state'] == 'reconciliation_pending'


def test_correction_invalidates_prior_coverage_and_valuation_cannot_be_reused(strategy):
    add(strategy, flow('deposit', 'inflow', 2, '50', '110', 2))
    withdrawal = flow('withdrawal', 'outflow', 4, '20', '110', 2)
    add(strategy, withdrawal)
    cover(strategy, 'inflow', 5)
    cover(strategy, 'outflow', 5)
    assert observe(strategy)['state'] == 'valuation_pending'
    fixed = flow('withdrawal', 'outflow', 4, '20', '176', 4)
    correction = dict(kind='correction', id='fix', source_ref='correct-valuation',
                      original_id='withdrawal', reason='核实提取前净值',
                      replacement={k: v for k, v in fixed.items() if k not in ('kind', 'id', 'source_ref')})
    receipt = add(strategy, correction)
    assert add(strategy, dict(correction, id='retry-fix')) == receipt
    assert observe(strategy)['state'] == 'coverage_pending'
    cover(strategy, 'outflow', 6)
    assert observe(strategy, '171.6')['return_pct'] == '33.1'


def test_unknown_or_ambiguous_valuation_does_not_turn_cash_into_profit(strategy):
    add(strategy, flow('deposit', 'inflow', 2, '50', '100', 2, reconciled=False))
    cover(strategy, 'inflow', 5)
    cover(strategy, 'outflow', 5)
    assert observe(strategy, '100')['state'] == 'reconciliation_pending'
    assert observe(strategy, '100')['return_pct'] is None


def test_replayed_coverage_does_not_undo_invalidation(strategy):
    cover(strategy, 'inflow', 5)
    receipt = cover(strategy, 'outflow', 5)
    add(strategy, flow('withdrawal', 'outflow', 2, '20', '110', 2))
    original = {key: value for key, value in receipt.items() if key != 'recorded_at'}
    assert add(strategy, dict(original, id='retry-coverage')) == receipt
    with pytest.raises(ValueError):
        add(strategy, dict(original, id='replay-with-new-cutoff', through=stamp(6)))
    assert observe(strategy)['state'] == 'coverage_pending'


def test_keeps_verified_valuation_as_cash_refreshes_and_rechecks_retroactive_flow(strategy):
    owner = ReturnValuations(strategy[0], 'example')

    def refresh(nav, day):
        return owner.observe(capital(strategy, nav, day, day), deadline=monotonic() + 2)

    assert refresh('110', 5)['state'] == 'coverage_pending'
    cover(strategy, 'inflow', 5)
    cover(strategy, 'outflow', 5)
    settled = refresh('113', 6)
    assert settled['return_pct'] == '10'
    assert settled['valued_at'] == stamp(5)
    assert refresh('120', 7) == settled
    cover(strategy, 'inflow', 6)
    cover(strategy, 'outflow', 6)
    assert refresh('120', 7)['return_pct'] == '13'
    add(strategy, flow('withdrawal', 'outflow', 2, '20', '110', 2))
    assert refresh('120', 7)['state'] == 'coverage_pending'


def test_simultaneous_flows_use_one_boundary_and_full_withdrawal_can_restart(strategy):
    add(strategy, flow('withdrawal-1', 'outflow', 2, '70', '110', 2))
    add(strategy, flow('withdrawal-2', 'outflow', 2, '40', '110', 2))
    add(strategy, flow('deposit', 'inflow', 4, '60', '0', 4))
    cover(strategy, 'inflow', 5)
    cover(strategy, 'outflow', 5)
    assert observe(strategy, '66')['return_pct'] == '21'


def test_invalid_database_only_degrades_returns(strategy):
    strategy[0].write_bytes(b'invalid SQLite')
    assert observe(strategy)['state'] == 'record_unavailable'


def test_registration_uses_actual_config_and_original_strategy_binding(strategy, capsys):
    database, origin, anchor = strategy
    broker = dict(expected_account='fixture', environment='simulation')
    anchor['account_binding_sha256'] = _digest(dict(account='fixture', environment='simulation', currency='CNY'))
    inputs = database.with_name('inputs.json')
    inputs.write_text(json.dumps(dict(capital_baseline=origin, cash_anchor=anchor)), encoding='utf-8')
    settings = dict(input_file=str(inputs), input_sha256=sha256(inputs.read_bytes()).hexdigest())
    config = database.with_name('native.json')
    config.write_text(json.dumps(dict(output_directory=str(database.parent), trader=broker,
        strategies=[dict(id='example', parameters=dict(python_strategy=settings))])), encoding='utf-8')
    record = database.with_name('record.json')
    record.write_text(json.dumps(dict(kind='coverage', id='inflow-cover', source_ref='inflow-audit',
                                      direction='inflow', through=stamp(5))), encoding='utf-8')
    argv = ['--execution-config', str(config), '--strategy-id', 'example', '--record', str(record), '--config-sha256']
    with pytest.raises(ValueError):
        main([*argv, '0' * 64])
    assert not database.exists()
    assert main([*argv, sha256(config.read_bytes()).hexdigest()]) == 0
    assert json.loads(capsys.readouterr().out)['id'] == 'inflow-cover'
    assert observe(strategy)['inflow_through'] == stamp(5)
