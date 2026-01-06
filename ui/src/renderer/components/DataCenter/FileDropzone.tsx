/**
 * Titan-Quant File Dropzone Component
 * 
 * Drag-and-drop file upload area with format detection.
 * Requirements: 2.1
 */

import React, { useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  FileDropzoneProps,
  ImportedFile,
  ImportStatus,
  DataFormat,
  detectFileFormat,
  formatFileSize,
  getFormatIcon,
  getFormatLabel,
} from './types';
import './FileDropzone.css';

/**
 * Generate unique ID for files
 */
const generateFileId = (): string => {
  return `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * FileDropzone Component
 */
const FileDropzone: React.FC<FileDropzoneProps> = ({
  onFilesSelected,
  onFileImported,
  acceptedFormats = [DataFormat.CSV, DataFormat.EXCEL, DataFormat.PARQUET],
  maxFileSize = 100 * 1024 * 1024, // 100MB default
  multiple = true,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // State
  const [isDragOver, setIsDragOver] = useState(false);
  const [files, setFiles] = useState<ImportedFile[]>([]);
  const [error, setError] = useState<string | null>(null);

  /**
   * Process selected files
   */
  const processFiles = useCallback((selectedFiles: FileList | File[]) => {
    const fileArray = Array.from(selectedFiles);
    const newFiles: ImportedFile[] = [];
    const errors: string[] = [];

    fileArray.forEach((file) => {
      // Detect format
      const detection = detectFileFormat(file);
      
      // Validate format
      if (!acceptedFormats.includes(detection.format) && detection.format !== DataFormat.UNKNOWN) {
        errors.push(t('dataCenter.formatNotSupported', { name: file.name }));
        return;
      }

      // Validate size
      if (file.size > maxFileSize) {
        errors.push(t('dataCenter.fileTooLarge', { 
          name: file.name, 
          max: formatFileSize(maxFileSize) 
        }));
        return;
      }

      // Create imported file record
      const importedFile: ImportedFile = {
        id: generateFileId(),
        name: file.name,
        size: file.size,
        format: detection.format,
        status: ImportStatus.IDLE,
        progress: 0,
        uploadedAt: Date.now(),
      };

      newFiles.push(importedFile);
    });

    if (errors.length > 0) {
      setError(errors.join('\n'));
    } else {
      setError(null);
    }

    if (newFiles.length > 0) {
      setFiles((prev) => [...prev, ...newFiles]);
      onFilesSelected?.(fileArray.filter((_, i) => i < newFiles.length));
      newFiles.forEach((file) => onFileImported?.(file));
    }
  }, [acceptedFormats, maxFileSize, onFilesSelected, onFileImported, t]);

  /**
   * Handle drag over
   */
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) {
      setIsDragOver(true);
    }
  }, [disabled]);

  /**
   * Handle drag leave
   */
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  /**
   * Handle drop
   */
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (disabled) return;

    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length > 0) {
      if (!multiple && droppedFiles.length > 1) {
        setError(t('dataCenter.singleFileOnly'));
        return;
      }
      processFiles(droppedFiles);
    }
  }, [disabled, multiple, processFiles, t]);

  /**
   * Handle click to open file dialog
   */
  const handleClick = useCallback(() => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, [disabled]);

  /**
   * Handle file input change
   */
  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      processFiles(selectedFiles);
    }
    // Reset input value to allow selecting the same file again
    e.target.value = '';
  }, [processFiles]);

  /**
   * Remove file from list
   */
  const handleRemoveFile = useCallback((fileId: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== fileId));
  }, []);

  /**
   * Clear all files
   */
  const handleClearAll = useCallback(() => {
    setFiles([]);
    setError(null);
  }, []);

  /**
   * Get accepted file extensions for input
   */
  const getAcceptedExtensions = (): string => {
    const extensions: string[] = [];
    if (acceptedFormats.includes(DataFormat.CSV)) {
      extensions.push('.csv');
    }
    if (acceptedFormats.includes(DataFormat.EXCEL)) {
      extensions.push('.xlsx', '.xls');
    }
    if (acceptedFormats.includes(DataFormat.PARQUET)) {
      extensions.push('.parquet');
    }
    return extensions.join(',');
  };

  /**
   * Get status icon
   */
  const getStatusIcon = (status: ImportStatus): string => {
    switch (status) {
      case ImportStatus.IDLE:
        return '⏳';
      case ImportStatus.UPLOADING:
      case ImportStatus.ANALYZING:
      case ImportStatus.CLEANING:
      case ImportStatus.IMPORTING:
        return '🔄';
      case ImportStatus.COMPLETED:
        return '✅';
      case ImportStatus.ERROR:
        return '❌';
      default:
        return '📄';
    }
  };

  return (
    <div className="file-dropzone-container">
      {/* Dropzone Area */}
      <div
        className={`file-dropzone ${isDragOver ? 'drag-over' : ''} ${disabled ? 'disabled' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={t('dataCenter.dropzoneLabel')}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="file-input-hidden"
          accept={getAcceptedExtensions()}
          multiple={multiple}
          onChange={handleFileInputChange}
          disabled={disabled}
        />
        
        <div className="dropzone-content">
          <div className="dropzone-icon">📁</div>
          <div className="dropzone-text">
            <p className="dropzone-title">{t('dataCenter.dropzoneTitle')}</p>
            <p className="dropzone-subtitle">{t('dataCenter.dropzoneSubtitle')}</p>
          </div>
          <div className="dropzone-formats">
            {acceptedFormats.map((format) => (
              <span key={format} className="format-badge">
                {getFormatIcon(format)} {getFormatLabel(format)}
              </span>
            ))}
          </div>
          <p className="dropzone-size-limit">
            {t('dataCenter.maxFileSize', { size: formatFileSize(maxFileSize) })}
          </p>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="dropzone-error">
          <span className="error-icon">⚠️</span>
          <span className="error-text">{error}</span>
          <button 
            className="error-dismiss" 
            onClick={() => setError(null)}
            aria-label={t('dataCenter.dismissError')}
          >
            ✕
          </button>
        </div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="file-list">
          <div className="file-list-header">
            <h4 className="file-list-title">
              {t('dataCenter.selectedFiles', { count: files.length })}
            </h4>
            <button 
              className="clear-all-btn"
              onClick={handleClearAll}
            >
              {t('dataCenter.clearAll')}
            </button>
          </div>
          
          <div className="file-list-items">
            {files.map((file) => (
              <div key={file.id} className={`file-item ${file.status}`}>
                <div className="file-icon">
                  {getFormatIcon(file.format)}
                </div>
                <div className="file-info">
                  <span className="file-name">{file.name}</span>
                  <span className="file-meta">
                    {getFormatLabel(file.format)} • {formatFileSize(file.size)}
                  </span>
                </div>
                <div className="file-status">
                  <span className="status-icon">{getStatusIcon(file.status)}</span>
                  {file.status === ImportStatus.UPLOADING && (
                    <div className="progress-bar">
                      <div 
                        className="progress-fill" 
                        style={{ width: `${file.progress}%` }}
                      />
                    </div>
                  )}
                </div>
                <button
                  className="file-remove-btn"
                  onClick={() => handleRemoveFile(file.id)}
                  aria-label={t('dataCenter.removeFile', { name: file.name })}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FileDropzone;
