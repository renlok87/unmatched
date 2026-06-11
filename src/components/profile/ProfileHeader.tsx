import React from 'react';
import { Button } from '@/design-system/components/Button';
import './ProfileHeader.css';

export interface ProfileHeaderProps {
  username: string;
  avatar?: string;
  country?: string;
  rating: number;
  rank: number;
  bio?: string;
  isOwnProfile: boolean;
  onEdit?: () => void;
  onAddFriend?: () => void;
  isFriend?: boolean;
}

export const ProfileHeader: React.FC<ProfileHeaderProps> = ({
  username,
  avatar,
  country,
  rating,
  rank,
  bio,
  isOwnProfile,
  onEdit,
  onAddFriend,
  isFriend = false,
}) => {
  const getCountryFlag = (country?: string) => {
    const flags: Record<string, string> = {
      ru: '🇷🇺',
      us: '🇺🇸',
      gb: '🇬🇧',
      de: '🇩🇪',
      fr: '🇫🇷',
      es: '🇪🇸',
      it: '🇮🇹',
      jp: '🇯🇵',
      cn: '🇨🇳',
      br: '🇧🇷',
    };
    return country ? flags[country.toLowerCase()] || '' : '';
  };

  return (
    <div className="profile-header">
      <div className="profile-header__avatar-section">
        {avatar ? (
          <img src={avatar} alt={username} className="profile-header__avatar" />
        ) : (
          <div className="profile-header__avatar-placeholder">
            {username[0].toUpperCase()}
          </div>
        )}
        <div className="profile-header__rank-badge">#{rank}</div>
      </div>

      <div className="profile-header__info">
        <div className="profile-header__name-section">
          <h1 className="profile-header__username">
            {username}
            {getCountryFlag(country) && (
              <span className="profile-header__country">
                {getCountryFlag(country)}
              </span>
            )}
          </h1>
          {isOwnProfile && (
            <Button variant="secondary" size="sm" onClick={onEdit}>
              Редактировать
            </Button>
          )}
          {!isOwnProfile && !isFriend && (
            <Button variant="primary" size="sm" onClick={onAddFriend}>
              Добавить в друзья
            </Button>
          )}
          {!isOwnProfile && isFriend && (
            <Button variant="ghost" size="sm" disabled>
              ✓ В друзьях
            </Button>
          )}
        </div>

        <div className="profile-header__rating-section">
          <div className="profile-header__rating-value">{rating}</div>
          <div className="profile-header__rating-label">ELO рейтинг</div>
        </div>

        {bio && <p className="profile-header__bio">{bio}</p>}
      </div>
    </div>
  );
};