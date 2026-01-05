"""
Parquet Storage Module

This module provides Parquet-based storage functionality for the Titan-Quant system.
It implements organized storage by exchange/contract/period with proper schemas
for Tick and Bar data.

Requirements: 2.6 - Store cleaned data as Parquet format, classified by date/contract
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from core.exceptions import DataError, ErrorCodes


class DataType(Enum):
    """Types of market data."""
    TICK = "tick"
    BAR = "bar"


class BarInterval(Enum):
    """Standard bar intervals."""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"


# Minimal required columns for each data type
TICK_REQUIRED_COLUMNS = ["timestamp", "last_price", "volume"]
BAR_REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

# Schema definitions
TICK_SCHEMA = {
    "timestamp": "datetime64[ns]",
    "last_price": "float64",
    "volume": "float64",
    "turnover": "float64",
    "bid_price_1": "float64",
    "bid_volume_1": "float64",
    "ask_price_1": "float64",
    "ask_volume_1": "float64",
}

BAR_SCHEMA = {
    "timestamp": "datetime64[ns]",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "float64",
    "turnover": "float64",
}


@dataclass
class StorageConfig:
    """Configuration for Parquet storage."""
    base_path: str = "database"
    compression: str = "snappy"
    row_group_size: int = 100000


class ParquetStorage:
    """
    Parquet-based storage for market data.
    
    Organizes data by:
    - database/ticks/{exchange}/{symbol}/{date}.parquet
    - database/bars/{exchange}/{symbol}/{interval}.parquet
    """
    
    def __init__(self, config: StorageConfig | None = None) -> None:
        """Initialize the ParquetStorage."""
        self.config = config or StorageConfig()
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Create base directories if they don't exist."""
        base = Path(self.config.base_path)
        (base / "ticks").mkdir(parents=True, exist_ok=True)
        (base / "bars").mkdir(parents=True, exist_ok=True)
        (base / "cache").mkdir(parents=True, exist_ok=True)
    
    def _get_tick_path(self, exchange: str, symbol: str, date: str) -> Path:
        """Get the file path for tick data."""
        return (
            Path(self.config.base_path) / "ticks" / 
            exchange.lower() / symbol.lower() / f"{date}.parquet"
        )
    
    def _get_bar_path(self, exchange: str, symbol: str, interval: str | BarInterval) -> Path:
        """Get the file path for bar data."""
        if isinstance(interval, BarInterval):
            interval = interval.value
        return (
            Path(self.config.base_path) / "bars" /
            exchange.lower() / symbol.lower() / f"{interval}.parquet"
        )
    
    def _validate_tick_schema(self, df: pd.DataFrame) -> None:
        """Validate that DataFrame has required tick columns."""
        missing = [col for col in TICK_REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise DataError(
                message=f"Missing required tick columns: {missing}",
                error_code=ErrorCodes.DATA_FORMAT_INVALID,
                details={"missing_columns": missing},
            )
    
    def _validate_bar_schema(self, df: pd.DataFrame) -> None:
        """Validate that DataFrame has required bar columns."""
        missing = [col for col in BAR_REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise DataError(
                message=f"Missing required bar columns: {missing}",
                error_code=ErrorCodes.DATA_FORMAT_INVALID,
                details={"missing_columns": missing},
            )

    def save_tick_data(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str,
        date: str,
    ) -> str:
        """Save tick data to Parquet file."""
        self._validate_tick_schema(df)
        
        file_path = self._get_tick_path(exchange, symbol, date)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_parquet(file_path, compression=self.config.compression, index=False)
        return str(file_path)
    
    def save_bar_data(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str,
        interval: str | BarInterval,
    ) -> str:
        """Save bar data to Parquet file."""
        self._validate_bar_schema(df)
        
        file_path = self._get_bar_path(exchange, symbol, interval)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_parquet(file_path, compression=self.config.compression, index=False)
        return str(file_path)
    
    def load_tick_data(
        self, 
        exchange: str, 
        symbol: str, 
        date: str,
        filters: list[tuple[str, str, Any]] | None = None,
    ) -> pd.DataFrame:
        """
        Load tick data from Parquet file.
        
        Args:
            exchange: Exchange name
            symbol: Symbol name
            date: Date string (YYYY-MM-DD)
            filters: Optional PyArrow filters for predicate pushdown
                     Format: [('column', 'op', value), ...]
                     Example: [('symbol', '==', 'btc_usdt')]
        
        Returns:
            DataFrame with tick data
        
        Performance Notes (Audit 2026-01-05):
            - Uses filters parameter for Predicate Pushdown when available
            - Reduces I/O by filtering at the Parquet level
        """
        file_path = self._get_tick_path(exchange, symbol, date)
        
        if not file_path.exists():
            raise DataError(
                message=f"Tick data not found: {file_path}",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
                file_path=str(file_path),
            )
        
        # [Optimization] Use filters for Predicate Pushdown when provided
        try:
            if filters:
                return pd.read_parquet(file_path, engine='pyarrow', filters=filters)
            return pd.read_parquet(file_path)
        except Exception as e:
            # Fallback to full read if filters fail (e.g., column not in file)
            if filters:
                return pd.read_parquet(file_path)
            raise
    
    def load_bar_data(
        self, 
        exchange: str, 
        symbol: str, 
        interval: str | BarInterval,
        filters: list[tuple[str, str, Any]] | None = None,
    ) -> pd.DataFrame:
        """
        Load bar data from Parquet file.
        
        Args:
            exchange: Exchange name
            symbol: Symbol name
            interval: Bar interval (e.g., '1m', '1h', '1d')
            filters: Optional PyArrow filters for predicate pushdown
                     Format: [('column', 'op', value), ...]
                     Example: [('symbol', '==', 'btc_usdt')]
        
        Returns:
            DataFrame with bar data
        
        Performance Notes (Audit 2026-01-05):
            - Uses filters parameter for Predicate Pushdown when available
            - Reduces I/O by filtering at the Parquet level
        """
        file_path = self._get_bar_path(exchange, symbol, interval)
        
        if not file_path.exists():
            raise DataError(
                message=f"Bar data not found: {file_path}",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
                file_path=str(file_path),
            )
        
        # [Optimization] Use filters for Predicate Pushdown when provided
        try:
            if filters:
                return pd.read_parquet(file_path, engine='pyarrow', filters=filters)
            return pd.read_parquet(file_path)
        except Exception as e:
            # Fallback to full read if filters fail (e.g., column not in file)
            if filters:
                return pd.read_parquet(file_path)
            raise
    
    def list_exchanges(self, data_type: DataType = DataType.BAR) -> list[str]:
        """List available exchanges."""
        base = Path(self.config.base_path) / ("ticks" if data_type == DataType.TICK else "bars")
        if not base.exists():
            return []
        return [d.name for d in base.iterdir() if d.is_dir()]
    
    def list_symbols(self, exchange: str, data_type: DataType = DataType.BAR) -> list[str]:
        """List available symbols for an exchange."""
        base = Path(self.config.base_path) / ("ticks" if data_type == DataType.TICK else "bars") / exchange.lower()
        if not base.exists():
            return []
        return [d.name for d in base.iterdir() if d.is_dir()]
    
    def list_tick_dates(self, exchange: str, symbol: str) -> list[str]:
        """List available dates for tick data."""
        base = Path(self.config.base_path) / "ticks" / exchange.lower() / symbol.lower()
        if not base.exists():
            return []
        return [f.stem for f in base.iterdir() if f.is_file() and f.suffix == ".parquet"]
    
    def list_bar_intervals(self, exchange: str, symbol: str) -> list[str]:
        """List available intervals for bar data."""
        base = Path(self.config.base_path) / "bars" / exchange.lower() / symbol.lower()
        if not base.exists():
            return []
        return [f.stem for f in base.iterdir() if f.is_file() and f.suffix == ".parquet"]

    def delete_tick_data(self, exchange: str, symbol: str, date: str) -> bool:
        """Delete tick data file."""
        file_path = self._get_tick_path(exchange, symbol, date)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def delete_bar_data(self, exchange: str, symbol: str, interval: str | BarInterval) -> bool:
        """Delete bar data file."""
        file_path = self._get_bar_path(exchange, symbol, interval)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def get_storage_info(self) -> dict[str, Any]:
        """Get information about stored data."""
        base = Path(self.config.base_path)
        
        tick_files = list((base / "ticks").rglob("*.parquet")) if (base / "ticks").exists() else []
        bar_files = list((base / "bars").rglob("*.parquet")) if (base / "bars").exists() else []
        
        tick_size = sum(f.stat().st_size for f in tick_files)
        bar_size = sum(f.stat().st_size for f in bar_files)
        
        return {
            "base_path": str(base),
            "tick_files": len(tick_files),
            "bar_files": len(bar_files),
            "tick_size_bytes": tick_size,
            "bar_size_bytes": bar_size,
            "total_size_bytes": tick_size + bar_size,
            "exchanges": {
                "ticks": self.list_exchanges(DataType.TICK),
                "bars": self.list_exchanges(DataType.BAR),
            },
        }


__all__ = [
    "DataType",
    "BarInterval",
    "TICK_SCHEMA",
    "BAR_SCHEMA",
    "TICK_REQUIRED_COLUMNS",
    "BAR_REQUIRED_COLUMNS",
    "StorageConfig",
    "ParquetStorage",
]
