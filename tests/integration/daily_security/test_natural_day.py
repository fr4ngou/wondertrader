"""同一日线owner按实际日历跨闭合窗口；所有来源用无副作用替身。"""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from integrations.guanheng import daily_data_service as service
from integrations.guanheng.market_generation import encode
from guanheng_app.observation.ashare_public import Archive


class NaturalDayTests(unittest.TestCase):
    def test_source_and_owner_share_same_close_boundary(self):
        end = datetime.fromisoformat('2026-11-04').date()
        dates = [(end-timedelta(days=offset)).isoformat() for offset in reversed(range(46))]
        rows = [dict(date=day, is_open=int(day in ('2026-11-03', '2026-11-04'))) for day in dates]
        table = dict(fields=['calendar_date', 'is_trading_day'],
                     rows=[[row['date'], str(row['is_open'])] for row in rows])
        archive = object.__new__(Archive)
        archive.receipts = lambda *args, **kwargs: [dict(calendar_sha256='saved-calendar-fixture')]
        archive.restore_records = lambda receipt: None
        archive.fetch = SimpleNamespace(objects=SimpleNamespace(get=lambda identity: encode(table)),
                                        budget=SimpleNamespace(remaining=lambda: None))
        calendar = dict(coverage_start=dates[0], coverage_end=dates[-1])
        with patch('guanheng_app.observation.calendars.official_calendar', return_value=(rows, None)):
            for stamp, expected in [('2026-11-04T15:29:59+08:00', '2026-11-03'),
                                    ('2026-11-04T15:30:00+08:00', '2026-11-04')]:
                archive.now = datetime.fromisoformat(stamp)
                self.assertEqual(archive.closed_day(end.isoformat()), expected)
                self.assertEqual(service.target_date(calendar, archive.now), expected)

    def test_boundary_timezone_weekend_and_holiday(self):
        rows = [dict(date=day, is_open=1) for day in
                ('2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06', '2026-11-09')]
        calendar = dict(coverage_start='2026-01-01', coverage_end='2026-12-31')
        cases = {
            '2026-11-04T09:00:00+08:00': '2026-11-03',
            '2026-11-04T15:29:59.999999+08:00': '2026-11-03',
            '2026-11-04T15:30:00+08:00': '2026-11-04',
            '2026-11-04T07:30:00+00:00': '2026-11-04',
            '2026-11-05T00:00:00+08:00': '2026-11-04',
            '2026-11-07T16:00:00+08:00': '2026-11-06',
            '2026-11-09T09:00:00+08:00': '2026-11-06',
            '2026-11-10T16:00:00+08:00': '2026-11-09',
        }
        with patch('guanheng_app.observation.calendars.official_calendar', return_value=(rows, None)):
            for stamp, expected in cases.items():
                with self.subTest(stamp=stamp):
                    self.assertEqual(service.target_date(calendar, datetime.fromisoformat(stamp)), expected)

    def test_unknown_calendar_coverage_and_naive_clock_are_rejected(self):
        calendar = dict(coverage_start='2026-11-01', coverage_end='2026-11-04')
        rows = [dict(date='2026-11-04', is_open=1)]
        with patch('guanheng_app.observation.calendars.official_calendar', return_value=(rows, None)):
            for stamp in ('2026-11-04T16:00:00', '2026-11-05T16:00:00+08:00'):
                with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                    service.target_date(calendar, datetime.fromisoformat(stamp))

    def test_one_owner_crosses_close_and_restart_reuses_completed_days(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def write(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(encode(value))
                return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())

            state = root/'state'
            old = state/'2026-11-03'/'REQUEST.json'
            write(old, dict(synthetic_scheduler_fixture=True, date='2026-11-03'))
            old_bytes = old.read_bytes()
            write(state/'INDEX.json', {'2026-11-03': dict(request=str(old), state='published', continuation_required=False)})
            calendar = write(root/'calendar.json', dict(coverage_start='2026-01-01', coverage_end='2026-12-31'))
            config = dict(schema='guanheng.daily-data-service.v1', directory=str(state), raw_store=str(root/'raw'),
                template=dict(schema='guanheng.daily-data-update.v1', publication_directory=str(root/'publication'), calendar=calendar),
                inputs=dict(connections=dict(batch={}, hpr={}), cache_from='20260701', max_rows=100,
                    source_kind='sdk-synthetic', public_facts=dict(source={}, allowed_hosts=[], seconds=30,
                        max_requests=1, max_bytes=1, response_bytes=1, timeout_seconds=1)),
                schedule=dict(timezone='Asia/Shanghai', at='09:00', poll_seconds=.1), cycle_seconds=60, retry_seconds=1)
            descriptor = write(root/'config.json', config)
            rows = [dict(date=day, is_open=1) for day in ('2026-11-03', '2026-11-04', '2026-11-05')]
            calls = []

            def prepare(configuration, day, output, **kwargs):
                calls.append(day)
                self.assertIn(str(old), kwargs['previous_requests'])
                return write(output/'UPDATE.json', dict(synthetic_scheduler_fixture=True, date=day))

            def run(request, output, **kwargs):
                return dict(current_sha256='b'*64, continuation_required=False)

            stamps = iter(['2026-11-04T09:00:00+08:00', '2026-11-04T15:29:59+08:00',
                           '2026-11-04T15:30:00+08:00', '2026-11-04T19:00:00+08:00'])
            control = str(uuid.uuid4())

            def clock():
                try:
                    return datetime.fromisoformat(next(stamps))
                except StopIteration:
                    write(root/control/'stop.json', dict(schema='guanheng.daily-data-stop.v1',
                        control_id=control, deadline=time.monotonic()+5))
                    return datetime.fromisoformat('2026-11-04T19:00:00+08:00')

            with patch('guanheng_app.observation.calendars.official_calendar', return_value=(rows, None)), \
                    patch.object(service, 'prepare_update', prepare), patch.object(service, 'run_update', run), \
                    patch.object(service.time, 'sleep', return_value=None):
                service.serve(descriptor, root/control, control, clock=clock)
                before = (state/'INDEX.json').read_bytes()
                control2 = str(uuid.uuid4())
                service.serve(descriptor, root/control2, control2, once=True,
                              clock=lambda: datetime.fromisoformat('2026-11-04T20:00:00+08:00'))
                self.assertEqual((state/'INDEX.json').read_bytes(), before)
                control3 = str(uuid.uuid4())
                service.serve(descriptor, root/control3, control3, once=True,
                              clock=lambda: datetime.fromisoformat('2026-11-05T15:30:00+08:00'))
            self.assertEqual(calls, ['2026-11-04', '2026-11-05'])
            self.assertEqual(old.read_bytes(), old_bytes)
            index = json.loads((state/'INDEX.json').read_bytes())
            self.assertEqual(set(index), {'2026-11-03', '2026-11-04', '2026-11-05'})
            self.assertTrue(all(row['state'] == 'published' for row in index.values()))
            self.assertTrue((root/control/'closed.json').exists())


if __name__ == '__main__':
    unittest.main()
