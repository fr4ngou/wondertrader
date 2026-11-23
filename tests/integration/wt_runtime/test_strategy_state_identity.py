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
