"""
Tests for Titan-Quant Message Handlers

Tests the message handlers for WebSocket communication including:
- Backtest control handlers
- Strategy operation handlers
- Manual trading handlers
- Snapshot handlers
- Alert handlers
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from core.server import Message, MessageType, MessageRouter
from core.handlers import MessageHandlers, SystemState


class TestSystemState:
    """Tests for SystemState class."""
    
    def test_default_state(self):
        """Test default system state."""
        state = SystemState()
        
        assert state.backtest_status == "idle"
        assert state.replay_status is None
        assert state.account is None
        assert state.positions == []
        assert state.strategies == []
        assert state.alerts == []
    
    def test_state_to_dict(self):
        """Test converting state to dictionary."""
        state = SystemState(
            backtest_status="running",
            account={"balance": 100000},
            positions=[{"symbol": "BTC_USDT", "volume": 1.0}],
        )
        
        result = state.to_dict()
        
        assert result["backtest_status"] == "running"
        assert result["account"] == {"balance": 100000}
        assert len(result["positions"]) == 1
        assert "timestamp" in result


class TestMessageHandlers:
    """Tests for MessageHandlers class."""
    
    def test_create_handlers(self):
        """Test creating message handlers."""
        handlers = MessageHandlers()
        
        assert handlers._event_bus is None
        assert handlers._replay_controller is None
        assert handlers._strategy_manager is None
    
    def test_set_components(self):
        """Test setting component references."""
        handlers = MessageHandlers()
        
        mock_event_bus = MagicMock()
        mock_replay = MagicMock()
        mock_strategy = MagicMock()
        
        handlers.set_event_bus(mock_event_bus)
        handlers.set_replay_controller(mock_replay)
        handlers.set_strategy_manager(mock_strategy)
        
        assert handlers._event_bus == mock_event_bus
        assert handlers._replay_controller == mock_replay
        assert handlers._strategy_manager == mock_strategy
    
    def test_create_router(self):
        """Test creating message router."""
        handlers = MessageHandlers()
        router = handlers.create_router()
        
        assert isinstance(router, MessageRouter)
        
        # Check that handlers are registered
        registered = router.get_handlers()
        assert MessageType.START_BACKTEST in registered
        assert MessageType.PAUSE in registered
        assert MessageType.RESUME in registered
        assert MessageType.STEP in registered
        assert MessageType.STOP in registered
        assert MessageType.LOAD_STRATEGY in registered
        assert MessageType.RELOAD_STRATEGY in registered
        assert MessageType.UPDATE_PARAMS in registered
        assert MessageType.MANUAL_ORDER in registered
        assert MessageType.CANCEL_ORDER in registered
        assert MessageType.CLOSE_ALL in registered
        assert MessageType.SAVE_SNAPSHOT in registered
        assert MessageType.LOAD_SNAPSHOT in registered
        assert MessageType.ALERT_ACK in registered
        assert MessageType.REQUEST_STATE in registered
    
    def test_get_state(self):
        """Test getting system state."""
        handlers = MessageHandlers()
        state = handlers.get_state()
        
        assert "backtest_status" in state
        assert "timestamp" in state
    
    def test_add_alert(self):
        """Test adding an alert."""
        handlers = MessageHandlers()
        
        handlers.add_alert("alert-001", {"message": "Test alert"})
        
        assert "alert-001" in handlers._pending_alerts
        assert handlers._pending_alerts["alert-001"]["message"] == "Test alert"


class TestBacktestControlHandlers:
    """Tests for backtest control handlers."""
    
    def test_handle_start_backtest(self):
        """Test start backtest handler."""
        handlers = MessageHandlers()
        
        msg = Message.create(
            MessageType.START_BACKTEST,
            payload={
                "strategy_id": "test-strategy",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "initial_capital": 100000,
            },
        )
        
        response = handlers.handle_start_backtest(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
    
    def test_handle_start_backtest_missing_field(self):
        """Test start backtest with missing required field."""
        handlers = MessageHandlers()
        
        msg = Message.create(
            MessageType.START_BACKTEST,
            payload={"strategy_id": "test-strategy"},  # Missing dates
        )
        
        response = handlers.handle_start_backtest(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "Missing required field" in response.payload["error"]
    
    def test_handle_pause_no_controller(self):
        """Test pause without replay controller."""
        handlers = MessageHandlers()
        
        msg = Message.create(MessageType.PAUSE)
        response = handlers.handle_pause(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "not available" in response.payload["error"]
    
    def test_handle_pause_with_controller(self):
        """Test pause with replay controller."""
        handlers = MessageHandlers()
        mock_controller = MagicMock()
        mock_controller.pause.return_value = True
        handlers.set_replay_controller(mock_controller)
        
        msg = Message.create(MessageType.PAUSE)
        response = handlers.handle_pause(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        mock_controller.pause.assert_called_once()
    
    def test_handle_resume_with_controller(self):
        """Test resume with replay controller."""
        handlers = MessageHandlers()
        mock_controller = MagicMock()
        mock_controller.resume.return_value = True
        handlers.set_replay_controller(mock_controller)
        
        msg = Message.create(MessageType.RESUME)
        response = handlers.handle_resume(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        mock_controller.resume.assert_called_once()
    
    def test_handle_step_with_controller(self):
        """Test step with replay controller."""
        handlers = MessageHandlers()
        mock_controller = MagicMock()
        mock_controller.step.return_value = True
        mock_status = MagicMock()
        mock_status.current_index = 100
        mock_status.current_time = datetime(2024, 1, 15)
        mock_controller.get_status.return_value = mock_status
        handlers.set_replay_controller(mock_controller)
        
        msg = Message.create(MessageType.STEP)
        response = handlers.handle_step(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        assert response.payload["current_index"] == 100
        mock_controller.step.assert_called_once()
    
    def test_handle_stop_with_controller(self):
        """Test stop with replay controller."""
        handlers = MessageHandlers()
        mock_controller = MagicMock()
        mock_controller.stop.return_value = True
        handlers.set_replay_controller(mock_controller)
        
        msg = Message.create(MessageType.STOP)
        response = handlers.handle_stop(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        mock_controller.stop.assert_called_once()


class TestStrategyHandlers:
    """Tests for strategy operation handlers."""
    
    def test_handle_load_strategy_no_manager(self):
        """Test load strategy without manager."""
        handlers = MessageHandlers()
        
        msg = Message.create(
            MessageType.LOAD_STRATEGY,
            payload={"file_path": "strategies/test.py"},
        )
        
        response = handlers.handle_load_strategy(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "not available" in response.payload["error"]
    
    def test_handle_load_strategy_missing_path(self):
        """Test load strategy with missing path."""
        handlers = MessageHandlers()
        mock_manager = MagicMock()
        handlers.set_strategy_manager(mock_manager)
        
        msg = Message.create(MessageType.LOAD_STRATEGY, payload={})
        response = handlers.handle_load_strategy(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "Missing file_path" in response.payload["error"]
    
    def test_handle_load_strategy_success(self):
        """Test successful strategy load."""
        handlers = MessageHandlers()
        mock_manager = MagicMock()
        mock_info = MagicMock()
        mock_info.strategy_id = "strategy-001"
        mock_info.class_name = "TestStrategy"
        mock_info.parameters = []
        mock_manager.load_strategy_file.return_value = mock_info
        handlers.set_strategy_manager(mock_manager)
        
        msg = Message.create(
            MessageType.LOAD_STRATEGY,
            payload={"file_path": "strategies/test.py"},
        )
        
        response = handlers.handle_load_strategy(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        assert response.payload["strategy_id"] == "strategy-001"
    
    def test_handle_update_params_success(self):
        """Test successful parameter update."""
        handlers = MessageHandlers()
        mock_manager = MagicMock()
        mock_manager.set_parameters.return_value = True
        handlers.set_strategy_manager(mock_manager)
        
        msg = Message.create(
            MessageType.UPDATE_PARAMS,
            payload={
                "strategy_id": "strategy-001",
                "params": {"fast_period": 5, "slow_period": 20},
            },
        )
        
        response = handlers.handle_update_params(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        mock_manager.set_parameters.assert_called_once_with(
            "strategy-001",
            {"fast_period": 5, "slow_period": 20},
        )


class TestManualTradingHandlers:
    """Tests for manual trading handlers."""
    
    def test_handle_manual_order(self):
        """Test manual order handler."""
        handlers = MessageHandlers()
        
        msg = Message.create(
            MessageType.MANUAL_ORDER,
            payload={
                "symbol": "BTC_USDT",
                "direction": "LONG",
                "offset": "OPEN",
                "price": 50000.0,
                "volume": 1.0,
            },
        )
        
        response = handlers.handle_manual_order(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        assert "order_id" in response.payload
    
    def test_handle_manual_order_missing_field(self):
        """Test manual order with missing field."""
        handlers = MessageHandlers()
        
        msg = Message.create(
            MessageType.MANUAL_ORDER,
            payload={"symbol": "BTC_USDT"},  # Missing other fields
        )
        
        response = handlers.handle_manual_order(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "Missing required field" in response.payload["error"]
    
    def test_handle_cancel_order(self):
        """Test cancel order handler."""
        handlers = MessageHandlers()
        
        msg = Message.create(
            MessageType.CANCEL_ORDER,
            payload={"order_id": "order-001"},
        )
        
        response = handlers.handle_cancel_order(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
    
    def test_handle_cancel_order_missing_id(self):
        """Test cancel order with missing ID."""
        handlers = MessageHandlers()
        
        msg = Message.create(MessageType.CANCEL_ORDER, payload={})
        response = handlers.handle_cancel_order(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "Missing order_id" in response.payload["error"]
    
    def test_handle_close_all(self):
        """Test close all positions handler."""
        handlers = MessageHandlers()
        
        msg = Message.create(MessageType.CLOSE_ALL)
        response = handlers.handle_close_all(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True


class TestSnapshotHandlers:
    """Tests for snapshot handlers."""
    
    def test_handle_save_snapshot_no_controller(self):
        """Test save snapshot without controller."""
        handlers = MessageHandlers()
        
        msg = Message.create(MessageType.SAVE_SNAPSHOT)
        response = handlers.handle_save_snapshot(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "not available" in response.payload["error"]
    
    def test_handle_save_snapshot_success(self):
        """Test successful snapshot save."""
        handlers = MessageHandlers()
        mock_controller = MagicMock()
        mock_controller.save_snapshot.return_value = "snapshots/test.json"
        handlers.set_replay_controller(mock_controller)
        
        msg = Message.create(
            MessageType.SAVE_SNAPSHOT,
            payload={"description": "Test snapshot"},
        )
        
        response = handlers.handle_save_snapshot(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        assert response.payload["path"] == "snapshots/test.json"
    
    def test_handle_load_snapshot_missing_path(self):
        """Test load snapshot with missing path."""
        handlers = MessageHandlers()
        mock_controller = MagicMock()
        handlers.set_replay_controller(mock_controller)
        
        msg = Message.create(MessageType.LOAD_SNAPSHOT, payload={})
        response = handlers.handle_load_snapshot(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "Missing path" in response.payload["error"]
    
    def test_handle_load_snapshot_success(self):
        """Test successful snapshot load."""
        handlers = MessageHandlers()
        mock_controller = MagicMock()
        mock_controller.load_snapshot.return_value = True
        handlers.set_replay_controller(mock_controller)
        
        msg = Message.create(
            MessageType.LOAD_SNAPSHOT,
            payload={"path": "snapshots/test.json"},
        )
        
        response = handlers.handle_load_snapshot(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True


class TestAlertHandlers:
    """Tests for alert handlers."""
    
    def test_handle_alert_ack_success(self):
        """Test successful alert acknowledgment."""
        handlers = MessageHandlers()
        handlers.add_alert("alert-001", {"message": "Test"})
        
        msg = Message.create(
            MessageType.ALERT_ACK,
            payload={"alert_id": "alert-001"},
        )
        
        response = handlers.handle_alert_ack(msg)
        
        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.payload["success"] is True
        assert "alert-001" not in handlers._pending_alerts
    
    def test_handle_alert_ack_not_found(self):
        """Test alert acknowledgment for non-existent alert."""
        handlers = MessageHandlers()
        
        msg = Message.create(
            MessageType.ALERT_ACK,
            payload={"alert_id": "nonexistent"},
        )
        
        response = handlers.handle_alert_ack(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "not found" in response.payload["error"]
    
    def test_handle_alert_ack_missing_id(self):
        """Test alert acknowledgment with missing ID."""
        handlers = MessageHandlers()
        
        msg = Message.create(MessageType.ALERT_ACK, payload={})
        response = handlers.handle_alert_ack(msg)
        
        assert response is not None
        assert response.type == MessageType.ERROR
        assert "Missing alert_id" in response.payload["error"]


class TestStateSync:
    """Tests for state synchronization."""
    
    def test_handle_request_state(self):
        """Test state request handler."""
        handlers = MessageHandlers()
        
        msg = Message.create(MessageType.REQUEST_STATE)
        response = handlers.handle_request_state(msg)
        
        assert response is not None
        assert response.type == MessageType.STATE_SYNC
        assert "backtest_status" in response.payload
        assert "timestamp" in response.payload
    
    def test_broadcast_update(self):
        """Test broadcast update."""
        handlers = MessageHandlers()
        
        broadcast_called = []
        def mock_broadcast(msg: Message):
            broadcast_called.append(msg)
        
        handlers.set_broadcast_callback(mock_broadcast)
        handlers.broadcast_update(MessageType.TICK_UPDATE, {"price": 100})
        
        assert len(broadcast_called) == 1
        assert broadcast_called[0].type == MessageType.TICK_UPDATE
        assert broadcast_called[0].payload["price"] == 100
