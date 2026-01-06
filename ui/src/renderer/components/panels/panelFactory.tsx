/**
 * Panel Factory
 * 
 * Creates panel components for Golden-Layout registration.
 */

import React from 'react';
import { PanelType, PanelComponentProps, PanelRegistration } from '../../types/layout';
import PlaceholderPanel from './PlaceholderPanel';
import KLineChartWithTools from '../KLineChart/KLineChartWithTools';
import { darkTheme, CandlestickData, TradeMarker, Indicator, Drawing } from '../KLineChart/types';
import OrderBook from '../OrderBook';
import { OrderBookData, OrderBookDisplayMode, darkOrderBookTheme } from '../OrderBook/types';
import { PlaybackBar, ManualTrade } from '../ControlPanel';
import StrategyLab from '../StrategyLab';
import DataCenter from '../DataCenter';
import Reports from '../Reports';
import { BacktestReport } from '../Reports/types';

/**
 * K-Line Chart Panel - Full-featured implementation with drawing tools and indicators
 */
const KLineChartPanel: React.FC<PanelComponentProps> = (props) => {
  // Extract data from component state if available
  const componentState = props.componentState || {};
  const data = (componentState.data as CandlestickData[]) || [];
  const tradeMarkers = (componentState.tradeMarkers as TradeMarker[]) || [];
  const indicators = (componentState.indicators as Indicator[]) || [];
  const drawings = (componentState.drawings as Drawing[]) || [];
  const symbol = (componentState.symbol as string) || '';
  const interval = (componentState.interval as string) || '';

  return (
    <KLineChartWithTools
      data={data}
      tradeMarkers={tradeMarkers}
      indicators={indicators}
      drawings={drawings}
      symbol={symbol}
      interval={interval}
      theme={darkTheme}
      autoSize={true}
      showDrawingTools={true}
      showIndicatorPanel={true}
    />
  );
};

/**
 * Order Book Panel - Full-featured implementation with depth visualization
 */
const OrderBookPanel: React.FC<PanelComponentProps> = (props) => {
  // Extract data from component state if available
  const componentState = props.componentState || {};
  const data = componentState.data as OrderBookData | undefined;
  const displayMode = (componentState.displayMode as OrderBookDisplayMode) || OrderBookDisplayMode.VERTICAL;
  const levels = (componentState.levels as number) || 10;
  const precision = (componentState.precision as number) || 2;
  const volumePrecision = (componentState.volumePrecision as number) || 4;

  return (
    <OrderBook
      data={data}
      displayMode={displayMode}
      levels={levels}
      precision={precision}
      volumePrecision={volumePrecision}
      theme={darkOrderBookTheme}
      autoSize={true}
      animateUpdates={true}
    />
  );
};

/**
 * Strategy Lab Panel - Full-featured implementation with code editor, params, and hot reload
 */
const StrategyLabPanel: React.FC<PanelComponentProps> = (props) => {
  const componentState = props.componentState || {};
  const initialStrategyId = componentState.strategyId as string | undefined;

  return (
    <StrategyLab
      initialStrategyId={initialStrategyId}
    />
  );
};

/**
 * Log Panel (placeholder)
 */
const LogPanel: React.FC<PanelComponentProps> = (props) => (
  <PlaceholderPanel panelName="Logs" icon="📝" {...props} />
);

/**
 * Positions Panel (placeholder)
 */
const PositionsPanel: React.FC<PanelComponentProps> = (props) => (
  <PlaceholderPanel panelName="Positions" icon="💼" {...props} />
);

/**
 * Trades Panel (placeholder)
 */
const TradesPanel: React.FC<PanelComponentProps> = (props) => (
  <PlaceholderPanel panelName="Trades" icon="💹" {...props} />
);

/**
 * Control Panel - Playback controls and manual trading
 */
const ControlPanel: React.FC<PanelComponentProps> = (props) => {
  const componentState = props.componentState || {};
  const symbol = (componentState.symbol as string) || 'BTC_USDT';
  const volume = (componentState.volume as number) || 1;

  return (
    <div className="control-panel-container" style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      gap: '16px', 
      padding: '16px',
      height: '100%',
      overflow: 'auto'
    }}>
      <PlaybackBar />
      <ManualTrade config={{ symbol, volume }} />
    </div>
  );
};

/**
 * Data Center Panel - Full-featured implementation with file import, cleaning, and provider config
 */
const DataCenterPanel: React.FC<PanelComponentProps> = (props) => {
  const componentState = props.componentState || {};
  const initialTab = (componentState.initialTab as 'import' | 'cleaning' | 'providers') || 'import';

  return (
    <DataCenter
      initialTab={initialTab}
    />
  );
};

/**
 * Reports Panel - Full-featured implementation with metrics cards and equity curve
 */
const ReportsPanel: React.FC<PanelComponentProps> = (props) => {
  const componentState = props.componentState || {};
  const report = componentState.report as BacktestReport | undefined;
  const isLoading = (componentState.isLoading as boolean) || false;
  const error = componentState.error as string | undefined;

  return (
    <Reports
      report={report}
      isLoading={isLoading}
      error={error}
    />
  );
};

/**
 * Panel component map
 */
const panelComponents: Record<PanelType, React.FC<PanelComponentProps>> = {
  [PanelType.KLINE_CHART]: KLineChartPanel,
  [PanelType.ORDER_BOOK]: OrderBookPanel,
  [PanelType.STRATEGY_LAB]: StrategyLabPanel,
  [PanelType.LOG_PANEL]: LogPanel,
  [PanelType.POSITIONS]: PositionsPanel,
  [PanelType.TRADES]: TradesPanel,
  [PanelType.CONTROL_PANEL]: ControlPanel,
  [PanelType.DATA_CENTER]: DataCenterPanel,
  [PanelType.REPORTS]: ReportsPanel,
};

/**
 * Get panel component by type
 */
export const getPanelComponent = (type: PanelType): React.FC<PanelComponentProps> => {
  return panelComponents[type] || PlaceholderPanel;
};

/**
 * Create panel registrations for all panel types
 */
export const createPanelComponents = (): PanelRegistration[] => {
  return [
    {
      type: PanelType.KLINE_CHART,
      title: 'K-Line Chart',
      component: KLineChartPanel,
    },
    {
      type: PanelType.ORDER_BOOK,
      title: 'Order Book',
      component: OrderBookPanel,
    },
    {
      type: PanelType.STRATEGY_LAB,
      title: 'Strategy Lab',
      component: StrategyLabPanel,
    },
    {
      type: PanelType.LOG_PANEL,
      title: 'Logs',
      component: LogPanel,
    },
    {
      type: PanelType.POSITIONS,
      title: 'Positions',
      component: PositionsPanel,
    },
    {
      type: PanelType.TRADES,
      title: 'Trades',
      component: TradesPanel,
    },
    {
      type: PanelType.CONTROL_PANEL,
      title: 'Control Panel',
      component: ControlPanel,
    },
    {
      type: PanelType.DATA_CENTER,
      title: 'Data Center',
      component: DataCenterPanel,
    },
    {
      type: PanelType.REPORTS,
      title: 'Reports',
      component: ReportsPanel,
    },
  ];
};

export default panelComponents;
