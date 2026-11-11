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
from .profile_facts import allocation_projection


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
    fee_reserve_cny: str | None  # 显式买入组预留，CNY十进制字符串；None由执行owner沿已核WT模板装配，0须有来源。
    fee_source: str | None  # 显式预留来源；None表示输入未提供，派生basis另标原WT费用文件SHA，不把未知当零。
    market_manifest_source: str  # 冻结行情清单的非空来源标识；不代替各批行情的实际来源时间或摘要。
    schema: str = 'guanheng.retained-cta-input.v1'  # 固定输入协议版本；默认沿原格式，缺失时仍由解析器拒绝。
    capital_baseline: dict | None = None  # 首次启用的当前总资本基准，含库存；None沿旧资本配置，存在时正常恢复复用原值。
    cash_anchor: dict | None = None  # 本次预算的券商现金原点；包含初始分配现金/账户现金及来源SHA，实际资本模式必填，旧解析可缺省。

    @classmethod
    def from_dict(cls, value):
        from guanheng_strategy_v1 import RetainedInput
        from guanheng_strategy_native import Basis, Price, QuantityPolicy
        _need(type(value) is dict and set(cls.__dataclass_fields__)-{'capital_baseline','cash_anchor'} <= set(value)
              <= set(cls.__dataclass_fields__)
              and value['schema'] == 'guanheng.retained-cta-input.v1', 'retained_input')
        data = dict(value)
        data['request'] = RetainedInput.from_dict(data['request'])
        _need(type(data['policy']) is dict, 'retained_policy')
        data['policy'] = QuantityPolicy(**data['policy'])
        if data.get('capital_baseline') is not None:
            from .strategy_capital import baseline
            data['capital_baseline'] = baseline(data['capital_baseline'], data['policy'])
        if data.get('cash_anchor') is not None:
            from .strategy_capital import cash_anchor
            data['cash_anchor'] = cash_anchor(data['cash_anchor'], data['capital_baseline'])
        source = data['market_manifest_source']
        _need(type(source) is str and 1 <= len(source) <= 256
              and all(32 <= ord(c) <= 126 for c in source), 'market_source')
        from guanheng_strategy_v1 import SYMBOLS
        Basis(data['request'].decision_cutoff.isoformat(), '0'*64, data['policy'].initial_capital_cny,
              '0', data['policy'].initial_capital_cny, data['fee_reserve_cny'], 'preflight',
              'preflight', data['fee_source'], tuple(Price(s, None, source) for s in SYMBOLS), False, 'preflight')
        return cls(**data)


def _retained_seed_identity(inputs, recovery, *, budget):
    """恢复时只核配置身份；旧seed周期保持原捕获/失效时间，当前决策由真实P/D重新装配。

    资金基准和初始周期属于耐久事实。恢复初始化只需配置/算法身份来校验原NSQ，
    不执行旧周期与新市场批次的混合决策。后续原回调先读取当前券商P/D、恢复周期，
    再使用实际捕获时间完整调用evaluate_retained；持仓、现金和委托准入继续原流程。
    """
    from guanheng_strategy_core.contracts import canonical_bytes
    from guanheng_strategy_v1 import ALGORITHM_ID, validate_retained_configuration
    _need(type(inputs) is RetainedRuntimeInput
          and recovery in ('record_clean','resume_clean','resume_reconciled'), 'retained_recovery_required')
    if recovery in ('resume_clean','resume_reconciled'):
        validate_retained_configuration(inputs.request.configuration)
        return hashlib.sha256(canonical_bytes(inputs.request.configuration)).hexdigest(), ALGORITHM_ID
    from .retained_evaluation import evaluate_retained
    admitted = evaluate_retained(inputs.request, inputs.policy, budget=budget)
    return admitted.target.config_id, admitted.target.algorithm_id


class RetainedStrategy:
    allocation = None  # 旧独立调用及局部适配器默认沿原单策略来源。
    deal_history = None  # 原账户只读历史材料；仅在唯一策略及固定资金基准接线。
    allocation_observation = None  # 双profile才由原借用刷新。
    """唯一当前版本实时薄桥。周期元数据存原KV，数量只读取原owner。

    首次已核周期可连续部分增减/清仓；新开仓起点缺少实际来源时等待。
    新周期仅消费原管理成交的源时间；缺少完整事实时保持等待。
    """
    def __init__(self, item, publish, configuration, native, *, deadline, code_identity, allocation=None):
        self.start_deadline = deadline  # 原监督者启动绝对截止；资金观察失败不重开启动预算。
        from guanheng_strategy_v1 import SYMBOLS
        from guanheng_strategy_core.contracts import EvaluationBudget
        from .execution_facts import admit_native_files, native_price_ticks
        from .strategy_profiles import shared_profiles
        _need(shared_profiles(native) == (allocation is not None), 'retained_cycle_scope')
        self.allocation, self.allocation_observation, self.participants = allocation, None, {}
        self._shared_announced = False
        parameters = item['parameters'].get('python_strategy')
        required = {'schema','input_file','input_sha256','main_symbol','evaluation_seconds','broker_max_age_seconds'}
        _need(type(parameters) is dict and required <= set(parameters) <= required | {'market_window', 'capital_account', 'capital_market'}
              and parameters['schema'] == 'guanheng.retained-cta.v1'
              and item['id'] == 'resonance-regime-v1', 'strategy_profile')
        self.execution_enabled=native['trader']['writes_enabled']
        _need(type(self.execution_enabled)is bool,'execution_permission')
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
                  and type(rule.get('is_cancel_unmanaged_order')) is bool, 'retained_cash_executor')
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
        self._initial_capital_basis = None  # 原初始化估值的不可变私有值；首帧NAP晚到时只由账户线程读取。
        self.capital_market = parameters.get('capital_market')
        if self.inputs.capital_baseline is not None and self.allocation is None:
            from .strategy_capital import AccountCashReader
            _need(self.inputs.cash_anchor is not None, 'capital_cash_anchor')
            self.capital_reader = AccountCashReader(parameters['capital_account'], self.max_age)
            if 'output_directory' in native:
                from .execution_deal_history import ClosedDealHistory
                self.deal_history = ClosedDealHistory.load(native, self.input_sha,
                    self.inputs.capital_baseline['baseline_at'], deadline)
                if self.deal_history is not None:
                    _need(self.capital_reader.binding['account'] == native['trader']['expected_account']
                          and self.capital_reader.binding['environment'] == native['trader']['environment'],
                          'broker_deal_history_account_scope')
        from .execution_market_window import MarketWindowFile
        self.market_window = MarketWindowFile.from_dict(parameters['market_window']) if 'market_window' in parameters else None
        self.recovery = configuration.recovery_mode
        _need(self.recovery in ('record_clean','resume_clean','resume_reconciled'), 'retained_recovery_required')
        now = datetime.now(timezone.utc)
        _need(self.inputs.request.decision_cutoff <= now, 'initial_cycle_window')
        if self.recovery not in ('resume_clean','resume_reconciled'):
            _need(self.inputs.request.cycles_captured_at <= now < self.inputs.request.cycles_valid_until,
                  'initial_cycle_window')
        self.config_identity, self.algorithm_identity = _retained_seed_identity(self.inputs, self.recovery,
            budget=EvaluationBudget(max_seconds=min(self.seconds, max(.001,deadline-time.monotonic()))))
        self.id, self.publish, self.execution = item['id'], publish, tuple(SYMBOLS)
        self.mapping = {s:('SSE' if s.endswith('.SH') else 'SZSE')+'.ETF.'+s[:6] for s in self.execution}
        self.reads = self.targets = tuple(sorted(self.mapping.values()))
        self.main = parameters['main_symbol'];_need(self.main in self.reads, 'main_symbol')
        from .profile_facts import configured_native_facts
        identities, frozen, self.native_price_ticks = configured_native_facts(configuration,native,self.mapping,deadline=deadline)
        self.native_fees = _json(frozen['fees'])
        self.native_fee_source = 'original-WT:fees-sha256:'+hashlib.sha256(frozen['fees']).hexdigest()
        self.takeover = 'takeover' in native
        identity = (self.id, self.input_sha, tuple(sorted(self.mapping.items())), asdict(self.inputs.policy), code_identity)
        if self.market_window is not None:
            identity += (self.market_window.configuration_identity,)
        self.state_identity = _digest(identity)
        # 故障恢复显式核前代发行身份；原状态模型、输入和数量不变量保持。
        self.previous_state_identity = None
        self.role_handoff = False  # 本次前代仍为旧角色时，仅退役零仓位角色的NSQ计划。
        self.previous_inputs = None  # 已SHA核验的原输入，专用于校验原状态身份和旧配置目标。
        self.recovery_native = native  # 原已准入恢复链；仅用于核验前代合法原报价及原时点。
        self.retained_market_source = None  # 保留报价时的原控制/文件SHA，独立于当前现金与NAP。
        self.initial_market_window = None  # 初始化只读验证的出版物元数据，不产生目标或新行情事件。
        if self.recovery == 'resume_reconciled':
            from .execution_recovery import load_transition
            unused, prior_code_identity = load_transition(native)
            prior_identity = (self.id,self.input_sha,tuple(sorted(self.mapping.items())),asdict(self.inputs.policy),prior_code_identity)
            from .execution_recovery import state_origin_configuration
            previous_native=state_origin_configuration(native,deadline=deadline)
            from .execution_role_replacement import is_role_handoff, input_value
            self.role_handoff = is_role_handoff(native, previous_native)
            if self.role_handoff:
                self.previous_inputs = input_value(previous_native, deadline=deadline)
                previous_parameters = next(row for row in previous_native['strategies'] if row['id']==self.id)['parameters']['python_strategy']
                old_mapping = dict(self.mapping)
                old_mapping.pop('588030.SH')
                old_mapping['589680.SH'] = 'SSE.ETF.589680'
                prior_identity = (self.id,previous_parameters['input_sha256'],tuple(sorted(old_mapping.items())),
                                  asdict(self.inputs.policy),prior_code_identity)
            prior_window=next(row for row in previous_native['strategies'] if row['id']==self.id)['parameters']['python_strategy'].get('market_window')
            if prior_window is not None:
                prior_identity += (MarketWindowFile.from_dict(prior_window).configuration_identity,)
            self.previous_state_identity = _digest(prior_identity)
        self.state, self.sequence, self.initialized = None, 0, False
        self.cycles, self.exits = {}, ()
        self.flat_sources = {}
        self.restored_state_id, self.restored_sequence = None, None

    def _publish(self,value,*,preview=False,deadline):
        """每份初始/状态观察携带当前kernel与执行集合；不推定尚未产生的目标或收益。"""
        from guanheng_strategy_v1 import STRATEGY_VERSION
        definition=dict(
            strategy_id=self.id,  # 本次WT绑定的策略身份，来自已准入运行配置。
            strategy_version=STRATEGY_VERSION,  # 本次实际安装并调用的kernel版本，非App依赖版本。
            symbols=list(self.execution))  # 本次已准入执行证券，业务SH/SZ代码；不含猜测持仓或目标权重。
        if self.allocation is not None:value=dict(value,owned_valuation=getattr(self,'_owned_valuation',None))
        return self.publish(self.id,dict(value,definition=definition),preview=preview,deadline=deadline)

    def binding(self):
        return StrategyBinding(self.id, self.main, self.reads, self.targets if self.execution_enabled else (), self.callback)

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
        if self.role_handoff:
            # 原公共NSQ构造器已核state_id；核原配置与原算法后整体放弃旧计划，七角色周期原样保留。
            from guanheng_strategy_v1.latest import RetainedConfig
            from guanheng_strategy_core.contracts import canonical_bytes
            original = self.previous_inputs['request']['configuration']
            if state is not None:
                old_config = RetainedConfig(**original)
                _need(state.policy == self.inputs.policy and state.target.strategy_id == self.id
                      and state.target.universe == tuple(sorted((set(self.execution)-{'588030.SH'})|{'589680.SH'}))
                      and state.target.algorithm_id == 'resonance-regime-v1@1.2.1/ledger-front-ratio-v1'
                      and state.target.config_id == hashlib.sha256(canonical_bytes(old_config)).hexdigest(),
                      'quantity_state_identity')
            # 先按原证券集合核元数据及规范编码，再切回新集合；不会把旧周期套给新基金。
            current_execution = self.execution
            self.execution = tuple(sorted((set(self.execution)-{'588030.SH'})|{'589680.SH'}))
            try:
                metadata, exits = self._metadata(value['cycles']), self._exit_values(value['exits'])
                expected = _json(self._state_payload(state,seq,metadata,exits).encode('ascii'))
            finally:
                self.execution = current_execution
            expected['identity'] = self.previous_state_identity
            _need(_encode(expected).decode('ascii') == text, 'quantity_state_encoding')
            self.state, self.sequence = None, seq
            self.cycles = {symbol: row for symbol,row in metadata.items() if symbol != '589680.SH'}
            self.exits = tuple(row for row in exits if row.symbol != '589680.SH')
            self.restored_state_id, self.restored_sequence = None if state is None else state.state_id, seq
            return
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

    def _allocation_refresh(self, context, deadline):
        """只在原Native借用内更新源账户事实，随后读取独立策略归属。"""
        if self.allocation is None:return None
        reason = self.allocation.observe_context(context,deadline=deadline,max_age_seconds=self.max_age)
        self.allocation_observation = self.allocation.strategy_observation(self.id,deadline=deadline)
        _need(self.allocation_observation.strategy.strategy_id==self.id,'retained_allocation_scope')
        from .owned_valuation import owned_valuation
        baseline=self.inputs.capital_baseline
        self._owned_valuation=owned_valuation(context,None if reason else self.allocation_observation,self.native_price_ticks,
            baseline_cny=baseline['total_cny']if baseline else self.inputs.policy.initial_capital_cny,
            baseline_source='retained.capital_baseline.total_cny'if baseline else'retained.policy.initial_capital_cny',
            max_age=self.max_age,deadline=deadline,baseline_at=baseline.get('baseline_at')if baseline else None)  # 不可变展示值；不进入原金融输入指纹。
        return reason

    def _broker_rows(self, broker):
        if self.allocation is not None:
            _need(self.allocation_observation is not None,'retained_allocation_unknown')
            rows={}
            for row in self.allocation_observation.strategy.positions:
                _need(row.symbol in self.targets and row.symbol not in rows,'retained_allocation_scope')
                total,valid=self._shares(row.quantity),self._shares(row.sellable)
                _need(valid<=total,'broker_quantity');rows[row.symbol]=(total,valid)
            return rows
        rows = {}
        for row in broker.positions:
            _need(row.is_long and row.symbol in self.targets and row.symbol not in rows, 'broker_scope')
            total, valid = self._shares(row.quantity), self._shares(row.sellable)
            _need(valid <= total, 'broker_quantity')
            rows[row.symbol] = (total,valid)
        return rows

    def _initialize(self, context):
        _need(self._allocation_refresh(context,self.start_deadline) is None,'retained_allocation_initial')
        broker = context.broker_observation()
        _need(broker.positions_known, 'broker_unknown')
        rows = self._broker_rows(broker)
        if self.recovery in ('resume_clean','resume_reconciled'):
            self._load_state(context.load_quantity_state())
            # 同策略恢复保留原冻结阶段；原WT活动订单参与后续pending观察。
            # 角色首次换代的旧计划由_load_state在核原配置后明确退役。
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
        if self.role_handoff and rows.get(self.mapping['588030.SH'],(0,0))[0]:
            # 候选验证已真实买入时，以原flat基准和完整D证明新基金开启；不冒充原库存。
            cutoff = datetime.now(timezone.utc)
            def check():
                _need(time.monotonic() < self.start_deadline, 'evaluation_budget')
            cycle_trades = self._historical_cycle_facts(broker, trades, cutoff, check)
            opening = self._opening_cycle('588030.SH', broker, cycle_trades, cutoff, check)
            _need(opening is not None, 'actual_opening_source_required')
            self.cycles['588030.SH'] = opening
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
        if self.allocation is not None:
            self._publish(dict(status='waiting_market_input',reason='awaiting_first_strategy_calculation',sequence=self.sequence,
                allocation_observation=allocation_projection(self.allocation_observation,include_read_projection=True)),
                deadline=self.start_deadline)  # 只发布ASA初始估值；不重复KV/目标或金融调用。
        if self.allocation is None and self.inputs.capital_baseline is not None and self.capital_market is not None:
            self._publish_initial_capital(context, broker)
        print('CTA retained strategy initialized',flush=True)
        print('CTA retained strategy initialized',file=sys.stderr,flush=True)

    def _native_cash(self, funds, market_value, account=None):
        """由固定原点和券商现金差得到实际策略余额；CTA统计只保留审计。"""
        from .execution_facts import _decimal
        from .strategy_capital import broker_cash_balance
        _need(math.isfinite(funds.fund_pnl) and market_value>=0,'native_funds')
        self.native_cash_basis=None
        if account is None:
            return None
        try:
            cash=broker_cash_balance(self.inputs.cash_anchor,account)
        except ValueError:
            return None
        self.native_cash_basis=dict(source='broker-cash-delta',
            cash_anchor_sha256=_digest(self.inputs.cash_anchor),
            account_source_sha256=account.source_sha256,
            native_theoretical_pnl_cny=repr(funds.fund_pnl),
            market_value_cny=_decimal(market_value),cash_balance_cny=_decimal(cash))
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
        if self.market_window is not None:candidate['market_window']=self.initial_market_window
        self._publish(candidate,preview=True,deadline=deadline)
        context.store_quantity_state(self._state_payload(self.state,self.sequence,self.cycles,self.exits))
        self._publish(candidate,deadline=deadline)

    def _publish_initial_capital(self, context, broker):
        try:
            response=self._read_initial_capital(context,broker)
            reason='awaiting_first_strategy_calculation'
        except Exception:
            # 来源/估值缺值局限于资金观察。KV/投影保存置于本捕获范围之外。
            self.capital_observation=None;response=None;reason='initial_capital_unavailable'
        if self.market_window is not None:
            # 只读核来源窗口及原Native历史，不调用策略计算、目标setter或金融API。
            from .execution_market_window import native_history_matches
            request=replace(self.inputs.request,decision_cutoff=datetime.now(timezone.utc))
            window=self.market_window.read(request,deadline=self.start_deadline)
            self.initial_market_window=window.publication
            if window.request is None:reason=window.reason
            elif not native_history_matches(window.request,self.mapping,context,
                    lambda:_need(time.monotonic()<self.start_deadline,'evaluation_deadline')):
                reason='market_history_mismatch'
        self._publish_initial_observation(context,broker,response,reason,deadline=self.start_deadline)

    def _snapshot_valuation(self, response, quantities):
        """原QMT快照的完整原价与时点；恢复和首次读取复用同一校验。"""
        from .execution_facts import canonical_raw_price
        _need(type(response) is dict and response['status']['code'] == 'Ok'
            and response['data']['metadata']['qualification'] in ('NativeVerified','ProductionQualified'),
            'capital_market_source')
        prices, stamps = {}, []
        now = datetime.now(timezone.utc)
        for row in response['data']['snapshots']:
            exchange, code = row['symbol'].split('.')
            key = exchange+'.ETF.'+code
            stamp = datetime.strptime(str(row['date'])+f"{row['action_time']//1000:06d}",'%Y%m%d%H%M%S')
            stamp = stamp.replace(tzinfo=ZoneInfo('Asia/Shanghai'),microsecond=row['action_time']%1000*1000)
            price = row['price']
            _need(key in quantities and key not in prices and row['source_time_verified'] is True
                and stamp <= now and type(price) in (int,float) and math.isfinite(price) and price > 0,
                'capital_market_snapshot')
            prices[key] = canonical_raw_price(price, self.native_price_ticks[key]);stamps.append(stamp)
        _need(set(prices) == set(quantities),'capital_market_complete')
        return sum((prices[code]*quantity for code,quantity in quantities.items()),Fraction(0)), min(stamps)

    def _retained_initial_valuation(self, broker, funds, *, deadline):
        """同账/数量/周期复用原事实估值；QMT与CTA来源、原价时点分别保持。"""
        from .execution_facts import canonical_raw_price
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
                and type(prior_basis) is dict
                and prior_basis.get('cash_anchor_sha256') == _digest(self.inputs.cash_anchor)
                and capital['baseline'] == self.inputs.capital_baseline
                and capital.get('cash_anchor') == self.inputs.cash_anchor,
                'retained_capital_basis_changed')
            kind = capital['market_value_source'];response = None
            if kind == 'broker-position+raw-QMT-snapshot':
                response = previous.get('initial_market_observation')
                if type(response) is not dict:continue
                value, stamp = self._snapshot_valuation(response,expected)
                _need(stamp == datetime.fromisoformat(capital['price_observed_at']),
                    'retained_capital_price_source')
            elif kind == 'broker-position+raw-CTA-price':
                basis = previous.get('quantity_basis')
                window = previous.get('market_window')
                price_time = capital.get('price_observed_at')
                if not (type(basis) is dict and type(basis.get('prices')) is list
                        and type(window) is dict and type(window.get('publication_sha256')) is str
                        and type(price_time) is str):continue
                # 原报价只核价格来源；NAP刷新可独立更新现金，恢复沿同一原点重读当前账户。
                prices = {}
                expected_source = 'original-CTA:applied-tick;window:'+window['publication_sha256']
                for row in basis['prices']:
                    _need(type(row) is dict,'retained_capital_price_source')
                    code = self.mapping.get(row.get('symbol'))
                    _need(code is not None and row.get('unit') == 'CNY/share' and row.get('adjustment') == 'raw'
                        and row.get('source') == expected_source and code not in prices
                        and type(row.get('raw_cny_per_share')) is str,
                        'retained_capital_price_source')
                    price = canonical_raw_price(row['raw_cny_per_share'],self.native_price_ticks[code])
                    prices[code] = price
                _need(set(expected) <= set(prices),'retained_capital_market_complete')
                value = sum((prices[code]*quantity for code,quantity in expected.items()),Fraction(0))
                stamp = datetime.fromisoformat(price_time)
                _need(stamp.utcoffset() is not None and stamp <= datetime.now(timezone.utc),
                    'retained_capital_price_source')
            else:continue
            _need(abs(value-Fraction(capital['market_value_cny'])) <= Fraction(1,100000000),
                'retained_capital_market_changed')
            self.retained_market_source = dict(source,original_valuation_at=capital['observed_at'],
                original_price_observed_at=capital['price_observed_at'],market_value_source=kind)
            return value, stamp, kind, response
        raise ValueError('retained_capital_market_unavailable')

    def _read_initial_capital(self, context, broker):
        """初始化后发布只读资金；券商现金、实际P和明确原价分别保留来源。

        原CTA初始化早于行情Parser启动，先读已声明的原MarketClient快照。
        快照不可用时，恢复沿同账、同数量和周期核对前代原估值。
        两条路径保留原价时点，不触发策略计算、目标setter或金融命令。
        后续原K线回调继续以原CTA价格和同一资本基准更新。
        """
        from guanheng_market_client import MarketClient, MarketUnavailable
        from .strategy_capital import InitialCapitalValuation
        market = self.capital_market
        _need(type(market) is dict and set(market) == {
            'base_url','token_env','timeout_seconds','max_response_bytes','max_age_seconds'}, 'capital_market')
        _need(type(market['max_age_seconds']) in (int,float) and 0 < market['max_age_seconds'] <= 3600,
              'capital_market_age')
        deadline = min(self.start_deadline,time.monotonic()+self.seconds)
        quantities = self._broker_rows(broker)
        funds = context.facts();_need(math.isfinite(funds.fund_pnl),'native_funds')
        codes = [code for symbol,code in self.mapping.items() if quantities.get(code,(0,0))[0]]
        value, response = Fraction(0), None
        market_value_source = 'broker-position+raw-QMT-snapshot'
        valuation_stamps = []  # 原报价时间；闭市最后价格仅用于有来源时点的估值展示。
        if codes:
            held = {code:quantities[code][0] for code in codes}
            try:
                token = os.environ.get(market['token_env'])
                _need(bool(token), 'capital_market_credentials')
                remaining = deadline-time.monotonic()
                # 恢复代给前代估值核验及账户读取保留时间，沿同一绝对截止。
                quote_budget = remaining/3 if self.recovery == 'resume_reconciled' else remaining
                client = MarketClient(market['base_url'],token,
                    timeout=min(market['timeout_seconds'],quote_budget),
                    max_response_bytes=market['max_response_bytes'])
                response = client.quotes_query(['.'.join(code.split('.')[::2]) for code in sorted(codes)])
                value,stamp = self._snapshot_valuation(response,held)
            except (ValueError,CtaBridgeError,MarketUnavailable):
                value,stamp,market_value_source,response = self._retained_initial_valuation(broker,funds,deadline=deadline)
            valuation_stamps.append(stamp)
        cutoff = datetime.now(timezone.utc)
        if self._initial_capital_basis is None:
            self._initial_capital_basis = InitialCapitalValuation(
                self.sequence+1,value,Fraction(repr(funds.fund_pnl)),cutoff.isoformat(),
                datetime.fromtimestamp(broker.position_received_ms/1000,timezone.utc).isoformat(),
                market_value_source,min(valuation_stamps).isoformat() if valuation_stamps else None)
        account,qualified = self.capital_reader.read(cutoff,deadline)
        cash=self._native_cash(funds,value,account)
        self.capital_observation = self._initial_capital_basis.observe(
            self.inputs.capital_baseline,self.inputs.cash_anchor,account,qualified,max_age_seconds=self.max_age)
        return response

    def _flat_source(self,symbol,broker,trades):
        if self.allocation is not None:return None
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

    def _historical_cycle_facts(self, broker, trades, cutoff, check):
        if self.deal_history is None:
            return trades
        if (trades is None or not trades.known or trades.query_received_ms is None
                or broker.position_received_ms is None):
            return None
        queried = datetime.fromtimestamp(trades.query_received_ms/1000, timezone.utc)
        position = datetime.fromtimestamp(broker.position_received_ms/1000, timezone.utc)
        if cutoff >= queried+timedelta(seconds=self.max_age):
            return None
        return self.deal_history.join(trades.trades, queried, position, cutoff, check)

    def _opening_cycle(self,symbol,broker,trades,cutoff,check):
        if self.allocation is not None:
            check();cycle=self.allocation_observation.opening_cycles.get(self.mapping[symbol])
            if cycle is None or cycle.status=='unknown' or cycle.opened_at is None or cycle.cycle_id is None or cycle.source_sha256 is None:return None
            origin=datetime.fromisoformat(cycle.opened_at)
            _need(origin.tzinfo is not None and origin<=cutoff,'retained_allocation_cycle')
            value=dict(cycle_id=cycle.cycle_id,source_sha256=cycle.source_sha256)
            if cycle.status=='initial_inventory':value.update(status='initial_inventory',baseline_at=origin.isoformat())
            else:_need(cycle.status=='held','retained_allocation_cycle');value['opened_at']=origin.isoformat()
            return value
        if self.inputs.capital_baseline is not None:
            # 唯一策略已核初始库存作为来源起点；完整实际成交与本次P一致才恢复开仓时间。
            # 查询事实可跨运行代，不能把仅驻内存的提交序号当作重启后的必要材料。
            from .execution_cycle_source import queried_opening_cycle
            initial=next((row for row in self.inputs.request.cycles if row.symbol==symbol),None)
            return queried_opening_cycle(symbol,self.mapping[symbol],initial,
                self.inputs.capital_baseline['baseline_at'],
                self._broker_rows(broker).get(self.mapping[symbol],(0,0))[0],
                datetime.fromtimestamp(broker.position_received_ms/1000,timezone.utc),cutoff,trades,check)
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

    def _capture(self, context, prices, cutoff, result_sha, *, price_source=None, price_observed_at=None, deadline=float('inf'), broker=None):
        from guanheng_strategy_native import Basis, NativePosition, Observation, Price
        from .execution_facts import _decimal, canonical_raw_price
        _need(set(prices) == set(self.execution), 'native_price_complete')
        canonical_prices = {s:canonical_raw_price(prices[s],self.native_price_ticks[self.mapping[s]])
                            for s in self.execution}  # 本帧唯一规范原价；原prices及其审计身份保持原double字节语义。
        raw, positions = [], []
        own_rows=self._broker_rows(broker) if self.allocation is not None else None
        for symbol in self.execution:
            if own_rows is not None:
                p=context.position(self.mapping[symbol]);actual,valid=own_rows.get(self.mapping[symbol],(0,0))
                wanted=actual if p.enum_target is None else self._shares(p.enum_target)
                positions.append(NativePosition(symbol,actual,valid,wanted if wanted!=actual else None))
                raw.append((symbol,asdict(p)));continue
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
        cash = nav-sum((p.actual*canonical_prices[p.symbol] for p in positions),Fraction(0))
        verified = True
        basis_pnl = Fraction(repr(facts.fund_pnl))
        nav_source, cash_source = 'original-CTA:explicit-genesis+flag0', 'original-CTA:NAV-minus-complete-theoretical-holdings'
        if self.allocation is not None:
            own=self.allocation_observation.strategy
            cash=Fraction(own.spendable_cash_cny)
            nav=Fraction(own.ledger_cash_cny)+sum((p.actual*canonical_prices[p.symbol] for p in positions),Fraction(0))
            basis_pnl=nav-Fraction(self.inputs.policy.initial_capital_cny)
            verified=own.cash_cny is not None
            nav_source,cash_source='ASA:strategy-ledger+own-position-raw-price','ASA:strategy-spendable-cash'
            identity=_digest((identity,allocation_projection(self.allocation_observation)))
        elif self.inputs.capital_baseline is not None:
            from .strategy_capital import observe_broker_capital
            _need(broker is not None and broker.positions_known and broker.position_received_ms is not None, 'capital_positions')
            quantities = self._broker_rows(broker)
            actual_value = sum((canonical_prices[s]*quantities.get(self.mapping[s],(0,0))[0]
                                for s in self.execution), Fraction(0))
            account, qualified = self.capital_reader.read(datetime.now(timezone.utc), deadline)
            ledger_cash=self._native_cash(facts,actual_value,account)
            self.capital_observation = None
            if ledger_cash is not None:
                self.capital_observation = observe_broker_capital(self.inputs.capital_baseline,self.inputs.cash_anchor,
                    Fraction(repr(facts.fund_pnl)),actual_value,cutoff.isoformat(),account,qualified,
                    max_age_seconds=self.max_age,
                    position_observed_at=datetime.fromtimestamp(broker.position_received_ms/1000,timezone.utc).isoformat(),
                    price_observed_at=price_observed_at)
            # 原NSQ字段承载本次实际盈亏；缺账户时仅构造未核准basis，保持资金等待。
            nav=Fraction(self.inputs.capital_baseline['total_cny']) if self.capital_observation is None else Fraction(self.capital_observation['nav_cny'])
            basis_pnl=nav-Fraction(self.inputs.capital_baseline['total_cny'])
            spendable = None if self.capital_observation is None else self.capital_observation['spendable_cash_cny']
            cash, verified = Fraction(spendable or '0'), spendable is not None
            nav_source, cash_source = 'broker-cash-delta+actual-position-raw-price', 'broker-cash-delta+account-frozen-available'
            identity = _digest((identity,self.capital_observation,asdict(broker)))
        basis = Basis(cutoff.isoformat(),result_sha,_decimal(nav),_decimal(basis_pnl),_decimal(cash),
                      self.inputs.fee_reserve_cny,nav_source,cash_source,self.inputs.fee_source,
                      tuple(Price(s,_decimal(canonical_prices[s]),price_source or self.inputs.market_manifest_source) for s in self.execution),verified,identity)
        observed = Observation(cutoff.isoformat(),'original-CTA:cash-long-theoretical',tuple(positions),True,identity)
        return facts,raw,basis,observed

    def _buy_fee_basis(self, target, basis, observation):
        """为本次原NSQ实际消费的目标装配新增买入组费用预留；不修改目标或现金。

        显式预留作为最低值，并覆盖已核WT开仓费率、同次原价和原NSQ份数；
        共用回放的费用事实装配，实际费用继续归WT。
        此值是本策略预算的配置模型预留，不声明券商佣金或独立子账户现金。
        """
        from .execution_facts import buy_fee_basis
        return buy_fee_basis(target, self.inputs.policy, basis, observation, self.mapping,
                             self.native_fees, self.native_fee_source, split_fills=True)

    def _current_quotes(self, context, cutoff):
        """读取原WT已应用tick副本；日线读缓存不承担当前报价及事件时点。"""
        read=getattr(context,'quote',None)
        if read is None:return None
        prices,stamps={},[]
        for symbol in self.execution:
            quote=read(self.mapping[symbol])
            if quote is None:return None
            _need(type(quote.price_cny)in(int,float)and math.isfinite(quote.price_cny)and quote.price_cny>0,'native_quote')
            stamp=datetime.strptime(str(quote.action_date)+f"{quote.action_time//1000:06d}",'%Y%m%d%H%M%S')
            stamp=stamp.replace(tzinfo=ZoneInfo('Asia/Shanghai'),microsecond=quote.action_time%1000*1000)
            if not stamp<=cutoff<stamp+timedelta(seconds=self.capital_market['max_age_seconds']):return None
            prices[symbol]=quote.price_cny;stamps.append(stamp)
        return prices,min(stamps).isoformat()

    def _execution_capture(self, broker, basis, theoretical, pending_orders=()):
        """唯一策略的实际数量沿本轮P；原理论账本只承担财务basis与pending信号。

        调用方先核P的新鲜度；同一来源摘要绑定两份观察，避免把理论目标到位
        授为券商成交。原绝对目标准入、活动订单和剩量继续归原执行器。
        """
        from guanheng_strategy_native import NativePosition, Observation
        _need(broker.positions_known, 'broker_unknown')
        rows = self._broker_rows(broker)
        identity = _digest((theoretical.native_observation_id,asdict(broker),
                            tuple(asdict(row) for row in pending_orders)))
        pending={row.symbol for row in pending_orders} if self.allocation is None else (set(self.targets) if self.allocation_observation.strategy.pending_groups else set())
        positions = tuple(NativePosition(p.symbol,*rows.get(self.mapping[p.symbol],(0,0)),
                          (p.pending_target if p.pending_target is not None else p.actual)
                          if self.mapping[p.symbol] in pending else p.pending_target)
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
        allocation_reason=self._allocation_refresh(context,deadline);check()
        cutoff = datetime.now(timezone.utc);broker = context.broker_observation();trades=context.broker_trades() if self.allocation is None else None;check()
        self.sequence += 1
        status, reason, cycles, metadata = (None if allocation_reason is None else 'waiting_allocation'),allocation_reason,[],dict(self.cycles)
        if not broker.positions_known or broker.position_received_ms is None:
            status, reason = 'waiting_broker_position','broker_position_unknown'
        else:
            received = datetime.fromtimestamp(broker.position_received_ms/1000,timezone.utc)
            if not received <= cutoff < received+timedelta(seconds=self.max_age):
                status, reason = 'waiting_broker_position','broker_position_stale'
        rows = self._broker_rows(broker)
        if status is None:
            if self.execution_enabled and self.allocation is not None and not self._shared_announced:
                from .profile_facts import announce_shared_hold
                announce_shared_hold(context,self.id,self.targets,self.allocation_observation,self.allocation,
                    source_identity=self.state_identity,deadline=deadline)
                self._shared_announced=True
            source = _digest(asdict(broker))
            cycle_trades = self._historical_cycle_facts(broker, trades, cutoff, check)
            if self.deal_history is not None and cycle_trades is None:
                status, reason = 'waiting_actual_cycle', 'broker_deal_coverage_required'
            for symbol in self.execution:
                quantity = rows.get(self.mapping[symbol],(0,0))[0]
                old = metadata.get(symbol)
                if not quantity:
                    self._track_flat_source(symbol,broker,trades,old)
                    metadata.pop(symbol,None);cycles.append(PositionCycle(symbol,'flat',0,source))
                else:
                    actual=self._opening_cycle(symbol,broker,cycle_trades,cutoff,check)
                    if self.allocation is not None or self.inputs.capital_baseline is not None:
                        # 完整查询已证明当前周期；真实卖平再买覆盖旧周期，缺证据则等待。
                        old=actual
                    elif old is None:old=actual
                    elif actual is not None and actual['cycle_id']==old['cycle_id']:
                        if datetime.fromisoformat(actual['opened_at'])<datetime.fromisoformat(old['opened_at']):old=actual
                    if old is None:
                        if status is None:
                            status, reason = 'waiting_actual_cycle', 'actual_opening_source_required'
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
        if self.deal_history is not None:
            candidate['broker_deal_history'] = self.deal_history.source()
        if self.allocation_observation is not None:candidate['allocation_observation']=allocation_projection(self.allocation_observation,include_read_projection=True)
        candidate['cycle_metadata']=dict(metadata)
        if self.inputs.capital_baseline is not None:
            candidate['capital_baseline'] = self.inputs.capital_baseline
            if self.capital_observation is not None:
                candidate['capital'] = self.capital_observation
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
        price_stamp=None
        if status is None and self.market_window is not None:
            current=self._current_quotes(context,cutoff)
            if current is None:
                status,reason='waiting_market_input','current_applied_quote_unavailable'
                candidate.update(status=status,reason=reason)
            else:prices,price_stamp=current
        if status is not None and self.capital_observation is not None:
            # 行情/持仓等待不改变账户事实资格；沿原NAP身份和本轮D续核，保留原估值时点。
            from .strategy_capital import refresh_account_constraint
            self.capital_observation = refresh_account_constraint(self.capital_observation,self.capital_reader,deadline)
            candidate['capital'] = self.capital_observation
        if status is None:
            if self.market_window is None:prices = {s:context.price(self.mapping[s]) for s in self.execution}
            _need(all(type(p) in (int,float) and math.isfinite(p) and p > 0 for p in prices.values()), 'native_price')
            price_source = None if self.market_window is None else 'original-CTA:applied-tick;window:'+candidate['market_window']['publication_sha256']
            facts,raw,basis,observed = self._capture(context,prices,cutoff,result['input_sha256'],price_source=price_source,price_observed_at=price_stamp,deadline=deadline,broker=broker)
            if self.capital_observation is not None:
                candidate['capital'] = self.capital_observation
            elif candidate.get('capital') is not None:
                # 本轮实际估值缺账户现金依据时，旧金额可留存，当前可用资格保持未知。
                candidate['capital'] = dict(candidate['capital'],
                    account_observation_qualified=False,spendable_cash_cny=None)
            candidate['native_cash_basis']=getattr(self,'native_cash_basis',None)
            # 活动单只读自原WT表；即使P已到目标，原单尚未终态也不结清/交接阶段。
            pending=context.pending_orders() if self.execution_enabled else ()
            basis,observed,execution = self._execution_capture(broker,basis,observed,pending)
            if not self.execution_enabled:
                outcome,previous_status=None,None
            elif self.allocation is not None and not basis.native_nav_verified:
                # 实际手续费等待与已确定的库存退出分开，保留原卖出阶段及未决订单身份。
                from guanheng_strategy_native.planner import advance_known_sells
                outcome = advance_known_sells(decision.target, self.inputs.policy, execution, basis, state)
                previous_status = None
                state = outcome.state
                if outcome.submit_targets:
                    exits = self._exit_values(result['next_exits'])
            elif self.inputs.capital_baseline is not None and not basis.native_nav_verified:
                # 当前现金约束缺失属于来源等待。原NSQ只接受已核basis；保留
                # 上一阶段与未决责任，下一轮取得新来源后再交原核推进。
                from guanheng_strategy_native import Outcome
                outcome, previous_status = Outcome('waiting_basis','account_cash_unavailable',state), None
            else:
                def fee_basis(target, current_basis, observation):
                    # 原接缝可先推进未决旧代再交接新代；每次实际目标分别装配并发布本次费用来源。
                    nonlocal basis
                    basis = self._buy_fee_basis(target,current_basis,observation)
                    return basis
                outcome, previous_status = advance_retained(decision.target,self.inputs.policy,execution,basis,state,
                    basis_for_target=fee_basis)
                state = outcome.state;exits = self._exit_values(result['next_exits'])
            vector = ()if outcome is None else tuple((self.mapping[t.symbol],t.shares) for t in outcome.submit_targets)
            candidate.update(status='observing'if outcome is None else outcome.status,
                             reason='analysis_only'if outcome is None else outcome.reason,core_result=result,
                             outcome=None if outcome is None else asdict(outcome),
                             quantity_basis=asdict(basis),native_observation=asdict(observed),raw_positions=raw,
                             raw_prices=tuple((s,prices[s]) for s in self.execution),  # 本帧原始未复权double报价，CNY/份，仅审计；规范原价仍在quantity_basis.prices。
                             execution_observation=asdict(execution),execution_position_qualified=True,
                             native_clock=asdict(facts),previous_status=previous_status)
            if vector:candidate['target_readback'] = dict(vector)
        # 编码和投影预检共用本轮D，随后才进入原setter/KV副作用。
        text = self._state_payload(state,self.sequence,metadata,exits)
        self._publish(candidate,preview=True,deadline=deadline);check()
        if vector:
            if self.allocation is not None:
                from .profile_facts import common_prices
                commons=common_prices(context,self.mapping,self.native_price_ticks,self.participants,now=cutoff,max_age=self.max_age)
                self.allocation.prepare_intent(self.id,context.event.epoch,source_sha256=result['input_sha256'],known_at=cutoff.isoformat(),
                    buy_price_caps={},common_prices=commons,deadline=deadline)
            _need(dict(context.set_targets(vector)) == dict(vector), 'target_readback');check()
        context.store_quantity_state(text);check()
        self.state,self.cycles,self.exits = state,metadata,exits
        self._publish(candidate,deadline=deadline);check()


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
        value=dict(value,native_setter_count=runtime.status()['setters'])  # 原ManagedStrategy累计setter调用数；原子只读，不推导交易事实。
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
    from .strategy_profiles import shared_profiles, build_strategies
    allocation, attribution = None, None
    if shared_profiles(native):
        from .account_attribution import create_runtime_attribution
        allocation, attribution = create_runtime_attribution(native,config,args.control,args.control_id,deadline=args.deadline)
    strategies = build_strategies(native,publish,config,deadline=args.deadline,code_identity=code_identity,
                                 retained_factory=RetainedStrategy,allocation=allocation)
    # -S准入后，关键纯核与NSQ实际导入路径仍逐项属于同一次绑定源码。
    for name, module in tuple(sys.modules.items()):
        if name.split('.')[0] in _python_packages(native):
            path = Path(module.__file__).absolute()
            _need(str(path) in identities and hashlib.sha256(_python_bytes(path, deadline=args.deadline)).hexdigest()
                  == identities[str(path)], 'imported_module_identity')
    runtime = CtaRuntime(config, tuple(s.binding() for s in strategies), deadline=args.deadline, attribution=attribution)
    # 同一原执行进程持有账户约束线程；线程只读NAP及发布值，从不借用Native上下文。
    # K线回调和账户更新共享唯一原子发布者，估值时间与策略sequence保持原值。
    refresh_stop = Event()
    from .strategy_capital import AccountCashReader, refresh_capital_report
    readers = {s.id:AccountCashReader(s.capital_reader.binding,s.max_age)
               for s in strategies if s.capital_reader is not None}
    capital_strategies = {s.id:s for s in strategies if s.capital_reader is not None}
    def refresh_accounts():
        try:
            while not refresh_stop.wait(10):
                deadline = time.monotonic()+2
                if not publication_lock.acquire(timeout=max(0,deadline-time.monotonic())):
                    continue
                try:
                    for strategy_id,reader in readers.items():
                        report = reports.get(strategy_id)
                        if report is None:
                            continue
                        strategy = capital_strategies[strategy_id]
                        updated = refresh_capital_report(report,reader,deadline,
                            initial_basis=strategy._initial_capital_basis,
                            origin=strategy.inputs.capital_baseline,anchor=strategy.inputs.cash_anchor)
                        if updated != report:
                            publish_locked(strategy_id,updated,deadline=deadline)
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
    workers=tuple(s.signals for s in strategies if hasattr(s,'signals'))
    try:
        for worker in workers:worker.start()
        if refresher is not None:
            refresher.start()
        result = runtime.run(args.control, args.control_id)
    finally:
        refresh_stop.set()
        for worker in workers:worker.request_close()
        worker_deadline=time.monotonic()+3
        workers_joined=all([worker.close(worker_deadline) for worker in workers])
        if workers:
            with (args.control/'signal-workers-closed.json').open('x',encoding='ascii') as stream:
                json.dump(dict(joined=workers_joined,pending=any(w.pending for w in workers)),stream)
        if refresher is not None:
            joined = refresher.join_until(time.monotonic()+3)
            with (args.control/'capital-refresh-closed.json').open('x',encoding='ascii') as stream:
                json.dump(dict(
                    joined=joined,  # 原ThreadOwner已取得标准线程退出/join证明；False表示关闭未确认。
                    pending=refresher.pending),stream)  # 账户读取线程仍有生命周期责任；布尔值，由原owner提供。
            _need(joined,'capital_refresh_close_unconfirmed')
        _need(workers_joined,'signal_worker_close_unconfirmed')
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
