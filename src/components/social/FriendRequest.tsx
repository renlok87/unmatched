import React from 'react';
import { Button } from '@/design-system/components/Button';
import { OnlineStatus } from './OnlineStatus';
import './FriendRequest.css';

export interface FriendRequestProps {
  id: string;
  user: {
    id: string;
    username: string;
    avatar?: string;
  };
  isOnline?: boolean;
  lastSeen?: string;
  onAccept: (requestId: string) => void;
  onDecline: (requestId: string) => void;
  isLoading?: boolean;
}

export const FriendRequest: React.FC<FriendRequestProps> = ({
  id,
  user,
  isOnline = false,
  lastSeen,
  onAccept,
  onDecline,
  isLoading = false,
}) => {
  return (
    <div className="friend-request">
      <div className="friend-request__user">
        {user.avatar ? (
          <img src={user.avatar} alt={user.username} className="friend-request__avatar" />
        ) : (
          <div className="friend-request__avatar-placeholder">
            {user.username[0].toUpperCase()}
          </div>
        )}
        <div className="friend-request__info">
          <div className="friend-request__username">{user.username}</div>
          <OnlineStatus isOnline={isOnline} lastSeen={lastSeen} showText />
        </div>
      </div>
      <div className="friend-request__actions">
        <Button
          variant="success"
          size="sm"
          onClick={() => onAccept(id)}
          disabled={isLoading}
          loading={isLoading}
        >
          Принять
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDecline(id)}
          disabled={isLoading}
        >
          Отклонить
        </Button>
      </div>
    </div>
  );
};