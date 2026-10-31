"""完整冻结前缀计算；状态由输入重建，函数不读取时钟、磁盘或外部服务。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import re
from time import monotonic
from zoneinfo import ZoneInfo

from .allocation import build_allocation_events
from .contracts import (
    AuxiliaryGap, ConfiguredStrategyConfig, CurrentTarget, DailyFrame,
    EvaluationBudget, EvaluationResult, FrozenHistory, KernelValidationError,
    KERNEL_VERSION, OBSERVATION_VERSION, STRATEGY_ID, STRATEGY_VERSION,
    SignalState, canonical_bytes, utc_timestamp,
)
from .features import build_daily_features
from .models import DailyObservation, observation_close_at
from .numerics import product, ratio
from .signals import ROLE_SIGNAL_MACHINES
from .computation import checked
from .historical_model import HistoricalEodModel, HISTORICAL_REASON

_SYMBOL = re.compile(r"[0-9]{6}\.(SH|SZ)\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_AUXILIARY = ("shares_delta_yi", "share_probability", "turnover_percentile", "margin_percentile")


def _fail(code, message):
    raise KernelValidationError(code, message)


def _aware(value):
    if (type(value) is not datetime or type(value.tzinfo) not in (timezone, ZoneInfo)
            or value.utcoffset() is None):
        return False
    utc_timestamp(value)
    return True


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _hash(value):
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _pairs(value):
    if type(value) is not tuple or not 1 <= len(value) <= len(ROLE_SIGNAL_MACHINES):
        _fail("invalid_config", "策略角色集合无效")
    for pair in value:
        if (type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str
                or pair[0] not in ROLE_SIGNAL_MACHINES or type(pair[1]) is not str
                or _SYMBOL.fullmatch(pair[1]) is None):
            _fail("invalid_config", "角色必须显式绑定沪深证券")
    result = dict(value)
    if len(result) != len(value) or len(set(result.values())) != len(result):
        _fail("invalid_config", "每个策略角色及其证券必须唯一")
    return result


def _config(config, cutoff):
    if type(config) is not ConfiguredStrategyConfig or not _aware(cutoff):
        _fail("invalid_time", "计算需要不可变配置和带时区的知晓截止")
    if (any(type(getattr(config, name)) is not str for name in (
            "strategy_id", "strategy_version", "observation_version", "warmup_policy"))
            or (config.strategy_id, config.strategy_version, config.observation_version, config.warmup_policy)
            != (STRATEGY_ID, STRATEGY_VERSION, OBSERVATION_VERSION, "regime-available-v1")):
        _fail("algorithm_identity_mismatch", "配置算法身份与configured 1.2.0不一致")
    if not _aware(config.valid_from) or not _aware(config.valid_until):
        _fail("invalid_time", "配置生效与失效时间必须带时区")
    if not config.valid_from <= cutoff < config.valid_until:
        _fail("config_expired", "计算知晓截止位于配置有效期之外")
    if (type(config.config_revision) is not str or not 1 <= len(config.config_revision) <= 128
            or any(ord(c) < 32 for c in config.config_revision)):
        _fail("invalid_config", "配置修订身份无效")
    roles = _pairs(config.symbol_roles)
    executions = _pairs(config.execution_symbols)
    if (set(roles) != set(executions) or type(config.benchmark_role) is not str
            or config.benchmark_role not in roles):
        _fail("invalid_config", "信号与执行角色必须一致且包含基准角色")
    windows = (config.regime_ma_period, config.position_window, config.volume_window)
    if any(type(v) is not int or not 2 <= v <= 10000 for v in windows):
        _fail("invalid_config", "特征窗口须为2至10000的整数")
    if (type(config.minimum_history_days) is not int
            or not max(windows) <= config.minimum_history_days <= 10000):
        _fail("invalid_config", "所需历史日数必须覆盖全部特征窗口")
    for value, lower, upper in ((config.budget_weight, 0, .95),
                                (config.symbol_cap_weight, .05, .25),
                                (config.max_weight_change, .01, .25)):
        if not _number(value) or not lower <= value <= upper:
            _fail("invalid_config", "策略预算、单证券上限或变化幅度超出已有规则范围")
    if config.budget_weight <= 0:
        _fail("invalid_config", "策略预算必须大于零")
    return roles, executions


def validate_configuration(config: ConfiguredStrategyConfig) -> None:
    """校验配置内部规则，沿计算入口的唯一_config逻辑，无I/O或当前时间读取。

    输入须由ConfiguredStrategyConfig.from_dict构造。此入口只核结构、算法、
    映射、窗口、预算和有效期顺序；实际计算继续以自己的knowledge_cutoff
    经过原_config准入。保存一个过期配置不会授予当前计算或交易资格。
    失败使用原KernelValidationError及稳定原因码，成功返回None。
    """
    if type(config) is not ConfiguredStrategyConfig:
        _fail("invalid_config", "策略配置需要唯一不可变领域模型")
    _config(config, config.valid_from)


def _budget(budget):
    if type(budget) is not EvaluationBudget:
        _fail("invalid_budget", "计算预算类型无效")
    for value, ceiling in ((budget.max_history_days, 4096), (budget.max_observations, 32768),
                           (budget.max_output_bytes, 8388608), (budget.max_text_characters, 8388608)):
        if type(value) is not int or not 1 <= value <= ceiling:
            _fail("invalid_budget", "计算预算必须在部署硬上限以内")
    if not _number(budget.max_seconds) or not 0 < budget.max_seconds <= 5:
        _fail("invalid_budget", "计算时间预算须位于零至五秒范围内")


def _history(history, roles, config, cutoff, budget, check, historical_model=None):
    if type(history) is not FrozenHistory or type(history.observations) is not tuple:
        _fail("invalid_history", "历史必须为不可变完整前缀")
    if not _hash(history.source_revision) or not _hash(history.factor_revision):
        _fail("invalid_source", "历史与复权来源需要SHA-256身份")
    if historical_model is not None:
        if type(historical_model) is not HistoricalEodModel:
            _fail("invalid_historical_model", "历史回测输入需要明确模型类型")
        if historical_model.dataset_sha256 != history.source_revision:
            _fail("invalid_historical_model", "历史回测模型与原始批次身份失配")
    rows = history.observations
    if not rows:
        _fail("empty_history", "缺少策略完整日线历史")
    if len(rows) > budget.max_observations:
        _fail("capacity_exceeded", "日线条数超出计算容量")
    symbols = set(roles.values())
    by_date = defaultdict(set)
    previous = None
    identities = set()
    text_characters = len(history.source_revision) + len(history.factor_revision)
    text_characters += sum(len(value) for pair in config.symbol_roles + config.execution_symbols for value in pair)
    text_characters += sum(len(getattr(config, field)) for field in (
        "config_revision", "benchmark_role", "strategy_id", "strategy_version", "observation_version", "warmup_policy"))
    if text_characters > budget.max_text_characters:
        _fail("capacity_exceeded", "来源文本超出计算容量")
    gaps = []
    roles_by_symbol = {symbol: role for role, symbol in roles.items()}
    for row in rows:
        check()
        if (type(row) is not DailyObservation or type(row.trade_date) is not date
                or type(row.symbol) is not str or row.symbol not in symbols):
            _fail("invalid_history", "历史包含非法日期或配置外证券")
        identity = (row.trade_date, row.symbol)
        if identity in identities:
            _fail("duplicate_observation", "同一交易日证券存在重复日线")
        if previous is not None and identity < previous:
            _fail("history_out_of_order", "历史须按交易日与证券排序")
        identities.add(identity)
        previous = identity
        by_date[row.trade_date].add(row.symbol)
        if len(by_date) > budget.max_history_days:
            _fail("capacity_exceeded", "历史交易日数超出计算容量")
        close_at = observation_close_at(row.trade_date)
        if close_at > cutoff:
            _fail("future_observation", "历史包含知晓截止之后的收盘")
        if historical_model is None:
            if not _aware(row.market_available_at):
                _fail("invalid_time", "日线必须声明带时区的市场可知时间")
            if row.market_available_at > close_at:
                _fail("future_market_fact", "日线在对应收盘决策时尚不可知")
        elif row.market_available_at is not None or historical_model.received_at < close_at:
            _fail("invalid_historical_model", "回测历史保留未知可知时间，实收须覆盖原日末区间")
        if not _hash(row.market_source_sha256):
            _fail("invalid_source", "每条日线需要原始来源摘要")
        # 缺辅助数值也不能把任意对象/超长文本带入哈希与不可变结果。
        if row.auxiliary_source_sha256 is not None and not _hash(row.auxiliary_source_sha256):
            _fail("invalid_auxiliary", "辅助来源摘要必须为空或规范SHA-256")
        numbers = (row.open, row.high, row.low, row.close, row.volume, row.amount)
        if not all(_number(v) for v in numbers):
            _fail("nonfinite_value", "日线价量金额必须为有限数值")
        if (min(numbers[:4]) <= 0 or row.high < max(row.open, row.close, row.low)
                or row.low > min(row.open, row.close, row.high) or row.volume < 0 or row.amount < 0):
            _fail("invalid_bar", "日线OHLC、成交量或金额不一致")
        if type(row.evidence_refs) is not tuple or not 1 <= len(row.evidence_refs) <= 16:
            _fail("invalid_source", "每条日线需要有界来源证据")
        for ref in row.evidence_refs:
            if type(ref) is not str or not 1 <= len(ref) <= 256:
                _fail("invalid_source", "日线来源证据格式无效")
            text_characters += len(ref)
        text_characters += len(row.symbol) + len(row.market_source_sha256)
        if row.auxiliary_source_sha256 is not None:
            text_characters += len(row.auxiliary_source_sha256)
        if text_characters > budget.max_text_characters:
            _fail("capacity_exceeded", "来源文本超出计算容量")
        if type(row.auxiliary_source_dates) is not tuple or len(row.auxiliary_source_dates) > 64:
            _fail("invalid_auxiliary", "辅助事实来源日期无效")
        if any(type(day) is not date or day > row.trade_date for day in row.auxiliary_source_dates):
            _fail("future_auxiliary", "辅助事实来源日期晚于本帧交易日")
        present = [name for name in _AUXILIARY if getattr(row, name) is not None]
        for name in present:
            value = getattr(row, name)
            if not _number(value) or (name != "shares_delta_yi" and not 0 <= value <= 100):
                _fail("invalid_auxiliary", "辅助事实数值超出有效范围")
        if present:
            if (not _aware(row.auxiliary_available_at) or not row.auxiliary_source_dates
                    or not _hash(row.auxiliary_source_sha256)):
                _fail("invalid_auxiliary", "辅助事实必须声明知晓时间、来源日及摘要")
        if row.auxiliary_available_at is not None:
            if not _aware(row.auxiliary_available_at):
                _fail("invalid_time", "辅助事实知晓时间必须带时区")
            if row.auxiliary_available_at > close_at:
                _fail("future_auxiliary", "辅助事实在对应日线帧的收盘时尚不可知")
        role = roles_by_symbol[row.symbol]
        required = ("share_probability", "turnover_percentile", "margin_percentile") if role == "csi300" else (
            ("shares_delta_yi",) if role in {"sh50", "kc50", "kc_composite", "zz500"} else ())
        missing = tuple(name for name in required if getattr(row, name) is None)
        if missing:
            gaps.append(AuxiliaryGap(row.trade_date, row.symbol, missing))
    if any(found != symbols for found in checked(by_date.values(), check)):
        _fail("incomplete_universe", "历史每个交易日须包含全部配置证券")
    days = sorted(by_date)
    if len(days) - 1 < config.minimum_history_days:
        _fail("insufficient_warmup", "当前收盘之前的完整历史不足配置预热要求")
    if not config.valid_from <= observation_close_at(days[-1]) < config.valid_until:
        _fail("config_expired", "最新收盘位于配置有效期之外")
    return days, tuple(gaps)


def evaluate_history(config: ConfiguredStrategyConfig, frozen_history: FrozenHistory,
                     knowledge_cutoff: datetime, *, budget: EvaluationBudget = EvaluationBudget()) -> EvaluationResult:
    """在显式截止计算完整前缀，返回含零目标、原信号日期及缺失资格。

    全部输入为不可变值，本函数无I/O、账户或交易副作用。资源超限、未来输入、
    配置失效及预热失败抛KernelValidationError；有缺失辅助时保留原灰灯算法，
    qualified=False。同一时间预算进入内部行/窗口/编码检查，宿主另持独立进程绝对截止。
    """
    return _evaluate_history(config, frozen_history, knowledge_cutoff, budget=budget)


def evaluate_historical_model(config: ConfiguredStrategyConfig, frozen_history: FrozenHistory,
                              model: HistoricalEodModel, model_cutoff: datetime, *,
                              budget: EvaluationBudget = EvaluationBudget()) -> EvaluationResult:
    """显式日末模型回放；原始行可知时间保持未知，实收及假设随结果传递。

    计算、配置、辅助因果与资源预算共用原核。返回qualified=False；无I/O、
    实时或交易副作用。默认evaluate_history继续按真实逐时点可知语义准入。
    """
    if type(model) is not HistoricalEodModel:
        _fail("invalid_historical_model", "显式历史入口需要完整回测模型")
    model = HistoricalEodModel.validated_copy(model)
    return _evaluate_history(config, frozen_history, model_cutoff, budget=budget, historical_model=model)


def _evaluate_history(config, frozen_history, knowledge_cutoff, *, budget, historical_model=None):
    _budget(budget)
    deadline = monotonic() + budget.max_seconds

    def check():
        if monotonic() >= deadline:
            _fail("calculation_timeout", "策略计算超出时间预算")

    check()
    roles, executions = _config(config, knowledge_cutoff)
    check()
    dates, gaps = _history(frozen_history, roles, config, knowledge_cutoff, budget, check, historical_model)
    features = build_daily_features(list(frozen_history.observations), universe=tuple(sorted(roles.values())),
        benchmark_symbol=roles[config.benchmark_role], regime_ma_period=config.regime_ma_period,
        position_window=config.position_window, volume_window=config.volume_window, check=check)
    check()
    first_ready = next((f.observation.trade_date for f in checked(features[roles[config.benchmark_role]], check)
                        if f.regime_score is not None), None)
    if first_ready is None:
        _fail("insufficient_warmup", "基准市场状态尚未完成预热")
    decisions = {}
    states = []
    by_date = defaultdict(list)
    for role, symbol in checked(sorted(roles.items()), check):
        state = {}
        decisions[symbol] = ROLE_SIGNAL_MACHINES[role](
            [row for row in checked(features[symbol], check) if row.observation.trade_date >= first_ready],
            symbol=symbol, state_out=state, check=check)
        states.append(SignalState(role, symbol, json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False)))
        for decision in checked(decisions[symbol], check):
            by_date[decision.trade_date].append(decision)
        check()
    unit = min(ratio(config.symbol_cap_weight, 2), ratio(config.budget_weight, len(roles) + 1))
    allocations = build_allocation_events(features_by_symbol=features, decisions_by_symbol=decisions,
        universe=tuple(sorted(roles.values())), benchmark_symbol=roles[config.benchmark_role],
        pre_risk_capacity=config.budget_weight, strength_symbol=roles.get("csi300"),
        base_unit_weight=unit, symbol_cap_weight=product(2, unit), check=check)
    check()
    target_weights = allocations[-1].as_dict() if allocations else {symbol: 0.0 for symbol in roles.values()}
    source_date = allocations[-1].trade_date if allocations else None
    targets = tuple(CurrentTarget(role, symbol, executions[role], target_weights[symbol], source_date)
                    for role, symbol in sorted(roles.items()))
    gap_days = {gap.trade_date for gap in checked(gaps, check)}
    frames = tuple(DailyFrame(day, tuple(sorted(by_date[day], key=lambda d: (d.action != "SELL", d.symbol, d.path))),
                              day not in gap_days) for day in checked(dates, check))
    identity = frozen_history if historical_model is None else {"history": frozen_history, "historical_model": historical_model}
    reasons = ("辅助事实缺失，保留灰灯及对应分支行为，输出待资格核实",) if gaps else ()
    if historical_model is not None:
        reasons += (HISTORICAL_REASON,)
    result = EvaluationResult(KERNEL_VERSION, STRATEGY_ID, STRATEGY_VERSION,
        sha256(canonical_bytes(config, check=check)).hexdigest(), sha256(canonical_bytes(identity, check=check)).hexdigest(),
        frozen_history.source_revision, frozen_history.factor_revision, knowledge_cutoff, first_ready, dates[-1],
        frames, tuple(allocations), targets, tuple(features[symbol][-1] for symbol in sorted(features)),
        tuple(states), gaps, not gaps and historical_model is None, reasons, historical_model)
    canonical_bytes(result, check=check, max_bytes=budget.max_output_bytes)
    check()
    return result
