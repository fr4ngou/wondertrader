"""与 ProviderTypes.h 对齐的只读投影；状态不授予账户或执行权限。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re


class IntegrationUnavailable(RuntimeError):
    """可诊断的能力/依赖缺口，调用方可直接投影到观衡健康页面。"""

    def __init__(self, reason: str, capability: str = "dependency"):
        self.reason, self.capability = reason, capability
        super().__init__(reason)

    def as_dict(self):
        return {"state": "unavailable", "capability": self.capability, "reason": self.reason}


QUALIFICATIONS = ("Unavailable", "DevelopmentVerified", "NativeVerified", "ProductionQualified")


@dataclass(frozen=True)
class Capability:
    supported: bool = False
    qualification: str = "Unavailable"
    reason: str = "尚未提供合格后端"

    def __post_init__(self):
        if type(self.supported) is not bool or self.qualification not in QUALIFICATIONS:
            raise ValueError("能力或资格枚举不合格")
        if not self.supported and self.qualification != "Unavailable":
            raise ValueError("未支持能力必须保持不可用资格")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("能力必须保留原因")

    def require(self, name: str, minimum: str = "DevelopmentVerified"):
        if minimum not in QUALIFICATIONS:
            raise ValueError("资格门槛不合格")
        if not self.supported or QUALIFICATIONS.index(self.qualification) < QUALIFICATIONS.index(minimum):
            raise IntegrationUnavailable(self.reason, name)


@dataclass(frozen=True)
class SourceSession:
    provider: str
    instance_id: str
    session_id: str
    generation: int

    def __post_init__(self):
        if self.provider not in ("Qmt", "Tdx"):
            raise ValueError("未知行情来源")
        if any(not isinstance(v, str) or not v or len(v) > 128 for v in (self.instance_id, self.session_id)):
            raise ValueError("来源实例或会话不合格")
        if type(self.generation) is not int or not 1 <= self.generation < 2**64:
            raise ValueError("来源代际必须为非零 uint64 整数")


def symbol(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", value):
        raise ValueError("证券代码必须为六位代码及 SH/SZ 后缀")
    return value


def positive(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + "必须为有限正数")
    return value


@dataclass(frozen=True)
class MarketBar:
    """标准库同字段投影；原 QMT 安装可将 native reader 的 DTO 工厂换为原 MarketBar。

    quantity 使用股、amount 使用元，occurred_at 为源端带时区的右端时间。
    来源/复权/资格由 HistoryResult.metadata 持有，避免改变既有 MarketBar schema。
    """
    symbol: str
    period: str
    occurred_at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    feature_version: str = "market-v1"

    def __post_init__(self):
        symbol(self.symbol)
        if self.period not in ("tick", "1m", "5m", "1d") or not isinstance(self.occurred_at, datetime) or self.occurred_at.tzinfo is None:
            raise ValueError("行情周期或源时间不合格")
        for name in ("open", "high", "low", "close"):
            positive(getattr(self, name), name)
        for name in ("volume", "amount"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("行情量额不合格")
        if self.high < max(self.open, self.low, self.close) or self.low > min(self.open, self.high, self.close):
            raise ValueError("行情 OHLC 不一致")
