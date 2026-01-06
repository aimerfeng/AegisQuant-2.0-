/**
 * Reports Component
 * 
 * Displays backtest report with metrics cards and equity curve chart.
 * 
 * Requirements:
 *   - 15.1: WHEN 回测结束, THEN THE Titan_Quant_System SHALL 自动生成交互式 HTML 报告
 *   - 15.2: THE 报告 SHALL 包含夏普比率、最大回撤、总收益等关键指标
 */

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ReportsProps,
  BacktestReport,
  BacktestMetrics,
  EquityPoint,
  TradeRecord,
  MetricCardConfig,
  ReportViewMode,
  darkReportsTheme,
} from './types';
import './Reports.css';

/**
 * Format number based on format type
 */
const formatValue = (
  value: number | undefined,
  format: 'percent' | 'number' | 'currency' | 'ratio',
  decimals: number = 2
): string => {
  if (value === undefined || value === null || isNaN(value)) {
    return '--';
  }

  switch (format) {
    case 'percent':
      return `${(value * 100).toFixed(decimals)}%`;
    case 'currency':
      return value.toLocaleString('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    case 'ratio':
      return value.toFixed(decimals);
    case 'number':
    default:
      return value.toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: decimals,
      });
  }
};

/**
 * Get color class based on value
 */
const getValueColorClass = (
  value: number | undefined,
  colorize: boolean,
  invertColor: boolean
): string => {
  if (!colorize || value === undefined || value === null || isNaN(value)) {
    return '';
  }

  const isPositive = invertColor ? value < 0 : value > 0;
  const isNegative = invertColor ? value > 0 : value < 0;

  if (isPositive) return 'value-positive';
  if (isNegative) return 'value-negative';
  return '';
};

/**
 * Metric Card Component
 */
interface MetricCardProps {
  config: MetricCardConfig;
  value: number | undefined;
  t: (key: string) => string;
}

const MetricCard: React.FC<MetricCardProps> = ({ config, value, t }) => {
  const colorClass = getValueColorClass(value, config.colorize ?? false, config.invertColor ?? false);
  const formattedValue = formatValue(value, config.format, config.decimals);

  return (
    <div className="metric-card">
      <div className="metric-card-header">
        {config.icon && <span className="metric-icon">{config.icon}</span>}
        <span className="metric-label">{t(`report.${config.label}`)}</span>
      </div>
      <div className={`metric-value ${colorClass}`}>
        {formattedValue}
      </div>
    </div>
  );
};

/**
 * Equity Curve Chart Component (Simple SVG implementation)
 */
interface EquityCurveChartProps {
  data: EquityPoint[];
  width?: number;
  height?: number;
}

const EquityCurveChart: React.FC<EquityCurveChartProps> = ({
  data,
  width = 800,
  height = 300,
}) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width, height });
  const [tooltip, setTooltip] = useState<{
    visible: boolean;
    x: number;
    y: number;
    data: EquityPoint | null;
  }>({ visible: false, x: 0, y: 0, data: null });

  // Handle resize
  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        setDimensions({ width: w, height: Math.max(h, 200) });
      }
    });

    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  // Calculate chart dimensions
  const padding = { top: 20, right: 20, bottom: 40, left: 70 };
  const chartWidth = dimensions.width - padding.left - padding.right;
  const chartHeight = dimensions.height - padding.top - padding.bottom;

  // Calculate scales
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    const equities = data.map((d) => d.equity);
    const minEquity = Math.min(...equities);
    const maxEquity = Math.max(...equities);
    const equityRange = maxEquity - minEquity || 1;

    // Scale functions
    const scaleX = (index: number) => (index / (data.length - 1)) * chartWidth;
    const scaleY = (equity: number) =>
      chartHeight - ((equity - minEquity) / equityRange) * chartHeight;

    // Generate path
    let path = `M ${scaleX(0)} ${scaleY(data[0].equity)}`;
    for (let i = 1; i < data.length; i++) {
      path += ` L ${scaleX(i)} ${scaleY(data[i].equity)}`;
    }

    // Generate area path (for fill)
    let areaPath = path;
    areaPath += ` L ${scaleX(data.length - 1)} ${chartHeight}`;
    areaPath += ` L ${scaleX(0)} ${chartHeight} Z`;

    // Generate Y-axis labels
    const yLabels: { value: number; y: number }[] = [];
    const labelCount = 5;
    for (let i = 0; i <= labelCount; i++) {
      const value = minEquity + (equityRange * i) / labelCount;
      yLabels.push({ value, y: scaleY(value) });
    }

    // Generate X-axis labels (show first, middle, last dates)
    const xLabels: { label: string; x: number }[] = [];
    if (data.length > 0) {
      const indices = [0, Math.floor(data.length / 2), data.length - 1];
      indices.forEach((idx) => {
        const date = new Date(data[idx].timestamp);
        xLabels.push({
          label: date.toLocaleDateString(),
          x: scaleX(idx),
        });
      });
    }

    return {
      path,
      areaPath,
      yLabels,
      xLabels,
      scaleX,
      scaleY,
      minEquity,
      maxEquity,
    };
  }, [data, chartWidth, chartHeight]);

  // Handle mouse move for tooltip
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!chartData || !data || data.length === 0) return;

    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left - padding.left;

    if (x < 0 || x > chartWidth) {
      setTooltip((prev) => ({ ...prev, visible: false }));
      return;
    }

    const index = Math.round((x / chartWidth) * (data.length - 1));
    const clampedIndex = Math.max(0, Math.min(index, data.length - 1));
    const point = data[clampedIndex];

    setTooltip({
      visible: true,
      x: chartData.scaleX(clampedIndex) + padding.left,
      y: chartData.scaleY(point.equity) + padding.top,
      data: point,
    });
  };

  const handleMouseLeave = () => {
    setTooltip((prev) => ({ ...prev, visible: false }));
  };

  if (!data || data.length === 0) {
    return (
      <div className="equity-chart-empty">
        <span className="empty-icon">📈</span>
        <span>{t('chart.noData')}</span>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="equity-chart-container">
      <svg
        width={dimensions.width}
        height={dimensions.height}
        className="equity-chart-svg"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {chartData && (
          <g transform={`translate(${padding.left}, ${padding.top})`}>
            {/* Grid lines */}
            {chartData.yLabels.map((label, i) => (
              <line
                key={`grid-${i}`}
                x1={0}
                y1={label.y}
                x2={chartWidth}
                y2={label.y}
                className="chart-grid-line"
              />
            ))}

            {/* Area fill */}
            <path d={chartData.areaPath} className="chart-area" />

            {/* Line */}
            <path d={chartData.path} className="chart-line" />

            {/* Y-axis labels */}
            {chartData.yLabels.map((label, i) => (
              <text
                key={`y-label-${i}`}
                x={-10}
                y={label.y}
                className="chart-axis-label"
                textAnchor="end"
                dominantBaseline="middle"
              >
                {formatValue(label.value, 'currency', 0)}
              </text>
            ))}

            {/* X-axis labels */}
            {chartData.xLabels.map((label, i) => (
              <text
                key={`x-label-${i}`}
                x={label.x}
                y={chartHeight + 25}
                className="chart-axis-label"
                textAnchor="middle"
              >
                {label.label}
              </text>
            ))}

            {/* Tooltip indicator */}
            {tooltip.visible && tooltip.data && (
              <>
                <circle
                  cx={tooltip.x - padding.left}
                  cy={tooltip.y - padding.top}
                  r={5}
                  className="chart-tooltip-dot"
                />
                <line
                  x1={tooltip.x - padding.left}
                  y1={0}
                  x2={tooltip.x - padding.left}
                  y2={chartHeight}
                  className="chart-tooltip-line"
                />
              </>
            )}
          </g>
        )}
      </svg>

      {/* Tooltip */}
      {tooltip.visible && tooltip.data && (
        <div
          className="equity-chart-tooltip"
          style={{
            left: tooltip.x + 10,
            top: tooltip.y - 10,
          }}
        >
          <div className="tooltip-row">
            <span className="tooltip-label">{t('chart.time')}:</span>
            <span className="tooltip-value">
              {new Date(tooltip.data.timestamp).toLocaleString()}
            </span>
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label">Equity:</span>
            <span className="tooltip-value">
              {formatValue(tooltip.data.equity, 'currency')}
            </span>
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label">Drawdown:</span>
            <span className="tooltip-value value-negative">
              {formatValue(tooltip.data.drawdown, 'percent')}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};


/**
 * Trade List Component
 */
interface TradeListProps {
  trades: TradeRecord[];
}

const TradeList: React.FC<TradeListProps> = ({ trades }) => {
  const { t } = useTranslation();
  const [sortField, setSortField] = useState<keyof TradeRecord>('timestamp');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const sortedTrades = useMemo(() => {
    return [...trades].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      }

      return 0;
    });
  }, [trades, sortField, sortDirection]);

  const handleSort = (field: keyof TradeRecord) => {
    if (field === sortField) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const getSortIndicator = (field: keyof TradeRecord) => {
    if (field !== sortField) return '';
    return sortDirection === 'asc' ? ' ↑' : ' ↓';
  };

  if (!trades || trades.length === 0) {
    return (
      <div className="trade-list-empty">
        <span className="empty-icon">📋</span>
        <span>{t('chart.noData')}</span>
      </div>
    );
  }

  return (
    <div className="trade-list-container">
      <table className="trade-list-table">
        <thead>
          <tr>
            <th onClick={() => handleSort('timestamp')}>
              {t('chart.time')}{getSortIndicator('timestamp')}
            </th>
            <th onClick={() => handleSort('symbol')}>
              Symbol{getSortIndicator('symbol')}
            </th>
            <th onClick={() => handleSort('direction')}>
              Direction{getSortIndicator('direction')}
            </th>
            <th onClick={() => handleSort('offset')}>
              Action{getSortIndicator('offset')}
            </th>
            <th onClick={() => handleSort('price')}>
              {t('chart.price')}{getSortIndicator('price')}
            </th>
            <th onClick={() => handleSort('volume')}>
              {t('chart.volume')}{getSortIndicator('volume')}
            </th>
            <th onClick={() => handleSort('commission')}>
              {t('chart.commission')}{getSortIndicator('commission')}
            </th>
            <th>Mode</th>
          </tr>
        </thead>
        <tbody>
          {sortedTrades.map((trade) => (
            <tr key={trade.tradeId} className={trade.isManual ? 'manual-trade' : ''}>
              <td>{new Date(trade.timestamp).toLocaleString()}</td>
              <td>{trade.symbol}</td>
              <td className={trade.direction === 'LONG' ? 'direction-long' : 'direction-short'}>
                {trade.direction}
              </td>
              <td>{trade.offset}</td>
              <td>{formatValue(trade.price, 'currency', 4)}</td>
              <td>{formatValue(trade.volume, 'number', 4)}</td>
              <td>{formatValue(trade.commission, 'currency', 4)}</td>
              <td>
                {trade.matchingMode}
                {trade.l2Level && ` (${trade.l2Level})`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

/**
 * Main Reports Component
 */
const Reports: React.FC<ReportsProps> = ({
  report,
  onLoadReport,
  onExportReport,
  isLoading = false,
  error = null,
}) => {
  const { t } = useTranslation();
  const [viewMode, setViewMode] = useState<ReportViewMode>(ReportViewMode.SUMMARY);

  // Metric card configurations
  const metricConfigs: MetricCardConfig[] = [
    { key: 'totalReturn', label: 'total_return', format: 'percent', decimals: 2, colorize: true, icon: '📈' },
    { key: 'sharpeRatio', label: 'sharpe_ratio', format: 'ratio', decimals: 2, colorize: true, icon: '📊' },
    { key: 'maxDrawdown', label: 'max_drawdown', format: 'percent', decimals: 2, colorize: true, invertColor: true, icon: '📉' },
    { key: 'winRate', label: 'win_rate', format: 'percent', decimals: 1, icon: '🎯' },
    { key: 'profitFactor', label: 'profit_factor', format: 'ratio', decimals: 2, colorize: true, icon: '💰' },
    { key: 'totalTrades', label: 'total_trades', format: 'number', decimals: 0, icon: '🔢' },
  ];

  // Additional metrics for expanded view
  const additionalMetricConfigs: MetricCardConfig[] = [
    { key: 'annualizedReturn', label: 'annualized_return', format: 'percent', decimals: 2, colorize: true },
    { key: 'volatility', label: 'volatility', format: 'percent', decimals: 2 },
    { key: 'calmarRatio', label: 'calmar_ratio', format: 'ratio', decimals: 2, colorize: true },
    { key: 'sortinoRatio', label: 'sortino_ratio', format: 'ratio', decimals: 2, colorize: true },
    { key: 'avgWin', label: 'avg_win', format: 'currency', decimals: 2, colorize: true },
    { key: 'avgLoss', label: 'avg_loss', format: 'currency', decimals: 2, colorize: true },
    { key: 'netProfit', label: 'net_profit', format: 'currency', decimals: 2, colorize: true },
    { key: 'totalCommission', label: 'total_commission', format: 'currency', decimals: 2 },
  ];

  // Loading state
  if (isLoading) {
    return (
      <div className="reports-container">
        <div className="reports-loading">
          <div className="loading-spinner" />
          <span>{t('chart.loading')}</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="reports-container">
        <div className="reports-error">
          <span className="error-icon">⚠️</span>
          <span className="error-message">{error}</span>
        </div>
      </div>
    );
  }

  // Empty state
  if (!report) {
    return (
      <div className="reports-container">
        <div className="reports-empty">
          <span className="empty-icon">📊</span>
          <h3 className="empty-title">{t('report.title')}</h3>
          <p className="empty-description">
            {t('layout.componentPlaceholder', { name: t('ui.reports') })}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="reports-container">
      {/* Header */}
      <div className="reports-header">
        <div className="reports-title-section">
          <h2 className="reports-title">{t('report.title')}</h2>
          <span className="reports-strategy">{report.strategyName}</span>
          <span className="reports-date">
            {new Date(report.createdAt).toLocaleString()}
          </span>
        </div>
        <div className="reports-actions">
          <div className="view-mode-tabs">
            <button
              className={`tab-btn ${viewMode === ReportViewMode.SUMMARY ? 'active' : ''}`}
              onClick={() => setViewMode(ReportViewMode.SUMMARY)}
            >
              {t('report.summary')}
            </button>
            <button
              className={`tab-btn ${viewMode === ReportViewMode.EQUITY ? 'active' : ''}`}
              onClick={() => setViewMode(ReportViewMode.EQUITY)}
            >
              {t('report.equity_curve')}
            </button>
            <button
              className={`tab-btn ${viewMode === ReportViewMode.TRADES ? 'active' : ''}`}
              onClick={() => setViewMode(ReportViewMode.TRADES)}
            >
              {t('report.trade_list')}
            </button>
          </div>
          {onExportReport && (
            <div className="export-buttons">
              <button
                className="export-btn"
                onClick={() => onExportReport('html')}
                title="Export HTML"
              >
                📄 HTML
              </button>
              <button
                className="export-btn"
                onClick={() => onExportReport('csv')}
                title="Export CSV"
              >
                📋 CSV
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="reports-content">
        {/* Summary View */}
        {viewMode === ReportViewMode.SUMMARY && (
          <div className="summary-view">
            {/* Primary Metrics */}
            <div className="metrics-section">
              <h3 className="section-title">{t('report.summary')}</h3>
              <div className="metrics-grid primary-metrics">
                {metricConfigs.map((config) => (
                  <MetricCard
                    key={config.key}
                    config={config}
                    value={report.metrics[config.key] as number}
                    t={t}
                  />
                ))}
              </div>
            </div>

            {/* Additional Metrics */}
            <div className="metrics-section">
              <h3 className="section-title">Additional Metrics</h3>
              <div className="metrics-grid secondary-metrics">
                {additionalMetricConfigs.map((config) => (
                  <MetricCard
                    key={config.key}
                    config={config}
                    value={report.metrics[config.key] as number}
                    t={t}
                  />
                ))}
              </div>
            </div>

            {/* Mini Equity Chart */}
            <div className="equity-section">
              <h3 className="section-title">{t('report.equity_curve')}</h3>
              <EquityCurveChart data={report.equityCurve} />
            </div>
          </div>
        )}

        {/* Equity Curve View */}
        {viewMode === ReportViewMode.EQUITY && (
          <div className="equity-view">
            <EquityCurveChart data={report.equityCurve} />
          </div>
        )}

        {/* Trades View */}
        {viewMode === ReportViewMode.TRADES && (
          <div className="trades-view">
            <TradeList trades={report.trades} />
          </div>
        )}
      </div>

      {/* Footer with matching info */}
      <div className="reports-footer">
        <span className="matching-info">
          Matching Mode: {report.matchingMode}
          {report.l2Level && ` (${report.l2Level})`}
        </span>
        <span className="report-id">Report ID: {report.reportId}</span>
      </div>
    </div>
  );
};

export default Reports;
