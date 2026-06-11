import React, { useState } from 'react';
import { useQuery, useMutation, gql } from '@apollo/client';
import { OnlineStatus } from './OnlineStatus';
import { FriendRequest } from './FriendRequest';
import { Button } from '@/design-system/components/Button';
import { Input } from '@/design-system/components/Input';
import './FriendsList.css';

const GET_FRIENDS = gql`
  query GetFriends {
    friends {
      id
      user {
        id
        username
        avatar
      }
      isOnline
      lastSeen
      status
    }
  }
`;

const GET_FRIEND_REQUESTS = gql`
  query GetFriendRequests {
    friendRequests {
      id
      user {
        id
        username
        avatar
      }
      createdAt
    }
  }
`;

const ACCEPT_FRIEND_REQUEST = gql`
  mutation AcceptFriendRequest($requestId: ID!) {
    acceptFriendRequest(requestId: $requestId) {
      id
      status
    }
  }
`;

const DECLINE_FRIEND_REQUEST = gql`
  mutation DeclineFriendRequest($requestId: ID!) {
    declineFriendRequest(requestId: $requestId) {
      id
    }
  }
`;

const REMOVE_FRIEND = gql`
  mutation RemoveFriend($friendId: ID!) {
    removeFriend(friendId: $friendId) {
      id
    }
  }
`;

export const FriendsList: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'friends' | 'requests'>('friends');
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());

  const { data: friendsData, loading: friendsLoading, refetch: refetchFriends } = useQuery(
    GET_FRIENDS,
  );
  const { data: requestsData, loading: requestsLoading, refetch: refetchRequests } = useQuery(
    GET_FRIEND_REQUESTS,
  );

  const [acceptRequest] = useMutation(ACCEPT_FRIEND_REQUEST, {
    onCompleted: () => {
      refetchFriends();
      refetchRequests();
    },
  });

  const [declineRequest] = useMutation(DECLINE_FRIEND_REQUEST, {
    onCompleted: () => {
      refetchRequests();
    },
  });

  const [removeFriend] = useMutation(REMOVE_FRIEND, {
    onCompleted: () => {
      refetchFriends();
    },
  });

  const handleAccept = async (requestId: string) => {
    setLoadingActions((prev) => new Set(prev).add(requestId));
    try {
      await acceptRequest({ variables: { requestId } });
    } finally {
      setLoadingActions((prev) => {
        const next = new Set(prev);
        next.delete(requestId);
        return next;
      });
    }
  };

  const handleDecline = async (requestId: string) => {
    setLoadingActions((prev) => new Set(prev).add(requestId));
    try {
      await declineRequest({ variables: { requestId } });
    } finally {
      setLoadingActions((prev) => {
        const next = new Set(prev);
        next.delete(requestId);
        return next;
      });
    }
  };

  const handleRemoveFriend = async (friendId: string) => {
    if (!confirm('Вы уверены, что хотите удалить этого друга?')) return;
    
    try {
      await removeFriend({ variables: { friendId } });
    } catch (error) {
      console.error('Failed to remove friend:', error);
    }
  };

  const filteredFriends = friendsData?.friends?.filter((friend: any) =>
    friend.user.username.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  const onlineFriends = filteredFriends.filter((f: any) => f.isOnline);
  const offlineFriends = filteredFriends.filter((f: any) => !f.isOnline);

  const requestCount = requestsData?.friendRequests?.length || 0;

  return (
    <div className="friends-list">
      <div className="friends-list__header">
        <h2 className="friends-list__title">Друзья</h2>
        <div className="friends-list__tabs">
          <button
            type="button"
            className={`friends-list__tab ${
              activeTab === 'friends' ? 'friends-list__tab--active' : ''
            }`}
            onClick={() => setActiveTab('friends')}
          >
            Друзья ({filteredFriends.length})
          </button>
          <button
            type="button"
            className={`friends-list__tab ${
              activeTab === 'requests' ? 'friends-list__tab--active' : ''
            }`}
            onClick={() => setActiveTab('requests')}
          >
            Запросы {requestCount > 0 && `(${requestCount})`}
          </button>
        </div>
      </div>

      <Input
        placeholder="Поиск друзей..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="friends-list__search"
      />

      {activeTab === 'friends' && (
        <div className="friends-list__content">
          {friendsLoading ? (
            <div className="friends-list__loading">Загрузка...</div>
          ) : filteredFriends.length === 0 ? (
            <div className="friends-list__empty">
              {searchQuery ? 'Друзья не найдены' : 'У вас пока нет друзей'}
            </div>
          ) : (
            <>
              {onlineFriends.length > 0 && (
                <div className="friends-list__section">
                  <h3 className="friends-list__section-title">В сети</h3>
                  <div className="friends-list__items">
                    {onlineFriends.map((friend: any) => (
                      <div key={friend.id} className="friends-list__item">
                        <div className="friends-list__user">
                          {friend.user.avatar ? (
                            <img
                              src={friend.user.avatar}
                              alt={friend.user.username}
                              className="friends-list__avatar"
                            />
                          ) : (
                            <div className="friends-list__avatar-placeholder">
                              {friend.user.username[0].toUpperCase()}
                            </div>
                          )}
                          <div className="friends-list__info">
                            <div className="friends-list__username">
                              {friend.user.username}
                            </div>
                            <OnlineStatus
                              isOnline={friend.isOnline}
                              lastSeen={friend.lastSeen}
                              showText
                            />
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveFriend(friend.id)}
                        >
                          Удалить
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {offlineFriends.length > 0 && (
                <div className="friends-list__section">
                  <h3 className="friends-list__section-title">Не в сети</h3>
                  <div className="friends-list__items">
                    {offlineFriends.map((friend: any) => (
                      <div key={friend.id} className="friends-list__item">
                        <div className="friends-list__user">
                          {friend.user.avatar ? (
                            <img
                              src={friend.user.avatar}
                              alt={friend.user.username}
                              className="friends-list__avatar"
                            />
                          ) : (
                            <div className="friends-list__avatar-placeholder">
                              {friend.user.username[0].toUpperCase()}
                            </div>
                          )}
                          <div className="friends-list__info">
                            <div className="friends-list__username">
                              {friend.user.username}
                            </div>
                            <OnlineStatus
                              isOnline={friend.isOnline}
                              lastSeen={friend.lastSeen}
                              showText
                            />
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveFriend(friend.id)}
                        >
                          Удалить
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {activeTab === 'requests' && (
        <div className="friends-list__content">
          {requestsLoading ? (
            <div className="friends-list__loading">Загрузка...</div>
          ) : !requestsData?.friendRequests || requestsData.friendRequests.length === 0 ? (
            <div className="friends-list__empty">Нет входящих запросов</div>
          ) : (
            <div className="friends-list__requests">
              {requestsData.friendRequests.map((request: any) => (
                <FriendRequest
                  key={request.id}
                  id={request.id}
                  user={request.user}
                  onAccept={handleAccept}
                  onDecline={handleDecline}
                  isLoading={loadingActions.has(request.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};