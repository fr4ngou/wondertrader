"""不可变公共值：经济目标、阶段 basis 与原生当次观察分别表达。"""

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from hashlib import sha256
import json
import re

from ._numbers import QuantityError, integer, number, rational, rows, text


POLICY_ID = "cash-etf-generation-sell-postsell-v1"
PROFILE_ID = "cash-etf-cny-share-m1-l100-v1"


def _timestamp(value: str) -> str:
    text(value, "observed_at", 40)
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError
    except (TypeError, ValueError, OverflowError) as exc:
        raise QuantityError("observed_at: timezone-aware ISO timestamp required") from exc
    return parsed.isoformat()


def _symbol(value: str) -> str:
    text(value, "symbol", 64)
    if re.fullmatch(r"[A-Z0-9][A-Z0-9._-]*", value) is None:
        raise QuantityError("symbol: canonical execution identifier required")
    return value


def _sha(value: str) -> None:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise QuantityError("input_sha256: lowercase SHA256 required")


def _flag(value: bool, name: str) -> None:
    if type(value) is not bool:
        raise QuantityError(f"{name}: bool required")


def _value(value):
    if is_dataclass(value):
        return {field.name: _value(getattr(value, field.name)) for field in fields(value)}
    if type(value) is tuple:
        return [_value(item) for item in value]
    return value


def digest(value) -> str:
    """本模块已验证的有界值内容身份；每日 basis 身份独立于经济代际。"""
    return sha256(json.dumps(_value(value), ensure_ascii=True, sort_keys=True,
                             separators=(",", ":")).encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class Weight:
    """单个 execution 证券的绝对权重，含零值；所有权重合计至多1。"""

    symbol: str
    weight: str

    def __post_init__(self):
        _symbol(self.symbol)
        object.__setattr__(self, "weight", number(self.weight, "weight"))
        if rational(self.weight) > 1:
            raise QuantityError("weight: exceeds one")


@dataclass(frozen=True, slots=True)
class EconomicTarget:
    """稳定配置须绑定完整 signal/execution 映射；weights 精确覆盖该 execution 集合。"""

    strategy_id: str
    algorithm_id: str
    config_id: str
    execution_policy_id: str
    allocation_date: str | None
    universe: tuple[str, ...]
    weights: tuple[Weight, ...]

    def __post_init__(self):
        for name in ("strategy_id", "algorithm_id", "config_id", "execution_policy_id"):
            text(getattr(self, name), name)
        if self.allocation_date is not None:
            text(self.allocation_date, "allocation_date", 10)
            try:
                if type(self.allocation_date) is not str or date.fromisoformat(
                    self.allocation_date
                ).isoformat() != self.allocation_date:
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise QuantityError("allocation_date: ISO date required") from exc
        if type(self.universe) is not tuple or not 1 <= len(self.universe) <= 8:
            raise QuantityError("universe: tuple of 1..8 execution symbols required")
        for symbol in self.universe:
            _symbol(symbol)
        if len(set(self.universe)) != len(self.universe):
            raise QuantityError("universe: duplicate execution symbol")
        object.__setattr__(self, "universe", tuple(sorted(self.universe)))
        object.__setattr__(self, "weights", rows(self.weights, Weight, "weights"))
        if tuple(row.symbol for row in self.weights) != self.universe:
            raise QuantityError("weights: incomplete execution universe")
        total = sum((rational(row.weight) for row in self.weights), start=0)
        if total > 1:
            raise QuantityError("weights: total exceeds one")
        if self.allocation_date is None and total:
            raise QuantityError("allocation_date: positive target requires allocation")


@dataclass(frozen=True, slots=True)
class QuantityPolicy:
    """首现金ETF份数模型。本金/来源为显式研究配置，禁止从账户总资产推定。"""

    initial_capital_cny: str
    capital_source: str
    policy_id: str = POLICY_ID
    profile_id: str = PROFILE_ID
    currency: str = "CNY"
    quantity_unit: str = "share"
    multiplier: int = 1
    lot: int = 100

    def __post_init__(self):
        object.__setattr__(self, "initial_capital_cny", number(
            self.initial_capital_cny, "initial_capital_cny"))
        if rational(self.initial_capital_cny) <= 0:
            raise QuantityError("initial_capital_cny: positive explicit capital required")
        text(self.capital_source, "capital_source")
        for name in ("policy_id", "profile_id", "currency", "quantity_unit"):
            text(getattr(self, name), name)
        if (self.policy_id, self.profile_id, self.currency, self.quantity_unit) != (
            POLICY_ID, PROFILE_ID, "CNY", "share"
        ) or type(self.multiplier) is not int or self.multiplier != 1 or (
            type(self.lot) is not int or self.lot != 100
        ):
            raise QuantityError("policy: unsupported units/profile/policy")


@dataclass(frozen=True, slots=True)
class Price:
    """当次 basis 的 raw 未复权 CNY/份；零权重可用 None 表示缺价。"""

    symbol: str
    raw_cny_per_share: str | None
    source: str
    adjustment: str = "raw"
    unit: str = "CNY/share"

    def __post_init__(self):
        _symbol(self.symbol)
        text(self.source, "price.source")
        text(self.adjustment, "price.adjustment")
        text(self.unit, "price.unit")
        if self.adjustment != "raw" or self.unit != "CNY/share":
            raise QuantityError("price: raw CNY/share required")
        if self.raw_cny_per_share is not None:
            value = number(self.raw_cny_per_share, "raw_price")
            if rational(value) <= 0:
                raise QuantityError("raw_price: positive price required")
            object.__setattr__(self, "raw_cny_per_share", value)


@dataclass(frozen=True, slots=True)
class Basis:
    """同步观察。NAV=显式本金+native flag0损益；verified 证明无外部流、费用及仓位覆盖。

    fee_reserve_cny 是此 basis 全组新增买入的预留；None 表示未知并等待。
    输入来源与时间须由适配器核实，纯模块的 verified 字段本身不授原生接线资格。
    """

    observed_at: str
    input_sha256: str
    nav_cny: str
    native_pnl_cny: str
    cash_cny: str
    fee_reserve_cny: str | None
    nav_source: str
    cash_source: str
    fee_source: str | None
    prices: tuple[Price, ...]
    native_nav_verified: bool
    native_observation_id: str

    def __post_init__(self):
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at))
        _sha(self.input_sha256)
        for name in ("nav_cny", "cash_cny"):
            object.__setattr__(self, name, number(getattr(self, name), name))
        object.__setattr__(self, "native_pnl_cny", number(
            self.native_pnl_cny, "native_pnl_cny", signed=True))
        for name in ("nav_source", "cash_source"):
            text(getattr(self, name), name)
        if self.fee_reserve_cny is not None:
            object.__setattr__(self, "fee_reserve_cny", number(
                self.fee_reserve_cny, "fee_reserve_cny"))
            text(self.fee_source, "fee_source")
        elif self.fee_source is not None:
            text(self.fee_source, "fee_source")
        object.__setattr__(self, "prices", rows(self.prices, Price, "prices"))
        _flag(self.native_nav_verified, "native_nav_verified")
        text(self.native_observation_id, "native_observation_id")


@dataclass(frozen=True, slots=True)
class NativePosition:
    """实际量与 pending 绝对目标严格分离；sellable 仅用于当次卖出资格。"""

    symbol: str
    actual: int
    sellable: int
    pending_target: int | None = None

    def __post_init__(self):
        _symbol(self.symbol)
        integer(self.actual, "actual")
        integer(self.sellable, "sellable")
        if self.sellable > self.actual:
            raise QuantityError("sellable: exceeds actual")
        if self.pending_target is not None:
            integer(self.pending_target, "pending_target")


@dataclass(frozen=True, slots=True)
class Observation:
    """当次原生事实观察；verified 要求实际、pending 与全部证券覆盖已独立核实。"""

    observed_at: str
    source: str
    positions: tuple[NativePosition, ...]
    verified: bool
    native_observation_id: str

    def __post_init__(self):
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at))
        text(self.source, "observation.source")
        object.__setattr__(self, "positions", rows(
            self.positions, NativePosition, "positions"))
        _flag(self.verified, "observation.verified")
        text(self.native_observation_id, "native_observation_id")


@dataclass(frozen=True, slots=True)
class Limits:
    """部署可收紧的硬预算：最多8证券、64阶段、65536输入字符串字符。"""

    max_stages: int = 16
    max_text_chars: int = 16384

    def __post_init__(self):
        integer(self.max_stages, "max_stages", 64)
        integer(self.max_text_chars, "max_text_chars", 65536)
        if self.max_stages < 1 or self.max_text_chars < 1:
            raise QuantityError("limits: invalid deployment budget")
