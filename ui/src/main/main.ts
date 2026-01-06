/**
 * Titan-Quant Electron Main Process
 * 
 * This is the main entry point for the Electron application.
 * It creates the browser window and handles system-level events.
 * 
 * Requirements:
 * - 11.4: WHEN 策略报错或触发风控, THEN THE UI_Client SHALL 发送 Sync_Alert，
 *         弹出原生系统通知并等待确认
 */

import { app, BrowserWindow, ipcMain, Notification, dialog } from 'electron';
import * as path from 'path';

let mainWindow: BrowserWindow | null = null;

const isDev = process.env.NODE_ENV === 'development';

/**
 * Notification urgency levels mapped to system notification settings
 */
type NotificationUrgency = 'low' | 'normal' | 'critical';

interface NotificationOptions {
  title: string;
  body: string;
  urgency?: NotificationUrgency;
  silent?: boolean;
  alertId?: string;
  alertType?: 'sync' | 'async';
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: 'Titan-Quant',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: !isDev,
    },
    show: false,
    backgroundColor: '#1e1e1e',
  });

  // Load the app
  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle events
app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC handlers for renderer process communication
ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-platform', () => {
  return process.platform;
});

/**
 * Handle system notifications
 * Supports both async (toast) and sync (blocking) notifications
 * 
 * Requirements:
 * - 11.4: Sync alerts should show native notification and bring window to focus
 */
ipcMain.on('show-notification', (event, options: NotificationOptions) => {
  const { title, body, urgency = 'normal', silent = false, alertId, alertType } = options;
  
  if (Notification.isSupported()) {
    const notification = new Notification({
      title,
      body,
      silent,
      urgency,
      // Use app icon for notifications
      icon: isDev ? undefined : path.join(__dirname, '../assets/icon.png'),
    });

    // When notification is clicked, focus the main window
    notification.on('click', () => {
      if (mainWindow) {
        if (mainWindow.isMinimized()) {
          mainWindow.restore();
        }
        mainWindow.focus();
        
        // Send message to renderer to handle the alert
        if (alertId) {
          mainWindow.webContents.send('notification-clicked', { alertId, alertType });
        }
      }
    });

    notification.show();
  }
});

/**
 * Handle sync alert dialog
 * Shows a native dialog that blocks until user acknowledges
 * 
 * Requirements:
 * - 11.4: Sync_Alert blocks until user confirms
 */
ipcMain.handle('show-sync-alert-dialog', async (event, options: {
  title: string;
  message: string;
  severity: string;
}) => {
  const { title, message, severity } = options;
  
  // Map severity to dialog type
  let type: 'none' | 'info' | 'error' | 'question' | 'warning' = 'info';
  switch (severity) {
    case 'critical':
    case 'error':
      type = 'error';
      break;
    case 'warning':
      type = 'warning';
      break;
    default:
      type = 'info';
  }

  // Bring window to front for critical alerts
  if (mainWindow && (severity === 'critical' || severity === 'error')) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
    // Flash the window to get user attention
    mainWindow.flashFrame(true);
  }

  // Show blocking dialog
  const result = await dialog.showMessageBox(mainWindow!, {
    type,
    title: `Titan-Quant - ${title}`,
    message: title,
    detail: message,
    buttons: ['Acknowledge'],
    defaultId: 0,
    noLink: true,
  });

  // Stop flashing after acknowledgment
  if (mainWindow) {
    mainWindow.flashFrame(false);
  }

  return { acknowledged: true, buttonIndex: result.response };
});

/**
 * Flash the taskbar/dock icon to get user attention
 */
ipcMain.on('flash-frame', (event, flash: boolean) => {
  if (mainWindow) {
    mainWindow.flashFrame(flash);
  }
});

/**
 * Bring window to front
 */
ipcMain.on('focus-window', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
  }
});
