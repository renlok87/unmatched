// ============================================================
// REPLAY PLAYER - UI компонент для воспроизведения записей игр
// ============================================================

import React, { useState, useEffect, useRef } from 'react';
import { formatTime } from './replayUtils';
import type { GameReplay, ReplayState } from '@/phaser/systems/ReplaySystem';
import './ReplayPlayer.css';

// ------------------------------------------------------------
// Props
// ------------------------------------------------------------

export interface ReplayPlayerProps {
  readonly replay: GameReplay | null;
  readonly onLoadReplay?: () => void;
  readonly onPlay?: () => void;
  readonly onPause?: () => void;
  readonly onStop?: () => void;
  readonly onSeek?: (time: number) => void;
  readonly onStep?: (direction: 'next' | 'previous') => void;
  readonly onReverse?: () => void;  // Обратное воспроизведение
  readonly onSpeedChange?: (speed: number) => void;
  readonly initialState?: ReplayState;
}

// ------------------------------------------------------------
// Компонент
// ------------------------------------------------------------

export const ReplayPlayer: React.FC<ReplayPlayerProps> = ({
  replay,
  onLoadReplay,
  onPlay,
  onPause,
  onStop,
  onSeek,
  onStep,
  onReverse,
  onSpeedChange,
  initialState,
}) => {
  const [state, setState] = useState<ReplayState>(
    initialState ?? {
      isPlaying: false,
      isPaused: false,
      isReversed: false,
      currentTime: 0,
      playbackSpeed: 1,
      currentEventIndex: 0,
      direction: 'forward',
      duration: 0,
      progress: 0,
    }
  );
  const [showTimeline, setShowTimeline] = useState(true);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);
  const [isReversed, setIsReversed] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // Обновление состояния из props
  useEffect(() => {
    if (initialState) {
      setState(initialState);
    }
  }, [initialState]);

  // Обработка клавиш
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!replay) return;

      switch (e.key) {
        case ' ':
          e.preventDefault();
          togglePlay();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          handleStep('previous');
          break;
        case 'ArrowRight':
          e.preventDefault();
          handleStep('next');
          break;
        case 'Escape':
          e.preventDefault();
          handleStop();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [replay, state.isPlaying, state.isPaused]);

  // Автоматическая прокрутка timeline
  useEffect(() => {
    if (!showTimeline || !containerRef.current) return;

    const timeline = containerRef.current.querySelector('.replay-player__timeline-progress');
    if (timeline) {
      timeline.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [state.currentTime, showTimeline]);

  // Обработчики
  const togglePlay = () => {
    if (state.isPlaying) {
      if (state.isPaused) {
        onPlay?.();
        setState(prev => ({ ...prev, isPlaying: true, isPaused: false }));
      } else {
        onPause?.();
        setState(prev => ({ ...prev, isPaused: true }));
      }
    } else {
      onPlay?.();
      setState(prev => ({ ...prev, isPlaying: true, isPaused: false }));
    }
  };

  const handleStop = () => {
    onStop?.();
    setState({
      isPlaying: false,
      isPaused: false,
      currentTime: 0,
      playbackSpeed: 1,
      currentEventIndex: 0,
    });
  };

  const handleStep = (direction: 'next' | 'previous') => {
    onStep?.(direction);
  };

  const handleReverse = () => {
    setIsReversed(!isReversed);
    onReverse?.();
    setState(prev => ({
      ...prev,
      direction: !isReversed ? 'backward' : 'forward',
      isReversed: !isReversed,
    }));
  };

  const handleSeek = (time: number) => {
    onSeek?.(time);
    setState(prev => ({ ...prev, currentTime: time }));
  };

  const handleSpeedChange = (speed: number) => {
    onSpeedChange?.(speed);
    setState(prev => ({ ...prev, playbackSpeed: speed }));
    setShowSpeedMenu(false);
  };

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!replay) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    const time = percent * replay.duration;

    handleSeek(time);
  };

  // Если нет replay - показываем кнопку загрузки
  if (!replay) {
    return (
      <div className="replay-player replay-player--empty">
        <button
          className="replay-player__load-btn"
          onClick={onLoadReplay}
        >
          <span className="replay-player__load-icon">📁</span>
          Load Replay
        </button>
      </div>
    );
  }

  const progress = replay.duration ? (state.currentTime / replay.duration) * 100 : 0;
  const isPlaying = state.isPlaying && !state.isPaused;

  return (
    <div ref={containerRef} className="replay-player">
      {/* Заголовок с информацией о replay */}
      <div className="replay-player__header">
        <div className="replay-player__info">
          <h3 className="replay-player__title">
            {replay.players.map(p => p.userName || p.heroId).join(' vs ')}
          </h3>
          <div className="replay-player__meta">
            <span className="replay-player__meta-item">
              <span className="replay-player__meta-icon">⏱</span>
              {formatTime(replay.duration)}
            </span>
            <span className="replay-player__meta-item">
              <span className="replay-player__meta-icon">📊</span>
              {replay.events.length} events
            </span>
            {replay.winnerId && (
              <span className="replay-player__meta-item">
                <span className="replay-player__meta-icon">🏆</span>
                {replay.players.find(p => p.userId === replay.winnerId)?.heroId || 'Winner'}
              </span>
            )}
          </div>
        </div>

        <button
          className="replay-player__close-btn"
          onClick={handleStop}
          title="Close replay"
        >
          ✕
        </button>
      </div>

      {/* Timeline */}
      {showTimeline && (
        <div className="replay-player__timeline-container">
          <div className="replay-player__timeline" onClick={handleTimelineClick}>
            {/* Фон timeline */}
            <div className="replay-player__timeline-bg" />

            {/* Маркеры событий */}
            <div className="replay-player__events">
              {replay.events.map((event, index) => (
                <div
                  key={index}
                  className={`replay-player__event-marker replay-player__event-marker--${event.type}`}
                  style={{
                    left: `${(event.timestamp / replay.duration) * 100}%`,
                  }}
                  title={`${event.type} (${formatTime(event.timestamp)})`}
                />
              ))}
            </div>

            {/* Прогресс бар */}
            <div
              className="replay-player__timeline-progress"
              style={{ width: `${progress}%` }}
            >
              <div className="replay-player__timeline-thumb" />
            </div>
          </div>

          {/* Время */}
          <div className="replay-player__time-display">
            <span className="replay-player__time-current">
              {formatTime(state.currentTime)}
            </span>
            <span className="replay-player__time-separator">/</span>
            <span className="replay-player__time-total">
              {formatTime(replay.duration)}
            </span>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="replay-player__controls">
        {/* Воспроизведение */}
        <div className="replay-player__playback-controls">
          <button
            className="replay-player__btn replay-player__btn--control"
            onClick={() => handleStep('previous')}
            disabled={!replay || state.currentEventIndex === 0}
            title="Previous event (←)"
          >
            <svg viewBox="0 0 24 24" width="24" height="24">
              <path d="M6 6h2v12H6V6zm3.5 6l8.5 6V6l-8.5 6z" fill="currentColor" />
            </svg>
          </button>

          <button
            className={`replay-player__btn replay-player__btn--control ${isReversed ? 'replay-player__btn--reversed' : ''}`}
            onClick={handleReverse}
            disabled={!state.isPlaying && !isReversed}
            title={isReversed ? 'Forward playback' : 'Reverse playback'}
          >
            <svg viewBox="0 0 24 24" width="24" height="24">
              {isReversed ? (
                <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" fill="currentColor" />
              ) : (
                <path d="M6 6h2v12H6V6zm3.5 6l8.5 6V6l-8.5 6z" fill="currentColor" />
              )}
            </svg>
          </button>

          <button
            className={`replay-player__btn replay-player__btn--play ${isPlaying ? 'replay-player__btn--playing' : ''}`}
            onClick={togglePlay}
            title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
          >
            {isPlaying ? (
              <svg viewBox="0 0 24 24" width="24" height="24">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" fill="currentColor" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" width="24" height="24">
                <path d="M8 5v14l11-7z" fill="currentColor" />
              </svg>
            )}
          </button>

          <button
            className="replay-player__btn replay-player__btn--control"
            onClick={() => handleStep('next')}
            disabled={!replay || state.currentEventIndex >= replay.events.length}
            title="Next event (→)"
          >
            <svg viewBox="0 0 24 24" width="24" height="24">
              <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" fill="currentColor" />
            </svg>
          </button>

          <button
            className="replay-player__btn replay-player__btn--stop"
            onClick={handleStop}
            title="Stop (Esc)"
          >
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M6 6h12v12H6V6z" fill="currentColor" />
            </svg>
          </button>
        </div>

        {/* Скорость воспроизведения */}
        <div className="replay-player__speed-control">
          <button
            className="replay-player__btn replay-player__btn--speed"
            onClick={() => setShowSpeedMenu(!showSpeedMenu)}
          >
            {state.playbackSpeed}×
          </button>

          {showSpeedMenu && (
            <div className="replay-player__speed-menu">
              {[0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3].map(speed => (
                <button
                  key={speed}
                  className={`replay-player__speed-option ${
                    state.playbackSpeed === speed ? 'replay-player__speed-option--active' : ''
                  }`}
                  onClick={() => handleSpeedChange(speed)}
                >
                  {speed}×
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Доп. кнопки */}
        <div className="replay-player__extra-controls">
          <button
            className="replay-player__btn replay-player__btn--toggle"
            onClick={() => setShowTimeline(!showTimeline)}
            title="Toggle timeline"
          >
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" fill="currentColor" />
            </svg>
          </button>

          <button
            className="replay-player__btn replay-player__btn--export"
            onClick={() => exportReplay(replay)}
            title="Export replay"
          >
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" fill="currentColor" />
            </svg>
          </button>
        </div>
      </div>

      {/* Информация о текущем событии */}
      {replay.events[state.currentEventIndex] && (
        <div className="replay-player__event-info">
          <span className="replay-player__event-type">
            {replay.events[state.currentEventIndex].type}
          </span>
          <span className="replay-player__event-time">
            at {formatTime(replay.events[state.currentEventIndex].timestamp)}
          </span>
        </div>
      )}
    </div>
  );
};

// ------------------------------------------------------------
// Утилиты
// ------------------------------------------------------------

function exportReplay(replay: GameReplay): void {
  const json = JSON.stringify(replay, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `replay_${replay.id}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default ReplayPlayer;
