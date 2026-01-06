"""
Property-Based Tests for Backtest Determinism

Property 2: Backtest Determinism
    For any backtest configuration, running the backtest multiple times
    with identical inputs must produce identical event sequences.

Validates: Requirements 1.6, 9.7
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List
import copy

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from core.engine.event_bus import EventBus
from core.engine.event import Event, EventType
from core.engine.replay import ReplayController, ReplayConfig, ReplaySpeed
from core.engine.snapshot import SnapshotManager


class TestBacktestDeterminism:
    """
    Property 2: Backtest Determinism
    
    *For any* backtest configuration, running the backtest multiple times
    with identical inputs must produce identical event sequences.
    
    **Validates: Requirements 1.6, 9.7**
    """
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.snapshot_dir = tmp_path / "snapshots"
        self.snapshot_dir.mkdir()
        yield
    
    def _create_data_provider(self, data_list):
        def provider(index):
            if 0 <= index < len(data_list):
                return copy.deepcopy(data_list[index])
            return None
        return provider
    
    def _run_backtest(self, data_list, snapshot_dir):
        event_bus = EventBus(max_history_size=10000)
        snapshot_manager = SnapshotManager()
        collected_events = []
        
        def event_collector(event):
            collected_events.append(event)
        
        for event_type in EventType:
            event_bus.subscribe(event_type, event_collector)
        
        config = ReplayConfig(
            initial_speed=ReplaySpeed.SPEED_MAX,
            time_unit_ms=0,
            snapshot_dir=snapshot_dir,
        )
        controller = ReplayController(config=config)
        
        start_time = data_list[0]["timestamp"] if data_list else datetime(2024, 1, 1)
        end_time = data_list[-1]["timestamp"] if data_list else datetime(2024, 1, 31)
        
        controller.initialize(
            event_bus=event_bus,
            snapshot_manager=snapshot_manager,
            data_provider=self._create_data_provider(data_list),
            start_time=start_time,
            end_time=end_time,
            total_data_points=len(data_list),
        )
        
        for _ in range(len(data_list)):
            controller.step()
        
        return collected_events, event_bus.get_current_sequence()
    
    @given(num_bars=st.integers(min_value=5, max_value=30))
    @settings(max_examples=100, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_identical_inputs_produce_identical_sequences(self, num_bars):
        """Feature: titan-quant, Property 2: Backtest Determinism"""
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        data_list = [
            {
                "symbol": "BTCUSDT", "exchange": "BINANCE",
                "timestamp": base_time + timedelta(minutes=i),
                "interval": "1m", "open_price": 100.0 + i,
                "high_price": 101.0 + i, "low_price": 99.0 + i,
                "close_price": 100.5 + i, "volume": 1000.0, "turnover": 100000.0,
            }
            for i in range(num_bars)
        ]
        
        events1, seq1 = self._run_backtest(data_list, str(self.snapshot_dir / "run1"))
        events2, seq2 = self._run_backtest(data_list, str(self.snapshot_dir / "run2"))
        
        assert seq1 == seq2
        assert len(events1) == len(events2)
        for e1, e2 in zip(events1, events2):
            assert e1.sequence_number == e2.sequence_number
            assert e1.event_type == e2.event_type
            assert e1.data == e2.data
    
    @given(num_bars=st.integers(min_value=10, max_value=50))
    @settings(max_examples=50, deadline=60000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multiple_runs_produce_identical_results(self, num_bars):
        """Feature: titan-quant, Property 2: Backtest Determinism"""
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        data_list = [
            {
                "symbol": "BTCUSDT", "exchange": "BINANCE",
                "timestamp": base_time + timedelta(minutes=i),
                "interval": "1m", "open_price": 100.0 + i,
                "high_price": 101.0 + i, "low_price": 99.0 + i,
                "close_price": 100.5 + i, "volume": 1000.0, "turnover": 100000.0,
            }
            for i in range(num_bars)
        ]
        
        results = []
        for run_idx in range(3):
            events, seq = self._run_backtest(data_list, str(self.snapshot_dir / f"run{run_idx}"))
            results.append((events, seq))
        
        base_events, base_seq = results[0]
        for run_idx in range(1, 3):
            events, seq = results[run_idx]
            assert seq == base_seq
            assert len(events) == len(base_events)


class TestEventSequenceMonotonicity:
    """Tests for event sequence monotonicity. Validates: Requirements 1.6, 1.7"""
    
    @given(num_events=st.integers(min_value=10, max_value=100))
    @settings(max_examples=100, deadline=10000)
    def test_sequence_numbers_are_monotonically_increasing(self, num_events):
        """Feature: titan-quant, Property 2: Backtest Determinism"""
        event_bus = EventBus()
        sequence_numbers = []
        
        for i in range(num_events):
            seq = event_bus.publish(
                event_type=EventType.BAR,
                data={"index": i, "price": 100 + i},
                source="test",
                timestamp=datetime(2024, 1, 1, 9, 30) + timedelta(minutes=i),
            )
            sequence_numbers.append(seq)
        
        for i in range(1, len(sequence_numbers)):
            assert sequence_numbers[i] > sequence_numbers[i - 1]
            assert sequence_numbers[i] == sequence_numbers[i - 1] + 1
    
    @given(event_types=st.lists(st.sampled_from(list(EventType)), min_size=5, max_size=50))
    @settings(max_examples=100, deadline=10000)
    def test_sequence_monotonicity_across_event_types(self, event_types):
        """Feature: titan-quant, Property 2: Backtest Determinism"""
        event_bus = EventBus()
        sequence_numbers = []
        
        for i, event_type in enumerate(event_types):
            seq = event_bus.publish(
                event_type=event_type,
                data={"index": i},
                source="test",
                timestamp=datetime(2024, 1, 1) + timedelta(seconds=i),
            )
            sequence_numbers.append(seq)
        
        for i in range(1, len(sequence_numbers)):
            assert sequence_numbers[i] > sequence_numbers[i - 1]
    
    def test_sequence_preserved_after_reset(self):
        """Feature: titan-quant, Property 2: Backtest Determinism"""
        event_bus = EventBus()
        
        for i in range(10):
            event_bus.publish(event_type=EventType.BAR, data={"index": i}, source="test")
        
        assert event_bus.get_current_sequence() == 10
        event_bus.reset()
        assert event_bus.get_current_sequence() == 0
        
        seq = event_bus.publish(event_type=EventType.BAR, data={"index": 0}, source="test")
        assert seq == 1
