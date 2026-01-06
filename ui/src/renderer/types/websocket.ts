/**
 * Titan-Quant WebSocket Types
 * 
 * Type definitions for WebSocket communication protocol.
 * Based on the design document communication protocol specification.
 */

/**
 * Message types for WebSocket communication
 */
export enum MessageType {
  // Control messages
  CONNECT = 'connect',
  DISCONNECT = 'disconnect',
  HEARTBEAT = 'heartbeat',

  // Backtest control
  START_BACKTEST = 'start_backtest',
  PAUSE = 'pause',
  RESUME = 'resume',
  STEP = 'step',
  STOP = 'stop',

  // Data push
  TICK_UPDATE = 'tick_update',
  BAR_UPDATE = 'bar_update',
  POSITION_UPDATE = 'position_update',
  ACCOUNT_UPDATE = 'account_update',
  TRADE_UPDATE = 'trade_update',

  // Strategy operations
  LOAD_STRATEGY = 'load_strategy',
  RELOAD_STRATEGY = 'reload_strategy',
  UPDATE_PARAMS = 'update_params',

  // Manual trading
  MANUAL_ORDER = 'manual_order',
  CANCEL_ORDER = 'cancel_order',
  CLOSE_ALL = 'close_all',

  // Snapshot
  SAVE_SNAPSHOT = 'save_snapshot',
  LOAD_SNAPSHOT = 'load_snapshot',

  // Alert
  ALERT = 'alert',
  ALERT_ACK = 'alert_ack',

  // System
  ERROR = 'error',
  STATUS = 'status',
  
  // State sync
  STATE_SYNC = 'state_sync',
  REQUEST_STATE = 'request_state',
  
  // Response
  RESPONSE = 'response',
}

/**
 * Base message structure
 */
export interface Message<T = unknown> {
  id: string;
  type: MessageType;
  timestamp: number;
  payload: T;
}

/**
 * Message handler function type
 */
export type MessageHandler<T = unknown> = (message: Message<T>) => void;

/**
 * WebSocket configuration
 */
export interface WebSocketConfig {
  url: string;
  reconnectInterval: number;
  maxReconnectInterval: number;
  reconnectDecay: number;
  maxReconnectAttempts: number;
  heartbeatInterval: number;
  heartbeatTimeout: number;
}

// Payload types for specific messages

/**
 * Start backtest payload
 */
export interface StartBacktestPayload {
  strategy_id: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  matching_config: {
    mode: 'L1' | 'L2';
    l2_level?: 'LEVEL_1' | 'LEVEL_2' | 'LEVEL_3';
    commission_rate: number;
    slippage_model: string;
    slippage_value: number;
  };
  replay_speed: number;
}

/**
 * Manual order payload
 */
export interface ManualOrderPayload {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  offset: 'OPEN' | 'CLOSE';
  price: number;
  volume: number;
}

/**
 * Tick data update payload
 */
export interface TickUpdatePayload {
  symbol: string;
  exchange: string;
  datetime: string;
  last_price: number;
  volume: number;
  bid_price_1: number;
  bid_volume_1: number;
  ask_price_1: number;
  ask_volume_1: number;
  bid_prices?: number[];
  bid_volumes?: number[];
  ask_prices?: number[];
  ask_volumes?: number[];
}

/**
 * Bar data update payload
 */
export interface BarUpdatePayload {
  symbol: string;
  exchange: string;
  datetime: string;
  interval: string;
  open_price: number;
  high_price: number;
  low_price: number;
  close_price: number;
  volume: number;
  turnover: number;
}

/**
 * Position update payload
 */
export interface PositionUpdatePayload {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  volume: number;
  cost_price: number;
  unrealized_pnl: number;
}

/**
 * Account update payload
 */
export interface AccountUpdatePayload {
  cash: number;
  frozen_margin: number;
  available_balance: number;
  total_value: number;
}

/**
 * Trade update payload
 */
export interface TradeUpdatePayload {
  trade_id: string;
  order_id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  offset: 'OPEN' | 'CLOSE';
  price: number;
  volume: number;
  commission: number;
  is_manual: boolean;
  timestamp: string;
}

/**
 * Alert payload
 */
export interface AlertPayload {
  alert_id: string;
  alert_type: 'sync' | 'async';
  severity: 'info' | 'warning' | 'error' | 'critical';
  title: string;
  message: string;
  timestamp: string;
}

/**
 * Error payload
 */
export interface ErrorPayload {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

/**
 * Heartbeat payload
 */
export interface HeartbeatPayload {
  ping?: number;
  pong?: number;
}
