# -*- coding: utf-8 -*-
"""QST-R14 公开交易能力描述符；只校验值与私有绑定身份，不授 SDK 写权限。

完整规则由 trading_contract 拥有。公共握手只带其规范摘要及资源限额，
避免把有限但较大的 symbol_rules 填入 4096 bytes 的组合 profile。
"""
import hashlib

from .protocol import ProtocolError, canonical, decode
from .trade_clock import CLOCK_SCHEMA
from .trading_contract import TradingKernelError, validate_trade_binding


TRADE_PROFILE_VERSION = 'qmt.trade-profile.v1'
SOURCE_STATUS_V1 = 'qmt.trade-source-status.v1'
SOURCE_STATUS_V2 = 'qmt.trade-source-status.v2'
_TRADE_OPERATIONS = ('order.cancel', 'order.insert')
_FIELDS = ('schema_version', 'binding_sha256', 'clock_schema', 'operations', 'limits')
_LIMIT_BOUNDS = (
    ('max_commands', 1, 4096),
    ('max_command_bytes', 1, 65536),
    ('max_command_ttl_ms', 100, 300000),
    ('max_call_result_bytes', 1024, 2097152),
    ('max_events', 1, 4096),
    ('max_event_bytes', 256, 1048576),
    ('max_total_event_bytes', 256, 16777216),
    ('max_event_page_bytes', 1280, 4190208),
)


def _reject():
    raise ProtocolError('trade capability differs from its explicit contract')


def _fields(value, names):
    if (type(value) is not dict or len(value) != len(names)
            or any(type(key) is not str for key in value) or set(value) != set(names)):
        _reject()


def validate_trade_profile(value):
    """返回无别名的普通 descriptor；联合控制预算留给完整 configuration。"""
    _fields(value, _FIELDS)
    if (type(value['schema_version']) is not str
            or value['schema_version'] != TRADE_PROFILE_VERSION
            or type(value['clock_schema']) is not str
            or value['clock_schema'] != CLOCK_SCHEMA):
        _reject()
    digest = value['binding_sha256']
    if (type(digest) is not str or len(digest) != 64
            or any(char not in '0123456789abcdef' for char in digest)):
        _reject()
    operations = value['operations']
    if (type(operations) is not list or len(operations) != len(_TRADE_OPERATIONS)
            or any(type(operation) is not str for operation in operations)
            or tuple(operations) != _TRADE_OPERATIONS):
        _reject()
    limits = value['limits']
    _fields(limits, tuple(item[0] for item in _LIMIT_BOUNDS))
    for name, minimum, maximum in _LIMIT_BOUNDS:
        number = limits[name]
        if type(number) is not int or not minimum <= number <= maximum:
            _reject()
    if (limits['max_total_event_bytes'] < limits['max_event_bytes']
            or limits['max_event_page_bytes'] < limits['max_event_bytes'] + 1024):
        _reject()
    # 所有节点已被限制为精确标量/有限容器；规范复制不运行外部对象转换协议。
    return decode(canonical(value))


def validate_trade_profile_binding(profile, binding):
    """核私有规则全文摘要和命令容量，返回公开 descriptor 的独立副本。

    摘要相等只证明配置一致；来源资格、真实写 gate 与原线程归执行 owner。
    """
    checked = validate_trade_profile(profile)
    try:
        private = validate_trade_binding(binding)
    except TradingKernelError:
        _reject()
    if (hashlib.sha256(canonical(private)).hexdigest() != checked['binding_sha256']
            or private['max_commands'] != checked['limits']['max_commands']):
        _reject()
    return checked
