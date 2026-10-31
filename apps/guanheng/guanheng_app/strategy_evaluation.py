"""固定V2业务接缝；数学归NVT，数量归NSQ，原生owner仍归Session。

本模块不接callable/动态模块，不持现金或持仓状态。可获知时间来自合格日线，
不冒称历史producer运行；source/factor改动须由外层新建会话。
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime, timezone, timedelta
from fractions import Fraction
from hashlib import sha256
import math
from time import monotonic

from guanheng_strategy_core import FrozenHistory
from guanheng_strategy_core.models import observation_close_at
from guanheng_strategy_native import EconomicTarget, Weight, QuantityPolicy

INPUT_SCHEMA = "nsb-v2-input-v1"
REPORT_SCHEMA = "nsb-v2-report-v1"
ALGORITHM_ID = "resonance-regime-v2@0.1.0/no-cycle/native-cash-etf-replay-v1"
SIGNAL_PROFILE = "legacy-backtest-evaluation-range-v1"
DATA_PROFILE = "native-frozen-causal-v1"
TARGET_POLICY = "reject-overweight-v1"
SYMBOLS = (
    "159780.SZ",
    "510050.SH",
    "510300.SH",
    "510500.SH",
    "512100.SH",
    "515080.SH",
    "588000.SH",
    "589680.SH",
)
# 本接缝固定SST a2的已发布来源；调用方只能核对，不能切换信号实现。
FEATURE_SOURCE_SHA256 = (
    "f49789eebbe6a18dfd245637fa4889b7eb08aae07d6041d41072b687f47b3bb3"
)
SIGNAL_SOURCE_SHA256 = (
    "f9840695a443fbc9d598a6934e047a1dea0ed5f12f2076624ca1833779de0763"
)
TZIF_SHA256 = "bf8b7ed82fe6e63e6d98f8cea934eeac901cd16aba85eb5755ce3f8b4289ea8a"
# 已封存V2报告的固定协议身份；只读解码独立于已退出发行的计算包。
ARCHIVED_ALLOCATION_ALGORITHM = "resonance-regime-v2@0.1.0/fixed-unit-source-v1"
ARCHIVED_ALLOCATION_SOURCE_SHA256 = "6035b1836b3b93e03a02afdde646858745823d45f29dfe226e36a13fee4232f5"


class EvaluationError(ValueError):
    """固定业务准入原因，无外部输入/路径/异常正文。"""


def wire(value):
    if type(value) in (date, datetime):
        return value.isoformat()
    if type(value) is tuple:
        return [wire(x) for x in value]
    if type(value) is dict:
        return {k: wire(v) for k, v in value.items()}
    if hasattr(type(value), "__dataclass_fields__"):
        return {f.name: wire(getattr(value, f.name)) for f in fields(value)}
    return value


def digest(value, *, check=None):
    from guanheng_strategy_core.contracts import canonical_bytes

    return sha256(
        canonical_bytes(wire(value), check=check, max_bytes=8 * 1024 * 1024)
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class V2BacktestSpec:
    history_start: date
    evaluation_start: date
    evaluation_end: date
    pre_risk_capacity: float
    execution_symbols: tuple[tuple[str, str], ...]
    strategy_id: str = "resonance-regime-v2"
    strategy_version: str = "0.1.0"
    algorithm_id: str = ALGORITHM_ID
    signal_profile: str = SIGNAL_PROFILE
    target_admission_policy: str = TARGET_POLICY
    data_qualification_profile: str = DATA_PROFILE

    def __post_init__(self):
        if (
            self.strategy_id,
            self.strategy_version,
            self.algorithm_id,
            self.signal_profile,
            self.target_admission_policy,
            self.data_qualification_profile,
        ) != (
            "resonance-regime-v2",
            "0.1.0",
            ALGORITHM_ID,
            SIGNAL_PROFILE,
            TARGET_POLICY,
            DATA_PROFILE,
        ):
            raise EvaluationError("V2固定算法或profile身份无效")
        for day in (self.history_start, self.evaluation_start, self.evaluation_end):
            if type(day) is not date or not date(1900, 1, 1) <= day <= date(
                9998, 12, 31
            ):
                raise EvaluationError("V2需要明确有界日期")
        if not self.history_start <= self.evaluation_start <= self.evaluation_end:
            raise EvaluationError("V2历史或评估范围失序")
        if (
            type(self.pre_risk_capacity) not in (int, float)
            or not 0 < self.pre_risk_capacity <= 1
        ):
            raise EvaluationError("V2容量需要显式零至一有限数")
        pairs = self.execution_symbols
        if (
            type(pairs) is not tuple
            or len(pairs) != 8
            or any(
                type(p) is not tuple
                or len(p) != 2
                or any(type(x) is not str for x in p)
                for p in pairs
            )
            or tuple(p[0] for p in pairs) != SYMBOLS
            or len({p[1] for p in pairs}) != 8
        ):
            raise EvaluationError("V2执行映射须有序完整一对一")
        import re

        if any(re.fullmatch(r"[0-9]{6}\.(?:SH|SZ)", p[1]) is None for p in pairs):
            raise EvaluationError("V2执行证券格式无效")

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {f.name for f in fields(cls)}:
            raise EvaluationError("V2配置字段不完整或含未知字段")
        data = dict(value)
        try:
            for name in ("history_start", "evaluation_start", "evaluation_end"):
                if type(data[name]) is not str or len(data[name]) != 10:
                    raise ValueError()
                data[name] = date.fromisoformat(data[name])
            pairs = data["execution_symbols"]
            if (
                type(pairs) is not list
                or len(pairs) != 8
                or any(type(p) is not list for p in pairs)
            ):
                raise ValueError()
            data["execution_symbols"] = tuple(tuple(p) for p in pairs)
            return cls(**data)
        except (TypeError, ValueError, OverflowError):
            raise EvaluationError("V2配置值未通过准入") from None


@dataclass(frozen=True, slots=True)
class FrozenV2SessionInput:
    strategy: V2BacktestSpec
    history: FrozenHistory
    native_mapping: tuple[tuple[str, str], ...]
    series: tuple
    policy: QuantityPolicy
    fee_reserve_cny: str | None
    fee_source: str | None
    market_manifest_source: str
    schema: str = INPUT_SCHEMA
    price_adjustment: str = "raw"
    price_unit: str = "CNY/share"
    volume_unit: str = "share"
    amount_unit: str = "CNY"
    daily_close: str = "Asia/Shanghai:15:00"


class V2Binding:
    """固定求值分支，无可变算法/数量状态；每次只调用真正NVT公共入口。"""

    def __init__(self, inputs, budget, *, deadline=None):
        from guanheng_strategy_v2 import V2Budget
        from importlib.metadata import version, PackageNotFoundError
        from .v2_package_profiles import current_packages

        try:
            if any(
                version(name) != expected
                for name, expected in current_packages().items()
            ):
                raise EvaluationError("V2固定计算包版本不匹配")
        except PackageNotFoundError:
            raise EvaluationError("V2固定计算包未安装") from None
        if (
            type(inputs) is not FrozenV2SessionInput
            or inputs.schema != INPUT_SCHEMA
            or type(inputs.strategy) is not V2BacktestSpec
        ):
            raise EvaluationError("需要本版冻结V2输入")
        # typed构造亦重验，不凭frozen/type跳过被篡改字段。
        self.spec = V2BacktestSpec(
            **{f.name: getattr(inputs.strategy, f.name) for f in fields(V2BacktestSpec)}
        )
        if type(inputs.history) is not FrozenHistory or not inputs.history.observations:
            raise EvaluationError("V2需要完整冻结历史")
        if budget is not None and type(budget) is not V2Budget:
            raise EvaluationError("V2预算类型无效")
        self.budget = (
            V2Budget()
            if budget is None
            else V2Budget(**{f.name: getattr(budget, f.name) for f in fields(V2Budget)})
        )
        end = monotonic() + self.budget.max_seconds if deadline is None else deadline

        def check():
            if monotonic() >= end:
                raise EvaluationError("V2准入期限耗尽")

        self.config_sha = digest(self.spec)
        self.policy_id = inputs.policy.policy_id
        self.execution = tuple(sorted(dict(self.spec.execution_symbols).values()))
        self.reads = set(SYMBOLS) | set(self.execution)
        self.benchmark = "510300.SH"
        rows = inputs.history.observations
        if (
            min(row.trade_date for row in rows) != self.spec.history_start
            or max(row.trade_date for row in rows) != self.spec.evaluation_end
        ):
            raise EvaluationError("V2历史实际边界与固定配置不同")
        keys = set()
        dates = set()
        for row in rows:
            check()
            keys.add((row.trade_date, row.symbol))
            dates.add(row.trade_date)
        dates = sorted(dates)
        check()
        if self.spec.evaluation_start not in dates:
            raise EvaluationError("V2评估起点缺少完整行情")
        if len(rows) != len(dates) * 8 or len(keys) != len(rows):
            raise EvaluationError("V2首原生域需要八证券共同完整日期")
        for day in dates:
            check()
            if any((day, symbol) not in keys for symbol in SYMBOLS):
                raise EvaluationError("V2首原生域需要八证券共同完整日期")
            if observation_close_at(day) != datetime.combine(
                day, datetime.min.time().replace(hour=15), timezone(timedelta(hours=8))
            ):
                raise EvaluationError("V2历史时区超出本原生固定收盘域")
        self.evaluate(
            inputs.history, observation_close_at(self.spec.evaluation_end), deadline=end
        )

    def evaluate(self, history, cutoff, *, deadline=None):
        from dataclasses import replace
        from guanheng_strategy_signals import SignalTraceInput
        from guanheng_strategy_v2 import evaluate_v2_history

        end = monotonic() + self.budget.max_seconds if deadline is None else deadline

        def remaining():
            left = end - monotonic()
            if left <= 0:
                raise EvaluationError("V2计算及投影期限耗尽")
            return replace(self.budget, max_seconds=min(left, self.budget.max_seconds))

        value = evaluate_v2_history(
            SignalTraceInput(
                history,
                self.spec.signal_profile,
                self.spec.evaluation_start,
                cutoff.date(),
                cutoff,
            ),
            pre_risk_capacity=self.spec.pre_risk_capacity,
            budget=remaining(),
        )
        pipeline = value.to_dict(budget=remaining())
        trace = value.signal_trace.to_dict(budget=remaining())
        remaining()
        daily = digest(
            {
                "stable_spec_sha256": self.config_sha,
                "signal_input_sha256": trace["input_sha256"],
                "cutoff": cutoff,
            },
            check=remaining,
        )
        allocation = pipeline["allocation"]
        raw = allocation["latest_raw_weights"]
        pairs = dict(raw) if raw is not None else {symbol: 0.0 for symbol in SYMBOLS}
        target = None
        admission = {
            "accepted": True,
            "policy_id": TARGET_POLICY,
            "code": "accepted",
            "raw_total": sum(
                (Fraction(repr(float(v))) for v in pairs.values()), Fraction(0)
            ),
        }
        total = admission.pop("raw_total")
        admission["raw_total_fraction"] = str(total)
        from guanheng_strategy_native import QuantityError

        try:
            target = EconomicTarget(
                self.spec.strategy_id,
                self.spec.algorithm_id,
                self.config_sha,
                self.policy_id,
                allocation["latest_event_date"],
                self.execution,
                tuple(
                    sorted(
                        (
                            Weight(
                                dict(self.spec.execution_symbols)[s],
                                repr(float(pairs[s])),
                            )
                            for s in SYMBOLS
                        ),
                        key=lambda w: w.symbol,
                    )
                ),
            )
        except QuantityError:
            if total <= 1:
                raise
            admission.update(accepted=False, code="blocked_raw_total")
        days = (self.spec.evaluation_end - self.spec.evaluation_start).days + 1
        rows = history.observations
        coverage = True
        benchmark_count = 0
        last_day = None
        for row in rows:
            remaining()
            last_day = (
                row.trade_date if last_day is None else max(last_day, row.trade_date)
            )
            if (
                row.symbol == "510300.SH"
                and row.trade_date <= self.spec.evaluation_start
            ):
                benchmark_count += 1
            if self.spec.evaluation_start <= row.trade_date <= self.spec.evaluation_end:
                coverage = (
                    coverage
                    and bool(row.evidence_refs)
                    and (
                        row.symbol == "159780.SZ"
                        or row.shares_delta_yi is not None
                        and row.auxiliary_available_at is not None
                    )
                    and (
                        row.symbol != "510300.SH"
                        or all(
                            getattr(row, k) is not None
                            for k in (
                                "share_probability",
                                "turnover_percentile",
                                "margin_percentile",
                            )
                        )
                    )
                )
        legacy = (
            last_day == self.spec.evaluation_end
            and 360 <= days <= 720
            and benchmark_count >= 100
            and coverage
        )
        header = {
            "kind": "resonance-v2",
            "pipeline": pipeline,
            "signal_trace": trace,
            "stable_spec_sha256": self.config_sha,
            "daily_input_sha256": daily,
            "target_admission": admission,
            "producer_readiness": {
                "native_input_ready": True,
                "legacy_offline_ready": bool(legacy),
                "source_qualified": False,
                "historically_produced": False,
            },
        }
        remaining()
        return header, target, daily, end


def _require(value, reason="V2报告字段或身份无效"):
    if not value:
        raise EvaluationError(reason)


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names.split()))


def _day(value):
    _require(type(value) is str and len(value) == 10)
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise EvaluationError("V2报告日期无效") from None
    _require(date(1900, 1, 1) <= result <= date(9998, 12, 31))
    return result


def _sha(value):
    import re

    _require(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None)


def _text(value, maximum=256):
    _require(
        type(value) is str
        and 0 < len(value) <= maximum
        and all(ord(c) >= 32 for c in value)
    )


def _number(value, minimum=None, maximum=None):
    _require(
        type(value) in (int, float)
        and (type(value) is not int or value.bit_length() <= 1024)
    )
    _require(
        math.isfinite(value)
        and (minimum is None or value >= minimum)
        and (maximum is None or value <= maximum)
    )


def _weights(value):
    _require(type(value) is list and len(value) == 8)
    for pair, symbol in zip(value, SYMBOLS, strict=True):
        _require(type(pair) is list and len(pair) == 2 and pair[0] == symbol)
        _number(pair[1], 0, 0.25)


def validate_shared_row(row, field, *, check=None):
    if check:
        check()
    if field == "allocation_events":
        _keys(row, "trade_date target_weights decision_paths evidence_refs")
        _weights(row["target_weights"])
        _require(
            type(row["decision_paths"]) is list and len(row["decision_paths"]) <= 8
        )
        for path in row["decision_paths"]:
            _text(path, 256)
        maximum = 136
    else:
        _keys(
            row,
            "symbol trade_date action strength path reason confidence evidence_refs available_at",
        )
        _require(
            row["symbol"] == SYMBOLS[int(field.split("_")[1])]
            and row["action"] in ("BUY", "SELL", "HOLD")
        )
        _number(row["strength"], 0, 1)
        _number(row["confidence"], 0, 1)
        _require(type(row["path"]) is str and len(row["path"]) <= 128)
        _require(type(row["reason"]) is str and len(row["reason"]) <= 256)
        from guanheng_strategy_core.contracts import utc_timestamp

        stamp = row["available_at"]
        _require(type(stamp) is str and len(stamp) <= 64)
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            raise EvaluationError("V2报告时间无效") from None
        _require(parsed == utc_timestamp(observation_close_at(_day(row["trade_date"]))))
        maximum = 17
    _day(row["trade_date"])
    refs = row["evidence_refs"]
    _require(type(refs) is list and len(refs) <= maximum)
    for ref in refs:
        if check:
            check()
        _text(ref, 256)


_META = "algorithm_id strategy_id strategy_version core_version core_wheel_sha256 feature_source_sha256 signal_source_sha256 input_sha256 trace_sha256 source_revision factor_revision signal_profile history_start evaluation_start evaluation_end knowledge_cutoff"


def validate_v2_header(header, day, *, check=None):
    """唯一Session validator调用的固定header核查；不再运行数学或复制宿主。"""
    if check:
        check()
    _keys(
        header,
        "kind pipeline signal_trace stable_spec_sha256 daily_input_sha256 target_admission producer_readiness",
    )
    _require(header["kind"] == "resonance-v2")
    for name in ("stable_spec_sha256", "daily_input_sha256"):
        _sha(header[name])
    pipeline, trace = header["pipeline"], header["signal_trace"]
    _keys(
        pipeline,
        "schema dependencies signal latest_features allocation source_qualified historically_produced execution_qualified scope pipeline_sha256",
    )
    _require(pipeline["schema"] == "guanheng.v2-history-result.v1")
    _sha(pipeline["pipeline_sha256"])
    _keys(pipeline["signal"], _META)
    _keys(
        trace,
        "schema "
        + _META
        + " feature_series_symbols decision_series latest_features historically_produced source_qualified execution_qualified scope",
    )
    _require(trace["schema"] == "guanheng.signal-trace.v1")
    for name in _META.split():
        _require(pipeline["signal"][name] == trace[name])
    _require(
        trace["algorithm_id"] == "resonance-regime-v2@0.1.0/no-cycle-signal-trace-v1"
        and trace["strategy_id"] == "resonance-regime-v2"
        and trace["strategy_version"] == "0.1.0"
        and trace["signal_profile"] == SIGNAL_PROFILE
    )
    from .v2_package_profiles import match_profile

    _require(
        match_profile(pipeline["dependencies"], trace) is not None
        and trace["feature_source_sha256"] == FEATURE_SOURCE_SHA256
        and trace["signal_source_sha256"] == SIGNAL_SOURCE_SHA256
    )
    for name in (
        "core_wheel_sha256",
        "feature_source_sha256",
        "signal_source_sha256",
        "input_sha256",
        "trace_sha256",
        "source_revision",
        "factor_revision",
    ):
        _sha(trace[name])
    from guanheng_strategy_core.contracts import utc_timestamp

    closed = _day(trace["evaluation_end"])
    _require(
        int(closed.strftime("%Y%m%d")) == day
        and _day(trace["history_start"]) <= _day(trace["evaluation_start"]) <= closed
    )
    _require(
        trace["knowledge_cutoff"]
        == utc_timestamp(observation_close_at(closed))
        .isoformat()
        .replace("+00:00", "Z")
    )
    _require(trace["feature_series_symbols"] == list(SYMBOLS))
    groups = trace["decision_series"]
    _require(type(groups) is list and len(groups) == 8)
    for group, symbol in zip(groups, SYMBOLS, strict=True):
        _keys(group, "symbol decisions")
        _require(group["symbol"] == symbol and group["decisions"] == [])
    for result in (pipeline, trace):
        _require(
            all(
                result[k] is False
                for k in (
                    "source_qualified",
                    "historically_produced",
                    "execution_qualified",
                )
            )
        )
        _text(result["scope"], 256)
    _require(pipeline["latest_features"] == trace["latest_features"])
    latest = trace["latest_features"]
    _require(type(latest) is list and len(latest) == 8)
    for feature, symbol in zip(latest, SYMBOLS, strict=True):
        _keys(
            feature,
            "symbol trade_date price_position volume_ratio change_pct trade_direction regime_score regime_label missing_auxiliary",
        )
        _require(feature["symbol"] == symbol and _day(feature["trade_date"]) == closed)
        for name in ("price_position", "volume_ratio", "change_pct", "regime_score"):
            if feature[name] is not None:
                _number(feature[name])
        _require(feature["trade_direction"] in ("NEUTRAL", "ACCUMULATE", "DISTRIBUTE"))
        _require(
            feature["regime_label"] is None
            or type(feature["regime_label"]) is str
            and len(feature["regime_label"]) <= 32
        )
        _require(
            type(feature["missing_auxiliary"]) is list
            and len(set(feature["missing_auxiliary"]))
            == len(feature["missing_auxiliary"])
            and set(feature["missing_auxiliary"])
            <= {
                "shares_delta_yi",
                "share_probability",
                "turnover_percentile",
                "margin_percentile",
            }
        )
    allocation = pipeline["allocation"]
    _keys(
        allocation,
        "schema algorithm_id strategy_id strategy_version source_sha256 time_policy timezone_data_sha256 input_sha256 source_revision factor_revision trace_sha256 signal_profile knowledge_cutoff history_start evaluation_start evaluation_end allocation_events latest_event_date latest_raw_weights new_event_for_cutoff state raw_diagnostic execution_qualified scope",
    )
    _require(
        allocation["schema"] == "guanheng.fixed-unit-result.v1"
        and allocation["algorithm_id"] == ARCHIVED_ALLOCATION_ALGORITHM
        and allocation["source_sha256"] == ARCHIVED_ALLOCATION_SOURCE_SHA256
        and allocation["strategy_id"] == "resonance-regime-v2"
        and allocation["strategy_version"] == "0.1.0"
        and allocation["allocation_events"] == []
        and allocation["execution_qualified"] is False
    )
    for name in (
        "source_revision",
        "factor_revision",
        "trace_sha256",
        "signal_profile",
        "knowledge_cutoff",
        "history_start",
        "evaluation_start",
        "evaluation_end",
    ):
        _require(allocation[name] == trace[name])
    for name in ("source_sha256", "timezone_data_sha256", "input_sha256"):
        _sha(allocation[name])
    _require(
        allocation["time_policy"] == "Asia/Shanghai@IANA2026c"
        and allocation["timezone_data_sha256"] == TZIF_SHA256
    )
    _text(allocation["scope"])
    _require(type(allocation["new_event_for_cutoff"]) is bool)
    if allocation["latest_event_date"] is None:
        _require(allocation["latest_raw_weights"] is None)
    else:
        _require(_day(allocation["latest_event_date"]) <= closed)
        _weights(allocation["latest_raw_weights"])
    state = allocation["state"]
    _keys(state, "active_buy_ranks sequence csi300_strength previous_raw_weights")
    _require(type(state["sequence"]) is int and 0 <= state["sequence"] <= 32768)
    _number(state["csi300_strength"], 0, 1)
    _require(state["previous_raw_weights"] == allocation["latest_raw_weights"])
    ranks = state["active_buy_ranks"]
    _require(type(ranks) is list and len(ranks) <= 7)
    seen = set()
    for pair in ranks:
        _require(
            type(pair) is list
            and len(pair) == 2
            and pair[0] in SYMBOLS
            and pair[0] != "510300.SH"
            and pair[0] not in seen
            and type(pair[1]) is int
            and 1 <= pair[1] <= state["sequence"]
        )
        seen.add(pair[0])
    diagnostic = allocation["raw_diagnostic"]
    _keys(
        diagnostic,
        "total_weight pre_risk_capacity exceeds_one exceeds_pre_risk_capacity",
    )
    _number(diagnostic["total_weight"], 0, 2)
    _number(diagnostic["pre_risk_capacity"], 0, 1)
    _require(diagnostic["pre_risk_capacity"] > 0)
    _require(
        type(diagnostic["exceeds_one"]) is bool
        and type(diagnostic["exceeds_pre_risk_capacity"]) is bool
    )
    admission = header["target_admission"]
    _keys(admission, "accepted policy_id code raw_total_fraction")
    _require(
        type(admission["accepted"]) is bool
        and admission["policy_id"] == TARGET_POLICY
        and admission["code"]
        == ("accepted" if admission["accepted"] else "blocked_raw_total")
    )
    import re

    _text(admission["raw_total_fraction"], 256)
    _require(
        re.fullmatch(
            r"(?:0|[1-9][0-9]{0,127})(?:/[1-9][0-9]{0,126})?",
            admission["raw_total_fraction"],
        )
        is not None
    )
    try:
        total = Fraction(admission["raw_total_fraction"])
    except (ValueError, ZeroDivisionError):
        raise EvaluationError("V2目标总量表示无效") from None
    raw = allocation["latest_raw_weights"] or [[s, 0] for s in SYMBOLS]
    raw_float_total = sum(pair[1] for pair in raw)
    _require(
        diagnostic["total_weight"] == raw_float_total
        and diagnostic["exceeds_one"] == (raw_float_total > 1)
        and diagnostic["exceeds_pre_risk_capacity"]
        == (raw_float_total > diagnostic["pre_risk_capacity"])
    )
    _require(
        total == sum((Fraction(repr(float(p[1]))) for p in raw), Fraction(0))
        and admission["accepted"] == (total <= 1)
    )
    readiness = header["producer_readiness"]
    _keys(
        readiness,
        "native_input_ready legacy_offline_ready source_qualified historically_produced",
    )
    _require(
        readiness["native_input_ready"] is True
        and type(readiness["legacy_offline_ready"]) is bool
        and readiness["source_qualified"] is False
        and readiness["historically_produced"] is False
    )
    if check:
        check()
