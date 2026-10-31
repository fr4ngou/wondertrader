"""策略统一行情：显式组合档案与活动来源，保留来源谱系及闭合分钟确认边界。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, time as day_time, timedelta, timezone
import hashlib
import json
import math
import re
import threading
import time
from types import MappingProxyType

from . import API_VERSION, MarketHTTPError, MarketProtocolError, MarketUnavailable, encode_json, strict_json, validate_response
from .history_calendar import CalendarConflict, CalendarTimeout
from .history_runner import CalendarSlice


__all__ = ["MarketSource", "StrategyMarket", "MinuteBar", "HistoryResult", "QuoteResult",
           "MinuteBatch", "MinuteSubscription"]
SHANGHAI = timezone(timedelta(hours=8))
_QUALIFICATIONS = ("Unavailable", "DevelopmentVerified", "NativeVerified", "ProductionQualified")


def _text(value, maximum=256):
    if (type(value) is not str or not value.strip() or len(value) > maximum
            or any(ord(c) < 32 or 0x7F <= ord(c) <= 0x9F or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise ValueError("行情文本配置不合格")


def _bound(value, maximum=None, *, zero=False):
    try:
        valid = (type(value) in (int, float) and math.isfinite(value)
                 and (value >= 0 if zero else value > 0) and (maximum is None or value <= maximum))
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("行情时间预算不合格")
    return value


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) in (list, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _instant(value, *, minute=False):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("行情时间必须带时区")
    result = value.astimezone(SHANGHAI)
    if (not 1992 <= result.year <= 2099 or (minute and (result.second or result.microsecond))):
        raise ValueError("行情时间或整分钟边界不合格")
    return result


def _minute(value):
    return int(value.strftime("%Y%m%d%H%M"))


def _security(value):
    if type(value) is not str or re.fullmatch(r"[0-9]{6}\.(SH|SZ)", value) is None:
        raise ValueError("行情证券身份不合格")
    code, market = value.split(".")
    return ("SSE" if market == "SH" else "SZSE"), code


def _empty():
    return MappingProxyType({})


def _provenance(value):
    return _freeze({name: tuple(versions.values()) for name, versions in value.items()})


@dataclass(frozen=True, slots=True)
class MarketSource:
    """显式固定来源及数据版本；client.timeout 为单次调用准入上界。"""

    name: str
    client: object
    dataset_version: str
    provider: str = "Qmt"
    allow_prepare: bool = False

    def __post_init__(self):
        _text(self.name, 128)
        _text(self.dataset_version)
        if self.provider not in ("Qmt", "Tdx") or type(self.allow_prepare) is not bool:
            raise ValueError("行情来源配置不合格")
        _bound(getattr(self.client, "timeout", None))
        if not callable(getattr(self.client, "history_query", None)) or (self.allow_prepare and
                any(not callable(getattr(self.client, name, None)) for name in ("history_read", "quotes_query"))):
            raise ValueError("行情来源接口缺失")


@dataclass(frozen=True, slots=True)
class MinuteBar:
    """规范化股/元、上海右端分钟；delivery 区分历史、恢复及当前闭合分钟。"""

    symbol: str
    minute: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    source_name: str
    delivery: str = "historical"


@dataclass(frozen=True, slots=True)
class HistoryResult:
    status: str
    reason: str
    bars: tuple
    missing_minutes: tuple
    provenance: object
    calendar_version: str


@dataclass(frozen=True, slots=True)
class QuoteResult:
    status: str
    reason: str
    data: object


@dataclass(frozen=True, slots=True)
class MinuteBatch:
    status: str
    batch_id: str
    bars: tuple
    delivery: str
    reason: str
    provenance: object
    after: int | None = None
    through: int | None = None
    calendar_version: str = ""


class _Stop(Exception):
    def __init__(self, status, reason, missing=()):
        self.status, self.reason, self.missing = status, reason, tuple(missing)


class StrategyMarket:
    """创建线程独占的同步访问器；无后台作业，所有外部调用共享本次截止预算。

    sources 保持显式顺序；相同分钟只合并完全相同的量价，不覆盖矛盾事实。
    provenance 为 source_name 到只读元数据元组，跨窗不同内容身份分别保留。
    """

    def __init__(self, sources, calendar, calendar_version, *, clock=None,
                 minimum_qualification="NativeVerified", timeout=30, max_bars=10000, max_windows=128):
        if type(sources) not in (list, tuple) or not 1 <= len(sources) <= 16 or any(not isinstance(s, MarketSource) for s in sources):
            raise ValueError("行情来源清单不合格")
        if (len({s.name for s in sources}) != len(sources) or len({s.provider for s in sources}) != 1
                or sum(s.allow_prepare for s in sources) > 1):
            raise ValueError("行情来源身份、供应商或活动源冲突")
        _text(calendar_version, 128)
        _bound(timeout, 300)
        _bound(getattr(calendar, "timeout", None))
        if (not callable(getattr(calendar, "minutes", None)) or (clock is not None and not callable(clock))
                or minimum_qualification not in _QUALIFICATIONS[1:]
                or type(max_bars) is not int or not 1 <= max_bars <= 1000000
                or type(max_windows) is not int or not 1 <= max_windows <= 10000):
            raise ValueError("行情接口配置或容量不合格")
        self.sources, self.calendar, self.calendar_version = tuple(sources), calendar, calendar_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.minimum_qualification = minimum_qualification
        self.timeout, self.max_bars, self.max_windows = timeout, max_bars, max_windows
        self._owner, self._closed = threading.get_ident(), False

    def _guard(self):
        if threading.get_ident() != self._owner:
            raise _Stop("Conflict", "行情接口由创建线程独占")
        if self._closed:
            raise _Stop("Unavailable", "行情接口已关闭")

    def _as_of(self, value):
        now = _instant(self.clock())
        cutoff = now if value is None else _instant(value)
        if cutoff > now:
            raise ValueError("行情查询截止时间超前")
        return cutoff

    @staticmethod
    def _check(deadline, bound=0):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or remaining < bound:
            raise _Stop("Timeout", "行情请求截止预算不足")

    def _invoke(self, owner, method, deadline, *args):
        try:
            bound = _bound(getattr(owner, "timeout", None))
        except ValueError:
            raise _Stop("Conflict", "行情依赖缺少有限调用预算") from None
        self._check(deadline, bound)
        try:
            result = getattr(owner, method)(*args)
        except (TimeoutError, CalendarTimeout):
            raise _Stop("Timeout", "行情依赖调用超时") from None
        except CalendarConflict:
            raise _Stop("Conflict", "交易日历事实校验失败") from None
        except MarketHTTPError as exc:
            # 原客户端已验证的非200状态仍须按本次请求再校验。
            result = exc.response
        except MarketProtocolError:
            raise _Stop("Conflict", "行情响应契约校验失败") from None
        except (MarketUnavailable, OSError):
            raise _Stop("Unavailable", "行情依赖暂不可用") from None
        except Exception:
            raise _Stop("Unavailable", "行情依赖调用失败") from None
        self._check(deadline)
        return result

    def _wire(self, source, action, request, deadline):
        payload = self._invoke(source.client, action.replace(".", "_"), deadline,
                               strict_json(encode_json(request)))
        wire = {"api_version": API_VERSION, "action": action,
                "symbols" if action == "quotes.query" else "request": request}
        try:
            # 统一校验同时脱离注入对象拥有的可变响应。
            payload = validate_response(strict_json(encode_json(payload)), wire)
        except Exception:
            raise _Stop("Conflict", "行情响应契约校验失败") from None
        self._check(deadline)
        status = payload["status"]["code"]
        if status != "Ok":
            raise _Stop(status, "行情来源返回未就绪状态")
        return payload["data"]

    def _qualified(self, qualification):
        if _QUALIFICATIONS.index(qualification) < _QUALIFICATIONS.index(self.minimum_qualification):
            raise _Stop("Unavailable", "行情来源资格低于配置下限")

    def _history_data(self, source, action, request, deadline):
        try:
            data = self._wire(source, action, request, deadline)
        except _Stop as exc:
            if exc.status == "Unavailable":
                return None
            raise
        metadata = data["metadata"]
        if metadata["source"]["provider"] != source.provider or metadata["dataset_version"] != source.dataset_version:
            raise _Stop("Conflict", "历史来源或数据版本不一致")
        if metadata["adjustment"] != "none" or metadata["factor_version"] != "":
            raise _Stop("Conflict", "历史复权语义未经本接口批准")
        self._qualified(metadata["qualification"])
        return data

    def _prepare_history(self, source, request, deadline):
        try:
            return self._history_data(source, "history.read", request, deadline)
        except _Stop as exc:
            if exc.status != "Pending":
                raise
        # Pending 不携带 bars，但准备过程可能已持久发布部分分钟。
        # 一次有界回查让后续缺口计算基于已验证事实，仍由原网格决定完整性。
        try:
            return self._history_data(source, "history.query", request, deadline)
        except _Stop as exc:
            if exc.status != "Pending":
                raise
            return None

    def _plans(self, symbol, start, end, cutoff, deadline, *, plan_limit=None):
        count = (end.date() - start.date()).days // 3 + 1
        if count > self.max_windows:
            raise _Stop("Backpressure", "历史窗口数量超过预算")
        plans, day, total = [], start.date(), 0
        while day <= end.date():
            stop = min(day + timedelta(days=2), end.date())
            plan = self._invoke(self.calendar, "minutes", deadline, symbol, day, stop, cutoff)
            if (not isinstance(plan, CalendarSlice) or plan.version != self.calendar_version
                    or type(plan.expected_minutes) is not tuple or len(plan.expected_minutes) > 10000
                    or type(plan.authoritative_empty) is not bool):
                raise _Stop("Conflict", "交易日历计划或版本不一致")
            lower = max(start, datetime.combine(day, day_time(), SHANGHAI))
            upper = min(end, datetime.combine(stop, day_time(23, 59), SHANGHAI))
            selected, previous = [], 0
            for minute in plan.expected_minutes:
                if type(minute) is not int or minute <= previous:
                    raise _Stop("Conflict", "交易日历分钟重复或倒序")
                try:
                    stamp = datetime.strptime(str(minute), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)
                except ValueError:
                    raise _Stop("Conflict", "交易日历分钟不合格") from None
                if len(str(minute)) != 12 or not day <= stamp.date() <= stop or stamp > cutoff:
                    raise _Stop("Conflict", "交易日历分钟越界")
                previous = minute
                if lower <= stamp <= upper:
                    selected.append(minute)
            if plan.authoritative_empty:
                try:
                    _text(plan.evidence_ref, 2048)
                except ValueError:
                    raise _Stop("Conflict", "空交易日历缺少权威证据") from None
                if plan.expected_minutes:
                    raise _Stop("Conflict", "空交易日历与分钟矛盾")
            elif not plan.expected_minutes:
                raise _Stop("Pending", "尚无可证明的闭合分钟网格")
            total += len(selected)
            if total > (self.max_bars if plan_limit is None else plan_limit):
                raise _Stop("Backpressure", "历史分钟数量超过预算")
            plans.append((lower, upper, selected))
            day = stop + timedelta(days=1)
        return plans

    @staticmethod
    def _merge(symbol, source, data, expected, merged, provenance):
        if data is None:
            return
        metadata = data["metadata"]
        identities = provenance.setdefault(source.name, {})
        identity = json.dumps(metadata, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))
        identities.setdefault(identity, metadata)
        for row in data["bars"]:
            if row["minute"] not in expected:
                continue
            bar = MinuteBar(symbol, row["minute"], row["open"], row["high"], row["low"], row["close"],
                            row["volume"], row["amount"], source.name)
            old = merged.get(bar.minute)
            if old is not None:
                fields = ("open", "high", "low", "close", "volume", "amount")
                if any(getattr(old, field) != getattr(bar, field) for field in fields):
                    raise _Stop("Conflict", "相同分钟出现矛盾量价事实")
            else:
                merged[bar.minute] = bar

    def _read_plans(self, symbol, plans, deadline, provenance):
        """范围读取与尾部读取共享来源比较、补齐及全量交付边界。"""
        exchange, code = _security(symbol)
        result, missing = [], []
        active = next((source for source in self.sources if source.allow_prepare), None)
        for lower, upper, minutes in plans:
            if not minutes:
                continue
            request = {"exchange": exchange, "code": code, "from": _minute(lower), "to": _minute(upper),
                       "expected_minutes": minutes, "calendar_version": self.calendar_version}
            expected, merged = set(minutes), {}
            for source in self.sources:
                data = self._history_data(source, "history.query", request, deadline)
                self._merge(symbol, source, data, expected, merged, provenance)
            gaps = sorted(expected - merged.keys())
            if gaps and active is not None:
                prepare_request = dict(request, **{"from": gaps[0], "to": gaps[-1], "expected_minutes": gaps})
                data = self._prepare_history(active, prepare_request, deadline)
                self._merge(symbol, active, data, expected, merged, provenance)
            missing.extend(sorted(expected - merged.keys()))
            result.extend(merged[minute] for minute in minutes if minute in merged)
        self._check(deadline)
        if missing:
            raise _Stop("Pending", "历史仍有未补齐分钟", missing)
        return HistoryResult("Ok", "", tuple(result), (), _provenance(provenance), self.calendar_version)

    def history_1m(self, symbol, start, end, *, as_of=None):
        """按权威分钟网格原子返回完整历史；错误和缺口结果 bars 恒为空。"""
        provenance = {}
        try:
            self._guard()
            deadline = time.monotonic() + self.timeout
            _security(symbol)
            start, end, cutoff = _instant(start, minute=True), _instant(end, minute=True), self._as_of(as_of)
            if start > end or end > cutoff:
                raise ValueError("历史范围越界")
            plans = self._plans(symbol, start, end, cutoff, deadline)
            return self._read_plans(symbol, plans, deadline, provenance)
        except _Stop as exc:
            return HistoryResult(exc.status, exc.reason, (), exc.missing, _provenance(provenance), self.calendar_version)
        except (ValueError, TypeError, OverflowError):
            return HistoryResult("InvalidInput", "历史请求参数不合格", (), (), _empty(), self.calendar_version)
        except Exception:
            return HistoryResult("Unavailable", "历史依赖调用失败", (), (), _empty(), self.calendar_version)

    def tail_history_1m(self, symbol, count, *, end=None, as_of=None):
        """按权威日历倒查最后count分钟；缺失源行仍按预期分钟补齐。"""
        provenance = {}
        try:
            self._guard()
            deadline = time.monotonic() + self.timeout
            _security(symbol)
            if type(count) is not int or count < 1 or count > self.max_bars:
                raise ValueError("尾部条数超过容量")
            cutoff = self._as_of(as_of)
            upper = cutoff.replace(second=0, microsecond=0) if end is None else _instant(end, minute=True)
            if upper > cutoff:
                raise ValueError("尾部截止时间超前")
            earliest = datetime(1992, 1, 1, tzinfo=SHANGHAI)
            plans, needed = [], count
            for _ in range(self.max_windows):
                lower = max(earliest, datetime.combine(upper.date(), day_time(), SHANGHAI) - timedelta(days=2))
                # 一次最多三日的日历扫描独立有界；只把所需末尾分钟计入交付容量。
                window = self._plans(symbol, lower, upper, cutoff, deadline, plan_limit=10000)
                for start, stop, minutes in reversed(window):
                    selected = minutes[-needed:]
                    if selected:
                        begin = datetime.strptime(str(selected[0]), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)
                        finish = datetime.strptime(str(selected[-1]), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)
                        plans.append((begin, finish, selected))
                        needed -= len(selected)
                self._check(deadline)
                if not needed:
                    return self._read_plans(symbol, list(reversed(plans)), deadline, provenance)
                if lower == earliest:
                    break
                upper = lower - timedelta(minutes=1)
            raise _Stop("Pending", "回溯预算内的权威历史分钟不足")
        except _Stop as exc:
            return HistoryResult(exc.status, exc.reason, (), exc.missing, _provenance(provenance), self.calendar_version)
        except (ValueError, TypeError, OverflowError):
            return HistoryResult("InvalidInput", "尾部历史请求参数不合格", (), (), _empty(), self.calendar_version)
        except Exception:
            return HistoryResult("Unavailable", "历史依赖调用失败", (), (), _empty(), self.calendar_version)

    def quote(self, symbol, *, as_of=None, max_age_seconds=60):
        """返回独立只读快照；新鲜度始终取源时间，接收时间不刷新行情年龄。"""
        try:
            self._guard()
            deadline = time.monotonic() + self.timeout
            exchange, code = _security(symbol)
            cutoff = self._as_of(as_of)
            _bound(max_age_seconds, zero=True)
            active = next((source for source in self.sources if source.allow_prepare), None)
            if active is None:
                raise _Stop("Unavailable", "缺少活动行情源")
            data = self._wire(active, "quotes.query", [exchange + "." + code], deadline)
            self._qualified(data["metadata"]["qualification"])
            row = data["snapshots"][0]
            if row["source"]["provider"] != active.provider:
                raise _Stop("Conflict", "快照供应商不一致")
            stamp = datetime.strptime(str(row["date"]) + f"{row['action_time'] // 1000:06d}", "%Y%m%d%H%M%S")
            stamp = stamp.replace(tzinfo=SHANGHAI, microsecond=(row["action_time"] % 1000) * 1000)
            if stamp > cutoff or (cutoff - stamp).total_seconds() > max_age_seconds:
                raise _Stop("Unavailable", "快照源时间超前或已过期")
            self._check(deadline)
            return QuoteResult("Ok", "", _freeze(data))
        except _Stop as exc:
            return QuoteResult(exc.status, exc.reason, _empty())
        except (ValueError, TypeError, OverflowError):
            return QuoteResult("InvalidInput", "快照请求参数不合格", _empty())
        except Exception:
            return QuoteResult("Unavailable", "快照依赖调用失败", _empty())

    def subscribe_minutes(self, symbol, after):
        """从事实 owner 已提交游标重建至少一次订阅；不创建后台线程。"""
        try:
            self._guard()
        except _Stop as exc:
            raise RuntimeError(exc.reason) from None
        _security(symbol)
        after = _instant(after, minute=True)
        if after > self._as_of(None):
            raise ValueError("分钟订阅游标超前")
        return MinuteSubscription(self, symbol, after)

    def close(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError("行情接口由创建线程独占")
        self._closed = True


class MinuteSubscription:
    """本地未确认批次冻结重投；只有正确 ack 才推进内存游标。"""

    def __init__(self, market, symbol, after):
        self._market, self._symbol, self._after = market, symbol, after
        self._owner, self._closed, self._pending = threading.get_ident(), False, None

    def _guard(self):
        if self._owner != threading.get_ident():
            raise RuntimeError("分钟订阅由创建线程独占")
        if self._closed or self._market._closed:
            raise RuntimeError("分钟订阅已关闭")

    def poll(self, *, as_of=None, until=None):
        """按until有界扫描；current始终按as_of判定，空权威扫描也等待确认。"""
        try:
            self._guard()
        except RuntimeError:
            return MinuteBatch("Unavailable", "", (), "closed-source-poll", "分钟订阅不可用", _empty())
        if self._pending is not None:
            return self._pending
        try:
            cutoff = self._market._as_of(as_of)
            last = cutoff.replace(second=0, microsecond=0)
            through = last if until is None else _instant(until, minute=True)
            if cutoff < self._after or through < self._after or through > cutoff:
                raise ValueError("分钟订阅截止时间早于游标")
        except Exception:
            return MinuteBatch("InvalidInput", "", (), "closed-source-poll", "分钟订阅参数不合格", _empty())
        start = self._after + timedelta(minutes=1)
        if start > through:
            return MinuteBatch("Ok", "", (), "closed-source-poll", "", _empty())
        history = self._market.history_1m(self._symbol, start, through, as_of=cutoff)
        if history.status != "Ok":
            return MinuteBatch(history.status, "", (), "closed-source-poll", history.reason, history.provenance)
        bars = tuple(replace(bar, delivery="current" if bar.minute == _minute(last) else "recovered") for bar in history.bars)
        # 扫描范围与日历也是确认事实；权威空范围需要稳定身份并可推进游标。
        identity = {"symbol": self._symbol, "after": _minute(self._after), "through": _minute(through),
                    "calendar_version": history.calendar_version, "bars": [asdict(bar) for bar in bars],
                    "provenance": json.loads(json.dumps(history.provenance, default=lambda value: dict(value)))}
        raw = json.dumps(identity, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
        batch = MinuteBatch("Ok", hashlib.sha256(raw).hexdigest(), bars, "closed-source-poll", "", history.provenance,
                            _minute(self._after), _minute(through), history.calendar_version)
        self._pending = batch
        return batch

    def ack(self, batch_id):
        self._guard()
        if type(batch_id) is not str or self._pending is None or batch_id != self._pending.batch_id:
            return False
        self._after = datetime.strptime(str(self._pending.through), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)
        self._pending = None
        return True

    def close(self):
        if self._owner != threading.get_ident():
            raise RuntimeError("分钟订阅由创建线程独占")
        self._closed, self._pending = True, None
