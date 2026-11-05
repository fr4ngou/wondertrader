"""唯一1.2.1与NSQ之间的业务接缝；原生owner提供周期、价格和策略资本。"""
from dataclasses import dataclass, fields, replace
from datetime import datetime
from zoneinfo import ZoneInfo

from guanheng_strategy_core.contracts import EvaluationBudget
from guanheng_strategy_native import EconomicTarget, QuantityPolicy, Weight, Limits, advance, generation_id
from guanheng_strategy_v1 import (
    STRATEGY_ID, STRATEGY_VERSION, ALGORITHM_ID,
    RetainedHistoricalModel, RetainedInput, RetainedResult, evaluate_current_view,
    evaluate_historical_model,
)
from guanheng_strategy_v1.role_profile import READABLE_STRATEGY_VERSIONS


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
    return _target_for_identity(value, policy, (STRATEGY_ID, STRATEGY_VERSION, ALGORITHM_ID), previous_target)


def target_for_report_result(value, policy, *, strategy_id, strategy_version, algorithm_id, previous_target=None):
    """原归档只读复核使用其原版本身份；不改变实时入口或原NSQ资金/数量规则。"""
    if (strategy_id != STRATEGY_ID or strategy_version not in READABLE_STRATEGY_VERSIONS
            or algorithm_id != strategy_id+'@'+strategy_version+'/ledger-front-ratio-v1'):
        raise ValueError('归档策略身份不属于受支持报告族')
    return _target_for_identity(value, policy, (strategy_id, strategy_version, algorithm_id), previous_target)


def _target_for_identity(value, policy, identity, previous_target):
    """实时与归档复用原经济目标投影；身份由各自准入边界明确提供。"""
    if type(policy) is not QuantityPolicy:
        raise ValueError('需要原NSQ明确的策略理论资本policy')
    if (value['strategy_id'], value['strategy_version']) != identity[:2]:
        raise ValueError('策略目标与本次角色版本不匹配')
    target = EconomicTarget(value['strategy_id'], identity[2],
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


def advance_retained(target, policy, observation, basis, state, *, limits=Limits(), basis_for_target=None):
    """前代交接与原NSQ推进；可选纯装配器按实际消费目标提供费用basis。

    basis_for_target(target,basis,observation)只装配原来源值，不执行金融操作；
    默认直接复用原basis，已有回放/读取调用保持原行为。旧代与新代各调用一次，
    份数、阶段、现金判定和冻结状态继续完全由原NSQ拥有。
    """
    def current_basis(current):
        return basis if basis_for_target is None else basis_for_target(current,basis,observation)
    previous_status, outcome = None, None
    if state is not None and generation_id(target, policy) != state.generation_id:
        prior = advance(state.target, policy, observation, current_basis(state.target), state, limits=limits)
        previous_status = prior.status
        if prior.status == 'converged':
            state = prior.state
        else:
            outcome = prior
    if outcome is None:
        outcome = advance(target, policy, observation, current_basis(target), state, limits=limits)
    return outcome, previous_status
