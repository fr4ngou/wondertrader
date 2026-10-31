"""QMT Broker 结果的集中转换；时间/量额/累计语义由已确认源 profile 提供。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import math
from types import MappingProxyType

from .models import Capability, IntegrationUnavailable, SourceSession, positive, symbol
from .shadow import aware


def verified_result(modules, payload, operation, known_at):
    """核对当前完整 v1 终态内容摘要；原始字典保留其时间文本与数字编码。"""
    raw = dict(payload) if isinstance(payload, dict) else payload.model_dump(mode="json")
    result = modules["contracts"].GatewayOperationResult.model_validate(raw)
    if (not result.ok or result.operation_id != operation or not result.result_sha256
            or aware(result.completed_at) > aware(known_at)):
        raise IntegrationUnavailable("Broker 结果缺失、失败、未来或缺少证据摘要", operation)
    expected = raw.pop("result_sha256", None)
    actual = hashlib.sha256(modules["broker_types"].canonical_json_bytes(raw)).hexdigest()
    if actual != expected:
        raise IntegrationUnavailable("Broker 结果正文与原持久摘要不符", operation)
    return result


@dataclass(frozen=True)
class QmtResponseProfile:
    profile_id: str
    version: str
    evidence_ref: str
    time_encoding: str
    bar_boundary: str
    volume_to_shares: float
    amount_to_yuan: float
    full_tick_cumulative: bool

    def __post_init__(self):
        if any(not isinstance(value, str) or not 1 <= len(value) <= 256
               for value in (self.profile_id, self.version, self.evidence_ref)):
            raise ValueError("源结果 profile 必须有版本和证据")
        if self.time_encoding != "epoch_ms" or self.bar_boundary not in ("left", "right"):
            raise IntegrationUnavailable("当前转换只支持明确的 epoch_ms 及分钟边界", "source_profile")
        positive(self.volume_to_shares, "源数量系数")
        positive(self.amount_to_yuan, "源金额系数")
        if type(self.full_tick_cumulative) is not bool:
            raise ValueError("累计快照语义必须明确")


@dataclass(frozen=True)
class SnapshotProjection:
    source: SourceSession
    security: str
    occurred_at: datetime
    price: float
    open: float
    high: float
    low: float
    previous_close: float
    cumulative_volume: float
    cumulative_amount: float
    result_sha256: str
    profile: QmtResponseProfile
    capability: Capability
    full_cumulative: bool = True


@dataclass(frozen=True)
class HistoryProjection:
    source: SourceSession
    bars: tuple
    result_sha256: str
    profile: QmtResponseProfile
    capability: Capability
    coverage: str = "unknown"
    alignment_revision: str | None = None


@dataclass(frozen=True)
class FiveMinuteGrid:
    """原日历/时段 owner 的明确五分钟区间，不在适配器推导开盘、午休或停牌规则。"""
    revision: str
    intervals: tuple[tuple[datetime, datetime], ...]
    _right_edges: object = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.revision, str) or not 1 <= len(self.revision) <= 256:
            raise ValueError("五分钟网格需要原 owner 的版本依据")
        values = tuple(tuple(item) for item in self.intervals)
        if not 1 <= len(values) <= 1000000 or any(len(item) != 2 for item in values):
            raise ValueError("五分钟网格区间为空或超限")
        for left, right in values:
            aware(left)
            aware(right)
            if any(value.second or value.microsecond for value in (left, right)) or right - left != timedelta(minutes=5):
                raise ValueError("原五分钟网格必须使用无秒/微秒的五分钟区间")
        ordered = sorted(values)
        if any(ordered[index][0] < ordered[index - 1][1] for index in range(1, len(ordered))):
            raise ValueError("原五分钟网格存在重复或重叠区间")
        object.__setattr__(self, "intervals", tuple(ordered))
        object.__setattr__(self, "_right_edges", MappingProxyType(dict(ordered)))

    def right_edge(self, left):
        # 对绝对时刻比较，UTC 和上海时区对同一边界得到相同结果。
        try:
            return self._right_edges[left]
        except KeyError as exc:
            raise IntegrationUnavailable("历史时点未落在原 owner 确认的五分钟网格", "market.market_data_ex") from exc


class QmtResultProjector:
    """外部模块与 SourceSession 注入；不调用 QMT，不猜测缺失字段或时间单位。"""

    def __init__(self, modules, source: SourceSession, capability: Capability, profile: QmtResponseProfile | None,
                 *, max_rows: int, five_minute_grid: FiveMinuteGrid | None = None):
        if (not isinstance(source, SourceSession) or source.provider != "Qmt"
                or type(max_rows) is not int or not 1 <= max_rows <= 1000000):
            raise ValueError("QMT 来源或转换预算不合格")
        if five_minute_grid is not None and not isinstance(five_minute_grid, FiveMinuteGrid):
            raise ValueError("五分钟网格必须来自明确的已校验区间")
        self.modules, self.source, self.capability, self.profile, self.max_rows = modules, source, capability, profile, max_rows
        self.five_minute_grid = five_minute_grid

    def _result(self, payload, operation, known_at):
        self.capability.require(operation)
        if self.profile is None:
            raise IntegrationUnavailable("源结果字段/单位/时间 profile 尚未确认", operation)
        return verified_result(self.modules, payload, operation, known_at)

    def _time(self, value):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise IntegrationUnavailable("源时间与 epoch_ms profile 不符", "source_time")
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        except (ValueError, OverflowError, OSError) as exc:
            raise IntegrationUnavailable("源时间超出范围", "source_time") from exc

    def snapshots(self, payload, securities, *, known_at, max_age: timedelta):
        result = self._result(payload, "market.full_tick", known_at)
        securities = tuple(securities)
        if (not securities or len(securities) != len(set(securities)) or len(securities) > self.max_rows
                or not isinstance(result.data, dict) or set(result.data) != set(securities)):
            raise IntegrationUnavailable("快照证券范围不完整或超限", "market.full_tick")
        if not self.profile.full_tick_cumulative:
            raise IntegrationUnavailable("源端完整累计快照语义尚未确认", "market.full_tick")
        if not timedelta(0) < max_age <= timedelta(minutes=5):
            raise ValueError("快照新鲜度预算不合格")
        snapshots = []
        for security in securities:
            symbol(security)
            row = result.data[security]
            required = {"time", "lastPrice", "open", "high", "low", "lastClose", "volume", "amount"}
            if not isinstance(row, dict) or not required <= set(row):
                raise IntegrationUnavailable("快照缺少完整价格/累计量额或源时间字段", "market.full_tick")
            stamp = self._time(row["time"])
            if not timedelta(0) <= known_at - stamp <= max_age:
                raise IntegrationUnavailable("源快照过期或来自未来", "market.full_tick")
            values = {}
            for key in ("lastPrice", "open", "high", "low", "lastClose"):
                values[key] = positive(row[key], key)
            volume, amount = row["volume"], row["amount"]
            if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in (volume, amount)):
                raise ValueError("快照累计量额不合格")
            if values["high"] < max(values["open"], values["lastPrice"]) or values["low"] > min(values["open"], values["lastPrice"]):
                raise ValueError("快照 OHLC 不一致")
            normalized_volume, normalized_amount = volume * self.profile.volume_to_shares, amount * self.profile.amount_to_yuan
            if not math.isfinite(normalized_volume) or not math.isfinite(normalized_amount):
                raise ValueError("快照量额换算溢出")
            snapshots.append(SnapshotProjection(self.source, security, stamp, values["lastPrice"], values["open"],
                values["high"], values["low"], values["lastClose"], normalized_volume,
                normalized_amount, result.result_sha256, self.profile, self.capability))
        return tuple(snapshots)

    def history(self, payload, securities, *, period: str, known_at):
        result = self._result(payload, "market.market_data_ex", known_at)
        securities = tuple(securities)
        if (period not in ("1m", "5m", "1d") or not securities or len(securities) != len(set(securities))
                or not isinstance(result.data, dict) or set(result.data) != set(securities)):
            raise IntegrationUnavailable("历史证券范围或周期不完整", "market.market_data_ex")
        if period != "1d" and self.profile.bar_boundary != "left":
            raise IntegrationUnavailable("原闭合校验器仅支持已确认的左端 QMT 分钟结果", "market.market_data_ex")
        if period == "5m" and self.five_minute_grid is None:
            raise IntegrationUnavailable("五分钟时段对齐需要原日历/时段 owner 的明确网格", "market.market_data_ex")
        canonical, identities, total = {}, {}, 0
        for security in securities:
            symbol(security)
            rows = result.data[security]
            if not isinstance(rows, list):
                raise IntegrationUnavailable("历史结果尚未编码为明确 records", "market.market_data_ex")
            canonical[security] = []
            for row in rows:
                total += 1
                if total > self.max_rows:
                    raise ValueError("历史转换超过记录预算")
                required = {"time", "open", "high", "low", "close", "volume", "amount"}
                if not isinstance(row, dict) or not required <= set(row):
                    raise IntegrationUnavailable("历史记录缺少明确时间或 OHLCV 字段", "market.market_data_ex")
                if any(type(row[field]) not in (int, float) or not math.isfinite(row[field])
                       for field in ("open", "high", "low", "close", "volume", "amount")):
                    raise ValueError("原生历史价格/量额必须为有限数值")
                stamp = self._time(row["time"])
                if period != "1d" and (stamp.second or stamp.microsecond):
                    raise ValueError("分钟源时间必须位于完整分钟格点，禁止取整")
                if period == "5m":
                    self.five_minute_grid.right_edge(stamp)
                checked = self.modules["contracts"].MarketBar(symbol=security, period=period, occurred_at=stamp,
                    **{field: row[field] for field in ("open", "high", "low", "close")},
                    volume=row["volume"] * self.profile.volume_to_shares, amount=row["amount"] * self.profile.amount_to_yuan)
                if checked.high < max(checked.open, checked.close, checked.low) or checked.low > min(checked.open, checked.close):
                    raise ValueError("历史 OHLC 不一致")
                identity = (security, stamp)
                semantic = checked.model_dump(mode="json")
                if identity in identities:
                    if identities[identity] != semantic:
                        raise ValueError("同一历史时点存在冲突")
                    continue
                identities[identity] = semantic
                canonical[security].append(dict(time=row["time"], **{key: getattr(checked, key)
                    for key in ("open", "high", "low", "close", "volume", "amount")}))
        bars = self.modules["bar_ingestion"].normalize_closed_bars(canonical, period=period, now=known_at)
        if period != "1d":
            step = timedelta(minutes=1 if period == "1m" else 5)
            bars = [bar.model_copy(update={"occurred_at": self.five_minute_grid.right_edge(bar.occurred_at)
                if period == "5m" else bar.occurred_at + step,
                "feature_version": "wt-right-{0}-v1".format(period)}) for bar in bars]
        return HistoryProjection(self.source, tuple(bars), result.result_sha256, self.profile, self.capability,
            alignment_revision=self.five_minute_grid.revision if period == "5m" else None)
