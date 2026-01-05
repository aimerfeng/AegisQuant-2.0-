"""
Abstract Data Provider Interface

This module defines the abstract base class for data providers in the Titan-Quant system.
Data providers allow pluggable data sources (MySQL, MongoDB, DolphinDB, Parquet, etc.)
to be used interchangeably for loading historical market data.

Requirements: Data source extension - Support pluggable data sources
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from core.engine.types import BarData, TickData


class ProviderStatus(Enum):
    """Data provider connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class HistoryRequest:
    """
    Historical data request parameters.
    
    Used to specify the data range and type when requesting
    historical market data from a data provider.
    
    Attributes:
        symbol: Trading symbol (e.g., "BTC_USDT", "AAPL")
        exchange: Exchange name (e.g., "binance", "nasdaq")
        start: Start datetime for the data range
        end: End datetime for the data range
        interval: Data interval ("tick", "1m", "5m", "1h", "1d", etc.)
    """
    symbol: str
    exchange: str
    start: datetime
    end: datetime
    interval: str  # "tick" | "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d" | "1w"
    
    def __post_init__(self) -> None:
        """Validate request parameters."""
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.exchange:
            raise ValueError("exchange must not be empty")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        valid_intervals = {"tick", "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}
        if self.interval not in valid_intervals:
            raise ValueError(f"interval must be one of {valid_intervals}")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "interval": self.interval,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryRequest:
        """Create HistoryRequest from dictionary."""
        return cls(
            symbol=data["symbol"],
            exchange=data["exchange"],
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            interval=data["interval"],
        )


@dataclass
class ProviderInfo:
    """
    Information about a data provider.
    
    Attributes:
        name: Provider name (e.g., "parquet", "mysql", "mongodb")
        version: Provider version
        description: Human-readable description
        supported_intervals: List of supported data intervals
        supports_tick: Whether tick data is supported
        supports_l2: Whether L2 order book data is supported
    """
    name: str
    version: str = "1.0.0"
    description: str = ""
    supported_intervals: list[str] = field(default_factory=lambda: ["1m", "5m", "1h", "1d"])
    supports_tick: bool = False
    supports_l2: bool = False


class AbstractDataProvider(ABC):
    """
    Abstract base class for data providers.
    
    This interface allows the Titan-Quant system to work with various
    data sources (MySQL, MongoDB, DolphinDB, local Parquet files, APIs)
    through a unified interface.
    
    Implementations should handle:
    - Connection management
    - Data loading and caching
    - Symbol/contract discovery
    - Error handling and reconnection
    
    Example usage:
        provider = MySQLDataProvider()
        provider.connect({"host": "localhost", "port": 3306, ...})
        
        req = HistoryRequest(
            symbol="BTC_USDT",
            exchange="binance",
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 31),
            interval="1h"
        )
        bars = provider.load_bar_history(req)
    """
    
    def __init__(self) -> None:
        """Initialize the data provider."""
        self._status: ProviderStatus = ProviderStatus.DISCONNECTED
        self._settings: dict[str, Any] = {}
        self._last_error: str | None = None
    
    @property
    def status(self) -> ProviderStatus:
        """Get current connection status."""
        return self._status
    
    @property
    def last_error(self) -> str | None:
        """Get the last error message, if any."""
        return self._last_error
    
    @abstractmethod
    def connect(self, settings: dict[str, Any]) -> bool:
        """
        Connect to the data source.
        
        Args:
            settings: Connection settings (host, port, credentials, etc.)
                     The exact keys depend on the provider implementation.
        
        Returns:
            True if connection successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from the data source.
        
        Returns:
            True if disconnection successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if currently connected to the data source.
        
        Returns:
            True if connected, False otherwise.
        """
        pass
    
    @abstractmethod
    def load_bar_history(self, req: HistoryRequest) -> list[BarData]:
        """
        Load K-line (bar) historical data.
        
        Args:
            req: History request parameters specifying symbol, exchange,
                 date range, and interval.
        
        Returns:
            List of BarData objects sorted by datetime ascending.
        
        Raises:
            DataError: If data loading fails or data is not available.
        """
        pass
    
    @abstractmethod
    def load_tick_history(self, req: HistoryRequest) -> list[TickData]:
        """
        Load tick-level historical data.
        
        Args:
            req: History request parameters. The interval field should be "tick".
        
        Returns:
            List of TickData objects sorted by datetime ascending.
        
        Raises:
            DataError: If data loading fails or tick data is not available.
        """
        pass
    
    @abstractmethod
    def get_available_symbols(self, exchange: str) -> list[str]:
        """
        Get list of available trading symbols for an exchange.
        
        Args:
            exchange: Exchange name (e.g., "binance", "okx")
        
        Returns:
            List of symbol names available for the exchange.
        """
        pass
    
    @abstractmethod
    def get_dominant_contract(self, symbol_root: str) -> str:
        """
        Get the dominant (most liquid) contract for a futures symbol.
        
        For spot markets, this typically returns the symbol unchanged.
        For futures, it returns the current main contract.
        
        Args:
            symbol_root: Root symbol (e.g., "IF" for CSI 300 futures)
        
        Returns:
            Full symbol of the dominant contract (e.g., "IF2401")
        """
        pass
    
    @abstractmethod
    def download_and_cache(self, req: HistoryRequest, save_path: str) -> bool:
        """
        Download data and cache it locally as Parquet files.
        
        This is useful for pre-downloading data for offline use
        or for improving performance by caching frequently used data.
        
        Args:
            req: History request parameters
            save_path: Local path to save the cached data
        
        Returns:
            True if download and cache successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of this data provider.
        
        Returns:
            Provider name (e.g., "parquet", "mysql", "mongodb")
        """
        pass
    
    def get_provider_info(self) -> ProviderInfo:
        """
        Get detailed information about this provider.
        
        Returns:
            ProviderInfo object with provider details.
        """
        return ProviderInfo(name=self.get_provider_name())
    
    def get_data_range(self, symbol: str, exchange: str, interval: str) -> tuple[datetime, datetime] | None:
        """
        Get the available data range for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            interval: Data interval
        
        Returns:
            Tuple of (start_datetime, end_datetime) or None if no data available.
        """
        # Default implementation returns None; subclasses can override
        return None
    
    def validate_request(self, req: HistoryRequest) -> bool:
        """
        Validate a history request against provider capabilities.
        
        Args:
            req: History request to validate
        
        Returns:
            True if request is valid for this provider, False otherwise.
        """
        info = self.get_provider_info()
        
        # Check if interval is supported
        if req.interval == "tick":
            return info.supports_tick
        return req.interval in info.supported_intervals


__all__ = [
    "ProviderStatus",
    "HistoryRequest",
    "ProviderInfo",
    "AbstractDataProvider",
]
