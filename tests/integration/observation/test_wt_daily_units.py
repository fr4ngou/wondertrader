"""未知量单位的日线价格准入与量指标资格分别回归。"""
from datetime import date,timedelta
from types import SimpleNamespace
from unittest.mock import patch
import hashlib,unittest
from guanheng_app.observation.wondertrader_source import history
from guanheng_app.observation import refresh_models as models
from guanheng_app.observation.source_fetch import SourceFailure


def fetch():
    return SimpleNamespace(timeout=20,records=[],objects=SimpleNamespace(put=lambda value:hashlib.sha256(value).hexdigest()),
        budget=SimpleNamespace(request=lambda:None,consume=lambda count:None,remaining=lambda:30))


def response(unit='unknown'):
    return dict(status=dict(code='Ok'),data=dict(metadata=dict(volume_unit=unit),bars=[dict(date=20261029,open=10.,high=12.,low=9.,close=11.,volume=123.,amount=456.)]))


class SourceUnitTests(unittest.TestCase):
    def test_unknown_preserves_readonly_ohlc_and_original_volume(self):
        for unit in ('unknown','share','lot'):
            client=SimpleNamespace(source_daily_history_query=lambda unused:response(unit))
            result=history(fetch(),dict(symbols=['sh000300']),'2026-10-01','2026-10-30',lambda seconds:client)
            row=result['market.sh000300'][0]
            self.assertEqual(row['open'],10.);self.assertEqual(row['provider_volume'],123.)
            self.assertEqual(row['provider_volume_unit'],unit)

    def test_changed_or_invalid_units_remain_rejected(self):
        for units,expected in ((iter(['unknown','share']),'market_volume_unit_changed'),(iter(['contracts']),'market_volume_unit_invalid')):
            client=SimpleNamespace(source_daily_history_query=lambda unused:response(next(units)))
            with self.assertRaises(SourceFailure) as raised:
                history(fetch(),dict(symbols=['sh000300']),'2023-01-01','2026-10-30',lambda seconds:client)
            self.assertEqual(raised.exception.code,expected)

    def comparison(self,unit,missing_base=False):
        days=[(date(2026,1,1)+timedelta(days=i)).isoformat() for i in range(31)]
        def rows(symbol):
            return [dict(date=day,close=10.+i,provider_volume=100.,**({'provider_volume_unit':unit(i) if callable(unit) else unit} if symbol=='cn' else {})) for i,day in enumerate(days)]
        tables={'market.sh000001':rows('cn'),'market.hkHSCEI':rows('hk')}
        datasets={'crossmarket.hk_a':[dict(date=day,a_activity=99.) for day in days]}
        definitions={'crossmarket.hk_a':dict(lines=[])}
        with patch.object(models,'comparison_calendars',return_value=(dict(cn=set(days),hk=set(days)),{})):
            models.comparison_model(tables,datasets,definitions,dict(base_date='2020-01-01' if missing_base else days[0]))
        return datasets['crossmarket.hk_a']

    def test_unknown_only_disables_volume_activity(self):
        rows=self.comparison('unknown')
        self.assertEqual(rows[-1]['a_close'],40.)
        self.assertEqual(rows[-1]['a_rebased'],400.)
        self.assertTrue(all(r['a_activity'] is None for r in rows))
        self.assertEqual(rows[-1]['hscei_activity'],1.)
        self.assertEqual(self.comparison('lot')[-1]['a_activity'],1.)

    def test_unknown_clears_preceding_activity_even_when_rebase_is_unavailable(self):
        self.assertTrue(all(r['a_activity'] is None for r in self.comparison('unknown',missing_base=True)))

    def test_unit_transition_restarts_twenty_observation_warmup(self):
        rows=self.comparison(lambda i:'share' if i<=20 else 'lot')
        self.assertEqual(rows[20]['a_activity'],1.)
        self.assertTrue(all(r['a_activity'] is None for r in rows[21:]))
        self.assertEqual(self.comparison(None)[-1]['a_activity'],1.)

    def test_unit_transition_clears_stale_activity_without_rebase_date(self):
        rows=self.comparison(lambda i:'share' if i<=20 else 'lot',missing_base=True)
        self.assertEqual(rows[20]['a_activity'],1.)
        self.assertTrue(all(r['a_activity'] is None for r in rows[21:]))
        self.assertEqual(rows[-1]['a_close'],40.)
        self.assertEqual(rows[-1]['a_provider_volume'],100.)
        self.assertEqual(self.comparison(None,missing_base=True)[-1]['a_activity'],1.)

    def test_cffex_and_basis_reference_are_final_after_one_pass_and_idempotent(self):
        import copy
        tables={'market.sh000001':[dict(date='2026-10-29',close=4001.)]}
        datasets={}
        for product in ('if','ih','ic','im'):
            datasets['cffex_'+product]=[dict(date='2026-10-29',front_close=4050.,front_contract=product+'2611',sse_reference=3900.)]
        definitions={}
        models.market_models(tables,datasets,definitions,{},'2026-10-29')
        models.attach_sse_reference(tables,datasets)
        first=copy.deepcopy(datasets)
        for product in ('if','ih','ic','im'):
            self.assertEqual(datasets['cffex_'+product][0]['sse_reference'],4001.)
            self.assertEqual(datasets['basis_'+product][0]['sse_reference'],4001.)
            self.assertEqual(datasets['basis_'+product][0]['front_close'],4050.)
        models.market_models(tables,datasets,definitions,{},'2026-10-29')
        models.attach_sse_reference(tables,datasets)
        self.assertEqual(datasets,first)


if __name__=='__main__':unittest.main()
