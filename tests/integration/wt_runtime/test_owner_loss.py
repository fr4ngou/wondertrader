"""复现已发布的 WT 进程内分析窗口状态缺少独立 PID。"""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import call, patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'apps/wt_runtime'))
from guanheng_wt_runtime import __main__ as cli, execution_recovery


class OwnerLossTests(unittest.TestCase):
    def setUp(self):
        self.control_id = str(uuid4())
        self.identity = dict(control_id=self.control_id, instance_id=str(uuid4()),
                             configuration_sha256='a' * 64, pid=1001)
        self.components = {
            'analysis_host': {'pid': 1002},
            'analysis_window': {'schema': 'guanheng.analysis-window-process-status.v1'},
        }
        self.config = SimpleNamespace(instance_id=self.identity['instance_id'], components=(
            ('analysis_host', SimpleNamespace(kind='qmt_read')),
            ('analysis_window', SimpleNamespace(kind='analysis_window')),
        ))
        temporary = tempfile.TemporaryDirectory(dir=ROOT / 'build')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / self.control_id
        self.directory.mkdir()
        cli._publish(self.directory, 'ready.json',
                     dict(self.identity, schema='guanheng.wt-runtime-ready.v1'))

    def record_loss(self):
        return cli.record_process_loss(self.config, self.identity['configuration_sha256'],
                                       self.directory, self.control_id)

    def write_status(self):
        cli._publish(self.directory, 'status.json',
                     dict(self.identity, schema='guanheng.wt-runtime-status.v1',
                          state='ready', ready=True, components=self.components))

    def test_runtime_owned_window_uses_verified_runtime_pid_on_retry(self):
        self.write_status()
        with patch.object(execution_recovery, 'require_process_exited') as check:
            self.assertEqual(self.record_loss(), 0)
            self.assertEqual(self.record_loss(), 0)
        self.assertEqual(check.call_args_list, [call(1001), call(1002)] * 2)
        loss = json.loads((self.directory / 'owner-loss.json').read_bytes())
        self.assertEqual(loss['component_pids'], {'analysis_host': 1002, 'analysis_window': 1001})
        failure = json.loads((self.directory / 'failure.json').read_bytes())
        self.assertIs(failure['components_closed'], False)
        self.assertFalse((self.directory / 'closed.json').exists())

    def test_missing_external_pid_and_unexpected_window_pid_fail_closed(self):
        for component, field, value in (('analysis_host', 'pid', None),
                                         ('analysis_window', 'pid', 1003),
                                         ('analysis_window', 'pid', 1001.0),
                                         ('analysis_window', 'schema', 'unknown')):
            with self.subTest(component=component, field=field, value=value):
                original = self.components[component].copy()
                self.components[component][field] = value
                self.write_status()
                with patch.object(execution_recovery, 'require_process_exited',
                                  side_effect=lambda pid: cli._require(type(pid) is int)):
                    with self.assertRaises(ValueError):
                        self.record_loss()
                self.assertFalse((self.directory / 'owner-loss.json').exists())
                (self.directory / 'status.json').unlink()
                self.components[component] = original
