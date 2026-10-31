# -*- coding: utf-8 -*-
"""Private pagefile-backed Win32 rings, owned and disposed by one I/O thread.

No Python file, socket, pipe or database API is used. Mutexes guard bounded
copies only; authentication/JSON and business work happen after leaving them.
An Event is a wake hint. Shared counters remain the authority after every wake.
"""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
import math
import struct
import threading
import time
from uuid import uuid4

from . import shm_wire as wire
from .protocol import ProtocolError, canonical
from .shm_codec import FrameCodec, generation_bytes
from .windows_security import (SecurityAttributes, check, current_session,
    libraries, private_descriptor, utc_now, verify_private_object, SecurityResources)


WAIT_OBJECT_0, WAIT_ABANDONED, WAIT_TIMEOUT = 0, 128, 258
READ_CONTROL, SYNCHRONIZE = 0x20000, 0x100000
MAP_ACCESS, MUTEX_ACCESS, EVENT_ACCESS = READ_CONTROL | 6, READ_CONTROL | SYNCHRONIZE | 1, READ_CONTROL | SYNCHRONIZE | 2


class _Starting(Exception):
    """Host has not published its first complete bootstrap header yet."""


def _libraries():
    kernel, security = libraries()
    for name, (arguments, result) in {
        "CreateFileMappingW": ([w.HANDLE, ctypes.POINTER(SecurityAttributes), w.DWORD,
            w.DWORD, w.DWORD, w.LPCWSTR], w.HANDLE),
        "OpenFileMappingW": ([w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE),
        "MapViewOfFile": ([w.HANDLE, w.DWORD, w.DWORD, w.DWORD, ctypes.c_size_t], w.LPVOID),
        "UnmapViewOfFile": ([w.LPCVOID], w.BOOL),
        "CreateMutexW": ([ctypes.POINTER(SecurityAttributes), w.BOOL, w.LPCWSTR], w.HANDLE),
        "OpenMutexW": ([w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE),
        "ReleaseMutex": ([w.HANDLE], w.BOOL),
        "CreateEventW": ([ctypes.POINTER(SecurityAttributes), w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE),
        "OpenEventW": ([w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE),
        "SetEvent": ([w.HANDLE], w.BOOL),
        "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
        "GetSystemTimePreciseAsFileTime": ([ctypes.POINTER(w.FILETIME)], None),
    }.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = arguments, result
    return kernel, security


def _remaining(deadline):
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError("invalid SHM monotonic deadline")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("SHM deadline elapsed")
    return remaining


class _View(object):
    """Every pointer access is bounded by a locally admitted, exact view size."""
    def __init__(self, pointer, size):
        self.pointer, self.size = pointer, size

    def _address(self, offset, length):
        if (type(offset) is not int or type(length) is not int or offset < 0
                or length < 0 or offset > self.size - length):
            raise ProtocolError("SHM memory access exceeds the admitted view")
        return self.pointer + offset

    def read(self, offset, length):
        return ctypes.string_at(self._address(offset, length), length)

    def write(self, offset, data):
        ctypes.memmove(self._address(offset, len(data)), data, len(data))


class _Resources(object):
    """Only the creating I/O thread disposes handles; foreign actors publish stop only."""
    def __init__(self, profile, stop):
        self.kernel, self.security = _libraries()
        self._security_resources = SecurityResources(self.kernel)
        if current_session(self.kernel) != profile.session_id:
            raise OSError("SHM requires the configured current Windows session")
        self.profile, self.stop = profile, stop
        self.owner = threading.get_ident()
        self.handles, self.views, self.events = [], [], []
        self._lifecycle = threading.Lock()
        self._disposed = False
        self.peer_owned = None

    def _handle(self, handle, created, required):
        # Capture the create result immediately, before security API calls can
        # overwrite GetLastError. Existing named objects are never initialized.
        error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(error)
        if handle not in self.handles:
            self.handles.append(handle)
        if created and error == 183:
            raise OSError("SHM kernel object name is already owned")
        verify_private_object(self.kernel, self.security, handle, required, resources=self._security_resources)
        return handle

    def _create(self, function, *arguments):
        with self._security_resources.scope():
            descriptor = private_descriptor(self.kernel, self.security, resources=self._security_resources)
            attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
            ctypes.set_last_error(0)
            handle = function(ctypes.byref(attributes), *arguments)
            error = ctypes.get_last_error()
            # scope释放descriptor前先持有native返回值；失败不能丢掉它。
            if handle:
                self.handles.append(handle)
        ctypes.set_last_error(error)
        return handle

    def mapping(self, name, size, create):
        if create:
            handle = self._create(lambda attrs: self.kernel.CreateFileMappingW(
                w.HANDLE(-1), attrs, 4, 0, size, name))
        else:
            handle = self.kernel.OpenFileMappingW(MAP_ACCESS, False, name)
        handle = self._handle(handle, create, MAP_ACCESS)
        pointer = check(self.kernel.MapViewOfFile(handle, 6, 0, 0, size))
        view = _View(pointer, size)
        self.views.append(view)
        return view

    def mutex(self, name, create):
        handle = (self._create(self.kernel.CreateMutexW, False, name) if create
            else self.kernel.OpenMutexW(MUTEX_ACCESS, False, name))
        return self._handle(handle, create, MUTEX_ACCESS)

    def event(self, name, create):
        # Auto-reset events can lose/coalesce notifications; polling counters
        # makes this safe and avoids using reset races as queue state.
        handle = (self._create(self.kernel.CreateEventW, False, False, name) if create
            else self.kernel.OpenEventW(EVENT_ACCESS, False, name))
        handle = self._handle(handle, create, EVENT_ACCESS)
        self.events.append(handle)
        return handle

    def wait(self, handle, deadline):
        if self.stop.is_set():
            raise OSError("SHM binding is closing")
        milliseconds = max(1, int(math.ceil(min(self.profile.poll_seconds, _remaining(deadline)) * 1000)))
        result = self.kernel.WaitForSingleObject(handle, milliseconds)
        if result not in (WAIT_OBJECT_0, WAIT_ABANDONED, WAIT_TIMEOUT):
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def wake(self):
        # Handle disposal and cross-thread SetEvent cannot race handle reuse.
        with self._lifecycle:
            if not self._disposed:
                for event in self.events:
                    self.kernel.SetEvent(event)

    def dispose(self):
        if threading.current_thread() is not self._security_resources.owner:
            raise RuntimeError("SHM resource disposal belongs to its I/O owner")
        with self._lifecycle:
            if self._disposed:
                return
            failure = None
            if self.peer_owned is not None:
                try:
                    check(self.kernel.ReleaseMutex(self.peer_owned))
                except BaseException as exc:
                    failure = exc
                else:
                    self.peer_owned = None
            for view in tuple(reversed(self.views)):
                try:
                    check(self.kernel.UnmapViewOfFile(view.pointer))
                except BaseException as exc:
                    if failure is None:
                        failure = exc
                else:
                    self.views.remove(view)
            for handle in tuple(reversed(self.handles)):
                if handle == self.peer_owned:
                    continue
                try:
                    check(self.kernel.CloseHandle(handle))
                except BaseException as exc:
                    if failure is None:
                        failure = exc
                else:
                    self.handles.remove(handle)
                    if handle in self.events:
                        self.events.remove(handle)
            try:
                self._security_resources.close()
            except BaseException as exc:
                if failure is None:
                    failure = exc
            self._disposed = (self.peer_owned is None and not self.views and not self.handles
                and self._security_resources.closed)
            if failure is not None:
                raise failure


class Ring(object):
    """One writer and one reader per ring, guarded by one kernel Mutex.

    A writer commits prefix/head only after its entire frame copy. A reader
    advances tail only after a complete private copy. Abandoned mutexes and
    broken invariants quarantine the generation instead of guessing recovery.
    """
    def __init__(self, resources, view, offset, mutex, event, name, direction, generation):
        self.resources, self.view, self.offset = resources, view, offset
        self.mutex, self.event = mutex, event
        self.name, self.direction, self.generation = name, direction, generation
        self.layout = resources.profile.layout(name, direction)
        self._sent = 0
        self._expected = dict(self.layout, magic=wire.RING_MAGIC, major=wire.VERSION[0], minor=wire.VERSION[1],
            header_size=wire.RING_SIZE, generation=generation_bytes(generation),
            route_epoch=resources.profile.route["route_epoch"], route_identity_sha256=resources.profile.route_hash,
            profile_sha256=resources.profile.profile_hash, reserved=b"\0" * 104)

    def _write_field(self, name, format_text, value):
        self.view.write(self.offset + wire.RING_OFFSETS[name], struct.pack(format_text, value))

    def initialize(self):
        values = dict(self._expected, head=0, tail=0, peer_claim=0, state=wire.STATES["init"])
        self.view.write(self.offset, struct.pack(wire.RING_FORMAT, *(values[key] for key in wire.RING_FIELDS)))

    def ready(self):
        self._write_field("state", "<I", wire.STATES["ready"])

    def quarantine(self):
        self._write_field("state", "<I", wire.STATES["quarantined"])
        self.resources.kernel.SetEvent(self.event)

    @contextmanager
    def locked(self, deadline):
        while True:
            result = self.resources.wait(self.mutex, deadline)
            if result != WAIT_TIMEOUT:
                break
        try:
            if result == WAIT_ABANDONED:
                self.quarantine()
                raise ProtocolError("abandoned SHM owner quarantined the generation")
            yield
        finally:
            check(self.resources.kernel.ReleaseMutex(self.mutex))

    def header(self, starting=False):
        value = dict(zip(wire.RING_FIELDS, struct.unpack(wire.RING_FORMAT,
            self.view.read(self.offset, wire.RING_SIZE))))
        if any(value[key] != expected for key, expected in self._expected.items()):
            self.quarantine()
            raise ProtocolError("SHM ring identity or admitted layout differs")
        permitted_claims = (0, 1) if self.name == "control" and self.direction == "agent_to_host" else (0,)
        if value["peer_claim"] not in permitted_claims:
            self.quarantine()
            raise ProtocolError("invalid SHM peer ownership claim")
        if not 0 <= value["tail"] <= value["head"] <= wire.LIMITS["max_sequence"] or value["head"] - value["tail"] > self.layout["slot_count"]:
            self.quarantine()
            raise ProtocolError("SHM ring counters are inconsistent")
        if starting and value["state"] == wire.STATES["init"]:
            raise _Starting()
        if value["state"] != wire.STATES["ready"]:
            raise ProtocolError("SHM ring is not ready")
        return value

    def finish(self, deadline):
        """Best-effort bounded close signal, even after the local stop flag.

        The independent control mutex remains available when a data ring fills.
        No view is unmapped until these owner-thread attempts have returned.
        """
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        result = self.resources.kernel.WaitForSingleObject(self.mutex, max(1, int(remaining * 1000)))
        if result in (WAIT_OBJECT_0, WAIT_ABANDONED):
            try:
                state = wire.STATES["quarantined"] if result == WAIT_ABANDONED else wire.STATES["closed"]
                current = struct.unpack("<I", self.view.read(self.offset + wire.RING_OFFSETS["state"], 4))[0]
                if current == wire.STATES["quarantined"]:
                    state = current
                self._write_field("state", "<I", state)
                self.resources.kernel.SetEvent(self.event)
            finally:
                check(self.resources.kernel.ReleaseMutex(self.mutex))

    def put(self, codec, packet, kind, deadline, service=None):
        # Encode once outside the mutex. Backpressure does not extend expiry.
        if self._sent >= wire.LIMITS["max_sequence"]:
            with self.locked(deadline):
                self._write_field("state", "<I", wire.STATES["draining"])
            raise ProtocolError("SHM sequence exhausted; a fresh generation is required")
        sequence = self._sent + 1
        frame = codec.encode(packet, self.name, self.direction, sequence, kind, deadline)
        while True:
            _remaining(deadline)
            if service is not None:
                service(deadline)
            with self.locked(deadline):
                header = self.header()
                if header["head"] != self._sent:
                    self.quarantine()
                    raise ProtocolError("SHM ring has more than one writer")
                full = header["head"] - header["tail"] == self.layout["slot_count"]
                if full and self.name == "quote":
                    # Only the dedicated quote slot may discard a complete old
                    # quote. Session/commands/critical facts cannot enter it.
                    self._write_field("tail", "<Q", header["tail"] + 1)
                    full = False
                if not full:
                    offset = self.offset + wire.RING_SIZE + (header["head"] % self.layout["slot_count"]) * self.layout["slot_bytes"]
                    self.view.write(offset, struct.pack(wire.SLOT_FORMAT, 0, wire.COMMITS["empty"], sequence))
                    self.view.write(offset + wire.SLOT_SIZE, frame)
                    self.view.write(offset, struct.pack(wire.SLOT_FORMAT, len(frame), wire.COMMITS["committed"], sequence))
                    self._write_field("head", "<Q", sequence)
                    self._sent = sequence
                    check(self.resources.kernel.SetEvent(self.event))
                    return
            self.resources.wait(self.event, deadline)

    def take(self, codec, deadline, *, wait=True, service=None):
        while True:
            _remaining(deadline)
            if service is not None:
                service(deadline)
            with self.locked(deadline):
                header = self.header()
                if header["head"] > header["tail"]:
                    offset = self.offset + wire.RING_SIZE + (header["tail"] % self.layout["slot_count"]) * self.layout["slot_bytes"]
                    length, commit, sequence = struct.unpack(wire.SLOT_FORMAT, self.view.read(offset, wire.SLOT_SIZE))
                    if (commit != wire.COMMITS["committed"] or sequence != header["tail"] + 1
                            or not wire.FRAME_SIZE < length <= self.layout["slot_bytes"] - wire.SLOT_SIZE):
                        self.quarantine()
                        raise ProtocolError("SHM slot is incomplete or its sequence/length differs")
                    frame = self.view.read(offset + wire.SLOT_SIZE, length)
                    self.view.write(offset, struct.pack(wire.SLOT_FORMAT, 0, wire.COMMITS["empty"], sequence))
                    self._write_field("tail", "<Q", sequence)
                    check(self.resources.kernel.SetEvent(self.event))
                    break
            if not wait:
                return None
            self.resources.wait(self.event, deadline)
        try:
            return codec.decode(frame, self.name, self.direction, sequence)
        except Exception:
            with self.locked(deadline):
                self.quarantine()
            raise


class SharedMemoryFramer(object):
    """Original Session packets over private control bootstrap and data rings."""
    def __init__(self, resources, rings, peer, generation, role, secret):
        self.resources, self.rings, self.peer = resources, rings, peer
        self.generation, self.role = generation, role
        self.codec = FrameCodec(resources.profile, generation, secret, clock=lambda: utc_now(resources.kernel))
        self._authenticated = False
        self._closed = False

    def _direction(self, outbound):
        return "host_to_agent" if (self.role == "host") == outbound else "agent_to_host"

    def _owner(self):
        if threading.get_ident() != self.resources.owner:
            raise RuntimeError("SHM channel I/O belongs to its original worker")

    def _control(self, outbound):
        return self.rings[("control", self._direction(outbound))]

    def _data(self, outbound):
        direction = self._direction(outbound)
        return self.rings[("command" if direction == "host_to_agent" else "reliable", direction)]

    def wait_peer(self, deadline):
        """Host I/O owner waits for this generation's existing one-way claim.

        deadline is the caller's absolute monotonic connection expiry. A claim
        proves arrival only; Session still authenticates under its I/O budget.
        Header validation, stop and polling use the original ring owner rules.
        """
        self._owner()
        if self.role != "host" or self._authenticated or self._closed:
            raise ProtocolError("SHM peer arrival requires an open Host bootstrap")
        ring = self._control(False)
        while True:
            with ring.locked(deadline):
                if ring.header()["peer_claim"] == 1:
                    return
            self.resources.wait(ring.event, deadline)

    def authenticated(self, generation):
        self._owner()
        if generation != self.generation or self._authenticated:
            raise ProtocolError("SHM Session generation differs from its mapping")
        self._authenticated = True

    def _service(self, deadline):
        control = self._control(False).take(self.codec, deadline, wait=False)
        if control is not None:
            unused_packet, kind = control
            # Post-handshake control has no business payload or Session seq.
            # Even a well-signed unexpected control kind closes this binding.
            raise ProtocolError("SHM peer control: " + kind)

    def send(self, value, deadline):
        self._owner()
        packet = canonical(value)
        if self._authenticated:
            ring = self._data(True)
            ring.put(self.codec, packet, "REQUEST" if self.role == "host" else "RESULT", deadline, self._service)
        else:
            self._control(True).put(self.codec, packet, "HELLO" if self.role == "host" else "HELLO_ACK", deadline)

    def receive(self, deadline):
        self._owner()
        ring = self._data(False) if self._authenticated else self._control(False)
        value, unused_kind = ring.take(self.codec, deadline, service=self._service if self._authenticated else None)
        return value

    def send_control(self, kind, deadline):
        """Independent control never advances or reorders the business Session."""
        self._owner()
        if not self._authenticated or kind not in ("DRAIN", "ERROR"):
            raise ProtocolError("invalid post-handshake SHM control")
        self._control(True).put(self.codec, canonical({"kind": kind}), kind, deadline)

    def request_close(self):
        self.resources.stop.set()

    def close(self):
        if threading.get_ident() != self.resources.owner:
            self.request_close()
            return
        if self._closed:
            return
        # Dispose only in the I/O owner, after the final copy/wait returned.
        self.request_close()
        try:
            deadline = time.monotonic() + wire.LIMITS["close_signal_seconds"]
            for ring in self.rings.values():
                ring.finish(deadline)
        finally:
            try:
                self.codec.close()
            finally:
                self.resources.dispose()
                self._closed = self.resources._disposed


def _rings(resources, create, deadline, generation=None):
    """Create all resources before READY; an opener trusts only fixed bounds."""
    profile = resources.profile
    base = profile.base_name
    bootstrap = resources.mapping(base + "-bootstrap-map", 2 * profile.control_unit_bytes, create)
    peer = resources.mutex(base + "-peer-mutex", create)
    controls = []
    for index, direction in enumerate(("host_to_agent", "agent_to_host")):
        stem = base + "-control-" + direction
        mutex, event = resources.mutex(stem + "-mutex", create), resources.event(stem + "-event", create)
        controls.append((index * profile.control_unit_bytes, mutex, event, direction))
    if not create:
        # Copy only the fixed header to learn the random name suffix, then
        # validate it under its own Mutex before deriving/opening data objects.
        while True:
            acquired = resources.wait(controls[0][1], deadline)
            if acquired != WAIT_TIMEOUT:
                break
        try:
            if acquired == WAIT_ABANDONED:
                bootstrap.write(wire.RING_OFFSETS["state"], struct.pack("<I", wire.STATES["quarantined"]))
                raise ProtocolError("abandoned SHM bootstrap owner")
            first = bootstrap.read(0, wire.RING_SIZE)
        finally:
            check(resources.kernel.ReleaseMutex(controls[0][1]))
        if first == b"\0" * wire.RING_SIZE:
            raise _Starting()
        raw = dict(zip(wire.RING_FIELDS, struct.unpack(wire.RING_FORMAT, first)))
        generation = raw["generation"].hex()
    rings = {}
    for offset, mutex, event, direction in controls:
        ring = Ring(resources, bootstrap, offset, mutex, event, "control", direction, generation)
        rings[("control", direction)] = ring
        if not create:
            with ring.locked(deadline):
                ring.header(starting=True)
    for name, direction in (("command", "host_to_agent"), ("reliable", "agent_to_host"), ("quote", "agent_to_host")):
        stem = base + "-" + generation + "-" + name
        view = resources.mapping(stem + "-map", profile.layout(name, direction)["mapped_bytes"], create)
        rings[(name, direction)] = Ring(resources, view, 0, resources.mutex(stem + "-mutex", create),
            resources.event(stem + "-event", create), name, direction, generation)
    if create:
        for ring in rings.values():
            with ring.locked(deadline):
                ring.initialize()
        for ring in sorted(rings.values(), key=lambda value: value.name == "control"):
            with ring.locked(deadline):
                ring.ready()
    return rings, peer, generation


class SharedMemoryListener(object):
    """Pure constructor; the same stop Event reaches the original I/O worker."""
    def __init__(self, profile, secret, stop=None):
        self.profile, self.secret = profile, secret
        self.stop = stop if stop is not None else threading.Event()
        self._guard = threading.Lock()
        self._resources, self._framer = None, None
        self._accepted, self._accepting = False, False

    @property
    def io_resources_closed(self):
        return (not self._accepting and (self._resources is None or
            self._resources._disposed and self._resources._security_resources.closed))

    def accept(self, deadline):
        _remaining(deadline)
        with self._guard:
            if self._accepted or self.stop.is_set():
                raise OSError("SHM listener has one generation")
            self._accepted, self._accepting = True, True
        resources = None
        try:
            resources = _Resources(self.profile, self.stop)
            self._resources = resources
            if self.stop.is_set():
                raise OSError("SHM listener is closing")
            generation = uuid4().hex
            rings, peer, generation = _rings(resources, True, deadline, generation)
            self._framer = SharedMemoryFramer(resources, rings, peer, generation, "host", self.secret)
            return self._framer
        except BaseException:
            if resources is not None:
                try:
                    resources.dispose()
                except BaseException:
                    pass  # _resources保留失败字段，原异常继续上抛。
            raise
        finally:
            self._accepting = False

    def close(self):
        self.stop.set()


def connect(profile, secret, deadline, stop=None, resource_owner=None):
    """Open one trusted generation; no automatic fallback, replay or reconnect."""
    stop = stop if stop is not None else threading.Event()
    while True:
        _remaining(deadline)
        resources = _Resources(profile, stop)
        if resource_owner is not None:
            resource_owner(resources)
        try:
            rings, peer, generation = _rings(resources, False, deadline)
            result = resources.kernel.WaitForSingleObject(peer, 0)
            if result == WAIT_TIMEOUT:
                raise ProtocolError("SHM generation already has an Agent I/O owner")
            if result not in (WAIT_OBJECT_0, WAIT_ABANDONED):
                raise ctypes.WinError(ctypes.get_last_error())
            resources.peer_owned = peer
            if result == WAIT_ABANDONED:
                for ring in rings.values():
                    with ring.locked(deadline):
                        ring.quarantine()
                raise ProtocolError("abandoned SHM Agent owner requires a fresh generation")
            for ring in rings.values():
                with ring.locked(deadline):
                    ring.header()
            claimed = rings[("control", "agent_to_host")]
            with claimed.locked(deadline):
                if claimed.header()["peer_claim"] != 0:
                    raise ProtocolError("SHM generation already claimed by an Agent")
                # A native Mutex is recursive on the same thread and becomes
                # available after normal release. The one-way shared claim
                # prevents either path from reattaching to an old generation.
                claimed._write_field("peer_claim", "<I", 1)
            # The claim is authoritative; wake the Host's existing arrival
            # wait promptly even when its polling interval exceeds I/O time.
            check(resources.kernel.SetEvent(claimed.event))
            return SharedMemoryFramer(resources, rings, peer, generation, "agent", secret)
        except (OSError, _Starting) as exc:
            try:
                resources.dispose()
            except BaseException:
                raise exc  # 上层已持resources；清理失败不能转成下一次探测。
            # A not-yet-created Host can appear within the same connect budget.
            # Permission/ownership/corruption faults never choose another path.
            if not isinstance(exc, _Starting) and getattr(exc, "winerror", None) != 2:
                raise
            if stop.wait(min(profile.poll_seconds, _remaining(deadline))):
                raise OSError("SHM connector is closing")
        except BaseException:
            try:
                resources.dispose()
            except BaseException:
                pass
            raise
