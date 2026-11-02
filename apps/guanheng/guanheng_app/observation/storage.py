"""本地不可变观察对象与事务目录；发布和采集lease分别拥有连接。"""

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from time import monotonic
from threading import get_ident
from datetime import datetime,timezone

from .contracts import ObservationError
from ..managed_local_process import _open_read

OBJECT_BYTES = 256 * 1024 * 1024
MANIFEST_BYTES = 64 * 1024 * 1024


def replace_readable_file(candidate,target):
    """单写者原子提交完整文件；共享删除读者可继续持有旧快照。

    沿原Host retained回执的ReplaceFileW语义：Windows MoveFileEx仍与打开
    的旧目标冲突。首发独占rename；其他平台用replace。失败保留原生错误，
    截止、未知结果及临时文件的清理由调用者持有。本观察包不依赖Host运行库。
    """
    try:os.lstat(target)
    except FileNotFoundError:
        os.rename(candidate,target);return
    if os.name!='nt':os.replace(candidate,target);return
    import ctypes
    from ctypes import wintypes
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.ReplaceFileW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,
        wintypes.DWORD,wintypes.LPVOID,wintypes.LPVOID]
    api.ReplaceFileW.restype=wintypes.BOOL
    if not api.ReplaceFileW(os.fspath(target),os.fspath(candidate),None,0,None,None):
        raise ctypes.WinError(ctypes.get_last_error())


def _catalog_runtime():
    # WAL-reset在3.51.3修正；读连接关闭也可触发checkpoint，所有目录连接统一准入。
    if sqlite3.sqlite_version_info < (3, 51, 3):
        raise ObservationError('unsupported_catalog_runtime', '观察目录需要SQLite 3.51.3或更新的Python运行环境', 503)


def _atomic_replace(path, body):
    """同目录完整写入并同步后替换；失败保持上次完整值，临时文件归本次调用。"""
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix='.incoming-')
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        # 心跳读者可持有旧文件；复用存储层统一替换原语，保留完整旧/新快照。
        replace_readable_file(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _write_guard(deadline,cancelled):
    if deadline is not None and (type(deadline) not in (int,float) or not math.isfinite(deadline)):
        raise ObservationError('invalid_write_deadline','观察写入截止无效',422)
    if cancelled is not None and cancelled():
        raise ObservationError('observation_stopped','观察写入已停止',503)
    if deadline is not None and monotonic()>=deadline:
        raise ObservationError('observation_timeout','观察写入超过原截止',503)


class SchedulerLease:
    """同根调度状态的存续期资格，仅所属线程可用；上下文退出即失效。"""
    def __init__(self,repository):
        self.repository,self.thread,self.active=repository,get_ident(),True

    def require(self,repository):
        if not self.active or self.repository is not repository or self.thread!=get_ident():
            raise ObservationError('scheduler_owner_required','观察调度发布资格无效',409)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def digest(body):
    return hashlib.sha256(body).hexdigest()


def valid_sha(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ObservationError('invalid_identity', '资产或版本身份无效', 422)
    return value


def local_root(root):
    path = Path(root)
    if not path.is_absolute() or str(path).startswith(('\\\\', '//')):
        raise ObservationError('invalid_root', '观察数据根需要显式本地绝对路径', 503)
    return path.resolve()


class ContentStore:
    def __init__(self, root):
        self.root = local_root(root)

    def path(self, sha):
        valid_sha(sha)
        path = self.root / 'objects' / 'sha256' / sha[:2] / sha
        if not path.resolve().is_relative_to(self.root):
            raise ObservationError('invalid_path', '观察对象路径无效', 503)
        return path

    def get(self, sha):
        try:
            with self.path(sha).open('rb') as stream:
                size = os.fstat(stream.fileno()).st_size
                if size > OBJECT_BYTES:
                    raise ObservationError('object_budget_exceeded', '观察对象超过读取容量', 503)
                # 按已打开文件的实际长度分配；额外一字节检测在途增长。
                body = stream.read(size + 1)
                if len(body) != size:
                    raise ObservationError('corrupt_object', '观察资产读取期间发生变化', 503)
        except OSError as exc:
            raise ObservationError('asset_unavailable', '已登记观察资产暂不可用', 503) from exc
        if len(body) > OBJECT_BYTES:
            raise ObservationError('object_budget_exceeded', '观察对象超过读取容量', 503)
        if digest(body) != sha:
            raise ObservationError('corrupt_object', '观察资产内容校验失败', 503)
        return body

    def put(self, body, *, kind='raw'):
        if not isinstance(body, bytes) or len(body) > OBJECT_BYTES:
            raise ObservationError('object_budget_exceeded', '观察对象超过保存容量', 422)
        sha = digest(body)
        target = self.path(sha)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            self.get(sha)
            return sha
        _atomic_replace(target, body)
        return sha


class SnapshotRepository:
    """短连接/有限busy等待；current与receipt共用一个提交点。

    采集连接持有独立lease库的IMMEDIATE事务；同一root的其他进程可读取
    目录，采集者也可向目录发布。连接关闭或进程退出会释放SQLite写锁。
    """

    def __init__(self, root):
        self.root = local_root(root)
        self.path = self.root / 'catalog.sqlite3'

    @contextmanager
    def connect(self, *, writing=False,deadline=None,cancelled=None):
        database = None
        try:
            _catalog_runtime()
            _write_guard(deadline,cancelled)
            wait=.25 if deadline is None else min(.25,max(0,deadline-monotonic()))
            database = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=wait)
            database.execute('PRAGMA busy_timeout='+str(int(wait*1000)))
            if deadline is not None or cancelled is not None:
                def interrupted():
                    try:_write_guard(deadline,cancelled);return 0
                    except ObservationError:return 1
                database.set_progress_handler(interrupted,1000)
            if writing:
                database.execute('BEGIN IMMEDIATE')
            _write_guard(deadline,cancelled)
            yield database
            if writing:
                _write_guard(deadline,cancelled)
                try:database.commit()
                except BaseException as exc:
                    if not database.in_transaction:
                        raise ObservationError('write_outcome_unknown','观察提交结果待核查',503) from exc
                    raise
                try:_write_guard(deadline,cancelled)
                except ObservationError as exc:
                    # 提交已进入持久边界，晚到确认只授未知，原身份留给后继核查。
                    raise ObservationError('write_outcome_unknown','观察提交结果待核查',503) from exc
        except sqlite3.Error as exc:
            _write_guard(deadline,cancelled)
            raise ObservationError('catalog_unavailable', '观察目录繁忙或暂不可用，请重新读取', 503) from exc
        finally:
            if database is not None:
                database.close()

    def initialize(self):
        _catalog_runtime()
        self.root.mkdir(parents=True, exist_ok=True)
        database = sqlite3.connect(self.path, timeout=0.25)
        try:
            # 原大manifest事务在rollback journal下会阻塞读；WAL让读者保留原完整提交。
            if database.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise ObservationError('catalog_wal_unavailable', '观察目录未能启用并发读取模式，请核对本地存储', 503)
            database.executescript('''
                PRAGMA synchronous=FULL;
                CREATE TABLE IF NOT EXISTS snapshots(version TEXT PRIMARY KEY, manifest BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS current(id INTEGER PRIMARY KEY CHECK(id=1), version TEXT REFERENCES snapshots(version));
                INSERT OR IGNORE INTO current VALUES(1,NULL);
                CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, receipt BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS completed_windows(window_key TEXT PRIMARY KEY, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS window_attempts(window_key TEXT PRIMARY KEY, attempts INTEGER NOT NULL, attempted_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS scheduler_state(id INTEGER PRIMARY KEY CHECK(id=1), body BLOB NOT NULL);
            ''')
            database.commit()
        finally:
            database.close()

    def current(self):
        with self.connect() as db:
            return db.execute('SELECT version FROM current WHERE id=1').fetchone()[0]

    def get(self, version):
        valid_sha(version)
        with self.connect() as db:
            row = db.execute('SELECT length(manifest) FROM snapshots WHERE version=?', (version,)).fetchone()
            if row is None:
                raise ObservationError('snapshot_not_found', '观察数据版本不存在', 404)
            if row[0] > MANIFEST_BYTES:
                raise ObservationError('manifest_budget_exceeded', '观察目录超过读取容量', 503)
            body = db.execute('SELECT manifest FROM snapshots WHERE version=?', (version,)).fetchone()[0]
        if digest(body) != version:
            raise ObservationError('corrupt_snapshot', '观察目录内容校验失败', 503)
        return json.loads(body)

    def publish(self, manifest, expected, *, receipt=None,deadline=None,cancelled=None):
        """准备/锁等待/提交共用原D；提交晚确认沿原版本核查，不作补偿回退。"""
        _write_guard(deadline,cancelled)
        if expected is not None:
            valid_sha(expected)
        body = encode(manifest)
        if len(body) > MANIFEST_BYTES:
            raise ObservationError('manifest_budget_exceeded', '观察目录超过保存容量', 422)
        version = digest(body)
        receipt_body = encode(receipt) if receipt is not None else None
        if receipt_body is not None and len(receipt_body) > 1024 * 1024:
            raise ObservationError('receipt_budget_exceeded', '观察发布记录超过容量', 422)
        try:
            return self._publish(body,version,expected,receipt,receipt_body,deadline,cancelled)
        except ObservationError as exc:
            if exc.code=='write_outcome_unknown':
                raise ObservationError('publication_outcome_unknown','观察发布结果待核查，请保留原版本和窗口身份',503) from exc
            raise

    def _publish(self,body,version,expected,receipt,receipt_body,deadline,cancelled):
        with self.connect(writing=True,deadline=deadline,cancelled=cancelled) as db:
            window = receipt.get('window_key') if receipt else None
            if window and db.execute('SELECT 1 FROM completed_windows WHERE window_key=?',(window,)).fetchone():
                raise ObservationError('window_already_complete','该观察窗口已完成',409)
            if db.execute('SELECT version FROM current WHERE id=1').fetchone()[0] != expected:
                raise ObservationError('publication_conflict', '当前观察版本已变化，本次发布已停止', 409)
            found = db.execute('SELECT length(manifest) FROM snapshots WHERE version=?', (version,)).fetchone()
            if found is not None:
                if found[0] != len(body) or db.execute('SELECT manifest FROM snapshots WHERE version=?', (version,)).fetchone()[0] != body:
                    raise ObservationError('corrupt_snapshot', '已存观察版本校验失败，本次采用已停止', 503)
            else:
                db.execute('INSERT INTO snapshots VALUES(?,?)', (version, body))
            db.execute('UPDATE current SET version=? WHERE id=1', (version,))
            if receipt_body is not None:
                db.execute('INSERT INTO runs(receipt) VALUES(?)', (receipt_body,))
                self._record_attempt(db,receipt)
                if window and receipt.get('window_complete') is True:
                    db.execute('INSERT INTO completed_windows VALUES(?,?)',(window,version))
        return version

    @staticmethod
    def _record_attempt(db,receipt):
        window=receipt.get('window_key')
        if window:
            reserved=receipt.get('attempt_number')
            if reserved is not None:
                row=db.execute('SELECT attempts,attempted_at FROM window_attempts WHERE window_key=?',(window,)).fetchone()
                if type(reserved) is not int or row is None or tuple(row)!=(reserved,receipt['started_at']):
                    raise ObservationError('window_attempt_conflict','观察窗口尝试身份已变化',409)
                return
            db.execute('INSERT INTO window_attempts VALUES(?,1,?) ON CONFLICT(window_key) DO UPDATE SET attempts=attempts+1,attempted_at=excluded.attempted_at',
                (window,receipt['started_at']))

    def reserve_window_attempt(self,key,now,maximum,retry_seconds,*,deadline=None,cancelled=None):
        """持采集lease时、网络前登记；崩溃仍留下有限尝试，不依赖展示回执。"""
        from .schedule_policy import window_as_of
        window_as_of(key,now)
        if (type(maximum) is not int or not 1<=maximum<=8
                or type(retry_seconds) not in (int,float) or not 1<=retry_seconds<=3600):
            raise ObservationError('invalid_window_attempt','观察窗口尝试预算无效',422)
        with self.connect(writing=True,deadline=deadline,cancelled=cancelled) as db:
            if db.execute('SELECT 1 FROM completed_windows WHERE window_key=?',(key,)).fetchone():
                return dict(status='window_already_complete',window_key=key)
            row=db.execute('SELECT attempts,attempted_at FROM window_attempts WHERE window_key=?',(key,)).fetchone()
            count=row[0] if row else 0
            if count>=maximum:return dict(status='window_attempts_exhausted',window_key=key)
            if row:
                try:
                    prior=datetime.fromisoformat(row[1])
                    if prior.tzinfo is None:raise ValueError('missing timezone')
                    elapsed=(now-prior).total_seconds()
                except (ValueError,TypeError,OverflowError):
                    raise ObservationError('invalid_window_attempt','观察窗口尝试记录无效',503) from None
                if elapsed<retry_seconds:return dict(status='window_backoff',window_key=key)
            stamp=now.isoformat()
            db.execute('INSERT INTO window_attempts VALUES(?,?,?) ON CONFLICT(window_key) DO UPDATE SET attempts=excluded.attempts,attempted_at=excluded.attempted_at',
                (key,count+1,stamp))
        return dict(status='reserved',window_key=key,attempt_number=count+1,started_at=stamp)

    def record_run(self,receipt,*,deadline=None,cancelled=None):
        _write_guard(deadline,cancelled)
        body=encode(receipt)
        if len(body)>1024*1024:
            raise ObservationError('receipt_budget_exceeded','观察更新记录超过容量',422)
        with self.connect(writing=True,deadline=deadline,cancelled=cancelled) as db:
            db.execute('INSERT INTO runs(receipt) VALUES(?)',(body,))
            self._record_attempt(db,receipt)

    def window_complete(self,key):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM completed_windows WHERE window_key=?',(key,)).fetchone() is not None

    def window_attempt(self,key):
        with self.connect() as db:
            row=db.execute('SELECT attempts,attempted_at FROM window_attempts WHERE window_key=?',(key,)).fetchone()
        return (row[0],row[1]) if row else (0,None)

    def runs(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT receipt FROM runs ORDER BY id DESC LIMIT 100')]

    def source_receipts(self, operation, source_id, day, *, deadline, cancelled=None,
                        status=None, part=None, policy=None, attempt_date=None):
        """原runs中的定日原件与尝试；先按事实身份筛选，再限制返回条数。"""
        predicates=["json_extract(CAST(receipt AS TEXT),'$.operation')=?",
                    "json_extract(CAST(receipt AS TEXT),'$.source_id')=?",
                    "json_extract(CAST(receipt AS TEXT),'$.date')=?"]
        arguments=[operation,source_id,day]
        for field,value in (('status',status),('part',part),('policy_sha256',policy),('attempt_date',attempt_date)):
            if value is not None:
                predicates.append("json_extract(CAST(receipt AS TEXT),'$."+field+"')=?")
                arguments.append(value)
        with self.connect(deadline=deadline,cancelled=cancelled) as db:
            rows=db.execute('SELECT receipt FROM runs WHERE '+' AND '.join(predicates)+
                ' ORDER BY id DESC LIMIT 32',arguments).fetchall()
        return [json.loads(row[0]) for row in rows]

    def source_archives(self,operation,source_id,start,end,*,deadline,cancelled=None,policy):
        """按交易日取最后成功原件锚；查询原runs，不以展示页100条上限截断历史。"""
        with self.connect(deadline=deadline,cancelled=cancelled) as db:
            rows=db.execute('''SELECT receipt FROM runs WHERE id IN (
                SELECT max(id) FROM runs WHERE
                json_extract(CAST(receipt AS TEXT),'$.operation')=? AND
                json_extract(CAST(receipt AS TEXT),'$.source_id')=? AND
                json_extract(CAST(receipt AS TEXT),'$.status')='success' AND
                json_extract(CAST(receipt AS TEXT),'$.policy_sha256')=? AND
                json_extract(CAST(receipt AS TEXT),'$.date') BETWEEN ? AND ?
                GROUP BY json_extract(CAST(receipt AS TEXT),'$.date'))
                ORDER BY id LIMIT 20001''',(operation,source_id,policy,start,end)).fetchall()
        if len(rows)>20000:
            raise ObservationError('source_archive_capacity','日终原件历史超过单次读取容量',503)
        return [json.loads(row[0]) for row in rows]

    def scheduler_status(self):
        try:
            try:
                # 原共享删除读句柄允许原子替换；读者得到上份或新份完整状态。
                with _open_read(self.root/'scheduler-status.json') as stream:
                    body=stream.read(4097)
            except FileNotFoundError:
                # 旧归档只读迁入：新监督者首次写入后，文件成为唯一当前状态。
                with self.connect() as db:
                    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='scheduler_state'").fetchone():
                        row=None
                    else:
                        size=db.execute('SELECT length(body) FROM scheduler_state WHERE id=1').fetchone()
                        if size and size[0]>4096:
                            raise ObservationError('scheduler_budget_exceeded','观察调度状态超过读取容量',503)
                        row=db.execute('SELECT body FROM scheduler_state WHERE id=1').fetchone()
                if row is None:return dict(enabled=False,state='not_configured',last_heartbeat=None)
                body=row[0]
            if len(body)>4096:
                raise ObservationError('scheduler_budget_exceeded','观察调度状态超过读取容量',503)
            status=json.loads(body);when=self._scheduler_fields(status)
            maximum=status['heartbeat_max_age_seconds']
            age=(datetime.now(timezone.utc)-when).total_seconds()
            if age<0 or status['enabled'] and age>maximum:status['state']='not_running_or_stale'
            return status
        except (KeyError,TypeError,ValueError,OverflowError,RecursionError):
            raise ObservationError('invalid_scheduler_status','观察调度状态无效',503) from None
        except OSError:
            raise ObservationError('scheduler_status_unavailable','观察调度状态暂不可用，请重新读取',503) from None

    def record_scheduler(self,status,*,lease=None):
        if not isinstance(lease,SchedulerLease):
            raise ObservationError('scheduler_owner_required','观察调度发布需要有效租约',409)
        lease.require(self)
        try:self._scheduler_fields(status)
        except (KeyError,TypeError,ValueError,OverflowError):
            raise ObservationError('invalid_scheduler_status','观察调度状态无效',422) from None
        body=encode(status)
        if len(body)>4096:
            raise ObservationError('scheduler_budget_exceeded','观察调度状态超过容量',422)
        # 心跳属于存续期调度事实；同一有效lease的唯一写者独立于大目录发布。
        _atomic_replace(self.root/'scheduler-status.json',body)

    @staticmethod
    def _scheduler_fields(status):
        fields={'enabled','state','phase','last_heartbeat','heartbeat_max_age_seconds','schedule','error_code'}
        if type(status) is not dict or set(status)!=fields:raise ValueError('scheduler fields')
        enabled=status['enabled'];maximum=status['heartbeat_max_age_seconds'];schedule=status['schedule']
        if (type(enabled) is not bool or status['state']!=('running' if enabled else 'stopped')
                or status['phase'] not in (('waiting','collecting','archiving') if enabled else ('stopped',))
                or type(maximum) not in (int,float) or not 0<maximum<=660
                or schedule!={'timezone':'Asia/Shanghai','times':['09:00']} or status['error_code'] is not None
                or type(status['last_heartbeat']) is not str or len(status['last_heartbeat'])>64):
            raise ValueError('scheduler identity')
        when=datetime.fromisoformat(status['last_heartbeat'])
        if when.tzinfo is None or when.utcoffset() is None:raise ValueError('scheduler timezone')
        return when

    @contextmanager
    def collection_lease(self):
        with self._lease('collection.sqlite3') as acquired:yield acquired

    @contextmanager
    def scheduler_lease(self):
        """独立于批次锁；正常退出和崩溃均由连接/OS释放唯一调度资格。"""
        with self._lease('scheduler.sqlite3') as acquired:
            if not acquired:
                yield None
                return
            # 仅保持连接，不保持读事务；原PASSIVE checkpoint仍可推进，WAL不因心跳频繁开闭。
            with self.connect() as directory:
                directory.execute('SELECT version FROM current WHERE id=1').fetchone()
                owner=SchedulerLease(self)
                try:yield owner
                finally:owner.active=False

    @contextmanager
    def _lease(self,name):
        database = sqlite3.connect(self.root / name, timeout=0)
        acquired = False
        try:
            try:
                database.execute('BEGIN IMMEDIATE')
                acquired = True
            except sqlite3.OperationalError as exc:
                if exc.sqlite_errorcode not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                    raise
            yield acquired
        finally:
            database.close()
