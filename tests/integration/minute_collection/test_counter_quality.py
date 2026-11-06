"""负量额沿原官方链恢复；格式错误、原文件、报价交付和当日边界分别保持。"""
from collections import deque
from copy import deepcopy
import ctypes as C
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import math
import sys
import threading
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'integrations'), str(ROOT / 'connectors/qmt_shm/agent'),
               str(ROOT / 'connectors/qmt_shm/host')]
from integrations.guanheng.minute_counter_quality import (
    NegativeMinuteCounter, require_minute_counters, negative_counter_count)
from integrations.guanheng.quote_counter_observation import QuoteCounterObservation
from integrations.guanheng.quote_collection import QuoteCollection
from integrations.guanheng.collected_history import CollectedSourceMarket
from integrations.guanheng import collection_maintenance as maintenance
from integrations.guanheng.native_history import NativeHistory, SourceHistoryMetadata, WTSBar, LOG_CALLBACK
from integrations.guanheng.models import SourceSession


class CounterQualityTests(unittest.TestCase):
    def test_negative_quality_distinct_from_format_and_nonfinite(self):
        require_minute_counters(0, 0, 202611051500)
        with self.assertRaises(NegativeMinuteCounter) as error:
            require_minute_counters(10, -1, 202611051301)
        self.assertEqual(error.exception.minute, 202611051301)
        for volume, amount in ((1, math.nan), (True, 1), ('2', 1)):
            with self.assertRaises(ValueError) as error:
                require_minute_counters(volume, amount, 202611051301)
            self.assertNotIsInstance(error.exception, NegativeMinuteCounter)

    def test_collected_quality_failure_preserves_other_valid_sources(self):
        market = object.__new__(CollectedSourceMarket)
        market._check = lambda: None
        market._symbols = {'SZSE.399003'}
        market._supplements = []
        original = dict(api_version='guanheng.market.v1', status=dict(code='Unavailable', reason='missing'), data={})
        market._base = SimpleNamespace(call=lambda request: deepcopy(original))
        market._read = lambda *args: (_ for _ in ()).throw(NegativeMinuteCounter(202611051301))
        request = dict(api_version='guanheng.market.v1', action='history.source-query', request=dict(
            exchange='SZSE', code='399003', **{'from':202611050931, 'to':202611051500}, limit=240))
        result, batches = market.source_batches(request)
        self.assertEqual(result['status']['code'], 'Unavailable')
        self.assertIn('负量或负额', result['status']['reason'])
        self.assertEqual(batches, [])
        market._read = lambda *args: (_ for _ in ()).throw(ValueError('identity mismatch'))
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            market.source_batches(request)

    def test_closed_complete_labels_with_negative_amount_queue_original_recovery(self):
        owner = object.__new__(maintenance.MinuteCollectionMaintenance)
        owner.owner = threading.get_ident(); owner.closed = False
        owner.clock = lambda: 1000.
        owner.wall_clock = lambda: datetime(2026, 11, 6, 10, tzinfo=maintenance.ZONE).timestamp()
        owner.next_step = 0.; owner.cursor = owner.cycle = 0
        owner._refresh_metadata = lambda: True
        owner._days = lambda now: ('2026-11-05', '2026-11-06')
        owner.dates = ('2026-11-05', '2026-11-06')
        owner.symbols = ['SZSE.988007']; owner.codes = {'SZSE.988007':'SZSE.IDX.988007'}
        owner.profile = {}; owner.rows = {}; owner.jobs = deque(); owner.queued = set(); owner.retry_at = {}
        owner.reader = None
        owner.c = dict(batch_size=1, interval_seconds=1, retry_seconds=1)
        closed = []
        class Reader:
            def __init__(self, *args): pass
            def read_day(self, symbol, day, cutoff):
                label = int(day.replace('-', '')) * 10000 + 1500
                return dict(expected_minutes=[label], missing_minutes=[], unexpected_minutes=[],
                    bars=[dict(minute=label, volume=0., amount=-2600960.)])
            def close(self): closed.append(True)
        with patch.object(maintenance, 'CollectionMinuteReader', Reader):
            owner.step(source_ready=False)
        old, current = owner.rows['SZSE.988007', '2026-11-05'], owner.rows['SZSE.988007', '2026-11-06']
        self.assertEqual(old['state'], 'invalid_counters')
        self.assertEqual(old['missing_count'], 0)
        self.assertEqual(old['invalid_counter_count'], 1)
        self.assertEqual(current['state'], 'awaiting_closed_day')
        self.assertEqual(list(owner.jobs), [('SZSE.988007', '2026-11-05')])
        self.assertEqual(closed, [True])

    def test_actual_negative_rows_are_counted_without_mutation(self):
        rows = [dict(minute=202611051459, volume=1., amount=2.),
                dict(minute=202611051500, volume=0., amount=-2600960.)]
        before = deepcopy(rows)
        self.assertEqual(negative_counter_count(rows), 1)
        self.assertEqual(rows, before)

    def test_source_counter_samples_bounded_and_next_day_is_new_baseline(self):
        observer = QuoteCounterObservation(['000003.SH'])
        timestamp = int(datetime(2026, 11, 5, 10, tzinfo=maintenance.ZONE).timestamp() * 1000)
        for i in range(100):
            observer.observe({'000003.SH':dict(time=timestamp+i, volume=i, amount=1000-i)}, 'incremental')
        snapshot = observer.snapshot()
        self.assertEqual(snapshot['counts']['amount_regressions'], 99)
        self.assertEqual(len(snapshot['recent']), 16)
        observer.observe({'000003.SH':dict(time=timestamp+86400000, volume=0, amount=0)}, 'snapshot')
        self.assertEqual(observer.snapshot()['counts'], snapshot['counts'])
        snapshot['recent'][0]['reasons'].clear()
        self.assertTrue(observer.snapshot()['recent'][0]['reasons'])

    def test_quote_counter_diagnostic_never_rewrites_or_rejects_original_push(self):
        calls = []
        collection = QuoteCollection(dict(symbols=['000003.SH']), 'unused', 'unused')
        collection._native = SimpleNamespace(push=lambda ticks, kind: calls.append(ticks) or len(ticks),
            counts=lambda: dict(subscribed=1, delivered=len(calls), writer_processed=len(calls)))
        first = {'000003.SH':dict(time=1793842200000, volume=10., amount=100.)}
        second = {'000003.SH':dict(time=1793842201000, volume=10., amount=90.)}
        original = deepcopy(second)
        collection._on_batch(first, 'snapshot'); collection._on_batch(second, 'incremental')
        self.assertIs(calls[-1], second)
        self.assertEqual(second, original)
        status = collection.status()
        self.assertEqual(status['pushed_ticks'], 2)
        self.assertIsNone(status['error'])
        self.assertEqual(status['source_counter_observation']['counts']['amount_regressions'], 1)


@unittest.skipUnless(os.name == 'nt' and os.environ.get('MCC_NATIVE_FIXTURE'),
                     'requires fixed actual Helper and Native ABI')
class NativeCounterPrecedenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = json.loads(Path(os.environ['MCC_NATIVE_FIXTURE']).read_bytes())
        cls.native = config['base']['native_reader']  # 已绑定原生文件ABI，测试不修改安装。
        helper = config['preparation']['helper']
        path = Path(helper['library'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == helper['sha256']
        cls.directory = os.add_dll_directory(str(path.parent))  # 原Helper依赖目录，类结束释放句柄。
        cls.helper = C.CDLL(str(path))  # 原WtDtHelper仅写本测试新目录中的DSB。
        cls.helper.store_bars.argtypes = [C.c_char_p, C.POINTER(WTSBar), C.c_int, C.c_char_p, LOG_CALLBACK]
        cls.helper.store_bars.restype = C.c_bool

    @classmethod
    def tearDownClass(cls):
        cls.directory.close()

    def check_case(self, name, *, negative=False, nonfinite=False, bad_date=False,
                   later_bad_date=False, identity_changed=False):
        parent = Path('E:/workspace/wondertrader-qa/minute-counter-precedence-regressions')
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            root = Path(temporary)
            rows = (WTSBar * 2)()
            for i, row in enumerate(rows):
                row.date = 20261105; row.time = (20261105 - 19900000) * 10000 + 931 + i
                row.open = row.high = row.low = row.close = 1.
                row.vol = 10.; row.money = 100.
            if negative: rows[0].money = -100.
            if nonfinite: rows[1].close = math.nan
            if bad_date: rows[0].date = 20261399
            if later_bad_date: rows[1].date = 20261399
            path = root / (name + '.dsb')
            logger = LOG_CALLBACK(lambda _message: None)
            self.assertTrue(self.helper.store_bars(os.fsencode(path), rows, len(rows), b'm1', logger))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            metadata = SourceHistoryMetadata(source=SourceSession('Qmt', 'regression', 'regression', 1),
                qualification='DevelopmentVerified', dataset_version='counter-precedence-regression',
                content_id=digest, source_license='private-test', period='1m', expected_count=2,
                price_unit='unknown', volume_unit='unknown', amount_unit='unknown', minute_boundary='right')
            reader = NativeHistory(Path(self.native['library']), self.native['sha256'],
                                   max_bars=10, max_file_bytes=1048576)
            try:
                with patch('integrations.guanheng.native_history.digest',
                           side_effect=[digest, '0' * 64]) if identity_changed else patch(
                               'integrations.guanheng.native_history.digest', return_value=digest):
                    with self.assertRaises(ValueError) as caught:
                        reader.read_source_file(path, '000003.SH', metadata)
                pure = negative and not (nonfinite or bad_date or later_bad_date or identity_changed)
                self.assertEqual(isinstance(caught.exception, NegativeMinuteCounter), pure, name)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            finally:
                reader.close()

    def test_real_helper_checks_all_rows_before_pure_negative_classification(self):
        self.check_case('negative-only', negative=True)
        self.check_case('nonfinite-only', nonfinite=True)
        self.check_case('negative-then-nonfinite', negative=True, nonfinite=True)

    def test_real_helper_checks_dates_and_identity_before_quality_fallback(self):
        self.check_case('bad-date-only', bad_date=True)
        self.check_case('negative-with-bad-date', negative=True, bad_date=True)
        self.check_case('negative-then-bad-date', negative=True, later_bad_date=True)
        self.check_case('negative-with-identity-change', negative=True, identity_changed=True)


if __name__ == '__main__':
    unittest.main()
