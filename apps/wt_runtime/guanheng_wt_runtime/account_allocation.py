"""ASA归属事实：借用原金融租约，记录原意图/命令/实际成交，绝不提交金融命令。"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import RLock
from time import monotonic
from uuid import UUID


class AllocationError(ValueError):
    """固定原因；原Source/订单事实仍由调用方持有，失败不表示未执行。"""
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class _RecordedRejection(AllocationError):
    """仅诊断留证事务可提交后抛出；金融事实修改仍统一回滚。"""


@dataclass(frozen=True)
class BookIdentity:
    account_scope_sha256: str  # 账户/环境/币种的原绑定摘要，不保存账号或凭据。
    financial_book_id: str  # 原金融账本稳定UUID，正常重启不变。
    baseline_sha256: str  # 旧金融基准原件SHA，新策略不能重建该基准。


@dataclass(frozen=True)
class OwnedPosition:
    symbol: str  # WT证券，如SSE.ETF.510500，当前模块只管理沪深ETF。
    quantity: int  # 实际归属整数份额；不是理论目标。
    sellable: int  # 已有来源资格的可卖整数份额，不超过quantity。


@dataclass(frozen=True)
class OpeningCycle:
    symbol: str  # 该策略自有证券，空仓周期在观察投影中为None。
    cycle_id: str | None  # 原owner周期身份或真实首次增量成交稳定派生身份。
    opened_at: str | None  # 原真实成交/共同转移价可知时刻；缺证明保持None。
    source_sha256: str | None  # 原周期事实的来源证明，缺证明保持None。
    status: str  # held/initial_inventory/unknown；不从P或当前时间推开仓。


@dataclass(frozen=True)
class SellReservation:
    command_id: str  # 同完整P/O观察中已证明冻结的原prepared SELL UUID。
    quantity: int  # 该原单尚未成交且已冻结的整数份额。
    source_sha256: str  # 同次原订单观察冻结依据SHA，不用预提交意图代替。


@dataclass(frozen=True)
class StrategySeed:
    strategy_id: str  # 同金融账本内唯一策略身份。
    version: str  # 本次策略经济模型版本，参与初始化身份核验。
    cash_cny: Decimal  # 原owner提供的初始现金，CNY精确到分。
    positions: tuple[OwnedPosition, ...]  # 显式分配的原库存；新策略为空。
    priority: int  # 同向需求FIFO优先级，旧策略先于新策略。
    universe: tuple[str, ...]  # 原配置明确的完整证券池，空仓证券也必须列出。
    opening_cycles: tuple[OpeningCycle, ...] = ()  # 旧owner明确给出的原周期；缺失保持unknown。


@dataclass(frozen=True)
class AccountSnapshot:
    revision: int  # 原完整P/A观察的单调序号；同号不同正文拒绝。
    trading_day: str  # 原来源上海交易日，ISO日期；不是本机刷新日期。
    available_cny: Decimal  # 账户原可用资金上限，冻结项不重复扣减。
    positions: tuple[OwnedPosition, ...]  # 原完整账户实际数量/可卖份额。
    source_sha256: str  # 原账户事实摘要，绑定本轮来源。
    sell_reservations: tuple[SellReservation, ...] = ()  # 同一完整观察证明的原订单冻结归属。


@dataclass(frozen=True)
class Target:
    symbol: str  # 该策略管理的WT证券。
    quantity: int  # 整数目标份额，当前ETF外部目标为100份倍数。
    buy_price_cap_cny: Decimal | None = None  # 该策略显式买价上限；None沿原策略无额外限价。


@dataclass(frozen=True)
class TargetIntent:
    intent_id: str  # 调用者原意图UUID，重复同正文幂等。
    strategy_id: str  # 已初始化策略，不接受未知策略。
    revision: int  # 该策略递增目标序号。
    targets: tuple[Target, ...]  # 本轮完整目标集合，不能省略已有非零库存。
    source_sha256: str  # 原策略输入/信号依据SHA。
    known_at: str  # 意图可知UTC时刻，带时区ISO。


@dataclass(frozen=True)
class CommonPrice:
    symbol: str  # 内部配对证券。
    price_cny: Decimal  # 双方共同可知的每份价格，精度0.001元。
    known_at: str  # 原价格可知时刻，带时区ISO。
    source_sha256: str  # 原价格事实SHA。
    participants: tuple[str, ...]  # 明确接受同一价格的策略id。
    qualified: bool  # 调用者核同价格资格；False不能转移。


@dataclass(frozen=True)
class GroupBinding:
    group_id: str  # 原Runtime/代际/提交组的稳定完整标识，不在此生成。
    symbol: str  # 原提交证券。
    side: str  # buy或sell，原方向。
    quantity: int  # 本组总申报上限；BUY为100份倍数，SELL保留原WT合法碎份。
    limit_price_cny: Decimal  # 原外部限价，买入本金按此上界预留。
    fee_bound_cny: Decimal  # 整组所有子单/成交费用的明确上界。


@dataclass(frozen=True)
class PreparedCommand:
    group_id: str  # 已绑定原group，关联不能在SDK返回后补造。
    wt_order_id: str  # 原WT entrust/local/user-tag组合标识，原样保存。
    command_id: str  # 原Host prepared插入命令UUID，模块不另造命令。
    command_sha256: str  # 原prepared命令正文SHA。
    quantity: int  # 该原插入child实际申报量，组内累计不越界。
    limit_price_cny: Decimal  # 原child限价，买入不得高于原组预留价格。


@dataclass(frozen=True)
class WTChildDisposition:
    group_id: str  # 原WTchild所属完整提交组，跨Runtime重启保留。
    wt_order_id: str  # 原WT稳定标识，不生成新命令身份。
    command_id: str | None  # 已成功prepared关联的原UUID；None表示未关联。
    not_called: bool  # 未prepared child已有原明确未调用证明；False继续未知/在途。
    terminal_state: str | None  # 已关联原command的持久终态；None/unknown仍有原责任。


@dataclass(frozen=True)
class WTChild:
    group_id: str  # 原Runtime/group完整身份。
    wt_order_id: str  # 原entrust/user_tag完整稳定组合，先于SDK prepared存在。
    quantity: int  # 原WT已形成child的实际整数数量。
    limit_price_cny: Decimal  # 与原prepared正文同一canonical限价。
    source_sha256: str  # 原WT child事件依据，不冒充SDK回执。


@dataclass(frozen=True)
class InboxEvent:
    event_id: str  # 原事件稳定身份；不是新金融命令UUID。
    kind: str  # 原Source/Native事实类型。
    raw_json: bytes  # 原完整UTF8 JSON字节，保留原SHA，不存另一套委托。
    payload_sha256: str  # 上述原字节SHA。
    source_sha256: str | None  # 原Source/derived证明SHA；本地NotSent无Source回执时明确None。
    applied: bool  # 仅表示归属投影完成，不授金融终态。
    reason: str | None  # 尚未投影的固定原因；原始事实始终保留。
    sequence: int  # 原收件顺序，分页水位不改变事件身份。


@dataclass(frozen=True)
class DispatchPermit:
    group_id: str  # 已持久绑定的原组。
    wt_order_id: str  # 已持久关联的原WT标识。
    command_id: str  # 只授此原命令进入原提交链。
    command_sha256: str  # 正文必须与持久原件相同。
    first_binding: bool  # 仅首次持久绑定为True；重复须沿原ID核查，不能据此重新提交。


@dataclass(frozen=True)
class GroupAuthorization:
    plan_id: str  # 当前原计划UUID。
    symbol: str  # 原WT请求证券。
    side: str  # 原WT请求方向。
    requested_quantity: int  # 原WT请求的整数份额，尚未裁剪。
    quantity: int  # 当前可分配份额；BUY向下到100，零表示等待输入变化。
    limit_price_cny: Decimal  # 本次实际canonical原限价，不能改用未来报价。
    fee_bound_cny: Decimal  # 本次整组费用上界。
    revision: int  # 预览账水位；bind_group仍以事务内当前事实重核。


@dataclass(frozen=True)
class FillFact:
    fill_id: str  # 原成交完整稳定身份，含账户scope/日期/原成交id语义。
    command_id: str  # 已prepared绑定的原插入命令UUID。
    quantity: int  # 本条增量实际成交份额，不能传累计成交量。
    price_cny: Decimal  # 原实际每份成交价。
    amount_cny: Decimal  # 原成交金额，分精度，核同价格乘实际份额。
    fee_cny: Decimal | None  # 原实际/显式模型费用；None保持未知。
    trading_day: str  # 原实际成交的上海交易日。
    settlement_day: str  # 来源日历明确的可卖交易日；买入至少晚于成交日。
    source_sha256: str  # 原实际成交来源SHA，重复身份不同正文拒绝。
    symbol: str  # 原成交证券，必须与绑定child的组一致。
    side: str  # 原成交方向buy/sell，不能仅凭传入command_id推定。
    executed_at: str | None = None  # 原真实trade_time含时区；缺失时周期时钟保持未知。


@dataclass(frozen=True)
class FeeFact:
    event_id: str  # 原后继费用事实UUID，重复同正文幂等。
    fill_id: str  # 费用所属原成交，不能跨成交挪用。
    fee_cny: Decimal  # 已确认非负费用，零必须显式提供。
    source_sha256: str  # 该费用事实原来源SHA。


@dataclass(frozen=True)
class TerminalFact:
    event_id: str  # 原确定终态或unknown观察UUID。
    group_id: str  # 原提交组身份。
    command_id: str | None  # child终态给原UUID；组收口为None。
    state: str  # filled/cancelled/rejected/not_called/unknown/group_closed。
    source_sha256: str  # 原owner给出的终态依据SHA，不以缺回报代替终态。
    filled_quantity: int | None = None  # child确定终态的原累计成交量；缺D时保留责任等待补齐。


@dataclass(frozen=True)
class PlanOrder:
    symbol: str  # 原WT应处理的证券。
    side: str  # 净外部方向，buy或sell。
    quantity: int  # 净残余份额，真实执行及百份处理继续归原WT。


@dataclass(frozen=True)
class PlanView:
    plan_id: str  # 调用者原计划UUID。
    orders: tuple[PlanOrder, ...]  # 份额归属后的净外部需求，不是委托。
    internal_transfers: tuple[dict, ...]  # 明示内部转移事实，绝不标为柜台成交。
    blocked_symbols: tuple[str, ...] = ()  # 原未结group仅阻塞其证券，其他证券继续计划。
    blocked_reasons: dict[str, str] = field(default_factory=dict)  # 分证券等待原因；保留原目标供后继重评。


@dataclass(frozen=True)
class PositionView:
    symbol: str  # 本策略的证券，不是整账户同码总份额。
    quantity: int  # 该策略真实已归属整数份额。
    sellable: int  # 原可卖减本模块已占款份额。
    reserved_sell: int  # 未终态原组占用的该策略可卖份额。


@dataclass(frozen=True)
class StrategyView:
    strategy_id: str  # 固定策略身份。
    version: str  # 原初始化经济版本。
    cash_cny: Decimal | None  # 费用全已知时的真实有符号余额；未知费用时为None。
    ledger_cash_cny: Decimal  # 已发生本金/已知费用后的有符号余额；实际费用可使其为负。
    reserved_cash_cny: Decimal  # 未结限价本金和未知费用的保守占款。
    spendable_cash_cny: Decimal  # max(0,本策略余额减占款)，仍受账户available总上限。
    unknown_fee_count: int  # 尚未取得费用事实的原fill数量。
    positions: tuple[PositionView, ...]  # 自有份额投影。
    pending_groups: tuple[str, ...]  # 原未知/未结group原标识，不能改成新ID。
    revision: int  # 本模块持久事务水位，不延长来源资格。


@dataclass(frozen=True)
class OwnedFillObservation:
    fill_id: str  # 原实际成交身份；公开UI另作不可逆摘要，不暴露原订单号。
    symbol: str  # 原实际成交标准WT证券；只列本策略获分配的部分。
    side: str  # 原成交buy/sell；内部转移不进入此集合。
    quantity: int  # 本策略获分配的实际份额，非账户总成交量。
    price_cny: Decimal  # 原实际成交每份价格，元，保持0.001元精度。
    amount_cny: Decimal  # 原已记账分配金额，元，沿原分配的分舍入。
    fee_cny: Decimal | None  # 原已确认分配费用；未知为None，零须原明确给出。
    trading_day: str  # 原成交上海交易日，ISO日期。
    executed_at: str | None  # 原实际成交时刻，带时区；缺少保持None。
    source_sha256: str  # 原实际成交来源SHA，不改用本次读取时间。


@dataclass(frozen=True)
class StrategyObservation:
    strategy: StrategyView  # 本策略真实归属份额/资金，非账户P复制。
    account_revision: int  # 原完整账户观察的持久水位。
    account_source_sha256: str  # 原账户观察依据，用于来源核同。
    trading_day: str  # 原账户上海交易日。
    opening_cycles: dict[str, OpeningCycle | None]  # 按标准证券区分原实际开仓周期/未知/空仓。
    book_scope_sha256: str | None = None  # 原ASA账本身份摘要；旧DTO缺失时按运行代隔离展示历史。
    observed_at: str | None = field(default=None, compare=False)  # 原owner读取UTC时刻；不参与经济事实相等性，不授估值clock。
    targets: dict[str, int] | None = None  # 原已提交完整目标份额；None表示尚无意图，区别全零。
    fills: tuple[OwnedFillObservation, ...] | None = None  # 仅原实际D已记账分配；旧DTO未知为None，完整空为()。
    fills_truncated: bool = False  # 仅发布最近2000条展示投影；原账本全部原件保留。



def _need(ok, reason):
    if not ok:
        raise AllocationError(reason)


def _text(value):
    _need(type(value) is str and 0 < len(value) <= 256 and all(ord(c) >= 32 for c in value), 'identity_invalid')
    return value


def _sha(value):
    _need(type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None, 'sha_invalid')
    return value


def _uuid(value):
    _text(value)
    try:
        _need(str(UUID(value)) == value, 'uuid_invalid')
    except ValueError:
        raise AllocationError('uuid_invalid') from None
    return value


def _quantity(value, *, positive=False, lot=False):
    _need(type(value) is int and 0 <= value <= 2**53-1 and (not positive or value > 0)
          and (not lot or value % 100 == 0), 'quantity_invalid')
    return value


def _symbol(value):
    _need(type(value) is str and re.fullmatch(r'(SSE|SZSE)\.ETF\.[0-9]{6}', value) is not None, 'symbol_invalid')
    return value


def _money(value):
    _need(type(value) is Decimal and value.is_finite() and value >= 0, 'money_invalid')
    _need(len(value.as_tuple().digits) <= 28 and -126 <= value.as_tuple().exponent <= 126
          and value.adjusted() <= 24, 'money_precision')
    numerator, denominator = value.as_integer_ratio()
    _need(numerator*100 % denominator == 0, 'money_precision')
    return numerator*100//denominator


def _price(value):
    _need(type(value) is Decimal and value.is_finite() and value > 0
          and len(value.as_tuple().digits) <= 24 and -126 <= value.as_tuple().exponent <= 126
          and value.adjusted() <= 18, 'price_invalid')
    numerator, denominator = value.as_integer_ratio()
    _need(numerator*1000 % denominator == 0, 'price_invalid')
    return str(value)


def _day(value):
    try:
        _need(type(value) is str and date.fromisoformat(value).isoformat() == value, 'date_invalid')
    except (ValueError, TypeError):
        raise AllocationError('date_invalid') from None
    return value


def _stamp(value, *, allow_future=False):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        _need(result.tzinfo is not None and (allow_future or result <= datetime.now(timezone.utc)), 'clock_invalid')
    except (ValueError, TypeError, AttributeError):
        raise AllocationError('clock_invalid') from None
    return result


def _wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False,
                      default=lambda x: str(x) if isinstance(x, Decimal) else asdict(x))


def _gross(price, quantity):
    numerator, denominator = Decimal(price).as_integer_ratio()
    # 正数精确ROUND_HALF_UP至分，避免调用方Decimal上下文精度改变本金。
    return (numerator*quantity*200+denominator)//(2*denominator)


def _cny(cents):
    sign, absolute = ('-' if cents < 0 else ''), abs(cents)
    return Decimal(f'{sign}{absolute//100}.{absolute%100:02d}')


def _split(cents, parts):
    """按实际分配份额拆分金额到分；余分按余数及原FIFO稳定分配。"""
    total = sum(q for _, q in parts)
    _need(total > 0, 'allocation_empty')
    result = [cents*q//total for _, q in parts]
    order = sorted(range(len(parts)), key=lambda i: (-(cents*parts[i][1] % total), i))
    for i in order[:cents-sum(result)]:
        result[i] += 1
    return result


class AccountAllocation:
    """单金融租约内的持久归属；owner/worker仅交不可变值，连接/锁逐调用释放。

    每个入口的deadline为调用方原monotonic绝对D；owner_check必须核原执行租约。
    返回许可只证明持久关联和占款，不表示原SDK调用、成交或交易权限。
    """
    def __init__(self, financial_root, identity: BookIdentity, *, owner_check, clock=monotonic):
        _need(type(identity) is BookIdentity and callable(owner_check), 'owner_required')
        _sha(identity.account_scope_sha256); _uuid(identity.financial_book_id); _sha(identity.baseline_sha256)
        root = Path(financial_root)
        _need(root.is_absolute() and root.is_dir(), 'financial_root_invalid')
        if os.name == 'nt':
            _need(root.drive.upper() in ('D:', 'E:'), 'financial_root_drive')
        for parent in (root, *root.parents):
            info = parent.lstat()
            _need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 1024, 'financial_root_invalid')
        self.path = root / 'account-allocation.sqlite3'
        self.identity, self.owner_check, self.clock = identity, owner_check, clock
        self._lock = RLock()

    def _check(self, deadline):
        _need(type(deadline) in (int, float) and math.isfinite(deadline), 'deadline_invalid')
        _need(self.owner_check() is None, 'owner_required')
        if self.clock() >= deadline:
            raise TimeoutError('allocation_deadline')

    @contextmanager
    def _transaction(self, deadline):
        self._check(deadline)
        if not self._lock.acquire(timeout=max(0, deadline-self.clock())):
            raise TimeoutError('allocation_deadline')
        db = None
        try:
            self._check(deadline)
            if self.path.exists():
                info = self.path.lstat()
                _need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not getattr(info, 'st_file_attributes', 0) & 1024, 'storage_invalid')
            db = sqlite3.connect(str(self.path), timeout=max(0, deadline-self.clock()), isolation_level=None)
            db.execute('PRAGMA temp_store=MEMORY')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            _need(not tables or tables == {'asa_identity', 'asa_book', 'asa_events', 'asa_inbox', 'asa_conflicts'}, 'storage_invalid')
            db.execute('CREATE TABLE IF NOT EXISTS asa_identity (id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS asa_book (id INTEGER PRIMARY KEY, revision INTEGER NOT NULL, value TEXT NOT NULL, sha256 TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS asa_events (identity TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS asa_inbox (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, raw_json BLOB NOT NULL, payload_sha256 TEXT NOT NULL, source_sha256 TEXT, applied INTEGER NOT NULL CHECK(applied IN(0,1)), reason TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS asa_conflicts (identity TEXT PRIMARY KEY, kind TEXT NOT NULL, fact_id TEXT NOT NULL, payload TEXT NOT NULL, source_sha256 TEXT NOT NULL)')
            row = db.execute('SELECT value FROM asa_identity WHERE id=1').fetchone()
            identity = _wire({'schema': 'asa-book.v2', **asdict(self.identity)})
            if row is None:
                db.execute('INSERT INTO asa_identity VALUES (1,?)', (identity,))
            else:
                _need(row[0] == identity, 'book_identity_conflict')
            rejection = None
            try:
                yield db
            except _RecordedRejection as error:
                rejection = error
            self._check(deadline)
            db.execute('COMMIT')
            # 提交后到达原D时保留已提交事实；调用方按原ID重读，不能当未执行。
            self._check(deadline)
            if rejection is not None:
                raise AllocationError(rejection.reason)
        except sqlite3.Error:
            self._check(deadline)
            raise AllocationError('storage_invalid') from None
        finally:
            try:
                if db is not None:
                    try:
                        if db.in_transaction:
                            db.rollback()
                    finally:
                        db.close()
            finally:
                self._lock.release()

    @staticmethod
    def _load(db):
        row = db.execute('SELECT revision,value,sha256 FROM asa_book WHERE id=1').fetchone()
        _need(row is not None, 'not_initialized')
        try:
            state = json.loads(row[1])
            _need(_wire(state) == row[1] and hashlib.sha256(row[1].encode('ascii')).hexdigest() == row[2], 'storage_invalid')
            _need(set(state) == {'strategies', 'unallocated_cash', 'unallocated_positions', 'account', 'plans', 'active_plan', 'groups', 'children', 'commands', 'fills'}, 'storage_invalid')
        except (ValueError, TypeError):
            raise AllocationError('storage_invalid') from None
        return row[0], state

    @staticmethod
    def _save(db, revision, state):
        raw = _wire(state)
        db.execute('UPDATE asa_book SET revision=?,value=?,sha256=? WHERE id=1',
                   (revision+1, raw, hashlib.sha256(raw.encode('ascii')).hexdigest()))

    @staticmethod
    def _event(db, identity, payload):
        raw = _wire(payload)
        old = db.execute('SELECT payload FROM asa_events WHERE identity=?', (identity,)).fetchone()
        if old:
            _need(old[0] == raw, 'event_identity_conflict')
            return False
        db.execute('INSERT INTO asa_events VALUES (?,?)', (identity, raw))
        return True

    @staticmethod
    def _inbox_row(row):
        raw = bytes(row[3])
        _need(hashlib.sha256(raw).hexdigest() == row[4], 'storage_invalid')
        return InboxEvent(row[1], row[2], raw, row[4], row[5], bool(row[6]), row[7], row[0])

    def receive_event(self, event_id, kind, raw_json, source_sha256, *, deadline):
        """持久接收原事件；失败保原正文，处理水位与原金融命令状态分开。"""
        return self._receive_event(event_id, kind, raw_json, source_sha256,
                                   deadline=deadline, broker=False, wt_order_id=None)[0]

    def receive_broker_event(self, event_id, kind, raw_json, source_sha256, wt_order_id, *, deadline):
        """在同一收件事务按原WT标识查归属并记录未关联原因。"""
        _need(kind in ('8', '9'), 'event_kind_invalid')
        if wt_order_id is not None:
            _text(wt_order_id)
        return self._receive_event(event_id, kind, raw_json, source_sha256,
                                   deadline=deadline, broker=True, wt_order_id=wt_order_id)

    def _receive_event(self, event_id, kind, raw_json, source_sha256, *, deadline, broker, wt_order_id):
        _text(event_id); _text(kind)
        if source_sha256 is not None: _sha(source_sha256)
        _need(type(raw_json) is bytes and 0 < len(raw_json) <= 2*1024*1024, 'event_bytes_invalid')
        def pairs(values):
            result = {}
            for key, value in values:
                _need(key not in result, 'event_json_invalid'); result[key] = value
            return result
        def invalid(_): raise AllocationError('event_json_invalid')
        def number(text):
            value = float(text); _need(math.isfinite(value), 'event_json_invalid'); return value
        try:
            value = json.loads(raw_json.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid, parse_float=number)
            _need(type(value) is dict, 'event_json_invalid')
        except (ValueError, UnicodeError, RecursionError):
            raise AllocationError('event_json_invalid') from None
        digest = hashlib.sha256(raw_json).hexdigest()
        with self._transaction(deadline) as db:
            row = db.execute('SELECT * FROM asa_inbox WHERE event_id=?', (event_id,)).fetchone()
            if row is None:
                db.execute('INSERT INTO asa_inbox(event_id,kind,raw_json,payload_sha256,source_sha256,applied,reason) VALUES(?,?,?,?,?,0,NULL)',
                           (event_id, kind, raw_json, digest, source_sha256))
                row = db.execute('SELECT * FROM asa_inbox WHERE event_id=?', (event_id,)).fetchone()
            else:
                _need(row[2] == kind and bytes(row[3]) == raw_json and row[4] == digest and row[5] == source_sha256, 'event_identity_conflict')
            inbox = self._inbox_row(row)
            command = None
            if broker and not inbox.applied:
                if wt_order_id is not None:
                    _, state = self._load(db)
                    command = self._prepared(state, wt_order_id)
                if command is None:
                    reason = ('attribution_wt_identity_missing' if wt_order_id is None
                              else 'attribution_command_unmapped')
                    if inbox.reason != reason:
                        db.execute('UPDATE asa_inbox SET reason=? WHERE event_id=?', (reason, event_id))
                        inbox = self._inbox_row(db.execute('SELECT * FROM asa_inbox WHERE event_id=?', (event_id,)).fetchone())
            return inbox, command

    def pending_events(self, *, limit=100, after_sequence=0, max_bytes=2*1024*1024, deadline):
        """按原收件顺序有界读取未投影事实；没有后台消费、重派或交易队列。"""
        _need(type(limit) is int and 1 <= limit <= 1000, 'event_page_invalid')
        _quantity(after_sequence); _need(type(max_bytes) is int and 1 <= max_bytes <= 2*1024*1024, 'event_page_invalid')
        with self._transaction(deadline) as db:
            result, total = [], 0
            for row in db.execute('SELECT * FROM asa_inbox WHERE applied=0 AND sequence>? ORDER BY sequence LIMIT ?', (after_sequence, limit)):
                if total+len(row[3]) > max_bytes:
                    _need(bool(result), 'event_page_budget'); break
                result.append(self._inbox_row(row)); total += len(row[3]); self._check(deadline)
            return tuple(result)

    def mark_event_applied(self, event_id, *, deadline):
        """仅标记归属投影已提交；原成交和终态仍在各自原身份中核验。"""
        _text(event_id)
        with self._transaction(deadline) as db:
            _need(db.execute('SELECT 1 FROM asa_inbox WHERE event_id=?', (event_id,)).fetchone(), 'event_unknown')
            db.execute('UPDATE asa_inbox SET applied=1,reason=NULL WHERE event_id=?', (event_id,))

    def mark_event_failed(self, event_id, reason, *, deadline):
        """保留原字节和固定失败原因，供原owner重放同事件；不建立新命令。"""
        _text(event_id); _text(reason)
        with self._transaction(deadline) as db:
            row = db.execute('SELECT applied FROM asa_inbox WHERE event_id=?', (event_id,)).fetchone()
            _need(row is not None, 'event_unknown'); _need(not row[0], 'event_already_applied')
            db.execute('UPDATE asa_inbox SET reason=? WHERE event_id=?', (reason, event_id))

    @staticmethod
    def _positions(values):
        _need(type(values) is tuple, 'positions_invalid')
        result = {}
        for p in values:
            _need(type(p) is OwnedPosition, 'positions_invalid')
            _symbol(p.symbol); _quantity(p.quantity); _quantity(p.sellable)
            _need(p.sellable <= p.quantity and p.symbol not in result, 'positions_invalid')
            result[p.symbol] = {'quantity': p.quantity, 'sellable': p.sellable, 'lots': []}
        return result

    @staticmethod
    def _cycle(cycle):
        _symbol(cycle.symbol); _need(cycle.status in ('held', 'initial_inventory', 'unknown'), 'cycle_invalid')
        if cycle.cycle_id is not None: _text(cycle.cycle_id)
        if cycle.source_sha256 is not None: _sha(cycle.source_sha256)
        if cycle.opened_at is not None:
            _stamp(cycle.opened_at)
            _need(cycle.cycle_id is not None and cycle.source_sha256 is not None, 'cycle_invalid')

    def _open_cycle(self, strategy, sid, symbol, origin, opened_at, source_sha256, *, fill_id=None):
        identity = hashlib.sha256(_wire(['asa-cycle.v1', self.identity.financial_book_id, sid, symbol, origin]).encode('ascii')).hexdigest()
        strategy['cycles'][symbol] = asdict(OpeningCycle(symbol, identity, opened_at, source_sha256,
                                                        'held' if opened_at is not None else 'unknown'))
        if fill_id is not None: strategy['cycles'][symbol]['origin_fill_id'] = fill_id

    @classmethod
    def _account(cls, value):
        _need(type(value) is AccountSnapshot, 'account_invalid')
        _quantity(value.revision, positive=True); _day(value.trading_day); _sha(value.source_sha256)
        _need(value.trading_day <= datetime.now(timezone(timedelta(hours=8))).date().isoformat(), 'account_future_day')
        _need(type(value.sell_reservations) is tuple, 'account_invalid')
        reservations = []
        for reservation in value.sell_reservations:
            _need(type(reservation) is SellReservation, 'account_invalid')
            _uuid(reservation.command_id); _quantity(reservation.quantity, positive=True); _sha(reservation.source_sha256)
            _need(not any(r['command_id'] == reservation.command_id for r in reservations), 'account_invalid')
            reservations.append(asdict(reservation))
        return {'revision': value.revision, 'day': value.trading_day, 'available': _money(value.available_cny),
                'positions': cls._positions(value.positions), 'source_sha256': value.source_sha256,
                'sell_reservations': reservations, 'adjustment': 0}

    def initialize(self, seeds, unallocated_cash_cny, account_snapshot, *, deadline):
        _need(type(seeds) is tuple and seeds, 'seeds_invalid')
        account, strategies = self._account(account_snapshot), {}
        priorities = set()
        for seed in seeds:
            _need(type(seed) is StrategySeed, 'seeds_invalid')
            _text(seed.strategy_id); _text(seed.version); _quantity(seed.priority)
            _need(type(seed.universe) is tuple and seed.universe, 'universe_invalid')
            for symbol in seed.universe: _symbol(symbol)
            _need(len(set(seed.universe)) == len(seed.universe), 'universe_invalid')
            positions = self._positions(seed.positions)
            _need(set(positions) <= set(seed.universe), 'universe_invalid')
            _need(seed.strategy_id not in strategies and seed.priority not in priorities, 'seeds_invalid')
            priorities.add(seed.priority)
            _need(type(seed.opening_cycles) is tuple, 'cycle_invalid')
            cycles = {}
            for cycle in seed.opening_cycles:
                _need(type(cycle) is OpeningCycle, 'cycle_invalid'); self._cycle(cycle)
                _need(cycle.symbol in positions and positions[cycle.symbol]['quantity'] and cycle.symbol not in cycles, 'cycle_invalid')
                cycles[cycle.symbol] = asdict(cycle)
            for symbol, position in positions.items():
                if position['quantity'] and symbol not in cycles:
                    cycles[symbol] = asdict(OpeningCycle(symbol, None, None, None, 'unknown'))
            strategies[seed.strategy_id] = {'version': seed.version, 'cash': _money(seed.cash_cny),
                'positions': positions, 'priority': seed.priority,
                'universe': list(seed.universe), 'intent': None, 'cycles': cycles}
        remainder = {}
        for symbol in set(account['positions']) | {k for s in strategies.values() for k in s['positions']}:
            actual = account['positions'].get(symbol, {'quantity': 0, 'sellable': 0})
            quantity = sum(s['positions'].get(symbol, {}).get('quantity', 0) for s in strategies.values())
            sellable = sum(s['positions'].get(symbol, {}).get('sellable', 0) for s in strategies.values())
            _need(quantity <= actual['quantity'] and sellable <= actual['sellable'], 'initial_position_mismatch')
            remainder[symbol] = {'quantity': actual['quantity']-quantity, 'sellable': actual['sellable']-sellable, 'lots': []}
        _need(not account['sell_reservations'], 'initial_freeze_unbound')
        state = {'strategies': strategies, 'unallocated_cash': _money(unallocated_cash_cny), 'unallocated_positions': remainder,
                 'account': account, 'plans': {}, 'active_plan': None, 'groups': {}, 'children': {}, 'commands': {}, 'fills': {}}
        with self._transaction(deadline) as db:
            if not self._event(db, 'initialize', state):
                return
            _need(db.execute('SELECT id FROM asa_book').fetchone() is None, 'already_initialized')
            raw = _wire(state)
            db.execute('INSERT INTO asa_book VALUES (1,1,?,?)', (raw, hashlib.sha256(raw.encode('ascii')).hexdigest()))

    @staticmethod
    def _priority(state):
        return sorted(state['strategies'], key=lambda s: (state['strategies'][s]['priority'], s))

    @staticmethod
    def _pos(strategy, symbol):
        return strategy['positions'].setdefault(symbol, {'quantity': 0, 'sellable': 0, 'lots': []})

    @staticmethod
    def _reserves(state):
        cash = {s: 0 for s in state['strategies']}
        sells = {}
        for g in state['groups'].values():
            unknown = any(state['fills'][f]['fee'] is None for f in g['fills'])
            remaining_fee = max(0, g['fee_bound']-g['fee_paid']) if not g['closed'] or unknown else 0
            for a in g['allocations']:
                rest = 0 if g['closed'] else a['quantity']-a['filled']
                if g['side'] == 'buy':
                    # 本金向上到分；完整费用上界按每个参与策略保守预留。
                    numerator, denominator = Decimal(g['price']).as_integer_ratio()
                    cash[a['strategy']] += ((numerator*100+denominator-1)//denominator)*rest
                else:
                    key = (a['strategy'], g['symbol'])
                    sells[key] = sells.get(key, 0)+rest
                cash[a['strategy']] += remaining_fee
        return cash, sells

    def observe_account(self, snapshot, *, deadline):
        account = self._account(snapshot)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            prior = state['account']
            _need(account['revision'] >= prior['revision'], 'account_stale')
            if account['revision'] == prior['revision']:
                _need(account == {**prior, 'adjustment': 0}, 'account_revision_conflict')
                return
            _need(account['day'] >= prior['day'], 'account_stale')
            frozen = {}
            for reservation in account['sell_reservations']:
                command = state['commands'].get(reservation['command_id'])
                _need(command is not None and command['terminal'] in (None, 'unknown'), 'account_freeze_unbound')
                group = state['groups'][command['group']]
                _need(group['side'] == 'sell' and not group['closed'] and reservation['quantity'] <= command['quantity']-command['filled'], 'account_freeze_unbound')
                frozen[group['symbol']] = frozen.get(group['symbol'], 0)+reservation['quantity']
            positions = [s['positions'] for s in state['strategies'].values()]+[state['unallocated_positions']]
            symbols = set(account['positions']) | {symbol for p in positions for symbol in p}
            for symbol in symbols:
                actual = account['positions'].get(symbol, {'quantity': 0, 'sellable': 0})
                for p in positions:
                    held = p.get(symbol)
                    if held:
                        mature = [lot for lot in held['lots'] if lot['day'] <= account['day']]
                        held['sellable'] += sum(lot['quantity'] for lot in mature)
                        held['lots'] = [lot for lot in held['lots'] if lot['day'] > account['day']]
                _need(sum(p.get(symbol, {}).get('quantity', 0) for p in positions) == actual['quantity'], 'account_position_mismatch')
                _need(sum(p.get(symbol, {}).get('sellable', 0) for p in positions)-frozen.get(symbol, 0) == actual['sellable'], 'account_sellable_mismatch')
            state['account'] = account
            self._save(db, rev, state)

    def record_targets(self, intent: TargetIntent, *, deadline):
        _need(type(intent) is TargetIntent and type(intent.targets) is tuple, 'intent_invalid')
        _uuid(intent.intent_id); _text(intent.strategy_id); _quantity(intent.revision, positive=True)
        _sha(intent.source_sha256); _stamp(intent.known_at)
        targets, caps = {}, {}
        for target in intent.targets:
            _need(type(target) is Target, 'intent_invalid')
            _symbol(target.symbol); _quantity(target.quantity, lot=True)
            _need(target.symbol not in targets, 'intent_invalid')
            targets[target.symbol] = target.quantity
            caps[target.symbol] = None if target.buy_price_cap_cny is None else _price(target.buy_price_cap_cny)
        payload = {'intent_id': intent.intent_id, 'revision': intent.revision, 'targets': targets,
                   'buy_caps': caps, 'source_sha256': intent.source_sha256, 'known_at': intent.known_at}
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            _need(intent.strategy_id in state['strategies'], 'strategy_unknown')
            if not self._event(db, 'intent:'+intent.intent_id, {'strategy': intent.strategy_id, **payload}):
                return
            strategy = state['strategies'][intent.strategy_id]
            _need(set(targets) == set(strategy['universe']), 'target_scope_incomplete')
            _need(strategy['intent'] is None or intent.revision > strategy['intent']['revision'], 'intent_stale')
            _need(all(not p['quantity'] or symbol in targets for symbol, p in strategy['positions'].items()), 'target_scope_incomplete')
            strategy['intent'] = payload
            self._save(db, rev, state)

    def current_targets(self, *, deadline):
        """一次原事务读取完整策略意图；None保持未提交，不能推为零目标。"""
        with self._transaction(deadline) as db:
            _, state = self._load(db)
            result = {}
            for sid, strategy in state['strategies'].items():
                item = strategy['intent']
                result[sid] = None if item is None else TargetIntent(item['intent_id'], sid, item['revision'],
                    tuple(Target(symbol, qty, None if item['buy_caps'][symbol] is None else Decimal(item['buy_caps'][symbol]))
                          for symbol, qty in sorted(item['targets'].items())), item['source_sha256'], item['known_at'])
            return result

    @classmethod
    def _native_demands(cls, state, execution_targets, blocked):
        """从WT账户净差分配原柜台买卖额度。内部净额不改变策略实际持仓。"""
        strategies = state['strategies']
        priority = cls._priority(state)
        demands = {}
        for symbol, target in sorted(execution_targets.items()):
            if symbol in blocked:
                continue
            owners = [sid for sid in priority if symbol in strategies[sid]['universe']]
            if not owners:
                continue
            positions = {sid: strategies[sid]['positions'].get(symbol, {}) for sid in owners}
            actual = {sid: positions[sid].get('quantity', 0) for sid in owners}
            sellable = {sid: positions[sid].get('sellable', 0) for sid in owners}
            wanted = {sid: (strategies[sid]['intent']['targets'][symbol]
                            if strategies[sid]['intent'] is not None else actual[sid])
                      for sid in owners}
            unallocated = state['unallocated_positions'].get(symbol, {}).get('quantity', 0)
            net = target - sum(actual.values()) - unallocated
            if net == 0:
                continue
            side = 'buy' if net > 0 else 'sell'
            remaining = abs(net)
            quantities = {}
            for sid in owners:
                gap = wanted[sid] - actual[sid] if net > 0 else min(actual[sid] - wanted[sid], sellable[sid])
                quantities[sid] = min(remaining, max(0, gap))
                remaining -= quantities[sid]
            if net < 0:
                # 组合风控可能要求额外减仓。只从已归属的库存分配，未分配库存不出售。
                extra = min(remaining, max(0, sum(wanted.values()) - target))
                for sid in owners:
                    quantity = min(extra, sellable[sid] - quantities[sid])
                    quantities[sid] += quantity
                    extra -= quantity
            rows = [{'strategy': sid, 'quantity': quantity}
                    for sid, quantity in quantities.items() if quantity]
            if rows:
                demands[symbol] = {'side': side, 'remaining': rows}
        return demands

    def plan(self, plan_id, prices: tuple[CommonPrice, ...], *, deadline, execution_targets=None):
        """实装双策略沿WT执行目标分配净差。无执行目标的独立归属演练沿原内部转移合同。"""
        _uuid(plan_id); _need(type(prices) is tuple, 'price_invalid')
        if execution_targets is not None:
            _need(type(execution_targets) is dict and not prices, 'execution_targets_invalid')
            execution_targets = dict(execution_targets)
            for symbol, quantity in execution_targets.items():
                _symbol(symbol); _quantity(quantity)
        quotes = {}
        for price in prices:
            _need(type(price) is CommonPrice and type(price.qualified) is bool and type(price.participants) is tuple, 'price_invalid')
            _symbol(price.symbol); _price(price.price_cny); _sha(price.source_sha256); _stamp(price.known_at, allow_future=True)
            for participant in price.participants: _text(participant)
            _need(price.symbol not in quotes and len(set(price.participants)) == len(price.participants), 'price_invalid')
            quotes[price.symbol] = asdict(price)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            inputs = {'prices': quotes}
            if execution_targets is not None:
                inputs['execution_targets'] = execution_targets
            if not self._event(db, 'plan:'+plan_id, inputs):
                return self._plan_view(state['plans'][plan_id])
            _need(plan_id not in state['plans'], 'storage_invalid')
            blocked = {g['symbol']: 'pending_group' for g in state['groups'].values() if not g['closed']}
            if execution_targets is not None:
                demands = self._native_demands(state, execution_targets, blocked)
                plan = {'plan_id': plan_id, 'demands': demands, 'transfers': [], 'blocked_reasons': blocked,
                        'intents': {sid: s['intent'] for sid, s in state['strategies'].items()}}
                state['plans'][plan_id] = plan; state['active_plan'] = plan_id
                self._save(db, rev, state)
                return self._plan_view(plan)
            deltas = {}
            for sid in self._priority(state):
                strategy = state['strategies'][sid]
                wanted = strategy['intent']['targets'] if strategy['intent'] is not None else {
                    symbol: p['quantity'] for symbol, p in strategy['positions'].items()}
                for symbol, quantity in wanted.items():
                    delta = quantity-self._pos(strategy, symbol)['quantity']
                    if delta:
                        deltas.setdefault(symbol, []).append({'strategy': sid, 'quantity': delta})
            transfers, demands = [], {}
            cash_reserves, _ = self._reserves(state)
            for symbol, entries in sorted(deltas.items()):
                if symbol in blocked:
                    continue
                # 一个证券的全部配对原子生效；其等待不回滚其他独立证券。
                trial = deepcopy(state['strategies']); paired = []
                buys = [dict(e) for e in entries if e['quantity'] > 0]
                sells = [dict(e) for e in entries if e['quantity'] < 0]
                try:
                    while buys and sells:
                        buyer, seller = buys[0], sells[0]; price = quotes.get(symbol)
                        _need(price is not None and price['qualified'] and {buyer['strategy'], seller['strategy']} <= set(price['participants']), 'common_price_unqualified')
                        at = _stamp(price['known_at'])
                        for entry in (buyer, seller):
                            intent = trial[entry['strategy']]['intent']
                            _need(intent is not None and at >= _stamp(intent['known_at']), 'common_price_clock')
                        qty = min(buyer['quantity'], -seller['quantity'])
                        old = trial[seller['strategy']]; new = trial[buyer['strategy']]
                        op = self._pos(old, symbol); np = self._pos(new, symbol)
                        _need(op['sellable'] >= qty, 'internal_sellable_insufficient')
                        cap = new['intent']['buy_caps'][symbol]
                        _need(cap is None or Decimal(price['price_cny']) <= Decimal(cap), 'internal_price_cap')
                        amount = _gross(price['price_cny'], qty)
                        _need(new['cash']-cash_reserves[buyer['strategy']] >= amount, 'strategy_cash_insufficient')
                        if not np['quantity']:
                            self._open_cycle(new, buyer['strategy'], symbol,
                                ['internal-transfer', plan_id, seller['strategy'], buyer['strategy']],
                                at.astimezone(timezone.utc).isoformat(), price['source_sha256'])
                        old['cash'] += amount; new['cash'] -= amount
                        op['quantity'] -= qty; op['sellable'] -= qty; np['quantity'] += qty; np['sellable'] += qty
                        if not op['quantity']: old['cycles'].pop(symbol, None)
                        paired.append({'symbol': symbol, 'seller': seller['strategy'], 'buyer': buyer['strategy'],
                                       'quantity': qty, 'amount_cents': amount, 'price_cny': str(price['price_cny']),
                                       'source_sha256': price['source_sha256'], 'kind': 'internal_transfer', 'fee_cents': 0})
                        buyer['quantity'] -= qty; seller['quantity'] += qty
                        if not buyer['quantity']: buys.pop(0)
                        if not seller['quantity']: sells.pop(0)
                except AllocationError as error:
                    if error.reason not in ('common_price_unqualified', 'common_price_clock', 'clock_invalid',
                            'internal_sellable_insufficient', 'internal_price_cap', 'strategy_cash_insufficient'):
                        raise
                    blocked[symbol] = error.reason
                    continue
                state['strategies'] = trial; transfers.extend(paired)
                left = buys or sells
                if left:
                    demands[symbol] = {'side': 'buy' if buys else 'sell', 'remaining': [
                        {'strategy': e['strategy'], 'quantity': abs(e['quantity'])} for e in left]}
                self._check(deadline)
            plan = {'plan_id': plan_id, 'demands': demands, 'transfers': transfers, 'blocked_reasons': blocked,
                    'intents': {sid: s['intent'] for sid, s in state['strategies'].items()}}
            state['plans'][plan_id] = plan; state['active_plan'] = plan_id
            self._save(db, rev, state)
            return self._plan_view(plan)

    @staticmethod
    def _plan_view(plan):
        return PlanView(plan['plan_id'], tuple(PlanOrder(symbol, row['side'], sum(a['quantity'] for a in row['remaining']))
            for symbol, row in sorted(plan['demands'].items()) if sum(a['quantity'] for a in row['remaining'])),
            tuple(plan['transfers']), tuple(sorted(plan['blocked_reasons'])), dict(plan['blocked_reasons']))

    @classmethod
    def _allocate_group(cls, state, plan_id, symbol, side, requested, price, fee):
        """预览与最终绑定共用的唯一份额/资金分配；此函数不修改原账。"""
        _need(state['active_plan'] == plan_id, 'plan_unknown')
        demand = state['plans'][plan_id]['demands'].get(symbol)
        if demand is None or demand['side'] != side:
            return []
        cash, sells = cls._reserves(state)
        account_left = max(0, state['account']['available']+state['account']['adjustment']-sum(cash.values()))
        numerator, denominator = Decimal(price).as_integer_ratio()
        unit = (numerator*100+denominator-1)//denominator
        left, result = requested, []
        for row in demand['remaining']:
            sid = row['strategy']; strategy = state['strategies'][sid]
            if not row['quantity'] or not left:
                continue
            intent = state['plans'][plan_id]['intents'][sid]
            cap = None if intent is None else intent['buy_caps'].get(symbol)
            if side == 'buy' and cap is not None and Decimal(price) > Decimal(cap):
                continue
            if side == 'buy':
                budget = min(strategy['cash']-cash[sid], account_left)-fee
                if budget < 0:
                    continue
                capacity = budget//unit
            else:
                # 原WT卖出只受可卖库存约束；真实费用随已发生D入账，不预设佣金现金门槛。
                capacity = max(0, strategy['positions'].get(symbol, {}).get('sellable', 0)-sells.get((sid, symbol), 0))
            qty = min(left, row['quantity'], capacity)
            if qty:
                result.append({'strategy': sid, 'quantity': qty, 'filled': 0, 'prepared': 0})
                if side == 'buy':
                    account_left -= fee+unit*qty
                left -= qty
        # 原WT BUY总量整手；每策略归属可含历史部分成交形成的碎份。
        excess = sum(a['quantity'] for a in result) % 100 if side == 'buy' else 0
        for a in reversed(result):
            reduction = min(excess, a['quantity']); a['quantity'] -= reduction; excess -= reduction
        return [a for a in result if a['quantity']]

    def preview_group(self, plan_id, symbol, side, requested_qty, limit_price_cny, fee_bound_cny, *, deadline):
        """原WT建组前只读资金授权；返回0等待，最终持久绑定另作事务复核。"""
        _uuid(plan_id); _symbol(symbol); _need(side in ('buy', 'sell'), 'group_invalid')
        _quantity(requested_qty, positive=True)
        price, fee = _price(limit_price_cny), _money(fee_bound_cny)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            allocations = self._allocate_group(state, plan_id, symbol, side, requested_qty, price, fee)
            return GroupAuthorization(plan_id, symbol, side, requested_qty, sum(a['quantity'] for a in allocations),
                                      Decimal(price), _cny(fee), rev)

    def bind_group(self, plan_id, group: GroupBinding, *, deadline):
        _uuid(plan_id); _need(type(group) is GroupBinding, 'group_invalid')
        _text(group.group_id); _symbol(group.symbol); _need(group.side in ('buy', 'sell'), 'group_invalid')
        _quantity(group.quantity, positive=True, lot=group.side == 'buy'); price = _price(group.limit_price_cny); fee = _money(group.fee_bound_cny)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            if not self._event(db, 'group:'+group.group_id, {'plan': plan_id, **asdict(group)}):
                return
            _need(group.group_id not in state['groups'], 'plan_unknown')
            allocations = self._allocate_group(state, plan_id, group.symbol, group.side, group.quantity, price, fee)
            _need(sum(a['quantity'] for a in allocations) == group.quantity, 'authorization_changed')
            demand = state['plans'][plan_id]['demands'][group.symbol]
            for allocation in allocations:
                row = next(x for x in demand['remaining'] if x['strategy'] == allocation['strategy'])
                row['quantity'] -= allocation['quantity']
            state['groups'][group.group_id] = {'plan': plan_id, 'symbol': group.symbol, 'side': group.side,
                'quantity': group.quantity, 'price': price, 'fee_bound': fee, 'fee_paid': 0, 'allocations': allocations,
                'closed': False, 'unknown': False, 'commands': [], 'fills': [], 'children': [],
                'delegate_ended': False, 'accepted_children': None}
            cash, sells = self._reserves(state)
            if group.side == 'buy':
                _need(all(state['strategies'][a['strategy']]['cash'] >= cash[a['strategy']] for a in allocations), 'strategy_cash_insufficient')
                _need(sum(cash.values()) <= max(0, state['account']['available']+state['account']['adjustment']), 'account_cash_insufficient')
            for (sid, symbol), quantity in sells.items():
                _need(self._pos(state['strategies'][sid], symbol)['sellable'] >= quantity, 'strategy_sellable_insufficient')
            self._save(db, rev, state)

    @staticmethod
    def _close_if_resolved(state, group):
        """只组合原delegate/child/终态证明收口；不推断缺失回报或重发命令。"""
        if group['closed']:
            return True
        children = [state['children'][name] for name in group['children']]
        if not group['delegate_ended'] or group['accepted_children'] is None:
            return False
        prepared = sum(child['command'] is not None for child in children)
        if not prepared <= group['accepted_children'] <= len(children):
            return False
        for child in children:
            if child['command'] is None:
                if not child['not_called']:
                    return False
            elif state['commands'][child['command']]['terminal'] not in ('filled', 'cancelled', 'rejected', 'not_called'):
                return False
        demand = state['plans'][group['plan']]['demands'][group['symbol']]
        for allocation in group['allocations']:
            rest = allocation['quantity']-allocation['filled']
            next(row for row in demand['remaining'] if row['strategy'] == allocation['strategy'])['quantity'] += rest
        group['closed'] = True; group['unknown'] = False
        return True

    def record_wt_child(self, child: WTChild, *, deadline):
        """原enqueue前固定原WT child与FIFO；worker乱序不改变策略归属。"""
        _need(type(child) is WTChild, 'child_invalid')
        _text(child.group_id); _text(child.wt_order_id); _sha(child.source_sha256)
        _quantity(child.quantity, positive=True); price = _price(child.limit_price_cny)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            if not self._event(db, 'wt-child:'+child.wt_order_id, asdict(child)):
                return
            group = state['groups'].get(child.group_id)
            _need(group is not None and not group['closed'] and not group['delegate_ended'], 'group_unavailable')
            _need(child.wt_order_id not in state['children'], 'wt_identity_conflict')
            _quantity(child.quantity, positive=True, lot=group['side'] == 'buy')
            _need((group['side'] == 'buy' and Decimal(price) <= Decimal(group['price']))
                  or (group['side'] == 'sell' and Decimal(price) >= Decimal(group['price'])), 'child_price_bound')
            left, allocations = child.quantity, []
            for allocation in group['allocations']:
                qty = min(left, allocation['quantity']-allocation['prepared'])
                if qty:
                    allocation['prepared'] += qty; left -= qty
                    allocations.append({'strategy': allocation['strategy'], 'quantity': qty, 'filled': 0})
            _need(left == 0, 'child_quantity')
            state['children'][child.wt_order_id] = {'group': child.group_id, 'quantity': child.quantity,
                'price': price, 'command': None, 'not_called': False, 'source_sha256': child.source_sha256,
                'allocations': allocations}
            group['children'].append(child.wt_order_id)
            self._save(db, rev, state)

    def record_group_end(self, group_id, accepted_children, source_sha256, *, deadline):
        """原delegate退出只给数量事实；无prepared的已记child仍保留责任。"""
        _text(group_id); _quantity(accepted_children); _sha(source_sha256)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            if not self._event(db, 'group-end:'+group_id,
                               {'accepted_children': accepted_children, 'source_sha256': source_sha256}):
                return
            group = state['groups'].get(group_id)
            _need(group is not None and not group['delegate_ended'], 'group_unavailable')
            _need(sum(state['children'][c]['command'] is not None for c in group['children']) <= accepted_children <= len(group['children']), 'group_children_incomplete')
            group['delegate_ended'] = True; group['accepted_children'] = accepted_children
            self._close_if_resolved(state, group); self._save(db, rev, state)

    def record_child_not_called(self, group_id, wt_order_id, source_sha256, *, deadline):
        """仅原明确未调用证明可结束尚无prepared UUID的WT child。"""
        _text(group_id); _text(wt_order_id); _sha(source_sha256)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            if not self._event(db, 'child-not-called:'+wt_order_id,
                               {'group': group_id, 'source_sha256': source_sha256}):
                return
            child = state['children'].get(wt_order_id); group = state['groups'].get(group_id)
            _need(child is not None and child['group'] == group_id and child['command'] is None
                  and group is not None and not group['closed'], 'child_unavailable')
            child['not_called'] = True
            for part in child['allocations']:
                next(a for a in group['allocations'] if a['strategy'] == part['strategy'])['prepared'] -= part['quantity']
            self._close_if_resolved(state, group); self._save(db, rev, state)

    def bind_prepared(self, command: PreparedCommand, *, deadline):
        _need(type(command) is PreparedCommand, 'command_invalid')
        _text(command.group_id); _text(command.wt_order_id); _uuid(command.command_id); _sha(command.command_sha256)
        _quantity(command.quantity, positive=True); price = _price(command.limit_price_cny)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            first = self._event(db, 'prepared:'+command.command_id, asdict(command))
            if first:
                group = state['groups'].get(command.group_id)
                _need(group is not None and not group['closed'] and not group['unknown'], 'group_unavailable')
                _quantity(command.quantity, positive=True, lot=group['side'] == 'buy')
                child = state['children'].get(command.wt_order_id)
                _need(child is not None and child['group'] == command.group_id and child['command'] is None
                      and not child['not_called'], 'wt_child_unbound')
                _need(child['quantity'] == command.quantity and Decimal(child['price']) == Decimal(price), 'prepared_child_changed')
                _need(not any(state['commands'][c]['terminal'] == 'unknown' for c in group['commands']), 'group_unavailable')
                _need((group['side'] == 'buy' and Decimal(price) <= Decimal(group['price']))
                      or (group['side'] == 'sell' and Decimal(price) >= Decimal(group['price'])), 'child_price_bound')
                _need(not any(c['wt_order_id'] == command.wt_order_id for c in state['commands'].values()), 'wt_identity_conflict')
                if group['side'] == 'buy':
                    cash, _ = self._reserves(state)
                    _need(all(state['strategies'][a['strategy']]['cash'] >= cash[a['strategy']]
                              for a in group['allocations']), 'strategy_cash_insufficient')
                    _need(sum(cash.values()) <= max(0, state['account']['available']+state['account']['adjustment']), 'account_cash_insufficient')
                state['commands'][command.command_id] = {'group': command.group_id, 'wt_order_id': command.wt_order_id,
                    'sha256': command.command_sha256, 'quantity': command.quantity, 'price': price,
                    'filled': 0, 'terminal': None, 'allocations': deepcopy(child['allocations'])}
                child['command'] = command.command_id
                group['commands'].append(command.command_id)
                self._save(db, rev, state)
            return DispatchPermit(command.group_id, command.wt_order_id, command.command_id, command.command_sha256, first)

    def lookup_prepared(self, wt_order_id, *, deadline):
        """沿已持久原WT标识核查prepared身份；返回None表示尚未关联，不生成新UUID。"""
        _text(wt_order_id)
        with self._transaction(deadline) as db:
            _, state = self._load(db)
            return self._prepared(state, wt_order_id)

    @staticmethod
    def _prepared(state, wt_order_id):
        child = state['children'].get(wt_order_id)
        if child is None or child['command'] is None:
            return None
        command_id = child['command']
        command = state['commands'][command_id]
        _need(command['wt_order_id'] == wt_order_id, 'storage_invalid')
        return PreparedCommand(command['group'], wt_order_id, command_id, command['sha256'],
                               command['quantity'], Decimal(command['price']))

    def lookup_wt_child(self, wt_order_id, *, deadline):
        """只读原child处置，供收件证明恢复；未调用资格仍由原owner证明入口授予。"""
        _text(wt_order_id)
        with self._transaction(deadline) as db:
            _, state = self._load(db)
            child = state['children'].get(wt_order_id)
            command = None if child is None or child['command'] is None else state['commands'][child['command']]
            return (None if child is None else WTChildDisposition(child['group'], wt_order_id,
                    child['command'], child['not_called'], None if command is None else command['terminal']))

    @staticmethod
    def _fee(state, fill, fee):
        group = state['groups'][fill['group']]
        _need(group['fee_paid']+fee <= group['fee_bound'], 'fee_bound_exceeded')
        parts = [(a['strategy'], a['quantity']) for a in fill['allocations']]
        for (sid, _), cents in zip(parts, _split(fee, parts)):
            # 真实已发生费用完整归原策略；有符号亏欠不转嫁其他策略，不拒收原成交。
            state['strategies'][sid]['cash'] -= cents
        group['fee_paid'] += fee; fill['fee'] = fee
        state['account']['adjustment'] -= fee

    @staticmethod
    def _fill_economics(fact, price, amount):
        numerator, denominator = Decimal(price).as_integer_ratio()
        return dict(command_id=fact.command_id, quantity=fact.quantity, price_milli=numerator*1000//denominator,
                    amount_cents=amount, trading_day=fact.trading_day, settlement_day=fact.settlement_day,
                    symbol=fact.symbol, side=fact.side)

    def apply_fill(self, fact: FillFact, *, deadline):
        _need(type(fact) is FillFact, 'fill_invalid')
        _text(fact.fill_id); _uuid(fact.command_id); _sha(fact.source_sha256)
        _quantity(fact.quantity, positive=True); price = _price(fact.price_cny); amount = _money(fact.amount_cny)
        _day(fact.trading_day); _day(fact.settlement_day)
        _symbol(fact.symbol); _need(fact.side in ('buy', 'sell'), 'fill_invalid')
        _need(fact.trading_day <= datetime.now(timezone(timedelta(hours=8))).date().isoformat(), 'fill_future_day')
        fee = None if fact.fee_cny is None else _money(fact.fee_cny)
        executed = None if fact.executed_at is None else _stamp(fact.executed_at).astimezone(timezone.utc).isoformat()
        if executed is not None:
            _need(_stamp(executed).astimezone(timezone(timedelta(hours=8))).date().isoformat() == fact.trading_day, 'fill_execution_day')
        _need(amount == _gross(price, fact.quantity), 'fill_amount')
        economics = self._fill_economics(fact, price, amount)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            existing = state['fills'].get(fact.fill_id)
            if existing is not None:
                _need(db.execute('SELECT 1 FROM asa_events WHERE identity=?', ('fill:'+fact.fill_id,)).fetchone(), 'storage_invalid')
                conflict = existing['economics'] != economics or (
                    executed is not None and existing['executed_at'] is not None and executed != existing['executed_at']) or (
                    fee is not None and existing['fee'] is not None and fee != existing['fee'])
                if conflict:
                    payload = _wire({'expected': existing['economics'], 'incoming': asdict(fact)})
                    identity = hashlib.sha256(payload.encode('ascii')).hexdigest()
                    db.execute('INSERT OR IGNORE INTO asa_conflicts VALUES(?,?,?,?,?)',
                               (identity, 'fill_economic_conflict', fact.fill_id, payload, fact.source_sha256))
                    raise _RecordedRejection('fill_economic_conflict')
                changed = False
                if fact.source_sha256 not in existing['source_proofs']:
                    existing['source_proofs'].append(fact.source_sha256); changed = True
                if executed is not None and existing['executed_at'] is None:
                    existing['executed_at'] = executed; changed = True
                    for strategy in state['strategies'].values():
                        for cycle in strategy['cycles'].values():
                            if cycle.get('origin_fill_id') == fact.fill_id and cycle['opened_at'] is None:
                                cycle.update(opened_at=executed, source_sha256=fact.source_sha256, status='held')
                if fee is not None and existing['fee'] is None:
                    self._fee(state, existing, fee); changed = True
                if changed: self._save(db, rev, state)
                return
            _need(self._event(db, 'fill:'+fact.fill_id, asdict(fact)), 'storage_invalid')
            self._apply_new_fill(state, fact, price, amount, fee, economics, executed)
            self._save(db, rev, state)

    def _apply_new_fill(self, state, fact, price, amount, fee, economics, executed):
        command = state['commands'].get(fact.command_id)
        _need(command is not None, 'command_unknown')
        group = state['groups'][command['group']]
        _need(group['symbol'] == fact.symbol and group['side'] == fact.side, 'fill_scope_conflict')
        _need(not group['closed'] and command['terminal'] in (None, 'unknown') and command['filled']+fact.quantity <= command['quantity'], 'fill_after_terminal_or_overfill')
        _need((group['side'] == 'buy' and Decimal(price) <= Decimal(command['price']))
              or (group['side'] == 'sell' and Decimal(price) >= Decimal(command['price'])), 'fill_price_bound')
        _need(group['side'] != 'buy' or fact.settlement_day > fact.trading_day, 'settlement_day_invalid')
        left, parts = fact.quantity, []
        for allocation in command['allocations']:
            quantity = min(left, allocation['quantity']-allocation['filled'])
            if quantity:
                allocation['filled'] += quantity; left -= quantity
                next(a for a in group['allocations'] if a['strategy'] == allocation['strategy'])['filled'] += quantity
                parts.append((allocation['strategy'], quantity))
        _need(left == 0, 'allocation_quantity')
        allocations = []
        for (sid, quantity), gross in zip(parts, _split(amount, parts)):
            strategy = state['strategies'][sid]; p = self._pos(strategy, group['symbol'])
            if group['side'] == 'buy':
                # BUY资格在派发前成立；后到的实际费用不能使已发生D丢失。
                if not p['quantity']:
                    self._open_cycle(strategy, sid, group['symbol'], ['fill', fact.fill_id], executed, fact.source_sha256, fill_id=fact.fill_id)
                strategy['cash'] -= gross; p['quantity'] += quantity
                p['lots'].append({'quantity': quantity, 'day': fact.settlement_day})
            else:
                _need(p['sellable'] >= quantity, 'fill_sellable_insufficient')
                strategy['cash'] += gross; p['quantity'] -= quantity; p['sellable'] -= quantity
                if not p['quantity']: strategy['cycles'].pop(group['symbol'], None)
            allocations.append({'strategy': sid, 'quantity': quantity, 'amount_cents': gross})
        command['filled'] += fact.quantity
        # 已发生本金流立即计入本地上限；下一份完整P/A核同后才替换来源上限。
        state['account']['adjustment'] += amount if group['side'] == 'sell' else -amount
        fill = {'group': command['group'], 'command': fact.command_id, 'quantity': fact.quantity, 'amount': amount,
                'fee': None, 'allocations': allocations, 'source_sha256': fact.source_sha256,
            'source_proofs': [fact.source_sha256], 'economics': economics, 'executed_at': executed}
        state['fills'][fact.fill_id] = fill; group['fills'].append(fact.fill_id)
        if fee is not None:
            self._fee(state, fill, fee)

    def apply_fee(self, fact: FeeFact, *, deadline):
        _need(type(fact) is FeeFact, 'fee_invalid')
        _uuid(fact.event_id); _text(fact.fill_id); _sha(fact.source_sha256); fee = _money(fact.fee_cny)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            if not self._event(db, 'fee:'+fact.event_id, asdict(fact)):
                return
            fill = state['fills'].get(fact.fill_id)
            _need(fill is not None, 'fill_unknown')
            if fill['fee'] is not None:
                _need(fill['fee'] == fee, 'fee_conflict')
                return
            self._fee(state, fill, fee)
            self._save(db, rev, state)

    def apply_terminal(self, fact: TerminalFact, *, deadline):
        _need(type(fact) is TerminalFact, 'terminal_invalid')
        _uuid(fact.event_id); _text(fact.group_id); _sha(fact.source_sha256)
        _need(fact.state in ('filled', 'cancelled', 'rejected', 'not_called', 'unknown', 'group_closed'), 'terminal_invalid')
        if fact.command_id is not None: _uuid(fact.command_id)
        if fact.filled_quantity is not None: _quantity(fact.filled_quantity)
        with self._transaction(deadline) as db:
            rev, state = self._load(db)
            prior_event = db.execute('SELECT payload FROM asa_events WHERE identity=?', ('terminal:'+fact.event_id,)).fetchone()
            if prior_event is not None:
                _need(prior_event[0] == _wire(asdict(fact)), 'event_identity_conflict')
                return
            group = state['groups'].get(fact.group_id)
            _need(group is not None, 'group_unknown')
            if fact.command_id is None:
                if fact.state == 'unknown':
                    if not group['closed']: group['unknown'] = True
                else:
                    _need(fact.state in ('group_closed', 'not_called'), 'terminal_invalid')
                    _need(fact.state != 'not_called' or not group['children'], 'group_called')
                    _need(self._close_if_resolved(state, group), 'group_unresolved')
            else:
                command = state['commands'].get(fact.command_id)
                _need(command is not None and command['group'] == fact.group_id, 'command_unknown')
                prior = command['terminal']
                _need(fact.state != 'group_closed', 'terminal_invalid')
                definitive = ('filled', 'cancelled', 'rejected', 'not_called')
                if prior in definitive and fact.state != 'unknown' and (
                        fact.state != prior or fact.filled_quantity != command['filled']):
                    payload = _wire({'expected_state': prior, 'expected_filled': command['filled'], 'incoming': asdict(fact)})
                    key = hashlib.sha256(payload.encode('ascii')).hexdigest()
                    db.execute('INSERT OR IGNORE INTO asa_conflicts VALUES(?,?,?,?,?)',
                               (key, 'terminal_economic_conflict', fact.command_id, payload, fact.source_sha256))
                    raise _RecordedRejection('terminal_economic_conflict')
                if fact.state != 'unknown':
                    _need(fact.filled_quantity is not None and fact.filled_quantity == command['filled'], 'terminal_missing_fills')
                _need(fact.state != 'filled' or command['filled'] == command['quantity'], 'terminal_missing_fills')
                _need(fact.state not in ('rejected', 'not_called') or command['filled'] == 0, 'terminal_has_fills')
                command.setdefault('terminal_proofs', []).append(asdict(fact))
                if prior not in definitive:
                    if fact.state in definitive:
                        for part in command['allocations']:
                            next(a for a in group['allocations'] if a['strategy'] == part['strategy'])['prepared'] -= part['quantity']-part['filled']
                    command['terminal'] = fact.state
                self._close_if_resolved(state, group)
            self._event(db, 'terminal:'+fact.event_id, asdict(fact))
            self._save(db, rev, state)

    @staticmethod
    def _strategy_view(state, strategy_id, revision):
        _need(strategy_id in state['strategies'], 'strategy_unknown')
        strategy = state['strategies'][strategy_id]; cash, sells = AccountAllocation._reserves(state)
        unknown = sum(fill['fee'] is None and any(a['strategy'] == strategy_id for a in fill['allocations']) for fill in state['fills'].values())
        reserved = cash[strategy_id]
        positions = tuple(PositionView(symbol, position['quantity'], position['sellable']-sells.get((strategy_id, symbol), 0),
                                       sells.get((strategy_id, symbol), 0)) for symbol, position in sorted(strategy['positions'].items()))
        return StrategyView(strategy_id, strategy['version'], None if unknown else _cny(strategy['cash']),
            _cny(strategy['cash']), _cny(reserved), _cny(max(0, strategy['cash']-reserved)), unknown, positions,
            tuple(key for key, group in state['groups'].items() if not group['closed']
                  and any(a['strategy'] == strategy_id for a in group['allocations'])), revision)

    def strategy_observation(self, strategy_id, *, deadline):
        """同一归属事务提供策略持仓/周期与账户来源身份；不复制账户D/P分配。"""
        _text(strategy_id)
        with self._transaction(deadline) as db:
            revision, state = self._load(db)
            view = self._strategy_view(state, strategy_id, revision)
            strategy = state['strategies'][strategy_id]; cycles = {}
            fields = ('symbol', 'cycle_id', 'opened_at', 'source_sha256', 'status')
            for symbol in strategy['universe']:
                position = strategy['positions'].get(symbol)
                if position is None or not position['quantity']:
                    cycles[symbol] = None
                else:
                    cycle = strategy['cycles'].get(symbol)
                    cycles[symbol] = OpeningCycle(symbol, None, None, None, 'unknown') if cycle is None else OpeningCycle(**{k:cycle[k]for k in fields})
            # 从原已记账allocation投影数量/金额/费用，绝不按账户证券反推归属。
            from collections import deque
            allocated, allocated_count = deque(maxlen=2000), 0
            for identity, fill in state['fills'].items():
                self._check(deadline)
                parts = [(a['strategy'], a['quantity']) for a in fill['allocations']]
                fees = [None] * len(parts) if fill['fee'] is None else _split(fill['fee'], parts)
                for part, fee in zip(fill['allocations'], fees):
                    if part['strategy'] != strategy_id: continue
                    allocated_count += 1
                    economics = fill['economics']
                    allocated.append(OwnedFillObservation(identity, economics['symbol'], economics['side'],
                        part['quantity'], Decimal(economics['price_milli']) / 1000,
                        _cny(part['amount_cents']), None if fee is None else _cny(fee),
                        economics['trading_day'], fill['executed_at'], fill['source_sha256']))
            intent = strategy['intent']
            return StrategyObservation(view, state['account']['revision'], state['account']['source_sha256'],
                state['account']['day'], cycles, hashlib.sha256(_wire(asdict(self.identity)).encode('ascii')).hexdigest(),
                datetime.now(timezone.utc).isoformat(), None if intent is None else dict(intent['targets']),
                tuple(allocated), allocated_count > 2000)

    def view(self, strategy_id, *, deadline):
        _text(strategy_id)
        with self._transaction(deadline) as db:
            revision, state = self._load(db)
            return self._strategy_view(state, strategy_id, revision)
