import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { adaptToLocal, type WireGameState } from '@/lib/gameStateAdapter';

const view = vi.hoisted(() => ({ state: {} as Record<string, unknown> }));
vi.mock('@/store/remoteGameStore', () => ({ useRemoteGameStore: () => view.state }));
vi.mock('@/hooks/useGameSync', () => ({ useGameSync: () => ({ isConnecting: false, hasError: false, connectionStatus: 'connected' }) }));
vi.mock('react-router-dom', () => ({ useParams: () => ({ gameId: 'g' }), useNavigate: () => vi.fn() }));
// Canvas and subscriptions are external to the React resource controls.
vi.mock('@/phaser/PhaserGame', () => ({ PhaserGame: () => null }));
import { GameView } from './GameView';

function setState(metadata: WireGameState['metadata'], phase = 'ACTION_MANEUVER') {
  const wire: WireGameState = {
    gameId: 'g', sequenceNumber: 11, phase, turnCount: 1, currentTurnPlayerId: 'a',
    players: [{ userId: 'a', heroId: 'a', health: 10, maxHealth: 10, fighterIds: [], isAlive: true }],
    fighters: [], boardState: { width: 3, height: 3 },
    handZones: { a: { maxSize: 7, cards: [
      { id: 'copy-1', cardId: 'same-catalog', cardType: 'ATTACK', name: 'First copy', boostValue: 1 },
      { id: 'new-instance', cardId: 'same-catalog', cardType: 'ATTACK', name: 'Newly drawn copy', boostValue: 3 },
    ] } }, metadata,
  };
  view.state = {
    wireState: wire,
    adaptedState: adaptToLocal(wire, { usernames: {}, heroAssets: {}, board: null, stanceOptions: {} }, 'a'),
    localUserId: 'a', selectedFighterId: null, selectedCardId: null,
    isMyTurn: () => true, actionsRemaining: () => metadata.actionsRemaining ?? 0,
    amIDefender: () => false, myPendingEffects: () => [], myStance: () => null, myStanceOptions: () => [],
  };
}

describe('S03 remote game controls', () => {
  beforeEach(() => setState({ actionsRemaining: 2 }));

  it('shows begin maneuver and no pass or early end-turn action', () => {
    const html = renderToStaticMarkup(<GameView />);
    expect(html).toContain('Начать манёвр');
    expect(html).not.toMatch(/>\s*Пас\s*</);
    expect(html).not.toContain('Конец хода');
  });

  it('restores the drawn hand and zero-move completion from a pending server snapshot', () => {
    setState({ actionsRemaining: 0, pendingManeuver: { id: 'm10', playerId: 'a' } });
    const html = renderToStaticMarkup(<GameView />);
    expect(html).toContain('Усиление манёвра');
    expect(html).toContain('value="new-instance"');
    expect(html).toContain('Newly drawn copy');
    expect(html).toContain('Завершить без движения');
    expect(html).not.toContain('Начать манёвр');
    expect(html).not.toContain('Конец хода');
  });

  it('restores exact-instance discard choices before turn handoff', () => {
    setState({ actionsRemaining: 0, pendingHandDiscard: { id: 'd10', playerId: 'a', count: 1 } }, 'TURN_END');
    const html = renderToStaticMarkup(<GameView />);
    expect(html).toContain('Сбросьте лишние карты');
    expect(html).toContain('value="copy-1"');
    expect(html).toContain('value="new-instance"');
    expect(html).not.toContain('Начать манёвр');
    expect(html).not.toContain('Конец хода');
  });

  it('counts only OWN remaining choices in the pending queue (foreign tails are not mine)', () => {
    const queue = [
      { id: 'pe1', type: 'MOVE', playerId: 'a', value: 1 },
      { id: 'pe2', type: 'MOVE', playerId: 'b', value: 1 },
      { id: 'pe3', type: 'MOVE', playerId: 'a', value: 1, optional: true },
    ] as const;
    setState({ actionsRemaining: 0, pendingEffects: [...queue] } as any);
    view.state = { ...view.state, myPendingEffects: () => [...queue] };
    const html = renderToStaticMarkup(<GameView />);
    expect(html).toContain('ещё в очереди: 1');
    expect(html).not.toContain('ещё в очереди: 2');
  });
});
