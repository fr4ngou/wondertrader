"""单次独立SDK查询投影原生图表；分钟聚合和日线原值由来源服务拥有。"""

from datetime import datetime, timedelta, timezone
import math
import re

from .contracts.market import (
    MarketChartBundle,
    MarketChartCandle,
    SHANGHAI_TIME_ZONE,
)
from .settings import ConsoleSettings


# 对应 WT NativeHistoryStore 的协议时间边界；图表不能扩大源支持年份。
NATIVE_HISTORY_FIRST_MINUTE = 200401010000
_STATUS_REASONS = {
    "Pending": "WonderTrader 行情尚未准备完成，请稍后重试",
    "Backpressure": "WonderTrader 行情读取繁忙，请稍后重试",
    "StaleSession": "WonderTrader 行情来源会话已变化，请稍后重试",
    "Conflict": "WonderTrader 行情来源存在冲突，暂不可用",
    "IoError": "WonderTrader 原生历史读取失败，暂不可用",
    "Timeout": "WonderTrader 行情读取超时，请稍后重试",
    "NotSupported": "WonderTrader 当前来源尚不支持所请求的周期",
    "Unavailable": "WonderTrader 行情来源暂不可用",
    "InvalidInput": "WonderTrader 未接受本次行情查询",
}


def normalize_chart_symbol(symbol: str) -> str:
    """共享证券边界：接受带空白/小写后缀的输入，输出标准沪深代码。"""
    normalized = symbol.strip().upper()
    if re.fullmatch(r"[0-9]{6}\.(SH|SZ)", normalized) is None:
        raise ValueError("证券代码须为六位数字及 .SH/.SZ 后缀")
    return normalized


def utc_now() -> datetime:
    """本次投影的观察时刻；测试可注入时钟，客户端不能改写源数据时间。"""
    return datetime.now(timezone.utc)


def unavailable_native_chart(symbol: str, period: str, reason: str) -> MarketChartBundle:
    """纯失败投影；不读取时间、配置、SDK 或任何行情来源。"""
    source_date = period in ("1d", "1w", "1mo")
    return MarketChartBundle(
        schema_version="1.8" if period in ("1w", "1mo") else "1.6" if period == "1d" else "1.4",
        symbol=symbol,
        period=period,
        data_available=False,
        missing_reason=reason,
        source_period="1d" if source_date else "1m",
        source_bar_count=0 if period in ("1m", "1d", "1w", "1mo") else None,
        source_kind="wondertrader",
        derived=period in ("5m", "1w", "1mo"),
    )


def _calendar_projection(candles, period, limit):
    """按上海交易日期所在自然周/月聚合；标签取该组最后一个实际交易日。"""
    groups = []
    for candle in candles:
        stamp = candle.occurred_at.astimezone(SHANGHAI_TIME_ZONE)
        iso = stamp.isocalendar()
        key = (iso.year, iso.week) if period == "1w" else (stamp.year, stamp.month)
        if not groups or groups[-1][0] != key:
            groups.append([key, [candle]])
        else:
            groups[-1][1].append(candle)
    selected = groups[-limit:]
    result = []
    for unused, rows in selected:
        result.append(MarketChartCandle(
            occurred_at=rows[-1].occurred_at,
            open=rows[0].open,
            high=max(row.high for row in rows),
            low=min(row.low for row in rows),
            close=rows[-1].close,
            volume=sum(row.volume for row in rows),
        ))
    return result, sum(len(rows) for unused, rows in selected)


def _calendar_year_cutoff(stamp, years):
    try:
        return stamp.replace(year=stamp.year - years)
    except ValueError:
        return stamp.replace(year=stamp.year - years, day=28)


def _daily_projection(response, request, symbol, period, limit, years):
    """复用SDK0.14封闭来源协议；图表层另核OHLC及日期标签身份。"""
    from guanheng_market_client.source_history import validate_source_daily_data

    data = validate_source_daily_data(response["data"], request)
    metadata = data["metadata"]
    candles = []
    for row in data["bars"]:
        stamp = datetime.strptime(str(row["date"]), "%Y%m%d").replace(tzinfo=SHANGHAI_TIME_ZONE)
        candles.append(MarketChartCandle(occurred_at=stamp.astimezone(timezone.utc),
            open=row["open"], high=row["high"], low=row["low"], close=row["close"], volume=row["volume"]))
    if years is not None and candles:
        last = candles[-1].occurred_at.astimezone(SHANGHAI_TIME_ZONE)
        cutoff = _calendar_year_cutoff(last, years).date()
        candles = [row for row in candles
                   if row.occurred_at.astimezone(SHANGHAI_TIME_ZONE).date() >= cutoff]
    native_source = {key: metadata[key] for key in (
        "dataset_version", "content_id", "qualification", "adjustment", "timezone", "value_semantics",
        "timestamp_semantics", "price_unit", "volume_unit", "amount_unit")}
    native_source.update(provider=metadata["source"]["provider"], coverage=data["coverage"],
        source_minute_boundary=metadata["minute_boundary"], chart_minute_boundary="source_date")
    source_count = len(candles)
    if period in ("1w", "1mo"):
        candles, source_count = _calendar_projection(candles, period, limit)
    else:
        candles = candles[-limit:]
        source_count = len(candles)
    return MarketChartBundle(schema_version="1.8" if period in ("1w", "1mo") else "1.6",
        symbol=symbol, period=period, candles=candles,
        data_available=bool(candles), as_of=candles[-1].occurred_at if candles else None,
        missing_reason=None if candles else "当前查询没有已发布的来源日线，日期标签不表示实际闭合或可获知时刻",
        source_period="1d", source_bar_count=source_count, source_kind="wondertrader",
        derived=period in ("1w", "1mo"),
        native_source=native_source)


def _daily_source_limit(period, limit, daily_limit, years):
    """为自然周期请求有界日线窗口；不足时按实际可聚合数据返回。"""
    if daily_limit is not None:
        return daily_limit
    if years is not None:
        return 2000
    if period == "1w":
        return min(2000, limit * 6 + 5)
    if period == "1mo":
        return min(2000, limit * 24 + 23)
    return limit


def build_native_chart(
    *,
    symbol: str,
    period: str,
    limit: int,
    before: datetime | None,
    settings: ConsoleSettings,
    now: datetime | None = None,
    client_factory=None,
    timeout_seconds: float | None = None,
    daily_limit: int | None = None,
    years: int | None = None,
) -> MarketChartBundle:
    """单次 SDK 历史查询；before 含端点，输出以 UTC 传输。

    canonical分钟使用图表左端时间；source分钟保留来源标签。
    source日线取上海日期上界、原日线日期零点标签，仅转换时区，未授闭合/知晓资格。

    每请求新建客户端，SDK 在每次交换 finally 中关闭连接；本模块没有连接或行情缓存。
    client_factory/now 只用于隔离调用验证，不改变生产依赖入口。
    """
    symbol = normalize_chart_symbol(symbol)
    if period not in ("1m", "5m", "1d", "1w", "1mo"):
        raise ValueError("分钟图表证券或周期无效")
    source_values = settings.wondertrader_history_semantics == "source"
    daily = period in ("1d", "1w", "1mo")
    if daily and not source_values:
        return unavailable_native_chart(symbol, period, "来源日线需要显式配置source历史语义")
    if source_values and period == "5m":
        return unavailable_native_chart(symbol, period, "当前来源提供原始1分钟线；确认分钟边界后再启用5分钟聚合")
    if type(limit) is not int or not 1 <= limit <= 2000:
        raise ValueError("分钟图表条数须为 1 至 2000")
    if daily_limit is not None and (period not in ("1w", "1mo")
            or type(daily_limit) is not int or not 1 <= daily_limit <= 2000):
        raise ValueError("daily_limit 仅接受周月查询的 1 至 2000 根真实日线")
    if years is not None and (period not in ("1d", "1w", "1mo")
            or type(years) is not int or years < 1):
        raise ValueError("years 仅接受日周月查询的正整数公历年")
    if daily_limit is not None and years is not None:
        raise ValueError("daily_limit 与 years 不能同时使用")
    if before is not None and (before.tzinfo is None or before.utcoffset() is None):
        raise ValueError("分钟图表 before 必须包含时区")
    minutes = 1 if period == "1m" else 5
    observed = utc_now() if now is None else now
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("分钟图表观察时刻必须包含时区")
    closed_at = observed.astimezone(SHANGHAI_TIME_ZONE).replace(second=0, microsecond=0)
    upper = closed_at
    if before is not None:
        try:
            upper = min(upper, before.astimezone(SHANGHAI_TIME_ZONE) + timedelta(minutes=0 if source_values else minutes))
        except OverflowError:
            return unavailable_native_chart(symbol, period, "分钟图表查询时间超出支持范围")
    upper = upper.replace(second=0, microsecond=0)
    end = int(upper.strftime("%Y%m%d" if daily else "%Y%m%d%H%M"))
    first = NATIVE_HISTORY_FIRST_MINUTE // 10000 if daily else NATIVE_HISTORY_FIRST_MINUTE
    if end < first:
        return unavailable_native_chart(symbol, period, "查询时间早于 WonderTrader 原生历史支持起点")
    timeout = settings.wondertrader_market_timeout_seconds
    if timeout_seconds is not None:
        if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds):
            raise ValueError("分钟图表读取预算须为有限秒数")
        if timeout_seconds <= 0:
            return unavailable_native_chart(symbol, period, "WonderTrader 行情读取预算已耗尽")
        # 调用者预算只能收紧部署上限；基准图使用绝对总截止剩余时间。
        timeout = min(timeout, timeout_seconds)
    if not settings.wondertrader_market_url or not settings.wondertrader_market_token.get_secret_value():
        return unavailable_native_chart(symbol, period, "尚未配置 WonderTrader 行情服务连接")
    if client_factory is None:
        try:
            from guanheng_market_client import MarketClient
        except ImportError:
            return unavailable_native_chart(symbol, period, "尚未安装 WonderTrader 独立行情 SDK")
        client_factory = MarketClient
    try:
        options = {"timeout": timeout}
        if settings.wondertrader_market_connect_ip:
            # 地址映射由部署配置拥有；SDK保留原URL的Host/SNI与证书校验。
            options["connect_ip"] = settings.wondertrader_market_connect_ip
        client = client_factory(
            settings.wondertrader_market_url,
            settings.wondertrader_market_token.get_secret_value(),
            **options,
        )
    except Exception:
        return unavailable_native_chart(symbol, period, "WonderTrader 行情连接配置不可用")
    request = {
        "exchange": "SSE" if symbol.endswith(".SH") else "SZSE",
        "code": symbol[:6],
        "from": first,
        "to": end,
        "limit": _daily_source_limit(period, limit, daily_limit, years) if daily else limit,
    }
    if not source_values:
        request["period_minutes"] = minutes
    try:
        response = (client.source_daily_history_query(request) if daily else
            client.source_history_query(request) if source_values else client.history_query(request))
    except Exception:
        # 不回显上游异常、地址、凭据或原始 reason，下一请求独立重读。
        return unavailable_native_chart(symbol, period, "WonderTrader 行情读取失败或超时，请稍后重试")
    try:
        code = response["status"]["code"]
        if code != "Ok":
            return unavailable_native_chart(
                symbol, period, _STATUS_REASONS.get(code, "WonderTrader 行情来源暂不可用")
            )
        if daily:
            return _daily_projection(response, request, symbol, period, limit, years)
        data = response["data"]
        if source_values:
            from guanheng_market_client.source_history import validate_source_data
            data = validate_source_data(data, request)
        metadata = data["metadata"]
        if metadata["adjustment"] != "none" or metadata["factor_version"] != "":
            return unavailable_native_chart(symbol, period, "当前分钟图表仅支持未复权的原生行情")
        if data["selection"] != {"period_minutes": minutes, "limit": limit}:
            raise ValueError("selection mismatch")
        if data["coverage"] != "Unknown" or data["missing_minutes"] or len(data["bars"]) > limit:
            raise ValueError("unsupported coverage or quantity")
        candles = []
        previous = 0
        for row in data["bars"]:
            stamp = datetime.strptime(str(row["minute"]), "%Y%m%d%H%M").replace(
                tzinfo=SHANGHAI_TIME_ZONE
            )
            if not previous < row["minute"] <= end or row["minute"] < NATIVE_HISTORY_FIRST_MINUTE:
                raise ValueError("minute outside requested range")
            if minutes == 5:
                hhmm = stamp.hour * 100 + stamp.minute
                if stamp.minute % 5 or not (935 <= hhmm <= 1130 or 1305 <= hhmm <= 1500):
                    raise ValueError("five minute bucket is not closed at a session boundary")
            previous = row["minute"]
            if source_values and (row["high"] < max(row["open"], row["close"], row["low"])
                    or row["low"] > min(row["open"], row["close"], row["high"])):
                return unavailable_native_chart(symbol, period,
                    f"QMT来源分钟{stamp.strftime('%Y-%m-%d %H:%M')}的四价范围不一致，原值已保留；标准K线图暂不绘制本次区间")
            # canonical 数值已归一化；source 数值保留来源单位，本层均不再换算。
            candles.append(MarketChartCandle(
                occurred_at=(stamp if source_values else stamp - timedelta(minutes=minutes)).astimezone(timezone.utc),
                open=row["open"], high=row["high"], low=row["low"], close=row["close"],
                volume=row["volume"],
            ))
        native_source = {
            "provider": metadata["source"]["provider"],
            "dataset_version": metadata["dataset_version"],
            "content_id": metadata["content_id"],
            "qualification": metadata["qualification"],
            "coverage": data["coverage"],
            "adjustment": metadata["adjustment"],
            "source_minute_boundary": metadata["minute_boundary"],
            "chart_minute_boundary": "source_label" if source_values else "left",
            "timezone": metadata["timezone"],
        }
        if source_values:
            # 原始价格/量额可展示；单位未知时保留标签，时间也不作左右端转换。
            for key in ("value_semantics", "timestamp_semantics", "price_unit", "volume_unit", "amount_unit"):
                native_source[key] = metadata[key]
        observation = None
        provenance = []
        if source_values:
            raw = data.get("observation")
            if raw is not None:
                window = raw["source_window"]
                def source_time(value):
                    return datetime.strptime(str(value), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI_TIME_ZONE).astimezone(timezone.utc)
                observation = {key: raw[key] for key in ("state", "source_rows", "requested_limit", "selected_rows",
                    "preparation_state", "preparation_request_id")}
                observation.update(source_schema=raw["schema"], source_window=None if window is None else {
                    "from_at":source_time(window["from"]), "to_at":source_time(window["to"])})
            for part in data.get("provenance", []):
                offset, count = part["offset"], part["count"]
                provenance.append(dict(offset=offset, count=count, first_at=candles[offset].occurred_at,
                    last_at=candles[offset+count-1].occurred_at, metadata=part["metadata"]))
        return MarketChartBundle(
            schema_version="1.7" if observation is not None or provenance else "1.5" if source_values else "1.4",
            symbol=symbol,
            period=period,
            candles=candles,
            data_available=bool(candles),
            as_of=candles[-1].occurred_at if candles else None,
            missing_reason=None if candles else "当前查询没有已发布的分钟线",
            source_period="1m",
            source_bar_count=len(candles) if minutes == 1 else None,
            source_kind="wondertrader",
            derived=minutes == 5,
            native_source=native_source,
            source_observation=observation,
            source_provenance=provenance,
        )
    except Exception:
        return unavailable_native_chart(symbol, period, "WonderTrader 行情响应未通过图表契约校验")
