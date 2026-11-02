"""当前总资本的人工可核样本和原帧失效；不启动终端或执行器。"""
import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import time
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source', action='store_true')
    args = parser.parse_args()
    if args.source:
        sys.path.insert(0, str(args.root/'apps/wt_runtime'))
    from guanheng_wt_runtime.strategy_capital import AccountCash, AccountCashReader, observe_capital, baseline
    from guanheng_wt_runtime.initial_inventory import prepare_initial_inventory
    from guanheng_wt_runtime.execution_configured import RetainedRuntimeInput
    from guanheng_strategy_native import QuantityPolicy
    now = datetime.now(timezone.utc)
    origin = dict(schema='guanheng.current-capital-baseline.v1', total_cny='1000000',
        source='user-confirmed-current-total:2026-11-02', baseline_at=now.isoformat(),
        historical_initial_capital_cny=None)
    cash = AccountCash('199800000', '1234.5', now.isoformat(), 'a'*64)
    value = observe_capital(origin, Fraction(3500), Fraction(200000), now.isoformat(), cash, True)
    assert (value['nav_cny'], value['cash_balance_cny'], value['spendable_cash_cny']) == ('1003500','803500','802265.5')
    assert value['historical_return_pct'] is None and value['baseline']['historical_initial_capital_cny'] is None
    low = observe_capital(origin, Fraction(0), Fraction(200000), now.isoformat(), replace(cash,available_cny='12000'), True)
    assert low['spendable_cash_cny'] == '12000'
    stale = observe_capital(origin, Fraction(0), Fraction(200000), now.isoformat(), cash, False)
    assert stale['spendable_cash_cny'] is None and stale['account_observed_at'] == cash.observed_at
    excess = observe_capital(origin, Fraction(0), Fraction(1200000), now.isoformat(), cash, True)
    assert excess['cash_balance_cny'] == '-200000' and excess['spendable_cash_cny'] == '0'
    try:
        baseline(origin, QuantityPolicy('120000','old-template'))
    except ValueError:
        pass
    else:
        raise AssertionError('capital/policy drift accepted')

    # 同一账户原帧：2亿元资产不在资金读取白名单内；缺冻结不能默认为0。
    args.work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.work) as temp:
        root = Path(temp); control = str(uuid4()); directory = root/control; directory.mkdir()
        path = directory/'observation.json'
        ref = dict(schema='guanheng.account-observation-reference.v1', control_id=control,
            config_sha256='b'*64, pid=17, path=str(path), ready_path=str(directory/'ready.json'))
        (root/'current.json').write_text(json.dumps(ref),encoding='utf8')
        frame = dict(schema='guanheng.account-observation.v1',control_id=control,config_sha256='b'*64,pid=17,
            binding=dict(account='SYNTHETIC',environment='live'),state='ready',
            close=dict(status='complete',exit_code=0,resources={k:True for k in (
                'member_before_resume','tree_reaped','stdout_eof','stderr_eof','readers_joined','resources_closed')}),
            completion=dict(closed=True,joined=True),observation=dict(summary=dict(source_kind='qmt_shm_bound',
            observation_qualified=True,batches=[dict(datatype='account',delivered=True,
            source=dict(account_id='SYNTHETIC',account_environment='live'),execution_finished_at=now.isoformat())]),
            rows=dict(account=[dict(facts={k:dict(availability='present',value=v)
            for k,v in {'m_dAvailable':199800000.0,'m_dFrozenCash':1234.5,'m_dBalance':200000000.0}.items()})])))
        path.write_text(json.dumps(frame),encoding='utf8')
        reader = AccountCashReader(dict(path=str(root/'current.json'),config_sha256='b'*64,
            account='SYNTHETIC',environment='live'),60)
        result, qualified = reader.read(now,time.monotonic()+5)
        assert qualified and result.available_cny=='199800000' and result.frozen_cash_cny=='1234.5'
        assert not hasattr(result,'balance')
        for target in ('fact', 'timestamp', 'resources', 'huge-amount', 'pid-bool', 'ready-path'):
            invalid = deepcopy(frame)
            invalid_ref = deepcopy(ref)
            if target == 'fact': invalid['observation']['rows']['account'][0]['facts']['m_dAvailable'] = 1
            elif target == 'timestamp': invalid['observation']['summary']['batches'][0]['execution_finished_at'] = 1
            elif target == 'huge-amount': invalid['observation']['rows']['account'][0]['facts']['m_dAvailable']['value'] = 10**400
            elif target == 'pid-bool': invalid_ref['pid'] = 1; invalid['pid'] = True
            elif target == 'ready-path': invalid_ref['ready_path'] = str(directory/'other.json')
            else: invalid['close']['resources'] = ['member_before_resume','tree_reaped','stdout_eof','stderr_eof','readers_joined','resources_closed']
            (root/'current.json').write_text(json.dumps(invalid_ref),encoding='utf8')
            path.write_text(json.dumps(invalid),encoding='utf8')
            assert reader.read(now,time.monotonic()+5) == (result,False)
        (root/'current.json').write_text(json.dumps(ref),encoding='utf8')
        path.write_text(json.dumps(frame),encoding='utf8')
        old, qualified = reader.read(now+timedelta(seconds=61),time.monotonic()+5)
        assert not qualified and old.observed_at == now.isoformat()
        frame['observation']['rows']['account'][0]['facts'].pop('m_dFrozenCash')
        path.write_text(json.dumps(frame),encoding='utf8')
        old, qualified = reader.read(now,time.monotonic()+5)
        assert not qualified and old == result
        frame['binding']['account']='WRONG'
        path.write_text(json.dumps(frame),encoding='utf8')
        assert reader.read(now,time.monotonic()+5) == (result,False)
    data=json.loads((args.root/'build/ms-per-date-replay-001/candidate-003/SESSION.json').read_bytes())
    template=RetainedRuntimeInput.from_dict(dict(schema='guanheng.retained-cta-input.v1',
        **{k:data[k]for k in ('request','policy','fee_reserve_cny','fee_source','market_manifest_source')}))
    facts=dict(schema='guanheng.initial-inventory-facts.v2',broker_source_sha256='c'*64,
        captured_at=now.isoformat(),valid_until=(now+timedelta(seconds=60)).isoformat(),
        captured_uptime_ms=1000,valid_until_uptime_ms=61000,
        positions=[dict(symbol='510050.SH',quantity=200,sellable=100,mark_price=4.,mark_source_sha256='d'*64)])
    prepared=prepare_initial_inventory(template,facts,now=now,uptime_ms=2000,
        capital={k:origin[k]for k in ('total_cny','source')})
    loaded=RetainedRuntimeInput.from_dict(json.loads(prepared.runtime_input))
    assert loaded.policy.initial_capital_cny=='1000000' and loaded.capital_baseline == origin
    assert loaded.request.previous_exits == ()
    native=json.loads(prepared.native_input)
    assert native['positions'][0]['quantity']==200 and native['positions'][0]['mark_price']==4.
    assert loaded.capital_baseline['total_cny']=='1000000'  # 库存800元已经包含在内。
    # 同一回调里理论1000份、券商实际500份；资金只按实际500份计价。
    from types import SimpleNamespace
    from guanheng_wt_runtime.execution_configured import RetainedStrategy
    from guanheng_wt_runtime.execution_strategy import PositionValue, FactsValue, BrokerObservationValue, BrokerPositionValue
    strategy=RetainedStrategy.__new__(RetainedStrategy)
    strategy.execution=tuple(c.symbol for c in loaded.request.cycles)
    strategy.mapping={s:('SSE'if s.endswith('.SH')else'SZSE')+'.ETF.'+s[:6]for s in strategy.execution}
    strategy.targets=tuple(strategy.mapping.values());strategy.inputs=loaded
    strategy.sequence=1;strategy.id='resonance-regime-v1';strategy.seconds=5;strategy.max_age=60
    strategy.capital_reader=SimpleNamespace(read=lambda *_:(cash,True))
    class Context:
        def position(self,code):
            held=code==strategy.mapping['510050.SH']
            return PositionValue(0,1000 if held else 0,1000 if held else 0,None,
                1 if held else 0,1 if held else 0,0,None,None)
        def facts(self):return FactsValue(20261102,1000,20261102,0.)
    ms=int(now.timestamp()*1000)
    broker=BrokerObservationValue(True,True,1,ms,1,ms,ms,200000000.,199800000.,
        (BrokerPositionValue(strategy.mapping['510050.SH'],True,500.,500.),))
    _,_,basis,observed=strategy._capture(Context(),{s:4. for s in strategy.execution},now,'e'*64,
        broker=broker,deadline=time.monotonic()+5)
    assert strategy.capital_observation['market_value_cny']=='2000'
    assert strategy.capital_observation['cash_balance_cny']=='998000'
    assert basis.cash_cny=='996765.5' and basis.nav_cny=='1000000'
    assert next(p for p in observed.positions if p.symbol=='510050.SH').actual==1000
    (args.work/'VALUES-001.json').write_text(json.dumps(dict(passed=True,source=args.source,
        manual_values=value,account_asset_not_consumed=True,missing_frozen_not_zero=True,
        stale_original_time_preserved=True,wrong_binding_rejected=True,capital_drift_rejected=True,
        malformed_NAP_nested_types_wait=True,negative_cash_known_zero_spendable=True,
        broker_position_not_theoretical_target_for_cash=True,
        prepared_input_sha256=sha256(prepared.runtime_input).hexdigest(),real_QMT_calls=0),indent=2),encoding='utf8')
    print(json.dumps(dict(passed=True,source=args.source,SDK_calls=0)))


if __name__ == '__main__':
    main()
