"""唯一策略的只读业务诊断；消费原计算结果，不重算信号或决定交易准入。"""
from collections import Counter
from copy import deepcopy
from datetime import date
import json

from .role_profile import ROLE_SYMBOLS

SCHEMA = 'guanheng.strategy-business-diagnostics.v1'
SUMMARY_SCHEMA = 'guanheng.strategy-business-diagnostics-summary.v1'
MARKET_FIELDS = ('open', 'high', 'low', 'close', 'volume', 'amount')
# 仅声明原信号机实际读取的辅助字段及其分支；阈值、灯色和买卖仍归原数学实现。
BRANCH_FIELDS = {
    'csi300': {'resonance_lamps': ('share_probability', 'turnover_percentile', 'margin_percentile')},
    'sh50': {'entries': ('shares_delta_yi',), 'sh50_large_redemption': ('shares_delta_yi',)},
    'kc50': {'entries': ('shares_delta_yi',), 'large_subscription_exemption': ('shares_delta_yi',)},
    'kc_composite': {'kc_cluster_reversal': ('shares_delta_yi',), 'kc_distribution_cluster': ('shares_delta_yi',)},
    'zz500': {'zz500_cluster_reversal': ('shares_delta_yi',), 'zz500_distribution_cluster': ('shares_delta_yi',)},
    'zz1000': {}, 'sc50': {}, 'dividend': {},
}
CALCULATION_STATES = ('not_scheduled', 'market_not_ready', 'warming_up', 'input_rejected',
                      'calculation_failed', 'completed')
EXECUTION_STATES = ('not_observed', 'not_requested', 'pending', 'completed', 'failed')


def _value(row, field):
    return row.get(field) if type(row) is dict else getattr(row, field, None)


def _day(value):
    if type(value) is date:
        return value.isoformat()
    if type(value) is str and len(value) == 10 and date.fromisoformat(value).isoformat() == value:
        return value
    raise ValueError('诊断输入需要明确交易日期')


def _coverage(rows, days, field):
    present = sorted(day for day in days if day in rows and _value(rows[day], field) is not None)
    missing_rows = len(days - rows.keys())
    missing_values = len(days)-len(present)-missing_rows
    return dict(
        expected_count=len(days),  # 对应输入/评估日期范围应有行数，不以已有行数冒充分母。
        non_null_count=len(present),  # 显式零和负份额变化均算已有值，None单独计缺失。
        first_non_null_date=present[0] if present else None,  # 首个有值的市场日期，非来源取得日。
        last_non_null_date=present[-1] if present else None,  # 最后有值日期，空覆盖保持None。
        missing_reasons={key: count for key, count in (
            ('observation_missing', missing_rows), ('not_supplied_in_observation', missing_values)) if count},
        # 来源未发布/请求失败等细因只能沿上游证据读取；空字段本身不证明具体来源故障。
    )


def describe_evaluation(observations, *, role_symbols=None, evaluation_dates=(), decisions=None,
                        calculation_state='not_scheduled', error_code=None, targets=None,
                        previous_targets=None, execution_state='not_observed', check=None):
    """统一实时/回测诊断，输入为已冻结事实及原机器结果；全部无IO。

    evaluation_dates来自实际交给原信号机的日期。未执行计算时保留空评估范围；
    历史报告可显式给原角色映射，避免用当前ETF替换旧报告身份。缺值不推断来源原因。
    target和execution独立投影，缺少执行证据时保持not_observed。
    """
    roles = dict(ROLE_SYMBOLS if role_symbols is None else role_symbols)
    if (set(roles) != set(BRANCH_FIELDS) or len(set(roles.values())) != 8
            or calculation_state not in CALCULATION_STATES or execution_state not in EXECUTION_STATES):
        raise ValueError('诊断角色或阶段无效')
    if not isinstance(observations, (tuple, list)) or len(observations) > 32768:
        raise ValueError('诊断输入超过原历史容量')
    grouped = {symbol: {} for symbol in roles.values()}
    input_days = set()
    research_models = set()
    for row in observations:
        if check is not None:
            check()
        day, symbol = _day(_value(row, 'trade_date')), _value(row, 'symbol')
        if symbol not in grouped or day in grouped[symbol]:
            raise ValueError('诊断输入证券或日期重复')
        grouped[symbol][day] = row
        research_models.update(ref.split(':', 1)[1] for ref in (_value(row, 'evidence_refs') or ())
                               if ref.startswith('auxiliary-research:'))
        input_days.add(day)
    evaluated = {_day(day) for day in evaluation_dates}
    if not evaluated <= input_days or len(input_days) > 4096 or len(research_models) > 1:
        raise ValueError('诊断评估日期不属于原输入')
    latest = max(evaluated) if evaluated else None
    role_values = {}
    for role, symbol in roles.items():
        if check is not None:
            check()
        rows = grouped[symbol]
        auxiliary = tuple(dict.fromkeys(field for values in BRANCH_FIELDS[role].values() for field in values))
        coverage = {field: dict(input=_coverage(rows, input_days, field),
                                evaluation=_coverage(rows, evaluated, field))
                    for field in MARKET_FIELDS+auxiliary}
        current = rows.get(latest)
        missing = [field for field in auxiliary if current is not None and _value(current, field) is None]
        branches = {}
        for branch, fields in BRANCH_FIELDS[role].items():
            absent = [field for field in fields if current is not None and _value(current, field) is None]
            # CSI300原五灯至少三灯；缺一部分辅助灯仍可能触发，三辅助全空则至多两灯。
            unavailable = bool(absent) and (branch != 'resonance_lamps' or len(absent) == len(fields))
            branches[branch] = dict(
                required_fields=list(fields),  # 此分支真正读取的辅助字段，其余角色不强制四字段。
                missing_fields=absent,  # 最新实际评估日缺字段，不代表所有独立路径不可计算。
                state=('not_evaluated' if current is None else 'unavailable' if unavailable else
                       'partially_observed' if absent else 'inputs_present'))
        signals = (decisions or {}).get(symbol, ())
        signals_recorded = decisions is not None or not evaluated
        counts = Counter(_value(item, 'action') for item in signals
                         if _day(_value(item, 'trade_date')) in evaluated)
        dated = [item for item in signals if latest is not None and _day(_value(item, 'trade_date')) == latest]
        latest_action = _value(dated[-1], 'action') if dated else 'HOLD' if latest and signals_recorded else None
        informed = [day for day in evaluated if day in rows
                    and all(_value(rows[day], field) is not None for field in auxiliary)]
        role_values[symbol] = dict(
            role=role,  # 业务角色；物理证券由本次显式角色映射拥有。
            field_coverage=coverage,  # 每个实际依赖字段的完整输入及实际模型评估覆盖。
            auxiliary_fields=list(auxiliary),  # 原规则所需辅助项，无依赖的角色为空列表。
            latest_missing_fields=missing,  # 最新已评估日的缺失项，未评估保持空并明确状态。
            branches=branches,  # 缺失影响哪些分支；独立价格退出/其他入场仍沿原规则。
            input_state='not_evaluated' if latest is None else 'input_missing' if missing else 'ready',
            signal_counts=dict(BUY=counts['BUY'], SELL=counts['SELL']) if signals_recorded else None,  # 模型信号数；旧报告未存次数时保持未知，不当零次。
            latest_action=latest_action,  # 当日原机器输出；没有转换时明确HOLD。
            signal_state=('not_evaluated' if latest is None else 'not_recorded' if not signals_recorded else 'signal_generated' if dated else
                          'input_missing' if missing else 'conditions_not_met'),
            last_successful_calculation_date=latest,  # 原机器成功完成调用的最近市场日，允许合法None输入。
            last_fully_informed_date=max(informed) if informed else None,  # 该角色全部依赖字段同时有值的最近评估日。
        )
    target_state = 'not_calculated' if targets is None else 'produced'
    if targets is not None and previous_targets is not None and targets == previous_targets:
        target_state = 'unchanged'
    return dict(
        schema=SCHEMA,  # 只读业务诊断版本，独立于策略数学版本及执行授权。
        auxiliary_availability_model=next(iter(research_models)) if research_models else 'actually-received',  # 研究知晓假设与默认真实取得路径明确区分。
        calculation_state=calculation_state,  # 未调度/行情/预热/输入/计算与成功分开表达。
        error_code=error_code,  # 原稳定错误码；不回显异常、账户或完整配置。
        input_range=dict(first_date=min(input_days) if input_days else None,
                         last_date=max(input_days) if input_days else None, expected_dates=len(input_days)),
        evaluation_range=dict(first_date=min(evaluated) if evaluated else None,
                              last_date=latest, expected_dates=len(evaluated)),
        roles=role_values,  # 按实际物理ETF索引，保持原角色身份。
        target_state=target_state,  # 产生完整目标与比较后不变分开；不推断是否提交交易。
        execution_state=execution_state,  # 缺少原执行证据时保持not_observed，不能当作执行成功。
    )


def summarize_diagnostics(value):
    """原生逐日报告保留紧凑语义；完整字段覆盖只在报告末日保存一次。"""
    return dict(schema=SUMMARY_SCHEMA, auxiliary_availability_model=value['auxiliary_availability_model'], calculation_state=value['calculation_state'],
        error_code=value['error_code'], target_state=value['target_state'], execution_state=value['execution_state'],
        roles={symbol: {key: deepcopy(row[key]) for key in ('role', 'latest_missing_fields', 'input_state',
            'signal_counts', 'latest_action', 'signal_state', 'last_successful_calculation_date',
            'last_fully_informed_date')} for symbol, row in value['roles'].items()})


def contextualize_diagnostics(value, *, targets=None, previous_targets=None, execution_state=None):
    """读取层复用同一语义添加实际目标比较/执行阶段，不修改原纯核结果或资金。"""
    result = deepcopy(value)
    if targets is not None:
        result['target_state'] = 'unchanged' if previous_targets is not None and targets == previous_targets else 'produced'
    if execution_state is not None:
        if execution_state not in EXECUTION_STATES:
            raise ValueError('诊断执行阶段无效')
        result['execution_state'] = execution_state
    return result


def failure_diagnostics(error_code):
    """失败尚无完整输入覆盖证据；只投影原稳定错误，不继续昂贵计算或伪造零覆盖。"""
    phase = ('warming_up' if error_code == 'warmup_required' else 'market_not_ready'
             if error_code in ('incomplete_history', 'opening_history_missing', 'initial_inventory_history_missing')
             else 'calculation_failed' if error_code in ('calculation_timeout', 'capacity_exceeded')
             else 'input_rejected')
    return dict(schema=SCHEMA, auxiliary_availability_model='unavailable', calculation_state=phase, error_code=error_code,
        input_range=None, evaluation_range=None, roles={}, target_state='not_calculated',
        execution_state='not_observed')


def validate_diagnostics(value, *, symbols, summary=False):
    """报告的有界只读准入；旧报告没有本字段时由调用方保持原读取路径。"""
    def need(condition):
        if not condition:
            raise ValueError('策略业务诊断字段或范围无效')
    def count(number):
        need(type(number) is int and 0 <= number <= 32768)
    need(type(value) is dict)
    expected = {'schema', 'auxiliary_availability_model', 'calculation_state', 'error_code', 'target_state', 'execution_state', 'roles'}
    if not summary:
        expected |= {'input_range', 'evaluation_range'}
    need(set(value) == expected and value['schema'] == (SUMMARY_SCHEMA if summary else SCHEMA))
    need(value['calculation_state'] in CALCULATION_STATES and value['execution_state'] in EXECUTION_STATES)
    need(value['auxiliary_availability_model'] in ('actually-received', 'research-next-common-session-0925-v1', 'unavailable'))
    need(value['target_state'] in ('not_calculated', 'produced', 'unchanged'))
    need(value['error_code'] is None or type(value['error_code']) is str and len(value['error_code']) <= 64)
    need(type(value['roles']) is dict)
    if not summary and value['input_range'] is None and value['evaluation_range'] is None:
        need(value['calculation_state'] != 'completed' and value['roles'] == {}
             and value['target_state'] == 'not_calculated' and value['error_code'] is not None)
        return value
    need(set(value['roles']) == set(symbols))
    if not summary:
        for key in ('input_range', 'evaluation_range'):
            scope = value[key]
            need(type(scope) is dict and set(scope) == {'first_date', 'last_date', 'expected_dates'})
            count(scope['expected_dates']); need(scope['expected_dates'] <= 4096)
            for name in ('first_date', 'last_date'):
                need((scope[name] is None) == (scope['expected_dates'] == 0))
                if scope[name] is not None:
                    _day(scope[name])
            need(scope['expected_dates'] == 0 or scope['first_date'] <= scope['last_date'])
        a, b = value['input_range'], value['evaluation_range']
        need(b['expected_dates'] <= a['expected_dates'])
        if b['expected_dates']:
            need(a['first_date'] <= b['first_date'] <= b['last_date'] <= a['last_date'])
    common_roles = {symbol: role for role, symbol in ROLE_SYMBOLS.items() if role != 'kc_composite'}
    need(set(common_roles) <= set(symbols) and len(set(symbols)) == 8)
    expected_roles = dict(common_roles, **{next(iter(set(symbols)-set(common_roles))): 'kc_composite'})
    row_keys = {'role', 'latest_missing_fields', 'input_state', 'signal_counts', 'latest_action',
                'signal_state', 'last_successful_calculation_date', 'last_fully_informed_date'}
    for symbol, row in value['roles'].items():
        need(type(row) is dict and set(row) == (row_keys if summary else
             row_keys | {'field_coverage', 'auxiliary_fields', 'branches'}))
        need(row['role'] == expected_roles[symbol])
        auxiliary = tuple(dict.fromkeys(field for items in BRANCH_FIELDS[row['role']].values() for field in items))
        missing = row['latest_missing_fields']
        need(type(missing) is list and len(set(missing)) == len(missing) and set(missing) <= set(auxiliary))
        need(row['input_state'] in ('not_evaluated', 'input_missing', 'ready'))
        need(row['signal_state'] in ('not_evaluated', 'not_recorded', 'input_missing', 'signal_generated', 'conditions_not_met'))
        counts = row.get('signal_counts')
        if counts is None:
            need(row['signal_state'] == 'not_recorded' and row['latest_action'] is None)
        else:
            need(type(counts) is dict and set(counts) == {'BUY', 'SELL'} and row['signal_state'] != 'not_recorded')
            for number in counts.values():
                count(number)
        need(row.get('latest_action') in (None, 'BUY', 'SELL', 'HOLD'))
        for key in ('last_successful_calculation_date', 'last_fully_informed_date'):
            need(row.get(key) is None or _day(row[key]) == row[key])
        latest = row['last_successful_calculation_date']
        need(row['last_fully_informed_date'] is None or latest is not None and row['last_fully_informed_date'] <= latest)
        need((row['input_state'] == 'not_evaluated') == (latest is None))
        need(latest is None or row['input_state'] == ('input_missing' if missing else 'ready'))
        if summary:
            continue
        fields = row.get('field_coverage')
        need(type(fields) is dict and set(fields) == set(MARKET_FIELDS+auxiliary))
        need(row['auxiliary_fields'] == list(auxiliary))
        branches = row['branches']
        need(type(branches) is dict and set(branches) == set(BRANCH_FIELDS[row['role']]))
        for branch, required in BRANCH_FIELDS[row['role']].items():
            item = branches[branch]
            need(type(item) is dict and set(item) == {'required_fields', 'missing_fields', 'state'})
            need(item['required_fields'] == list(required))
            absent = [field for field in required if field in missing]
            need(item['missing_fields'] == absent)
            unavailable = bool(absent) and (branch != 'resonance_lamps' or len(absent) == len(required))
            need(item['state'] == ('not_evaluated' if latest is None else 'unavailable' if unavailable else
                                  'partially_observed' if absent else 'inputs_present'))
        for field in fields.values():
            need(type(field) is dict and set(field) == {'input', 'evaluation'})
            for scope, coverage in field.items():
                need(type(coverage) is dict and set(coverage) == {'expected_count', 'non_null_count',
                    'first_non_null_date', 'last_non_null_date', 'missing_reasons'})
                count(coverage['expected_count']); count(coverage['non_null_count'])
                need(coverage['non_null_count'] <= coverage['expected_count'])
                need(coverage['expected_count'] == value[scope+'_range']['expected_dates'])
                missing = coverage['missing_reasons']
                need(type(missing) is dict and set(missing) <= {'observation_missing', 'not_supplied_in_observation'})
                for number in missing.values():
                    count(number)
                need(sum(missing.values()) == coverage['expected_count']-coverage['non_null_count'])
                for key in ('first_non_null_date', 'last_non_null_date'):
                    need((coverage[key] is None) == (coverage['non_null_count'] == 0))
                    if coverage[key] is not None:
                        _day(coverage[key])
    # 拒绝非JSON/非有限值及超界诊断，不接受藏在附加字段里的任意业务正文。
    need(len(json.dumps(value, allow_nan=False, separators=(',', ':')).encode('utf-8')) <= 131072)
    return value
