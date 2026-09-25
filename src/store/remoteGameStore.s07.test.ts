/** S07 GD-027 / ACC-011: дедупликация без потери полноты.
 *  Фикстуры перестановок HTTP-snapshot ↔ WS-проекция одного sequence:
 *  итоговое состояние одно, decks не стираются и не «освежаются» пустыми,
 *  старый снапшот не откатывает state, пропуск seq не требует дельт. */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { WireGameState } from '@/lib/gameStateAdapter';

const network = vi.hoisted(() => ({ mutate: vi.fn(), query: vi.fn() }));
vi.mock('@/lib/apolloClient', () => ({ apolloClient: network }));
vi.mock('@/store/authStore', () => ({ useAuthStore: { getState: () => ({ user: { id: 'a' } }) } }));
import { useRemoteGameStore } from './remoteGameStore';

const decks = {
  a: { cards: [], drawPile: [], count: 5 },
  b: { cards: [], drawPile: [], count: 4 },
};

function snap(seq: number, extra: Partial<WireGameState> = {}): WireGameState {
  return {
    gameId: 'g', sequenceNumber: seq, phase: 'ACTION_MANEUVER', turnCount: 1, currentTurnPlayerId: 'a',
    players: [{ userId: 'a', heroId: 'a', health: 10, maxHealth: 10, fighterIds: ['a'], isAlive: true }],
    fighters: [], boardState: { width: 3, height: 3 },
    handZones: { a: { cards: [], maxSize: 7 } },
    decks,
    discardPiles: { a: [], b: [] },
    metadata: { actionsRemaining: 1 },
    ...extra,
  } as WireGameState;
}

/** WS-проекция того же seq: без decks/discardPiles (частичная). */
const wsProjection = (seq: number, extra: Partial<WireGameState> = {}): WireGameState => {
  const { decks: _d, discardPiles: _dp, ...rest } = snap(seq, extra);
  return rest as WireGameState;
};

describe('S07 ACC-011 snapshot permutations', () => {
  beforeEach(() => {
    useRemoteGameStore.getState().disconnect();
    useRemoteGameStore.setState({ currentGameId: 'g', localUserId: 'a' });
  });

  it.each([
    { name: 'HTTP → WS', order: (seq: number) => [snap(seq), wsProjection(seq)] },
    { name: 'WS → HTTP', order: (seq: number) => [wsProjection(seq), snap(seq)] },
  ])('$name одного seq: одно состояние, decks/discard сохранены', ({ order }) => {
    const [first, second] = order(11);
    useRemoteGameStore.getState().applyWireState(first);
    useRemoteGameStore.getState().applyWireState(second);

    const s = useRemoteGameStore.getState();
    expect(s.lastSequenceNumber).toBe(11);
    expect(s.wireState).toEqual(snap(11));
  });

  it('старый snapshot после нового события не откатывает state', () => {
    useRemoteGameStore.getState().applyWireState(snap(12, { currentTurnPlayerId: 'b' }));
    useRemoteGameStore.getState().applyWireState(snap(11, { currentTurnPlayerId: 'a' }));
    const s = useRemoteGameStore.getState();
    expect(s.lastSequenceNumber).toBe(12);
    expect(s.wireState?.currentTurnPlayerId).toBe('b');
  });

  it('пропуск sequence применяется как новый снапшот (gap не блокирует)', () => {
    useRemoteGameStore.getState().applyWireState(snap(11));
    useRemoteGameStore.getState().applyWireState(wsProjection(13, { phase: 'COMBAT' }));
    const s = useRemoteGameStore.getState();
    expect(s.lastSequenceNumber).toBe(13);
    expect(s.wireState?.phase).toBe('COMBAT');
    // decks из seq 11 не стёрты проекцией без decks
    expect(s.wireState?.decks).toEqual(decks);
  });

  it('эхо мутации (ответ + подписка того же seq) не дублирует применение', () => {
    useRemoteGameStore.getState().applyWireState(snap(11));
    const before = useRemoteGameStore.getState().adaptedState;
    useRemoteGameStore.getState().applyWireState(wsProjection(11));
    const after = useRemoteGameStore.getState();
    expect(after.lastSequenceNumber).toBe(11);
    expect(after.adaptedState).toEqual(before);
  });

  it('refetchState применяет снапшот безусловно после сброса guard', async () => {
    useRemoteGameStore.getState().applyWireState(snap(20));
    network.query.mockImplementation(async () => ({
      data: { gameState: { state: JSON.stringify(snap(20, { phase: 'GAME_OVER' })) } },
    }));
    await useRemoteGameStore.getState().refetchState();
    const s = useRemoteGameStore.getState();
    expect(s.wireState?.phase).toBe('GAME_OVER');
    expect(s.lastSequenceNumber).toBe(20);
    expect(s.wireState?.decks).toEqual(decks);
  });
});
