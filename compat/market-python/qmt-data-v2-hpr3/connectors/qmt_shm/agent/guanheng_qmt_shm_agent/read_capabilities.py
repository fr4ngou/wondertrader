# -*- coding: utf-8 -*-
"""Host/Agent共用的封闭读能力准入；不执行SDK或持久化。

返回值是无调用者别名的普通dict。v2/v3/v4必须提供当前result额度上下文，
不能用对象标记/缓存跳过联合准入；未来操作只能由同版代码显式登记。
"""
import math
from datetime import datetime, timedelta, timezone
from uuid import UUID
from .protocol import ProtocolError, canonical, decode
from .account_query import POLICY_VERSION, IDENTITY_POLICY_VERSION, IDENTITY_SCHEMA

FULL_TICK = 'market.full_tick'
HISTORY = 'market.history_1m'
ACCOUNT = 'account.trade_detail'
PROFILE_VERSION = 'qmt.read-profile.v2'
ACCOUNT_PROFILE_VERSION = 'qmt.read-profile.v3'
TRADE_READ_PROFILE_VERSION = 'qmt.read-profile.v4'
BULK_READ_PROFILE_VERSION = 'qmt.read-profile.v5'
PREPARATION = 'market.history_prepare'
PREPARATION_PROFILE_VERSION = 'qmt.read-profile.v6'
_OPERATIONS = (FULL_TICK, HISTORY, ACCOUNT, PREPARATION)
_POLICIES = ('qmt.standard-read.v1', 'qmt.history-read.v1', 'qmt.account-read.v1', 'qmt.history-preparation.v1')
_CONTROL_FIELDS = ('schema_version', 'max_pending_calls', 'max_call_bytes', 'max_reply_bytes',
    'max_retained_bytes', 'max_cycle_messages', 'max_cycle_bytes', 'poll_seconds', 'max_call_seconds')


def known_operation(operation):
    return type(operation) is str and operation in _OPERATIONS


def _reject():
    raise ProtocolError('read capability or request exceeds its explicit contract')


def _fields(value, fields):
    if (type(value) is not dict or len(value) != len(fields)
            or any(type(key) is not str for key in value) or set(value) != set(fields)):
        _reject()


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        _reject()


def _control(value, version):
    # 信用和时限关系仍由原ControlProfile验证，此处限制复制前的形状和标量。
    _fields(value, _CONTROL_FIELDS)
    if type(value['schema_version']) is not str or value['schema_version'] != version:
        _reject()
    for key in _CONTROL_FIELDS[1:7]:
        _integer(value[key], 1, 2**53-1)
    for key in ('poll_seconds', 'max_call_seconds'):
        item = value[key]
        if type(item) not in (int, float) or not 0 < item <= 600 or not math.isfinite(item):
            _reject()


def _history_limits(limits, max_result_bytes):
    _integer(max_result_bytes, 8192, 2097152)
    _fields(limits, ('schema_version', 'max_calendar_days', 'max_rows', 'max_data_bytes'))
    if type(limits['schema_version']) is not str or limits['schema_version'] != 'qmt.history-1m.v1':
        _reject()
    _integer(limits['max_calendar_days'], 1, 5)
    _integer(limits['max_rows'], 1, 2000)
    _integer(limits['max_data_bytes'], 1024, max_result_bytes-4096)
    return decode(canonical(limits))


def shanghai_date():
    """本能力日期域自2021起，使用现代上海UTC+8；公开request没有now入口。"""
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).date()


def explicit_profile_version(read_operations):
    """由封闭能力集选择版本；旧full_tick三字段profile保持原bytes。

    新账户能力可与行情共用认证连接，只有显式包含账户才采用v3。
    Host、Agent及配对工具使用此纯函数，不构造假SDK实例选择版本。
    """
    if (type(read_operations) is not list or not 1 <= len(read_operations) <= len(_OPERATIONS)
            or any(not known_operation(op) for op in read_operations)
            or read_operations != sorted(set(read_operations))):
        _reject()
    if PREPARATION in read_operations:
        if len(read_operations) < 2:
            _reject()
        return PREPARATION_PROFILE_VERSION
    if ACCOUNT in read_operations:
        return ACCOUNT_PROFILE_VERSION
    return None if read_operations == [FULL_TICK] else PROFILE_VERSION


def _operation_profiles(profile, operations, max_result_bytes):
    # 各版本共用读 descriptor 和结果额度，不能降级 profile 绕过版本准入。
    _integer(max_result_bytes, 8192, 2097152)
    entries = profile['operation_profiles']
    _fields(entries, operations)
    maximum = 0
    for op in operations:
        descriptor = entries[op]
        _fields(descriptor, ('policy_id', 'policy_version', 'execution_timeout_ms', 'limits'))
        versions = ((POLICY_VERSION, IDENTITY_POLICY_VERSION)
            if op == ACCOUNT and profile.get('read_profile_version') == TRADE_READ_PROFILE_VERSION
            else (POLICY_VERSION,))
        if (type(descriptor['policy_id']) is not str or descriptor['policy_id'] != _POLICIES[_OPERATIONS.index(op)]
                or type(descriptor['policy_version']) is not str or descriptor['policy_version'] not in versions):
            _reject()
        _integer(descriptor['execution_timeout_ms'], 100, 30000)
        maximum = max(maximum, descriptor['execution_timeout_ms'])
        limits = descriptor['limits']
        if op == FULL_TICK:
            _fields(limits, ())
        elif op == HISTORY:
            _history_limits(limits, max_result_bytes)
        elif op == PREPARATION:
            from .history_preparation import limits as preparation_limits
            preparation_limits(limits)
            if descriptor['execution_timeout_ms'] > limits['total_timeout_ms']:
                _reject()
        else:
            from .account_query import validate_account_limits
            from .errors import GatewayError
            try:
                validate_account_limits(limits, max_result_bytes)
            except GatewayError:
                _reject()
    if maximum != profile['execution_timeout_ms']:
        _reject()


def validate_read_profile(profile, *, max_result_bytes=None):
    if type(profile) is dict and profile.get('read_profile_version') == BULK_READ_PROFILE_VERSION:
        from .bulk_capabilities import validate_bulk_read_profile
        return validate_bulk_read_profile(profile, max_result_bytes=max_result_bytes)
    if type(profile) is not dict or len(profile) not in (3, 5, 6):
        _reject()
    operations = profile.get('read_operations')
    read_version = explicit_profile_version(operations)
    version = profile.get('read_profile_version')
    trade = type(version) is str and version == TRADE_READ_PROFILE_VERSION
    _integer(profile.get('execution_timeout_ms'), 100, 30000)
    _control(profile.get('control_profile'), '2.0' if trade else '1.0')
    if trade:
        _fields(profile, ('read_profile_version', 'read_operations', 'execution_timeout_ms',
                          'control_profile', 'operation_profiles', 'trade_profile'))
        if ACCOUNT not in operations or PREPARATION in operations:
            _reject()
        from .trade_capabilities import validate_trade_profile
        validate_trade_profile(profile['trade_profile'])
        _operation_profiles(profile, operations, max_result_bytes)
    elif operations == [FULL_TICK]:
        _fields(profile, ('read_operations', 'execution_timeout_ms', 'control_profile'))
    else:
        _fields(profile, ('read_profile_version', 'read_operations', 'execution_timeout_ms',
                          'control_profile', 'operation_profiles'))
        if type(version) is not str or version != read_version:
            _reject()
        _operation_profiles(profile, operations, max_result_bytes)
    raw = canonical(profile)
    if len(raw) > 4096:
        _reject()
    return decode(raw)


def build_read_profile(read_operations, execution_timeout_ms, control_profile, operation_profiles=None, *, max_result_bytes=None):
    version = explicit_profile_version(read_operations)
    value = {'read_operations': read_operations, 'execution_timeout_ms': execution_timeout_ms,
             'control_profile': control_profile}
    if read_operations != [FULL_TICK]:
        value.update(read_profile_version=version, operation_profiles=operation_profiles)
    elif operation_profiles is not None:
        _reject()
    return validate_read_profile(value, max_result_bytes=max_result_bytes)


def build_trade_read_profile(read_operations, execution_timeout_ms, control_profile,
                             operation_profiles, trade_profile, *, max_result_bytes):
    """显式构造组合 v4；只描述能力，真实写许可由独立 owner 默认关闭。"""
    value = {'read_profile_version': TRADE_READ_PROFILE_VERSION,
             'read_operations': read_operations, 'execution_timeout_ms': execution_timeout_ms,
             'control_profile': control_profile, 'operation_profiles': operation_profiles,
             'trade_profile': trade_profile}
    return validate_read_profile(value, max_result_bytes=max_result_bytes)


def operation_descriptor(profile, operation, *, max_result_bytes=None):
    value = validate_read_profile(profile, max_result_bytes=max_result_bytes)
    if not known_operation(operation) or operation not in value['read_operations']:
        _reject()
    if value['read_operations'] == [FULL_TICK]:
        return {'policy_id': _POLICIES[0], 'policy_version': '1.0',
                'execution_timeout_ms': value['execution_timeout_ms'], 'limits': {}}
    return value['operation_profiles'][operation]


def validate_read_result_projection(request, result):
    """核原请求选择的账户结果版本；不改原文、不解释金融字段。"""
    if request['operation_id'] == PREPARATION:
        from .history_preparation import validate_result
        validate_result(request, result)
        return
    if request['operation_id'] != ACCOUNT or result.get('ok') is not True:
        return
    version = request['policy_version']
    if type(version) is not str or version not in (POLICY_VERSION, IDENTITY_POLICY_VERSION):
        _reject()
    data = result.get('data')
    if version == POLICY_VERSION:
        # 旧Host只保存有界原文，完整旧data语义仍归原Core；只阻止新投影降级。
        if type(data) is dict and data.get('schema_version') == IDENTITY_SCHEMA:
            _reject()
        return
    if type(data) is not dict or data.get('schema_version') != IDENTITY_SCHEMA:
        _reject()


def validate_read_request(request, profile, *, as_of_date=None, max_result_bytes=None):
    """原八字段准入；v1请求scope可投影两字段，认证profile仍须完整。

    v2/v3要求完整五字段，v4要求完整六字段，均使用实际result额度。
    原body不被转换或写回，组合profile按实际control2校验。
    """
    _fields(request, ('request_id', 'correlation_id', 'operation_id', 'arguments', 'timeout_ms',
                      'policy_id', 'policy_version', 'priority_class'))
    for key in ('request_id', 'correlation_id'):
        value = request[key]
        if type(value) is not str or len(value) != 36:
            _reject()
        try:
            if str(UUID(value)) != value:
                _reject()
        except (ValueError, TypeError, AttributeError):
            _reject()
    if not known_operation(request['operation_id']):
        _reject()
    # v1公开request准入原本接两字段scope投影；认证profile仍单独要求完整三字段。
    if type(profile) is dict and len(profile) == 2:
        _fields(profile, ('read_operations', 'execution_timeout_ms'))
        if profile['read_operations'] != [FULL_TICK] or type(profile['read_operations']) is not list or request['operation_id'] != FULL_TICK:
            _reject()
        _integer(profile['execution_timeout_ms'], 100, 30000)
        descriptor = {'policy_id': _POLICIES[0], 'policy_version': '1.0',
                      'execution_timeout_ms': profile['execution_timeout_ms'], 'limits': {}}
    else:
        descriptor = operation_descriptor(profile, request['operation_id'], max_result_bytes=max_result_bytes)
    if (type(request['policy_id']) is not str or request['policy_id'] != descriptor['policy_id']
            or type(request['policy_version']) is not str or request['policy_version'] != descriptor['policy_version']
            or type(request['priority_class']) is not str or request['priority_class'] != 'normal'
            or type(request['arguments']) is not dict):
        _reject()
    _integer(request['timeout_ms'], 100, descriptor['execution_timeout_ms'])
    if request['operation_id'] == HISTORY:
        from .history_1m import arguments, HistoryError
        limits = descriptor['limits']
        try:
            arguments(request['arguments'], shanghai_date() if as_of_date is None else as_of_date,
                      limits['max_calendar_days'], limits['max_rows'])
        except HistoryError:
            _reject()
    elif request['operation_id'] == ACCOUNT:
        from .account_query import validate_account_arguments
        from .errors import GatewayError
        try:
            validate_account_arguments(request['arguments'])
        except GatewayError:
            _reject()
    elif request['operation_id'] == PREPARATION:
        from .history_preparation import arguments
        arguments(request['arguments'], descriptor['limits'])
