"""
Titan-Quant Data Types

This module defines the core data types used throughout the Titan-Quant system
for market data, orders, and trades.

Requirements:
    - 7.1: Matching_Engine SHALL 支持 L1 撮合模式
    - 7.2: Matching_Engine SHALL 支持 L2 撮合模式

Technical Debt Resolution (TD-001):
    - Migrated from float to Decimal for price/volume fields to avoid IEEE 754 precision errors
    - All financial calculations now use Decimal for production-grade accuracy
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Optional, Union


# Decimal precision for financial calculations
PRICE_PRECISION = Decimal("0.00000001")  # 8 decimal places for crypto
VOLUME_PRECISION = Decimal("0.00000001")


def to_decimal(value: Union[float, int, str, Decimal, None], default: Decimal = Decimal("0")) -> Decimal:
    """Convert a value to Decimal safely."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return default


def decimal_to_float(value: Decimal) -> float:
    """Convert Decimal to float for serialization."""
    return float(value)


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
        open_price: Opening price (Decimal for precision)
        high_price: Highest price during the interval (Decimal)
        low_price: Lowest price during the interval (Decimal)
        close_price: Closing price (Decimal)
        volume: Trading volume (Decimal)
        turnover: Trading turnover (value) (Decimal)
        open_interest: Open interest (for futures, optional) (Decimal)
    
    Note:
        TD-001 Resolution: All price/volume fields use Decimal to avoid
        IEEE 754 floating-point precision errors in financial calculations.
    """
    symbol: str
    exchange: str
    datetime: datetime
    interval: str
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    turnover: Decimal
    open_interest: Decimal = field(default_factory=lambda: Decimal("0"))
    
    def __post_init__(self) -> None:
        """Validate and convert bar data after initialization."""
        # Convert to Decimal if needed (for backward compatibility with float inputs)
        self.open_price = to_decimal(self.open_price)
        self.high_price = to_decimal(self.high_price)
        self.low_price = to_decimal(self.low_price)
        self.close_price = to_decimal(self.close_price)
        self.volume = to_decimal(self.volume)
        self.turnover = to_decimal(self.turnover)
        self.open_interest = to_decimal(self.open_interest)
        
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
        """Convert to dictionary for serialization (uses string for Decimal precision)."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "datetime": self.datetime.isoformat(),
            "interval": self.interval,
            "open_price": str(self.open_price),
            "high_price": str(self.high_price),
            "low_price": str(self.low_price),
            "close_price": str(self.close_price),
            "volume": str(self.volume),
            "turnover": str(self.turnover),
            "open_interest": str(self.open_interest),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BarData:
        """Create BarData from dictionary."""
        return cls(
            symbol=data["symbol"],
            exchange=data["exchange"],
            datetime=datetime.fromisoformat(data["datetime"]),
            interval=data["interval"],
            open_price=to_decimal(data["open_price"]),
            high_price=to_decimal(data["high_price"]),
            low_price=to_decimal(data["low_price"]),
            close_price=to_decimal(data["close_price"]),
            volume=to_decimal(data["volume"]),
            turnover=to_decimal(data["turnover"]),
            open_interest=to_decimal(data.get("open_interest", "0")),
        )
    
    # Backward compatibility: float properties for existing code
    @property
    def open_price_float(self) -> float:
        """Get open_price as float (for backward compatibility)."""
        return float(self.open_price)
    
    @property
    def close_price_float(self) -> float:
        """Get close_price as float (for backward compatibility)."""
        return float(self.close_price)


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
        last_price: Last traded price (Decimal)
        volume: Last traded volume (Decimal)
        bid_price_1: Best bid price (Decimal)
        bid_volume_1: Best bid volume (Decimal)
        ask_price_1: Best ask price (Decimal)
        ask_volume_1: Best ask volume (Decimal)
        bid_prices: L2 bid prices (levels 1-10) (Decimal list)
        bid_volumes: L2 bid volumes (levels 1-10) (Decimal list)
        ask_prices: L2 ask prices (levels 1-10) (Decimal list)
        ask_volumes: L2 ask volumes (levels 1-10) (Decimal list)
        open_interest: Open interest (for futures) (Decimal)
        turnover: Daily turnover (Decimal)
    
    Note:
        TD-001 Resolution: All price/volume fields use Decimal to avoid
        IEEE 754 floating-point precision errors in financial calculations.
    """
    symbol: str
    exchange: str
    datetime: datetime
    last_price: Decimal
    volume: Decimal
    bid_price_1: Decimal
    bid_volume_1: Decimal
    ask_price_1: Decimal
    ask_volume_1: Decimal
    # L2 order book data (optional)
    bid_prices: Optional[list[Decimal]] = None
    bid_volumes: Optional[list[Decimal]] = None
    ask_prices: Optional[list[Decimal]] = None
    ask_volumes: Optional[list[Decimal]] = None
    # Additional fields
    open_interest: Decimal = field(default_factory=lambda: Decimal("0"))
    turnover: Decimal = field(default_factory=lambda: Decimal("0"))
    
    def __post_init__(self) -> None:
        """Validate and convert tick data after initialization."""
        # Convert to Decimal if needed (for backward compatibility with float inputs)
        self.last_price = to_decimal(self.last_price)
        self.volume = to_decimal(self.volume)
        self.bid_price_1 = to_decimal(self.bid_price_1)
        self.bid_volume_1 = to_decimal(self.bid_volume_1)
        self.ask_price_1 = to_decimal(self.ask_price_1)
        self.ask_volume_1 = to_decimal(self.ask_volume_1)
        self.open_interest = to_decimal(self.open_interest)
        self.turnover = to_decimal(self.turnover)
        
        # Convert L2 data to Decimal lists
        if self.bid_prices is not None:
            self.bid_prices = [to_decimal(p) for p in self.bid_prices]
        if self.bid_volumes is not None:
            self.bid_volumes = [to_decimal(v) for v in self.bid_volumes]
        if self.ask_prices is not None:
            self.ask_prices = [to_decimal(p) for p in self.ask_prices]
        if self.ask_volumes is not None:
            self.ask_volumes = [to_decimal(v) for v in self.ask_volumes]
        
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
    def spread(self) -> Decimal:
        """Calculate bid-ask spread (Decimal precision)."""
        return self.ask_price_1 - self.bid_price_1
    
    @property
    def mid_price(self) -> Decimal:
        """Calculate mid price (Decimal precision)."""
        return (self.bid_price_1 + self.ask_price_1) / Decimal("2")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (uses string for Decimal precision)."""
        result = {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "datetime": self.datetime.isoformat(),
            "last_price": str(self.last_price),
            "volume": str(self.volume),
            "bid_price_1": str(self.bid_price_1),
            "bid_volume_1": str(self.bid_volume_1),
            "ask_price_1": str(self.ask_price_1),
            "ask_volume_1": str(self.ask_volume_1),
            "open_interest": str(self.open_interest),
            "turnover": str(self.turnover),
        }
        if self.bid_prices is not None:
            result["bid_prices"] = [str(p) for p in self.bid_prices]
        if self.bid_volumes is not None:
            result["bid_volumes"] = [str(v) for v in self.bid_volumes]
        if self.ask_prices is not None:
            result["ask_prices"] = [str(p) for p in self.ask_prices]
        if self.ask_volumes is not None:
            result["ask_volumes"] = [str(v) for v in self.ask_volumes]
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TickData:
        """Create TickData from dictionary."""
        bid_prices = None
        bid_volumes = None
        ask_prices = None
        ask_volumes = None
        
        if data.get("bid_prices"):
            bid_prices = [to_decimal(p) for p in data["bid_prices"]]
        if data.get("bid_volumes"):
            bid_volumes = [to_decimal(v) for v in data["bid_volumes"]]
        if data.get("ask_prices"):
            ask_prices = [to_decimal(p) for p in data["ask_prices"]]
        if data.get("ask_volumes"):
            ask_volumes = [to_decimal(v) for v in data["ask_volumes"]]
        
        return cls(
            symbol=data["symbol"],
            exchange=data["exchange"],
            datetime=datetime.fromisoformat(data["datetime"]),
            last_price=to_decimal(data["last_price"]),
            volume=to_decimal(data["volume"]),
            bid_price_1=to_decimal(data["bid_price_1"]),
            bid_volume_1=to_decimal(data["bid_volume_1"]),
            ask_price_1=to_decimal(data["ask_price_1"]),
            ask_volume_1=to_decimal(data["ask_volume_1"]),
            bid_prices=bid_prices,
            bid_volumes=bid_volumes,
            ask_prices=ask_prices,
            ask_volumes=ask_volumes,
            open_interest=to_decimal(data.get("open_interest", "0")),
            turnover=to_decimal(data.get("turnover", "0")),
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
        price: Order price (0 for market orders) (Decimal)
        volume: Order volume (Decimal)
        traded: Filled volume (Decimal)
        status: Order status
        is_manual: Whether this is a manual intervention order
        create_time: Order creation timestamp
        update_time: Last update timestamp
        strategy_id: Associated strategy ID (optional)
        reference: User reference/note (optional)
    
    Note:
        TD-001 Resolution: price/volume/traded fields use Decimal to avoid
        IEEE 754 floating-point precision errors in financial calculations.
    """
    order_id: str
    symbol: str
    exchange: str
    direction: str  # "LONG" | "SHORT"
    offset: str     # "OPEN" | "CLOSE"
    price: Decimal
    volume: Decimal
    traded: Decimal
    status: str     # "PENDING" | "FILLED" | "PARTIALLY_FILLED" | "CANCELLED" | "REJECTED"
    is_manual: bool
    create_time: datetime
    update_time: Optional[datetime] = None
    strategy_id: Optional[str] = None
    reference: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate and convert order data after initialization."""
        # Convert to Decimal if needed (for backward compatibility with float inputs)
        self.price = to_decimal(self.price)
        self.volume = to_decimal(self.volume)
        self.traded = to_decimal(self.traded)
        
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
    def remaining(self) -> Decimal:
        """Calculate remaining unfilled volume (Decimal precision)."""
        return self.volume - self.traded
    
    @property
    def fill_ratio(self) -> Decimal:
        """Calculate fill ratio (0.0 to 1.0) (Decimal precision)."""
        return self.traded / self.volume if self.volume > 0 else Decimal("0")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (uses string for Decimal precision)."""
        result = {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "direction": self.direction,
            "offset": self.offset,
            "price": str(self.price),
            "volume": str(self.volume),
            "traded": str(self.traded),
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
            price=to_decimal(data["price"]),
            volume=to_decimal(data["volume"]),
            traded=to_decimal(data["traded"]),
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
    "to_decimal",
    "decimal_to_float",
    "PRICE_PRECISION",
    "VOLUME_PRECISION",
]
