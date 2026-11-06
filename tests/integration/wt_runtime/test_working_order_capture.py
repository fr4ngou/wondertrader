"""原WT活动单必须阻止已到数量阶段过早交接，终态后才由原NSQ继续。"""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'strategy_quantities'))
from test_target_handoff import TargetHandoffTests
from guanheng_wt_runtime.execution_configured import RetainedStrategy
from guanheng_wt_runtime.execution_strategy import BrokerObservationValue,BrokerPositionValue,PendingOrderValue
from guanheng_wt_runtime.retained_evaluation import advance_retained


class WorkingOrderCaptureTests(unittest.TestCase):
    def setUp(self):
        sample=TargetHandoffTests();sample.setUp();self.sample=sample
        self.strategy=RetainedStrategy.__new__(RetainedStrategy)
        self.strategy.mapping={'510000.SH':'SSE.ETF.510000','510001.SH':'SSE.ETF.510001'}
        self.strategy.targets=tuple(self.strategy.mapping.values())
        self.broker=BrokerObservationValue(True,True,1,1,1,1,2,10000.,5000.,
            (BrokerPositionValue('SSE.ETF.510000',True,5000.,5000.),))

    def capture(self, pending):
        return self.strategy._execution_capture(self.broker,self.sample.basis,self.sample.observation,pending)

    def test_working_order_retains_frozen_stage_and_terminal_accepts_new_target(self):
        row=PendingOrderValue('SSE.ETF.510000',1000.,True)
        basis,unused,observed=self.capture((row,))
        outcome,unused=advance_retained(self.sample.new,self.sample.policy,observed,basis,self.sample.state)
        self.assertEqual(outcome.status,'waiting_pending')
        self.assertIs(outcome.state,self.sample.state)
        basis,unused,observed=self.capture(())
        outcome,unused=advance_retained(self.sample.new,self.sample.policy,observed,basis,self.sample.state)
        self.assertEqual(outcome.state.target,self.sample.new)
        self.assertEqual(outcome.status,'selling')

    def test_partial_fill_keeps_original_stage_and_order_identity_changes_capture(self):
        first=self.capture((PendingOrderValue('SSE.ETF.510000',1000.,True),))
        second=self.capture((PendingOrderValue('SSE.ETF.510000',800.,True),))
        self.assertNotEqual(first[2].native_observation_id,second[2].native_observation_id)
        self.assertEqual(first[2].positions[0].actual,5000)
        self.assertEqual(second[2].positions[0].actual,5000)
        outcome,unused=advance_retained(self.sample.new,self.sample.policy,second[2],second[0],self.sample.state)
        self.assertIs(outcome.state,self.sample.state)


if __name__=='__main__':unittest.main()
