# -*- coding: utf-8 -*-
"""QST-R15 显式组合配置；只冻结值与联合容量，不启动交易或授 ready。"""
from .protocol import canonical, decode
from .read_configuration import ReadConfiguration, _REQUIRED, _READ_EXTRA, _admit_configuration
from .read_capabilities import ACCOUNT, TRADE_READ_PROFILE_VERSION, build_trade_read_profile
from .trade_capabilities import validate_trade_profile_binding
from .trading_contract import validate_trade_binding


_TRADE_FIELDS = _REQUIRED | _READ_EXTRA | frozenset((
    'trade_profile', 'trade_binding', 'writes_enabled'))


class TradeConfiguration(ReadConfiguration):
    """公开配置与私有部署事实分离；私有规则属性每次返回无别名副本。"""
    def __init__(self, value, route, budget, control_profile, profile, secret,
                 trade_binding, writes_enabled):
        ReadConfiguration.__init__(self, value, route, budget, control_profile, profile, secret)
        self._trade_binding_bytes = canonical(trade_binding)
        self._writes_enabled = writes_enabled

    @property
    def trade_binding(self):
        return decode(self._trade_binding_bytes)

    @property
    def writes_enabled(self):
        # 精确 bool 只表示部署请求；运行 owner 仍核权限、来源、gap 和停止门。
        return self._writes_enabled


def _build_profile(value, control):
    return build_trade_read_profile(value['allowed_operations'], value['execution_timeout_ms'],
        control, value['operation_profiles'], value['trade_profile'],
        max_result_bytes=value['max_result_bytes'])


def _require_trade_profile(profile, control, binding):
    account = profile['operation_profiles'][ACCOUNT]['limits']['account_binding']
    if any(account[key] != binding[key] for key in ('account_id', 'account_environment')):
        raise ValueError('read and trade account binding differs')
    limits = profile['trade_profile']['limits']
    overhead = control.contract.CONSTANTS['message_overhead_bytes']
    # base64按完整三字节组预留；向下近似native_body_limit不能证明末组可放下。
    if 4 * ((limits['max_command_bytes'] + 2) // 3) + overhead > control.max_call_bytes:
        raise ValueError('control CALL cannot contain the complete trade command')
    control.require_native_budgets(limits['max_call_result_bytes'], limits['max_event_page_bytes'])
    if limits['max_command_ttl_ms'] / 1000 + control.io_seconds > control.max_call_seconds:
        raise ValueError('control lifetime cannot contain the original trade deadline')
    # 连续退休gap仍占窗口；四Host槽只支持一次page后业务ACK，不能无限轮询。
    if control.max_pending_calls < 4:
        raise ValueError('control window cannot progress trade event acknowledgement')
    control.require_directions(7)
    if control.call_slots('host') < 4 or control.call_slots('agent') < 1:
        raise ValueError('control role credits cannot progress trade event acknowledgement')


def validate_trade_configuration(trusted_bootstrap):
    """显式准入 v4/control2；旧入口保持拒绝，成功不证明 SDK 可用或获准写。"""
    if (type(trusted_bootstrap) is not dict or len(trusted_bootstrap) != len(_TRADE_FIELDS)
            or any(type(key) is not str for key in trusted_bootstrap)
            or set(trusted_bootstrap) != _TRADE_FIELDS):
        raise ValueError('trade bootstrap has missing or unsupported fields')
    if (type(trusted_bootstrap['read_profile_version']) is not str
            or trusted_bootstrap['read_profile_version'] != TRADE_READ_PROFILE_VERSION):
        raise ValueError('explicit combined trade profile version required')
    secret, requested = trusted_bootstrap['secret'], trusted_bootstrap['writes_enabled']
    if type(secret) is not bytes or len(secret) < 32:
        raise ValueError('missing trusted bootstrap secret')
    if type(requested) is not bool:
        raise ValueError('explicit boolean write request required')
    # 先用规则唯一owner限制私有树，再复制公开值；不对任意私有对象先做JSON展开。
    private = validate_trade_binding(trusted_bootstrap['trade_binding'])
    descriptor = validate_trade_profile_binding(trusted_bootstrap['trade_profile'], private)
    public = {key: item for key, item in trusted_bootstrap.items()
              if key not in ('secret', 'trade_binding', 'writes_enabled')}
    public['trade_profile'] = descriptor
    value = decode(canonical(public))

    def require_profile(profile, control):
        _require_trade_profile(profile, control, private)

    route, budget, control, profile = _admit_configuration(value, _build_profile, require_profile)
    return TradeConfiguration(value, route, budget, control, profile, secret, private, requested)
