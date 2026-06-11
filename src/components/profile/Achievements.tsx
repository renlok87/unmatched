import React from 'react';
import { useQuery, gql } from '@apollo/client';
import './Achievements.css';

const GET_ACHIEVEMENTS = gql`
  query GetAchievements($userId: ID!) {
    achievements(userId: $userId) {
      id
      name
      description
      icon
      category
      isHidden
      isUnlocked
      progress
      maxProgress
      unlockedAt
    }
  }
`;

interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  isHidden: boolean;
  isUnlocked: boolean;
  progress: number;
  maxProgress: number;
  unlockedAt?: string;
}

interface AchievementsProps {
  userId: string;
}

export const Achievements: React.FC<AchievementsProps> = ({ userId }) => {
  const { data, loading, error } = useQuery(GET_ACHIEVEMENTS, {
    variables: { userId },
  });

  if (loading) {
    return (
      <div className="achievements achievements--loading">
        <div className="achievements__loading-text">Загрузка достижений...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="achievements achievements--error">
        <div className="achievements__error-text">
          Ошибка загрузки достижений
        </div>
      </div>
    );
  }

  const achievements: Achievement[] = data?.achievements || [];
  const unlockedCount = achievements.filter((a) => a.isUnlocked).length;
  const totalCount = achievements.length;

  const categories = Array.from(
    new Set(achievements.map((a) => a.category))
  ).filter(Boolean);

  return (
    <div className="achievements">
      <div className="achievements__header">
        <h2 className="achievements__title">Достижения</h2>
        <div className="achievements__summary">
          <span className="achievements__count">
            {unlockedCount} / {totalCount}
          </span>
          <span className="achievements__percentage">
            {totalCount > 0 ? Math.round((unlockedCount / totalCount) * 100) : 0}%
          </span>
        </div>
      </div>

      <div className="achievements__progress-bar">
        <div
          className="achievements__progress-fill"
          style={{
            width: `${totalCount > 0 ? (unlockedCount / totalCount) * 100 : 0}%`,
          }}
        />
      </div>

      {categories.length > 0 ? (
        categories.map((category) => {
          const categoryAchievements = achievements.filter(
            (a) => a.category === category
          );

          return (
            <div key={category} className="achievements__category">
              <h3 className="achievements__category-title">{category}</h3>
              <div className="achievements__grid">
                {categoryAchievements.map((achievement) => (
                  <AchievementCard key={achievement.id} achievement={achievement} />
                ))}
              </div>
            </div>
          );
        })
      ) : (
        <div className="achievements__grid">
          {achievements.map((achievement) => (
            <AchievementCard key={achievement.id} achievement={achievement} />
          ))}
        </div>
      )}

      {achievements.length === 0 && (
        <div className="achievements__empty">
          <div className="achievements__empty-icon">🏆</div>
          <div className="achievements__empty-text">
            У вас пока нет достижений
          </div>
        </div>
      )}
    </div>
  );
};

interface AchievementCardProps {
  achievement: Achievement;
}

const AchievementCard: React.FC<AchievementCardProps> = ({ achievement }) => {
  const progressPercentage =
    achievement.maxProgress > 0
      ? (achievement.progress / achievement.maxProgress) * 100
      : achievement.isUnlocked
      ? 100
      : 0;

  return (
    <div
      className={`achievement-card ${
        achievement.isUnlocked ? 'achievement-card--unlocked' : ''
      } ${achievement.isHidden ? 'achievement-card--hidden' : ''}`}
    >
      <div className="achievement-card__icon">
        {achievement.isHidden && !achievement.isUnlocked ? (
          <span className="achievement-card__hidden-icon">❓</span>
        ) : (
          <span className="achievement-card__emoji">{achievement.icon}</span>
        )}
      </div>

      <div className="achievement-card__content">
        <h4 className="achievement-card__name">
          {achievement.isHidden && !achievement.isUnlocked
            ? '???'
            : achievement.name}
        </h4>
        <p className="achievement-card__description">
          {achievement.isHidden && !achievement.isUnlocked
            ? 'Секретное достижение'
            : achievement.description}
        </p>

        {achievement.maxProgress > 0 && (
          <div className="achievement-card__progress">
            <div className="achievement-card__progress-bar">
              <div
                className="achievement-card__progress-fill"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
            <span className="achievement-card__progress-text">
              {achievement.progress} / {achievement.maxProgress}
            </span>
          </div>
        )}

        {achievement.unlockedAt && (
          <div className="achievement-card__unlocked-date">
            {new Date(achievement.unlockedAt).toLocaleDateString('ru-RU', {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
          </div>
        )}
      </div>

      {achievement.isUnlocked && (
        <div className="achievement-card__status achievement-card__status--unlocked">
          ✓
        </div>
      )}
    </div>
  );
};