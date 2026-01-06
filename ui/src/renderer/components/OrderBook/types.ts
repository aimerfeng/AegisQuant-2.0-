/**
 * OrderBook Types
 * 
 * Type definitions for the Order Book (深度图) component.
 */

/**
 * Single price level in the order book
 */
export interface OrderBookLevel {
  price: number;
  volume: number;
  total: number;      // Cumulative volume
  percentage: number; // Percentage of max volume for visualization
}

/**
 * Order book data structure
 */
export interface OrderBookData {
  symbol: string;
  timestamp: number;
  bids: OrderBookLevel[];  // Buy orders (sorted by price descending)
  asks: OrderBookLevel[];  // Sell orders (sorted by price ascending)
  lastPrice?: number;
  spread?: number;
  spreadPercent?: number;
}

/**
 * Order book update message from WebSocket
 */
export interface OrderBookUpdate {
  type: 'snapshot' | 'delta';
  symbol: string;
  timestamp: number;
  bids?: Array<[number, number]>;  // [price, volume]
  asks?: Array<[number, number]>;  // [price, volume]
}

/**
 * Order book display mode
 */
export enum OrderBookDisplayMode {
  VERTICAL = 'vertical',     // Traditional vertical layout
  HORIZONTAL = 'horizontal', // Horizontal depth chart
  COMBINED = 'combined',     // Both views
}

/**
 * Order book theme
 */
export interface OrderBookTheme {
  backgroundColor: string;
  textColor: string;
  bidColor: string;
  askColor: string;
  bidBackgroundColor: string;
  askBackgroundColor: string;
  spreadColor: string;
  borderColor: string;
  highlightColor: string;
  headerBackgroundColor: string;
}

/**
 * Default dark theme for order book
 */
export const darkOrderBookTheme: OrderBookTheme = {
  backgroundColor: '#1e222d',
  textColor: '#d1d4dc',
  bidColor: '#26a69a',
  askColor: '#ef5350',
  bidBackgroundColor: 'rgba(38, 166, 154, 0.15)',
  askBackgroundColor: 'rgba(239, 83, 80, 0.15)',
  spreadColor: '#758696',
  borderColor: '#2b2f3a',
  highlightColor: '#3d4f5f',
  headerBackgroundColor: '#252930',
};

/**
 * Default light theme for order book
 */
export const lightOrderBookTheme: OrderBookTheme = {
  backgroundColor: '#ffffff',
  textColor: '#131722',
  bidColor: '#26a69a',
  askColor: '#ef5350',
  bidBackgroundColor: 'rgba(38, 166, 154, 0.1)',
  askBackgroundColor: 'rgba(239, 83, 80, 0.1)',
  spreadColor: '#9598a1',
  borderColor: '#e1e3eb',
  highlightColor: '#f0f3fa',
  headerBackgroundColor: '#f8f9fd',
};

/**
 * OrderBook component props
 */
export interface OrderBookProps {
  // Data
  data?: OrderBookData;
  
  // Display options
  displayMode?: OrderBookDisplayMode;
  levels?: number;  // Number of price levels to display (default: 10)
  precision?: number;  // Price decimal precision
  volumePrecision?: number;  // Volume decimal precision
  
  // Theme
  theme?: OrderBookTheme;
  
  // Callbacks
  onPriceClick?: (price: number, side: 'bid' | 'ask') => void;
  onVolumeClick?: (price: number, volume: number, side: 'bid' | 'ask') => void;
  
  // Animation
  animateUpdates?: boolean;
  
  // Dimensions
  width?: number;
  height?: number;
  autoSize?: boolean;
}

/**
 * Order book state for internal management
 */
export interface OrderBookState {
  isLoading: boolean;
  lastUpdateTime: number;
  highlightedPrice: number | null;
  maxBidVolume: number;
  maxAskVolume: number;
}

/**
 * Price level change type for animation
 */
export enum PriceLevelChangeType {
  NONE = 'none',
  INCREASED = 'increased',
  DECREASED = 'decreased',
  NEW = 'new',
  REMOVED = 'removed',
}

/**
 * Animated price level with change tracking
 */
export interface AnimatedOrderBookLevel extends OrderBookLevel {
  changeType: PriceLevelChangeType;
  previousVolume?: number;
}
