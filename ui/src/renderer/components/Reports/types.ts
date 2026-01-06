/**
 * Reports Component Types
 * 
 * Type definitions for the backtest report viewer component.
 * 
 * Requirements: 15.1, 15.2
 */

/**
 * Equity curve data point
 */
export interface EquityPoint {
  timestamp: string;
  equity: number;
  cash: number;
  positionValue: number;
  drawdown: number;
}

/**
 * Trade record for display
 */
export interface TradeRecord {
  tradeId: string;
  orderId: string;
  timestamp: string;
  symbol: string;
  exchange: string;
  direction: 'LONG' | 'SHORT';
  offset: 'OPEN' | 'CLOSE';
  price: number;
  volume: number;
  turnover: number;
  commission: number;
  slippage: number;
  matchingMode: string;
  l2Level?: string;
  queueWaitTime?: number;
  isManual: boolean;
}

/**
 * Backtest performance metrics
 * 
 * Property 25: Report Metrics Completeness
 * Required metrics: sharpe_ratio, max_drawdown, total_return, win_rate, profit_factor, total_trades
 */
export interface BacktestMetrics {
  // Required metrics
  sharpeRatio: number;
  maxDrawdown: number;
  totalReturn: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  
  // Additional metrics
  annualizedReturn?: number;
  volatility?: number;
  calmarRatio?: number;
  sortinoRatio?: number;
  avgWin?: number;
  avgLoss?: number;
  maxWin?: number;
  maxLoss?: number;
  avgTradeDuration?: number;
  totalCommission?: number;
  netProfit?: number;
  grossProfit?: number;
  grossLoss?: number;
  winningTrades?: number;
  losingTrades?: number;
  startDate?: string;
  endDate?: string;
  initialCapital?: number;
  finalEquity?: number;
}

/**
 * Complete backtest report data
 */
export interface BacktestReport {
  reportId: string;
  backtestId: string;
  strategyName: string;
  metrics: BacktestMetrics;
  trades: TradeRecord[];
  equityCurve: EquityPoint[];
  createdAt: string;
  matchingMode: string;
  l2Level?: string;
}

/**
 * Metric card configuration
 */
export interface MetricCardConfig {
  key: keyof BacktestMetrics;
  label: string;
  format: 'percent' | 'number' | 'currency' | 'ratio';
  decimals?: number;
  colorize?: boolean;
  invertColor?: boolean; // For metrics where negative is good (like drawdown)
  icon?: string;
}

/**
 * Report view mode
 */
export enum ReportViewMode {
  SUMMARY = 'summary',
  TRADES = 'trades',
  EQUITY = 'equity',
}

/**
 * Reports component props
 */
export interface ReportsProps {
  report?: BacktestReport | null;
  onLoadReport?: (reportId: string) => void;
  onExportReport?: (format: 'html' | 'csv' | 'json') => void;
  isLoading?: boolean;
  error?: string | null;
}

/**
 * Theme for reports component
 */
export interface ReportsTheme {
  backgroundColor: string;
  cardBackgroundColor: string;
  textColor: string;
  textSecondaryColor: string;
  borderColor: string;
  profitColor: string;
  lossColor: string;
  chartLineColor: string;
  chartGridColor: string;
}

/**
 * Default dark theme for reports
 */
export const darkReportsTheme: ReportsTheme = {
  backgroundColor: '#1e1e1e',
  cardBackgroundColor: '#252526',
  textColor: '#d4d4d4',
  textSecondaryColor: '#9d9d9d',
  borderColor: '#3e3e42',
  profitColor: '#4caf50',
  lossColor: '#f44336',
  chartLineColor: '#0078d4',
  chartGridColor: '#3e3e42',
};
