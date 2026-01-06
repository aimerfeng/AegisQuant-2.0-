/**
 * Titan-Quant Cleaning Preview Component
 * 
 * Data cleaning preview with missing value highlighting and outlier marking.
 * Requirements: 2.2, 2.3
 */

import React, { useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CleaningPreviewProps,
  DataPreview,
  DataQualityIssue,
  CleaningConfig,
  FillMethod,
} from './types';
import './CleaningPreview.css';

/**
 * Default cleaning configuration
 */
const DEFAULT_CLEANING_CONFIG: CleaningConfig = {
  fillMethod: FillMethod.FORWARD_FILL,
  outlierThreshold: 3.0,
  removeOutliers: false,
  alignTimestamps: true,
};

/**
 * CleaningPreview Component
 */
const CleaningPreview: React.FC<CleaningPreviewProps> = ({
  preview,
  config = DEFAULT_CLEANING_CONFIG,
  onConfigChange,
  onApplyCleaning,
  isLoading = false,
  disabled = false,
}) => {
  const { t } = useTranslation();
  
  // Local state for config editing
  const [localConfig, setLocalConfig] = useState<CleaningConfig>(config);
  const [activeTab, setActiveTab] = useState<'summary' | 'data' | 'issues'>('summary');

  /**
   * Handle config change
   */
  const handleConfigChange = useCallback((key: keyof CleaningConfig, value: unknown) => {
    const newConfig = { ...localConfig, [key]: value };
    setLocalConfig(newConfig);
    onConfigChange?.(newConfig);
  }, [localConfig, onConfigChange]);

  /**
   * Get issue count by type
   */
  const issueStats = useMemo(() => {
    if (!preview?.qualityReport) {
      return { missing: 0, outlier: 0, alignment: 0, total: 0 };
    }
    
    const issues = preview.qualityReport.issues || [];
    const missing = issues.filter(i => i.type === 'missing').length;
    const outlier = issues.filter(i => i.type === 'outlier').length;
    const alignment = issues.filter(i => i.type === 'alignment').length;
    
    return {
      missing,
      outlier,
      alignment,
      total: missing + outlier + alignment,
    };
  }, [preview]);

  /**
   * Check if a cell has an issue
   */
  const getCellIssue = useCallback((rowIndex: number, column: string): DataQualityIssue | undefined => {
    if (!preview?.rows) return undefined;
    const row = preview.rows.find(r => r.rowIndex === rowIndex);
    return row?.issues.find(i => i.column === column);
  }, [preview]);

  /**
   * Get cell class based on issue
   */
  const getCellClass = useCallback((issue?: DataQualityIssue): string => {
    if (!issue) return '';
    if (issue.type === 'missing') return 'cell-missing';
    if (issue.type === 'outlier') return 'cell-outlier';
    if (issue.severity === 'error') return 'cell-error';
    return 'cell-warning';
  }, []);

  /**
   * Render summary tab
   */
  const renderSummary = () => {
    if (!preview?.qualityReport) {
      return (
        <div className="cleaning-empty">
          <span className="empty-icon">📊</span>
          <p>{t('dataCenter.loadingPreview')}</p>
        </div>
      );
    }

    const { qualityReport } = preview;

    return (
      <div className="cleaning-summary">
        {/* Stats Cards */}
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-value">{qualityReport.totalRows}</span>
            <span className="stat-label">{t('dataCenter.totalRows')}</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{qualityReport.totalColumns}</span>
            <span className="stat-label">{t('dataCenter.totalColumns')}</span>
          </div>
          <div className="stat-card warning">
            <span className="stat-value">{issueStats.missing}</span>
            <span className="stat-label">{t('dataCenter.missingValues')}</span>
          </div>
          <div className="stat-card error">
            <span className="stat-value">{issueStats.outlier}</span>
            <span className="stat-label">{t('dataCenter.outliers')}</span>
          </div>
        </div>

        {/* Missing Values by Column */}
        {Object.keys(qualityReport.missingValues).length > 0 && (
          <div className="summary-section">
            <h4 className="section-title">
              ⚠️ {t('dataCenter.missingValues')}
            </h4>
            <div className="column-stats">
              {Object.entries(qualityReport.missingValues).map(([col, count]) => (
                <div key={col} className="column-stat">
                  <span className="column-name">{col}</span>
                  <span className="column-count">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Outliers by Column */}
        {Object.keys(qualityReport.outliers).length > 0 && (
          <div className="summary-section">
            <h4 className="section-title">
              🔴 {t('dataCenter.outliers')}
            </h4>
            <div className="column-stats">
              {Object.entries(qualityReport.outliers).map(([col, rows]) => (
                <div key={col} className="column-stat">
                  <span className="column-name">{col}</span>
                  <span className="column-count">{rows.length}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Timestamp Gaps */}
        {qualityReport.timestampGaps.length > 0 && (
          <div className="summary-section">
            <h4 className="section-title">
              ⏱️ {t('dataCenter.timestampGaps')}
            </h4>
            <div className="gap-list">
              {qualityReport.timestampGaps.slice(0, 5).map((gap, i) => (
                <span key={i} className="gap-item">{gap}</span>
              ))}
              {qualityReport.timestampGaps.length > 5 && (
                <span className="gap-more">
                  +{qualityReport.timestampGaps.length - 5} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* No Issues */}
        {issueStats.total === 0 && (
          <div className="no-issues">
            <span className="no-issues-icon">✅</span>
            <p>{t('dataCenter.noIssues')}</p>
          </div>
        )}
      </div>
    );
  };

  /**
   * Render data preview tab
   */
  const renderDataPreview = () => {
    if (!preview?.rows || preview.rows.length === 0) {
      return (
        <div className="cleaning-empty">
          <span className="empty-icon">📋</span>
          <p>{t('dataCenter.loadingPreview')}</p>
        </div>
      );
    }

    return (
      <div className="data-preview-table-container">
        <table className="data-preview-table">
          <thead>
            <tr>
              <th className="row-index-header">#</th>
              {preview.columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row) => (
              <tr key={row.rowIndex}>
                <td className="row-index">{row.rowIndex}</td>
                {preview.columns.map((col) => {
                  const issue = getCellIssue(row.rowIndex, col);
                  const cellClass = getCellClass(issue);
                  const value = row.data[col];
                  
                  return (
                    <td 
                      key={col} 
                      className={cellClass}
                      title={issue?.message}
                    >
                      {value === null || value === undefined ? (
                        <span className="null-value">NULL</span>
                      ) : (
                        String(value)
                      )}
                      {issue && (
                        <span className="issue-indicator">
                          {issue.type === 'missing' ? '⚠️' : '🔴'}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  /**
   * Render issues tab
   */
  const renderIssues = () => {
    const issues = preview?.qualityReport?.issues || [];
    
    if (issues.length === 0) {
      return (
        <div className="cleaning-empty">
          <span className="empty-icon">✅</span>
          <p>{t('dataCenter.noIssues')}</p>
        </div>
      );
    }

    return (
      <div className="issues-list">
        {issues.map((issue, index) => (
          <div 
            key={index} 
            className={`issue-item ${issue.severity}`}
          >
            <div className="issue-header">
              <span className="issue-type">
                {issue.type === 'missing' && '⚠️'}
                {issue.type === 'outlier' && '🔴'}
                {issue.type === 'alignment' && '⏱️'}
                {issue.type === 'format' && '📄'}
              </span>
              <span className="issue-location">
                {t('dataCenter.column')}: {issue.column}, {t('dataCenter.row')}: {issue.rowIndex}
              </span>
              <span className={`issue-severity ${issue.severity}`}>
                {t(`dataCenter.${issue.severity}`)}
              </span>
            </div>
            <p className="issue-message">{issue.message}</p>
            {issue.value !== undefined && (
              <span className="issue-value">
                {t('dataCenter.value')}: {String(issue.value)}
              </span>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className={`cleaning-preview ${isLoading ? 'loading' : ''}`}>
      {/* Header */}
      <div className="cleaning-header">
        <h3 className="cleaning-title">{t('dataCenter.cleaningPreview')}</h3>
      </div>

      {/* Configuration Panel */}
      <div className="cleaning-config">
        <div className="config-row">
          <label className="config-label">{t('dataCenter.fillMethod')}</label>
          <select
            className="config-select"
            value={localConfig.fillMethod}
            onChange={(e) => handleConfigChange('fillMethod', e.target.value as FillMethod)}
            disabled={disabled}
          >
            <option value={FillMethod.FORWARD_FILL}>
              {t('dataCenter.forwardFill')}
            </option>
            <option value={FillMethod.LINEAR}>
              {t('dataCenter.linearInterpolation')}
            </option>
            <option value={FillMethod.DROP}>
              {t('dataCenter.dropRows')}
            </option>
          </select>
        </div>

        <div className="config-row">
          <label className="config-label">
            {t('dataCenter.outlierThreshold')}
          </label>
          <input
            type="number"
            className="config-input"
            value={localConfig.outlierThreshold}
            onChange={(e) => handleConfigChange('outlierThreshold', parseFloat(e.target.value))}
            min={1}
            max={5}
            step={0.5}
            disabled={disabled}
          />
        </div>

        <div className="config-row checkbox">
          <label className="config-checkbox-label">
            <input
              type="checkbox"
              checked={localConfig.removeOutliers}
              onChange={(e) => handleConfigChange('removeOutliers', e.target.checked)}
              disabled={disabled}
            />
            {t('dataCenter.removeOutliers')}
          </label>
        </div>

        <div className="config-row checkbox">
          <label className="config-checkbox-label">
            <input
              type="checkbox"
              checked={localConfig.alignTimestamps}
              onChange={(e) => handleConfigChange('alignTimestamps', e.target.checked)}
              disabled={disabled}
            />
            {t('dataCenter.alignTimestamps')}
          </label>
        </div>

        <button
          className="apply-btn"
          onClick={onApplyCleaning}
          disabled={disabled || isLoading}
        >
          {isLoading ? '...' : t('dataCenter.applyCleaning')}
        </button>
      </div>

      {/* Tabs */}
      <div className="cleaning-tabs">
        <button
          className={`tab-btn ${activeTab === 'summary' ? 'active' : ''}`}
          onClick={() => setActiveTab('summary')}
        >
          📊 {t('report.summary')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'data' ? 'active' : ''}`}
          onClick={() => setActiveTab('data')}
        >
          📋 {t('dataCenter.previewData')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'issues' ? 'active' : ''}`}
          onClick={() => setActiveTab('issues')}
        >
          ⚠️ {t('dataCenter.issue')} ({issueStats.total})
        </button>
      </div>

      {/* Tab Content */}
      <div className="cleaning-content">
        {activeTab === 'summary' && renderSummary()}
        {activeTab === 'data' && renderDataPreview()}
        {activeTab === 'issues' && renderIssues()}
      </div>
    </div>
  );
};

export default CleaningPreview;
