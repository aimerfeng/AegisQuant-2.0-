"""
Engine Adapters (VeighNa, Custom, etc.)

This module provides adapters for different trading engines,
enabling the Titan-Quant system to work with various backends.
"""
from core.engine.adapters.veighna_adapter import VEIGHNA_AVAILABLE, VeighNaAdapter

__all__ = [
    "VeighNaAdapter",
    "VEIGHNA_AVAILABLE",
]
