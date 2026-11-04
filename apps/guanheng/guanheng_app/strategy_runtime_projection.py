"""原CTA业务结果的纯白名单投影；不持有或创建运行owner。"""
from datetime import datetime, timezone
import math
import re
from .strategy_catalog import strategy_definition

def _require(value):
    if not value:
        raise ValueError('策略业务结果格式无效')

_LABELS = {
    'initializing': '正在准备目标', 'selling': '正在调整卖出目标', 'buying': '正在调整买入目标',
    'converged': '理论持仓已达到本阶段目标', 'waiting_basis': '等待完整资金与价格',
    'waiting_sellable': '等待持仓可卖', 'waiting_pending': '等待原生未决目标处理',
    'waiting_cash': '等待可用资金', 'waiting_fee': '等待费用信息',
    'supersession_required': '等待原目标处理完成', 'blocked': '本轮目标暂未执行',
    'waiting_broker_position': '等待更新券商持仓', 'waiting_actual_cycle': '等待确认实际开仓信息',
    'waiting_market_input': '等待策略所需行情', 'observing': '分析运行中',
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


def _native_security(value):
    """等待期只转换明确的WT ETF交易所代码；未知来源保持读取失败，不猜交易所。"""
    _require(type(value)is str)
    match=re.fullmatch(r'(SSE|SZSE)\.ETF\.([0-9]{6})',value)
    _require(match is not None)
    return match[2]+{'SSE':'.SH','SZSE':'.SZ'}[match[1]]


def _observation(value, symbols):
    """核同一原生观察合同；资格由发布者持有，消费者不重算执行结果。"""
    from guanheng_strategy_native import NativePosition, Observation
    _require(type(value) is dict and type(value.get('positions')) is list and len(value['positions']) == len(symbols))
    fields = dict(value)
    fields['positions'] = tuple(NativePosition(**p) for p in fields['positions'])
    observed = Observation(**fields)
    _require(observed.verified and {p.symbol for p in observed.positions} == set(symbols))
    _time(observed.observed_at)
    return observed


def published_identity(identity, report):
    """从本轮WT结果取版本/集合；等待计算时只保留实际发布的持仓/周期证券。"""
    _require(type(report)is dict)
    result=report.get('core_result')
    version=None
    declaration=report.get('definition')
    if declaration is not None:
        _require(type(declaration)is dict and {'strategy_id','strategy_version','symbols'}<=set(declaration)
                 and declaration['strategy_id']==identity and declaration['strategy_version']is not None
                 and type(declaration['symbols'])is list)
        version=declaration['strategy_version']
        symbols=tuple(sorted(declaration['symbols']))
        if result is not None:
            _require(type(result)is dict and result.get('strategy_id')==identity
                     and result.get('strategy_version')==version and type(result.get('targets'))is dict
                     and set(result['targets'])==set(symbols))
    elif result is not None:
        _require(type(result)is dict and result.get('strategy_id')==identity)
        version=result.get('strategy_version')
        _require(version is not None and type(result.get('targets'))is dict)
        symbols=tuple(sorted(result['targets']))
    else:
        observed=report.get('execution_observation')or report.get('native_observation')
        if type(observed)is dict and type(observed.get('positions'))is list:
            symbols=tuple(sorted(p['symbol']for p in observed['positions']))
        else:
            native=report.get('broker_observation',{}).get('positions',[])
            symbols=tuple(sorted(set(report.get('cycle_metadata',{}))|{
                _native_security(p['symbol'])for p in native}))
    _require(len(symbols)<=8 and (result is None or len(symbols)==8) and len(set(symbols))==len(symbols)
             and all(type(s)is str and re.fullmatch(r'[0-9]{6}\.(SH|SZ)',s)for s in symbols))
    definition=strategy_definition(identity,version)
    return definition,symbols


def project_strategy(value, *, runtime_state='ready'):
    """仅复制业务白名单，不重算策略、数量、费用或券商资金。输入来自原发布边界。"""
    _require(type(value) is dict and set(value) == {'schema', 'strategies'}
             and value['schema'] == 'guanheng.configured-cta-observation.v1')
    strategies = value['strategies']
    _require(type(strategies) is dict and len(strategies) <= 1)
    if not strategies:
        return None
    identity,report = next(iter(strategies.items()))
    definition,symbols = published_identity(identity,report)
    codes={('SSE'if s.endswith('.SH')else'SZSE')+'.ETF.'+s[:6]:s for s in symbols}
    _require(type(report) is dict and report.get('status') in _LABELS
             and type(report.get('sequence')) is int and report['sequence'] > 0
             and report.get('broker_position_qualified') is False)
    status = report['status']
    execution_qualified = report.get('execution_position_qualified', False)
    _require(type(execution_qualified) is bool)
    if execution_qualified:
        _observation(report.get('execution_observation'),symbols)
    result = report.get('core_result')
    _require(status != 'waiting_market_input' or result is None and report.get('outcome') is None)
    rows = {s: dict(symbol=s, target_weight=None, theoretical_quantity=None, theoretical_sellable=None,
                   pending_target=None, stage_target=None, broker_quantity=None, broker_sellable=None) for s in symbols}
    decision_at = None
    if result is not None:
        from .execution_configured import _restore_quantity_state
        _require(type(result) is dict and result.get('schema') == 'guanheng.retained-resonance-result.v1'
                 and result.get('strategy_id') == identity and result.get('strategy_version') == definition['strategy_version'])
        decision_at = _time(result['decision_cutoff'])
        weights = result['targets']
        _require(type(weights) is dict and set(weights) == set(symbols)
                 and all(type(w) in (int, float) and math.isfinite(w) and 0 <= w <= 1 for w in weights.values()))
        observed = _observation(report['native_observation'],symbols)
        _require(_time(observed.observed_at) == decision_at)
        outcome = report['outcome']
        if status == 'observing':
            _require(outcome is None and report.get('reason') == 'analysis_only'
                     and report.get('target_readback') is None)
            state = None
        else:
            _require(type(outcome) is dict and outcome.get('status') == status)
            state = _restore_quantity_state(outcome['state'])
            _require(state is None or state.target.strategy_id == identity
                     and set(state.target.universe) == set(symbols))
            _require(state is None or state.target.config_id == result['configuration_sha256']
                     and state.target.algorithm_id.startswith(identity+'@'+definition['strategy_version']+'/'))
        targets = {} if state is None else {p.symbol: p.shares for p in state.targets}
        _require(not targets or set(targets) == set(symbols))
        readback = report.get('target_readback')
        if readback is not None:
            submitted = {p['symbol']: _quantity(p['shares']) for p in outcome['submit_targets']}
            _require(type(readback) is dict and set(readback) == set(codes)
                     and {codes[c]: _quantity(q) for c, q in readback.items()} == submitted == targets)
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
            symbol = codes.get(p['symbol'])
            if symbol is not None:
                _require(p['is_long'] and symbol not in seen)
                seen.add(symbol)
                rows[symbol].update(broker_quantity=quantity, broker_sellable=sellable)
    from .strategy_capital_projection import project_baseline, project_capital
    capital_origin = project_baseline(report.get('capital_baseline'))
    capital = project_capital(report.get('capital'), capital_origin, runtime_state=runtime_state)
    return dict(strategy_id=identity,  # 同轮WT发布的策略身份；不从App当前依赖反推。
                display_name=definition['display_name'],
                strategy_version=definition['strategy_version'],  # WT实际版本，未发布时None；不生成缺失版本。
                status=status, status_label=_LABELS[status], decision_at=decision_at,
                broker_observed_at=broker_at, broker_position_qualified=False,
                execution_position_qualified=execution_qualified, positions=list(rows.values()),
                capital_baseline=capital_origin, capital=capital)

