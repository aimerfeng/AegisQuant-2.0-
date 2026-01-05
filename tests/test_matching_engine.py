"""
Property-Based Tests for Matching Engine

This module contains property-based tests using Hypothesis to verify
the correctness properties of the MatchingEngine implementation.

Property 13: Trade Record Completeness
    For any executed trade, the TradeRecord must contain all required fields:
    trade_id, order_id, symbol, direction, price, volume, commission, slippage,
    matching_mode, and timestamp.

Validates: Requirements 7.5
"""
from datetime import datetime

import pytest
from hypothesis import given, settings, strategies as st

from core.engine.matching import (
    MatchingConfig,
    MatchingEngine,
    MatchingMode,
    L2SimulationLevel,
    SlippageModel,
    TradeRecord,
)
from core.engine.types import OrderData, TickData


# Custom strategies for generating test data
@st.composite
def valid_tick_data(draw) -> TickData:
    """Generate valid TickData for testing."""
    symbol = draw(st.sampled_from(["BTC_USDT", "ETH_USDT", "SOL_USDT"]))
    exchange = draw(st.sampled_from(["binance", "okx", "huobi"]))
    
    # Generate realistic prices
    base_price = draw(st.floats(min_value=100.0, max_value=100000.0))
    spread = draw(st.floats(min_value=0.01, max_value=base_price * 0.01))
    
    bid_price = base_price
    ask_price = base_price + spread
    
    return TickData(
        symbol=symbol,
        exchange=exchange,
        datetime=datetime.now(),
        last_price=base_price + spread / 2,
        volume=draw(st.floats(min_value=0.1, max_value=1000.0)),
        bid_price_1=bid_price,
        bid_volume_1=draw(st.floats(min_value=1.0, max_value=100.0)),
        ask_price_1=ask_price,
        ask_volume_1=draw(st.floats(min_value=1.0, max_value=100.0)),
    )


@st.composite
def valid_order_data(draw, tick: TickData, is_market: bool = False) -> OrderData:
    """Generate valid OrderData that can be matched against the tick."""
    direction = draw(st.sampled_from(["LONG", "SHORT"]))
    offset = draw(st.sampled_from(["OPEN", "CLOSE"]))
    
    if is_market:
        price = 0.0  # Market order
    else:
        # Limit order that crosses the spread (will be filled)
        if direction == "LONG":
            price = tick.ask_price_1 * draw(st.floats(min_value=1.0, max_value=1.05))
        else:
            price = tick.bid_price_1 * draw(st.floats(min_value=0.95, max_value=1.0))
    
    return OrderData(
        order_id=f"order_{draw(st.integers(min_value=1, max_value=999999))}",
        symbol=tick.symbol,
        exchange=tick.exchange,
        direction=direction,
        offset=offset,
        price=price,
        volume=draw(st.floats(min_value=0.01, max_value=10.0)),
        traded=0.0,
        status="PENDING",
        is_manual=draw(st.booleans()),
        create_time=datetime.now(),
    )


@st.composite
def matching_config_strategy(draw) -> MatchingConfig:
    """Generate valid MatchingConfig for testing."""
    mode = draw(st.sampled_from([MatchingMode.L1, MatchingMode.L2]))
    
    l2_level = None
    if mode == MatchingMode.L2:
        l2_level = draw(st.sampled_from(list(L2SimulationLevel)))
    
    return MatchingConfig(
        mode=mode,
        l2_level=l2_level,
        commission_rate=draw(st.floats(min_value=0.0, max_value=0.01)),
        slippage_model=draw(st.sampled_from(list(SlippageModel))),
        slippage_value=draw(st.floats(min_value=0.0, max_value=0.001)),
        min_commission=draw(st.floats(min_value=0.0, max_value=1.0)),
        enable_partial_fill=draw(st.booleans()),
    )


class TestTradeRecordCompleteness:
    """
    Property 13: Trade Record Completeness
    
    *For any* executed trade, the TradeRecord must contain all required fields:
    trade_id, order_id, symbol, direction, price, volume, commission, slippage,
    matching_mode, and timestamp.
    
    **Validates: Requirements 7.5**
    """
    
    @given(
        tick=valid_tick_data(),
        is_market=st.booleans(),
    )
    @settings(max_examples=100, deadline=5000)
    def test_trade_record_contains_all_required_fields_l1(
        self, tick: TickData, is_market: bool
    ) -> None:
        """
        Property: For any trade executed in L1 mode, the TradeRecord must
        contain all required fields with valid values.
        
        Feature: titan-quant, Property 13: Trade Record Completeness
        """
        # Create L1 matching engine
        config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=0.0003,
            slippage_model=SlippageModel.FIXED,
            slippage_value=0.0001,
        )
        engine = MatchingEngine(config)
        
        # Generate order that will be filled
        order = OrderData(
            order_id="test_order_001",
            symbol=tick.symbol,
            exchange=tick.exchange,
            direction="LONG" if is_market else "LONG",
            offset="OPEN",
            price=0.0 if is_market else tick.ask_price_1 * 1.01,  # Market or limit crossing spread
            volume=1.0,
            traded=0.0,
            status="PENDING",
            is_manual=False,
            create_time=datetime.now(),
        )
        
        # Submit and process
        engine.submit_order(order)
        trades = engine.process_tick(tick)
        
        # Verify trade was executed
        assert len(trades) >= 1, "Expected at least one trade to be executed"
        
        trade = trades[0]
        
        # Verify all required fields are present and valid
        self._verify_trade_record_completeness(trade)
    
    @given(
        tick=valid_tick_data(),
        l2_level=st.sampled_from(list(L2SimulationLevel)),
    )
    @settings(max_examples=100, deadline=5000)
    def test_trade_record_contains_all_required_fields_l2(
        self, tick: TickData, l2_level: L2SimulationLevel
    ) -> None:
        """
        Property: For any trade executed in L2 mode, the TradeRecord must
        contain all required fields including L2-specific fields.
        
        Feature: titan-quant, Property 13: Trade Record Completeness
        """
        # Create L2 matching engine
        config = MatchingConfig(
            mode=MatchingMode.L2,
            l2_level=l2_level,
            commission_rate=0.0003,
            slippage_model=SlippageModel.FIXED,
            slippage_value=0.0001,
        )
        engine = MatchingEngine(config)
        
        # Generate market order (guaranteed to fill)
        order = OrderData(
            order_id="test_order_002",
            symbol=tick.symbol,
            exchange=tick.exchange,
            direction="LONG",
            offset="OPEN",
            price=0.0,  # Market order
            volume=1.0,
            traded=0.0,
            status="PENDING",
            is_manual=True,
            create_time=datetime.now(),
        )
        
        # Submit and process
        engine.submit_order(order)
        trades = engine.process_tick(tick)
        
        # Verify trade was executed
        assert len(trades) >= 1, "Expected at least one trade to be executed"
        
        trade = trades[0]
        
        # Verify all required fields are present and valid
        self._verify_trade_record_completeness(trade)
        
        # Verify L2-specific fields
        assert trade.matching_mode == MatchingMode.L2
        assert trade.l2_level == l2_level
        assert trade.queue_wait_time is not None
    
    @given(
        config=matching_config_strategy(),
        tick=valid_tick_data(),
    )
    @settings(max_examples=100, deadline=5000)
    def test_trade_record_completeness_with_various_configs(
        self, config: MatchingConfig, tick: TickData
    ) -> None:
        """
        Property: For any valid matching configuration and tick data,
        executed trades must have complete records.
        
        Feature: titan-quant, Property 13: Trade Record Completeness
        """
        engine = MatchingEngine(config)
        
        # Generate market order (guaranteed to fill)
        order = OrderData(
            order_id="test_order_003",
            symbol=tick.symbol,
            exchange=tick.exchange,
            direction="SHORT",
            offset="CLOSE",
            price=0.0,  # Market order
            volume=0.5,
            traded=0.0,
            status="PENDING",
            is_manual=False,
            create_time=datetime.now(),
        )
        
        # Submit and process
        engine.submit_order(order)
        trades = engine.process_tick(tick)
        
        # Verify trade was executed
        assert len(trades) >= 1, "Expected at least one trade to be executed"
        
        for trade in trades:
            self._verify_trade_record_completeness(trade)
    
    def _verify_trade_record_completeness(self, trade: TradeRecord) -> None:
        """Helper to verify all required fields in a TradeRecord."""
        # Required fields per Requirements 7.5
        assert trade.trade_id is not None and len(trade.trade_id) > 0, \
            "trade_id must be non-empty"
        
        assert trade.order_id is not None and len(trade.order_id) > 0, \
            "order_id must be non-empty"
        
        assert trade.symbol is not None and len(trade.symbol) > 0, \
            "symbol must be non-empty"
        
        assert trade.exchange is not None and len(trade.exchange) > 0, \
            "exchange must be non-empty"
        
        assert trade.direction in ("LONG", "SHORT"), \
            f"direction must be 'LONG' or 'SHORT', got {trade.direction}"
        
        assert trade.offset in ("OPEN", "CLOSE"), \
            f"offset must be 'OPEN' or 'CLOSE', got {trade.offset}"
        
        assert trade.price >= 0, \
            f"price must be non-negative, got {trade.price}"
        
        assert trade.volume > 0, \
            f"volume must be positive, got {trade.volume}"
        
        assert trade.turnover >= 0, \
            f"turnover must be non-negative, got {trade.turnover}"
        
        assert trade.commission >= 0, \
            f"commission must be non-negative, got {trade.commission}"
        
        assert trade.slippage >= 0, \
            f"slippage must be non-negative, got {trade.slippage}"
        
        assert isinstance(trade.matching_mode, MatchingMode), \
            f"matching_mode must be MatchingMode enum, got {type(trade.matching_mode)}"
        
        assert isinstance(trade.timestamp, datetime), \
            f"timestamp must be datetime, got {type(trade.timestamp)}"
        
        assert isinstance(trade.is_manual, bool), \
            f"is_manual must be bool, got {type(trade.is_manual)}"
        
        # Verify turnover calculation
        expected_turnover = trade.price * trade.volume
        assert abs(trade.turnover - expected_turnover) < 0.01, \
            f"turnover should be price * volume, expected {expected_turnover}, got {trade.turnover}"


class TestMatchingEngineBasicFunctionality:
    """Unit tests for basic MatchingEngine functionality."""
    
    def test_l1_market_order_fills_at_opposite_price(self) -> None:
        """Test that L1 market orders fill at the opposite side price."""
        config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=0.0,
            slippage_value=0.0,
        )
        engine = MatchingEngine(config)
        
        tick = TickData(
            symbol="BTC_USDT",
            exchange="binance",
            datetime=datetime.now(),
            last_price=50000.0,
            volume=100.0,
            bid_price_1=49990.0,
            bid_volume_1=10.0,
            ask_price_1=50010.0,
            ask_volume_1=10.0,
        )
        
        # Buy order should fill at ask price
        buy_order = OrderData(
            order_id="buy_001",
            symbol="BTC_USDT",
            exchange="binance",
            direction="LONG",
            offset="OPEN",
            price=0.0,  # Market order
            volume=1.0,
            traded=0.0,
            status="PENDING",
            is_manual=False,
            create_time=datetime.now(),
        )
        
        engine.submit_order(buy_order)
        trades = engine.process_tick(tick)
        
        assert len(trades) == 1
        assert trades[0].price == tick.ask_price_1
        
        # Sell order should fill at bid price
        engine.reset()
        sell_order = OrderData(
            order_id="sell_001",
            symbol="BTC_USDT",
            exchange="binance",
            direction="SHORT",
            offset="CLOSE",
            price=0.0,  # Market order
            volume=1.0,
            traded=0.0,
            status="PENDING",
            is_manual=False,
            create_time=datetime.now(),
        )
        
        engine.submit_order(sell_order)
        trades = engine.process_tick(tick)
        
        assert len(trades) == 1
        assert trades[0].price == tick.bid_price_1
    
    def test_commission_calculation(self) -> None:
        """Test that commission is calculated correctly."""
        config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=0.001,  # 0.1%
            slippage_value=0.0,
            min_commission=0.0,
        )
        engine = MatchingEngine(config)
        
        tick = TickData(
            symbol="BTC_USDT",
            exchange="binance",
            datetime=datetime.now(),
            last_price=50000.0,
            volume=100.0,
            bid_price_1=50000.0,
            bid_volume_1=10.0,
            ask_price_1=50000.0,
            ask_volume_1=10.0,
        )
        
        order = OrderData(
            order_id="order_001",
            symbol="BTC_USDT",
            exchange="binance",
            direction="LONG",
            offset="OPEN",
            price=0.0,
            volume=1.0,
            traded=0.0,
            status="PENDING",
            is_manual=False,
            create_time=datetime.now(),
        )
        
        engine.submit_order(order)
        trades = engine.process_tick(tick)
        
        assert len(trades) == 1
        expected_commission = 50000.0 * 1.0 * 0.001  # turnover * rate
        assert abs(trades[0].commission - expected_commission) < 0.01
    
    def test_cancel_order(self) -> None:
        """Test order cancellation."""
        engine = MatchingEngine()
        
        order = OrderData(
            order_id="order_001",
            symbol="BTC_USDT",
            exchange="binance",
            direction="LONG",
            offset="OPEN",
            price=45000.0,  # Limit order below market
            volume=1.0,
            traded=0.0,
            status="PENDING",
            is_manual=False,
            create_time=datetime.now(),
        )
        
        engine.submit_order(order)
        assert len(engine.get_pending_orders()) == 1
        
        result = engine.cancel_order("order_001")
        assert result is True
        assert len(engine.get_pending_orders()) == 0
        
        # Cancel non-existent order
        result = engine.cancel_order("non_existent")
        assert result is False
    
    def test_simulation_limitations_description(self) -> None:
        """Test that simulation limitations are properly described."""
        # L1 mode
        config_l1 = MatchingConfig(mode=MatchingMode.L1)
        engine_l1 = MatchingEngine(config_l1)
        limitations_l1 = engine_l1.get_simulation_limitations()
        assert "L1" in limitations_l1
        assert "infinite liquidity" in limitations_l1.lower()
        
        # L2 Level-1
        config_l2_1 = MatchingConfig(
            mode=MatchingMode.L2,
            l2_level=L2SimulationLevel.LEVEL_1
        )
        engine_l2_1 = MatchingEngine(config_l2_1)
        limitations_l2_1 = engine_l2_1.get_simulation_limitations()
        assert "Queue Position" in limitations_l2_1
        
        # L2 Level-2
        config_l2_2 = MatchingConfig(
            mode=MatchingMode.L2,
            l2_level=L2SimulationLevel.LEVEL_2
        )
        engine_l2_2 = MatchingEngine(config_l2_2)
        limitations_l2_2 = engine_l2_2.get_simulation_limitations()
        assert "Order Book" in limitations_l2_2
    
    def test_quality_metrics_tracking(self) -> None:
        """Test that quality metrics are properly tracked."""
        config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=0.0003,
            slippage_value=0.0001,
        )
        engine = MatchingEngine(config)
        
        tick = TickData(
            symbol="BTC_USDT",
            exchange="binance",
            datetime=datetime.now(),
            last_price=50000.0,
            volume=100.0,
            bid_price_1=49990.0,
            bid_volume_1=10.0,
            ask_price_1=50010.0,
            ask_volume_1=10.0,
        )
        
        # Submit and execute multiple orders
        for i in range(5):
            order = OrderData(
                order_id=f"order_{i}",
                symbol="BTC_USDT",
                exchange="binance",
                direction="LONG",
                offset="OPEN",
                price=0.0,
                volume=1.0,
                traded=0.0,
                status="PENDING",
                is_manual=False,
                create_time=datetime.now(),
            )
            engine.submit_order(order)
            engine.process_tick(tick)
        
        metrics = engine.get_quality_metrics()
        
        assert metrics.total_orders == 5
        assert metrics.filled_orders == 5
        assert metrics.total_turnover > 0
        assert metrics.total_commission > 0
