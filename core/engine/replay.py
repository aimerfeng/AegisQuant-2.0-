"""
Titan-Quant Replay Controller

This module implements the replay controller for backtest playback control.
The ReplayController provides VCR-like controls including pause, resume,
step, and speed adjustment, integrated with EventBus and SnapshotManager.

Requirements:
    - 5.1: THE Replay_Controller SHALL 在界面底部提供播放条，支持暂停、播放、2x/4x/10x 加速、单步调试
    - 5.2: WHEN 用户点击暂停, THEN THE Replay_Controller SHALL 立即冻结回测状态
    - 5.3: WHEN 用户点击单步调试, THEN THE Replay_Controller SHALL 前进一个时间单位并更新所有视图
    - 5.4: WHEN 用户调整播放速度, THEN THE Replay_Controller SHALL 按指定倍速推进回测时间
"""
from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from core.engine.event import Event, EventType
from core.engine.event_bus import EventBus, IEventBus
from core.engine.snapshot import (
    AccountState,
    PositionState,
    StrategyState,
    Snapshot,
    SnapshotManager,
    ISnapshotManager,
)
from core.exceptions import EngineError, SnapshotError, ErrorCodes


class ReplayState(Enum):
    """
    Enumeration of replay controller states.
    
    The replay controller can be in one of the following states:
    - IDLE: Not started, waiting for initialization
    - PLAYING: Actively replaying events at the configured speed
    - PAUSED: Replay is paused, state is frozen
    - STEPPING: Single-step mode, advances one event at a time
    - STOPPED: Replay has ended or been stopped
    """
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STEPPING = "stepping"
    STOPPED = "stopped"


class ReplaySpeed(Enum):
    """
    Enumeration of supported replay speeds.
    
    Speed multipliers for replay playback:
    - SPEED_1X: Real-time playback (1x)
    - SPEED_2X: Double speed (2x)
    - SPEED_4X: Quadruple speed (4x)
    - SPEED_10X: Ten times speed (10x)
    - SPEED_MAX: Maximum speed (no delay)
    """
    SPEED_1X = 1.0
    SPEED_2X = 2.0
    SPEED_4X = 4.0
    SPEED_10X = 10.0
    SPEED_MAX = float('inf')


@dataclass
class ReplayConfig:
    """
    Configuration for the replay controller.
    
    Attributes:
        initial_speed: Initial replay speed multiplier
        time_unit_ms: Base time unit in milliseconds for single step
        auto_snapshot_interval: Interval for automatic snapshots (in events)
        snapshot_dir: Directory for saving snapshots
    """
    initial_speed: ReplaySpeed = ReplaySpeed.SPEED_1X
    time_unit_ms: float = 1000.0  # 1 second default
    auto_snapshot_interval: int = 1000  # Auto snapshot every 1000 events
    snapshot_dir: str = "database/snapshots"


@dataclass
class ReplayStatus:
    """
    Current status of the replay controller.
    
    Attributes:
        state: Current replay state
        speed: Current replay speed
        current_time: Current simulation time
        current_index: Current data index
        event_sequence: Current event sequence number
        total_events: Total events processed
        progress_percent: Progress percentage (0-100)
    """
    state: ReplayState
    speed: ReplaySpeed
    current_time: datetime
    current_index: int
    event_sequence: int
    total_events: int
    progress_percent: float


# Type alias for data provider callback
DataProvider = Callable[[int], Optional[Dict[str, Any]]]
# Type alias for state update callback
StateUpdateCallback = Callable[[ReplayStatus], None]


class IReplayController(ABC):
    """
    Abstract interface for the Replay Controller.
    
    The Replay Controller provides VCR-like controls for backtest playback,
    including pause, resume, step, and speed adjustment. It integrates with
    the EventBus for event processing and SnapshotManager for state persistence.
    """
    
    @abstractmethod
    def initialize(
        self,
        event_bus: IEventBus,
        snapshot_manager: ISnapshotManager,
        data_provider: DataProvider,
        start_time: datetime,
        end_time: datetime,
        total_data_points: int,
    ) -> bool:
        """
        Initialize the replay controller.
        
        Args:
            event_bus: Event bus for publishing events
            snapshot_manager: Snapshot manager for state persistence
            data_provider: Callback to get data at a specific index
            start_time: Start time of the replay
            end_time: End time of the replay
            total_data_points: Total number of data points to replay
        
        Returns:
            True if initialization was successful.
        """
        pass
    
    @abstractmethod
    def play(self) -> bool:
        """
        Start or resume replay playback.
        
        Returns:
            True if playback started successfully.
        """
        pass
    
    @abstractmethod
    def pause(self) -> bool:
        """
        Pause replay playback immediately.
        
        Freezes the current backtest state. All views should stop updating.
        
        Returns:
            True if pause was successful.
        """
        pass
    
    @abstractmethod
    def resume(self) -> bool:
        """
        Resume replay from paused state.
        
        Returns:
            True if resume was successful.
        """
        pass
    
    @abstractmethod
    def step(self) -> bool:
        """
        Advance replay by exactly one time unit.
        
        Processes exactly one data point and updates all views.
        
        Returns:
            True if step was successful, False if at end of data.
        """
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """
        Stop replay completely.
        
        Returns:
            True if stop was successful.
        """
        pass
    
    @abstractmethod
    def set_speed(self, speed: ReplaySpeed) -> bool:
        """
        Set the replay speed.
        
        Args:
            speed: The new replay speed multiplier.
        
        Returns:
            True if speed was set successfully.
        """
        pass
    
    @abstractmethod
    def get_status(self) -> ReplayStatus:
        """
        Get the current replay status.
        
        Returns:
            Current replay status including state, speed, and progress.
        """
        pass
    
    @abstractmethod
    def save_snapshot(self, description: Optional[str] = None) -> str:
        """
        Save a snapshot of the current state.
        
        Args:
            description: Optional description for the snapshot.
        
        Returns:
            Path to the saved snapshot file.
        """
        pass
    
    @abstractmethod
    def load_snapshot(self, path: str) -> bool:
        """
        Load and restore state from a snapshot.
        
        Args:
            path: Path to the snapshot file.
        
        Returns:
            True if snapshot was loaded and restored successfully.
        """
        pass
    
    @abstractmethod
    def seek_to_index(self, index: int) -> bool:
        """
        Seek to a specific data index.
        
        Args:
            index: The data index to seek to.
        
        Returns:
            True if seek was successful.
        """
        pass
    
    @abstractmethod
    def seek_to_time(self, timestamp: datetime) -> bool:
        """
        Seek to a specific timestamp.
        
        Args:
            timestamp: The timestamp to seek to.
        
        Returns:
            True if seek was successful.
        """
        pass


class ReplayController(IReplayController):
    """
    Implementation of the Replay Controller.
    
    Provides VCR-like controls for backtest playback with integration
    to EventBus and SnapshotManager. Supports pause, resume, step,
    and variable speed playback.
    
    Thread Safety:
        All public methods are thread-safe. The replay loop runs in a
        separate thread and can be controlled from the main thread.
    
    Example:
        >>> event_bus = EventBus()
        >>> snapshot_manager = SnapshotManager()
        >>> controller = ReplayController()
        >>> controller.initialize(
        ...     event_bus=event_bus,
        ...     snapshot_manager=snapshot_manager,
        ...     data_provider=lambda i: {"price": 100 + i},
        ...     start_time=datetime(2024, 1, 1),
        ...     end_time=datetime(2024, 1, 31),
        ...     total_data_points=1000
        ... )
        >>> controller.play()
        >>> controller.pause()
        >>> controller.step()
        >>> controller.save_snapshot("Before trade")
    """
    
    def __init__(self, config: Optional[ReplayConfig] = None) -> None:
        """
        Initialize the Replay Controller.
        
        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self._config = config or ReplayConfig()
        self._lock = threading.RLock()
        
        # Core components (set during initialize)
        self._event_bus: Optional[IEventBus] = None
        self._snapshot_manager: Optional[ISnapshotManager] = None
        self._data_provider: Optional[DataProvider] = None
        
        # Replay state
        self._state = ReplayState.IDLE
        self._speed = self._config.initial_speed
        self._current_index = 0
        self._current_time: Optional[datetime] = None
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._total_data_points = 0
        self._total_events_processed = 0
        
        # Account and position state (for snapshots)
        self._account_state: Optional[AccountState] = None
        self._positions: List[PositionState] = []
        self._strategies: List[StrategyState] = []
        
        # Backtest ID
        self._backtest_id: Optional[str] = None
        
        # Threading
        self._replay_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._step_event = threading.Event()
        
        # Callbacks
        self._status_callbacks: List[StateUpdateCallback] = []
    
    def initialize(
        self,
        event_bus: IEventBus,
        snapshot_manager: ISnapshotManager,
        data_provider: DataProvider,
        start_time: datetime,
        end_time: datetime,
        total_data_points: int,
    ) -> bool:
        """
        Initialize the replay controller with required components.
        
        Args:
            event_bus: Event bus for publishing events
            snapshot_manager: Snapshot manager for state persistence
            data_provider: Callback to get data at a specific index
            start_time: Start time of the replay
            end_time: End time of the replay
            total_data_points: Total number of data points to replay
        
        Returns:
            True if initialization was successful.
        
        Raises:
            EngineError: If initialization fails.
        """
        with self._lock:
            if self._state not in (ReplayState.IDLE, ReplayState.STOPPED):
                raise EngineError(
                    message="Cannot initialize while replay is active",
                    error_code=ErrorCodes.ENGINE_INIT_FAILED,
                    details={"current_state": self._state.value},
                )
            
            self._event_bus = event_bus
            self._snapshot_manager = snapshot_manager
            self._data_provider = data_provider
            self._start_time = start_time
            self._end_time = end_time
            self._current_time = start_time
            self._total_data_points = total_data_points
            self._current_index = 0
            self._total_events_processed = 0
            self._backtest_id = str(uuid.uuid4())
            
            # Initialize default account state
            self._account_state = AccountState(
                cash=1000000.0,
                frozen_margin=0.0,
                available_balance=1000000.0,
                total_equity=1000000.0,
                unrealized_pnl=0.0,
            )
            self._positions = []
            self._strategies = []
            
            # Reset events
            self._stop_event.clear()
            self._pause_event.set()  # Start paused
            self._step_event.clear()
            
            self._state = ReplayState.PAUSED
            self._notify_status_change()
            
            return True
    
    def play(self) -> bool:
        """
        Start or resume replay playback.
        
        Starts the replay loop in a separate thread if not already running.
        
        Returns:
            True if playback started successfully.
        """
        with self._lock:
            if self._state == ReplayState.IDLE:
                raise EngineError(
                    message="Replay controller not initialized",
                    error_code=ErrorCodes.ENGINE_NOT_INITIALIZED,
                )
            
            if self._state == ReplayState.STOPPED:
                # Reset for new playback
                self._current_index = 0
                self._current_time = self._start_time
                self._total_events_processed = 0
                self._stop_event.clear()
            
            self._state = ReplayState.PLAYING
            self._pause_event.clear()  # Allow replay to proceed
            
            # Start replay thread if not running
            if self._replay_thread is None or not self._replay_thread.is_alive():
                self._replay_thread = threading.Thread(
                    target=self._replay_loop,
                    daemon=True,
                    name="ReplayController-Loop"
                )
                self._replay_thread.start()
            
            self._notify_status_change()
            return True
    
    def pause(self) -> bool:
        """
        Pause replay playback immediately.
        
        Freezes the current backtest state.
        
        Returns:
            True if pause was successful.
        """
        with self._lock:
            if self._state not in (ReplayState.PLAYING, ReplayState.STEPPING):
                return False
            
            self._state = ReplayState.PAUSED
            self._pause_event.set()  # Signal pause
            self._notify_status_change()
            return True
    
    def resume(self) -> bool:
        """
        Resume replay from paused state.
        
        Returns:
            True if resume was successful.
        """
        with self._lock:
            if self._state != ReplayState.PAUSED:
                return False
            
            return self.play()
    
    def step(self) -> bool:
        """
        Advance replay by exactly one time unit.
        
        Processes exactly one data point and updates all views.
        This is the core method for single-step debugging.
        
        Returns:
            True if step was successful, False if at end of data.
        """
        with self._lock:
            if self._state == ReplayState.IDLE:
                raise EngineError(
                    message="Replay controller not initialized",
                    error_code=ErrorCodes.ENGINE_NOT_INITIALIZED,
                )
            
            if self._current_index >= self._total_data_points:
                self._state = ReplayState.STOPPED
                self._notify_status_change()
                return False
            
            # Process exactly one data point
            success = self._process_single_step()
            
            if success:
                self._state = ReplayState.PAUSED
                self._notify_status_change()
            
            return success
    
    def stop(self) -> bool:
        """
        Stop replay completely.
        
        Returns:
            True if stop was successful.
        """
        with self._lock:
            self._stop_event.set()
            self._pause_event.clear()  # Release any waiting
            self._state = ReplayState.STOPPED
            
            # Wait for replay thread to finish
            if self._replay_thread and self._replay_thread.is_alive():
                self._replay_thread.join(timeout=2.0)
            
            self._notify_status_change()
            return True
    
    def set_speed(self, speed: ReplaySpeed) -> bool:
        """
        Set the replay speed.
        
        Args:
            speed: The new replay speed multiplier.
        
        Returns:
            True if speed was set successfully.
        """
        with self._lock:
            self._speed = speed
            self._notify_status_change()
            return True
    
    def get_status(self) -> ReplayStatus:
        """
        Get the current replay status.
        
        Returns:
            Current replay status including state, speed, and progress.
        """
        with self._lock:
            progress = 0.0
            if self._total_data_points > 0:
                progress = (self._current_index / self._total_data_points) * 100.0
            
            event_sequence = 0
            if self._event_bus:
                event_sequence = self._event_bus.get_current_sequence()
            
            return ReplayStatus(
                state=self._state,
                speed=self._speed,
                current_time=self._current_time or datetime.now(),
                current_index=self._current_index,
                event_sequence=event_sequence,
                total_events=self._total_events_processed,
                progress_percent=progress,
            )
    
    def save_snapshot(self, description: Optional[str] = None) -> str:
        """
        Save a snapshot of the current state.
        
        Args:
            description: Optional description for the snapshot.
        
        Returns:
            Path to the saved snapshot file.
        
        Raises:
            SnapshotError: If snapshot save fails.
        """
        with self._lock:
            if not self._snapshot_manager or not self._event_bus:
                raise EngineError(
                    message="Replay controller not initialized",
                    error_code=ErrorCodes.ENGINE_NOT_INITIALIZED,
                )
            
            # Get pending events from event bus
            pending_events = [
                e.to_dict() for e in self._event_bus.get_pending_events()
            ]
            
            # Create snapshot
            snapshot = self._snapshot_manager.create_snapshot(
                account=self._account_state or AccountState(
                    cash=0, frozen_margin=0, available_balance=0
                ),
                positions=self._positions,
                strategies=self._strategies,
                event_sequence=self._event_bus.get_current_sequence(),
                pending_events=pending_events,
                data_timestamp=self._current_time or datetime.now(),
                data_index=self._current_index,
                backtest_id=self._backtest_id,
                description=description,
            )
            
            # Generate snapshot path
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_path = f"{self._config.snapshot_dir}/{self._backtest_id}_{timestamp_str}.json"
            
            # Save snapshot
            self._snapshot_manager.save_snapshot(snapshot, snapshot_path)
            
            return snapshot_path
    
    def load_snapshot(self, path: str) -> bool:
        """
        Load and restore state from a snapshot.
        
        Args:
            path: Path to the snapshot file.
        
        Returns:
            True if snapshot was loaded and restored successfully.
        
        Raises:
            SnapshotError: If snapshot load or restore fails.
        """
        with self._lock:
            if not self._snapshot_manager:
                raise EngineError(
                    message="Replay controller not initialized",
                    error_code=ErrorCodes.ENGINE_NOT_INITIALIZED,
                )
            
            # Pause if playing
            was_playing = self._state == ReplayState.PLAYING
            if was_playing:
                self.pause()
            
            # Load snapshot
            snapshot = self._snapshot_manager.load_snapshot(path)
            if not snapshot:
                raise SnapshotError(
                    message=f"Snapshot not found: {path}",
                    error_code=ErrorCodes.SNAPSHOT_NOT_FOUND,
                    details={"path": path},
                )
            
            # Validate compatibility
            if not self._snapshot_manager.is_compatible(snapshot):
                raise SnapshotError(
                    message=f"Snapshot version {snapshot.version} is not compatible",
                    error_code=ErrorCodes.SNAPSHOT_VERSION_MISMATCH,
                    snapshot_id=snapshot.snapshot_id,
                    snapshot_version=snapshot.version,
                )
            
            # Restore state
            self._account_state = snapshot.account
            self._positions = snapshot.positions
            self._strategies = snapshot.strategies
            self._current_index = snapshot.data_index
            self._current_time = snapshot.data_timestamp
            
            # Reset event bus if needed
            if self._event_bus and hasattr(self._event_bus, 'reset'):
                self._event_bus.reset()
            
            self._state = ReplayState.PAUSED
            self._notify_status_change()
            
            return True
    
    def seek_to_index(self, index: int) -> bool:
        """
        Seek to a specific data index.
        
        Args:
            index: The data index to seek to.
        
        Returns:
            True if seek was successful.
        """
        with self._lock:
            if index < 0 or index >= self._total_data_points:
                return False
            
            # Pause if playing
            was_playing = self._state == ReplayState.PLAYING
            if was_playing:
                self.pause()
            
            self._current_index = index
            
            # Update current time based on data at index
            if self._data_provider:
                data = self._data_provider(index)
                if data and "timestamp" in data:
                    if isinstance(data["timestamp"], datetime):
                        self._current_time = data["timestamp"]
                    elif isinstance(data["timestamp"], str):
                        self._current_time = datetime.fromisoformat(data["timestamp"])
            
            self._notify_status_change()
            return True
    
    def seek_to_time(self, timestamp: datetime) -> bool:
        """
        Seek to a specific timestamp.
        
        This performs a linear search to find the closest data point.
        For large datasets, consider implementing binary search.
        
        Args:
            timestamp: The timestamp to seek to.
        
        Returns:
            True if seek was successful.
        """
        with self._lock:
            if not self._data_provider:
                return False
            
            # Linear search for the closest timestamp
            # TODO: Implement binary search for large datasets
            best_index = 0
            best_diff = float('inf')
            
            for i in range(self._total_data_points):
                data = self._data_provider(i)
                if data and "timestamp" in data:
                    data_time = data["timestamp"]
                    if isinstance(data_time, str):
                        data_time = datetime.fromisoformat(data_time)
                    
                    diff = abs((data_time - timestamp).total_seconds())
                    if diff < best_diff:
                        best_diff = diff
                        best_index = i
                    
                    # Early exit if we've passed the target
                    if data_time > timestamp and diff > best_diff:
                        break
            
            return self.seek_to_index(best_index)
    
    def set_account_state(self, account: AccountState) -> None:
        """
        Update the account state (for external updates).
        
        Args:
            account: New account state.
        """
        with self._lock:
            self._account_state = account
    
    def set_positions(self, positions: List[PositionState]) -> None:
        """
        Update the positions list (for external updates).
        
        Args:
            positions: New positions list.
        """
        with self._lock:
            self._positions = positions
    
    def set_strategies(self, strategies: List[StrategyState]) -> None:
        """
        Update the strategies list (for external updates).
        
        Args:
            strategies: New strategies list.
        """
        with self._lock:
            self._strategies = strategies
    
    def register_status_callback(self, callback: StateUpdateCallback) -> None:
        """
        Register a callback for status updates.
        
        Args:
            callback: Function to call when status changes.
        """
        with self._lock:
            self._status_callbacks.append(callback)
    
    def unregister_status_callback(self, callback: StateUpdateCallback) -> None:
        """
        Unregister a status callback.
        
        Args:
            callback: The callback to remove.
        """
        with self._lock:
            if callback in self._status_callbacks:
                self._status_callbacks.remove(callback)
    
    def _replay_loop(self) -> None:
        """
        Main replay loop running in a separate thread.
        
        Processes data points at the configured speed until stopped or paused.
        """
        while not self._stop_event.is_set():
            # Check for pause
            if self._pause_event.is_set():
                time.sleep(0.01)  # Small sleep to prevent busy waiting
                continue
            
            with self._lock:
                if self._current_index >= self._total_data_points:
                    self._state = ReplayState.STOPPED
                    self._notify_status_change()
                    break
                
                # Process one data point
                self._process_single_step()
            
            # Calculate delay based on speed
            if self._speed != ReplaySpeed.SPEED_MAX:
                delay = self._config.time_unit_ms / 1000.0 / self._speed.value
                time.sleep(delay)
    
    def _process_single_step(self) -> bool:
        """
        Process exactly one data point.
        
        This is the core method that advances the simulation by one step.
        
        Returns:
            True if processing was successful.
        """
        if not self._data_provider or not self._event_bus:
            return False
        
        # Get data at current index
        data = self._data_provider(self._current_index)
        if data is None:
            return False
        
        # Extract timestamp from data
        data_timestamp = self._current_time
        if "timestamp" in data:
            if isinstance(data["timestamp"], datetime):
                data_timestamp = data["timestamp"]
            elif isinstance(data["timestamp"], str):
                data_timestamp = datetime.fromisoformat(data["timestamp"])
        
        # Determine event type based on data
        event_type = EventType.BAR
        if "last_price" in data or "bid_price_1" in data:
            event_type = EventType.TICK
        
        # Publish event to event bus with simulation timestamp
        self._event_bus.publish(
            event_type=event_type,
            data=data,
            source="replay_controller",
            timestamp=data_timestamp,
        )
        
        # Update state
        self._current_index += 1
        self._current_time = data_timestamp
        self._total_events_processed += 1
        
        return True
    
    def _notify_status_change(self) -> None:
        """Notify all registered callbacks of status change."""
        status = self.get_status()
        for callback in self._status_callbacks:
            try:
                callback(status)
            except Exception:
                pass  # Ignore callback errors


__all__ = [
    "ReplayState",
    "ReplaySpeed",
    "ReplayConfig",
    "ReplayStatus",
    "IReplayController",
    "ReplayController",
    "DataProvider",
    "StateUpdateCallback",
]
