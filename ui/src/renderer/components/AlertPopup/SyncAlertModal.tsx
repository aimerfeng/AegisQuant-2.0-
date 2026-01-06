/**
 * Titan-Quant Sync Alert Modal
 * 
 * Modal component for synchronous alerts that block until acknowledged.
 * Used for critical alerts like risk triggers and strategy errors.
 * 
 * Requirements:
 * - 11.4: WHEN 策略报错或触发风控, THEN THE UI_Client SHALL 发送 Sync_Alert，
 *         弹出原生系统通知并等待确认
 */

import React, { useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertSeverity } from '../../stores/alertStore';
import { SEVERITY_ICONS } from './types';
import './AlertPopup.css';

interface SyncAlertModalProps {
  /** Whether the modal is visible */
  visible: boolean;
  /** Alert ID */
  alertId: string;
  /** Alert severity level */
  severity: AlertSeverity;
  /** Alert title */
  title: string;
  /** Alert message */
  message: string;
  /** Alert timestamp */
  timestamp: string;
  /** Callback when alert is acknowledged */
  onAcknowledge: (alertId: string) => void;
}

/**
 * Format timestamp for display
 */
const formatTimestamp = (timestamp: string): string => {
  try {
    const date = new Date(timestamp);
    return date.toLocaleString();
  } catch {
    return timestamp;
  }
};

/**
 * Sync Alert Modal Component
 * 
 * Displays a modal dialog for synchronous alerts that require user acknowledgment.
 * The modal blocks interaction with the rest of the application until acknowledged.
 */
const SyncAlertModal: React.FC<SyncAlertModalProps> = ({
  visible,
  alertId,
  severity,
  title,
  message,
  timestamp,
  onAcknowledge,
}) => {
  const { t } = useTranslation();

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === 'Escape') {
        onAcknowledge(alertId);
      }
    },
    [alertId, onAcknowledge]
  );

  // Add keyboard listener when modal is visible
  useEffect(() => {
    if (visible) {
      document.addEventListener('keydown', handleKeyDown);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [visible, handleKeyDown]);

  if (!visible) {
    return null;
  }

  const icon = SEVERITY_ICONS[severity];

  return (
    <div
      className="alert-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="alert-modal-title"
      aria-describedby="alert-modal-message"
    >
      <div className="alert-modal">
        <div className={`alert-modal-header severity-${severity}`}>
          <span className="alert-modal-icon" role="img" aria-label={severity}>
            {icon}
          </span>
          <h2 id="alert-modal-title" className="alert-modal-title">
            {title}
          </h2>
        </div>

        <div className="alert-modal-body">
          <p id="alert-modal-message" className="alert-modal-message">
            {message}
          </p>
          <div className="alert-modal-timestamp">
            <span>🕐</span>
            <span>{formatTimestamp(timestamp)}</span>
          </div>
        </div>

        <div className="alert-modal-footer">
          <button
            className="alert-modal-button primary"
            onClick={() => onAcknowledge(alertId)}
            autoFocus
          >
            {t('ui.acknowledge', 'Acknowledge')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SyncAlertModal;
