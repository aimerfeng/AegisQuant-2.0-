/**
 * KLine Chart Utilities
 * 
 * Helper functions for chart calculations and data transformations.
 */

import { Time } from 'lightweight-charts';
import {
  CandlestickData,
  VolumeData,
  MAConfig,
  MACDConfig,
  RSIConfig,
  BollingerConfig,
  IndicatorType,
} from './types';

/**
 * Calculate Simple Moving Average
 */
export function calculateSMA(data: CandlestickData[], period: number): { time: Time; value: number }[] {
  const result: { time: Time; value: number }[] = [];
  
  if (data.length < period) return result;
  
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close;
    }
    result.push({
      time: data[i].time,
      value: sum / period,
    });
  }
  
  return result;
}

/**
 * Calculate Exponential Moving Average
 */
export function calculateEMA(data: CandlestickData[], period: number): { time: Time; value: number }[] {
  const result: { time: Time; value: number }[] = [];
  
  if (data.length < period) return result;
  
  const multiplier = 2 / (period + 1);
  
  // First EMA is SMA
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += data[i].close;
  }
  let ema = sum / period;
  result.push({ time: data[period - 1].time, value: ema });
  
  // Calculate subsequent EMAs
  for (let i = period; i < data.length; i++) {
    ema = (data[i].close - ema) * multiplier + ema;
    result.push({ time: data[i].time, value: ema });
  }
  
  return result;
}

/**
 * Calculate MACD
 */
export function calculateMACD(
  data: CandlestickData[],
  fastPeriod: number = 12,
  slowPeriod: number = 26,
  signalPeriod: number = 9
): {
  macd: { time: Time; value: number }[];
  signal: { time: Time; value: number }[];
  histogram: { time: Time; value: number; color: string }[];
} {
  const fastEMA = calculateEMA(data, fastPeriod);
  const slowEMA = calculateEMA(data, slowPeriod);
  
  // Calculate MACD line
  const macdLine: { time: Time; value: number }[] = [];
  const slowStartIndex = slowPeriod - fastPeriod;
  
  for (let i = 0; i < slowEMA.length; i++) {
    const fastIndex = i + slowStartIndex;
    if (fastIndex < fastEMA.length) {
      macdLine.push({
        time: slowEMA[i].time,
        value: fastEMA[fastIndex].value - slowEMA[i].value,
      });
    }
  }
  
  // Calculate Signal line (EMA of MACD)
  const signalLine: { time: Time; value: number }[] = [];
  if (macdLine.length >= signalPeriod) {
    const multiplier = 2 / (signalPeriod + 1);
    
    let sum = 0;
    for (let i = 0; i < signalPeriod; i++) {
      sum += macdLine[i].value;
    }
    let signal = sum / signalPeriod;
    signalLine.push({ time: macdLine[signalPeriod - 1].time, value: signal });
    
    for (let i = signalPeriod; i < macdLine.length; i++) {
      signal = (macdLine[i].value - signal) * multiplier + signal;
      signalLine.push({ time: macdLine[i].time, value: signal });
    }
  }
  
  // Calculate Histogram
  const histogram: { time: Time; value: number; color: string }[] = [];
  const signalStartIndex = signalPeriod - 1;
  
  for (let i = 0; i < signalLine.length; i++) {
    const macdIndex = i + signalStartIndex;
    if (macdIndex < macdLine.length) {
      const value = macdLine[macdIndex].value - signalLine[i].value;
      histogram.push({
        time: signalLine[i].time,
        value,
        color: value >= 0 ? 'rgba(38, 166, 154, 0.8)' : 'rgba(239, 83, 80, 0.8)',
      });
    }
  }
  
  return { macd: macdLine, signal: signalLine, histogram };
}

/**
 * Calculate RSI
 */
export function calculateRSI(
  data: CandlestickData[],
  period: number = 14
): { time: Time; value: number }[] {
  const result: { time: Time; value: number }[] = [];
  
  if (data.length < period + 1) return result;
  
  // Calculate price changes
  const changes: number[] = [];
  for (let i = 1; i < data.length; i++) {
    changes.push(data[i].close - data[i - 1].close);
  }
  
  // Calculate initial average gain and loss
  let avgGain = 0;
  let avgLoss = 0;
  
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) {
      avgGain += changes[i];
    } else {
      avgLoss += Math.abs(changes[i]);
    }
  }
  
  avgGain /= period;
  avgLoss /= period;
  
  // First RSI
  let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  let rsi = 100 - (100 / (1 + rs));
  result.push({ time: data[period].time, value: rsi });
  
  // Calculate subsequent RSIs using smoothed averages
  for (let i = period; i < changes.length; i++) {
    const change = changes[i];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? Math.abs(change) : 0;
    
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    
    rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi = 100 - (100 / (1 + rs));
    result.push({ time: data[i + 1].time, value: rsi });
  }
  
  return result;
}

/**
 * Calculate Bollinger Bands
 */
export function calculateBollingerBands(
  data: CandlestickData[],
  period: number = 20,
  stdDev: number = 2
): {
  upper: { time: Time; value: number }[];
  middle: { time: Time; value: number }[];
  lower: { time: Time; value: number }[];
} {
  const middle = calculateSMA(data, period);
  const upper: { time: Time; value: number }[] = [];
  const lower: { time: Time; value: number }[] = [];
  
  for (let i = period - 1; i < data.length; i++) {
    // Calculate standard deviation
    let sumSquares = 0;
    const middleValue = middle[i - period + 1].value;
    
    for (let j = 0; j < period; j++) {
      const diff = data[i - j].close - middleValue;
      sumSquares += diff * diff;
    }
    
    const std = Math.sqrt(sumSquares / period);
    
    upper.push({
      time: data[i].time,
      value: middleValue + stdDev * std,
    });
    
    lower.push({
      time: data[i].time,
      value: middleValue - stdDev * std,
    });
  }
  
  return { upper, middle, lower };
}

/**
 * Generate volume data from candlestick data
 */
export function generateVolumeData(
  data: CandlestickData[],
  upColor: string = 'rgba(38, 166, 154, 0.5)',
  downColor: string = 'rgba(239, 83, 80, 0.5)'
): VolumeData[] {
  return data.map((candle) => ({
    time: candle.time,
    value: candle.volume || 0,
    color: candle.close >= candle.open ? upColor : downColor,
  }));
}

/**
 * Format price for display
 */
export function formatPrice(price: number, decimals: number = 2): string {
  return price.toFixed(decimals);
}

/**
 * Format volume for display
 */
export function formatVolume(volume: number): string {
  if (volume >= 1e9) {
    return (volume / 1e9).toFixed(2) + 'B';
  }
  if (volume >= 1e6) {
    return (volume / 1e6).toFixed(2) + 'M';
  }
  if (volume >= 1e3) {
    return (volume / 1e3).toFixed(2) + 'K';
  }
  return volume.toFixed(2);
}

/**
 * Format percentage for display
 */
export function formatPercent(value: number, decimals: number = 2): string {
  return (value * 100).toFixed(decimals) + '%';
}

/**
 * Generate unique ID
 */
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Clamp value between min and max
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Linear interpolation
 */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Calculate line intersection point
 */
export function lineIntersection(
  x1: number, y1: number,
  x2: number, y2: number,
  x3: number, y3: number,
  x4: number, y4: number
): { x: number; y: number } | null {
  const denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
  if (Math.abs(denom) < 1e-10) return null;
  
  const t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom;
  
  return {
    x: x1 + t * (x2 - x1),
    y: y1 + t * (y2 - y1),
  };
}

/**
 * Default Fibonacci levels
 */
export const DEFAULT_FIBONACCI_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];

/**
 * Default indicator configurations
 */
export const DEFAULT_MA_CONFIG: Omit<MAConfig, 'id'> = {
  type: IndicatorType.MA,
  period: 20,
  color: '#2196F3',
  lineWidth: 1,
  visible: true,
};

export const DEFAULT_EMA_CONFIG: Omit<MAConfig, 'id'> = {
  type: IndicatorType.EMA,
  period: 20,
  color: '#FF9800',
  lineWidth: 1,
  visible: true,
};

export const DEFAULT_MACD_CONFIG: Omit<MACDConfig, 'id'> = {
  type: IndicatorType.MACD,
  fastPeriod: 12,
  slowPeriod: 26,
  signalPeriod: 9,
  macdColor: '#2196F3',
  signalColor: '#FF9800',
  histogramPositiveColor: 'rgba(38, 166, 154, 0.8)',
  histogramNegativeColor: 'rgba(239, 83, 80, 0.8)',
  visible: true,
};

export const DEFAULT_RSI_CONFIG: Omit<RSIConfig, 'id'> = {
  type: IndicatorType.RSI,
  period: 14,
  overbought: 70,
  oversold: 30,
  lineColor: '#9C27B0',
  overboughtColor: 'rgba(239, 83, 80, 0.3)',
  oversoldColor: 'rgba(38, 166, 154, 0.3)',
  visible: true,
};

export const DEFAULT_BOLLINGER_CONFIG: Omit<BollingerConfig, 'id'> = {
  type: IndicatorType.BOLLINGER,
  period: 20,
  stdDev: 2,
  upperColor: '#2196F3',
  middleColor: '#FF9800',
  lowerColor: '#2196F3',
  fillColor: 'rgba(33, 150, 243, 0.1)',
  fillOpacity: 0.1,
  visible: true,
};
