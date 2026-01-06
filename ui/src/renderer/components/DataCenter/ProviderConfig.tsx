/**
 * Titan-Quant Provider Config Component
 * 
 * Data source configuration and management.
 * Requirements: Data Source Extension
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ProviderConfigProps,
  DataProviderConfig,
  DataProviderType,
} from './types';
import './ProviderConfig.css';

/**
 * Generate unique ID for providers
 */
const generateProviderId = (): string => {
  return `provider-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * Get provider type icon
 */
const getProviderIcon = (type: DataProviderType): string => {
  switch (type) {
    case DataProviderType.PARQUET:
      return '🗃️';
    case DataProviderType.MYSQL:
      return '🐬';
    case DataProviderType.MONGODB:
      return '🍃';
    case DataProviderType.DOLPHINDB:
      return '🐬';
    default:
      return '📁';
  }
};

/**
 * Default provider config template
 */
const getDefaultProviderConfig = (type: DataProviderType): Partial<DataProviderConfig> => {
  switch (type) {
    case DataProviderType.PARQUET:
      return {
        type,
        name: '',
        path: './database',
        isDefault: false,
      };
    case DataProviderType.MYSQL:
      return {
        type,
        name: '',
        host: 'localhost',
        port: 3306,
        database: '',
        username: '',
        password: '',
        isDefault: false,
      };
    case DataProviderType.MONGODB:
      return {
        type,
        name: '',
        host: 'localhost',
        port: 27017,
        database: '',
        username: '',
        password: '',
        isDefault: false,
      };
    case DataProviderType.DOLPHINDB:
      return {
        type,
        name: '',
        host: 'localhost',
        port: 8848,
        database: '',
        username: 'admin',
        password: '',
        isDefault: false,
      };
    default:
      return { type, name: '', isDefault: false };
  }
};

/**
 * ProviderConfig Component
 */
const ProviderConfig: React.FC<ProviderConfigProps> = ({
  providers = [],
  activeProviderId,
  onProviderSelect,
  onProviderAdd,
  onProviderUpdate,
  onProviderDelete,
  onProviderTest,
  disabled = false,
}) => {
  const { t } = useTranslation();
  
  // State
  const [isEditing, setIsEditing] = useState(false);
  const [editingProvider, setEditingProvider] = useState<Partial<DataProviderConfig> | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; success: boolean } | null>(null);

  /**
   * Handle add new provider
   */
  const handleAddProvider = useCallback((type: DataProviderType) => {
    const defaultConfig = getDefaultProviderConfig(type);
    setEditingProvider(defaultConfig);
    setIsEditing(true);
  }, []);

  /**
   * Handle edit provider
   */
  const handleEditProvider = useCallback((provider: DataProviderConfig) => {
    setEditingProvider({ ...provider });
    setIsEditing(true);
  }, []);

  /**
   * Handle save provider
   */
  const handleSaveProvider = useCallback(() => {
    if (!editingProvider || !editingProvider.name || !editingProvider.type) return;

    if (editingProvider.id) {
      // Update existing
      onProviderUpdate?.(editingProvider.id, editingProvider);
    } else {
      // Add new
      onProviderAdd?.({
        ...editingProvider,
        type: editingProvider.type,
        name: editingProvider.name,
        isDefault: editingProvider.isDefault || false,
      } as Omit<DataProviderConfig, 'id' | 'isConnected'>);
    }

    setIsEditing(false);
    setEditingProvider(null);
  }, [editingProvider, onProviderAdd, onProviderUpdate]);

  /**
   * Handle cancel edit
   */
  const handleCancelEdit = useCallback(() => {
    setIsEditing(false);
    setEditingProvider(null);
  }, []);

  /**
   * Handle delete provider
   */
  const handleDeleteProvider = useCallback((id: string) => {
    if (window.confirm(t('dataCenter.confirmDelete'))) {
      onProviderDelete?.(id);
    }
  }, [onProviderDelete, t]);

  /**
   * Handle test connection
   */
  const handleTestConnection = useCallback(async (id: string) => {
    if (!onProviderTest) return;
    
    setTestingId(id);
    setTestResult(null);
    
    try {
      const success = await onProviderTest(id);
      setTestResult({ id, success });
    } catch {
      setTestResult({ id, success: false });
    } finally {
      setTestingId(null);
    }
  }, [onProviderTest]);

  /**
   * Handle form field change
   */
  const handleFieldChange = useCallback((field: keyof DataProviderConfig, value: unknown) => {
    setEditingProvider(prev => prev ? { ...prev, [field]: value } : null);
  }, []);

  /**
   * Render provider form
   */
  const renderProviderForm = () => {
    if (!editingProvider) return null;

    const isNew = !editingProvider.id;
    const type = editingProvider.type;

    return (
      <div className="provider-form">
        <h4 className="form-title">
          {isNew ? t('dataCenter.addProvider') : t('dataCenter.editProvider')}
        </h4>

        <div className="form-group">
          <label className="form-label">{t('dataCenter.providerName')}</label>
          <input
            type="text"
            className="form-input"
            value={editingProvider.name || ''}
            onChange={(e) => handleFieldChange('name', e.target.value)}
            placeholder={t('dataCenter.providerName')}
            disabled={disabled}
          />
        </div>

        {isNew && (
          <div className="form-group">
            <label className="form-label">{t('dataCenter.providerType')}</label>
            <select
              className="form-select"
              value={editingProvider.type || ''}
              onChange={(e) => {
                const newType = e.target.value as DataProviderType;
                setEditingProvider(getDefaultProviderConfig(newType));
              }}
              disabled={disabled}
            >
              <option value={DataProviderType.PARQUET}>
                {getProviderIcon(DataProviderType.PARQUET)} {t('dataCenter.parquet')}
              </option>
              <option value={DataProviderType.MYSQL}>
                {getProviderIcon(DataProviderType.MYSQL)} {t('dataCenter.mysql')}
              </option>
              <option value={DataProviderType.MONGODB}>
                {getProviderIcon(DataProviderType.MONGODB)} {t('dataCenter.mongodb')}
              </option>
              <option value={DataProviderType.DOLPHINDB}>
                {getProviderIcon(DataProviderType.DOLPHINDB)} {t('dataCenter.dolphindb')}
              </option>
            </select>
          </div>
        )}

        {/* Type-specific fields */}
        {type === DataProviderType.PARQUET && (
          <div className="form-group">
            <label className="form-label">{t('dataCenter.path')}</label>
            <input
              type="text"
              className="form-input"
              value={editingProvider.path || ''}
              onChange={(e) => handleFieldChange('path', e.target.value)}
              placeholder="./database"
              disabled={disabled}
            />
          </div>
        )}

        {(type === DataProviderType.MYSQL || 
          type === DataProviderType.MONGODB || 
          type === DataProviderType.DOLPHINDB) && (
          <>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">{t('dataCenter.host')}</label>
                <input
                  type="text"
                  className="form-input"
                  value={editingProvider.host || ''}
                  onChange={(e) => handleFieldChange('host', e.target.value)}
                  placeholder="localhost"
                  disabled={disabled}
                />
              </div>
              <div className="form-group small">
                <label className="form-label">{t('dataCenter.port')}</label>
                <input
                  type="number"
                  className="form-input"
                  value={editingProvider.port || ''}
                  onChange={(e) => handleFieldChange('port', parseInt(e.target.value))}
                  disabled={disabled}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">{t('dataCenter.database')}</label>
              <input
                type="text"
                className="form-input"
                value={editingProvider.database || ''}
                onChange={(e) => handleFieldChange('database', e.target.value)}
                disabled={disabled}
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">{t('dataCenter.username')}</label>
                <input
                  type="text"
                  className="form-input"
                  value={editingProvider.username || ''}
                  onChange={(e) => handleFieldChange('username', e.target.value)}
                  disabled={disabled}
                />
              </div>
              <div className="form-group">
                <label className="form-label">{t('dataCenter.password')}</label>
                <input
                  type="password"
                  className="form-input"
                  value={editingProvider.password || ''}
                  onChange={(e) => handleFieldChange('password', e.target.value)}
                  disabled={disabled}
                />
              </div>
            </div>
          </>
        )}

        <div className="form-group checkbox">
          <label className="form-checkbox-label">
            <input
              type="checkbox"
              checked={editingProvider.isDefault || false}
              onChange={(e) => handleFieldChange('isDefault', e.target.checked)}
              disabled={disabled}
            />
            {t('dataCenter.setAsDefault')}
          </label>
        </div>

        <div className="form-actions">
          <button
            className="btn btn-secondary"
            onClick={handleCancelEdit}
          >
            {t('dataCenter.cancel')}
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSaveProvider}
            disabled={disabled || !editingProvider.name}
          >
            {t('dataCenter.save')}
          </button>
        </div>
      </div>
    );
  };

  /**
   * Render provider list
   */
  const renderProviderList = () => {
    if (providers.length === 0) {
      return (
        <div className="provider-empty">
          <span className="empty-icon">🗄️</span>
          <p>{t('dataCenter.noProviders')}</p>
        </div>
      );
    }

    return (
      <div className="provider-list">
        {providers.map((provider) => {
          const isActive = provider.id === activeProviderId;
          const isTesting = testingId === provider.id;
          const hasTestResult = testResult?.id === provider.id;

          return (
            <div
              key={provider.id}
              className={`provider-item ${isActive ? 'active' : ''} ${provider.isConnected ? 'connected' : ''}`}
              onClick={() => onProviderSelect?.(provider.id)}
            >
              <div className="provider-icon">
                {getProviderIcon(provider.type)}
              </div>
              
              <div className="provider-info">
                <div className="provider-name">
                  {provider.name}
                  {provider.isDefault && (
                    <span className="default-badge">{t('dataCenter.isDefault')}</span>
                  )}
                </div>
                <div className="provider-meta">
                  {t(`dataCenter.${provider.type}`)}
                  {provider.host && ` • ${provider.host}:${provider.port}`}
                  {provider.path && ` • ${provider.path}`}
                </div>
              </div>

              <div className="provider-status">
                {provider.isConnected ? (
                  <span className="status-connected">●</span>
                ) : (
                  <span className="status-disconnected">○</span>
                )}
              </div>

              <div className="provider-actions">
                <button
                  className={`action-btn test ${hasTestResult ? (testResult.success ? 'success' : 'error') : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleTestConnection(provider.id);
                  }}
                  disabled={disabled || isTesting}
                  title={t('dataCenter.testConnection')}
                >
                  {isTesting ? '...' : '🔌'}
                </button>
                <button
                  className="action-btn edit"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEditProvider(provider);
                  }}
                  disabled={disabled}
                  title={t('dataCenter.editProvider')}
                >
                  ✏️
                </button>
                <button
                  className="action-btn delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteProvider(provider.id);
                  }}
                  disabled={disabled}
                  title={t('dataCenter.deleteProvider')}
                >
                  🗑️
                </button>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="provider-config">
      {/* Header */}
      <div className="provider-header">
        <h3 className="provider-title">{t('dataCenter.providerConfig')}</h3>
        {!isEditing && (
          <div className="add-provider-dropdown">
            <button className="add-btn" disabled={disabled}>
              + {t('dataCenter.addProvider')}
            </button>
            <div className="dropdown-menu">
              <button onClick={() => handleAddProvider(DataProviderType.PARQUET)}>
                {getProviderIcon(DataProviderType.PARQUET)} {t('dataCenter.parquet')}
              </button>
              <button onClick={() => handleAddProvider(DataProviderType.MYSQL)}>
                {getProviderIcon(DataProviderType.MYSQL)} {t('dataCenter.mysql')}
              </button>
              <button onClick={() => handleAddProvider(DataProviderType.MONGODB)}>
                {getProviderIcon(DataProviderType.MONGODB)} {t('dataCenter.mongodb')}
              </button>
              <button onClick={() => handleAddProvider(DataProviderType.DOLPHINDB)}>
                {getProviderIcon(DataProviderType.DOLPHINDB)} {t('dataCenter.dolphindb')}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="provider-content">
        {isEditing ? renderProviderForm() : renderProviderList()}
      </div>
    </div>
  );
};

export default ProviderConfig;
