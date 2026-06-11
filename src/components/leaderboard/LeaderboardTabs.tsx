import React from 'react';
import './LeaderboardTabs.css';

export type LeaderboardTab = 'global' | 'friends' | 'weekly';

interface LeaderboardTabsProps {
  activeTab: LeaderboardTab;
  onTabChange: (tab: LeaderboardTab) => void;
  friendsCount?: number;
}

export const LeaderboardTabs: React.FC<LeaderboardTabsProps> = ({
  activeTab,
  onTabChange,
  friendsCount = 0,
}) => {
  const tabs = [
    { id: 'global' as LeaderboardTab, label: 'Мир' },
    { id: 'friends' as LeaderboardTab, label: 'Друзья', badge: friendsCount },
    { id: 'weekly' as LeaderboardTab, label: 'Неделя' },
  ];

  return (
    <div className="leaderboard-tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`leaderboard-tabs__tab ${
            activeTab === tab.id ? 'leaderboard-tabs__tab--active' : ''
          }`}
          onClick={() => onTabChange(tab.id)}
        >
          <span className="leaderboard-tabs__tab-label">{tab.label}</span>
          {tab.badge !== undefined && tab.badge > 0 && (
            <span className="leaderboard-tabs__tab-badge">{tab.badge}</span>
          )}
        </button>
      ))}
    </div>
  );
};