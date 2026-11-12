# -*- coding: utf-8 -*-
"""QST-R9/R10 的纯数据准入；Agent 与 Host 共用同一字段和阶段契约。

本模块没有 SDK、时钟、权限或 Journal 所有权。校验成功只证明字段与
原命令一致，不证明柜台受理；Host 自有中断原因放在 Journal 外层元数据。
"""
import hashlib
import math
import re
from uuid import UUID

from .protocol import canonical


_MAX_INTEGER = 2 ** 53 - 1
LEGACY_BINDING_SCHEMA = 'qmt.trade-binding.v1'  # 冻结证券规则，供旧部署和历史核查。
TRADE_BINDING_SCHEMA = 'qmt.trade-binding.v2'  # 证券规则由 WT 与券商处理。
_BINDING_KEYS = frozenset(('schema_version', 'binding_id', 'account_id',
    'account_type', 'account_environment', 'strategy_name', 'max_commands'))
_RULE_KEYS = frozenset(('price_tick', 'buy_min', 'buy_step', 'sell_min', 'sell_step'))
_COMMON_KEYS = frozenset(('schema_version', 'command_id', 'operation',
    'binding_id', 'account_id', 'account_type', 'entrust_id', 'user_tag'))
_INSERT_KEYS = _COMMON_KEYS | frozenset(('symbol', 'side', 'order_type',
    'limit_price', 'quantity', 'sdk_user_order_id'))
_CANCEL_KEYS = _COMMON_KEYS | frozenset(('original_command_id', 'broker_order_id'))
_SYMBOL = re.compile(r'[0-9]{6}\.(SH|SZ)\Z')
_DECIMAL = re.compile(r'[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z')


def terminal_insert_observed(command, rows):
    """核原insert的唯一完整ORDER终态；仅通信责任证明，不计算持仓或改SDK结果。

    调用方先验证账户完整查询与来源。缺字段、重复token和任何冲突保持未知，
    原限价按实际传入SDK的double比较；布尔值不作为数量或价格。
    """
    if command.get('operation') != 'order.insert' or type(rows) is not list:
        return False
    matched = [row for row in rows if type(row) is dict
               and row.get('m_strRemark') == command['sdk_user_order_id']]
    if len(matched) != 1:
        return False
    row = matched[0]
    symbol, exchange = command['symbol'].split('.')
    broker = row.get('m_strOrderSysID')
    if (row.get('m_strAccountID') != command['account_id']
            or row.get('m_strInstrumentID') != symbol or row.get('m_strExchangeID') != exchange
            or type(broker) is not str or not 1 <= len(broker) <= 63
            or any(not 33 <= ord(c) < 127 for c in broker)):
        return False
    for key in ('m_nOffsetFlag', 'm_nVolumeTotalOriginal', 'm_nVolumeTraded',
                'm_nVolumeTotal', 'm_nOrderStatus'):
        if type(row.get(key)) is not int:
            return False
    qty, filled, left = (row['m_nVolumeTotalOriginal'], row['m_nVolumeTraded'], row['m_nVolumeTotal'])
    state, price = row['m_nOrderStatus'], row.get('m_dLimitPrice')
    if (row['m_nOffsetFlag'] != (48 if command['side'] == 'buy' else 49)
            or qty != command['quantity'] or not 0 <= filled <= qty or not 0 <= left <= qty
            or filled + left > qty or state not in (53, 54, 56, 57)
            or state == 56 and (filled != qty or left != 0)
            or state == 57 and filled != 0
            or type(price) not in (int, float)):
        return False
    try:
        return math.isfinite(price) and price > 0 and price == float(command['limit_price'])
    except (OverflowError, ValueError):
        return False


class TradingKernelError(ValueError):
    """只携带固定安全码；账户、SDK 异常值及命令原文不进入异常消息。"""


def _fail(code):
    raise TradingKernelError(code) from None


def _shape(value, keys, code):
    if (type(value) is not dict or len(value) != len(keys)
            or any(type(key) is not str for key in value) or set(value) != keys):
        _fail(code)


def _text(value, limit, code, ascii_only=False):
    if (type(value) is not str or not 1 <= len(value) <= limit
            or not value.strip()):
        _fail(code)
    if any(ord(ch) < 32 or 127 <= ord(ch) <= 159 for ch in value):
        _fail(code)
    try:
        size = len(value.encode('ascii' if ascii_only else 'utf-8'))
    except UnicodeError:
        _fail(code)
    if size > limit:
        _fail(code)
    return value


def _integer(value, low, high, code):
    if type(value) is not int or not low <= value <= high:
        _fail(code)
    return value


def _uuid(value):
    if type(value) is not str or len(value) != 36:
        _fail('invalid_command')
    try:
        valid = str(UUID(value)) == value
    except (ValueError, AttributeError):
        valid = False
    if not valid:
        _fail('invalid_command')
    return value


def _fraction(value, code):
    # 用整数分子/分母校验价位，避免借用调用者 Decimal 精度、舍入和陷阱。
    # 长度与指数先受限，防止不可信十进制生成无界大整数。
    if type(value) is not str or not 1 <= len(value) <= 64 or not _DECIMAL.fullmatch(value):
        _fail(code)
    parts = value.lower().split('e')
    exponent = int(parts[1]) if len(parts) == 2 else 0
    if abs(exponent) > 308:
        _fail(code)
    whole, dot, fraction = parts[0].partition('.')
    numerator = int(whole + fraction)
    if numerator <= 0:
        _fail(code)
    scale = len(fraction) - exponent
    return (numerator * 10 ** max(-scale, 0), 10 ** max(scale, 0))


def validate_trade_binding(value):
    """校验并深拷贝绑定；只保留普通 dict/精确标量，不保留外部配置别名。"""
    schema = value.get('schema_version') if type(value) is dict else None
    if type(schema) is not str or schema not in (LEGACY_BINDING_SCHEMA, TRADE_BINDING_SCHEMA):
        _fail('invalid_binding')
    legacy = schema == LEGACY_BINDING_SCHEMA
    _shape(value, _BINDING_KEYS | {'symbol_rules'} if legacy else _BINDING_KEYS, 'invalid_binding')
    if (any(type(value[name]) is not str for name in
            ('schema_version', 'account_type', 'account_environment'))
            or value['account_type'] != 'stock'
            or value['account_environment'] != 'live'):
        _fail('invalid_binding')
    result = dict(value)
    _text(result['binding_id'], 128, 'invalid_binding', True)
    _text(result['account_id'], 63, 'invalid_binding')
    _text(result['strategy_name'], 128, 'invalid_binding')
    _integer(result['max_commands'], 1, 4096, 'invalid_binding')
    if not legacy:
        return result
    rules = result['symbol_rules']
    if type(rules) is not dict or not 1 <= len(rules) <= 4096:
        _fail('invalid_binding')
    copied = {}
    for symbol, rule in rules.items():
        if type(symbol) is not str or not _SYMBOL.fullmatch(symbol):
            _fail('invalid_binding')
        _shape(rule, _RULE_KEYS, 'invalid_binding')
        _fraction(rule['price_tick'], 'invalid_binding')
        for name in ('buy_min', 'buy_step', 'sell_min', 'sell_step'):
            _integer(rule[name], 1, _MAX_INTEGER, 'invalid_binding')
        copied[symbol] = dict(rule)
    # 允许值都是精确标量；重建两层映射即完整深拷贝，避免任意 __deepcopy__。
    result['symbol_rules'] = copied
    return result


def validate_trade_command(value):
    """校验并复制原命令；不改字段值，也不代替 owner 的账户/绑定相等检查。"""
    if type(value) is not dict or len(value) not in (len(_INSERT_KEYS), len(_CANCEL_KEYS)):
        _fail('invalid_command')
    value = dict(value)
    if any(type(item) not in (str, int) for item in value.values()):
        _fail('invalid_command')
    operation = value.get('operation')
    if type(operation) is not str or operation not in ('order.insert', 'order.cancel'):
        _fail('invalid_command')
    _shape(value, _INSERT_KEYS if operation == 'order.insert' else _CANCEL_KEYS,
           'invalid_command')
    if (value['schema_version'] != 'qmt.trade-command.v1'
            or value['account_type'] != 'stock'):
        _fail('invalid_command')
    _uuid(value['command_id'])
    _text(value['binding_id'], 128, 'invalid_command', True)
    _text(value['account_id'], 63, 'invalid_command')
    # 固定 WTSTradeDef.hpp:131–132 的两个 char[64]，保留结尾 NUL 空间。
    for name in ('entrust_id', 'user_tag'):
        _text(value[name], 63, 'invalid_command')
    if operation == 'order.insert':
        if (type(value['symbol']) is not str or not _SYMBOL.fullmatch(value['symbol'])
                or type(value['side']) is not str or value['side'] not in ('buy', 'sell')
                or value['order_type'] != 'limit'):
            _fail('invalid_command')
        _fraction(value['limit_price'], 'invalid_command')
        _integer(value['quantity'], 1, _MAX_INTEGER, 'invalid_command')
        token = _text(value['sdk_user_order_id'], 64, 'invalid_command', True)
        if any(ord(ch) < 33 for ch in token):
            _fail('invalid_command')
    else:
        _uuid(value['original_command_id'])
        _text(value['broker_order_id'], 128, 'invalid_command', True)
    return value


def _result(command, digest, stage, entered, code=None, signal=None):
    return {'schema_version': 'qmt.trade-call-result.v1',
            'command_id': command['command_id'], 'command_sha256': digest,
            'operation': command['operation'], 'stage': stage,
            'sdk_entered': entered, 'signal_sent': signal, 'error_code': code}


_RESULT_KEYS = frozenset(('schema_version', 'command_id', 'command_sha256',
    'operation', 'stage', 'sdk_entered', 'signal_sent', 'error_code'))
_PRE_CALL_CODES = frozenset(('not_admitted', 'capacity_exhausted', 'binding_mismatch',
    'writes_disabled', 'admission_closed', 'symbol_not_allowed', 'quantity_off_grid',
    'price_off_grid', 'price_not_representable', 'deadline_expired', 'clock_failed'))
_INSERT_ONLY_CODES = frozenset(('symbol_not_allowed', 'quantity_off_grid',
                               'price_off_grid', 'price_not_representable'))
_POST_CALL_CODES = frozenset(('sdk_exception', 'invalid_sdk_return',
                            'deadline_expired_after_call'))


def command_digest(command):
    """对通过准入的原字段取规范 SHA-256；字符串表示不作数值归一化。"""
    frozen = validate_trade_command(command)
    return hashlib.sha256(canonical(frozen)).hexdigest()


def validate_call_result(result, command):
    """核 Agent 调用事实并返回副本；第二参数必须是完整原命令 dict。

    stage/entered/signal/error 必须构成该 SDK 操作能够产生的组合；原 ID、
    operation 和 canonical 摘要必须全部相等。这里不接收 Host 自造的
    owner_restarted/interrupted，也不把 sdk_returned 升级为柜台受理。
    """
    frozen = validate_trade_command(command)
    _shape(result, _RESULT_KEYS, 'invalid_call_result')
    result = dict(result)
    for name in ('schema_version', 'command_id', 'command_sha256', 'operation', 'stage'):
        if type(result[name]) is not str or not 1 <= len(result[name]) <= 64:
            _fail('invalid_call_result')
    if (result['schema_version'] != 'qmt.trade-call-result.v1'
            or result['operation'] not in ('order.insert', 'order.cancel')
            or result['stage'] not in ('definitely_not_called', 'sdk_returned', 'unknown')
            or type(result['sdk_entered']) is not bool
            or (result['signal_sent'] is not None and type(result['signal_sent']) is not bool)
            or (result['error_code'] is not None and
                (type(result['error_code']) is not str or not 1 <= len(result['error_code']) <= 64))):
        _fail('invalid_call_result')
    if (result['command_id'] != frozen['command_id']
            or result['operation'] != frozen['operation']
            or result['command_sha256'] != command_digest(frozen)):
        _fail('result_command_mismatch')
    stage, entered = result['stage'], result['sdk_entered']
    signal, code = result['signal_sent'], result['error_code']
    insert = frozen['operation'] == 'order.insert'
    if insert and signal is not None:
        _fail('invalid_call_result')
    if stage == 'definitely_not_called':
        if (entered or signal is not None or code not in _PRE_CALL_CODES
                or (not insert and code in _INSERT_ONLY_CODES)):
            _fail('invalid_call_result')
    elif stage == 'sdk_returned':
        if not entered or code is not None or (not insert and type(signal) is not bool):
            _fail('invalid_call_result')
    else:
        if not entered or code not in _POST_CALL_CODES:
            _fail('invalid_call_result')
        # cancel 只有精确 bool 后才检查 D；异常可能发生于 SDK 或后置时钟。
        if ((code == 'invalid_sdk_return' and signal is not None)
                or (not insert and code == 'deadline_expired_after_call' and type(signal) is not bool)):
            _fail('invalid_call_result')
    return result
