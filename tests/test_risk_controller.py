"""
Tests for Risk Controller Module

Property Tests:
    - Property 17: Risk Control Trigger
    
Validates: Requirements 10.1, 10.2
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from core.engine.risk import (
    AccountSnapshot,
    RiskConfig,
    RiskController,
    RiskLevel,
    RiskTriggerType,
    TradeResult,
)
from core.exceptions import RiskControlError


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def default_config() -> RiskConfig:
    """Create default risk configuration."""
    return RiskConfig(
        max_daily_drawdown=0.05,
        max_single_loss=0.02,
        max_position_ratio=0.8,
        enable_auto_liquidation=True,
        warning_daily_drawdown=0.03,
        warning_single_loss=0.01,
        warning_position_ratio=0.6,
        consecutive_losses_threshold=5,
    )


@pytest.fixture
def risk_controller(default_config: RiskConfig) -> RiskController:
    """Create risk controller with default config."""
    return RiskController(default_config)


# =============================================================================
# Unit Tests
# =============================================================================

class TestRiskConfig:
    """Tests for RiskConfig class."""
    
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RiskConfig()
        assert config.max_daily_drawdown == 0.05
        assert config.max_single_loss == 0.02
        assert config.max_position_ratio == 0.8
        assert config.enable_auto_liquidation is True
    
    def test_config_validation(self) -> None:
        """Test configuration validation."""
        with pytest.raises(ValueError, match="max_daily_drawdown"):
            RiskConfig(max_daily_drawdown=1.5)
        
        with pytest.raises(ValueError, match="max_single_loss"):
            RiskConfig(max_single_loss=-0.1)
        
        with pytest.raises(ValueError, match="check_interval"):
            RiskConfig(check_interval=0)
    
    def test_config_from_yaml(self, tmp_path: Any) -> None:
        """Test loading config from YAML file."""
        yaml_content = """
risk:
  max_daily_drawdown: 0.10
  max_single_loss: 0.03
  max_position_ratio: 0.7
  enable_auto_liquidation: false
  check_interval: 2

thresholds:
  warning:
    daily_drawdown: 0.05
    single_loss: 0.015
    position_ratio: 0.5
  circuit_breaker:
    daily_drawdown: 0.10
    single_loss: 0.03
    consecutive_losses: 3
"""
        config_file = tmp_path / "risk_control.yaml"
        config_file.write_text(yaml_content)
        
        config = RiskConfig.from_yaml(config_file)
        assert config.max_daily_drawdown == 0.10
        assert config.max_single_loss == 0.03
        assert config.max_position_ratio == 0.7
        assert config.enable_auto_liquidation is False
        assert config.consecutive_losses_threshold == 3
    
    def test_config_to_dict(self, default_config: RiskConfig) -> None:
        """Test config serialization."""
        data = default_config.to_dict()
        assert data["max_daily_drawdown"] == 0.05
        assert data["max_single_loss"] == 0.02
        assert "enable_auto_liquidation" in data


class TestAccountSnapshot:
    """Tests for AccountSnapshot class."""
    
    def test_daily_drawdown_calculation(self) -> None:
        """Test daily drawdown calculation."""
        snapshot = AccountSnapshot(
            equity=95000,
            cash=50000,
            positions_value=45000,
            unrealized_pnl=-5000,
            realized_pnl=0,
            initial_equity=100000,
            high_water_mark=100000,
            timestamp=datetime.now(),
        )
        assert snapshot.daily_drawdown == pytest.approx(0.05)
    
    def test_position_ratio_calculation(self) -> None:
        """Test position ratio calculation."""
        snapshot = AccountSnapshot(
            equity=100000,
            cash=20000,
            positions_value=80000,
            unrealized_pnl=0,
            realized_pnl=0,
            initial_equity=100000,
            high_water_mark=100000,
            timestamp=datetime.now(),
        )
        assert snapshot.position_ratio == pytest.approx(0.8)
    
    def test_zero_equity_handling(self) -> None:
        """Test handling of zero equity."""
        snapshot = AccountSnapshot(
            equity=0,
            cash=0,
            positions_value=0,
            unrealized_pnl=0,
            realized_pnl=0,
            initial_equity=100000,
            high_water_mark=100000,
            timestamp=datetime.now(),
        )
        assert snapshot.daily_drawdown == 1.0
        assert snapshot.position_ratio == 0.0


class TestRiskController:
    """Tests for RiskController class."""
    
    def test_check_drawdown_normal(self, risk_controller: RiskController) -> None:
        """Test drawdown check returns normal for low drawdown."""
        level = risk_controller.check_drawdown(0.01)
        assert level == RiskLevel.NORMAL
    
    def test_check_drawdown_warning(self, risk_controller: RiskController) -> None:
        """Test drawdown check returns warning for moderate drawdown."""
        level = risk_controller.check_drawdown(0.04)
        assert level == RiskLevel.WARNING
    
    def test_check_drawdown_circuit_breaker(self, risk_controller: RiskController) -> None:
        """Test drawdown check returns circuit breaker for high drawdown."""
        level = risk_controller.check_drawdown(0.06)
        assert level == RiskLevel.CIRCUIT_BREAKER
    
    def test_check_single_loss_normal(self, risk_controller: RiskController) -> None:
        """Test single loss check returns normal for small loss."""
        level = risk_controller.check_single_loss(0.005)
        assert level == RiskLevel.NORMAL
    
    def test_check_single_loss_warning(self, risk_controller: RiskController) -> None:
        """Test single loss check returns warning for moderate loss."""
        level = risk_controller.check_single_loss(0.015)
        assert level == RiskLevel.WARNING
    
    def test_check_single_loss_circuit_breaker(self, risk_controller: RiskController) -> None:
        """Test single loss check returns circuit breaker for large loss."""
        level = risk_controller.check_single_loss(0.025)
        assert level == RiskLevel.CIRCUIT_BREAKER
    
    def test_circuit_breaker_trigger_on_drawdown(self, default_config: RiskConfig) -> None:
        """Test circuit breaker triggers on excessive drawdown."""
        controller = RiskController(default_config)
        
        snapshot = AccountSnapshot(
            equity=94000,
            cash=50000,
            positions_value=44000,
            unrealized_pnl=-6000,
            realized_pnl=0,
            initial_equity=100000,
            high_water_mark=100000,
            timestamp=datetime.now(),
        )
        
        with pytest.raises(RiskControlError) as exc_info:
            controller.update_account(snapshot)
        
        assert exc_info.value.trigger_type == "daily_drawdown"
        assert controller.is_circuit_breaker_active()
    
    def test_circuit_breaker_trigger_on_single_loss(self, default_config: RiskConfig) -> None:
        """Test circuit breaker triggers on excessive single loss."""
        controller = RiskController(default_config)
        controller.reset_daily_state(100000)
        
        trade = TradeResult(
            trade_id="test_001",
            symbol="BTC_USDT",
            pnl=-2500,
            pnl_ratio=-0.025,  # 2.5% loss > 2% threshold
            timestamp=datetime.now(),
        )
        
        with pytest.raises(RiskControlError) as exc_info:
            controller.record_trade(trade)
        
        assert exc_info.value.trigger_type == "single_loss"
        assert controller.is_circuit_breaker_active()
    
    def test_consecutive_losses_trigger(self, default_config: RiskConfig) -> None:
        """Test circuit breaker triggers on consecutive losses."""
        controller = RiskController(default_config)
        controller.reset_daily_state(100000)
        
        # Record 4 small losses (below threshold)
        for i in range(4):
            trade = TradeResult(
                trade_id=f"test_{i:03d}",
                symbol="BTC_USDT",
                pnl=-100,
                pnl_ratio=-0.001,
                timestamp=datetime.now(),
            )
            level = controller.record_trade(trade)
            assert level == RiskLevel.NORMAL
        
        # 5th consecutive loss should trigger circuit breaker
        trade = TradeResult(
            trade_id="test_004",
            symbol="BTC_USDT",
            pnl=-100,
            pnl_ratio=-0.001,
            timestamp=datetime.now(),
        )
        
        with pytest.raises(RiskControlError) as exc_info:
            controller.record_trade(trade)
        
        assert exc_info.value.trigger_type == "consecutive_losses"
    
    def test_winning_trade_resets_consecutive_losses(self, default_config: RiskConfig) -> None:
        """Test winning trade resets consecutive loss counter."""
        controller = RiskController(default_config)
        controller.reset_daily_state(100000)
        
        # Record 3 losses
        for i in range(3):
            trade = TradeResult(
                trade_id=f"loss_{i}",
                symbol="BTC_USDT",
                pnl=-100,
                pnl_ratio=-0.001,
                timestamp=datetime.now(),
            )
            controller.record_trade(trade)
        
        assert controller.get_consecutive_losses() == 3
        
        # Record a winning trade
        win_trade = TradeResult(
            trade_id="win_001",
            symbol="BTC_USDT",
            pnl=500,
            pnl_ratio=0.005,
            timestamp=datetime.now(),
        )
        controller.record_trade(win_trade)
        
        assert controller.get_consecutive_losses() == 0
    
    def test_liquidation_callback(self, default_config: RiskConfig) -> None:
        """Test liquidation callback is called on circuit breaker."""
        controller = RiskController(default_config)
        
        liquidation_called = []
        
        def mock_liquidation() -> None:
            liquidation_called.append(True)
        
        controller.set_liquidation_callback(mock_liquidation)
        
        snapshot = AccountSnapshot(
            equity=94000,
            cash=50000,
            positions_value=44000,
            unrealized_pnl=-6000,
            realized_pnl=0,
            initial_equity=100000,
            high_water_mark=100000,
            timestamp=datetime.now(),
        )
        
        with pytest.raises(RiskControlError):
            controller.update_account(snapshot)
        
        assert len(liquidation_called) == 1
    
    def test_alert_callback(self, default_config: RiskConfig) -> None:
        """Test alert callback is called on risk events."""
        controller = RiskController(default_config)
        
        alerts = []
        
        def mock_alert(event: Any) -> None:
            alerts.append(event)
        
        controller.set_alert_callback(mock_alert)
        
        snapshot = AccountSnapshot(
            equity=94000,
            cash=50000,
            positions_value=44000,
            unrealized_pnl=-6000,
            realized_pnl=0,
            initial_equity=100000,
            high_water_mark=100000,
            timestamp=datetime.now(),
        )
        
        with pytest.raises(RiskControlError):
            controller.update_account(snapshot)
        
        assert len(alerts) == 1
        assert alerts[0].risk_level == RiskLevel.CIRCUIT_BREAKER
    
    def test_trigger_history(self, default_config: RiskConfig) -> None:
        """Test trigger history is recorded."""
        controller = RiskController(default_config)
        
        snapshot = AccountSnapshot(
            equity=94000,
            cash=50000,
            positions_value=44000,
            unrealized_pnl=-6000,
            realized_pnl=0,
            initial_equity=100000,
            high_water_mark=100000,
            timestamp=datetime.now(),
        )
        
        with pytest.raises(RiskControlError):
            controller.update_account(snapshot)
        
        history = controller.get_trigger_history()
        assert len(history) == 1
        assert history[0].trigger_type == RiskTriggerType.DAILY_DRAWDOWN
    
    def test_reset_daily_state(self, risk_controller: RiskController) -> None:
        """Test daily state reset."""
        risk_controller.reset_daily_state(100000)
        
        account = risk_controller.get_current_account()
        assert account is not None
        assert account.equity == 100000
        assert account.initial_equity == 100000
        assert account.high_water_mark == 100000
        assert risk_controller.get_consecutive_losses() == 0


# =============================================================================
# Property-Based Tests
# =============================================================================

class TestRiskControlProperty:
    """Property-based tests for risk control."""
    
    @given(
        drawdown=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        max_drawdown=st.floats(min_value=0.01, max_value=0.5, allow_nan=False),
        warning_drawdown=st.floats(min_value=0.005, max_value=0.25, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_property_17_drawdown_trigger(
        self,
        drawdown: float,
        max_drawdown: float,
        warning_drawdown: float,
    ) -> None:
        """
        Property 17: Risk Control Trigger (Drawdown)
        
        For any account state where daily drawdown exceeds X%, the Risk_Controller
        must trigger a circuit breaker, stop the strategy, and initiate position
        liquidation.
        
        Validates: Requirements 10.1
        """
        # Ensure warning < max threshold
        assume(warning_drawdown < max_drawdown)
        
        config = RiskConfig(
            max_daily_drawdown=max_drawdown,
            warning_daily_drawdown=warning_drawdown,
            enable_auto_liquidation=True,
        )
        controller = RiskController(config)
        
        level = controller.check_drawdown(drawdown)
        
        # Property: If drawdown >= max_drawdown, must return CIRCUIT_BREAKER
        if drawdown >= max_drawdown:
            assert level == RiskLevel.CIRCUIT_BREAKER, (
                f"Drawdown {drawdown:.4f} >= threshold {max_drawdown:.4f} "
                f"should trigger CIRCUIT_BREAKER, got {level}"
            )
        # Property: If warning <= drawdown < max, must return WARNING
        elif drawdown >= warning_drawdown:
            assert level == RiskLevel.WARNING, (
                f"Drawdown {drawdown:.4f} >= warning {warning_drawdown:.4f} "
                f"should trigger WARNING, got {level}"
            )
        # Property: If drawdown < warning, must return NORMAL
        else:
            assert level == RiskLevel.NORMAL, (
                f"Drawdown {drawdown:.4f} < warning {warning_drawdown:.4f} "
                f"should be NORMAL, got {level}"
            )
    
    @given(
        loss_ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        max_loss=st.floats(min_value=0.01, max_value=0.5, allow_nan=False),
        warning_loss=st.floats(min_value=0.005, max_value=0.25, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_property_17_single_loss_trigger(
        self,
        loss_ratio: float,
        max_loss: float,
        warning_loss: float,
    ) -> None:
        """
        Property 17: Risk Control Trigger (Single Loss)
        
        For any trade where single loss exceeds Y%, the Risk_Controller must
        trigger a circuit breaker, stop the strategy, and initiate position
        liquidation.
        
        Validates: Requirements 10.2
        """
        # Ensure warning < max threshold
        assume(warning_loss < max_loss)
        
        config = RiskConfig(
            max_single_loss=max_loss,
            warning_single_loss=warning_loss,
            enable_auto_liquidation=True,
        )
        controller = RiskController(config)
        
        level = controller.check_single_loss(loss_ratio)
        
        # Property: If loss >= max_loss, must return CIRCUIT_BREAKER
        if loss_ratio >= max_loss:
            assert level == RiskLevel.CIRCUIT_BREAKER, (
                f"Loss {loss_ratio:.4f} >= threshold {max_loss:.4f} "
                f"should trigger CIRCUIT_BREAKER, got {level}"
            )
        # Property: If warning <= loss < max, must return WARNING
        elif loss_ratio >= warning_loss:
            assert level == RiskLevel.WARNING, (
                f"Loss {loss_ratio:.4f} >= warning {warning_loss:.4f} "
                f"should trigger WARNING, got {level}"
            )
        # Property: If loss < warning, must return NORMAL
        else:
            assert level == RiskLevel.NORMAL, (
                f"Loss {loss_ratio:.4f} < warning {warning_loss:.4f} "
                f"should be NORMAL, got {level}"
            )
    
    @given(
        initial_equity=st.floats(min_value=10000, max_value=10000000, allow_nan=False),
        equity_drop_pct=st.floats(min_value=0.0, max_value=0.2, allow_nan=False),
        max_drawdown=st.floats(min_value=0.03, max_value=0.15, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_property_17_full_circuit_breaker(
        self,
        initial_equity: float,
        equity_drop_pct: float,
        max_drawdown: float,
    ) -> None:
        """
        Property 17: Risk Control Trigger (Full Integration)
        
        For any account state where daily drawdown exceeds the configured
        threshold, the Risk_Controller must:
        1. Trigger circuit breaker
        2. Stop the strategy
        3. Raise RiskControlError
        
        Validates: Requirements 10.1, 10.2
        """
        # Ensure there's a meaningful gap between drop and threshold to avoid float precision issues
        assume(abs(equity_drop_pct - max_drawdown) > 0.001)
        
        config = RiskConfig(
            max_daily_drawdown=max_drawdown,
            warning_daily_drawdown=max_drawdown * 0.6,
            enable_auto_liquidation=True,
        )
        controller = RiskController(config)
        
        # Calculate current equity after drop
        current_equity = initial_equity * (1 - equity_drop_pct)
        
        snapshot = AccountSnapshot(
            equity=current_equity,
            cash=current_equity * 0.5,
            positions_value=current_equity * 0.5,
            unrealized_pnl=current_equity - initial_equity,
            realized_pnl=0,
            initial_equity=initial_equity,
            high_water_mark=initial_equity,
            timestamp=datetime.now(),
        )
        
        # Property: If drawdown > threshold (with margin), must raise RiskControlError
        if equity_drop_pct > max_drawdown:
            with pytest.raises(RiskControlError) as exc_info:
                controller.update_account(snapshot)
            
            # Verify circuit breaker is active
            assert controller.is_circuit_breaker_active(), (
                "Circuit breaker should be active after trigger"
            )
            
            # Verify error contains correct information
            assert exc_info.value.trigger_type == "daily_drawdown"
            assert exc_info.value.threshold == max_drawdown
        else:
            # Should not raise for drawdown below threshold
            level = controller.update_account(snapshot)
            assert level in (RiskLevel.NORMAL, RiskLevel.WARNING)
            assert not controller.is_circuit_breaker_active()
