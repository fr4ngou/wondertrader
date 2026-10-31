"""Host-owned durable read-operation identity and results.

Every state transition commits before the corresponding external action. A
dispatch interrupted by process exit is never automatically sent a second time.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import math
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


def construct_journal(factory, *args, failed_owners=None, **kwargs):
    """构造失败尚有资源时，将原owner交回既有创建槽，原异常继续传播。"""
    try:
        return factory(*args, **kwargs)
    except BaseException as error:
        owner = getattr(error, 'journal_owner', None)
        if owner is not None and failed_owners is not None:
            failed_owners[0] = owner
        raise


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
        self._check_owner_deadline()
        resolved_path = Path(path).resolve()
        self._check_owner_deadline()
        self.path, self.route = resolved_path, identity(route)
        self.max_records, self.max_result_bytes = max_records, max_result_bytes
        self._lock = threading.RLock()
        # OS lock is held for the lifetime of the owner, not just a SQL transaction.
        # It prevents a second process from recovering a live dispatch as failed.
        self._check_owner_deadline()
        self._owner = self.path.with_suffix(self.path.suffix + ".owner").open("a+b")
        self._database = None
        try:
            self._check_owner_deadline()
            self._owner.seek(0)
            self._check_owner_deadline()
            if os.name == "nt":
                import msvcrt
                self._check_owner_deadline()
                msvcrt.locking(self._owner.fileno(), msvcrt.LK_NBLCK, 1)
                self._check_owner_deadline()
            else:
                import fcntl
                self._check_owner_deadline()
                fcntl.flock(self._owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._check_owner_deadline()
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

    def _check_owner_deadline(self):
        """缺省无新增截止；专用owner可在路径/租约创建前后收紧原D。"""
        pass

    @staticmethod
    def _finish_deadline(deadline):
        if deadline is not None:
            if type(deadline) not in (int, float) or not math.isfinite(deadline):
                raise ValueError('result persistence requires an absolute monotonic deadline')
            if time.monotonic() >= deadline:
                raise TimeoutError('original read result persistence deadline elapsed')

    def _open_connection(self, timeout):
        """原连接创建接缝；专用维护owner可附加同一连接的截止代理。"""
        return sqlite3.connect(self.path, timeout=timeout, check_same_thread=False)

    def _connection(self, timeout):
        """原文件 owner/事务锁持有唯一连接；FULL WAL 每次提交仍实际同步。

        连接跨原 HTTP/域线程复用但从不并行使用。保留 SQLite 的默认自动
        checkpoint，避免逐事务关闭最后连接触发额外 checkpoint/同步。
        """
        if self._database is None:
            # 取得连接即归入唯一owner；后续PRAGMA失败也沿close释放，关闭失败
            # 保留连接和文件锁，避免构造未返回时丢失可恢复资源。
            self._database = self._open_connection(timeout)
            mode = self._database.execute('PRAGMA journal_mode=WAL').fetchone()
            self._database.execute('PRAGMA synchronous=FULL')
            if mode != ('wal',) or self._database.execute('PRAGMA synchronous').fetchone() != (2,):
                raise sqlite3.OperationalError('durable communication Journal mode unavailable')
        return self._database

    @contextmanager
    def _transaction(self, deadline=None):
        remaining = None if deadline is None else max(0, deadline-time.monotonic())
        acquired = self._lock.acquire() if remaining is None else self._lock.acquire(timeout=remaining)
        if not acquired:
            raise TimeoutError('Journal transaction busy; retain its owner')
        database = None
        try:
            if self._owner.closed:
                raise RuntimeError("Journal owner is closed")
            self._finish_deadline(deadline)
            timeout = 1 if deadline is None else min(1, max(0, deadline-time.monotonic()))
            database = self._connection(timeout)
            # 只有 SQLite 锁等待预算变化；原首次 D 不续期，原 SQL/提交边界保持。
            database.execute('PRAGMA busy_timeout='+str(int(timeout*1000)))
            self._finish_deadline(deadline)
            database.execute('BEGIN IMMEDIATE')
            yield database
            self._finish_deadline(deadline)
            database.commit()
            # COMMIT 已返回但超期仍保留其实际落盘事实，原调用者不发送源 ACK。
            self._finish_deadline(deadline)
        except BaseException:
            if database is not None:
                database.rollback()
            raise
        finally:
            self._lock.release()
        self._finish_deadline(deadline)

    def close(self, deadline=None):
        if deadline is not None and (type(deadline) not in (int,float) or not math.isfinite(deadline)):
            raise ValueError('close requires absolute monotonic deadline')
        acquired = self._lock.acquire() if deadline is None else self._lock.acquire(timeout=max(0,deadline-time.monotonic()))
        if not acquired:
            raise TimeoutError('Journal transaction busy; retain its owner')
        try:
            if not self._owner.closed:
                if self._database is not None:
                    self._finish_deadline(deadline)
                    self._database.close()
                    self._database = None
                    self._finish_deadline(deadline)
                self._owner.close()
        except BaseException as error:
            # 工厂尚未返回时，由原异常携带同一owner；常驻工厂接回原创建槽。
            # 原异常类型/context不替换，调用方必须确认close后才释放该责任。
            if not self._owner.closed or self._database is not None:
                error.journal_owner = self
            raise
        finally:
            self._lock.release()

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
