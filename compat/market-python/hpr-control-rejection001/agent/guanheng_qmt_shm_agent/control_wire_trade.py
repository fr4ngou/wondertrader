# -*- coding: utf-8 -*-
"""生成的显式交易 grammar；修改公开 JSON 后运行生成器。"""
# Source: connectors/qmt_shm/protocol/local_control_protocol_trade.json
from types import MappingProxyType
from . import control_wire as base

SOURCE_SHA256 = 'fad86306863baac40ea781e496ff634176c2eb433afe8bc3a39f50030f1a3628'
BASE_SOURCE_SHA256 = '0f87c044850d410019647381e2db7c8f44a6cfb52bd3c55bdfb67095f06b59a3'
CONTRACT_VERSION = '2.0'

if base.SOURCE_SHA256 != BASE_SOURCE_SHA256:
    raise ImportError('trade grammar base identity differs')

PACKET_FIELDS = base.PACKET_FIELDS
BINDING_FIELDS = base.BINDING_FIELDS
OBSERVATION_IDENTITY_FIELDS = base.OBSERVATION_IDENTITY_FIELDS
ERROR_FIELDS = base.ERROR_FIELDS
PACKET_KINDS = base.PACKET_KINDS
MESSAGE_FIELDS = base.MESSAGE_FIELDS
ERROR_CODES = base.ERROR_CODES
PROFILE_BOUNDS = base.PROFILE_BOUNDS
CONSTANTS = base.CONSTANTS

OPERATION_CALLERS = MappingProxyType(dict(tuple(base.OPERATION_CALLERS.items())
    + tuple({'agent.trade': 'host', 'agent.trade.status': 'host', 'agent.trade.events': 'host', 'agent.trade.ack': 'host'}.items())))
OPERATION_PAYLOAD_FIELDS = MappingProxyType(dict(tuple(base.OPERATION_PAYLOAD_FIELDS.items())
    + tuple({'agent.trade': ('kind', 'body', 'clock_schema', 'deadline_ms'), 'agent.trade.status': (), 'agent.trade.events': ('session_id', 'after_seq', 'limit', 'max_bytes'), 'agent.trade.ack': ('session_id', 'through_seq')}.items())))
