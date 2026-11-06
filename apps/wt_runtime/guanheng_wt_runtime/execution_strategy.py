"""同安装CTA运行体的Python薄接口；金融事实与生命周期沿原WT/受管进程。"""
from __future__ import annotations

import ctypes as C
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
import threading
import time
from uuid import UUID

from .execution_process import ExecutionProcessConfig
from .managed_local_process import _inspect, _read, _json


class CtaBridgeError(RuntimeError):
    """有限接口原因码；原始业务异常仅保留在本进程私有owner。"""


def _need(value, code='invalid_binding'):
    if not value:
        raise CtaBridgeError(code)


class _Packed(C.Structure):
    _pack_ = 8


class Bar(_Packed):
    _fields_ = [('date', C.c_uint32), ('reserved', C.c_uint32), ('time', C.c_uint64),
                *[(key, C.c_double) for key in ('open', 'high', 'low', 'close', 'volume', 'money', 'hold', 'diff')]]


class Event(_Packed):
    _fields_ = [('size', C.c_uint32), ('kind', C.c_uint32), ('epoch', C.c_uint64),
                ('owner_token', C.c_uint64), ('thread_id', C.c_uint64), ('ctx_id', C.c_uint32),
                ('date', C.c_uint32), ('time', C.c_uint32), ('tdate', C.c_uint32),
                ('symbol', C.c_char * 64), ('period', C.c_char * 8), ('bar', Bar)]


class Facts(_Packed):
    _fields_ = [('size', C.c_uint32), ('date', C.c_uint32), ('time', C.c_uint32),
                ('tdate', C.c_uint32), ('fund_pnl', C.c_double)]


class CashBasis(_Packed):
    _fields_ = [('size', C.c_uint32), ('version', C.c_uint32),  # 可选现金扩展结构大小与版本1。
                ('realized_pnl_cny', C.c_double),  # WT原已实现盈亏，CNY。
                ('fees_cny', C.c_double),  # WT原累计费用，CNY。
                ('average_price_cny', C.c_double)]  # 证券原平均成本，CNY/份。


class Quote(_Packed):
    _fields_ = [('size', C.c_uint32), ('version', C.c_uint32),  # 原扩展大小与版本1。
                ('action_date', C.c_uint32),  # 原tick事件日期，上海YYYYMMDD。
                ('action_time', C.c_uint32),  # 原tick事件时刻，上海HHMMSSmmm。
                ('price_cny', C.c_double)]  # 原WT已应用tick原价，CNY/份。


class Position(_Packed):
    _fields_ = [('size', C.c_uint32), ('flags', C.c_uint32),
                *[(key, C.c_double) for key in ('raw_position', 'raw_valid', 'enum_target')],
                *[(key, C.c_uint64) for key in ('first_entry', 'last_entry', 'last_exit')],
                ('actual_quantity', C.c_double), ('pending_quantity', C.c_double)]


class Target(_Packed):
    _fields_ = [('symbol', C.c_char * 64), ('quantity', C.c_double)]


class _BrokerFacts(_Packed):
    _fields_ = [('size', C.c_uint32), ('version', C.c_uint32), ('positions_known', C.c_uint32), ('account_known', C.c_uint32),
                *[(key, C.c_uint64) for key in ('position_revision', 'position_received_ms', 'account_revision',
                                               'account_received_ms', 'published_epoch_ms')],
                ('balance', C.c_double), ('available', C.c_double)]


class _BrokerPosition(_Packed):
    _fields_ = [('symbol', C.c_char * 64), ('quantity', C.c_double), ('sellable', C.c_double), ('is_long', C.c_uint32)]


class _PendingOrder(_Packed):
    _fields_ = [('symbol',C.c_char*64),  # 原WT标准证券代码；调用方值副本。
                ('remaining',C.c_double),  # 原表未成交股/份；不用于累加持仓。
                ('is_buy',C.c_uint32)]  # 1买、0卖，沿原委托方向。


class _BrokerTradeFacts(_Packed):
    _fields_ = [(key,C.c_uint32) for key in ('size','version','known','error')] + [
        (key,C.c_uint64) for key in ('revision','received_ms','query_revision','query_received_ms',
                                    'live_revision','published_epoch_ms')]


class _BrokerTrade(_Packed):
    _fields_ = [(key,C.c_char*64) for key in ('symbol','trade_id','order_id','user_tag')] + [
        ('trade_date',C.c_uint32),('is_buy',C.c_uint32)] + [
        (key,C.c_uint64) for key in ('trade_time','first_live_revision','received_ms')] + [
        (key,C.c_double) for key in ('quantity','price','amount')]


class _BrokerTradeFactsV2(_Packed):
    _fields_ = [('facts',_BrokerTradeFacts),('submission_revision',C.c_uint64),
                ('origins_known',C.c_uint32),('reserved',C.c_uint32)]


class _BrokerTradeV2(_Packed):
    _fields_ = [('trade',_BrokerTrade),('submission_revision',C.c_uint64)]


class _Config(_Packed):
    _fields_ = [('size', C.c_uint32), ('abi_version', C.c_uint32), ('read_count', C.c_uint32),
                ('execution_count', C.c_uint32), ('strategy_id', C.c_char * 64), ('main_symbol', C.c_char * 64),
                ('read_symbols', (C.c_char * 64) * 16), ('execution_symbols', (C.c_char * 64) * 8)]


class _ConfigV2(_Packed):
    # 可选九标的配置，原_Config及所有共享值结构保持。
    _fields_ = [*_Config._fields_[:-1], ('execution_symbols', (C.c_char * 64) * 9)]


class _Status(_Packed):
    _fields_ = [('size', C.c_uint32), ('configured', C.c_uint32), ('created', C.c_uint32),
                ('destroyed', C.c_uint32), ('active', C.c_uint32), ('failure', C.c_int32),
                ('callbacks', C.c_uint64), ('setters', C.c_uint64), ('owner_token', C.c_uint64)]


_Callback = C.CFUNCTYPE(C.c_int32, C.POINTER(Event), C.c_void_p)
_claim_lock, _claimed = threading.Lock(), False


def _symbol(value):
    _need(type(value) is str and 0 < len(value) < 32 and all(32 < ord(c) < 127 for c in value))
    parts = value.split('.')
    _need(len(parts) in (2, 3) and all(parts) and (len(parts) != 3 or parts[-1] not in ('+', '-')))
    return value


@dataclass(frozen=True)
class StrategyBinding:
    strategy_id: str
    main_symbol: str
    read_symbols: tuple[str, ...]
    execution_symbols: tuple[str, ...]  # 明确目标权限；空元组为只读绑定，须Native可选能力1。
    callback: object
    native_config_abi: int = 1  # 配置布局版本；默认1八标的，显式2允许九标的。

    def __post_init__(self):
        name = self.strategy_id
        _need(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,63}', name) and not name.endswith('.'))
        stem = name.split('.')[0].lower()
        _need(stem not in ('con', 'prn', 'aux', 'nul') and not re.fullmatch(r'(?:com|lpt)[1-9]', stem))
        _symbol(self.main_symbol)
        _need(type(self.native_config_abi) is int and self.native_config_abi in (1, 2), 'configuration_abi')
        capacity = 9 if self.native_config_abi == 2 else 8
        for values, maximum, minimum in ((self.read_symbols, 16, 1), (self.execution_symbols, capacity, 0)):
            _need(type(values) is tuple and minimum <= len(values) <= maximum)
            _need(len(set(values)) == len(values))
            for code in values:
                _symbol(code)
        _need(self.main_symbol in self.read_symbols and set(self.execution_symbols) <= set(self.read_symbols)
              and callable(self.callback))


@dataclass(frozen=True)
class BarValue:
    date: int
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    money: float
    hold: float
    diff: float


@dataclass(frozen=True)
class EventValue:
    kind: int
    epoch: int
    owner_token: int
    thread_id: int
    ctx_id: int
    date: int
    time: int
    tdate: int
    symbol: str
    period: str
    bar: BarValue | None


@dataclass(frozen=True)
class FactsValue:
    date: int
    time: int
    tdate: int
    fund_pnl: float


@dataclass(frozen=True)
class CashBasisValue:
    realized_pnl_cny: float  # WT flag1原已实现盈亏，CNY。
    fees_cny: float  # WT flag3原费用，CNY。
    average_price_cny: float  # 当前证券原WT平均持仓成本，CNY/份。


@dataclass(frozen=True)
class QuoteValue:
    action_date: int  # 原tick上海事件日期YYYYMMDD。
    action_time: int  # 原tick上海事件时刻HHMMSSmmm，保留原毫秒。
    price_cny: float  # 原WT已应用的tick价格，CNY/份。


@dataclass(frozen=True)
class PositionValue:
    flags: int
    raw_position: float
    raw_valid: float
    enum_target: float | None
    first_entry: int
    last_entry: int
    last_exit: int
    actual_quantity: float | None
    pending_quantity: float | None


@dataclass(frozen=True)
class BrokerPositionValue:
    """原券商表的非零方向持仓，单位股/份；不替代策略理论PositionValue。"""
    symbol: str
    is_long: bool
    quantity: float
    sellable: float


@dataclass(frozen=True)
class PendingOrderValue:
    """原WT订单表中的已核自有活动单；身份和可变余量继续归Adapter。"""
    symbol: str  # WT标准代码，来自原订单合约。
    remaining: float  # 本次原表的未成交股/份，正有限值。
    is_buy: bool  # 原委托方向；只作未决责任观察。


@dataclass(frozen=True)
class BrokerObservationValue:
    """P/A各自的接收时间；published_ms仅表示自有副本发布，不延长查询新鲜度。"""
    positions_known: bool
    account_known: bool
    position_revision: int
    position_received_ms: int | None
    account_revision: int
    account_received_ms: int | None
    published_epoch_ms: int
    balance: float | None
    available: float | None
    positions: tuple[BrokerPositionValue, ...]


@dataclass(frozen=True)
class BrokerTradeValue:
    symbol: str
    trade_id: str
    order_id: str
    user_tag: str
    trade_date: int
    is_buy: bool
    trade_time: int
    first_live_revision: int
    received_ms: int
    quantity: float
    price: float
    amount: float
    submission_revision: int = 0


@dataclass(frozen=True)
class BrokerTradesValue:
    """原查询/回报有限事实；成交时间与接收时间分列，不能相互替代。"""
    known: bool
    error: int
    revision: int
    received_ms: int | None
    query_revision: int
    query_received_ms: int | None
    live_revision: int
    published_epoch_ms: int
    trades: tuple[BrokerTradeValue, ...]
    # None=库缺少原提交身份能力或身份投影unknown；0=当前实例尚无已登记委托。
    submission_revision: int | None = None


def _bar(value):
    return BarValue(**{key: getattr(value, key) for key in BarValue.__dataclass_fields__})


class CallbackContext:
    """本次回调的借用门面；只返回冻结值，离开原OS线程或epoch后拒绝调用。"""

    def __init__(self, owner, binding, event):
        self.event, self._owner, self._binding = event, owner, binding
        self._live = True

    def _access(self, kinds=(1, 4)):
        _need(self._live and self._owner._active is self, 'borrow_expired')
        _need(self._owner._thread() == self.event.thread_id, 'wrong_thread')
        _need(self.event.kind in kinds, 'wrong_phase')
        return self._owner._api

    def _code(self, value):
        _need(value in self._binding.read_symbols, 'unknown_symbol')
        return value.encode('ascii')

    @staticmethod
    def _ok(result):
        _need(result == 0, 'native_read_failed' if result == -8 else 'native_operation_failed')

    def facts(self):
        api = self._access();out = Facts();out.size = C.sizeof(out)
        self._ok(api.gh_ms_facts(self.event.epoch, C.byref(out)))
        return FactsValue(out.date, out.time, out.tdate, out.fund_pnl)

    def cash_basis(self, code):
        """同一回调借用原WT现金依据；缺扩展时只撤销资金观察资格。"""
        api=self._access();function=getattr(api,'gh_ms_cash_basis',None)
        if function is None:return None
        out=CashBasis();out.size=C.sizeof(out);out.version=1
        result=function(self.event.epoch,self._code(code),C.byref(out))
        if result==-8:return None
        self._ok(result)
        return CashBasisValue(out.realized_pnl_cny,out.fees_cny,out.average_price_cny)

    def quote(self, code):
        """同epoch复制原WT已应用tick；缺扩展/首tick时返回None。"""
        api=self._access();function=getattr(api,'gh_ms_quote',None)
        if function is None:return None
        out=Quote();out.size=C.sizeof(out);out.version=1
        result=function(self.event.epoch,self._code(code),C.byref(out))
        if result==-8:return None
        self._ok(result)
        return QuoteValue(out.action_date,out.action_time,out.price_cny)

    def price(self, code):
        api = self._access();out = C.c_double()
        self._ok(api.gh_ms_price(self.event.epoch, self._code(code), C.byref(out)))
        return out.value

    def position(self, code):
        api = self._access();out = Position();out.size = C.sizeof(out)
        self._ok(api.gh_ms_position(self.event.epoch, self._code(code), C.byref(out)))
        return PositionValue(out.flags, out.raw_position, out.raw_valid, out.enum_target if out.flags & 2 else None,
                             out.first_entry, out.last_entry, out.last_exit,
                             out.actual_quantity if out.flags & 4 else None,
                             out.pending_quantity if out.flags & 8 else None)

    def bars(self, code, period, count, *, main=False):
        api = self._access()
        _need(period in ('m1', 'd1') and type(count) is int and 1 <= count <= 4096 and type(main) is bool,
              'invalid_bar_request')
        out = (Bar * count)();written = C.c_uint32()
        self._ok(api.gh_ms_bars(self.event.epoch, self._code(code), period.encode('ascii'), count,
                               int(main), out, count, C.byref(written)))
        _need(written.value <= count, 'native_capacity')
        return tuple(_bar(row) for row in out[:written.value])

    def set_targets(self, values):
        api = self._access((4,))
        _need(bool(self._binding.execution_symbols),'target_submission_disabled')
        _need(type(values) is tuple and len(values) == len(self._binding.execution_symbols), 'incomplete_target')
        _need(all(type(row) is tuple and len(row) == 2 for row in values), 'invalid_target')
        _need(all(type(code) is str for code, _ in values), 'invalid_target')
        _need(len({code for code, _ in values}) == len(values)
              and {code for code, _ in values} == set(self._binding.execution_symbols), 'incomplete_target')
        out = (Target * len(values))();readback = (Target * len(values))()
        for index, (code, quantity) in enumerate(values):
            _need(type(quantity) in (int, float) and 0 <= quantity <= 9007199254740900 and math.isfinite(quantity)
                  and quantity % 100 == 0, 'invalid_quantity')
            out[index].symbol = code.encode('ascii');out[index].quantity = quantity
        self._ok(api.gh_ms_set_targets(self.event.epoch, out, len(values), readback, len(values)))
        return tuple((bytes(row.symbol).decode('ascii'), row.quantity) for row in readback)

    def load_quantity_state(self):
        api = self._access()
        _need(self._owner._state_abi == 1, 'state_capability')
        value = C.create_string_buffer(32769);written = C.c_uint32()
        self._ok(api.gh_ms_state_read(self.event.epoch, value, len(value), C.byref(written)))
        _need(written.value <= 32768 and value.raw[written.value] == 0, 'native_capacity')
        return value.raw[:written.value].decode('ascii')

    def store_quantity_state(self, value):
        api = self._access()
        _need(self._owner._state_abi == 1, 'state_capability')
        _need(type(value) is str and 1 <= len(value) <= 32768 and all(32 <= ord(c) < 127 for c in value),
              'invalid_quantity_state')
        raw = value.encode('ascii')
        self._ok(api.gh_ms_state_write(self.event.epoch, raw, len(raw)))

    def broker_observation(self):
        """本次INIT/SCHEDULE读取独立账户观察值；原ctx实际量字段语义保持。"""
        self._access()
        return self._owner.broker_observation()

    def pending_orders(self):
        """复制原WT自有活动订单；禁止策略另建委托状态机。"""
        self._access()
        return self._owner.pending_orders()

    def broker_trades(self):
        """复制原成交事实；旧运行库缺少可选能力时为None，不发起来源查询。"""
        self._access()
        return self._owner.broker_trades()


class CtaRuntime:
    """每进程一次的运行体装配；父owner先验证完整安装并将本进程纳入Job。"""

    def __init__(self, configuration, bindings, *, deadline, attribution=None):
        global _claimed
        _need(type(configuration) is ExecutionProcessConfig and type(bindings) is tuple and 1 <= len(bindings) <= 64)
        _need(all(type(value) is StrategyBinding for value in bindings))
        _need(len({value.strategy_id.lower() for value in bindings}) == len(bindings))
        _need(type(deadline) in (int, float) and math.isfinite(deadline) and time.monotonic() < deadline, 'startup_deadline')
        raw = _read(configuration.configuration, 256 * 1024, clock=time.monotonic, deadline=deadline)
        _need(hashlib.sha256(raw).hexdigest() == configuration.configuration_sha256, 'configuration_identity')
        native = _json(raw)
        _need(native.get('schema_version') == 'guanheng.cta-execution.v1'
              and type(native.get('installation_root')) is str
              and Path(native['installation_root']) == configuration.installation / 'app', 'configuration_identity')
        strategies = native.get('strategies')
        _need(type(strategies) is list and len(strategies) == len(bindings), 'binding_configuration_mismatch')
        _need(all(type(item) is dict and type(item.get('id')) is str
                  and item.get('module') == 'strategies/GuanhengManagedStrategy.dll'
                  and item.get('factory') == 'GuanhengManagedStrategy' and item.get('name') == 'Core'
                  for item in strategies), 'binding_configuration_mismatch')
        _need(len({item['id'] for item in strategies}) == len(strategies)
              and {item['id'] for item in strategies} == {value.strategy_id for value in bindings},
              'binding_configuration_mismatch')
        with _claim_lock:
            _need(not _claimed, 'runtime_already_claimed');_claimed = True
        self.configuration, self.bindings = configuration, bindings
        self._active, self._last_error, self._ran, self._refs = None, None, False, []
        self._running = False  # 原Native调用的动态寿命；金融租约只在原借用回调中授ASA使用。
        root = configuration.installation / 'app'
        expected = dict(configuration.artifacts)
        for name in ('GuanhengCtaRuntime.dll', 'strategies/GuanhengManagedStrategy.dll'):
            data = _read(root / name, 32 * 1024 * 1024, clock=time.monotonic, deadline=deadline)
            _need(hashlib.sha256(data).hexdigest() == expected.get('app/' + name), 'module_identity')
        self._kernel = C.WinDLL('kernel32')
        self._kernel.GetCurrentThreadId.argtypes = [];self._kernel.GetCurrentThreadId.restype = C.c_uint32
        self._controller = self._thread()
        _need(time.monotonic() < deadline, 'startup_deadline')
        self._runtime = C.CDLL(str(root / 'GuanhengCtaRuntime.dll'))
        # 显式共享账户接线仅注册Runtime一次；它向同次实际Managed/Standard传递。
        # 持有引用至run返回及原worker回收，默认单策略路径不要求该可选能力。
        self._attribution = attribution
        if attribution is not None:
            from .account_attribution import AttributionBridge
            _need(type(attribution) is AttributionBridge, 'attribution_binding')
            attribution.register(self._runtime)
            attribution.bind_owner(self)
        self._pending_read=getattr(self._runtime,'gh_cta_pending_orders_read',None)
        if self._pending_read is not None:
            layout=self._runtime.gh_cta_pending_order_layout
            layout.argtypes=[];layout.restype=C.c_uint64
            _need(layout()==C.sizeof(_PendingOrder),'pending_orders_layout')
            self._pending_read.argtypes=[C.POINTER(_PendingOrder),C.c_uint32,C.POINTER(C.c_uint32)]
            self._pending_read.restype=C.c_int32
        extension = getattr(self._runtime, 'gh_cta_broker_abi_version', None)
        self._broker_abi = 0
        if extension is not None:
            extension.argtypes = [];extension.restype = C.c_uint32
            self._broker_abi = int(extension())
            _need(self._broker_abi == 1, 'broker_abi_version')
            layout = self._runtime.gh_cta_broker_layout;layout.argtypes = [C.c_uint32];layout.restype = C.c_uint64
            _need(layout(1) == C.sizeof(_BrokerFacts) and layout(2) == C.sizeof(_BrokerPosition), 'broker_abi_layout')
            read = self._runtime.gh_cta_broker_read
            read.argtypes = [C.POINTER(_BrokerFacts), C.POINTER(_BrokerPosition), C.c_uint32, C.POINTER(C.c_uint32)]
            read.restype = C.c_int32
        extension = getattr(self._runtime,'gh_cta_broker_trades_abi_version',None)
        self._broker_trades_abi=0
        self._broker_trades_v2=False
        if extension is not None:
            extension.argtypes=[];extension.restype=C.c_uint32
            self._broker_trades_abi=int(extension());_need(self._broker_trades_abi==1,'broker_trades_abi')
            layout=self._runtime.gh_cta_broker_trades_layout
            layout.argtypes=[C.c_uint32];layout.restype=C.c_uint64
            _need(layout(1)==C.sizeof(_BrokerTradeFacts) and layout(2)==C.sizeof(_BrokerTrade),'broker_trades_layout')
            read=self._runtime.gh_cta_broker_trades_read
            read.argtypes=[C.POINTER(_BrokerTradeFacts),C.POINTER(_BrokerTrade),C.c_uint32,C.POINTER(C.c_uint32)]
            read.restype=C.c_int32
            read2=getattr(self._runtime,'gh_cta_broker_trades_v2_read',None)
            if read2 is not None:
                _need(layout(3)==C.sizeof(_BrokerTradeFactsV2) and layout(4)==C.sizeof(_BrokerTradeV2),'broker_trades_layout')
                read2.argtypes=[C.POINTER(_BrokerTradeFactsV2),C.POINTER(_BrokerTradeV2),C.c_uint32,C.POINTER(C.c_uint32)]
                read2.restype=C.c_int32;self._broker_trades_v2=True
        _need(time.monotonic() < deadline, 'startup_deadline')
        self._api = api = C.CDLL(str(root / 'strategies/GuanhengManagedStrategy.dll'))
        _need(time.monotonic() < deadline, 'startup_deadline')
        api.gh_ms_layout.argtypes = [C.c_uint32];api.gh_ms_layout.restype = C.c_uint64
        _need(self._runtime.gh_cta_runtime_abi_version() == api.gh_ms_abi_version() == 1, 'abi_version')
        extension = getattr(api, 'gh_ms_state_abi_version', None)
        self._state_abi = 0
        if extension is not None:
            extension.argtypes = [];extension.restype = C.c_uint32
            self._state_abi = int(extension())
            _need(self._state_abi == 1, 'state_abi_version')
        _need(configuration.recovery_mode is None or self._state_abi == 1, 'state_capability')
        for index, value in enumerate((_Config, _Status, Event, Bar, Facts, Position, Target), 1):
            _need(api.gh_ms_layout(index) == C.sizeof(value), 'abi_layout')
        prototypes = {
            'gh_ms_configure': [C.POINTER(_Config), _Callback, C.c_void_p],
            'gh_ms_status': [C.POINTER(_Status)], 'gh_ms_facts': [C.c_uint64, C.POINTER(Facts)],
            'gh_ms_price': [C.c_uint64, C.c_char_p, C.POINTER(C.c_double)],
            'gh_ms_position': [C.c_uint64, C.c_char_p, C.POINTER(Position)],
            'gh_ms_bars': [C.c_uint64, C.c_char_p, C.c_char_p, C.c_uint32, C.c_uint32, C.POINTER(Bar), C.c_uint32, C.POINTER(C.c_uint32)],
            'gh_ms_set_targets': [C.c_uint64, C.POINTER(Target), C.c_uint32, C.POINTER(Target), C.c_uint32]}
        if self._state_abi:
            prototypes.update(gh_ms_state_read=[C.c_uint64, C.POINTER(C.c_char), C.c_uint32, C.POINTER(C.c_uint32)],
                              gh_ms_state_write=[C.c_uint64, C.c_char_p, C.c_uint32])
        if getattr(api,'gh_ms_cash_basis',None) is not None:
            prototypes['gh_ms_cash_basis']=[C.c_uint64,C.c_char_p,C.POINTER(CashBasis)]
        if getattr(api,'gh_ms_quote',None) is not None:
            _need(api.gh_ms_layout(8)==C.sizeof(Quote),'quote_abi_layout')
            prototypes['gh_ms_quote']=[C.c_uint64,C.c_char_p,C.POINTER(Quote)]
        for name, parameters in prototypes.items():
            function = getattr(api, name);function.argtypes = parameters;function.restype = C.c_int32
        if any(not binding.execution_symbols for binding in bindings):
            readonly=getattr(api,'gh_ms_read_only_abi_version',None)
            _need(readonly is not None,'readonly_binding_capability')
            readonly.argtypes=[];readonly.restype=C.c_uint32
            _need(readonly()==1,'readonly_binding_capability')
        configure_v2 = None
        if any(binding.native_config_abi == 2 for binding in bindings):
            version = getattr(api, 'gh_ms_config_v2_abi_version', None)
            layout = getattr(api, 'gh_ms_config_v2_layout', None)
            configure_v2 = getattr(api, 'gh_ms_configure_v2', None)
            _need(version is not None and layout is not None and configure_v2 is not None, 'configuration_v2_capability')
            version.argtypes = [];version.restype = C.c_uint32
            layout.argtypes = [];layout.restype = C.c_uint64
            _need(version() == 2 and layout() == C.sizeof(_ConfigV2), 'configuration_v2_layout')
            configure_v2.argtypes = [C.POINTER(_ConfigV2), _Callback, C.c_void_p]
            configure_v2.restype = C.c_int32
        for binding in bindings:
            _need(time.monotonic() < deadline, 'startup_deadline')
            config_type = _ConfigV2 if binding.native_config_abi == 2 else _Config
            configure = configure_v2 if binding.native_config_abi == 2 else api.gh_ms_configure
            config = config_type();config.size = C.sizeof(config);config.abi_version = binding.native_config_abi
            config.strategy_id = binding.strategy_id.encode('ascii');config.main_symbol = binding.main_symbol.encode('ascii')
            config.read_count = len(binding.read_symbols);config.execution_count = len(binding.execution_symbols)
            for field, values in (('read_symbols', binding.read_symbols), ('execution_symbols', binding.execution_symbols)):
                for index, value in enumerate(values):
                    C.memmove(C.addressof(config) + getattr(config_type, field).offset + index * 64, value.encode('ascii'), len(value))
            callback = _Callback(lambda event, user, value=binding: self._callback(value, event))
            self._refs.append(callback)
            _need(configure(C.byref(config), callback, None) == 0, 'native_configuration')
        _need(time.monotonic() < deadline, 'startup_deadline')

    def _thread(self):
        return int(self._kernel.GetCurrentThreadId())

    def financial_borrowed(self):
        """借用原Native已持有的账户租约，不创建第二个owner。

        原CtaProcess在取得账户mutex后才创建策略/Standard回调；关闭时先回收
        策略及worker再释放mutex。仅这些同步调用栈可访问ASA，后台线程无资格。
        """
        return bool(self._running and ((self._active is not None and
            self._active.event.thread_id == self._thread()) or
            (self._attribution is not None and self._attribution.callback_active)))

    def _callback(self, binding, pointer):
        context = None
        try:
            _need(self._active is None and self._last_error is None, 'callback_overlap')
            raw = pointer.contents
            _need(raw.size == C.sizeof(Event) and raw.kind in (1, 2, 3, 4, 5) and raw.thread_id == self._thread(), 'event_identity')
            event = EventValue(raw.kind, raw.epoch, raw.owner_token, raw.thread_id, raw.ctx_id, raw.date, raw.time, raw.tdate,
                               bytes(raw.symbol).decode('ascii'), bytes(raw.period).decode('ascii'), _bar(raw.bar) if raw.kind == 3 else None)
            context = CallbackContext(self, binding, event);self._active = context
            result = binding.callback(context)
            _need(result is None, 'callback_result')
            return 0
        except BaseException as error:
            if self._last_error is None:
                self._last_error = error
            return -1
        finally:
            if context is not None:
                context._live = False
            self._active = None

    def status(self):
        value = _Status();value.size = C.sizeof(value)
        _need(self._api.gh_ms_status(C.byref(value)) == 0, 'native_status')
        return {key: getattr(value, key) for key in ('configured', 'created', 'destroyed', 'active', 'failure', 'callbacks', 'setters', 'owner_token')}

    def broker_observation(self):
        """复制当前原账户观察；运行前/关闭后Unavailable，旧DLL可选能力明确缺失。"""
        _need(self._broker_abi == 1, 'broker_capability')
        facts = _BrokerFacts();facts.size = C.sizeof(facts);facts.version = 1
        rows = (_BrokerPosition * 4096)();written = C.c_uint32()
        result = self._runtime.gh_cta_broker_read(C.byref(facts), rows, len(rows), C.byref(written))
        _need(result != -2, 'broker_unavailable');_need(result != -5, 'broker_capacity')
        _need(result == 0 and facts.positions_known in (0,1) and facts.account_known in (0,1)
              and written.value <= len(rows), 'broker_read_failed')
        positions = []
        for row in rows[:written.value]:
            code = bytes(row.symbol).decode('ascii')
            _need(0 < len(code) < 64 and all(32 < ord(c) < 127 for c in code)
                  and row.is_long in (0,1) and math.isfinite(row.quantity) and math.isfinite(row.sellable)
                  and row.quantity > 0 and 0 <= row.sellable <= row.quantity, 'broker_position')
            positions.append(BrokerPositionValue(code, bool(row.is_long), row.quantity, row.sellable))
        _need(len({(p.symbol,p.is_long) for p in positions}) == len(positions), 'broker_position')
        if facts.positions_known:
            _need(facts.position_revision > 0 and 0 < facts.position_received_ms <= facts.published_epoch_ms, 'broker_received_time')
        else:
            _need(not positions, 'broker_unknown_positions')
        if facts.account_known:
            _need(facts.account_revision > 0 and 0 < facts.account_received_ms <= facts.published_epoch_ms
                  and math.isfinite(facts.balance) and math.isfinite(facts.available), 'broker_received_time')
        return BrokerObservationValue(bool(facts.positions_known), bool(facts.account_known),
            facts.position_revision, facts.position_received_ms if facts.positions_known else None,
            facts.account_revision, facts.account_received_ms if facts.account_known else None,
            facts.published_epoch_ms, facts.balance if facts.account_known else None,
            facts.available if facts.account_known else None, tuple(positions))

    def pending_orders(self):
        """沿原同次账户发布复制活动单；旧DLL能力缺失保持明确。"""
        _need(self._pending_read is not None,'pending_orders_capability')
        rows=(_PendingOrder*4096)();written=C.c_uint32()
        result=self._pending_read(rows,len(rows),C.byref(written))
        _need(result==0 and written.value<=len(rows),'pending_orders_read')
        values=[]
        for row in rows[:written.value]:
            code=bytes(row.symbol).decode('ascii')
            _need(0<len(code)<64 and all(32<ord(c)<127 for c in code)
                  and row.is_buy in (0,1) and math.isfinite(row.remaining) and row.remaining>0,'pending_order_value')
            values.append(PendingOrderValue(code,row.remaining,bool(row.is_buy)))
        return tuple(values)

    def broker_trades(self):
        if not self._broker_trades_abi:return None
        header=_BrokerTradeFactsV2() if self._broker_trades_v2 else _BrokerTradeFacts()
        facts=header.facts if self._broker_trades_v2 else header
        facts.size=C.sizeof(header);facts.version=2 if self._broker_trades_v2 else 1
        rows=((_BrokerTradeV2 if self._broker_trades_v2 else _BrokerTrade)*4096)();written=C.c_uint32()
        read=self._runtime.gh_cta_broker_trades_v2_read if self._broker_trades_v2 else self._runtime.gh_cta_broker_trades_read
        result=read(C.byref(header),rows,len(rows),C.byref(written))
        _need(result!=-2,'broker_trades_unavailable');_need(result!=-5,'broker_trades_capacity')
        _need(result==0 and facts.known in (0,1) and facts.error in (0,1,2,3)
              and facts.live_revision<=facts.revision and written.value<=len(rows),'broker_trades_read')
        def text(row,key,empty=False):
            value=bytes(getattr(row,key)).decode('ascii')
            _need((empty or value) and len(value)<64 and all(32<=ord(c)<127 for c in value),'broker_trade_identity')
            return value
        submission_revision=None
        if self._broker_trades_v2:
            _need(header.origins_known in (0,1) and header.reserved==0,'broker_trade_origin')
            if header.origins_known:submission_revision=header.submission_revision
        values=[]
        for item in rows[:written.value]:
            row=item.trade if self._broker_trades_v2 else item
            origin=item.submission_revision if self._broker_trades_v2 else 0
            _need((submission_revision is not None and origin<=submission_revision) or not origin,'broker_trade_origin')
            _need(row.is_buy in (0,1) and 0<=row.first_live_revision<=facts.live_revision
                  and 0<row.received_ms<=facts.published_epoch_ms
                  and 19000101<=row.trade_date<=99991231 and row.trade_time<240000000
                  and all(math.isfinite(v) for v in (row.quantity,row.price,row.amount))
                  and row.quantity>0 and row.price>0 and row.amount>=0,'broker_trade_value')
            values.append(BrokerTradeValue(text(row,'symbol'),text(row,'trade_id'),text(row,'order_id'),
                text(row,'user_tag',True),row.trade_date,bool(row.is_buy),row.trade_time,row.first_live_revision,
                row.received_ms,row.quantity,row.price,row.amount,origin))
        _need(len({v.trade_id for v in values})==len(values),'broker_trade_identity')
        if facts.known:
            _need(facts.error==0 and facts.query_revision>0 and 0<facts.query_received_ms<=facts.published_epoch_ms
                  and 0<facts.received_ms<=facts.published_epoch_ms,'broker_trades_time')
        else:_need(not values,'broker_trades_unknown')
        return BrokerTradesValue(bool(facts.known),facts.error,facts.revision,facts.received_ms or None,
            facts.query_revision,facts.query_received_ms or None,facts.live_revision,facts.published_epoch_ms,tuple(values),submission_revision)

    def run(self, control_directory, control_id):
        _need(not self._ran, 'runtime_already_run')
        _need(self._thread() == self._controller, 'wrong_thread')
        directory = Path(control_directory);_need(directory.is_absolute(), 'control_directory');_inspect(directory, directory=True)
        _need(type(control_id) is str and str(UUID(control_id)) == control_id, 'control_identity')
        self._ran = True
        config = self.configuration
        arguments = [str(config.pythonw), '--config', str(config.configuration), '--control', str(directory),
                     '--control-id', control_id, '--config-sha256', config.configuration_sha256]
        self._runtime.gh_cta_run.argtypes = [C.c_uint32, C.POINTER(C.c_wchar_p), C.c_void_p, C.c_void_p]
        self._runtime.gh_cta_run.restype = C.c_int32
        values = (C.c_wchar_p * len(arguments))(*arguments)
        # health直接使用原生原子入口；运行期间不依赖Python控制线程取得GIL。
        self._running = True
        try:
            result = int(self._runtime.gh_cta_run(len(arguments), values, C.cast(self._api.gh_ms_health, C.c_void_p), None))
        finally:
            self._running = False
        if self._last_error is None and self._attribution is not None:
            self._last_error = self._attribution.failure
        return result
