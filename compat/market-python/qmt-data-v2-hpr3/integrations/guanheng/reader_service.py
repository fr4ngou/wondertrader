"""独立只读历史服务：单线程拥有 StrategyMarket，供原生 reader 按次读取。"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timedelta
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib
import ipaddress
import math
import os
import re
import socket
import threading
import time
import uuid

from ..guanheng_market_client import (
    MAX_RESPONSE_BYTES, STATUS_CODES, MarketProtocolError, MarketUnavailable,
    _DeadlineReader, _integer, _metadata, _object, _prices, _text, _timeout,
    _token, encode_json, strict_json,
)
from ..guanheng_market_client.strategy_market import SHANGHAI, StrategyMarket


from ..guanheng_market_client.reader_protocol import API_VERSION, HISTORY_PATH
_NO_ID = "0" * 32
_QUALIFICATIONS = ("DevelopmentVerified", "NativeVerified", "ProductionQualified")
_REASONS = {code: "reader " + code.lower() for code in STATUS_CODES}
_REASONS["Ok"] = ""


def _minute(value):
    _integer(value, 199201010000, 209912312359)
    try:
        return datetime.strptime(str(value), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)
    except ValueError:
        raise MarketProtocolError("reader minute is invalid") from None


def _stamp(value):
    return int(value.strftime("%Y%m%d%H%M"))


def _budget(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 300:
        raise ValueError("reader time budget is invalid")
    return value


def _label(value, maximum=128):
    _text(value, limit=maximum)
    if not value.strip():
        raise MarketProtocolError("reader identity is empty")
    return value


def _request(value, as_of, max_bars):
    if type(value) is not dict or value.get("action") not in ("tail", "range"):
        raise MarketProtocolError("reader action is unsupported")
    action = value["action"]
    _object(value, ("api_version", "id", "action", "symbol", "end",
                    "count" if action == "tail" else "after"))
    if (value["api_version"] != API_VERSION or type(value["id"]) is not str
            or re.fullmatch("[0-9a-f]{32}", value["id"]) is None
            or type(value["symbol"]) is not str
            or re.fullmatch(r"[0-9]{6}\.(SH|SZ)", value["symbol"]) is None):
        raise MarketProtocolError("reader request identity is invalid")
    _integer(value["end"], 0, 209912312359)
    end = as_of if value["end"] == 0 else _minute(value["end"])
    if end > as_of:
        raise MarketProtocolError("reader end lies in the future")
    if action == "tail":
        _integer(value["count"], 1, max_bars)
        after = None
    else:
        after = _minute(value["after"])
        if after > as_of:
            raise MarketProtocolError("reader cursor lies in the future")
    return end, after


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.request_id = _NO_ID
        now = time.monotonic()
        self.deadline = now + self.server.request_timeout
        self.rfile = _DeadlineReader(self.rfile, self.connection,
            min(self.deadline, now + self.server.socket_timeout), self.server.max_request_bytes + 32768)

    def handle(self):
        self.request_version, self.command, self.requestline = "HTTP/1.1", None, ""
        try:
            super().handle()
        except (TimeoutError, socket.timeout):
            self._respond(408, "Timeout")
        except MarketProtocolError:
            self._respond(413, "InvalidInput")
        except OSError:
            self.close_connection = True
        except Exception:
            self._respond(503, "Unavailable")

    def log_message(self, *_args):
        pass

    def send_error(self, code, message=None, explain=None):
        self._respond(code, "InvalidInput")

    def handle_expect_100(self):
        self._respond(417, "InvalidInput")
        return False

    def _respond(self, http_status, code, data=None):
        self.close_connection = True
        try:
            payload = self.server.envelope(self.request_id, code, data)
            body = encode_json(payload)
            if len(body) > self.server.max_response_bytes:
                http_status, body = 502, encode_json(self.server.envelope(self.request_id, "Backpressure"))
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                # 截止后只允许一个短小固定失败响应，不把迟到的成功发布给调用者。
                http_status, body = 504, encode_json(self.server.envelope(self.request_id, "Timeout"))
                remaining = min(.1, self.server.socket_timeout)
            self.connection.settimeout(min(remaining, self.server.socket_timeout))
            self.send_response(http_status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (OSError, MarketProtocolError):
            pass

    def do_POST(self):
        self.server._check_owner()
        authorizations = self.headers.get_all("Authorization", [])
        expected = ("Bearer " + self.server.bearer_token).encode("ascii")
        if len(authorizations) != 1 or not hmac.compare_digest(authorizations[0].encode("utf-8"), expected):
            return self._respond(401, "InvalidInput")
        if self.path != HISTORY_PATH:
            return self._respond(404, "NotSupported")
        if self.headers.get_all("Transfer-Encoding"):
            return self._respond(400, "InvalidInput")
        lengths = self.headers.get_all("Content-Length", [])
        if (len(lengths) != 1 or len(lengths[0]) > 9
                or not lengths[0].isascii() or not lengths[0].isdecimal()):
            return self._respond(411, "InvalidInput")
        length = int(lengths[0])
        if not 0 < length <= self.server.max_request_bytes:
            return self._respond(413, "InvalidInput")
        content_types = self.headers.get_all("Content-Type", [])
        if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json":
            return self._respond(415, "InvalidInput")
        raw = self.rfile.read(length)
        if len(raw) != length:
            return self._respond(400, "InvalidInput")
        try:
            request = strict_json(raw)
            if (type(request) is dict and type(request.get("id")) is str
                    and re.fullmatch("[0-9a-f]{32}", request["id"])):
                self.request_id = request["id"]
            now = self.server.observation_time()
            end, after = _request(request, now, self.server.max_bars)
        except MarketProtocolError:
            return self._respond(400, "InvalidInput")
        try:
            code, data = self.server.history(request, now, end, after, self.deadline)
        except TimeoutError:
            return self._respond(504, "Timeout")
        except MarketProtocolError:
            return self._respond(502, "Unavailable")
        except Exception:
            return self._respond(503, "Unavailable")
        self._respond(200, code, data)


class ReaderHTTPServer(HTTPServer):
    """创建、serve、close 在同一拥有线程；其他线程仅可调用 shutdown。

    factory 是受管的零参构造器，返回当前线程创建的 StrategyMarket。market.clock
    是唯一观察时钟。request_timeout 包含读取、SDK 声明的总预算和输出校验；依赖须
    遵守 SDK 有界调用契约，服务不派生可继续执行的超时线程。响应超过容量整批拒绝。
    """

    allow_reuse_address = False

    def __init__(self, address, market_factory, token, policy_id, *, max_bars=10000,
                 max_request_bytes=4096, max_response_bytes=8 * 1024 * 1024,
                 socket_timeout=5, request_timeout=35):
        try:
            host = ipaddress.ip_address(address[0])
            if not host.is_loopback:
                raise ValueError
            _integer(address[1], 0, 65535)
        except (ValueError, TypeError, IndexError):
            raise ValueError("reader server requires a literal loopback address") from None
        self._owner, self._closed, self.market = threading.get_ident(), False, None
        self.bearer_token, self.policy_id = _token(token), _label(policy_id)
        self.instance_id = uuid.uuid4().hex
        self.max_bars = _integer(max_bars, 1, 10000)
        self.max_request_bytes = _integer(max_request_bytes, 1, 262144)
        self.max_response_bytes = _integer(max_response_bytes, 1024, MAX_RESPONSE_BYTES)
        self.socket_timeout, self.request_timeout = _timeout(socket_timeout), _budget(request_timeout)
        if self.socket_timeout > self.request_timeout or not callable(market_factory):
            raise ValueError("reader server budget or factory is invalid")
        self.address_family = socket.AF_INET6 if host.version == 6 else socket.AF_INET
        super().__init__(address, _Handler)
        try:
            self.market = market_factory()
            if (not isinstance(self.market, StrategyMarket) or self.market._owner != self._owner
                    or self.market._closed or not callable(getattr(self.market, "tail_history_1m", None))
                    or _budget(self.market.timeout) >= self.request_timeout):
                raise ValueError("reader factory must create an owned bounded StrategyMarket")
            self.max_bars = min(self.max_bars, self.market.max_bars)
            self._sources = {source.name: source for source in self.market.sources}
            self._minimum_qualification = self.market.minimum_qualification
        except Exception:
            self.server_close()
            raise MarketUnavailable("reader factory unavailable") from None

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise MarketUnavailable("reader service belongs to another thread")
        if self._closed:
            raise MarketUnavailable("reader service is closed")

    def observation_time(self):
        self._check_owner()
        value = self.market.clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise MarketUnavailable("reader clock unavailable")
        value = value.astimezone(SHANGHAI).replace(second=0, microsecond=0)
        _minute(_stamp(value))
        return value

    def envelope(self, request_id, code, data=None):
        return {"api_version": API_VERSION, "id": request_id, "instance_id": self.instance_id,
                "policy_id": self.policy_id, "status": {"code": code, "reason": _REASONS[code]},
                "data": data if code == "Ok" and data is not None else {}}

    def _provenance(self, value):
        if not isinstance(value, Mapping) or len(value) > len(self._sources):
            raise MarketProtocolError("reader provenance is invalid")
        output, segments = {}, 0
        for name, versions in value.items():
            if name not in self._sources or type(versions) is not tuple or not versions:
                raise MarketProtocolError("reader provenance source is invalid")
            segments += len(versions)
            if segments > self.max_response_bytes // 256:
                raise MarketProtocolError("reader provenance exceeds its budget")
            source = self._sources[name]
            output[name] = []
            for metadata in versions:
                if not isinstance(metadata, Mapping) or not isinstance(metadata.get("source"), Mapping):
                    raise MarketProtocolError("reader provenance segment is invalid")
                # SDK 元数据是只读视图；仅解除容器冻结，单位和资格证据保持原值。
                plain = dict(metadata, source=dict(metadata["source"]))
                _metadata(plain)
                if (plain["dataset_version"] != source.dataset_version or plain["source"]["provider"] != source.provider
                        or plain["adjustment"] != "none" or plain["factor_version"] != ""
                        or _QUALIFICATIONS.index(plain["qualification"]) < _QUALIFICATIONS.index(self._minimum_qualification)):
                    raise MarketProtocolError("reader provenance differs from its managed policy")
                output[name].append(plain)
        return output

    def history(self, request, now, end, after, deadline):
        self._check_owner()
        if self.market.timeout > deadline - time.monotonic():
            raise TimeoutError("reader call has insufficient budget")
        if after is not None and after >= end:
            return "Ok", {"symbol": request["symbol"], "as_of": _stamp(now), "bars": [], "provenance": {}}
        if request["action"] == "tail":
            result = self.market.tail_history_1m(request["symbol"], request["count"], end=end, as_of=now)
        else:
            result = self.market.history_1m(request["symbol"], after + timedelta(minutes=1), end, as_of=now)
        if time.monotonic() >= deadline:
            raise TimeoutError("reader call exceeded its budget")
        code, bars = getattr(result, "status", None), getattr(result, "bars", None)
        if type(code) is not str or code not in STATUS_CODES or type(bars) is not tuple:
            raise MarketProtocolError("reader SDK status is invalid")
        if code != "Ok":
            if bars:
                raise MarketProtocolError("reader SDK error contains partial bars")
            return code, {}
        if (len(bars) > self.max_bars or (request["action"] == "tail" and len(bars) != request["count"])
                or getattr(result, "missing_minutes", None) != ()
                or getattr(result, "calendar_version", None) != self.market.calendar_version):
            raise MarketProtocolError("reader SDK coverage is invalid")
        provenance = self._provenance(getattr(result, "provenance", None))
        output, previous = [], 0
        for bar in bars:
            minute = getattr(bar, "minute", None)
            right = _minute(minute)
            if (bar.symbol != request["symbol"] or minute <= previous or right > end
                    or (after is not None and right <= after) or bar.source_name not in provenance
                    or bar.delivery != "historical"):
                raise MarketProtocolError("reader SDK bar identity is invalid")
            row = {name: getattr(bar, name, None) for name in ("open", "high", "low", "close", "volume", "amount")}
            _prices(row, "close", "volume", "amount")
            delivery = "historical" if after is None else "current" if right == now else "recovered"
            output.append(dict(minute=minute, **row, delivery=delivery))
            previous = minute
        return "Ok", {"symbol": request["symbol"], "as_of": _stamp(now), "bars": output, "provenance": provenance}

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(self.socket_timeout)
        return connection, address

    def handle_error(self, request, client_address):
        # HTTPServer 默认输出异常和客户端详情；托管服务只暴露固定 wire 错误。
        pass

    def serve_forever(self, poll_interval=.1):
        self._check_owner()
        return super().serve_forever(poll_interval)

    def handle_request(self):
        self._check_owner()
        return super().handle_request()

    def server_close(self):
        if threading.get_ident() != self._owner:
            raise MarketUnavailable("reader service belongs to another thread")
        super().server_close()
        if not self._closed:
            self._closed = True
            if isinstance(self.market, StrategyMarket) and self.market._owner == self._owner:
                self.market.close()


def from_env(address=("127.0.0.1", 8766), *, environ=None, **limits):
    """仅由受管启动环境授权 module:callable 导入；工厂自行读取来源/日历配置。"""
    values = os.environ if environ is None else environ
    try:
        token, policy = _token(values["GH_READER_TOKEN"]), _label(values["GH_READER_POLICY_ID"])
        target = values["GH_READER_FACTORY"]
        if type(target) is not str or re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", target) is None:
            raise ValueError("reader factory identity is invalid")
        module_name, function_name = target.split(":")
        # import 及 factory 调用都发生在随后拥有 SDK 的服务器线程。
        def factory():
            return getattr(importlib.import_module(module_name), function_name)()
        return ReaderHTTPServer(address, factory, token, policy, **limits)
    except Exception:
        raise MarketUnavailable("reader service startup unavailable; verify managed environment") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    try:
        server = from_env((args.host, args.port))
    except (ValueError, MarketUnavailable):
        print("reader service startup unavailable")
        return 1
    try:
        print("{0} listening on loopback port {1}".format(API_VERSION, server.server_port), flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
