# -*- coding: utf-8 -*-
"""QST2 纯值合同；不创建线程、SDK、文件、网络或共享内存资源。"""
import hashlib
import math
import re

from .protocol import TransportBudget, canonical, decode, identity

PROFILE_SCHEMA = 'qmt.quote-stream.v1'
WARMUP_PROFILE_SCHEMA = 'qmt.quote-stream.v2'
WARMUP_COMPLETE_SCHEMA = 'qmt.quote-warmup-complete.v1'
WARMUP_READY_SCHEMA = 'qmt.quote-warmup-ready.v1'
NATIVE_BATCH_LIMIT = 200
BATCH_SCHEMA = 'qmt.quote-batch.v1'
HEARTBEAT_SCHEMA = 'qmt.quote-heartbeat.v1'
TICK_FIELDS = ('time', 'lastPrice', 'open', 'high', 'low', 'lastClose', 'volume', 'amount')
COUNTER_FIELDS = ('callbacks', 'received_ticks', 'accepted_ticks', 'rejected_ticks', 'queue_depth', 'sent_ticks', 'latest_symbols', 'missing_symbols', 'overflows')


def _fields(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('quote stream fields differ')


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('quote stream integer exceeds budget')
    return value


def _symbols(symbols):
    if (type(symbols) is not list or not 1 <= len(symbols) <= 10000
            or any(type(s) is not str or re.fullmatch(r'[0-9]{6}[.](SH|SZ)', s) is None for s in symbols)
            or symbols != sorted(set(symbols))):
        raise ValueError('quote stream symbols must be sorted unique SH/SZ codes')
    return list(symbols)


def symbols_digest(symbols):
    return hashlib.sha256(canonical(_symbols(symbols))).hexdigest()


def validate_profile(profile, symbols):
    symbols = _symbols(symbols)
    _fields(profile, ('schema_version', 'symbols_sha256', 'max_symbols', 'max_batch', 'max_pending_ticks'))
    if profile['schema_version'] not in (PROFILE_SCHEMA, WARMUP_PROFILE_SCHEMA) or profile['symbols_sha256'] != symbols_digest(symbols):
        raise ValueError('quote stream profile identity differs')
    maximum = _integer(profile['max_symbols'], 1, 10000)
    if len(symbols) > maximum:
        raise ValueError('quote stream symbol capacity exceeded')
    # v1保留原上限；v2在同一原帧预算内传热态大批，接收owner仍按原200交Native。
    _integer(profile['max_batch'], 1, maximum if profile['schema_version'] == WARMUP_PROFILE_SCHEMA else NATIVE_BATCH_LIMIT)
    _integer(profile['max_pending_ticks'], maximum, 65536)
    return dict(profile)


def validate_settings(value):
    """返回独立配置；secret为原私有bytes，其余值只保留合同内普通类型。"""
    _fields(value, ('route', 'secret', 'max_frame', 'transport', 'connect_seconds', 'io_seconds', 'symbols', 'profile'))
    if type(value['secret']) is not bytes or len(value['secret']) < 32:
        raise ValueError('quote stream requires private IPC secret')
    route = identity(value['route'])
    _integer(value['max_frame'], 1024, 4194304)
    TransportBudget(value['connect_seconds'], value['io_seconds'])
    symbols = _symbols(value['symbols'])
    profile = validate_profile(value['profile'], symbols)
    transport = decode(canonical(value['transport']))
    if type(transport) is not dict or transport.get('kind') != 'builtin-shm':
        raise ValueError('quote stream requires builtin SHM')
    # 复用原布局/映射/认证联合准入，构造本身没有内核I/O。
    from .transport_profile import validate_transport_profile
    validate_transport_profile(transport, route, value['max_frame'], profile)
    return {'route': route, 'secret': value['secret'], 'max_frame': value['max_frame'],
        'transport': transport, 'connect_seconds': value['connect_seconds'], 'io_seconds': value['io_seconds'],
        'symbols': symbols, 'profile': profile}


def transport_digest(framer):
    """配对两端共享同一运输代摘要，用于关联断线证据。"""
    generation = getattr(framer, 'generation', None)
    if type(generation) is not str or re.fullmatch(r'[0-9a-f]{32}', generation) is None:
        return None
    return hashlib.sha256(generation.encode('ascii')).hexdigest()


def normalize_tick(row):
    """SDK行允许额外源字段；仅复制八个原数值，不替换缺值或换算量额。"""
    if type(row) is not dict or any(key not in row for key in TICK_FIELDS):
        raise ValueError('quote stream tick fields missing')
    tick = {}
    for key in TICK_FIELDS:
        value = row[key]
        if (type(value) not in (int, float)
                or (type(value) is int and not -(2 ** 63) <= value < 2 ** 64)
                or not math.isfinite(value)):
            raise ValueError('quote stream tick requires finite wire numbers')
        tick[key] = value
    stamp = tick['time']
    # 原epoch毫秒保留整值及数值类型；范围限定2004..2099，避免浮点转整数溢出。
    if not 1072886400000 <= stamp <= 4102444799999 or math.floor(stamp) != stamp:
        raise ValueError('quote stream epoch milliseconds invalid')
    low, high, price, opened = tick['low'], tick['high'], tick['lastPrice'], tick['open']
    if (low <= 0 or high < low or not low <= opened <= high or not low <= price <= high
            or tick['lastClose'] <= 0 or tick['volume'] < 0 or tick['amount'] < 0):
        raise ValueError('quote stream prices or cumulative quantities invalid')
    return tick


def validate_batch(packet, profile, symbols):
    """整包验证后返回独立ticks；任何非法成员拒绝整包，不产生部分回调。"""
    admitted = validate_profile(profile, symbols)
    _fields(packet, ('schema_version', 'kind', 'ticks'))
    if packet['schema_version'] != BATCH_SCHEMA or packet['kind'] not in ('snapshot', 'incremental'):
        raise ValueError('quote stream batch identity invalid')
    rows = packet['ticks']
    if type(rows) is not dict or not 1 <= len(rows) <= admitted['max_batch']:
        raise ValueError('quote stream batch size invalid')
    allowed, ticks = set(symbols), {}
    for symbol, row in rows.items():
        if symbol not in allowed:
            raise ValueError('quote stream batch has unadmitted symbol')
        _fields(row, TICK_FIELDS)
        ticks[symbol] = normalize_tick(row)
    return {'schema_version': BATCH_SCHEMA, 'kind': packet['kind'], 'ticks': ticks}


def validate_heartbeat(packet, profile=None):
    _fields(packet, ('schema_version',) + COUNTER_FIELDS)
    if packet['schema_version'] != HEARTBEAT_SCHEMA:
        raise ValueError('quote stream heartbeat identity invalid')
    result = {'schema_version': HEARTBEAT_SCHEMA}
    for key in COUNTER_FIELDS:
        result[key] = _integer(packet[key], 0, 2 ** 63 - 1)
    if profile is not None and result['queue_depth'] > profile['max_pending_ticks']:
        raise ValueError('quote stream heartbeat queue exceeds capacity')
    return result


def warmup_marker(schema, symbols):
    """同一已认证代的冷初始化集合收据；不携带报价、命令或新授权。"""
    if schema not in (WARMUP_COMPLETE_SCHEMA, WARMUP_READY_SCHEMA):
        raise ValueError('quote warmup marker schema differs')
    values = sorted(symbols)
    return dict(schema_version=schema, symbols_sha256=symbols_digest(values), symbol_count=len(values))


def validate_warmup_marker(packet, schema, symbols):
    _fields(packet, ('schema_version', 'symbols_sha256', 'symbol_count'))
    expected = warmup_marker(schema, symbols)
    if type(packet['symbol_count']) is not int or packet != expected:
        raise ValueError('quote warmup consumed symbols differ')
    return expected
