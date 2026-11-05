"""原费表分舍入及完整买入现金覆盖，保护已复现的负现金根因。"""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'apps/wt_runtime'))
from guanheng_strategy_native import (
    Basis, EconomicTarget, NativePosition, Observation, Price, QuantityPolicy, Weight, advance,
)
from guanheng_wt_runtime.execution_facts import buy_fee_basis


class BuyFeeBasisTests(unittest.TestCase):
    def model(self, capital='100', weight='1', held=0, cash='100', reserve='0'):
        symbol, stamp = '510300.SH', '2026-11-05T15:00:00+08:00'
        policy = QuantityPolicy(capital, 'explicit test model')
        target = EconomicTarget('qa', 'unchanged-model', 'explicit', policy.policy_id, '2026-11-05',
            (symbol,), (Weight(symbol, weight),))
        basis = Basis(stamp, '0'*64, capital, '0', cash, reserve, 'native', 'native', 'configured',
            (Price(symbol, '1', 'native'),), True, 'native-capture')
        observation = Observation(stamp, 'native', (NativePosition(symbol, held, held, None),), True, 'native-capture')
        return target, policy, basis, observation, {symbol:'SSE.ETF.510300'}

    def test_original_double_half_cent_changes_cash_admission(self):
        # Decimal先求精确乘积会分别得到0.04/0，原WT连续double运算实际为0.03/0.01。
        for rate, expected in ((.00035, '0.03'), (4.9999999999999996e-05, '0.01')):
            with self.subTest(rate=rate):
                target, policy, basis, observation, mapping = self.model()
                adjusted = buy_fee_basis(target, policy, basis, observation, mapping,
                    {'SSE.ETF':dict(open=rate, byvolume=True)}, 'original-fees', split_fills=False)
                self.assertEqual(adjusted.fee_reserve_cny, expected)
                self.assertEqual(advance(target, policy, observation, adjusted, None).status, 'waiting_cash')
                self.assertEqual(target.weights[0].weight, '1')

    def test_explicit_twenty_is_not_proof_of_full_buy_fee_coverage(self):
        target, policy, basis, observation, mapping = self.model('1000000', '0.9999', 800000, '200000', '20')
        self.assertEqual(advance(target, policy, observation, basis, None).status, 'buying')
        adjusted = buy_fee_basis(target, policy, basis, observation, mapping,
            {'SSE.ETF':dict(open=.01, byvolume=True)}, 'original-fees', split_fills=False)
        self.assertEqual(adjusted.fee_reserve_cny, '1999')
        self.assertEqual(advance(target, policy, observation, adjusted, None).status, 'waiting_cash')

    def test_minimum_fee_and_configured_floor_keep_native_units(self):
        target, policy, basis, observation, mapping = self.model(reserve='20')
        adjusted = buy_fee_basis(target, policy, basis, observation, mapping,
            {'SSE.ETF':dict(open=.0001, minfee=5, byvolume=False)}, 'original-fees', split_fills=False)
        self.assertEqual(adjusted.fee_reserve_cny, '20')
        adjusted = buy_fee_basis(target, policy, replace(basis, fee_reserve_cny='0'), observation, mapping,
            {'SSE.ETF':dict(open=.0001, minfee=5, byvolume=False)}, 'original-fees', split_fills=False)
        self.assertEqual(adjusted.fee_reserve_cny, '5')


if __name__ == '__main__':
    unittest.main()
