"""
Titan-Quant Snapshot Manager

This module implements the snapshot mechanism for state persistence and recovery.
Snapshots capture the complete system state including account, positions,
strategy variables, event queue position, and data stream position.

Requirements:
    - 5.5: WHEN 用户点击"保存快照", THEN THE Replay_Controller SHALL 将以下内容序列化到磁盘
    - 5.6: WHEN 用户加载快照, THEN THE Replay_Controller SHALL 完整恢复上述所有状态
    - 5.7: THE Snapshot SHALL 包含版本号，WHEN 快照版本与当前系统版本不兼容, 
           THEN THE Replay_Controller SHALL 拒绝加载并提示用户
"""
from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.exceptions import SnapshotError, ErrorCodes


@dataclass
class AccountState:
    """
    Account state snapshot.
    
    Captures the financial state of the trading account at a specific point in time.
    
    Attributes:
        cash: Available cash balance (not including margin)
        frozen_margin: Margin currently used for open positions
        available_balance: Total available balance (cash - frozen_margin)
        total_equity: Total account equity including unrealized P&L
        unrealized_pnl: Total unrealized profit/loss from open positions
    """
    cash: float
    frozen_margin: float
    available_balance: float
    total_equity: float = 0.0
    unrealized_pnl: float = 0.0
    
    def __post_init__(self) -> None:
        """Validate account state after initialization."""
        if self.cash < 0:
            raise ValueError("cash must be non-negative")
        if self.frozen_margin < 0:
            raise ValueError("frozen_margin must be non-negative")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "cash": self.cash,
            "frozen_margin": self.frozen_margin,
            "available_balance": self.available_balance,
            "total_equity": self.total_equity,
            "unrealized_pnl": self.unrealized_pnl,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AccountState:
        """Create AccountState from dictionary."""
        return cls(
            cash=data["cash"],
            frozen_margin=data["frozen_margin"],
            available_balance=data["available_balance"],
            total_equity=data.get("total_equity", 0.0),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
        )


@dataclass
class PositionState:
    """
    Position state snapshot.
    
    Captures the state of a single position at a specific point in time.
    
    Attributes:
        symbol: Trading symbol (e.g., "BTC_USDT")
        exchange: Exchange name (e.g., "binance")
        direction: Position direction ("LONG" or "SHORT")
        volume: Position size/quantity
        cost_price: Average entry price
        unrealized_pnl: Current unrealized profit/loss
        margin: Margin used for this position
        open_time: When the position was opened
    """
    symbol: str
    exchange: str
    direction: str  # "LONG" | "SHORT"
    volume: float
    cost_price: float
    unrealized_pnl: float
    margin: float = 0.0
    open_time: Optional[datetime] = None
    
    def __post_init__(self) -> None:
        """Validate position state after initialization."""
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.exchange:
            raise ValueError("exchange must not be empty")
        if self.direction not in ("LONG", "SHORT"):
            raise ValueError("direction must be 'LONG' or 'SHORT'")
        if self.volume < 0:
            raise ValueError("volume must be non-negative")
        if self.cost_price < 0:
            raise ValueError("cost_price must be non-negative")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "direction": self.direction,
            "volume": self.volume,
            "cost_price": self.cost_price,
            "unrealized_pnl": self.unrealized_pnl,
            "margin": self.margin,
        }
        if self.open_time:
            result["open_time"] = self.open_time.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PositionState:
        """Create PositionState from dictionary."""
        open_time = None
        if data.get("open_time"):
            open_time = datetime.fromisoformat(data["open_time"])
        return cls(
            symbol=data["symbol"],
            exchange=data["exchange"],
            direction=data["direction"],
            volume=data["volume"],
            cost_price=data["cost_price"],
            unrealized_pnl=data["unrealized_pnl"],
            margin=data.get("margin", 0.0),
            open_time=open_time,
        )


@dataclass
class StrategyState:
    """
    Strategy state snapshot.
    
    Captures the complete state of a strategy instance including all
    parameters and state variables.
    
    Attributes:
        strategy_id: Unique identifier for the strategy instance
        class_name: Name of the strategy class
        parameters: Strategy configuration parameters
        variables: All state variables (indicators, counters, etc.)
        is_active: Whether the strategy is currently active
    """
    strategy_id: str
    class_name: str
    parameters: Dict[str, Any]
    variables: Dict[str, Any]
    is_active: bool = True
    
    def __post_init__(self) -> None:
        """Validate strategy state after initialization."""
        if not self.strategy_id:
            raise ValueError("strategy_id must not be empty")
        if not self.class_name:
            raise ValueError("class_name must not be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy_id": self.strategy_id,
            "class_name": self.class_name,
            "parameters": self.parameters,
            "variables": self.variables,
            "is_active": self.is_active,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategyState:
        """Create StrategyState from dictionary."""
        return cls(
            strategy_id=data["strategy_id"],
            class_name=data["class_name"],
            parameters=data["parameters"],
            variables=data["variables"],
            is_active=data.get("is_active", True),
        )


@dataclass
class Snapshot:
    """
    Complete system state snapshot.
    
    Captures the entire system state at a specific point in time, enabling
    full state restoration for debugging, replay, and crash recovery.
    
    The snapshot includes:
    - Version information for compatibility checking
    - Account financial state
    - All open positions
    - Strategy instances with their state variables
    - Event bus state (sequence number and pending events)
    - Data stream position (timestamp and index)
    
    Attributes:
        version: Snapshot format version for compatibility checking
        snapshot_id: Unique identifier for this snapshot
        create_time: When the snapshot was created
        account: Account financial state
        positions: List of all open positions
        strategies: List of all strategy states
        event_sequence: Current event bus sequence number
        pending_events: Events waiting to be processed
        data_timestamp: Current position in the data stream (time)
        data_index: Current position in the data stream (index)
        backtest_id: Associated backtest ID (optional)
        description: User-provided description (optional)
    """
    version: str
    snapshot_id: str
    create_time: datetime
    account: AccountState
    positions: List[PositionState]
    strategies: List[StrategyState]
    event_sequence: int
    pending_events: List[Dict[str, Any]]
    data_timestamp: datetime
    data_index: int
    backtest_id: Optional[str] = None
    description: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate snapshot after initialization."""
        if not self.version:
            raise ValueError("version must not be empty")
        if not self.snapshot_id:
            raise ValueError("snapshot_id must not be empty")
        if self.event_sequence < 0:
            raise ValueError("event_sequence must be non-negative")
        if self.data_index < 0:
            raise ValueError("data_index must be non-negative")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert snapshot to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the snapshot suitable for
            JSON serialization and storage.
        """
        result = {
            "version": self.version,
            "snapshot_id": self.snapshot_id,
            "create_time": self.create_time.isoformat(),
            "account": self.account.to_dict(),
            "positions": [p.to_dict() for p in self.positions],
            "strategies": [s.to_dict() for s in self.strategies],
            "event_sequence": self.event_sequence,
            "pending_events": self.pending_events,
            "data_timestamp": self.data_timestamp.isoformat(),
            "data_index": self.data_index,
        }
        if self.backtest_id:
            result["backtest_id"] = self.backtest_id
        if self.description:
            result["description"] = self.description
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Snapshot:
        """
        Create a Snapshot from a dictionary.
        
        Args:
            data: Dictionary containing snapshot data.
        
        Returns:
            Snapshot instance created from the dictionary.
        
        Raises:
            KeyError: If required keys are missing.
            ValueError: If data validation fails.
        """
        return cls(
            version=data["version"],
            snapshot_id=data["snapshot_id"],
            create_time=datetime.fromisoformat(data["create_time"]),
            account=AccountState.from_dict(data["account"]),
            positions=[PositionState.from_dict(p) for p in data["positions"]],
            strategies=[StrategyState.from_dict(s) for s in data["strategies"]],
            event_sequence=data["event_sequence"],
            pending_events=data["pending_events"],
            data_timestamp=datetime.fromisoformat(data["data_timestamp"]),
            data_index=data["data_index"],
            backtest_id=data.get("backtest_id"),
            description=data.get("description"),
        )


class ISnapshotManager(ABC):
    """
    Abstract interface for the Snapshot Manager.
    
    The Snapshot Manager is responsible for creating, saving, loading,
    and restoring system state snapshots. It ensures version compatibility
    and data integrity during snapshot operations.
    """
    
    # Current snapshot format version
    CURRENT_VERSION = "1.0.0"
    
    @abstractmethod
    def create_snapshot(
        self,
        account: AccountState,
        positions: List[PositionState],
        strategies: List[StrategyState],
        event_sequence: int,
        pending_events: List[Dict[str, Any]],
        data_timestamp: datetime,
        data_index: int,
        backtest_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Snapshot:
        """
        Create a new snapshot of the current system state.
        
        Args:
            account: Current account state
            positions: List of current positions
            strategies: List of strategy states
            event_sequence: Current event bus sequence number
            pending_events: Pending events in the queue
            data_timestamp: Current data stream timestamp
            data_index: Current data stream index
            backtest_id: Optional associated backtest ID
            description: Optional user description
        
        Returns:
            A new Snapshot instance capturing the current state.
        """
        pass
    
    @abstractmethod
    def save_snapshot(self, snapshot: Snapshot, path: str) -> bool:
        """
        Save a snapshot to disk.
        
        Args:
            snapshot: The snapshot to save
            path: File path to save the snapshot
        
        Returns:
            True if save was successful, False otherwise.
        
        Raises:
            SnapshotError: If save operation fails.
        """
        pass
    
    @abstractmethod
    def load_snapshot(self, path: str) -> Optional[Snapshot]:
        """
        Load a snapshot from disk.
        
        Args:
            path: File path to load the snapshot from
        
        Returns:
            The loaded Snapshot, or None if file doesn't exist.
        
        Raises:
            SnapshotError: If load operation fails or data is corrupted.
        """
        pass
    
    @abstractmethod
    def restore_snapshot(self, snapshot: Snapshot) -> bool:
        """
        Restore system state from a snapshot.
        
        This method should be overridden by implementations that have
        access to the actual system components (EventBus, Engine, etc.).
        
        Args:
            snapshot: The snapshot to restore from
        
        Returns:
            True if restoration was successful, False otherwise.
        
        Raises:
            SnapshotError: If restoration fails.
        """
        pass
    
    @abstractmethod
    def is_compatible(self, snapshot: Snapshot) -> bool:
        """
        Check if a snapshot is compatible with the current system version.
        
        Args:
            snapshot: The snapshot to check
        
        Returns:
            True if the snapshot is compatible, False otherwise.
        """
        pass


class SnapshotManager(ISnapshotManager):
    """
    Implementation of the Snapshot Manager.
    
    Provides functionality for creating, saving, loading, and validating
    system state snapshots. Uses JSON serialization for storage.
    
    Example:
        >>> manager = SnapshotManager()
        >>> snapshot = manager.create_snapshot(
        ...     account=AccountState(cash=100000, frozen_margin=0, available_balance=100000),
        ...     positions=[],
        ...     strategies=[],
        ...     event_sequence=0,
        ...     pending_events=[],
        ...     data_timestamp=datetime.now(),
        ...     data_index=0
        ... )
        >>> manager.save_snapshot(snapshot, "snapshots/test.json")
        True
        >>> loaded = manager.load_snapshot("snapshots/test.json")
        >>> loaded.snapshot_id == snapshot.snapshot_id
        True
    """
    
    # Compatible versions (can load snapshots from these versions)
    COMPATIBLE_VERSIONS = {"1.0.0"}
    
    def __init__(self) -> None:
        """Initialize the Snapshot Manager."""
        pass
    
    def create_snapshot(
        self,
        account: AccountState,
        positions: List[PositionState],
        strategies: List[StrategyState],
        event_sequence: int,
        pending_events: List[Dict[str, Any]],
        data_timestamp: datetime,
        data_index: int,
        backtest_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Snapshot:
        """
        Create a new snapshot of the current system state.
        
        Args:
            account: Current account state
            positions: List of current positions
            strategies: List of strategy states
            event_sequence: Current event bus sequence number
            pending_events: Pending events in the queue
            data_timestamp: Current data stream timestamp
            data_index: Current data stream index
            backtest_id: Optional associated backtest ID
            description: Optional user description
        
        Returns:
            A new Snapshot instance capturing the current state.
        """
        snapshot_id = str(uuid.uuid4())
        create_time = datetime.now()
        
        return Snapshot(
            version=self.CURRENT_VERSION,
            snapshot_id=snapshot_id,
            create_time=create_time,
            account=account,
            positions=positions,
            strategies=strategies,
            event_sequence=event_sequence,
            pending_events=pending_events,
            data_timestamp=data_timestamp,
            data_index=data_index,
            backtest_id=backtest_id,
            description=description,
        )
    
    def save_snapshot(self, snapshot: Snapshot, path: str) -> bool:
        """
        Save a snapshot to disk as JSON.
        
        Args:
            snapshot: The snapshot to save
            path: File path to save the snapshot
        
        Returns:
            True if save was successful.
        
        Raises:
            SnapshotError: If save operation fails.
        """
        try:
            file_path = Path(path)
            
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert snapshot to dictionary
            snapshot_dict = snapshot.to_dict()
            
            # Write to file with pretty formatting
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(snapshot_dict, f, indent=2, ensure_ascii=False)
            
            return True
            
        except (OSError, IOError) as e:
            raise SnapshotError(
                message=f"Failed to save snapshot: {e}",
                error_code=ErrorCodes.SNAPSHOT_CORRUPTED,
                snapshot_id=snapshot.snapshot_id,
                details={"path": path, "error": str(e)},
            )
        except (TypeError, ValueError) as e:
            raise SnapshotError(
                message=f"Failed to serialize snapshot: {e}",
                error_code=ErrorCodes.SNAPSHOT_CORRUPTED,
                snapshot_id=snapshot.snapshot_id,
                details={"path": path, "error": str(e)},
            )
    
    def load_snapshot(self, path: str) -> Optional[Snapshot]:
        """
        Load a snapshot from disk.
        
        Args:
            path: File path to load the snapshot from
        
        Returns:
            The loaded Snapshot, or None if file doesn't exist.
        
        Raises:
            SnapshotError: If load operation fails or data is corrupted.
        """
        file_path = Path(path)
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                snapshot_dict = json.load(f)
            
            snapshot = Snapshot.from_dict(snapshot_dict)
            
            # Check version compatibility
            if not self.is_compatible(snapshot):
                raise SnapshotError(
                    message=f"Snapshot version {snapshot.version} is not compatible "
                            f"with current version {self.CURRENT_VERSION}",
                    error_code=ErrorCodes.SNAPSHOT_VERSION_MISMATCH,
                    snapshot_id=snapshot.snapshot_id,
                    snapshot_version=snapshot.version,
                    details={
                        "snapshot_version": snapshot.version,
                        "current_version": self.CURRENT_VERSION,
                        "compatible_versions": list(self.COMPATIBLE_VERSIONS),
                    },
                )
            
            return snapshot
            
        except json.JSONDecodeError as e:
            raise SnapshotError(
                message=f"Failed to parse snapshot JSON: {e}",
                error_code=ErrorCodes.SNAPSHOT_CORRUPTED,
                details={"path": path, "error": str(e)},
            )
        except KeyError as e:
            raise SnapshotError(
                message=f"Snapshot is missing required field: {e}",
                error_code=ErrorCodes.SNAPSHOT_CORRUPTED,
                details={"path": path, "missing_field": str(e)},
            )
        except (ValueError, TypeError) as e:
            raise SnapshotError(
                message=f"Invalid snapshot data: {e}",
                error_code=ErrorCodes.SNAPSHOT_CORRUPTED,
                details={"path": path, "error": str(e)},
            )
    
    def restore_snapshot(self, snapshot: Snapshot) -> bool:
        """
        Validate that a snapshot can be restored.
        
        This base implementation only validates the snapshot structure.
        Actual restoration requires access to system components and should
        be implemented by a subclass or the ReplayController.
        
        Args:
            snapshot: The snapshot to validate for restoration
        
        Returns:
            True if the snapshot is valid and can be restored.
        
        Raises:
            SnapshotError: If the snapshot is invalid or incompatible.
        """
        # Check version compatibility
        if not self.is_compatible(snapshot):
            raise SnapshotError(
                message=f"Cannot restore: snapshot version {snapshot.version} "
                        f"is not compatible with current version {self.CURRENT_VERSION}",
                error_code=ErrorCodes.SNAPSHOT_VERSION_MISMATCH,
                snapshot_id=snapshot.snapshot_id,
                snapshot_version=snapshot.version,
            )
        
        # Validate snapshot structure
        try:
            # Ensure all required fields are present and valid
            assert snapshot.account is not None
            assert snapshot.positions is not None
            assert snapshot.strategies is not None
            assert snapshot.event_sequence >= 0
            assert snapshot.data_index >= 0
            return True
        except AssertionError as e:
            raise SnapshotError(
                message=f"Snapshot validation failed: {e}",
                error_code=ErrorCodes.SNAPSHOT_RESTORE_FAILED,
                snapshot_id=snapshot.snapshot_id,
            )
    
    def is_compatible(self, snapshot: Snapshot) -> bool:
        """
        Check if a snapshot is compatible with the current system version.
        
        Args:
            snapshot: The snapshot to check
        
        Returns:
            True if the snapshot version is in the compatible versions set.
        """
        return snapshot.version in self.COMPATIBLE_VERSIONS


__all__ = [
    "AccountState",
    "PositionState",
    "StrategyState",
    "Snapshot",
    "ISnapshotManager",
    "SnapshotManager",
]
