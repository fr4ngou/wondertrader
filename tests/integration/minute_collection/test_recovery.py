"""闭合日恢复与逐段来源回归；原生/真实来源另由实际模块主链验收。"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'integrations'), str(ROOT / 'connectors/qmt_shm/agent'),
               str(ROOT / 'connectors/qmt_shm/host')]

from integrations.guanheng.source_history_selection import select_sources, SourceSelectionConflict
from integrations.guanheng.collection_coverage import CollectionCoverage
from guanheng_market_client.exchange_calendar import official_calendar, CalendarFailure


def data(version, quantities):
    metadata = dict(source=dict(provider='Qmt', instance_id='fixture', session_id='fixture', generation=1),
        qualification='DevelopmentVerified', dataset_version=version, source_license='synthetic-fixture',
        adjustment='none', factor_version='', minute_boundary='right', timezone='Asia/Shanghai',
        content_id=hashlib.sha256(version.encode()).hexdigest(), value_semantics='source',
        timestamp_semantics='source_label', price_unit='unknown', volume_unit='unknown', amount_unit='unknown')
    bars = [dict(symbol='SSE.510300', minute=minute, open=1., high=1., low=1., close=1.,
                 volume=float(volume), amount=float(volume)) for minute, volume in quantities]
    return dict(metadata=metadata, bars=bars, coverage='Unknown', missing_minutes=[],
                selection=dict(period_minutes=1, limit=10))


class RecoverySelectionTests(unittest.TestCase):
    def setUp(self):
        self.query = dict(exchange='SSE', code='510300', **{'from':202611030931, 'to':202611040932}, limit=10)
        self.raw = data('writer', [(202611030932, 30), (202611040931, 4)])
        self.recovered = data('source-day', [(202611030931, 10), (202611030932, 20)])
        self.preferences = [dict(**{'from':202611030931, 'to':202611031500}, dataset_version='source-day')]

    def test_gap_only_conflicts_with_cumulative_boundary(self):
        with self.assertRaises(SourceSelectionConflict):
            select_sources([self.recovered, self.raw], self.query)

    def test_complete_day_selection_removes_accumulated_boundary_without_double_count(self):
        value = select_sources([self.recovered, self.raw], self.query, preferred_ranges=self.preferences)
        self.assertEqual([r['volume'] for r in value['bars']], [10., 20., 4.])
        self.assertEqual([p['metadata']['dataset_version'] for p in value['provenance']], ['source-day', 'writer'])
        self.assertEqual(sum(r['volume'] for r in value['bars'][:2]), 30.)
        self.assertEqual(self.raw['bars'][0]['volume'], 30.)

    def test_reselect_mixed_data_preserves_leaf_metadata(self):
        mixed = select_sources([self.recovered, self.raw], self.query, preferred_ranges=self.preferences)
        selected = select_sources([mixed], self.query, preferred_ranges=self.preferences)
        self.assertEqual(selected, mixed)

    def test_two_complete_versions_remain_explicit_conflict(self):
        preferences = self.preferences + [dict(self.preferences[0], dataset_version='other-day')]
        with self.assertRaises(SourceSelectionConflict):
            select_sources([self.recovered], self.query, preferred_ranges=preferences)


class SharedCalendarTests(unittest.TestCase):
    def test_original_digest_and_closure_rules_remain_identical(self):
        days = ['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06']
        encode = lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        configuration = dict(id='fixture', coverage_start='2026-11-01', coverage_end='2026-11-08',
            verified_through='2026-11-08', closed_dates=[], method='synthetic-fixture', evidence=[],
            verified_open_dates_sha256=hashlib.sha256(encode(days)).hexdigest())
        rows, metadata = official_calendar(configuration)
        self.assertEqual([r['date'] for r in rows if r['is_open']], days)
        self.assertEqual(metadata['version'], hashlib.sha256(encode(configuration)).hexdigest())
        broken = deepcopy(configuration); broken['closed_dates'] = ['2026-11-03']
        with self.assertRaises(CalendarFailure):
            official_calendar(broken)


class QuoteCoverageTests(unittest.TestCase):
    def test_original_integral_float_timestamp_remains_accepted(self):
        coverage = CollectionCoverage(['510300.SH'])
        coverage.accept({'510300.SH': {'time': 1793775600000.0}}, 1793775601.)
        value = coverage.snapshot(1793775602.)['symbols'][0]
        self.assertEqual(value['source_time_ms'], 1793775600000)
        self.assertEqual(value['delivered_ticks'], 1)
        self.assertEqual(value['quote_state'], 'observed_today')

    def test_invalid_batch_does_not_partially_advance_time_projection(self):
        coverage = CollectionCoverage(['510300.SH', '510500.SH'])
        with self.assertRaises(ValueError):
            coverage.accept({'510300.SH': {'time': 1793775600000}, '510500.SH': {'time': float('nan')}}, 1793775601.)
        self.assertTrue(all(row['source_time_ms'] is None for row in coverage.snapshot(1793775602.)['symbols']))


if __name__ == '__main__':
    unittest.main()
