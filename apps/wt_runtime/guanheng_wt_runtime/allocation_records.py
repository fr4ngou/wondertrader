"""归属账本持久行。同一个 SQLite 事务按原身份读取、修改及提交相关记录。"""
import hashlib
import json
from decimal import Decimal, InvalidOperation


KINDS = ('plans', 'groups', 'children', 'commands', 'fills')


def digest(raw):
    return hashlib.sha256(raw.encode('ascii')).hexdigest()


def decode(raw, sha256, wire):
    if digest(raw) != sha256:
        raise ValueError('storage_invalid')
    value = json.loads(raw)
    if wire(value) != raw:
        raise ValueError('storage_invalid')
    return value


def schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS asa_record ('
               'kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, sha256 TEXT NOT NULL, '
               'active INTEGER NOT NULL, PRIMARY KEY(kind,id))')
    db.execute('CREATE INDEX IF NOT EXISTS asa_record_active ON asa_record(kind,active,id)')
    db.execute('CREATE TABLE IF NOT EXISTS asa_source_proof ('
               'kind TEXT NOT NULL, id TEXT NOT NULL, proof_id TEXT NOT NULL, payload TEXT NOT NULL, '
               'sha256 TEXT NOT NULL, PRIMARY KEY(kind,id,proof_id))')
    db.execute("""CREATE INDEX IF NOT EXISTS asa_inbox_pending_order ON asa_inbox(
        json_extract(CAST(raw_json AS TEXT), '$.user_tag'), sequence)
        WHERE applied=0 AND kind IN ('8','9')""")
    db.execute("""CREATE INDEX IF NOT EXISTS asa_inbox_pending_local ON asa_inbox(sequence)
        WHERE applied=0 AND kind NOT IN ('8','9')""")


def ensure_broker_receipt_index(db):
    # 老库保留原收件，离线归并在副本中补齐键。
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='asa_inbox_receipt'").fetchone() is None:
        db.execute('ALTER TABLE asa_inbox ADD COLUMN receipt_key TEXT')
        db.execute('CREATE UNIQUE INDEX asa_inbox_receipt ON asa_inbox(receipt_key) WHERE receipt_key IS NOT NULL')


def broker_receipt_key(kind, payload, wire):
    """以柜台业务状态去重，保留不同来源类型、经济变化和原始证据。"""
    identity = payload.get('trade_id' if kind == '8' else 'order_id')
    if (kind not in ('8', '9') or type(identity) is not str or not identity
            or type(payload.get('trading_date')) is not int
            or payload.get('source_kind') not in ('query-result', 'derived-facts')):
        return None
    transport = {
        'instance_id', 'native_generation', 'group_id', 'source_sha256', 'output_index', 'request_id',
        'result_sha256', 'lookup_sha256', 'sequence', 'derived_page_sha256', 'derived_event_sha256',
        'canonical_key_sha256',
    }
    # 实时独立来源以柜台的稳定证据键区分，查询批次身份仍不参与比较。
    if payload['source_kind'] == 'derived-facts':
        transport.remove('canonical_key_sha256')
    fact = {key: value for key, value in payload.items() if key not in transport}
    for key in ('quantity', 'filled_quantity', 'remaining_quantity'):
        value = fact.get(key)
        if type(value) is float and value.is_integer():
            fact[key] = int(value)
    if kind == '8':
        fact.setdefault('fee_cny', None)
    # 仅合并精确相等的十进制文本。离档价格与非法值继续进入原校验。
    for key in ('price_cny', 'amount_cny', 'fee_cny'):
        value = fact.get(key)
        if type(value) is not str or not 0 < len(value) <= 128:
            continue
        try:
            number = Decimal(value)
        except InvalidOperation:
            continue
        if not number.is_finite():
            continue
        sign, digits, exponent = number.as_tuple()
        if not number:
            fact[key] = '0'
            continue
        end = len(digits)
        while digits[end-1] == 0:
            end -= 1
        coefficient = ''.join(map(str, digits[:end]))
        fact[key] = f'{"-" if sign else ""}{coefficient}e{exponent+len(digits)-end}'
    return digest(wire([kind, fact]))


def save_proof(db, kind, identity, proof_id, payload, wire):
    raw = wire(payload)
    row = db.execute('SELECT payload,sha256 FROM asa_source_proof WHERE kind=? AND id=? AND proof_id=?',
                     (kind, identity, proof_id)).fetchone()
    if row is not None:
        if row != (raw, digest(raw)):
            raise ValueError('storage_invalid')
        return False
    db.execute('INSERT INTO asa_source_proof VALUES (?,?,?,?,?)',
               (kind, identity, proof_id, raw, digest(raw)))
    return True


def active(kind, value):
    if kind == 'groups':
        return int(not value['closed'])
    if kind == 'children':
        return int(value['command'] is not None)
    if kind == 'fills':
        return int(value['fee'] is None)
    return 0


class Records:
    """一次归属操作的原身份缓存。写入只比较已经访问的行。"""
    def __init__(self, db, kind, wire):
        self.db = db  # 借用当前线程 SQLite 事务。
        self.kind = kind  # 原归属实体类型。
        self.wire = wire  # 账本原有规范编码。
        self.loaded = {}  # 访问过的实体，按原 ID 复用。
        self.original = {}  # 同一行初次读取的原编码。

    def __getitem__(self, identity):
        if identity not in self.loaded:
            row = self.db.execute('SELECT payload,sha256 FROM asa_record WHERE kind=? AND id=?',
                                  (self.kind, identity)).fetchone()
            if row is None:
                raise KeyError(identity)
            self.loaded[identity] = decode(*row, self.wire)
            self.original[identity] = row[0]
        return self.loaded[identity]

    def get(self, identity, default=None):
        try:
            return self[identity]
        except KeyError:
            return default

    def __contains__(self, identity):
        return identity in self.loaded or self.db.execute(
            'SELECT 1 FROM asa_record WHERE kind=? AND id=?', (self.kind, identity)).fetchone() is not None

    def __setitem__(self, identity, value):
        self.loaded[identity] = value

    def items(self, *, active_only=False):
        query = 'SELECT id FROM asa_record WHERE kind=?'
        if active_only:
            query += ' AND active=1'
        keys = {row[0] for row in self.db.execute(query, (self.kind,))}
        keys.update(key for key, value in self.loaded.items() if not active_only or active(self.kind, value))
        for key in sorted(keys):
            value = self[key]
            if not active_only or active(self.kind, value):
                yield key, value

    def save(self):
        for key, value in self.loaded.items():
            raw = self.wire(value)
            if raw == self.original.get(key):
                continue
            self.db.execute('INSERT INTO asa_record VALUES (?,?,?,?,?) '
                            'ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,'
                            'sha256=excluded.sha256,active=excluded.active',
                            (self.kind, key, raw, digest(raw), active(self.kind, value)))
