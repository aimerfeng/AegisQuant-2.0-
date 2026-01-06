"""
Titan-Quant Message Handlers

This module implements the message handlers for WebSocket communication.
Each handler processes a specific message type and returns an appropriate response.

Requirements:
    - 1.3: WHEN UI_Client 崩溃或断开连接, THEN THE Core_Engine SHALL 继续执行当前回测任务并保持状态
    - 1.4: WHEN UI_Client 重新连接, THEN THE Core_Engine SHALL 恢复状态同步并继续提供数据流

Features:
    - Backtest control handlers (start, pause, resume, step, stop)
    - Strategy operation handlers (load, reload, update params)
    - Manual trading handlers (order, cancel, close all)
    - Snapshot handlers (save, load)
    - Alert handlers (acknowledge)
    - State synchronization
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from core.server import Message, MessageType, MessageRouter
from core.exceptions import EngineError, StrategyError, SnapshotError, ErrorCodes

if TYPE_CHECKING:
    from core.engine.event_bus import EventBus
    from core.engine.replay import ReplayController, ReplayStatus
    from core.engine.snapshot import SnapshotManager
    from core.engine.matching import MatchingEngine
    from core.strategies.manager import StrategyManager


logger = logging.getLogger(__name__)


@dataclass
class SystemState:
    """
    Current system state for synchronization.
    
    Attributes:
        backtest_status: Current backtest status
        replay_status: Current replay controller status
        account: Current account state
        positions: Current positions
        strategies: Loaded strategies
        alerts: Pending alerts
    """
    backtest_status: str = "idle"
    replay_status: Optional[Dict[str, Any]] = None
    account: Optional[Dict[str, Any]] = None
    positions: List[Dict[str, Any]] = field(default_factory=list)
    strategies: List[Dict[str, Any]] = field(default_factory=list)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "backtest_status": self.backtest_status,
            "replay_status": self.replay_status,
            "account": self.account,
            "positions": self.positions,
            "strategies": self.strategies,
            "alerts": self.alerts,
            "timestamp": int(datetime.now().timestamp() * 1000),
        }


class MessageHandlers:
    """
    Collection of message handlers for the WebSocket server.
    
    This class provides handlers for all message types and integrates
    with the core engine components (EventBus, ReplayController, etc.).
    
    Example:
        >>> handlers = MessageHandlers()
        >>> handlers.set_replay_controller(replay_controller)
        >>> handlers.set_strategy_manager(strategy_manager)
        >>> router = handlers.create_router()
        >>> server.register_router(router)
    """
    
    def __init__(self) -> None:
        """Initialize the message handlers."""
        # Core components (set via setters)
        self._event_bus: Optional[Any] = None
        self._replay_controller: Optional[Any] = None
        self._snapshot_manager: Optional[Any] = None
        self._matching_engine: Optional[Any] = None
        self._strategy_manager: Optional[Any] = None
        
        # System state
        self._state = SystemState()
        
        # Pending alerts
        self._pending_alerts: Dict[str, Dict[str, Any]] = {}
        
        # Broadcast callback (set by server)
        self._broadcast_callback: Optional[Callable[[Message], None]] = None
    
    # Component setters
    def set_event_bus(self, event_bus: Any) -> None:
        """Set the event bus component."""
        self._event_bus = event_bus
    
    def set_replay_controller(self, controller: Any) -> None:
        """Set the replay controller component."""
        self._replay_controller = controller
    
    def set_snapshot_manager(self, manager: Any) -> None:
        """Set the snapshot manager component."""
        self._snapshot_manager = manager
    
    def set_matching_engine(self, engine: Any) -> None:
        """Set the matching engine component."""
        self._matching_engine = engine
    
    def set_strategy_manager(self, manager: Any) -> None:
        """Set the strategy manager component."""
        self._strategy_manager = manager
    
    def set_broadcast_callback(self, callback: Callable[[Message], None]) -> None:
        """Set the broadcast callback for pushing updates to clients."""
        self._broadcast_callback = callback
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current system state for synchronization.
        
        Returns:
            Dictionary containing current system state.
        """
        self._update_state()
        return self._state.to_dict()
    
    def _update_state(self) -> None:
        """Update internal state from components."""
        # Update replay status
        if self._replay_controller:
            try:
                status = self._replay_controller.get_status()
                self._state.replay_status = {
                    "state": status.state.value,
                    "speed": status.speed.value,
                    "current_time": status.current_time.isoformat(),
                    "current_index": status.current_index,
                    "event_sequence": status.event_sequence,
                    "total_events": status.total_events,
                    "progress_percent": status.progress_percent,
                }
                self._state.backtest_status = status.state.value
            except Exception as e:
                logger.warning(f"Failed to get replay status: {e}")
        
        # Update strategies
        if self._strategy_manager:
            try:
                strategies = self._strategy_manager.list_strategies()
                self._state.strategies = [s.to_dict() for s in strategies]
            except Exception as e:
                logger.warning(f"Failed to get strategies: {e}")
        
        # Update alerts
        self._state.alerts = list(self._pending_alerts.values())
    
    def create_router(self) -> MessageRouter:
        """
        Create a message router with all handlers registered.
        
        Returns:
            MessageRouter with all handlers.
        """
        router = MessageRouter()
        
        # Backtest control
        router.register(MessageType.START_BACKTEST, self.handle_start_backtest)
        router.register(MessageType.PAUSE, self.handle_pause)
        router.register(MessageType.RESUME, self.handle_resume)
        router.register(MessageType.STEP, self.handle_step)
        router.register(MessageType.STOP, self.handle_stop)
        
        # Strategy operations
        router.register(MessageType.LOAD_STRATEGY, self.handle_load_strategy)
        router.register(MessageType.RELOAD_STRATEGY, self.handle_reload_strategy)
        router.register(MessageType.UPDATE_PARAMS, self.handle_update_params)
        
        # Manual trading
        router.register(MessageType.MANUAL_ORDER, self.handle_manual_order)
        router.register(MessageType.CANCEL_ORDER, self.handle_cancel_order)
        router.register(MessageType.CLOSE_ALL, self.handle_close_all)
        
        # Snapshot
        router.register(MessageType.SAVE_SNAPSHOT, self.handle_save_snapshot)
        router.register(MessageType.LOAD_SNAPSHOT, self.handle_load_snapshot)
        
        # Alert
        router.register(MessageType.ALERT_ACK, self.handle_alert_ack)
        
        # State sync
        router.register(MessageType.REQUEST_STATE, self.handle_request_state)
        
        return router
    
    # Backtest control handlers
    def handle_start_backtest(self, msg: Message) -> Optional[Message]:
        """
        Handle start backtest request.
        
        Payload:
            strategy_id: str - Strategy to run
            start_date: str - Start date (ISO format)
            end_date: str - End date (ISO format)
            initial_capital: float - Initial capital
            matching_config: dict - Matching engine configuration
            replay_speed: float - Replay speed multiplier
        """
        payload = msg.payload
        
        try:
            # Validate required fields
            required = ["strategy_id", "start_date", "end_date"]
            for field in required:
                if field not in payload:
                    return self._error_response(msg.id, f"Missing required field: {field}")
            
            # TODO: Initialize backtest with provided configuration
            # This would involve:
            # 1. Loading the strategy
            # 2. Configuring the matching engine
            # 3. Setting up the replay controller
            # 4. Starting the backtest
            
            logger.info(f"Starting backtest: {payload}")
            
            return Message.create(
                MessageType.RESPONSE,
                payload={
                    "success": True,
                    "message": "Backtest started",
                    "backtest_id": payload.get("strategy_id"),
                },
                msg_id=msg.id,
            )
            
        except Exception as e:
            logger.error(f"Failed to start backtest: {e}")
            return self._error_response(msg.id, str(e))
    
    def handle_pause(self, msg: Message) -> Optional[Message]:
        """Handle pause request."""
        try:
            if self._replay_controller:
                success = self._replay_controller.pause()
                return Message.create(
                    MessageType.RESPONSE,
                    payload={"success": success, "message": "Paused" if success else "Failed to pause"},
                    msg_id=msg.id,
                )
            return self._error_response(msg.id, "Replay controller not available")
        except Exception as e:
            logger.error(f"Failed to pause: {e}")
            return self._error_response(msg.id, str(e))
    
    def handle_resume(self, msg: Message) -> Optional[Message]:
        """Handle resume request."""
        try:
            if self._replay_controller:
                success = self._replay_controller.resume()
                return Message.create(
                    MessageType.RESPONSE,
                    payload={"success": success, "message": "Resumed" if success else "Failed to resume"},
                    msg_id=msg.id,
                )
            return self._error_response(msg.id, "Replay controller not available")
        except Exception as e:
            logger.error(f"Failed to resume: {e}")
            return self._error_response(msg.id, str(e))
    
    def handle_step(self, msg: Message) -> Optional[Message]:
        """Handle single step request."""
        try:
            if self._replay_controller:
                success = self._replay_controller.step()
                status = self._replay_controller.get_status()
                return Message.create(
                    MessageType.RESPONSE,
                    payload={
                        "success": success,
                        "message": "Stepped" if success else "End of data",
                        "current_index": status.current_index,
                        "current_time": status.current_time.isoformat(),
                    },
                    msg_id=msg.id,
                )
            return self._error_response(msg.id, "Replay controller not available")
        except Exception as e:
            logger.error(f"Failed to step: {e}")
            return self._error_response(msg.id, str(e))
    
    def handle_stop(self, msg: Message) -> Optional[Message]:
        """Handle stop request."""
        try:
            if self._replay_controller:
                success = self._replay_controller.stop()
                return Message.create(
                    MessageType.RESPONSE,
                    payload={"success": success, "message": "Stopped" if success else "Failed to stop"},
                    msg_id=msg.id,
                )
            return self._error_response(msg.id, "Replay controller not available")
        except Exception as e:
            logger.error(f"Failed to stop: {e}")
            return self._error_response(msg.id, str(e))
    
    # Strategy operation handlers
    def handle_load_strategy(self, msg: Message) -> Optional[Message]:
        """
        Handle load strategy request.
        
        Payload:
            file_path: str - Path to strategy file
        """
        payload = msg.payload
        
        try:
            if not self._strategy_manager:
                return self._error_response(msg.id, "Strategy manager not available")
            
            file_path = payload.get("file_path")
            if not file_path:
                return self._error_response(msg.id, "Missing file_path")
            
            info = self._strategy_manager.load_strategy_file(file_path)
            
            return Message.create(
                MessageType.RESPONSE,
                payload={
                    "success": True,
                    "strategy_id": info.strategy_id,
                    "class_name": info.class_name,
                    "parameters": [p.to_dict() for p in info.parameters],
                },
                msg_id=msg.id,
            )
            
        except StrategyError as e:
            logger.error(f"Failed to load strategy: {e}")
            return self._error_response(msg.id, str(e), e.error_code)
        except Exception as e:
            logger.error(f"Failed to load strategy: {e}")
            return self._error_response(msg.id, str(e))
    
    def handle_reload_strategy(self, msg: Message) -> Optional[Message]:
        """
        Handle reload strategy request.
        
        Payload:
            strategy_id: str - Strategy to reload
            policy: str - Hot reload policy (reset, preserve, selective)
            preserve_vars: list - Variables to preserve (for selective)
        """
        payload = msg.payload
        
        try:
            if not self._strategy_manager:
                return self._error_response(msg.id, "Strategy manager not available")
            
            strategy_id = payload.get("strategy_id")
            if not strategy_id:
                return self._error_response(msg.id, "Missing strategy_id")
            
            from core.strategies.manager import HotReloadPolicy
            
            policy_str = payload.get("policy", "reset")
            policy = HotReloadPolicy(policy_str)
            preserve_vars = set(payload.get("preserve_vars", []))
            
            result = self._strategy_manager.hot_reload(strategy_id, policy, preserve_vars)
            
            return Message.create(
                MessageType.RESPONSE,
                payload={
                    "success": result.success,
                    "policy": result.policy.value,
                    "preserved_variables": result.preserved_variables,
                    "reset_variables": result.reset_variables,
                    "error_message": result.error_message,
                },
                msg_id=msg.id,
            )
            
        except StrategyError as e:
            logger.error(f"Failed to reload strategy: {e}")
            return self._error_response(msg.id, str(e), e.error_code)
        except Exception as e:
            logger.error(f"Failed to reload strategy: {e}")
            return self._error_response(msg.id, str(e))
    
    def handle_update_params(self, msg: Message) -> Optional[Message]:
        """
        Handle update parameters request.
        
        Payload:
            strategy_id: str - Strategy to update
            params: dict - Parameter values to set
        """
        payload = msg.payload
        
        try:
            if not self._strategy_manager:
                return self._error_response(msg.id, "Strategy manager not available")
            
            strategy_id = payload.get("strategy_id")
            params = payload.get("params", {})
            
            if not strategy_id:
                return self._error_response(msg.id, "Missing strategy_id")
            
            success = self._strategy_manager.set_parameters(strategy_id, params)
            
            return Message.create(
                MessageType.RESPONSE,
                payload={"success": success, "message": "Parameters updated"},
                msg_id=msg.id,
            )
            
        except StrategyError as e:
            logger.error(f"Failed to update params: {e}")
            return self._error_response(msg.id, str(e), e.error_code)
        except Exception as e:
            logger.error(f"Failed to update params: {e}")
            return self._error_response(msg.id, str(e))
    
    # Manual trading handlers
    def handle_manual_order(self, msg: Message) -> Optional[Message]:
        """
        Handle manual order request.
        
        Requirements:
            - 6.1: WHILE 回放模式运行中, THE UI_Client SHALL 提供"市价买入/卖出"按钮供用户手动下单
            - 6.2: WHEN 用户手动下单, THEN THE Matching_Engine SHALL 执行订单并标记为"人工干预单"
        
        Payload:
            symbol: str - Trading symbol
            exchange: str - Exchange name (optional, defaults to "backtest")
            direction: str - LONG or SHORT
            offset: str - OPEN or CLOSE
            price: float - Order price (0 for market order)
            volume: float - Order volume
        """
        payload = msg.payload
        
        try:
            # Validate required fields
            required = ["symbol", "direction", "offset", "price", "volume"]
            for field_name in required:
                if field_name not in payload:
                    return self._error_response(msg.id, f"Missing required field: {field_name}")
            
            # Validate direction
            direction = payload["direction"]
            if direction not in ("LONG", "SHORT"):
                return self._error_response(msg.id, f"Invalid direction: {direction}. Must be 'LONG' or 'SHORT'")
            
            # Validate offset
            offset = payload["offset"]
            if offset not in ("OPEN", "CLOSE"):
                return self._error_response(msg.id, f"Invalid offset: {offset}. Must be 'OPEN' or 'CLOSE'")
            
            # Validate volume
            volume = payload["volume"]
            if volume <= 0:
                return self._error_response(msg.id, "Volume must be positive")
            
            # Generate order ID
            order_id = f"manual_{int(datetime.now().timestamp() * 1000)}"
            
            # Create order data with is_manual=True
            from core.engine.types import OrderData, to_decimal
            
            order = OrderData(
                order_id=order_id,
                symbol=payload["symbol"],
                exchange=payload.get("exchange", "backtest"),
                direction=direction,
                offset=offset,
                price=to_decimal(payload["price"]),
                volume=to_decimal(volume),
                traded=to_decimal(0),
                status="PENDING",
                is_manual=True,  # Mark as manual intervention order (Requirement 6.2)
                create_time=datetime.now(),
            )
            
            # Submit to matching engine if available
            if self._matching_engine:
                submitted_order_id = self._matching_engine.submit_order(order)
                logger.info(f"Manual order submitted to matching engine: {submitted_order_id}")
            else:
                logger.info(f"Manual order created (no matching engine): {order_id}")
            
            return Message.create(
                MessageType.RESPONSE,
                payload={
                    "success": True,
                    "message": "Order submitted",
                    "order_id": order_id,
                    "is_manual": True,
                },
                msg_id=msg.id,
            )
            
        except Exception as e:
            logger.error(f"Failed to submit manual order: {e}")
            return self._error_response(msg.id, str(e))
    
    def handle_cancel_order(self, msg: Message) -> Optional[Message]:
        """
        Handle cancel order request.
        
        Payload:
            order_id: str - Order to cancel
        """
        payload = msg.payload
        
        try:
            order_id = payload.get("order_id")
            if not order_id:
                return self._error_response(msg.id, "Missing order_id")
            
            # TODO: Cancel order in matching engine
            
            logger.info(f"Cancel order: {order_id}")
            
            return Message.create(
                MessageType.RESPONSE,
                payload={"success": True, "message": "Order cancelled", "order_id": order_id},
                msg_id=msg.id,
            )
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return self._error_response(msg.id, str(e))
    
    def handle_close_all(self, msg: Message) -> Optional[Message]:
        """
        Handle close all positions request.
        
        Requirements:
            - 6.4: WHEN 用户点击"一键清仓", THEN THE Matching_Engine SHALL 立即平掉所有持仓
        
        This creates market orders to close all open positions.
        All close orders are marked as manual intervention orders.
        """
        try:
            closed_positions = []
            errors = []
            
            # Get current positions from state
            positions = self._state.positions if self._state.positions else []
            
            if not positions:
                logger.info("Close all positions requested - no positions to close")
                return Message.create(
                    MessageType.RESPONSE,
                    payload={
                        "success": True,
                        "message": "No positions to close",
                        "closed_count": 0,
                        "closed_positions": [],
                    },
                    msg_id=msg.id,
                )
            
            from core.engine.types import OrderData, to_decimal
            
            for position in positions:
                try:
                    # Extract position details
                    symbol = position.get("symbol", "")
                    direction = position.get("direction", "")
                    volume = position.get("volume", 0)
                    exchange = position.get("exchange", "backtest")
                    
                    if not symbol or volume <= 0:
                        continue
                    
                    # Determine close direction (opposite of position direction)
                    close_direction = "SHORT" if direction == "LONG" else "LONG"
                    
                    # Generate order ID for close order
                    order_id = f"close_all_{int(datetime.now().timestamp() * 1000)}_{symbol}"
                    
                    # Create market order to close position
                    close_order = OrderData(
                        order_id=order_id,
                        symbol=symbol,
                        exchange=exchange,
                        direction=close_direction,
                        offset="CLOSE",
                        price=to_decimal(0),  # Market order (price=0)
                        volume=to_decimal(volume),
                        traded=to_decimal(0),
                        status="PENDING",
                        is_manual=True,  # Mark as manual intervention order
                        create_time=datetime.now(),
                    )
                    
                    # Submit to matching engine if available
                    if self._matching_engine:
                        submitted_order_id = self._matching_engine.submit_order(close_order)
                        logger.info(f"Close order submitted: {submitted_order_id} for {symbol}")
                    
                    closed_positions.append({
                        "symbol": symbol,
                        "direction": direction,
                        "volume": volume,
                        "close_order_id": order_id,
                    })
                    
                except Exception as e:
                    error_msg = f"Failed to close position {position.get('symbol', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            success = len(errors) == 0
            message = "All positions closed" if success else f"Closed {len(closed_positions)} positions with {len(errors)} errors"
            
            logger.info(f"Close all positions: {len(closed_positions)} closed, {len(errors)} errors")
            
            return Message.create(
                MessageType.RESPONSE,
                payload={
                    "success": success,
                    "message": message,
                    "closed_count": len(closed_positions),
                    "closed_positions": closed_positions,
                    "errors": errors if errors else None,
                },
                msg_id=msg.id,
            )
            
        except Exception as e:
            logger.error(f"Failed to close all positions: {e}")
            return self._error_response(msg.id, str(e))
    
    # Snapshot handlers
    def handle_save_snapshot(self, msg: Message) -> Optional[Message]:
        """
        Handle save snapshot request.
        
        Payload:
            description: str - Optional snapshot description
        """
        payload = msg.payload
        
        try:
            if not self._replay_controller:
                return self._error_response(msg.id, "Replay controller not available")
            
            description = payload.get("description")
            path = self._replay_controller.save_snapshot(description)
            
            return Message.create(
                MessageType.RESPONSE,
                payload={"success": True, "message": "Snapshot saved", "path": path},
                msg_id=msg.id,
            )
            
        except SnapshotError as e:
            logger.error(f"Failed to save snapshot: {e}")
            return self._error_response(msg.id, str(e), e.error_code)
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return self._error_response(msg.id, str(e))
    
    def handle_load_snapshot(self, msg: Message) -> Optional[Message]:
        """
        Handle load snapshot request.
        
        Payload:
            path: str - Path to snapshot file
        """
        payload = msg.payload
        
        try:
            if not self._replay_controller:
                return self._error_response(msg.id, "Replay controller not available")
            
            path = payload.get("path")
            if not path:
                return self._error_response(msg.id, "Missing path")
            
            success = self._replay_controller.load_snapshot(path)
            
            return Message.create(
                MessageType.RESPONSE,
                payload={"success": success, "message": "Snapshot loaded" if success else "Failed to load"},
                msg_id=msg.id,
            )
            
        except SnapshotError as e:
            logger.error(f"Failed to load snapshot: {e}")
            return self._error_response(msg.id, str(e), e.error_code)
        except Exception as e:
            logger.error(f"Failed to load snapshot: {e}")
            return self._error_response(msg.id, str(e))
    
    # Alert handlers
    def handle_alert_ack(self, msg: Message) -> Optional[Message]:
        """
        Handle alert acknowledgment.
        
        Payload:
            alert_id: str - Alert to acknowledge
        """
        payload = msg.payload
        
        try:
            alert_id = payload.get("alert_id")
            if not alert_id:
                return self._error_response(msg.id, "Missing alert_id")
            
            if alert_id in self._pending_alerts:
                del self._pending_alerts[alert_id]
                logger.info(f"Alert acknowledged: {alert_id}")
                return Message.create(
                    MessageType.RESPONSE,
                    payload={"success": True, "message": "Alert acknowledged"},
                    msg_id=msg.id,
                )
            else:
                return self._error_response(msg.id, f"Alert not found: {alert_id}")
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
            return self._error_response(msg.id, str(e))
    
    # State sync handler
    def handle_request_state(self, msg: Message) -> Optional[Message]:
        """Handle state request."""
        return Message.create(
            MessageType.STATE_SYNC,
            payload=self.get_state(),
            msg_id=msg.id,
        )
    
    # Helper methods
    def _error_response(
        self,
        msg_id: str,
        error: str,
        error_code: Optional[str] = None,
    ) -> Message:
        """Create an error response message."""
        payload = {"success": False, "error": error}
        if error_code:
            payload["error_code"] = error_code
        return Message.create(MessageType.ERROR, payload, msg_id)
    
    def add_alert(self, alert_id: str, alert_data: Dict[str, Any]) -> None:
        """Add a pending alert."""
        self._pending_alerts[alert_id] = alert_data
    
    def broadcast_update(self, msg_type: MessageType, payload: Dict[str, Any]) -> None:
        """Broadcast an update to all connected clients."""
        if self._broadcast_callback:
            msg = Message.create(msg_type, payload)
            self._broadcast_callback(msg)


__all__ = [
    "SystemState",
    "MessageHandlers",
]
