import React from 'react';
import './ProfileStats.css';

export interface ProfileStatsProps {
  gamesPlayed: number;
  wins: number;
  losses: number;
  winRate: number;
  currentStreak: number;
  bestStreak: number;
  peakRating: number;
  favoriteHero?: {
    id: string;
    name: string;
    thumbnailUrl?: string;
  };
}

interface StatItem {
  label: string;
  value: string | number;
  icon: string;
  progress?: number;
  highlight?: 'positive' | 'negative';
  hero?: {
    id: string;
    name: string;
    thumbnailUrl?: string;
  };
}

export const ProfileStats: React.FC<ProfileStatsProps> = ({
  gamesPlayed,
  wins,
  losses,
  winRate,
  currentStreak,
  bestStreak,
  peakRating,
  favoriteHero,
}) => {
  const stats: StatItem[] = [
    {
      label: 'Игры сыграно',
      value: gamesPlayed,
      icon: '🎮',
    },
    {
      label: 'Win Rate',
      value: `${winRate}%`,
      icon: '📊',
      progress: winRate,
    },
    {
      label: 'Текущая серия',
      value: currentStreak > 0 ? `+${currentStreak}` : currentStreak,
      icon: currentStreak > 0 ? '🔥' : currentStreak < 0 ? '❄️' : '➖',
      highlight: currentStreak > 0 ? 'positive' : currentStreak < 0 ? 'negative' : undefined,
    },
    {
      label: 'Победы',
      value: wins,
      icon: '🏆',
    },
    {
      label: 'Поражения',
      value: losses,
      icon: '💔',
    },
    {
      label: 'Лучшая серия',
      value: bestStreak,
      icon: '⭐',
      highlight: 'positive',
    },
    {
      label: 'Пиковый рейтинг',
      value: peakRating,
      icon: '🎯',
      highlight: 'positive',
    },
  ];

  if (favoriteHero) {
    stats.push({
      label: 'Любимый герой',
      value: favoriteHero.name,
      icon: '🦸',
      hero: favoriteHero,
    });
  }

  return (
    <div className="profile-stats">
      <h2 className="profile-stats__title">Статистика</h2>
      <div className="profile-stats__grid">
        {stats.map((stat, index) => (
          <div
            key={index}
            className={`profile-stats__card ${
              stat.highlight ? `profile-stats__card--${stat.highlight}` : ''
            }`}
          >
            <div className="profile-stats__card-icon">{stat.icon}</div>
            <div className="profile-stats__card-content">
              <div className="profile-stats__card-value">{stat.value}</div>
              <div className="profile-stats__card-label">{stat.label}</div>
              {stat.progress !== undefined && (
                <div className="profile-stats__card-progress">
                  <div
                    className="profile-stats__card-progress-bar"
                    style={{ width: `${stat.progress}%` }}
                  />
                </div>
              )}
            </div>
            {stat.hero && (
              <div className="profile-stats__card-hero">
                {stat.hero.thumbnailUrl ? (
                  <img src={stat.hero.thumbnailUrl} alt={stat.hero.name} />
                ) : (
                  <div className="profile-stats__card-hero-placeholder">
                    {stat.hero.name[0]}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};