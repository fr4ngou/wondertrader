"""不可变策略领域值；日期、来源、目标与执行权限分别命名。"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
import json
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from .models import DailyFeature, DailyObservation, ResonanceDecision
from .computation import checked

if TYPE_CHECKING:
    from .historical_model import HistoricalEodModel

STRATEGY_ID = "resonance-regime-v1"
STRATEGY_VERSION = "1.2.0"
KERNEL_VERSION = "configured-resonance-kernel-1"
OBSERVATION_VERSION = "resonance-daily-closed-v3"


class KernelValidationError(ValueError):
    """稳定原因码与可公开中文说明；失败时没有可提交的新目标。"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _strict_fields(cls, value):
    if (type(value) is not dict or any(type(key) is not str for key in value)
            or set(value) - {f.name for f in fields(cls)}):
        raise KernelValidationError("invalid_payload", "策略输入字段不符合本领域契约")
    return dict(value)


def _timestamp(value):
    if isinstance(value, str):
        if len(value) > 64:
            raise KernelValidationError("invalid_time", "策略时间表示超出允许长度")
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise KernelValidationError("invalid_time", "策略时间必须为带时区的ISO时间") from exc
    return value


def utc_timestamp(value: datetime) -> datetime:
    """共享时间准入与编码边界；标准时区仍须能归一化为可表示UTC。"""
    if (type(value) is not datetime or type(value.tzinfo) not in (timezone, ZoneInfo)
            or value.utcoffset() is None):
        raise KernelValidationError("invalid_time", "策略时间必须使用明确且不可变的标准时区")
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise KernelValidationError("time_unrepresentable", "策略时间超出UTC可表示范围") from exc


def json_value(value, *, check=None):
    """生成确定性公开值；UTC归一化使等价时区表达具有相同身份。"""
    if check is not None:
        check()
    if is_dataclass(value):
        return {f.name: json_value(getattr(value, f.name), check=check) for f in fields(value)
                if not (f.metadata.get("omit_none") and getattr(value, f.name) is None)}
    if isinstance(value, datetime):
        return utc_timestamp(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [json_value(item, check=check) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item, check=check) for key, item in value.items()}
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_bytes(value, *, check=None, max_bytes=None):
    """普通helper保留编码；预算调用按有界JSON块检查，输出超限提前拒绝。

    已准入字符串和容器分别受256字符/32768行等上限约束；单次字符串
    转义、排序、bytearray扩容及最终bytes复制有界，属于非抢占步骤。
    """
    if check is None and max_bytes is None:
        return json.dumps(json_value(value), ensure_ascii=True, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("ascii")
    public = json_value(value, check=check)
    encoder = json.JSONEncoder(ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    result = bytearray()
    for chunk in checked(encoder.iterencode(public), check, interval=32):
        result.extend(chunk.encode("ascii"))
        if max_bytes is not None and len(result) > max_bytes:
            raise KernelValidationError("capacity_exceeded", "策略结果超出输出容量")
    if check is not None:
        check()
    result = bytes(result)
    if check is not None:
        check()
    return result


@dataclass(frozen=True)
class ConfiguredStrategyConfig:
    """角色键同时连接信号与执行证券；权重是业务请求，不授交易权限。

    minimum_history_days 指当前日之前的完整交易日数。配置有效期约束当前
    close及knowledge_cutoff，历史预热允许早于配置创建时间。
    """

    config_revision: str
    symbol_roles: tuple[tuple[str, str], ...]
    execution_symbols: tuple[tuple[str, str], ...]
    benchmark_role: str
    valid_from: datetime
    valid_until: datetime
    minimum_history_days: int = 100
    regime_ma_period: int = 100
    position_window: int = 60
    volume_window: int = 20
    budget_weight: float = 0.8
    symbol_cap_weight: float = 0.25
    max_weight_change: float = 0.25
    strategy_id: str = STRATEGY_ID
    strategy_version: str = STRATEGY_VERSION
    observation_version: str = OBSERVATION_VERSION
    warmup_policy: str = "regime-available-v1"

    @classmethod
    def from_dict(cls, value):
        data = _strict_fields(cls, value)
        for key in ("symbol_roles", "execution_symbols"):
            item = data.get(key)
            if isinstance(item, dict):
                item = sorted(item.items())
            if isinstance(item, (list, tuple)):
                item = tuple(tuple(pair) if isinstance(pair, (tuple, list)) else pair for pair in item)
            data[key] = item
        for key in ("valid_from", "valid_until"):
            data[key] = _timestamp(data.get(key))
        try:
            return cls(**data)
        except TypeError as exc:
            raise KernelValidationError("invalid_config", "策略配置缺少必要字段") from exc

    def to_dict(self):
        return json_value(self)


@dataclass(frozen=True)
class FrozenHistory:
    """全标的完整且有序的前缀；revision指内容来源，全部修订重新计算。"""

    observations: tuple[DailyObservation, ...]
    source_revision: str
    factor_revision: str

    @classmethod
    def from_dict(cls, value):
        data = _strict_fields(cls, value)
        rows = data.get("observations")
        if not isinstance(rows, (list, tuple)) or len(rows) > 32768:
            raise KernelValidationError("capacity_exceeded", "冻结历史超出允许条数")
        converted = []
        for row in rows:
            item = _strict_fields(DailyObservation, row)
            try:
                if isinstance(item.get("trade_date"), str):
                    item["trade_date"] = date.fromisoformat(item["trade_date"])
                for name in ("market_available_at", "auxiliary_available_at"):
                    if name in item:
                        item[name] = _timestamp(item[name])
                for name in ("evidence_refs", "auxiliary_source_dates"):
                    if name in item:
                        if type(item[name]) not in (list, tuple):
                            raise KernelValidationError("invalid_history", "来源证据及日期必须使用明确序列")
                        item[name] = tuple(item[name])
                item["auxiliary_source_dates"] = tuple(
                    date.fromisoformat(day) if isinstance(day, str) else day
                    for day in item.get("auxiliary_source_dates", ())
                )
                converted.append(DailyObservation(**item))
            except (TypeError, ValueError) as exc:
                raise KernelValidationError("invalid_history", "冻结历史字段格式无效") from exc
        data["observations"] = tuple(converted)
        try:
            return cls(**data)
        except TypeError as exc:
            raise KernelValidationError("invalid_history", "冻结历史缺少来源身份") from exc

    def to_dict(self):
        return json_value(self)


@dataclass(frozen=True)
class EvaluationBudget:
    """仅收紧部署容量，不改变业务阈值；大输入在分配计算结构前拒绝。"""

    max_history_days: int = 4096
    max_observations: int = 32768
    max_output_bytes: int = 8 * 1024 * 1024
    max_text_characters: int = 8 * 1024 * 1024
    max_seconds: float = 5.0


@dataclass(frozen=True)
class DailyFrame:
    trade_date: date
    decisions: tuple[ResonanceDecision, ...]
    auxiliary_qualified: bool


@dataclass(frozen=True)
class CurrentTarget:
    role: str
    signal_symbol: str
    execution_symbol: str
    target_weight: float
    source_allocation_date: date | None


@dataclass(frozen=True)
class SignalState:
    role: str
    symbol: str
    # JSON字符串固定内部状态，避免frozen dataclass中嵌入可变dict。
    state_json: str


@dataclass(frozen=True)
class AuxiliaryGap:
    trade_date: date
    symbol: str
    missing_fields: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationResult:
    kernel_version: str
    strategy_id: str
    strategy_version: str
    config_sha256: str
    input_sha256: str
    source_revision: str
    factor_revision: str
    knowledge_cutoff: datetime
    first_ready_date: date
    last_closed_date: date
    daily_frames: tuple[DailyFrame, ...]
    allocation_events: tuple
    current_targets: tuple[CurrentTarget, ...]
    latest_features: tuple[DailyFeature, ...]
    signal_states: tuple[SignalState, ...]
    auxiliary_gaps: tuple[AuxiliaryGap, ...]
    qualified: bool
    qualification_reasons: tuple[str, ...]
    historical_model: HistoricalEodModel | None = field(default=None, metadata={"omit_none": True})

    def to_dict(self):
        return json_value(self)
