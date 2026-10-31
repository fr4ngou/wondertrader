# -*- coding: utf-8 -*-
"""Pure SHM profile and authenticated frame codec; no OS, file or SDK I/O."""
import base64
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import math
import re
import struct
import time
from uuid import UUID, uuid4

from .timestamps import source_timestamp
from .protocol import ProtocolError, canonical, decode, identity
from . import shm_wire as wire


FRAME_KEY_DOMAIN = b"qmt-shm-frame-key-v1\x00"
BODY_FIELDS = frozenset(("kind", "ring_id", "direction", "contract_version", "request_id", "attempt_id",
    "correlation_id", "identity", "capability_sha256", "key_id", "issued_at", "expires_at", "payload"))


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid SHM " + name)
    return value


def generation_bytes(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ProtocolError("invalid SHM generation")
    return UUID(hex=value).bytes


def slot_bytes(packet_max):
    return wire.SLOT_SIZE + wire.FRAME_SIZE + wire.ENVELOPE_RESERVE_BYTES + 4 * ((packet_max + 2) // 3)


class SharedMemoryProfile(object):
    """Freeze trusted capacity/identity once, before creating kernel objects."""
    def __init__(self, config, route, max_frame, business_profile):
        required = {"kind", "name", "key_id", "windows_session_id", "slot_counts", "control_packet_max_bytes",
            "max_mapped_bytes", "max_recent_frames", "poll_seconds"}
        if not isinstance(config, dict) or set(config) != required or config["kind"] != "shm":
            raise ValueError("SHM profile has missing or unknown fields")
        if (not isinstance(config["name"], str) or len(config["name"]) > wire.LIMITS["max_name_bytes"]
                or not re.fullmatch(r"qmt-broker-[A-Za-z0-9_-]+", config["name"])):
            raise ValueError("invalid private SHM object name")
        if (not isinstance(config["key_id"], str) or len(config["key_id"]) > wire.LIMITS["max_key_id_bytes"]
                or not re.fullmatch(r"[A-Za-z0-9_.:-]+", config["key_id"])):
            raise ValueError("invalid trusted SHM key identifier")
        self._route = canonical(identity(route))
        self.max_frame = integer(max_frame, 1, wire.LIMITS["max_packet_bytes"], "packet budget")
        self.session_id = integer(config["windows_session_id"], 0, 4294967295, "Windows session")
        counts = config["slot_counts"]
        if not isinstance(counts, dict) or set(counts) != {"command", "reliable", "quote"}:
            raise ValueError("invalid SHM ring counts")
        counts = {key: integer(value, 1, wire.LIMITS["quote_slot_count"] if key == "quote" else wire.LIMITS["max_slot_count"], "slot count")
            for key, value in counts.items()}
        self.control_max = integer(config["control_packet_max_bytes"], wire.LIMITS["min_control_packet_bytes"],
            wire.LIMITS["max_control_packet_bytes"], "control packet budget")
        if len(canonical(business_profile)) + wire.HANDSHAKE_OVERHEAD_BYTES > self.control_max:
            raise ValueError("control packet budget cannot contain the trusted handshake profile")
        self.max_recent = integer(config["max_recent_frames"], 1, wire.LIMITS["max_recent_frames"], "nonce cache budget")
        maximum = integer(config["max_mapped_bytes"], 1, wire.LIMITS["max_mapped_bytes"], "mapping budget")
        poll = config["poll_seconds"]
        if (type(poll) not in (int, float) or not math.isfinite(poll)
                or not wire.LIMITS["min_poll_seconds"] <= poll <= wire.LIMITS["max_poll_seconds"]):
            raise ValueError("invalid SHM event polling budget")
        self.slot_bytes, self.control_slot_bytes = slot_bytes(max_frame), slot_bytes(self.control_max)
        self.control_unit_bytes = wire.RING_SIZE + self.control_slot_bytes
        self.mapped_bytes = 2 * self.control_unit_bytes + sum(wire.RING_SIZE + n * self.slot_bytes for n in counts.values())
        if self.mapped_bytes > maximum:
            raise ValueError("SHM mapping budget cannot contain all complete rings")
        self.poll_seconds, self.key_id = float(poll), config["key_id"]
        self.capability_hash = hashlib.sha256(canonical(business_profile)).hexdigest()
        self.route_hash = hashlib.sha256(self._route).digest()
        self.base_name = "Local\\" + config["name"] + "-" + self.route_hash.hex()[:16]
        # The canonical profile includes derived layout and all admission limits.
        # Peer data can neither enlarge it nor mutate the caller's chosen owner.
        self._profile = canonical(dict(config, slot_counts=counts, max_frame=max_frame,
            slot_bytes=self.slot_bytes, control_slot_bytes=self.control_slot_bytes,
            mapped_bytes=self.mapped_bytes, definition_sha256=wire.SOURCE_SHA256,
            capability_sha256=self.capability_hash, route=self.route, poll_seconds=float(poll)))
        self.profile_hash = hashlib.sha256(self._profile).digest()

    @property
    def route(self):
        return decode(self._route)

    def layout(self, name, direction):
        if name not in wire.RINGS or direction not in wire.DIRECTIONS:
            raise ValueError("unknown SHM ring/direction")
        if (name == "command" and direction != "host_to_agent"
                or name in ("reliable", "quote") and direction != "agent_to_host"):
            raise ValueError("SHM ring has the wrong direction")
        control = name == "control"
        count = wire.LIMITS["control_slot_count"] if control else decode(self._profile)["slot_counts"][name]
        width = self.control_slot_bytes if control else self.slot_bytes
        return {"ring_id": wire.RINGS[name], "direction": wire.DIRECTIONS[direction],
            "slot_count": count, "slot_bytes": width, "mapped_bytes": wire.RING_SIZE + count * width}


class FrameCodec(object):
    """Validate private frames after copying them out of shared memory locks."""
    def __init__(self, profile, generation, secret, clock=None):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("SHM requires trusted private IPC credentials")
        self.profile, self.generation = profile, generation
        self._generation_bytes, self._secret = generation_bytes(generation), secret
        self._seen = OrderedDict()
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def _key(self, layout):
        if self._secret is None:
            raise ProtocolError("SHM codec is closed")
        context = canonical({"generation": self.generation, "ring_id": layout["ring_id"],
            "direction": layout["direction"], "route_sha256": self.profile.route_hash.hex(),
            "profile_sha256": self.profile.profile_hash.hex(), "key_id": self.profile.key_id})
        return hmac.new(self._secret, FRAME_KEY_DOMAIN + context, hashlib.sha256).digest()

    @staticmethod
    def _kind(kind, name, direction):
        valid = {"control": {"HELLO", "HELLO_ACK", "PING", "PONG", "ERROR", "DRAIN"},
            "command": {"REQUEST"}, "reliable": {"RESULT"}, "quote": {"QUOTE"}}
        if not isinstance(kind, str) or kind not in valid[name] or direction not in wire.DIRECTIONS:
            raise ProtocolError("SHM message kind is not allowed on this ring")

    def encode(self, packet, name, direction, sequence, kind, deadline):
        layout = self.profile.layout(name, direction)
        self._kind(kind, name, direction)
        integer(sequence, 1, wire.LIMITS["max_sequence"], "frame sequence")
        cap = self.profile.control_max if name == "control" else self.profile.max_frame
        if not isinstance(packet, bytes) or not 1 <= len(packet) <= cap:
            raise ProtocolError("SHM Session packet exceeds its unchanged byte budget")
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError("invalid monotonic frame deadline")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("SHM frame deadline elapsed")
        now, message = self._clock(), uuid4()
        try:
            expires = now + timedelta(seconds=remaining)
        except (OverflowError, ValueError) as exc:
            raise ProtocolError("SHM frame deadline cannot be represented") from exc
        body = canonical({"kind": kind, "ring_id": layout["ring_id"], "direction": layout["direction"],
            "contract_version": wire.CONTRACT_VERSION, "request_id": str(message), "attempt_id": str(message),
            "correlation_id": None, "identity": self.profile.route, "capability_sha256": self.profile.capability_hash,
            "key_id": self.profile.key_id, "issued_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "payload": base64.b64encode(packet).decode("ascii")})
        if wire.SLOT_SIZE + wire.FRAME_SIZE + len(body) > layout["slot_bytes"]:
            raise ProtocolError("SHM frame exceeds its fixed slot")
        header = struct.pack(wire.FRAME_FORMAT, wire.FRAME_MAGIC, wire.VERSION[0], wire.VERSION[1],
            wire.FRAME_SIZE, 0, len(body), 0, self._generation_bytes, message.bytes, sequence,
            hashlib.sha256(body).digest(), b"\0" * 32)
        mac = hmac.new(self._key(layout), header[:wire.FRAME_MAC_OFFSET] + body, hashlib.sha256).digest()
        return header[:wire.FRAME_MAC_OFFSET] + mac + body

    def decode(self, frame, name, direction, expected_sequence):
        layout = self.profile.layout(name, direction)
        if (not isinstance(frame, bytes) or not wire.FRAME_SIZE < len(frame) <= layout["slot_bytes"] - wire.SLOT_SIZE):
            raise ProtocolError("invalid bounded SHM frame length")
        values = dict(zip(wire.FRAME_FIELDS, struct.unpack(wire.FRAME_FORMAT, frame[:wire.FRAME_SIZE])))
        if (values["magic"] != wire.FRAME_MAGIC or (values["major"], values["minor"]) != wire.VERSION
                or values["header_len"] != wire.FRAME_SIZE or values["flags"] != 0 or values["reserved"] != 0
                or values["body_len"] != len(frame) - wire.FRAME_SIZE or values["generation"] != self._generation_bytes
                or type(expected_sequence) is not int or not 1 <= expected_sequence <= wire.LIMITS["max_sequence"]
                or values["transport_sequence"] != expected_sequence):
            raise ProtocolError("SHM frame version, size, generation or sequence differs")
        body = frame[wire.FRAME_SIZE:]
        if (hashlib.sha256(body).digest() != values["body_sha256"] or not hmac.compare_digest(values["hmac_sha256"],
                hmac.new(self._key(layout), frame[:wire.FRAME_MAC_OFFSET] + body, hashlib.sha256).digest())):
            raise ProtocolError("SHM frame authentication failed")
        value = decode(body)
        message = str(UUID(bytes=values["message_id"]))
        if (not isinstance(value, dict) or set(value) != BODY_FIELDS or value["request_id"] != message
                or value["attempt_id"] != message or value["correlation_id"] is not None
                or value["contract_version"] != wire.CONTRACT_VERSION or value["identity"] != self.profile.route
                or value["ring_id"] != layout["ring_id"] or value["direction"] != layout["direction"]
                or type(value["ring_id"]) is not int or type(value["direction"]) is not int
                or value["capability_sha256"] != self.profile.capability_hash or value["key_id"] != self.profile.key_id):
            raise ProtocolError("SHM frame identity/profile differs")
        self._kind(value["kind"], name, direction)
        now = self._clock()
        if not source_timestamp(value["issued_at"]) <= now < source_timestamp(value["expires_at"]):
            raise ProtocolError("SHM transport frame expired or its clock is invalid")
        if message in self._seen:
            raise ProtocolError("replayed SHM frame")
        try:
            packet = base64.b64decode(value["payload"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ProtocolError("invalid SHM packet encoding") from exc
        cap = self.profile.control_max if name == "control" else self.profile.max_frame
        if (not 1 <= len(packet) <= cap or base64.b64encode(packet).decode("ascii") != value["payload"]):
            raise ProtocolError("SHM Session packet exceeds its unchanged byte budget")
        # Parse before committing the recent nonce; strict JSON rejects unsafe
        # packet data without changing any business state or durable cursor.
        packet_value = decode(packet)
        if not isinstance(packet_value, dict):
            raise ProtocolError("SHM Session packet must be an object")
        self._seen[message] = values["body_sha256"]
        while len(self._seen) > self.profile.max_recent:
            self._seen.popitem(last=False)
        return packet_value, value["kind"]

    def close(self):
        self._secret = None
        self._seen.clear()
