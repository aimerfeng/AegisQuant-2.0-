"""
Utility Modules
- Audit Logger
- Encryption
- Notification
- I18N
"""

from utils.audit import (
    ActionType,
    GENESIS_HASH,
    AuditRecord,
    compute_record_hash,
    verify_record_hash,
    compute_file_checksum,
    IAuditLogger,
    AuditLogger,
    verify_audit_logs_on_startup,
)

from utils.encrypt import (
    EncryptionError,
    IEncryptionService,
    FernetEncryption,
    SensitiveDataFilter,
    create_secure_logger,
    get_encryption_service,
    encrypt,
    decrypt,
)

from utils.notifier import (
    # Enums
    AlertType,
    AlertChannel,
    AlertSeverity,
    AlertEventType,
    # Data classes
    Alert,
    AlertConfig,
    EmailConfig,
    WebhookConfig,
    # Interfaces
    INotificationChannel,
    IAlertSystem,
    # Channel implementations
    EmailChannel,
    WebhookChannel,
    SystemNotificationChannel,
    # Main implementation
    AlertSystem,
    # Convenience functions
    get_alert_system,
    set_alert_system,
    send_sync_alert,
    send_async_alert,
)

from utils.i18n import (
    # Enums
    Language,
    # Data classes
    I18nConfig,
    # Interfaces
    II18nManager,
    # Implementation
    I18nManager,
    # Singleton functions
    get_i18n_manager,
    set_i18n_manager,
    reset_i18n_manager,
    # Convenience functions
    translate,
    set_language,
    get_current_language,
    # Keys
    I18nKeys,
    # Integration helpers
    translate_error,
    translate_audit,
    translate_alert,
    translate_status,
    translate_ui,
    get_localized_action_type,
    get_localized_alert_event,
)

__all__ = [
    # Audit Logger
    "ActionType",
    "GENESIS_HASH",
    "AuditRecord",
    "compute_record_hash",
    "verify_record_hash",
    "compute_file_checksum",
    "IAuditLogger",
    "AuditLogger",
    "verify_audit_logs_on_startup",
    # Encryption
    "EncryptionError",
    "IEncryptionService",
    "FernetEncryption",
    "SensitiveDataFilter",
    "create_secure_logger",
    "get_encryption_service",
    "encrypt",
    "decrypt",
    # Notifier
    "AlertType",
    "AlertChannel",
    "AlertSeverity",
    "AlertEventType",
    "Alert",
    "AlertConfig",
    "EmailConfig",
    "WebhookConfig",
    "INotificationChannel",
    "IAlertSystem",
    "EmailChannel",
    "WebhookChannel",
    "SystemNotificationChannel",
    "AlertSystem",
    "get_alert_system",
    "set_alert_system",
    "send_sync_alert",
    "send_async_alert",
    # I18N
    "Language",
    "I18nConfig",
    "II18nManager",
    "I18nManager",
    "get_i18n_manager",
    "set_i18n_manager",
    "reset_i18n_manager",
    "translate",
    "set_language",
    "get_current_language",
    "I18nKeys",
    "translate_error",
    "translate_audit",
    "translate_alert",
    "translate_status",
    "translate_ui",
    "get_localized_action_type",
    "get_localized_alert_event",
]
