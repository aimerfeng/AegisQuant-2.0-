"""
Property-Based Tests for Replay Controller

This module contains property-based tests using Hypothesis to verify
the correctness properties of the Replay Controller implementation.

Property 9: Single Step Precision
    For any backtest state, executing a single step must advance the simulation
    by exactly one time unit (tick or bar interval) and process exactly the
    events for that time unit.

Validates: Requirements 5.3
"""
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest
from hypothesis import given, settings, strategies as st, assume

from core.engine.event import Event, EventType
from core.engine.event_bus import EventBus
from core.engine.replay import (
    DataProvider,
    IReplayController,
    ReplayConfig,
    ReplayController,
    ReplaySpeed,
    ReplayState,
    ReplayStatus,
)
from core.engine.snapshot import (
    AccountState,
    PositionState,
    StrategyState,
    Snapshot,
    SnapshotManager,
)


# Custom strategies for generating valid test data
@st.composite
def data_point_strategy(draw, index: int = 0, base_time: Optional[datetime] = None):
    """Generate a valid data point for replay."""
    if base_time is None:
        base_time = datetime(2024, 1, 1, 9, 0, 0)
    
    timestamp = base_time + timedelta(seconds=index)
    price = draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
    volume = draw(st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False))
    
    return {
        "timestamp": timestamp,
        "open": price,
        "high": price * 1.01,
        "low": price * 0.99,
        "close": price,
        "volume": volume,
    }


@st.composite
def tick_data_point_strategy(draw, index: int = 0, base_time: Optional[datetime] = None):
    """Generate a valid tick data point for replay."""
    if base_time is None:
        base_time = datetime(2024, 1, 1, 9, 0, 0)
    
    timestamp = base_time + timedelta(milliseconds=index * 100)
    last_price = draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
    volume = draw(st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    spread = draw(st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False))
    
    return {
        "timestamp": timestamp,
        "last_price": last_price,
        "volume": volume,
        "bid_price_1": last_price - spread / 2,
        "ask_price_1": last_price + spread / 2,
        "bid_volume_1": draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)),
        "ask_volume_1": draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)),
    }


class MockDataProvider:
    """Mock data provider for testing."""
    
    def __init__(self, data_points: List[Dict[str, Any]]):
        self.data_points = data_points
        self.access_count = 0
        self.accessed_indices: List[int] = []
    
    def __call__(self, index: int) -> Optional[Dict[str, Any]]:
        self.access_count += 1
        self.accessed_indices.append(index)
        if 0 <= index < len(self.data_points):
            return self.data_points[index]
        return None
    
    def reset(self):
        self.access_count = 0
        self.accessed_indices = []


class TestSingleStepPrecision:
    """
    Property 9: Single Step Precision
    
    *For any* backtest state, executing a single step must advance the simulation
    by exactly one time unit (tick or bar interval) and process exactly the
    events for that time unit.
    
    **Validates: Requirements 5.3**
    """
    
    @given(
        num_data_points=st.integers(min_value=5, max_value=100),
        initial_index=st.integers(min_value=0, max_value=50),
    )
    @settings(max_examples=100, deadline=10000)
    def test_single_step_advances_by_exactly_one(
        self,
        num_data_points: int,
        initial_index: int,
    ) -> None:
        """
        Property: Each step() call must advance the data index by exactly 1.
        
        Feature: titan-quant, Property 9: Single Step Precision
        """
        assume(initial_index < num_data_points)
        
        # Generate data points
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        data_points = [
            {
                "timestamp": base_time + timedelta(seconds=i),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000.0,
            }
            for i in range(num_data_points)
        ]
        
        # Create components
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        data_provider = MockDataProvider(data_points)
        
        # Initialize controller
        controller = ReplayController()
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=num_data_points),
            total_data_points=num_data_points,
        )
        
        # Seek to initial index
        if initial_index > 0:
            controller.seek_to_index(initial_index)
        
        # Get initial state
        initial_status = controller.get_status()
        initial_data_index = initial_status.current_index
        
        # Execute single step
        data_provider.reset()
        success = controller.step()
        
        # Verify step was successful (unless at end)
        if initial_index < num_data_points:
            assert success, "Step should succeed when not at end of data"
            
            # Verify index advanced by exactly 1
            final_status = controller.get_status()
            assert final_status.current_index == initial_data_index + 1, \
                f"Index should advance by exactly 1: {initial_data_index} -> {final_status.current_index}"
            
            # Verify exactly one data point was accessed
            assert data_provider.access_count == 1, \
                f"Exactly one data point should be accessed, got {data_provider.access_count}"
            assert data_provider.accessed_indices == [initial_data_index], \
                f"Should access index {initial_data_index}, accessed {data_provider.accessed_indices}"
    
    @given(
        num_steps=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100, deadline=10000)
    def test_multiple_steps_advance_sequentially(
        self,
        num_steps: int,
    ) -> None:
        """
        Property: Multiple step() calls must advance the index sequentially.
        
        Feature: titan-quant, Property 9: Single Step Precision
        """
        num_data_points = num_steps + 10  # Ensure enough data
        
        # Generate data points
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        data_points = [
            {
                "timestamp": base_time + timedelta(seconds=i),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000.0,
            }
            for i in range(num_data_points)
        ]
        
        # Create components
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        data_provider = MockDataProvider(data_points)
        
        # Initialize controller
        controller = ReplayController()
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=num_data_points),
            total_data_points=num_data_points,
        )
        
        # Execute multiple steps and verify sequential advancement
        for expected_index in range(num_steps):
            status_before = controller.get_status()
            assert status_before.current_index == expected_index, \
                f"Before step {expected_index}: index should be {expected_index}, got {status_before.current_index}"
            
            success = controller.step()
            assert success, f"Step {expected_index} should succeed"
            
            status_after = controller.get_status()
            assert status_after.current_index == expected_index + 1, \
                f"After step {expected_index}: index should be {expected_index + 1}, got {status_after.current_index}"
    
    @given(
        num_data_points=st.integers(min_value=5, max_value=50),
    )
    @settings(max_examples=100, deadline=10000)
    def test_step_publishes_exactly_one_event(
        self,
        num_data_points: int,
    ) -> None:
        """
        Property: Each step() must publish exactly one event to the EventBus.
        
        Feature: titan-quant, Property 9: Single Step Precision
        """
        # Generate data points
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        data_points = [
            {
                "timestamp": base_time + timedelta(seconds=i),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000.0,
            }
            for i in range(num_data_points)
        ]
        
        # Create components
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        data_provider = MockDataProvider(data_points)
        
        # Track events
        received_events: List[Event] = []
        def event_handler(event: Event):
            received_events.append(event)
        
        event_bus.subscribe(EventType.BAR, event_handler)
        event_bus.subscribe(EventType.TICK, event_handler)
        
        # Initialize controller
        controller = ReplayController()
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=num_data_points),
            total_data_points=num_data_points,
        )
        
        # Execute steps and verify event count
        for i in range(min(5, num_data_points)):
            events_before = len(received_events)
            controller.step()
            events_after = len(received_events)
            
            assert events_after == events_before + 1, \
                f"Step {i}: should publish exactly 1 event, published {events_after - events_before}"
    
    @given(
        num_data_points=st.integers(min_value=5, max_value=50),
    )
    @settings(max_examples=100, deadline=10000)
    def test_step_updates_current_time(
        self,
        num_data_points: int,
    ) -> None:
        """
        Property: Each step() must update current_time to match the data timestamp.
        
        Feature: titan-quant, Property 9: Single Step Precision
        """
        # Generate data points with specific timestamps
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        data_points = [
            {
                "timestamp": base_time + timedelta(seconds=i * 5),  # 5 second intervals
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000.0,
            }
            for i in range(num_data_points)
        ]
        
        # Create components
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        data_provider = MockDataProvider(data_points)
        
        # Initialize controller
        controller = ReplayController()
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=num_data_points * 5),
            total_data_points=num_data_points,
        )
        
        # Execute steps and verify time updates
        for i in range(min(5, num_data_points)):
            controller.step()
            status = controller.get_status()
            expected_time = base_time + timedelta(seconds=i * 5)
            
            assert status.current_time == expected_time, \
                f"Step {i}: current_time should be {expected_time}, got {status.current_time}"


class TestReplayControllerStateTransitions:
    """Tests for replay controller state transitions."""
    
    def test_initial_state_is_idle(self) -> None:
        """Test that controller starts in IDLE state."""
        controller = ReplayController()
        status = controller.get_status()
        assert status.state == ReplayState.IDLE
    
    def test_initialize_transitions_to_paused(self) -> None:
        """Test that initialize() transitions to PAUSED state."""
        controller = ReplayController()
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        
        data_points = [{"timestamp": datetime.now(), "close": 100.0}]
        data_provider = MockDataProvider(data_points)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            total_data_points=1,
        )
        
        status = controller.get_status()
        assert status.state == ReplayState.PAUSED
    
    def test_step_from_paused_returns_to_paused(self) -> None:
        """Test that step() from PAUSED state returns to PAUSED."""
        controller = ReplayController()
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        data_points = [
            {"timestamp": base_time + timedelta(seconds=i), "close": 100.0 + i}
            for i in range(10)
        ]
        data_provider = MockDataProvider(data_points)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=10),
            total_data_points=10,
        )
        
        # Step should return to PAUSED
        controller.step()
        status = controller.get_status()
        assert status.state == ReplayState.PAUSED
    
    def test_stop_transitions_to_stopped(self) -> None:
        """Test that stop() transitions to STOPPED state."""
        controller = ReplayController()
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        
        data_points = [{"timestamp": datetime.now(), "close": 100.0}]
        data_provider = MockDataProvider(data_points)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            total_data_points=1,
        )
        
        controller.stop()
        status = controller.get_status()
        assert status.state == ReplayState.STOPPED


class TestReplayControllerSpeedControl:
    """Tests for replay speed control."""
    
    @given(speed=st.sampled_from(list(ReplaySpeed)))
    @settings(max_examples=20, deadline=5000)
    def test_set_speed_updates_status(self, speed: ReplaySpeed) -> None:
        """
        Property: set_speed() must update the speed in status.
        
        Feature: titan-quant, Property 9: Single Step Precision
        """
        controller = ReplayController()
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        
        data_points = [{"timestamp": datetime.now(), "close": 100.0}]
        data_provider = MockDataProvider(data_points)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            total_data_points=1,
        )
        
        controller.set_speed(speed)
        status = controller.get_status()
        assert status.speed == speed


class TestReplayControllerSnapshotIntegration:
    """Tests for snapshot integration with replay controller."""
    
    def test_save_snapshot_creates_file(self) -> None:
        """Test that save_snapshot() creates a snapshot file."""
        controller = ReplayController(config=ReplayConfig(
            snapshot_dir=tempfile.gettempdir()
        ))
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        data_points = [
            {"timestamp": base_time + timedelta(seconds=i), "close": 100.0 + i}
            for i in range(10)
        ]
        data_provider = MockDataProvider(data_points)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=10),
            total_data_points=10,
        )
        
        # Execute a few steps
        for _ in range(3):
            controller.step()
        
        # Save snapshot
        snapshot_path = controller.save_snapshot("Test snapshot")
        
        try:
            assert os.path.exists(snapshot_path), "Snapshot file should exist"
        finally:
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
    
    def test_load_snapshot_restores_state(self) -> None:
        """Test that load_snapshot() restores the saved state."""
        temp_dir = tempfile.gettempdir()
        controller = ReplayController(config=ReplayConfig(snapshot_dir=temp_dir))
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        data_points = [
            {"timestamp": base_time + timedelta(seconds=i), "close": 100.0 + i}
            for i in range(20)
        ]
        data_provider = MockDataProvider(data_points)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=20),
            total_data_points=20,
        )
        
        # Execute some steps
        for _ in range(5):
            controller.step()
        
        # Save snapshot
        snapshot_path = controller.save_snapshot("Before more steps")
        saved_status = controller.get_status()
        
        try:
            # Execute more steps
            for _ in range(5):
                controller.step()
            
            # Verify state changed
            changed_status = controller.get_status()
            assert changed_status.current_index != saved_status.current_index
            
            # Load snapshot
            controller.load_snapshot(snapshot_path)
            
            # Verify state restored
            restored_status = controller.get_status()
            assert restored_status.current_index == saved_status.current_index
            
        finally:
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)


class TestReplayControllerSeek:
    """Tests for seek functionality."""
    
    @given(
        num_data_points=st.integers(min_value=10, max_value=100),
        target_index=st.integers(min_value=0, max_value=99),
    )
    @settings(max_examples=50, deadline=10000)
    def test_seek_to_index_sets_correct_position(
        self,
        num_data_points: int,
        target_index: int,
    ) -> None:
        """
        Property: seek_to_index() must set the current index to the target.
        
        Feature: titan-quant, Property 9: Single Step Precision
        """
        assume(target_index < num_data_points)
        
        controller = ReplayController()
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        data_points = [
            {"timestamp": base_time + timedelta(seconds=i), "close": 100.0 + i}
            for i in range(num_data_points)
        ]
        data_provider = MockDataProvider(data_points)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=num_data_points),
            total_data_points=num_data_points,
        )
        
        # Seek to target index
        success = controller.seek_to_index(target_index)
        assert success, f"Seek to index {target_index} should succeed"
        
        status = controller.get_status()
        assert status.current_index == target_index, \
            f"Current index should be {target_index}, got {status.current_index}"
    
    def test_seek_to_invalid_index_fails(self) -> None:
        """Test that seeking to an invalid index fails."""
        controller = ReplayController()
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        
        data_points = [{"timestamp": datetime.now(), "close": 100.0} for _ in range(10)]
        data_provider = MockDataProvider(data_points)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            total_data_points=10,
        )
        
        # Seek to negative index should fail
        assert not controller.seek_to_index(-1)
        
        # Seek beyond data should fail
        assert not controller.seek_to_index(100)


class TestReplayControllerProgress:
    """Tests for progress tracking."""
    
    @given(
        num_data_points=st.integers(min_value=10, max_value=100),
        steps_to_execute=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=50, deadline=10000)
    def test_progress_percentage_is_accurate(
        self,
        num_data_points: int,
        steps_to_execute: int,
    ) -> None:
        """
        Property: Progress percentage must accurately reflect current position.
        
        Feature: titan-quant, Property 9: Single Step Precision
        """
        assume(steps_to_execute <= num_data_points)
        
        controller = ReplayController()
        event_bus = EventBus()
        snapshot_manager = SnapshotManager()
        
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        data_points = [
            {"timestamp": base_time + timedelta(seconds=i), "close": 100.0 + i}
            for i in range(num_data_points)
        ]
        data_provider = MockDataProvider(data_points)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=data_provider,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=num_data_points),
            total_data_points=num_data_points,
        )
        
        # Execute steps
        for _ in range(steps_to_execute):
            controller.step()
        
        status = controller.get_status()
        expected_progress = (steps_to_execute / num_data_points) * 100.0
        
        assert abs(status.progress_percent - expected_progress) < 0.01, \
            f"Progress should be {expected_progress}%, got {status.progress_percent}%"
