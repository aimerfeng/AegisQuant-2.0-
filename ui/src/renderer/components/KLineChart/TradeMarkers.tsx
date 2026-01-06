/**
 * Trade Markers Component
 * 
 * Displays trade entry/exit markers on the K-Line chart with:
 * - Arrow markers for open/close positions
 * - Hover tooltips showing P&L details
 * - Color coding for long/short and profit/loss
 * 
 * Requirements: 3.4, 3.5
 */

import React, { useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Time, ISeriesApi, SeriesMarker } from 'lightweight-charts';
import { TradeMarker, TradeDetails, ChartTheme } from './types';
import { formatPrice, formatPercent } from './utils';
import './TradeMarkers.css';

interface TradeMarkersProps {
  markers: TradeMarker[];
  candlestickSeries: ISeriesApi<'Candlestick'> | null;
  theme: ChartTheme;
  onMarkerHover?: (marker: TradeMarker | null) => void;
  onMarkerClick?: (marker: TradeMarker) => void;
  showMarkers?: boolean;
  onToggleMarkers?: (show: boolean) => void;
}

/**
 * Trade Markers Component
 */
const TradeMarkers: React.FC<TradeMarkersProps> = ({
  markers,
  candlestickSeries,
  theme,
  onMarkerHover,
  onMarkerClick,
  showMarkers = true,
  onToggleMarkers,
}) => {
  const { t } = useTranslation();
  const [hoveredMarker, setHoveredMarker] = useState<TradeMarker | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });

  // Convert markers to series markers format
  const seriesMarkers = useMemo((): SeriesMarker<Time>[] => {
    if (!showMarkers) return [];

    return markers.map((marker) => {
      // Determine marker appearance based on trade details
      const details = marker.tradeDetails;
      let color = marker.color;
      let shape = marker.shape;
      let position = marker.position;

      if (details) {
        // Color based on direction
        if (details.direction === 'LONG') {
          color = details.action === 'OPEN' ? theme.upColor : theme.downColor;
          position = details.action === 'OPEN' ? 'belowBar' : 'aboveBar';
          shape = details.action === 'OPEN' ? 'arrowUp' : 'arrowDown';
        } else {
          color = details.action === 'OPEN' ? theme.downColor : theme.upColor;
          position = details.action === 'OPEN' ? 'aboveBar' : 'belowBar';
          shape = details.action === 'OPEN' ? 'arrowDown' : 'arrowUp';
        }

        // Override color for close positions based on P&L
        if (details.action === 'CLOSE' && details.pnl !== undefined) {
          color = details.pnl >= 0 ? theme.upColor : theme.downColor;
        }
      }

      return {
        time: marker.time,
        position,
        color,
        shape,
        text: marker.text,
        size: marker.size || 1,
        id: marker.id,
      };
    });
  }, [markers, showMarkers, theme]);

  // Update series markers when they change
  React.useEffect(() => {
    if (candlestickSeries && seriesMarkers.length > 0) {
      candlestickSeries.setMarkers(seriesMarkers);
    } else if (candlestickSeries) {
      candlestickSeries.setMarkers([]);
    }
  }, [candlestickSeries, seriesMarkers]);

  // Handle marker hover
  const handleMarkerHover = useCallback((marker: TradeMarker | null, x?: number, y?: number) => {
    setHoveredMarker(marker);
    if (marker && x !== undefined && y !== undefined) {
      setTooltipPosition({ x, y });
    }
    onMarkerHover?.(marker);
  }, [onMarkerHover]);

  // Calculate trade statistics
  const tradeStats = useMemo(() => {
    const closeTrades = markers.filter(m => m.tradeDetails?.action === 'CLOSE' && m.tradeDetails?.pnl !== undefined);
    
    if (closeTrades.length === 0) return null;

    const totalPnl = closeTrades.reduce((sum, m) => sum + (m.tradeDetails?.pnl || 0), 0);
    const winningTrades = closeTrades.filter(m => (m.tradeDetails?.pnl || 0) >= 0);
    const winRate = closeTrades.length > 0 ? winningTrades.length / closeTrades.length : 0;

    return {
      totalTrades: closeTrades.length,
      totalPnl,
      winRate,
      winningTrades: winningTrades.length,
      losingTrades: closeTrades.length - winningTrades.length,
    };
  }, [markers]);

  // Render tooltip
  const renderTooltip = () => {
    if (!hoveredMarker?.tradeDetails) return null;

    const details = hoveredMarker.tradeDetails;
    const isProfitable = (details.pnl || 0) >= 0;

    return (
      <div
        className="trade-tooltip"
        style={{
          left: tooltipPosition.x + 15,
          top: tooltipPosition.y - 10,
        }}
      >
        <div className="tooltip-header">
          <span className={`direction-badge ${details.direction.toLowerCase()}`}>
            {t(`chart.${details.direction.toLowerCase()}`)}
          </span>
          <span className={`action-badge ${details.action.toLowerCase()}`}>
            {t(`chart.${details.action === 'OPEN' ? 'openPosition' : 'closePosition'}`)}
          </span>
          {details.isManual && (
            <span className="manual-badge">{t('chart.manualTrade')}</span>
          )}
        </div>

        <div className="tooltip-body">
          <div className="tooltip-row">
            <span className="label">{t('chart.price')}:</span>
            <span className="value">{formatPrice(details.price)}</span>
          </div>
          <div className="tooltip-row">
            <span className="label">{t('chart.volume')}:</span>
            <span className="value">{details.volume}</span>
          </div>
          
          {details.pnl !== undefined && (
            <div className="tooltip-row pnl-row">
              <span className="label">{t('chart.pnl')}:</span>
              <span className={`value ${isProfitable ? 'profit' : 'loss'}`}>
                {isProfitable ? '+' : ''}{formatPrice(details.pnl)}
                {details.pnlPercent !== undefined && (
                  <span className="percent">
                    ({isProfitable ? '+' : ''}{formatPercent(details.pnlPercent)})
                  </span>
                )}
              </span>
            </div>
          )}

          {details.commission !== undefined && (
            <div className="tooltip-row">
              <span className="label">{t('chart.commission')}:</span>
              <span className="value">-{formatPrice(details.commission)}</span>
            </div>
          )}

          <div className="tooltip-row time-row">
            <span className="label">{t('chart.time')}:</span>
            <span className="value">{details.timestamp}</span>
          </div>
        </div>

        {/* Trade ID for reference */}
        <div className="tooltip-footer">
          <span className="trade-id">ID: {details.tradeId}</span>
        </div>
      </div>
    );
  };

  // Render trade statistics summary
  const renderStats = () => {
    if (!tradeStats) return null;

    return (
      <div className="trade-stats">
        <div className="stat-item">
          <span className="stat-label">Trades</span>
          <span className="stat-value">{tradeStats.totalTrades}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Win Rate</span>
          <span className="stat-value">{formatPercent(tradeStats.winRate)}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Total P&L</span>
          <span className={`stat-value ${tradeStats.totalPnl >= 0 ? 'profit' : 'loss'}`}>
            {tradeStats.totalPnl >= 0 ? '+' : ''}{formatPrice(tradeStats.totalPnl)}
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="trade-markers-container">
      {/* Toggle button */}
      <div className="markers-toggle">
        <button
          className={`toggle-btn ${showMarkers ? 'active' : ''}`}
          onClick={() => onToggleMarkers?.(!showMarkers)}
          title={showMarkers ? t('chart.hideMarkers') : t('chart.showMarkers')}
        >
          {showMarkers ? '🏷️' : '🏷️'}
          <span className="toggle-label">
            {showMarkers ? t('chart.hideMarkers') : t('chart.showMarkers')}
          </span>
        </button>
        {showMarkers && markers.length > 0 && (
          <span className="marker-count">{markers.length}</span>
        )}
      </div>

      {/* Trade statistics */}
      {showMarkers && renderStats()}

      {/* Tooltip */}
      {renderTooltip()}
    </div>
  );
};

/**
 * Create trade markers from trade records
 */
export function createTradeMarkers(
  trades: Array<{
    tradeId: string;
    symbol: string;
    direction: 'LONG' | 'SHORT';
    action: 'OPEN' | 'CLOSE';
    price: number;
    volume: number;
    timestamp: string;
    pnl?: number;
    pnlPercent?: number;
    commission?: number;
    isManual?: boolean;
  }>,
  theme: ChartTheme
): TradeMarker[] {
  return trades.map((trade) => {
    const isLong = trade.direction === 'LONG';
    const isOpen = trade.action === 'OPEN';
    
    // Determine marker appearance
    let color: string;
    let shape: 'arrowUp' | 'arrowDown';
    let position: 'aboveBar' | 'belowBar';

    if (isLong) {
      color = isOpen ? theme.upColor : theme.downColor;
      shape = isOpen ? 'arrowUp' : 'arrowDown';
      position = isOpen ? 'belowBar' : 'aboveBar';
    } else {
      color = isOpen ? theme.downColor : theme.upColor;
      shape = isOpen ? 'arrowDown' : 'arrowUp';
      position = isOpen ? 'aboveBar' : 'belowBar';
    }

    // Override color for close positions based on P&L
    if (!isOpen && trade.pnl !== undefined) {
      color = trade.pnl >= 0 ? theme.upColor : theme.downColor;
    }

    return {
      id: trade.tradeId,
      time: new Date(trade.timestamp).getTime() / 1000 as Time,
      position,
      color,
      shape,
      text: isOpen ? 'O' : 'C',
      size: 1,
      tradeDetails: {
        tradeId: trade.tradeId,
        direction: trade.direction,
        action: trade.action,
        price: trade.price,
        volume: trade.volume,
        pnl: trade.pnl,
        pnlPercent: trade.pnlPercent,
        commission: trade.commission,
        timestamp: trade.timestamp,
        isManual: trade.isManual,
      },
    };
  });
}

export default TradeMarkers;
