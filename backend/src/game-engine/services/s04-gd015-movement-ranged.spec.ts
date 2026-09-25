import { GameState } from '../models';
import { s03Fixture, s03Engine } from '../../test/fixtures/s03-engine.fixture';
import { AiDecisionService } from './ai-decision.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { GameRulesValidator } from '../validators/game-rules.validator';

const context = (state: GameState, userId = 'a') => ({ gameId: state.gameId, userId, currentState: state });

type Patch = (f: GameState['fighters'][number]) => GameState['fighters'][number];

function fixture(opts: {
  hand?: number;
  fighters?: Record<string, Patch>;
  cells?: (x: number, y: number, cell: GameState['boardState']['cells'][number][number]) => GameState['boardState']['cells'][number][number];
} = {}): GameState {
  const base = s03Fixture(opts.hand ?? 1);
  let state = base;
  if (opts.fighters) {
    state = { ...state, fighters: state.fighters.map(f => (opts.fighters![f.id] ? opts.fighters![f.id](f) : f)) };
  }
  if (opts.cells) {
    state = {
      ...state,
      boardState: {
        ...state.boardState,
        cells: state.boardState.cells.map((row, y) => row.map((cell, x) => opts.cells!(x, y, cell))),
      },
    };
  }
  return state;
}

describe('GD-015: movement path rules via production executor', () => {
  let service: any;
  beforeEach(() => { service = s03Engine().executor; });

  async function begin(state: GameState) {
    const r = await service.executeBeginManeuver({ gameId: state.gameId, expectedSequenceNumber: state.sequenceNumber }, context(state));
    expect(r.success).toBe(true);
    return r.gameState as GameState;
  }

  it('maneuver path may traverse a living allied fighter', async () => {
    const state = fixture({ fighters: { helper: f => ({ ...f, position: { x: 1, y: 0 } }) } });
    const pending = await begin(state);
    const r = await service.executeManeuver({ gameId: state.gameId, maneuverId: pending.metadata.pendingManeuver!.id,
      moves: [{ fighterId: 'a', path: [{ x: 1, y: 0 }, { x: 2, y: 0 }] }] }, context(pending));
    expect(r.success).toBe(true);
    expect(r.gameState.fighters[0].position).toEqual({ x: 2, y: 0 });
  });

  it('maneuver path through a living enemy fails atomically', async () => {
    const state = fixture({ fighters: { b: f => ({ ...f, position: { x: 1, y: 0 } }) } });
    const pending = await begin(state);
    const before = JSON.parse(JSON.stringify(pending));
    const r = await service.executeManeuver({ gameId: state.gameId, maneuverId: pending.metadata.pendingManeuver!.id,
      moves: [{ fighterId: 'a', path: [{ x: 1, y: 0 }, { x: 2, y: 0 }] }] }, context(pending));
    expect(r.success).toBe(false);
    expect(r.gameState).toBeUndefined();
    // pending/hand/action state unchanged on rejected completion
    expect(pending.metadata.pendingManeuver).toEqual(before.metadata.pendingManeuver);
    expect(pending.handZones.a.cards.map(c => c.id)).toEqual(before.handZones.a.cards.map((c: any) => c.id));
    expect(pending.metadata.actionsRemaining).toBe(1);
    expect(pending.sequenceNumber).toBe(before.sequenceNumber);
    expect(pending.fighters.map(f => f.position)).toEqual(before.fighters.map(f => f.position));
    // тот же манёвр всё ещё завершаем без движения
    const ok = await service.executeManeuver({ gameId: state.gameId, maneuverId: pending.metadata.pendingManeuver!.id, moves: [] }, context(pending));
    expect(ok.success).toBe(true);
  });

  it.each([
    ['enemy on endpoint', { b: (f: any) => ({ ...f, position: { x: 2, y: 0 } }) }],
    ['ally on endpoint', { helper: (f: any) => ({ ...f, position: { x: 2, y: 0 } }) }],
  ])('maneuver may not end on a living fighter: %s', async (_name, fighters) => {
    const state = fixture({ fighters: fighters as any });
    const pending = await begin(state);
    const r = await service.executeManeuver({ gameId: state.gameId, maneuverId: pending.metadata.pendingManeuver!.id,
      moves: [{ fighterId: 'a', path: [{ x: 1, y: 0 }, { x: 2, y: 0 }] }] }, context(pending));
    expect(r.success).toBe(false);
  });

  it('defeated fighters do not block path or endpoint', async () => {
    const dead = (f: any) => ({ ...f, health: 0, isDefeated: true, position: { x: 1, y: 0 } });
    // через побеждённого
    const through = fixture({ fighters: { helper: dead } });
    const p1 = await begin(through);
    const r1 = await service.executeManeuver({ gameId: through.gameId, maneuverId: p1.metadata.pendingManeuver!.id,
      moves: [{ fighterId: 'a', path: [{ x: 1, y: 0 }, { x: 2, y: 0 }] }] }, context(p1));
    expect(r1.success).toBe(true);
    // на клетку побеждённого
    const onto = fixture({ fighters: { helper: dead } });
    const p2 = await begin(onto);
    const r2 = await service.executeManeuver({ gameId: onto.gameId, maneuverId: p2.metadata.pendingManeuver!.id,
      moves: [{ fighterId: 'a', path: [{ x: 1, y: 0 }] }] }, context(p2));
    expect(r2.success).toBe(true);
    expect(r2.gameState.fighters[0].position).toEqual({ x: 1, y: 0 });
  });

  it('rejects a path longer than movement allowance', async () => {
    const state = fixture();
    const pending = await begin(state);
    const r = await service.executeManeuver({ gameId: state.gameId, maneuverId: pending.metadata.pendingManeuver!.id,
      moves: [{ fighterId: 'a', path: [{ x: 1, y: 0 }, { x: 2, y: 0 }, { x: 3, y: 0 }] }] }, context(pending));
    expect(r.success).toBe(false);
  });

  it('rejects a path through a wall cell and non-step paths', async () => {
    const walled = fixture({ cells: (x, _y, cell) => (x === 1 ? { ...cell, type: 'wall' as const } : cell) });
    const pending = await begin(walled);
    const r = await service.executeManeuver({ gameId: walled.gameId, maneuverId: pending.metadata.pendingManeuver!.id,
      moves: [{ fighterId: 'a', path: [{ x: 1, y: 0 }, { x: 2, y: 0 }] }] }, context(pending));
    expect(r.success).toBe(false);
    const jump = await service.executeManeuver({ gameId: walled.gameId, maneuverId: pending.metadata.pendingManeuver!.id,
      moves: [{ fighterId: 'a', path: [{ x: 3, y: 0 }] }] }, context(pending));
    expect(jump.success).toBe(false);
  });
});

describe('GD-015: ranged attacks vs board zones via production executor', () => {
  let service: any;
  beforeEach(() => { service = s03Engine().executor; });

  function zoned(zonesByCell: Record<string, string[] | string>, attackType: 'melee' | 'ranged', targetAt: { x: number; y: number }): GameState {
    return fixture({
      fighters: {
        a: f => ({ ...f, attackType }),
        b: f => ({ ...f, position: targetAt }),
      },
      cells: (x, y, cell) => {
        const z = zonesByCell[`${x}:${y}`];
        if (!z) return cell;
        return Array.isArray(z) ? { ...cell, zones: z } : { ...cell, zone: z };
      },
    });
  }

  it('ranged attack succeeds on adjacent target across disjoint zones', async () => {
    const state = zoned({ '0:0': 'A', '1:0': 'B' }, 'ranged', { x: 1, y: 0 });
    const r = await service.executeAttack({ gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'h0' }, context(state));
    expect(r.success).toBe(true);
    expect(r.gameState.phase).toBe('COMBAT');
  });

  it('ranged attack succeeds at distance via secondary zone intersection', async () => {
    const state = zoned({ '0:0': ['z1', 'z2'], '5:0': ['z2', 'z3'] }, 'ranged', { x: 5, y: 0 });
    const r = await service.executeAttack({ gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'h0' }, context(state));
    expect(r.success).toBe(true);
  });

  it('ranged attack succeeds via legacy single zone field', async () => {
    const state = zoned({ '0:0': 'legacy', '5:0': 'legacy' }, 'ranged', { x: 5, y: 0 });
    const r = await service.executeAttack({ gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'h0' }, context(state));
    expect(r.success).toBe(true);
  });

  it('ranged attack fails on distant target in disjoint zones', async () => {
    const state = zoned({ '0:0': ['z1'], '5:0': ['z9'] }, 'ranged', { x: 5, y: 0 });
    const r = await service.executeAttack({ gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'h0' }, context(state));
    expect(r.success).toBe(false);
    expect(state.phase).toBe('ACTION_MANEUVER');
    expect(state.metadata.actionsRemaining).toBe(2);
    expect(state.handZones.a.cards).toHaveLength(1);
  });

  it('melee attack stays adjacency-only even in a shared zone', async () => {
    const state = zoned({ '0:0': 'z1', '5:0': 'z1' }, 'melee', { x: 5, y: 0 });
    const r = await service.executeAttack({ gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'h0' }, context(state));
    expect(r.success).toBe(false);
  });
});

describe('GD-015: AI path consistency with movement rules', () => {
  it('AI maneuver path traverses a living ally and never ends on an occupied cell', () => {
    const ai = new AiDecisionService(new AdjacencyService());
    const state: GameState = {
      ...s03Fixture(0),
      currentTurnPlayerId: 'b',
      fighters: [
        { id: 'a', ownerId: 'a', heroId: 'a', name: 'a', type: 'HERO' as any, health: 10, maxHealth: 10,
          position: { x: 3, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
        { id: 'b', ownerId: 'b', heroId: 'b', name: 'b', type: 'HERO' as any, health: 10, maxHealth: 10,
          position: { x: 0, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
        { id: 'mb', ownerId: 'b', heroId: 'b', name: 'mb', type: 'MINION' as any, health: 10, maxHealth: 10,
          position: { x: 1, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
      ],
      metadata: { ...s03Fixture(0).metadata,
        pendingManeuver: { id: 'm1', playerId: 'b' }, actionsRemaining: 1 },
    } as any;
    const action = ai.decide(state, 'b');
    expect(action).toMatchObject({ kind: 'maneuver', maneuverId: 'm1' });
    const moves = (action as any).moves as Array<{ fighterId: string; path: Array<{ x: number; y: number }> }>;
    expect(moves).toHaveLength(1);
    const path = moves[0].path;
    // путь сквозь союзника на (1,0) — ближе к врагу на (3,0), чем окольный
    expect(path).toEqual([{ x: 1, y: 0 }, { x: 2, y: 0 }]);
    const last = path[path.length - 1];
    expect(state.fighters.some(f => f.health > 0 && f.position.x === last.x && f.position.y === last.y)).toBe(false);
    // сгенерированный путь валиден по серверным правилам
    const validator = new GameRulesValidator(new AdjacencyService());
    expect(validator.validateManeuver(state, 'b', undefined, path, 'b')).toEqual({ valid: true });
  });
});
