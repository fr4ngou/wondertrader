"""冻结main003真实消费的读取回归；不求值信号，不运行交易owner。"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from guanheng_app.strategy_current_auxiliary_projection import project_current_auxiliary
from guanheng_app.strategy_runtime_projection import project_strategy

ROOT = Path(__file__).resolve().parents[3]
CURRENT = json.loads(Path(__file__).with_name('current-auxiliary.fixture.json').read_bytes())
SYMBOLS = tuple(CURRENT['available_fields'])


def report():
    value = json.loads((ROOT/'tests/integration/wt_observer/current-fixtures/strategy.json').read_bytes())
    value.update(status='observing', reason='analysis_only', outcome=None, target_readback=None)
    value['core_result']['decision_cutoff'] = CURRENT['decision_at']
    value['native_observation']['observed_at'] = CURRENT['decision_at']
    for mapping in (value['core_result']['targets'],):
        mapping['588030.SH'] = mapping.pop('589000.SH')
    for row in value['native_observation']['positions']:
        if row['symbol'] == '589000.SH':
            row['symbol'] = '588030.SH'
    value.pop('definition', None)
    value['core_result']['current_auxiliary'] = deepcopy(CURRENT)
    value['core_result']['diagnostics'] = json.loads((ROOT/'apps/guanheng/console/src/workspace/current-auxiliary.fixture.json').read_bytes())['strategy']['diagnostics']
    return value


def project(value):
    return project_strategy(dict(schema='guanheng.configured-cta-observation.v1', strategies={'resonance-regime-v1': value}))


class CurrentAuxiliaryProjection(unittest.TestCase):
    def test_real_seven_consumed_and_sixteen_available_preserve_original_value_identity(self):
        source = dict(decision_cutoff=CURRENT['decision_at'], current_auxiliary=deepcopy(CURRENT))
        before = deepcopy(source)
        value, state, reason = project_current_auxiliary(source, SYMBOLS)
        self.assertEqual((state, reason), ('available', None))
        self.assertEqual(sum(map(len, value['required_fields'].values())), 7)
        self.assertEqual(sum(map(len, value['available_fields'].values())), 16)
        self.assertEqual(value['consumed_fields'], CURRENT['consumed_fields'])
        self.assertEqual(sum(map(len, value['consumed_fields'].values())), 7)
        self.assertEqual(source, before)
        value['available_fields'].clear()
        self.assertEqual(source, before)

    def test_optional_bad_data_degrades_current_only_and_keeps_core_history(self):
        original = report()
        baseline = project(original)
        for mutate in (
            lambda v: v.update(schema='unknown'),
            lambda v: v.update(data_revision='f'*64),
            lambda v: v.update(decision_at='2099-01-01T00:00:00+00:00'),
            lambda v: v.update(historical_rows_unchanged=False),
            lambda v: v['consumed_fields']['510050.SH']['shares_delta_yi'].update(value=True),
            lambda v: v['consumed_fields']['510050.SH'].clear(),
            lambda v: v['available_fields']['510300.SH']['share_probability'].update(private_account='not-for-logs'),
            lambda v: v['historical_effective_fields'].pop('510050.SH'),
        ):
            bad = deepcopy(original)
            mutate(bad['core_result']['current_auxiliary'])
            with self.assertLogs('guanheng_app.strategy_current_auxiliary_projection', level='WARNING') as captured:
                value = project(bad)
            self.assertEqual(len(captured.output), 1)
            self.assertNotIn('not-for-logs', str(captured.output))
            self.assertEqual((value['current_auxiliary'], value['current_auxiliary_state'], value['current_auxiliary_reason']),
                             (None, 'unavailable', 'invalid_current_auxiliary'))
            for key in ('capital', 'capital_baseline', 'positions', 'status', 'decision_at', 'diagnostics'):
                self.assertEqual(value[key], baseline[key])

    def test_old_and_not_calculated_keep_absence_and_original_diagnostics(self):
        source = report()
        expected = project(source)
        del source['core_result']['current_auxiliary']
        old = project(source)
        self.assertEqual((old['current_auxiliary_state'], old['current_auxiliary_reason']), ('absent', 'not_recorded'))
        self.assertEqual(old['diagnostics'], expected['diagnostics'])
        self.assertEqual(project_current_auxiliary(None, SYMBOLS), (None, 'absent', 'not_calculated'))


if __name__ == '__main__':
    unittest.main()
