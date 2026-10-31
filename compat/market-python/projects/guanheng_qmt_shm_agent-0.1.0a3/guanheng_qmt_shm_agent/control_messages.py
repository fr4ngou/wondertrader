# -*- coding: utf-8 -*-
"""Strict pure control envelopes; all messages validate before owner delivery."""
import hashlib
import math
import re

from . import control_wire as wire
from .control_versions import control_contract
from .timestamps import source_timestamp
from .protocol import ProtocolError, Session, canonical, decode, identity


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sequence(value):
    if type(value) is not int or not 1 <= value <= wire.CONSTANTS["max_sequence"]:
        raise ProtocolError("invalid control sequence")
    return value


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ProtocolError("invalid control content identity")


def _bytes(value):
    try:
        return canonical(value)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("control message is not bounded JSON data") from exc


def validate_message(value, profile, sender):
    wire = profile.contract
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str) or value["kind"] not in wire.MESSAGE_FIELDS:
        raise ProtocolError("unknown control message kind")
    kind = value["kind"]
    if set(value) != set(wire.MESSAGE_FIELDS[kind]):
        raise ProtocolError("control message has missing or unknown fields")
    sequence(value["call_seq"])
    maximum = profile.max_call_bytes if kind == "CALL" else profile.max_reply_bytes
    if kind == "ACK":
        maximum = wire.CONSTANTS["entry_overhead_bytes"]
    if len(_bytes(value)) > maximum:
        raise ProtocolError("control message exceeds its complete byte budget")
    if kind == "CALL":
        operation = value["operation"]
        if (not isinstance(operation, str) or operation not in wire.OPERATION_CALLERS
                or wire.OPERATION_CALLERS[operation] != sender):
            raise ProtocolError("control operation is unavailable in this direction")
        payload = value["payload"]
        if not isinstance(payload, dict) or set(payload) != set(wire.OPERATION_PAYLOAD_FIELDS[operation]):
            raise ProtocolError("control operation payload has missing or unknown fields")
        source_timestamp(value["expires_at"])
    elif kind == "REPLY":
        _digest(value["request_sha256"])
        if type(value["ok"]) is not bool:
            raise ProtocolError("control reply requires literal success state")
        if value["ok"]:
            if not isinstance(value["payload"], dict) or value["error"] is not None:
                raise ProtocolError("control success payload differs")
        else:
            error = value["error"]
            if (value["payload"] is not None or not isinstance(error, dict) or set(error) != set(wire.ERROR_FIELDS)
                    or not isinstance(error["code"], str) or error["code"] not in wire.ERROR_CODES
                    or not isinstance(error["message"], str)
                    or not 1 <= len(error["message"].encode("utf-8")) <= wire.CONSTANTS["max_error_text_bytes"]):
                raise ProtocolError("control failure payload differs")
    else:
        _digest(value["reply_sha256"])


def validate_packet(value, profile, sender, generation, cycle_seq):
    """Return a private immutable-by-owner copy only after the entire grammar.

    Contextual request/window/receipt checks belong to the peer's single memory
    transaction; domain/native handlers never run in this validation function.
    """
    wire = profile.contract
    if sender not in wire.PACKET_KINDS:
        raise ValueError("unknown trusted control peer role")
    Session._nonce(generation)
    sequence(cycle_seq)
    if (not isinstance(value, dict) or set(value) != set(wire.PACKET_FIELDS)
            or value["kind"] != wire.PACKET_KINDS[sender] or value["schema_version"] != wire.CONTRACT_VERSION
            or value["generation"] != generation or type(value["cycle_seq"]) is not int
            or value["cycle_seq"] != cycle_seq):
        raise ProtocolError("control cycle identity, version or sequence differs")
    last_tick = value["last_tick"]
    if (sender == "host" and last_tick is not None
            or last_tick is not None and (type(last_tick) not in (int, float)
                or not 0 <= last_tick <= wire.CONSTANTS["max_last_tick"] or not math.isfinite(last_tick))):
        raise ProtocolError("control liveness is not an original finite strategy tick")
    messages = value["messages"]
    if not isinstance(messages, list) or len(messages) > profile.max_cycle_messages:
        raise ProtocolError("control cycle message count exceeds its budget")
    encoded = _bytes(value)
    if len(encoded) > profile.max_cycle_bytes:
        raise ProtocolError("control cycle exceeds its complete byte budget")
    seen = set()
    for message in messages:
        validate_message(message, profile, sender)
        reference = (message["kind"], message["call_seq"])
        if reference in seen:
            raise ProtocolError("duplicate control message within one cycle")
        seen.add(reference)
    return decode(encoded)


def validate_host_binding(value, *, route, generation, capability_sha256, observation_identity, schema_version="1.0"):
    """The authenticated Host reports its actual store, never a guessed epoch.

    Instance/transport IDs identify this connection. They do not establish any
    account or native execution authority; a plain read Journal reports null.
    """
    wire = control_contract(schema_version)
    if (not isinstance(value, dict) or set(value) != set(wire.BINDING_FIELDS)
            or value["schema_version"] != wire.CONTRACT_VERSION or identity(value["route"]) != identity(route)
            or value["transport_generation"] != generation or value["capability_sha256"] != capability_sha256):
        raise ProtocolError("Host binding differs from the actual authenticated profile")
    Session._nonce(generation)
    Session._nonce(value["host_instance_id"])
    _digest(capability_sha256)
    journal_generation = value["journal_generation"]
    if journal_generation is not None and (type(journal_generation) is not int or not 1 <= journal_generation < 2 ** 63):
        raise ProtocolError("Host Journal generation is unavailable or invalid")
    if getattr(wire, "METADATA", None) is not None and journal_generation is None:
        raise ProtocolError("metadata requires the actual native Journal generation")
    observed = value["observation_identity"]
    if observed != observation_identity:
        raise ProtocolError("Host observation identity differs from the trusted scope")
    if observed is not None:
        if (not isinstance(observed, dict) or set(observed) != set(wire.OBSERVATION_IDENTITY_FIELDS)
                or observed["account_environment"] not in ("simulation", "live")):
            raise ProtocolError("invalid Host observation identity")
        for name in ("agent_id", "account_id", "qmt_session_id"):
            if not isinstance(observed[name], str) or not 1 <= len(observed[name].encode("utf-8")) <= 128:
                raise ProtocolError("invalid Host observation source")
    return decode(_bytes(value))


def host_binding(*, route, generation, host_instance_id, journal_generation, capability_sha256,
                 observation_identity, schema_version="1.0"):
    """Build and validate one actual binding using the same public field owner.

    Budget admission can pass maximum-width placeholder IDs. Such a template
    measures bytes only and never becomes a connected or cached authority.
    """
    value = {"schema_version": schema_version, "route": route, "transport_generation": generation,
        "host_instance_id": host_instance_id, "journal_generation": journal_generation,
        "observation_identity": observation_identity, "capability_sha256": capability_sha256}
    return validate_host_binding(value, route=route, generation=generation,
        capability_sha256=capability_sha256, observation_identity=observation_identity, schema_version=schema_version)
