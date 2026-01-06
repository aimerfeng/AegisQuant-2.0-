/**
 * Titan-Quant Main Application Component
 * 
 * Root component that sets up the application layout,
 * WebSocket connection, and global state management.
 */

import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useConnectionStore } from './stores/connectionStore';
import { useI18nStore } from './stores/i18nStore';
import MainLayout from './components/MainLayout';
import ConnectionStatus from './components/ConnectionStatus';
import './styles/App.css';

const App: React.FC = () => {
  const { t } = useTranslation();
  const { connect, isConnected } = useConnectionStore();
  const { currentLanguage } = useI18nStore();

  useEffect(() => {
    // Initialize WebSocket connection on app start
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
    </div>
  );
};

export default App;
