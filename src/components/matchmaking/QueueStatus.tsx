import React, { useEffect, useState } from 'react';
import { useMatchmakingStore } from '@/store/matchmakingStore';
import { Badge } from '@/design-system/components/Badge';

interface QueueStatusProps {
  className?: string;
}

export const QueueStatus: React.FC<QueueStatusProps> = ({ className = '' }) => {
  const {
    inQueue,
    position,
    estimatedWaitTime,
    totalPlayers,
    mode,
    loading,
    fetchQueueStatus,
  } = useMatchmakingStore();

  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    if (!inQueue) {
      setElapsedTime(0);
      return;
    }

    const interval = setInterval(() => {
      setElapsedTime((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, [inQueue]);

  useEffect(() => {
    if (inQueue) {
      fetchQueueStatus();
      const statusInterval = setInterval(fetchQueueStatus, 5000);
      return () => clearInterval(statusInterval);
    }
  }, [inQueue, fetchQueueStatus]);

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds} сек`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes} мин ${remainingSeconds} сек`;
  };

  const getEstimatedTime = (): string => {
    if (estimatedWaitTime === null || estimatedWaitTime === 0) {
      return 'Вычисляется...';
    }
    return formatTime(estimatedWaitTime);
  };

  const getProgressPercentage = (): number => {
    if (estimatedWaitTime === null || estimatedWaitTime === 0) return 0;
    return Math.min((elapsedTime / estimatedWaitTime) * 100, 100);
  };

  const getStatusText = (): string => {
    if (!inQueue) return 'Не в очереди';
    if (position === null || position === 1) return 'Поиск соперника...';
    return `Позиция в очереди: ${position}`;
  };

  if (!inQueue) {
    return (
      <div className={`queue-status queue-status-idle ${className}`}>
        <div className="queue-status-content">
          <span className="status-icon">⏸️</span>
          <div className="status-info">
            <span className="status-text">Вы не в очереди</span>
            <span className="status-subtext">Нажмите "Найти игру" для начала</span>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={`queue-status queue-status-loading ${className}`}>
        <div className="queue-status-content">
          <div className="loading-spinner" />
          <div className="status-info">
            <span className="status-text">Обновление статуса...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`queue-status queue-status-active ${className}`}>
      <div className="queue-status-header">
        <div className="queue-mode-badge">
          <Badge>{mode === 'ONE_V_ONE' ? '1 на 1' : mode === 'TWO_V_TWO' ? '2 на 2' : mode}</Badge>
        </div>
        <span className="status-text">{getStatusText()}</span>
      </div>

      <div className="queue-progress">
        <svg className="progress-ring" viewBox="0 0 120 120">
          <circle
            className="progress-ring-bg"
            cx="60"
            cy="60"
            r="54"
            fill="none"
            strokeWidth="8"
          />
          <circle
            className="progress-ring-fill"
            cx="60"
            cy="60"
            r="54"
            fill="none"
            strokeWidth="8"
            strokeLinecap="round"
            style={{
              strokeDasharray: '339.292',
              strokeDashoffset: `${339.292 - (339.292 * getProgressPercentage()) / 100}`,
            }}
          />
        </svg>
        <div className="progress-center">
          <div className="progress-time">{formatTime(elapsedTime)}</div>
          <div className="progress-label">В очереди</div>
        </div>
      </div>

      <div className="queue-stats">
        <div className="queue-stat">
          <span className="stat-label">Игроков в очереди:</span>
          <span className="stat-value">{totalPlayers}</span>
        </div>
        <div className="queue-stat">
          <span className="stat-label">Ожидаемое время:</span>
          <span className="stat-value">{getEstimatedTime()}</span>
        </div>
      </div>

      <div className="queue-animation">
        <div className="searching-pulse" />
      </div>
    </div>
  );
};

export default QueueStatus;