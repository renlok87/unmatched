import React, { useEffect } from 'react';
import type { Hero } from '@/types/hero';
import { apolloClient } from '@/lib/apolloClient';
import { gql } from '@apollo/client';

interface HeroDetailsPanelProps {
  hero: Hero;
}

export const HeroDetailsPanel: React.FC<HeroDetailsPanelProps> = ({ hero }) => {
  const [details, setDetails] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(false);

  useEffect(() => {
    const loadDetails = async () => {
      setLoading(true);
      try {
        const { data } = await apolloClient.query({
          query: gql`
            query HeroDetails($id: String!) {
              hero(id: $id) {
                id
                name
                health
                movement
                set
                fighterType
                sidekickCount
                sidekickHealth
                urls {
                  avatar
                  mini
                  cardCover
                }
                abilities {
                  id
                  name
                  text
                  trigger
                }
                cards {
                  id
                  title
                  type
                  value
                  boost
                  quantity
                }
              }
            }
          `,
          variables: { id: hero.id },
          fetchPolicy: 'cache-first',
        });

        if (data?.hero) {
          setDetails(data.hero);
        }
      } catch (err) {
        console.error('Failed to load hero details:', err);
      } finally {
        setLoading(false);
      }
    };

    loadDetails();
  }, [hero.id]);

  const displayHero = details || hero;

  return (
    <div className="hero-details">
      <div className="hero-details__image">
        {displayHero.urls?.avatar ? (
          <img src={displayHero.urls.avatar} alt={displayHero.name} />
        ) : (
          <div className="hero-details__placeholder">{displayHero.name[0]}</div>
        )}
      </div>

      <h2 className="hero-details__name">{displayHero.name}</h2>

      <div className="hero-details__stats">
        <div className="hero-details__stat">
          <span className="hero-details__stat-label">Здоровье:</span>
          <span className="hero-details__stat-value">{displayHero.health}</span>
        </div>
        <div className="hero-details__stat">
          <span className="hero-details__stat-label">Перемещение:</span>
          <span className="hero-details__stat-value">{displayHero.movement}</span>
        </div>
        <div className="hero-details__stat">
          <span className="hero-details__stat-label">Тип бойца:</span>
          <span className="hero-details__stat-value">{displayHero.fighterType}</span>
        </div>
        <div className="hero-details__stat">
          <span className="hero-details__stat-label">Сет:</span>
          <span className="hero-details__stat-value">{displayHero.set}</span>
        </div>
        {displayHero.sidekickCount !== undefined && (
          <div className="hero-details__stat">
            <span className="hero-details__stat-label">Боевые товарищи:</span>
            <span className="hero-details__stat-value">{displayHero.sidekickCount}</span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="hero-details__loading">
          <div className="loading-spinner" />
          <p>Загрузка деталей...</p>
        </div>
      ) : (
        <>
          {displayHero.abilities && displayHero.abilities.length > 0 && (
            <div className="hero-details__abilities">
              <h3 className="hero-details__section-title">Способности</h3>
              {displayHero.abilities.map((ability: any) => (
                <div key={ability.id} className="hero-details__ability">
                  <h4 className="hero-details__ability-name">{ability.name}</h4>
                  <p className="hero-details__ability-text">{ability.text}</p>
                  {ability.trigger && (
                    <span className="hero-details__ability-trigger">
                      Триггер: {ability.trigger}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {displayHero.cards && displayHero.cards.length > 0 && (
            <div className="hero-details__deck">
              <h3 className="hero-details__section-title">Колода</h3>
              <div className="hero-details__deck-summary">
                {displayHero.cards.reduce((acc: Record<string, number>, card: any) => {
                  acc[card.type] = (acc[card.type] || 0) + card.quantity;
                  return acc;
                }, {})}
                {Object.entries(
                  displayHero.cards.reduce((acc: Record<string, number>, card: any) => {
                    acc[card.type] = (acc[card.type] || 0) + card.quantity;
                    return acc;
                  }, {}) as Record<string, number>,
                ).map(([type, count]) => (
                  <span key={type} className="hero-details__deck-item">
                    {type}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default HeroDetailsPanel;