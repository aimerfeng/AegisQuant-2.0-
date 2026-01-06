/**
 * Titan-Quant Layout Types
 * 
 * Type definitions for Golden-Layout integration and workspace management.
 */

import { ComponentItemConfig, LayoutConfig, ItemConfig } from 'golden-layout';

/**
 * Supported panel component types
 */
export enum PanelType {
  KLINE_CHART = 'kline-chart',
  ORDER_BOOK = 'order-book',
  STRATEGY_LAB = 'strategy-lab',
  LOG_PANEL = 'log-panel',
  POSITIONS = 'positions',
  TRADES = 'trades',
  CONTROL_PANEL = 'control-panel',
  DATA_CENTER = 'data-center',
  REPORTS = 'reports',
}

/**
 * Panel component configuration
 */
export interface PanelConfig {
  type: PanelType;
  title: string;
  componentState?: Record<string, unknown>;
  isClosable?: boolean;
  reorderEnabled?: boolean;
}

/**
 * Workspace preset configuration
 */
export interface WorkspacePreset {
  id: string;
  name: string;
  description?: string;
  layoutConfig: LayoutConfig;
  createdAt: number;
  updatedAt: number;
}

/**
 * Layout persistence data
 */
export interface LayoutPersistenceData {
  version: string;
  currentLayoutConfig: LayoutConfig | null;
  presets: WorkspacePreset[];
  activePresetId: string | null;
}

/**
 * Panel registration entry
 */
export interface PanelRegistration {
  type: PanelType;
  title: string;
  defaultConfig?: Partial<ComponentItemConfig>;
  component: React.ComponentType<PanelComponentProps>;
}

/**
 * Props passed to panel components
 */
export interface PanelComponentProps {
  glContainer?: unknown;
  glEventHub?: unknown;
  title?: string;
  componentState?: Record<string, unknown>;
}

/**
 * Layout store state
 */
export interface LayoutStoreState {
  // Current layout state
  isLayoutReady: boolean;
  currentLayoutConfig: LayoutConfig | null;
  
  // Presets
  presets: WorkspacePreset[];
  activePresetId: string | null;
  
  // Panel registry
  registeredPanels: Map<PanelType, PanelRegistration>;
  
  // Actions
  setLayoutReady: (ready: boolean) => void;
  setCurrentLayoutConfig: (config: LayoutConfig | null) => void;
  saveCurrentLayout: (name: string, description?: string) => string;
  loadPreset: (presetId: string) => LayoutConfig | null;
  deletePreset: (presetId: string) => boolean;
  updatePreset: (presetId: string, config: Partial<WorkspacePreset>) => boolean;
  registerPanel: (registration: PanelRegistration) => void;
  unregisterPanel: (type: PanelType) => void;
  getDefaultLayout: () => LayoutConfig;
  exportLayout: () => LayoutPersistenceData;
  importLayout: (data: LayoutPersistenceData) => boolean;
}

/**
 * Default layout configuration version
 */
export const LAYOUT_VERSION = '1.0.0';

/**
 * Local storage key for layout persistence
 */
export const LAYOUT_STORAGE_KEY = 'titan-quant-layout';
