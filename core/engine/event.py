"""
Titan-Quant Event System

This module defines the core event types and data structures for the
event-driven architecture. The Event_Bus uses these types to ensure
deterministic event processing with monotonically increasing sequence numbers.

Requirements:
    - 1.5: Event_Bus SHALL 采用事件驱动架构处理所有系统消息
    - 1.6: Event_Bus SHALL 保证事件处理的顺序确定性
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(Enum):
    """
    Enumeration of all event types in the Titan-Quant system.
    
    Event types are categorized by their source and purpose:
    - Market data events: TICK, BAR
    - Trading events: ORDER, TRADE, POSITION
    - Account events: ACCOUNT
    - Strategy events: STRATEGY
    - Risk events: RISK
    - System events: SYSTEM
    """
    
    # Market data events
    TICK = "tick"
    BAR = "bar"
    
    # Trading events
    ORDER = "order"
    TRADE = "trade"
    POSITION = "position"
    
    # Account events
    ACCOUNT = "account"
    
    # Strategy events
    STRATEGY = "strategy"
    
    # Risk events
    RISK = "risk"
    
    # System events
    SYSTEM = "system"


@dataclass(frozen=True)
class Event:
    """
    Base event class with monotonically increasing sequence number.
    
    The Event class is the fundamental unit of communication in the
    event-driven architecture. Each event is immutable (frozen=True)
    to ensure data integrity during processing.
    
    Attributes:
        sequence_number: Monotonically increasing sequence number that
            guarantees event ordering and enables deterministic replay.
            This number is assigned by the EventBus when the event is
            published and must be strictly greater than all previous
            sequence numbers.
        event_type: The type of event, determining how it will be routed
            and processed by subscribers.
        timestamp: The timestamp when the event occurred (not when it
            was published). For market data events, this is the exchange
            timestamp. For system events, this is the local time.
        data: The event payload. The structure depends on the event_type.
            For TICK events, this would be TickData. For ORDER events,
            this would be OrderData, etc.
        source: Identifier of the component that generated this event.
            Used for debugging and audit purposes.
    
    Example:
        >>> event = Event(
        ...     sequence_number=1,
        ...     event_type=EventType.TICK,
        ...     timestamp=datetime.now(),
        ...     data={"symbol": "BTC/USDT", "price": 50000.0},
        ...     source="data_provider"
        ... )
    """
    
    sequence_number: int
    event_type: EventType
    timestamp: datetime
    data: Any
    source: str
    
    def __post_init__(self) -> None:
        """Validate event data after initialization."""
        if self.sequence_number < 0:
            raise ValueError("sequence_number must be non-negative")
        if not isinstance(self.event_type, EventType):
            raise TypeError("event_type must be an EventType enum member")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime object")
        if not self.source:
            raise ValueError("source must not be empty")
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert event to dictionary for serialization.
        
        Returns:
            Dictionary representation of the event suitable for
            JSON serialization or storage.
        """
        return {
            "sequence_number": self.sequence_number,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """
        Create an Event from a dictionary.
        
        Args:
            data: Dictionary containing event data with keys:
                - sequence_number: int
                - event_type: str (EventType value)
                - timestamp: str (ISO format datetime)
                - data: Any
                - source: str
        
        Returns:
            Event instance created from the dictionary data.
        
        Raises:
            KeyError: If required keys are missing.
            ValueError: If event_type is not a valid EventType.
        """
        return cls(
            sequence_number=data["sequence_number"],
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data["data"],
            source=data["source"],
        )


__all__ = [
    "Event",
    "EventType",
]
