/**
 * Titan-Quant Stores Index
 * 
 * Central export for all Zustand stores.
 * 
 * Requirements:
 * - UI 状态管理: Centralized state management using Zustand
 */

// Connection store - WebSocket connection state
export { useConnectionStore, ConnectionState } from './connectionStore';

// Auth store - User authentication and authorization
export { 
  useAuthStore, 
  useIsAuthenticated, 
  useCurrentUser, 
  useHasPermission, 
  useIsAdmin,
  type User,
  type UserRole,
  type AuthSession,
} from './authStore';

// I18n store - Internationalization state
export { useI18nStore, type SupportedLanguage } from './i18nStore';

// Layout store - Golden-Layout workspace state
export { useLayoutStore } from './layoutStore';

// Alert store - Alert and notification state
export { 
  useAlertStore,
  type Alert,
  type AlertSeverity,
  type AlertType,
} from './alertStore';

// Backtest store - Backtest lifecycle and data state
export {
  useBacktestStore,
  useBacktestStatus,
  usePlaybackState,
  useAccountState,
  usePositions,
  useTrades,
  BacktestStatus,
  type BacktestConfig,
  type Position,
  type AccountState,
  type Trade,
  type TickData,
  type BarData,
  type BacktestMetrics,
  type MatchingMode,
  type L2SimulationLevel,
  type PlaybackSpeed,
} from './backtestStore';

// Strategy store - Strategy management state
export {
  useStrategyStore,
  useAvailableStrategies,
  useSelectedStrategy,
  useActiveStrategies,
  useIsReloading,
  StrategyStatus,
  type StrategyInstance,
} from './strategyStore';
