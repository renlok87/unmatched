import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/design-system/components/Button';
import { Input } from '@/design-system/components/Input';

export interface ChatMessage {
  id: string;
  userId: string;
  username: string;
  message: string;
  timestamp: Date;
  isSystem?: boolean;
}

interface RoomChatProps {
  gameId?: string;
}

export const RoomChat: React.FC<RoomChatProps> = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();

    if (!input.trim()) return;

    const newMessage: ChatMessage = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      userId: localStorage.getItem('userId') || '',
      username: localStorage.getItem('username') || 'Игрок',
      message: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newMessage]);
    setInput('');
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="room-chat">
      <h3 className="room-chat__title">Чат комнаты</h3>
      <div className="room-chat__messages">
        {messages.length === 0 ? (
          <div className="room-chat__empty">
            <span className="room-chat__empty-icon">💬</span>
            <span className="room-chat__empty-text">Нет сообщений</span>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`room-chat__message ${
                msg.isSystem ? 'room-chat__message--system' : ''
              }`}
            >
              {msg.isSystem ? (
                <span className="room-chat__system-text">{msg.message}</span>
              ) : (
                <>
                  <span className="room-chat__message-time">
                    {formatTime(msg.timestamp)}
                  </span>
                  <span className="room-chat__message-author">
                    {msg.username}
                  </span>
                  <span className="room-chat__message-text">
                    {msg.message}
                  </span>
                </>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSendMessage} className="room-chat__input">
        <Input
          type="text"
          placeholder="Введите сообщение..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <Button type="submit" variant="primary">
          Отправить
        </Button>
      </form>
    </div>
  );
};

export default RoomChat;