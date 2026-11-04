"""Independent loopback-only market service backed by the versioned JSON C ABI.

The creating thread owns the server and native handle for their whole lifetime.
No QMT business package or source checkout is used by this service.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import os
from pathlib import Path
import re
import socket
import threading
import time

from ..guanheng_market_client import (
    API_VERSION, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, PATHS, MarketProtocolError,
    MarketUnavailable, _DeadlineReader, _integer, _object, _text, _timeout, _token,
    encode_json, strict_json, validate_request, validate_response,
)


def _failure(code, reason):
    return {"api_version": API_VERSION, "status": {"code": code, "reason": reason}, "data": {}}


class NativeMarket:
    """Copy each result before the ABI may invalidate it; enforce thread ownership."""

    def __init__(self, library, sha256, config, *, max_response_bytes=8 * 1024 * 1024):
        self._owner, self._handle, self._directory = threading.get_ident(), None, None
        self._maximum = _integer(max_response_bytes, 1024, MAX_RESPONSE_BYTES)
        try:
            library = Path(library).resolve(strict=True)
            if type(sha256) is not str or not re.fullmatch("[0-9a-f]{64}", sha256):
                raise ValueError
            digest = hashlib.sha256()
            with library.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if not hmac.compare_digest(digest.hexdigest(), sha256):
                raise ValueError
            encoded = encode_json(config)
            if len(encoded) > 65536:
                raise ValueError
            if os.name == "nt":
                self._directory = os.add_dll_directory(str(library.parent))
            self._native = ctypes.CDLL(str(library))
            self._native.gh_market_create.argtypes = [ctypes.c_char_p]
            self._native.gh_market_create.restype = ctypes.c_void_p
            self._native.gh_market_call.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            self._native.gh_market_call.restype = ctypes.c_char_p
            self._native.gh_market_destroy.argtypes = [ctypes.c_void_p]
            self._native.gh_market_destroy.restype = None
            self._handle = self._native.gh_market_create(encoded)
            if not self._handle:
                raise ValueError
        except (OSError, ValueError, AttributeError, TypeError):
            self.close()
            raise MarketUnavailable("native market dependency or startup configuration unavailable") from None

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise MarketUnavailable("native market handle belongs to another thread")

    def call(self, request):
        self._check_owner()
        if self._handle is None:
            raise MarketUnavailable("native market handle is closed")
        encoded = encode_json(request)
        if len(encoded) > MAX_REQUEST_BYTES:
            raise MarketProtocolError("market request exceeds its byte budget")
        request = validate_request(strict_json(encoded))
        # c_char_p copies the trusted, digest-pinned ABI's NUL-terminated output.
        # Its storage remains native-owned and must not be retained as a pointer.
        result = self._native.gh_market_call(self._handle, encoded)
        if result is None or len(result) > self._maximum:
            raise MarketProtocolError("native market response unavailable or exceeds its byte budget")
        return validate_response(strict_json(result), request)

    def close(self):
        self._check_owner()
        if self._handle is not None:
            self._native.gh_market_destroy(self._handle)
            self._handle = None
        if self._directory is not None:
            self._directory.close()
            self._directory = None


class _Handler(BaseHTTPRequestHandler):
    server_version, sys_version = "GuanhengMarket/1", ""
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.rfile = _DeadlineReader(self.rfile, self.connection,
            time.monotonic() + self.server.socket_timeout, self.server.max_request_bytes + 32768)

    def handle(self):
        self.request_version, self.command, self.requestline = "HTTP/1.1", None, ""
        try:
            super().handle()
        except (TimeoutError, socket.timeout):
            self._respond(408, _failure("Timeout", "market request read deadline expired"))
        except MarketProtocolError:
            self._respond(413, _failure("InvalidInput", "market request exceeds its read budget"))
        except (ConnectionError, OSError):
            self.close_connection = True

    def log_message(self, _format, *_args):
        # Request paths, headers and configuration never enter default access logs.
        return

    def send_error(self, code, message=None, explain=None):
        self._respond(code, _failure("InvalidInput", "market HTTP request is unsupported"))

    def handle_expect_100(self):
        self._respond(417, _failure("InvalidInput", "market Expect requests are unsupported"))
        return False

    def _respond(self, status, value, *, deadline=None):
        self.close_connection = True
        try:
            data = encode_json(value)
            if len(data) > self.server.max_response_bytes:
                status, data = 502, encode_json(_failure("Unavailable", "native market response exceeds its budget"))
            if deadline is not None:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    status,data=200,encode_json(_failure('Timeout','daily batch deadline expired'))
                else:
                    self.connection.settimeout(min(self.server.socket_timeout,remaining))
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
        except (ConnectionError, OSError):
            return

    def _dispatch_body(self):
        self.server._check_owner()
        batch_deadline = time.monotonic() + self.server.socket_timeout
        authorizations = self.headers.get_all("Authorization", [])
        expected = ("Bearer " + self.server.bearer_token).encode("ascii")
        if len(authorizations) != 1 or not hmac.compare_digest(authorizations[0].encode("utf-8"), expected):
            self._respond(401, _failure("InvalidInput", "market authentication required"))
            return
        action = next((a for a, path in PATHS.items() if self.path == path), None)
        if action is None:
            self._respond(404, _failure("NotSupported", "market path is unsupported"))
            return
        if (self.command == "GET") != (action == "capabilities"):
            self._respond(405, _failure("NotSupported", "market HTTP method is unsupported"))
            return
        if self.headers.get_all("Transfer-Encoding"):
            self._respond(400, _failure("InvalidInput", "market transfer encoding is unsupported"))
            return
        lengths = self.headers.get_all("Content-Length", [])
        if self.command == "GET":
            if lengths and lengths != ["0"]:
                self._respond(400, _failure("InvalidInput", "market capabilities request must be bodyless"))
                return
            request = {"api_version": API_VERSION, "action": action}
        else:
            if (len(lengths) != 1 or len(lengths[0]) > 9
                    or not lengths[0].isascii() or not lengths[0].isdecimal()):
                self._respond(411, _failure("InvalidInput", "market request requires one content length"))
                return
            length = int(lengths[0])
            if not 0 < length <= self.server.max_request_bytes:
                self._respond(413, _failure("InvalidInput", "market request body exceeds its budget"))
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                self._respond(415, _failure("InvalidInput", "market request must be JSON"))
                return
            data = self.rfile.read(length)
            if len(data) != length:
                self._respond(400, _failure("InvalidInput", "market request body is truncated"))
                return
            try:
                request = validate_request(strict_json(data))
                if request["action"] != action:
                    raise MarketProtocolError("market request action differs from its path")
            except MarketProtocolError:
                self._respond(400, _failure("InvalidInput", "market request fields or version are unsupported"))
                return
        try:
            if request['action'] == 'history.source-daily-batch-query':
                from .source_daily_batch import call_daily_batch
                reply = call_daily_batch(self.server.native,request,deadline=batch_deadline,
                    max_response_bytes=self.server.max_response_bytes)
            else:
                reply = self.server.native.call(request)
            result = validate_response(reply, request)
        except MarketProtocolError:
            self._respond(502, _failure("Unavailable", "native market response violates its contract"))
            return
        except Exception:
            self._respond(503, _failure("Unavailable", "native market dependency unavailable"))
            return
        self._respond(200, result,deadline=batch_deadline if request['action']=='history.source-daily-batch-query'else None)

    def _dispatch(self):
        try:
            self._dispatch_body()
        except (TimeoutError, socket.timeout):
            self._respond(408, _failure("Timeout", "market request read deadline expired"))
        except MarketProtocolError:
            self._respond(413, _failure("InvalidInput", "market request exceeds its read budget"))

    do_GET = do_POST = _dispatch


class MarketHTTPServer(HTTPServer):
    """Single-thread HTTP server; only shutdown() may be signalled by another thread."""

    allow_reuse_address = False

    def __init__(self, address, native, token, *, max_request_bytes=MAX_REQUEST_BYTES,
                 max_response_bytes=8 * 1024 * 1024, socket_timeout=5.0, owns_native=True):
        try:
            host = ipaddress.ip_address(address[0])
            if not host.is_loopback:
                raise ValueError
            _integer(address[1], 0, 65535)
        except (ValueError, TypeError, IndexError):
            raise ValueError("market server must bind a literal loopback address") from None
        self._owner, self.native = threading.get_ident(), native
        self._owns_native, self._closed = owns_native, False
        self.bearer_token, self.socket_timeout = _token(token), _timeout(socket_timeout)
        self.max_request_bytes = _integer(max_request_bytes, 1, MAX_REQUEST_BYTES)
        self.max_response_bytes = _integer(max_response_bytes, 1024, MAX_RESPONSE_BYTES)
        self.address_family = socket.AF_INET6 if host.version == 6 else socket.AF_INET
        super().__init__(address, _Handler)

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise MarketUnavailable("market HTTP server belongs to another thread")

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(self.socket_timeout)
        return connection, address

    def serve_forever(self, poll_interval=.1):
        self._check_owner()
        return super().serve_forever(poll_interval)

    def handle_request(self):
        self._check_owner()
        return super().handle_request()

    def server_close(self):
        self._check_owner()
        super().server_close()
        if not self._closed:
            self._closed = True
            if self._owns_native:
                self.native.close()


def from_env(address=("127.0.0.1", 8765), *, environ=None, **limits):
    """Build one owned server from explicit managed inputs; never discover QMT files.

    Config is a private, VCS-excluded JSON file. Authentication values may only
    come from environment injection and are never written back or logged.
    """
    values, native = os.environ if environ is None else environ, None
    try:
        token = _token(values["GH_MARKET_TOKEN"])
        path = Path(values["GH_MARKET_CONFIG_FILE"])
        with path.open("rb") as stream:
            data = stream.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError
        config = strict_json(data)
        if len(data) > 65536 and config.get("mode") not in ("source-stores", "source-catalog", "source-collected", "source-market-snapshot", "source-market-current"):
            raise ValueError
        # 原值文件服务显式选择独立适配器；普通线上配置继续沿原生Market ABI。
        if config.get("mode") in ("source-store", "source-stores", "source-catalog", "source-collected", "source-market-snapshot", "source-market-current"):
            from .source_market import create_native_source_market
            native = create_native_source_market(config,
                max_response_bytes=limits.get("max_response_bytes", 8 * 1024 * 1024))
            return MarketHTTPServer(address, native, token, **limits)
        _object(config, ("base_url", "history_root", "timeout_ms", "max_response_bytes", "profile", "native_reader"),
                ("base_url", "history_root", "profile"))
        # Reject credentials in the file rather than copying them into runtime state.
        config["key_id"] = _text(values["QMT_GATEWAY_KEY_ID"], limit=128)
        config["hmac_secret"] = _text(values["QMT_GATEWAY_HMAC_SECRET"], limit=4096)
        native = NativeMarket(Path(values["GH_MARKET_LIBRARY"]), values["GH_MARKET_LIBRARY_SHA256"], config,
                              max_response_bytes=limits.get("max_response_bytes", 8 * 1024 * 1024))
        return MarketHTTPServer(address, native, token, **limits)
    except Exception:
        if native is not None:
            native.close()
        raise MarketUnavailable("market service startup unavailable; verify managed library, config and environment") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        server = from_env((args.host, args.port))
    except (ValueError, MarketUnavailable):
        print("market service startup unavailable")
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
