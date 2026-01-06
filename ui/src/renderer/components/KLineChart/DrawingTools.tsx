/**
 * Drawing Tools Component
 * 
 * Provides drawing tools for the K-Line chart:
 * - Trend lines
 * - Fibonacci retracement
 * - Rectangle boxes
 * 
 * Coordinates are exposed to strategies for reading.
 * Requirements: 3.2
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Time, IChartApi, ISeriesApi } from 'lightweight-charts';
import {
  Drawing,
  DrawingToolType,
  TrendLineDrawing,
  FibonacciDrawing,
  RectangleDrawing,
  ChartTheme,
} from './types';
import { generateId, DEFAULT_FIBONACCI_LEVELS } from './utils';
import { LineStyle } from 'lightweight-charts';
import './DrawingTools.css';

interface DrawingToolsProps {
  chart: IChartApi | null;
  mainSeries: ISeriesApi<'Candlestick'> | null;
  drawings: Drawing[];
  activeDrawingTool: DrawingToolType;
  theme: ChartTheme;
  onDrawingComplete: (drawing: Drawing) => void;
  onDrawingUpdate: (drawing: Drawing) => void;
  onDrawingDelete: (drawingId: string) => void;
  onToolChange: (tool: DrawingToolType) => void;
  onCoordinatesExport?: (drawings: Drawing[]) => void;
}

interface DrawingPoint {
  time: Time;
  price: number;
  x: number;
  y: number;
}

/**
 * Drawing Tools Component
 */
const DrawingTools: React.FC<DrawingToolsProps> = ({
  chart,
  mainSeries,
  drawings,
  activeDrawingTool,
  theme,
  onDrawingComplete,
  onDrawingUpdate,
  onDrawingDelete,
  onToolChange,
  onCoordinatesExport,
}) => {
  const { t } = useTranslation();
  const svgRef = useRef<SVGSVGElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<DrawingPoint | null>(null);
  const [currentPoint, setCurrentPoint] = useState<DrawingPoint | null>(null);
  const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null);
  const [svgDimensions, setSvgDimensions] = useState({ width: 0, height: 0 });

  // Update SVG dimensions when chart resizes
  useEffect(() => {
    if (!chart) return;

    const updateDimensions = () => {
      const chartElement = chart.chartElement();
      if (chartElement) {
        setSvgDimensions({
          width: chartElement.clientWidth,
          height: chartElement.clientHeight,
        });
      }
    };

    updateDimensions();
    
    // Listen for resize
    const resizeObserver = new ResizeObserver(updateDimensions);
    const chartElement = chart.chartElement();
    if (chartElement) {
      resizeObserver.observe(chartElement);
    }

    return () => resizeObserver.disconnect();
  }, [chart]);

  // Convert chart coordinates to pixel coordinates
  const chartToPixel = useCallback((time: Time, price: number): { x: number; y: number } | null => {
    if (!chart || !mainSeries) return null;

    const timeScale = chart.timeScale();
    const x = timeScale.timeToCoordinate(time);
    const y = mainSeries.priceToCoordinate(price);

    if (x === null || y === null) return null;
    return { x, y };
  }, [chart, mainSeries]);

  // Convert pixel coordinates to chart coordinates
  const pixelToChart = useCallback((x: number, y: number): { time: Time; price: number } | null => {
    if (!chart || !mainSeries) return null;

    const timeScale = chart.timeScale();
    const time = timeScale.coordinateToTime(x);
    const price = mainSeries.coordinateToPrice(y);

    if (time === null || price === null) return null;
    return { time, price };
  }, [chart, mainSeries]);

  // Handle mouse down for starting a drawing
  const handleMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (activeDrawingTool === DrawingToolType.NONE || !chart || !mainSeries) return;

    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const chartCoords = pixelToChart(x, y);

    if (!chartCoords) return;

    setIsDrawing(true);
    setStartPoint({
      time: chartCoords.time,
      price: chartCoords.price,
      x,
      y,
    });
    setCurrentPoint({
      time: chartCoords.time,
      price: chartCoords.price,
      x,
      y,
    });
  }, [activeDrawingTool, chart, mainSeries, pixelToChart]);

  // Handle mouse move for drawing preview
  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing || !startPoint) return;

    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const chartCoords = pixelToChart(x, y);

    if (!chartCoords) return;

    setCurrentPoint({
      time: chartCoords.time,
      price: chartCoords.price,
      x,
      y,
    });
  }, [isDrawing, startPoint, pixelToChart]);

  // Handle mouse up for completing a drawing
  const handleMouseUp = useCallback(() => {
    if (!isDrawing || !startPoint || !currentPoint) {
      setIsDrawing(false);
      return;
    }

    // Create the drawing based on active tool
    let newDrawing: Drawing | null = null;

    switch (activeDrawingTool) {
      case DrawingToolType.TREND_LINE:
        newDrawing = {
          id: generateId(),
          type: DrawingToolType.TREND_LINE,
          visible: true,
          color: '#2196F3',
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          startPoint: { time: startPoint.time, price: startPoint.price },
          endPoint: { time: currentPoint.time, price: currentPoint.price },
          extendLeft: false,
          extendRight: false,
        } as TrendLineDrawing;
        break;

      case DrawingToolType.FIBONACCI:
        newDrawing = {
          id: generateId(),
          type: DrawingToolType.FIBONACCI,
          visible: true,
          color: '#FF9800',
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          startPoint: { time: startPoint.time, price: startPoint.price },
          endPoint: { time: currentPoint.time, price: currentPoint.price },
          levels: DEFAULT_FIBONACCI_LEVELS,
          showLabels: true,
        } as FibonacciDrawing;
        break;

      case DrawingToolType.RECTANGLE:
        newDrawing = {
          id: generateId(),
          type: DrawingToolType.RECTANGLE,
          visible: true,
          color: '#9C27B0',
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          topLeft: {
            time: startPoint.time < currentPoint.time ? startPoint.time : currentPoint.time,
            price: Math.max(startPoint.price, currentPoint.price),
          },
          bottomRight: {
            time: startPoint.time > currentPoint.time ? startPoint.time : currentPoint.time,
            price: Math.min(startPoint.price, currentPoint.price),
          },
          fillColor: '#9C27B0',
          fillOpacity: 0.1,
        } as RectangleDrawing;
        break;
    }

    if (newDrawing) {
      onDrawingComplete(newDrawing);
      
      // Export coordinates for strategy access
      if (onCoordinatesExport) {
        onCoordinatesExport([...drawings, newDrawing]);
      }
    }

    setIsDrawing(false);
    setStartPoint(null);
    setCurrentPoint(null);
  }, [isDrawing, startPoint, currentPoint, activeDrawingTool, drawings, onDrawingComplete, onCoordinatesExport]);

  // Render trend line
  const renderTrendLine = (drawing: TrendLineDrawing, isPreview: boolean = false) => {
    const start = chartToPixel(drawing.startPoint.time, drawing.startPoint.price);
    const end = chartToPixel(drawing.endPoint.time, drawing.endPoint.price);

    if (!start || !end) return null;

    const isSelected = selectedDrawingId === drawing.id;

    return (
      <g key={drawing.id} className={`drawing trend-line ${isSelected ? 'selected' : ''}`}>
        <line
          x1={start.x}
          y1={start.y}
          x2={end.x}
          y2={end.y}
          stroke={drawing.color}
          strokeWidth={isSelected ? drawing.lineWidth + 1 : drawing.lineWidth}
          strokeDasharray={drawing.lineStyle === LineStyle.Dashed ? '5,5' : undefined}
          opacity={isPreview ? 0.6 : 1}
          onClick={() => !isPreview && setSelectedDrawingId(drawing.id)}
        />
        {isSelected && !isPreview && (
          <>
            <circle
              cx={start.x}
              cy={start.y}
              r={5}
              className="control-point"
            />
            <circle
              cx={end.x}
              cy={end.y}
              r={5}
              className="control-point"
            />
          </>
        )}
      </g>
    );
  };

  // Render Fibonacci retracement
  const renderFibonacci = (drawing: FibonacciDrawing, isPreview: boolean = false) => {
    const start = chartToPixel(drawing.startPoint.time, drawing.startPoint.price);
    const end = chartToPixel(drawing.endPoint.time, drawing.endPoint.price);

    if (!start || !end) return null;

    const isSelected = selectedDrawingId === drawing.id;
    const priceRange = drawing.startPoint.price - drawing.endPoint.price;
    const minX = Math.min(start.x, end.x);
    const maxX = Math.max(start.x, end.x);
    const width = maxX - minX;

    return (
      <g key={drawing.id} className={`drawing fibonacci ${isSelected ? 'selected' : ''}`}>
        {drawing.levels.map((level, index) => {
          const levelPrice = drawing.endPoint.price + priceRange * level;
          const levelCoord = chartToPixel(drawing.startPoint.time, levelPrice);
          if (!levelCoord) return null;

          return (
            <g key={`${drawing.id}-level-${index}`}>
              <line
                x1={minX}
                y1={levelCoord.y}
                x2={maxX}
                y2={levelCoord.y}
                stroke={drawing.color}
                strokeWidth={drawing.lineWidth}
                strokeDasharray="4,4"
                opacity={isPreview ? 0.6 : 0.8}
              />
              {drawing.showLabels && !isPreview && (
                <text
                  x={maxX + 5}
                  y={levelCoord.y + 4}
                  fill={theme.textColor}
                  fontSize={10}
                  className="fibonacci-label"
                >
                  {(level * 100).toFixed(1)}%
                </text>
              )}
            </g>
          );
        })}
        {isSelected && !isPreview && (
          <>
            <circle cx={start.x} cy={start.y} r={5} className="control-point" />
            <circle cx={end.x} cy={end.y} r={5} className="control-point" />
          </>
        )}
      </g>
    );
  };

  // Render rectangle
  const renderRectangle = (drawing: RectangleDrawing, isPreview: boolean = false) => {
    const topLeft = chartToPixel(drawing.topLeft.time, drawing.topLeft.price);
    const bottomRight = chartToPixel(drawing.bottomRight.time, drawing.bottomRight.price);

    if (!topLeft || !bottomRight) return null;

    const isSelected = selectedDrawingId === drawing.id;
    const x = Math.min(topLeft.x, bottomRight.x);
    const y = Math.min(topLeft.y, bottomRight.y);
    const width = Math.abs(bottomRight.x - topLeft.x);
    const height = Math.abs(bottomRight.y - topLeft.y);

    return (
      <g key={drawing.id} className={`drawing rectangle ${isSelected ? 'selected' : ''}`}>
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          stroke={drawing.color}
          strokeWidth={isSelected ? drawing.lineWidth + 1 : drawing.lineWidth}
          fill={drawing.fillColor || drawing.color}
          fillOpacity={drawing.fillOpacity || 0.1}
          opacity={isPreview ? 0.6 : 1}
          onClick={() => !isPreview && setSelectedDrawingId(drawing.id)}
        />
        {isSelected && !isPreview && (
          <>
            <circle cx={x} cy={y} r={5} className="control-point" />
            <circle cx={x + width} cy={y} r={5} className="control-point" />
            <circle cx={x} cy={y + height} r={5} className="control-point" />
            <circle cx={x + width} cy={y + height} r={5} className="control-point" />
          </>
        )}
      </g>
    );
  };

  // Render preview drawing while user is drawing
  const renderPreview = () => {
    if (!isDrawing || !startPoint || !currentPoint) return null;

    const previewDrawing: Drawing = (() => {
      switch (activeDrawingTool) {
        case DrawingToolType.TREND_LINE:
          return {
            id: 'preview',
            type: DrawingToolType.TREND_LINE,
            visible: true,
            color: '#2196F3',
            lineWidth: 1,
            lineStyle: LineStyle.Solid,
            startPoint: { time: startPoint.time, price: startPoint.price },
            endPoint: { time: currentPoint.time, price: currentPoint.price },
          } as TrendLineDrawing;

        case DrawingToolType.FIBONACCI:
          return {
            id: 'preview',
            type: DrawingToolType.FIBONACCI,
            visible: true,
            color: '#FF9800',
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            startPoint: { time: startPoint.time, price: startPoint.price },
            endPoint: { time: currentPoint.time, price: currentPoint.price },
            levels: DEFAULT_FIBONACCI_LEVELS,
            showLabels: false,
          } as FibonacciDrawing;

        case DrawingToolType.RECTANGLE:
          return {
            id: 'preview',
            type: DrawingToolType.RECTANGLE,
            visible: true,
            color: '#9C27B0',
            lineWidth: 1,
            lineStyle: LineStyle.Solid,
            topLeft: {
              time: startPoint.time < currentPoint.time ? startPoint.time : currentPoint.time,
              price: Math.max(startPoint.price, currentPoint.price),
            },
            bottomRight: {
              time: startPoint.time > currentPoint.time ? startPoint.time : currentPoint.time,
              price: Math.min(startPoint.price, currentPoint.price),
            },
            fillColor: '#9C27B0',
            fillOpacity: 0.1,
          } as RectangleDrawing;

        default:
          return null;
      }
    })();

    if (!previewDrawing) return null;

    switch (previewDrawing.type) {
      case DrawingToolType.TREND_LINE:
        return renderTrendLine(previewDrawing as TrendLineDrawing, true);
      case DrawingToolType.FIBONACCI:
        return renderFibonacci(previewDrawing as FibonacciDrawing, true);
      case DrawingToolType.RECTANGLE:
        return renderRectangle(previewDrawing as RectangleDrawing, true);
      default:
        return null;
    }
  };

  // Handle delete key for selected drawing
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedDrawingId) {
        onDrawingDelete(selectedDrawingId);
        setSelectedDrawingId(null);
      }
      if (e.key === 'Escape') {
        setSelectedDrawingId(null);
        onToolChange(DrawingToolType.NONE);
        setIsDrawing(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedDrawingId, onDrawingDelete, onToolChange]);

  return (
    <div className="drawing-tools-container">
      {/* Drawing toolbar */}
      <div className="drawing-toolbar">
        <button
          className={`tool-btn ${activeDrawingTool === DrawingToolType.TREND_LINE ? 'active' : ''}`}
          onClick={() => onToolChange(
            activeDrawingTool === DrawingToolType.TREND_LINE 
              ? DrawingToolType.NONE 
              : DrawingToolType.TREND_LINE
          )}
          title={t('chart.trendLine')}
        >
          📈
        </button>
        <button
          className={`tool-btn ${activeDrawingTool === DrawingToolType.FIBONACCI ? 'active' : ''}`}
          onClick={() => onToolChange(
            activeDrawingTool === DrawingToolType.FIBONACCI 
              ? DrawingToolType.NONE 
              : DrawingToolType.FIBONACCI
          )}
          title={t('chart.fibonacci')}
        >
          📐
        </button>
        <button
          className={`tool-btn ${activeDrawingTool === DrawingToolType.RECTANGLE ? 'active' : ''}`}
          onClick={() => onToolChange(
            activeDrawingTool === DrawingToolType.RECTANGLE 
              ? DrawingToolType.NONE 
              : DrawingToolType.RECTANGLE
          )}
          title={t('chart.rectangle')}
        >
          ⬜
        </button>
        <div className="toolbar-divider" />
        <button
          className="tool-btn clear-btn"
          onClick={() => {
            drawings.forEach(d => onDrawingDelete(d.id));
            setSelectedDrawingId(null);
          }}
          title={t('chart.clearDrawings')}
          disabled={drawings.length === 0}
        >
          🗑️
        </button>
      </div>

      {/* Drawing overlay SVG */}
      <svg
        ref={svgRef}
        className={`drawing-overlay ${activeDrawingTool !== DrawingToolType.NONE ? 'active' : ''}`}
        width={svgDimensions.width}
        height={svgDimensions.height}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* Render existing drawings */}
        {drawings.filter(d => d.visible).map((drawing) => {
          switch (drawing.type) {
            case DrawingToolType.TREND_LINE:
              return renderTrendLine(drawing as TrendLineDrawing);
            case DrawingToolType.FIBONACCI:
              return renderFibonacci(drawing as FibonacciDrawing);
            case DrawingToolType.RECTANGLE:
              return renderRectangle(drawing as RectangleDrawing);
            default:
              return null;
          }
        })}

        {/* Render preview */}
        {renderPreview()}
      </svg>
    </div>
  );
};

export default DrawingTools;
