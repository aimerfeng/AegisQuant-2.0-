/**
 * Layout Persistence Utilities
 * 
 * Utilities for saving, loading, exporting, and importing layout configurations.
 * Requirements: 4.3, 4.4
 */

import { LayoutConfig } from 'golden-layout';
import {
  LayoutPersistenceData,
  WorkspacePreset,
  LAYOUT_VERSION,
  LAYOUT_STORAGE_KEY,
} from '../types/layout';

/**
 * Storage keys
 */
const PRESETS_STORAGE_KEY = `${LAYOUT_STORAGE_KEY}-presets`;
const CURRENT_LAYOUT_KEY = `${LAYOUT_STORAGE_KEY}-current`;

/**
 * Save layout configuration to localStorage
 */
export const saveLayoutToStorage = (config: LayoutConfig): boolean => {
  try {
    const data = JSON.stringify(config);
    localStorage.setItem(CURRENT_LAYOUT_KEY, data);
    return true;
  } catch (error) {
    console.error('Failed to save layout to storage:', error);
    return false;
  }
};

/**
 * Load layout configuration from localStorage
 */
export const loadLayoutFromStorage = (): LayoutConfig | null => {
  try {
    const data = localStorage.getItem(CURRENT_LAYOUT_KEY);
    if (!data) return null;
    return JSON.parse(data) as LayoutConfig;
  } catch (error) {
    console.error('Failed to load layout from storage:', error);
    return null;
  }
};

/**
 * Save presets to localStorage
 */
export const savePresetsToStorage = (presets: WorkspacePreset[]): boolean => {
  try {
    const data = JSON.stringify(presets);
    localStorage.setItem(PRESETS_STORAGE_KEY, data);
    return true;
  } catch (error) {
    console.error('Failed to save presets to storage:', error);
    return false;
  }
};

/**
 * Load presets from localStorage
 */
export const loadPresetsFromStorage = (): WorkspacePreset[] => {
  try {
    const data = localStorage.getItem(PRESETS_STORAGE_KEY);
    if (!data) return [];
    return JSON.parse(data) as WorkspacePreset[];
  } catch (error) {
    console.error('Failed to load presets from storage:', error);
    return [];
  }
};

/**
 * Export layout data to JSON string
 */
export const exportLayoutToJson = (data: LayoutPersistenceData): string => {
  return JSON.stringify(data, null, 2);
};

/**
 * Import layout data from JSON string
 */
export const importLayoutFromJson = (jsonString: string): LayoutPersistenceData | null => {
  try {
    const data = JSON.parse(jsonString) as LayoutPersistenceData;
    
    // Validate structure
    if (!data.version) {
      console.error('Invalid layout data: missing version');
      return null;
    }
    
    // Version compatibility check
    if (data.version !== LAYOUT_VERSION) {
      console.warn(`Layout version mismatch: expected ${LAYOUT_VERSION}, got ${data.version}`);
      // Still allow import but log warning
    }
    
    return data;
  } catch (error) {
    console.error('Failed to parse layout JSON:', error);
    return null;
  }
};

/**
 * Download layout data as JSON file
 */
export const downloadLayoutAsFile = (data: LayoutPersistenceData, filename?: string): void => {
  const jsonString = exportLayoutToJson(data);
  const blob = new Blob([jsonString], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  
  const link = document.createElement('a');
  link.href = url;
  link.download = filename || `titan-quant-layout-${Date.now()}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  URL.revokeObjectURL(url);
};

/**
 * Read layout data from uploaded file
 */
export const readLayoutFromFile = (file: File): Promise<LayoutPersistenceData | null> => {
  return new Promise((resolve) => {
    const reader = new FileReader();
    
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        const data = importLayoutFromJson(content);
        resolve(data);
      } else {
        resolve(null);
      }
    };
    
    reader.onerror = () => {
      console.error('Failed to read file');
      resolve(null);
    };
    
    reader.readAsText(file);
  });
};

/**
 * Clear all layout data from storage
 */
export const clearLayoutStorage = (): void => {
  localStorage.removeItem(CURRENT_LAYOUT_KEY);
  localStorage.removeItem(PRESETS_STORAGE_KEY);
  localStorage.removeItem(LAYOUT_STORAGE_KEY);
};

/**
 * Validate layout configuration structure
 */
export const isValidLayoutConfig = (config: unknown): config is LayoutConfig => {
  if (!config || typeof config !== 'object') return false;
  const layoutConfig = config as LayoutConfig;
  return layoutConfig.root !== undefined;
};

/**
 * Create a deep clone of layout configuration
 */
export const cloneLayoutConfig = (config: LayoutConfig): LayoutConfig => {
  return JSON.parse(JSON.stringify(config));
};

/**
 * Merge two layout configurations (for partial updates)
 */
export const mergeLayoutConfigs = (
  base: LayoutConfig,
  override: Partial<LayoutConfig>
): LayoutConfig => {
  return {
    ...base,
    ...override,
    root: override.root || base.root,
    header: {
      ...base.header,
      ...override.header,
    },
  };
};
