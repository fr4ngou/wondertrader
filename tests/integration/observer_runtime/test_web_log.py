"""独立Web日志的容量与故障回归；真实隐藏HTTP主链由隔离验真另外记录。"""
import contextlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == 'win32', 'Windows Web maintenance entry')
class WebLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[3] / 'scripts/runtime_templates/observer-web.py'
        spec = importlib.util.spec_from_file_location('observer_web_log_tests', path)
        cls.owner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.owner)

    def series(self, root):
        return [p for p in root.glob('web.log*') if p.is_file()]

    def status(self, root):
        return json.loads((root / 'web-log-status.json').read_bytes())

    def test_existing_text_and_both_redirects_restore_after_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'web.log').write_text('原日志\n', encoding='utf8')
            stdout, stderr = sys.stdout, sys.stderr
            with self.assertRaisesRegex(RuntimeError, 'synthetic'):
                with self.owner.WebLog(root / 'web.log') as log:
                    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                        print('新stdout')
                        print('新stderr', file=sys.stderr)
                        raise RuntimeError('synthetic')
            self.assertIs(sys.stdout, stdout)
            self.assertIs(sys.stderr, stderr)
            self.assertEqual((root / 'web.log').read_text(encoding='utf8'), '原日志\n新stdout\n新stderr\n')
            self.assertTrue(self.status(root)['closed'])
            self.assertEqual(self.status(root)['state'], 'ok')
            log.close()
            with self.assertRaises(ValueError):
                log.write('关闭后写入')

    def test_one_large_unterminated_unicode_write_respects_total_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = ('中🙂\ud800\n' * 5000) + '保留尾部'
            with self.owner.WebLog(root / 'web.log', maximum=128, backups=2) as log:
                self.assertEqual(log.write(text), len(text))
                log.flush()
            files = self.series(root)
            self.assertEqual(len(files), 3)
            self.assertLessEqual(sum(p.stat().st_size for p in files), 384)
            for path in files:
                self.assertLessEqual(path.stat().st_size, 128)
                path.read_bytes().decode('utf8')
            self.assertTrue((root / 'web.log').read_text(encoding='utf8').endswith('保留尾部'))
            self.assertEqual(self.status(root)['written_bytes'], len(text.encode('utf8', 'backslashreplace')))

    def test_oversized_existing_series_retains_readable_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('web.log', 'web.log.1', 'web.log.2'):
                (root / name).write_bytes(('旧🙂' * 1000 + '最新尾部').encode('utf8'))
            unrelated = root / 'other.log'
            unrelated.write_bytes(b'keep original')
            with self.owner.WebLog(root / 'web.log', maximum=128, backups=2):
                pass
            for path in self.series(root):
                self.assertLessEqual(path.stat().st_size, 128)
                self.assertTrue(path.read_bytes().decode('utf8').endswith('最新尾部'))
            self.assertEqual(unrelated.read_bytes(), b'keep original')

    def test_real_file_open_error_reports_once_and_drops_without_buffering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'web.log').mkdir()  # 实际文件路径不可打开，避免依赖管理员ACL或填满磁盘。
            with self.owner.WebLog(root / 'web.log') as log:
                self.assertEqual(log.write('第一次失败'), 5)
                live = self.status(root)
                self.assertEqual(live['state'], 'degraded')
                self.assertEqual(live['dropped_characters'], 5)
                self.assertFalse(live['closed'])
                with patch.object(log.handler, 'emit', side_effect=AssertionError('must remain disabled')):
                    log.write('后续丢弃')
            status = self.status(root)
            self.assertEqual(status['write_failures'], 1)
            self.assertEqual(status['dropped_characters'], 9)
            self.assertTrue(status['closed'])

    def test_rotation_failure_keeps_web_caller_running(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.owner.WebLog(root / 'web.log', maximum=64, backups=1) as log:
                log.write('a' * 60)
                with patch.object(self.owner.os, 'rename', side_effect=OSError('synthetic rename failure')):
                    log.write('remaining')
                self.assertEqual(log.error_type, 'OSError')
            self.assertEqual((root / 'web.log').read_bytes(), b'a' * 60)
            self.assertEqual(self.status(root)['dropped_characters'], 9)

    def test_flush_failure_and_unwritable_status_do_not_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.owner.WebLog(root / 'web.log') as log:
                log.write('confirmed')
                with patch.object(log.handler, 'flush', side_effect=OSError('synthetic full disk')):
                    with patch.object(self.owner.os, 'replace', side_effect=OSError('synthetic status failure')):
                        log.flush()
                        self.assertEqual(log.error_type, 'OSError')
            self.assertEqual(self.status(root)['state'], 'degraded')
            self.assertFalse((root / 'web-log-status.tmp').exists())

    def test_two_original_streams_share_rotation_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.owner.WebLog(root / 'web.log', maximum=128, backups=2) as log:
                workers = [threading.Thread(target=lambda: [log.write('并发🙂' * 8) for _ in range(30)])
                           for _ in range(2)]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join()
            self.assertEqual(self.status(root)['write_failures'], 0)
            self.assertLessEqual(sum(p.stat().st_size for p in self.series(root)), 384)
            for path in self.series(root):
                path.read_bytes().decode('utf8')


if __name__ == '__main__':
    unittest.main()
