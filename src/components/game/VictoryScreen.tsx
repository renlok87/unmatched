// ============================================================
// VICTORY SCREEN - Экран победы/поражения
// ============================================================

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { VictoryResult, type VictoryCheckResult } from '@/phaser/systems';
import './VictoryScreen.css';

// ------------------------------------------------------------
// Интерфейсы
// ------------------------------------------------------------

interface VictoryScreenProps {
  result: VictoryCheckResult | null;
  visible: boolean;
  playerName?: string;
  opponentName?: string;
  onPlayAgain?: () => void;
  onReturnToLobby?: () => void;
}

interface VictoryStats {
  turnsPlayed: number;
  damageDealt: number;
  damageTaken: number;
  fightersDefeated: number;
  cardsPlayed: number;
}

// ------------------------------------------------------------
// Компонент
// ------------------------------------------------------------

export const VictoryScreen: React.FC<VictoryScreenProps> = ({
  result,
  visible,
  opponentName = 'Opponent',
  onPlayAgain,
  onReturnToLobby,
}) => {
  const navigate = useNavigate();
  const [animationState, setAnimationState] = useState<'entering' | 'visible' | 'exiting'>('entering');
  const [showStats, setShowStats] = useState(false);
  const [stats] = useState<VictoryStats>({
    turnsPlayed: 0,
    damageDealt: 0,
    damageTaken: 0,
    fightersDefeated: 0,
    cardsPlayed: 0,
  });

  // Анимация появления
  useEffect(() => {
    if (visible) {
      setAnimationState('entering');
      setTimeout(() => setAnimationState('visible'), 50);
    } else {
      setAnimationState('exiting');
      setShowStats(false);
    }
  }, [visible]);

  // Показываем статистику с задержкой
  useEffect(() => {
    if (visible && animationState === 'visible') {
      const timer = setTimeout(() => setShowStats(true), 500);
      return () => clearTimeout(timer);
    }
  }, [visible, animationState]);

  // Обработчики кнопок
  const handlePlayAgain = () => {
    setAnimationState('exiting');
    setTimeout(() => {
      if (onPlayAgain) {
        onPlayAgain();
      } else {
        navigate('/matchmaking');
      }
    }, 300);
  };

  const handleReturnToLobby = () => {
    setAnimationState('exiting');
    setTimeout(() => {
      if (onReturnToLobby) {
        onReturnToLobby();
      } else {
        navigate('/lobby');
      }
    }, 300);
  };

  // Не рендерим, если не видно
  if (!visible || !result) {
    return null;
  }

  const isVictory = result.result === VictoryResult.VICTORY;
  const isDefeat = result.result === VictoryResult.DEFEAT;
  const isDraw = result.result === VictoryResult.DRAW;

  return (
    <div className={`victory-screen victory-screen--${result.result.toLowerCase()} victory-screen--${animationState}`}>
      {/* Фоновый эффект */}
      <div className="victory-screen__background">
        <div className={`victory-screen__gradient victory-screen__gradient--${result.result.toLowerCase()}`} />
        <div className="victory-screen__particles">
          {Array.from({ length: 20 }).map((_, i) => (
            <div
              key={i}
              className="victory-screen__particle"
              style={{
                left: `${Math.random() * 100}%`,
                animationDelay: `${Math.random() * 2}s`,
                animationDuration: `${2 + Math.random() * 3}s`,
              }}
            />
          ))}
        </div>
      </div>

      {/* Контент */}
      <div className="victory-screen__content">
        {/* Иконка результата */}
        <div className="victory-screen__icon">
          {isVictory && <VictoryIcon />}
          {isDefeat && <DefeatIcon />}
          {isDraw && <DrawIcon />}
        </div>

        {/* Заголовок */}
        <h1 className="victory-screen__title">
          {isVictory && 'VICTORY!'}
          {isDefeat && 'DEFEATED'}
          {isDraw && 'DRAW'}
        </h1>

        {/* Причина победы/поражения */}
        <p className="victory-screen__reason">
          {result.reason}
        </p>

        {/* Информация о победителе */}
        {result.winnerId && (
          <div className="victory-screen__winner">
            <span className="victory-screen__winner-label">
              {isVictory ? 'You' : opponentName}
            </span>
            <span className="victory-screen__winner-text"> won the battle!</span>
          </div>
        )}

        {/* Статистика игры */}
        {showStats && (
          <div className="victory-screen__stats">
            <div className="victory-screen__stat">
              <span className="victory-screen__stat-value">{stats.turnsPlayed}</span>
              <span className="victory-screen__stat-label">Turns</span>
            </div>
            <div className="victory-screen__stat">
              <span className="victory-screen__stat-value">{stats.damageDealt}</span>
              <span className="victory-screen__stat-label">Damage Dealt</span>
            </div>
            <div className="victory-screen__stat">
              <span className="victory-screen__stat-value">{stats.fightersDefeated}</span>
              <span className="victory-screen__stat-label">Fighters Defeated</span>
            </div>
            <div className="victory-screen__stat">
              <span className="victory-screen__stat-value">{stats.cardsPlayed}</span>
              <span className="victory-screen__stat-label">Cards Played</span>
            </div>
          </div>
        )}

        {/* Кнопки действий */}
        <div className="victory-screen__actions">
          <button
            className={`victory-screen__button victory-screen__button--primary ${
              isVictory ? 'victory-screen__button--victory' : ''
            }`}
            onClick={handlePlayAgain}
          >
            <span className="victory-screen__button-icon">↻</span>
            Play Again
          </button>
          <button
            className="victory-screen__button victory-screen__button--secondary"
            onClick={handleReturnToLobby}
          >
            <span className="victory-screen__button-icon">⌂</span>
            Return to Lobby
          </button>
        </div>

        {/* XP и бонусы (только для победы) */}
        {isVictory && (
          <div className="victory-screen__rewards">
            <div className="victory-screen__reward">
              <span className="victory-screen__reward-icon">⭐</span>
              <span className="victory-screen__reward-text">+{calculateXP(stats)} XP</span>
            </div>
            <div className="victory-screen__reward">
              <span className="victory-screen__reward-icon">🏆</span>
              <span className="victory-screen__reward-text">Rank Points</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ------------------------------------------------------------
// Иконки результатов
// ------------------------------------------------------------

const VictoryIcon: React.FC = () => (
  <svg className="victory-screen__svg" viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="45" fill="#4ecca3" opacity="0.2" />
    <path
      d="M50 20 L60 40 L80 40 L65 55 L70 75 L50 62 L30 75 L35 55 L20 40 L40 40 Z"
      fill="#4ecca3"
      stroke="#fff"
      strokeWidth="2"
    />
  </svg>
);

const DefeatIcon: React.FC = () => (
  <svg className="victory-screen__svg" viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="45" fill="#ff6b6b" opacity="0.2" />
    <path
      d="M35 35 L65 65 M65 35 L35 65"
      stroke="#ff6b6b"
      strokeWidth="8"
      strokeLinecap="round"
    />
  </svg>
);

const DrawIcon: React.FC = () => (
  <svg className="victory-screen__svg" viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="45" fill="#ffd93d" opacity="0.2" />
    <path
      d="M50 25 L50 75 M25 50 L75 50"
      stroke="#ffd93d"
      strokeWidth="8"
      strokeLinecap="round"
    />
  </svg>
);

// ------------------------------------------------------------
// Утилиты
// ------------------------------------------------------------

function calculateXP(stats: VictoryStats): number {
  // Базовый XP за победу
  let xp = 100;

  // Бонусы за статистику
  xp += stats.turnsPlayed * 5;
  xp += stats.damageDealt * 2;
  xp += stats.fightersDefeated * 25;
  xp += stats.cardsPlayed * 3;

  return xp;
}

// ------------------------------------------------------------
// Hook для использования экрана победы
// ------------------------------------------------------------

export function useVictoryScreen() {
  const [result, setResult] = useState<VictoryCheckResult | null>(null);
  const [visible, setVisible] = useState(false);

  const show = (checkResult: VictoryCheckResult) => {
    setResult(checkResult);
    setVisible(true);
  };

  const hide = () => {
    setVisible(false);
    setTimeout(() => setResult(null), 300);
  };

  return {
    result,
    visible,
    show,
    hide,
  };
}

export default VictoryScreen;
