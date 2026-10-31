# -*- coding: utf-8 -*-
"""QST-R9 原线程交易调用边界；仅显式注入的 SDK 替身/函数可被调用。

本模块不启动线程或 I/O。索引仅抑制当前 Agent 会话的重复调用；Host
负责持久命令、权限核验与重启核查，SDK 正常返回不证明柜台受理。
"""
import inspect
import math
from _thread import get_ident
from time import monotonic

from .trading_contract import (
    TradingKernelError, validate_trade_binding, validate_trade_command, command_digest,
    _MAX_INTEGER, _fail, _fraction, _result, terminal_insert_observed)


_MISSING = object()


def trade_admission_error(operation, enabled, closed, hard_fault, unknown_fenced):
    """UC-R1 原操作准入；unknown只封新insert，具体取消关联由Host拥有。"""
    if not enabled:
        return 'writes_disabled'
    if closed or hard_fault is not None or (unknown_fenced and operation != 'order.cancel'):
        return 'admission_closed'
    return None


class TradingKernel(object):
    """绑定原线程的有限调用 owner；request_close 可由停止通知调用。

    execute 的 deadline 是调用方已映射的原 monotonic D。已保存身份可在
    close/过期后取原结果；跨线程、非 live_drain 和同步重入均只报安全码。
    request_close 关闭后续准入，已经进入执行的调用仍由其原 D 收尾。
    """
    def __init__(self, context, *, binding, passorder, cancel,
                 writes_enabled=False, clock=monotonic, reserve_call=None, release_call=None):
        if type(writes_enabled) is not bool or not all(
                callable(item) for item in (passorder, cancel, clock)):
            _fail('invalid_configuration')
        if not ((reserve_call is None and release_call is None)
                or (callable(reserve_call) and callable(release_call))):
            _fail('invalid_configuration')
        self._binding = validate_trade_binding(binding)
        self._context = context
        self._passorder, self._cancel, self._clock = passorder, cancel, clock
        self._reserve_call, self._release_call = reserve_call, release_call
        self._owner = get_ident()
        self._enabled = writes_enabled
        self._closed = False
        self._unknown_fenced = False
        self._hard_fault = None
        self._executing = False
        self._commands = {}
        self._observed_unknown = set()

    def request_close(self):
        """只停止新写；不清索引、不发撤单、不丢失在途调用所有权。"""
        self._closed = True

    def fence_unknown(self):
        self._unknown_fenced = True

    def observe_order_query(self, commands, rows):
        """原线程消费已核完整ORDER；保留原结果及去重身份，只退役已证明的insert等待。"""
        if get_ident() != self._owner or self._executing:
            _fail('wrong_thread')
        changed = False
        for command in commands:
            identity = command['command_id']
            old = self._commands.get(identity)
            if (old is not None and old[0] == command_digest(command)
                    and old[1]['stage'] == 'unknown' and identity not in self._observed_unknown
                    and terminal_insert_observed(command, rows)):
                self._observed_unknown.add(identity)
                changed = True
        if changed:
            self._unknown_fenced = any(value[1]['stage'] == 'unknown'
                and identity not in self._observed_unknown for identity, value in self._commands.items())
        return self._unknown_fenced

    def request_fault(self, code):
        # 首个硬错独占此槽；先前unknown不遮蔽后继时钟/交接故障。
        if self._hard_fault is None:
            self._hard_fault = code

    def _admission(self, operation):
        return trade_admission_error(operation, self._enabled, self._closed,
                                     self._hard_fault, self._unknown_fenced)

    def _now(self):
        try:
            now = self._clock()
        except BaseException:
            self.request_fault('clock_failed')
            _fail('clock_failed')
        if type(now) not in (int, float):
            self.request_fault('clock_failed')
            _fail('clock_failed')
        try:
            finite = math.isfinite(now)
        except (OverflowError, ValueError):
            finite = False
        if not finite:
            self.request_fault('clock_failed')
            _fail('clock_failed')
        return now

    def execute(self, command, *, deadline, phase):
        if get_ident() != self._owner:
            _fail('wrong_thread')
        if self._executing:
            _fail('reentrant_call')
        if type(phase) is not str or phase != 'live_drain':
            _fail('invalid_phase')
        if type(deadline) not in (int, float):
            _fail('invalid_deadline')
        try:
            finite = math.isfinite(deadline)
        except (OverflowError, ValueError):
            finite = False
        if not finite:
            _fail('invalid_deadline')
        self._executing = True
        try:
            frozen = validate_trade_command(command)
            digest = command_digest(frozen)
            identity = frozen['command_id']
            old = self._commands.get(identity)
            if old is not None:
                if old[0] != digest:
                    _fail('command_conflict')
                return dict(old[1])
            if len(self._commands) >= self._binding['max_commands']:
                return _result(frozen, digest, 'definitely_not_called', False,
                               'capacity_exhausted')
            # 在任何注入时钟/SDK 前占身份。调用前拒绝也不因刷新 D 而重试。
            stored = _result(frozen, digest, 'definitely_not_called', False,
                             'not_admitted')
            self._commands[identity] = (digest, stored)
            self._execute(frozen, deadline, stored)
            return dict(stored)
        finally:
            self._executing = False

    def _execute(self, command, deadline, result):
        binding = self._binding
        code = None
        if any(command[name] != binding[name]
               for name in ('binding_id', 'account_id', 'account_type')):
            code = 'binding_mismatch'
        else:
            code = self._admission(command['operation'])
        args = None
        if code is None and command['operation'] == 'order.insert':
            rule = binding['symbol_rules'].get(command['symbol'])
            if rule is None:
                code = 'symbol_not_allowed'
            else:
                minimum = rule[command['side'] + '_min']
                step = rule[command['side'] + '_step']
                price_num, price_den = _fraction(command['limit_price'], 'invalid_command')
                tick_num, tick_den = _fraction(rule['price_tick'], 'invalid_binding')
                if (command['quantity'] < minimum
                        or (command['quantity'] - minimum) % step):
                    code = 'quantity_off_grid'
                elif price_num * tick_den % (price_den * tick_num):
                    code = 'price_off_grid'
                else:
                    price = float(command['limit_price'])
                    if not math.isfinite(price) or price <= 0:
                        code = 'price_not_representable'
                    else:
                        args = (23 if command['side'] == 'buy' else 24, 1101,
                            binding['account_id'], command['symbol'], 11, price,
                            command['quantity'], binding['strategy_name'], 2,
                            command['sdk_user_order_id'], self._context)
        elif code is None:
            args = (command['broker_order_id'], binding['account_id'], 'STOCK', self._context)
        if code is None:
            try:
                if self._now() >= deadline:
                    code = 'deadline_expired'
            except TradingKernelError:
                code = 'clock_failed'
            # 注入时钟也可能同步触发停止；此时尚无 SDK 副作用。
            code = code or self._admission(command['operation'])
        if code is not None:
            result['error_code'] = code
            return
        ticket = None
        if self._reserve_call is not None:
            try:
                ticket = self._reserve_call(command['operation'])
            except BaseException:
                self.request_fault('sdk_admission_failed')
                result['error_code'] = 'admission_closed'
                return
            if ticket is None:
                result['error_code'] = 'admission_closed'
                return
        try:
            if ticket is not None:
                # 短锁竞争期间原D/close可能变化；仍明确未调用时退票，保留原结果阶段。
                try:
                    code = 'deadline_expired' if self._now() >= deadline else None
                except TradingKernelError:
                    code = 'clock_failed'
                code = code or self._admission(command['operation'])
                if code is not None:
                    result['error_code'] = code
                    return
            self._invoke_sdk(command, args, deadline, result)
        finally:
            if ticket is not None:
                try:
                    self._release_call(ticket)
                except BaseException:
                    # Service锁存硬错；保留已有SDK结果及event owner未证释放的原票。
                    self.request_fault('sdk_release_failed')

    def _invoke_sdk(self, command, args, deadline, result):
        # SDK 进入点之后的全部失败均有副作用可能，保留该身份并关闭新写。
        result.update(stage='unknown', sdk_entered=True, error_code='sdk_exception')
        try:
            if command['operation'] == 'order.insert':
                returned = self._passorder(*args)
                valid = returned is None
            else:
                returned = self._cancel(*args)
                valid = type(returned) is bool
                if valid:
                    result['signal_sent'] = returned
            if not valid:
                result['error_code'] = 'invalid_sdk_return'
            elif self._now() >= deadline:
                result['error_code'] = 'deadline_expired_after_call'
            else:
                result.update(stage='sdk_returned', error_code=None)
        except BaseException:
            # SDK 或时钟的异常内容可能含账户/委托；对外只输出固定安全码。
            result['error_code'] = 'sdk_exception'
        if result['stage'] == 'unknown':
            self.fence_unknown()


# 字段来自国信官方 3.3.5 帮助 7254–7398、7866–7882 行。
# 这里只保留源观察，不解释金额/状态、不拼接身份、不推断所属命令。
_ORDER_FIELDS = ('m_strAccountID', 'm_strExchangeID', 'm_strInstrumentID',
    'm_strOrderRef', 'm_strOrderSysID', 'm_strRemark', 'm_nOrderPriceType',
    'm_nDirection', 'm_nOffsetFlag', 'm_dLimitPrice', 'm_nVolumeTotalOriginal',
    'm_nOrderSubmitStatus', 'm_nOrderStatus', 'm_nVolumeTraded', 'm_nVolumeTotal',
    'm_nErrorID', 'm_dFrozenMargin', 'm_dFrozenCommission', 'm_strInsertDate',
    'm_strInsertTime', 'm_dTradedPrice', 'm_dCancelAmount', 'm_strCancelInfo')
_DEAL_FIELDS = ('m_strAccountID', 'm_strExchangeID', 'm_strInstrumentID',
    'm_strTradeID', 'm_strOrderRef', 'm_strOrderSysID', 'm_strRemark',
    'm_nDirection', 'm_nOffsetFlag', 'm_dPrice', 'm_nVolume', 'm_strTradeDate',
    'm_strTradeTime', 'm_dComssion', 'm_dTradeAmount', 'm_nOrderPriceType')
_ERROR_FIELDS = ('opType', 'orderType', 'accountID', 'orderCode', 'prType',
                 'modelPrice', 'modelVolume', 'strategyName')


def _source_scalar(value):
    if value is None or type(value) is bool:
        return value
    if type(value) is str:
        if len(value) > 4096:
            _fail('source_value_invalid')
        try:
            size = len(value.encode('utf-8'))
        except UnicodeError:
            _fail('source_value_invalid')
        if size <= 4096:
            return value
    elif type(value) is int and -_MAX_INTEGER <= value <= _MAX_INTEGER:
        return value
    elif type(value) is float and math.isfinite(value):
        return value
    _fail('source_value_invalid')


def _snapshot(source, fields):
    result = {}
    for name in fields:
        if type(source) is dict:
            value = source.get(name, _MISSING)
        else:
            try:
                value = getattr(source, name)  # 每个允许字段恰好至多一次真实 getter。
            except AttributeError:
                try:
                    declared = inspect.getattr_static(source, name, _MISSING)
                except Exception:
                    _fail('source_shape_invalid')
                if declared is not _MISSING:
                    _fail('source_shape_invalid')
                value = _MISSING
            except Exception:
                _fail('source_shape_invalid')
        if value is not _MISSING:
            result[name] = _source_scalar(value)
    return result


def snapshot_order(order_info):
    """有限白名单快照；缺失字段省略，null、零和原字符串分别保留。"""
    return _snapshot(order_info, _ORDER_FIELDS)


def snapshot_deal(deal_info):
    """成交原观察；SDK 对象只在本次投影借用，不持有或猜测 WT 身份。"""
    return _snapshot(deal_info, _DEAL_FIELDS)


def snapshot_error(order_args, err_msg):
    """错误策略串保持原值；文档没有保证可拆出唯一 userOrderId。"""
    if err_msg is not None and type(err_msg) is not str:
        _fail('source_value_invalid')
    return {'order_args': _snapshot(order_args, _ERROR_FIELDS),
            'err_msg': _source_scalar(err_msg)}
