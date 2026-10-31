"""观衡configured Resonance 1.2.0独立纯业务核。"""

from .dependency_identity import package_identity

_PACKAGE_VERSION, _DEPENDENCIES, _MANIFEST = package_identity(__name__, "guanheng-strategy-core")

from .contracts import (
    AuxiliaryGap, ConfiguredStrategyConfig, CurrentTarget, DailyFrame,
    EvaluationBudget, EvaluationResult, FrozenHistory, KernelValidationError,
    SignalState,
)
from .kernel import evaluate_history, evaluate_historical_model, validate_configuration
from .historical_model import HistoricalEodModel
from .models import DailyObservation

__all__ = [
    "evaluate_history", "validate_configuration", "ConfiguredStrategyConfig", "FrozenHistory", "DailyObservation",
    "EvaluationBudget", "EvaluationResult", "KernelValidationError", "CurrentTarget",
    "DailyFrame", "SignalState", "AuxiliaryGap",
    "HistoricalEodModel", "evaluate_historical_model",
]
