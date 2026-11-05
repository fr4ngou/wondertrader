"""受管来源历史商店：原生读取、启动预载与单线程有界缓存。"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import OrderedDict
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
import re
import threading

from ..guanheng_market_client import (
    API_VERSION, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, MarketProtocolError,
    MarketUnavailable, encode_json, strict_json, validate_request, validate_response,
)
from ..guanheng_market_client.source_history import validate_source_metadata
from ..guanheng_market_client.daily_contract import SOURCE_DAILY_MARKETS, source_price_basis
from .models import SourceSession, IntegrationUnavailable
from .native_history import NativeHistory


def _require(value):
    if not value:
        raise ValueError("来源历史服务配置或导入身份不合格")


def _hash(value):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)
    return value


def _metadata(value, period="1m"):
    result = {key: getattr(value, key) for key in (
        "qualification", "dataset_version", "source_license", "adjustment",
        "factor_version", "minute_boundary", "timezone", "content_id",
        "value_semantics", "timestamp_semantics", "price_unit", "volume_unit", "amount_unit")}
    result["source"] = asdict(value.source)
    if period == "1d":
        result["period"] = period
    return validate_source_metadata(result, period=period)


def _minute(value):
    # 原SourceReader已校验上海标签；这里只编码原年月日时分，不移动区间。
    return value.year * 100000000 + value.month * 1000000 + value.day * 10000 + value.hour * 100 + value.minute


@dataclass(frozen=True)
class _SourceStore:
    """路由只保存原成功根与身份；行情事实仍由原Reader负责。"""

    root: Path  # 数据侧已完成导入的原生历史根。
    receipt_sha256: str  # 本根成功收据的完整字节身份。
    source: SourceSession  # 原件归属的数据采集会话；每批查询保留原身份。
    period: str  # 本根基础周期1m或1d。
    adjustment: str  # 本根来源价格口径；none或显式front_ratio参考。


class NativeSourceMarket:
    """创建线程独占reader、缓存与close；预加载完成后构造才返回。"""

    def __init__(self, config, *, max_response_bytes=8 * 1024 * 1024):
        self._owner = threading.get_ident()
        self._reader = None
        self._closed = False
        self._cache = OrderedDict()
        self._cache_bars = 0
        _require(type(config) is dict)
        mode = config.get("mode")
        _require(mode in ("source-store", "source-stores", "source-catalog"))
        catalog = mode == "source-catalog"
        fields = {"mode", "native_reader", "max_bars", "max_cache_bars", "preload_symbols"}
        fields |= {"store_root", "import_receipt_sha256"} if mode == "source-store" else {"stores"}
        _require(set(config) == fields)
        for key in ("max_bars", "max_cache_bars"):
            _require(type(config[key]) is int and 1 <= config[key] <= 1000000)
        _require(type(max_response_bytes) is int and 1024 <= max_response_bytes <= MAX_RESPONSE_BYTES)
        self._maximum = max_response_bytes
        self._capacity = config["max_cache_bars"]
        self._max_bars = config["max_bars"]
        native = config["native_reader"]
        _require(type(native) is dict and set(native) == {"library", "sha256"})
        _require(type(native["library"]) is str and Path(native["library"]).is_absolute())
        library, library_sha = native["library"], _hash(native["sha256"])
        preload = config["preload_symbols"]
        _require(type(preload) is list and (1 if mode == "source-store" else 0) <= len(preload) <= 10000)
        preload_keys = []
        for item in preload:
            if catalog:
                _require(type(item) is dict and {"symbol", "period"} <= set(item) <= {"symbol", "period", "adjustment"})
                security, period = item["symbol"], item["period"]
                _require(period in ("1m", "1d"))
                adjustment = item.get('adjustment', 'none')
                _require(adjustment in (('none', 'front_ratio') if period == '1d' else ('none',)))
            else:
                security, period = item, "1m"
                adjustment = 'none'
            _require(type(security) is str and re.fullmatch(r"(?:SSE|SZSE|BSE)\.[0-9]{6}" if period == '1d' else r"(?:SSE|SZSE)\.[0-9]{6}", security))
            preload_keys.append((security, period, adjustment))
        _require(len(set(preload_keys)) == len(preload_keys))
        specs = ([{key: config[key] for key in ("store_root", "import_receipt_sha256")}]
                 if mode == "source-store" else config["stores"])
        _require(type(specs) is list and 1 <= len(specs) <= 1024)
        self._registered = {}
        stores, roots = [], set()
        # 多根启动只读取原收据；总字节数有界，不随证券数同时解码DSB。
        remaining = 268435456 if mode == "source-store" else 16 * 1024 * 1024
        for spec in specs:
            _require(type(spec) is dict and set(spec) == {"store_root", "import_receipt_sha256"})
            _require(type(spec["store_root"]) is str and Path(spec["store_root"]).is_absolute())
            root = Path(spec["store_root"]).resolve(strict=True)
            _require(root.is_dir() and root not in roots)
            roots.add(root)
            receipt_sha = _hash(spec["import_receipt_sha256"])
            with (root / "qmt-import.json").open("rb") as stream:
                raw = stream.read(remaining + 1)
            _require(len(raw) <= remaining and hashlib.sha256(raw).hexdigest() == receipt_sha)
            remaining -= len(raw)
            receipt = strict_json(raw)
            _require(type(receipt) is dict and type(receipt.get("schema_version")) is int
                     and receipt["schema_version"] in ((2, 3, 4) if catalog else (2,))
                     and receipt.get("status") == "passed")
            period = "1d" if receipt["schema_version"] in (3, 4) else "1m"
            _require(period != "1d" or receipt.get("period") == "1d")
            profile = receipt["profile"]
            adjustment = profile['adjustment']
            _require(source_price_basis(adjustment, profile['factor_version'], allow_reference=receipt['schema_version'] == 4))
            source = SourceSession(**{k: profile[k] for k in ("provider", "instance_id", "session_id", "generation")})
            store = _SourceStore(root, receipt_sha, source, period, adjustment)
            stores.append(store)
            entries = receipt["securities"]
            _require(type(entries) is list and 1 <= len(entries) <= 10000)
            for entry in entries:
                exchange, code, count = entry["exchange"], entry["code"], entry["count"]
                _require(exchange in (SOURCE_DAILY_MARKETS if receipt['schema_version'] == 4 else ('SSE', 'SZSE')) and type(code) is str and re.fullmatch(r"[0-9]{6}", code))
                security = exchange + "." + code
                key = (security, period, adjustment)
                _require(key not in self._registered and type(count) is int and 1 <= count <= 1000000)
                _require(len(self._registered) < (20000 if catalog else 10000))
                self._registered[key] = (store, count)
        first = stores[0].source
        _require(all(s.source.provider == first.provider for s in stores))
        same_instance = all(s.source.instance_id == first.instance_id for s in stores)
        _require(catalog or same_instance)
        self._source = first
        self._collection = len(stores) > 1
        if self._collection:
            # 能力页标识收据集合，逐证券返回仍使用其原采集session。
            identity = hashlib.sha256(encode_json(sorted(s.receipt_sha256 for s in stores))).hexdigest()
            instance = first.instance_id if same_instance else "source-catalog:" + identity
            self._source = SourceSession(first.provider, instance, "source-stores:" + identity, 1)
        _require(all(key in self._registered for key in preload_keys))
        _require(sum(self._registered[key][1] for key in preload_keys) <= self._capacity)
        _require(all(self._registered[key][1] <= self._max_bars for key in preload_keys))
        try:
            self._reader = NativeHistory(Path(library), library_sha,
                max_bars=self._max_bars, max_file_bytes=268435456)
            for security, period, adjustment in preload_keys:
                self._load(security, period, adjustment)
        except BaseException:
            self.close()
            raise

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise MarketUnavailable("来源历史reader属于创建线程")

    def _load(self, security, period="1m", adjustment="none"):
        # 同标的分钟/日线分别缓存；总记录预算仍归同一LRU所有者。
        key = (security, period, adjustment)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        store, count = self._registered[key]
        if count > min(self._capacity, self._max_bars):
            raise MarketUnavailable("证券记录数超过来源历史缓存预算")
        # 原生解码前逐出旧证券，避免同时持有超出总容量的证券数据。
        while self._cache_bars + count > self._capacity:
            _, old = self._cache.popitem(last=False)
            self._cache_bars -= len(old[0].bars)
            del old
        exchange, code = security.split(".")
        history = self._reader.read_source_store(store.root, exchange, code,
            expected_import_sha256=store.receipt_sha256)
        _require(len(history.bars) == count and history.metadata.source == store.source
                 and history.metadata.period == period and history.metadata.adjustment == adjustment)
        _metadata(history.metadata, period)
        minutes = tuple((_minute(bar.occurred_at) // 10000 if period == "1d" else _minute(bar.occurred_at))
                        for bar in history.bars)
        _require(all(a < b for a, b in zip(minutes, minutes[1:])))
        cached = (history, minutes)
        self._cache[key] = cached
        self._cache_bars += count
        return cached

    def has_source_history(self, security, period, *, adjustment='none'):
        """只读注册事实，不解码文件；已注册与日期覆盖、数据完整性分别核实。"""
        self._check_owner()
        return not self._closed and (security,period,adjustment) in self._registered

    def call(self, request):
        self._check_owner()
        if self._closed:
            raise MarketUnavailable("来源历史reader已关闭")
        encoded = encode_json(request)
        if len(encoded) > MAX_REQUEST_BYTES:
            raise MarketProtocolError("来源历史请求超过字节预算")
        request = validate_request(strict_json(encoded))
        data, code, reason = {}, "Ok", ""
        action = request["action"]
        if action == "capabilities":
            unavailable = dict(supported=False, qualification="Unavailable", reason="来源历史商店未提供此能力")
            data = dict(source=asdict(self._source), snapshot=dict(unavailable), trading=dict(unavailable),
                history=dict(supported=True, qualification="DevelopmentVerified", reason=("已绑定离线收据集合，逐证券原始来源见metadata" if self._collection
                    else "已绑定原生来源历史，保留源值单位与时间标签")))
        elif action in ("history.source-query", "history.source-daily-query"):
            query = request["request"]
            if 'snapshot_id' in query:
                return dict(api_version=API_VERSION,status=dict(code='NotSupported',reason='market snapshot is not configured'),data={})
            security = query["exchange"] + "." + query["code"]
            period = "1d" if action == "history.source-daily-query" else "1m"
            adjustment = query.get('adjustment', 'none') if period == '1d' else 'none'
            if (security, period, adjustment) not in self._registered:
                code, reason = "Unavailable", "导入收据未登记此证券"
            else:
                try:
                    history, minutes = self._load(security, period, adjustment)
                    start = bisect_left(minutes, query["from"])
                    end = bisect_right(minutes, query["to"])
                    start = max(start, end - query["limit"])
                    bars = []
                    for index in range(start, end):
                        bar = history.bars[index]
                        item = {key: getattr(bar, key) for key in ("open", "high", "low", "close", "volume", "amount")}
                        item.update(symbol=security)
                        item["date" if period == "1d" else "minute"] = minutes[index]
                        bars.append(item)
                    data = dict(metadata=_metadata(history.metadata, period), bars=bars, coverage="Unknown")
                    if period == "1d":
                        data.update(missing_dates=[], selection=dict(period="1d", limit=query["limit"]))
                        if query.get('include_archive',False):
                            data['archive']=dict(first_date=minutes[0],  # 本价格口径实际首日，不授上市前缺失判断。
                                last_date=minutes[-1],  # 原成功根实际末日，与请求截止分别保留。
                                count=len(minutes))  # 整个原归档实际条数，独立于本次limit。
                    else:
                        data.update(missing_minutes=[], selection=dict(period_minutes=1, limit=query["limit"]))
                except (OSError, ValueError, IntegrationUnavailable, MarketUnavailable) as error:
                    # 已登记数据的读取失败属于操作故障，不能作为无行情参与统计。
                    logging.getLogger(__name__).warning(
                        'source_history_read_failed security=%s period=%s adjustment=%s error_type=%s errno=%s winerror=%s',
                        security, period, adjustment, type(error).__name__,
                        getattr(error,'errno',None),getattr(error,'winerror',None))
                    code, reason = "IoError", "来源历史读取失败，请检查数据存储和来源绑定"
        else:
            code, reason = "NotSupported", "来源历史商店仅提供显式来源历史查询"
        result = dict(api_version=API_VERSION, status=dict(code=code, reason=reason), data=data)
        if len(encode_json(result)) > self._maximum:
            raise MarketProtocolError("来源历史响应超过字节预算")
        return validate_response(result, request)

    def close(self):
        self._check_owner()
        if self._reader is not None:
            self._reader.close()
            self._reader = None
        self._cache.clear()
        self._cache_bars = 0
        self._closed = True


def prepare_source_config(catalog, output_config, *, native_reader, native_reader_sha256,
                          expected_catalog_sha256=None, max_bars=1000000,
                          max_cache_bars=1000000, preload_symbols=(), exclude_failed_symbols=()):
    """外部离线生成新候选配置；精确核目录成员并关闭校验Reader后才写文件。

    目录只描述已完成的输入集合；实际DSB校验继续归原Reader。此入口不启动服务、
    不改变活动配置，空预载不解码行情；调用者可沿原preload约定预热指定证券。
    """
    catalog = Path(catalog).resolve(strict=True)
    output = Path(output_config).absolute()
    _require(not output.exists() and not output.is_symlink())
    with catalog.open("rb") as stream:
        raw = stream.read(32 * 1024 * 1024 + 1)
    _require(len(raw) <= 32 * 1024 * 1024)
    catalog_sha = hashlib.sha256(raw).hexdigest()
    if expected_catalog_sha256 is not None:
        _require(catalog_sha == _hash(expected_catalog_sha256))
    value = strict_json(raw)
    fields = {"schema", "status", "entries", "coverage", "value_semantics"}
    _require(type(value) is dict and (set(value) == fields or set(value) == fields | {"tail_refresh"}))
    tail_refresh = value.get("tail_refresh", "unspecified")
    _require("tail_refresh" not in value or tail_refresh == "pending_current_qmt_download")
    _require(type(exclude_failed_symbols) in (list, tuple) and len(exclude_failed_symbols) <= 10000)
    _require(all(type(s) is str and re.fullmatch(r"[0-9]{6}\.(?:SH|SZ)", s) for s in exclude_failed_symbols))
    excluded = set(exclude_failed_symbols)
    _require(len(excluded) == len(exclude_failed_symbols))
    required_status = "completed_with_failures" if excluded else "completed"
    _require(value["schema"] == "qmt.full-history-catalog.v1" and value["status"] == required_status
             and value["coverage"] == "unknown" and value["value_semantics"] == "source")
    entries = value["entries"]
    _require(type(entries) is list and 1 <= len(entries) <= 10000)
    expected, stores, seen, failed, empty = {}, {}, set(), set(), 0
    for entry in entries:
        _require(type(entry) is dict)
        symbol = entry.get("symbol")
        _require(type(symbol) is str and re.fullmatch(r"[0-9]{6}\.(?:SH|SZ)", symbol) is not None)
        _require(symbol not in seen)
        seen.add(symbol)
        if entry.get("status") == "failed":
            # 显式排除仅针对已终止的失败项；目录和失败记录仍保留原身份。
            _require(symbol in excluded)
            failed.add(symbol)
            continue
        _require(symbol not in excluded)
        if entry.get("status") == "empty":
            empty += 1
            continue
        _require(entry.get("status") == "imported")
        count = entry.get("rows")
        _require(type(count) is int and 1 <= count <= 1000000)
        root = entry.get("store")
        _require(type(root) is str and Path(root).is_absolute())
        root = Path(root).resolve(strict=True)
        receipt_sha = _hash(entry.get("import_receipt_sha256"))
        _require(root not in stores or stores[root] == receipt_sha)
        stores[root] = receipt_sha
        code, suffix = symbol.split(".")
        security = ("SSE." if suffix == "SH" else "SZSE.") + code
        expected[security] = (root, receipt_sha, count)
    _require(expected and failed == excluded)
    config = dict(mode="source-stores",
        stores=[dict(store_root=str(root), import_receipt_sha256=sha)
                for root, sha in sorted(stores.items(), key=lambda item: str(item[0]))],
        native_reader=dict(library=str(Path(native_reader).resolve(strict=True)), sha256=_hash(native_reader_sha256)),
        max_bars=max_bars, max_cache_bars=max_cache_bars, preload_symbols=list(preload_symbols))
    encoded = encode_json(config)
    _require(len(encoded) <= 1024 * 1024)
    market = NativeSourceMarket(config)
    try:
        # 复用运行期唯一注册实现，目录不能少列证券或暗中带入其他批次。
        actual = {security: (store.root, store.receipt_sha256, count)
                  for (security, period, adjustment), (store, count) in market._registered.items() if period == "1m" and adjustment == 'none'}
        _require(actual == expected)
    finally:
        market.close()
    # 同目录临时文件先完整写入并关闭，再无覆盖发布到候选路径。
    temporary, published, temporary_retained = None, False, False
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, prefix=".source-config-", delete=False) as stream:
            temporary = Path(stream.name)
            if stream.write(encoded) != len(encoded):
                raise OSError("候选配置未完整写入")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
        published = True
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                # 发布前保留原首因；发布成功后只残留已关闭的临时副本，明确回报。
                temporary_retained = True
    return dict(schema="qmt.source-stores-preparation.v1", status="passed",
        catalog_sha256=catalog_sha, config_sha256=hashlib.sha256(encoded).hexdigest(),
        catalog_status=value["status"], excluded_failed_symbols=sorted(excluded), tail_refresh=tail_refresh,
        stores=len(stores), imported_securities=len(expected), empty_securities=empty,
        source_rows=sum(item[2] for item in expected.values()), output_config=str(output),
        temporary_file_retained=temporary_retained)


class _ConfigParser(argparse.ArgumentParser):
    def error(self, message):
        # 参数中的非本地编码文字也不进入机器错误流。
        raise ValueError("读取配置参数不合格")


def main(argv=None):
    """只准备离线候选；凭据由服务启动环境注入，不进入生成配置。"""
    parser = _ConfigParser(description="从已完成导入目录准备统一来源历史配置")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--catalog-sha256")
    parser.add_argument("--output-config", required=True)
    parser.add_argument("--native-reader", required=True)
    parser.add_argument("--native-reader-sha256", required=True)
    parser.add_argument("--max-bars", type=int, default=1000000)
    parser.add_argument("--max-cache-bars", type=int, default=1000000)
    parser.add_argument("--preload-symbol", action="append", default=[])
    parser.add_argument("--exclude-failed-symbol", action="append", default=[],
                        help="显式列出终态目录中全部失败证券，仅准备其余已导入子集")
    try:
        args = parser.parse_args(argv)
        result = prepare_source_config(args.catalog, args.output_config,
            native_reader=args.native_reader, native_reader_sha256=args.native_reader_sha256,
            expected_catalog_sha256=args.catalog_sha256, max_bars=args.max_bars,
            max_cache_bars=args.max_cache_bars, preload_symbols=args.preload_symbol,
            exclude_failed_symbols=args.exclude_failed_symbol)
    except Exception:
        print(json.dumps(dict(status="failed", reason="离线读取配置准备未完成，原数据与配置保持"), ensure_ascii=True),
              file=sys.stderr, flush=True)
        return 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False), flush=True)
    return 0


def create_native_source_market(config, *, max_response_bytes=8 * 1024 * 1024):
    if type(config) is dict and config.get('mode') == 'source-current-day':
        from .current_day import CurrentDayMarket
        return CurrentDayMarket(config,max_response_bytes=max_response_bytes)
    """显式来源配置选择实现；已有导入模式保持原Reader和缓存行为。"""
    if type(config) is dict and config.get('mode') == 'source-recovered':
        from .recovered_history import RecoveredSourceMarket
        return RecoveredSourceMarket(config, max_response_bytes=max_response_bytes)
    if type(config) is dict and config.get('mode') == 'source-preparing':
        from .source_history_preparation import SourcePreparingMarket
        return SourcePreparingMarket(config)
    if type(config) is dict and config.get('mode') == 'source-market-current':
        from .market_current import CurrentSourceMarket
        return CurrentSourceMarket(config,max_response_bytes=max_response_bytes)
    if type(config) is dict and config.get('mode') == 'source-market-snapshot':
        from .market_snapshot import SnapshotSourceMarket
        return SnapshotSourceMarket(config,max_response_bytes=max_response_bytes)
    if type(config) is dict and config.get('mode') == 'source-daily-overlay':
        from .daily_overlay import DailyOverlayMarket
        return DailyOverlayMarket(config, max_response_bytes=max_response_bytes)
    if type(config) is dict and config.get('mode') == 'source-shm-quotes':
        from .shm_quotes import ShmQuotesMarket
        return ShmQuotesMarket(config, max_response_bytes=max_response_bytes)
    if type(config) is dict and config.get('mode') == 'source-collected':
        from .collected_history import CollectedSourceMarket
        return CollectedSourceMarket(config, max_response_bytes=max_response_bytes)
    return NativeSourceMarket(config, max_response_bytes=max_response_bytes)


if __name__ == "__main__":
    raise SystemExit(main())
