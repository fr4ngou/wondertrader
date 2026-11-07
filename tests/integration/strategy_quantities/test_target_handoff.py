"""合成数量主链：已结清阶段交接、实际未决保留和诊断序号持续推进。"""
from dataclasses import replace
import unittest

from guanheng_strategy_native import (
    Basis, EconomicTarget, NativePosition, Observation, Price, Quantity, QuantityError,
    QuantityPolicy, StageState, Weight, advance,
)
from guanheng_wt_runtime.retained_evaluation import advance_retained, LEGACY_QUANTITY_MODEL


class TargetHandoffTests(unittest.TestCase):
    def setUp(self):
        self.policy = QuantityPolicy('10000', 'synthetic explicit capital')
        self.old = EconomicTarget('synthetic', 'synthetic-v1', 'config', self.policy.policy_id,
            '2025-06-26', ('510000.SH', '510001.SH'),
            (Weight('510000.SH', '0.5'), Weight('510001.SH', '0.5')))
        self.new = replace(self.old, allocation_date='2025-07-31',
            weights=(Weight('510000.SH', '0.2'), Weight('510001.SH', '0.3')))
        self.frozen = Basis('2025-08-20T09:30:00+08:00', 'a'*64, '10000', '0',
            '5000', '0', 'synthetic NAV', 'synthetic cash', 'synthetic fee',
            (Price('510000.SH', '1', 'synthetic raw'), Price('510001.SH', '1', 'synthetic raw')),
            True, 'capture-before-sell')
        self.state = StageState(self.old, self.policy, self.frozen, 'selling', 16,
            (Quantity('510000.SH', 8000), Quantity('510001.SH', 0)),
            (Quantity('510000.SH', 5000), Quantity('510001.SH', 0)))
        self.basis = replace(self.frozen, observed_at='2025-08-21T09:30:00+08:00',
            native_observation_id='capture-after-sell')
        self.observation = Observation(self.basis.observed_at, 'synthetic actual capture',
            (NativePosition('510000.SH', 5000, 5000), NativePosition('510001.SH', 0, 0)),
            True, self.basis.native_observation_id)

    def test_missing_actual_fee_keeps_frozen_sell_then_allows_zero_weight_exit(self):
        from guanheng_strategy_native.planner import advance_known_sells
        basis = replace(self.basis, native_nav_verified=False)
        partially_sold = replace(self.observation,
            positions=(NativePosition('510000.SH', 6000, 6000), NativePosition('510001.SH', 0, 0)))
        pending = replace(partially_sold,
            positions=(NativePosition('510000.SH', 6000, 5000, 5000), NativePosition('510001.SH', 0, 0)))
        self.assertEqual(advance_known_sells(self.new, self.policy, pending, basis, self.state).status,
                         'waiting_pending')
        result = advance_known_sells(self.new, self.policy, partially_sold, basis, self.state)
        self.assertEqual(result.submit_targets, self.state.targets)
        waiting = advance_known_sells(self.new, self.policy, self.observation, basis, self.state)
        self.assertEqual((waiting.status, waiting.submit_targets), ('waiting_basis', ()))

        exit_target = replace(self.new, weights=(Weight('510000.SH', '0'), Weight('510001.SH', '0.3')))
        own_positions = replace(self.observation,
            positions=(NativePosition('510000.SH', 5000, 5000), NativePosition('510001.SH', 1700, 1700)))
        result = advance_known_sells(exit_target, self.policy, own_positions, basis, None)
        self.assertEqual(result.submit_targets,
            (Quantity('510000.SH', 0), Quantity('510001.SH', 1700)))
        self.assertFalse(result.state.basis.native_nav_verified)

    def test_settled_sell_accepts_latest_target_without_buying_old_target(self):
        outcome, _ = advance_retained(self.new, self.policy, self.observation, self.basis, self.state)
        self.assertEqual(outcome.status, 'selling')
        self.assertEqual(outcome.state.target, self.new)
        self.assertEqual(outcome.state.sequence, 1)
        self.assertEqual(outcome.submit_targets,
            (Quantity('510000.SH', 2000), Quantity('510001.SH', 0)))
        self.assertEqual(advance_retained(self.new, self.policy, self.observation, self.basis, self.state)[0], outcome)
        self.assertEqual(advance(self.new, self.policy, self.observation, self.basis, self.state), outcome)

    def test_new_target_consumes_one_fee_basis_and_report_repeats_same_result(self):
        observed = replace(self.observation, positions=(NativePosition('510000.SH', 0, 0),
            NativePosition('510001.SH', 0, 0)))
        old = replace(self.old, weights=(Weight('510000.SH', '0'), Weight('510001.SH', '0.5')))
        state = StageState(old, self.policy, self.frozen, 'awaiting_buy', 0,
            (Quantity('510000.SH', 0), Quantity('510001.SH', 0)),
            (Quantity('510000.SH', 0), Quantity('510001.SH', 0)))
        new = replace(old, allocation_date='2025-07-31',
            weights=(Weight('510000.SH', '0.5'), Weight('510001.SH', '0')))
        base = replace(self.basis, cash_cny='5004')
        consumed = []
        def fees(target, basis, observation):
            consumed.append(target)
            return replace(basis, fee_reserve_cny='5' if target == old else '3')
        runtime = advance_retained(new, self.policy, observed, base, state, basis_for_target=fees)
        report = advance_retained(new, self.policy, observed, replace(base, fee_reserve_cny='3'), state)
        self.assertEqual(consumed, [new])
        self.assertEqual(runtime, report)
        self.assertEqual(runtime[0].status, 'buying')

    def test_diagnostic_sequence_above_old_limits_continues_same_target(self):
        for sequence in (16, 64, 65, 1000):
            outcome = advance(self.old, self.policy, self.observation, self.basis,
                replace(self.state, sequence=sequence))
            self.assertEqual(outcome.status, 'buying')
            self.assertEqual(outcome.state.sequence, sequence+1)

    def test_pending_or_partial_actual_keeps_original_identity(self):
        for position, expected in (
            (NativePosition('510000.SH', 5000, 5000, 5000), 'waiting_pending'),
            (NativePosition('510000.SH', 6000, 6000), 'selling'),
            (NativePosition('510000.SH', 4000, 4000), 'blocked'),
        ):
            observed = replace(self.observation, positions=(position, self.observation.positions[1]))
            outcome, _ = advance_retained(self.new, self.policy, observed, self.basis, self.state)
            self.assertEqual(outcome.status, expected)
            self.assertIs(outcome.state, self.state)

    def test_same_sell_capture_and_unverified_observation_cannot_handoff(self):
        observed = replace(self.observation, observed_at=self.frozen.observed_at,
            native_observation_id=self.frozen.native_observation_id)
        outcome, _ = advance_retained(self.new, self.policy, observed, self.frozen, self.state)
        self.assertEqual(outcome.status, 'waiting_basis')
        self.assertIs(outcome.state, self.state)
        with self.assertRaises(QuantityError):
            advance_retained(self.new, self.policy, replace(self.observation, verified=False),
                self.basis, self.state)

    def test_waiting_cash_without_pending_accepts_new_target(self):
        state = StageState(self.old, self.policy, self.frozen, 'awaiting_buy', 0,
            self.state.targets, self.state.targets)
        unfunded = replace(self.basis, cash_cny='4900')
        outcome, _ = advance_retained(self.new, self.policy, self.observation, unfunded, state)
        self.assertEqual(outcome.state.target, self.new)
        self.assertEqual(outcome.status, 'selling')

    def test_old_report_math_is_explicit_read_only_reproduction(self):
        outcome, _ = advance_retained(self.new, self.policy, self.observation, self.basis,
            self.state, quantity_model=LEGACY_QUANTITY_MODEL)
        self.assertEqual(outcome.reason, 'stage_budget_exhausted')
        self.assertIs(outcome.state, self.state)


if __name__ == '__main__':
    unittest.main()
