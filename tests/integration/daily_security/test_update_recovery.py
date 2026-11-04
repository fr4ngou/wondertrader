"""同任务的未提交目录、发布租约和09:00窗口；不访问来源或调用原生导入。"""
from datetime import datetime
import hashlib
from pathlib import Path
import tempfile
import time
import uuid
import unittest
from unittest.mock import patch

from integrations.guanheng.daily_data_stages import prepare_directory
from integrations.guanheng import daily_data_update as update
from integrations.guanheng.daily_data_service import target_date, serve
from integrations.guanheng.market_generation import GenerationPublisher, encode
from guanheng_app.observation.refresh_models import source_window


class RecoveryTests(unittest.TestCase):
    def test_partial_outputs_of_each_stage_are_preserved_and_replaced_by_new_attempt(self):
        for name, marker in [('facts', 'catalog.json'), ('gap-plan', 'PLAN.json'), ('snapshot', 'PREPARED.json')]:
            with self.subTest(stage=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                outputs = []

                def interrupted(output):
                    output.mkdir()
                    (output / 'partial').write_bytes(b'partial-owned-output')
                    outputs.append(output)
                    raise InterruptedError('before completion marker')

                def restore(output):
                    body = (output / marker).read_bytes()
                    return dict(path=str(output / marker), sha256=hashlib.sha256(body).hexdigest())

                def complete(output):
                    output.mkdir()
                    (output / marker).write_bytes(encode(dict(test_fixture=True)))
                    outputs.append(output)
                    return restore(output)

                with self.assertRaises(InterruptedError):
                    prepare_directory(root, name, marker, interrupted, restore)
                result = prepare_directory(root, name, marker, complete, restore)
                self.assertNotEqual(outputs[0], outputs[1])
                self.assertEqual((outputs[0] / 'partial').read_bytes(), b'partial-owned-output')
                self.assertEqual(prepare_directory(root, name, marker, complete, restore), result)
                self.assertEqual(len(outputs), 2)

    def test_completed_output_is_adopted_after_crash_before_phase_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []

            def restore(output):
                body = (output / 'PLAN.json').read_bytes()
                return dict(path=str(output / 'PLAN.json'), sha256=hashlib.sha256(body).hexdigest())

            def complete(output):
                output.mkdir()
                calls.append(output)
                (output / 'PLAN.json').write_bytes(b'completed-test-plan')
                return restore(output)

            save = update._save

            def interrupted_save(path, value):
                if path.name == 'PHASE-gap-plan.json' and value['result'] is not None:
                    raise InterruptedError('after marker, before phase commit')
                save(path, value)

            with patch.object(update, '_save', interrupted_save), self.assertRaises(InterruptedError):
                prepare_directory(root, 'gap-plan', 'PLAN.json', complete, restore)
            result = prepare_directory(root, 'gap-plan', 'PLAN.json', complete, restore)
            self.assertEqual(len(calls), 1)
            self.assertEqual(Path(result['path']).parent, calls[0])
            Path(result['path']).write_bytes(b'changed-committed-plan')
            with self.assertRaisesRegex(ValueError, 'committed output differs'):
                prepare_directory(root, 'gap-plan', 'PLAN.json', complete, restore)

    def test_lock_rejection_does_not_write_task_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fields = ('cache universe daily_facts security_reference calendar base_configuration basic_capture '
                      'helper previous_stores previous_archives protected_slots authorized_from authorized_to additional_archives')
            request = {name: None for name in fields.split()}
            request.update(schema='guanheng.daily-data-update.v1', publication_directory=str(root / 'publication'))
            with GenerationPublisher(request['publication_directory']):
                with self.assertRaises(OSError):
                    update.run_update(request, root / 'work', deadline=time.monotonic() + 5)
            self.assertFalse((root / 'work').exists())

    def test_daily_window_keeps_yesterday_after_close(self):
        rows = [dict(date=day, is_open=1) for day in ('2026-11-02', '2026-11-03', '2026-11-04')]
        calendar = dict(coverage_start='2026-01-01', coverage_end='2026-12-31')
        with patch('guanheng_app.observation.calendars.official_calendar', return_value=(rows, None)):
            morning = target_date(calendar, datetime.fromisoformat('2026-11-04T09:00:00+08:00'))
            afternoon = target_date(calendar, datetime.fromisoformat('2026-11-04T16:00:00+08:00'))
            next_day = target_date(calendar, datetime.fromisoformat('2026-11-05T09:00:00+08:00'))
        self.assertEqual(morning, '2026-11-03')
        self.assertEqual(afternoon, morning)
        self.assertEqual(next_day, '2026-11-04')

    def test_service_lock_rejection_does_not_reserve_shared_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = dict(schema='guanheng.daily-data-service.v1', directory=str(root / 'state'),
                raw_store=str(root / 'raw'), template=dict(schema='guanheng.daily-data-update.v1',
                    publication_directory=str(root / 'publication')),
                inputs=dict(connections=dict(batch={}, hpr={}), cache_from='20260701', max_rows=100,
                    source_kind='actual-qmt', public_facts=dict(source={}, allowed_hosts=[], seconds=30,
                        max_requests=1, max_bytes=1, response_bytes=1, timeout_seconds=1)),
                schedule=dict(timezone='Asia/Shanghai', at='09:00', poll_seconds=.1),
                cycle_seconds=60, retry_seconds=1)
            path = root / 'config.json'
            path.write_bytes(encode(config))
            descriptor = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            control_id = str(uuid.uuid4())
            with GenerationPublisher(config['template']['publication_directory']):
                with self.assertRaises(OSError):
                    serve(descriptor, root / control_id, control_id, once=True, as_of='2026-11-03')
            self.assertFalse((root / 'state').exists())
            self.assertTrue((root / control_id / 'failure.json').exists())

    def test_t2108_backlog_selects_current_snapshot_without_losing_old_source_window_policy(self):
        budget = dict(max_days_per_batch=93)
        current = source_window('2026-03-01', '2026-11-03', dict(kind='wt_t2108', overlap_days=0), budget)
        historical = source_window('2026-03-01', '2026-11-03', dict(kind='wt_breadth', overlap_days=0), budget)
        self.assertEqual(current, ('2026-03-01', '2026-11-03'))
        self.assertEqual(historical, ('2026-03-01', '2026-06-01'))


if __name__ == '__main__':
    unittest.main()
