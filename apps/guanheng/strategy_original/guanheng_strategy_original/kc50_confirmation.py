"""七只 ETF 共振收复确认版的纯信号和组合风格规则。"""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from statistics import mean

STRATEGY_ID = 'resonance-kc50-pullback-confirm'
STRATEGY_VERSION = '0.3.0a1'
DISPLAY_NAME = '共振原版-科创50回调收复确认实验版'
CODES = ('159352', '159780', '510050', '510300', '512100', '515080', '588000')
START = '2021-11-01'
GROWTH = ('588000', '159780')
MARKET = ('510300', '512100')
DIVIDEND = '515080'
ALPHA = 1 - 2 ** (-1 / 5)
SHARE_FIELDS = ('shares_yi', 'shares_delta_yi', 'shares_delta_pct', 'share_prob', 'share_adjust')
REFERENCE_FIELD = 'kc50_pullback_confirmation'


def market_state(history, calendar):
    """从回放暖机日开始，按共同交易日递推两个宽基及成长相对红利的日收益。"""
    returns = {
        code: {row['date']: row['close'] / previous['close'] - 1 for previous, row in zip(rows, rows[1:])}
        for code, rows in history.items() if code in (*MARKET, *GROWTH, DIVIDEND)
    }
    state = [0.0, 0.0, 0.0]
    for day in calendar:
        growth = [returns[c][day] for c in GROWTH if day in returns[c]]
        if not growth or any(day not in returns[c] for c in (*MARKET, DIVIDEND)):
            continue
        daily = (returns[MARKET[0]][day], returns[MARKET[1]][day], mean(growth) - returns[DIVIDEND][day])
        state = [previous + (value - previous) * ALPHA for previous, value in zip(state, daily)]
        yield day, tuple(state)


def allocation(state, active):
    """新资金计划的权重分数，未形成一致风格时等权。"""
    favored = set()
    label = None
    if state and min(state) > 0:
        favored, label = active.intersection(GROWTH), '成长'
    elif state and max(state) < 0:
        favored, label = active.intersection((DIVIDEND,)), '红利'
    if favored and favored != active:
        return {code: 3 if code in favored else 2 for code in active}, label
    return dict.fromkeys(active, 1), None


def lagged_features(daily, calendar):
    """只用上一交易日的份额派生特征，同一组字段一起移动。"""
    from resonance.analysis.composite import calc_composite_probability
    from resonance.analysis.factors import classify_signal

    previous_day = dict(zip(calendar[1:], calendar))
    for code in CODES:
        rows = daily[code]
        by_day = {row['date']: row for row in rows}
        lagged = []
        for row in rows:
            prior = by_day.get(previous_day.get(row['date']), {})
            item = dict(row, **{key: prior.get(key) for key in SHARE_FIELDS})
            score = calc_composite_probability(item['vol_prob'], item['dir_prob'], item['share_prob'], item['price_position'])
            lagged.append(dict(item, composite_prob=score, signal_level=classify_signal(score)))
        yield code, lagged


@dataclass(frozen=True)
class Pullback:
    """一次科创 50 空仓回调观察，区间使用当时已闭合的 K 线。"""
    day: str  # 首个候选交易日，北京时间 YYYY-MM-DD。
    high: float  # 候选日最高价，前复权元/份。
    low: float  # 候选日最低价，前复权元/份。


class PullbackConfirmation:
    """只接收原科创 50 循环中空仓分支的候选。"""
    def __init__(self, market):
        self.market = market
        self.pending = None

    def decide(self, row, action, reason):
        day = row['date']
        if day < START:
            return action, reason
        pullback = action == 'BUY' and reason.startswith('牛市回调底:')
        if action == 'BUY' and not pullback:
            self.pending = None
            return action, reason
        if self.pending is not None:
            candidate = self.pending
            close = row['close_price']
            if close > candidate.high:
                self.pending = None
                return 'BUY', f'牛市回调底收复确认: {candidate.day} 高点{candidate.high:.4f}，收盘{close:.4f}'
            if close < candidate.low:
                self.pending = None
            return None, ''
        state = self.market.get(day)
        if pullback and state is not None and round(state[0], 8) < 0 and round(state[1], 8) < 0:
            self.pending = Pullback(day, row['high_price'], row['low_price'])
            return None, ''
        return action, reason


def evaluate_kc50(backend, rows, market, turnover, margin):
    """对已核验的固定原函数装配空仓接缝，持仓及退出继续调用原判断。"""
    from base.analysis.strategy import kc50

    relative = 'backend/base/analysis/strategy/kc50.py'
    path = backend.parent / relative
    raw = path.read_bytes()
    manifest = json.loads(Path(__file__).with_name('source_manifest.json').read_bytes())
    if hashlib.sha256(raw).hexdigest() != manifest['files'][relative] or Path(kc50.__file__).resolve() != path.resolve():
        raise ValueError('科创50原规则来源失配')
    tree = ast.parse(raw.decode('utf8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run_kc50_strategy')
    original = ast.parse('if position == 0 and buy_candidate == "BUY":\n    action, reason = buy_candidate, buy_reason').body[0]
    replacement = ast.parse('if position == 0:\n    action, reason = decide_entry(row, buy_candidate, buy_reason)').body[0]
    matches = [
        (loop, index, node) for loop in function.body if isinstance(loop, ast.For)
        for index, node in enumerate(loop.body) if ast.dump(node) == ast.dump(original)
    ]
    if len(matches) != 1:
        raise ValueError('科创50空仓分支结构失配')
    loop, index, node = matches[0]
    loop.body[index] = ast.copy_location(replacement, node)
    controller = PullbackConfirmation(market)
    namespace = dict(vars(kc50), decide_entry=controller.decide)
    adapted = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(adapted, str(path), 'exec'), namespace)
    prepared = [dict(row, _tp=turnover.get(row['date'], {}).get('percentile'),
                     _mp=margin.get(row['date'], {}).get('percentile')) for row in rows]
    return namespace['run_kc50_strategy'](prepared)
