"""双策略受控材料准入；纯读取先行，ASA初始化借用原Native账户租约。"""
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
    def __init__(self, root, identity, seeds, unallocated, snapshot):
        self._root, self._identity = root, identity  # 原金融状态根及稳定账本身份，保留跨代经济归属。
        self._seeds, self._unallocated, self._snapshot = seeds, unallocated, snapshot  # 显式冻结初值，不用账户available重建旧本金。
        self._allocation, self._bridge = None, None  # ASA唯一事实owner；bridge由同次Runtime装配后授同步借用。
        self._lock = RLock()  # 首次Native owner/worker竞争共享同一初始化，等待计入原D。

    def bind(self, bridge):
        _need(self._bridge is None, 'shared_account_already_bound')
        self._bridge = bridge

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        # getattr本身不触盘；原方法调用的绝对D同时约束首次初始化。
        def invoke(*args, deadline, **kwargs):
            self._bridge.owner_check()
            _need(self._lock.acquire(timeout=max(0, deadline-monotonic())), 'shared_account_deadline')
            try:
                if self._allocation is None:
                    from .account_allocation import AccountAllocation
                    allocation = AccountAllocation(self._root, self._identity, owner_check=self._bridge.owner_check)
                    allocation.initialize(self._seeds, self._unallocated, self._snapshot, deadline=deadline)
                    self._allocation = allocation
            finally:
                self._lock.release()
            return getattr(self._allocation, name)(*args, deadline=deadline, **kwargs)
        return invoke


def create_runtime_attribution(native, configuration, control_directory, control_id, *, deadline):
    """显式旧+原版组合的一次装配；仅核材料，返回惰性coordinator与可选Bridge。

    材料里的旧seed由原金融owner及部署审查提供并绑定原件SHA；本函数不从整账户
    available推断旧策略本金、成本或周期。原版固定新增100万元、零归属库存。
    实际采用、原Source权限扩展和旧ctx恢复由所属owner另行完成。
    """
    from .account_allocation import (BookIdentity, StrategySeed, OwnedPosition, OpeningCycle,
                                     AccountSnapshot, SellReservation)
    from guanheng_market_client.exchange_calendar import official_calendar
    from guanheng_strategy_original.reference import DEFAULT_CODES
    strategies = native['strategies']
    _need(type(strategies) is list and len(strategies) == 2, 'shared_account_profile')
    old = next((s for s in strategies if s['id'] == 'resonance-regime-v1'), None)
    original = next((s for s in strategies if s['id'] == 'resonance-original-wt-351f9d5-stable'), None)
    _need(old is not None and original is not None, 'shared_account_profile')
    parameters = original['parameters']['python_strategy']
    _need(parameters['schema'] == 'guanheng.original-live-cta.v1', 'shared_account_profile')
    value = _fixed(parameters['shared_account'], deadline)
    _need(type(value) is dict and set(value) == {'schema', 'identity', 'financial_root', 'initialization',
          'calendar', 'fee_reserve_model', 'callback_seconds'}
          and value['schema'] == 'guanheng.shared-account-allocation.v1', 'shared_account_schema')
    root = Path(value['financial_root'])
    _need(root.is_absolute() and root.drive.upper() in ('D:', 'E:')
          and root == Path(native['output_directory']), 'shared_account_financial_root')
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
    _need(len(seeds) == 2 and {s.strategy_id for s in seeds} == {old['id'], original['id']}, 'shared_account_seed_scope')
    old_seed = next(s for s in seeds if s.strategy_id == old['id'])
    new_seed = next(s for s in seeds if s.strategy_id == original['id'])
    original_universe = {('SZSE' if code.startswith('1') else 'SSE')+'.ETF.'+code for code in DEFAULT_CODES}
    _need(new_seed.cash_cny == Decimal('1000000') and not new_seed.positions and not new_seed.opening_cycles
          and set(new_seed.universe) == original_universe and old_seed.priority < new_seed.priority,
          'shared_account_user_allocation')
    _need(new_seed.version == parameters['strategy_version'], 'shared_account_strategy_version')
    snapshot = dict(initial['account_snapshot'])
    _need(type(snapshot['available_cny']) is str, 'shared_account_money')
    snapshot['available_cny'] = Decimal(snapshot['available_cny'])
    snapshot['positions'] = tuple(OwnedPosition(**p) for p in snapshot['positions'])
    snapshot['sell_reservations'] = tuple(SellReservation(**r) for r in snapshot.get('sell_reservations', []))
    snapshot = AccountSnapshot(**snapshot)
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
    _need(set(fees['securities']) == set(old_seed.universe) | set(new_seed.universe), 'shared_account_fee_scope')
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
    _need(type(initial['unallocated_cash_cny']) is str, 'shared_account_money')
    allocation = _BorrowedAllocation(root, identity, tuple(seeds), Decimal(initial['unallocated_cash_cny']), snapshot)
    coordinator = AttributionCoordinator(allocation, control_id=control_id,
        account_scope_sha256=identity.account_scope_sha256, strategy_ids=(old_seed.strategy_id, new_seed.strategy_id),
        fee_bound=fee_bound, settlement_day=settlement, trading_day_qualified=lambda day: day in days,
        account_observation_day=observation_day, execution_scale=native['executer']['scale'])
    bridge = AttributionBridge(coordinator, callback_seconds=value['callback_seconds'])
    allocation.bind(bridge)
    return coordinator, bridge
