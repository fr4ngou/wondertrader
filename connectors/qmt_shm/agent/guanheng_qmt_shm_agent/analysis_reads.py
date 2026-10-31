# -*- coding: utf-8 -*-
"""原策略线程的日线和原生因子读取；只复制源值，复权仍归 WT Reader。"""
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone

from .history_1m import History1mAdapter, HistoryError, _number, fail
from .protocol import ProtocolError, canonical, decode

DAILY = 'market.market_data'
FACTORS = 'market.divid_factors'
DAILY_POLICY = 'qmt.daily-read.v1'
FACTORS_POLICY = 'qmt.factor-read.v1'
PROFILE_VERSION = 'qmt.read-profile.v7'
FIELDS = ('time', 'open', 'high', 'low', 'close', 'volume', 'amount')
SHANGHAI = timezone(timedelta(hours=8))


def _require(value):
    if not value:
        raise ProtocolError('analysis read exceeds its explicit source contract')


def limits(operation, value, max_result_bytes):
    """纯部署准入，不触发 SDK、文件或通信；额度只限定一次请求。"""
    _require(type(max_result_bytes) is int and 8192 <= max_result_bytes <= 2097152)
    fields = ('schema_version', 'max_calendar_days', 'max_rows', 'max_data_bytes') if operation == DAILY else (
        'schema_version', 'max_events', 'max_data_bytes')
    _require(operation in (DAILY, FACTORS) and type(value) is dict and set(value) == set(fields))
    _require(value['schema_version'] == ('qmt.daily-history.v1' if operation == DAILY else 'qmt.divid-factors.v1'))
    for name, maximum in ((('max_calendar_days', 40000), ('max_rows', 20000)) if operation == DAILY else (('max_events', 4096),)):
        _require(type(value[name]) is int and 1 <= value[name] <= maximum)
    _require(type(value['max_data_bytes']) is int and 1024 <= value['max_data_bytes'] <= max_result_bytes - 4096)
    return decode(canonical(value))


def _symbol(value):
    _require(type(value) is str and len(value) == 9 and re.match(r'^[0-9]{6}\.(SH|SZ)$', value) is not None)
    return value


def _day(value):
    _require(type(value) is str and len(value) == 8 and re.match(r'^[0-9]{8}$', value) is not None)
    try:
        parsed = date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        raise ProtocolError('analysis read date invalid')
    _require(1992 <= parsed.year <= 2099)
    return parsed


def arguments(operation, value, scope, as_of_date):
    _require(type(value) is dict and type(as_of_date) is date)
    if operation == FACTORS:
        _require(set(value) == {'symbol'})
        return (_symbol(value['symbol']),)
    _require(operation == DAILY and set(value) == {'symbol', 'start_date', 'end_date', 'max_rows', 'adjustment'})
    symbol = _symbol(value['symbol'])
    start, end = _day(value['start_date']), _day(value['end_date'])
    _require(start <= end <= as_of_date and (end - start).days < scope['max_calendar_days'])
    _require(type(value['max_rows']) is int and 1 <= value['max_rows'] <= scope['max_rows'])
    _require(type(value['adjustment']) is str and value['adjustment'] in ('none', 'front_ratio'))
    return symbol, value['start_date'], value['end_date'], value['max_rows'], value['adjustment'], start, end


class _AnalysisAdapter(History1mAdapter):
    """复用分钟适配器的原线程、同一截止和有界编码；不继承分钟日期范围。"""
    def __init__(self, context, operation, scope, max_result_bytes, clock=time.monotonic, as_of_date_provider=None):
        from .read_capabilities import shanghai_date
        self.scope = limits(operation, scope, max_result_bytes)
        self.context, self.operation = context, operation
        self.max_data_bytes, self.max_result_bytes = self.scope['max_data_bytes'], max_result_bytes
        self.clock, self.owner = clock, threading.get_ident()
        self.as_of_date_provider = shanghai_date if as_of_date_provider is None else as_of_date_provider
        _require(callable(clock) and callable(self.as_of_date_provider))

    def execute(self, value, deadline):
        self._check(deadline)
        parsed = arguments(self.operation, value, self.scope, self.as_of_date_provider())
        data = self._read(parsed, deadline)
        self._encode(data, self.max_data_bytes, deadline)
        return data


class DailyHistoryAdapter(_AnalysisAdapter):
    def __init__(self, context, scope, max_result_bytes, **kwargs):
        _AnalysisAdapter.__init__(self, context, DAILY, scope, max_result_bytes, **kwargs)

    def _read(self, parsed, deadline):
        symbol, start_text, end_text, maximum, adjustment, start, end = parsed
        self._check(deadline)
        try:
            values = self.context.get_market_data_ex(fields=list(FIELDS), stock_code=[symbol], period='1d',
                start_time=start_text, end_time=end_text, count=maximum + 1,
                dividend_type=adjustment, fill_data=False, subscribe=False)
        except Exception:
            fail('qmt_call_failed')
        self._check(deadline)
        if type(values) is not dict or set(values) != {symbol}:
            fail('source_shape_invalid')
        frame = values[symbol]
        try:
            shape = frame.shape
            if type(shape) not in (tuple, list) or len(shape) != 2 or any(type(n) is not int or n < 0 for n in shape):
                fail('source_shape_invalid')
            rows, columns = shape
            if rows > maximum:
                fail('history_window_limit')
            if columns not in ((0, 7) if rows == 0 else (7,)):
                fail('source_shape_invalid')
            names = []
            for name in frame.columns:
                self._check(deadline)
                if len(names) >= columns or type(name) is not str or name not in FIELDS or name in names:
                    fail('source_shape_invalid')
                names.append(name)
            if len(names) != columns:
                fail('source_shape_invalid')
            positions = [names.index(field) for field in FIELDS] if columns else []
            iterator, output, previous = iter(frame.itertuples(index=False, name=None)), {}, None
            for index in range(rows + 1):
                self._check(deadline)
                try:
                    original = next(iterator)
                except StopIteration:
                    if index != rows:
                        fail('source_shape_invalid')
                    break
                if index == rows or type(original) not in (tuple, list) or len(original) != columns:
                    fail('source_shape_invalid')
                selected = []
                for position in positions:
                    self._check(deadline)
                    selected.append(_number(original[position]))
                stamp = selected[0]
                if not float(stamp).is_integer() or not 0 <= stamp <= 4102444800000:
                    fail('source_value_invalid')
                # QMT time 为实际毫秒时标，日线按上海日期归属；不伪造首次可知时刻。
                observed = datetime.fromtimestamp(stamp / 1000., SHANGHAI).date()
                if not start <= observed <= end or (previous is not None and observed <= previous):
                    fail('source_value_invalid')
                previous = observed
                if min(selected[1:5]) <= 0 or min(selected[5:]) < 0:
                    fail('source_value_invalid')
                output['{0:04d}{1:02d}{2:02d}'.format(observed.year, observed.month, observed.day)] = dict(zip(FIELDS[1:], selected[1:]))
            self._check(deadline)
            return {symbol: output}
        except (HistoryError, ProtocolError):
            raise
        except Exception:
            fail('source_shape_invalid')


class DividFactorsAdapter(_AnalysisAdapter):
    def __init__(self, context, scope, max_result_bytes, **kwargs):
        _AnalysisAdapter.__init__(self, context, FACTORS, scope, max_result_bytes, **kwargs)

    def _read(self, parsed, deadline):
        self._check(deadline)
        try:
            original = self.context.get_divid_factors(parsed[0])
        except Exception:
            fail('qmt_call_failed')
        self._check(deadline)
        if type(original) is not dict or len(original) > self.scope['max_events']:
            fail('source_shape_invalid')
        output = {}
        for key, row in original.items():
            self._check(deadline)
            stamp = _number(key)
            if not float(stamp).is_integer() or not 0 <= stamp <= 4102444800000 or type(row) not in (list, tuple) or len(row) != 7:
                fail('source_value_invalid')
            values = []
            for value in row:
                self._check(deadline)
                values.append(_number(value))
            if values[6] <= 0:
                fail('source_value_invalid')
            label = str(int(stamp))
            if label in output:
                fail('source_value_invalid')
            output[label] = values
        self._check(deadline)
        return output
