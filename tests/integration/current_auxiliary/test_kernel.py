"""当前辅助消费的时间、历史隔离和同bar幂等根因回归。"""
from copy import deepcopy
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
import json
from pathlib import Path
import unittest

from guanheng_strategy_core.contracts import canonical_bytes
from guanheng_strategy_v1 import (RetainedInput,RetainedHistoricalModel,RetainedValidationError,
    evaluate_current_view,evaluate_historical_model,CurrentAuxiliaryValue,CurrentAuxiliaryView,CycleExit)
from guanheng_strategy_v1.auxiliary import DERIVATION_VERSION
from guanheng_strategy_v1.role_profile import KC_SYMBOL,SYMBOLS

ROOT=Path(__file__).resolve().parents[3]

def sample():
    value=json.loads((ROOT/'apps/guanheng/strategy_v1/examples/INPUT.json').read_text(encoding='utf8').replace('589000.SH',KC_SYMBOL))['cases'][0]['request']
    value['cycles']=[dict(symbol=s,status='flat',quantity=0,source_sha256='1'*64)for s in SYMBOLS]
    return RetainedInput.from_dict(value)

def view(request, *, changes=None):
    day=request.analysis.basis_date
    dates=sorted({r.trade_date for r in request.history.observations})
    known=observation_time(day)+timedelta(hours=1)
    items=[]
    for symbol,field,value in [('588000.SH','shares_delta_yi',20.),('510300.SH','share_probability',95.),
                              ('510300.SH','turnover_percentile',2.5),('510300.SH','margin_percentile',2.5)]:
        items.append(CurrentAuxiliaryValue(symbol,field,value,day,known,
            tuple(dates[-2:] if field in ('shares_delta_yi','share_probability') else dates[-20:]),('3'*64,)))
    if changes:items=changes(items)
    return CurrentAuxiliaryView(day,DERIVATION_VERSION,tuple(sorted(items,key=lambda x:(x.symbol,x.field))))

def observation_time(day):
    return datetime.fromisoformat(day.isoformat()+'T15:00:00+08:00')

def current_request():
    request=sample();cutoff=observation_time(request.analysis.basis_date)+timedelta(days=1)
    return replace(request,decision_cutoff=cutoff,cycles_captured_at=cutoff,cycles_valid_until=cutoff+timedelta(minutes=5))

def panic_current_request():
    # 显式合成输入只修改夹具已有末帧，不创建当日/未来bar；原价和分析价配对保持。
    request=current_request();basis=request.analysis.basis_date
    def market(row):
        return replace(row,open=90.,high=91.,low=89.,close=90.,volume=5000.) if row.symbol=='588000.SH' and row.trade_date==basis else row
    history=replace(request.history,observations=tuple(market(r)for r in request.history.observations))
    analysis=replace(request.analysis,bars=tuple(replace(b,observation=market(b.observation),raw_close=90.,factor=1.)
        if b.observation.symbol=='588000.SH' and b.observation.trade_date==basis else b for b in request.analysis.bars))
    return replace(request,history=history,analysis=analysis)


class CurrentAuxiliaryKernel(unittest.TestCase):
    def test_complete_projection_preserves_history_and_legacy_wire(self):
        old=current_request();before=canonical_bytes(old.history)
        self.assertNotIn('current_auxiliary',json.loads(canonical_bytes(old)))
        baseline=evaluate_current_view(old).to_dict()
        current=replace(old,current_auxiliary=view(old));encoded=canonical_bytes(current)
        restored=RetainedInput.from_dict(json.loads(encoded));self.assertEqual(restored,current)
        result=evaluate_current_view(restored).to_dict()
        self.assertEqual(canonical_bytes(current.history),before)
        self.assertEqual(result['historical_model_state']['model_decisions'],baseline['model_decisions'])
        self.assertEqual(result['historical_model_state']['model_states'],baseline['model_states'])
        self.assertEqual(result['historical_model_state']['allocation_state'],baseline['allocation_state'])
        self.assertEqual(result['diagnostics'],baseline['diagnostics'])
        self.assertEqual(result['current_auxiliary']['consumed_fields']['588000.SH']['shares_delta_yi']['value'],20.)

    def test_true_knowledge_cutoff_and_basis_are_required(self):
        request=current_request();facts=view(request);known=max(v.known_by for v in facts.values)
        facts.qualify(request.analysis.basis_date,known)
        with self.assertRaises(ValueError):facts.qualify(request.analysis.basis_date,known-timedelta(microseconds=1))
        with self.assertRaises(ValueError):facts.qualify(request.analysis.basis_date-timedelta(days=1),known)
        bad=replace(request,current_auxiliary=facts,decision_cutoff=known-timedelta(microseconds=1),
                    cycles_captured_at=known-timedelta(minutes=1),cycles_valid_until=known+timedelta(minutes=1))
        with self.assertRaises(RetainedValidationError)as error:evaluate_current_view(bad)
        self.assertEqual(error.exception.code,'invalid_current_auxiliary')

    def test_historical_models_do_not_accept_current_facts(self):
        request=sample();cutoff=observation_time(request.analysis.basis_date)
        model=RetainedHistoricalModel(request.history.source_revision,request.history.factor_revision,
            request.analysis.basis_date,request.current_view.received_at)
        request=replace(request,current_auxiliary=view(request),decision_cutoff=cutoff,
            cycles_captured_at=cutoff,cycles_valid_until=cutoff+timedelta(seconds=1))
        with self.assertRaises(RetainedValidationError)as error:evaluate_historical_model(request,model)
        self.assertEqual(error.exception.code,'current_auxiliary_forbidden')

    def test_polling_and_restoration_do_not_repeat_terminal_state(self):
        request=current_request();request=replace(request,current_auxiliary=view(request))
        first=evaluate_current_view(request).to_dict()
        restored=RetainedInput.from_dict(json.loads(canonical_bytes(request)))
        repeated=evaluate_current_view(replace(restored,decision_cutoff=request.decision_cutoff+timedelta(seconds=1))).to_dict()
        for key in ('targets','model_states','model_decisions','allocation_state','holding_days','reference_prices','next_exits','source_allocation_date'):
            self.assertEqual(first[key],repeated[key],key)
        self.assertEqual(first['current_auxiliary']['data_revision'],repeated['current_auxiliary']['data_revision'])

    def test_actual_cycle_indexes_and_ages_keep_full_market_prefix(self):
        request=current_request();first_day=min(r.trade_date for r in request.history.observations)
        cycles=tuple(replace(c,status='initial_inventory',quantity=100,cycle_id='same-'+c.symbol,baseline_at=observation_time(first_day))for c in request.cycles)
        request=replace(request,cycles=cycles)
        baseline=evaluate_current_view(request).to_dict()
        projected=evaluate_current_view(replace(request,current_auxiliary=view(request))).to_dict()
        self.assertEqual(projected['holding_days'],baseline['holding_days'])
        self.assertEqual(projected['reference_prices'],baseline['reference_prices'])
        self.assertEqual(request.cycles,cycles)

    def test_first_effective_frame_is_not_forward_filled(self):
        request=current_request();days=sorted({r.trade_date for r in request.history.observations})
        item=next(v for v in view(request).values if v.field=='shares_delta_yi')
        old=replace(item,statistic_date=days[-2],source_dates=tuple(days[-3:-1]),known_by=observation_time(days[-2]))
        old_view=CurrentAuxiliaryView(days[-1],DERIVATION_VERSION,(old,))
        self.assertEqual(old_view.projected_values(days),())
        at_basis=replace(item,known_by=observation_time(days[-1]))
        self.assertEqual(CurrentAuxiliaryView(days[-1],DERIVATION_VERSION,(at_basis,)).projected_values(days),(at_basis,))
        after_basis=replace(item,known_by=observation_time(days[-1])+timedelta(microseconds=1))
        self.assertEqual(CurrentAuxiliaryView(days[-1],DERIVATION_VERSION,(after_basis,)).projected_values(days),(after_basis,))
        baseline=evaluate_current_view(request).to_dict()
        repeated=evaluate_current_view(replace(request,current_auxiliary=old_view)).to_dict()
        self.assertEqual(repeated['targets'],baseline['targets'])
        self.assertEqual(repeated['model_states'],baseline['model_states'])
        self.assertFalse(repeated['current_auxiliary']['consumed_fields']['588000.SH'])
        self.assertIn('shares_delta_yi',repeated['current_auxiliary']['historical_effective_fields']['588000.SH'])

    def test_new_current_buy_keeps_actual_market_basis_date(self):
        request=panic_current_request();baseline=evaluate_current_view(request).to_dict()
        request=replace(request,current_auxiliary=view(request))
        result=evaluate_current_view(request).to_dict();basis=request.analysis.basis_date.isoformat()
        historical=[d for d in baseline['model_decisions']['588000.SH']if d['trade_date']==basis]
        self.assertFalse(historical)
        current=result['model_decisions']['588000.SH'][-1]
        self.assertEqual((current['action'],current['trade_date']),('BUY',basis))
        self.assertEqual(result['source_allocation_date'],basis)
        self.assertEqual(result['current_auxiliary']['market_basis_date'],basis)
        actual=datetime.fromisoformat(result['current_auxiliary']['decision_at']).astimezone(timezone(timedelta(hours=8))).date()
        self.assertGreater(actual,request.analysis.basis_date)
        self.assertEqual(result['historical_model_state']['model_decisions'],baseline['model_decisions'])

    def test_same_basis_exit_blocks_new_buy_until_next_actual_basis(self):
        request=panic_current_request();request=replace(request,current_auxiliary=view(request))
        basis=request.analysis.basis_date;days=sorted({r.trade_date for r in request.history.observations})
        same=CycleExit('588000.SH','original-cycle',basis,'same_basis_exit')
        blocked=evaluate_current_view(replace(request,previous_exits=(same,))).to_dict()
        self.assertEqual(blocked['model_decisions']['588000.SH'][-1]['action'],'BUY')
        self.assertEqual(blocked['targets']['588000.SH'],0)
        self.assertEqual(blocked['exit_paths']['588000.SH'],'same_basis_exit')
        self.assertEqual(blocked['next_exits'][0]['trade_date'],basis.isoformat())
        # 使用同一真实输入中已有的更早帧作为退出日；当前basis已经真实前进才允许原fresh分支。
        prior=replace(same,trade_date=days[-2])
        fresh=evaluate_current_view(replace(request,previous_exits=(prior,))).to_dict()
        self.assertNotIn('588000.SH',fresh['exit_paths'])
        self.assertFalse(fresh['next_exits'])
        self.assertGreater(fresh['targets']['588000.SH'],0)
        self.assertTrue(all(c.status=='flat' and c.quantity==0 for c in request.cycles))

    def test_bad_identity_unknown_field_and_noncausal_source_are_rejected(self):
        facts=view(current_request());wire=facts.to_dict();wire['sha256']='0'*64
        with self.assertRaises(ValueError):CurrentAuxiliaryView.from_dict(wire)
        wire=facts.to_dict();wire['values'][0]['source_dates']=['invalid']*65
        with self.assertRaises(ValueError):CurrentAuxiliaryView.from_dict(wire)
        wire=facts.to_dict();wire['values'][0]['known_by']='x'*65
        with self.assertRaises(ValueError):CurrentAuxiliaryView.from_dict(wire)
        wire=facts.to_dict();wire['values'][0]['field']='invented'
        with self.assertRaises(ValueError):CurrentAuxiliaryView.from_dict(wire)
        with self.assertRaises(ValueError):replace(facts,values=(replace(facts.values[0],value=float('nan')),))
        with self.assertRaises(ValueError):replace(facts,values=(replace(facts.values[0],known_by=datetime(1900,1,1,tzinfo=timezone.utc)),))
        share = next(v for v in facts.values if v.field == 'shares_delta_yi')
        percentile = next(v for v in facts.values if v.field == 'turnover_percentile')
        with self.assertRaises(ValueError):replace(facts,values=(replace(share,source_dates=(share.statistic_date,)),))
        with self.assertRaises(ValueError):replace(facts,values=(replace(percentile,source_dates=percentile.source_dates[-2:]),))
        days=sorted({r.trade_date for r in current_request().history.observations})
        gap=replace(share,source_dates=(days[-3],days[-1]))
        with self.assertRaises(ValueError):CurrentAuxiliaryView(facts.basis_date,facts.derivation_version,(gap,)).qualify(
            facts.basis_date,current_request().decision_cutoff,days)

if __name__=='__main__':unittest.main()
