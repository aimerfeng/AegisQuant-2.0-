"""
Property-Based Tests for Alert System

This module contains property-based tests using Hypothesis to verify
the correctness properties of the AlertSystem implementation.

Properties tested:
    - Property 18: Alert Type Classification

Validates: Requirements 11.3
"""
import threading
import time
from datetime import datetime
from typing import Any, Dict, List

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck

from utils.notifier import (
    AlertType,
    AlertChannel,
    AlertSeverity,
    AlertEventType,
    Alert,
    AlertConfig,
    AlertSystem,
    SystemNotificationChannel,
    get_alert_system,
    set_alert_system,
)


# Custom strategies for generating test data
@st.composite
def alert_config_strategy(draw):
    """Generate valid alert configurations for testing."""
    event_type = draw(st.sampled_from([e.value for e in AlertEventType]))
    alert_type = draw(st.sampled_from([AlertType.SYNC, AlertType.ASYNC]))
    channels = draw(st.lists(
        st.sampled_from([AlertChannel.SYSTEM_NOTIFICATION, AlertChannel.EMAIL, AlertChannel.WEBHOOK]),
        min_size=1,
        max_size=3,
        unique=True
    ))
    severity = draw(st.sampled_from([s for s in AlertSeverity]))
    enabled = draw(st.booleans())
    
    return AlertConfig(
        event_type=event_type,
        alert_type=alert_type,
        channels=channels,
        severity=severity,
        enabled=enabled
    )


@st.composite
def alert_message_strategy(draw):
    """Generate valid alert messages for testing."""
    title = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'Z'),
        whitelist_characters=' _-!?.'
    )))
    message = draw(st.text(min_size=1, max_size=500, alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'Z'),
        whitelist_characters=' _-!?.\n'
    )))
    severity = draw(st.sampled_from([s for s in AlertSeverity]))
    event_type = draw(st.sampled_from([e.value for e in AlertEventType]))
    
    return {
        "title": title,
        "message": message,
        "severity": severity,
        "event_type": event_type,
    }


class TestAlertTypeClassification:
    """
    Property 18: Alert Type Classification
    
    *For any* alert event, the alert must be correctly classified as
    Sync_Alert (blocking) or Async_Alert (non-blocking) based on the
    configured alert rules.
    
    **Validates: Requirements 11.3**
    """
    
    @pytest.fixture(autouse=True)
    def setup_alert_system(self):
        """Create a fresh alert system for each test."""
        self.system = AlertSystem(sync_timeout=1)
        yield
        self.system.shutdown()
    
    @given(config=alert_config_strategy())
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_alert_type_matches_config(self, config: AlertConfig) -> None:
        """
        Property: For any alert configuration, alerts sent for that event type
        must have the alert_type matching the configuration.
        
        Feature: titan-quant, Property 18: Alert Type Classification
        """
        # Configure the event
        self.system.configure_event_alert(config)
        
        # Skip if disabled
        if not config.enabled:
            return
        
        # For sync alerts, we need to auto-acknowledge to avoid blocking
        if config.alert_type == AlertType.SYNC:
            def auto_ack():
                time.sleep(0.1)
                alerts = self.system.get_unacknowledged_alerts()
                for alert in alerts:
                    self.system.acknowledge_alert(alert.alert_id, "test_user")
            
            ack_thread = threading.Thread(target=auto_ack)
            ack_thread.start()
            
            self.system.send_event_alert(
                event_type=config.event_type,
                title="Test Alert",
                message="Test message"
            )
            
            ack_thread.join(timeout=2)
            
            # Verify the alert was created with correct type
            alerts = self.system.get_all_alerts()
            matching_alerts = [a for a in alerts if a.event_type == config.event_type]
            
            if matching_alerts:
                assert matching_alerts[-1].alert_type == AlertType.SYNC
        else:
            # Async alert
            alert_id = self.system.send_event_alert(
                event_type=config.event_type,
                title="Test Alert",
                message="Test message"
            )
            
            if alert_id:
                alert = self.system.get_alert(alert_id)
                assert alert is not None
                assert alert.alert_type == AlertType.ASYNC
    
    @given(
        alert_type=st.sampled_from([AlertType.SYNC, AlertType.ASYNC]),
        severity=st.sampled_from([s for s in AlertSeverity])
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_direct_alert_type_preserved(
        self,
        alert_type: AlertType,
        severity: AlertSeverity
    ) -> None:
        """
        Property: For any directly sent alert (sync or async), the alert_type
        must be preserved in the created alert object.
        
        Feature: titan-quant, Property 18: Alert Type Classification
        """
        if alert_type == AlertType.SYNC:
            # Auto-acknowledge sync alerts
            def auto_ack():
                time.sleep(0.1)
                alerts = self.system.get_unacknowledged_alerts()
                for alert in alerts:
                    self.system.acknowledge_alert(alert.alert_id, "test_user")
            
            ack_thread = threading.Thread(target=auto_ack)
            ack_thread.start()
            
            self.system.send_sync_alert(
                title="Test Sync",
                message="Test sync message",
                severity=severity
            )
            
            ack_thread.join(timeout=2)
            
            # Find the sync alert
            alerts = self.system.get_all_alerts()
            sync_alerts = [a for a in alerts if a.alert_type == AlertType.SYNC]
            assert len(sync_alerts) > 0
            assert sync_alerts[-1].alert_type == AlertType.SYNC
        else:
            alert_id = self.system.send_async_alert(
                title="Test Async",
                message="Test async message",
                severity=severity,
                channels=[AlertChannel.SYSTEM_NOTIFICATION]
            )
            
            alert = self.system.get_alert(alert_id)
            assert alert is not None
            assert alert.alert_type == AlertType.ASYNC
    
    def test_sync_alert_blocks_until_acknowledged(self) -> None:
        """
        Property: Sync alerts must block the calling thread until acknowledged.
        
        Feature: titan-quant, Property 18: Alert Type Classification
        """
        start_time = time.time()
        acknowledged = False
        
        def delayed_ack():
            nonlocal acknowledged
            time.sleep(0.3)
            alerts = self.system.get_unacknowledged_alerts()
            if alerts:
                self.system.acknowledge_alert(alerts[0].alert_id, "test_user")
                acknowledged = True
        
        ack_thread = threading.Thread(target=delayed_ack)
        ack_thread.start()
        
        result = self.system.send_sync_alert(
            title="Blocking Test",
            message="This should block",
            severity=AlertSeverity.WARNING
        )
        
        elapsed = time.time() - start_time
        ack_thread.join()
        
        # Should have blocked for at least 0.2 seconds
        assert elapsed >= 0.2
        assert result is True
        assert acknowledged is True
    
    def test_async_alert_does_not_block(self) -> None:
        """
        Property: Async alerts must not block the calling thread.
        
        Feature: titan-quant, Property 18: Alert Type Classification
        """
        start_time = time.time()
        
        alert_id = self.system.send_async_alert(
            title="Non-blocking Test",
            message="This should not block",
            severity=AlertSeverity.INFO,
            channels=[AlertChannel.SYSTEM_NOTIFICATION]
        )
        
        elapsed = time.time() - start_time
        
        # Should return almost immediately (less than 0.1 seconds)
        assert elapsed < 0.1
        assert alert_id is not None
        
        alert = self.system.get_alert(alert_id)
        assert alert is not None
        assert alert.alert_type == AlertType.ASYNC


class TestAlertDataIntegrity:
    """Unit tests for Alert data class integrity."""
    
    def test_alert_to_dict_and_back(self) -> None:
        """Test that alerts can be serialized and deserialized."""
        alert = Alert(
            alert_id="test-123",
            alert_type=AlertType.SYNC,
            severity=AlertSeverity.CRITICAL,
            title="Test Alert",
            message="Test message content",
            event_type=AlertEventType.RISK_TRIGGER.value,
            metadata={"key": "value", "number": 42}
        )
        
        alert_dict = alert.to_dict()
        restored = Alert.from_dict(alert_dict)
        
        assert restored.alert_id == alert.alert_id
        assert restored.alert_type == alert.alert_type
        assert restored.severity == alert.severity
        assert restored.title == alert.title
        assert restored.message == alert.message
        assert restored.event_type == alert.event_type
        assert restored.metadata == alert.metadata
    
    def test_alert_acknowledge(self) -> None:
        """Test alert acknowledgment."""
        alert = Alert(
            alert_id="test-456",
            alert_type=AlertType.SYNC,
            severity=AlertSeverity.WARNING,
            title="Ack Test",
            message="Test acknowledgment"
        )
        
        assert alert.acknowledged is False
        assert alert.acknowledged_at is None
        assert alert.acknowledged_by is None
        
        alert.acknowledge("user123")
        
        assert alert.acknowledged is True
        assert alert.acknowledged_at is not None
        assert alert.acknowledged_by == "user123"


class TestAlertConfigIntegrity:
    """Unit tests for AlertConfig data class integrity."""
    
    def test_config_to_dict_and_back(self) -> None:
        """Test that configs can be serialized and deserialized."""
        config = AlertConfig(
            event_type=AlertEventType.RISK_TRIGGER.value,
            alert_type=AlertType.SYNC,
            channels=[AlertChannel.EMAIL, AlertChannel.SYSTEM_NOTIFICATION],
            severity=AlertSeverity.CRITICAL,
            enabled=True,
            template_title="Risk Alert: {reason}",
            template_message="Risk triggered at {time}"
        )
        
        config_dict = config.to_dict()
        restored = AlertConfig.from_dict(config_dict)
        
        assert restored.event_type == config.event_type
        assert restored.alert_type == config.alert_type
        assert restored.channels == config.channels
        assert restored.severity == config.severity
        assert restored.enabled == config.enabled
        assert restored.template_title == config.template_title
        assert restored.template_message == config.template_message


class TestAlertSystemConfiguration:
    """Unit tests for AlertSystem configuration."""
    
    @pytest.fixture(autouse=True)
    def setup_alert_system(self):
        """Create a fresh alert system for each test."""
        self.system = AlertSystem(sync_timeout=1)
        yield
        self.system.shutdown()
    
    def test_configure_event_alert(self) -> None:
        """Test configuring alert rules for events."""
        config = AlertConfig(
            event_type="custom_event",
            alert_type=AlertType.ASYNC,
            channels=[AlertChannel.WEBHOOK],
            severity=AlertSeverity.INFO
        )
        
        result = self.system.configure_event_alert(config)
        assert result is True
        
        retrieved = self.system.get_event_config("custom_event")
        assert retrieved is not None
        assert retrieved.event_type == "custom_event"
        assert retrieved.alert_type == AlertType.ASYNC
    
    def test_default_configs_loaded(self) -> None:
        """Test that default configurations are loaded."""
        # Risk trigger should be configured by default
        config = self.system.get_event_config(AlertEventType.RISK_TRIGGER.value)
        assert config is not None
        assert config.alert_type == AlertType.SYNC
        assert config.severity == AlertSeverity.CRITICAL
        
        # Backtest complete should be async
        config = self.system.get_event_config(AlertEventType.BACKTEST_COMPLETE.value)
        assert config is not None
        assert config.alert_type == AlertType.ASYNC
        assert config.severity == AlertSeverity.INFO
    
    def test_get_unacknowledged_alerts(self) -> None:
        """Test retrieving unacknowledged sync alerts."""
        # Send an async alert (should not appear in unacknowledged)
        self.system.send_async_alert(
            title="Async",
            message="Async message",
            severity=AlertSeverity.INFO,
            channels=[AlertChannel.SYSTEM_NOTIFICATION]
        )
        
        # Initially no unacknowledged sync alerts
        unacked = self.system.get_unacknowledged_alerts()
        assert len(unacked) == 0
