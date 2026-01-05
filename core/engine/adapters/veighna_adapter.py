"""
Titan-Quant VeighNa Engine Adapter

This module implements the IEngineAdapter interface for the VeighNa trading framework,
enabling Titan-Quant to use VeighNa's backtesting and trading capabilities.

VeighNa (formerly vnpy) is a popular open-source quantitative trading framework
that provides comprehensive backtesting and live trading functionality.

Requirements:
    - 1.2: Core_Engine SHALL 通过 Engine_Adapter 接口与底层框架解耦，
           支持 VeighNa、自研引擎等多种实现

Note:
    This adapter provides a bridge between Titan-Quant and VeighNa.
    When VeighNa is not installed, the adapter will operate in stub mode
    for testing and development purposes.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Optional, Union

from core.engine.adapter import (
    BacktestMode,
    BacktestResult,
    EngineConfig,
    EngineState,
    IEngineAdapter,
)
from core.engine.types import BarData, OrderData, TickData
from core.exceptions import EngineError, ErrorCodes

logger = logging.getLogger(__name__)


# Try to import VeighNa components
# If not available, we'll use stub implementations
try:
    from vnpy.trader.constant import Direction as VnDirection
    from vnpy.trader.constant import Exchange as VnExchange
    from vnpy.trader.constant import Offset as VnOffset
    from vnpy.trader.constant import Status as VnStatus
    from vnpy.trader.object import BarData as VnBarData
    from vnpy.trader.object import OrderData as VnOrderData
    from vnpy.trader.object import TickData as VnTickData
    from vnpy_ctastrategy.backtesting import BacktestingEngine
    
    VEIGHNA_AVAILABLE = True
except ImportError:
    VEIGHNA_AVAILABLE = False
    logger.warning(
        "VeighNa (vnpy) is not installed. VeighNaAdapter will operate in stub mode. "
        "Install vnpy to enable full functionality: pip install vnpy vnpy_ctastrategy"
    )


class VeighNaAdapter(IEngineAdapter):
    """
    VeighNa engine adapter implementation.
    
    This adapter wraps VeighNa's BacktestingEngine to provide a unified
    interface for the Titan-Quant system. It handles:
    - Engine initialization and configuration
    - Strategy loading and management
    - Backtest execution control (start, pause, resume, step, stop)
    - Order management
    - Position and account queries
    - Event callbacks
    
    When VeighNa is not installed, the adapter operates in stub mode,
    providing basic functionality for testing and development.
    
    Attributes:
        _engine: The underlying VeighNa BacktestingEngine instance
        _state: Current engine state
        _config: Engine configuration
        _strategies: Dictionary of loaded strategies
        _orders: Dictionary of submitted orders
        _callbacks: Dictionary of registered callbacks
        _current_datetime: Current simulation datetime
        _replay_speed: Replay speed multiplier
    
    Example:
        >>> adapter = VeighNaAdapter()
        >>> adapter.initialize({"initial_capital": 1000000})
        >>> strategy_id = adapter.load_strategy(MyStrategy, {"fast_period": 10})
        >>> adapter.start_backtest(datetime(2023, 1, 1), datetime(2023, 12, 31))
    """
    
    ENGINE_NAME = "VeighNa"
    ENGINE_VERSION = "3.0.0"  # VeighNa version we're targeting
    
    def __init__(self) -> None:
        """Initialize the VeighNa adapter."""
        self._engine: Any = None
        self._state: EngineState = EngineState.STOPPED
        self._config: Optional[EngineConfig] = None
        self._strategies: dict[str, Any] = {}
        self._orders: dict[str, OrderData] = {}
        self._callbacks: dict[str, tuple[str, Callable[[Any], None]]] = {}
        self._current_datetime: Optional[datetime] = None
        self._replay_speed: float = 1.0
        self._positions: dict[str, Any] = {}
        self._account: dict[str, Any] = {
            "balance": 0.0,
            "available": 0.0,
            "frozen": 0.0,
        }
        self._backtest_result: Optional[BacktestResult] = None
        self._is_veighna_available = VEIGHNA_AVAILABLE
    
    def initialize(self, config: Union[dict[str, Any], EngineConfig]) -> bool:
        """
        Initialize the VeighNa engine with configuration.
        
        Args:
            config: Engine configuration parameters.
        
        Returns:
            True if initialization successful.
        
        Raises:
            EngineError: If initialization fails.
        """
        try:
            self._state = EngineState.INITIALIZING
            
            # Parse configuration
            if isinstance(config, dict):
                self._config = EngineConfig.from_dict(config)
            else:
                self._config = config
            
            # Initialize account with starting capital
            self._account = {
                "balance": self._config.initial_capital,
                "available": self._config.initial_capital,
                "frozen": 0.0,
            }
            
            if self._is_veighna_available:
                # Initialize VeighNa BacktestingEngine
                self._engine = BacktestingEngine()
                self._engine.set_parameters(
                    capital=self._config.initial_capital,
                    rate=self._config.commission_rate,
                    slippage=self._config.slippage,
                )
                logger.info("VeighNa BacktestingEngine initialized successfully")
            else:
                # Stub mode - no actual engine
                logger.info("VeighNaAdapter initialized in stub mode (VeighNa not installed)")
            
            self._state = EngineState.STOPPED
            return True
            
        except Exception as e:
            self._state = EngineState.ERROR
            raise EngineError(
                message=f"Failed to initialize VeighNa engine: {e}",
                error_code=ErrorCodes.ENGINE_INIT_FAILED,
                engine_name=self.ENGINE_NAME,
            ) from e
    
    def load_strategy(self, strategy_class: type, params: dict[str, Any]) -> str:
        """
        Load a strategy into the engine.
        
        Args:
            strategy_class: The strategy class to instantiate.
            params: Strategy parameters.
        
        Returns:
            Strategy ID string.
        """
        strategy_id = f"strategy_{uuid.uuid4().hex[:8]}"
        
        self._strategies[strategy_id] = {
            "class": strategy_class,
            "params": params,
            "instance": None,
        }
        
        if self._is_veighna_available and self._engine:
            # Add strategy to VeighNa engine
            self._engine.add_strategy(
                strategy_class,
                params,
            )
        
        logger.info(f"Strategy loaded: {strategy_id} ({strategy_class.__name__})")
        return strategy_id
    
    def unload_strategy(self, strategy_id: str) -> bool:
        """
        Unload a strategy from the engine.
        
        Args:
            strategy_id: The strategy ID to unload.
        
        Returns:
            True if successful.
        """
        if strategy_id in self._strategies:
            del self._strategies[strategy_id]
            logger.info(f"Strategy unloaded: {strategy_id}")
            return True
        return False
    
    def start_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        symbols: Optional[list[str]] = None
    ) -> bool:
        """
        Start backtesting.
        
        Args:
            start_date: Backtest start date.
            end_date: Backtest end date.
            symbols: Optional list of symbols.
        
        Returns:
            True if started successfully.
        """
        if self._state == EngineState.RUNNING:
            logger.warning("Backtest is already running")
            return False
        
        self._current_datetime = start_date
        self._state = EngineState.RUNNING
        
        if self._is_veighna_available and self._engine:
            # Configure and run VeighNa backtest
            self._engine.set_parameters(
                start=start_date,
                end=end_date,
            )
            # Note: Actual execution would be handled by VeighNa's run_backtesting()
        
        logger.info(f"Backtest started: {start_date} to {end_date}")
        return True
    
    def pause(self) -> bool:
        """Pause the running backtest."""
        if self._state != EngineState.RUNNING:
            return False
        
        self._state = EngineState.PAUSED
        logger.info("Backtest paused")
        return True
    
    def resume(self) -> bool:
        """Resume a paused backtest."""
        if self._state != EngineState.PAUSED:
            return False
        
        self._state = EngineState.RUNNING
        logger.info("Backtest resumed")
        return True
    
    def step(self) -> bool:
        """
        Execute a single step in the backtest.
        
        Returns:
            True if step executed, False if backtest is complete.
        """
        if self._state not in (EngineState.RUNNING, EngineState.PAUSED):
            return False
        
        # In stub mode, just advance the datetime
        if self._current_datetime:
            # Advance by one minute (default step)
            from datetime import timedelta
            self._current_datetime += timedelta(minutes=1)
        
        logger.debug(f"Step executed: {self._current_datetime}")
        return True
    
    def stop(self) -> bool:
        """Stop the running backtest."""
        if self._state == EngineState.STOPPED:
            return False
        
        self._state = EngineState.STOPPED
        
        # Generate stub backtest result
        if self._config:
            self._backtest_result = BacktestResult(
                total_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=len([o for o in self._orders.values() if o.status == "FILLED"]),
                start_date=self._current_datetime or datetime.now(),
                end_date=datetime.now(),
                final_capital=self._account["balance"],
            )
        
        logger.info("Backtest stopped")
        return True
    
    def get_state(self) -> EngineState:
        """Get the current engine state."""
        return self._state
    
    def get_engine_name(self) -> str:
        """Get the engine name."""
        return self.ENGINE_NAME
    
    def get_engine_version(self) -> str:
        """Get the engine version."""
        if self._is_veighna_available:
            try:
                import vnpy
                return getattr(vnpy, "__version__", self.ENGINE_VERSION)
            except Exception:
                pass
        return self.ENGINE_VERSION
    
    def submit_order(self, order: OrderData) -> str:
        """
        Submit an order to the engine.
        
        Args:
            order: Order data to submit.
        
        Returns:
            Order ID string.
        """
        self._orders[order.order_id] = order
        
        # Trigger order callbacks
        self._trigger_callbacks("order", order)
        
        logger.info(f"Order submitted: {order.order_id}")
        return order.order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: The order ID to cancel.
        
        Returns:
            True if successful.
        """
        if order_id not in self._orders:
            return False
        
        order = self._orders[order_id]
        if not order.is_active:
            return False
        
        # Create updated order with cancelled status
        cancelled_order = OrderData(
            order_id=order.order_id,
            symbol=order.symbol,
            exchange=order.exchange,
            direction=order.direction,
            offset=order.offset,
            price=order.price,
            volume=order.volume,
            traded=order.traded,
            status="CANCELLED",
            is_manual=order.is_manual,
            create_time=order.create_time,
            update_time=datetime.now(),
            strategy_id=order.strategy_id,
            reference=order.reference,
        )
        self._orders[order_id] = cancelled_order
        
        logger.info(f"Order cancelled: {order_id}")
        return True
    
    def get_order(self, order_id: str) -> Optional[OrderData]:
        """Get order by ID."""
        return self._orders.get(order_id)
    
    def get_all_orders(self) -> list[OrderData]:
        """Get all orders."""
        return list(self._orders.values())
    
    def get_active_orders(self) -> list[OrderData]:
        """Get all active orders."""
        return [o for o in self._orders.values() if o.is_active]
    
    def get_positions(self) -> dict[str, Any]:
        """Get current positions."""
        return self._positions.copy()
    
    def get_account(self) -> dict[str, Any]:
        """Get account information."""
        return self._account.copy()
    
    def get_backtest_result(self) -> Optional[BacktestResult]:
        """Get backtest result."""
        return self._backtest_result
    
    def set_replay_speed(self, speed: float) -> bool:
        """
        Set the replay speed multiplier.
        
        Args:
            speed: Speed multiplier (1.0 = normal).
        
        Returns:
            True if successful.
        """
        if speed <= 0:
            return False
        
        self._replay_speed = speed
        logger.info(f"Replay speed set to {speed}x")
        return True
    
    def get_current_datetime(self) -> Optional[datetime]:
        """Get the current simulation datetime."""
        return self._current_datetime
    
    def register_callback(
        self,
        event_type: str,
        callback: Callable[[Any], None]
    ) -> str:
        """
        Register a callback for engine events.
        
        Args:
            event_type: Type of event (e.g., "tick", "bar", "trade", "order")
            callback: Callback function.
        
        Returns:
            Callback ID.
        """
        callback_id = f"cb_{uuid.uuid4().hex[:8]}"
        self._callbacks[callback_id] = (event_type, callback)
        logger.debug(f"Callback registered: {callback_id} for {event_type}")
        return callback_id
    
    def unregister_callback(self, callback_id: str) -> bool:
        """
        Unregister a callback.
        
        Args:
            callback_id: The callback ID to unregister.
        
        Returns:
            True if successful.
        """
        if callback_id in self._callbacks:
            del self._callbacks[callback_id]
            logger.debug(f"Callback unregistered: {callback_id}")
            return True
        return False
    
    def _trigger_callbacks(self, event_type: str, data: Any) -> None:
        """
        Trigger all callbacks for a specific event type.
        
        Args:
            event_type: The event type.
            data: Event data to pass to callbacks.
        """
        for callback_id, (cb_type, callback) in self._callbacks.items():
            if cb_type == event_type:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Callback {callback_id} error: {e}")
    
    # VeighNa-specific helper methods
    
    def is_veighna_available(self) -> bool:
        """Check if VeighNa is available."""
        return self._is_veighna_available
    
    def get_underlying_engine(self) -> Any:
        """
        Get the underlying VeighNa engine instance.
        
        Returns:
            VeighNa BacktestingEngine instance or None if not available.
        """
        return self._engine


__all__ = [
    "VeighNaAdapter",
    "VEIGHNA_AVAILABLE",
]
