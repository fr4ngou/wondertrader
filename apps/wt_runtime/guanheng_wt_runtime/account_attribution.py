"""原Native归属回调的值边界；账本由ASA拥有，命令继续由原WT/Host拥有。"""
from __future__ import annotations

import ctypes as C
from dataclasses import dataclass
from dataclasses import asdict
import hashlib
import json
import math
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
import sys
from threading import RLock, local
from time import monotonic
from uuid import UUID, NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo


class AttributionError(RuntimeError):
    """有限原因码；失败保留原Native责任，不产生补发命令。"""


def _need(value, reason):
    if not value:
        raise AttributionError(reason)


class NativeEvent(C.Structure):
    """GhAttributionEventV1；指针仅由Native拥有，回调返回前完整复制。"""
    _pack_ = 8
    _fields_ = [
        ('size', C.c_uint32),  # 本结构字节数，严格核验ABI1布局。
        ('version', C.c_uint32),  # 独立归属ABI版本，固定1。
        ('kind', C.c_uint32),  # 原11类事件阶段，不能当金融总状态。
        ('thread_role', C.c_uint32),  # 1策略ctx、2执行owner、3原I/O worker。
        ('epoch', C.c_uint64),  # 原ctx代际；非ctx阶段可以为0。
        ('remaining_ms', C.c_uint64),  # 原阶段剩余毫秒；0表示该阶段未单独给D。
        ('json_bytes', C.c_uint32),  # 原UTF8字节数，最多2MiB，不含NUL。
        ('reserved', C.c_uint32),  # ABI1固定0。
        ('json_utf8', C.c_void_p),  # Native借用指针，跨回调使用前必须复制。
    ]


class NativeReply(C.Structure):
    """GhAttributionReplyV1；初值拒绝，成功完成持久动作后才明确答复。"""
    _pack_ = 8
    _fields_ = [
        ('size', C.c_uint32),  # 本结构大小，ABI1为24字节。
        ('version', C.c_uint32),  # 回复版本固定1。
        ('decision', C.c_int32),  # 0确认/允许，1仅authorize暂缓，-1失败。
        ('reserved', C.c_uint32),  # ABI1固定0。
        ('authorized_quantity', C.c_double),  # authorize整数份数，其余事件固定0。
    ]


NativeCallback = C.CFUNCTYPE(C.c_int32, C.POINTER(NativeEvent), C.POINTER(NativeReply), C.c_void_p)


@dataclass(frozen=True)
class AttributionEvent:
    kind: int  # 原Native阶段1至11。
    thread_role: int  # 原回调线程角色；不授跨线程ctx权限。
    epoch: int  # 原ctx epoch，不作为跨重启持久身份。
    body: dict  # 本次完整复制、已严格解析的JSON；handler同步拥有，不引用Native。
    raw: bytes  # 完整原UTF8正文，用于保存原接收证明；不输出整段私有配置。
    sha256: str  # 原事件正文SHA；Source证明另取body原source_sha256。
    deadline: float  # 单调绝对截止，复制/解析/handler共享且不得刷新。


def _pairs(values):
    result = {}
    for key, value in values:
        _need(key not in result, 'duplicate_json_key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise AttributionError('nonfinite_json')


def _validate_tree(body):
    pending = [(body, 0)]
    while pending:
        value, depth = pending.pop()
        _need(depth <= 24, 'attribution_json_depth')
        if type(value) is float:
            _need(math.isfinite(value), 'nonfinite_json')
        elif type(value) is dict:
            pending.extend((child, depth + 1) for child in value.values())
        elif type(value) is list:
            pending.extend((child, depth + 1) for child in value)


class AttributionBridge:
    """同配置线程注册一次，持有callback至全部原worker回收。

    handler(event)同步返回：authorize为允许的整数份数（0表示暂缓），
    其余阶段返回None。handler不得重入Native控制/交易API，不执行Source网络读取。
    callback_seconds为声明的本地持久回调资源预算；有原阶段D时取二者较早值。
    本对象不调用下单/撤单、不维护第二份订单队列或归属数据库。
    """

    def __init__(self, handler, *, callback_seconds, clock=monotonic):
        _need(callable(handler) and callable(clock), 'callback_handler')
        _need(type(callback_seconds) in (int, float) and math.isfinite(callback_seconds)
              and callback_seconds > 0, 'callback_budget')
        self._handler, self._clock, self._seconds = handler, clock, callback_seconds
        self._callback = NativeCallback(self._receive)
        self._runtime = None
        self._failure = None
        self._borrow = local()
        self._owner = None

    def bind_owner(self, owner):
        """仅由同次CtaRuntime装配绑定；不创建另一把金融租约。"""
        _need(self._owner is None and callable(getattr(owner, 'financial_borrowed', None)), 'attribution_owner')
        self._owner = owner

    @property
    def callback_active(self):
        """仅当前真实Native回调线程的同步借用；不能跨线程保存。"""
        return bool(getattr(self._borrow, 'active', False))

    def owner_check(self):
        """借用原Runtime账户租约；配置/退出后及普通后台线程均无账本写权限。"""
        _need(self._owner is not None and self._owner.financial_borrowed(), 'attribution_owner_not_borrowed')

    @property
    def failure(self):
        """最近原异常供受控owner诊断；不把异常或源正文自动打印。"""
        return self._failure

    def register(self, runtime):
        """原run前向已核SHA的Runtime DLL注册；其负责传给同次Managed/Standard。"""
        _need(self._runtime is None, 'callback_already_registered')
        version = getattr(runtime, 'gh_cta_attribution_abi_version', None)
        layout = getattr(runtime, 'gh_cta_attribution_layout', None)
        configure = getattr(runtime, 'gh_cta_attribution_configure', None)
        _need(version is not None and layout is not None and configure is not None, 'attribution_capability')
        version.argtypes, version.restype = [], C.c_uint32
        layout.argtypes, layout.restype = [C.c_uint32], C.c_uint64
        _need(version() == 1 and layout(1) == C.sizeof(NativeEvent)
              and layout(2) == C.sizeof(NativeReply), 'attribution_layout')
        configure.argtypes, configure.restype = [NativeCallback, C.c_void_p], C.c_int32
        _need(configure(self._callback, None) == 0, 'attribution_registration')
        self._runtime = runtime  # 原运行体/回调一并保留至进程owner正常回收。

    def _receive(self, event_pointer, reply_pointer, user):
        previous_borrow = self.callback_active
        try:
            _need(not previous_borrow, 'attribution_callback_reentry')
            _need(bool(event_pointer) and bool(reply_pointer), 'attribution_pointer')
            header, reply = event_pointer.contents, reply_pointer.contents
            _need(reply.size == C.sizeof(NativeReply) and reply.version == 1
                  and reply.reserved == 0, 'attribution_reply_layout')
            reply.decision, reply.authorized_quantity = -1, 0
            _need(header.size == C.sizeof(NativeEvent) and header.version == 1
                  and header.reserved == 0 and 1 <= header.kind <= 11
                  and header.thread_role in (1, 2, 3), 'attribution_event_layout')
            _need((header.kind == 1 and header.thread_role == 1 and header.epoch > 0)
                  or (header.kind in (2, 3, 4, 5, 10) and header.thread_role == 2)
                  or (header.kind in (6, 7, 8, 9, 11) and header.thread_role in (2, 3)),
                  'attribution_thread_role')
            _need(header.kind not in (7, 8, 9) or header.remaining_ms > 0, 'attribution_original_deadline')
            started = self._clock()
            seconds = min(self._seconds, header.remaining_ms / 1000) if header.remaining_ms else self._seconds
            deadline = started + seconds
            _need(0 < header.json_bytes <= 2 * 1024 * 1024 and bool(header.json_utf8), 'attribution_body_size')
            raw = C.string_at(header.json_utf8, header.json_bytes)
            body = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_invalid_constant)
            _need(type(body) is dict, 'attribution_body_type')
            _validate_tree(body)
            _need(self._clock() < deadline, 'attribution_deadline')
            event = AttributionEvent(header.kind, header.thread_role, header.epoch, body, raw,
                                     hashlib.sha256(raw).hexdigest(), deadline)
            self._borrow.active = True
            quantity = self._handler(event)
            _need(self._clock() < deadline, 'attribution_deadline')
            if header.kind == 4:
                requested = body.get('requested_quantity')
                _need(type(requested) in (int, float) and math.isfinite(requested)
                      and requested > 0 and requested == int(requested), 'attribution_requested_quantity')
                _need(type(quantity) is int and 0 <= quantity <= requested, 'attribution_authorized_quantity')
                _need(body.get('side') in ('buy', 'sell') and
                      (body['side'] == 'sell' or quantity % 100 == 0), 'attribution_authorized_lot')
                reply.decision, reply.authorized_quantity = (0, quantity) if quantity else (1, 0)
            else:
                _need(quantity is None, 'attribution_notification_reply')
                reply.decision = 0
            return 0
        except BaseException as error:
            self._failure = error
            return -1  # C ABI不抛异常；原Native保留UUID/责任并关闭后继写入。
        finally:
            self._borrow.active = previous_borrow


class AttributionCoordinator:
    """同步连接原Native事件与唯一ASA；不连接Source、不持有第二份金融账。

    fee_bound(symbol,side,quantity,price)由部署者提供已声明的整组费用上界；
    settlement_day(ISO交易日)由已核交易日历提供，不能用自然日加一天。
    ctx在完整目标setter前调用prepare_intent，回调只消费这些已备值及ASA快照。
    所有原Source事实先保存ASA inbox，再应用；合法O先于D的终态保留待续。
    """

    def __init__(self, allocation, *, control_id, account_scope_sha256, strategy_ids,
                 fee_bound, settlement_day, clock=monotonic, utcnow=lambda: datetime.now(timezone.utc),
                 trading_day_qualified=None, account_observation_day=None):
        _need(type(control_id) is str and str(UUID(control_id)) == control_id, 'attribution_control')
        _need(type(account_scope_sha256) is str and len(account_scope_sha256) == 64
              and all(c in '0123456789abcdef' for c in account_scope_sha256), 'attribution_account_scope')
        _need(type(strategy_ids) is tuple and len(strategy_ids) > 1
              and len(set(strategy_ids)) == len(strategy_ids), 'attribution_strategies')
        _need(callable(fee_bound) and callable(settlement_day), 'attribution_fact_providers')
        _need(account_observation_day is None or callable(account_observation_day), 'attribution_fact_providers')
        self.allocation, self.strategy_ids = allocation, strategy_ids
        self._control, self._scope = control_id, account_scope_sha256
        self._fee_bound, self._settlement = fee_bound, settlement_day
        self._clock, self._utcnow = clock, utcnow
        self._lock, self._metadata, self._plan = RLock(), {}, None
        self._seen_strategies, self._merged, self._armed = set(), {}, False
        self._account_fingerprint, self._last_mutating_fill_ms = None, 0
        self._inbox_cursor = 0  # 原inbox分页水位，仅观察调度；unknown原件不阻塞后页。
        self._order_sources = {}  # 当前原O投影，原始每次证明保存在唯一ASA inbox。
        self._trading_day_qualified = trading_day_qualified
        self._account_observation_day = account_observation_day  # 官方日历按实际P/A接收上海日选择最近已开市日。
        self._authorizations = {}  # 仅保存原Local预览到紧接group的同次准入值；没有金融占款/命令状态。

    def _identity(self, *parts):
        return str(uuid5(NAMESPACE_URL, json.dumps((self._scope, *parts), sort_keys=True, separators=(',', ':'))))

    def _enter(self, deadline):
        _need(self._lock.acquire(timeout=max(0, deadline-self._clock())), 'attribution_deadline')
        if self._clock() >= deadline:
            self._lock.release()
            raise AttributionError('attribution_deadline')

    def view(self, strategy_id, *, deadline):
        return self.allocation.view(strategy_id, deadline=deadline)

    def strategy_observation(self, strategy_id, *, deadline):
        return self.allocation.strategy_observation(strategy_id, deadline=deadline)

    def observe_context(self, context, *, deadline, max_age_seconds):
        """仅Managed借用内读取原完整P/A，核同D及O冻结后更新ASA/T+1。

        返回None为已核同；明确等待原因只影响本轮策略决策。原账户事实及策略
        归属继续分别保存，不能把旧P/新A或未覆盖实际D的观察用于释放买入责任。
        """
        from .account_allocation import AccountSnapshot, AllocationError, OwnedPosition, SellReservation
        self._enter(deadline)
        try:
            self.replay_pending(deadline=deadline)
            broker = context.broker_observation()
            if not broker.positions_known or not broker.account_known:
                return 'account_observation_unknown'
            now_ms = self._utcnow().timestamp()*1000
            received = (broker.position_received_ms, broker.account_received_ms)
            if any(t is None or not t <= now_ms < t+max_age_seconds*1000 for t in received):
                return 'account_observation_stale'
            if min(received) < self._last_mutating_fill_ms:
                return 'account_observation_before_actual_fill'
            received_day = datetime.fromtimestamp(min(received)/1000, timezone.utc).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
            day = received_day if self._account_observation_day is None else self._account_observation_day(received_day)
            if day is None:
                return 'account_observation_day_unqualified'
            _need(type(day) is str and date.fromisoformat(day).isoformat() == day and day <= received_day,
                  'attribution_account_observation_day')
            if self._trading_day_qualified is not None and not self._trading_day_qualified(day):
                return 'account_trading_day_unqualified'
            account_body = asdict(broker)
            account_body.pop('published_epoch_ms')  # 展示副本发布不生成一份新的券商P/A。
            fingerprint = hashlib.sha256(json.dumps((self._control, day, account_body, self._order_sources), sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            if fingerprint == self._account_fingerprint:
                return None
            positions = []
            for row in broker.positions:
                _need(row.is_long, 'attribution_short_position')
                positions.append(OwnedPosition(row.symbol, self._quantity(row.quantity), self._quantity(row.sellable)))
            reservations = []
            for tag, source in self._order_sources.items():
                if source['side'] != 'sell' or source['terminal'] or not source['remaining_quantity']:
                    continue
                command = self.allocation.lookup_prepared(tag, deadline=deadline)
                if command is not None:
                    reservations.append(SellReservation(command.command_id,
                        self._quantity(source['remaining_quantity']), source['source_sha256']))
            prior = self.allocation.strategy_observation(self.strategy_ids[0], deadline=deadline)
            available = self._source_decimal(repr(broker.available), '.01')
            snapshot = AccountSnapshot(prior.account_revision+1, day, available, tuple(positions), fingerprint, tuple(reservations))
            try:
                self.allocation.observe_account(snapshot, deadline=deadline)
            except AllocationError as error:
                if error.reason in ('account_position_mismatch', 'account_sellable_mismatch', 'account_freeze_unbound'):
                    return error.reason
                raise
            self._account_fingerprint = fingerprint
            return None
        finally:
            self._lock.release()

    def prepare_intent(self, strategy_id, epoch, *, source_sha256, known_at,
                       buy_price_caps, common_prices, deadline):
        """原ctx setter前保存本轮不可变元数据；同策略只保留最新借用epoch。"""
        _need(strategy_id in self.strategy_ids and type(epoch) is int and epoch > 0, 'attribution_intent')
        _need(type(buy_price_caps) is dict and type(common_prices) is tuple, 'attribution_intent')
        self._enter(deadline)
        try:
            self._metadata[strategy_id] = (epoch, source_sha256, known_at, dict(buy_price_caps), common_prices)
        finally:
            self._lock.release()

    @staticmethod
    def _quantity(value):
        _need(type(value) in (int, float) and math.isfinite(value) and value >= 0
              and value == int(value), 'attribution_quantity')
        return int(value)

    @staticmethod
    def _price(value):
        _need(type(value) is str, 'attribution_price')
        result = Decimal(value)
        _need(result.is_finite() and result > 0, 'attribution_price')
        return result

    @staticmethod
    def _source_decimal(value, quantum):
        """只收敛原有限double尾差，原正文与SHA由inbox保留；明显离档值待核。"""
        _need(type(value) is str and 0 < len(value) <= 128, 'source_cash_precision_unproven')
        number = Decimal(value)
        _need(number.is_finite(), 'source_cash_precision_unproven')
        binary = float(number)
        _need(math.isfinite(binary), 'source_cash_precision_unproven')
        epsilon = 4 * sys.float_info.epsilon * abs(binary)
        step = Decimal(quantum)
        _need(epsilon < float(step)/4, 'source_cash_precision_unproven')
        with localcontext() as context:
            context.prec = 64
            normalized = number.quantize(step, rounding=ROUND_HALF_UP)
            _need(abs(number-normalized) <= Decimal.from_float(epsilon), 'source_cash_precision_unproven')
        return normalized

    def _group(self, body):
        _need(type(body.get('instance_id')) is str and body['instance_id'], 'attribution_group')
        generation, group = body.get('native_generation'), body.get('group_id')
        _need(type(generation) is int and generation > 0 and type(group) is int and group > 0, 'attribution_group')
        return f"{self._control}:{body['instance_id']}:{generation}:{group}"

    @staticmethod
    def _wt_identity(body):
        # 原mapper为owned提供稳定原user_tag；缺身份保留原事实，禁止靠revision猜。
        tag = body.get('user_tag')
        _need(type(tag) is str and bool(tag), 'attribution_wt_identity_missing')
        return tag

    def _current_plan(self, deadline):
        intents = self.allocation.current_targets(deadline=deadline)
        observations = {sid: self.allocation.view(sid, deadline=deadline) for sid in self.strategy_ids}
        prices = {}
        for metadata in self._metadata.values():
            for price in metadata[4]:
                previous = prices.get(price.symbol)
                if previous is None or price.known_at > previous.known_at:
                    prices[price.symbol] = price
        # 计划本身的写水位不作为重建原因；真实意图、库存、未结组或共同价变化才重评。
        fingerprint = repr((intents, tuple((sid, v.positions, v.pending_groups, v.ledger_cash_cny,
                            v.reserved_cash_cny, v.unknown_fee_count) for sid, v in observations.items()),
                            tuple(sorted(prices.items()))))
        if self._plan is None or self._plan[0] != fingerprint:
            plan_id = self._identity(self._control, 'plan', fingerprint)
            result = self.allocation.plan(plan_id, tuple(prices.values()), deadline=deadline)
            self._plan = fingerprint, result.plan_id
        return self._plan[1]

    def _verify_merged(self, deadline):
        # 初始恢复可能先回放原WT执行目标；两个ctx均给出本代完整意图前保持暂缓。
        self._armed = False
        if self._seen_strategies != set(self.strategy_ids):
            return
        intents = self.allocation.current_targets(deadline=deadline)
        expected = {}
        for sid in self.strategy_ids:
            intent = intents[sid]
            _need(intent is not None, 'attribution_intent_missing')
            for target in intent.targets:
                expected[target.symbol] = expected.get(target.symbol, 0) + target.quantity
        _need({s: q for s, q in expected.items() if q} == {s: q for s, q in self._merged.items() if q},
              'attribution_merged_targets_conflict')
        self._armed = True

    def _command(self, body, deadline):
        command = self.allocation.lookup_prepared(self._wt_identity(body), deadline=deadline)
        _need(command is not None, 'attribution_command_unmapped')
        provided = body.get('command_id')
        _need(provided is None or provided == command.command_id, 'attribution_command_conflict')
        return command

    def _source(self, event, event_id):
        from .account_allocation import FillFact, TerminalFact
        body, deadline = event.body, event.deadline
        if event.kind == 8:
            command = self._command(body, deadline)
            before_quantity = sum(p.quantity for sid in self.strategy_ids
                for p in self.allocation.view(sid, deadline=deadline).positions if p.symbol == body['symbol'])
            day = datetime.strptime(str(body['trading_date']), '%Y%m%d').date().isoformat()
            tick = body['trade_time']
            _need(type(tick) is int and 0 <= tick < 240000000, 'attribution_trade_time')
            executed = datetime.strptime(str(body['trading_date']), '%Y%m%d').replace(
                hour=tick//10000000, minute=tick//100000 % 100, second=tick//1000 % 100,
                microsecond=tick % 1000*1000, tzinfo=ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc).isoformat()
            settlement = self._settlement(day) if body['side'] == 'buy' else day
            amount = self._source_decimal(body['amount_cny'], '.01')
            fee = None if body.get('fee_cny') is None else self._source_decimal(body['fee_cny'], '.01')
            self.allocation.apply_fill(FillFact(body['trade_id'], command.command_id,
                self._quantity(body['quantity']), self._source_decimal(body['price_cny'], '.001'), amount, fee, day, settlement,
                body['source_sha256'], body['symbol'], body['side'], executed_at=executed), deadline=deadline)
            after_quantity = sum(p.quantity for sid in self.strategy_ids
                for p in self.allocation.view(sid, deadline=deadline).positions if p.symbol == body['symbol'])
            if after_quantity != before_quantity:
                self._last_mutating_fill_ms = self._utcnow().timestamp()*1000
        elif event.kind == 9:
            command = self._command(body, deadline)
            tag = self._wt_identity(body)
            child = self.allocation.lookup_wt_child(tag, deadline=deadline)
            # 只投影尚有责任的自有SELL冻结；历史/外国O原件完整保留在inbox。
            # 持久原终态排除乱序旧active O，内存无需另存无界终态墓碑。
            resolved = child is not None and child.terminal_state in ('filled', 'cancelled', 'rejected', 'not_called')
            if body['terminal'] or resolved:
                self._order_sources.pop(tag, None)
            elif body['side'] == 'sell' and body['remaining_quantity']:
                previous = self._order_sources.get(tag)
                if previous is None or body['filled_quantity'] >= previous['filled_quantity']:
                    self._order_sources[tag] = dict(body)
            if body['terminal']:
                state = {48: 'filled', 50: 'cancelled', 52: 'rejected', 53: 'cancelled'}.get(body['order_state'])
                _need(state is not None, 'attribution_order_state')
                self.allocation.apply_terminal(TerminalFact(event_id, command.group_id, command.command_id,
                    state, body['source_sha256'], self._quantity(body['filled_quantity'])), deadline=deadline)
        else:
            _need(event.kind == 11, 'attribution_source_kind')
            if body['dispatch_not_entered']:
                _need(body['phase'] in (0, 3) and body['filled_quantity'] == 0, 'attribution_not_called_proof')
                command = self.allocation.lookup_prepared(self._wt_identity(body), deadline=deadline)
                proof = body.get('source_sha256') or event.sha256  # 明确本地证明，不伪造Source结果。
                if command is None:
                    self.allocation.record_child_not_called(self._group(body), self._wt_identity(body), proof, deadline=deadline)
                else:
                    _need(body.get('command_id') in (None, command.command_id), 'attribution_command_conflict')
                    self.allocation.apply_terminal(TerminalFact(event_id, command.group_id, command.command_id,
                        'not_called', proof, 0), deadline=deadline)
            elif body['phase'] == 5:
                command = self._command(body, deadline)
                self.allocation.apply_terminal(TerminalFact(event_id, command.group_id, command.command_id,
                    'unknown', body.get('source_sha256') or event.sha256), deadline=deadline)
            # SDKReturned/Queued/Dispatching沿原Host责任；此通知不授券商终态。

    def _receive_source(self, event):
        event_id = self._identity('source', event.kind, event.sha256)
        inbox = self.allocation.receive_event(event_id, str(event.kind), event.raw,
                    event.body.get('source_sha256'), deadline=event.deadline)
        if inbox.applied:
            return
        try:
            self._source(event, event_id)
        except Exception as error:
            reason = getattr(error, 'reason', str(error) if type(error) is AttributionError else type(error).__name__)
            self.allocation.mark_event_failed(event_id, reason, deadline=event.deadline)
            # O先于D及全账户无归属源行是保留事实等待核查；不能解释为未成交或补发。
            if reason not in ('terminal_missing_fills', 'attribution_command_unmapped', 'attribution_wt_identity_missing'):
                raise
        else:
            self.allocation.mark_event_applied(event_id, deadline=event.deadline)

    def replay_pending(self, *, deadline, limit=100):
        """原owner用本轮绝对D续核已接收事实；不联网、不重发原命令。

        limit是一次读取分页量，未处理原件继续留在ASA；它不限制目标/交易数量。
        后续原D或新owner机会可继续调用。经济幂等及全部proof仍由ASA验证。
        """
        self._enter(deadline)
        try:
            page = self.allocation.pending_events(limit=limit, after_sequence=self._inbox_cursor, deadline=deadline)
            if not page and self._inbox_cursor:
                self._inbox_cursor = 0
                page = self.allocation.pending_events(limit=limit, after_sequence=0, deadline=deadline)
            for inbox in page:
                body = json.loads(inbox.raw_json, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
                if inbox.kind == '7':
                    # 收件恢复只核已持久的关联/原NoCall，永不补发prepared或授新许可。
                    tag = self._wt_identity(body)
                    command = self.allocation.lookup_prepared(tag, deadline=deadline)
                    child = self.allocation.lookup_wt_child(tag, deadline=deadline)
                    if command is not None:
                        _need(command.command_id == body['command_id'] and command.command_sha256 == body['command_sha256']
                              and command.quantity == self._quantity(body['quantity'])
                              and command.limit_price_cny == self._price(body['limit_price_cny']),
                              'attribution_command_conflict')
                        self.allocation.mark_event_applied(inbox.event_id, deadline=deadline)
                    elif child is not None and child.not_called:
                        self.allocation.mark_event_applied(inbox.event_id, deadline=deadline)
                    else:
                        self.allocation.mark_event_failed(inbox.event_id, 'original_prepared_requires_query', deadline=deadline)
                    self._inbox_cursor = inbox.sequence
                    continue
                event = AttributionEvent(int(inbox.kind), 2, 0, body, inbox.raw_json, inbox.payload_sha256, deadline)
                self._receive_source(event)
                self._inbox_cursor = inbox.sequence
        finally:
            self._lock.release()

    def __call__(self, event):
        from .account_allocation import GroupBinding, PreparedCommand, Target, TargetIntent, WTChild
        self._enter(event.deadline)
        try:
            body, deadline = event.body, event.deadline
            if event.kind == 1:
                sid = body['strategy_id'];metadata = self._metadata.get(sid)
                _need(sid in self.strategy_ids and metadata is not None and metadata[0] == event.epoch,
                      'attribution_intent_metadata')
                targets = tuple(Target(row['symbol'], self._quantity(row['quantity']), metadata[3].get(row['symbol']))
                                for row in body['targets'])
                intent_id = self._identity(self._control, sid, event.epoch, event.sha256)
                previous = self.allocation.current_targets(deadline=deadline)[sid]
                revision = (previous.revision if previous is not None and previous.intent_id == intent_id
                            else self.allocation.view(sid, deadline=deadline).revision+1)
                self.allocation.record_targets(TargetIntent(intent_id, sid, revision, targets,
                    metadata[1], metadata[2]), deadline=deadline)
                if previous is None or previous.intent_id != intent_id:
                    self._armed = False  # 首setter前的新意图须等原WT合并commit，旧已绑定组仍继续原责任。
                self._seen_strategies.add(sid)
            elif event.kind in (2, 3):
                if event.kind == 2:
                    rows = body['targets']
                    _need(type(rows) is list and len({row['symbol'] for row in rows}) == len(rows), 'attribution_targets')
                    self._merged = {row['symbol']: self._quantity(row['quantity']) for row in rows}
                else:
                    symbol, delta = body['symbol'], body['quantity_delta']
                    _need(type(delta) in (int, float) and math.isfinite(delta)
                          and delta == int(delta), 'attribution_quantity')
                    self._merged[symbol] = self._quantity(self._merged.get(symbol, 0)+delta)
                self._verify_merged(deadline)
                if self._armed:
                    self._current_plan(deadline)
            elif event.kind == 4:
                if not self._armed:
                    return 0
                quantity, price = self._quantity(body['requested_quantity']), self._price(body['limit_price_cny'])
                fee = self._fee_bound(body['symbol'], body['side'], quantity, price)
                authorization = self.allocation.preview_group(self._current_plan(deadline), body['symbol'], body['side'],
                    quantity, price, fee, deadline=deadline)
                key = body['instance_id'], body['symbol'], body['side']
                self._authorizations.pop(key, None)
                if authorization.quantity:
                    self._authorizations[key] = authorization
                return authorization.quantity
            elif event.kind == 5:
                quantity, price = self._quantity(body['quantity']), self._price(body['limit_price_cny'])
                key = body['instance_id'], body['symbol'], body['side']
                authorization = self._authorizations.pop(key, None)
                _need(authorization is not None and authorization.quantity == quantity
                      and authorization.limit_price_cny == price, 'attribution_group_without_authorization')
                # ctx可在authorize后提交新意图；原WT尚在执行旧commit，此组严格沿已授权原plan。
                self.allocation.bind_group(authorization.plan_id, GroupBinding(self._group(body), body['symbol'],
                    body['side'], quantity, price, authorization.fee_bound_cny), deadline=deadline)
            elif event.kind == 6:
                self.allocation.record_wt_child(WTChild(self._group(body), self._wt_identity(body),
                    self._quantity(body['quantity']), self._price(body['limit_price_cny']), event.sha256), deadline=deadline)
            elif event.kind == 7:
                event_id = self._identity('prepared', event.sha256)
                received = self.allocation.receive_event(event_id, '7', event.raw, None, deadline=deadline)
                _need(not received.applied, 'attribution_original_command_requires_query')
                try:
                    permit = self.allocation.bind_prepared(PreparedCommand(self._group(body), self._wt_identity(body),
                        body['command_id'], body['command_sha256'], self._quantity(body['quantity']),
                        self._price(body['limit_price_cny'])), deadline=deadline)
                    _need(permit.first_binding, 'attribution_original_command_requires_query')
                except Exception as error:
                    reason = getattr(error, 'reason', type(error).__name__)
                    self.allocation.mark_event_failed(event_id, reason, deadline=deadline)
                    raise
                self.allocation.mark_event_applied(event_id, deadline=deadline)
            elif event.kind == 10:
                self.allocation.record_group_end(self._group(body), body['accepted_children'], event.sha256, deadline=deadline)
            else:
                self._receive_source(event)
            return None
        finally:
            self._lock.release()


def create_runtime_attribution(native, configuration, control_directory, control_id, *, deadline):
    """固定共享账户材料装配入口；默认单策略调用方不进入此可选路径。"""
    from .shared_account_configuration import create_runtime_attribution as create
    return create(native, configuration, control_directory, control_id, deadline=deadline)
