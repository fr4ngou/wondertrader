"""固定线上profile目录；不接受动态模块、脚本或任意包加载。"""
RETAINED_PROFILE = 'guanheng.retained-cta.v1'
RETAINED_ID = 'resonance-regime-v1'
ORIGINAL_PROFILE = 'guanheng.original-live-cta.v1'
ORIGINAL_ID = 'resonance-original-wt-351f9d5-stable'
RETAINED_PACKAGES = ('guanheng_wt_runtime', 'guanheng_strategy_core',
                     'guanheng_strategy_native', 'guanheng_strategy_v1', 'tzdata')
SHARED_PACKAGES = RETAINED_PACKAGES + ('guanheng_strategy_original', 'guanheng_market_client')


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
