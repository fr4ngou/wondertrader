"""configured 1.2.0纯核、NSQ与固定原CtaMocker的单会话组合。

本同步入口必须运行于外层预绑定Job并有绝对截止的独占进程。回调只读冻结
值和原生owner接口；本模块保存计算阶段与有限结果，持仓及资金事实归原生。
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field as dataclass_field, fields, is_dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from time import monotonic
from threading import get_ident
from types import MappingProxyType
import zlib

from guanheng_strategy_core import (
    ConfiguredStrategyConfig, EvaluationBudget, FrozenHistory,
    KernelValidationError, HistoricalEodModel, evaluate_history, evaluate_historical_model,
)
from guanheng_strategy_core.historical_model import HISTORICAL_REASON, HISTORICAL_SCOPE, HISTORICAL_REPORT_SCHEMA
from guanheng_strategy_native import (
    Basis, EconomicTarget, Limits, NativePosition, Observation, Price,
    QuantityPolicy, StageState, Weight, advance, generation_id,
)

from .strategy_porter import (
    BacktestConfig, BacktestPorter, Bar, Callbacks, Funds, Position, Target,
)
from .strategy_replay_facts import (_public, _json, _digest, SessionError, NativeSeries, NativeCapture, _native_json,
    _quantity, _decimal, capture_native, admit_native_files)
from .strategy_evaluation import FrozenV2SessionInput, REPORT_SCHEMA as V2_REPORT_SCHEMA, SYMBOLS as V2_SYMBOLS

ORIGINAL_BT_SHA256 = "4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e"
ABI_PROBE_SHA256 = "a7fdb6ecd763ebdd395d4b0d11d78a1f6d30bbb57f23a63630c2410c243b71b6"
_SHANGHAI = timezone(timedelta(hours=8))
_MODEL = "original-CtaMocker:flat-single-context-cash-long-absolute-setter-v1"
REPORT_SCHEMA = "nsb-report-v2"
MAX_RECORD_PAYLOAD_BYTES = 256 * 1024
MAX_EXPANDED_REPORT_BYTES = 64 * 1024 * 1024
_SHARED_FIELDS = ("daily_frames", "allocation_events", "auxiliary_gaps")
_V2_SHARED_FIELDS = tuple('decision_'+str(i) for i in range(8)) + ('allocation_events',)


def report_schema_for_input(value):
    """固定两种会话，不接调用方指定的模块/报告codec。"""
    if type(value) is dict and value.get('schema') == 'nsb-v2-input-v1':
        return V2_REPORT_SCHEMA
    if type(value) is dict and "historical_model" in value:
        return HISTORICAL_REPORT_SCHEMA
    return REPORT_SCHEMA




class _ReportCheckSignal(BaseException):
    """报告内部的控制信号，越过业务/编码错误转换后交回原调用方。"""

    def __init__(self, original):
        self.original = original
        super().__init__()


def _run_report_checked(operation, check):
    """隔离调用方截止/取消异常，公开出口恢复同一异常对象及其原因码。

    check可使用与业务验证器相同的异常类型。内部传专用BaseException信号，
    使解压、编码和字段校验只转换自身错误；控制异常始终由调用方拥有。
    """
    if check is None:
        return operation(None)

    def guarded_check():
        try:
            check()
        except BaseException as original:
            raise _ReportCheckSignal(original) from None

    try:
        return operation(guarded_check)
    except _ReportCheckSignal as stopped:
        original = stopped.original
        raise original.with_traceback(original.__traceback__) from None










def _immutable(value, *, check=None):
    """先限制输入树再序列化，拒绝frozen dataclass中的调用者可变容器。"""
    nodes, characters = 0, 0

    def visit(item, depth):
        nonlocal nodes, characters
        nodes += 1
        if check is not None and nodes%128==1:check()
        if nodes > 1048576 or depth > 16:
            raise SessionError("冻结输入树超过容量")
        if type(item) is str:
            characters += len(item)
            if characters > 8 * 1024 * 1024:
                raise SessionError("冻结输入文本超过容量")
        elif is_dataclass(item):
            for field in fields(item):
                visit(getattr(item, field.name), depth + 1)
        elif type(item) is tuple:
            for child in item:
                visit(child, depth + 1)
        elif type(item) not in (int, float, bool, type(None), date, datetime):
            raise SessionError("冻结输入包含可变或未知对象")

    visit(value, 0)
    if check is not None:check()


def _text(value, name):
    if type(value) is not str or not 1 <= len(value) <= 256 or any(ord(c) < 32 for c in value):
        raise SessionError(name + "需要有界明确来源")








@dataclass(frozen=True, slots=True)
class SessionLimits:
    """完整结果保留预算；到界前拒绝新计算/提交，外层另持进程绝对截止。"""
    max_calculations: int = 4096
    max_result_bytes: int = 8 * 1024 * 1024

    def __post_init__(self):
        for value, maximum in ((self.max_calculations, 4096), (self.max_result_bytes, 8388608)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise SessionError("会话结果预算超出硬上限")


@dataclass(frozen=True, slots=True)
class FrozenSessionInput:
    """native前冻结并核实的业务输入，费用预留为本次全部新增买入的显式上界。

    本profile日线为raw CNY/share、volume为份、amount为CNY，收盘为上海15:00。
    source_revision/factor_revision及逐行来源属于FrozenHistory，任何修订新建会话。
    fee_reserve_cny=None保留NSQ waiting_fee；零值必须附明确来源。
    """
    config: ConfiguredStrategyConfig
    history: FrozenHistory
    native_mapping: tuple[tuple[str, str], ...]
    series: tuple[NativeSeries, ...]
    policy: QuantityPolicy
    fee_reserve_cny: str | None
    fee_source: str | None
    market_manifest_source: str
    price_adjustment: str = "raw"
    price_unit: str = "CNY/share"
    volume_unit: str = "share"
    amount_unit: str = "CNY"
    daily_close: str = "Asia/Shanghai:15:00"
    historical_model: HistoricalEodModel | None = dataclass_field(default=None, metadata={"omit_none": True})




@dataclass(frozen=True, slots=True)
class ResultHistory:
    """完整增长历史各存一份；JSON行不可变，逐日边界由SessionRecord明确记录。"""
    daily_frames_json: tuple[str, ...] = ()
    allocation_events_json: tuple[str, ...] = ()
    auxiliary_gaps_json: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class V2ResultHistory:
    decision_series_json: tuple = tuple((symbol, ()) for symbol in V2_SYMBOLS)
    allocation_events_json: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """有界压缩当日完整header/原值/阶段，累计frames/events/gaps使用共享边界。"""
    trading_date: int
    minute: int
    status: str
    reason: str
    history_end: tuple[int, ...] | None
    payload_b64: str
    payload_bytes: int
    payload_sha256: str

    def to_dict(self, history: ResultHistory):
        """单记录便利入口；history为该条完整前缀，统一走报告准入。"""
        header = _unpack_record(_public(self))["header"]
        historical = type(header) is dict and "historical_model" in header
        schema = V2_REPORT_SCHEMA if type(history) is V2ResultHistory else HISTORICAL_REPORT_SCHEMA if historical else REPORT_SCHEMA
        options = {"scope": HISTORICAL_SCOPE} if historical else {}
        report = SessionReport("single-record", self.status, (self,), (), 0, (), history,
                               schema=schema, **options)
        return reconstruct_session_record(report, 0)


@dataclass(frozen=True, slots=True, init=False)
class ValidatedSessionReport:
    """一次同版准入后的深不可变值，供重复索引读取；构造也执行唯一校验器。

    不保存调用者dict引用；wire和共享解析值均递归冻结。每日压缩快照按需
    有界解压，避免缓存全部展开快照；每次重建返回独立普通值。
    """
    _wire: object
    _history: object

    def __init__(self, value: dict, *, check=None):
        admitted = validate_report_dict(value, check=check)
        object.__setattr__(self, "_wire", admitted._wire)
        object.__setattr__(self, "_history", admitted._history)

    @property
    def record_count(self):
        return len(self._wire["records"])

    def to_dict(self, *, check=None):
        return _thaw_json(self._wire, check=check)


@dataclass(frozen=True, slots=True)
class SessionReport:
    session_id: str
    status: str
    records: tuple[SessionRecord, ...]
    callback_counts: tuple[tuple[str, int], ...]
    result_bytes: int
    native_files: tuple[tuple[str, str], ...]
    shared_history: ResultHistory
    schema: str = REPORT_SCHEMA
    scope: str = "synthetic-or-admitted-raw-BT-only; RT/real-source/HTTP/broker/production-unqualified"
    _validated: ValidatedSessionReport = dataclass_field(init=False, repr=False, compare=False,
                                                        metadata={"wire": False})

    def __post_init__(self):
        # result_bytes=0是构建请求，准入时精确求固定点；其他值须与wire完全一致。
        admitted = _admit_report(self, model=True,
                                 derive_size=type(self.result_bytes) is int and self.result_bytes == 0)
        value = admitted.to_dict()
        for name in ("session_id", "status", "result_bytes", "schema", "scope"):
            object.__setattr__(self, name, value[name])
        object.__setattr__(self, "records", tuple(SessionRecord(**{
            **row, "history_end": None if row["history_end"] is None else tuple(row["history_end"])
        }) for row in value["records"]))
        for name in ("callback_counts", "native_files"):
            object.__setattr__(self, name, tuple(tuple(row) for row in value[name]))
        if self.schema == V2_REPORT_SCHEMA:
            object.__setattr__(self, 'shared_history', V2ResultHistory(
                tuple((symbol, tuple(rows)) for symbol,rows in value['shared_history']['decision_series_json']),
                tuple(value['shared_history']['allocation_events_json'])))
        else:
            object.__setattr__(self, "shared_history", ResultHistory(**{
                name: tuple(rows) for name, rows in value["shared_history"].items()}))
        object.__setattr__(self, "_validated", admitted)

    def to_dict(self):
        """生成独立可传输v2值；完整业务结果使用公开重建函数取得。"""
        return self._validated.to_dict()


def _snapshot_json(value, *, maximum=8 * 1024 * 1024, check=None, model=False):
    """先有界复制JSON树，再交唯一业务校验器；回调不能修改已完成的快照。"""
    used, nodes = 0, 0

    def consume(count):
        nonlocal used
        used += count
        if used > maximum:
            raise SessionError("报告JSON树字节预算耗尽")

    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        if check is not None and nodes % 128 == 1:
            check()
        if nodes > 1048576 or depth > 32:
            raise SessionError("报告JSON树节点或深度超限")
        if model and type(item) in (SessionReport, SessionRecord, ResultHistory, V2ResultHistory):
            members = [item_field for item_field in fields(item) if item_field.metadata.get("wire", True)]
            consume(2 + max(0, len(members) - 1))
            result = {}
            for member in members:
                visit(member.name, depth + 1)
                consume(1)
                result[member.name] = visit(getattr(item, member.name), depth + 1)
            return result
        if type(item) is dict:
            consume(2 + max(0, len(item) - 1))
            result = {}
            for key, child in item.items():
                if type(key) is not str:
                    raise SessionError("报告JSON键必须为字符串")
                visit(key, depth + 1)
                consume(1)
                result[key] = visit(child, depth + 1)
            return result
        if type(item) is list or (model and type(item) is tuple):
            consume(2 + max(0, len(item) - 1))
            return [visit(child, depth + 1) for child in item]
        if (type(item) not in (str, int, float, bool, type(None))
                or (type(item) is str and len(item) > maximum)
                or (type(item) is int and item.bit_length() > 4096)
                or (type(item) is float and not math.isfinite(item))):
            raise SessionError("报告JSON值类型或容量无效")
        consume(len(json.dumps(item, ensure_ascii=True, allow_nan=False, separators=(",", ":"))))
        return item

    result = visit(value, 0)
    if check is not None:
        check()
    return result


def _freeze_json(value, *, check=None):
    if check is not None:
        check()
    if type(value) is dict:
        return MappingProxyType({key: _freeze_json(child, check=check) for key, child in value.items()})
    if type(value) is list:
        return tuple(_freeze_json(child, check=check) for child in value)
    return value


def _thaw_json(value, *, check=None):
    if check is not None:
        check()
    if type(value) is MappingProxyType:
        return {key: _thaw_json(child, check=check) for key, child in value.items()}
    if type(value) is tuple:
        return [_thaw_json(child, check=check) for child in value]
    return value


def _pack_record(day, minute, status, reason, ends, payload):
    raw = _json(payload).encode("ascii")
    if len(raw) > MAX_RECORD_PAYLOAD_BYTES:
        raise SessionError("当日完整快照展开容量耗尽")
    return SessionRecord(day, minute, status, reason, ends,
                         base64.b64encode(zlib.compress(raw)).decode("ascii"), len(raw), sha256(raw).hexdigest())


def _unpack_record(record, *, check=None):
    """有限分块解压，SHA绑定完整当日值；调用者的总截止贯穿验证。"""
    if check is not None:
        check()
    size = record.get("payload_bytes")
    encoded = record.get("payload_b64")
    if (type(size) is not int or not 0 < size <= MAX_RECORD_PAYLOAD_BYTES
            or type(encoded) is not str or len(encoded) > 2 * MAX_RECORD_PAYLOAD_BYTES
            or type(record.get("payload_sha256")) is not str):
        raise SessionError("当日快照格式或展开预算无效")
    try:
        compressed = base64.b64decode(encoded, validate=True)
        decoder, raw = zlib.decompressobj(), bytearray()
        for offset in range(0, len(compressed), 4096):
            block = compressed[offset:offset + 4096]
            while block:
                if check is not None:
                    check()
                raw.extend(decoder.decompress(block, min(65536, size + 1 - len(raw))))
                if len(raw) > size:
                    raise SessionError("当日快照实际展开超过声明预算")
                block = decoder.unconsumed_tail
        if (not decoder.eof or decoder.unused_data or len(raw) != size
                or sha256(raw).hexdigest() != record["payload_sha256"]):
            raise SessionError("当日快照压缩边界、长度或SHA失配")
        payload = _snapshot_json(_native_json(bytes(raw)), maximum=MAX_RECORD_PAYLOAD_BYTES, check=check)
    except (ValueError, zlib.error) as exc:
        raise SessionError("当日快照编码无效") from exc
    if type(payload) is not dict or set(payload) != {
        "header", "capture", "outcome", "previous_status", "submit_vector", "readback"
    }:
        raise SessionError("当日快照字段不完整")
    return payload


def _v2_prefix_result(header, ends, history, *, check=None):
    """恢复并校验同一完整前缀，准入和公开重建共用此实现。

    header来自本次独立解压值；共享行只读。逐日前缀仅临时展开，避免把全部
    累计结果缓存回报告。校验先于已验证标签发布，轻量页面也继承完整性结论。
    """
    from guanheng_strategy_core.contracts import canonical_bytes

    for i, group in enumerate(header['signal_trace']['decision_series']):
        group['decisions'] = [_thaw_json(row, check=check)
                              for row in history['decision_' + str(i) + '_json'][:ends[i]]]
    header['pipeline']['allocation']['allocation_events'] = [
        _thaw_json(row, check=check) for row in history['allocation_events_json'][:ends[-1]]]
    for field, key in (('signal_trace', 'trace_sha256'), ('pipeline', 'pipeline_sha256')):
        body = dict(header[field])
        expected = body.pop(key)
        try:
            actual = sha256(canonical_bytes(body, check=check, max_bytes=8 * 1024 * 1024)).hexdigest()
        except KernelValidationError:
            raise SessionError('V2完整前缀编码或容量无效') from None
        if actual != expected:
            raise SessionError('V2重建结果摘要失配')
    return _snapshot_json({'schema': 'nsb-v2-prefix-v1', 'pipeline': header['pipeline'],
                           'signal_trace': header['signal_trace']},
                          maximum=8 * 1024 * 1024, check=check)


def _reconstruct_record(record, history, *, check=None, schema=REPORT_SCHEMA):
    payload = _unpack_record(record, check=check)
    result = payload.pop("header")
    ends = record["history_end"]
    if result is not None:
        result = dict(result)
        if schema == V2_REPORT_SCHEMA:
            result = _v2_prefix_result(result, ends, history, check=check)
        for field, end in zip(_SHARED_FIELDS if schema!=V2_REPORT_SCHEMA else (), ends if schema!=V2_REPORT_SCHEMA else (), strict=True):
            rows = history[field + "_json"]
            values = []
            for row in rows[:end]:
                values.append(_thaw_json(row, check=check))
            result[field] = values
        if check is not None:
            check()
        # JSON树先计量再编码，完整前缀的输出预算也沿同一check。
        if schema != V2_REPORT_SCHEMA:
            result = _snapshot_json(result, maximum=8 * 1024 * 1024, check=check)
        if check is not None:
            check()
    return {"trading_date": record["trading_date"], "minute": record["minute"],
            "status": record["status"], "reason": record["reason"], "result": result, **payload}


def reconstruct_session_record(report: SessionReport | ValidatedSessionReport | dict, index: int, *, check=None) -> dict:
    """同版准入后重建独立值；全量扫描复用validate_report_dict返回值。

    raw dict每次完整准入，避免依赖可变对象标签或调用者先验；SessionReport
    在构造时已经准入并深冻结，ValidatedSessionReport供外部一次准入后复用。
    """
    return _run_report_checked(
        lambda guarded: _reconstruct_session_record(report, index, check=guarded), check)


def _reconstruct_session_record(report, index, *, check):
    if type(report) is SessionReport:
        admitted = report._validated
    elif type(report) is ValidatedSessionReport:
        admitted = report
    else:
        admitted = validate_report_dict(report, check=check)
    if type(index) is not int or not 0 <= index < admitted.record_count:
        raise SessionError("重建记录索引越界")
    return _reconstruct_record(admitted._wire["records"][index], admitted._history, check=check,schema=admitted._wire['schema'])


def reconstruct_prefix_result(report: SessionReport | ValidatedSessionReport | dict, index: int, *, check=None) -> dict | None:
    """精确还原整个公开EvaluationResult；预热记录返回None并保留原记录理由。"""
    return reconstruct_session_record(report, index, check=check)["result"]


def validate_report_dict(value: dict, *, check=None) -> ValidatedSessionReport:
    """v2唯一准入，返回深不可变报告值；重复索引读取复用返回值。

    wire最多8MiB，最多4096记录，每条展开256KiB，全会话展开最多64MiB。
    复制并计量输入后校验共享行/每日快照；宿主持run/input/install及输出绑定。
    """
    return _admit_report(value, check=check)


def project_session_record(report, index, *, check=None):
    """同一validator下的有界当日投影，不为展示展开全部增长历史。"""
    return _run_report_checked(
        lambda guarded: _project_session_record(report, index, check=guarded), check)


def _project_session_record(report, index, *, check):
    admitted=report._validated if type(report) is SessionReport else report if type(report) is ValidatedSessionReport else validate_report_dict(report,check=check)
    if type(index) is not int or not 0<=index<admitted.record_count:raise SessionError('重建记录索引越界')
    record=admitted._wire['records'][index]
    payload=_unpack_record(record,check=check);header=payload.pop('header')
    return {'record':{'trading_date':record['trading_date'],'minute':record['minute'],
        'status':record['status'],'reason':record['reason'],**payload},'evaluation_summary':header,
        'report_schema':admitted._wire['schema']}


def _admit_report(value, *, check=None, derive_size=False, model=False):
    from .strategy_evaluation import EvaluationError

    def admit(guarded):
        # 业务错误统一为会话原因；调用方check经独立控制信号越过本转换。
        try:
            return _admit_report_body(value, check=guarded, derive_size=derive_size, model=model)
        except EvaluationError:
            raise SessionError('V2报告字段、来源或因果身份无效') from None

    return _run_report_checked(admit, check)


def _admit_report_body(value, *, check=None, derive_size=False, model=False):
    value = _snapshot_json(value, check=check, model=model)
    if (type(value) is not dict or set(value) != {item.name for item in fields(SessionReport)
                                               if item.metadata.get("wire", True)}
            or value.get("schema") not in (REPORT_SCHEMA,V2_REPORT_SCHEMA,HISTORICAL_REPORT_SCHEMA)):
        raise SessionError("报告schema无效")
    _text(value["session_id"], "报告会话身份")
    _text(value["status"], "报告阶段")
    _text(value["scope"], "报告资格范围")
    historical = value["schema"] == HISTORICAL_REPORT_SCHEMA
    if historical and value["scope"] != HISTORICAL_SCOPE:
        raise SessionError("历史回测报告须保存明确资格范围")
    for field, maximum in (("callback_counts", 16), ("native_files", 5)):
        rows = value[field]
        if (type(rows) is not list or len(rows) > maximum
                or any(type(row) is not list or len(row) != 2 for row in rows)):
            raise SessionError("报告callback/资料身份字段无效")
        for name, item in rows:
            _text(name, "报告callback/资料名称")
            if field == "callback_counts":
                if type(item) is not int or not 0 <= item <= 2**53 - 1:
                    raise SessionError("报告callback计数无效")
            elif type(item) is not str or re.fullmatch(r"[0-9a-f]{64}", item) is None:
                raise SessionError("报告原生资料SHA无效")
        if len({row[0] for row in rows}) != len(rows):
            raise SessionError("报告callback/资料名称重复")
    records, history = value.get("records"), value.get("shared_history")
    v2=value['schema']==V2_REPORT_SCHEMA
    shared_fields=_V2_SHARED_FIELDS if v2 else _SHARED_FIELDS
    if v2:
        if type(history) is not dict or set(history)!={'decision_series_json','allocation_events_json'}:
            raise SessionError('V2共享历史字段无效')
        groups=history['decision_series_json']
        if (type(groups) is not list or len(groups)!=8 or any(type(g) is not list or len(g)!=2 or g[0]!=s
                for g,s in zip(groups,V2_SYMBOLS,strict=True))):raise SessionError('V2共享证券组失配')
        history={**{'decision_'+str(i)+'_json':g[1] for i,g in enumerate(groups)},
                 'allocation_events_json':history['allocation_events_json']}
    if (type(records) is not list or not 1 <= len(records) <= 4096 or type(history) is not dict
            or set(history) != {field + "_json" for field in shared_fields}):
        raise SessionError("报告记录/共享历史格式无效")
    expanded, prior_ends, prior_day, parsed_history = 0, tuple(0 for _ in shared_fields), 0, {}
    historical_identity = None
    stable_v2=None
    for field in shared_fields:
        rows = history[field + "_json"]
        if type(rows) is not list or len(rows) > (32768 if field == "auxiliary_gaps" else 4096):
            raise SessionError("共享历史超过行数容量")
        parsed = []
        for row in rows:
            if check is not None:
                check()
            if type(row) is not str or len(row) > MAX_RECORD_PAYLOAD_BYTES:
                raise SessionError("共享历史行格式或容量无效")
            expanded += len(row)
            if expanded > MAX_EXPANDED_REPORT_BYTES:
                raise SessionError("共享历史展开容量无效")
            try:
                item = _snapshot_json(_native_json(row.encode("ascii")),
                                      maximum=MAX_RECORD_PAYLOAD_BYTES, check=check)
            except UnicodeError as exc:
                raise SessionError("共享历史必须为ASCII JSON") from exc
            if type(item) is not dict:
                raise SessionError("共享历史行必须为对象")
            if v2:
                from .strategy_evaluation import validate_shared_row
                validate_shared_row(item,field,check=check)
                if parsed and item['trade_date']<=parsed[-1]['trade_date']:
                    raise SessionError('V2共享行日期失序')
            parsed.append(_freeze_json(item, check=check))
        parsed_history[field + "_json"] = tuple(parsed)
    for record in records:
        if check is not None:
            check()
        if type(record) is not dict or set(record) != {field.name for field in fields(SessionRecord)}:
            raise SessionError("报告记录字段不完整")
        day = record["trading_date"]
        if (type(day) is not int or day <= prior_day or type(record["minute"]) is not int
                or record["minute"] != 1500):
            raise SessionError("报告闭合日期失序")
        StrategyBacktestSession._clock(day, record["minute"])
        prior_day = day
        _text(record["status"], "记录阶段")
        _text(record["reason"], "记录理由")
        payload = _unpack_record(record, check=check)
        expanded += record["payload_bytes"]
        if expanded > MAX_EXPANDED_REPORT_BYTES:
            raise SessionError("报告累计展开容量耗尽")
        ends = record["history_end"]
        if payload["header"] is None:
            if ends is not None or record["status"] != "warming_up":
                raise SessionError("预热记录语义无效")
        else:
            if v2:
                from .strategy_evaluation import validate_v2_header
                validate_v2_header(payload['header'],day,check=check)
                if type(ends) is not list or len(ends)!=9:raise SessionError('V2共享边界失配')
                for field,end,prior in zip(shared_fields,ends,prior_ends,strict=True):
                    if type(end) is not int or not prior<=end<=len(history[field+'_json']):raise SessionError('V2共享边界越界或回退')
                    rows=parsed_history[field+'_json']
                    if end and int(rows[end-1]['trade_date'].replace('-',''))>day:raise SessionError('V2共享历史越截止')
                    if end<len(rows) and int(rows[end]['trade_date'].replace('-',''))<=day:
                        raise SessionError('V2边界漏引用已知共享前缀')
                header=payload['header'];trace=header['signal_trace'];allocation=header['pipeline']['allocation']
                identity=(header['stable_spec_sha256'],tuple(trace[name] for name in (
                    'source_revision','factor_revision','history_start','evaluation_start')),
                    allocation['raw_diagnostic']['pre_risk_capacity'],
                    trace['core_version'],trace['core_wheel_sha256'],
                    tuple(sorted(header['pipeline']['dependencies'].items())))
                if stable_v2 is not None and identity!=stable_v2:raise SessionError('V2同会话固定身份发生修订')
                stable_v2=identity
                if any(ends[i] and parsed_history[field+'_json'][0]['trade_date']<trace['evaluation_start']
                       for i,field in enumerate(shared_fields)):
                    raise SessionError('V2共享历史越过固定评估起点')
                events=parsed_history['allocation_events_json']
                last=events[ends[-1]-1] if ends[-1] else None
                if ((last is None and allocation['latest_event_date'] is not None)
                        or (last is not None and (allocation['latest_event_date']!=last['trade_date']
                            or allocation['latest_raw_weights']!=_thaw_json(last['target_weights'],check=check)))
                        or allocation['new_event_for_cutoff']!=(last is not None and int(last['trade_date'].replace('-',''))==day)):
                    raise SessionError('V2当日分配状态与共享事件边界失配')
                # 结构和边界正确仍可能引用被改动的共享行；在发布已验证标签前，
                # 用公开重建的同一逻辑核全部摘要和组合容量。页面无需重复展开。
                _v2_prefix_result(header, ends, parsed_history, check=check)
                prior_ends=tuple(ends)
                continue
            from guanheng_strategy_core import EvaluationResult
            header = payload["header"]
            expected_fields = {f.name for f in fields(EvaluationResult)} - set(_SHARED_FIELDS) - {"historical_model"}
            if (type(header) is not dict or set(header) - {"historical_model"} != expected_fields
                    or type(ends) is not list or len(ends) != 3):
                raise SessionError("完整核header字段/边界失配")
            if "historical_model" in header:
                try:
                    model = HistoricalEodModel.from_dict(header["historical_model"])
                except KernelValidationError as exc:
                    raise SessionError("报告历史模型无效") from exc
                if (not historical or model.dataset_sha256 != header.get("source_revision") or header.get("qualified") is not False
                        or type(header.get("qualification_reasons")) is not list
                        or HISTORICAL_REASON not in header["qualification_reasons"] or value["scope"] != HISTORICAL_SCOPE):
                    raise SessionError("报告历史模型资格或范围失配")
                identity = _json(model)
                if historical_identity is not None and identity != historical_identity:
                    raise SessionError("报告内历史模型身份发生变化")
                historical_identity = identity
            elif historical:
                raise SessionError("历史回测报告缺少完整模型与来源身份")
            for name in ("kernel_version", "strategy_id", "strategy_version"):
                _text(header[name], "核header算法身份")
            for name in ("config_sha256", "input_sha256", "source_revision", "factor_revision"):
                if type(header[name]) is not str or re.fullmatch(r"[0-9a-f]{64}", header[name]) is None:
                    raise SessionError("核header输入身份无效")
            try:
                ready = date.fromisoformat(header["first_ready_date"])
                closed = date.fromisoformat(header["last_closed_date"])
                cutoff = datetime.fromisoformat(header["knowledge_cutoff"])
                if ready > closed or int(closed.strftime("%Y%m%d")) != day or cutoff.tzinfo is None:
                    raise ValueError()
                if historical:
                    from guanheng_strategy_core.models import observation_close_at
                    if model.received_at < observation_close_at(closed):
                        raise ValueError()
            except (ValueError, TypeError) as exc:
                raise SessionError("核header因果日期无效") from exc
            if (type(header["qualified"]) is not bool
                    or any(type(header[name]) is not list or len(header[name]) > 8
                           or any(type(row) is not dict for row in header[name])
                           for name in ("current_targets", "latest_features", "signal_states"))
                    or type(header["qualification_reasons"]) is not list
                    or any(type(reason) is not str for reason in header["qualification_reasons"])):
                raise SessionError("核header结果字段类型无效")
            for field, end, prior in zip(_SHARED_FIELDS, ends, prior_ends, strict=True):
                if type(end) is not int or not prior <= end <= len(history[field + "_json"]):
                    raise SessionError("报告共享历史边界越界或回退")
            prior_ends = tuple(ends)
    if tuple(len(history[field + "_json"]) for field in shared_fields) != prior_ends:
        raise SessionError("报告含未引用的额外历史")
    if check is not None:
        check()
    if derive_size:
        for _ in range(3):
            if check is not None:
                check()
            value["result_bytes"] = len(_json(value).encode("ascii"))
    if (type(value["result_bytes"]) is not int or len(_json(value).encode("ascii")) != value["result_bytes"]
            or value["result_bytes"] > 8 * 1024 * 1024):
        raise SessionError("报告完整字节身份或容量失配")
    if check is not None:
        check()
    admitted = object.__new__(ValidatedSessionReport)
    object.__setattr__(admitted, "_wire", _freeze_json(value, check=check))
    object.__setattr__(admitted, "_history", MappingProxyType(parsed_history))
    return admitted


class StrategyBacktestSession:
    """一次性同步owner。run前由外层完成Job绑定、进程/管道预算及独立目录准入。

    同进程只允许一个Porter。callbacks从不stop/release/join；run返回后才停日志。
    本接口没有恢复旧native目录或替换已冻结source/config/factor的能力。
    """

    def __init__(self, inputs: FrozenSessionInput, *, limits: SessionLimits = SessionLimits(),
                 kernel_budget: EvaluationBudget = EvaluationBudget(), quantity_limits: Limits = Limits(),v2_budget=None):
        started=monotonic()
        if type(inputs) not in (FrozenSessionInput,FrozenV2SessionInput) or type(limits) is not SessionLimits:
            raise SessionError("需要明确冻结输入和会话预算")
        # frozen标签不能保证调用方对象以后不变；owner只持重验硬限后的独占值。
        try:
            limits = SessionLimits(**{item.name: getattr(limits, item.name) for item in fields(SessionLimits)})
        except AttributeError:
            raise SessionError("会话结果预算字段不完整") from None
        v2=type(inputs) is FrozenV2SessionInput
        deadline=None
        if v2:
            from guanheng_strategy_v2 import V2Budget
            if v2_budget is not None and type(v2_budget) is not V2Budget:raise SessionError('V2预算类型无效')
            v2_budget=V2Budget() if v2_budget is None else V2Budget(**{f.name:getattr(v2_budget,f.name) for f in fields(V2Budget)})
            deadline=started+v2_budget.max_seconds
            if type(kernel_budget) is not EvaluationBudget or kernel_budget!=EvaluationBudget():
                raise SessionError('V2输入须使用本版V2预算')
        def check():
            if deadline is not None and monotonic()>=deadline:raise SessionError('V2完整准入期限耗尽')
        _immutable(inputs,check=check if v2 else None)
        if (not v2 and type(inputs.config) is not ConfiguredStrategyConfig) or type(inputs.history) is not FrozenHistory:
            raise SessionError("核配置/历史类型无效")
        if type(inputs.policy) is not QuantityPolicy or type(quantity_limits) is not Limits:
            raise SessionError("数量policy/预算类型无效")
        self._historical_model = None if v2 else inputs.historical_model
        if self._historical_model is not None and type(self._historical_model) is not HistoricalEodModel:
            raise SessionError("冻结会话需要明确历史回测模型")
        if self._historical_model is not None:
            self._historical_model = HistoricalEodModel.validated_copy(self._historical_model)
            inputs = replace(inputs, historical_model=self._historical_model)
        amount_unit = "unknown" if self._historical_model is not None else "CNY"
        if (inputs.price_adjustment, inputs.price_unit, inputs.volume_unit, inputs.amount_unit, inputs.daily_close) != (
            "raw", "CNY/share", "share", amount_unit, "Asia/Shanghai:15:00"
        ):
            raise SessionError("当前原生现金ETF模型只接明确raw日线及单位")
        _text(inputs.market_manifest_source, "行情manifest")
        if inputs.fee_source is not None:
            _text(inputs.fee_source, "费用来源")
        if inputs.fee_reserve_cny is not None:
            if type(inputs.fee_reserve_cny) is not str or len(inputs.fee_reserve_cny) > 256:
                raise SessionError("费用预留需要有界十进制字符串")
            _text(inputs.fee_source, "费用来源")
        if len(inputs.history.observations) > 32768 or not inputs.history.observations:
            raise SessionError("冻结核历史为空或超出容量")
        if len(_json(inputs).encode("ascii")) > 16 * 1024 * 1024:
            raise SessionError("冻结会话输入超过容量")
        check()
        config, history = None if v2 else inputs.config, inputs.history
        self._business=None
        # 原单一核承担全部规则及逐行辅助/来源校验；仅预热不足是可运行的空提交状态。
        last_day = max(row.trade_date for row in history.observations)
        if v2:
            from .strategy_evaluation import V2Binding
            self._business=V2Binding(inputs,v2_budget,deadline=deadline)
        else:
            if v2_budget is not None:raise SessionError('configured输入不能选择V2预算')
            try:
                self._evaluate_history(config, history, self._clock(int(last_day.strftime("%Y%m%d")), 1500), budget=kernel_budget)
            except KernelValidationError as exc:
                if exc.code != "insufficient_warmup":
                    raise
        self._inputs, self._limits = inputs, limits
        self._kernel_budget, self._quantity_limits = kernel_budget, quantity_limits
        self._execution = self._business.execution if v2 else tuple(sorted(dict(config.execution_symbols).values()))
        reads = self._business.reads if v2 else set(dict(config.symbol_roles).values()) | set(self._execution)
        mapping = inputs.native_mapping
        if (type(mapping) is not tuple or len(mapping) != len(reads) or len(reads) > 16
                or any(type(pair) is not tuple or len(pair) != 2 for pair in mapping)):
            raise SessionError("映射需要完整且唯一的读取并集")
        self._mapping = dict(mapping)
        if len(self._mapping) != len(mapping) or set(self._mapping) != reads:
            raise SessionError("映射缺失或重复")
        for symbol, native in mapping:
            if (type(native) is not str or re.fullmatch(r"(?:SSE|SZSE)\.ETF\.[0-9]{6}", native) is None
                    or native.split(".")[2] != symbol[:6]
                    or (native.startswith("SSE.") and not symbol.endswith(".SH"))
                    or (native.startswith("SZSE.") and not symbol.endswith(".SZ"))):
                raise SessionError("需要显式同代码沪深ETF映射")
        if len(set(self._mapping.values())) != len(reads):
            raise SessionError("原生映射重复")
        if type(inputs.series) is not tuple or len(inputs.series) != len(reads):
            raise SessionError("原生行情未覆盖读取并集")
        self._series = {}
        expected_days = tuple(sorted({int(row.trade_date.strftime("%Y%m%d")) for row in history.observations}))
        for series in inputs.series:
            check()
            if (type(series) is not NativeSeries or series.symbol in self._series
                    or series.symbol not in self._mapping.values() or type(series.bars) is not tuple
                    or len(series.bars) > 4096 or any(type(bar) is not Bar for bar in series.bars)
                    or tuple(bar.date for bar in series.bars) != expected_days):
                raise SessionError("原生raw行情日期集合缺失、重复、越界或失序")
            for bar in series.bars:
                check()
                if (bar.time != 0 or min(bar.open, bar.high, bar.low, bar.close) <= 0
                        or bar.low > min(bar.open, bar.high, bar.close)
                        or bar.high < max(bar.open, bar.low, bar.close) or min(bar.vol, bar.money) < 0):
                    raise SessionError("raw日线数值或日期编码失效")
            self._series[series.symbol] = series.bars
        day_indexes = {day: index for index, day in enumerate(expected_days)}
        for row in history.observations:
            check()
            native_rows = self._series[self._mapping[row.symbol]]
            bar = native_rows[day_indexes[int(row.trade_date.strftime("%Y%m%d"))]]
            if self._market(row) != self._bar_market(bar):
                raise SessionError("核行情与原生loader逐日字段失配")
        self._days = expected_days
        # Basis构造复用NSQ对费用/资本精度的准入；verified不对外授资格。
        Basis(self._clock(expected_days[-1], 1500).isoformat(), "0" * 64,
              inputs.policy.initial_capital_cny, "0", inputs.policy.initial_capital_cny,
              inputs.fee_reserve_cny, "preflight-only", "preflight-only", inputs.fee_source,
              tuple(Price(symbol, None, "preflight-only") for symbol in self._execution), False, "preflight")
        self._input_id = _digest(inputs)
        check()
        self._owner = get_ident()
        self._records, self._used_bytes = [], 0
        self._result_history = V2ResultHistory() if v2 else ResultHistory()
        self._history_bytes = len(_json(self._result_history))
        self._expanded_bytes = 0
        self._state: StageState | None = None
        self._sequence, self._bar_count, self._last_clock = 0, 0, None
        self._session_id, self._porter, self._started, self._initialized = None, None, False, False
        self._native_files = ()

    def _evaluate_history(self, config, history, cutoff, *, budget):
        """仅本回测owner显式选择回测库函数；默认严格核保持原可知准入。"""
        if self._historical_model is not None:
            return evaluate_historical_model(config, history, self._historical_model, cutoff, budget=budget)
        return evaluate_history(config, history, cutoff, budget=budget)

    @staticmethod
    def _market(row):
        return row.open, row.high, row.low, row.close, row.volume, row.amount

    @staticmethod
    def _bar_market(bar):
        return bar.open, bar.high, bar.low, bar.close, bar.vol, bar.money

    @staticmethod
    def _clock(day, minute):
        try:
            if type(day) is not int or type(minute) is not int:
                raise ValueError
            parsed = datetime.strptime(str(day), "%Y%m%d").date()
            return datetime.combine(parsed, time(minute // 100, minute % 100), _SHANGHAI)
        except (ValueError, OverflowError) as exc:
            raise SessionError("原生时钟无效") from exc

    @property
    def records(self):
        return tuple(self._records)

    @property
    def result_history(self):
        return self._result_history

    @property
    def state(self):
        return self._state

    def _owner_porter(self, porter):
        if (get_ident() != self._owner or porter is not self._porter or not self._started
                or self._session_id is None):
            raise SessionError("会话只接受本次run的原生owner上下文")

    def _initialize(self, porter):
        self._owner_porter(porter)
        if self._initialized:
            raise SessionError("重复原生初始化")
        if (set(porter.symbols) != set(self._mapping.values())
                or set(porter.execution_symbols) != {self._mapping[s] for s in self._execution}):
            raise SessionError("原生读取/执行集合失配")
        if porter.targets() or any(getattr(porter.funds(), name) != 0 for name in ("net", "realized", "dynamic", "fees")):
            raise SessionError("会话需要初始flat且无资金损益")
        for symbol in self._execution:
            position = porter.position(self._mapping[symbol])
            if any(getattr(position, name) != 0 for name in ("total", "valid", "first_entry", "last_entry")):
                raise SessionError("初始原生持仓非空")
        benchmark = self._mapping[self._business.benchmark if self._business is not None else dict(self._inputs.config.symbol_roles)[self._inputs.config.benchmark_role]]
        for symbol in sorted(self._series):
            porter.get_bars(symbol, "d1", 2, main=symbol == benchmark)
            porter.subscribe_bars(symbol, "d1")
        self._initialized = True

    def _loader(self, symbol, period):
        if period != "d1" or symbol not in self._series:
            raise SessionError("loader只允许已冻结完整日线")
        return self._series[symbol]

    def _on_bar(self, porter, symbol, period, bar):
        self._owner_porter(porter)
        # 不在on_bar读取bars；get_bars会改变原生closed标记。
        if period != "d1" or symbol not in self._series or bar not in self._series[symbol]:
            raise SessionError("原生bar事件与冻结来源失配")
        self._bar_count += 1
        if self._bar_count > 16 * 4096:
            raise SessionError("bar事件超出预算")

    def _capture(self, porter, day, minute, input_sha, *, check=None):
        return capture_native(self, porter, day, minute, input_sha, check=check)

    def _record_size(self, record, history_bytes=None, *, before_submit=False):
        size = len(_json(record).encode("ascii"))
        if before_submit:
            # zlib compressBound式的上界覆盖全部原值读回，不依赖压缩后的相似程度。
            raw = record.payload_bytes + 1024  # 最多8个31字节代码及18字符数量。
            bound = raw + (raw >> 12) + (raw >> 14) + (raw >> 25) + 13
            size += 4 * ((bound + 2) // 3) - len(record.payload_b64)
        shared_bytes = self._history_bytes if history_bytes is None else history_bytes
        if (self._used_bytes + size + shared_bytes + 8192
                > self._limits.max_result_bytes
                or self._expanded_bytes + record.payload_bytes + shared_bytes + (1024 if before_submit else 0)
                > MAX_EXPANDED_REPORT_BYTES
                or record.payload_bytes + (1024 if before_submit else 0) > MAX_RECORD_PAYLOAD_BYTES):
            raise SessionError("会话完整结果字节预算耗尽")
        return size

    def _extend_result_history(self, public, *, check=None):
        if self._business is not None:
            from guanheng_strategy_core.contracts import canonical_bytes
            def encode(value):
                return canonical_bytes(value,check=check,max_bytes=MAX_RECORD_PAYLOAD_BYTES).decode('ascii')
            groups=[];stored=self._history_bytes
            for (symbol,old),group in zip(self._result_history.decision_series_json,public['signal_trace']['decision_series'],strict=True):
                if check is not None:check()
                if group['symbol']!=symbol:raise SessionError('V2信号证券序列失配')
                new=tuple(encode(row) for row in group['decisions']);group['decisions']=[]
                if new[:len(old)]!=old:raise SessionError('V2已有信号历史修订，须新建会话')
                stored+=sum(len(encode(row))+(1 if len(old)+i else 0) for i,row in enumerate(new[len(old):]))
                groups.append((symbol,new))
            old=self._result_history.allocation_events_json
            new=tuple(encode(row) for row in public['pipeline']['allocation']['allocation_events'])
            public['pipeline']['allocation']['allocation_events']=[]
            if new[:len(old)]!=old:raise SessionError('V2已有分配历史修订，须新建会话')
            stored+=sum(len(encode(row))+(1 if len(old)+i else 0) for i,row in enumerate(new[len(old):]))
            return V2ResultHistory(tuple(groups),new),stored
        rows, stored = {}, self._history_bytes
        for field in _SHARED_FIELDS:
            old = getattr(self._result_history, field + "_json")
            new = tuple(_json(value) for value in public.pop(field))
            if new[:len(old)] != old:
                raise SessionError("同会话完整历史发生修订，须重新建立会话")
            stored += sum(len(_json(row)) + (1 if len(old) + index else 0)
                          for index, row in enumerate(new[len(old):]))
            rows[field + "_json"] = new
        return ResultHistory(**rows), stored

    def _calculate(self, porter, day, minute):
        started = monotonic()
        self._owner_porter(porter)
        # 原生读取、前缀核对、求值和提交共用本轮窗口，读取之后不能重新起算。
        deadline = started + self._business.budget.max_seconds if self._business is not None else None

        def check():
            if deadline is not None and monotonic() >= deadline:
                raise SessionError("V2完整回调期限耗尽")

        check()
        cutoff = self._clock(day, minute)
        if (not self._initialized or minute != 1500 or day not in self._days
                or (self._last_clock is not None and cutoff <= self._last_clock)
                or len(self._records) >= self._limits.max_calculations):
            raise SessionError("calculate时钟、重复调用或结果条数预算无效")
        self._last_clock = cutoff
        # 按实际原生日期/逐日字段核完全部读取并集，再附回同证券日期的因果辅助。
        for symbol, source in self._series.items():
            check()
            observed = porter.get_bars(symbol, "d1", 4096)
            check()
            expected = []
            for bar in source:
                check()
                if bar.date <= day:
                    expected.append(bar)
            if observed.symbol != symbol or observed.period != "d1" or observed.bars != tuple(expected):
                raise SessionError("原生完整前缀与冻结来源字段/日期失配")
            check()
        observations = []
        for row in self._inputs.history.observations:
            check()
            if row.trade_date <= cutoff.date():
                observations.append(row)
        history = replace(self._inputs.history, observations=tuple(observations))
        check()
        if self._business is not None:
            header,target,daily,end=self._business.evaluate(history,cutoff,deadline=deadline)
            check()
            capture=self._capture(porter,day,minute,daily,check=check)
            check()
            if target is None:
                # 未调用advance；报告保留旧阶段名，实际与pending仍取本次capture。
                self._finish_record(porter,day,minute,header,capture,None,self._state.phase if self._state else None,
                    status='blocked_raw_total',reason='V2原始总权重超过现金模型上限，保留事实并停止新增提交',deadline=end)
            else:
                outcome,previous_status=self._advance(target,capture)
                check()
                self._finish_record(porter,day,minute,header,capture,outcome,previous_status,deadline=end)
            return
        try:
            result = self._evaluate_history(self._inputs.config, history, cutoff, budget=self._kernel_budget)
        except KernelValidationError as exc:
            if exc.code != "insufficient_warmup":
                raise
            record = _pack_record(day, minute, "warming_up", exc.message, None, {
                "header": None, "capture": None, "outcome": None, "previous_status": None,
                "submit_vector": (), "readback": ()})
            self._used_bytes += self._record_size(record)
            self._expanded_bytes += record.payload_bytes
            self._records.append(record)
            return
        allocation_dates = {target.source_allocation_date for target in result.current_targets}
        if len(allocation_dates) != 1:
            raise SessionError("核心完整目标allocation日期不统一")
        allocation = next(iter(allocation_dates))
        target = EconomicTarget(result.strategy_id, result.kernel_version + ":" + result.strategy_version,
                                result.config_sha256, self._inputs.policy.policy_id,
                                allocation.isoformat() if allocation else None, self._execution,
                                tuple(sorted((Weight(row.execution_symbol, repr(row.target_weight))
                                              for row in result.current_targets), key=lambda row: row.symbol)))
        capture = self._capture(porter, day, minute, result.input_sha256)
        outcome, previous_status = self._advance(target, capture)
        self._finish_record(porter,day,minute,result.to_dict(),capture,outcome,previous_status)

    def _finish_record(self,porter,day,minute,header,capture,outcome,previous_status,*,status=None,reason=None,deadline=None):
        def check():
            if deadline is not None and monotonic()>=deadline:raise SessionError('V2求值及报告保留期限耗尽')
        check()
        vector = tuple(Target(self._mapping[row.symbol], row.shares) for row in outcome.submit_targets) if outcome is not None else ()
        if self._business is not None:
            _snapshot_json({'schema':'nsb-v2-prefix-v1','pipeline':header['pipeline'],
                            'signal_trace':header['signal_trace']},maximum=8*1024*1024,check=check)
        shared, history_bytes = self._extend_result_history(header,check=check if deadline is not None else None)
        ends = (tuple(len(rows) for _,rows in shared.decision_series_json)+(len(shared.allocation_events_json),)
                if self._business is not None else tuple(len(getattr(shared,field+'_json')) for field in _SHARED_FIELDS))
        payload = {"header": header, "capture": capture, "outcome": outcome,
                   "previous_status": previous_status, "submit_vector": vector, "readback": ()}
        status,reason=(outcome.status,outcome.reason) if outcome is not None else (status,reason)
        record = _pack_record(day, minute, status, reason, ends, payload)
        self._record_size(record, history_bytes, before_submit=bool(vector))
        check()
        if vector:
            readback = porter.submit_targets(vector, "v2-nsq-session" if self._business is not None else "configured-nsq-session")
            if (type(readback) is not tuple or len(readback) > len(self._execution)
                    or any(type(row) is not tuple or len(row) != 2 or row[0] not in {self._mapping[s] for s in self._execution}
                           or _quantity(row[1]) != row[1] for row in readback)):
                raise SessionError("完整目标提交读回包含未知值")
            payload["readback"] = readback
            record = _pack_record(day, minute, status, reason, ends, payload)
        size = self._record_size(record, history_bytes)
        check()
        self._state = outcome.state if outcome is not None else self._state
        self._result_history, self._history_bytes = shared, history_bytes
        self._used_bytes += size
        self._expanded_bytes += record.payload_bytes
        self._records.append(record)

    def _advance(self, target, capture):
        previous_status = None
        state = self._state
        if state is not None and generation_id(target, self._inputs.policy) != state.generation_id:
            previous = advance(state.target, self._inputs.policy, capture.observation, capture.basis,
                               state, limits=self._quantity_limits)
            previous_status = previous.status
            if previous.status != "converged":
                # 保留旧阶段和理由；旧目标可按NSQ继续执行，新代际尚未接纳。
                return previous, previous_status
            state = previous.state
        return advance(target, self._inputs.policy, capture.observation, capture.basis,
                       state, limits=self._quantity_limits), previous_status

    def _admit_native_files(self, config):
        return admit_native_files(self._mapping, config)

    def run(self, library: Path, abi_probe: Path, config: BacktestConfig) -> SessionReport:
        """同步包装固定原DLL，调用者必须已在自有独占Job中绑定本进程。

        不启动进程、不做硬中断承诺。只有原生正常结束及释放后返回report；等待、
        预热与未收敛保留具体status，ABI/提交未知结果抛出并由外层隔离全部输出。
        """
        if get_ident() != self._owner or self._started or type(config) is not BacktestConfig:
            raise SessionError("run只允许创建owner调用一次")
        self._started = True
        if (type(config.start) is not int or type(config.end) is not int
                or config.end != self._days[-1] * 10000 + 1500
                or config.start // 10000 not in self._days or config.start % 10000 > 1500):
            raise SessionError("回放边界必须覆盖明确冻结末日且起点在完整集合")
        if self._business is not None and config.start//10000!=int(self._business.spec.evaluation_start.strftime('%Y%m%d')):
            raise SessionError('V2回放起点须等于固定评估起点')
        self._native_files, frozen_bytes = self._admit_native_files(config)
        cwd = Path(config.cwd)
        if not cwd.is_absolute() or cwd.resolve() != Path.cwd().resolve():
            raise SessionError("run需要外层预准入的独占绝对CWD")
        # 私有副本由本次owner首次创建；native只加载这些已准入字节。
        directory = cwd / "session-basefiles"
        directory.mkdir(exist_ok=False)
        for name, data in frozen_bytes.items():
            with (directory / (name + ".json")).open("xb") as stream:
                stream.write(data)
        config = replace(config, **{name: directory / (name + ".json") for name in frozen_bytes})
        self._session_id = _digest((self._input_id, str(config.cwd), config.start, config.end,
                                    config.name, self._native_files, ORIGINAL_BT_SHA256, ABI_PROBE_SHA256))
        porter = BacktestPorter(library, ORIGINAL_BT_SHA256, abi_probe, ABI_PROBE_SHA256,
                               symbols=tuple(sorted(self._series)),
                               execution_symbols=tuple(sorted(self._mapping[s] for s in self._execution)),
                               loader=self._loader, callbacks=Callbacks(self._initialize, self._calculate, self._on_bar))
        self._porter = porter
        porter.configure(config)
        try:
            counts = porter.run()
        finally:
            porter.release()
        expected_dates = tuple(day for day in self._days[1:] if day >= config.start // 10000)
        if tuple(record.trading_date for record in self._records) != expected_dates:
            raise SessionError("原生正常结束但闭合calculate日期集合缺失")
        status = self._records[-1].status if self._records else "blocked_no_calculation"
        report_schema = (V2_REPORT_SCHEMA if self._business is not None else
                         HISTORICAL_REPORT_SCHEMA if self._historical_model is not None else REPORT_SCHEMA)
        report_options = {"scope": HISTORICAL_SCOPE} if self._historical_model is not None else {}
        report = SessionReport(self._session_id, status, tuple(self._records), counts,
                               0, self._native_files, self._result_history,
                               schema=report_schema,
                               **report_options)
        if report.result_bytes > self._limits.max_result_bytes:
            raise SessionError("完整报告序列化容量耗尽")
        return report
