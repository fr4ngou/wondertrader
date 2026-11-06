"""停止状态下显式扩展原事件容量；金融事实与普通启动语义继续归原owner。"""
from contextlib import contextmanager
import base64
import hashlib
import math
from pathlib import Path

from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.trade_clock import SharedUptimeClock
from .bound import digest, sha256_text
from .journal import HostReadJournal, JournalConflict, construct_journal
from .read_retention_journal import RetainedTradingJournal
from .trade_event_records import CONTINUITY_VERSION, validate_trade_event_storage
from .trade_pair import _inspect, _verified, material_deadline, _check_material_deadline
from .trading_journal import HostTradingJournal
from .trading_journal import _DeadlineCursor


class _CheckedCursor(_DeadlineCursor):
    def __getattr__(self, name):
        self._check()
        value = getattr(self._cursor, name)
        self._check()
        if callable(value):
            raise AttributeError('unchecked cursor operation is unavailable during maintenance')
        return value

    def __iter__(self):
        return self

    def __next__(self):
        self._check()
        try:
            value = next(self._cursor)
        except StopIteration:
            self._check()
            raise
        self._check()
        return value


class _CheckedConnection:
    """同一原连接的截止代理；rollback/close只作物理退休，不重开业务。"""
    def __init__(self, database, deadline):
        self._database, self._deadline = database, deadline

    def _check(self):
        HostReadJournal._finish_deadline(self._deadline)

    def __getattr__(self, name):
        self._check()
        value = getattr(self._database, name)
        self._check()
        if callable(value):
            raise AttributeError('unchecked connection operation is unavailable during maintenance')
        return value

    def execute(self, *args):
        self._check()
        cursor = self._database.execute(*args)
        self._check()
        return _CheckedCursor(cursor, self._check)

    def commit(self):
        self._check()
        self._database.commit()
        self._check()

    def rollback(self):
        return self._database.rollback()

    def close(self):
        return self._database.close()


def _schema(database):
    rows = database.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
    if any(row[0] not in ('table', 'index') for row in rows):
        raise JournalConflict('event capacity maintenance requires the original Journal schema')
    return rows


class _MaintenanceValidation:
    """借用原验证和租约；构造期任何持久事实/结构变更均在提交前拒绝。

    普通构造可能恢复旧dispatch或补旧schema。维护只接受已完整初始化、
    本次验证无需改变的原库，避免把这些启动副作用混入容量变更。
    """
    def __init__(self, *args, maintenance_deadline, **kwargs):
        self._maintenance_deadline = maintenance_deadline
        self._maintenance_opening = True
        super().__init__(*args, **kwargs)
        self._maintenance_opening = False

    @contextmanager
    def _transaction(self, deadline=None):
        selected = self._maintenance_deadline if deadline is None else min(deadline, self._maintenance_deadline)
        with super()._transaction(selected) as database:
            if self._maintenance_opening:
                before_schema = _schema(database)
                tables = {row[1] for row in before_schema
                    if row[0] == 'table' and not row[1].startswith('sqlite_')}
                if not self._maintenance_schema_matches(tables):
                    raise JournalConflict('event capacity maintenance requires an initialized Journal')
                before_changes = database.total_changes
            yield database
            if self._maintenance_opening and (database.total_changes != before_changes
                    or _schema(database) != before_schema):
                raise JournalConflict('event capacity validation would change retained facts')

    def _maintenance_schema_matches(self,tables):
        return tables==self.schema_tables

    def close(self, deadline=None):
        # 新截止只授失败后的物理回收；事务始终夹在首次维护D内。
        selected = self._maintenance_deadline if deadline is None else deadline
        super().close(deadline=selected)
        HostReadJournal._finish_deadline(selected)

    def _open_connection(self, timeout):
        HostReadJournal._finish_deadline(self._maintenance_deadline)
        # 原owner在返回后先保存代理，再经其execute核connect晚回，保留可关闭责任。
        return _CheckedConnection(super()._open_connection(timeout), self._maintenance_deadline)

    def _check_owner_deadline(self):
        HostReadJournal._finish_deadline(self._maintenance_deadline)


class _TradingMaintenance(_MaintenanceValidation, HostTradingJournal):
    pass


class _RetainedTradingMaintenance(_MaintenanceValidation, RetainedTradingJournal):
    pass


def _facts(database, deadline, *, excluded_tables=frozenset(('trade_event_identity',))):
    """返回有界的表摘要；原BLOB/账户/请求正文始终留在原事务内。"""
    schema = [row for row in _schema(database) if row[1]not in excluded_tables and row[2]not in excluded_tables]
    tables = []
    for unused, name, unused_table, unused_sql in schema:
        if unused != 'table':
            continue
        # 名称来自已验证的固定表集合或SQLite原自增表；双引号只转义标识符。
        quoted = '"' + name.replace('"', '""') + '"'
        columns = database.execute('PRAGMA table_info(' + quoted + ')').fetchall()
        keys = [row[1] for row in sorted(columns, key=lambda row: row[5]) if row[5]]
        order = ','.join('"' + key.replace('"', '""') + '"' for key in keys) or 'rowid'
        value = hashlib.sha256(canonical(columns))
        count = 0
        cursor = database.execute('SELECT * FROM ' + quoted + ' ORDER BY ' + order)
        while True:
            HostReadJournal._finish_deadline(deadline)
            row = cursor.fetchone()
            HostReadJournal._finish_deadline(deadline)
            if row is None:
                break
            encoded = canonical([{'blob': base64.b64encode(item).decode('ascii')}
                if type(item) is bytes else {'value': item} for item in row])
            value.update(len(encoded).to_bytes(8, 'big'))
            value.update(encoded)
            count += 1
        tables.append(dict(table=name, rows=count, sha256=value.hexdigest()))
    return dict(schema_sha256=digest(canonical(schema)), tables=tables,
        facts_sha256=digest(canonical(tables)))


def expand_product_event_storage(directory, *, expected_identity_sha256, event_storage,
                                 deadline, installed_agent=None, failed_owners=None):
    """核原配对后扩展原Journal，返回qmt.trade-event-storage-expansion.v1。

    deadline为调用者首次固定的绝对monotonic秒。只增加max_streams和可选
    max_bytes，其他容量及来源/profile保持。原文件租约持有到close成功。
    不启动运输/域/SDK/WT，不重写配对文件；新运行须显式生成新容量材料。
    构造/提交/关闭失败原样传播；commit晚回可能已生效，须核原身份，不重做
    金融操作。failed_owners为原单槽责任接缝，关闭未确认时保留同一owner。
    """
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError('event capacity maintenance requires an absolute deadline')
    HostReadJournal._finish_deadline(deadline)
    expected_identity_sha256 = sha256_text(expected_identity_sha256)
    if failed_owners is not None and (type(failed_owners) is not list
            or len(failed_owners) != 1 or failed_owners[0] is not None):
        raise ValueError('event capacity maintenance requires one empty owner slot')
    unused_identity, snapshot = _verified(directory, installed_agent, deadline=deadline)
    config, unused_credentials, unused_settings, unused_policies, public, admitted, unused_lifecycle = snapshot
    old_storage = config['event_storage']
    new_storage, unused_limits, unused_identity, unused_sha = validate_trade_event_storage(
        admitted.profile, admitted.trade_binding, event_storage,
        max_result_bytes=config['max_result_bytes'])
    if (new_storage['max_streams'] <= old_storage['max_streams']
            or new_storage['max_bytes'] < old_storage['max_bytes']
            or any(new_storage[key] != old_storage[key] for key in ('max_events', 'max_page_bytes'))):
        raise ValueError('event capacity maintenance only expands streams and bytes')
    path = Path(config['journal_path'])
    lock_path = path.with_suffix(path.suffix + '.owner')
    with material_deadline(deadline):
        _inspect(path)
        exists = lock_path.exists()
        _check_material_deadline()
        if exists:
            _inspect(lock_path)
    HostReadJournal._finish_deadline(deadline)
    journal_type, extra = _TradingMaintenance, {}
    if 'read_retention' in config:
        from .bulk_clock import WindowsBulkUptimeClock
        journal_type = _RetainedTradingMaintenance
        extra['retention_clock'] = WindowsBulkUptimeClock()
    limits = admitted.profile['trade_profile']['limits']
    owner = construct_journal(journal_type, path, config['route'],
        failed_owners=failed_owners, maintenance_deadline=deadline,
        max_records=config['max_records'], max_result_bytes=config['max_result_bytes'],
        max_request_bytes=public['max_request_bytes'], max_journal_bytes=config['max_journal_bytes'],
        trade_binding=admitted.trade_binding, max_trade_commands=limits['max_commands'],
        max_trade_bytes=config['max_trade_bytes'], max_trade_result_bytes=limits['max_call_result_bytes'],
        read_profile=admitted.profile, event_storage=old_storage,
        clock=SharedUptimeClock().seconds, connection_continuity=CONTINUITY_VERSION, **extra)
    if failed_owners is not None:
        failed_owners[0] = owner
    try:
        old_identity = owner.events._identity_bytes
        if digest(old_identity) != expected_identity_sha256:
            raise JournalConflict('event capacity original identity differs')
        profile = dict(admitted.profile)
        stored = decode(old_identity)
        if digest(canonical(profile)) != stored['profile_sha256']:
            profile.pop('read_retention', None)
        unused_storage, unused_limits, new_identity, unused_sha = validate_trade_event_storage(
            profile, admitted.trade_binding, new_storage, max_result_bytes=config['max_result_bytes'])
        if (digest(canonical(profile)) != stored['profile_sha256']
                or decode(new_identity)['binding_sha256'] != stored['binding_sha256']):
            raise JournalConflict('event capacity original profile differs')
        with owner._transaction(deadline) as database:
            row = database.execute('SELECT value FROM trade_event_identity WHERE id=1').fetchone()
            if row != (old_identity,):
                raise JournalConflict('event capacity original identity changed')
            before = _facts(database, deadline)
            changed = database.execute('UPDATE trade_event_identity SET value=? WHERE id=1 AND value=?',
                (new_identity, old_identity)).rowcount
            after = _facts(database, deadline)
            if changed != 1 or before != after:
                raise JournalConflict('event capacity maintenance changed retained facts')
            result = dict(schema_version='qmt.trade-event-storage-expansion.v1',
                old_identity_sha256=expected_identity_sha256, new_identity_sha256=digest(new_identity),
                old_event_storage=dict(old_storage), new_event_storage=dict(new_storage),
                facts_sha256_before=before['facts_sha256'], facts_sha256_after=after['facts_sha256'],
                schema_sha256=before['schema_sha256'], tables=before['tables'],
                changed_identity_rows=changed, constructor_fact_changes=0,
                transport_started=False, SDK_calls=0, WT_started=False)
    finally:
        try:
            owner.close(deadline=deadline)
        finally:
            if failed_owners is not None and owner._owner.closed and owner._database is None:
                failed_owners[0] = None
    HostReadJournal._finish_deadline(deadline)
    result['journal_owner_closed'] = owner._owner.closed and owner._database is None
    return result


def main(argv=None):
    """显式离线维护CLI；超时失败只作物理回收，输出不确认任何SDK副作用。"""
    import argparse
    import json
    import sys
    import time

    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError('event capacity CLI arguments')

    owners = [None]
    cleanup_seconds = None
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('--directory', type=Path, required=True)
        parser.add_argument('--installed-agent', type=Path, required=True)
        parser.add_argument('--expected-identity-sha256', required=True)
        for field in ('max-streams', 'max-events', 'max-bytes', 'max-page-bytes'):
            parser.add_argument('--' + field, type=int, required=True)
        parser.add_argument('--timeout-seconds', type=float, required=True)
        parser.add_argument('--cleanup-seconds', type=float, required=True)
        arguments = list(sys.argv[1:] if argv is None else argv)
        if not arguments:
            parser.print_help()
            return 0
        args = parser.parse_args(arguments)
        if any(not math.isfinite(value) or not .001 <= value <= 300
                for value in (args.timeout_seconds, args.cleanup_seconds)):
            raise ValueError('explicit bounded maintenance and cleanup budgets required')
        cleanup_seconds = args.cleanup_seconds
        deadline = time.monotonic() + args.timeout_seconds
        result = expand_product_event_storage(args.directory,
            expected_identity_sha256=args.expected_identity_sha256,
            event_storage=dict(max_streams=args.max_streams, max_events=args.max_events,
                max_bytes=args.max_bytes, max_page_bytes=args.max_page_bytes),
            deadline=deadline, installed_agent=args.installed_agent, failed_owners=owners)
        print(json.dumps(dict(schema_version='qmt.trade-event-maintenance-cli.v1', ok=True,
            outcome_confirmed=True, result=result), ensure_ascii=True))
        return 0
    except Exception:
        # 工作D保持原值。后继预算只交给同一owner的物理close，不继续维护事务。
        if owners[0] is not None and cleanup_seconds is not None:
            try:
                owners[0].close(deadline=time.monotonic() + cleanup_seconds)
            except Exception:
                pass
        closed = owners[0] is None or (owners[0]._owner.closed and owners[0]._database is None)
        print(json.dumps(dict(schema_version='qmt.trade-event-maintenance-cli.v1', ok=False,
            outcome_confirmed=False, journal_owner_closed=closed,
            error_code='maintenance_not_confirmed'), ensure_ascii=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
