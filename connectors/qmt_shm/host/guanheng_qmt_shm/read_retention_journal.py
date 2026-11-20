"""已确认读责任回收；账户观察原期限结束后释放交付额度，未知及金融证明保留。"""
from contextlib import contextmanager
import threading
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_retention import (retention, validate_identity,
    require_live, ended, CONSUMED, LOOKUP, result_confirmed)
from .bound import digest, unb64, sha256_text
from .bound_journal import BoundReadJournal
from .history_preparation_journal import HistoryPreparationJournal
from .trading_journal import HostTradingJournal
from .journal import JournalConflict


recyclable = result_confirmed


class _RetainedJournal:
    schema_tables = BoundReadJournal.schema_tables | {'read_retention_identity', 'read_retention'}
    _allow_legacy_initialization = False
    # 只有账户观察 owner 允许丢失消费确认的确定结果在原期限结束后回收。
    # 普通读取、HPR 和其他操作继续要求消费确认，金融引用另行阻止回收。
    _expire_account_observations = False

    def __init__(self, *args, clock, http_retention=None, **kwargs):
        profile = kwargs['read_profile']
        self.retention_capability = retention(profile['read_retention'] if http_retention is None else http_retention)
        self.retention_clock = clock
        self._ticket_context = threading.local()
        identity=dict(schema='qmt.read-journal-retention.v1',
            profile=profile, max_records=kwargs['max_records'],
            max_request_bytes=kwargs['max_request_bytes'], max_result_bytes=kwargs['max_result_bytes'],
            max_journal_bytes=kwargs['max_journal_bytes'])
        if http_retention is not None:
            if profile.get('read_profile_version')!='qmt.read-profile.v4' or 'read_retention'in profile:
                raise ValueError('distinct HTTP-only v4 retention required')
            identity.update(schema='qmt.http-read-journal-retention.v1',http_read_retention=self.retention_capability)
        self._retention_identity = canonical(identity)
        # 此标志只覆盖构造，数据库原事务持有文件 owner 后才校验，避免 TOCTOU。
        self._retention_opening = True
        super().__init__(*args, **dict(kwargs, **self._base_clock_arguments(clock)))
        self._retention_opening = False
        try:
            # 账户观察可重新查询；先让原 owner 完成路由、金融及事件身份验证，
            # 再附加读取元数据。已有无票据责任仍占原额度，绝不推断为可删除。
            if self._allow_legacy_initialization:
                with self._transaction() as db:
                    tables = self._tables(db)
                    if 'read_retention' not in tables:
                        self._initialize_retention(db)
        except BaseException:
            self.close()
            raise

    def _base_clock_arguments(self, clock):
        return {'clock': clock} if isinstance(self, RetainedPreparationJournal) else {}

    @staticmethod
    def _tables(db):
        return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT GLOB 'sqlite_*'")}

    def _initialize_retention(self, db):
        db.execute('CREATE TABLE read_retention_identity (id INTEGER PRIMARY KEY CHECK(id=1),value BLOB NOT NULL)')
        db.execute('INSERT INTO read_retention_identity VALUES(1,?)', (self._retention_identity,))
        db.execute('''CREATE TABLE read_retention (request_id TEXT PRIMARY KEY,
            ticket BLOB NOT NULL,consumed INTEGER NOT NULL DEFAULT 0)''')

    @contextmanager
    def _transaction(self, deadline=None):
        with super()._transaction(deadline) as db:
            fresh = False
            if self._retention_opening:
                tables = self._tables(db)
                fresh = not tables
                if tables:
                    retained_tables = tables & {'read_retention_identity', 'read_retention'}
                    legacy = self._allow_legacy_initialization and not retained_tables
                    if retained_tables and len(retained_tables) != 2:
                        raise JournalConflict('incomplete retained read Journal schema')
                    if not legacy and not _RetainedJournal.schema_tables <= tables:
                        raise JournalConflict('retained reads require a new or same-schema Journal')
                    if retained_tables:
                        if ({row[1] for row in db.execute('PRAGMA table_info(read_retention_identity)')} != {'id', 'value'}
                                or {row[1] for row in db.execute('PRAGMA table_info(read_retention)')} != {'request_id', 'ticket', 'consumed'}):
                            raise JournalConflict('unknown retained read Journal columns')
                        rows = db.execute('SELECT id,value FROM read_retention_identity').fetchall()
                        if len(rows) != 1 or rows[0][0] != 1 or (bytes(rows[0][1]) != self._retention_identity and not getattr(self,'_historical_retention_identity_matches',lambda raw:False)(bytes(rows[0][1]))):
                            raise JournalConflict('read retention Journal configuration differs')
            yield db
            if fresh and not self._allow_legacy_initialization:
                self._initialize_retention(db)

    def submit_ticket(self, body, admitted_binding, value, *, queue_timeout_ms, deadline=None):
        value = validate_identity(decode(body), value)
        if getattr(self._ticket_context, 'value', None) is not None:
            raise RuntimeError('read ticket admission is not reentrant')
        self._ticket_context.value = value
        try:
            return super().submit_bound(body, admitted_binding, queue_timeout_ms=queue_timeout_ms, deadline=deadline)
        finally:
            del self._ticket_context.value

    def _before_bound_admission(self, db, request, admitted, body):
        value = getattr(self._ticket_context, 'value', None)
        if value is None:
            raise JournalConflict('retained read admission requires an original ticket')
        require_live(request, value, self.retention_capability, admitted['host_instance_id'], self.retention_clock)
        self._reap(db, admitted['host_instance_id'])

    def _bound_admitted(self, db, rid, request, admitted, body):
        db.execute('INSERT INTO read_retention(request_id,ticket) VALUES(?,?)',
            (rid, canonical(self._ticket_context.value)))

    def read_reply_upper(self, rid, body, *, deadline):
        """Journal域内核原请求/票据，返回原绝对D的保守monotonic上界；不续期、不消费。"""
        import time
        from guanheng_qmt_shm_agent.read_retention import now_ms
        with self._transaction(deadline) as db:
            row=db.execute('SELECT o.body,r.ticket FROM read_operations o '
                'JOIN read_retention r USING(request_id) WHERE o.request_id=?',(rid,)).fetchone()
            if row is None or bytes(row[0])!=body:
                raise JournalConflict('original read wait ticket differs')
            value=validate_identity(decode(body),decode(bytes(row[1])))
            sampled=time.monotonic()
            return sampled+(value['expires_ms']-now_ms(self.retention_clock))/1000

    def _reap(self, db, epoch):
        count = 0
        # 在 SQL 中限定候选，避免其他通道每轮加载全部未消费终态的结果正文。
        rows = db.execute('''SELECT o.request_id,o.result,r.ticket
            FROM read_operations o JOIN read_retention r USING(request_id)
            WHERE o.state='terminal' AND (r.consumed=1
                OR (? AND o.operation_id='account.trade_detail'))''', (self._expire_account_observations,))
        for rid, raw, value in rows.fetchall():
            if (raw is not None and recyclable(decode(bytes(raw)))
                    and not self._read_held_by_financial_proof(db, rid)
                    and ended(decode(bytes(value)), epoch, self.retention_clock)):
                # 无 tombstone：原票据已失效，原 UUID 内容绑定不允许取得新准入。
                db.execute('DELETE FROM read_retention WHERE request_id=?', (rid,))
                db.execute('DELETE FROM read_operations WHERE request_id=?', (rid,))
                count += 1
        return count

    def _read_held_by_financial_proof(self, db, rid):
        return False

    def _retention_extra_counts(self):
        return {}

    def consumed(self, rid, value, epoch):
        if (type(value) is not dict or set(value) != {'schema', 'request_body_sha256', 'result_body_sha256'}
                or value['schema'] != CONSUMED):
            raise ValueError('invalid consumed read receipt')
        sha256_text(value['request_body_sha256']); sha256_text(value['result_body_sha256'])
        with self._transaction() as db:
            row = db.execute('SELECT body,result,state FROM read_operations WHERE request_id=?', (rid,)).fetchone()
            if row is None:
                return None
            if db.execute('SELECT 1 FROM read_retention WHERE request_id=?', (rid,)).fetchone() is None:
                raise JournalConflict('original read has no consumable retention ticket')
            if (row[2] != 'terminal' or row[1] is None or digest(bytes(row[0])) != value['request_body_sha256']
                    or digest(bytes(row[1])) != value['result_body_sha256']):
                raise JournalConflict('consumed receipt differs from original persisted result')
            db.execute('UPDATE read_retention SET consumed=1 WHERE request_id=?', (rid,))
            self._reap(db, epoch)
            retained = db.execute('SELECT 1 FROM read_operations WHERE request_id=?', (rid,)).fetchone() is not None
            return dict(schema='qmt.read-consumed-result.v1', request_id=rid, consumed=True, retained=retained)

    def lookup(self, rid, value, epoch):
        if (type(value) is not dict or set(value) != {'schema', 'ticket', 'request_body_b64', 'request_body_sha256'}
                or value['schema'] != LOOKUP):
            raise ValueError('invalid retained read lookup')
        body = unb64(value['request_body_b64'], self.max_request_bytes)
        if digest(body) != sha256_text(value['request_body_sha256']):
            raise ValueError('lookup original bytes differ')
        request = decode(body)
        self._validate_bound_request(request)
        original = validate_identity(request, value['ticket'])
        if rid != request['request_id']:
            raise ValueError('lookup path differs from original request')
        result = self.get_bound(rid)
        if result is not None:
            if result['request_body_sha256'] != digest(body):
                raise JournalConflict('lookup original content differs')
            return 200 if result['state'] == 'terminal' else 202, result
        return (410, 'read_ticket_ended_unretained') if ended(original, epoch, self.retention_clock) else (404, 'read_result_unconfirmed')

    def retention_status(self, epoch):
        with self._transaction() as db:
            self._reap(db, epoch)
            counts = dict(queued_or_running=0, held_unknown=0, awaiting_consumer=0, awaiting_ticket_end=0)
            counts.update(self._retention_extra_counts())
            legacy = 0
            for rid, state, raw, consumed, ticket_id in db.execute('''SELECT o.request_id,o.state,o.result,r.consumed,r.request_id FROM read_operations o
                    LEFT JOIN read_retention r USING(request_id)'''):
                if ticket_id is None:
                    legacy += 1
                    continue
                key = ('queued_or_running' if state != 'terminal' else 'held_unknown'
                    if raw is None or not recyclable(decode(bytes(raw))) else
                    'held_financial_proof' if self._read_held_by_financial_proof(db, rid) else
                    'awaiting_consumer' if not consumed else 'awaiting_ticket_end')
                counts[key] += 1
            return dict(schema='qmt.read-retention-status.v1', capacity=self.max_records,
                retained=sum(counts.values())+legacy, logical_bytes=self._used(db),
                **dict(counts, **({'legacy_records': legacy} if self._allow_legacy_initialization else {})))


class RetainedReadJournal(_RetainedJournal, BoundReadJournal):
    """独立普通只读连接；不接收交易或 bulk Journal。"""


class RetainedPreparationJournal(_RetainedJournal, HistoryPreparationJournal):
    """原 HPR 中断与截止算法保持，由本层接手已确认责任的回收。"""


class RetainedAccountJournal(_RetainedJournal, BoundReadJournal):
    """显式 v3；旧账户读责任保留，元数据在原身份验证后附加。"""
    _allow_legacy_initialization = True
    _expire_account_observations = True

    def __init__(self, *args, **kwargs):
        if kwargs.get('read_profile', {}).get('read_profile_version') != 'qmt.read-profile.v3':
            raise ValueError('explicit account retirement requires a v3 profile')
        super().__init__(*args, **kwargs)


class RetainedTradingJournal(_RetainedJournal, HostTradingJournal):
    """显式 v4；金融 Journal、事件、原预算及其事务继续由原 owner 管理。"""
    schema_tables = HostTradingJournal.schema_tables | {'read_retention_identity', 'read_retention'}
    _allow_legacy_initialization = True
    _expire_account_observations = True

    def __init__(self, *args, clock, retention_clock, **kwargs):
        if kwargs.get('read_profile', {}).get('read_profile_version') != 'qmt.read-profile.v4':
            raise ValueError('explicit trading retirement requires a v4 profile')
        self._retained_business_clock = clock
        super().__init__(*args, clock=retention_clock, **kwargs)

    def _base_clock_arguments(self, clock):
        # 金融算法仍接原 callable 秒时钟；票据另用同机 uptime clock 对象。
        return {'clock': self._retained_business_clock}

    def _event_record_arguments(self, read_profile):
        if 'read_retention'not in read_profile:
            return {}  # HTTP能力不改变原事件profile身份，不声明一条虚假的profile迁移。
        previous = dict(read_profile)
        previous.pop('read_retention',None)
        return {'previous_read_profile': previous}

    def _read_held_by_financial_proof(self, db, rid):
        # 撤单/恢复仍会核原查询结果。消费确认只结束观察交付，不能移除
        # 当前金融关联的证明；新查询按原算法替换引用后，旧证明才可回收。
        return db.execute('SELECT 1 FROM trade_order_links WHERE query_request_id=? LIMIT 1', (rid,)).fetchone() is not None

    def _retention_extra_counts(self):
        return {'held_financial_proof': 0}

    def _historical_read_profile_matches(self, binding):
        if super()._historical_read_profile_matches(binding):
            return True
        previous = self.admission_profile
        if 'read_retention'not in previous:return False
        del previous['read_retention']
        return binding['capability_sha256'] == digest(canonical(previous))


class HttpRetainedTradingJournal(RetainedTradingJournal):
    """显式Host HTTP消费能力；旧原件保持，终态按实际不可变正文计费。"""
    def __init__(self,*args,http_retention,**kwargs):
        super().__init__(*args,http_retention=retention(http_retention),**kwargs)
    @staticmethod
    def _used(db):
        # 原终态不可覆写；只有读行计费收敛，金融表/原reserved_bytes/旧ID和正文不改。
        from .bound import MAX_METADATA_BYTES
        return db.execute('''SELECT COALESCE(SUM(CASE WHEN state='terminal' AND result IS NOT NULL
            THEN length(body)+length(result)+? ELSE reserved_bytes END),0) FROM read_operations''',
            (MAX_METADATA_BYTES,)).fetchone()[0]

    def _admit_new_bound(self, request, queue_timeout_ms):
        # UTC先采、uptime后采；事务/采样等待只收紧票据原D，Source仍接原SDK正文。
        import time
        from guanheng_qmt_shm_agent.read_retention import now_ms
        utc=time.time();value=self._ticket_context.value
        end=utc+(value['expires_ms']-now_ms(self.retention_clock))/1000
        return min(super()._admit_new_bound(request,queue_timeout_ms),end)
