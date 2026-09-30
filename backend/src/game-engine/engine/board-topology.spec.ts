/**
 * ENV-MAPS B1 — правила движка на ГРАФЕ оригинальной карты (board-topology).
 *
 * Синтетическая топологическая доска 6x3 (решётка; '#' — непроходимая
 * позиция без пространства):
 *
 *        x=0  x=1  x=2  x=3  x=4  x=5
 *   y=0   A -- B -- C ============== F        C==F — одна связь через 3 шага решётки
 *   y=1   G ---#--- H    #    #    J        G--H и B--L пересекаются в (1,1) БЕЗ развилки
 *   y=2   K -- L -- M    #    #    P
 *
 * Связи: A-B, B-C, C-F(длинная), F-J, J-P, G-K, G-H, H-M, H-C, K-L, L-M, L-B.
 * A и G — соседи по решётке, но НЕ связаны. Зоны: red {A,B,C},
 * blue {C,F,J,P} (C — в двух зонах), green {G,H,K,L,M}.
 *
 * Вторая половина файла — регрессия сеточных досок (Cobble City без links):
 * новые пути кода сравниваются с копиями ПРЕЖНИХ реализаций бит-в-бит.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { BoardState, Cell, Fighter, GameState, Position } from '../models';
import {
  createEmptyBoardState,
  CardType,
  EffectTarget,
  EffectTiming,
  EffectType,
  FighterType,
} from '../models';
import type { Card, CardEffect } from '../models';
import { GamePhase } from '../models';
import type { AttackDto, ManeuverDto } from '../../games/dto/gameplay.dto';
import {
  boardDistance,
  distanceField,
  graphDistance,
  hasTopology,
  isAdjacent,
  isWithinDistance,
  neighbours,
  ORTHOGONAL_NSEW,
} from './board-topology';
import { AdjacencyService } from './adjacency.service';
import { MovementService } from './movement.service';
import { AStarService, PathCacheService } from '../movement';
import {
  isCellPassable,
  isFreeEndpoint,
  isInBoardBounds,
  isTraversable,
} from '../movement/traversal';
import { GameRulesValidator } from '../validators/game-rules.validator';
import { AiDecisionService } from '../services/ai-decision.service';
import { GenericHeroAbilityHandler } from '../abilities/generic-hero-ability.handler';
import { ABILITY_CONFIGS } from '../abilities/ability-config';
import type { ExtendedHeroAbilityHandler } from '../abilities/hero-ability-registry';
import { MsMarvelHandler } from '../abilities/heroes/ms-marvel.handler';
import { s03Fixture, s03Engine } from '../../test/fixtures/s03-engine.fixture';

// ============================================================================
// Синтетическая топологическая доска
// ============================================================================

type SpaceId = 'A' | 'B' | 'C' | 'F' | 'G' | 'H' | 'J' | 'K' | 'L' | 'M' | 'P';

const SPACES: Record<SpaceId, { x: number; y: number; zones: string[] }> = {
  A: { x: 0, y: 0, zones: ['red'] },
  B: { x: 1, y: 0, zones: ['red'] },
  C: { x: 2, y: 0, zones: ['red', 'blue'] },
  F: { x: 5, y: 0, zones: ['blue'] },
  G: { x: 0, y: 1, zones: ['green'] },
  H: { x: 2, y: 1, zones: ['green'] },
  J: { x: 5, y: 1, zones: ['blue'] },
  K: { x: 0, y: 2, zones: ['green'] },
  L: { x: 1, y: 2, zones: ['green'] },
  M: { x: 2, y: 2, zones: ['green'] },
  P: { x: 5, y: 2, zones: ['blue'] },
};
const IDS = Object.keys(SPACES) as SpaceId[];
const EDGES: Array<[SpaceId, SpaceId]> = [
  ['A', 'B'],
  ['B', 'C'],
  ['C', 'F'],
  ['F', 'J'],
  ['J', 'P'],
  ['G', 'K'],
  ['G', 'H'],
  ['H', 'M'],
  ['H', 'C'],
  ['K', 'L'],
  ['L', 'M'],
  ['L', 'B'],
];
/** Эталон BFS-дистанций от A (по линиям) */
const DIST_FROM_A: Record<SpaceId, number> = {
  A: 0,
  B: 1,
  C: 2,
  L: 2,
  F: 3,
  H: 3,
  K: 3,
  M: 3,
  J: 4,
  G: 4,
  P: 5,
};

const at = (id: SpaceId): Position => ({ x: SPACES[id].x, y: SPACES[id].y });
const key = (p: Position) => `${p.x}:${p.y}`;
const idAt = (p: Position): string =>
  IDS.find((id) => SPACES[id].x === p.x && SPACES[id].y === p.y) ?? `#${key(p)}`;
const ids = (ps: readonly Position[]) => ps.map(idAt);
const sortedIds = (ps: readonly Position[]) => ids(ps).sort();

/**
 * Доска по контракту: каждая позиция решётки — явная клетка; пространства
 * несут zones/spaceId/links (обе стороны связи), остальное — obstacle.
 */
function topologyBoard(patch?: (cell: Cell) => Cell): BoardState {
  const links = new Map<SpaceId, Position[]>();
  for (const [u, v] of EDGES) {
    links.set(u, [...(links.get(u) ?? []), at(v)]);
    links.set(v, [...(links.get(v) ?? []), at(u)]);
  }
  const cells: Cell[][] = [];
  for (let y = 0; y < 3; y++) {
    const row: Cell[] = [];
    for (let x = 0; x < 6; x++) {
      const id = IDS.find((s) => SPACES[s].x === x && SPACES[s].y === y);
      const cell: Cell = id
        ? {
            type: 'normal',
            x,
            y,
            zones: [...SPACES[id].zones],
            spaceId: id,
            links: links.get(id) ?? [],
          }
        : { type: 'obstacle', x, y };
      row.push(patch ? patch(cell) : cell);
    }
    cells.push(row);
  }
  return { width: 6, height: 3, cells, doors: {}, fog: {}, tokens: {} };
}

const TOPO = topologyBoard();

function fighter(
  id: string,
  ownerId: string,
  pos: Position,
  extra: Partial<Fighter> = {},
): Fighter {
  return {
    id,
    ownerId,
    heroId: ownerId,
    name: id,
    type: FighterType.HERO,
    health: 10,
    maxHealth: 10,
    position: pos,
    effects: [],
    hasSidekick: false,
    movement: 2,
    ...extra,
  };
}

/**
 * s03-фикстура (игроки a/b, бойцы a, b, helper) на топологической доске:
 * бойцы расставлены по id пространств; null — боец убирается со стола.
 */
function topoState(
  place: Partial<Record<'a' | 'b' | 'helper', SpaceId | null>>,
  opts: { hand?: number; patch?: (f: Fighter) => Fighter; board?: BoardState } = {},
): GameState {
  const base = s03Fixture(opts.hand ?? 1);
  const defaults: Record<string, SpaceId | null> = { a: 'A', b: 'P', helper: null };
  const fighters = base.fighters
    .map((f) => {
      const where = f.id in place ? place[f.id as 'a' | 'b' | 'helper'] : defaults[f.id];
      return where ? { ...f, position: at(where) } : null;
    })
    .filter((f): f is Fighter => f !== null)
    .map((f) => (opts.patch ? opts.patch(f) : f));
  return { ...base, boardState: opts.board ?? TOPO, fighters };
}

const context = (state: GameState, userId = 'a') => ({
  gameId: state.gameId,
  userId,
  currentState: state,
});

// ============================================================================
// 1. Чистый модуль board-topology
// ============================================================================

describe('board-topology: graph rules on a synthetic original-map board', () => {
  it('detects topology only when a cell carries links', () => {
    expect(hasTopology(TOPO)).toBe(true);
    expect(hasTopology(createEmptyBoardState(6, 4))).toBe(false);
    expect(hasTopology(undefined)).toBe(false);
    // Даже пустой массив links у одной клетки включает режим графа
    const one = createEmptyBoardState(2, 1);
    const withEmptyLinks = {
      ...one,
      cells: [[{ ...one.cells[0][0], links: [] }, one.cells[0][1]]],
    };
    expect(hasTopology(withEmptyLinks)).toBe(true);
    expect(neighbours(withEmptyLinks, { x: 0, y: 0 })).toEqual([]);
  });

  it('every lattice position is explicit; non-spaces are impassable obstacles', () => {
    const flat = TOPO.cells.flat();
    expect(flat).toHaveLength(18);
    expect(
      flat
        .filter((c) => c.spaceId)
        .map((c) => c.spaceId)
        .sort(),
    ).toEqual([...IDS].sort());
    for (const c of flat.filter((c) => !c.spaceId)) expect(isCellPassable(c)).toBe(false);
  });

  it('neighbours are exactly the links, in declared order', () => {
    expect(ids(neighbours(TOPO, at('A')))).toEqual(['B']);
    expect(ids(neighbours(TOPO, at('G')))).toEqual(['K', 'H']);
    expect(ids(neighbours(TOPO, at('B')))).toEqual(['A', 'C', 'L']);
    expect(ids(neighbours(TOPO, at('C')))).toEqual(['B', 'F', 'H']);
    // obstacle-позиция на пересечении линий — ни с кем не связана
    expect(neighbours(TOPO, { x: 1, y: 1 })).toEqual([]);
  });

  it('a lattice neighbour that is NOT linked is not adjacent', () => {
    expect(isAdjacent(TOPO, at('A'), at('G'))).toBe(false);
    expect(isAdjacent(TOPO, at('A'), at('B'))).toBe(true);
  });

  it('a long link spanning 3 lattice steps is adjacency (distance 1)', () => {
    expect(isAdjacent(TOPO, at('C'), at('F'))).toBe(true);
    expect(graphDistance(TOPO, at('C'), at('F'))).toBe(1);
    expect(boardDistance(TOPO, at('C'), at('F'))).toBe(1);
  });

  it('lines crossing without a junction stay independent', () => {
    expect(isAdjacent(TOPO, at('G'), at('H'))).toBe(true);
    expect(isAdjacent(TOPO, at('B'), at('L'))).toBe(true);
    for (const [u, v] of [
      ['G', 'B'],
      ['G', 'L'],
      ['H', 'B'],
      ['H', 'L'],
    ] as Array<[SpaceId, SpaceId]>) {
      expect(isAdjacent(TOPO, at(u), at(v))).toBe(false);
    }
    expect(graphDistance(TOPO, at('G'), at('B'))).toBe(3);
  });

  it('adjacency is symmetric and matches the edge list exactly', () => {
    const edgeSet = new Set(EDGES.flatMap(([u, v]) => [`${u}${v}`, `${v}${u}`]));
    for (const u of IDS) {
      expect(isAdjacent(TOPO, at(u), at(u))).toBe(false);
      for (const v of IDS) {
        if (u === v) continue;
        expect(isAdjacent(TOPO, at(u), at(v))).toBe(edgeSet.has(`${u}${v}`));
      }
    }
  });

  it('graph distances are BFS over links (not manhattan)', () => {
    for (const id of IDS) {
      expect(graphDistance(TOPO, at('A'), at(id))).toBe(DIST_FROM_A[id]);
      expect(boardDistance(TOPO, at('A'), at(id))).toBe(DIST_FROM_A[id]);
      expect(distanceField(TOPO, at('A'))(at(id))).toBe(DIST_FROM_A[id]);
    }
    expect(isWithinDistance(TOPO, at('A'), at('G'), 1)).toBe(false); // манхэттен 1, по линиям 4
    expect(isWithinDistance(TOPO, at('B'), at('F'), 2)).toBe(true); // манхэттен 4, по линиям 2
  });

  it('passable filter and disconnected spaces', () => {
    // A связана только с B: без B до C не добраться
    expect(graphDistance(TOPO, at('A'), at('C'), (p) => key(p) !== key(at('B')))).toBe(Infinity);
    // изолированное пространство (без links) на топологической доске недостижимо
    const isolated = topologyBoard((c) =>
      c.x === 4 && c.y === 2 ? { type: 'normal', x: 4, y: 2, links: [] } : c,
    );
    expect(graphDistance(isolated, at('A'), { x: 4, y: 2 })).toBe(Infinity);
    expect(distanceField(isolated, { x: 4, y: 2 })(at('A'))).toBe(Infinity);
  });

  it('one-sided link declarations are symmetrised; out-of-board and self links ignored', () => {
    const b = createEmptyBoardState(3, 1);
    const board: BoardState = {
      ...b,
      cells: [
        [
          {
            ...b.cells[0][0],
            links: [
              { x: 2, y: 0 },
              { x: 0, y: 0 },
              { x: 9, y: 0 },
            ],
          },
          { ...b.cells[0][1] },
          { ...b.cells[0][2] },
        ],
      ],
    };
    expect(isAdjacent(board, { x: 2, y: 0 }, { x: 0, y: 0 })).toBe(true);
    expect(neighbours(board, { x: 0, y: 0 })).toEqual([{ x: 2, y: 0 }]);
    expect(neighbours(board, { x: 1, y: 0 })).toEqual([]); // решёточный сосед, но связи нет
  });
});

// ============================================================================
// 2. AdjacencyService (обёртки)
// ============================================================================

describe('AdjacencyService on a topology board', () => {
  const adjacency = new AdjacencyService();

  it('getAdjacentCells returns linked cells only (diagonal option ignored)', () => {
    expect(adjacency.getAdjacentCells(TOPO, at('A')).map((c) => idAt(c.position))).toEqual(['B']);
    const g = adjacency.getAdjacentCells(TOPO, at('G'), { includeDiagonal: true });
    expect(g.map((c) => idAt(c.position))).toEqual(['K', 'H']);
    expect(g.every((c) => c.cost === 1 && !c.isBlocked)).toBe(true);
  });

  it('getReachableCells walks the graph, blockedPositions cut it', () => {
    const r = adjacency.getReachableCells(TOPO, at('A'), 2);
    expect([...r.values()].map((v) => idAt(v.position)).sort()).toEqual(['B', 'C', 'L']);
    expect(r.get(key(at('C')))!.cost).toBe(2);
    const blocked = adjacency.getReachableCells(TOPO, at('A'), 5, {
      blockedPositions: new Set([key(at('B'))]),
    });
    expect(blocked.size).toBe(0);
    // «дыра» решётки как 'normal' без связей всё равно недостижима
    const holey = topologyBoard((c) =>
      c.x === 1 && c.y === 1 ? { type: 'normal', x: 1, y: 1 } : c,
    );
    const fromG = adjacency.getReachableCells(holey, at('G'), 6);
    expect(fromG.has('1:1')).toBe(false);
    expect(fromG.size).toBe(IDS.length - 1);
  });

  it('isAdjacent / boardDistance / isInSameZone read the state board', async () => {
    const state = { boardState: TOPO };
    await expect(adjacency.isAdjacent(state, at('A'), at('G'))).resolves.toBe(false);
    await expect(adjacency.isAdjacent(state, at('C'), at('F'))).resolves.toBe(true);
    expect(adjacency.boardDistance(state, at('A'), at('P'))).toBe(5);
    // мультизонность: C (red+blue) делит зону и с A (red), и с J (blue)
    expect(adjacency.isInSameZone(state, at('C'), at('A'))).toBe(true);
    expect(adjacency.isInSameZone(state, at('C'), at('J'))).toBe(true);
    expect(adjacency.isInSameZone(state, at('A'), at('J'))).toBe(false);
    // без доски — прежний манхэттен
    await expect(adjacency.isAdjacent(null, { x: 0, y: 0 }, { x: 0, y: 1 })).resolves.toBe(true);
  });
});

// ============================================================================
// 3. Движение: валидатор, MovementService, A*, production executor
// ============================================================================

describe('movement on a topology board', () => {
  const validator = new GameRulesValidator(new AdjacencyService());

  it('validateMovement: reach by links within movement, unlinked lattice neighbour unreachable', () => {
    const s = topoState({ a: 'A', b: 'P' });
    for (const id of ['B', 'C', 'L'] as SpaceId[]) {
      expect(validator.validateMovement(s, 'a', at(id), 'a')).toEqual({ valid: true });
    }
    expect(validator.validateMovement(s, 'a', at('G'), 'a').code).toBe('NOT_ENOUGH_MOVEMENT');
    expect(validator.validateMovement(s, 'a', at('F'), 'a').code).toBe('NOT_ENOUGH_MOVEMENT');
    expect(validator.validateMovement(s, 'a', { x: 1, y: 1 }, 'a').code).toBe('INVALID_POSITION');
  });

  it('validateMovement: allies passable, enemies block, occupied end forbidden', () => {
    const ally = topoState({ a: 'A', helper: 'B', b: 'P' });
    expect(validator.validateMovement(ally, 'a', at('C'), 'a')).toEqual({ valid: true });
    expect(validator.validateMovement(ally, 'a', at('B'), 'a').code).toBe('POSITION_OCCUPIED');
    const enemy = topoState({ a: 'A', b: 'B' });
    expect(validator.validateMovement(enemy, 'a', at('C'), 'a').code).toBe('NOT_ENOUGH_MOVEMENT');
    expect(validator.validateMovement(enemy, 'a', at('L'), 'a').code).toBe('NOT_ENOUGH_MOVEMENT');
  });

  it('validateManeuver: steps must follow links (long link ok, lattice/crossing jumps rejected)', () => {
    const fromA = topoState({ a: 'A', b: 'P' });
    expect(validator.validateManeuver(fromA, 'a', undefined, [at('G')], 'a').code).toBe(
      'INVALID_STEP',
    );
    expect(validator.validateManeuver(fromA, 'a', undefined, [at('B'), at('C')], 'a')).toEqual({
      valid: true,
    });
    const fromC = topoState({ a: 'C', b: 'P' });
    expect(validator.validateManeuver(fromC, 'a', undefined, [at('F'), at('J')], 'a')).toEqual({
      valid: true,
    });
    const fromG = topoState({ a: 'G', b: 'P' });
    expect(validator.validateManeuver(fromG, 'a', undefined, [at('B')], 'a').code).toBe(
      'INVALID_STEP',
    );
    expect(validator.validateManeuver(fromG, 'a', undefined, [at('L')], 'a').code).toBe(
      'INVALID_STEP',
    );
    expect(validator.validateManeuver(fromG, 'a', undefined, [{ x: 1, y: 1 }], 'a').code).toBe(
      'INVALID_POSITION',
    );
    expect(validator.validateManeuver(fromG, 'a', undefined, [at('H'), at('C')], 'a')).toEqual({
      valid: true,
    });
  });

  it('validateManeuver: GD-015 occupancy on the graph', () => {
    const enemyMid = topoState({ a: 'A', b: 'B' });
    expect(validator.validateManeuver(enemyMid, 'a', undefined, [at('B'), at('C')], 'a').code).toBe(
      'PATH_BLOCKED_BY_ENEMY',
    );
    const allyMid = topoState({ a: 'A', helper: 'B', b: 'P' });
    expect(validator.validateManeuver(allyMid, 'a', undefined, [at('B'), at('C')], 'a')).toEqual({
      valid: true,
    });
    const allyEnd = topoState({ a: 'A', helper: 'C', b: 'P' });
    expect(validator.validateManeuver(allyEnd, 'a', undefined, [at('B'), at('C')], 'a').code).toBe(
      'POSITION_OCCUPIED',
    );
  });

  it('MovementService: targets and executed steps follow links', async () => {
    const movement = new MovementService(new AStarService(), new PathCacheService());
    const s = topoState({ a: 'A', helper: 'B', b: 'L' });
    // союзник на B проходим, но конечной клеткой быть не может; враг на L — нет
    expect(sortedIds(movement.getValidMoveTargets(s, 'a', 2))).toEqual(['C']);
    expect((await movement.executeMovement(s, 'a', [at('B'), at('C')])).success).toBe(true);
    const lattice = await movement.executeMovement(topoState({ a: 'A' }), 'a', [at('G')]);
    expect(lattice.success).toBe(false);
    const long = await movement.executeMovement(topoState({ a: 'C' }), 'a', [at('F')]);
    expect(long.success).toBe(true);
    expect(long.nextState!.fighters.find((f) => f.id === 'a')!.position).toEqual(at('F'));
  });

  describe('A* on the graph', () => {
    const astar = new AStarService();
    const empty = (): GameState => ({ ...topoState({}), fighters: [] });

    it('finds the shortest path along links', () => {
      const r = astar.findPath(empty(), 'x', at('A'), at('F'), 10);
      expect(r.exists).toBe(true);
      expect(r.cost).toBe(3);
      expect(ids(r.path)).toEqual(['A', 'B', 'C', 'F']);
    });

    it('cost equals graph distance for every pair (heuristic admissible despite long links)', () => {
      const state = empty();
      for (const u of IDS) {
        for (const v of IDS) {
          const r = astar.findPath(state, 'x', at(u), at(v), 20);
          expect(r.exists).toBe(true);
          expect(r.cost).toBe(graphDistance(TOPO, at(u), at(v)));
          // каждый шаг пути — по связи, пересечение (1,1) не используется
          for (let i = 1; i < r.path.length; i++)
            expect(isAdjacent(TOPO, r.path[i - 1], r.path[i])).toBe(true);
          expect(r.path.some((p) => key(p) === '1:1')).toBe(false);
        }
      }
    });

    it('respects maxCost, enemies, allies and occupied endpoints', () => {
      expect(astar.findPath(empty(), 'x', at('A'), at('P'), 4).exists).toBe(false);
      expect(astar.findPath(empty(), 'x', at('A'), at('P'), 5).exists).toBe(true);
      // C — единственный проход к F
      const enemyOnC = topoState({ a: 'A', b: 'C' });
      expect(astar.findPath(enemyOnC, 'a', at('A'), at('F'), 10).exists).toBe(false);
      const allyOnC = topoState({ a: 'A', helper: 'C', b: 'P' });
      expect(astar.findPath(allyOnC, 'a', at('A'), at('F'), 10).cost).toBe(3);
      expect(astar.findPath(allyOnC, 'a', at('A'), at('C'), 10).exists).toBe(false);
    });

    it('statically unreachable target is not found', () => {
      const isolated = topologyBoard((c) =>
        c.x === 4 && c.y === 2 ? { type: 'normal', x: 4, y: 2, links: [] } : c,
      );
      const state = { ...topoState({}, { board: isolated }), fighters: [] };
      expect(astar.findPath(state, 'x', at('A'), { x: 4, y: 2 }, 50).exists).toBe(false);
    });
  });

  describe('maneuver via production executor', () => {
    let service: ReturnType<typeof s03Engine>['executor'];
    beforeEach(() => {
      service = s03Engine().executor;
    });

    async function maneuver(state: GameState, path: Position[]) {
      const begun = await service.executeBeginManeuver(
        { gameId: state.gameId, expectedSequenceNumber: state.sequenceNumber },
        context(state),
      );
      expect(begun.success).toBe(true);
      const pending = begun.gameState;
      const dto: ManeuverDto = {
        gameId: state.gameId,
        maneuverId: pending.metadata.pendingManeuver!.id,
        moves: [{ fighterId: 'a', path }],
      };
      return service.executeManeuver(dto, context(pending));
    }

    it('moves along a long link and rejects an unlinked lattice step', async () => {
      const ok = await maneuver(topoState({ a: 'C', b: 'A' }), [at('F'), at('J')]);
      expect(ok.success).toBe(true);
      expect(ok.gameState!.fighters.find((f) => f.id === 'a')!.position).toEqual(at('J'));
      const bad = await maneuver(topoState({ a: 'A', b: 'P' }), [at('G')]);
      expect(bad.success).toBe(false);
    });
  });
});

// ============================================================================
// 4. Атака: смежность по связям, ranged по зонам, дальность по линиям
// ============================================================================

describe('attack range on a topology board (production executor)', () => {
  let engine: ReturnType<typeof s03Engine>;
  beforeEach(() => {
    engine = s03Engine();
  });

  const attack = (state: GameState) => {
    const dto: AttackDto = { gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'h0' };
    return engine.executor.executeAttack(dto, context(state));
  };
  const as = (attackType: 'melee' | 'ranged', a: SpaceId, b: SpaceId) =>
    topoState({ a, b }, { patch: (f) => (f.id === 'a' ? { ...f, attackType } : f) });

  it('melee: linked target (incl. long link) only', async () => {
    expect((await attack(as('melee', 'C', 'F'))).success).toBe(true);
    expect((await attack(as('melee', 'A', 'B'))).success).toBe(true);
    // решёточный сосед без связи
    expect((await attack(as('melee', 'A', 'G'))).success).toBe(false);
    // общая зона melee не помогает
    expect((await attack(as('melee', 'C', 'J'))).success).toBe(false);
  });

  it('ranged: adjacent OR shares at least one zone (multi-zone spaces are in all their zones)', async () => {
    expect((await attack(as('ranged', 'A', 'C'))).success).toBe(true); // red
    expect((await attack(as('ranged', 'J', 'C'))).success).toBe(true); // blue
    expect((await attack(as('ranged', 'C', 'P'))).success).toBe(true); // blue
    expect((await attack(as('ranged', 'H', 'A'))).success).toBe(false); // green vs red, not linked
    expect((await attack(as('ranged', 'A', 'G'))).success).toBe(false); // manhattan 1, но не связь и зоны разные
    expect((await attack(as('ranged', 'A', 'F'))).success).toBe(false);
    expect((await attack(as('ranged', 'M', 'C'))).success).toBe(false); // green vs red/blue, not linked
    expect((await attack(as('ranged', 'H', 'C'))).success).toBe(true); // связь H-C
  });

  it('extended range abilities receive the graph distance', async () => {
    const seen: number[] = [];
    const handler: ExtendedHeroAbilityHandler = {
      heroId: 'a',
      abilityName: 'reach',
      abilityDescription: 'attack up to 2 spaces',
      canAttackAtRange: (_a: string, _d: string, range: number) => {
        seen.push(range);
        return range <= 2;
      },
    };
    engine.registry.registerExtended(handler);
    // A→L: манхэттен 3, по линиям 2 (A-B-L)
    expect((await attack(as('melee', 'A', 'L'))).success).toBe(true);
    // A→F: манхэттен 5, по линиям 3
    expect((await attack(as('melee', 'A', 'F'))).success).toBe(false);
    expect(seen).toEqual([2, 3]);
  });

  it('validateAttack (legacy validator entry) uses board distance', () => {
    const validator = new GameRulesValidator(new AdjacencyService());
    const s = (a: SpaceId, b: SpaceId) => ({
      ...topoState({ a, b }),
      phase: GamePhase.ACTION_ATTACK,
    });
    const act = { attackerId: 'a', targetId: 'b', cardId: 'h0' };
    expect(validator.validateAttack(s('C', 'F'), act)).toEqual({ valid: true });
    expect(validator.validateAttack(s('A', 'G'), act).code).toBe('OUT_OF_RANGE');
  });
});

// ============================================================================
// 5. AI: соседи и дистанции по графу
// ============================================================================

describe('AI decisions on a topology board', () => {
  const ai = new AiDecisionService(new AdjacencyService());
  const validator = new GameRulesValidator(new AdjacencyService());
  const attackHand = (state: GameState): GameState => ({
    ...state,
    currentTurnPlayerId: 'b',
    handZones: {
      ...state.handZones,
      b: {
        cards: [
          {
            id: 'atk',
            cardId: 'atk',
            name: 'atk',
            cardType: CardType.ATTACK,
            attackValue: 3,
          } as any,
        ],
        maxSize: 7,
      },
    },
  });
  const pendingManeuver = (state: GameState): GameState => ({
    ...state,
    currentTurnPlayerId: 'b',
    metadata: {
      ...state.metadata,
      pendingManeuver: { id: 'm1', playerId: 'b' } as any,
      actionsRemaining: 1,
    },
  });

  it('does not attack a lattice neighbour that is not linked; attacks across a long link', () => {
    const lattice = attackHand(topoState({ a: 'A', b: 'G' }));
    expect(ai.decide(lattice, 'b')).toMatchObject({ kind: 'beginManeuver' });
    const longLink = attackHand(topoState({ a: 'F', b: 'C' }));
    expect(ai.decide(longLink, 'b')).toMatchObject({
      kind: 'attack',
      attackerId: 'b',
      targetId: 'a',
    });
  });

  it('maneuver path follows links and strictly approaches by graph distance', () => {
    const state = pendingManeuver(topoState({ a: 'A', b: 'G' }));
    const action = ai.decide(state, 'b') as any;
    expect(action).toMatchObject({ kind: 'maneuver', maneuverId: 'm1' });
    const path: Position[] = action.moves[0].path;
    // G(4) → K(3) → L(2): первый в порядке связей строгий спуск
    expect(ids(path)).toEqual(['K', 'L']);
    expect(validator.validateManeuver(state, 'b', undefined, path, 'b')).toEqual({ valid: true });
  });

  it('nearest enemy is chosen by graph distance, not manhattan', () => {
    // враг-герой a на A (манхэттен 1, по линиям 4) и враг-герой helper на M (манхэттен 3, по линиям 2)
    const state = pendingManeuver(
      topoState(
        { a: 'A', helper: 'M', b: 'G' },
        { patch: (f) => (f.id === 'helper' ? { ...f, type: FighterType.HERO } : f) },
      ),
    );
    const action = ai.decide(state, 'b') as any;
    expect(ids(action.moves[0].path)).toEqual(['H']);
  });

  it('CHOOSE_SPACE stage 2 picks among linked cells only', () => {
    const state: GameState = {
      ...topoState({ a: 'H', b: 'P' }),
      currentTurnPlayerId: 'b',
      metadata: {
        ...topoState({}).metadata,
        pendingEffects: [
          {
            id: 'cs',
            type: 'CHOOSE_SPACE',
            playerId: 'b',
            stage: 2,
            anchor: at('G'),
            text: 't',
          } as any,
        ],
      },
    };
    const action = ai.decide(state, 'b') as any;
    expect(action.kind).toBe('resolveSpace');
    // G связан с K и H; враг на H → максимум целей
    expect(idAt({ x: action.x, y: action.y })).toBe('H');
  });
});

// ============================================================================
// 6. Эффекты карт и способности героев
// ============================================================================

describe('card effects and hero abilities on a topology board', () => {
  const damageAdjacent: CardEffect = {
    id: 'dmg',
    type: EffectType.DAMAGE,
    timing: EffectTiming.ON_PLAY,
    value: 1,
    target: EffectTarget.ENEMIES_ADJACENT_TO_SELF,
  } as CardEffect;
  const scheme: Card = {
    id: 'sch',
    cardId: 'sch',
    name: 'sch',
    nameEn: 'sch',
    nameRu: 'sch',
    cardType: CardType.SCHEME,
    effects: [damageAdjacent],
  } as Card;
  const healthOf = (s: GameState, id: string) => s.fighters.find((f) => f.id === id)!.health;

  it('ENEMIES_ADJACENT_TO_SELF uses links', async () => {
    const { effects } = s03Engine();
    const lattice = await effects.executeOnPlayEffects(topoState({ a: 'A', b: 'G' }), scheme, 'a');
    expect(healthOf(lattice.state, 'b')).toBe(10);
    const linked = await effects.executeOnPlayEffects(topoState({ a: 'A', b: 'B' }), scheme, 'a');
    expect(healthOf(linked.state, 'b')).toBe(9);
    const longLink = await effects.executeOnPlayEffects(topoState({ a: 'C', b: 'F' }), scheme, 'a');
    expect(healthOf(longLink.state, 'b')).toBe(9);
  });

  it("generic turn-damage 'enemy-adjacent' (Dracula) uses links", async () => {
    const config = ABILITY_CONFIGS.find((c) => c.heroId === 'dracula')!;
    const deck = { drawCards: jest.fn(async (s: GameState) => s) };
    const handler = new GenericHeroAbilityHandler(config, { deck, zone: new AdjacencyService() });
    const state = (enemyAt: SpaceId): GameState => ({
      ...topoState({ a: 'A', b: enemyAt }),
      fighters: [
        fighter('a', 'a', at('A'), { heroSlug: 'dracula' }),
        fighter('b', 'b', at(enemyAt)),
      ],
    });
    const unlinked = state('G');
    expect(await handler.onTurnStart(unlinked, 'a')).toBe(unlinked);
    const next = await handler.onTurnStart(state('B'), 'a');
    expect(healthOf(next, 'b')).toBe(9);
  });

  it('Ms. Marvel legacy handler measures range and turn-start step on the graph', async () => {
    const handler = new MsMarvelHandler();
    const state = (msAt: SpaceId, enemyAt: SpaceId): GameState => ({
      ...topoState({}),
      players: [
        {
          userId: 'a',
          heroId: 'ms-marvel',
          health: 10,
          maxHealth: 10,
          fighterIds: ['a'],
          isAlive: true,
        } as any,
      ],
      fighters: [
        fighter('a', 'a', at(msAt), { heroId: 'ms-marvel' }),
        fighter('b', 'b', at(enemyAt)),
      ],
    });
    expect(handler.canAttackTarget(state('A', 'C'), 'a', 'b')).toBe(true); // 2 по линиям
    expect(handler.canAttackTarget(state('B', 'F'), 'a', 'b')).toBe(true); // манхэттен 4, по линиям 2
    expect(handler.canAttackTarget(state('A', 'P'), 'a', 'b')).toBe(false); // по линиям 5 > 2
    expect(handler.canAttackTarget(state('G', 'B'), 'a', 'b')).toBe(false); // манхэттен 2, по линиям 3
    expect(sortedIds(handler.getAvailableTurnStartPositions(state('B', 'C'), 'a'))).toEqual([
      'A',
      'L',
    ]);
    const moved = await handler.executeTurnStartMove(state('C', 'P'), 'a', at('F'));
    expect(moved.fighters[0].position).toEqual(at('F'));
    const refused = await handler.executeTurnStartMove(state('A', 'P'), 'a', at('G'));
    expect(refused.fighters[0].position).toEqual(at('A'));
  });
});

// ============================================================================
// 7. Регрессия: сеточные доски (Cobble City, без links) — бит-в-бит как раньше
// ============================================================================

/** Копия ПРЕЖНЕЙ AdjacencyService.getAdjacentCells (до board-topology) */
function legacyAdjacentCells(board: BoardState, pos: Position, includeDiagonal = false) {
  const orth = [
    { dx: 0, dy: -1, direction: 'north' },
    { dx: 0, dy: 1, direction: 'south' },
    { dx: 1, dy: 0, direction: 'east' },
    { dx: -1, dy: 0, direction: 'west' },
  ];
  const diag = [
    { dx: 1, dy: -1, direction: 'northeast' },
    { dx: -1, dy: -1, direction: 'northwest' },
    { dx: 1, dy: 1, direction: 'southeast' },
    { dx: -1, dy: 1, direction: 'southwest' },
  ];
  const out: Array<{ position: Position; direction: string; cost: number; isBlocked: boolean }> =
    [];
  for (const { dx, dy, direction } of includeDiagonal ? [...orth, ...diag] : orth) {
    const p = { x: pos.x + dx, y: pos.y + dy };
    if (p.x < 0 || p.x >= board.width || p.y < 0 || p.y >= board.height) continue;
    const cell = board.cells[p.y]?.[p.x];
    if (!cell) continue;
    const isBlocked =
      cell.type === 'wall' || cell.type === 'obstacle' || (cell.type === 'door' && !cell.isOpen);
    out.push({
      position: p,
      direction,
      cost: includeDiagonal && dx !== 0 && dy !== 0 ? 1.5 : 1,
      isBlocked,
    });
  }
  return out;
}

/** Копия ПРЕЖНЕЙ getReachableCells */
function legacyReachable(
  board: BoardState,
  start: Position,
  maxCost: number,
  blocked?: ReadonlySet<string>,
) {
  const reachable = new Map<string, { position: Position; cost: number }>();
  const visited = new Set<string>([key(start)]);
  const queue = [{ position: start, cost: 0 }];
  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current.cost > 0) reachable.set(key(current.position), current);
    if (current.cost >= maxCost) continue;
    for (const cell of legacyAdjacentCells(board, current.position)) {
      if (cell.isBlocked || blocked?.has(key(cell.position))) continue;
      if (visited.has(key(cell.position))) continue;
      visited.add(key(cell.position));
      queue.push({ position: cell.position, cost: current.cost + cell.cost });
    }
  }
  return reachable;
}

/** Копия ПРЕЖНЕЙ MovementService.getValidMoveTargets */
function legacyValidMoveTargets(state: GameState, fighterId: string, maxCost: number): Position[] {
  const fighter = state.fighters.find((f) => f.id === fighterId);
  if (!fighter || maxCost < 1) return [];
  const targets: Position[] = [];
  const visited = new Set<string>([key(fighter.position)]);
  const queue = [{ position: fighter.position, cost: 0 }];
  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current.cost >= maxCost) continue;
    const p = current.position;
    for (const n of [
      { x: p.x, y: p.y - 1 },
      { x: p.x + 1, y: p.y },
      { x: p.x, y: p.y + 1 },
      { x: p.x - 1, y: p.y },
    ]) {
      if (visited.has(key(n))) continue;
      const cell = state.boardState.cells[n.y]?.[n.x];
      if (!cell || !isCellPassable(cell)) continue;
      if (!isTraversable(state, fighterId, n)) continue;
      visited.add(key(n));
      queue.push({ position: n, cost: current.cost + 1 });
      if (isFreeEndpoint(state, fighterId, n)) targets.push(n);
    }
  }
  return targets;
}

/** Копия ПРЕЖНЕГО AStarService.findPath (манхэттен-эвристика, N/E/S/W) */
function legacyAStar(
  state: any,
  fighterId: string,
  start: Position,
  end: Position,
  maxCost: number,
) {
  const none = { path: [] as Position[], cost: 0, exists: false };
  if (!isInBoardBounds(state?.boardState, start) || !isInBoardBounds(state?.boardState, end))
    return none;
  if (!isCellPassable(state?.boardState?.cells?.[start.y]?.[start.x])) return none;
  if (!isCellPassable(state?.boardState?.cells?.[end.y]?.[end.x])) return none;
  if (!isFreeEndpoint(state, fighterId, end)) return none;
  const h = (p: Position) => Math.abs(p.x - end.x) + Math.abs(p.y - end.y);
  type N = { pos: Position; g: number; h: number; f: number };
  const open: N[] = [{ pos: start, g: 0, h: h(start), f: h(start) }];
  const closed = new Set<string>();
  const cameFrom = new Map<string, Position>();
  while (open.length > 0) {
    open.sort((a, b) => a.f - b.f);
    const cur = open.shift()!;
    if (cur.g > maxCost) continue;
    if (cur.pos.x === end.x && cur.pos.y === end.y) {
      const path = [cur.pos];
      let k = key(cur.pos);
      while (cameFrom.has(k)) {
        const p = cameFrom.get(k)!;
        path.unshift(p);
        k = key(p);
      }
      return { path, cost: cur.g, exists: true };
    }
    closed.add(key(cur.pos));
    const p = cur.pos;
    for (const n of [
      { x: p.x, y: p.y - 1 },
      { x: p.x + 1, y: p.y },
      { x: p.x, y: p.y + 1 },
      { x: p.x - 1, y: p.y },
    ]) {
      if (!isInBoardBounds(state?.boardState, n)) continue;
      if (!isCellPassable(state?.boardState?.cells?.[n.y]?.[n.x])) continue;
      if (!isTraversable(state, fighterId, n)) continue;
      if (closed.has(key(n))) continue;
      const g = cur.g + 1;
      const existing = open.find((o) => o.pos.x === n.x && o.pos.y === n.y);
      if (!existing) {
        open.push({ pos: n, g, h: h(n), f: g + h(n) });
        cameFrom.set(key(n), cur.pos);
      } else if (g < existing.g) {
        existing.g = g;
        existing.f = g + existing.h;
        cameFrom.set(key(n), cur.pos);
      }
    }
  }
  return none;
}

describe('grid regression: boards without links behave exactly as before', () => {
  const root = resolve(__dirname, '../../../..');
  const cobble: BoardState = JSON.parse(
    readFileSync(resolve(root, 'docs/game-design/evidence/S01/duel-start-p1.json'), 'utf8'),
  ).boardState;
  // Cobble с препятствиями: стена, закрытая и открытая двери, «дыра» в cells
  const cobbleWalled: BoardState = {
    ...cobble,
    cells: cobble.cells.map((row, y) =>
      row.map((c, x) => {
        if (x === 2 && y === 2) return { ...c, type: 'wall' as const };
        if (x === 1 && y === 3) return { ...c, type: 'door' as const, isOpen: false };
        if (x === 3 && y === 1) return { ...c, type: 'door' as const, isOpen: true };
        if (x === 4 && y === 4) return undefined as unknown as Cell;
        return c;
      }),
    ),
  };
  const boards: Array<[string, BoardState]> = [
    ['cobble', cobble],
    ['cobble-walled', cobbleWalled],
  ];
  const all = (b: BoardState): Position[] =>
    Array.from({ length: b.height }, (_, y) =>
      Array.from({ length: b.width }, (_, x) => ({ x, y })),
    ).flat();

  it('Cobble capture is a grid board (no links anywhere)', () => {
    expect(cobble.width * cobble.height).toBe(30);
    expect(hasTopology(cobble)).toBe(false);
    expect(hasTopology(cobbleWalled)).toBe(false);
  });

  it.each(boards)(
    '%s: getAdjacentCells identical to legacy (order, direction, cost, blocking)',
    (_n, board) => {
      const adjacency = new AdjacencyService();
      for (const p of all(board)) {
        for (const includeDiagonal of [false, true]) {
          expect(adjacency.getAdjacentCells(board, p, { includeDiagonal })).toEqual(
            legacyAdjacentCells(board, p, includeDiagonal),
          );
        }
        // neighbours() не проверяет существование клетки (это делают вызывающие)
        const existing = neighbours(board, p, ORTHOGONAL_NSEW).filter(
          (q) => board.cells[q.y]?.[q.x],
        );
        expect(existing).toEqual(legacyAdjacentCells(board, p).map((c) => c.position));
      }
    },
  );

  it.each(boards)(
    '%s: getReachableCells identical to legacy for every start and budget',
    (_n, board) => {
      const adjacency = new AdjacencyService();
      const blocked = new Set(['1:1', '3:4']);
      for (const p of all(board)) {
        for (const maxCost of [1, 2, 3, 5]) {
          expect([...adjacency.getReachableCells(board, p, maxCost).entries()]).toEqual([
            ...legacyReachable(board, p, maxCost).entries(),
          ]);
          expect([
            ...adjacency
              .getReachableCells(board, p, maxCost, { blockedPositions: blocked })
              .entries(),
          ]).toEqual([...legacyReachable(board, p, maxCost, blocked).entries()]);
        }
      }
    },
  );

  it.each(boards)('%s: adjacency and distance are manhattan for every pair', async (_n, board) => {
    const adjacency = new AdjacencyService();
    const state = { boardState: board };
    for (const a of all(board)) {
      for (const b of all(board)) {
        const m = Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
        expect(isAdjacent(board, a, b)).toBe(m === 1);
        await expect(adjacency.isAdjacent(state, a, b)).resolves.toBe(m === 1);
        expect(boardDistance(board, a, b)).toBe(m);
        expect(adjacency.boardDistance(state, a, b)).toBe(m);
        expect(distanceField(board, b)(a)).toBe(m);
      }
    }
  });

  it.each(boards)('%s: A* path/cost and move targets identical to legacy', (_n, board) => {
    const astar = new AStarService();
    const movement = new MovementService(astar, new PathCacheService());
    const state: GameState = {
      ...s03Fixture(0),
      boardState: board,
      fighters: [
        fighter('a', 'a', { x: 0, y: 0 }, { movement: 3 }),
        fighter('ally', 'a', { x: 1, y: 2 }),
        fighter('enemy', 'b', { x: 3, y: 2 }),
      ],
    };
    for (const end of all(board)) {
      for (const maxCost of [3, 10]) {
        expect(astar.findPath(state, 'a', { x: 0, y: 0 }, end, maxCost)).toEqual(
          legacyAStar(state, 'a', { x: 0, y: 0 }, end, maxCost),
        );
      }
    }
    for (const budget of [1, 2, 3, 4]) {
      expect(movement.getValidMoveTargets(state, 'a', budget)).toEqual(
        legacyValidMoveTargets(state, 'a', budget),
      );
    }
  });
});
