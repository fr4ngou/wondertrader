# -*- coding: utf-8 -*-
"""HMAC request authentication with timestamp and nonce replay checks."""

from __future__ import print_function

import hashlib
import hmac
import math
import threading
import time
from datetime import datetime
try:
    from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit
except ImportError:  # pragma: no cover - Python 2 is not supported, kept harmless for QMT loaders.
    from urlparse import parse_qsl, urlsplit
    from urllib import quote, unquote, urlencode

from guanheng_qmt_shm_agent.errors import AuthenticationError, ReplayError


REQUIRED_HEADERS = (
    "X-QMT-Key-Id",
    "X-QMT-Timestamp",
    "X-QMT-Nonce",
    "X-QMT-Content-SHA256",
    "X-QMT-Signature",
)


def content_sha256(body):
    if body is None:
        body = b""
    if not isinstance(body, bytes):
        body = body.encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def canonical_target(uri):
    parts = urlsplit(uri)
    path = quote(unquote(parts.path or "/"), safe="/-._~")
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    pairs.sort(key=lambda item: (item[0], item[1]))
    query = urlencode(pairs, doseq=True)
    if query:
        return path + "?" + query
    return path


def canonical_request(method, uri, timestamp, nonce, body_sha256):
    return "\n".join(
        (method.upper(), canonical_target(uri), str(timestamp), str(nonce), body_sha256.lower())
    ).encode("utf-8")


def sign_request(secret, method, uri, timestamp, nonce, body_sha256):
    if not isinstance(secret, bytes):
        secret = secret.encode("utf-8")
    message = canonical_request(method, uri, timestamp, nonce, body_sha256)
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _timestamp_seconds(value):
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("timestamp must be finite")
        return result
    except (TypeError, ValueError):
        pass
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.strptime(text.replace("+00:00", "Z"), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise AuthenticationError("invalid_timestamp", "timestamp must be UTC epoch seconds or ISO-8601 Z")
    return (parsed - datetime(1970, 1, 1)).total_seconds()


class NonceCache(object):
    def __init__(self, ttl_seconds=60, max_entries=10000):
        self.ttl_seconds = float(ttl_seconds)
        self.max_entries = int(max_entries)
        self._entries = {}
        self._lock = threading.Lock()

    def consume(self, key_id, nonce, now):
        cache_key = (key_id, nonce)
        with self._lock:
            cutoff = now - self.ttl_seconds
            expired = [key for key, seen_at in self._entries.items() if seen_at < cutoff]
            for key in expired:
                self._entries.pop(key, None)
            if cache_key in self._entries:
                raise ReplayError()
            if len(self._entries) >= self.max_entries:
                raise AuthenticationError(
                    "nonce_cache_full", "nonce replay cache is full", 503
                )
            self._entries[cache_key] = now


class HMACVerifier(object):
    def __init__(self, key_resolver, max_clock_skew_seconds=30, nonce_cache=None, clock=None):
        if isinstance(key_resolver, dict):
            keys = dict(key_resolver)
            key_resolver = keys.get
        if not callable(key_resolver):
            raise TypeError("key_resolver must be callable or a mapping")
        self.key_resolver = key_resolver
        self.max_clock_skew_seconds = float(max_clock_skew_seconds)
        self.nonce_cache = nonce_cache or NonceCache(
            ttl_seconds=max(60, self.max_clock_skew_seconds * 2)
        )
        self.clock = clock or time.time

    def verify(self, method, uri, headers, body=b""):
        values = {}
        for name in REQUIRED_HEADERS:
            value = headers.get(name)
            if not value:
                raise AuthenticationError(
                    "missing_auth_header", "required authentication header is missing: {0}".format(name)
                )
            if len(value) > 512:
                raise AuthenticationError("invalid_auth_header", "authentication header is too long")
            values[name] = value

        if len(values["X-QMT-Nonce"]) > 128:
            raise AuthenticationError("invalid_nonce", "nonce is too long")
        if len(values["X-QMT-Key-Id"]) > 128:
            raise AuthenticationError("invalid_key_id", "key id is too long")
        for name in ("X-QMT-Content-SHA256", "X-QMT-Signature"):
            value = values[name].lower()
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise AuthenticationError("invalid_auth_header", "digest and signature must be SHA-256 hex")

        now = float(self.clock())
        signed_at = _timestamp_seconds(values["X-QMT-Timestamp"])
        if abs(now - signed_at) > self.max_clock_skew_seconds:
            raise AuthenticationError("timestamp_skew", "request timestamp is outside the allowed window")

        actual_digest = content_sha256(body)
        claimed_digest = values["X-QMT-Content-SHA256"].lower()
        if not hmac.compare_digest(actual_digest, claimed_digest):
            raise AuthenticationError("content_hash_mismatch", "request body digest does not match")

        key_id = values["X-QMT-Key-Id"]
        secret = self.key_resolver(key_id)
        if not secret:
            raise AuthenticationError("unknown_key", "unknown HMAC key id")
        expected = sign_request(
            secret,
            method,
            uri,
            values["X-QMT-Timestamp"],
            values["X-QMT-Nonce"],
            claimed_digest,
        )
        if not hmac.compare_digest(expected, values["X-QMT-Signature"].lower()):
            raise AuthenticationError("invalid_signature", "request signature is invalid")

        self.nonce_cache.consume(key_id, values["X-QMT-Nonce"], now)
        return key_id
