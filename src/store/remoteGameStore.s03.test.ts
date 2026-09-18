import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getOperationAST, type DocumentNode } from 'graphql';
import type { WireGameState } from '@/lib/gameStateAdapter';

const network = vi.hoisted(() => ({ mutate: vi.fn(), query: vi.fn() }));
vi.mock('@/lib/apolloClient', () => ({ apolloClient: network }));
vi.mock('@/store/authStore', () => ({ useAuthStore: { getState: () => ({ user: { id: 'a' } }) } }));
import { useRemoteGameStore } from './remoteGameStore';

function state(metadata: WireGameState['metadata'] = {}): WireGameState {
  return {
    gameId: 'g', sequenceNumber: 10, phase: 'ACTION_MANEUVER', turnCount: 1, currentTurnPlayerId: 'a',
    players: [{ userId: 'a', heroId: 'a', health: 10, maxHealth: 10, fighterIds: ['a'], isAlive: true }],
    fighters: [], boardState: { width: 3, height: 3 },
    handZones: { a: { cards: [], maxSize: 7 } }, metadata: { actionsRemaining: 1, ...metadata },
  };
}

describe('S03 remote resource mutations', () => {
  beforeEach(() => {
    network.mutate.mockReset();
    useRemoteGameStore.getState().disconnect();
    useRemoteGameStore.setState({ currentGameId: 'g', localUserId: 'a' });
    useRemoteGameStore.getState().applyWireState(state());
  });

  it('begins only once and exposes the drawn card before a separate completion', async () => {
    const drawn = { id: 'new-instance', cardId: 'catalog', name: 'New boost', cardType: 'ATTACK' as const, boostValue: 3 };
    const next = { ...state({ actionsRemaining: 0, pendingManeuver: { id: 'm10', playerId: 'a' } }),
      sequenceNumber: 11, handZones: { a: { cards: [drawn], maxSize: 7 } } };
    network.mutate.mockImplementation(async ({ mutation, variables }: { mutation: DocumentNode; variables: unknown }) => {
      expect(getOperationAST(mutation)?.name?.value).toBe('BeginManeuver');
      expect(variables).toEqual({ input: { gameId: 'g', expectedSequenceNumber: 10 } });
      return { data: { beginManeuver: { state: JSON.stringify(next), sequenceNumber: 11 } } };
    });

    await useRemoteGameStore.getState().beginManeuver();

    expect(useRemoteGameStore.getState().wireState?.handZones.a.cards).toEqual([drawn]);
    expect(useRemoteGameStore.getState().wireState?.metadata.pendingManeuver?.id).toBe('m10');
    expect(network.mutate).toHaveBeenCalledTimes(1);
  });

  it.each([{ moves: [] }, { moves: [{ fighterId: 'hero', path: [{ x: 1, y: 0 }] }, { fighterId: 'helper', path: [{ x: 2, y: 1 }] }] }])
    ('completes the resumed choice with exact moves $moves and the newly drawn boost', async ({ moves }) => {
      useRemoteGameStore.getState().applyWireState({ ...state({ pendingManeuver: { id: 'persisted', playerId: 'a' } }), sequenceNumber: 11 });
      network.mutate.mockImplementation(async ({ mutation, variables }: { mutation: DocumentNode; variables: unknown }) => {
        expect(getOperationAST(mutation)?.name?.value).toBe('CompleteManeuver');
        expect(variables).toEqual({ input: { gameId: 'g', maneuverId: 'persisted', moves, boostCardId: 'new-instance' } });
        return { data: { maneuver: { state: JSON.stringify({ ...state(), sequenceNumber: 12 }), sequenceNumber: 12 } } };
      });
      await useRemoteGameStore.getState().completeManeuver('persisted', moves, 'new-instance');
      expect(useRemoteGameStore.getState().wireState?.metadata.pendingManeuver).toBeUndefined();
    });

  it('sends chosen instance IDs to the restored discard choice', async () => {
    network.mutate.mockImplementation(async ({ mutation, variables }: { mutation: DocumentNode; variables: unknown }) => {
      expect(getOperationAST(mutation)?.name?.value).toBe('DiscardToLimit');
      expect(variables).toEqual({ input: { gameId: 'g', pendingId: 'discard-10', cardIds: ['copy-2', 'copy-4'] } });
      return { data: { discardToLimit: { state: JSON.stringify({ ...state(), sequenceNumber: 11, currentTurnPlayerId: 'b' }), sequenceNumber: 11 } } };
    });
    await useRemoteGameStore.getState().discardToLimit('discard-10', ['copy-2', 'copy-4']);
    expect(useRemoteGameStore.getState().wireState?.currentTurnPlayerId).toBe('b');
  });
});
