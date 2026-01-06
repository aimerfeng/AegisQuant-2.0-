/**
 * OrderBook Component
 * 
 * Displays order book depth with buy/sell levels (买一到买十/卖一到卖十).
 * Supports vertical list view and horizontal depth chart visualization.
 * 
 * Requirements: 3.6 - THE UI_Client SHALL 提供独立的 OrderBook 深度图窗口，动态展示买一到买十的变化
 */

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  OrderBookProps,
  OrderBookData,
  OrderBookLevel,
  OrderBookDisplayMode,
  OrderBookTheme,
  AnimatedOrderBookLevel,
  PriceLevelChangeType,
  darkOrderBookTheme,
} from './types';
import './OrderBook.css';

/**
 * Format number with specified precision
 */
const formatNumber = (value: number, precision: number): string => {
  return value.toFixed(precision);
};

/**
 * Calculate cumulative totals for order book levels
 */
const calculateTotals = (levels: OrderBookLevel[]): OrderBookLevel[] => {
  let cumulative = 0;
  return levels.map(level => {
    cumulative += level.volume;
    return { ...level, total: cumulative };
  });
};

/**
 * Calculate percentage for volume bar visualization
 */
const calculatePercentages = (levels: OrderBookLevel[], maxVolume: number): OrderBookLevel[] => {
  if (maxVolume === 0) return levels;
  return levels.map(level => ({
    ...level,
    percentage: (level.total / maxVolume) * 100,
  }));
};

/**
 * Detect changes between old and new price levels for animation
 */
const detectChanges = (
  oldLevels: OrderBookLevel[],
  newLevels: OrderBookLevel[]
): AnimatedOrderBookLevel[] => {
  const oldMap = new Map(oldLevels.map(l => [l.price, l]));
  
  return newLevels.map(level => {
    const oldLevel = oldMap.get(level.price);
    let changeType = PriceLevelChangeType.NONE;
    let previousVolume: number | undefined;
    
    if (!oldLevel) {
      changeType = PriceLevelChangeType.NEW;
    } else if (level.volume > oldLevel.volume) {
      changeType = PriceLevelChangeType.INCREASED;
      previousVolume = oldLevel.volume;
    } else if (level.volume < oldLevel.volume) {
      changeType = PriceLevelChangeType.DECREASED;
      previousVolume = oldLevel.volume;
    }
    
    return { ...level, changeType, previousVolume };
  });
};

/**
 * Price Level Row Component
 * Wrapped with React.memo for performance optimization on high-frequency updates
 */
interface PriceLevelRowProps {
  level: AnimatedOrderBookLevel;
  side: 'bid' | 'ask';
  precision: number;
  volumePrecision: number;
  theme: OrderBookTheme;
  animateUpdates: boolean;
  onClick?: (price: number, side: 'bid' | 'ask') => void;
}

const PriceLevelRow: React.FC<PriceLevelRowProps> = React.memo(({
  level,
  side,
  precision,
  volumePrecision,
  theme,
  animateUpdates,
  onClick,
}) => {
  const [flashClass, setFlashClass] = useState('');
  
  useEffect(() => {
    if (!animateUpdates) return;
    
    let className = '';
    switch (level.changeType) {
      case PriceLevelChangeType.INCREASED:
        className = 'flash-increase';
        break;
      case PriceLevelChangeType.DECREASED:
        className = 'flash-decrease';
        break;
      case PriceLevelChangeType.NEW:
        className = 'flash-new';
        break;
    }
    
    if (className) {
      setFlashClass(className);
      const timer = setTimeout(() => setFlashClass(''), 500);
      return () => clearTimeout(timer);
    }
  }, [level.changeType, level.volume, animateUpdates]);
  
  const handleClick = useCallback(() => {
    onClick?.(level.price, side);
  }, [level.price, side, onClick]);
  
  const style = {
    '--volume-percent': `${level.percentage}%`,
    '--bid-color': theme.bidColor,
    '--ask-color': theme.askColor,
    '--bid-bg-color': theme.bidBackgroundColor,
    '--ask-bg-color': theme.askBackgroundColor,
    '--highlight-color': theme.highlightColor,
  } as React.CSSProperties;
  
  return (
    <div
      className={`orderbook-row ${side} ${flashClass}`}
      style={style}
      onClick={handleClick}
    >
      <span className="orderbook-price">{formatNumber(level.price, precision)}</span>
      <span className="orderbook-volume">{formatNumber(level.volume, volumePrecision)}</span>
      <span className="orderbook-total">{formatNumber(level.total, volumePrecision)}</span>
    </div>
  );
}, (prevProps, nextProps) => {
  // Custom comparison for performance - only re-render when relevant props change
  return (
    prevProps.level.price === nextProps.level.price &&
    prevProps.level.volume === nextProps.level.volume &&
    prevProps.level.total === nextProps.level.total &&
    prevProps.level.changeType === nextProps.level.changeType &&
    prevProps.side === nextProps.side &&
    prevProps.precision === nextProps.precision &&
    prevProps.volumePrecision === nextProps.volumePrecision
  );
});


/**
 * Depth Chart Component (Horizontal visualization)
 */
interface DepthChartProps {
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  theme: OrderBookTheme;
  width: number;
  height: number;
}

const DepthChart: React.FC<DepthChartProps> = ({
  bids,
  asks,
  theme,
  width,
  height,
}) => {
  const padding = { top: 10, right: 10, bottom: 20, left: 10 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  
  // Calculate price range
  const allPrices = [...bids.map(b => b.price), ...asks.map(a => a.price)];
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const priceRange = maxPrice - minPrice || 1;
  
  // Calculate max cumulative volume
  const maxBidTotal = bids.length > 0 ? Math.max(...bids.map(b => b.total)) : 0;
  const maxAskTotal = asks.length > 0 ? Math.max(...asks.map(a => a.total)) : 0;
  const maxTotal = Math.max(maxBidTotal, maxAskTotal) || 1;
  
  // Scale functions
  const scaleX = (price: number) => ((price - minPrice) / priceRange) * chartWidth;
  const scaleY = (total: number) => chartHeight - (total / maxTotal) * chartHeight;
  
  // Generate path for bids (left side, cumulative from right to left)
  const bidPath = useMemo(() => {
    if (bids.length === 0) return '';
    
    const sortedBids = [...bids].sort((a, b) => b.price - a.price);
    let path = `M ${scaleX(sortedBids[0].price)} ${scaleY(sortedBids[0].total)}`;
    
    for (let i = 1; i < sortedBids.length; i++) {
      // Step pattern for order book visualization
      path += ` L ${scaleX(sortedBids[i].price)} ${scaleY(sortedBids[i - 1].total)}`;
      path += ` L ${scaleX(sortedBids[i].price)} ${scaleY(sortedBids[i].total)}`;
    }
    
    // Close the path
    path += ` L ${scaleX(sortedBids[sortedBids.length - 1].price)} ${chartHeight}`;
    path += ` L ${scaleX(sortedBids[0].price)} ${chartHeight} Z`;
    
    return path;
  }, [bids, chartWidth, chartHeight, minPrice, priceRange, maxTotal]);
  
  // Generate path for asks (right side, cumulative from left to right)
  const askPath = useMemo(() => {
    if (asks.length === 0) return '';
    
    const sortedAsks = [...asks].sort((a, b) => a.price - b.price);
    let path = `M ${scaleX(sortedAsks[0].price)} ${scaleY(sortedAsks[0].total)}`;
    
    for (let i = 1; i < sortedAsks.length; i++) {
      path += ` L ${scaleX(sortedAsks[i].price)} ${scaleY(sortedAsks[i - 1].total)}`;
      path += ` L ${scaleX(sortedAsks[i].price)} ${scaleY(sortedAsks[i].total)}`;
    }
    
    // Close the path
    path += ` L ${scaleX(sortedAsks[sortedAsks.length - 1].price)} ${chartHeight}`;
    path += ` L ${scaleX(sortedAsks[0].price)} ${chartHeight} Z`;
    
    return path;
  }, [asks, chartWidth, chartHeight, minPrice, priceRange, maxTotal]);
  
  // Midpoint line
  const midPrice = bids.length > 0 && asks.length > 0
    ? (bids[0].price + asks[0].price) / 2
    : (minPrice + maxPrice) / 2;
  
  return (
    <svg
      className="depth-chart-svg"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
    >
      <g transform={`translate(${padding.left}, ${padding.top})`}>
        {/* Bid area */}
        {bidPath && (
          <path
            d={bidPath}
            className="depth-area-bid"
            style={{
              fill: theme.bidBackgroundColor,
              stroke: theme.bidColor,
            }}
          />
        )}
        
        {/* Ask area */}
        {askPath && (
          <path
            d={askPath}
            className="depth-area-ask"
            style={{
              fill: theme.askBackgroundColor,
              stroke: theme.askColor,
            }}
          />
        )}
        
        {/* Midpoint line */}
        <line
          x1={scaleX(midPrice)}
          y1={0}
          x2={scaleX(midPrice)}
          y2={chartHeight}
          className="depth-midpoint-line"
          style={{ stroke: theme.spreadColor }}
        />
        
        {/* Price labels */}
        <text
          x={0}
          y={chartHeight + 15}
          className="depth-axis-label"
          style={{ fill: theme.textColor }}
        >
          {formatNumber(minPrice, 2)}
        </text>
        <text
          x={chartWidth}
          y={chartHeight + 15}
          className="depth-axis-label"
          textAnchor="end"
          style={{ fill: theme.textColor }}
        >
          {formatNumber(maxPrice, 2)}
        </text>
      </g>
    </svg>
  );
};

/**
 * Main OrderBook Component
 */
const OrderBook: React.FC<OrderBookProps> = ({
  data,
  displayMode = OrderBookDisplayMode.VERTICAL,
  levels = 10,
  precision = 2,
  volumePrecision = 4,
  theme = darkOrderBookTheme,
  onPriceClick,
  // onVolumeClick - reserved for future use
  animateUpdates = true,
  width,
  height,
  autoSize = true,
}) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ width: 300, height: 400 });
  const [currentMode, setCurrentMode] = useState(displayMode);
  const [previousData, setPreviousData] = useState<OrderBookData | null>(null);
  
  // Handle container resize
  useEffect(() => {
    if (!autoSize || !containerRef.current) return;
    
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        setContainerSize({ width: w, height: h });
      }
    });
    
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, [autoSize]);
  
  // Process order book data
  const processedData = useMemo(() => {
    if (!data) return null;
    
    // Limit to specified number of levels
    let bids = data.bids.slice(0, levels);
    let asks = data.asks.slice(0, levels);
    
    // Calculate cumulative totals
    bids = calculateTotals(bids);
    asks = calculateTotals(asks);
    
    // Calculate max volumes for percentage bars
    const maxBidTotal = bids.length > 0 ? bids[bids.length - 1].total : 0;
    const maxAskTotal = asks.length > 0 ? asks[asks.length - 1].total : 0;
    const maxTotal = Math.max(maxBidTotal, maxAskTotal);
    
    // Calculate percentages
    bids = calculatePercentages(bids, maxTotal);
    asks = calculatePercentages(asks, maxTotal);
    
    return { ...data, bids, asks };
  }, [data, levels]);
  
  // Detect changes for animation
  const animatedBids = useMemo(() => {
    if (!processedData || !previousData) {
      return processedData?.bids.map(b => ({ ...b, changeType: PriceLevelChangeType.NONE })) || [];
    }
    return detectChanges(previousData.bids, processedData.bids);
  }, [processedData, previousData]);
  
  const animatedAsks = useMemo(() => {
    if (!processedData || !previousData) {
      return processedData?.asks.map(a => ({ ...a, changeType: PriceLevelChangeType.NONE })) || [];
    }
    return detectChanges(previousData.asks, processedData.asks);
  }, [processedData, previousData]);
  
  // Update previous data for change detection
  useEffect(() => {
    if (processedData) {
      const timer = setTimeout(() => {
        setPreviousData(processedData);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [processedData]);
  
  // Handle price click
  const handlePriceClick = useCallback((price: number, side: 'bid' | 'ask') => {
    onPriceClick?.(price, side);
  }, [onPriceClick]);
  
  // Calculate spread
  const spread = useMemo(() => {
    if (!processedData || processedData.bids.length === 0 || processedData.asks.length === 0) {
      return null;
    }
    const bestBid = processedData.bids[0].price;
    const bestAsk = processedData.asks[0].price;
    const spreadValue = bestAsk - bestBid;
    const spreadPercent = (spreadValue / bestAsk) * 100;
    return { value: spreadValue, percent: spreadPercent };
  }, [processedData]);
  
  // CSS variables for theming
  const containerStyle = {
    '--bg-color': theme.backgroundColor,
    '--text-color': theme.textColor,
    '--border-color': theme.borderColor,
    '--highlight-color': theme.highlightColor,
    '--header-bg-color': theme.headerBackgroundColor,
    '--bid-color': theme.bidColor,
    '--ask-color': theme.askColor,
    '--spread-color': theme.spreadColor,
    backgroundColor: theme.backgroundColor,
    color: theme.textColor,
    width: autoSize ? '100%' : width,
    height: autoSize ? '100%' : height,
  } as React.CSSProperties;
  
  // Render loading state
  if (!data) {
    return (
      <div ref={containerRef} className="orderbook-container" style={containerStyle}>
        <div className="orderbook-loading">
          <div className="orderbook-loading-spinner" />
        </div>
      </div>
    );
  }
  
  // Render empty state
  if (!processedData || (processedData.bids.length === 0 && processedData.asks.length === 0)) {
    return (
      <div ref={containerRef} className="orderbook-container" style={containerStyle}>
        <div className="orderbook-empty">
          <span className="orderbook-empty-icon">📊</span>
          <span className="orderbook-empty-text">{t('layout.orderBookPlaceholder')}</span>
        </div>
      </div>
    );
  }
  
  return (
    <div ref={containerRef} className="orderbook-container" style={containerStyle}>
      {/* Header */}
      <div className="orderbook-header" style={{ backgroundColor: theme.headerBackgroundColor }}>
        <div>
          <span className="orderbook-title">{t('layout.orderBook')}</span>
          {processedData.symbol && (
            <span className="orderbook-symbol"> - {processedData.symbol}</span>
          )}
        </div>
        <div className="orderbook-controls">
          <button
            className={`orderbook-mode-btn ${currentMode === OrderBookDisplayMode.VERTICAL ? 'active' : ''}`}
            onClick={() => setCurrentMode(OrderBookDisplayMode.VERTICAL)}
            title="Vertical View"
          >
            ☰
          </button>
          <button
            className={`orderbook-mode-btn ${currentMode === OrderBookDisplayMode.HORIZONTAL ? 'active' : ''}`}
            onClick={() => setCurrentMode(OrderBookDisplayMode.HORIZONTAL)}
            title="Depth Chart"
          >
            📈
          </button>
          <button
            className={`orderbook-mode-btn ${currentMode === OrderBookDisplayMode.COMBINED ? 'active' : ''}`}
            onClick={() => setCurrentMode(OrderBookDisplayMode.COMBINED)}
            title="Combined View"
          >
            ⊞
          </button>
        </div>
      </div>
      
      {/* Content based on display mode */}
      <div className="orderbook-content">
        {(currentMode === OrderBookDisplayMode.VERTICAL || currentMode === OrderBookDisplayMode.COMBINED) && (
          <div className={`orderbook-vertical ${currentMode === OrderBookDisplayMode.COMBINED ? '' : ''}`}>
            {/* Table Header */}
            <div className="orderbook-table-header" style={{ backgroundColor: theme.headerBackgroundColor }}>
              <span>{t('chart.price')}</span>
              <span>{t('chart.volume')}</span>
              <span>Total</span>
            </div>
            
            {/* Asks (sell orders) - displayed in reverse order */}
            <div className="orderbook-asks">
              {animatedAsks.slice().reverse().map((level) => (
                <PriceLevelRow
                  key={`ask-${level.price}`}
                  level={level}
                  side="ask"
                  precision={precision}
                  volumePrecision={volumePrecision}
                  theme={theme}
                  animateUpdates={animateUpdates}
                  onClick={handlePriceClick}
                />
              ))}
            </div>
            
            {/* Spread */}
            {spread && (
              <div className="orderbook-spread" style={{ color: theme.spreadColor }}>
                <span className="spread-label">Spread:</span>
                <span className="spread-value">{formatNumber(spread.value, precision)}</span>
                <span className="spread-percent">({formatNumber(spread.percent, 2)}%)</span>
              </div>
            )}
            
            {/* Bids (buy orders) */}
            <div className="orderbook-bids">
              {animatedBids.map((level) => (
                <PriceLevelRow
                  key={`bid-${level.price}`}
                  level={level}
                  side="bid"
                  precision={precision}
                  volumePrecision={volumePrecision}
                  theme={theme}
                  animateUpdates={animateUpdates}
                  onClick={handlePriceClick}
                />
              ))}
            </div>
          </div>
        )}
        
        {(currentMode === OrderBookDisplayMode.HORIZONTAL || currentMode === OrderBookDisplayMode.COMBINED) && (
          <div className="orderbook-horizontal">
            <div className="depth-chart-container">
              <DepthChart
                bids={processedData.bids}
                asks={processedData.asks}
                theme={theme}
                width={containerSize.width - 24}
                height={currentMode === OrderBookDisplayMode.COMBINED ? 150 : containerSize.height - 100}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default OrderBook;
