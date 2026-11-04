"""旧输入在REQUEST提交前后的原读取责任；不允许恢复生成旧请求。"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from integrations.guanheng import daily_data_service as service
from integrations.guanheng.daily_input_recovery import observe_input_reads
from integrations.guanheng.market_generation import encode
from guanheng_qmt_shm.read_retention_client import RetainedReadPending


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(value))
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def memory():
    return dict(consumed=set(), pending=set(), checked={}, slots={}, roots=set())


class InputRecoveryTests(unittest.TestCase):
    def fixtures(self, root, *, published=False, attempted=True, reference=False):
        old = root/'state/2026-11-03/REQUEST.json'
        if published:
            write(old, dict(synthetic_fixture=True))
        configuration = dict(inputs=dict(connections=dict(batch={})), price_scope=dict(reference_connection={}))
        write(old.parent/'inputs/INPUTS.json', dict(configuration=configuration))
        name = 'prices/source/universe-000.json' if reference else 'cache/slots/0000-none.json'
        slot = old.parent/'inputs'/name
        request = dict(request_id=str(uuid.uuid4()), operation_id='market.security_universe' if reference else 'market.market_data', arguments={})
        write(slot, dict(request=request, attempted=attempted, consumed=False))
        index = {'2026-11-03': dict(request=str(old), state='published' if published else 'failed')}
        return old, slot, request, index

    def patches(self, *, pending=False):
        class Transport:
            def __init__(self, *args, **kwargs):
                pass
            def close(self):
                pass
        class Client:
            def __init__(self, transport):
                pass
            def read(self, operation, arguments, slot, **kwargs):
                if pending:
                    raise RetainedReadPending('original unresolved')
                self_record = json.loads(slot.read_bytes())
                assert slot.exists() and self_record['attempted'] is True
                assert operation == self_record['request']['operation_id']
                self_record['consumed'] = True
                write(slot, self_record)
        return (patch('integrations.guanheng.source_history_transport.BoundHistorySource', Transport),
                patch('guanheng_qmt_shm.read_retention_client.RetainedReadClient', Client),
                patch('guanheng_qmt_shm.read_retention_client.inspect_saved_result', return_value=None))

    def test_unprepared_old_day_is_not_a_missing_request_dependency_and_keeps_original_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, slot, request, index = self.fixtures(root)
            before = (old.parent/'inputs/INPUTS.json').read_bytes()
            write(root/'state/INDEX.json', index)
            calendar = write(root/'calendar.json', dict(coverage_start='2026-01-01', coverage_end='2026-12-31'))
            config = dict(schema='guanheng.daily-data-service.v1', directory=str(root/'state'), raw_store=str(root/'raw'),
                template=dict(schema='guanheng.daily-data-update.v1', publication_directory=str(root/'publication'), calendar=calendar),
                inputs=dict(connections=dict(batch={}, hpr={}), cache_from='20260701', max_rows=100,
                    source_kind='sdk-synthetic', public_facts=dict(source={}, allowed_hosts=[], seconds=30,
                        max_requests=1, max_bytes=1, response_bytes=1, timeout_seconds=1)),
                schedule=dict(timezone='Asia/Shanghai', at='09:00', poll_seconds=.1), cycle_seconds=60, retry_seconds=1)
            descriptor = write(root/'config.json', config)
            prepared = []
            def prepare(configuration, day, output, **kwargs):
                self.assertNotIn(str(old), kwargs['previous_requests'])
                prepared.append(day)
                return write(output/'UPDATE.json', dict(synthetic_scheduler_fixture=True))
            p1, p2, p3 = self.patches()
            rows = [dict(date=day, is_open=1) for day in ('2026-11-03', '2026-11-04')]
            with p1, p2, p3, patch('guanheng_app.observation.calendars.official_calendar', return_value=(rows, None)), \
                    patch.object(service, 'prepare_update', prepare), \
                    patch.object(service, 'run_update', return_value=dict(current_sha256='b'*64, continuation_required=False)):
                for _ in range(2):
                    control = str(uuid.uuid4())
                    service.serve(descriptor, root/control, control, once=True,
                                  clock=lambda: datetime.fromisoformat('2026-11-04T16:00:00+08:00'))
            self.assertEqual(prepared, ['2026-11-04'])
            self.assertFalse(old.exists())
            self.assertEqual((old.parent/'inputs/INPUTS.json').read_bytes(), before)
            saved = json.loads(slot.read_bytes())
            self.assertEqual(saved['request'], request)
            self.assertTrue(saved['consumed'])
            self.assertEqual(json.loads((root/'state/INDEX.json').read_bytes())['2026-11-03'], index['2026-11-03'])

    def test_committed_request_with_pending_reference_keeps_polling_original_id(self):
        with tempfile.TemporaryDirectory() as directory:
            old, slot, request, index = self.fixtures(Path(directory), published=True, reference=True)
            state = memory()
            p1, p2, p3 = self.patches(pending=True)
            with p1, p2, p3:
                result = observe_input_reads(index, state, target_day='2026-11-04', deadline=time.monotonic()+5, cancelled=lambda: False)
            self.assertEqual(result['pending'], 1)
            p1, p2, p3 = self.patches()
            with p1, p2, p3:
                result = observe_input_reads(index, state, target_day='2026-11-04', deadline=time.monotonic()+5, cancelled=lambda: False)
            self.assertEqual(result['pending'], 0)
            self.assertTrue(json.loads(slot.read_bytes())['consumed'])
            self.assertEqual(json.loads(slot.read_bytes())['request'], request)

    def test_unattempted_old_read_is_never_dispatched(self):
        with tempfile.TemporaryDirectory() as directory:
            _, slot, _, index = self.fixtures(Path(directory), attempted=False)
            before = slot.read_bytes()
            with patch('guanheng_qmt_shm.read_retention_client.inspect_saved_result', return_value=None), \
                    patch('integrations.guanheng.source_history_transport.BoundHistorySource', side_effect=AssertionError('new dispatch forbidden')):
                observe_input_reads(index, memory(), target_day='2026-11-04', deadline=time.monotonic()+5, cancelled=lambda: False)
            self.assertEqual(slot.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
