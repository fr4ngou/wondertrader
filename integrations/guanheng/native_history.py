"""通过自有有界文件 ABI 调用原 WtDtHelper；DSB 解码由原生 WT 唯一实现。"""
from __future__ import annotations

from .qmt_dat_layout import local_dat_counters_valid
from ..guanheng_market_client.daily_contract import source_daily_symbol, source_daily_security, source_price_basis

from .price_quality import price_range_status, summarize_source_bars, validate_price_quality

import ctypes as C
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import json
import hashlib
import os
from pathlib import Path
import struct
import stat
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .dependencies import digest
from .models import Capability, IntegrationUnavailable, MarketBar, QUALIFICATIONS, SourceSession, positive, symbol


class WTSBar(C.Structure):
    _pack_ = 8
    _fields_ = [("date", C.c_uint32), ("reserve", C.c_uint32), ("time", C.c_uint64)] + [
        (name, C.c_double) for name in ("open", "high", "low", "close", "settle", "money", "vol", "hold", "add")]


BAR_CALLBACK = C.CFUNCTYPE(None, C.POINTER(WTSBar), C.c_uint32, C.c_bool)
COUNT_CALLBACK = C.CFUNCTYPE(None, C.c_uint32)
LOG_CALLBACK = C.CFUNCTYPE(None, C.c_char_p)


def source_date_label(day: datetime):
    """来源日线是八位YYYYMMDD日期标签，固定00:00+08:00，与IANA时刻分开。

    CSV四位年、JSON八位日期整数和WTSBar.date共同可表示1000..9999年。
    本标签不声明收盘/知晓时刻；canonical和分钟继续使用shanghai_time。
    """
    encoded = day.year * 10000 + day.month * 100 + day.day
    if len(str(encoded)) != 8 or day.hour or day.minute or day.second or day.microsecond:
        raise ValueError("来源日线必须为八位有效日期的零点标签")
    return day.replace(tzinfo=timezone(timedelta(hours=8), "Asia/Shanghai"))


def shanghai_time(day: datetime):
    # 1992 年起上海无夏令时；现代证券历史可由标准库明确表达 +08:00。
    # 更早历史必须具有 IANA 规则，避免在精简 Windows 包里静默改变历史时间。
    if day.year >= 1992:
        return timezone(timedelta(hours=8), "Asia/Shanghai")
    try:
        return ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError as exc:
        raise IntegrationUnavailable("1992 年前历史需要外部 IANA 时区资料", "history") from exc


@dataclass(frozen=True)
class HistoryMetadata:
    source: SourceSession
    qualification: str
    dataset_version: str
    content_id: str
    source_license: str
    period: str
    expected_count: int | None
    volume_to_shares: float
    amount_to_yuan: float
    adjustment: str = "none"
    factor_version: str = ""
    minute_boundary: str = "right"
    timezone: str = "Asia/Shanghai"

    def __post_init__(self):
        if not isinstance(self.source, SourceSession):
            raise ValueError("历史来源必须为已校验的活动 SourceSession")
        Capability(True, self.qualification, "历史源资格").require("history")
        if self.period not in ("1m", "5m", "1d") or self.minute_boundary != "right" or self.timezone != "Asia/Shanghai":
            raise ValueError("历史周期、时区或分钟边界尚未支持")
        if self.adjustment not in ("none", "front_ratio") or (self.adjustment != "none" and not self.factor_version):
            raise ValueError("复权方式或因子版本缺失")
        if not self.dataset_version or not self.source_license:
            raise ValueError("历史数据集版本及来源资格必须明确")
        if len(self.content_id) != 64 or any(c not in "0123456789abcdef" for c in self.content_id):
            raise ValueError("历史文件内容身份必须为 SHA-256")
        if self.expected_count is not None and (type(self.expected_count) is not int or self.expected_count < 0):
            raise ValueError("预期记录数不合格")
        positive(self.volume_to_shares, "数量换算")
        positive(self.amount_to_yuan, "金额换算")


@dataclass(frozen=True)
class SourceHistoryBar:
    """源时间标签和原值；单位及区间只由返回的 SourceHistoryMetadata 声明。"""
    symbol: str
    period: str
    occurred_at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float

    @property
    def price_range_status(self):
        """源值质量供策略显式检查；不修改原始四价。"""
        return price_range_status(self.open, self.high, self.low, self.close)


@dataclass(frozen=True)
class SourceHistoryMetadata:
    source: SourceSession  # 该冻结来源的提供者、实例、会话与代际。
    qualification: str  # 原来源验收等级，当前仅DevelopmentVerified。
    dataset_version: str  # 来源格式及派生版本，保持计数与缺失字段语义。
    content_id: str  # 当前读取DSB的SHA256，由调用者读前后核对。
    source_license: str  # 来源许可声明；unknown不提升为开放再分发许可。
    period: str  # 原生周期，1m或1d。
    expected_count: int | None  # 本文件预期bar数；None表示只有读取预算约束。
    price_unit: str  # 原始价格单位CNY或unknown，不执行隐式换算。
    volume_unit: str  # 来源量单位share、lot或unknown；数值保持。
    amount_unit: str  # 来源额单位CNY或unknown；数值保持。
    minute_boundary: str  # 来源分钟边界；日线固定unknown。
    value_semantics: str = "source"  # 保留来源原值。
    timestamp_semantics: str = "source_label"  # 分钟标签或日线交易日期；不授知晓时刻。
    adjustment: str = "none"  # 原来源价格口径；显式日线可保存供应商front_ratio参考，默认none。
    factor_version: str = ""  # none为空；供应商分析价绑定原捕获SHA，不代表独立因子已验证。
    timezone: str = "Asia/Shanghai"  # 来源标签解释时区。
    price_range_inconsistent_rows: int = 0  # 明确记录的OHLC异常行数，默认0。

    def __post_init__(self):
        if (not isinstance(self.source, SourceSession) or self.source.provider not in ("Qmt", "BaoStock", "Tencent", "CSI")
                or (self.source.provider != "Qmt" and self.period != "1d")
                or self.qualification != "DevelopmentVerified" or self.period not in ("1m", "1d")
                or self.value_semantics != "source"
                or (self.period == "1m" and self.timestamp_semantics != "source_label")
                or (self.period == "1d" and (self.timestamp_semantics != "source_date" or self.minute_boundary != "unknown"))
                or not source_price_basis(self.adjustment, self.factor_version,
                    allow_reference=self.period == "1d" and self.source.provider == "Qmt")
                or self.timezone != "Asia/Shanghai"
                or self.price_unit not in ("CNY", "unknown") or self.amount_unit not in ("CNY", "unknown")
                or self.volume_unit not in ("share", "lot", "unknown")
                or self.minute_boundary not in ("left", "right", "unknown")
                or (self.expected_count is not None and
                    (type(self.expected_count) is not int or not 1 <= self.expected_count <= 1000000))
                or type(self.price_range_inconsistent_rows) is not int
                or not 0 <= self.price_range_inconsistent_rows <= (self.expected_count or 0)):
            raise ValueError("来源历史语义不合格")
        for value in (self.dataset_version, self.source_license):
            _source_text(value, 256)
        for value in (self.source.instance_id, self.source.session_id):
            _source_text(value, 128)
        _source_hash(self.content_id)


def source_file_metadata(metadata, content_id, expected_count, *, decoding_version=None, quality=None):
    """原生文件读取的唯一来源头构造；CSV身份与当前DSB字节身份分别保留。

    复合归档可声明自身解码布局版本；原段来源/单位/复权继续由metadata拥有。
    quality仅赋已绑定文件的异常行计数，缺项保持严格零异常准入。
    """
    values = {key: metadata[key] for key in ('qualification', 'dataset_version', 'source_license', 'period',
        'price_unit', 'volume_unit', 'amount_unit', 'minute_boundary', 'value_semantics',
        'timestamp_semantics', 'adjustment', 'factor_version', 'timezone')}
    if decoding_version is not None:
        values['dataset_version'] = decoding_version
    return SourceHistoryMetadata(
        source=SourceSession(**metadata['source']),  # 原提供者/实例/会话/代际，与WT当前目录版本区分。
        content_id=content_id,  # 正在读取的DSB完整SHA，非CSV原件身份。
        expected_count=expected_count,  # 该冻结文件实际记录条数，原生解压前校验。
        price_range_inconsistent_rows=quality['inconsistent_rows'] if quality is not None else 0,
        # 上述计数只授绑定文件的原OHLC质量声明，缺项保持严格原行为。
        **values)


def _source_hash(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("来源历史摘要不合格")
    return value


def _source_text(value, limit):
    if (not isinstance(value, str) or not value.strip() or not 1 <= len(value) <= limit
            or any(ord(c) < 32 or 0x7F <= ord(c) <= 0x9F or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise ValueError("来源历史文本不合格")


def _source_keys(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError("来源历史字段不合格")


def _source_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("来源历史重复字段")
            out[key] = value
        return out

    def constant(unused):
        raise ValueError("来源历史非有限 JSON 数值")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("来源历史 JSON 不合格") from exc


def _source_bytes(path, limit):
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("来源历史输入必须为普通文件")
        raw = stream.read(min(limit, os.fstat(stream.fileno()).st_size) + 1)
    if len(raw) > limit:
        raise ValueError("来源历史文件超过预算")
    return raw


@dataclass(frozen=True)
class HistoryResult:
    bars: tuple
    metadata: HistoryMetadata | SourceHistoryMetadata
    coverage: str
    missing: tuple[datetime, ...]
    calendar_version: str


def _parse_source_receipt(receipt_raw):
    """完整准入一次收据并建立证券索引；直接读取与冻结读取共用同一规则。"""
    receipt = _source_json(receipt_raw)
    daily = receipt.get("schema_version") in (3, 4)
    _source_keys(receipt, "schema_version status qualification coverage manifest_sha256 helper_sha256 profile securities"
        + (" period" if daily else ""))
    if (type(receipt["schema_version"]) is not int or receipt["schema_version"] not in (2, 3, 4)
            or (daily and receipt["period"] != "1d")
            or receipt["status"] != "passed" or receipt["qualification"] != "DevelopmentVerified"
            or receipt["coverage"] != "unknown"):
        raise ValueError("来源导入收据未完成或版本不合格")
    _source_hash(receipt["manifest_sha256"])
    _source_hash(receipt["helper_sha256"])
    profile = receipt["profile"]
    _source_keys(profile, "provider instance_id session_id generation dataset_version source_license input_kind timezone minute_boundary adjustment factor_version value_semantics price_unit volume_unit amount_unit")
    if (profile["provider"] != "Qmt" or profile["input_kind"] not in ("synthetic", "qmt_export")
            or not source_price_basis(profile["adjustment"], profile["factor_version"],
                allow_reference=receipt["schema_version"] == 4)):
        raise ValueError("来源导入 profile 不合格")
    source = SourceSession(profile["provider"], profile["instance_id"], profile["session_id"], profile["generation"])
    entries = receipt["securities"]
    if type(entries) is not list or not 1 <= len(entries) <= 10000:
        raise ValueError("来源导入证券清单不合格")
    indexed, seen, chunk_count = {}, set(), 0
    for entry in entries:
        _source_keys(entry, "symbol exchange code path sha256 metadata_path metadata_sha256 count chunks first_label last_label"
            + (" price_range_quality" if "price_range_quality" in entry else ""))
        entry_symbol = source_daily_symbol(entry["symbol"], allow_bse=receipt["schema_version"] == 4)
        if entry_symbol in seen:
            raise ValueError("来源导入证券重复")
        seen.add(entry_symbol)
        entry_code, suffix = entry_symbol.split(".")
        entry_exchange = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}[suffix]
        storage = "day" if daily else "min1"
        relative = f"his/{storage}/{entry_exchange}/{entry_code}.dsb"
        if (entry["code"] != entry_code or entry["exchange"] != entry_exchange
                or entry["path"] != relative or entry["metadata_path"] != relative + ".metadata.json"
                or type(entry["count"]) is not int or not 1 <= entry["count"] <= 1000000):
            raise ValueError("来源导入证券路径或记录数错配")
        _source_hash(entry["sha256"])
        _source_hash(entry["metadata_sha256"])
        for key in ("first_label", "last_label"):
            _source_text(entry[key], 32)
        if type(entry["chunks"]) is not list or not entry["chunks"]:
            raise ValueError("来源导入分片缺失")
        chunk_count += len(entry["chunks"])
        if chunk_count > 10000:
            raise ValueError("来源导入分片超过预算")
        for chunk in entry["chunks"]:
            _source_keys(chunk, "path sha256")
            _source_text(chunk["path"], 4096)
            _source_hash(chunk["sha256"])
        indexed[entry_symbol] = entry
    return profile, source, daily, indexed


@dataclass(frozen=True)
class _SourceReceiptIndex:
    receipt_hash: str  # 原成功收据完整SHA，固定本次读取事实。
    profile: dict  # 已准入的原来源profile，Reader内部独占，不交给调用者修改。
    source: SourceSession  # 原采集或导入会话，不由缓存产生新来源身份。
    daily: bool  # 原收据周期是否为日线；分钟保持原规则。
    entries: dict  # 原供应商证券到已准入原记录的索引，无调用者别名。
    lease: object | None  # Windows只读、禁止写入/删除的文件句柄，归NativeHistory关闭。
    bytes: int  # 收据原字节数，用于Reader总索引额度。


def _pin_source_receipt(path):
    """冻结Windows成功收据；允许并发只读，保持物理文件不可替换或改写。"""
    import msvcrt
    kernel=C.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW
    create.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p]
    create.restype=C.c_void_p
    handle=create(str(path),0x80000000,1,None,3,0x80,None)
    if handle==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
    try:descriptor=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
    except BaseException:
        kernel.CloseHandle.argtypes=[C.c_void_p];kernel.CloseHandle(handle);raise
    try:return os.fdopen(descriptor,'rb')
    except BaseException:os.close(descriptor);raise


class NativeHistory:
    """同步读取外部已准备文件；调用者在受管 worker 使用，限制文件/条数预算。

    library_sha256 来自受管制品清单。仅接受当前 ABI 的 v2 DSB；回调内复制并校验，
    返回值包含来源证据。数据必须处于受控冻结目录，原生解压分配由 WT 库拥有。
    """

    def __init__(self, library: Path, library_sha256: str, *, max_bars: int, max_file_bytes: int):
        if type(max_bars) is not int or not 1 <= max_bars <= 1000000:
            raise ValueError("历史记录预算不合格")
        if type(max_file_bytes) is not int or not 20 <= max_file_bytes <= 268435456:
            raise ValueError("历史文件预算不合格")
        self.library = Path(library).resolve()
        self.max_bars, self.max_file_bytes = max_bars, max_file_bytes
        self._dll_directory = None
        self._receipt_indexes = {}  # 当前拥有线程的冻结收据索引；不缓存可变收据。
        self._receipt_index_bytes = 0  # 冻结原件总字节，硬上限16MiB，与source-catalog准入一致。
        try:
            if digest(self.library) != library_sha256:
                raise ValueError("自有历史文件适配制品摘要变化")
            if C.sizeof(WTSBar) != 88:
                raise ValueError("WTSBarStruct ABI 不匹配")
            if os.name == "nt":
                self._dll_directory = os.add_dll_directory(str(self.library.parent))
            self.native = C.CDLL(str(self.library))
            # 自有导出与原 Helper 分开；版本、结构布局和制品摘要共同确认调用身份。
            self.native.gh_native_bar_file_version.argtypes = []
            self.native.gh_native_bar_file_version.restype = C.c_uint32
            self.native.gh_native_bar_file_layout.argtypes = [C.c_uint32]
            self.native.gh_native_bar_file_layout.restype = C.c_uint32
            actual = [self.native.gh_native_bar_file_layout(i) for i in range(5)]
            expected = [C.sizeof(WTSBar), WTSBar.date.offset, WTSBar.time.offset,
                        WTSBar.open.offset, WTSBar.add.offset]
            if self.native.gh_native_bar_file_version() != 1 or actual != expected:
                raise ValueError("自有历史文件 ABI 版本或结构布局不匹配")
            self.native.gh_native_bar_file_read.argtypes = [C.c_wchar_p, C.c_char_p,
                C.c_uint32, C.c_uint32, C.c_uint32, BAR_CALLBACK, COUNT_CALLBACK, LOG_CALLBACK]
            self.native.gh_native_bar_file_read.restype = C.c_uint32
        except (OSError, ValueError, AttributeError) as exc:
            self.close()
            raise IntegrationUnavailable("原生历史依赖不可用：" + str(exc), "history") from exc

    def close(self):
        for index in self._receipt_indexes.values():
            if index.lease is not None:index.lease.close()
        self._receipt_indexes.clear()
        self._receipt_index_bytes = 0
        if self._dll_directory is not None:
            self._dll_directory.close()
            self._dll_directory = None

    def _admit_source_receipt(self, root, expected):
        """固定SHA的Windows商店完整准入一次；可变/无固定SHA读取继续逐次核验。"""
        key=(root,_source_hash(expected))if expected is not None else None
        if key in self._receipt_indexes:return self._receipt_indexes[key]
        path=root/'qmt-import.json';lease=None
        try:
            if key is not None and os.name=='nt':lease=_pin_source_receipt(path)
            raw=_source_bytes(path,self.max_file_bytes);identity=hashlib.sha256(raw).hexdigest()
            if expected is not None and identity!=expected:raise ValueError('来源导入收据身份不匹配')
            profile,source,daily,entries=_parse_source_receipt(raw)
            index=_SourceReceiptIndex(identity,profile,source,daily,entries,lease,len(raw))
            if lease is not None:
                if self._receipt_index_bytes+len(raw)>16*1024*1024 or len(self._receipt_indexes)>=1024:
                    raise ValueError('来源收据索引超过读取预算')
                self._receipt_indexes[key]=index;self._receipt_index_bytes+=len(raw);lease=None
            return index
        finally:
            if lease is not None:lease.close()

    def read_store(self, root: Path, exchange: str, code: str, market_bar_type=MarketBar, *,
                   expected_times=(), calendar_version=""):
        """消费 History.h 的 min1 存储和 format=1 sidecar；导入源换算仅作证据保留。

        NativeHistoryStore 在写 DSB 前已统一数量股/金额元，本出口保持已存值。
        sidecar 没有记录数承诺，count callback 与实际回调/返回值进行完整性核对。
        """
        if exchange not in ("SSE", "SZSE"):
            raise ValueError("未知 WT 证券交易所")
        security = symbol(code + (".SH" if exchange == "SSE" else ".SZ"))
        path = Path(root).resolve() / "his" / "min1" / exchange / (code + ".dsb")
        sidecar = path.with_suffix(".dsb.metadata.json")
        if sidecar.stat().st_size > 65536:
            raise ValueError("历史来源元数据超限")
        sidecar_sha256 = digest(sidecar)
        marker = Path(root).resolve() / ".guanheng-frozen"
        if marker.exists():
            if marker.stat().st_size > 256:
                raise ValueError("冻结历史身份文件超限")
            identities = marker.read_text(encoding="ascii").splitlines()
            if len(identities) != 2 or identities != [digest(path), sidecar_sha256]:
                raise ValueError("冻结历史内容或来源元数据发生修订")
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        required = {"format", "provider", "instance_id", "session_id", "generation", "qualification",
                    "dataset_version", "source_license", "adjustment", "factor_version", "minute_boundary",
                    "timezone", "volume_to_shares", "amount_to_yuan", "content_id"}
        if set(data) != required or type(data["format"]) is not int or data["format"] != 1:
            raise ValueError("历史来源元数据字段或版本不合格")
        if (type(data["provider"]) is not int or data["provider"] not in (0, 1)
                or type(data["qualification"]) is not int or not 0 <= data["qualification"] <= 3):
            raise ValueError("历史来源枚举不合格")
        metadata = HistoryMetadata(
            SourceSession(("Qmt", "Tdx")[data["provider"]], data["instance_id"], data["session_id"], data["generation"]),
            QUALIFICATIONS[data["qualification"]], data["dataset_version"], data["content_id"],
            data["source_license"], "1m", None, data["volume_to_shares"], data["amount_to_yuan"],
            data["adjustment"], data["factor_version"], data["minute_boundary"], data["timezone"])
        result = self.read(path, security, metadata, market_bar_type,
                           expected_times=expected_times, calendar_version=calendar_version)
        if digest(sidecar) != sidecar_sha256:
            raise ValueError("历史读取期间来源元数据发生修订")
        return result

    def read(self, path: Path, security: str, metadata: HistoryMetadata, market_bar_type=MarketBar, *,
             expected_times=(), calendar_version: str = "") -> HistoryResult:
        """返回原 MarketBar DTO；覆盖 complete 需要显式预期时点及其日历版本。"""
        if not isinstance(metadata, HistoryMetadata):
            raise ValueError("canonical 历史入口需要 canonical 元数据")
        return self._read(path, security, metadata, market_bar_type,
                          expected_times=expected_times, calendar_version=calendar_version)

    def read_source_store(self, root: Path, exchange: str, code: str, *, expected_import_sha256=None) -> HistoryResult:
        """相对成功收据核源值；独立 expected_import_sha256 才绑定读前整套替换。"""
        if exchange not in ("SSE", "SZSE", "BSE"):
            raise ValueError("未知 WT 证券交易所")
        security = source_daily_security(exchange, code)
        root = Path(root).resolve(strict=True)
        receipt_path = root / "qmt-import.json"
        index = self._admit_source_receipt(root, expected_import_sha256)
        receipt_hash, profile, source, daily = index.receipt_hash, index.profile, index.source, index.daily
        selected = index.entries.get(security)
        if selected is None:
            raise ValueError("来源导入收据缺少证券")
        path = root / selected["path"]
        sidecar = root / selected["metadata_path"]
        if not path.resolve(strict=True).is_relative_to(root) or not sidecar.resolve(strict=True).is_relative_to(root):
            raise ValueError("来源历史路径越界")
        metadata_raw = _source_bytes(sidecar, 65536)
        if hashlib.sha256(metadata_raw).hexdigest() != selected["metadata_sha256"]:
            raise ValueError("来源元数据与导入收据不匹配")
        data = _source_json(metadata_raw)
        expected = {key: profile[key] for key in ("instance_id", "session_id", "generation", "dataset_version", "source_license", "adjustment", "factor_version", "timezone", "value_semantics", "price_unit", "volume_unit", "amount_unit", "minute_boundary")}
        expected.update(format=2, provider=0, qualification=1, timestamp_semantics="source_label", content_id=selected["sha256"])
        if daily:
            expected.update(format=3, period="1d", timestamp_semantics="source_date")
        quality = selected.get("price_range_quality")
        if quality is not None:
            # 摘要与DSB一同绑定原成功收据，回读后再逐条重算比较。
            validate_price_quality(quality, selected["count"])
            expected["price_range_quality"] = quality
        if data != expected or any(type(data.get(key)) is not int for key in ("format", "provider", "qualification", "generation")):
            raise ValueError("来源元数据与收据 profile 不匹配")
        metadata = SourceHistoryMetadata(source, "DevelopmentVerified", profile["dataset_version"], selected["sha256"],
            profile["source_license"], "1d" if daily else "1m", selected["count"], profile["price_unit"], profile["volume_unit"],
            profile["amount_unit"], profile["minute_boundary"], profile["value_semantics"], data["timestamp_semantics"],
            profile["adjustment"], profile["factor_version"], profile["timezone"],
            quality["inconsistent_rows"] if quality is not None else 0)
        result = self._read(path, security, metadata, SourceHistoryBar)
        if quality is not None and summarize_source_bars(result.bars) != quality:
            raise ValueError("来源价格质量与实际历史记录不匹配")
        if (result.bars[0].occurred_at.isoformat() != selected["first_label"]
                or result.bars[-1].occurred_at.isoformat() != selected["last_label"]):
            raise ValueError("来源历史标签与收据不匹配")
        if ((index.lease is None and hashlib.sha256(_source_bytes(receipt_path, self.max_file_bytes)).hexdigest() != receipt_hash)
                or hashlib.sha256(_source_bytes(sidecar, 65536)).hexdigest() != selected["metadata_sha256"]):
            raise ValueError("来源历史读取期间收据或元数据变化")
        return result

    def read_source_file(self, path: Path, security: str, metadata: SourceHistoryMetadata) -> HistoryResult:
        """读取原Writer归档；不将采集文件伪装为QMT导入成功收据。

        调用方绑定当前文件SHA和采集数据集来源。Writer不登记预期行数时传None，
        原文件ABI负责解压前的条数预算及完整回调；已导入商店仍沿其精确count校验。
        """
        if not isinstance(metadata, SourceHistoryMetadata):
            raise ValueError("来源文件读取需要显式source元数据")
        return self._read(path, security, metadata, SourceHistoryBar)

    def _read(self, path, security, metadata, market_bar_type, *, expected_times=(), calendar_version=""):
        """两个显式语义入口共用唯一文件 ABI 和回调解码内核。"""
        if isinstance(metadata, SourceHistoryMetadata) and metadata.period == "1d":
            source_daily_symbol(security)
        else:
            symbol(security)
        path = Path(path).resolve(strict=True)
        if (metadata.expected_count is not None and metadata.expected_count > self.max_bars) or path.stat().st_size > self.max_file_bytes:
            raise ValueError("历史读取超过受管预算")
        if digest(path) != metadata.content_id:
            raise ValueError("历史文件与冻结内容身份不符")
        with path.open("rb") as stream:
            header = stream.read(20)
        if len(header) < 20:
            raise ValueError("DSB 头部截断")
        flag, kind, version, size = struct.unpack("<8sHHQ", header)
        if flag != b"&^%$#@!\0" or kind != {"1m": 21, "5m": 22, "1d": 23}[metadata.period] or version != 4:
            raise ValueError("DSB 类型或版本与登记历史不符")
        if size != path.stat().st_size - 20:
            raise ValueError("DSB 压缩体长度不符")
        bars, counts, failures = [], [], []

        @COUNT_CALLBACK
        def count(value):
            counts.append(value)
            if (metadata.expected_count is not None and value != metadata.expected_count) or value > self.max_bars:
                failures.append("原生记录数与清单或预算不符")

        @BAR_CALLBACK
        def receive(pointer, length, last):
            try:
                if failures:
                    return
                if not pointer or not last or len(bars) + length > self.max_bars:
                    raise ValueError("原生回调边界不合格")
                for index in range(length):
                    row = WTSBar.from_buffer_copy(pointer[index])
                    values = [getattr(row, field) for field in ("open", "high", "low", "close", "vol", "money")]
                    if any(not math.isfinite(v) for v in values):
                        raise ValueError("历史值必须为有限数")
                    if min(row.open, row.high, row.low, row.close) <= 0 or min(row.vol, row.money) < 0:
                        raise ValueError("历史价格或量额不合格")
                    if isinstance(metadata, SourceHistoryMetadata) and not local_dat_counters_valid(metadata.dataset_version, row.vol, row.money):
                        raise ValueError("QMT DAT历史计数字段存在旧符号回绕或超出布局")
                    # 只有已绑定质量声明的source存储可保留异常原值；canonical与旧无声明源仍严格检查。
                    annotated_source = isinstance(metadata, SourceHistoryMetadata) and metadata.price_range_inconsistent_rows > 0
                    if not annotated_source and price_range_status(row.open, row.high, row.low, row.close) != "consistent":
                        raise ValueError("历史 OHLC 不一致")
                    day = datetime.strptime(str(row.date), "%Y%m%d")
                    if metadata.period == "1d":
                        # source-date保留日期；canonical沿原15:00右端合同。
                        # 知晓/闭合时间由来源证据另外提供，不能从日期字段虚构。
                        if isinstance(metadata, SourceHistoryMetadata):
                            if row.time != 0 or len(str(row.date)) != 8:
                                raise ValueError("原生源日线日期布局不合格")
                            stamp = source_date_label(day)
                        else:
                            stamp = day.replace(hour=15, tzinfo=shanghai_time(day))
                    else:
                        encoded_day, hm = divmod(row.time, 10000)
                        if encoded_day + 19900000 != row.date:
                            raise ValueError("WT 分钟日期与交易日期不符")
                        hour, minute = divmod(hm, 100)
                        stamp = day.replace(hour=hour, minute=minute, tzinfo=shanghai_time(day))
                    if bars and stamp <= bars[-1].occurred_at:
                        raise ValueError("历史时间重复或倒序")
                    bars.append(market_bar_type(symbol=security, period=metadata.period, occurred_at=stamp,
                        open=row.open, high=row.high, low=row.low, close=row.close,
                        volume=row.vol, amount=row.money))
            except Exception as exc:
                failures.append(str(exc))

        native_reasons = []

        @LOG_CALLBACK
        def logger(reason):
            # 只接收自有ABI的固定分类；日志不复制原始路径或配置。
            allowed = (b"native_file_busy", b"native_read_budget_exceeded", b"native_read_validation_failed")
            if reason in allowed and not native_reasons:
                native_reasons.append(reason.decode("ascii"))
        # 文件所有者在同一句柄下核 SHA，并让原 Helper 读取不可变私有快照。
        returned = self.native.gh_native_bar_file_read(str(path), metadata.content_id.encode("ascii"),
            self.max_bars, self.max_file_bytes, {"1m": 21, "5m": 22, "1d": 23}[metadata.period], receive, count, logger)
        if (failures or returned == 0 or counts != [returned] or returned != len(bars)
                or (metadata.expected_count is not None and returned != metadata.expected_count)):
            reason = failures[0] if failures else (native_reasons[0] if native_reasons else "记录或回调不完整")
            raise ValueError("原生历史读取失败：" + reason)
        if digest(path) != metadata.content_id:
            raise ValueError("历史读取期间文件发生修订")
        expected = tuple(expected_times)
        if any(t.tzinfo is None for t in expected) or len(expected) != len(set(expected)):
            raise ValueError("预期时点必须带时区且唯一")
        if expected and not calendar_version:
            raise ValueError("确认覆盖需要预期交易时点的版本依据")
        actual = {b.occurred_at for b in bars}
        missing = tuple(sorted(set(expected) - actual))
        coverage = ("gaps" if missing else "complete") if expected else "unknown"
        return HistoryResult(tuple(bars), metadata, coverage, missing, calendar_version)
