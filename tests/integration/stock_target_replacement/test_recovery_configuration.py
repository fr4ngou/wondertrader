"""执行修正模式只影响运行选择；同账恢复保留全部金融业务身份。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'apps/wt_runtime'))
from guanheng_wt_runtime.execution_recovery import _same_business


class RecoveryConfigurationTests(unittest.TestCase):
    def fixture(self):
        return dict(budget=dict(run_ms=0),trader=dict(account='SYNTHETIC',writes_enabled=True),
            output_directory='synthetic-original-ledger',capital_baseline=dict(total_cny='1000000'),
            cash_anchor=dict(original='synthetic-original-cash'),strategies=[dict(id='synthetic-original')],
            executer=dict(scale=1,policy=dict(default=dict(name='WtExeFact.WtStockMinImpactBorrowedExeUnit',min_order=100))))

    def test_modes_compare_without_mutating_originals(self):
        for name in ('WtExeFact.WtStockMinImpactExeUnit','WtExeFact.WtStockMinImpactBorrowedExeUnit'):
            for mode in (None,False,True):
                before=self.fixture();before['executer']['policy']['default']['name']=name
                after=deepcopy(before)
                if mode is not None:after['executer']['policy']['default']['replace_equal_position_target']=mode
                originals=deepcopy((before,after))
                self.assertTrue(_same_business(before,after))
                self.assertTrue(_same_business(after,before))
                self.assertEqual((before,after),originals)

    def test_invalid_types_and_other_algorithms_remain_rejected(self):
        for value in (None,0,1,'true',{},[]):
            before=self.fixture();after=deepcopy(before)
            after['executer']['policy']['default']['replace_equal_position_target']=value
            with self.subTest(value=value),self.assertRaises(ValueError):_same_business(before,after)
        before=self.fixture();after=deepcopy(before)
        after['executer']['policy']['default'].update(name='WtExeFact.WtMinImpactExeUnit',replace_equal_position_target=True)
        with self.assertRaises(ValueError):_same_business(before,after)

    def test_other_financial_and_execution_fields_stay_strict(self):
        mutations=[lambda x:x['trader'].update(account='OTHER'),lambda x:x['trader'].update(writes_enabled=False),
            lambda x:x.update(output_directory='other-ledger'),lambda x:x['capital_baseline'].update(total_cny='2000000'),
            lambda x:x['cash_anchor'].update(original='other'),lambda x:x['strategies'][0].update(id='other'),
            lambda x:x['executer'].update(scale=2),lambda x:x['executer']['policy']['default'].update(min_order=200)]
        for mutate in mutations:
            before=self.fixture();after=deepcopy(before)
            after['executer']['policy']['default']['replace_equal_position_target']=True;mutate(after)
            self.assertFalse(_same_business(before,after))

if __name__=='__main__':unittest.main()
