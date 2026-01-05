"""
Titan-Quant Key Store Module

This module implements secure storage and retrieval of API keys
for exchange connections. All sensitive data is encrypted using
Fernet symmetric encryption before storage.

Requirements:
    - 13.1: THE Titan_Quant_System SHALL 使用 Fernet 对称加密存储 API Key 和邮箱密码
    - 13.2: THE Titan_Quant_System SHALL 将加密密钥存储在独立的 keyfile.key 文件中
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from utils.encrypt import FernetEncryption, EncryptionError


class Permission(Enum):
    """API key permissions."""
    READ = "read"
    TRADE = "trade"
    WITHDRAW = "withdraw"


@dataclass
class ExchangeKey:
    """
    Exchange API key data model.
    
    Stores encrypted API credentials for exchange connections.
    All sensitive fields (api_key, secret_key, passphrase) are
    stored as ciphertext.
    
    Attributes:
        key_id: Unique identifier for this key entry.
        user_id: User who owns this key.
        exchange: Exchange name (e.g., "binance", "okx").
        api_key_name: User-defined name for this key.
        api_key_ciphertext: Encrypted API key.
        secret_key_ciphertext: Encrypted secret key.
        passphrase_ciphertext: Encrypted passphrase (optional).
        permissions: List of permissions for this key.
        is_active: Whether this key is currently active.
        created_at: When this key was created.
        updated_at: When this key was last updated.
    """
    key_id: str
    user_id: str
    exchange: str
    api_key_name: str
    api_key_ciphertext: str
    secret_key_ciphertext: str
    passphrase_ciphertext: Optional[str] = None
    permissions: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key_id": self.key_id,
            "user_id": self.user_id,
            "exchange": self.exchange,
            "api_key_name": self.api_key_name,
            "api_key_ciphertext": self.api_key_ciphertext,
            "secret_key_ciphertext": self.secret_key_ciphertext,
            "passphrase_ciphertext": self.passphrase_ciphertext,
            "permissions": self.permissions,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExchangeKey:
        """Create ExchangeKey from dictionary."""
        return cls(
            key_id=data["key_id"],
            user_id=data["user_id"],
            exchange=data["exchange"],
            api_key_name=data["api_key_name"],
            api_key_ciphertext=data["api_key_ciphertext"],
            secret_key_ciphertext=data["secret_key_ciphertext"],
            passphrase_ciphertext=data.get("passphrase_ciphertext"),
            permissions=data.get("permissions", []),
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"],
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )


@dataclass
class DecryptedKey:
    """
    Decrypted API key data for use in memory.
    
    This class holds the plaintext API credentials after decryption.
    It should only exist in memory and never be persisted or logged.
    
    Attributes:
        key_id: Unique identifier for this key entry.
        user_id: User who owns this key.
        exchange: Exchange name.
        api_key_name: User-defined name.
        api_key: Plaintext API key.
        secret_key: Plaintext secret key.
        passphrase: Plaintext passphrase (optional).
        permissions: List of permissions.
    """
    key_id: str
    user_id: str
    exchange: str
    api_key_name: str
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None
    permissions: list[str] = field(default_factory=list)
    
    def __repr__(self) -> str:
        """Safe repr that doesn't expose sensitive data."""
        return (
            f"DecryptedKey(key_id={self.key_id!r}, "
            f"user_id={self.user_id!r}, "
            f"exchange={self.exchange!r}, "
            f"api_key_name={self.api_key_name!r}, "
            f"api_key=[REDACTED], "
            f"secret_key=[REDACTED], "
            f"passphrase=[REDACTED], "
            f"permissions={self.permissions!r})"
        )
    
    def __str__(self) -> str:
        """Safe str that doesn't expose sensitive data."""
        return self.__repr__()


class IKeyStore(ABC):
    """Abstract interface for key storage."""
    
    @abstractmethod
    def store_key(
        self,
        user_id: str,
        exchange: str,
        api_key_name: str,
        api_key: str,
        secret_key: str,
        passphrase: Optional[str] = None,
        permissions: Optional[list[str]] = None
    ) -> str:
        """
        Store a new API key.
        
        Args:
            user_id: User who owns this key.
            exchange: Exchange name.
            api_key_name: User-defined name.
            api_key: Plaintext API key (will be encrypted).
            secret_key: Plaintext secret key (will be encrypted).
            passphrase: Optional passphrase (will be encrypted).
            permissions: List of permissions.
            
        Returns:
            The key_id of the stored key.
        """
        pass
    
    @abstractmethod
    def get_key(self, key_id: str) -> Optional[DecryptedKey]:
        """
        Retrieve and decrypt an API key.
        
        Args:
            key_id: The key identifier.
            
        Returns:
            Decrypted key data, or None if not found.
        """
        pass
    
    @abstractmethod
    def get_keys_by_user(self, user_id: str) -> list[ExchangeKey]:
        """
        Get all keys for a user (encrypted).
        
        Args:
            user_id: The user identifier.
            
        Returns:
            List of encrypted key entries.
        """
        pass
    
    @abstractmethod
    def get_keys_by_exchange(
        self,
        user_id: str,
        exchange: str
    ) -> list[ExchangeKey]:
        """
        Get all keys for a user and exchange (encrypted).
        
        Args:
            user_id: The user identifier.
            exchange: The exchange name.
            
        Returns:
            List of encrypted key entries.
        """
        pass
    
    @abstractmethod
    def update_key(
        self,
        key_id: str,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        passphrase: Optional[str] = None,
        permissions: Optional[list[str]] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """
        Update an existing API key.
        
        Args:
            key_id: The key identifier.
            api_key: New API key (will be encrypted).
            secret_key: New secret key (will be encrypted).
            passphrase: New passphrase (will be encrypted).
            permissions: New permissions list.
            is_active: New active status.
            
        Returns:
            True if update was successful.
        """
        pass
    
    @abstractmethod
    def delete_key(self, key_id: str) -> bool:
        """
        Delete an API key.
        
        Args:
            key_id: The key identifier.
            
        Returns:
            True if deletion was successful.
        """
        pass
    
    @abstractmethod
    def deactivate_key(self, key_id: str) -> bool:
        """
        Deactivate an API key without deleting it.
        
        Args:
            key_id: The key identifier.
            
        Returns:
            True if deactivation was successful.
        """
        pass
    
    @abstractmethod
    def has_permission(self, key_id: str, permission: str) -> bool:
        """
        Check if a key has a specific permission.
        
        Args:
            key_id: The key identifier.
            permission: The permission to check.
            
        Returns:
            True if the key has the permission.
        """
        pass


class SQLiteKeyStore(IKeyStore):
    """
    SQLite-based key store implementation.
    
    Stores encrypted API keys in a SQLite database with the schema
    defined in the design document.
    """
    
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS exchange_keys (
        key_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        exchange TEXT NOT NULL,
        api_key_name TEXT NOT NULL,
        api_key_ciphertext TEXT NOT NULL,
        secret_key_ciphertext TEXT NOT NULL,
        passphrase_ciphertext TEXT,
        permissions TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT
    )
    """
    
    CREATE_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS idx_exchange_keys_user_id 
    ON exchange_keys(user_id);
    
    CREATE INDEX IF NOT EXISTS idx_exchange_keys_exchange 
    ON exchange_keys(user_id, exchange);
    """
    
    def __init__(
        self,
        db_path: str = "database/titan_quant.db",
        encryption_service: Optional[FernetEncryption] = None,
        key_dir: str = "config"
    ) -> None:
        """
        Initialize the SQLite key store.
        
        Args:
            db_path: Path to the SQLite database file.
            encryption_service: Optional encryption service instance.
            key_dir: Directory for the encryption key file.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption service
        if encryption_service:
            self._encryption = encryption_service
        else:
            self._encryption = FernetEncryption(key_dir=key_dir)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(self.CREATE_TABLE_SQL)
            cursor.executescript(self.CREATE_INDEX_SQL)
            conn.commit()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def store_key(
        self,
        user_id: str,
        exchange: str,
        api_key_name: str,
        api_key: str,
        secret_key: str,
        passphrase: Optional[str] = None,
        permissions: Optional[list[str]] = None
    ) -> str:
        """Store a new API key with encryption."""
        key_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Encrypt sensitive data
        api_key_ciphertext = self._encryption.encrypt(api_key)
        secret_key_ciphertext = self._encryption.encrypt(secret_key)
        passphrase_ciphertext = (
            self._encryption.encrypt(passphrase) if passphrase else None
        )
        
        # Serialize permissions
        permissions_json = json.dumps(permissions or [])
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO exchange_keys (
                    key_id, user_id, exchange, api_key_name,
                    api_key_ciphertext, secret_key_ciphertext,
                    passphrase_ciphertext, permissions, is_active,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key_id, user_id, exchange, api_key_name,
                    api_key_ciphertext, secret_key_ciphertext,
                    passphrase_ciphertext, permissions_json, 1,
                    now.isoformat(), None
                )
            )
            conn.commit()
        
        return key_id
    
    def get_key(self, key_id: str) -> Optional[DecryptedKey]:
        """Retrieve and decrypt an API key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM exchange_keys WHERE key_id = ? AND is_active = 1",
                (key_id,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        # Decrypt sensitive data
        try:
            api_key = self._encryption.decrypt(row["api_key_ciphertext"])
            secret_key = self._encryption.decrypt(row["secret_key_ciphertext"])
            passphrase = (
                self._encryption.decrypt(row["passphrase_ciphertext"])
                if row["passphrase_ciphertext"]
                else None
            )
        except EncryptionError:
            return None
        
        # Parse permissions
        permissions = json.loads(row["permissions"]) if row["permissions"] else []
        
        return DecryptedKey(
            key_id=row["key_id"],
            user_id=row["user_id"],
            exchange=row["exchange"],
            api_key_name=row["api_key_name"],
            api_key=api_key,
            secret_key=secret_key,
            passphrase=passphrase,
            permissions=permissions
        )
    
    def get_keys_by_user(self, user_id: str) -> list[ExchangeKey]:
        """Get all keys for a user (encrypted)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM exchange_keys WHERE user_id = ?",
                (user_id,)
            )
            rows = cursor.fetchall()
        
        return [self._row_to_exchange_key(row) for row in rows]
    
    def get_keys_by_exchange(
        self,
        user_id: str,
        exchange: str
    ) -> list[ExchangeKey]:
        """Get all keys for a user and exchange (encrypted)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM exchange_keys WHERE user_id = ? AND exchange = ?",
                (user_id, exchange)
            )
            rows = cursor.fetchall()
        
        return [self._row_to_exchange_key(row) for row in rows]
    
    def _row_to_exchange_key(self, row: sqlite3.Row) -> ExchangeKey:
        """Convert a database row to ExchangeKey."""
        permissions = json.loads(row["permissions"]) if row["permissions"] else []
        
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
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=(
                datetime.fromisoformat(row["updated_at"])
                if row["updated_at"]
                else None
            )
        )
    
    def update_key(
        self,
        key_id: str,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        passphrase: Optional[str] = None,
        permissions: Optional[list[str]] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """Update an existing API key."""
        updates = []
        params = []
        
        if api_key is not None:
            updates.append("api_key_ciphertext = ?")
            params.append(self._encryption.encrypt(api_key))
        
        if secret_key is not None:
            updates.append("secret_key_ciphertext = ?")
            params.append(self._encryption.encrypt(secret_key))
        
        if passphrase is not None:
            updates.append("passphrase_ciphertext = ?")
            params.append(self._encryption.encrypt(passphrase))
        
        if permissions is not None:
            updates.append("permissions = ?")
            params.append(json.dumps(permissions))
        
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(key_id)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE exchange_keys SET {', '.join(updates)} WHERE key_id = ?",
                params
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_key(self, key_id: str) -> bool:
        """Delete an API key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM exchange_keys WHERE key_id = ?",
                (key_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def deactivate_key(self, key_id: str) -> bool:
        """Deactivate an API key without deleting it."""
        return self.update_key(key_id, is_active=False)
    
    def has_permission(self, key_id: str, permission: str) -> bool:
        """Check if a key has a specific permission."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT permissions FROM exchange_keys WHERE key_id = ? AND is_active = 1",
                (key_id,)
            )
            row = cursor.fetchone()
        
        if not row:
            return False
        
        permissions = json.loads(row["permissions"]) if row["permissions"] else []
        return permission in permissions
    
    def get_active_keys_count(self, user_id: str) -> int:
        """Get count of active keys for a user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM exchange_keys WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            return cursor.fetchone()[0]


__all__ = [
    "Permission",
    "ExchangeKey",
    "DecryptedKey",
    "IKeyStore",
    "SQLiteKeyStore",
]
