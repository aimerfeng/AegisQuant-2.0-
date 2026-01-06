"""
Titan-Quant Core Engine Module
"""
__version__ = "0.1.0"

from core.optimizer import (
    ParameterOptimizer,
    OptimizationConfig,
    OptimizationObjective,
    OptimizationAlgorithm,
    ParameterRange,
    ParameterType,
    OptimizationResult,
    OptimizationSummary,
    int_range,
    float_range,
    categorical,
)

from core.report import (
    EquityPoint,
    BacktestMetrics,
    BacktestReport,
    MetricsCalculator,
    ReportGenerator,
)

from core.server import (
    Message,
    MessageType,
    ServerConfig,
    WebSocketServer,
    MessageRouter,
    ClientInfo,
    ServerThread,
    run_server,
    run_server_async,
)

from core.handlers import (
    SystemState,
    MessageHandlers,
)

__all__ = [
    # Optimizer
    "ParameterOptimizer",
    "OptimizationConfig",
    "OptimizationObjective",
    "OptimizationAlgorithm",
    "ParameterRange",
    "ParameterType",
    "OptimizationResult",
    "OptimizationSummary",
    "int_range",
    "float_range",
    "categorical",
    # Report
    "EquityPoint",
    "BacktestMetrics",
    "BacktestReport",
    "MetricsCalculator",
    "ReportGenerator",
    # WebSocket Server
    "Message",
    "MessageType",
    "ServerConfig",
    "WebSocketServer",
    "MessageRouter",
    "ClientInfo",
    "ServerThread",
    "run_server",
    "run_server_async",
    # Message Handlers
    "SystemState",
    "MessageHandlers",
]
