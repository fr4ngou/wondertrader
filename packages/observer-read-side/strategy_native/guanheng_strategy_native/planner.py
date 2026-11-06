"""纯分阶段推进；无原生API、数据库、撮合、现金账或委托副作用。"""

from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import datetime

from ._numbers import QuantityError, integer, rational, rows, text
from .models import (
    Basis, EconomicTarget, Limits, Observation, QuantityPolicy, digest,
)


def generation_id(target: EconomicTarget, policy: QuantityPolicy) -> str:
    """稳定经济身份；每日输入、basis、价格、NAV与观察时点完全独立。"""
    if type(target) is not EconomicTarget or type(policy) is not QuantityPolicy:
        raise QuantityError("generation: EconomicTarget and QuantityPolicy required")
    return digest(("nsq-generation-v1", target, policy))


@dataclass(frozen=True, slots=True)
class Quantity:
    """绝对理论目标份数；整数在 native double 的精确范围内。"""

    symbol: str
    shares: int

    def __post_init__(self):
        from .models import _symbol

        _symbol(self.symbol)
        integer(self.shares, "shares")


def _complete(target, policy, basis):
    if type(target) is not EconomicTarget or type(policy) is not QuantityPolicy or (
        type(basis) is not Basis
    ):
        raise QuantityError("target/policy/basis: exact public value types required")
    if tuple(row.symbol for row in basis.prices) != target.universe:
        raise QuantityError("prices: incomplete execution universe")
    if any(rational(weight.weight) > 0 and price.raw_cny_per_share is None
           for weight, price in zip(target.weights, basis.prices, strict=True)):
        raise QuantityError("raw_price: positive-weight price unavailable")
    if not basis.native_nav_verified:
        raise QuantityError("basis: unverified native strategy NAV")
    if rational(policy.initial_capital_cny) + rational(basis.native_pnl_cny) != rational(
        basis.nav_cny
    ):
        raise QuantityError("NAV: explicit genesis plus native flag0 PnL mismatch")


def target_quantities(
    target: EconomicTarget, policy: QuantityPolicy, basis: Basis,
) -> tuple[Quantity, ...]:
    """精确执行 100*floor(weight*NAV/raw_price/100)，返回完整且排序的份数向量。

    正权重缺价拒绝；零权重直接为0。该计算结果尚未取得提交或成交资格。
    """
    _complete(target, policy, basis)
    result = []
    for weight, price in zip(target.weights, basis.prices, strict=True):
        if rational(weight.weight) == 0:
            quantity = 0
        else:
            if price.raw_cny_per_share is None:
                raise QuantityError("raw_price: positive-weight price unavailable")
            lots = rational(weight.weight) * rational(basis.nav_cny) / (
                rational(price.raw_cny_per_share) * policy.lot
            )
            quantity = (lots.numerator // lots.denominator) * policy.lot
        result.append(Quantity(weight.symbol, quantity))
    return tuple(result)


def _cash_required(targets, starts, basis):
    if basis.fee_reserve_cny is None:
        return None
    notional = rational(basis.fee_reserve_cny)
    for target, start, price in zip(targets, starts, basis.prices, strict=True):
        delta = target.shares - start.shares
        if delta > 0:
            if price.raw_cny_per_share is None:
                raise QuantityError("buy: raw price unavailable")
            notional += delta * rational(price.raw_cny_per_share)
    return notional


@dataclass(frozen=True, slots=True)
class StageState:
    """可重建的冻结决策，非持仓账。starts仅记录该阶段冻结瞬间的basis范围。

    调用者恢复时构造同一版本完整值；构造器重新核对向量、basis与现金不变量。
    相同state可重复推进；本模块不对原生写入、成交或pending撤销作确认。
    """

    target: EconomicTarget  # 当前冻结阶段对应的完整经济目标。
    policy: QuantityPolicy  # 数量单位、整手与明确本金的计算规则。
    basis: Basis  # 冻结时的价格、资金和原生观察身份。
    phase: str  # 等待买入、卖出、买入或已完成的业务阶段。
    sequence: int  # 当前计划的诊断阶段序号；不限制可执行次数。
    starts: tuple[Quantity, ...]  # 冻结时实际数量，界定允许的阶段进展。
    targets: tuple[Quantity, ...]  # 本阶段完整冻结目标，保留零数量证券。
    version: int = 1  # 冻结值结构版本，恢复时完整核验。

    def __post_init__(self):
        if type(self.version) is not int or self.version != 1:
            raise QuantityError("state: unsupported version")
        if type(self.phase) is not str or self.phase not in (
            "awaiting_buy", "selling", "buying", "converged"
        ):
            raise QuantityError("state: invalid phase")
        if type(self.sequence) is not int or self.sequence < 0:
            raise QuantityError("state: nonnegative diagnostic sequence required")
        if (self.phase == "awaiting_buy" and self.sequence != 0) or (
            self.phase != "awaiting_buy" and self.sequence < 1
        ):
            raise QuantityError("state: invalid stage sequence")
        object.__setattr__(self, "starts", rows(self.starts, Quantity, "starts"))
        object.__setattr__(self, "targets", rows(self.targets, Quantity, "targets"))
        computed = target_quantities(self.target, self.policy, self.basis)
        if self.target.allocation_date is None:
            raise QuantityError("state: initializing target cannot freeze")
        if tuple(row.symbol for row in self.starts) != self.target.universe or (
            tuple(row.symbol for row in self.targets) != self.target.universe
        ):
            raise QuantityError("state: incomplete frozen universe")
        if self.phase in ("selling", "awaiting_buy"):
            expected = tuple(Quantity(row.symbol, min(row.shares, start.shares))
                             for row, start in zip(computed, self.starts, strict=True))
            if self.targets != expected:
                raise QuantityError("state: inconsistent frozen sell vector")
            has_sells = any(start.shares > row.shares for start, row in zip(
                self.starts, self.targets, strict=True))
            if has_sells != (self.phase == "selling"):
                raise QuantityError("state: sell settlement qualification differs from frozen vector")
        else:
            if self.targets != computed or any(start.shares > row.shares
                                              for start, row in zip(
                                                  self.starts, computed, strict=True)):
                raise QuantityError("state: inconsistent frozen buy vector")
            required = _cash_required(self.targets, self.starts, self.basis)
            if required is None or required > rational(self.basis.cash_cny):
                raise QuantityError("state: buy not fully funded at frozen basis")

    @property
    def generation_id(self) -> str:
        return generation_id(self.target, self.policy)

    @property
    def state_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class Outcome:
    """status/reason为纯判定；submit_targets为空即禁止本次写入。

    非空向量仍须宿主完整预校验、受限提交及读回；不代表已调用或已成交。
    state在等待/冲突时保留原冻结内容。
    """

    status: str
    reason: str
    state: StageState | None
    submit_targets: tuple[Quantity, ...] = ()

    def __post_init__(self):
        text(self.status, "outcome.status")
        text(self.reason, "outcome.reason")
        if self.status not in (
            "initializing", "selling", "waiting_basis", "waiting_sellable", "waiting_pending",
            "waiting_cash", "waiting_fee", "buying", "converged", "supersession_required", "blocked",
        ):
            raise QuantityError("outcome: invalid status")
        if self.state is not None and type(self.state) is not StageState:
            raise QuantityError("outcome: invalid state type")
        if type(self.submit_targets) is not tuple:
            raise QuantityError("outcome: immutable submit tuple required")
        if self.submit_targets:
            normalized = rows(self.submit_targets, Quantity, "submit_targets")
            if self.state is None or normalized != self.state.targets or self.status not in (
                "selling", "buying"
            ):
                raise QuantityError("outcome: submission differs from executable frozen stage")
            object.__setattr__(self, "submit_targets", normalized)


def _text_budget(values, limits):
    used = 0

    def visit(value):
        nonlocal used
        if type(value) is str:
            used += len(value)
            if used > limits.max_text_chars:
                raise QuantityError("input: total text deployment budget exceeded")
        elif type(value) is tuple:
            for item in value:
                visit(item)
        elif is_dataclass(value):
            for field in fields(value):
                visit(getattr(value, field.name))

    visit(values)


def _observe(target, policy, observation, basis):
    _complete(target, policy, basis)
    if type(observation) is not Observation or not observation.verified:
        raise QuantityError("observation: verified separate actual/pending facts required")
    if observation.observed_at != basis.observed_at:
        raise QuantityError("observation: basis timestamp differs")
    if observation.native_observation_id != basis.native_observation_id:
        raise QuantityError("observation: coherent native capture identity differs")
    if tuple(row.symbol for row in observation.positions) != target.universe:
        raise QuantityError("observation: incomplete execution universe")


def _pending(observation, state):
    expected = {} if state is None else {row.symbol: row.shares for row in state.targets}
    pending = tuple(row for row in observation.positions if row.pending_target is not None)
    if any(row.pending_target != expected.get(row.symbol) for row in pending):
        return Outcome("blocked", "native_pending_conflict", state)
    if pending:
        return Outcome("waiting_pending", "native_pending_unresolved", state)
    return None


def _within(observation, state):
    for observed, start, target in zip(
        observation.positions, state.starts, state.targets, strict=True
    ):
        low, high = sorted((start.shares, target.shares))
        if not low <= observed.actual <= high or (
            state.phase == "converged" and observed.actual != target.shares
        ):
            return False
    return True


def _current_stage(state, observation):
    if not _within(observation, state):
        return Outcome("blocked", "actual_outside_frozen_stage", state)
    pending = _pending(observation, state)
    if pending is not None:
        return pending
    settled = all(row.actual == target.shares for row, target in zip(
        observation.positions, state.targets, strict=True))
    if settled:
        if state.phase in ("selling", "awaiting_buy"):
            return None
        completed = state if state.phase == "converged" else replace(state, phase="converged")
        return Outcome("converged", "frozen_buy_actual_confirmed", completed)
    if state.phase == "selling":
        if any(row.actual - target.shares > row.sellable for row, target in zip(
            observation.positions, state.targets, strict=True)):
            return Outcome("waiting_sellable", "native_sellable_insufficient", state)
        return Outcome("selling", "frozen_sell_ready", state, state.targets)
    return Outcome("buying", "frozen_buy_ready", state, state.targets)


def advance(
    target: EconomicTarget,
    policy: QuantityPolicy,
    observation: Observation,
    basis: Basis,
    state: StageState | None = None,
    *,
    limits: Limits = Limits(),
) -> Outcome:
    """由当次原生观察推进一个阶段，无I/O及副作用，输入不合格抛 QuantityError。

    有非零卖差才冻结selling；无卖差可在同coherent basis直接冻结buy。
    真实卖出结清后须新的原生capture；未知pending/T+1不足及旧未决代际均等待。
    """
    if type(limits) is not Limits or (state is not None and type(state) is not StageState):
        raise QuantityError("limits/state: exact public value types required")
    _observe(target, policy, observation, basis)
    _text_budget((target, policy, observation, basis, state), limits)
    if state is not None:
        if datetime.fromisoformat(observation.observed_at) < datetime.fromisoformat(
            state.basis.observed_at
        ):
            return Outcome("blocked", "observation_precedes_frozen_basis", state)
        if generation_id(target, policy) != state.generation_id:
            if target.universe != state.target.universe:
                return Outcome("supersession_required", "universe_handoff_required", state)
            check = _current_stage(state, observation)
            if check is not None and check.status != "converged":
                return check
            if state.phase == "selling" and (
                basis.native_observation_id == state.basis.native_observation_id
            ):
                return Outcome("waiting_basis", "fresh_post_sell_basis_required", state)
            # actual已到旧冻结阶段目标、pending为空，直接按本次最新经济目标接续。
            # 旧卖出阶段结束不等于旧整轮买入完成；无需计算或保留旧买入费用。
            state = None
        else:
            current = _current_stage(state, observation)
            if current is not None:
                return current
            if state.phase == "selling" and (
                basis.native_observation_id == state.basis.native_observation_id
            ):
                return Outcome("waiting_basis", "fresh_post_sell_basis_required", state)

    if target.allocation_date is None:
        return Outcome("initializing", "no_dated_allocation", None)
    if state is None:
        pending = _pending(observation, None)
        if pending is not None:
            return pending
    computed = target_quantities(target, policy, basis)
    starts = tuple(Quantity(row.symbol, row.actual) for row in observation.positions)
    sequence = 1 if state is None else state.sequence + 1
    if any(start.shares > row.shares for start, row in zip(
        starts, computed, strict=True
    )):
        targets = tuple(Quantity(row.symbol, min(row.shares, start.shares))
                        for row, start in zip(computed, starts, strict=True))
        frozen = StageState(target, policy, basis, "selling", sequence, starts, targets)
        _text_budget((frozen,), limits)
        return _current_stage(frozen, observation)
    if state is None:
        # 无卖差意味着尚未发生本代际卖出/费用；同一coherent basis足以核买入。
        state = StageState(target, policy, basis, "awaiting_buy", 0, starts, starts)
    required = _cash_required(computed, starts, basis)
    if required is None:
        return Outcome("waiting_fee", "explicit_buy_fee_reserve_unavailable", state)
    if required > rational(basis.cash_cny):
        return Outcome("waiting_cash", "whole_buy_group_unfunded", state)
    frozen = StageState(target, policy, basis, "buying", sequence, starts, computed)
    _text_budget((frozen,), limits)
    return _current_stage(frozen, observation)
