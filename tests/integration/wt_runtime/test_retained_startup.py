"""保留策略启动窗口和实际开仓时间回归。"""
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from guanheng_wt_runtime.execution_configured import RetainedRuntimeInput, _retained_seed_identity
from guanheng_strategy_core.contracts import canonical_bytes
from guanheng_strategy_native import QuantityPolicy
from guanheng_strategy_v1 import ALGORITHM_ID, RetainedConfig


class RetainedStartupTests(unittest.TestCase):
    def test_callback_failure_keeps_fixed_reason_for_persistent_log(self):
        from guanheng_wt_runtime.execution_configured import _callback_failure_details
        from guanheng_wt_runtime.execution_strategy import CtaBridgeError
        details = _callback_failure_details(CtaBridgeError('account_sellable_mismatch'))
        self.assertEqual(details['reason'], 'account_sellable_mismatch')
        self.assertEqual(details['exception_type'], 'CtaBridgeError')
        self.assertNotIn('reason', _callback_failure_details(CtaBridgeError('private-account-material')))

    def test_recovery_seed_preserves_original_cycle_clock_without_deciding(self):
        from guanheng_strategy_core.contracts import EvaluationBudget
        request = SimpleNamespace(configuration=RetainedConfig('synthetic-new-role',.8),
            cycles_captured_at='2026-11-04T09:13:01.119030+00:00',
            cycles_valid_until='2026-11-04T09:17:01.119030+00:00')
        inputs = RetainedRuntimeInput(request,QuantityPolicy('1000000','synthetic'),None,None,'synthetic')
        original = dict(vars(request))
        with patch('guanheng_wt_runtime.retained_evaluation.evaluate_retained',
                   side_effect=AssertionError('synthetic-old-seed-must-not-decide')) as evaluate:
            for recovery in ('resume_clean','resume_reconciled'):
                identity = _retained_seed_identity(inputs,recovery,budget=EvaluationBudget())
                self.assertEqual(identity,(sha256(canonical_bytes(request.configuration)).hexdigest(),ALGORITHM_ID))
            evaluate.assert_not_called()
            with self.assertRaisesRegex(AssertionError,'synthetic-old-seed'):
                _retained_seed_identity(inputs,'record_clean',budget=EvaluationBudget())
            evaluate.assert_called_once()
        self.assertEqual(vars(request),original)

    def test_new_candidate_fill_keeps_real_opening_time(self):
        from guanheng_wt_runtime.execution_cycle_source import queried_opening_cycle
        symbol = '588030.SH'
        row = SimpleNamespace(symbol='SSE.ETF.588030', trade_id='synthetic-fill', order_id='synthetic-order',
            user_tag='synthetic-wt', trade_date=20261105, trade_time=142757000, is_buy=True,
            quantity=100., price=1.403, amount=140.3)
        result = queried_opening_cycle(symbol, row.symbol,
            dict(symbol=symbol, status='flat', quantity=0, source_sha256='f'*64),
            '2026-11-04T09:13:01.119030+00:00', 100,
            datetime(2026,11,5,6,28,tzinfo=timezone.utc), datetime(2026,11,5,6,29,tzinfo=timezone.utc),
            SimpleNamespace(known=True,trades=(row,)), lambda: None)
        self.assertEqual(result['opened_at'], '2026-11-05T06:27:57+00:00')


if __name__ == '__main__':
    unittest.main()
