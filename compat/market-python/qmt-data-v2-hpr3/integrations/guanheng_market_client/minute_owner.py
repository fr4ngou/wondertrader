"""MarketData分钟接纳公开契约；同步、有界HTTP，不拥有持久消费状态。"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
import hashlib
import http.client
import io
import re
import ssl
import time
from uuid import UUID
from urllib.parse import urlsplit

from . import _metadata, _prices, encode_json, strict_json
from .history_runner import OperationsClient, _DeadlineRaw, canonical_bytes
from .strategy_market import SHANGHAI, _text

MAX_BYTES = 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}")
_STREAM = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_CHECKPOINT = {"schema_version", "stream_id", "policy_sha256", "symbol", "feature_version", "calendar_version",
               "bootstrap_after", "live_after", "committed_after", "revision", "phase", "last_batch_id", "max_batch_minutes"}
_RECEIPT = {"schema_version", "status", "stream_id", "policy_sha256", "batch_id", "request_sha256",
            "previous_after", "committed_after", "revision", "stored_count", "current_enqueued_count",
            "feature_event_ids", "accepted_at"}
_REQUEST = {"schema_version", "policy_sha256", "expected_revision", "after", "through", "calendar_version",
            "mode", "batch_id", "request_sha256", "bars", "provenance"}
_BAR = {"symbol", "minute", "open", "high", "low", "close", "volume", "amount", "source_name", "delivery"}


class MinuteOwnerUnavailable(OSError):
    def __init__(self):
        super().__init__("minute owner unavailable")


class MinuteOwnerConflict(ValueError):
    def __init__(self):
        super().__init__("minute owner conflict")


class MinuteOwnerProtocolError(ValueError):
    def __init__(self):
        super().__init__("minute owner protocol invalid")


class MinuteOwnerRejected(ValueError):
    def __init__(self):
        super().__init__("minute owner request rejected")


def stream_identity(value):
    if type(value) is not str or _STREAM.fullmatch(value) is None:
        raise ValueError("minute stream identity invalid")
    return value


def sha_identity(value):
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise ValueError("minute content identity invalid")
    return value


def minute_time(value):
    if type(value) is not int or not 199201010000 <= value <= 209912312359:
        raise ValueError("minute time invalid")
    return datetime.strptime(str(value), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)


def _integer(value, minimum=0, maximum=2**63-1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError


def _fields(value, fields):
    if type(value) is not dict or value.keys() != fields:
        raise ValueError


def _calendar(value):
    if type(value) is not str or re.fullmatch(r"cal-min1-v1-[0-9a-f]{64}", value) is None:
        raise ValueError


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return [_plain(item) for item in value]
    return value


def _checkpoint(value):
    _fields(value, _CHECKPOINT)
    if value["schema_version"] != "guanheng.minute.checkpoint.v1":
        raise ValueError
    stream_identity(value["stream_id"])
    sha_identity(value["policy_sha256"])
    if type(value["symbol"]) is not str or re.fullmatch(r"[0-9]{6}\.(SH|SZ)", value["symbol"]) is None:
        raise ValueError
    for key in ("feature_version", "calendar_version"):
        _text(value[key], 128 if key == "calendar_version" else 256)
    _calendar(value["calendar_version"])
    lower, live, after = (minute_time(value[key]) for key in ("bootstrap_after", "live_after", "committed_after"))
    if lower > live or after < lower:
        raise ValueError
    _integer(value["revision"])
    _integer(value["max_batch_minutes"], 1, 1440)
    if value["phase"] != ("warmup" if after < live else "subscription"):
        raise ValueError
    if value["revision"] == 0:
        if value["last_batch_id"] != "" or after != lower:
            raise ValueError
    else:
        sha_identity(value["last_batch_id"])
    return value


def validate_checkpoint(value):
    try:
        return _checkpoint(strict_json(encode_json(value)))
    except Exception:
        pass
    raise MinuteOwnerProtocolError()


def validate_receipt(value):
    try:
        value = strict_json(encode_json(value))
        _fields(value, _RECEIPT)
        if value["schema_version"] != "guanheng.minute.receipt.v1" or value["status"] != "Committed":
            raise ValueError
        stream_identity(value["stream_id"])
        for key in ("policy_sha256", "batch_id", "request_sha256"):
            sha_identity(value[key])
        if minute_time(value["previous_after"]) >= minute_time(value["committed_after"]):
            raise ValueError
        _integer(value["revision"], 1)
        _integer(value["stored_count"], 0, 512)
        _integer(value["current_enqueued_count"], 0, min(1, value["stored_count"]))
        if (type(value["feature_event_ids"]) is not list
                or len(value["feature_event_ids"]) != value["current_enqueued_count"]):
            raise ValueError
        for item in value["feature_event_ids"]:
            if type(item) is not str or str(UUID(item)) != item:
                raise ValueError
        stamp = value["accepted_at"]
        if type(stamp) is not str or len(stamp) > 64:
            raise ValueError
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if parsed.utcoffset() != timedelta(0):
            raise ValueError
        return value
    except Exception:
        pass
    raise MinuteOwnerProtocolError()


def _normalize_request(value):
    value = strict_json(encode_json(_plain(value)))
    _fields(value, _REQUEST)
    if value["schema_version"] != "guanheng.minute.batch.v1":
        raise ValueError
    for key in ("policy_sha256", "batch_id", "request_sha256"):
        sha_identity(value[key])
    _integer(value["expected_revision"])
    lower, upper = minute_time(value["after"]), minute_time(value["through"])
    if not timedelta(0) < upper - lower <= timedelta(minutes=1440):
        raise ValueError
    _calendar(value["calendar_version"])
    if value["mode"] not in ("warmup", "subscription"):
        raise ValueError
    provenance = value["provenance"]
    if type(provenance) is not dict or len(provenance) > 16:
        raise ValueError
    for name, segments in provenance.items():
        _text(name, 128)
        if type(segments) is not list or not 1 <= len(segments) <= 128:
            raise ValueError
        for segment in segments:
            _metadata(segment)
            if segment["adjustment"] != "none" or segment["factor_version"] != "":
                raise ValueError
            for field in ("volume_to_shares", "amount_to_yuan"):
                segment[field] = float(segment[field])
    bars = value["bars"]
    if type(bars) is not list or len(bars) > 512:
        raise ValueError
    previous, symbol, currents = value["after"], None, 0
    for row in bars:
        _fields(row, _BAR)
        minute_time(row["minute"])
        if not previous < row["minute"] <= value["through"]:
            raise ValueError
        if type(row["symbol"]) is not str or re.fullmatch(r"[0-9]{6}\.(SH|SZ)", row["symbol"]) is None:
            raise ValueError
        if symbol is not None and row["symbol"] != symbol:
            raise ValueError
        if row["source_name"] not in provenance:
            raise ValueError
        allowed = ("historical",) if value["mode"] == "warmup" else ("current", "recovered")
        if row["delivery"] not in allowed:
            raise ValueError
        if row["delivery"] == "current":
            currents += 1
            if row["minute"] != value["through"] or currents > 1:
                raise ValueError
        _prices(row, "close", "volume", "amount")
        for field in ("open", "high", "low", "close", "volume", "amount"):
            row[field] = float(row[field])
        previous, symbol = row["minute"], row["symbol"]
    if len(canonical_bytes(value)) > MAX_BYTES:
        raise ValueError
    return value


def request_digest(value):
    """与owner共享规范：价格/量额/来源系数转float，排除摘要字段本身。"""
    normalized = _normalize_request(value)
    normalized.pop("request_sha256")
    return hashlib.sha256(canonical_bytes(normalized)).hexdigest()


def admission_request(checkpoint, batch):
    """保留SDK批身份；预热投递仅改HTTP副本，不改变待ACK批次。"""
    try:
        cp = validate_checkpoint(checkpoint)
        if (batch.status != "Ok" or batch.delivery != "closed-source-poll" or batch.after != cp["committed_after"]
                or batch.calendar_version != cp["calendar_version"]):
            raise ValueError
        bars = [{name: getattr(row, name) for name in _BAR} for row in batch.bars]
        if any(row["symbol"] != cp["symbol"] for row in bars):
            raise ValueError
        if cp["phase"] == "warmup":
            if batch.through > cp["live_after"]:
                raise ValueError
            for row in bars:
                row["delivery"] = "historical"
        value = dict(schema_version="guanheng.minute.batch.v1", policy_sha256=cp["policy_sha256"],
            expected_revision=cp["revision"], after=batch.after, through=batch.through,
            calendar_version=batch.calendar_version, mode=cp["phase"], batch_id=batch.batch_id,
            request_sha256="0" * 64, bars=bars, provenance=_plain(batch.provenance))
        normalized = _normalize_request(value)
        normalized["request_sha256"] = request_digest(normalized)
        return normalized
    except Exception:
        pass
    raise MinuteOwnerProtocolError()


def confirm_receipt(value, stream, request):
    receipt = validate_receipt(value)
    expected = dict(stream_id=stream, policy_sha256=request["policy_sha256"], batch_id=request["batch_id"],
        request_sha256=request["request_sha256"], previous_after=request["after"],
        committed_after=request["through"], revision=request["expected_revision"]+1, stored_count=len(request["bars"]))
    if any(receipt[key] != item for key, item in expected.items()):
        raise MinuteOwnerProtocolError()
    if receipt["current_enqueued_count"] > sum(row["delivery"] == "current" for row in request["bars"]):
        raise MinuteOwnerProtocolError()
    return receipt


class MinuteOwnerClient:
    """单次HTTP交换，不重试POST；未知接纳结果由worker按原身份回查。"""
    def __init__(self, base_url, token, *, timeout=5):
        try:
            if (type(base_url) is not str or not 1 <= len(base_url) <= 2048
                    or any(not 33 <= ord(c) <= 126 for c in base_url) or "\\" in base_url):
                raise ValueError
            port = urlsplit(base_url).port
            if port is not None and not 1 <= port <= 65535:
                raise ValueError
            # 复用既有端点、凭据和有限时间准入；deadline reader同源共用。
            transport = OperationsClient(base_url, token, timeout=timeout, max_response_bytes=MAX_BYTES)
            if type(token) is not str or any(not 33 <= ord(c) <= 126 for c in token):
                raise ValueError
            self.host, self.port, self.scheme = transport.host, transport.port, transport.scheme
            self.token, self.timeout = transport.token, transport.timeout
            return
        except Exception:
            pass
        raise MinuteOwnerProtocolError()

    def _exchange(self, method, path, payload=None, *, absent=False):
        body = None if payload is None else canonical_bytes(payload)
        if body is not None and len(body) > MAX_BYTES:
            raise MinuteOwnerProtocolError()
        deadline = time.monotonic() + self.timeout
        class Response(http.client.HTTPResponse):
            def __init__(self, sock, *args, **kwargs):
                super().__init__(sock, *args, **kwargs)
                self.fp = io.BufferedReader(_DeadlineRaw(self.fp, sock, deadline))
        connection, response = None, None
        error = None
        try:
            connection = (http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout, context=ssl.create_default_context())
                if self.scheme == "https" else http.client.HTTPConnection(self.host, self.port, timeout=self.timeout))
            connection.response_class = Response
            connection.connect()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            connection.sock.settimeout(remaining)
            connection.request(method, path, body=body, headers={"X-Internal-Token": self.token,
                "Content-Type": "application/json", "Accept": "application/json", "Connection": "close"})
            response = connection.getresponse()
            if response.status == 404 and absent:
                return None
            if response.status == 409:
                raise MinuteOwnerConflict()
            if response.status in (400, 401, 403, 404, 422):
                raise MinuteOwnerRejected()
            if response.status != 200:
                raise MinuteOwnerUnavailable()
            if response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise MinuteOwnerProtocolError()
            length = response.getheader("Content-Length")
            if length is not None and (len(length) > 9 or not length.isascii() or not length.isdecimal() or int(length) > MAX_BYTES):
                raise MinuteOwnerProtocolError()
            chunks, count = [], 0
            while True:
                chunk = response.read1(min(65536, MAX_BYTES + 1 - count))
                if not chunk:
                    break
                chunks.append(chunk)
                count += len(chunk)
                if count > MAX_BYTES:
                    raise MinuteOwnerProtocolError()
            if length is not None and count != int(length):
                raise MinuteOwnerProtocolError()
            if time.monotonic() >= deadline:
                raise TimeoutError
            return strict_json(b"".join(chunks))
        except (MinuteOwnerConflict, MinuteOwnerRejected, MinuteOwnerProtocolError, MinuteOwnerUnavailable) as exc:
            error = type(exc)
        except (OSError, http.client.HTTPException, TimeoutError):
            error = MinuteOwnerUnavailable
        except Exception:
            error = MinuteOwnerProtocolError
        finally:
            try:
                if response is not None:
                    response.close()
            except Exception:
                pass
            try:
                if connection is not None:
                    connection.close()
            except Exception:
                pass
        raise error()

    def checkpoint(self, stream):
        stream = stream_identity(stream)
        result = validate_checkpoint(self._exchange("GET", "/v1/market/minute-streams/" + stream + "/checkpoint"))
        if result["stream_id"] != stream:
            raise MinuteOwnerProtocolError()
        return result

    def submit(self, stream, request):
        stream = stream_identity(stream)
        try:
            payload = _normalize_request(request)
            if request_digest(payload) != payload["request_sha256"]:
                raise ValueError
        except Exception:
            raise MinuteOwnerProtocolError() from None
        return confirm_receipt(self._exchange("POST", "/v1/market/minute-streams/" + stream + "/batches", payload), stream, payload)

    def receipt(self, stream, batch):
        stream, batch = stream_identity(stream), sha_identity(batch)
        result = self._exchange("GET", "/v1/market/minute-streams/" + stream + "/batches/" + batch, absent=True)
        if result is None:
            return None
        result = validate_receipt(result)
        if result["stream_id"] != stream or result["batch_id"] != batch:
            raise MinuteOwnerProtocolError()
        return result
