/**
 * Titan-Quant Alert Popup Types
 * 
 * Type definitions for the alert popup component.
 */

import { AlertSeverity, AlertType } from '../../stores/alertStore';

/**
 * Alert popup props
 */
export interface AlertPopupProps {
  /** Whether the popup is visible */
  visible: boolean;
  /** Alert ID */
  alertId: string;
  /** Alert type (sync or async) */
  alertType: AlertType;
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
  /** Callback when popup is closed (for async alerts) */
  onClose?: (alertId: string) => void;
}

/**
 * Alert toast props for async notifications
 */
export interface AlertToastProps {
  /** Alert data */
  alert: {
    alert_id: string;
    alert_type: AlertType;
    severity: AlertSeverity;
    title: string;
    message: string;
    timestamp: string;
  };
  /** Callback when toast is dismissed */
  onDismiss: (alertId: string) => void;
  /** Auto-dismiss timeout in milliseconds (0 = no auto-dismiss) */
  autoDismissTimeout?: number;
}

/**
 * Alert container props
 */
export interface AlertContainerProps {
  /** Maximum number of toasts to show */
  maxToasts?: number;
  /** Position of toast container */
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
}

/**
 * Severity icon mapping
 */
export const SEVERITY_ICONS: Record<AlertSeverity, string> = {
  info: 'ℹ️',
  warning: '⚠️',
  error: '❌',
  critical: '🚨',
};

/**
 * Severity colors mapping
 */
export const SEVERITY_COLORS: Record<AlertSeverity, string> = {
  info: '#17a2b8',
  warning: '#ffc107',
  error: '#dc3545',
  critical: '#721c24',
};
