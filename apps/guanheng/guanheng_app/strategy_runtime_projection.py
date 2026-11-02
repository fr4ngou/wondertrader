"""原CTA业务结果的纯白名单投影；不持有或创建运行owner。"""
from datetime import datetime, timezone
import math
from .strategy_catalog import strategy_catalog

def _require(value):
    if not value:
        raise ValueError('策略业务结果格式无效')

_SYMBOLS = ('159780.SZ', '510050.SH', '510300.SH', '510500.SH', '512100.SH', '515080.SH', '588000.SH', '589000.SH')
_CODES = {('SSE' if s.endswith('.SH') else 'SZSE') + '.ETF.' + s[:6]: s for s in _SYMBOLS}
_LABELS = {
    'initializing': '正在准备目标', 'selling': '正在调整卖出目标', 'buying': '正在调整买入目标',
    'converged': '理论持仓已达到本阶段目标', 'waiting_basis': '等待完整资金与价格',
    'waiting_sellable': '等待持仓可卖', 'waiting_pending': '等待原生未决目标处理',
    'waiting_cash': '等待可用资金', 'waiting_fee': '等待费用信息',
    'supersession_required': '等待原目标处理完成', 'blocked': '本轮目标暂未执行',
    'waiting_broker_position': '等待更新券商持仓', 'waiting_actual_cycle': '等待确认实际开仓信息',
    'waiting_market_input': '等待策略所需行情',
}


def _time(value):
    _require(type(value) is str and len(value) <= 64)
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    _require(stamp.utcoffset() is not None and stamp <= datetime.now(timezone.utc))
    return stamp.astimezone(timezone.utc).isoformat()


def _quantity(value):
    _require(type(value) in (int, float) and 0 <= value <= 9007199254740991
             and math.isfinite(value) and int(value) == value)
    return int(value)


def _observation(value):
    """核同一原生观察合同；资格由发布者持有，消费者不重算执行结果。"""
    from guanheng_strategy_native import NativePosition, Observation
    _require(type(value) is dict and type(value.get('positions')) is list and len(value['positions']) == 8)
    fields = dict(value)
    fields['positions'] = tuple(NativePosition(**p) for p in fields['positions'])
    observed = Observation(**fields)
    _require(observed.verified and {p.symbol for p in observed.positions} == set(_SYMBOLS))
    _time(observed.observed_at)
    return observed


def project_strategy(value, *, runtime_state='ready'):
    """仅复制业务白名单，不重算策略、数量、费用或券商资金。输入来自原发布边界。"""
    _require(type(value) is dict and set(value) == {'schema', 'strategies'}
             and value['schema'] == 'guanheng.configured-cta-observation.v1')
    strategies = value['strategies']
    _require(type(strategies) is dict and set(strategies) <= {'resonance-regime-v1'})
    if not strategies:
        return None
    report = strategies['resonance-regime-v1']
    _require(type(report) is dict and report.get('status') in _LABELS
             and type(report.get('sequence')) is int and report['sequence'] > 0
             and report.get('broker_position_qualified') is False)
    status = report['status']
    execution_qualified = report.get('execution_position_qualified', False)
    _require(type(execution_qualified) is bool)
    if execution_qualified:
        _observation(report.get('execution_observation'))
    result = report.get('core_result')
    _require(status != 'waiting_market_input' or result is None and report.get('outcome') is None)
    rows = {s: dict(symbol=s, target_weight=None, theoretical_quantity=None, theoretical_sellable=None,
                   pending_target=None, stage_target=None, broker_quantity=None, broker_sellable=None) for s in _SYMBOLS}
    decision_at = None
    if result is not None:
        from .execution_configured import _restore_quantity_state
        _require(type(result) is dict and result.get('schema') == 'guanheng.retained-resonance-result.v1'
                 and result.get('strategy_id') == 'resonance-regime-v1' and result.get('strategy_version') == '1.1.2')
        decision_at = _time(result['decision_cutoff'])
        weights = result['targets']
        _require(type(weights) is dict and set(weights) == set(_SYMBOLS)
                 and all(type(w) in (int, float) and math.isfinite(w) and 0 <= w <= 1 for w in weights.values()))
        observed = _observation(report['native_observation'])
        _require(_time(observed.observed_at) == decision_at)
        outcome = report['outcome']
        _require(type(outcome) is dict and outcome.get('status') == status)
        state = _restore_quantity_state(outcome['state'])
        _require(state is None or state.target.strategy_id == 'resonance-regime-v1'
                 and set(state.target.universe) == set(_SYMBOLS))
        targets = {} if state is None else {p.symbol: p.shares for p in state.targets}
        _require(not targets or set(targets) == set(_SYMBOLS))
        readback = report.get('target_readback')
        if readback is not None:
            submitted = {p['symbol']: _quantity(p['shares']) for p in outcome['submit_targets']}
            _require(type(readback) is dict and set(readback) == set(_CODES)
                     and {_CODES[c]: _quantity(q) for c, q in readback.items()} == submitted == targets)
        for p in observed.positions:
            rows[p.symbol].update(target_weight=weights[p.symbol], theoretical_quantity=p.actual,
                theoretical_sellable=p.sellable, pending_target=p.pending_target, stage_target=targets.get(p.symbol))
    else:
        _require(status in ('waiting_broker_position', 'waiting_actual_cycle', 'waiting_market_input'))
    broker = report['broker_observation']
    _require(type(broker) is dict and type(broker.get('positions_known')) is bool
             and type(broker.get('positions')) is list and len(broker['positions']) <= 4096)
    received = broker.get('position_received_ms')
    broker_at = None
    if received is not None:
        _require(type(received) is int and 0 <= received <= 253402300799999)
        broker_at = _time(datetime.fromtimestamp(received / 1000, timezone.utc).isoformat())
    if broker['positions_known']:
        _require(broker_at is not None)
        for row in rows.values():
            row.update(broker_quantity=0, broker_sellable=0)
        seen = set()
        for p in broker['positions']:
            _require(type(p) is dict and type(p.get('symbol')) is str and type(p.get('is_long')) is bool)
            quantity, sellable = _quantity(p['quantity']), _quantity(p['sellable'])
            _require(sellable <= quantity)
            symbol = _CODES.get(p['symbol'])
            if symbol is not None:
                _require(p['is_long'] and symbol not in seen)
                seen.add(symbol)
                rows[symbol].update(broker_quantity=quantity, broker_sellable=sellable)
    definition = strategy_catalog()['strategies'][0]
    from .strategy_capital_projection import project_baseline, project_capital
    capital_origin = project_baseline(report.get('capital_baseline'))
    capital = project_capital(report.get('capital'), capital_origin, runtime_state=runtime_state)
    return dict(display_name=definition['display_name'], strategy_version=definition['strategy_version'],
                status=status, status_label=_LABELS[status], decision_at=decision_at,
                broker_observed_at=broker_at, broker_position_qualified=False,
                execution_position_qualified=execution_qualified, positions=list(rows.values()),
                capital_baseline=capital_origin, capital=capital)

