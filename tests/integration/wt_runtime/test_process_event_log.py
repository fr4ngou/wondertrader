"""受管输出在回收后丢失首错的回归；使用真实隐藏子进程，不启动QMT或交易。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'apps/wt_runtime'))
from guanheng_wt_runtime.managed_local_process import ManagedLocalProcess
from guanheng_wt_runtime.runtime_diagnostics import ProcessEventLog
from guanheng_wt_runtime import runtime_diagnostics


class ProcessLogTests(unittest.TestCase):
    def test_trade_reply_persists_only_fixed_diagnostic_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            log = ProcessEventLog(directory, 'run', 'trade-host-process')
            command = 'a' * 64
            log.feed(1, f'GH_TRADE_REPLY_INTERRUPTED call_expired unknown {command}\n'.encode())
            log.feed(1, f'GH_TRADE_REPLY_INTERRUPTED PRIVATE unknown {command}\n'.encode())
            log.feed(1, f'GH_TRADE_REPLY_INTERRUPTED binding_closed replied {command} PRIVATE\n'.encode())
            self.assertTrue(log.drain(5))
            events = [json.loads(line) for line in (Path(directory)/'process-events.jsonl').read_text().splitlines()]
            self.assertEqual(len(events), 1)
            entry = events[0]
            self.assertEqual((entry['event'], entry['rpc_error'], entry['delivery'], entry['command_sha256']),
                             ('trade_reply_interrupted', 'call_expired', 'unknown', command))

    def test_trade_diagnostic_frames_do_not_consume_the_ordinary_output_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            log = ProcessEventLog(directory, 'run', 'trade-host-process')
            line = f'GH_ACCOUNT_READ_FINISH commit_timeout {"b" * 64}\n'.encode()
            for _ in range(20):
                self.assertEqual(log.feed(1, line[:12]), 0)
                self.assertEqual(log.feed(1, line[12:]), 0)
            rejected = line.rstrip() + b' PRIVATE\n'
            self.assertEqual(log.feed(1, rejected), len(rejected))
            padded = b' ' * 1000 + line
            self.assertEqual(log.feed(1, padded), len(rejected) + len(padded))
            self.assertEqual(log.feed(1, line[:-1]), len(rejected) + len(padded))
            self.assertEqual(log.finish(1), len(rejected) + len(padded) + len(line) - 1)
            self.assertTrue(log.drain(5))

    def test_real_child_error_remains_after_original_buffers_cleared(self):
        with tempfile.TemporaryDirectory() as directory:
            owner = ManagedLocalProcess(SimpleNamespace(control_root=directory,
                startup_seconds=10, stop_seconds=10, max_output_bytes=1048576))
            marker = 'PRIVATE_TEST_VALUE'
            child = subprocess.Popen([sys.executable, '-I', '-B', '-c',
                'print("PRIVATE_TEST_VALUE");raise PermissionError(5,"PRIVATE_TEST_VALUE")'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=0x08000000 if os.name == 'nt' else 0)
            owner._job = SimpleNamespace(stdout=child.stdout, stderr=child.stderr)
            owner._start_readers()
            try:
                self.assertEqual(child.wait(timeout=15), 1)
                for thread in owner._readers:
                    self.assertTrue(thread.join_until(time.monotonic()+5))
            finally:
                child.stdout.close()
                child.stderr.close()
            owner._buffers = [bytearray(), bytearray()]
            self.assertTrue(owner._diagnostic.drain(5))
            raw = (Path(directory)/'process-events.jsonl').read_text(encoding='utf8')
            self.assertNotIn(marker, raw)
            events = [json.loads(line) for line in raw.splitlines()]
            self.assertTrue(any(e['event'] == 'stream_exception' and e['exception_type'] == 'PermissionError'
                                and e['errno'] == 5 for e in events))
            self.assertEqual(sum(e['event'] == 'stream_summary' for e in events), 2)
            self.assertEqual(owner._diagnostic.snapshot()['write_failures'], 0)

    def test_split_exception_and_known_frame_drop_private_text(self):
        with tempfile.TemporaryDirectory() as directory:
            log = ProcessEventLog(directory, 'run', 'test')
            for chunk in [b'  File "C:\\PRIVATE\\host.py", line 81, in run\nPermis',
                          b'sionError: [WinError 5] PRIVATE\nPRIVATE\n']:
                log.feed(1, chunk)
            log.finish(1)
            self.assertTrue(log.drain(5))
            raw = (Path(directory)/'process-events.jsonl').read_text(encoding='utf8')
            self.assertNotIn('PRIVATE', raw)
            event = json.loads(raw.splitlines()[0])
            self.assertEqual(event['winerror'], 5)
            self.assertEqual(event['frames'], [{'file': 'host.py', 'line': 81}])

    def test_rotation_bounds_all_generations(self):
        with tempfile.TemporaryDirectory() as directory:
            for generation in range(3):
                log = ProcessEventLog(directory, str(generation), 'test', max_bytes=4096, backups=2)
                for _ in range(45):
                    log.event('process_ready')
                self.assertTrue(log.drain(5))
                self.assertEqual(log.snapshot()['write_failures'], 0)
            files = list(Path(directory).glob('process-events.jsonl*'))
            self.assertLessEqual(len(files), 3)
            self.assertLessEqual(sum(p.stat().st_size for p in files), 3*4096)
            for path in files:
                for line in path.read_text(encoding='utf8').splitlines():
                    self.assertEqual(json.loads(line)['schema'], 'guanheng.process-event.v1')

    def test_oversized_line_and_custom_exception_never_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            log = ProcessEventLog(directory, 'run', 'test')
            for _ in range(8):
                log.feed(1, b'PRIVATE'*1024)
            log.feed(1, b'ValueError: PRIVATE\nValueError: PRIVATE\n')
            custom = type('PRIVATE', (Exception,), {})
            log.event('process_failure', error=custom('PRIVATE'))
            log.finish(1)
            self.assertTrue(log.drain(5))
            raw = (Path(directory)/'process-events.jsonl').read_text(encoding='utf8')
            self.assertNotIn('PRIVATE', raw)
            self.assertEqual(raw.count('stream_exception'), 1)
            self.assertLessEqual(len(log._pending[1]), 8192)

    def test_log_io_failure_does_not_replace_original_process_result(self):
        with tempfile.TemporaryDirectory() as directory:
            log = ProcessEventLog(Path(directory)/'missing', 'run', 'test')
            log.event('process_failure', code='host_exit', error=ValueError('PRIVATE'))
            self.assertTrue(log.drain(5))
            self.assertEqual(log.snapshot()['records_written'], 0)
            self.assertEqual(log.snapshot()['write_failures'], 1)

    def test_slow_disk_preserves_stop_deadline_and_pipe_drain_with_bounded_queue(self):
        # 原反例：fsync卡住时，_failure尚未发布停止；现在监督和reader只做有界内存提交。
        import io
        with tempfile.TemporaryDirectory() as directory:
            owner = ManagedLocalProcess(SimpleNamespace(control_root=directory,
                startup_seconds=10, stop_seconds=10, max_output_bytes=32))
            entered, release = threading.Event(), threading.Event()
            original = runtime_diagnostics.os.fsync
            def slow(fd):
                entered.set()
                if not release.wait(5):
                    raise TimeoutError('test disk gate')
                original(fd)
            with patch.object(runtime_diagnostics.os, 'fsync', slow):
                try:
                    owner._diagnostic.event('process_started')
                    self.assertTrue(entered.wait(2))
                    before = time.monotonic()
                    owner._failure('host_exit')
                    deadline = owner._stop_deadline
                    self.assertTrue(owner._stop.is_set())
                    self.assertTrue(owner._ready.is_set())
                    owner._reader(1, io.BytesIO(b'ValueError: PRIVATE\n' + b'x'*100))
                    self.assertTrue(owner._eof[1])
                    self.assertEqual(owner._stop_deadline, deadline)
                    self.assertEqual(owner.status()['error_code'], 'host_exit')
                    for _ in range(300):
                        owner._diagnostic.event('process_ready')
                    status = owner._diagnostic.snapshot()
                    self.assertLess(time.monotonic()-before, 1)
                    self.assertLessEqual(status['records_pending'], 257)
                    self.assertGreater(status['records_dropped'], 0)
                finally:
                    release.set()
                self.assertTrue(owner._diagnostic.drain(8))
            self.assertEqual(owner._diagnostic.snapshot()['write_failures'], 0)

    def test_overlapping_processes_share_rotation_budget(self):
        # 真正两个Windows进程竞争同一系列，不能用本对象/本进程锁冒充跨进程保护。
        with tempfile.TemporaryDirectory() as directory:
            code = '''import json,sys,time
sys.path.insert(0,sys.argv[2])
from guanheng_wt_runtime.runtime_diagnostics import ProcessEventLog
log=ProcessEventLog(sys.argv[1],sys.argv[3],'test',max_bytes=4096,backups=1)
for index in range(120):
    log.event('process_ready')
    time.sleep(.001)
assert log.drain(10)
print(json.dumps(log.snapshot()))
'''
            children = [subprocess.Popen([sys.executable, '-I', '-B', '-c', code, directory,
                str(ROOT/'apps/wt_runtime'), str(index)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=0x08000000 if os.name == 'nt' else 0) for index in range(2)]
            for child in children:
                output, error = child.communicate(timeout=20)
                self.assertEqual(child.returncode, 0, error.decode('utf8', errors='replace'))
                status = json.loads(output)
                self.assertGreater(status['records_written'], 0)
                self.assertEqual(status['records_written'] + status['write_failures'], 120)
                self.assertEqual(status['records_pending'], 0)
            files = list(Path(directory).glob('process-events.jsonl*'))
            self.assertLessEqual(sum(p.stat().st_size for p in files), 8192)
            self.assertTrue(all(p.stat().st_size <= 4096 for p in files))
            self.assertEqual((Path(directory)/'process-events.lock').stat().st_size, 1)
            for path in files:
                for line in path.read_text(encoding='utf8').splitlines():
                    self.assertEqual(json.loads(line)['event'], 'process_ready')


if __name__ == '__main__':
    unittest.main()
