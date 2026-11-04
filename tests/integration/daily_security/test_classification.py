"""证券缺口根因回归；合成事实只区分未知/零/有效价格，真实主链另有证据。"""
import tempfile
from pathlib import Path
import unittest

from integrations.guanheng.market_generation import encode
from integrations.guanheng.security_reference import SecurityReference
from integrations.guanheng_market_client.security import validate_security_data


class Facts:
    def __init__(self, rows):
        self.rows = rows

    def security_state(self, day, symbol):
        return self.rows.get(day)


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        # 明确合成日历，以连续工作日区分每个互斥分支；不作为真实交易日证据。
        path = root / 'calendar.json'
        path.write_bytes(encode(dict(kind='official-exchange-calendar/v1', id='test.calendar',
            coverage_start='2026-01-01', coverage_end='2026-12-31', closed_dates=[],
            verified_through='2026-11-02', evidence=[dict(test_fixture=True)])))
        import hashlib
        self.reference = SecurityReference(calendar=dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        self.addCleanup(self.reference.close)
        self.query = dict(symbol='SSE.600000', **{'from': 20261102, 'to': 20261106}, adjustment='none', snapshot_id='a' * 64)
        self.security = dict(symbol='SSE.600000', name=None, market='SSE', security_type='stock',
                             listed_on='2026-11-03', expires_on=None, observed_at=None)

    def test_pre_listing_zero_unknown_and_observed_price_are_distinct(self):
        facts = Facts({
            '2026-11-04': dict(tradestatus='0', qualification='qualified', volume='0', close_reference='10.42'),
            '2026-11-05': dict(tradestatus='0', qualification='qualified', volume='', close_reference=''),
            '2026-11-06': dict(tradestatus='1', qualification='qualified', volume='12500', close_reference='10.51')})
        result = self.reference.assess(self.query, self.security, [20261103], facts)
        self.assertEqual(result['before_listing_dates'], [20261102])
        self.assertEqual(result['no_trade_dates'], [20261104])
        self.assertEqual(result['unresolved_dates'], [20261105])
        self.assertEqual(result['missing_dates'], [20261106])
        response = dict(security=self.security, source_snapshot_id='a' * 64, adjustment='none',
                        history_status=dict(code='Ok', reason=''), archive=dict(first_date=20261103, last_date=20261103, count=1),
                        available_dates=[20261103], gap_assessment=result, reference_sha256=None)
        self.assertIs(validate_security_data(response, self.query), response)

    def test_active_status_without_price_and_halted_with_trades_stay_unknown(self):
        self.security['listed_on'] = None
        cases = [dict(tradestatus='1', qualification='qualified', volume='', close_reference=''),
                 dict(tradestatus='1', qualification='qualified', volume='0', close_reference='0'),
                 dict(tradestatus='0', qualification='qualified', volume='200', close_reference='10.51'),
                 dict(tradestatus='1', qualification='identity_unverified', volume='200', close_reference='10.51')]
        for state in cases:
            with self.subTest(state=state):
                result = self.reference.assess(self.query, self.security, [20261102, 20261103, 20261104, 20261105],
                                               Facts({'2026-11-06': state}))
                self.assertEqual(result['unresolved_dates'], [20261106])
                self.assertEqual(result['missing_dates'], [])
                self.assertEqual(result['no_trade_dates'], [])

    def test_expiry_and_calendar_limits_are_explicit(self):
        self.security['listed_on'] = None
        self.security['expires_on'] = '2026-11-04'
        result = self.reference.assess(self.query, self.security, [20261102, 20261103, 20261104], None)
        self.assertEqual(result['after_expiry_dates'], [20261105, 20261106])
        outside = dict(self.query, **{'from': 20191104, 'to': 20191108})
        result = self.reference.assess(outside, self.security, [], None)
        self.assertFalse(result['calendar_covered'])
        self.assertTrue(all(result[key] == [] for key in
                        ('missing_dates', 'no_trade_dates', 'before_listing_dates', 'after_expiry_dates', 'unresolved_dates')))

    def test_no_calendar_keeps_readable_price_dates_and_unknown_metadata(self):
        reference = SecurityReference()
        self.addCleanup(reference.close)
        identity = reference.security(dict(basics={}), 'SSE.510300')
        self.assertIsNone(identity['name'])
        result = reference.assess(self.query, identity, [20261103], None)
        self.assertIsNone(result['calendar_id'])
        self.assertFalse(result['calendar_covered'])
        reference.close()
        with self.assertRaises(ValueError):
            reference.security(dict(basics={}), 'SSE.510300')


if __name__ == '__main__':
    unittest.main()
