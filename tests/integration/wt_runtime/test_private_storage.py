"""正式恢复材料按原退出收据、快照及独占目标路径核验。"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from guanheng_wt_runtime import private_storage
from guanheng_wt_runtime.execution_recovery import (
    _require_storage_predecessor, canonical, compatible_business_configuration, execution_state_files,
)
from guanheng_wt_runtime.service_control import ServiceController


def fixture(root, pid):
    control = root / str(uuid4())
    control.mkdir()
    output = root / 'origin'
    (output / 'portfolio').mkdir(parents=True)
    (output / 'outputs' / 'strategy').mkdir(parents=True)
    (output / 'portfolio' / 'datas.json').write_bytes(b'{"fund": 1234}')
    (output / 'outputs' / 'strategy' / 'trades.csv').write_bytes(b'original records')
    bound = dict(control_id=control.name, config_sha256='a'*64, pid=pid)
    ready = dict(schema='guanheng.execution.ready.v1', **bound)
    closed = dict(schema='guanheng.execution.closed.v2', **bound, closed=True, ok=True,
                  recovery_ready=True, resources_closed=True, exit_code=0, error_code=None)
    (control / 'ready.json').write_bytes(canonical(ready))
    (control / 'closed.json').write_bytes(canonical(closed))
    marker = dict(schema='guanheng.cta-clean.v2', closed=True, control_id=control.name,
                  pid=pid, closed_config_sha256='a'*64, closed_receipt=str(control / 'closed.json'),
                  files=execution_state_files(output))
    (output / '.cta-clean.json').write_bytes(canonical(marker))
    databases = (root / 'communication.sqlite3', root / 'account-allocation.sqlite3')
    for database in databases:
        with closing(sqlite3.connect(database)) as db, db:
            db.execute('CREATE TABLE original (sequence INTEGER PRIMARY KEY, state TEXT)')
            db.execute("INSERT INTO original VALUES (17, 'unresolved')")
            if database == databases[0]:
                db.execute('CREATE TABLE read_operations (sequence INTEGER PRIMARY KEY AUTOINCREMENT)')
                db.execute('CREATE TABLE trade_event_auth_connections (id INTEGER PRIMARY KEY)')
                db.execute('INSERT INTO trade_event_auth_connections VALUES (1)')
    return control, output, *databases


@pytest.mark.skipif(os.name != 'nt', reason='使用原 Windows 退出证明')
def test_prepares_complete_private_copy_from_exited_owner(tmp_path, monkeypatch):
    # Popen 保留实际 PID。正常退出后仍可由系统证明已回收。
    with subprocess.Popen([sys.executable, '-B', '-c', '']) as owner:
        assert owner.wait(timeout=5) == 0
        inputs = fixture(tmp_path, owner.pid)
    target = tmp_path / 'private'
    reference = private_storage.prepare_private_copy(*inputs, target)
    receipt = target / 'verified.json'
    value = json.loads(receipt.read_bytes())
    assert reference == dict(file=str(receipt), sha256=private_storage.file_sha256(receipt))
    assert (target / 'native/outputs/strategy/trades.csv').read_bytes() == b'original records'
    assert execution_state_files(target / 'native') == execution_state_files(inputs[1])
    for role in ('qmt', 'allocation'):
        info = value['databases'][role]
        info_path = Path(info['target'])
        assert info_path.parent == target / role
        assert private_storage.file_sha256(info_path) == info['target_sha256']
        with closing(sqlite3.connect(info_path)) as db:
            assert db.execute('SELECT * FROM original').fetchall() == [(17, 'unresolved')]
    arguments = dict(control=inputs[0], configuration_sha256='a'*64, output=inputs[1], journal=inputs[2],
                     allocation=inputs[3], target_output=target/'native',
                     target_journal=target/'qmt'/inputs[2].name,
                     target_allocation=target/'allocation'/inputs[3].name)
    assert private_storage.verify_private_copy(reference, **arguments) == value
    qmt = arguments['target_journal']
    original_qmt = qmt.read_bytes()
    with closing(sqlite3.connect(qmt)) as db, db:
        db.execute("INSERT INTO read_operations DEFAULT VALUES")
        db.execute('INSERT INTO trade_event_auth_connections VALUES (2)')
        db.execute("UPDATE original SET state='changed'")
    with pytest.raises(ValueError):
        private_storage.verify_private_copy(reference, **arguments, allow_qmt_read_progress=True)
    with closing(sqlite3.connect(qmt)) as db, db:
        db.execute("UPDATE original SET state='unresolved'")
    assert private_storage.verify_private_copy(reference, **arguments, allow_qmt_read_progress=True) == value
    with closing(sqlite3.connect(qmt)) as db, db:
        db.execute('DELETE FROM trade_event_auth_connections WHERE id=1')
    with pytest.raises(ValueError):
        private_storage.verify_private_copy(reference, **arguments, allow_qmt_read_progress=True)
    qmt.write_bytes(original_qmt)
    original_config = dict(output_directory=str(inputs[1]), budget={'run_ms': 0},
                           trader={'binding_sha256': 'd'*64, 'base_url': 'http://127.0.0.1:1234'})
    successor = {**original_config, 'output_directory': str(target/'native'),
                 'shared_account_storage': {'allocation_root': str(target/'allocation')},
                 'private_storage_origin': reference}
    assert compatible_business_configuration(successor, original_config)
    _require_storage_predecessor(successor, original_config, inputs[0], 'a'*64)
    with pytest.raises(ValueError):
        _require_storage_predecessor(successor, original_config, inputs[0], 'b'*64)
    _require_storage_predecessor(successor, successor, target, 'c'*64)  # 同根重启保留原材料。

    before = SimpleNamespace(components=(('trade_host', 'original'),))
    after = SimpleNamespace(components=(('trade_host', 'successor'),), startup_seconds=5)
    controller = ServiceController(None)
    identities = {
        'original': {'journal_path': str(inputs[2]), 'trade_binding_sha256': 'd'*64},
        'successor': {'journal_path': str(arguments['target_journal']), 'trade_binding_sha256': 'd'*64},
    }
    def deployment_identity(component, *, include_storage_model=False):
        result = (identities[component], ('127.0.0.1', 1234))
        return (*result, 'fixed-model') if include_storage_model else result

    monkeypatch.setattr(controller, '_trade_deployment_identity', deployment_identity)
    def storage(native, *, deadline):
        if native is original_config:
            return {}, inputs[3].parent, inputs[1]
        return {}, target/'allocation', target/'native'

    from guanheng_wt_runtime import shared_account_configuration
    monkeypatch.setattr(shared_account_configuration, 'allocation_storage', storage)
    with pytest.raises(ValueError):
        controller._require_managed_trade_handoff(before, after, original_config, successor)
    controller._require_managed_trade_handoff(before, after, original_config, successor,
        private_storage=reference, predecessor_control=inputs[0], predecessor_sha='a'*64)
    slash_reference = {**reference, 'file': Path(reference['file']).as_posix()}
    controller._require_managed_trade_handoff(before, after, original_config, successor,
        private_storage=slash_reference, predecessor_control=inputs[0], predecessor_sha='a'*64)
    with pytest.raises(FileExistsError):
        private_storage.prepare_private_copy(*inputs, target)
    sidecar = arguments['target_journal'].with_name(arguments['target_journal'].name + '-wal')
    sidecar.write_bytes(b'new WAL contents')
    with pytest.raises(ValueError):
        private_storage.verify_private_copy(reference, **arguments)
    sidecar.unlink()
    old_marker = inputs[1] / '.cta-clean.json'
    archived_marker = inputs[1] / ('.cta-relocated-' + reference['sha256'] + '.json')
    old_marker.rename(archived_marker)
    assert private_storage.verify_private_copy(reference, **arguments) == value
    old_marker.write_bytes(archived_marker.read_bytes())
    with pytest.raises(ValueError):
        private_storage.verify_private_copy(reference, **arguments)
    old_marker.unlink()
    candidate_marker = target / 'native' / '.cta-clean.json'
    candidate_marker.rename(candidate_marker.with_name('.cta-clean.consumed.json'))
    assert private_storage.verify_private_copy(reference, **arguments) == value
    claim = target / 'native' / ('.cta-reconciled-' + 'e'*64 + '.json')
    claim.write_bytes(b'{}')
    with pytest.raises(ValueError):
        private_storage.verify_private_copy(reference, **arguments)
    claim.unlink()
    (target/'native/outputs/strategy/trades.csv').write_bytes(b'replaced history')
    with pytest.raises(ValueError):
        private_storage.verify_private_copy(reference, **arguments)


@pytest.mark.skipif(os.name != 'nt', reason='使用原 Windows 退出证明')
def test_private_copy_refuses_live_owner(tmp_path):
    inputs = fixture(tmp_path, os.getpid())
    target = tmp_path / 'private'
    with pytest.raises(ValueError):
        private_storage.prepare_private_copy(*inputs, target)
    assert not target.exists()

@pytest.mark.skipif(os.name != 'nt', reason='使用原 Windows 文件租约')
def test_abandon_restores_old_marker_and_cannot_be_adopted(tmp_path):
    with subprocess.Popen([sys.executable, '-B', '-c', '']) as owner:
        assert owner.wait(timeout=5) == 0
        control, original, journal, allocation = fixture(tmp_path, owner.pid)
    private = tmp_path / 'private'
    reference = private_storage.prepare_private_copy(control, original, journal, allocation, private)
    marker = original / '.cta-clean.json'
    raw = marker.read_bytes()
    marker.rename(original / ('.cta-relocated-' + reference['sha256'] + '.json'))
    target = private / 'native'
    (target / marker.name).rename(target / '.cta-clean.consumed.json')
    args = dict(control=control, configuration_sha256='a'*64, output=original, journal=journal, allocation=allocation)
    with private_storage.native_output_lease(target):
        with pytest.raises(OSError):
            private_storage.abandon_private_copy(reference, **args)
    assert not marker.exists() and not (private / 'abandoned.json').exists()
    with private_storage.journal_owner_lease(private / 'qmt' / journal.name):
        with pytest.raises(OSError):
            private_storage.abandon_private_copy(reference, **args)
    assert not marker.exists() and not (private / 'abandoned.json').exists()
    with closing(sqlite3.connect(private / 'qmt' / journal.name)) as db, db:
        db.execute("UPDATE original SET state='advanced'")
    with pytest.raises(ValueError):
        private_storage.abandon_private_copy(reference, **args)
    assert not marker.exists() and not (private / 'abandoned.json').exists()
    (private / 'qmt' / journal.name).unlink()
    private_storage._backup(journal, private / 'qmt' / journal.name)
    assert private_storage.abandon_private_copy(reference, **args)['state'] == 'abandoned'
    assert marker.read_bytes() == raw
    assert private_storage.abandon_private_copy(reference, **args)['state'] == 'abandoned'
    with pytest.raises(ValueError):
        private_storage.verify_private_copy(reference, **args, target_output=target,
            target_journal=private/'qmt'/journal.name, target_allocation=private/'allocation'/allocation.name)
