"""
Titan-Quant Matching Engine

This module implements the matching engine for order execution simulation.
It supports both L1 (price-based) and L2 (order book-based) matching modes
with configurable commission and slippage models.

Requirements:
    - 7.1: Matching_Engine SHALL 支持 L1 撮合模式（基于对价成交，假设无限流动性）
    - 7.2: Matching_Engine SHALL 支持 L2 撮合模式，并明确声明模拟等级
    - 7.3: WHEN 用户选择 L2 撮合, THEN THE Matching_Engine SHALL 在报告中明确标注所使用的模拟等级及其局限性
    - 7.4: WHEN 用户配置回测参数, THEN THE Matching_Engine SHALL 允许设置手续费率和滑点模型
    - 7.5: THE Matching_Engine SHALL 记录每笔成交的详细信息

Technical Debt Resolution (TD-001):
    - TradeRecord uses Decimal for price/volume/turnover/commission/slippage
    - All financial calculations use Decimal for production-grade accuracy
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from core.engine.types import OrderData, TickData, to_decimal
from core.exceptions import EngineError, ErrorCodes


class MatchingMode(Enum):
    """
    Matching mode enumeration.
    
    L1: Price-based matching assuming infinite liquidity.
        Orders are filled at the opposite side price (bid for sells, ask for buys).
        
    L2: Order book-based matching with queue position simulation.
        Requires L2 market data and simulates realistic order execution.
    """
    L1 = "L1"
    L2 = "L2"


class L2SimulationLevel(Enum):
    """
    L2 simulation level enumeration.
    
    Each level provides different accuracy and complexity trade-offs:
    
    LEVEL_1 (Queue Position Estimation):
        - Estimates queue position based on order arrival time and price priority
        - Assumes FIFO execution within price levels
        - Limitations: Does not account for hidden orders or order cancellations
        
    LEVEL_2 (Full Order Book Rebuild):
        - Rebuilds complete order book from historical L2 snapshots
        - Tracks individual order lifecycle
        - Limitations: Requires high-quality L2 data, may miss intra-snapshot events
        
    LEVEL_3 (Market Microstructure Simulation):
        - Includes hidden order estimation and iceberg order detection
        - Models market maker behavior and adverse selection
        - Limitations: Highly model-dependent, requires calibration
    """
    LEVEL_1 = "queue_position"
    LEVEL_2 = "orderbook_rebuild"
    LEVEL_3 = "microstructure"


class SlippageModel(Enum):
    """
    Slippage model enumeration.
    
    FIXED: Constant slippage applied to all trades.
    VOLUME_BASED: Slippage increases with order volume relative to market volume.
    VOLATILITY_BASED: Slippage scales with market volatility.
    """
    FIXED = "fixed"
    VOLUME_BASED = "volume_based"
    VOLATILITY_BASED = "volatility_based"


@dataclass
class MatchingConfig:
    """
    Matching engine configuration.
    
    Attributes:
        mode: Matching mode (L1 or L2)
        l2_level: L2 simulation level (required if mode is L2)
        commission_rate: Commission rate as a decimal (e.g., 0.0003 for 0.03%)
        slippage_model: Slippage calculation model
        slippage_value: Base slippage value (interpretation depends on model)
        min_commission: Minimum commission per trade
        enable_partial_fill: Whether to allow partial order fills
    """
    mode: MatchingMode
    l2_level: Optional[L2SimulationLevel] = None
    commission_rate: float = 0.0003
    slippage_model: SlippageModel = SlippageModel.FIXED
    slippage_value: float = 0.0001
    min_commission: float = 0.0
    enable_partial_fill: bool = True
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.mode == MatchingMode.L2 and self.l2_level is None:
            raise ValueError("l2_level is required when mode is L2")
        if self.commission_rate < 0:
            raise ValueError("commission_rate must be non-negative")
        if self.slippage_value < 0:
            raise ValueError("slippage_value must be non-negative")
        if self.min_commission < 0:
            raise ValueError("min_commission must be non-negative")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mode": self.mode.value,
            "l2_level": self.l2_level.value if self.l2_level else None,
            "commission_rate": self.commission_rate,
            "slippage_model": self.slippage_model.value,
            "slippage_value": self.slippage_value,
            "min_commission": self.min_commission,
            "enable_partial_fill": self.enable_partial_fill,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MatchingConfig:
        """Create MatchingConfig from dictionary."""
        return cls(
            mode=MatchingMode(data["mode"]),
            l2_level=L2SimulationLevel(data["l2_level"]) if data.get("l2_level") else None,
            commission_rate=data.get("commission_rate", 0.0003),
            slippage_model=SlippageModel(data.get("slippage_model", "fixed")),
            slippage_value=data.get("slippage_value", 0.0001),
            min_commission=data.get("min_commission", 0.0),
            enable_partial_fill=data.get("enable_partial_fill", True),
        )


@dataclass
class TradeRecord:
    """
    Trade execution record.
    
    Contains all details of an executed trade for audit and analysis.
    
    Attributes:
        trade_id: Unique trade identifier
        order_id: Associated order identifier
        symbol: Trading symbol
        exchange: Exchange name
        direction: Trade direction ("LONG" or "SHORT")
        offset: Trade offset ("OPEN" or "CLOSE")
        price: Execution price (Decimal)
        volume: Executed volume (Decimal)
        turnover: Trade turnover (price * volume) (Decimal)
        commission: Commission charged (Decimal)
        slippage: Slippage incurred (Decimal)
        matching_mode: Matching mode used
        l2_level: L2 simulation level (if applicable)
        queue_wait_time: Queue wait time in L2 mode (seconds)
        timestamp: Trade execution timestamp
        is_manual: Whether this was a manual trade
    
    Note:
        TD-001 Resolution: price/volume/turnover/commission/slippage use Decimal
        to avoid IEEE 754 floating-point precision errors in financial calculations.
    """
    trade_id: str
    order_id: str
    symbol: str
    exchange: str
    direction: str
    offset: str
    price: Decimal
    volume: Decimal
    turnover: Decimal
    commission: Decimal
    slippage: Decimal
    matching_mode: MatchingMode
    l2_level: Optional[L2SimulationLevel]
    queue_wait_time: Optional[float]
    timestamp: datetime
    is_manual: bool = False
    
    def __post_init__(self) -> None:
        """Validate and convert trade record after initialization."""
        # Convert to Decimal if needed (for backward compatibility with float inputs)
        self.price = to_decimal(self.price)
        self.volume = to_decimal(self.volume)
        self.turnover = to_decimal(self.turnover)
        self.commission = to_decimal(self.commission)
        self.slippage = to_decimal(self.slippage)
        
        if not self.trade_id:
            raise ValueError("trade_id must not be empty")
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
        if self.price < 0:
            raise ValueError("price must be non-negative")
        if self.volume <= 0:
            raise ValueError("volume must be positive")
        if self.commission < 0:
            raise ValueError("commission must be non-negative")
        if self.slippage < 0:
            raise ValueError("slippage must be non-negative")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (uses string for Decimal precision)."""
        return {
            "trade_id": self.trade_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "direction": self.direction,
            "offset": self.offset,
            "price": str(self.price),
            "volume": str(self.volume),
            "turnover": str(self.turnover),
            "commission": str(self.commission),
            "slippage": str(self.slippage),
            "matching_mode": self.matching_mode.value,
            "l2_level": self.l2_level.value if self.l2_level else None,
            "queue_wait_time": self.queue_wait_time,
            "timestamp": self.timestamp.isoformat(),
            "is_manual": self.is_manual,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TradeRecord:
        """Create TradeRecord from dictionary."""
        return cls(
            trade_id=data["trade_id"],
            order_id=data["order_id"],
            symbol=data["symbol"],
            exchange=data["exchange"],
            direction=data["direction"],
            offset=data["offset"],
            price=to_decimal(data["price"]),
            volume=to_decimal(data["volume"]),
            turnover=to_decimal(data["turnover"]),
            commission=to_decimal(data["commission"]),
            slippage=to_decimal(data["slippage"]),
            matching_mode=MatchingMode(data["matching_mode"]),
            l2_level=L2SimulationLevel(data["l2_level"]) if data.get("l2_level") else None,
            queue_wait_time=data.get("queue_wait_time"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            is_manual=data.get("is_manual", False),
        )


@dataclass
class MatchingQualityMetrics:
    """
    Matching quality metrics for analysis and reporting.
    
    Attributes:
        total_orders: Total number of orders processed
        filled_orders: Number of fully filled orders
        partially_filled_orders: Number of partially filled orders
        cancelled_orders: Number of cancelled orders
        rejected_orders: Number of rejected orders
        fill_rate: Ratio of filled volume to total order volume
        avg_slippage: Average slippage across all trades
        max_slippage: Maximum slippage observed
        slippage_distribution: Slippage distribution by percentile
        avg_queue_wait_time: Average queue wait time (L2 mode only)
        max_queue_wait_time: Maximum queue wait time (L2 mode only)
        total_commission: Total commission paid
        total_turnover: Total trading turnover
    """
    total_orders: int = 0
    filled_orders: int = 0
    partially_filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    fill_rate: float = 0.0
    avg_slippage: float = 0.0
    max_slippage: float = 0.0
    slippage_distribution: dict[str, float] = field(default_factory=dict)
    avg_queue_wait_time: Optional[float] = None
    max_queue_wait_time: Optional[float] = None
    total_commission: float = 0.0
    total_turnover: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_orders": self.total_orders,
            "filled_orders": self.filled_orders,
            "partially_filled_orders": self.partially_filled_orders,
            "cancelled_orders": self.cancelled_orders,
            "rejected_orders": self.rejected_orders,
            "fill_rate": self.fill_rate,
            "avg_slippage": self.avg_slippage,
            "max_slippage": self.max_slippage,
            "slippage_distribution": self.slippage_distribution,
            "avg_queue_wait_time": self.avg_queue_wait_time,
            "max_queue_wait_time": self.max_queue_wait_time,
            "total_commission": self.total_commission,
            "total_turnover": self.total_turnover,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MatchingQualityMetrics:
        """Create MatchingQualityMetrics from dictionary."""
        return cls(
            total_orders=data.get("total_orders", 0),
            filled_orders=data.get("filled_orders", 0),
            partially_filled_orders=data.get("partially_filled_orders", 0),
            cancelled_orders=data.get("cancelled_orders", 0),
            rejected_orders=data.get("rejected_orders", 0),
            fill_rate=data.get("fill_rate", 0.0),
            avg_slippage=data.get("avg_slippage", 0.0),
            max_slippage=data.get("max_slippage", 0.0),
            slippage_distribution=data.get("slippage_distribution", {}),
            avg_queue_wait_time=data.get("avg_queue_wait_time"),
            max_queue_wait_time=data.get("max_queue_wait_time"),
            total_commission=data.get("total_commission", 0.0),
            total_turnover=data.get("total_turnover", 0.0),
        )



class IMatchingEngine(ABC):
    """
    Abstract interface for the Matching Engine.
    
    The Matching Engine is responsible for simulating order execution
    during backtesting. It supports both L1 and L2 matching modes.
    """
    
    @abstractmethod
    def configure(self, config: MatchingConfig) -> None:
        """Configure matching parameters."""
        pass
    
    @abstractmethod
    def submit_order(self, order: OrderData) -> str:
        """Submit an order for matching. Returns order ID."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        pass
    
    @abstractmethod
    def process_tick(self, tick: TickData) -> list[TradeRecord]:
        """Process tick data and return any resulting trades."""
        pass
    
    @abstractmethod
    def get_quality_metrics(self) -> MatchingQualityMetrics:
        """Get matching quality metrics."""
        pass
    
    @abstractmethod
    def get_simulation_limitations(self) -> str:
        """Get description of current simulation limitations."""
        pass
    
    @abstractmethod
    def get_pending_orders(self) -> list[OrderData]:
        """Get all pending orders."""
        pass


class MatchingEngine(IMatchingEngine):
    """
    Matching engine implementation supporting L1 and L2 modes.
    
    This engine simulates order execution with configurable commission
    and slippage models. It tracks all trades and provides quality metrics.
    """
    
    # Simulation limitations descriptions
    _LIMITATIONS = {
        MatchingMode.L1: (
            "L1 Mode Limitations:\n"
            "- Assumes infinite liquidity at best bid/ask prices\n"
            "- Does not consider order book depth or queue position\n"
            "- May overestimate fill rates for large orders\n"
            "- Slippage is model-based, not market-based"
        ),
        L2SimulationLevel.LEVEL_1: (
            "L2 Level-1 (Queue Position) Limitations:\n"
            "- Queue position is estimated based on arrival time\n"
            "- Does not account for hidden orders or iceberg orders\n"
            "- Assumes FIFO execution within price levels\n"
            "- Order cancellations by other participants not modeled"
        ),
        L2SimulationLevel.LEVEL_2: (
            "L2 Level-2 (Order Book Rebuild) Limitations:\n"
            "- Requires high-quality L2 snapshot data\n"
            "- May miss intra-snapshot order book changes\n"
            "- Assumes data represents true market state\n"
            "- Does not model latency or market impact"
        ),
        L2SimulationLevel.LEVEL_3: (
            "L2 Level-3 (Microstructure) Limitations:\n"
            "- Hidden order estimation is model-dependent\n"
            "- Market maker behavior requires calibration\n"
            "- Adverse selection model may not match actual market\n"
            "- Results highly sensitive to model parameters"
        ),
    }
    
    def __init__(self, config: Optional[MatchingConfig] = None) -> None:
        """
        Initialize the matching engine.
        
        Args:
            config: Optional initial configuration. If None, uses L1 defaults.
        """
        self._config = config or MatchingConfig(mode=MatchingMode.L1)
        self._pending_orders: dict[str, OrderData] = {}
        self._trades: list[TradeRecord] = []
        self._metrics = MatchingQualityMetrics()
        
        # L2 specific state
        self._queue_positions: dict[str, float] = {}  # order_id -> estimated position
        self._order_arrival_times: dict[str, datetime] = {}
    
    def configure(self, config: MatchingConfig) -> None:
        """Configure matching parameters."""
        self._config = config
    
    def submit_order(self, order: OrderData) -> str:
        """
        Submit an order for matching.
        
        Args:
            order: The order to submit.
            
        Returns:
            The order ID.
        """
        self._pending_orders[order.order_id] = order
        self._order_arrival_times[order.order_id] = datetime.now()
        self._metrics.total_orders += 1
        return order.order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: The ID of the order to cancel.
            
        Returns:
            True if cancelled, False if order not found.
        """
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]
            if order_id in self._queue_positions:
                del self._queue_positions[order_id]
            if order_id in self._order_arrival_times:
                del self._order_arrival_times[order_id]
            self._metrics.cancelled_orders += 1
            return True
        return False
    
    def process_tick(self, tick: TickData) -> list[TradeRecord]:
        """
        Process tick data and execute matching orders.
        
        Args:
            tick: The tick data to process.
            
        Returns:
            List of trade records for executed trades.
        
        Note:
            TODO (v2.0 Optimization): Current implementation iterates through all
            pending orders on every tick (O(N) complexity). For strategies with
            thousands of limit orders (e.g., grid trading), consider implementing
            a price-time priority queue or bucket system using sortedcontainers.SortedDict
            to verify only relevant orders (e.g., Buy orders >= Tick Price).
            See: docs/audit/2026-01-05-task5-matching-engine-audit.md
        """
        if self._config.mode == MatchingMode.L1:
            return self._process_tick_l1(tick)
        else:
            return self._process_tick_l2(tick)
    
    def _process_tick_l1(self, tick: TickData) -> list[TradeRecord]:
        """Process tick with L1 matching logic."""
        trades: list[TradeRecord] = []
        orders_to_remove: list[str] = []
        
        for order_id, order in self._pending_orders.items():
            if order.symbol != tick.symbol:
                continue
            
            # Check if order can be filled
            fill_price = self._get_l1_fill_price(order, tick)
            if fill_price is None:
                continue
            
            # Calculate slippage (Decimal)
            slippage = self._calculate_slippage(order, tick, fill_price)
            
            # Apply slippage to fill price (Decimal arithmetic)
            if order.direction == "LONG":
                final_price = fill_price + slippage
            else:
                final_price = fill_price - slippage
            
            # Calculate commission (Decimal)
            turnover = final_price * order.volume
            commission = self._calculate_commission(turnover)
            
            # Create trade record
            trade = TradeRecord(
                trade_id=str(uuid.uuid4()),
                order_id=order_id,
                symbol=order.symbol,
                exchange=order.exchange,
                direction=order.direction,
                offset=order.offset,
                price=final_price,
                volume=order.volume,
                turnover=turnover,
                commission=commission,
                slippage=slippage,
                matching_mode=MatchingMode.L1,
                l2_level=None,
                queue_wait_time=None,
                timestamp=tick.datetime,
                is_manual=order.is_manual,
            )
            
            trades.append(trade)
            orders_to_remove.append(order_id)
            self._update_metrics_for_trade(trade)
        
        # Remove filled orders
        for order_id in orders_to_remove:
            del self._pending_orders[order_id]
            self._metrics.filled_orders += 1
        
        self._trades.extend(trades)
        return trades
    
    def _get_l1_fill_price(self, order: OrderData, tick: TickData) -> Optional[Decimal]:
        """Get fill price for L1 matching (returns Decimal)."""
        if order.direction == "LONG":
            # Buy orders fill at ask price
            if order.price == 0:  # Market order
                return tick.ask_price_1
            elif order.price >= tick.ask_price_1:  # Limit order crosses spread
                return tick.ask_price_1
        else:
            # Sell orders fill at bid price
            if order.price == 0:  # Market order
                return tick.bid_price_1
            elif order.price <= tick.bid_price_1:  # Limit order crosses spread
                return tick.bid_price_1
        
        return None
    
    def _process_tick_l2(self, tick: TickData) -> list[TradeRecord]:
        """Process tick with L2 matching logic."""
        trades: list[TradeRecord] = []
        orders_to_remove: list[str] = []
        
        for order_id, order in self._pending_orders.items():
            if order.symbol != tick.symbol:
                continue
            
            # Update queue position
            queue_wait_time = self._update_queue_position(order_id, order, tick)
            
            # Check if order can be filled based on L2 logic
            fill_result = self._check_l2_fill(order, tick, queue_wait_time)
            if fill_result is None:
                continue
            
            fill_price, fill_volume = fill_result
            
            # Calculate slippage (Decimal)
            slippage = self._calculate_slippage(order, tick, fill_price)
            
            # Apply slippage (Decimal arithmetic)
            if order.direction == "LONG":
                final_price = fill_price + slippage
            else:
                final_price = fill_price - slippage
            
            # Calculate commission (Decimal)
            turnover = final_price * fill_volume
            commission = self._calculate_commission(turnover)
            
            # Create trade record
            trade = TradeRecord(
                trade_id=str(uuid.uuid4()),
                order_id=order_id,
                symbol=order.symbol,
                exchange=order.exchange,
                direction=order.direction,
                offset=order.offset,
                price=final_price,
                volume=fill_volume,
                turnover=turnover,
                commission=commission,
                slippage=slippage,
                matching_mode=MatchingMode.L2,
                l2_level=self._config.l2_level,
                queue_wait_time=queue_wait_time,
                timestamp=tick.datetime,
                is_manual=order.is_manual,
            )
            
            trades.append(trade)
            
            # Check if fully filled
            if fill_volume >= order.remaining:
                orders_to_remove.append(order_id)
                self._metrics.filled_orders += 1
            else:
                # Partial fill - update order
                self._metrics.partially_filled_orders += 1
            
            self._update_metrics_for_trade(trade)
        
        # Remove filled orders
        for order_id in orders_to_remove:
            del self._pending_orders[order_id]
            if order_id in self._queue_positions:
                del self._queue_positions[order_id]
            if order_id in self._order_arrival_times:
                del self._order_arrival_times[order_id]
        
        self._trades.extend(trades)
        return trades
    
    def _update_queue_position(
        self, order_id: str, order: OrderData, tick: TickData
    ) -> float:
        """Update and return queue wait time for an order."""
        arrival_time = self._order_arrival_times.get(order_id, tick.datetime)
        wait_time = (tick.datetime - arrival_time).total_seconds()
        
        # Estimate queue position based on simulation level
        if self._config.l2_level == L2SimulationLevel.LEVEL_1:
            # Simple queue position estimation
            self._queue_positions[order_id] = wait_time
        elif self._config.l2_level == L2SimulationLevel.LEVEL_2:
            # Use order book data if available
            if tick.has_l2_data:
                self._queue_positions[order_id] = self._estimate_queue_from_book(
                    order, tick
                )
            else:
                self._queue_positions[order_id] = wait_time
        else:  # LEVEL_3
            # Advanced microstructure estimation
            self._queue_positions[order_id] = self._estimate_queue_microstructure(
                order, tick, wait_time
            )
        
        return wait_time
    
    def _estimate_queue_from_book(self, order: OrderData, tick: TickData) -> float:
        """Estimate queue position from order book data."""
        if order.direction == "LONG":
            # For buy orders, look at bid side
            if tick.bid_prices and tick.bid_volumes:
                for i, price in enumerate(tick.bid_prices):
                    if order.price >= price:
                        # Estimate position based on volume ahead
                        return sum(tick.bid_volumes[:i+1])
        else:
            # For sell orders, look at ask side
            if tick.ask_prices and tick.ask_volumes:
                for i, price in enumerate(tick.ask_prices):
                    if order.price <= price:
                        return sum(tick.ask_volumes[:i+1])
        return 0.0
    
    def _estimate_queue_microstructure(
        self, order: OrderData, tick: TickData, wait_time: float
    ) -> float:
        """Estimate queue position with microstructure model."""
        # Simplified microstructure model
        # In production, this would include hidden order estimation
        base_position = self._estimate_queue_from_book(order, tick)
        
        # Add estimated hidden liquidity (simplified model)
        hidden_factor = 1.2  # Assume 20% hidden liquidity
        return base_position * hidden_factor
    
    def _check_l2_fill(
        self, order: OrderData, tick: TickData, queue_wait_time: float
    ) -> Optional[tuple[Decimal, Decimal]]:
        """
        Check if order can be filled in L2 mode.
        
        Returns:
            Tuple of (fill_price, fill_volume) as Decimals or None if no fill.
        """
        # Market orders always fill
        if order.price == 0:
            if order.direction == "LONG":
                return (tick.ask_price_1, order.remaining)
            else:
                return (tick.bid_price_1, order.remaining)
        
        # Limit orders need price and queue check
        if order.direction == "LONG":
            if order.price >= tick.ask_price_1:
                # Price crosses spread - immediate fill
                return (tick.ask_price_1, order.remaining)
            elif order.price >= tick.bid_price_1:
                # At or better than best bid - check queue
                if self._check_queue_fill(order, tick, queue_wait_time):
                    return (order.price, order.remaining)
        else:
            if order.price <= tick.bid_price_1:
                # Price crosses spread - immediate fill
                return (tick.bid_price_1, order.remaining)
            elif order.price <= tick.ask_price_1:
                # At or better than best ask - check queue
                if self._check_queue_fill(order, tick, queue_wait_time):
                    return (order.price, order.remaining)
        
        return None
    
    def _check_queue_fill(
        self, order: OrderData, tick: TickData, queue_wait_time: float
    ) -> bool:
        """Check if order at queue position can be filled."""
        # Simplified queue fill logic
        # In production, this would use actual volume data
        min_wait_time = 1.0  # Minimum 1 second wait
        
        if self._config.l2_level == L2SimulationLevel.LEVEL_1:
            return queue_wait_time >= min_wait_time
        elif self._config.l2_level == L2SimulationLevel.LEVEL_2:
            # Check against traded volume
            return queue_wait_time >= min_wait_time and tick.volume > 0
        else:  # LEVEL_3
            # More conservative fill estimation
            return queue_wait_time >= min_wait_time * 2 and tick.volume > order.volume
    
    def _calculate_slippage(
        self, order: OrderData, tick: TickData, base_price: Decimal
    ) -> Decimal:
        """Calculate slippage based on configured model (returns Decimal)."""
        slippage_value = to_decimal(self._config.slippage_value)
        
        if self._config.slippage_model == SlippageModel.FIXED:
            return slippage_value * base_price
        
        elif self._config.slippage_model == SlippageModel.VOLUME_BASED:
            # Slippage increases with order size relative to market volume
            if tick.volume > 0:
                volume_ratio = order.volume / tick.volume
                return slippage_value * base_price * (Decimal("1") + volume_ratio)
            return slippage_value * base_price
        
        elif self._config.slippage_model == SlippageModel.VOLATILITY_BASED:
            # Slippage based on spread as volatility proxy
            spread_ratio = tick.spread / tick.mid_price if tick.mid_price > 0 else Decimal("0")
            return slippage_value * base_price * (Decimal("1") + spread_ratio * Decimal("10"))
        
        return Decimal("0")
    
    def _calculate_commission(self, turnover: Decimal) -> Decimal:
        """Calculate commission for a trade (returns Decimal)."""
        commission_rate = to_decimal(self._config.commission_rate)
        min_commission = to_decimal(self._config.min_commission)
        commission = turnover * commission_rate
        return max(commission, min_commission)
    
    def _update_metrics_for_trade(self, trade: TradeRecord) -> None:
        """Update metrics after a trade (handles Decimal values)."""
        # Convert Decimal to float for metrics (metrics use float for simplicity)
        self._metrics.total_turnover += float(trade.turnover)
        self._metrics.total_commission += float(trade.commission)
        
        # Update slippage metrics
        trade_slippage = float(trade.slippage)
        if self._metrics.max_slippage < trade_slippage:
            self._metrics.max_slippage = trade_slippage
        
        # Update average slippage
        n = len(self._trades)
        if n > 0:
            self._metrics.avg_slippage = (
                (self._metrics.avg_slippage * (n - 1) + trade_slippage) / n
            )
        
        # Update queue wait time metrics (L2 only)
        if trade.queue_wait_time is not None:
            if self._metrics.max_queue_wait_time is None:
                self._metrics.max_queue_wait_time = trade.queue_wait_time
            else:
                self._metrics.max_queue_wait_time = max(
                    self._metrics.max_queue_wait_time, trade.queue_wait_time
                )
            
            if self._metrics.avg_queue_wait_time is None:
                self._metrics.avg_queue_wait_time = trade.queue_wait_time
            else:
                self._metrics.avg_queue_wait_time = (
                    (self._metrics.avg_queue_wait_time * (n - 1) + trade.queue_wait_time) / n
                )
        
        # Update fill rate
        total_volume = sum(float(t.volume) for t in self._trades)
        total_order_volume = total_volume + sum(
            float(o.remaining) for o in self._pending_orders.values()
        )
        if total_order_volume > 0:
            self._metrics.fill_rate = total_volume / total_order_volume
    
    def get_quality_metrics(self) -> MatchingQualityMetrics:
        """Get matching quality metrics."""
        # Calculate slippage distribution (convert Decimal to float for metrics)
        if self._trades:
            slippages = sorted([float(t.slippage) for t in self._trades])
            n = len(slippages)
            self._metrics.slippage_distribution = {
                "p25": slippages[int(n * 0.25)] if n > 0 else 0.0,
                "p50": slippages[int(n * 0.50)] if n > 0 else 0.0,
                "p75": slippages[int(n * 0.75)] if n > 0 else 0.0,
                "p95": slippages[int(n * 0.95)] if n > 0 else 0.0,
            }
        
        return self._metrics
    
    def get_simulation_limitations(self) -> str:
        """Get description of current simulation limitations."""
        if self._config.mode == MatchingMode.L1:
            return self._LIMITATIONS[MatchingMode.L1]
        else:
            return self._LIMITATIONS.get(
                self._config.l2_level,
                "Unknown simulation level"
            )
    
    def get_pending_orders(self) -> list[OrderData]:
        """Get all pending orders."""
        return list(self._pending_orders.values())
    
    def get_trades(self) -> list[TradeRecord]:
        """Get all executed trades."""
        return self._trades.copy()
    
    def reset(self) -> None:
        """Reset the matching engine state."""
        self._pending_orders.clear()
        self._trades.clear()
        self._metrics = MatchingQualityMetrics()
        self._queue_positions.clear()
        self._order_arrival_times.clear()


__all__ = [
    "MatchingMode",
    "L2SimulationLevel",
    "SlippageModel",
    "MatchingConfig",
    "TradeRecord",
    "MatchingQualityMetrics",
    "IMatchingEngine",
    "MatchingEngine",
]
