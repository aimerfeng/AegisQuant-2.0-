/**
 * Titan-Quant Main Layout Component
 * 
 * This component provides the main workspace layout.
 * Using a simple flexbox layout for now (Golden Layout integration pending fix).
 */

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';
import LayoutToolbar from './LayoutToolbar';
import PlaceholderPanel from './panels/PlaceholderPanel';
import OrderBook from './OrderBook';
import { darkOrderBookTheme, OrderBookDisplayMode } from './OrderBook/types';
import KLineChart from './KLineChart';
import StrategyLab from './StrategyLab';
import DataCenter from './DataCenter';
import Reports from './Reports';
import { PlaybackBar, ManualTrade } from './ControlPanel';
import Positions from './Positions';
import Trades from './Trades';
import Logs from './Logs';
import './MainLayout.css';

// Simple tab-based panel component
interface TabPanelProps {
  tabs: { id: string; title: string; content: React.ReactNode }[];
  defaultTab?: string;
}

const TabPanel: React.FC<TabPanelProps> = ({ tabs, defaultTab }) => {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id);
  
  return (
    <div className="tab-panel">
      <div className="tab-header">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.title}
          </button>
        ))}
      </div>
      <div className="tab-content">
        {tabs.find(t => t.id === activeTab)?.content}
      </div>
    </div>
  );
};

const MainLayout: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="main-layout">
      <div className="layout-toolbar">
        <div className="toolbar-left">
          <LayoutToolbar />
        </div>
        <div className="toolbar-right">
          <LanguageSelector />
        </div>
      </div>
      <div className="layout-workspace simple-layout">
        {/* Left sidebar */}
        <div className="panel-container sidebar-left">
          <TabPanel
            tabs={[
              {
                id: 'positions',
                title: t('panels.positions', 'Positions'),
                content: <Positions />
              },
              {
                id: 'trades',
                title: t('panels.trades', 'Trades'),
                content: <Trades />
              }
            ]}
          />
        </div>

        {/* Main content area */}
        <div className="panel-container main-content">
          <div className="main-top">
            <TabPanel
              tabs={[
                {
                  id: 'chart',
                  title: t('panels.chart', 'K-Line Chart'),
                  content: <KLineChart symbol="BTC/USDT" interval="1H" autoSize={true} />
                },
                {
                  id: 'strategy',
                  title: t('panels.strategy', 'Strategy Lab'),
                  content: <StrategyLab />
                },
                {
                  id: 'data',
                  title: t('panels.data', 'Data Center'),
                  content: <DataCenter />
                }
              ]}
            />
          </div>
          <div className="main-bottom">
            <TabPanel
              tabs={[
                {
                  id: 'logs',
                  title: t('panels.logs', 'Logs'),
                  content: <Logs />
                },
                {
                  id: 'reports',
                  title: t('panels.reports', 'Reports'),
                  content: <Reports />
                }
              ]}
            />
          </div>
        </div>

        {/* Right sidebar */}
        <div className="panel-container sidebar-right">
          <TabPanel
            tabs={[
              {
                id: 'orderbook',
                title: t('panels.orderbook', 'Order Book'),
                content: (
                  <OrderBook
                    displayMode={OrderBookDisplayMode.VERTICAL}
                    levels={10}
                    precision={2}
                    volumePrecision={4}
                    theme={darkOrderBookTheme}
                    autoSize={true}
                  />
                )
              },
              {
                id: 'control',
                title: t('panels.control', 'Control'),
                content: (
                  <div className="control-panel-wrapper">
                    <PlaybackBar />
                    <ManualTrade />
                  </div>
                )
              }
            ]}
          />
        </div>
      </div>
    </div>
  );
};

export default MainLayout;
