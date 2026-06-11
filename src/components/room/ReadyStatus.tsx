import React from 'react';
import { Button } from '@/design-system/components/Button';

interface ReadyStatusProps {
  isReady: boolean;
  onToggle: () => void;
  disabled?: boolean;
  allReady: boolean;
}

export const ReadyStatus: React.FC<ReadyStatusProps> = ({
  isReady,
  onToggle,
  disabled = false,
  allReady,
}) => {
  return (
    <div className="ready-status">
      {allReady && (
        <div className="ready-status__all-ready">
          <span className="ready-status__all-ready-icon">✓</span>
          <span className="ready-status__all-ready-text">Все готовы!</span>
        </div>
      )}
      <Button
        variant={isReady ? 'success' : 'primary'}
        onClick={onToggle}
        disabled={disabled}
        loading={disabled}
      >
        {isReady ? 'Я готов' : 'Не готов'}
      </Button>
    </div>
  );
};

export default ReadyStatus;