# -*- coding: utf-8 -*-
"""Generated control constants; edit public JSON and regenerate."""
# Source: src/qmt_platform/common/local_control_protocol.json
# Canonical definition SHA-256: 0f87c044850d410019647381e2db7c8f44a6cfb52bd3c55bdfb67095f06b59a3
from types import MappingProxyType


SOURCE_SHA256 = '0f87c044850d410019647381e2db7c8f44a6cfb52bd3c55bdfb67095f06b59a3'
CONTRACT_VERSION = '1.0'
PACKET_FIELDS = ('kind', 'schema_version', 'generation', 'cycle_seq', 'last_tick', 'messages')
BINDING_FIELDS = ('schema_version', 'route', 'transport_generation', 'host_instance_id', 'journal_generation', 'observation_identity', 'capability_sha256')
OBSERVATION_IDENTITY_FIELDS = ('agent_id', 'account_id', 'account_environment', 'qmt_session_id')
ERROR_FIELDS = ('code', 'message')
PACKET_KINDS = MappingProxyType({'host': 'control.cycle', 'agent': 'control.cycle.result'})
MESSAGE_FIELDS = MappingProxyType({'CALL': ('kind', 'call_seq', 'operation', 'expires_at', 'payload'), 'REPLY': ('kind', 'call_seq', 'request_sha256', 'ok', 'payload', 'error'), 'ACK': ('kind', 'call_seq', 'reply_sha256')})
OPERATION_CALLERS = MappingProxyType({'agent.read': 'host', 'agent.observations': 'host', 'host.binding.read': 'agent'})
OPERATION_PAYLOAD_FIELDS = MappingProxyType({'agent.read': ('kind', 'body', 'queue_timeout_ms', 'queue_expires_at'), 'agent.observations': ('after_seq',), 'host.binding.read': ()})
ERROR_CODES = frozenset(('invalid_arguments', 'queue_full', 'capability_unavailable', 'call_expired', 'reply_too_large', 'binding_closed'))
PROFILE_BOUNDS = MappingProxyType({'max_pending_calls': ('integer', 1, 1024), 'max_call_bytes': ('integer', 1024, 1048576), 'max_reply_bytes': ('integer', 1024, 4190208), 'max_retained_bytes': ('integer', 1, 67108864), 'max_cycle_messages': ('integer', 1, 64), 'max_cycle_bytes': ('integer', 2048, 4190208), 'poll_seconds': ('finite_number', 0.001, 1), 'max_call_seconds': ('finite_number', 0.1, 360)})
CONSTANTS = MappingProxyType({'entry_overhead_bytes': 1024, 'cycle_overhead_bytes': 1024, 'message_overhead_bytes': 1024, 'session_overhead_bytes': 4096, 'max_error_text_bytes': 256, 'max_sequence': 18446744073709551615, 'max_last_tick': 253402300799})
