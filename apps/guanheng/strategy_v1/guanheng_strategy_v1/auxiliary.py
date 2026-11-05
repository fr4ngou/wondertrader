"""共振策略辅助事实的纯派生与合并，沿原causal-v3公式和生效规则。

外部采集负责真实发布时间与来源摘要；本模块不联网、不推定历史发布时间，
不读账户或产生委托。份额单位亿份，全市场成交额和融资余额单位亿元。
"""
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
from math import isfinite
from statistics import fmean

from guanheng_strategy_core.models import DailyObservation, observation_close_at

DERIVATION_VERSION = 'resonance-auxiliary-causal-v3'
PERCENTILE_WINDOW = 60
PERCENTILE_MIN_POINTS = 20
TURNOVER_MEAN_WINDOW = 5


@dataclass(frozen=True, slots=True)
class AuxiliaryPublication:
    """某一统计日的外部事实；采集时刻与可获知时刻各自保留。"""
    kind: str  # shares为ETF总份额，turnover为沪深股票成交额，margin为沪深融资余额。
    statistic_date: date  # 来源统计日，区别于随后能够用于策略的生效交易日。
    value: float  # shares单位亿份；turnover/margin单位亿元，均为有限正数。
    available_at: datetime  # 有来源依据的可获知时刻，带时区；本模块不由统计日推算。
    received_at: datetime  # 本系统实际取得原文的时刻，带时区；不回填为历史采集时间。
    source_sha256: str  # 来源原文的SHA256；多个原文先由采集方形成完整来源清单摘要。
    symbol: str | None = None  # shares所属证券；市场汇总的turnover/margin为空。


@dataclass(frozen=True, slots=True)
class _Value:
    statistic_date: date  # 本派生量对应的最新来源统计日。
    available_at: datetime  # 所有依赖项均已可获知的最晚时刻。
    value: float  # 对应输出字段的数值，单位由字段定义。
    source_dates: tuple[date, ...]  # 全部依赖统计日，最多64个，不含未来日。
    sources: tuple[str, ...]  # 全部依赖原文摘要，用于派生事实身份。


def share_probability_from_delta_pct(value):
    """沿原份额变化百分比映射到0..100刻度，阈值等号保持原定义。"""
    if value > 10:
        return 95.
    if value > 5:
        return 80.+(value-5.)/5.*15.
    if value > 3:
        return 65.+(value-3.)/2.*15.
    if value > 1:
        return 45.+(value-1.)/2.*20.
    if value > 0:
        return 30.+value*15.
    if value > -1:
        return 15.+(value+1.)*15.
    if value > -5:
        return 5.+(value+5.)/4.*10.
    return max(0., 5.+(value+5.)/5.*5.)


def _validate(publications, symbols):
    seen = set()
    for item in publications:
        if (type(item) is not AuxiliaryPublication or item.kind not in ('shares', 'turnover', 'margin')
                or type(item.statistic_date) is not date or type(item.value) not in (int, float)
                or not isfinite(item.value) or item.value <= 0
                or type(item.available_at) is not datetime or item.available_at.utcoffset() is None
                or type(item.received_at) is not datetime or item.received_at.utcoffset() is None
                or item.available_at > item.received_at
                or item.available_at.astimezone(observation_close_at(item.statistic_date).tzinfo).date() < item.statistic_date
                or type(item.source_sha256) is not str or len(item.source_sha256) != 64
                or any(c not in '0123456789abcdef' for c in item.source_sha256)
                or (item.symbol not in symbols if item.kind == 'shares' else item.symbol is not None)):
            raise ValueError('invalid_auxiliary_publication')
        key = (item.kind, item.symbol, item.statistic_date)
        if key in seen:
            raise ValueError('duplicate_auxiliary_publication')
        seen.add(key)


def _value(item, value, dependencies):
    if not isfinite(value):
        raise ValueError('auxiliary_derived_not_finite')
    return _Value(item.statistic_date, max(p.available_at for p in dependencies), value,
                  tuple(sorted({p.statistic_date for p in dependencies})),
                  tuple(sorted({p.source_sha256 for p in dependencies})))


def _percentiles(publications, smoothing):
    """全历史前缀的5日均值/原余额，使用最多60点、至少20点的midrank分位。"""
    ordered = sorted(publications, key=lambda p: p.statistic_date)
    smoothed, result = [], []
    for index, item in enumerate(ordered):
        # 原规则在不足完整5日时使用当日值；保持公式，不提前做短均值。
        smoothed.append(item.value if index+1 < smoothing else
                        fmean(p.value for p in ordered[index-smoothing+1:index+1]))
        window = smoothed[max(0, index-PERCENTILE_WINDOW+1):index+1]
        if len(window) < PERCENTILE_MIN_POINTS:
            continue
        percentile = (sum(v < smoothed[index] for v in window)
                      + .5*sum(v == smoothed[index] for v in window))/len(window)*100.
        dependencies = ordered[max(0, index-PERCENTILE_WINDOW-smoothing+2):index+1]
        result.append(_value(item, percentile, dependencies))
    return result


def _effective(values, days):
    """每个派生值只分配到首个已经可获知的交易日；保持原一日一次生效规则。"""
    closes = [observation_close_at(day) for day in days]
    selected = {}
    for value in sorted(values, key=lambda v: (v.available_at, v.statistic_date)):
        index = bisect_left(closes, value.available_at)
        while index < len(days) and days[index] < value.statistic_date:
            index += 1
        if index == len(days):
            continue
        day = days[index]
        previous = selected.get(day)
        if previous is None or (value.statistic_date, value.available_at) > (previous.statistic_date, previous.available_at):
            selected[day] = value
    return selected


def merge_auxiliary(observations, publications):
    """返回新的DailyObservation序列；行情值保持，缺失值保持None。

    参数为同一来源快照的完整行情与辅助前缀。辅助按原统计日去重，归入首次
    可获知的策略收盘；调用者提供更早的行情时可保留预热。无辅助的行维持原值，
    已有同名辅助事实要求一致，冲突交事实所有者处理。
    """
    observations, publications = tuple(observations), tuple(publications)
    if not observations or len(observations) > 32768 or len(publications) > 65536:
        raise ValueError('auxiliary_capacity')
    dates, identities = defaultdict(set), set()
    for row in observations:
        if type(row) is not DailyObservation or (row.symbol, row.trade_date) in identities:
            raise ValueError('invalid_auxiliary_market_dates')
        identities.add((row.symbol, row.trade_date))
        dates[row.symbol].add(row.trade_date)
    dates = {symbol: sorted(days) for symbol, days in dates.items()}
    _validate(publications, set(dates))
    grouped = defaultdict(list)
    for item in publications:
        grouped[(item.kind, item.symbol)].append(item)
    facts = defaultdict(dict)
    for (kind, symbol), values in grouped.items():
        if kind != 'shares':
            field = 'turnover_percentile' if kind == 'turnover' else 'margin_percentile'
            for day, value in _effective(_percentiles(values, TURNOVER_MEAN_WINDOW if kind == 'turnover' else 1),
                                         dates.get('510300.SH', [])).items():
                facts[('510300.SH', day)][field] = value
            continue
        ordered = sorted(values, key=lambda p: p.statistic_date)
        deltas, probabilities = [], []
        for previous, current in zip(ordered, ordered[1:]):
            # 份额原文为十进制，先精确求差再交原浮点信号机，保护5/10亿份阈值。
            delta = float(Decimal(str(current.value))-Decimal(str(previous.value)))
            dependencies = (previous, current)
            deltas.append(_value(current, delta, dependencies))
            probabilities.append(_value(current, share_probability_from_delta_pct(delta/previous.value*100.), dependencies))
        for field, values in [('shares_delta_yi', deltas), ('share_probability', probabilities)]:
            for day, value in _effective(values, dates[symbol]).items():
                facts[(symbol, day)][field] = value
    result = []
    for row in observations:
        values = facts.get((row.symbol, row.trade_date))
        if not values:
            result.append(row)
            continue
        if any(getattr(row, field) is not None for field in
               ('shares_delta_yi', 'share_probability', 'turnover_percentile', 'margin_percentile')):
            raise ValueError('auxiliary_input_already_enriched')
        source_dates = tuple(sorted({day for value in values.values() for day in value.source_dates}))
        payload = {field: dict(value=value.value, sources=value.sources,
                              dates=[str(d) for d in value.source_dates], available_at=value.available_at.isoformat())
                   for field, value in values.items()}
        digest = sha256(json.dumps(dict(derivation=DERIVATION_VERSION, fields=payload),
                                   sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        result.append(replace(row, **{field: value.value for field, value in values.items()},
            auxiliary_available_at=max(value.available_at for value in values.values()),
            auxiliary_source_dates=source_dates, auxiliary_source_sha256=digest,
            evidence_refs=tuple(dict.fromkeys(row.evidence_refs+('auxiliary:'+digest,)))))
    return tuple(result)
