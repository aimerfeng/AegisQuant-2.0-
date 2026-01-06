/**
 * Titan-Quant Connection Store
 * 
 * Zustand store for managing WebSocket connection state.
 */

import { create } from 'zustand';
import { WebSocketService } from '../services/websocket';

export enum ConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECONNECTING = 'reconnecting',
  ERROR = 'error',
}

interface ConnectionStore {
  connectionState: ConnectionState;
  wsService: WebSocketService | null;
  lastError: string | null;
  reconnectAttempts: number;
  
  // Actions
  connect: (url?: string) => void;
  disconnect: () => void;
  setConnectionState: (state: ConnectionState) => void;
  setError: (error: string | null) => void;
  incrementReconnectAttempts: () => void;
  resetReconnectAttempts: () => void;
}

const DEFAULT_WS_URL = 'ws://localhost:8765';

export const useConnectionStore = create<ConnectionStore>((set, get) => ({
  connectionState: ConnectionState.DISCONNECTED,
  wsService: null,
  lastError: null,
  reconnectAttempts: 0,

  connect: (url: string = DEFAULT_WS_URL) => {
    const { wsService, connectionState } = get();
    
    // Don't connect if already connected or connecting
    if (connectionState === ConnectionState.CONNECTED || 
        connectionState === ConnectionState.CONNECTING) {
      return;
    }

    set({ connectionState: ConnectionState.CONNECTING });

    // Create new WebSocket service if needed
    let service = wsService;
    if (!service) {
      service = new WebSocketService(url, {
        onOpen: () => {
          set({ 
            connectionState: ConnectionState.CONNECTED,
            lastError: null,
          });
          get().resetReconnectAttempts();
        },
        onClose: () => {
          const currentState = get().connectionState;
          if (currentState !== ConnectionState.DISCONNECTED) {
            set({ connectionState: ConnectionState.DISCONNECTED });
          }
        },
        onError: (error) => {
          set({ 
            connectionState: ConnectionState.ERROR,
            lastError: error.message || 'Connection error',
          });
        },
        onReconnecting: () => {
          set({ connectionState: ConnectionState.RECONNECTING });
          get().incrementReconnectAttempts();
        },
      });
      set({ wsService: service });
    }

    service.connect();
  },

  disconnect: () => {
    const { wsService } = get();
    if (wsService) {
      wsService.disconnect();
    }
    set({ connectionState: ConnectionState.DISCONNECTED });
  },

  setConnectionState: (state: ConnectionState) => {
    set({ connectionState: state });
  },

  setError: (error: string | null) => {
    set({ lastError: error });
  },

  incrementReconnectAttempts: () => {
    set((state) => ({ reconnectAttempts: state.reconnectAttempts + 1 }));
  },

  resetReconnectAttempts: () => {
    set({ reconnectAttempts: 0 });
  },
}));
