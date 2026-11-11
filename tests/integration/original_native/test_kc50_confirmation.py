from guanheng_strategy_original.kc50_confirmation import PullbackConfirmation


def test_pullback_holds_first_range_then_confirms():
    origin = dict(date='2026-10-08', close_price=1.53, high_price=1.61, low_price=1.52)
    gate = PullbackConfirmation({'2026-10-08': (-0.1, -0.2, 0.3)})
    assert gate.decide(origin, 'BUY', '牛市回调底: 原信号') == (None, '')
    later = dict(date='2026-10-09', close_price=1.61, high_price=1.7, low_price=1.55)
    assert gate.decide(later, 'BUY', '牛市回调底: 第二次') == (None, '')
    action, reason = gate.decide(dict(later, date='2026-10-12', close_price=1.62), None, '')
    assert action == 'BUY' and '2026-10-08 高点1.6100' in reason
    assert gate.pending is None


def test_original_panic_takes_priority_over_pullback_invalidation():
    origin = dict(date='2026-10-08', close_price=1.53, high_price=1.61, low_price=1.52)
    gate = PullbackConfirmation({'2026-10-08': (-0.1, -0.2, 0.3)})
    gate.decide(origin, 'BUY', '牛市回调底: 原信号')
    later = dict(date='2026-10-09', close_price=1.50, high_price=1.6, low_price=1.49)
    assert gate.decide(later, 'BUY', '恐慌底: 原信号') == ('BUY', '恐慌底: 原信号')
    assert gate.pending is None
