import React from 'react';
import './EmotePicker.css';

interface QuickPhrase {
  id: string;
  text: string;
}

const QUICK_PHRASES: Record<string, QuickPhrase[]> = {
  greetings: [
    { id: 'gg', text: 'Good game!' },
    { id: 'hf', text: 'Have fun!' },
    { id: 'gl', text: 'Good luck!' },
  ],
  combat: [
    { id: 'wp', text: 'Well played!' },
    { id: 'nic', text: 'Nice attack!' },
    { id: 'oops', text: 'My mistake!' },
  ],
  fun: [
    { id: 'lol', text: '😂' },
    { id: 'wow', text: '😮' },
    { id: 'think', text: '🤔' },
  ],
};

const CATEGORY_LABELS: Record<string, string> = {
  greetings: 'Приветствия',
  combat: 'Бой',
  fun: 'Эмодзи',
};

interface EmotePickerProps {
  onSelect: (phrase: string) => void;
  onClose: () => void;
}

export const EmotePicker: React.FC<EmotePickerProps> = ({ onSelect, onClose }) => {
  const categories = Object.keys(QUICK_PHRASES) as Array<keyof typeof QUICK_PHRASES>;

  return (
    <div className="emote-picker-overlay" onClick={onClose}>
      <div className="emote-picker" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="emote-picker__close"
          onClick={onClose}
          aria-label="Закрыть"
        >
          ✕
        </button>

        <h3 className="emote-picker__title">Быстрые фразы</h3>

        <div className="emote-picker__content">
          {categories.map((category) => (
            <div key={category} className="emote-picker__category">
              <div className="emote-picker__category-title">
                {CATEGORY_LABELS[category]}
              </div>
              <div className="emote-picker__phrases">
                {QUICK_PHRASES[category].map((phrase) => (
                  <button
                    key={phrase.id}
                    type="button"
                    className="emote-picker__phrase"
                    onClick={() => {
                      onSelect(phrase.text);
                      onClose();
                    }}
                  >
                    {phrase.text}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};