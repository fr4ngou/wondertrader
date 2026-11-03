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
from threading import Event, RLock
from zoneinfo import ZoneInfo

from .execution_process import ExecutionProcessConfig, _PYTHON_PACKAGES, _python_bytes, _python_inventory, _python_packages
from .execution_strategy import CtaBridgeError, CtaRuntime, StrategyBinding, _need
from .managed_local_process import _inspect, _json, _read
from .thread_owner import ThreadOwner


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False, default=str).encode('ascii')


def _digest(value):
    return hashlib.sha256(_encode(value)).hexdigest()


def _quantity(value):
    _need(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 9007199254740900
          and value % 100 == 0, 'native_quantity')
    return int(value)


class ProjectionPublicationTimeout(CtaBridgeError):
    """本轮可重建观察投影的发布预算耗尽；原金融事实保持各自owner。"""


def _check_publication_deadline(deadline):
    if time.monotonic() >= deadline:
        raise ProjectionPublicationTimeout('projection_deadline')


def _replace_projection(temporary, target, deadline):
    """Windows旧读句柄可能报5/32/33；仅在本轮有限预算内等待释放。"""
    last_error = None
    while True:
        if time.monotonic() >= deadline:
            raise ProjectionPublicationTimeout('projection_deadline') from last_error
        try:
            temporary.replace(target)
            return
        except OSError as error:
            if getattr(error, 'winerror', None) not in (5, 32, 33):
                raise
            last_error = error
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProjectionPublicationTimeout('projection_deadline') from error
            time.sleep(min(.002, remaining))


def _write_projection(temporary, target, raw, deadline):
    """独占临时文件；未提交时清理本次文件，原子替换成功即为提交边界。"""
    owned = False
    try:
        _check_publication_deadline(deadline)
        with temporary.open('xb') as stream:
            owned = True
            stream.write(raw)
        _check_publication_deadline(deadline)
        _replace_projection(temporary, target, deadline)
        owned = False
    finally:
        # 已存在的pending属于其他未决发布，创建失败时保留它并传播原错误。
        if owned:
            temporary.unlink(missing_ok=True)


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
    request: object  # 原策略核RetainedInput值对象；由冻结输入解析，持有规则/行情/周期及时点，必填且不持有资源。
    policy: object  # 原NSQ QuantityPolicy；由显式配置解析，资本为CNY、现金ETF数量为股/份，必填。
    fee_reserve_cny: str | None  # 新买入组的费用预留，CNY十进制字符串；None表示未知，0表示明确无需预留。
    fee_source: str | None  # 上述费用预留的来源标识；来自冻结输入，None表示来源未知，不是已知零费用。
    market_manifest_source: str  # 冻结行情清单的非空来源标识；不代替各批行情的实际来源时间或摘要。
    schema: str = 'guanheng.retained-cta-input.v1'  # 固定输入协议版本；默认沿原格式，缺失时仍由解析器拒绝。
    capital_baseline: dict | None = None  # 首次启用的当前总资本基准，含库存；None沿旧资本配置，存在时正常恢复复用原值。

    @classmethod
    def from_dict(cls, value):
        from guanheng_strategy_v1 import RetainedInput
        from guanheng_strategy_native import Basis, Price, QuantityPolicy
        _need(type(value) is dict and set(cls.__dataclass_fields__)-{'capital_baseline'} <= set(value)
              <= set(cls.__dataclass_fields__)
              and value['schema'] == 'guanheng.retained-cta-input.v1', 'retained_input')
        data = dict(value)
        data['request'] = RetainedInput.from_dict(data['request'])
        _need(type(data['policy']) is dict, 'retained_policy')
        data['policy'] = QuantityPolicy(**data['policy'])
        if data.get('capital_baseline') is not None:
            from .strategy_capital import baseline
            data['capital_baseline'] = baseline(data['capital_baseline'], data['policy'])
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
        self.start_deadline = deadline  # 原监督者启动绝对截止；资金观察失败不重开启动预算。
        from guanheng_strategy_v1 import SYMBOLS
        from .retained_evaluation import evaluate_retained
        from guanheng_strategy_core.contracts import EvaluationBudget
        from .execution_facts import admit_native_files
        _need(type(native.get('strategies')) is list and len(native['strategies'])==1, 'retained_cycle_scope')
        parameters = item['parameters'].get('python_strategy')
        required = {'schema','input_file','input_sha256','main_symbol','evaluation_seconds','broker_max_age_seconds'}
        _need(type(parameters) is dict and required <= set(parameters) <= required | {'market_window', 'capital_account', 'capital_market'}
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
        self.capital_reader, self.capital_observation = None, None
        self.capital_market = parameters.get('capital_market')
        if self.inputs.capital_baseline is not None:
            from .strategy_capital import AccountCashReader
            self.capital_reader = AccountCashReader(parameters['capital_account'], self.max_age)
        from .execution_market_window import MarketWindowFile
        self.market_window = MarketWindowFile.from_dict(parameters['market_window']) if 'market_window' in parameters else None
        self.recovery = configuration.recovery_mode
        _need(self.recovery in ('record_clean','resume_clean','resume_reconciled'), 'retained_recovery_required')
        now = datetime.now(timezone.utc)
        _need(self.inputs.request.decision_cutoff <= now, 'initial_cycle_window')
        if self.recovery not in ('resume_clean','resume_reconciled'):
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
        # 故障恢复显式核前代发行身份；原状态模型、输入和数量不变量保持。
        self.previous_state_identity = None
        self.recovery_native = native  # 原已准入恢复链；仅用于核验前代合法原报价及原时点。
        self.retained_market_source = None  # 保留报价时的原控制/文件SHA，独立于当前现金与NAP。
        if self.recovery == 'resume_reconciled':
            from .execution_recovery import load_transition
            unused, prior_code_identity = load_transition(native)
            prior_identity = (self.id,self.input_sha,tuple(sorted(self.mapping.items())),asdict(self.inputs.policy),prior_code_identity)
            if self.market_window is not None:
                prior_identity += (self.market_window.configuration_identity,)
            self.previous_state_identity = _digest(prior_identity)
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
              and value['identity'] == (self.previous_state_identity or self.state_identity), 'quantity_state_identity')
        seq = value['sequence'];_need(type(seq) is int and 0 <= seq <= 9007199254740991, 'quantity_state_sequence')
        state = _restore_quantity_state(value['state'])
        if state is not None:
            _need(state.policy == self.inputs.policy and state.target.strategy_id == self.id
                  and state.target.universe == self.execution and state.target.config_id == self.config_identity
                  and state.target.algorithm_id == self.algorithm_identity, 'quantity_state_identity')
        metadata, exits = self._metadata(value['cycles']), self._exit_values(value['exits'])
        expected = _json(self._state_payload(state,seq,metadata,exits).encode('ascii'))
        expected['identity'] = self.previous_state_identity or self.state_identity
        _need(_encode(expected).decode('ascii') == text, 'quantity_state_encoding')
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
        if self.recovery in ('resume_clean','resume_reconciled'):
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
        if self.recovery not in ('resume_clean','resume_reconciled'):
            context.store_quantity_state(self._state_payload(None,0,self.cycles,self.exits))
        elif self.recovery == 'resume_reconciled':
            # 身份交接独立于资金展示和首轮调度；正常关闭后即可沿本代身份恢复。
            context.store_quantity_state(self._state_payload(self.state,self.sequence,self.cycles,self.exits))
        self.initialized = True
        if self.inputs.capital_baseline is not None and self.capital_market is not None:
            self._publish_initial_capital(context, broker)
        print('CTA retained strategy initialized',flush=True)
        print('CTA retained strategy initialized',file=sys.stderr,flush=True)

    def _native_cash(self, context, broker):
        """复用原WT已实现盈亏、费用和持仓成本；当前券商数量须与原账一致。"""
        from .execution_facts import _decimal
        rows=self._broker_rows(broker);cost=Fraction(0);fund=None
        read=getattr(context,'cash_basis',None)
        if read is None:return None
        for symbol,code in self.mapping.items():
            quantity=rows.get(code,(0,0))[0]
            if context.position(code).raw_position != quantity:return None
            value=read(code)
            if value is None or not all(math.isfinite(v) for v in (value.realized_pnl_cny,value.fees_cny,value.average_price_cny)):
                return None
            current=(Fraction(repr(value.realized_pnl_cny)),Fraction(repr(value.fees_cny)))
            if fund is not None and current != fund:return None
            fund=current
            if quantity and value.average_price_cny <= 0:return None
            cost+=quantity*Fraction(repr(value.average_price_cny))
        if fund is None:return None
        cash=Fraction(self.inputs.capital_baseline['total_cny'])+fund[0]-fund[1]-cost
        self.native_cash_basis=dict(source='original-WT:flag1-flag3-position-average',
            realized_pnl_cny=_decimal(fund[0]),fees_cny=_decimal(fund[1]),position_cost_cny=_decimal(cost),
            cash_balance_cny=_decimal(cash))
        return cash

    def _publish_initial_observation(self, context, broker, response, reason, *, deadline):
        self.sequence += 1
        candidate = dict(status='waiting_market_input',reason=reason,sequence=self.sequence,
            broker_observation=asdict(broker),broker_position_qualified=False,recovery_mode=self.recovery,
            restored_state_id=self.restored_state_id,restored_sequence=self.restored_sequence,
            cycle_metadata=dict(self.cycles),capital_baseline=self.inputs.capital_baseline,
            capital=self.capital_observation,initial_market_observation=response,
            native_cash_basis=getattr(self,'native_cash_basis',None),
            retained_market_source=self.retained_market_source)
        self.publish(self.id,candidate,preview=True,deadline=deadline)
        context.store_quantity_state(self._state_payload(self.state,self.sequence,self.cycles,self.exits))
        self.publish(self.id,candidate,deadline=deadline)

    def _publish_initial_capital(self, context, broker):
        try:
            response=self._read_initial_capital(context,broker)
            reason='awaiting_first_strategy_calculation'
        except Exception:
            # 来源/估值缺值局限于资金观察。KV/投影保存置于本捕获范围之外。
            self.capital_observation=None;response=None;reason='initial_capital_unavailable'
        self._publish_initial_observation(context,broker,response,reason,deadline=self.start_deadline)

    def _retained_initial_market(self, broker, funds, cash, *, deadline):
        """同账/数量/周期核验后复用原QMT快照；当前NAP和原WT账仍分别现取。"""
        from .execution_recovery import prior_strategy_observations
        expected = {code:value[0] for code,value in self._broker_rows(broker).items() if value[0]}
        for previous, source in prior_strategy_observations(self.recovery_native,self.id,deadline=deadline):
            capital = previous.get('capital')
            if type(capital) is not dict:continue
            prior_basis = previous.get('native_cash_basis')
            positions = previous.get('broker_observation',{}).get('positions',[])
            old = {row['symbol']:row['quantity'] for row in positions if row['quantity']}
            _need(old == expected and previous.get('cycle_metadata') == self.cycles
                and previous.get('capital_baseline') == self.inputs.capital_baseline
                and prior_basis == self.native_cash_basis
                and capital['baseline'] == self.inputs.capital_baseline
                and Fraction(capital['cash_balance_cny']) == cash
                and Fraction(capital['native_pnl_cny']) == Fraction(repr(funds.fund_pnl)),
                'retained_capital_basis_changed')
            response = previous.get('initial_market_observation')
            _need(type(response) is dict and response['status']['code'] == 'Ok'
                and response['data']['metadata']['qualification'] in ('NativeVerified','ProductionQualified')
                and capital['market_value_source'] == 'broker-position+raw-QMT-snapshot',
                'retained_capital_market_source')
            self.retained_market_source = dict(source,original_valuation_at=capital['observed_at'],
                original_price_observed_at=capital['price_observed_at'])
            return response
        raise ValueError('retained_capital_market_unavailable')

    def _read_initial_capital(self, context, broker):
        """初始化后发布只读资金；原WT损益、券商P和明确当前快照各保留原来源。

        原CTA初始化早于行情Parser启动，当前价格尚未进入CTA缓存。首次估值使用
        已声明的原MarketClient快照，不触发策略计算、目标setter或金融命令。
        后续原K线回调继续以原CTA价格和同一资本基准更新。
        """
        from guanheng_market_client import MarketClient
        from .strategy_capital import observe_capital
        market = self.capital_market
        _need(type(market) is dict and set(market) == {
            'base_url','token_env','timeout_seconds','max_response_bytes','max_age_seconds'}, 'capital_market')
        _need(type(market['max_age_seconds']) in (int,float) and 0 < market['max_age_seconds'] <= 3600,
              'capital_market_age')
        deadline = min(self.start_deadline,time.monotonic()+self.seconds)
        quantities = self._broker_rows(broker)
        # 原账现金先独立核实。报价暂缺时仍保留真实现金依据，避免报价失败抹掉原账。
        cash = self._native_cash(context,broker)
        _need(cash is not None,'capital_cash_unknown')
        funds = context.facts();_need(math.isfinite(funds.fund_pnl),'native_funds')
        codes = [code for symbol,code in self.mapping.items() if quantities.get(code,(0,0))[0]]
        value, response = Fraction(0), None
        valuation_stamps = []  # 原报价时间；闭市最后价格仅用于有来源时点的估值展示。
        if codes:
            client = MarketClient(market['base_url'],os.environ[market['token_env']],
                timeout=min(market['timeout_seconds'],deadline-time.monotonic()),
                max_response_bytes=market['max_response_bytes'])
            try:
                response = client.quotes_query(['.'.join(code.split('.')[::2]) for code in sorted(codes)])
                _need(response['status']['code'] == 'Ok' and response['data']['metadata']['qualification']
                      in ('NativeVerified','ProductionQualified'), 'capital_market_source')
            except Exception:
                response = self._retained_initial_market(broker,funds,cash,deadline=deadline)
            observed = {}
            now = datetime.now(timezone.utc)
            for row in response['data']['snapshots']:
                exchange,code = row['symbol'].split('.')
                key = exchange+'.ETF.'+code
                stamp = datetime.strptime(str(row['date'])+f"{row['action_time']//1000:06d}",'%Y%m%d%H%M%S')
                stamp = stamp.replace(tzinfo=ZoneInfo('Asia/Shanghai'),microsecond=row['action_time']%1000*1000)
                price = row['price']
                _need(key in codes and key not in observed and row['source_time_verified'] is True
                    and stamp <= now
                    and type(price) in (int,float) and math.isfinite(price) and price > 0,'capital_market_snapshot')
                observed[key] = price
                valuation_stamps.append(stamp)
            _need(set(observed) == set(codes),'capital_market_complete')
            value = sum((Fraction(repr(observed[code]))*quantities[code][0] for code in codes),Fraction(0))
        cutoff = datetime.now(timezone.utc)
        account,qualified = self.capital_reader.read(cutoff,deadline)
        completed_at = datetime.now(timezone.utc)
        self.capital_observation = observe_capital(self.inputs.capital_baseline,Fraction(repr(funds.fund_pnl)),
            value,completed_at.isoformat(),
            account,qualified,max_age_seconds=self.max_age,
            position_observed_at=datetime.fromtimestamp(broker.position_received_ms/1000,timezone.utc).isoformat(),
            market_value_source='broker-position+raw-QMT-snapshot',
            cash_balance=cash,price_observed_at=min(valuation_stamps).isoformat() if valuation_stamps else None)
        return response

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

    def _capture(self, context, prices, cutoff, result_sha, *, price_source=None, deadline=float('inf'), broker=None):
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
        verified = True
        nav_source, cash_source = 'original-CTA:explicit-genesis+flag0', 'original-CTA:NAV-minus-complete-theoretical-holdings'
        if self.inputs.capital_baseline is not None:
            from .strategy_capital import observe_capital
            _need(broker is not None and broker.positions_known and broker.position_received_ms is not None, 'capital_positions')
            quantities = self._broker_rows(broker)
            actual_value = sum((Fraction(repr(prices[s]))*quantities.get(self.mapping[s],(0,0))[0]
                                for s in self.execution), Fraction(0))
            account, qualified = self.capital_reader.read(datetime.now(timezone.utc), deadline)
            ledger_cash=self._native_cash(context,broker)
            self.capital_observation = None
            if ledger_cash is not None and ledger_cash==nav-actual_value:
                self.capital_observation = observe_capital(self.inputs.capital_baseline, Fraction(repr(facts.fund_pnl)),
                    actual_value, cutoff.isoformat(), account, qualified, max_age_seconds=self.max_age,
                    position_observed_at=datetime.fromtimestamp(broker.position_received_ms/1000,timezone.utc).isoformat(),
                    cash_balance=ledger_cash)
            spendable = None if self.capital_observation is None else self.capital_observation['spendable_cash_cny']
            cash, verified = Fraction(spendable or '0'), spendable is not None
            nav_source, cash_source = 'current-capital:explicit-baseline+WT-flag0', 'original-WT:cash-ledger+NAP-cash-constraint'
            identity = _digest((identity,self.capital_observation,asdict(broker)))
        basis = Basis(cutoff.isoformat(),result_sha,_decimal(nav),repr(facts.fund_pnl),_decimal(cash),
                      self.inputs.fee_reserve_cny,nav_source,cash_source,self.inputs.fee_source,
                      tuple(Price(s,repr(prices[s]),price_source or self.inputs.market_manifest_source) for s in self.execution),verified,identity)
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
        if self.inputs.capital_baseline is not None:
            candidate['capital_baseline'] = self.inputs.capital_baseline
            if self.capital_observation is not None:
                candidate['capital'] = dict(self.capital_observation,
                    account_observation_qualified=False, spendable_cash_cny=None)
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
            facts,raw,basis,observed = self._capture(context,prices,cutoff,result['input_sha256'],price_source=price_source,deadline=deadline,broker=broker)
            if self.capital_observation is not None:
                candidate['capital'] = self.capital_observation
            basis,observed,execution = self._execution_capture(broker,basis,observed)
            if self.inputs.capital_baseline is not None and not basis.native_nav_verified:
                # 当前现金约束缺失属于来源等待。原NSQ只接受已核basis；保留
                # 上一阶段与未决责任，下一轮取得新来源后再交原核推进。
                from guanheng_strategy_native import Outcome
                outcome, previous_status = Outcome('waiting_basis','account_cash_unavailable',state), None
            else:
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
    reports, publication_lock = {}, RLock()

    def publish(strategy_id, value, *, preview=False, deadline):
        if not publication_lock.acquire(timeout=max(0,deadline-time.monotonic())):
            raise ProjectionPublicationTimeout('projection_lock_deadline')
        try:
            return publish_locked(strategy_id,value,preview=preview,deadline=deadline)
        finally:
            publication_lock.release()

    def publish_locked(strategy_id, value, *, preview=False, deadline):
        _check_publication_deadline(deadline)
        candidate = dict(reports);candidate[strategy_id] = value
        raw = _encode({'schema': 'guanheng.configured-cta-observation.v2',
                       'control_id': args.control_id, 'config_sha256': args.config_sha256,
                       'pid': os.getpid(), 'strategies': candidate})
        _need(len(raw) <= 4 * 1024 * 1024, 'projection_capacity')
        _check_publication_deadline(deadline)
        if preview:
            return
        temporary = args.control / 'strategies.pending'
        _write_projection(temporary, args.control / 'strategies.json', raw, deadline)
        # 原子替换已经提交，内存发布状态随即推进；截止不能撤回已提交投影。
        reports[strategy_id] = value

    code_identity = _digest(identities)
    if config.recovery_mode == 'resume_reconciled':
        from .execution_recovery import load_transition
        binding = _json(_read(args.control/'python-binding.json',256*1024))
        load_transition(native,identities,binding=binding)
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
    # 同一原执行进程持有账户约束线程；线程只读NAP及发布值，从不借用Native上下文。
    # K线回调和账户更新共享唯一原子发布者，估值时间与策略sequence保持原值。
    refresh_stop = Event()
    from .strategy_capital import AccountCashReader, refresh_account_constraint
    readers = {s.id:AccountCashReader(s.capital_reader.binding,s.max_age)
               for s in strategies if s.capital_reader is not None}
    def refresh_accounts():
        try:
            while not refresh_stop.wait(10):
                deadline = time.monotonic()+2
                if not publication_lock.acquire(timeout=max(0,deadline-time.monotonic())):
                    continue
                try:
                    for strategy_id,reader in readers.items():
                        report = reports.get(strategy_id)
                        capital = None if report is None else report.get('capital')
                        if capital is None:
                            continue
                        updated = refresh_account_constraint(capital,reader,deadline)
                        if updated != capital:
                            publish_locked(strategy_id,dict(report,capital=updated),deadline=deadline)
                except ProjectionPublicationTimeout:
                    # 本轮观察尚未提交时保留最后成功值；下一轮重新读取权威NAP批次。
                    # 原K线回调仍传播该异常，保持原策略/金融写入失败语义。
                    continue
                finally:
                    publication_lock.release()
        except Exception as error:
            # 账户约束更新局部故障保留原资金/时点；原过期规则会撤销可用资格。
            with (args.control/'capital-refresh-failure.json').open('x',encoding='ascii') as stream:
                json.dump(dict(exception_type=type(error).__name__),stream)
    refresher = ThreadOwner(target=refresh_accounts,name='capital-account-constraint') if readers else None
    try:
        if refresher is not None:
            refresher.start()
        result = runtime.run(args.control, args.control_id)
    finally:
        refresh_stop.set()
        if refresher is not None:
            joined = refresher.join_until(time.monotonic()+3)
            with (args.control/'capital-refresh-closed.json').open('x',encoding='ascii') as stream:
                json.dump(dict(
                    joined=joined,  # 原ThreadOwner已取得标准线程退出/join证明；False表示关闭未确认。
                    pending=refresher.pending),stream)  # 账户读取线程仍有生命周期责任；布尔值，由原owner提供。
            _need(joined,'capital_refresh_close_unconfirmed')
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
