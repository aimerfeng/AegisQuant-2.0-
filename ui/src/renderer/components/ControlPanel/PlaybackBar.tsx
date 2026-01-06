/**
 * Titan-Quant Playback Control Bar Component
 * 
 * Provides playback controls for backtest replay:
 * - Pause/Play toggle
 * - Speed control (1x, 2x, 4x, 10x)
 * - Single step debugging
 * 
 * Requirements: 5.1
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useConnectionStore } from '../../stores/connectionStore';
import { MessageType } from '../../types/websocket';
import './PlaybackBar.css';

export type PlaybackSpeed = 1 | 2 | 4 | 10;

export interface PlaybackState {
  isPlaying: boolean;
  speed: PlaybackSpeed;
  currentTime: string;
  progress: number;
}

interface PlaybackBarProps {
  initialState?: Partial<PlaybackState>;
  onStateChange?: (state: PlaybackState) => void;
}

const SPEED_OPTIONS: PlaybackSpeed[] = [1, 2, 4, 10];

const PlaybackBar: React.FC<PlaybackBarProps> = ({
  initialState,
  onStateChange,
}) => {
  const { t } = useTranslation();
  const { wsService, connectionState } = useConnectionStore();
  
  const [playbackState, setPlaybackState] = useState<PlaybackState>({
    isPlaying: false,
    speed: 1,
    currentTime: '--:--:--',
    progress: 0,
    ...initialState,
  });

  const isConnected = connectionState === 'connected';

  const updateState = useCallback((updates: Partial<PlaybackState>) => {
    setPlaybackState(prev => {
      const newState = { ...prev, ...updates };
      onStateChange?.(newState);
      return newState;
    });
  }, [onStateChange]);

  const handlePlayPause = useCallback(() => {
    if (!wsService || !isConnected) return;

    const newIsPlaying = !playbackState.isPlaying;
    
    if (newIsPlaying) {
      wsService.send(MessageType.RESUME, { speed: playbackState.speed });
    } else {
      wsService.send(MessageType.PAUSE, {});
    }
    
    updateState({ isPlaying: newIsPlaying });
  }, [wsService, isConnected, playbackState.isPlaying, playbackState.speed, updateState]);

  const handleStep = useCallback(() => {
    if (!wsService || !isConnected) return;
    
    // Ensure paused before stepping
    if (playbackState.isPlaying) {
      wsService.send(MessageType.PAUSE, {});
      updateState({ isPlaying: false });
    }
    
    wsService.send(MessageType.STEP, {});
  }, [wsService, isConnected, playbackState.isPlaying, updateState]);

  const handleSpeedChange = useCallback((speed: PlaybackSpeed) => {
    if (!wsService || !isConnected) return;
    
    updateState({ speed });
    
    // If currently playing, update the speed on the server
    if (playbackState.isPlaying) {
      wsService.send(MessageType.RESUME, { speed });
    }
  }, [wsService, isConnected, playbackState.isPlaying, updateState]);

  const handleStop = useCallback(() => {
    if (!wsService || !isConnected) return;
    
    wsService.send(MessageType.STOP, {});
    updateState({ isPlaying: false, progress: 0 });
  }, [wsService, isConnected, updateState]);

  return (
    <div className="playback-bar">
      <div className="playback-controls">
        {/* Stop Button */}
        <button
          className="playback-btn playback-btn-stop"
          onClick={handleStop}
          disabled={!isConnected}
          title={t('playback.stop')}
          aria-label={t('playback.stop')}
        >
          <span className="playback-icon">⏹</span>
        </button>

        {/* Play/Pause Button */}
        <button
          className={`playback-btn playback-btn-primary ${playbackState.isPlaying ? 'playing' : ''}`}
          onClick={handlePlayPause}
          disabled={!isConnected}
          title={playbackState.isPlaying ? t('ui.pause') : t('playback.play')}
          aria-label={playbackState.isPlaying ? t('ui.pause') : t('playback.play')}
        >
          <span className="playback-icon">
            {playbackState.isPlaying ? '⏸' : '▶'}
          </span>
        </button>

        {/* Step Button */}
        <button
          className="playback-btn playback-btn-step"
          onClick={handleStep}
          disabled={!isConnected || playbackState.isPlaying}
          title={t('playback.step')}
          aria-label={t('playback.step')}
        >
          <span className="playback-icon">⏭</span>
        </button>
      </div>

      {/* Speed Control */}
      <div className="playback-speed">
        <span className="speed-label">{t('playback.speed')}:</span>
        <div className="speed-buttons">
          {SPEED_OPTIONS.map(speed => (
            <button
              key={speed}
              className={`speed-btn ${playbackState.speed === speed ? 'active' : ''}`}
              onClick={() => handleSpeedChange(speed)}
              disabled={!isConnected}
              title={`${speed}x ${t('playback.speed')}`}
              aria-label={`${speed}x ${t('playback.speed')}`}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>

      {/* Progress Display */}
      <div className="playback-progress">
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${playbackState.progress}%` }}
          />
        </div>
        <span className="progress-time">{playbackState.currentTime}</span>
      </div>

      {/* Status Indicator */}
      <div className="playback-status">
        <span className={`status-indicator ${playbackState.isPlaying ? 'playing' : 'paused'}`}>
          {playbackState.isPlaying ? t('status.running') : t('status.paused')}
        </span>
      </div>
    </div>
  );
};

export default PlaybackBar;
