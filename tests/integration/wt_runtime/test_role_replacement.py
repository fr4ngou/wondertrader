"""同账零角色换代主链：原NSQ退役、七周期保留、新基金按自身实际成交开仓。"""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from guanheng_wt_runtime.execution_configured import (RetainedRuntimeInput, RetainedStrategy,
                                                     _retained_seed_identity)
from guanheng_wt_runtime.execution_strategy import CtaBridgeError
from guanheng_wt_runtime.execution_role_replacement import (role_origin_configuration, validate_inputs,
                                                          OLD_SYMBOL, NEW_SYMBOL, NEW_CODE)
from guanheng_strategy_core.contracts import canonical_bytes
from guanheng_strategy_native import (Basis, EconomicTarget, NativePosition, Observation, Price,
                                     QuantityPolicy, Weight, advance)
from guanheng_strategy_v1 import SYMBOLS, ALGORITHM_ID, RetainedConfig


class RoleReplacementTests(unittest.TestCase):
    def test_recovery_seed_preserves_original_cycle_clock_without_deciding(self):
        from guanheng_strategy_core.contracts import EvaluationBudget
        request = SimpleNamespace(configuration=RetainedConfig('synthetic-new-role',.8),
            cycles_captured_at='2026-11-04T09:13:01.119030+00:00',
            cycles_valid_until='2026-11-04T09:17:01.119030+00:00')
        inputs = RetainedRuntimeInput(request,QuantityPolicy('1000000','synthetic'),None,None,'synthetic')
        original = dict(vars(request))
        with patch('guanheng_wt_runtime.retained_evaluation.evaluate_retained',
                   side_effect=AssertionError('synthetic-old-seed-must-not-decide')) as evaluate:
            for recovery in ('resume_clean','resume_reconciled'):
                identity = _retained_seed_identity(inputs,recovery,budget=EvaluationBudget())
                self.assertEqual(identity,(sha256(canonical_bytes(request.configuration)).hexdigest(),ALGORITHM_ID))
            evaluate.assert_not_called()
            with self.assertRaisesRegex(AssertionError,'synthetic-old-seed'):
                _retained_seed_identity(inputs,'record_clean',budget=EvaluationBudget())
            evaluate.assert_called_once()
        self.assertEqual(vars(request),original)

    def test_explicit_same_ledger_input_and_filter_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root/'app'
            app.mkdir()
            def save(path,value):
                raw = json.dumps(value,sort_keys=True,separators=(',',':')).encode()
                path.write_bytes(raw)
                return sha256(raw).hexdigest()
            old_symbols = tuple(sorted((set(SYMBOLS)-{NEW_SYMBOL})|{OLD_SYMBOL}))
            config = asdict(RetainedConfig('synthetic-old-role',.8))
            config.update(kc_composite_signal_symbol=OLD_SYMBOL,kc_composite_execution_symbol=OLD_SYMBOL)
            old_input = dict(schema='synthetic-shape',capital_baseline={'total_cny':'1000000'},
                cash_anchor={'original':'synthetic-cash-origin'},policy={'original':'synthetic-policy'},
                fee_reserve_cny='100',fee_source='synthetic',market_manifest_source='synthetic-old-data',
                request=dict(configuration=config,cycles=[dict(symbol=s,status='flat',quantity=0)for s in old_symbols],
                    previous_exits=[],history={'own_symbol':OLD_SYMBOL},analysis={},current_view={},
                    decision_cutoff='2026-11-04T07:00:00+00:00',cycles_captured_at='synthetic',cycles_valid_until='synthetic'))
            new_input = deepcopy(old_input)
            new_input['market_manifest_source'] = 'synthetic-new-own-data'
            selected = new_input['request']['configuration']
            selected.update(config_revision='synthetic-new-role',kc_composite_signal_symbol=NEW_SYMBOL,
                            kc_composite_execution_symbol=NEW_SYMBOL)
            new_input['request']['cycles'] = [dict(row,symbol=NEW_SYMBOL)if row['symbol']==OLD_SYMBOL else row
                                             for row in new_input['request']['cycles']]
            new_input['request']['history'] = {'own_symbol':NEW_SYMBOL}
            old_file,new_file = root/'old-input.json',root/'new-input.json'
            old_sha,new_sha = save(old_file,old_input),save(new_file,new_input)
            origin = dict(budget={'run_ms':0},installation_root=str(app),output_directory=str(root/'same-financial'),
                environment={'filters':''},trader={'account':'synthetic','writes_enabled':True,'binding_id':'old-binding'},
                strategies=[dict(id='resonance-regime-v1',parameters={'python_strategy':dict(input_file=str(old_file),
                    input_sha256=old_sha,market_window={'path':str(root/'old-window'),'max_age_seconds':3600},
                    capital_market={'base_url':'http://127.0.0.1:18000','token_env':'OLD_TOKEN','max_age_seconds':300})})],
                data={'store':{'symbols':[dict(symbol=s,std_code=('SSE'if s.endswith('.SH')else'SZSE')+'.ETF.'+s[:6])for s in old_symbols],
                               'daily':{'path':str(root/'old-daily'),'adjfactor':str(root/'old-factors')}}})
            native = deepcopy(origin)
            original_file = root/'execution.json'
            native['role_replacement'] = dict(schema='guanheng.zero-position-role-replacement.v1',
                                              file=str(original_file),sha256=save(original_file,origin))
            current = native['strategies'][0]['parameters']['python_strategy']
            current.update(input_file=str(new_file),input_sha256=new_sha)
            current['market_window']['path'] = str(root/'new-window')
            native['data']['store']['symbols'] = [dict(row,symbol=NEW_SYMBOL,std_code=NEW_CODE)
                if row['symbol']==OLD_SYMBOL else row for row in native['data']['store']['symbols']]
            native['data']['store']['daily'].update(path=str(root/'new-own-daily'),adjfactor=str(root/'new-own-factors'))
            native['environment']['filters'] = 'retired-role-filter.json'
            save(app/'retired-role-filter.json',{'code_filters':{'SSE.ETF.589680':{'action':'ignore'}}})
            self.assertEqual(role_origin_configuration(native),origin)
            self.assertEqual(native['output_directory'],origin['output_directory'])
            self.assertEqual(native['data']['store']['symbols'][-1]['symbol'],NEW_SYMBOL)
            changed = deepcopy(new_input)
            changed['capital_baseline']['total_cny'] = '200000000'
            with self.assertRaises(ValueError):
                validate_inputs(old_input,changed)

    def fixture(self):
        old_symbols = tuple(sorted((set(SYMBOLS) - {NEW_SYMBOL}) | {OLD_SYMBOL}))
        configuration = asdict(RetainedConfig('synthetic-old-role', .8))
        configuration.update(kc_composite_signal_symbol=OLD_SYMBOL, kc_composite_execution_symbol=OLD_SYMBOL)
        policy = QuantityPolicy('1000000', 'synthetic-explicit-capital')
        target = EconomicTarget('resonance-regime-v1', 'resonance-regime-v1@1.2.1/ledger-front-ratio-v1',
            sha256(canonical_bytes(RetainedConfig(**configuration))).hexdigest(), policy.policy_id,
            '2026-11-05', old_symbols, tuple(Weight(s, '0.25' if s == OLD_SYMBOL else '0') for s in old_symbols))
        basis = Basis('2026-11-05T06:20:00+00:00', 'a'*64, '1000000', '0', '1000000',
            '0', 'synthetic-capital', 'synthetic-cash', 'synthetic-fees',
            tuple(Price(s, '2', 'synthetic-own-price:' + s) for s in old_symbols), True, 'synthetic-original-P')
        observation = Observation(basis.observed_at, 'synthetic-original-P',
            tuple(NativePosition(s, 0, 0) for s in old_symbols), True, basis.native_observation_id)
        frozen = advance(target, policy, observation, basis).state
        self.assertIsNotNone(frozen)
        strategy = RetainedStrategy.__new__(RetainedStrategy)
        strategy.id = 'resonance-regime-v1'
        strategy.execution = SYMBOLS
        strategy.inputs = SimpleNamespace(policy=policy)
        strategy.state_identity = 'b'*64
        strategy.previous_state_identity = 'c'*64
        strategy.previous_inputs = {'request': {'configuration': configuration}}
        strategy.role_handoff = True
        metadata = {'515080.SH': dict(cycle_id='synthetic-original-cycle', opened_at='2026-11-04T01:35:00+00:00', source_sha256='d'*64)}
        payload = json.loads(strategy._state_payload(frozen, 32, metadata, ()))
        payload['identity'] = strategy.previous_state_identity
        text = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return strategy, text, frozen, basis, observation, metadata

    def test_original_frozen_plan_retires_and_new_target_uses_new_security(self):
        strategy, text, frozen, basis, observation, metadata = self.fixture()
        strategy._load_state(text)
        self.assertIsNone(strategy.state)
        self.assertEqual(strategy.cycles, metadata)
        self.assertEqual(strategy.sequence, 32)
        self.assertEqual(strategy.inputs.policy.initial_capital_cny, '1000000')
        target = replace(frozen.target, algorithm_id=ALGORITHM_ID, config_id='e'*64, universe=SYMBOLS,
            weights=tuple(Weight(s, '0.25' if s == NEW_SYMBOL else '0') for s in SYMBOLS))
        current = replace(basis, prices=tuple(Price(s, '1.403' if s == NEW_SYMBOL else '2',
            'synthetic-own-price:' + s) for s in SYMBOLS))
        observed = replace(observation, positions=tuple(NativePosition(s, 0, 0) for s in SYMBOLS))
        outcome = advance(target, strategy.inputs.policy, observed, current, strategy.state)
        self.assertEqual(outcome.state.target.universe, SYMBOLS)
        self.assertNotIn(OLD_SYMBOL, outcome.state.target.universe)
        self.assertGreater(next(row.shares for row in outcome.state.targets if row.symbol == NEW_SYMBOL), 0)
        self.assertEqual(json.loads(text)['state']['target']['algorithm_id'], frozen.target.algorithm_id)

    def test_wrong_original_configuration_is_rejected(self):
        strategy, text, *_ = self.fixture()
        strategy.previous_inputs['request']['configuration']['budget_fraction'] = .7
        with self.assertRaises(CtaBridgeError) as error:
            strategy._load_state(text)
        self.assertEqual(str(error.exception), "quantity_state_identity")

    def test_new_candidate_fill_keeps_real_opening_time(self):
        from guanheng_wt_runtime.execution_cycle_source import queried_opening_cycle
        row = SimpleNamespace(symbol='SSE.ETF.588030', trade_id='synthetic-fill', order_id='synthetic-order',
            user_tag='synthetic-wt', trade_date=20261105, trade_time=142757000, is_buy=True,
            quantity=100., price=1.403, amount=140.3)
        result = queried_opening_cycle(NEW_SYMBOL, row.symbol,
            dict(symbol=NEW_SYMBOL, status='flat', quantity=0, source_sha256='f'*64),
            '2026-11-04T09:13:01.119030+00:00', 100,
            datetime(2026,11,5,6,28,tzinfo=timezone.utc), datetime(2026,11,5,6,29,tzinfo=timezone.utc),
            SimpleNamespace(known=True,trades=(row,)), lambda: None)
        self.assertEqual(result['opened_at'], '2026-11-05T06:27:57+00:00')


if __name__ == '__main__':
    unittest.main()
