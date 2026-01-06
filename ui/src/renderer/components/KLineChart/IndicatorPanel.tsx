/**
 * Indicator Panel Component
 * 
 * Provides a panel for managing technical indicators:
 * - MA (Moving Average)
 * - EMA (Exponential Moving Average)
 * - MACD
 * - RSI
 * - Bollinger Bands
 * 
 * Supports drag-and-drop adding of indicators.
 * Requirements: 3.3
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Indicator,
  IndicatorType,
  MAConfig,
  MACDConfig,
  RSIConfig,
  BollingerConfig,
} from './types';
import {
  generateId,
  DEFAULT_MA_CONFIG,
  DEFAULT_EMA_CONFIG,
  DEFAULT_MACD_CONFIG,
  DEFAULT_RSI_CONFIG,
  DEFAULT_BOLLINGER_CONFIG,
} from './utils';
import './IndicatorPanel.css';

interface IndicatorPanelProps {
  indicators: Indicator[];
  onIndicatorAdd: (indicator: Indicator) => void;
  onIndicatorRemove: (indicatorId: string) => void;
  onIndicatorUpdate: (indicator: Indicator) => void;
}

interface IndicatorOption {
  type: IndicatorType;
  name: string;
  icon: string;
  defaultConfig: Omit<Indicator, 'id'>;
}

const indicatorOptions: IndicatorOption[] = [
  { type: IndicatorType.MA, name: 'MA', icon: '📈', defaultConfig: DEFAULT_MA_CONFIG },
  { type: IndicatorType.EMA, name: 'EMA', icon: '📉', defaultConfig: DEFAULT_EMA_CONFIG },
  { type: IndicatorType.MACD, name: 'MACD', icon: '📊', defaultConfig: DEFAULT_MACD_CONFIG },
  { type: IndicatorType.RSI, name: 'RSI', icon: '📏', defaultConfig: DEFAULT_RSI_CONFIG },
  { type: IndicatorType.BOLLINGER, name: 'BB', icon: '🎯', defaultConfig: DEFAULT_BOLLINGER_CONFIG },
];

/**
 * Indicator Panel Component
 */
const IndicatorPanel: React.FC<IndicatorPanelProps> = ({
  indicators,
  onIndicatorAdd,
  onIndicatorRemove,
  onIndicatorUpdate,
}) => {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const [editingIndicator, setEditingIndicator] = useState<string | null>(null);
  const [draggedIndicator, setDraggedIndicator] = useState<IndicatorType | null>(null);

  // Handle adding a new indicator
  const handleAddIndicator = useCallback((option: IndicatorOption) => {
    const newIndicator: Indicator = {
      ...option.defaultConfig,
      id: generateId(),
    } as Indicator;
    onIndicatorAdd(newIndicator);
  }, [onIndicatorAdd]);

  // Handle drag start
  const handleDragStart = useCallback((e: React.DragEvent, type: IndicatorType) => {
    setDraggedIndicator(type);
    e.dataTransfer.setData('indicatorType', type);
    e.dataTransfer.effectAllowed = 'copy';
  }, []);

  // Handle drag end
  const handleDragEnd = useCallback(() => {
    setDraggedIndicator(null);
  }, []);

  // Handle drop on chart (this would be handled by the chart container)
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const type = e.dataTransfer.getData('indicatorType') as IndicatorType;
    const option = indicatorOptions.find((o) => o.type === type);
    if (option) {
      handleAddIndicator(option);
    }
    setDraggedIndicator(null);
  }, [handleAddIndicator]);

  // Handle toggle visibility
  const handleToggleVisibility = useCallback((indicator: Indicator) => {
    onIndicatorUpdate({ ...indicator, visible: !indicator.visible });
  }, [onIndicatorUpdate]);

  // Handle parameter change
  const handleParamChange = useCallback((indicator: Indicator, param: string, value: number | string) => {
    const updated = { ...indicator, [param]: value };
    onIndicatorUpdate(updated as Indicator);
  }, [onIndicatorUpdate]);

  // Render indicator settings
  const renderIndicatorSettings = (indicator: Indicator) => {
    if (editingIndicator !== indicator.id) return null;

    switch (indicator.type) {
      case IndicatorType.MA:
      case IndicatorType.EMA: {
        const config = indicator as MAConfig;
        return (
          <div className="indicator-settings">
            <div className="setting-row">
              <label>{t('chart.period')}</label>
              <input
                type="number"
                value={config.period}
                min={1}
                max={200}
                onChange={(e) => handleParamChange(indicator, 'period', parseInt(e.target.value) || 20)}
              />
            </div>
            <div className="setting-row">
              <label>{t('chart.color')}</label>
              <input
                type="color"
                value={config.color}
                onChange={(e) => handleParamChange(indicator, 'color', e.target.value)}
              />
            </div>
          </div>
        );
      }

      case IndicatorType.MACD: {
        const config = indicator as MACDConfig;
        return (
          <div className="indicator-settings">
            <div className="setting-row">
              <label>Fast</label>
              <input
                type="number"
                value={config.fastPeriod}
                min={1}
                max={50}
                onChange={(e) => handleParamChange(indicator, 'fastPeriod', parseInt(e.target.value) || 12)}
              />
            </div>
            <div className="setting-row">
              <label>Slow</label>
              <input
                type="number"
                value={config.slowPeriod}
                min={1}
                max={100}
                onChange={(e) => handleParamChange(indicator, 'slowPeriod', parseInt(e.target.value) || 26)}
              />
            </div>
            <div className="setting-row">
              <label>Signal</label>
              <input
                type="number"
                value={config.signalPeriod}
                min={1}
                max={50}
                onChange={(e) => handleParamChange(indicator, 'signalPeriod', parseInt(e.target.value) || 9)}
              />
            </div>
          </div>
        );
      }

      case IndicatorType.RSI: {
        const config = indicator as RSIConfig;
        return (
          <div className="indicator-settings">
            <div className="setting-row">
              <label>{t('chart.period')}</label>
              <input
                type="number"
                value={config.period}
                min={1}
                max={100}
                onChange={(e) => handleParamChange(indicator, 'period', parseInt(e.target.value) || 14)}
              />
            </div>
            <div className="setting-row">
              <label>Overbought</label>
              <input
                type="number"
                value={config.overbought}
                min={50}
                max={100}
                onChange={(e) => handleParamChange(indicator, 'overbought', parseInt(e.target.value) || 70)}
              />
            </div>
            <div className="setting-row">
              <label>Oversold</label>
              <input
                type="number"
                value={config.oversold}
                min={0}
                max={50}
                onChange={(e) => handleParamChange(indicator, 'oversold', parseInt(e.target.value) || 30)}
              />
            </div>
            <div className="setting-row">
              <label>{t('chart.color')}</label>
              <input
                type="color"
                value={config.lineColor}
                onChange={(e) => handleParamChange(indicator, 'lineColor', e.target.value)}
              />
            </div>
          </div>
        );
      }

      case IndicatorType.BOLLINGER: {
        const config = indicator as BollingerConfig;
        return (
          <div className="indicator-settings">
            <div className="setting-row">
              <label>{t('chart.period')}</label>
              <input
                type="number"
                value={config.period}
                min={1}
                max={100}
                onChange={(e) => handleParamChange(indicator, 'period', parseInt(e.target.value) || 20)}
              />
            </div>
            <div className="setting-row">
              <label>Std Dev</label>
              <input
                type="number"
                value={config.stdDev}
                min={0.5}
                max={5}
                step={0.5}
                onChange={(e) => handleParamChange(indicator, 'stdDev', parseFloat(e.target.value) || 2)}
              />
            </div>
            <div className="setting-row">
              <label>Upper</label>
              <input
                type="color"
                value={config.upperColor}
                onChange={(e) => handleParamChange(indicator, 'upperColor', e.target.value)}
              />
            </div>
            <div className="setting-row">
              <label>Middle</label>
              <input
                type="color"
                value={config.middleColor}
                onChange={(e) => handleParamChange(indicator, 'middleColor', e.target.value)}
              />
            </div>
          </div>
        );
      }

      default:
        return null;
    }
  };

  // Get indicator display name
  const getIndicatorDisplayName = (indicator: Indicator): string => {
    switch (indicator.type) {
      case IndicatorType.MA:
        return `MA(${(indicator as MAConfig).period})`;
      case IndicatorType.EMA:
        return `EMA(${(indicator as MAConfig).period})`;
      case IndicatorType.MACD: {
        const config = indicator as MACDConfig;
        return `MACD(${config.fastPeriod},${config.slowPeriod},${config.signalPeriod})`;
      }
      case IndicatorType.RSI:
        return `RSI(${(indicator as RSIConfig).period})`;
      case IndicatorType.BOLLINGER: {
        const config = indicator as BollingerConfig;
        return `BB(${config.period},${config.stdDev})`;
      }
    }
  };

  // Get indicator color
  const getIndicatorColor = (indicator: Indicator): string => {
    switch (indicator.type) {
      case IndicatorType.MA:
      case IndicatorType.EMA:
        return (indicator as MAConfig).color;
      case IndicatorType.MACD:
        return (indicator as MACDConfig).macdColor;
      case IndicatorType.RSI:
        return (indicator as RSIConfig).lineColor;
      case IndicatorType.BOLLINGER:
        return (indicator as BollingerConfig).middleColor;
    }
  };

  return (
    <div className={`indicator-panel ${isExpanded ? 'expanded' : ''}`}>
      {/* Panel header */}
      <div className="panel-header" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="panel-title">{t('chart.indicators')}</span>
        <span className="panel-toggle">{isExpanded ? '▼' : '▶'}</span>
      </div>

      {/* Panel content */}
      {isExpanded && (
        <div className="panel-content">
          {/* Available indicators (draggable) */}
          <div className="indicator-options">
            <div className="options-label">{t('chart.addIndicator')}</div>
            <div className="options-grid">
              {indicatorOptions.map((option) => (
                <div
                  key={option.type}
                  className={`indicator-option ${draggedIndicator === option.type ? 'dragging' : ''}`}
                  draggable
                  onDragStart={(e) => handleDragStart(e, option.type)}
                  onDragEnd={handleDragEnd}
                  onClick={() => handleAddIndicator(option)}
                  title={t(`chart.${option.type}`)}
                >
                  <span className="option-icon">{option.icon}</span>
                  <span className="option-name">{option.name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Active indicators */}
          {indicators.length > 0 && (
            <div className="active-indicators">
              <div className="section-label">Active</div>
              {indicators.map((indicator) => (
                <div key={indicator.id} className="indicator-item">
                  <div className="indicator-header">
                    <div
                      className="color-dot"
                      style={{ backgroundColor: getIndicatorColor(indicator) }}
                    />
                    <span className="indicator-name">{getIndicatorDisplayName(indicator)}</span>
                    <div className="indicator-actions">
                      <button
                        className={`action-btn visibility ${indicator.visible ? 'visible' : 'hidden'}`}
                        onClick={() => handleToggleVisibility(indicator)}
                        title={indicator.visible ? 'Hide' : 'Show'}
                      >
                        {indicator.visible ? '👁️' : '👁️‍🗨️'}
                      </button>
                      <button
                        className={`action-btn settings ${editingIndicator === indicator.id ? 'active' : ''}`}
                        onClick={() => setEditingIndicator(
                          editingIndicator === indicator.id ? null : indicator.id
                        )}
                        title="Settings"
                      >
                        ⚙️
                      </button>
                      <button
                        className="action-btn remove"
                        onClick={() => onIndicatorRemove(indicator.id)}
                        title={t('chart.removeIndicator')}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                  {renderIndicatorSettings(indicator)}
                </div>
              ))}
            </div>
          )}

          {/* Empty state */}
          {indicators.length === 0 && (
            <div className="empty-state">
              <span>Drag or click to add indicators</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default IndicatorPanel;
