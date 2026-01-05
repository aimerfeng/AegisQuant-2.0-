"""
Titan-Quant Engine Adapter Interface

This module defines the abstract interface for engine adapters, enabling
the system to work with different trading frameworks (VeighNa, custom engines, etc.)
through a unified interface.

Requirements:
    - 1.2: Core_Engine SHALL 通过 Engine_Adapter 接口与底层框架解耦，
           支持 VeighNa、自研引擎等多种实现
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from typing import Any, Callable, Optional, Union

from core.engine.types import BarData, OrderData, TickData


class EngineState(Enum):
    """Engine running state."""
    STOPPED = "stopped"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class BacktestMode(Enum):
    """Backtest execution mode."""
    SINGLE_THREAD = "single_thread"  # Deterministic, for backtesting
    MULTI_PROCESS = "multi_process"  # Parallel, for optimization


@dataclass
class EngineConfig:
    """
    Engine configuration parameters.
    
    Attributes:
        initial_capital: Starting capital for backtest
        commission_rate: Trading commission rate
        slippage: Slippage value
        data_path: Path to market data
        log_level: Logging level
        mode: Backtest execution mode
    """
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    slippage: float = 0.0001
    data_path: str = "./database"
    log_level: str = "INFO"
    mode: BacktestMode = BacktestMode.SINGLE_THREAD
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "initial_capital": self.initial_capital,
            "commission_rate": self.commission_rate,
            "slippage": self.slippage,
            "data_path": self.data_path,
            "log_level": self.log_level,
            "mode": self.mode.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EngineConfig:
        """Create from dictionary."""
        mode = data.get("mode", "single_thread")
        if isinstance(mode, str):
            mode = BacktestMode(mode)
        return cls(
            initial_capital=data.get("initial_capital", 1_000_000.0),
            commission_rate=data.get("commission_rate", 0.0003),
            slippage=data.get("slippage", 0.0001),
            data_path=data.get("data_path", "./database"),
            log_level=data.get("log_level", "INFO"),
            mode=mode,
        )


@dataclass
class BacktestResult:
    """
    Backtest result summary.
    
    Attributes:
        total_return: Total return percentage
        sharpe_ratio: Sharpe ratio
        max_drawdown: Maximum drawdown percentage
        win_rate: Win rate percentage
        profit_factor: Profit factor
        total_trades: Total number of trades
        start_date: Backtest start date
        end_date: Backtest end date
        final_capital: Final capital value
    """
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    start_date: datetime
    end_date: datetime
    final_capital: float
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "final_capital": self.final_capital,
        }


# Type alias for strategy callback
StrategyCallback = Callable[[Union[BarData, TickData]], None]


class IEngineAdapter(ABC):
    """
    Abstract base class for engine adapters.
    
    This interface defines the contract that all engine adapters must implement,
    allowing the Titan-Quant system to work with different trading frameworks
    (VeighNa, custom engines, etc.) through a unified interface.
    
    The adapter pattern enables:
    - Decoupling from specific trading frameworks
    - Easy switching between different engines
    - Consistent API for backtesting and live trading
    - Testability through mock implementations
    
    Implementations:
    - VeighNaAdapter: Adapter for VeighNa trading framework
    - CustomAdapter: Custom engine implementation (future)
    
    Example:
        >>> adapter = VeighNaAdapter()
        >>> adapter.initialize(config)
        >>> strategy_id = adapter.load_strategy(MyStrategy, {"param1": 10})
        >>> adapter.start_backtest(start_date, end_date)
    """
    
    @abstractmethod
    def initialize(self, config: Union[dict[str, Any], EngineConfig]) -> bool:
        """
        Initialize the engine with configuration.
        
        Args:
            config: Engine configuration, either as a dictionary or EngineConfig object.
                   Should include initial_capital, commission_rate, slippage, etc.
        
        Returns:
            True if initialization successful, False otherwise.
        
        Raises:
            EngineError: If initialization fails due to invalid config or system error.
        """
        pass
    
    @abstractmethod
    def load_strategy(self, strategy_class: type, params: dict[str, Any]) -> str:
        """
        Load a strategy into the engine.
        
        Args:
            strategy_class: The strategy class to instantiate.
            params: Strategy parameters dictionary.
        
        Returns:
            Strategy ID string for future reference.
        
        Raises:
            StrategyError: If strategy loading fails.
        """
        pass
    
    @abstractmethod
    def unload_strategy(self, strategy_id: str) -> bool:
        """
        Unload a strategy from the engine.
        
        Args:
            strategy_id: The strategy ID returned by load_strategy.
        
        Returns:
            True if unloading successful, False otherwise.
        """
        pass
    
    @abstractmethod
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
            symbols: Optional list of symbols to backtest. If None, uses all loaded symbols.
        
        Returns:
            True if backtest started successfully, False otherwise.
        
        Raises:
            EngineError: If backtest cannot be started.
        """
        pass
    
    @abstractmethod
    def pause(self) -> bool:
        """
        Pause the running backtest.
        
        Returns:
            True if paused successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def resume(self) -> bool:
        """
        Resume a paused backtest.
        
        Returns:
            True if resumed successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def step(self) -> bool:
        """
        Execute a single step (one time unit) in the backtest.
        
        This is used for single-step debugging mode.
        
        Returns:
            True if step executed successfully, False if backtest is complete.
        """
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """
        Stop the running backtest.
        
        Returns:
            True if stopped successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_state(self) -> EngineState:
        """
        Get the current engine state.
        
        Returns:
            Current EngineState enum value.
        """
        pass
    
    @abstractmethod
    def get_engine_name(self) -> str:
        """
        Get the name of the underlying engine.
        
        Returns:
            Engine name string (e.g., "VeighNa", "Custom").
        """
        pass
    
    @abstractmethod
    def get_engine_version(self) -> str:
        """
        Get the version of the underlying engine.
        
        Returns:
            Engine version string.
        """
        pass
    
    @abstractmethod
    def submit_order(self, order: OrderData) -> str:
        """
        Submit an order to the engine.
        
        Args:
            order: Order data to submit.
        
        Returns:
            Order ID string.
        
        Raises:
            EngineError: If order submission fails.
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: The order ID to cancel.
        
        Returns:
            True if cancellation successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_order(self, order_id: str) -> Optional[OrderData]:
        """
        Get order information by ID.
        
        Args:
            order_id: The order ID to query.
        
        Returns:
            OrderData if found, None otherwise.
        """
        pass
    
    @abstractmethod
    def get_all_orders(self) -> list[OrderData]:
        """
        Get all orders.
        
        Returns:
            List of all OrderData objects.
        """
        pass
    
    @abstractmethod
    def get_active_orders(self) -> list[OrderData]:
        """
        Get all active (unfilled) orders.
        
        Returns:
            List of active OrderData objects.
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> dict[str, Any]:
        """
        Get current positions.
        
        Returns:
            Dictionary mapping symbol to position information.
        """
        pass
    
    @abstractmethod
    def get_account(self) -> dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Dictionary containing account balance, margin, etc.
        """
        pass
    
    @abstractmethod
    def get_backtest_result(self) -> Optional[BacktestResult]:
        """
        Get backtest result after completion.
        
        Returns:
            BacktestResult if backtest is complete, None otherwise.
        """
        pass
    
    @abstractmethod
    def set_replay_speed(self, speed: float) -> bool:
        """
        Set the replay speed multiplier.
        
        Args:
            speed: Speed multiplier (1.0 = normal, 2.0 = 2x, etc.)
        
        Returns:
            True if speed set successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_current_datetime(self) -> Optional[datetime]:
        """
        Get the current simulation datetime.
        
        Returns:
            Current datetime in the simulation, None if not running.
        """
        pass
    
    @abstractmethod
    def register_callback(
        self,
        event_type: str,
        callback: Callable[[Any], None]
    ) -> str:
        """
        Register a callback for engine events.
        
        Args:
            event_type: Type of event to listen for (e.g., "tick", "bar", "trade")
            callback: Callback function to invoke when event occurs.
        
        Returns:
            Callback ID for future unregistration.
        """
        pass
    
    @abstractmethod
    def unregister_callback(self, callback_id: str) -> bool:
        """
        Unregister a previously registered callback.
        
        Args:
            callback_id: The callback ID returned by register_callback.
        
        Returns:
            True if unregistration successful, False otherwise.
        """
        pass


__all__ = [
    "EngineState",
    "BacktestMode",
    "EngineConfig",
    "BacktestResult",
    "StrategyCallback",
    "IEngineAdapter",
]
