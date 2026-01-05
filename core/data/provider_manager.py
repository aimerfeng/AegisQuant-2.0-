"""
Data Provider Manager

This module implements the data provider manager for the Titan-Quant system.
It handles registration, configuration, and switching between different
data providers (Parquet, MySQL, MongoDB, etc.).

Requirements: Data source extension - Provider registration, switching, configuration management
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Type

from core.data.provider import (
    AbstractDataProvider,
    HistoryRequest,
    ProviderInfo,
    ProviderStatus,
)
from core.data.providers.parquet_provider import ParquetDataProvider
from core.data.providers.mysql_provider import MySQLDataProvider
from core.data.providers.mongodb_provider import MongoDBDataProvider
from core.engine.types import BarData, TickData
from core.exceptions import DataError, ErrorCodes


@dataclass
class ProviderConfig:
    """
    Configuration for a data provider.
    
    Attributes:
        provider_type: Type of provider ("parquet", "mysql", "mongodb")
        name: User-defined name for this provider instance
        settings: Connection settings for the provider
        is_default: Whether this is the default provider
        enabled: Whether this provider is enabled
    """
    provider_type: str
    name: str
    settings: dict[str, Any] = field(default_factory=dict)
    is_default: bool = False
    enabled: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "provider_type": self.provider_type,
            "name": self.name,
            "settings": self.settings,
            "is_default": self.is_default,
            "enabled": self.enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderConfig:
        """Create ProviderConfig from dictionary."""
        return cls(
            provider_type=data["provider_type"],
            name=data["name"],
            settings=data.get("settings", {}),
            is_default=data.get("is_default", False),
            enabled=data.get("enabled", True),
        )


class DataProviderManager:
    """
    Manager for data providers.
    
    This class handles:
    - Registration of provider types
    - Creation and configuration of provider instances
    - Switching between providers
    - Provider lifecycle management
    
    Built-in provider types:
    - "parquet": Local Parquet file storage
    - "mysql": MySQL database
    - "mongodb": MongoDB database
    
    Example:
        manager = DataProviderManager()
        
        # Register a custom provider type
        manager.register_provider_type("custom", CustomDataProvider)
        
        # Add a provider instance
        manager.add_provider(ProviderConfig(
            provider_type="parquet",
            name="local",
            settings={"base_path": "./database"},
            is_default=True,
        ))
        
        # Connect and use
        manager.connect("local")
        bars = manager.load_bar_history(request)
    """
    
    # Built-in provider types
    BUILTIN_PROVIDERS: dict[str, Type[AbstractDataProvider]] = {
        "parquet": ParquetDataProvider,
        "mysql": MySQLDataProvider,
        "mongodb": MongoDBDataProvider,
    }
    
    def __init__(self) -> None:
        """Initialize the data provider manager."""
        self._provider_types: dict[str, Type[AbstractDataProvider]] = {}
        self._providers: dict[str, AbstractDataProvider] = {}
        self._configs: dict[str, ProviderConfig] = {}
        self._active_provider: str | None = None
        
        # Register built-in providers
        for name, provider_class in self.BUILTIN_PROVIDERS.items():
            self._provider_types[name] = provider_class
    
    def register_provider_type(
        self,
        type_name: str,
        provider_class: Type[AbstractDataProvider],
    ) -> None:
        """
        Register a new provider type.
        
        Args:
            type_name: Name for the provider type
            provider_class: Provider class (must inherit from AbstractDataProvider)
        
        Raises:
            ValueError: If type_name is already registered
        """
        if type_name in self._provider_types:
            raise ValueError(f"Provider type '{type_name}' is already registered")
        
        if not issubclass(provider_class, AbstractDataProvider):
            raise ValueError("provider_class must inherit from AbstractDataProvider")
        
        self._provider_types[type_name] = provider_class
    
    def unregister_provider_type(self, type_name: str) -> bool:
        """
        Unregister a provider type.
        
        Args:
            type_name: Name of the provider type to unregister
        
        Returns:
            True if unregistered, False if not found.
        """
        if type_name in self.BUILTIN_PROVIDERS:
            raise ValueError(f"Cannot unregister built-in provider type '{type_name}'")
        
        if type_name in self._provider_types:
            del self._provider_types[type_name]
            return True
        return False
    
    def get_registered_types(self) -> list[str]:
        """
        Get list of registered provider types.
        
        Returns:
            List of provider type names.
        """
        return list(self._provider_types.keys())
    
    def add_provider(self, config: ProviderConfig) -> bool:
        """
        Add a new provider instance.
        
        Args:
            config: Provider configuration
        
        Returns:
            True if added successfully, False otherwise.
        
        Raises:
            ValueError: If provider type is not registered or name already exists
        """
        if config.provider_type not in self._provider_types:
            raise ValueError(f"Unknown provider type: {config.provider_type}")
        
        if config.name in self._configs:
            raise ValueError(f"Provider '{config.name}' already exists")
        
        # Create provider instance
        provider_class = self._provider_types[config.provider_type]
        provider = provider_class()
        
        self._providers[config.name] = provider
        self._configs[config.name] = config
        
        # Set as default if specified or if it's the first provider
        if config.is_default or len(self._configs) == 1:
            self._set_default(config.name)
        
        return True
    
    def remove_provider(self, name: str) -> bool:
        """
        Remove a provider instance.
        
        Args:
            name: Provider name
        
        Returns:
            True if removed, False if not found.
        """
        if name not in self._providers:
            return False
        
        # Disconnect if connected
        provider = self._providers[name]
        if provider.is_connected():
            provider.disconnect()
        
        # Remove from active if it was active
        if self._active_provider == name:
            self._active_provider = None
        
        del self._providers[name]
        del self._configs[name]
        
        return True
    
    def _set_default(self, name: str) -> None:
        """Set a provider as the default."""
        for config_name, config in self._configs.items():
            config.is_default = (config_name == name)
    
    def get_provider(self, name: str) -> AbstractDataProvider | None:
        """
        Get a provider instance by name.
        
        Args:
            name: Provider name
        
        Returns:
            Provider instance or None if not found.
        """
        return self._providers.get(name)
    
    def get_config(self, name: str) -> ProviderConfig | None:
        """
        Get provider configuration by name.
        
        Args:
            name: Provider name
        
        Returns:
            Provider configuration or None if not found.
        """
        return self._configs.get(name)
    
    def list_providers(self) -> list[str]:
        """
        Get list of configured provider names.
        
        Returns:
            List of provider names.
        """
        return list(self._providers.keys())
    
    def get_default_provider_name(self) -> str | None:
        """
        Get the name of the default provider.
        
        Returns:
            Default provider name or None if no default.
        """
        for name, config in self._configs.items():
            if config.is_default:
                return name
        return None
    
    def set_default_provider(self, name: str) -> bool:
        """
        Set a provider as the default.
        
        Args:
            name: Provider name
        
        Returns:
            True if set successfully, False if provider not found.
        """
        if name not in self._configs:
            return False
        
        self._set_default(name)
        return True
    
    def connect(self, name: str | None = None) -> bool:
        """
        Connect to a provider.
        
        Args:
            name: Provider name (uses default if None)
        
        Returns:
            True if connected successfully, False otherwise.
        """
        if name is None:
            name = self.get_default_provider_name()
        
        if name is None:
            raise DataError(
                message="No provider specified and no default provider configured",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
            )
        
        if name not in self._providers:
            raise DataError(
                message=f"Provider '{name}' not found",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
            )
        
        provider = self._providers[name]
        config = self._configs[name]
        
        if provider.connect(config.settings):
            self._active_provider = name
            return True
        return False
    
    def disconnect(self, name: str | None = None) -> bool:
        """
        Disconnect from a provider.
        
        Args:
            name: Provider name (uses active provider if None)
        
        Returns:
            True if disconnected successfully, False otherwise.
        """
        if name is None:
            name = self._active_provider
        
        if name is None:
            return True  # Nothing to disconnect
        
        if name not in self._providers:
            return False
        
        provider = self._providers[name]
        result = provider.disconnect()
        
        if name == self._active_provider:
            self._active_provider = None
        
        return result
    
    def disconnect_all(self) -> None:
        """Disconnect all providers."""
        for name in self._providers:
            self.disconnect(name)
    
    def switch_provider(self, name: str) -> bool:
        """
        Switch to a different provider.
        
        This disconnects the current active provider and connects
        to the specified provider.
        
        Args:
            name: Provider name to switch to
        
        Returns:
            True if switched successfully, False otherwise.
        """
        if name not in self._providers:
            return False
        
        # Disconnect current provider
        if self._active_provider and self._active_provider != name:
            self.disconnect(self._active_provider)
        
        # Connect to new provider
        return self.connect(name)
    
    def get_active_provider(self) -> AbstractDataProvider | None:
        """
        Get the currently active provider.
        
        Returns:
            Active provider instance or None.
        """
        if self._active_provider:
            return self._providers.get(self._active_provider)
        return None
    
    def get_active_provider_name(self) -> str | None:
        """
        Get the name of the currently active provider.
        
        Returns:
            Active provider name or None.
        """
        return self._active_provider
    
    def _ensure_active(self) -> AbstractDataProvider:
        """Ensure there's an active provider, raise error if not."""
        provider = self.get_active_provider()
        if provider is None:
            raise DataError(
                message="No active provider. Call connect() first.",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
            )
        if not provider.is_connected():
            raise DataError(
                message="Active provider is not connected",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
            )
        return provider
    
    def load_bar_history(self, req: HistoryRequest) -> list[BarData]:
        """
        Load bar history from the active provider.
        
        Args:
            req: History request parameters
        
        Returns:
            List of BarData objects.
        """
        provider = self._ensure_active()
        return provider.load_bar_history(req)
    
    def load_tick_history(self, req: HistoryRequest) -> list[TickData]:
        """
        Load tick history from the active provider.
        
        Args:
            req: History request parameters
        
        Returns:
            List of TickData objects.
        """
        provider = self._ensure_active()
        return provider.load_tick_history(req)
    
    def get_available_symbols(self, exchange: str) -> list[str]:
        """
        Get available symbols from the active provider.
        
        Args:
            exchange: Exchange name
        
        Returns:
            List of symbol names.
        """
        provider = self._ensure_active()
        return provider.get_available_symbols(exchange)
    
    def get_dominant_contract(self, symbol_root: str) -> str:
        """
        Get dominant contract from the active provider.
        
        Args:
            symbol_root: Root symbol
        
        Returns:
            Dominant contract symbol.
        """
        provider = self._ensure_active()
        return provider.get_dominant_contract(symbol_root)
    
    def download_and_cache(self, req: HistoryRequest, save_path: str) -> bool:
        """
        Download and cache data from the active provider.
        
        Args:
            req: History request parameters
            save_path: Path to save cached data
        
        Returns:
            True if successful, False otherwise.
        """
        provider = self._ensure_active()
        return provider.download_and_cache(req, save_path)
    
    def get_provider_info(self, name: str | None = None) -> ProviderInfo | None:
        """
        Get provider information.
        
        Args:
            name: Provider name (uses active provider if None)
        
        Returns:
            ProviderInfo or None if provider not found.
        """
        if name is None:
            name = self._active_provider
        
        if name is None or name not in self._providers:
            return None
        
        return self._providers[name].get_provider_info()
    
    def get_all_provider_info(self) -> dict[str, ProviderInfo]:
        """
        Get information for all configured providers.
        
        Returns:
            Dictionary mapping provider names to ProviderInfo.
        """
        return {
            name: provider.get_provider_info()
            for name, provider in self._providers.items()
        }
    
    def get_provider_status(self, name: str | None = None) -> ProviderStatus | None:
        """
        Get provider connection status.
        
        Args:
            name: Provider name (uses active provider if None)
        
        Returns:
            ProviderStatus or None if provider not found.
        """
        if name is None:
            name = self._active_provider
        
        if name is None or name not in self._providers:
            return None
        
        return self._providers[name].status
    
    def update_provider_settings(
        self,
        name: str,
        settings: dict[str, Any],
        reconnect: bool = False,
    ) -> bool:
        """
        Update provider settings.
        
        Args:
            name: Provider name
            settings: New settings (merged with existing)
            reconnect: Whether to reconnect after updating
        
        Returns:
            True if updated successfully, False otherwise.
        """
        if name not in self._configs:
            return False
        
        config = self._configs[name]
        config.settings.update(settings)
        
        if reconnect and name == self._active_provider:
            self.disconnect(name)
            return self.connect(name)
        
        return True
    
    def export_configs(self) -> list[dict[str, Any]]:
        """
        Export all provider configurations.
        
        Returns:
            List of configuration dictionaries.
        """
        return [config.to_dict() for config in self._configs.values()]
    
    def import_configs(self, configs: list[dict[str, Any]]) -> int:
        """
        Import provider configurations.
        
        Args:
            configs: List of configuration dictionaries
        
        Returns:
            Number of configurations imported.
        """
        count = 0
        for config_dict in configs:
            try:
                config = ProviderConfig.from_dict(config_dict)
                if config.name not in self._configs:
                    self.add_provider(config)
                    count += 1
            except Exception:
                continue
        return count


# Global manager instance
_manager: DataProviderManager | None = None


def get_provider_manager() -> DataProviderManager:
    """
    Get the global data provider manager instance.
    
    Returns:
        DataProviderManager instance.
    """
    global _manager
    if _manager is None:
        _manager = DataProviderManager()
    return _manager


def reset_provider_manager() -> None:
    """Reset the global data provider manager instance."""
    global _manager
    if _manager is not None:
        _manager.disconnect_all()
    _manager = None


__all__ = [
    "ProviderConfig",
    "DataProviderManager",
    "get_provider_manager",
    "reset_provider_manager",
]
