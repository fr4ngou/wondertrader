"""原生分析超期后沿原 Job 收口，再开始独立观察。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from guanheng_analysis_window_producer import pipeline, runtime


class NativeDeadlineRecovery(unittest.TestCase):
    def test_native_entry_classifies_only_the_child_tool_deadline(self):
        with patch.object(sys, 'argv', ['pipeline', '--native-request', 'unused.json']), \
                patch.object(pipeline, 'load', return_value={}), \
                patch.object(pipeline, 'native_pipeline', side_effect=subprocess.TimeoutExpired('fixture', 60)):
            self.assertEqual(pipeline.main(), pipeline.NATIVE_TOOL_TIMEOUT)
        with patch.object(sys, 'argv', ['pipeline', '--native-request', 'unused.json']), \
                patch.object(pipeline, 'load', return_value={}), \
                patch.object(pipeline, 'native_pipeline', side_effect=ValueError('invalid native output')):
            with self.assertRaises(ValueError):
                pipeline.main()

    def test_deadline_logs_original_capture_and_reaps_before_next_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            owner = runtime.AnalysisWindowProducer.__new__(runtime.AnalysisWindowProducer)
            owner.directory = Path(folder)
            owner.publication = owner.directory / 'window.json'
            owner.publication.write_bytes(b'previous published window')
            owner._resume_attempt = owner._runner = owner._deadline = None
            owner._lock, owner._stop, owner._wake = threading.RLock(), threading.Event(), threading.Event()
            owner._lease_acquired = True
            owner._state = dict(phase='waiting_source', error=None, current_capture_id=None, published_count=1)
            owner.refresh_seconds, owner.interval, owner.max_age = 1, 0, 60
            owner.start_date, owner.max_rows, owner.artifacts = '2026-01-01', 10, {}
            owner.python, owner.worker_cwd = 'fixture', 'fixture'
            sequence, captures = [], []
            snapshot = owner.directory / 'source.json'
            snapshot.write_text('{}', encoding='utf8')

            class Provider:
                def capture(self, request, directory, *, deadline):
                    captures.append(request['capture_id'])
                    sequence.append('capture')
                    if len(captures) == 2:
                        owner._stop.set()
                        raise runtime.SourcePending('analysis_refresh_interrupted')
                    return snapshot

            class Runner:
                receipt = {'resources_closed': False, 'exit_code': None}

                def run(self, *args, **kwargs):
                    sequence.append('timeout')
                    raise runtime.NativeRefreshDeadline('analysis_native_refresh_deadline')

                def reap(self, deadline):
                    sequence.append('reap')
                    return sequence.count('reap') == 2

            owner.provider = Provider()
            with patch.object(runtime, 'NativeRefreshJob', return_value=Runner()), \
                    patch.object(runtime, 'validate_snapshot', return_value={}), \
                    self.assertLogs(runtime.__name__, level='ERROR'):
                owner._run()

            self.assertEqual(sequence, ['capture', 'timeout', 'reap', 'reap', 'capture'])
            self.assertNotEqual(*captures)
            failure = next(owner.directory.glob('r-*/ERROR-analysis_native_refresh_deadline.json'))
            saved = json.loads(failure.read_bytes())
            self.assertEqual((saved['phase'], saved['capture_id'], saved['action'], saved['native_resources_closed']),
                             ('native_refresh', captures[0], 'reap_then_retry', False))
            self.assertEqual(owner.publication.read_bytes(), b'previous published window')
