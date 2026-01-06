/**
 * Titan-Quant Alert Container
 * 
 * Container component that manages and displays all alerts.
 * Handles both sync modal alerts and async toast notifications.
 * 
 * Requirements:
 * - 11.3: THE Titan_Quant_System SHALL 区分两种告警类型
 * - 11.4: Sync_Alert 弹出原生系统通知并等待确认
 * - 11.5: Async_Alert 不阻塞流程，后台发送
 */

import React, { useEffect, useState } from 'react';
import { useAlertStore, Alert } from '../../stores/alertStore';
import { useIntegration } from '../../hooks/useIntegration';
import { getIntegrationService } from '../../services/integration';
import { MessageType } from '../../types/websocket';
import SyncAlertModal from './SyncAlertModal';
import AlertToast from './AlertToast';
import './AlertPopup.css';

interface AlertContainerProps {
  /** Maximum number of toasts to show */
  maxToasts?: number;
  /** Position of toast container */
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  /** Auto-dismiss timeout for async alerts (ms) */
  autoDismissTimeout?: number;
}

/**
 * Alert Container Component
 * 
 * Main container that:
 * 1. Listens for alert messages from WebSocket
 * 2. Displays sync alerts as modal dialogs
 * 3. Displays async alerts as toast notifications
 * 4. Sends acknowledgment back to server for sync alerts
 */
const AlertContainer: React.FC<AlertContainerProps> = ({
  maxToasts = 5,
  position = 'top-right',
  autoDismissTimeout = 5000,
}) => {
  const {
    alerts,
    pendingSyncAlert,
    showSyncModal,
    acknowledgeAlert,
  } = useAlertStore();

  const { acknowledgeAlert: sendAcknowledge } = useIntegration();

  // Track displayed async toasts
  const [displayedToasts, setDisplayedToasts] = useState<Alert[]>([]);

  // Update displayed toasts when alerts change
  useEffect(() => {
    const asyncAlerts = alerts
      .filter((alert) => alert.alert_type === 'async' && !alert.acknowledged)
      .slice(0, maxToasts);
    setDisplayedToasts(asyncAlerts);
  }, [alerts, maxToasts]);

  // Handle sync alert acknowledgment
  const handleSyncAcknowledge = async (alertId: string) => {
    acknowledgeAlert(alertId);

    // Send acknowledgment to server
    try {
      await sendAcknowledge(alertId);
    } catch (error) {
      console.error('Failed to send alert acknowledgment:', error);
    }
  };

  // Handle toast dismiss
  const handleToastDismiss = (alertId: string) => {
    acknowledgeAlert(alertId);
  };

  return (
    <>
      {/* Sync Alert Modal */}
      {pendingSyncAlert && (
        <SyncAlertModal
          visible={showSyncModal}
          alertId={pendingSyncAlert.alert_id}
          severity={pendingSyncAlert.severity}
          title={pendingSyncAlert.title}
          message={pendingSyncAlert.message}
          timestamp={pendingSyncAlert.timestamp}
          onAcknowledge={handleSyncAcknowledge}
        />
      )}

      {/* Async Alert Toasts */}
      <div className={`alert-toast-container ${position}`}>
        {displayedToasts.map((alert) => (
          <AlertToast
            key={alert.alert_id}
            alertId={alert.alert_id}
            severity={alert.severity}
            title={alert.title}
            message={alert.message}
            timestamp={alert.timestamp}
            onDismiss={handleToastDismiss}
            autoDismissTimeout={autoDismissTimeout}
          />
        ))}
      </div>
    </>
  );
};

export default AlertContainer;
