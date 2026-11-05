"""原WT发布引用到App公开读取的诊断接续；全部观察/运行引用均为隔离夹具。"""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from guanheng_app.strategy_runtime_projection import project_strategy, _diagnostics
from guanheng_strategy_v1 import validate_diagnostics


ROOT = Path(__file__).resolve().parents[3]
IDENTITY = 'resonance-regime-v1'


def report():
    value = json.loads((ROOT / 'tests/integration/wt_observer/current-fixtures/strategy.json').read_bytes())
    fixture = ROOT / 'apps/guanheng/console/src/workspace/strategy-diagnostics.fixture.json'
    value['core_result']['diagnostics'] = json.loads(fixture.read_bytes())['diagnostics']
    return value


def project(value):
    return project_strategy(dict(schema='guanheng.configured-cta-observation.v1', strategies={IDENTITY: value}))


class RuntimeDiagnosticProjection(unittest.TestCase):
    def test_same_v1_diagnostic_preserves_role_gaps_and_only_contextualizes_execution(self):
        source = report()
        before = deepcopy(source)
        result = project(source)
        diagnostic = result['diagnostics']
        self.assertEqual((result['diagnostics_state'], result['diagnostics_reason']), ('available', None))
        validate_diagnostics(diagnostic, symbols=tuple(source['core_result']['targets']))
        self.assertEqual(diagnostic, dict(source['core_result']['diagnostics'], execution_state='pending'))
        self.assertEqual(diagnostic['roles']['510300.SH']['latest_missing_fields'],
                         ['share_probability', 'turnover_percentile', 'margin_percentile'])
        self.assertEqual(diagnostic['roles']['510300.SH']['branches']['resonance_lamps']['state'], 'unavailable')
        self.assertEqual(source, before)
        del source['core_result']['diagnostics']
        original = project(source)
        self.assertIsNone(original.pop('diagnostics'))
        self.assertEqual(original.pop('diagnostics_state'), 'absent')
        self.assertEqual(original.pop('diagnostics_reason'), 'not_recorded')
        result.pop('diagnostics')
        result.pop('diagnostics_state')
        result.pop('diagnostics_reason')
        self.assertEqual(result, original)  # 原资金、持仓、目标与时刻保持相同。

    def test_uncomputed_and_old_results_keep_unknown_instead_of_fabricating_zero_coverage(self):
        source = report()
        source['core_result'].pop('diagnostics')
        old = project(source)
        self.assertIsNone(old['diagnostics'])
        self.assertEqual((old['diagnostics_state'], old['diagnostics_reason']), ('absent', 'not_recorded'))
        source.update(status='waiting_market_input', core_result=None, outcome=None, target_readback=None)
        waiting = project(source)
        self.assertIsNone(waiting['decision_at'])
        self.assertIsNone(waiting['diagnostics'])
        self.assertEqual((waiting['diagnostics_state'], waiting['diagnostics_reason']), ('absent', 'not_calculated'))
        self.assertTrue(all(row['target_weight'] is None for row in waiting['positions']))

    def test_execution_semantics_reuse_original_outcome_and_return_independent_values(self):
        source = report()['core_result']
        symbols = tuple(source['targets'])
        for outcome, expected in ((None, 'not_requested'), ({'status': 'selling'}, 'pending'),
                                  ({'status': 'converged'}, 'completed')):
            projected, status, reason = _diagnostics(source, symbols, outcome)
            self.assertEqual(projected['execution_state'], expected)
            self.assertEqual((status, reason), ('available', None))
            projected['roles'].clear()
            self.assertEqual(len(source['diagnostics']['roles']), 8)

    def test_invalid_role_count_or_version_only_degrades_diagnostic_with_one_sanitized_warning(self):
        for change in (lambda value: value['roles'].pop('510300.SH'),
                       lambda value: value['roles']['510300.SH']['signal_counts'].update(BUY=-1),
                       lambda value: value.update(schema='unknown.diagnostic.v9')):
            source = report()
            expected = project(source)
            change(source['core_result']['diagnostics'])
            source['core_result']['diagnostics']['error_code'] = 'private-marker-not-for-logs'
            with self.assertLogs('guanheng_app.strategy_runtime_projection', level='WARNING') as captured:
                result = project(source)
            self.assertEqual(len(captured.output), 1)
            self.assertIn('strategy_diagnostics_unavailable', captured.output[0])
            self.assertNotIn('private-marker', captured.output[0])
            self.assertIsNone(result['diagnostics'])
            self.assertEqual((result['diagnostics_state'], result['diagnostics_reason']), ('unavailable', 'invalid_diagnostics'))
            for key in ('positions', 'capital_baseline', 'capital', 'status', 'decision_at'):
                self.assertEqual(result[key], expected[key])

    def test_original_public_routes_share_diagnostic_and_failed_refresh_recovers(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            control, instance, execution = str(uuid4()), str(uuid4()), str(uuid4())
            folder = root / execution
            folder.mkdir()
            identity = dict(control_id=execution, config_sha256='b'*64, pid=777)
            business = dict(schema='guanheng.execution-observation-reference.v1',
                            path=str(folder/'strategies.json'), ready_path=str(folder/'ready.json'), **identity)
            runtime = dict(schema='guanheng.wt-runtime-status.v1', control_id=control, instance_id=instance,
                           configuration_sha256='a'*64, pid=555, state='ready', ready=True,
                           components=dict(execution=dict(state='ready', ready=True, pending=True, forced=False,
                                                          pid=777, business_observation=business)))
            (root/'status.json').write_text(json.dumps(runtime), encoding='utf8')
            (folder/'ready.json').write_text(json.dumps(dict(schema='guanheng.execution.ready.v1', closed=False, **identity)), encoding='utf8')
            source = report()

            def publish():
                (folder/'strategies.json').write_text(json.dumps(dict(schema='guanheng.configured-cta-observation.v2',
                    strategies={IDENTITY: source}, **identity)), encoding='utf8')

            publish()
            settings = ConsoleSettings(wt_status_file=str(root/'status.json'), wt_control_id=control,
                                       wt_instance_id=instance, wt_configuration_sha256='a'*64)
            app = create_app(settings)
            with TestClient(app) as client:
                first = client.get('/v1/ui/strategy-runtime')
                self.assertEqual(first.status_code, 200)
                diagnostic = first.json()['strategy']['diagnostics']
                details = client.get('/v1/ui/strategy-details')
                self.assertEqual(details.status_code, 200)
                self.assertEqual(details.json()['calculation']['diagnostics'], diagnostic)
                # 附加诊断损坏只使该字段降级，两条原路由继续提供已核核心事实。
                source['core_result']['diagnostics']['roles']['510300.SH']['signal_counts']['BUY'] = -1
                publish()
                degraded = client.get('/v1/ui/strategy-runtime')
                self.assertEqual(degraded.status_code, 200)
                strategy = degraded.json()['strategy']
                self.assertIsNone(strategy['diagnostics'])
                self.assertEqual(strategy['diagnostics_state'], 'unavailable')
                self.assertEqual(strategy['positions'], first.json()['strategy']['positions'])
                degraded_details = client.get('/v1/ui/strategy-details')
                self.assertEqual(degraded_details.status_code, 200)
                self.assertEqual(degraded_details.json()['calculation']['diagnostics_state'], 'unavailable')
                source = report()
                publish()
                self.assertEqual(client.get('/v1/ui/strategy-runtime').json()['strategy']['diagnostics'], diagnostic)
                # 真正核心持仓损坏仍走原整份失败，不能被附加诊断降级吞掉。
                source['broker_observation']['positions'][0]['sellable'] = source['broker_observation']['positions'][0]['quantity'] + 1
                publish()
                self.assertEqual(client.get('/v1/ui/strategy-runtime').status_code, 503)
            self.assertTrue(app.state.shutdown_complete)
            self.assertEqual(app.state.reader.live_threads, 0)


if __name__ == '__main__':
    unittest.main()
