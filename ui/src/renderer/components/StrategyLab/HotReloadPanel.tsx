/**
 * Titan-Quant Hot Reload Panel Component
 * 
 * UI for strategy hot reload functionality.
 * Features:
 * - Reload policy selection (Reset, Preserve, Selective)
 * - Variable selection for selective mode
 * - Reload history and rollback
 * 
 * Requirements: 8.3
 */

import React, { useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useConnectionStore } from '../../stores/connectionStore';
import { MessageType } from '../../types/websocket';
import { HotReloadPanelProps, HotReloadPolicy, ReloadResult } from './types';
import './HotReloadPanel.css';

/**
 * Policy option configuration
 */
interface PolicyOption {
  policy: HotReloadPolicy;
  icon: string;
  titleKey: string;
  descKey: string;
}

const POLICY_OPTIONS: PolicyOption[] = [
  {
    policy: HotReloadPolicy.RESET,
    icon: '🔄',
    titleKey: 'strategyLab.policyReset',
    descKey: 'strategyLab.policyResetDesc',
  },
  {
    policy: HotReloadPolicy.PRESERVE,
    icon: '💾',
    titleKey: 'strategyLab.policyPreserve',
    descKey: 'strategyLab.policyPreserveDesc',
  },
  {
    policy: HotReloadPolicy.SELECTIVE,
    icon: '✏️',
    titleKey: 'strategyLab.policySelective',
    descKey: 'strategyLab.policySelectiveDesc',
  },
];

/**
 * Mock state variables for demonstration
 * In production, these would come from the backend
 */
const MOCK_STATE_VARIABLES = [
  { name: 'fast_ma', type: 'float', value: 0.0 },
  { name: 'slow_ma', type: 'float', value: 0.0 },
  { name: 'position', type: 'int', value: 0 },
  { name: 'entry_price', type: 'float', value: 0.0 },
  { name: 'trade_count', type: 'int', value: 0 },
  { name: 'last_signal', type: 'str', value: 'none' },
];

/**
 * Hot Reload Panel Component
 */
const HotReloadPanel: React.FC<HotReloadPanelProps> = ({
  strategyId,
  isReloading = false,
  lastReloadResult,
  onReload,
  onRollback,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const { wsService, connectionState } = useConnectionStore();
  
  const [selectedPolicy, setSelectedPolicy] = useState<HotReloadPolicy>(HotReloadPolicy.RESET);
  const [selectedVariables, setSelectedVariables] = useState<Set<string>>(new Set());
  const [showVariableSelector, setShowVariableSelector] = useState(false);
  const [localIsReloading, setLocalIsReloading] = useState(false);

  const isConnected = connectionState === 'connected';
  const canReload = strategyId && isConnected && !disabled && !isReloading && !localIsReloading;

  // Handle policy selection
  const handlePolicyChange = useCallback((policy: HotReloadPolicy) => {
    setSelectedPolicy(policy);
    if (policy === HotReloadPolicy.SELECTIVE) {
      setShowVariableSelector(true);
    } else {
      setShowVariableSelector(false);
      setSelectedVariables(new Set());
    }
  }, []);

  // Handle variable selection toggle
  const handleVariableToggle = useCallback((varName: string) => {
    setSelectedVariables(prev => {
      const newSet = new Set(prev);
      if (newSet.has(varName)) {
        newSet.delete(varName);
      } else {
        newSet.add(varName);
      }
      return newSet;
    });
  }, []);

  // Select all variables
  const handleSelectAll = useCallback(() => {
    setSelectedVariables(new Set(MOCK_STATE_VARIABLES.map(v => v.name)));
  }, []);

  // Deselect all variables
  const handleDeselectAll = useCallback(() => {
    setSelectedVariables(new Set());
  }, []);

  // Handle reload action
  const handleReload = useCallback(async () => {
    if (!canReload) return;

    setLocalIsReloading(true);

    try {
      // Send reload request via WebSocket
      if (wsService) {
        wsService.send(MessageType.RELOAD_STRATEGY, {
          strategy_id: strategyId,
          policy: selectedPolicy,
          preserve_vars: selectedPolicy === HotReloadPolicy.SELECTIVE
            ? Array.from(selectedVariables)
            : undefined,
        });
      }

      // Call the onReload callback
      onReload?.(
        selectedPolicy,
        selectedPolicy === HotReloadPolicy.SELECTIVE
          ? Array.from(selectedVariables)
          : undefined
      );
    } finally {
      // Reset loading state after a delay (in production, this would be handled by response)
      setTimeout(() => {
        setLocalIsReloading(false);
      }, 1000);
    }
  }, [canReload, wsService, strategyId, selectedPolicy, selectedVariables, onReload]);

  // Handle rollback action
  const handleRollback = useCallback(() => {
    if (!strategyId || !isConnected || disabled) return;

    if (wsService) {
      wsService.send(MessageType.RELOAD_STRATEGY, {
        strategy_id: strategyId,
        action: 'rollback',
      });
    }

    onRollback?.();
  }, [strategyId, isConnected, disabled, wsService, onRollback]);

  // Format timestamp for display
  const formatTimestamp = useCallback((timestamp?: number) => {
    if (!timestamp) return '--';
    return new Date(timestamp).toLocaleString();
  }, []);

  // Determine result status styling
  const resultStatusClass = useMemo(() => {
    if (!lastReloadResult) return '';
    return lastReloadResult.success ? 'success' : 'error';
  }, [lastReloadResult]);

  return (
    <div className="hot-reload-panel">
      <div className="hot-reload-header">
        <h3 className="hot-reload-title">{t('strategyLab.hotReload')}</h3>
        {strategyId && (
          <span className="hot-reload-strategy-id">{strategyId}</span>
        )}
      </div>

      {!strategyId ? (
        <div className="hot-reload-empty">
          <p>{t('strategyLab.selectStrategy')}</p>
        </div>
      ) : (
        <>
          {/* Policy Selection */}
          <div className="hot-reload-section">
            <h4 className="section-title">{t('strategyLab.reloadPolicy')}</h4>
            <div className="policy-options">
              {POLICY_OPTIONS.map(option => (
                <button
                  key={option.policy}
                  className={`policy-option ${selectedPolicy === option.policy ? 'selected' : ''}`}
                  onClick={() => handlePolicyChange(option.policy)}
                  disabled={disabled || isReloading || localIsReloading}
                >
                  <span className="policy-icon">{option.icon}</span>
                  <div className="policy-content">
                    <span className="policy-title">{t(option.titleKey)}</span>
                    <span className="policy-desc">{t(option.descKey)}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Variable Selector (for Selective mode) */}
          {showVariableSelector && (
            <div className="hot-reload-section">
              <div className="section-header">
                <h4 className="section-title">{t('strategyLab.selectVariables')}</h4>
                <div className="section-actions">
                  <button
                    className="section-action-btn"
                    onClick={handleSelectAll}
                    disabled={disabled}
                  >
                    Select All
                  </button>
                  <button
                    className="section-action-btn"
                    onClick={handleDeselectAll}
                    disabled={disabled}
                  >
                    Deselect All
                  </button>
                </div>
              </div>
              <div className="variable-list">
                {MOCK_STATE_VARIABLES.map(variable => (
                  <label
                    key={variable.name}
                    className={`variable-item ${selectedVariables.has(variable.name) ? 'selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedVariables.has(variable.name)}
                      onChange={() => handleVariableToggle(variable.name)}
                      disabled={disabled}
                    />
                    <span className="variable-name">{variable.name}</span>
                    <span className="variable-type">{variable.type}</span>
                    <span className="variable-value">{String(variable.value)}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="hot-reload-actions">
            <button
              className={`reload-btn ${localIsReloading || isReloading ? 'loading' : ''}`}
              onClick={handleReload}
              disabled={!canReload}
            >
              {localIsReloading || isReloading ? (
                <>
                  <span className="loading-spinner">⟳</span>
                  {t('strategyLab.reloading')}
                </>
              ) : (
                <>
                  🔄 {t('strategyLab.reload')}
                </>
              )}
            </button>
            <button
              className="rollback-btn"
              onClick={handleRollback}
              disabled={!strategyId || !isConnected || disabled || !lastReloadResult}
              title={t('strategyLab.rollback')}
            >
              ↩ {t('strategyLab.rollback')}
            </button>
          </div>

          {/* Last Reload Result */}
          {lastReloadResult && (
            <div className={`hot-reload-result ${resultStatusClass}`}>
              <div className="result-header">
                <span className="result-status">
                  {lastReloadResult.success ? '✓' : '✗'}
                  {lastReloadResult.success
                    ? t('strategyLab.reloadSuccess')
                    : t('strategyLab.reloadFailed')}
                </span>
                <span className="result-policy">{lastReloadResult.policy}</span>
              </div>
              
              {lastReloadResult.errorMessage && (
                <p className="result-error">{lastReloadResult.errorMessage}</p>
              )}

              {lastReloadResult.preservedVariables.length > 0 && (
                <div className="result-vars">
                  <span className="vars-label">{t('strategyLab.preservedVars')}:</span>
                  <span className="vars-list">
                    {lastReloadResult.preservedVariables.join(', ')}
                  </span>
                </div>
              )}

              {lastReloadResult.resetVariables.length > 0 && (
                <div className="result-vars">
                  <span className="vars-label">{t('strategyLab.resetVars')}:</span>
                  <span className="vars-list">
                    {lastReloadResult.resetVariables.join(', ')}
                  </span>
                </div>
              )}
            </div>
          )}

          {!lastReloadResult && (
            <div className="hot-reload-no-history">
              <p>{t('strategyLab.noReloadHistory')}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default HotReloadPanel;
