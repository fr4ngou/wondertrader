"""历史回算绑定较新WT快照；合成股票池变化用来捕捉日期和成员混用。"""
import hashlib
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from guanheng_app.observation import wt_breadth_source as source
from guanheng_app.observation.source_fetch import CollectionBudget, SourceFailure
from integrations.guanheng_market_client.daily_facts import FIELDS, STATS


class Objects:
    def __init__(self):
        self.values = {}

    def put(self, body):
        identity = hashlib.sha256(body).hexdigest()
        self.values[identity] = body
        return identity

    def get(self, identity):
        return self.values[identity]


class SnapshotDateTests(unittest.TestCase):
    def run_history(self, day, *, mismatch=False, wrong_snapshot_date=False):
        snapshot_id = 'a' * 64
        calls = []
        # 历史池有一只退出证券；新快照池另含新增证券，不能用末日池覆盖历史池。
        current = ['SSE.600000', 'SZSE.000001']
        members = ['SSE.600000'] if day == '2026-11-02' or mismatch else current

        def ok(data):
            return dict(status=dict(code='Ok'), data=data)

        class Client:
            def source_market_snapshot_query(self, date):
                calls.append(('snapshot', date))
                return ok(dict(snapshot_id=snapshot_id, members=current,
                               observation_date='2026-11-02' if wrong_snapshot_date else '2026-11-03'))

            def source_day_facts_query(self, date, identity):
                calls.append(('facts', date, identity))
                return ok(dict(date=date, fields=FIELDS, members=members,
                               rows=[[date, symbol, '10.5', '10', '1500', '6', '1', 'qualified'] for symbol in members],
                               stats={key: 0 for key in STATS}, provenance=dict(universe_sha256='b' * 64)))

            def source_daily_history_batch_query(self, request):
                calls.append(('prices', request))
                return ok(dict(results=[dict(symbol=symbol, status=dict(code='Ok'), data=dict(
                    source_snapshot_id=snapshot_id, metadata=dict(adjustment='none'),
                    bars=[dict(date=int(day.replace('-', '')), close=10.5)])) for symbol in members]))

        fetch = SimpleNamespace(budget=CollectionBudget(time.monotonic() + 5), timeout=1, objects=Objects(), records=[])
        with patch.object(source, 'observation_day', return_value=day), patch.object(
                source, 'official_calendar', return_value=([dict(date=day, is_open=1)], None)):
            result = source.history(fetch, {}, day, day, lambda seconds: Client(), calendar={}, snapshot_date='2026-11-03')
        return result, calls

    def test_historical_window_uses_current_snapshot_and_its_own_members(self):
        result, calls = self.run_history('2026-11-02')
        self.assertEqual(calls[0], ('snapshot', '2026-11-03'))
        self.assertEqual(result['breadth.ashare'][0]['market_count'], 1)
        self.assertEqual(result['breadth.ashare'][0]['advancing_count'], 1)
        self.assertEqual(calls[-1][1]['to'], 20261102)
        self.assertEqual(calls[-1][1]['snapshot_id'], 'a' * 64)

    def test_current_day_members_must_equal_snapshot_members(self):
        with self.assertRaisesRegex(SourceFailure, 'wt_daily_facts_universe_differs'):
            self.run_history('2026-11-03', mismatch=True)

    def test_misdated_snapshot_is_rejected_before_prices(self):
        with self.assertRaisesRegex(SourceFailure, 'wt_market_snapshot_date_differs'):
            self.run_history('2026-11-02', wrong_snapshot_date=True)


if __name__ == '__main__':
    unittest.main()
