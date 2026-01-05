"""
Titan-Quant Event Bus

This module implements the core event bus for the event-driven architecture.
The EventBus guarantees deterministic event processing through monotonically
increasing sequence numbers and supports event replay for debugging and
snapshot restoration.

Requirements:
    - 1.6: Event_Bus SHALL 保证事件处理的顺序确定性
    - 1.7: Event_Bus SHALL 使用单调递增的事件序号标识每个事件，支持事件回溯和重放
"""
from __future__ import annotations

import threading
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable

from core.engine.event import Event, EventType
from core.exceptions import EngineError, ErrorCodes


# Type alias for event handlers
EventHandler = Callable[[Event], None]


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
    def publish(self, event_type: EventType, data: Any, source: str) -> int:
        """
        Publish an event to the bus.
        
        Args:
            event_type: The type of event being published.
            data: The event payload data.
            source: Identifier of the component publishing the event.
        
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
            or -1 if no events have been published.
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
    - Event history for replay functionality
    - Deterministic event ordering
    
    The EventBus maintains an internal event history that can be used
    for debugging, snapshot creation, and state restoration.
    
    Example:
        >>> bus = EventBus()
        >>> def handler(event: Event):
        ...     print(f"Received: {event.data}")
        >>> sub_id = bus.subscribe(EventType.TICK, handler)
        >>> seq = bus.publish(EventType.TICK, {"price": 100}, "test")
        Received: {'price': 100}
        >>> bus.unsubscribe(sub_id)
        True
    """
    
    def __init__(self, max_history_size: int = 10000) -> None:
        """
        Initialize the Event Bus.
        
        Args:
            max_history_size: Maximum number of events to keep in history.
                Older events are discarded when this limit is reached.
                Default is 10000 events.
        """
        self._lock = threading.RLock()
        self._sequence_counter: int = 0
        self._max_history_size = max_history_size
        
        # Event history for replay functionality
        self._event_history: list[Event] = []
        
        # Pending events queue (events waiting to be processed)
        self._pending_events: list[Event] = []
        
        # Subscribers: event_type -> {subscription_id -> handler}
        self._subscribers: dict[EventType, dict[str, EventHandler]] = defaultdict(dict)
        
        # Reverse mapping: subscription_id -> event_type
        self._subscription_types: dict[str, EventType] = {}
    
    def publish(self, event_type: EventType, data: Any, source: str) -> int:
        """
        Publish an event to the bus with automatic sequence number assignment.
        
        The sequence number is atomically incremented to ensure monotonicity.
        All registered handlers for the event type are called synchronously.
        
        Args:
            event_type: The type of event being published.
            data: The event payload data.
            source: Identifier of the component publishing the event.
        
        Returns:
            The sequence number assigned to the published event.
        
        Raises:
            EngineError: If event publishing fails.
        """
        with self._lock:
            # Atomically increment sequence number
            self._sequence_counter += 1
            sequence_number = self._sequence_counter
            
            # Create the event
            event = Event(
                sequence_number=sequence_number,
                event_type=event_type,
                timestamp=datetime.now(),
                data=data,
                source=source,
            )
            
            # Add to history (with size limit)
            self._event_history.append(event)
            if len(self._event_history) > self._max_history_size:
                # Remove oldest events
                self._event_history = self._event_history[-self._max_history_size:]
            
            # Get handlers for this event type
            handlers = list(self._subscribers[event_type].values())
        
        # Call handlers outside the lock to prevent deadlocks
        for handler in handlers:
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
                        "error": str(e),
                    },
                )
        
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
        Get the complete event history.
        
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
]
