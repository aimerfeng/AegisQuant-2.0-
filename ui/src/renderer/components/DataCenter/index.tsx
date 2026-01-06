/**
 * Titan-Quant Data Center Component
 * 
 * Main Data Center component combining:
 * - File Dropzone (file import with format detection)
 * - Cleaning Preview (data quality analysis and cleaning)
 * - Provider Config (data source management)
 * 
 * Requirements: 2.1, 2.2, 2.3, Data Source Extension
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useConnectionStore } from '../../stores/connectionStore';
import FileDropzone from './FileDropzone';
import CleaningPreview from './CleaningPreview';
import ProviderConfig from './ProviderConfig';
import {
  DataCenterProps,
  ImportedFile,
  DataPreview,
  DataQualityReport,
  CleaningConfig,
  FillMethod,
  DataProviderConfig,
  DataProviderType,
  DataFormat,
} from './types';
import './DataCenter.css';

/**
 * Tab type for the data center panels
 */
type TabType = 'import' | 'cleaning' | 'providers';

/**
 * Mock data providers for demonstration
 */
const MOCK_PROVIDERS: DataProviderConfig[] = [
  {
    id: 'provider-001',
    type: DataProviderType.PARQUET,
    name: 'Local Parquet Store',
    path: './database',
    isDefault: true,
    isConnected: true,
    lastConnected: Date.now(),
  },
];

/**
 * Mock data preview for demonstration
 */
const MOCK_PREVIEW: DataPreview = {
  columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume'],
  rows: [
    {
      rowIndex: 0,
      data: { timestamp: '2024-01-01 09:00:00', open: 100.5, high: 101.2, low: 100.1, close: 100.8, volume: 1000 },
      issues: [],
    },
    {
      rowIndex: 1,
      data: { timestamp: '2024-01-01 09:01:00', open: 100.8, high: 101.5, low: null, close: 101.2, volume: 1200 },
      issues: [{ type: 'missing', column: 'low', rowIndex: 1, value: null, message: 'Missing value detected', severity: 'warning' }],
    },
    {
      rowIndex: 2,
      data: { timestamp: '2024-01-01 09:02:00', open: 101.2, high: 150.0, low: 101.0, close: 101.5, volume: 800 },
      issues: [{ type: 'outlier', column: 'high', rowIndex: 2, value: 150.0, message: 'Value exceeds 3σ threshold', severity: 'error' }],
    },
    {
      rowIndex: 3,
      data: { timestamp: '2024-01-01 09:03:00', open: 101.5, high: 102.0, low: 101.3, close: 101.8, volume: 950 },
      issues: [],
    },
    {
      rowIndex: 4,
      data: { timestamp: '2024-01-01 09:04:00', open: 101.8, high: 102.2, low: 101.5, close: 102.0, volume: 1100 },
      issues: [],
    },
  ],
  totalRows: 1000,
  qualityReport: {
    totalRows: 1000,
    totalColumns: 6,
    missingValues: { low: 15, volume: 3 },
    outliers: { high: [2, 45, 123], close: [89] },
    timestampGaps: ['2024-01-01 10:30:00', '2024-01-01 14:00:00'],
    alignmentIssues: [],
    issues: [
      { type: 'missing', column: 'low', rowIndex: 1, value: null, message: 'Missing value detected', severity: 'warning' },
      { type: 'outlier', column: 'high', rowIndex: 2, value: 150.0, message: 'Value exceeds 3σ threshold', severity: 'error' },
    ],
  },
};

/**
 * DataCenter Component
 */
const DataCenter: React.FC<DataCenterProps> = ({
  initialTab = 'import',
}) => {
  const { t } = useTranslation();
  const { connectionState } = useConnectionStore();
  
  // State
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);
  const [importedFiles, setImportedFiles] = useState<ImportedFile[]>([]);
  const [preview, setPreview] = useState<DataPreview | undefined>(MOCK_PREVIEW);
  const [cleaningConfig, setCleaningConfig] = useState<CleaningConfig>({
    fillMethod: FillMethod.FORWARD_FILL,
    outlierThreshold: 3.0,
    removeOutliers: false,
    alignTimestamps: true,
  });
  const [providers, setProviders] = useState<DataProviderConfig[]>(MOCK_PROVIDERS);
  const [activeProviderId, setActiveProviderId] = useState<string | undefined>(MOCK_PROVIDERS[0]?.id);
  const [isLoading, setIsLoading] = useState(false);

  const isConnected = connectionState === 'connected';

  /**
   * Handle files selected
   */
  const handleFilesSelected = useCallback((files: File[]) => {
    console.log('Files selected:', files);
    // In production, send files to backend for processing
  }, []);

  /**
   * Handle file imported
   */
  const handleFileImported = useCallback((file: ImportedFile) => {
    setImportedFiles((prev) => [...prev, file]);
    // Switch to cleaning tab after import
    setActiveTab('cleaning');
  }, []);

  /**
   * Handle cleaning config change
   */
  const handleCleaningConfigChange = useCallback((config: CleaningConfig) => {
    setCleaningConfig(config);
  }, []);

  /**
   * Handle apply cleaning
   */
  const handleApplyCleaning = useCallback(() => {
    setIsLoading(true);
    // Simulate cleaning process
    setTimeout(() => {
      setIsLoading(false);
      // In production, send cleaning request to backend
    }, 1500);
  }, []);

  /**
   * Handle provider select
   */
  const handleProviderSelect = useCallback((providerId: string) => {
    setActiveProviderId(providerId);
  }, []);

  /**
   * Handle provider add
   */
  const handleProviderAdd = useCallback((config: Omit<DataProviderConfig, 'id' | 'isConnected'>) => {
    const newProvider: DataProviderConfig = {
      ...config,
      id: `provider-${Date.now()}`,
      isConnected: false,
    };
    setProviders((prev) => [...prev, newProvider]);
  }, []);

  /**
   * Handle provider update
   */
  const handleProviderUpdate = useCallback((id: string, config: Partial<DataProviderConfig>) => {
    setProviders((prev) => prev.map((p) => 
      p.id === id ? { ...p, ...config } : p
    ));
  }, []);

  /**
   * Handle provider delete
   */
  const handleProviderDelete = useCallback((id: string) => {
    setProviders((prev) => prev.filter((p) => p.id !== id));
    if (activeProviderId === id) {
      setActiveProviderId(undefined);
    }
  }, [activeProviderId]);

  /**
   * Handle provider test
   */
  const handleProviderTest = useCallback(async (id: string): Promise<boolean> => {
    // Simulate connection test
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(Math.random() > 0.3); // 70% success rate for demo
      }, 1000);
    });
  }, []);

  return (
    <div className="data-center">
      {/* Header */}
      <div className="data-center-header">
        <h2 className="data-center-title">{t('dataCenter.title')}</h2>
      </div>

      {/* Tab Navigation */}
      <div className="data-center-tabs">
        <button
          className={`tab-btn ${activeTab === 'import' ? 'active' : ''}`}
          onClick={() => setActiveTab('import')}
        >
          📥 {t('dataCenter.import')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'cleaning' ? 'active' : ''}`}
          onClick={() => setActiveTab('cleaning')}
        >
          🧹 {t('dataCenter.cleaning')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'providers' ? 'active' : ''}`}
          onClick={() => setActiveTab('providers')}
        >
          🗄️ {t('dataCenter.providers')}
        </button>
      </div>

      {/* Tab Content */}
      <div className="data-center-content">
        {activeTab === 'import' && (
          <FileDropzone
            onFilesSelected={handleFilesSelected}
            onFileImported={handleFileImported}
            acceptedFormats={[DataFormat.CSV, DataFormat.EXCEL, DataFormat.PARQUET]}
            maxFileSize={100 * 1024 * 1024}
            multiple={true}
          />
        )}

        {activeTab === 'cleaning' && (
          <CleaningPreview
            preview={preview}
            config={cleaningConfig}
            onConfigChange={handleCleaningConfigChange}
            onApplyCleaning={handleApplyCleaning}
            isLoading={isLoading}
            disabled={!isConnected}
          />
        )}

        {activeTab === 'providers' && (
          <ProviderConfig
            providers={providers}
            activeProviderId={activeProviderId}
            onProviderSelect={handleProviderSelect}
            onProviderAdd={handleProviderAdd}
            onProviderUpdate={handleProviderUpdate}
            onProviderDelete={handleProviderDelete}
            onProviderTest={handleProviderTest}
            disabled={!isConnected}
          />
        )}
      </div>
    </div>
  );
};

export default DataCenter;

// Export sub-components for individual use
export { FileDropzone, CleaningPreview, ProviderConfig };
export * from './types';
