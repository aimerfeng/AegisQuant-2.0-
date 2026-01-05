"""
Titan-Quant Data Types

This module defines the core data types used throughout the Titan-Quant system
for market data, orders, and trades.

Requirements:
    - 7.1: Matching_Engine SHALL 支持 L1 撮合模式
    - 7.2: Matching_Engine SHALL 支持 L2 撮合模式
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class Direction(Enum):
    """Order direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class Offset(Enum):
    """Order offset type."""
    OPEN = "OPEN"
    CLOSE = "CLOSE"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class Interval(Enum):
    """Bar interval types."""
    TICK = "tick"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAILY = "1d"
    WEEKLY = "1w"


@dataclass
class BarData:
    """
    K-line (candlestick) bar data.
    
    Represents OHLCV data for a specific time interval.
    Used for backtesting and technical analysis.
    
    Attributes:
        symbol: Trading symbol (e.g., "BTC_USDT")
        exchange: Exchange name (e.g., "binance", "okx")
        datetime: Bar timestamp (start of the interval)
        interval: Bar interval (e.g., "1m", "5m", "1h", "1d")
        open_price: Opening price
        high_price: Highest price during the interval
        low_price: Lowest price during the interval
        close_price: Closing price
        volume: Trading volume
        turnover: Trading turnover (value)
        open_interest: Open interest (for futures, optional)
    """
    symbol: str
    exchange: str
    datetime: datetime
    interval: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    turnover: float
    open_interest: float = 0.0
    
    def __post_init__(self) -> None:
        """Validate bar data after initialization."""
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.exchange:
            raise ValueError("exchange must not be empty")
        if self.high_price < self.low_price:
            raise ValueError("high_price must be >= low_price")
        if self.open_price < 0 or self.close_price < 0:
            raise ValueError("prices must be non-negative")
        if self.volume < 0:
            raise ValueError("volume must be non-negative")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "datetime": self.datetime.isoformat(),
            "interval": self.interval,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "volume": self.volume,
            "turnover": self.turnover,
            "open_interest": self.open_interest,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BarData:
        """Create BarData from dictionary."""
        return cls(
            symbol=data["symbol"],
            exchange=data["exchange"],
            datetime=datetime.fromisoformat(data["datetime"]),
            interval=data["interval"],
            open_price=data["open_price"],
            high_price=data["high_price"],
            low_price=data["low_price"],
            close_price=data["close_price"],
            volume=data["volume"],
            turnover=data["turnover"],
            open_interest=data.get("open_interest", 0.0),
        )


@dataclass
class TickData:
    """
    Tick-level market data.
    
    Represents real-time market data including last trade price
    and order book depth (L1 or L2).
    
    Attributes:
        symbol: Trading symbol
        exchange: Exchange name
        datetime: Tick timestamp
        last_price: Last traded price
        volume: Last traded volume
        bid_price_1: Best bid price
        bid_volume_1: Best bid volume
        ask_price_1: Best ask price
        ask_volume_1: Best ask volume
        bid_prices: L2 bid prices (levels 1-10)
        bid_volumes: L2 bid volumes (levels 1-10)
        ask_prices: L2 ask prices (levels 1-10)
        ask_volumes: L2 ask volumes (levels 1-10)
        open_interest: Open interest (for futures)
        turnover: Daily turnover
    """
    symbol: str
    exchange: str
    datetime: datetime
    last_price: float
    volume: float
    bid_price_1: float
    bid_volume_1: float
    ask_price_1: float
    ask_volume_1: float
    # L2 order book data (optional)
    bid_prices: Optional[list[float]] = None
    bid_volumes: Optional[list[float]] = None
    ask_prices: Optional[list[float]] = None
    ask_volumes: Optional[list[float]] = None
    # Additional fields
    open_interest: float = 0.0
    turnover: float = 0.0
    
    def __post_init__(self) -> None:
        """Validate tick data after initialization."""
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.exchange:
            raise ValueError("exchange must not be empty")
        if self.last_price < 0:
            raise ValueError("last_price must be non-negative")
        # Validate L2 data consistency
        if self.bid_prices is not None and self.bid_volumes is not None:
            if len(self.bid_prices) != len(self.bid_volumes):
                raise ValueError("bid_prices and bid_volumes must have same length")
        if self.ask_prices is not None and self.ask_volumes is not None:
            if len(self.ask_prices) != len(self.ask_volumes):
                raise ValueError("ask_prices and ask_volumes must have same length")
    
    @property
    def has_l2_data(self) -> bool:
        """Check if L2 order book data is available."""
        return (
            self.bid_prices is not None 
            and self.ask_prices is not None
            and len(self.bid_prices) > 0
            and len(self.ask_prices) > 0
        )
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.ask_price_1 - self.bid_price_1
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price."""
        return (self.bid_price_1 + self.ask_price_1) / 2
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "datetime": self.datetime.isoformat(),
            "last_price": self.last_price,
            "volume": self.volume,
            "bid_price_1": self.bid_price_1,
            "bid_volume_1": self.bid_volume_1,
            "ask_price_1": self.ask_price_1,
            "ask_volume_1": self.ask_volume_1,
            "open_interest": self.open_interest,
            "turnover": self.turnover,
        }
        if self.bid_prices is not None:
            result["bid_prices"] = self.bid_prices
        if self.bid_volumes is not None:
            result["bid_volumes"] = self.bid_volumes
        if self.ask_prices is not None:
            result["ask_prices"] = self.ask_prices
        if self.ask_volumes is not None:
            result["ask_volumes"] = self.ask_volumes
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TickData:
        """Create TickData from dictionary."""
        return cls(
            symbol=data["symbol"],
            exchange=data["exchange"],
            datetime=datetime.fromisoformat(data["datetime"]),
            last_price=data["last_price"],
            volume=data["volume"],
            bid_price_1=data["bid_price_1"],
            bid_volume_1=data["bid_volume_1"],
            ask_price_1=data["ask_price_1"],
            ask_volume_1=data["ask_volume_1"],
            bid_prices=data.get("bid_prices"),
            bid_volumes=data.get("bid_volumes"),
            ask_prices=data.get("ask_prices"),
            ask_volumes=data.get("ask_volumes"),
            open_interest=data.get("open_interest", 0.0),
            turnover=data.get("turnover", 0.0),
        )


@dataclass
class OrderData:
    """
    Order data structure.
    
    Represents a trading order with all relevant information
    for order management and execution tracking.
    
    Attributes:
        order_id: Unique order identifier
        symbol: Trading symbol
        exchange: Exchange name
        direction: Order direction (LONG/SHORT)
        offset: Order offset (OPEN/CLOSE)
        price: Order price (0 for market orders)
        volume: Order volume
        traded: Filled volume
        status: Order status
        is_manual: Whether this is a manual intervention order
        create_time: Order creation timestamp
        update_time: Last update timestamp
        strategy_id: Associated strategy ID (optional)
        reference: User reference/note (optional)
    """
    order_id: str
    symbol: str
    exchange: str
    direction: str  # "LONG" | "SHORT"
    offset: str     # "OPEN" | "CLOSE"
    price: float
    volume: float
    traded: float
    status: str     # "PENDING" | "FILLED" | "PARTIALLY_FILLED" | "CANCELLED" | "REJECTED"
    is_manual: bool
    create_time: datetime
    update_time: Optional[datetime] = None
    strategy_id: Optional[str] = None
    reference: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate order data after initialization."""
        if not self.order_id:
            raise ValueError("order_id must not be empty")
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.exchange:
            raise ValueError("exchange must not be empty")
        if self.direction not in ("LONG", "SHORT"):
            raise ValueError("direction must be 'LONG' or 'SHORT'")
        if self.offset not in ("OPEN", "CLOSE"):
            raise ValueError("offset must be 'OPEN' or 'CLOSE'")
        if self.volume <= 0:
            raise ValueError("volume must be positive")
        if self.traded < 0:
            raise ValueError("traded must be non-negative")
        if self.traded > self.volume:
            raise ValueError("traded cannot exceed volume")
        valid_statuses = {"PENDING", "FILLED", "PARTIALLY_FILLED", "CANCELLED", "REJECTED"}
        if self.status not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
    
    @property
    def is_active(self) -> bool:
        """Check if order is still active (can be filled or cancelled)."""
        return self.status in ("PENDING", "PARTIALLY_FILLED")
    
    @property
    def remaining(self) -> float:
        """Calculate remaining unfilled volume."""
        return self.volume - self.traded
    
    @property
    def fill_ratio(self) -> float:
        """Calculate fill ratio (0.0 to 1.0)."""
        return self.traded / self.volume if self.volume > 0 else 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "direction": self.direction,
            "offset": self.offset,
            "price": self.price,
            "volume": self.volume,
            "traded": self.traded,
            "status": self.status,
            "is_manual": self.is_manual,
            "create_time": self.create_time.isoformat(),
        }
        if self.update_time:
            result["update_time"] = self.update_time.isoformat()
        if self.strategy_id:
            result["strategy_id"] = self.strategy_id
        if self.reference:
            result["reference"] = self.reference
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrderData:
        """Create OrderData from dictionary."""
        return cls(
            order_id=data["order_id"],
            symbol=data["symbol"],
            exchange=data["exchange"],
            direction=data["direction"],
            offset=data["offset"],
            price=data["price"],
            volume=data["volume"],
            traded=data["traded"],
            status=data["status"],
            is_manual=data["is_manual"],
            create_time=datetime.fromisoformat(data["create_time"]),
            update_time=datetime.fromisoformat(data["update_time"]) if data.get("update_time") else None,
            strategy_id=data.get("strategy_id"),
            reference=data.get("reference"),
        )


__all__ = [
    "Direction",
    "Offset",
    "OrderStatus",
    "Interval",
    "BarData",
    "TickData",
    "OrderData",
]
