"""原Host管理器到控制收据的首故障回归；只用内存owner和私有目录替身。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import PropertyMock, patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'connectors/qmt_shm/host'), str(ROOT / 'connectors/qmt_shm/agent'),
               str(Path(__file__).resolve().parent)]

from guanheng_qmt_shm import paired_control as control
from guanheng_qmt_shm.read_service import ReconnectingReadService
from test_host_service import CONFIG, CREDS, PROFILE, Factory


class DiagnosticServer:
    """真实管理器负责原代创建/退休；HTTP监听由同线程替身替代，不建网络或进程。"""
    def __init__(self, service, factory, directory, reason):
        self.service, self.factory, self.directory, self.reason = service, factory, directory, reason
        self.started = self.should_exit = False
        self.close_calls = 0

    def run(self):
        self.service.start()
        self.started = True
        triggered = False
        end = time.monotonic() + 2
        while not self.should_exit:
            if not triggered and (self.directory / 'ready.json').exists():
                # 原触发窗口：服务已ready，单代owner自行失败，原monitor负责映射与停止。
                self.factory.runtimes[0].end(self.reason)
                triggered = True
            if time.monotonic() >= end:
                raise AssertionError('synthetic control did not stop')
            time.sleep(.001)

    def request_close(self):
        original = self.service.begin_shutdown()
        self.service.request_close()
        self.should_exit = True
        return original

    def close(self):
        self.close_calls += 1
        self.service.close(self.request_close())


class HostFailureDiagnosticTests(unittest.TestCase):
    def run_failure(self, reason='ProtocolError', close_error=None, diagnostic_writer=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name) / 'control'
        factory = Factory()
        if close_error is not None:
            factory.options.append({'close_error': close_error})
        service = ReconnectingReadService(factory, configuration=copy.deepcopy(CONFIG),
            credentials=copy.deepcopy(CREDS), profile=copy.deepcopy(PROFILE),
            reconnect_seconds=.005, poll_seconds=.002)
        server = DiagnosticServer(service, factory, directory, reason)
        writes = []

        def mkdir(path):
            Path(path).mkdir()
            return Path(path)

        def write(path, raw):
            writes.append((Path(path).name, bytes(raw)))
            if Path(path).name.startswith('failure-diagnostic.') and diagnostic_writer is not None:
                return diagnostic_writer(path, raw)
            with Path(path).open('xb') as stream:
                stream.write(raw)

        identity = dict(pair_manifest_sha256='a' * 64, pair_config_sha256='b' * 64)
        try:
            with patch.object(control, 'create_server', return_value=server), \
                    patch.object(control, 'create_private_directory', side_effect=mkdir), \
                    patch.object(control, 'write_private_new', side_effect=write):
                with self.assertRaises(control.PairedControlError) as caught:
                    control._serve_factory(lambda: (service, {}, identity),
                        control_directory=directory, control_id=str(uuid4()))
        finally:
            # 故意保留的失败owner只在测试结束后去登记；管理/monitor线程必须真实退出。
            service._thread.join(2)
            self.assertFalse(service._thread.is_alive())
            for owner in list(control._PENDING):
                if owner.runtime is service:
                    owner.done.set()
                    owner.monitor.join(2)
                    self.assertFalse(owner.monitor.is_alive())
                    control._PENDING.discard(owner)
        return directory, service, factory, server, caught.exception, writes

    def diagnostic(self, directory):
        path = directory / 'failure-diagnostic.json'
        raw = path.read_bytes()
        self.assertLessEqual(len(raw), 4096)
        self.assertNotIn(b'PRIVATE', raw)
        value = json.loads(raw)
        self.assertEqual(value['schema'], 'qmt.host-failure-diagnostic.v1')
        self.assertEqual(set(value), {'schema', 'control_id', 'pid', 'pair_manifest_sha256',
            'pair_config_sha256', 'first_failure', 'retirement', 'cleanup_reason'})
        return value

    def test_actual_runtime_failure_survives_control_mapping_and_close(self):
        directory, service, factory, server, failure, writes = self.run_failure()
        value = self.diagnostic(directory)
        self.assertEqual(value['first_failure']['reason'], 'runtime_authentication_or_protocol')
        self.assertEqual(value['first_failure']['runtime_failure'], 'ProtocolError')
        self.assertEqual(value['first_failure']['generation'], 1)
        self.assertIsNone(value['retirement'])
        self.assertEqual(failure.error_code, 'runtime_failed')
        self.assertEqual(failure.result['status'], 'failed')
        self.assertTrue(failure.result['runtime_closed'])
        self.assertEqual((len(factory.runtimes), factory.runtimes[0].close_calls, server.close_calls), (1, 1, 1))
        ready = json.loads((directory / 'ready.json').read_bytes())
        closed = json.loads((directory / 'closed.json').read_bytes())
        self.assertEqual(set(ready), {'schema', 'control_id', 'pid', 'pair_manifest_sha256',
            'pair_config_sha256', 'listen_host', 'listen_port'})
        self.assertEqual(set(closed), {'schema', 'control_id', 'pid', 'pair_manifest_sha256',
            'pair_config_sha256', 'status', 'runtime_closed', 'monitor_joined', 'error_code'})
        self.assertEqual(value['control_id'], ready['control_id'])
        self.assertEqual([name for name, raw in writes[:2]], ['ready.json', 'closed.json'])

    def test_retirement_exception_keeps_first_runtime_failure_and_original_owner(self):
        directory, service, factory, server, failure, writes = self.run_failure(
            close_error=OSError('SYNTHETIC_PRIVATE_PATH_AND_ACCOUNT'))
        value = self.diagnostic(directory)
        self.assertEqual(value['first_failure']['reason'], 'runtime_authentication_or_protocol')
        self.assertIsNone(value['first_failure']['cleanup_reason'])
        self.assertEqual(value['cleanup_reason'], 'retirement_unconfirmed')
        self.assertEqual(value['retirement']['exception_type'], 'OSError')
        self.assertEqual(value['retirement']['step'], 'runtime_close')
        self.assertIs(type(value['retirement']['remaining_budget_ms']), int)
        self.assertEqual(failure.error_code, 'runtime_failed')
        self.assertFalse(failure.result['runtime_closed'])
        self.assertIs(service._runtime, factory.runtimes[0])
        self.assertEqual(factory.runtimes[0].close_calls, 1)
        self.assertEqual(len(factory.runtimes[0].close_deadlines), 1)
        original = service.failure_diagnostic_snapshot
        service._fault('runtime_journal')
        self.assertEqual(service.failure_diagnostic_snapshot, original)
        original['first_failure']['reason'] = 'mutated_copy'
        self.assertEqual(service.failure_diagnostic_snapshot['first_failure']['reason'],
                         'runtime_authentication_or_protocol')

    def test_retryable_transport_with_failed_retirement_records_both_layers(self):
        directory, service, factory, server, failure, writes = self.run_failure(
            reason='TimeoutError', close_error=RuntimeError('SYNTHETIC_PRIVATE_TEXT'))
        value = self.diagnostic(directory)
        self.assertEqual(value['first_failure']['reason'], 'retirement_unconfirmed')
        self.assertEqual(value['first_failure']['runtime_failure'], 'TimeoutError')
        self.assertEqual(value['retirement']['exception_type'], 'RuntimeError')
        self.assertEqual(value['retirement']['step'], 'runtime_close')
        self.assertEqual(len(factory.runtimes), 1)
        self.assertFalse(failure.result['runtime_closed'])

    def test_unknown_runtime_or_exception_values_are_never_serialized(self):
        class PrivateException(Exception):
            pass
        directory, service, factory, server, failure, writes = self.run_failure(
            reason='SYNTHETIC_PRIVATE_ACCOUNT', close_error=PrivateException('SYNTHETIC_PRIVATE_SECRET'))
        value = self.diagnostic(directory)
        self.assertEqual(value['first_failure']['runtime_failure'], 'other')
        self.assertEqual(value['retirement']['exception_type'], 'other')
        self.assertNotIn('PrivateException', json.dumps(value))

    def test_late_failed_diagnostic_cannot_change_already_confirmed_close_result(self):
        def fail_write(path, raw):
            # 故障诊断I/O即使越过原D并失败，原closed和返回结果已经确定，禁止再次改判。
            with patch.object(control.time, 'monotonic', return_value=time.monotonic() + 60):
                raise OSError('SYNTHETIC_PRIVATE_WRITE_FAILURE')
        directory, service, factory, server, failure, writes = self.run_failure(diagnostic_writer=fail_write)
        self.assertFalse((directory / 'failure-diagnostic.json').exists())
        self.assertEqual(failure.error_code, 'runtime_failed')
        self.assertEqual(failure.result['status'], 'failed')
        self.assertTrue(failure.result['runtime_closed'] and failure.result['monitor_joined'])
        self.assertEqual(json.loads((directory / 'closed.json').read_bytes())['status'], 'failed')
        self.assertEqual(factory.runtimes[0].close_calls, 1)

    def test_snapshot_failure_preserves_original_error_and_cleanup(self):
        with patch.object(ReconnectingReadService, 'failure_diagnostic_snapshot',
                new_callable=PropertyMock, side_effect=OSError('SYNTHETIC_PRIVATE_SNAPSHOT')):
            directory, service, factory, server, failure, writes = self.run_failure()
        self.assertFalse((directory / 'failure-diagnostic.json').exists())
        self.assertEqual(failure.error_code, 'runtime_failed')
        self.assertTrue(failure.result['runtime_closed'] and failure.result['monitor_joined'])
        self.assertEqual((factory.runtimes[0].close_calls, server.close_calls), (1, 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
