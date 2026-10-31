# -*- coding: utf-8 -*-
"""Generated wire constants. Edit the public JSON owner and regenerate."""
# Source: src/qmt_platform/common/local_transport_protocol.json
# Canonical definition SHA-256: 85381c8ca186afcb249b48ccae5c15470132f2317b97dffbce82d9125afb38be
from types import MappingProxyType


SOURCE_SHA256 = '85381c8ca186afcb249b48ccae5c15470132f2317b97dffbce82d9125afb38be'
CONTRACT_VERSION = '1.0'
VERSION = (1, 0)
RING_MAGIC = b'QMTBRNG1'
FRAME_MAGIC = b'QMTBFRM1'
RING_FORMAT = '<8sHHI16sIIIIQQQQ32s32sII104s'
RING_SIZE = 256
RING_FIELDS = ('magic', 'major', 'minor', 'header_size', 'generation', 'ring_id', 'direction', 'slot_count', 'slot_bytes', 'mapped_bytes', 'head', 'tail', 'route_epoch', 'route_identity_sha256', 'profile_sha256', 'state', 'peer_claim', 'reserved')
RING_OFFSETS = MappingProxyType({'magic': 0, 'major': 8, 'minor': 10, 'header_size': 12, 'generation': 16, 'ring_id': 32, 'direction': 36, 'slot_count': 40, 'slot_bytes': 44, 'mapped_bytes': 48, 'head': 56, 'tail': 64, 'route_epoch': 72, 'route_identity_sha256': 80, 'profile_sha256': 112, 'state': 144, 'peer_claim': 148, 'reserved': 152})
SLOT_FORMAT = '<IIQ'
SLOT_SIZE = 16
SLOT_FIELDS = ('frame_len', 'commit', 'slot_sequence')
SLOT_OFFSETS = MappingProxyType({'frame_len': 0, 'commit': 4, 'slot_sequence': 8})
FRAME_FORMAT = '<8sHHHHII16s16sQ32s32s'
FRAME_SIZE = 128
FRAME_FIELDS = ('magic', 'major', 'minor', 'header_len', 'flags', 'body_len', 'reserved', 'generation', 'message_id', 'transport_sequence', 'body_sha256', 'hmac_sha256')
FRAME_OFFSETS = MappingProxyType({'magic': 0, 'major': 8, 'minor': 10, 'header_len': 12, 'flags': 14, 'body_len': 16, 'reserved': 20, 'generation': 24, 'message_id': 40, 'transport_sequence': 56, 'body_sha256': 64, 'hmac_sha256': 96})
RINGS = MappingProxyType({'command': 1, 'reliable': 2, 'quote': 3, 'control': 4})
DIRECTIONS = MappingProxyType({'host_to_agent': 1, 'agent_to_host': 2})
STATES = MappingProxyType({'init': 1, 'ready': 2, 'draining': 3, 'quarantined': 4, 'closed': 5})
COMMITS = MappingProxyType({'empty': 0, 'committed': 1})
MESSAGE_KINDS = frozenset(('HELLO', 'HELLO_ACK', 'REQUEST', 'RESULT', 'QUOTE', 'PING', 'PONG', 'ERROR', 'DRAIN'))
ENVELOPE_RESERVE_BYTES = 4096
HANDSHAKE_OVERHEAD_BYTES = 2048
FRAME_MAC_OFFSET = 96
LIMITS = MappingProxyType({'max_packet_bytes': 4194304, 'max_slot_count': 1024, 'quote_slot_count': 1, 'control_slot_count': 1, 'max_mapped_bytes': 67108864, 'min_control_packet_bytes': 1024, 'max_control_packet_bytes': 65536, 'max_name_bytes': 80, 'max_key_id_bytes': 64, 'max_recent_frames': 4096, 'min_poll_seconds': 0.001, 'max_poll_seconds': 1, 'close_signal_seconds': 0.05, 'max_sequence': 18446744073709551615})
