import React from 'react';
import './OnlineStatus.css';

export interface OnlineStatusProps {
  isOnline: boolean;
  lastSeen?: string;
  showText?: boolean;
}

export const OnlineStatus: React.FC<OnlineStatusProps> = ({
  isOnline,
  lastSeen,
  showText = false,
}) => {
  const formatLastSeen = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'только что';
    if (diffMins < 60) return `${diffMins} мин назад`;
    if (diffHours < 24) return `${diffHours} ч назад`;
    if (diffDays < 7) return `${diffDays} д назад`;
    return date.toLocaleDateString('ru-RU');
  };

  return (
    <div className={`online-status ${isOnline ? 'online-status--online' : 'online-status--offline'}`}>
      <div className="online-status__indicator" />
      {showText && (
        <span className="online-status__text">
          {isOnline ? 'В сети' : lastSeen ? formatLastSeen(lastSeen) : 'Не в сети'}
        </span>
      )}
    </div>
  );
};