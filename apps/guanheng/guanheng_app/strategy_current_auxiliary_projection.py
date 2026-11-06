"""只读投影纯核已经记录的当前消费；不求值信号或替换历史覆盖。"""
from copy import deepcopy
from datetime import date, datetime
import logging
import json


def project_current_auxiliary(result, symbols):
    """可选附加信息独立准入，错误只降级本投影。"""
    if result is None or result.get('current_auxiliary') is None:
        return None, 'absent', 'not_calculated' if result is None else 'not_recorded'
    try:
        from guanheng_strategy_v1 import CurrentAuxiliaryView
        from guanheng_strategy_v1.diagnostics import BRANCH_FIELDS
        from guanheng_strategy_v1.role_profile import ROLE_SYMBOLS

        def need(value):
            if not value:
                raise ValueError('invalid_current_auxiliary')

        def same(left, right):
            # JSON数值类型保持原字节语义，拒绝bool冒充0/1的Python相等比较。
            return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)

        value = result['current_auxiliary']
        base = {'schema', 'basis_date', 'derivation_version', 'values', 'sha256'}
        need(type(value) is dict and set(value) == base | {
            'decision_at', 'market_basis_date', 'data_revision', 'historical_rows_unchanged',
            'available_fields', 'consumed_fields', 'historical_effective_fields'})
        # 直接复用冻结V1原值/摘要/知晓时间准入；不调用派生、projected_values或信号机。
        view = CurrentAuxiliaryView.from_dict({key: value[key] for key in base})
        decision = datetime.fromisoformat(result['decision_cutoff'])
        need(datetime.fromisoformat(value['decision_at']) == decision
             and value['market_basis_date'] == value['basis_date']
             and value['data_revision'] == view.sha256 and value['historical_rows_unchanged'] is True
             and set(symbols) == set(ROLE_SYMBOLS.values()))
        view.qualify(date.fromisoformat(value['market_basis_date']), decision)
        available = {symbol: {} for symbol in symbols}
        for item in view.values:
            available[item.symbol][item.field] = item.to_dict()
        need(same(value['available_fields'], available))
        required = {symbol: list(dict.fromkeys(field for fields in BRANCH_FIELDS[role].values()
                                              for field in fields)) for role, symbol in ROLE_SYMBOLS.items()}
        for name in ('consumed_fields', 'historical_effective_fields'):
            mapping = value[name]
            need(type(mapping) is dict and set(mapping) == set(symbols))
            for symbol, fields in mapping.items():
                need(type(fields) is dict and set(fields) <= set(available[symbol]))
                need(all(same(item, available[symbol][field]) for field, item in fields.items()))
        for symbol in symbols:
            # 仅核发布结果中两类字段的归属/分区，与原角色声明一致；不重算生效日。
            expected = set(required[symbol]) & set(available[symbol]) - set(value['historical_effective_fields'][symbol])
            need(set(value['consumed_fields'][symbol]) == expected)
        return dict(
            schema='guanheng.current-auxiliary-consumption.v1',  # App公开当前消费投影版本。
            decision_at=value['decision_at'],  # 纯核真实决策截止，区别于页面读取时间。
            market_basis_date=value['market_basis_date'],  # 本次真实闭合行情基准日。
            data_revision=value['data_revision'],  # 原当前视图稳定数据摘要。
            derivation_version=value['derivation_version'],  # 原唯一派生身份，读取层不改公式。
            historical_rows_unchanged=True,  # 发布者声明的历史行保持事实，历史诊断仍独立。
            required_fields=required,  # 从V1原角色声明取得的必需辅助字段；无辅助依赖的角色为空。
            available_fields=deepcopy(available),  # 原可用派生值及其统计日、知晓时刻、依赖来源。
            consumed_fields=deepcopy(value['consumed_fields']),  # 纯核本次实际消费原值，不能以可用值补齐。
            historical_effective_fields=deepcopy(value['historical_effective_fields']),  # 已在历史生效的原字段分区。
        ), 'available', None
    except Exception as error:
        try:
            logging.getLogger(__name__).warning('strategy_current_auxiliary_unavailable error_type=%s', type(error).__name__)
        except Exception:
            pass  # 附加日志错误不改变核心读取。
        return None, 'unavailable', 'invalid_current_auxiliary'
