"""共享账户受控材料准入；ASA初始化借用原Native账户租约。"""
from __future__ import annotations

from decimal import Decimal, localcontext, ROUND_CEILING
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
from time import monotonic
from threading import RLock

from .account_attribution import AttributionBridge, AttributionCoordinator, AttributionError, _need
from .managed_local_process import _json, _read


def _fixed(descriptor, deadline, maximum=1024*1024):
    _need(type(descriptor) is dict and set(descriptor) == {'path', 'sha256'}, 'shared_account_descriptor')
    path = Path(descriptor['path'])
    _need(path.is_absolute() and path.drive.upper() in ('D:', 'E:'), 'shared_account_drive')
    raw = _read(path, maximum, clock=monotonic, deadline=deadline)
    _need(hashlib.sha256(raw).hexdigest() == descriptor['sha256'], 'shared_account_identity')
    return _json(raw)


class _BorrowedAllocation:
    """配置对象不打开SQLite；首次原Native借用才初始化，后继重启核同原初值。"""
    def __init__(self, root, identity, seeds, unallocated, snapshot, *, require_existing=False):
        self._root, self._identity = root, identity  # 原金融状态根及稳定账本身份，保留跨代经济归属。
        self._seeds, self._unallocated, self._snapshot = seeds, unallocated, snapshot  # 显式冻结初值，不用账户available重建旧本金。
        self._allocation, self._bridge = None, None  # ASA唯一事实owner；bridge由同次Runtime装配后授同步借用。
        self._initialized = False  # 初值验证成功后才向后继调用和热读发布。
        self._require_existing = require_existing  # 独立账本路径须接续原库。
        self._lock = RLock()  # 首次Native owner/worker竞争共享同一初始化，等待计入原D。

    def bind(self, bridge):
        _need(self._bridge is None, 'shared_account_already_bound')
        self._bridge = bridge

    def close(self, deadline):
        return self._allocation is None or self._allocation.close(deadline)

    def strategy_state(self, strategy_id, *, deadline):
        allocation = self._allocation
        _need(self._initialized, 'shared_account_state_unavailable')
        return allocation.strategy_state(strategy_id, deadline=deadline)

    def strategy_history(self, strategy_id, *, deadline):
        if not self._initialized:
            return None
        return self._allocation.strategy_observation(strategy_id, deadline=deadline)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        # getattr本身不触盘；原方法调用的绝对D同时约束首次初始化。
        def invoke(*args, deadline, **kwargs):
            self._bridge.owner_check()
            _need(self._lock.acquire(timeout=max(0, deadline-monotonic())), 'shared_account_deadline')
            try:
                if not self._initialized:
                    from .account_allocation import AccountAllocation
                    if self._allocation is None:
                        self._allocation = AccountAllocation(self._root, self._identity, owner_check=self._bridge.owner_check,
                                                             require_existing=self._require_existing, wal=True)
                    self._allocation.initialize(self._seeds, self._unallocated, self._snapshot, deadline=deadline)
                    self._initialized = True
            finally:
                self._lock.release()
            return getattr(self._allocation, name)(*args, deadline=deadline, **kwargs)
        return invoke


def create_runtime_attribution(native, configuration, control_directory, control_id, *, deadline):
    """由账户配置和各策略seed装配同一归属owner，保持原初值和来源身份。"""
    from .account_allocation import (BookIdentity, StrategySeed, OwnedPosition, OpeningCycle,
                                     AccountSnapshot, SellReservation, _money)
    from .strategy_profiles import ORIGINAL_PROFILE, shared_profiles, shared_account_reference
    from guanheng_market_client.exchange_calendar import official_calendar

    _need(shared_profiles(native), 'shared_account_profile')
    strategies = {row['id']: row['parameters']['python_strategy'] for row in native['strategies']}
    generic = 'shared_account' in native['executer']
    value = _fixed(shared_account_reference(native), deadline)
    fields = {'schema', 'identity', 'financial_root', 'initialization',
              'calendar', 'fee_reserve_model', 'callback_seconds'}
    _need(type(value) is dict and fields <= set(value) <= fields | {'allocation_root'}
          and value['schema'] == 'guanheng.shared-account-allocation.v1', 'shared_account_schema')
    financial_root = Path(value['financial_root'])
    _need(financial_root.is_absolute() and financial_root.drive.upper() in ('D:', 'E:')
          and financial_root == Path(native['output_directory']), 'shared_account_financial_root')
    root = Path(value.get('allocation_root', value['financial_root']))
    _need(root.is_absolute() and root.drive.upper() in ('D:', 'E:'), 'shared_account_allocation_root')
    if root != financial_root:
        # 路径切换必须先迁入原账。缺少数据库时不能用初始化材料重建已运行账户。
        _need((root / 'account-allocation.sqlite3').is_file(), 'shared_account_relocated_book_missing')
    _need(Path(control_directory).is_absolute() and configuration.configuration.is_absolute(), 'shared_account_control')
    identity = BookIdentity(**value['identity'])
    account_scope = json.dumps(dict(account=native['trader']['expected_account'],
        environment=native['trader']['environment'], currency='CNY'), sort_keys=True, separators=(',', ':')).encode('ascii')
    _need(identity.account_scope_sha256 == hashlib.sha256(account_scope).hexdigest(), 'shared_account_scope_identity')
    initial = _fixed(value['initialization'], deadline)
    _need(type(initial) is dict and set(initial) == {'schema', 'seeds', 'unallocated_cash_cny',
          'account_snapshot', 'source_evidence'} and initial['schema'] == 'guanheng.account-allocation-seed.v1',
          'shared_account_seed')
    evidence = initial['source_evidence']
    _need(type(evidence) is dict and set(evidence) == {'old_basis', 'account_observation'}, 'shared_account_seed_evidence')
    for descriptor in evidence.values():
        _fixed(descriptor, deadline, 4*1024*1024)
    _need(identity.baseline_sha256 == evidence['old_basis']['sha256'], 'shared_account_baseline')
    seeds = []
    for item in initial['seeds']:
        fields = dict(item)
        _need(type(fields['cash_cny']) is str, 'shared_account_money')
        fields['cash_cny'] = Decimal(fields['cash_cny'])
        fields['positions'] = tuple(OwnedPosition(**p) for p in fields['positions'])
        fields['universe'] = tuple(fields['universe'])
        fields['opening_cycles'] = tuple(OpeningCycle(**p) for p in fields.get('opening_cycles', []))
        seeds.append(StrategySeed(**fields))
    _need(len(seeds) == len(strategies) and {seed.strategy_id for seed in seeds} == set(strategies),
          'shared_account_seed_scope')
    _need(len({seed.priority for seed in seeds}) == len(seeds), 'shared_account_seed_priority')
    for seed in seeds:
        parameters = strategies[seed.strategy_id]
        _money(seed.cash_cny)
        if parameters['schema'] == ORIGINAL_PROFILE:
            from .original_live import initial_capital
            _need(seed.cash_cny == initial_capital(parameters) and not seed.positions
                  and not seed.opening_cycles, 'shared_account_user_allocation')
            _need(seed.version == parameters['strategy_version'], 'shared_account_strategy_version')
    snapshot = dict(initial['account_snapshot'])
    _need(type(snapshot['available_cny']) is str, 'shared_account_money')
    snapshot['available_cny'] = Decimal(snapshot['available_cny'])
    snapshot['positions'] = tuple(OwnedPosition(**p) for p in snapshot['positions'])
    snapshot['sell_reservations'] = tuple(SellReservation(**r) for r in snapshot.get('sell_reservations', []))
    snapshot = AccountSnapshot(**snapshot)
    _need(type(initial['unallocated_cash_cny']) is str, 'shared_account_money')
    unallocated = Decimal(initial['unallocated_cash_cny'])
    if generic:
        funded = _money(unallocated) + sum(_money(seed.cash_cny) for seed in seeds)
        _need(funded <= _money(snapshot.available_cny), 'shared_account_initial_cash_unfunded')
    # 同一份受控NAP原件的内容由部署审查核同；不能以可用余额替代旧seed。
    _need(snapshot.source_sha256 == evidence['account_observation']['sha256'], 'shared_account_snapshot_identity')
    calendar = _fixed(value['calendar'], deadline)
    def check():
        _need(monotonic() < deadline, 'shared_account_deadline')
    rows, unused_metadata = official_calendar(calendar, check=check)
    days = tuple(r['date'] for r in rows if r['is_open'])
    def observation_day(received_day):
        # 实际观察日由完整P/A接收时钟和同一官方日历所有；未来计划session保留给排程。
        if not calendar['coverage_start'] <= received_day <= calendar['coverage_end']:
            return None
        index = bisect_right(days, received_day)
        return days[index-1] if index else None
    def settlement(day):
        _need(day in days, 'shared_account_calendar_day')
        next_day = next((d for d in days if d > day), None)
        _need(next_day is not None, 'shared_account_calendar_outside_coverage')
        return next_day
    fees = _fixed(value['fee_reserve_model'], deadline)
    _need(type(fees) is dict and set(fees) == {'schema', 'source', 'securities'}
          and fees['schema'] == 'guanheng.asa-fee-reserve.v1' and type(fees['source']) is str and fees['source'],
          'shared_account_fee_model')
    universes = {seed.strategy_id: frozenset(seed.universe) for seed in seeds}
    _need(set(fees['securities']) == set().union(*universes.values()), 'shared_account_fee_scope')
    bounds = {}
    for symbol, sides in fees['securities'].items():
        _need(type(sides) is dict and set(sides) == {'buy', 'sell'}, 'shared_account_fee_model')
        for side, rule in sides.items():
            _need(type(rule) is dict and set(rule) == {'fixed_cny', 'per_share_cny'}, 'shared_account_fee_model')
            _need(type(rule['fixed_cny']) is str and type(rule['per_share_cny']) is str, 'shared_account_fee_model')
            fixed, unit = Decimal(rule['fixed_cny']), Decimal(rule['per_share_cny'])
            _need(fixed.is_finite() and unit.is_finite() and fixed >= 0 and unit >= 0, 'shared_account_fee_model')
            bounds[symbol, side] = fixed, unit
    def fee_bound(symbol, side, quantity, price):
        fixed, unit = bounds[symbol, side]
        with localcontext() as context:
            context.prec = 64
            return (fixed+unit*quantity).quantize(Decimal('.01'), rounding=ROUND_CEILING)
    allocation = _BorrowedAllocation(root, identity, tuple(seeds), unallocated, snapshot,
                                     require_existing=root != financial_root)
    coordinator = AttributionCoordinator(allocation, control_id=control_id,
        account_scope_sha256=identity.account_scope_sha256, strategy_ids=tuple(strategies),
        fee_bound=fee_bound, settlement_day=settlement, trading_day_qualified=lambda day: day in days,
        account_observation_day=observation_day, execution_scale=native['executer']['scale'],
        configured_universes=universes)
    bridge = AttributionBridge(coordinator, callback_seconds=value['callback_seconds'])
    allocation.bind(bridge)
    return coordinator, bridge
