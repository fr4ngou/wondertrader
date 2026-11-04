"""将显式分钟/日线CSV转为WT原生历史；不读取厂商缓存或连接账户。"""
from __future__ import annotations

from .price_quality import PriceRangeQuality, price_range_status
from ..guanheng_market_client.daily_contract import source_price_basis
from .qmt_dat_layout import local_dat_counters_valid

import argparse
import csv
import ctypes as C
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

from .native_history import BAR_CALLBACK, COUNT_CALLBACK, LOG_CALLBACK, WTSBar, source_date_label


class ImportFailure(ValueError):
    """安全错误类别及说明；不包含来源行、路径内容或原生日志。"""

    def __init__(self, category, message):
        self.category = category
        super().__init__(message)


def _fail(message, category="input"):
    raise ImportFailure(category, message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _read(path, maximum):
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            _fail("输入必须为普通文件")
        data = stream.read(min(maximum, os.fstat(stream.fileno()).st_size) + 1)
    if len(data) > maximum:
        _fail("输入字节数超过预算", "budget")
    return data


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected.split()):
        _fail("输入字段或版本不合格")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("JSON 字段重复")
        result[key] = value
    return result


def _text(value, maximum=256):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F
                   or 0xD800 <= ord(char) <= 0xDFFF for char in value)):
        _fail("身份、版本或许可字段不合格")


def _number(value, *, positive=False):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and (not positive or value > 0)
    except OverflowError:
        valid = False
    if not valid:
        _fail("数量换算必须为正有限数")
    return float(value)


def _hash(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail("SHA-256 身份不合格")


def _chunk_path(base, value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        _fail("分片必须为普通相对路径")
    parts = PurePosixPath(value)
    if parts.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        _fail("分片路径越界")
    current = base
    for part in parts.parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            _fail("分片路径包含符号链接或重解析点")
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(base):
        _fail("分片路径越界")
    return resolved


def _json(data):
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=lambda unused: _fail("JSON 数值不合格"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail("manifest 编码或 JSON 不合格")


def _manifest(data, base):
    document = _json(data)
    daily = type(document) is dict and document.get("schema_version") in (3, 4)
    _keys(document, "schema_version profile securities" + (" period" if daily else ""))
    if type(document["schema_version"]) is not int or document["schema_version"] not in (1, 2, 3, 4):
        _fail("manifest 版本不合格")
    if daily and document["period"] != "1d":
        _fail("源日线周期不合格")
    profile = document["profile"]
    source_values = document["schema_version"] in (2, 3, 4)
    _keys(profile, "provider instance_id session_id generation dataset_version source_license input_kind timezone minute_boundary adjustment factor_version " +
          ("value_semantics price_unit volume_unit amount_unit" if source_values else "volume_to_shares amount_to_yuan"))
    for key in ("instance_id", "session_id", "dataset_version", "source_license"):
        _text(profile[key], 128 if key in ("instance_id", "session_id") else 256)
    if (profile["provider"] != "Qmt" or profile["input_kind"] not in ("synthetic", "qmt_export")
            or profile["timezone"] != "Asia/Shanghai"
            or profile["minute_boundary"] not in (("left", "right", "unknown") if source_values else ("left", "right"))
            or not source_price_basis(profile["adjustment"], profile["factor_version"],
                allow_reference=document["schema_version"] == 4)
            or type(profile["generation"]) is not int or not 1 <= profile["generation"] <= 2**64 - 1):
        _fail("来源、分钟边界、复权或代次声明不合格")
    if source_values:
        if (profile["value_semantics"] != "source" or profile["price_unit"] not in ("CNY", "unknown")
                or profile["amount_unit"] not in ("CNY", "unknown")
                or profile["volume_unit"] not in ("share", "lot", "unknown")):
            _fail("来源数值语义或单位不合格")
        if daily and profile["minute_boundary"] != "unknown":
            _fail("源日线必须保留交易日期语义")
    else:
        _number(profile["volume_to_shares"], positive=True)
        _number(profile["amount_to_yuan"], positive=True)
    securities = document["securities"]
    if type(securities) is not list or not 1 <= len(securities) <= 10000:
        _fail("证券数量不合格")
    seen, chunks = set(), 0
    for security in securities:
        _keys(security, "symbol chunks")
        symbol = security["symbol"]
        pattern = r"[0-9]{6}\.(SH|SZ|BJ)" if document["schema_version"] == 4 else r"[0-9]{6}\.(SH|SZ)"
        if not isinstance(symbol, str) or re.fullmatch(pattern, symbol) is None or symbol in seen:
            _fail("证券身份重复或不合格")
        seen.add(symbol)
        if type(security["chunks"]) is not list or not security["chunks"]:
            _fail("每个证券必须声明分片")
        chunks += len(security["chunks"])
        if chunks > 10000:
            _fail("分片总数超过预算", "budget")
        for chunk in security["chunks"]:
            _keys(chunk, "path sha256")
            _hash(chunk["sha256"])
            _chunk_path(base, chunk["path"])
    return document


def _rows(data, profile, previous, remaining, *, period="1m"):
    source_values = profile.get("value_semantics") == "source"
    if period not in ("1m", "1d"):
        _fail("导入周期不合格")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        if next(reader, None) != ["timestamp", "open", "high", "low", "close", "volume", "amount"]:
            _fail("CSV 表头不合格")
        rows, first, last = [], None, previous
        for fields in reader:
            if len(rows) >= remaining:
                _fail("历史记录数超过预算", "budget")
            if len(fields) != 7 or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\+08:00", fields[0]) is None:
                _fail("分钟时间或 CSV 列数不合格")
            stamp = datetime.fromisoformat(fields[0])
            if period == "1d" and (not source_values or stamp.hour or stamp.minute):
                _fail("源日线必须使用交易日期零点标签")
            if period == "1d":
                stamp = source_date_label(stamp)
            elif not 1992 <= stamp.year <= 2099:
                _fail("历史日期超出支持范围")
            if not source_values and profile["minute_boundary"] == "left":
                right = stamp + timedelta(minutes=1)
                if right.date() != stamp.date():
                    _fail("左端分钟转换跨日")
                stamp = right
            if last is not None and stamp <= last:
                _fail("分钟时间重复或倒序")
            values = [float(value) for value in fields[1:]]
            op, high, low, close, volume, money = values
            if (not all(math.isfinite(value) for value in values) or min(values[:4]) <= 0
                    or min(volume, money) < 0):
                _fail("价格、OHLC 或量额不合格")
            if source_values and not local_dat_counters_valid(profile["dataset_version"], volume, money):
                _fail("QMT DAT计数字段超出已核布局或存在旧符号回绕", "quantity")
            # canonical保持标准OHLC；source原值由独立质量摘要如实标识。
            if not source_values and price_range_status(op, high, low, close) != "consistent":
                _fail("价格、OHLC 或量额不合格")
            if not source_values:
                volume *= profile["volume_to_shares"]
                money *= profile["amount_to_yuan"]
            if not math.isfinite(volume) or not math.isfinite(money):
                _fail("转换后量额超出有限范围")
            day = int(stamp.strftime("%Y%m%d"))
            row = WTSBar(date=day, time=0 if period == "1d" else (day - 19900000) * 10000 + stamp.hour * 100 + stamp.minute,
                         open=op, high=high, low=low, close=close, settle=close, money=money, vol=volume)
            rows.append(row)
            if first is None:
                first = stamp
            last = stamp
        return rows, first, last
    except (UnicodeError, csv.Error, ValueError, OverflowError) as exc:
        if isinstance(exc, ImportFailure):
            raise
        _fail("CSV 编码、日期或数值不合格")


class _Native:
    """只回读本次有界生成文件；回调数据在 native 返回前逐字段比对。"""

    def __init__(self, helper, identity):
        self.directory = None
        _hash(identity)
        self.helper = Path(helper).resolve(strict=True)
        if _digest(self.helper) != identity or C.sizeof(WTSBar) != 88:
            _fail("原生制品身份或 ABI 不匹配", "dependency")
        try:
            if os.name == "nt":
                self.directory = os.add_dll_directory(str(self.helper.parent))
            self.lib = C.CDLL(str(self.helper))
            self.lib.store_bars.argtypes = [C.c_char_p, C.POINTER(WTSBar), C.c_int, C.c_char_p, LOG_CALLBACK]
            self.lib.store_bars.restype = C.c_bool
            self.lib.read_dsb_bars.argtypes = [C.c_char_p, BAR_CALLBACK, COUNT_CALLBACK, LOG_CALLBACK]
            self.lib.read_dsb_bars.restype = C.c_uint32
            if _digest(self.helper) != identity:
                _fail("加载期间原生制品身份变化", "dependency")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.directory is not None:
            self.directory.close()
            self.directory = None

    def write_verify(self, path, rows, *, period="1m"):
        if period not in ("1m", "1d"):
            _fail("原生写入周期不合格")
        array = (WTSBar * len(rows))(*rows)
        logger = LOG_CALLBACK(lambda unused: None)
        # 历史 bool 实现不能单独证明落盘；文件与完整回读共同构成成功条件。
        self.lib.store_bars(os.fsencode(path), array, len(rows), b"d" if period == "1d" else b"m1", logger)
        if not path.is_file():
            _fail("原生历史写入未产生文件", "native")
        self.verify(path, rows, period=period)

    def verify(self, path, rows, *, period="1m"):
        """只读核对已写文件与本次原输入；供独占离线导入的中断续接共用。"""
        import struct
        with path.open('rb')as stream:header=stream.read(20)
        if len(header)!=20:
            _fail("原生历史文件头未完整写出", "native")
        flag,kind,version,size=struct.unpack('<8sHHQ',header)
        if (flag!=b'&^%$#@!\0'or version!=4 or kind!={'1m':21,'1d':23}[period]
                or size!=path.stat().st_size-20):
            _fail("原生历史文件类型或长度不符", "native")
        logger = LOG_CALLBACK(lambda unused: None)
        counts, events, failures, offset = [], [], [], 0

        @COUNT_CALLBACK
        def count(value):
            try:
                counts.append(value)
                if value != len(rows):
                    failures.append(True)
            except Exception:
                failures.append(True)

        @BAR_CALLBACK
        def bars(pointer, length, last):
            nonlocal offset
            try:
                events.append(bool(last))
                if failures or not pointer or length == 0 or offset + length > len(rows):
                    failures.append(True)
                    return
                for index in range(length):
                    actual, expected = pointer[index], rows[offset + index]
                    if any(getattr(actual, field) != getattr(expected, field) for field, unused in WTSBar._fields_):
                        failures.append(True)
                        return
                offset += length
            except Exception:
                failures.append(True)

        returned = self.lib.read_dsb_bars(os.fsencode(path), bars, count, logger)
        if (failures or counts != [len(rows)] or returned != len(rows) or offset != len(rows)
                or not events or events[-1] is not True or any(events[:-1])):
            _fail("原生历史回读字段或回调不完整", "native")


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def _write_json(path, value):
    data = _json_bytes(value)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return _sha(data)


def import_dataset(manifest, output_root, helper, helper_sha256, *, max_bars=1000000,
                   max_input_bytes=268435456, max_total_bars=10000000,
                   resume_manifest_sha256=None) -> dict:
    """同步导入一个显式清单；输出新根，成功收据最后落盘，失败根保留诊断。

    v1量额转股/元和右端分钟；v2保留源分钟；v3保留源交易日期；v4显式保存
    三市场原价或供应商前复权日线参考。只产生开发资格、
    coverage=unknown。输入和原生失败抛出安全 ImportFailure。
    resume_manifest_sha256仅用于调用方已确认关闭、独占的未成功输出根，
    必须等于原输入清单SHA。逐证券沿同一CSV/原生字段验证复用，成功根不可续写。
    缺sidecar的不完整DSB保留为.interrupted，再原子写出完整证券；完整文件不改写。
    """
    native = None
    try:
        for value, maximum in ((max_bars, 1000000), (max_input_bytes, 268435456), (max_total_bars, 10000000000)):
            if type(value) is not int or not 1 <= value <= maximum:
                _fail("导入预算不合格", "budget")
        manifest = Path(manifest).resolve(strict=True)
        source = _read(manifest, 4 * 1024 * 1024)
        document = _manifest(source, manifest.parent)
        root = Path(output_root).absolute()
        resuming = resume_manifest_sha256 is not None
        if resuming:
            _hash(resume_manifest_sha256)
            if (_sha(source) != resume_manifest_sha256 or not root.is_dir()
                    or (root / "qmt-import.json").exists()):
                _fail("续接清单或未完成根身份不合格", "target")
        else:
            try:
                root.mkdir(parents=False, exist_ok=False)
            except FileExistsError:
                _fail("目标根已存在，请选择新根", "target")
        native = _Native(helper, helper_sha256)
        profile, results, total = document["profile"], [], 0
        source_values = document["schema_version"] in (2, 3, 4)
        period = document.get("period", "1m")
        for security in document["securities"]:
            rows, first, last = [], None, None
            for chunk in security["chunks"]:
                data = _read(_chunk_path(manifest.parent, chunk["path"]), max_input_bytes)
                if _sha(data) != chunk["sha256"]:
                    _fail("分片与声明摘要不符")
                budget = min(max_bars - len(rows), max_total_bars - total - len(rows))
                added, chunk_first, last = (_rows(data, profile, last, budget, period=period)
                    if period == "1d" else _rows(data, profile, last, budget))
                if first is None:
                    first = chunk_first
                rows.extend(added)
            if not rows:
                _fail("证券没有分钟记录")
            total += len(rows)
            code, market = security["symbol"].split(".")
            exchange = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}[market]
            storage = "day" if period == "1d" else "min1"
            relative = f"his/{storage}/{exchange}/{code}.dsb"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path = root / (relative + ".metadata.json")
            write = not path.exists()
            if not write:
                if not resuming:
                    _fail("新导入目标出现已有证券文件", "target")
                try:
                    native.verify(path, rows, period=period)
                except ImportFailure:
                    # 已完成sidecar表示完整证券，内容不一致按损坏处理；
                    # 中断于原生写入的无sidecar文件保留原字节后重新生成。
                    if metadata_path.exists():
                        raise
                    from uuid import uuid4
                    retained = path.with_suffix(path.suffix + ".interrupted-" + uuid4().hex)
                    path.rename(retained)
                    write = True
            if write:
                pending = path.with_suffix(path.suffix + ".importing")
                if pending.exists():
                    if not resuming:
                        _fail("新根出现已有原生暂存文件", "target")
                    try:
                        native.verify(pending, rows, period=period)
                    except ImportFailure:
                        from uuid import uuid4
                        pending.rename(pending.with_name(pending.name + ".interrupted-" + uuid4().hex))
                    else:
                        write = False
                if write:
                    if period == "1d":
                        native.write_verify(pending, rows, period=period)
                    else:
                        native.write_verify(pending, rows)
                pending.replace(path)
            quality = PriceRangeQuality()
            if source_values:
                for row in rows:
                    encoded_day, hm = divmod(row.time, 10000)
                    day = row.date
                    label = f"{day//10000:04d}-{day//100%100:02d}-{day%100:02d}T{hm//100:02d}:{hm%100:02d}:00+08:00"
                    quality.observe(label, row.open, row.high, row.low, row.close)
            quality_result = quality.result()
            identity = _digest(path)
            metadata = {key: profile[key] for key in ("instance_id", "session_id", "generation", "dataset_version", "source_license", "adjustment", "factor_version", "timezone")}
            if source_values:
                metadata.update({key: profile[key] for key in ("value_semantics", "price_unit", "volume_unit", "amount_unit", "minute_boundary")})
                metadata.update(format=2, timestamp_semantics="source_label")
                if period == "1d":
                    # 原生day只存交易日期；00:00标签不代表该时刻已获知收盘数据。
                    metadata.update(format=3, period="1d", timestamp_semantics="source_date")
                if quality_result["inconsistent_rows"]:
                    metadata["price_range_quality"] = quality_result
            else:
                metadata.update(volume_to_shares=profile["volume_to_shares"], amount_to_yuan=profile["amount_to_yuan"],
                                format=1, minute_boundary="right")
            metadata.update(provider=0, qualification=1, content_id=identity)
            metadata_relative = relative + ".metadata.json"
            if metadata_path.exists():
                body = _read(metadata_path, max_input_bytes)
                if not resuming or body != _json_bytes(metadata):
                    _fail("已有证券来源元数据与原输入不符", "target")
                metadata_identity = _sha(body)
            else:
                pending_metadata = metadata_path.with_name(metadata_path.name + '.importing')
                if pending_metadata.exists():
                    if not resuming:
                        _fail("新根出现已有元数据暂存文件", "target")
                    if _read(pending_metadata, max_input_bytes) != _json_bytes(metadata):
                        from uuid import uuid4
                        pending_metadata.rename(pending_metadata.with_name(pending_metadata.name + '.interrupted-' + uuid4().hex))
                if not pending_metadata.exists():
                    _write_json(pending_metadata, metadata)
                metadata_identity = _digest(pending_metadata)
                pending_metadata.replace(metadata_path)
            item = dict(symbol=security["symbol"], exchange=exchange, code=code, path=relative,
                                sha256=identity, metadata_path=metadata_relative, metadata_sha256=metadata_identity,
                                count=len(rows), chunks=security["chunks"])
            item.update({"first_label" if source_values else "first_right": first.isoformat(),
                         "last_label" if source_values else "last_right": last.isoformat()})
            if source_values and quality_result["inconsistent_rows"]:
                item["price_range_quality"] = quality_result
            results.append(item)
        receipt = dict(schema_version=document["schema_version"], status="passed", qualification="DevelopmentVerified", coverage="unknown",
                       manifest_sha256=_sha(source), helper_sha256=helper_sha256, profile=profile, securities=results)
        if period == "1d":
            receipt["period"] = period
        temporary = root / ".qmt-import.json.tmp"
        _write_json(temporary, receipt)
        temporary.replace(root / "qmt-import.json")
        return receipt
    except ImportFailure:
        raise
    except (OSError, AttributeError):
        _fail("文件系统或原生依赖不可用", "dependency")
    except (ValueError, TypeError, OverflowError, RecursionError):
        _fail("输入或编码不合格")
    finally:
        if native is not None:
            native.close()


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"status": "failed", "category": "input", "message": "命令参数不合格"}, ensure_ascii=True), file=sys.stderr)
        raise SystemExit(2)


def main(argv=None):
    parser = _ArgumentParser(description="将显式 QMT 分钟导出转换为新 WT 开发历史根")
    for key in ("manifest", "output-root", "helper", "helper-sha256"):
        parser.add_argument("--" + key, required=True)
    for key, default in (("max-bars", 1000000), ("max-input-bytes", 268435456), ("max-total-bars", 10000000)):
        parser.add_argument("--" + key, type=int, default=default)
    args = parser.parse_args(argv)
    try:
        receipt = import_dataset(**vars(args))
    except ImportFailure as exc:
        print(json.dumps({"status": "failed", "category": exc.category, "message": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 1
    print(json.dumps(receipt, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
