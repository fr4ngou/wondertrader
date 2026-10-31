# -*- coding: utf-8 -*-
"""Builtin-mmap Channel for the unchanged authenticated business Session.

The Host alone selects an immutable peer nonce. Concurrent Agent arrivals only
write an admission mailbox and cannot replace the selected peer or its frames.
Two bounded single-writer slots carry complete reliable Session packets. Native
resource creation and protected ACL checks belong to builtin_shm_native.
"""
import hashlib
import hmac
import math
import mmap
import re
import struct
import sys
import threading
import time
from uuid import uuid4

from .protocol import ProtocolError, canonical, decode, identity


# 本仓新配对版本；install-008无schema配置须重新配对，不能隐式转为此版本。
PROFILE_SCHEMA = 'qmt.builtin-shm.v1'
MAGIC = b'QBIM0001'
HEADER_BYTES, SLOT_HEADER_BYTES = 256, 64
CLAIM_OFFSET, SELECTED_OFFSET = 96, 144
CLOSE_OFFSETS = {'host': 192, 'agent': 200}
MAX_SEQUENCE = 2 ** 53 - 1


class BuiltinMemoryProfile(object):
    """Trusted layout: bytes, seconds and actual Windows session, no defaults."""
    def __init__(self, config, route, max_frame, business_profile):
        # Aligned 64-bit sequence commits rely on this qualified Windows/x64
        # memory model. Other architectures require a separately verified
        # atomic-publication adapter rather than silently reusing this layout.
        if sys.platform != 'win32' or struct.calcsize('P') != 8 or 'AMD64' not in sys.version.upper():
            raise ValueError('builtin SHM requires qualified Windows AMD64 Python')
        if (type(config) is not dict or set(config) != {'kind', 'schema_version', 'name', 'max_mapped_bytes',
                'poll_seconds', 'windows_session_id'} or config['kind'] != 'builtin-shm'
                or config['schema_version'] != PROFILE_SCHEMA):
            raise ValueError('invalid builtin SHM profile fields')
        if not isinstance(config['name'], str) or not re.fullmatch(r'qmt-broker-[A-Za-z0-9_-]{1,80}', config['name']):
            raise ValueError('invalid builtin SHM private name')
        if type(max_frame) is not int or not 1024 <= max_frame <= 4194304:
            raise ValueError('invalid builtin SHM packet budget')
        if type(config['windows_session_id']) is not int or not 0 <= config['windows_session_id'] < 2 ** 32:
            raise ValueError('invalid builtin SHM Windows session')
        poll, maximum = config['poll_seconds'], config['max_mapped_bytes']
        if type(poll) not in (int, float) or not math.isfinite(poll) or not .001 <= poll <= .05:
            raise ValueError('invalid builtin SHM polling seconds')
        self.slot_bytes = ((SLOT_HEADER_BYTES + max_frame + 63) // 64) * 64
        self.mapped_bytes = HEADER_BYTES + 2 * self.slot_bytes
        if type(maximum) is not int or not self.mapped_bytes + HEADER_BYTES <= maximum <= 67108864:
            raise ValueError('builtin SHM exceeds declared mapped-byte budget')
        self.max_frame, self.poll_seconds = max_frame, float(poll)
        self.session_id = config['windows_session_id']
        route_hash = hashlib.sha256(canonical(identity(route))).hexdigest()
        self.name = 'Local\\' + config['name'] + '-' + route_hash[:16]
        self.profile_hash = hashlib.sha256(canonical({'configuration': config, 'route': route,
            'max_frame': max_frame, 'mapped_bytes': self.mapped_bytes,
            'rendezvous_bytes': HEADER_BYTES,
            'business': business_profile, 'layout': MAGIC.decode('ascii')})).digest()


def _mac(secret, domain, value):
    return hmac.new(secret, MAGIC + domain + value, hashlib.sha256).digest()


def authenticated_header(view, profile, secret):
    """Check the fixed bounded header before any peer-controlled allocation."""
    value = bytes(view[:88])
    if (value[:8] != MAGIC or value[24:56] != profile.profile_hash or
            not hmac.compare_digest(value[56:88], _mac(secret, b'header', value[:56]))):
        raise ProtocolError('builtin SHM header authentication differs')
    return value[8:24]


class BuiltinMemoryFramer(object):
    """Single I/O owner; cross-thread close only signals its local stop Event."""
    def __init__(self, view, profile, secret, generation, role, stop=None, dispose=None):
        self.view, self.profile, self.secret, self.role = view, profile, secret, role
        self.generation, self._generation = generation.hex(), generation
        self._owner = threading.get_ident()
        self._stop = stop if stop is not None else threading.Event()
        self._dispose, self._closed, self._authenticated = dispose, False, False
        self._sent, self._received, self._peer = 0, 0, None

    def _check(self, *, arriving=False):
        if threading.get_ident() != self._owner:
            raise RuntimeError('builtin SHM I/O belongs to its original worker')
        if self._closed or self._stop.is_set():
            raise OSError('builtin SHM binding is closing')
        if authenticated_header(self.view, self.profile, self.secret) != self._generation:
            raise ProtocolError('builtin SHM generation changed')
        peer_role = 'agent' if self.role == 'host' else 'host'
        if struct.unpack('<Q', self.view[CLOSE_OFFSETS[peer_role]:CLOSE_OFFSETS[peer_role]+8])[0]:
            raise OSError('builtin SHM peer is closing')
        if not arriving and self._peer is not None:
            selected = bytes(self.view[SELECTED_OFFSET:SELECTED_OFFSET+48])
            if selected != self._claim(self._peer, b'selected'):
                raise ProtocolError('builtin SHM selected peer changed')

    def _claim(self, nonce, domain):
        return nonce + _mac(self.secret, domain, self._generation + self.profile.profile_hash + nonce)

    def _wait(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('builtin SHM deadline expired')
        self._stop.wait(min(remaining, self.profile.poll_seconds))

    def wait_peer(self, deadline, *, wait_for_peer=False):
        """Host独占认领一个对端；显式常驻模式只延续空闲等待。

        映射创建仍沿原deadline，认证握手在Session另用有限I/O期限。
        本循环只由原I/O线程读共享内存；stop唤醒后由同线程收口资源。
        """
        if type(wait_for_peer) is not bool:
            raise ValueError("explicit peer wait mode required")
        if self.role != 'host' or self._peer is not None:
            raise ProtocolError('builtin SHM peer admission has one Host owner')
        while True:
            self._check(arriving=True)
            value = bytes(self.view[CLAIM_OFFSET:CLAIM_OFFSET+48])
            if value[:16] != b'\0' * 16 and hmac.compare_digest(value, self._claim(value[:16], b'arrival')):
                if not wait_for_peer and time.monotonic() >= deadline:
                    raise TimeoutError('builtin SHM peer admission deadline expired')
                self._peer = value[:16]
                self.view[SELECTED_OFFSET:SELECTED_OFFSET+48] = self._claim(self._peer, b'selected')
                return
            if wait_for_peer:
                self._stop.wait(self.profile.poll_seconds)
            else:
                self._wait(deadline)

    def join(self, deadline):
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or time.monotonic() >= deadline:
            raise TimeoutError('builtin SHM peer admission deadline expired')
        self._peer = uuid4().bytes
        # A selected peer is immutable for this Host generation. Arrivals do
        # not touch either reliable slot until Host has chosen their nonce.
        self._check(arriving=True)
        selected = bytes(self.view[SELECTED_OFFSET:SELECTED_OFFSET+48])
        if selected != b'\0' * 48:
            if not hmac.compare_digest(selected, self._claim(selected[:16], b'selected')):
                raise ProtocolError('builtin SHM selected peer authentication differs')
            # 已认证旧对端仍占用本代：等待owner换代，不覆盖其nonce或关闭位。
            raise OSError('builtin SHM generation already has an authenticated Agent')
        claim = self._claim(self._peer, b'arrival')
        if time.monotonic() >= deadline:
            raise TimeoutError('builtin SHM peer admission deadline expired')
        self.view[CLAIM_OFFSET:CLAIM_OFFSET+48] = claim
        while True:
            self._check(arriving=True)
            selected = bytes(self.view[SELECTED_OFFSET:SELECTED_OFFSET+48])
            if hmac.compare_digest(selected, self._claim(selected[:16], b'selected')):
                if selected[:16] != self._peer:
                    raise OSError('builtin SHM selected another authenticated Agent')
                if time.monotonic() >= deadline:
                    raise TimeoutError('builtin SHM peer selection deadline expired')
                return
            self._wait(deadline)

    def authenticated(self, generation):
        self._check()
        if generation != self.generation or self._authenticated or self._peer is None:
            raise ProtocolError('builtin SHM Session generation differs')
        self._authenticated = True

    def _slot(self, outbound):
        host_direction = (self.role == 'host') == outbound
        return HEADER_BYTES + (0 if host_direction else self.profile.slot_bytes), b'H' if host_direction else b'A'

    def _packet_mac(self, direction, sequence, packet):
        return _mac(self.secret, b'packet', self._generation + self.profile.profile_hash + self._peer
            + direction + struct.pack('<QI', sequence, len(packet)) + packet)

    def send(self, value, deadline):
        self._check()
        packet = canonical(value)
        if self._peer is None or not 1 <= len(packet) <= self.profile.max_frame or self._sent >= MAX_SEQUENCE:
            raise ProtocolError('builtin SHM frame exceeds its boundary')
        offset, direction = self._slot(True)
        while struct.unpack('<Q', self.view[offset+8:offset+16])[0] != self._sent:
            self._check()
            self._wait(deadline)
        self._check()
        if time.monotonic() >= deadline:
            raise TimeoutError('builtin SHM send deadline expired')
        sequence = self._sent + 1
        self.view[offset+64:offset+64+len(packet)] = packet
        self.view[offset+16:offset+24] = struct.pack('<II', len(packet), 0)
        self.view[offset+24:offset+56] = self._packet_mac(direction, sequence, packet)
        # Commit last. The writer cannot reuse this slot before receiver ACK.
        if time.monotonic() >= deadline:
            raise TimeoutError('builtin SHM send publication deadline expired')
        self.view[offset:offset+8] = struct.pack('<Q', sequence)
        self._sent = sequence

    def receive(self, deadline):
        offset, direction = self._slot(False)
        while True:
            self._check()
            sequence = struct.unpack('<Q', self.view[offset:offset+8])[0]
            if sequence != self._received:
                break
            self._wait(deadline)
        if sequence != self._received + 1 or sequence > MAX_SEQUENCE:
            raise ProtocolError('builtin SHM frame sequence differs')
        if time.monotonic() >= deadline:
            raise TimeoutError('builtin SHM receive deadline expired')
        size, reserved = struct.unpack('<II', self.view[offset+16:offset+24])
        if not 1 <= size <= self.profile.max_frame or reserved or bytes(self.view[offset+56:offset+64]) != b'\0' * 8:
            raise ProtocolError('builtin SHM frame length/reserved fields differ')
        packet = bytes(self.view[offset+64:offset+64+size])
        proof = bytes(self.view[offset+24:offset+56])
        self._check()
        if (struct.unpack('<Q', self.view[offset:offset+8])[0] != sequence or
                not hmac.compare_digest(proof, self._packet_mac(direction, sequence, packet))):
            raise ProtocolError('builtin SHM frame authentication differs')
        result = decode(packet)
        self._check()
        if time.monotonic() >= deadline:
            raise TimeoutError('builtin SHM decode deadline expired')
        self._received = sequence
        self.view[offset+8:offset+16] = struct.pack('<Q', sequence)
        return result

    def request_close(self):
        self._stop.set()

    def close(self):
        """原I/O线程释放；失败保留尚未关闭的字段，随后同owner可继续收口。"""
        if threading.get_ident() != self._owner:
            self.request_close()
            return
        if self._closed:
            return
        self._stop.set()
        failure = None
        if self.view is not None:
            try:
                # 未被选中的到达者不能写活动连接的关闭位。
                selected = bytes(self.view[SELECTED_OFFSET:SELECTED_OFFSET+48])
                if (self.role == 'host' or self._peer is not None
                        and selected == self._claim(self._peer, b'selected')):
                    try:
                        generation = authenticated_header(self.view, self.profile, self.secret)
                    except ProtocolError:
                        generation = None
                    if generation == self._generation:
                        offset = CLOSE_OFFSETS[self.role]
                        self.view[offset:offset+8] = struct.pack('<Q', 1)
            except BaseException as exc:
                failure = exc
            try:
                self.view.close()
            except BaseException as exc:
                if failure is None:
                    failure = exc
            else:
                self.view = None
        if self._dispose is not None:
            try:
                self._dispose()
            except BaseException as exc:
                if failure is None:
                    failure = exc
            else:
                self._dispose = None
        self._closed = self.view is None and self._dispose is None
        if self._closed:
            self.secret = None
        if failure is not None:
            raise failure


class BuiltinMemoryConnector(object):
    """一个原I/O线程的建连owner；失败视图先成功释放，再允许继续探测。"""
    def __init__(self, profile, secret, stop=None):
        self.profile, self.secret = profile, secret
        self._owner = threading.get_ident()
        self._stop = stop if stop is not None else threading.Event()
        self._rendezvous, self._view, self._framer = None, None, None
        self._attempted = False

    def _check(self, deadline):
        if threading.get_ident() != self._owner:
            raise RuntimeError('builtin SHM connector belongs to its original worker')
        if self._stop.is_set():
            raise OSError('builtin SHM connect cancelled')
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or time.monotonic() >= deadline:
            raise TimeoutError('builtin SHM connect deadline expired')

    def _release(self, attribute):
        value = getattr(self, attribute)
        if value is not None:
            value.close()
            setattr(self, attribute, None)

    def _wait(self, deadline):
        self._check(deadline)
        self._stop.wait(min(self.profile.poll_seconds, max(0, deadline-time.monotonic())))

    def connect(self, deadline):
        if self._attempted:
            raise OSError('builtin SHM connector has one connection attempt')
        self._attempted = True
        try:
            while True:
                self._check(deadline)
                self._rendezvous = mmap.mmap(-1, HEADER_BYTES, tagname=self.profile.name)
                self._check(deadline)
                try:
                    generation = authenticated_header(self._rendezvous, self.profile, self.secret)
                    if struct.unpack('<Q', self._rendezvous[CLOSE_OFFSETS['host']:CLOSE_OFFSETS['host']+8])[0]:
                        raise ProtocolError('builtin SHM Host rendezvous is closing')
                except ProtocolError:
                    # 缺名字只产生未认证小view；释放后在原D内等待原Host，不切后端。
                    self._release('_rendezvous')
                    self._wait(deadline)
                    continue
                self._release('_rendezvous')
                self._check(deadline)
                self._view = mmap.mmap(-1, self.profile.mapped_bytes,
                    tagname=self.profile.name+'-'+generation.hex())
                self._check(deadline)
                try:
                    if authenticated_header(self._view, self.profile, self.secret) != generation:
                        raise ProtocolError('builtin SHM data generation differs from rendezvous')
                except ProtocolError:
                    self._release('_view')
                    self._wait(deadline)
                    continue
                self._framer = BuiltinMemoryFramer(self._view, self.profile, self.secret,
                    generation, 'agent', self._stop)
                self._view = None
                self._framer.join(deadline)
                self._check(deadline)
                return self._framer
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass  # 原异常继续上抛，失败资源仍在此owner的字段内。
            raise

    def close(self):
        self._stop.set()
        if threading.get_ident() != self._owner:
            return
        failure = None
        for attribute in ('_framer', '_view', '_rendezvous'):
            try:
                self._release(attribute)
            except BaseException as exc:
                if failure is None:
                    failure = exc
        if failure is not None:
            raise failure


def connect(profile, secret, deadline, stop=None, _owner=None):
    """LocalTransport在I/O前持有_owner；Agent只用内建mmap，不打开文件或DLL。"""
    connector = _owner if _owner is not None else BuiltinMemoryConnector(profile, secret, stop)
    return connector.connect(deadline)
