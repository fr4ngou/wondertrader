# -*- coding: utf-8 -*-
"""单次原SDK列表读取；各Frame沿原日线解码，批次身份由原运输持有。"""
import re
import threading
import time
from datetime import date
from .analysis_reads import DailyHistoryAdapter, FIELDS, _day, _require
from .history_1m import History1mAdapter, HistoryError, fail
from .protocol import canonical, decode

POLICY = 'qmt.daily-batch-read.v1'
PROFILE_VERSION = 'qmt.read-profile.v8'
RESULT_SCHEMA = 'qmt.daily-batch-result.v1'


def limits(value, max_result_bytes):
    _require(type(max_result_bytes) is int and 8192 <= max_result_bytes <= 2097152)
    _require(type(value) is dict and set(value) == {'schema_version', 'max_symbols', 'max_calendar_days', 'max_rows', 'max_data_bytes'})
    _require(value['schema_version'] == 'qmt.daily-batch.v1')
    for key, maximum in (('max_symbols', 1024), ('max_calendar_days', 40000), ('max_rows', 20000)):
        _require(type(value[key]) is int and 1 <= value[key] <= maximum)
    _require(type(value['max_data_bytes']) is int and 1024 <= value['max_data_bytes'] <= max_result_bytes-4096)
    return decode(canonical(value))


def arguments(value, scope, as_of_date):
    _require(type(value) is dict and set(value) == {'symbols', 'start_date', 'end_date', 'max_rows', 'adjustment'})
    symbols = value['symbols']
    _require(type(symbols) is list and 1 <= len(symbols) <= scope['max_symbols'])
    _require(all(type(s) is str and len(s) == 9 and re.match(r'^[0-9]{6}\.(SH|SZ|BJ)$', s) is not None for s in symbols))
    _require(len(set(symbols)) == len(symbols))
    start, end = _day(value['start_date']), _day(value['end_date'])
    _require(type(as_of_date) is date and start <= end <= as_of_date and (end-start).days < scope['max_calendar_days'])
    _require(type(value['max_rows']) is int and 1 <= value['max_rows'] <= scope['max_rows'])
    _require(type(value['adjustment']) is str and value['adjustment'] in ('none', 'front_ratio'))
    return symbols, value['start_date'], value['end_date'], value['max_rows'], value['adjustment'], start, end


class _ReturnedFrames(object):
    """已完成SDK返回的内存视图，复用原解码器时不再次进入SDK。"""
    def __init__(self, frames):
        self.frames = frames

    def get_market_data_ex(self, **kwargs):
        symbol = kwargs['stock_code'][0]
        return {symbol: self.frames[symbol]}


class DailyBatchAdapter(History1mAdapter):
    def __init__(self, context, scope, max_result_bytes, clock=time.monotonic, as_of_date_provider=None):
        from .read_capabilities import shanghai_date
        self.scope = limits(scope, max_result_bytes)
        self.context, self.clock, self.owner = context, clock, threading.get_ident()
        self.max_result_bytes, self.max_data_bytes = max_result_bytes, self.scope['max_data_bytes']
        self.as_of_date_provider = shanghai_date if as_of_date_provider is None else as_of_date_provider

    def execute(self, value, deadline):
        self._check(deadline)
        parsed = arguments(value, self.scope, self.as_of_date_provider())
        symbols, start, end, maximum, adjustment = parsed[:5]
        try:
            frames = self.context.get_market_data_ex(fields=list(FIELDS), stock_code=list(symbols), period='1d',
                start_time=start, end_time=end, count=maximum+1, dividend_type=adjustment, fill_data=False, subscribe=False)
        except Exception:
            fail('qmt_call_failed')
        self._check(deadline)
        if type(frames) is not dict or any(type(s) is not str or s not in symbols for s in frames):
            fail('source_shape_invalid')
        single_scope = dict(schema_version='qmt.daily-history.v1', max_calendar_days=self.scope['max_calendar_days'],
            max_rows=self.scope['max_rows'], max_data_bytes=self.max_data_bytes)
        decoder = DailyHistoryAdapter(_ReturnedFrames(frames), single_scope, self.max_result_bytes,
            clock=self.clock, as_of_date_provider=self.as_of_date_provider)
        output = {}
        for symbol in symbols:
            self._check(deadline)
            if symbol not in frames:
                output[symbol] = dict(status='missing', data={}, error_code=None)
                continue
            try:
                rows = decoder._read((symbol,)+parsed[1:], deadline)[symbol]
                output[symbol] = dict(status='observed' if rows else 'empty', data=rows, error_code=None)
            except HistoryError as error:
                # 局部源形状/值/条数保留证券状态；线程和同一截止失败继续原失败路径。
                if error.code not in ('source_shape_invalid', 'source_value_invalid', 'history_window_limit'):
                    raise
                output[symbol] = dict(status='requires_partition' if error.code == 'history_window_limit' else 'invalid',
                    data={}, error_code=error.code)
        result = dict(schema=RESULT_SCHEMA, adjustment=adjustment, securities=output)
        self._encode(result, self.max_data_bytes, deadline)
        return result
