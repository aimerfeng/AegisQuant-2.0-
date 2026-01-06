/**
 * Titan-Quant Strategy Lab Component
 * 
 * Main Strategy IDE component combining:
 * - Code Editor (Monaco Editor with Python support)
 * - Parameter Panel (Dynamic form generation)
 * - Hot Reload Panel (Strategy reload functionality)
 * 
 * Requirements: 8.1, 8.2, 8.3
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useConnectionStore } from '../../stores/connectionStore';
import { MessageType } from '../../types/websocket';
import CodeEditor from './CodeEditor';
import ParamPanel from './ParamPanel';
import HotReloadPanel from './HotReloadPanel';
import {
  StrategyLabProps,
  StrategyParameter,
  StrategyMetadata,
  ReloadResult,
  HotReloadPolicy,
  STRATEGY_TEMPLATE_SNIPPETS,
} from './types';
import './StrategyLab.css';

/**
 * Tab type for the strategy lab panels
 */
type TabType = 'editor' | 'params' | 'reload';

/**
 * Mock strategy data for demonstration
 * In production, this would come from the backend
 */
const MOCK_STRATEGIES: StrategyMetadata[] = [
  {
    strategyId: 'strategy-001',
    name: 'MA Crossover Strategy',
    className: 'MACrossoverStrategy',
    filePath: 'strategies/ma_crossover.py',
    parameters: [
      {
        name: 'fast_period',
        paramType: 'int',
        defaultValue: 10,
        currentValue: 10,
        minValue: 1,
        maxValue: 100,
        uiWidget: 'slider',
        description: '[Indicator] Fast moving average period',
      },
      {
        name: 'slow_period',
        paramType: 'int',
        defaultValue: 20,
        currentValue: 20,
        minValue: 5,
        maxValue: 200,
        uiWidget: 'slider',
        description: '[Indicator] Slow moving average period',
      },
      {
        name: 'volume',
        paramType: 'float',
        defaultValue: 1.0,
        currentValue: 1.0,
        minValue: 0.1,
        maxValue: 100,
        step: 0.1,
        uiWidget: 'slider',
        description: '[Trading] Trade volume per signal',
      },
      {
        name: 'stop_loss',
        paramType: 'float',
        defaultValue: 0.02,
        currentValue: 0.02,
        minValue: 0.001,
        maxValue: 0.1,
        step: 0.001,
        uiWidget: 'input',
        description: '[Risk] Stop loss percentage',
      },
      {
        name: 'use_trailing_stop',
        paramType: 'bool',
        defaultValue: false,
        currentValue: false,
        uiWidget: 'checkbox',
        description: '[Risk] Enable trailing stop loss',
      },
    ],
    checksum: 'abc123',
    createdAt: Date.now() - 86400000,
    updatedAt: Date.now(),
  },
];

/**
 * Strategy Lab Component
 */
const StrategyLab: React.FC<StrategyLabProps> = ({
  initialStrategyId,
  onStrategyChange,
}) => {
  const { t } = useTranslation();
  const { wsService, connectionState } = useConnectionStore();
  
  // State
  const [activeTab, setActiveTab] = useState<TabType>('editor');
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | undefined>(initialStrategyId);
  const [strategies, setStrategies] = useState<StrategyMetadata[]>(MOCK_STRATEGIES);
  const [codeContent, setCodeContent] = useState<string>(STRATEGY_TEMPLATE_SNIPPETS.ctaTemplate);
  const [isCodeDirty, setIsCodeDirty] = useState(false);
  const [isReloading, setIsReloading] = useState(false);
  const [lastReloadResult, setLastReloadResult] = useState<ReloadResult | undefined>();
  const [cursorPosition, setCursorPosition] = useState({ line: 1, column: 1 });

  const isConnected = connectionState === 'connected';
  const selectedStrategy = strategies.find(s => s.strategyId === selectedStrategyId);

  // Handle strategy selection
  const handleStrategySelect = useCallback((strategyId: string) => {
    if (isCodeDirty) {
      // In production, show confirmation dialog
      const confirm = window.confirm(t('strategyLab.unsavedChanges'));
      if (!confirm) return;
    }

    setSelectedStrategyId(strategyId);
    setIsCodeDirty(false);
    setLastReloadResult(undefined);
    onStrategyChange?.(strategyId);

    // Load strategy code (mock)
    const strategy = strategies.find(s => s.strategyId === strategyId);
    if (strategy) {
      // In production, fetch code from backend
      setCodeContent(STRATEGY_TEMPLATE_SNIPPETS.ctaTemplate);
    }
  }, [isCodeDirty, strategies, onStrategyChange, t]);

  // Handle code change
  const handleCodeChange = useCallback((content: string) => {
    setCodeContent(content);
    setIsCodeDirty(true);
  }, []);

  // Handle code save
  const handleCodeSave = useCallback((content: string) => {
    if (!selectedStrategyId || !wsService) return;

    // Send save request to backend
    wsService.send(MessageType.UPDATE_PARAMS, {
      strategy_id: selectedStrategyId,
      action: 'save_code',
      code: content,
    });

    setIsCodeDirty(false);
  }, [selectedStrategyId, wsService]);

  // Handle parameter change
  const handleParamChange = useCallback((name: string, value: unknown) => {
    if (!selectedStrategyId) return;

    setStrategies(prev => prev.map(strategy => {
      if (strategy.strategyId !== selectedStrategyId) return strategy;
      return {
        ...strategy,
        parameters: strategy.parameters.map(param => {
          if (param.name !== name) return param;
          return { ...param, currentValue: value };
        }),
      };
    }));
  }, [selectedStrategyId]);

  // Handle apply all parameters
  const handleApplyParams = useCallback((params: Record<string, unknown>) => {
    if (!selectedStrategyId || !wsService) return;

    wsService.send(MessageType.UPDATE_PARAMS, {
      strategy_id: selectedStrategyId,
      parameters: params,
    });
  }, [selectedStrategyId, wsService]);

  // Handle hot reload
  const handleReload = useCallback((policy: HotReloadPolicy, preserveVars?: string[]) => {
    if (!selectedStrategyId) return;

    setIsReloading(true);

    // Simulate reload (in production, wait for backend response)
    setTimeout(() => {
      setIsReloading(false);
      setLastReloadResult({
        success: true,
        policy,
        preservedVariables: preserveVars || (policy === HotReloadPolicy.PRESERVE
          ? ['fast_ma', 'slow_ma', 'position']
          : []),
        resetVariables: policy === HotReloadPolicy.RESET
          ? ['fast_ma', 'slow_ma', 'position', 'entry_price', 'trade_count']
          : [],
      });
    }, 1500);
  }, [selectedStrategyId]);

  // Handle rollback
  const handleRollback = useCallback(() => {
    if (!selectedStrategyId) return;

    // Simulate rollback
    setLastReloadResult({
      success: true,
      policy: HotReloadPolicy.RESET,
      preservedVariables: [],
      resetVariables: ['fast_ma', 'slow_ma', 'position', 'entry_price', 'trade_count'],
    });
  }, [selectedStrategyId]);

  // Handle cursor position change
  const handleCursorChange = useCallback((position: { line: number; column: number }) => {
    setCursorPosition(position);
  }, []);

  return (
    <div className="strategy-lab">
      {/* Header */}
      <div className="strategy-lab-header">
        <div className="header-left">
          <h2 className="strategy-lab-title">{t('strategyLab.title')}</h2>
          <select
            className="strategy-selector"
            value={selectedStrategyId || ''}
            onChange={(e) => handleStrategySelect(e.target.value)}
          >
            <option value="" disabled>
              {t('strategyLab.selectStrategy')}
            </option>
            {strategies.map(strategy => (
              <option key={strategy.strategyId} value={strategy.strategyId}>
                {strategy.name}
              </option>
            ))}
          </select>
        </div>
        <div className="header-right">
          {isCodeDirty && (
            <span className="dirty-indicator">● {t('strategyLab.modified')}</span>
          )}
          <span className="cursor-position">
            {t('strategyLab.cursorPosition', {
              line: cursorPosition.line,
              col: cursorPosition.column,
            })}
          </span>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="strategy-lab-tabs">
        <button
          className={`tab-btn ${activeTab === 'editor' ? 'active' : ''}`}
          onClick={() => setActiveTab('editor')}
        >
          📝 {t('strategyLab.codeEditor')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'params' ? 'active' : ''}`}
          onClick={() => setActiveTab('params')}
        >
          ⚙️ {t('strategyLab.parameters')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'reload' ? 'active' : ''}`}
          onClick={() => setActiveTab('reload')}
        >
          🔄 {t('strategyLab.hotReload')}
        </button>
      </div>

      {/* Tab Content */}
      <div className="strategy-lab-content">
        {activeTab === 'editor' && (
          <CodeEditor
            initialContent={codeContent}
            language="python"
            theme="vs-dark"
            onChange={handleCodeChange}
            onSave={handleCodeSave}
            onCursorChange={handleCursorChange}
            readOnly={!selectedStrategyId}
          />
        )}

        {activeTab === 'params' && (
          <ParamPanel
            strategyId={selectedStrategyId}
            parameters={selectedStrategy?.parameters || []}
            onParameterChange={handleParamChange}
            onApplyAll={handleApplyParams}
            disabled={!isConnected}
          />
        )}

        {activeTab === 'reload' && (
          <HotReloadPanel
            strategyId={selectedStrategyId}
            isReloading={isReloading}
            lastReloadResult={lastReloadResult}
            onReload={handleReload}
            onRollback={handleRollback}
            disabled={!isConnected}
          />
        )}
      </div>
    </div>
  );
};

export default StrategyLab;

// Export sub-components for individual use
export { CodeEditor, ParamPanel, HotReloadPanel };
export * from './types';
