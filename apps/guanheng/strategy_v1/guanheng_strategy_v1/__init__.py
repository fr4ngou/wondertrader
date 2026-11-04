"""唯一保留共振1.2.1纯策略；实际状态与执行归原生宿主。"""
from guanheng_strategy_core.dependency_identity import package_identity

_PACKAGE_VERSION, _DEPENDENCIES, _MANIFEST = package_identity(__name__, 'guanheng-strategy-v1')

from .role_profile import ALGORITHM_ID, ROLE_SYMBOLS
from .latest import (
    AnalysisBar, AnalysisWindow, CurrentHistoryView, CycleExit, PositionCycle,
    RetainedConfig, RetainedInput, RetainedResult, RetainedValidationError,
    STRATEGY_ID, STRATEGY_VERSION, SYMBOLS, evaluate_current_view,
    evaluate_historical_model, RetainedHistoricalModel, validate_retained_configuration,
)

__all__ = ['ALGORITHM_ID', 'ROLE_SYMBOLS', 'AnalysisBar', 'AnalysisWindow', 'CurrentHistoryView', 'CycleExit', 'PositionCycle',
    'RetainedConfig', 'RetainedInput', 'RetainedResult', 'RetainedValidationError',
    'STRATEGY_ID', 'STRATEGY_VERSION', 'SYMBOLS', 'evaluate_current_view',
    'evaluate_historical_model', 'RetainedHistoricalModel', 'validate_retained_configuration']
