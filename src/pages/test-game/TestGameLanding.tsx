import React, { useState } from 'react';
import { useTestGameStore } from '@/store/testGameStore';
import './TestGamePage.css';

export const TestGameLanding: React.FC = () => {
  const { allHeroes, isLoading, initializeRandomGame } = useTestGameStore();
  const [isStarting, setIsStarting] = useState(false);

  const handleRandomStart = async () => {
    setIsStarting(true);
    try {
      await initializeRandomGame();
    } finally {
      setIsStarting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="test-game-page">
        <div className="landing-container">
          <div className="loading-spinner"></div>
          <p className="loading-text">Загрузка данных о героях...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="test-game-page">
      <div className="landing-container">
        <div className="landing-content">
          <h1 className="landing-title">🎮 Тестовая игра Unmatched</h1>
          <p className="landing-subtitle">
            Нажмите кнопку для начала игры со случайными героями
          </p>

          <div className="start-actions-centered">
            <button
              onClick={handleRandomStart}
              disabled={isStarting || allHeroes.length < 2}
              className="btn btn-primary btn-lg"
            >
              {isStarting ? 'Загрузка...' : '🎲 Случайные герои'}
            </button>

            {allHeroes.length < 2 && (
              <p className="error-text">
                Недостаточно героев для начала игры (нужно минимум 2)
              </p>
            )}
          </div>

          <div className="hero-list-full">
            <h2 className="selection-title">Доступные герои: {allHeroes.length}</h2>
            <div className="heroes-grid">
              {allHeroes.map((hero) => (
                <div key={hero.id} className="hero-card">
                  <div className="hero-avatar">
                    {hero.name?.[0] || '?'}
                  </div>
                  <div className="hero-info">
                    <h3 className="hero-name">{hero.name}</h3>
                    <div className="hero-stats">
                      <span>❤️ {hero.health}</span>
                      <span>👟 {hero.movement}</span>
                      <span>📦 {hero.set}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
