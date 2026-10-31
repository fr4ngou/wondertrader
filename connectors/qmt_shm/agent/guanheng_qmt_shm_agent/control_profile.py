# -*- coding: utf-8 -*-
"""Trusted control budgets; pure admission before starting any I/O owner."""
import math

from . import control_wire as wire
from .control_versions import control_contract
from .protocol import TransportBudget, canonical, decode


class ControlProfile(object):
    """Freeze one deployment profile, with room for both RPC directions.

    max_pending_calls bounds a sequence window, not just unfinished futures.
    Retained bytes assign fixed caller-role quotas at both peers: Host receives
    the odd slot so read + observation can coexist with a reverse query. An
    idle opposite role never lends credit that its peer could also allocate.
    max_retained_bytes counts canonical payloads and reserved response/receipt
    capacity; it is not an operating-system RSS measurement. Native operation
    policies and native result/observation budgets keep their existing owners.
    """
    def __init__(self, config, max_frame, budget):
        if not isinstance(config, dict):
            raise ValueError("control profile requires an explicit object")
        selected_wire = control_contract(config.get("schema_version"))
        if set(config) != set(selected_wire.PROFILE_BOUNDS) | {"schema_version"}:
            raise ValueError("control profile has missing or unknown fields/version")
        self._contract = selected_wire
        if type(max_frame) is not int or not 1024 <= max_frame <= 4194304:
            raise ValueError("invalid unchanged Session packet cap")
        if not isinstance(budget, TransportBudget):
            raise ValueError("control profile requires the existing transport budget owner")
        selected = {"schema_version": selected_wire.CONTRACT_VERSION}
        for name, (kind, minimum, maximum) in selected_wire.PROFILE_BOUNDS.items():
            value = config[name]
            if (type(value) not in ((int,) if kind == "integer" else (int, float))
                    or not minimum <= value <= maximum or not math.isfinite(value)):
                raise ValueError("invalid control budget: " + name)
            selected[name] = int(value) if kind == "integer" else float(value)
        self._profile = canonical(selected)
        self.io_seconds = budget.io_seconds
        for name, value in selected.items():
            if name != "schema_version":
                setattr(self, name, value)
        self.base_bytes = len(self._profile)
        if self.poll_seconds > self.io_seconds / 2:
            raise ValueError("control polling exceeds the existing I/O deadline")
        if (self.max_cycle_bytes > max_frame - wire.CONSTANTS["session_overhead_bytes"]
                or max(self.max_call_bytes, self.max_reply_bytes) + wire.CONSTANTS["cycle_overhead_bytes"] > self.max_cycle_bytes):
            raise ValueError("control cycle cannot contain a complete message within Session cap")
        self.require_directions(2)

    @property
    def contract(self):
        """Complete grammar of this trusted, already-authenticated version."""
        return self._contract

    @property
    def version(self):
        return self._contract.CONTRACT_VERSION

    @property
    def metadata(self):
        """Optional fixed metadata extension; only the version owner selects it."""
        return getattr(self._contract, "METADATA", None)

    @property
    def configuration(self):
        return decode(self._profile)

    def reservation(self, call_bytes):
        if type(call_bytes) is not int or not 1 <= call_bytes <= self.max_call_bytes:
            raise ValueError("invalid complete CALL reservation")
        return call_bytes + self.max_reply_bytes + wire.CONSTANTS["entry_overhead_bytes"]

    def call_slots(self, caller):
        """Maximum charged sequence span for this CALL origin at either peer.

        Each slot reserves a maximum CALL, REPLY and receipt. Both endpoints
        derive the same shares solely from the authenticated profile, including
        queued calls and retired gaps invisible to the other endpoint.
        """
        if caller not in wire.PACKET_KINDS:
            raise ValueError("control quota requires a trusted caller role")
        total = min(2 * self.max_pending_calls,
            (self.max_retained_bytes - self.base_bytes) // self.reservation(self.max_call_bytes))
        return (total + 1) // 2 if caller == "host" else total // 2

    def require_directions(self, count):
        """A pending read must leave capacity for a reverse metadata request."""
        if type(count) is not int or not 2 <= count <= 2 * self.max_pending_calls:
            raise ValueError("independent calls exceed the two direction windows")
        if self.max_retained_bytes < self.base_bytes + count * self.reservation(self.max_call_bytes):
            raise ValueError("control retained budget cannot contain required independent calls")

    @property
    def native_body_limit(self):
        # body is original bytes encoded once as base64 in the read payload;
        # the fixed reserve covers the complete RPC/read wrapper, not its data.
        return max(0, (self.max_call_bytes - wire.CONSTANTS["message_overhead_bytes"]) * 3 // 4)

    def require_native_budgets(self, max_result_bytes, max_observation_bytes=None):
        if self.native_body_limit <= 0:
            raise ValueError("control CALL budget cannot contain an original native read")
        values = (max_result_bytes,) if max_observation_bytes is None else (max_result_bytes, max_observation_bytes)
        for value in values:
            if (type(value) is not int or value < 1
                    or value + wire.CONSTANTS["message_overhead_bytes"] > self.max_reply_bytes):
                raise ValueError("control REPLY cannot contain the complete original result/page")
        if max_observation_bytes is not None:
            if self.max_pending_calls < 2:
                raise ValueError("control window cannot progress read and observation independently")
            self.require_directions(3)

    def require_roundtrip(self, queue_ms, native_ms):
        """Use the original policy budgets; never restart them at each cycle."""
        if any(type(value) is not int or value < 1 for value in (queue_ms, native_ms)):
            raise ValueError("control read requires original operation policy budgets")
        if (queue_ms + native_ms) / 1000 + self.io_seconds > self.max_call_seconds:
            raise ValueError("control lifetime cannot contain original queue/native/I/O budgets")


