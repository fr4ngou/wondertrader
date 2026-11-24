# -*- coding: utf-8 -*-
"""QAR账户只读SDK边界：只返回data，不封装终态，不拥有账户账本。

构造线程独占调用；同一传入monotonic截止覆盖SDK、每次属性/item、投影和编码。
SDK与stdlib单步不可抢占，返回后立即检查；原终态finalizer/发布前检查归Agent。
"""
import inspect
import json
import math
import sys
import threading
import time
import types
from datetime import datetime, timezone

from .errors import GatewayError

SCHEMA = 'qmt.account-batch.v1'
IDENTITY_SCHEMA = 'qmt.account-batch.v2'
FEE_SCHEMA = 'qmt.account-batch.v3'
POLICY_VERSION = '1.0'
IDENTITY_POLICY_VERSION = '2.0'
FEE_POLICY_VERSION = '3.0'
LIMITS_SCHEMA = 'qmt.account-read.v1'
MAX_INTEGER = 2**53 - 1
_IDENTITY_FIELDS = ('m_strAccountID', 'm_strMoneyType')
_FIELDS = {
    'position': ('m_strInstrumentID', 'm_strExchangeID', 'm_nVolume',
        'm_nCanUseVolume', 'm_nYesterdayVolume', 'm_nFrozenVolume',
        'm_nOnRoadVolume', 'm_dAvgPrice', 'm_dOpenPrice', 'm_dPositionProfit',
        'm_dFloatProfit', 'm_dMarketValue'),
    'order': ('m_strInstrumentID', 'm_strExchangeID', 'm_strOrderSysID',
        'm_nOffsetFlag', 'm_nVolumeTotalOriginal', 'm_nVolumeTraded',
        'm_nVolumeTotal', 'm_nOrderStatus', 'm_dLimitPrice', 'm_dCancelAmount',
        'm_strInsertDate', 'm_strInsertTime'),
    'deal': ('m_strInstrumentID', 'm_strExchangeID', 'm_strOrderSysID',
        'm_strTradeID', 'm_nOffsetFlag', 'm_nVolume', 'm_dPrice',
        'm_dTradeAmount', 'm_strTradeDate', 'm_strTradeTime'),
    'account': ('m_dBalance', 'm_dAvailable', 'm_dPreBalance', 'm_dCommission',
        'm_dFrozenCash', 'm_dFrozenMargin', 'm_dFrozenCommission',
        'm_dPositionProfit', 'm_dFloatProfit'),
}
_IDENTITY_PROJECTION_FIELDS = ('m_strRemark', 'm_strOrderRef')
_TRADE_FEE_FIELDS = ('m_dCommission', 'm_dComission', 'm_dComssion')  # SDK逐笔当前费用别名，原值可缺。
_MESSAGES = {
    'invalid_request': '账户读取参数或受管额度不合格',
    'owner_required': '账户读取需要构造时的原策略线程',
    'execution_timeout': '账户读取已超出同一执行截止，按原请求核查',
    'source_shape_invalid': '账户来源结构或属性读取不合格',
    'source_value_invalid': '账户来源标量、身份或时间不合格',
    'result_too_large': '账户结果超过受管容量',
    'qmt_call_failed': '原生账户读取失败',
}
_MISSING = object()


class AccountQueryError(GatewayError):
    def __init__(self, code):
        GatewayError.__init__(self, code, _MESSAGES[code])


def _fail(code):
    raise AccountQueryError(code)


def account_projection_version(policy_version):
    """已准入descriptor的唯一版本投影；不从响应或写开关选择。"""
    if type(policy_version) is str:
        if policy_version == POLICY_VERSION:
            return 1
        if policy_version == IDENTITY_POLICY_VERSION:
            return 2
        if policy_version == FEE_POLICY_VERSION:
            return 3
    _fail('invalid_request')


def _fields(value, expected):
    if (type(value) is not dict or len(value) != len(expected)
            or any(type(key) is not str for key in value)
            or set(value) != set(expected)):
        _fail('invalid_request')


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        _fail('invalid_request')


def validate_account_limits(limits, max_result_bytes):
    """纯受管配置准入；不取SDK/时钟，不导入profile模块，返回无容器别名的dict。"""
    _integer(max_result_bytes, 8192, 2097152)
    _fields(limits, ('schema_version', 'account_binding', 'max_rows',
                     'max_nodes', 'max_scalar_chars', 'max_data_bytes'))
    if type(limits['schema_version']) is not str or limits['schema_version'] != LIMITS_SCHEMA:
        _fail('invalid_request')
    binding = limits['account_binding']
    _fields(binding, ('account_id', 'account_environment', 'currency', 'financial_profile'))
    account = binding['account_id']
    if type(account) is not str or not 1 <= len(account) <= 63:
        _fail('invalid_request')
    # 先限码点再编码；UTF-8不接受surrogate。JSON解码后的合法代理对已是单一码点。
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in account):
        _fail('invalid_request')
    try:
        if len(account.encode('utf-8')) > 63:
            _fail('invalid_request')
    except UnicodeError:
        _fail('invalid_request')
    for key, allowed in (('account_environment', ('simulation', 'live')),
                         ('currency', ('CNY',)),
                         ('financial_profile', ('cny_cash_shsz_v1',))):
        if type(binding[key]) is not str or binding[key] not in allowed:
            _fail('invalid_request')
    _integer(limits['max_rows'], 1, 4096)
    _integer(limits['max_nodes'], 1, 65536)
    _integer(limits['max_scalar_chars'], 1, 262144)
    _integer(limits['max_data_bytes'], 1024, min(1048576, max_result_bytes - 4096))
    return {'schema_version': LIMITS_SCHEMA,
            'account_binding': {key: binding[key] for key in
                ('account_id', 'account_environment', 'currency', 'financial_profile')},
            'max_rows': limits['max_rows'], 'max_nodes': limits['max_nodes'],
            'max_scalar_chars': limits['max_scalar_chars'],
            'max_data_bytes': limits['max_data_bytes']}


def validate_account_arguments(value):
    """只准三项固定参数；账户、函数及策略过滤均不由请求提供。"""
    _fields(value, ('account_type', 'datatype', 'scope'))
    if (type(value['account_type']) is not str or value['account_type'] != 'stock'
            or type(value['scope']) is not str or value['scope'] != 'account'
            or type(value['datatype']) is not str or value['datatype'] not in _FIELDS):
        _fail('invalid_request')
    return value['datatype']


def _utc_now():
    return datetime.now(timezone.utc)


def _finite_clock(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


class _Budget(object):
    """最终DTO每个值/对象键各一节点；键和字符串按重复出现的Unicode码点计量。"""
    def __init__(self, limits, check):
        self.max_nodes = limits['max_nodes']
        self.max_chars = limits['max_scalar_chars']
        self.nodes = self.chars = 0
        self.check = check

    def node(self):
        self.check()
        if self.nodes >= self.max_nodes:
            _fail('result_too_large')
        self.nodes += 1

    def scalar(self, value):
        self.node()
        if type(value) is str:
            count = len(value)
            if count > self.max_chars - self.chars:
                _fail('result_too_large')
            for character in value:
                self.check()
                if 0xd800 <= ord(character) <= 0xdfff:
                    _fail('source_value_invalid')
            self.chars += count
        elif type(value) is int:
            if not -MAX_INTEGER <= value <= MAX_INTEGER:
                _fail('source_value_invalid')
        elif type(value) is float:
            if not math.isfinite(value):
                _fail('source_value_invalid')
        elif value is not None and type(value) is not bool:
            _fail('source_value_invalid')
        self.check()
        return value

    def fixed_copy(self, value):
        # 只走本模块构造的有限元数据；原SDK对象永远不进入递归遍历。
        if type(value) is dict:
            self.node()
            output = {}
            for key, item in value.items():
                self.check()
                self.scalar(key)
                output[key] = self.fixed_copy(item)
            self.check()
            return output
        if type(value) is list:
            self.node()
            output = []
            for item in value:
                self.check()
                output.append(self.fixed_copy(item))
            self.check()
            return output
        return self.scalar(value)


class AccountQueryAdapter(object):
    """固定账户与只读函数只在构造时注入；不查询、不修改登录/账户状态。

    execute只返回独立data DTO；原Agent负责统一结果finalizer和发布前截止检查。
    可选金融字段的合法JSON类型原样保留，财务意义与invalid判定归唯一C++ mapper。
    """
    def __init__(self, read_trade_detail, limits, max_result_bytes,
                 clock=time.monotonic, utc_now=_utc_now, *, projection_version=1, observe_result=None):
        if type(projection_version) is not int or projection_version not in (1, 2, 3):
            _fail('invalid_request')
        self._projection_version = projection_version
        self._schema = (SCHEMA, IDENTITY_SCHEMA, FEE_SCHEMA)[projection_version-1]
        self._limits = validate_account_limits(limits, max_result_bytes)
        if not callable(read_trade_detail) or not callable(clock) or not callable(utc_now):
            _fail('invalid_request')
        self._reader = read_trade_detail
        if observe_result is not None and not callable(observe_result):
            _fail('invalid_request')
        self._observe_result = observe_result
        self._clock, self._utc_now = clock, utc_now
        self._owner = threading.get_ident()

    def _check(self, deadline):
        if threading.get_ident() != self._owner:
            _fail('owner_required')
        if not _finite_clock(deadline):
            _fail('invalid_request')
        try:
            now = self._clock()
        except Exception:
            _fail('invalid_request')
        if not _finite_clock(now):
            _fail('invalid_request')
        if now >= deadline:
            _fail('execution_timeout')

    def _stamp(self, deadline):
        self._check(deadline)
        try:
            value = self._utc_now()
            self._check(deadline)
            if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
                _fail('source_value_invalid')
            value = value.astimezone(timezone.utc)
            text = '{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.{:06d}Z'.format(
                value.year, value.month, value.day, value.hour, value.minute,
                value.second, value.microsecond)
        except AccountQueryError:
            raise
        except Exception:
            self._check(deadline)
            _fail('source_value_invalid')
        self._check(deadline)
        return value, text

    def _field(self, row, name, deadline):
        self._check(deadline)
        if type(row) is dict:
            value = row.get(name, _MISSING)
        else:
            try:
                value = getattr(row, name)  # 每个允许字段最多一次真正getter。
            except AttributeError:
                self._check(deadline)
                try:
                    declared = inspect.getattr_static(row, name, _MISSING)
                except Exception:
                    self._check(deadline)
                    _fail('source_shape_invalid')
                self._check(deadline)
                if declared is not _MISSING:
                    _fail('source_shape_invalid')
                value = _MISSING
            except Exception:
                self._check(deadline)
                _fail('source_shape_invalid')
        self._check(deadline)
        return value

    def _scalar(self, value, deadline):
        self._check(deadline)
        if type(value) in (str, int, float, bool) or value is None:
            return value
        # 不import第三方。仅承认已注入SDK运行时numpy模块的同名精确导出标量类型；
        # 仅伪造__module__、自定义子类和ndarray不能获得任意item转换资格。
        numpy = sys.modules.get('numpy')
        kind = type(value)
        if type(numpy) is not types.ModuleType or type(kind) is not type:
            _fail('source_value_invalid')
        namespace = vars(numpy)
        generic = namespace.get('generic')
        if (type(generic) is not type or namespace.get(kind.__name__) is not kind
                or kind.__module__ != 'numpy' or not issubclass(kind, generic)):
            _fail('source_value_invalid')
        self._check(deadline)
        try:
            item = getattr(value, 'item')
            self._check(deadline)
            if not callable(item):
                _fail('source_value_invalid')
            value = item()
        except AccountQueryError:
            raise
        except Exception:
            self._check(deadline)
            _fail('source_value_invalid')
        self._check(deadline)
        if type(value) not in (str, int, float, bool) and value is not None:
            _fail('source_value_invalid')
        return value

    def _row(self, row, datatype, budget, deadline):
        if type(row) is not dict and issubclass(type(row), (dict, list, tuple, str, bytes,
                                                    bytearray, int, float, bool, set, frozenset)):
            _fail('source_shape_invalid')
        if row is None:
            _fail('source_shape_invalid')
        budget.node()
        output = {}
        names = _FIELDS[datatype] + _IDENTITY_FIELDS
        if self._projection_version in (2, 3) and datatype in ('order', 'deal'):
            names += _IDENTITY_PROJECTION_FIELDS
        if self._projection_version == 3 and datatype == 'deal':
            names += _TRADE_FEE_FIELDS
        for name in names:
            self._check(deadline)
            value = self._field(row, name, deadline)
            if value is _MISSING:
                continue
            value = self._scalar(value, deadline)
            if name == 'm_strAccountID':
                if type(value) is not str or value != self._limits['account_binding']['account_id']:
                    _fail('source_value_invalid')
            elif name == 'm_strMoneyType':
                # 空币种保留来源原值；部署CNY声明与来源未知由金融mapper分别表达。
                if type(value) is not str or value not in ('', self._limits['account_binding']['currency']):
                    _fail('source_value_invalid')
            budget.scalar(name)
            output[name] = budget.scalar(value)
        self._check(deadline)
        return output

    def _encode(self, data, deadline):
        self._check(deadline)
        try:
            encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True,
                separators=(',', ':'), allow_nan=False)
            iterator = iter(encoder.iterencode(data))
            size = 0
            while True:
                self._check(deadline)
                try:
                    piece = next(iterator)
                except StopIteration:
                    break
                self._check(deadline)
                encoded = piece.encode('utf-8')
                self._check(deadline)
                size += len(encoded)
                if size > self._limits['max_data_bytes']:
                    _fail('result_too_large')
        except AccountQueryError:
            raise
        except Exception:
            self._check(deadline)
            _fail('source_value_invalid')
        self._check(deadline)

    def execute(self, arguments, deadline):
        self._check(deadline)
        datatype = validate_account_arguments(arguments)
        self._check(deadline)
        started, started_text = self._stamp(deadline)
        binding = dict(self._limits['account_binding'], origin='trusted_bootstrap_argument')
        # completed_at预留最终同宽27字符UTC值，row_count预留一个标量节点；
        # 最终替换不重复计预算。小额度因此可在SDK前拒绝，最终DTO仍精确计量。
        template = {'schema_version': self._schema, 'account_binding': binding,
            'query': {'account_type': 'stock', 'datatype': datatype,
                      'scope': 'account', 'strategy_name': None},
            'execution': {'started_at': started_text, 'completed_at': started_text},
            'completeness': {'complete': True, 'truncated': False, 'row_count': 0,
                             'coverage': 'sdk_returned_list'},
            'trading_date': {'value': None, 'source': 'unavailable'}, 'rows': []}
        budget = _Budget(self._limits, lambda: self._check(deadline))
        data = budget.fixed_copy(template)
        self._check(deadline)
        try:
            values = self._reader(self._limits['account_binding']['account_id'], 'stock', datatype)
        except Exception:
            self._check(deadline)
            _fail('qmt_call_failed')
        self._check(deadline)
        if type(values) is not list:
            _fail('source_shape_invalid')
        count = len(values)
        if count > self._limits['max_rows']:
            _fail('result_too_large')
        if datatype == 'account' and count != 1:
            _fail('source_shape_invalid')
        for index in range(count):
            self._check(deadline)
            if len(values) != count:
                _fail('source_shape_invalid')
            row = values[index]
            self._check(deadline)
            data['rows'].append(self._row(row, datatype, budget, deadline))
            self._check(deadline)
            if len(values) != count:
                _fail('source_shape_invalid')
        completed, completed_text = self._stamp(deadline)
        if completed < started:
            _fail('source_value_invalid')
        data['execution']['completed_at'] = completed_text
        data['completeness']['row_count'] = count
        self._encode(data, deadline)
        self._check(deadline)
        if self._observe_result is not None:
            self._observe_result(data)
            self._check(deadline)
        return data
