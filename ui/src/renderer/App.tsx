/**
 * Titan-Quant Main Application Component
 * 
 * Root component that sets up the application layout,
 * WebSocket connection, and global state management.
 * 
 * Requirements:
 * - 1.1: Core_Engine SHALL communicate with UI_Client via WebSocket
 * - 1.4: WHEN UI_Client reconnects, Core_Engine SHALL restore state sync
 * - 11.4: UI_Client SHALL display sync alerts as modal dialogs
 */

import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useI18nStore } from './stores/i18nStore';
import { initIntegrationService } from './services/integration';
import { useIntegration } from './hooks/useIntegration';
import MainLayout from './components/MainLayout';
import ConnectionStatus from './components/ConnectionStatus';
import { AlertContainer } from './components/AlertPopup';
import './styles/App.css';

const App: React.FC = () => {
  const { t } = useTranslation();
  const { currentLanguage } = useI18nStore();
  const { connect, isConnected } = useIntegration();

  useEffect(() => {
    // Initialize integration service and connect on app start
    initIntegrationService({
      wsUrl: 'ws://localhost:8765',
      autoConnect: false,
      onConnected: () => {
        console.log('[App] Connected to backend server');
      },
      onDisconnected: () => {
        console.log('[App] Disconnected from backend server');
      },
      onError: (error) => {
        console.error('[App] Connection error:', error);
      },
    });
    
    // Connect to the server
    connect();
  }, [connect]);

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="app-title">
          <h1>Titan-Quant</h1>
          <span className="app-subtitle">{t('app.subtitle')}</span>
        </div>
        <div className="app-status">
          <ConnectionStatus />
        </div>
      </header>
      <main className="app-main">
        <MainLayout />
      </main>
      <footer className="app-footer">
        <span>{t('app.version', { version: '1.0.0' })}</span>
        <span className="language-indicator">{currentLanguage.toUpperCase()}</span>
      </footer>
      
      {/* Alert Container for sync/async notifications */}
      <AlertContainer 
        maxToasts={5}
        position="top-right"
        autoDismissTimeout={5000}
      />
    </div>
  );
};

export default App;
