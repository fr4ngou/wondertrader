"""Immutable inputs and outputs for the independently implemented Resonance strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo
from .computation import checked

DEFAULT_SYMBOLS = ("510050.SH", "510300.SH", "510500.SH", "512100.SH", "588000.SH", "589680.SH", "159780.SZ", "515080.SH")
SUPPORTED_INPUT_SYMBOLS = set(DEFAULT_SYMBOLS) | {"589000.SH"}

TradeDirection = Literal["ACCUMULATE", "DISTRIBUTE", "NEUTRAL"]
Lamp = Literal["green", "red", "gray"]
SignalAction = Literal["BUY", "SELL", "HOLD"]


def observation_close_at(trade_date):
    return datetime.combine(trade_date, time(15, 0), tzinfo=ZoneInfo("Asia/Shanghai"))


@dataclass(frozen=True)
class DailyObservation:
    """One closed daily observation; optional fields are never imputed."""

    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    shares_delta_yi: float | None = None
    share_probability: float | None = None
    turnover_percentile: float | None = None
    margin_percentile: float | None = None
    auxiliary_available_at: datetime | None = None
    auxiliary_source_dates: tuple[date, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    market_available_at: datetime | None = None
    market_source_sha256: str = ""
    auxiliary_source_sha256: str | None = None


@dataclass(frozen=True)
class DailyFeature:
    """Closed-bar factors used by the strategy state machines."""

    observation: DailyObservation
    change_pct: float | None
    price_position: float | None
    volume_ratio: float | None
    trade_direction: TradeDirection
    regime_score: float | None = None
    regime_label: Literal["bull", "bear", "range", "insufficient"] = "insufficient"


@dataclass(frozen=True)
class ResonanceLights:
    """Five-lamp evidence for the 510300 generic resonance rule."""

    price_position: Lamp
    share_flow: Lamp
    trade_direction: Lamp
    turnover_heat: Lamp
    margin_leverage: Lamp

    @property
    def green_count(self) -> int:
        return sum(value == "green" for value in self.values())

    @property
    def red_count(self) -> int:
        return sum(value == "red" for value in self.values())

    def values(self) -> tuple[Lamp, Lamp, Lamp, Lamp, Lamp]:
        return (
            self.price_position,
            self.share_flow,
            self.trade_direction,
            self.turnover_heat,
            self.margin_leverage,
        )


@dataclass(frozen=True)
class ResonanceDecision:
    """One state transition emitted by a symbol-specific pure signal machine."""

    symbol: str
    trade_date: date
    action: SignalAction
    strength: float
    path: str
    reason: str
    confidence: float
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)


def validate_observations(values: list[DailyObservation], *, universe=None, check=None) -> list[DailyObservation]:
    """Normalize ordering and reject ambiguous or impossible market facts."""

    if not values:
        raise ValueError("resonance observations cannot be empty")
    supported = set(universe) if universe is not None else SUPPORTED_INPUT_SYMBOLS
    ordered = sorted(checked(values, check), key=lambda item: (item.trade_date, item.symbol.upper()))
    identities: set[tuple[str, date]] = set()
    for item in checked(ordered, check):
        symbol = item.symbol.upper()
        if symbol not in supported:
            raise ValueError("unsupported resonance ETF: {0}".format(symbol))
        identity = (symbol, item.trade_date)
        if identity in identities:
            raise ValueError("duplicate resonance observation: {0} {1}".format(*identity))
        identities.add(identity)
        if min(item.open, item.high, item.low, item.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if item.high < max(item.open, item.close, item.low):
            raise ValueError("daily high is inconsistent with OHLC")
        if item.low > min(item.open, item.close, item.high):
            raise ValueError("daily low is inconsistent with OHLC")
        if item.volume < 0 or item.amount < 0:
            raise ValueError("volume and amount cannot be negative")
        for name, percentile in (
            ("share_probability", item.share_probability),
            ("turnover_percentile", item.turnover_percentile),
            ("margin_percentile", item.margin_percentile),
        ):
            if percentile is not None and not 0 <= percentile <= 100:
                raise ValueError("{0} must be between 0 and 100".format(name))
        if (
            item.auxiliary_available_at is not None
            and item.auxiliary_available_at.tzinfo is None
        ):
            raise ValueError("auxiliary_available_at must be timezone-aware")
        if item.auxiliary_available_at is not None and item.auxiliary_available_at > observation_close_at(item.trade_date):
            raise ValueError("auxiliary facts were unavailable at the strategy close")
        if any(value > item.trade_date for value in item.auxiliary_source_dates):
            raise ValueError("auxiliary source date cannot be in the future")
    return ordered
