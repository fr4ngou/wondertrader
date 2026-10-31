"""Versioned pure signal state machines for resonance-regime-v1."""

from __future__ import annotations

from math import ceil

from .features import resonance_lights
from .models import DailyFeature, ResonanceDecision
from .numerics import add, product
from .computation import checked


RESONANCE_VERDICT_N = 3
CSI300_TRANCHES = 3


def _count_direction(
    features: list[DailyFeature], index: int, direction: str, window: int
) -> int:
    return sum(
        item.trade_direction == direction
        for item in features[max(0, index - window + 1) : index + 1]
    )


def _days_since_high(features: list[DailyFeature], index: int, window: int) -> int:
    rows = features[max(0, index - window + 1) : index + 1]
    high = max(item.observation.close for item in rows)
    for offset, item in enumerate(reversed(rows)):
        if item.observation.close == high:
            return offset
    return window


def _recent_direction(
    features: list[DailyFeature], index: int, direction: str, window: int
) -> bool:
    return any(
        item.trade_direction == direction
        for item in features[max(0, index - window) : index]
    )


def _sell_threshold(feature: DailyFeature) -> int:
    ratio = feature.volume_ratio if feature.volume_ratio is not None else 1.0
    return max(2, ceil(add(2.0, product(ratio, 0.55))))


def _decision(
    feature: DailyFeature,
    *,
    action: str,
    strength: float,
    path: str,
    reason: str,
    confidence: float,
) -> ResonanceDecision:
    return ResonanceDecision(
        symbol=feature.observation.symbol.upper(),
        trade_date=feature.observation.trade_date,
        action=action,
        strength=strength,
        path=path,
        reason=reason,
        confidence=max(0.0, min(1.0, confidence)),
        evidence_refs=feature.observation.evidence_refs,
    )


def run_csi300_resonance(features: list[DailyFeature], *, symbol="510300.SH", state=None, state_out=None, start_index=0, check=None) -> list[ResonanceDecision]:
    """Apply five-lamp resonance and move one of three internal tranches at a time."""

    level = (state or {}).get('level', 0)
    decisions: list[ResonanceDecision] = []
    for feature in checked(features[start_index:], check):
        if feature.observation.symbol.upper() != symbol:
            raise ValueError("CSI300 resonance accepts only 510300.SH")
        lights = resonance_lights(feature)
        action = "HOLD"
        path = "neutral"
        previous_level = level
        if lights.green_count >= RESONANCE_VERDICT_N and level < CSI300_TRANCHES:
            level += 1
            action = "BUY"
            path = "opportunity_resonance"
        elif lights.red_count >= RESONANCE_VERDICT_N and level > 0:
            level -= 1
            action = "SELL"
            path = "danger_resonance"
        if level == previous_level:
            continue
        evidence = tuple(
            dict.fromkeys(
                feature.observation.evidence_refs
                + (
                    "resonance-lights:{0}:{1}".format(
                        lights.green_count,
                        lights.red_count,
                    ),
                )
            )
        )
        decisions.append(
            ResonanceDecision(
                symbol=symbol,
                trade_date=feature.observation.trade_date,
                action=action,
                strength=level / CSI300_TRANCHES,
                path=path,
                reason=(
                    "opportunity resonance adds one of three tranches"
                    if action == "BUY"
                    else "danger resonance removes one of three tranches"
                ),
                confidence=max(lights.green_count, lights.red_count) / 5.0,
                evidence_refs=evidence,
            )
        )
    if state_out is not None:
        state_out.update({'level': level})
    return decisions


def run_sh50_swing(features: list[DailyFeature], *, symbol="510050.SH", state=None, state_out=None, start_index=0, boundary_override=None, check=None) -> list[ResonanceDecision]:
    """510050 panic/low accumulation entries and two explicit exits."""

    position = (state or {}).get('position', False)
    hold_days = (state or {}).get('hold_days', 0)
    peak = (state or {}).get('peak', 0.0)
    waiting_cluster = (state or {}).get('waiting_cluster', False)
    cluster_low: float | None = (state or {}).get('cluster_low', None)
    decisions: list[ResonanceDecision] = []
    boundary = boundary_override
    for index in checked(range(start_index, len(features)), check):
        feature = features[index]
        if feature.observation.symbol.upper() != symbol:
            raise ValueError("SH50 swing accepts only 510050.SH")
        row = feature.observation
        pp = feature.price_position
        change = feature.change_pct
        ratio = feature.volume_ratio
        shares = row.shares_delta_yi
        accumulations = _count_direction(features, index, "ACCUMULATE", 10)
        days_high = _days_since_high(features, index, 30)
        if boundary is not None and boundary[1] is not None and index >= boundary[1]:
            position = True
            hold_days = index - boundary[0] - 1  # the existing held branch increments once
            peak = row.close if index == boundary[1] else max(peak, row.close)
        if not position:
            path = None
            if (
                feature.trade_direction == "ACCUMULATE"
                and shares is not None
                and shares > 0
                and accumulations < 2
            ):
                if change is not None and change <= -5 and pp is not None and pp <= 30:
                    path = "sh50_panic"
                elif (
                    pp is not None
                    and pp <= 10
                    and change is not None
                    and change <= -2
                    and days_high >= 12
                ):
                    path = "sh50_extreme_low"
                elif pp is not None and pp <= 40 and (
                    days_high >= 12 or shares >= 10
                ):
                    path = "sh50_low_accumulation"
            if path is None and accumulations >= 2:
                waiting_cluster = True
                cluster_low = min(
                    item.observation.close
                    for item in features[max(0, index - 9) : index + 1]
                )
            if waiting_cluster and cluster_low is not None:
                if row.close < cluster_low:
                    waiting_cluster = False
                    cluster_low = None
                elif (
                    change is not None
                    and change >= 2
                    and ratio is not None
                    and ratio >= 1.2
                    and pp is not None
                    and pp <= 45
                    and shares is not None
                    and shares > 0
                ):
                    path = "sh50_cluster_reversal"
                    waiting_cluster = False
                    cluster_low = None
            if path is not None:
                position = True
                hold_days = 0
                peak = row.close
                decisions.append(
                    _decision(
                        feature,
                        action="BUY",
                        strength=1.0,
                        path=path,
                        reason="reviewed SH50 entry condition",
                        confidence=0.7,
                    )
                )
            continue
        hold_days += 1
        peak = max(peak, row.close)
        path = None
        if (
            hold_days >= 10
            and shares is not None
            and shares <= -10
            and pp is not None
            and pp >= 60
        ):
            path = "sh50_large_redemption"
        elif hold_days >= 10 and row.close < product(peak, 0.95):
            path = "sh50_trailing_exit"
        if path is not None:
            position = False
            decisions.append(
                _decision(
                    feature,
                    action="SELL",
                    strength=0.0,
                    path=path,
                    reason="reviewed SH50 exit condition",
                    confidence=0.8,
                )
            )
    if state_out is not None:
        state_out.update({'position': position, 'hold_days': hold_days, 'peak': peak, 'waiting_cluster': waiting_cluster, 'cluster_low': cluster_low})
    return decisions


def run_kc50_swing(features: list[DailyFeature], *, symbol="588000.SH", state=None, state_out=None, start_index=0, boundary_override=None, check=None) -> list[ResonanceDecision]:
    """588000 share-confirmed low entries with an eight-percent trailing exit."""

    position = (state or {}).get('position', False)
    hold_days = (state or {}).get('hold_days', 0)
    peak = (state or {}).get('peak', 0.0)
    decisions: list[ResonanceDecision] = []
    boundary = boundary_override
    for index in checked(range(start_index, len(features)), check):
        feature = features[index]
        if feature.observation.symbol.upper() != symbol:
            raise ValueError("KC50 swing accepts only 588000.SH")
        row = feature.observation
        pp = feature.price_position
        change = feature.change_pct
        shares = row.shares_delta_yi
        if boundary is not None and boundary[1] is not None and index >= boundary[1]:
            position = True
            hold_days = index - boundary[0] - 1  # the existing held branch increments once
            peak = row.close if index == boundary[1] else max(peak, row.close)
        if not position:
            path = None
            if feature.trade_direction == "ACCUMULATE" and shares is not None and shares > 0:
                if change is not None and change <= -6 and pp is not None and pp <= 30:
                    path = "kc50_panic"
                elif pp is not None and pp <= 30 and _days_since_high(features, index, 30) >= 15:
                    path = "kc50_low_accumulation"
            if path is not None:
                position = True
                hold_days = 0
                peak = row.close
                decisions.append(
                    _decision(
                        feature,
                        action="BUY",
                        strength=1.0,
                        path=path,
                        reason="share-confirmed KC50 entry",
                        confidence=0.75,
                    )
                )
            continue
        hold_days += 1
        peak = max(peak, row.close)
        exempt = shares is not None and shares >= 5
        if hold_days >= 10 and row.close < product(peak, 0.92) and not exempt:
            position = False
            decisions.append(
                _decision(
                    feature,
                    action="SELL",
                    strength=0.0,
                    path="kc50_trailing_exit",
                    reason="eight-percent trailing exit without large subscription exemption",
                    confidence=0.8,
                )
            )
    if state_out is not None:
        state_out.update({'position': position, 'hold_days': hold_days, 'peak': peak})
    return decisions


def run_sc50_swing(features: list[DailyFeature], *, symbol="159780.SZ", state=None, state_out=None, start_index=0, boundary_override=None, check=None) -> list[ResonanceDecision]:
    """159780 panic, low, launch and cluster-reversal entries."""

    position = (state or {}).get('position', False)
    hold_days = (state or {}).get('hold_days', 0)
    peak = (state or {}).get('peak', 0.0)
    waiting_cluster = (state or {}).get('waiting_cluster', False)
    cluster_low: float | None = (state or {}).get('cluster_low', None)
    decisions: list[ResonanceDecision] = []
    boundary = boundary_override
    for index in checked(range(start_index, len(features)), check):
        feature = features[index]
        if feature.observation.symbol.upper() != symbol:
            raise ValueError("SC50 swing accepts only 159780.SZ")
        row = feature.observation
        pp = feature.price_position
        change = feature.change_pct
        ratio = feature.volume_ratio
        accumulations = _count_direction(features, index, "ACCUMULATE", 10)
        if boundary is not None and boundary[1] is not None and index >= boundary[1]:
            position = True
            hold_days = index - boundary[0] - 1  # the existing held branch increments once
            peak = row.close if index == boundary[1] else max(peak, row.close)
        if not position:
            path = None
            prior = features[max(0, index - 20) : index]
            prior_low = min((item.observation.close for item in prior), default=row.close)
            recent_extreme = any(
                item.price_position is not None and item.price_position <= 15
                for item in prior
            )
            if (
                feature.trade_direction == "ACCUMULATE"
                and change is not None
                and change <= -9
                and pp is not None
                and pp <= 20
                and accumulations < 3
            ):
                path = "sc50_panic"
            elif (
                feature.trade_direction == "ACCUMULATE"
                and pp is not None
                and pp <= 40
                and _days_since_high(features, index, 30) >= 15
                and row.close > prior_low
            ):
                path = "sc50_low_accumulation"
            elif (
                ratio is not None
                and ratio >= 2
                and change is not None
                and change >= 4
                and pp is not None
                and pp <= 75
                and recent_extreme
            ):
                path = "sc50_volume_launch"
            elif accumulations >= 3:
                waiting_cluster = True
                cluster_low = min(
                    item.observation.close
                    for item in features[max(0, index - 9) : index + 1]
                )
            if waiting_cluster and cluster_low is not None:
                if row.close < cluster_low:
                    waiting_cluster = False
                    cluster_low = None
                elif (
                    change is not None
                    and change >= 2
                    and ratio is not None
                    and ratio >= 1.2
                    and pp is not None
                    and pp <= 45
                ):
                    path = "sc50_cluster_reversal"
                    waiting_cluster = False
                    cluster_low = None
            if path is not None:
                position = True
                hold_days = 0
                peak = row.close
                decisions.append(
                    _decision(
                        feature,
                        action="BUY",
                        strength=1.0,
                        path=path,
                        reason="reviewed SC50 entry condition",
                        confidence=0.7,
                    )
                )
            continue
        hold_days += 1
        peak = max(peak, row.close)
        if hold_days >= 10 and row.close < product(peak, 0.90):
            position = False
            decisions.append(
                _decision(
                    feature,
                    action="SELL",
                    strength=0.0,
                    path="sc50_trailing_exit",
                    reason="ten-percent trailing exit",
                    confidence=0.8,
                )
            )
    if state_out is not None:
        state_out.update({'position': position, 'hold_days': hold_days, 'peak': peak, 'waiting_cluster': waiting_cluster, 'cluster_low': cluster_low})
    return decisions


def run_kc_composite_swing(features: list[DailyFeature], *, symbol=None, state=None, state_out=None, start_index=0, boundary_override=None, check=None) -> list[ResonanceDecision]:
    """KC composite low/panic entries, cluster reversal, and distribution exit."""

    position = (state or {}).get('position', False)
    hold_days = (state or {}).get('hold_days', 0)
    waiting_cluster = (state or {}).get('waiting_cluster', False)
    cluster_low: float | None = (state or {}).get('cluster_low', None)
    decisions: list[ResonanceDecision] = []
    boundary = boundary_override
    for index in checked(range(start_index, len(features)), check):
        feature = features[index]
        if feature.observation.symbol.upper() not in ({symbol} if symbol is not None else {"589680.SH", "589000.SH"}):
            raise ValueError("KC composite swing accepts only reviewed KC ETFs")
        row = feature.observation
        pp = feature.price_position
        change = feature.change_pct
        ratio = feature.volume_ratio
        shares = row.shares_delta_yi
        accumulations = _count_direction(features, index, "ACCUMULATE", 10)
        if boundary is not None and boundary[1] is not None and index >= boundary[1]:
            position = True
            hold_days = index - boundary[0] - 1  # the existing held branch increments once
        if not position:
            path = None
            if (
                feature.trade_direction == "ACCUMULATE"
                and change is not None
                and change <= -10
                and pp is not None
                and pp <= 40
                and accumulations < 2
            ):
                path = "kc_panic"
            elif (
                feature.trade_direction == "ACCUMULATE"
                and pp is not None
                and pp <= 35
                and accumulations < 2
                and _days_since_high(features, index, 60) >= 15
            ):
                path = "kc_low_accumulation"
            elif (
                index >= 59
                and pp is not None
                and pp <= 15
                and accumulations < 2
                and ratio is not None
                and ratio < 1.0
            ):
                path = "kc_extreme_low_volume"
            elif accumulations >= 2:
                waiting_cluster = True
                cluster_low = min(
                    item.observation.close
                    for item in features[max(0, index - 9) : index + 1]
                )
            if waiting_cluster and cluster_low is not None:
                if row.close < cluster_low:
                    waiting_cluster = False
                    cluster_low = None
                elif (
                    change is not None
                    and change >= 2
                    and ratio is not None
                    and ratio >= 1.2
                    and pp is not None
                    and pp <= 45
                    and shares is not None
                    and shares > 0
                ):
                    path = "kc_cluster_reversal"
                    waiting_cluster = False
                    cluster_low = None
            if path is not None:
                position = True
                hold_days = 0
                decisions.append(
                    _decision(
                        feature,
                        action="BUY",
                        strength=1.0,
                        path=path,
                        reason="reviewed KC composite entry condition",
                        confidence=0.7,
                    )
                )
            continue
        hold_days += 1
        distributions = _count_direction(features, index, "DISTRIBUTE", 10)
        if (
            hold_days >= 10
            and feature.trade_direction == "DISTRIBUTE"
            and distributions >= 2
            and shares is not None
            and shares < 0
        ):
            position = False
            decisions.append(
                _decision(
                    feature,
                    action="SELL",
                    strength=0.0,
                    path="kc_distribution_cluster",
                    reason="distribution cluster confirmed by share outflow",
                    confidence=0.8,
                )
            )
    if state_out is not None:
        state_out.update({'position': position, 'hold_days': hold_days, 'waiting_cluster': waiting_cluster, 'cluster_low': cluster_low})
    return decisions


def run_zz500_trend(features: list[DailyFeature], *, symbol="510500.SH", state=None, state_out=None, start_index=0, boundary_override=None, check=None) -> list[ResonanceDecision]:
    """510500 right-side trend state machine with a three-day top watch."""

    position = (state or {}).get('position', False)
    hold_days = (state or {}).get('hold_days', 0)
    waiting_cluster = (state or {}).get('waiting_cluster', False)
    cluster_low: float | None = (state or {}).get('cluster_low', None)
    distribution_count = (state or {}).get('distribution_count', 0)
    sell_threshold = (state or {}).get('sell_threshold', 2)
    top_watch = (state or {}).get('top_watch', 0)
    decisions: list[ResonanceDecision] = []
    boundary = boundary_override
    for index in checked(range(start_index, len(features)), check):
        feature = features[index]
        if feature.observation.symbol.upper() != symbol:
            raise ValueError("ZZ500 trend accepts only 510500.SH")
        row = feature.observation
        pp = feature.price_position
        change = feature.change_pct
        ratio = feature.volume_ratio
        shares = row.shares_delta_yi
        accumulations = _count_direction(features, index, "ACCUMULATE", 10)
        if boundary is not None and boundary[1] is not None and index >= boundary[1]:
            position = True
            hold_days = index - boundary[0] - 1  # the existing held branch increments once
            if index == boundary[1]:
                distribution_count = 0
                sell_threshold = _sell_threshold(feature)
                top_watch = 0
        if not position:
            path = None
            if (
                feature.trade_direction == "ACCUMULATE"
                and change is not None
                and change <= -5
                and pp is not None
                and pp <= 35
                and accumulations < 3
            ):
                path = "zz500_panic"
            elif (
                feature.trade_direction == "ACCUMULATE"
                and pp is not None
                and pp <= 35
                and accumulations < 3
                and _days_since_high(features, index, 60) >= 15
            ):
                path = "zz500_low_accumulation"
            elif accumulations >= 3:
                waiting_cluster = True
                cluster_low = min(
                    item.observation.close
                    for item in features[max(0, index - 9) : index + 1]
                )
            if waiting_cluster and cluster_low is not None:
                if row.close < cluster_low:
                    waiting_cluster = False
                    cluster_low = None
                elif (
                    change is not None
                    and change >= 2
                    and ratio is not None
                    and ratio >= 1.2
                    and pp is not None
                    and pp <= 45
                    and shares is not None
                    and shares > 0
                ):
                    path = "zz500_cluster_reversal"
                    waiting_cluster = False
                    cluster_low = None
            if path is not None:
                position = True
                hold_days = 0
                distribution_count = 0
                top_watch = 0
                sell_threshold = _sell_threshold(feature)
                decisions.append(
                    _decision(
                        feature,
                        action="BUY",
                        strength=1.0,
                        path=path,
                        reason="reviewed ZZ500 entry condition",
                        confidence=0.7,
                    )
                )
            continue
        hold_days += 1
        path = None
        if top_watch > 0:
            top_watch -= 1
            if change is not None and change >= 1 and ratio is not None and ratio >= 1.2:
                top_watch = 0
                distribution_count = 0
            elif top_watch == 0:
                path = "zz500_top_watch_exit"
        if (
            path is None
            and top_watch == 0
            and feature.trade_direction == "DISTRIBUTE"
            and pp is not None
            and pp >= 95
            and not _recent_direction(features, index, "DISTRIBUTE", 5)
        ):
            top_watch = 3
        if top_watch == 0 and path is None and feature.trade_direction == "DISTRIBUTE":
            if pp is not None and pp >= 85 and ratio is not None and ratio >= 1.5:
                distribution_count += 1
                if (
                    hold_days >= 5
                    and distribution_count >= sell_threshold
                    and shares is not None
                    and shares < 0
                ):
                    path = "zz500_distribution_cluster"
        if path is not None:
            position = False
            top_watch = 0
            decisions.append(
                _decision(
                    feature,
                    action="SELL",
                    strength=0.0,
                    path=path,
                    reason="reviewed ZZ500 distribution exit",
                    confidence=0.8,
                )
            )
    if state_out is not None:
        state_out.update({'position': position, 'hold_days': hold_days, 'waiting_cluster': waiting_cluster, 'cluster_low': cluster_low, 'distribution_count': distribution_count, 'sell_threshold': sell_threshold, 'top_watch': top_watch})
    return decisions


def run_zz1000_memory(features: list[DailyFeature], *, symbol="512100.SH", state=None, state_out=None, start_index=0, boundary_override=None, check=None) -> list[ResonanceDecision]:
    """512100 cluster reversal and distribution-memory state machine."""

    position = (state or {}).get('position', False)
    hold_days = (state or {}).get('hold_days', 0)
    waiting_cluster = (state or {}).get('waiting_cluster', False)
    distribution_count = (state or {}).get('distribution_count', 0)
    sell_threshold = (state or {}).get('sell_threshold', 2)
    watch_mode = (state or {}).get('watch_mode', False)
    watch_high = (state or {}).get('watch_high', 0.0)
    decisions: list[ResonanceDecision] = []
    boundary = boundary_override
    for index in checked(range(start_index, len(features)), check):
        feature = features[index]
        if feature.observation.symbol.upper() != symbol:
            raise ValueError("ZZ1000 memory accepts only 512100.SH")
        row = feature.observation
        pp = feature.price_position
        change = feature.change_pct
        ratio = feature.volume_ratio
        accumulations = _count_direction(features, index, "ACCUMULATE", 10)
        if boundary is not None and boundary[1] is not None and index >= boundary[1]:
            position = True
            hold_days = index - boundary[0] - 1  # the existing held branch increments once
            if index == boundary[1]:
                distribution_count = 0
                sell_threshold = _sell_threshold(feature)
                watch_mode = False
        if not position:
            path = None
            if (
                feature.trade_direction == "ACCUMULATE"
                and change is not None
                and change <= -5
            ):
                path = "zz1000_panic"
            elif accumulations >= 3:
                waiting_cluster = True
            if waiting_cluster and index > 0:
                previous_change = features[index - 1].change_pct
                cluster_ended = (
                    feature.trade_direction != "ACCUMULATE" or accumulations < 3
                )
                if (
                    cluster_ended
                    and change is not None
                    and change > 0
                    and previous_change is not None
                    and previous_change > 0
                    and ratio is not None
                    and ratio >= 1.0
                ):
                    path = "zz1000_two_day_reversal"
                    waiting_cluster = False
            if path is not None:
                position = True
                hold_days = 0
                distribution_count = 0
                watch_mode = False
                sell_threshold = _sell_threshold(feature)
                decisions.append(
                    _decision(
                        feature,
                        action="BUY",
                        strength=1.0,
                        path=path,
                        reason="reviewed ZZ1000 entry condition",
                        confidence=0.7,
                    )
                )
            continue
        hold_days += 1
        path = None
        if watch_mode:
            watch_high = max(watch_high, row.close)
            previous = features[max(0, index - 5) : index]
            previous_low = min(
                (item.observation.close for item in previous),
                default=row.close,
            )
            if row.close < previous_low:
                path = "zz1000_watch_break_low"
            elif pp is not None and pp < 60:
                path = "zz1000_watch_position_exit"
            elif row.close < product(watch_high, 0.96):
                path = "zz1000_watch_trailing_exit"
        if (
            not watch_mode
            and feature.trade_direction == "DISTRIBUTE"
            and pp is not None
            and pp >= 75
            and ratio is not None
            and ratio >= 1.3
        ):
            distribution_count += 1
            if hold_days >= 5 and distribution_count >= sell_threshold:
                if (change is not None and change >= 3) or ratio >= 4:
                    path = "zz1000_accelerating_top"
                else:
                    watch_mode = True
                    watch_high = row.close
        if path is not None:
            position = False
            watch_mode = False
            decisions.append(
                _decision(
                    feature,
                    action="SELL",
                    strength=0.0,
                    path=path,
                    reason="reviewed ZZ1000 distribution-memory exit",
                    confidence=0.8,
                )
            )
    if state_out is not None:
        state_out.update({'position': position, 'hold_days': hold_days, 'waiting_cluster': waiting_cluster, 'distribution_count': distribution_count, 'sell_threshold': sell_threshold, 'watch_mode': watch_mode, 'watch_high': watch_high})
    return decisions


def run_dividend_memory(features: list[DailyFeature], *, symbol="515080.SH", state=None, state_out=None, start_index=0, boundary_override=None, check=None) -> list[ResonanceDecision]:
    """515080 oversold detection, right-side entry and distribution exit."""

    position = (state or {}).get('position', False)
    hold_days = (state or {}).get('hold_days', 0)
    waiting_reversal = (state or {}).get('waiting_reversal', False)
    distribution_count = (state or {}).get('distribution_count', 0)
    sell_threshold = (state or {}).get('sell_threshold', 2)
    decisions: list[ResonanceDecision] = []
    boundary = boundary_override
    for index in checked(range(start_index, len(features)), check):
        feature = features[index]
        if feature.observation.symbol.upper() != symbol:
            raise ValueError("dividend memory accepts only 515080.SH")
        pp = feature.price_position
        change = feature.change_pct
        ratio = feature.volume_ratio
        accumulations = _count_direction(features, index, "ACCUMULATE", 10)
        if boundary is not None and boundary[1] is not None and index >= boundary[1]:
            position = True
            hold_days = index - boundary[0] - 1  # the existing held branch increments once
            if index == boundary[1]:
                distribution_count = 0
                sell_threshold = _sell_threshold(feature)
        if not position:
            path = None
            if (
                feature.trade_direction == "ACCUMULATE"
                and change is not None
                and change <= -5
                and pp is not None
                and pp <= 25
            ):
                path = "dividend_systemic_crisis"
            elif accumulations >= 2 and pp is not None and pp <= 25:
                waiting_reversal = True
            if waiting_reversal:
                previous_change = features[index - 1].change_pct if index > 0 else None
                two_day = (
                    change is not None
                    and change > 0
                    and previous_change is not None
                    and previous_change > 0
                    and ratio is not None
                    and ratio >= 1.0
                )
                strong = (
                    change is not None
                    and change > 2
                    and ratio is not None
                    and ratio > 1.2
                    and pp is not None
                    and pp <= 40
                )
                if two_day or strong:
                    path = "dividend_right_side_reversal"
                    waiting_reversal = False
            if path is not None:
                position = True
                hold_days = 0
                distribution_count = 0
                sell_threshold = _sell_threshold(feature)
                decisions.append(
                    _decision(
                        feature,
                        action="BUY",
                        strength=1.0,
                        path=path,
                        reason="reviewed dividend ETF entry condition",
                        confidence=0.7,
                    )
                )
            continue
        hold_days += 1
        if (
            feature.trade_direction == "DISTRIBUTE"
            and pp is not None
            and pp >= 75
            and ratio is not None
            and ratio >= 1.3
        ):
            distribution_count += 1
            if hold_days >= 8 and distribution_count >= sell_threshold:
                position = False
                decisions.append(
                    _decision(
                        feature,
                        action="SELL",
                        strength=0.0,
                        path="dividend_distribution_cluster",
                        reason="distribution cluster confirms mean-reversion exit",
                        confidence=0.8,
                    )
                )
    if state_out is not None:
        state_out.update({'position': position, 'hold_days': hold_days, 'waiting_reversal': waiting_reversal, 'distribution_count': distribution_count, 'sell_threshold': sell_threshold})
    return decisions


def run_signal_machines(
    features_by_symbol: dict[str, list[DailyFeature]], *, check=None,
) -> dict[str, list[ResonanceDecision]]:
    """Run the exact reviewed machine for every provided supported symbol."""

    machines = {
        "510300.SH": run_csi300_resonance,
        "510050.SH": run_sh50_swing,
        "510500.SH": run_zz500_trend,
        "512100.SH": run_zz1000_memory,
        "588000.SH": run_kc50_swing,
        "589680.SH": run_kc_composite_swing,
        "589000.SH": run_kc_composite_swing,
        "159780.SZ": run_sc50_swing,
        "515080.SH": run_dividend_memory,
    }
    unknown = sorted(set(features_by_symbol) - set(machines))
    if unknown:
        raise ValueError("unsupported resonance feature symbols: {0}".format(unknown))
    return {
        symbol: machines[symbol](features_by_symbol[symbol], check=check)
        for symbol in checked(sorted(features_by_symbol), check)
    }




ROLE_SIGNAL_MACHINES = {
    "csi300": run_csi300_resonance, "sh50": run_sh50_swing,
    "zz500": run_zz500_trend, "zz1000": run_zz1000_memory,
    "kc50": run_kc50_swing, "kc_composite": run_kc_composite_swing,
    "sc50": run_sc50_swing, "dividend": run_dividend_memory,
}


def run_role_signal_machines(features_by_symbol, symbol_roles, *, check=None):
    """Apply declared algorithm roles without inferring roles from securities."""
    if set(symbol_roles) - set(ROLE_SIGNAL_MACHINES):
        raise ValueError("unsupported signal role")
    if set(features_by_symbol) != set(symbol_roles.values()):
        raise ValueError("feature universe differs from declared roles")
    return {symbol: ROLE_SIGNAL_MACHINES[role](features_by_symbol[symbol], symbol=symbol, check=check)
            for role, symbol in checked(sorted(symbol_roles.items()), check)}
