"""
Property-Based Tests for Manual Trading

This module contains property-based tests using Hypothesis to verify
the correctness properties of the manual trading functionality.

Property 11: Manual Order Marking
    For any order submitted through the manual trading interface, the order
    must have is_manual=true, and the corresponding audit log entry must be
    categorized as "MANUAL_TRADE" distinct from "AUTO_TRADE".

Property 12: Close All Positions
    For any non-empty position set, executing "close all" must result in
    close orders being generated for all positions at market price.

Validates: Requirements 6.2, 6.3, 6.4
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from core.handlers import MessageHandlers, SystemState
from core.server import Message, MessageType
from core.engine.types import OrderData, to_decimal


# Custom strategies for generating test data
@st.composite
def valid_manual_order_payload(draw) -> Dict[str, Any]:
    """Generate valid manual order payload for testing."""
    symbol = draw(st.sampled_from(["BTC_USDT", "ETH_USDT", "SOL_USDT", "DOGE_USDT"]))
    exchange = draw(st.sampled_from(["binance", "okx", "huobi", "backtest"]))
    direction = draw(st.sampled_from(["LONG", "SHORT"]))
    offset = draw(st.sampled_from(["OPEN", "CLOSE"]))
    price = draw(st.floats(min_value=0.0, max_value=100000.0))  # 0 for market order
    volume = draw(st.floats(min_value=0.001, max_value=1000.0))
    
    return {
        "symbol": symbol,
        "exchange": exchange,
        "direction": direction,
        "offset": offset,
        "price": price,
        "volume": volume,
    }


@st.composite
def valid_position(draw) -> Dict[str, Any]:
    """Generate valid position data for testing."""
    symbol = draw(st.sampled_from(["BTC_USDT", "ETH_USDT", "SOL_USDT", "DOGE_USDT"]))
    exchange = draw(st.sampled_from(["binance", "okx", "huobi", "backtest"]))
    direction = draw(st.sampled_from(["LONG", "SHORT"]))
    volume = draw(st.floats(min_value=0.001, max_value=100.0))
    cost_price = draw(st.floats(min_value=1.0, max_value=100000.0))
    
    return {
        "symbol": symbol,
        "exchange": exchange,
        "direction": direction,
        "volume": volume,
        "cost_price": cost_price,
        "unrealized_pnl": draw(st.floats(min_value=-10000.0, max_value=10000.0)),
    }


@st.composite
def position_list(draw, min_size: int = 1, max_size: int = 10) -> List[Dict[str, Any]]:
    """Generate a list of positions for testing."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    positions = []
    used_symbols = set()
    
    for _ in range(size):
        position = draw(valid_position())
        # Ensure unique symbols
        while position["symbol"] in used_symbols:
            position["symbol"] = draw(st.sampled_from(
                [f"TEST_{i}_USDT" for i in range(100)]
            ))
        used_symbols.add(position["symbol"])
        positions.append(position)
    
    return positions


class TestManualOrderMarking:
    """
    Property 11: Manual Order Marking
    
    *For any* order submitted through the manual trading interface, the order
    must have is_manual=true, and the corresponding audit log entry must be
    categorized as "MANUAL_TRADE" distinct from "AUTO_TRADE".
    
    **Validates: Requirements 6.2, 6.3**
    """
    
    @given(payload=valid_manual_order_payload())
    @settings(max_examples=100, deadline=5000)
    def test_manual_order_is_marked_as_manual(self, payload: Dict[str, Any]) -> None:
        """
        Property: For any valid manual order payload, the submitted order
        must have is_manual=True in the response.
        
        Feature: titan-quant, Property 11: Manual Order Marking
        """
        handlers = MessageHandlers()
        
        # Create mock matching engine to capture submitted orders
        mock_engine = MagicMock()
        submitted_orders = []
        
        def capture_order(order: OrderData) -> str:
            submitted_orders.append(order)
            return order.order_id
        
        mock_engine.submit_order.side_effect = capture_order
        handlers.set_matching_engine(mock_engine)
        
        # Create manual order message
        msg = Message.create(MessageType.MANUAL_ORDER, payload=payload)
        
        # Handle the message
        response = handlers.handle_manual_order(msg)
        
        # Verify response indicates success
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        assert response.payload["is_manual"] is True
        
        # Verify the order submitted to matching engine has is_manual=True
        assert len(submitted_orders) == 1
        submitted_order = submitted_orders[0]
        assert submitted_order.is_manual is True, \
            "Manual order must have is_manual=True"
        
        # Verify order details match payload
        assert submitted_order.symbol == payload["symbol"]
        assert submitted_order.direction == payload["direction"]
        assert submitted_order.offset == payload["offset"]
        assert float(submitted_order.volume) == pytest.approx(payload["volume"], rel=1e-6)
    
    @given(
        symbol=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_')),
        direction=st.sampled_from(["LONG", "SHORT"]),
        offset=st.sampled_from(["OPEN", "CLOSE"]),
        price=st.floats(min_value=0.0, max_value=100000.0),
        volume=st.floats(min_value=0.001, max_value=1000.0),
    )
    @settings(max_examples=100, deadline=5000)
    def test_manual_order_preserves_all_fields(
        self,
        symbol: str,
        direction: str,
        offset: str,
        price: float,
        volume: float,
    ) -> None:
        """
        Property: For any manual order, all input fields must be preserved
        in the submitted order.
        
        Feature: titan-quant, Property 11: Manual Order Marking
        """
        handlers = MessageHandlers()
        
        # Create mock matching engine
        mock_engine = MagicMock()
        submitted_orders = []
        mock_engine.submit_order.side_effect = lambda o: (submitted_orders.append(o), o.order_id)[1]
        handlers.set_matching_engine(mock_engine)
        
        payload = {
            "symbol": symbol,
            "direction": direction,
            "offset": offset,
            "price": price,
            "volume": volume,
        }
        
        msg = Message.create(MessageType.MANUAL_ORDER, payload=payload)
        response = handlers.handle_manual_order(msg)
        
        assert response.payload["success"] is True
        assert len(submitted_orders) == 1
        
        order = submitted_orders[0]
        assert order.symbol == symbol
        assert order.direction == direction
        assert order.offset == offset
        assert float(order.price) == pytest.approx(price, rel=1e-6)
        assert float(order.volume) == pytest.approx(volume, rel=1e-6)
        assert order.is_manual is True
    
    def test_manual_order_distinct_from_auto_order(self) -> None:
        """
        Test that manual orders are distinguishable from auto orders.
        
        Feature: titan-quant, Property 11: Manual Order Marking
        """
        handlers = MessageHandlers()
        
        mock_engine = MagicMock()
        submitted_orders = []
        mock_engine.submit_order.side_effect = lambda o: (submitted_orders.append(o), o.order_id)[1]
        handlers.set_matching_engine(mock_engine)
        
        # Submit manual order
        manual_payload = {
            "symbol": "BTC_USDT",
            "direction": "LONG",
            "offset": "OPEN",
            "price": 50000.0,
            "volume": 1.0,
        }
        
        msg = Message.create(MessageType.MANUAL_ORDER, payload=manual_payload)
        handlers.handle_manual_order(msg)
        
        # Verify manual order
        assert len(submitted_orders) == 1
        manual_order = submitted_orders[0]
        assert manual_order.is_manual is True
        
        # Create an auto order for comparison
        auto_order = OrderData(
            order_id="auto_001",
            symbol="BTC_USDT",
            exchange="binance",
            direction="LONG",
            offset="OPEN",
            price=to_decimal(50000.0),
            volume=to_decimal(1.0),
            traded=to_decimal(0),
            status="PENDING",
            is_manual=False,  # Auto order
            create_time=datetime.now(),
        )
        
        # Verify distinction
        assert manual_order.is_manual != auto_order.is_manual
        assert manual_order.is_manual is True
        assert auto_order.is_manual is False


class TestCloseAllPositions:
    """
    Property 12: Close All Positions
    
    *For any* non-empty position set, executing "close all" must result in
    close orders being generated for all positions at market price.
    
    **Validates: Requirements 6.4**
    """
    
    @given(positions=position_list(min_size=1, max_size=10))
    @settings(max_examples=100, deadline=5000)
    def test_close_all_generates_orders_for_all_positions(
        self, positions: List[Dict[str, Any]]
    ) -> None:
        """
        Property: For any non-empty position set, close_all must generate
        a close order for each position.
        
        Feature: titan-quant, Property 12: Close All Positions
        """
        handlers = MessageHandlers()
        
        # Set up positions in state
        handlers._state.positions = positions
        
        # Create mock matching engine to capture orders
        mock_engine = MagicMock()
        submitted_orders = []
        mock_engine.submit_order.side_effect = lambda o: (submitted_orders.append(o), o.order_id)[1]
        handlers.set_matching_engine(mock_engine)
        
        # Execute close all
        msg = Message.create(MessageType.CLOSE_ALL)
        response = handlers.handle_close_all(msg)
        
        # Verify response
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        assert response.payload["closed_count"] == len(positions)
        
        # Verify orders were generated for all positions
        assert len(submitted_orders) == len(positions)
        
        # Verify each order is a close order with correct properties
        position_symbols = {p["symbol"] for p in positions}
        order_symbols = {o.symbol for o in submitted_orders}
        assert position_symbols == order_symbols, \
            "Close orders must be generated for all position symbols"
        
        for order in submitted_orders:
            assert order.offset == "CLOSE", "All orders must be CLOSE orders"
            assert order.is_manual is True, "Close all orders must be marked as manual"
            assert float(order.price) == 0.0, "Close all orders must be market orders (price=0)"
    
    @given(positions=position_list(min_size=1, max_size=5))
    @settings(max_examples=100, deadline=5000)
    def test_close_all_uses_opposite_direction(
        self, positions: List[Dict[str, Any]]
    ) -> None:
        """
        Property: For any position, the close order must use the opposite
        direction (LONG position -> SHORT close, SHORT position -> LONG close).
        
        Feature: titan-quant, Property 12: Close All Positions
        """
        handlers = MessageHandlers()
        handlers._state.positions = positions
        
        mock_engine = MagicMock()
        submitted_orders = []
        mock_engine.submit_order.side_effect = lambda o: (submitted_orders.append(o), o.order_id)[1]
        handlers.set_matching_engine(mock_engine)
        
        msg = Message.create(MessageType.CLOSE_ALL)
        handlers.handle_close_all(msg)
        
        # Create mapping of position symbol to direction
        position_directions = {p["symbol"]: p["direction"] for p in positions}
        
        # Verify each close order has opposite direction
        for order in submitted_orders:
            position_direction = position_directions[order.symbol]
            expected_close_direction = "SHORT" if position_direction == "LONG" else "LONG"
            assert order.direction == expected_close_direction, \
                f"Close order for {position_direction} position must be {expected_close_direction}"
    
    @given(positions=position_list(min_size=1, max_size=5))
    @settings(max_examples=100, deadline=5000)
    def test_close_all_uses_correct_volume(
        self, positions: List[Dict[str, Any]]
    ) -> None:
        """
        Property: For any position, the close order volume must equal
        the position volume.
        
        Feature: titan-quant, Property 12: Close All Positions
        """
        handlers = MessageHandlers()
        handlers._state.positions = positions
        
        mock_engine = MagicMock()
        submitted_orders = []
        mock_engine.submit_order.side_effect = lambda o: (submitted_orders.append(o), o.order_id)[1]
        handlers.set_matching_engine(mock_engine)
        
        msg = Message.create(MessageType.CLOSE_ALL)
        handlers.handle_close_all(msg)
        
        # Create mapping of position symbol to volume
        position_volumes = {p["symbol"]: p["volume"] for p in positions}
        
        # Verify each close order has correct volume
        for order in submitted_orders:
            expected_volume = position_volumes[order.symbol]
            assert float(order.volume) == pytest.approx(expected_volume, rel=1e-6), \
                f"Close order volume must equal position volume"
    
    def test_close_all_with_empty_positions(self) -> None:
        """
        Test that close_all with no positions returns success with zero count.
        
        Feature: titan-quant, Property 12: Close All Positions
        """
        handlers = MessageHandlers()
        handlers._state.positions = []
        
        mock_engine = MagicMock()
        handlers.set_matching_engine(mock_engine)
        
        msg = Message.create(MessageType.CLOSE_ALL)
        response = handlers.handle_close_all(msg)
        
        assert response.payload["success"] is True
        assert response.payload["closed_count"] == 0
        assert response.payload["message"] == "No positions to close"
        
        # Verify no orders were submitted
        mock_engine.submit_order.assert_not_called()
    
    def test_close_all_orders_are_market_orders(self) -> None:
        """
        Test that all close orders are market orders (price=0).
        
        Feature: titan-quant, Property 12: Close All Positions
        """
        handlers = MessageHandlers()
        handlers._state.positions = [
            {"symbol": "BTC_USDT", "direction": "LONG", "volume": 1.0, "exchange": "binance"},
            {"symbol": "ETH_USDT", "direction": "SHORT", "volume": 5.0, "exchange": "binance"},
        ]
        
        mock_engine = MagicMock()
        submitted_orders = []
        mock_engine.submit_order.side_effect = lambda o: (submitted_orders.append(o), o.order_id)[1]
        handlers.set_matching_engine(mock_engine)
        
        msg = Message.create(MessageType.CLOSE_ALL)
        handlers.handle_close_all(msg)
        
        for order in submitted_orders:
            assert float(order.price) == 0.0, \
                "Close all orders must be market orders with price=0"


class TestManualTradingValidation:
    """Unit tests for manual trading input validation."""
    
    def test_manual_order_missing_symbol(self) -> None:
        """Test that missing symbol returns error."""
        handlers = MessageHandlers()
        
        payload = {
            "direction": "LONG",
            "offset": "OPEN",
            "price": 50000.0,
            "volume": 1.0,
        }
        
        msg = Message.create(MessageType.MANUAL_ORDER, payload=payload)
        response = handlers.handle_manual_order(msg)
        
        assert response.type == MessageType.ERROR
        assert "Missing required field: symbol" in response.payload["error"]
    
    def test_manual_order_invalid_direction(self) -> None:
        """Test that invalid direction returns error."""
        handlers = MessageHandlers()
        
        payload = {
            "symbol": "BTC_USDT",
            "direction": "INVALID",
            "offset": "OPEN",
            "price": 50000.0,
            "volume": 1.0,
        }
        
        msg = Message.create(MessageType.MANUAL_ORDER, payload=payload)
        response = handlers.handle_manual_order(msg)
        
        assert response.type == MessageType.ERROR
        assert "Invalid direction" in response.payload["error"]
    
    def test_manual_order_invalid_offset(self) -> None:
        """Test that invalid offset returns error."""
        handlers = MessageHandlers()
        
        payload = {
            "symbol": "BTC_USDT",
            "direction": "LONG",
            "offset": "INVALID",
            "price": 50000.0,
            "volume": 1.0,
        }
        
        msg = Message.create(MessageType.MANUAL_ORDER, payload=payload)
        response = handlers.handle_manual_order(msg)
        
        assert response.type == MessageType.ERROR
        assert "Invalid offset" in response.payload["error"]
    
    def test_manual_order_zero_volume(self) -> None:
        """Test that zero volume returns error."""
        handlers = MessageHandlers()
        
        payload = {
            "symbol": "BTC_USDT",
            "direction": "LONG",
            "offset": "OPEN",
            "price": 50000.0,
            "volume": 0,
        }
        
        msg = Message.create(MessageType.MANUAL_ORDER, payload=payload)
        response = handlers.handle_manual_order(msg)
        
        assert response.type == MessageType.ERROR
        assert "Volume must be positive" in response.payload["error"]
    
    def test_manual_order_negative_volume(self) -> None:
        """Test that negative volume returns error."""
        handlers = MessageHandlers()
        
        payload = {
            "symbol": "BTC_USDT",
            "direction": "LONG",
            "offset": "OPEN",
            "price": 50000.0,
            "volume": -1.0,
        }
        
        msg = Message.create(MessageType.MANUAL_ORDER, payload=payload)
        response = handlers.handle_manual_order(msg)
        
        assert response.type == MessageType.ERROR
        assert "Volume must be positive" in response.payload["error"]
