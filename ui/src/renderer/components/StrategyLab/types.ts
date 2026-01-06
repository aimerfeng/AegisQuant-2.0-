/**
 * Titan-Quant Strategy Lab Types
 * 
 * Type definitions for Strategy IDE components.
 * Requirements: 8.1, 8.2, 8.3
 */

/**
 * Hot reload policy options
 */
export enum HotReloadPolicy {
  RESET = 'reset',           // Reset all variables
  PRESERVE = 'preserve',     // Preserve all state variables
  SELECTIVE = 'selective',   // User-specified variables to preserve
}

/**
 * Strategy parameter type
 */
export type StrategyParamType = 'int' | 'float' | 'string' | 'enum' | 'bool';

/**
 * UI widget type for parameter rendering
 */
export type ParamWidgetType = 'input' | 'slider' | 'dropdown' | 'checkbox';

/**
 * Strategy parameter definition
 */
export interface StrategyParameter {
  name: string;
  paramType: StrategyParamType;
  defaultValue: unknown;
  currentValue: unknown;
  minValue?: number;
  maxValue?: number;
  step?: number;
  options?: Array<{ label: string; value: unknown }>;
  uiWidget: ParamWidgetType;
  description?: string;
}

/**
 * Strategy metadata
 */
export interface StrategyMetadata {
  strategyId: string;
  name: string;
  className: string;
  filePath: string;
  parameters: StrategyParameter[];
  checksum: string;
  createdAt: number;
  updatedAt: number;
}

/**
 * Hot reload result
 */
export interface ReloadResult {
  success: boolean;
  policy: HotReloadPolicy;
  preservedVariables: string[];
  resetVariables: string[];
  errorMessage?: string;
}

/**
 * Code editor state
 */
export interface CodeEditorState {
  content: string;
  language: string;
  isDirty: boolean;
  cursorPosition: { line: number; column: number };
  selectedText?: string;
}

/**
 * Strategy file info
 */
export interface StrategyFile {
  path: string;
  name: string;
  content: string;
  isModified: boolean;
  lastSaved?: number;
}

/**
 * Code editor props
 */
export interface CodeEditorProps {
  initialContent?: string;
  language?: string;
  readOnly?: boolean;
  onChange?: (content: string) => void;
  onSave?: (content: string) => void;
  onCursorChange?: (position: { line: number; column: number }) => void;
  height?: string | number;
  theme?: 'vs-dark' | 'vs-light' | 'hc-black';
}

/**
 * Parameter panel props
 */
export interface ParamPanelProps {
  strategyId?: string;
  parameters: StrategyParameter[];
  onParameterChange?: (name: string, value: unknown) => void;
  onApplyAll?: (params: Record<string, unknown>) => void;
  disabled?: boolean;
}

/**
 * Hot reload panel props
 */
export interface HotReloadPanelProps {
  strategyId?: string;
  isReloading?: boolean;
  lastReloadResult?: ReloadResult;
  onReload?: (policy: HotReloadPolicy, preserveVars?: string[]) => void;
  onRollback?: () => void;
  disabled?: boolean;
}

/**
 * Strategy lab panel props
 */
export interface StrategyLabProps {
  initialStrategyId?: string;
  onStrategyChange?: (strategyId: string) => void;
}

/**
 * Python autocomplete suggestion
 */
export interface PythonSuggestion {
  label: string;
  kind: 'function' | 'class' | 'variable' | 'keyword' | 'snippet';
  insertText: string;
  documentation?: string;
  detail?: string;
}

/**
 * Strategy template snippets
 */
export const STRATEGY_TEMPLATE_SNIPPETS: Record<string, string> = {
  ctaTemplate: `from core.strategies.template import CtaTemplate

class MyStrategy(CtaTemplate):
    """
    Custom CTA Strategy
    """
    
    # Strategy parameters
    parameters = {
        "fast_period": 10,
        "slow_period": 20,
        "volume": 1.0,
    }
    
    def __init__(self, engine, strategy_name, vt_symbol, setting):
        super().__init__(engine, strategy_name, vt_symbol, setting)
        
        # Initialize variables
        self.fast_ma = 0.0
        self.slow_ma = 0.0
        
    def on_init(self):
        """Strategy initialization"""
        self.write_log("Strategy initialized")
        self.load_bar(10)
        
    def on_start(self):
        """Strategy start"""
        self.write_log("Strategy started")
        
    def on_stop(self):
        """Strategy stop"""
        self.write_log("Strategy stopped")
        
    def on_bar(self, bar):
        """Process bar data"""
        # Calculate indicators
        # Generate signals
        # Execute trades
        pass
`,
  onBar: `def on_bar(self, bar):
    """Process bar data"""
    # Calculate indicators
    close_prices = self.get_close_prices()
    
    # Generate signals
    if self.fast_ma > self.slow_ma:
        if self.pos == 0:
            self.buy(bar.close_price, self.volume)
    elif self.fast_ma < self.slow_ma:
        if self.pos > 0:
            self.sell(bar.close_price, abs(self.pos))
`,
  onTick: `def on_tick(self, tick):
    """Process tick data"""
    # Real-time tick processing
    pass
`,
};
