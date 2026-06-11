import React, { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useHeroSelectionStore } from '@/store/heroSelectionStore';
import { HeroGrid } from './HeroGrid';
import { HeroDetailsPanel } from './HeroDetailsPanel';
import { apolloClient } from '@/lib/apolloClient';
import { GetGameDocument } from '@/gql/graphql';

export const HeroSelection: React.FC = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const {
    heroes,
    selectedHero,
    takenHeroIds,
    loading,
    error,
    filters,
    mount,
    unmount,
    loadHeroes,
    setFilters,
    selectHero,
    selectHeroOnServer,
    setTakenHeroIds,
    clearError,
  } = useHeroSelectionStore();

  const [hoveredHero, setHoveredHero] = React.useState<typeof selectedHero>(null);

  useEffect(() => {
    mount();

    if (gameId) {
      loadHeroes();
      pollGameStatus();
    }

    return () => {
      unmount();
    };
  }, [gameId]);

  const pollGameStatus = async () => {
    if (!gameId) return;

    try {
      const { data } = await apolloClient.query({
        query: GetGameDocument,
        variables: { id: gameId },
        fetchPolicy: 'network-only',
      });

      if (data?.game) {
        const heroIds = data.game.players
          .filter((p: any) => p.heroId)
          .map((p: any) => p.heroId);
        setTakenHeroIds(heroIds);
      }
    } catch (err) {
      console.error('Failed to poll game status:', err);
    }
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFilters({ search: e.target.value });
  };

  const handleSetChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFilters({ set: e.target.value || null });
  };

  const handleHeroClick = async (hero: typeof selectedHero) => {
    if (!hero || !gameId) return;

    selectHero(hero);

    try {
      await selectHeroOnServer(gameId, hero.id);

      setTimeout(() => {
        pollGameStatus();
      }, 500);
    } catch (err) {
      console.error('Failed to select hero:', err);
    }
  };

  const handleHeroHover = (hero: typeof selectedHero) => {
    setHoveredHero(hero);
  };

  const displayHero = hoveredHero || selectedHero;

  return (
    <div className="hero-selection">
      <div className="hero-selection__header">
        <h1 className="hero-selection__title">Выберите героя</h1>
        <div className="hero-selection__filters">
          <div className="hero-selection__filter">
            <input
              type="text"
              placeholder="Поиск по имени..."
              value={filters.search || ''}
              onChange={handleSearchChange}
              className="hero-selection__search-input"
            />
          </div>
          <div className="hero-selection__filter">
            <select
              value={filters.set || ''}
              onChange={handleSetChange}
              className="hero-selection__set-select"
            >
              <option value="">Все сеты</option>
              <option value="Marvel">Marvel</option>
              <option value="DC">DC</option>
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="hero-selection__error">
          <span>⚠️</span>
          <span>{error}</span>
          <button onClick={clearError}>✕</button>
        </div>
      )}

      <div className="hero-selection__content">
        <div className="hero-selection__grid">
          <HeroGrid
            heroes={heroes}
            selectedHero={selectedHero}
            takenHeroIds={takenHeroIds}
            loading={loading}
            onHeroClick={handleHeroClick}
            onHeroHover={handleHeroHover}
            emptyMessage="Нет героев, соответствующих фильтрам"
          />
        </div>

        {displayHero && (
          <div className="hero-selection__details">
            <HeroDetailsPanel hero={displayHero} />
          </div>
        )}
      </div>
    </div>
  );
};

export default HeroSelection;