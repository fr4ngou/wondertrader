"""消费原日历 owner 的分钟计划；交易日与会话规则由服务端维护。"""
from __future__ import annotations

from datetime import date, datetime, time as day_time, timedelta, timezone
import hashlib
import http.client
import io
import ipaddress
import math
import re
import ssl
import time
from urllib.parse import urlsplit

from . import strict_json
from .history_runner import CalendarSlice, _DeadlineRaw, canonical_bytes

__all__ = ["CalendarProjectionProvider", "calendar_binding_version", "CalendarUnavailable",
           "CalendarConflict", "CalendarTimeout"]

QUERY_SCHEMA = "guanheng.calendar.query.v1"
PROJECTION_SCHEMA = "guanheng.calendar.minutes.v1"
PROJECTION_VERSION = "cn-a-share-continuous-right-1m-v1"
MAX_RESPONSE_BYTES = 512 * 1024
SHANGHAI = timezone(timedelta(hours=8))
_FIELDS = {"schema_version", "symbol", "calendar_version", "version", "projection_version", "scope",
           "security_exclusions", "start_date", "end_date", "as_of", "expected_minutes",
           "authoritative_empty", "facts", "facts_sha256", "sha256"}
_FACT_FIELDS = {"market", "trade_date", "is_trading_day", "open_at", "close_at", "calendar_version",
                "source_id", "source_url", "source_retrieved_at", "evidence_refs"}


class CalendarUnavailable(OSError):
    """单次传输或证据 owner 不可用，调用者可在后续回合重新读取。"""


class CalendarConflict(ValueError):
    """输入、响应身份、事实或不可变证据冲突。"""


class CalendarTimeout(CalendarUnavailable, TimeoutError):
    """完整 HTTP、校验与证据调用预算耗尽。"""


def _text(value, maximum=128):
    if type(value) is not str or not 1 <= len(value) <= maximum or any(ord(c) < 32 for c in value):
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def _bound(value, minimum=1):
    # Range comparison rejects arbitrary-size integers before float conversion.
    return type(value) in (int, float) and minimum <= value <= 30 and math.isfinite(value)


def calendar_binding_version(source_version):
    """按公开线协议绑定源版本和投影版本；保持与原 owner 的规范 JSON 一致。"""
    if not _text(source_version):
        raise CalendarConflict("history calendar source version invalid")
    raw = canonical_bytes({"calendar_version": source_version, "projection_version": PROJECTION_VERSION})
    return "cal-min1-v1-" + hashlib.sha256(raw).hexdigest()


def _date(value):
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError
    return date.fromisoformat(value)


def _instant(value):
    if (type(value) is not str or not 20 <= len(value) <= 64
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})", value) is None):
        raise ValueError
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError
    return parsed


def _sha(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


class CalendarProjectionProvider:
    """单次 POST 获取计划并回读存证，返回既有 CalendarSlice。

    timeout 为完整调用的秒预算（1..30），http_timeout 为其中单次 HTTP 上界。
    evidence 必须声明有限 timeout 并提供 put/get；每次调用前须容纳完整上界。
    本类不共享可变请求状态，线程安全性取决于注入 evidence owner。
    阻塞依赖及资源清理的硬停止由外部监督者承担。
    """
    def __init__(self, base_url, token, evidence, source_calendar_version, *, timeout=15,
                 http_timeout=5, max_response_bytes=MAX_RESPONSE_BYTES):
        try:
            if (type(base_url) is not str or not 1 <= len(base_url) <= 2048
                    or any(ord(c) <= 32 or ord(c) > 126 for c in base_url) or "\\" in base_url):
                raise ValueError
            url = urlsplit(base_url)
            if (url.scheme not in ("http", "https") or not url.hostname or url.username is not None
                    or url.password is not None or url.path not in ("", "/") or url.query or url.fragment
                    or (url.port is not None and not 1 <= url.port <= 65535)
                    or (url.scheme == "http" and not ipaddress.ip_address(url.hostname).is_loopback)):
                raise ValueError
        except (ValueError, TypeError):
            raise CalendarConflict("history calendar transport configuration invalid") from None
        if (type(token) is not str or not 1 <= len(token) <= 4096
                or any(ord(c) < 33 or ord(c) > 126 for c in token)
                or not _bound(timeout) or not _bound(http_timeout, 0.001) or http_timeout > timeout
                or type(max_response_bytes) is not int or not 1 <= max_response_bytes <= MAX_RESPONSE_BYTES):
            raise CalendarConflict("history calendar configuration invalid")
        if (not callable(getattr(evidence, "put", None)) or not callable(getattr(evidence, "get", None))
                or not _bound(getattr(evidence, "timeout", None))):
            raise CalendarConflict("history calendar bounded evidence owner required")
        self.version = calendar_binding_version(source_calendar_version)
        self.source_calendar_version, self.evidence = source_calendar_version, evidence
        self.host, self.port, self.scheme, self.token = url.hostname, url.port, url.scheme, token
        self.timeout, self.http_timeout = float(timeout), float(http_timeout)
        self.max_response_bytes = max_response_bytes

    @staticmethod
    def _check(deadline, bound=0):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or remaining < bound:
            raise CalendarTimeout("history calendar deadline exceeded") from None

    def _exchange(self, body, deadline):
        self._check(deadline, self.http_timeout)
        exchange_deadline = min(deadline, time.monotonic() + self.http_timeout)

        class Response(http.client.HTTPResponse):
            def __init__(self, sock, *args, **kwargs):
                super().__init__(sock, *args, **kwargs)
                self.fp = io.BufferedReader(_DeadlineRaw(self.fp, sock, exchange_deadline))

        connection = (http.client.HTTPSConnection(self.host, self.port, timeout=self.http_timeout,
                      context=ssl.create_default_context()) if self.scheme == "https"
                      else http.client.HTTPConnection(self.host, self.port, timeout=self.http_timeout))
        connection.response_class = Response
        response = None
        try:
            connection.connect()
            self._check(exchange_deadline)
            connection.sock.settimeout(exchange_deadline - time.monotonic())
            connection.request("POST", "/v1/market/calendar/minutes/query", body=body,
                headers={"X-Internal-Token": self.token, "Content-Type": "application/json",
                         "Accept": "application/json", "Connection": "close"})
            response = connection.getresponse()
            if (response.status != 200 or response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json"
                    or response.getheader("Content-Encoding", "identity").lower() != "identity"):
                raise CalendarUnavailable("history calendar response rejected") from None
            lengths = response.headers.get_all("Content-Length", [])
            if len(lengths) > 1 or (lengths and (not lengths[0].isascii() or not lengths[0].isdecimal()
                    or len(lengths[0]) > 9 or int(lengths[0]) > self.max_response_bytes)):
                raise CalendarUnavailable("history calendar response limit invalid") from None
            if lengths and response.getheader("Transfer-Encoding") is not None:
                raise CalendarUnavailable("history calendar response framing invalid") from None
            chunks, count = [], 0
            while True:
                self._check(exchange_deadline)
                chunk = response.read1(min(65536, self.max_response_bytes + 1 - count))
                if not chunk:
                    break
                chunks.append(chunk)
                count += len(chunk)
                if count > self.max_response_bytes:
                    raise CalendarUnavailable("history calendar response limit exceeded") from None
            if lengths and count != int(lengths[0]):
                raise CalendarUnavailable("history calendar response truncated") from None
            self._check(exchange_deadline)
            return b"".join(chunks)
        except (TimeoutError, CalendarTimeout):
            raise CalendarTimeout("history calendar deadline exceeded") from None
        except CalendarUnavailable:
            raise
        except (OSError, http.client.HTTPException, ValueError):
            raise CalendarUnavailable("history calendar transport unavailable") from None
        finally:
            try:
                if response is not None:
                    response.close()
            except Exception:
                raise CalendarUnavailable("history calendar transport cleanup unavailable") from None
            finally:
                try:
                    connection.close()
                except Exception:
                    raise CalendarUnavailable("history calendar transport cleanup unavailable") from None

    def _validate(self, value, query):
        if type(value) is not dict or set(value) != _FIELDS:
            raise ValueError
        expected = {**query, "schema_version": PROJECTION_SCHEMA, "version": self.version,
                    "projection_version": PROJECTION_VERSION, "scope": "exchange_plan",
                    "security_exclusions": "not_applied"}
        if any(type(value[k]) is not str or value[k] != v for k, v in expected.items()):
            raise ValueError
        start, end, cutoff = _date(value["start_date"]), _date(value["end_date"]), _instant(value["as_of"])
        facts = value["facts"]
        if type(facts) is not list or len(facts) != 2 * ((end - start).days + 1):
            raise ValueError
        required = [(start + timedelta(days=i), market) for i in range((end - start).days + 1) for market in ("SH", "SZ")]
        sessions = {}
        for item, (trade_date, market) in zip(facts, required):
            if (type(item) is not dict or set(item) != _FACT_FIELDS or item["market"] != market
                    or _date(item["trade_date"]) != trade_date or type(item["is_trading_day"]) is not bool
                    or item["calendar_version"] != self.source_calendar_version
                    or not _text(item["source_id"], 4096) or item["source_id"] == "unversioned"
                    or not _text(item["source_url"], 4096) or _instant(item["source_retrieved_at"]) > cutoff
                    or type(item["evidence_refs"]) is not list or not item["evidence_refs"]
                    or any(not _text(ref, 4096) for ref in item["evidence_refs"])):
                raise ValueError
            source_url = urlsplit(item["source_url"])
            if source_url.scheme not in ("http", "https") or not source_url.hostname:
                raise ValueError
            if item["is_trading_day"]:
                opens, closes = _instant(item["open_at"]), _instant(item["close_at"])
                if (opens >= closes or opens.astimezone(SHANGHAI).date() != trade_date
                        or closes.astimezone(SHANGHAI).date() != trade_date):
                    raise ValueError
                session = (True, opens, closes)
            else:
                if item["open_at"] is not None or item["close_at"] is not None:
                    raise ValueError
                session = (False, None, None)
            if market == "SZ" and sessions[trade_date] != session:
                raise ValueError
            sessions[trade_date] = session
        minutes = value["expected_minutes"]
        if (type(minutes) is not list or len(minutes) > 720 or any(type(v) is not int for v in minutes)
                or minutes != sorted(set(minutes)) or type(value["authoritative_empty"]) is not bool):
            raise ValueError
        for minute in minutes:
            if len(str(minute)) != 12:
                raise ValueError
            instant = datetime.strptime(str(minute), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)
            if not start <= instant.date() <= end or instant > cutoff:
                raise ValueError
            opened, opens, closes = sessions[instant.date()]
            if not opened or not opens < instant <= closes:
                raise ValueError
        if value["authoritative_empty"] and (minutes or any(session[0] for session in sessions.values())
                or datetime.combine(end + timedelta(days=1), day_time(), SHANGHAI) > cutoff):
            raise ValueError
        if (not _sha(value["facts_sha256"]) or not _sha(value["sha256"])
                or hashlib.sha256(canonical_bytes(facts)).hexdigest() != value["facts_sha256"]
                or hashlib.sha256(canonical_bytes({k: v for k, v in value.items() if k != "sha256"})).hexdigest() != value["sha256"]):
            raise ValueError
        return canonical_bytes(value)

    def _evidence_call(self, method, deadline, *args):
        bound = getattr(self.evidence, "timeout", None)
        if not _bound(bound):
            raise CalendarConflict("history calendar bounded evidence owner required")
        self._check(deadline, bound)
        try:
            result = getattr(self.evidence, method)(*args)
        except TimeoutError:
            raise CalendarTimeout("history calendar deadline exceeded") from None
        except ValueError:
            raise CalendarConflict("history calendar evidence conflict") from None
        except Exception:
            raise CalendarUnavailable("history calendar evidence unavailable") from None
        self._check(deadline)
        return result

    def minutes(self, symbol, start_date, end_date, as_of):
        """验证精确证券/日期/as_of，再存证回读；失败保留固定去敏错误。"""
        deadline = time.monotonic() + self.timeout
        try:
            if (type(symbol) is not str or re.fullmatch(r"[0-9]{6}\.(SH|SZ)", symbol) is None
                    or type(start_date) is not date or type(end_date) is not date
                    or not 0 <= (end_date - start_date).days < 3 or not isinstance(as_of, datetime)
                    or as_of.tzinfo is None or as_of.utcoffset() is None or as_of > datetime.now(timezone.utc)):
                raise ValueError
            query = {"schema_version": QUERY_SCHEMA, "symbol": symbol, "calendar_version": self.source_calendar_version,
                     "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "as_of": as_of.isoformat()}
            _instant(query["as_of"])
        except (ValueError, TypeError, OverflowError):
            raise CalendarConflict("history calendar query invalid") from None
        body = canonical_bytes(query)
        self._check(deadline)
        raw = self._exchange(body, deadline)
        self._check(deadline)
        try:
            value = strict_json(raw)
            canonical = self._validate(value, query)
        except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
            raise CalendarConflict("history calendar projection invalid") from None
        self._check(deadline)
        # response.sha256 排除自身；存储摘要覆盖完整已验响应的规范字节。
        storage_sha256 = hashlib.sha256(canonical).hexdigest()
        self._check(deadline)
        reference = self._evidence_call("put", deadline, storage_sha256, canonical)
        if not _text(reference, 2048):
            raise CalendarConflict("history calendar evidence reference invalid")
        stored = self._evidence_call("get", deadline, storage_sha256)
        if type(stored) is not bytes or stored != canonical or hashlib.sha256(stored).hexdigest() != storage_sha256:
            raise CalendarConflict("history calendar evidence content invalid")
        self._check(deadline)
        return CalendarSlice(self.version, tuple(value["expected_minutes"]), value["authoritative_empty"], reference)
