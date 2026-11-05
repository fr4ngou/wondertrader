"""同账正常换代的零持仓角色替换；原金融文件和历史事实均保持原件。"""
from __future__ import annotations

import copy
import hashlib
import time
from pathlib import Path

from .managed_local_process import _json, _path, _read, _require, _sha

OLD_SYMBOL = '589680.SH'  # 本次退役科创角色证券，仅允许实际持仓为零时替换。
NEW_SYMBOL = '588030.SH'  # 新科创角色证券；价格、周期和前复权历史全部使用自身事实。
OLD_CODE = 'SSE.ETF.589680'  # WT原目标证券身份，保留在原账中并沿原过滤器停止执行。
NEW_CODE = 'SSE.ETF.588030'  # WT新执行身份，与新基金原合约一致。


def parameters(native):
    """本模块仅处理既有单策略；多策略分账仍由原配置负责。"""
    rows = native['strategies']
    _require(type(rows) is list and len(rows) == 1 and rows[0]['id'] == 'resonance-regime-v1')
    return rows[0]['parameters']['python_strategy']


def input_value(native, *, deadline=float('inf')):
    """核输入原件SHA；不重写数据、不将旧基金行情改名。"""
    selected = parameters(native)
    raw = _read(_path(selected['input_file']), 16 * 1024 * 1024, deadline=deadline, clock=time.monotonic)
    _require(hashlib.sha256(raw).hexdigest() == _sha(selected['input_sha256']))
    return _json(raw)


def validate_inputs(old, new):
    """原资金基准、现金锚点、七证券周期和风险规则逐项不变。"""
    _require(set(old) == set(new))
    for key in set(old) - {'request', 'market_manifest_source'}:
        _require(old[key] == new[key])
    before, after = old['request'], new['request']
    _require(set(before) == set(after))
    left, right = copy.deepcopy(before['configuration']), copy.deepcopy(after['configuration'])
    _require(left['config_revision'] != right['config_revision'])
    for key in ('kc_composite_signal_symbol', 'kc_composite_execution_symbol'):
        _require(left[key] == OLD_SYMBOL and right[key] == NEW_SYMBOL)
        right[key] = left[key]
    right['config_revision'] = left['config_revision']
    _require(left == right)
    old_cycles = {row['symbol']: row for row in before['cycles']}
    new_cycles = {row['symbol']: row for row in after['cycles']}
    _require(len(old_cycles) == len(new_cycles) == 8
             and set(new_cycles) == (set(old_cycles) - {OLD_SYMBOL}) | {NEW_SYMBOL})
    for symbol in set(old_cycles) - {OLD_SYMBOL}:
        _require(old_cycles[symbol] == new_cycles[symbol])
    for row in (old_cycles[OLD_SYMBOL], new_cycles[NEW_SYMBOL]):
        _require(row['status'] == 'flat' and type(row['quantity']) is int and row['quantity'] == 0)
    _require(before['previous_exits'] == after['previous_exits'])
    # 新history/analysis/current_view由1.2.2正式输入校验器核证券和复权；这里保留原金融事实。
    for key in set(before) - {'configuration', 'cycles', 'history', 'analysis', 'current_view',
                              'decision_cutoff', 'cycles_captured_at', 'cycles_valid_until'}:
        _require(before[key] == after[key])


def role_origin_configuration(native, *, deadline=float('inf')):
    """唯一显式换代接缝；比较投影返回已钉住的前代，运行仍消费完整新配置。"""
    marker = native.get('role_replacement')
    if marker is None:
        return native
    _require(type(marker) is dict and set(marker) == {'schema', 'file', 'sha256'}
             and marker['schema'] == 'guanheng.zero-position-role-replacement.v1')
    path = _path(marker['file'])
    _require(path.name == 'execution.json')
    raw = _read(path, 256 * 1024, deadline=deadline, clock=time.monotonic)
    _require(hashlib.sha256(raw).hexdigest() == _sha(marker['sha256']))
    origin = _json(raw)
    _require('role_replacement' not in origin)
    validate_inputs(input_value(origin, deadline=deadline), input_value(native, deadline=deadline))
    before, after = copy.deepcopy(origin), copy.deepcopy(native)
    for value in (before, after):
        value.pop('recovery', None)
    after.pop('role_replacement')
    old_parameters, new_parameters = parameters(before), parameters(after)
    for key in ('input_file', 'input_sha256'):
        new_parameters[key] = old_parameters[key]
    # 只替换读取源定位；最大年龄、复权方式、预算和其他规则继续精确比较。
    for key in ('capital_market',):
        if key in new_parameters:
            for field in ('base_url', 'token_env'):
                new_parameters[key][field] = old_parameters[key][field]
    if 'market_window' in new_parameters:
        new_parameters['market_window']['path'] = old_parameters['market_window']['path']
    old_store, new_store = before['data']['store'], after['data']['store']
    expected = [dict(row, symbol=NEW_SYMBOL, std_code=NEW_CODE) if row['symbol'] == OLD_SYMBOL
                else row for row in old_store['symbols']]
    _require(sorted(new_store['symbols'], key=lambda row: row['symbol'])
             == sorted(expected, key=lambda row: row['symbol']))
    new_store['symbols'] = copy.deepcopy(old_store['symbols'])
    for key in ('path', 'adjfactor', 'publication'):
        _require((key in new_store['daily']) == (key in old_store['daily']))
        if key in new_store['daily']:
            new_store['daily'][key] = copy.deepcopy(old_store['daily'][key])
    for key in ('base_url', 'binding_id', 'binding_sha256', 'instance_id', 'key_id_env', 'hmac_secret_env'):
        _require((key in before['trader']) == (key in after['trader']))
        if key in after['trader']:
            after['trader'][key] = before['trader'][key]
    # 原WT证券ignore在初始化恢复理论目标时生效；只影响退役证券，原账不做假卖平。
    _require(before['environment']['filters'] == '')
    relative = Path(after['environment']['filters'])
    _require(bool(after['environment']['filters']) and not relative.is_absolute() and '..' not in relative.parts)
    filter_path = Path(native['installation_root']) / relative
    filters = _json(_read(filter_path, 4096, deadline=deadline, clock=time.monotonic))
    _require(filters == {'code_filters': {OLD_CODE: {'action': 'ignore'}}})
    after['environment']['filters'] = ''
    from .execution_recovery import _same_business
    _require(_same_business(before, after))
    return origin


def is_role_handoff(current, previous):
    """原恢复前代仍使用旧角色时才重算NSQ；后续同版正常重启沿既有路径。"""
    if 'role_replacement' not in current:
        return False
    rows = previous['data']['store']['symbols']
    return any(row['symbol'] == OLD_SYMBOL for row in rows)
