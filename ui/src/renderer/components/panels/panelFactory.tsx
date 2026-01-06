/**
 * Panel Factory
 * 
 * Creates panel components for Golden-Layout registration.
 */

import React from 'react';
import { PanelType, PanelComponentProps, PanelRegistration } from '../../types/layout';
import PlaceholderPanel from './PlaceholderPanel';

/**
 * K-Line Chart Panel (placeholder)
 */
const KLineChartPanel: React.FC<PanelComponentProps> = (props) => (
  <PlaceholderPanel panelName="K-Line Chart" icon="📈" {...props} />
);

/**
 * Order Book Panel (placeholder)
 */
const OrderBookPanel: React.FC<PanelComponentProps> = (props) => (
  <PlaceholderPanel panelName="Order Book" icon="📊" {...props} />
);

/**
 * Strategy Lab Panel (placeholder)
 */
const StrategyLabPanel: React.FC<PanelComponentProps> = (props) => (
  <PlaceholderPanel panelName="Strategy Lab" icon="🔬" {...props} />
);

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
 * Control Panel (placeholder)
 */
const ControlPanel: React.FC<PanelComponentProps> = (props) => (
  <PlaceholderPanel panelName="Control Panel" icon="🎛️" {...props} />
);

/**
 * Data Center Panel (placeholder)
 */
const DataCenterPanel: React.FC<PanelComponentProps> = (props) => (
  <PlaceholderPanel panelName="Data Center" icon="🗄️" {...props} />
);

/**
 * Reports Panel (placeholder)
 */
const ReportsPanel: React.FC<PanelComponentProps> = (props) => (
  <PlaceholderPanel panelName="Reports" icon="📑" {...props} />
);

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
