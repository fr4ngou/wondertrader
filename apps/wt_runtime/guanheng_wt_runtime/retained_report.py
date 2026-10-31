"""唯一1.1.2报告准入和逐日投影；任务、归档、绩效复用此只读边界。"""
from dataclasses import dataclass, fields
from datetime import date, datetime
from fractions import Fraction
import math
import re

from guanheng_strategy_core.models import observation_close_at
from guanheng_strategy_native import (Basis, EconomicTarget, NativePosition, Observation,
    Outcome, Price, Quantity, QuantityPolicy, StageState, Weight)
from guanheng_strategy_v1 import RetainedHistoricalModel, SYMBOLS
from .retained_replay import REPORT_SCHEMA, REPORT_SCOPE
from .retained_evaluation import target_for_result, advance_retained
from .strategy_replay_facts import SessionError, _MODEL, _digest, _json, _quantity
from .report_values import _snapshot_json, _freeze_json, _thaw_json, _run_report_checked

ALGORITHM = 'resonance-regime-v1@1.1.2/ledger-front-ratio-v1'
NATIVES = {s: ('SSE' if s.endswith('.SH') else 'SZSE')+'.ETF.'+s[:6] for s in SYMBOLS}


def need(condition):
    if not condition:
        raise SessionError('唯一策略报告字段、身份或原生事实不一致')


def keys(value, names):
    need(type(value) is dict and set(value) == set(names.split()))
    return dict(value)


def model_fields(cls, value):
    need(type(value) is dict and set(value) == {f.name for f in fields(cls)})
    return dict(value)


def text(value, maximum=256):
    need(type(value) is str and 0 < len(value) <= maximum and all(ord(c) >= 32 for c in value))


def sha(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None)


def pairs(value, maximum, *, hashes=False, quantities=True):
    need(type(value) is list and len(value) <= maximum)
    result = {}
    for row in value:
        need(type(row) is list and len(row) == 2)
        name, item = row
        text(name)
        need(name not in result)
        if hashes:
            sha(item)
        elif quantities:
            _quantity(item)
        result[name] = item
    return result


def timestamp(value):
    need(type(value) is str and len(value) <= 64)
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(result.tzinfo is not None)
    return result


def basis(value):
    data = model_fields(Basis, value)
    need(type(data['prices']) is list and len(data['prices']) == 8)
    data['prices'] = tuple(Price(**model_fields(Price, p)) for p in data['prices'])
    result = Basis(**data)
    need(tuple(p.symbol for p in result.prices) == SYMBOLS)
    return result


def state(value):
    if value is None:
        return None
    data = model_fields(StageState, value)
    target = model_fields(EconomicTarget, data['target'])
    need(target['universe'] == list(SYMBOLS) and type(target['weights']) is list and len(target['weights']) == 8)
    target['universe'] = tuple(target['universe'])
    target['weights'] = tuple(Weight(**model_fields(Weight, p)) for p in target['weights'])
    data['target'] = EconomicTarget(**target)
    data['policy'] = QuantityPolicy(**model_fields(QuantityPolicy, data['policy']))
    data['basis'] = basis(data['basis'])
    for name in ('starts', 'targets'):
        need(type(data[name]) is list and len(data[name]) == 8)
        data[name] = tuple(Quantity(**model_fields(Quantity, p)) for p in data[name])
    return StageState(**data)


def summary(value, day, historical, configuration_sha):
    keys(value, 'schema strategy_id strategy_version full_result_sha256 input_sha256 configuration_sha256 '
        'decision_cutoff current_view budget_fraction targets source_allocation_date exit_paths next_exits '
        'holding_days reference_prices model_states analysis_source_kind source_qualified execution_qualified historical_model')
    need((value['schema'], value['strategy_id'], value['strategy_version']) ==
        ('guanheng.retained-replay-decision.v1', 'resonance-regime-v1', '1.1.2'))
    for key in ('full_result_sha256', 'input_sha256', 'configuration_sha256'):
        sha(value[key])
    need(value['configuration_sha256'] == configuration_sha)
    need(timestamp(value['decision_cutoff']) == observation_close_at(day))
    need(value['historical_model'] == historical and value['source_qualified'] is False and value['execution_qualified'] is False)
    view = keys(value['current_view'], 'dataset_sha256 received_at history_basis historical_first_available revision_history source_amount_unit amount_usage')
    model = RetainedHistoricalModel.from_dict(historical)
    need(view['dataset_sha256'] == model.dataset_sha256 and timestamp(view['received_at']) == model.received_at)
    need(tuple(view[k] for k in ('history_basis', 'historical_first_available', 'revision_history', 'source_amount_unit', 'amount_usage'))
        == ('current-visible-reconstruction', 'unknown', 'unknown', 'unknown', 'unused'))
    need(type(value['budget_fraction']) in (int, float) and math.isfinite(value['budget_fraction'])
        and 0 < value['budget_fraction'] <= .95)
    targets = value['targets']
    need(type(targets) is dict and set(targets) == set(SYMBOLS))
    need(all(type(w) in (int, float) and math.isfinite(w) and 0 <= w <= min(.25, value['budget_fraction']) for w in targets.values()))
    need(sum(Fraction(repr(float(w))) for w in targets.values()) <= 1)
    if value['source_allocation_date'] is not None:
        need(date.fromisoformat(value['source_allocation_date']) <= day)
    else:
        need(not any(targets.values()))
    need(value['analysis_source_kind'] in ('synthetic-model', 'qmt-native-verified'))
    need(type(value['model_states']) is dict and set(value['model_states']) == set(SYMBOLS))
    for key in ('holding_days', 'reference_prices', 'exit_paths'):
        need(type(value[key]) is dict and set(value[key]) <= set(SYMBOLS)-{'510300.SH'})
    need(all(type(n) is int and 0 <= n <= 4096 for n in value['holding_days'].values()))
    need(all(type(n) in (int, float) and math.isfinite(n) and n > 0 for n in value['reference_prices'].values()))
    for path in value['exit_paths'].values():
        text(path)
    need(type(value['next_exits']) is list and len(value['next_exits']) <= 7)
    exits = {}
    for item in value['next_exits']:
        keys(item, 'symbol cycle_id trade_date path')
        need(item['symbol'] in value['exit_paths'] and item['symbol'] not in exits)
        text(item['cycle_id'])
        need(date.fromisoformat(item['trade_date']) <= day and item['path'] == value['exit_paths'][item['symbol']])
        exits[item['symbol']] = item
    need(set(exits) == set(value['exit_paths']))


def capture(value, report, record, policy):
    keys(value, 'session_id sequence trading_date minute projection positions prices funds observation basis')
    need(value['session_id'] == report['session_id'] and value['trading_date'] == record['trading_date'] and value['minute'] == 1500)
    need(type(value['sequence']) is int and 1 <= value['sequence'] <= 4096)
    projected = pairs(value['projection'], 8)
    need(set(projected) <= set(NATIVES.values()))
    need(type(value['positions']) is list and len(value['positions']) == 8)
    actual = {}
    for raw, symbol in zip(value['positions'], SYMBOLS, strict=True):
        keys(raw, 'symbol total valid first_entry last_entry')
        need(raw['symbol'] == NATIVES[symbol])
        total, valid = _quantity(raw['total']), _quantity(raw['valid'])
        need(valid <= total)
        first, last = raw['first_entry'], raw['last_entry']
        need(type(first) is int and type(last) is int and 0 <= first <= last
            and ((first == 0) == (last == 0)))
        if first:
            need(total > 0 and raw['symbol'] in projected)
            for entry in (first, last):
                need(len(str(entry)) == 12 and entry <= record['trading_date']*10000+1500)
                datetime.strptime(str(entry), '%Y%m%d%H%M')
        else:
            need(total == projected.get(raw['symbol'], 0))
        quantity = total if first else 0
        target = projected.get(raw['symbol'], quantity)
        actual[symbol] = NativePosition(symbol, quantity, valid if quantity else 0, target if target != quantity else None)
    b = basis(value['basis'])
    o = model_fields(Observation, value['observation'])
    need(type(o['positions']) is list and len(o['positions']) == 8)
    o['positions'] = tuple(NativePosition(**model_fields(NativePosition, p)) for p in o['positions'])
    o = Observation(**o)
    need(o.positions == tuple(actual.values()) and o.verified and b.native_nav_verified)
    day = datetime.strptime(str(record['trading_date']), '%Y%m%d').date()
    need(timestamp(b.observed_at) == timestamp(o.observed_at) == observation_close_at(day))
    need(o.source == _MODEL and b.native_observation_id == o.native_observation_id)
    identity = _digest((value['session_id'], value['sequence'], value['trading_date'], value['minute'],
        value['projection'], value['positions'], value['prices'], value['funds']))
    need(identity == o.native_observation_id)
    raw_prices = pairs(value['prices'], 8, quantities=False)
    # 原始价格为double，不能用数量整数校验；逐一核对原值与同次价格basis。
    need(set(raw_prices) == set(NATIVES.values()))
    need(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in raw_prices.values()))
    for p in b.prices:
        need(p.raw_cny_per_share is not None and Fraction(p.raw_cny_per_share) == Fraction(repr(float(raw_prices[NATIVES[p.symbol]]))))
    funds = keys(value['funds'], 'net realized dynamic fees')
    need(all(type(v) in (int, float) and math.isfinite(v) for v in funds.values()) and funds['fees'] >= 0)
    nav = Fraction(policy.initial_capital_cny)+Fraction(repr(float(funds['net'])))
    cash = nav-sum(p.actual*Fraction(q.raw_cny_per_share) for p, q in zip(o.positions, b.prices, strict=True))
    need(Fraction(b.nav_cny) == nav and Fraction(b.cash_cny) == cash
        and Fraction(b.native_pnl_cny) == Fraction(repr(float(funds['net']))))
    return b, o


@dataclass(frozen=True, slots=True, init=False)
class ValidatedRetainedReport:
    _wire: object

    @property
    def record_count(self):
        return len(self._wire['records'])

    def to_dict(self, *, check=None):
        return _thaw_json(self._wire, check=check)


def validate_report(value, *, check=None):
    return _run_report_checked(lambda guarded: _admit(value, guarded), check)


def validate_per_date_report(value, *, check=None):
    """逐日来源先核每窗身份，再共用原财务、NSQ及输出准入。"""
    return _run_report_checked(lambda guarded: _admit(value, guarded, per_date=True), check)


def _per_date_source(value):
    source = keys(value['per_date_source'], 'schema manifest_sha256 windows')
    need(source['schema'] == 'guanheng.retained-per-date-source.v1')
    sha(source['manifest_sha256'])
    windows = source['windows']
    need(type(windows) is dict and 1 <= len(windows) <= 4096)
    days = []
    for day, digest in windows.items():
        need(type(day) is str and len(day) == 10 and date.fromisoformat(day).isoformat() == day)
        sha(digest)
        days.append(day)
    need(days == sorted(days))
    return source


def _per_date_model(record, source, day):
    window = keys(record['market_window'], 'manifest_sha256 window_sha256 basis_date factor_revision '
        'known_at received_at native_output_sha256')
    for name in ('manifest_sha256', 'window_sha256', 'factor_revision', 'native_output_sha256'):
        sha(window[name])
    need(window['manifest_sha256'] == source['manifest_sha256'] and window['basis_date'] == day.isoformat()
        and window['window_sha256'] == source['windows'].get(day.isoformat()))
    received = timestamp(window['received_at'])
    need(timestamp(window['known_at']) <= received and observation_close_at(day) <= received)
    if record['result'] is None:
        return None
    model = record['result']['historical_model']
    admitted = RetainedHistoricalModel.from_dict(model)
    need(admitted.basis_date == day and admitted.factor_sha256 == window['factor_revision']
        and admitted.received_at == received)
    return model


def _admit(value, check, *, per_date=False):
    try:
        value = _snapshot_json(value, maximum=8388608, check=check)
        keys(value, 'schema session_id input_sha256 configuration_sha256 policy scope strategy_id strategy_version '
            'historical_model status native_files native_outputs callback_counts records source_qualified execution_qualified'
            + (' per_date_source' if per_date else ''))
        schema, scope = REPORT_SCHEMA, REPORT_SCOPE
        if per_date:
            from .retained_per_date_replay import REPORT_SCHEMA as schema, REPORT_SCOPE as scope
        need((value['schema'], value['scope'], value['strategy_id'], value['strategy_version']) ==
            (schema, scope, 'resonance-regime-v1', '1.1.2'))
        for name in ('session_id', 'input_sha256', 'configuration_sha256'):
            sha(value[name])
        need(value['source_qualified'] is False and value['execution_qualified'] is False)
        source = None
        if per_date:
            need(value['historical_model'] is None)
            source = _per_date_source(value)
        else:
            RetainedHistoricalModel.from_dict(value['historical_model'])
        policy = QuantityPolicy(**model_fields(QuantityPolicy, value['policy']))
        bases = pairs(value['native_files'], 5, hashes=True)
        need(set(bases) == {'sessions', 'commodities', 'contracts', 'holidays', 'fees'})
        outputs = pairs(value['native_outputs'], 7, hashes=True)
        need(len(outputs) == 7 and {'funds.csv', 'positions.csv', 'trades.csv', 'closes.csv', 'signals.csv'} <= set(outputs))
        strategy_files = set(outputs)-{'funds.csv', 'positions.csv', 'trades.csv', 'closes.csv', 'signals.csv'}
        need(any(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,30}\.json', name) and 'ud_'+name in strategy_files
            for name in strategy_files))
        counts = pairs(value['callback_counts'], 4)
        records = value['records']
        need(type(records) is list and len(records) <= 4096 and set(counts) == {'init', 'bar', 'calculate', 'calc_done'})
        need(counts['init'] == 1 and counts['calculate'] == len(records) and counts['calc_done'] == 0 and counts['bar'] <= 32768)
        need(all(type(n) is int for n in counts.values()))
        prior, prior_state = 0, None
        for index, record in enumerate(records):
            if check is not None:
                check()
            keys(record, 'trading_date minute status reason result capture outcome previous_status readback'
                + (' market_window' if per_date else ''))
            day = record['trading_date']
            need(type(day) is int and day > prior and record['minute'] == 1500)
            prior = day
            actual_day = datetime.strptime(str(day), '%Y%m%d').date()
            historical = (_per_date_model(record, source, actual_day) if per_date else value['historical_model'])
            text(record['status']); text(record['reason'], 512)
            need(record['previous_status'] is None or record['previous_status'] in (
                'initializing', 'selling', 'buying', 'converged', 'waiting_fee', 'waiting_cash',
                'waiting_basis', 'waiting_pending', 'waiting_sellable', 'awaiting_buy',
                'supersession_required', 'blocked'))
            b, observation = capture(record['capture'], value, record, policy)
            need(record['capture']['sequence'] == index+1)
            if record['result'] is None:
                need(record['status'] == 'warming_up' and record['outcome'] is None and record['readback'] == [])
                need(b.input_sha256 == _digest((value['input_sha256'], day)))
                continue
            summary(record['result'], actual_day, historical, value['configuration_sha256'])
            need(b.input_sha256 == record['result']['input_sha256'])
            out = model_fields(Outcome, record['outcome'])
            out['state'] = state(out['state'])
            need(type(out['submit_targets']) is list and len(out['submit_targets']) <= 8)
            out['submit_targets'] = tuple(Quantity(**model_fields(Quantity, q)) for q in out['submit_targets'])
            out = Outcome(**out)
            need((record['status'], record['reason']) == (out.status, out.reason))
            target = target_for_result(record['result'], policy,
                previous_target=prior_state.target if prior_state is not None else None)
            expected, previous_status = advance_retained(target, policy, observation, b, prior_state)
            need(out == expected and record['previous_status'] == previous_status)
            prior_state = out.state
            if out.state is not None:
                t = out.state.target
                need(out.state.policy == policy and t.universe == SYMBOLS
                    and (t.strategy_id, t.algorithm_id, t.config_id) == ('resonance-regime-v1', ALGORITHM, value['configuration_sha256']))
            back = pairs(record['readback'], 8)
            need(set(back) <= set(NATIVES.values()))
            if out.submit_targets:
                need(len(out.submit_targets) == 8)
                need(all(back.get(NATIVES[t.symbol], 0) == t.shares for t in out.submit_targets))
            else:
                need(not back)
        need(value['status'] == (records[-1]['status'] if records else 'blocked_no_calculation'))
        result = object.__new__(ValidatedRetainedReport)
        object.__setattr__(result, '_wire', _freeze_json(value, check=check))
        return result
    except SessionError:
        raise
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError):
        raise SessionError('唯一策略报告未通过领域准入') from None


def project_record(report, index, *, check=None):
    def project(guarded):
        need(type(report) is ValidatedRetainedReport and type(index) is int and 0 <= index < report.record_count)
        row = _thaw_json(report._wire['records'][index], check=guarded)
        evaluation = row.pop('result')
        row['submit_vector'] = [] if row['outcome'] is None else [dict(symbol=NATIVES[q['symbol']], quantity=q['shares'])
            for q in row['outcome']['submit_targets']]
        return dict(record=row, evaluation_summary=evaluation, report_schema=report._wire['schema'])
    return _run_report_checked(project, check)
