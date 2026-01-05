"""
Titan-Quant Encryption Module

This module implements Fernet symmetric encryption for sensitive data
such as API keys and passwords. It also provides a custom logging filter
to prevent sensitive data from appearing in logs.

Requirements:
    - 13.1: THE Titan_Quant_System SHALL 使用 Fernet 对称加密存储 API Key 和邮箱密码
    - 13.2: THE Titan_Quant_System SHALL 将加密密钥存储在独立的 keyfile.key 文件中
    - 13.3: WHEN 读取敏感配置, THEN THE Titan_Quant_System SHALL 在内存中解密，不在日志中输出明文
"""
from __future__ import annotations

import base64
import logging
import os
import re
import secrets
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Set

from cryptography.fernet import Fernet, InvalidToken

from core.exceptions import TitanQuantError


class EncryptionError(TitanQuantError):
    """Exception raised for encryption/decryption errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict | None = None
    ) -> None:
        super().__init__(message, error_code, details)


class ErrorCodes:
    """Error codes for encryption module."""
    KEY_NOT_FOUND = "E7001"
    KEY_GENERATION_FAILED = "E7002"
    ENCRYPTION_FAILED = "E7003"
    DECRYPTION_FAILED = "E7004"
    INVALID_KEY = "E7005"


class IEncryptionService(ABC):
    """Abstract interface for encryption service."""
    
    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext data.
        
        Args:
            plaintext: The data to encrypt.
            
        Returns:
            Base64-encoded ciphertext.
        """
        pass
    
    @abstractmethod
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext data.
        
        Args:
            ciphertext: Base64-encoded ciphertext.
            
        Returns:
            Decrypted plaintext.
        """
        pass
    
    @abstractmethod
    def generate_key(self) -> bytes:
        """
        Generate a new encryption key.
        
        Returns:
            The generated key bytes.
        """
        pass
    
    @abstractmethod
    def load_key(self) -> bytes:
        """
        Load the encryption key from storage.
        
        Returns:
            The loaded key bytes.
        """
        pass
    
    @abstractmethod
    def save_key(self, key: bytes) -> bool:
        """
        Save the encryption key to storage.
        
        Args:
            key: The key bytes to save.
            
        Returns:
            True if successful.
        """
        pass


class FernetEncryption(IEncryptionService):
    """
    Fernet symmetric encryption implementation.
    
    Uses the cryptography library's Fernet implementation which provides:
    - AES-128-CBC encryption
    - HMAC-SHA256 authentication
    - Timestamp-based token validation
    
    The encryption key is stored in a separate keyfile.key file.
    """
    
    DEFAULT_KEY_FILE = "keyfile.key"
    
    def __init__(
        self,
        key_dir: str = "config",
        key_file: str = DEFAULT_KEY_FILE,
        auto_generate: bool = True
    ) -> None:
        """
        Initialize the Fernet encryption service.
        
        Args:
            key_dir: Directory to store the key file.
            key_file: Name of the key file.
            auto_generate: If True, generate a key if none exists.
        """
        self._key_dir = Path(key_dir)
        self._key_file = key_file
        self._key_path = self._key_dir / self._key_file
        self._fernet: Optional[Fernet] = None
        
        # Ensure key directory exists
        self._key_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize the Fernet instance
        self._initialize(auto_generate)
    
    def _initialize(self, auto_generate: bool) -> None:
        """Initialize the Fernet instance with the key."""
        if self._key_path.exists():
            key = self.load_key()
        elif auto_generate:
            key = self.generate_key()
            self.save_key(key)
        else:
            raise EncryptionError(
                message=f"Key file not found: {self._key_path}",
                error_code=ErrorCodes.KEY_NOT_FOUND
            )
        
        try:
            self._fernet = Fernet(key)
        except Exception as e:
            raise EncryptionError(
                message=f"Invalid encryption key: {e}",
                error_code=ErrorCodes.INVALID_KEY
            )
    
    def generate_key(self) -> bytes:
        """
        Generate a new Fernet encryption key.
        
        Returns:
            A new 32-byte URL-safe base64-encoded key.
        """
        return Fernet.generate_key()
    
    def load_key(self) -> bytes:
        """
        Load the encryption key from the key file.
        
        Returns:
            The key bytes.
            
        Raises:
            EncryptionError: If the key file cannot be read.
        """
        try:
            with open(self._key_path, "rb") as f:
                return f.read().strip()
        except Exception as e:
            raise EncryptionError(
                message=f"Failed to load key from {self._key_path}: {e}",
                error_code=ErrorCodes.KEY_NOT_FOUND
            )
    
    def save_key(self, key: bytes) -> bool:
        """
        Save the encryption key to the key file.
        
        The key file is created with restricted permissions (owner read/write only).
        
        Args:
            key: The key bytes to save.
            
        Returns:
            True if successful.
            
        Raises:
            EncryptionError: If the key cannot be saved.
        """
        try:
            # Write key to file
            with open(self._key_path, "wb") as f:
                f.write(key)
            
            # Set restrictive permissions (Windows doesn't support chmod the same way)
            try:
                os.chmod(self._key_path, 0o600)
            except (OSError, AttributeError):
                # On Windows, chmod may not work as expected
                pass
            
            return True
        except Exception as e:
            raise EncryptionError(
                message=f"Failed to save key to {self._key_path}: {e}",
                error_code=ErrorCodes.KEY_GENERATION_FAILED
            )
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using Fernet.
        
        Args:
            plaintext: The string to encrypt.
            
        Returns:
            Base64-encoded ciphertext string.
            
        Raises:
            EncryptionError: If encryption fails.
        """
        if self._fernet is None:
            raise EncryptionError(
                message="Encryption service not initialized",
                error_code=ErrorCodes.ENCRYPTION_FAILED
            )
        
        try:
            plaintext_bytes = plaintext.encode("utf-8")
            ciphertext_bytes = self._fernet.encrypt(plaintext_bytes)
            return ciphertext_bytes.decode("utf-8")
        except Exception as e:
            raise EncryptionError(
                message=f"Encryption failed: {e}",
                error_code=ErrorCodes.ENCRYPTION_FAILED
            )
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext using Fernet.
        
        Args:
            ciphertext: Base64-encoded ciphertext string.
            
        Returns:
            Decrypted plaintext string.
            
        Raises:
            EncryptionError: If decryption fails.
        """
        if self._fernet is None:
            raise EncryptionError(
                message="Encryption service not initialized",
                error_code=ErrorCodes.DECRYPTION_FAILED
            )
        
        try:
            ciphertext_bytes = ciphertext.encode("utf-8")
            plaintext_bytes = self._fernet.decrypt(ciphertext_bytes)
            return plaintext_bytes.decode("utf-8")
        except InvalidToken:
            raise EncryptionError(
                message="Decryption failed: invalid token or corrupted data",
                error_code=ErrorCodes.DECRYPTION_FAILED
            )
        except Exception as e:
            raise EncryptionError(
                message=f"Decryption failed: {e}",
                error_code=ErrorCodes.DECRYPTION_FAILED
            )
    
    def get_key_path(self) -> Path:
        """Get the path to the key file."""
        return self._key_path
    
    def key_exists(self) -> bool:
        """Check if the key file exists."""
        return self._key_path.exists()
    
    def rotate_key(self) -> bytes:
        """
        Generate and save a new encryption key.
        
        WARNING: This will invalidate all previously encrypted data!
        
        Returns:
            The new key bytes.
        """
        new_key = self.generate_key()
        self.save_key(new_key)
        self._fernet = Fernet(new_key)
        return new_key


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that redacts sensitive data from log messages.
    
    This filter scans log messages for patterns that match sensitive data
    (API keys, passwords, secrets) and replaces them with redacted placeholders.
    
    Requirements:
        - 13.3: Sensitive data must not appear in logs
    """
    
    # Default patterns to redact
    DEFAULT_PATTERNS = [
        # API keys (various formats)
        r'(?i)(api[_-]?key|apikey)["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?',
        r'(?i)(secret[_-]?key|secretkey)["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?',
        r'(?i)(access[_-]?key|accesskey)["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?',
        # Passwords
        r'(?i)(password|passwd|pwd)["\s:=]+["\']?([^\s"\']{4,})["\']?',
        # Tokens
        r'(?i)(token|auth[_-]?token)["\s:=]+["\']?([a-zA-Z0-9_\-\.]{16,})["\']?',
        # Fernet encrypted data (base64 with specific prefix)
        r'gAAAAA[a-zA-Z0-9_\-=]{50,}',
        # Generic base64 encoded secrets (long strings)
        r'(?i)(secret|private[_-]?key)["\s:=]+["\']?([a-zA-Z0-9+/=]{32,})["\']?',
    ]
    
    # Placeholder for redacted content
    REDACTED = "[REDACTED]"
    
    def __init__(
        self,
        name: str = "",
        patterns: Optional[list[str]] = None,
        additional_patterns: Optional[list[str]] = None,
        sensitive_keys: Optional[Set[str]] = None
    ) -> None:
        """
        Initialize the sensitive data filter.
        
        Args:
            name: Filter name.
            patterns: Custom patterns to use (replaces defaults).
            additional_patterns: Additional patterns to add to defaults.
            sensitive_keys: Set of dictionary keys to always redact.
        """
        super().__init__(name)
        
        if patterns is not None:
            self._patterns = [re.compile(p) for p in patterns]
        else:
            self._patterns = [re.compile(p) for p in self.DEFAULT_PATTERNS]
        
        if additional_patterns:
            self._patterns.extend([re.compile(p) for p in additional_patterns])
        
        self._sensitive_keys = sensitive_keys or {
            "api_key", "apikey", "api-key",
            "secret_key", "secretkey", "secret-key",
            "password", "passwd", "pwd",
            "token", "auth_token", "access_token",
            "private_key", "privatekey",
            "passphrase",
            "api_key_ciphertext", "secret_key_ciphertext",
            "passphrase_ciphertext",
        }
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record by redacting sensitive data.
        
        Args:
            record: The log record to filter.
            
        Returns:
            True (always allows the record, but modifies it).
        """
        # Redact the message
        if record.msg:
            record.msg = self._redact_string(str(record.msg))
        
        # Redact args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = self._redact_dict(record.args)
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    self._redact_string(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        
        return True
    
    def _redact_string(self, text: str) -> str:
        """Redact sensitive patterns from a string."""
        result = text
        
        for pattern in self._patterns:
            # For patterns with groups, replace the sensitive part
            def replacer(match):
                groups = match.groups()
                if len(groups) >= 2:
                    # Replace the second group (the sensitive value)
                    return match.group(0).replace(groups[1], self.REDACTED)
                else:
                    # Replace the entire match
                    return self.REDACTED
            
            result = pattern.sub(replacer, result)
        
        return result
    
    def _redact_dict(self, data: dict) -> dict:
        """Redact sensitive keys from a dictionary."""
        result = {}
        for key, value in data.items():
            key_lower = str(key).lower().replace("-", "_")
            if key_lower in self._sensitive_keys:
                result[key] = self.REDACTED
            elif isinstance(value, str):
                result[key] = self._redact_string(value)
            elif isinstance(value, dict):
                result[key] = self._redact_dict(value)
            else:
                result[key] = value
        return result
    
    def add_pattern(self, pattern: str) -> None:
        """Add a new pattern to redact."""
        self._patterns.append(re.compile(pattern))
    
    def add_sensitive_key(self, key: str) -> None:
        """Add a new sensitive key to redact."""
        self._sensitive_keys.add(key.lower().replace("-", "_"))


def create_secure_logger(
    name: str,
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Create a logger with sensitive data filtering enabled.
    
    Args:
        name: Logger name.
        level: Logging level.
        format_string: Optional format string.
        
    Returns:
        Configured logger with SensitiveDataFilter.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Add handler if none exists
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        
        if format_string:
            formatter = logging.Formatter(format_string)
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


# Module-level encryption instance (lazy initialization)
_encryption_service: Optional[FernetEncryption] = None


def get_encryption_service(
    key_dir: str = "config",
    key_file: str = FernetEncryption.DEFAULT_KEY_FILE,
    auto_generate: bool = True
) -> FernetEncryption:
    """
    Get or create the global encryption service instance.
    
    Args:
        key_dir: Directory for the key file.
        key_file: Name of the key file.
        auto_generate: Whether to auto-generate a key if none exists.
        
    Returns:
        The encryption service instance.
    """
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = FernetEncryption(
            key_dir=key_dir,
            key_file=key_file,
            auto_generate=auto_generate
        )
    
    return _encryption_service


def encrypt(plaintext: str) -> str:
    """
    Encrypt plaintext using the global encryption service.
    
    Args:
        plaintext: The string to encrypt.
        
    Returns:
        Encrypted ciphertext.
    """
    return get_encryption_service().encrypt(plaintext)


def decrypt(ciphertext: str) -> str:
    """
    Decrypt ciphertext using the global encryption service.
    
    Args:
        ciphertext: The encrypted string.
        
    Returns:
        Decrypted plaintext.
    """
    return get_encryption_service().decrypt(ciphertext)


__all__ = [
    "EncryptionError",
    "ErrorCodes",
    "IEncryptionService",
    "FernetEncryption",
    "SensitiveDataFilter",
    "create_secure_logger",
    "get_encryption_service",
    "encrypt",
    "decrypt",
]
