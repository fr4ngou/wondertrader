"""唯一策略的完整券商成交可缺WT标签；周期仍由原成交和P证明。"""
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'apps/wt_runtime'))
from guanheng_wt_runtime.execution_cycle_source import queried_opening_cycle


class OpeningCycleTests(unittest.TestCase):
    def setUp(self):
        self.initial = dict(symbol='159780.SZ', status='flat', quantity=0,
                            source_sha256='a' * 64)
        self.baseline = '2026-11-04T09:13:01.119030+00:00'
        self.received = datetime(2026, 11, 5, 5, 23, tzinfo=timezone.utc)
        self.cutoff = datetime(2026, 11, 5, 5, 24, tzinfo=timezone.utc)

    @staticmethod
    def trade(identity, clock, quantity, *, buy=True):
        # 合成行沿正式BrokerTradeObservation形状；查询保留原空标签和零live修订。
        return SimpleNamespace(symbol='SZSE.ETF.159780', trade_id='synthetic.' + identity,
            order_id='synthetic.order.' + identity, user_tag='', trade_date=20261105,
            trade_time=clock, is_buy=buy, quantity=float(quantity), price=.751,
            amount=.751 * quantity, first_live_revision=0, submission_revision=0)

    def cycle(self, rows, quantity, *, received=None):
        trades = SimpleNamespace(known=True, trades=rows)
        return queried_opening_cycle('159780.SZ', 'SZSE.ETF.159780', self.initial,
            self.baseline, quantity, received or self.received, self.cutoff, trades, lambda: None)

    def test_complete_query_without_tag_recovers_real_opening(self):
        rows = [self.trade('first', 93613000, 1000), self.trade('next', 93700000, 11000)]
        original = [dict(vars(row)) for row in rows]
        result = self.cycle(rows, 12000)
        self.assertEqual(result['opened_at'], '2026-11-05T01:36:13+00:00')
        self.assertEqual(len(result['source_sha256']), 64)
        self.assertEqual([vars(row) for row in rows], original)
        self.assertEqual(self.cycle(rows[:1], 1000)['cycle_id'], result['cycle_id'])

    def test_existing_inventory_keeps_its_original_baseline(self):
        self.initial.update(status='initial_inventory', quantity=12900,
                            cycle_id='initial-inventory:synthetic', baseline_at=self.baseline)
        result = self.cycle([self.trade('add', 93613000, 3600)], 16500)
        self.assertEqual(result, dict(status='initial_inventory',
            cycle_id='initial-inventory:synthetic', baseline_at=self.baseline, source_sha256='a' * 64))

    def test_missing_fills_do_not_invent_an_opening(self):
        self.assertIsNone(self.cycle([self.trade('first', 93613000, 1000)], 12000))

    def test_newer_fill_does_not_explain_an_earlier_position(self):
        rows = [self.trade('first', 93613000, 1000), self.trade('later', 93700000, 11000)]
        received = datetime(2026, 11, 5, 1, 36, 20, tzinfo=timezone.utc)
        self.assertIsNone(self.cycle(rows, 12000, received=received))

    def test_flat_then_rebuy_uses_the_actual_new_opening(self):
        rows = [self.trade('old', 93613000, 1000), self.trade('flat', 93700000, 1000, buy=False),
                self.trade('new', 100000000, 12000)]
        self.assertEqual(self.cycle(rows, 12000)['opened_at'], '2026-11-05T02:00:00+00:00')

    def test_ambiguous_same_time_ordering_still_waits(self):
        rows = [self.trade('buy', 93613000, 12000), self.trade('sell', 93613000, 1000, buy=False)]
        self.assertIsNone(self.cycle(rows, 11000))


if __name__ == '__main__':
    unittest.main()
