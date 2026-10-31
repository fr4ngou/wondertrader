"""Host-owned durable read-operation identity and results.

Every state transition commits before the corresponding external action. A
dispatch interrupted by process exit is never automatically sent a second time.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import sqlite3
import threading
import time

from guanheng_qmt_shm_agent.protocol import canonical, decode, identity
from guanheng_qmt_shm_agent.results import finalize_result
from .contracts import GatewayOperationRequest, GatewayOperationResult


class JournalConflict(ValueError):
    pass


class JournalFull(ValueError):
    pass


def interrupted(request_id: str, operation_id: str, code: str) -> dict:
    return GatewayOperationResult(request_id=request_id, operation_id=operation_id,
        ok=False, error_code=code,
        error_message="读取中断；领取原结果，使用新请求身份发起后续观察").model_dump(mode="json")


class HostReadJournal:
    """One exclusive host process owns this store, fixed to one route identity.

    path is an absolute managed Host path, never an Agent filesystem path.
    max_records (1..1000000) limits all retained facts; max_result_bytes
    (1024..2097152) limits a terminal JSON result. Both are required deployment
    budgets with no silent eviction. Exhaustion rejects new work; prior results
    remain readable. SQLite failure propagates and must close runtime admission.
    """
    schema_tables = frozenset(("identity", "read_operations"))

    def __init__(self, path: Path, route: dict, *, max_records: int, max_result_bytes: int):
        if not Path(path).is_absolute():
            raise ValueError("Journal path must be absolute")
        if type(max_records) is not int or not 1 <= max_records <= 1000000:
            raise ValueError("invalid Journal record budget")
        if type(max_result_bytes) is not int or not 1024 <= max_result_bytes <= 2097152:
            raise ValueError("invalid result byte budget")
        self.path, self.route = Path(path).resolve(), identity(route)
        self.max_records, self.max_result_bytes = max_records, max_result_bytes
        self._lock = threading.RLock()
        # OS lock is held for the lifetime of the owner, not just a SQL transaction.
        # It prevents a second process from recovering a live dispatch as failed.
        self._owner = self.path.with_suffix(self.path.suffix + ".owner").open("a+b")
        try:
            self._owner.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._owner.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self._transaction() as db:
                existing_tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT GLOB 'sqlite_*'")}
                if (existing_tables - self.schema_tables
                        or existing_tables and not {"identity", "read_operations"} <= existing_tables):
                    # A mistyped path must not add tables to the legacy trading
                    # Journal or another application's database.
                    raise JournalConflict("Host read Journal requires its own database")
                db.execute("CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY CHECK(id=1), value BLOB)")
                encoded = canonical(self.route)
                existing = db.execute("SELECT value FROM identity WHERE id=1").fetchone()
                if existing and bytes(existing[0]) != encoded:
                    raise JournalConflict("Journal is bound to a different route")
                db.execute("INSERT OR IGNORE INTO identity VALUES(1,?)", (encoded,))
                db.execute("""CREATE TABLE IF NOT EXISTS read_operations (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT UNIQUE NOT NULL,
                    operation_id TEXT NOT NULL, request_sha256 TEXT NOT NULL, body BLOB NOT NULL,
                    state TEXT NOT NULL, expires_at REAL NOT NULL, queued_at REAL NOT NULL,
                    started_at REAL, result BLOB)""")
                rows = db.execute("SELECT request_id,operation_id FROM read_operations WHERE state='dispatching'").fetchall()
                for request_id, operation_id in rows:
                    self._finish(db, request_id, self._interrupted_result(request_id, operation_id, "operation_interrupted"))
        except BaseException:
            self.close()
            raise

    @contextmanager
    def _transaction(self):
        with self._lock:
            if self._owner.closed:
                raise RuntimeError("Journal owner is closed")
            db = sqlite3.connect(self.path, timeout=1)
            try:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    def close(self):
        with self._lock:
            if not self._owner.closed:
                self._owner.close()

    def submit(self, body: bytes, *, queue_timeout_ms: int) -> str:
        """Commit queued before returning; v1 identity excludes timeout/correlation.

        body is the validated v1 request's original UTF-8 bytes. Queue timeout is
        the selected policy's positive milliseconds, persisted as UTC epoch
        expiry so a restart cannot grant a fresh admission window.
        """
        if type(queue_timeout_ms) is not int or not 1 <= queue_timeout_ms <= 300000:
            raise ValueError("invalid persisted queue timeout")
        request = GatewayOperationRequest.model_validate(decode(body))
        digest = hashlib.sha256(canonical({"operation_id": request.operation_id,
                                          "arguments": request.arguments})).hexdigest()
        request_id = str(request.request_id)
        with self._transaction() as db:
            existing = db.execute("SELECT request_sha256 FROM read_operations WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing[0] != digest:
                    raise JournalConflict("request_id already has different content")
                return request_id
            if db.execute("SELECT COUNT(*) FROM read_operations").fetchone()[0] >= self.max_records:
                raise JournalFull("Journal record budget exhausted")
            db.execute("""INSERT INTO read_operations
                (request_id,operation_id,request_sha256,body,state,expires_at,queued_at)
                VALUES(?,?,?,?,'queued',?,?)""", (request_id, request.operation_id, digest,
                     body, time.time() + queue_timeout_ms / 1000, time.time()))
        return request_id

    def claim(self) -> tuple[str, bytes, int, float] | None:
        """Commit dispatching before IPC send; never claim dispatching again."""
        with self._transaction() as db:
            while True:
                row = db.execute("""SELECT request_id,operation_id,body,expires_at
                    FROM read_operations WHERE state='queued' ORDER BY seq LIMIT 1""").fetchone()
                if row is None:
                    return None
                request_id, operation_id, body, expires_at = row
                remaining_ms = int((expires_at - time.time()) * 1000)
                if remaining_ms <= 0:
                    self._finish(db, request_id, self._interrupted_result(request_id, operation_id, "queue_timeout"))
                    continue
                db.execute("UPDATE read_operations SET state='dispatching',started_at=? WHERE request_id=?", (time.time(), request_id))
                return request_id, bytes(body), remaining_ms, expires_at

    def _interrupted_result(self, request_id, operation_id, code):
        """由显式owner选择合法中断结果；恢复与实时中断共用同一入口。"""
        return interrupted(request_id, operation_id, code)

    def _finish(self, db, request_id, result):
        result = finalize_result(result, self.max_result_bytes)
        db.execute("UPDATE read_operations SET state='terminal',result=? WHERE request_id=?",
                   (canonical(result), request_id))

    def finish(self, request_id: str, result: dict):
        result = GatewayOperationResult.model_validate(result).model_dump(mode="json")
        with self._transaction() as db:
            row = db.execute("SELECT operation_id,state FROM read_operations WHERE request_id=?", (request_id,)).fetchone()
            if (row is None or row[1] != "dispatching" or result["request_id"] != request_id
                    or result["operation_id"] != row[0]):
                raise JournalConflict("result does not match active dispatch")
            self._finish(db, request_id, result)

    def get(self, request_id: str) -> dict | None:
        with self._transaction() as db:
            row = db.execute("SELECT operation_id,state,result,request_sha256,queued_at,started_at FROM read_operations WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                return None
            return {"request_id": request_id, "operation_id": row[0], "state": row[1],
                    "result": decode(bytes(row[2])) if row[2] is not None else None,
                    "request_sha256": row[3], "queued_at": row[4], "started_at": row[5]}
