"""R18 原通信事件持久记录；连接、锁、线程及截止均属于传入 Journal。

所有返回收据只证明 Host 持久接收/源确认，不计算交易业务状态。源 ACK
不删除原事件；相同身份重放逐字节核对。网络和 WT 消费由调用 owner 处理。
"""
from contextlib import contextmanager

from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.account_query import account_projection_version
from guanheng_qmt_shm_agent.read_capabilities import validate_read_profile
from guanheng_qmt_shm_agent.trade_capabilities import validate_trade_profile_binding
from guanheng_qmt_shm_agent.trading_kernel import snapshot_order, snapshot_deal, snapshot_error
from .bound import digest, MAX_BINDING_BYTES, MAX_METADATA_BYTES
from .journal import JournalConflict, JournalFull

TABLES = frozenset(('trade_event_identity', 'trade_event_streams', 'trade_events'))
CONTINUITY_VERSION = 'qmt.trade-auth-continuity.v1'
CONTINUITY_TABLES = frozenset(('trade_event_auth_connections',))
_AUTH_COLUMNS = ('session_id', 'binding_id', 'auth_index', 'origin_binding', 'host_binding',
    'previous_index', 'durable_through', 'ack_intended_through', 'source_ack_through',
    'observed_published_through', 'reserved_bytes')
_MAX_SEQUENCE = 2 ** 53 - 1
_STREAM_BYTES = MAX_BINDING_BYTES + 1024
_STREAM_COLUMNS = ('session_id', 'binding_id', 'host_binding', 'durable_through',
    'ack_intended_through', 'source_ack_through', 'observed_published_through', 'gap', 'reserved_bytes')
_EVENT_COLUMNS = ('session_id', 'binding_id', 'sequence', 'body', 'sha256', 'reserved_bytes')


def _reject():
    raise JournalConflict('trade event identity, content or frontier differs')


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names) or any(type(k) is not str for k in value):
        _reject()


def _integer(value, low=0, high=_MAX_SEQUENCE):
    if type(value) is not int or not low <= value <= high:
        _reject()
    return value


def _identity(value):
    if (type(value) is not str or not 1 <= len(value) <= 128 or not value.strip()
            or any(not 32 <= ord(c) < 127 for c in value)):
        _reject()
    return value


def _object(raw, maximum):
    if type(raw) is not bytes or not 1 <= len(raw) <= maximum:
        _reject()
    value = decode(raw)
    if canonical(value) != raw:
        _reject()
    return value


def _gap(value):
    if value is not None:
        _fields(value, ('code', 'sequence'))
        _identity(value['code'])
        if value['sequence'] is not None:
            _integer(value['sequence'], 1)
    return value


def validate_trade_event_storage(profile, trade_binding, event_storage, *, max_result_bytes):
    """纯校验事件存储配置，返回独立值副本；供工厂与实际 Journal 共用。"""
    checked = validate_read_profile(profile, max_result_bytes=max_result_bytes)
    if checked.get('read_profile_version') != 'qmt.read-profile.v4':
        _reject()
    private = trade_binding
    descriptor = validate_trade_profile_binding(checked['trade_profile'], private)
    _fields(event_storage, ('max_streams', 'max_events', 'max_bytes', 'max_page_bytes'))
    storage = decode(canonical(event_storage))
    _integer(storage['max_streams'], 1, 4096)
    _integer(storage['max_events'], 1, 1000000)
    limits = descriptor['limits']
    _integer(storage['max_page_bytes'], limits['max_event_bytes'] + 1024,
             limits['max_event_page_bytes'])
    if 4 * ((storage['max_page_bytes'] + 2) // 3) + MAX_METADATA_BYTES > 4194304:
        _reject()
    identity = canonical({'schema_version': 'qmt.trade-event-storage.v1',
        'profile_sha256': digest(canonical(checked)),
        'binding_sha256': descriptor['binding_sha256'], 'event_storage': storage})
    unit = limits['max_event_bytes'] + 512
    _integer(storage['max_bytes'], len(identity) + _STREAM_BYTES + unit,
             len(identity) + storage['max_streams'] * _STREAM_BYTES + storage['max_events'] * unit)
    return storage, dict(limits), identity, digest(canonical(checked))


class TradeEventRecords:
    """无独立 owner 的有界通信记录接口；构造纯校验，initialize 借用初始化事务。

    source 必须来自认证运行 owner；deadline 是入域前固定的绝对 monotonic 秒。
    方法沿 Journal 原事务拒绝晚回，异常传播；不调用新命令准入或清除 unknown。
    """
    def __init__(self, owner, event_storage, profile, *, max_result_bytes, connection_continuity=None,
                 previous_read_profile=None):
        storage, limits, identity, profile_sha = validate_trade_event_storage(
            profile, owner.trade_binding, event_storage, max_result_bytes=max_result_bytes)
        if connection_continuity not in (None, CONTINUITY_VERSION):
            _reject()
        self._continuity = connection_continuity is not None
        private = owner.trade_binding
        self._owner, self._identity_bytes = owner, identity
        self._retained_usage = None  # 同一写入者锁内维护已提交的流数、事件数和逻辑字节。
        self._storage, self._limits = storage, dict(limits)
        self._profile_sha = profile_sha
        self._projection_version = account_projection_version(
            profile['operation_profiles']['account.trade_detail']['policy_version'])
        self._previous_identity = self._previous_profile_sha = None
        if previous_read_profile is not None:
            # 仅显式读取回收 owner 给出此关系。旧金融身份保持原 bytes；
            # 唯一可接受的变化是完整 profile 附加 read_retention，其他字段严格相同。
            if 'read_retention' not in profile:
                _reject()
            previous = dict(profile)
            del previous['read_retention']
            if canonical(previous_read_profile) != canonical(previous):
                _reject()
            unused, unused_limits, self._previous_identity, self._previous_profile_sha = validate_trade_event_storage(
                previous, owner.trade_binding, event_storage, max_result_bytes=max_result_bytes)
        self._binding_id, self._account_id = private['binding_id'], private['account_id']

    @property
    def connection_continuity(self):
        """显式续接模式；运行 owner 用于核对工厂与实际存储契约。"""
        return CONTINUITY_VERSION if self._continuity else None

    @property
    def storage(self):
        """返回已准入存储配置副本，供同 owner 运行器核对同次预算。"""
        return decode(canonical(self._storage))

    def _source(self, source, *, retained=False):
        _fields(source, ('host_binding', 'session_id'))
        session = _identity(source['session_id'])
        if type(source['host_binding']) is not dict:
            _reject()
        raw = self._owner._source(source['host_binding'])
        value = _object(raw, MAX_BINDING_BYTES)
        allowed = {self._profile_sha}
        if retained:allowed.update(self._owner._historical_profile_hashes())
        if retained and self._previous_profile_sha is not None:
            allowed.add(self._previous_profile_sha)
        if value['schema_version'] != '2.0' or value['capability_sha256'] not in allowed:
            _reject()
        return session, raw

    def _event(self, value, session):
        _fields(value, ('schema_version', 'session_id', 'binding_id', 'sequence', 'kind', 'payload'))
        if (value['schema_version'] != 'qmt.trade-event.v1' or value['session_id'] != session
                or value['binding_id'] != self._binding_id or type(value['kind']) is not str
                or type(value['payload']) is not dict):
            _reject()
        _integer(value['sequence'], 1)
        payload = value['payload']
        if value['kind'] == 'order':
            projected = snapshot_order(payload)
            account = payload.get('m_strAccountID')
        elif value['kind'] == 'deal':
            projected = snapshot_deal(payload, projection_version=self._projection_version)
            account = payload.get('m_strAccountID')
        elif value['kind'] == 'error':
            _fields(payload, ('order_args', 'err_msg'))
            if type(payload['order_args']) is not dict:
                _reject()
            projected = snapshot_error(payload['order_args'], payload['err_msg'])
            account = payload['order_args'].get('accountID')
        else:
            _reject()
        if (type(account) is not str or account != self._account_id
                or canonical(projected) != canonical(payload)):
            _reject()
        raw = canonical(value)
        if len(raw) > self._limits['max_event_bytes']:
            _reject()
        return raw

    def _stream(self, row):
        if row is None:
            return None
        session, binding_id, raw, durable, intended, ack, published, gap_raw, reserved = row
        _identity(session)
        if (binding_id != self._binding_id or type(raw) is not bytes
                or type(reserved) is not int or reserved != _STREAM_BYTES):
            _reject()
        self._source({'session_id': session, 'host_binding': _object(raw, MAX_BINDING_BYTES)}, retained=True)
        for value in (durable, intended, ack, published):
            _integer(value)
        if not 0 <= ack <= intended == durable <= published or durable > self._storage['max_events']:
            _reject()
        gap = _gap(_object(gap_raw, 1024))
        return {'schema_version': 'qmt.trade-event-receipt.v1', 'session_id': session,
            'binding_id': binding_id, 'host_binding_sha256': digest(raw),
            'durable_through': durable, 'ack_intended_through': intended,
            'source_ack_through': ack, 'observed_published_through': published, 'gap': gap}

    def _find(self, db, session, source_raw):
        row = db.execute('SELECT ' + ','.join(_STREAM_COLUMNS) +
            ' FROM trade_event_streams WHERE session_id=? AND binding_id=?',
            (session, self._binding_id)).fetchone()
        result = self._stream(row)
        if row is not None:
            self._authenticate_current(db, session, source_raw, row[2])
        return result

    def _auth_rows(self, db, session):
        cursor = db.execute('SELECT ' + ','.join(_AUTH_COLUMNS) +
            ' FROM trade_event_auth_connections WHERE session_id=? AND binding_id=? ORDER BY auth_index',
            (session, self._binding_id))
        while True:
            row = cursor.fetchone()
            if row is None:
                return
            yield row

    def _same_source(self, origin, actual):
        # 认证随机 nonce 只标识连接；账户/会话/profile/epoch 的稳定范围保持原值。
        before, after = decode(origin), decode(actual)
        for key in ('transport_generation', 'host_instance_id'):
            before.pop(key); after.pop(key)
        if before != after:
            _reject()

    def _auth_reservation(self, row):
        return len(canonical({'schema_version': CONTINUITY_VERSION,
            'session_id': row[0], 'binding_id': row[1], 'auth_index': row[2],
            'origin_binding': decode(row[3]), 'host_binding': decode(row[4]),
            'previous_index': row[5], 'durable_through': row[6],
            'ack_intended_through': row[7], 'source_ack_through': row[8],
            'observed_published_through': row[9]})) + 512

    def _append_auth(self, db, session, origin, actual, previous, state):
        row = (session, self._binding_id, previous + 1, origin, actual, previous,
            state['durable_through'], state['ack_intended_through'],
            state['source_ack_through'], state['observed_published_through'])
        reserved = self._auth_reservation(row)
        db.execute('INSERT INTO trade_event_auth_connections VALUES(?,?,?,?,?,?,?,?,?,?,?)', row + (reserved,))
        return reserved

    def _authenticate_current(self, db, session, actual, origin=None):
        if origin is None:
            stream = db.execute('SELECT host_binding FROM trade_event_streams WHERE session_id=? AND binding_id=?',
                                (session, self._binding_id)).fetchone()
            if stream is None:
                _reject()
            origin = stream[0]
        if self._continuity:
            row = db.execute('SELECT host_binding FROM trade_event_auth_connections '
                'WHERE session_id=? AND binding_id=? ORDER BY auth_index DESC LIMIT 1',
                (session, self._binding_id)).fetchone()
            if row is None or row[0] != actual:
                _reject()
        elif origin != actual:
            _reject()

    def _event_source(self, db, session, binding_id, sequence):
        """内部证明读取：按首次持久事件的连接区间还原来源，重放不授新证明。"""
        if binding_id != self._binding_id:
            _reject()
        if self._continuity:
            row = db.execute('SELECT host_binding FROM trade_event_auth_connections '
                'WHERE session_id=? AND binding_id=? AND durable_through<? '
                'ORDER BY auth_index DESC LIMIT 1', (session, binding_id, sequence)).fetchone()
        else:
            row = db.execute('SELECT host_binding FROM trade_event_streams WHERE session_id=? AND binding_id=?',
                             (session, binding_id)).fetchone()
        if row is None:
            _reject()
        source = {'session_id': session, 'host_binding': _object(row[0], MAX_BINDING_BYTES)}
        if self._source(source, retained=True)[1] != row[0]:
            _reject()
        return source

    def resume(self, source, *, deadline):
        """认证 owner 串行关闭旧连接后登记新关系；返回原收据，未知流返回 None。

        本接口只记录已认证来源的通信续接；旧 binding 重用拒绝，原事件/命令不改写。
        """
        if not self._continuity:
            _reject()
        session, actual = self._source(source)
        with self._event_transaction(deadline) as db:
            stream = db.execute('SELECT ' + ','.join(_STREAM_COLUMNS) +
                ' FROM trade_event_streams WHERE session_id=? AND binding_id=?',
                (session, self._binding_id)).fetchone()
            state = self._stream(stream)
            if state is None:
                return None
            self._same_source(stream[2], actual)
            latest = db.execute('SELECT auth_index,host_binding FROM trade_event_auth_connections '
                'WHERE session_id=? AND binding_id=? ORDER BY auth_index DESC LIMIT 1',
                (session, self._binding_id)).fetchone()
            if latest is None:
                _reject()
            if latest[1] != actual:
                if db.execute('SELECT 1 FROM trade_event_auth_connections '
                        'WHERE session_id=? AND binding_id=? AND host_binding=?',
                        (session, self._binding_id, actual)).fetchone():
                    _reject()
                added = self._append_auth(db, session, stream[2], actual, latest[0], state)
                self._reserve_usage(reserved_bytes=added)
        return state

    def authenticated(self, source, *, deadline):
        """只读已登记的当前精确认证关系；未知流或未登记连接返回 False。"""
        session, actual = self._source(source)
        with self._owner._trade_transaction(deadline) as db:
            stream = db.execute('SELECT host_binding FROM trade_event_streams WHERE session_id=? AND binding_id=?',
                                (session, self._binding_id)).fetchone()
            if stream is None:
                return False
            if not self._continuity:
                return stream[0] == actual
            row = db.execute('SELECT host_binding FROM trade_event_auth_connections '
                'WHERE session_id=? AND binding_id=? ORDER BY auth_index DESC LIMIT 1',
                (session, self._binding_id)).fetchone()
            if row is None:
                _reject()
            return row[0] == actual

    def _initialize_auth(self, db, existed):
        if not self._continuity:
            return
        db.execute('''CREATE TABLE IF NOT EXISTS trade_event_auth_connections (
            session_id TEXT NOT NULL, binding_id TEXT NOT NULL, auth_index INTEGER NOT NULL,
            origin_binding BLOB NOT NULL, host_binding BLOB NOT NULL, previous_index INTEGER NOT NULL,
            durable_through INTEGER NOT NULL, ack_intended_through INTEGER NOT NULL,
            source_ack_through INTEGER NOT NULL, observed_published_through INTEGER NOT NULL,
            reserved_bytes INTEGER NOT NULL, PRIMARY KEY(session_id,binding_id,auth_index))''')
        columns = db.execute('PRAGMA table_info(trade_event_auth_connections)').fetchall()
        if ({row[1] for row in columns} != set(_AUTH_COLUMNS)
                or [row[1] for row in columns if row[5]] != ['session_id', 'binding_id', 'auth_index']):
            _reject()
        self._usage(db)
        cursor = db.execute('SELECT ' + ','.join(_STREAM_COLUMNS) + ' FROM trade_event_streams')
        total = 0
        while True:
            stream = cursor.fetchone()
            if stream is None:
                break
            state = self._stream(stream)
            if not existed:
                # 旧精确绑定库的全部原事件已有同一 genesis 证明，原字节保持。
                self._append_auth(db, stream[0], stream[2], stream[2], 0,
                    dict(durable_through=0, ack_intended_through=0,
                         source_ack_through=0, observed_published_through=0))
            previous, seen, frontiers = 0, set(), (0, 0, 0, 0)
            for row in self._auth_rows(db, stream[0]):
                total += 1
                _integer(row[2], 1)
                _integer(row[5])
                if (type(row[10]) is not int or row[2] != previous + 1 or row[5] != previous or row[3] != stream[2]
                        or row[4] in seen or row[10] != self._auth_reservation(row)):
                    _reject()
                self._source({'session_id': stream[0], 'host_binding': _object(row[4], MAX_BINDING_BYTES)}, retained=True)
                self._same_source(stream[2], row[4])
                for value in row[6:10]:
                    _integer(value)
                if (not 0 <= row[8] <= row[7] == row[6] <= row[9]
                        or any(a > b for a, b in zip(frontiers, row[6:10]))
                        or any(row[i + 6] > state[key] for i, key in enumerate((
                            'durable_through', 'ack_intended_through', 'source_ack_through',
                            'observed_published_through')))):
                    _reject()
                if previous == 0 and (row[4] != stream[2] or row[6:10] != (0, 0, 0, 0)):
                    _reject()
                previous, frontiers = row[2], row[6:10]
                seen.add(row[4])
            if previous == 0:
                _reject()
        if total != db.execute('SELECT COUNT(*) FROM trade_event_auth_connections').fetchone()[0]:
            _reject()

    def _retained_event(self, row, session):
        sid, bid, sequence, body, sha, reserved = row
        _integer(sequence, 1)
        if sid != session or bid != self._binding_id or type(body) is not bytes:
            _reject()
        value = _object(body, self._limits['max_event_bytes'])
        if (self._event(value, session) != body or value['sequence'] != sequence
                or digest(body) != sha or type(reserved) is not int or reserved != len(body) + 512):
            _reject()
        return value

    def _usage(self, db):
        streams, stream_bytes = db.execute(
            'SELECT COUNT(*),COALESCE(SUM(reserved_bytes),0) FROM trade_event_streams').fetchone()
        events, event_bytes = db.execute(
            'SELECT COUNT(*),COALESCE(SUM(reserved_bytes),0) FROM trade_events').fetchone()
        auth_bytes = (db.execute('SELECT COALESCE(SUM(reserved_bytes),0) '
            'FROM trade_event_auth_connections').fetchone()[0] if self._continuity else 0)
        return self._checked_usage(streams, events, stream_bytes + event_bytes + auth_bytes)

    def _checked_usage(self, streams, events, reserved_bytes):
        if (streams > self._storage['max_streams'] or events > self._storage['max_events']
                or len(self._identity_bytes) + reserved_bytes > self._storage['max_bytes']):
            raise JournalFull('trade event retention capacity exhausted')
        return streams, events, reserved_bytes

    @contextmanager
    def _event_transaction(self, deadline):
        # 外层复用同一把锁，提交失败或结果未知时先使缓存失效，再允许下一调用。
        with self._owner._trade_lock(deadline):
            before = self._retained_usage
            try:
                with self._owner._trade_transaction(deadline) as db:
                    if self._retained_usage is None:
                        self._retained_usage = self._usage(db)
                    before = self._retained_usage
                    yield db
            except BaseException:
                if self._retained_usage != before:
                    self._retained_usage = None
                raise

    def _reserve_usage(self, *, streams=0, events=0, reserved_bytes=0):
        previous_streams, previous_events, previous_bytes = self._retained_usage
        self._retained_usage = self._checked_usage(
            previous_streams + streams, previous_events + events, previous_bytes + reserved_bytes)

    def initialize(self, db):
        """在 Journal 初始化原事务、命令恢复前调用；逐行验证，不启动连接/线程。"""
        continuity_existed = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='trade_event_auth_connections'").fetchone() is not None
        if continuity_existed and not self._continuity:
            _reject()
        present = set()
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            if row[0] in TABLES:
                present.add(row[0])
        if present and present != TABLES:
            _reject()
        db.execute('CREATE TABLE IF NOT EXISTS trade_event_identity (id INTEGER PRIMARY KEY CHECK(id=1), value BLOB NOT NULL)')
        db.execute('''CREATE TABLE IF NOT EXISTS trade_event_streams (
            session_id TEXT NOT NULL, binding_id TEXT NOT NULL, host_binding BLOB NOT NULL,
            durable_through INTEGER NOT NULL, ack_intended_through INTEGER NOT NULL,
            source_ack_through INTEGER NOT NULL, observed_published_through INTEGER NOT NULL,
            gap BLOB NOT NULL, reserved_bytes INTEGER NOT NULL, PRIMARY KEY(session_id,binding_id))''')
        db.execute('''CREATE TABLE IF NOT EXISTS trade_events (
            session_id TEXT NOT NULL, binding_id TEXT NOT NULL, sequence INTEGER NOT NULL,
            body BLOB NOT NULL, sha256 TEXT NOT NULL, reserved_bytes INTEGER NOT NULL,
            PRIMARY KEY(session_id,binding_id,sequence))''')
        for table, columns, keys in (
                ('trade_event_identity', ('id', 'value'), ('id',)),
                ('trade_event_streams', _STREAM_COLUMNS, ('session_id', 'binding_id')),
                ('trade_events', _EVENT_COLUMNS, ('session_id', 'binding_id', 'sequence'))):
            found, primary = set(), {}
            cursor = db.execute('PRAGMA table_info(' + table + ')')
            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                found.add(row[1])
                if row[5]:
                    primary[row[5]] = row[1]
                if len(found) > len(columns):
                    _reject()
            if found != set(columns) or tuple(primary.get(i + 1) for i in range(len(primary))) != keys:
                _reject()
        cursor = db.execute('SELECT id,value FROM trade_event_identity')
        identity = cursor.fetchone()
        if identity is None:
            if present:
                _reject()
            db.execute('INSERT INTO trade_event_identity VALUES(1,?)', (self._identity_bytes,))
        else:
            if self._previous_identity is not None and identity == (1, self._previous_identity):
                self._identity_bytes = self._previous_identity
            if identity != (1,self._identity_bytes) and identity is not None and identity[0]==1 and self._owner._historical_event_identity_matches(bytes(identity[1])):
                self._identity_bytes=bytes(identity[1])
            if identity != (1, self._identity_bytes) or cursor.fetchone() is not None:
                _reject()
        self._initialize_auth(db, continuity_existed)
        usage = self._usage(db)
        stream_count, event_count, _ = usage
        cursor = db.execute('SELECT ' + ','.join(_STREAM_COLUMNS) + ' FROM trade_event_streams')
        checked_streams = checked_events = 0
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            checked_streams += 1
            if checked_streams > stream_count:
                _reject()
            state = self._stream(row)
            events = db.execute('SELECT ' + ','.join(_EVENT_COLUMNS) +
                ' FROM trade_events WHERE session_id=? AND binding_id=? ORDER BY sequence',
                (row[0], row[1]))
            sequence = 0
            while True:
                event = events.fetchone()
                if event is None:
                    break
                sequence += 1
                checked_events += 1
                if checked_events > event_count or sequence > state['durable_through']:
                    _reject()
                self._retained_event(event, row[0])
                if event[2] != sequence:
                    _reject()
            if sequence != state['durable_through']:
                _reject()
        if checked_events != event_count or checked_streams != stream_count:
            _reject()
        self._retained_usage = usage  # 初始化事务成功后，Journal 才对外提供事件接口。

    def _page_arguments(self, after_seq, limit, max_bytes):
        _integer(after_seq)
        _integer(limit, 1, self._limits['max_events'])
        _integer(max_bytes, 1, self._storage['max_page_bytes'])

    def ingest(self, source, page_bytes, *, after_seq, limit, max_bytes, deadline):
        """原页、新连续后缀及待 ACK 意图原子提交；返回成功后方可发送源 ACK。"""
        session, source_raw = self._source(source)
        self._page_arguments(after_seq, limit, max_bytes)
        page = _object(page_bytes, max_bytes)
        _fields(page, ('schema_version', 'session_id', 'binding_id', 'acknowledged_through',
                      'published_through', 'gap', 'events'))
        if (page['schema_version'] != 'qmt.trade-event-page.v1' or page['session_id'] != session
                or page['binding_id'] != self._binding_id or type(page['events']) is not list
                or len(page['events']) > limit):
            _reject()
        acknowledged = _integer(page['acknowledged_through'])
        published = _integer(page['published_through'])
        if not acknowledged <= after_seq <= published or (not page['events'] and published > after_seq):
            _reject()
        gap = _gap(page['gap'])
        raw_events = []
        for number, value in enumerate(page['events'], after_seq + 1):
            raw = self._event(value, session)
            if value['sequence'] != number or number > published:
                _reject()
            raw_events.append((number, raw))
        with self._event_transaction(deadline) as db:
            state = self._find(db, session, source_raw)
            new_stream = state is None
            added_bytes = 0
            if new_stream:
                if after_seq != 0 or acknowledged != 0:
                    _reject()
                db.execute('INSERT INTO trade_event_streams VALUES(?,?,?,?,?,?,?,?,?)',
                    (session, self._binding_id, source_raw, 0, 0, 0, 0, canonical(None), _STREAM_BYTES))
                added_bytes = _STREAM_BYTES
                if self._continuity:
                    added_bytes += self._append_auth(db, session, source_raw, source_raw, 0,
                        dict(durable_through=0, ack_intended_through=0,
                             source_ack_through=0, observed_published_through=0))
                state = self._find(db, session, source_raw)
            durable = state['durable_through']
            if acknowledged > durable or after_seq > durable:
                _reject()
            if state['gap'] is not None and gap is not None and canonical(state['gap']) != canonical(gap):
                _reject()
            for sequence, raw in raw_events:
                if sequence <= durable:
                    row = db.execute('SELECT ' + ','.join(_EVENT_COLUMNS) +
                        ' FROM trade_events WHERE session_id=? AND binding_id=? AND sequence=?',
                        (session, self._binding_id, sequence)).fetchone()
                    if row is None:
                        _reject()
                    self._retained_event(row, session)
                    if row[3] != raw or row[4] != digest(raw):
                        _reject()
                else:
                    if sequence != durable + 1:
                        _reject()
                    reserved = len(raw) + 512
                    db.execute('INSERT INTO trade_events VALUES(?,?,?,?,?,?)',
                        (session, self._binding_id, sequence, raw, digest(raw), reserved))
                    added_bytes += reserved
                    self._owner._order_links.ingest_event(db, decode(raw), source)
                    durable = sequence
            saved_gap = state['gap'] if state['gap'] is not None else gap
            new_events = durable != state['durable_through']
            if new_stream or new_events:
                self._reserve_usage(streams=int(new_stream), events=durable - state['durable_through'],
                                    reserved_bytes=added_bytes)
            observed = max(published, state['observed_published_through'])
            if new_events or observed != state['observed_published_through'] or saved_gap != state['gap']:
                db.execute('''UPDATE trade_event_streams SET durable_through=?,ack_intended_through=?,
                    observed_published_through=?,gap=? WHERE session_id=? AND binding_id=?''',
                    (durable, durable, observed, canonical(saved_gap), session, self._binding_id))
                state = self._find(db, session, source_raw)
            receipt = state
        return receipt

    def state(self, source, *, deadline):
        """返回持久前沿副本；显式版本链允许历史原source，只读不授新事件。"""
        session, source_raw = self._source(source,retained=bool(self._owner._historical_profile_hashes()))
        with self._owner._trade_transaction(deadline) as db:
            receipt = self._find(db, session, source_raw)
        return receipt

    def acknowledge(self, source, ack_bytes, *, through_seq, deadline):
        """只记录原源业务 ACK 回复；RPC ACK/发送成功不得调用此接口冒充证明。"""
        session, source_raw = self._source(source)
        _integer(through_seq)
        ack = _object(ack_bytes, 1024)
        _fields(ack, ('schema_version', 'session_id', 'through_seq'))
        _integer(ack['through_seq'])
        if (ack['schema_version'] != 'qmt.trade-event-ack.v1' or ack['session_id'] != session
                or ack['through_seq'] != through_seq):
            _reject()
        with self._owner._trade_transaction(deadline) as db:
            state = self._find(db, session, source_raw)
            if state is None or not state['source_ack_through'] <= through_seq <= state['ack_intended_through']:
                _reject()
            if through_seq != state['source_ack_through']:
                db.execute('UPDATE trade_event_streams SET source_ack_through=? WHERE session_id=? AND binding_id=?',
                    (through_seq, session, self._binding_id))
                state = self._find(db, session, source_raw)
            receipt = state
        return receipt

    def read(self, source, *, after_seq, limit, max_bytes, deadline):
        """有界复制原持久事件；显式版本链只授历史读取，不授新来源准入。"""
        session, source_raw = self._source(source,retained=bool(self._owner._historical_profile_hashes()))
        self._page_arguments(after_seq, limit, max_bytes)
        with self._owner._trade_transaction(deadline) as db:
            receipt = self._find(db, session, source_raw)
            if receipt is None:
                return None
            if after_seq > receipt['durable_through']:
                _reject()
            result = {'schema_version': 'qmt.persisted-trade-events.v1', 'receipt': receipt, 'events': []}
            if self._continuity:
                # 同一 Journal 事务内的 _find 已核准当前连接，原收据和事件保持。
                result['schema_version'] = 'qmt.persisted-trade-events.v2'
                result['continuity'] = dict(schema_version='qmt.trade-source-continuity.v1',
                    session_id=session, binding_id=self._binding_id,
                    current_host_binding_sha256=digest(source_raw),
                    origin_host_binding_sha256=receipt['host_binding_sha256'], authenticated=True)
            size = len(canonical(result))
            if size > max_bytes:
                raise JournalFull('persisted event page metadata exceeds budget')
            cursor = db.execute('SELECT ' + ','.join(_EVENT_COLUMNS) +
                ' FROM trade_events WHERE session_id=? AND binding_id=? AND sequence>? ORDER BY sequence LIMIT ?',
                (session, self._binding_id, after_seq, limit))
            expected = after_seq + 1
            for unused in range(min(limit, receipt['durable_through'] - after_seq)):
                row = cursor.fetchone()
                if row is None or row[2] != expected:
                    _reject()
                value = self._retained_event(row, session)
                next_size = size + len(row[3]) + (1 if result['events'] else 0)
                if next_size > max_bytes:
                    if not result['events']:
                        raise JournalFull('persisted event does not fit page budget')
                    break
                result['events'].append(value)
                size = next_size
                expected += 1
            raw = canonical(result)
        return raw
