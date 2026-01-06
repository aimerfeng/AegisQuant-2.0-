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
from decimal import Decimal

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
        # Use Decimal arithmetic for price calculation
        order_price = Decimal("0") if is_market else tick.ask_price_1 * Decimal("1.01")
        order = OrderData(
            order_id="test_order_001",
            symbol=tick.symbol,
            exchange=tick.exchange,
            direction="LONG" if is_market else "LONG",
            offset="OPEN",
            price=order_price,  # Market or limit crossing spread
            volume=Decimal("1.0"),
            traded=Decimal("0"),
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
        
        # Verify turnover calculation (using Decimal comparison)
        expected_turnover = trade.price * trade.volume
        assert abs(float(trade.turnover) - float(expected_turnover)) < 0.01, \
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
        expected_commission = Decimal("50000.0") * Decimal("1.0") * Decimal("0.001")  # turnover * rate
        assert abs(float(trades[0].commission) - float(expected_commission)) < 0.01
    
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


class TestDecimalPrecision:
    """
    Tests for Decimal precision in financial calculations.
    
    These tests verify that the matching engine uses Decimal arithmetic
    to avoid floating-point precision errors that could accumulate
    during long-term backtests.
    
    **Validates: Requirements 7.7**
    """
    
    def test_no_floating_point_accumulation_error(self) -> None:
        """
        Test that repeated small trades don't accumulate floating-point errors.
        
        This test simulates a scenario where many small trades are executed,
        which would cause precision errors with float arithmetic but not with Decimal.
        
        Example: 0.1 + 0.2 != 0.3 in float, but Decimal("0.1") + Decimal("0.2") == Decimal("0.3")
        """
        config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=Decimal("0.0001"),  # 0.01% commission
            slippage_value=Decimal("0"),  # No slippage for precision test
            min_commission=Decimal("0"),
        )
        engine = MatchingEngine(config)
        
        # Create tick with precise prices
        tick = TickData(
            symbol="BTC_USDT",
            exchange="binance",
            datetime=datetime.now(),
            last_price=Decimal("0.1"),  # Small price to test precision
            volume=Decimal("1000000"),
            bid_price_1=Decimal("0.1"),
            bid_volume_1=Decimal("1000000"),
            ask_price_1=Decimal("0.1"),
            ask_volume_1=Decimal("1000000"),
        )
        
        # Execute 1000 trades with volume 0.1 each
        # With float: 0.1 * 1000 might not equal exactly 100.0
        # With Decimal: Decimal("0.1") * 1000 == Decimal("100.0") exactly
        num_trades = 1000
        trade_volume = Decimal("0.1")
        
        for i in range(num_trades):
            order = OrderData(
                order_id=f"order_{i}",
                symbol="BTC_USDT",
                exchange="binance",
                direction="LONG",
                offset="OPEN",
                price=Decimal("0"),  # Market order
                volume=trade_volume,
                traded=Decimal("0"),
                status="PENDING",
                is_manual=False,
                create_time=datetime.now(),
            )
            engine.submit_order(order)
            engine.process_tick(tick)
        
        # Verify total volume is exactly 100.0 (not 99.99999... or 100.00001...)
        trades = engine.get_trades()
        total_volume = sum(t.volume for t in trades)
        expected_volume = trade_volume * num_trades
        
        assert total_volume == expected_volume, \
            f"Total volume {total_volume} != expected {expected_volume} (precision error)"
        
        # Verify total turnover is exactly price * total_volume
        total_turnover = sum(t.turnover for t in trades)
        expected_turnover = Decimal("0.1") * expected_volume
        
        assert total_turnover == expected_turnover, \
            f"Total turnover {total_turnover} != expected {expected_turnover} (precision error)"
    
    def test_commission_precision_over_many_trades(self) -> None:
        """
        Test that commission calculations maintain precision over many trades.
        
        Commission = turnover * rate, and small rates like 0.0001 can cause
        precision issues with float arithmetic.
        """
        # Use a commission rate that causes float precision issues
        # 0.0001 * 10000 should equal exactly 1.0
        config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=Decimal("0.0001"),
            slippage_value=Decimal("0"),
            min_commission=Decimal("0"),
        )
        engine = MatchingEngine(config)
        
        tick = TickData(
            symbol="BTC_USDT",
            exchange="binance",
            datetime=datetime.now(),
            last_price=Decimal("1"),
            volume=Decimal("1000000"),
            bid_price_1=Decimal("1"),
            bid_volume_1=Decimal("1000000"),
            ask_price_1=Decimal("1"),
            ask_volume_1=Decimal("1000000"),
        )
        
        # Execute 100 trades with turnover 100 each
        # Total turnover = 10000, commission = 10000 * 0.0001 = 1.0 exactly
        num_trades = 100
        trade_volume = Decimal("100")
        
        for i in range(num_trades):
            order = OrderData(
                order_id=f"order_{i}",
                symbol="BTC_USDT",
                exchange="binance",
                direction="LONG",
                offset="OPEN",
                price=Decimal("0"),
                volume=trade_volume,
                traded=Decimal("0"),
                status="PENDING",
                is_manual=False,
                create_time=datetime.now(),
            )
            engine.submit_order(order)
            engine.process_tick(tick)
        
        # Verify total commission is exactly 1.0
        trades = engine.get_trades()
        total_commission = sum(t.commission for t in trades)
        expected_commission = Decimal("10000") * Decimal("0.0001")
        
        assert total_commission == expected_commission, \
            f"Total commission {total_commission} != expected {expected_commission}"
        
        # Also verify via metrics
        metrics = engine.get_quality_metrics()
        assert metrics.total_commission == expected_commission, \
            f"Metrics commission {metrics.total_commission} != expected {expected_commission}"
    
    def test_slippage_precision(self) -> None:
        """
        Test that slippage calculations maintain Decimal precision.
        """
        config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=Decimal("0"),
            slippage_model=SlippageModel.FIXED,
            slippage_value=Decimal("0.00001"),  # Very small slippage
            min_commission=Decimal("0"),
        )
        engine = MatchingEngine(config)
        
        # Price where small slippage matters
        tick = TickData(
            symbol="BTC_USDT",
            exchange="binance",
            datetime=datetime.now(),
            last_price=Decimal("50000"),
            volume=Decimal("100"),
            bid_price_1=Decimal("50000"),
            bid_volume_1=Decimal("100"),
            ask_price_1=Decimal("50000"),
            ask_volume_1=Decimal("100"),
        )
        
        order = OrderData(
            order_id="order_001",
            symbol="BTC_USDT",
            exchange="binance",
            direction="LONG",
            offset="OPEN",
            price=Decimal("0"),
            volume=Decimal("1"),
            traded=Decimal("0"),
            status="PENDING",
            is_manual=False,
            create_time=datetime.now(),
        )
        
        engine.submit_order(order)
        trades = engine.process_tick(tick)
        
        assert len(trades) == 1
        trade = trades[0]
        
        # Slippage should be exactly 50000 * 0.00001 = 0.5
        expected_slippage = Decimal("50000") * Decimal("0.00001")
        assert trade.slippage == expected_slippage, \
            f"Slippage {trade.slippage} != expected {expected_slippage}"
        
        # Final price should be ask + slippage = 50000 + 0.5 = 50000.5
        expected_price = Decimal("50000") + expected_slippage
        assert trade.price == expected_price, \
            f"Price {trade.price} != expected {expected_price}"
    
    def test_metrics_decimal_precision(self) -> None:
        """
        Test that MatchingQualityMetrics maintains Decimal precision.
        """
        config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=Decimal("0.0003"),
            slippage_value=Decimal("0.0001"),
        )
        engine = MatchingEngine(config)
        
        tick = TickData(
            symbol="BTC_USDT",
            exchange="binance",
            datetime=datetime.now(),
            last_price=Decimal("50000"),
            volume=Decimal("100"),
            bid_price_1=Decimal("50000"),
            bid_volume_1=Decimal("100"),
            ask_price_1=Decimal("50000"),
            ask_volume_1=Decimal("100"),
        )
        
        # Execute multiple trades
        for i in range(10):
            order = OrderData(
                order_id=f"order_{i}",
                symbol="BTC_USDT",
                exchange="binance",
                direction="LONG",
                offset="OPEN",
                price=Decimal("0"),
                volume=Decimal("1"),
                traded=Decimal("0"),
                status="PENDING",
                is_manual=False,
                create_time=datetime.now(),
            )
            engine.submit_order(order)
            engine.process_tick(tick)
        
        metrics = engine.get_quality_metrics()
        
        # Verify metrics are Decimal types
        assert isinstance(metrics.total_turnover, Decimal), \
            f"total_turnover should be Decimal, got {type(metrics.total_turnover)}"
        assert isinstance(metrics.total_commission, Decimal), \
            f"total_commission should be Decimal, got {type(metrics.total_commission)}"
        assert isinstance(metrics.avg_slippage, Decimal), \
            f"avg_slippage should be Decimal, got {type(metrics.avg_slippage)}"
        assert isinstance(metrics.max_slippage, Decimal), \
            f"max_slippage should be Decimal, got {type(metrics.max_slippage)}"
        assert isinstance(metrics.fill_rate, Decimal), \
            f"fill_rate should be Decimal, got {type(metrics.fill_rate)}"
    
    def test_config_decimal_serialization_roundtrip(self) -> None:
        """
        Test that MatchingConfig Decimal values survive serialization round-trip.
        """
        original_config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=Decimal("0.00033333"),  # Repeating decimal
            slippage_value=Decimal("0.00012345"),
            min_commission=Decimal("0.01"),
        )
        
        # Serialize and deserialize
        config_dict = original_config.to_dict()
        restored_config = MatchingConfig.from_dict(config_dict)
        
        # Verify values are preserved exactly
        assert restored_config.commission_rate == original_config.commission_rate, \
            f"commission_rate not preserved: {restored_config.commission_rate} != {original_config.commission_rate}"
        assert restored_config.slippage_value == original_config.slippage_value, \
            f"slippage_value not preserved: {restored_config.slippage_value} != {original_config.slippage_value}"
        assert restored_config.min_commission == original_config.min_commission, \
            f"min_commission not preserved: {restored_config.min_commission} != {original_config.min_commission}"
    
    def test_trade_record_decimal_serialization_roundtrip(self) -> None:
        """
        Test that TradeRecord Decimal values survive serialization round-trip.
        """
        original_trade = TradeRecord(
            trade_id="test_001",
            order_id="order_001",
            symbol="BTC_USDT",
            exchange="binance",
            direction="LONG",
            offset="OPEN",
            price=Decimal("50000.12345678"),
            volume=Decimal("0.00012345"),
            turnover=Decimal("6.17287654321"),
            commission=Decimal("0.00185186"),
            slippage=Decimal("0.00005"),
            matching_mode=MatchingMode.L1,
            l2_level=None,
            queue_wait_time=None,
            timestamp=datetime.now(),
            is_manual=False,
        )
        
        # Serialize and deserialize
        trade_dict = original_trade.to_dict()
        restored_trade = TradeRecord.from_dict(trade_dict)
        
        # Verify values are preserved exactly
        assert restored_trade.price == original_trade.price, \
            f"price not preserved: {restored_trade.price} != {original_trade.price}"
        assert restored_trade.volume == original_trade.volume, \
            f"volume not preserved: {restored_trade.volume} != {original_trade.volume}"
        assert restored_trade.turnover == original_trade.turnover, \
            f"turnover not preserved: {restored_trade.turnover} != {original_trade.turnover}"
        assert restored_trade.commission == original_trade.commission, \
            f"commission not preserved: {restored_trade.commission} != {original_trade.commission}"
        assert restored_trade.slippage == original_trade.slippage, \
            f"slippage not preserved: {restored_trade.slippage} != {original_trade.slippage}"
    
    @given(
        num_trades=st.integers(min_value=100, max_value=500),
        price=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100000"), places=8),
        volume=st.decimals(min_value=Decimal("0.00001"), max_value=Decimal("100"), places=8),
    )
    @settings(max_examples=50, deadline=10000)
    def test_long_backtest_no_precision_drift(
        self, num_trades: int, price: Decimal, volume: Decimal
    ) -> None:
        """
        Property: For any number of trades with any valid price/volume,
        the total turnover should equal sum of individual turnovers exactly.
        
        This property would fail with float arithmetic due to precision drift.
        
        Feature: titan-quant, Property: Decimal Precision No Drift
        **Validates: Requirements 7.7**
        """
        config = MatchingConfig(
            mode=MatchingMode.L1,
            commission_rate=Decimal("0"),
            slippage_value=Decimal("0"),
            min_commission=Decimal("0"),
        )
        engine = MatchingEngine(config)
        
        tick = TickData(
            symbol="BTC_USDT",
            exchange="binance",
            datetime=datetime.now(),
            last_price=price,
            volume=Decimal("1000000"),
            bid_price_1=price,
            bid_volume_1=Decimal("1000000"),
            ask_price_1=price,
            ask_volume_1=Decimal("1000000"),
        )
        
        for i in range(num_trades):
            order = OrderData(
                order_id=f"order_{i}",
                symbol="BTC_USDT",
                exchange="binance",
                direction="LONG",
                offset="OPEN",
                price=Decimal("0"),
                volume=volume,
                traded=Decimal("0"),
                status="PENDING",
                is_manual=False,
                create_time=datetime.now(),
            )
            engine.submit_order(order)
            engine.process_tick(tick)
        
        trades = engine.get_trades()
        
        # Calculate expected total turnover
        expected_total_turnover = price * volume * num_trades
        actual_total_turnover = sum(t.turnover for t in trades)
        
        # With Decimal, these should be exactly equal
        assert actual_total_turnover == expected_total_turnover, \
            f"Precision drift detected: {actual_total_turnover} != {expected_total_turnover}"
        
        # Also verify via metrics
        metrics = engine.get_quality_metrics()
        assert metrics.total_turnover == expected_total_turnover, \
            f"Metrics precision drift: {metrics.total_turnover} != {expected_total_turnover}"
