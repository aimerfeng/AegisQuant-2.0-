/**
 * Positions Component
 * 
 * Displays current trading positions with P&L information.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import './Positions.css';

interface Position {
  id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  volume: number;
  entryPrice: number;
  currentPrice: number;
  pnl: number;
  pnlPercent: number;
}

interface PositionsProps {
  positions?: Position[];
}

const Positions: React.FC<PositionsProps> = ({ positions = [] }) => {
  const { t } = useTranslation();

  // Mock data for demonstration
  const mockPositions: Position[] = positions.length > 0 ? positions : [
    { id: '1', symbol: 'BTC/USDT', direction: 'LONG', volume: 0.5, entryPrice: 42150.00, currentPrice: 42580.00, pnl: 215.00, pnlPercent: 1.02 },
    { id: '2', symbol: 'ETH/USDT', direction: 'SHORT', volume: 2.0, entryPrice: 2280.00, currentPrice: 2265.00, pnl: 30.00, pnlPercent: 0.66 },
  ];

  const totalPnl = mockPositions.reduce((sum, p) => sum + p.pnl, 0);

  return (
    <div className="positions-container">
      <div className="positions-header">
        <span className="positions-title">{t('panels.positions', 'Positions')}</span>
        <span className={`total-pnl ${totalPnl >= 0 ? 'profit' : 'loss'}`}>
          {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)} USDT
        </span>
      </div>
      
      {mockPositions.length === 0 ? (
        <div className="positions-empty">
          <span className="empty-icon">💼</span>
          <span>{t('positions.noPositions', 'No open positions')}</span>
        </div>
      ) : (
        <div className="positions-list">
          {mockPositions.map(position => (
            <div key={position.id} className="position-item">
              <div className="position-header">
                <span className="position-symbol">{position.symbol}</span>
                <span className={`position-direction ${position.direction.toLowerCase()}`}>
                  {position.direction}
                </span>
              </div>
              <div className="position-details">
                <div className="detail-row">
                  <span className="label">{t('positions.volume', 'Volume')}:</span>
                  <span className="value">{position.volume}</span>
                </div>
                <div className="detail-row">
                  <span className="label">{t('positions.entry', 'Entry')}:</span>
                  <span className="value">{position.entryPrice.toFixed(2)}</span>
                </div>
                <div className="detail-row">
                  <span className="label">{t('positions.current', 'Current')}:</span>
                  <span className="value">{position.currentPrice.toFixed(2)}</span>
                </div>
                <div className="detail-row">
                  <span className="label">P&L:</span>
                  <span className={`value ${position.pnl >= 0 ? 'profit' : 'loss'}`}>
                    {position.pnl >= 0 ? '+' : ''}{position.pnl.toFixed(2)} ({position.pnlPercent.toFixed(2)}%)
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Positions;
