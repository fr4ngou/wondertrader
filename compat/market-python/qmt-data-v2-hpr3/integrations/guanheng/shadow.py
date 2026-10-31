"""以源事件/回放时间驱动同一个外部纯策略，产出原 StrategyIntent 影子目标。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5


def aware(value: datetime):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("策略时间必须包含明确时区")
    return value


class ShadowClock:
    """每个策略实例一个时钟；预热和补发仅供状态重建，不创建执行意图。

    live 的 now 由可信运行上下文显式提供；replay 仅取回放源时间。
    watermark 阻止重复/乱序事件；状态资格与账户执行资格仍由原业务服务管理。
    """

    def __init__(self, mode: str, *, max_lag: timedelta):
        if mode not in ("replay", "live") or not timedelta(0) < max_lag <= timedelta(days=1):
            raise ValueError("影子时钟模式或新鲜度预算不合格")
        self.mode, self.max_lag = mode, max_lag
        self.watermark = None

    def admit(self, occurred_at: datetime, *, delivery: str = "current", now=None) -> bool:
        aware(occurred_at)
        if delivery not in ("current", "warmup", "backfill"):
            raise ValueError("未知事件投递类别")
        if delivery != "current":
            return False
        if self.mode == "live":
            aware(now)
            if not timedelta(0) <= now - occurred_at <= self.max_lag:
                return False
        if self.watermark is not None and occurred_at <= self.watermark:
            return False
        self.watermark = occurred_at
        return True


@dataclass(frozen=True)
class ReplayResult:
    decisions: tuple
    intents: tuple
    state: dict


class ResonanceShadow:
    """只适配已登记 resonance-regime-v1 沪深300纯核心，不实现信号或账本规则。

    modules 由 ExternalQmt.strategy 提供。输入为已结束日线及显式辅助证据；
    WT 的分钟/当前 bar 必须先经过有资格的日线闭合链，不能静默当成完整日线。
    """

    def __init__(self, modules, *, config_id: UUID, config_version: str, budget_weight: float,
                 symbol_cap_weight: float, intent_lifetime: timedelta):
        if not isinstance(config_id, UUID) or not config_version or not timedelta(0) < intent_lifetime <= timedelta(days=1):
            raise ValueError("影子策略上下文不合格")
        if not 0 < symbol_cap_weight <= budget_weight <= 0.95:
            raise ValueError("影子目标预算不合格")
        self.modules = modules
        self.config_id, self.config_version = config_id, config_version
        self.budget, self.cap, self.lifetime = budget_weight, symbol_cap_weight, intent_lifetime

    def observations(self, bars, *, auxiliary=None):
        result = []
        for bar in bars:
            if bar.period != "1d" or bar.symbol != "510300.SH":
                raise ValueError("当前纯核心切片只接受已结束的 510300.SH 日线")
            aware(bar.occurred_at)
            fields = dict((auxiliary or {}).get(bar.occurred_at.date(), {}))
            available = fields.get("auxiliary_available_at")
            if available is not None and aware(available) > bar.occurred_at:
                raise ValueError("辅助数据在决策时间之后获知")
            if any(day > bar.occurred_at.date() for day in fields.get("auxiliary_source_dates", ())):
                raise ValueError("辅助数据引用未来日期")
            result.append(self.modules["models"].DailyObservation(
                symbol=bar.symbol, trade_date=bar.occurred_at.date(), open=bar.open, high=bar.high,
                low=bar.low, close=bar.close, volume=bar.volume, amount=bar.amount, **fields))
        return self.modules["models"].validate_observations(result)

    def replay(self, observations, *, incremental: bool) -> ReplayResult:
        """整段/逐条模式共享信号核心和目标转换；因果特征分别按整段/前缀计算。"""
        rows = self.modules["models"].validate_observations(list(observations))
        state, decisions = {}, []
        if incremental:
            for end in range(1, len(rows) + 1):
                features = self.modules["features"].build_daily_features(rows[:end])["510300.SH"]
                state_out = {}
                decisions.extend(self.modules["signals"].run_csi300_resonance(
                    features, state=state, state_out=state_out, start_index=end - 1))
                state = state_out
        else:
            features = self.modules["features"].build_daily_features(rows)["510300.SH"]
            decisions = self.modules["signals"].run_csi300_resonance(features, state_out=state)
        return ReplayResult(tuple(decisions), self._intents(decisions), state)

    def _intents(self, decisions):
        values, current = [], 0.0
        clock = ShadowClock("replay", max_lag=self.lifetime)
        for decision in decisions:
            value = self.target(decision, current_target=current, clock=clock)
            if value is None:
                raise ValueError("策略决策出现重复或倒序")
            current = value.target_weight
            values.append(value)
        return tuple(values)

    def target(self, decision, *, current_target: float, clock: ShadowClock, delivery="current", now=None):
        """原策略目标 DTO 的统一出口；预热/补发/过期与重复决策返回 None。"""
        stamp = self.modules["models"].observation_close_at(decision.trade_date)
        if delivery in ("warmup", "backfill"):
            return None
        if clock.mode == "live" and aware(now) >= stamp + self.lifetime:
            return None
        correlation = uuid5(NAMESPACE_URL, "guanheng-shadow:{0}:{1}:{2}:{3}".format(
            self.config_id, self.config_version, decision.symbol, decision.trade_date))
        value = self.modules["strategy"].build_intent(
            decision=decision, occurred_at=stamp, valid_until=stamp + self.lifetime,
            correlation_id=correlation, config_id=self.config_id, config_version=self.config_version,
            budget_weight=self.budget, current_target_weight=current_target, symbol_cap_weight=self.cap)
        return value if clock.admit(stamp, delivery=delivery, now=now) else None

    def compare(self, observations):
        """返回可供审阅的同输入结果；不比较模拟成交或生产账户事实。"""
        frozen = tuple(observations)
        whole, incremental = self.replay(frozen, incremental=False), self.replay(frozen, incremental=True)
        same = (whole.decisions == incremental.decisions and whole.state == incremental.state
                and [v.model_dump(mode="json") for v in whole.intents]
                == [v.model_dump(mode="json") for v in incremental.intents])
        if not same:
            raise ValueError("相同冻结输入的整段/增量决策或影子目标不一致")
        return whole, incremental
