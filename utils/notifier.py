"""
Titan-Quant Alert/Notification System

This module implements the alert and notification system with support for
synchronous (blocking) and asynchronous (non-blocking) alerts, as well as
multiple notification channels (Email, Webhook).

Requirements:
    - 11.1: THE Titan_Quant_System SHALL 支持 SMTP 邮件通知
    - 11.2: THE Titan_Quant_System SHALL 支持 Webhook 通知（飞书/钉钉）
    - 11.3: THE Titan_Quant_System SHALL 区分两种告警类型：
            - Sync_Alert（同步告警）: 阻塞当前流程直到用户确认
            - Async_Alert（异步告警）: 不阻塞流程，后台发送
    - 11.4: WHEN 策略报错或触发风控, THEN THE UI_Client SHALL 发送 Sync_Alert
    - 11.5: WHEN 回测完成或定时报告, THEN THE Titan_Quant_System SHALL 发送 Async_Alert
    - 11.6: THE Titan_Quant_System SHALL 允许用户为每种事件类型配置告警级别和通知渠道
"""
from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import ssl
import threading
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


logger = logging.getLogger(__name__)


class AlertType(Enum):
    """
    Alert type classification.
    
    - SYNC: Synchronous alert that blocks the current flow until acknowledged
    - ASYNC: Asynchronous alert that doesn't block, sent in background
    """
    SYNC = "sync"
    ASYNC = "async"


class AlertChannel(Enum):
    """
    Notification channels for alerts.
    
    - EMAIL: SMTP email notification
    - WEBHOOK: HTTP webhook (Feishu/DingTalk/Slack)
    - SYSTEM_NOTIFICATION: Native system notification (for UI client)
    """
    EMAIL = "email"
    WEBHOOK = "webhook"
    SYSTEM_NOTIFICATION = "system_notification"


class AlertSeverity(Enum):
    """
    Alert severity levels.
    
    - INFO: Informational messages
    - WARNING: Warning messages that may require attention
    - ERROR: Error messages indicating problems
    - CRITICAL: Critical messages requiring immediate action
    """
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertEventType(Enum):
    """
    Predefined alert event types for configuration.
    """
    RISK_TRIGGER = "risk_trigger"
    STRATEGY_ERROR = "strategy_error"
    BACKTEST_COMPLETE = "backtest_complete"
    SYSTEM_ERROR = "system_error"
    DATA_ERROR = "data_error"
    CONNECTION_LOST = "connection_lost"
    POSITION_LIQUIDATED = "position_liquidated"
    DAILY_REPORT = "daily_report"
    CUSTOM = "custom"


@dataclass
class Alert:
    """
    Alert message data class.
    
    Attributes:
        alert_id: Unique identifier for the alert
        alert_type: Type of alert (SYNC or ASYNC)
        severity: Severity level of the alert
        title: Alert title/subject
        message: Detailed alert message
        timestamp: When the alert was created
        event_type: The event type that triggered this alert
        acknowledged: Whether the alert has been acknowledged (for SYNC alerts)
        acknowledged_at: When the alert was acknowledged
        acknowledged_by: Who acknowledged the alert
        metadata: Additional metadata for the alert
    """
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = AlertEventType.CUSTOM.value
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Alert:
        """Create Alert from dictionary."""
        return cls(
            alert_id=data["alert_id"],
            alert_type=AlertType(data["alert_type"]),
            severity=AlertSeverity(data["severity"]),
            title=data["title"],
            message=data["message"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=data.get("event_type", AlertEventType.CUSTOM.value),
            acknowledged=data.get("acknowledged", False),
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            acknowledged_by=data.get("acknowledged_by"),
            metadata=data.get("metadata", {}),
        )
    
    def acknowledge(self, user_id: str) -> None:
        """Mark the alert as acknowledged."""
        self.acknowledged = True
        self.acknowledged_at = datetime.now()
        self.acknowledged_by = user_id


@dataclass
class AlertConfig:
    """
    Configuration for alert rules.
    
    Defines how a specific event type should be handled in terms of
    alert type, channels, and severity.
    
    Attributes:
        event_type: The event type this config applies to
        alert_type: Whether to use SYNC or ASYNC alerts
        channels: List of notification channels to use
        severity: Default severity level for this event type
        enabled: Whether this alert config is active
        template_title: Optional title template with {placeholders}
        template_message: Optional message template with {placeholders}
    """
    event_type: str
    alert_type: AlertType
    channels: List[AlertChannel]
    severity: AlertSeverity
    enabled: bool = True
    template_title: Optional[str] = None
    template_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "alert_type": self.alert_type.value,
            "channels": [c.value for c in self.channels],
            "severity": self.severity.value,
            "enabled": self.enabled,
            "template_title": self.template_title,
            "template_message": self.template_message,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AlertConfig:
        """Create AlertConfig from dictionary."""
        return cls(
            event_type=data["event_type"],
            alert_type=AlertType(data["alert_type"]),
            channels=[AlertChannel(c) for c in data["channels"]],
            severity=AlertSeverity(data["severity"]),
            enabled=data.get("enabled", True),
            template_title=data.get("template_title"),
            template_message=data.get("template_message"),
        )



@dataclass
class EmailConfig:
    """
    SMTP email configuration.
    
    Attributes:
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port
        username: SMTP authentication username
        password: SMTP authentication password (should be encrypted)
        sender_email: Email address to send from
        use_tls: Whether to use TLS encryption
        use_ssl: Whether to use SSL encryption
    """
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    sender_email: str
    use_tls: bool = True
    use_ssl: bool = False


@dataclass
class WebhookConfig:
    """
    Webhook configuration for Feishu/DingTalk/Slack.
    
    Attributes:
        url: Webhook URL
        webhook_type: Type of webhook ("feishu", "dingtalk", "slack", "custom")
        secret: Optional secret for signature verification
        headers: Optional additional headers
    """
    url: str
    webhook_type: str = "custom"
    secret: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


class INotificationChannel(ABC):
    """
    Abstract interface for notification channels.
    """
    
    @abstractmethod
    def send(self, alert: Alert, recipients: List[str]) -> bool:
        """
        Send an alert through this channel.
        
        Args:
            alert: The alert to send.
            recipients: List of recipients (email addresses, webhook URLs, etc.)
            
        Returns:
            True if sent successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_channel_type(self) -> AlertChannel:
        """Get the channel type."""
        pass


class EmailChannel(INotificationChannel):
    """
    Email notification channel using SMTP.
    
    Implements Requirement 11.1: SMTP email notification support.
    """
    
    def __init__(self, config: EmailConfig) -> None:
        """
        Initialize the email channel.
        
        Args:
            config: Email configuration.
        """
        self._config = config
    
    def send(self, alert: Alert, recipients: List[str]) -> bool:
        """
        Send an alert via email.
        
        Args:
            alert: The alert to send.
            recipients: List of email addresses.
            
        Returns:
            True if sent successfully, False otherwise.
        """
        if not recipients:
            logger.warning("No email recipients specified")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"
            msg["From"] = self._config.sender_email
            msg["To"] = ", ".join(recipients)
            
            # Create plain text and HTML versions
            text_content = self._format_text_message(alert)
            html_content = self._format_html_message(alert)
            
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))
            
            # Send email
            if self._config.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self._config.smtp_host,
                    self._config.smtp_port,
                    context=context
                ) as server:
                    server.login(self._config.username, self._config.password)
                    server.sendmail(
                        self._config.sender_email,
                        recipients,
                        msg.as_string()
                    )
            else:
                with smtplib.SMTP(
                    self._config.smtp_host,
                    self._config.smtp_port
                ) as server:
                    if self._config.use_tls:
                        server.starttls()
                    server.login(self._config.username, self._config.password)
                    server.sendmail(
                        self._config.sender_email,
                        recipients,
                        msg.as_string()
                    )
            
            logger.info(f"Email sent successfully to {recipients}")
            return True
            
        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False
    
    def _format_text_message(self, alert: Alert) -> str:
        """Format alert as plain text."""
        return f"""
Titan-Quant Alert
=================

Severity: {alert.severity.value.upper()}
Type: {alert.alert_type.value}
Event: {alert.event_type}
Time: {alert.timestamp.isoformat()}

Title: {alert.title}

Message:
{alert.message}

Alert ID: {alert.alert_id}
"""
    
    def _format_html_message(self, alert: Alert) -> str:
        """Format alert as HTML."""
        severity_colors = {
            AlertSeverity.INFO: "#17a2b8",
            AlertSeverity.WARNING: "#ffc107",
            AlertSeverity.ERROR: "#dc3545",
            AlertSeverity.CRITICAL: "#721c24",
        }
        color = severity_colors.get(alert.severity, "#6c757d")
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .alert-box {{ border: 2px solid {color}; border-radius: 8px; padding: 20px; }}
        .severity {{ color: {color}; font-weight: bold; font-size: 14px; }}
        .title {{ font-size: 18px; font-weight: bold; margin: 10px 0; }}
        .message {{ margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 4px; }}
        .meta {{ font-size: 12px; color: #6c757d; }}
    </style>
</head>
<body>
    <div class="alert-box">
        <div class="severity">[{alert.severity.value.upper()}] {alert.event_type}</div>
        <div class="title">{alert.title}</div>
        <div class="message">{alert.message}</div>
        <div class="meta">
            <p>Time: {alert.timestamp.isoformat()}</p>
            <p>Alert ID: {alert.alert_id}</p>
        </div>
    </div>
</body>
</html>
"""
    
    def get_channel_type(self) -> AlertChannel:
        """Get the channel type."""
        return AlertChannel.EMAIL


class WebhookChannel(INotificationChannel):
    """
    Webhook notification channel for Feishu/DingTalk/Slack.
    
    Implements Requirement 11.2: Webhook notification support.
    """
    
    def __init__(self, config: WebhookConfig) -> None:
        """
        Initialize the webhook channel.
        
        Args:
            config: Webhook configuration.
        """
        self._config = config
    
    def send(self, alert: Alert, recipients: List[str]) -> bool:
        """
        Send an alert via webhook.
        
        Args:
            alert: The alert to send.
            recipients: List of webhook URLs (overrides config URL if provided).
            
        Returns:
            True if sent successfully, False otherwise.
        """
        urls = recipients if recipients else [self._config.url]
        
        success = True
        for url in urls:
            try:
                payload = self._format_payload(alert)
                headers = {
                    "Content-Type": "application/json",
                    **self._config.headers
                }
                
                request = Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                
                with urlopen(request, timeout=10) as response:
                    if response.status == 200:
                        logger.info(f"Webhook sent successfully to {url}")
                    else:
                        logger.warning(f"Webhook returned status {response.status}")
                        success = False
                        
            except (URLError, HTTPError) as e:
                logger.error(f"Failed to send webhook to {url}: {e}")
                success = False
            except Exception as e:
                logger.error(f"Unexpected error sending webhook: {e}")
                success = False
        
        return success
    
    def _format_payload(self, alert: Alert) -> Dict[str, Any]:
        """Format alert as webhook payload based on webhook type."""
        if self._config.webhook_type == "feishu":
            return self._format_feishu_payload(alert)
        elif self._config.webhook_type == "dingtalk":
            return self._format_dingtalk_payload(alert)
        elif self._config.webhook_type == "slack":
            return self._format_slack_payload(alert)
        else:
            return self._format_generic_payload(alert)
    
    def _format_feishu_payload(self, alert: Alert) -> Dict[str, Any]:
        """Format payload for Feishu (飞书)."""
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"[{alert.severity.value.upper()}] {alert.title}"
                    },
                    "template": self._get_feishu_color(alert.severity)
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "plain_text",
                            "content": alert.message
                        }
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"Event: {alert.event_type} | Time: {alert.timestamp.isoformat()}"
                            }
                        ]
                    }
                ]
            }
        }
    
    def _get_feishu_color(self, severity: AlertSeverity) -> str:
        """Get Feishu card color based on severity."""
        colors = {
            AlertSeverity.INFO: "blue",
            AlertSeverity.WARNING: "yellow",
            AlertSeverity.ERROR: "red",
            AlertSeverity.CRITICAL: "red",
        }
        return colors.get(severity, "grey")
    
    def _format_dingtalk_payload(self, alert: Alert) -> Dict[str, Any]:
        """Format payload for DingTalk (钉钉)."""
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"[{alert.severity.value.upper()}] {alert.title}",
                "text": f"""### [{alert.severity.value.upper()}] {alert.title}

{alert.message}

---
- Event: {alert.event_type}
- Time: {alert.timestamp.isoformat()}
- Alert ID: {alert.alert_id}
"""
            }
        }
    
    def _format_slack_payload(self, alert: Alert) -> Dict[str, Any]:
        """Format payload for Slack."""
        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ffcc00",
            AlertSeverity.ERROR: "#ff0000",
            AlertSeverity.CRITICAL: "#8b0000",
        }
        
        return {
            "attachments": [
                {
                    "color": color_map.get(alert.severity, "#808080"),
                    "title": f"[{alert.severity.value.upper()}] {alert.title}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Event", "value": alert.event_type, "short": True},
                        {"title": "Time", "value": alert.timestamp.isoformat(), "short": True},
                    ],
                    "footer": f"Alert ID: {alert.alert_id}"
                }
            ]
        }
    
    def _format_generic_payload(self, alert: Alert) -> Dict[str, Any]:
        """Format generic webhook payload."""
        return alert.to_dict()
    
    def get_channel_type(self) -> AlertChannel:
        """Get the channel type."""
        return AlertChannel.WEBHOOK


class SystemNotificationChannel(INotificationChannel):
    """
    System notification channel for UI client notifications.
    
    This channel stores alerts for the UI client to retrieve and display
    as native system notifications.
    """
    
    def __init__(self, callback: Optional[Callable[[Alert], None]] = None) -> None:
        """
        Initialize the system notification channel.
        
        Args:
            callback: Optional callback function to invoke when an alert is sent.
        """
        self._callback = callback
        self._pending_alerts: List[Alert] = []
        self._lock = threading.Lock()
    
    def send(self, alert: Alert, recipients: List[str]) -> bool:
        """
        Send a system notification.
        
        Args:
            alert: The alert to send.
            recipients: Ignored for system notifications.
            
        Returns:
            True always (notifications are stored locally).
        """
        with self._lock:
            self._pending_alerts.append(alert)
        
        if self._callback:
            try:
                self._callback(alert)
            except Exception as e:
                logger.error(f"System notification callback error: {e}")
        
        logger.info(f"System notification queued: {alert.title}")
        return True
    
    def get_pending_alerts(self) -> List[Alert]:
        """Get and clear pending alerts."""
        with self._lock:
            alerts = self._pending_alerts.copy()
            self._pending_alerts.clear()
            return alerts
    
    def get_channel_type(self) -> AlertChannel:
        """Get the channel type."""
        return AlertChannel.SYSTEM_NOTIFICATION


class IAlertSystem(ABC):
    """
    Abstract interface for the Alert System.
    
    The Alert System provides both synchronous (blocking) and asynchronous
    (non-blocking) alert capabilities with multiple notification channels.
    """
    
    @abstractmethod
    def send_sync_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        event_type: str = AlertEventType.CUSTOM.value,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a synchronous alert that blocks until acknowledged.
        
        Args:
            title: Alert title.
            message: Alert message.
            severity: Alert severity level.
            event_type: Type of event that triggered the alert.
            metadata: Optional additional metadata.
            
        Returns:
            True if acknowledged, False if timed out or failed.
        """
        pass
    
    @abstractmethod
    def send_async_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        channels: List[AlertChannel],
        event_type: str = AlertEventType.CUSTOM.value,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Send an asynchronous alert that doesn't block.
        
        Args:
            title: Alert title.
            message: Alert message.
            severity: Alert severity level.
            channels: List of channels to send through.
            event_type: Type of event that triggered the alert.
            metadata: Optional additional metadata.
            
        Returns:
            The alert ID.
        """
        pass
    
    @abstractmethod
    def configure_event_alert(self, config: AlertConfig) -> bool:
        """
        Configure alert rules for an event type.
        
        Args:
            config: Alert configuration.
            
        Returns:
            True if configured successfully.
        """
        pass
    
    @abstractmethod
    def acknowledge_alert(self, alert_id: str, user_id: str) -> bool:
        """
        Acknowledge a synchronous alert.
        
        Args:
            alert_id: ID of the alert to acknowledge.
            user_id: ID of the user acknowledging.
            
        Returns:
            True if acknowledged successfully.
        """
        pass
    
    @abstractmethod
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Get an alert by ID.
        
        Args:
            alert_id: The alert ID.
            
        Returns:
            The alert if found, None otherwise.
        """
        pass


class AlertSystem(IAlertSystem):
    """
    Alert system implementation with sync/async support.
    
    This class implements the full alert system with:
    - Synchronous alerts that block until acknowledged
    - Asynchronous alerts sent in background threads
    - Multiple notification channels (Email, Webhook, System)
    - Configurable alert rules per event type
    
    Implements Requirements 11.3, 11.4, 11.5, 11.6
    """
    
    # Default timeout for sync alerts (seconds)
    DEFAULT_SYNC_TIMEOUT = 300  # 5 minutes
    
    def __init__(
        self,
        email_config: Optional[EmailConfig] = None,
        webhook_config: Optional[WebhookConfig] = None,
        system_notification_callback: Optional[Callable[[Alert], None]] = None,
        sync_timeout: float = DEFAULT_SYNC_TIMEOUT,
        max_workers: int = 4
    ) -> None:
        """
        Initialize the alert system.
        
        Args:
            email_config: Optional email channel configuration.
            webhook_config: Optional webhook channel configuration.
            system_notification_callback: Optional callback for system notifications.
            sync_timeout: Timeout for synchronous alerts in seconds.
            max_workers: Maximum number of worker threads for async alerts.
        """
        self._sync_timeout = sync_timeout
        self._lock = threading.RLock()
        
        # Initialize channels
        self._channels: Dict[AlertChannel, INotificationChannel] = {}
        
        if email_config:
            self._channels[AlertChannel.EMAIL] = EmailChannel(email_config)
        
        if webhook_config:
            self._channels[AlertChannel.WEBHOOK] = WebhookChannel(webhook_config)
        
        self._channels[AlertChannel.SYSTEM_NOTIFICATION] = SystemNotificationChannel(
            callback=system_notification_callback
        )
        
        # Alert storage
        self._alerts: Dict[str, Alert] = {}
        self._pending_sync_alerts: Dict[str, threading.Event] = {}
        
        # Alert configurations
        self._alert_configs: Dict[str, AlertConfig] = {}
        self._load_default_configs()
        
        # Thread pool for async alerts
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Email recipients (configurable)
        self._email_recipients: List[str] = []
        
        # Webhook URLs (configurable)
        self._webhook_urls: List[str] = []
    
    def _load_default_configs(self) -> None:
        """Load default alert configurations."""
        default_configs = [
            AlertConfig(
                event_type=AlertEventType.RISK_TRIGGER.value,
                alert_type=AlertType.SYNC,
                channels=[AlertChannel.SYSTEM_NOTIFICATION, AlertChannel.EMAIL],
                severity=AlertSeverity.CRITICAL
            ),
            AlertConfig(
                event_type=AlertEventType.STRATEGY_ERROR.value,
                alert_type=AlertType.SYNC,
                channels=[AlertChannel.SYSTEM_NOTIFICATION],
                severity=AlertSeverity.ERROR
            ),
            AlertConfig(
                event_type=AlertEventType.BACKTEST_COMPLETE.value,
                alert_type=AlertType.ASYNC,
                channels=[AlertChannel.EMAIL],
                severity=AlertSeverity.INFO
            ),
            AlertConfig(
                event_type=AlertEventType.SYSTEM_ERROR.value,
                alert_type=AlertType.SYNC,
                channels=[AlertChannel.SYSTEM_NOTIFICATION, AlertChannel.EMAIL],
                severity=AlertSeverity.CRITICAL
            ),
            AlertConfig(
                event_type=AlertEventType.DATA_ERROR.value,
                alert_type=AlertType.ASYNC,
                channels=[AlertChannel.SYSTEM_NOTIFICATION],
                severity=AlertSeverity.WARNING
            ),
            AlertConfig(
                event_type=AlertEventType.DAILY_REPORT.value,
                alert_type=AlertType.ASYNC,
                channels=[AlertChannel.EMAIL],
                severity=AlertSeverity.INFO
            ),
        ]
        
        for config in default_configs:
            self._alert_configs[config.event_type] = config
    
    def set_email_recipients(self, recipients: List[str]) -> None:
        """Set email recipients for alerts."""
        self._email_recipients = recipients
    
    def set_webhook_urls(self, urls: List[str]) -> None:
        """Set webhook URLs for alerts."""
        self._webhook_urls = urls
    
    def add_channel(self, channel: INotificationChannel) -> None:
        """Add a notification channel."""
        self._channels[channel.get_channel_type()] = channel
    
    def _create_alert(
        self,
        alert_type: AlertType,
        title: str,
        message: str,
        severity: AlertSeverity,
        event_type: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Alert:
        """Create a new alert."""
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            event_type=event_type,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._alerts[alert.alert_id] = alert
        
        return alert
    
    def send_sync_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        event_type: str = AlertEventType.CUSTOM.value,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a synchronous alert that blocks until acknowledged.
        
        This method blocks the calling thread until the alert is acknowledged
        or the timeout is reached.
        
        Args:
            title: Alert title.
            message: Alert message.
            severity: Alert severity level.
            event_type: Type of event that triggered the alert.
            metadata: Optional additional metadata.
            
        Returns:
            True if acknowledged, False if timed out.
        """
        alert = self._create_alert(
            alert_type=AlertType.SYNC,
            title=title,
            message=message,
            severity=severity,
            event_type=event_type,
            metadata=metadata
        )
        
        # Create acknowledgment event
        ack_event = threading.Event()
        with self._lock:
            self._pending_sync_alerts[alert.alert_id] = ack_event
        
        # Send through configured channels
        config = self._alert_configs.get(event_type)
        channels = config.channels if config else [AlertChannel.SYSTEM_NOTIFICATION]
        
        self._send_to_channels(alert, channels)
        
        logger.info(f"Sync alert sent, waiting for acknowledgment: {alert.alert_id}")
        
        # Wait for acknowledgment
        acknowledged = ack_event.wait(timeout=self._sync_timeout)
        
        # Cleanup
        with self._lock:
            self._pending_sync_alerts.pop(alert.alert_id, None)
        
        if not acknowledged:
            logger.warning(f"Sync alert timed out: {alert.alert_id}")
        
        return acknowledged
    
    def send_async_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        channels: List[AlertChannel],
        event_type: str = AlertEventType.CUSTOM.value,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Send an asynchronous alert that doesn't block.
        
        The alert is sent in a background thread and this method returns
        immediately with the alert ID.
        
        Args:
            title: Alert title.
            message: Alert message.
            severity: Alert severity level.
            channels: List of channels to send through.
            event_type: Type of event that triggered the alert.
            metadata: Optional additional metadata.
            
        Returns:
            The alert ID.
        """
        alert = self._create_alert(
            alert_type=AlertType.ASYNC,
            title=title,
            message=message,
            severity=severity,
            event_type=event_type,
            metadata=metadata
        )
        
        # Send in background
        self._executor.submit(self._send_to_channels, alert, channels)
        
        logger.info(f"Async alert queued: {alert.alert_id}")
        return alert.alert_id
    
    def _send_to_channels(self, alert: Alert, channels: List[AlertChannel]) -> None:
        """Send alert to specified channels."""
        for channel_type in channels:
            channel = self._channels.get(channel_type)
            if not channel:
                logger.warning(f"Channel not configured: {channel_type}")
                continue
            
            try:
                recipients = self._get_recipients_for_channel(channel_type)
                channel.send(alert, recipients)
            except Exception as e:
                logger.error(f"Failed to send alert via {channel_type}: {e}")
    
    def _get_recipients_for_channel(self, channel_type: AlertChannel) -> List[str]:
        """Get recipients for a channel type."""
        if channel_type == AlertChannel.EMAIL:
            return self._email_recipients
        elif channel_type == AlertChannel.WEBHOOK:
            return self._webhook_urls
        else:
            return []
    
    def configure_event_alert(self, config: AlertConfig) -> bool:
        """
        Configure alert rules for an event type.
        
        Args:
            config: Alert configuration.
            
        Returns:
            True if configured successfully.
        """
        with self._lock:
            self._alert_configs[config.event_type] = config
        
        logger.info(f"Alert config updated for event: {config.event_type}")
        return True
    
    def get_event_config(self, event_type: str) -> Optional[AlertConfig]:
        """Get alert configuration for an event type."""
        return self._alert_configs.get(event_type)
    
    def acknowledge_alert(self, alert_id: str, user_id: str) -> bool:
        """
        Acknowledge a synchronous alert.
        
        Args:
            alert_id: ID of the alert to acknowledge.
            user_id: ID of the user acknowledging.
            
        Returns:
            True if acknowledged successfully.
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                logger.warning(f"Alert not found: {alert_id}")
                return False
            
            if alert.acknowledged:
                logger.info(f"Alert already acknowledged: {alert_id}")
                return True
            
            alert.acknowledge(user_id)
            
            # Signal waiting thread
            ack_event = self._pending_sync_alerts.get(alert_id)
            if ack_event:
                ack_event.set()
        
        logger.info(f"Alert acknowledged by {user_id}: {alert_id}")
        return True
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get an alert by ID."""
        return self._alerts.get(alert_id)
    
    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts."""
        return list(self._alerts.values())
    
    def get_unacknowledged_alerts(self) -> List[Alert]:
        """Get all unacknowledged sync alerts."""
        return [
            alert for alert in self._alerts.values()
            if alert.alert_type == AlertType.SYNC and not alert.acknowledged
        ]
    
    def send_event_alert(
        self,
        event_type: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Send an alert based on event type configuration.
        
        This method looks up the configuration for the event type and
        sends the appropriate type of alert (sync or async).
        
        Args:
            event_type: The event type.
            title: Alert title.
            message: Alert message.
            metadata: Optional additional metadata.
            
        Returns:
            Alert ID for async alerts, None for sync alerts.
        """
        config = self._alert_configs.get(event_type)
        if not config:
            logger.warning(f"No config for event type: {event_type}")
            return None
        
        if not config.enabled:
            logger.debug(f"Alert disabled for event type: {event_type}")
            return None
        
        # Apply templates if configured
        final_title = title
        final_message = message
        
        if config.template_title and metadata:
            try:
                final_title = config.template_title.format(**metadata)
            except KeyError:
                pass
        
        if config.template_message and metadata:
            try:
                final_message = config.template_message.format(**metadata)
            except KeyError:
                pass
        
        if config.alert_type == AlertType.SYNC:
            self.send_sync_alert(
                title=final_title,
                message=final_message,
                severity=config.severity,
                event_type=event_type,
                metadata=metadata
            )
            return None
        else:
            return self.send_async_alert(
                title=final_title,
                message=final_message,
                severity=config.severity,
                channels=config.channels,
                event_type=event_type,
                metadata=metadata
            )
    
    def shutdown(self) -> None:
        """Shutdown the alert system and cleanup resources."""
        self._executor.shutdown(wait=True)
        logger.info("Alert system shutdown complete")


# Convenience functions
_default_alert_system: Optional[AlertSystem] = None


def get_alert_system() -> AlertSystem:
    """Get the default alert system instance."""
    global _default_alert_system
    if _default_alert_system is None:
        _default_alert_system = AlertSystem()
    return _default_alert_system


def set_alert_system(system: AlertSystem) -> None:
    """Set the default alert system instance."""
    global _default_alert_system
    _default_alert_system = system


def send_sync_alert(
    title: str,
    message: str,
    severity: AlertSeverity = AlertSeverity.WARNING
) -> bool:
    """Send a synchronous alert using the default system."""
    return get_alert_system().send_sync_alert(title, message, severity)


def send_async_alert(
    title: str,
    message: str,
    severity: AlertSeverity = AlertSeverity.INFO,
    channels: Optional[List[AlertChannel]] = None
) -> str:
    """Send an asynchronous alert using the default system."""
    if channels is None:
        channels = [AlertChannel.SYSTEM_NOTIFICATION]
    return get_alert_system().send_async_alert(title, message, severity, channels)


__all__ = [
    # Enums
    "AlertType",
    "AlertChannel",
    "AlertSeverity",
    "AlertEventType",
    # Data classes
    "Alert",
    "AlertConfig",
    "EmailConfig",
    "WebhookConfig",
    # Interfaces
    "INotificationChannel",
    "IAlertSystem",
    # Channel implementations
    "EmailChannel",
    "WebhookChannel",
    "SystemNotificationChannel",
    # Main implementation
    "AlertSystem",
    # Convenience functions
    "get_alert_system",
    "set_alert_system",
    "send_sync_alert",
    "send_async_alert",
]
