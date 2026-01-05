"""
Titan-Quant Risk Controller
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Union

import yaml

from core.exceptions import ErrorCodes, RiskControlError

logger = logging.getLogger(__name__)


class RiskTriggerType(Enum):
    DAILY_DRAWDOWN = "daily_drawdown"
    SINGLE_LOSS = "single_loss"
    POSITION_RATIO = "position_ratio"
    CONSECUTIVE_LOSSES = "consecutive_losses"


class RiskLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass
class RiskConfig:
    max_daily_drawdown: float = 0.05
    max_single_loss: float = 0.02
    max_position_ratio: float = 0.8
    enable_auto_liquidation: bool = True
    check_interval: float = 1.0
    warning_daily_drawdown: float = 0.03
    warning_single_loss: float = 0.01
    warning_position_ratio: float = 0.6
    consecutive_losses_threshold: int = 5

    def __post_init__(self) -> None:
        if not 0 < self.max_daily_drawdown <= 1:
            raise ValueError("max_daily_drawdown must be between 0 and 1")
        if not 0 < self.max_single_loss <= 1:
            raise ValueError("max_single_loss must be between 0 and 1")
        if not 0 < self.max_position_ratio <= 1:
            raise ValueError("max_position_ratio must be between 0 and 1")
        if self.check_interval <= 0:
            raise ValueError("check_interval must be positive")
        if self.consecutive_losses_threshold < 1:
            raise ValueError("consecutive_losses_threshold must be at least 1")

    @classmethod
    def from_yaml(cls, file_path: Union[str, Path]) -> "RiskConfig":
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Risk config file not found: {file_path}")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        risk_data = data.get("risk", {})
        thresholds = data.get("thresholds", {})
        warning = thresholds.get("warning", {})
        circuit_breaker = thresholds.get("circuit_breaker", {})
        return cls(
            max_daily_drawdown=circuit_breaker.get("daily_drawdown", risk_data.get("max_daily_drawdown", 0.05)),
            max_single_loss=circuit_breaker.get("single_loss", risk_data.get("max_single_loss", 0.02)),
            max_position_ratio=risk_data.get("max_position_ratio", 0.8),
            enable_auto_liquidation=risk_data.get("enable_auto_liquidation", True),
            check_interval=risk_data.get("check_interval", 1.0),
            warning_daily_drawdown=warning.get("daily_drawdown", 0.03),
            warning_single_loss=warning.get("single_loss", 0.01),
            warning_position_ratio=warning.get("position_ratio", 0.6),
            consecutive_losses_threshold=circuit_breaker.get("consecutive_losses", 5),
        )

    def to_dict(self) -> dict:
        return {
            "max_daily_drawdown": self.max_daily_drawdown,
            "max_single_loss": self.max_single_loss,
            "max_position_ratio": self.max_position_ratio,
            "enable_auto_liquidation": self.enable_auto_liquidation,
            "check_interval": self.check_interval,
            "warning_daily_drawdown": self.warning_daily_drawdown,
            "warning_single_loss": self.warning_single_loss,
            "warning_position_ratio": self.warning_position_ratio,
            "consecutive_losses_threshold": self.consecutive_losses_threshold,
        }


@dataclass
class RiskTriggerEvent:
    trigger_type: RiskTriggerType
    trigger_time: datetime
    threshold: float
    actual_value: float
    risk_level: RiskLevel
    market_state: dict = field(default_factory=dict)
    account_state: dict = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "trigger_type": self.trigger_type.value,
            "trigger_time": self.trigger_time.isoformat(),
            "threshold": self.threshold,
            "actual_value": self.actual_value,
            "risk_level": self.risk_level.value,
            "market_state": self.market_state,
            "account_state": self.account_state,
            "message": self.message,
        }


@dataclass
class AccountSnapshot:
    equity: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl: float
    initial_equity: float
    high_water_mark: float
    timestamp: datetime

    @property
    def daily_drawdown(self) -> float:
        if self.high_water_mark <= 0:
            return 0.0
        return (self.high_water_mark - self.equity) / self.high_water_mark

    @property
    def daily_return(self) -> float:
        if self.initial_equity <= 0:
            return 0.0
        return (self.equity - self.initial_equity) / self.initial_equity

    @property
    def position_ratio(self) -> float:
        if self.equity <= 0:
            return 0.0
        return self.positions_value / self.equity

    def to_dict(self) -> dict:
        return {
            "equity": self.equity,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "initial_equity": self.initial_equity,
            "high_water_mark": self.high_water_mark,
            "timestamp": self.timestamp.isoformat(),
            "daily_drawdown": self.daily_drawdown,
            "daily_return": self.daily_return,
            "position_ratio": self.position_ratio,
        }


@dataclass
class TradeResult:
    trade_id: str
    symbol: str
    pnl: float
    pnl_ratio: float
    timestamp: datetime

    @property
    def is_loss(self) -> bool:
        return self.pnl < 0

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "pnl": self.pnl,
            "pnl_ratio": self.pnl_ratio,
            "timestamp": self.timestamp.isoformat(),
            "is_loss": self.is_loss,
        }


LiquidationCallback = Callable[[], None]
AlertCallback = Callable[[RiskTriggerEvent], None]


class IRiskController(ABC):
    @abstractmethod
    def configure(self, config: RiskConfig) -> None:
        pass

    @abstractmethod
    def update_account(self, snapshot: AccountSnapshot) -> RiskLevel:
        pass

    @abstractmethod
    def record_trade(self, trade: TradeResult) -> RiskLevel:
        pass

    @abstractmethod
    def check_drawdown(self, drawdown: float) -> RiskLevel:
        pass

    @abstractmethod
    def check_single_loss(self, loss_ratio: float) -> RiskLevel:
        pass

    @abstractmethod
    def check_position_ratio(self, ratio: float) -> RiskLevel:
        pass

    @abstractmethod
    def trigger_circuit_breaker(self, trigger_type: RiskTriggerType, threshold: float,
                                 actual_value: float, market_state: dict) -> None:
        pass

    @abstractmethod
    def reset_daily_state(self, initial_equity: float) -> None:
        pass

    @abstractmethod
    def get_trigger_history(self) -> list:
        pass

    @abstractmethod
    def is_circuit_breaker_active(self) -> bool:
        pass

    @abstractmethod
    def set_liquidation_callback(self, callback: LiquidationCallback) -> None:
        pass

    @abstractmethod
    def set_alert_callback(self, callback: AlertCallback) -> None:
        pass


class RiskController(IRiskController):
    def __init__(self, config: Optional[RiskConfig] = None) -> None:
        self._config = config or RiskConfig()
        self._circuit_breaker_active = False
        self._trigger_history: list = []
        self._consecutive_losses = 0
        self._current_account: Optional[AccountSnapshot] = None
        self._liquidation_callback: Optional[LiquidationCallback] = None
        self._alert_callback: Optional[AlertCallback] = None
        self._strategy_stopped = False

    def configure(self, config: RiskConfig) -> None:
        self._config = config
        logger.info(f"Risk controller configured: {config.to_dict()}")

    def update_account(self, snapshot: AccountSnapshot) -> RiskLevel:
        self._current_account = snapshot
        drawdown_level = self.check_drawdown(snapshot.daily_drawdown)
        if drawdown_level == RiskLevel.CIRCUIT_BREAKER:
            self.trigger_circuit_breaker(
                RiskTriggerType.DAILY_DRAWDOWN,
                self._config.max_daily_drawdown,
                snapshot.daily_drawdown,
                {"timestamp": snapshot.timestamp.isoformat()},
            )
            return RiskLevel.CIRCUIT_BREAKER
        position_level = self.check_position_ratio(snapshot.position_ratio)
        if position_level == RiskLevel.CIRCUIT_BREAKER:
            self.trigger_circuit_breaker(
                RiskTriggerType.POSITION_RATIO,
                self._config.max_position_ratio,
                snapshot.position_ratio,
                {"timestamp": snapshot.timestamp.isoformat()},
            )
            return RiskLevel.CIRCUIT_BREAKER
        if drawdown_level == RiskLevel.WARNING or position_level == RiskLevel.WARNING:
            return RiskLevel.WARNING
        return RiskLevel.NORMAL

    def record_trade(self, trade: TradeResult) -> RiskLevel:
        if trade.is_loss:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0
        if trade.is_loss:
            loss_ratio = abs(trade.pnl_ratio)
            loss_level = self.check_single_loss(loss_ratio)
            if loss_level == RiskLevel.CIRCUIT_BREAKER:
                self.trigger_circuit_breaker(
                    RiskTriggerType.SINGLE_LOSS,
                    self._config.max_single_loss,
                    loss_ratio,
                    {"trade_id": trade.trade_id, "symbol": trade.symbol,
                     "pnl": trade.pnl, "timestamp": trade.timestamp.isoformat()},
                )
                return RiskLevel.CIRCUIT_BREAKER
            if loss_level == RiskLevel.WARNING:
                self._emit_warning(
                    RiskTriggerType.SINGLE_LOSS,
                    self._config.warning_single_loss,
                    loss_ratio,
                    {"trade_id": trade.trade_id, "symbol": trade.symbol, "pnl": trade.pnl},
                )
                return RiskLevel.WARNING
        if self._consecutive_losses >= self._config.consecutive_losses_threshold:
            self.trigger_circuit_breaker(
                RiskTriggerType.CONSECUTIVE_LOSSES,
                float(self._config.consecutive_losses_threshold),
                float(self._consecutive_losses),
                {"consecutive_losses": self._consecutive_losses,
                 "timestamp": trade.timestamp.isoformat()},
            )
            return RiskLevel.CIRCUIT_BREAKER
        return RiskLevel.NORMAL

    def check_drawdown(self, drawdown: float) -> RiskLevel:
        if drawdown >= self._config.max_daily_drawdown:
            return RiskLevel.CIRCUIT_BREAKER
        elif drawdown >= self._config.warning_daily_drawdown:
            return RiskLevel.WARNING
        return RiskLevel.NORMAL

    def check_single_loss(self, loss_ratio: float) -> RiskLevel:
        if loss_ratio >= self._config.max_single_loss:
            return RiskLevel.CIRCUIT_BREAKER
        elif loss_ratio >= self._config.warning_single_loss:
            return RiskLevel.WARNING
        return RiskLevel.NORMAL

    def check_position_ratio(self, ratio: float) -> RiskLevel:
        if ratio >= self._config.max_position_ratio:
            return RiskLevel.CIRCUIT_BREAKER
        elif ratio >= self._config.warning_position_ratio:
            return RiskLevel.WARNING
        return RiskLevel.NORMAL

    def trigger_circuit_breaker(self, trigger_type: RiskTriggerType, threshold: float,
                                 actual_value: float, market_state: dict) -> None:
        if self._circuit_breaker_active:
            logger.warning("Circuit breaker already active, ignoring trigger")
            return
        self._circuit_breaker_active = True
        self._strategy_stopped = True
        account_state = {}
        if self._current_account:
            account_state = self._current_account.to_dict()
        message = self._build_trigger_message(trigger_type, threshold, actual_value)
        event = RiskTriggerEvent(
            trigger_type=trigger_type, trigger_time=datetime.now(),
            threshold=threshold, actual_value=actual_value,
            risk_level=RiskLevel.CIRCUIT_BREAKER, market_state=market_state,
            account_state=account_state, message=message,
        )
        self._trigger_history.append(event)
        logger.critical(f"CIRCUIT BREAKER TRIGGERED: {trigger_type.value} - "
                       f"threshold={threshold:.4f}, actual={actual_value:.4f}")
        if self._alert_callback:
            self._alert_callback(event)
        if self._config.enable_auto_liquidation and self._liquidation_callback:
            logger.warning("Initiating forced liquidation...")
            try:
                self._liquidation_callback()
                logger.info("Forced liquidation completed")
            except Exception as e:
                logger.error(f"Forced liquidation failed: {e}")
        raise RiskControlError(
            message=message, error_code=self._get_error_code(trigger_type),
            trigger_type=trigger_type.value, threshold=threshold,
            actual_value=actual_value, auto_liquidate=self._config.enable_auto_liquidation,
        )

    def _emit_warning(self, trigger_type: RiskTriggerType, threshold: float,
                      actual_value: float, market_state: dict) -> None:
        account_state = {}
        if self._current_account:
            account_state = self._current_account.to_dict()
        message = self._build_warning_message(trigger_type, threshold, actual_value)
        event = RiskTriggerEvent(
            trigger_type=trigger_type, trigger_time=datetime.now(),
            threshold=threshold, actual_value=actual_value,
            risk_level=RiskLevel.WARNING, market_state=market_state,
            account_state=account_state, message=message,
        )
        self._trigger_history.append(event)
        logger.warning(f"RISK WARNING: {message}")
        if self._alert_callback:
            self._alert_callback(event)

    def _build_trigger_message(self, trigger_type: RiskTriggerType, threshold: float,
                                actual_value: float) -> str:
        messages = {
            RiskTriggerType.DAILY_DRAWDOWN: f"Daily drawdown exceeded: {actual_value:.2%} > {threshold:.2%}",
            RiskTriggerType.SINGLE_LOSS: f"Single trade loss exceeded: {actual_value:.2%} > {threshold:.2%}",
            RiskTriggerType.POSITION_RATIO: f"Position ratio exceeded: {actual_value:.2%} > {threshold:.2%}",
            RiskTriggerType.CONSECUTIVE_LOSSES: f"Consecutive losses exceeded: {int(actual_value)} >= {int(threshold)}",
        }
        return messages.get(trigger_type, f"Risk trigger: {trigger_type.value}")

    def _build_warning_message(self, trigger_type: RiskTriggerType, threshold: float,
                                actual_value: float) -> str:
        messages = {
            RiskTriggerType.DAILY_DRAWDOWN: f"Daily drawdown warning: {actual_value:.2%} approaching {threshold:.2%}",
            RiskTriggerType.SINGLE_LOSS: f"Single trade loss warning: {actual_value:.2%} approaching {threshold:.2%}",
            RiskTriggerType.POSITION_RATIO: f"Position ratio warning: {actual_value:.2%} approaching {threshold:.2%}",
            RiskTriggerType.CONSECUTIVE_LOSSES: f"Consecutive losses warning: {int(actual_value)} approaching {int(threshold)}",
        }
        return messages.get(trigger_type, f"Risk warning: {trigger_type.value}")

    def _get_error_code(self, trigger_type: RiskTriggerType) -> str:
        codes = {
            RiskTriggerType.DAILY_DRAWDOWN: ErrorCodes.RISK_DRAWDOWN_EXCEEDED,
            RiskTriggerType.SINGLE_LOSS: ErrorCodes.RISK_SINGLE_LOSS_EXCEEDED,
            RiskTriggerType.POSITION_RATIO: ErrorCodes.RISK_POSITION_EXCEEDED,
            RiskTriggerType.CONSECUTIVE_LOSSES: ErrorCodes.RISK_CIRCUIT_BREAKER,
        }
        return codes.get(trigger_type, ErrorCodes.RISK_CIRCUIT_BREAKER)

    def reset_daily_state(self, initial_equity: float) -> None:
        self._circuit_breaker_active = False
        self._strategy_stopped = False
        self._consecutive_losses = 0
        self._current_account = AccountSnapshot(
            equity=initial_equity, cash=initial_equity, positions_value=0.0,
            unrealized_pnl=0.0, realized_pnl=0.0, initial_equity=initial_equity,
            high_water_mark=initial_equity, timestamp=datetime.now(),
        )
        logger.info(f"Daily state reset with initial equity: {initial_equity}")

    def get_trigger_history(self) -> list:
        return self._trigger_history.copy()

    def is_circuit_breaker_active(self) -> bool:
        return self._circuit_breaker_active

    def is_strategy_stopped(self) -> bool:
        return self._strategy_stopped

    def set_liquidation_callback(self, callback: LiquidationCallback) -> None:
        self._liquidation_callback = callback

    def set_alert_callback(self, callback: AlertCallback) -> None:
        self._alert_callback = callback

    def get_config(self) -> RiskConfig:
        return self._config

    def get_current_account(self) -> Optional[AccountSnapshot]:
        return self._current_account

    def get_consecutive_losses(self) -> int:
        return self._consecutive_losses


__all__ = [
    "RiskTriggerType",
    "RiskLevel",
    "RiskConfig",
    "RiskTriggerEvent",
    "AccountSnapshot",
    "TradeResult",
    "LiquidationCallback",
    "AlertCallback",
    "IRiskController",
    "RiskController",
]
