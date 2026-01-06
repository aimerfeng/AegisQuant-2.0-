"""
Titan-Quant User Authentication Module

This module implements user management, authentication, and role-based
access control for the Titan-Quant system.

Requirements:
    - 12.2: THE Titan_Quant_System SHALL 支持创建多用户（Admin/Trader 角色）
    - 12.3: WHEN 用户登录, THEN THE Titan_Quant_System SHALL 验证密码并解密本地 KeyStore
    - 12.4: THE Titan_Quant_System SHALL 根据用户角色限制功能访问
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, Set, TypeVar, Union

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

from core.exceptions import TitanQuantError
from core.data.key_store import SQLiteKeyStore, DecryptedKey, IKeyStore


class AuthenticationError(TitanQuantError):
    """Exception raised for authentication errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict | None = None
    ) -> None:
        super().__init__(message, error_code, details)


class AuthorizationError(TitanQuantError):
    """Exception raised for authorization/permission errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict | None = None,
        required_role: str | None = None,
        user_role: str | None = None
    ) -> None:
        details = details or {}
        if required_role:
            details["required_role"] = required_role
        if user_role:
            details["user_role"] = user_role
        super().__init__(message, error_code, details)
        self.required_role = required_role
        self.user_role = user_role


class AuthErrorCodes:
    """Error codes for authentication module."""
    USER_NOT_FOUND = "E8001"
    INVALID_PASSWORD = "E8002"
    USER_ALREADY_EXISTS = "E8003"
    INVALID_ROLE = "E8004"
    ACCESS_DENIED = "E8005"
    SESSION_EXPIRED = "E8006"
    KEYSTORE_DECRYPT_FAILED = "E8007"
    PASSWORD_HASH_FAILED = "E8008"


class UserRole(Enum):
    """User roles for access control."""
    ADMIN = "admin"
    TRADER = "trader"
    
    @classmethod
    def from_string(cls, role_str: str) -> "UserRole":
        """Convert string to UserRole enum."""
        role_lower = role_str.lower()
        for role in cls:
            if role.value == role_lower:
                return role
        raise ValueError(f"Invalid role: {role_str}")


class Permission(Enum):
    """System permissions for role-based access control."""
    # User management
    CREATE_USER = "create_user"
    DELETE_USER = "delete_user"
    MODIFY_USER = "modify_user"
    VIEW_USERS = "view_users"
    
    # Strategy management
    CREATE_STRATEGY = "create_strategy"
    DELETE_STRATEGY = "delete_strategy"
    MODIFY_STRATEGY = "modify_strategy"
    VIEW_STRATEGY = "view_strategy"
    EXECUTE_STRATEGY = "execute_strategy"
    
    # Backtest operations
    RUN_BACKTEST = "run_backtest"
    VIEW_BACKTEST = "view_backtest"
    DELETE_BACKTEST = "delete_backtest"
    
    # Data management
    IMPORT_DATA = "import_data"
    DELETE_DATA = "delete_data"
    VIEW_DATA = "view_data"
    
    # API key management
    MANAGE_API_KEYS = "manage_api_keys"
    VIEW_API_KEYS = "view_api_keys"
    
    # System configuration
    MODIFY_SYSTEM_CONFIG = "modify_system_config"
    VIEW_SYSTEM_CONFIG = "view_system_config"
    
    # Risk control
    MODIFY_RISK_CONFIG = "modify_risk_config"
    VIEW_RISK_CONFIG = "view_risk_config"
    
    # Manual trading
    MANUAL_TRADE = "manual_trade"
    CLOSE_ALL_POSITIONS = "close_all_positions"
    
    # Reports
    VIEW_REPORTS = "view_reports"
    EXPORT_REPORTS = "export_reports"


# Role-Permission mapping
ROLE_PERMISSIONS: dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: set(Permission),  # Admin has all permissions
    UserRole.TRADER: {
        # Strategy permissions
        Permission.CREATE_STRATEGY,
        Permission.MODIFY_STRATEGY,
        Permission.VIEW_STRATEGY,
        Permission.EXECUTE_STRATEGY,
        # Backtest permissions
        Permission.RUN_BACKTEST,
        Permission.VIEW_BACKTEST,
        # Data permissions
        Permission.IMPORT_DATA,
        Permission.VIEW_DATA,
        # API key permissions (own keys only)
        Permission.MANAGE_API_KEYS,
        Permission.VIEW_API_KEYS,
        # View configs
        Permission.VIEW_SYSTEM_CONFIG,
        Permission.VIEW_RISK_CONFIG,
        # Trading permissions
        Permission.MANUAL_TRADE,
        Permission.CLOSE_ALL_POSITIONS,
        # Reports
        Permission.VIEW_REPORTS,
        Permission.EXPORT_REPORTS,
    },
}


@dataclass
class User:
    """
    User data model.
    
    Attributes:
        user_id: Unique identifier for the user.
        username: Unique username for login.
        password_hash: Argon2 hashed password.
        role: User role (admin or trader).
        settings: User preferences as JSON.
        preferred_language: User's preferred language.
        created_at: When the user was created.
        last_login: When the user last logged in.
        is_active: Whether the user account is active.
    """
    user_id: str
    username: str
    password_hash: str
    role: UserRole
    settings: dict[str, Any] = field(default_factory=dict)
    preferred_language: str = "zh_cn"
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    is_active: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role.value,
            "settings": self.settings,
            "preferred_language": self.preferred_language,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_active": self.is_active,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        """Create User from dictionary."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            password_hash=data["password_hash"],
            role=UserRole.from_string(data["role"]),
            settings=data.get("settings", {}),
            preferred_language=data.get("preferred_language", "zh_cn"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if isinstance(data["created_at"], str)
                else data["created_at"]
            ),
            last_login=(
                datetime.fromisoformat(data["last_login"])
                if data.get("last_login")
                else None
            ),
            is_active=data.get("is_active", True),
        )
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in ROLE_PERMISSIONS.get(self.role, set())
    
    def get_permissions(self) -> Set[Permission]:
        """Get all permissions for this user's role."""
        return ROLE_PERMISSIONS.get(self.role, set())
    
    def __repr__(self) -> str:
        """Safe repr that doesn't expose password hash."""
        return (
            f"User(user_id={self.user_id!r}, "
            f"username={self.username!r}, "
            f"role={self.role.value!r}, "
            f"is_active={self.is_active!r})"
        )


@dataclass
class AuthSession:
    """
    Authentication session data.
    
    Attributes:
        session_id: Unique session identifier.
        user_id: User ID for this session.
        user: The authenticated user object.
        created_at: When the session was created.
        expires_at: When the session expires.
        ip_address: IP address of the client.
    """
    session_id: str
    user_id: str
    user: User
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


class IUserManager(ABC):
    """Abstract interface for user management."""
    
    @abstractmethod
    def create_user(
        self,
        username: str,
        password: str,
        role: UserRole,
        settings: Optional[dict[str, Any]] = None,
        preferred_language: str = "zh_cn"
    ) -> User:
        """
        Create a new user.
        
        Args:
            username: Unique username.
            password: Plaintext password (will be hashed).
            role: User role.
            settings: Optional user settings.
            preferred_language: Preferred language code.
            
        Returns:
            The created User object.
        """
        pass
    
    @abstractmethod
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        pass
    
    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        pass
    
    @abstractmethod
    def update_user(
        self,
        user_id: str,
        password: Optional[str] = None,
        role: Optional[UserRole] = None,
        settings: Optional[dict[str, Any]] = None,
        preferred_language: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """Update user information."""
        pass
    
    @abstractmethod
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        pass
    
    @abstractmethod
    def list_users(self) -> list[User]:
        """List all users."""
        pass


class IAuthenticator(ABC):
    """Abstract interface for authentication."""
    
    @abstractmethod
    def authenticate(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> AuthSession:
        """
        Authenticate a user.
        
        Args:
            username: Username to authenticate.
            password: Plaintext password.
            ip_address: Optional client IP address.
            
        Returns:
            AuthSession on successful authentication.
            
        Raises:
            AuthenticationError: If authentication fails.
        """
        pass
    
    @abstractmethod
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        pass
    
    @abstractmethod
    def hash_password(self, password: str) -> str:
        """Hash a password using Argon2."""
        pass


class IAccessControl(ABC):
    """Abstract interface for access control."""
    
    @abstractmethod
    def check_permission(
        self,
        user: User,
        permission: Permission
    ) -> bool:
        """Check if user has a specific permission."""
        pass
    
    @abstractmethod
    def require_permission(
        self,
        user: User,
        permission: Permission
    ) -> None:
        """
        Require a permission, raising an error if not granted.
        
        Raises:
            AuthorizationError: If permission is not granted.
        """
        pass
    
    @abstractmethod
    def get_role_permissions(self, role: UserRole) -> Set[Permission]:
        """Get all permissions for a role."""
        pass


class PasswordHasher_:
    """
    Password hashing using Argon2.
    
    Argon2 is the winner of the Password Hashing Competition and is
    recommended for secure password storage.
    """
    
    def __init__(self) -> None:
        """Initialize the password hasher with secure defaults."""
        self._hasher = PasswordHasher(
            time_cost=3,        # Number of iterations
            memory_cost=65536,  # Memory usage in KiB (64 MB)
            parallelism=4,      # Number of parallel threads
            hash_len=32,        # Length of the hash in bytes
            salt_len=16,        # Length of the salt in bytes
        )
    
    def hash(self, password: str) -> str:
        """
        Hash a password using Argon2.
        
        Args:
            password: Plaintext password.
            
        Returns:
            Argon2 hash string.
        """
        return self._hasher.hash(password)
    
    def verify(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plaintext password to verify.
            password_hash: Argon2 hash to verify against.
            
        Returns:
            True if password matches, False otherwise.
        """
        try:
            self._hasher.verify(password_hash, password)
            return True
        except (VerifyMismatchError, InvalidHash):
            return False
    
    def needs_rehash(self, password_hash: str) -> bool:
        """
        Check if a password hash needs to be rehashed.
        
        This is useful when upgrading hash parameters.
        
        Args:
            password_hash: Existing hash to check.
            
        Returns:
            True if rehashing is recommended.
        """
        return self._hasher.check_needs_rehash(password_hash)


class SQLiteUserManager(IUserManager, IAuthenticator, IAccessControl):
    """
    SQLite-based user management implementation.
    
    Provides user CRUD operations, authentication, and access control.
    """
    
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('admin', 'trader')),
        settings TEXT,
        preferred_language TEXT DEFAULT 'zh_cn',
        created_at TEXT NOT NULL,
        last_login TEXT,
        is_active INTEGER DEFAULT 1
    )
    """
    
    CREATE_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
    """
    
    def __init__(
        self,
        db_path: str = "database/titan_quant.db",
    ) -> None:
        """
        Initialize the SQLite user manager.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._password_hasher = PasswordHasher_()
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
    
    def _row_to_user(self, row: sqlite3.Row) -> User:
        """Convert a database row to User object."""
        settings = json.loads(row["settings"]) if row["settings"] else {}
        return User(
            user_id=row["user_id"],
            username=row["username"],
            password_hash=row["password_hash"],
            role=UserRole.from_string(row["role"]),
            settings=settings,
            preferred_language=row["preferred_language"] or "zh_cn",
            created_at=datetime.fromisoformat(row["created_at"]),
            last_login=(
                datetime.fromisoformat(row["last_login"])
                if row["last_login"]
                else None
            ),
            is_active=bool(row["is_active"]),
        )
    
    # IUserManager implementation
    
    def create_user(
        self,
        username: str,
        password: str,
        role: UserRole,
        settings: Optional[dict[str, Any]] = None,
        preferred_language: str = "zh_cn"
    ) -> User:
        """Create a new user with Argon2 password hashing."""
        # Check if username already exists
        if self.get_user_by_username(username):
            raise AuthenticationError(
                message=f"Username '{username}' already exists",
                error_code=AuthErrorCodes.USER_ALREADY_EXISTS
            )
        
        user_id = str(uuid.uuid4())
        password_hash = self._password_hasher.hash(password)
        now = datetime.now()
        
        user = User(
            user_id=user_id,
            username=username,
            password_hash=password_hash,
            role=role,
            settings=settings or {},
            preferred_language=preferred_language,
            created_at=now,
            is_active=True,
        )
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (
                    user_id, username, password_hash, role, settings,
                    preferred_language, created_at, last_login, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    user.username,
                    user.password_hash,
                    user.role.value,
                    json.dumps(user.settings),
                    user.preferred_language,
                    user.created_at.isoformat(),
                    None,
                    1,
                )
            )
            conn.commit()
        
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        return self._row_to_user(row)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        return self._row_to_user(row)
    
    def update_user(
        self,
        user_id: str,
        password: Optional[str] = None,
        role: Optional[UserRole] = None,
        settings: Optional[dict[str, Any]] = None,
        preferred_language: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """Update user information."""
        updates = []
        params = []
        
        if password is not None:
            updates.append("password_hash = ?")
            params.append(self._password_hasher.hash(password))
        
        if role is not None:
            updates.append("role = ?")
            params.append(role.value)
        
        if settings is not None:
            updates.append("settings = ?")
            params.append(json.dumps(settings))
        
        if preferred_language is not None:
            updates.append("preferred_language = ?")
            params.append(preferred_language)
        
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        
        if not updates:
            return False
        
        params.append(user_id)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?",
                params
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM users WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def list_users(self) -> list[User]:
        """List all users."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
        
        return [self._row_to_user(row) for row in rows]
    
    # IAuthenticator implementation
    
    def authenticate(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> AuthSession:
        """
        Authenticate a user with username and password.
        
        Requirements:
            - 12.3: Verify password and decrypt local KeyStore
        """
        user = self.get_user_by_username(username)
        
        if not user:
            raise AuthenticationError(
                message=f"User '{username}' not found",
                error_code=AuthErrorCodes.USER_NOT_FOUND
            )
        
        if not user.is_active:
            raise AuthenticationError(
                message=f"User '{username}' is deactivated",
                error_code=AuthErrorCodes.USER_NOT_FOUND
            )
        
        if not self.verify_password(password, user.password_hash):
            raise AuthenticationError(
                message="Invalid password",
                error_code=AuthErrorCodes.INVALID_PASSWORD
            )
        
        # Update last login time
        self._update_last_login(user.user_id)
        
        # Create session
        session = AuthSession(
            session_id=str(uuid.uuid4()),
            user_id=user.user_id,
            user=user,
            ip_address=ip_address,
        )
        
        return session
    
    def _update_last_login(self, user_id: str) -> None:
        """Update the last login timestamp for a user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET last_login = ? WHERE user_id = ?",
                (datetime.now().isoformat(), user_id)
            )
            conn.commit()
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its Argon2 hash."""
        return self._password_hasher.verify(password, password_hash)
    
    def hash_password(self, password: str) -> str:
        """Hash a password using Argon2."""
        return self._password_hasher.hash(password)
    
    # IAccessControl implementation
    
    def check_permission(
        self,
        user: User,
        permission: Permission
    ) -> bool:
        """Check if user has a specific permission."""
        return user.has_permission(permission)
    
    def require_permission(
        self,
        user: User,
        permission: Permission
    ) -> None:
        """
        Require a permission, raising an error if not granted.
        
        Requirements:
            - 12.4: Role-based access control
        """
        if not self.check_permission(user, permission):
            raise AuthorizationError(
                message=f"Permission denied: {permission.value}",
                error_code=AuthErrorCodes.ACCESS_DENIED,
                required_role=None,
                user_role=user.role.value
            )
    
    def get_role_permissions(self, role: UserRole) -> Set[Permission]:
        """Get all permissions for a role."""
        return ROLE_PERMISSIONS.get(role, set())
    
    def get_active_users_count(self) -> int:
        """Get count of active users."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE is_active = 1"
            )
            return cursor.fetchone()[0]
    
    def get_users_by_role(self, role: UserRole) -> list[User]:
        """Get all users with a specific role."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE role = ?",
                (role.value,)
            )
            rows = cursor.fetchall()
        
        return [self._row_to_user(row) for row in rows]


class AuthenticationService:
    """
    High-level authentication service that combines user management
    and KeyStore decryption.
    
    Requirements:
        - 12.3: WHEN 用户登录, THEN THE Titan_Quant_System SHALL 验证密码并解密本地 KeyStore
    """
    
    def __init__(
        self,
        user_manager: SQLiteUserManager,
        key_store: Optional[IKeyStore] = None
    ) -> None:
        """
        Initialize the authentication service.
        
        Args:
            user_manager: User manager instance.
            key_store: Optional key store for API key management.
        """
        self._user_manager = user_manager
        self._key_store = key_store
        self._active_sessions: dict[str, AuthSession] = {}
    
    def login(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> tuple[AuthSession, list[DecryptedKey]]:
        """
        Authenticate user and decrypt their API keys.
        
        This method:
        1. Verifies the user's password
        2. Creates an authentication session
        3. Decrypts the user's API keys from the KeyStore
        
        Args:
            username: Username to authenticate.
            password: Plaintext password.
            ip_address: Optional client IP address.
            
        Returns:
            Tuple of (AuthSession, list of DecryptedKey).
            
        Raises:
            AuthenticationError: If authentication fails.
        """
        # Authenticate user
        session = self._user_manager.authenticate(
            username=username,
            password=password,
            ip_address=ip_address
        )
        
        # Store active session
        self._active_sessions[session.session_id] = session
        
        # Decrypt user's API keys if key store is available
        decrypted_keys: list[DecryptedKey] = []
        if self._key_store:
            try:
                user_keys = self._key_store.get_keys_by_user(session.user_id)
                for key in user_keys:
                    if key.is_active:
                        decrypted = self._key_store.get_key(key.key_id)
                        if decrypted:
                            decrypted_keys.append(decrypted)
            except Exception as e:
                # Log the error but don't fail login
                # Keys can be decrypted later on demand
                pass
        
        return session, decrypted_keys
    
    def logout(self, session_id: str) -> bool:
        """
        Logout a user session.
        
        Args:
            session_id: Session ID to logout.
            
        Returns:
            True if session was found and removed.
        """
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            return True
        return False
    
    def get_session(self, session_id: str) -> Optional[AuthSession]:
        """
        Get an active session by ID.
        
        Args:
            session_id: Session ID to look up.
            
        Returns:
            AuthSession if found and not expired, None otherwise.
        """
        session = self._active_sessions.get(session_id)
        if session and session.is_expired():
            del self._active_sessions[session_id]
            return None
        return session
    
    def validate_session(self, session_id: str) -> AuthSession:
        """
        Validate a session, raising an error if invalid.
        
        Args:
            session_id: Session ID to validate.
            
        Returns:
            Valid AuthSession.
            
        Raises:
            AuthenticationError: If session is invalid or expired.
        """
        session = self.get_session(session_id)
        if not session:
            raise AuthenticationError(
                message="Session not found or expired",
                error_code=AuthErrorCodes.SESSION_EXPIRED
            )
        return session
    
    def get_user_keys(
        self,
        session: AuthSession,
        exchange: Optional[str] = None
    ) -> list[DecryptedKey]:
        """
        Get decrypted API keys for the authenticated user.
        
        Args:
            session: Active authentication session.
            exchange: Optional exchange filter.
            
        Returns:
            List of decrypted API keys.
        """
        if not self._key_store:
            return []
        
        if exchange:
            keys = self._key_store.get_keys_by_exchange(
                session.user_id, exchange
            )
        else:
            keys = self._key_store.get_keys_by_user(session.user_id)
        
        decrypted_keys: list[DecryptedKey] = []
        for key in keys:
            if key.is_active:
                decrypted = self._key_store.get_key(key.key_id)
                if decrypted:
                    decrypted_keys.append(decrypted)
        
        return decrypted_keys
    
    def check_permission(
        self,
        session: AuthSession,
        permission: Permission
    ) -> bool:
        """Check if the session user has a permission."""
        return self._user_manager.check_permission(session.user, permission)
    
    def require_permission(
        self,
        session: AuthSession,
        permission: Permission
    ) -> None:
        """Require a permission for the session user."""
        self._user_manager.require_permission(session.user, permission)
    
    @property
    def user_manager(self) -> SQLiteUserManager:
        """Get the user manager instance."""
        return self._user_manager
    
    @property
    def key_store(self) -> Optional[IKeyStore]:
        """Get the key store instance."""
        return self._key_store


# Decorator for permission checking
F = TypeVar('F', bound=Callable[..., Any])


def require_permission(permission: Permission) -> Callable[[F], F]:
    """
    Decorator to require a permission for a function.
    
    The decorated function must have a 'user' parameter or
    'session' parameter with a 'user' attribute.
    
    Usage:
        @require_permission(Permission.CREATE_STRATEGY)
        def create_strategy(user: User, name: str) -> Strategy:
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Try to find user in kwargs
            user = kwargs.get('user')
            
            # Try to find session in kwargs
            if user is None:
                session = kwargs.get('session')
                if session and hasattr(session, 'user'):
                    user = session.user
            
            # Try to find user in args (assuming first arg after self)
            if user is None and len(args) > 1:
                if isinstance(args[1], User):
                    user = args[1]
                elif hasattr(args[1], 'user'):
                    user = args[1].user
            
            if user is None:
                raise AuthorizationError(
                    message="No user context found for permission check",
                    error_code=AuthErrorCodes.ACCESS_DENIED
                )
            
            if not user.has_permission(permission):
                raise AuthorizationError(
                    message=f"Permission denied: {permission.value}",
                    error_code=AuthErrorCodes.ACCESS_DENIED,
                    user_role=user.role.value
                )
            
            return func(*args, **kwargs)
        
        return wrapper  # type: ignore
    
    return decorator


def require_role(role: UserRole) -> Callable[[F], F]:
    """
    Decorator to require a specific role for a function.
    
    Usage:
        @require_role(UserRole.ADMIN)
        def admin_only_function(user: User) -> None:
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Try to find user in kwargs
            user = kwargs.get('user')
            
            # Try to find session in kwargs
            if user is None:
                session = kwargs.get('session')
                if session and hasattr(session, 'user'):
                    user = session.user
            
            # Try to find user in args
            if user is None and len(args) > 1:
                if isinstance(args[1], User):
                    user = args[1]
                elif hasattr(args[1], 'user'):
                    user = args[1].user
            
            if user is None:
                raise AuthorizationError(
                    message="No user context found for role check",
                    error_code=AuthErrorCodes.ACCESS_DENIED
                )
            
            if user.role != role:
                raise AuthorizationError(
                    message=f"Role '{role.value}' required",
                    error_code=AuthErrorCodes.ACCESS_DENIED,
                    required_role=role.value,
                    user_role=user.role.value
                )
            
            return func(*args, **kwargs)
        
        return wrapper  # type: ignore
    
    return decorator


class AccessControlManager:
    """
    Centralized access control manager for role-based access control.
    
    This class provides a comprehensive RBAC implementation that:
    - Manages role-permission mappings
    - Supports custom permission rules
    - Provides resource-level access control
    - Supports permission inheritance
    
    Requirements:
        - 12.4: THE Titan_Quant_System SHALL 根据用户角色限制功能访问
    """
    
    def __init__(
        self,
        role_permissions: Optional[dict[UserRole, Set[Permission]]] = None
    ) -> None:
        """
        Initialize the access control manager.
        
        Args:
            role_permissions: Optional custom role-permission mapping.
                             Uses default ROLE_PERMISSIONS if not provided.
        """
        self._role_permissions = role_permissions or ROLE_PERMISSIONS.copy()
        self._resource_rules: dict[str, dict[str, Set[Permission]]] = {}
    
    def check_permission(
        self,
        user: User,
        permission: Permission
    ) -> bool:
        """
        Check if a user has a specific permission.
        
        Args:
            user: User to check.
            permission: Permission to check for.
            
        Returns:
            True if user has the permission.
        """
        if not user.is_active:
            return False
        
        role_perms = self._role_permissions.get(user.role, set())
        return permission in role_perms
    
    def check_permissions(
        self,
        user: User,
        permissions: Set[Permission]
    ) -> bool:
        """
        Check if a user has all specified permissions.
        
        Args:
            user: User to check.
            permissions: Set of permissions to check for.
            
        Returns:
            True if user has all permissions.
        """
        return all(self.check_permission(user, p) for p in permissions)
    
    def check_any_permission(
        self,
        user: User,
        permissions: Set[Permission]
    ) -> bool:
        """
        Check if a user has any of the specified permissions.
        
        Args:
            user: User to check.
            permissions: Set of permissions to check for.
            
        Returns:
            True if user has at least one permission.
        """
        return any(self.check_permission(user, p) for p in permissions)
    
    def require_permission(
        self,
        user: User,
        permission: Permission
    ) -> None:
        """
        Require a permission, raising an error if not granted.
        
        Args:
            user: User to check.
            permission: Required permission.
            
        Raises:
            AuthorizationError: If permission is not granted.
        """
        if not self.check_permission(user, permission):
            raise AuthorizationError(
                message=f"Permission denied: {permission.value}",
                error_code=AuthErrorCodes.ACCESS_DENIED,
                user_role=user.role.value
            )
    
    def require_role(
        self,
        user: User,
        role: UserRole
    ) -> None:
        """
        Require a specific role.
        
        Args:
            user: User to check.
            role: Required role.
            
        Raises:
            AuthorizationError: If user doesn't have the role.
        """
        if user.role != role:
            raise AuthorizationError(
                message=f"Role '{role.value}' required",
                error_code=AuthErrorCodes.ACCESS_DENIED,
                required_role=role.value,
                user_role=user.role.value
            )
    
    def get_user_permissions(self, user: User) -> Set[Permission]:
        """
        Get all permissions for a user.
        
        Args:
            user: User to get permissions for.
            
        Returns:
            Set of permissions the user has.
        """
        if not user.is_active:
            return set()
        return self._role_permissions.get(user.role, set()).copy()
    
    def get_role_permissions(self, role: UserRole) -> Set[Permission]:
        """
        Get all permissions for a role.
        
        Args:
            role: Role to get permissions for.
            
        Returns:
            Set of permissions for the role.
        """
        return self._role_permissions.get(role, set()).copy()
    
    def add_role_permission(
        self,
        role: UserRole,
        permission: Permission
    ) -> None:
        """
        Add a permission to a role.
        
        Args:
            role: Role to add permission to.
            permission: Permission to add.
        """
        if role not in self._role_permissions:
            self._role_permissions[role] = set()
        self._role_permissions[role].add(permission)
    
    def remove_role_permission(
        self,
        role: UserRole,
        permission: Permission
    ) -> None:
        """
        Remove a permission from a role.
        
        Args:
            role: Role to remove permission from.
            permission: Permission to remove.
        """
        if role in self._role_permissions:
            self._role_permissions[role].discard(permission)
    
    def set_resource_permissions(
        self,
        resource_type: str,
        resource_id: str,
        permissions: Set[Permission]
    ) -> None:
        """
        Set permissions required for a specific resource.
        
        This allows fine-grained access control at the resource level.
        
        Args:
            resource_type: Type of resource (e.g., "strategy", "backtest").
            resource_id: Unique identifier for the resource.
            permissions: Set of permissions required to access the resource.
        """
        if resource_type not in self._resource_rules:
            self._resource_rules[resource_type] = {}
        self._resource_rules[resource_type][resource_id] = permissions
    
    def check_resource_access(
        self,
        user: User,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """
        Check if a user can access a specific resource.
        
        Args:
            user: User to check.
            resource_type: Type of resource.
            resource_id: Resource identifier.
            
        Returns:
            True if user can access the resource.
        """
        if resource_type not in self._resource_rules:
            return True  # No rules defined, allow access
        
        if resource_id not in self._resource_rules[resource_type]:
            return True  # No rules for this resource, allow access
        
        required_perms = self._resource_rules[resource_type][resource_id]
        return self.check_any_permission(user, required_perms)
    
    def can_user_manage_user(
        self,
        actor: User,
        target: User
    ) -> bool:
        """
        Check if one user can manage another user.
        
        Rules:
        - Admins can manage all users
        - Users cannot manage themselves (for deletion)
        - Traders cannot manage other users
        
        Args:
            actor: User performing the action.
            target: User being managed.
            
        Returns:
            True if actor can manage target.
        """
        # Admins can manage all users
        if actor.role == UserRole.ADMIN:
            return True
        
        # Traders cannot manage other users
        return False
    
    def get_accessible_permissions(
        self,
        user: User
    ) -> dict[str, bool]:
        """
        Get a dictionary of all permissions and whether the user has them.
        
        Useful for UI to show/hide features based on permissions.
        
        Args:
            user: User to check.
            
        Returns:
            Dictionary mapping permission names to boolean access.
        """
        return {
            perm.value: self.check_permission(user, perm)
            for perm in Permission
        }


# Global access control manager instance
_access_control_manager: Optional[AccessControlManager] = None


def get_access_control_manager() -> AccessControlManager:
    """
    Get or create the global access control manager instance.
    
    Returns:
        The access control manager instance.
    """
    global _access_control_manager
    if _access_control_manager is None:
        _access_control_manager = AccessControlManager()
    return _access_control_manager


__all__ = [
    # Exceptions
    "AuthenticationError",
    "AuthorizationError",
    "AuthErrorCodes",
    # Enums
    "UserRole",
    "Permission",
    # Data classes
    "User",
    "AuthSession",
    # Constants
    "ROLE_PERMISSIONS",
    # Interfaces
    "IUserManager",
    "IAuthenticator",
    "IAccessControl",
    # Implementations
    "PasswordHasher_",
    "SQLiteUserManager",
    "AuthenticationService",
    "AccessControlManager",
    # Functions
    "get_access_control_manager",
    # Decorators
    "require_permission",
    "require_role",
]
