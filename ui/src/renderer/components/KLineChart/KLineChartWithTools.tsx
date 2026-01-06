/**
 * KLine Chart With Tools Component
 * 
 * Enhanced K-Line chart component that includes:
 * - Drawing tools (trend lines, Fibonacci, rectangles)
 * - Indicator panel
 * - Full interactivity
 * 
 * This is the main component to use for the full-featured chart.
 * Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  Time,
  CrosshairMode,
  LineStyle,
  LineWidth,
  SeriesMarker,
  MouseEventParams,
} from 'lightweight-charts';
import {
  KLineChartProps,
  Drawing,
  DrawingToolType,
  Indicator,
  IndicatorType,
  ChartState,
  darkTheme,
  TradeMarker,
  MAConfig,
  MACDConfig,
  RSIConfig,
  BollingerConfig,
} from './types';
import {
  calculateSMA,
  calculateEMA,
  calculateMACD,
  calculateRSI,
  calculateBollingerBands,
  generateVolumeData,
  formatPrice,
  formatPercent,
} from './utils';
import DrawingTools from './DrawingTools';
import IndicatorPanel from './IndicatorPanel';
import './KLineChart.css';

/**
 * Extended props for the full-featured chart
 */
interface KLineChartWithToolsProps extends KLineChartProps {
  showDrawingTools?: boolean;
  showIndicatorPanel?: boolean;
}

/**
 * KLine Chart With Tools Component
 */
const KLineChartWithTools: React.FC<KLineChartWithToolsProps> = ({
  data = [],
  volumeData,
  tradeMarkers = [],
  drawings: initialDrawings = [],
  activeDrawingTool: initialDrawingTool = DrawingToolType.NONE,
  onDrawingComplete,
  onDrawingUpdate,
  onDrawingDelete,
  indicators: initialIndicators = [],
  onIndicatorAdd,
  onIndicatorRemove,
  onIndicatorUpdate,
  theme = darkTheme,
  symbol = '',
  interval = '',
  onCrosshairMove,
  onVisibleRangeChange,
  onTradeMarkerHover,
  onTradeMarkerClick,
  onDrawingCoordinatesExport,
  width,
  height,
  autoSize = true,
  showDrawingTools = true,
  showIndicatorPanel = true,
}) => {
  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const indicatorSeriesRef = useRef<Map<string, ISeriesApi<'Line' | 'Histogram'>>>(new Map());

  // State
  const [chartState, setChartState] = useState<ChartState>({
    isReady: false,
    visibleRange: null,
    crosshairPosition: null,
    hoveredMarker: null,
    activeDrawing: null,
    drawingInProgress: false,
  });
  const [drawings, setDrawings] = useState<Drawing[]>(initialDrawings);
  const [activeDrawingTool, setActiveDrawingTool] = useState<DrawingToolType>(initialDrawingTool);
  const [indicators, setIndicators] = useState<Indicator[]>(initialIndicators);
  const [tooltipData, setTooltipData] = useState<{
    visible: boolean;
    x: number;
    y: number;
    marker: TradeMarker | null;
  }>({ visible: false, x: 0, y: 0, marker: null });

  // Convert trade markers to series markers
  const seriesMarkers: SeriesMarker<Time>[] = tradeMarkers.map((marker) => ({
    time: marker.time,
    position: marker.position,
    color: marker.color,
    shape: marker.shape,
    text: marker.text,
    size: marker.size || 1,
    id: marker.id,
  }));

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: width || containerRef.current.clientWidth,
      height: height || containerRef.current.clientHeight,
      layout: {
        background: { color: theme.backgroundColor },
        textColor: theme.textColor,
      },
      grid: {
        vertLines: { color: theme.gridColor },
        horzLines: { color: theme.gridColor },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: theme.crosshairColor,
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: theme.crosshairColor,
        },
        horzLine: {
          color: theme.crosshairColor,
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: theme.crosshairColor,
        },
      },
      rightPriceScale: {
        borderColor: theme.borderColor,
      },
      timeScale: {
        borderColor: theme.borderColor,
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });

    chartRef.current = chart;

    // Create candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: theme.upColor,
      downColor: theme.downColor,
      borderUpColor: theme.upColor,
      borderDownColor: theme.downColor,
      wickUpColor: theme.upColor,
      wickDownColor: theme.downColor,
    });
    candlestickSeriesRef.current = candlestickSeries;

    // Create volume series
    const volumeSeries = chart.addHistogramSeries({
      color: theme.volumeUpColor,
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    volumeSeriesRef.current = volumeSeries;

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // Subscribe to events
    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      if (param.time && param.point) {
        const price = candlestickSeries.coordinateToPrice(param.point.y);
        setChartState((prev) => ({
          ...prev,
          crosshairPosition: { time: param.time as Time, price: price || 0 },
        }));
        onCrosshairMove?.(param.time as Time, price);

        const hoveredMarkerId = param.hoveredObjectId;
        if (hoveredMarkerId) {
          const marker = tradeMarkers.find((m) => m.id === hoveredMarkerId);
          if (marker) {
            setTooltipData({ visible: true, x: param.point.x, y: param.point.y, marker });
            onTradeMarkerHover?.(marker);
          }
        } else {
          setTooltipData((prev) => ({ ...prev, visible: false, marker: null }));
          onTradeMarkerHover?.(null);
        }
      } else {
        setChartState((prev) => ({ ...prev, crosshairPosition: null }));
        onCrosshairMove?.(null, null);
      }
    });

    chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
      if (range) {
        setChartState((prev) => ({
          ...prev,
          visibleRange: { from: range.from as Time, to: range.to as Time },
        }));
        onVisibleRangeChange?.(range.from as Time, range.to as Time);
      }
    });

    chart.subscribeClick((param: MouseEventParams) => {
      if (param.hoveredObjectId) {
        const marker = tradeMarkers.find((m) => m.id === param.hoveredObjectId);
        if (marker) onTradeMarkerClick?.(marker);
      }
    });

    setChartState((prev) => ({ ...prev, isReady: true }));

    return () => {
      chart.remove();
      chartRef.current = null;
      candlestickSeriesRef.current = null;
      volumeSeriesRef.current = null;
      indicatorSeriesRef.current.clear();
    };
  }, [theme]);

  // Handle auto-resize
  useEffect(() => {
    if (!autoSize || !containerRef.current || !chartRef.current) return;

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(containerRef.current);

    return () => resizeObserver.disconnect();
  }, [autoSize]);

  // Update candlestick data
  useEffect(() => {
    if (!candlestickSeriesRef.current || data.length === 0) return;

    candlestickSeriesRef.current.setData(data);
    if (seriesMarkers.length > 0) {
      candlestickSeriesRef.current.setMarkers(seriesMarkers);
    }
    chartRef.current?.timeScale().fitContent();
  }, [data, seriesMarkers]);

  // Update volume data
  useEffect(() => {
    if (!volumeSeriesRef.current) return;
    const volData = volumeData || generateVolumeData(data, theme.volumeUpColor, theme.volumeDownColor);
    volumeSeriesRef.current.setData(volData);
  }, [data, volumeData, theme]);

  // Update indicators
  useEffect(() => {
    if (!chartRef.current || !candlestickSeriesRef.current || data.length === 0) return;

    // Remove old indicator series
    indicatorSeriesRef.current.forEach((series, id) => {
      if (!indicators.find((ind) => ind.id === id || id.startsWith(ind.id))) {
        chartRef.current?.removeSeries(series);
        indicatorSeriesRef.current.delete(id);
      }
    });

    // Add/update indicators
    indicators.forEach((indicator) => {
      if (!indicator.visible) {
        const existingSeries = indicatorSeriesRef.current.get(indicator.id);
        if (existingSeries) {
          chartRef.current?.removeSeries(existingSeries);
          indicatorSeriesRef.current.delete(indicator.id);
        }
        return;
      }

      switch (indicator.type) {
        case IndicatorType.MA:
        case IndicatorType.EMA: {
          const config = indicator as MAConfig;
          const maData = indicator.type === IndicatorType.MA
            ? calculateSMA(data, config.period)
            : calculateEMA(data, config.period);

          let series = indicatorSeriesRef.current.get(indicator.id) as ISeriesApi<'Line'>;
          if (!series) {
            series = chartRef.current!.addLineSeries({
              color: config.color,
              lineWidth: config.lineWidth as LineWidth,
              priceScaleId: 'right',
            });
            indicatorSeriesRef.current.set(indicator.id, series);
          }
          series.setData(maData);
          break;
        }

        case IndicatorType.MACD: {
          const config = indicator as MACDConfig;
          const { macd, signal, histogram } = calculateMACD(
            data, config.fastPeriod, config.slowPeriod, config.signalPeriod
          );

          const macdId = `${indicator.id}-macd`;
          let macdSeries = indicatorSeriesRef.current.get(macdId) as ISeriesApi<'Line'>;
          if (!macdSeries) {
            macdSeries = chartRef.current!.addLineSeries({
              color: config.macdColor, lineWidth: 1, priceScaleId: 'macd',
            });
            indicatorSeriesRef.current.set(macdId, macdSeries);
          }
          macdSeries.setData(macd);

          const signalId = `${indicator.id}-signal`;
          let signalSeries = indicatorSeriesRef.current.get(signalId) as ISeriesApi<'Line'>;
          if (!signalSeries) {
            signalSeries = chartRef.current!.addLineSeries({
              color: config.signalColor, lineWidth: 1, priceScaleId: 'macd',
            });
            indicatorSeriesRef.current.set(signalId, signalSeries);
          }
          signalSeries.setData(signal);

          const histId = `${indicator.id}-hist`;
          let histSeries = indicatorSeriesRef.current.get(histId) as ISeriesApi<'Histogram'>;
          if (!histSeries) {
            histSeries = chartRef.current!.addHistogramSeries({ priceScaleId: 'macd' });
            indicatorSeriesRef.current.set(histId, histSeries);
          }
          histSeries.setData(histogram);

          chartRef.current!.priceScale('macd').applyOptions({
            scaleMargins: { top: 0.7, bottom: 0.1 },
          });
          break;
        }

        case IndicatorType.RSI: {
          const config = indicator as RSIConfig;
          const rsiData = calculateRSI(data, config.period);

          let series = indicatorSeriesRef.current.get(indicator.id) as ISeriesApi<'Line'>;
          if (!series) {
            series = chartRef.current!.addLineSeries({
              color: config.lineColor, lineWidth: 1, priceScaleId: 'rsi',
            });
            indicatorSeriesRef.current.set(indicator.id, series);
          }
          series.setData(rsiData);

          chartRef.current!.priceScale('rsi').applyOptions({
            scaleMargins: { top: 0.7, bottom: 0.1 },
          });
          break;
        }

        case IndicatorType.BOLLINGER: {
          const config = indicator as BollingerConfig;
          const { upper, middle, lower } = calculateBollingerBands(data, config.period, config.stdDev);

          const upperId = `${indicator.id}-upper`;
          let upperSeries = indicatorSeriesRef.current.get(upperId) as ISeriesApi<'Line'>;
          if (!upperSeries) {
            upperSeries = chartRef.current!.addLineSeries({
              color: config.upperColor, lineWidth: 1, priceScaleId: 'right',
            });
            indicatorSeriesRef.current.set(upperId, upperSeries);
          }
          upperSeries.setData(upper);

          const middleId = `${indicator.id}-middle`;
          let middleSeries = indicatorSeriesRef.current.get(middleId) as ISeriesApi<'Line'>;
          if (!middleSeries) {
            middleSeries = chartRef.current!.addLineSeries({
              color: config.middleColor, lineWidth: 1, priceScaleId: 'right',
            });
            indicatorSeriesRef.current.set(middleId, middleSeries);
          }
          middleSeries.setData(middle);

          const lowerId = `${indicator.id}-lower`;
          let lowerSeries = indicatorSeriesRef.current.get(lowerId) as ISeriesApi<'Line'>;
          if (!lowerSeries) {
            lowerSeries = chartRef.current!.addLineSeries({
              color: config.lowerColor, lineWidth: 1, priceScaleId: 'right',
            });
            indicatorSeriesRef.current.set(lowerId, lowerSeries);
          }
          lowerSeries.setData(lower);
          break;
        }
      }
    });
  }, [data, indicators]);

  // Drawing handlers
  const handleDrawingComplete = useCallback((drawing: Drawing) => {
    setDrawings((prev) => [...prev, drawing]);
    onDrawingComplete?.(drawing);
  }, [onDrawingComplete]);

  const handleDrawingUpdate = useCallback((drawing: Drawing) => {
    setDrawings((prev) => prev.map((d) => d.id === drawing.id ? drawing : d));
    onDrawingUpdate?.(drawing);
  }, [onDrawingUpdate]);

  const handleDrawingDelete = useCallback((drawingId: string) => {
    setDrawings((prev) => prev.filter((d) => d.id !== drawingId));
    onDrawingDelete?.(drawingId);
  }, [onDrawingDelete]);

  const handleToolChange = useCallback((tool: DrawingToolType) => {
    setActiveDrawingTool(tool);
  }, []);

  // Indicator handlers
  const handleIndicatorAdd = useCallback((indicator: Indicator) => {
    setIndicators((prev) => [...prev, indicator]);
    onIndicatorAdd?.(indicator);
  }, [onIndicatorAdd]);

  const handleIndicatorRemove = useCallback((indicatorId: string) => {
    setIndicators((prev) => prev.filter((i) => i.id !== indicatorId));
    onIndicatorRemove?.(indicatorId);
  }, [onIndicatorRemove]);

  const handleIndicatorUpdate = useCallback((indicator: Indicator) => {
    setIndicators((prev) => prev.map((i) => i.id === indicator.id ? indicator : i));
    onIndicatorUpdate?.(indicator);
  }, [onIndicatorUpdate]);

  // Export coordinates
  useEffect(() => {
    if (onDrawingCoordinatesExport && drawings.length > 0) {
      onDrawingCoordinatesExport(drawings);
    }
  }, [drawings, onDrawingCoordinatesExport]);

  // Render tooltip
  const renderTooltip = () => {
    if (!tooltipData.visible || !tooltipData.marker?.tradeDetails) return null;

    const details = tooltipData.marker.tradeDetails;
    const isProfitable = (details.pnl || 0) >= 0;

    return (
      <div className="kline-tooltip" style={{ left: tooltipData.x + 10, top: tooltipData.y - 10 }}>
        <div className="tooltip-header">
          <span className={`direction ${details.direction.toLowerCase()}`}>{details.direction}</span>
          <span className="action">{details.action}</span>
          {details.isManual && <span className="manual-badge">Manual</span>}
        </div>
        <div className="tooltip-body">
          <div className="tooltip-row">
            <span className="label">Price:</span>
            <span className="value">{formatPrice(details.price)}</span>
          </div>
          <div className="tooltip-row">
            <span className="label">Volume:</span>
            <span className="value">{details.volume}</span>
          </div>
          {details.pnl !== undefined && (
            <div className="tooltip-row">
              <span className="label">P&L:</span>
              <span className={`value ${isProfitable ? 'profit' : 'loss'}`}>
                {isProfitable ? '+' : ''}{formatPrice(details.pnl)}
                {details.pnlPercent !== undefined && (
                  <span className="percent">({isProfitable ? '+' : ''}{formatPercent(details.pnlPercent)})</span>
                )}
              </span>
            </div>
          )}
          {details.commission !== undefined && (
            <div className="tooltip-row">
              <span className="label">Commission:</span>
              <span className="value">{formatPrice(details.commission)}</span>
            </div>
          )}
          <div className="tooltip-row">
            <span className="label">Time:</span>
            <span className="value">{details.timestamp}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`kline-chart-container ${activeDrawingTool !== DrawingToolType.NONE ? 'drawing-mode' : ''}`}>
      {/* Chart header */}
      <div className="kline-header">
        <div className="symbol-info">
          {symbol && <span className="symbol">{symbol}</span>}
          {interval && <span className="interval">{interval}</span>}
        </div>
        {chartState.crosshairPosition && data.length > 0 && (
          <div className="crosshair-info">
            <span className="price">Price: {formatPrice(chartState.crosshairPosition.price)}</span>
          </div>
        )}
      </div>

      {/* Chart container */}
      <div
        ref={containerRef}
        className="kline-chart"
        style={{ width: autoSize ? '100%' : width, height: autoSize ? '100%' : height }}
      />

      {/* Drawing tools overlay */}
      {showDrawingTools && chartState.isReady && (
        <DrawingTools
          chart={chartRef.current}
          mainSeries={candlestickSeriesRef.current}
          drawings={drawings}
          activeDrawingTool={activeDrawingTool}
          theme={theme}
          onDrawingComplete={handleDrawingComplete}
          onDrawingUpdate={handleDrawingUpdate}
          onDrawingDelete={handleDrawingDelete}
          onToolChange={handleToolChange}
          onCoordinatesExport={onDrawingCoordinatesExport}
        />
      )}

      {/* Indicator panel */}
      {showIndicatorPanel && chartState.isReady && (
        <IndicatorPanel
          indicators={indicators}
          onIndicatorAdd={handleIndicatorAdd}
          onIndicatorRemove={handleIndicatorRemove}
          onIndicatorUpdate={handleIndicatorUpdate}
        />
      )}

      {/* Trade tooltip */}
      {renderTooltip()}

      {/* Loading state */}
      {!chartState.isReady && (
        <div className="kline-loading">
          <span>Loading chart...</span>
        </div>
      )}
    </div>
  );
};

export default KLineChartWithTools;
