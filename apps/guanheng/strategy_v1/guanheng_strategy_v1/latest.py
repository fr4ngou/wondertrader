"""正式1.2.2的完整纯决策；实际周期和复权事实由外部owner冻结提供。"""
from dataclasses import MISSING, dataclass, field, fields, is_dataclass, replace
from datetime import date, datetime
from decimal import Context, Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from math import isfinite
import re
from time import monotonic
from zoneinfo import ZoneInfo

from guanheng_strategy_core.allocation import build_allocation_events, _targets
from guanheng_strategy_core.contracts import EvaluationBudget, FrozenHistory, KernelValidationError, canonical_bytes, utc_timestamp
from guanheng_strategy_core.features import build_daily_features
from guanheng_strategy_core.models import DailyObservation, observation_close_at, validate_observations
from guanheng_strategy_core.signals import ROLE_SIGNAL_MACHINES
from .historical import RetainedHistoricalModel

from .role_profile import KC_SYMBOL, ROLE_SYMBOLS, STRATEGY_ID, STRATEGY_VERSION, SYMBOLS
ZONE = ZoneInfo('Asia/Shanghai')


class RetainedValidationError(ValueError):
    """固定原因码与中文说明；不回显账户或调用者原值。"""
    def __init__(self, code, reason):
        self.code, self.reason = code, reason
        super().__init__(reason)


def _require(condition, code, reason):
    if not condition:
        raise RetainedValidationError(code, reason)


def _number(value):
    try:
        return type(value) in (int, float) and isfinite(value)
    except OverflowError:
        return False


def _hash(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None


def _time(value):
    try:
        utc_timestamp(value)
        return True
    except KernelValidationError:
        return False


def _text(value):
    return type(value) is str and 0 < len(value) <= 256 and value.isascii()


def _copy(value, kind):
    _require(type(value) is kind, 'invalid_input', '需要本版不可变领域输入')
    return kind(**{field.name: getattr(value, field.name) for field in fields(kind)})


@dataclass(frozen=True, slots=True)
class RetainedConfig:
    """六参数沿已核正式配置；预算为账户比例，算法不把它改成全部现金。"""
    config_revision: str  # 配置所有者提供的版本身份；变更角色后必须生成新的非空ASCII身份。
    budget_fraction: float  # 策略预算占账户比例；沿原配置，范围(0, 0.95]，无单位。
    symbol_cap_weight: float = .25  # 单证券目标权重上限；沿原规则固定0.25。
    max_weight_change: float = .25  # 单次权重变化上限；沿原规则固定0.25。
    kc_composite_signal_symbol: str = KC_SYMBOL  # 本版科创角色信号证券；使用博时科创100自身原价与前复权历史。
    kc_composite_execution_symbol: str = KC_SYMBOL  # 本版科创角色执行证券；须与信号、周期和成本证券一致。
    signal_warmup_policy_version: str = 'regime-available-v1'  # 现有信号预热规则版本；沿原可用历史语义。
    state_input_policy_version: str = 'ledger-front-ratio-v1'  # 实际周期及同基准前复权输入规则；沿1.1.2分支。


def validate_retained_configuration(config: RetainedConfig) -> None:
    """配置服务与实际决策共用正式版本规则；数据和实际周期由运行入口准入。"""
    config = _copy(config, RetainedConfig)
    _require(_text(config.config_revision) and _number(config.budget_fraction) and 0 < config.budget_fraction <= .95
        and type(config.symbol_cap_weight) in (int, float) and config.symbol_cap_weight == .25
        and type(config.max_weight_change) in (int, float) and config.max_weight_change == .25
        and all(type(item) is str for item in (config.kc_composite_signal_symbol, config.kc_composite_execution_symbol,
             config.signal_warmup_policy_version, config.state_input_policy_version))
        and (config.kc_composite_signal_symbol, config.kc_composite_execution_symbol,
             config.signal_warmup_policy_version, config.state_input_policy_version)
        == (KC_SYMBOL, KC_SYMBOL, 'regime-available-v1', 'ledger-front-ratio-v1'),
        'invalid_configuration', '配置须符合正式1.2.2六参数和策略预算')


@dataclass(frozen=True, slots=True)
class PositionCycle:
    """B原生周期/初始库存的只读事实，quantity单位为股。

    held使用实际opened_at；initial_inventory使用带时区的新运行baseline_at，
    首个严格晚于该基准的分析收盘形成参考价。flat/held的baseline_at为空，
    规范JSON省略此字段以保留旧输入身份；新系统重启沿用原基准。
    """
    symbol: str
    status: str
    quantity: int
    source_sha256: str
    cycle_id: str | None = None
    opened_at: datetime | None = None
    baseline_at: datetime | None = field(default=None, metadata={'omit_none': True})


@dataclass(frozen=True, slots=True)
class AnalysisBar:
    """同一前复权基准的分析值；raw_close和factor核查原值配对。"""
    observation: DailyObservation
    raw_close: float
    factor: float


@dataclass(frozen=True, slots=True)
class AnalysisWindow:
    basis_date: date
    known_at: datetime
    source_revision: str
    factor_revision: str
    bars: tuple[AnalysisBar, ...]
    adjustment: str = 'front_ratio'
    source_kind: str = 'synthetic-model'


@dataclass(frozen=True, slots=True)
class CurrentHistoryView:
    """当前实收版本用于之后决策；历史逐时点可获知资格保持未知。"""
    dataset_sha256: str
    received_at: datetime
    history_basis: str = 'current-visible-reconstruction'
    historical_first_available: str = 'unknown'
    revision_history: str = 'unknown'
    source_amount_unit: str = 'unknown'
    amount_usage: str = 'unused'


@dataclass(frozen=True, slots=True)
class CycleExit:
    symbol: str
    cycle_id: str
    trade_date: date
    path: str


@dataclass(frozen=True, slots=True)
class RetainedInput:
    configuration: RetainedConfig
    history: FrozenHistory
    analysis: AnalysisWindow
    current_view: CurrentHistoryView
    cycles: tuple[PositionCycle, ...]
    cycles_captured_at: datetime
    cycles_valid_until: datetime
    decision_cutoff: datetime
    previous_exits: tuple[CycleExit, ...] = ()
    schema: str = 'guanheng.retained-resonance-input.v1'

    @classmethod
    def from_dict(cls, value):
        """B/App共用固定JSON解码；值校验统一交唯一计算入口。"""
        _require(cls is RetainedInput, 'invalid_input', '需要本版固定输入模型')
        try:
            data = _wire(value, RetainedInput)
            data['configuration'] = RetainedConfig(**_wire(data['configuration'], RetainedConfig))
            history = data['history'] = FrozenHistory.from_dict(data['history'])
            analysis = _wire(data['analysis'], AnalysisWindow)
            _require(type(analysis['bars']) is list and len(analysis['bars']) <= 32768,
                     'capacity_exceeded', '分析窗口超出有界容量')
            bars = [_wire(item, AnalysisBar) for item in analysis['bars']]
            observations = FrozenHistory.from_dict(dict(observations=[b['observation'] for b in bars],
                source_revision=history.source_revision, factor_revision=history.factor_revision)).observations
            analysis['bars'] = tuple(AnalysisBar(row, b['raw_close'], b['factor']) for row, b in zip(observations, bars))
            analysis['basis_date'] = _wire_date(analysis['basis_date'])
            analysis['known_at'] = _wire_time(analysis['known_at'])
            data['analysis'] = AnalysisWindow(**analysis)
            view = _wire(data['current_view'], CurrentHistoryView)
            view['received_at'] = _wire_time(view['received_at'])
            data['current_view'] = CurrentHistoryView(**view)
            _require(type(data['cycles']) is list and len(data['cycles']) == 8,
                     'invalid_cycles', '需要全部八证券的持仓周期')
            cycles = []
            for item in data['cycles']:
                cycle = _wire(item, PositionCycle)
                for name in ('opened_at', 'baseline_at'):
                    if cycle.get(name) is not None:
                        cycle[name] = _wire_time(cycle[name])
                cycles.append(PositionCycle(**cycle))
            data['cycles'] = tuple(cycles)
            previous = data.get('previous_exits', [])
            _require(type(previous) is list and len(previous) <= 8, 'invalid_exit', '退出记录超过八证券范围')
            exits = []
            for item in previous:
                record = _wire(item, CycleExit)
                record['trade_date'] = _wire_date(record['trade_date'])
                exits.append(CycleExit(**record))
            data['previous_exits'] = tuple(exits)
            for name in ('cycles_captured_at', 'cycles_valid_until', 'decision_cutoff'):
                data[name] = _wire_time(data[name])
            return RetainedInput(**data)
        except RetainedValidationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise RetainedValidationError('invalid_input', '固定策略输入字段或时间格式无效') from None


def _wire(value, kind):
    declared = fields(kind)
    required = {f.name for f in declared if f.default is MISSING and f.default_factory is MISSING}
    _require(type(value) is dict and required <= set(value) <= {f.name for f in declared},
             'invalid_input', '策略输入字段与本版协议不一致')
    return dict(value)


def _wire_date(value):
    _require(type(value) is str and len(value) == 10, 'invalid_input', '需要明确交易日期')
    return date.fromisoformat(value)


def _wire_time(value):
    _require(type(value) is str and len(value) <= 64, 'invalid_input', '需要带时区时间')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    _require(_time(result), 'invalid_input', '需要带时区时间')
    return result


@dataclass(frozen=True, slots=True, init=False)
class RetainedResult:
    _canonical: bytes
    _digest: str

    def __init__(self, *args, **kwargs):
        raise RetainedValidationError('invalid_result', '结果由唯一计算入口生成')

    def to_dict(self):
        _require(type(self) is RetainedResult and type(self._canonical) is bytes
            and len(self._canonical) <= 8388608 and sha256(self._canonical).hexdigest() == self._digest,
            'invalid_result', '结果内容已改变')
        return json.loads(self._canonical)


class _Clock:
    def __init__(self, budget):
        self.started = monotonic()
        budget = self.budget = _copy(budget, EvaluationBudget)
        _require(all(type(value) is int and 1 <= value <= cap for value, cap in (
            (budget.max_history_days, 4096), (budget.max_observations, 32768),
            (budget.max_output_bytes, 8388608), (budget.max_text_characters, 8388608)))
            and _number(budget.max_seconds) and 0 < budget.max_seconds <= 5,
            'invalid_budget', '计算预算超过部署硬上限')

    def __call__(self):
        _require(monotonic()-self.started < self.budget.max_seconds,
                 'calculation_timeout', '策略计算超过总期限')

    def encode(self, value):
        try:
            return canonical_bytes(value, check=self, max_bytes=self.budget.max_output_bytes)
        except KernelValidationError as error:
            raise RetainedValidationError(error.code, '策略内容超过有界编码容量') from None

    def admit_text(self, value):
        """计算前核全部已隔离输入的文本值；同一字段每次出现均计入容量。"""
        pending, count = [value], 0
        while pending:
            self()
            item = pending.pop()
            if type(item) is str:
                count += len(item)
                _require(count <= self.budget.max_text_characters,
                         'capacity_exceeded', '输入文本超过计算容量')
            elif type(item) is tuple:
                pending.extend(item)
            elif is_dataclass(item):
                pending.extend(getattr(item, field.name) for field in fields(item))


def _observation(value):
    row = _copy(value, DailyObservation)
    _require(type(row.symbol) is str and row.symbol in SYMBOLS and type(row.trade_date) is date,
             'invalid_history', '证券或交易日期无效')
    _require(all(_number(getattr(row, name)) for name in ('open', 'high', 'low', 'close', 'volume', 'amount')),
             'invalid_history', '价量必须为有限数值')
    _require(all(value is None or _number(value) for value in (
        row.shares_delta_yi, row.share_probability, row.turnover_percentile, row.margin_percentile)),
        'invalid_history', '辅助事实必须为有限数值或明确缺失')
    _require(type(row.evidence_refs) is tuple and len(row.evidence_refs) <= 32
        and all(_text(item) for item in row.evidence_refs)
        # 成交额先做5日均值再取60日分位，完整来源前缀最多60+5-1=64日。
        and type(row.auxiliary_source_dates) is tuple and len(row.auxiliary_source_dates) <= 64
        and all(type(day) is date for day in row.auxiliary_source_dates)
        and (row.auxiliary_available_at is None or _time(row.auxiliary_available_at))
        and (row.market_available_at is None or _time(row.market_available_at))
        and _hash(row.market_source_sha256)
        and (row.auxiliary_source_sha256 is None or _hash(row.auxiliary_source_sha256)),
        'invalid_history', '来源或辅助事实身份无效')
    auxiliary = (row.shares_delta_yi, row.share_probability, row.turnover_percentile, row.margin_percentile)
    _require(not any(value is not None for value in auxiliary)
        or (row.auxiliary_available_at is not None and row.auxiliary_source_sha256 is not None
            and bool(row.auxiliary_source_dates)), 'invalid_history', '辅助事实缺少可获知时间和来源')
    return replace(row,
        market_available_at=utc_timestamp(row.market_available_at) if row.market_available_at is not None else None,
        auxiliary_available_at=utc_timestamp(row.auxiliary_available_at) if row.auxiliary_available_at is not None else None)


def _evaluate_current_view(request: RetainedInput, *, budget, historical_model=None) -> RetainedResult:
    """重建1.1.2市场模型和实际周期，返回完整目标及供B持久化的退出状态。

    全程纯计算；拒绝未知周期、未来数据、错复权配对和缺少实际开仓历史。
    状态与经济目标分别输出，真实委托/数量/费用由原生执行owner处理。
    """
    clock = _Clock(budget)
    request = _copy(request, RetainedInput)
    _require(type(request.schema) is str and request.schema == 'guanheng.retained-resonance-input.v1', 'invalid_input', '输入协议版本不匹配')
    config = _copy(request.configuration, RetainedConfig)
    validate_retained_configuration(config)
    history = _copy(request.history, FrozenHistory)
    analysis = _copy(request.analysis, AnalysisWindow)
    view = _copy(request.current_view, CurrentHistoryView)
    _require(_time(request.decision_cutoff) and _time(view.received_at) and _time(analysis.known_at)
        and _time(request.cycles_captured_at)
        and _time(request.cycles_valid_until), 'future_input', '输入需要明确且可表示的时间')
    # Python同一ZoneInfo对象的fold时间直接比较采用墙钟顺序；所有判断先转UTC。
    request = replace(request, decision_cutoff=utc_timestamp(request.decision_cutoff),
        cycles_captured_at=utc_timestamp(request.cycles_captured_at),
        cycles_valid_until=utc_timestamp(request.cycles_valid_until))
    analysis = replace(analysis, known_at=utc_timestamp(analysis.known_at))
    view = replace(view, received_at=utc_timestamp(view.received_at))
    if historical_model is not None:
        historical = _copy(historical_model, RetainedHistoricalModel)
        _require(historical.dataset_sha256 == view.dataset_sha256
            and historical.factor_sha256 == history.factor_revision
            and historical.basis_date == analysis.basis_date and historical.received_at == view.received_at,
            'source_mismatch', '回测假设与实际历史批次不一致')
    _require(analysis.known_at <= view.received_at
        and (view.received_at <= request.decision_cutoff if historical_model is None
             else request.decision_cutoff <= view.received_at)
        and request.cycles_captured_at <= request.decision_cutoff < request.cycles_valid_until,
        'future_input', '决策早于来源接收、分析可知或持仓捕获时间')
    _require(all(type(item) is str for item in (view.history_basis, view.historical_first_available,
        view.revision_history, view.source_amount_unit, view.amount_usage, analysis.adjustment, analysis.source_kind))
        and view.history_basis == 'current-visible-reconstruction'
        and (view.historical_first_available, view.revision_history, view.source_amount_unit, view.amount_usage)
        == ('unknown', 'unknown', 'unknown', 'unused')
        and _hash(history.source_revision) and _hash(history.factor_revision)
        and analysis.source_revision == view.dataset_sha256 == history.source_revision
        and analysis.factor_revision == history.factor_revision and analysis.adjustment == 'front_ratio'
        and analysis.source_kind in ('synthetic-model', 'qmt-native-verified')
        and type(analysis.basis_date) is date,
        'source_mismatch', '历史版本、前复权基准或来源声明不一致')
    _require(type(history.observations) is tuple and type(analysis.bars) is tuple
        and 800 <= len(history.observations) <= clock.budget.max_observations
        and len(analysis.bars) == len(history.observations), 'capacity_exceeded', '需要完整有界八证券预热历史')
    raw, adjusted, copied_bars = [], [], []
    for source, item in zip(history.observations, analysis.bars):
        clock()
        row, bar = _observation(source), _copy(item, AnalysisBar)
        other = _observation(bar.observation)
        _require((row.symbol, row.trade_date) == (other.symbol, other.trade_date)
            and _number(bar.factor) and bar.factor > 0 and _number(bar.raw_close) and bar.raw_close > 0
            and Decimal(str(bar.raw_close)).quantize(Decimal('.001'), rounding=ROUND_HALF_UP, context=Context(prec=350))
            == Decimal(str(row.close)).quantize(Decimal('.001'), rounding=ROUND_HALF_UP, context=Context(prec=350))
            and abs(other.close/bar.raw_close-bar.factor) <= max(1e-7, bar.factor*1e-5),
            'analysis_mismatch', '分析价、原始价和复权因子配对无效')
        _require(observation_close_at(row.trade_date) <= view.received_at
            and (historical_model is None or observation_close_at(row.trade_date) <= request.decision_cutoff)
            and row.trade_date <= analysis.basis_date
            and (row.market_available_at is None
                or observation_close_at(row.trade_date) <= row.market_available_at <= view.received_at),
            'future_input', '历史含尚未闭合或未来可知数据')
        if historical_model is not None:
            _require(row.market_available_at is None or row.market_available_at <= observation_close_at(row.trade_date),
                'future_input', '已有市场可知时间晚于历史模型日末')
        # 复权只替换市场数值；辅助事实沿原逐日可知身份，不从分析窗口覆盖。
        adjusted.append(replace(row, **{key: getattr(other, key) for key in ('open', 'high', 'low', 'close', 'volume', 'amount')}))
        copied_bars.append(replace(bar, observation=other))
        raw.append(row)
    identities = [(row.trade_date, row.symbol) for row in raw]
    _require(identities == sorted(set(identities)), 'invalid_history', '历史须按日期与证券唯一有序')
    days = sorted({row.trade_date for row in raw})
    _require(len(days) <= clock.budget.max_history_days
        and (days[-1] == analysis.basis_date if historical_model is None else days[-1] <= analysis.basis_date)
        and len(raw) == len(days)*8
        and all({row.symbol for row in raw[i:i+8]} == set(SYMBOLS) for i in range(0, len(raw), 8)),
        'incomplete_history', '历史日期与八证券覆盖不完整')
    try:
        validate_observations(raw)
        validate_observations(adjusted)
    except ValueError:
        raise RetainedValidationError('invalid_history', '行情或辅助事实未通过因果校验') from None
    _require(type(request.cycles) is tuple and len(request.cycles) == 8
        and type(request.previous_exits) is tuple and len(request.previous_exits) <= 8,
        'invalid_cycles', '需要全部八证券的当前持仓周期')
    cycles = {}
    for value in request.cycles:
        cycle = _copy(value, PositionCycle)
        _require(cycle.symbol in SYMBOLS and cycle.symbol not in cycles and _hash(cycle.source_sha256)
            and type(cycle.quantity) is int and 0 <= cycle.quantity <= 10**12,
            'invalid_cycles', '持仓周期数量或来源无效')
        _require(type(cycle.status) is str and cycle.status in ('flat', 'held', 'initial_inventory'),
                 'unknown_cycle', '持仓周期或初始库存起点尚未确认')
        _require((cycle.status == 'flat' and cycle.quantity == 0 and cycle.cycle_id is None
                    and cycle.opened_at is None and cycle.baseline_at is None)
            or (cycle.status == 'held' and cycle.quantity > 0 and _text(cycle.cycle_id)
                and cycle.baseline_at is None and _time(cycle.opened_at)
                and utc_timestamp(cycle.opened_at) <= request.cycles_captured_at)
            or (cycle.status == 'initial_inventory' and cycle.quantity > 0 and _text(cycle.cycle_id)
                and cycle.opened_at is None and _time(cycle.baseline_at)
                and utc_timestamp(cycle.baseline_at) <= request.cycles_captured_at),
            'invalid_cycles', '持仓须有已核实的实际周期或明确的新运行库存基准')
        if cycle.opened_at is not None:
            cycle = replace(cycle, opened_at=utc_timestamp(cycle.opened_at))
        if cycle.baseline_at is not None:
            cycle = replace(cycle, baseline_at=utc_timestamp(cycle.baseline_at))
        cycles[cycle.symbol] = cycle
    _require(len({c.baseline_at for c in cycles.values() if c.status == 'initial_inventory'}) <= 1,
             'invalid_cycles', '同一初始库存批次须采用一致的新运行基准')
    records = {}
    for value in request.previous_exits:
        record = _copy(value, CycleExit)
        _require(record.symbol in SYMBOLS and record.symbol not in records and _text(record.cycle_id)
            and _text(record.path) and type(record.trade_date) is date and record.trade_date <= days[-1],
            'invalid_exit', '原生策略退出状态无效')
        cycle = cycles[record.symbol]
        if cycle.status == 'initial_inventory':
            _require(record.cycle_id == cycle.cycle_id
                and observation_close_at(record.trade_date) > cycle.baseline_at,
                'invalid_exit', '初始库存只接受新运行基准之后同周期的退出状态')
        records[record.symbol] = record
    previous_exits = tuple(records[s] for s in sorted(records))
    normalized = replace(request, configuration=config, history=replace(history, observations=tuple(raw)),
        analysis=replace(analysis, bars=tuple(copied_bars)), current_view=view,
        cycles=tuple(cycles[s] for s in SYMBOLS), previous_exits=previous_exits)
    clock.admit_text(normalized)
    features = build_daily_features(adjusted, universe=SYMBOLS, check=clock)
    first = next((f.observation.trade_date for f in features['510300.SH'] if f.regime_score is not None), None)
    _require(first is not None, 'warmup_required', '市场状态尚未完成预热')
    series = {symbol: [f for f in features[symbol] if f.observation.trade_date >= first] for symbol in SYMBOLS}
    decisions, model_states = {}, {}
    for role, symbol in ROLE_SYMBOLS.items():
        clock()
        state = {}
        decisions[symbol] = ROLE_SIGNAL_MACHINES[role](series[symbol], symbol=symbol, state_out=state, check=clock)
        model_states[symbol] = state
    allocation = {}
    build_allocation_events(features_by_symbol=series, decisions_by_symbol=decisions,
        universe=SYMBOLS, state_out=allocation, check=clock)
    exits, ages, peaks = {}, {}, {}
    for role, symbol in ROLE_SYMBOLS.items():
        clock()
        cycle, record = cycles[symbol], records.get(symbol)
        model = decisions[symbol][-1] if decisions[symbol] else None
        actual_exit = None
        if cycle.status != 'flat' and role != 'csi300':
            values = features[symbol]
            if cycle.status == 'initial_inventory':
                # 新基准只开启之后的规则状态；既有行情不冒充旧实际周期。
                _require(cycle.baseline_at.astimezone(ZONE).date() >= days[0],
                         'initial_inventory_history_missing', '新运行基准所需行情不完整，请保留原基准核查')
                first_price = next((i for i, f in enumerate(values)
                    if observation_close_at(f.observation.trade_date) > cycle.baseline_at), None)
                opening = first_price if first_price is not None else len(values)
            else:
                opening_day = cycle.opened_at.astimezone(ZONE).date()
                opening = next((i for i, f in enumerate(values) if f.observation.trade_date == opening_day), None)
                _require(opening is not None or opening_day > days[-1],
                         'opening_history_missing', '实际开仓交易日缺少分析行情')
                if opening is None:
                    # 原1.1.2允许当日成交先于首根新收盘价，参考价形成前年龄为零。
                    opening = len(values)
                first_price = next((i for i, f in enumerate(values)
                    if observation_close_at(f.observation.trade_date) >= cycle.opened_at), None)
            ages[symbol] = max(0, len(values)-opening-1)
            if first_price is not None:
                actual = ROLE_SIGNAL_MACHINES[role](values, symbol=symbol, start_index=first_price,
                    boundary_override=(opening, first_price), check=clock)
                peaks[symbol] = max(f.observation.close for f in values[first_price:])
                actual_exit = next((d for d in reversed(actual) if d.action == 'SELL' and d.trade_date == days[-1]), None)
        if actual_exit is not None:
            records[symbol] = CycleExit(symbol, cycle.cycle_id, days[-1], actual_exit.path)
            exits[symbol] = actual_exit.path
        elif record is not None:
            recovered = cycle.status != 'flat' and record.cycle_id == cycle.cycle_id and days[-1] > record.trade_date
            fresh = model is not None and model.action == 'BUY' and model.trade_date > record.trade_date
            if recovered or fresh:
                records.pop(symbol)
            else:
                exits[symbol] = record.path
    _require(all(c.status == 'flat' or c.symbol in exits for c in cycles.values())
        or allocation.get('last_event_date') is not None,
        'allocation_unavailable', '实际持仓已确认，尚无完整分配判断')
    weights = _targets(symbols=set(SYMBOLS),
        active={symbol: value for symbol, value in allocation['active'].items() if symbol not in exits},
        csi300_strength=allocation['csi300_strength'], csi300_factor=allocation['csi300_factor'],
        pre_risk_capacity=1, check=clock)
    _require(all(0 <= weight <= min(config.budget_fraction, .25) for weight in weights.values()),
             'target_bounds', '策略目标超出原规则与预算边界')
    # 退出延续引用原退出日；解除退出才形成新的当日经济判断。
    allocation_dates = [date.fromisoformat(allocation['last_event_date'])] if allocation.get('last_event_date') else []
    allocation_dates.extend(records[s].trade_date for s in exits)
    if any(r.symbol not in records for r in previous_exits):
        allocation_dates.append(days[-1])
    source_date = max(allocation_dates) if allocation_dates else None
    identity = normalized if historical_model is None else dict(request=normalized, historical_model=historical)
    input_sha = sha256(clock.encode(identity)).hexdigest()
    value = dict(schema='guanheng.retained-resonance-result.v1' if historical_model is None
            else 'guanheng.retained-resonance-historical-result.v1', strategy_id=STRATEGY_ID,
        strategy_version=STRATEGY_VERSION, input_sha256=input_sha, decision_cutoff=request.decision_cutoff,
        configuration_sha256=sha256(clock.encode(config)).hexdigest(),
        current_view=view, budget_fraction=config.budget_fraction, targets=weights,
        source_allocation_date=source_date,
        exit_paths=exits, next_exits=tuple(records[s] for s in sorted(records)),
        holding_days=ages, reference_prices=peaks, model_states=model_states,
        model_decisions=decisions, allocation_state=allocation,
        analysis_source_kind=analysis.source_kind,
        source_qualified=False, execution_qualified=False)
    if historical_model is not None:
        value['historical_model'] = historical
    encoded = clock.encode(value)
    result = object.__new__(RetainedResult)
    object.__setattr__(result, '_canonical', encoded)
    object.__setattr__(result, '_digest', sha256(encoded).hexdigest())
    clock()
    return result


def evaluate_current_view(request: RetainedInput, *, budget=EvaluationBudget()) -> RetainedResult:
    """消费当前可见完整输入，统一返回完整八目标或固定领域错误；零IO。"""
    try:
        return _evaluate_current_view(request, budget=budget)
    except RetainedValidationError:
        raise
    except KernelValidationError as error:
        raise RetainedValidationError(error.code, '共享数学计算未通过领域准入') from None
    except (AttributeError, TypeError, ValueError, ArithmeticError):
        raise RetainedValidationError('invalid_input', '策略输入或计算数值无效') from None


def evaluate_historical_model(request: RetainedInput, model: RetainedHistoricalModel, *,
                              budget=EvaluationBudget()) -> RetainedResult:
    """显式最终批次回放；同一规则只读模型截止前缀，实际接收时间保持原值。"""
    try:
        _require(type(model) is RetainedHistoricalModel, 'invalid_input', '历史入口需要明确回测假设')
        return _evaluate_current_view(request, budget=budget, historical_model=model)
    except RetainedValidationError:
        raise
    except KernelValidationError as error:
        raise RetainedValidationError(error.code, '共享数学计算未通过领域准入') from None
    except (AttributeError, TypeError, ValueError, ArithmeticError):
        raise RetainedValidationError('invalid_input', '策略历史模型或计算数值无效') from None
