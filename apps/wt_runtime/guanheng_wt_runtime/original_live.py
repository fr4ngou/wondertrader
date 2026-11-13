"""原版线上策略意图：固定信号输入、独立ctx，实际归属由ASA拥有。"""
from __future__ import annotations
from dataclasses import asdict
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json,math,re,time
from .execution_strategy import StrategyBinding,TargetQuoteUnavailable,_need
from .execution_facts import canonical_raw_price
from .original_signal_runtime import OriginalSignalConfig,OriginalSignalWorker,_sha
from .profile_facts import configured_etf_mapping,configured_native_facts,digest,quote_value,common_prices,allocation_projection

ORIGINAL_PROFILE='guanheng.original-live-cta.v1'
ORIGINAL_STRATEGY_ID='resonance-original-wt-351f9d5-stable'
ORIGINAL_LIVE_VERSION='0.2.0a1'
CONFIRM_LIVE_ID='resonance-kc50-pullback-confirm'
CONFIRM_LIVE_VERSION='0.3.0a1'


def initial_capital(parameters):
    """实例明确的初始CNY金额，沿分账的分级精度。"""
    from .account_allocation import _money
    text = parameters.get('initial_capital_cny')
    _need(type(text) is str, 'original_live_capital')
    try:
        cash = Decimal(text)
    except InvalidOperation:
        raise ValueError('original_live_capital') from None
    _need(_money(cash) > 0, 'original_live_capital')
    return cash


class OriginalLiveStrategy:
    """自身只保存策略意图；不发命令、不复制账户P、不维护资金或成交账本。"""
    def __init__(self,item,publish,configuration,native,*,deadline,code_identity,allocation,signals=None):
        from guanheng_strategy_original.reference import DEFAULT_CODES
        p=item['parameters']['python_strategy'];required={'schema','strategy_version','main_symbol','price_policy','timing_policy','activation_mode',
            'initial_capital_cny','state_mode','signal_source','quote_max_age_seconds','evaluation_seconds','broker_max_age_seconds'}
        self.version = p.get('strategy_version')
        _need(self.version in (ORIGINAL_LIVE_VERSION, CONFIRM_LIVE_VERSION), 'original_live_profile')
        self.confirmation = self.version == CONFIRM_LIVE_VERSION
        allowed = {'shared_account'} if self.confirmation else {'shared_account','execution_symbol_589680'}
        allowed.add('execution_securities')
        _need(type(p)is dict and required<=set(p)<=required|allowed and p['schema']==ORIGINAL_PROFILE,
              'original_live_profile')
        _need(p['price_policy'] in ('executor-price','signal-close-cap') and p['timing_policy']=='next-session-first-schedule'
              and p['activation_mode']=='signals-from-activation'
              and p['state_mode'] in ('new','resume'),'original_live_model')
        for k,maximum in (('quote_max_age_seconds',3600),('broker_max_age_seconds',3600),('evaluation_seconds',5)):
            _need(type(p[k])in(int,float) and math.isfinite(p[k]) and 0<p[k]<=maximum,'original_live_budget')
        if 'shared_account' in p:
            shared=p['shared_account'];_need(type(shared)is dict and set(shared)=={'path','sha256'},'shared_account_binding')
            from .original_signal_runtime import _path
            _path(shared['path']);_sha(shared['sha256'])
        _need(allocation is not None,'shared_allocation_required')
        self.initial_capital_cny = initial_capital(p)
        self.start_deadline=deadline
        self.id=item['id'];self.publish=publish;self.allocation=allocation;self.parameters=dict(p);self.codes=tuple(DEFAULT_CODES)
        if self.confirmation:
            from guanheng_strategy_original.kc50_confirmation import CODES
            self.codes = CODES
        substitutions = {}
        if 'execution_symbol_589680' in p:
            execution_symbol=p['execution_symbol_589680']
            _need(type(execution_symbol) is str and re.fullmatch(r'SSE\.ETF\.[0-9]{6}',execution_symbol)
                  and p['price_policy']=='executor-price','original_execution_symbol')
            substitutions['589680'] = execution_symbol
        self.mapping = configured_etf_mapping(native, self.codes, substitutions)
        # 实际账本使用执行证券，信号状态仍使用原六位代码。
        self.analysis_codes={symbol:code for code,symbol in self.mapping.items()}
        self.reads=self.targets=tuple(sorted(self.mapping.values()));self.main=p['main_symbol'];_need(self.main in self.reads,'main_symbol')
        if 'execution_securities' in p:
            declared = p['execution_securities']
            _need(type(declared) is list and all(type(code) is str for code in declared)
                  and tuple(sorted(declared)) == self.targets, 'original_execution_securities')
        _,_,self.ticks=configured_native_facts(configuration,native,self.mapping,deadline=deadline)
        self.signals=signals or OriginalSignalWorker(OriginalSignalConfig.from_dict(p['signal_source']),confirmation=self.confirmation)
        self.seconds=p['evaluation_seconds'];self.max_age=p['broker_max_age_seconds'];self.capital_reader=None;self.participants={}
        self.execution_enabled=native['trader']['writes_enabled'];_need(type(self.execution_enabled)is bool,'execution_permission')
        self.identity=digest((self.id,self.version,{k:v for k,v in p.items() if k!='state_mode'},code_identity));self.initialized=False;self.sequence=0
        from .execution_recovery import strategy_state_mode
        try:
            self.state_mode = strategy_state_mode(native, self.id, deadline=deadline) or p['state_mode']
        except Exception as error:
            error.strategy_id = self.id  # 来源为已校验的当前策略声明。
            code = str(error)
            error.recovery_check = code if code in (
                'recovery_missing_strategy_state', 'recovery_strategy_userdata_digest',
                'recovery_strategy_targets_required',
            ) else 'recovery_strategy_state_unavailable'
            raise
        self.previous_identity=None
        if self.state_mode=='resume' and getattr(configuration,'recovery_mode',None)=='resume_reconciled':
            from .execution_recovery import load_transition,state_origin_configuration
            _,prior_code=load_transition(native)
            previous=state_origin_configuration(native,deadline=deadline)
            prior=next((row for row in previous['strategies'] if row['id']==self.id),None)
            _need(prior is not None,'original_previous_profile_required')
            old=prior['parameters']['python_strategy']
            _need({k:v for k,v in old.items() if k!='state_mode'}=={k:v for k,v in p.items() if k!='state_mode'},'original_model_transition')
            self.previous_identity=digest((self.id,self.version,{k:v for k,v in old.items() if k!='state_mode'},prior_code))
        self._buys=set();self._sells=set();self._plan=None;self._last_date=None;self._last_source=None
        self._intent_known_at=None;self._intent_prices={};self._consumed_sha=None;self._consumed_codes={};self._announced=False
        self._atr_state={}

    def binding(self):return StrategyBinding(self.id,self.main,self.reads,self.targets if self.execution_enabled else (),self.callback,native_config_abi=2)

    def _state(self):
        state = dict(
            schema='guanheng.original-live-intent.v1',  # 固定意图KV协议，不是券商账本。
            identity=self.identity,  # 本模型配置/代码身份SHA，跨安装仅沿原transition接受前代。
            sequence=self.sequence,  # 回调观察序号，不是交易次数或命令UUID。
            buys=sorted(self._buys),  # 已消费原BUY后尚未完成的六位代码集合。
            sells=sorted(self._sells),  # 已消费原SELL的退出意图，实际可卖继续由ASA/WT拥有。
            plan=self._plan,  # 完整策略目标份数，100份倍数；None表示未规划或已完成，不表示清仓。
            last_date=self._last_date,  # 最近至少一个证券消费的闭合决策日ISO；初始为None。
            last_source=self._last_source,  # 当前未完成动作的完整纯结果SHA；没有动作时为None。
            consumed_sha=self._consumed_sha,  # 最近消费结果的摘要，仅供观察修订，不替代逐证券水位。
            consumed_codes=dict(self._consumed_codes),  # 每证券{date,sha256}；缺项表示该证券尚未消费。
            intent_known_at=self._intent_known_at,  # 原信号实际已知截止，带时区ISO；初始None。
            intent_prices=dict(self._intent_prices))  # 原决策日原价收盘，CNY/份；缺证券为未知，不放宽cap。

        if self.confirmation:
            state['atr_protection'] = self._atr_state  # 按证券保存实际开仓周期及已处理闭合日的原价高点、保护线。
        return state

    def _view(self,context,deadline):
        reason=self.allocation.observe_context(context,deadline=deadline,max_age_seconds=self.max_age)
        broker=context.broker_observation();now=datetime.now(timezone.utc)
        if reason is not None:return None,broker
        _need(broker.positions_known and broker.position_received_ms is not None,'original_broker_unknown')
        stamp=datetime.fromtimestamp(broker.position_received_ms/1000,timezone.utc)
        if not stamp<=now<stamp+timedelta(seconds=self.max_age):return None,broker
        own=self.allocation.strategy_observation(self.id,deadline=deadline);_need(own.strategy.strategy_id==self.id,'original_allocation_scope')
        _need(all(row.symbol in self.targets for row in own.strategy.positions),'original_allocation_scope')
        return own,broker

    def _initialize(self,context):
        context.bars(self.main,'m1',1,main=True)
        deadline=min(self.start_deadline,time.monotonic()+self.seconds)
        own,broker=self._view(context,deadline)
        _need(own is not None,'original_initial_allocation')
        text=context.load_quantity_state()
        if self.state_mode=='new':
            _need(text=='' and context.facts().fund_pnl==0,'original_new_context_required')
            for symbol in self.targets:
                p=context.position(symbol);_need(p.raw_position==0 and p.raw_valid==0 and p.first_entry==p.last_entry==0,'original_new_context_required')
            view=own.strategy
            _need(view.ledger_cash_cny==self.initial_capital_cny and not view.pending_groups and all(r.quantity==0 for r in view.positions),'original_new_allocation_required')
            context.store_quantity_state(json.dumps(self._state(),sort_keys=True,separators=(',',':')))
        else:
            state=json.loads(text);_need(type(state)is dict and set(state)==set(self._state()) and state['schema']=='guanheng.original-live-intent.v1'
                and state['identity']in (self.identity,self.previous_identity) and state['identity']is not None,'original_state_identity')
            _need(type(state['sequence'])is int and state['sequence']>=0,'original_state_sequence')
            for name in ('buys','sells'):_need(type(state[name])is list and len(state[name])==len(set(state[name])) and set(state[name])<=set(self.codes),'original_state_intent')
            if state['plan']is not None:_need(set(state['plan'])==set(self.codes) and all(type(x)is int and x>=0 and x%100==0 for x in state['plan'].values()),'original_state_plan')
            if state['last_date']is not None:_need(date.fromisoformat(state['last_date']).isoformat()==state['last_date'],'original_state_date')
            _need(not set(state['buys'])&set(state['sells']),'original_state_intent')
            if state['last_source'] is not None:_sha(state['last_source'])
            if state['consumed_sha'] is not None:_sha(state['consumed_sha'])
            _need(type(state['consumed_codes'])is dict and set(state['consumed_codes'])<=set(self.codes),'original_state_consumed')
            for row in state['consumed_codes'].values():
                _need(type(row)is dict and set(row)=={'date','sha256'} and date.fromisoformat(row['date']).isoformat()==row['date'],'original_state_consumed');_sha(row['sha256'])
            if state['intent_known_at'] is not None:
                stamp=datetime.fromisoformat(state['intent_known_at']);_need(stamp.tzinfo is not None,'original_state_time')
            _need(type(state['intent_prices'])is dict and set(state['intent_prices'])<=set(self.codes),'original_state_prices')
            for price in state['intent_prices'].values():
                value=Decimal(str(price));_need(value.is_finite() and value>0,'original_state_prices')
            if state['buys'] or state['sells'] or state['plan'] is not None:
                _need(state['last_source'] is not None and state['intent_known_at'] is not None,'original_state_source')
            self.sequence=state['sequence'];self._buys=set(state['buys']);self._sells=set(state['sells']);self._plan=state['plan'];self._last_date=state['last_date'];self._last_source=state['last_source']
            self._intent_known_at=state['intent_known_at'];self._intent_prices=dict(state['intent_prices']);self._consumed_sha=state['consumed_sha'];self._consumed_codes=dict(state['consumed_codes'])
            if self.confirmation:
                atr = state['atr_protection']
                _need(type(atr) is dict and set(atr) <= set(self.codes), 'confirmation_atr_state')
                for row in atr.values():
                    _need(type(row) is dict and set(row) == {'cycle', 'date', 'peak', 'line'}
                          and type(row['cycle']) is str and bool(row['cycle'])
                          and date.fromisoformat(row['date']).isoformat() == row['date']
                          and ((row['line'] is None and row['peak'] is None)
                               or (all(type(row[key]) in (int, float) and math.isfinite(row[key]) for key in ('peak','line'))
                                   and 0 <= row['line'] <= row['peak'])), 'confirmation_atr_state')
                self._atr_state = atr
            if state['identity']!=self.identity:context.store_quantity_state(json.dumps(self._state(),sort_keys=True,separators=(',',':')))
        self.initialized=True
        self.publish(self.id,dict(
            status='initialized',  # ctx及自有分配已核初始化；不宣布成交或信号齐备。
            definition=self._definition(),  # 原ctx已核证券声明；ASA暂缺时也保留证券范围。
            strategy_id=self.id,  # 独立原版线上策略身份。
            strategy_version=self.version,  # 本次线上执行模型版本，不改a1/a2历史报告。
            initial_capital_cny=format(self.initial_capital_cny,'f'),  # 本实例明确的初始CNY金额。
            capital_source='ASA:explicit-new-allocation',  # 独立分配由唯一ASA拥有。
            owned_valuation=self._valuation(context,own,deadline),  # 本策略原价估值，费用未齐只发布参考值。
            allocation_observation=allocation_projection(own,include_read_projection=True),  # 自有份额/现金/周期及原账户来源，CNY十进制文本。
            model='signals-from-activation',  # 历史held仅展示，首次从最新合格闭合信号激活。
            execution_qualified=False),  # 本投影不授金融综合资格，执行owner另核真实权限。
            deadline=time.monotonic()+self.seconds)

    def _valuation(self,context,own,deadline):
        """附加观察局限于已有Native借用；预算仅取原profile声明。"""
        from .owned_valuation import owned_valuation
        return owned_valuation(context,own,self.ticks,baseline_cny=self.parameters['initial_capital_cny'],
            baseline_source='original-profile.initial_capital_cny',max_age=self.parameters['quote_max_age_seconds'],
            deadline=deadline)

    def _definition(self):
        """只读已核ctx证券池，不从账户持仓或信号推断交易所。"""
        return dict(
            strategy_id=self.id,  # 本次真实ctx策略身份。
            strategy_version=self.version,  # 已选择线上模型版本。
            symbols=[code+{'SSE':'.SH','SZSE':'.SZ'}[exchange]
                     for exchange,_,code in (symbol.split('.') for symbol in self.mapping.values())])  # 已核执行证券，含零持仓。

    def _confirmation_atr(self, prepared, small, own, actual, eligible, sells, new_buys):
        """用实际归属周期推进只升保护线，计算不持有券商或执行器。"""
        from zoneinfo import ZoneInfo
        from .kc50_atr_protection import protection_line

        view = small['confirmation']
        day = small['decision_date']
        updated = {code: row for code, row in self._atr_state.items() if actual[code]}
        rows, exits = {}, []
        recovery = None
        for code, inputs in view['atr_inputs'].items():
            prior = updated.get(code)
            cycle = own.opening_cycles.get(self.mapping[code])
            if prior is not None and cycle is not None and cycle.cycle_id and prior['cycle'] != cycle.cycle_id:
                updated.pop(code)
                prior = None
            row = dict(inputs, quantity=actual[code], line=prior['line'] if prior else None,
                       peak=prior['peak'] if prior else None, status='flat')
            rows[code] = row
            if not actual[code]:
                continue
            if not inputs['qualified']:
                row['status'] = 'atr_history_units_unqualified'
                continue
            if cycle is None or not cycle.cycle_id or not cycle.opened_at:
                row['status'] = 'opening_cycle_unavailable'
                continue
            opened = datetime.fromisoformat(cycle.opened_at).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
            if code in sells:
                row['status'] = 'exit_pending'
                continue
            if not eligible or opened > day:
                row['status'] = 'decision_not_eligible'
                continue
            if code in new_buys:
                updated[code] = dict(cycle=cycle.cycle_id, date=day, peak=None, line=None)
                row.update(peak=None, line=None, status='buy_resets_protection')
                continue
            if prior is not None and prior['date'] >= day:
                row['status'] = 'observed'
                continue
            peak, line = row['peak'], row['line']
            crossed = None
            if (prior is None and opened < day) or (prior and prior['date'] != view['previous_date']):
                if recovery is None:
                    recovery = json.loads(prepared.confirmation_recovery_json or b'{}')
                history = recovery.get(code, {})
                start = opened if prior is None else prior['date']
                if start not in history or view['previous_date'] not in history:
                    row['status'] = 'atr_history_resume_required'
                    continue
                for observed in sorted(history):
                    if observed < start or (prior and observed == start) or observed >= day:
                        continue
                    close, atr = history[observed]
                    peak, line = protection_line(close, atr, inputs['multiplier'], peak, line)
                    if close <= line and crossed is None:
                        crossed = observed
            peak, line = protection_line(inputs['close'], inputs['atr'], inputs['multiplier'], peak, line)
            updated[code] = dict(cycle=cycle.cycle_id, date=day, peak=peak, line=line)
            exit_now = crossed is not None or inputs['close'] <= line
            row.update(peak=peak, line=line, status='exit' if exit_now else 'protected', breach_date=crossed or (day if exit_now else None))
            if exit_now:
                exits.append(code)
        return updated, rows, exits

    def callback(self,context):
        if context.event.kind==1:self._initialize(context);return
        if context.event.kind!=4:return
        _need(self.initialized,'original_not_initialized');deadline=time.monotonic()+self.seconds;self.sequence+=1
        own,broker=self._view(context,deadline)
        observation = dict(definition=self._definition(), sequence=self.sequence,
            owned_valuation=self._valuation(context, own, deadline),
            allocation_observation=None if own is None else allocation_projection(own,include_read_projection=True),
            account_observation=asdict(broker), execution_qualified=False)
        if self.execution_enabled and own is not None and not self._announced:
            if self._plan is None and not self._sells and not self._buys:
                from .profile_facts import announce_shared_hold
                try:
                    announce_shared_hold(context,self.id,self.targets,own,self.allocation,source_identity=self.identity,deadline=deadline)
                except TargetQuoteUnavailable:
                    self.publish(self.id, dict(observation, status='waiting', reason='target_quote_unavailable'), deadline=deadline)
                    return
                self._announced=True
            else:
                # 恢复的未完成目标沿原source/cap，不能以保持动作放宽买入上界。
                quantities={r.symbol:r.quantity for r in own.strategy.positions}
                desired={s:(quantities.get(s,0) if context.position(s).enum_target is None else int(context.position(s).enum_target)) for s in self.targets}
                if self._plan is not None:desired={self.mapping[c]:q for c,q in self._plan.items()}
                for c in self._sells:desired[self.mapping[c]]=0
                caps={}
                if self.parameters['price_policy']=='signal-close-cap':
                    for s,q in desired.items():
                        if q>quantities.get(s,0):
                            raw=self._intent_prices.get(s.rsplit('.',1)[1]);_need(raw is not None,'original_state_cap_missing');ratio=canonical_raw_price(raw,self.ticks[s]);caps[s]=Decimal(ratio.numerator)/Decimal(ratio.denominator)
                self.allocation.prepare_intent(self.id,context.event.epoch,source_sha256=self._last_source,known_at=self._intent_known_at,buy_price_caps=caps,common_prices=(),deadline=deadline)
                try:
                    _need(dict(context.set_targets(tuple(desired.items())))==desired,'original_target_readback')
                except TargetQuoteUnavailable:
                    self.publish(self.id, dict(observation, status='waiting', reason='target_quote_unavailable'), deadline=deadline)
                    return
                self._announced=True
        read=self.signals.latest();small=None if read.value is None else read.value.projection()
        candidate=dict(observation,
            strategy_id=self.id,  # 当前独立策略身份。
            strategy_version=self.version,  # 线上模型版本，不冒充冻结回测版本。
            price_policy=self.parameters['price_policy'],  # 显式执行价格模型；不是已成交价格保证。
            timing_policy=self.parameters['timing_policy'],  # 下一会话首个具备条件的分钟调度。
            signal=small,  # 后台不可变小投影；无最后成功值时为None。
            signal_ready=read.ready,  # 本轮发布/计算是否成功，逐路由资格另列。
            signal_reason=read.reason,  # 固定等待/失败分类，缺省None。
            )
        candidate['signal_revision_after_consumption']=small is not None and self._last_date==small['decision_date'] and self._consumed_sha!=small['signal_sha256']
        def waiting(reason):
            self.publish(self.id,dict(candidate,status='waiting',reason=reason),deadline=deadline)
        if own is None:waiting('broker_observation_stale');return
        if not read.ready or small is None:waiting('prepared_signal_unavailable');return
        qualifications=small.get('route_qualification',{})
        _need(type(qualifications)is dict and set(qualifications)==set(self.codes),'original_route_qualification')
        candidate['route_qualification']=qualifications
        trade=datetime.strptime(str(context.event.tdate),'%Y%m%d').date().isoformat()
        actual={c:0 for c in self.codes}
        for p in own.strategy.positions:actual[self.analysis_codes[p.symbol]]=p.quantity
        buys=set(self._buys);sells={c for c in self._sells if actual[c]>0};plan=None if self._plan is None else dict(self._plan)
        last_date,last_source=self._last_date,self._last_source
        consumed_sha=self._consumed_sha;consumed_codes=dict(self._consumed_codes)
        intent_known_at,intent_prices=self._intent_known_at,dict(self._intent_prices)
        eligible=small['eligible_date']==trade and small['decision_date']<trade
        consumed_any=False
        confirmation = small['confirmation'] if self.confirmation else None
        blocked_buys = []
        new_buys = set()
        atr_state = None
        if eligible:
            for c,rows in small['signals_today'].items():
                _need(c in self.codes,'original_signal_scope')
                prior=consumed_codes.get(c)
                if not qualifications[c]['qualified'] or (prior is not None and prior['date']>=small['decision_date']):continue
                if confirmation is not None and any(row['action']=='BUY' for row in rows) and not confirmation['atr_inputs'][c]['qualified']:
                    blocked_buys.append(c)
                    continue
                consumed_codes[c]=dict(
                    date=small['decision_date'],  # 此证券实际消费的闭合决策日ISO。
                    sha256=small['signal_sha256'])  # 当时完整纯结果SHA；后继修订不重复消费。
                consumed_any=True
                for row in rows:
                    _need(row['date']==small['decision_date'] and row['action'] in ('BUY','SELL'),'original_signal_record')
                    if row['action']=='BUY':
                        buys.add(c);sells.discard(c);plan=None
                        new_buys.add(c)
                    else:sells.add(c);buys.discard(c);plan=None if plan is None else dict(plan,**{c:0})
                    last_source=small['signal_sha256'];intent_known_at=small['decision_at'];intent_prices=dict(small['signal_close_prices'])
            if consumed_any:last_date=small['decision_date'];consumed_sha=small['signal_sha256']
        if confirmation is not None:
            atr_state, protection, exits = self._confirmation_atr(read.value,small,own,actual,eligible,sells,new_buys)
            candidate['atr_protection'] = protection
            candidate['atr_blocked_buy_codes'] = blocked_buys
            candidate['atr_exit_codes'] = exits
            for code in exits:
                sells.add(code);buys.discard(code);plan=None if plan is None else dict(plan,**{code:0})
            # 未成交增仓仍按首次信号的价格上界和来源；新的ATR退出只缩减目标。
            if exits and not buys and (plan is None or all(quantity <= actual[code] for code, quantity in plan.items())):
                last_source=small['signal_sha256'];intent_known_at=small['decision_at'];intent_prices=dict(small['signal_close_prices'])
        if not consumed_any and not (buys or sells or plan is not None) and atr_state == (self._atr_state if self.confirmation else None):
            if blocked_buys:waiting('atr_history_units_unqualified')
            elif eligible and any(not r['qualified'] for r in qualifications.values()):waiting('route_data_unqualified')
            elif not eligible:waiting('signal_session_not_eligible')
            else:self.publish(self.id, dict(candidate, status='holding', reason=None,
                signal_consumed_date=last_date), deadline=deadline)
            return
        now=datetime.now(timezone.utc);prices={}
        for c in self.codes:
            value=quote_value(context,self.mapping[c],self.ticks[self.mapping[c]],now=now,max_age=self.parameters['quote_max_age_seconds'])
            if value is not None:prices[c]=value[0]
        if plan is not None and all(actual[c]==q for c,q in plan.items()):plan=None;buys.clear()
        if buys and plan is None:
            active=({c for c,q in actual.items() if q>0}|buys)-sells
            if active and all(c in prices for c in active) and all(c in prices for c,q in actual.items() if q):
                nav=Fraction(own.strategy.ledger_cash_cny)+sum((q*prices[c] for c,q in actual.items() if q),Fraction(0))
                if nav>0:
                    weights = dict.fromkeys(active,1)
                    if confirmation is not None:
                        from guanheng_strategy_original.kc50_confirmation import allocation
                        weights, candidate['style'] = allocation(confirmation['style_state'],active)
                    total = sum(weights.values())
                    plan={c:int(nav*weights[c]/total/prices[c]/100)*100 if c in active else 0 for c in self.codes}
                    if confirmation is not None:
                        for code in active:
                            if not confirmation['atr_inputs'][code]['qualified'] or (actual[code] and protection[code]['status'] in ('atr_history_resume_required','opening_cycle_unavailable')):
                                plan[code] = min(plan[code], actual[code])
        desired={c:(actual[c] if context.position(self.mapping[c]).enum_target is None else int(context.position(self.mapping[c]).enum_target)) for c in self.codes} if plan is None else dict(plan)
        for c in sells:desired[c]=0
        vector=tuple((self.mapping[c],desired[c]) for c in self.codes)
        comparison = {code: context.position(symbol).enum_target for code, symbol in self.mapping.items()}
        changed=any((actual[code] if self.confirmation and comparison[code] is None else comparison[code])!=quantity
                    for code,quantity in desired.items())
        caps={}
        if self.parameters['price_policy']=='signal-close-cap':
            for c in self.codes:
                if desired[c]>actual[c]:
                    raw=intent_prices.get(c)
                    if raw is None:waiting('signal_raw_close_missing');return
                    ratio=canonical_raw_price(raw,self.ticks[self.mapping[c]]);caps[self.mapping[c]]=Decimal(ratio.numerator)/Decimal(ratio.denominator)
        commons=common_prices(context,self.mapping,self.ticks,self.participants,now=now,max_age=self.parameters['quote_max_age_seconds'])
        candidate.update(
            status='targets_ready' if changed else 'waiting' if blocked_buys else 'holding',  # 目标是否需改变，不表示券商已成交。
            reason='atr_history_units_unqualified' if blocked_buys else None,  # 保留被拦截的买入原因。
            desired_targets=dict(vector),  # 标准代码到完整目标份数；100份倍数，非资金权重。
            buy_intents=sorted(buys),  # 自有组合尚待完成的原BUY代码。
            sell_intents=sorted(sells),  # 自有组合尚待退出的原SELL代码。
            signal_consumed_date=last_date,  # 最近消费闭合日，允许部分证券尚未合格。
            signal_revision_after_consumption=self._last_date==small['decision_date'] and self._consumed_sha!=small['signal_sha256'])  # 同日更晚修订只展示差异。
        self.publish(self.id,candidate,preview=True,deadline=deadline)
        if changed and (sells or plan is not None) and self.execution_enabled:
            _need(all(type(q)is int and q>=0 and q%100==0 for _,q in vector),'original_target_quantity')
            self.allocation.prepare_intent(self.id,context.event.epoch,source_sha256=last_source,known_at=intent_known_at,
                buy_price_caps=caps,common_prices=commons,deadline=deadline)
            try:
                _need(dict(context.set_targets(vector))==dict(vector),'original_target_readback')
            except TargetQuoteUnavailable:
                candidate.pop('desired_targets', None)
                candidate.pop('signal_consumed_date', None)
                waiting('target_quote_unavailable')
                return
        state=dict(
            schema='guanheng.original-live-intent.v1',  # 同_state声明的唯一意图协议。
            identity=self.identity,  # 当前配置/代码身份SHA。
            sequence=self.sequence,  # 本次已完成回调观察序号。
            buys=sorted(buys),  # 尚未完成的BUY六位代码。
            sells=sorted(sells),  # 尚未完成的SELL六位代码。
            plan=plan,  # 完整策略目标份数或尚未规划/已完成的None。
            last_date=last_date,  # 最近实际消费的闭合决策日。
            last_source=last_source,  # 本轮未完成动作原纯结果SHA。
            consumed_sha=consumed_sha,  # 最近消费摘要，独立于当前意图来源。
            consumed_codes=consumed_codes,  # 逐证券决策日/原SHA，缺项尚未消费。
            intent_known_at=intent_known_at,  # 原信号已知时刻，带时区ISO或初始None。
            intent_prices=intent_prices)  # 原价收盘CNY/份，不借新日结果重写旧cap。
        if self.confirmation:
            state['atr_protection'] = atr_state
        context.store_quantity_state(json.dumps(state,sort_keys=True,separators=(',',':')))
        if self.confirmation:
            self._atr_state = atr_state
        self._buys,self._sells,self._plan,self._last_date,self._last_source=buys,sells,plan,last_date,last_source
        self._intent_known_at,self._intent_prices,self._consumed_sha=intent_known_at,intent_prices,consumed_sha
        self._consumed_codes=consumed_codes
        self.publish(self.id,candidate,deadline=deadline)
