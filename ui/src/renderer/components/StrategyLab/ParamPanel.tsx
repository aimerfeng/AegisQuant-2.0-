/**
 * Titan-Quant Strategy Parameter Panel Component
 * 
 * Dynamic form generation for strategy parameters.
 * Features:
 * - Automatic UI widget mapping (slider, dropdown, input)
 * - Real-time parameter validation
 * - Apply and reset functionality
 * 
 * Requirements: 8.2
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { ParamPanelProps, StrategyParameter, StrategyParamType } from './types';
import './ParamPanel.css';

/**
 * Individual parameter input component
 */
interface ParamInputProps {
  parameter: StrategyParameter;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled?: boolean;
}

const ParamInput: React.FC<ParamInputProps> = ({
  parameter,
  value,
  onChange,
  disabled = false,
}) => {
  const { t } = useTranslation();

  // Render slider for numeric types with min/max
  if (
    (parameter.paramType === 'int' || parameter.paramType === 'float') &&
    parameter.minValue !== undefined &&
    parameter.maxValue !== undefined &&
    parameter.uiWidget === 'slider'
  ) {
    const step = parameter.step ?? (parameter.paramType === 'int' ? 1 : 0.01);
    const numValue = typeof value === 'number' ? value : Number(value) || parameter.minValue;

    return (
      <div className="param-slider-container">
        <input
          type="range"
          className="param-slider"
          min={parameter.minValue}
          max={parameter.maxValue}
          step={step}
          value={numValue}
          onChange={(e) => {
            const newValue = parameter.paramType === 'int'
              ? parseInt(e.target.value, 10)
              : parseFloat(e.target.value);
            onChange(newValue);
          }}
          disabled={disabled}
        />
        <input
          type="number"
          className="param-slider-value"
          min={parameter.minValue}
          max={parameter.maxValue}
          step={step}
          value={numValue}
          onChange={(e) => {
            const newValue = parameter.paramType === 'int'
              ? parseInt(e.target.value, 10)
              : parseFloat(e.target.value);
            if (!isNaN(newValue)) {
              onChange(Math.min(Math.max(newValue, parameter.minValue!), parameter.maxValue!));
            }
          }}
          disabled={disabled}
        />
      </div>
    );
  }

  // Render dropdown for enum types
  if (parameter.paramType === 'enum' && parameter.options) {
    return (
      <select
        className="param-dropdown"
        value={String(value)}
        onChange={(e) => {
          const option = parameter.options?.find(opt => String(opt.value) === e.target.value);
          onChange(option?.value ?? e.target.value);
        }}
        disabled={disabled}
      >
        {parameter.options.map((option) => (
          <option key={String(option.value)} value={String(option.value)}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  // Render checkbox for boolean types
  if (parameter.paramType === 'bool') {
    return (
      <label className="param-checkbox-container">
        <input
          type="checkbox"
          className="param-checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
        />
        <span className="param-checkbox-label">
          {value ? t('ui.confirm') : t('ui.cancel')}
        </span>
      </label>
    );
  }

  // Render number input for numeric types without slider
  if (parameter.paramType === 'int' || parameter.paramType === 'float') {
    const step = parameter.step ?? (parameter.paramType === 'int' ? 1 : 0.01);
    return (
      <input
        type="number"
        className="param-input param-input-number"
        value={typeof value === 'number' ? value : ''}
        min={parameter.minValue}
        max={parameter.maxValue}
        step={step}
        onChange={(e) => {
          const newValue = parameter.paramType === 'int'
            ? parseInt(e.target.value, 10)
            : parseFloat(e.target.value);
          if (!isNaN(newValue)) {
            onChange(newValue);
          }
        }}
        disabled={disabled}
        placeholder={String(parameter.defaultValue)}
      />
    );
  }

  // Default: text input for string types
  return (
    <input
      type="text"
      className="param-input param-input-text"
      value={String(value ?? '')}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      placeholder={String(parameter.defaultValue)}
    />
  );
};

/**
 * Parameter type badge component
 */
const ParamTypeBadge: React.FC<{ type: StrategyParamType }> = ({ type }) => {
  const typeColors: Record<StrategyParamType, string> = {
    int: '#4caf50',
    float: '#2196f3',
    string: '#ff9800',
    enum: '#9c27b0',
    bool: '#e91e63',
  };

  return (
    <span
      className="param-type-badge"
      style={{ backgroundColor: typeColors[type] }}
    >
      {type}
    </span>
  );
};

/**
 * Main Parameter Panel Component
 */
const ParamPanel: React.FC<ParamPanelProps> = ({
  strategyId,
  parameters,
  onParameterChange,
  onApplyAll,
  disabled = false,
}) => {
  const { t } = useTranslation();
  
  // Local state for parameter values
  const [localValues, setLocalValues] = useState<Record<string, unknown>>({});
  const [hasChanges, setHasChanges] = useState(false);

  // Initialize local values from parameters
  useEffect(() => {
    const initialValues: Record<string, unknown> = {};
    parameters.forEach(param => {
      initialValues[param.name] = param.currentValue ?? param.defaultValue;
    });
    setLocalValues(initialValues);
    setHasChanges(false);
  }, [parameters]);

  // Check if values have changed from current
  const checkChanges = useCallback((values: Record<string, unknown>) => {
    return parameters.some(param => {
      const currentVal = param.currentValue ?? param.defaultValue;
      return values[param.name] !== currentVal;
    });
  }, [parameters]);

  // Handle individual parameter change
  const handleParamChange = useCallback((name: string, value: unknown) => {
    setLocalValues(prev => {
      const newValues = { ...prev, [name]: value };
      setHasChanges(checkChanges(newValues));
      return newValues;
    });
    onParameterChange?.(name, value);
  }, [onParameterChange, checkChanges]);

  // Apply all parameter changes
  const handleApplyAll = useCallback(() => {
    onApplyAll?.(localValues);
    setHasChanges(false);
  }, [localValues, onApplyAll]);

  // Reset all parameters to default values
  const handleResetAll = useCallback(() => {
    const defaultValues: Record<string, unknown> = {};
    parameters.forEach(param => {
      defaultValues[param.name] = param.defaultValue;
    });
    setLocalValues(defaultValues);
    setHasChanges(checkChanges(defaultValues));
  }, [parameters, checkChanges]);

  // Group parameters by category (if description contains category prefix)
  const groupedParams = useMemo(() => {
    const groups: Record<string, StrategyParameter[]> = { default: [] };
    
    parameters.forEach(param => {
      // Check if description has category prefix like "[Category] Description"
      const match = param.description?.match(/^\[([^\]]+)\]\s*/);
      if (match) {
        const category = match[1];
        if (!groups[category]) {
          groups[category] = [];
        }
        groups[category].push(param);
      } else {
        groups.default.push(param);
      }
    });

    // Remove empty default group
    if (groups.default.length === 0) {
      delete groups.default;
    }

    return groups;
  }, [parameters]);

  if (parameters.length === 0) {
    return (
      <div className="param-panel param-panel-empty">
        <p className="param-empty-message">
          {strategyId
            ? t('strategyLab.noStrategyLoaded')
            : t('strategyLab.selectStrategy')}
        </p>
      </div>
    );
  }

  return (
    <div className="param-panel">
      <div className="param-panel-header">
        <h3 className="param-panel-title">{t('strategyLab.parameters')}</h3>
        <div className="param-panel-actions">
          <button
            className="param-btn param-btn-reset"
            onClick={handleResetAll}
            disabled={disabled}
            title={t('strategyLab.resetParams')}
          >
            ↺ {t('strategyLab.resetParams')}
          </button>
          <button
            className={`param-btn param-btn-apply ${hasChanges ? 'has-changes' : ''}`}
            onClick={handleApplyAll}
            disabled={disabled || !hasChanges}
            title={t('strategyLab.applyParams')}
          >
            ✓ {t('strategyLab.applyParams')}
          </button>
        </div>
      </div>

      <div className="param-panel-content">
        {Object.entries(groupedParams).map(([groupName, groupParams]) => (
          <div key={groupName} className="param-group">
            {groupName !== 'default' && (
              <div className="param-group-header">{groupName}</div>
            )}
            <div className="param-list">
              {groupParams.map(param => (
                <div key={param.name} className="param-item">
                  <div className="param-item-header">
                    <label className="param-label" htmlFor={`param-${param.name}`}>
                      {param.name}
                    </label>
                    <ParamTypeBadge type={param.paramType} />
                  </div>
                  
                  {param.description && (
                    <p className="param-description">
                      {param.description.replace(/^\[[^\]]+\]\s*/, '')}
                    </p>
                  )}
                  
                  <div className="param-input-wrapper">
                    <ParamInput
                      parameter={param}
                      value={localValues[param.name] ?? param.defaultValue}
                      onChange={(value) => handleParamChange(param.name, value)}
                      disabled={disabled}
                    />
                  </div>

                  {(param.minValue !== undefined || param.maxValue !== undefined) && (
                    <div className="param-range-info">
                      {param.minValue !== undefined && (
                        <span>{t('strategyLab.paramMin')}: {param.minValue}</span>
                      )}
                      {param.maxValue !== undefined && (
                        <span>{t('strategyLab.paramMax')}: {param.maxValue}</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {hasChanges && (
        <div className="param-panel-footer">
          <span className="param-changes-indicator">
            ● {t('strategyLab.unsavedChanges')}
          </span>
        </div>
      )}
    </div>
  );
};

export default ParamPanel;
