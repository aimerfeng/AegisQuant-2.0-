"""
Tests for Titan-Quant WebSocket Server

Tests the WebSocket communication layer including:
- Server startup and shutdown
- Message routing
- Heartbeat detection
- Client connection handling
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Check if websockets is available
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from core.server import (
    Message,
    MessageType,
    ServerConfig,
    WebSocketServer,
    MessageRouter,
    ClientInfo,
    ServerThread,
    run_server,
)


class TestMessage:
    """Tests for Message class."""
    
    def test_create_message(self):
        """Test creating a message with auto-generated ID and timestamp."""
        msg = Message.create(
            MessageType.START_BACKTEST,
            payload={"strategy_id": "test-123"},
        )
        
        assert msg.id is not None
        assert msg.type == MessageType.START_BACKTEST
        assert msg.timestamp > 0
        assert msg.payload == {"strategy_id": "test-123"}
    
    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        msg = Message(
            id="msg-001",
            type=MessageType.TICK_UPDATE,
            timestamp=1704067200000,
            payload={"price": 100.5},
        )
        
        result = msg.to_dict()
        
        assert result["id"] == "msg-001"
        assert result["type"] == "tick_update"
        assert result["timestamp"] == 1704067200000
        assert result["payload"] == {"price": 100.5}
    
    def test_message_to_json(self):
        """Test converting message to JSON string."""
        msg = Message(
            id="msg-001",
            type=MessageType.HEARTBEAT,
            timestamp=1704067200000,
            payload={},
        )
        
        json_str = msg.to_json()
        data = json.loads(json_str)
        
        assert data["id"] == "msg-001"
        assert data["type"] == "heartbeat"
    
    def test_message_from_dict(self):
        """Test creating message from dictionary."""
        data = {
            "id": "msg-002",
            "type": "pause",
            "timestamp": 1704067200000,
            "payload": {"reason": "user_request"},
        }
        
        msg = Message.from_dict(data)
        
        assert msg.id == "msg-002"
        assert msg.type == MessageType.PAUSE
        assert msg.timestamp == 1704067200000
        assert msg.payload == {"reason": "user_request"}
    
    def test_message_from_json(self):
        """Test creating message from JSON string."""
        json_str = '{"id": "msg-003", "type": "resume", "timestamp": 1704067200000, "payload": {}}'
        
        msg = Message.from_json(json_str, client_id="client-001")
        
        assert msg.id == "msg-003"
        assert msg.type == MessageType.RESUME
        assert msg.client_id == "client-001"
    
    def test_message_from_dict_with_defaults(self):
        """Test creating message with missing optional fields."""
        data = {"type": "step"}
        
        msg = Message.from_dict(data)
        
        assert msg.id is not None
        assert msg.type == MessageType.STEP
        assert msg.timestamp > 0
        assert msg.payload == {}


class TestServerConfig:
    """Tests for ServerConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ServerConfig()
        
        assert config.host == "127.0.0.1"
        assert config.port == 8765
        assert config.heartbeat_interval == 30.0
        assert config.heartbeat_timeout == 60.0
        assert config.max_message_size == 10 * 1024 * 1024
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ServerConfig(
            host="0.0.0.0",
            port=9000,
            heartbeat_interval=15.0,
        )
        
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.heartbeat_interval == 15.0


class TestClientInfo:
    """Tests for ClientInfo class."""
    
    def test_client_info_creation(self):
        """Test creating client info."""
        now = datetime.now()
        client = ClientInfo(
            client_id="client-001",
            websocket=MagicMock(),
            connected_at=now,
            last_heartbeat=now,
        )
        
        assert client.client_id == "client-001"
        assert client.connected_at == now
        assert client.subscriptions == set()
    
    def test_client_is_alive(self):
        """Test client alive check."""
        now = datetime.now()
        client = ClientInfo(
            client_id="client-001",
            websocket=MagicMock(),
            connected_at=now,
            last_heartbeat=now,
        )
        
        assert client.is_alive(timeout_seconds=60.0) is True


class TestMessageRouter:
    """Tests for MessageRouter class."""
    
    def test_register_handler(self):
        """Test registering a handler."""
        router = MessageRouter()
        
        def handler(msg: Message) -> Optional[Message]:
            return None
        
        router.register(MessageType.START_BACKTEST, handler)
        
        handlers = router.get_handlers()
        assert MessageType.START_BACKTEST in handlers
        assert handlers[MessageType.START_BACKTEST] == handler
    
    def test_handler_decorator(self):
        """Test handler decorator."""
        router = MessageRouter()
        
        @router.handler(MessageType.PAUSE)
        def handle_pause(msg: Message) -> Optional[Message]:
            return Message.create(MessageType.RESPONSE, {"status": "paused"})
        
        handlers = router.get_handlers()
        assert MessageType.PAUSE in handlers
    
    def test_apply_to_server(self):
        """Test applying handlers to server."""
        if not WEBSOCKETS_AVAILABLE:
            pytest.skip("websockets not available")
        
        router = MessageRouter()
        
        @router.handler(MessageType.STEP)
        def handle_step(msg: Message) -> Optional[Message]:
            return None
        
        server = WebSocketServer()
        router.apply_to_server(server)
        
        # Handler should be registered
        assert MessageType.STEP in server._handlers


@pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not available")
class TestWebSocketServer:
    """Tests for WebSocketServer class."""
    
    def test_server_creation(self):
        """Test creating a WebSocket server."""
        config = ServerConfig(host="127.0.0.1", port=8766)
        server = WebSocketServer(config)
        
        assert server._config.host == "127.0.0.1"
        assert server._config.port == 8766
        assert server.is_running() is False
    
    def test_register_handler(self):
        """Test registering a message handler."""
        server = WebSocketServer()
        
        def handler(msg: Message) -> Optional[Message]:
            return None
        
        server.register_handler(MessageType.MANUAL_ORDER, handler)
        
        assert MessageType.MANUAL_ORDER in server._handlers
    
    def test_unregister_handler(self):
        """Test unregistering a message handler."""
        server = WebSocketServer()
        
        def handler(msg: Message) -> Optional[Message]:
            return None
        
        server.register_handler(MessageType.CANCEL_ORDER, handler)
        server.unregister_handler(MessageType.CANCEL_ORDER)
        
        assert MessageType.CANCEL_ORDER not in server._handlers
    
    def test_get_connected_clients_empty(self):
        """Test getting connected clients when none connected."""
        server = WebSocketServer()
        
        clients = server.get_connected_clients()
        
        assert clients == []
    
    def test_set_state_provider(self):
        """Test setting state provider."""
        server = WebSocketServer()
        
        def state_provider() -> Dict[str, Any]:
            return {"status": "running"}
        
        server.set_state_provider(state_provider)
        
        assert server._state_provider == state_provider
    
    def test_handle_heartbeat(self):
        """Test heartbeat handler."""
        server = WebSocketServer()
        
        msg = Message.create(
            MessageType.HEARTBEAT,
            payload={"client_time": 1704067200000},
        )
        
        response = server._handle_heartbeat(msg)
        
        assert response is not None
        assert response.type == MessageType.HEARTBEAT_ACK
        assert "server_time" in response.payload
        assert response.payload["client_time"] == 1704067200000
    
    def test_handle_request_state_with_provider(self):
        """Test state request handler with provider."""
        server = WebSocketServer()
        
        def state_provider() -> Dict[str, Any]:
            return {"backtest_status": "running", "progress": 50}
        
        server.set_state_provider(state_provider)
        
        msg = Message.create(MessageType.REQUEST_STATE)
        response = server._handle_request_state(msg)
        
        assert response is not None
        assert response.type == MessageType.STATE_SYNC
        assert response.payload["backtest_status"] == "running"
        assert response.payload["progress"] == 50
    
    def test_handle_request_state_without_provider(self):
        """Test state request handler without provider."""
        server = WebSocketServer()
        
        msg = Message.create(MessageType.REQUEST_STATE)
        response = server._handle_request_state(msg)
        
        assert response is None


@pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not available")
class TestRunServer:
    """Tests for run_server function."""
    
    def test_run_server_creates_server(self):
        """Test that run_server creates a server instance."""
        config = ServerConfig(port=8767)
        
        server = run_server(config)
        
        assert isinstance(server, WebSocketServer)
        assert server._config.port == 8767
    
    def test_run_server_with_handlers(self):
        """Test run_server with handlers."""
        def handler(msg: Message) -> Optional[Message]:
            return None
        
        handlers = {MessageType.LOAD_STRATEGY: handler}
        server = run_server(handlers=handlers)
        
        assert MessageType.LOAD_STRATEGY in server._handlers
    
    def test_run_server_with_state_provider(self):
        """Test run_server with state provider."""
        def state_provider() -> Dict[str, Any]:
            return {"status": "idle"}
        
        server = run_server(state_provider=state_provider)
        
        assert server._state_provider == state_provider


class TestMessageTypes:
    """Tests for MessageType enum."""
    
    def test_all_message_types_have_values(self):
        """Test that all message types have string values."""
        for msg_type in MessageType:
            assert isinstance(msg_type.value, str)
            assert len(msg_type.value) > 0
    
    def test_control_message_types(self):
        """Test control message types."""
        assert MessageType.CONNECT.value == "connect"
        assert MessageType.DISCONNECT.value == "disconnect"
        assert MessageType.HEARTBEAT.value == "heartbeat"
    
    def test_backtest_message_types(self):
        """Test backtest control message types."""
        assert MessageType.START_BACKTEST.value == "start_backtest"
        assert MessageType.PAUSE.value == "pause"
        assert MessageType.RESUME.value == "resume"
        assert MessageType.STEP.value == "step"
        assert MessageType.STOP.value == "stop"
    
    def test_data_push_message_types(self):
        """Test data push message types."""
        assert MessageType.TICK_UPDATE.value == "tick_update"
        assert MessageType.BAR_UPDATE.value == "bar_update"
        assert MessageType.POSITION_UPDATE.value == "position_update"
        assert MessageType.ACCOUNT_UPDATE.value == "account_update"
        assert MessageType.TRADE_UPDATE.value == "trade_update"
    
    def test_strategy_message_types(self):
        """Test strategy operation message types."""
        assert MessageType.LOAD_STRATEGY.value == "load_strategy"
        assert MessageType.RELOAD_STRATEGY.value == "reload_strategy"
        assert MessageType.UPDATE_PARAMS.value == "update_params"
    
    def test_manual_trading_message_types(self):
        """Test manual trading message types."""
        assert MessageType.MANUAL_ORDER.value == "manual_order"
        assert MessageType.CANCEL_ORDER.value == "cancel_order"
        assert MessageType.CLOSE_ALL.value == "close_all"
    
    def test_snapshot_message_types(self):
        """Test snapshot message types."""
        assert MessageType.SAVE_SNAPSHOT.value == "save_snapshot"
        assert MessageType.LOAD_SNAPSHOT.value == "load_snapshot"
    
    def test_alert_message_types(self):
        """Test alert message types."""
        assert MessageType.ALERT.value == "alert"
        assert MessageType.ALERT_ACK.value == "alert_ack"


@pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not available")
class TestWebSocketServerAsync:
    """Async tests for WebSocketServer."""
    
    @pytest.mark.asyncio
    async def test_server_start_stop(self):
        """Test starting and stopping the server."""
        # Use a high port number to avoid permission issues
        config = ServerConfig(host="127.0.0.1", port=49168)
        server = WebSocketServer(config)
        
        try:
            await server.start()
            assert server.is_running() is True
            
            await server.stop()
            assert server.is_running() is False
        except PermissionError:
            pytest.skip("Port permission denied - skipping network test")
        except OSError as e:
            if "address already in use" in str(e).lower() or "permission" in str(e).lower():
                pytest.skip(f"Port unavailable: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_broadcast_no_clients(self):
        """Test broadcasting with no connected clients."""
        config = ServerConfig(host="127.0.0.1", port=49169)
        server = WebSocketServer(config)
        
        try:
            await server.start()
            
            msg = Message.create(MessageType.TICK_UPDATE, {"price": 100})
            sent_count = await server.broadcast(msg)
            
            assert sent_count == 0
            
            await server.stop()
        except PermissionError:
            pytest.skip("Port permission denied - skipping network test")
        except OSError as e:
            if "address already in use" in str(e).lower() or "permission" in str(e).lower():
                pytest.skip(f"Port unavailable: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_send_to_nonexistent_client(self):
        """Test sending to a client that doesn't exist."""
        config = ServerConfig(host="127.0.0.1", port=49170)
        server = WebSocketServer(config)
        
        try:
            await server.start()
            
            msg = Message.create(MessageType.ACCOUNT_UPDATE, {"balance": 1000})
            result = await server.send_to_client("nonexistent-client", msg)
            
            assert result is False
            
            await server.stop()
        except PermissionError:
            pytest.skip("Port permission denied - skipping network test")
        except OSError as e:
            if "address already in use" in str(e).lower() or "permission" in str(e).lower():
                pytest.skip(f"Port unavailable: {e}")
            raise
