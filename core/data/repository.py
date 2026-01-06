"""
Titan-Quant Data Access Layer (Repository)

This module provides CRUD operations for all database tables in the Titan-Quant system.
It uses SQLite as the underlying database and provides a clean interface for data access.

Tables:
    - users: User accounts and authentication
    - exchange_keys: Encrypted API keys for exchanges
    - strategies: Strategy metadata and configuration
    - backtest_records: Backtest execution records
    - backtest_results: Backtest performance results
    - snapshots: System state snapshots
    - alert_configs: Alert configuration rules
    - data_providers: Data source configurations
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Generic, TypeVar, Optional, List, Dict

from core.exceptions import DataError, ErrorCodes


# Type variable for generic repository
T = TypeVar("T")


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    TRADER = "trader"


class BacktestStatus(str, Enum):
    """Backtest status enumeration."""
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class AlertType(str, Enum):
    """Alert type enumeration."""
    SYNC = "sync"
    ASYNC = "async"


class AlertSeverity(str, Enum):
    """Alert severity enumeration."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProviderType(str, Enum):
    """Data provider type enumeration."""
    PARQUET = "parquet"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    DOLPHINDB = "dolphindb"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class User:
    """User data model."""
    user_id: str
    username: str
    password_hash: str
    role: UserRole
    settings: Optional[Dict[str, Any]] = None
    preferred_language: str = "zh_cn"
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


@dataclass
class ExchangeKey:
    """Exchange API key data model."""
    key_id: str
    user_id: str
    exchange: str
    api_key_name: str
    api_key_ciphertext: str
    secret_key_ciphertext: str
    passphrase_ciphertext: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Strategy:
    """Strategy metadata data model."""
    strategy_id: str
    name: str
    class_name: str
    file_path: str
    checksum: str
    parameters: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class BacktestRecord:
    """Backtest record data model."""
    backtest_id: str
    strategy_id: Optional[str]
    start_date: datetime
    end_date: datetime
    initial_capital: float
    matching_mode: str
    status: BacktestStatus
    l2_level: Optional[str] = None
    data_provider: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class BacktestResult:
    """Backtest result data model."""
    result_id: str
    backtest_id: str
    total_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    total_trades: Optional[int] = None
    metrics_json: Optional[Dict[str, Any]] = None
    report_path: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Snapshot:
    """Snapshot data model."""
    snapshot_id: str
    backtest_id: Optional[str]
    version: str
    file_path: str
    data_timestamp: datetime
    created_at: Optional[datetime] = None


@dataclass
class AlertConfig:
    """Alert configuration data model."""
    config_id: str
    event_type: str
    alert_type: AlertType
    channels: List[str]
    severity: AlertSeverity
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class DataProvider:
    """Data provider configuration data model."""
    provider_id: str
    provider_type: ProviderType
    name: str
    connection_config: Dict[str, Any]
    is_default: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# Database Connection Manager
# ============================================================================

class DatabaseManager:
    """
    SQLite database connection manager.
    
    Provides connection pooling and transaction management for the repository layer.
    """
    
    _instance: Optional["DatabaseManager"] = None
    _db_path: Optional[str] = None
    
    def __new__(cls, db_path: Optional[str] = None) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: Optional[str] = None) -> None:
        if self._initialized and db_path is None:
            return
        
        if db_path:
            self._db_path = db_path
        elif self._db_path is None:
            self._db_path = os.path.join("database", "titan_quant.db")
        
        self._initialized = True
    
    @property
    def db_path(self) -> str:
        """Get the database file path."""
        return self._db_path or os.path.join("database", "titan_quant.db")
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get a database connection with automatic cleanup.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get a database connection with transaction support.
        
        Yields:
            sqlite3.Connection: Database connection with transaction
        """
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    
    def initialize_database(self, schema_path: Optional[str] = None) -> None:
        """
        Initialize the database with the schema.
        
        Args:
            schema_path: Path to the schema SQL file
        """
        if schema_path is None:
            schema_path = os.path.join("database", "schema.sql")
        
        # Ensure database directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        # Read and execute schema
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        
        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()
    
    def reset(self) -> None:
        """Reset the singleton instance (for testing)."""
        DatabaseManager._instance = None
        DatabaseManager._db_path = None


def get_database_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """Get the database manager singleton instance."""
    return DatabaseManager(db_path)


def reset_database_manager() -> None:
    """Reset the database manager singleton (for testing)."""
    DatabaseManager._instance = None
    DatabaseManager._db_path = None


# ============================================================================
# Base Repository
# ============================================================================

class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository providing common CRUD operations.
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self._db_manager = db_manager or get_database_manager()
    
    @property
    @abstractmethod
    def table_name(self) -> str:
        """Get the table name for this repository."""
        pass
    
    @property
    @abstractmethod
    def primary_key(self) -> str:
        """Get the primary key column name."""
        pass
    
    @abstractmethod
    def _row_to_model(self, row: sqlite3.Row) -> T:
        """Convert a database row to a model instance."""
        pass
    
    @abstractmethod
    def _model_to_dict(self, model: T) -> Dict[str, Any]:
        """Convert a model instance to a dictionary for database insertion."""
        pass
    
    def _generate_id(self) -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())
    
    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse a datetime value from the database."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # Try ISO format first
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
            # Try standard SQLite format
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
            # Try date-only format
            try:
                return datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                pass
        return None
    
    def _format_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Format a datetime value for database storage."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)
    
    def _format_date(self, value: Optional[datetime]) -> Optional[str]:
        """Format a date value for database storage (DATE columns)."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        return str(value)


# ============================================================================
# User Repository
# ============================================================================

class UserRepository(BaseRepository[User]):
    """Repository for user CRUD operations."""
    
    @property
    def table_name(self) -> str:
        return "users"
    
    @property
    def primary_key(self) -> str:
        return "user_id"
    
    def _row_to_model(self, row: sqlite3.Row) -> User:
        settings = None
        if row["settings"]:
            settings = json.loads(row["settings"])
        
        return User(
            user_id=row["user_id"],
            username=row["username"],
            password_hash=row["password_hash"],
            role=UserRole(row["role"]),
            settings=settings,
            preferred_language=row["preferred_language"],
            created_at=self._parse_datetime(row["created_at"]),
            last_login=self._parse_datetime(row["last_login"]),
        )
    
    def _model_to_dict(self, model: User) -> Dict[str, Any]:
        return {
            "user_id": model.user_id,
            "username": model.username,
            "password_hash": model.password_hash,
            "role": model.role.value if isinstance(model.role, UserRole) else model.role,
            "settings": json.dumps(model.settings) if model.settings else None,
            "preferred_language": model.preferred_language,
            "last_login": self._format_datetime(model.last_login),
        }
    
    def create(self, user: User) -> User:
        """Create a new user."""
        if not user.user_id:
            user.user_id = self._generate_id()
        
        data = self._model_to_dict(user)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        
        return self.get_by_id(user.user_id)
    
    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get a user by username."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_all(self) -> List[User]:
        """Get all users."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM {self.table_name}")
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def update(self, user: User) -> Optional[User]:
        """Update an existing user."""
        data = self._model_to_dict(user)
        del data["user_id"]  # Don't update primary key
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?",
                list(data.values()) + [user.user_id]
            )
        
        return self.get_by_id(user.user_id)
    
    def update_last_login(self, user_id: str) -> None:
        """Update the last login timestamp for a user."""
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET last_login = ? WHERE {self.primary_key} = ?",
                (datetime.now().isoformat(), user_id)
            )
    
    def delete(self, user_id: str) -> bool:
        """Delete a user by ID."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?",
                (user_id,)
            )
            return cursor.rowcount > 0



# ============================================================================
# Exchange Key Repository
# ============================================================================

class ExchangeKeyRepository(BaseRepository[ExchangeKey]):
    """Repository for exchange key CRUD operations."""
    
    @property
    def table_name(self) -> str:
        return "exchange_keys"
    
    @property
    def primary_key(self) -> str:
        return "key_id"
    
    def _row_to_model(self, row: sqlite3.Row) -> ExchangeKey:
        permissions = None
        if row["permissions"]:
            permissions = json.loads(row["permissions"])
        
        return ExchangeKey(
            key_id=row["key_id"],
            user_id=row["user_id"],
            exchange=row["exchange"],
            api_key_name=row["api_key_name"],
            api_key_ciphertext=row["api_key_ciphertext"],
            secret_key_ciphertext=row["secret_key_ciphertext"],
            passphrase_ciphertext=row["passphrase_ciphertext"],
            permissions=permissions,
            is_active=bool(row["is_active"]),
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
        )
    
    def _model_to_dict(self, model: ExchangeKey) -> Dict[str, Any]:
        return {
            "key_id": model.key_id,
            "user_id": model.user_id,
            "exchange": model.exchange,
            "api_key_name": model.api_key_name,
            "api_key_ciphertext": model.api_key_ciphertext,
            "secret_key_ciphertext": model.secret_key_ciphertext,
            "passphrase_ciphertext": model.passphrase_ciphertext,
            "permissions": json.dumps(model.permissions) if model.permissions else None,
            "is_active": model.is_active,
        }
    
    def create(self, key: ExchangeKey) -> ExchangeKey:
        """Create a new exchange key."""
        if not key.key_id:
            key.key_id = self._generate_id()
        
        data = self._model_to_dict(key)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        
        return self.get_by_id(key.key_id)
    
    def get_by_id(self, key_id: str) -> Optional[ExchangeKey]:
        """Get an exchange key by ID."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?",
                (key_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_user_id(self, user_id: str) -> List[ExchangeKey]:
        """Get all exchange keys for a user."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE user_id = ?",
                (user_id,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def get_by_exchange(self, user_id: str, exchange: str) -> List[ExchangeKey]:
        """Get exchange keys for a specific exchange."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE user_id = ? AND exchange = ?",
                (user_id, exchange)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def get_active_keys(self, user_id: str) -> List[ExchangeKey]:
        """Get all active exchange keys for a user."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def update(self, key: ExchangeKey) -> Optional[ExchangeKey]:
        """Update an existing exchange key."""
        data = self._model_to_dict(key)
        del data["key_id"]  # Don't update primary key
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?",
                list(data.values()) + [key.key_id]
            )
        
        return self.get_by_id(key.key_id)
    
    def deactivate(self, key_id: str) -> bool:
        """Deactivate an exchange key."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE {self.table_name} SET is_active = 0 WHERE {self.primary_key} = ?",
                (key_id,)
            )
            return cursor.rowcount > 0
    
    def delete(self, key_id: str) -> bool:
        """Delete an exchange key by ID."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?",
                (key_id,)
            )
            return cursor.rowcount > 0


# ============================================================================
# Strategy Repository
# ============================================================================

class StrategyRepository(BaseRepository[Strategy]):
    """Repository for strategy CRUD operations."""
    
    @property
    def table_name(self) -> str:
        return "strategies"
    
    @property
    def primary_key(self) -> str:
        return "strategy_id"
    
    def _row_to_model(self, row: sqlite3.Row) -> Strategy:
        parameters = None
        if row["parameters"]:
            parameters = json.loads(row["parameters"])
        
        return Strategy(
            strategy_id=row["strategy_id"],
            name=row["name"],
            class_name=row["class_name"],
            file_path=row["file_path"],
            checksum=row["checksum"],
            parameters=parameters,
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
        )
    
    def _model_to_dict(self, model: Strategy) -> Dict[str, Any]:
        return {
            "strategy_id": model.strategy_id,
            "name": model.name,
            "class_name": model.class_name,
            "file_path": model.file_path,
            "checksum": model.checksum,
            "parameters": json.dumps(model.parameters) if model.parameters else None,
        }
    
    def create(self, strategy: Strategy) -> Strategy:
        """Create a new strategy."""
        if not strategy.strategy_id:
            strategy.strategy_id = self._generate_id()
        
        data = self._model_to_dict(strategy)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        
        return self.get_by_id(strategy.strategy_id)
    
    def get_by_id(self, strategy_id: str) -> Optional[Strategy]:
        """Get a strategy by ID."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?",
                (strategy_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_name(self, name: str) -> Optional[Strategy]:
        """Get a strategy by name."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_class_name(self, class_name: str) -> List[Strategy]:
        """Get strategies by class name."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE class_name = ?",
                (class_name,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def get_all(self) -> List[Strategy]:
        """Get all strategies."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM {self.table_name}")
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def update(self, strategy: Strategy) -> Optional[Strategy]:
        """Update an existing strategy."""
        data = self._model_to_dict(strategy)
        del data["strategy_id"]  # Don't update primary key
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?",
                list(data.values()) + [strategy.strategy_id]
            )
        
        return self.get_by_id(strategy.strategy_id)
    
    def delete(self, strategy_id: str) -> bool:
        """Delete a strategy by ID."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?",
                (strategy_id,)
            )
            return cursor.rowcount > 0


# ============================================================================
# Backtest Record Repository
# ============================================================================

class BacktestRecordRepository(BaseRepository[BacktestRecord]):
    """Repository for backtest record CRUD operations."""
    
    @property
    def table_name(self) -> str:
        return "backtest_records"
    
    @property
    def primary_key(self) -> str:
        return "backtest_id"
    
    def _row_to_model(self, row: sqlite3.Row) -> BacktestRecord:
        return BacktestRecord(
            backtest_id=row["backtest_id"],
            strategy_id=row["strategy_id"],
            start_date=self._parse_datetime(row["start_date"]),
            end_date=self._parse_datetime(row["end_date"]),
            initial_capital=row["initial_capital"],
            matching_mode=row["matching_mode"],
            l2_level=row["l2_level"],
            data_provider=row["data_provider"],
            status=BacktestStatus(row["status"]),
            created_at=self._parse_datetime(row["created_at"]),
            completed_at=self._parse_datetime(row["completed_at"]),
        )
    
    def _model_to_dict(self, model: BacktestRecord) -> Dict[str, Any]:
        return {
            "backtest_id": model.backtest_id,
            "strategy_id": model.strategy_id,
            "start_date": self._format_date(model.start_date) if isinstance(model.start_date, datetime) else model.start_date,
            "end_date": self._format_date(model.end_date) if isinstance(model.end_date, datetime) else model.end_date,
            "initial_capital": model.initial_capital,
            "matching_mode": model.matching_mode,
            "l2_level": model.l2_level,
            "data_provider": model.data_provider,
            "status": model.status.value if isinstance(model.status, BacktestStatus) else model.status,
            "completed_at": self._format_datetime(model.completed_at),
        }
    
    def create(self, record: BacktestRecord) -> BacktestRecord:
        """Create a new backtest record."""
        if not record.backtest_id:
            record.backtest_id = self._generate_id()
        
        data = self._model_to_dict(record)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        
        return self.get_by_id(record.backtest_id)
    
    def get_by_id(self, backtest_id: str) -> Optional[BacktestRecord]:
        """Get a backtest record by ID."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?",
                (backtest_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_strategy_id(self, strategy_id: str) -> List[BacktestRecord]:
        """Get all backtest records for a strategy."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE strategy_id = ? ORDER BY created_at DESC",
                (strategy_id,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def get_by_status(self, status: BacktestStatus) -> List[BacktestRecord]:
        """Get backtest records by status."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE status = ? ORDER BY created_at DESC",
                (status.value,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def get_all(self, limit: int = 100) -> List[BacktestRecord]:
        """Get all backtest records with optional limit."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def update_status(self, backtest_id: str, status: BacktestStatus) -> bool:
        """Update the status of a backtest record."""
        completed_at = None
        if status in (BacktestStatus.COMPLETED, BacktestStatus.FAILED):
            completed_at = datetime.now().isoformat()
        
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE {self.table_name} SET status = ?, completed_at = ? WHERE {self.primary_key} = ?",
                (status.value, completed_at, backtest_id)
            )
            return cursor.rowcount > 0
    
    def update(self, record: BacktestRecord) -> Optional[BacktestRecord]:
        """Update an existing backtest record."""
        data = self._model_to_dict(record)
        del data["backtest_id"]  # Don't update primary key
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?",
                list(data.values()) + [record.backtest_id]
            )
        
        return self.get_by_id(record.backtest_id)
    
    def delete(self, backtest_id: str) -> bool:
        """Delete a backtest record by ID."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?",
                (backtest_id,)
            )
            return cursor.rowcount > 0



# ============================================================================
# Backtest Result Repository
# ============================================================================

class BacktestResultRepository(BaseRepository[BacktestResult]):
    """Repository for backtest result CRUD operations."""
    
    @property
    def table_name(self) -> str:
        return "backtest_results"
    
    @property
    def primary_key(self) -> str:
        return "result_id"
    
    def _row_to_model(self, row: sqlite3.Row) -> BacktestResult:
        metrics_json = None
        if row["metrics_json"]:
            metrics_json = json.loads(row["metrics_json"])
        
        return BacktestResult(
            result_id=row["result_id"],
            backtest_id=row["backtest_id"],
            total_return=row["total_return"],
            sharpe_ratio=row["sharpe_ratio"],
            max_drawdown=row["max_drawdown"],
            win_rate=row["win_rate"],
            profit_factor=row["profit_factor"],
            total_trades=row["total_trades"],
            metrics_json=metrics_json,
            report_path=row["report_path"],
            created_at=self._parse_datetime(row["created_at"]),
        )
    
    def _model_to_dict(self, model: BacktestResult) -> Dict[str, Any]:
        return {
            "result_id": model.result_id,
            "backtest_id": model.backtest_id,
            "total_return": model.total_return,
            "sharpe_ratio": model.sharpe_ratio,
            "max_drawdown": model.max_drawdown,
            "win_rate": model.win_rate,
            "profit_factor": model.profit_factor,
            "total_trades": model.total_trades,
            "metrics_json": json.dumps(model.metrics_json) if model.metrics_json else None,
            "report_path": model.report_path,
        }
    
    def create(self, result: BacktestResult) -> BacktestResult:
        """Create a new backtest result."""
        if not result.result_id:
            result.result_id = self._generate_id()
        
        data = self._model_to_dict(result)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        
        return self.get_by_id(result.result_id)
    
    def get_by_id(self, result_id: str) -> Optional[BacktestResult]:
        """Get a backtest result by ID."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?",
                (result_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_backtest_id(self, backtest_id: str) -> Optional[BacktestResult]:
        """Get the result for a specific backtest."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE backtest_id = ?",
                (backtest_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_all(self, limit: int = 100) -> List[BacktestResult]:
        """Get all backtest results with optional limit."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def update(self, result: BacktestResult) -> Optional[BacktestResult]:
        """Update an existing backtest result."""
        data = self._model_to_dict(result)
        del data["result_id"]  # Don't update primary key
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?",
                list(data.values()) + [result.result_id]
            )
        
        return self.get_by_id(result.result_id)
    
    def delete(self, result_id: str) -> bool:
        """Delete a backtest result by ID."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?",
                (result_id,)
            )
            return cursor.rowcount > 0


# ============================================================================
# Snapshot Repository
# ============================================================================

class SnapshotRepository(BaseRepository[Snapshot]):
    """Repository for snapshot CRUD operations."""
    
    @property
    def table_name(self) -> str:
        return "snapshots"
    
    @property
    def primary_key(self) -> str:
        return "snapshot_id"
    
    def _row_to_model(self, row: sqlite3.Row) -> Snapshot:
        return Snapshot(
            snapshot_id=row["snapshot_id"],
            backtest_id=row["backtest_id"],
            version=row["version"],
            file_path=row["file_path"],
            data_timestamp=self._parse_datetime(row["data_timestamp"]),
            created_at=self._parse_datetime(row["created_at"]),
        )
    
    def _model_to_dict(self, model: Snapshot) -> Dict[str, Any]:
        return {
            "snapshot_id": model.snapshot_id,
            "backtest_id": model.backtest_id,
            "version": model.version,
            "file_path": model.file_path,
            "data_timestamp": self._format_datetime(model.data_timestamp) if isinstance(model.data_timestamp, datetime) else model.data_timestamp,
        }
    
    def create(self, snapshot: Snapshot) -> Snapshot:
        """Create a new snapshot."""
        if not snapshot.snapshot_id:
            snapshot.snapshot_id = self._generate_id()
        
        data = self._model_to_dict(snapshot)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        
        return self.get_by_id(snapshot.snapshot_id)
    
    def get_by_id(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get a snapshot by ID."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?",
                (snapshot_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_backtest_id(self, backtest_id: str) -> List[Snapshot]:
        """Get all snapshots for a backtest."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE backtest_id = ? ORDER BY data_timestamp DESC",
                (backtest_id,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def get_latest_by_backtest_id(self, backtest_id: str) -> Optional[Snapshot]:
        """Get the latest snapshot for a backtest."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE backtest_id = ? ORDER BY data_timestamp DESC LIMIT 1",
                (backtest_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_all(self, limit: int = 100) -> List[Snapshot]:
        """Get all snapshots with optional limit."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def delete(self, snapshot_id: str) -> bool:
        """Delete a snapshot by ID."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?",
                (snapshot_id,)
            )
            return cursor.rowcount > 0
    
    def delete_by_backtest_id(self, backtest_id: str) -> int:
        """Delete all snapshots for a backtest. Returns count of deleted rows."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE backtest_id = ?",
                (backtest_id,)
            )
            return cursor.rowcount


# ============================================================================
# Alert Config Repository
# ============================================================================

class AlertConfigRepository(BaseRepository[AlertConfig]):
    """Repository for alert configuration CRUD operations."""
    
    @property
    def table_name(self) -> str:
        return "alert_configs"
    
    @property
    def primary_key(self) -> str:
        return "config_id"
    
    def _row_to_model(self, row: sqlite3.Row) -> AlertConfig:
        channels = json.loads(row["channels"]) if row["channels"] else []
        
        return AlertConfig(
            config_id=row["config_id"],
            event_type=row["event_type"],
            alert_type=AlertType(row["alert_type"]),
            channels=channels,
            severity=AlertSeverity(row["severity"]),
            enabled=bool(row["enabled"]),
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
        )
    
    def _model_to_dict(self, model: AlertConfig) -> Dict[str, Any]:
        return {
            "config_id": model.config_id,
            "event_type": model.event_type,
            "alert_type": model.alert_type.value if isinstance(model.alert_type, AlertType) else model.alert_type,
            "channels": json.dumps(model.channels),
            "severity": model.severity.value if isinstance(model.severity, AlertSeverity) else model.severity,
            "enabled": model.enabled,
        }
    
    def create(self, config: AlertConfig) -> AlertConfig:
        """Create a new alert configuration."""
        if not config.config_id:
            config.config_id = self._generate_id()
        
        data = self._model_to_dict(config)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        
        return self.get_by_id(config.config_id)
    
    def get_by_id(self, config_id: str) -> Optional[AlertConfig]:
        """Get an alert configuration by ID."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?",
                (config_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_event_type(self, event_type: str) -> Optional[AlertConfig]:
        """Get alert configuration for a specific event type."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE event_type = ?",
                (event_type,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_enabled(self) -> List[AlertConfig]:
        """Get all enabled alert configurations."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE enabled = 1"
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def get_all(self) -> List[AlertConfig]:
        """Get all alert configurations."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM {self.table_name}")
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def update(self, config: AlertConfig) -> Optional[AlertConfig]:
        """Update an existing alert configuration."""
        data = self._model_to_dict(config)
        del data["config_id"]  # Don't update primary key
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?",
                list(data.values()) + [config.config_id]
            )
        
        return self.get_by_id(config.config_id)
    
    def set_enabled(self, config_id: str, enabled: bool) -> bool:
        """Enable or disable an alert configuration."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE {self.table_name} SET enabled = ? WHERE {self.primary_key} = ?",
                (enabled, config_id)
            )
            return cursor.rowcount > 0
    
    def delete(self, config_id: str) -> bool:
        """Delete an alert configuration by ID."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?",
                (config_id,)
            )
            return cursor.rowcount > 0


# ============================================================================
# Data Provider Repository
# ============================================================================

class DataProviderRepository(BaseRepository[DataProvider]):
    """Repository for data provider configuration CRUD operations."""
    
    @property
    def table_name(self) -> str:
        return "data_providers"
    
    @property
    def primary_key(self) -> str:
        return "provider_id"
    
    def _row_to_model(self, row: sqlite3.Row) -> DataProvider:
        connection_config = json.loads(row["connection_config"]) if row["connection_config"] else {}
        
        return DataProvider(
            provider_id=row["provider_id"],
            provider_type=ProviderType(row["provider_type"]),
            name=row["name"],
            connection_config=connection_config,
            is_default=bool(row["is_default"]),
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
        )
    
    def _model_to_dict(self, model: DataProvider) -> Dict[str, Any]:
        return {
            "provider_id": model.provider_id,
            "provider_type": model.provider_type.value if isinstance(model.provider_type, ProviderType) else model.provider_type,
            "name": model.name,
            "connection_config": json.dumps(model.connection_config),
            "is_default": model.is_default,
        }
    
    def create(self, provider: DataProvider) -> DataProvider:
        """Create a new data provider configuration."""
        if not provider.provider_id:
            provider.provider_id = self._generate_id()
        
        data = self._model_to_dict(provider)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        
        return self.get_by_id(provider.provider_id)
    
    def get_by_id(self, provider_id: str) -> Optional[DataProvider]:
        """Get a data provider by ID."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?",
                (provider_id,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_name(self, name: str) -> Optional[DataProvider]:
        """Get a data provider by name."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_by_type(self, provider_type: ProviderType) -> List[DataProvider]:
        """Get data providers by type."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE provider_type = ?",
                (provider_type.value,)
            )
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def get_default(self) -> Optional[DataProvider]:
        """Get the default data provider."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE is_default = 1"
            )
            row = cursor.fetchone()
            return self._row_to_model(row) if row else None
    
    def get_all(self) -> List[DataProvider]:
        """Get all data providers."""
        with self._db_manager.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM {self.table_name}")
            return [self._row_to_model(row) for row in cursor.fetchall()]
    
    def update(self, provider: DataProvider) -> Optional[DataProvider]:
        """Update an existing data provider."""
        data = self._model_to_dict(provider)
        del data["provider_id"]  # Don't update primary key
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        
        with self._db_manager.transaction() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?",
                list(data.values()) + [provider.provider_id]
            )
        
        return self.get_by_id(provider.provider_id)
    
    def set_default(self, provider_id: str) -> bool:
        """Set a data provider as the default."""
        with self._db_manager.transaction() as conn:
            # Clear existing default
            conn.execute(f"UPDATE {self.table_name} SET is_default = 0")
            # Set new default
            cursor = conn.execute(
                f"UPDATE {self.table_name} SET is_default = 1 WHERE {self.primary_key} = ?",
                (provider_id,)
            )
            return cursor.rowcount > 0
    
    def delete(self, provider_id: str) -> bool:
        """Delete a data provider by ID."""
        with self._db_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?",
                (provider_id,)
            )
            return cursor.rowcount > 0


# ============================================================================
# Repository Factory
# ============================================================================

class RepositoryFactory:
    """
    Factory for creating repository instances.
    
    Provides a centralized way to create and manage repository instances
    with shared database connection.
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self._db_manager = db_manager or get_database_manager()
        self._repositories: Dict[str, BaseRepository] = {}
    
    def get_user_repository(self) -> UserRepository:
        """Get the user repository instance."""
        if "user" not in self._repositories:
            self._repositories["user"] = UserRepository(self._db_manager)
        return self._repositories["user"]
    
    def get_exchange_key_repository(self) -> ExchangeKeyRepository:
        """Get the exchange key repository instance."""
        if "exchange_key" not in self._repositories:
            self._repositories["exchange_key"] = ExchangeKeyRepository(self._db_manager)
        return self._repositories["exchange_key"]
    
    def get_strategy_repository(self) -> StrategyRepository:
        """Get the strategy repository instance."""
        if "strategy" not in self._repositories:
            self._repositories["strategy"] = StrategyRepository(self._db_manager)
        return self._repositories["strategy"]
    
    def get_backtest_record_repository(self) -> BacktestRecordRepository:
        """Get the backtest record repository instance."""
        if "backtest_record" not in self._repositories:
            self._repositories["backtest_record"] = BacktestRecordRepository(self._db_manager)
        return self._repositories["backtest_record"]
    
    def get_backtest_result_repository(self) -> BacktestResultRepository:
        """Get the backtest result repository instance."""
        if "backtest_result" not in self._repositories:
            self._repositories["backtest_result"] = BacktestResultRepository(self._db_manager)
        return self._repositories["backtest_result"]
    
    def get_snapshot_repository(self) -> SnapshotRepository:
        """Get the snapshot repository instance."""
        if "snapshot" not in self._repositories:
            self._repositories["snapshot"] = SnapshotRepository(self._db_manager)
        return self._repositories["snapshot"]
    
    def get_alert_config_repository(self) -> AlertConfigRepository:
        """Get the alert config repository instance."""
        if "alert_config" not in self._repositories:
            self._repositories["alert_config"] = AlertConfigRepository(self._db_manager)
        return self._repositories["alert_config"]
    
    def get_data_provider_repository(self) -> DataProviderRepository:
        """Get the data provider repository instance."""
        if "data_provider" not in self._repositories:
            self._repositories["data_provider"] = DataProviderRepository(self._db_manager)
        return self._repositories["data_provider"]


# Singleton factory instance
_factory_instance: Optional[RepositoryFactory] = None


def get_repository_factory(db_manager: Optional[DatabaseManager] = None) -> RepositoryFactory:
    """Get the repository factory singleton instance."""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = RepositoryFactory(db_manager)
    return _factory_instance


def reset_repository_factory() -> None:
    """Reset the repository factory singleton (for testing)."""
    global _factory_instance
    _factory_instance = None


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Enums
    "UserRole",
    "BacktestStatus",
    "AlertType",
    "AlertSeverity",
    "ProviderType",
    # Data Models
    "User",
    "ExchangeKey",
    "Strategy",
    "BacktestRecord",
    "BacktestResult",
    "Snapshot",
    "AlertConfig",
    "DataProvider",
    # Database Manager
    "DatabaseManager",
    "get_database_manager",
    "reset_database_manager",
    # Repositories
    "BaseRepository",
    "UserRepository",
    "ExchangeKeyRepository",
    "StrategyRepository",
    "BacktestRecordRepository",
    "BacktestResultRepository",
    "SnapshotRepository",
    "AlertConfigRepository",
    "DataProviderRepository",
    # Factory
    "RepositoryFactory",
    "get_repository_factory",
    "reset_repository_factory",
]
