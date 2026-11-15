"""Standard-library client and strict wire contract for guanheng.market.v1.

No WT library, QMT checkout, account or trading client is imported here.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import http.client
import ipaddress
import json
import math
import re
import socket
import ssl
import time
from urllib.parse import urlsplit


__version__ = "0.21.1"
API_VERSION = "guanheng.market.v1"
MAX_REQUEST_BYTES = 262144
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_ROWS = 10000
MAX_SYMBOLS = 64
PATHS = {
    "capabilities": "/api/market/v1/capabilities",
    "history.query": "/api/market/v1/history/query",
    "history.source-query": "/api/market/v1/history/source-query",
    "history.source-daily-query": "/api/market/v1/history/source-daily-query",
    "history.source-daily-batch-query": "/api/market/v1/history/source-daily-batch-query",
    "market.source-snapshot-query": "/api/market/v1/source-snapshot/query",
    "market.source-day-facts-query": "/api/market/v1/source-day-facts/query",
    "market.source-supplement-query": "/api/market/v1/source-supplement/query",
    "market.source-security-query": "/api/market/v1/source-security/query",
    "history.read": "/api/market/v1/history/read",
    "history.prepare": "/api/market/v1/history/prepare",
    "history.work": "/api/market/v1/history/work",
    "history.task.prepare": "/api/market/v1/history/task/prepare",
    "history.task.inspect": "/api/market/v1/history/task/inspect",
    "history.task.work": "/api/market/v1/history/task/work",
    "history.task.release": "/api/market/v1/history/task/release",
    "quotes.query": "/api/market/v1/quotes/query",
}
STATUS_CODES = frozenset(("Ok", "Unavailable", "InvalidInput", "NotSupported", "Pending",
                         "Timeout", "Backpressure", "StaleSession", "Conflict", "IoError"))
QUALIFICATIONS = frozenset(("Unavailable", "DevelopmentVerified", "NativeVerified", "ProductionQualified"))


class MarketProtocolError(ValueError):
    """Unsupported, ambiguous or invalid public wire data; no partial qualification."""


class MarketUnavailable(RuntimeError):
    """Transport or local native dependency unavailable; details exclude secrets."""


class MarketHTTPError(MarketUnavailable):
    def __init__(self, status, response):
        self.http_status, self.response = status, response
        super().__init__("market HTTP request rejected ({0})".format(status))


def _object(value, keys, required=None):
    if type(value) is not dict or set(value) - set(keys) or not set(required or keys) <= set(value):
        raise MarketProtocolError("market object fields are invalid")
    return value


def _text(value, *, limit=1024, empty=False):
    if (type(value) is not str or len(value) > limit or (not value and not empty)
            or any(ord(c) < 32 or 0x7F <= ord(c) <= 0x9F for c in value)):
        raise MarketProtocolError("market text field is invalid")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise MarketProtocolError("market text field is not valid UTF-8") from None
    return value


def _integer(value, minimum=0, maximum=2**64 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise MarketProtocolError("market integer is invalid")
    return value


def _number(value, *, positive=False):
    try:
        valid = (type(value) in (int, float) and math.isfinite(value)
                 and (value > 0 if positive else value >= 0))
    except OverflowError:
        valid = False
    if not valid:
        raise MarketProtocolError("market number is invalid")
    return value


def _enum(value, options):
    if type(value) is not str or value not in options:
        raise MarketProtocolError("market enum is unsupported")
    return value


def _minute(value):
    _integer(value, 199001010000, 209912312359)
    try:
        datetime.strptime(str(value), "%Y%m%d%H%M")
    except ValueError:
        raise MarketProtocolError("market minute is invalid") from None
    return value


def _symbol(value):
    if type(value) is not str or not re.fullmatch(r"(?:SSE|SZSE)\.[0-9]{6}", value):
        raise MarketProtocolError("market symbol is invalid")
    return value


def _queue_id(value):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{32}", value):
        raise MarketProtocolError("history queue identity is invalid")
    return value


def _source(value, *, daily=False):
    _object(value, ("provider", "instance_id", "session_id", "generation"))
    # 公开指数提供者只进入日线；canonical/分钟/快照继续使用原提供者合同。
    providers = ("Qmt", "Tdx", "BaoStock", "Tencent", "CSI", "CNI") if daily else ("Qmt", "Tdx")
    if value["provider"] not in providers:
        raise MarketProtocolError("market provider is unsupported")
    _text(value["instance_id"], limit=128)
    _text(value["session_id"], limit=128)
    _integer(value["generation"], 1)
    return value


def _capability(value):
    _object(value, ("supported", "qualification", "reason"))
    if type(value["supported"]) is not bool:
        raise MarketProtocolError("market capability is invalid")
    _enum(value["qualification"], QUALIFICATIONS)
    if not value["supported"] and value["qualification"] != "Unavailable":
        raise MarketProtocolError("unsupported capability cannot be qualified")
    if value["supported"] and value["qualification"] == "Unavailable":
        raise MarketProtocolError("supported capability lacks qualification")
    _text(value["reason"], empty=True)


def _list(value, limit):
    if type(value) is not list or len(value) > limit:
        raise MarketProtocolError("market list exceeds its budget")
    return value


def strict_json(data):
    """Reject duplicates, non-finite numbers, invalid UTF-8 and excessive nesting."""
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise MarketProtocolError("market JSON contains duplicate fields")
            out[key] = value
        return out

    def invalid(_value):
        raise MarketProtocolError("market JSON contains a non-finite number")

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
        todo = [(value, 0)]
        while todo:
            item, depth = todo.pop()
            if depth > 16:
                raise MarketProtocolError("market JSON nesting exceeds its budget")
            if type(item) is dict:
                todo.extend((v, depth + 1) for v in item.values())
            elif type(item) is list:
                todo.extend((v, depth + 1) for v in item)
            elif type(item) is float and not math.isfinite(item):
                invalid(item)
        return value
    except (UnicodeError, ValueError, RecursionError, OverflowError):
        raise MarketProtocolError("market JSON is invalid") from None


def encode_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise MarketProtocolError("market JSON cannot be encoded") from None


def validate_request(value):
    _object(value, ("api_version", "action", "request", "symbols", "queue_id", "task_id"),
            ("api_version", "action"))
    if value["api_version"] != API_VERSION:
        raise MarketProtocolError("market version or action is unsupported")
    action = _enum(value["action"], PATHS)
    keys = {"api_version", "action"}
    if action == "history.source-query":
        from .source_history import validate_source_request
        keys.add("request")
        validate_source_request(value.get("request"))
    elif action == "history.source-daily-query":
        from .source_history import validate_source_daily_request
        keys.add("request")
        validate_source_daily_request(value.get("request"))
    elif action == "history.source-daily-batch-query":
        from .daily_batch import validate_daily_batch_request
        keys.add('request')
        validate_daily_batch_request(value.get('request'))
    elif action == 'market.source-security-query':
        from .security import validate_security_request
        keys.add('request')
        validate_security_request(value.get('request'))
    elif action == 'market.source-day-facts-query':
        from .daily_facts import validate_facts_request
        keys.add('request')
        validate_facts_request(value.get('request'))
    elif action == 'market.source-supplement-query':
        from .supplement_facts import validate_supplement_request
        keys.add('request')
        validate_supplement_request(value.get('request'))
    elif action == 'market.source-snapshot-query':
        from .market_snapshot import validate_snapshot_request
        keys.add('request')
        validate_snapshot_request(value.get('request'))
    elif action in ("history.query", "history.read", "history.prepare", "history.task.prepare"):
        keys.add("request")
        r = value.get("request")
        fields = ("exchange", "code", "from", "to", "expected_minutes", "calendar_version")
        if action == "history.query":
            fields += ("period_minutes", "limit")
        _object(r, fields,
                ("exchange", "code", "from", "to"))
        if r["exchange"] not in ("SSE", "SZSE") or type(r["code"]) is not str or not re.fullmatch(r"[0-9]{6}", r["code"]):
            raise MarketProtocolError("history security is invalid")
        if _minute(r["from"]) > _minute(r["to"]):
            raise MarketProtocolError("history range is invalid")
        expected = _list(r.get("expected_minutes", []), MAX_ROWS)
        for minute in expected:
            if not r["from"] <= _minute(minute) <= r["to"]:
                raise MarketProtocolError("expected minute lies outside requested history")
        if expected != sorted(set(expected)):
            raise MarketProtocolError("expected minutes must be sorted and unique")
        calendar = _text(r.get("calendar_version", ""), limit=128, empty=True)
        if expected and not calendar:
            raise MarketProtocolError("expected minutes require a calendar version")
        selected = "period_minutes" in r or "limit" in r
        if selected:
            period = _integer(r.get("period_minutes", 1), 1, 60)
            if period not in (1, 5, 15, 30, 60):
                raise MarketProtocolError("native history period is unsupported")
            if "limit" in r:
                _integer(r["limit"], 1, MAX_ROWS)
            if expected or calendar:
                raise MarketProtocolError("history window cannot use an m1 coverage grid")
    elif action in ("history.task.inspect", "history.task.work", "history.task.release"):
        keys.update(("queue_id", "task_id"))
        _queue_id(value.get("queue_id"))
        _integer(value.get("task_id"), 1)
    elif action == "quotes.query":
        keys.add("symbols")
        symbols = _list(value.get("symbols"), MAX_SYMBOLS)
        if not symbols or len(set(_symbol(s) for s in symbols)) != len(symbols):
            raise MarketProtocolError("quote symbols must be nonempty and unique")
    if set(value) != keys:
        raise MarketProtocolError("market action fields are invalid")
    return value


def _metadata(m):
    _object(m, ("source", "qualification", "dataset_version", "source_license", "adjustment",
                "factor_version", "minute_boundary", "timezone", "volume_to_shares",
                "amount_to_yuan", "content_id"))
    _source(m["source"])
    _enum(m["qualification"], QUALIFICATIONS - {"Unavailable"})
    _text(m["dataset_version"], limit=256)
    _text(m["source_license"], limit=1024)
    _text(m["factor_version"], limit=256, empty=True)
    if (m["adjustment"] not in ("none", "front_ratio")
            or (m["adjustment"] != "none" and not m["factor_version"])
            or m["minute_boundary"] != "right" or m["timezone"] != "Asia/Shanghai"):
        raise MarketProtocolError("history source semantics are unsupported")
    for key in ("volume_to_shares", "amount_to_yuan"):
        _number(m[key], positive=True)
    if type(m["content_id"]) is not str or not re.fullmatch("[0-9a-f]{64}", m["content_id"]):
        raise MarketProtocolError("history content identity is invalid")


def _prices(row, close_key, volume_key, amount_key):
    for key in ("open", "high", "low", close_key):
        _number(row[key], positive=True)
    for key in (volume_key, amount_key):
        _number(row[key])
    if row["high"] < max(row["open"], row["low"], row[close_key]) or row["low"] > min(row["open"], row["high"], row[close_key]):
        raise MarketProtocolError("market OHLC is inconsistent")


def validate_response(value, request):
    validate_request(request)
    _object(value, ("api_version", "status", "data"))
    if value["api_version"] != API_VERSION:
        raise MarketProtocolError("market response version is unsupported")
    status, data, action = value["status"], value["data"], request["action"]
    _object(status, ("code", "reason"))
    _enum(status["code"], STATUS_CODES)
    _text(status["reason"], empty=status["code"] == "Ok")
    if type(data) is not dict:
        raise MarketProtocolError("market response data must be an object")
    ok = status["code"] == "Ok"
    if not ok and not data:
        return value
    if action == "capabilities":
        _object(data, ("source", "snapshot", "history", "trading"))
        if data["source"] is not None:
            _source(data["source"])
        for key in ("snapshot", "history", "trading"):
            _capability(data[key])
        if data["trading"]["supported"]:
            raise MarketProtocolError("market API cannot grant trading")
        if data["source"] is None and any(data[k]["supported"] for k in ("snapshot", "history")):
            raise MarketProtocolError("market capability has no source")
    elif action.startswith("history.task."):
        _object(data, ("queue_id", "task_id", "state"))
        _queue_id(data["queue_id"])
        task_id = _integer(data["task_id"], 1)
        state = _enum(data["state"], ("Pending", "Complete", "Unavailable", "Failed", "Released"))
        if action != "history.task.prepare":
            if data["queue_id"] != request["queue_id"] or task_id != request["task_id"]:
                raise MarketProtocolError("history task response identity differs from its request")
        code = status["code"]
        consistent = {
            "Pending": code in ("Pending", "Backpressure"),
            "Complete": ok and action != "history.task.release",
            "Unavailable": code in ("Unavailable", "NotSupported"),
            "Failed": code not in ("Ok", "Pending", "Unavailable", "NotSupported"),
            "Released": ok and action == "history.task.release",
        }
        if (not consistent[state] or (code == "Pending" and state != "Pending")
                or (action == "history.task.release" and not ok)):
            raise MarketProtocolError("history task status and state disagree")
    elif action in ("history.prepare", "history.work"):
        _object(data, ("task_id", "state"))
        _integer(data["task_id"])
        if data["state"] not in ("Pending", "Complete", "Unavailable", "Failed"):
            raise MarketProtocolError("history task state is unsupported")
    elif not ok:
        raise MarketProtocolError("failed market response contains unexpected payload")
    elif action == "history.source-query":
        from .source_history import validate_source_data
        validate_source_data(data, request["request"])
    elif action == "history.source-daily-query":
        from .source_history import validate_source_daily_data
        validate_source_daily_data(data, request["request"])
    elif action == "history.source-daily-batch-query":
        from .daily_batch import validate_daily_batch_data
        validate_daily_batch_data(data,request['request'])
    elif action == 'market.source-security-query':
        from .security import validate_security_data
        validate_security_data(data,request['request'])
    elif action == 'market.source-day-facts-query':
        from .daily_facts import validate_facts_data
        validate_facts_data(data,request['request'])
    elif action == 'market.source-supplement-query':
        from .supplement_facts import validate_supplement_data
        validate_supplement_data(data,request['request'])
    elif action == 'market.source-snapshot-query':
        from .market_snapshot import validate_market_snapshot
        validate_market_snapshot(data)
        if data['observation_date'] != request['request']['date']:
            raise MarketProtocolError('market snapshot date differs from request')
        if (not request['request'].get('include_supplement',False)
                and 'supplement_facts_sha256'in data['provenance']):
            raise MarketProtocolError('market snapshot projection differs from request')
    elif action in ("history.query", "history.read"):
        r = request["request"]
        selected = "period_minutes" in r or "limit" in r
        fields = ("bars", "metadata", "coverage", "missing_minutes")
        if selected:
            fields += ("selection",)
        _object(data, fields)
        if selected:
            selection = _object(data["selection"], ("period_minutes", "limit"))
            if (_integer(selection["period_minutes"], 1, 60) != r.get("period_minutes", 1)
                    or _integer(selection["limit"], 0, MAX_ROWS) != r.get("limit", 0)):
                raise MarketProtocolError("history window selection differs from request")
        _metadata(data["metadata"])
        bars, previous = _list(data["bars"], MAX_ROWS), 0
        if selected and r.get("limit") and len(bars) > r["limit"]:
            raise MarketProtocolError("history window exceeds requested count")
        for bar in bars:
            _object(bar, ("minute", "open", "high", "low", "close", "volume", "amount"))
            minute = _minute(bar["minute"])
            if not r["from"] <= minute <= r["to"] or minute <= previous:
                raise MarketProtocolError("history bars are out of range, repeated or unordered")
            _prices(bar, "close", "volume", "amount")
            previous = minute
        missing = _list(data["missing_minutes"], MAX_ROWS)
        for minute in missing:
            if not r["from"] <= _minute(minute) <= r["to"]:
                raise MarketProtocolError("missing minute is outside requested history")
        if missing != sorted(set(missing)) or data["coverage"] not in ("Unknown", "Complete", "Gaps"):
            raise MarketProtocolError("history coverage is invalid")
        if (data["coverage"] == "Complete" and missing) or (data["coverage"] == "Gaps" and not missing):
            raise MarketProtocolError("history coverage disagrees with its gaps")
        if selected and (data["coverage"] != "Unknown" or missing):
            raise MarketProtocolError("history window has no m1 coverage proof")
        expected = r.get("expected_minutes", [])
        if data["coverage"] != "Unknown":
            if not expected or not r.get("calendar_version"):
                raise MarketProtocolError("known coverage lacks a requested calendar")
            actual_missing = sorted(set(expected) - {bar["minute"] for bar in bars})
            if missing != actual_missing:
                raise MarketProtocolError("history coverage disagrees with requested minutes")
    else:
        _object(data, ("snapshots", "metadata"))
        metadata = data["metadata"]
        _object(metadata, ("qualification", "profile_version", "source_license", "timezone",
                           "price_unit", "volume_unit", "amount_unit", "volume_to_shares", "amount_to_yuan"))
        _enum(metadata["qualification"], QUALIFICATIONS - {"Unavailable"})
        _text(metadata["profile_version"], limit=128)
        _text(metadata["source_license"], limit=256)
        if (metadata["timezone"] != "Asia/Shanghai" or metadata["price_unit"] != "CNY"
                or metadata["volume_unit"] != "share" or metadata["amount_unit"] != "CNY"):
            raise MarketProtocolError("quote source units or timezone are unsupported")
        _number(metadata["volume_to_shares"], positive=True)
        _number(metadata["amount_to_yuan"], positive=True)
        seen, source = set(), None
        for row in _list(data["snapshots"], MAX_SYMBOLS):
            _object(row, ("source", "symbol", "date", "action_time", "price", "open", "high", "low",
                          "pre_close", "total_volume", "total_turnover", "full_cumulative", "source_time_verified"))
            _source(row["source"])
            if source is not None and row["source"] != source:
                raise MarketProtocolError("quote response mixes source sessions")
            source = row["source"]
            name = _symbol(row["symbol"])
            if name not in request["symbols"] or name in seen:
                raise MarketProtocolError("quote response contains unrequested or repeated symbols")
            seen.add(name)
            _integer(row["date"], 19900101, 20991231)
            stamp = _integer(row["action_time"], 0, 235959999)
            try:
                datetime.strptime(str(row["date"]) + "{0:06d}".format(stamp // 1000), "%Y%m%d%H%M%S")
            except ValueError:
                raise MarketProtocolError("quote source time is invalid") from None
            _prices(row, "price", "total_volume", "total_turnover")
            _number(row["pre_close"], positive=True)
            if row["full_cumulative"] is not True or row["source_time_verified"] is not True:
                raise MarketProtocolError("quote source semantics are not verified")
        if seen != set(request["symbols"]):
            raise MarketProtocolError("quote response is missing requested symbols")
    return value


def _timeout(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 30:
        raise ValueError("market timeout must be finite and in (0,30] seconds")
    return value


def _token(value):
    if type(value) is not str or not 1 <= len(value) <= 4096 or any(not 33 <= ord(c) <= 126 for c in value):
        raise ValueError("market Bearer token is required")
    return value


class _DeadlineReader:
    """Bound each underlying read by one absolute deadline, including headers."""

    def __init__(self, raw, connection, deadline, maximum):
        self.raw, self.connection, self.deadline, self.remaining = raw, connection, deadline, maximum
        self.header_bytes, self.headers_done = 0, False

    def _before(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("market read deadline expired")
        self.connection.settimeout(remaining)

    def _count(self, data):
        self.remaining -= len(data)
        if self.remaining < 0:
            raise MarketProtocolError("market read budget exceeded")
        return data

    def readline(self, size=-1):
        out = bytearray()
        limit = 32769 if size < 0 else min(size, 32769)
        while len(out) < limit:
            self._before()
            data = self._count(self.raw.read(1))
            if not data:
                break
            out.extend(data)
            if data == b"\n":
                break
        if not self.headers_done:
            self.header_bytes += len(out)
            if self.header_bytes > 32768:
                raise MarketProtocolError("market headers exceed their budget")
            if out in (b"\r\n", b"\n"):
                self.headers_done = True
        return bytes(out)

    def read1(self, size=-1):
        self._before()
        size = min(65536 if size < 0 else size, self.remaining + 1)
        return self._count(self.raw.read1(size))

    def read(self, size=-1):
        out = bytearray()
        while size < 0 or len(out) < size:
            data = self.read1(65536 if size < 0 else min(size - len(out), 65536))
            if not data:
                break
            out.extend(data)
        return bytes(out)

    def readinto(self, target):
        data = self.read(len(target))
        target[:len(data)] = data
        return len(data)

    def close(self):
        self.raw.close()

    def __getattr__(self, name):
        return getattr(self.raw, name)


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("market exchange deadline expired")
    return remaining


def _connection_address(host, connect_ip):
    """数值URL固定路由；域名仅作TLS身份，部署方显式拥有连接地址。"""
    try:
        literal = ipaddress.ip_address(host) if "%" not in host else None
    except ValueError:
        literal = None
    if connect_ip is None:
        if literal is None:
            raise ValueError("HTTPS hostname requires an explicit numeric connect_ip")
        return literal
    if type(connect_ip) is not str or "%" in connect_ip:
        raise ValueError("market connect_ip must be an unscoped numeric IP")
    address = ipaddress.ip_address(connect_ip)
    if literal is not None and address != literal:
        raise ValueError("numeric market endpoint cannot change its connection address")
    return address


class _DeadlineConnection(http.client.HTTPConnection):
    """一次交换拥有socket；数值连接和每次TLS/发送共同消耗原绝对截止。"""

    def __init__(self, host, port, address, deadline, context):
        self.default_port = 443 if context is not None else 80
        super().__init__(host, port, timeout=_remaining(deadline))
        self._address, self._deadline, self._context = address, deadline, context

    def connect(self):
        # 不使用create_connection：即便地址是IP，该便捷函数仍会调用getaddrinfo。
        _remaining(self._deadline)
        family = socket.AF_INET if self._address.version == 4 else socket.AF_INET6
        self.sock = socket.socket(family, socket.SOCK_STREAM)
        target = ((str(self._address), self.port) if family == socket.AF_INET
                  else (str(self._address), self.port, 0, 0))
        try:
            self.sock.settimeout(_remaining(self._deadline))
            self.sock.connect(target)
            _remaining(self._deadline)
            if self._context is not None:
                # wrap成功后所有权转给TLS socket；握手前重新计算TCP消费后的剩余预算。
                self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host,
                                                      do_handshake_on_connect=False)
                self.sock.settimeout(_remaining(self._deadline))
                self.sock.do_handshake()
                _remaining(self._deadline)
        except BaseException:
            self.close()
            raise

    def send(self, data):
        # SDK只发送已编码且有容量限制的bytes；逐段进度避免TLS sendall反复使用旧超时。
        if self.sock is None:
            if not self.auto_open:
                raise http.client.NotConnected()
            self.connect()
        pending = memoryview(data)
        while pending:
            self.sock.settimeout(_remaining(self._deadline))
            sent = self.sock.send(pending)
            if sent <= 0:
                raise OSError("market socket stopped accepting bytes")
            pending = pending[sent:]
        _remaining(self._deadline)


class _JSONTransport:
    """Shared bounded JSON exchange; protocol validation belongs to its caller."""

    def __init__(self, base_url, token, *, timeout=5.0, max_response_bytes=8 * 1024 * 1024,
                 connect_ip=None):
        """HTTPS域名须显式connect_ip；构造只验证配置，不解析DNS或创建连接。"""
        try:
            if (type(base_url) is not str or not 1 <= len(base_url) <= 2048
                    or any(not 33 <= ord(c) <= 126 for c in base_url) or "\\" in base_url):
                raise ValueError
            url = urlsplit(base_url)
            if (url.scheme not in ("http", "https") or not url.hostname
                    or url.username is not None or url.password is not None
                    or url.path not in ("", "/") or url.query or url.fragment or "%" in url.hostname
                    or url.port is not None and not 1 <= url.port <= 65535):
                raise ValueError
            if url.scheme == "http" and not ipaddress.ip_address(url.hostname).is_loopback:
                raise ValueError
            self._address = _connection_address(url.hostname, connect_ip)
            self.host, self.port = url.hostname, url.port or (443 if url.scheme == "https" else 80)
        except (TypeError, ValueError):
            raise ValueError("market endpoint requires numeric loopback HTTP or verified HTTPS with explicit numeric address") from None
        self.scheme, self.token, self.timeout = url.scheme, _token(token), _timeout(timeout)
        self.max_response_bytes = _integer(max_response_bytes, 1024, MAX_RESPONSE_BYTES)

    def _exchange(self, method, path, body, validate):
        deadline, maximum = time.monotonic() + self.timeout, self.max_response_bytes

        class Response(http.client.HTTPResponse):
            def __init__(self, connection, *args, **kwargs):
                super().__init__(connection, *args, **kwargs)
                try:
                    self.fp = _DeadlineReader(self.fp, connection, deadline, maximum + 32768)
                except BaseException:
                    # super 已取得文件引用；包装失败时由本对象释放，避免 traceback 延长连接寿命。
                    self.close()
                    raise

        connection = response = None
        try:
            # 默认信任材料初始化是同步本地工作；返回后检查预算，不声称可抢占OS初始化。
            context = ssl.create_default_context() if self.scheme == "https" else None
            connection = _DeadlineConnection(self.host, self.port, self._address, deadline, context)
            connection.response_class = Response
            connection.connect()
            connection.request(method, path, body=None if method == "GET" else body,
                headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json",
                         "Accept": "application/json", "Connection": "close"})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                raise MarketProtocolError("market redirect is forbidden")
            if response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise MarketProtocolError("market response must be JSON")
            length = response.getheader("Content-Length")
            if length is not None and (len(length) > 9 or not length.isascii()
                                       or not length.isdecimal() or int(length) > maximum):
                raise MarketProtocolError("market response exceeds its byte budget")
            blocks, count = [], 0
            while True:
                data = response.read1(min(65536, maximum + 1 - count))
                if not data:
                    break
                count += len(data)
                if count > maximum:
                    raise MarketProtocolError("market response exceeds its byte budget")
                blocks.append(data)
            if length is not None and count != int(length):
                raise MarketProtocolError("market response is truncated")
            value = validate(strict_json(b"".join(blocks)))
            if time.monotonic() >= deadline:
                raise TimeoutError("market response validation exceeded deadline")
            if response.status != 200:
                raise MarketHTTPError(response.status, value)
            return value
        except (OSError, http.client.HTTPException, TimeoutError):
            raise MarketUnavailable("market transport unavailable or deadline exceeded") from None
        finally:
            try:
                if response is not None:
                    response.close()
            finally:
                if connection is not None:
                    connection.close()


class MarketClient(_JSONTransport):
    """One bounded request per call; no redirects, proxy discovery or write retries."""

    def call(self, request):
        # Round-trip detaches caller mutations before validation and I/O.
        body = encode_json(request)
        if len(body) > MAX_REQUEST_BYTES:
            raise MarketProtocolError("market request exceeds its byte budget")
        request = validate_request(strict_json(body))
        method = "GET" if request["action"] == "capabilities" else "POST"
        return self._exchange(method, PATHS[request["action"]], body,
                              lambda value: validate_response(value, request))

    def capabilities(self):
        return self.call({"api_version": API_VERSION, "action": "capabilities"})

    def history_query(self, request):
        return self.call({"api_version": API_VERSION, "action": "history.query", "request": request})

    def source_history_query(self, request):
        """显式读取来源分钟原值；单位和时间标签随响应元数据返回。"""
        return self.call({"api_version": API_VERSION, "action": "history.source-query", "request": request})

    def source_daily_history_query(self, request):
        """读取原生源日线；返回交易日期及原单位，不授闭合/知晓时刻。"""
        return self.call({"api_version": API_VERSION, "action": "history.source-daily-query", "request": request})

    def source_daily_history_batch_query(self, request):
        """同一WT入口批读最多64证券；逐项保留原来源、价格口径、缺失及覆盖状态。"""
        return self.call(dict(api_version=API_VERSION,action='history.source-daily-batch-query',request=request))

    def source_market_snapshot_query(self, day, *, include_supplement=True):
        """默认读取完整落盘身份；显式False取得兼容旧消费者的独立合法投影。"""
        return self.call(dict(api_version=API_VERSION,action='market.source-snapshot-query',
            request=dict(date=day,include_supplement=include_supplement)))

    def source_security_query(self, request):
        """同版本读取证券资料、实际首尾和窗口内日期缺口；最多366自然日。"""
        return self.call(dict(api_version=API_VERSION,action='market.source-security-query',request=request))

    def source_day_facts_query(self, day, snapshot_id, *, include_stock_cross_section=False,
                               include_shsz_valuation=False, include_shsz_breadth=False):
        """读取同一WT版本的定日前收盘、成交股数、换手及交易状态。"""
        request = dict(date=day, snapshot_id=snapshot_id)
        if include_stock_cross_section is not False:
            request['include_stock_cross_section'] = include_stock_cross_section  # 显式读取同日横截面投影。
        if include_shsz_valuation is not False:
            request['include_shsz_valuation'] = include_shsz_valuation  # 显式读取 BaoStock 沪深估值投影。
        if include_shsz_breadth is not False:
            request['include_shsz_breadth'] = include_shsz_breadth  # 显式读取原沪深股票池基础统计。
        return self.call(dict(api_version=API_VERSION, action='market.source-day-facts-query', request=request))

    def source_supplement_query(self, request):
        """同快照分页读取ETF份额、融资报表和成交额事实/缺口；查询不触发补采。"""
        return self.call(dict(api_version=API_VERSION,action='market.source-supplement-query',request=request))

    def history_read(self, request):
        """一次有界读取及服务内补齐；请求结束不保留客户端需要释放的任务。"""
        return self.call({"api_version": API_VERSION, "action": "history.read", "request": request})

    def history_prepare(self, request):
        return self.call({"api_version": API_VERSION, "action": "history.prepare", "request": request})

    def history_work(self):
        return self.call({"api_version": API_VERSION, "action": "history.work"})

    def history_task_prepare(self, request):
        """显式准备临时任务；失败 data 可为空，返回身份仅在本次服务实例有效。"""
        return self.call({"api_version": API_VERSION, "action": "history.task.prepare", "request": request})

    def history_task_inspect(self, queue_id, task_id):
        """只读核查指定任务，校验响应仍属于传入实例与编号。"""
        return self.call({"api_version": API_VERSION, "action": "history.task.inspect",
                          "queue_id": queue_id, "task_id": task_id})

    def history_task_work(self, queue_id, task_id):
        """有界推进指定任务一次；超时后由作业 owner 核查，客户端不自动重试。"""
        return self.call({"api_version": API_VERSION, "action": "history.task.work",
                          "queue_id": queue_id, "task_id": task_id})

    def history_task_release(self, queue_id, task_id):
        """幂等释放指定实例的任务；已发布 DSB 由原生 Store 保留。"""
        return self.call({"api_version": API_VERSION, "action": "history.task.release",
                          "queue_id": queue_id, "task_id": task_id})

    def quotes_query(self, symbols):
        return self.call({"api_version": API_VERSION, "action": "quotes.query", "symbols": symbols})


def iter_history_windows(request, *, hours=72):
    """Yield bounded inclusive minute windows; never prepare, poll or retry them.

    A caller owns the job/checkpoint and explicitly performs query/prepare/work.
    The source permits at most 72 natural hours per window, including closures.
    """
    if type(hours) is not int or not 1 <= hours <= 72:
        raise ValueError("history windows must use 1..72 natural hours")
    copied = strict_json(encode_json(request))
    validate_request({"api_version": API_VERSION, "action": "history.prepare", "request": copied})
    current = datetime.strptime(str(copied["from"]), "%Y%m%d%H%M")
    end = datetime.strptime(str(copied["to"]), "%Y%m%d%H%M")
    while current <= end:
        stop = min(current + timedelta(hours=hours), end)
        lower, upper = int(current.strftime("%Y%m%d%H%M")), int(stop.strftime("%Y%m%d%H%M"))
        part = dict(copied, **{"from": lower, "to": upper})
        if "expected_minutes" in copied:
            part["expected_minutes"] = [m for m in copied["expected_minutes"] if lower <= m <= upper]
        yield part
        current = stop + timedelta(minutes=1)
