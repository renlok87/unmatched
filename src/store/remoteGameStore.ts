/**
 * Remote Game Store (v2)
 *
 * Единственный источник истины игры на фронте — СЕРВЕР. Стор:
 * - загружает начальное состояние (GetGame → контентные Hero/Board → GetGameState),
 * - применяет полные wire-снапшоты (query/mutation/subscription) через
 *   applyWireState с guard'ом по sequenceNumber,
 * - шлёт gameplay-мутации (ответ применяется сразу; эхо подписки
 *   дедуплицируется по seq),
 * - отдаёт adaptedState (локальный формат) для Phaser GameScene.
 *
 * Никакой локальной игровой логики — валидация подсказок UI ведётся по
 * wire-состоянию, истина всегда у сервера.
 */

import { create } from 'zustand';
import { gql as apolloGql } from '@apollo/client';
import { apolloClient } from '@/lib/apolloClient';
import { useAuthStore } from '@/store/authStore';
import * as gql from '@/gql/graphql';
import {
  adaptToLocal,
  parseWireState,
  parseSubscriptionState,
  type AdapterRefs,
  type WireGameState,
} from '@/lib/gameStateAdapter';
import type { GameState as LocalGameState, BoardDefinition } from '@/core/models/types';

export type ConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'error';

// Контентные запросы (арты): герой по ИМЕНИ (контентный резолвер hero(id)
// ключуется именем), доски — списком
const HERO_ASSETS_QUERY = apolloGql`
  query RemoteHeroAssets($id: String!) {
    hero(id: $id) {
      id
      name
      avatarUrl
      cards {
        id
        title
        imageUrl
        imageUrlRu
      }
    }
  }
`;

const BOARDS_QUERY = apolloGql`
  query RemoteBoards {
    boards {
      id
      name
      width
      height
      recommendedPlayers
      imageUrl
      spaces {
        position { x y }
        zones
        isObstacle
      }
    }
  }
`;

interface MutationResultShape {
  state: string;
  sequenceNumber: number;
}

interface RemoteGameState {
  // Состояние
  currentGameId: string | null;
  wireState: WireGameState | null;
  adaptedState: LocalGameState | null;
  lastSequenceNumber: number;
  refs: AdapterRefs;
  localUserId: string | null;
  connectionStatus: ConnectionStatus;
  syncError: string | null;
  actionError: string | null;
  isSyncing: boolean;

  // UI-selection (никакой игровой логики)
  selectedFighterId: string | null;
  selectedCardId: string | null;

  // Подключение/синхронизация
  connectToGame: (gameId: string) => Promise<void>;
  disconnect: () => void;
  applyWireState: (wire: WireGameState) => void;
  handleSubscriptionState: (payload: Parameters<typeof parseSubscriptionState>[0]) => void;
  refetchState: () => Promise<void>;

  // Хелперы для UI
  isMyTurn: () => boolean;
  actionsRemaining: () => number;
  amIDefender: () => boolean;

  // Мутации gameplay
  maneuver: (fighterId: string, path: Array<{ x: number; y: number }>, boostCardId?: string) => Promise<void>;
  moveFighter: (fighterId: string, x: number, y: number) => Promise<void>;
  attack: (attackerId: string, targetId: string, cardId: string, boostCardId?: string) => Promise<void>;
  playDefense: (cardId: string, boostCardId?: string) => Promise<void>;
  playScheme: (cardId: string) => Promise<void>;
  resolveCombat: () => Promise<void>;
  endTurn: () => Promise<void>;
  pass: () => Promise<void>;
  leaveGame: () => Promise<void>;

  // UI selection
  selectFighter: (fighterId: string | null) => void;
  selectCard: (cardId: string | null) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  clearErrors: () => void;
}

/** id текущего юзера: authStore (источник истины) с фоллбеком на localStorage */
function currentUserId(): string | null {
  return useAuthStore.getState().user?.id ?? localStorage.getItem('userId');
}

const emptyRefs = (): AdapterRefs => ({ usernames: {}, heroAssets: {}, board: null });

export const useRemoteGameStore = create<RemoteGameState>((set, get) => ({
  currentGameId: null,
  wireState: null,
  adaptedState: null,
  lastSequenceNumber: 0,
  refs: emptyRefs(),
  localUserId: null,
  connectionStatus: 'disconnected',
  syncError: null,
  actionError: null,
  isSyncing: false,
  selectedFighterId: null,
  selectedCardId: null,

  connectToGame: async (gameId: string) => {
    set({
      connectionStatus: 'connecting',
      syncError: null,
      isSyncing: true,
      currentGameId: gameId,
      localUserId: currentUserId(),
    });

    try {
      // 1. Метаданные игры: username'ы, boardId
      const { data: gameData } = await apolloClient.query<{
        game: {
          boardId?: string | null;
          players: Array<{ userId: string; username: string; heroId?: string | null }>;
        };
      }>({
        query: gql.GetGameDocument,
        variables: { id: gameId },
        fetchPolicy: 'network-only',
      });
      const usernames: Record<string, string> = {};
      gameData.game.players.forEach((p) => {
        usernames[p.userId] = p.username;
      });

      // 2. Начальное wire-состояние
      const { data: stateData } = await apolloClient.query<{
        gameState: { state: string; sequenceNumber: number };
      }>({
        query: gql.GetGameStateDocument,
        variables: { gameId },
        fetchPolicy: 'network-only',
      });
      const wire = parseWireState(stateData.gameState.state);

      // 3. Контентные арты: герои по именам HERO-бойцов + доска
      const heroNames = [
        ...new Set(wire.fighters.filter((f) => f.type === 'HERO').map((f) => f.name)),
      ];
      const heroAssets: AdapterRefs['heroAssets'] = {};
      await Promise.all(
        heroNames.map(async (name) => {
          try {
            const { data } = await apolloClient.query<{
              hero: {
                name: string;
                avatarUrl?: string;
                cards: Array<{ id: string; title: string; imageUrl?: string; imageUrlRu?: string }>;
              } | null;
            }>({ query: HERO_ASSETS_QUERY, variables: { id: name } });
            if (data.hero) {
              heroAssets[name] = {
                avatarUrl: data.hero.avatarUrl,
                cards: data.hero.cards ?? [],
              };
            }
          } catch {
            // арт-фоллбек в GameScene — отсутствие контента не блокирует игру
          }
        }),
      );

      let board: BoardDefinition | null = null;
      try {
        const { data } = await apolloClient.query<{ boards: Array<BoardDefinition & { id: string }> }>({
          query: BOARDS_QUERY,
        });
        const boardId = gameData.game.boardId;
        board =
          (boardId ? data.boards.find((b) => b.id === boardId) : undefined) ??
          // wire-геометрия точнее списка — фоллбек по размеру
          data.boards.find(
            (b) => b.width === wire.boardState.width && b.height === wire.boardState.height,
          ) ??
          null;
      } catch {
        board = null; // fallback на wire-геометрию в адаптере
      }

      set({ refs: { usernames, heroAssets, board } });
      get().applyWireState(wire);
      set({ connectionStatus: 'connected', isSyncing: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to connect to game';
      set({ connectionStatus: 'error', syncError: message, isSyncing: false });
      throw error;
    }
  },

  disconnect: () => {
    set({
      currentGameId: null,
      wireState: null,
      adaptedState: null,
      lastSequenceNumber: 0,
      refs: emptyRefs(),
      connectionStatus: 'disconnected',
      syncError: null,
      actionError: null,
      selectedFighterId: null,
      selectedCardId: null,
    });
  },

  /**
   * Единая точка применения wire-снапшота (query/mutation/subscription).
   * Каждое событие — ПОЛНЫЙ снапшот: guard по seq + merge decks/discardPiles
   * (подписка их не несёт). Дельты/eventsSince не нужны.
   */
  applyWireState: (wire: WireGameState) => {
    const state = get();
    if (wire.sequenceNumber <= state.lastSequenceNumber && state.wireState) {
      return; // эхо подписки после ответа мутации / устаревший снапшот
    }
    const merged: WireGameState = {
      ...wire,
      decks: wire.decks ?? state.wireState?.decks,
      discardPiles: wire.discardPiles ?? state.wireState?.discardPiles,
    };
    const localUserId = state.localUserId ?? currentUserId() ?? '';
    set({
      wireState: merged,
      adaptedState: adaptToLocal(merged, state.refs, localUserId),
      lastSequenceNumber: wire.sequenceNumber,
    });
  },

  handleSubscriptionState: (payload) => {
    try {
      get().applyWireState(parseSubscriptionState(payload));
    } catch (e) {
      console.error('[remoteGameStore] Failed to parse subscription state:', e);
    }
  },

  refetchState: async () => {
    const gameId = get().currentGameId;
    if (!gameId) return;
    const { data } = await apolloClient.query<{ gameState: { state: string } }>({
      query: gql.GetGameStateDocument,
      variables: { gameId },
      fetchPolicy: 'network-only',
    });
    // refetch после конфликта: принимаем снапшот безусловно (сброс guard'а)
    set({ lastSequenceNumber: 0, wireState: null });
    get().applyWireState(parseWireState(data.gameState.state));
  },

  isMyTurn: () => {
    const { wireState, localUserId } = get();
    return Boolean(wireState && localUserId && wireState.currentTurnPlayerId === localUserId);
  },

  actionsRemaining: () => get().wireState?.metadata.actionsRemaining ?? 0,

  amIDefender: () => {
    const { wireState, localUserId } = get();
    return Boolean(wireState?.metadata.combatInfo?.defenderId === localUserId);
  },

  maneuver: (fighterId, path, boostCardId) =>
    runMutation(set, get, gql.ManeuverDocument, {
      input: { gameId: get().currentGameId, fighterId, boostCardId: boostCardId ?? null, path },
    }, 'maneuver'),

  moveFighter: (fighterId, x, y) =>
    runMutation(set, get, gql.MoveFighterDocument, {
      input: { gameId: get().currentGameId, fighterId, x, y },
    }, 'moveFighter'),

  attack: (attackerId, targetId, cardId, boostCardId) =>
    runMutation(set, get, gql.AttackDocument, {
      input: {
        gameId: get().currentGameId,
        attackerId,
        targetId,
        cardId,
        boostCardId: boostCardId ?? null,
      },
    }, 'attack'),

  playDefense: (cardId, boostCardId) =>
    runMutation(set, get, gql.PlayDefenseDocument, {
      input: { gameId: get().currentGameId, cardId, boostCardId: boostCardId ?? null },
    }, 'playDefense'),

  playScheme: (cardId) =>
    runMutation(set, get, gql.PlaySchemeDocument, {
      input: { gameId: get().currentGameId, cardId },
    }, 'playScheme'),

  resolveCombat: () =>
    runMutation(set, get, gql.ResolveCombatDocument, {
      input: { gameId: get().currentGameId },
    }, 'resolveCombat'),

  endTurn: () =>
    runMutation(set, get, gql.EndTurnDocument, {
      input: { gameId: get().currentGameId },
    }, 'endTurn'),

  pass: () =>
    runMutation(set, get, gql.PassDocument, {
      input: { gameId: get().currentGameId },
    }, 'pass'),

  leaveGame: async () => {
    const gameId = get().currentGameId;
    if (!gameId) return;
    try {
      await apolloClient.mutate({
        mutation: gql.LeaveGameDocument,
        variables: { gameId },
      });
    } finally {
      get().disconnect();
    }
  },

  selectFighter: (fighterId) => set({ selectedFighterId: fighterId }),
  selectCard: (cardId) => set({ selectedCardId: cardId }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  clearErrors: () => set({ syncError: null, actionError: null }),
}));

/**
 * Общий путь gameplay-мутаций: ответ применяется сразу (мгновенный отклик),
 * эхо подписки с тем же seq отбросит guard. Конфликт optimistic lock /
 * любая ошибка → actionError + refetch актуального состояния.
 */
async function runMutation(
  set: (partial: Partial<RemoteGameState>) => void,
  get: () => RemoteGameState,
  document: unknown,
  variables: Record<string, unknown>,
  name: string,
): Promise<void> {
  set({ actionError: null });
  try {
    const { data } = await apolloClient.mutate({
      mutation: document as never,
      variables,
    });
    const result = (data as Record<string, MutationResultShape> | null)?.[name];
    if (result?.state) {
      get().applyWireState(parseWireState(result.state));
    }
    // после успешного действия сбрасываем выбор
    set({ selectedCardId: null, selectedFighterId: null });
  } catch (error) {
    const message = error instanceof Error ? error.message : `Action ${name} failed`;
    set({ actionError: message });
    if (/Concurrent modification|sequence/i.test(message)) {
      await get().refetchState().catch(() => undefined);
    }
    throw error;
  }
}

// Selector-хуки
export const useCurrentGameId = () => useRemoteGameStore((s) => s.currentGameId);
export const useAdaptedGameState = () => useRemoteGameStore((s) => s.adaptedState);
export const useConnectionStatus = () => useRemoteGameStore((s) => s.connectionStatus);
export const useIsGameSyncing = () => useRemoteGameStore((s) => s.isSyncing);
export const useGameSyncError = () => useRemoteGameStore((s) => s.syncError);
export const useActionError = () => useRemoteGameStore((s) => s.actionError);
