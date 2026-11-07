"""已注册profile与运行实例选择。配置引用固定策略实现。"""
from pathlib import PureWindowsPath
import re
RETAINED_PROFILE = 'guanheng.retained-cta.v1'
RETAINED_ID = 'resonance-regime-v1'
ORIGINAL_PROFILE = 'guanheng.original-live-cta.v1'
ORIGINAL_ID = 'resonance-original-wt-351f9d5-stable'
RETAINED_PACKAGES = ('guanheng_wt_runtime', 'guanheng_strategy_core',
                     'guanheng_strategy_native', 'guanheng_strategy_v1', 'tzdata')
SHARED_PACKAGES = RETAINED_PACKAGES + ('guanheng_strategy_original', 'guanheng_market_client')
SOURCE_OWNER_PACKAGES = ('guanheng_qmt_shm', 'guanheng_qmt_shm_agent')
SOURCE_HANDOFF_PACKAGES = SHARED_PACKAGES + SOURCE_OWNER_PACKAGES
# import包名与真实发行名分别固定；Host发行名不能由包名替换下划线推导。
PACKAGE_DISTRIBUTIONS = {package: package.replace('_', '-') for package in SOURCE_HANDOFF_PACKAGES}
PACKAGE_DISTRIBUTIONS['guanheng_qmt_shm'] = 'guanheng-qmt-shm-host'


def source_handoff(native, *, deadline=float('inf')):
    """仅由显式、原字节摘要已核的Source续接材料选择额外两个固定owner。

    这里只决定源码绑定集合；完整业务、原Source权限及恢复材料继续由原准入核验。
    无Source续接保持原单/双策略集合，材料错误直接拒绝，避免静默降为较小集合。
    """
    import hashlib
    import time
    from .managed_local_process import _read, _json, _path, _require, _sha
    marker = native.get('strategy_extension_origin')
    if marker is None or 'dependency_handoff' not in marker:
        return False
    reference = marker['dependency_handoff']
    _require(type(reference) is dict and set(reference) == {'file', 'sha256'})
    raw = _read(_path(reference['file']), 1024 * 1024, deadline=deadline, clock=time.monotonic)
    _require(hashlib.sha256(raw).hexdigest() == _sha(reference['sha256']))
    value = _json(raw)
    from .execution_dependency_handoff import FIELDS, SOURCE_FIELDS
    _require(type(value) is dict and set(value) == FIELDS
             and value['schema'] == 'guanheng.strategy-dependency-handoff.v1')
    proof = value['source_extension']
    _require(proof is None or type(proof) is dict and set(proof) == SOURCE_FIELDS)
    if proof is not None:
        _require(shared_profiles(native))
    return proof is not None


def shared_account_reference(native):
    """执行器统一持有账户描述符。兼容原版行内的旧引用。"""
    executer = native.get('executer', {})
    current = executer.get('shared_account')
    if 'shared_account' in executer and current is None:
        raise ValueError('shared_account_reference_missing')
    for item in native['strategies']:
        legacy = item['parameters']['python_strategy'].get('shared_account')
        if legacy is not None:
            if current is None:
                current = legacy
            elif current != legacy:
                raise ValueError('shared_account_reference_conflict')
    return current


def shared_profiles(native):
    """策略ID是运行实例身份，profile schema选择已登记的策略实现。"""
    rows = native.get('strategies')
    if type(rows) is not list or not 1 <= len(rows) <= 64:
        raise ValueError('strategy_profiles')
    seen = set()
    for row in rows:
        strategy_id = row['id']
        schema = row['parameters'].get('python_strategy', {}).get('schema')
        if (type(strategy_id) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,62}', strategy_id)
                or PureWindowsPath(strategy_id).is_reserved() or strategy_id.casefold() in seen
                or schema not in (RETAINED_PROFILE, ORIGINAL_PROFILE)
                or (schema == RETAINED_PROFILE and strategy_id != RETAINED_ID)
                or (strategy_id == RETAINED_ID and schema != RETAINED_PROFILE)):
            raise ValueError('strategy_profiles')
        seen.add(strategy_id.casefold())
    shared = shared_account_reference(native) is not None
    if not shared and (len(rows) != 1 or rows[0]['id'] != RETAINED_ID):
        raise ValueError('shared_allocation_required')
    return shared


def build_strategies(native, publish, configuration, *, deadline, code_identity, retained_factory, allocation=None):
    shared = shared_profiles(native)
    if shared and allocation is None:
        raise ValueError('shared_allocation_required')
    result = []
    for item in native['strategies']:
        if item['parameters']['python_strategy']['schema'] == RETAINED_PROFILE:
            factory = retained_factory
        else:
            from .original_live import OriginalLiveStrategy
            factory = OriginalLiveStrategy
        kwargs = dict(deadline=deadline, code_identity=code_identity)
        if shared:
            kwargs['allocation'] = allocation
        result.append(factory(item, publish, configuration, native, **kwargs))
    if shared:
        allocation.verify_profile_targets({strategy.id: strategy.targets for strategy in result})
    participants = {}
    for strategy in result:
        for symbol in strategy.targets:
            participants.setdefault(symbol, []).append(strategy.id)
    for strategy in result:
        strategy.participants = {symbol: tuple(sorted(ids)) for symbol, ids in participants.items()}
    return tuple(result)
