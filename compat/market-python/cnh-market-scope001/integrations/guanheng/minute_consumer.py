"""把已验证的右端分钟值接入原 MarketBar owner，保留预热与当前事件边界。"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import re

from ..guanheng_market_client import (
    MarketProtocolError, _metadata as _strict_metadata, _prices as _strict_prices,
    _text as _strict_text,
)


SHANGHAI = timezone(timedelta(hours=8))


def _instant(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("minute consumer requires an aware observation clock")
    return value.astimezone(SHANGHAI)


def _text(value, maximum=256):
    try:
        _strict_text(value, limit=maximum)
        return bool(value.strip())
    except MarketProtocolError:
        return False


def _metadata(value):
    if not isinstance(value, Mapping):
        raise ValueError("minute provenance is missing")
    source = value.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("minute provenance is invalid")
    # 与线协议共用严格来源、资格及数值规则，只解开只读视图，不改变原证据。
    _strict_metadata(dict(value, source=dict(source)))
    if value["adjustment"] != "none" or value["factor_version"] != "":
        raise ValueError("minute provenance adjustment is unsupported")


class RetainedMinuteConsumer:
    """同步薄适配；宿主注入原 DTO、事实存储与当前分钟发布函数。

    整批校验和 DTO 构造先于效果；实际事实/发布失败时不 ACK，重投幂等由原 owner
    承担。消费时钟重新判定当前资格，旧批次不会因迟到重投触发当前策略。
    """

    def __init__(self, store, market_bar_type, publish_current, feature_version):
        if (not callable(getattr(store, "save_bar", None)) or not callable(market_bar_type)
                or not callable(publish_current) or not _text(feature_version)):
            raise ValueError("minute consumer dependencies are invalid")
        self.store, self.market_bar_type = store, market_bar_type
        self.publish_current, self.feature_version = publish_current, feature_version

    def _prepare(self, result, as_of, *, historical):
        now = _instant(as_of)
        if getattr(result, "status", None) != "Ok":
            raise ValueError("minute input is not ready")
        provenance = getattr(result, "provenance", None)
        bars = getattr(result, "bars", None)
        if not isinstance(provenance, Mapping) or type(bars) is not tuple:
            raise ValueError("minute input shape is invalid")
        for name, metadata in provenance.items():
            if not _text(name, 128):
                raise ValueError("minute provenance identity is invalid")
            if type(metadata) is not tuple or not metadata:
                raise ValueError("minute provenance segments are invalid")
            for segment in metadata:
                _metadata(segment)
        prepared, previous, symbol = [], 0, None
        for bar in bars:
            minute = getattr(bar, "minute", None)
            current_symbol = getattr(bar, "symbol", None)
            source_name, delivery = getattr(bar, "source_name", None), getattr(bar, "delivery", None)
            if (type(minute) is not int or minute <= previous or not 199201010000 <= minute <= 209912312359
                    or type(current_symbol) is not str or re.fullmatch(r"[0-9]{6}\.(SH|SZ)", current_symbol) is None
                    or (symbol is not None and current_symbol != symbol)
                    or not _text(source_name, 128) or source_name not in provenance
                    or delivery not in (("historical",) if historical else ("recovered", "current"))):
                raise ValueError("minute bar identity is invalid")
            try:
                right = datetime.strptime(str(minute), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)
            except ValueError:
                raise ValueError("minute bar time is invalid") from None
            if right > now:
                raise ValueError("minute bar is not closed")
            values = {name: getattr(bar, name, None) for name in ("open", "high", "low", "close", "volume", "amount")}
            _strict_prices(values, "close", "volume", "amount")
            # 右端只在此减一分钟；输入量额已经是股/元，来源系数只留作证据。
            original = self.market_bar_type(symbol=current_symbol, period="1m",
                occurred_at=right - timedelta(minutes=1), feature_version=self.feature_version, **values)
            current = not historical and delivery == "current" and right == now.replace(second=0, microsecond=0)
            prepared.append((original, current))
            previous, symbol = minute, current_symbol
        return prepared, provenance

    def warmup(self, history_result, *, as_of):
        """历史只调用原 save_bar，保留原 feature/outbox 的当前事件入口。"""
        prepared, _ = self._prepare(history_result, as_of, historical=True)
        for original, _ in prepared:
            self.store.save_bar(original)
        return len(prepared)

    def consume(self, subscription, batch, *, as_of):
        """整批效果成功后 ACK；任何校验、保存、发布或确认异常直接交宿主恢复。"""
        if (not callable(getattr(subscription, "ack", None))
                or getattr(batch, "delivery", None) != "closed-source-poll"):
            raise ValueError("minute subscription contract is invalid")
        prepared, provenance = self._prepare(batch, as_of, historical=False)
        batch_id = getattr(batch, "batch_id", None)
        after, through = getattr(batch, "after", None), getattr(batch, "through", None)
        calendar_version = getattr(batch, "calendar_version", "")
        has_scan = after is not None or through is not None or calendar_version != ""
        if has_scan:
            if (type(after) is not int or type(through) is not int
                    or not 199201010000 <= after < through <= 209912312359
                    or not _text(calendar_version, 128)):
                raise ValueError("minute scan identity is invalid")
            try:
                datetime.strptime(str(after), "%Y%m%d%H%M")
                end = datetime.strptime(str(through), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)
            except ValueError:
                raise ValueError("minute scan time is invalid") from None
            if end > _instant(as_of) or any(not after < bar.minute <= through for bar in batch.bars):
                raise ValueError("minute scan range is invalid")
        if (prepared or has_scan) and not _text(batch_id, 256):
            raise ValueError("minute batch identity is invalid")
        for original, current in prepared:
            if current:
                self.publish_current(original, provenance)
            else:
                self.store.save_bar(original)
        if prepared or has_scan:
            if subscription.ack(batch_id) is not True:
                raise ValueError("minute acknowledgement was not confirmed")
        return len(prepared)
