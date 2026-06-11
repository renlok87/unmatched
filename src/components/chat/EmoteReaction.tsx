import React, { useEffect } from 'react';
import './EmoteReaction.css';

interface EmoteReactionProps {
  emote: string;
  playerId: string;
  onComplete: () => void;
}

export const EmoteReaction: React.FC<EmoteReactionProps> = ({ emote, playerId, onComplete }) => {
  useEffect(() => {
    const timer = setTimeout(onComplete, 2000);
    return () => clearTimeout(timer);
  }, [onComplete]);

  const randomX = Math.random() * 200 - 100;
  const randomDelay = Math.random() * 0.5;

  return (
    <div
      className="emote-reaction"
      data-player-id={playerId}
      style={{
        '--random-x': `${randomX}px`,
        '--random-delay': `${randomDelay}s`,
      } as React.CSSProperties}
      aria-label={`Эмоция: ${emote}`}
    >
      <span className="emote-reaction__content">{emote}</span>
    </div>
  );
};