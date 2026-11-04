"""原目录完整性与价格用途分开；官方指数原值和身份的准入回归。"""
from copy import deepcopy
import unittest
from guanheng_qmt_shm_agent.security_price_roles import non_price_role,source_price_role
from integrations.guanheng.official_index_prices import parse_prices,parse_cni_prices


class PriceRoles(unittest.TestCase):
    def test_confirmed_type_and_effective_date_required(self):
        identity=dict(symbol='SSE.510303',security_type='etf')
        self.assertEqual(non_price_role(identity,'2026-11-03')['role'],'fund_subscription')
        self.assertIsNone(non_price_role(identity,'2026-05-21'))
        self.assertIsNone(non_price_role(dict(identity,security_type='unknown'),'2026-11-03'))
        self.assertIsNone(non_price_role(dict(identity,symbol='SSE.510300'),'2026-11-03'))
        self.assertEqual(non_price_role(dict(identity,symbol='SSE.510304'),'2026-11-03')['role'],'fund_subscription_cash')

    def test_source_seam_preserves_original_and_uses_same_rule(self):
        raw=dict(symbol='395001.SZ',market='SZ',security_type='index',source_groups=['深圳指数'])
        original=deepcopy(raw)
        result=source_price_role(raw,'2026-11-03')
        self.assertEqual(result['role'],'turnover_statistic')
        self.assertEqual(raw,original)
        self.assertIsNone(source_price_role(dict(raw,symbol='395010.SZ'),'2026-11-03'))
        self.assertIsNone(source_price_role(dict(raw,security_type='unknown'),'2026-11-03'))


class OfficialPrices(unittest.TestCase):
    def setUp(self):
        self.identity=dict(symbol='SSE.000925',name='基本面50',security_type='index')
        self.basic=dict(indexCode='000925',indexShortNameCn='基本面50',indexFullNameCn='中证锐联基本面50指数')
        self.row=dict(indexCode='000925',tradeDate='20261103',open=10.,high=12.,low=9.,close=11.,tradingVol=3.,tradingValue=4.)

    def parse(self,rows):
        return parse_prices(self.identity,self.basic,rows,'20261102','20261103')

    def test_original_six_values_preserved(self):
        self.assertEqual(self.parse([self.row])['data']['20261103'],dict(open=10.,high=12.,low=9.,close=11.,volume=3.,amount=4.))

    def test_close_only_is_missing_fields_and_never_synthesized(self):
        value=self.parse([dict(self.row,open=None,high=None,low=None)])
        self.assertEqual(value['unqualified_dates'],{'20261103':'source_fields_missing'})
        self.assertEqual(value['data'],{})

    def test_wrong_identity_and_name_rejected(self):
        self.assertEqual(parse_prices(dict(self.identity,name='其他指数'),self.basic,[self.row],'20261102','20261103')['reason'],'official_identity_unqualified')
        with self.assertRaises(ValueError):self.parse([dict(self.row,indexCode='399806')])

    def test_official_price_rows_can_independently_confirm_identity(self):
        row=dict(self.row,indexNameCn='基本面50',indexNameCnAll='中证锐联基本面50指数')
        self.assertEqual(parse_prices(self.identity,None,[row],'20261102','20261103')['reason'],'available')
        self.assertEqual(parse_prices(self.identity,None,[dict(row,indexNameCn='别的指数',indexNameCnAll='其他')],'20261102','20261103')['data'],{})

    def test_repeated_or_outside_dates_rejected(self):
        with self.assertRaises(ValueError):self.parse([self.row,self.row])
        with self.assertRaises(ValueError):self.parse([dict(self.row,tradeDate='20261104')])

    def test_zero_nan_and_inconsistent_ohlc_excluded(self):
        for change in (dict(close=0),dict(close=float('nan')),dict(low=15.),dict(tradingVol=-1)):
            self.assertEqual(self.parse([dict(self.row,**change)])['data'],{})

    def test_cni_timezone_columns_identity_and_original_values(self):
        identity=dict(symbol='SZSE.399379',name='国证基金',security_type='index')
        response=dict(indexCode='399379',indexName='国证基金',item=['timestamp','open','high','low','close','volume','amount'],
            data=[[1793635200000,8169.6876,8209.3572,8095.1905,8127.3445,279127692459,546876343839.66]])
        value=parse_cni_prices(identity,response,'20261103','20261103')
        self.assertEqual(value['data']['20261103']['close'],8127.3445)
        self.assertEqual(value['data']['20261103']['volume'],279127692459)
        self.assertEqual(parse_cni_prices(dict(identity,name='其他'),response,'20261103','20261103')['data'],{})
        response['data'][0][0]+=1000
        with self.assertRaises(ValueError):parse_cni_prices(identity,response,'20261103','20261103')
