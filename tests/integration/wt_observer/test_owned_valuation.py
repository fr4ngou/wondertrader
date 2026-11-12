"""真实ASA和实际profile只读getter→发布→观衡日线；金额为QA合成实际费用替身。"""
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from decimal import Decimal as D
from fractions import Fraction
import json
from time import monotonic
from types import SimpleNamespace as NS
from uuid import uuid4

from guanheng_wt_runtime.account_allocation import AccountAllocation,BookIdentity,AccountSnapshot,StrategySeed,OwnedPosition,FeeFact
from guanheng_wt_runtime import original_live as original
from guanheng_wt_runtime.execution_configured import RetainedStrategy
from guanheng_wt_runtime.profile_facts import allocation_projection
from guanheng_wt_runtime.owned_valuation import owned_valuation
from guanheng_app.strategy_runtime_projection import project_strategy,project_strategies
from guanheng_app.live_strategy_performance import LiveStrategyPerformanceOwner
from test_dual_strategy_read import OLD,NEW,CODES,OLD_CODES,SHA,make_book,wrapper,snapshot


def deadline(): return monotonic()+30


class Context:
    """仅本地原Native getter形态，金融setter/来源查询均无调用。"""
    def __init__(self):
        self.event=NS(kind=1,epoch=1,tdate=20261109);self.kv='';self.prices={};self.age=1;self.quote_calls=[]
    def bars(self,*_a,**_kw):return ()
    def load_quantity_state(self):return self.kv
    def store_quantity_state(self,value):self.kv=value
    def facts(self):return NS(fund_pnl=0)
    def position(self,_symbol):return NS(raw_position=0,raw_valid=0,first_entry=0,last_entry=0,enum_target=None)
    def broker_observation(self):
        @dataclass(frozen=True)
        class Broker:
            positions_known: bool  # QA完整持仓观察标记。
            position_received_ms: int  # 本次QA实际接收UTC毫秒。
            positions: tuple = ()  # 全账户QA库存不参与估值。
        return Broker(True,int(datetime.now(timezone.utc).timestamp()*1000))
    def set_targets(self,*_a):raise AssertionError('read-only valuation must never set targets')
    def quote(self,symbol):
        self.quote_calls.append(symbol)
        if symbol not in self.prices:return None
        stamp=(datetime.now(timezone.utc)-timedelta(seconds=self.age)).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Shanghai'))
        return NS(action_date=int(stamp.strftime('%Y%m%d')),action_time=int(stamp.strftime('%H%M%S'))*1000+stamp.microsecond//1000,price_cny=self.prices[symbol])


class Bridge:
    def __init__(self,store):self.store=store
    def observe_context(self,*_a,**_kw):return None
    def strategy_observation(self,sid,*,deadline):return self.store.strategy_observation(sid,deadline=deadline)
    def prepare_intent(self,*_a,**_kw):raise AssertionError('read-only valuation must never prepare intent')


def profile(monkeypatch,store):
    monkeypatch.setattr(original,'configured_native_facts',lambda *a,**k:((),{},{s:Fraction(1,1000)for s in CODES}))
    p=dict(schema=original.ORIGINAL_PROFILE,strategy_version='0.2.0a1',main_symbol='SSE.ETF.510300',price_policy='signal-close-cap',
        timing_policy='next-session-first-schedule',activation_mode='signals-from-activation',initial_capital_cny='1000000',state_mode='new',
        signal_source={},quote_max_age_seconds=60,evaluation_seconds=2,broker_max_age_seconds=60,shared_account={'path':'E:/synthetic.json','sha256':SHA})
    published=[]
    reader_rows = []
    for standard in CODES:
        market, _, code = standard.split('.')
        reader_rows.append(dict(std_code=standard, symbol=code + ('.SZ' if market == 'SZSE' else '.SH')))
    native = {'trader': {'writes_enabled': False}, 'data': {'store': {'symbols': reader_rows}}}
    value=original.OriginalLiveStrategy(dict(id=NEW,parameters={'python_strategy':p}),lambda sid,v,**kw:published.append(v),NS(),
        native,deadline=deadline(),code_identity='f'*64,allocation=Bridge(store),
        signals=NS(latest=lambda:NS(value=None,ready=False,reason='synthetic_signal_unavailable')))
    return value,published


def cash_store(root):
    root.mkdir()
    store=AccountAllocation(root,BookIdentity(SHA,str(uuid4()),'b'*64),owner_check=lambda:None)
    store.initialize((StrategySeed(OLD,'1.2.2',D('10000'),(OwnedPosition(CODES[0],100,100),),0,OLD_CODES),StrategySeed(NEW,'0.2.0a1',D('1000000'),(),1,CODES)),
        D('0'),AccountSnapshot(1,'2026-11-06',D('2000000'),(OwnedPosition(CODES[0],100,100),),SHA),deadline=deadline())
    return store


def test_cash_only_actual_profile_initial_point_and_fingerprint(monkeypatch,tmp_path):
    store=cash_store(tmp_path/'asa')
    ctx=Context();owner,out=profile(monkeypatch,store)
    before=allocation_projection(store.strategy_observation(NEW,deadline=deadline()))
    owner.callback(ctx)
    value=out[-1]['owned_valuation']
    assert value['state']=='actual' and value['nav_cny']=='1000000.00' and value['market_value_cny']=='0.00'
    assert ctx.quote_calls==[]  # 空仓不向另一报价owner请求任何数据。
    assert allocation_projection(store.strategy_observation(NEW,deadline=deadline()))==before
    wire=json.loads(json.dumps(out[-1]));p=project_strategy(wrapper({NEW:wire}),strategy_id=NEW)
    assert p['valuation_state']=='actual' and p['owned_valuation']['nav_cny']=='1000000.00'
    snap=snapshot({NEW:wire});live=LiveStrategyPerformanceOwner(None,snapshot_reader=lambda _:snap,process_probe=lambda *_:True)
    try:
        result=live.read(NEW,'0.2.0a1',deadline=deadline())
        assert result['coverage']['point_count']==1 and result['summary']['nav_cny']=='1000000.00'
        assert result['summary']['pnl_cny'] is None and result['summary']['return_pct'] is None
    finally:live.close()


def test_actual_profile_schedule_publishes_reference_while_signal_waiting(monkeypatch,tmp_path):
    store=cash_store(tmp_path/'asa');owner,out=profile(monkeypatch,store);ctx=Context();owner.callback(ctx)
    # 沿真实ASA的原计划/child/D，生成QA实际成交替身；profile保持只读，无setter/prepare。
    from test_dual_strategy_read import uid,STAMP
    from guanheng_wt_runtime.account_allocation import TargetIntent,Target,GroupBinding,WTChild,PreparedCommand,FillFact
    for sid,codes in ((OLD,OLD_CODES),(NEW,CODES)):
        store.record_targets(TargetIntent(uid(),sid,1,tuple(Target(s,200 if s==CODES[0]else 0)for s in codes),SHA,STAMP),deadline=deadline())
    plan,group,child,command=[uid()for _ in range(4)];store.plan(plan,(),deadline=deadline())
    store.bind_group(plan,GroupBinding(group,CODES[0],'buy',300,D('2'),D('5')),deadline=deadline())
    store.record_wt_child(WTChild(group,child,300,D('2'),SHA),deadline=deadline())
    store.bind_prepared(PreparedCommand(group,child,command,SHA,300,D('2')),deadline=deadline())
    store.apply_fill(FillFact('callback-owned-fill',command,300,D('2'),D('600'),None,'2026-11-06','2026-11-09',SHA,CODES[0],'buy',STAMP),deadline=deadline())
    ctx.prices[CODES[0]]=3.;ctx.event=NS(kind=4,epoch=2,tdate=20261109)
    before=allocation_projection(store.strategy_observation(NEW,deadline=deadline()))
    owner.callback(ctx)
    assert out[-1]['status']=='waiting' and out[-1]['owned_valuation']['state']=='reference-fee-pending'
    assert out[-1]['owned_valuation']['reference_nav_cny']=='1000200.00'
    assert allocation_projection(store.strategy_observation(NEW,deadline=deadline()))==before


def test_real_book_two_profiles_reference_to_actual_fee_and_quote_gaps(monkeypatch,tmp_path):
    store=make_book(tmp_path/'asa');ctx=Context();ctx.prices[CODES[0]]=3.
    owner,_out=profile(monkeypatch,store)
    old=RetainedStrategy.__new__(RetainedStrategy);old.id=OLD;old.allocation=Bridge(store);old.max_age=60
    old.native_price_ticks={s:Fraction(1,1000)for s in OLD_CODES};old.inputs=NS(capital_baseline={'total_cny':'10200.00'},policy=NS(initial_capital_cny='10200.00'))
    rows={}
    def capture():
        own=store.strategy_observation(NEW,deadline=deadline());old._allocation_refresh(ctx,deadline())
        values={OLD:old._owned_valuation,NEW:owner._valuation(ctx,own,deadline())}
        for sid,codes,version in ((OLD,OLD_CODES,'1.2.2'),(NEW,CODES,'0.2.0a1')):
            obs=store.strategy_observation(sid,deadline=deadline())
            # Valuation and allocation must use the same frozen ASA revision/clock.
            if sid==OLD:obs=old.allocation_observation
            else:obs=own
            rows[sid]=dict(strategy_id=sid,strategy_version=version,status='holding',allocation_observation=allocation_projection(obs,include_read_projection=True),owned_valuation=values[sid])
        return json.loads(json.dumps(rows))
    source=capture();assert source[NEW]['owned_valuation']['reference_nav_cny']=='1000200.00'
    assert source[OLD]['owned_valuation']['reference_nav_cny']=='10400.00'
    assert source[NEW]['owned_valuation']['nav_cny'] is None
    display=tmp_path/'display';display.mkdir()
    live=LiveStrategyPerformanceOwner(None,history_root=str(display),snapshot_reader=lambda _:snapshot(source),process_probe=lambda *_:True)
    try:
        result=live.read(NEW,'0.2.0a1',deadline=deadline())
        assert result['coverage']['point_count']==0 and result['coverage']['reference_point_count']==1
        assert result['summary']['reference_nav_cny']=='1000200.00' and result['summary']['nav_cny'] is None
        ctx.prices.clear();missing=capture();assert missing[NEW]['owned_valuation']['state']=='unavailable'
        source=missing;gap=live.read(NEW,'0.2.0a1',deadline=deadline())
        assert gap['coverage']['valuation_state']=='unavailable' and gap['summary']['observed_at']==result['summary']['observed_at']
        assert gap['summary']['reference_nav_cny']=='1000200.00'
        ctx.prices[CODES[0]]=3.;ctx.age=61;expired=capture();assert expired[NEW]['owned_valuation']['state']=='unavailable'
        ctx.age=1
        # 5元是QA对“原Source确认实际费用”的替身；不读取Native模型fees或fee_bound作为实费。
        store.apply_fee(FeeFact(str(uuid4()),'actual-shared-fill',D('5'),'c'*64),deadline=deadline())
        source=capture();actual=live.read(NEW,'0.2.0a1',deadline=deadline())
        assert actual['summary']['nav_cny']=='1000196.67' and actual['summary']['reference_nav_cny'] is None
        assert actual['coverage']['point_count']==1 and actual['coverage']['reference_point_count']==0
        assert source[OLD]['owned_valuation']['nav_cny']=='10398.33'
        assert actual['summary']['reference_change_cny']=='196.67' and actual['summary']['return_pct'] is None
    finally:live.close()


def test_asa_detail_never_spends_deadline_on_nap_and_legacy_default_keeps_account(monkeypatch,tmp_path):
    import time
    import pytest
    import guanheng_app.observer_strategy_details as details
    import guanheng_app.wt_business_observation as business
    import guanheng_app.account_publication as account
    from test_dual_strategy_read import reports
    rows=reports(make_book(tmp_path/'asa'));calls=[];limits=[]
    runtime=dict(state='ready',components=dict(execution=dict(state='ready',ready=True)))
    monkeypatch.setattr(details,'resolve_runtime_configuration',lambda c,d:c)
    monkeypatch.setattr(details,'read_runtime_snapshot',lambda c,d:NS(value=runtime))
    def source(c,d):
        limits.append(d)
        if monotonic()>=d:raise TimeoutError('original deadline')
        return rows,None,'ready'
    def slow_nap(*_a,**_kw):
        calls.append('NAP');time.sleep(.04);raise TimeoutError('NAP unavailable')
    monkeypatch.setattr(business,'read_business',source)
    monkeypatch.setattr(account,'observe_published_account',slow_nap)
    end=monotonic()+.025
    value=details.observe_details(NS(account_source='wt_account_publication'),object(),end,NEW)
    assert value['calculation']['strategy_id']==NEW and value['assignment']['scope']=='strategy-allocated'
    assert calls==[] and limits==[end] and monotonic()<end
    # 同一个耗时故障确能耗尽原D；ASA查询通过“不调用无关NAP”保护主路径，D没有刷新。
    with pytest.raises(TimeoutError):slow_nap()
    assert monotonic()>end
    now=int(datetime.now(timezone.utc).timestamp()*1000)
    rows={OLD:dict(status='waiting_market_input',sequence=1,broker_position_qualified=False,
        definition=dict(strategy_id=OLD,strategy_version='1.2.2',symbols=[s.rsplit('.',1)[1]+('.SH'if s.startswith('SSE.')else'.SZ')for s in OLD_CODES]),
        broker_observation=dict(positions_known=True,positions=[],position_received_ms=now))}
    observed=[]
    monkeypatch.setattr(account,'observe_published_account',lambda *_a,**_kw:observed.append('NAP')or NS(model_dump=lambda **_k:{'aggregate':True}))
    legacy=details.observe_details(NS(account_source='wt_account_publication'),object(),deadline())
    assert observed==['NAP'] and legacy['account']=={'aggregate':True} and legacy['assignment']['scope']=='current-account-inventory'


def test_quote_failure_rounding_and_read_only_fingerprint(tmp_path):
    from decimal import localcontext
    store=make_book(tmp_path/'asa');own=store.strategy_observation(NEW,deadline=deadline());ctx=Context()
    ticks={s:Fraction(1,1000)for s in CODES}
    def value():return owned_valuation(ctx,own,ticks,baseline_cny='1000000',baseline_source='original-profile.initial_capital_cny',max_age=60,deadline=deadline())
    before=json.dumps(allocation_projection(own),sort_keys=True,separators=(',',':'))
    for price,age in ((float('nan'),1),(3.00001,1),(3.,-10),(3.,61)):
        ctx.prices[CODES[0]]=price;ctx.age=age
        result=value();assert result['state']=='unavailable' and result['nav_cny']is result['reference_nav_cny']is None
    ctx.prices[CODES[0]]=3.001;ctx.age=1
    with localcontext() as precision:
        precision.prec=2;low=value()
    assert low['reference_nav_cny']=='1000200.20'
    after=json.dumps(allocation_projection(store.strategy_observation(NEW,deadline=deadline())),sort_keys=True,separators=(',',':'))
    assert before==after  # 报价/展示clock变化未进入原金融五字段，更未改账。


def test_valuation_proof_failure_does_not_hide_ownership(tmp_path):
    from test_dual_strategy_read import reports
    store=make_book(tmp_path/'asa');rows=reports(store);ctx=Context();ctx.prices[CODES[0]]=3.
    own=store.strategy_observation(NEW,deadline=deadline())
    val=owned_valuation(ctx,own,{s:Fraction(1,1000)for s in CODES},baseline_cny='1000000',
        baseline_source='original-profile.initial_capital_cny',max_age=60,deadline=deadline())
    rows[NEW]['owned_valuation']=val;rows[NEW]['allocation_observation']=json.loads(json.dumps(allocation_projection(own,include_read_projection=True)))
    rows[NEW]['owned_valuation']['source_sha256']='0'*64
    projected=project_strategy(wrapper(rows),strategy_id=NEW)
    assert projected['valuation_state']=='unavailable' and projected['valuation_reason']=='invalid_owned_valuation'
    assert next(p for p in projected['positions']if p['symbol']=='510300.SH')['broker_quantity']==200

def test_shared_valuation_keeps_funding_and_returns_separate_by_strategy(tmp_path):
    from guanheng_wt_runtime.strategy_capital import _digest
    from guanheng_wt_runtime.strategy_capital_flow import (
        FILE_NAME, ReturnValuations, SharedReturnValuations, append_record, capital_identity, owned_return_basis,
    )

    store = cash_store(tmp_path/'asa')
    ctx = Context()
    ctx.prices[CODES[0]] = 2.0
    now = datetime.now(timezone.utc)
    start = (now-timedelta(days=4)).isoformat()
    flow_at = (now-timedelta(days=2)).isoformat()
    origin = dict(schema='guanheng.current-capital-baseline.v1', total_cny='9000', source='test',
                  baseline_at=start, historical_initial_capital_cny=None)
    anchor = dict(schema='guanheng.broker-cash-anchor.v1', baseline_sha256=_digest(origin),
                  allocated_cash_cny='9000', market_value_cny='0', account_cash_cny='15000',
                  account_observed_at=start, account_source_sha256='1'*64, account_binding_sha256=SHA,
                  position_source_sha256='3'*64, price_source_sha256='4'*64)
    own = store.strategy_observation(OLD, deadline=deadline())
    valuation = owned_valuation(ctx, own, {CODES[0]: Fraction(1, 1000)},
        baseline_cny='9000', baseline_at=start, baseline_source='retained.capital_baseline.total_cny',
        max_age=60, deadline=deadline())
    assert valuation['nav_cny'] == '10200.00'
    path = tmp_path/FILE_NAME
    scope = capital_identity(OLD, origin, anchor)
    append_record(path, scope, origin, dict(kind='flow', id='previous-inflow', source_ref='cash-proof',
        direction='inflow', amount_cny='1000', effective_at=flow_at, nav_before_cny='9000',
        nav_observed_at=flow_at, nav_source_ref='nav-proof', nav_cash_receipt_ref='cash-in-ledger'), deadline=deadline())
    basis = owned_return_basis(valuation, origin, anchor)
    for direction in ('inflow', 'outflow'):
        append_record(path, scope, origin, dict(kind='coverage', id=direction+'-check',
            source_ref=direction+'-audit', direction=direction, through=valuation['observed_at']), deadline=deadline())
    owner = SharedReturnValuations(path, OLD, origin, anchor)
    result = owner.refresh(basis, deadline=deadline())
    restarted = SharedReturnValuations(path, OLD, origin, anchor)
    assert restarted.refresh(None, deadline=deadline()) == result
    assert result['return_pct'] == '2' and result['flow_count'] == 1
    assert ReturnValuations(path, NEW).observe(basis, deadline=deadline())['return_pct'] is None
    assert owned_return_basis(dict(valuation, state='reference-fee-pending'), origin, anchor) is None

    rows = {OLD: dict(status='holding', strategy_id=OLD, strategy_version='1.2.2',
        allocation_observation=allocation_projection(own, include_read_projection=True),
        owned_valuation=valuation, capital_baseline=origin, capital_return=result,
        capital_history_anchor_sha256=_digest(anchor))}
    wire = json.loads(json.dumps(rows))
    projected = project_strategy(wrapper(wire), strategy_id=OLD)
    assert projected['capital_baseline']['total_cny'] == '9000'
    assert projected['capital_return'] == result
    snap = snapshot(wire)
    live = LiveStrategyPerformanceOwner(None, snapshot_reader=lambda _: snap, process_probe=lambda *_: True)
    try:
        summary = live.read(OLD, '1.2.2', deadline=deadline())['summary']
        assert summary['nav_cny'] == '10200.00' and summary['return_pct'] == '2'
    finally:
        live.close()

    rows[OLD]['owned_valuation'] = None  # 重启未到报价，独立观察端无历史缓存。
    without_quote = json.loads(json.dumps(rows))
    projected = project_strategy(wrapper(without_quote), strategy_id=OLD)
    assert projected['owned_valuation'] is None and projected['capital_return'] == result
    restart_snapshot = snapshot(without_quote)
    live = LiveStrategyPerformanceOwner(None, snapshot_reader=lambda _: restart_snapshot, process_probe=lambda *_: True)
    try:
        history = live.read(OLD, '1.2.2', deadline=deadline())
        summary = history['summary']
        assert summary['nav_cny'] == '10200.00' and summary['return_pct'] == '2'
        assert datetime.fromisoformat(summary['observed_at']) == datetime.fromisoformat(result['valued_at'])
    finally:
        live.close()
    append_record(path, scope, origin, dict(kind='flow', id='newly-reconciled-outflow', source_ref='cash-proof-two',
        direction='outflow', amount_cny='100', effective_at=(now-timedelta(days=1)).isoformat(),
        nav_before_cny=None, nav_observed_at=None, nav_source_ref=None, nav_cash_receipt_ref=None), deadline=deadline())
    assert restarted.refresh(None, deadline=deadline())['return_pct'] is None
