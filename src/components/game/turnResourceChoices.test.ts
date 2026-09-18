import { describe, expect, it } from 'vitest';
import { appendManeuverStep, resourceControls, toggleDiscardInstance } from './turnResourceChoices';
import type { WireGameState } from '@/lib/gameStateAdapter';

const state = (metadata: WireGameState['metadata'] = {}): WireGameState => ({
  gameId: 'g', sequenceNumber: 10, phase: 'ACTION_MANEUVER', turnCount: 1,
  currentTurnPlayerId: 'a', players: [], fighters: [], handZones: {},
  boardState: { width: 3, height: 3 }, metadata: { actionsRemaining: 2, ...metadata },
});

describe('S03 resource choice controls', () => {
  it('offers begin maneuver while preventing early end-turn', () => {
    expect(resourceControls(state(), 'a')).toMatchObject({ canBegin: true, canEnd: false });
    expect(resourceControls(state({ actionsRemaining: 0 }), 'a')).toMatchObject({ canBegin: false, canEnd: true });
  });

  it('restores a pending maneuver with zero actions and blocks unrelated actions', () => {
    const pending = { id: 'm10', playerId: 'a' };
    expect(resourceControls(state({ actionsRemaining: 0, pendingManeuver: pending }), 'a'))
      .toMatchObject({ maneuver: pending, canBegin: false, canEnd: false, canAct: false });
    expect(resourceControls(state({ pendingManeuver: pending }), 'b'))
      .toMatchObject({ maneuver: null, canBegin: false, canEnd: false, canAct: false });
  });

  it('restores a discard choice and never exposes actions after terminal state', () => {
    const discard = { id: 'd10', playerId: 'a', count: 2 };
    const wire = { ...state({ pendingHandDiscard: discard }), phase: 'TURN_END' };
    expect(resourceControls(wire, 'a')).toMatchObject({ discard, canBegin: false, canEnd: false, canAct: false });
    expect(resourceControls({ ...wire, phase: 'GAME_OVER' }, 'a'))
      .toMatchObject({ discard: null, maneuver: null, canBegin: false, canEnd: false, canAct: false });
  });

  it('records ordered routes for several fighters without mutating previous choices', () => {
    const first = appendManeuverStep([], 'hero', { x: 1, y: 0 });
    const second = appendManeuverStep(first, 'helper', { x: 2, y: 1 });
    const third = appendManeuverStep(second, 'hero', { x: 1, y: 1 });
    expect(third).toEqual([
      { fighterId: 'hero', path: [{ x: 1, y: 0 }, { x: 1, y: 1 }] },
      { fighterId: 'helper', path: [{ x: 2, y: 1 }] },
    ]);
    expect(first).toEqual([{ fighterId: 'hero', path: [{ x: 1, y: 0 }] }]);
  });

  it('chooses distinct card instances and never silently replaces a full selection', () => {
    expect(toggleDiscardInstance(['copy-1'], 'copy-2', 2)).toEqual(['copy-1', 'copy-2']);
    expect(toggleDiscardInstance(['copy-1', 'copy-2'], 'copy-3', 2)).toEqual(['copy-1', 'copy-2']);
    expect(toggleDiscardInstance(['copy-1', 'copy-2'], 'copy-1', 2)).toEqual(['copy-2']);
  });
});
