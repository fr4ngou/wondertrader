"""为停止后的 WT 制作可核验的跨盘恢复材料。"""
from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import os
from pathlib import Path
import sqlite3

from .execution_recovery import canonical, execution_state_files, require_process_exited
from .managed_local_process import _identity, _inspect, _json, _open_read, _path, _read, _require, _sha


def file_sha256(path):
    """流式核大文件，比较同一打开句柄的前后身份。"""
    initial = _inspect(path)
    digest = hashlib.sha256()
    with _open_read(path) as stream:
        before = os.fstat(stream.fileno())
        _require(_identity(initial) == _identity(before))
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
        _require(_identity(before) == _identity(os.fstat(stream.fileno())))
    return digest.hexdigest()


def _close_proof(control, root, *, migration_sha256=None):
    marker_path = root / '.cta-clean.json'
    if migration_sha256 is not None:
        archived = root / f'.cta-relocated-{_sha(migration_sha256)}.json'
        if os.path.lexists(archived):
            _require(not os.path.lexists(marker_path))
            marker_path = archived
    marker_raw = _read(marker_path, 256 * 1024)
    marker = _json(marker_raw)
    closed_path = control / 'closed.json'
    raw = _read(closed_path, 4096)
    closed = _json(raw)
    ready = _json(_read(control / 'ready.json', 4096))
    identity = ('pid', 'control_id', 'config_sha256')
    _require(closed['schema'] == 'guanheng.execution.closed.v2'
             and ready['schema'] == 'guanheng.execution.ready.v1'
             and all(ready[key] == closed[key] for key in identity)
             and closed['control_id'] == control.name
             and closed['closed'] is True and closed['ok'] is True
             and closed['recovery_ready'] is True and closed['resources_closed'] is True
             and closed['exit_code'] == 0 and closed['error_code'] is None)
    _require(marker['schema'] == 'guanheng.cta-clean.v2' and marker['closed'] is True
             and marker['pid'] == closed['pid'] and marker['control_id'] == closed['control_id']
             and marker['closed_config_sha256'] == closed['config_sha256']
             and _path(marker['closed_receipt']) == closed_path
             and not (root / '.cta-clean.prepared.json').exists())
    require_process_exited(closed['pid'])
    return marker, hashlib.sha256(marker_raw).hexdigest(), hashlib.sha256(raw).hexdigest()


def _write_copy(source, target):
    initial = _inspect(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    _inspect(target.parent, directory=True)
    with _open_read(source) as original, target.open('xb') as destination:
        _require(_identity(initial) == _identity(os.fstat(original.fileno())))
        for block in iter(lambda: original.read(1024 * 1024), b''):
            destination.write(block)
        _require(_identity(initial) == _identity(os.fstat(original.fileno())))
        destination.flush()
        os.fsync(destination.fileno())


def _database_digest(path):
    digest = file_sha256(path)
    for suffix in ('-wal', '-journal'):
        sidecar = path.with_name(path.name + suffix)
        if os.path.lexists(sidecar):
            _require(_inspect(sidecar).st_size == 0)
    return digest


def _backup(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original, closing(
            sqlite3.connect(target)) as candidate:
        original.backup(candidate)
        _require(candidate.execute('PRAGMA integrity_check').fetchall() == [('ok',)])


def _require_same_qmt_trade_journal(source, target):
    """允许只读查询和新增连接审计，逐表核对其余通信事实。"""
    read_tables = ('read_operations', 'read_retention', 'read_retention_identity')
    auth_table = 'trade_event_auth_connections'
    with closing(sqlite3.connect(target.as_uri() + '?mode=ro', uri=True)) as connection:
        connection.execute('ATTACH DATABASE ? AS original', (source.as_uri() + '?mode=ro',))
        connection.execute('BEGIN')
        schema = "SELECT type,name,tbl_name,sql FROM {}.sqlite_master ORDER BY type,name"
        current = connection.execute(schema.format('main')).fetchall()
        _require(current == connection.execute(schema.format('original')).fetchall())
        for kind, name, _, _ in current:
            if kind != 'table' or name in read_tables:
                continue
            table = '"' + name.replace('"', '""') + '"'
            where = " WHERE name NOT IN (?,?,?)" if name == 'sqlite_sequence' else ''
            args = (*read_tables, *read_tables) if where else ()
            columns = connection.execute(f'PRAGMA main.table_info({table})').fetchall()
            _require(bool(columns))
            group = ','.join(str(column[0] + 1) for column in columns)
            if name == auth_table:
                # 新连接会追加认证审计。原记录必须完整，实际事件仍在下表逐条比对。
                _require(connection.execute(
                    f'SELECT * FROM original.{table} EXCEPT SELECT * FROM main.{table} LIMIT 1'
                ).fetchone() is None)
                continue
            for left, right in (('main', 'original'), ('original', 'main')):
                first = f'SELECT *, count(*) FROM {left}.{table}{where}'
                second = f'SELECT *, count(*) FROM {right}.{table}{where}'
                difference = connection.execute(
                    f'{first} GROUP BY {group} EXCEPT {second} GROUP BY {group} LIMIT 1', args)
                _require(difference.fetchone() is None)


def prepare_private_copy(control, output, journal, allocation, private_root, *, compact_allocation=False):
    """根据原干净退出证明，复制原生文件并一致备份两个 SQLite 库。

    调用者持有原服务的变更租约，且已确认同组所有进程退出。结果用于演练和迁移准入。
    """
    control, output, journal, allocation, private_root = (
        _path(str(path)) for path in (control, output, journal, allocation, private_root))
    _inspect(private_root.parent, directory=True)
    _require(all(not private_root.is_relative_to(path) and not path.is_relative_to(private_root)
                 for path in (control, output, journal, allocation)))
    marker, marker_sha, closed_sha = _close_proof(control, output)
    state_files = execution_state_files(output)
    _require(state_files == marker['files'])
    private_root.mkdir()
    native = private_root / 'native'
    files = set(state_files)
    files.add('.cta-clean.json')
    from .execution_deal_history import FILE_NAME as CLOSED_DEALS
    from .strategy_capital_flow import FILE_NAME as CAPITAL_FLOWS
    for name in (CLOSED_DEALS, CAPITAL_FLOWS):
        if os.path.lexists(output / name):
            files.add(name)
    if CAPITAL_FLOWS in files:
        _database_digest(output / CAPITAL_FLOWS)
    for folder in ('outputs', 'execdata'):
        parent = output / folder
        if parent.exists():
            _inspect(parent, directory=True)
            for root, dirs, names in os.walk(parent):
                for name in dirs:
                    _inspect(Path(root) / name, directory=True)
                for name in names:
                    files.add((Path(root) / name).relative_to(output).as_posix())
    copies = {}
    for name in sorted(files):
        source, target = output / name, native / name
        _write_copy(source, target)
        copies[name] = file_sha256(target)
        _require(copies[name] == file_sha256(source))
    _require(execution_state_files(native) == state_files and copies['.cta-clean.json'] == marker_sha)
    databases = {}
    for role, source in (('qmt', journal), ('allocation', allocation)):
        candidate = private_root / role / source.name
        before = _database_digest(source)
        if role == 'allocation' and compact_allocation:
            from .allocation_compaction import compact
            _require(candidate.name == 'account-allocation.sqlite3')
            compact(source, candidate.parent)
        else:
            _backup(source, candidate)
        _require(_database_digest(source) == before)
        databases[role] = dict(source=str(source), target=str(candidate), source_sha256=before,
                               target_sha256=_database_digest(candidate))
    _require(_close_proof(control, output) == (marker, marker_sha, closed_sha)
             and all(file_sha256(output / name) == digest for name, digest in copies.items())
             and all(_database_digest(_path(entry['source'])) == entry['source_sha256'] for entry in databases.values()))
    value = dict(
        schema='guanheng.wt-private-storage-copy.v1',  # 固定迁移材料；与原退出及数据水位绑定。
        predecessor_control=str(control),  # 原执行进程的干净退出材料目录。
        predecessor_configuration_sha256=_sha(marker['closed_config_sha256']),  # 原生配置身份。
        predecessor_closed_sha256=closed_sha,  # 原干净退出收据摘要。
        original_output=str(output),  # 前代原生输出根。
        target_output=str(native),  # 后继完整原生状态候选根。
        native_files=copies,  # 各原文件及候选相对路径共同的SHA。
        databases=databases,  # 两库前后绝对路径和快照摘要。
        compaction_sha256=(file_sha256(private_root/'allocation'/'verified.json') if compact_allocation else None),
    )
    receipt = private_root / 'verified.json'
    raw = canonical(value)
    with receipt.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return dict(file=str(receipt), sha256=hashlib.sha256(raw).hexdigest())



def pending_target_marker(root, original_marker_digest):
    """原生认领之前的关闭凭据。已发布认领的目录必须走正常恢复。"""
    _require(not any(root.glob('.cta-reconciled-*.json*')))
    active = root / '.cta-clean.json'
    marker = active if os.path.lexists(active) else root / '.cta-clean.consumed.json'
    _require(file_sha256(marker) == _sha(original_marker_digest))
    return marker


@contextmanager
def native_output_lease(root):
    """沿 Native 的独占文件句柄锁，协调两个目录的恢复凭据变更。"""
    import ctypes
    from ctypes import wintypes

    _inspect(root, directory=True)
    path = root / '.cta-session.lock'
    if os.path.lexists(path):
        _inspect(path)
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes, api.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
    handle = api.CreateFileW(str(path), 0xC0000000, 0, None, 4, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        _inspect(path)
        yield
    finally:
        _require(bool(api.CloseHandle(handle)))


@contextmanager
def journal_owner_lease(journal):
    """沿 QMT 通信库原 owner 字节锁，核候选和原库都已离线。"""
    import msvcrt

    path = journal.with_suffix(journal.suffix + '.owner')
    _inspect(path.parent, directory=True)
    if os.path.lexists(path):
        _inspect(path)
    with path.open('a+b') as stream:
        _inspect(path)
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _move_durable(source, target):
    """同卷独占移动；返回前由 Windows 确认元数据写入。"""
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    api.MoveFileExW.restype = wintypes.BOOL
    if not api.MoveFileExW(str(source), str(target), 8):  # MOVEFILE_WRITE_THROUGH
        raise ctypes.WinError(ctypes.get_last_error())


def abandon_private_copy(reference, *, control, configuration_sha256, output, journal, allocation):
    """候选从未认领且两库水位未变时，退役候选并恢复旧目录凭据。"""
    receipt, value = private_copy_reference(reference)
    output = _path(str(output))
    target = _path(value['target_output'])
    _require(target == receipt.parent / 'native' and output == _path(value['original_output']) and target != output)
    cancel = receipt.parent / 'abandoned.json'
    cancelled = canonical({'schema': 'guanheng.wt-private-storage-abandoned.v1', 'receipt_sha256': reference['sha256']})
    source_journal = _path(str(journal))
    candidate_journal = _path(value['databases']['qmt']['target'])
    _require(candidate_journal.parent == receipt.parent / 'qmt' and candidate_journal != source_journal)
    with (native_output_lease(output), native_output_lease(target),
          journal_owner_lease(source_journal), journal_owner_lease(candidate_journal)):
        retry = os.path.lexists(cancel)
        if retry:
            _require(_read(cancel, 4096) == cancelled)
        verify_private_copy(reference, control=control, configuration_sha256=configuration_sha256,
            output=output, journal=journal, allocation=allocation, target_output=target,
            target_journal=value['databases']['qmt']['target'],
            target_allocation=value['databases']['allocation']['target'], allow_abandoned=retry,
            allow_qmt_read_progress=True)
        if not retry:
            from uuid import uuid4
            pending = receipt.parent / ('.abandoned-' + str(uuid4()) + '.pending')
            with pending.open('xb') as stream:
                stream.write(cancelled)
                stream.flush()
                os.fsync(stream.fileno())
            _move_durable(pending, cancel)
        archived = output / f".cta-relocated-{_sha(reference['sha256'])}.json"
        if archived.exists():
            _move_durable(archived, output / '.cta-clean.json')
        return {'state': 'abandoned', 'receipt_sha256': reference['sha256']}


def verify_private_copy(reference, *, control, configuration_sha256, output, journal, allocation,
                        target_output, target_journal, target_allocation, allow_abandoned=False,
                        allow_qmt_read_progress=False):
    """核本次准备材料和实际前后目录。原进程关闭、文件变更或错配均会被发现。"""
    receipt, value = private_copy_reference(reference)
    _require(allow_abandoned or not os.path.lexists(receipt.parent / 'abandoned.json'))
    control, output, target_output = (_path(str(path)) for path in (control, output, target_output))
    marker, marker_sha, closed_sha = _close_proof(control, output, migration_sha256=reference['sha256'])
    _require(set(value) == {'schema', 'predecessor_control', 'predecessor_configuration_sha256',
                            'predecessor_closed_sha256', 'original_output', 'target_output',
                            'native_files', 'databases', 'compaction_sha256'}
             and value['schema'] == 'guanheng.wt-private-storage-copy.v1'
             and _path(value['predecessor_control']) == control
             and value['predecessor_configuration_sha256'] == configuration_sha256 == marker['closed_config_sha256']
             and value['predecessor_closed_sha256'] == closed_sha
             and _path(value['original_output']) == output
             and _path(value['target_output']) == target_output == receipt.parent / 'native')
    native_files = value['native_files']
    _require(type(native_files) is dict and native_files.get('.cta-clean.json') == marker_sha
             and all(native_files.get(name) == digest for name, digest in marker['files'].items())
             and execution_state_files(target_output) == marker['files'])
    target_marker = pending_target_marker(target_output, marker_sha)
    if target_marker.name == '.cta-clean.consumed.json' and not allow_abandoned:
        _require(not os.path.lexists(output / '.cta-clean.json'))
    for name, digest in native_files.items():
        if name == '.cta-clean.json':
            continue  # 同一份关闭凭据的前后摘要已核。
        original = _path(str(output / name))
        target = _path(str(target_output / name))
        _require(original.is_relative_to(output) and target.is_relative_to(target_output)
                 and file_sha256(original) == _sha(digest) == file_sha256(target))
    databases = value['databases']
    _require(type(databases) is dict and set(databases) == {'qmt', 'allocation'})
    for role, source, target in (('qmt', journal, target_journal),
                                 ('allocation', allocation, target_allocation)):
        row = databases[role]
        _require(type(row) is dict and set(row) == {'source', 'target', 'source_sha256', 'target_sha256'})
        source = _path(str(source))
        target = _path(str(target))
        _require(_path(row['source']) == source and _path(row['target']) == target
                 and target.parent == receipt.parent / role
                 and _database_digest(source) == _sha(row['source_sha256']))
        target_digest = _database_digest(target)
        if role == 'qmt' and allow_qmt_read_progress and target_digest != _sha(row['target_sha256']):
            _require_same_qmt_trade_journal(source, target)
        else:
            _require(target_digest == _sha(row['target_sha256']))
    compaction_sha = value['compaction_sha256']
    from .strategy_capital_flow import FILE_NAME as CAPITAL_FLOWS
    if CAPITAL_FLOWS in native_files:
        _database_digest(output / CAPITAL_FLOWS)
        _database_digest(target_output / CAPITAL_FLOWS)
    if compaction_sha is not None:
        report_path = receipt.parent/'allocation'/'verified.json'
        report_raw = _read(report_path, 4096)
        _require(hashlib.sha256(report_raw).hexdigest() == _sha(compaction_sha))
        artifacts = _json(report_raw)['sha256']
        _require(set(artifacts) == {'account-allocation.sqlite3', 'original.sqlite3', 'receipt-map.sqlite3'})
        for name, digest in artifacts.items():
            _require(_database_digest(report_path.parent / name) == _sha(digest))
    return value



def private_copy_reference(reference):
    """读取固定跨盘材料。持续使用的配置仅依赖材料本身，运行库可继续推进。"""
    _require(type(reference) is dict and set(reference) == {'file', 'sha256'})
    receipt = _path(reference['file'])
    raw = _read(receipt, 4 * 1024 * 1024)
    _require(hashlib.sha256(raw).hexdigest() == _sha(reference['sha256']))
    value = _json(raw)
    _require(value.get('schema') == 'guanheng.wt-private-storage-copy.v1')
    return receipt, value


def configured_private_copy(native):
    """解析显式私有根并校验它与原生、分账目录一致。"""
    reference = native.get('private_storage_origin')
    if reference is None:
        return None
    receipt, value = private_copy_reference(reference)
    original = _path(value['original_output'])
    target = _path(value['target_output'])
    allocation = _path(value['databases']['allocation']['target'])
    _require(original != target and target.drive.casefold() in ('d:', 'e:')
             and target == _path(native['output_directory']) == receipt.parent / 'native'
             and allocation == receipt.parent / 'allocation' / 'account-allocation.sqlite3'
             and _path(native['shared_account_storage']['allocation_root']) == allocation.parent)
    return value
