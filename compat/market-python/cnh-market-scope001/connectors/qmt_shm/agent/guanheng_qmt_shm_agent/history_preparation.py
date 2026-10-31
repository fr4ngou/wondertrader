# -*- coding: utf-8 -*-
"""显式缓存补齐的纯合同；单位/覆盖和原生下载完成分别核实。"""
import math
import re
from datetime import datetime
from .protocol import ProtocolError, canonical, decode
from .trade_clock import CLOCK_SCHEMA

OPERATION = 'market.history_prepare'
PROFILE_VERSION = 'qmt.read-profile.v6'
POLICY = 'qmt.history-preparation.v1'
LIMITS_SCHEMA = 'qmt.history-preparation-limits.v1'
MARKET_LIMITS_SCHEMA = 'qmt.history-preparation-limits.v2'
RESULT_SCHEMA = 'qmt.history-preparation-result.v1'


def _fail():
    raise ProtocolError('history preparation exceeds its explicit capability')


def limits(value):
    from .read_capabilities import _fields, _integer
    if type(value) is not dict:
        _fail()
    schema = value.get('schema_version')
    fields = ('schema_version', 'periods', 'max_calendar_days',
              'max_tasks', 'max_queued', 'total_timeout_ms')
    # v2按来源支持的沪深市场接收证券，证券是否存在及有无数据由QMT确认。
    # 已签v1配对继续使用原清单语义；新版本不会扩大旧认证身份的能力。
    if schema == LIMITS_SCHEMA:
        _fields(value, fields + ('symbols',))
        symbols = value['symbols']
        if (type(symbols) is not list or not 1 <= len(symbols) <= 128
                or any(type(s) is not str or re.fullmatch(r'[0-9]{6}\.(?:SH|SZ)', s) is None for s in symbols)
                or symbols != sorted(set(symbols))):
            _fail()
    elif schema == MARKET_LIMITS_SCHEMA:
        _fields(value, fields)
    else:
        _fail()
    periods = value['periods']
    if (type(periods) is not list or not periods
            or any(type(p) is not str or p not in ('1m', '1d') for p in periods)
            or periods != sorted(set(periods))):
        _fail()
    _fields(value['max_calendar_days'], ('1m', '1d'))
    for number in value['max_calendar_days'].values():
        _integer(number, 1, 36600)
    for key in ('max_tasks', 'max_queued'):
        _integer(value[key], 1, 1024)
    _integer(value['total_timeout_ms'], 100, 30000)
    if value['max_queued'] > value['max_tasks']:
        _fail()
    return decode(canonical(value))


def arguments(value, scope):
    from .read_capabilities import _fields, _integer
    scope = limits(scope)
    _fields(value, ('symbol', 'period', 'start_time', 'end_time', 'clock_schema', 'deadline_ms'))
    if (type(value['symbol']) is not str
            or re.fullmatch(r'[0-9]{6}\.(?:SH|SZ)', value['symbol']) is None
            or ('symbols' in scope and value['symbol'] not in scope['symbols'])
            or type(value['period']) is not str or value['period'] not in scope['periods']
            or type(value['clock_schema']) is not str or value['clock_schema'] != CLOCK_SCHEMA):
        _fail()
    _integer(value['deadline_ms'], 1, 2**32 * 1000)
    stamps = []
    for key in ('start_time', 'end_time'):
        text = value[key]
        pattern = r'[0-9]{8}' if value['period'] == '1d' else r'[0-9]{12}00'
        if type(text) is not str or re.fullmatch(pattern, text) is None:
            _fail()
        try:
            stamp = datetime(int(text[:4]), int(text[4:6]), int(text[6:8]),
                int(text[8:10]) if len(text) > 8 else 0,
                int(text[10:12]) if len(text) > 8 else 0)
        except ValueError:
            _fail()
        if not 1992 <= stamp.year <= 2099:
            _fail()
        stamps.append(stamp)
    if (stamps[0] > stamps[1]
            or (stamps[1].date() - stamps[0].date()).days + 1 > scope['max_calendar_days'][value['period']]):
        _fail()
    return decode(canonical(value))


def now_ms(clock):
    try:
        value = clock.seconds()
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 2**32:
            _fail()
        return int(value * 1000)
    except Exception:
        _fail()


def require_live(value, scope, clock):
    arguments(value, scope)
    remaining = value['deadline_ms'] - now_ms(clock)
    if not 0 < remaining <= scope['total_timeout_ms']:
        _fail()
    return remaining


def returned(value):
    return dict(schema=RESULT_SCHEMA, effect='call_returned', coverage='unknown',
        **{key: value[key] for key in ('symbol', 'period', 'start_time', 'end_time')})


def validate_result(request, result):
    if result.get('ok') is True and result.get('data') != returned(request['arguments']):
        _fail()


def validate_configuration(value):
    """仅专用入口授v6；普通read构造及交易/bulk入口保持旧准入。"""
    from .read_configuration import validate_read_configuration
    admitted = validate_read_configuration(value, allow_preparation=True)
    if admitted.profile.get('read_profile_version') != PROFILE_VERSION:
        _fail()
    descriptor = admitted.profile['operation_profiles'][OPERATION]
    if (admitted.value['transport']['kind'] != 'builtin-shm'
            or admitted.value['max_pending'] != descriptor['limits']['max_queued']):
        _fail()
    return admitted
