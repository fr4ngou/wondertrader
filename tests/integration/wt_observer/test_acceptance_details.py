"""OAR实际HTTP接缝回归；金融事实fixture与真实部署验收分别登记。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from time import monotonic
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'apps/guanheng'))
from fastapi.testclient import TestClient
from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings


class DetailsAcceptance(unittest.TestCase):
    def test_strategy_details_without_execution_keep_display_identity_and_unknown_version(self):
        with TestClient(create_app(ConsoleSettings())) as client:
            response = client.get('/v1/ui/strategy-details')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['strategy']['strategy_id'], 'resonance-regime-v1')
            self.assertTrue(data['strategy']['display_name'])
            self.assertIsNone(data['strategy']['strategy_version'])
            self.assertEqual(data['execution']['state'], 'unconfigured')
            self.assertIsNone(data['returns']['cumulative_pct']['value'])
            self.assertTrue(data['returns']['cumulative_pct']['reason'])

    def test_archive_configuration_is_a_readable_empty_state(self):
        with TestClient(create_app(ConsoleSettings())) as client:
            response = client.get('/v1/ui/backtest/source')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['state'], 'unconfigured')

    def test_current_inventory_keeps_broker_fields_without_execution(self):
        from guanheng_app.observer_strategy_details import observe_details
        fixture = json.loads((ROOT/'apps/guanheng/console/src/workspace/account-v2.fixture.json').read_bytes())
        # 四条当前持仓；明确不同数量/可卖/市值，防止字段混用或归零。
        row = fixture['groups']['position']['rows'][0]
        fixture['groups']['position']['rows'] = [json.loads(json.dumps(row)) for _ in range(4)]
        for index, item in enumerate(fixture['groups']['position']['rows']):
            item['identity']['m_strInstrumentID'] = f'5100{index}0'
            for name, amount in (('quantity', 1200+index), ('sellable', 800+index), ('market_value', 9800+index)):
                item['fields'][name] = dict(availability='present', value=amount, reason=None)
        account = SimpleNamespace(model_dump=lambda **_: fixture)
        runtime = SimpleNamespace(value=dict(state='ready', components={'account_observation':{}}))
        settings = ConsoleSettings(account_source='wt_account_publication')
        with patch('guanheng_app.observer_strategy_details.read_runtime_snapshot', return_value=runtime), \
             patch('guanheng_app.account_publication.observe_published_account', return_value=account):
            securities = SimpleNamespace(available=True, name=lambda symbol: {'510000.SH': '测试ETF'}.get(symbol))
            value = observe_details(settings, object(), monotonic()+2, securities=securities)
        self.assertEqual(value['security_names'], {'510000.SH': '测试ETF'})
        self.assertEqual(value['execution']['state'], 'not_started')
        self.assertEqual(value['account'], fixture)
        self.assertIsNone(value['budget_cny']['value'])
        self.assertIsNone(value['execution']['started_at']['value'])
        self.assertIsNone(value['returns']['cumulative_pct']['value'])

    def test_current_account_failure_does_not_hide_stopped_execution(self):
        from guanheng_app.observer_strategy_details import observe_details
        runtime=SimpleNamespace(value=dict(state='closed',components={'execution':dict(state='ready')}))
        with patch('guanheng_app.observer_strategy_details.read_runtime_snapshot',return_value=runtime), \
             patch('guanheng_app.wt_business_observation.observe_account',side_effect=ValueError('private account info')), \
             patch('guanheng_app.wt_business_observation.read_business',side_effect=ValueError('private runtime info')):
            value=observe_details(ConsoleSettings(),object(),monotonic()+2)
        self.assertEqual(value['execution']['state'],'closed')
        self.assertIsNone(value['account'])
        self.assertNotIn('private',json.dumps(value))

    def test_archive_empty_invalid_path_and_bad_receipt_have_distinct_states(self):
        with tempfile.TemporaryDirectory() as folder:
            for root,expected in ((folder,'empty'),(folder+'/missing','invalid_path')):
                with TestClient(create_app(ConsoleSettings(backtest_archive_root=root))) as client:
                    response=client.get('/v1/ui/backtest/source')
                    self.assertEqual(response.json()['state'],expected)
            run=Path(folder)/('a'*32);run.mkdir();(run/'completed-archive.json').write_text('{}')
            with TestClient(create_app(ConsoleSettings(backtest_archive_root=folder))) as client:
                response=client.get('/v1/ui/backtest/source')
                self.assertEqual(response.json()['state'],'invalid_archive')

    def test_instance_failure_is_local_and_private_id_stays_hidden(self):
        from guanheng_app.observer_strategy_details import observe_instances
        first=SimpleNamespace(instance_id='account-instance')
        second=SimpleNamespace(instance_id='market-instance')
        values=[OSError('private path'),dict(state='available',reason='原发布',published_at='2026-11-01T00:00:00Z',runtime=dict(components=[dict(name='history')]))]
        with patch('guanheng_app.observer_strategy_details.observe_runtime',side_effect=values):
            value=observe_instances([('账户',first),('行情',second)],monotonic()+2)
        self.assertEqual([x['state'] for x in value['instances']],['unavailable','available'])
        self.assertEqual(value['instances'][1]['runtime']['components'][0]['name'],'history')
        self.assertNotIn('private',json.dumps(value))
        self.assertNotIn('market-instance',json.dumps(value))

    def test_invalid_extra_catalog_keeps_primary_instance_readable(self):
        with patch.dict('os.environ',{'GUANHENG_WT_INSTANCE_CATALOG':'relative.json'}):
            with TestClient(create_app(ConsoleSettings())) as client:
                response=client.get('/v1/ui/wt-instances')
                self.assertEqual(response.status_code,200)
                self.assertEqual(len(response.json()['instances']),1)
                self.assertIn('catalog_reason',response.json())
                self.assertEqual(client.post('/v1/ui/wt-instances').status_code,405)
                self.assertEqual(client.post('/v1/ui/strategy-details').status_code,405)
                self.assertEqual(client.get('/v1/ui/strategy-details?extra=1').status_code,422)


if __name__ == '__main__':
    unittest.main()
