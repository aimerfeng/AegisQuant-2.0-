/**
 * Titan-Quant Alert Toast
 * 
 * Toast notification component for asynchronous alerts.
 * Auto-dismisses after a configurable timeout.
 * 
 * Requirements:
 * - 11.5: WHEN 回测完成或定时报告, THEN THE Titan_Quant_System SHALL 发送 Async_Alert
 */

import React, { useEffect, useState, useCallback } from 'react';
import { AlertSeverity } from '../../stores/alertStore';
import { SEVERITY_ICONS } from './types';
import './AlertPopup.css';

interface AlertToastProps {
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
  /** Callback when toast is dismissed */
  onDismiss: (alertId: string) => void;
  /** Auto-dismiss timeout in milliseconds (0 = no auto-dismiss) */
  autoDismissTimeout?: number;
}

/**
 * Format timestamp for display
 */
const formatTimestamp = (timestamp: string): string => {
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    // Show relative time for recent alerts
    if (diff < 60000) {
      return 'Just now';
    } else if (diff < 3600000) {
      const minutes = Math.floor(diff / 60000);
      return `${minutes}m ago`;
    } else if (diff < 86400000) {
      const hours = Math.floor(diff / 3600000);
      return `${hours}h ago`;
    }
    
    return date.toLocaleTimeString();
  } catch {
    return timestamp;
  }
};

/**
 * Alert Toast Component
 * 
 * Displays a toast notification for asynchronous alerts.
 * Supports auto-dismiss with a progress bar indicator.
 */
const AlertToast: React.FC<AlertToastProps> = ({
  alertId,
  severity,
  title,
  message,
  timestamp,
  onDismiss,
  autoDismissTimeout = 5000,
}) => {
  const [isExiting, setIsExiting] = useState(false);

  // Handle dismiss with exit animation
  const handleDismiss = useCallback(() => {
    setIsExiting(true);
    // Wait for animation to complete before calling onDismiss
    setTimeout(() => {
      onDismiss(alertId);
    }, 300);
  }, [alertId, onDismiss]);

  // Auto-dismiss timer
  useEffect(() => {
    if (autoDismissTimeout > 0) {
      const timer = setTimeout(() => {
        handleDismiss();
      }, autoDismissTimeout);

      return () => clearTimeout(timer);
    }
  }, [autoDismissTimeout, handleDismiss]);

  const icon = SEVERITY_ICONS[severity];

  return (
    <div
      className={`alert-toast ${isExiting ? 'exiting' : ''}`}
      role="alert"
      aria-live="polite"
    >
      <div className={`alert-toast-header severity-${severity}`}>
        <span className="alert-toast-icon" role="img" aria-label={severity}>
          {icon}
        </span>
        <h3 className="alert-toast-title">{title}</h3>
        <button
          className="alert-toast-close"
          onClick={handleDismiss}
          aria-label="Dismiss notification"
        >
          ✕
        </button>
      </div>

      <div className="alert-toast-body">
        <p className="alert-toast-message">{message}</p>
        <div className="alert-toast-timestamp">{formatTimestamp(timestamp)}</div>
      </div>

      {autoDismissTimeout > 0 && (
        <div className="alert-toast-progress">
          <div
            className="alert-toast-progress-bar"
            style={{ animationDuration: `${autoDismissTimeout}ms` }}
          />
        </div>
      )}
    </div>
  );
};

export default AlertToast;
