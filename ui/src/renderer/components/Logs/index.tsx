/**
 * Logs Component
 * 
 * Displays system and trading logs.
 */

import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './Logs.css';

type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';

interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  source: string;
  message: string;
}

interface LogsProps {
  logs?: LogEntry[];
  maxLogs?: number;
}

const Logs: React.FC<LogsProps> = ({ logs = [], maxLogs = 100 }) => {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<LogLevel | 'ALL'>('ALL');
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Mock data for demonstration
  const mockLogs: LogEntry[] = logs.length > 0 ? logs : [
    { id: '1', timestamp: '14:32:15.123', level: 'INFO', source: 'Engine', message: 'Backtest started for MA Crossover Strategy' },
    { id: '2', timestamp: '14:32:15.456', level: 'INFO', source: 'Data', message: 'Loading BTC/USDT data from 2024-01-01 to 2024-12-31' },
    { id: '3', timestamp: '14:32:16.789', level: 'DEBUG', source: 'Strategy', message: 'Initialized MA indicators: fast=10, slow=20' },
    { id: '4', timestamp: '14:32:17.012', level: 'INFO', source: 'Engine', message: 'Processing 365 trading days...' },
    { id: '5', timestamp: '14:32:18.345', level: 'WARN', source: 'Risk', message: 'Position size exceeds 50% of portfolio' },
    { id: '6', timestamp: '14:32:19.678', level: 'INFO', source: 'Trade', message: 'BUY 0.5 BTC @ 42150.00' },
    { id: '7', timestamp: '14:32:20.901', level: 'ERROR', source: 'Network', message: 'WebSocket connection lost, reconnecting...' },
    { id: '8', timestamp: '14:32:21.234', level: 'INFO', source: 'Network', message: 'WebSocket reconnected successfully' },
  ];

  const filteredLogs = filter === 'ALL' 
    ? mockLogs 
    : mockLogs.filter(log => log.level === filter);

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [filteredLogs, autoScroll]);

  const getLevelClass = (level: LogLevel) => {
    return `log-level-${level.toLowerCase()}`;
  };

  return (
    <div className="logs-container">
      <div className="logs-toolbar">
        <div className="filter-buttons">
          {(['ALL', 'INFO', 'WARN', 'ERROR', 'DEBUG'] as const).map(level => (
            <button
              key={level}
              className={`filter-btn ${filter === level ? 'active' : ''} ${level !== 'ALL' ? getLevelClass(level as LogLevel) : ''}`}
              onClick={() => setFilter(level)}
            >
              {level}
            </button>
          ))}
        </div>
        <div className="logs-actions">
          <label className="auto-scroll-toggle">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            {t('logs.autoScroll', 'Auto-scroll')}
          </label>
          <button className="clear-btn" onClick={() => {}}>
            {t('logs.clear', 'Clear')}
          </button>
        </div>
      </div>
      
      <div className="logs-content">
        {filteredLogs.length === 0 ? (
          <div className="logs-empty">
            <span>{t('logs.noLogs', 'No logs to display')}</span>
          </div>
        ) : (
          filteredLogs.map(log => (
            <div key={log.id} className={`log-entry ${getLevelClass(log.level)}`}>
              <span className="log-timestamp">{log.timestamp}</span>
              <span className={`log-level ${getLevelClass(log.level)}`}>{log.level}</span>
              <span className="log-source">[{log.source}]</span>
              <span className="log-message">{log.message}</span>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
};

export default Logs;
