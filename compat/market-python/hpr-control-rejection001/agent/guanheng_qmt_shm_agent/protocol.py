# -*- coding: utf-8 -*-
"""Authenticated, bounded JSON messages over replaceable complete-byte streams.

Wire v1 belongs to this module. It is independent of HTTP, Win32 and Journal.
Request bodies travel as base64 bytes; this layer never rewrites business data.
"""
import hashlib
import hmac
import json
import math
import struct
from uuid import uuid4


class ProtocolError(ValueError):
    pass


class TransportBudget(object):
    """Required deployment budgets in seconds; no implicit retry or extension.

    connect_seconds is 0.1..60 for accept/open, io_seconds is 0.05..30 for
    handshake/idle exchange/result transfer. They do not replace operation
    queue/native budgets. Nonfinite, boolean or missing values fail startup.
    """
    def __init__(self, connect_seconds, io_seconds):
        for value, minimum, maximum in ((connect_seconds, 0.1, 60), (io_seconds, 0.05, 30)):
            if type(value) not in (float, int) or not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError("invalid transport timeout budget")
        self.connect_seconds, self.io_seconds = connect_seconds, io_seconds


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(unused):
    raise ProtocolError("nonfinite JSON value")


def _float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ProtocolError("nonfinite JSON value")
    return value


def _integer(text):
    # Broker-native 64-bit integers are representable; unbounded decimal input
    # must not consume the embedded interpreter while converting a huge int.
    if len(text.lstrip("-")) > 20:
        raise ProtocolError("integer exceeds 64-bit wire range")
    value = int(text)
    if not -(2 ** 63) <= value < 2 ** 64:
        raise ProtocolError("integer exceeds 64-bit wire range")
    return value


def decode(value):
    try:
        return json.loads(value.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_nonfinite, parse_float=_float, parse_int=_integer)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("invalid JSON message") from exc


def identity(value):
    """Control-owned route/executor/epoch; required, no implicit account remapping."""
    if not isinstance(value, dict) or set(value) != {"route_id", "executor_id", "route_epoch"}:
        raise ProtocolError("route identity shape is invalid")
    for key in ("route_id", "executor_id"):
        if not isinstance(value[key], str) or not 1 <= len(value[key]) <= 128:
            raise ProtocolError("route identity text is invalid")
    if type(value["route_epoch"]) is not int or not 0 <= value["route_epoch"] < 2 ** 53:
        raise ProtocolError("route epoch is invalid")
    return dict(value)


class Framer(object):
    """Four-byte network-order byte length, followed by exactly that many bytes.

    max_frame is trusted bootstrap's byte cap (1024..4194304, no default).
    deadline is an absolute monotonic deadline passed unchanged to all partial
    transfers. Invalid/oversized prefixes are rejected before allocating a body.
    """
    def __init__(self, stream, max_frame):
        if type(max_frame) is not int or not 1024 <= max_frame <= 4194304:
            raise ValueError("max_frame must be 1024..4194304 bytes")
        self.stream, self.max_frame = stream, max_frame

    def _read(self, size, deadline):
        result = bytearray()
        while len(result) < size:
            chunk = self.stream.read(size - len(result), deadline)
            if not chunk or len(chunk) > size - len(result):
                raise ProtocolError("incomplete or overflowing stream")
            result.extend(chunk)
        return bytes(result)

    def receive(self, deadline):
        size = struct.unpack("!I", self._read(4, deadline))[0]
        if not 1 <= size <= self.max_frame:
            raise ProtocolError("frame size exceeds configured boundary")
        return decode(self._read(size, deadline))

    def send(self, value, deadline):
        data = canonical(value)
        if not 1 <= len(data) <= self.max_frame:
            raise ProtocolError("frame size exceeds configured boundary")
        pending = struct.pack("!I", len(data)) + data
        while pending:
            written = self.stream.write(pending, deadline)
            if type(written) is not int or not 1 <= written <= len(pending):
                raise ProtocolError("invalid partial write")
            pending = pending[written:]

    def authenticated(self, generation):
        """Stream framing has no separate bootstrap resource to switch."""

    def close(self):
        self.stream.close()


def _mac(secret, value):
    return hmac.new(secret, canonical(value), hashlib.sha256).hexdigest()


def _signed(secret, value):
    return {"value": value, "mac": _mac(secret, value)}


def _verified(secret, envelope):
    if not isinstance(envelope, dict) or set(envelope) != {"value", "mac"}:
        raise ProtocolError("invalid authentication envelope")
    if not isinstance(envelope["mac"], str) or not hmac.compare_digest(
            envelope["mac"], _mac(secret, envelope["value"])):
        raise ProtocolError("authentication failed")
    if not isinstance(envelope["value"], dict):
        raise ProtocolError("message must be an object")
    return envelope["value"]


class Session(object):
    """One generation; sequence spaces and direction are independently bound.

    secret is injected bytes with at least 32 bytes of entropy, never peer data.
    profile contains authenticated pure-data read-operation policy, not code.
    Sessions are single-worker owned; any exception closes the worker binding.
    """
    def __init__(self, framer, secret, route, role, generation=None):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("bootstrap requires at least 32 secret bytes")
        if role not in ("host", "agent"):
            raise ValueError("invalid session role")
        self.framer, self._root = framer, secret
        self.route, self.role = identity(route), role
        if generation is not None:
            self._nonce(generation)
        self._pinned_generation = generation
        self.generation, self._key = None, None
        self._sent, self._received = 0, 0

    def _handshake_value(self, phase, host_nonce, agent_nonce):
        return {"version": 1, "phase": phase, "route": self.route,
                "generation": self.generation, "host_nonce": host_nonce,
                "agent_nonce": agent_nonce}

    def handshake_steps(self, profile=None):
        """One authentication state machine for blocking and callback drivers.

        Each yielded action uses the same caller-owned absolute deadline. A
        callback driver retains this generator while no complete frame exists;
        it never restarts a challenge, nonce or deadline when returning to QMT.
        """
        if self._key is not None:
            raise ProtocolError("session already authenticated")
        if self.role == "host":
            self.generation, host_nonce = self._pinned_generation or uuid4().hex, uuid4().hex
            hello = self._handshake_value("challenge", host_nonce, None)
            yield ("send", _signed(self._root, hello))
            reply = _verified(self._root, (yield ("receive", None)))
            agent_nonce = reply.get("agent_nonce")
            self._nonce(agent_nonce)
            if reply != self._handshake_value("response", host_nonce, agent_nonce):
                raise ProtocolError("challenge identity mismatch")
            ready = self._handshake_value("ready", host_nonce, agent_nonce)
            ready["profile"] = profile
            yield ("send", _signed(self._root, ready))
        else:
            hello = _verified(self._root, (yield ("receive", None)))
            self.generation, host_nonce = hello.get("generation"), hello.get("host_nonce")
            self._nonce(self.generation)
            self._nonce(host_nonce)
            if self._pinned_generation is not None and self.generation != self._pinned_generation:
                raise ProtocolError("challenge generation differs from its trusted transport")
            if hello != self._handshake_value("challenge", host_nonce, None):
                raise ProtocolError("challenge identity mismatch")
            agent_nonce = uuid4().hex
            yield ("send", _signed(self._root, self._handshake_value(
                "response", host_nonce, agent_nonce)))
            ready = _verified(self._root, (yield ("receive", None)))
            profile = ready.pop("profile", None)
            if ready != self._handshake_value("ready", host_nonce, agent_nonce):
                raise ProtocolError("host did not prove the fresh agent challenge")
        key = hmac.new(self._root, canonical(self._handshake_value(
            "session-key", host_nonce, agent_nonce)), hashlib.sha256).digest()
        self.framer.authenticated(self.generation)
        self._key = key
        return profile

    def handshake(self, deadline, profile=None):
        steps = self.handshake_steps(profile)
        action = next(steps)
        while True:
            operation, value = action
            received = (self.framer.send(value, deadline) if operation == "send"
                        else self.framer.receive(deadline))
            try:
                action = steps.send(received)
            except StopIteration as completed:
                return completed.value

    @staticmethod
    def _nonce(value):
        if not isinstance(value, str) or len(value) != 32 or any(
                char not in "0123456789abcdef" for char in value):
            raise ProtocolError("invalid challenge or generation")

    def outgoing(self, payload):
        """Encode the next original identity without publishing or advancing it."""
        if self._key is None:
            raise ProtocolError("session is not authenticated")
        return _signed(self._key, {"generation": self.generation, "role": self.role,
            "seq": self._sent + 1, "payload": payload})

    def send(self, payload, deadline):
        packet = self.outgoing(payload)
        self._sent += 1
        self.framer.send(packet, deadline)

    def incoming(self, envelope):
        """One verification/sequence transition shared by both execution modes."""
        if self._key is None:
            raise ProtocolError("session is not authenticated")
        value = _verified(self._key, envelope)
        expected_role = "agent" if self.role == "host" else "host"
        if (set(value) != {"generation", "role", "seq", "payload"}
                or value["generation"] != self.generation or value["role"] != expected_role
                or type(value["seq"]) is not int or value["seq"] != self._received + 1):
            raise ProtocolError("stale, replayed or out-of-order message")
        self._received += 1
        return value["payload"]

    def receive(self, deadline):
        if self._key is None:
            raise ProtocolError("session is not authenticated")
        return self.incoming(self.framer.receive(deadline))

    def close(self):
        self._key = None
        self.framer.close()
