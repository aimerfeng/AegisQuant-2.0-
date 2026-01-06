"""
Tests for the Titan-Quant Repository Layer

This module tests the CRUD operations for all database tables.
"""
import os
import tempfile
import pytest
from datetime import datetime

from core.data.repository import (
    # Enums
    UserRole,
    BacktestStatus,
    AlertType,
    AlertSeverity,
    ProviderType,
    # Data Models
    User,
    ExchangeKey,
    Strategy,
    BacktestRecord,
    BacktestResult,
    Snapshot,
    AlertConfig,
    DataProvider,
    # Database Manager
    DatabaseManager,
    get_database_manager,
    reset_database_manager,
    # Repositories
    UserRepository,
    ExchangeKeyRepository,
    StrategyRepository,
    BacktestRecordRepository,
    BacktestResultRepository,
    SnapshotRepository,
    AlertConfigRepository,
    DataProviderRepository,
    # Factory
    RepositoryFactory,
    get_repository_factory,
    reset_repository_factory,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Reset singletons
    reset_database_manager()
    reset_repository_factory()
    
    # Create temp directory and database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_titan_quant.db")
    schema_path = os.path.join("database", "schema.sql")
    
    # Initialize database
    db_manager = get_database_manager(db_path)
    db_manager.initialize_database(schema_path)
    
    yield db_manager
    
    # Cleanup
    reset_database_manager()
    reset_repository_factory()
    if os.path.exists(db_path):
        os.remove(db_path)
    os.rmdir(temp_dir)


class TestUserRepository:
    """Tests for UserRepository."""
    
    def test_create_user(self, temp_db):
        """Test creating a new user."""
        repo = UserRepository(temp_db)
        user = User(
            user_id="test-user-1",
            username="testuser",
            password_hash="hashed_password",
            role=UserRole.TRADER,
            preferred_language="en",
        )
        
        created = repo.create(user)
        
        assert created is not None
        assert created.user_id == "test-user-1"
        assert created.username == "testuser"
        assert created.role == UserRole.TRADER
    
    def test_get_user_by_id(self, temp_db):
        """Test getting a user by ID."""
        repo = UserRepository(temp_db)
        user = User(
            user_id="test-user-2",
            username="testuser2",
            password_hash="hashed_password",
            role=UserRole.ADMIN,
        )
        repo.create(user)
        
        found = repo.get_by_id("test-user-2")
        
        assert found is not None
        assert found.username == "testuser2"
        assert found.role == UserRole.ADMIN
    
    def test_get_user_by_username(self, temp_db):
        """Test getting a user by username."""
        repo = UserRepository(temp_db)
        user = User(
            user_id="test-user-3",
            username="uniqueuser",
            password_hash="hashed_password",
            role=UserRole.TRADER,
        )
        repo.create(user)
        
        found = repo.get_by_username("uniqueuser")
        
        assert found is not None
        assert found.user_id == "test-user-3"
    
    def test_update_user(self, temp_db):
        """Test updating a user."""
        repo = UserRepository(temp_db)
        user = User(
            user_id="test-user-4",
            username="updateuser",
            password_hash="old_hash",
            role=UserRole.TRADER,
        )
        repo.create(user)
        
        user.password_hash = "new_hash"
        user.role = UserRole.ADMIN
        updated = repo.update(user)
        
        assert updated is not None
        assert updated.password_hash == "new_hash"
        assert updated.role == UserRole.ADMIN
    
    def test_delete_user(self, temp_db):
        """Test deleting a user."""
        repo = UserRepository(temp_db)
        user = User(
            user_id="test-user-5",
            username="deleteuser",
            password_hash="hashed_password",
            role=UserRole.TRADER,
        )
        repo.create(user)
        
        result = repo.delete("test-user-5")
        
        assert result is True
        assert repo.get_by_id("test-user-5") is None


class TestExchangeKeyRepository:
    """Tests for ExchangeKeyRepository."""
    
    def test_create_exchange_key(self, temp_db):
        """Test creating a new exchange key."""
        # First create a user
        user_repo = UserRepository(temp_db)
        user = User(
            user_id="key-test-user",
            username="keyuser",
            password_hash="hash",
            role=UserRole.TRADER,
        )
        user_repo.create(user)
        
        # Create exchange key
        key_repo = ExchangeKeyRepository(temp_db)
        key = ExchangeKey(
            key_id="test-key-1",
            user_id="key-test-user",
            exchange="binance",
            api_key_name="My Binance Key",
            api_key_ciphertext="encrypted_api_key",
            secret_key_ciphertext="encrypted_secret",
            permissions=["read", "trade"],
        )
        
        created = key_repo.create(key)
        
        assert created is not None
        assert created.exchange == "binance"
        assert created.permissions == ["read", "trade"]
    
    def test_get_keys_by_user(self, temp_db):
        """Test getting exchange keys by user ID."""
        user_repo = UserRepository(temp_db)
        user = User(
            user_id="multi-key-user",
            username="multikeyuser",
            password_hash="hash",
            role=UserRole.TRADER,
        )
        user_repo.create(user)
        
        key_repo = ExchangeKeyRepository(temp_db)
        for i in range(3):
            key = ExchangeKey(
                key_id=f"multi-key-{i}",
                user_id="multi-key-user",
                exchange="binance" if i < 2 else "okx",
                api_key_name=f"Key {i}",
                api_key_ciphertext=f"api_{i}",
                secret_key_ciphertext=f"secret_{i}",
            )
            key_repo.create(key)
        
        keys = key_repo.get_by_user_id("multi-key-user")
        
        assert len(keys) == 3
    
    def test_deactivate_key(self, temp_db):
        """Test deactivating an exchange key."""
        user_repo = UserRepository(temp_db)
        user = User(
            user_id="deactivate-user",
            username="deactivateuser",
            password_hash="hash",
            role=UserRole.TRADER,
        )
        user_repo.create(user)
        
        key_repo = ExchangeKeyRepository(temp_db)
        key = ExchangeKey(
            key_id="deactivate-key",
            user_id="deactivate-user",
            exchange="binance",
            api_key_name="Deactivate Key",
            api_key_ciphertext="api",
            secret_key_ciphertext="secret",
            is_active=True,
        )
        key_repo.create(key)
        
        result = key_repo.deactivate("deactivate-key")
        
        assert result is True
        updated = key_repo.get_by_id("deactivate-key")
        assert updated.is_active is False


class TestStrategyRepository:
    """Tests for StrategyRepository."""
    
    def test_create_strategy(self, temp_db):
        """Test creating a new strategy."""
        repo = StrategyRepository(temp_db)
        strategy = Strategy(
            strategy_id="test-strategy-1",
            name="Test Strategy",
            class_name="TestStrategy",
            file_path="/strategies/test.py",
            checksum="abc123",
            parameters={"param1": 10, "param2": 0.5},
        )
        
        created = repo.create(strategy)
        
        assert created is not None
        assert created.name == "Test Strategy"
        assert created.parameters == {"param1": 10, "param2": 0.5}
    
    def test_get_strategy_by_name(self, temp_db):
        """Test getting a strategy by name."""
        repo = StrategyRepository(temp_db)
        strategy = Strategy(
            strategy_id="named-strategy",
            name="Named Strategy",
            class_name="NamedStrategy",
            file_path="/strategies/named.py",
            checksum="def456",
        )
        repo.create(strategy)
        
        found = repo.get_by_name("Named Strategy")
        
        assert found is not None
        assert found.strategy_id == "named-strategy"


class TestBacktestRecordRepository:
    """Tests for BacktestRecordRepository."""
    
    def test_create_backtest_record(self, temp_db):
        """Test creating a new backtest record."""
        repo = BacktestRecordRepository(temp_db)
        record = BacktestRecord(
            backtest_id="test-backtest-1",
            strategy_id=None,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=100000.0,
            matching_mode="L1",
            status=BacktestStatus.RUNNING,
        )
        
        created = repo.create(record)
        
        assert created is not None
        assert created.initial_capital == 100000.0
        assert created.status == BacktestStatus.RUNNING
    
    def test_update_backtest_status(self, temp_db):
        """Test updating backtest status."""
        repo = BacktestRecordRepository(temp_db)
        record = BacktestRecord(
            backtest_id="status-backtest",
            strategy_id=None,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=100000.0,
            matching_mode="L1",
            status=BacktestStatus.RUNNING,
        )
        repo.create(record)
        
        result = repo.update_status("status-backtest", BacktestStatus.COMPLETED)
        
        assert result is True
        updated = repo.get_by_id("status-backtest")
        assert updated.status == BacktestStatus.COMPLETED
        assert updated.completed_at is not None


class TestBacktestResultRepository:
    """Tests for BacktestResultRepository."""
    
    def test_create_backtest_result(self, temp_db):
        """Test creating a new backtest result."""
        # First create a backtest record
        record_repo = BacktestRecordRepository(temp_db)
        record = BacktestRecord(
            backtest_id="result-backtest",
            strategy_id=None,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=100000.0,
            matching_mode="L1",
            status=BacktestStatus.COMPLETED,
        )
        record_repo.create(record)
        
        # Create result
        result_repo = BacktestResultRepository(temp_db)
        result = BacktestResult(
            result_id="test-result-1",
            backtest_id="result-backtest",
            total_return=0.15,
            sharpe_ratio=1.5,
            max_drawdown=0.08,
            win_rate=0.55,
            total_trades=100,
            metrics_json={"custom_metric": 42},
        )
        
        created = result_repo.create(result)
        
        assert created is not None
        assert created.sharpe_ratio == 1.5
        assert created.metrics_json == {"custom_metric": 42}


class TestSnapshotRepository:
    """Tests for SnapshotRepository."""
    
    def test_create_snapshot(self, temp_db):
        """Test creating a new snapshot."""
        repo = SnapshotRepository(temp_db)
        snapshot = Snapshot(
            snapshot_id="test-snapshot-1",
            backtest_id=None,
            version="1.0.0",
            file_path="/snapshots/test.json",
            data_timestamp=datetime(2024, 6, 15, 12, 0, 0),
        )
        
        created = repo.create(snapshot)
        
        assert created is not None
        assert created.version == "1.0.0"
    
    def test_get_latest_snapshot(self, temp_db):
        """Test getting the latest snapshot for a backtest."""
        # Create backtest record first
        record_repo = BacktestRecordRepository(temp_db)
        record = BacktestRecord(
            backtest_id="snapshot-backtest",
            strategy_id=None,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=100000.0,
            matching_mode="L1",
            status=BacktestStatus.RUNNING,
        )
        record_repo.create(record)
        
        # Create multiple snapshots
        repo = SnapshotRepository(temp_db)
        for i in range(3):
            snapshot = Snapshot(
                snapshot_id=f"snapshot-{i}",
                backtest_id="snapshot-backtest",
                version="1.0.0",
                file_path=f"/snapshots/snap_{i}.json",
                data_timestamp=datetime(2024, 6, 15 + i, 12, 0, 0),
            )
            repo.create(snapshot)
        
        latest = repo.get_latest_by_backtest_id("snapshot-backtest")
        
        assert latest is not None
        assert latest.snapshot_id == "snapshot-2"


class TestAlertConfigRepository:
    """Tests for AlertConfigRepository."""
    
    def test_create_alert_config(self, temp_db):
        """Test creating a new alert configuration."""
        repo = AlertConfigRepository(temp_db)
        config = AlertConfig(
            config_id="test-alert-1",
            event_type="risk_trigger",
            alert_type=AlertType.SYNC,
            channels=["email", "webhook"],
            severity=AlertSeverity.CRITICAL,
            enabled=True,
        )
        
        created = repo.create(config)
        
        assert created is not None
        assert created.alert_type == AlertType.SYNC
        assert created.channels == ["email", "webhook"]
    
    def test_get_enabled_configs(self, temp_db):
        """Test getting enabled alert configurations."""
        repo = AlertConfigRepository(temp_db)
        
        # Create enabled and disabled configs
        for i, enabled in enumerate([True, True, False]):
            config = AlertConfig(
                config_id=f"enabled-config-{i}",
                event_type=f"event_{i}",
                alert_type=AlertType.ASYNC,
                channels=["email"],
                severity=AlertSeverity.INFO,
                enabled=enabled,
            )
            repo.create(config)
        
        enabled_configs = repo.get_enabled()
        
        assert len(enabled_configs) == 2


class TestDataProviderRepository:
    """Tests for DataProviderRepository."""
    
    def test_create_data_provider(self, temp_db):
        """Test creating a new data provider."""
        repo = DataProviderRepository(temp_db)
        provider = DataProvider(
            provider_id="test-provider-1",
            provider_type=ProviderType.PARQUET,
            name="Local Parquet",
            connection_config={"path": "/data/parquet"},
            is_default=True,
        )
        
        created = repo.create(provider)
        
        assert created is not None
        assert created.provider_type == ProviderType.PARQUET
        assert created.connection_config == {"path": "/data/parquet"}
    
    def test_get_default_provider(self, temp_db):
        """Test getting the default data provider."""
        repo = DataProviderRepository(temp_db)
        
        # Create providers
        for i, is_default in enumerate([False, True, False]):
            provider = DataProvider(
                provider_id=f"default-provider-{i}",
                provider_type=ProviderType.PARQUET,
                name=f"Provider {i}",
                connection_config={},
                is_default=is_default,
            )
            repo.create(provider)
        
        default = repo.get_default()
        
        assert default is not None
        assert default.provider_id == "default-provider-1"
    
    def test_set_default_provider(self, temp_db):
        """Test setting a provider as default."""
        repo = DataProviderRepository(temp_db)
        
        # Create two providers
        for i in range(2):
            provider = DataProvider(
                provider_id=f"set-default-{i}",
                provider_type=ProviderType.MYSQL,
                name=f"MySQL {i}",
                connection_config={"host": "localhost"},
                is_default=(i == 0),
            )
            repo.create(provider)
        
        # Change default
        result = repo.set_default("set-default-1")
        
        assert result is True
        new_default = repo.get_default()
        assert new_default.provider_id == "set-default-1"


class TestRepositoryFactory:
    """Tests for RepositoryFactory."""
    
    def test_factory_creates_repositories(self, temp_db):
        """Test that factory creates all repository types."""
        factory = RepositoryFactory(temp_db)
        
        assert factory.get_user_repository() is not None
        assert factory.get_exchange_key_repository() is not None
        assert factory.get_strategy_repository() is not None
        assert factory.get_backtest_record_repository() is not None
        assert factory.get_backtest_result_repository() is not None
        assert factory.get_snapshot_repository() is not None
        assert factory.get_alert_config_repository() is not None
        assert factory.get_data_provider_repository() is not None
    
    def test_factory_returns_same_instance(self, temp_db):
        """Test that factory returns the same repository instance."""
        factory = RepositoryFactory(temp_db)
        
        repo1 = factory.get_user_repository()
        repo2 = factory.get_user_repository()
        
        assert repo1 is repo2
