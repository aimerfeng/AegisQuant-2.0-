/**
 * KLine Chart Types
 * 
 * Type definitions for the K-Line chart component.
 */

import { Time, SeriesMarker, LineStyle } from 'lightweight-charts';

/**
 * OHLCV candlestick data
 */
export interface CandlestickData {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

/**
 * Volume bar data
 */
export interface VolumeData {
  time: Time;
  value: number;
  color?: string;
}

/**
 * Trade marker for displaying entry/exit points
 */
export interface TradeMarker {
  id: string;
  time: Time;
  position: 'aboveBar' | 'belowBar';
  color: string;
  shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square';
  text?: string;
  size?: number;
  // Trade details for tooltip
  tradeDetails?: TradeDetails;
}

/**
 * Trade details for tooltip display
 */
export interface TradeDetails {
  tradeId: string;
  direction: 'LONG' | 'SHORT';
  action: 'OPEN' | 'CLOSE';
  price: number;
  volume: number;
  pnl?: number;
  pnlPercent?: number;
  commission?: number;
  timestamp: string;
  isManual?: boolean;
}

/**
 * Drawing tool types
 */
export enum DrawingToolType {
  NONE = 'none',
  TREND_LINE = 'trendLine',
  FIBONACCI = 'fibonacci',
  RECTANGLE = 'rectangle',
}

/**
 * Drawing object base interface
 */
export interface DrawingObject {
  id: string;
  type: DrawingToolType;
  visible: boolean;
  color: string;
  lineWidth: number;
  lineStyle: LineStyle;
}

/**
 * Trend line drawing
 */
export interface TrendLineDrawing extends DrawingObject {
  type: DrawingToolType.TREND_LINE;
  startPoint: { time: Time; price: number };
  endPoint: { time: Time; price: number };
  extendLeft?: boolean;
  extendRight?: boolean;
}

/**
 * Fibonacci retracement drawing
 */
export interface FibonacciDrawing extends DrawingObject {
  type: DrawingToolType.FIBONACCI;
  startPoint: { time: Time; price: number };
  endPoint: { time: Time; price: number };
  levels: number[]; // e.g., [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
  showLabels: boolean;
}

/**
 * Rectangle drawing
 */
export interface RectangleDrawing extends DrawingObject {
  type: DrawingToolType.RECTANGLE;
  topLeft: { time: Time; price: number };
  bottomRight: { time: Time; price: number };
  fillColor?: string;
  fillOpacity?: number;
}

/**
 * Union type for all drawing objects
 */
export type Drawing = TrendLineDrawing | FibonacciDrawing | RectangleDrawing;

/**
 * Technical indicator types
 */
export enum IndicatorType {
  MA = 'ma',
  EMA = 'ema',
  MACD = 'macd',
  RSI = 'rsi',
  BOLLINGER = 'bollinger',
}

/**
 * Indicator configuration base
 */
export interface IndicatorConfig {
  id: string;
  type: IndicatorType;
  visible: boolean;
  color?: string;
}

/**
 * Moving Average configuration
 */
export interface MAConfig extends IndicatorConfig {
  type: IndicatorType.MA | IndicatorType.EMA;
  period: number;
  color: string;
  lineWidth: number;
}

/**
 * MACD configuration
 */
export interface MACDConfig extends IndicatorConfig {
  type: IndicatorType.MACD;
  fastPeriod: number;
  slowPeriod: number;
  signalPeriod: number;
  macdColor: string;
  signalColor: string;
  histogramPositiveColor: string;
  histogramNegativeColor: string;
}

/**
 * RSI configuration
 */
export interface RSIConfig extends IndicatorConfig {
  type: IndicatorType.RSI;
  period: number;
  overbought: number;
  oversold: number;
  lineColor: string;
  overboughtColor: string;
  oversoldColor: string;
}

/**
 * Bollinger Bands configuration
 */
export interface BollingerConfig extends IndicatorConfig {
  type: IndicatorType.BOLLINGER;
  period: number;
  stdDev: number;
  upperColor: string;
  middleColor: string;
  lowerColor: string;
  fillColor?: string;
  fillOpacity?: number;
}

/**
 * Union type for all indicator configs
 */
export type Indicator = MAConfig | MACDConfig | RSIConfig | BollingerConfig;

/**
 * Chart theme
 */
export interface ChartTheme {
  backgroundColor: string;
  textColor: string;
  gridColor: string;
  borderColor: string;
  upColor: string;
  downColor: string;
  volumeUpColor: string;
  volumeDownColor: string;
  crosshairColor: string;
}

/**
 * Default dark theme
 */
export const darkTheme: ChartTheme = {
  backgroundColor: '#1e222d',
  textColor: '#d1d4dc',
  gridColor: '#2b2f3a',
  borderColor: '#2b2f3a',
  upColor: '#26a69a',
  downColor: '#ef5350',
  volumeUpColor: 'rgba(38, 166, 154, 0.5)',
  volumeDownColor: 'rgba(239, 83, 80, 0.5)',
  crosshairColor: '#758696',
};

/**
 * Default light theme
 */
export const lightTheme: ChartTheme = {
  backgroundColor: '#ffffff',
  textColor: '#131722',
  gridColor: '#e1e3eb',
  borderColor: '#e1e3eb',
  upColor: '#26a69a',
  downColor: '#ef5350',
  volumeUpColor: 'rgba(38, 166, 154, 0.5)',
  volumeDownColor: 'rgba(239, 83, 80, 0.5)',
  crosshairColor: '#9598a1',
};

/**
 * KLine chart props
 */
export interface KLineChartProps {
  // Data
  data?: CandlestickData[];
  volumeData?: VolumeData[];
  
  // Trade markers
  tradeMarkers?: TradeMarker[];
  
  // Drawings
  drawings?: Drawing[];
  activeDrawingTool?: DrawingToolType;
  onDrawingComplete?: (drawing: Drawing) => void;
  onDrawingUpdate?: (drawing: Drawing) => void;
  onDrawingDelete?: (drawingId: string) => void;
  
  // Indicators
  indicators?: Indicator[];
  onIndicatorAdd?: (indicator: Indicator) => void;
  onIndicatorRemove?: (indicatorId: string) => void;
  onIndicatorUpdate?: (indicator: Indicator) => void;
  
  // Theme
  theme?: ChartTheme;
  
  // Symbol info
  symbol?: string;
  interval?: string;
  
  // Callbacks
  onCrosshairMove?: (time: Time | null, price: number | null) => void;
  onVisibleRangeChange?: (from: Time, to: Time) => void;
  onTradeMarkerHover?: (marker: TradeMarker | null) => void;
  onTradeMarkerClick?: (marker: TradeMarker) => void;
  
  // Drawing coordinate exposure for strategy
  onDrawingCoordinatesExport?: (drawings: Drawing[]) => void;
  
  // Chart dimensions
  width?: number;
  height?: number;
  autoSize?: boolean;
}

/**
 * Chart state for internal management
 */
export interface ChartState {
  isReady: boolean;
  visibleRange: { from: Time; to: Time } | null;
  crosshairPosition: { time: Time; price: number } | null;
  hoveredMarker: TradeMarker | null;
  activeDrawing: Drawing | null;
  drawingInProgress: boolean;
}
