"""
Titan-Quant Exception Classes

This module defines the exception hierarchy for the Titan-Quant system.
All custom exceptions inherit from TitanQuantError base class.

Exception Hierarchy:
    TitanQuantError (base)
    ├── EngineError - Core engine related errors
    ├── DataError - Data governance and provider errors
    ├── StrategyError - Strategy management errors
    ├── SnapshotError - Snapshot save/load errors
    ├── AuditIntegrityError - Audit log integrity violations
    └── RiskControlError - Risk control trigger errors
"""
from __future__ import annotations

from typing import Any


class TitanQuantError(Exception):
    """
    Base exception class for all Titan-Quant errors.
    
    All custom exceptions in the system should inherit from this class
    to enable unified error handling and logging.
    
    Attributes:
        message: Human-readable error description
        error_code: Optional error code for programmatic handling
        details: Optional dictionary with additional error context
    """
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"details={self.details!r})"
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
        }


class EngineError(TitanQuantError):
    """
    Exception raised for core engine related errors.
    
    This includes errors from:
    - Event bus operations
    - Engine adapter initialization/execution
    - Matching engine operations
    - Replay controller operations
    
    Examples:
        - Engine initialization failure
        - Event publishing failure
        - Adapter connection errors
    """
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        engine_name: str | None = None
    ) -> None:
        details = details or {}
        if engine_name:
            details["engine_name"] = engine_name
        super().__init__(message, error_code, details)
        self.engine_name = engine_name


class DataError(TitanQuantError):
    """
    Exception raised for data governance and provider errors.
    
    This includes errors from:
    - Data import/export operations
    - Data cleaning and validation
    - Data provider connections
    - Parquet storage operations
    
    Examples:
        - Invalid data format
        - Missing required columns
        - Data provider connection failure
        - Timestamp alignment errors
    """
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        data_source: str | None = None,
        file_path: str | None = None
    ) -> None:
        details = details or {}
        if data_source:
            details["data_source"] = data_source
        if file_path:
            details["file_path"] = file_path
        super().__init__(message, error_code, details)
        self.data_source = data_source
        self.file_path = file_path


class StrategyError(TitanQuantError):
    """
    Exception raised for strategy management errors.
    
    This includes errors from:
    - Strategy loading and parsing
    - Hot reload operations
    - Parameter validation
    - Strategy execution
    
    Examples:
        - Invalid strategy class
        - Hot reload failure
        - Parameter out of range
        - Strategy state inconsistency
    """
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        strategy_id: str | None = None,
        strategy_name: str | None = None
    ) -> None:
        details = details or {}
        if strategy_id:
            details["strategy_id"] = strategy_id
        if strategy_name:
            details["strategy_name"] = strategy_name
        super().__init__(message, error_code, details)
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name


class SnapshotError(TitanQuantError):
    """
    Exception raised for snapshot save/load errors.
    
    This includes errors from:
    - Snapshot creation
    - Snapshot serialization/deserialization
    - Snapshot restoration
    - Version compatibility checks
    
    Examples:
        - Snapshot file not found
        - Incompatible snapshot version
        - Corrupted snapshot data
        - State restoration failure
    """
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        snapshot_id: str | None = None,
        snapshot_version: str | None = None
    ) -> None:
        details = details or {}
        if snapshot_id:
            details["snapshot_id"] = snapshot_id
        if snapshot_version:
            details["snapshot_version"] = snapshot_version
        super().__init__(message, error_code, details)
        self.snapshot_id = snapshot_id
        self.snapshot_version = snapshot_version


class AuditIntegrityError(TitanQuantError):
    """
    Exception raised for audit log integrity violations.
    
    This is a critical security exception that indicates:
    - Audit log tampering detected
    - Hash chain verification failure
    - Checksum mismatch
    
    When this exception is raised, the system should:
    1. Send a sync alert
    2. Refuse to start/continue operations
    3. Log the incident for investigation
    
    Examples:
        - Hash chain broken
        - Record hash mismatch
        - Missing audit records
    """
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        log_file: str | None = None,
        record_id: str | None = None,
        expected_hash: str | None = None,
        actual_hash: str | None = None
    ) -> None:
        details = details or {}
        if log_file:
            details["log_file"] = log_file
        if record_id:
            details["record_id"] = record_id
        if expected_hash:
            details["expected_hash"] = expected_hash
        if actual_hash:
            details["actual_hash"] = actual_hash
        super().__init__(message, error_code, details)
        self.log_file = log_file
        self.record_id = record_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


class RiskControlError(TitanQuantError):
    """
    Exception raised when risk control triggers.
    
    This includes:
    - Daily drawdown limit exceeded
    - Single trade loss limit exceeded
    - Position ratio limit exceeded
    - Circuit breaker triggered
    
    When this exception is raised, the system should:
    1. Stop the strategy
    2. Optionally liquidate positions
    3. Send appropriate alerts
    
    Examples:
        - Max drawdown exceeded
        - Single loss limit hit
        - Consecutive losses threshold
    """
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        trigger_type: str | None = None,
        threshold: float | None = None,
        actual_value: float | None = None,
        auto_liquidate: bool = False
    ) -> None:
        details = details or {}
        if trigger_type:
            details["trigger_type"] = trigger_type
        if threshold is not None:
            details["threshold"] = threshold
        if actual_value is not None:
            details["actual_value"] = actual_value
        details["auto_liquidate"] = auto_liquidate
        super().__init__(message, error_code, details)
        self.trigger_type = trigger_type
        self.threshold = threshold
        self.actual_value = actual_value
        self.auto_liquidate = auto_liquidate


class ErrorCodes:
    """Standard error codes for Titan-Quant exceptions."""
    
    # Engine errors (E1xxx)
    ENGINE_INIT_FAILED = "E1001"
    ENGINE_NOT_RUNNING = "E1002"
    EVENT_PUBLISH_FAILED = "E1003"
    ADAPTER_CONNECTION_FAILED = "E1004"
    MATCHING_ENGINE_ERROR = "E1005"
    
    # Data errors (E2xxx)
    DATA_FORMAT_INVALID = "E2001"
    DATA_IMPORT_FAILED = "E2002"
    DATA_PROVIDER_ERROR = "E2003"
    DATA_ALIGNMENT_ERROR = "E2004"
    DATA_QUALITY_ERROR = "E2005"
    
    # Strategy errors (E3xxx)
    STRATEGY_LOAD_FAILED = "E3001"
    STRATEGY_NOT_FOUND = "E3002"
    STRATEGY_PARAM_INVALID = "E3003"
    HOT_RELOAD_FAILED = "E3004"
    STRATEGY_STATE_ERROR = "E3005"
    
    # Snapshot errors (E4xxx)
    SNAPSHOT_NOT_FOUND = "E4001"
    SNAPSHOT_CORRUPTED = "E4002"
    SNAPSHOT_VERSION_MISMATCH = "E4003"
    SNAPSHOT_RESTORE_FAILED = "E4004"
    
    # Audit errors (E5xxx)
    AUDIT_INTEGRITY_VIOLATION = "E5001"
    AUDIT_HASH_MISMATCH = "E5002"
    AUDIT_CHAIN_BROKEN = "E5003"
    
    # Risk control errors (E6xxx)
    RISK_DRAWDOWN_EXCEEDED = "E6001"
    RISK_SINGLE_LOSS_EXCEEDED = "E6002"
    RISK_POSITION_EXCEEDED = "E6003"
    RISK_CIRCUIT_BREAKER = "E6004"


__all__ = [
    "TitanQuantError",
    "EngineError",
    "DataError",
    "StrategyError",
    "SnapshotError",
    "AuditIntegrityError",
    "RiskControlError",
    "ErrorCodes",
]
