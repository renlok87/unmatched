import React, { useState } from 'react';
import { useLazyQuery, gql } from '@apollo/client';
import { useNavigate } from 'react-router-dom';
import { LeaderboardTabs, type LeaderboardTab } from './LeaderboardTabs';
import { LeaderboardTable } from './LeaderboardTable';
import { Input } from '@/design-system/components/Input';
import './LeaderboardView.css';

const LEADERBOARD_FRAGMENT = gql`
  fragment LeaderboardEntryFragment on LeaderboardEntry {
    rank
    user {
      id
      username
      avatar
      country
    }
    rating
    gamesPlayed
    wins
    winRate
    streak
  }
`;

const GET_LEADERBOARD = gql`
  ${LEADERBOARD_FRAGMENT}
  query GetLeaderboard($options: LeaderboardOptions!) {
    leaderboard(options: $options) {
      players {
        ...LeaderboardEntryFragment
      }
      totalCount
      yourRank {
        rank
        rating
      }
    }
  }
`;

const GET_FRIENDS_LEADERBOARD = gql`
  ${LEADERBOARD_FRAGMENT}
  query GetFriendsLeaderboard($options: LeaderboardOptions!) {
    friendsLeaderboard(options: $options) {
      players {
        ...LeaderboardEntryFragment
      }
      totalCount
      yourRank {
        rank
        rating
      }
    }
  }
`;

interface LeaderboardViewProps {
  defaultTab?: LeaderboardTab;
}

export const LeaderboardView: React.FC<LeaderboardViewProps> = ({ defaultTab = 'global' }) => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<LeaderboardTab>(defaultTab);
  const [searchQuery, setSearchQuery] = useState('');
  const [gameMode, setGameMode] = useState<string>('all');

  const [getLeaderboard, { data: globalData, loading: globalLoading }] =
    useLazyQuery(GET_LEADERBOARD, {
      variables: {
        options: {
          mode: gameMode === 'all' ? undefined : gameMode,
          period: activeTab === 'weekly' ? 'weekly' : 'all',
          limit: 50,
          offset: 0,
          search: searchQuery || undefined,
        },
      },
      fetchPolicy: 'network-only',
    });

  const [getFriendsLeaderboard, { data: friendsData, loading: friendsLoading }] =
    useLazyQuery(GET_FRIENDS_LEADERBOARD, {
      variables: {
        options: {
          mode: gameMode === 'all' ? undefined : gameMode,
          period: activeTab === 'weekly' ? 'weekly' : 'all',
          limit: 50,
          offset: 0,
          search: searchQuery || undefined,
        },
      },
      fetchPolicy: 'network-only',
    });

  React.useEffect(() => {
    if (activeTab === 'friends') {
      getFriendsLeaderboard();
    } else {
      getLeaderboard();
    }
  }, [activeTab, gameMode, searchQuery]);

  const handleTabChange = (tab: LeaderboardTab) => {
    setActiveTab(tab);
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
  };

  const handlePlayerClick = (playerId: string) => {
    navigate(`/profile/${playerId}`);
  };

  const data = activeTab === 'friends' ? friendsData : globalData;
  const isLoading = activeTab === 'friends' ? friendsLoading : globalLoading;
  const players = data?.leaderboard?.players || [];
  const currentUserRank = data?.leaderboard?.yourRank;

  return (
    <div className="leaderboard-view">
      <div className="leaderboard-view__header">
        <h1 className="leaderboard-view__title">Таблица лидеров</h1>
        <div className="leaderboard-view__controls">
          <Input
            placeholder="Поиск по имени..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="leaderboard-view__search"
          />
          <select
            value={gameMode}
            onChange={(e) => setGameMode(e.target.value)}
            className="leaderboard-view__mode-select"
          >
            <option value="all">Все режимы</option>
            <option value="1v1">1 vs 1</option>
            <option value="2v2">2 vs 2</option>
          </select>
        </div>
      </div>

      <LeaderboardTabs activeTab={activeTab} onTabChange={handleTabChange} />

      <LeaderboardTable
        players={players}
        currentUserRank={currentUserRank}
        isLoading={isLoading}
        onPlayerClick={handlePlayerClick}
      />
    </div>
  );
};