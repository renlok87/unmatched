import React, { useState, useEffect, useRef } from 'react';
import { useLazyQuery, useMutation, useSubscription, gql } from '@apollo/client';
import { ChatMessage, type ChatMessageType } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { EmotePicker } from './EmotePicker';
import { EmoteReaction } from './EmoteReaction';
import { useUser } from '@/store/authStore';
import { chatModeration } from '@/utils/chatModeration';
import './GameChat.css';

const CHAT_MESSAGES = gql`
  fragment ChatMessageFragment on ChatMessage {
    id
    type
    content
    user {
      id
      username
      avatar
    }
    timestamp
  }
`;

const GET_CHAT_MESSAGES = gql`
  ${CHAT_MESSAGES}
  query GetChatMessages($gameId: ID!, $limit: Int) {
    chatMessages(gameId: $gameId, limit: $limit) {
      ...ChatMessageFragment
    }
  }
`;

const SEND_CHAT_MESSAGE = gql`
  ${CHAT_MESSAGES}
  mutation SendChatMessage($gameId: ID!, $content: String!) {
    sendChatMessage(gameId: $gameId, content: $content) {
      ...ChatMessageFragment
    }
  }
`;

const CHAT_UPDATES = gql`
  ${CHAT_MESSAGES}
  subscription ChatUpdates($gameId: ID!) {
    chatUpdates(gameId: $gameId) {
      ...ChatMessageFragment
    }
  }
`;

interface GameChatProps {
  gameId: string;
  collapsible?: boolean;
}

export const GameChat: React.FC<GameChatProps> = ({ gameId, collapsible = true }) => {
  const user = useUser();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [showEmotePicker, setShowEmotePicker] = useState(false);
  const [activeEmotes, setActiveEmotes] = useState<Array<{ id: string; emote: string; playerId: string }>>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [getMessages, { data: messagesData, loading: messagesLoading }] = useLazyQuery(
    GET_CHAT_MESSAGES,
    {
      variables: { gameId, limit: 50 },
      fetchPolicy: 'network-only',
    },
  );

  const [sendMessage] = useMutation(SEND_CHAT_MESSAGE, {
    optimisticResponse: (vars) => ({
      sendChatMessage: {
        id: `temp-${Date.now()}`,
        type: 'user' as ChatMessageType,
        content: vars.content,
        user: {
          id: user?.id || '',
          username: user?.username || 'Вы',
          avatar: user?.avatar,
        },
        timestamp: new Date().toISOString(),
        __typename: 'ChatMessage',
      },
    }),
    update: (cache, { data }) => {
      if (data?.sendChatMessage) {
        const existing = cache.readQuery({
          query: GET_CHAT_MESSAGES,
          variables: { gameId, limit: 50 },
        }) as { chatMessages: typeof data.sendChatMessage[] } | null;

        cache.writeQuery({
          query: GET_CHAT_MESSAGES,
          variables: { gameId, limit: 50 },
          data: {
            chatMessages: [...(existing?.chatMessages || []), data.sendChatMessage],
          },
        });
      }
    },
  });

  const { data: subscriptionData } = useSubscription(CHAT_UPDATES, {
    variables: { gameId },
    skip: !gameId,
  });

  useEffect(() => {
    if (gameId) {
      getMessages();
    }
  }, [gameId, getMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messagesData, subscriptionData]);

  const handleSend = (message: string) => {
    if (message.trim()) {
      const validation = chatModeration.validateMessage(user?.id || '', message.trim());

      if (!validation.isValid) {
        alert(validation.reason);
        return;
      }

      const { content, wasFiltered } = chatModeration.recordMessage(user?.id || '', message.trim());

      sendMessage({ variables: { gameId, content } });

      if (wasFiltered) {
        alert('Ваше сообщение было отфильтровано');
      }

      if (content.match(/^[😂😮🤔😊😄😍👍👎]$/)) {
        showEmoteOnScreen(content);
      }
    }
  };

  const showEmoteOnScreen = (emote: string) => {
    const id = `emote-${Date.now()}`;
    setActiveEmotes((prev) => [...prev, { id, emote, playerId: user?.id || '' }]);

    setTimeout(() => {
      setActiveEmotes((prev) => prev.filter((e) => e.id !== id));
    }, 2000);
  };

  const messages = messagesData?.chatMessages || [];
  const newMessage = subscriptionData?.chatUpdates;

  const filteredMessages = messages.filter((msg: any) => {
    if (msg.user?.id) {
      return !chatModeration.isUserIgnored(msg.user.id);
    }
    return true;
  });

  const allMessages = newMessage && !chatModeration.isUserIgnored(newMessage.user?.id || '')
    ? [...filteredMessages, newMessage]
    : filteredMessages;

  if (collapsible && isCollapsed) {
    return (
      <button
        type="button"
        className="game-chat__toggle game-chat__toggle--collapsed"
        onClick={() => setIsCollapsed(false)}
        aria-label="Открыть чат"
      >
        💬
      </button>
    );
  }

  return (
    <div className="game-chat">
      {activeEmotes.map((emote) => (
        <EmoteReaction
          key={emote.id}
          emote={emote.emote}
          playerId={emote.playerId}
          onComplete={() => {}}
        />
      ))}

      <div className="game-chat__header">
        <h3 className="game-chat__title">Чат</h3>
        {collapsible && (
          <button
            type="button"
            className="game-chat__toggle"
            onClick={() => setIsCollapsed(true)}
            aria-label="Свернуть чат"
          >
            ✕
          </button>
        )}
      </div>

      <div className="game-chat__messages">
        {messagesLoading ? (
          <div className="game-chat__loading">Загрузка сообщений...</div>
        ) : allMessages.length === 0 ? (
          <div className="game-chat__empty">Нет сообщений</div>
        ) : (
          allMessages.map((message: any) => (
            <ChatMessage
              key={message.id}
              message={message}
              isOwn={message.user?.id === user?.id}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="game-chat__input">
        <ChatInput
          onSend={handleSend}
          onEmoteClick={() => setShowEmotePicker(true)}
          disabled={messagesLoading}
        />
      </div>

      {showEmotePicker && (
        <EmotePicker
          onSelect={(phrase) => handleSend(phrase)}
          onClose={() => setShowEmotePicker(false)}
        />
      )}
    </div>
  );
};