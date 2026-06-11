import React, { useState } from 'react';
import { chatModeration } from '@/utils/chatModeration';
import { useUser } from '@/store/authStore';
import './ChatMessage.css';

export type ChatMessageType = 'user' | 'system' | 'emote' | 'combat' | 'game';

export interface ChatMessage {
  id: string;
  type: ChatMessageType;
  content: string;
  user?: {
    id: string;
    username: string;
    avatar?: string;
  };
  timestamp: string;
}

interface ChatMessageProps {
  message: ChatMessage;
  isOwn: boolean;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, isOwn }) => {
  const [showReportMenu, setShowReportMenu] = useState(false);
  const currentUser = useUser();
  const time = new Date(message.timestamp).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  });

  const handleReport = (reason: string) => {
    if (message.user) {
      chatModeration.reportMessage(message.id, currentUser?.id || '', reason);
      alert('Сообщение отправлено на модерацию');
      setShowReportMenu(false);
    }
  };

  const handleIgnore = () => {
    if (message.user && confirm(`Вы уверены, что хотите скрыть сообщения от ${message.user.username}?`)) {
      chatModeration.ignoreUser(message.user.id);
      alert('Сообщения от этого игрока скрыты');
      setShowReportMenu(false);
    }
  };

  return (
    <div
      className={`chat-message chat-message--${message.type} ${
        isOwn ? 'chat-message--own' : ''
      }`}
    >
      {message.type === 'user' && message.user && (
        <>
          <div className="chat-message__avatar">
            {message.user.avatar ? (
              <img src={message.user.avatar} alt={message.user.username} />
            ) : (
              <div className="chat-message__avatar-placeholder">
                {message.user.username[0].toUpperCase()}
              </div>
            )}
          </div>
          <div className="chat-message__content">
            <div className="chat-message__header">
              <span className="chat-message__username">{message.user.username}</span>
              <span className="chat-message__time">{time}</span>
              {!isOwn && (
                <button
                  className="chat-message__report-button"
                  onClick={() => setShowReportMenu(!showReportMenu)}
                  title="Пожаловаться"
                >
                  ⚠️
                </button>
              )}
            </div>
            <div className="chat-message__text">{message.content}</div>
            {showReportMenu && !isOwn && (
              <div className="chat-message__report-menu">
                <div className="chat-message__report-title">Причина жалобы:</div>
                <button onClick={() => handleReport('spam')}>Спам</button>
                <button onClick={() => handleReport('profanity')}>Ненормативная лексика</button>
                <button onClick={() => handleReport('harassment')}>Оскорбления</button>
                <button onClick={() => handleReport('other')}>Другое</button>
                <div className="chat-message__report-divider" />
                <button onClick={handleIgnore} className="chat-message__report-menu--ignore">
                  Скрыть сообщения от этого игрока
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {message.type === 'system' && (
        <div className="chat-message__system">
          <span className="chat-message__system-icon">ⓘ</span>
          <span className="chat-message__text">{message.content}</span>
          <span className="chat-message__time">{time}</span>
        </div>
      )}

      {message.type === 'emote' && (
        <div className="chat-message__emote">
          {message.user && (
            <span className="chat-message__username">{message.user.username}: </span>
          )}
          <span className="chat-message__text">{message.content}</span>
        </div>
      )}

      {message.type === 'combat' && (
        <div className="chat-message__combat">
          <span className="chat-message__combat-icon">⚔️</span>
          <span className="chat-message__text">{message.content}</span>
        </div>
      )}

      {message.type === 'game' && (
        <div className="chat-message__game">
          <span className="chat-message__game-icon">🎮</span>
          <span className="chat-message__text">{message.content}</span>
        </div>
      )}
    </div>
  );
};