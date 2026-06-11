import React from 'react';
import './TargetSelector.css';

export interface Position {
  x: number;
  y: number;
}

export interface Fighter {
  id: string;
  name: string;
  type: 'hero' | 'sidekick';
  health: number;
  maxHealth: number;
  position: Position;
}

interface TargetSelectorProps {
  targets: Fighter[];
  selectedTargetId: string | null;
  onTargetSelect: (targetId: string) => void;
  onClose: () => void;
}

export const TargetSelector: React.FC<TargetSelectorProps> = ({
  targets,
  selectedTargetId,
  onTargetSelect,
  onClose,
}) => {
  const handleTargetClick = (targetId: string) => {
    onTargetSelect(targetId);
  };

  return (
    <div className="target-selector">
      <div className="target-selector__overlay" onClick={onClose} />
      <div className="target-selector__content">
        <h3 className="target-selector__title">Выберите цель</h3>
        <div className="target-selector__list">
          {targets.map((target) => (
            <button
              key={target.id}
              className={`target-selector__item ${
                selectedTargetId === target.id
                  ? 'target-selector__item--selected'
                  : ''
              }`}
              onClick={() => handleTargetClick(target.id)}
            >
              <div className="target-selector__item-type">
                {target.type === 'hero' ? '🦸' : '🦸‍♂️'}
              </div>
              <div className="target-selector__item-info">
                <div className="target-selector__item-name">
                  {target.name}
                </div>
                <div className="target-selector__item-health">
                  ❤️ {target.health}/{target.maxHealth}
                </div>
              </div>
              {selectedTargetId === target.id && (
                <div className="target-selector__item-check">✓</div>
              )}
            </button>
          ))}
        </div>
        <div className="target-selector__actions">
          <button
            className="target-selector__cancel"
            onClick={onClose}
          >
            Отмена
          </button>
          <button
            className="target-selector__confirm"
            onClick={() => {
              if (selectedTargetId) {
                onClose();
              }
            }}
            disabled={!selectedTargetId}
          >
            Подтвердить
          </button>
        </div>
      </div>
    </div>
  );
};

export default TargetSelector;