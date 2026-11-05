"""共振策略辅助事实的纯派生与合并，沿原causal-v3公式和生效规则。

外部采集负责真实发布时间与来源摘要；本模块不联网、不推定历史发布时间，
不读账户或产生委托。份额单位亿份，全市场成交额和融资余额单位亿元。
"""
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from decimal import Decimal
from hashlib import sha256
import json
from math import isfinite
from statistics import fmean
from zoneinfo import ZoneInfo
from typing import TypedDict

from guanheng_strategy_core.models import DailyObservation, observation_close_at

DERIVATION_VERSION = 'resonance-auxiliary-causal-v3'
PERCENTILE_WINDOW = 60
PERCENTILE_MIN_POINTS = 20
TURNOVER_MEAN_WINDOW = 5
RESEARCH_MODEL = 'research-next-common-session-0925-v1'
RESEARCH_EVIDENCE = 'auxiliary-research:' + RESEARCH_MODEL


class FieldCoverage(TypedDict):
    """来源派生能力和实际行生效分别报告，策略必需字段由策略诊断所有者确定。"""
    market_rows: int  # 当前证券实际行情行数，包含未富集的历史行。
    derived_points: int  # 原公式成功派生的统计日数，可能尚未到真实生效收盘。
    applied_rows: int  # 当前窗口实际带该字段的行情行数。
    last_applied_date: str | None  # 最近实际生效的窗口交易日；没有则为空。
    last_statistic_date: str | None  # 最近成功派生使用的来源统计日；没有则为空。
    known_by: str | None  # 最近派生全部依赖均可知的带时区上界；未知历史采用真实实收。
    status: str  # applied、awaiting_real_close或source_or_warmup_missing。


class ResearchDeclaration(TypedDict):
    """显式历史研究身份；原实际时钟保持，实时消费者必须拒绝研究标记。"""
    schema: str  # 声明协议版本guanheng.auxiliary-research-declaration.v1。
    model: str  # 明确选择的研究时钟模型，默认实时入口不调用。
    evidence_marker: str  # 每条研究行的固定标记，含尚缺辅助的行。
    data_sha256: str  # 调用方核定的原始完整数据制品字节SHA256。
    derivation: str  # 唯一原公式的版本身份。
    derivation_sha256: str  # 调用方核定的实际派生代码字节SHA256。
    strategy_id: str  # 被研究的策略身份，不表示交易授权。
    strategy_version: str  # 被研究的策略版本，与数据/模型一起绑定。
    publications_sha256: str  # 所有统计值、原文摘要、真实和假设时钟的规范清单摘要。
    actual_first_received_at: str | None  # 全部原件的最早真实实收；没有原件为空。
    actual_last_received_at: str | None  # 全部原件的最晚真实实收；没有原件为空。
    historical_first_available: str  # 原文历史首次可知仍为unknown。
    modeled_publications: int  # 在实际行情中存在后继共同交易日的建模事实数量。
    historical_causal_qualified: bool  # 固定False，研究假设不证明历史因果可得性。
    realtime_qualified: bool  # 固定False，研究产物不进入实时执行。
    declaration_sha256: str  # 其他全部声明字段的sort_keys/compact JSON SHA256。


@dataclass(frozen=True, slots=True)
class AuxiliaryPublication:
    """某一统计日的外部事实；采集时刻与可获知时刻各自保留。"""
    kind: str  # shares为ETF总份额，turnover为沪深股票成交额，margin为沪深融资余额。
    statistic_date: date  # 来源统计日，区别于随后能够用于策略的生效交易日。
    value: float  # shares单位亿份；turnover/margin单位亿元，均为有限正数。
    available_at: datetime | None  # 有证据的来源可知时间；历史首次未知保留None，生效使用实收上界。
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
    if len(publications) > 65536:
        raise ValueError('auxiliary_capacity')
    seen = set()
    for item in publications:
        if (type(item) is not AuxiliaryPublication or item.kind not in ('shares', 'turnover', 'margin')
                or type(item.statistic_date) is not date or type(item.value) not in (int, float)
                or not isfinite(item.value) or item.value <= 0
                or type(item.received_at) is not datetime or item.received_at.utcoffset() is None
                or (item.available_at is not None and (type(item.available_at) is not datetime
                    or item.available_at.utcoffset() is None or item.available_at > item.received_at))
                or (item.available_at or item.received_at).astimezone(
                    observation_close_at(item.statistic_date).tzinfo).date() < item.statistic_date
                or type(item.source_sha256) is not str or len(item.source_sha256) != 64
                or any(c not in '0123456789abcdef' for c in item.source_sha256)
                or (item.symbol not in symbols if item.kind == 'shares' else item.symbol is not None)):
            raise ValueError('invalid_auxiliary_publication')
        key = (item.kind, item.symbol, item.statistic_date)
        if key in seen:
            raise ValueError('duplicate_auxiliary_publication')
        seen.add(key)


def _market_dates(observations):
    """合并、覆盖和研究共用实际有界行情日历，拒绝重复或伪造日期。"""
    if not observations or len(observations) > 32768:
        raise ValueError('auxiliary_capacity')
    dates, identities = defaultdict(set), set()
    for row in observations:
        if (type(row) is not DailyObservation or type(row.trade_date) is not date
                or (row.symbol, row.trade_date) in identities):
            raise ValueError('invalid_auxiliary_market_dates')
        identities.add((row.symbol, row.trade_date))
        dates[row.symbol].add(row.trade_date)
    return {symbol: sorted(days) for symbol, days in dates.items()}


def _value(item, value, dependencies):
    if not isfinite(value):
        raise ValueError('auxiliary_derived_not_finite')
    # 默认实时资格沿本系统真正收到的时刻；早于实收的来源发布时间不回填旧决策。
    return _Value(item.statistic_date, max(p.received_at for p in dependencies), value,
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


def _derived(publications, statistic_days):
    """每个派生字段只计算一次公式；实时合并、覆盖及研究共用此数学接缝。"""
    grouped = defaultdict(list)
    for item in publications:
        grouped[(item.kind, item.symbol)].append(item)
    result = {}
    day_index = {day: index for index, day in enumerate(statistic_days)}
    for (kind, symbol), values in grouped.items():
        if kind != 'shares':
            field = 'turnover_percentile' if kind == 'turnover' else 'margin_percentile'
            result[('510300.SH', field)] = _percentiles(values, TURNOVER_MEAN_WINDOW if kind == 'turnover' else 1)
            continue
        ordered = sorted(values, key=lambda p: p.statistic_date)
        deltas, probabilities = [], []
        for previous, current in zip(ordered, ordered[1:]):
            # 缺中间来源日时，多日累计差不能冒充单日净变化。
            if (previous.statistic_date not in day_index or current.statistic_date not in day_index
                    or day_index[current.statistic_date] != day_index[previous.statistic_date]+1):
                continue
            delta = float(Decimal(str(current.value))-Decimal(str(previous.value)))
            dependencies = (previous, current)
            deltas.append(_value(current, delta, dependencies))
            probabilities.append(_value(current, share_probability_from_delta_pct(delta/previous.value*100.), dependencies))
        result[(symbol, 'shares_delta_yi')] = deltas
        result[(symbol, 'share_probability')] = probabilities
    return result


def auxiliary_coverage(observations, publications):
    """原来源、已派生与已生效分别计数；不把预热数值计为历史已知事实。"""
    observations, publications = tuple(observations), tuple(publications)
    dates = _market_dates(observations)
    _validate(publications, set(dates))
    derived = _derived(publications, sorted({row.trade_date for row in observations}))
    result = {}
    for symbol in sorted({row.symbol for row in observations}):
        rows = [row for row in observations if row.symbol == symbol]
        result[symbol] = {}
        for field in ('shares_delta_yi', 'share_probability', 'turnover_percentile', 'margin_percentile'):
            values = derived.get((symbol, field), [])
            latest = max(values, key=lambda value: value.statistic_date) if values else None
            applied = [row for row in rows if getattr(row, field) is not None]
            result[symbol][field] = FieldCoverage(market_rows=len(rows), derived_points=len(values),
                applied_rows=len(applied), last_applied_date=str(applied[-1].trade_date) if applied else None,
                last_statistic_date=str(latest.statistic_date) if latest else None,
                known_by=latest.available_at.isoformat() if latest else None,
                status=('applied' if applied else 'awaiting_real_close' if latest else 'source_or_warmup_missing'))
    return result


def merge_auxiliary(observations, publications):
    """返回新的DailyObservation序列；行情值保持，缺失值保持None。

    参数为同一来源快照的完整行情与辅助前缀。辅助按原统计日去重，归入首次
    可获知的策略收盘；调用者提供更早的行情时可保留预热。无辅助的行维持原值，
    已有同名辅助事实要求一致，冲突交事实所有者处理。
    """
    observations, publications = tuple(observations), tuple(publications)
    dates = _market_dates(observations)
    _validate(publications, set(dates))
    facts = defaultdict(dict)
    for (symbol, field), values in _derived(publications, sorted({row.trade_date for row in observations})).items():
        for day, value in _effective(values, dates.get(symbol, [])).items():
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


def merge_auxiliary_research(observations, publications, *, data_sha256, derivation_sha256,
                             strategy_id, strategy_version):
    """显式研究入口：假设统计日后首个共同交易日09:25可知，原实际时钟保持。

    返回(研究行, 研究声明)。输出每条行带固定研究标记，供实时入口拒绝；
    没有下一实际共同交易日的事实不产生新行。声明绑定完整原件/实际时钟清单。
    本入口不联网，不改变传入publication，不提供历史因果实证资格。
    """
    observations, publications = tuple(observations), tuple(publications)
    dates = _market_dates(observations)
    _validate(publications, set(dates))
    if (any(type(value) is not str or len(value) != 64
                or any(c not in '0123456789abcdef' for c in value)
                for value in (data_sha256, derivation_sha256))
            or any(type(v) is not str or not 1 <= len(v) <= 128 for v in (strategy_id, strategy_version))):
        raise ValueError('invalid_auxiliary_research_identity')
    days = sorted(set.intersection(*(set(found) for found in dates.values())))
    modeled, ledger = [], []
    for item in publications:
        index = bisect_right(days, item.statistic_date)
        assumed = (datetime.combine(days[index], time(9, 25), tzinfo=ZoneInfo('Asia/Shanghai'))
                   if index < len(days) else None)
        ledger.append(dict(kind=item.kind, symbol=item.symbol, statistic_date=str(item.statistic_date),
            value=item.value, available_at=item.available_at.isoformat() if item.available_at else None,
            received_at=item.received_at.isoformat(), source_sha256=item.source_sha256,
            assumed_available_at=assumed.isoformat() if assumed else None))
        if assumed is not None:
            # 仅内部研究副本使用假设时钟；ledger及调用方对象保留全部真实时钟。
            modeled.append(replace(item, available_at=assumed, received_at=assumed))
    merged = merge_auxiliary(observations, modeled)
    result = tuple(replace(row, evidence_refs=tuple(dict.fromkeys(row.evidence_refs + (RESEARCH_EVIDENCE,))))
                   for row in merged)
    digest = lambda value: sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                            allow_nan=False).encode()).hexdigest()
    clocks = sorted(item.received_at.isoformat() for item in publications)
    declaration = ResearchDeclaration(schema='guanheng.auxiliary-research-declaration.v1', model=RESEARCH_MODEL,
        evidence_marker=RESEARCH_EVIDENCE, data_sha256=data_sha256,
        derivation=DERIVATION_VERSION, derivation_sha256=derivation_sha256,
        strategy_id=strategy_id, strategy_version=strategy_version,
        publications_sha256=digest(sorted(ledger, key=lambda value: (
            value['kind'], value['symbol'] or '', value['statistic_date']))),
        actual_first_received_at=clocks[0] if clocks else None,
        actual_last_received_at=clocks[-1] if clocks else None,
        historical_first_available='unknown', modeled_publications=len(modeled),
        historical_causal_qualified=False, realtime_qualified=False)
    declaration['declaration_sha256'] = digest(declaration)
    return result, declaration
