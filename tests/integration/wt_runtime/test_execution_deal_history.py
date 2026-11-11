"""跨日券商成交来源及原 R22 周期路径。"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from guanheng_wt_runtime.execution_configured import RetainedStrategy
from guanheng_wt_runtime.execution_cycle_source import _digest, queried_opening_cycle
from guanheng_wt_runtime.execution_deal_export import _native_trade_id, verify_export, _EXPORT_FIELDS
from guanheng_wt_runtime.execution_deal_history import ClosedDealHistory, SCHEMA, SHANGHAI
from guanheng_wt_runtime.execution_strategy import BrokerTradeValue


SYMBOL = '159780.SZ'
NATIVE = 'SZSE.ETF.159780'
BASELINE = '2026-11-04T09:13:01+00:00'
SCOPE = 'a'*64
INITIAL = dict(symbol=SYMBOL, status='flat', quantity=0, source_sha256='b'*64)


def stamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=SHANGHAI).astimezone(timezone.utc)


def broker_row(day, event_time, trade_id='origin', *, quantity=27000, buy=True):
    return BrokerTradeValue(NATIVE, trade_id, 'order', '', day, buy, event_time, 0,
                            1000, quantity, 1.25, quantity*1.25)


def history_value(*rows):
    value = dict(schema=SCHEMA, scope=SCOPE, first_day='2026-11-04', last_day='2026-11-11',
                 received_at=stamp('2026-11-11T15:30:00').isoformat(), export_sha256='c'*64,
                 observation_sha256='d'*64, coverage_sha256='e'*64, rows=[asdict(row) for row in rows])
    value['sha256'] = _digest(value)
    return value


def capture(rows, queried):
    return SimpleNamespace(known=True, query_received_ms=int(queried.timestamp()*1000), trades=tuple(rows))


class ClosedDealHistoryTest(unittest.TestCase):
    def setUp(self):
        self.opening = broker_row(20261106, 94501000)
        self.history = ClosedDealHistory.from_dict(history_value(self.opening), SCOPE, BASELINE)
        self.today = stamp('2026-11-12T09:31:00')
        self.cutoff = stamp('2026-11-12T09:31:10')

    def check(self):
        pass

    def join(self, *current):
        return self.history.join(current, self.today, self.today, self.cutoff, self.check)

    def cycle(self, trades):
        return queried_opening_cycle(SYMBOL, NATIVE, INITIAL, BASELINE, 27000, self.today,
                                     self.cutoff, trades, self.check)

    def test_empty_current_query_preserves_original_opening_and_time(self):
        actual = self.cycle(self.join())
        self.assertEqual(actual['opened_at'], stamp('2026-11-06T09:45:01').isoformat())

    def test_missing_day_wrong_scope_and_tampered_receipt(self):
        later = stamp('2026-11-13T09:31:10')
        self.assertIsNone(self.history.join((), later, later, later, self.check))
        self.assertIsNone(self.history.join((), self.history.received_at, self.today, self.cutoff, self.check))
        original = history_value(self.opening)
        with self.assertRaises(ValueError):
            ClosedDealHistory.from_dict(original, 'e'*64, BASELINE)
        original['rows'][0]['quantity'] += 1
        with self.assertRaises(ValueError):
            ClosedDealHistory.from_dict(original, SCOPE, BASELINE)

    def test_duplicate_with_local_tag_deduplicates_and_conflicting_fill_rejects(self):
        same = replace(self.opening, user_tag='local')
        self.assertEqual(self.join(same).trades, (self.opening,))
        self.assertIsNone(self.join(replace(same, quantity=100)))
        omitted = broker_row(20261110, 94501000, 'omitted')
        self.assertIsNone(self.join(omitted))

    def test_current_equal_net_sell_then_rebuy_changes_cycle(self):
        sold = broker_row(20261112, 93001000, 'sold', buy=False)
        rebought = broker_row(20261112, 93010000, 'rebought')
        actual = self.cycle(self.join(sold, rebought))
        self.assertEqual(actual['opened_at'], stamp('2026-11-12T09:30:10').isoformat())

    def test_actual_strategy_requires_current_query_after_position(self):
        strategy = RetainedStrategy.__new__(RetainedStrategy)
        strategy.deal_history = self.history
        strategy.max_age = 60
        broker = SimpleNamespace(position_received_ms=int(self.today.timestamp()*1000))
        older = stamp('2026-11-12T09:30:59')
        self.assertIsNone(strategy._historical_cycle_facts(broker, capture([], older), self.cutoff, self.check))
        self.assertIsNone(strategy._historical_cycle_facts(broker, capture([], self.history.received_at), self.cutoff, self.check))
        actual = strategy._historical_cycle_facts(broker, capture([], self.today), self.cutoff, self.check)
        self.assertEqual(actual.trades, (self.opening,))
        future = stamp('2026-11-12T09:32:00')
        broker.position_received_ms = int(future.timestamp()*1000)
        self.assertIsNone(strategy._historical_cycle_facts(broker, capture([], self.today), self.cutoff, self.check))

    def test_qmt_export_checks_identity_and_original_millisecond_fact(self):
        day = '20261106'
        original = broker_row(int(day), 94501234, _native_trade_id('SZSE', '159780', day, '8897'))
        row = ['account', 'SZ', '159780', '8897', 'order', '买入', '1.25', '27000', day, '09:45:01', '33750.00']
        exported = ('\t'.join(_EXPORT_FIELDS)+'\n'+'\t'.join(row)+'\n').encode('gb18030')
        evidence = verify_export(exported, 'account', self.history.first_day,
                                 self.history.last_day, 1, [asdict(original)])
        self.assertEqual(evidence, [asdict(original)])
        with self.assertRaises(ValueError):
            verify_export(exported, 'wrong-account', self.history.first_day,
                          self.history.last_day, 1, [asdict(original)])
        with self.assertRaises(ValueError):
            verify_export(exported, 'account', self.history.first_day,
                          self.history.last_day, 2, [asdict(original)])


if __name__ == '__main__':
    unittest.main()
