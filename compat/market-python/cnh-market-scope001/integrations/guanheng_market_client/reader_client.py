"""Validated, thread-owned reads of the native WT history service.

tail/range return detached standard JSON envelopes, preserving status and source
evidence. The server owns calendar coverage and observation time; this client
owns no market files, business cursor or implicit retry.
"""
from datetime import datetime
import re
import threading
from uuid import uuid4

from . import (
    MAX_ROWS, STATUS_CODES, MarketProtocolError, MarketUnavailable,
    _JSONTransport, _integer, _metadata, _object, _prices, _text, encode_json,
)
from .reader_protocol import API_VERSION, HISTORY_PATH


def _minute(value):
    _integer(value, 199201010000, 209912312359)
    try:
        datetime.strptime(str(value), "%Y%m%d%H%M")
    except ValueError:
        raise MarketProtocolError("reader minute is invalid") from None
    return value


def _identity(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise MarketProtocolError("reader instance identity is invalid")
    return value


class ReaderClient(_JSONTransport):
    """Create, call and close on one thread; rebuild after server instance change."""

    def __init__(self, base_url, token, policy_id, *, timeout=5.0,
                 max_response_bytes=8 * 1024 * 1024, max_bars=MAX_ROWS, connect_ip=None):
        super().__init__(base_url, token, timeout=timeout, max_response_bytes=max_response_bytes,
                         connect_ip=connect_ip)
        self.policy_id = _text(policy_id, limit=128)
        if not policy_id.strip():
            raise ValueError("reader policy is required")
        self.max_bars = _integer(max_bars, 1, MAX_ROWS)
        self._owner, self._closed, self._instance = threading.get_ident(), False, None

    def _guard(self):
        if threading.get_ident() != self._owner:
            raise MarketUnavailable("reader client belongs to another thread")
        if self._closed:
            raise MarketUnavailable("reader client is closed")

    def close(self):
        if threading.get_ident() != self._owner:
            raise MarketUnavailable("reader client belongs to another thread")
        self._closed = True

    def tail(self, symbol, count, *, end=0):
        """Read exactly count authoritative minutes, ending at service time or end."""
        return self._read("tail", symbol, end, count)

    def range(self, symbol, after, *, end=0):
        """Read (after,end]; an empty range remains an explicitly validated result."""
        return self._read("range", symbol, end, after)

    def _read(self, action, symbol, end, bound):
        self._guard()
        if type(symbol) is not str or re.fullmatch(r"[0-9]{6}\.(SH|SZ)", symbol) is None:
            raise MarketProtocolError("reader symbol is invalid")
        _integer(end, 0, 209912312359)
        if end:
            _minute(end)
        _integer(bound, 1, self.max_bars) if action == "tail" else _minute(bound)
        request = dict(api_version=API_VERSION, id=uuid4().hex, action=action, symbol=symbol, end=end)
        request["count" if action == "tail" else "after"] = bound
        value = self._exchange("POST", HISTORY_PATH, encode_json(request),
                               lambda response: self._validate(response, request))
        # Only a fully validated, timely HTTP 200 Ok response can bind the client.
        if value["status"]["code"] == "Ok":
            self._instance = value["instance_id"]
        return value

    def _validate(self, value, request):
        try:
            return self._validated(value, request)
        except (KeyError, TypeError, ValueError, OverflowError):
            raise MarketProtocolError("reader response identity or data is invalid") from None

    def _validated(self, value, request):
        _object(value, ("api_version", "id", "instance_id", "policy_id", "status", "data"))
        instance = _identity(value["instance_id"])
        if (value["api_version"] != API_VERSION or value["id"] != request["id"]
                or value["policy_id"] != self.policy_id
                or (self._instance is not None and instance != self._instance)):
            raise MarketProtocolError("reader response identity changed")
        status, data = value["status"], value["data"]
        _object(status, ("code", "reason"))
        if type(status["code"]) is not str or status["code"] not in STATUS_CODES:
            raise MarketProtocolError("reader status is invalid")
        _text(status["reason"], empty=status["code"] == "Ok")
        if type(data) is not dict:
            raise MarketProtocolError("reader data is invalid")
        if status["code"] != "Ok":
            if data:
                raise MarketProtocolError("reader error contains data")
            return value
        _object(data, ("symbol", "as_of", "bars", "provenance"))
        as_of = _minute(data["as_of"])
        end = request["end"] or as_of
        if data["symbol"] != request["symbol"] or end > as_of:
            raise MarketProtocolError("reader observation identity is invalid")
        if request["action"] == "range" and request["after"] > as_of:
            raise MarketProtocolError("reader cursor exceeds observation time")
        bars, provenance = data["bars"], data["provenance"]
        if type(bars) is not list or len(bars) > self.max_bars or type(provenance) is not dict:
            raise MarketProtocolError("reader result exceeds budget")
        if request["action"] == "tail" and len(bars) != request["count"]:
            raise MarketProtocolError("reader tail is incomplete")
        if bars and not provenance:
            raise MarketProtocolError("reader source evidence is missing")
        for name, segments in provenance.items():
            _text(name, limit=128)
            if not name.strip() or type(segments) is not list or not segments:
                raise MarketProtocolError("reader source evidence is invalid")
            for segment in segments:
                _metadata(segment)
                if segment["adjustment"] != "none" or segment["factor_version"] != "":
                    raise MarketProtocolError("reader adjustment is unsupported")
        previous = 0
        for row in bars:
            _object(row, ("minute", "open", "high", "low", "close", "volume", "amount", "delivery"))
            minute = _minute(row["minute"])
            if not previous < minute <= end:
                raise MarketProtocolError("reader minutes are unordered or out of range")
            if request["action"] == "range" and minute <= request["after"]:
                raise MarketProtocolError("reader range includes its excluded cursor")
            expected = ("historical" if request["action"] == "tail" else
                        "current" if minute == as_of else "recovered")
            if row["delivery"] != expected:
                raise MarketProtocolError("reader delivery is invalid")
            _prices(row, "close", "volume", "amount")
            previous = minute
        return value
