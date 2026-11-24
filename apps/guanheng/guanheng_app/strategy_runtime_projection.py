"""原CTA业务结果的纯白名单投影；不持有或创建运行owner。"""
from datetime import datetime, timezone
from decimal import Decimal
import logging
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
    'waiting_allocation': '等待确认策略归属',
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


def _diagnostics(result, symbols, outcome):
    """附加诊断独立准入；错误仅影响诊断，核心资金/持仓继续原验证。"""
    value = result.get('diagnostics')
    if value is None:
        return None, 'absent', 'not_recorded'
    try:
        from guanheng_strategy_v1 import validate_diagnostics, contextualize_diagnostics
        validate_diagnostics(value, symbols=symbols)
        # 与原回测逐日投影一致：setter接收目标仍为pending，原NSQ确认converged才完成。
        execution = ('not_requested' if outcome is None else
                     'completed' if outcome['status'] == 'converged' else 'pending')
        return contextualize_diagnostics(value, execution_state=execution), 'available', None
    except Exception as error:
        # 每次投影最多一条固定事件/异常类型；不写输入、异常原文或账户资料。
        try:
            logging.getLogger(__name__).warning('strategy_diagnostics_unavailable error_type=%s', type(error).__name__)
        except Exception:
            pass  # 附加告警本身也不能改变已核核心读取的结果。
        return None, 'unavailable', 'invalid_diagnostics'


def published_identity(identity, report):
    """从本轮WT结果取版本/集合；等待计算时只保留实际发布的持仓/周期证券。"""
    _require(type(report)is dict)
    from .strategy_allocation_projection import project_allocation
    allocation=project_allocation(identity,report)
    if allocation is not None:
        _require(report.get('strategy_id',identity)==identity and report.get('strategy_version',allocation['strategy_version'])==allocation['strategy_version'])
        declaration=report.get('definition')
        if declaration is not None:
            _require(type(declaration)is dict and declaration.get('strategy_id')==identity
                and declaration.get('strategy_version')==allocation['strategy_version']
                and type(declaration.get('symbols'))is list
                and set(declaration['symbols'])=={p['symbol']for p in allocation['positions']})
        return strategy_definition(identity,allocation['strategy_version']),tuple(sorted(p['symbol'] for p in allocation['positions']))
    if report.get('strategy_id')==identity and report.get('strategy_version') is not None:
        # 原版等待期可未取得ASA；仅复制原发布的声明/目标集合，不填账户P。
        declaration=report.get('definition')
        if declaration is not None:
            _require(type(declaration)is dict and declaration.get('strategy_id')==identity
                and declaration.get('strategy_version')==report['strategy_version'] and type(declaration.get('symbols'))is list)
            symbols=tuple(sorted(declaration['symbols']))
            _require(len(symbols)<=64 and len(set(symbols))==len(symbols)
                and all(type(s)is str and re.fullmatch(r'[0-9]{6}\.(SH|SZ)',s)for s in symbols))
        else:
            native=report.get('desired_targets') or {}
            symbols=tuple(sorted(_native_security(c) for c in native))
        return strategy_definition(identity,report['strategy_version']),symbols
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


def _published_targets(value, identity, version, configuration, symbols):
    """只投影V1冻结身份与份数；不恢复规划器或重判旧basis的执行资格。"""
    if value is None:
        return {}
    from guanheng_strategy_native import EconomicTarget, Quantity, Weight

    _require(type(value) is dict and type(value.get('version')) is int and value['version'] == 1)
    target = value.get('target')
    _require(type(target) is dict and type(target.get('universe')) is list
             and type(target.get('weights')) is list and len(target['weights']) == len(symbols))
    target = EconomicTarget(**dict(target, universe=tuple(target['universe']),
        weights=tuple(Weight(**row) for row in target['weights'])))
    _require(target.strategy_id == identity and set(target.universe) == set(symbols)
             and target.config_id == configuration and target.algorithm_id.startswith(identity+'@'+version+'/'))
    quantities = value.get('targets')
    _require(type(quantities) is list and len(quantities) == len(symbols))
    quantities = tuple(Quantity(**row) for row in quantities)
    _require(tuple(row.symbol for row in quantities) == target.universe)
    return {row.symbol: row.shares for row in quantities}


def project_strategy(value, *, runtime_state='ready', strategy_id=None):
    """仅复制业务白名单，不重算策略、数量、费用或券商资金。输入来自原发布边界。"""
    _require(type(value) is dict and set(value) == {'schema', 'strategies'}
             and value['schema'] == 'guanheng.configured-cta-observation.v1')
    strategies = value['strategies']
    _require(type(strategies) is dict and len(strategies) <= 32)
    if not strategies: return None
    # 旧无参数单策略接口保留；多策略旧summary明确选择既有策略，绝不按map顺序选。
    if strategy_id is None:
        strategy_id=next(iter(strategies)) if len(strategies)==1 else 'resonance-regime-v1'
    if strategy_id not in strategies: return None
    identity,report = strategy_id,strategies[strategy_id]
    definition,symbols = published_identity(identity,report)
    from .strategy_allocation_projection import project_allocation
    allocation=project_allocation(identity,report)
    if 'allocation_observation'in report or report.get('status')=='waiting_allocation' or report.get('strategy_id')==identity and report.get('strategy_version') is not None:
        return _allocated_strategy(identity,report,definition,symbols,allocation)
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
    diagnostics = None
    diagnostics_state, diagnostics_reason = 'absent', 'not_calculated'
    if result is not None:
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
            targets = {}
        else:
            _require(type(outcome) is dict and outcome.get('status') == status)
            targets = _published_targets(outcome['state'], identity, definition['strategy_version'],
                                         result['configuration_sha256'], symbols)
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
    from .strategy_capital_projection import project_baseline, project_capital, project_capital_return
    capital_origin = project_baseline(report.get('capital_baseline'))
    capital = project_capital(report.get('capital'), capital_origin, runtime_state=runtime_state)
    capital_return = project_capital_return(report.get('capital_return'), capital_origin, capital)
    if result is not None:
        diagnostics, diagnostics_state, diagnostics_reason = _diagnostics(result, symbols, outcome)
    from .strategy_current_auxiliary_projection import project_current_auxiliary
    current, current_state, current_reason = project_current_auxiliary(result, symbols)
    return dict(strategy_id=identity,  # 同轮WT发布的策略身份；不从App当前依赖反推。
                display_name=definition['display_name'],
                strategy_version=definition['strategy_version'],  # WT实际版本，未发布时None；不生成缺失版本。
                status=status, status_label=_LABELS[status], decision_at=decision_at,
                broker_observed_at=broker_at, broker_position_qualified=False,
                execution_position_qualified=execution_qualified, positions=list(rows.values()),
                capital_baseline=capital_origin, capital=capital,
                **({'capital_return': capital_return} if capital_return is not None else {}),
                diagnostics=diagnostics,  # 本轮V1统一业务诊断；未计算、未记录或无效时为None。
                diagnostics_state=diagnostics_state,  # 附加信息的可用性，独立于原策略和账户状态。
                diagnostics_reason=diagnostics_reason,  # 稳定原因码；可用时None，不回显原始诊断。
                current_auxiliary=current,  # 当前决策消费原值；与历史逐行diagnostics分别表达。
                current_auxiliary_state=current_state,  # 当前附加信息独立可用性，不影响资金与持仓。
                current_auxiliary_reason=current_reason)  # 当前未记录/无效的稳定原因；可用时None。



def _consumed_signal(report, symbols):
    """展示策略保存的已消费信号；旧报告仍可按原日期和修订标识核对。"""
    from datetime import date
    routes = report.get('consumed_routes')
    decision_date = report.get('signal_consumed_date')
    if 'consumed_routes' in report:
        _require(type(routes) is dict)
        if not routes:
            return None
        _require(type(decision_date) is str
                 and date.fromisoformat(decision_date).isoformat() == decision_date)
        current = {code: row for code, row in routes.items() if row['date'] == decision_date}
        _require(bool(current))
        eligible_days = {row['eligible_date'] for row in current.values()}
        _require(len(eligible_days) == 1)
        eligible_date = eligible_days.pop()
        _require(date.fromisoformat(eligible_date).isoformat() == eligible_date and decision_date < eligible_date)
        decision_at = max(_time(row['decision_at']) for row in current.values())
        rows = []
        for symbol in symbols:
            row = current.get(symbol.split('.')[0])
            if row is None:
                rows.append(dict(symbol=symbol, qualified=False, actions=[], model_held=None, auxiliary_missing=[]))
                continue
            actions, model_held, missing = row['actions'], row['model_held'], row['auxiliary_missing']
            _require(type(actions) is list and all(a in ('BUY', 'SELL') for a in actions)
                     and (model_held is None or type(model_held) is bool)
                     and type(missing) is list and all(type(r) is str and re.fullmatch('[a-z_]+', r) for r in missing))
            rows.append(dict(symbol=symbol, qualified=True, actions=actions,
                             model_held=model_held, auxiliary_missing=missing))
        return dict(decision_at=decision_at, decision_date=decision_date,
                    eligible_date=eligible_date, securities=rows)
    signal = report.get('signal')
    if (type(signal) is not dict or signal.get('schema') != 'guanheng.original-current-signal.v1'
            or report.get('signal_ready') is not True or report.get('signal_revision_after_consumption') is True
            or signal.get('decision_date') != report.get('signal_consumed_date')):
        return None
    decision_date = signal['decision_date']
    eligible_date = signal['eligible_date']
    _require(type(decision_date) is str and type(eligible_date) is str
             and date.fromisoformat(decision_date).isoformat() == decision_date
             and date.fromisoformat(eligible_date).isoformat() == eligible_date and decision_date < eligible_date)
    rows = []
    for symbol in symbols:
        code = symbol.split('.')[0]
        route = signal['route_qualification'][code]
        actions = [row['action'] for row in signal['signals_today'][code]]
        model_held = signal['model_state'][code]['held']
        _require(type(route['qualified']) is bool and all(action in ('BUY', 'SELL') for action in actions)
                 and (model_held is None or type(model_held) is bool))
        missing = [value.partition(':')[0] for value in route.get('optional_diagnostics', ())
                   if value.partition(':')[2] in ('', code)]
        rows.append(dict(symbol=symbol, qualified=route['qualified'], actions=actions,
                         model_held=model_held, auxiliary_missing=sorted(set(missing))))
    return dict(decision_at=_time(signal['decision_at']), decision_date=decision_date,
                eligible_date=eligible_date, securities=rows)


def _allocated_strategy(identity,report,definition,symbols,allocation):
    """新/旧profile共用ASA归属投影；执行目标与实际份额分列，账户资金不混入。"""
    labels=dict(_LABELS,initialized='策略已初始化',waiting='等待策略所需事实',holding='保持当前目标',targets_ready='目标已准备')
    status=report.get('status')
    _require(status in labels)
    legacy=None
    if report.get('core_result') is not None:
        retained=dict(report)
        for key in ('allocation_observation','strategy_id','strategy_version'):retained.pop(key,None)
        legacy=project_strategy(dict(schema='guanheng.configured-cta-observation.v1',strategies={identity:retained}))
    own={p['symbol']:p for p in allocation['positions']} if allocation else {}
    targets=None if allocation is None else allocation['targets']
    rows=[]
    for symbol in symbols:
        p=own.get(symbol)
        rows.append(dict(symbol=symbol,target_weight=None,theoretical_quantity=None,theoretical_sellable=None,
            pending_target=None,stage_target=None if targets is None else targets.get(symbol),
            broker_quantity=None if p is None else p['quantity'],broker_sellable=None if p is None else p['sellable']))
    from .strategy_current_auxiliary_projection import project_current_auxiliary
    auxiliary,auxiliary_state,auxiliary_reason=project_current_auxiliary(None,symbols)
    extra=dict(diagnostics=None,diagnostics_state='absent',diagnostics_reason='not_calculated',
        current_auxiliary=auxiliary,current_auxiliary_state=auxiliary_state,current_auxiliary_reason=auxiliary_reason)
    if legacy is not None:
        for key in extra:extra[key]=legacy[key]
        weights={p['symbol']:p['target_weight'] for p in legacy['positions']}
        for row in rows:row['target_weight']=weights[row['symbol']]
    consumed = None
    if legacy is None:
        try:
            consumed = _consumed_signal(report, symbols)
        except (KeyError, ValueError, TypeError, AttributeError):
            logging.getLogger(__name__).warning('strategy_consumed_signal_invalid')
        if consumed is not None:
            extra.update(diagnostics_reason='not_recorded', current_auxiliary_reason='not_recorded')
    from .strategy_valuation_projection import project_owned_valuation
    valuation,valuation_state,valuation_reason=project_owned_valuation(identity,report,allocation)
    if valuation is not None and valuation_state in ('actual', 'reference-fee-pending'):
        from .strategy_allocation_projection import security
        quotes = {security(quote['symbol']): quote for quote in valuation['quotes']}
        for row in rows:
            quote = quotes.get(row['symbol'])
            if quote is not None:
                row.update(
                    market_value_cny=format(Decimal(quote['price_cny']) * quote['quantity'], 'f'),  # 自有份额乘已核原价，人民币元。
                    market_value_observed_at=quote['observed_at'])  # 该标的原报价时间，带时区。
    from .strategy_capital_projection import project_baseline, project_capital_return
    baseline = project_baseline(report.get('capital_baseline'))
    capital_return = None
    history_anchor = report.get('capital_history_anchor_sha256')
    if baseline is None or type(history_anchor) is not str or not re.fullmatch(r'[0-9a-f]{64}', history_anchor):
        history_anchor = None
    reported_return = report.get('capital_return')
    if baseline is not None and valuation_state == 'actual':
        if (valuation['baseline_cny'] is not None and valuation['baseline_at'] == baseline['baseline_at']
                and Decimal(valuation['baseline_cny']) == Decimal(baseline['total_cny'])):
            capital_return = project_capital_return(reported_return, baseline, dict(
                observed_at=valuation['observed_at'], account_observed_at=valuation['cash_observed_at'],
                nav_cny=valuation['nav_cny']))
    elif history_anchor is not None and isinstance(reported_return, dict) and reported_return.get('state') == 'available':
        # 只有已核收益携带可展示的历史净值；时钟保持原截止，不补当前估值。
        current_time = datetime.now(timezone.utc).isoformat()
        capital_return = project_capital_return(reported_return, baseline, dict(
            observed_at=current_time, account_observed_at=current_time, nav_cny=None))
    return dict(strategy_id=identity,display_name=definition['display_name'],strategy_version=definition['strategy_version'],
        owned_valuation=valuation,valuation_state=valuation_state,valuation_reason=valuation_reason,  # 原profile自有估值及独立缺失分类；App不估价。
        status=status,status_label=labels[status],
        decision_at=(legacy['decision_at'] if legacy is not None else consumed and consumed['decision_at']),
        **({'consumed_signal': consumed} if consumed is not None else {}),
        broker_observed_at=None if allocation is None else allocation['observed_at'],
        broker_position_qualified=False,execution_position_qualified=False,positions=rows,
        capital_baseline=baseline, capital=None,  # 分账估值沿自有资金投影，基准沿原策略。
        **({'capital_history_anchor_sha256': history_anchor} if history_anchor is not None else {}),
        **({'capital_return': capital_return} if capital_return is not None else {}),
        ownership=allocation,  # 原ASA自有现金/实际D/完整目标，与账户P/A单独标识。
        position_basis='strategy-allocated',  # 同代码实际份额已由ASA唯一账本归属。
        **extra)


def project_strategies(value, *, runtime_state='ready'):
    """同轮逐ID准入；任一策略格式失败明确报错，不退回其他身份。"""
    _require(type(value)is dict and type(value.get('strategies'))is dict)
    return [project_strategy(value,runtime_state=runtime_state,strategy_id=identity) for identity in value['strategies']]
