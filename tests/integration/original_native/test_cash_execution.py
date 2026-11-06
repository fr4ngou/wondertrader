"""现金约束的人工成本/时钟回归；完整WT DLL原件另以合成夹具核验。"""
from copy import deepcopy
from fractions import Fraction as F
from pathlib import Path
import json
import unittest
from guanheng_wt_runtime.original_native_contracts import build_input,_digest,ALGORITHM_ID,UPSTREAM_COMMIT,validate_report,verify_report_input,LEGACY_MODEL
from guanheng_wt_runtime.original_native_replay import OriginalNativeSession


def inputs(future_open=8):
    days=['2024-01-02','2024-01-03','2024-01-04','2024-01-05','2024-01-08']
    daily={c:[dict(date=d,code=c,open_price=p,high_price=p+1,low_price=p-1,close_price=p,volume=1000) for d in days] for c,p in [('510300',10),('510050',20)]}
    daily['510300'][2].update(open_price=future_open,high_price=max(11,future_open),low_price=min(9,future_open))
    snapshot=dict(daily=daily,calendar=days,source={'price_basis':'synthetic'})
    trades={c:[dict(action='BUY',date=days[1],price=p,reason='synthetic original signal')] for c,p in [('510300',10),('510050',20)]}
    report=dict(schema='guanheng.resonance-original-report.v1',algorithm_id=ALGORITHM_ID,upstream_commit=UPSTREAM_COMMIT,input_sha256=_digest(snapshot,original=True),trades_by_code=trades,portfolio={'history':[{'date':d} for d in days[1:]]})
    return build_input(snapshot,report)


class ObservationPorter:
    def __init__(self):self.submissions=[]
    def submit_conditional_targets(self,vector,limits,tag):
        self.submissions.append((vector,limits,tag));return ()
    def store_userdata(self,*args):pass


def session(value=None):
    value=inputs() if value is None else value
    s=OriginalNativeSession(value);p=ObservationPorter();s._porter=p;s._started=s._initialized=True;s._session_id='0'*64
    s._fees={e+'.ETF':dict(byvolume=False,open=.0003,close=.0003,closetoday=.0003) for e in ('SSE','SZSE')}
    return s,p


def observe(s,p,day=20240103,*,cash='1000000',actual=None,prices=None,pending=False):
    actual=actual or {'510300':0,'510050':0};prices=prices or {'510300':10,'510050':20}
    positions=[dict(symbol=s._mapping[c],total=q,valid=q,first_entry=202401021500 if q else 0,last_entry=202401021500 if q else 0) for c,q in actual.items()]
    nav=F(cash)+sum((F(str(prices[c]))*q for c,q in actual.items()),F(0))
    capture=dict(basis=dict(cash_cny=cash,nav_cny=str(float(nav))),positions=positions,prices=[[s._mapping[c],v] for c,v in prices.items()],projection=[])
    s._capture=lambda *_:(capture,actual,pending)
    s._calculate(p,day,1500)
    return s._records[-1]


class CashPlanningOracle(unittest.TestCase):
    def test_two_etf_whole_batch_includes_both_commissions(self):
        s,p=session();row=observe(s,p)
        quantities={r['symbol']:r['quantity'] for r in row['submit_vector']}
        self.assertEqual(quantities,{'SSE.ETF.510050':24800,'SSE.ETF.510300':49700})
        self.assertEqual(F(row['cash_control']['reserved_buy_cost_cny']),F('993297.92'))
        self.assertEqual(dict(p.submissions[0][1]),{'SSE.ETF.510050':20,'SSE.ETF.510300':10})

    def test_future_gap_never_enters_signal_day_plan(self):
        first,p=session(inputs(8));second,q=session(inputs(1000))
        a=observe(first,p);b=observe(second,q)
        self.assertEqual(a['cash_control'],b['cash_control']);self.assertEqual(a['submit_vector'],b['submit_vector'])

    def test_unfilled_sale_does_not_fund_same_batch_buy(self):
        s,p=session();a=observe(s,p,cash='100',actual={'510300':100000,'510050':0})
        self.assertEqual([o['action'] for o in a['cash_control']['orders']],['SELL'])
        self.assertEqual(a['cash_control']['reserved_buy_cost_cny'],'0')
        # 后继观测已确认实际减持和回款后，才使用该真实现金；原BUY意图保留。
        b=observe(s,p,20240104,cash='503000',actual={'510300':49700,'510050':0})
        self.assertEqual([(o['action'],o['quantity']) for o in b['cash_control']['orders']],[('BUY',24800)])
        self.assertLessEqual(F(b['cash_control']['reserved_buy_cost_cny']),F('502999'))

    def test_unfilled_gap_up_is_cash_capped_on_later_known_close(self):
        s,p=session();observe(s,p)
        b=observe(s,p,20240104,prices={'510300':20,'510050':40})
        self.assertEqual({r['symbol']:r['quantity'] for r in b['submit_vector']},{'SSE.ETF.510050':12400,'SSE.ETF.510300':25000})
        self.assertEqual(F(b['cash_control']['reserved_buy_cost_cny']),F('996298.82'))

    def test_minimum_fee_and_by_share_fee_are_cost_bounds(self):
        s,p=session();rule=s._fees['SSE.ETF'];rule['minfee']=5
        self.assertEqual(s._buy_bound('510300',100,F(1)),F('105.01'))
        self.assertLessEqual(s._sell_floor('510300',100),F('0.051'))
        rule.update(byvolume=True,open=.1,close=.1,closetoday=.1)
        self.assertEqual(s._buy_bound('510300',100,F(1)),F('110.01'))
        self.assertGreater(s._sell_floor('510300',100),F('.1'))

    def test_native_triggered_pending_is_not_submitted_again(self):
        s,p=session();row=observe(s,p,pending=True)
        self.assertEqual(row['status'],'pending_native_execution');self.assertEqual(p.submissions,[])

    def test_actual_negative_cash_fails_instead_of_reporting_success(self):
        s,p=session()
        with self.assertRaises(ValueError):observe(s,p,cash='-0.01')
        self.assertEqual(p.submissions,[])

    def test_old_a1_model_remains_readable_with_original_semantics(self):
        report=json.loads((Path(__file__).parent/'fixtures/manual-wt-report.json').read_bytes())
        self.assertEqual(validate_report(report).to_dict()['historical_model'],LEGACY_MODEL)
        self.assertEqual(report['strategy_version'],'0.1.0a1')


class ActualNativeCashOracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).parent/'fixtures'
        cls.report=json.loads((root/'cash-wt-report.json').read_bytes())
        cls.inputs=json.loads((root/'cash-wt-input.json').read_bytes())

    def test_native_late_buy_has_human_computed_cash_and_fees(self):
        r=validate_report(self.report).to_dict();verify_report_input(r,self.inputs)
        # 实际原生三笔：49700@8、24800@24、卖49700@14；首日20元限价未成交。
        cash=F(1000000)-49700*8-F('119.28')-24800*24-F('178.56')+49700*14-F('208.74')
        self.assertEqual(cash,F('702493.42'))
        self.assertLess(abs(F(r['records'][-1]['capture']['basis']['cash_cny'])-cash),F('.000001'))
        self.assertLess(abs(F(r['records'][-1]['capture']['basis']['nav_cny'])-(cash+24800*26)),F('.000001'))
        self.assertAlmostEqual(r['records'][-1]['capture']['funds']['fees'],506.58)
        self.assertTrue(all(F(row['capture']['basis']['cash_cny'])>=0 for row in r['records']))

    def test_understated_reserve_wrong_day_limit_or_direction_fails(self):
        for change in ('reserve','limit','quantity','direction'):
            with self.subTest(change=change):
                r=deepcopy(self.report);row=r['records'][0];order=row['cash_control']['orders'][0]
                if change=='reserve':row['cash_control']['reserved_buy_cost_cny']='1'
                if change=='limit':order['limit_price_cny']='19'
                if change=='quantity':order['quantity']+=100
                if change=='direction':order['action']='SELL'
                with self.assertRaises(ValueError):validate_report(r)


if __name__=='__main__':unittest.main(verbosity=2)
