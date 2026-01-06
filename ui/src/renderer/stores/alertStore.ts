/**
 * Titan-Quant Alert Store
 * 
 * Zustand store for managing alert state and notifications.
 * Supports both synchronous (blocking) and asynchronous alerts.
 * 
 * Requirements:
 * - 11.3: Distinguish between Sync_Alert and Async_Alert
 * - 11.4: UI_Client SHALL send Sync_Alert for strategy errors and risk triggers
 *         弹出原生系统通知并等待确认
 */

import { create } from 'zustand';
import { AlertPayload } from '../types/websocket';

/**
 * Alert severity levels
 */
export type AlertSeverity = 'info' | 'warning' | 'error' | 'critical';

/**
 * Alert type - sync blocks until acknowledged, async doesn't block
 */
export type AlertType = 'sync' | 'async';

/**
 * Notification urgency for native notifications
 */
type NotificationUrgency = 'low' | 'normal' | 'critical';

/**
 * Alert interface
 */
export interface Alert {
  alert_id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  title: string;
  message: string;
  timestamp: string;
  acknowledged: boolean;
  acknowledged_at?: string;
  acknowledged_by?: string;
}

/**
 * Alert store state interface
 */
interface AlertStore {
  // State
  alerts: Alert[];
  pendingSyncAlert: Alert | null;
  showSyncModal: boolean;
  
  // Actions
  addAlert: (alert: AlertPayload) => void;
  acknowledgeAlert: (alertId: string, userId?: string) => void;
  dismissAlert: (alertId: string) => void;
  clearAllAlerts: () => void;
  getUnacknowledgedAlerts: () => Alert[];
  getSyncAlerts: () => Alert[];
  getAsyncAlerts: () => Alert[];
  
  // Native notification
  showNativeNotification: (title: string, body: string, options?: {
    urgency?: NotificationUrgency;
    alertId?: string;
    alertType?: AlertType;
  }) => void;
  
  // Sync alert dialog (blocking)
  showSyncAlertDialog: (title: string, message: string, severity: AlertSeverity) => Promise<boolean>;
  
  // Window focus
  focusWindow: () => void;
  flashWindow: (flash: boolean) => void;
}

/**
 * Check if we're in Electron environment
 */
const isElectron = (): boolean => {
  return typeof window !== 'undefined' && 
         typeof window.process === 'object' && 
         (window.process as NodeJS.Process).type === 'renderer';
};

/**
 * Get Electron IPC renderer
 */
const getIpcRenderer = () => {
  if (isElectron()) {
    try {
      return window.require('electron').ipcRenderer;
    } catch (error) {
      console.warn('Failed to get ipcRenderer:', error);
      return null;
    }
  }
  return null;
};

/**
 * Map severity to notification urgency
 */
const severityToUrgency = (severity: AlertSeverity): NotificationUrgency => {
  switch (severity) {
    case 'critical':
      return 'critical';
    case 'error':
    case 'warning':
      return 'normal';
    default:
      return 'low';
  }
};

/**
 * Send native notification via Electron IPC
 */
const sendNativeNotification = (
  title: string, 
  body: string,
  options?: {
    urgency?: NotificationUrgency;
    alertId?: string;
    alertType?: AlertType;
  }
): void => {
  const ipcRenderer = getIpcRenderer();
  
  if (ipcRenderer) {
    ipcRenderer.send('show-notification', {
      title,
      body,
      urgency: options?.urgency || 'normal',
      silent: false,
      alertId: options?.alertId,
      alertType: options?.alertType,
    });
  } else {
    // Browser fallback using Notification API
    if ('Notification' in window) {
      if (Notification.permission === 'granted') {
        new Notification(title, { body });
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
          if (permission === 'granted') {
            new Notification(title, { body });
          }
        });
      }
    }
  }
};

/**
 * Show sync alert dialog (blocking) via Electron IPC
 */
const showSyncDialog = async (
  title: string,
  message: string,
  severity: AlertSeverity
): Promise<boolean> => {
  const ipcRenderer = getIpcRenderer();
  
  if (ipcRenderer) {
    try {
      const result = await ipcRenderer.invoke('show-sync-alert-dialog', {
        title,
        message,
        severity,
      });
      return result.acknowledged;
    } catch (error) {
      console.warn('Failed to show sync alert dialog:', error);
      return false;
    }
  }
  
  // Browser fallback - use window.confirm (blocking)
  return window.confirm(`${title}\n\n${message}`);
};

/**
 * Focus the main window
 */
const focusMainWindow = (): void => {
  const ipcRenderer = getIpcRenderer();
  if (ipcRenderer) {
    ipcRenderer.send('focus-window');
  }
};

/**
 * Flash the window frame
 */
const flashMainWindow = (flash: boolean): void => {
  const ipcRenderer = getIpcRenderer();
  if (ipcRenderer) {
    ipcRenderer.send('flash-frame', flash);
  }
};

/**
 * Alert store implementation
 */
export const useAlertStore = create<AlertStore>((set, get) => ({
  alerts: [],
  pendingSyncAlert: null,
  showSyncModal: false,

  addAlert: (alertPayload: AlertPayload) => {
    const alert: Alert = {
      alert_id: alertPayload.alert_id,
      alert_type: alertPayload.alert_type,
      severity: alertPayload.severity,
      title: alertPayload.title,
      message: alertPayload.message,
      timestamp: alertPayload.timestamp,
      acknowledged: false,
    };

    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 100), // Keep last 100 alerts
    }));

    // Handle sync alerts - show modal and native notification
    if (alert.alert_type === 'sync') {
      set({
        pendingSyncAlert: alert,
        showSyncModal: true,
      });
      
      // Focus window and flash for critical/error sync alerts
      if (alert.severity === 'critical' || alert.severity === 'error') {
        get().focusWindow();
        get().flashWindow(true);
      }
      
      // Show native notification for sync alerts
      get().showNativeNotification(alert.title, alert.message, {
        urgency: severityToUrgency(alert.severity),
        alertId: alert.alert_id,
        alertType: 'sync',
      });
    } else {
      // Async alerts - show native notification only
      get().showNativeNotification(alert.title, alert.message, {
        urgency: severityToUrgency(alert.severity),
        alertId: alert.alert_id,
        alertType: 'async',
      });
    }
  },

  acknowledgeAlert: (alertId: string, userId?: string) => {
    const now = new Date().toISOString();
    
    // Stop window flashing when alert is acknowledged
    get().flashWindow(false);
    
    set((state) => ({
      alerts: state.alerts.map((alert) =>
        alert.alert_id === alertId
          ? {
              ...alert,
              acknowledged: true,
              acknowledged_at: now,
              acknowledged_by: userId || 'user',
            }
          : alert
      ),
      // Close sync modal if this was the pending sync alert
      pendingSyncAlert:
        state.pendingSyncAlert?.alert_id === alertId
          ? null
          : state.pendingSyncAlert,
      showSyncModal:
        state.pendingSyncAlert?.alert_id === alertId
          ? false
          : state.showSyncModal,
    }));
  },

  dismissAlert: (alertId: string) => {
    set((state) => ({
      alerts: state.alerts.filter((alert) => alert.alert_id !== alertId),
    }));
  },

  clearAllAlerts: () => {
    set({ alerts: [] });
  },

  getUnacknowledgedAlerts: () => {
    return get().alerts.filter((alert) => !alert.acknowledged);
  },

  getSyncAlerts: () => {
    return get().alerts.filter((alert) => alert.alert_type === 'sync');
  },

  getAsyncAlerts: () => {
    return get().alerts.filter((alert) => alert.alert_type === 'async');
  },

  showNativeNotification: (title: string, body: string, options?: {
    urgency?: NotificationUrgency;
    alertId?: string;
    alertType?: AlertType;
  }) => {
    sendNativeNotification(title, body, options);
  },

  showSyncAlertDialog: async (title: string, message: string, severity: AlertSeverity) => {
    return showSyncDialog(title, message, severity);
  },

  focusWindow: () => {
    focusMainWindow();
  },

  flashWindow: (flash: boolean) => {
    flashMainWindow(flash);
  },
}));

// Set up IPC listener for notification clicks (when running in Electron)
if (typeof window !== 'undefined') {
  const ipcRenderer = getIpcRenderer();
  if (ipcRenderer) {
    ipcRenderer.on('notification-clicked', (_event: unknown, data: { alertId: string; alertType: string }) => {
      const store = useAlertStore.getState();
      // If it's a sync alert, make sure the modal is shown
      if (data.alertType === 'sync') {
        const alert = store.alerts.find(a => a.alert_id === data.alertId);
        if (alert && !alert.acknowledged) {
          useAlertStore.setState({
            pendingSyncAlert: alert,
            showSyncModal: true,
          });
        }
      }
    });
  }
}

export default useAlertStore;
