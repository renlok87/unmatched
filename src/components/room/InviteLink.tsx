import React, { useState } from 'react';
import { Button } from '@/design-system/components/Button';

interface InviteLinkProps {
  gameCode: string | null;
}

export const InviteLink: React.FC<InviteLinkProps> = ({ gameCode }) => {
  const [copied, setCopied] = useState(false);

  const inviteUrl = gameCode
    ? `${window.location.origin}/join/${gameCode}`
    : window.location.href;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Присоединяйся к игре Unmatched!',
          text: 'Присоединяйся ко мне в игру Unmatched!',
          url: inviteUrl,
        });
      } catch (err) {
        console.error('Failed to share:', err);
      }
    }
  };

  return (
    <div className="invite-link">
      <h3 className="invite-link__title">Пригласить друзей</h3>
      {gameCode && (
        <div className="invite-link__code">
          <span className="invite-link__code-label">Код комнаты:</span>
          <span className="invite-link__code-value">{gameCode}</span>
        </div>
      )}
      <div className="invite-link__url">
        <input
          type="text"
          value={inviteUrl}
          readOnly
          className="invite-link__input"
        />
      </div>
      <div className="invite-link__actions">
        <Button
          variant="secondary"
          onClick={handleCopy}
          disabled={copied}
        >
          {copied ? 'Скопировано!' : 'Копировать ссылку'}
        </Button>
        {typeof navigator.share === 'function' && (
          <Button variant="ghost" onClick={handleShare}>
            Поделиться
          </Button>
        )}
      </div>
    </div>
  );
};

export default InviteLink;