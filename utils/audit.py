"""
Titan-Quant Audit Logger

This module implements the audit logging system with chain hash integrity
verification. It provides tamper-evident logging for all critical operations.

Requirements:
    - 14.1: THE Audit_Logger SHALL 使用 RotatingFileHandler 实现线程安全的日志写入
    - 14.2: WHEN 用户执行手动平仓操作, THEN THE Audit_Logger SHALL 记录 IP、时间、操作详情
    - 14.3: WHEN 用户修改策略参数, THEN THE Audit_Logger SHALL 记录修改前值和修改后值
    - 14.4: THE Audit_Logger SHALL 将交易审计日志写入 trading_audit.log
    - 14.5: THE Audit_Logger SHALL 将用户操作日志写入 user_action.log
    - 14.6: THE Audit_Logger SHALL 为每条审计记录生成 SHA-256 Hash，包含前一条记录的 Hash（链式哈希）
    - 14.7: THE Audit_Logger SHALL 在日志文件末尾维护 Checksum，用于检测日志篡改
    - 14.8: WHEN 系统启动, THEN THE Audit_Logger SHALL 验证审计日志的完整性
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from core.exceptions import AuditIntegrityError, ErrorCodes


class ActionType(Enum):
    """Audit action types."""
    MANUAL_TRADE = "MANUAL_TRADE"
    AUTO_TRADE = "AUTO_TRADE"
    PARAM_CHANGE = "PARAM_CHANGE"
    STRATEGY_RELOAD = "STRATEGY_RELOAD"
    STRATEGY_LOAD = "STRATEGY_LOAD"
    RISK_TRIGGER = "RISK_TRIGGER"
    SNAPSHOT_SAVE = "SNAPSHOT_SAVE"
    SNAPSHOT_LOAD = "SNAPSHOT_LOAD"
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    SYSTEM_START = "SYSTEM_START"
    SYSTEM_STOP = "SYSTEM_STOP"
    CLOSE_ALL_POSITIONS = "CLOSE_ALL_POSITIONS"
    CONFIG_CHANGE = "CONFIG_CHANGE"


# Genesis hash for the first record in the chain
GENESIS_HASH = "0" * 64


@dataclass
class AuditRecord:
    """
    Audit record with chain hash integrity.
    
    Each record contains a SHA-256 hash computed from its content
    combined with the previous record's hash, forming an unbroken chain.
    
    Attributes:
        record_id: Unique record identifier
        timestamp: Record creation timestamp
        user_id: User who performed the action
        ip_address: IP address of the user
        action_type: Type of action performed
        action_detail: Detailed description of the action
        previous_value: Value before the change (for modifications)
        new_value: Value after the change (for modifications)
        previous_hash: Hash of the previous record in the chain
        record_hash: SHA-256 hash of this record
    """
    record_id: str
    timestamp: datetime
    user_id: str
    ip_address: str
    action_type: str
    action_detail: dict[str, Any]
    previous_value: Optional[Any] = None
    new_value: Optional[Any] = None
    previous_hash: str = GENESIS_HASH
    record_hash: str = ""
    
    def __post_init__(self) -> None:
        """Compute record hash if not provided."""
        if not self.record_hash:
            self.record_hash = compute_record_hash(self)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "action_type": self.action_type,
            "action_detail": self.action_detail,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "previous_hash": self.previous_hash,
            "record_hash": self.record_hash,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditRecord:
        """Create AuditRecord from dictionary."""
        return cls(
            record_id=data["record_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            user_id=data["user_id"],
            ip_address=data["ip_address"],
            action_type=data["action_type"],
            action_detail=data["action_detail"],
            previous_value=data.get("previous_value"),
            new_value=data.get("new_value"),
            previous_hash=data.get("previous_hash", GENESIS_HASH),
            record_hash=data.get("record_hash", ""),
        )
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)
    
    @classmethod
    def from_json(cls, json_str: str) -> AuditRecord:
        """Create AuditRecord from JSON string."""
        return cls.from_dict(json.loads(json_str))


def compute_record_hash(record: AuditRecord) -> str:
    """
    Compute SHA-256 hash for an audit record.
    
    The hash is computed from the record content combined with
    the previous record's hash, forming a chain.
    
    Args:
        record: The audit record to hash.
        
    Returns:
        SHA-256 hash as hexadecimal string.
    """
    # Create a deterministic string representation for hashing
    hash_content = (
        f"{record.record_id}|"
        f"{record.timestamp.isoformat()}|"
        f"{record.user_id}|"
        f"{record.ip_address}|"
        f"{record.action_type}|"
        f"{json.dumps(record.action_detail, sort_keys=True, ensure_ascii=False)}|"
        f"{json.dumps(record.previous_value, sort_keys=True, ensure_ascii=False) if record.previous_value else 'null'}|"
        f"{json.dumps(record.new_value, sort_keys=True, ensure_ascii=False) if record.new_value else 'null'}|"
        f"{record.previous_hash}"
    )
    
    return hashlib.sha256(hash_content.encode("utf-8")).hexdigest()


def verify_record_hash(record: AuditRecord) -> bool:
    """
    Verify that a record's hash is correct.
    
    Args:
        record: The audit record to verify.
        
    Returns:
        True if the hash is valid, False otherwise.
    """
    expected_hash = compute_record_hash(record)
    return record.record_hash == expected_hash


def compute_file_checksum(file_path: str) -> str:
    """
    Compute SHA-256 checksum of a file.
    
    Args:
        file_path: Path to the file.
        
    Returns:
        SHA-256 checksum as hexadecimal string.
    """
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    
    return sha256_hash.hexdigest()


class IAuditLogger(ABC):
    """
    Abstract interface for the Audit Logger.
    
    The Audit Logger provides tamper-evident logging for all critical
    operations in the system using chain hash integrity.
    """
    
    @abstractmethod
    def log_trade(
        self,
        user_id: str,
        ip: str,
        trade_data: dict[str, Any],
        is_manual: bool
    ) -> str:
        """
        Log a trade execution.
        
        Args:
            user_id: User who executed the trade.
            ip: IP address of the user.
            trade_data: Trade details (from TradeRecord.to_dict()).
            is_manual: Whether this was a manual intervention trade.
            
        Returns:
            The record ID.
        """
        pass
    
    @abstractmethod
    def log_param_change(
        self,
        user_id: str,
        ip: str,
        strategy_id: str,
        param_name: str,
        old_value: Any,
        new_value: Any
    ) -> str:
        """
        Log a strategy parameter change.
        
        Args:
            user_id: User who made the change.
            ip: IP address of the user.
            strategy_id: ID of the strategy.
            param_name: Name of the parameter changed.
            old_value: Previous parameter value.
            new_value: New parameter value.
            
        Returns:
            The record ID.
        """
        pass
    
    @abstractmethod
    def log_action(
        self,
        user_id: str,
        ip: str,
        action_type: str,
        detail: dict[str, Any],
        previous_value: Optional[Any] = None,
        new_value: Optional[Any] = None
    ) -> str:
        """
        Log a generic action.
        
        Args:
            user_id: User who performed the action.
            ip: IP address of the user.
            action_type: Type of action (from ActionType enum).
            detail: Action details.
            previous_value: Optional previous value.
            new_value: Optional new value.
            
        Returns:
            The record ID.
        """
        pass
    
    @abstractmethod
    def verify_integrity(self) -> bool:
        """
        Verify the integrity of all audit logs.
        
        Returns:
            True if all logs are intact, False if tampering detected.
            
        Raises:
            AuditIntegrityError: If tampering is detected.
        """
        pass
    
    @abstractmethod
    def get_checksum(self, log_type: str) -> str:
        """
        Get the checksum of a log file.
        
        Args:
            log_type: Type of log ("trading" or "user_action").
            
        Returns:
            SHA-256 checksum of the log file.
        """
        pass


class AuditLogger(IAuditLogger):
    """
    Audit logger implementation with chain hash integrity.
    
    This logger maintains two separate log files:
    - trading_audit.log: For trade-related events
    - user_action.log: For user operation events
    
    Each log entry is a JSON object with a SHA-256 hash that includes
    the previous entry's hash, forming a tamper-evident chain.
    """
    
    # Log file names
    TRADING_LOG = "trading_audit.log"
    USER_ACTION_LOG = "user_action.log"
    CHECKSUM_SUFFIX = ".checksum"
    
    # Log rotation settings
    MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    BACKUP_COUNT = 5
    
    def __init__(
        self,
        log_dir: str = "logs",
        max_bytes: int = MAX_BYTES,
        backup_count: int = BACKUP_COUNT
    ) -> None:
        """
        Initialize the audit logger.
        
        Args:
            log_dir: Directory for log files.
            max_bytes: Maximum size of each log file before rotation.
            backup_count: Number of backup files to keep.
        """
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        
        # Thread lock for thread-safe operations
        self._lock = threading.RLock()
        
        # Track last hash for each log type
        self._last_hashes: dict[str, str] = {
            "trading": GENESIS_HASH,
            "user_action": GENESIS_HASH,
        }
        
        # Initialize loggers
        self._trading_logger = self._create_logger(
            "titan_quant.audit.trading",
            self._log_dir / self.TRADING_LOG
        )
        self._user_action_logger = self._create_logger(
            "titan_quant.audit.user_action",
            self._log_dir / self.USER_ACTION_LOG
        )
        
        # Load last hashes from existing logs
        self._load_last_hashes()
    
    def _create_logger(self, name: str, file_path: Path) -> logging.Logger:
        """Create a logger with rotating file handler."""
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Create rotating file handler
        handler = RotatingFileHandler(
            str(file_path),
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding="utf-8"
        )
        
        # Use a simple formatter that outputs just the message
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        logger.propagate = False
        
        return logger
    
    def _load_last_hashes(self) -> None:
        """Load the last hash from each log file."""
        for log_type, log_file in [
            ("trading", self.TRADING_LOG),
            ("user_action", self.USER_ACTION_LOG)
        ]:
            file_path = self._log_dir / log_file
            if file_path.exists():
                last_hash = self._get_last_hash_from_file(file_path)
                if last_hash:
                    self._last_hashes[log_type] = last_hash
    
    def _get_last_hash_from_file(self, file_path: Path) -> Optional[str]:
        """Get the last record hash from a log file."""
        last_hash = None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record_dict = json.loads(line)
                            last_hash = record_dict.get("record_hash")
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
        return last_hash
    
    def _create_record(
        self,
        user_id: str,
        ip: str,
        action_type: str,
        detail: dict[str, Any],
        previous_value: Optional[Any],
        new_value: Optional[Any],
        log_type: str
    ) -> AuditRecord:
        """Create an audit record with proper chain hash."""
        record = AuditRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip,
            action_type=action_type,
            action_detail=detail,
            previous_value=previous_value,
            new_value=new_value,
            previous_hash=self._last_hashes[log_type],
        )
        
        # Update last hash
        self._last_hashes[log_type] = record.record_hash
        
        return record
    
    def _write_record(self, record: AuditRecord, log_type: str) -> None:
        """Write a record to the appropriate log file."""
        json_line = record.to_json()
        
        if log_type == "trading":
            self._trading_logger.info(json_line)
        else:
            self._user_action_logger.info(json_line)
        
        # Update checksum file
        self._update_checksum(log_type)
    
    def _update_checksum(self, log_type: str) -> None:
        """Update the checksum file for a log."""
        if log_type == "trading":
            log_file = self._log_dir / self.TRADING_LOG
        else:
            log_file = self._log_dir / self.USER_ACTION_LOG
        
        checksum_file = Path(str(log_file) + self.CHECKSUM_SUFFIX)
        
        if log_file.exists():
            checksum = compute_file_checksum(str(log_file))
            with open(checksum_file, "w", encoding="utf-8") as f:
                f.write(checksum)
    
    def log_trade(
        self,
        user_id: str,
        ip: str,
        trade_data: dict[str, Any],
        is_manual: bool
    ) -> str:
        """Log a trade execution."""
        with self._lock:
            action_type = ActionType.MANUAL_TRADE.value if is_manual else ActionType.AUTO_TRADE.value
            
            record = self._create_record(
                user_id=user_id,
                ip=ip,
                action_type=action_type,
                detail=trade_data,
                previous_value=None,
                new_value=None,
                log_type="trading"
            )
            
            self._write_record(record, "trading")
            return record.record_id
    
    def log_param_change(
        self,
        user_id: str,
        ip: str,
        strategy_id: str,
        param_name: str,
        old_value: Any,
        new_value: Any
    ) -> str:
        """Log a strategy parameter change."""
        with self._lock:
            detail = {
                "strategy_id": strategy_id,
                "param_name": param_name,
            }
            
            record = self._create_record(
                user_id=user_id,
                ip=ip,
                action_type=ActionType.PARAM_CHANGE.value,
                detail=detail,
                previous_value=old_value,
                new_value=new_value,
                log_type="user_action"
            )
            
            self._write_record(record, "user_action")
            return record.record_id
    
    def log_action(
        self,
        user_id: str,
        ip: str,
        action_type: str,
        detail: dict[str, Any],
        previous_value: Optional[Any] = None,
        new_value: Optional[Any] = None
    ) -> str:
        """Log a generic action."""
        with self._lock:
            # Determine log type based on action
            if action_type in (ActionType.MANUAL_TRADE.value, ActionType.AUTO_TRADE.value):
                log_type = "trading"
            else:
                log_type = "user_action"
            
            record = self._create_record(
                user_id=user_id,
                ip=ip,
                action_type=action_type,
                detail=detail,
                previous_value=previous_value,
                new_value=new_value,
                log_type=log_type
            )
            
            self._write_record(record, log_type)
            return record.record_id
    
    def verify_integrity(self) -> bool:
        """
        Verify the integrity of all audit logs.
        
        Checks:
        1. Each record's hash is correctly computed
        2. The chain of hashes is unbroken
        3. The file checksum matches the stored checksum
        
        Returns:
            True if all logs are intact.
            
        Raises:
            AuditIntegrityError: If tampering is detected.
        """
        with self._lock:
            for log_type, log_file in [
                ("trading", self.TRADING_LOG),
                ("user_action", self.USER_ACTION_LOG)
            ]:
                file_path = self._log_dir / log_file
                if not file_path.exists():
                    continue
                
                # Verify checksum
                checksum_file = Path(str(file_path) + self.CHECKSUM_SUFFIX)
                if checksum_file.exists():
                    with open(checksum_file, "r", encoding="utf-8") as f:
                        stored_checksum = f.read().strip()
                    
                    actual_checksum = compute_file_checksum(str(file_path))
                    if stored_checksum != actual_checksum:
                        raise AuditIntegrityError(
                            message=f"Checksum mismatch for {log_file}",
                            error_code=ErrorCodes.AUDIT_INTEGRITY_VIOLATION,
                            log_file=str(file_path),
                            expected_hash=stored_checksum,
                            actual_hash=actual_checksum
                        )
                
                # Verify chain integrity
                self._verify_chain_integrity(file_path)
        
        return True
    
    def _verify_chain_integrity(self, file_path: Path) -> None:
        """Verify the hash chain integrity of a log file."""
        previous_hash = GENESIS_HASH
        line_number = 0
        
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_number += 1
                line = line.strip()
                if not line:
                    continue
                
                try:
                    record_dict = json.loads(line)
                    record = AuditRecord.from_dict(record_dict)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    raise AuditIntegrityError(
                        message=f"Invalid record format at line {line_number}",
                        error_code=ErrorCodes.AUDIT_INTEGRITY_VIOLATION,
                        log_file=str(file_path),
                        record_id=f"line_{line_number}",
                        details={"error": str(e)}
                    )
                
                # Verify previous hash link
                if record.previous_hash != previous_hash:
                    raise AuditIntegrityError(
                        message=f"Chain broken at line {line_number}: previous hash mismatch",
                        error_code=ErrorCodes.AUDIT_CHAIN_BROKEN,
                        log_file=str(file_path),
                        record_id=record.record_id,
                        expected_hash=previous_hash,
                        actual_hash=record.previous_hash
                    )
                
                # Verify record hash
                expected_hash = compute_record_hash(record)
                if record.record_hash != expected_hash:
                    raise AuditIntegrityError(
                        message=f"Hash mismatch at line {line_number}",
                        error_code=ErrorCodes.AUDIT_HASH_MISMATCH,
                        log_file=str(file_path),
                        record_id=record.record_id,
                        expected_hash=expected_hash,
                        actual_hash=record.record_hash
                    )
                
                previous_hash = record.record_hash
    
    def get_checksum(self, log_type: str) -> str:
        """Get the checksum of a log file."""
        if log_type == "trading":
            file_path = self._log_dir / self.TRADING_LOG
        elif log_type == "user_action":
            file_path = self._log_dir / self.USER_ACTION_LOG
        else:
            raise ValueError(f"Unknown log type: {log_type}")
        
        if not file_path.exists():
            return ""
        
        return compute_file_checksum(str(file_path))
    
    def get_records(self, log_type: str) -> list[AuditRecord]:
        """
        Get all records from a log file.
        
        Args:
            log_type: Type of log ("trading" or "user_action").
            
        Returns:
            List of audit records.
        """
        if log_type == "trading":
            file_path = self._log_dir / self.TRADING_LOG
        elif log_type == "user_action":
            file_path = self._log_dir / self.USER_ACTION_LOG
        else:
            raise ValueError(f"Unknown log type: {log_type}")
        
        records = []
        if not file_path.exists():
            return records
        
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = AuditRecord.from_json(line)
                        records.append(record)
                    except (json.JSONDecodeError, KeyError):
                        continue
        
        return records
    
    def get_last_hash(self, log_type: str) -> str:
        """Get the last hash for a log type."""
        return self._last_hashes.get(log_type, GENESIS_HASH)


def verify_audit_logs_on_startup(log_dir: str = "logs") -> bool:
    """
    Verify audit log integrity on system startup.
    
    This function should be called during system initialization
    to ensure audit logs have not been tampered with.
    
    Args:
        log_dir: Directory containing log files.
        
    Returns:
        True if logs are intact.
        
    Raises:
        AuditIntegrityError: If tampering is detected.
    """
    logger = AuditLogger(log_dir=log_dir)
    return logger.verify_integrity()


__all__ = [
    "ActionType",
    "GENESIS_HASH",
    "AuditRecord",
    "compute_record_hash",
    "verify_record_hash",
    "compute_file_checksum",
    "IAuditLogger",
    "AuditLogger",
    "verify_audit_logs_on_startup",
]
