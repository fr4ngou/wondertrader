"""状态兼容身份与部署身份分离；空持仓也须校验算法和配置。"""
import pytest
from datetime import datetime,timezone
from types import SimpleNamespace as NS
import time
from guanheng_wt_runtime.strategy_state import StrategyStateRecord


def test_model_identity_has_versioned_state_contract_and_all_business_fields():
    model=dict(strategy_id='synthetic-instance', input_sha256='a'*64,
               mapping={'synthetic.SH':'SSE.ETF.synthetic'}, policy={'capital_cny':'1000000'},
               configuration='b'*64, algorithm='algorithm-v1', market_window=None)
    record=StrategyStateRecord('synthetic.quantity-state.v1')
    identity=record.model_identity(model)
    assert identity==record.model_identity(dict(reversed(tuple(model.items()))))
    for key in model:
        changed=dict(model);changed[key]='synthetic-different'
        assert record.model_identity(changed)!=identity
    assert StrategyStateRecord('synthetic.quantity-state.v2').model_identity(model)!=identity


def retained(monkeypatch,code_identity, *, algorithm='synthetic-v1',config='b'*64):
    from guanheng_wt_runtime import execution_configured as mod
    from guanheng_wt_runtime import profile_facts,strategy_profiles
    from guanheng_strategy_native import QuantityPolicy
    inputs=NS(request=NS(decision_cutoff=datetime.now(timezone.utc)),policy=QuantityPolicy('1000000','synthetic'),
              capital_baseline=None,cash_anchor=None)
    monkeypatch.setattr(strategy_profiles,'shared_profiles',lambda n:False)
    monkeypatch.setattr(mod,'_read',lambda *a,**kw:b'{}')
    monkeypatch.setattr(mod.RetainedRuntimeInput,'from_dict',lambda v:inputs)
    monkeypatch.setattr(mod,'_retained_seed_identity',lambda *a,**kw:(config,algorithm))
    monkeypatch.setattr(profile_facts,'configured_native_facts',lambda *a,**kw:({},dict(fees=b'{}'),{}))
    p=dict(schema='guanheng.retained-cta.v1',input_file='E:/synthetic/input.json',
           input_sha256=__import__('hashlib').sha256(b'{}').hexdigest(),main_symbol='SSE.ETF.510300',
           evaluation_seconds=2,broker_max_age_seconds=60)
    native=dict(trader=dict(writes_enabled=True),executer=dict(scale=1,policy={'default':dict(
        name='WtExeFact.WtStockMinImpactExeUnit',min_order=100,is_cancel_unmanaged_order=False)}))
    return mod.RetainedStrategy(dict(id='resonance-regime-v1',parameters={'python_strategy':p}),
        lambda *a,**kw:None,NS(recovery_mode='resume_clean'),native,deadline=time.monotonic()+5,
        code_identity=code_identity,market_input_timeout=5)


def test_retained_empty_state_survives_deployment_change_but_rejects_algorithm_and_config(monkeypatch):
    from guanheng_wt_runtime.execution_strategy import CtaBridgeError
    original=retained(monkeypatch,'a'*64)
    raw=original._state_payload(None,424,{},())
    successor=retained(monkeypatch,'b'*64)
    successor._load_state(raw)
    assert successor.sequence==424 and successor._state_payload(None,424,{},())==raw
    for changed in (dict(algorithm='synthetic-v2'),dict(config='c'*64)):
        owner=retained(monkeypatch,'b'*64,**changed)
        with pytest.raises(CtaBridgeError,match='quantity_state_identity'):
            owner._load_state(raw)


def test_retained_init_mirror_failure_and_new_install_keep_original_asa_record(monkeypatch):
    from guanheng_wt_runtime import execution_configured as mod
    from guanheng_wt_runtime.strategy_state import SharedStrategyState
    initial=retained(monkeypatch,'a'*64)
    raw=initial._state_payload(None,424,{},())
    class Book:
        def load_strategy_state(self,*a,**kw):return raw
        def commit_strategy_state(self,*a,**kw):raise AssertionError('INIT rewrote original ASA state')
    class Context:
        kv=''
        broken=True
        def broker_observation(self):return NS(positions_known=True)
        def broker_trades(self):return None
        def load_quantity_state(self):return self.kv
        def store_quantity_state(self,value):
            if self.broken:raise OSError('synthetic native mirror save interrupted')
            self.kv=value
    monkeypatch.setattr(mod,'register_main_minute',lambda *a,**kw:None)
    monkeypatch.setattr(mod,'allocation_projection',lambda *a,**kw:None)
    for broken,code in ((True,'b'*64),(False,'c'*64)):
        owner=retained(monkeypatch,code);owner.allocation=Book()
        owner.recovery_state=SharedStrategyState(mod.RETAINED_STATE,owner.allocation,owner.id)
        owner._allocation_refresh=lambda *a:None
        owner._broker_rows=lambda *a:{}
        owner._flat_source=lambda *a:None
        ctx=Context();ctx.broken=broken
        if broken:
            with pytest.raises(OSError,match='mirror save interrupted'):owner._initialize(ctx)
        else:
            owner._initialize(ctx)
            assert owner.initialized and owner.sequence==424 and ctx.kv==raw


@pytest.mark.parametrize('reason', ('account_sellable_mismatch', 'account_position_mismatch',
                                  'account_observation_unknown', 'account_observation_stale',
                                  'account_freeze_unbound'))
def test_retained_account_wait_restores_state_without_target_or_restart(monkeypatch, reason):
    from dataclasses import dataclass
    from guanheng_wt_runtime import execution_configured as mod, owned_valuation
    from guanheng_wt_runtime.strategy_state import SharedStrategyState
    owner = retained(monkeypatch, 'b'*64)
    raw = owner._state_payload(None, 424, {}, ())
    published = []
    @dataclass(frozen=True)
    class Broker:
        positions_known: bool = True
        position_received_ms: int = int(time.time()*1000)
    @dataclass(frozen=True)
    class Request:
        cycles: tuple = ()
        cycles_captured_at: object = None
        cycles_valid_until: object = None
        decision_cutoff: object = None
        previous_exits: tuple = ()
    class Book:
        current_reason = reason
        def observe_context(self, *a, **kw): return self.current_reason
        def strategy_state(self, *a, **kw): return NS(strategy=NS(strategy_id=owner.id, positions=()))
        def load_strategy_state(self, *a, **kw): return raw
        def commit_strategy_state(self, *a, **kw): raise AssertionError('waiting rewrote original state')
    class Context:
        kv = ''
        event = NS(kind=1, epoch=1)
        known = reason != 'account_observation_unknown'
        def broker_observation(self): return Broker(self.known, int(time.time()*1000) if self.known else None)
        def broker_trades(self): return None
        def load_quantity_state(self): return self.kv
        def store_quantity_state(self, value): self.kv = value
        def set_targets(self, *a): raise AssertionError('waiting submitted targets')
    monkeypatch.setattr(mod, 'register_main_minute', lambda *a, **kw: None)
    monkeypatch.setattr(mod, 'allocation_projection', lambda *a, **kw: None)
    monkeypatch.setattr(owned_valuation, 'owned_valuation', lambda *a, **kw: None)
    owner.allocation = Book()
    owner.recovery_state = SharedStrategyState(mod.RETAINED_STATE, owner.allocation, owner.id)
    owner.publish = lambda sid, value, **kw: published.append(value)
    ctx = Context()
    owner.callback(ctx)
    assert owner.initialized and owner.sequence == 424 and ctx.kv == raw
    assert published[-1]['status'] == 'waiting_allocation' and published[-1]['reason'] == reason
    ctx.event = NS(kind=4, epoch=2)
    owner.callback(ctx)
    assert published[-1]['status'] == 'waiting_allocation' and published[-1]['reason'] == reason
    # 同一存活实例再次取得合格账户；不以重启重置记录。
    owner.allocation.current_reason = None
    ctx.known = True
    owner.inputs.request = Request()
    owner.market_window = NS(read=lambda *a, **kw: NS(request=None, publication={}, reason='awaiting_test_market'))
    owner.execution_enabled = False
    owner.callback(ctx)
    assert published[-1]['status'] == 'waiting_market_input' and published[-1]['reason'] == 'awaiting_test_market'
    assert owner.initialized and ctx.kv == raw


def test_retained_publishes_computed_result_while_waiting_for_trading_quote(monkeypatch):
    from dataclasses import dataclass
    from guanheng_strategy_v1 import STRATEGY_VERSION
    from guanheng_wt_runtime import execution_configured as mod, retained_evaluation
    from guanheng_wt_runtime.execution_strategy import BrokerObservationValue

    @dataclass(frozen=True)
    class Request:
        cycles: tuple = ()
        cycles_captured_at: datetime | None = None
        cycles_valid_until: datetime | None = None
        decision_cutoff: datetime | None = None
        previous_exits: tuple = ()

    owner = retained(monkeypatch, 'b'*64)
    owner.initialized = True
    owner.inputs.request = Request()
    owner.market_window = NS(read=lambda request, **kwargs: NS(request=request, publication={}))
    monkeypatch.setattr(mod, 'native_history_matches', lambda *args: True)
    monkeypatch.setattr(owner, '_store_state', lambda *args: None)
    result = dict(schema='guanheng.retained-resonance-result.v1', strategy_id=owner.id,
                  strategy_version=STRATEGY_VERSION, targets=dict.fromkeys(owner.execution, 0))

    def calculated(request, *args, **kwargs):
        result['decision_cutoff'] = request.decision_cutoff.isoformat()
        return NS(result=NS(to_dict=lambda: result))

    monkeypatch.setattr(retained_evaluation, 'evaluate_retained', calculated)
    publications = []
    owner.publish = lambda identity, value, **kwargs: publications.append(value)
    broker = BrokerObservationValue(True, False, 1, int(time.time()*1000), 0, None, 0, None, None, ())

    def unexpected_target(*args):
        pytest.fail('缺交易报价时提交了目标')

    context = NS(event=NS(kind=4), quote=lambda symbol: None, broker_observation=lambda: broker,
                 broker_trades=lambda: None, set_targets=unexpected_target)
    owner.callback(context)

    published = publications[-1]
    assert published['status'] == 'waiting_market_input'
    assert published['reason'] == 'current_applied_quote_unavailable'
    assert published['core_result'] == result
    assert published.get('outcome') is None and published.get('target_readback') is None
    assert owner.state is None
