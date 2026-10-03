/**
 * MS-T-02 — canonical reachability and path of a fighter move
 * (docs/game-design/move-selection/04-technical-design.md §3.1, §3.2).
 *
 * ONE rule function for the server side of move selection. The UE client
 * mirrors it in FS08BoardModel (MS-T-03); parity is held by the golden
 * fixtures in backend/prisma/fixtures/movement (MS-R-41) and the property
 * test movement/move-parity.property.spec.ts (MS-R-42).
 *
 * Rules of one step (02 §2, GD-015, the same as movement/traversal.ts):
 *  - neighbours: board-topology.neighbours — the (symmetrised) links on a
 *    topology board, the 4 orthogonal cells on a grid;
 *  - a step may enter a cell that exists, is in bounds and is not a wall,
 *    obstacle or closed door (traversal.isCellPassable);
 *  - a living ENEMY of the mover (another owner, isLivingFighter) blocks the
 *    step unless `passThroughEnemies` (Winged Frenzy); living allies do not;
 *  - a defeated fighter (health <= 0 or isDefeated) blocks nothing;
 *  - the move may END on the start ("stay": no entry in moves[]) or on a cell
 *    without any other living fighter (traversal.isFreeEndpoint).
 *
 * Canonical path: BFS distances do not depend on the neighbour order; the
 * predecessor of every path cell is the neighbour one step closer to the
 * start with the smallest key K = (spaceId, y, x) on a topology board and
 * K = (y, x) on a grid. spaceId compares ordinally (UTF-16 code units, case
 * sensitive — FString::Compare(…, ESearchCase::CaseSensitive) in UE).
 * The resulting path does not depend on the order of `links` either.
 *
 * `parent` in ReachMap is the BFS discovery parent and is NOT normative (it
 * depends on the neighbour order); only `dist` and canonicalPath are.
 *
 * The step limit compares with `>=`, exactly like the legacy
 * AdjacencyService.getReachableCells: cells up to `maxSteps` steps away are
 * reached, Infinity means "no limit" (cue fallback, 04 §4.6).
 */

import type { Fighter, Position } from '../models';
import { getFighterMovement } from '../models';
import { hasTopology, isInBounds, neighbours, posKey } from '../engine/board-topology';
import type { TopologyBoard } from '../engine/board-topology';
import { isCellPassable, isFreeEndpoint, isLivingFighter } from './traversal';

/** Minimal slice of GameState the movement rules read */
export interface CanonicalState {
  readonly boardState: TopologyBoard | null | undefined;
  readonly fighters: readonly Fighter[];
}

export interface ReachOptions {
  /** Living enemies do not block steps (Winged Frenzy, pending.canPassThroughEnemies). */
  readonly passThroughEnemies?: boolean;
}

export interface ReachMap {
  readonly moverId: string;
  readonly ownerId: string;
  readonly start: Position;
  readonly maxSteps: number;
  /** `x:y` → steps from the start (start = 0); BFS insertion order */
  readonly dist: ReadonlyMap<string, number>;
  /** `x:y` → BFS discovery parent key (start → null). Not normative. */
  readonly parent: ReadonlyMap<string, string | null>;
}

const samePos = (a: Position, b: Position): boolean => a.x === b.x && a.y === b.y;

/** The cell exists inside the board and its terrain lets a fighter in. */
export function isPassableSpace(board: TopologyBoard | null | undefined, p: Position): boolean {
  if (!board || !isInBounds(board, p)) return false;
  return isCellPassable(board.cells[p.y]?.[p.x]);
}

/**
 * BFS reach of `moverId` within `maxSteps` steps (04 §3.1 computeReach).
 * Throws when the mover is not in `state.fighters` (callers check first).
 * Without a board only the start is reachable (no invented grid).
 */
export function computeReach(
  state: CanonicalState,
  moverId: string,
  maxSteps: number,
  opts: ReachOptions = {},
): ReachMap {
  const mover = state.fighters.find((f) => f.id === moverId);
  if (!mover) throw new Error(`computeReach: fighter ${moverId} is not on the board`);
  const board = state.boardState;
  const start: Position = { x: mover.position.x, y: mover.position.y };
  const startKey = posKey(start);
  const dist = new Map<string, number>([[startKey, 0]]);
  const parent = new Map<string, string | null>([[startKey, null]]);
  const result: ReachMap = { moverId, ownerId: mover.ownerId, start, maxSteps, dist, parent };
  if (!board) return result;

  const enemyCells = new Set<string>(
    opts.passThroughEnemies
      ? []
      : state.fighters
          .filter((f) => f.id !== moverId && isLivingFighter(f) && f.ownerId !== mover.ownerId)
          .map((f) => posKey(f.position)),
  );

  const queue: Position[] = [start];
  for (let i = 0; i < queue.length; i++) {
    const current = queue[i];
    const currentKey = posKey(current);
    const d = dist.get(currentKey) ?? 0;
    if (d >= maxSteps) continue;
    for (const next of neighbours(board, current)) {
      const nextKey = posKey(next);
      if (dist.has(nextKey)) continue;
      if (!isPassableSpace(board, next)) continue;
      if (enemyCells.has(nextKey)) continue;
      dist.set(nextKey, d + 1);
      parent.set(nextKey, currentKey);
      queue.push(next);
    }
  }
  return result;
}

/** Steps to `p` within the reach, or undefined when it is not reached. */
export function reachDistance(reach: ReachMap, p: Position): number | undefined {
  return reach.dist.get(posKey(p));
}

/** 04 §3.1 isEndpoint: the start ("stay") or a cell without another living fighter. */
export function isEndpoint(state: CanonicalState, reach: ReachMap, p: Position): boolean {
  return samePos(p, reach.start) || isFreeEndpoint(state, reach.moverId, p);
}

/** Canonical key K of a cell: (spaceId, y, x) on a topology board, ('', y, x) on a grid. */
export function canonicalKey(
  board: TopologyBoard | null | undefined,
  p: Position,
): readonly [string, number, number] {
  const spaceId = hasTopology(board) ? (board.cells[p.y]?.[p.x]?.spaceId ?? '') : '';
  return [spaceId, p.y, p.x];
}

/** Total order of cells by K (ordinal string compare, then y, then x). */
export function compareCanonical(
  board: TopologyBoard | null | undefined,
  a: Position,
  b: Position,
): number {
  const [sa, ya, xa] = canonicalKey(board, a);
  const [sb, yb, xb] = canonicalKey(board, b);
  if (sa !== sb) return sa < sb ? -1 : 1;
  if (ya !== yb) return ya - yb;
  return xa - xb;
}

/**
 * Canonical path to `dest` WITHOUT the start cell (the wire format of
 * `maneuver.moves[].path`, 04 §4.1). `[]` — dest is the start ("stay", not
 * sent); `null` — dest is not reached or cannot end the move.
 */
export function canonicalPath(
  reach: ReachMap,
  state: CanonicalState,
  dest: Position,
): Position[] | null {
  if (samePos(dest, reach.start)) return [];
  const steps = reachDistance(reach, dest);
  if (steps === undefined || !isEndpoint(state, reach, dest)) return null;
  const board = state.boardState;
  const path: Position[] = [{ x: dest.x, y: dest.y }];
  let current: Position = dest;
  for (let d = steps; d > 1; d--) {
    let best: Position | null = null;
    for (const candidate of neighbours(board, current)) {
      if (reach.dist.get(posKey(candidate)) !== d - 1) continue;
      if (!best || compareCanonical(board, candidate, best) < 0) best = candidate;
    }
    // BFS invariant: a cell at distance d has a neighbour at d - 1
    if (!best) throw new Error(`canonicalPath: broken reach at ${posKey(current)}`);
    path.unshift({ x: best.x, y: best.y });
    current = best;
  }
  return path;
}

/** Cells the move may end on (start excluded), sorted by K. */
export function reachableEndpoints(
  state: CanonicalState,
  reach: ReachMap,
  maxSteps = reach.maxSteps,
): Position[] {
  const out: Position[] = [];
  for (const [key, d] of reach.dist) {
    if (d < 1 || d > maxSteps) continue;
    const [x, y] = key.split(':').map(Number);
    if (isEndpoint(state, reach, { x, y })) out.push({ x, y });
  }
  return out.sort((a, b) => compareCanonical(state.boardState, a, b));
}

/** Plate tiers of one fighter (04 §3.2, MS-E-80): base `1..baseSteps`, boost `baseSteps+1..boostSteps`. */
export interface ReachTiers {
  readonly base: Position[];
  readonly boost: Position[];
}

export function reachTiers(
  state: CanonicalState,
  reach: ReachMap,
  baseSteps: number,
  boostSteps: number,
): ReachTiers {
  const all = reachableEndpoints(state, reach, Math.max(baseSteps, boostSteps));
  const base: Position[] = [];
  const boost: Position[] = [];
  for (const p of all) {
    const d = reachDistance(reach, p) ?? Infinity;
    if (d <= baseSteps) base.push(p);
    else if (d <= boostSteps) boost.push(p);
  }
  return { base, boost };
}

// ---------------------------------------------------------------------------
// Sequential draft evaluation (04 §3.2) — the reference for FS09DraftEval
// ---------------------------------------------------------------------------

/** A hand card as the draft sees it: instance id and printed BOOST (null = none). */
export interface DraftHandCard {
  readonly id: string;
  readonly boostValue?: number | null;
}

export interface DraftMoveInput {
  readonly fighterId: string;
  readonly dest: Position;
}

export interface DraftInput {
  readonly moves: readonly DraftMoveInput[];
  readonly boostCardId?: string | null;
}

export type DraftMoveStatus = 'ok' | 'needBoost' | 'conflict';

/** Why a move is a Conflict (the client maps it to a why.* key, MS-T-05/06). */
export type DraftConflict =
  | 'missing'
  | 'not-yours'
  | 'defeated'
  | 'immobilized'
  | 'duplicate'
  | 'no-path';

export interface DraftMoveEval {
  readonly order: number;
  readonly fighterId: string;
  readonly dest: Position;
  /** getFighterMovement of the fighter (raw value rule, MS-E-04, MS-E-107) */
  readonly base: number;
  /** canonical path without the start; [] = stay; null = Conflict */
  readonly path: Position[] | null;
  readonly status: DraftMoveStatus;
  /** absolute BOOST the move needs: max(0, len(path) - base); 0 for Conflict */
  readonly requiredBoost: number;
  readonly conflict?: DraftConflict;
  /** plate tiers of this fighter on the work state before its move */
  readonly reach: ReachTiers;
}

export interface DraftEval {
  /** BOOST of the selected card (null BOOST or no card → 0) */
  readonly selectedBoost: number;
  /** max BOOST of the hand cards that have one (boostValue != null), 0 if none */
  readonly maxBoost: number;
  readonly moves: DraftMoveEval[];
  /** fighters after the Ok/NeedBoost moves (work_n) */
  readonly fighters: readonly Fighter[];
}

/** BOOST a card adds; null/undefined/non-number → null (no printed BOOST). */
export function cardBoost(card: DraftHandCard | undefined): number | null {
  const v = card?.boostValue;
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function isImmobilized(f: Fighter): boolean {
  return (f.effects ?? []).some((e) => e.type === 'immobilized');
}

/**
 * Evaluates the ordered draft on the positions after the previous moves
 * (04 §3.2): reach with base + max(selected, max hand BOOST), canonical path,
 * required BOOST and status Ok / NeedBoost / Conflict. `actorId` (optional)
 * rejects fighters of another owner. The mover needs only health > 0
 * (MS-E-77, as validateManeuver); blockers use isLivingFighter (MS-E-24).
 */
export function evaluateDraft(
  state: CanonicalState,
  draft: DraftInput,
  hand: readonly DraftHandCard[],
  actorId?: string,
): DraftEval {
  const selectedCard = draft.boostCardId ? hand.find((c) => c.id === draft.boostCardId) : undefined;
  const selectedBoost = cardBoost(selectedCard) ?? 0;
  const maxBoost = hand.reduce((m, c) => Math.max(m, cardBoost(c) ?? 0), 0);

  let fighters: readonly Fighter[] = state.fighters;
  const seen = new Set<string>();
  const moves: DraftMoveEval[] = [];
  const noTiers: ReachTiers = { base: [], boost: [] };

  draft.moves.forEach((mv, order) => {
    const dest = { x: mv.dest.x, y: mv.dest.y };
    const fighter = fighters.find((f) => f.id === mv.fighterId);
    const base = fighter ? getFighterMovement(fighter) : 0;
    const conflict = (why: DraftConflict, reach: ReachTiers = noTiers): void => {
      moves.push({
        order,
        fighterId: mv.fighterId,
        dest,
        base,
        path: null,
        status: 'conflict',
        requiredBoost: 0,
        conflict: why,
        reach,
      });
    };
    if (seen.has(mv.fighterId)) return conflict('duplicate');
    seen.add(mv.fighterId);
    if (!fighter) return conflict('missing');
    if (actorId !== undefined && fighter.ownerId !== actorId) return conflict('not-yours');
    if (fighter.health <= 0) return conflict('defeated');
    if (isImmobilized(fighter)) return conflict('immobilized');

    const work: CanonicalState = { boardState: state.boardState, fighters };
    const reach = computeReach(work, fighter.id, base + Math.max(selectedBoost, maxBoost));
    const tiers = reachTiers(work, reach, base + selectedBoost, base + maxBoost);
    const path = canonicalPath(reach, work, dest);
    if (!path) return conflict('no-path', tiers);

    const requiredBoost = Math.max(0, path.length - base);
    moves.push({
      order,
      fighterId: fighter.id,
      dest,
      base,
      path,
      status: requiredBoost <= selectedBoost ? 'ok' : 'needBoost',
      requiredBoost,
      reach: tiers,
    });
    fighters = fighters.map((f) => (f.id === fighter.id ? { ...f, position: dest } : f));
  });

  return { selectedBoost, maxBoost, moves, fighters };
}
