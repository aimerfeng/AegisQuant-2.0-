/**
 * Layout Toolbar Component
 * 
 * Provides controls for saving, loading, and managing layout presets.
 * Requirements: 4.3, 4.4
 */

import React, { useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useLayoutStore } from '../stores/layoutStore';
import { downloadLayoutAsFile, readLayoutFromFile } from '../utils/layoutPersistence';
import './LayoutToolbar.css';

const LayoutToolbar: React.FC = () => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showPresetMenu, setShowPresetMenu] = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [presetName, setPresetName] = useState('');
  const [presetDescription, setPresetDescription] = useState('');
  const [notification, setNotification] = useState<string | null>(null);

  const {
    presets,
    activePresetId,
    currentLayoutConfig,
    saveCurrentLayout,
    loadPreset,
    deletePreset,
    getDefaultLayout,
    setCurrentLayoutConfig,
    exportLayout,
    importLayout,
  } = useLayoutStore();

  /**
   * Show notification message
   */
  const showNotification = useCallback((message: string) => {
    setNotification(message);
    setTimeout(() => setNotification(null), 3000);
  }, []);

  /**
   * Handle save preset
   */
  const handleSavePreset = useCallback(() => {
    if (!presetName.trim()) return;

    try {
      saveCurrentLayout(presetName.trim(), presetDescription.trim() || undefined);
      showNotification(t('layout.layoutSaved'));
      setShowSaveDialog(false);
      setPresetName('');
      setPresetDescription('');
    } catch (error) {
      console.error('Failed to save preset:', error);
    }
  }, [presetName, presetDescription, saveCurrentLayout, showNotification, t]);

  /**
   * Handle load preset
   */
  const handleLoadPreset = useCallback((presetId: string) => {
    const config = loadPreset(presetId);
    if (config) {
      showNotification(t('layout.layoutLoaded'));
    }
    setShowPresetMenu(false);
  }, [loadPreset, showNotification, t]);

  /**
   * Handle delete preset
   */
  const handleDeletePreset = useCallback((presetId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    if (deletePreset(presetId)) {
      showNotification(t('layout.layoutDeleted'));
    }
  }, [deletePreset, showNotification, t]);

  /**
   * Handle reset layout
   */
  const handleResetLayout = useCallback(() => {
    const defaultConfig = getDefaultLayout();
    setCurrentLayoutConfig(defaultConfig);
    showNotification(t('layout.layoutLoaded'));
    setShowPresetMenu(false);
  }, [getDefaultLayout, setCurrentLayoutConfig, showNotification, t]);

  /**
   * Handle export layout
   */
  const handleExportLayout = useCallback(() => {
    const data = exportLayout();
    downloadLayoutAsFile(data);
    showNotification(t('layout.layoutExported'));
  }, [exportLayout, showNotification, t]);

  /**
   * Handle import layout
   */
  const handleImportClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  /**
   * Handle file selection for import
   */
  const handleFileChange = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const data = await readLayoutFromFile(file);
    if (data && importLayout(data)) {
      showNotification(t('layout.layoutImported'));
    } else {
      showNotification(t('layout.layoutImportError'));
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [importLayout, showNotification, t]);

  return (
    <div className="layout-toolbar-container">
      {/* Preset Menu Button */}
      <div className="toolbar-dropdown">
        <button
          className="toolbar-button"
          onClick={() => setShowPresetMenu(!showPresetMenu)}
          title={t('layout.presets')}
        >
          <span className="button-icon">📐</span>
          <span className="button-text">{t('layout.presets')}</span>
          <span className="dropdown-arrow">▼</span>
        </button>

        {showPresetMenu && (
          <div className="dropdown-menu">
            {/* Preset List */}
            <div className="preset-list">
              {presets.length === 0 ? (
                <div className="no-presets">{t('layout.noPresets')}</div>
              ) : (
                presets.map((preset) => (
                  <div
                    key={preset.id}
                    className={`preset-item ${preset.id === activePresetId ? 'active' : ''}`}
                    onClick={() => handleLoadPreset(preset.id)}
                  >
                    <div className="preset-info">
                      <span className="preset-name">{preset.name}</span>
                      {preset.description && (
                        <span className="preset-description">{preset.description}</span>
                      )}
                    </div>
                    <button
                      className="preset-delete"
                      onClick={(e) => handleDeletePreset(preset.id, e)}
                      title={t('layout.deletePreset')}
                    >
                      ✕
                    </button>
                  </div>
                ))
              )}
            </div>

            {/* Menu Actions */}
            <div className="menu-divider" />
            <button
              className="menu-item"
              onClick={() => {
                setShowSaveDialog(true);
                setShowPresetMenu(false);
              }}
            >
              <span className="menu-icon">💾</span>
              {t('layout.savePreset')}
            </button>
            <button className="menu-item" onClick={handleResetLayout}>
              <span className="menu-icon">🔄</span>
              {t('layout.resetLayout')}
            </button>
            <div className="menu-divider" />
            <button className="menu-item" onClick={handleExportLayout}>
              <span className="menu-icon">📤</span>
              {t('layout.exportLayout')}
            </button>
            <button className="menu-item" onClick={handleImportClick}>
              <span className="menu-icon">📥</span>
              {t('layout.importLayout')}
            </button>
          </div>
        )}
      </div>

      {/* Hidden file input for import */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {/* Save Dialog */}
      {showSaveDialog && (
        <div className="dialog-overlay" onClick={() => setShowSaveDialog(false)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <h3>{t('layout.savePreset')}</h3>
            <div className="dialog-content">
              <label>
                {t('layout.presetName')}
                <input
                  type="text"
                  value={presetName}
                  onChange={(e) => setPresetName(e.target.value)}
                  placeholder={t('layout.presetName')}
                  autoFocus
                />
              </label>
              <label>
                {t('layout.presetDescription')}
                <textarea
                  value={presetDescription}
                  onChange={(e) => setPresetDescription(e.target.value)}
                  placeholder={t('layout.presetDescription')}
                  rows={3}
                />
              </label>
            </div>
            <div className="dialog-actions">
              <button
                className="dialog-button cancel"
                onClick={() => setShowSaveDialog(false)}
              >
                {t('ui.cancel')}
              </button>
              <button
                className="dialog-button primary"
                onClick={handleSavePreset}
                disabled={!presetName.trim()}
              >
                {t('ui.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Notification */}
      {notification && (
        <div className="notification">
          {notification}
        </div>
      )}
    </div>
  );
};

export default LayoutToolbar;
