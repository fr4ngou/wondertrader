"""唯一保留共振1.1.2纯策略；实际状态与执行归原生宿主。"""
from guanheng_strategy_core.dependency_identity import package_identity

_PACKAGE_VERSION, _DEPENDENCIES, _MANIFEST = package_identity(__name__, 'guanheng-strategy-v1')

from .latest import (
    AnalysisBar, AnalysisWindow, CurrentHistoryView, CycleExit, PositionCycle,
    RetainedConfig, RetainedInput, RetainedResult, RetainedValidationError,
    STRATEGY_ID, STRATEGY_VERSION, SYMBOLS, evaluate_current_view,
    evaluate_historical_model, RetainedHistoricalModel, validate_retained_configuration,
)

__all__ = ['AnalysisBar', 'AnalysisWindow', 'CurrentHistoryView', 'CycleExit', 'PositionCycle',
    'RetainedConfig', 'RetainedInput', 'RetainedResult', 'RetainedValidationError',
    'STRATEGY_ID', 'STRATEGY_VERSION', 'SYMBOLS', 'evaluate_current_view',
    'evaluate_historical_model', 'RetainedHistoricalModel', 'validate_retained_configuration']
