/**
 * Titan-Quant Workspace Layout Component
 * 
 * Integrates Golden-Layout for multi-window drag-and-drop layout management.
 * Supports window docking, splitting, and layout persistence.
 * 
 * Requirements: 4.1, 4.2
 */

import React, { useEffect, useRef, useCallback, useState } from 'react';
import { createRoot, Root } from 'react-dom/client';
import {
  GoldenLayout,
  LayoutConfig,
  ComponentContainer,
  JsonValue,
  ResolvedComponentItemConfig,
} from 'golden-layout';
import { useTranslation } from 'react-i18next';
import { useLayoutStore } from '../stores/layoutStore';
import { PanelType, PanelComponentProps } from '../types/layout';
import { getPanelComponent } from '../components/panels/panelFactory';
import './WorkspaceLayout.css';

/**
 * Component wrapper for Golden-Layout
 * Handles React component mounting/unmounting within GL containers
 */
interface ComponentRef {
  root: Root;
  container: ComponentContainer;
}

const WorkspaceLayout: React.FC = () => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const goldenLayoutRef = useRef<GoldenLayout | null>(null);
  const componentRefs = useRef<Map<string, ComponentRef>>(new Map());
  const [isInitialized, setIsInitialized] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    currentLayoutConfig,
    setCurrentLayoutConfig,
    setLayoutReady,
    getDefaultLayout,
  } = useLayoutStore();

  /**
   * Create a unique ID for component instances
   */
  const createComponentId = useCallback((): string => {
    return `gl-component-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  /**
   * Bind component to Golden-Layout container
   */
  const bindComponent = useCallback((
    container: ComponentContainer,
    itemConfig: ResolvedComponentItemConfig
  ): void => {
    const componentType = itemConfig.componentType as PanelType;
    const componentId = createComponentId();
    
    // Get the React component for this panel type
    const PanelComponent = getPanelComponent(componentType);
    
    // Create container element
    const containerElement = document.createElement('div');
    containerElement.className = 'gl-component-container';
    containerElement.id = componentId;
    container.element.appendChild(containerElement);

    // Create React root and render component
    const root = createRoot(containerElement);
    
    const props: PanelComponentProps = {
      glContainer: container,
      glEventHub: goldenLayoutRef.current?.eventHub,
      title: itemConfig.title,
      componentState: itemConfig.componentState as Record<string, unknown>,
    };

    root.render(<PanelComponent {...props} />);

    // Store reference for cleanup
    componentRefs.current.set(componentId, { root, container });

    // Handle container destruction
    container.on('beforeComponentRelease', () => {
      const ref = componentRefs.current.get(componentId);
      if (ref) {
        ref.root.unmount();
        componentRefs.current.delete(componentId);
      }
    });
  }, [createComponentId]);

  /**
   * Unbind component from Golden-Layout container
   */
  const unbindComponent = useCallback((container: ComponentContainer): void => {
    // Find and cleanup the component
    componentRefs.current.forEach((ref, id) => {
      if (ref.container === container) {
        ref.root.unmount();
        componentRefs.current.delete(id);
      }
    });
  }, []);

  /**
   * Handle layout state changes
   */
  const handleLayoutStateChanged = useCallback((): void => {
    if (goldenLayoutRef.current) {
      try {
        const config = goldenLayoutRef.current.saveLayout();
        setCurrentLayoutConfig(config);
      } catch (err) {
        console.error('Failed to save layout state:', err);
      }
    }
  }, [setCurrentLayoutConfig]);

  /**
   * Initialize Golden-Layout
   */
  const initializeLayout = useCallback((): void => {
    if (!containerRef.current) {
      setError('Container element not found');
      return;
    }

    try {
      // Get layout config (use saved or default)
      const layoutConfig = currentLayoutConfig || getDefaultLayout();

      // Create Golden-Layout instance
      const goldenLayout = new GoldenLayout(
        containerRef.current,
        bindComponent,
        unbindComponent
      );

      // Store reference
      goldenLayoutRef.current = goldenLayout;

      // Register all panel component types
      Object.values(PanelType).forEach((panelType) => {
        goldenLayout.registerComponentConstructor(panelType, () => {
          // This is handled by bindComponent
        });
      });

      // Listen for state changes
      goldenLayout.on('stateChanged', handleLayoutStateChanged);

      // Load the layout configuration
      goldenLayout.loadLayout(layoutConfig);

      // Mark as initialized
      setIsInitialized(true);
      setLayoutReady(true);
      setError(null);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      console.error('Failed to initialize Golden-Layout:', err);
      setError(`Failed to initialize layout: ${errorMessage}`);
      setIsInitialized(false);
      setLayoutReady(false);
    }
  }, [
    currentLayoutConfig,
    getDefaultLayout,
    bindComponent,
    unbindComponent,
    handleLayoutStateChanged,
    setLayoutReady,
  ]);

  /**
   * Handle window resize
   */
  const handleResize = useCallback((): void => {
    if (goldenLayoutRef.current) {
      goldenLayoutRef.current.setSize(
        containerRef.current?.clientWidth || window.innerWidth,
        containerRef.current?.clientHeight || window.innerHeight
      );
    }
  }, []);

  /**
   * Initialize layout on mount
   */
  useEffect(() => {
    initializeLayout();

    // Add resize listener
    window.addEventListener('resize', handleResize);

    // Cleanup on unmount
    return () => {
      window.removeEventListener('resize', handleResize);
      
      // Cleanup all component refs
      componentRefs.current.forEach((ref) => {
        ref.root.unmount();
      });
      componentRefs.current.clear();

      // Destroy Golden-Layout instance
      if (goldenLayoutRef.current) {
        goldenLayoutRef.current.destroy();
        goldenLayoutRef.current = null;
      }

      setLayoutReady(false);
    };
  }, []); // Only run on mount/unmount

  /**
   * Expose layout API for external use
   */
  useEffect(() => {
    // Expose methods on window for debugging/testing
    if (typeof window !== 'undefined') {
      (window as any).__titanQuantLayout = {
        getLayout: () => goldenLayoutRef.current,
        saveLayout: () => goldenLayoutRef.current?.saveLayout(),
        resetLayout: () => {
          if (goldenLayoutRef.current) {
            goldenLayoutRef.current.loadLayout(getDefaultLayout());
          }
        },
        addPanel: (panelType: PanelType, title?: string) => {
          if (goldenLayoutRef.current) {
            goldenLayoutRef.current.addComponent(panelType, undefined, title || panelType);
          }
        },
      };
    }

    return () => {
      if (typeof window !== 'undefined') {
        delete (window as any).__titanQuantLayout;
      }
    };
  }, [getDefaultLayout]);

  // Render error state
  if (error) {
    return (
      <div className="workspace-layout-error">
        <div className="error-content">
          <span className="error-icon">⚠️</span>
          <h3>{t('layout.initError')}</h3>
          <p>{error}</p>
          <button 
            className="retry-button"
            onClick={initializeLayout}
          >
            {t('layout.retry')}
          </button>
        </div>
      </div>
    );
  }

  // Render loading state
  if (!isInitialized) {
    return (
      <div className="workspace-layout-loading">
        <div className="loading-content">
          <div className="loading-spinner"></div>
          <p>{t('layout.initializing')}</p>
        </div>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef} 
      className="workspace-layout-container"
      data-testid="workspace-layout"
    />
  );
};

export default WorkspaceLayout;
