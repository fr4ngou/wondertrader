"""唯一1.1.2与NSQ之间的业务接缝；原生owner提供周期、价格和策略资本。"""
from dataclasses import dataclass, fields, replace
from datetime import datetime
from zoneinfo import ZoneInfo

from guanheng_strategy_core.contracts import EvaluationBudget
from guanheng_strategy_native import EconomicTarget, QuantityPolicy, Weight, Limits, advance, generation_id
from guanheng_strategy_v1 import (
    RetainedHistoricalModel, RetainedInput, RetainedResult, evaluate_current_view,
    evaluate_historical_model,
)


@dataclass(frozen=True, slots=True)
class RetainedDecision:
    result: RetainedResult
    target: EconomicTarget


def evaluate_retained(request: RetainedInput, policy: QuantityPolicy, *,
                      historical_model: RetainedHistoricalModel | None = None,
                      previous_target: EconomicTarget | None = None,
                      budget=EvaluationBudget()) -> RetainedDecision:
    """一次调用唯一纯核，再将封闭结果完整交原NSQ；此层不算份数或撮合。"""
    if type(policy) is not QuantityPolicy:
        raise ValueError('需要原NSQ明确的策略理论资本policy')
    policy = QuantityPolicy(**{name: getattr(policy, name) for name in policy.__dataclass_fields__})
    result = (evaluate_current_view(request, budget=budget) if historical_model is None
        else evaluate_historical_model(request, historical_model, budget=budget))
    value = result.to_dict()
    return RetainedDecision(result, target_for_result(value, policy, previous_target=previous_target))


def target_for_result(value, policy, *, previous_target=None):
    """纯核结果的唯一经济目标投影；报告摘要复用同一投影核对状态。"""
    if type(policy) is not QuantityPolicy:
        raise ValueError('需要原NSQ明确的策略理论资本policy')
    target = EconomicTarget(value['strategy_id'], 'resonance-regime-v1@1.1.2/ledger-front-ratio-v1',
        value['configuration_sha256'], policy.policy_id, value['source_allocation_date'],
        tuple(sorted(value['targets'])),
        tuple(Weight(symbol, repr(float(weight))) for symbol, weight in sorted(value['targets'].items())))
    if previous_target is not None:
        if type(previous_target) is not EconomicTarget:
            raise ValueError('上一经济目标须来自原NSQ状态')
        previous_target = EconomicTarget(**{f.name: getattr(previous_target, f.name) for f in fields(EconomicTarget)})
        stable = ('strategy_id', 'algorithm_id', 'config_id', 'execution_policy_id', 'universe', 'weights')
        if all(getattr(target, k) == getattr(previous_target, k) for k in stable):
            target = replace(target, allocation_date=previous_target.allocation_date)
        elif (previous_target.allocation_date is not None
                and (target.allocation_date is None or target.allocation_date <= previous_target.allocation_date)):
            day = datetime.fromisoformat(value['decision_cutoff'].replace('Z', '+00:00')).astimezone(ZoneInfo('Asia/Shanghai')).date()
            target = replace(target, allocation_date=day.isoformat())
    return target


def advance_retained(target, policy, observation, basis, state, *, limits=Limits()):
    """回放的前代交接与原NSQ推进；生产者和报告核查共享完整状态转换。"""
    previous_status, outcome = None, None
    if state is not None and generation_id(target, policy) != state.generation_id:
        prior = advance(state.target, policy, observation, basis, state, limits=limits)
        previous_status = prior.status
        if prior.status == 'converged':
            state = prior.state
        else:
            outcome = prior
    if outcome is None:
        outcome = advance(target, policy, observation, basis, state, limits=limits)
    return outcome, previous_status
