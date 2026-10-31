# -*- coding: utf-8 -*-
"""Bounded memory RPC state; one I/O owner, nonblocking domain futures.

Transport, durable journals and native execution retain their own owners. This
module never waits, calls a handler, reconnects or decides execution authority.
Canonical copies and validation happen outside the strategy-shared memory lock.
"""
import threading
import time

from . import control_wire as wire
from .control_messages import digest, sequence, validate_message, validate_packet
from .control_profile import ControlProfile
from .timestamps import source_timestamp
from .protocol import ProtocolError, Session, canonical, decode


def _failure(code):
    return canonical({"ok": False, "payload": None, "error": {"code": code, "message": code}})


class ControlFuture(object):
    """One delivery; the consumer acknowledges only after its domain commit."""
    def __init__(self, peer):
        self._peer = peer
        self._value, self._taken, self._acknowledged, self._retired = None, False, False, False
        self._delivery = "queued"
        self._take_lease = None

    @property
    def delivery(self):
        with self._peer._lock:
            return self._delivery

    @property
    def retired(self):
        with self._peer._lock:
            return self._retired

    def take(self):
        """完整构造结果后才完成交付；失败保留原值且仍禁止 ACK。"""
        lease = object()
        try:
            with self._peer._lock:
                if self._value is None or self._taken or self._take_lease is not None:
                    return None
                value, delivery = self._value, self._delivery
                self._take_lease = lease
            # 解码及返回字典分配均在锁外；同步重入和另一消费者只看到领取中。
            result = decode(value)
            delivered = {"ok": result["ok"], "payload": result["payload"],
                "error": result["error"], "delivery": delivery}
            with self._peer._lock:
                if self._take_lease is not lease or self._value is not value or self._taken:
                    return None
                # close 保留的原终态仍可交付；这里不重建已退休的 outgoing 条目。
                self._taken = True
            return delivered
        finally:
            # 包括 MemoryError/KeyboardInterrupt；清理只释放本次领取身份。
            with self._peer._lock:
                if self._take_lease is lease:
                    self._take_lease = None

    def ack(self):
        self._peer._ack(self)


class _ReplyAckReceipt(object):
    """一个缓存成功回复的确认事实；只保留锁与固定身份。

    pending 由源端验证 ACK 后变为 acknowledged，close 时变为 abandoned。
    该对象不保存 payload 或 peer，也不自行授予 Host 持久化资格。
    """
    __slots__ = ("_lock", "_identity", "_state")

    def __init__(self, lock, generation, call_seq, request_sha256, reply_sha256):
        self._lock = lock
        self._identity = (generation, call_seq, request_sha256, reply_sha256)
        self._state = "pending"

    @property
    def generation(self):
        return self._identity[0]

    @property
    def call_seq(self):
        return self._identity[1]

    @property
    def request_sha256(self):
        return self._identity[2]

    @property
    def reply_sha256(self):
        return self._identity[3]

    @property
    def state(self):
        with self._lock:
            return self._state


class _Batch(object):
    """Opaque selection receipt; changing the caller's packet cannot alter it."""
    def __init__(self, packet, selected):
        self._encoded, self.selected = canonical(packet), tuple(selected)

    @property
    def packet(self):
        return decode(self._encoded)


class ControlPeer(object):
    """Strict ordered cycles and two independently bounded call windows.

    A whole CALL/maximum REPLY/receipt reservation remains charged until its
    contiguous retirement watermark advances. Retired gaps thus consume both
    window and byte capacity. Both peers derive the same fixed caller-role
    quotas from the authenticated profile. Local queued calls cannot borrow
    the other role's independently usable credit. All state transitions share
    one short memory lock.
    """
    def __init__(self, role, generation, profile, monotonic=None, utc_seconds=None):
        if role not in wire.PACKET_KINDS or not isinstance(profile, ControlProfile):
            raise ValueError("control peer requires a trusted role and profile")
        Session._nonce(generation)
        self.role, self.generation, self.profile = role, generation, profile
        self.remote = "agent" if role == "host" else "host"
        self._mono, self._utc = monotonic or time.monotonic, utc_seconds or time.time
        self._lock = threading.Lock()
        self._out, self._incoming = {}, {}
        self._out_next, self._in_next = 1, 1
        self._out_floor, self._in_floor = 0, 0
        self._out_gaps, self._in_gaps = set(), set()
        self._cycle, self._phase = 1, "send" if role == "host" else "receive"
        self._batch, self._closed, self._turn = None, False, "CALL"
        self._slots = (profile.call_slots(self.role), profile.call_slots(self.remote))

    def _charge(self, outgoing, incoming_next, incoming_floor):
        queued = sum(entry["seq"] is None for entry in outgoing.values())
        return self._out_next - self._out_floor - 1 + queued, incoming_next - incoming_floor - 1

    def _capacity(self, counts, direction):
        if counts[direction] + 1 > self._slots[direction]:
            raise BufferError("control call window or retained bytes are full")

    def _open(self):
        if self._closed:
            raise OSError("control binding is closed")

    def can_submit(self):
        """Advisory local credit check; submit remains the admission owner.

        The Host's sole outgoing owner checks before a durable Journal claim or
        another observation poll. Completed gaps still occupy this quota until
        the oldest outstanding call retires. No credit is reserved by this read.
        """
        with self._lock:
            self._open()
            return self._charge(self._out, self._in_next, self._in_floor)[0] < self._slots[0]

    def has_incoming(self, operation):
        """查询尚保留的同类CALL；已缓存结果在对端ACK前继续计入交接。

        原bytes在短锁内捕获，有限解码在锁外；查询不推进退休或信用额度。
        receive仍只由原I/O owner调用，跨线程close只会使查询更保守。
        """
        if type(operation) is not str or operation not in self.profile.contract.OPERATION_CALLERS:
            raise ValueError('explicit control operation required')
        with self._lock:
            self._open()
            values = tuple(entry['call'] for entry in self._incoming.values())
        found = any(decode(value)['operation'] == operation for value in values)
        with self._lock:
            self._open()
            if values != tuple(entry['call'] for entry in self._incoming.values()):
                raise ProtocolError('control CALL ownership changed during query')
            return found

    def retained_reply_matches(self, call_seq, payload):
        """确认实际缓存的成功原文；reply=True也可能只缓存了过期错误。

        不重放或修改缓存；构造/解码失败向owner传播，不能授正常交接。
        """
        sequence(call_seq)
        expected = canonical(payload)
        with self._lock:
            entry = self._incoming.get(call_seq)
            value = None if entry is None else entry['reply']
        if value is None:
            return False
        reply = decode(value)
        matches = (reply['ok'] is True and reply['error'] is None
                   and canonical(reply['payload']) == expected)
        with self._lock:
            current = self._incoming.get(call_seq)
            return (not self._closed and current is not None
                    and current['reply'] is value and matches)

    def observe_reply_ack(self, call_seq, payload):
        """观察同一成功缓存的真实 ACK，普通路径不分配额外收据。

        返回 None 或一个稳定收据；全包 ACK 验证提交前始终 pending。
        有限编码/解码及候选构造在锁外，发布时重核原 bytes 及 open。
        """
        sequence(call_seq)
        expected = canonical(payload)
        with self._lock:
            entry = self._incoming.get(call_seq)
            value = None if entry is None else entry["reply"]
        if value is None:
            return None
        reply = decode(value)
        if (reply["ok"] is not True or reply["error"] is not None
                or canonical(reply["payload"]) != expected):
            return None
        candidate = _ReplyAckReceipt(self._lock, self.generation, call_seq,
            reply["request_sha256"], digest(reply))
        with self._lock:
            current = self._incoming.get(call_seq)
            if self._closed or current is None or current["reply"] is not value:
                return None
            receipt = current.get("ack_receipt")
            if receipt is None:
                current["ack_receipt"] = receipt = candidate
            return receipt

    def submit(self, operation, payload, expires_at):
        """Trusted fixed operation, with one original aware absolute deadline.

        Reserve the longest possible sequence representation before admission;
        the real wire sequence is assigned only when an I/O batch selects it.
        """
        started = self._mono()
        remaining = source_timestamp(expires_at).timestamp() - self._utc()
        if not 0 < remaining <= self.profile.max_call_seconds:
            raise ValueError("control call has expired or exceeds its original lifetime")
        call = {"kind": "CALL", "call_seq": wire.CONSTANTS["max_sequence"],
            "operation": operation, "expires_at": expires_at, "payload": payload}
        validate_message(call, self.profile, self.role)
        encoded = canonical(call)
        deadline = started + remaining
        future = ControlFuture(self)
        with self._lock:
            self._open()
            self._capacity(self._charge(self._out, self._in_next, self._in_floor), 0)
            self._out[future] = {"seq": None, "call": encoded, "request_sha256": None,
                "reply_sha256": None, "deadline": deadline, "state": "queued", "ack": False}
        return future

    @staticmethod
    def _retire(number, floor, gaps):
        gaps.add(number)
        while floor + 1 in gaps:
            floor += 1
            gaps.remove(floor)
        return floor

    def _ack(self, future):
        with self._lock:
            if not future._taken:
                raise RuntimeError("control result must be consumed before acknowledgement")
            if future._acknowledged:
                return
            entry = self._out.get(future)
            if entry is None:
                future._acknowledged = True
                return
            number, reply_hash = entry["seq"], entry["reply_sha256"]
        encoded = canonical({"kind": "ACK", "call_seq": number, "reply_sha256": reply_hash})
        with self._lock:
            if future._acknowledged:
                return
            future._acknowledged = True
            entry = self._out.get(future)
            if entry is not None:
                entry["ack"], entry["ack_bytes"] = True, encoded

    def prepare(self, last_tick=None):
        """Select before I/O: every chosen CALL is already delivery-uncertain.

        The fixed overhead covers packet fields, delimiters and bounded tick.
        No raw message may exceed its own complete byte cap. ACKs have priority;
        CALLs and retained REPLYs alternate, with unsent replies before repeats.
        """
        self.expire()
        selected, encoded, allocated = [], [], []
        used = wire.CONSTANTS["cycle_overhead_bytes"]
        with self._lock:
            cycle = self._cycle
        validate_packet({"kind": wire.PACKET_KINDS[self.role], "schema_version": self.profile.version,
            "generation": self.generation, "cycle_seq": cycle, "last_tick": last_tick, "messages": []},
            self.profile, self.role, self.generation, cycle)
        with self._lock:
            self._open()
            if self._phase != "send" or self._batch is not None:
                raise RuntimeError("control cycle is not ready for a new send selection")
            acks = [("ACK", future, entry) for future, entry in self._out.items() if entry["ack"]]
            calls = [("CALL", future, entry) for future, entry in self._out.items() if entry["state"] == "queued"]
            replies = [("REPLY", number, entry) for number, entry in self._incoming.items() if entry["reply"] is not None]
            replies.sort(key=lambda item: item[2]["sent"])
            queues = {"CALL": calls, "REPLY": replies}
            candidates = list(acks)
            turn = self._turn
            while calls or replies:
                kind = turn if queues[turn] else ("REPLY" if turn == "CALL" else "CALL")
                candidates.append(queues[kind].pop(0))
                turn = "REPLY" if kind == "CALL" else "CALL"
            for kind, reference, entry in candidates:
                if kind == "ACK":
                    value = entry["ack_bytes"]
                else:
                    value = entry["call"] if kind == "CALL" else entry["reply"]
                if len(encoded) >= self.profile.max_cycle_messages:
                    break
                if used + len(value) > self.profile.max_cycle_bytes:
                    continue
                number = None
                if kind == "CALL":
                    sequence(self._out_next)
                    number = self._out_next
                    self._out_next += 1
                    entry["seq"], entry["state"] = number, "sending"
                    reference._delivery = "sending"
                encoded.append(value)
                allocated.append(number)
                used += len(value)
                selected.append((kind, reference))
                if kind in ("CALL", "REPLY"):
                    self._turn = "REPLY" if kind == "CALL" else "CALL"
            cycle = self._cycle
            # Reserve the send phase before releasing the memory lock.
            self._batch = selected
        # Selection accounts for the maximum-width sequence template. Actual
        # substitution, public encoding and hashing all run outside the lock;
        # strategy close can complete even while these operations are paused.
        encoded = [value if number is None else value.replace(b'"call_seq":18446744073709551615',
            b'"call_seq":' + str(number).encode("ascii"), 1) for value, number in zip(encoded, allocated)]
        messages = [decode(value) for value in encoded]
        packet = {"kind": wire.PACKET_KINDS[self.role], "schema_version": self.profile.version,
            "generation": self.generation, "cycle_seq": cycle, "last_tick": last_tick, "messages": messages}
        packet = validate_packet(packet, self.profile, self.role, self.generation, cycle)
        hashes = [(reference, digest(message), value) for (kind, reference), message, value in zip(selected, messages, encoded) if kind == "CALL"]
        batch = _Batch(packet, selected)
        with self._lock:
            self._open()
            for future, request_hash, value in hashes:
                self._out[future]["request_sha256"] = request_hash
                self._out[future]["call"] = value
            self._batch = batch
        return batch

    def sent(self, batch):
        """Only a completed Session.send permits ACK retirement or sent state."""
        with self._lock:
            self._open()
            if self._batch is not batch:
                raise RuntimeError("control send receipt differs from the selected batch")
            for kind, reference in batch.selected:
                if kind == "CALL":
                    self._out[reference]["state"] = "sent"
                    reference._delivery = "sent"
                elif kind == "REPLY":
                    self._incoming[reference]["sent"] = True
                else:
                    entry = self._out.pop(reference)
                    reference._value = None
                    reference._retired = True
                    self._out_floor = self._retire(entry["seq"], self._out_floor, self._out_gaps)
            self._batch, self._phase = None, "receive"
            if self.role == "agent":
                self._cycle += 1

    def receive(self, value):
        """Validate grammar and every contextual transition before publication."""
        self.expire()
        with self._lock:
            self._open()
            cycle = self._cycle
        checked = validate_packet(value, self.profile, self.remote, self.generation, cycle)
        now, utc = self._mono(), self._utc()
        prepared = []
        for message in checked["messages"]:
            encoded = canonical(message)
            remaining = (min(self.profile.max_call_seconds, source_timestamp(message["expires_at"]).timestamp() - utc)
                if message["kind"] == "CALL" else 0)
            prepared.append((message, encoded, digest(message), now + remaining))
        with self._lock:
            self._open()
            if self._phase != "receive" or self._cycle != cycle:
                raise ProtocolError("control cycle is not ready for this response")
            incoming = {number: dict(entry) for number, entry in self._incoming.items()}
            outgoing = {future: dict(entry) for future, entry in self._out.items()}
            by_seq = {entry["seq"]: (future, entry) for future, entry in outgoing.items() if entry["seq"] is not None}
            in_next, in_floor, in_gaps = self._in_next, self._in_floor, set(self._in_gaps)
            deliveries, acknowledgements = [], []
            for message, encoded, message_hash, deadline in prepared:
                kind, number = message["kind"], message["call_seq"]
                if kind == "CALL":
                    old = incoming.get(number)
                    if old is not None:
                        if old["request_sha256"] != message_hash:
                            raise ProtocolError("active control CALL content differs")
                        continue
                    if number != in_next or number > in_floor + self.profile.max_pending_calls:
                        raise ProtocolError("control CALL is retired or outside its consecutive window")
                    try:
                        self._capacity(self._charge(outgoing, in_next, in_floor), 1)
                    except BufferError as exc:
                        raise ProtocolError("incoming control reservation exceeds its bound") from exc
                    incoming[number] = {"call": encoded, "request_sha256": message_hash,
                        "deadline": deadline, "taken": False, "lease": None, "reply": None, "reply_sha256": None, "sent": False}
                    in_next += 1
                elif kind == "REPLY":
                    found = by_seq.get(number)
                    if found is None:
                        raise ProtocolError("control REPLY is retired or has no selected request")
                    future, entry = found
                    if entry["state"] not in ("sent", "completed") or entry["request_sha256"] != message["request_sha256"]:
                        raise ProtocolError("control REPLY differs from the sent request")
                    if entry["reply_sha256"] is not None:
                        if entry["reply_sha256"] != message_hash:
                            raise ProtocolError("duplicate control REPLY content differs")
                        continue
                    entry["state"], entry["reply_sha256"] = "completed", message_hash
                    deliveries.append((future, encoded))
                else:
                    entry = incoming.get(number)
                    if entry is None or not entry["sent"] or entry["reply_sha256"] != message["reply_sha256"]:
                        raise ProtocolError("control ACK lacks a matching retained sent REPLY")
                    receipt = entry.get("ack_receipt")
                    if receipt is not None:
                        acknowledgements.append(receipt)
                    del incoming[number]
                    in_floor = self._retire(number, in_floor, in_gaps)
            self._incoming, self._out = incoming, outgoing
            self._in_next, self._in_floor, self._in_gaps = in_next, in_floor, in_gaps
            # 全包已验证；确认与退休在同一次锁内发布，不回调业务 owner。
            for receipt in acknowledgements:
                receipt._state = "acknowledged"
            for future, encoded in deliveries:
                future._value, future._delivery = encoded, "replied"
            self._phase = "send"
            if self.role == "host":
                self._cycle += 1
        return checked["last_tick"]

    def take_call(self):
        """Return one private domain request; duplicate CALLs never requeue it."""
        return self._take_call(False)

    def take_call_with_deadline(self):
        """交给交易队列原 wire 与首次映射的本地 D，避免取出时重启期限。

        与 take_call 共用一个 taken 标记；值复制在锁外完成，不调用 SDK。
        返回 None 或 (call dict, deadline 秒)，本方法不创造业务准入事实。
        """
        return self._take_call(True)

    def _take_call(self, include_deadline):
        self.expire()
        lease, number = object(), None
        try:
            with self._lock:
                self._open()
                for number, entry in self._incoming.items():
                    if not entry["taken"] and entry["lease"] is None and entry["reply"] is None:
                        encoded, deadline = entry["call"], entry["deadline"]
                        entry["lease"] = lease
                        break
                else:
                    return None
            value = decode(encoded)
            delivered = (value, deadline) if include_deadline else value
            # 构造期间原 D 可能耗尽；原过期处理负责回执，迟到领取不能派发。
            self.expire()
            with self._lock:
                current = self._incoming.get(number)
                if (self._closed or current is None or current["lease"] is not lease
                        or current["taken"] or current["reply"] is not None):
                    return None
                # receive 浅复制条目仍保留同一令牌；close/ACK 删除后绝不重建。
                current["taken"] = True
            return delivered
        finally:
            with self._lock:
                current = self._incoming.get(number)
                if current is not None and current["lease"] is lease:
                    current["lease"] = None

    def reply(self, call_seq, payload=None, error=None):
        """One reply cache; late domain completion cannot replace expiry."""
        sequence(call_seq)
        with self._lock:
            self._open()
            entry = self._incoming.get(call_seq)
            if entry is None:
                raise ProtocolError("control reply has no admitted CALL")
            request_hash, deadline = entry["request_sha256"], entry["deadline"]
        if self._mono() >= deadline:
            payload, error = None, {"code": "call_expired", "message": "call_expired"}
        message = {"kind": "REPLY", "call_seq": call_seq, "request_sha256": request_hash,
            "ok": error is None, "payload": payload, "error": error}
        validate_message(message, self.profile, self.role)
        encoded, reply_hash = canonical(message), digest(message)
        with self._lock:
            self._open()
            entry = self._incoming.get(call_seq)
            if entry is None or entry["request_sha256"] != request_hash:
                raise ProtocolError("control CALL retired during domain completion")
            if entry["reply"] is not None:
                return False
            entry["reply"], entry["reply_sha256"] = encoded, reply_hash
        return True

    def expire(self):
        """Queued timeouts retire locally; an uncertain timeout closes binding."""
        now = self._mono()
        failure = _failure("call_expired")
        with self._lock:
            if self._closed:
                return
            uncertain = any(entry["deadline"] <= now and entry["state"] in ("sending", "sent") for entry in self._out.values())
            if not uncertain:
                for future, entry in list(self._out.items()):
                    if entry["deadline"] <= now and entry["state"] == "queued":
                        future._value, future._delivery = failure, "not_sent"
                        future._retired = True
                        del self._out[future]
            expired = [number for number, entry in self._incoming.items() if entry["deadline"] <= now and entry["reply"] is None]
        if uncertain:
            self.close()
            return
        for number in expired:
            self.reply(number, error={"code": "call_expired", "message": "call_expired"})

    def close(self):
        """Complete every future without inventing native no-call proof."""
        failure = _failure("binding_closed")
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for future, entry in self._out.items():
                future._retired = True
                if future._value is None:
                    future._value = failure
                    future._delivery = "not_sent" if entry["state"] == "queued" else "unknown"
            for entry in self._incoming.values():
                receipt = entry.get("ack_receipt")
                if receipt is not None:
                    receipt._state = "abandoned"
            self._out.clear()
            self._incoming.clear()
            self._batch = None
