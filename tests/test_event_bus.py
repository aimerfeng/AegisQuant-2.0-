"""
Property-Based Tests for EventBus

This module contains property-based tests using Hypothesis to verify
the correctness properties of the EventBus implementation.

Property 1: Event Sequence Monotonicity
    For any sequence of events published to the Event_Bus, the sequence_number
    of each event must be strictly greater than the sequence_number of the
    previous event.

Validates: Requirements 1.7
"""
import threading
from datetime import datetime

import pytest
from hypothesis import given, settings, strategies as st

from core.engine import EventBus, EventType, Event


class TestEventSequenceMonotonicity:
    """
    Property 1: Event Sequence Monotonicity
    
    *For any* sequence of events published to the Event_Bus, the sequence_number
    of each event must be strictly greater than the sequence_number of the
    previous event.
    
    **Validates: Requirements 1.7**
    """
    
    @given(
        event_count=st.integers(min_value=1, max_value=100),
        event_types=st.lists(
            st.sampled_from(list(EventType)),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_sequence_numbers_are_strictly_increasing(
        self, event_count: int, event_types: list[EventType]
    ) -> None:
        """
        Property: For any sequence of published events, each event's
        sequence number must be strictly greater than the previous one.
        
        Feature: titan-quant, Property 1: Event Sequence Monotonicity
        """
        bus = EventBus()
        sequence_numbers: list[int] = []
        
        # Publish events with various types
        for i, event_type in enumerate(event_types[:event_count]):
            seq = bus.publish(
                event_type=event_type,
                data={"index": i},
                source="test"
            )
            sequence_numbers.append(seq)
        
        # Verify strict monotonicity
        for i in range(1, len(sequence_numbers)):
            assert sequence_numbers[i] > sequence_numbers[i - 1], (
                f"Sequence number {sequence_numbers[i]} at index {i} "
                f"is not greater than {sequence_numbers[i - 1]} at index {i - 1}"
            )
    
    @given(
        num_threads=st.integers(min_value=2, max_value=5),
        events_per_thread=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=100, deadline=10000)
    def test_sequence_monotonicity_under_concurrent_access(
        self, num_threads: int, events_per_thread: int
    ) -> None:
        """
        Property: Even under concurrent access from multiple threads,
        sequence numbers must remain strictly monotonically increasing.
        
        Feature: titan-quant, Property 1: Event Sequence Monotonicity
        """
        bus = EventBus()
        all_sequences: list[int] = []
        lock = threading.Lock()
        
        def publish_events(thread_id: int) -> None:
            for i in range(events_per_thread):
                seq = bus.publish(
                    event_type=EventType.TICK,
                    data={"thread": thread_id, "index": i},
                    source=f"thread_{thread_id}"
                )
                with lock:
                    all_sequences.append(seq)
        
        # Create and start threads
        threads = [
            threading.Thread(target=publish_events, args=(i,))
            for i in range(num_threads)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Sort sequences and verify no duplicates and strict monotonicity
        sorted_sequences = sorted(all_sequences)
        
        # Check no duplicates
        assert len(sorted_sequences) == len(set(sorted_sequences)), (
            "Duplicate sequence numbers found under concurrent access"
        )
        
        # Check strict monotonicity
        for i in range(1, len(sorted_sequences)):
            assert sorted_sequences[i] > sorted_sequences[i - 1], (
                f"Sequence numbers are not strictly increasing: "
                f"{sorted_sequences[i - 1]} -> {sorted_sequences[i]}"
            )
    
    @given(
        initial_publishes=st.integers(min_value=1, max_value=50),
        additional_publishes=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=100, deadline=5000)
    def test_sequence_continues_after_history_clear(
        self, initial_publishes: int, additional_publishes: int
    ) -> None:
        """
        Property: After clearing history, sequence numbers must continue
        to increase from where they left off (not reset).
        
        Feature: titan-quant, Property 1: Event Sequence Monotonicity
        """
        bus = EventBus()
        
        # Publish initial events
        for i in range(initial_publishes):
            bus.publish(EventType.TICK, {"index": i}, "test")
        
        last_seq_before_clear = bus.get_current_sequence()
        
        # Clear history
        bus.clear_history()
        
        # Publish more events
        first_seq_after_clear = bus.publish(EventType.TICK, {"after": "clear"}, "test")
        
        # Verify sequence continues (not reset)
        assert first_seq_after_clear > last_seq_before_clear, (
            f"Sequence number {first_seq_after_clear} after clear "
            f"should be greater than {last_seq_before_clear} before clear"
        )


class TestEventBusBasicFunctionality:
    """Unit tests for basic EventBus functionality."""
    
    def test_subscribe_and_receive_events(self) -> None:
        """Test that subscribers receive published events."""
        bus = EventBus()
        received_events: list[Event] = []
        
        def handler(event: Event) -> None:
            received_events.append(event)
        
        sub_id = bus.subscribe(EventType.TICK, handler)
        bus.publish(EventType.TICK, {"price": 100}, "test")
        
        assert len(received_events) == 1
        assert received_events[0].data == {"price": 100}
        
        bus.unsubscribe(sub_id)
    
    def test_unsubscribe_stops_receiving_events(self) -> None:
        """Test that unsubscribed handlers don't receive events."""
        bus = EventBus()
        received_events: list[Event] = []
        
        def handler(event: Event) -> None:
            received_events.append(event)
        
        sub_id = bus.subscribe(EventType.TICK, handler)
        bus.publish(EventType.TICK, {"price": 100}, "test")
        
        assert len(received_events) == 1
        
        bus.unsubscribe(sub_id)
        bus.publish(EventType.TICK, {"price": 200}, "test")
        
        # Should still be 1, not 2
        assert len(received_events) == 1
    
    def test_replay_from_sequence_number(self) -> None:
        """Test event replay functionality."""
        bus = EventBus()
        
        seq1 = bus.publish(EventType.TICK, {"price": 100}, "test")
        seq2 = bus.publish(EventType.BAR, {"close": 200}, "test")
        seq3 = bus.publish(EventType.TICK, {"price": 300}, "test")
        
        # Replay from seq2
        replayed = bus.replay_from(seq2)
        
        assert len(replayed) == 2
        assert replayed[0].sequence_number == seq2
        assert replayed[1].sequence_number == seq3
    
    def test_event_history_size_limit(self) -> None:
        """Test that event history respects size limit."""
        max_size = 10
        bus = EventBus(max_history_size=max_size)
        
        # Publish more events than the limit
        for i in range(max_size + 5):
            bus.publish(EventType.TICK, {"index": i}, "test")
        
        history = bus.get_event_history()
        assert len(history) == max_size
        
        # Verify oldest events were removed
        assert history[0].data["index"] == 5  # First 5 should be gone
