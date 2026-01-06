/**
 * Titan-Quant Frontend-Backend Integration Service
 * 
 * This service provides the complete communication flow between the frontend
 * and backend, including:
 * - WebSocket connection management
 * - Message sending and receiving
 * - State synchronization
 * - Store updates based on server messages
 * 
 * Requirements:
 * - 1.1: Core_Engine SHALL communicate with UI_Client via WebSocket
 * - 1.3: WHEN UI_Client crashes, Core_Engine SHALL continue execution
 * - 1.4: WHEN UI_Client reconnects, Core_Engine SHALL restore state sync
 */

import { WebSocketService, WebSocketCallbacks } from './websocket';
import {
  MessageType,
  Message,
  TickUpdatePayload,
  BarUpdatePayload,
  PositionUpdatePayload,
  AccountUpdatePayload,
  TradeUpdatePayload,
  AlertPayload,
  StartBacktestPayload,
  ManualOrderPayload,
} from '../types/websocket';
import { useConnectionStore, ConnectionState } from '../stores/connectionStore';
import { useBacktestStore, BacktestStatus } from '../stores/backtestStore';
import { useStrategyStore, StrategyStatus } from '../stores/strategyStore';
import { useAlertStore } from '../stores/alertStore';

/**
 * State sync payload from server
 */
interface StateSyncPayload {
  backtest_status: string;
  replay_status?: {
    state: string;
    speed: number;
    current_time: string;
    current_index: number;
    event_sequence: number;
    total_events: number;
    progress_percent: number;
  };
  account?: {
    cash: number;
    frozen_margin: number;
    available_balance: number;
    total_value: number;
  };
  positions?: Array<{
    symbol: string;
    direction: 'LONG' | 'SHORT';
    volume: number;
    cost_price: number;
    unrealized_pnl: number;
  }>;
  strategies?: Array<{
    strategy_id: string;
    name: string;
    class_name: string;
    status: string;
    parameters: Record<string, unknown>;
  }>;
  alerts?: Array<{
    alert_id: string;
    alert_type: 'sync' | 'async';
    severity: 'info' | 'warning' | 'error' | 'critical';
    title: string;
    message: string;
    timestamp: string;
  }>;
  timestamp: number;
}

/**
 * Response payload from server
 */
interface ResponsePayload {
  success: boolean;
  message?: string;
  error?: string;
  error_code?: string;
  [key: string]: unknown;
}

/**
 * Pending request tracking
 */
interface PendingRequest {
  resolve: (response: ResponsePayload) => void;
  reject: (error: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
}

/**
 * Integration service configuration
 */
export interface IntegrationConfig {
  wsUrl?: string;
  requestTimeout?: number;
  autoConnect?: boolean;
  onConnected?: () => void;
  onDisconnected?: () => void;
  onError?: (error: Error) => void;
}

const DEFAULT_CONFIG: IntegrationConfig = {
  wsUrl: 'ws://localhost:8765',
  requestTimeout: 30000,
  autoConnect: true,
};

/**
 * Integration Service
 * 
 * Manages the complete communication flow between frontend and backend.
 */
export class IntegrationService {
  private wsService: WebSocketService | null = null;
  private config: IntegrationConfig;
  private pendingRequests: Map<string, PendingRequest> = new Map();
  private isInitialized = false;

  constructor(config?: IntegrationConfig) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Initialize the integration service
   */
  public initialize(): void {
    if (this.isInitialized) {
      console.warn('[Integration] Already initialized');
      return;
    }

    const callbacks: WebSocketCallbacks = {
      onOpen: this.handleOpen.bind(this),
      onClose: this.handleClose.bind(this),
      onError: this.handleError.bind(this),
      onMessage: this.handleMessage.bind(this),
      onReconnecting: this.handleReconnecting.bind(this),
    };

    this.wsService = new WebSocketService(this.config.wsUrl, callbacks);
    this.isInitialized = true;

    if (this.config.autoConnect) {
      this.connect();
    }
  }

  /**
   * Connect to the WebSocket server
   */
  public connect(): void {
    if (!this.wsService) {
      this.initialize();
    }
    
    useConnectionStore.getState().setConnectionState(ConnectionState.CONNECTING);
    this.wsService?.connect();
  }

  /**
   * Disconnect from the WebSocket server
   */
  public disconnect(): void {
    this.wsService?.disconnect();
    useConnectionStore.getState().setConnectionState(ConnectionState.DISCONNECTED);
  }

  /**
   * Check if connected
   */
  public isConnected(): boolean {
    return this.wsService?.isConnected() ?? false;
  }

  // ============================================
  // Backtest Control Methods
  // ============================================

  /**
   * Start a backtest
   */
  public async startBacktest(config: StartBacktestPayload): Promise<ResponsePayload> {
    useBacktestStore.getState().startBacktest({
      strategyId: config.strategy_id,
      startDate: config.start_date,
      endDate: config.end_date,
      initialCapital: config.initial_capital,
      matchingMode: config.matching_config.mode,
      l2Level: config.matching_config.l2_level,
      commissionRate: config.matching_config.commission_rate,
      slippageModel: config.matching_config.slippage_model,
      slippageValue: config.matching_config.slippage_value,
    });

    return this.sendRequest(MessageType.START_BACKTEST, config);
  }

  /**
   * Pause the backtest
   */
  public async pause(): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.PAUSE, {});
  }

  /**
   * Resume the backtest
   */
  public async resume(): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.RESUME, {});
  }

  /**
   * Step forward one time unit
   */
  public async step(): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.STEP, {});
  }

  /**
   * Stop the backtest
   */
  public async stop(): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.STOP, {});
  }

  // ============================================
  // Strategy Methods
  // ============================================

  /**
   * Load a strategy
   */
  public async loadStrategy(filePath: string): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.LOAD_STRATEGY, { file_path: filePath });
  }

  /**
   * Reload a strategy with hot reload
   */
  public async reloadStrategy(
    strategyId: string,
    policy: 'reset' | 'preserve' | 'selective',
    preserveVars?: string[]
  ): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.RELOAD_STRATEGY, {
      strategy_id: strategyId,
      policy,
      preserve_vars: preserveVars,
    });
  }

  /**
   * Update strategy parameters
   */
  public async updateParams(
    strategyId: string,
    params: Record<string, unknown>
  ): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.UPDATE_PARAMS, {
      strategy_id: strategyId,
      params,
    });
  }

  // ============================================
  // Manual Trading Methods
  // ============================================

  /**
   * Submit a manual order
   */
  public async submitManualOrder(order: ManualOrderPayload): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.MANUAL_ORDER, order);
  }

  /**
   * Cancel an order
   */
  public async cancelOrder(orderId: string): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.CANCEL_ORDER, { order_id: orderId });
  }

  /**
   * Close all positions
   */
  public async closeAllPositions(): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.CLOSE_ALL, {});
  }

  // ============================================
  // Snapshot Methods
  // ============================================

  /**
   * Save a snapshot
   */
  public async saveSnapshot(description?: string): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.SAVE_SNAPSHOT, { description });
  }

  /**
   * Load a snapshot
   */
  public async loadSnapshot(path: string): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.LOAD_SNAPSHOT, { path });
  }

  // ============================================
  // Alert Methods
  // ============================================

  /**
   * Acknowledge an alert
   */
  public async acknowledgeAlert(alertId: string): Promise<ResponsePayload> {
    useAlertStore.getState().acknowledgeAlert(alertId);
    return this.sendRequest(MessageType.ALERT_ACK, { alert_id: alertId });
  }

  // ============================================
  // State Sync Methods
  // ============================================

  /**
   * Request current state from server
   */
  public async requestState(): Promise<ResponsePayload> {
    return this.sendRequest(MessageType.STATUS, {});
  }

  // ============================================
  // Private Methods
  // ============================================

  /**
   * Send a request and wait for response
   */
  private sendRequest<T = unknown>(type: MessageType, payload: T): Promise<ResponsePayload> {
    return new Promise((resolve, reject) => {
      if (!this.wsService || !this.wsService.isConnected()) {
        reject(new Error('Not connected to server'));
        return;
      }

      const messageId = this.wsService.send(type, payload);

      const timeout = setTimeout(() => {
        this.pendingRequests.delete(messageId);
        reject(new Error('Request timeout'));
      }, this.config.requestTimeout);

      this.pendingRequests.set(messageId, { resolve, reject, timeout });
    });
  }

  /**
   * Handle WebSocket open event
   */
  private handleOpen(): void {
    console.log('[Integration] Connected to server');
    useConnectionStore.getState().setConnectionState(ConnectionState.CONNECTED);
    useConnectionStore.getState().resetReconnectAttempts();
    this.config.onConnected?.();

    // Request initial state sync
    this.requestState().catch((err) => {
      console.warn('[Integration] Failed to request initial state:', err);
    });
  }

  /**
   * Handle WebSocket close event
   */
  private handleClose(): void {
    console.log('[Integration] Disconnected from server');
    useConnectionStore.getState().setConnectionState(ConnectionState.DISCONNECTED);
    this.config.onDisconnected?.();

    // Reject all pending requests
    this.pendingRequests.forEach((request, id) => {
      clearTimeout(request.timeout);
      request.reject(new Error('Connection closed'));
      this.pendingRequests.delete(id);
    });
  }

  /**
   * Handle WebSocket error event
   */
  private handleError(error: Error): void {
    console.error('[Integration] WebSocket error:', error);
    useConnectionStore.getState().setConnectionState(ConnectionState.ERROR);
    useConnectionStore.getState().setError(error.message);
    this.config.onError?.(error);
  }

  /**
   * Handle reconnecting event
   */
  private handleReconnecting(attempt: number): void {
    console.log(`[Integration] Reconnecting (attempt ${attempt})`);
    useConnectionStore.getState().setConnectionState(ConnectionState.RECONNECTING);
    useConnectionStore.getState().incrementReconnectAttempts();
  }

  /**
   * Handle incoming WebSocket message
   */
  private handleMessage(message: Message): void {
    // Check if this is a response to a pending request
    if (this.pendingRequests.has(message.id)) {
      const request = this.pendingRequests.get(message.id)!;
      clearTimeout(request.timeout);
      this.pendingRequests.delete(message.id);
      request.resolve(message.payload as ResponsePayload);
      return;
    }

    // Handle different message types
    switch (message.type) {
      case MessageType.STATE_SYNC:
        this.handleStateSync(message.payload as StateSyncPayload);
        break;

      case MessageType.TICK_UPDATE:
        this.handleTickUpdate(message.payload as TickUpdatePayload);
        break;

      case MessageType.BAR_UPDATE:
        this.handleBarUpdate(message.payload as BarUpdatePayload);
        break;

      case MessageType.POSITION_UPDATE:
        this.handlePositionUpdate(message.payload as PositionUpdatePayload[]);
        break;

      case MessageType.ACCOUNT_UPDATE:
        this.handleAccountUpdate(message.payload as AccountUpdatePayload);
        break;

      case MessageType.TRADE_UPDATE:
        this.handleTradeUpdate(message.payload as TradeUpdatePayload);
        break;

      case MessageType.ALERT:
        this.handleAlert(message.payload as AlertPayload);
        break;

      case MessageType.ERROR:
        this.handleServerError(message.payload as ResponsePayload);
        break;

      case MessageType.CONNECT:
        console.log('[Integration] Server acknowledged connection:', message.payload);
        break;

      case MessageType.HEARTBEAT:
        // Heartbeat is handled by WebSocketService
        break;

      default:
        console.log('[Integration] Unhandled message type:', message.type, message.payload);
    }
  }

  /**
   * Handle state sync from server
   */
  private handleStateSync(payload: StateSyncPayload): void {
    console.log('[Integration] State sync received:', payload);

    const backtestStore = useBacktestStore.getState();
    const strategyStore = useStrategyStore.getState();
    const alertStore = useAlertStore.getState();

    // Update backtest status
    if (payload.backtest_status) {
      const statusMap: Record<string, BacktestStatus> = {
        idle: BacktestStatus.IDLE,
        loading: BacktestStatus.LOADING,
        running: BacktestStatus.RUNNING,
        paused: BacktestStatus.PAUSED,
        completed: BacktestStatus.COMPLETED,
        failed: BacktestStatus.FAILED,
      };
      backtestStore.setStatus(statusMap[payload.backtest_status] || BacktestStatus.IDLE);
    }

    // Update replay status
    if (payload.replay_status) {
      const { progress_percent, current_time } = payload.replay_status;
      backtestStore.setProgress(progress_percent, current_time);
    }

    // Update account
    if (payload.account) {
      backtestStore.updateAccount({
        cash: payload.account.cash,
        frozen_margin: payload.account.frozen_margin,
        available_balance: payload.account.available_balance,
        total_value: payload.account.total_value,
      });
    }

    // Update positions
    if (payload.positions) {
      backtestStore.updatePositions(
        payload.positions.map((p) => ({
          symbol: p.symbol,
          direction: p.direction,
          volume: p.volume,
          cost_price: p.cost_price,
          unrealized_pnl: p.unrealized_pnl,
        }))
      );
    }

    // Update strategies
    if (payload.strategies) {
      payload.strategies.forEach((s) => {
        const statusMap: Record<string, StrategyStatus> = {
          unloaded: StrategyStatus.UNLOADED,
          loading: StrategyStatus.LOADING,
          loaded: StrategyStatus.LOADED,
          running: StrategyStatus.RUNNING,
          stopped: StrategyStatus.STOPPED,
          error: StrategyStatus.ERROR,
        };
        strategyStore.setStrategyStatus(s.strategy_id, statusMap[s.status] || StrategyStatus.UNLOADED);
      });
    }

    // Update alerts
    if (payload.alerts) {
      payload.alerts.forEach((alert) => {
        alertStore.addAlert(alert);
      });
    }
  }

  /**
   * Handle tick update from server
   */
  private handleTickUpdate(payload: TickUpdatePayload): void {
    useBacktestStore.getState().updateTick(payload);
  }

  /**
   * Handle bar update from server
   */
  private handleBarUpdate(payload: BarUpdatePayload): void {
    useBacktestStore.getState().updateBar(payload);
  }

  /**
   * Handle position update from server
   */
  private handlePositionUpdate(payload: PositionUpdatePayload[]): void {
    useBacktestStore.getState().updatePositions(payload);
  }

  /**
   * Handle account update from server
   */
  private handleAccountUpdate(payload: AccountUpdatePayload): void {
    useBacktestStore.getState().updateAccount(payload);
  }

  /**
   * Handle trade update from server
   */
  private handleTradeUpdate(payload: TradeUpdatePayload): void {
    useBacktestStore.getState().addTrade(payload);
  }

  /**
   * Handle alert from server
   */
  private handleAlert(payload: AlertPayload): void {
    useAlertStore.getState().addAlert(payload);
  }

  /**
   * Handle server error
   */
  private handleServerError(payload: ResponsePayload): void {
    console.error('[Integration] Server error:', payload.error);
    useConnectionStore.getState().setError(payload.error || 'Unknown server error');
  }
}

// Singleton instance
let integrationService: IntegrationService | null = null;

/**
 * Get the integration service singleton
 */
export function getIntegrationService(): IntegrationService {
  if (!integrationService) {
    integrationService = new IntegrationService();
  }
  return integrationService;
}

/**
 * Initialize the integration service with custom config
 */
export function initIntegrationService(config?: IntegrationConfig): IntegrationService {
  integrationService = new IntegrationService(config);
  integrationService.initialize();
  return integrationService;
}

export default IntegrationService;
