"""固定线上profile目录；不接受动态模块、脚本或任意包加载。"""
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


def shared_profiles(native):
    """旧单策略原样通过；双策略固定身份且各只有一个独立ctx。"""
    rows = native.get('strategies')
    if type(rows) is not list:
        raise ValueError('strategy_profiles')
    pairs = tuple((r['id'], r['parameters'].get('python_strategy', {}).get('schema')) for r in rows)
    if pairs == ((RETAINED_ID, RETAINED_PROFILE),):
        return False
    if len(pairs) == 2 and set(pairs) == {(RETAINED_ID, RETAINED_PROFILE), (ORIGINAL_ID, ORIGINAL_PROFILE)}:
        return True
    raise ValueError('strategy_profiles')


def build_strategies(native, publish, configuration, *, deadline, code_identity, retained_factory, allocation=None):
    shared = shared_profiles(native)
    if shared and allocation is None:
        raise ValueError('shared_allocation_required')
    result = []
    for item in native['strategies']:
        if item['id'] == RETAINED_ID:factory = retained_factory
        else:
            from .original_live import OriginalLiveStrategy
            factory = OriginalLiveStrategy
        kwargs = dict(deadline=deadline, code_identity=code_identity)
        if shared:
            kwargs['allocation'] = allocation
        result.append(factory(item, publish, configuration, native, **kwargs))
    participants = {}
    for strategy in result:
        for symbol in strategy.targets:
            participants.setdefault(symbol, []).append(strategy.id)
    for strategy in result:
        strategy.participants = {symbol: tuple(sorted(ids)) for symbol, ids in participants.items()}
    return tuple(result)
