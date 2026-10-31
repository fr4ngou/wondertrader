"""将已校验 WT 历史映射为原观衡前端/策略 DTO；数据与资格证据独立保留。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from time import monotonic
from uuid import NAMESPACE_URL, uuid5

from .models import IntegrationUnavailable, symbol
from .shadow import aware
from .source_projection import verified_result


@dataclass(frozen=True)
class CompatibilityResult:
    value: object
    source_metadata: tuple
    state: str
    reason: str


class RetainedMarketData:
    """保持原 DTO；source_metadata 携带 WT/来源资格，不向旧 schema 伪造新枚举。

    history 由 NativeHistory 返回。已有完整日线才可映射日线批次，分钟不隐式提升为
    收盘日线。旧 coverage 的 qmt-1d-v1 来源约束无法表达 TDX，明确 unavailable。
    """

    def __init__(self, modules):
        self.modules, self.contracts = modules, modules["contracts"]

    def chart(self, security, period, history=None, *, limit=240, before=None, unavailable_reason=None):
        symbol(security)
        if period not in ("1m", "5m", "1d") or type(limit) is not int or not 1 <= limit <= 2000:
            raise ValueError("行情图周期或条数不合格")
        if before is not None:
            aware(before)
        if unavailable_reason:
            bars, metadata, state, reason = (), (), "unavailable", str(unavailable_reason)
        elif history is None:
            bars, metadata, state, reason = (), (), "empty", "尚无已准备的权威历史"
        else:
            if history.metadata.period != period:
                raise IntegrationUnavailable("请求周期尚未准备；分钟聚合由 WT 原有链负责", "history")
            bars = tuple(history.bars)
            if any(b.symbol != security or b.period != period for b in bars):
                raise ValueError("历史范围与图表请求不符")
            bars = tuple(b for b in bars if before is None or b.occurred_at <= before)[-limit:]
            metadata, state, reason = (history.metadata,), "ready" if bars else "empty", "已读取冻结原生历史" if bars else "请求区间尚无历史"
        candles = [self.contracts.MarketChartCandle(occurred_at=b.occurred_at, open=b.open,
            high=b.high, low=b.low, close=b.close, volume=b.volume) for b in bars]
        value = self.contracts.MarketChartBundle(symbol=security, period=period, candles=candles,
            data_available=bool(candles), as_of=candles[-1].occurred_at if candles else None,
            missing_reason=None if candles else reason, source_period=period,
            source_bar_count=len(bars), source_kind="market_bars" if bars else None)
        return CompatibilityResult(value, metadata, state, reason)

    def coverage(self, histories: dict, *, trade_date, generated_at: datetime, observation_version="resonance-daily-closed-v1"):
        aware(generated_at)
        required = self.contracts.RESONANCE_OBSERVATION_SYMBOLS.get(observation_version)
        if required is None:
            raise IntegrationUnavailable("当前覆盖适配只消费原 v1/v2 固定证券集", "coverage")
        if set(histories) - set(required):
            raise ValueError("日线覆盖超出所选观察版本")
        items, evidence, future_count = [], [], 0
        for security in required:
            history = histories.get(security)
            latest = None
            if history:
                if history.metadata.period != "1d" or history.metadata.source.provider != "Qmt":
                    raise IntegrationUnavailable("旧覆盖 DTO 只接受明确的 QMT 日线来源", "coverage")
                evidence.append(history.metadata)
                if any(b.symbol != security or b.period != "1d" or b.feature_version != "qmt-1d-v1" for b in history.bars):
                    raise IntegrationUnavailable("旧覆盖 DTO 需要原 qmt-1d-v1 来源事实", "coverage")
                known = []
                for bar in history.bars:
                    if aware(bar.occurred_at) <= generated_at:
                        known.append(bar)
                    else:
                        future_count += 1
                latest = max(known, key=lambda bar: bar.occurred_at) if known else None
            day = latest.occurred_at.astimezone(self.contracts.SHANGHAI_TIME_ZONE).date() if latest else None
            status = "unavailable" if day is None else "current" if day == trade_date else "stale" if day < trade_date else "future"
            items.append(self.contracts.ResonanceDailyBarCoverageItem(symbol=security,
                latest_closed_at=latest.occurred_at if latest else None, latest_trade_date=day,
                status=status, matches_trade_date=status == "current"))
        covered = sum(item.matches_trade_date for item in items)
        value = self.contracts.ResonanceDailyBarCoverage(observation_version=observation_version,
            trade_date=trade_date, generated_at=generated_at, items=items,
            covered_symbol_count=covered, required_symbol_count=len(required), complete=covered == len(required))
        reason = "覆盖仅取生成时刻前已获知的闭合日线"
        if future_count:
            reason += "；{0}条晚于生成时刻的日线未计入，等待源闭合时刻后重新读取".format(future_count)
        return CompatibilityResult(value, tuple(evidence), "ready" if value.complete else "incomplete", reason)

    def batch(self, histories: dict, *, trade_date, closed_at, valid_until,
              observation_version="resonance-daily-closed-v1", auxiliary=None):
        aware(closed_at)
        aware(valid_until)
        required = self.contracts.RESONANCE_OBSERVATION_SYMBOLS.get(observation_version)
        if required is None or set(histories) != set(required):
            raise IntegrationUnavailable("完整批次需要所选版本的全部已闭合日线", "daily_batch")
        observations, evidence, metadata = [], [], []
        for security in required:
            history = histories[security]
            if history.metadata.period != "1d":
                raise IntegrationUnavailable("分钟数据尚未取得日线闭合资格", "daily_batch")
            rows = [b for b in history.bars if b.symbol == security and b.occurred_at.date() == trade_date]
            if len(rows) != 1 or rows[0].occurred_at > closed_at:
                raise IntegrationUnavailable("日线缺失、重复或晚于批次关闭时刻", "daily_batch")
            bar = rows[0]
            reference = "wt-dsb:" + history.metadata.content_id
            observations.append(self.contracts.ResonanceDailyObservation(symbol=security, trade_date=trade_date,
                open=bar.open, high=bar.high, low=bar.low, close=bar.close, volume=bar.volume, amount=bar.amount,
                evidence_refs=[reference], **dict((auxiliary or {}).get(security, {}))))
            evidence.append(reference)
            metadata.append(history.metadata)
        identity = self.contracts.resonance_observation_set_sha256(observations)
        value = self.contracts.ResonanceDailyClosedBatch(batch_id=uuid5(NAMESPACE_URL, "wt-batch:" + identity),
            observation_version=observation_version, trade_date=trade_date, closed_at=closed_at,
            valid_until=valid_until, observations=observations, observation_set_sha256=identity, evidence_refs=evidence)
        return CompatibilityResult(value, tuple(metadata), "ready", "完整日线批次；executable=false")

    def analysis_window(self, *, raw, adjusted, factors, basis_date, known_at, source, capability):
        """复用原复权/因果证据校验，缺少原生因子证据时明确不可用。"""
        if source.provider != "Qmt":
            raise IntegrationUnavailable("原分析窗口 DTO 需要 QMT 原生因子及复权证据", "analysis")
        capability.require("analysis")
        try:
            for values, operation in ((raw, "market.market_data_ex"), (adjusted, "market.market_data_ex"), (factors, "market.divid_factors")):
                for payload in values.values():
                    verified_result(self.modules, payload, operation, known_at)
            value = self.modules["analysis"].build_analysis_window(raw=raw, adjusted=adjusted,
                factors=factors, basis_date=basis_date, known_at=aware(known_at))
        except (ValueError, TypeError) as exc:
            raise IntegrationUnavailable("分析窗口证据不完整：" + str(exc), "analysis") from exc
        return CompatibilityResult(value, (source, capability), "ready", "沿用原 QMT 复权窗口校验与修订身份")


class ChartReadInterface:
    """原 Console client.get 接缝；已准备历史读取由明确的 loader 提供。

    loader(security,period,limit,before) 在原调用者的有界 worker 执行，不发补数或交易。
    其它服务继续交给原只读客户端；缺少该依赖时报告缺口。此对象不创建网络客户端。
    """

    def __init__(self, market: RetainedMarketData, history_loader, *, other_reads=None):
        self.market, self.history_loader, self.other_reads = market, history_loader, other_reads

    def get(self, service, path, *, params=None, timeout, max_attempts=1):
        if (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0
                or type(max_attempts) is not int or max_attempts != 1):
            raise ValueError("只读接口要求显式单尝试与有限期限")
        if service != "market-data":
            if self.other_reads is None:
                raise IntegrationUnavailable("缺少原业务只读客户端：" + str(service), "console_overlay")
            return self.other_reads.get(service, path, params=params, timeout=timeout, max_attempts=1)
        prefix = "/v1/market/chart/"
        if not isinstance(path, str) or not path.startswith(prefix):
            raise IntegrationUnavailable("尚未注册此原 MarketData 接口", "market_read")
        security = symbol(path[len(prefix):])
        params = dict(params or {})
        if set(params) - {"period", "limit", "before"}:
            raise ValueError("图表读取参数尚未支持")
        period, limit, before = params.get("period", "1d"), params.get("limit", 240), params.get("before")
        if isinstance(before, str):
            before = datetime.fromisoformat(before.replace("Z", "+00:00"))
        if period not in ("1m", "5m", "1d") or type(limit) is not int or not 1 <= limit <= 2000:
            raise ValueError("图表周期或条数不合格")
        if before is not None:
            aware(before)
        started = monotonic()
        try:
            history = self.history_loader(security, period, limit, before)
            result = self.market.chart(security, period, history, limit=limit, before=before)
        except (IntegrationUnavailable, OSError, ValueError) as exc:
            result = self.market.chart(security, period, unavailable_reason="原生历史暂不可用：" + str(exc))
        if monotonic() - started > timeout:
            raise TimeoutError("原生历史读取超过调用期限")
        return result.value.model_dump(mode="json")
