/**
 * Titan-Quant Integration Hook
 * 
 * React hook for accessing the integration service and its methods.
 * Provides a convenient way to interact with the backend from React components.
 * 
 * Requirements:
 * - 1.1: Core_Engine SHALL communicate with UI_Client via WebSocket
 * - 1.4: WHEN UI_Client reconnects, Core_Engine SHALL restore state sync
 */

import { useCallback, useEffect, useRef } from 'react';
import { getIntegrationService, IntegrationService } from '../services/integration';
import { useConnectionStore, ConnectionState } from '../stores/connectionStore';
import { StartBacktestPayload, ManualOrderPayload } from '../types/websocket';

/**
 * Integration hook return type
 */
export interface UseIntegrationReturn {
  // Connection state
  isConnected: boolean;
  connectionState: ConnectionState;
  lastError: string | null;
  reconnectAttempts: number;

  // Connection methods
  connect: () => void;
  disconnect: () => void;

  // Backtest control
  startBacktest: (config: StartBacktestPayload) => Promise<void>;
  pause: () => Promise<void>;
  resume: () => Promise<void>;
  step: () => Promise<void>;
  stop: () => Promise<void>;

  // Strategy methods
  loadStrategy: (filePath: string) => Promise<void>;
  reloadStrategy: (
    strategyId: string,
    policy: 'reset' | 'preserve' | 'selective',
    preserveVars?: string[]
  ) => Promise<void>;
  updateParams: (strategyId: string, params: Record<string, unknown>) => Promise<void>;

  // Manual trading
  submitManualOrder: (order: ManualOrderPayload) => Promise<void>;
  cancelOrder: (orderId: string) => Promise<void>;
  closeAllPositions: () => Promise<void>;

  // Snapshot methods
  saveSnapshot: (description?: string) => Promise<void>;
  loadSnapshot: (path: string) => Promise<void>;

  // Alert methods
  acknowledgeAlert: (alertId: string) => Promise<void>;

  // State sync
  requestState: () => Promise<void>;
}

/**
 * Hook for accessing the integration service
 */
export function useIntegration(): UseIntegrationReturn {
  const serviceRef = useRef<IntegrationService | null>(null);
  
  const {
    connectionState,
    lastError,
    reconnectAttempts,
  } = useConnectionStore();

  // Initialize service on first use
  useEffect(() => {
    if (!serviceRef.current) {
      serviceRef.current = getIntegrationService();
    }
  }, []);

  const getService = useCallback((): IntegrationService => {
    if (!serviceRef.current) {
      serviceRef.current = getIntegrationService();
    }
    return serviceRef.current;
  }, []);

  // Connection methods
  const connect = useCallback(() => {
    getService().connect();
  }, [getService]);

  const disconnect = useCallback(() => {
    getService().disconnect();
  }, [getService]);

  // Backtest control
  const startBacktest = useCallback(async (config: StartBacktestPayload) => {
    const response = await getService().startBacktest(config);
    if (!response.success) {
      throw new Error(response.error || 'Failed to start backtest');
    }
  }, [getService]);

  const pause = useCallback(async () => {
    const response = await getService().pause();
    if (!response.success) {
      throw new Error(response.error || 'Failed to pause');
    }
  }, [getService]);

  const resume = useCallback(async () => {
    const response = await getService().resume();
    if (!response.success) {
      throw new Error(response.error || 'Failed to resume');
    }
  }, [getService]);

  const step = useCallback(async () => {
    const response = await getService().step();
    if (!response.success) {
      throw new Error(response.error || 'Failed to step');
    }
  }, [getService]);

  const stop = useCallback(async () => {
    const response = await getService().stop();
    if (!response.success) {
      throw new Error(response.error || 'Failed to stop');
    }
  }, [getService]);

  // Strategy methods
  const loadStrategy = useCallback(async (filePath: string) => {
    const response = await getService().loadStrategy(filePath);
    if (!response.success) {
      throw new Error(response.error || 'Failed to load strategy');
    }
  }, [getService]);

  const reloadStrategy = useCallback(async (
    strategyId: string,
    policy: 'reset' | 'preserve' | 'selective',
    preserveVars?: string[]
  ) => {
    const response = await getService().reloadStrategy(strategyId, policy, preserveVars);
    if (!response.success) {
      throw new Error(response.error || 'Failed to reload strategy');
    }
  }, [getService]);

  const updateParams = useCallback(async (
    strategyId: string,
    params: Record<string, unknown>
  ) => {
    const response = await getService().updateParams(strategyId, params);
    if (!response.success) {
      throw new Error(response.error || 'Failed to update params');
    }
  }, [getService]);

  // Manual trading
  const submitManualOrder = useCallback(async (order: ManualOrderPayload) => {
    const response = await getService().submitManualOrder(order);
    if (!response.success) {
      throw new Error(response.error || 'Failed to submit order');
    }
  }, [getService]);

  const cancelOrder = useCallback(async (orderId: string) => {
    const response = await getService().cancelOrder(orderId);
    if (!response.success) {
      throw new Error(response.error || 'Failed to cancel order');
    }
  }, [getService]);

  const closeAllPositions = useCallback(async () => {
    const response = await getService().closeAllPositions();
    if (!response.success) {
      throw new Error(response.error || 'Failed to close all positions');
    }
  }, [getService]);

  // Snapshot methods
  const saveSnapshot = useCallback(async (description?: string) => {
    const response = await getService().saveSnapshot(description);
    if (!response.success) {
      throw new Error(response.error || 'Failed to save snapshot');
    }
  }, [getService]);

  const loadSnapshot = useCallback(async (path: string) => {
    const response = await getService().loadSnapshot(path);
    if (!response.success) {
      throw new Error(response.error || 'Failed to load snapshot');
    }
  }, [getService]);

  // Alert methods
  const acknowledgeAlert = useCallback(async (alertId: string) => {
    const response = await getService().acknowledgeAlert(alertId);
    if (!response.success) {
      throw new Error(response.error || 'Failed to acknowledge alert');
    }
  }, [getService]);

  // State sync
  const requestState = useCallback(async () => {
    const response = await getService().requestState();
    if (!response.success) {
      throw new Error(response.error || 'Failed to request state');
    }
  }, [getService]);

  return {
    // Connection state
    isConnected: connectionState === ConnectionState.CONNECTED,
    connectionState,
    lastError,
    reconnectAttempts,

    // Connection methods
    connect,
    disconnect,

    // Backtest control
    startBacktest,
    pause,
    resume,
    step,
    stop,

    // Strategy methods
    loadStrategy,
    reloadStrategy,
    updateParams,

    // Manual trading
    submitManualOrder,
    cancelOrder,
    closeAllPositions,

    // Snapshot methods
    saveSnapshot,
    loadSnapshot,

    // Alert methods
    acknowledgeAlert,

    // State sync
    requestState,
  };
}

export default useIntegration;
