"""
Property-Based Tests for Encryption Module

This module contains property-based tests using Hypothesis to verify
the correctness properties of the encryption implementation.

Properties tested:
    - Property 20: Sensitive Data Encryption Round-Trip
    - Property 21: Sensitive Data Log Exclusion

Validates: Requirements 13.1, 13.3
"""
from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck

from utils.encrypt import (
    FernetEncryption,
    SensitiveDataFilter,
    create_secure_logger,
    EncryptionError,
)
from core.data.key_store import (
    SQLiteKeyStore,
    ExchangeKey,
    DecryptedKey,
    Permission,
)


# Custom strategies for generating test data
@st.composite
def sensitive_data_strategy(draw):
    """Generate sensitive data strings for testing."""
    # Generate various types of sensitive data
    data_type = draw(st.sampled_from([
        "api_key", "secret_key", "password", "token"
    ]))
    
    if data_type == "api_key":
        # API keys are typically alphanumeric with some special chars
        return draw(st.text(
            min_size=16,
            max_size=64,
            alphabet=st.characters(
                whitelist_categories=('L', 'N'),
                whitelist_characters='-_'
            )
        ))
    elif data_type == "secret_key":
        # Secret keys can be longer and more complex
        return draw(st.text(
            min_size=32,
            max_size=128,
            alphabet=st.characters(
                whitelist_categories=('L', 'N'),
                whitelist_characters='-_+/='
            )
        ))
    elif data_type == "password":
        # Passwords can contain various characters
        return draw(st.text(
            min_size=8,
            max_size=64,
            alphabet=st.characters(
                whitelist_categories=('L', 'N', 'P'),
                blacklist_characters='\x00\n\r'
            )
        ))
    else:  # token
        # Tokens are typically base64-like
        return draw(st.text(
            min_size=20,
            max_size=256,
            alphabet=st.characters(
                whitelist_categories=('L', 'N'),
                whitelist_characters='-_.'
            )
        ))


@st.composite
def exchange_key_data_strategy(draw):
    """Generate exchange key data for testing."""
    return {
        "user_id": draw(st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=('L', 'N'),
                whitelist_characters='_-'
            )
        )),
        "exchange": draw(st.sampled_from([
            "binance", "okx", "huobi", "bybit", "kraken"
        ])),
        "api_key_name": draw(st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(
                whitelist_categories=('L', 'N'),
                whitelist_characters='_- '
            )
        )),
        "api_key": draw(st.text(
            min_size=16,
            max_size=64,
            alphabet=st.characters(
                whitelist_categories=('L', 'N'),
                whitelist_characters='-_'
            )
        )),
        "secret_key": draw(st.text(
            min_size=32,
            max_size=128,
            alphabet=st.characters(
                whitelist_categories=('L', 'N'),
                whitelist_characters='-_+/='
            )
        )),
        "passphrase": draw(st.one_of(
            st.none(),
            st.text(
                min_size=8,
                max_size=32,
                alphabet=st.characters(
                    whitelist_categories=('L', 'N'),
                    whitelist_characters='-_'
                )
            )
        )),
        "permissions": draw(st.lists(
            st.sampled_from([p.value for p in Permission]),
            min_size=0,
            max_size=3,
            unique=True
        )),
    }


class TestSensitiveDataEncryptionRoundTrip:
    """
    Property 20: Sensitive Data Encryption Round-Trip
    
    *For any* sensitive data (API keys, passwords), encrypting with Fernet
    and decrypting must produce the original plaintext.
    
    **Validates: Requirements 13.1**
    """
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create a temporary directory for each test."""
        self.key_dir = tmp_path / "config"
        self.key_dir.mkdir()
        yield
    
    @given(plaintext=sensitive_data_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_encryption_round_trip(self, plaintext: str) -> None:
        """
        Property: For any sensitive data, encrypt then decrypt
        must return the original plaintext.
        
        Feature: titan-quant, Property 20: Sensitive Data Encryption Round-Trip
        """
        # Skip empty strings as they're not valid sensitive data
        assume(len(plaintext) > 0)
        
        encryption = FernetEncryption(key_dir=str(self.key_dir))
        
        # Encrypt
        ciphertext = encryption.encrypt(plaintext)
        
        # Verify ciphertext is different from plaintext
        assert ciphertext != plaintext
        
        # Decrypt
        decrypted = encryption.decrypt(ciphertext)
        
        # Verify round-trip
        assert decrypted == plaintext
    
    @given(plaintext=st.text(min_size=1, max_size=1000))
    @settings(max_examples=100, deadline=5000)
    def test_encryption_round_trip_arbitrary_text(self, plaintext: str) -> None:
        """
        Property: For any arbitrary text, encrypt then decrypt
        must return the original text.
        
        Feature: titan-quant, Property 20: Sensitive Data Encryption Round-Trip
        """
        # Skip strings with null bytes as they may cause issues
        assume('\x00' not in plaintext)
        assume(len(plaintext) > 0)
        
        encryption = FernetEncryption(key_dir=str(self.key_dir))
        
        ciphertext = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(ciphertext)
        
        assert decrypted == plaintext
    
    @given(key_data=exchange_key_data_strategy())
    @settings(max_examples=100, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_key_store_round_trip(self, key_data: dict) -> None:
        """
        Property: For any API key data, storing and retrieving
        must return the original plaintext values.
        
        Feature: titan-quant, Property 20: Sensitive Data Encryption Round-Trip
        """
        # Skip empty values
        assume(len(key_data["user_id"]) > 0)
        assume(len(key_data["api_key_name"]) > 0)
        assume(len(key_data["api_key"]) > 0)
        assume(len(key_data["secret_key"]) > 0)
        
        # Use unique temp directory for each test
        import uuid
        unique_dir = Path(tempfile.mkdtemp()) / f"test_{uuid.uuid4().hex}"
        unique_dir.mkdir(parents=True, exist_ok=True)
        
        db_path = unique_dir / "test.db"
        key_dir = unique_dir / "config"
        key_dir.mkdir()
        
        key_store = SQLiteKeyStore(
            db_path=str(db_path),
            key_dir=str(key_dir)
        )
        
        # Store the key
        key_id = key_store.store_key(
            user_id=key_data["user_id"],
            exchange=key_data["exchange"],
            api_key_name=key_data["api_key_name"],
            api_key=key_data["api_key"],
            secret_key=key_data["secret_key"],
            passphrase=key_data["passphrase"],
            permissions=key_data["permissions"]
        )
        
        # Retrieve the key
        decrypted = key_store.get_key(key_id)
        
        # Verify round-trip
        assert decrypted is not None
        assert decrypted.user_id == key_data["user_id"]
        assert decrypted.exchange == key_data["exchange"]
        assert decrypted.api_key_name == key_data["api_key_name"]
        assert decrypted.api_key == key_data["api_key"]
        assert decrypted.secret_key == key_data["secret_key"]
        assert decrypted.passphrase == key_data["passphrase"]
        assert set(decrypted.permissions) == set(key_data["permissions"])
    
    def test_different_keys_produce_different_ciphertext(self) -> None:
        """
        Property: Different encryption keys must produce different ciphertext
        for the same plaintext.
        
        Feature: titan-quant, Property 20: Sensitive Data Encryption Round-Trip
        """
        # Create two encryption services with different keys
        key_dir1 = Path(tempfile.mkdtemp()) / "key1"
        key_dir2 = Path(tempfile.mkdtemp()) / "key2"
        key_dir1.mkdir(parents=True)
        key_dir2.mkdir(parents=True)
        
        enc1 = FernetEncryption(key_dir=str(key_dir1))
        enc2 = FernetEncryption(key_dir=str(key_dir2))
        
        plaintext = "test_api_key_12345"
        
        ciphertext1 = enc1.encrypt(plaintext)
        ciphertext2 = enc2.encrypt(plaintext)
        
        # Ciphertexts should be different (different keys)
        assert ciphertext1 != ciphertext2
        
        # But both should decrypt to the same plaintext with their own keys
        assert enc1.decrypt(ciphertext1) == plaintext
        assert enc2.decrypt(ciphertext2) == plaintext
    
    def test_wrong_key_fails_decryption(self) -> None:
        """
        Property: Decrypting with the wrong key must fail.
        
        Feature: titan-quant, Property 20: Sensitive Data Encryption Round-Trip
        """
        key_dir1 = Path(tempfile.mkdtemp()) / "key1"
        key_dir2 = Path(tempfile.mkdtemp()) / "key2"
        key_dir1.mkdir(parents=True)
        key_dir2.mkdir(parents=True)
        
        enc1 = FernetEncryption(key_dir=str(key_dir1))
        enc2 = FernetEncryption(key_dir=str(key_dir2))
        
        plaintext = "secret_data_12345"
        ciphertext = enc1.encrypt(plaintext)
        
        # Decrypting with wrong key should fail
        with pytest.raises(EncryptionError):
            enc2.decrypt(ciphertext)


class TestSensitiveDataLogExclusion:
    """
    Property 21: Sensitive Data Log Exclusion
    
    *For any* log output generated during sensitive data operations,
    the log content must not contain any plaintext sensitive data
    (API keys, passwords).
    
    **Validates: Requirements 13.3**
    """
    
    @pytest.fixture(autouse=True)
    def setup_logger(self):
        """Set up a logger with string capture for testing."""
        self.log_stream = io.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setLevel(logging.DEBUG)
        self.handler.setFormatter(logging.Formatter("%(message)s"))
        yield
        self.handler.close()
    
    @given(api_key=st.text(
        min_size=20,
        max_size=64,
        alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            whitelist_characters='-_',
            max_codepoint=127  # ASCII only for realistic API keys
        )
    ))
    @settings(max_examples=100, deadline=5000)
    def test_api_key_redacted_in_logs(self, api_key: str) -> None:
        """
        Property: For any API key logged, the plaintext must be redacted.
        
        Feature: titan-quant, Property 21: Sensitive Data Log Exclusion
        """
        assume(len(api_key) >= 20)
        # API keys are typically alphanumeric ASCII
        assume(api_key.isascii())
        
        # Create logger with filter
        logger = logging.getLogger(f"test_api_key_{id(api_key)}")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.addFilter(SensitiveDataFilter())
        
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        
        # Log message containing API key
        logger.info(f"api_key: {api_key}")
        logger.info(f"API_KEY={api_key}")
        logger.info(f'api-key: "{api_key}"')
        
        log_output = stream.getvalue()
        
        # API key should not appear in plaintext
        assert api_key not in log_output
        # But [REDACTED] should appear
        assert "[REDACTED]" in log_output
    
    @given(password=st.text(
        min_size=8,
        max_size=32,
        alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            whitelist_characters='!@#$%^&*()-_=+',
            blacklist_characters='\x00\n\r\t "\'',  # Exclude quotes and whitespace
            max_codepoint=127  # ASCII only for realistic passwords
        )
    ))
    @settings(max_examples=100, deadline=5000)
    def test_password_redacted_in_logs(self, password: str) -> None:
        """
        Property: For any password logged, the plaintext must be redacted.
        
        Feature: titan-quant, Property 21: Sensitive Data Log Exclusion
        """
        assume(len(password) >= 8)
        assume(' ' not in password)  # Passwords typically don't have spaces
        assume('"' not in password)  # Exclude quotes for regex matching
        assume("'" not in password)
        assume(password.isascii())
        
        logger = logging.getLogger(f"test_password_{id(password)}")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.addFilter(SensitiveDataFilter())
        
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        
        # Log message containing password
        logger.info(f"password: {password}")
        logger.info(f"PASSWORD={password}")
        logger.info(f'pwd: "{password}"')
        
        log_output = stream.getvalue()
        
        # Password should not appear in plaintext
        assert password not in log_output
        # But [REDACTED] should appear
        assert "[REDACTED]" in log_output
    
    @given(secret=st.text(
        min_size=20,
        max_size=64,
        alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            whitelist_characters='-_',
            max_codepoint=127  # ASCII only for realistic secret keys
        )
    ))
    @settings(max_examples=100, deadline=5000)
    def test_secret_key_redacted_in_logs(self, secret: str) -> None:
        """
        Property: For any secret key logged, the plaintext must be redacted.
        
        Feature: titan-quant, Property 21: Sensitive Data Log Exclusion
        """
        assume(len(secret) >= 20)
        # Secret keys are typically alphanumeric ASCII
        assume(secret.isascii())
        
        logger = logging.getLogger(f"test_secret_{id(secret)}")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.addFilter(SensitiveDataFilter())
        
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        
        # Log message containing secret key
        logger.info(f"secret_key: {secret}")
        logger.info(f"SECRET_KEY={secret}")
        logger.info(f'secretkey: "{secret}"')
        
        log_output = stream.getvalue()
        
        # Secret should not appear in plaintext
        assert secret not in log_output
        # But [REDACTED] should appear
        assert "[REDACTED]" in log_output
    
    def test_decrypted_key_repr_is_safe(self) -> None:
        """
        Property: The string representation of DecryptedKey must not
        expose sensitive data.
        
        Feature: titan-quant, Property 21: Sensitive Data Log Exclusion
        """
        key = DecryptedKey(
            key_id="test-123",
            user_id="user1",
            exchange="binance",
            api_key_name="My Key",
            api_key="super_secret_api_key_12345",
            secret_key="even_more_secret_key_67890",
            passphrase="my_passphrase",
            permissions=["read", "trade"]
        )
        
        # Check repr
        repr_str = repr(key)
        assert "super_secret_api_key_12345" not in repr_str
        assert "even_more_secret_key_67890" not in repr_str
        assert "my_passphrase" not in repr_str
        assert "[REDACTED]" in repr_str
        
        # Check str
        str_str = str(key)
        assert "super_secret_api_key_12345" not in str_str
        assert "even_more_secret_key_67890" not in str_str
        assert "my_passphrase" not in str_str
        assert "[REDACTED]" in str_str
    
    def test_filter_with_dict_args(self) -> None:
        """
        Property: The filter must redact sensitive keys in dict arguments.
        
        Feature: titan-quant, Property 21: Sensitive Data Log Exclusion
        """
        logger = logging.getLogger("test_dict_filter")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        sensitive_filter = SensitiveDataFilter()
        logger.addFilter(sensitive_filter)
        
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        
        # Log with dict containing sensitive data
        data = {
            "api_key": "my_secret_api_key_12345",
            "password": "super_secret_password",
            "username": "john_doe"  # Not sensitive
        }
        
        # The filter processes the record, so we need to check the dict redaction
        redacted = sensitive_filter._redact_dict(data)
        
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["username"] == "john_doe"  # Not redacted
    
    def test_create_secure_logger(self) -> None:
        """
        Property: Loggers created with create_secure_logger must have
        the sensitive data filter applied.
        
        Feature: titan-quant, Property 21: Sensitive Data Log Exclusion
        """
        logger = create_secure_logger("test_secure")
        
        # Verify filter is applied
        filter_names = [type(f).__name__ for f in logger.filters]
        assert "SensitiveDataFilter" in filter_names


class TestKeyStoreOperations:
    """Unit tests for KeyStore operations."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create a temporary directory for each test."""
        self.db_path = tmp_path / "test.db"
        self.key_dir = tmp_path / "config"
        self.key_dir.mkdir()
        self.key_store = SQLiteKeyStore(
            db_path=str(self.db_path),
            key_dir=str(self.key_dir)
        )
        yield
    
    def test_store_and_retrieve_key(self) -> None:
        """Test basic store and retrieve operations."""
        key_id = self.key_store.store_key(
            user_id="user1",
            exchange="binance",
            api_key_name="Main Key",
            api_key="api_key_12345",
            secret_key="secret_key_67890",
            passphrase="my_passphrase",
            permissions=["read", "trade"]
        )
        
        decrypted = self.key_store.get_key(key_id)
        
        assert decrypted is not None
        assert decrypted.api_key == "api_key_12345"
        assert decrypted.secret_key == "secret_key_67890"
        assert decrypted.passphrase == "my_passphrase"
        assert "read" in decrypted.permissions
        assert "trade" in decrypted.permissions
    
    def test_get_keys_by_user(self) -> None:
        """Test retrieving all keys for a user."""
        self.key_store.store_key(
            user_id="user1",
            exchange="binance",
            api_key_name="Key 1",
            api_key="api1",
            secret_key="secret1"
        )
        self.key_store.store_key(
            user_id="user1",
            exchange="okx",
            api_key_name="Key 2",
            api_key="api2",
            secret_key="secret2"
        )
        self.key_store.store_key(
            user_id="user2",
            exchange="binance",
            api_key_name="Key 3",
            api_key="api3",
            secret_key="secret3"
        )
        
        user1_keys = self.key_store.get_keys_by_user("user1")
        assert len(user1_keys) == 2
        
        user2_keys = self.key_store.get_keys_by_user("user2")
        assert len(user2_keys) == 1
    
    def test_get_keys_by_exchange(self) -> None:
        """Test retrieving keys by exchange."""
        self.key_store.store_key(
            user_id="user1",
            exchange="binance",
            api_key_name="Key 1",
            api_key="api1",
            secret_key="secret1"
        )
        self.key_store.store_key(
            user_id="user1",
            exchange="binance",
            api_key_name="Key 2",
            api_key="api2",
            secret_key="secret2"
        )
        self.key_store.store_key(
            user_id="user1",
            exchange="okx",
            api_key_name="Key 3",
            api_key="api3",
            secret_key="secret3"
        )
        
        binance_keys = self.key_store.get_keys_by_exchange("user1", "binance")
        assert len(binance_keys) == 2
        
        okx_keys = self.key_store.get_keys_by_exchange("user1", "okx")
        assert len(okx_keys) == 1
    
    def test_update_key(self) -> None:
        """Test updating a key."""
        key_id = self.key_store.store_key(
            user_id="user1",
            exchange="binance",
            api_key_name="Key 1",
            api_key="old_api_key",
            secret_key="old_secret_key",
            permissions=["read"]
        )
        
        # Update the key
        self.key_store.update_key(
            key_id=key_id,
            api_key="new_api_key",
            permissions=["read", "trade"]
        )
        
        decrypted = self.key_store.get_key(key_id)
        assert decrypted.api_key == "new_api_key"
        assert decrypted.secret_key == "old_secret_key"  # Unchanged
        assert "trade" in decrypted.permissions
    
    def test_delete_key(self) -> None:
        """Test deleting a key."""
        key_id = self.key_store.store_key(
            user_id="user1",
            exchange="binance",
            api_key_name="Key 1",
            api_key="api1",
            secret_key="secret1"
        )
        
        assert self.key_store.get_key(key_id) is not None
        
        self.key_store.delete_key(key_id)
        
        assert self.key_store.get_key(key_id) is None
    
    def test_deactivate_key(self) -> None:
        """Test deactivating a key."""
        key_id = self.key_store.store_key(
            user_id="user1",
            exchange="binance",
            api_key_name="Key 1",
            api_key="api1",
            secret_key="secret1"
        )
        
        assert self.key_store.get_key(key_id) is not None
        
        self.key_store.deactivate_key(key_id)
        
        # Deactivated key should not be returned by get_key
        assert self.key_store.get_key(key_id) is None
        
        # But should still exist in the database
        keys = self.key_store.get_keys_by_user("user1")
        assert len(keys) == 1
        assert keys[0].is_active is False
    
    def test_has_permission(self) -> None:
        """Test permission checking."""
        key_id = self.key_store.store_key(
            user_id="user1",
            exchange="binance",
            api_key_name="Key 1",
            api_key="api1",
            secret_key="secret1",
            permissions=["read", "trade"]
        )
        
        assert self.key_store.has_permission(key_id, "read") is True
        assert self.key_store.has_permission(key_id, "trade") is True
        assert self.key_store.has_permission(key_id, "withdraw") is False
