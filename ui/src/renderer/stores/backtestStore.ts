/**
 * Titan-Quant Backtest Store
 * 
 * Zustand store for managing backtest state and synchronization.
 * Handles backtest lifecycle, playback control, and real-time data updates.
 * 
 * Requirements:
 * - 5.1: Replay_Controller SHALL provide playback controls
 * - 5.2: WHEN user clicks pause, Replay_Controller SHALL freeze backtest state
 * - 5.3: WHEN user clicks single step, Replay_Controller SHALL advance one time unit
 * - 5.4: WHEN user adjusts playback speed, Replay_Controller SHALL adjust accordingly
 * - 9.7: Backtest_Mode SHALL use single-threaded sequential execution for determinism
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  TickUpdatePayload,
  BarUpdatePayload,
  PositionUpdatePayload,
  AccountUpdatePayload,
  TradeUpdatePayload,
} from '../types/websocket';

/**
 * Backtest status enum
 */
export enum BacktestStatus {
  IDLE = 'idle',
  LOADING = 'loading',
  RUNNING = 'running',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

/**
 * Matching mode
 */
export type MatchingMode = 'L1' | 'L2';

/**
 * L2 simulation level
 */
export type L2SimulationLevel = 'LEVEL_1' | 'LEVEL_2' | 'LEVEL_3';

/**
 * Playback speed options
 */
export type PlaybackSpeed = 1 | 2 | 4 | 10;

/**
 * Backtest configuration
 */
export interface BacktestConfig {
  strategyId: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  matchingMode: MatchingMode;
  l2Level?: L2SimulationLevel;
  commissionRate: number;
  slippageModel: string;
  slippageValue: number;
}

/**
 * Position data
 */
export interface Position {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  volume: number;
  costPrice: number;
  unrealizedPnl: number;
}

/**
 * Account state
 */
export interface AccountState {
  cash: number;
  frozenMargin: number;
  availableBalance: number;
  totalValue: number;
}

/**
 * Trade record
 */
export interface Trade {
  tradeId: string;
  orderId: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  offset: 'OPEN' | 'CLOSE';
  price: number;
  volume: number;
  commission: number;
  isManual: boolean;
  timestamp: string;
}

/**
 * Tick data
 */
export interface TickData {
  symbol: string;
  exchange: string;
  datetime: string;
  lastPrice: number;
  volume: number;
  bidPrice1: number;
  bidVolume1: number;
  askPrice1: number;
  askVolume1: number;
  bidPrices?: number[];
  bidVolumes?: number[];
  askPrices?: number[];
  askVolumes?: number[];
}

/**
 * Bar data
 */
export interface BarData {
  symbol: string;
  exchange: string;
  datetime: string;
  interval: string;
  openPrice: number;
  highPrice: number;
  lowPrice: number;
  closePrice: number;
  volume: number;
  turnover: number;
}

/**
 * Backtest result metrics
 */
export interface BacktestMetrics {
  totalReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  avgProfit: number;
  avgLoss: number;
}

/**
 * Backtest store state
 */
interface BacktestState {
  // Backtest lifecycle
  status: BacktestStatus;
  backtestId: string | null;
  config: BacktestConfig | null;
  error: string | null;
  
  // Playback control
  isPlaying: boolean;
  playbackSpeed: PlaybackSpeed;
  currentTime: string;
  progress: number;
  
  // Real-time data
  currentTick: TickData | null;
  currentBar: BarData | null;
  bars: BarData[];
  
  // Account & positions
  account: AccountState;
  positions: Position[];
  
  // Trade history
  trades: Trade[];
  
  // Results
  metrics: BacktestMetrics | null;
}

/**
 * Backtest store actions
 */
interface BacktestActions {
  // Lifecycle actions
  startBacktest: (config: BacktestConfig) => void;
  setBacktestId: (id: string) => void;
  setStatus: (status: BacktestStatus) => void;
  setError: (error: string | null) => void;
  resetBacktest: () => void;
  
  // Playback actions
  play: () => void;
  pause: () => void;
  setPlaybackSpeed: (speed: PlaybackSpeed) => void;
  setProgress: (progress: number, currentTime: string) => void;
  
  // Data update actions
  updateTick: (tick: TickUpdatePayload) => void;
  updateBar: (bar: BarUpdatePayload) => void;
  updateAccount: (account: AccountUpdatePayload) => void;
  updatePositions: (positions: PositionUpdatePayload[]) => void;
  addTrade: (trade: TradeUpdatePayload) => void;
  
  // Results
  setMetrics: (metrics: BacktestMetrics) => void;
  
  // Getters
  getPosition: (symbol: string) => Position | undefined;
  getTotalPnl: () => number;
}

/**
 * Initial account state
 */
const initialAccount: AccountState = {
  cash: 0,
  frozenMargin: 0,
  availableBalance: 0,
  totalValue: 0,
};

/**
 * Initial backtest state
 */
const initialState: BacktestState = {
  status: BacktestStatus.IDLE,
  backtestId: null,
  config: null,
  error: null,
  isPlaying: false,
  playbackSpeed: 1,
  currentTime: '--:--:--',
  progress: 0,
  currentTick: null,
  currentBar: null,
  bars: [],
  account: initialAccount,
  positions: [],
  trades: [],
  metrics: null,
};

/**
 * Backtest store implementation
 */
export const useBacktestStore = create<BacktestState & BacktestActions>()(
  persist(
    (set, get) => ({
      ...initialState,

      // Lifecycle actions
      startBacktest: (config: BacktestConfig) => {
        set({
          status: BacktestStatus.LOADING,
          config,
          error: null,
          isPlaying: false,
          progress: 0,
          currentTime: '--:--:--',
          bars: [],
          trades: [],
          positions: [],
          account: {
            ...initialAccount,
            cash: config.initialCapital,
            availableBalance: config.initialCapital,
            totalValue: config.initialCapital,
          },
          metrics: null,
        });
      },

      setBacktestId: (id: string) => {
        set({ backtestId: id });
      },

      setStatus: (status: BacktestStatus) => {
        set({ status });
        
        // Auto-update isPlaying based on status
        if (status === BacktestStatus.RUNNING) {
          set({ isPlaying: true });
        } else if (status === BacktestStatus.PAUSED || 
                   status === BacktestStatus.COMPLETED || 
                   status === BacktestStatus.FAILED) {
          set({ isPlaying: false });
        }
      },

      setError: (error: string | null) => {
        set({ 
          error,
          status: error ? BacktestStatus.FAILED : get().status,
        });
      },

      resetBacktest: () => {
        set(initialState);
      },

      // Playback actions
      play: () => {
        set({ isPlaying: true, status: BacktestStatus.RUNNING });
      },

      pause: () => {
        set({ isPlaying: false, status: BacktestStatus.PAUSED });
      },

      setPlaybackSpeed: (speed: PlaybackSpeed) => {
        set({ playbackSpeed: speed });
      },

      setProgress: (progress: number, currentTime: string) => {
        set({ progress, currentTime });
      },

      // Data update actions
      updateTick: (tick: TickUpdatePayload) => {
        const tickData: TickData = {
          symbol: tick.symbol,
          exchange: tick.exchange,
          datetime: tick.datetime,
          lastPrice: tick.last_price,
          volume: tick.volume,
          bidPrice1: tick.bid_price_1,
          bidVolume1: tick.bid_volume_1,
          askPrice1: tick.ask_price_1,
          askVolume1: tick.ask_volume_1,
          bidPrices: tick.bid_prices,
          bidVolumes: tick.bid_volumes,
          askPrices: tick.ask_prices,
          askVolumes: tick.ask_volumes,
        };
        set({ currentTick: tickData });
      },

      updateBar: (bar: BarUpdatePayload) => {
        const barData: BarData = {
          symbol: bar.symbol,
          exchange: bar.exchange,
          datetime: bar.datetime,
          interval: bar.interval,
          openPrice: bar.open_price,
          highPrice: bar.high_price,
          lowPrice: bar.low_price,
          closePrice: bar.close_price,
          volume: bar.volume,
          turnover: bar.turnover,
        };
        
        set((state) => ({
          currentBar: barData,
          bars: [...state.bars.slice(-999), barData], // Keep last 1000 bars
        }));
      },

      updateAccount: (account: AccountUpdatePayload) => {
        set({
          account: {
            cash: account.cash,
            frozenMargin: account.frozen_margin,
            availableBalance: account.available_balance,
            totalValue: account.total_value,
          },
        });
      },

      updatePositions: (positions: PositionUpdatePayload[]) => {
        const positionData: Position[] = positions.map(p => ({
          symbol: p.symbol,
          direction: p.direction,
          volume: p.volume,
          costPrice: p.cost_price,
          unrealizedPnl: p.unrealized_pnl,
        }));
        set({ positions: positionData });
      },

      addTrade: (trade: TradeUpdatePayload) => {
        const tradeData: Trade = {
          tradeId: trade.trade_id,
          orderId: trade.order_id,
          symbol: trade.symbol,
          direction: trade.direction,
          offset: trade.offset,
          price: trade.price,
          volume: trade.volume,
          commission: trade.commission,
          isManual: trade.is_manual,
          timestamp: trade.timestamp,
        };
        
        set((state) => ({
          trades: [...state.trades, tradeData],
        }));
      },

      // Results
      setMetrics: (metrics: BacktestMetrics) => {
        set({ metrics });
      },

      // Getters
      getPosition: (symbol: string) => {
        return get().positions.find(p => p.symbol === symbol);
      },

      getTotalPnl: () => {
        const { positions } = get();
        return positions.reduce((sum, p) => sum + p.unrealizedPnl, 0);
      },
    }),
    {
      name: 'titan-quant-backtest',
      partialize: (state) => ({
        // Only persist configuration, not runtime state
        config: state.config,
        playbackSpeed: state.playbackSpeed,
      }),
    }
  )
);

/**
 * Hook to get backtest status
 */
export const useBacktestStatus = () => useBacktestStore((state) => state.status);

/**
 * Hook to get playback state
 */
export const usePlaybackState = () => useBacktestStore((state) => ({
  isPlaying: state.isPlaying,
  speed: state.playbackSpeed,
  progress: state.progress,
  currentTime: state.currentTime,
}));

/**
 * Hook to get account state
 */
export const useAccountState = () => useBacktestStore((state) => state.account);

/**
 * Hook to get positions
 */
export const usePositions = () => useBacktestStore((state) => state.positions);

/**
 * Hook to get trades
 */
export const useTrades = () => useBacktestStore((state) => state.trades);

export default useBacktestStore;
