/**
 * Trades Component
 * 
 * Displays recent trade history.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import './Trades.css';

interface Trade {
  id: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  price: number;
  volume: number;
  time: string;
  pnl?: number;
}

interface TradesProps {
  trades?: Trade[];
}

const Trades: React.FC<TradesProps> = ({ trades = [] }) => {
  const { t } = useTranslation();

  // Mock data for demonstration
  const mockTrades: Trade[] = trades.length > 0 ? trades : [
    { id: '1', symbol: 'BTC/USDT', direction: 'BUY', price: 42150.00, volume: 0.5, time: '14:32:15', pnl: undefined },
    { id: '2', symbol: 'ETH/USDT', direction: 'SELL', price: 2280.00, volume: 2.0, time: '14:28:42', pnl: 45.20 },
    { id: '3', symbol: 'BTC/USDT', direction: 'SELL', price: 42080.00, volume: 0.3, time: '14:15:08', pnl: -12.50 },
    { id: '4', symbol: 'ETH/USDT', direction: 'BUY', price: 2265.00, volume: 1.5, time: '13:58:33', pnl: undefined },
  ];

  return (
    <div className="trades-container">
      <div className="trades-header">
        <span className="trades-title">{t('panels.trades', 'Trades')}</span>
        <span className="trades-count">{mockTrades.length} {t('trades.recent', 'recent')}</span>
      </div>
      
      {mockTrades.length === 0 ? (
        <div className="trades-empty">
          <span className="empty-icon">💹</span>
          <span>{t('trades.noTrades', 'No recent trades')}</span>
        </div>
      ) : (
        <div className="trades-list">
          {mockTrades.map(trade => (
            <div key={trade.id} className="trade-item">
              <div className="trade-main">
                <div className="trade-info">
                  <span className={`trade-direction ${trade.direction.toLowerCase()}`}>
                    {trade.direction}
                  </span>
                  <span className="trade-symbol">{trade.symbol}</span>
                </div>
                <span className="trade-time">{trade.time}</span>
              </div>
              <div className="trade-details">
                <span className="trade-price">{trade.price.toFixed(2)}</span>
                <span className="trade-volume">×{trade.volume}</span>
                {trade.pnl !== undefined && (
                  <span className={`trade-pnl ${trade.pnl >= 0 ? 'profit' : 'loss'}`}>
                    {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Trades;
