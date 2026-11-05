"""完整纯核、角色诊断与研究隔离；在普通安装的候选解释器中运行。"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import unittest

from guanheng_strategy_core.contracts import canonical_bytes
from guanheng_strategy_core.models import observation_close_at
from guanheng_strategy_v1 import (
    RetainedInput, RetainedHistoricalModel, RetainedValidationError, evaluate_current_view,
    evaluate_historical_model, contextualize_diagnostics, validate_diagnostics,
)
from guanheng_strategy_v1.historical import AUXILIARY_RESEARCH_MARKER, AuxiliaryResearchDeclaration
from guanheng_strategy_v1.role_profile import KC_SYMBOL, SYMBOLS

ROOT = Path(__file__).resolve().parents[3]
AUXILIARY = ('shares_delta_yi', 'share_probability', 'turnover_percentile', 'margin_percentile')


def sample():
    value = json.loads((ROOT/'apps/guanheng/strategy_v1/examples/INPUT.json').read_text('utf8').replace('589000.SH', KC_SYMBOL))
    raw = value['cases'][0]['request']
    raw['cycles'] = [dict(symbol=s, status='flat', quantity=0, source_sha256='1'*64) for s in SYMBOLS]
    return RetainedInput.from_dict(raw)


def history_model(request):
    return RetainedHistoricalModel(request.history.source_revision, request.history.factor_revision,
                                  request.analysis.basis_date, request.current_view.received_at)


def historical_request(request):
    cutoff = datetime.fromisoformat(request.analysis.basis_date.isoformat()+'T15:00:00+08:00')
    return replace(request, decision_cutoff=cutoff, cycles_captured_at=cutoff,
                   cycles_valid_until=cutoff+timedelta(seconds=1))


def transform_rows(request, change):
    return replace(request, history=replace(request.history, observations=tuple(change(r) for r in request.history.observations)),
        analysis=replace(request.analysis, bars=tuple(replace(b, observation=change(b.observation)) for b in request.analysis.bars)))


def declaration(request):
    value = dict(schema='guanheng.auxiliary-research-declaration.v1',
        model='research-next-common-session-0925-v1', evidence_marker=AUXILIARY_RESEARCH_MARKER,
        data_sha256='a'*64, derivation='resonance-auxiliary-causal-v3', derivation_sha256='b'*64,
        strategy_id='resonance-regime-v1', strategy_version='1.2.2', publications_sha256='c'*64,
        actual_first_received_at=request.current_view.received_at.isoformat(),
        actual_last_received_at=request.current_view.received_at.isoformat(),
        historical_first_available='unknown', modeled_publications=600,
        historical_causal_qualified=False, realtime_qualified=False)
    value['declaration_sha256'] = sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',',':')).encode('utf8')).hexdigest()
    return value


class CompleteKernelDiagnostics(unittest.TestCase):
    def test_current_and_historical_actual_role_universe(self):
        request = sample()
        current = evaluate_current_view(request).to_dict()
        historical = evaluate_historical_model(historical_request(request), history_model(request)).to_dict()
        self.assertEqual(set(current['targets']), set(SYMBOLS))
        self.assertIn('588030.SH', current['targets'])
        self.assertEqual(current['targets'], historical['targets'])
        self.assertEqual(current['diagnostics'], historical['diagnostics'])
        validate_diagnostics(current['diagnostics'], symbols=SYMBOLS)

    def test_missing_fields_are_role_and_branch_specific(self):
        request = transform_rows(sample(), lambda r: replace(r, **dict.fromkeys(AUXILIARY)))
        value = evaluate_current_view(request).to_dict()
        diagnostic = value['diagnostics']
        self.assertEqual(diagnostic['calculation_state'], 'completed')
        roles = diagnostic['roles']
        for symbol in ('510300.SH', '510050.SH', '588000.SH'):
            self.assertEqual(roles[symbol]['signal_counts'], {'BUY': 0, 'SELL': 0})
            self.assertEqual(roles[symbol]['input_state'], 'input_missing')
        self.assertEqual(roles['159780.SZ']['auxiliary_fields'], [])
        self.assertEqual(roles['159780.SZ']['input_state'], 'ready')
        self.assertEqual(roles['588000.SH']['branches']['large_subscription_exemption']['state'], 'unavailable')
        self.assertNotIn('trailing_exit', roles['588000.SH']['branches'])
        self.assertEqual(roles['510300.SH']['field_coverage']['share_probability']['input']['non_null_count'], 0)
        validate_diagnostics(diagnostic, symbols=SYMBOLS)

    def test_zero_is_a_value_and_one_missing_lamp_is_partial(self):
        # 显式带来源的合成零变动，及一盏未知/两盏已有辅助灯；不替现场缺值填零。
        request = transform_rows(sample(), lambda r: replace(r, shares_delta_yi=0,
            share_probability=None if r.symbol == '510300.SH' else r.share_probability,
            turnover_percentile=45 if r.symbol == '510300.SH' else r.turnover_percentile,
            margin_percentile=55 if r.symbol == '510300.SH' else r.margin_percentile,
            auxiliary_available_at=observation_close_at(r.trade_date), auxiliary_source_dates=(r.trade_date,),
            auxiliary_source_sha256='7'*64))
        value = evaluate_current_view(request).to_dict()['diagnostics']
        zero = value['roles']['588000.SH']['field_coverage']['shares_delta_yi']['input']
        self.assertEqual(zero['non_null_count'], sum(r.symbol == '588000.SH' and r.shares_delta_yi is not None
            for r in request.history.observations))
        self.assertGreater(zero['non_null_count'], 0)
        self.assertEqual(value['roles']['510300.SH']['branches']['resonance_lamps']['state'], 'partially_observed')

    def test_full_input_and_evaluation_denominators_are_distinct(self):
        diagnostic = evaluate_current_view(sample()).to_dict()['diagnostics']
        self.assertGreater(diagnostic['input_range']['expected_dates'], diagnostic['evaluation_range']['expected_dates'])
        for role in diagnostic['roles'].values():
            field = role['field_coverage']['close']
            self.assertEqual(field['input']['expected_count'], diagnostic['input_range']['expected_dates'])
            self.assertEqual(field['evaluation']['expected_count'], diagnostic['evaluation_range']['expected_dates'])

    def test_target_unchanged_and_execution_failed_do_not_change_kernel(self):
        value = evaluate_current_view(sample()).to_dict()
        original = deepcopy(value['diagnostics'])
        projection = contextualize_diagnostics(original, targets=value['targets'],
            previous_targets=value['targets'], execution_state='failed')
        self.assertEqual(projection['target_state'], 'unchanged')
        self.assertEqual(projection['execution_state'], 'failed')
        projection['roles']['510300.SH']['latest_missing_fields'].append('test')
        self.assertEqual(original, value['diagnostics'])

    def test_short_valid_window_is_warmup_not_calculation_failure(self):
        request = sample()
        days = sorted({r.trade_date for r in request.history.observations})[:99]
        request = replace(request, history=replace(request.history, observations=tuple(
            r for r in request.history.observations if r.trade_date in days)),
            analysis=replace(request.analysis, basis_date=days[-1], bars=tuple(
                b for b in request.analysis.bars if b.observation.trade_date in days)))
        with self.assertRaises(RetainedValidationError) as caught:
            evaluate_current_view(request)
        self.assertEqual(caught.exception.code, 'warmup_required')
        self.assertEqual(caught.exception.diagnostics['calculation_state'], 'warming_up')
        validate_diagnostics(caught.exception.diagnostics, symbols=SYMBOLS)

    def test_bad_market_input_is_rejected_before_warmup_label(self):
        request = sample()
        days = sorted({r.trade_date for r in request.history.observations})[:99]
        request = replace(request, history=replace(request.history, observations=tuple(
            r for r in request.history.observations if r.trade_date in days)),
            analysis=replace(request.analysis, basis_date=days[-1], bars=tuple(
                b for b in request.analysis.bars if b.observation.trade_date in days)))
        request = transform_rows(request, lambda r: replace(r, high=r.low))
        with self.assertRaises(RetainedValidationError) as caught:
            evaluate_current_view(request)
        self.assertEqual(caught.exception.diagnostics['calculation_state'], 'input_rejected')

    def test_diagnostic_poison_rejected(self):
        original = evaluate_current_view(sample()).to_dict()['diagnostics']
        for change in (lambda d: d['roles']['510300.SH'].update(role='sc50'),
                       lambda d: d['roles']['510300.SH']['signal_counts'].update(BUY=-1),
                       lambda d: d['roles']['510300.SH']['field_coverage']['close']['input'].update(expected_count=1),
                       lambda d: d['roles']['510300.SH'].update(unbounded_private_configuration='hidden')):
            value = deepcopy(original);change(value)
            with self.assertRaises(ValueError):
                validate_diagnostics(value, symbols=SYMBOLS)


class ExplicitResearchModel(unittest.TestCase):
    def setUp(self):
        self.request = transform_rows(sample(), lambda r: replace(r,
            evidence_refs=tuple(r.evidence_refs)+(AUXILIARY_RESEARCH_MARKER,)))
        self.model = history_model(self.request).with_auxiliary_research(self.request.history, declaration(self.request))

    def test_research_realtime_rejected_historical_explicitly_accepted(self):
        with self.assertRaises(RetainedValidationError) as caught:
            evaluate_current_view(self.request)
        self.assertEqual(caught.exception.code, 'research_input_forbidden')
        result = evaluate_historical_model(historical_request(self.request), self.model).to_dict()
        self.assertEqual(result['diagnostics']['auxiliary_availability_model'], 'research-next-common-session-0925-v1')
        self.assertFalse(result['historical_model']['auxiliary_research']['realtime_qualified'])

    def test_research_requires_matching_declaration_and_complete_input_digest(self):
        request = historical_request(self.request)
        with self.assertRaises(RetainedValidationError) as caught:
            evaluate_historical_model(request, history_model(self.request))
        self.assertEqual(caught.exception.code, 'research_model_required')
        with self.assertRaises(RetainedValidationError) as caught:
            evaluate_historical_model(request, replace(self.model, auxiliary_input_sha256='f'*64))
        self.assertEqual(caught.exception.code, 'research_input_mismatch')

    def test_research_marker_cannot_be_stripped_from_one_row(self):
        first = self.request.history.observations[0]
        request = transform_rows(self.request, lambda r: replace(r,evidence_refs=())
            if (r.symbol,r.trade_date) == (first.symbol,first.trade_date) else r)
        model = history_model(request).with_auxiliary_research(request.history, declaration(request))
        with self.assertRaises(RetainedValidationError) as caught:
            evaluate_historical_model(historical_request(request), model)
        self.assertEqual(caught.exception.code, 'research_input_mismatch')

    def test_default_historical_model_keeps_old_wire_identity(self):
        model = history_model(sample())
        wire = json.loads(canonical_bytes(model))
        self.assertNotIn('auxiliary_research', wire)
        self.assertNotIn('auxiliary_input_sha256', wire)
        self.assertEqual(RetainedHistoricalModel.from_dict(wire), model)
        wire['auxiliary_research'] = declaration(sample())
        wire['auxiliary_research']['realtime_qualified'] = True
        with self.assertRaises(ValueError):
            RetainedHistoricalModel.from_dict(wire)


if __name__ == '__main__':
    unittest.main()
