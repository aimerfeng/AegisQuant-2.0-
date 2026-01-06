"""
Data Governance and Provider Module

This module provides data import, cleaning, storage, provider functionality,
and database repository layer for the Titan-Quant system.
"""
from core.data.importer import DataFormat, DataImporter, import_data
from core.data.cleaner import (
    FillMethod,
    DataQualityReport,
    CleaningConfig,
    DataCleaner,
)
from core.data.storage import (
    DataType,
    BarInterval,
    TICK_SCHEMA,
    BAR_SCHEMA,
    TICK_REQUIRED_COLUMNS,
    BAR_REQUIRED_COLUMNS,
    StorageConfig,
    ParquetStorage,
)
from core.data.provider import (
    ProviderStatus,
    HistoryRequest,
    ProviderInfo,
    AbstractDataProvider,
)
from core.data.provider_manager import (
    ProviderConfig,
    DataProviderManager,
    get_provider_manager,
    reset_provider_manager,
)
from core.data.providers import (
    ParquetDataProvider,
    MySQLDataProvider,
    MongoDBDataProvider,
)
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
    BaseRepository,
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

__all__ = [
    # Importer
    "DataFormat",
    "DataImporter",
    "import_data",
    # Cleaner
    "FillMethod",
    "DataQualityReport",
    "CleaningConfig",
    "DataCleaner",
    # Storage
    "DataType",
    "BarInterval",
    "TICK_SCHEMA",
    "BAR_SCHEMA",
    "TICK_REQUIRED_COLUMNS",
    "BAR_REQUIRED_COLUMNS",
    "StorageConfig",
    "ParquetStorage",
    # Provider Interface
    "ProviderStatus",
    "HistoryRequest",
    "ProviderInfo",
    "AbstractDataProvider",
    # Provider Manager
    "ProviderConfig",
    "DataProviderManager",
    "get_provider_manager",
    "reset_provider_manager",
    # Provider Implementations
    "ParquetDataProvider",
    "MySQLDataProvider",
    "MongoDBDataProvider",
    # Repository Enums
    "UserRole",
    "BacktestStatus",
    "AlertType",
    "AlertSeverity",
    "ProviderType",
    # Repository Data Models
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
    # Repository Factory
    "RepositoryFactory",
    "get_repository_factory",
    "reset_repository_factory",
]
