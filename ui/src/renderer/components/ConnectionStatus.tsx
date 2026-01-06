/**
 * Titan-Quant Connection Status Component
 * 
 * Displays the current WebSocket connection status
 * and provides reconnection controls.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { useConnectionStore, ConnectionState } from '../stores/connectionStore';

const ConnectionStatus: React.FC = () => {
  const { t } = useTranslation();
  const { connectionState, connect, disconnect } = useConnectionStore();

  const getStatusClass = (): string => {
    switch (connectionState) {
      case ConnectionState.CONNECTED:
        return 'connected';
      case ConnectionState.CONNECTING:
      case ConnectionState.RECONNECTING:
        return 'connecting';
      default:
        return '';
    }
  };

  const getStatusText = (): string => {
    switch (connectionState) {
      case ConnectionState.CONNECTED:
        return t('connection.connected');
      case ConnectionState.CONNECTING:
        return t('connection.connecting');
      case ConnectionState.RECONNECTING:
        return t('connection.reconnecting');
      case ConnectionState.DISCONNECTED:
        return t('connection.disconnected');
      case ConnectionState.ERROR:
        return t('connection.error');
      default:
        return t('connection.unknown');
    }
  };

  const handleClick = () => {
    if (connectionState === ConnectionState.CONNECTED) {
      disconnect();
    } else if (
      connectionState === ConnectionState.DISCONNECTED ||
      connectionState === ConnectionState.ERROR
    ) {
      connect();
    }
  };

  return (
    <div className="connection-status" onClick={handleClick} style={{ cursor: 'pointer' }}>
      <div className={`connection-indicator ${getStatusClass()}`} />
      <span>{getStatusText()}</span>
    </div>
  );
};

export default ConnectionStatus;
