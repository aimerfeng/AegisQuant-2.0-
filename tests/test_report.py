"""
Property-Based Tests for Backtest Report Generator

This module contains property-based tests using Hypothesis to verify
the correctness properties of the Report Generator implementation.

Property 25: Report Metrics Completeness
    For any completed backtest, the generated report must contain all required
    metrics: sharpe_ratio, max_drawdown, total_return, win_rate, profit_factor,
    and total_trades.

Validates: Requirements 15.2
"""
import math
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import pytest
from hypothesis import given, settings, strategies as st, assume

from core.engine.matching import MatchingMode, TradeRecord
from core.report import (
    BacktestMetrics,
    BacktestReport,
    EquityPoint,
    MetricsCalculator,
    ReportGenerator,
)


# ==================== Hypothesis Strategies ====================

@st.composite
def trade_record_strategy(draw, symbol: str = "BTC_USDT"):
    """Generate a valid TradeRecord."""
    trade_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    
    direction = draw(st.sampled_from(["LONG", "SHORT"]))
    offset = draw(st.sampled_from(["OPEN", "CLOSE"]))
    
    price = Decimal(str(draw(st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False))))
    volume = Decimal(str(draw(st.floats(min_value=0.001, max_value=100.0, allow_nan=False, allow_infinity=False))))
    turnover = price * volume
    
    commission = turnover * Decimal("0.0003")
    slippage = Decimal(str(draw(st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False))))
    
    # Generate timestamp within a reasonable range
    base_time = datetime(2024, 1, 1)
    offset_seconds = draw(st.integers(min_value=0, max_value=365 * 24 * 3600))
    timestamp = base_time + timedelta(seconds=offset_seconds)
    
    return TradeRecord(
        trade_id=trade_id,
        order_id=order_id,
        symbol=symbol,
        exchange="binance",
        direction=direction,
        offset=offset,
        price=price,
        volume=volume,
        turnover=turnover,
        commission=commission,
        slippage=slippage,
        matching_mode=MatchingMode.L1,
        l2_level=None,
        queue_wait_time=None,
        timestamp=timestamp,
        is_manual=False,
    )


@st.composite
def equity_point_strategy(draw, base_time: datetime = None):
    """Generate a valid EquityPoint."""
    if base_time is None:
        base_time = datetime(2024, 1, 1)
    
    offset_seconds = draw(st.integers(min_value=0, max_value=365 * 24 * 3600))
    timestamp = base_time + timedelta(seconds=offset_seconds)
    
    equity = Decimal(str(draw(st.floats(min_value=100000.0, max_value=10000000.0, allow_nan=False, allow_infinity=False))))
    cash = Decimal(str(draw(st.floats(min_value=0.0, max_value=float(equity), allow_nan=False, allow_infinity=False))))
    position_value = equity - cash
    drawdown = Decimal(str(draw(st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False))))
    
    return EquityPoint(
        timestamp=timestamp,
        equity=equity,
        cash=cash,
        position_value=position_value,
        drawdown=drawdown,
    )


@st.composite
def equity_curve_strategy(draw, min_points: int = 2, max_points: int = 100):
    """Generate a valid equity curve (sorted by timestamp)."""
    num_points = draw(st.integers(min_value=min_points, max_value=max_points))
    
    base_time = datetime(2024, 1, 1)
    initial_equity = draw(st.floats(min_value=500000.0, max_value=2000000.0, allow_nan=False, allow_infinity=False))
    
    points = []
    current_equity = initial_equity
    peak_equity = initial_equity
    
    for i in range(num_points):
        timestamp = base_time + timedelta(days=i)
        
        # Random walk for equity
        change_pct = draw(st.floats(min_value=-0.05, max_value=0.05, allow_nan=False, allow_infinity=False))
        current_equity = current_equity * (1 + change_pct)
        current_equity = max(current_equity, 10000.0)  # Floor at 10k
        
        # Track peak and calculate drawdown
        if current_equity > peak_equity:
            peak_equity = current_equity
        
        drawdown = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0
        
        # Random cash/position split
        cash_ratio = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        cash = current_equity * cash_ratio
        position_value = current_equity - cash
        
        points.append(EquityPoint(
            timestamp=timestamp,
            equity=Decimal(str(current_equity)),
            cash=Decimal(str(cash)),
            position_value=Decimal(str(position_value)),
            drawdown=Decimal(str(drawdown)),
        ))
    
    return points


@st.composite
def trade_list_strategy(draw, min_trades: int = 0, max_trades: int = 50):
    """Generate a list of trades with proper OPEN/CLOSE pairing."""
    num_pairs = draw(st.integers(min_value=min_trades, max_value=max_trades))
    
    trades = []
    base_time = datetime(2024, 1, 1)
    
    for i in range(num_pairs):
        # Generate an OPEN trade
        direction = draw(st.sampled_from(["LONG", "SHORT"]))
        order_id = str(uuid.uuid4())
        
        open_price = Decimal(str(draw(st.floats(min_value=1000.0, max_value=50000.0, allow_nan=False, allow_infinity=False))))
        volume = Decimal(str(draw(st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False))))
        
        open_time = base_time + timedelta(hours=i * 2)
        close_time = open_time + timedelta(hours=1)
        
        # Price change for close
        price_change_pct = draw(st.floats(min_value=-0.1, max_value=0.1, allow_nan=False, allow_infinity=False))
        close_price = open_price * Decimal(str(1 + price_change_pct))
        
        # Create OPEN trade
        open_turnover = open_price * volume
        open_commission = open_turnover * Decimal("0.0003")
        
        open_trade = TradeRecord(
            trade_id=str(uuid.uuid4()),
            order_id=order_id,
            symbol="BTC_USDT",
            exchange="binance",
            direction=direction,
            offset="OPEN",
            price=open_price,
            volume=volume,
            turnover=open_turnover,
            commission=open_commission,
            slippage=Decimal("0"),
            matching_mode=MatchingMode.L1,
            l2_level=None,
            queue_wait_time=None,
            timestamp=open_time,
            is_manual=False,
        )
        trades.append(open_trade)
        
        # Create CLOSE trade
        close_turnover = close_price * volume
        close_commission = close_turnover * Decimal("0.0003")
        
        close_trade = TradeRecord(
            trade_id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            symbol="BTC_USDT",
            exchange="binance",
            direction=direction,
            offset="CLOSE",
            price=close_price,
            volume=volume,
            turnover=close_turnover,
            commission=close_commission,
            slippage=Decimal("0"),
            matching_mode=MatchingMode.L1,
            l2_level=None,
            queue_wait_time=None,
            timestamp=close_time,
            is_manual=False,
        )
        trades.append(close_trade)
    
    return trades



# ==================== Test Classes ====================

class TestReportMetricsCompleteness:
    """
    Property 25: Report Metrics Completeness
    
    *For any* completed backtest, the generated report must contain all required
    metrics: sharpe_ratio, max_drawdown, total_return, win_rate, profit_factor,
    and total_trades.
    
    **Validates: Requirements 15.2**
    """
    
    @given(
        trades=trade_list_strategy(min_trades=0, max_trades=20),
        equity_curve=equity_curve_strategy(min_points=5, max_points=50),
    )
    @settings(max_examples=100, deadline=30000)
    def test_property_report_metrics_completeness(
        self,
        trades: List[TradeRecord],
        equity_curve: List[EquityPoint],
    ) -> None:
        """
        Property: All generated reports must contain all required metrics.
        
        Feature: titan-quant, Property 25: Report Metrics Completeness
        **Validates: Requirements 15.2**
        """
        # Generate report
        generator = ReportGenerator(initial_capital=1_000_000.0)
        report = generator.generate_report(
            backtest_id=str(uuid.uuid4()),
            strategy_name="TestStrategy",
            trades=trades,
            equity_curve=equity_curve,
        )
        
        # Verify all required metrics are present
        metrics = report.metrics
        
        # Check required metrics exist and are valid numbers
        assert metrics.sharpe_ratio is not None, "sharpe_ratio is missing"
        assert not math.isnan(metrics.sharpe_ratio), "sharpe_ratio is NaN"
        
        assert metrics.max_drawdown is not None, "max_drawdown is missing"
        assert not math.isnan(metrics.max_drawdown), "max_drawdown is NaN"
        assert metrics.max_drawdown >= 0, "max_drawdown must be non-negative"
        
        assert metrics.total_return is not None, "total_return is missing"
        assert not math.isnan(metrics.total_return), "total_return is NaN"
        
        assert metrics.win_rate is not None, "win_rate is missing"
        assert not math.isnan(metrics.win_rate), "win_rate is NaN"
        assert 0 <= metrics.win_rate <= 1, "win_rate must be between 0 and 1"
        
        assert metrics.profit_factor is not None, "profit_factor is missing"
        assert not math.isnan(metrics.profit_factor), "profit_factor is NaN"
        assert metrics.profit_factor >= 0, "profit_factor must be non-negative"
        
        assert metrics.total_trades is not None, "total_trades is missing"
        assert metrics.total_trades >= 0, "total_trades must be non-negative"
        
        # Verify has_required_metrics returns True
        assert metrics.has_required_metrics(), "has_required_metrics() should return True"
    
    def test_empty_backtest_has_required_metrics(self) -> None:
        """Test that even empty backtests have all required metrics."""
        generator = ReportGenerator(initial_capital=1_000_000.0)
        report = generator.generate_report(
            backtest_id=str(uuid.uuid4()),
            strategy_name="EmptyStrategy",
            trades=[],
            equity_curve=[],
        )
        
        metrics = report.metrics
        
        # All required metrics should be present (with default values)
        assert metrics.has_required_metrics()
        assert metrics.sharpe_ratio == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.total_return == 0.0
        assert metrics.win_rate == 0.0
        assert metrics.profit_factor == 0.0
        assert metrics.total_trades == 0
    
    def test_get_required_metrics_returns_all_required(self) -> None:
        """Test that get_required_metrics returns exactly the required fields."""
        metrics = BacktestMetrics(
            sharpe_ratio=1.5,
            max_drawdown=0.15,
            total_return=0.25,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=100,
        )
        
        required = metrics.get_required_metrics()
        
        assert "sharpe_ratio" in required
        assert "max_drawdown" in required
        assert "total_return" in required
        assert "win_rate" in required
        assert "profit_factor" in required
        assert "total_trades" in required
        
        assert required["sharpe_ratio"] == 1.5
        assert required["max_drawdown"] == 0.15
        assert required["total_return"] == 0.25
        assert required["win_rate"] == 0.6
        assert required["profit_factor"] == 2.0
        assert required["total_trades"] == 100


class TestMetricsCalculator:
    """Unit tests for MetricsCalculator."""
    
    def test_sharpe_ratio_calculation(self) -> None:
        """Test Sharpe ratio calculation."""
        calculator = MetricsCalculator(initial_capital=1_000_000.0)
        
        # Create equity curve with positive returns
        base_time = datetime(2024, 1, 1)
        equity_curve = []
        equity = 1_000_000.0
        
        for i in range(252):  # One year of daily data
            equity *= 1.001  # 0.1% daily return
            equity_curve.append(EquityPoint(
                timestamp=base_time + timedelta(days=i),
                equity=Decimal(str(equity)),
                cash=Decimal(str(equity * 0.5)),
                position_value=Decimal(str(equity * 0.5)),
                drawdown=Decimal("0"),
            ))
        
        metrics = calculator.calculate_metrics([], equity_curve)
        
        # Sharpe should be positive for positive returns
        assert metrics.sharpe_ratio > 0
    
    def test_max_drawdown_calculation(self) -> None:
        """Test max drawdown calculation."""
        calculator = MetricsCalculator(initial_capital=1_000_000.0)
        
        # Create equity curve with known drawdown
        base_time = datetime(2024, 1, 1)
        equity_values = [1_000_000, 1_100_000, 1_050_000, 900_000, 950_000]  # 18.18% drawdown from peak
        
        equity_curve = []
        peak = equity_values[0]
        
        for i, equity in enumerate(equity_values):
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            
            equity_curve.append(EquityPoint(
                timestamp=base_time + timedelta(days=i),
                equity=Decimal(str(equity)),
                cash=Decimal(str(equity * 0.5)),
                position_value=Decimal(str(equity * 0.5)),
                drawdown=Decimal(str(drawdown)),
            ))
        
        metrics = calculator.calculate_metrics([], equity_curve)
        
        # Max drawdown should be approximately 18.18% (from 1.1M to 0.9M)
        expected_dd = (1_100_000 - 900_000) / 1_100_000
        assert abs(metrics.max_drawdown - expected_dd) < 0.01
    
    def test_win_rate_calculation(self) -> None:
        """Test win rate calculation."""
        calculator = MetricsCalculator(initial_capital=1_000_000.0)
        
        # Create trades with known win rate (2 wins, 1 loss = 66.67%)
        base_time = datetime(2024, 1, 1)
        trades = []
        
        # Winning trade 1
        trades.append(TradeRecord(
            trade_id="1", order_id="o1", symbol="BTC", exchange="binance",
            direction="LONG", offset="OPEN", price=Decimal("100"),
            volume=Decimal("1"), turnover=Decimal("100"),
            commission=Decimal("0.03"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time,
        ))
        trades.append(TradeRecord(
            trade_id="2", order_id="o2", symbol="BTC", exchange="binance",
            direction="LONG", offset="CLOSE", price=Decimal("110"),  # +10 profit
            volume=Decimal("1"), turnover=Decimal("110"),
            commission=Decimal("0.033"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time + timedelta(hours=1),
        ))
        
        # Winning trade 2
        trades.append(TradeRecord(
            trade_id="3", order_id="o3", symbol="BTC", exchange="binance",
            direction="LONG", offset="OPEN", price=Decimal("100"),
            volume=Decimal("1"), turnover=Decimal("100"),
            commission=Decimal("0.03"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time + timedelta(hours=2),
        ))
        trades.append(TradeRecord(
            trade_id="4", order_id="o4", symbol="BTC", exchange="binance",
            direction="LONG", offset="CLOSE", price=Decimal("105"),  # +5 profit
            volume=Decimal("1"), turnover=Decimal("105"),
            commission=Decimal("0.0315"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time + timedelta(hours=3),
        ))
        
        # Losing trade
        trades.append(TradeRecord(
            trade_id="5", order_id="o5", symbol="BTC", exchange="binance",
            direction="LONG", offset="OPEN", price=Decimal("100"),
            volume=Decimal("1"), turnover=Decimal("100"),
            commission=Decimal("0.03"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time + timedelta(hours=4),
        ))
        trades.append(TradeRecord(
            trade_id="6", order_id="o6", symbol="BTC", exchange="binance",
            direction="LONG", offset="CLOSE", price=Decimal("90"),  # -10 loss
            volume=Decimal("1"), turnover=Decimal("90"),
            commission=Decimal("0.027"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time + timedelta(hours=5),
        ))
        
        metrics = calculator.calculate_metrics(trades, [])
        
        # Win rate should be 2/3 = 0.6667
        assert abs(metrics.win_rate - 0.6667) < 0.01
        assert metrics.total_trades == 3
    
    def test_profit_factor_calculation(self) -> None:
        """Test profit factor calculation."""
        calculator = MetricsCalculator(initial_capital=1_000_000.0)
        
        base_time = datetime(2024, 1, 1)
        trades = []
        
        # Winning trade: +20 profit
        trades.append(TradeRecord(
            trade_id="1", order_id="o1", symbol="BTC", exchange="binance",
            direction="LONG", offset="OPEN", price=Decimal("100"),
            volume=Decimal("1"), turnover=Decimal("100"),
            commission=Decimal("0"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time,
        ))
        trades.append(TradeRecord(
            trade_id="2", order_id="o2", symbol="BTC", exchange="binance",
            direction="LONG", offset="CLOSE", price=Decimal("120"),
            volume=Decimal("1"), turnover=Decimal("120"),
            commission=Decimal("0"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time + timedelta(hours=1),
        ))
        
        # Losing trade: -10 loss
        trades.append(TradeRecord(
            trade_id="3", order_id="o3", symbol="BTC", exchange="binance",
            direction="LONG", offset="OPEN", price=Decimal("100"),
            volume=Decimal("1"), turnover=Decimal("100"),
            commission=Decimal("0"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time + timedelta(hours=2),
        ))
        trades.append(TradeRecord(
            trade_id="4", order_id="o4", symbol="BTC", exchange="binance",
            direction="LONG", offset="CLOSE", price=Decimal("90"),
            volume=Decimal("1"), turnover=Decimal("90"),
            commission=Decimal("0"), slippage=Decimal("0"),
            matching_mode=MatchingMode.L1, l2_level=None,
            queue_wait_time=None, timestamp=base_time + timedelta(hours=3),
        ))
        
        metrics = calculator.calculate_metrics(trades, [])
        
        # Profit factor = 20 / 10 = 2.0
        assert abs(metrics.profit_factor - 2.0) < 0.01


class TestReportGenerator:
    """Unit tests for ReportGenerator."""
    
    def test_generate_report_creates_valid_report(self) -> None:
        """Test that generate_report creates a valid BacktestReport."""
        generator = ReportGenerator(initial_capital=1_000_000.0)
        
        report = generator.generate_report(
            backtest_id="test-123",
            strategy_name="TestStrategy",
            trades=[],
            equity_curve=[],
        )
        
        assert report.report_id is not None
        assert report.backtest_id == "test-123"
        assert report.strategy_name == "TestStrategy"
        assert report.metrics is not None
        assert report.created_at is not None
    
    def test_save_report_creates_files(self) -> None:
        """Test that save_report creates all expected files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ReportGenerator(reports_dir=tmpdir, initial_capital=1_000_000.0)
            
            # Create a simple equity curve
            base_time = datetime(2024, 1, 1)
            equity_curve = [
                EquityPoint(
                    timestamp=base_time + timedelta(days=i),
                    equity=Decimal(str(1_000_000 + i * 1000)),
                    cash=Decimal("500000"),
                    position_value=Decimal(str(500000 + i * 1000)),
                    drawdown=Decimal("0"),
                )
                for i in range(10)
            ]
            
            report = generator.generate_report(
                backtest_id="test-save",
                strategy_name="SaveTest",
                trades=[],
                equity_curve=equity_curve,
            )
            
            report_path = generator.save_report(report)
            
            # Check files exist
            assert os.path.exists(os.path.join(report_path, "report.html"))
            assert os.path.exists(os.path.join(report_path, "trades.csv"))
            assert os.path.exists(os.path.join(report_path, "metrics.json"))
    
    def test_trades_csv_contains_all_trades(self) -> None:
        """Test that trades.csv contains all trade records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ReportGenerator(reports_dir=tmpdir, initial_capital=1_000_000.0)
            
            base_time = datetime(2024, 1, 1)
            trades = [
                TradeRecord(
                    trade_id=f"t{i}", order_id=f"o{i}", symbol="BTC",
                    exchange="binance", direction="LONG", offset="OPEN",
                    price=Decimal("100"), volume=Decimal("1"),
                    turnover=Decimal("100"), commission=Decimal("0.03"),
                    slippage=Decimal("0"), matching_mode=MatchingMode.L1,
                    l2_level=None, queue_wait_time=None,
                    timestamp=base_time + timedelta(hours=i),
                )
                for i in range(5)
            ]
            
            report = generator.generate_report(
                backtest_id="test-csv",
                strategy_name="CSVTest",
                trades=trades,
                equity_curve=[],
            )
            
            report_path = generator.save_report(report)
            
            # Read CSV and count rows
            csv_path = os.path.join(report_path, "trades.csv")
            with open(csv_path, "r") as f:
                lines = f.readlines()
            
            # Should have header + 5 trades
            assert len(lines) == 6


class TestBacktestMetrics:
    """Unit tests for BacktestMetrics dataclass."""
    
    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        """Test serialization roundtrip."""
        original = BacktestMetrics(
            sharpe_ratio=1.5,
            max_drawdown=0.15,
            total_return=0.25,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=100,
            annualized_return=0.30,
            volatility=0.20,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=1_000_000.0,
            final_equity=1_250_000.0,
        )
        
        data = original.to_dict()
        restored = BacktestMetrics.from_dict(data)
        
        assert restored.sharpe_ratio == original.sharpe_ratio
        assert restored.max_drawdown == original.max_drawdown
        assert restored.total_return == original.total_return
        assert restored.win_rate == original.win_rate
        assert restored.profit_factor == original.profit_factor
        assert restored.total_trades == original.total_trades
        assert restored.start_date == original.start_date
        assert restored.end_date == original.end_date
    
    def test_has_required_metrics_with_nan(self) -> None:
        """Test that NaN values are detected as invalid."""
        metrics = BacktestMetrics(
            sharpe_ratio=float('nan'),
            max_drawdown=0.15,
            total_return=0.25,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=100,
        )
        
        assert not metrics.has_required_metrics()
    
    def test_has_required_metrics_with_negative_trades(self) -> None:
        """Test that negative total_trades is invalid."""
        metrics = BacktestMetrics(
            sharpe_ratio=1.5,
            max_drawdown=0.15,
            total_return=0.25,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=-1,
        )
        
        assert not metrics.has_required_metrics()


class TestEquityPoint:
    """Unit tests for EquityPoint dataclass."""
    
    def test_to_dict(self) -> None:
        """Test EquityPoint serialization."""
        point = EquityPoint(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            equity=Decimal("1000000"),
            cash=Decimal("500000"),
            position_value=Decimal("500000"),
            drawdown=Decimal("0.05"),
        )
        
        data = point.to_dict()
        
        assert data["timestamp"] == "2024-01-01T12:00:00"
        assert data["equity"] == "1000000"
        assert data["cash"] == "500000"
        assert data["position_value"] == "500000"
        assert data["drawdown"] == "0.05"
