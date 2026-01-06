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
import { useIntegration } from '../../hooks/useIntegration';
import { useBacktestStore, usePlaybackState } from '../../stores/backtestStore';
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
  const { isConnected, pause, resume, step, stop } = useIntegration();
  const backtestPlayback = usePlaybackState();
  const { play: storePlay, pause: storePause, setPlaybackSpeed } = useBacktestStore();
  
  const [playbackState, setPlaybackState] = useState<PlaybackState>({
    isPlaying: backtestPlayback.isPlaying,
    speed: backtestPlayback.speed,
    currentTime: backtestPlayback.currentTime,
    progress: backtestPlayback.progress,
    ...initialState,
  });

  const updateState = useCallback((updates: Partial<PlaybackState>) => {
    setPlaybackState(prev => {
      const newState = { ...prev, ...updates };
      onStateChange?.(newState);
      return newState;
    });
  }, [onStateChange]);

  const handlePlayPause = useCallback(async () => {
    if (!isConnected) return;

    const newIsPlaying = !playbackState.isPlaying;
    
    try {
      if (newIsPlaying) {
        await resume();
        storePlay();
      } else {
        await pause();
        storePause();
      }
      updateState({ isPlaying: newIsPlaying });
    } catch (error) {
      console.error('Failed to toggle playback:', error);
    }
  }, [isConnected, playbackState.isPlaying, resume, pause, storePlay, storePause, updateState]);

  const handleStep = useCallback(async () => {
    if (!isConnected) return;
    
    try {
      // Ensure paused before stepping
      if (playbackState.isPlaying) {
        await pause();
        storePause();
        updateState({ isPlaying: false });
      }
      
      await step();
    } catch (error) {
      console.error('Failed to step:', error);
    }
  }, [isConnected, playbackState.isPlaying, pause, step, storePause, updateState]);

  const handleSpeedChange = useCallback(async (speed: PlaybackSpeed) => {
    if (!isConnected) return;
    
    setPlaybackSpeed(speed);
    updateState({ speed });
    
    // If currently playing, update the speed on the server
    if (playbackState.isPlaying) {
      try {
        await resume();
      } catch (error) {
        console.error('Failed to update speed:', error);
      }
    }
  }, [isConnected, playbackState.isPlaying, setPlaybackSpeed, resume, updateState]);

  const handleStop = useCallback(async () => {
    if (!isConnected) return;
    
    try {
      await stop();
      storePause();
      updateState({ isPlaying: false, progress: 0 });
    } catch (error) {
      console.error('Failed to stop:', error);
    }
  }, [isConnected, stop, storePause, updateState]);

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
