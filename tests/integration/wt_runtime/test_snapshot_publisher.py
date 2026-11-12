"""展示快照共享冲突根因回归；真实Windows句柄、SDK替换与原Runtime入口，零QMT调用。"""
import errno
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'apps/wt_runtime'))
from guanheng_wt_runtime import __main__ as entry
from guanheng_wt_runtime.runtime_diagnostics import flush_process_logs
from guanheng_wt_runtime.snapshot_publisher import MAX_SNAPSHOT_BYTES, SnapshotPublisher


class BoundedRuntime:
    """每轮真实检查计数；正常stop沿原控制文件，状态读取与严格收据分开验证。"""
    def __init__(self, directory, identity):
        self.directory, self.identity = directory, identity
        self.closed = False
        self.reader = None
        self.checks = 0
        self.close_calls = []
        self.pending_counts = []

    def start(self, deadline):
        return True

    def status(self):
        return dict(schema='guanheng.wt-runtime-status.v1',
            state='closed' if self.closed else 'ready', ready=not self.closed,
            error_code=None, revision=self.checks, components={})

    def wait_close_request(self, seconds):
        target = self.directory / 'status.json'
        if self.reader is None and target.exists():
            self.reader = target.open('rb')
        return self.closed

    def check(self):
        self.checks += 1
        owned = [p for p in self.directory.iterdir() if p.name.startswith('.status.json.')]
        self.pending_counts.append(len(owned))
        if self.checks == 40:
            # 展示连续锁定40轮后仍接受正常身份的stop，不凭快照发布成功推进业务。
            (self.directory / 'stop.json').write_text(json.dumps(dict(
                schema='guanheng.wt-runtime-stop.v1', **self.identity)), encoding='ascii')
        return True

    def request_close(self):
        self.closed = True

    def close(self, seconds):
        self.close_calls.append(seconds)
        self.closed = True
        return True


@unittest.skipUnless(os.name == 'nt', '根因涉及Windows普通读句柄的共享删除规则')
class SnapshotPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / 'build')
        self.addCleanup(self.temporary.cleanup)
        # 测试直接调用入口，先等异步日志关闭句柄再清理Windows临时目录。
        self.addCleanup(lambda: self.assertTrue(flush_process_logs(5)))
        self.root = Path(self.temporary.name)

    def test_sustained_lock_has_one_candidate_then_unlock_publishes_latest(self):
        publisher = SnapshotPublisher(self.root, replace=entry.replace_status)
        self.assertTrue(publisher.publish({'revision': 0}))
        foreign = self.root / '.status.json.foreign'
        foreign.write_bytes(b'foreign owner bytes')
        pending_paths = set()
        reader = publisher.target.open('rb')
        try:
            for revision in range(1, 151):
                self.assertFalse(publisher.publish({'revision': revision, 'current': 'x' * 1024}))
                pending_paths.add(publisher.pending_file)
                self.assertEqual(json.loads(publisher.target.read_bytes()), {'revision': 0})
                self.assertLessEqual(publisher.pending_file.stat().st_size, MAX_SNAPSHOT_BYTES)
                self.assertEqual(len([p for p in self.root.iterdir()
                    if p.name.startswith('.status.json.') and p != foreign]), 1)
            self.assertEqual(len(pending_paths), 1)
            self.assertEqual(json.loads(publisher.pending_file.read_bytes())['revision'], 150)
            self.assertEqual(foreign.read_bytes(), b'foreign owner bytes')
        finally:
            reader.close()
        self.assertTrue(publisher.publish({'revision': 151}))
        self.assertEqual(json.loads(publisher.target.read_bytes()), {'revision': 151})
        self.assertIsNone(publisher.pending_file)
        self.assertEqual(set(self.root.iterdir()), {publisher.target, foreign})

    def test_only_proven_32_33_conflicts_are_deferred(self):
        for code in (32, 33, 5, 1117, None):
            with self.subTest(winerror=code):
                error = PermissionError(errno.EACCES, 'PRIVATE_PATH_AND_ACCOUNT')
                if code is not None:
                    error.winerror = code
                publisher = SnapshotPublisher(self.root, replace=lambda *unused: (_ for _ in ()).throw(error))
                if code in (32, 33):
                    self.assertFalse(publisher.publish({'revision': code}))
                else:
                    with self.assertRaises(PermissionError) as caught:
                        publisher.publish({'revision': code})
                    self.assertIs(caught.exception, error)

    def test_exclusive_candidate_collision_and_capacity_keep_other_files(self):
        candidate = self.root / '.status.json.synthetic-collision'
        candidate.write_bytes(b'other owner')
        with patch('guanheng_wt_runtime.snapshot_publisher.uuid4', return_value='synthetic-collision'):
            publisher = SnapshotPublisher(self.root, replace=entry.replace_status)
        with self.assertRaises(FileExistsError):
            publisher.publish({'revision': 1})
        self.assertEqual(candidate.read_bytes(), b'other owner')
        self.assertIsNone(publisher.pending_file)
        publisher = SnapshotPublisher(self.root, replace=entry.replace_status)
        with self.assertRaises(ValueError):
            publisher.publish({'oversize': 'x' * MAX_SNAPSHOT_BYTES})
        with self.assertRaises(ValueError):
            publisher.publish({'nonfinite': float('nan')})
        self.assertEqual(set(self.root.iterdir()), {candidate})

    def test_replaced_pending_candidate_does_not_overwrite_another_owner(self):
        error = PermissionError(errno.EACCES, 'synthetic sharing conflict')
        error.winerror = 32
        publisher = SnapshotPublisher(self.root, replace=lambda *unused: (_ for _ in ()).throw(error))
        self.assertFalse(publisher.publish({'revision': 1}))
        candidate = publisher.pending_file
        old = self.root / 'old-owner-candidate'
        candidate.rename(old)
        candidate.write_bytes(b'foreign owner')
        with self.assertRaises(ValueError):
            publisher.publish({'revision': 2})
        self.assertEqual(candidate.read_bytes(), b'foreign owner')
        self.assertEqual(json.loads(old.read_bytes()), {'revision': 1})

    def configuration(self):
        return SimpleNamespace(instance_id=str(uuid4()), startup_seconds=1, stop_seconds=2)

    def test_original_runtime_keeps_health_checks_and_normal_stop_under_lock(self):
        directory = self.root / 'run'
        config = self.configuration()
        control_id, sha = str(uuid4()), 'a' * 64
        identity = dict(control_id=control_id, instance_id=config.instance_id, configuration_sha256=sha)
        runtime = BoundedRuntime(directory, identity)
        try:
            with patch.object(entry, 'Runtime', return_value=runtime):
                self.assertEqual(entry.run(config, sha, directory, control_id), 0)
            self.assertEqual(runtime.checks, 40)
            self.assertEqual(set(runtime.pending_counts), {1})
            self.assertEqual(runtime.close_calls, [2])
            self.assertEqual(json.loads((directory / 'status.json').read_bytes())['revision'], 0)
            closed = json.loads((directory / 'closed.json').read_bytes())
            self.assertEqual(set(closed), {'schema', 'control_id', 'instance_id', 'pid',
                'configuration_sha256', 'components_closed', 'error_code', 'status'})
            self.assertTrue(closed['components_closed'])
            self.assertIsNone(closed['error_code'])
            self.assertFalse((directory / 'failure.json').exists())
            self.assertFalse((directory / 'diagnostic.json').exists())
            pending = [p for p in directory.iterdir() if p.name.startswith('.status.json.')]
            self.assertEqual(len(pending), 1)
            self.assertEqual(json.loads(pending[0].read_bytes())['state'], 'closed')
        finally:
            if runtime.reader is not None:
                runtime.reader.close()

    def test_nonsharing_io_still_fails_and_records_safe_phase_type_winerror(self):
        directory = self.root / 'io-failure'
        config = self.configuration()
        runtime = BoundedRuntime(directory, {})
        original, denied = entry.replace_status, []
        def deny_once(candidate, target):
            if target.exists() and not denied:
                denied.append(True)
                error = PermissionError(errno.EACCES, 'PRIVATE_ACCOUNT_AND_TOKEN')
                error.winerror = 5
                raise error
            return original(candidate, target)
        try:
            with patch.object(entry, 'Runtime', return_value=runtime), \
                    patch.object(entry, 'replace_status', side_effect=deny_once):
                self.assertEqual(entry.run(config, 'b' * 64, directory, str(uuid4())), 2)
            self.assertEqual(runtime.checks, 0)
            self.assertEqual(runtime.close_calls, [2])
            diagnostic = json.loads((directory / 'diagnostic.json').read_bytes())
            self.assertEqual(diagnostic['failure'], dict(phase='loop_status_publish',
                exception_type='PermissionError', errno=errno.EACCES, winerror=5))
            self.assertNotIn('PRIVATE', json.dumps(diagnostic))
            self.assertNotIn(str(directory), json.dumps(diagnostic))
            self.assertEqual(json.loads((directory / 'failure.json').read_bytes())['error_code'], 'runtime_failure')
        finally:
            if runtime.reader is not None:
                runtime.reader.close()

    def test_ready_control_receipt_conflict_remains_strict(self):
        directory = self.root / 'strict-control'
        runtime = BoundedRuntime(directory, {})
        original = entry._publish
        def deny_ready(directory, name, value, **kwargs):
            if name == 'ready.json':
                error = PermissionError(errno.EACCES, 'PRIVATE_READY_PATH')
                error.winerror = 32
                raise error
            return original(directory, name, value, **kwargs)
        with patch.object(entry, 'Runtime', return_value=runtime), \
                patch.object(entry, '_publish', side_effect=deny_ready):
            self.assertEqual(entry.run(self.configuration(), 'c' * 64, directory, str(uuid4())), 2)
        diagnostic = json.loads((directory / 'diagnostic.json').read_bytes())
        self.assertEqual(diagnostic['failure']['phase'], 'ready_publish')
        self.assertEqual(diagnostic['failure']['winerror'], 32)
        self.assertTrue((directory / 'failure.json').exists())
        self.assertFalse((directory / 'ready.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
