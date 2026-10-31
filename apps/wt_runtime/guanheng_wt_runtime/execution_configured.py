"""固定configured业务到原CTA的薄接线；算法、数量规则和金融账目沿原owner。"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from .execution_process import ExecutionProcessConfig, _PYTHON_PACKAGES, _python_bytes, _python_inventory, _python_packages
from .execution_strategy import CtaRuntime, StrategyBinding, _need
from .managed_local_process import _inspect, _json, _read


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False, default=str).encode('ascii')


def _digest(value):
    return hashlib.sha256(_encode(value)).hexdigest()


def _quantity(value):
    _need(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 9007199254740900
          and value % 100 == 0, 'native_quantity')
    return int(value)


def _replace_projection(temporary, target, deadline):
    """Windows读者持有旧文件时替换可报5/32/33；沿本轮D等待原句柄释放。

    本函数只发布本宿主独占的观察投影。失败保留最后原生错误及pending文件，
    调用方沿既有health停止；原持仓/KV及已发生setter继续由原owner持有。
    """
    last_error = None
    while True:
        if time.monotonic() >= deadline:
            if last_error is not None:
                raise last_error
            _need(False, 'evaluation_deadline')
        try:
            temporary.replace(target)
            return
        except OSError as error:
            if getattr(error, 'winerror', None) not in (5, 32, 33):
                raise
            last_error = error
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(.002, remaining))


def _state_fields(cls, value):
    _need(type(value) is dict and set(value) == set(cls.__dataclass_fields__), 'quantity_state_fields')
    return dict(value)


def _restore_quantity_state(value):
    """只重建NSQ原公开值，让其构造器复核冻结阶段；本接缝不计算数量。"""
    if value is None:
        return None
    from guanheng_strategy_native import Basis, EconomicTarget, Price, Quantity, QuantityPolicy, StageState, Weight

    def rows(cls, values):
        _need(type(values) is list and 1 <= len(values) <= 8, 'quantity_state_rows')
        return tuple(cls(**_state_fields(cls, item)) for item in values)

    state = _state_fields(StageState, value)
    target = _state_fields(EconomicTarget, state['target'])
    _need(type(target['universe']) is list and 1 <= len(target['universe']) <= 8, 'quantity_state_rows')
    target['universe'] = tuple(target['universe'])
    target['weights'] = rows(Weight, target['weights'])
    state['target'] = EconomicTarget(**target)
    state['policy'] = QuantityPolicy(**_state_fields(QuantityPolicy, state['policy']))
    basis = _state_fields(Basis, state['basis']);basis['prices'] = rows(Price, basis['prices'])
    state['basis'] = Basis(**basis)
    for key in ('starts', 'targets'):
        state[key] = rows(Quantity, state[key])
    return StageState(**state)


@dataclass(frozen=True)
class RetainedRuntimeInput:
    """固定当前决策输入；本金显式，实际周期来源由接入owner核实。"""
    request: object
    policy: object
    fee_reserve_cny: str | None
    fee_source: str | None
    market_manifest_source: str
    schema: str = 'guanheng.retained-cta-input.v1'

    @classmethod
    def from_dict(cls, value):
        from guanheng_strategy_v1 import RetainedInput
        from guanheng_strategy_native import Basis, Price, QuantityPolicy
        _need(type(value) is dict and set(value) == set(cls.__dataclass_fields__)
              and value['schema'] == 'guanheng.retained-cta-input.v1', 'retained_input')
        data = dict(value)
        data['request'] = RetainedInput.from_dict(data['request'])
        _need(type(data['policy']) is dict, 'retained_policy')
        data['policy'] = QuantityPolicy(**data['policy'])
        source = data['market_manifest_source']
        _need(type(source) is str and 1 <= len(source) <= 256
              and all(32 <= ord(c) <= 126 for c in source), 'market_source')
        from guanheng_strategy_v1 import SYMBOLS
        Basis(data['request'].decision_cutoff.isoformat(), '0'*64, data['policy'].initial_capital_cny,
              '0', data['policy'].initial_capital_cny, data['fee_reserve_cny'], 'preflight',
              'preflight', data['fee_source'], tuple(Price(s, None, source) for s in SYMBOLS), False, 'preflight')
        return cls(**data)


class RetainedStrategy:
    """唯一1.1.2实时薄桥。周期元数据存原KV，数量只读取原owner。

    首次已核周期可连续部分增减/清仓；新开仓起点缺少实际来源时等待。
    新周期仅消费原管理成交的源时间；缺少完整事实时保持等待。
    """
    def __init__(self, item, publish, configuration, native, *, deadline, code_identity):
        from guanheng_strategy_v1 import SYMBOLS
        from .retained_evaluation import evaluate_retained
        from guanheng_strategy_core.contracts import EvaluationBudget
        from .execution_facts import admit_native_files
        _need(type(native.get('strategies')) is list and len(native['strategies'])==1, 'retained_cycle_scope')
        parameters = item['parameters'].get('python_strategy')
        required = {'schema','input_file','input_sha256','main_symbol','evaluation_seconds','broker_max_age_seconds'}
        _need(type(parameters) is dict and required <= set(parameters) <= required | {'market_window'}
              and parameters['schema'] == 'guanheng.retained-cta.v1'
              and item['id'] == 'resonance-regime-v1', 'strategy_profile')
        executer = native.get('executer',{})
        policies = executer.get('policy',{}) if type(executer) is dict else {}
        _need(type(executer) is dict and type(policies) is dict and 'default' in policies
              and type(executer.get('scale')) in (int,float) and executer['scale'] == 1
              and executer.get('strict_sync',False) is False and executer.get('groups',{}) == {}
              and type(executer.get('clear',{})) is dict
              and executer.get('clear',{}).get('active',False) is False, 'retained_cash_executor')
        for rule in policies.values():
            _need(type(rule) is dict and rule.get('name') in ('WtExeFact.WtStockMinImpactExeUnit',
                                              'WtExeFact.WtStockMinImpactBorrowedExeUnit')
                  and type(rule.get('min_order')) in (int,float) and rule['min_order'] == 100
                  and rule.get('is_cancel_unmanaged_order') is False, 'retained_cash_executor')
        self.seconds, self.max_age = parameters['evaluation_seconds'], parameters['broker_max_age_seconds']
        _need(type(self.seconds) in (int,float) and math.isfinite(self.seconds) and .1 <= self.seconds <= 5,
              'evaluation_budget')
        _need(type(self.max_age) in (int,float) and math.isfinite(self.max_age) and 1 <= self.max_age <= 3600,
              'broker_age_budget')
        path = Path(parameters['input_file']);_need(path.is_absolute(), 'strategy_input')
        raw = _read(path, 16*1024*1024, clock=time.monotonic, deadline=deadline)
        self.input_sha = hashlib.sha256(raw).hexdigest()
        _need(self.input_sha == parameters['input_sha256'], 'strategy_input_identity')
        self.inputs = RetainedRuntimeInput.from_dict(_json(raw))
        from .execution_market_window import MarketWindowFile
        self.market_window = MarketWindowFile.from_dict(parameters['market_window']) if 'market_window' in parameters else None
        self.recovery = configuration.recovery_mode
        _need(self.recovery in ('record_clean','resume_clean'), 'retained_recovery_required')
        now = datetime.now(timezone.utc)
        _need(self.inputs.request.decision_cutoff <= now, 'initial_cycle_window')
        if self.recovery != 'resume_clean':
            _need(self.inputs.request.cycles_captured_at <= now < self.inputs.request.cycles_valid_until,
                  'initial_cycle_window')
        admitted = evaluate_retained(self.inputs.request, self.inputs.policy,
                                    budget=EvaluationBudget(max_seconds=min(self.seconds, max(.001,deadline-time.monotonic()))))
        self.config_identity, self.algorithm_identity = admitted.target.config_id, admitted.target.algorithm_id
        self.id, self.publish, self.execution = item['id'], publish, tuple(SYMBOLS)
        self.mapping = {s:('SSE' if s.endswith('.SH') else 'SZSE')+'.ETF.'+s[:6] for s in self.execution}
        self.reads = self.targets = tuple(sorted(self.mapping.values()))
        self.main = parameters['main_symbol'];_need(self.main in self.reads, 'main_symbol')
        root = configuration.installation/'app';expected = dict(configuration.artifacts)
        names = {n:native['base_data'][n] for n in ('sessions','commodities','contracts','holidays')}
        names['fees'] = native['environment'].get('fees')
        paths = {}
        for name,relative in names.items():
            _need(type(relative) is str and relative, 'native_cash_model')
            path = root/relative
            _need(path.is_relative_to(root) and '..' not in path.parts, 'native_cash_model')
            data = _read(path, 1024*1024, clock=time.monotonic, deadline=deadline)
            _need(hashlib.sha256(data).hexdigest() == expected.get('app/'+path.relative_to(root).as_posix()),
                  'native_cash_model_identity')
            paths[name] = path
        identities, frozen = admit_native_files(self.mapping, SimpleNamespace(**paths))
        _need(all(hashlib.sha256(frozen[n]).hexdigest() == expected.get('app/'+paths[n].relative_to(root).as_posix())
                  for n,_ in identities) and time.monotonic() < deadline, 'native_cash_model_identity')
        self.takeover = 'takeover' in native
        identity = (self.id, self.input_sha, tuple(sorted(self.mapping.items())), asdict(self.inputs.policy), code_identity)
        if self.market_window is not None:
            identity += (self.market_window.configuration_identity,)
        self.state_identity = _digest(identity)
        self.state, self.sequence, self.initialized = None, 0, False
        self.cycles, self.exits = {}, ()
        self.flat_sources = {}
        self.restored_state_id, self.restored_sequence = None, None

    def binding(self):
        return StrategyBinding(self.id, self.main, self.reads, self.targets, self.callback)

    @staticmethod
    def _shares(value):
        _need(type(value) in (int,float) and math.isfinite(value) and 0 <= value <= 9007199254740991
              and int(value) == value, 'native_quantity')
        return int(value)

    def _metadata(self, value):
        _need(type(value) is dict and set(value) <= set(self.execution), 'cycle_metadata')
        result = {}
        for symbol,item in value.items():
            _need(type(item) is dict, 'cycle_metadata')
            initial = item.get('status') == 'initial_inventory'
            fields = {'status','cycle_id','baseline_at','source_sha256'} if initial else {'cycle_id','opened_at','source_sha256'}
            _need(set(item) == fields, 'cycle_metadata')
            key, source = item['cycle_id'],item['source_sha256']
            _need(type(key) is str and 1 <= len(key) <= 256 and all(32 <= ord(c) <= 126 for c in key)
                  and type(source) is str and len(source) == 64 and all(c in '0123456789abcdef' for c in source),
                  'cycle_metadata')
            opened = datetime.fromisoformat(item['baseline_at' if initial else 'opened_at'])
            _need(opened.utcoffset() is not None and opened <= datetime.now(timezone.utc), 'cycle_metadata')
            result[symbol] = dict(item)
        return result

    def _exit_values(self, values):
        from guanheng_strategy_v1 import CycleExit
        _need(type(values) is list and len(values) <= 8, 'cycle_exits')
        exits = []
        for value in values:
            _need(type(value) is dict and set(value) == {'symbol','cycle_id','trade_date','path'}
                  and value['symbol'] in self.execution, 'cycle_exits')
            for key in ('cycle_id','path'):
                _need(type(value[key]) is str and 1 <= len(value[key]) <= 256
                      and all(32 <= ord(c) <= 126 for c in value[key]), 'cycle_exits')
            exits.append(CycleExit(value['symbol'],value['cycle_id'],date.fromisoformat(value['trade_date']),value['path']))
        _need(len({e.symbol for e in exits}) == len(exits), 'cycle_exits')
        return tuple(exits)

    def _state_payload(self, state, sequence, metadata, exits):
        value = dict(schema='guanheng.retained-quantity-state.v1', strategy_id=self.id, identity=self.state_identity,
                     sequence=sequence, state=None if state is None else asdict(state),
                     state_id=_digest(None) if state is None else state.state_id,
                     cycles=metadata, exits=[asdict(e) for e in exits])
        raw = _encode(value);_need(len(raw) <= 32768, 'quantity_state_capacity')
        return raw.decode('ascii')

    def _load_state(self, text):
        _need(type(text) is str and 1 <= len(text) <= 32768, 'quantity_state_missing')
        value = _json(text.encode('ascii'))
        _need(set(value) == {'schema','strategy_id','identity','sequence','state','state_id','cycles','exits'}
              and value['schema'] == 'guanheng.retained-quantity-state.v1' and value['strategy_id'] == self.id
              and value['identity'] == self.state_identity, 'quantity_state_identity')
        seq = value['sequence'];_need(type(seq) is int and 0 <= seq <= 9007199254740991, 'quantity_state_sequence')
        state = _restore_quantity_state(value['state'])
        if state is not None:
            _need(state.policy == self.inputs.policy and state.target.strategy_id == self.id
                  and state.target.universe == self.execution and state.target.config_id == self.config_identity
                  and state.target.algorithm_id == self.algorithm_identity, 'quantity_state_identity')
        metadata, exits = self._metadata(value['cycles']), self._exit_values(value['exits'])
        _need(self._state_payload(state,seq,metadata,exits) == text, 'quantity_state_encoding')
        self.state, self.sequence, self.cycles, self.exits = state, seq, metadata, exits
        self.restored_state_id, self.restored_sequence = None if state is None else state.state_id, seq

    def _broker_rows(self, broker):
        rows = {}
        for row in broker.positions:
            _need(row.is_long and row.symbol in self.targets and row.symbol not in rows, 'broker_scope')
            total, valid = self._shares(row.quantity), self._shares(row.sellable)
            _need(valid <= total, 'broker_quantity')
            rows[row.symbol] = (total,valid)
        return rows

    def _initialize(self, context):
        broker = context.broker_observation()
        _need(broker.positions_known, 'broker_unknown')
        rows = self._broker_rows(broker)
        if self.recovery == 'resume_clean':
            self._load_state(context.load_quantity_state())
            # 原单已由运行owner撤清并重查P/A；保留周期/止损和退出记忆，重新规划执行。
            self.state = None
        else:
            _need(context.facts().fund_pnl == 0, 'takeover_mark_required')
            text = context.load_quantity_state()
            if self.takeover:
                _need(_json(text.encode('ascii')) == {'schema':'guanheng.retained-init.v1','input_sha256':self.input_sha},
                      'retained_initial_state')
            else:
                _need(text == '' and not rows, 'fresh_strategy_required')
            metadata = {}
            for cycle in self.inputs.request.cycles:
                code = self.mapping[cycle.symbol];total,valid = rows.get(code,(0,0));p = context.position(code)
                _need(total == cycle.quantity and p.raw_position == total and p.raw_valid == valid,
                      'initial_broker_position')
                if total:
                    initial = cycle.status == 'initial_inventory'
                    origin = cycle.baseline_at if initial else cycle.opened_at
                    _need(cycle.status in ('held','initial_inventory') and origin is not None, 'initial_cycle_position')
                    opened = origin.astimezone(ZoneInfo('Asia/Shanghai'))
                    _need(p.first_entry == int(opened.strftime('%Y%m%d%H%M')),
                          'initial_cycle_position')
                    metadata[cycle.symbol] = dict(cycle_id=cycle.cycle_id,source_sha256=cycle.source_sha256)
                    if initial:
                        metadata[cycle.symbol].update(status='initial_inventory',baseline_at=origin.isoformat())
                    else:
                        metadata[cycle.symbol]['opened_at'] = origin.isoformat()
                else:
                    _need(cycle.status == 'flat' and p.first_entry == p.last_entry == 0, 'fresh_strategy_required')
            self.cycles, self.exits = self._metadata(metadata), tuple(self.inputs.request.previous_exits)
        trades=context.broker_trades()
        self.flat_sources={symbol:self._flat_source(symbol,broker,trades) for symbol in self.execution
                           if not rows.get(self.mapping[symbol],(0,0))[0]}
        # 原主K线触发规则保持，用户状态由原dirty保存流程落盘。
        context.bars(self.main,'m1',1,main=True)
        if self.recovery != 'resume_clean':
            context.store_quantity_state(self._state_payload(None,0,self.cycles,self.exits))
        self.initialized = True
        print('CTA retained strategy initialized',flush=True)
        print('CTA retained strategy initialized',file=sys.stderr,flush=True)

    def _flat_source(self,symbol,broker,trades):
        if trades is None or not trades.known or trades.submission_revision is None:return None
        return {'submission_revision':trades.submission_revision,
                'source_sha256':_digest(('guanheng.actual-flat-source.v1',self.state_identity,symbol,
                                         broker.position_revision,broker.position_received_ms))}

    def _track_flat_source(self,symbol,broker,trades,previous_cycle):
        # NSQ原冻结目标已交setter后，P尚为空不能把已提交开仓移到锚点之前。
        # 没有这一责任时，每次新flat P都成为新的来源下界，旧往返成交随之退出。
        opening_target=self.state is not None and any(q.symbol==symbol and q.shares>0 for q in self.state.targets)
        if previous_cycle is not None or not opening_target:
            self.flat_sources[symbol]=self._flat_source(symbol,broker,trades)

    def _opening_cycle(self,symbol,broker,trades,cutoff,check):
        source=self.flat_sources.get(symbol)
        if source is None or trades is None or not trades.known or trades.submission_revision is None:return None
        latest=min(cutoff,datetime.fromtimestamp(broker.position_received_ms/1000,timezone.utc))
        candidates=[]
        for row in trades.trades:
            check()
            if not (row.symbol==self.mapping[symbol] and row.is_buy and row.user_tag and row.first_live_revision
                    and source['submission_revision']<row.submission_revision<=trades.submission_revision):continue
            day=datetime.strptime(str(row.trade_date),'%Y%m%d');clock=row.trade_time
            opened=day.replace(hour=clock//10000000,minute=clock//100000%100,second=clock//1000%100,
                               microsecond=clock%1000*1000,tzinfo=ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc)
            if opened<=latest:candidates.append((opened,row.trade_id,row))
        if not candidates:return None
        opened,unused,row=min(candidates,key=lambda item:(item[0],item[1]))
        return dict(cycle_id='native-open:'+_digest((symbol,source['source_sha256'])),
                    opened_at=opened.isoformat(),
                    source_sha256=_digest(('guanheng.actual-opening-source.v1',source,asdict(row))))

    def _capture(self, context, prices, cutoff, result_sha, *, price_source=None):
        from guanheng_strategy_native import Basis, NativePosition, Observation, Price
        from .execution_facts import _decimal
        raw, positions = [], []
        for symbol in self.execution:
            p = context.position(self.mapping[symbol]);total = self._shares(p.raw_position)
            actual = total if p.first_entry else 0
            # 空仓财务观察不消费理论可卖字段；原始值保留，执行可卖仍来自券商P。
            _need(type(p.raw_valid) in (int,float) and math.isfinite(p.raw_valid), 'native_quantity')
            valid = self._shares(p.raw_valid) if actual else 0
            _need(valid <= total and (p.first_entry == 0) == (p.last_entry == 0) and p.last_entry >= p.first_entry,
                  'native_entries')
            _need(not p.first_entry or total > 0, 'native_entries')
            wanted = actual if p.enum_target is None else self._shares(p.enum_target)
            positions.append(NativePosition(symbol,actual,valid if actual else 0,wanted if wanted != actual else None))
            raw.append((symbol,asdict(p)))
        facts = context.facts();_need(math.isfinite(facts.fund_pnl), 'native_funds')
        identity = _digest((self.id,self.sequence,raw,prices,asdict(facts)))
        nav = Fraction(self.inputs.policy.initial_capital_cny)+Fraction(repr(facts.fund_pnl))
        cash = nav-sum((p.actual*Fraction(repr(prices[p.symbol])) for p in positions),Fraction(0))
        basis = Basis(cutoff.isoformat(),result_sha,_decimal(nav),repr(facts.fund_pnl),_decimal(cash),
                      self.inputs.fee_reserve_cny,'original-CTA:explicit-genesis+flag0',
                      'original-CTA:NAV-minus-complete-theoretical-holdings',self.inputs.fee_source,
                      tuple(Price(s,repr(prices[s]),price_source or self.inputs.market_manifest_source) for s in self.execution),True,identity)
        observed = Observation(cutoff.isoformat(),'original-CTA:cash-long-theoretical',tuple(positions),True,identity)
        return facts,raw,basis,observed

    def _execution_capture(self, broker, basis, theoretical):
        """唯一策略的实际数量沿本轮P；原理论账本只承担财务basis与pending信号。

        调用方先核P的新鲜度；同一来源摘要绑定两份观察，避免把理论目标到位
        授为券商成交。原绝对目标准入、活动订单和剩量继续归原执行器。
        """
        from guanheng_strategy_native import NativePosition, Observation
        _need(broker.positions_known, 'broker_unknown')
        rows = self._broker_rows(broker)
        identity = _digest((theoretical.native_observation_id,asdict(broker)))
        positions = tuple(NativePosition(p.symbol,*rows.get(self.mapping[p.symbol],(0,0)),p.pending_target)
                          for p in theoretical.positions)
        return (replace(basis,native_observation_id=identity),
                replace(theoretical,native_observation_id=identity),
                Observation(theoretical.observed_at,'broker-query:complete-position+original-CTA-pending',
                            positions,True,identity))

    def callback(self, context):
        if context.event.kind not in (1,4):return
        if context.event.kind == 1:
            self._initialize(context);return
        _need(self.initialized, 'strategy_not_initialized')
        from guanheng_strategy_core.contracts import EvaluationBudget
        from guanheng_strategy_v1 import PositionCycle
        from .retained_evaluation import evaluate_retained, advance_retained
        deadline = time.monotonic()+self.seconds
        def check():_need(time.monotonic() < deadline, 'evaluation_deadline')
        cutoff = datetime.now(timezone.utc);broker = context.broker_observation();trades=context.broker_trades();check()
        self.sequence += 1
        status, reason, cycles, metadata = None,None,[],dict(self.cycles)
        if not broker.positions_known or broker.position_received_ms is None:
            status, reason = 'waiting_broker_position','broker_position_unknown'
        else:
            received = datetime.fromtimestamp(broker.position_received_ms/1000,timezone.utc)
            if not received <= cutoff < received+timedelta(seconds=self.max_age):
                status, reason = 'waiting_broker_position','broker_position_stale'
        rows = self._broker_rows(broker)
        if status is None:
            source = _digest(asdict(broker))
            for symbol in self.execution:
                quantity = rows.get(self.mapping[symbol],(0,0))[0]
                old = metadata.get(symbol)
                if not quantity:
                    self._track_flat_source(symbol,broker,trades,old)
                    metadata.pop(symbol,None);cycles.append(PositionCycle(symbol,'flat',0,source))
                else:
                    actual=self._opening_cycle(symbol,broker,trades,cutoff,check)
                    if old is None:old=actual
                    elif actual is not None and actual['cycle_id']==old['cycle_id']:
                        if datetime.fromisoformat(actual['opened_at'])<datetime.fromisoformat(old['opened_at']):old=actual
                    if old is None:status, reason = 'waiting_actual_cycle','actual_opening_source_required'
                    else:
                        metadata[symbol]=old
                        initial = old.get('status') == 'initial_inventory'
                        origin = datetime.fromisoformat(old['baseline_at' if initial else 'opened_at'])
                        cycles.append(PositionCycle(symbol,'initial_inventory' if initial else 'held',quantity,
                            _digest((source,old['source_sha256'])),old['cycle_id'],
                            None if initial else origin,origin if initial else None))
        candidate = dict(status=status,reason=reason,sequence=self.sequence,broker_observation=asdict(broker),
                         broker_position_qualified=False,recovery_mode=self.recovery,
                         restored_state_id=self.restored_state_id,restored_sequence=self.restored_sequence)
        candidate['broker_trades']=None if trades is None else asdict(trades)
        candidate['cycle_metadata']=dict(metadata)
        state, exits, vector = self.state,self.exits,()
        if status is None:
            request = replace(self.inputs.request,cycles=tuple(cycles),cycles_captured_at=received,
                              cycles_valid_until=received+timedelta(seconds=self.max_age),decision_cutoff=cutoff,
                              previous_exits=self.exits)
            if self.market_window is not None:
                window = self.market_window.read(request,deadline=deadline);check()
                candidate['market_window'] = window.publication
                if window.request is None:
                    status,reason = 'waiting_market_input',window.reason
                    candidate.update(status=status,reason=reason)
                else:
                    request = window.request
        if status is None:
            check()
            decision = evaluate_retained(request,self.inputs.policy,previous_target=state.target if state else None,
                budget=EvaluationBudget(max_seconds=max(.001,deadline-time.monotonic())))
            result = decision.result.to_dict();check()
            if self.market_window is not None:
                from .execution_market_window import native_history_matches
                if not native_history_matches(request,self.mapping,context,check):
                    status,reason = 'waiting_market_input','market_history_mismatch'
                    candidate.update(status=status,reason=reason)
            else:
                for symbol,code in self.mapping.items():
                    expected = tuple(r for r in request.history.observations if r.symbol == symbol)
                    actual = context.bars(code,'d1',len(expected));check()
                    _need(len(actual) == len(expected), 'native_history')
                    for row,bar in zip(actual,expected,strict=True):
                        _need((row.date,row.open,row.high,row.low,row.close,row.volume,row.money)
                              == (int(bar.trade_date.strftime('%Y%m%d')),bar.open,bar.high,bar.low,bar.close,bar.volume,bar.amount),
                              'native_history')
        if status is None:
            prices = {s:context.price(self.mapping[s]) for s in self.execution}
            _need(all(type(p) in (int,float) and math.isfinite(p) and p > 0 for p in prices.values()), 'native_price')
            price_source = None if self.market_window is None else 'original-CTA:quote;window:'+candidate['market_window']['publication_sha256']
            facts,raw,basis,observed = self._capture(context,prices,cutoff,result['input_sha256'],price_source=price_source)
            basis,observed,execution = self._execution_capture(broker,basis,observed)
            outcome, previous_status = advance_retained(decision.target,self.inputs.policy,execution,basis,state)
            state = outcome.state;exits = self._exit_values(result['next_exits'])
            vector = tuple((self.mapping[t.symbol],t.shares) for t in outcome.submit_targets)
            candidate.update(status=outcome.status,reason=outcome.reason,core_result=result,outcome=asdict(outcome),
                             quantity_basis=asdict(basis),native_observation=asdict(observed),raw_positions=raw,
                             execution_observation=asdict(execution),execution_position_qualified=True,
                             native_clock=asdict(facts),previous_status=previous_status)
            if vector:candidate['target_readback'] = dict(vector)
        # 编码和投影预检共用本轮D，随后才进入原setter/KV副作用。
        text = self._state_payload(state,self.sequence,metadata,exits)
        self.publish(self.id,candidate,preview=True,deadline=deadline);check()
        if vector:
            _need(dict(context.set_targets(vector)) == dict(vector), 'target_readback');check()
        context.store_quantity_state(text);check()
        self.state,self.cycles,self.exits = state,metadata,exits
        self.publish(self.id,candidate,deadline=deadline);check()


def _verify_python(args):
    _need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
          and sys.pycache_prefix == str(args.control / 'python-cache')
          and not (args.control / 'python-cache').exists(), 'isolated_python')
    raw = _read(args.control / 'python-binding.json', 256 * 1024, clock=time.monotonic, deadline=args.deadline)
    _need(hashlib.sha256(raw).hexdigest() == args.python_binding_sha256, 'python_binding')
    value = _json(raw)
    _need(set(value) == {'schema', 'python', 'site_root', 'files'} and value['schema'] == 'guanheng.cta-python-binding.v1'
          and Path(value['python']) == Path(sys.executable), 'python_binding')
    site = Path(value['site_root'])
    _need(site == Path(__file__).absolute().parent.parent, 'python_binding')
    files = value['files']
    _need(type(files) is list and 1 <= len(files) <= 512, 'python_binding')
    seen, total = set(), 0
    for row in files:
        _need(type(row) is list and len(row) == 2 and type(row[0]) is str, 'python_binding')
        path = Path(row[0]);_need(path.is_absolute() and path not in seen, 'python_binding');seen.add(path)
        data = _python_bytes(path, deadline=args.deadline)
        total += len(data);_need(total <= 64 * 1024 * 1024 and hashlib.sha256(data).hexdigest() == row[1], 'python_binding')
    _need(Path(__file__).absolute() in seen and Path(sys._base_executable) in seen, 'python_binding')
    identities = dict(files)
    native = _json(_read(args.config, 256*1024, clock=time.monotonic, deadline=args.deadline))
    _python_inventory(site, identities, packages=_python_packages(native))
    return identities


def main():
    parser = argparse.ArgumentParser(description='观衡固定业务策略原生CTA子进程')
    for name in ('config', 'control', 'installation'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('control-id', 'config-sha256', 'python-binding-sha256'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--deadline', type=float, required=True)
    args = parser.parse_args()
    _need(math.isfinite(args.deadline) and time.monotonic() < args.deadline, 'startup_deadline')
    identities = _verify_python(args)
    config = ExecutionProcessConfig.load(args.installation, args.config, args.control.parent)
    _need(config.configuration_sha256 == args.config_sha256, 'configuration_identity')
    native = _json(_read(args.config, 256 * 1024, clock=time.monotonic, deadline=args.deadline))
    reports = {}

    def publish(strategy_id, value, *, preview=False, deadline):
        def check():
            _need(time.monotonic() < deadline, 'evaluation_deadline')
        check()
        candidate = dict(reports);candidate[strategy_id] = value
        raw = _encode({'schema': 'guanheng.configured-cta-observation.v2',
                       'control_id': args.control_id, 'config_sha256': args.config_sha256,
                       'pid': os.getpid(), 'strategies': candidate})
        _need(len(raw) <= 4 * 1024 * 1024, 'projection_capacity')
        check()
        if preview:
            return
        temporary = args.control / 'strategies.pending'
        with temporary.open('xb') as stream:
            stream.write(raw)
        check()
        _replace_projection(temporary, args.control / 'strategies.json', deadline)
        check()
        reports[strategy_id] = value

    code_identity = _digest(identities)
    strategies = tuple(RetainedStrategy(
                            item,publish,config,native,deadline=args.deadline,code_identity=code_identity)
                       for item in native['strategies'])
    # -S准入后，关键纯核与NSQ实际导入路径仍逐项属于同一次绑定源码。
    for name, module in tuple(sys.modules.items()):
        if name.split('.')[0] in _PYTHON_PACKAGES:
            path = Path(module.__file__).absolute()
            _need(str(path) in identities and hashlib.sha256(_python_bytes(path, deadline=args.deadline)).hexdigest()
                  == identities[str(path)], 'imported_module_identity')
    runtime = CtaRuntime(config, tuple(s.binding() for s in strategies), deadline=args.deadline)
    result = runtime.run(args.control, args.control_id)
    if runtime._last_error is not None:
        # 私有有限诊断只记类型/调用位置；账户、变量内容和异常正文保持在原owner内。
        import traceback
        error = runtime._last_error
        value = {'schema': 'guanheng.configured-callback-failure.v1',
                 'exception_type': type(error).__name__,
                 'frames': [{'file': Path(row.filename).name, 'function': row.name, 'line': row.lineno}
                            for row in traceback.extract_tb(error.__traceback__)[-16:]]}
        with (args.control / 'callback-failure.json').open('xb') as stream:
            stream.write(_encode(value))
    return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as error:
        print('CTA startup failed: ' + type(error).__name__, file=sys.stderr, flush=True)
        raise SystemExit(2)
