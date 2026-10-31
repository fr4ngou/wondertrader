"""Pure allocation policy for the reviewed Resonance signal machines."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .models import DEFAULT_SYMBOLS as RESONANCE_V1_SYMBOLS

from .features import regime_weight
from .models import DailyFeature, ResonanceDecision
from .numerics import add, product
from .computation import checked


BASE_UNIT_WEIGHT = 0.125
SYMBOL_CAP_WEIGHT = 0.25
PRE_RISK_CAPACITY = 1.0


@dataclass(frozen=True)
class AllocationEvent:
    """One post-close target snapshot before account-level Portfolio risk."""

    trade_date: date
    target_weights: tuple[tuple[str, float], ...]
    decision_paths: tuple[str, ...]
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, float]:
        return dict(self.target_weights)


def _regime_scores(
    features_by_symbol: dict[str, list[DailyFeature]], benchmark_symbol="510300.SH", *, check=None,
) -> dict[date, float]:
    benchmark = features_by_symbol.get(benchmark_symbol)
    if not benchmark:
        raise ValueError("configured benchmark features are required for regime allocation")
    values = {}
    for feature in checked(benchmark, check):
        if feature.regime_score is not None:
            values[feature.observation.trade_date] = feature.regime_score
    return values


def _targets(
    *,
    symbols: set[str],
    active: dict[str, tuple[float, int]],
    csi300_strength: float,
    csi300_factor: float,
    pre_risk_capacity: float,
    strength_symbol="510300.SH", base_unit_weight=BASE_UNIT_WEIGHT, symbol_cap_weight=SYMBOL_CAP_WEIGHT, check=None,
) -> dict[str, float]:
    targets = {symbol: 0.0 for symbol in sorted(symbols)}
    if strength_symbol is not None and csi300_strength > 0:
        targets[strength_symbol] = product(product(symbol_cap_weight, csi300_strength), csi300_factor)

    for symbol, (factor, _rank) in checked(active.items(), check):
        targets[symbol] = product(base_unit_weight, factor)

    used = sum(targets.values())
    for symbol, (factor, _rank) in checked(sorted(
        active.items(), key=lambda item: (-item[1][1], item[0])
    ), check):
        upgrade = product(base_unit_weight, factor)
        if add(used, upgrade) > pre_risk_capacity + 1e-12:
            continue
        targets[symbol] = add(targets[symbol], upgrade)
        used = add(used, upgrade)
    return targets


def build_allocation_events(
    *,
    features_by_symbol: dict[str, list[DailyFeature]],
    decisions_by_symbol: dict[str, list[ResonanceDecision]],
    pre_risk_capacity: float = PRE_RISK_CAPACITY,
    universe: tuple[str, ...] = RESONANCE_V1_SYMBOLS,
    benchmark_symbol="510300.SH", base_unit_weight=BASE_UNIT_WEIGHT, symbol_cap_weight=SYMBOL_CAP_WEIGHT,
    strength_symbol="510300.SH",
    state=None, state_out=None, check=None,
) -> list[AllocationEvent]:
    """Apply sell-first/base-unit/recent-buy-first-upgrade allocation semantics.

    The returned weights are strategy requests, not account approvals. Portfolio remains
    responsible for the 95% account cap and every other hard-risk rule.
    """

    if not 0 < pre_risk_capacity <= 1:
        raise ValueError("pre_risk_capacity must be between zero and one")
    scores = _regime_scores(features_by_symbol, benchmark_symbol, check=check)
    by_date: dict[date, list[ResonanceDecision]] = defaultdict(list)
    for symbol, decisions in checked(decisions_by_symbol.items(), check):
        normalized = symbol.upper()
        if normalized not in set(universe):
            raise ValueError("unsupported allocation symbol: {0}".format(normalized))
        for decision in checked(decisions, check):
            if decision.symbol.upper() != normalized:
                raise ValueError("decision symbol does not match its allocation series")
            by_date[decision.trade_date].append(decision)

    state = state or {}
    active: dict[str, tuple[float, int]] = dict(state.get("active", {}))
    csi300_strength = state.get("csi300_strength", 0.0)
    csi300_factor = state.get("csi300_factor", 1.0)
    sequence = state.get("sequence", 0)
    previous: dict[str, float] | None = state.get("previous")
    events = []
    for trade_date in checked(sorted(by_date), check):
        if trade_date not in scores:
            raise ValueError(
                "benchmark regime is unavailable for decision date {0}".format(trade_date)
            )
        factor = regime_weight(scores[trade_date])
        decisions = sorted(
            by_date[trade_date],
            key=lambda item: (item.action != "SELL", item.symbol, item.path),
        )
        for decision in checked(decisions, check):
            symbol = decision.symbol.upper()
            if symbol == strength_symbol:
                csi300_strength = decision.strength
                csi300_factor = factor
                continue
            if decision.action == "SELL":
                active.pop(symbol, None)
            elif decision.action == "BUY":
                sequence += 1
                active[symbol] = (factor, sequence)

        targets = _targets(
            symbols=set(universe),
            active=active,
            csi300_strength=csi300_strength,
            csi300_factor=csi300_factor,
            pre_risk_capacity=pre_risk_capacity,
            strength_symbol=strength_symbol, base_unit_weight=base_unit_weight, symbol_cap_weight=symbol_cap_weight, check=check,
        )
        if previous is not None and all(
            abs(targets[symbol] - previous[symbol]) <= 1e-12
            for symbol in targets
        ):
            continue
        previous = targets
        events.append(
            AllocationEvent(
                trade_date=trade_date,
                target_weights=tuple(sorted(targets.items())),
                decision_paths=tuple(
                    "{0}:{1}:{2}".format(item.symbol, item.action, item.path)
                    for item in decisions
                ),
                evidence_refs=tuple(
                    dict.fromkeys(
                        evidence
                        for item in decisions
                        for evidence in item.evidence_refs
                    )
                ),
            )
        )
    if state_out is not None:
        state_out.update(active=active, csi300_strength=csi300_strength,
            csi300_factor=csi300_factor, sequence=sequence, previous=previous,
            last_event_date=(events[-1].trade_date.isoformat() if events else state.get("last_event_date")))
    return events
