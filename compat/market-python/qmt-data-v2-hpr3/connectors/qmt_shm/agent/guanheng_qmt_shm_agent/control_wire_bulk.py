# -*- coding: utf-8 -*-
"""生成的显式bulk grammar；修改公开 JSON 后运行生成器。"""
# Source: connectors/qmt_shm/protocol/local_control_protocol_bulk.json
from types import MappingProxyType
from . import control_wire as base

SOURCE_SHA256 = 'c8af6c839de2334663e038c141aef672bcbec2182ee62d2191a586a727f4e8d4'
BASE_SOURCE_SHA256 = '0f87c044850d410019647381e2db7c8f44a6cfb52bd3c55bdfb67095f06b59a3'
CONTRACT_VERSION = '3.0'

if base.SOURCE_SHA256 != BASE_SOURCE_SHA256:
    raise ImportError('bulk grammar base identity differs')

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
    + tuple({'agent.bulk.open': 'host', 'agent.bulk.page': 'host', 'agent.bulk.status': 'host'}.items())))
OPERATION_PAYLOAD_FIELDS = MappingProxyType(dict(tuple(base.OPERATION_PAYLOAD_FIELDS.items())
    + tuple({'agent.bulk.open': ('request_id', 'identity', 'arguments', 'clock_schema', 'deadline_ms', 'queue_deadline_ms'), 'agent.bulk.page': ('request_id', 'identity', 'page_index'), 'agent.bulk.status': ('request_id', 'identity')}.items())))
