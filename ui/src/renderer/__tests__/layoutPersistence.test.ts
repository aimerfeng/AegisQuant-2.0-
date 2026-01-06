/**
 * Layout Persistence Property-Based Tests
 * 
 * Property 8: Layout Persistence Round-Trip
 * Validates: Requirements 4.3, 4.4
 * 
 * Tests that layout configurations can be saved and loaded without data loss.
 */

import * as fc from 'fast-check';
import { LayoutConfig, ItemType, ComponentItemConfig } from 'golden-layout';
import {
  exportLayoutToJson,
  importLayoutFromJson,
  isValidLayoutConfig,
  cloneLayoutConfig,
} from '../utils/layoutPersistence';
import {
  LayoutPersistenceData,
  WorkspacePreset,
  PanelType,
  LAYOUT_VERSION,
} from '../types/layout';

/**
 * Arbitrary generator for PanelType
 */
const panelTypeArb = fc.constantFrom(
  PanelType.KLINE_CHART,
  PanelType.ORDER_BOOK,
  PanelType.STRATEGY_LAB,
  PanelType.LOG_PANEL,
  PanelType.POSITIONS,
  PanelType.TRADES,
  PanelType.CONTROL_PANEL,
  PanelType.DATA_CENTER,
  PanelType.REPORTS
);

/**
 * Arbitrary generator for component state
 */
const componentStateArb = fc.dictionary(
  fc.string({ minLength: 1, maxLength: 20 }),
  fc.oneof(
    fc.string(),
    fc.integer(),
    fc.boolean(),
    fc.constant(null)
  )
);

/**
 * Arbitrary generator for a component item config
 */
const componentItemArb = fc.record({
  componentType: panelTypeArb,
  title: fc.string({ minLength: 1, maxLength: 50 }),
  componentState: componentStateArb,
}).map(item => ({
  type: ItemType.component,
  componentType: item.componentType,
  title: item.title,
  componentState: item.componentState,
} as ComponentItemConfig));

/**
 * Arbitrary generator for row/column type
 */
const rowOrColumnTypeArb = fc.constantFrom('row', 'column').map(t => 
  t === 'row' ? ItemType.row : ItemType.column
);

/**
 * Arbitrary generator for a simple layout config (non-recursive for simplicity)
 * Note: We only generate the root content, not header options to avoid type complexity
 */
const simpleLayoutConfigArb = fc.record({
  rootType: rowOrColumnTypeArb,
  content: fc.array(componentItemArb, { minLength: 1, maxLength: 5 }),
}).map(config => {
  const layoutConfig: LayoutConfig = {
    root: {
      type: config.rootType,
      content: config.content,
    },
  };
  return layoutConfig;
});

/**
 * Arbitrary generator for workspace preset
 */
const workspacePresetArb: fc.Arbitrary<WorkspacePreset> = fc.record({
  id: fc.uuid(),
  name: fc.string({ minLength: 1, maxLength: 50 }),
  description: fc.option(fc.string({ maxLength: 200 }), { nil: undefined }),
  layoutConfig: simpleLayoutConfigArb,
  createdAt: fc.integer({ min: 0, max: Date.now() }),
  updatedAt: fc.integer({ min: 0, max: Date.now() }),
});

/**
 * Arbitrary generator for layout persistence data
 */
const layoutPersistenceDataArb: fc.Arbitrary<LayoutPersistenceData> = fc.record({
  version: fc.constant(LAYOUT_VERSION),
  currentLayoutConfig: fc.option(simpleLayoutConfigArb, { nil: null }),
  presets: fc.array(workspacePresetArb, { minLength: 0, maxLength: 5 }),
  activePresetId: fc.option(fc.uuid(), { nil: null }),
});

describe('Layout Persistence Property Tests', () => {
  /**
   * Feature: titan-quant, Property 8: Layout Persistence Round-Trip
   * Validates: Requirements 4.3, 4.4
   * 
   * For any valid layout persistence data, exporting to JSON and importing
   * back should produce an equivalent data structure.
   */
  describe('Property 8: Layout Persistence Round-Trip', () => {
    it('should preserve layout data through export/import cycle', () => {
      fc.assert(
        fc.property(layoutPersistenceDataArb, (originalData) => {
          // Export to JSON
          const jsonString = exportLayoutToJson(originalData);
          
          // Import from JSON
          const importedData = importLayoutFromJson(jsonString);
          
          // Verify import succeeded
          expect(importedData).not.toBeNull();
          
          if (importedData) {
            // Verify version is preserved
            expect(importedData.version).toBe(originalData.version);
            
            // Verify activePresetId is preserved
            expect(importedData.activePresetId).toBe(originalData.activePresetId);
            
            // Verify presets count is preserved
            expect(importedData.presets.length).toBe(originalData.presets.length);
            
            // Verify each preset is preserved
            for (let i = 0; i < originalData.presets.length; i++) {
              expect(importedData.presets[i].id).toBe(originalData.presets[i].id);
              expect(importedData.presets[i].name).toBe(originalData.presets[i].name);
              expect(importedData.presets[i].description).toBe(originalData.presets[i].description);
              expect(importedData.presets[i].createdAt).toBe(originalData.presets[i].createdAt);
              expect(importedData.presets[i].updatedAt).toBe(originalData.presets[i].updatedAt);
            }
            
            // Verify currentLayoutConfig is preserved (deep equality)
            if (originalData.currentLayoutConfig) {
              expect(importedData.currentLayoutConfig).not.toBeNull();
              expect(JSON.stringify(importedData.currentLayoutConfig))
                .toBe(JSON.stringify(originalData.currentLayoutConfig));
            } else {
              expect(importedData.currentLayoutConfig).toBeNull();
            }
          }
        }),
        { numRuns: 100 }
      );
    });

    it('should preserve layout config through clone operation', () => {
      fc.assert(
        fc.property(simpleLayoutConfigArb, (originalConfig) => {
          // Clone the config
          const clonedConfig = cloneLayoutConfig(originalConfig);
          
          // Verify deep equality
          expect(JSON.stringify(clonedConfig)).toBe(JSON.stringify(originalConfig));
          
          // Verify it's a different object (not same reference)
          expect(clonedConfig).not.toBe(originalConfig);
          expect(clonedConfig.root).not.toBe(originalConfig.root);
        }),
        { numRuns: 100 }
      );
    });

    it('should correctly validate layout configs', () => {
      fc.assert(
        fc.property(simpleLayoutConfigArb, (config) => {
          // Valid configs should pass validation
          expect(isValidLayoutConfig(config)).toBe(true);
        }),
        { numRuns: 100 }
      );
    });

    it('should reject invalid layout configs', () => {
      // Test various invalid inputs
      expect(isValidLayoutConfig(null)).toBe(false);
      expect(isValidLayoutConfig(undefined)).toBe(false);
      expect(isValidLayoutConfig({})).toBe(false);
      expect(isValidLayoutConfig({ notRoot: 'value' })).toBe(false);
      expect(isValidLayoutConfig('string')).toBe(false);
      expect(isValidLayoutConfig(123)).toBe(false);
      expect(isValidLayoutConfig([])).toBe(false);
    });

    it('should handle JSON parsing errors gracefully', () => {
      // Invalid JSON should return null
      expect(importLayoutFromJson('not valid json')).toBeNull();
      expect(importLayoutFromJson('{incomplete')).toBeNull();
      expect(importLayoutFromJson('')).toBeNull();
    });

    it('should preserve preset metadata through round-trip', () => {
      fc.assert(
        fc.property(workspacePresetArb, (originalPreset) => {
          // Create persistence data with single preset
          const data: LayoutPersistenceData = {
            version: LAYOUT_VERSION,
            currentLayoutConfig: null,
            presets: [originalPreset],
            activePresetId: originalPreset.id,
          };
          
          // Round-trip
          const jsonString = exportLayoutToJson(data);
          const importedData = importLayoutFromJson(jsonString);
          
          expect(importedData).not.toBeNull();
          if (importedData) {
            expect(importedData.presets.length).toBe(1);
            const importedPreset = importedData.presets[0];
            
            // Verify all preset fields
            expect(importedPreset.id).toBe(originalPreset.id);
            expect(importedPreset.name).toBe(originalPreset.name);
            expect(importedPreset.description).toBe(originalPreset.description);
            expect(importedPreset.createdAt).toBe(originalPreset.createdAt);
            expect(importedPreset.updatedAt).toBe(originalPreset.updatedAt);
            
            // Verify layout config within preset
            expect(JSON.stringify(importedPreset.layoutConfig))
              .toBe(JSON.stringify(originalPreset.layoutConfig));
          }
        }),
        { numRuns: 100 }
      );
    });

    it('should preserve component state through round-trip', () => {
      fc.assert(
        fc.property(componentStateArb, (originalState) => {
          // Create a layout with component state
          const config: LayoutConfig = {
            root: {
              type: ItemType.row,
              content: [
                {
                  type: ItemType.component,
                  componentType: PanelType.KLINE_CHART,
                  title: 'Test',
                  componentState: originalState,
                } as ComponentItemConfig,
              ],
            },
          };
          
          const data: LayoutPersistenceData = {
            version: LAYOUT_VERSION,
            currentLayoutConfig: config,
            presets: [],
            activePresetId: null,
          };
          
          // Round-trip
          const jsonString = exportLayoutToJson(data);
          const importedData = importLayoutFromJson(jsonString);
          
          expect(importedData).not.toBeNull();
          if (importedData && importedData.currentLayoutConfig && importedData.currentLayoutConfig.root) {
            const importedRoot = importedData.currentLayoutConfig.root as any;
            const importedContent = importedRoot.content;
            expect(importedContent).toBeDefined();
            if (importedContent && importedContent.length > 0) {
              const importedComponent = importedContent[0] as any;
              expect(JSON.stringify(importedComponent.componentState))
                .toBe(JSON.stringify(originalState));
            }
          }
        }),
        { numRuns: 100 }
      );
    });
  });
});
