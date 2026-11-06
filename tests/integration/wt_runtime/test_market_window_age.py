"""窗口时效换代保持原路径、金融身份及原对象。"""
from copy import deepcopy
import unittest
from guanheng_wt_runtime.execution_recovery import _same_business
from guanheng_wt_runtime.execution_strategy import CtaBridgeError

class MarketWindowAgeRecoveryTests(unittest.TestCase):
    def fixture(self):
        return dict(budget=dict(run_ms=0),trader=dict(account='SYNTHETIC'),
            strategies=[dict(parameters=dict(python_strategy=dict(market_window=dict(
                path='E:/synthetic/current-window.json',max_age_seconds=3600))))])

    def test_explicit_age_change_preserves_originals(self):
        old=self.fixture();new=deepcopy(old)
        new['strategies'][0]['parameters']['python_strategy']['market_window']['max_age_seconds']=600
        self.assertTrue(_same_business(old,new));self.assertTrue(_same_business(new,old))
        self.assertEqual(old['strategies'][0]['parameters']['python_strategy']['market_window']['max_age_seconds'],3600)

    def test_invalid_age_rejected(self):
        for value in (0,-1,True,'600',float('inf'),float('nan'),604801):
            with self.subTest(value=str(value)):
                new=self.fixture();new['strategies'][0]['parameters']['python_strategy']['market_window']['max_age_seconds']=value
                with self.assertRaises((ValueError,CtaBridgeError)):_same_business(self.fixture(),new)

    def test_source_path_and_account_remain_bound(self):
        for key in ('path','account'):
            new=self.fixture()
            if key=='path':new['strategies'][0]['parameters']['python_strategy']['market_window']['path']='E:/synthetic/other-window.json'
            else:new['trader']['account']='OTHER'
            self.assertFalse(_same_business(self.fixture(),new))

if __name__=='__main__':unittest.main()
