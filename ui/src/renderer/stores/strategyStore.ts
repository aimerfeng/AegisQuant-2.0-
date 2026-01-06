/**
 * Titan-Quant Strategy Store
 * 
 * Zustand store for managing strategy state and synchronization.
 * Handles strategy loading, parameter management, and hot reload.
 * 
 * Requirements:
 * - 8.1: Strategy_Lab SHALL provide Monaco Editor with Python syntax highlighting
 * - 8.2: WHEN strategy class defines parameters dict, Strategy_Lab SHALL auto-map to UI form
 * - 8.3: WHEN user modifies strategy code and clicks Reload, Strategy_Lab SHALL execute hot reload
 * - 8.4: WHEN hot reload executes, Strategy_Lab SHALL log reload mode and affected variables
 * - 8.5: IF hot reload causes state inconsistency, Strategy_Lab SHALL provide rollback option
 * - 8.6: Strategy_Lab SHALL provide strategy templates (CtaTemplate)
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  HotReloadPolicy,
  StrategyParameter,
  StrategyMetadata,
  ReloadResult,
  StrategyFile,
} from '../components/StrategyLab/types';

/**
 * Strategy status enum
 */
export enum StrategyStatus {
  UNLOADED = 'unloaded',
  LOADING = 'loading',
  LOADED = 'loaded',
  RUNNING = 'running',
  STOPPED = 'stopped',
  ERROR = 'error',
}

/**
 * Strategy instance state
 */
export interface StrategyInstance {
  strategyId: string;
  name: string;
  className: string;
  status: StrategyStatus;
  parameters: Record<string, unknown>;
  stateVariables: Record<string, unknown>;
  preservedVariables: string[];
  lastReloadResult?: ReloadResult;
  error?: string;
}

/**
 * Strategy store state
 */
interface StrategyState {
  // Available strategies
  availableStrategies: StrategyMetadata[];
  
  // Active strategy instances
  activeStrategies: Map<string, StrategyInstance>;
  
  // Currently selected strategy for editing
  selectedStrategyId: string | null;
  
  // Strategy files (for code editor)
  openFiles: Map<string, StrategyFile>;
  activeFileId: string | null;
  
  // Hot reload state
  isReloading: boolean;
  reloadHistory: ReloadResult[];
  
  // Loading state
  isLoading: boolean;
  error: string | null;
}

/**
 * Strategy store actions
 */
interface StrategyActions {
  // Strategy management
  setAvailableStrategies: (strategies: StrategyMetadata[]) => void;
  addStrategy: (strategy: StrategyMetadata) => void;
  removeStrategy: (strategyId: string) => void;
  
  // Strategy selection
  selectStrategy: (strategyId: string | null) => void;
  
  // Strategy instance management
  loadStrategy: (strategyId: string, params?: Record<string, unknown>) => void;
  unloadStrategy: (strategyId: string) => void;
  setStrategyStatus: (strategyId: string, status: StrategyStatus) => void;
  setStrategyError: (strategyId: string, error: string | null) => void;
  
  // Parameter management
  updateParameter: (strategyId: string, paramName: string, value: unknown) => void;
  updateParameters: (strategyId: string, params: Record<string, unknown>) => void;
  resetParameters: (strategyId: string) => void;
  
  // State variable management
  updateStateVariables: (strategyId: string, variables: Record<string, unknown>) => void;
  setPreservedVariables: (strategyId: string, variables: string[]) => void;
  
  // Hot reload
  startReload: (strategyId: string, policy: HotReloadPolicy, preserveVars?: string[]) => void;
  completeReload: (strategyId: string, result: ReloadResult) => void;
  rollback: (strategyId: string) => void;
  
  // File management
  openFile: (file: StrategyFile) => void;
  closeFile: (fileId: string) => void;
  setActiveFile: (fileId: string | null) => void;
  updateFileContent: (fileId: string, content: string) => void;
  markFileSaved: (fileId: string) => void;
  
  // Loading state
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  // Getters
  getStrategy: (strategyId: string) => StrategyInstance | undefined;
  getStrategyMetadata: (strategyId: string) => StrategyMetadata | undefined;
  getActiveFile: () => StrategyFile | undefined;
}

/**
 * Initial state
 */
const initialState: StrategyState = {
  availableStrategies: [],
  activeStrategies: new Map(),
  selectedStrategyId: null,
  openFiles: new Map(),
  activeFileId: null,
  isReloading: false,
  reloadHistory: [],
  isLoading: false,
  error: null,
};

/**
 * Strategy store implementation
 */
export const useStrategyStore = create<StrategyState & StrategyActions>()(
  persist(
    (set, get) => ({
      ...initialState,

      // Strategy management
      setAvailableStrategies: (strategies: StrategyMetadata[]) => {
        set({ availableStrategies: strategies });
      },

      addStrategy: (strategy: StrategyMetadata) => {
        set((state) => ({
          availableStrategies: [...state.availableStrategies, strategy],
        }));
      },

      removeStrategy: (strategyId: string) => {
        set((state) => ({
          availableStrategies: state.availableStrategies.filter(
            s => s.strategyId !== strategyId
          ),
        }));
      },

      // Strategy selection
      selectStrategy: (strategyId: string | null) => {
        set({ selectedStrategyId: strategyId });
      },

      // Strategy instance management
      loadStrategy: (strategyId: string, params?: Record<string, unknown>) => {
        const metadata = get().availableStrategies.find(s => s.strategyId === strategyId);
        if (!metadata) {
          set({ error: `Strategy ${strategyId} not found` });
          return;
        }

        const defaultParams: Record<string, unknown> = {};
        metadata.parameters.forEach(p => {
          defaultParams[p.name] = p.defaultValue;
        });

        const instance: StrategyInstance = {
          strategyId,
          name: metadata.name,
          className: metadata.className,
          status: StrategyStatus.LOADING,
          parameters: { ...defaultParams, ...params },
          stateVariables: {},
          preservedVariables: [],
        };

        set((state) => {
          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, instance);
          return { activeStrategies: newStrategies };
        });
      },

      unloadStrategy: (strategyId: string) => {
        set((state) => {
          const newStrategies = new Map(state.activeStrategies);
          newStrategies.delete(strategyId);
          return { 
            activeStrategies: newStrategies,
            selectedStrategyId: state.selectedStrategyId === strategyId 
              ? null 
              : state.selectedStrategyId,
          };
        });
      },

      setStrategyStatus: (strategyId: string, status: StrategyStatus) => {
        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return state;

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, { ...strategy, status });
          return { activeStrategies: newStrategies };
        });
      },

      setStrategyError: (strategyId: string, error: string | null) => {
        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return state;

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, { 
            ...strategy, 
            error: error || undefined,
            status: error ? StrategyStatus.ERROR : strategy.status,
          });
          return { activeStrategies: newStrategies };
        });
      },

      // Parameter management
      updateParameter: (strategyId: string, paramName: string, value: unknown) => {
        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return state;

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, {
            ...strategy,
            parameters: { ...strategy.parameters, [paramName]: value },
          });
          return { activeStrategies: newStrategies };
        });
      },

      updateParameters: (strategyId: string, params: Record<string, unknown>) => {
        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return state;

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, {
            ...strategy,
            parameters: { ...strategy.parameters, ...params },
          });
          return { activeStrategies: newStrategies };
        });
      },

      resetParameters: (strategyId: string) => {
        const metadata = get().availableStrategies.find(s => s.strategyId === strategyId);
        if (!metadata) return;

        const defaultParams: Record<string, unknown> = {};
        metadata.parameters.forEach(p => {
          defaultParams[p.name] = p.defaultValue;
        });

        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return state;

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, {
            ...strategy,
            parameters: defaultParams,
          });
          return { activeStrategies: newStrategies };
        });
      },

      // State variable management
      updateStateVariables: (strategyId: string, variables: Record<string, unknown>) => {
        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return state;

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, {
            ...strategy,
            stateVariables: { ...strategy.stateVariables, ...variables },
          });
          return { activeStrategies: newStrategies };
        });
      },

      setPreservedVariables: (strategyId: string, variables: string[]) => {
        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return state;

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, {
            ...strategy,
            preservedVariables: variables,
          });
          return { activeStrategies: newStrategies };
        });
      },

      // Hot reload
      startReload: (strategyId: string, _policy: HotReloadPolicy, _preserveVars?: string[]) => {
        set({ isReloading: true });
        
        // Update strategy status
        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return state;

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, {
            ...strategy,
            status: StrategyStatus.LOADING,
          });
          return { activeStrategies: newStrategies };
        });
      },

      completeReload: (strategyId: string, result: ReloadResult) => {
        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return { isReloading: false };

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, {
            ...strategy,
            status: result.success ? StrategyStatus.LOADED : StrategyStatus.ERROR,
            lastReloadResult: result,
            error: result.errorMessage,
          });

          return {
            activeStrategies: newStrategies,
            isReloading: false,
            reloadHistory: [...state.reloadHistory.slice(-19), result], // Keep last 20
          };
        });
      },

      rollback: (strategyId: string) => {
        // Rollback is handled by the backend, we just update the UI state
        set((state) => {
          const strategy = state.activeStrategies.get(strategyId);
          if (!strategy) return state;

          const newStrategies = new Map(state.activeStrategies);
          newStrategies.set(strategyId, {
            ...strategy,
            status: StrategyStatus.LOADING,
            lastReloadResult: undefined,
          });
          return { activeStrategies: newStrategies };
        });
      },

      // File management
      openFile: (file: StrategyFile) => {
        set((state) => {
          const newFiles = new Map(state.openFiles);
          newFiles.set(file.path, file);
          return { 
            openFiles: newFiles,
            activeFileId: file.path,
          };
        });
      },

      closeFile: (fileId: string) => {
        set((state) => {
          const newFiles = new Map(state.openFiles);
          newFiles.delete(fileId);
          
          // If closing active file, select another one
          let newActiveId = state.activeFileId;
          if (state.activeFileId === fileId) {
            const remainingFiles = Array.from(newFiles.keys());
            newActiveId = remainingFiles.length > 0 ? remainingFiles[0] : null;
          }
          
          return { 
            openFiles: newFiles,
            activeFileId: newActiveId,
          };
        });
      },

      setActiveFile: (fileId: string | null) => {
        set({ activeFileId: fileId });
      },

      updateFileContent: (fileId: string, content: string) => {
        set((state) => {
          const file = state.openFiles.get(fileId);
          if (!file) return state;

          const newFiles = new Map(state.openFiles);
          newFiles.set(fileId, {
            ...file,
            content,
            isModified: true,
          });
          return { openFiles: newFiles };
        });
      },

      markFileSaved: (fileId: string) => {
        set((state) => {
          const file = state.openFiles.get(fileId);
          if (!file) return state;

          const newFiles = new Map(state.openFiles);
          newFiles.set(fileId, {
            ...file,
            isModified: false,
            lastSaved: Date.now(),
          });
          return { openFiles: newFiles };
        });
      },

      // Loading state
      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },

      setError: (error: string | null) => {
        set({ error });
      },

      // Getters
      getStrategy: (strategyId: string) => {
        return get().activeStrategies.get(strategyId);
      },

      getStrategyMetadata: (strategyId: string) => {
        return get().availableStrategies.find(s => s.strategyId === strategyId);
      },

      getActiveFile: () => {
        const { openFiles, activeFileId } = get();
        return activeFileId ? openFiles.get(activeFileId) : undefined;
      },
    }),
    {
      name: 'titan-quant-strategy',
      partialize: (state) => ({
        // Only persist available strategies and selected strategy
        availableStrategies: state.availableStrategies,
        selectedStrategyId: state.selectedStrategyId,
      }),
      // Don't persist Maps, they will be rebuilt
      merge: (persistedState, currentState) => ({
        ...currentState,
        ...(persistedState as Partial<StrategyState>),
        activeStrategies: new Map(),
        openFiles: new Map(),
      }),
    }
  )
);

/**
 * Hook to get available strategies
 */
export const useAvailableStrategies = () => 
  useStrategyStore((state) => state.availableStrategies);

/**
 * Hook to get selected strategy
 */
export const useSelectedStrategy = () => {
  const selectedId = useStrategyStore((state) => state.selectedStrategyId);
  const getStrategy = useStrategyStore((state) => state.getStrategy);
  return selectedId ? getStrategy(selectedId) : undefined;
};

/**
 * Hook to get active strategies
 */
export const useActiveStrategies = () => 
  useStrategyStore((state) => Array.from(state.activeStrategies.values()));

/**
 * Hook to check if reloading
 */
export const useIsReloading = () => useStrategyStore((state) => state.isReloading);

export default useStrategyStore;
