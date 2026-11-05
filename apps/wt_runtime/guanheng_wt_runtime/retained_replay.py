"""唯一1.2.1日线回放，使用原持仓/资金、NSQ、撮合和userdata。

同步run由外层预绑定Job和总截止约束。首模型从原生flat开始，独占所有setter；
不用于实时接管。完整报告的HTTP/归档消费者沿各自公开schema接入。
"""
from dataclasses import dataclass, fields, MISSING, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hashlib import sha256
from threading import get_ident
from time import monotonic
import json

from guanheng_strategy_core.contracts import EvaluationBudget, canonical_bytes
from guanheng_strategy_core.models import observation_close_at
from guanheng_strategy_native import Basis, Limits, Price, QuantityPolicy
from guanheng_strategy_v1 import (
    CycleExit, PositionCycle, RetainedHistoricalModel, RetainedInput,
    describe_evaluation, summarize_diagnostics, contextualize_diagnostics,
    RetainedValidationError, SYMBOLS, STRATEGY_ID, STRATEGY_VERSION,
)
from .retained_evaluation import evaluate_retained, advance_retained
from .strategy_porter import BacktestConfig, BacktestPorter, Callbacks, Target
from .strategy_replay_facts import (
    SessionError, _digest, _json, admit_native_files, capture_native,
)

ORIGINAL_BT_SHA256 = '4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e'
ABI_PROBE_SHA256 = 'a7fdb6ecd763ebdd395d4b0d11d78a1f6d30bbb57f23a63630c2410c243b71b6'
STATE_KEY = 'rr112_replay_v1'
REPORT_SCHEMA = 'guanheng.retained-replay-report.v1'
REPORT_SCOPE = 'retained-historical-backtest-only; final-basis/availability-assumed; RT/broker/production-unqualified'
ZONE = timezone(timedelta(hours=8))


@dataclass(frozen=True, slots=True)
class RetainedReplayInput:
    request: RetainedInput
    model: RetainedHistoricalModel
    policy: QuantityPolicy
    fee_reserve_cny: str | None
    fee_source: str | None
    market_manifest_source: str
    price_unit: str = 'CNY/share'
    volume_unit: str = 'share'
    amount_unit: str = 'unknown'
    schema: str = 'guanheng.retained-replay-input.v1'

    @classmethod
    def from_dict(cls, value):
        declared = fields(cls)
        required = {f.name for f in declared if f.default is MISSING}
        if (cls is not RetainedReplayInput or type(value) is not dict
                or not required <= set(value) <= {f.name for f in declared}):
            raise SessionError('唯一策略回放输入字段与固定协议不一致')
        data = dict(value)
        data['request'] = RetainedInput.from_dict(data['request'])
        data['model'] = RetainedHistoricalModel.from_dict(data['model'])
        if type(data['policy']) is not dict:
            raise SessionError('数量policy需要固定对象')
        try:
            data['policy'] = QuantityPolicy(**data['policy'])
            return cls(**data)
        except TypeError:
            raise SessionError('数量policy字段与固定协议不一致') from None


class RetainedBacktestSession:
    """一个新原生回放owner；周期元数据和退出状态沿原userdata保存。

    数量始终取当次原持仓，周期只存身份/开仓时间，不另记持仓或资金。
    所有失败均终止本次run，原生部分输出交外层隔离，禁止作为完成报告。
    """
    def __init__(self, inputs: RetainedReplayInput, *, budget=EvaluationBudget(),
                 max_result_bytes=8388608):
        if (type(inputs) is not RetainedReplayInput or inputs.schema != 'guanheng.retained-replay-input.v1'
                or type(budget) is not EvaluationBudget):
            raise SessionError('需要本版明确回放输入和预算')
        if type(max_result_bytes) is not int or not 1 <= max_result_bytes <= 8388608:
            raise SessionError('回放报告预算超过硬上限')
        request = RetainedInput.from_dict(json.loads(canonical_bytes(inputs.request, max_bytes=8388608)))
        if any(c.status != 'flat' for c in request.cycles) or request.previous_exits:
            raise SessionError('本回放从新原生flat开始，持仓接管由实时owner负责')
        model = inputs.model
        if type(model) is not RetainedHistoricalModel:
            raise SessionError('需要明确最终批次历史假设')
        model = RetainedHistoricalModel(**{k: getattr(model, k) for k in model.__dataclass_fields__})
        if type(inputs.policy) is not QuantityPolicy:
            raise SessionError('需要显式策略理论本金policy')
        policy = QuantityPolicy(**{k: getattr(inputs.policy, k) for k in inputs.policy.__dataclass_fields__})
        if (inputs.price_unit != 'CNY/share' or inputs.volume_unit not in ('share', 'lot') or inputs.amount_unit != 'unknown'
                or type(inputs.market_manifest_source) is not str or not 1 <= len(inputs.market_manifest_source) <= 256
                or any(ord(c) < 32 for c in inputs.market_manifest_source)):
            raise SessionError('原生现金ETF需要明确价量单位和来源；金额保留未知')
        Basis(request.decision_cutoff.isoformat(), '0'*64, policy.initial_capital_cny, '0',
            policy.initial_capital_cny, inputs.fee_reserve_cny, 'preflight', 'preflight', inputs.fee_source,
            tuple(Price(s, None, 'preflight') for s in SYMBOLS), False, 'preflight')
        self._inputs = replace(inputs, request=request, model=model, policy=policy)
        self._budget, self._maximum = replace(budget), max_result_bytes
        self._mapping = {s: ('SSE' if s.endswith('.SH') else 'SZSE')+'.ETF.'+s[:6] for s in SYMBOLS}
        self._execution, self._quantity_limits = SYMBOLS, Limits()
        self._series = {}
        from .strategy_porter import Bar
        for symbol, native in self._mapping.items():
            self._series[native] = tuple(Bar(int(r.trade_date.strftime('%Y%m%d')), 0,
                r.open, r.high, r.low, r.close, r.close, r.amount, r.volume)
                for r in request.history.observations if r.symbol == symbol)
        self._days = tuple(b.date for b in self._series[self._mapping['510300.SH']])
        # 完整批次先经唯一核校验；native加载前拒绝错基准、错配对和不完整输入。
        end = observation_close_at(request.analysis.basis_date)
        preflight = replace(request, decision_cutoff=end, cycles_captured_at=end,
            cycles_valid_until=end+timedelta(seconds=1))
        evaluate_retained(preflight, policy, historical_model=model, budget=self._budget)
        self._owner, self._porter, self._started, self._initialized = get_ident(), None, False, False
        self._session_id, self._sequence, self._state = None, 0, None
        self._records, self._last_clock, self._bar_count = [], None, 0
        self._last_userdata = ''
        self._input_id = sha256(canonical_bytes(self._inputs)).hexdigest()

    @staticmethod
    def _clock(day, minute):
        return datetime.strptime(str(day*10000+minute), '%Y%m%d%H%M').replace(tzinfo=ZONE)

    def _owner_porter(self, porter):
        if get_ident() != self._owner or porter is not self._porter or not self._started:
            raise SessionError('只接受本次回放owner线程和上下文')

    def _initialize(self, porter):
        self._owner_porter(porter)
        funds = porter.funds()
        if self._initialized or porter.targets() or (funds.net, funds.realized, funds.dynamic, funds.fees) != (0, 0, 0, 0):
            raise SessionError('原回放需要新flat且无损益')
        for native in self._mapping.values():
            value = porter.position(native)
            if (value.total, value.valid, value.first_entry, value.last_entry) != (0, 0, 0, 0):
                raise SessionError('原回放初始持仓非空')
        if porter.load_userdata(STATE_KEY):
            raise SessionError('新回放原用户状态已存在')
        for native in sorted(self._series):
            porter.get_bars(native, 'd1', 2, main=native == self._mapping['510300.SH'])
            porter.subscribe_bars(native, 'd1')
        self._initialized = True

    def _loader(self, symbol, period):
        if period != 'd1' or symbol not in self._series:
            raise SessionError('只读取本次冻结日线')
        return self._series[symbol]

    def _on_bar(self, porter, symbol, period, bar):
        self._owner_porter(porter)
        if period != 'd1' or symbol not in self._series or bar not in self._series[symbol]:
            raise SessionError('原bar回调与本次冻结输入失配')
        self._bar_count += 1
        if self._bar_count > 32768:
            raise SessionError('bar回调超过容量')

    def _cycles(self, porter, capture):
        text = porter.load_userdata(STATE_KEY)
        if text != self._last_userdata:
            raise SessionError('原生策略用户状态在独占回放期间发生变化')
        previous = json.loads(text) if text else {'cycles': {}, 'exits': []}
        cycles, metadata = [], {}
        raw = {p.symbol: p for p in capture.positions}
        for position in capture.observation.positions:
            symbol, quantity = position.symbol, position.actual
            cycle = PositionCycle(symbol, 'flat', 0, capture.observation.native_observation_id)
            if quantity:
                old = previous['cycles'].get(symbol)
                if old is None:
                    entry = raw[self._mapping[symbol]].first_entry
                    opened = self._clock(entry//10000, entry % 10000)
                    old = dict(cycle_id=_digest((self._session_id, symbol, entry)), opened_at=opened.isoformat())
                metadata[symbol] = old
                cycle = replace(cycle, status='held', quantity=quantity,
                    cycle_id=old['cycle_id'], opened_at=datetime.fromisoformat(old['opened_at']))
            cycles.append(cycle)
        exits = tuple(CycleExit(e['symbol'], e['cycle_id'], datetime.strptime(e['trade_date'], '%Y-%m-%d').date(),
            e['path']) for e in previous['exits'])
        return tuple(cycles), exits, metadata

    def _market_request(self, cutoff, cycles, exits, check):
        """原最终批次入口；逐日来源只替换市场输入，原生状态仍由本owner提供。"""
        full = self._inputs.request
        request = replace(full, history=replace(full.history,
                observations=tuple(r for r in full.history.observations if r.trade_date <= cutoff.date())),
            analysis=replace(full.analysis,
                bars=tuple(b for b in full.analysis.bars if b.observation.trade_date <= cutoff.date())),
            cycles=cycles, previous_exits=exits, decision_cutoff=cutoff,
            cycles_captured_at=cutoff, cycles_valid_until=cutoff+timedelta(seconds=1))
        model = self._inputs.model
        if model.auxiliary_research is not None:
            model = replace(model, auxiliary_input_sha256=sha256(canonical_bytes(request.history)).hexdigest())
        return request, model, None

    def _report_market(self):
        """原报告合同保持；明确逐日来源的派生入口登记其自己的报告族。"""
        return {}

    def _calculate(self, porter, day, minute):
        self._owner_porter(porter)
        deadline = monotonic()+self._budget.max_seconds
        def check():
            if monotonic() >= deadline:
                raise SessionError('唯一策略完整回调期限耗尽')
        cutoff = self._clock(day, minute)
        if (not self._initialized or minute != 1500 or day not in self._days
                or self._last_clock is not None and cutoff <= self._last_clock or len(self._records) >= 4096):
            raise SessionError('回放时钟失序、重复或超过容量')
        self._last_clock = cutoff
        for native, rows in self._series.items():
            check()
            if porter.get_bars(native, 'd1', 4096).bars != tuple(b for b in rows if b.date <= day):
                raise SessionError('原生完整行情前缀与冻结输入失配')
        capture = capture_native(self, porter, day, minute, _digest((self._input_id, day)), check=check)
        cycles, exits, metadata = self._cycles(porter, capture)
        request, historical_model, publication = self._market_request(cutoff, cycles, exits, check)
        result, outcome, previous_status = None, None, None
        if len(request.history.observations) < 800:
            status, reason = 'warming_up', '完整历史尚未完成策略预热'
        else:
            check()
            remaining = replace(self._budget, max_seconds=min(self._budget.max_seconds, deadline-monotonic()))
            try:
                decision = evaluate_retained(request, self._inputs.policy,
                    historical_model=historical_model, budget=remaining,
                    previous_target=self._state.target if self._state is not None else None)
            except RetainedValidationError as error:
                if error.code != 'warmup_required':
                    raise
                status, reason = 'warming_up', error.reason
            else:
                result = decision.result.to_dict()
                capture = replace(capture, basis=replace(capture.basis, input_sha256=result['input_sha256']))
                outcome, previous_status = advance_retained(decision.target, self._inputs.policy,
                    capture.observation, capture.basis, self._state, limits=self._quantity_limits)
                status, reason = outcome.status, outcome.reason
        check()
        # 报告只保存当日业务结果与原值；累计模型信号由固定输入复现，不逐日重复。
        summary = None if result is None else dict(
            schema='guanheng.retained-replay-decision.v1', full_result_sha256=_digest(result),
            **{k: v for k, v in result.items() if k not in ('schema', 'model_decisions', 'allocation_state', 'diagnostics')})
        if summary is not None:
            prior = next((r['result']['targets'] for r in reversed(self._records) if r['result'] is not None), None)
            self._business_diagnostics = contextualize_diagnostics(result['diagnostics'],
                targets=result['targets'], previous_targets=prior)
            summary['diagnostics'] = summarize_diagnostics(self._business_diagnostics)
        record = dict(trading_date=day, minute=minute, status=status, reason=reason,
            result=summary, capture=capture, outcome=outcome, previous_status=previous_status, readback=())
        if publication is not None:
            record['market_window'] = publication
        if len(_json((*self._records, record)).encode('ascii'))+65536 > self._maximum:
            raise SessionError('原生目标提交前报告容量耗尽')
        vector = () if outcome is None else tuple(Target(self._mapping[t.symbol], t.shares) for t in outcome.submit_targets)
        if vector:
            check()
            record['readback'] = porter.submit_targets(vector, 'rr112-nsq-replay')
        check()
        next_exits = json.loads(self._last_userdata)['exits'] if self._last_userdata else []
        if result is not None:
            next_exits = result['next_exits']
        text = _json(dict(schema='guanheng.retained-replay-state.v1', session_id=self._session_id,
            cycles=metadata, exits=next_exits))
        check()
        porter.store_userdata(STATE_KEY, text)
        check()
        self._last_userdata = text
        if outcome is not None:
            self._state = outcome.state
        self._records.append(json.loads(_json(record)))

    def run(self, library: Path, abi_probe: Path, config: BacktestConfig) -> dict:
        """外层独占Job中的同步主入口；固定原DLL正常结束并释放后才返回报告。"""
        if get_ident() != self._owner or self._started or type(config) is not BacktestConfig:
            raise SessionError('本回放只允许创建线程运行一次')
        self._started = True
        if (config.end != self._days[-1]*10000+1500 or config.start//10000 not in self._days
                or config.start % 10000 > 1500 or Path(config.cwd).resolve() != Path.cwd().resolve()):
            raise SessionError('回放起止必须覆盖明确输入末日及独占CWD')
        identities, frozen = admit_native_files(self._mapping, config)
        base = Path(config.cwd)/'session-basefiles'
        base.mkdir(exist_ok=False)
        for name, data in frozen.items():
            with (base/(name+'.json')).open('xb') as stream:
                stream.write(data)
        config = replace(config, **{name: base/(name+'.json') for name in frozen})
        self._session_id = _digest((self._input_id, str(config.cwd), config.start, config.end,
            config.name, identities, ORIGINAL_BT_SHA256, ABI_PROBE_SHA256))
        porter = self._porter = BacktestPorter(library, ORIGINAL_BT_SHA256, abi_probe, ABI_PROBE_SHA256,
            symbols=tuple(sorted(self._series)), execution_symbols=tuple(sorted(self._mapping.values())),
            loader=self._loader, callbacks=Callbacks(self._initialize, self._calculate, self._on_bar))
        porter.configure(config)
        try:
            counts = porter.run()
        finally:
            porter.release()
        expected = tuple(d for d in self._days[1:] if d >= config.start//10000)
        if tuple(r['trading_date'] for r in self._records) != expected:
            raise SessionError('原生正常结束但计算日期缺失')
        output = Path(config.output)/config.name
        state_file = output/('ud_'+config.name+'.json')
        if (not state_file.is_file() or state_file.stat().st_size > 131072
                or json.loads(state_file.read_bytes()) != {STATE_KEY: self._last_userdata}):
            raise SessionError('原生正常结束后用户状态磁盘保存失配')
        native_outputs = []
        for name in ('funds.csv', 'positions.csv', 'trades.csv', 'closes.csv', 'signals.csv',
                     config.name+'.json', 'ud_'+config.name+'.json'):
            path = output/name
            if not path.is_file() or path.stat().st_size > 8388608:
                raise SessionError('原生完成输出缺失或超过有界容量')
            native_outputs.append((name, sha256(path.read_bytes()).hexdigest()))
        report = dict(schema=REPORT_SCHEMA, session_id=self._session_id, input_sha256=self._input_id,
            scope=REPORT_SCOPE, policy=self._inputs.policy,
            configuration_sha256=sha256(canonical_bytes(self._inputs.request.configuration)).hexdigest(),
            strategy_id=STRATEGY_ID, strategy_version=STRATEGY_VERSION, historical_model=self._inputs.model,
            status=self._records[-1]['status'] if self._records else 'blocked_no_calculation',
            native_files=identities, native_outputs=tuple(native_outputs), callback_counts=counts, records=tuple(self._records),
            source_qualified=False, execution_qualified=False)
        report.update(self._report_market())
        # 顶层模型与逐日结果共用领域规范编码，时间及输入身份保持同一表示。
        report['diagnostics'] = getattr(self, '_business_diagnostics', None) or describe_evaluation(
            self._inputs.request.history.observations, calculation_state='warming_up' if self._records else 'not_scheduled')
        raw = canonical_bytes(report, max_bytes=self._maximum)
        return json.loads(raw)
