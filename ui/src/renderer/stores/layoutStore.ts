/**
 * Titan-Quant Layout Store
 * 
 * Zustand store for managing Golden-Layout workspace state and persistence.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { LayoutConfig, ItemType, ComponentItemConfig } from 'golden-layout';
import {
  PanelType,
  PanelRegistration,
  WorkspacePreset,
  LayoutPersistenceData,
  LayoutStoreState,
  LAYOUT_VERSION,
  LAYOUT_STORAGE_KEY,
} from '../types/layout';

/**
 * Generate unique ID for presets
 */
const generatePresetId = (): string => {
  return `preset-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * Create default layout configuration
 */
const createDefaultLayout = (): LayoutConfig => ({
  root: {
    type: ItemType.row,
    content: [
      // Left sidebar - Strategies & Positions
      {
        type: ItemType.column,
        width: 15,
        content: [
          {
            type: ItemType.component,
            componentType: PanelType.POSITIONS,
            title: 'Positions',
            componentState: {},
          } as ComponentItemConfig,
        ],
      },
      // Main content area
      {
        type: ItemType.column,
        width: 60,
        content: [
          // Chart area
          {
            type: ItemType.component,
            componentType: PanelType.KLINE_CHART,
            title: 'K-Line Chart',
            height: 70,
            componentState: {},
          } as ComponentItemConfig,
          // Log panel
          {
            type: ItemType.component,
            componentType: PanelType.LOG_PANEL,
            title: 'Logs',
            height: 30,
            componentState: {},
          } as ComponentItemConfig,
        ],
      },
      // Right sidebar - Order Book
      {
        type: ItemType.column,
        width: 25,
        content: [
          {
            type: ItemType.component,
            componentType: PanelType.ORDER_BOOK,
            title: 'Order Book',
            componentState: {},
          } as ComponentItemConfig,
        ],
      },
    ],
  },
  header: {
    popout: false,
    maximise: true,
    close: true,
    minimise: false,
  },
});

/**
 * Validate layout configuration structure
 */
const isValidLayoutConfig = (config: unknown): config is LayoutConfig => {
  if (!config || typeof config !== 'object') return false;
  const layoutConfig = config as LayoutConfig;
  return layoutConfig.root !== undefined;
};

/**
 * Layout store implementation
 */
export const useLayoutStore = create<LayoutStoreState>()(
  persist(
    (set, get) => ({
      // Initial state
      isLayoutReady: false,
      currentLayoutConfig: null,
      presets: [],
      activePresetId: null,
      registeredPanels: new Map<PanelType, PanelRegistration>(),

      // Actions
      setLayoutReady: (ready: boolean) => {
        set({ isLayoutReady: ready });
      },

      setCurrentLayoutConfig: (config: LayoutConfig | null) => {
        set({ currentLayoutConfig: config });
      },

      saveCurrentLayout: (name: string, description?: string): string => {
        const { currentLayoutConfig, presets } = get();
        
        if (!currentLayoutConfig) {
          throw new Error('No current layout to save');
        }

        const presetId = generatePresetId();
        const now = Date.now();
        
        const newPreset: WorkspacePreset = {
          id: presetId,
          name,
          description,
          layoutConfig: JSON.parse(JSON.stringify(currentLayoutConfig)), // Deep clone
          createdAt: now,
          updatedAt: now,
        };

        set({ 
          presets: [...presets, newPreset],
          activePresetId: presetId,
        });

        return presetId;
      },

      loadPreset: (presetId: string): LayoutConfig | null => {
        const { presets } = get();
        const preset = presets.find(p => p.id === presetId);
        
        if (!preset) {
          return null;
        }

        set({ 
          activePresetId: presetId,
          currentLayoutConfig: JSON.parse(JSON.stringify(preset.layoutConfig)),
        });

        return preset.layoutConfig;
      },

      deletePreset: (presetId: string): boolean => {
        const { presets, activePresetId } = get();
        const presetIndex = presets.findIndex(p => p.id === presetId);
        
        if (presetIndex === -1) {
          return false;
        }

        const newPresets = presets.filter(p => p.id !== presetId);
        const newActiveId = activePresetId === presetId ? null : activePresetId;

        set({ 
          presets: newPresets,
          activePresetId: newActiveId,
        });

        return true;
      },

      updatePreset: (presetId: string, config: Partial<WorkspacePreset>): boolean => {
        const { presets } = get();
        const presetIndex = presets.findIndex(p => p.id === presetId);
        
        if (presetIndex === -1) {
          return false;
        }

        const updatedPresets = [...presets];
        updatedPresets[presetIndex] = {
          ...updatedPresets[presetIndex],
          ...config,
          updatedAt: Date.now(),
        };

        set({ presets: updatedPresets });
        return true;
      },

      registerPanel: (registration: PanelRegistration) => {
        const { registeredPanels } = get();
        const newPanels = new Map(registeredPanels);
        newPanels.set(registration.type, registration);
        set({ registeredPanels: newPanels });
      },

      unregisterPanel: (type: PanelType) => {
        const { registeredPanels } = get();
        const newPanels = new Map(registeredPanels);
        newPanels.delete(type);
        set({ registeredPanels: newPanels });
      },

      getDefaultLayout: (): LayoutConfig => {
        return createDefaultLayout();
      },

      exportLayout: (): LayoutPersistenceData => {
        const { currentLayoutConfig, presets, activePresetId } = get();
        return {
          version: LAYOUT_VERSION,
          currentLayoutConfig,
          presets,
          activePresetId,
        };
      },

      importLayout: (data: LayoutPersistenceData): boolean => {
        // Version check
        if (data.version !== LAYOUT_VERSION) {
          console.warn(`Layout version mismatch: expected ${LAYOUT_VERSION}, got ${data.version}`);
          // For now, we'll still try to import but log a warning
        }

        // Validate layout config if present
        if (data.currentLayoutConfig && !isValidLayoutConfig(data.currentLayoutConfig)) {
          console.error('Invalid layout configuration in import data');
          return false;
        }

        // Validate presets
        const validPresets = data.presets.filter(preset => 
          preset.id && 
          preset.name && 
          isValidLayoutConfig(preset.layoutConfig)
        );

        set({
          currentLayoutConfig: data.currentLayoutConfig,
          presets: validPresets,
          activePresetId: data.activePresetId,
        });

        return true;
      },
    }),
    {
      name: LAYOUT_STORAGE_KEY,
      partialize: (state) => ({
        currentLayoutConfig: state.currentLayoutConfig,
        presets: state.presets,
        activePresetId: state.activePresetId,
      }),
      // Don't persist the Map, it will be rebuilt on app start
      merge: (persistedState, currentState) => ({
        ...currentState,
        ...(persistedState as Partial<LayoutStoreState>),
        registeredPanels: new Map(),
      }),
    }
  )
);

export default useLayoutStore;
