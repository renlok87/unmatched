import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card } from './Card';
import { gql } from '@apollo/client';
import { apolloClient } from '@/lib/apolloClient';
import { CardType, EffectTiming } from '../../core/models/types';
import type { CardInstance, CardDefinition } from '../../core/models/types';
import './CardShow.css';

// GraphQL query для получения карты по ID
const GET_CARD_QUERY = gql`
  query GetCard($id: String!) {
    card(id: $id) {
      id
      title
      type
      value
      boost
      quantity
      characterName
      effects {
        id
        timing
        text
      }
    }
  }
`;

// Преобразование типов из GraphQL в наши типы
const mapCardType = (type: string): CardType => {
  const typeMap: Record<string, CardType> = {
    'ATTACK': CardType.ATTACK,
    'DEFENSE': CardType.DEFENSE,
    'VERSATILE': CardType.VERSATILE,
    'SCHEME': CardType.SCHEME,
    'attack': CardType.ATTACK,
    'defense': CardType.DEFENSE,
    'versatile': CardType.VERSATILE,
    'scheme': CardType.SCHEME,
  };
  return typeMap[type] ?? CardType.ATTACK;
};

const mapEffectTiming = (timing: string): EffectTiming => {
  const timingMap: Record<string, EffectTiming> = {
    'IMMEDIATELY': EffectTiming.IMMEDIATELY,
    'DURING_COMBAT': EffectTiming.DURING_COMBAT,
    'AFTER_COMBAT': EffectTiming.AFTER_COMBAT,
    'START_OF_TURN': EffectTiming.START_OF_TURN,
    'END_OF_TURN': EffectTiming.END_OF_TURN,
    'WHEN_PLAYED': EffectTiming.WHEN_PLAYED,
    'WHEN_ATTACKED': EffectTiming.WHEN_ATTACKED,
    'WHEN_DEFENDING': EffectTiming.WHEN_DEFENDING,
    'immediately': EffectTiming.IMMEDIATELY,
    'during_combat': EffectTiming.DURING_COMBAT,
    'after_combat': EffectTiming.AFTER_COMBAT,
    'start_of_turn': EffectTiming.START_OF_TURN,
    'end_of_turn': EffectTiming.END_OF_TURN,
    'when_played': EffectTiming.WHEN_PLAYED,
    'when_attacked': EffectTiming.WHEN_ATTACKED,
    'when_defending': EffectTiming.WHEN_DEFENDING,
  };
  return timingMap[timing] ?? EffectTiming.IMMEDIATELY;
};

interface GraphQLEffect {
  id: string;
  timing: string;
  text: string;
}

interface GraphQLCard {
  id: string;
  title: string;
  type: string;
  value: number;
  boost: number;
  quantity: number;
  characterName: string;
  effects?: GraphQLEffect[];
}

export const CardShow: React.FC = () => {
  const { cardId } = useParams<{ cardId: string }>();
  const navigate = useNavigate();
  const [card, setCard] = useState<CardInstance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  console.log('CardShow render, cardId:', cardId, 'type:', typeof cardId);

  useEffect(() => {
    console.log('CardShow useEffect, cardId:', cardId);

    if (!cardId) {
      console.error('Card ID is empty!');
      setError('Card ID not provided');
      setLoading(false);
      return;
    }

    const fetchCard = async () => {
      try {
        const { data, errors } = await apolloClient.query<{
          card: GraphQLCard;
        }>({
          query: GET_CARD_QUERY,
          variables: { id: cardId },
          fetchPolicy: 'network-only',
        });

        if (errors || !data?.card) {
          setError(errors?.map(e => e.message).join(', ') || `Card with ID "${cardId}" not found`);
          return;
        }

        const graphqlCard = data.card;

        // Создаём CardDefinition из данных GraphQL
        const cardDefinition: CardDefinition = {
          id: graphqlCard.id,
          title: graphqlCard.title,
          type: mapCardType(graphqlCard.type),
          value: graphqlCard.value,
          boost: graphqlCard.boost,
          quantity: graphqlCard.quantity,
          characterName: graphqlCard.characterName,
          effects: (graphqlCard.effects || []).map(effect => ({
            id: effect.id,
            timing: mapEffectTiming(effect.timing),
            text: effect.text,
          })),
        };

        const cardInstance: CardInstance = {
          id: graphqlCard.id,
          definition: cardDefinition,
          ownerId: 'viewer',
          instanceIndex: 0,
        };

        setCard(cardInstance);
      } catch (err) {
        setError('Failed to load card data');
        console.error('Error loading card:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchCard();
  }, [cardId]);

  if (loading) {
    return (
      <div className="card-show-container">
        <div className="card-show-loading">Loading card...</div>
      </div>
    );
  }

  if (error || !card) {
    return (
      <div className="card-show-container">
        <div className="card-show-error">
          <p>{error || 'Card not found'}</p>
          <button onClick={() => navigate(-1)} className="btn-back">
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="card-show-container">
      <button onClick={() => navigate(-1)} className="btn-back">
        ← Back
      </button>

      <div className="card-show-content">
        <div className="card-show-card">
          <Card card={card} isPlayable={false} showValue={true} />
        </div>

        <div className="card-show-details">
          <h1>{card.definition.title}</h1>

          <div className="card-show-meta">
            <span className={`card-type-badge ${card.definition.type}`}>
              {card.definition.type.toUpperCase()}
            </span>
            <span className="card-id">ID: {card.definition.id}</span>
          </div>

          <div className="card-show-stats">
            <div className="stat">
              <span className="stat-label">Value:</span>
              <span className="stat-value">{card.definition.value}</span>
            </div>
            {card.definition.boost > 0 && (
              <div className="stat">
                <span className="stat-label">Boost:</span>
                <span className="stat-value">+{card.definition.boost}</span>
              </div>
            )}
            <div className="stat">
              <span className="stat-label">Quantity in Deck:</span>
              <span className="stat-value">{card.definition.quantity}</span>
            </div>
          </div>

          <div className="card-show-character">
            <span className="character-label">Character:</span>
            <span className="character-name">{card.definition.characterName}</span>
          </div>

          {card.definition.effects.length > 0 && (
            <div className="card-show-effects">
              <h2>Effects</h2>
              {card.definition.effects.map((effect) => (
                <div key={effect.id} className="effect-detail">
                  <span className="effect-timing-badge">{effect.timing}</span>
                  <p className="effect-text">{effect.text}</p>
                </div>
              ))}
            </div>
          )}

          {card.definition.effects.length === 0 && (
            <div className="card-show-effects">
              <p className="no-effects">This card has no special effects.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CardShow;
