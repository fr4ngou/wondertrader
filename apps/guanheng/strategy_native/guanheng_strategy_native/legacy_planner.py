"""旧报告的只读阶段数学；保留原16阶段结果，运行入口不调用此实现。"""
from dataclasses import replace
from datetime import datetime
from ._numbers import QuantityError, rational
from .models import Limits
from .planner import (Basis, EconomicTarget, QuantityPolicy, Observation, StageState, Outcome, Quantity,
    _observe, _text_budget, _current_stage, _pending, target_quantities, generation_id, _cash_required)

_LEGACY_MAX_STAGES = 16  # 仅重放已冻结旧报告，保持旧结果与SHA语义。

def advance_legacy(
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
    if state is not None and state.sequence > 64:
        raise QuantityError("legacy state: unsupported stage sequence")
    _observe(target, policy, observation, basis)
    _text_budget((target, policy, observation, basis, state), limits)
    if state is not None:
        if state.sequence > _LEGACY_MAX_STAGES:
            return Outcome("blocked", "stage_budget_exhausted", state)
        if datetime.fromisoformat(observation.observed_at) < datetime.fromisoformat(
            state.basis.observed_at
        ):
            return Outcome("blocked", "observation_precedes_frozen_basis", state)
        if generation_id(target, policy) != state.generation_id:
            if state.phase != "converged":
                return Outcome("supersession_required", "prior_generation_unresolved", state)
            if target.universe != state.target.universe:
                return Outcome("supersession_required", "universe_handoff_required", state)
            check = _current_stage(state, observation)
            if check.status != "converged":
                return check
            # 新代际从当前原生观察开始，绝不暗示撤销旧pending。
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
    if sequence > _LEGACY_MAX_STAGES:
        return Outcome("blocked", "stage_budget_exhausted", state)
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
