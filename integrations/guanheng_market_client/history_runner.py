"""Operations-owned, explicitly stepped history acquisition; no job database.

The injected calendar/evidence owners supply authoritative facts. Network clients
perform one bounded exchange; this runner never creates/resumes production jobs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time as day_time, timedelta, timezone
import hashlib
import http.client
import io
import ipaddress
import json
import math
import re
import ssl
import threading
import time
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID, NAMESPACE_URL, uuid5

from . import API_VERSION, MarketHTTPError, MarketUnavailable, strict_json, validate_response

__all__ = ["HistoryBinding", "CalendarSlice", "CalendarProvider", "EvidenceSink", "StepResult", "CloseResult",
    "OperationsUnavailable", "OperationsConflict", "OperationsClient", "HistoryRunner", "canonical_bytes", "digest", "validate_job"]

SHANGHAI = timezone(timedelta(hours=8))


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _text(value, limit=256):
    return type(value) is str and 0 < len(value) <= limit and all(ord(c) >= 32 for c in value)


def _instant(value):
    if not isinstance(value, str):
        raise ValueError("history timestamp invalid")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("history timestamp requires timezone")
    return result


@dataclass(frozen=True)
class HistoryBinding:
    agent_id: str
    profile_version: str
    calendar_version: str
    source_license: str
    volume_to_shares: float
    amount_to_yuan: float
    provider: str = "Qmt"
    price_unit: str = "CNY"
    volume_unit: str = "share"
    amount_unit: str = "CNY"
    minute_boundary: str = "right"
    timezone: str = "Asia/Shanghai"

    def __post_init__(self):
        if (self.provider != "Qmt" or (self.price_unit, self.volume_unit, self.amount_unit) != ("CNY", "share", "CNY")
                or self.minute_boundary != "right" or self.timezone != "Asia/Shanghai"
                or any(not _text(value) for value in (self.agent_id, self.profile_version, self.calendar_version, self.source_license))):
            raise ValueError("history binding invalid")
        for value in (self.volume_to_shares, self.amount_to_yuan):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("history source units invalid")

    @property
    def sha256(self):
        return digest(asdict(self))

    @property
    def dataset_version(self):
        return "wt-qmt-1m-" + self.sha256[:32]


@dataclass(frozen=True)
class CalendarSlice:
    version: str
    expected_minutes: tuple[int, ...]
    authoritative_empty: bool = False
    evidence_ref: str = ""


class CalendarProvider(Protocol):
    def minutes(self, symbol: str, start_date: date, end_date: date, as_of: datetime) -> CalendarSlice: ...


class EvidenceSink(Protocol):
    # Immutable content address: repeated put of identical bytes returns the same
    # reference; get takes the SHA-256, not a local path supplied by the job.
    def put(self, sha256: str, canonical: bytes) -> str: ...
    def get(self, sha256: str) -> bytes: ...


@dataclass(frozen=True)
class StepResult:
    status: str
    job_id: str
    confirmed_segments: int = 0
    reason: str = ""
    result_ref: str | None = None


@dataclass(frozen=True)
class CloseResult:
    """本地排空观察；pending_task 表示已知身份，recovery_required 表示未知准备遗留。

    后两项均为 False 才能确认资源排空；status 不表示 Operations 作业停止或成功。
    reason 为固定诊断，不包含任务身份、凭据或远端正文。
    """
    status: str
    pending_task: bool = False
    recovery_required: bool = False
    reason: str = ""


class OperationsUnavailable(RuntimeError):
    pass


class OperationsConflict(OperationsUnavailable):
    pass


def validate_job(value, job_id):
    """Validate original v1 shape/hash without importing a private QMT package."""
    if type(value) is not dict or type(value.get("spec")) is not dict:
        raise ValueError("history job invalid")
    spec = value["spec"]
    expected = {"schema_version", "job_id", "dataset_version", "symbols", "start_date", "end_date", "as_of", "period", "segment_days", "count", "min_bars", "agent_id", "policy_id"}
    if set(spec) != expected or spec["schema_version"] != "1.0" or str(UUID(spec["job_id"])) != str(UUID(str(job_id))):
        raise ValueError("history job identity invalid")
    if value.get("schema_version") != "1.0" or value.get("request_sha256") != digest({k: v for k, v in spec.items() if k != "job_id"}):
        raise ValueError("history job binding hash invalid")
    symbols = spec["symbols"]
    if (type(symbols) is not list or not 1 <= len(symbols) <= 20 or symbols != sorted(set(symbols))
            or any(type(s) is not str or not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", s) for s in symbols)):
        raise ValueError("history symbols invalid")
    if date.fromisoformat(spec["start_date"]) > date.fromisoformat(spec["end_date"]):
        raise ValueError("history dates invalid")
    _instant(spec["as_of"])
    _instant(value["updated_at"])
    for name, maximum in (("segment_days", 366), ("count", 5000), ("min_bars", 5000)):
        if type(spec[name]) is not int or not 1 <= spec[name] <= maximum:
            raise ValueError("history job budget invalid")
    if spec["min_bars"] > spec["count"] or not _text(spec["dataset_version"], 128):
        raise ValueError("history job counts invalid")
    status = value.get("status")
    if status not in ("queued", "running", "stop_requested", "stopped", "succeeded", "failed") or type(value.get("stop_requested")) is not bool:
        raise ValueError("history job lifecycle invalid")
    checkpoints = value.get("checkpoints")
    if type(checkpoints) is not list or len(checkpoints) > 10000:
        raise ValueError("history checkpoints invalid")
    identities = set()
    for item in checkpoints:
        if type(item) is not dict or item.get("status") not in ("confirmed", "failed"):
            raise ValueError("history checkpoint invalid")
        identity = (item.get("symbol"), item.get("start_date"), item.get("end_date"))
        if identity in identities:
            raise ValueError("history checkpoint repeated")
        identities.add(identity)
        if item["status"] == "confirmed" and (type(item.get("result_sha256")) is not str or not re.fullmatch(r"[0-9a-f]{64}", item["result_sha256"])):
            raise ValueError("history checkpoint hash invalid")
        if type(item.get("bar_count")) is not int or item["bar_count"] < 0:
            raise ValueError("history checkpoint count invalid")
        UUID(item["request_id"])
    if value.get("completed_segments") != sum(c["status"] == "confirmed" for c in checkpoints):
        raise ValueError("history completed count invalid")
    if type(value.get("remaining_segments")) is not int or value["remaining_segments"] < 0:
        raise ValueError("history remaining count invalid")
    if (status in ("stopped", "succeeded", "failed")) != (value.get("completed_at") is not None):
        raise ValueError("history completion invalid")
    if status == "succeeded" and not _text(value.get("result_ref"), 2048):
        raise ValueError("history result reference invalid")
    return value


class _DeadlineRaw(io.RawIOBase):
    def __init__(self, raw, sock, deadline):
        self.raw, self.sock, self.deadline = raw, sock, deadline

    def readable(self):
        return True

    def readinto(self, buffer):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        self.sock.settimeout(remaining)
        chunk = self.raw.read1(min(len(buffer), 65536))
        if time.monotonic() >= self.deadline:
            raise TimeoutError
        buffer[:len(chunk)] = chunk
        return len(chunk)

    def close(self):
        if not self.closed:
            try:
                self.raw.close()
            finally:
                super().close()


class OperationsClient:
    """Single GET/PUT exchanges only; no create/resume/stop or automatic retry."""
    def __init__(self, base_url, token, *, timeout=5.0, max_response_bytes=4 * 1024 * 1024):
        try:
            url = urlsplit(base_url)
            if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
                    or url.path not in ("", "/") or url.query or url.fragment
                    or (url.scheme == "http" and not ipaddress.ip_address(url.hostname).is_loopback)):
                raise ValueError
            self.host, self.port, self.scheme = url.hostname, url.port, url.scheme
        except (TypeError, ValueError):
            raise ValueError("operations requires literal loopback HTTP or verified HTTPS") from None
        if not _text(token, 4096) or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError("operations transport configuration invalid")
        if type(max_response_bytes) is not int or not 1024 <= max_response_bytes <= 16 * 1024 * 1024:
            raise ValueError("operations response limit invalid")
        self.token, self.timeout, self.max_response_bytes = token, timeout, max_response_bytes

    def _call(self, method, job_id, payload=None):
        job_id = str(UUID(str(job_id)))
        path = "/v1/operations/history-jobs/" + job_id + ("/checkpoint" if method == "PUT" else "")
        body = None if payload is None else canonical_bytes(payload)
        if body and len(body) > 65536:
            raise ValueError("operations request limit")
        deadline = time.monotonic() + self.timeout

        class Response(http.client.HTTPResponse):
            def __init__(self, sock, *args, **kwargs):
                super().__init__(sock, *args, **kwargs)
                self.fp = io.BufferedReader(_DeadlineRaw(self.fp, sock, deadline))

        connection = (http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout, context=ssl.create_default_context())
            if self.scheme == "https" else http.client.HTTPConnection(self.host, self.port, timeout=self.timeout))
        connection.response_class = Response
        response = None
        try:
            connection.connect()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            connection.sock.settimeout(remaining)
            connection.request(method, path, body=body, headers={"X-Internal-Token": self.token,
                "Content-Type": "application/json", "Accept": "application/json", "Connection": "close"})
            response = connection.getresponse()
            if response.status == 409:
                raise OperationsConflict("operations revision conflict")
            if response.status != 200 or response.getheader("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                raise OperationsUnavailable("operations response rejected")
            length = response.getheader("Content-Length")
            if length is not None and (not length.isascii() or not length.isdecimal() or len(length) > 9 or int(length) > self.max_response_bytes):
                raise OperationsUnavailable("operations response limit")
            chunks, count = [], 0
            while True:
                chunk = response.read1(min(65536, self.max_response_bytes + 1 - count))
                if not chunk:
                    break
                chunks.append(chunk)
                count += len(chunk)
                if count > self.max_response_bytes:
                    raise OperationsUnavailable("operations response limit")
            if length is not None and count != int(length):
                raise OperationsUnavailable("operations response truncated")
            if time.monotonic() >= deadline:
                raise TimeoutError
            return validate_job(strict_json(b"".join(chunks)), job_id)
        except (OSError, http.client.HTTPException, TimeoutError):
            raise OperationsUnavailable("operations transport unavailable") from None
        finally:
            if response:
                response.close()
            connection.close()

    def get_job(self, job_id):
        return self._call("GET", job_id)

    def checkpoint(self, job_id, payload):
        return self._call("PUT", job_id, payload)


class _Halt(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


class HistoryRunner:
    """Single owner thread and one ephemeral task; Operations owns all progress.

    Injected network clients declare timeout (seconds); a call starts only when
    that entire bound fits the step deadline. Calendar/evidence implementations
    must provide bounded local calls; elapsed overrun is rejected, not preempted.
    """
    def __init__(self, operations, market, calendar: CalendarProvider, evidence: EvidenceSink,
                 binding: HistoryBinding, *, budget_ms=30000):
        if not isinstance(binding, HistoryBinding) or type(budget_ms) is not int or not 1 <= budget_ms <= 30000:
            raise ValueError("history runner configuration invalid")
        if any(value is None for value in (operations, market, calendar, evidence)):
            raise ValueError("history runner owners required")
        for client in (operations, market):
            bound = getattr(client, "timeout", None)
            if type(bound) not in (int, float) or not math.isfinite(bound) or not 0 < bound <= 30:
                raise ValueError("history network clients require a bounded timeout")
        self.operations, self.market, self.calendar, self.evidence, self.binding = operations, market, calendar, evidence, binding
        self.budget_ms, self.owner, self.active_task = budget_ms, threading.get_ident(), None
        self.task_phase, self.release_outcome = None, None
        self.running = False
        self.closed, self.queue_recovery_required, self._prepare_exchange_started = False, False, False

    def _call(self, owner, method, *args):
        remaining = self.deadline - time.monotonic()
        bound = getattr(owner, "timeout", 0)
        if remaining <= 0 or (bound and remaining < bound):
            raise _Halt("Timeout", "history step budget exhausted before bounded call")
        function = getattr(owner, method)
        if owner is self.market and method == "history_task_prepare":
            # 从通过准入的实际调用开始，持续到调用者接管身份或观察有效拒绝。
            # 返回合法响应仍有中断窗口，不能在 HTTP helper 返回时忘记该边界。
            self._prepare_exchange_started = True
        result = function(*args)
        if time.monotonic() >= self.deadline:
            raise _Halt("Timeout", "history injected call exceeded step budget")
        return result

    def _get(self, job_id):
        return validate_job(self._call(self.operations, "get_job", job_id), job_id)

    def _commit(self, job, *, checkpoint=None, status="running", remaining=None, result_ref=None):
        payload = {"schema_version": "1.0", "expected_updated_at": job["updated_at"], "status": status,
            "remaining_segments": job["remaining_segments"] if remaining is None else remaining}
        if checkpoint is not None:
            payload["checkpoint"] = checkpoint
        if result_ref is not None:
            payload["result_ref"] = result_ref
        try:
            current = validate_job(self._call(self.operations, "checkpoint", job["spec"]["job_id"], payload), job["spec"]["job_id"])
        except (OperationsConflict, OperationsUnavailable):
            # A lost PUT reply proves no non-application. Read the authoritative
            # job before deciding, and never blindly repeat this PUT.
            current = self._get(job["spec"]["job_id"])
        if current["request_sha256"] != job["request_sha256"] or current["spec"] != job["spec"]:
            raise _Halt("Conflict", "immutable job specification changed")
        if checkpoint is not None:
            found = self._find(current, self._key(checkpoint))
            identity = ("symbol", "start_date", "end_date", "status", "request_id", "bar_count", "result_sha256")
            if found is None or any(found.get(k) != checkpoint.get(k) for k in identity):
                raise _Halt("Conflict", "checkpoint outcome requires authoritative review")
        elif status == "succeeded":
            if current["status"] != "succeeded" or current.get("result_ref") != result_ref:
                raise _Halt("Conflict", "job completion outcome requires authoritative review")
        elif status == "stopped":
            if current["status"] != "stopped":
                raise _Halt("Conflict", "job stop outcome requires authoritative review")
        elif current["status"] not in ("running", "stop_requested"):
            raise _Halt("Conflict", "job start outcome requires authoritative review")
        return current

    @staticmethod
    def _key(item):
        return item["symbol"], item["start_date"], item["end_date"]

    def _find(self, job, key):
        return next((c for c in job["checkpoints"] if self._key(c) == key and c["status"] == "confirmed"), None)

    def _plan(self, spec):
        segments = []
        for symbol in spec["symbols"]:
            current, final = date.fromisoformat(spec["start_date"]), date.fromisoformat(spec["end_date"])
            while current <= final:
                end = min(final, current + timedelta(days=spec["segment_days"] - 1))
                segments.append((symbol, current.isoformat(), end.isoformat()))
                if len(segments) > 10000:
                    raise _Halt("Backpressure", "history segment plan exceeds budget")
                current = end + timedelta(days=1)
        return segments

    def _calendar(self, key, as_of):
        symbol, start, end = key
        calendar = self._call(self.calendar, "minutes", symbol, date.fromisoformat(start), date.fromisoformat(end), as_of)
        if not isinstance(calendar, CalendarSlice) or calendar.version != self.binding.calendar_version or type(calendar.authoritative_empty) is not bool:
            raise _Halt("Unavailable", "authoritative calendar identity unavailable")
        values = list(calendar.expected_minutes)
        if len(values) > 5000 or any(type(v) is not int for v in values) or values != sorted(set(values)):
            raise _Halt("InvalidInput", "authoritative minute grid invalid")
        for minute in values:
            instant = datetime.strptime(str(minute), "%Y%m%d%H%M").replace(tzinfo=SHANGHAI)
            if not start <= instant.date().isoformat() <= end or instant > as_of:
                raise _Halt("InvalidInput", "authoritative minute grid outside closed job boundary")
        if not values:
            closed = datetime.combine(date.fromisoformat(end) + timedelta(days=1), day_time(), tzinfo=SHANGHAI) <= as_of
            if not calendar.authoritative_empty or not _text(calendar.evidence_ref, 2048) or not closed:
                raise _Halt("Pending", "empty calendar requires authoritative closed-range evidence")
        elif calendar.authoritative_empty:
            raise _Halt("InvalidInput", "nonempty calendar cannot be authoritative empty")
        return calendar

    def _market(self, action, *args):
        method = {"history.query": "history_query", "history.task.prepare": "history_task_prepare",
            "history.task.inspect": "history_task_inspect", "history.task.work": "history_task_work", "history.task.release": "history_task_release"}[action]
        request = {"api_version": API_VERSION, "action": action}
        if action in ("history.query", "history.task.prepare"):
            request["request"] = args[0]
        else:
            request.update(queue_id=args[0], task_id=args[1])
        preparing = action == "history.task.prepare"
        try:
            try:
                value = self._call(self.market, method, *args)
            except MarketHTTPError as exc:
                value = exc.response
            return validate_response(value, request)
        except BaseException:
            if preparing and self._prepare_exchange_started:
                # 后续成功的新编号不能证明旧未知编号已回收；仅队列 owner 可恢复。
                # 中断也可能发生在远端分配之后；只记录风险，原样传播中断。
                self.queue_recovery_required = True
            raise

    def _clear_task(self):
        self.active_task, self.task_phase, self.release_outcome = None, None, None

    def _release(self):
        if self.active_task is None:
            return "Ok"
        _, queue, task_id = self.active_task
        # 在交换前保留释放意图；未发出、背压、丢回复都只重试同身份幂等释放。
        # 不能退回 inspect：远端可能已删除任务，inspect 的 InvalidInput 无法判定释放结果。
        self.task_phase = "Releasing"
        result = self._market("history.task.release", queue, task_id)
        if result["status"]["code"] not in ("Ok", "StaleSession"):
            raise _Halt(result["status"]["code"], "history task release unconfirmed")
        self._clear_task()
        return result["status"]["code"]

    def _observe_task(self, response):
        # 调用者已先 query DSB。协议错误码描述本次观察，data.state
        # 才说明任务是否终结；丢回复后必须核查终态并回收，不能重发 work。
        code, task = response["status"]["code"], response["data"]
        if code == "StaleSession":
            self._clear_task()
            raise _Halt(code, "history queue restarted; requery on next step")
        if not task:
            raise _Halt(code, "history task state not observed")
        if task["state"] in ("Complete", "Failed", "Unavailable"):
            self.release_outcome = "Pending" if task["state"] == "Complete" else code
            outcome = self.release_outcome
            released = self._release()
            raise _Halt("StaleSession" if released == "StaleSession" else outcome,
                "history terminal task released; requery before preparing again")
        if code != "Pending":
            # Pending+Backpressure 仍为在途，错误空 data 不代表任何已知终态。
            raise _Halt(code, "history task cannot advance during current observation")

    def _data(self, request, expected_source):
        response = self._market("history.query", request)
        status = response["status"]["code"]
        if status != "Ok":
            if status == "Unavailable":
                return None
            raise _Halt(status, "history query unavailable")
        data, metadata = response["data"], response["data"]["metadata"]
        source = metadata["source"]
        if (source["provider"] != "Qmt" or source["instance_id"] != self.binding.agent_id
                or metadata["dataset_version"] != self.binding.profile_version or metadata["source_license"] != self.binding.source_license
                or metadata["volume_to_shares"] != self.binding.volume_to_shares or metadata["amount_to_yuan"] != self.binding.amount_to_yuan
                or metadata["adjustment"] != "none" or metadata["minute_boundary"] != self.binding.minute_boundary
                or metadata["timezone"] != self.binding.timezone or metadata["qualification"] not in ("NativeVerified", "ProductionQualified")):
            raise _Halt("Conflict", "history source binding mismatch")
        if expected_source is not None and source != expected_source:
            raise _Halt("StaleSession", "history source session differs from confirmed evidence")
        if self.observed_source is not None and source != self.observed_source:
            raise _Halt("StaleSession", "history source changed within segment")
        self.observed_source = source
        if data["coverage"] != "Complete" or data["missing_minutes"]:
            return None
        if [bar["minute"] for bar in data["bars"]] != request["expected_minutes"]:
            raise _Halt("Conflict", "history result differs from entire authoritative minute grid")
        return data

    def _manifest(self, job, key, calendar, data):
        return {"schema_version": "guanheng.history.segment.v1", "job_id": job["spec"]["job_id"],
            "segment": {"symbol": key[0], "start_date": key[1], "end_date": key[2]},
            "as_of": job["spec"]["as_of"], "binding": asdict(self.binding), "binding_sha256": self.binding.sha256,
            "calendar_version": calendar.version, "expected_minutes": list(calendar.expected_minutes),
            "calendar_evidence_ref": calendar.evidence_ref,
            "completion_basis": "market_complete_grid" if data is not None else "calendar_authoritative_empty",
            "market": data}

    def _store(self, manifest):
        raw, sha = canonical_bytes(manifest), digest(manifest)
        reference = self._call(self.evidence, "put", sha, raw)
        if not _text(reference, 2048) or self._call(self.evidence, "get", sha) != raw:
            raise _Halt("Conflict", "immutable evidence could not be verified")
        return sha, reference

    def _confirmed(self, job, plan):
        source, hashes = None, []
        for checkpoint in job["checkpoints"]:
            if checkpoint["status"] != "confirmed":
                continue
            key = self._key(checkpoint)
            if key not in plan:
                raise _Halt("Conflict", "confirmed segment outside immutable plan")
            raw = self._call(self.evidence, "get", checkpoint["result_sha256"])
            if type(raw) is not bytes or len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != checkpoint["result_sha256"]:
                raise _Halt("Conflict", "confirmed evidence content changed")
            manifest = strict_json(raw)
            calendar = self._calendar(key, _instant(job["spec"]["as_of"]))
            market = manifest.get("market")
            if canonical_bytes(manifest) != raw or manifest != self._manifest(job, key, calendar, market):
                raise _Halt("Conflict", "confirmed evidence identity changed")
            if market is not None:
                request = self._request(key, calendar)
                validate_response({"api_version": API_VERSION, "status": {"code": "Ok", "reason": ""}, "data": market},
                    {"api_version": API_VERSION, "action": "history.query", "request": request})
                metadata = market["metadata"]
                current = market["metadata"]["source"]
                if (market["coverage"] != "Complete" or market["missing_minutes"]
                        or [bar["minute"] for bar in market["bars"]] != list(calendar.expected_minutes)
                        or current["provider"] != "Qmt" or current["instance_id"] != self.binding.agent_id
                        or metadata["dataset_version"] != self.binding.profile_version or metadata["source_license"] != self.binding.source_license
                        or metadata["volume_to_shares"] != self.binding.volume_to_shares or metadata["amount_to_yuan"] != self.binding.amount_to_yuan
                        or metadata["adjustment"] != "none" or metadata["qualification"] not in ("NativeVerified", "ProductionQualified")):
                    raise _Halt("Conflict", "confirmed market evidence invalid")
                if source is not None and source != current:
                    raise _Halt("StaleSession", "confirmed history mixes source sessions")
                source = current
            elif calendar.expected_minutes:
                raise _Halt("Conflict", "confirmed market grid has no market evidence")
            expected_uuid = str(uuid5(NAMESPACE_URL, "guanheng-history:"+job["spec"]["job_id"]+":"+"|".join(key)+":"+checkpoint["result_sha256"]))
            if checkpoint["request_id"] != expected_uuid or checkpoint["bar_count"] != (len(market["bars"]) if market else 0):
                raise _Halt("Conflict", "confirmed checkpoint differs from evidence")
            hashes.append(checkpoint["result_sha256"])
        return source, hashes

    @staticmethod
    def _request(key, calendar):
        return {"exchange": "SSE" if key[0].endswith(".SH") else "SZSE", "code": key[0][:6],
            "from": int(key[1].replace("-", "")+"0000"), "to": int(key[2].replace("-", "")+"2359"),
            "expected_minutes": list(calendar.expected_minutes), "calendar_version": calendar.version}

    def close(self) -> CloseResult:
        """本线程有界关闭：先拒绝新 step，每次最多释放一次已知身份。

        使用构造时 budget_ms 的独立截止；未确认可在本线程重复调用。
        不访问 Operations、不 prepare/work；本地关闭不等于控制面停止作业。
        未知 prepare 遗留只保留 owner 恢复标记，不创建持久任务账本。
        """
        recovery_required = self.queue_recovery_required or self._prepare_exchange_started
        if threading.get_ident() != self.owner or self.running:
            return CloseResult("Conflict", self.active_task is not None, recovery_required,
                               "history close requires its non-reentrant owner thread")
        self.queue_recovery_required = recovery_required
        self.closed = True
        self.running, self.deadline = True, time.monotonic() + self.budget_ms / 1000
        try:
            status = self._release()
            if self.queue_recovery_required:
                return CloseResult("Unavailable", False, True, "history queue owner recovery required")
            return CloseResult(status, False, False, "history runner drained")
        except _Halt as exc:
            return CloseResult(exc.status, self.active_task is not None, self.queue_recovery_required,
                               "history task release unconfirmed")
        except (MarketUnavailable, OSError):
            return CloseResult("Unavailable", self.active_task is not None, self.queue_recovery_required,
                               "history close transport unavailable")
        except (ValueError, KeyError, TypeError, OverflowError):
            return CloseResult("Conflict", self.active_task is not None, self.queue_recovery_required,
                               "history close contract invalid")
        except Exception:
            return CloseResult("Unavailable", self.active_task is not None, self.queue_recovery_required,
                               "history close owner unavailable")
        finally:
            self.running = False

    def step(self, job_id, max_segments=1):
        try:
            job_id = str(UUID(str(job_id)))
        except (ValueError, TypeError, AttributeError):
            return StepResult("InvalidInput", "", reason="history job UUID invalid")
        if threading.get_ident() != self.owner or self.running:
            return StepResult("Conflict", job_id, reason="history runner requires its non-reentrant owner thread")
        if self.closed:
            return StepResult("Conflict", job_id, reason="history runner closed")
        if type(max_segments) is not int or not 1 <= max_segments <= 64:
            return StepResult("InvalidInput", job_id, reason="history step segment limit invalid")
        self.running, self.deadline = True, time.monotonic() + self.budget_ms / 1000
        count = 0
        try:
            job = self._get(job_id)
            spec = job["spec"]
            if (spec["period"] != "1m" or spec["policy_id"] != "wt.history.v1" or spec["segment_days"] > 3
                    or spec["dataset_version"] != self.binding.dataset_version or spec["agent_id"] != self.binding.agent_id):
                raise _Halt("NotSupported", "history job family or binding rejected")
            if job["status"] in ("stopped", "failed", "succeeded"):
                return StepResult("Ok", job_id, reason="history job is terminal; no work advanced", result_ref=job.get("result_ref"))
            if job["stop_requested"]:
                self._release()
                self._commit(job, status="stopped")
                return StepResult("Ok", job_id, reason="history stop confirmed at segment boundary")
            plan = self._plan(spec)
            source, hashes = self._confirmed(job, plan)
            if job["status"] == "queued":
                job = self._commit(job)
            for key in plan:
                if self._find(job, key):
                    continue
                if count >= max_segments:
                    break
                job = self._get(job_id)
                if job["spec"] != spec:
                    raise _Halt("Conflict", "immutable job specification changed")
                if job["status"] in ("stopped", "failed", "succeeded"):
                    return StepResult("Ok", job_id, count, "history job is terminal; no work advanced", job.get("result_ref"))
                if job["stop_requested"]:
                    self._release()
                    self._commit(job, status="stopped")
                    return StepResult("Ok", job_id, count, "history stop confirmed at segment boundary")
                if self._find(job, key):
                    source, hashes = self._confirmed(job, plan)
                    continue
                calendar = self._calendar(key, _instant(spec["as_of"]))
                data = None
                self.observed_source = source
                if calendar.expected_minutes:
                    if len(calendar.expected_minutes) > spec["count"]:
                        raise _Halt("Backpressure", "history minute grid exceeds immutable requested count")
                    request = self._request(key, calendar)
                    data = self._data(request, source)
                    if data is None:
                        if self.active_task and self.active_task[0] != (job_id, key):
                            self._release()
                        if self.active_task and self.task_phase == "Releasing":
                            outcome = self.release_outcome or "Pending"
                            released = self._release()
                            raise _Halt("StaleSession" if released == "StaleSession" else outcome,
                                "history task release confirmed; requery before preparing again")
                        if self.active_task:
                            _, queue, task_id = self.active_task
                            inspected = self._market("history.task.inspect", queue, task_id)
                            self._observe_task(inspected)
                        if self.active_task is None:
                            prepared = self._market("history.task.prepare", request)
                            if not prepared["data"]:
                                self._prepare_exchange_started = False
                                raise _Halt(prepared["status"]["code"], "history preparation unavailable")
                            task = prepared["data"]
                            self.active_task = ((job_id, key), task["queue_id"], task["task_id"])
                            self.task_phase = "Active"
                            self._prepare_exchange_started = False
                            self._observe_task(prepared)
                        _, queue, task_id = self.active_task
                        worked = self._market("history.task.work", queue, task_id)
                        if worked["status"]["code"] == "StaleSession":
                            self._clear_task()
                            raise _Halt("StaleSession", "history queue restarted; requery on next step")
                        data = self._data(request, source)
                        if data is None:
                            self._observe_task(worked)
                            raise _Halt("Pending", "history full minute coverage not confirmed")
                    self._release()
                    source = data["metadata"]["source"]
                manifest = self._manifest(job, key, calendar, data)
                sha, _ = self._store(manifest)
                request_id = str(uuid5(NAMESPACE_URL, "guanheng-history:"+job_id+":"+"|".join(key)+":"+sha))
                checkpoint = {"schema_version": "1.0", "symbol": key[0], "start_date": key[1], "end_date": key[2],
                    "status": "confirmed", "attempt": 1, "request_id": request_id,
                    "bar_count": len(data["bars"]) if data else 0, "result_sha256": sha,
                    "error_code": None, "completed_at": datetime.now(timezone.utc).isoformat()}
                remaining = len(plan) - job["completed_segments"] - 1
                job = self._commit(job, checkpoint=checkpoint, remaining=remaining)
                count += 1
                hashes.append(sha)
                if job["stop_requested"]:
                    self._commit(job, status="stopped")
                    return StepResult("Ok", job_id, count, "history stop confirmed after segment")
            if all(self._find(job, key) for key in plan):
                _, hashes = self._confirmed(job, plan)
                final = {"schema_version": "guanheng.history.result.v1", "job_id": job_id, "binding_sha256": self.binding.sha256,
                    "segment_sha256": sorted(hashes)}
                _, reference = self._store(final)
                self._commit(job, status="succeeded", remaining=0, result_ref=reference)
                return StepResult("Ok", job_id, count, "history complete", reference)
            self._commit(job)
            return StepResult("Pending", job_id, count, "history segments remain")
        except _Halt as exc:
            return StepResult(exc.status, job_id, count, exc.reason)
        except (OperationsUnavailable, MarketUnavailable, OSError):
            return StepResult("Unavailable", job_id, count, "history owner transport unavailable; requery before next advance")
        except (ValueError, KeyError, TypeError, OverflowError):
            return StepResult("Conflict", job_id, count, "history contract or immutable evidence invalid")
        finally:
            # 合法响应返回到身份接管之间也可能中断；未完成交接一律保留恢复需求。
            if self._prepare_exchange_started:
                self.queue_recovery_required = True
            self.running = False
