/**
 * Пример компонента с использованием Apollo Client и сгенерированных типов
 */

import { useQuery, useMutation, useSubscription } from '@apollo/client';
import { GetGameDocument, GameStateUpdatedDocument, CreateGameDocument, JoinGameDocument, ToggleReadyDocument, GameMode } from '@/gql';
import type { GetGameQuery, CreateGameMutationVariables, JoinGameMutationVariables, ToggleReadyMutationVariables } from '@/gql';

interface ApolloExampleProps {
  gameId: string;
}

export function ApolloExample({ gameId }: ApolloExampleProps) {
  // Хук полностью типизирован! gameId проверяется на соответствие String!
  const { data, loading, error } = useQuery<GetGameQuery>(GetGameDocument, {
    variables: { id: gameId },
    skip: !gameId,
  });

  // Подписка на real-time обновления игры
  const { data: subscriptionData } = useSubscription(
    GameStateUpdatedDocument,
    {
      variables: { gameId, since: 0 },
      skip: !gameId,
    }
  );

  if (loading) return <div>Loading game...</div>;
  if (error) return <div>Error: {error.message}</div>;

  const game = data?.game;
  if (!game) return <div>Game not found</div>;

  return (
    <div className="game-container">
      <h2>Game: {game.id}</h2>
      <div className="game-info">
        <p>Mode: {game.mode}</p>
        <p>Status: {game.status}</p>
        <p>Phase: {game.phase ?? 'N/A'}</p>
        <p>Current Turn: {game.currentTurn ?? 'N/A'}</p>
      </div>

      <div className="players">
        <h3>Players:</h3>
        {game.players.map((player) => (
          <div key={player.id} className="player">
            <p>
              {player.username} {player.avatar && `(${player.avatar})`}
            </p>
            <p>Hero: {player.heroId ?? 'Not selected'}</p>
            <p>Ready: {player.isReady ? 'Yes' : 'No'}</p>
            <p>Passed: {player.hasPassed ? 'Yes' : 'No'}</p>
          </div>
        ))}
      </div>

      {subscriptionData?.gameStateUpdated && (
        <div className="live-updates">
          <h4>Live Update:</h4>
          <p>Phase: {subscriptionData.gameStateUpdated.phase}</p>
          <p>Turn: {subscriptionData.gameStateUpdated.turnCount}</p>
        </div>
      )}
    </div>
  );
}

/**
 * Пример с мутациями
 */
export function GameActions() {
  const [createGame, { loading: creating }] = useMutation(CreateGameDocument, {
    refetchQueries: ['MyGames'],
  });

  const [joinGame, { loading: joining }] = useMutation(JoinGameDocument);

  const [toggleReady, { loading: toggling }] = useMutation(ToggleReadyDocument);

  const handleCreateGame = () => {
    createGame({
      variables: {
        input: {
          mode: GameMode.OneVOne,
          boardId: 'cobble-city',
        },
      } as CreateGameMutationVariables,
    });
  };

  const handleJoinGame = (gameId: string, heroId: string) => {
    joinGame({
      variables: {
        input: {
          gameId,
          heroId,
        },
      } as JoinGameMutationVariables,
    });
  };

  const handleToggleReady = (gameId: string) => {
    toggleReady({
      variables: { gameId } as ToggleReadyMutationVariables,
    });
  };

  return (
    <div className="game-actions">
      <button onClick={handleCreateGame} disabled={creating}>
        Create Game
      </button>
      <button onClick={() => handleJoinGame('game-123', 'hero-ms-marvel')} disabled={joining}>
        Join Game
      </button>
      <button onClick={() => handleToggleReady('game-123')} disabled={toggling}>
        Toggle Ready
      </button>
    </div>
  );
}

/**
 * Пример с подписками
 */
export function GameSubscription({ gameId }: { gameId: string }) {
  const { data, loading } = useSubscription(
    GameStateUpdatedDocument,
    {
      variables: { gameId, since: 0 },
    }
  );

  if (loading) return <div>Connecting to game...</div>;

  const updatedState = data?.gameStateUpdated;

  return (
    <div className="game-updates">
      <h3>Live Updates:</h3>
      {updatedState && (
        <>
          <p>Phase: {updatedState.phase}</p>
          <p>Turn Count: {updatedState.turnCount}</p>
          <p>Current Player: {updatedState.currentTurnPlayerId}</p>
          <p>Sequence: {updatedState.sequenceNumber}</p>
        </>
      )}
    </div>
  );
}
