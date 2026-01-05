"""
Titan-Quant Event Bus

This module implements the core event bus for the event-driven architecture.
The EventBus guarantees deterministic event processing through monotonically
increasing sequence numbers and supports event replay for debugging and
snapshot restoration.

Requirements:
    - 1.6: Event_Bus SHALL 保证事件处理的顺序确定性
    - 1.7: Event_Bus SHALL 使用单调递增的事件序号标识每个事件，支持事件回溯和重放

Technical Debt Resolution (TD-004):
    - Added HeartbeatMonitor for detecting strategy handler blocking >100ms
    - Watchdog thread monitors handler execution time
    - Callback mechanism for alerting on slow handlers

Note on Event History:
    The in-memory event history is a "hot buffer" for UI catch-up and short-term
    replay. For full crash recovery from sequence 0, use the Snapshot mechanism
    (Task 9) or implement an EventPersister to Parquet/SQLite.
"""
from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from core.engine.event import Event, EventType
from core.exceptions import EngineError, ErrorCodes


# Type alias for event handlers
EventHandler = Callable[[Event], None]

# Type alias for slow handler callback
SlowHandlerCallback = Callable[[str, str, float], None]  # (subscription_id, handler_name, duration_ms)


@dataclass
class HandlerExecutionInfo:
    """Information about a handler execution for monitoring."""
    subscription_id: str
    handler_name: str
    start_time: float
    event_type: EventType


class HeartbeatMonitor:
    """
    Watchdog monitor for detecting slow/blocking event handlers.
    
    Technical Debt Resolution (TD-004):
        Monitors handler execution time and alerts when handlers block >threshold_ms.
        This prevents silent stalls in the event bus when strategy handlers block.
    
    Example:
        >>> monitor = HeartbeatMonitor(threshold_ms=100)
        >>> monitor.set_slow_handler_callback(lambda sid, name, dur: print(f"Slow: {name}"))
        >>> monitor.start()
        >>> # ... handlers are monitored ...
        >>> monitor.stop()
    """
    
    def __init__(self, threshold_ms: float = 100.0, check_interval_ms: float = 50.0) -> None:
        """
        Initialize the heartbeat monitor.
        
        Args:
            threshold_ms: Threshold in milliseconds for slow handler detection (default: 100ms)
            check_interval_ms: How often to check for slow handlers (default: 50ms)
        """
        self._threshold_ms = threshold_ms
        self._check_interval_ms = check_interval_ms
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Currently executing handlers
        self._active_handlers: dict[str, HandlerExecutionInfo] = {}
        
        # Callback for slow handler alerts
        self._slow_handler_callback: Optional[SlowHandlerCallback] = None
        
        # Statistics
        self._slow_handler_count = 0
        self._total_handler_calls = 0
    
    def set_slow_handler_callback(self, callback: SlowHandlerCallback) -> None:
        """Set callback to be invoked when a slow handler is detected."""
        self._slow_handler_callback = callback
    
    def start(self) -> None:
        """Start the heartbeat monitor thread."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="HeartbeatMonitor",
            daemon=True
        )
        self._monitor_thread.start()
    
    def stop(self) -> None:
        """Stop the heartbeat monitor thread."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None
    
    def handler_started(
        self, subscription_id: str, handler_name: str, event_type: EventType
    ) -> None:
        """Record that a handler has started execution."""
        with self._lock:
            self._active_handlers[subscription_id] = HandlerExecutionInfo(
                subscription_id=subscription_id,
                handler_name=handler_name,
                start_time=time.perf_counter(),
                event_type=event_type,
            )
            self._total_handler_calls += 1
    
    def handler_finished(self, subscription_id: str) -> Optional[float]:
        """
        Record that a handler has finished execution.
        
        Returns:
            Duration in milliseconds, or None if handler wasn't tracked.
        """
        with self._lock:
            info = self._active_handlers.pop(subscription_id, None)
            if info:
                duration_ms = (time.perf_counter() - info.start_time) * 1000
                return duration_ms
            return None
    
    def _monitor_loop(self) -> None:
        """Background thread that checks for slow handlers."""
        while not self._stop_event.wait(timeout=self._check_interval_ms / 1000):
            self._check_slow_handlers()
    
    def _check_slow_handlers(self) -> None:
        """Check for handlers that have exceeded the threshold."""
        current_time = time.perf_counter()
        slow_handlers: list[tuple[str, str, float]] = []
        
        with self._lock:
            for sub_id, info in list(self._active_handlers.items()):
                duration_ms = (current_time - info.start_time) * 1000
                if duration_ms > self._threshold_ms:
                    slow_handlers.append((sub_id, info.handler_name, duration_ms))
        
        # Invoke callbacks outside the lock
        for sub_id, handler_name, duration_ms in slow_handlers:
            self._slow_handler_count += 1
            if self._slow_handler_callback:
                try:
                    self._slow_handler_callback(sub_id, handler_name, duration_ms)
                except Exception:
                    pass  # Don't let callback errors affect monitoring
    
    def get_statistics(self) -> dict[str, Any]:
        """Get monitoring statistics."""
        with self._lock:
            return {
                "threshold_ms": self._threshold_ms,
                "total_handler_calls": self._total_handler_calls,
                "slow_handler_count": self._slow_handler_count,
                "active_handlers": len(self._active_handlers),
                "is_running": self._running,
            }
    
    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running


class IEventBus(ABC):
    """
    Abstract interface for the Event Bus.
    
    The Event Bus is the central message broker in the event-driven
    architecture. It provides:
    - Event publishing with automatic sequence number assignment
    - Event subscription with handler registration
    - Event replay for debugging and state restoration
    - Thread-safe operations for concurrent access
    """
    
    @abstractmethod
    def publish(
        self,
        event_type: EventType,
        data: Any,
        source: str,
        timestamp: Optional[datetime] = None,
    ) -> int:
        """
        Publish an event to the bus.
        
        Args:
            event_type: The type of event being published.
            data: The event payload data.
            source: Identifier of the component publishing the event.
            timestamp: Optional simulation timestamp. If None, uses current
                wall-clock time. For backtesting, this MUST be the simulation
                time (e.g., the timestamp of the Tick/Bar being processed)
                to ensure deterministic replay.
        
        Returns:
            The sequence number assigned to the published event.
        """
        pass
    
    @abstractmethod
    def subscribe(self, event_type: EventType, handler: EventHandler) -> str:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: The type of events to subscribe to.
            handler: Callback function to handle received events.
        
        Returns:
            A unique subscription ID that can be used to unsubscribe.
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: The subscription ID returned by subscribe().
        
        Returns:
            True if unsubscription was successful, False if ID not found.
        """
        pass
    
    @abstractmethod
    def get_current_sequence(self) -> int:
        """
        Get the current event sequence number.
        
        Returns:
            The sequence number of the last published event,
            or 0 if no events have been published.
        """
        pass
    
    @abstractmethod
    def replay_from(self, sequence_number: int) -> list[Event]:
        """
        Replay events from a specific sequence number.
        
        Args:
            sequence_number: The sequence number to start replay from.
        
        Returns:
            List of events from the specified sequence number onwards.
        """
        pass
    
    @abstractmethod
    def get_pending_events(self) -> list[Event]:
        """
        Get all pending events in the queue.
        
        Returns:
            List of events that have not yet been processed.
        """
        pass


class EventBus(IEventBus):
    """
    Thread-safe implementation of the Event Bus.
    
    This implementation guarantees:
    - Monotonically increasing sequence numbers for all events
    - Thread-safe publish and subscribe operations
    - Event history for replay functionality (hot buffer)
    - Deterministic event ordering
    - Support for simulation timestamps (critical for backtesting)
    - Heartbeat monitoring for slow handler detection (TD-004)
    
    The EventBus maintains an internal event history (using deque for O(1)
    eviction) that can be used for debugging, snapshot creation, and
    short-term state restoration. For full crash recovery, use the
    Snapshot mechanism or an external EventPersister.
    
    Example:
        >>> bus = EventBus()
        >>> def handler(event: Event):
        ...     print(f"Received: {event.data}")
        >>> sub_id = bus.subscribe(EventType.TICK, handler)
        >>> # For backtesting, inject simulation time:
        >>> sim_time = datetime(2024, 1, 15, 10, 30, 0)
        >>> seq = bus.publish(EventType.TICK, {"price": 100}, "test", timestamp=sim_time)
        Received: {'price': 100}
        >>> bus.unsubscribe(sub_id)
        True
    """
    
    def __init__(
        self, 
        max_history_size: int = 10000,
        enable_heartbeat: bool = False,
        heartbeat_threshold_ms: float = 100.0,
    ) -> None:
        """
        Initialize the Event Bus.
        
        Args:
            max_history_size: Maximum number of events to keep in the hot
                buffer. Older events are automatically discarded (O(1) via
                deque). Default is 10000 events.
            enable_heartbeat: Whether to enable heartbeat monitoring (TD-004).
                Default is False for backward compatibility.
            heartbeat_threshold_ms: Threshold for slow handler detection.
                Default is 100ms.
                
                Note: This is a hot buffer for UI catch-up. For full crash
                recovery from sequence 0, use Snapshot or EventPersister.
        """
        self._lock = threading.RLock()
        self._sequence_counter: int = 0
        self._max_history_size = max_history_size
        
        # Event history using deque for O(1) eviction at C level
        self._event_history: deque[Event] = deque(maxlen=max_history_size)
        
        # Pending events queue (events waiting to be processed)
        self._pending_events: deque[Event] = deque()
        
        # Subscribers: event_type -> {subscription_id -> handler}
        self._subscribers: dict[EventType, dict[str, EventHandler]] = defaultdict(dict)
        
        # Reverse mapping: subscription_id -> event_type
        self._subscription_types: dict[str, EventType] = {}
        
        # Handler names for monitoring
        self._handler_names: dict[str, str] = {}
        
        # TD-004: Heartbeat monitor for slow handler detection
        self._heartbeat_monitor: Optional[HeartbeatMonitor] = None
        if enable_heartbeat:
            self._heartbeat_monitor = HeartbeatMonitor(threshold_ms=heartbeat_threshold_ms)
            self._heartbeat_monitor.start()
    
    def set_slow_handler_callback(self, callback: SlowHandlerCallback) -> None:
        """
        Set callback for slow handler alerts (TD-004).
        
        Args:
            callback: Function called when a handler exceeds threshold.
                      Signature: (subscription_id, handler_name, duration_ms) -> None
        """
        if self._heartbeat_monitor:
            self._heartbeat_monitor.set_slow_handler_callback(callback)
    
    def enable_heartbeat_monitor(self, threshold_ms: float = 100.0) -> None:
        """
        Enable heartbeat monitoring (TD-004).
        
        Args:
            threshold_ms: Threshold for slow handler detection.
        """
        if self._heartbeat_monitor is None:
            self._heartbeat_monitor = HeartbeatMonitor(threshold_ms=threshold_ms)
        self._heartbeat_monitor.start()
    
    def disable_heartbeat_monitor(self) -> None:
        """Disable heartbeat monitoring."""
        if self._heartbeat_monitor:
            self._heartbeat_monitor.stop()
    
    def get_heartbeat_statistics(self) -> Optional[dict[str, Any]]:
        """Get heartbeat monitoring statistics (TD-004)."""
        if self._heartbeat_monitor:
            return self._heartbeat_monitor.get_statistics()
        return None
    
    def publish(
        self,
        event_type: EventType,
        data: Any,
        source: str,
        timestamp: Optional[datetime] = None,
    ) -> int:
        """
        Publish an event to the bus with automatic sequence number assignment.
        
        The sequence number is atomically incremented to ensure monotonicity.
        All registered handlers for the event type are called synchronously.
        
        Args:
            event_type: The type of event being published.
            data: The event payload data.
            source: Identifier of the component publishing the event.
            timestamp: Optional simulation timestamp. If None, uses current
                wall-clock time. For backtesting, this MUST be the simulation
                time to ensure deterministic replay.
        
        Returns:
            The sequence number assigned to the published event.
        
        Raises:
            EngineError: If event publishing fails.
        """
        with self._lock:
            # Atomically increment sequence number
            self._sequence_counter += 1
            sequence_number = self._sequence_counter
            
            # Use provided timestamp or fall back to wall-clock time
            # For backtesting: Engine/ReplayController injects simulation time
            event_timestamp = timestamp if timestamp is not None else datetime.now()
            
            # Create the event
            event = Event(
                sequence_number=sequence_number,
                event_type=event_type,
                timestamp=event_timestamp,
                data=data,
                source=source,
            )
            
            # Add to history (deque handles eviction automatically in O(1))
            self._event_history.append(event)
            
            # Get handlers for this event type
            handlers = list(self._subscribers[event_type].items())
        
        # Call handlers outside the lock to prevent deadlocks
        for subscription_id, handler in handlers:
            handler_name = self._handler_names.get(subscription_id, handler.__name__)
            
            # TD-004: Track handler execution with heartbeat monitor
            if self._heartbeat_monitor:
                self._heartbeat_monitor.handler_started(subscription_id, handler_name, event_type)
            
            try:
                handler(event)
            except Exception as e:
                # Log error but don't stop other handlers
                raise EngineError(
                    message=f"Event handler failed: {e}",
                    error_code=ErrorCodes.EVENT_PUBLISH_FAILED,
                    details={
                        "event_type": event_type.value,
                        "sequence_number": sequence_number,
                        "handler": handler_name,
                        "error": str(e),
                    },
                )
            finally:
                # TD-004: Record handler completion
                if self._heartbeat_monitor:
                    self._heartbeat_monitor.handler_finished(subscription_id)
        
        return sequence_number
    
    def subscribe(self, event_type: EventType, handler: EventHandler) -> str:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: The type of events to subscribe to.
            handler: Callback function to handle received events.
                The handler receives an Event object as its only argument.
        
        Returns:
            A unique subscription ID that can be used to unsubscribe.
        
        Raises:
            TypeError: If handler is not callable.
        """
        if not callable(handler):
            raise TypeError("handler must be callable")
        
        subscription_id = str(uuid.uuid4())
        
        with self._lock:
            self._subscribers[event_type][subscription_id] = handler
            self._subscription_types[subscription_id] = event_type
            # Store handler name for monitoring (TD-004)
            self._handler_names[subscription_id] = getattr(handler, "__name__", str(handler))
        
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: The subscription ID returned by subscribe().
        
        Returns:
            True if unsubscription was successful, False if ID not found.
        """
        with self._lock:
            if subscription_id not in self._subscription_types:
                return False
            
            event_type = self._subscription_types[subscription_id]
            del self._subscribers[event_type][subscription_id]
            del self._subscription_types[subscription_id]
            # Clean up handler name (TD-004)
            self._handler_names.pop(subscription_id, None)
            
            return True
    
    def get_current_sequence(self) -> int:
        """
        Get the current event sequence number.
        
        Returns:
            The sequence number of the last published event,
            or 0 if no events have been published.
        """
        with self._lock:
            return self._sequence_counter
    
    def replay_from(self, sequence_number: int) -> list[Event]:
        """
        Replay events from a specific sequence number.
        
        This method returns all events with sequence numbers greater than
        or equal to the specified sequence number. Events are returned
        in order of their sequence numbers.
        
        Note: Only events within the hot buffer (max_history_size) are
        available. For full replay from sequence 0, use Snapshot restoration.
        
        Args:
            sequence_number: The sequence number to start replay from.
        
        Returns:
            List of events from the specified sequence number onwards.
            Returns an empty list if no matching events are found.
        """
        with self._lock:
            return [
                event for event in self._event_history
                if event.sequence_number >= sequence_number
            ]
    
    def get_pending_events(self) -> list[Event]:
        """
        Get all pending events in the queue.
        
        Returns:
            List of events that have not yet been processed.
            In the current synchronous implementation, this is typically empty
            as events are processed immediately upon publishing.
        """
        with self._lock:
            return list(self._pending_events)
    
    def get_event_history(self) -> list[Event]:
        """
        Get the complete event history from the hot buffer.
        
        Returns:
            List of all events in the history buffer.
        """
        with self._lock:
            return list(self._event_history)
    
    def clear_history(self) -> None:
        """
        Clear the event history.
        
        This does not reset the sequence counter, ensuring that
        sequence numbers remain monotonically increasing.
        """
        with self._lock:
            self._event_history.clear()
    
    def reset(self) -> None:
        """
        Reset the event bus to its initial state.
        
        This clears all history, pending events, and resets the
        sequence counter. Subscriptions are preserved.
        
        Warning: This should only be used for testing or when
        starting a completely new backtest session.
        """
        with self._lock:
            self._sequence_counter = 0
            self._event_history.clear()
            self._pending_events.clear()
    
    def get_subscriber_count(self, event_type: EventType) -> int:
        """
        Get the number of subscribers for an event type.
        
        Args:
            event_type: The event type to check.
        
        Returns:
            Number of active subscribers for the event type.
        """
        with self._lock:
            return len(self._subscribers[event_type])


__all__ = [
    "IEventBus",
    "EventBus",
    "EventHandler",
    "SlowHandlerCallback",
    "HeartbeatMonitor",
    "HandlerExecutionInfo",
]
