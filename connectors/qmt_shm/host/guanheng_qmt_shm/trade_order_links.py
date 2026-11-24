"""R21 有限原委托通信关联；借用 Journal 原事务，不拥有线程或数据库。

只为已持久派发命令以完整 token/account 认领新事件。关联故障锁存安全码，原事件与既有
broker 证明保留；lookup 不授业务终态、WT 应用或跨会话撤单资格。
"""
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.trading_contract import _text, terminal_insert_observed
from guanheng_qmt_shm_agent.read_capabilities import validate_read_result_projection, validate_read_request
from .bound import digest, MAX_METADATA_BYTES
from .journal import JournalConflict

TABLES = frozenset(('trade_order_links',))
ASSOCIATION_ERRORS = frozenset(('broker_identity_conflict',
    'broker_identity_unrepresentable', 'symbol_mismatch'))
_COLUMNS = ('command_id', 'broker_order_id', 'source_session_id', 'source_binding_id',
            'source_sequence', 'source_event_sha256', 'association_error',
            'query_request_id', 'query_row_index', 'query_result_sha256')


def _order_query(request, result):
    return (request.get('operation_id') == 'account.trade_detail'
        and request.get('policy_version') in ('2.0', '3.0')
        and request.get('arguments', {}).get('datatype') == 'order'
        and result.get('ok') is True)


def validate_lookup_identity(identity):
    """沿共用原命令字符串校验；只接受原 WT 二元身份或完整 SDK token。"""
    if type(identity) is not dict or any(type(k) is not str for k in identity):
        raise JournalConflict('invalid original order lookup identity')
    if set(identity) == {'entrust_id', 'user_tag'}:
        for key in ('entrust_id', 'user_tag'):
            _text(identity[key], 63, 'invalid_command')
    elif set(identity) == {'sdk_user_order_id'}:
        token = _text(identity['sdk_user_order_id'], 64, 'invalid_command', True)
        if any(ord(c) < 33 for c in token):
            raise JournalConflict('invalid original order token')
    else:
        raise JournalConflict('invalid original order lookup identity')
    return dict(identity)


def _broker(value):
    try:
        return _text(value, 63, 'invalid_command', True)
    except ValueError:
        return None


class OrderSourceUnavailable(JournalConflict):
    """当前原来源proof缺失；只读历史事实保留，不能派发新取消。"""


class TradeOrderLinks:
    """内部 db 参数均由原 Journal owner 授予，不单独 commit 或打开连接。"""
    def __init__(self, owner):
        self._owner = owner

    def _rows(self, db):
        cursor = db.execute('SELECT command_id FROM trade_order_links ORDER BY command_id')
        for unused in range(self._owner.max_trade_commands + 1):
            row = cursor.fetchone()
            if row is None:
                return
            if unused == self._owner.max_trade_commands:
                raise JournalConflict('order link capacity differs')
            yield row[0]

    def _insert(self, db, cid):
        record = self._owner._record(self._owner._select(db, cid))
        if record is None or decode(record['body'])['operation'] != 'order.insert':
            raise JournalConflict('order link original insert differs')
        return record, decode(record['body'])

    def reserve_insert(self, db, command):
        """原 insert 同事务建唯一空关联；WT 号换 UUID 拒绝，原命令回滚。"""
        for cid in self._rows(db):
            unused, other = self._insert(db, cid)
            if other['entrust_id'] == command['entrust_id']:
                raise JournalConflict('WT entrust identity already belongs to original insert')
        db.execute('INSERT INTO trade_order_links(command_id) VALUES(?)', (command['command_id'],))

    def _association(self, command, event):
        payload = event['payload']
        symbol, exchange = command['symbol'].split('.')
        if (('m_strInstrumentID' in payload and payload['m_strInstrumentID'] != symbol)
                or ('m_strExchangeID' in payload and payload['m_strExchangeID'] != exchange)):
            return None, 'symbol_mismatch'
        value = payload.get('m_strOrderSysID')
        if value is None or value == '':
            return None, None
        broker = _broker(value)
        return (broker, None) if broker is not None else (None, 'broker_identity_unrepresentable')

    def _query_rows(self, request, result, profile=None):
        # 原Host投影validator只核版本。认领身份还须核真实账户范围与完整原列表，
        # 金额/仓位/状态等金融解释继续由唯一mapper负责。
        validate_read_result_projection(request, result)
        data = result.get('data')
        limits = (self._owner.admission_profile if profile is None else profile)['operation_profiles']['account.trade_detail']['limits']
        if (type(data) is not dict or data.get('schema_version') not in ('qmt.account-batch.v2', 'qmt.account-batch.v3')
                or data.get('account_binding') != dict(limits['account_binding'], origin='trusted_bootstrap_argument')
                or data.get('query') != {'account_type': 'stock', 'datatype': 'order',
                                         'scope': 'account', 'strategy_name': None}
                or type(data.get('rows')) is not list or len(data['rows']) > limits['max_rows']
                or any(type(row) is not dict for row in data['rows'])):
            raise JournalConflict('order query account scope or rows differ')
        complete = data.get('completeness')
        if (type(complete) is not dict or set(complete) != {'complete','truncated','row_count','coverage'}
                or complete['complete'] is not True or complete['truncated'] is not False
                or type(complete['row_count']) is not int or complete['row_count'] != len(data['rows'])
                or complete['coverage'] != 'sdk_returned_list'):
            raise JournalConflict('order query original list is incomplete')
        return data

    def ingest_event(self, db, event, source):
        """在原事件 INSERT 后同事务调用；未知 token 不猜关联，关联故障不丢回报。"""
        if event['kind'] not in ('order', 'deal'):
            return
        if source['session_id'] != event['session_id']:
            raise JournalConflict('event association source session differs')
        actual = self._owner._source(source['host_binding'])
        self._owner.events._authenticate_current(db, event['session_id'], actual)
        payload = event['payload']
        token = payload.get('m_strRemark')
        if type(token) is not str or not token:
            return
        row = db.execute('SELECT command_id FROM trade_commands WHERE sdk_user_order_id=?', (token,)).fetchone()
        if row is None:
            return
        record, command = self._insert(db, row[0])
        # 只有已持久派发的原命令可认领本次新事件；旧事件不因后续派发补认。
        # 观察源可跨 Host 恢复，不能把原 dispatch B 强制替换或要求相等。
        if record['dispatch_binding'] is None:
            return
        if payload.get('m_strAccountID') != command['account_id']:
            return
        current = self._link(db, row[0])
        if current['association_error'] is not None:
            return
        broker, error = self._association(command, event)
        if error is None and broker is not None and current['broker_order_id'] not in (None, broker):
            error = 'broker_identity_conflict'
        if error is not None:
            db.execute('UPDATE trade_order_links SET association_error=? WHERE command_id=?', (error, row[0]))
        elif broker is not None:
            # 相同 broker 的后续真实回报可提供当前会话证明；不能只把 B 换成当前值。
            db.execute('''UPDATE trade_order_links SET broker_order_id=?,source_session_id=?,
                source_binding_id=?,source_sequence=?,source_event_sha256=? WHERE command_id=?''',
                (broker, event['session_id'], event['binding_id'], event['sequence'],
                 digest(canonical(event)), row[0]))

    def _persistent(self, read):
        """持久关联元数据/原proof共用硬故障边界；请求身份比较留在边界外。"""
        try:
            return read()
        except (JournalConflict, ValueError, TypeError, KeyError, OverflowError, RecursionError):
            self._owner._fail_trade('order_proof_invalid')
            raise JournalConflict('retained order proof is invalid') from None

    def _link(self, db, cid):
        return self._persistent(lambda: self._link_value(db, cid))

    def _link_value(self, db, cid):
        row = db.execute('SELECT ' + ','.join(_COLUMNS) + ' FROM trade_order_links WHERE command_id=?', (cid,)).fetchone()
        if row is None:
            raise JournalConflict('original insert lacks order link metadata')
        value = dict(zip(_COLUMNS, row))
        if len(canonical(value)) > MAX_METADATA_BYTES or value['association_error'] not in ASSOCIATION_ERRORS | {None}:
            raise JournalConflict('order link metadata differs')
        proof = [value[k] for k in ('source_session_id', 'source_binding_id',
                                    'source_sequence', 'source_event_sha256')]
        if any(x is None for x in proof) and not all(x is None for x in proof):
            raise JournalConflict('order link proof is incomplete')
        query = [value[k] for k in ('query_request_id', 'query_row_index', 'query_result_sha256')]
        if any(x is None for x in query) and not all(x is None for x in query):
            raise JournalConflict('order query proof is incomplete')
        if value['broker_order_id'] is not None and proof[0] is None and query[0] is None:
            raise JournalConflict('broker association lacks its observation')
        return value

    def _proof(self, db, link, command):
        return self._persistent(lambda: self._event_proof_value(db, link, command))

    def _event_proof_value(self, db, link, command):
        if link['broker_order_id'] is not None or link['association_error'] is not None:
            record, unused = self._insert(db, command['command_id'])
            if record['dispatch_binding'] is None:
                raise JournalConflict('order link lacks original dispatch proof')
        if link['source_sequence'] is None:
            return None
        if (_broker(link['broker_order_id']) != link['broker_order_id']
                or link['source_binding_id'] != command['binding_id']
                or type(link['source_sequence']) is not int or not 1 <= link['source_sequence'] <= 2**53-1):
            raise JournalConflict('order link proof identity differs')
        row = db.execute('''SELECT e.body,e.sha256,s.host_binding,s.durable_through
            FROM trade_events e JOIN trade_event_streams s
            ON e.session_id=s.session_id AND e.binding_id=s.binding_id
            WHERE e.session_id=? AND e.binding_id=? AND e.sequence=?''',
            (link['source_session_id'], link['source_binding_id'], link['source_sequence'])).fetchone()
        if (row is None or type(row[0]) is not bytes or digest(row[0]) != row[1]
                or row[1] != link['source_event_sha256'] or link['source_sequence'] > row[3]):
            raise JournalConflict('order link original event proof differs')
        event = decode(row[0])
        if (canonical(event) != row[0] or event['kind'] not in ('order', 'deal')
                or event['session_id'] != link['source_session_id']
                or event['binding_id'] != link['source_binding_id']
                or event['sequence'] != link['source_sequence']
                or event['payload'].get('m_strRemark') != command['sdk_user_order_id']
                or event['payload'].get('m_strAccountID') != command['account_id']
                or self._association(command, event) != (link['broker_order_id'], None)):
            raise JournalConflict('order link event does not prove original insert')
        source = self._owner.events._event_source(db, link['source_session_id'],
            link['source_binding_id'], link['source_sequence'])
        binding = source['host_binding']
        if (self._owner._source(binding) != canonical(binding)
                or not self._owner._historical_read_profile_matches(binding)):
            raise JournalConflict('order link original binding differs')
        return source

    def _query_proof(self, db, link, command):
        return self._persistent(lambda: self._query_proof_value(db, link, command))

    def _query_proof_value(self, db, link, command):
        """只引用已保存原行；重新核完整原bytes/来源，不从当前runtime补来源。"""
        rid = link['query_request_id']
        if rid is None:
            return None, None
        record, unused = self._insert(db, command['command_id'])
        if record['dispatch_binding'] is None:
            raise JournalConflict('query association lacks original dispatch')
        row = db.execute('''SELECT body,result,admitted_binding,dispatch_binding,result_binding,state
            FROM read_operations WHERE request_id=?''', (rid,)).fetchone()
        if (row is None or row[5] != 'terminal' or any(type(v) is not bytes for v in row[:5])
                or not row[2] == row[3] == row[4]
                or len(row[0]) > self._owner.max_request_bytes
                or len(row[1]) > self._owner.max_result_bytes):
            raise JournalConflict('order query original record is unavailable')
        request, result = decode(row[0]), decode(row[1])
        unsigned = dict(result); sha = unsigned.pop('result_sha256', None)
        if (canonical(request) != row[0] or canonical(result) != row[1]
                or result.get('request_id') != rid or request.get('request_id') != rid
                or result.get('operation_id') != request.get('operation_id')
                or digest(canonical(unsigned)) != sha or sha != link['query_result_sha256']
                or not _order_query(request, result)):
            raise JournalConflict('order query original identity differs')
        binding = decode(row[4])
        profile = self._owner._historical_read_profile(binding)
        if self._owner._source(binding) != row[4] or profile is None:
            raise JournalConflict('order query source differs')
        validate_read_request(request, profile,max_result_bytes=self._owner.max_result_bytes)
        data = self._query_rows(request, result, profile)
        index = link['query_row_index']
        if (data['schema_version'] not in ('qmt.account-batch.v2', 'qmt.account-batch.v3')
                or data['account_binding']['account_id'] != command['account_id']
                or type(index) is not int or not 0 <= index < len(data['rows'])):
            raise JournalConflict('order query row identity differs')
        payload = data['rows'][index]
        if (payload.get('m_strRemark') != command['sdk_user_order_id']
                or payload.get('m_strAccountID') != command['account_id']
                or 'm_strInstrumentID' not in payload or 'm_strExchangeID' not in payload):
            raise JournalConflict('order query does not identify original insert')
        broker, error = self._association(command, {'payload': payload})
        if error is None and broker != link['broker_order_id']:
            error = 'broker_identity_conflict'
        if broker is None and error is None:
            raise JournalConflict('order query lacks broker identity')
        if error is not None and error != link['association_error']:
            raise JournalConflict('order query association evidence differs')
        return {'request_id': rid, 'result_sha256': sha, 'row_index': index,
                'host_binding': binding}, error

    def ingest_query(self, db, rid, request, result, *, deadline=None):
        """新真实ORDER结果保存后同事务认领；历史GET和启动扫描不调用。"""
        if not _order_query(request, result):
            return
        self._owner._finish_deadline(deadline)
        data = self._query_rows(request, result)
        self._owner._finish_deadline(deadline)
        # 基类已经在本事务核原request/result摘要并保存；来源整批只核一次，
        # 避免每条委托重解析完整rows。lookup/重启仍各自核其原记录。
        saved = db.execute('SELECT state,result_binding FROM read_operations WHERE request_id=?', (rid,)).fetchone()
        if saved is None or saved[0] != 'terminal' or type(saved[1]) is not bytes:
            raise JournalConflict('order query result has not been saved')
        observed = decode(saved[1])
        if (self._owner._source(observed) != saved[1]
                or observed['capability_sha256'] != digest(canonical(self._owner.admission_profile))):
            raise JournalConflict('order query source differs')
        for index, payload in enumerate(data['rows']):
            self._owner._finish_deadline(deadline)
            token = payload.get('m_strRemark')
            if type(token) is not str or not token:
                continue
            found = db.execute('SELECT command_id FROM trade_commands WHERE sdk_user_order_id=?', (token,)).fetchone()
            if found is None:
                continue
            record, command = self._insert(db, found[0])
            if record['dispatch_binding'] is None:
                continue
            if (data['account_binding']['account_id'] != command['account_id']
                    or payload.get('m_strAccountID') != command['account_id']):
                raise JournalConflict('order query account differs from original insert')
            if 'm_strInstrumentID' not in payload or 'm_strExchangeID' not in payload:
                continue
            link = self._link(db, found[0])
            if link['association_error'] is not None:
                continue
            broker, error = self._association(command, {'payload': payload})
            if error is None and broker is None:
                continue
            if error is None and link['broker_order_id'] not in (None, broker):
                error = 'broker_identity_conflict'
            retained = link['broker_order_id'] if error is not None else broker
            db.execute('''UPDATE trade_order_links SET broker_order_id=?,association_error=?,
                query_request_id=?,query_row_index=?,query_result_sha256=? WHERE command_id=?''',
                (retained, error, rid, index, result['result_sha256'], found[0]))
            # 包括新增字段的实际逻辑字节仍受原每命令metadata预留约束。
            self._link(db, found[0])
            self._owner._finish_deadline(deadline)

    def lookup(self, db, identity):
        """读取原 insert 与实际事件证明，无匹配返回 None，不依赖当前写开关。"""
        identity = validate_lookup_identity(identity)
        found = None
        if 'sdk_user_order_id' in identity:
            # 完整token沿原唯一列定位；原命令/事件/query证明仍在同一事务重新验证。
            # 不缓存lookup或金融状态，未知token也不遍历其它原委托。
            selected = db.execute('''SELECT link.command_id FROM trade_commands AS command
                JOIN trade_order_links AS link ON link.command_id=command.command_id
                WHERE command.sdk_user_order_id=? LIMIT 2''', (identity['sdk_user_order_id'],))
            candidates = tuple(row[0] for row in (selected.fetchone(),selected.fetchone()) if row is not None)
        else:
            candidates = self._rows(db)
        for cid in candidates:
            record, command = self._insert(db, cid)
            if not all(command[k] == v for k, v in identity.items()):
                continue
            if found is not None:
                raise JournalConflict('original order identity has conflicting inserts')
            link = self._link(db, cid)
            source, query = self._validated_proofs(db, link, command)
            found = {'schema_version': 'qmt.trade-order-reference.v1', 'insert': record,
                'broker_order_id': link['broker_order_id'], 'source': source,
                'source_sequence': link['source_sequence'],
                'source_event_sha256': link['source_event_sha256'],
                'association_error': link['association_error']}
            if query is not None:
                found.update(schema_version='qmt.trade-order-reference.v2', query_observation=query)
        return found

    def _validated_proofs(self, db, link, original):
        return self._proof(db, link, original), self._query_proof(db, link, original)[0]

    def resolves_unknown(self, db, record):
        """仅用原Journal的完整ORDER终态解除原insert等待；结果unknown及原bytes保持。"""
        command = decode(record['body'])
        if command['operation'] != 'order.insert' or record['dispatch_binding'] is None:
            return False
        link = self._link(db, command['command_id'])
        if link['association_error'] is not None:
            return False
        observation, error = self._query_proof(db, link, command)
        if observation is None or error is not None:
            return False
        saved = db.execute('SELECT result FROM read_operations WHERE request_id=?',
                           (observation['request_id'],)).fetchone()
        # _query_proof在同一原事务已核实际bytes、完整列表、账户/原行和摘要。
        result = decode(bytes(saved[0]))
        return terminal_insert_observed(command, result['data']['rows'])

    def validate_cancel(self, db, command, current_source=None):
        record, original = self._insert(db, command['original_command_id'])
        if any(command[key] != original[key] for key in
                ('account_id', 'account_type', 'binding_id', 'entrust_id', 'user_tag')):
            raise JournalConflict('cancel original identity differs')
        if record['dispatch_binding'] is None:
            raise OrderSourceUnavailable('cancel lacks original dispatch')
        link = self._link(db, original['command_id'])
        if link['association_error'] is not None:
            self._owner._fail_trade('order_association_conflict')
            raise JournalConflict('cancel original association conflicts')
        if link['broker_order_id'] is None:
            raise OrderSourceUnavailable('cancel lacks observed broker')
        if link['broker_order_id'] != command['broker_order_id']:
            raise JournalConflict('cancel broker identity differs')
        proof, observation = self._validated_proofs(db, link, original)
        if proof is None and observation is None:
            raise OrderSourceUnavailable('cancel lacks original source proof')
        if current_source is not None:
            actual = self._owner._source(current_source['host_binding'])
            current_event = (proof is not None and self._owner._source(proof['host_binding']) == actual
                             and proof['session_id'] == current_source['session_id'])
            current_query = (observation is not None
                             and self._owner._source(observation['host_binding']) == actual)
            if not (current_event or current_query):
                raise OrderSourceUnavailable('cancel original proof is not current')

    def has_errors(self, db):
        return db.execute('SELECT 1 FROM trade_order_links WHERE association_error IS NOT NULL LIMIT 1').fetchone() is not None

    def initialize(self, db):
        """首次迁移仅恢复原 insert 空索引；已有表只验证原证明，不追认旧事件。"""
        existed = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='trade_order_links'").fetchone() is not None
        db.execute('''CREATE TABLE IF NOT EXISTS trade_order_links (
            command_id TEXT PRIMARY KEY REFERENCES trade_commands(command_id),
            broker_order_id TEXT, source_session_id TEXT, source_binding_id TEXT,
            source_sequence INTEGER, source_event_sha256 TEXT, association_error TEXT,
            FOREIGN KEY(source_session_id,source_binding_id,source_sequence)
                REFERENCES trade_events(session_id,binding_id,sequence))''')
        present = {row[1] for row in db.execute('PRAGMA table_info(trade_order_links)')}
        for name, kind in (('query_request_id', 'TEXT REFERENCES read_operations(request_id)'),
                           ('query_row_index', 'INTEGER'), ('query_result_sha256', 'TEXT')):
            if name not in present:
                db.execute('ALTER TABLE trade_order_links ADD COLUMN ' + name + ' ' + kind)
        columns = db.execute('PRAGMA table_info(trade_order_links)').fetchall()
        if ({row[1] for row in columns} != set(_COLUMNS)
                or [row[1] for row in columns if row[5]] != ['command_id']):
            raise JournalConflict('order link schema differs')
        keys = db.execute('PRAGMA foreign_key_list(trade_order_links)').fetchall()
        expected = {('trade_commands', 'command_id', 'command_id'),
            ('read_operations', 'query_request_id', 'request_id'),
            ('trade_events', 'source_session_id', 'session_id'),
            ('trade_events', 'source_binding_id', 'binding_id'), ('trade_events', 'source_sequence', 'sequence')}
        if {(row[2],row[3],row[4]) for row in keys} != expected:
            raise JournalConflict('order link foreign keys differ')
        cursor = db.execute('SELECT command_id FROM trade_commands ORDER BY seq')
        entrusts, inserts = set(), set()
        for unused in range(self._owner.max_trade_commands + 1):
            row = cursor.fetchone()
            if row is None:
                break
            if unused == self._owner.max_trade_commands:
                raise JournalConflict('retained command capacity differs')
            record = self._owner._record(self._owner._select(db, row[0]))
            command = decode(record['body'])
            if command['operation'] != 'order.insert':
                continue
            if command['entrust_id'] in entrusts:
                raise JournalConflict('retained WT entrust identity conflicts')
            entrusts.add(command['entrust_id']); inserts.add(command['command_id'])
            if not existed:
                db.execute('INSERT INTO trade_order_links(command_id) VALUES(?)', (command['command_id'],))
        if set(self._rows(db)) != inserts:
            raise JournalConflict('order links differ from retained inserts')
        has_events = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='trade_events'").fetchone() is not None
        # 旧事件没有命令/事件先后证明；迁移不得扫描历史 token 补授关联。
        failures = {}
        for cid in self._rows(db):
            unused, command = self._insert(db, cid)
            link = self._link(db, cid)
            self._proof(db, link, command)
            query, query_error = self._query_proof(db, link, command)
            if link['association_error'] is not None and query_error != link['association_error']:
                failures[command['sdk_user_order_id']] = (command, link)
        if failures and not has_events:
            raise JournalConflict('association failure lacks retained source events')
        if failures:
            # 故障证明统一逐行扫描一次，避免命令数乘事件数的恢复开销。
            cursor = db.execute('SELECT body FROM trade_events ORDER BY rowid')
            while failures:
                row = cursor.fetchone()
                if row is None:
                    raise JournalConflict('association failure lacks original evidence')
                event = decode(row[0]); payload = event['payload']
                if event['kind'] not in ('order', 'deal'):
                    continue
                token = payload.get('m_strRemark')
                if type(token) is not str or token not in failures:
                    continue
                command, link = failures[token]
                if payload.get('m_strAccountID') != command['account_id']:
                    continue
                broker, error = self._association(command, event)
                if error is None and broker is not None and link['broker_order_id'] not in (None, broker):
                    error = 'broker_identity_conflict'
                if error == link['association_error']:
                    del failures[token]
