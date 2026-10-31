"""独占子进程内的原生CTA回测边界；父Job/绝对截止由外层owner负责。

不热卸载、不在callback中停止原生。目标枚举是pending覆盖投影，total对新证券
也可能回显pending；本层完整保留这些口径，不制造成交或撤销确认。
"""
from __future__ import annotations

import ctypes as C
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
from threading import Lock, current_thread, get_ident
from typing import Callable


class PorterError(RuntimeError):
    """原生边界准入或协议错误。"""


class AdmissionError(PorterError):
    """原生代码执行前拒绝不受支持的输入或ABI。"""


def validate_backtest_window(start: int, end: int) -> None:
    """纯准入：上海回放YYYYMMDDHHMM整数及有序窗口；拒绝时抛AdmissionError。"""
    for value in (start, end):
        if type(value) is not int or len(str(value)) != 12:
            raise AdmissionError("回放时间需要YYYYMMDDHHMM整数")
        try:
            datetime.strptime(str(value), "%Y%m%d%H%M")
        except ValueError as exc:
            raise AdmissionError("回放时间非法") from exc
    if start > end:
        raise AdmissionError("回放范围倒序")


class PhaseError(PorterError):
    """当前线程、阶段或调用栈不允许此操作。"""


class PorterBlocked(PorterError):
    """原生callback/运行失败已锁存，本进程不得再产生完成结果。"""


class IncompleteBatch(PorterBlocked):
    """逐证券提交或完整读回失败；部分原生状态须由外层隔离。"""


@dataclass(frozen=True, slots=True)
class Failure:
    code: str
    phase: str
    reason: str


def _finite(value):
    if type(value) not in (int, float):
        raise AdmissionError("数值类型不合格")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise AdmissionError("数值不能表示为double") from exc
    if not math.isfinite(result):
        raise AdmissionError("数值必须有限")
    return result


def _quantity(value):
    result = _finite(value)
    if result < 0 or not result.is_integer() or (type(value) is int and int(result) != value):
        raise AdmissionError("数量必须是非负且double精确表示的整数")
    return result


def _text(value, maximum, *, identifier=False):
    if type(value) is not str or "\0" in value:
        raise AdmissionError("字符串类型或NUL不合格")
    if len(value) > maximum:
        raise AdmissionError("字符串超过原生字节预算")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise AdmissionError("字符串不是有效UTF8") from exc
    if len(encoded) > maximum or (identifier and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,30}", value)):
        raise AdmissionError("字符串超过原生缓冲区或标识不合格")
    return encoded


def _symbol(value):
    _text(value, 31)
    if not re.fullmatch(r"(?:SSE|SZSE)\.(?:STK|ETF)\.[0-9]{6}", value):
        raise AdmissionError("当前证券profile仅支持显式SSE/SZSE.STK/ETF六位代码")
    return value


def _trusted_bytes(path, expected, maximum):
    path = Path(path)
    if not path.is_absolute() or type(expected) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise AdmissionError("需要绝对路径及外部可信SHA256")
    if not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise AdmissionError("制品文件缺失或超过预算")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if not 0 < len(data) <= maximum:
        raise AdmissionError("制品读取超过预算")
    if hashlib.sha256(data).hexdigest() != expected:
        raise AdmissionError("制品内容身份变化")
    return path.resolve(), data


@dataclass(frozen=True, slots=True)
class Bar:
    date: int
    time: int
    open: float
    high: float
    low: float
    close: float
    settle: float
    money: float
    vol: float
    hold: float = 0.0
    add: float = 0.0
    reserve: int = 0

    def __post_init__(self):
        for name, maximum in (("date", 0xffffffff), ("reserve", 0xffffffff), ("time", 0xffffffffffffffff)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= maximum:
                raise AdmissionError("bar整数布局越界")
        try:
            if len(str(self.date)) != 8:
                raise ValueError()
            datetime.strptime(str(self.date), "%Y%m%d")
        except ValueError as exc:
            raise AdmissionError("bar日期非法") from exc
        for name in ("open", "high", "low", "close", "settle", "money", "vol", "hold", "add"):
            object.__setattr__(self, name, _finite(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class Prefix:
    symbol: str
    period: str
    bars: tuple[Bar, ...]


@dataclass(frozen=True, slots=True)
class Target:
    symbol: str
    quantity: float

    def __post_init__(self):
        _symbol(self.symbol)
        object.__setattr__(self, "quantity", _quantity(self.quantity))


@dataclass(frozen=True, slots=True)
class Position:
    """total/valid是原接口读数；首次pending可回显。entry仅指当前明细，平仓归0。"""
    symbol: str
    total: float
    valid: float
    first_entry: int
    last_entry: int


@dataclass(frozen=True, slots=True)
class Funds:
    """原flag0..3；net=realized+dynamic-fees，不含初始本金或现金购买力。"""
    net: float
    realized: float
    dynamic: float
    fees: float


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    cwd: Path
    output: Path
    storage: Path
    sessions: Path
    commodities: Path
    contracts: Path
    holidays: Path
    fees: Path
    start: int
    end: int
    name: str


@dataclass(frozen=True, slots=True)
class Callbacks:
    on_init: Callable[[BacktestPorter], None]
    on_calculate: Callable[[BacktestPorter, int, int], None]
    on_bar: Callable[[BacktestPorter, str, str, Bar], None]


class _NativeBar(C.Structure):
    _pack_ = 8
    _fields_ = [("date", C.c_uint32), ("reserve", C.c_uint32), ("time", C.c_uint64)] + [
        (name, C.c_double) for name in ("open", "high", "low", "close", "settle", "money", "vol", "hold", "add")]


_H, _N, _T = C.c_ulong, C.c_uint32, C.c_char_p
_INIT = C.CFUNCTYPE(None, _H)
_TICK = C.CFUNCTYPE(None, _H, _T, C.c_void_p)
_CALC = C.CFUNCTYPE(None, _H, _N, _N)
_BAR = C.CFUNCTYPE(None, _H, _T, _T, C.POINTER(_NativeBar))
_SESSION = C.CFUNCTYPE(None, _H, _N, C.c_bool)
_CONDITION = C.CFUNCTYPE(None, _H, _T, C.c_double, C.c_double, _T)
_BARS = C.CFUNCTYPE(None, _H, _T, _T, C.POINTER(_NativeBar), _N, C.c_bool)
_POSITIONS = C.CFUNCTYPE(None, _H, _T, C.c_double, C.c_bool)
_EVENT = C.CFUNCTYPE(None, _N, _N, _N)
_LOAD = C.CFUNCTYPE(C.c_bool, _T, _T)
_FACTORS = C.CFUNCTYPE(C.c_bool, _T)
_TICKS_LOAD = C.CFUNCTYPE(C.c_bool, _T, _N)
_PROTOTYPES = {
    "register_evt_callback": ([_EVENT], None),
    "register_cta_callbacks": ([_INIT, _TICK, _CALC, _BAR, _SESSION, _CALC, _CONDITION], None),
    "register_ext_data_loader": ([_LOAD, _LOAD, _FACTORS, _TICKS_LOAD, C.c_bool], None),
    "feed_raw_bars": ([C.POINTER(_NativeBar), _N], None),
    "init_backtest": ([_T, C.c_bool, _T], None), "config_backtest": ([_T, C.c_bool], None),
    "init_cta_mocker": ([_T, C.c_int, C.c_bool, C.c_bool, C.c_bool, C.c_bool], _H),
    "cta_get_bars": ([_H, _T, _T, _N, C.c_bool, _BARS], _N),
    "cta_sub_bar_events": ([_H, _T, _T], None), "cta_get_price": ([_T], C.c_double),
    "cta_get_fund_data": ([_H, C.c_int], C.c_double),
    "cta_get_position": ([_H, _T, C.c_bool, _T], C.c_double),
    "cta_get_all_position": ([_H, _POSITIONS], None),
    "cta_get_first_entertime": ([_H, _T], C.c_uint64),
    "cta_get_last_entertime": ([_H, _T], C.c_uint64),
    "cta_set_position": ([_H, _T, C.c_double, _T, C.c_double, C.c_double], None),
    "cta_save_userdata": ([_H, _T, _T], None),
    "cta_load_userdata": ([_H, _T, _T], _T),
    "run_backtest": ([C.c_bool, C.c_bool], None), "release_backtest": ([], None),
}
_PROCESS_LOCK = Lock()
_PROCESS_KEEPERS = []  # 保留CDLL及全部callback到进程退出；release不释放此租约。


def _reason(exc):
    try:
        return f"{type(exc).__name__}: {exc}"[:512]
    except BaseException:
        return "异常诊断字符串不可用"


def _current_cwd():
    """先核原框架实际255字节_getcwd调用，避免仅按resolved路径长度推断。"""
    runtime = C.CDLL("ucrtbase.dll")
    runtime._getcwd.argtypes = [C.POINTER(C.c_char), C.c_int]
    runtime._getcwd.restype = C.c_void_p
    buffer = C.create_string_buffer(255)
    if not runtime._getcwd(buffer, len(buffer)):
        raise AdmissionError("当前目录超过原_getcwd接口或编码边界")
    try:
        actual = Path(buffer.value.decode("mbcs", "strict")).resolve()
    except UnicodeError as exc:
        raise AdmissionError("原_getcwd字符编码不合格") from exc
    if actual != Path.cwd().resolve():
        raise AdmissionError("原_getcwd与Python当前目录身份不一致")
    return actual


def _admit_pe(data):
    """在LoadLibrary之前核PE32+ AMD64及所用非forwarded C导出。"""
    try:
        if data[:2] != b"MZ":
            raise ValueError()
        pe = struct.unpack_from("<I", data, 60)[0]
        if data[pe:pe + 4] != b"PE\0\0":
            raise ValueError()
        machine, count = struct.unpack_from("<HH", data, pe + 4)
        optional_size = struct.unpack_from("<H", data, pe + 20)[0]
        optional = pe + 24
        if machine != 0x8664 or not 1 <= count <= 96 or optional_size < 120 or struct.unpack_from("<H", data, optional)[0] != 0x20b:
            raise ValueError()
        export, export_size = struct.unpack_from("<II", data, optional + 112)
        table = optional + optional_size

        def offset(rva, length):
            for index in range(count):
                size, address, raw_size, raw = struct.unpack_from("<IIII", data, table + index * 40 + 8)
                if address <= rva and rva + length <= address + min(size, raw_size):
                    result = raw + rva - address
                    if result + length <= len(data):
                        return result
            raise ValueError()

        directory = offset(export, 40)
        functions, names, function_table, name_table, ordinals = struct.unpack_from("<IIIII", data, directory + 20)
        if not 1 <= names <= 4096 or not names <= functions <= 4096:
            raise ValueError()
        found = set()
        for i in range(names):
            name_rva = struct.unpack_from("<I", data, offset(name_table + 4 * i, 4))[0]
            start = offset(name_rva, 1)
            end = data.find(b"\0", start, min(start + 256, len(data)))
            if end < start:
                raise ValueError()
            name = data[start:end].decode("ascii")
            if name in _PROTOTYPES:
                ordinal = struct.unpack_from("<H", data, offset(ordinals + 2 * i, 2))[0]
                if ordinal >= functions:
                    raise ValueError()
                entry = struct.unpack_from("<I", data, offset(function_table + 4 * ordinal, 4))[0]
                if not entry or export <= entry < export + export_size:
                    raise ValueError()
                found.add(name)
        if found != set(_PROTOTYPES):
            raise ValueError()
    except (ValueError, struct.error, UnicodeError) as exc:
        raise AdmissionError("DLL的AMD64/PE32+或必需C导出不合格") from exc


def _admit_layout(data):
    """可信SHA绑定的真实header编译probe；Python布局仅作交叉检查。"""
    try:
        proof = json.loads(data)
        layout = proof["backtest"]["result"]
        macros = proof["macros"]["result"]
        expected = {"pointer": 8, "bool": 1, "CtxHandler": 4, "unsigned_long": 4,
                    "WtUInt32": 4, "WtUInt64": 8, "double": 8}
        if any(type(layout[k]) is not int or layout[k] != v for k, v in expected.items()):
            raise ValueError()
        if macros != {"EXPORT_FLAG": "__declspec(dllexport)", "PORTER_FLAG": "_cdecl"}:
            raise ValueError()
        offsets = {"date": 0, "reserve_": 4, "time": 8, "open": 16, "high": 24, "low": 32,
                   "close": 40, "settle": 48, "money": 56, "vol": 64, "hold": 72, "add": 80}
        if layout["bar"]["size"] != 88 or layout["bar"]["align"] != 8 or any(layout["bar"]["offsets"][k] != v for k, v in offsets.items()):
            raise ValueError()
        if C.sizeof(_NativeBar) != 88 or C.alignment(_NativeBar) != 8 or C.sizeof(_H) != 4 or C.sizeof(C.c_void_p) != 8 or C.sizeof(C.c_bool) != 1:
            raise ValueError()
        for name, _ in _NativeBar._fields_:
            if getattr(_NativeBar, name).offset != offsets["reserve_" if name == "reserve" else name]:
                raise ValueError()
    except (KeyError, ValueError, TypeError, RecursionError) as exc:
        raise AdmissionError("真实header ABI证据与当前Python布局不匹配") from exc


class BacktestPorter:
    """每进程一次、owner线程唯一。on_init(p), on_bar(p,symbol,period,bar),
    on_calculate(p,date,minute)同步运行；loader只返回有界tuple[Bar]。

    abi_probe及SHA由受信构建owner提供，绑定真实原header编译结果；本DLL没有
    layout导出，本层不能从任意DLL自动证明其内部结构布局。外层仍须绑定制品谱系。
    """

    def __init__(self, library: Path, library_sha256: str, abi_probe: Path, abi_probe_sha256: str, *,
                 symbols: tuple[str, ...], execution_symbols: tuple[str, ...], loader: Callable[[str, str], tuple[Bar, ...]],
                 callbacks: Callbacks, max_bars: int = 32768):
        if os.name != "nt" or C.sizeof(C.c_void_p) != 8:
            raise AdmissionError("仅授Windows x64原生ABI")
        if type(symbols) is not tuple or not 1 <= len(symbols) <= 16 or any(type(s) is not str for s in symbols) or len(set(symbols)) != len(symbols):
            raise AdmissionError("读取证券必须为1..16个不同标识的tuple")
        for symbol in symbols:
            _symbol(symbol)
        if (type(execution_symbols) is not tuple or len(execution_symbols) > 8
                or any(type(s) is not str for s in execution_symbols)
                or len(set(execution_symbols)) != len(execution_symbols)
                or not set(execution_symbols) <= set(symbols)):
            raise AdmissionError("执行证券必须为读取集合的显式不同子集，最多8个")
        if type(max_bars) is not int or not 1 <= max_bars <= 32768:
            raise AdmissionError("历史条数预算必须为1..32768")
        if not isinstance(callbacks, Callbacks) or not all(callable(c) for c in (loader, callbacks.on_init, callbacks.on_bar, callbacks.on_calculate)):
            raise AdmissionError("需要显式loader和三个callback")
        library, binary = _trusted_bytes(library, library_sha256, 128 * 1024 * 1024)
        _admit_pe(binary)
        _, proof = _trusted_bytes(abi_probe, abi_probe_sha256, 1024 * 1024)
        _admit_layout(proof)
        _current_cwd()
        self._owner, self._symbols, self._max_bars = get_ident(), symbols, max_bars
        self._owner_thread = current_thread()
        self._execution_symbols = execution_symbols
        self._loader, self._user = loader, callbacks
        self._state, self._phase, self._ctx = "created", "idle", 0
        self._stack, self._active_user = [], False
        self._failure, self._main, self._end_seen = None, None, False
        self._counts = {"init": 0, "bar": 0, "calculate": 0, "calc_done": 0}
        self._strong = []
        self._bar_sink, self._position_sink = None, None
        with _PROCESS_LOCK:
            if _PROCESS_KEEPERS:
                raise PhaseError("每个进程只能创建一个Porter，release后仍须退出进程")
            _PROCESS_KEEPERS.append(self)
        self._dll_directory = os.add_dll_directory(str(library.parent))
        self._native = C.CDLL(str(library))
        for name, (arguments, result) in _PROTOTYPES.items():
            fn = getattr(self._native, name)
            fn.argtypes, fn.restype = arguments, result
        if hashlib.sha256(library.read_bytes()).hexdigest() != library_sha256:
            self._block("admission", "DLL加载期间身份变化")
            raise AdmissionError("DLL加载期间身份变化")
        self._make_callbacks()

    @property
    def failure(self) -> Failure | None:
        return self._failure

    @property
    def symbols(self) -> tuple[str, ...]:
        return self._symbols

    @property
    def execution_symbols(self) -> tuple[str, ...]:
        return self._execution_symbols

    @property
    def max_bars(self) -> int:
        return self._max_bars

    @property
    def callback_counts(self) -> tuple[tuple[str, int], ...]:
        return tuple(self._counts.items())

    def _owner_only(self):
        if get_ident() != self._owner or current_thread() is not self._owner_thread:
            raise PhaseError("原生上下文只允许owner线程访问")

    def _block(self, code, reason):
        if self._failure is None:
            self._failure = Failure(code, self._phase, reason[:512] if type(reason) is str else "原生边界失败")

    def _healthy(self):
        if self._failure is not None:
            raise PorterBlocked(str(self._failure))

    def _gate(self, phases=("init", "calculate", "after_run")):
        self._owner_only()
        self._healthy()
        if self._state not in ("running", "finished") or self._phase not in phases or self._stack not in ([], ["run_backtest"]):
            raise PhaseError("当前阶段或原生重入栈不允许此操作")
        if self._stack and not self._active_user:
            raise PhaseError("原生内部callback不能重入用户API")

    def _call(self, name, *args):
        self._owner_only()
        self._stack.append(name)
        try:
            return getattr(self._native, name)(*args)
        finally:
            self._stack.pop()

    def _number(self, name, *args):
        try:
            return _finite(self._call(name, *args))
        except AdmissionError as exc:
            self._block("protocol", _reason(exc))
            raise PorterBlocked(str(self._failure)) from exc

    def _callback(self, phase, function, *args):
        old_phase, old_active = self._phase, self._active_user
        try:
            self._owner_only()
            if self._stack != ["run_backtest"]:
                raise PhaseError("非预期的用户callback重入")
            if self._failure is not None:
                return
            self._phase, self._active_user = phase, True
            function(self, *args)
        except BaseException as exc:
            self._block("callback", _reason(exc))
        finally:
            self._phase, self._active_user = old_phase, old_active

    def _internal(self, phase, function, *args):
        old_phase, old_active = self._phase, self._active_user
        try:
            self._owner_only()
            self._phase, self._active_user = phase, False
            return function(*args)
        except BaseException as exc:
            self._block("protocol", _reason(exc))
            return False
        finally:
            self._phase, self._active_user = old_phase, old_active

    def _key(self, symbol, period):
        if symbol not in self.symbols or period not in ("m1", "d1"):
            raise AdmissionError("证券或周期未准入")
        return symbol.encode(), period.encode()

    def _make_callbacks(self):
        def initialize(ctx):
            if ctx != self._ctx:
                self._block("protocol", "init ctx不匹配")
                return
            self._counts["init"] += 1
            self._callback("init", self._user.on_init)

        def bar(ctx, symbol, period, pointer):
            def copy():
                if ctx != self._ctx or not pointer:
                    raise PorterError("bar ctx/指针不匹配")
                code, interval = symbol.decode("ascii"), period.decode("ascii")
                self._key(code, interval)
                native = _NativeBar.from_buffer_copy(C.string_at(pointer, 88))
                return code, interval, Bar(**{name: getattr(native, name) for name, _ in _NativeBar._fields_})
            copied = self._internal("bar_copy", copy)
            if copied is not False:
                self._counts["bar"] += 1
                self._callback("bar", self._user.on_bar, *copied)

        def calculate(ctx, date, minute):
            if ctx != self._ctx:
                self._block("protocol", "calculate ctx不匹配")
                return
            self._counts["calculate"] += 1
            self._callback("calculate", self._user.on_calculate, date, minute)

        def event(kind, date, minute):
            def copy():
                if kind == 5:
                    self._end_seen = True
            self._internal("event", copy)

        def final_loader(symbol, period):
            def feed():
                if self._stack != ["run_backtest", "cta_get_bars"]:
                    raise PhaseError("final loader仅允许get_bars的受控嵌套")
                self._healthy()
                code, interval = symbol.decode("ascii"), period.decode("ascii")
                self._key(code, interval)
                rows = self._loader(code, interval)
                if type(rows) is not tuple or len(rows) > self.max_bars or any(type(row) is not Bar for row in rows):
                    raise AdmissionError("loader必须返回有界immutable Bar tuple")
                if not rows:
                    # 原cacheFinalBarsFromLoader对success+0会访问bars[0]；空源走失败/0返回。
                    return False
                keys = [row.date if interval == "d1" else row.time for row in rows]
                if any(a >= b for a, b in zip(keys, keys[1:])):
                    raise AdmissionError("loader时间重复或倒序")
                if interval == "m1" and any(row.time // 10000 + 19900000 != row.date or row.time % 100 >= 60 or row.time % 10000 // 100 >= 24 for row in rows):
                    raise AdmissionError("loader分钟编码不合格")
                block = (_NativeBar * len(rows))()
                for i, row in enumerate(rows):
                    for name, _ in _NativeBar._fields_:
                        setattr(block[i], name, getattr(row, name))
                self._call("feed_raw_bars", block, len(rows))
                return True
            return bool(self._internal("loader", feed))

        def calc_done(*unused):
            self._internal("calc_done", lambda: self._counts.__setitem__("calc_done", self._counts["calc_done"] + 1))

        def ignored(*unused):
            self._internal("ignored", lambda: None)

        def bars_sink(*values):
            if self._bar_sink is None:
                self._block("protocol", "bars callback超出同步借用期")
            else:
                self._internal("bars_dispatch", self._bar_sink, *values)

        def positions_sink(*values):
            if self._position_sink is None:
                self._block("protocol", "position callback超出同步借用期")
            else:
                self._internal("positions_dispatch", self._position_sink, *values)

        self._strong = [_INIT(initialize), _TICK(ignored), _CALC(calculate), _BAR(bar), _SESSION(ignored),
                        _CALC(calc_done), _CONDITION(ignored), _EVENT(event), _LOAD(final_loader),
                        _BARS(bars_sink), _POSITIONS(positions_sink)]

    def configure(self, config: BacktestConfig):
        """只生成CTA配置；文件内容/来源/恢复身份的完整准入仍由外层owner承担。"""
        self._owner_only()
        self._healthy()
        if self._state != "created" or self._stack or not isinstance(config, BacktestConfig):
            raise PhaseError("configure只允许创建后调用一次")
        _text(config.name, 31, identifier=True)
        paths = {name: Path(getattr(config, name)) for name in ("cwd", "output", "storage", "sessions", "commodities", "contracts", "holidays", "fees")}
        if any(not path.is_absolute() for path in paths.values()) or paths["cwd"].resolve() != Path.cwd().resolve():
            raise AdmissionError("所有配置路径必须绝对且CWD同身份")
        cwd = _current_cwd()
        try:
            encoded = str(cwd).encode("mbcs", "strict")
            if len(encoded) >= 255 or encoded.decode("mbcs") != str(cwd):
                raise ValueError()
        except (UnicodeError, ValueError) as exc:
            raise AdmissionError("CWD超过原_getcwd接口或字符编码边界") from exc
        output, storage = paths["output"].resolve(), paths["storage"].resolve()
        if output == storage or output.is_relative_to(storage) or storage.is_relative_to(output):
            raise AdmissionError("输出与fallback存储需要互不嵌套的独立目录")
        for name in ("output", "storage"):
            path = paths[name].resolve()
            if path == cwd or not path.is_relative_to(cwd) or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
                raise AdmissionError("输出及fallback存储需要独立CWD下的空目录")
            path.mkdir(parents=True, exist_ok=True)
        if any(not paths[name].is_file() for name in ("sessions", "commodities", "contracts", "holidays", "fees")):
            raise AdmissionError("显式基础资料文件缺失")
        validate_backtest_window(config.start, config.end)
        payload = {"env": {"mocker": "cta"}, "notifier": {"active": False}, "replayer": {
            "basefiles": {key: str(paths[name]) for key, name in (("session", "sessions"), ("commodity", "commodities"), ("contract", "contracts"), ("holiday", "holidays"))},
            "mode": "csv", "path": str(paths["storage"]), "stime": config.start, "etime": config.end,
            "tick": False, "fees": str(paths["fees"])}}
        logging = {"root": {"async": False, "level": "warn", "sinks": [{"type": "basic_file_sink", "filename": str(paths["output"] / "native.log"), "pattern": "%v", "truncate": True}]}}
        try:
            self._call("register_evt_callback", self._strong[7])
            self._call("register_cta_callbacks", *self._strong[:7])
            self._call("register_ext_data_loader", self._strong[8], _LOAD(), _FACTORS(), _TICKS_LOAD(), False)
            self._call("init_backtest", json.dumps(logging).encode(), False, str(paths["output"]).encode())
            self._call("config_backtest", json.dumps(payload).encode(), False)
            self._ctx = self._call("init_cta_mocker", config.name.encode(), 0, False, True, False, False)
            if not self._ctx:
                raise PorterError("原生ctx创建失败")
            self._state = "configured"
        except BaseException as exc:
            self._block("configuration", _reason(exc))
            raise PorterBlocked(str(self._failure)) from exc

    def get_bars(self, symbol: str, period: str, count: int, *, main: bool = False) -> Prefix:
        self._gate(("init", "calculate"))
        code, interval = self._key(symbol, period)
        if type(count) is not int or not 1 <= count <= self.max_bars or type(main) is not bool:
            raise AdmissionError("bars预算或main标记不合格")
        if main:
            if self._main not in (None, (symbol, period)) or (self._main is None and self._phase != "init"):
                raise PhaseError("主线只能在init登记一次")
            self._main = (symbol, period)
        blocks, chunks = [], []

        def receive(ctx, got_symbol, got_period, pointer, length, last):
            def copy():
                if ctx != self._ctx or got_symbol != code or got_period != interval or sum(c[0] for c in chunks) + length > count:
                    raise PorterError("bars身份或总量不匹配")
                if chunks and chunks[-1][1]:
                    raise PorterError("isLast之后仍有block")
                if length and not pointer:
                    raise PorterError("非空bars缺指针")
                blocks.append(C.string_at(pointer, length * 88) if length else b"")
                chunks.append((length, bool(last)))
            self._internal("bars_copy", copy)

        self._bar_sink = receive
        try:
            returned = self._call("cta_get_bars", self._ctx, code, interval, count, main, self._strong[9])
        finally:
            self._bar_sink = None
        self._healthy()
        raw = b"".join(blocks)
        if returned != sum(c[0] for c in chunks) or returned * 88 != len(raw) or (chunks and not chunks[-1][1]) or (returned and not chunks):
            self._block("protocol", "bars返回量/count/isLast不一致")
            raise PorterBlocked(str(self._failure))
        values = []
        try:
            for offset in range(0, len(raw), 88):
                bar = _NativeBar.from_buffer_copy(raw[offset:offset + 88])
                values.append(Bar(**{name: getattr(bar, name) for name, _ in _NativeBar._fields_}))
        except BaseException as exc:
            self._block("protocol", _reason(exc))
            raise PorterBlocked(str(self._failure)) from exc
        return Prefix(symbol, period, tuple(values))

    def subscribe_bars(self, symbol: str, period: str):
        self._gate(("init",))
        self._call("cta_sub_bar_events", self._ctx, *self._key(symbol, period))

    def get_price(self, symbol: str) -> float:
        self._gate()
        self._key(symbol, "m1")
        return self._number("cta_get_price", symbol.encode())

    def funds(self) -> Funds:
        self._gate()
        return Funds(*(self._number("cta_get_fund_data", self._ctx, flag) for flag in range(4)))

    def position(self, symbol: str) -> Position:
        self._gate()
        self._key(symbol, "m1")
        code = symbol.encode()
        total = self._number("cta_get_position", self._ctx, code, False, b"")
        valid = self._number("cta_get_position", self._ctx, code, True, b"")
        first = self._call("cta_get_first_entertime", self._ctx, code)
        last = self._call("cta_get_last_entertime", self._ctx, code)
        return Position(symbol, total, valid, first, last)

    def load_userdata(self, key: str) -> str:
        """复制原策略用户值；只读回本profile产生的至多32KiB ASCII状态。"""
        self._gate(("init", "calculate", "after_run"))
        encoded = _text(key, 31, identifier=True)
        raw = self._call("cta_load_userdata", self._ctx, encoded, b"")
        if type(raw) is not bytes or len(raw) > 32768 or not raw.isascii():
            self._block("protocol", "原生用户状态超出ASCII或容量合同")
            raise PorterBlocked(str(self._failure))
        return raw.decode("ascii")

    def store_userdata(self, key: str, value: str) -> None:
        """原接口保存并立即核读；磁盘保存由原CtaMocker正常完成负责。"""
        self._gate(("calculate",))
        encoded_key, encoded_value = _text(key, 31, identifier=True), _text(value, 32768)
        if not value.isascii():
            raise AdmissionError("原生用户状态需要ASCII")
        self._call("cta_save_userdata", self._ctx, encoded_key, encoded_value)
        if self.load_userdata(key) != value:
            self._block("protocol", "原生用户状态保存读回失配")
            raise PorterBlocked(str(self._failure))

    def targets(self) -> tuple[tuple[str, float], ...]:
        """原get_all_position合并投影，包含pending，不是实际成交集合。"""
        self._gate()
        rows, ended = [], []

        def receive(ctx, symbol, quantity, last):
            def copy():
                if ctx != self._ctx or ended:
                    raise PorterError("目标枚举身份或结束标志不匹配")
                value = _finite(quantity)
                code = symbol.decode("ascii")
                if last:
                    if code or value != 0:
                        raise PorterError("目标枚举结束帧非法")
                    ended.append(True)
                else:
                    if code not in self.symbols or len(rows) >= len(self.symbols) or any(c == code for c, _ in rows):
                        raise PorterError("目标枚举证券重复或越界")
                    rows.append((code, value))
            self._internal("targets_copy", copy)

        self._position_sink = receive
        try:
            self._call("cta_get_all_position", self._ctx, self._strong[10])
        finally:
            self._position_sink = None
        self._healthy()
        if ended != [True]:
            self._block("protocol", "目标枚举缺少唯一末帧")
            raise PorterBlocked(str(self._failure))
        return tuple(sorted(rows))

    def submit_targets(self, vector: tuple[Target, ...], tag: str = "") -> tuple[tuple[str, float], ...]:
        """完整预校验后有限逐证券提交、完整读回。失败锁存incomplete，无撤销/回滚。"""
        self._gate(("calculate",))
        if not self.execution_symbols:
            raise PhaseError("只读profile没有执行证券或提交能力")
        encoded_tag = _text(tag, 31)
        if any(c in tag for c in ('"', ',', '\r', '\n')):
            raise AdmissionError("tag不能破坏原生CSV字段边界")
        if type(vector) is not tuple or any(type(row) is not Target for row in vector):
            raise AdmissionError("目标需要immutable Target tuple")
        if len(vector) != len(self.execution_symbols) or {row.symbol for row in vector} != set(self.execution_symbols):
            raise AdmissionError("目标必须覆盖全部且不同的已准入执行证券")
        values = {row.symbol: _quantity(row.quantity) for row in vector}
        try:
            for symbol in self.execution_symbols:
                self._call("cta_set_position", self._ctx, symbol.encode(), values[symbol], encoded_tag, 0, 0)
            readback = self.targets()
            actual = dict(readback)
            if (any(actual.get(symbol, 0.0) != values[symbol] for symbol in self.execution_symbols)
                    or any(value != 0 for symbol, value in readback if symbol not in self.execution_symbols)):
                raise IncompleteBatch("原生拒绝/旧pending/partial目标读回不匹配")
            return readback
        except BaseException as exc:
            self._block("incomplete_batch", _reason(exc))
            raise IncompleteBatch(str(self._failure)) from exc

    def run(self) -> tuple[tuple[str, int], ...]:
        """同步原生运行；本层无法中断C调用，父进程仍须Job与总截止。"""
        self._owner_only()
        self._healthy()
        if self._state != "configured" or self._stack:
            raise PhaseError("run只允许configure后同步调用一次")
        self._state = "running"
        try:
            self._call("run_backtest", True, False)
        except BaseException as exc:
            self._block("run", _reason(exc))
        finally:
            self._state, self._phase = "finished", "after_run"
        if not self._end_seen:
            self._block("run", "缺少原生backtest end事件")
        self._healthy()
        return self.callback_counts

    def release(self):
        """run返回后由owner停日志；不join、不热卸载、不授完整排空。"""
        self._owner_only()
        if self._state not in ("finished", "released") or self._stack or self._active_user:
            raise PhaseError("release只能在同步run返回后调用")
        if self._state != "released":
            self._call("release_backtest")
            self._state = "released"
