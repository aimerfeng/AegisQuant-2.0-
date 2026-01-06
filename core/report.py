"""
Titan-Quant Backtest Report Generator

This module implements the backtest report generation functionality,
including metrics calculation and HTML report generation.

Requirements:
    - 15.1: WHEN 回测结束, THEN THE Titan_Quant_System SHALL 自动生成交互式 HTML 报告
    - 15.2: THE 报告 SHALL 包含夏普比率、最大回撤、总收益等关键指标
    - 15.3: THE 报告 SHALL 包含资金曲线图和逐笔成交单（trades.csv）
    - 15.4: THE Titan_Quant_System SHALL 将报告保存到 reports/ 目录，按实验编号分类

Property 25: Report Metrics Completeness
    For any completed backtest, the generated report must contain all required
    metrics: sharpe_ratio, max_drawdown, total_return, win_rate, profit_factor,
    and total_trades.
"""
from __future__ import annotations

import csv
import json
import math
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.engine.matching import TradeRecord
from core.engine.types import to_decimal


# ==================== Data Classes ====================

@dataclass
class EquityPoint:
    """
    A single point on the equity curve.
    
    Attributes:
        timestamp: The timestamp of this equity point
        equity: Total equity value at this point
        cash: Cash balance
        position_value: Value of open positions
        drawdown: Current drawdown from peak (as decimal, e.g., 0.05 = 5%)
    """
    timestamp: datetime
    equity: Decimal
    cash: Decimal
    position_value: Decimal
    drawdown: Decimal = field(default_factory=lambda: Decimal("0"))
    
    def __post_init__(self) -> None:
        """Convert values to Decimal if needed."""
        self.equity = to_decimal(self.equity)
        self.cash = to_decimal(self.cash)
        self.position_value = to_decimal(self.position_value)
        self.drawdown = to_decimal(self.drawdown)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": str(self.equity),
            "cash": str(self.cash),
            "position_value": str(self.position_value),
            "drawdown": str(self.drawdown),
        }


@dataclass
class BacktestMetrics:
    """
    Complete backtest performance metrics.
    
    This dataclass contains all required metrics as specified in Requirements 15.2.
    
    Attributes:
        sharpe_ratio: Risk-adjusted return (annualized)
        max_drawdown: Maximum peak-to-trough decline (as decimal)
        total_return: Total return over the backtest period (as decimal)
        win_rate: Percentage of winning trades (as decimal)
        profit_factor: Gross profit / Gross loss
        total_trades: Total number of completed trades
        
        Additional metrics:
        annualized_return: Annualized return
        volatility: Annualized volatility of returns
        calmar_ratio: Annualized return / Max drawdown
        sortino_ratio: Return / Downside deviation
        avg_win: Average winning trade profit
        avg_loss: Average losing trade loss
        max_win: Largest winning trade
        max_loss: Largest losing trade
        avg_trade_duration: Average trade duration in seconds
        total_commission: Total commission paid
        net_profit: Net profit after commissions
        gross_profit: Total profit from winning trades
        gross_loss: Total loss from losing trades
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital
        final_equity: Ending equity
    """
    # Required metrics (Property 25)
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    win_rate: float
    profit_factor: float
    total_trades: int
    
    # Additional metrics
    annualized_return: float = 0.0
    volatility: float = 0.0
    calmar_ratio: float = 0.0
    sortino_ratio: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    avg_trade_duration: float = 0.0
    total_commission: float = 0.0
    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    winning_trades: int = 0
    losing_trades: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_capital: float = 0.0
    final_equity: float = 0.0
    
    def has_required_metrics(self) -> bool:
        """
        Check if all required metrics are present and valid.
        
        Property 25: Report Metrics Completeness
        """
        # Check that required metrics are not None/NaN
        required = [
            self.sharpe_ratio,
            self.max_drawdown,
            self.total_return,
            self.win_rate,
            self.profit_factor,
        ]
        
        for metric in required:
            if metric is None or (isinstance(metric, float) and math.isnan(metric)):
                return False
        
        # total_trades must be non-negative
        if self.total_trades < 0:
            return False
        
        return True
    
    def get_required_metrics(self) -> Dict[str, Any]:
        """Get only the required metrics as a dictionary."""
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert all metrics to dictionary."""
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "annualized_return": self.annualized_return,
            "volatility": self.volatility,
            "calmar_ratio": self.calmar_ratio,
            "sortino_ratio": self.sortino_ratio,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "max_win": self.max_win,
            "max_loss": self.max_loss,
            "avg_trade_duration": self.avg_trade_duration,
            "total_commission": self.total_commission,
            "net_profit": self.net_profit,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_capital": self.initial_capital,
            "final_equity": self.final_equity,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BacktestMetrics:
        """Create BacktestMetrics from dictionary."""
        start_date = None
        end_date = None
        if data.get("start_date"):
            start_date = datetime.fromisoformat(data["start_date"])
        if data.get("end_date"):
            end_date = datetime.fromisoformat(data["end_date"])
        
        return cls(
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            total_return=data.get("total_return", 0.0),
            win_rate=data.get("win_rate", 0.0),
            profit_factor=data.get("profit_factor", 0.0),
            total_trades=data.get("total_trades", 0),
            annualized_return=data.get("annualized_return", 0.0),
            volatility=data.get("volatility", 0.0),
            calmar_ratio=data.get("calmar_ratio", 0.0),
            sortino_ratio=data.get("sortino_ratio", 0.0),
            avg_win=data.get("avg_win", 0.0),
            avg_loss=data.get("avg_loss", 0.0),
            max_win=data.get("max_win", 0.0),
            max_loss=data.get("max_loss", 0.0),
            avg_trade_duration=data.get("avg_trade_duration", 0.0),
            total_commission=data.get("total_commission", 0.0),
            net_profit=data.get("net_profit", 0.0),
            gross_profit=data.get("gross_profit", 0.0),
            gross_loss=data.get("gross_loss", 0.0),
            winning_trades=data.get("winning_trades", 0),
            losing_trades=data.get("losing_trades", 0),
            start_date=start_date,
            end_date=end_date,
            initial_capital=data.get("initial_capital", 0.0),
            final_equity=data.get("final_equity", 0.0),
        )



@dataclass
class BacktestReport:
    """
    Complete backtest report containing metrics, trades, and equity curve.
    
    Attributes:
        report_id: Unique report identifier
        backtest_id: Associated backtest identifier
        strategy_name: Name of the strategy
        metrics: Calculated performance metrics
        trades: List of all trade records
        equity_curve: List of equity points over time
        created_at: Report creation timestamp
        matching_mode: Matching mode used (L1/L2)
        l2_level: L2 simulation level if applicable
    """
    report_id: str
    backtest_id: str
    strategy_name: str
    metrics: BacktestMetrics
    trades: List[TradeRecord]
    equity_curve: List[EquityPoint]
    created_at: datetime
    matching_mode: str = "L1"
    l2_level: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "report_id": self.report_id,
            "backtest_id": self.backtest_id,
            "strategy_name": self.strategy_name,
            "metrics": self.metrics.to_dict(),
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": [e.to_dict() for e in self.equity_curve],
            "created_at": self.created_at.isoformat(),
            "matching_mode": self.matching_mode,
            "l2_level": self.l2_level,
        }


# ==================== Metrics Calculator ====================

class MetricsCalculator:
    """
    Calculator for backtest performance metrics.
    
    This class computes all required metrics from trade records and equity curve.
    """
    
    # Risk-free rate for Sharpe ratio calculation (annualized)
    RISK_FREE_RATE = 0.02  # 2% annual risk-free rate
    
    # Trading days per year for annualization
    TRADING_DAYS_PER_YEAR = 252
    
    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        risk_free_rate: float = 0.02,
    ) -> None:
        """
        Initialize the metrics calculator.
        
        Args:
            initial_capital: Starting capital for the backtest
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate
    
    def calculate_metrics(
        self,
        trades: List[TradeRecord],
        equity_curve: List[EquityPoint],
    ) -> BacktestMetrics:
        """
        Calculate all backtest metrics from trades and equity curve.
        
        Args:
            trades: List of executed trades
            equity_curve: List of equity points over time
            
        Returns:
            BacktestMetrics with all calculated values
        """
        # Handle empty data
        if not trades and not equity_curve:
            return self._empty_metrics()
        
        # Calculate trade-based metrics
        trade_metrics = self._calculate_trade_metrics(trades)
        
        # Calculate equity-based metrics
        equity_metrics = self._calculate_equity_metrics(equity_curve)
        
        # Combine all metrics
        return BacktestMetrics(
            # Required metrics
            sharpe_ratio=equity_metrics.get("sharpe_ratio", 0.0),
            max_drawdown=equity_metrics.get("max_drawdown", 0.0),
            total_return=equity_metrics.get("total_return", 0.0),
            win_rate=trade_metrics.get("win_rate", 0.0),
            profit_factor=trade_metrics.get("profit_factor", 0.0),
            total_trades=trade_metrics.get("total_trades", 0),
            
            # Additional metrics
            annualized_return=equity_metrics.get("annualized_return", 0.0),
            volatility=equity_metrics.get("volatility", 0.0),
            calmar_ratio=equity_metrics.get("calmar_ratio", 0.0),
            sortino_ratio=equity_metrics.get("sortino_ratio", 0.0),
            avg_win=trade_metrics.get("avg_win", 0.0),
            avg_loss=trade_metrics.get("avg_loss", 0.0),
            max_win=trade_metrics.get("max_win", 0.0),
            max_loss=trade_metrics.get("max_loss", 0.0),
            avg_trade_duration=trade_metrics.get("avg_trade_duration", 0.0),
            total_commission=trade_metrics.get("total_commission", 0.0),
            net_profit=trade_metrics.get("net_profit", 0.0),
            gross_profit=trade_metrics.get("gross_profit", 0.0),
            gross_loss=trade_metrics.get("gross_loss", 0.0),
            winning_trades=trade_metrics.get("winning_trades", 0),
            losing_trades=trade_metrics.get("losing_trades", 0),
            start_date=equity_metrics.get("start_date"),
            end_date=equity_metrics.get("end_date"),
            initial_capital=self.initial_capital,
            final_equity=equity_metrics.get("final_equity", self.initial_capital),
        )
    
    def _empty_metrics(self) -> BacktestMetrics:
        """Return metrics for empty backtest (no trades)."""
        return BacktestMetrics(
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            total_return=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            total_trades=0,
            initial_capital=self.initial_capital,
            final_equity=self.initial_capital,
        )
    
    def _calculate_trade_metrics(
        self,
        trades: List[TradeRecord],
    ) -> Dict[str, Any]:
        """Calculate metrics based on trade records."""
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
                "total_commission": 0.0,
                "net_profit": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "winning_trades": 0,
                "losing_trades": 0,
                "avg_trade_duration": 0.0,
            }
        
        # Group trades by order to calculate P&L per round-trip
        pnl_list = self._calculate_trade_pnl(trades)
        
        # Separate winning and losing trades
        winning_pnl = [p for p in pnl_list if p > 0]
        losing_pnl = [p for p in pnl_list if p < 0]
        
        # Calculate metrics
        total_trades = len(pnl_list)
        winning_trades = len(winning_pnl)
        losing_trades = len(losing_pnl)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        gross_profit = sum(winning_pnl) if winning_pnl else 0.0
        gross_loss = abs(sum(losing_pnl)) if losing_pnl else 0.0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
        # Cap profit factor at a reasonable value for display
        if profit_factor == float('inf'):
            profit_factor = 999.99
        
        avg_win = sum(winning_pnl) / len(winning_pnl) if winning_pnl else 0.0
        avg_loss = sum(losing_pnl) / len(losing_pnl) if losing_pnl else 0.0
        
        max_win = max(winning_pnl) if winning_pnl else 0.0
        max_loss = min(losing_pnl) if losing_pnl else 0.0
        
        total_commission = sum(float(t.commission) for t in trades)
        net_profit = sum(pnl_list)
        
        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_win": max_win,
            "max_loss": max_loss,
            "total_commission": total_commission,
            "net_profit": net_profit,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "avg_trade_duration": 0.0,  # Would need entry/exit timestamps
        }
    
    def _calculate_trade_pnl(self, trades: List[TradeRecord]) -> List[float]:
        """
        Calculate P&L for each completed trade (round-trip).
        
        This groups OPEN and CLOSE trades to calculate realized P&L.
        """
        # Track open positions by symbol
        positions: Dict[str, List[Tuple[str, Decimal, Decimal]]] = {}  # symbol -> [(direction, price, volume)]
        pnl_list: List[float] = []
        
        for trade in sorted(trades, key=lambda t: t.timestamp):
            symbol = trade.symbol
            
            if trade.offset == "OPEN":
                # Opening a new position
                if symbol not in positions:
                    positions[symbol] = []
                positions[symbol].append((trade.direction, trade.price, trade.volume))
            
            elif trade.offset == "CLOSE":
                # Closing a position - calculate P&L
                if symbol in positions and positions[symbol]:
                    # FIFO matching
                    remaining_volume = trade.volume
                    
                    while remaining_volume > 0 and positions[symbol]:
                        open_dir, open_price, open_vol = positions[symbol][0]
                        
                        close_vol = min(remaining_volume, open_vol)
                        
                        # Calculate P&L based on direction
                        if open_dir == "LONG":
                            pnl = float((trade.price - open_price) * close_vol)
                        else:  # SHORT
                            pnl = float((open_price - trade.price) * close_vol)
                        
                        # Subtract commission
                        pnl -= float(trade.commission) * float(close_vol / trade.volume)
                        
                        pnl_list.append(pnl)
                        
                        remaining_volume -= close_vol
                        
                        if close_vol >= open_vol:
                            positions[symbol].pop(0)
                        else:
                            positions[symbol][0] = (open_dir, open_price, open_vol - close_vol)
        
        return pnl_list
    
    def _calculate_equity_metrics(
        self,
        equity_curve: List[EquityPoint],
    ) -> Dict[str, Any]:
        """Calculate metrics based on equity curve."""
        if not equity_curve:
            return {
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "total_return": 0.0,
                "annualized_return": 0.0,
                "volatility": 0.0,
                "calmar_ratio": 0.0,
                "sortino_ratio": 0.0,
                "start_date": None,
                "end_date": None,
                "final_equity": self.initial_capital,
            }
        
        # Sort by timestamp
        sorted_curve = sorted(equity_curve, key=lambda e: e.timestamp)
        
        # Extract equity values
        equities = [float(e.equity) for e in sorted_curve]
        
        # Calculate returns
        returns = self._calculate_returns(equities)
        
        # Basic metrics
        start_date = sorted_curve[0].timestamp
        end_date = sorted_curve[-1].timestamp
        final_equity = equities[-1]
        
        total_return = (final_equity - self.initial_capital) / self.initial_capital
        
        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(equities)
        
        # Calculate annualized metrics
        days = (end_date - start_date).days
        years = days / 365.0 if days > 0 else 1.0
        
        annualized_return = ((1 + total_return) ** (1 / years) - 1) if years > 0 else total_return
        
        # Calculate volatility (annualized)
        volatility = self._calculate_volatility(returns)
        
        # Calculate Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio(returns, annualized_return)
        
        # Calculate Sortino ratio
        sortino_ratio = self._calculate_sortino_ratio(returns, annualized_return)
        
        # Calculate Calmar ratio
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0.0
        
        return {
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "total_return": total_return,
            "annualized_return": annualized_return,
            "volatility": volatility,
            "calmar_ratio": calmar_ratio,
            "sortino_ratio": sortino_ratio,
            "start_date": start_date,
            "end_date": end_date,
            "final_equity": final_equity,
        }
    
    def _calculate_returns(self, equities: List[float]) -> List[float]:
        """Calculate period returns from equity values."""
        if len(equities) < 2:
            return []
        
        returns = []
        for i in range(1, len(equities)):
            if equities[i - 1] > 0:
                ret = (equities[i] - equities[i - 1]) / equities[i - 1]
                returns.append(ret)
        
        return returns
    
    def _calculate_max_drawdown(self, equities: List[float]) -> float:
        """Calculate maximum drawdown from equity curve."""
        if not equities:
            return 0.0
        
        peak = equities[0]
        max_dd = 0.0
        
        for equity in equities:
            if equity > peak:
                peak = equity
            
            drawdown = (peak - equity) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate annualized volatility from returns."""
        if len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        
        # Annualize
        return daily_vol * math.sqrt(self.TRADING_DAYS_PER_YEAR)
    
    def _calculate_sharpe_ratio(
        self,
        returns: List[float],
        annualized_return: float,
    ) -> float:
        """Calculate Sharpe ratio."""
        if not returns:
            return 0.0
        
        volatility = self._calculate_volatility(returns)
        
        if volatility == 0:
            return 0.0
        
        excess_return = annualized_return - self.risk_free_rate
        return excess_return / volatility
    
    def _calculate_sortino_ratio(
        self,
        returns: List[float],
        annualized_return: float,
    ) -> float:
        """Calculate Sortino ratio (using downside deviation)."""
        if not returns:
            return 0.0
        
        # Calculate downside deviation (only negative returns)
        negative_returns = [r for r in returns if r < 0]
        
        if not negative_returns:
            return 0.0 if annualized_return <= self.risk_free_rate else float('inf')
        
        downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
        downside_deviation = math.sqrt(downside_variance) * math.sqrt(self.TRADING_DAYS_PER_YEAR)
        
        if downside_deviation == 0:
            return 0.0
        
        excess_return = annualized_return - self.risk_free_rate
        return excess_return / downside_deviation



# ==================== Report Generator ====================

class ReportGenerator:
    """
    Generator for backtest reports including HTML and CSV exports.
    
    Requirements:
        - 15.1: Generate interactive HTML report
        - 15.3: Include equity curve chart and trades.csv
        - 15.4: Save to reports/ directory by experiment ID
    """
    
    DEFAULT_REPORTS_DIR = "reports"
    
    def __init__(
        self,
        reports_dir: str = DEFAULT_REPORTS_DIR,
        initial_capital: float = 1_000_000.0,
    ) -> None:
        """
        Initialize the report generator.
        
        Args:
            reports_dir: Directory to save reports
            initial_capital: Starting capital for metrics calculation
        """
        self.reports_dir = Path(reports_dir)
        self.initial_capital = initial_capital
        self.metrics_calculator = MetricsCalculator(initial_capital=initial_capital)
    
    def generate_report(
        self,
        backtest_id: str,
        strategy_name: str,
        trades: List[TradeRecord],
        equity_curve: List[EquityPoint],
        matching_mode: str = "L1",
        l2_level: Optional[str] = None,
    ) -> BacktestReport:
        """
        Generate a complete backtest report.
        
        Args:
            backtest_id: Unique backtest identifier
            strategy_name: Name of the strategy
            trades: List of executed trades
            equity_curve: List of equity points
            matching_mode: Matching mode used
            l2_level: L2 simulation level if applicable
            
        Returns:
            BacktestReport with all data and metrics
        """
        # Calculate metrics
        metrics = self.metrics_calculator.calculate_metrics(trades, equity_curve)
        
        # Create report
        report = BacktestReport(
            report_id=str(uuid.uuid4()),
            backtest_id=backtest_id,
            strategy_name=strategy_name,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            created_at=datetime.now(),
            matching_mode=matching_mode,
            l2_level=l2_level,
        )
        
        return report
    
    def save_report(
        self,
        report: BacktestReport,
        generate_html: bool = True,
        generate_csv: bool = True,
        generate_json: bool = True,
    ) -> str:
        """
        Save report to disk.
        
        Args:
            report: The report to save
            generate_html: Whether to generate HTML report
            generate_csv: Whether to generate trades.csv
            generate_json: Whether to generate metrics.json
            
        Returns:
            Path to the report directory
        """
        # Create report directory
        report_dir = self.reports_dir / report.backtest_id
        report_dir.mkdir(parents=True, exist_ok=True)
        
        if generate_html:
            self._generate_html_report(report, report_dir)
        
        if generate_csv:
            self._generate_trades_csv(report, report_dir)
        
        if generate_json:
            self._generate_metrics_json(report, report_dir)
        
        return str(report_dir)
    
    def _generate_html_report(
        self,
        report: BacktestReport,
        report_dir: Path,
    ) -> None:
        """Generate interactive HTML report."""
        html_content = self._build_html_template(report)
        
        html_path = report_dir / "report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    
    def _generate_trades_csv(
        self,
        report: BacktestReport,
        report_dir: Path,
    ) -> None:
        """Generate trades.csv file."""
        csv_path = report_dir / "trades.csv"
        
        if not report.trades:
            # Create empty CSV with headers
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "trade_id", "order_id", "timestamp", "symbol", "exchange",
                    "direction", "offset", "price", "volume", "turnover",
                    "commission", "slippage", "matching_mode", "l2_level",
                    "queue_wait_time", "is_manual"
                ])
            return
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                "trade_id", "order_id", "timestamp", "symbol", "exchange",
                "direction", "offset", "price", "volume", "turnover",
                "commission", "slippage", "matching_mode", "l2_level",
                "queue_wait_time", "is_manual"
            ])
            
            # Write trades
            for trade in report.trades:
                writer.writerow([
                    trade.trade_id,
                    trade.order_id,
                    trade.timestamp.isoformat(),
                    trade.symbol,
                    trade.exchange,
                    trade.direction,
                    trade.offset,
                    str(trade.price),
                    str(trade.volume),
                    str(trade.turnover),
                    str(trade.commission),
                    str(trade.slippage),
                    trade.matching_mode.value,
                    trade.l2_level.value if trade.l2_level else "",
                    trade.queue_wait_time if trade.queue_wait_time else "",
                    trade.is_manual,
                ])
    
    def _generate_metrics_json(
        self,
        report: BacktestReport,
        report_dir: Path,
    ) -> None:
        """Generate metrics.json file."""
        json_path = report_dir / "metrics.json"
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _build_html_template(self, report: BacktestReport) -> str:
        """Build the HTML report template with embedded data."""
        metrics = report.metrics
        
        # Prepare equity curve data for chart
        equity_data = []
        for point in report.equity_curve:
            equity_data.append({
                "time": point.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "value": float(point.equity),
            })
        
        # Prepare drawdown data
        drawdown_data = []
        for point in report.equity_curve:
            drawdown_data.append({
                "time": point.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "value": float(point.drawdown) * 100,  # Convert to percentage
            })
        
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>回测报告 - {report.strategy_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid #333;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 2.5em;
            color: #00d4ff;
            margin-bottom: 10px;
        }}
        .header .meta {{
            color: #888;
            font-size: 0.9em;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .metric-card {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 212, 255, 0.2);
        }}
        .metric-card .label {{
            font-size: 0.85em;
            color: #888;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .metric-card .value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #00d4ff;
        }}
        .metric-card .value.positive {{
            color: #00ff88;
        }}
        .metric-card .value.negative {{
            color: #ff4444;
        }}
        .chart-section {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .chart-section h2 {{
            color: #00d4ff;
            margin-bottom: 20px;
            font-size: 1.3em;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
        }}
        .trades-section {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .trades-section h2 {{
            color: #00d4ff;
            margin-bottom: 20px;
            font-size: 1.3em;
        }}
        .trades-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}
        .trades-table th {{
            background: rgba(0, 212, 255, 0.2);
            padding: 12px;
            text-align: left;
            border-bottom: 2px solid #00d4ff;
        }}
        .trades-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .trades-table tr:hover {{
            background: rgba(255, 255, 255, 0.05);
        }}
        .direction-long {{
            color: #00ff88;
        }}
        .direction-short {{
            color: #ff4444;
        }}
        .footer {{
            text-align: center;
            padding: 30px 0;
            color: #666;
            font-size: 0.85em;
            margin-top: 40px;
            border-top: 1px solid #333;
        }}
        @media (max-width: 768px) {{
            .metrics-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .header h1 {{
                font-size: 1.8em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {report.strategy_name}</h1>
            <div class="meta">
                回测ID: {report.backtest_id} | 
                生成时间: {report.created_at.strftime("%Y-%m-%d %H:%M:%S")} |
                撮合模式: {report.matching_mode}{f" ({report.l2_level})" if report.l2_level else ""}
            </div>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="label">总收益率</div>
                <div class="value {'positive' if metrics.total_return >= 0 else 'negative'}">
                    {metrics.total_return * 100:.2f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="label">夏普比率</div>
                <div class="value {'positive' if metrics.sharpe_ratio >= 0 else 'negative'}">
                    {metrics.sharpe_ratio:.2f}
                </div>
            </div>
            <div class="metric-card">
                <div class="label">最大回撤</div>
                <div class="value negative">
                    {metrics.max_drawdown * 100:.2f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="label">胜率</div>
                <div class="value">
                    {metrics.win_rate * 100:.1f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="label">盈亏比</div>
                <div class="value {'positive' if metrics.profit_factor >= 1 else 'negative'}">
                    {metrics.profit_factor:.2f}
                </div>
            </div>
            <div class="metric-card">
                <div class="label">总交易次数</div>
                <div class="value">
                    {metrics.total_trades}
                </div>
            </div>
            <div class="metric-card">
                <div class="label">年化收益</div>
                <div class="value {'positive' if metrics.annualized_return >= 0 else 'negative'}">
                    {metrics.annualized_return * 100:.2f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="label">年化波动率</div>
                <div class="value">
                    {metrics.volatility * 100:.2f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="label">卡玛比率</div>
                <div class="value {'positive' if metrics.calmar_ratio >= 0 else 'negative'}">
                    {metrics.calmar_ratio:.2f}
                </div>
            </div>
            <div class="metric-card">
                <div class="label">索提诺比率</div>
                <div class="value {'positive' if metrics.sortino_ratio >= 0 else 'negative'}">
                    {metrics.sortino_ratio:.2f}
                </div>
            </div>
            <div class="metric-card">
                <div class="label">初始资金</div>
                <div class="value">
                    ¥{metrics.initial_capital:,.0f}
                </div>
            </div>
            <div class="metric-card">
                <div class="label">最终权益</div>
                <div class="value {'positive' if metrics.final_equity >= metrics.initial_capital else 'negative'}">
                    ¥{metrics.final_equity:,.0f}
                </div>
            </div>
        </div>
        
        <div class="chart-section">
            <h2>📈 资金曲线</h2>
            <div class="chart-container">
                <canvas id="equityChart"></canvas>
            </div>
        </div>
        
        <div class="chart-section">
            <h2>📉 回撤曲线</h2>
            <div class="chart-container">
                <canvas id="drawdownChart"></canvas>
            </div>
        </div>
        
        <div class="trades-section">
            <h2>📋 交易记录 (共 {len(report.trades)} 笔)</h2>
            <div style="overflow-x: auto;">
                <table class="trades-table">
                    <thead>
                        <tr>
                            <th>时间</th>
                            <th>合约</th>
                            <th>方向</th>
                            <th>开平</th>
                            <th>价格</th>
                            <th>数量</th>
                            <th>成交额</th>
                            <th>手续费</th>
                            <th>滑点</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(self._format_trade_row(t) for t in report.trades[:100])}
                        {f'<tr><td colspan="9" style="text-align:center;color:#888;">... 显示前100条，共{len(report.trades)}条记录，完整数据请查看 trades.csv</td></tr>' if len(report.trades) > 100 else ''}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>Titan-Quant 量化回测系统 | 报告生成于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
    
    <script>
        // Equity curve data
        const equityData = {json.dumps(equity_data)};
        
        // Drawdown data
        const drawdownData = {json.dumps(drawdown_data)};
        
        // Equity Chart
        const equityCtx = document.getElementById('equityChart').getContext('2d');
        new Chart(equityCtx, {{
            type: 'line',
            data: {{
                labels: equityData.map(d => d.time),
                datasets: [{{
                    label: '权益',
                    data: equityData.map(d => d.value),
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    x: {{
                        display: true,
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }},
                        ticks: {{
                            color: '#888',
                            maxTicksLimit: 10
                        }}
                    }},
                    y: {{
                        display: true,
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }},
                        ticks: {{
                            color: '#888',
                            callback: function(value) {{
                                return '¥' + value.toLocaleString();
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Drawdown Chart
        const ddCtx = document.getElementById('drawdownChart').getContext('2d');
        new Chart(ddCtx, {{
            type: 'line',
            data: {{
                labels: drawdownData.map(d => d.time),
                datasets: [{{
                    label: '回撤 %',
                    data: drawdownData.map(d => d.value),
                    borderColor: '#ff4444',
                    backgroundColor: 'rgba(255, 68, 68, 0.2)',
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    x: {{
                        display: true,
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }},
                        ticks: {{
                            color: '#888',
                            maxTicksLimit: 10
                        }}
                    }},
                    y: {{
                        display: true,
                        reverse: true,
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }},
                        ticks: {{
                            color: '#888',
                            callback: function(value) {{
                                return value.toFixed(1) + '%';
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>'''
        
        return html
    
    def _format_trade_row(self, trade: TradeRecord) -> str:
        """Format a single trade as an HTML table row."""
        direction_class = "direction-long" if trade.direction == "LONG" else "direction-short"
        direction_text = "做多" if trade.direction == "LONG" else "做空"
        offset_text = "开仓" if trade.offset == "OPEN" else "平仓"
        
        return f'''
        <tr>
            <td>{trade.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</td>
            <td>{trade.symbol}</td>
            <td class="{direction_class}">{direction_text}</td>
            <td>{offset_text}</td>
            <td>{float(trade.price):,.4f}</td>
            <td>{float(trade.volume):,.4f}</td>
            <td>¥{float(trade.turnover):,.2f}</td>
            <td>¥{float(trade.commission):,.4f}</td>
            <td>{float(trade.slippage):,.6f}</td>
        </tr>'''


# ==================== Exports ====================

__all__ = [
    "EquityPoint",
    "BacktestMetrics",
    "BacktestReport",
    "MetricsCalculator",
    "ReportGenerator",
]
