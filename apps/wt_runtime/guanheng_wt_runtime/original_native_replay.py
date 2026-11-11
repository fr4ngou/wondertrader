"""冻结原版信号的WT执行接缝；纯值准入由original_native_contracts唯一拥有。"""
from __future__ import annotations
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from threading import get_ident
from .kc50_atr_protection import AtrProtection
from .strategy_porter import BacktestConfig, BacktestPorter, Bar, Callbacks, Target
from .strategy_replay_facts import SessionError, admit_native_files, _decimal
from .retained_replay import ORIGINAL_BT_SHA256, ABI_PROBE_SHA256
from .original_native_contracts import (
    _quantity,
    INPUT_SCHEMA,
    REPORT_SCHEMA,
    STRATEGY_ID,
    STRATEGY_VERSION,
    ALGORITHM_ID,
    UPSTREAM_COMMIT,
    REPORT_SCOPE,
    MAX_BYTES,
    INPUT_FIELDS,
    MODEL,
    LEGACY_VERSION,
    CONFIRM_VERSION,
    model_for_version,
    _encode,
    _digest,
    _need,
    _hash,
    _text,
    _day,
    _money,
    _number,
    _native,
    normalize_input,
    build_input,
    configuration_id,
    OriginalNativeInput,
    ValidatedOriginalNativeReport,
    validate_report,
    verify_report_input,
    project_record,
)

STATE_KEY='original_native_v1'
ZONE=timezone(timedelta(hours=8))


def session_identity(input_id,cwd,start,end,name,identities):
    return _digest((input_id,str(cwd),start,end,name,identities,ORIGINAL_BT_SHA256,ABI_PROBE_SHA256))


class OriginalNativeSession:
    """一个受管子进程独占一次原生上下文；本对象不拥有成交或额外现金账本。"""
    def __init__(self,inputs):
        self._value=normalize_input(inputs.to_dict() if type(inputs) is OriginalNativeInput else inputs)
        self._owner=get_ident();self._porter=None;self._started=False;self._initialized=False
        self._codes=tuple(sorted(self._value['history']));self._mapping={code:_native(code) for code in self._codes}
        self._series={self._mapping[code]:tuple(Bar(_day(row['date']),0,row['open'],row['high'],row['low'],row['close'],row['close'],
            row['amount'],row['volume']) for row in self._value['history'][code]) for code in self._codes}
        self._days=tuple(_day(day) for day in self._value['calendar']);self._input_id=_digest(self._value)
        self._closed_dates={native:set() for native in self._series}  # 原bar回调确认可消费日期；不保存成交或价格账本。
        self._records=[];self._session_id=None;self._last_userdata=''
        self._buy_intents=set()  # 尚未生成合法完整目标的原BUY意图，不代表成交或现金。
        self._sell_intents=set()  # T+1冻结/原生pending下保留的原SELL责任。
        self._cash_plan=None  # 原BUY当日固定的份数目标；只保存策略意图，成交与现金由WT拥有。
        self._fees={}  # 已核SHA的绑定费用模板，用于下单成本上界，不替代原生实际费用。
        self._market={}
        self._atr=None
        if self._value['strategy']['strategy_version']==CONFIRM_VERSION:
            from guanheng_strategy_original.kc50_confirmation import START, allocation, market_state

            self._market={_day(day):state for day,state in market_state(self._value['history'],self._value['calendar']) if day>=START}
            self._allocation=allocation
            self._atr=AtrProtection(self._value['history'],START)
        self._signals={}
        for code,rows in self._value['reference_report']['trades_by_code'].items():
            for row in rows:self._signals.setdefault(_day(row['date']),[]).append(dict(code=code,**row))

    def _guard(self,porter):_need(get_ident()==self._owner and porter is self._porter and self._started)

    def _initialize(self,porter):
        self._guard(porter);_need(not self._initialized and not porter.targets())
        _need(asdict(porter.funds())==dict(net=0,realized=0,dynamic=0,fees=0))
        for native in self._mapping.values():
            position=porter.position(native);_need(position.total==0 and position.valid==0 and position.first_entry==0)
            # 初始化统一注册全部真实行情（未来上市者可返回空），让原引擎在首bar时推进游标。
            # 闭合前不重复读取空slice；首根闭合回调后即具备消费资格，不增加策略预热。
            porter.get_bars(native,'d1',2,main=native==self._mapping['510300' if '510300' in self._codes else self._codes[0]])
            porter.subscribe_bars(native,'d1')
        _need(not porter.load_userdata(STATE_KEY));self._initialized=True

    def _loader(self,symbol,period):
        _need(period=='d1' and symbol in self._series);return self._series[symbol]

    def _on_bar(self,porter,symbol,period,bar):
        self._guard(porter);_need(period=='d1' and symbol in self._series and bar in self._series[symbol])
        self._closed_dates[symbol].add(bar.date)

    def _capture(self,porter,day):
        before=porter.targets();projection=dict(before);_need(len(projection)==len(before) and set(projection)<=set(self._series))
        positions=[];prices=[];actual={};pending=False;market=Fraction(0)
        for code,native in self._mapping.items():
            raw=porter.position(native);total=_quantity(raw.total);valid=_quantity(raw.valid);_need(valid<=total)
            quantity=total if raw.first_entry else 0;actual[code]=quantity
            pending=pending or projection.get(native,quantity)!=quantity
            prefix=tuple(bar for bar in self._series[native] if bar.date<=day)
            # 原DLL对已缓存cursor0的重复空slice读取存在下溢；本owner只消费原bar回调
            # 确认的完整闭合前缀。上市前保持无价格，首个真实bar由引擎推进后正常消费。
            if prefix:
                _need(prefix[-1].date in self._closed_dates[native])
                got=porter.get_bars(native,'d1',4096).bars
                if got!=prefix:
                    raise SessionError('original_native_prefix_mismatch:'+native+':'+str(day)+':'+str(len(got))+':'+str(len(prefix)))
                price=porter.get_price(native)
                if price==0:_need(quantity==0);price=None
                elif price!=prefix[-1].close:
                    raise SessionError('original_native_price_mismatch:'+native+':'+str(day))
            else:_need(quantity==0);price=None
            if quantity:market+=quantity*Fraction(repr(float(price)))
            positions.append(asdict(raw));prices.append([native,price])
        funds=asdict(porter.funds());_need(porter.targets()==before)
        nav=Fraction(1000000)+Fraction(repr(float(funds['net'])));cash=nav-market
        capture=dict(session_id=self._session_id,sequence=len(self._records)+1,trading_date=day,minute=1500,
            projection=[list(item) for item in before],positions=positions,prices=prices,funds=funds,
            basis=dict(observed_at=datetime.strptime(str(day)+'1500','%Y%m%d%H%M').replace(tzinfo=ZONE).isoformat(),
                input_sha256=self._input_id,nav_cny=_decimal(nav),cash_cny=_decimal(cash),pnl_cny=repr(float(funds['net'])),
                capital_source='explicit-genesis-plus-WT-net',cash_source='WT-NAV-minus-complete-actual-position-value',
                price_basis=self._value['price_basis']))
        return capture,actual,pending

    def _calculate(self,porter,day,minute):
        if self._value['strategy']['strategy_version']!=LEGACY_VERSION:
            return self._calculate_cash(porter,day,minute)
        self._guard(porter);_need(self._initialized and minute==1500 and day in self._days and (not self._records or day>self._records[-1]['trading_date']))
        capture,actual,pending=self._capture(porter,day);signals=self._signals.get(day,[])
        nav=_money(capture['basis']['nav_cny']);cash=_money(capture['basis']['cash_cny'])
        targets=dict(actual);status='holding';reason='沿原生已成交份数保持';vector=[];readback=[]
        old_projection=dict(capture['projection'])
        self._sell_intents={code for code in self._sell_intents if actual[code]>0 or old_projection.get(self._mapping[code],0)>0}
        for signal in signals:
            code=signal['code']
            if signal['action']=='BUY':
                self._buy_intents.add(code);self._sell_intents.discard(code)
            else:self._sell_intents.add(code);self._buy_intents.discard(code)
        if (self._buy_intents or self._sell_intents) and not pending:
            frozen={code:actual[code]-_quantity(next(p['valid'] for p in capture['positions'] if p['symbol']==self._mapping[code])) for code in self._codes}
            # T+1先按原生可卖量减持，剩余意图延后；不把拒绝后的partial当成功。
            for code in self._sell_intents:targets[code]=frozen[code]
            active=({code for code,qty in actual.items() if qty>0}|self._buy_intents)-self._sell_intents
            if self._buy_intents and cash>=0 and nav>_money(self._value['fee_reserve_cny']):
                today={code:next((bar for bar in self._series[native] if bar.date==day),None) for code,native in self._mapping.items()}
                visible_prices=dict(capture['prices'])
                if all(today[code] is not None and visible_prices[self._mapping[code]] is not None for code in active):
                    budget=(nav-_money(self._value['fee_reserve_cny']))/len(active) if active else Fraction(0)
                    desired=dict(targets)
                    for code in active:desired[code]=int(budget/Fraction(repr(float(today[code].close)))/100)*100
                    if all(desired[code]>=frozen[code] for code in self._codes):
                        targets=desired;self._buy_intents.clear()
                        status='buy_targets_submitted';reason='当日已知净值与价格等权；原生可卖约束满足后下一tick撮合'
                    else:status='deferred_T1';reason='等权减持涉及当日冻结份额，保留原BUY意图等待T+1可卖'
                else:status='blocked_missing_price';reason='目标证券缺少D日价格，新买保持未执行'
            elif self._buy_intents:status='cash_deficit' if cash<0 else 'insufficient_budget';reason='现金或显式费用预留不足，保留原BUY意图'
            else:
                status='deferred_T1' if any(frozen[c] for c in self._sell_intents) else 'sell_targets_submitted'
                reason='SELL按原生可卖量释放，冻结余额顺延；其他份数保持'
            if targets!=actual:
                vector=[dict(symbol=self._mapping[code],quantity=targets[code]) for code in self._codes]
                readback=[list(x) for x in porter.submit_targets(tuple(Target(x['symbol'],x['quantity']) for x in vector),'original-WT-standard')]
        elif pending:status='pending_native_execution';reason='原生pending尚未成交，保留其责任'
        text=_encode(dict(schema='guanheng.original-native-state.v1',session_id=self._session_id,sequence=len(self._records)+1,
            buy_intents=sorted(self._buy_intents),sell_intents=sorted(self._sell_intents))).decode('ascii')
        porter.store_userdata(STATE_KEY,text);self._last_userdata=text
        self._records.append(dict(trading_date=day,minute=1500,status=status,reason=reason,capture=capture,
            signals=signals,submit_vector=vector,readback=readback,cash_deficit=cash<0,result=None,outcome=None,previous_status=None))

    def _buy_bound(self,code,quantity,price):
        """原生每笔费用的向上成本界；多明细费用不用于买入开仓，预留1分覆盖分位舍入。"""
        fee=self._fees.get(self._mapping[code].rsplit('.',1)[0])
        if fee is None:return quantity*price
        rate=Fraction(repr(float(fee['open'])))
        commission=rate*quantity*(1 if fee['byvolume'] else price)
        commission=max(commission,Fraction(repr(float(fee.get('minfee',0))))) if rate else Fraction(0)
        return quantity*price+commission+Fraction(1,100)

    def _sell_floor(self,code,quantity):
        """确保原生每笔卖出净流入非负；不用未来成交价或未成交卖出款。"""
        fee=self._fees.get(self._mapping[code].rsplit('.',1)[0])
        if fee is None:return Fraction(1,1000000)
        rate=max(Fraction(repr(float(fee[k]))) for k in ('close','closetoday'))
        # 原生按明细逐笔收费；本模型每次新增至少100份，每个关闭明细至少100份。
        minimum=Fraction(repr(float(fee.get('minfee',0))))
        if fee['byvolume']:return max(rate+(minimum+Fraction(1,100))/100,Fraction(1,1000000))
        _need(rate<1)
        return max((minimum+Fraction(1,100))/(100*(1-rate)),Fraction(1,1000000))

    def _calculate_cash(self,porter,day,minute):
        self._guard(porter);_need(self._initialized and minute==1500 and day in self._days and (not self._records or day>self._records[-1]['trading_date']))
        capture,actual,pending=self._capture(porter,day);signals=self._signals.get(day,[])
        cash=_money(capture['basis']['cash_cny']);nav=_money(capture['basis']['nav_cny']);_need(cash>=0)
        available=max(Fraction(0),cash-1)  # 实际现金仅扣一元浮点/费用舍入余量；未成交销售从不计入。
        control=dict(available_cash_cny=_decimal(available),reserved_buy_cost_cny='0',orders=[])
        targets=dict(actual);status='holding';reason='沿原生实际持仓保持';vector=[];readback=[]
        self._sell_intents={code for code in self._sell_intents if actual[code]>0}
        exits=[]
        if self._atr is not None:
            date=datetime.strptime(str(day),'%Y%m%d').date().isoformat()
            exits=list(self._atr.exits(date,actual,signals,self._sell_intents))
        style=None
        if self._cash_plan is not None and all(actual[c]==q for c,q in self._cash_plan.items()):
            self._cash_plan=None;self._buy_intents.clear()
        for signal in signals+exits:
            code=signal['code']
            if signal['action']=='BUY':
                self._buy_intents.add(code);self._sell_intents.discard(code);self._cash_plan=None
            else:
                self._sell_intents.add(code);self._buy_intents.discard(code)
                if self._cash_plan is not None:self._cash_plan[code]=0
        frozen={code:actual[code]-_quantity(next(p['valid'] for p in capture['positions'] if p['symbol']==self._mapping[code])) for code in self._codes}
        prices={code:Fraction(repr(float(price))) for native,price in capture['prices'] if price is not None for code in self._codes if self._mapping[code]==native}
        if not pending:
            if self._buy_intents and self._cash_plan is None:
                active=({c for c,q in actual.items() if q>0}|self._buy_intents)-self._sell_intents
                if active and all(c in prices and any(b.date==day for b in self._series[self._mapping[c]]) for c in active):
                    budget=max(Fraction(0),nav-_money(self._value['fee_reserve_cny']))
                    weights=dict.fromkeys(active,1)
                    if day in self._market:
                        weights,style=self._allocation(self._market[day],active)
                    total_weight=sum(weights.values())
                    self._cash_plan={c:(int(budget*weights[c]/total_weight/prices[c]/100)*100 if c in active else 0) for c in self._codes}
                else:status='blocked_missing_price';reason='原BUY目标缺少当日已闭合价格，保留意图'
            if self._cash_plan is not None:targets={c:max(q,frozen[c]) for c,q in self._cash_plan.items()}
            for c in self._sell_intents:targets[c]=frozen[c]
            increases={c:targets[c]-actual[c] for c in self._codes if targets[c]>actual[c]}
            full_cost=sum((self._buy_bound(c,q,prices[c]) for c,q in increases.items()),Fraction(0))
            scale=min(Fraction(1),available/full_cost) if full_cost else Fraction(1)
            limits=[];reserved=Fraction(0)
            for c in self._codes:
                if c in increases:
                    q=int(increases[c]*scale/100)*100
                    while q and reserved+self._buy_bound(c,q,prices[c])>available:q-=100
                    targets[c]=actual[c]+q
                    if q:
                        bound=self._buy_bound(c,q,prices[c]);reserved+=bound
                        limits.append((self._mapping[c],float(prices[c])))
                        control['orders'].append(dict(symbol=self._mapping[c],action='BUY',quantity=q,
                            limit_price_cny=_decimal(prices[c]),buy_cost_bound_cny=_decimal(bound)))
                elif targets[c]<actual[c]:
                    floor=self._sell_floor(c,actual[c]-targets[c])
                    # 向上转换保证浮点限价仍覆盖精确费用界。
                    import math
                    limit=math.nextafter(float(floor),math.inf)
                    limits.append((self._mapping[c],limit))
                    control['orders'].append(dict(symbol=self._mapping[c],action='SELL',quantity=actual[c]-targets[c],
                        limit_price_cny=_decimal(Fraction(repr(limit))),buy_cost_bound_cny='0'))
            control['reserved_buy_cost_cny']=_decimal(reserved);_need(reserved<=available)
            if limits:
                vector=[dict(symbol=self._mapping[c],quantity=targets[c]) for c in self._codes]
                readback=[list(x) for x in porter.submit_conditional_targets(tuple(Target(x['symbol'],x['quantity']) for x in vector),tuple(limits),'original-WT-cash-limit')]
                status='cash_limited_conditions_submitted';reason='当前实际现金覆盖全部买入本金及绑定费用上界；原生限价撮合，未成交意图顺延'
            elif self._cash_plan is not None or self._buy_intents or self._sell_intents:
                status='deferred_T1' if any(frozen.values()) else 'waiting_cash_or_lot'
                reason='保留原信号份数意图；等待原生可卖份额、实际卖出回款或整手预算'
        else:status='pending_native_execution';reason='保留原生已触发未成交责任，不重复预占或下单'
        if exits:reason='ATR 退出：'+'、'.join(item['reason'] for item in exits)+'。'+reason
        if style:reason=f'风格权重：{style}。'+reason
        text=_encode(dict(schema='guanheng.original-native-state.v2',session_id=self._session_id,sequence=len(self._records)+1,
            buy_intents=sorted(self._buy_intents),sell_intents=sorted(self._sell_intents),cash_plan=self._cash_plan)).decode('ascii')
        porter.store_userdata(STATE_KEY,text);self._last_userdata=text
        self._records.append(dict(trading_date=day,minute=1500,status=status,reason=reason,capture=capture,signals=signals,
            submit_vector=vector,readback=readback,cash_deficit=False,cash_control=control,result=None,outcome=None,previous_status=None))

    def run(self,library,abi_probe,config):
        _need(get_ident()==self._owner and not self._started and type(config) is BacktestConfig)
        _need(config.start//10000==self._days[0] and config.start%10000<=1500 and config.end==self._days[-1]*10000+1500)
        self._started=True;identities,frozen=admit_native_files(self._mapping,config)
        self._fees=json.loads(frozen['fees'])
        if self._value['strategy']['strategy_version']!=LEGACY_VERSION:
            for rule in self._fees.values():
                _need(rule['byvolume'] or max(rule['close'],rule['closetoday'])<1)
        base=Path(config.cwd)/'session-basefiles';base.mkdir(exist_ok=False)
        for name,raw in frozen.items():(base/(name+'.json')).write_bytes(raw)
        config=replace(config,**{name:base/(name+'.json') for name in frozen})
        self._session_id=session_identity(self._input_id,config.cwd,config.start,config.end,config.name,identities)
        porter=self._porter=BacktestPorter(library,ORIGINAL_BT_SHA256,abi_probe,ABI_PROBE_SHA256,
            symbols=tuple(sorted(self._series)),execution_symbols=tuple(sorted(self._series)),max_execution_symbols=9,
            loader=self._loader,callbacks=Callbacks(self._initialize,self._calculate,self._on_bar))
        porter.configure(config)
        try:counts=porter.run()
        finally:porter.release()
        _need([r['trading_date'] for r in self._records]==list(self._days[1:]))
        output=Path(config.output)/config.name
        _need(json.loads((output/('ud_'+config.name+'.json')).read_bytes())=={STATE_KEY:self._last_userdata})
        files=[]
        for name in ('funds.csv','positions.csv','trades.csv','closes.csv','signals.csv',config.name+'.json','ud_'+config.name+'.json'):
            path=output/name;_need(path.is_file() and path.stat().st_size<=32*1024*1024)
            files.append([name,hashlib.sha256(path.read_bytes()).hexdigest()])
        report=dict(schema=REPORT_SCHEMA,session_id=self._session_id,input_sha256=self._input_id,scope=REPORT_SCOPE,
            policy=self._value['policy'],configuration_sha256=configuration_id(self._value),strategy_id=self._value['strategy']['strategy_id'],strategy_version=self._value['strategy']['strategy_version'],
            signal_algorithm_id=ALGORITHM_ID,historical_model=model_for_version(self._value['strategy']['strategy_version']),reference_report_sha256=self._value['reference_report_sha256'],
            execution_model=model_for_version(self._value['strategy']['strategy_version']),evaluation_window=self._value['evaluation_window'],
            source_snapshot_sha256=self._value['source_snapshot_sha256'],status=self._records[-1]['status'],native_files=[list(x) for x in identities],
            native_outputs=files,callback_counts=[list(x) for x in counts],records=self._records,source_qualified=False,
            execution_qualified=False,point_in_time_qualified=False)
        return validate_report(report).to_dict()


def verify_host_report(report,payload,*,directory,start,end,name,basefiles):
    """父owner绑定冻结输入、执行窗口和原生会话；不信任子进程自报经济身份。"""
    value=verify_report_input(report,payload);input_id=_digest(value)
    _need(report['session_id']==session_identity(input_id,directory,start,end,name,report['native_files']))
    _need(start//10000==_day(value['calendar'][0]) and end==_day(value['calendar'][-1])*10000+1500)
    _need([r['trading_date'] for r in report['records']]==[_day(d) for d in value['calendar'][1:]])
    _need(dict(report['native_files'])=={key:row['sha256'] for key,row in basefiles.items()})
