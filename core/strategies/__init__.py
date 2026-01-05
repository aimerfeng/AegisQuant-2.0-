"""
Strategy Management Module

This module provides strategy management functionality including:
- Strategy parameter parsing and UI mapping
- Hot reload with multiple policies
- Strategy template base class
"""
from core.strategies.manager import (
    HotReloadPolicy,
    IStrategyManager,
    ParameterExtractor,
    ParameterType,
    ReloadResult,
    StrategyInfo,
    StrategyManager,
    StrategyParameter,
    UIWidget,
    preserve,
)
from core.strategies.template import (
    CtaTemplate,
    StrategyStatus,
    TradeSignal,
)

__all__ = [
    # Manager
    "HotReloadPolicy",
    "ParameterType",
    "UIWidget",
    "StrategyParameter",
    "ReloadResult",
    "StrategyInfo",
    "ParameterExtractor",
    "IStrategyManager",
    "StrategyManager",
    "preserve",
    # Template
    "StrategyStatus",
    "TradeSignal",
    "CtaTemplate",
]
