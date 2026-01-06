"""
Titan-Quant WebSocket Server

This module implements the WebSocket communication layer for the Titan-Quant system.
The server provides real-time bidirectional communication between the Core Engine
(Python daemon) and UI Client (Electron + React).

Requirements:
    - 1.1: THE Core_Engine SHALL 作为独立守护进程运行，与 UI_Client 通过 WebSocket/ZMQ 通信
    - 1.3: WHEN UI_Client 崩溃或断开连接, THEN THE Core_Engine SHALL 继续执行当前回测任务并保持状态
    - 1.4: WHEN UI_Client 重新连接, THEN THE Core_Engine SHALL 恢复状态同步并继续提供数据流

Features:
    - WebSocket server with message routing
    - Heartbeat detection for connection health
    - Client reconnection with state synchronization
    - Thread-safe message handling
    - Graceful shutdown support
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from core.exceptions import EngineError, ErrorCodes


logger = logging.getLogger(__name__)


class MessageType(Enum):
    """
    WebSocket message types.
    
    Defines all supported message types for client-server communication.
    """
    # Control messages
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    ERROR = "error"
    
    # Backtest control
    START_BACKTEST = "start_backtest"
    PAUSE = "pause"
    RESUME = "resume"
    STEP = "step"
    STOP = "stop"
    
    # Data push
    TICK_UPDATE = "tick_update"
    BAR_UPDATE = "bar_update"
    POSITION_UPDATE = "position_update"
    ACCOUNT_UPDATE = "account_update"
    TRADE_UPDATE = "trade_update"
    
    # Strategy operations
    LOAD_STRATEGY = "load_strategy"
    RELOAD_STRATEGY = "reload_strategy"
    UPDATE_PARAMS = "update_params"
    
    # Manual trading
    MANUAL_ORDER = "manual_order"
    CANCEL_ORDER = "cancel_order"
    CLOSE_ALL = "close_all"
    
    # Snapshot
    SAVE_SNAPSHOT = "save_snapshot"
    LOAD_SNAPSHOT = "load_snapshot"
    
    # Alert
    ALERT = "alert"
    ALERT_ACK = "alert_ack"
    
    # State sync
    STATE_SYNC = "state_sync"
    REQUEST_STATE = "request_state"
    
    # Response
    RESPONSE = "response"


@dataclass
class Message:
    """
    WebSocket message structure.
    
    Attributes:
        id: Unique message identifier
        type: Message type
        timestamp: Message timestamp (Unix milliseconds)
        payload: Message payload data
        client_id: Client identifier (for server-side tracking)
    """
    id: str
    type: MessageType
    timestamp: int
    payload: Dict[str, Any] = field(default_factory=dict)
    client_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], client_id: Optional[str] = None) -> Message:
        """Create Message from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MessageType(data["type"]),
            timestamp=data.get("timestamp", int(time.time() * 1000)),
            payload=data.get("payload", {}),
            client_id=client_id,
        )
    
    @classmethod
    def from_json(cls, json_str: str, client_id: Optional[str] = None) -> Message:
        """Create Message from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data, client_id)
    
    @classmethod
    def create(
        cls,
        msg_type: MessageType,
        payload: Optional[Dict[str, Any]] = None,
        msg_id: Optional[str] = None,
    ) -> Message:
        """Create a new message with auto-generated ID and timestamp."""
        return cls(
            id=msg_id or str(uuid.uuid4()),
            type=msg_type,
            timestamp=int(time.time() * 1000),
            payload=payload or {},
        )


@dataclass
class ClientInfo:
    """
    Connected client information.
    
    Attributes:
        client_id: Unique client identifier
        websocket: WebSocket connection
        connected_at: Connection timestamp
        last_heartbeat: Last heartbeat timestamp
        user_id: Associated user ID (if authenticated)
        subscriptions: Set of subscribed event types
    """
    client_id: str
    websocket: Any  # WebSocketServerProtocol
    connected_at: datetime
    last_heartbeat: datetime
    user_id: Optional[str] = None
    subscriptions: Set[str] = field(default_factory=set)
    
    def is_alive(self, timeout_seconds: float = 60.0) -> bool:
        """Check if client connection is still alive based on heartbeat."""
        elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
        return elapsed < timeout_seconds


# Type alias for message handlers
MessageHandler = Callable[[Message], Optional[Message]]


@dataclass
class ServerConfig:
    """
    WebSocket server configuration.
    
    Attributes:
        host: Server host address
        port: Server port number
        heartbeat_interval: Heartbeat interval in seconds
        heartbeat_timeout: Heartbeat timeout in seconds
        max_message_size: Maximum message size in bytes
        reconnect_grace_period: Grace period for reconnection in seconds
    """
    host: str = "127.0.0.1"
    port: int = 8765
    heartbeat_interval: float = 30.0
    heartbeat_timeout: float = 60.0
    max_message_size: int = 10 * 1024 * 1024  # 10MB
    reconnect_grace_period: float = 300.0  # 5 minutes


class IWebSocketServer(ABC):
    """
    Abstract interface for the WebSocket Server.
    
    The WebSocket Server provides real-time bidirectional communication
    between the Core Engine and UI Client.
    """
    
    @abstractmethod
    async def start(self) -> None:
        """Start the WebSocket server."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the WebSocket server."""
        pass
    
    @abstractmethod
    def register_handler(self, msg_type: MessageType, handler: MessageHandler) -> None:
        """Register a message handler for a specific message type."""
        pass
    
    @abstractmethod
    def unregister_handler(self, msg_type: MessageType) -> None:
        """Unregister a message handler."""
        pass
    
    @abstractmethod
    async def broadcast(self, message: Message) -> int:
        """Broadcast a message to all connected clients."""
        pass
    
    @abstractmethod
    async def send_to_client(self, client_id: str, message: Message) -> bool:
        """Send a message to a specific client."""
        pass
    
    @abstractmethod
    def get_connected_clients(self) -> List[str]:
        """Get list of connected client IDs."""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Check if server is running."""
        pass



class WebSocketServer(IWebSocketServer):
    """
    Implementation of the WebSocket Server.
    
    Provides real-time bidirectional communication with features:
    - Message routing to registered handlers
    - Heartbeat detection for connection health
    - Client reconnection with state synchronization
    - Thread-safe operations
    - Graceful shutdown
    
    Example:
        >>> server = WebSocketServer(ServerConfig(host="127.0.0.1", port=8765))
        >>> server.register_handler(MessageType.START_BACKTEST, handle_start_backtest)
        >>> await server.start()
        >>> # Server is now running and accepting connections
        >>> await server.stop()
    """
    
    def __init__(self, config: Optional[ServerConfig] = None) -> None:
        """
        Initialize the WebSocket Server.
        
        Args:
            config: Server configuration. Uses defaults if not provided.
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets library is required. Install with: pip install websockets"
            )
        
        self._config = config or ServerConfig()
        self._lock = threading.RLock()
        
        # Server state
        self._server: Optional[Any] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Connected clients: client_id -> ClientInfo
        self._clients: Dict[str, ClientInfo] = {}
        
        # Message handlers: MessageType -> handler
        self._handlers: Dict[MessageType, MessageHandler] = {}
        
        # Disconnected client states for reconnection
        # client_id -> (disconnect_time, state_data)
        self._disconnected_states: Dict[str, tuple[datetime, Dict[str, Any]]] = {}
        
        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # State provider callback for state sync
        self._state_provider: Optional[Callable[[], Dict[str, Any]]] = None
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """Register default message handlers."""
        self._handlers[MessageType.HEARTBEAT] = self._handle_heartbeat
        self._handlers[MessageType.REQUEST_STATE] = self._handle_request_state
    
    def set_state_provider(self, provider: Callable[[], Dict[str, Any]]) -> None:
        """
        Set the state provider callback for state synchronization.
        
        Args:
            provider: Callback that returns current system state.
        """
        self._state_provider = provider
    
    async def start(self) -> None:
        """
        Start the WebSocket server.
        
        Starts listening for connections and begins heartbeat monitoring.
        
        Raises:
            EngineError: If server fails to start.
        """
        if self._running:
            logger.warning("WebSocket server is already running")
            return
        
        try:
            self._loop = asyncio.get_event_loop()
            
            # Start the WebSocket server
            self._server = await websockets.serve(
                self._handle_connection,
                self._config.host,
                self._config.port,
                max_size=self._config.max_message_size,
            )
            
            self._running = True
            
            # Start heartbeat monitoring
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            logger.info(
                f"WebSocket server started on ws://{self._config.host}:{self._config.port}"
            )
            
        except Exception as e:
            raise EngineError(
                message=f"Failed to start WebSocket server: {e}",
                error_code=ErrorCodes.ENGINE_INIT_FAILED,
                details={"host": self._config.host, "port": self._config.port},
            )
    
    async def stop(self) -> None:
        """
        Stop the WebSocket server gracefully.
        
        Closes all client connections and stops the server.
        """
        if not self._running:
            return
        
        self._running = False
        
        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close all client connections
        with self._lock:
            for client_id, client_info in list(self._clients.items()):
                try:
                    await client_info.websocket.close(1001, "Server shutting down")
                except Exception:
                    pass
            self._clients.clear()
        
        # Close the server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        
        logger.info("WebSocket server stopped")
    
    def register_handler(self, msg_type: MessageType, handler: MessageHandler) -> None:
        """
        Register a message handler for a specific message type.
        
        Args:
            msg_type: The message type to handle.
            handler: The handler function. Should accept a Message and
                     optionally return a response Message.
        """
        with self._lock:
            self._handlers[msg_type] = handler
            logger.debug(f"Registered handler for {msg_type.value}")
    
    def unregister_handler(self, msg_type: MessageType) -> None:
        """
        Unregister a message handler.
        
        Args:
            msg_type: The message type to unregister.
        """
        with self._lock:
            if msg_type in self._handlers:
                del self._handlers[msg_type]
                logger.debug(f"Unregistered handler for {msg_type.value}")
    
    async def broadcast(self, message: Message) -> int:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast.
        
        Returns:
            Number of clients the message was sent to.
        """
        sent_count = 0
        json_msg = message.to_json()
        
        with self._lock:
            clients = list(self._clients.values())
        
        for client_info in clients:
            try:
                await client_info.websocket.send(json_msg)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to client {client_info.client_id}: {e}")
        
        return sent_count
    
    async def send_to_client(self, client_id: str, message: Message) -> bool:
        """
        Send a message to a specific client.
        
        Args:
            client_id: The target client ID.
            message: The message to send.
        
        Returns:
            True if message was sent successfully.
        """
        with self._lock:
            client_info = self._clients.get(client_id)
        
        if not client_info:
            logger.warning(f"Client not found: {client_id}")
            return False
        
        try:
            await client_info.websocket.send(message.to_json())
            return True
        except Exception as e:
            logger.warning(f"Failed to send to client {client_id}: {e}")
            return False
    
    def get_connected_clients(self) -> List[str]:
        """Get list of connected client IDs."""
        with self._lock:
            return list(self._clients.keys())
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handle a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection.
        """
        client_id = str(uuid.uuid4())
        client_info = ClientInfo(
            client_id=client_id,
            websocket=websocket,
            connected_at=datetime.now(),
            last_heartbeat=datetime.now(),
        )
        
        # Register client
        with self._lock:
            self._clients[client_id] = client_info
        
        logger.info(f"Client connected: {client_id}")
        
        # Send connect acknowledgment with client ID
        connect_msg = Message.create(
            MessageType.CONNECT,
            payload={"client_id": client_id, "server_time": int(time.time() * 1000)},
        )
        
        try:
            await websocket.send(connect_msg.to_json())
            
            # Check for reconnection state
            await self._handle_reconnection(client_id)
            
            # Handle messages
            async for raw_message in websocket:
                await self._process_message(client_id, raw_message)
                
        except ConnectionClosed as e:
            logger.info(f"Client disconnected: {client_id} (code={e.code})")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            # Save state for potential reconnection
            await self._save_disconnect_state(client_id)
            
            # Unregister client
            with self._lock:
                self._clients.pop(client_id, None)
            
            logger.info(f"Client removed: {client_id}")
    
    async def _process_message(self, client_id: str, raw_message: str) -> None:
        """
        Process an incoming message from a client.
        
        Args:
            client_id: The client ID.
            raw_message: The raw message string.
        """
        try:
            message = Message.from_json(raw_message, client_id)
            
            # Update heartbeat timestamp
            with self._lock:
                if client_id in self._clients:
                    self._clients[client_id].last_heartbeat = datetime.now()
            
            # Find and execute handler
            handler = self._handlers.get(message.type)
            
            if handler:
                try:
                    response = handler(message)
                    
                    # Send response if handler returned one
                    if response:
                        await self.send_to_client(client_id, response)
                        
                except Exception as e:
                    logger.error(f"Handler error for {message.type.value}: {e}")
                    error_msg = Message.create(
                        MessageType.ERROR,
                        payload={
                            "error": str(e),
                            "original_message_id": message.id,
                            "original_type": message.type.value,
                        },
                    )
                    await self.send_to_client(client_id, error_msg)
            else:
                logger.warning(f"No handler for message type: {message.type.value}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from client {client_id}: {e}")
        except ValueError as e:
            logger.error(f"Invalid message from client {client_id}: {e}")
    
    async def _handle_reconnection(self, client_id: str) -> None:
        """
        Handle client reconnection with state synchronization.
        
        Requirement 1.4: WHEN UI_Client 重新连接, THEN THE Core_Engine SHALL 
        恢复状态同步并继续提供数据流
        
        Args:
            client_id: The reconnected client ID.
        """
        # Check if we have state to sync
        if self._state_provider:
            try:
                state = self._state_provider()
                sync_msg = Message.create(
                    MessageType.STATE_SYNC,
                    payload=state,
                )
                await self.send_to_client(client_id, sync_msg)
                logger.info(f"Sent state sync to client {client_id}")
            except Exception as e:
                logger.error(f"Failed to sync state to client {client_id}: {e}")
    
    async def _save_disconnect_state(self, client_id: str) -> None:
        """
        Save client state for potential reconnection.
        
        Requirement 1.3: WHEN UI_Client 崩溃或断开连接, THEN THE Core_Engine SHALL 
        继续执行当前回测任务并保持状态
        
        Args:
            client_id: The disconnecting client ID.
        """
        with self._lock:
            client_info = self._clients.get(client_id)
            if client_info:
                state_data = {
                    "user_id": client_info.user_id,
                    "subscriptions": list(client_info.subscriptions),
                    "connected_at": client_info.connected_at.isoformat(),
                }
                self._disconnected_states[client_id] = (datetime.now(), state_data)
        
        # Clean up old disconnected states
        self._cleanup_disconnected_states()
    
    def _cleanup_disconnected_states(self) -> None:
        """Clean up expired disconnected client states."""
        now = datetime.now()
        grace_period = self._config.reconnect_grace_period
        
        with self._lock:
            expired = [
                cid for cid, (disconnect_time, _) in self._disconnected_states.items()
                if (now - disconnect_time).total_seconds() > grace_period
            ]
            for cid in expired:
                del self._disconnected_states[cid]
    
    async def _heartbeat_loop(self) -> None:
        """
        Background task for heartbeat monitoring.
        
        Sends heartbeat messages and checks for dead connections.
        """
        while self._running:
            try:
                await asyncio.sleep(self._config.heartbeat_interval)
                
                if not self._running:
                    break
                
                # Send heartbeat to all clients
                heartbeat_msg = Message.create(
                    MessageType.HEARTBEAT,
                    payload={"server_time": int(time.time() * 1000)},
                )
                
                with self._lock:
                    clients = list(self._clients.items())
                
                for client_id, client_info in clients:
                    # Check if client is still alive
                    if not client_info.is_alive(self._config.heartbeat_timeout):
                        logger.warning(f"Client {client_id} heartbeat timeout")
                        try:
                            await client_info.websocket.close(1001, "Heartbeat timeout")
                        except Exception:
                            pass
                        continue
                    
                    # Send heartbeat
                    try:
                        await client_info.websocket.send(heartbeat_msg.to_json())
                    except Exception as e:
                        logger.warning(f"Failed to send heartbeat to {client_id}: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    def _handle_heartbeat(self, message: Message) -> Optional[Message]:
        """Handle heartbeat message from client."""
        return Message.create(
            MessageType.HEARTBEAT_ACK,
            payload={
                "client_time": message.payload.get("client_time"),
                "server_time": int(time.time() * 1000),
            },
            msg_id=message.id,
        )
    
    def _handle_request_state(self, message: Message) -> Optional[Message]:
        """Handle state request from client."""
        if self._state_provider:
            try:
                state = self._state_provider()
                return Message.create(
                    MessageType.STATE_SYNC,
                    payload=state,
                    msg_id=message.id,
                )
            except Exception as e:
                logger.error(f"Failed to get state: {e}")
                return Message.create(
                    MessageType.ERROR,
                    payload={"error": str(e)},
                    msg_id=message.id,
                )
        return None



class MessageRouter:
    """
    Message router for organizing and dispatching message handlers.
    
    Provides a convenient way to register handlers and integrate with
    the WebSocket server.
    
    Example:
        >>> router = MessageRouter()
        >>> @router.handler(MessageType.START_BACKTEST)
        ... def handle_start(msg: Message) -> Optional[Message]:
        ...     # Handle start backtest
        ...     return Message.create(MessageType.RESPONSE, {"status": "started"})
        >>> server.register_router(router)
    """
    
    def __init__(self) -> None:
        """Initialize the message router."""
        self._handlers: Dict[MessageType, MessageHandler] = {}
    
    def handler(self, msg_type: MessageType) -> Callable[[MessageHandler], MessageHandler]:
        """
        Decorator for registering message handlers.
        
        Args:
            msg_type: The message type to handle.
        
        Returns:
            Decorator function.
        """
        def decorator(func: MessageHandler) -> MessageHandler:
            self._handlers[msg_type] = func
            return func
        return decorator
    
    def register(self, msg_type: MessageType, handler: MessageHandler) -> None:
        """
        Register a handler for a message type.
        
        Args:
            msg_type: The message type.
            handler: The handler function.
        """
        self._handlers[msg_type] = handler
    
    def get_handlers(self) -> Dict[MessageType, MessageHandler]:
        """Get all registered handlers."""
        return self._handlers.copy()
    
    def apply_to_server(self, server: WebSocketServer) -> None:
        """
        Apply all handlers to a WebSocket server.
        
        Args:
            server: The WebSocket server to register handlers with.
        """
        for msg_type, handler in self._handlers.items():
            server.register_handler(msg_type, handler)


def run_server(
    config: Optional[ServerConfig] = None,
    handlers: Optional[Dict[MessageType, MessageHandler]] = None,
    state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
) -> WebSocketServer:
    """
    Create and run a WebSocket server.
    
    This is a convenience function for creating and starting a server
    with the specified configuration and handlers.
    
    Args:
        config: Server configuration.
        handlers: Dictionary of message handlers.
        state_provider: Callback for state synchronization.
    
    Returns:
        The running WebSocket server instance.
    
    Example:
        >>> async def main():
        ...     server = run_server(
        ...         config=ServerConfig(port=8765),
        ...         handlers={MessageType.START_BACKTEST: handle_start},
        ...     )
        ...     await server.start()
        ...     # Server is running
        ...     await server.stop()
    """
    server = WebSocketServer(config)
    
    if handlers:
        for msg_type, handler in handlers.items():
            server.register_handler(msg_type, handler)
    
    if state_provider:
        server.set_state_provider(state_provider)
    
    return server


async def run_server_async(
    config: Optional[ServerConfig] = None,
    handlers: Optional[Dict[MessageType, MessageHandler]] = None,
    state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    shutdown_event: Optional[asyncio.Event] = None,
) -> None:
    """
    Run a WebSocket server until shutdown.
    
    This is a convenience function for running a server that blocks
    until a shutdown event is set.
    
    Args:
        config: Server configuration.
        handlers: Dictionary of message handlers.
        state_provider: Callback for state synchronization.
        shutdown_event: Event to signal shutdown. If None, runs forever.
    
    Example:
        >>> async def main():
        ...     shutdown = asyncio.Event()
        ...     # Run server in background
        ...     task = asyncio.create_task(run_server_async(
        ...         config=ServerConfig(port=8765),
        ...         shutdown_event=shutdown,
        ...     ))
        ...     # Do other work...
        ...     shutdown.set()  # Signal shutdown
        ...     await task
    """
    server = run_server(config, handlers, state_provider)
    
    try:
        await server.start()
        
        if shutdown_event:
            await shutdown_event.wait()
        else:
            # Run forever
            while True:
                await asyncio.sleep(1)
                
    finally:
        await server.stop()


class ServerThread:
    """
    Helper class to run WebSocket server in a separate thread.
    
    Useful for integrating the WebSocket server with synchronous code
    or running alongside other async tasks.
    
    Example:
        >>> server_thread = ServerThread(ServerConfig(port=8765))
        >>> server_thread.start()
        >>> # Server is running in background
        >>> server_thread.broadcast_sync(Message.create(MessageType.TICK_UPDATE, {...}))
        >>> server_thread.stop()
    """
    
    def __init__(
        self,
        config: Optional[ServerConfig] = None,
        handlers: Optional[Dict[MessageType, MessageHandler]] = None,
        state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> None:
        """
        Initialize the server thread.
        
        Args:
            config: Server configuration.
            handlers: Dictionary of message handlers.
            state_provider: Callback for state synchronization.
        """
        self._config = config
        self._handlers = handlers or {}
        self._state_provider = state_provider
        
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[WebSocketServer] = None
        self._shutdown_event: Optional[asyncio.Event] = None
        self._started = threading.Event()
    
    def start(self) -> None:
        """Start the server in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        # Wait for server to start
        self._started.wait(timeout=10.0)
    
    def stop(self) -> None:
        """Stop the server and wait for thread to finish."""
        if self._shutdown_event and self._loop:
            self._loop.call_soon_threadsafe(self._shutdown_event.set)
        
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
    
    def _run_loop(self) -> None:
        """Run the event loop in the thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        self._shutdown_event = asyncio.Event()
        self._server = WebSocketServer(self._config)
        
        for msg_type, handler in self._handlers.items():
            self._server.register_handler(msg_type, handler)
        
        if self._state_provider:
            self._server.set_state_provider(self._state_provider)
        
        async def run():
            await self._server.start()
            self._started.set()
            await self._shutdown_event.wait()
            await self._server.stop()
        
        try:
            self._loop.run_until_complete(run())
        finally:
            self._loop.close()
    
    def broadcast_sync(self, message: Message) -> int:
        """
        Broadcast a message synchronously from another thread.
        
        Args:
            message: The message to broadcast.
        
        Returns:
            Number of clients the message was sent to.
        """
        if not self._server or not self._loop:
            return 0
        
        future = asyncio.run_coroutine_threadsafe(
            self._server.broadcast(message),
            self._loop,
        )
        return future.result(timeout=5.0)
    
    def send_to_client_sync(self, client_id: str, message: Message) -> bool:
        """
        Send a message to a specific client synchronously.
        
        Args:
            client_id: The target client ID.
            message: The message to send.
        
        Returns:
            True if message was sent successfully.
        """
        if not self._server or not self._loop:
            return False
        
        future = asyncio.run_coroutine_threadsafe(
            self._server.send_to_client(client_id, message),
            self._loop,
        )
        return future.result(timeout=5.0)
    
    def get_connected_clients(self) -> List[str]:
        """Get list of connected client IDs."""
        if not self._server:
            return []
        return self._server.get_connected_clients()
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._server is not None and self._server.is_running()
    
    def register_handler(self, msg_type: MessageType, handler: MessageHandler) -> None:
        """Register a message handler."""
        self._handlers[msg_type] = handler
        if self._server:
            self._server.register_handler(msg_type, handler)


__all__ = [
    # Enums
    "MessageType",
    # Data classes
    "Message",
    "ClientInfo",
    "ServerConfig",
    # Interfaces
    "IWebSocketServer",
    # Implementations
    "WebSocketServer",
    "MessageRouter",
    "ServerThread",
    # Functions
    "run_server",
    "run_server_async",
    # Type aliases
    "MessageHandler",
]
