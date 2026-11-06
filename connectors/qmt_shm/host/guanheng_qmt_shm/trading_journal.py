"""QST-R10：同一通信 Journal 的持久命令身份。

继承的 owner 和 SQLite 事务串行化读写通信事实。调用方须等 claim_trade
成功返回后才能外发；该方法失败时保留原身份。SDK 回执归来源所有，Host
重启/中断原因单独记录。本模块不授交易权限、来源或柜台就绪资格。
"""
from __future__ import annotations

from contextlib import contextmanager
import math
import sqlite3
import time

from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.trading_contract import (
    validate_trade_binding, validate_trade_command, command_digest,
    validate_call_result)
from .bound import digest, request_id, sha256_text, MAX_METADATA_BYTES, MAX_REQUEST_BYTES
from .bound_journal import BoundReadJournal
from .journal import JournalConflict, JournalFull
from .trade_event_records import (TABLES as EVENT_TABLES, CONTINUITY_TABLES,
    CONTINUITY_VERSION, TradeEventRecords)
from .trade_order_links import TABLES as ORDER_LINK_TABLES, TradeOrderLinks, OrderSourceUnavailable
from .trade_binding_extension import BindingVersions, TABLES as BINDING_VERSION_TABLES


_COLUMNS = ('command_id', 'command_sha256', 'body', 'state', 'admitted_binding',
    'dispatch_binding', 'result_binding', 'source_result', 'result_sha256',
    'host_reason', 'queued_at', 'expires_at', 'started_at', 'reserved_bytes',
    'sdk_user_order_id', 'original_command_id')
_TERMINAL = frozenset(('definitely_not_called', 'sdk_returned', 'unknown'))
_HOST_REASONS = frozenset(('owner_restarted', 'deadline_expired',
    'source_binding_changed', 'deadline_unavailable', 'interrupted'))


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def validate_trade_journal_configuration(trade_binding, *, max_trade_commands,
                                        max_trade_bytes, max_trade_result_bytes):
    """纯校验交易存储身份及逻辑额度；配置和实际 Journal 共用此实现。

    返回私有绑定副本与规范身份 bytes，不打开存储或获取 owner。原命令的
    每条实际 reservation 仍由 Journal 受理时计算，终态继续占用原额度。
    """
    frozen = validate_trade_binding(trade_binding)
    if (type(max_trade_commands) is not int or not 1 <= max_trade_commands <= 4096
            or type(max_trade_result_bytes) is not int
            or not 1024 <= max_trade_result_bytes <= 2097152
            or type(max_trade_bytes) is not int):
        raise ValueError('invalid explicit trade Journal budget or clocks')
    identity_bytes = canonical({'schema_version': 'qmt.trade-journal.v1',
        'trade_binding': frozen, 'max_trade_commands': max_trade_commands,
        'max_trade_bytes': max_trade_bytes, 'max_trade_result_bytes': max_trade_result_bytes})
    unit = MAX_REQUEST_BYTES + max_trade_result_bytes + MAX_METADATA_BYTES
    if not (len(identity_bytes) + max_trade_result_bytes + MAX_METADATA_BYTES
            < max_trade_bytes <= len(identity_bytes) + max_trade_commands * unit):
        raise ValueError('invalid explicit trade logical byte budget')
    return frozen, identity_bytes


class CancelPending(JournalConflict):
    """同一原insert已有唯一实际未决取消；本新UUID尚未登记。"""


class _DeadlineCursor:
    """只检查交易取值前后截止；游标、连接及事务仍由继承 owner 管理。"""
    def __init__(self, cursor, check):
        self._cursor, self._check = cursor, check

    def fetchone(self):
        self._check()
        value = self._cursor.fetchone()
        self._check()
        return value

    def fetchall(self):
        self._check()
        value = self._cursor.fetchall()
        self._check()
        return value


class _DeadlineDatabase:
    """有限 SQL 截止代理；不暴露 commit/rollback/close 或拥有连接。"""
    def __init__(self, database, check):
        self._database, self._check = database, check

    def execute(self, sql, parameters=()):
        self._check()
        cursor = self._database.execute(sql, parameters)
        self._check()
        return _DeadlineCursor(cursor, self._check)


class HostTradingJournal(BoundReadJournal):
    """同一 BoundReadJournal 的版本化交易扩展，共用 owner、锁与 SQLite 文件。

    max_journal_bytes 保持原读额度；max_trade_bytes 包含交易 identity 原文、
    每命令原字节、最大结果预留及有界 metadata 预留。总逻辑上限为两者之和，
    终态记录保留。注入的 clock 须与调用者使用同一 monotonic 域；事务锁和
    SQLite 等待仍沿继承算法使用真实原始 I/O 截止，单位均为秒。

    submit/get/finish/interrupt 返回无别名 record；未知 ID 的 get 返回 None。
    claim 返回 record 加本 owner 原 deadline/剩余 ttl_ms，空队列或已有一个
    dispatching 时返回 None。返回 body 是原始 bytes；result_sha256 对规范
    source_result 字节取摘要；host_reason 只表达 Host 原因。所有方法要求
    调用方原绝对 deadline，冲突/容量/截止/SQLite 错误向调用者传播。
    admitted/actual/received B 须来自上层认证 owner，本模块只核精确关系。
    connection_continuity 默认 None；显式版本仅授事件认证续接，仍保留原命令
    精确绑定及业务截止。附属续接表要求每次重开都显式选择同一版本。
    trade_binding_extension默认None，保持原精确身份；显式版本仅接受原库已采用
    的current绑定。binding_extension_maintenance默认False，仅维护构造可准备/
    采用且禁止新交易受理/派发；原命令查询始终保留。
    """
    schema_tables = (BoundReadJournal.schema_tables
        | frozenset(('trade_identity', 'trade_commands')) | EVENT_TABLES | CONTINUITY_TABLES | ORDER_LINK_TABLES | BINDING_VERSION_TABLES)

    def __setattr__(self, name, value):
        if name in {'max_trade_commands', 'max_trade_bytes', 'max_trade_result_bytes',
                    '_trade_identity_bytes', '_trade_binding_bytes', '_clock', '_wall_clock',
                    '_event_records', '_order_links', '_binding_versions'} and hasattr(self, name):
            raise AttributeError('trade Journal admission configuration is frozen')
        super().__setattr__(name, value)

    def __init__(self, path, route, *, max_records, max_result_bytes,
                 max_request_bytes, max_journal_bytes, trade_binding,
                 max_trade_commands, max_trade_bytes, max_trade_result_bytes,
                 read_profile=None, clock=time.monotonic, wall_clock=time.time,
                 event_storage=None, connection_continuity=None, trade_binding_extension=None, binding_extension_maintenance=False):
        if (connection_continuity not in (None, CONTINUITY_VERSION)
                or connection_continuity is not None and event_storage is None):
            raise ValueError('explicit event authentication continuity configuration required')
        frozen, identity_bytes = validate_trade_journal_configuration(trade_binding,
            max_trade_commands=max_trade_commands, max_trade_bytes=max_trade_bytes,
            max_trade_result_bytes=max_trade_result_bytes)
        if not callable(clock) or not callable(wall_clock):
            raise ValueError('invalid explicit trade Journal budget or clocks')
        self.max_trade_commands = max_trade_commands
        self.max_trade_result_bytes = max_trade_result_bytes
        self.max_trade_bytes = max_trade_bytes
        self._trade_binding_bytes = canonical(frozen)
        self._trade_identity_bytes = identity_bytes
        self._clock, self._wall_clock = clock, wall_clock
        self._binding_versions=BindingVersions(self,trade_binding_extension,binding_extension_maintenance)
        self._binding_opening=True
        self._trade_deadlines = {}
        self._trade_failed = False
        self._trade_hard_fault = None
        self._order_links = TradeOrderLinks(self)
        read_profile = None if read_profile is None else decode(canonical(read_profile))
        events = (None if event_storage is None
            else TradeEventRecords(self,event_storage,read_profile,max_result_bytes=max_result_bytes,
                                  connection_continuity=connection_continuity, **self._event_record_arguments(read_profile)))
        self._event_records = events
        super().__init__(path, route, max_records=max_records,
            max_result_bytes=max_result_bytes, max_request_bytes=max_request_bytes,
            max_journal_bytes=max_journal_bytes, read_profile=read_profile)
        try:
            with self._transaction() as db:
                tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if connection_continuity is None and tables & CONTINUITY_TABLES:
                    raise JournalConflict('event authentication continuity requires explicit configuration')
                if event_storage is None and tables & EVENT_TABLES:
                    raise JournalConflict('event communication storage requires explicit configuration')
                if ('trade_identity' in tables) != ('trade_commands' in tables):
                    raise JournalConflict('incomplete trade Journal schema')
                db.execute('CREATE TABLE IF NOT EXISTS trade_identity (id INTEGER PRIMARY KEY CHECK(id=1), value BLOB NOT NULL)')
                db.execute('''CREATE TABLE IF NOT EXISTS trade_commands (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    command_id TEXT UNIQUE NOT NULL, command_sha256 TEXT NOT NULL,
                    body BLOB NOT NULL, state TEXT NOT NULL, admitted_binding BLOB NOT NULL,
                    dispatch_binding BLOB, result_binding BLOB, source_result BLOB,
                    result_sha256 TEXT, host_reason TEXT, queued_at REAL NOT NULL,
                    expires_at REAL NOT NULL, started_at REAL, reserved_bytes INTEGER NOT NULL,
                    sdk_user_order_id TEXT UNIQUE, original_command_id TEXT)''')
                if ({row[1] for row in db.execute('PRAGMA table_info(trade_identity)')} != {'id', 'value'}
                        or {row[1] for row in db.execute('PRAGMA table_info(trade_commands)')} != set(_COLUMNS) | {'seq'}):
                    raise JournalConflict('unknown trade Journal columns')
                identities = db.execute('SELECT id,value FROM trade_identity').fetchall()
                count = db.execute('SELECT COUNT(*) FROM trade_commands').fetchone()[0]
                if identities:
                    if len(identities) != 1 or identities[0][0] != 1 or (bytes(identities[0][1]) != self._trade_identity_bytes and not self._binding_versions.trade_identity_matches(bytes(identities[0][1]))):
                        raise JournalConflict('trade Journal identity differs')
                elif count:
                    raise JournalConflict('retained trade facts lack their identity')
                else:
                    db.execute('INSERT INTO trade_identity VALUES(1,?)', (self._trade_identity_bytes,))
                # 事件身份和原文先在同一事务验证，再恢复命令；新扩展没有第二个owner。
                if events is not None:
                    events.initialize(db)
                if count > self.max_trade_commands or self._trade_used(db) > self.max_trade_bytes:
                    raise JournalFull('retained trade facts exceed explicit budget')
                # 恢复前验证保留身份；UTC 仅供描述，不重建上一 owner 的 monotonic D。
                for row in db.execute('SELECT ' + ','.join(_COLUMNS) + ' FROM trade_commands').fetchall():
                    self._record(row)
                self._order_links.initialize(db)
                db.execute("UPDATE trade_commands SET state='definitely_not_called',host_reason='owner_restarted' WHERE state='queued'")
                db.execute("UPDATE trade_commands SET state='unknown',host_reason='owner_restarted' WHERE state='dispatching'")
                self._admission_facts(db)
            self._binding_opening=False
        except BaseException:
            self.close()
            raise

    @contextmanager
    def _transaction(self,deadline=None):
        with super()._transaction(deadline) as db:
            if self._binding_opening:self._binding_versions.opening(db)
            yield db

    def prepare_binding_extension(self,new_binding,authorization_sha256,rule_changes,*,deadline):
        """仅原独占维护owner纯核prepare；不重写配对、命令、事件或读票据。"""
        return self._binding_versions.prepare(new_binding,authorization_sha256,rule_changes,deadline=deadline)

    def adopt_binding_extension(self,plan,*,deadline):
        """沿同一SQLite原事务CAS采用；随后关闭维护owner，用新绑定重开。"""
        return self._binding_versions.adopt(plan,deadline=deadline)

    def _historical_event_identity_matches(self,raw):
        return self._binding_versions.event_identity_matches(raw)

    def _historical_retention_identity_matches(self,raw):
        return self._binding_versions.retention_identity_matches(raw)

    def _historical_profile_hashes(self):
        return self._binding_versions.profile_hashes()

    @property
    def trade_binding(self):
        return decode(self._trade_binding_bytes)

    def _event_record_arguments(self, read_profile):
        """附加 owner 可显式提供读取身份关系；原交易事件默认保持严格身份。"""
        return {}

    def _historical_read_profile_matches(self, binding):
        """只核已有持久proof；新来源准入仍由完整认证profile校验。"""
        return binding['capability_sha256'] in ({digest(canonical(self.admission_profile))}|self._historical_profile_hashes())

    def _bound_result_saved(self, db, rid, request, result, deadline):
        # 原读结果和原委托通信观察一起提交；失败均回滚，GET不触发认领。
        self._order_links.ingest_query(db, rid, request, result, deadline=deadline)

    @property
    def events(self):
        return self._event_records

    def _check_io(self, deadline):
        # I/O 与继承事务共享真实 monotonic 域；业务时钟失效后，
        # 原身份/回执仍可在独立 I/O 预算内领取。
        now = time.monotonic()
        if now >= deadline:
            raise TimeoutError('trade Journal IO deadline elapsed')
        return now

    @contextmanager
    def _trade_lock(self, deadline):
        if not _finite(deadline):
            raise ValueError('absolute monotonic deadline required')
        self._check_io(deadline)
        if not self._lock.acquire(timeout=max(0, deadline - time.monotonic())):
            raise TimeoutError('Journal transaction busy; retain its owner')
        try:
            self._check_io(deadline)
            yield
        finally:
            self._lock.release()

    @contextmanager
    def _trade_transaction(self, deadline):
        with self._trade_lock(deadline):
            commit_attempted = False
            try:
                # 连接、PRAGMA、BEGIN、提交/回滚和 close 完整沿继承算法。
                # 已开始的 SQLite/OS I/O 无法瞬时取消；yield 边界拒绝
                # connect/BEGIN 晚回，SQL 代理和提交前后检查拒绝后续晚回。
                with self._transaction(deadline) as db:
                    self._check_io(deadline)
                    yield _DeadlineDatabase(db, lambda: self._check_io(deadline))
                    self._check_io(deadline)
                    commit_attempted = True
                self._check_io(deadline)
            except sqlite3.Error:
                self._fail_trade('journal_unavailable')
                raise
            except TimeoutError:
                if commit_attempted:
                    # COMMIT 已开始则可能持久生效；原记录保留，新写锁闭。
                    self._fail_trade('journal_unavailable')
                raise

    def _now(self, clock):
        try:
            value = clock()
            if not _finite(value):
                raise ValueError()
            return value
        except Exception:
            self._fail_trade('clock_unavailable')
            raise JournalConflict('trade Journal clock unavailable') from None

    def _trade_used(self, db):
        return len(self._trade_identity_bytes) + self._binding_versions.logical_bytes(db) + db.execute(
            'SELECT COALESCE(SUM(reserved_bytes),0) FROM trade_commands').fetchone()[0]

    def _fail_trade(self, code):
        self._trade_failed = True
        if self._trade_hard_fault is None:
            self._trade_hard_fault = code

    def _admission_facts(self, db):
        conflict = db.execute("""SELECT original_command_id FROM trade_commands
            WHERE original_command_id IS NOT NULL AND state IN ('queued','dispatching','unknown')
            GROUP BY original_command_id HAVING COUNT(*)>1 LIMIT 1""").fetchone()
        if conflict is not None:
            self._fail_trade('cancel_pending_conflict')
        if self._order_links.has_errors(db):
            self._fail_trade('order_association_conflict')
        if self._trade_failed and self._trade_hard_fault is None:
            self._fail_trade('journal_unavailable')
        unresolved = False
        cursor = db.execute('SELECT ' + ','.join(_COLUMNS) + " FROM trade_commands WHERE state='unknown'")
        for unused in range(self.max_trade_commands + 1):
            row = cursor.fetchone()
            if row is None:
                break
            try:
                resolved = self._order_links.resolves_unknown(db, self._record(row))
            except JournalConflict:
                # 原证明校验已锁存硬错，状态查询继续报告保护事实。
                resolved = False
            if not resolved:
                unresolved = True
                break
        else:
            self._fail_trade('trade_record_invalid')
            raise JournalConflict('unknown trade count exceeds retained capacity')
        return {'unknown_fenced': unresolved,
            'hard_fault': None if self._trade_hard_fault is None else {'code': self._trade_hard_fault}}

    def _admission_open(self, db, operation='order.insert', cancel_admission=False):
        facts = self._admission_facts(db)
        return (facts['hard_fault'] is None and (not facts['unknown_fenced']
            or operation == 'order.cancel' and cancel_admission))

    def _admission(self, db, operation='order.insert', cancel_admission=False):
        if self._binding_versions.maintenance:
            raise JournalConflict('binding maintenance cannot admit or dispatch new trades')
        if not self._admission_open(db, operation, cancel_admission):
            raise JournalConflict('trade admission closed; retain original identities')

    def _cancel_records(self, db, original):
        # 原集合有界逐项校验，只保留最新终态候选及至多一个未决实际记录。
        cursor = db.execute('SELECT command_id FROM trade_commands WHERE original_command_id=? ORDER BY seq DESC LIMIT ?',
            (original['command_id'], self.max_trade_commands+1))
        latest, pending = None, []
        link = self._order_links._link(db, original['command_id'])
        for index in range(self.max_trade_commands+1):
            row = cursor.fetchone()
            if row is None:
                return latest, pending
            if index == self.max_trade_commands:
                self._fail_trade('cancel_pending_conflict')
                raise JournalConflict('retained cancel capacity differs')
            record = self._record(self._select(db, row[0]))
            command = decode(record['body'])
            if (command['operation'] != 'order.cancel' or any(command[key] != original[key]
                    for key in ('account_id', 'account_type', 'binding_id', 'entrust_id', 'user_tag'))
                    or command['broker_order_id'] != link['broker_order_id']):
                self._fail_trade('order_proof_invalid')
                raise JournalConflict('retained cancel original identity differs')
            if latest is None:
                latest = record
            if record['state'] in ('queued','dispatching','unknown'):
                if pending:
                    self._fail_trade('cancel_pending_conflict')
                    raise JournalConflict('multiple pending cancels for original insert')
                pending.append(record)
        return latest, pending

    def _current_source(self, actual, current_session):
        if current_session is None:
            return None
        if (type(current_session) is not str or not 1 <= len(current_session) <= 128
                or not current_session.strip() or any(not 32 <= ord(c) < 127 for c in current_session)):
            raise ValueError('invalid current source session')
        return {'host_binding': decode(actual), 'session_id': current_session}

    def _source(self, value):
        checked = self._validated_binding(value)
        if checked['route'] != self.route:
            raise JournalConflict('trade source route differs')
        return canonical(checked)

    def _command(self, body):
        if type(body) is not bytes or not 1 <= len(body) <= MAX_REQUEST_BYTES:
            raise ValueError('bounded original canonical command bytes required')
        command = validate_trade_command(decode(body))
        if canonical(command) != body:
            raise JournalConflict('trade command bytes are not canonical')
        fixed = self.trade_binding
        if any(command[key] != fixed[key] for key in ('binding_id', 'account_id', 'account_type')):
            raise JournalConflict('trade command binding differs')
        return command

    def _select(self, db, cid):
        return db.execute('SELECT ' + ','.join(_COLUMNS) + ' FROM trade_commands WHERE command_id=?', (cid,)).fetchone()

    def _record(self, row):
        try:
            return self._decode_record(row)
        except (JournalConflict, ValueError, TypeError, KeyError, OverflowError):
            self._fail_trade('trade_record_invalid')
            raise JournalConflict('retained trade record is invalid') from None

    def _decode_record(self, row):
        if row is None:
            return None
        stored = dict(zip(_COLUMNS, row))
        body = bytes(stored['body'])
        command = self._command(body)
        if stored['command_id'] != command['command_id'] or stored['command_sha256'] != command_digest(command):
            raise JournalConflict('stored trade command identity differs')
        expected_reservation = len(body) + self.max_trade_result_bytes + MAX_METADATA_BYTES
        if (stored['reserved_bytes'] != expected_reservation
                or stored['sdk_user_order_id'] != command.get('sdk_user_order_id')
                or stored['original_command_id'] != command.get('original_command_id')
                or stored['state'] not in _TERMINAL | {'queued', 'dispatching'}
                or any(not _finite(stored[key]) for key in ('queued_at', 'expires_at'))):
            raise JournalConflict('stored trade metadata differs')
        admitted = self._source(decode(bytes(stored['admitted_binding'])))
        dispatched, received = stored['dispatch_binding'], stored['result_binding']
        if ((dispatched is not None and bytes(dispatched) != admitted)
                or (received is not None and (dispatched is None or bytes(received) != bytes(dispatched)))):
            raise JournalConflict('stored trade source identity differs')
        result = stored['source_result']
        reason = stored['host_reason']
        if result is not None:
            raw = bytes(result)
            checked = validate_call_result(decode(raw), command)
            if (canonical(checked) != raw or len(raw) > self.max_trade_result_bytes
                    or digest(raw) != stored['result_sha256'] or received is None
                    or stored['state'] != checked['stage'] or reason is not None):
                raise JournalConflict('stored trade result identity differs')
        else:
            checked = None
            if stored['result_sha256'] is not None or received is not None:
                raise JournalConflict('stored trade result identity missing')
            if stored['state'] in _TERMINAL:
                if reason not in _HOST_REASONS or stored['state'] == 'sdk_returned':
                    raise JournalConflict('stored Host terminal reason differs')
            elif reason is not None:
                raise JournalConflict('pending trade cannot have terminal reason')
        if ((stored['state'] == 'queued' and dispatched is not None)
                or (stored['state'] in ('dispatching', 'sdk_returned', 'unknown') and dispatched is None)
                or (dispatched is not None and not _finite(stored['started_at']))):
            raise JournalConflict('stored trade dispatch identity missing')
        return {'schema_version': 'qmt.trade-record.v1', 'command_id': command['command_id'],
            'command_sha256': stored['command_sha256'], 'body': body,
            'state': stored['state'], 'admitted_binding': decode(admitted),
            'dispatch_binding': decode(bytes(dispatched)) if dispatched is not None else None,
            'result_binding': decode(bytes(received)) if received is not None else None,
            'source_result': checked, 'result_sha256': stored['result_sha256'],
            'host_reason': reason, 'queued_at': stored['queued_at'],
            'expires_at': stored['expires_at'], 'started_at': stored['started_at']}

    def submit_trade(self, body, admitted_binding, *, ttl_ms, deadline, business_deadline=None,
                     cancel_admission=False, current_session=None):
        command = self._command(body)
        admitted = self._source(admitted_binding)
        if type(ttl_ms) is not int or not 1 <= ttl_ms <= 300000:
            raise ValueError('invalid trade TTL')
        if business_deadline is not None and not _finite(business_deadline):
            raise ValueError('finite original trade business deadline required')
        if type(cancel_admission) is not bool or cancel_admission and current_session is None:
            raise ValueError('explicit current cancel admission required')
        current_source = self._current_source(admitted, current_session)
        cid = command['command_id']
        with self._trade_lock(deadline):
            with self._trade_transaction(deadline) as db:
                existing = self._record(self._select(db, cid))
                if existing is not None:
                    if existing['body'] != body:
                        raise JournalConflict('trade identity already has different bytes')
                    # 重连只领取原记录；传入的新 B 不覆盖原 B，也不延长 D。
                    return existing
                if self._binding_versions.version is not None:
                    if admitted_binding['capability_sha256']!=digest(canonical(self.admission_profile)):
                        raise JournalConflict('new trade requires current binding profile')
                self._admission(db, command['operation'], cancel_admission)
                token = command.get('sdk_user_order_id')
                original = command.get('original_command_id')
                if token is not None and db.execute('SELECT 1 FROM trade_commands WHERE sdk_user_order_id=?', (token,)).fetchone():
                    raise JournalConflict('source token already belongs to another command')
                if original is not None:
                    prior = self._record(self._select(db, original))
                    if prior is None:
                        raise JournalConflict('cancel original command is unknown')
                    prior_command = decode(prior['body'])
                    if (prior_command['operation'] != 'order.insert' or any(
                            command[key] != prior_command[key] for key in
                            ('account_id', 'account_type', 'binding_id', 'entrust_id', 'user_tag'))):
                        raise JournalConflict('cancel original identity differs')
                    self._order_links.validate_cancel(db, command, current_source)
                    unused, pending = self._cancel_records(db, prior_command)
                now = self._now(self._clock)
                original_deadline = now + ttl_ms / 1000 if business_deadline is None else business_deadline
                if business_deadline is not None:
                    if original_deadline <= now:
                        raise TimeoutError('original trade business deadline elapsed before admission')
                    if original_deadline - now > ttl_ms / 1000:
                        raise ValueError('original trade business deadline exceeds configured TTL')
                # 原D/目标proof先核，未决识别先于新增count/bytes额度。
                if original is not None and pending:
                    raise CancelPending('original insert has a pending cancel')
                reservation = len(body) + self.max_trade_result_bytes + MAX_METADATA_BYTES
                if (db.execute('SELECT COUNT(*) FROM trade_commands').fetchone()[0] >= self.max_trade_commands
                        or self._trade_used(db) + reservation > self.max_trade_bytes):
                    raise JournalFull('trade communication capacity exhausted')
                # quota消耗同一原业务D；重读剩余时间，既不续TTL也不登记已过D的新UUID。
                now = self._now(self._clock)
                if original_deadline <= now:
                    raise TimeoutError('original trade business deadline elapsed after quota')
                utc = self._now(self._wall_clock)
                db.execute('''INSERT INTO trade_commands
                    (command_id,command_sha256,body,state,admitted_binding,queued_at,
                     expires_at,reserved_bytes,sdk_user_order_id,original_command_id)
                    VALUES(?,?,?,'queued',?,?,?,?,?,?)''',
                    (cid, command_digest(command), body, admitted, utc,
                     utc + original_deadline - now, reservation, token, original))
                if command['operation'] == 'order.insert':
                    self._order_links.reserve_insert(db, command)
                accepted = self._record(self._select(db, cid))
            # 首次业务 D = 首次受理 monotonic + TTL，独立于本次 I/O D。
            # 提交成功后同锁安装缓存；回滚不留下游离缓存，提交不明锁闭新写。
            self._trade_deadlines[cid] = original_deadline
            return accepted

    def claim_trade(self, actual_binding, *, deadline, cancel_admission=False, current_session=None):
        actual = self._source(actual_binding)
        if type(cancel_admission) is not bool or cancel_admission and current_session is None:
            raise ValueError('explicit current cancel admission required')
        current_source = self._current_source(actual, current_session)
        # 外层同一 RLock 持有至提交后业务 D 复核及 ttl 计算完成，竞争
        # 调用无法在晚提交与 admission latch 之间进入。
        with self._trade_lock(deadline):
            with self._trade_transaction(deadline) as db:
                # Runtime缓存与本事务间可新锁存硬错。关闭准入属于空领取，
                # 后续status/event/ACK继续；实际proof/存储异常仍原样传播。
                if not self._admission_open(db,
                        'order.cancel' if cancel_admission else 'order.insert', cancel_admission):
                    return None
                if db.execute("SELECT 1 FROM trade_commands WHERE state='dispatching' LIMIT 1").fetchone():
                    return None
                claimed = None
                rows = db.execute("SELECT command_id FROM trade_commands WHERE state='queued' ORDER BY seq LIMIT ?",
                    (self.max_trade_commands+1,)).fetchall()
                if len(rows) > self.max_trade_commands:
                    self._fail_trade('journal_unavailable')
                    raise JournalConflict('queued trade capacity differs')
                for row in rows:
                    self._check_io(deadline)
                    record = self._record(self._select(db, row[0]))
                    cid = record['command_id']
                    original_deadline = self._trade_deadlines.get(cid)
                    now = self._now(self._clock)
                    reason = None
                    if canonical(record['admitted_binding']) != actual:
                        reason = 'source_binding_changed'
                    elif original_deadline is None:
                        reason = 'deadline_unavailable'
                    elif int((original_deadline - now) * 1000) <= 0:
                        reason = 'deadline_expired'
                    if reason:
                        db.execute("UPDATE trade_commands SET state='definitely_not_called',host_reason=? WHERE command_id=?", (reason, cid))
                        continue
                    command = decode(record['body'])
                    facts = self._admission_facts(db)
                    if facts['unknown_fenced'] and command['operation'] == 'order.insert':
                        continue
                    self._admission(db, command['operation'], cancel_admission)
                    if command['operation'] == 'order.cancel':
                        try:
                            self._order_links.validate_cancel(db, command, current_source)
                        except OrderSourceUnavailable:
                            db.execute("UPDATE trade_commands SET state='definitely_not_called',host_reason='source_binding_changed' WHERE command_id=?", (cid,))
                            continue
                        original = decode(self._record(self._select(db, command['original_command_id']))['body'])
                        self._cancel_records(db, original)
                    db.execute("UPDATE trade_commands SET state='dispatching',dispatch_binding=?,started_at=? WHERE command_id=?",
                        (actual, self._now(self._wall_clock), cid))
                    claimed = self._record(self._select(db, cid))
                    break
                if claimed is None:
                    return None
            # 此时 COMMIT 已返回。仅使用原业务 D，提交耗时必须从剩余 TTL
            # 扣除；晚回保留已可能提交的 dispatching，重开按 unknown 恢复。
            try:
                self._check_io(deadline)
                now = self._now(self._clock)
                # 注入的业务时钟也可能晚回；返回派发记录前再次核原 I/O D。
                self._check_io(deadline)
                remaining = int((original_deadline - now) * 1000)
                if remaining <= 0:
                    raise TimeoutError('trade business deadline elapsed after commit')
            except BaseException:
                self._fail_trade('journal_unavailable')
                raise
            claimed.update(deadline=original_deadline, ttl_ms=remaining)
            return claimed

    def finish_trade(self, command_id, result, received_binding, *, deadline):
        cid = request_id(command_id)
        received = self._source(received_binding)
        with self._trade_transaction(deadline) as db:
            record = self._record(self._select(db, cid))
            if record is None or record['dispatch_binding'] is None or canonical(record['dispatch_binding']) != received:
                raise JournalConflict('trade result differs from original dispatch')
            checked = validate_call_result(result, decode(record['body']))
            raw = canonical(checked)
            if len(raw) > self.max_trade_result_bytes:
                raise JournalFull('trade result exceeds reserved capacity')
            if record['source_result'] is not None:
                if canonical(record['source_result']) != raw:
                    raise JournalConflict('trade result already has different content')
                return record
            if record['state'] != 'dispatching':
                raise JournalConflict('trade result has no active original dispatch')
            db.execute('''UPDATE trade_commands SET state=?,source_result=?,result_sha256=?,
                result_binding=? WHERE command_id=?''',
                (checked['stage'], raw, digest(raw), received, cid))
            return self._record(self._select(db, cid))

    def interrupt_trade(self, command_id, *, deadline):
        cid = request_id(command_id)
        with self._trade_transaction(deadline) as db:
            record = self._record(self._select(db, cid))
            if record is None:
                raise JournalConflict('trade interruption identity unknown')
            # 迟到中断保留已提交 SDK 事实；中断先提交则保持 unknown。
            if record['state'] in _TERMINAL:
                return record
            if record['state'] != 'dispatching':
                raise JournalConflict('trade interruption lacks original dispatch')
            db.execute("UPDATE trade_commands SET state='unknown',host_reason='interrupted' WHERE command_id=?", (cid,))
            return self._record(self._select(db, cid))

    def get_trade(self, command_id, *, deadline):
        cid = request_id(command_id)
        with self._trade_transaction(deadline) as db:
            return self._record(self._select(db, cid))

    def trade_admission(self, *, deadline):
        """原事务内分别读取尚待核查的责任与硬故障；原命令结果保持。"""
        with self._trade_transaction(deadline) as db:
            return self._admission_facts(db)

    def has_observed_unknown_trade(self, *, deadline):
        """原unknown记录仍存在且全部获ORDER终态证明，才授本地等待退役依据。"""
        with self._trade_transaction(deadline) as db:
            present = db.execute("SELECT 1 FROM trade_commands WHERE state='unknown' LIMIT 1").fetchone()
            facts = self._admission_facts(db)
            return present is not None and not facts['unknown_fenced'] and facts['hard_fault'] is None

    def has_unknown_trade(self, *, deadline):
        """旧接口保留共用阻写意义；新调度使用独立trade_admission事实。"""
        facts = self.trade_admission(deadline=deadline)
        return facts['unknown_fenced'] or facts['hard_fault'] is not None

    def lookup_trade_cancel(self, original_command_id, original_command_sha256, *, deadline):
        cid, sha = request_id(original_command_id), sha256_text(original_command_sha256)
        with self._trade_transaction(deadline) as db:
            record = self._record(self._select(db, cid))
            if record is None:
                return None
            original = decode(record['body'])
            if original['operation'] != 'order.insert' or record['command_sha256'] != sha:
                raise JournalConflict('cancel lookup original identity differs')
            reference = self._order_links.lookup(db, {key: original[key] for key in ('entrust_id','user_tag')})
            if reference is None or reference['association_error'] is not None:
                raise JournalConflict('cancel lookup original association differs')
            latest, pending = self._cancel_records(db, original)
            return {'schema_version': 'qmt.trade-cancel-reference.v1',
                'original_command_id': cid, 'original_command_sha256': sha,
                'cancel': pending[0] if pending else latest}

    def lookup_trade_order(self, identity, *, deadline):
        """按原 WT 身份或完整 token 读取通信关联；断连/关闭写时仍可核查。"""
        with self._trade_transaction(deadline) as db:
            return self._order_links.lookup(db, identity)
