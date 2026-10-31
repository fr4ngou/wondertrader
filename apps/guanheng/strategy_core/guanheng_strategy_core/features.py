"""Pure closed-day factor calculations for resonance-regime-v1."""

from __future__ import annotations

from collections import defaultdict

from .models import (
    DailyFeature,
    DailyObservation,
    Lamp,
    ResonanceLights,
    validate_observations,
)
from .numerics import add, finite, positive_mean, product, ratio, subtract
from .computation import checked


POSITION_WINDOW = 60
VOLUME_WINDOW = 20
REGIME_MA_PERIOD = 100
REGIME_EMA_SMOOTH = 20
VOLUME_ACTIVE_RATIO = 1.5


def _price_position(window: list[DailyObservation], period=POSITION_WINDOW, *, check=None) -> float | None:
    if len(window) < period:
        return None
    low = min(item.low for item in checked(window, check, interval=32))
    high = max(item.high for item in checked(window, check, interval=32))
    if high <= low:
        return 50.0
    return max(0.0, min(100.0, product(ratio(subtract(window[-1].close, low), subtract(high, low)), 100.0)))


def _volume_ratio(window: list[DailyObservation], period=VOLUME_WINDOW, *, check=None) -> float | None:
    if len(window) < period:
        return None
    average = positive_mean([item.volume for item in checked(window, check, interval=32)], check=check)
    return ratio(window[-1].volume, average) if average > 0 else None


def _trade_direction(price_position: float | None, volume_ratio: float | None) -> str:
    if price_position is None or volume_ratio is None or volume_ratio < VOLUME_ACTIVE_RATIO:
        return "NEUTRAL"
    if price_position <= 40:
        return "ACCUMULATE"
    if price_position >= 70:
        return "DISTRIBUTE"
    return "NEUTRAL"


def _regime_series(closes: list[float], period=REGIME_MA_PERIOD, *, check=None) -> list[float | None]:
    results: list[float | None] = [None] * len(closes)
    ema: float | None = None
    alpha = 2.0 / (REGIME_EMA_SMOOTH + 1.0)
    for index in checked(range(period - 1, len(closes)), check):
        window = closes[index - period + 1 : index + 1]
        moving_average = positive_mean(window, check=check)
        deviation = subtract(ratio(closes[index], moving_average), 1.0)
        ema = deviation if ema is None else add(product(alpha, deviation), product(1.0 - alpha, ema))
        results[index] = max(-1.0, min(1.0, ratio(ema, 0.15)))
    return results


def regime_weight(score: float) -> float:
    """Scale one buy unit by the user-specified market-regime rule."""

    return max(0.5, min(1.0, add(0.8, product(0.2, finite(score)))))


def build_daily_features(values: list[DailyObservation], *, universe=None,
                         benchmark_symbol="510300.SH", regime_ma_period=REGIME_MA_PERIOD,
                         position_window=POSITION_WINDOW, volume_window=VOLUME_WINDOW, check=None) -> dict[str, list[DailyFeature]]:
    """Compute factors without future data and attach the 510300 regime by date."""

    if any(type(value) is not int or value < 1 for value in (regime_ma_period, position_window, volume_window)):
        raise ValueError("feature windows must be positive integers")
    observations = validate_observations(values, universe=universe, check=check)
    grouped: dict[str, list[DailyObservation]] = defaultdict(list)
    for item in checked(observations, check):
        grouped[item.symbol.upper()].append(item)
    benchmark = grouped.get(benchmark_symbol, [])
    regime_by_date = {
        item.trade_date: score
        for item, score in checked(zip(benchmark, _regime_series(
            [item.close for item in checked(benchmark, check)], regime_ma_period, check=check)), check)
    }
    results: dict[str, list[DailyFeature]] = {}
    for symbol, rows in checked(sorted(grouped.items()), check):
        features: list[DailyFeature] = []
        for index, item in checked(enumerate(rows), check):
            position = _price_position(rows[max(0, index - position_window + 1) : index + 1], position_window, check=check)
            volume_ratio = _volume_ratio(
                rows[max(0, index - volume_window + 1) : index + 1], volume_window, check=check
            )
            change = None
            if index > 0:
                change = product(subtract(ratio(item.close, rows[index - 1].close), 1.0), 100.0)
            regime = regime_by_date.get(item.trade_date)
            label = "insufficient"
            if regime is not None:
                label = "bull" if regime > 0.3 else "bear" if regime < -0.3 else "range"
            features.append(
                DailyFeature(
                    observation=item,
                    change_pct=change,
                    price_position=position,
                    volume_ratio=volume_ratio,
                    trade_direction=_trade_direction(position, volume_ratio),
                    regime_score=regime,
                    regime_label=label,
                )
            )
        results[symbol] = features
    return results


def _position_lamp(value: float | None) -> Lamp:
    if value is None:
        return "gray"
    if value <= 40:
        return "green"
    if value >= 70:
        return "red"
    return "gray"


def _percentile_lamp(value: float | None, *, green_min: float, red_max: float) -> Lamp:
    if value is None:
        return "gray"
    if value >= green_min:
        return "green"
    if value <= red_max:
        return "red"
    return "gray"


def _heat_lamp(value: float | None) -> Lamp:
    if value is None:
        return "gray"
    if value <= 20:
        return "green"
    if value >= 80:
        return "red"
    return "gray"


def resonance_lights(feature: DailyFeature) -> ResonanceLights:
    """Build the five evidence lamps; missing evidence stays gray."""

    observation = feature.observation
    direction: Lamp = "gray"
    if feature.trade_direction == "ACCUMULATE":
        direction = "green"
    elif feature.trade_direction == "DISTRIBUTE":
        direction = "red"
    return ResonanceLights(
        price_position=_position_lamp(feature.price_position),
        share_flow=_percentile_lamp(
            observation.share_probability,
            green_min=65,
            red_max=30,
        ),
        trade_direction=direction,
        turnover_heat=_heat_lamp(observation.turnover_percentile),
        margin_leverage=_heat_lamp(observation.margin_percentile),
    )
