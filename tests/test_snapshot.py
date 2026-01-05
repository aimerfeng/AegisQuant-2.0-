"""
Property-Based Tests for Snapshot Manager

This module contains property-based tests using Hypothesis to verify
the correctness properties of the Snapshot Manager implementation.

Property 10: Snapshot Round-Trip
    For any valid backtest state, creating a snapshot and restoring from it
    must produce an identical state including account balance, positions,
    strategy variables, event queue position, and data stream position.

Validates: Requirements 5.5, 5.6
"""
import os
import tempfile
from datetime import datetime

import pytest
from hypothesis import given, settings, strategies as st, assume

from core.engine.snapshot import (
    AccountState,
    PositionState,
    StrategyState,
    Snapshot,
    SnapshotManager,
)


# Custom strategies for generating valid test data
@st.composite
def account_state_strategy(draw):
    """Generate valid AccountState instances."""
    cash = draw(st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False))
    frozen_margin = draw(st.floats(min_value=0, max_value=cash, allow_nan=False, allow_infinity=False))
    available_balance = cash - frozen_margin
    unrealized_pnl = draw(st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False))
    total_equity = cash + unrealized_pnl
    
    return AccountState(
        cash=cash,
        frozen_margin=frozen_margin,
        available_balance=available_balance,
        total_equity=total_equity,
        unrealized_pnl=unrealized_pnl,
    )


@st.composite
def position_state_strategy(draw):
    """Generate valid PositionState instances."""
    symbol = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_')))
    assume(len(symbol) > 0)
    
    exchange = draw(st.sampled_from(["binance", "okx", "huobi", "bybit"]))
    direction = draw(st.sampled_from(["LONG", "SHORT"]))
    volume = draw(st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
    cost_price = draw(st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False))
    unrealized_pnl = draw(st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False))
    margin = draw(st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False))
    
    return PositionState(
        symbol=symbol,
        exchange=exchange,
        direction=direction,
        volume=volume,
        cost_price=cost_price,
        unrealized_pnl=unrealized_pnl,
        margin=margin,
        open_time=None,  # Simplified for testing
    )


@st.composite
def strategy_state_strategy(draw):
    """Generate valid StrategyState instances."""
    strategy_id = draw(st.text(min_size=1, max_size=36, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_')))
    assume(len(strategy_id) > 0)
    
    class_name = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_')))
    assume(len(class_name) > 0)
    
    # Generate simple parameters (JSON-serializable)
    parameters = draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_')),
        values=st.one_of(
            st.integers(min_value=-1000000, max_value=1000000),
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            st.booleans(),
            st.text(min_size=0, max_size=50),
        ),
        min_size=0,
        max_size=10,
    ))
    
    # Generate simple variables (JSON-serializable)
    variables = draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_')),
        values=st.one_of(
            st.integers(min_value=-1000000, max_value=1000000),
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            st.booleans(),
            st.text(min_size=0, max_size=50),
            st.lists(st.integers(min_value=-1000, max_value=1000), min_size=0, max_size=10),
        ),
        min_size=0,
        max_size=10,
    ))
    
    is_active = draw(st.booleans())
    
    return StrategyState(
        strategy_id=strategy_id,
        class_name=class_name,
        parameters=parameters,
        variables=variables,
        is_active=is_active,
    )


class TestSnapshotRoundTrip:
    """
    Property 10: Snapshot Round-Trip
    
    *For any* valid backtest state, creating a snapshot and restoring from it
    must produce an identical state including account balance, positions,
    strategy variables, event queue position, and data stream position.
    
    **Validates: Requirements 5.5, 5.6**
    """
    
    @given(
        account=account_state_strategy(),
        positions=st.lists(position_state_strategy(), min_size=0, max_size=5),
        strategies=st.lists(strategy_state_strategy(), min_size=0, max_size=3),
        event_sequence=st.integers(min_value=0, max_value=1000000),
        data_index=st.integers(min_value=0, max_value=1000000),
    )
    @settings(max_examples=100, deadline=10000)
    def test_snapshot_save_load_round_trip(
        self,
        account: AccountState,
        positions: list[PositionState],
        strategies: list[StrategyState],
        event_sequence: int,
        data_index: int,
    ) -> None:
        """
        Property: For any valid system state, saving a snapshot and loading it
        back must produce an identical state.
        
        Feature: titan-quant, Property 10: Snapshot Round-Trip
        """
        manager = SnapshotManager()
        
        # Create a snapshot with the generated state
        data_timestamp = datetime(2024, 1, 15, 10, 30, 0)
        pending_events = [{"type": "tick", "seq": i} for i in range(min(3, event_sequence % 10))]
        
        original_snapshot = manager.create_snapshot(
            account=account,
            positions=positions,
            strategies=strategies,
            event_sequence=event_sequence,
            pending_events=pending_events,
            data_timestamp=data_timestamp,
            data_index=data_index,
            description="Test snapshot",
        )
        
        # Save and load the snapshot
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            manager.save_snapshot(original_snapshot, temp_path)
            loaded_snapshot = manager.load_snapshot(temp_path)
            
            assert loaded_snapshot is not None, "Failed to load snapshot"
            
            # Verify all fields match
            # Note: Version may be upgraded by migration (TD-003), so check it's compatible
            assert loaded_snapshot.version in manager.COMPATIBLE_VERSIONS
            assert loaded_snapshot.snapshot_id == original_snapshot.snapshot_id
            
            # Account state
            assert loaded_snapshot.account.cash == original_snapshot.account.cash
            assert loaded_snapshot.account.frozen_margin == original_snapshot.account.frozen_margin
            assert loaded_snapshot.account.available_balance == original_snapshot.account.available_balance
            assert loaded_snapshot.account.total_equity == original_snapshot.account.total_equity
            assert loaded_snapshot.account.unrealized_pnl == original_snapshot.account.unrealized_pnl
            
            # Positions
            assert len(loaded_snapshot.positions) == len(original_snapshot.positions)
            for orig_pos, loaded_pos in zip(original_snapshot.positions, loaded_snapshot.positions):
                assert loaded_pos.symbol == orig_pos.symbol
                assert loaded_pos.exchange == orig_pos.exchange
                assert loaded_pos.direction == orig_pos.direction
                assert loaded_pos.volume == orig_pos.volume
                assert loaded_pos.cost_price == orig_pos.cost_price
                assert loaded_pos.unrealized_pnl == orig_pos.unrealized_pnl
                assert loaded_pos.margin == orig_pos.margin
            
            # Strategies
            assert len(loaded_snapshot.strategies) == len(original_snapshot.strategies)
            for orig_strat, loaded_strat in zip(original_snapshot.strategies, loaded_snapshot.strategies):
                assert loaded_strat.strategy_id == orig_strat.strategy_id
                assert loaded_strat.class_name == orig_strat.class_name
                assert loaded_strat.parameters == orig_strat.parameters
                assert loaded_strat.variables == orig_strat.variables
                assert loaded_strat.is_active == orig_strat.is_active
            
            # Event bus state
            assert loaded_snapshot.event_sequence == original_snapshot.event_sequence
            assert loaded_snapshot.pending_events == original_snapshot.pending_events
            
            # Data stream position
            assert loaded_snapshot.data_timestamp == original_snapshot.data_timestamp
            assert loaded_snapshot.data_index == original_snapshot.data_index
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    @given(account=account_state_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_account_state_round_trip(self, account: AccountState) -> None:
        """
        Property: AccountState serialization and deserialization must be lossless.
        
        Feature: titan-quant, Property 10: Snapshot Round-Trip
        """
        # Convert to dict and back
        account_dict = account.to_dict()
        restored = AccountState.from_dict(account_dict)
        
        assert restored.cash == account.cash
        assert restored.frozen_margin == account.frozen_margin
        assert restored.available_balance == account.available_balance
        assert restored.total_equity == account.total_equity
        assert restored.unrealized_pnl == account.unrealized_pnl
    
    @given(position=position_state_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_position_state_round_trip(self, position: PositionState) -> None:
        """
        Property: PositionState serialization and deserialization must be lossless.
        
        Feature: titan-quant, Property 10: Snapshot Round-Trip
        """
        # Convert to dict and back
        position_dict = position.to_dict()
        restored = PositionState.from_dict(position_dict)
        
        assert restored.symbol == position.symbol
        assert restored.exchange == position.exchange
        assert restored.direction == position.direction
        assert restored.volume == position.volume
        assert restored.cost_price == position.cost_price
        assert restored.unrealized_pnl == position.unrealized_pnl
        assert restored.margin == position.margin
    
    @given(strategy=strategy_state_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_strategy_state_round_trip(self, strategy: StrategyState) -> None:
        """
        Property: StrategyState serialization and deserialization must be lossless.
        
        Feature: titan-quant, Property 10: Snapshot Round-Trip
        """
        # Convert to dict and back
        strategy_dict = strategy.to_dict()
        restored = StrategyState.from_dict(strategy_dict)
        
        assert restored.strategy_id == strategy.strategy_id
        assert restored.class_name == strategy.class_name
        assert restored.parameters == strategy.parameters
        assert restored.variables == strategy.variables
        assert restored.is_active == strategy.is_active


class TestSnapshotVersionCompatibility:
    """Tests for snapshot version compatibility checking."""
    
    def test_compatible_version_loads_successfully(self) -> None:
        """Test that snapshots with compatible versions load successfully."""
        manager = SnapshotManager()
        
        account = AccountState(cash=100000, frozen_margin=0, available_balance=100000)
        snapshot = manager.create_snapshot(
            account=account,
            positions=[],
            strategies=[],
            event_sequence=0,
            pending_events=[],
            data_timestamp=datetime.now(),
            data_index=0,
        )
        
        assert manager.is_compatible(snapshot)
    
    def test_incompatible_version_raises_error(self) -> None:
        """Test that snapshots with incompatible versions raise SnapshotError."""
        manager = SnapshotManager()
        
        # Create a snapshot with an incompatible version
        account = AccountState(cash=100000, frozen_margin=0, available_balance=100000)
        snapshot = Snapshot(
            version="0.0.1",  # Incompatible version
            snapshot_id="test-id",
            create_time=datetime.now(),
            account=account,
            positions=[],
            strategies=[],
            event_sequence=0,
            pending_events=[],
            data_timestamp=datetime.now(),
            data_index=0,
        )
        
        assert not manager.is_compatible(snapshot)
    
    def test_restore_validates_snapshot(self) -> None:
        """Test that restore_snapshot validates the snapshot before restoration."""
        manager = SnapshotManager()
        
        account = AccountState(cash=100000, frozen_margin=0, available_balance=100000)
        snapshot = manager.create_snapshot(
            account=account,
            positions=[],
            strategies=[],
            event_sequence=0,
            pending_events=[],
            data_timestamp=datetime.now(),
            data_index=0,
        )
        
        # Should return True for valid snapshot
        assert manager.restore_snapshot(snapshot)


class TestSnapshotBasicFunctionality:
    """Unit tests for basic Snapshot functionality."""
    
    def test_create_snapshot_generates_unique_id(self) -> None:
        """Test that each snapshot gets a unique ID."""
        manager = SnapshotManager()
        account = AccountState(cash=100000, frozen_margin=0, available_balance=100000)
        
        snapshot1 = manager.create_snapshot(
            account=account,
            positions=[],
            strategies=[],
            event_sequence=0,
            pending_events=[],
            data_timestamp=datetime.now(),
            data_index=0,
        )
        
        snapshot2 = manager.create_snapshot(
            account=account,
            positions=[],
            strategies=[],
            event_sequence=0,
            pending_events=[],
            data_timestamp=datetime.now(),
            data_index=0,
        )
        
        assert snapshot1.snapshot_id != snapshot2.snapshot_id
    
    def test_load_nonexistent_file_returns_none(self) -> None:
        """Test that loading a non-existent file returns None."""
        manager = SnapshotManager()
        result = manager.load_snapshot("/nonexistent/path/snapshot.json")
        assert result is None
    
    def test_snapshot_with_positions_and_strategies(self) -> None:
        """Test snapshot creation with positions and strategies."""
        manager = SnapshotManager()
        
        account = AccountState(
            cash=100000,
            frozen_margin=5000,
            available_balance=95000,
            total_equity=105000,
            unrealized_pnl=5000,
        )
        
        positions = [
            PositionState(
                symbol="BTC_USDT",
                exchange="binance",
                direction="LONG",
                volume=1.0,
                cost_price=50000,
                unrealized_pnl=5000,
                margin=5000,
            ),
            PositionState(
                symbol="ETH_USDT",
                exchange="binance",
                direction="SHORT",
                volume=10.0,
                cost_price=3000,
                unrealized_pnl=-500,
                margin=3000,
            ),
        ]
        
        strategies = [
            StrategyState(
                strategy_id="strat1",
                class_name="MACrossStrategy",
                parameters={"fast_period": 10, "slow_period": 20},
                variables={"position": 1, "last_signal": "buy"},
                is_active=True,
            ),
        ]
        
        snapshot = manager.create_snapshot(
            account=account,
            positions=positions,
            strategies=strategies,
            event_sequence=1000,
            pending_events=[{"type": "tick"}],
            data_timestamp=datetime(2024, 1, 15, 10, 30, 0),
            data_index=5000,
            backtest_id="bt-001",
            description="Test backtest snapshot",
        )
        
        assert snapshot.version == SnapshotManager.CURRENT_VERSION
        assert len(snapshot.positions) == 2
        assert len(snapshot.strategies) == 1
        assert snapshot.event_sequence == 1000
        assert snapshot.data_index == 5000
        assert snapshot.backtest_id == "bt-001"
