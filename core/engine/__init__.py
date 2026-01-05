"""
Core Engine Components
- Event Bus
- Engine Adapter
- Matching Engine
- Replay Controller
- Risk Controller
- Snapshot Manager
"""
from core.engine.adapter import (
    BacktestMode,
    BacktestResult,
    EngineConfig,
    EngineState,
    IEngineAdapter,
)
from core.engine.event import Event, EventType
from core.engine.event_bus import EventBus, EventHandler, IEventBus
from core.engine.matching import (
    IMatchingEngine,
    L2SimulationLevel,
    MatchingConfig,
    MatchingEngine,
    MatchingMode,
    MatchingQualityMetrics,
    SlippageModel,
    TradeRecord,
)
from core.engine.snapshot import (
    AccountState,
    ISnapshotManager,
    PositionState,
    Snapshot,
    SnapshotManager,
    StrategyState,
)
from core.engine.replay import (
    DataProvider,
    IReplayController,
    ReplayConfig,
    ReplayController,
    ReplaySpeed,
    ReplayState,
    ReplayStatus,
    StateUpdateCallback,
)
from core.engine.risk import (
    AccountSnapshot,
    AlertCallback,
    IRiskController,
    LiquidationCallback,
    RiskConfig,
    RiskController,
    RiskLevel,
    RiskTriggerEvent,
    RiskTriggerType,
    TradeResult,
)
from core.engine.types import (
    BarData,
    Direction,
    Interval,
    Offset,
    OrderData,
    OrderStatus,
    TickData,
)

__all__ = [
    # Event system
    "Event",
    "EventType",
    "EventBus",
    "EventHandler",
    "IEventBus",
    # Data types
    "BarData",
    "TickData",
    "OrderData",
    "Direction",
    "Offset",
    "OrderStatus",
    "Interval",
    # Engine adapter
    "IEngineAdapter",
    "EngineState",
    "EngineConfig",
    "BacktestMode",
    "BacktestResult",
    # Matching engine
    "MatchingMode",
    "L2SimulationLevel",
    "SlippageModel",
    "MatchingConfig",
    "TradeRecord",
    "MatchingQualityMetrics",
    "IMatchingEngine",
    "MatchingEngine",
    # Snapshot manager
    "AccountState",
    "PositionState",
    "StrategyState",
    "Snapshot",
    "ISnapshotManager",
    "SnapshotManager",
    # Replay controller
    "ReplayState",
    "ReplaySpeed",
    "ReplayConfig",
    "ReplayStatus",
    "IReplayController",
    "ReplayController",
    "DataProvider",
    "StateUpdateCallback",
    # Risk controller
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
