/**
 * Titan-Quant Data Center Types
 * 
 * Type definitions for Data Center components.
 * Requirements: 2.1, 2.2, 2.3, Data Source Extension
 */

/**
 * Supported data file formats
 */
export enum DataFormat {
  CSV = 'csv',
  EXCEL = 'excel',
  PARQUET = 'parquet',
  UNKNOWN = 'unknown',
}

/**
 * Fill method for missing values
 */
export enum FillMethod {
  FORWARD_FILL = 'ffill',
  LINEAR = 'linear',
  DROP = 'drop',
}

/**
 * Data provider types
 */
export enum DataProviderType {
  PARQUET = 'parquet',
  MYSQL = 'mysql',
  MONGODB = 'mongodb',
  DOLPHINDB = 'dolphindb',
}

/**
 * File import status
 */
export enum ImportStatus {
  IDLE = 'idle',
  UPLOADING = 'uploading',
  ANALYZING = 'analyzing',
  CLEANING = 'cleaning',
  IMPORTING = 'importing',
  COMPLETED = 'completed',
  ERROR = 'error',
}

/**
 * Imported file information
 */
export interface ImportedFile {
  id: string;
  name: string;
  size: number;
  format: DataFormat;
  status: ImportStatus;
  progress: number;
  error?: string;
  uploadedAt: number;
}

/**
 * Data quality issue
 */
export interface DataQualityIssue {
  type: 'missing' | 'outlier' | 'alignment' | 'format';
  column: string;
  rowIndex: number;
  value: unknown;
  message: string;
  severity: 'warning' | 'error';
}

/**
 * Data quality report
 */
export interface DataQualityReport {
  totalRows: number;
  totalColumns: number;
  missingValues: Record<string, number>;
  outliers: Record<string, number[]>;
  timestampGaps: string[];
  alignmentIssues: string[];
  issues: DataQualityIssue[];
}

/**
 * Cleaning configuration
 */
export interface CleaningConfig {
  fillMethod: FillMethod;
  outlierThreshold: number;
  removeOutliers: boolean;
  alignTimestamps: boolean;
}

/**
 * Data preview row
 */
export interface DataPreviewRow {
  rowIndex: number;
  data: Record<string, unknown>;
  issues: DataQualityIssue[];
}

/**
 * Data preview
 */
export interface DataPreview {
  columns: string[];
  rows: DataPreviewRow[];
  totalRows: number;
  qualityReport: DataQualityReport;
}

/**
 * Data provider configuration
 */
export interface DataProviderConfig {
  id: string;
  type: DataProviderType;
  name: string;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  path?: string;
  isDefault: boolean;
  isConnected: boolean;
  lastConnected?: number;
}

/**
 * FileDropzone props
 */
export interface FileDropzoneProps {
  onFilesSelected?: (files: File[]) => void;
  onFileImported?: (file: ImportedFile) => void;
  acceptedFormats?: DataFormat[];
  maxFileSize?: number;
  multiple?: boolean;
  disabled?: boolean;
}

/**
 * CleaningPreview props
 */
export interface CleaningPreviewProps {
  preview?: DataPreview;
  config?: CleaningConfig;
  onConfigChange?: (config: CleaningConfig) => void;
  onApplyCleaning?: () => void;
  isLoading?: boolean;
  disabled?: boolean;
}

/**
 * ProviderConfig props
 */
export interface ProviderConfigProps {
  providers?: DataProviderConfig[];
  activeProviderId?: string;
  onProviderSelect?: (providerId: string) => void;
  onProviderAdd?: (config: Omit<DataProviderConfig, 'id' | 'isConnected'>) => void;
  onProviderUpdate?: (id: string, config: Partial<DataProviderConfig>) => void;
  onProviderDelete?: (id: string) => void;
  onProviderTest?: (id: string) => Promise<boolean>;
  disabled?: boolean;
}

/**
 * DataCenter main component props
 */
export interface DataCenterProps {
  initialTab?: 'import' | 'cleaning' | 'providers';
}

/**
 * File format detection result
 */
export interface FormatDetectionResult {
  format: DataFormat;
  confidence: number;
  mimeType?: string;
  extension?: string;
}

/**
 * Utility function to detect file format
 */
export const detectFileFormat = (file: File): FormatDetectionResult => {
  const extension = file.name.split('.').pop()?.toLowerCase() || '';
  const mimeType = file.type;

  // Check by extension
  if (extension === 'csv' || mimeType === 'text/csv') {
    return { format: DataFormat.CSV, confidence: 1.0, mimeType, extension };
  }
  
  if (extension === 'xlsx' || extension === 'xls' || 
      mimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
      mimeType === 'application/vnd.ms-excel') {
    return { format: DataFormat.EXCEL, confidence: 1.0, mimeType, extension };
  }
  
  if (extension === 'parquet' || mimeType === 'application/octet-stream') {
    // Parquet files often have octet-stream mime type
    if (extension === 'parquet') {
      return { format: DataFormat.PARQUET, confidence: 1.0, mimeType, extension };
    }
    return { format: DataFormat.PARQUET, confidence: 0.5, mimeType, extension };
  }

  return { format: DataFormat.UNKNOWN, confidence: 0, mimeType, extension };
};

/**
 * Format file size for display
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

/**
 * Get format icon
 */
export const getFormatIcon = (format: DataFormat): string => {
  switch (format) {
    case DataFormat.CSV:
      return '📄';
    case DataFormat.EXCEL:
      return '📊';
    case DataFormat.PARQUET:
      return '🗃️';
    default:
      return '📁';
  }
};

/**
 * Get format label
 */
export const getFormatLabel = (format: DataFormat): string => {
  switch (format) {
    case DataFormat.CSV:
      return 'CSV';
    case DataFormat.EXCEL:
      return 'Excel';
    case DataFormat.PARQUET:
      return 'Parquet';
    default:
      return 'Unknown';
  }
};
