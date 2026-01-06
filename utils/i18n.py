"""
Internationalization (I18N) Module for Titan-Quant

This module provides internationalization support for the Titan-Quant system,
enabling multi-language support for error messages, audit logs, and alerts.

Features:
- Language pack loading from JSON files
- Dynamic language switching
- Parameter interpolation in translations
- Fallback to default language when translation is missing
- Thread-safe singleton pattern

Usage:
    from utils.i18n import get_i18n_manager, Language, translate
    
    # Get the singleton instance
    i18n = get_i18n_manager()
    
    # Set language
    i18n.set_language(Language.ZH_CN)
    
    # Translate with parameters
    message = i18n.translate("error.insufficient_fund", required=100, available=50)
    
    # Or use the convenience function
    message = translate("error.insufficient_fund", required=100, available=50)
"""
from __future__ import annotations

import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Language(Enum):
    """Supported languages."""
    EN = "en"
    ZH_CN = "zh_cn"
    ZH_TW = "zh_tw"
    JA = "ja"


@dataclass
class I18nConfig:
    """Internationalization configuration."""
    default_language: Language = Language.ZH_CN
    fallback_language: Language = Language.EN
    language_pack_dir: str = "config/i18n"


class II18nManager(ABC):
    """Abstract interface for internationalization manager."""
    
    @abstractmethod
    def load_language_pack(self, lang: Language) -> bool:
        """Load language pack JSON file."""
        pass
    
    @abstractmethod
    def set_language(self, lang: Language) -> bool:
        """Set current language."""
        pass
    
    @abstractmethod
    def get_current_language(self) -> Language:
        """Get current language."""
        pass
    
    @abstractmethod
    def translate(self, key: str, **kwargs: Any) -> str:
        """
        Translate text with parameter interpolation.
        
        Args:
            key: Translation key in dot notation (e.g., "error.insufficient_fund")
            **kwargs: Parameters for interpolation
            
        Returns:
            Translated string with parameters substituted
        """
        pass
    
    @abstractmethod
    def get_all_keys(self) -> List[str]:
        """Get all translation keys."""
        pass


class I18nManager(II18nManager):
    """
    Internationalization manager implementation.
    
    Provides language pack loading, dynamic language switching,
    and parameter interpolation for translations.
    """
    
    def __init__(self, config: Optional[I18nConfig] = None) -> None:
        """
        Initialize I18nManager.
        
        Args:
            config: I18n configuration, uses defaults if not provided
        """
        self._config = config or I18nConfig()
        self._current_language = self._config.default_language
        self._language_packs: Dict[Language, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        
        # Try to load default and fallback language packs
        self._load_initial_packs()
    
    def _load_initial_packs(self) -> None:
        """Load initial language packs (default and fallback)."""
        # Load fallback language first
        self.load_language_pack(self._config.fallback_language)
        
        # Load default language if different from fallback
        if self._config.default_language != self._config.fallback_language:
            self.load_language_pack(self._config.default_language)
    
    def _get_language_file_path(self, lang: Language) -> Path:
        """Get the file path for a language pack."""
        return Path(self._config.language_pack_dir) / f"{lang.value}.json"
    
    def load_language_pack(self, lang: Language) -> bool:
        """
        Load language pack from JSON file.
        
        Args:
            lang: Language to load
            
        Returns:
            True if loaded successfully, False otherwise
        """
        file_path = self._get_language_file_path(lang)
        
        try:
            if not file_path.exists():
                return False
            
            with open(file_path, "r", encoding="utf-8") as f:
                pack = json.load(f)
            
            with self._lock:
                self._language_packs[lang] = pack
            
            return True
        except (json.JSONDecodeError, IOError, OSError):
            return False
    
    def set_language(self, lang: Language) -> bool:
        """
        Set current language.
        
        Args:
            lang: Language to set
            
        Returns:
            True if language was set successfully
        """
        with self._lock:
            # Load language pack if not already loaded
            if lang not in self._language_packs:
                if not self.load_language_pack(lang):
                    return False
            
            self._current_language = lang
            return True
    
    def get_current_language(self) -> Language:
        """Get current language."""
        with self._lock:
            return self._current_language
    
    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Optional[str]:
        """
        Get nested value from dictionary using dot notation.
        
        Args:
            data: Dictionary to search
            key: Key in dot notation (e.g., "error.insufficient_fund")
            
        Returns:
            Value if found, None otherwise
        """
        keys = key.split(".")
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        
        return current if isinstance(current, str) else None
    
    def _flatten_keys(self, data: Dict[str, Any], prefix: str = "") -> List[str]:
        """
        Flatten nested dictionary keys into dot notation.
        
        Args:
            data: Dictionary to flatten
            prefix: Current key prefix
            
        Returns:
            List of flattened keys
        """
        keys = []
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.extend(self._flatten_keys(v, full_key))
            else:
                keys.append(full_key)
        return keys
    
    def translate(self, key: str, **kwargs: Any) -> str:
        """
        Translate text with parameter interpolation.
        
        Args:
            key: Translation key in dot notation
            **kwargs: Parameters for interpolation
            
        Returns:
            Translated string with parameters substituted.
            Returns the key itself if translation not found.
        """
        with self._lock:
            # Try current language
            if self._current_language in self._language_packs:
                value = self._get_nested_value(
                    self._language_packs[self._current_language], key
                )
                if value is not None:
                    return self._interpolate(value, kwargs)
            
            # Try fallback language
            if self._config.fallback_language in self._language_packs:
                value = self._get_nested_value(
                    self._language_packs[self._config.fallback_language], key
                )
                if value is not None:
                    return self._interpolate(value, kwargs)
            
            # Return key if no translation found
            return key
    
    def _interpolate(self, template: str, params: Dict[str, Any]) -> str:
        """
        Interpolate parameters into template string.
        
        Uses Python's str.format() style placeholders: {param_name}
        
        Args:
            template: Template string with placeholders
            params: Parameters to substitute
            
        Returns:
            Interpolated string
        """
        try:
            return template.format(**params)
        except KeyError:
            # Return template with available substitutions
            for k, v in params.items():
                template = template.replace(f"{{{k}}}", str(v))
            return template
    
    def get_all_keys(self) -> List[str]:
        """
        Get all translation keys from current language pack.
        
        Returns:
            List of all translation keys in dot notation
        """
        with self._lock:
            if self._current_language in self._language_packs:
                return self._flatten_keys(self._language_packs[self._current_language])
            return []
    
    def has_key(self, key: str) -> bool:
        """
        Check if a translation key exists.
        
        Args:
            key: Translation key to check
            
        Returns:
            True if key exists in current or fallback language
        """
        with self._lock:
            # Check current language
            if self._current_language in self._language_packs:
                if self._get_nested_value(
                    self._language_packs[self._current_language], key
                ) is not None:
                    return True
            
            # Check fallback language
            if self._config.fallback_language in self._language_packs:
                if self._get_nested_value(
                    self._language_packs[self._config.fallback_language], key
                ) is not None:
                    return True
            
            return False
    
    def get_available_languages(self) -> List[Language]:
        """
        Get list of languages with loaded packs.
        
        Returns:
            List of available languages
        """
        with self._lock:
            return list(self._language_packs.keys())
    
    def reload_language_packs(self) -> bool:
        """
        Reload all language packs from disk.
        
        Returns:
            True if all packs reloaded successfully
        """
        with self._lock:
            languages = list(self._language_packs.keys())
            self._language_packs.clear()
            
            success = True
            for lang in languages:
                if not self.load_language_pack(lang):
                    success = False
            
            return success


# Singleton instance
_i18n_manager: Optional[I18nManager] = None
_i18n_lock = threading.Lock()


def get_i18n_manager(config: Optional[I18nConfig] = None) -> I18nManager:
    """
    Get the singleton I18nManager instance.
    
    Args:
        config: Optional configuration (only used on first call)
        
    Returns:
        I18nManager singleton instance
    """
    global _i18n_manager
    
    if _i18n_manager is None:
        with _i18n_lock:
            if _i18n_manager is None:
                _i18n_manager = I18nManager(config)
    
    return _i18n_manager


def set_i18n_manager(manager: I18nManager) -> None:
    """
    Set the singleton I18nManager instance.
    
    Useful for testing or custom configurations.
    
    Args:
        manager: I18nManager instance to use
    """
    global _i18n_manager
    with _i18n_lock:
        _i18n_manager = manager


def reset_i18n_manager() -> None:
    """Reset the singleton I18nManager instance."""
    global _i18n_manager
    with _i18n_lock:
        _i18n_manager = None


# Convenience functions
def translate(key: str, **kwargs: Any) -> str:
    """
    Translate text using the singleton I18nManager.
    
    Args:
        key: Translation key in dot notation
        **kwargs: Parameters for interpolation
        
    Returns:
        Translated string
    """
    return get_i18n_manager().translate(key, **kwargs)


def set_language(lang: Language) -> bool:
    """
    Set current language using the singleton I18nManager.
    
    Args:
        lang: Language to set
        
    Returns:
        True if language was set successfully
    """
    return get_i18n_manager().set_language(lang)


def get_current_language() -> Language:
    """
    Get current language from the singleton I18nManager.
    
    Returns:
        Current language
    """
    return get_i18n_manager().get_current_language()


# I18N Keys for the system
class I18nKeys:
    """Standard I18N keys used throughout the system."""
    
    # Error messages
    ERROR_INSUFFICIENT_FUND = "error.insufficient_fund"
    ERROR_ORDER_REJECTED = "error.order_rejected"
    ERROR_STRATEGY_ERROR = "error.strategy_error"
    ERROR_ENGINE_INIT_FAILED = "error.engine_init_failed"
    ERROR_DATA_FORMAT_INVALID = "error.data_format_invalid"
    ERROR_DATA_IMPORT_FAILED = "error.data_import_failed"
    ERROR_STRATEGY_LOAD_FAILED = "error.strategy_load_failed"
    ERROR_SNAPSHOT_NOT_FOUND = "error.snapshot_not_found"
    ERROR_SNAPSHOT_VERSION_MISMATCH = "error.snapshot_version_mismatch"
    ERROR_AUDIT_INTEGRITY_VIOLATION = "error.audit_integrity_violation"
    ERROR_RISK_DRAWDOWN_EXCEEDED = "error.risk_drawdown_exceeded"
    ERROR_RISK_SINGLE_LOSS_EXCEEDED = "error.risk_single_loss_exceeded"
    ERROR_HOT_RELOAD_FAILED = "error.hot_reload_failed"
    ERROR_CONNECTION_FAILED = "error.connection_failed"
    ERROR_AUTHENTICATION_FAILED = "error.authentication_failed"
    ERROR_PERMISSION_DENIED = "error.permission_denied"
    
    # Audit log types
    AUDIT_MANUAL_TRADE = "audit.manual_trade"
    AUDIT_PARAM_CHANGE = "audit.param_change"
    AUDIT_STRATEGY_RELOAD = "audit.strategy_reload"
    AUDIT_USER_LOGIN = "audit.user_login"
    AUDIT_USER_LOGOUT = "audit.user_logout"
    AUDIT_RISK_TRIGGER = "audit.risk_trigger"
    AUDIT_SNAPSHOT_CREATED = "audit.snapshot_created"
    AUDIT_SNAPSHOT_RESTORED = "audit.snapshot_restored"
    AUDIT_BACKTEST_STARTED = "audit.backtest_started"
    AUDIT_BACKTEST_COMPLETED = "audit.backtest_completed"
    AUDIT_CLOSE_ALL_POSITIONS = "audit.close_all_positions"
    
    # Alert messages
    ALERT_RISK_TRIGGER = "alert.risk_trigger"
    ALERT_BACKTEST_COMPLETE = "alert.backtest_complete"
    ALERT_STRATEGY_ERROR = "alert.strategy_error"
    ALERT_CONNECTION_LOST = "alert.connection_lost"
    ALERT_CONNECTION_RESTORED = "alert.connection_restored"
    ALERT_AUDIT_INTEGRITY_VIOLATION = "alert.audit_integrity_violation"
    ALERT_SYSTEM_ERROR = "alert.system_error"
    
    # UI labels
    UI_LOGIN = "ui.login"
    UI_LOGOUT = "ui.logout"
    UI_START_BACKTEST = "ui.start_backtest"
    UI_STOP_BACKTEST = "ui.stop_backtest"
    UI_PAUSE = "ui.pause"
    UI_RESUME = "ui.resume"
    UI_SAVE_SNAPSHOT = "ui.save_snapshot"
    UI_LOAD_SNAPSHOT = "ui.load_snapshot"
    UI_CLOSE_ALL = "ui.close_all"
    
    # Status messages
    STATUS_RUNNING = "status.running"
    STATUS_PAUSED = "status.paused"
    STATUS_COMPLETED = "status.completed"
    STATUS_FAILED = "status.failed"
    STATUS_CONNECTED = "status.connected"
    STATUS_DISCONNECTED = "status.disconnected"


# ============================================================================
# I18N Integration Helpers for Existing Modules
# ============================================================================

def translate_error(error_key: str, **kwargs: Any) -> str:
    """
    Translate an error message.
    
    Args:
        error_key: Error key (e.g., "insufficient_fund")
        **kwargs: Parameters for interpolation
        
    Returns:
        Translated error message
    """
    full_key = f"error.{error_key}" if not error_key.startswith("error.") else error_key
    return translate(full_key, **kwargs)


def translate_audit(audit_key: str, **kwargs: Any) -> str:
    """
    Translate an audit log type.
    
    Args:
        audit_key: Audit key (e.g., "manual_trade")
        **kwargs: Parameters for interpolation
        
    Returns:
        Translated audit type
    """
    full_key = f"audit.{audit_key}" if not audit_key.startswith("audit.") else audit_key
    return translate(full_key, **kwargs)


def translate_alert(alert_key: str, **kwargs: Any) -> str:
    """
    Translate an alert message.
    
    Args:
        alert_key: Alert key (e.g., "risk_trigger")
        **kwargs: Parameters for interpolation
        
    Returns:
        Translated alert message
    """
    full_key = f"alert.{alert_key}" if not alert_key.startswith("alert.") else alert_key
    return translate(full_key, **kwargs)


def translate_status(status_key: str, **kwargs: Any) -> str:
    """
    Translate a status message.
    
    Args:
        status_key: Status key (e.g., "running")
        **kwargs: Parameters for interpolation
        
    Returns:
        Translated status message
    """
    full_key = f"status.{status_key}" if not status_key.startswith("status.") else status_key
    return translate(full_key, **kwargs)


def translate_ui(ui_key: str, **kwargs: Any) -> str:
    """
    Translate a UI label.
    
    Args:
        ui_key: UI key (e.g., "login")
        **kwargs: Parameters for interpolation
        
    Returns:
        Translated UI label
    """
    full_key = f"ui.{ui_key}" if not ui_key.startswith("ui.") else ui_key
    return translate(full_key, **kwargs)


def get_localized_action_type(action_type: str) -> str:
    """
    Get localized action type name for audit logs.
    
    Maps ActionType enum values to I18N keys.
    
    Args:
        action_type: Action type value (e.g., "MANUAL_TRADE")
        
    Returns:
        Localized action type name
    """
    action_map = {
        "MANUAL_TRADE": "audit.manual_trade",
        "AUTO_TRADE": "audit.order_submitted",
        "PARAM_CHANGE": "audit.param_change",
        "STRATEGY_RELOAD": "audit.strategy_reload",
        "STRATEGY_LOAD": "audit.strategy_started",
        "RISK_TRIGGER": "audit.risk_trigger",
        "SNAPSHOT_SAVE": "audit.snapshot_created",
        "SNAPSHOT_LOAD": "audit.snapshot_restored",
        "USER_LOGIN": "audit.user_login",
        "USER_LOGOUT": "audit.user_logout",
        "SYSTEM_START": "audit.backtest_started",
        "SYSTEM_STOP": "audit.backtest_completed",
        "CLOSE_ALL_POSITIONS": "audit.close_all_positions",
        "CONFIG_CHANGE": "audit.config_changed",
    }
    
    key = action_map.get(action_type, f"audit.{action_type.lower()}")
    return translate(key)


def get_localized_alert_event(event_type: str) -> str:
    """
    Get localized alert event type name.
    
    Args:
        event_type: Alert event type value
        
    Returns:
        Localized event type name
    """
    event_map = {
        "risk_trigger": "alert.risk_trigger",
        "strategy_error": "alert.strategy_error",
        "backtest_complete": "alert.backtest_complete",
        "system_error": "alert.system_error",
        "data_error": "error.data_import_failed",
        "connection_lost": "alert.connection_lost",
        "position_liquidated": "audit.close_all_positions",
        "daily_report": "alert.backtest_complete",
    }
    
    key = event_map.get(event_type, f"alert.{event_type}")
    return translate(key)


__all__ = [
    # Enums
    "Language",
    # Data classes
    "I18nConfig",
    # Interfaces
    "II18nManager",
    # Implementation
    "I18nManager",
    # Singleton functions
    "get_i18n_manager",
    "set_i18n_manager",
    "reset_i18n_manager",
    # Convenience functions
    "translate",
    "set_language",
    "get_current_language",
    # Keys
    "I18nKeys",
    # Integration helpers
    "translate_error",
    "translate_audit",
    "translate_alert",
    "translate_status",
    "translate_ui",
    "get_localized_action_type",
    "get_localized_alert_event",
]
