/**
 * Titan-Quant Manual Trade Component
 * 
 * Provides manual trading controls during backtest replay:
 * - Market Buy button
 * - Market Sell button
 * - Close All Positions button
 * 
 * Requirements: 6.1
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useIntegration } from '../../hooks/useIntegration';
import { ManualOrderPayload } from '../../types/websocket';
import './ManualTrade.css';

export interface ManualTradeConfig {
  symbol: string;
  volume: number;
}

interface ManualTradeProps {
  config?: ManualTradeConfig;
  onOrderSubmitted?: (order: ManualOrderPayload) => void;
  onCloseAll?: () => void;
}

const DEFAULT_CONFIG: ManualTradeConfig = {
  symbol: 'BTC_USDT',
  volume: 1,
};

const ManualTrade: React.FC<ManualTradeProps> = ({
  config = DEFAULT_CONFIG,
  onOrderSubmitted,
  onCloseAll,
}) => {
  const { t } = useTranslation();
  const { isConnected, submitManualOrder, closeAllPositions } = useIntegration();
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showConfirmCloseAll, setShowConfirmCloseAll] = useState(false);
  const [tradeConfig, setTradeConfig] = useState<ManualTradeConfig>(config);

  const handleBuy = useCallback(async () => {
    if (!isConnected || isSubmitting) return;

    setIsSubmitting(true);
    
    const order: ManualOrderPayload = {
      symbol: tradeConfig.symbol,
      direction: 'LONG',
      offset: 'OPEN',
      price: 0, // Market order - price determined by matching engine
      volume: tradeConfig.volume,
    };

    try {
      await submitManualOrder(order);
      onOrderSubmitted?.(order);
    } catch (error) {
      console.error('Failed to submit buy order:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [isConnected, isSubmitting, tradeConfig, submitManualOrder, onOrderSubmitted]);

  const handleSell = useCallback(async () => {
    if (!isConnected || isSubmitting) return;

    setIsSubmitting(true);
    
    const order: ManualOrderPayload = {
      symbol: tradeConfig.symbol,
      direction: 'SHORT',
      offset: 'OPEN',
      price: 0, // Market order - price determined by matching engine
      volume: tradeConfig.volume,
    };

    try {
      await submitManualOrder(order);
      onOrderSubmitted?.(order);
    } catch (error) {
      console.error('Failed to submit sell order:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [isConnected, isSubmitting, tradeConfig, submitManualOrder, onOrderSubmitted]);

  const handleCloseAll = useCallback(() => {
    if (!isConnected) return;
    
    setShowConfirmCloseAll(true);
  }, [isConnected]);

  const confirmCloseAll = useCallback(async () => {
    if (!isConnected) return;

    try {
      await closeAllPositions();
      setShowConfirmCloseAll(false);
      onCloseAll?.();
    } catch (error) {
      console.error('Failed to close all positions:', error);
      setShowConfirmCloseAll(false);
    }
  }, [isConnected, closeAllPositions, onCloseAll]);

  const cancelCloseAll = useCallback(() => {
    setShowConfirmCloseAll(false);
  }, []);

  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    if (!isNaN(value) && value > 0) {
      setTradeConfig(prev => ({ ...prev, volume: value }));
    }
  }, []);

  const handleSymbolChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setTradeConfig(prev => ({ ...prev, symbol: e.target.value }));
  }, []);

  return (
    <div className="manual-trade">
      {/* Trade Configuration */}
      <div className="trade-config">
        <div className="config-field">
          <label className="config-label">{t('manualTrade.symbol')}</label>
          <input
            type="text"
            className="config-input"
            value={tradeConfig.symbol}
            onChange={handleSymbolChange}
            disabled={!isConnected}
          />
        </div>
        <div className="config-field">
          <label className="config-label">{t('manualTrade.volume')}</label>
          <input
            type="number"
            className="config-input config-input-volume"
            value={tradeConfig.volume}
            onChange={handleVolumeChange}
            min="0.001"
            step="0.1"
            disabled={!isConnected}
          />
        </div>
      </div>

      {/* Trade Buttons */}
      <div className="trade-buttons">
        <button
          className="trade-btn trade-btn-buy"
          onClick={handleBuy}
          disabled={!isConnected || isSubmitting}
          title={t('manualTrade.marketBuy')}
          aria-label={t('manualTrade.marketBuy')}
        >
          <span className="trade-btn-icon">▲</span>
          <span className="trade-btn-text">{t('ui.buy')}</span>
        </button>

        <button
          className="trade-btn trade-btn-sell"
          onClick={handleSell}
          disabled={!isConnected || isSubmitting}
          title={t('manualTrade.marketSell')}
          aria-label={t('manualTrade.marketSell')}
        >
          <span className="trade-btn-icon">▼</span>
          <span className="trade-btn-text">{t('ui.sell')}</span>
        </button>
      </div>

      {/* Close All Button */}
      <div className="close-all-section">
        <button
          className="trade-btn trade-btn-close-all"
          onClick={handleCloseAll}
          disabled={!isConnected}
          title={t('ui.close_all')}
          aria-label={t('ui.close_all')}
        >
          <span className="trade-btn-icon">✕</span>
          <span className="trade-btn-text">{t('ui.close_all')}</span>
        </button>
      </div>

      {/* Confirmation Dialog */}
      {showConfirmCloseAll && (
        <div className="confirm-dialog-overlay">
          <div className="confirm-dialog">
            <h4 className="confirm-title">{t('manualTrade.confirmCloseAll')}</h4>
            <p className="confirm-message">{t('manualTrade.closeAllWarning')}</p>
            <div className="confirm-buttons">
              <button
                className="confirm-btn confirm-btn-cancel"
                onClick={cancelCloseAll}
              >
                {t('ui.cancel')}
              </button>
              <button
                className="confirm-btn confirm-btn-confirm"
                onClick={confirmCloseAll}
              >
                {t('ui.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ManualTrade;
