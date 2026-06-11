import React, { useState } from 'react';
import { useQuery, useLazyQuery, gql } from '@apollo/client';
import { useParams } from 'react-router-dom';
import { useUser } from '@/store/authStore';
import { ProfileHeader } from './ProfileHeader';
import { ProfileStats } from './ProfileStats';
import { MatchHistory } from './MatchHistory';
import { RatingChart } from './RatingChart';
import { EditProfileModal } from './EditProfileModal';
import { Achievements } from './Achievements';
import './ProfileView.css';

const PROFILE_FRAGMENT = gql`
  fragment ProfileFragment on Profile {
    user {
      id
      username
      avatar
      country
      bio
      createdAt
    }
    stats {
      gamesPlayed
      wins
      losses
      winRate
      currentStreak
      bestStreak
      favoriteHero {
        id
        name
        thumbnailUrl
      }
    }
    rating {
      current
      peak
      rank
    }
  }
`;

const GET_PROFILE = gql`
  ${PROFILE_FRAGMENT}
  query GetProfile($userId: ID!) {
    profile(userId: $userId) {
      ...ProfileFragment
    }
  }
`;

const GET_MATCH_HISTORY = gql`
  query GetMatchHistory($userId: ID!, $options: HistoryOptions!) {
    matchHistory(userId: $userId, options: $options) {
      games {
        id
        mode
        result
        heroes {
          id
          name
          thumbnailUrl
        }
        playedAt
        ratingChange
      }
      totalCount
    }
  }
`;

const GET_RATING_HISTORY = gql`
  query GetRatingHistory($userId: ID!, $period: Period!) {
    ratingHistory(userId: $userId, period: $period) {
      date
      rating
      gameId
    }
  }
`;

interface ProfileViewProps {
  isOwnProfile?: boolean;
}

export const ProfileView: React.FC<ProfileViewProps> = ({ isOwnProfile: isOwnProfileProp }) => {
  const { userId } = useParams<{ userId: string }>();
  const currentUser = useUser();

  const isOwnProfile = isOwnProfileProp || userId === currentUser?.id;

  const [showEditModal, setShowEditModal] = useState(false);
  const [ratingPeriod, _setRatingPeriod] = useState<'week' | 'month' | 'all'>('all');

  const { data: profileData, loading: profileLoading, refetch: refetchProfile } = useQuery(
    GET_PROFILE,
    {
      variables: { userId: userId || currentUser?.id || '' },
      skip: !userId && !currentUser?.id,
      fetchPolicy: 'network-only',
    },
  );

  const [getMatchHistory, { data: matchHistoryData, loading: matchHistoryLoading }] =
    useLazyQuery(GET_MATCH_HISTORY, {
      variables: {
        userId: userId || currentUser?.id || '',
        options: {
          limit: 20,
          offset: 0,
        },
      },
      fetchPolicy: 'network-only',
    });

  const [getRatingHistory, { data: ratingHistoryData }] = useLazyQuery(GET_RATING_HISTORY, {
    variables: {
      userId: userId || currentUser?.id || '',
      period: ratingPeriod,
    },
    fetchPolicy: 'network-only',
  });

  React.useEffect(() => {
    if (userId || currentUser?.id) {
      getMatchHistory();
      getRatingHistory();
    }
  }, [userId, currentUser?.id, ratingPeriod]);

  const handleEdit = () => {
    setShowEditModal(true);
  };

  const handleAddFriend = () => {
    console.log('Add friend functionality will be implemented');
  };

  const handleEditSuccess = () => {
    refetchProfile();
  };

  const handleGameClick = (gameId: string) => {
    console.log('Navigate to game replay:', gameId);
  };

  const handleLoadMoreMatches = () => {
    console.log('Load more matches');
  };

  if (profileLoading) {
    return (
      <div className="profile-view profile-view--loading">
        <div className="profile-view__loading-spinner" />
        <p>Загрузка профиля...</p>
      </div>
    );
  }

  const profile = profileData?.profile;

  if (!profile) {
    return (
      <div className="profile-view profile-view--error">
        <p>Профиль не найден</p>
      </div>
    );
  }

  return (
    <div className="profile-view">
      <ProfileHeader
        username={profile.user.username}
        avatar={profile.user.avatar || undefined}
        country={profile.user.country || undefined}
        rating={profile.rating.current}
        rank={profile.rating.rank}
        bio={profile.user.bio || undefined}
        isOwnProfile={isOwnProfile}
        onEdit={handleEdit}
        onAddFriend={handleAddFriend}
      />

      <div className="profile-view__grid">
        <div className="profile-view__main">
          <ProfileStats
            gamesPlayed={profile.stats.gamesPlayed}
            wins={profile.stats.wins}
            losses={profile.stats.losses}
            winRate={profile.stats.winRate}
            currentStreak={profile.stats.currentStreak}
            bestStreak={profile.stats.bestStreak}
            peakRating={profile.rating.peak}
            favoriteHero={profile.stats.favoriteHero || undefined}
          />

          <MatchHistory
            games={matchHistoryData?.matchHistory?.games || []}
            onLoadMore={handleLoadMoreMatches}
            onGameClick={handleGameClick}
            hasMore={false}
            isLoading={matchHistoryLoading}
          />
        </div>

        <div className="profile-view__sidebar">
          <RatingChart
            data={ratingHistoryData?.ratingHistory || []}
            period={ratingPeriod}
            peakRating={profile.rating.peak}
          />

          <Achievements userId={userId || currentUser?.id || ''} />
        </div>
      </div>

      {showEditModal && (
        <EditProfileModal
          isOpen={showEditModal}
          onClose={() => setShowEditModal(false)}
          currentProfile={{
            username: profile.user.username,
            avatar: profile.user.avatar || undefined,
            country: profile.user.country || undefined,
            bio: profile.user.bio || undefined,
          }}
          onSuccess={handleEditSuccess}
        />
      )}
    </div>
  );
};