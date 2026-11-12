"""固定profile完整业务调用链；不打开Source/账户/执行Host。"""
from dataclasses import dataclass,replace
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from fractions import Fraction
import json,time
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from guanheng_wt_runtime import original_live as mod
from guanheng_wt_runtime.original_signal_runtime import (OriginalPublication,PreparedOriginalSignal,OriginalSignalRead,OriginalSignalConfig,OriginalSignalWorker)
from guanheng_wt_runtime.strategy_profiles import *
from guanheng_wt_runtime.execution_process import _python_packages
from guanheng_wt_runtime.execution_strategy import CtaBridgeError,FactsValue,PositionValue,QuoteValue
from guanheng_wt_runtime.account_allocation import StrategyView,StrategyObservation,PositionView,OpeningCycle
from guanheng_strategy_original.reference import DEFAULT_CODES

@dataclass(frozen=True)
class Broker:
    positions_known:bool=True
    position_received_ms:int=0
    positions:tuple=()

class Allocation:
    def __init__(self):
        self.calls=[];self.reason=None;self.own=StrategyObservation(StrategyView(ORIGINAL_ID,'0.2.0a1',Decimal(1000000),Decimal(1000000),Decimal(0),Decimal(1000000),0,(),(),1),1,'b'*64,'2026-11-09',{})
    def observe_context(self,ctx,**kw):self.calls.append('observe');return self.reason
    def strategy_observation(self,sid,**kw):assert sid==self.own.strategy.strategy_id;self.calls.append('view');return self.own
    def prepare_intent(self,sid,epoch,**kw):self.calls.append(('prepare',sid,epoch,kw))

class Context:
    def __init__(self,code):
        self.code=code;self.event=NS(kind=1,epoch=1,tdate=20261109);self.kv='';self.targets={};self.calls=[]
    def broker_observation(self):return Broker(position_received_ms=int(time.time()*1000),positions=(NS(symbol='FOREIGN',quantity=999999),))
    def facts(self):return FactsValue(20261109,931,20261109,0)
    def position(self,s):return PositionValue(0,0,0,self.targets.get(s),0,0,0,None,None)
    def bars(self,*a,**kw):self.calls.append('bars');return ()
    def load_quantity_state(self):return self.kv
    def store_quantity_state(self,text):self.kv=text;self.calls.append('state')
    def quote(self,s):
        now=datetime.now().astimezone(__import__('zoneinfo').ZoneInfo('Asia/Shanghai'))-timedelta(seconds=1)
        return QuoteValue(int(now.strftime('%Y%m%d')),int(now.strftime('%H%M%S'))*1000+now.microsecond//1000,10.)
    def set_targets(self,vector):self.calls.append('set');self.targets=dict(vector);return vector

class Signals:
    def __init__(self,small):self.small=small;self.ready=True
    def latest(self):
        p=OriginalPublication('2026-11-06','a'*64,'b'*64,'2026-11-09','c'*64)
        return OriginalSignalRead(PreparedOriginalSignal(p,json.dumps(self.small).encode(),'2026-11-07T00:00:00+00:00'),self.ready,None)

def small(actions=None):
    return dict(signal_qualified=True,eligible_date='2026-11-09',decision_date='2026-11-06',decision_at='2026-11-06T15:30:00+08:00',signal_sha256='d'*64,
        signals_today={c:[] for c in DEFAULT_CODES}|({c:[dict(action=a,date='2026-11-06')] for c,a in (actions or {}).items()}),
        signal_close_prices={c:9.5 for c in DEFAULT_CODES},model_state={c:dict(held=True) for c in DEFAULT_CODES},route_qualification={c:dict(qualified=True,reasons=[]) for c in DEFAULT_CODES})

def make(monkeypatch,actions=None,policy='signal-close-cap',mode='new',signals=None,allocation=None,
         strategy_id=ORIGINAL_ID,capital='1000000',execution_symbol=None,version='0.2.0a1',writes_enabled=True, reader_rows=None):
    monkeypatch.setattr(mod,'configured_native_facts',
        lambda config,native,mapping,**kw:((),{},dict.fromkeys(mapping.values(),Fraction(1,1000))))
    p=dict(schema=ORIGINAL_PROFILE,strategy_version=version,main_symbol='SSE.ETF.510300',price_policy=policy,
        timing_policy='next-session-first-schedule',activation_mode='signals-from-activation',initial_capital_cny=capital,state_mode=mode,
        signal_source={},quote_max_age_seconds=60,evaluation_seconds=2,broker_max_age_seconds=60,shared_account={'path':'E:/fixed.json','sha256':'a'*64})
    if execution_symbol is not None:
        p['execution_symbol_589680']=execution_symbol
    if allocation is None:
        allocation = Allocation()
        cash = Decimal(capital)
        allocation.own = replace(allocation.own, strategy=replace(allocation.own.strategy,
            strategy_id=strategy_id, cash_cny=cash, ledger_cash_cny=cash, spendable_cash_cny=cash))
    out=[];sig=signals or Signals(small(actions))
    def publish(sid,value,**kw):
        from guanheng_wt_runtime.execution_configured import _encode
        _encode(value);out.append((value,kw))
    if reader_rows is None:
        reader_rows = [dict(std_code=f'{"SZSE" if code.startswith("159") else "SSE"}.ETF.{code}',
                            symbol=f'{code}.{"SZ" if code.startswith("159") else "SH"}') for code in DEFAULT_CODES]
        if execution_symbol is not None and all(row['std_code'] != execution_symbol for row in reader_rows):
            reader_rows.append(dict(std_code=execution_symbol, symbol=execution_symbol.rsplit('.', 1)[-1] + '.SH'))
    native = {'trader': {'writes_enabled': writes_enabled}, 'data': {'store': {'symbols': reader_rows}}}
    owner=mod.OriginalLiveStrategy(dict(id=strategy_id,parameters={'python_strategy':p}),publish,NS(),native,deadline=time.monotonic()+3,code_identity='f'*64,allocation=allocation,signals=sig)
    ctx=Context(owner.codes[0]);return owner,ctx,allocation,sig,out

def schedule(owner,ctx):ctx.event=NS(kind=4,epoch=2,tdate=20261109);owner.callback(ctx)

def test_strategy_instance_uses_declared_model_version_and_reader_mappings(monkeypatch):
    owner, *_ = make(monkeypatch, strategy_id='another-cta-instance', version=mod.CONFIRM_LIVE_VERSION)
    assert owner.confirmation and owner.mapping['159352'] == 'SZSE.ETF.159352'
    with pytest.raises(CtaBridgeError, match='native_reader_mapping_missing_or_ambiguous'):
        make(monkeypatch, reader_rows=[])


def test_activation_actual_empty_ignores_model_holdings(monkeypatch):
    owner,ctx,asa,sig,out=make(monkeypatch);owner.callback(ctx);schedule(owner,ctx)
    assert len(ctx.targets)==9 and not any(ctx.targets.values()) and owner._last_date=='2026-11-06' and out[-1][0]['allocation_observation']['strategy']['positions']==()
    assert asa.calls[:4]==['observe','view','observe','view']

def test_signal_to_nine_complete_targets_metadata_before_set(monkeypatch):
    c=DEFAULT_CODES[0];owner,ctx,asa,sig,out=make(monkeypatch,{c:'BUY'});assert asa.calls==[]
    owner.callback(ctx);schedule(owner,ctx)
    assert owner.binding().native_config_abi==2 and len(ctx.targets)==9
    symbol=owner.mapping[c];assert ctx.targets[symbol]==100000 and sum(ctx.targets.values())==100000
    event=[x for x in asa.calls if type(x)is tuple][-1];assert event[0]=='prepare'
    assert event[3]['buy_price_caps']=={symbol:Decimal('9.5')} and event[3]['known_at']==sig.small['decision_at']
    assert json.loads(ctx.kv)['last_source']=='d'*64
    schedule(owner,ctx);assert ctx.calls.count('set')==2


def test_opening_substitution_uses_original_signal_and_execution_quote(monkeypatch):
    symbol = 'SSE.ETF.588230'
    owner, ctx, asa, sig, out = make(monkeypatch, {'589680': 'BUY'}, policy='executor-price',
                                    execution_symbol=symbol)
    quotes = []
    def quote(context, code, tick, **kwargs):
        quotes.append(code)
        return (Fraction(2), None) if code == symbol else None
    monkeypatch.setattr(mod, 'quote_value', quote)

    owner.callback(ctx)
    schedule(owner, ctx)

    assert len(ctx.targets) == 9 and ctx.targets[symbol] == 500000
    assert 'SSE.ETF.589680' not in ctx.targets and 'SSE.ETF.589680' not in quotes
    assert '588230.SH' in out[0][0]['definition']['symbols']
    assert json.loads(ctx.kv)['buys'] == ['589680']
    assert '588230' not in sig.small['route_qualification']
    assert asa.calls[-1][3]['buy_price_caps'] == {}


def test_original_exit_uses_owned_execution_position(monkeypatch):
    symbol = 'SSE.ETF.588230'
    owner, ctx, asa, _, _ = make(monkeypatch, {'589680': 'SELL'}, policy='executor-price',
                                execution_symbol=symbol)
    owner.callback(ctx)
    asa.own = replace(asa.own, strategy=replace(asa.own.strategy,
        positions=(PositionView(symbol,10000,10000,0),)))
    ctx.targets[symbol] = 10000

    schedule(owner, ctx)

    assert ctx.targets[symbol] == 0 and 'SSE.ETF.589680' not in ctx.targets
    assert json.loads(ctx.kv)['sells'] == ['589680']


@pytest.mark.parametrize(('policy','symbol'), [
    ('signal-close-cap','SSE.ETF.588230'),
    ('executor-price','SSE.ETF.588000'),
])
def test_execution_substitution_rejects_cross_fund_price_cap_and_duplicate_route(monkeypatch,policy,symbol):
    with pytest.raises(CtaBridgeError, match='original_execution_symbol'):
        make(monkeypatch, policy=policy, execution_symbol=symbol)

def test_third_instance_targets_use_its_configured_capital(monkeypatch):
    code = DEFAULT_CODES[0]
    owner, ctx, _, _, out = make(monkeypatch, {code:'BUY'}, strategy_id='original-small', capital='250000.05')
    owner.callback(ctx)
    schedule(owner, ctx)
    assert ctx.targets[owner.mapping[code]] == 25000
    assert out[0][0]['initial_capital_cny'] == '250000.05'


def test_equalweight_uses_own_actual_and_cash(monkeypatch):
    c,d=DEFAULT_CODES[:2];owner,ctx,asa,sig,out=make(monkeypatch,{d:'BUY'})
    owner.callback(ctx)
    asa.own=replace(asa.own,strategy=replace(asa.own.strategy,ledger_cash_cny=Decimal(900000),cash_cny=Decimal(900000),positions=(PositionView(owner.mapping[c],10000,10000,0),)))
    schedule(owner,ctx);assert ctx.targets[owner.mapping[c]]==ctx.targets[owner.mapping[d]]==50000

def test_pending_buy_preserves_original_source_cap_across_day(monkeypatch):
    c=DEFAULT_CODES[0];owner,ctx,asa,sig,out=make(monkeypatch,{c:'BUY'});owner.callback(ctx);schedule(owner,ctx)
    ctx.targets={};sig.small.update(decision_date='2026-11-09',eligible_date='2026-11-10',signal_sha256='e'*64,decision_at='2026-11-09T16:00:00+08:00',signal_close_prices={c:50.},signals_today={})
    ctx.event=NS(kind=4,epoch=3,tdate=20261110);owner.callback(ctx)
    last=[x for x in asa.calls if type(x)is tuple][-1][3]
    assert last['source_sha256']=='d'*64 and last['buy_price_caps'][owner.mapping[c]]==Decimal('9.5')

@pytest.mark.parametrize('what',['unready','unqualified','calendar','future','stale_account'])
def test_waiting_keeps_zero_side_effects(monkeypatch,what):
    owner,ctx,asa,sig,out=make(monkeypatch,{DEFAULT_CODES[0]:'BUY'});owner.callback(ctx)
    if what=='unready':sig.ready=False
    elif what=='unqualified':sig.small['route_qualification']={c:dict(qualified=False,reasons=['own_price_unit']) for c in DEFAULT_CODES}
    elif what=='calendar':sig.small['eligible_date']=None
    elif what=='future':sig.small['decision_date']='2026-11-10'
    else:asa.reason='account_observation_stale'
    schedule(owner,ctx);assert not any(ctx.targets.values()) and len([x for x in asa.calls if type(x)is tuple])==(0 if what=='stale_account' else 1)

def test_revision_after_consumption_not_consumed(monkeypatch):
    owner,ctx,asa,sig,out=make(monkeypatch);owner.callback(ctx);schedule(owner,ctx)
    sig.small=small({DEFAULT_CODES[0]:'BUY'});sig.small['signal_sha256']='e'*64;schedule(owner,ctx)
    assert not any(ctx.targets.values()) and out[-1][0]['signal_revision_after_consumption']

def test_fixed_dispatch_packages_and_identity():
    old={'id':RETAINED_ID,'parameters':{'python_strategy':{'schema':RETAINED_PROFILE}}}
    new={'id':ORIGINAL_ID,'parameters':{'python_strategy':{'schema':ORIGINAL_PROFILE}}}
    third=dict(new, id='original-small')
    account=dict(shared_account={'path':'E:/frozen.json','sha256':'a'*64})
    assert _python_packages({'strategies':[old]})==RETAINED_PACKAGES
    assert _python_packages({'strategies':[new,old,third],'executer':account})==SHARED_PACKAGES
    for rows in ([new],[old,old],[old,new,new],[old,new,dict(third,id=ORIGINAL_ID.upper())]):
        with pytest.raises(ValueError):_python_packages({'strategies':rows, 'executer':account} if len(rows)>1 else {'strategies':rows})

@pytest.mark.parametrize('count', [1, 4, 64, 65])
def test_shared_profile_count_follows_native_capacity(count):
    rows = [
        dict(id=f'original-{i}', parameters=dict(python_strategy=dict(schema=ORIGINAL_PROFILE)))
        for i in range(count)
    ]
    account = dict(shared_account={'path': 'E:/frozen.json', 'sha256': 'a'*64})
    native = dict(strategies=rows, executer=account)
    if count == 65:
        with pytest.raises(ValueError, match='strategy_profiles'):
            _python_packages(native)
    else:
        assert _python_packages(native) == SHARED_PACKAGES


def test_retained_optional_allocation_own_positions_and_cycle():
    from guanheng_wt_runtime.execution_configured import RetainedStrategy
    owner=RetainedStrategy.__new__(RetainedStrategy);owner.id=RETAINED_ID;owner.allocation=Allocation()
    owner.mapping={'510300.SH':'SSE.ETF.510300'};owner.targets=('SSE.ETF.510300',)
    view=replace(owner.allocation.own.strategy,strategy_id=RETAINED_ID,positions=(PositionView('SSE.ETF.510300',100,50,0),))
    cycle=OpeningCycle('SSE.ETF.510300','old-cycle','2024-01-02T10:00:00+08:00','c'*64,'initial_inventory')
    owner.allocation_observation=replace(owner.allocation.own,strategy=view,opening_cycles={'SSE.ETF.510300':cycle})
    assert owner._broker_rows(Broker(positions=(NS(symbol='FOREIGN'),)))=={'SSE.ETF.510300':(100,50)}
    assert owner._opening_cycle('510300.SH',None,None,datetime.now(timezone.utc),lambda:None)['baseline_at']=='2024-01-02T10:00:00+08:00'
    owner.allocation_observation=replace(owner.allocation_observation,opening_cycles={'SSE.ETF.510300':replace(cycle,status='unknown',opened_at=None)})
    assert owner._opening_cycle('510300.SH',None,None,datetime.now(timezone.utc),lambda:None) is None

def config(tmp_path):
    return OriginalSignalConfig(tmp_path,tmp_path/'CURRENT.json',tmp_path/'work',{},'2024-01-01','recalc','official',.01,2.,2.)

def computer_result():
    return dict(schema='guanheng.original-current-signal.v1',algorithm_id='original',upstream_commit='3'*40,facts_sha256='a'*64,prepared_sha256='b'*64,
        decision_date='2026-11-06',decision_at='2026-11-06T16:00:00+08:00',signals_today={},model_state={},signal_qualified=False,profile='causal-current',diagnostics={'reasons':['today_margin_missing'],'coverage':{} })

def test_background_worker_complete_chain_and_join(tmp_path):
    pub=OriginalPublication('2026-11-06','a'*64,'b'*64,'2026-11-09','c'*64);seen=[]
    class Client:
        def close(self):seen.append('closed')
    def collect(c,**kw):seen.append('collect');return NS(facts={'snapshot_id':'a'*64,'raw':{'510300':{'price_unit':'unknown','bars':[]}},'analysis':{},'codes':['510300'],'profile':'causal-current'})
    worker=OriginalSignalWorker(config(tmp_path),client_factory=Client,publication_reader=lambda *a,**kw:pub,collector=collect,computer=lambda *a,**kw:computer_result(),utcnow=lambda:datetime(2026,11,7,tzinfo=timezone.utc))
    worker.start();end=time.monotonic()+2
    while not worker.latest().ready and time.monotonic()<end:time.sleep(.005)
    assert worker.latest().ready and worker.latest().value.projection()['signal_qualified'] is False
    assert worker.latest().value.projection()['signal_close_prices']=={}
    assert worker.close(time.monotonic()+2) and not worker.pending and not worker.latest().ready and seen.count('collect')==1 and seen[-1]=='closed'

def test_changed_publication_and_failed_worker_never_ready(tmp_path):
    pub=OriginalPublication('2026-11-06','a'*64,'b'*64,None,None);calls=[]
    def reader(*a,**kw):calls.append(1);return pub if len(calls)%2 else replace(pub,pointer_sha256='e'*64)
    worker=OriginalSignalWorker(config(tmp_path),client_factory=lambda:None,publication_reader=reader,
        collector=lambda *a,**kw:NS(facts={'snapshot_id':'a'*64,'raw':{},'analysis':{},'codes':['510300'],'profile':'causal-current'}),computer=lambda *a,**kw:computer_result(),utcnow=lambda:datetime(2026,11,7,tzinfo=timezone.utc))
    worker.start();time.sleep(.06);assert worker.close(time.monotonic()+2)
    assert worker.latest().value is None and not worker.latest().ready


def test_optional_macro_diagnostic_does_not_block_route(monkeypatch):
    code=DEFAULT_CODES[0];owner,ctx,asa,sig,out=make(monkeypatch,{code:'BUY'});sig.small['signal_qualified']=False
    owner.callback(ctx);schedule(owner,ctx)
    assert ctx.targets[owner.mapping[code]]==100000


def test_one_unqualified_route_does_not_consume_or_block_other(monkeypatch):
    a,b=DEFAULT_CODES[:2];owner,ctx,asa,sig,out=make(monkeypatch,{a:'BUY',b:'BUY'})
    sig.small['route_qualification'][a]=dict(qualified=False,reasons=['own_price_unit'])
    owner.callback(ctx);schedule(owner,ctx)
    assert ctx.targets[owner.mapping[a]]==0 and ctx.targets[owner.mapping[b]]==100000
    assert a not in owner._consumed_codes and b in owner._consumed_codes


def test_route_qualification_ignores_optional_history_guards():
    from guanheng_wt_runtime.original_signal_runtime import route_qualification
    facts=dict(profile='causal-current',codes=['510300'],analysis={'510300':{'price_unit':'CNY/share','volume_unit':'share'},'000300':{'price_unit':'index-point'}},raw={'510300':{'price_unit':'CNY/share'}})
    result=dict(diagnostics={'reasons':['today_shares_missing:510300','today_turnover_missing','today_margin_missing'],
        'coverage':{'510300':{'today_present':True,'ma250_full_rows':0,'missing_benchmark_dates':[],'unresolved_split_dates':[]}}},model_state={'510300':{'held':False}})
    assert route_qualification(facts,result)['510300']['qualified']
    facts['analysis']['510300']['price_unit']='unknown'
    assert not route_qualification(facts,result)['510300']['qualified']


def test_waiting_original_announces_hold_and_old_sell_authorizes(tmp_path,monkeypatch):
    from guanheng_wt_runtime.account_allocation import AccountAllocation,BookIdentity,StrategySeed,OwnedPosition,AccountSnapshot
    from guanheng_wt_runtime.account_attribution import AttributionCoordinator,AttributionEvent
    from guanheng_wt_runtime.execution_strategy import BrokerObservationValue,BrokerPositionValue
    from uuid import uuid4
    from hashlib import sha256
    code='SSE.ETF.510300';universe=tuple(('SZSE' if c.startswith('159') else 'SSE')+'.ETF.'+c for c in DEFAULT_CODES)
    (tmp_path/'book').mkdir()
    book=AccountAllocation(tmp_path/'book',BookIdentity('a'*64,str(uuid4()),'b'*64),owner_check=lambda:None)
    book.initialize((StrategySeed(RETAINED_ID,'1.2.2',Decimal(10000),(OwnedPosition(code,10000,10000),),0,(code,)),
        StrategySeed(ORIGINAL_ID,'0.2.0a1',Decimal(1000000),(),1,universe)),Decimal(0),
        AccountSnapshot(1,'2026-11-06',Decimal(2000000),(OwnedPosition(code,10000,10000),),'c'*64),deadline=time.monotonic()+5)
    coord=AttributionCoordinator(book,control_id=str(uuid4()),account_scope_sha256='a'*64,strategy_ids=(RETAINED_ID,ORIGINAL_ID),
        fee_bound=lambda *a:Decimal(5),settlement_day=lambda day:'2026-11-09')
    def send(kind,body,epoch=0):
        if kind==4:body=dict(body,instance_id='synthetic-native-executor')
        raw=json.dumps(body).encode();return coord(AttributionEvent(kind,1 if kind==1 else 2,epoch,body,raw,sha256(raw).hexdigest(),time.monotonic()+5))
    # 旧策略真实SELL意图已交原kind1，但另一ctx尚未声明时仍保持原保守规则。
    coord.prepare_intent(RETAINED_ID,10,source_sha256='d'*64,known_at='2026-11-06T09:00:00+08:00',buy_price_caps={},common_prices=(),deadline=time.monotonic()+5)
    send(1,dict(strategy_id=RETAINED_ID,targets=[dict(symbol=code,quantity=0)]),10)
    assert send(4,dict(symbol=code,side='sell',requested_quantity=10000,limit_price_cny='10'))==0
    owner,ctx,unused,sig,out=make(monkeypatch,allocation=coord);sig.ready=False
    now=int(time.time()*1000)
    ctx.broker_observation=lambda:BrokerObservationValue(True,True,1,now,1,now,now,2000000.,2000000.,(BrokerPositionValue(code,True,10000.,10000.),))
    def set_targets(vector):
        ctx.targets=dict(vector);ctx.calls.append('set')
        send(1,dict(strategy_id=ORIGINAL_ID,targets=[dict(symbol=s,quantity=q) for s,q in vector]),ctx.event.epoch)
        send(2,dict(targets=[dict(symbol=s,quantity=q) for s,q in vector]))
        return vector
    ctx.set_targets=set_targets;ctx.event=NS(kind=1,epoch=1,tdate=20261106);owner.callback(ctx)
    ctx.event=NS(kind=4,epoch=2,tdate=20261106);owner.callback(ctx)
    assert len(ctx.targets)==9 and not any(ctx.targets.values())
    assert send(4,dict(symbol=code,side='sell',requested_quantity=10000,limit_price_cny='10'))==10000
    assert all(p.quantity == 0 for p in book.view(ORIGINAL_ID, deadline=time.monotonic()+5).positions)


def test_resume_preserves_pending_original_caps_and_context_not_reseeded(monkeypatch):
    c=DEFAULT_CODES[0];owner,ctx,asa,sig,out=make(monkeypatch,{c:'BUY'});owner.callback(ctx);schedule(owner,ctx)
    saved=ctx.kv;resumed,newctx,newasa,newsig,newout=make(monkeypatch,mode='resume');newctx.kv=saved
    resumed.callback(newctx)
    assert resumed._plan==owner._plan and resumed._last_source==owner._last_source and resumed._intent_prices==owner._intent_prices
    newsig.ready=False;schedule(resumed,newctx)
    assert newctx.targets[resumed.mapping[c]]==100000
    meta=[x for x in newasa.calls if type(x)is tuple][-1][3]
    assert meta['source_sha256']=='d'*64 and meta['buy_price_caps'][resumed.mapping[c]]==Decimal('9.5')


def test_verified_recovery_resumes_fixed_initial_new_declaration(monkeypatch):
    from guanheng_wt_runtime import execution_recovery
    c=DEFAULT_CODES[0];owner,ctx,asa,sig,out=make(monkeypatch,{c:'BUY'})
    owner.callback(ctx);schedule(owner,ctx);saved=ctx.kv
    monkeypatch.setattr(execution_recovery,'strategy_state_mode',lambda *a,**kw:'resume')
    resumed,newctx,newasa,newsig,newout=make(monkeypatch,mode='new');newctx.kv=saved
    assert resumed.parameters['state_mode']=='new' and resumed.state_mode=='resume'
    resumed.callback(newctx)
    assert resumed._plan==owner._plan and resumed._intent_prices==owner._intent_prices
    assert resumed._consumed_codes==owner._consumed_codes and resumed._last_source==owner._last_source


def test_worker_close_timeout_retains_original_owner_and_rejoins(tmp_path):
    from threading import Event
    entered,release=Event(),Event()
    pub=OriginalPublication('2026-11-06','a'*64,'b'*64,None,None)
    def blocked(*a,**kw):entered.set();release.wait(2);return computer_result()
    worker=OriginalSignalWorker(config(tmp_path),client_factory=lambda:None,publication_reader=lambda *a,**kw:pub,
        collector=lambda *a,**kw:NS(facts={'snapshot_id':'a'*64,'raw':{},'analysis':{},'codes':['510300'],'profile':'causal-current'}),computer=blocked,
        utcnow=lambda:datetime(2026,11,7,tzinfo=timezone.utc))
    worker.start();assert entered.wait(1)
    try:
        assert not worker.close(time.monotonic()+.01) and worker.pending and not worker.latest().ready
        with pytest.raises(ValueError):worker.start()
    finally:
        release.set();assert worker.close(time.monotonic()+2)
    assert not worker.latest().ready and not worker.pending


def test_resume_unplanned_buy_keeps_cap_on_existing_native_target(monkeypatch):
    c=DEFAULT_CODES[0];owner,ctx,asa,sig,out=make(monkeypatch,{c:'BUY'});owner.callback(ctx);schedule(owner,ctx)
    state=json.loads(ctx.kv);state['plan']=None
    resumed,newctx,newasa,newsig,newout=make(monkeypatch,mode='resume');newctx.kv=json.dumps(state);newctx.targets=dict(ctx.targets)
    resumed.callback(newctx);newsig.ready=False;schedule(resumed,newctx)
    meta=[x for x in newasa.calls if type(x)is tuple][-1][3]
    assert meta['source_sha256']=='d'*64 and meta['known_at']==sig.small['decision_at'] and meta['buy_price_caps'][resumed.mapping[c]]==Decimal('9.5')


def calendar_publication(root,*,bad=False):
    from guanheng_market_client.market_snapshot import snapshot_identity,validate_market_snapshot
    from guanheng_market_client.exchange_calendar import encode,digest
    def write(name,value):
        path=root/name;raw=encode(value);path.write_bytes(raw);return dict(path=str(path),sha256=digest(raw))
    calendar=dict(kind='official-exchange-calendar/v1',id='test',coverage_start='2026-11-06',coverage_end='2026-11-10',
        verified_through='2026-11-10',closed_dates=[],verified_open_dates_sha256=digest(encode(['2026-11-06','2026-11-09','2026-11-10'])),method='official-fixture',evidence=[])
    if bad:calendar.update(closed_dates=['2026-11-09'],verified_open_dates_sha256='0'*64)
    cal=write('calendar.json',calendar)
    provenance={k:'a'*64 for k in ('capture_sha256','source_binding_sha256','universe_sha256','basics_sha256','base_configuration_sha256')}
    provenance['calendar_sha256']=cal['sha256']
    snapshot=dict(schema='guanheng.market-source-snapshot.v1',snapshot_id='a'*64,observation_date='2026-11-06',members=['SSE.510300'],source_kind='sdk-synthetic',
        source_received_at='2026-11-06T16:00:00+08:00',price_bases=['none','front_ratio'],
        price_reference=dict(kind='supplier_current_front_ratio',capture_sha256='a'*64,requested_from='20261101',requested_to='20261106',reference_date=None,independent_factors=None),
        basics={'SSE.510300':None},provenance=provenance)
    snapshot['snapshot_id']=snapshot_identity(snapshot);validate_market_snapshot(snapshot)
    frozen=write('source.json',dict(mode='source-market-snapshot',snapshot=write('snapshot.json',snapshot),calendar=cal))
    current=root/'CURRENT.json';write('CURRENT.json',dict(schema='guanheng.market-current.v1',observation_date='2026-11-06',snapshot_id=snapshot['snapshot_id'],configuration=frozen))
    return NS(current_file=current)


def test_calendar_uses_official_owner_and_verified_next_session(tmp_path):
    from guanheng_wt_runtime.original_signal_runtime import read_original_publication
    value=read_original_publication(calendar_publication(tmp_path),deadline=time.monotonic()+2)
    assert value.eligible_date=='2026-11-09'


def test_calendar_rebound_snapshot_still_rejects_wrong_official_verification(tmp_path):
    from guanheng_wt_runtime.original_signal_runtime import read_original_publication
    from guanheng_market_client.exchange_calendar import CalendarFailure
    with pytest.raises(CalendarFailure,match='official_calendar_verification_mismatch'):
        read_original_publication(calendar_publication(tmp_path,bad=True),deadline=time.monotonic()+2)


def readonly_setter(owner,context):
    from threading import get_native_id
    from guanheng_wt_runtime.execution_strategy import CallbackContext
    context.event=NS(kind=4,epoch=2,tdate=20261109,thread_id=get_native_id())
    runtime=NS(_thread=get_native_id,_api=NS());native=CallbackContext(runtime,owner.binding(),context.event);runtime._active=native
    context.set_targets=native.set_targets


def test_original_readonly_first_schedule_keeps_native_permission_and_publishes(monkeypatch):
    owner,ctx,asa,sig,out=make(monkeypatch,{DEFAULT_CODES[0]:'BUY'});owner.execution_enabled=False;owner.callback(ctx)
    readonly_setter(owner,ctx);owner.callback(ctx)
    assert owner.binding().execution_symbols==() and not any(type(x)is tuple for x in asa.calls)
    assert out[-1][0]['desired_targets'][owner.mapping[DEFAULT_CODES[0]]]>0 and not owner._announced


def test_retained_readonly_waiting_market_never_announces_targets():
    from guanheng_wt_runtime.execution_configured import RetainedStrategy
    @dataclass(frozen=True)
    class Request:
        cycles:tuple=()
        cycles_captured_at:object=None
        cycles_valid_until:object=None
        decision_cutoff:object=None
        previous_exits:tuple=()
    owner=RetainedStrategy.__new__(RetainedStrategy);owner.id=RETAINED_ID;owner.main='SSE.ETF.510300'
    owner.execution=('510300.SH',);owner.mapping={'510300.SH':owner.main};owner.reads=owner.targets=(owner.main,)
    owner.initialized=True;owner.execution_enabled=False;owner.seconds=2;owner.max_age=60;owner.sequence=0
    owner.allocation=Allocation();owner.allocation_observation=replace(owner.allocation.own,strategy=replace(owner.allocation.own.strategy,strategy_id=RETAINED_ID))
    owner._allocation_refresh=lambda *a:None;owner._shared_announced=False;owner.cycles={};owner.exits=();owner.flat_sources={};owner.state=None
    owner.recovery='resume_clean';owner.restored_state_id=owner.restored_sequence=None;owner.capital_observation=None
    owner.inputs=NS(request=Request(),capital_baseline=None);owner.market_window=NS(read=lambda *a,**kw:NS(request=None,publication={},reason='waiting_source'))
    owner._state_payload=lambda *a:'original-state';published=[];owner._publish=lambda v,**kw:published.append(v)
    ctx=Context('510300');readonly_setter(owner,ctx);owner.callback(ctx)
    assert owner.binding().execution_symbols==() and not owner._shared_announced and published[-1]['status']=='waiting_market_input'


def unit_evidence_descriptor(tmp_path):
    from guanheng_market_client import source_units as api
    from hashlib import sha256
    document=dict(schema='qmt.source-unit-evidence.v1',profile_id=api.PROFILE_ID,source_business_sha256='a'*64,reference_capture_sha256='b'*64,source_api=api.SOURCE_API,
        vendor_wrapper=dict(name='vendor_wrapper',uri=api.SOURCE_API,path='E:/synthetic-wrapper.py',sha256=api.VENDOR_SHA256),
        documents=[dict(name=name,uri=uri,path='E:/synthetic-'+name,sha256=identity) for name,uri,identity in api.DOCUMENTS])
    raw=json.dumps(document).encode();path=tmp_path/'units.json';path.write_bytes(raw);return dict(path=str(path),sha256=sha256(raw).hexdigest())


def test_unit_evidence_fixed_sha_sdk_dto_only_passes_from_worker(tmp_path):
    from guanheng_market_client.source_units import UnitEvidence
    from threading import get_native_id
    main=get_native_id();seen=[];pub=OriginalPublication('2026-11-06','a'*64,'b'*64,None,None)
    cfg=replace(config(tmp_path),unit_evidence=unit_evidence_descriptor(tmp_path))
    def collect(*a,**kw):
        assert get_native_id()!=main and isinstance(kw['unit_evidence'],UnitEvidence)
        seen.append(kw['unit_evidence'])
        return NS(facts={'snapshot_id':'a'*64,'raw':{},'analysis':{},'codes':['510300'],'profile':'causal-current'})
    worker=OriginalSignalWorker(cfg,client_factory=lambda:None,publication_reader=lambda *a,**kw:pub,collector=collect,computer=lambda *a,**kw:computer_result(),utcnow=lambda:datetime(2026,11,7,tzinfo=timezone.utc))
    worker.start();until=time.monotonic()+2
    try:
        while not worker.latest().ready and time.monotonic()<until:time.sleep(.005)
        assert worker.latest().ready and len(seen)==1 and seen[0].sha256==cfg.unit_evidence['sha256']
    finally:assert worker.close(time.monotonic()+2)


def test_unit_evidence_bad_sha_stops_before_client_or_collector(tmp_path):
    descriptor=unit_evidence_descriptor(tmp_path);descriptor['sha256']='0'*64;seen=[]
    worker=OriginalSignalWorker(replace(config(tmp_path),unit_evidence=descriptor),client_factory=lambda:seen.append('client'))
    worker.start();assert worker.close(time.monotonic()+2)
    assert not seen and not worker.latest().ready and worker.latest().value is None


def test_signal_source_unit_descriptor_whitelist_and_old_default(tmp_path):
    import guanheng_market_client
    market=dict(base_url='http://127.0.0.1:18136',token_env='SYNTHETIC_TOKEN',timeout_seconds=1.,max_response_bytes=1048576)
    raw=dict(source_root=str(tmp_path),current_file=str(tmp_path/'CURRENT.json'),work_directory=str(tmp_path/'work'),market=market,
        history_from='2024-01-01',feature_stage='recalc',turnover_kind='official',poll_seconds=1.,query_seconds=2.,compute_seconds=2.)
    assert OriginalSignalConfig.from_dict(raw).unit_evidence is None
    valid=unit_evidence_descriptor(tmp_path);assert OriginalSignalConfig.from_dict(dict(raw,unit_evidence=valid)).unit_evidence['sha256']==valid['sha256']
    for wrong in ({'path':valid['path'],'sha256':valid['sha256'],'mapping':{}},{'path':'C:/forbidden.json','sha256':valid['sha256']},{'path':valid['path'],'sha256':'bad'}):
        with pytest.raises((ValueError,RuntimeError)):OriginalSignalConfig.from_dict(dict(raw,unit_evidence=wrong))


def test_unit_descriptor_worker_real_collector_sdk_resolver_fixed_compute(tmp_path):
    import importlib.util
    from guanheng_market_client.source_units import parse_unit_evidence,PROFILE_ID
    from guanheng_wt_runtime.original_signal_runtime import _path
    repo=Path(__file__).resolve().parents[3];upstream=repo/'research/resonance-20261105/upstream-resonance'
    if not (upstream/'backend/base/analysis/strategy/router.py').is_file():pytest.skip('explicit fixed original source required')
    path=repo/'tests/integration/strategy_original/test_market_facts.py';spec=importlib.util.spec_from_file_location('published_fixture_for_original_worker',path)
    fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
    descriptor=unit_evidence_descriptor(tmp_path);evidence=parse_unit_evidence(Path(descriptor['path']).read_bytes());seen=[]
    class Published(fixtures.Published):
        def source_daily_history_batch_query(self,request):
            reply=super().source_daily_history_batch_query(request)
            for row in reply['data']['results']:
                data=row['data'];index=row['symbol']=='SSE.000300'
                part=dict(data['metadata'],price_unit='unknown'if index else'CNY',volume_unit='lot',amount_unit='unknown',
                    dataset_version='qmt.batch-native-day.v2:'+PROFILE_ID+':'+evidence.sha256,source={'provider':'Qmt'})
                data['metadata'].update(price_unit='unknown',volume_unit='unknown')
                data['provenance']=[dict(offset=0,count=len(data['bars']),metadata=part)]if data['bars']else[]
            return reply
    client=Published();cfg=replace(config(tmp_path),source_root=upstream,unit_evidence=descriptor,query_seconds=5.,compute_seconds=5.)
    pub=OriginalPublication('2026-11-06',fixtures.IDENTITY,'b'*64,'2026-11-09',None)
    worker=OriginalSignalWorker(cfg,client_factory=lambda:client,publication_reader=lambda *a,**kw:pub,utcnow=lambda:datetime(2026,11,7,tzinfo=timezone.utc))
    worker.start();until=time.monotonic()+8
    try:
        while not worker.latest().ready and time.monotonic()<until:time.sleep(.01)
        value=worker.latest();assert value.ready,value.reason
        output=value.value.projection();assert output['signal_close_prices'] and output['signal_close_prices']['510300']==2.
        assert output['model_state']['510300']['held']is None and output['signal_qualified']is False
        assert not output['route_qualification']['510300']['qualified']
        assert {kind for kind,_ in client.calls}=={'snapshot','history','supplement'}
    finally:assert worker.close(time.monotonic()+2)


class ConfirmationSignals(Signals):
    def latest(self):
        read = super().latest()
        return replace(read, value=replace(read.value, confirmation_recovery_json=json.dumps(self.recovery).encode()))


def confirmation_fixture(monkeypatch, *, actions=None, recovery=None):
    from guanheng_strategy_original.kc50_confirmation import CODES, STRATEGY_ID, STRATEGY_VERSION
    projection = small(actions)
    for key in ('signals_today', 'signal_close_prices', 'model_state', 'route_qualification'):
        projection[key] = {code: projection[key][code] for code in CODES}
    projection['confirmation'] = dict(previous_date='2026-11-05', style_state=[.01, .01, .01],
        atr_inputs={code:dict(close=10., atr=1., multiplier=2., qualified=True) for code in CODES})
    signals = ConfirmationSignals(projection)
    signals.recovery = recovery or {}
    return make(monkeypatch, signals=signals, strategy_id=STRATEGY_ID, version=STRATEGY_VERSION, writes_enabled=False)


def test_confirmation_no_write_plans_seven_growth_targets(monkeypatch):
    owner, ctx, allocation, _, out = confirmation_fixture(monkeypatch, actions={'588000':'BUY','510300':'BUY'})
    owner.callback(ctx)
    schedule(owner, ctx)
    row = out[-1][0]
    assert row['style'] == '成长' and len(row['desired_targets']) == 7
    assert row['desired_targets']['SSE.ETF.588000'] == 60000 and row['desired_targets']['SSE.ETF.510300'] == 40000
    assert not owner.binding().execution_symbols and 'set' not in ctx.calls
    assert not any(isinstance(x,tuple) and x[0]=='prepare' for x in allocation.calls)


@pytest.mark.parametrize(('buy','exit_codes','line'), [(False,['588000'],13.),(True,[],None)])
def test_confirmation_replays_missed_atr_breach_and_preserves_buy_priority(monkeypatch,buy,exit_codes,line):
    code = '588000'
    owner,ctx,asa,_,out = confirmation_fixture(monkeypatch, actions={code:'BUY'} if buy else {},
        recovery={code:{'2026-11-04':[15.,1.],'2026-11-05':[12.,1.]}})
    owner.callback(ctx)
    symbol=owner.mapping[code]
    asa.own=replace(asa.own,strategy=replace(asa.own.strategy,positions=(PositionView(symbol,100,100,0),)),
        opening_cycles={symbol:OpeningCycle(symbol,'actual-cycle','2026-11-04T09:31:00+08:00','b'*64,'held')})
    schedule(owner,ctx)
    observed=out[-1][0]
    assert observed['atr_exit_codes']==exit_codes and observed['atr_protection'][code]['line']==line
    if not buy:
        assert observed['atr_protection'][code]['breach_date']=='2026-11-05'
        assert observed['desired_targets'][symbol]==0
        assert json.loads(ctx.kv)['atr_protection'][code]['line']==13.
    assert 'set' not in ctx.calls


def test_confirmation_atr_exit_preserves_pending_buy_cap(monkeypatch):
    bought, exited = '510300', '588000'
    owner,ctx,asa,signals,out = confirmation_fixture(monkeypatch,actions={bought:'BUY'},
        recovery={exited:{'2026-11-06':[15.,1.]}})
    owner.callback(ctx)
    schedule(owner,ctx)
    first=json.loads(ctx.kv)
    symbol=owner.mapping[exited]
    asa.own=replace(asa.own,strategy=replace(asa.own.strategy,positions=(PositionView(symbol,100,100,0),)),
        opening_cycles={symbol:OpeningCycle(symbol,'actual-cycle','2026-11-06T09:31:00+08:00','b'*64,'held')})
    signals.small.update(decision_date='2026-11-09',eligible_date='2026-11-10',signal_sha256='e'*64,
        decision_at='2026-11-09T16:00:00+08:00',signal_close_prices=dict.fromkeys(owner.codes,11.),
        signals_today={code:[] for code in owner.codes})
    signals.small['confirmation']['previous_date']='2026-11-06'
    ctx.event=NS(kind=4,epoch=3,tdate=20261110)
    owner.callback(ctx)
    last=json.loads(ctx.kv)
    assert out[-1][0]['atr_exit_codes']==[exited] and out[-1][0]['desired_targets'][symbol]==0
    assert last['last_source']==first['last_source'] and last['intent_prices'][bought]==9.5
    assert 'set' not in ctx.calls


def test_confirmation_same_day_qualified_buy_resets_existing_line(monkeypatch):
    code='588000'
    owner,ctx,asa,signals,out=confirmation_fixture(monkeypatch,actions={code:'BUY'})
    owner.callback(ctx)
    symbol=owner.mapping[code]
    asa.own=replace(asa.own,strategy=replace(asa.own.strategy,positions=(PositionView(symbol,100,100,0),)),
        opening_cycles={symbol:OpeningCycle(symbol,'actual-cycle','2026-11-06T09:31:00+08:00','b'*64,'held')})
    signals.small['route_qualification'][code]['qualified']=False
    schedule(owner,ctx)
    assert json.loads(ctx.kv)['atr_protection'][code]['line']==8.
    signals.small['route_qualification'][code]['qualified']=True
    signals.small['signal_sha256']='e'*64
    schedule(owner,ctx)
    assert out[-1][0]['atr_protection'][code]['status']=='buy_resets_protection'
    assert json.loads(ctx.kv)['atr_protection'][code]['line'] is None and 'set' not in ctx.calls
