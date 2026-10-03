/**
 * MS-T-02 — golden move fixtures (unmatched.move-fixture/1, 04 §4.8):
 * loader, full-GameState builder on top of s03Fixture()/s03Engine(), the
 * reference expectations (canonical-path) and the routing by expect.layer:
 *
 *   dto            — class-validator over ManeuverDto/PositionInput, with the
 *                    options of the global ValidationPipe (main.ts);
 *   validator      — GameRulesValidator.validateManeuver, move after move;
 *   executor       — GameActionExecutorService.executeManeuver on the full
 *                    GameState (phase, pendingManeuver, hand, decks, registry);
 *   resolvePending — executeResolvePendingEffect for a pending MOVE/PLACE.
 *
 * Fixture files: backend/prisma/fixtures/movement/<name>.move-fixture.json.
 * Generated ones come from backend/scripts/gen-move-fixtures.ts; manual ones
 * (expectSource "manual") are written by hand from the rules and only read.
 *
 * MS-T-06: the executor and resolvePendingEffect report ActionResult.code
 * (02 §1.1); `serverCodeOf` takes that code and nothing else - a rejection
 * without a code is reported as NO_CODE (a missing MS-T-06 code fails the
 * fixture instead of being guessed from the error text).
 *
 * Format additions to 04 §4.8 (the interfaces below are the reference for
 * the UE parity reader, MS-T-03):
 *  - `name` (= file name without .move-fixture.json), `description`,
 *    `cases` (MS-E rows), `actor` (sender, default p1; pending → ownerId);
 *  - `board.lattice` = { width, height, walls?: [[x,y]], edges?: [[[x,y],[x,y]]] }:
 *    an inline board where every cell is a space; with `edges` it is a
 *    topology board (a cell without edges has links []);
 *  - `draft.moves[i].path` — a FORCED command path (no start cell), sent
 *    verbatim; the destination is `dest` or, if absent, the last path cell
 *    (an empty path = stay). Conflict moves need one, since they have no
 *    canonical path to send;
 *  - `fighters[i].movement` is the raw save value (number, string, null or
 *    absent); `effects` is a list of effect types;
 *  - `expect.serverDetail` (dto layer: constraint path behind DTO_REJECTED)
 *    and `expect.pendingRuleChange` { task, rule, server } — a documented
 *    server-vs-rules deviation: `server` is today's answer, the named task
 *    (MS-T-19 / MS-T-20) changes it;
 *  - `expect.reach` lists are compared as sets; `paths` exactly (null =
 *    Conflict, [] = stay).
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { plainToInstance } from 'class-transformer';
import { validate, type ValidationError } from 'class-validator';
import type {
  BoardState,
  Fighter,
  GameState,
  PendingEffect,
  Position,
} from '../../game-engine/models';
import { FighterType } from '../../game-engine/models';
import {
  canonicalPath,
  computeReach,
  evaluateDraft,
  reachTiers,
  type DraftEval,
  type DraftHandCard,
  type DraftInput,
  type DraftMoveStatus,
} from '../../game-engine/movement/canonical-path';
import { GameRulesValidator } from '../../game-engine/validators/game-rules.validator';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { ManeuverDto } from '../../games/dto/gameplay.dto';
import { GameInitializationService } from '../../games/services/game-initialization.service';
import {
  fixtureSha256,
  loadTopologyFixture,
  topologyBoardRow,
  TOPOLOGY_FIXTURE_DIR,
} from '../../../prisma/seed-env-map-boards';
import { s03Card, s03Engine, s03Fixture } from './s03-engine.fixture';

export const MOVE_FIXTURE_SCHEMA = 'unmatched.move-fixture/1';
export const MOVE_FIXTURE_DIR = resolve(__dirname, '../../../prisma/fixtures/movement');
export const MOVE_FIXTURE_SUFFIX = '.move-fixture.json';
export const MOVE_FIXTURE_GENERATOR = 'backend/scripts/gen-move-fixtures.ts';
/** dto-layer rejection: class-validator stopped the input; 02 §1.1 has no ruleCode for it */
export const DTO_REJECTED = 'DTO_REJECTED';

export type Cell2 = [number, number];
export interface XY {
  x: number;
  y: number;
}

export interface MoveFixtureBoard {
  /** topology map ('marmoreal' | 'sarpedon') or the name of an inline lattice */
  key: string;
  /** sha256 of backend/prisma/fixtures/boards/<key>.topology.json (LF), MS-R-67 */
  topologySha256?: string;
  /** inline lattice: every cell is a space; walls are obstacles; edges make it a topology board */
  lattice?: { width: number; height: number; walls?: Cell2[]; edges?: [Cell2, Cell2][] };
}

export interface MoveFixtureFighter {
  id: string;
  ownerId: string;
  position: XY;
  name?: string;
  type?: 'HERO' | 'MINION';
  health?: number;
  maxHealth?: number;
  isDefeated?: boolean;
  /** raw value as it may come from a save: number, string, null or absent (MS-E-04/107) */
  movement?: unknown;
  /** effect types, e.g. ["immobilized"] */
  effects?: string[];
}

export interface MoveFixtureHandCard {
  id: string;
  boostValue: number | null;
}

export interface MoveFixtureDraftMove {
  fighterId: string;
  /** destination picked by the player; the client builds the canonical path */
  dest?: XY;
  /** forced command path (without the start) — used verbatim instead of the canonical one */
  path?: XY[];
}

export interface MoveFixtureDraft {
  moves: MoveFixtureDraftMove[];
  boostCardId?: string | null;
}

export interface MoveFixturePending {
  type: 'MOVE' | 'PLACE';
  /** fighter the choice moves */
  fighterId: string;
  /** player who owns (resolves) the choice */
  ownerId: string;
  /** MOVE distance; absent/null → 1, 0 → stay only (MS-E-57, MS-E-76) */
  value?: number | null;
  canPassThroughEnemies?: boolean;
  targetsOpponent?: boolean;
  zoneFighterName?: string | null;
  optional?: boolean;
  /** cell the player picks */
  target: XY;
}

export type MoveFixtureLayer = 'dto' | 'validator' | 'executor' | 'resolvePending';

export interface MoveFixtureExpect {
  layer: MoveFixtureLayer;
  reach?: Record<string, { base: Cell2[]; boost: Cell2[] }>;
  paths?: Record<string, Cell2[] | null>;
  status?: Record<string, DraftMoveStatus>;
  requiredBoost?: Record<string, number>;
  /** 'ok' or a code of 02 §1.1 (DTO_REJECTED on the dto layer) */
  server: string;
  /** dto layer: the class-validator constraint path(s) behind DTO_REJECTED, e.g. moves.0.path.0.x:max */
  serverDetail?: string;
  /** documented server-vs-rules deviation (02): today's `server` changes in a later task */
  pendingRuleChange?: { task: string; rule: string; server: string };
}

export interface MoveFixture {
  schema: string;
  name: string;
  expectSource: 'manual' | 'generated';
  description?: string;
  /** MS-E rows the fixture covers */
  cases?: string[];
  /** player who sends the command (default p1; for pending — pending.ownerId) */
  actor?: string;
  board: MoveFixtureBoard;
  fighters: MoveFixtureFighter[];
  hand?: MoveFixtureHandCard[];
  draft?: MoveFixtureDraft;
  pending?: MoveFixturePending;
  expect: MoveFixtureExpect;
}

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

export function moveFixtureFiles(dir = MOVE_FIXTURE_DIR): string[] {
  return readdirSync(dir)
    .filter((f) => f.endsWith(MOVE_FIXTURE_SUFFIX))
    .sort()
    .map((f) => join(dir, f));
}

export function loadMoveFixtures(dir = MOVE_FIXTURE_DIR): MoveFixture[] {
  return moveFixtureFiles(dir).map((file) => JSON.parse(readFileSync(file, 'utf8')) as MoveFixture);
}

export function topologyFile(key: string): string {
  return join(TOPOLOGY_FIXTURE_DIR, `${key}.topology.json`);
}

/** sha256 (LF) of the topology file a fixture is pinned to, or null for inline lattices */
export function currentTopologySha256(board: MoveFixtureBoard): string | null {
  if (board.lattice) return null;
  return fixtureSha256(readFileSync(topologyFile(board.key)));
}

/** MS-R-67: message for a fixture pinned to another topology, or null when fresh */
export function topologyStaleness(fx: MoveFixture): string | null {
  const current = currentTopologySha256(fx.board);
  if (current === null || current === fx.board.topologySha256) return null;
  return (
    `${fx.name}: pinned to ${fx.board.key}.topology.json sha256 ${fx.board.topologySha256}, ` +
    `the file is now ${current}. Regenerate with ${MOVE_FIXTURE_GENERATOR} --write and re-check ` +
    `the manual fixtures of this board by hand.`
  );
}

// ---------------------------------------------------------------------------
// Board and GameState
// ---------------------------------------------------------------------------

const toXY = ([x, y]: Cell2): XY => ({ x, y });
export const toCell2 = (p: Position): Cell2 => [p.x, p.y];
const k2 = (p: Position): string => `${p.x}:${p.y}`;

/** Board.cells row of an inline lattice (the shape buildBoardState reads from the DB) */
function latticeRow(board: MoveFixtureBoard) {
  const { width, height, walls = [], edges } = board.lattice;
  const wallSet = new Set(walls.map((c) => k2(toXY(c))));
  const links = new Map<string, Position[]>();
  for (const [a, b] of edges ?? []) {
    links.set(k2(toXY(a)), [...(links.get(k2(toXY(a))) ?? []), toXY(b)]);
    links.set(k2(toXY(b)), [...(links.get(k2(toXY(b))) ?? []), toXY(a)]);
  }
  const cells = [];
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const key = `${x}:${y}`;
      cells.push({
        x,
        y,
        ...(wallSet.has(key) ? { isObstacle: true } : {}),
        ...(edges ? { links: links.get(key) ?? [] } : {}),
      });
    }
  }
  return { id: `lattice-${board.key}`, name: board.key, cells };
}

const boardCache = new Map<string, BoardState>();

/**
 * Engine BoardState of a fixture board, built by the production
 * GameInitializationService.buildBoardState from the same Board row the seed
 * writes (topology maps) or from an inline lattice row.
 */
export function boardStateFor(board: MoveFixtureBoard): BoardState {
  const cacheKey = JSON.stringify(board.lattice ? board : { key: board.key });
  const cached = boardCache.get(cacheKey);
  if (cached) return cached;
  let row: unknown;
  if (board.lattice) {
    row = latticeRow(board);
  } else {
    const file = topologyFile(board.key);
    const { fixture, sha256 } = loadTopologyFixture(file);
    row = JSON.parse(JSON.stringify(topologyBoardRow(fixture, sha256, file)));
  }
  const init = new GameInitializationService(null as never, null as never);
  const state = init['buildBoardState'](row as never);
  boardCache.set(cacheKey, state);
  return state;
}

export function fixtureActor(fx: MoveFixture): string {
  return fx.pending?.ownerId ?? fx.actor ?? 'p1';
}

function engineFighter(f: MoveFixtureFighter, index: number, all: MoveFixtureFighter[]): Fighter {
  const health = f.health ?? 10;
  const firstOfOwner = all.findIndex((o) => o.ownerId === f.ownerId) === index;
  return {
    id: f.id,
    ownerId: f.ownerId,
    heroId: `hero-${f.ownerId}`,
    name: f.name ?? f.id,
    type:
      (f.type ?? (firstOfOwner ? 'HERO' : 'MINION')) === 'HERO'
        ? FighterType.HERO
        : FighterType.MINION,
    health,
    maxHealth: f.maxHealth ?? Math.max(health, 10),
    position: { x: f.position.x, y: f.position.y },
    effects: (f.effects ?? []).map((type) => ({ type })),
    hasSidekick: false,
    isDefeated: f.isDefeated ?? false,
    // raw value, exactly as a save may hold it (number | string | null)
    ...('movement' in f ? { movement: f.movement as number } : {}),
  };
}

/**
 * Full GameState of a fixture on top of s03Fixture(): players of every owner,
 * board, fighters, the actor's hand and decks, phase ACTION_MANEUVER, one
 * action left (begin already spent the other, so a maneuver does not pass
 * the turn), and either the open pendingManeuver (draft) or the pending
 * MOVE/PLACE choice at the head of the queue.
 */
export function buildMoveFixtureState(fx: MoveFixture): GameState {
  const base = s03Fixture(0, 1);
  const actor = fixtureActor(fx);
  const owners = [...new Set([actor, ...fx.fighters.map((f) => f.ownerId)])];
  const fighters = fx.fighters.map((f, i, all) => engineFighter(f, i, all));
  const filler = (owner: string, n: number) => s03Card(`${owner}-deck-${n}`);
  const seq = base.sequenceNumber;
  const pending: PendingEffect | undefined = fx.pending
    ? {
        id: `pending:${fx.name}`,
        type: fx.pending.type,
        playerId: fx.pending.ownerId,
        ...(fx.pending.value !== undefined ? { value: fx.pending.value } : {}),
        ...(fx.pending.canPassThroughEnemies ? { canPassThroughEnemies: true } : {}),
        ...(fx.pending.targetsOpponent ? { targetsOpponent: true } : {}),
        ...(fx.pending.zoneFighterName ? { zoneFighterName: fx.pending.zoneFighterName } : {}),
        ...(fx.pending.optional !== undefined ? { optional: fx.pending.optional } : {}),
        text: `fixture ${fx.name}`,
      }
    : undefined;
  return {
    ...base,
    gameId: `move-fixture:${fx.name}`,
    currentTurnPlayerId: actor,
    players: owners.map((userId) => ({
      userId,
      heroId: `hero-${userId}`,
      health: 10,
      maxHealth: 10,
      fighterIds: fighters.filter((f) => f.ownerId === userId).map((f) => f.id),
      isAlive: true,
    })),
    fighters,
    decks: Object.fromEntries(
      owners.map((o) => [o, { cards: [], drawPile: [filler(o, 1), filler(o, 2)] }]),
    ),
    handZones: Object.fromEntries(
      owners.map((o) => [
        o,
        {
          cards:
            o === actor
              ? (fx.hand ?? []).map((c) => ({
                  ...s03Card(c.id),
                  boostValue: c.boostValue,
                  isVisible: true,
                }))
              : [],
          maxSize: 7,
        },
      ]),
    ),
    discardPiles: Object.fromEntries(owners.map((o) => [o, []])),
    boardState: boardStateFor(fx.board),
    metadata: {
      ...base.metadata,
      lastActionBy: actor,
      actionsRemaining: 1,
      ...(fx.draft
        ? { pendingManeuver: { id: `maneuver:${base.turnCount}:${seq - 1}`, playerId: actor } }
        : {}),
      ...(pending ? { pendingEffects: [pending] } : {}),
    },
  } as GameState;
}

export function fixtureHand(fx: MoveFixture): DraftHandCard[] {
  return (fx.hand ?? []).map((c) => ({ id: c.id, boostValue: c.boostValue }));
}

/** Draft as the client holds it: a forced path's last cell is the destination */
export function draftInputOf(fx: MoveFixture, state: GameState): DraftInput {
  return {
    boostCardId: fx.draft?.boostCardId ?? undefined,
    moves: (fx.draft?.moves ?? []).map((m) => {
      const start = state.fighters.find((f) => f.id === m.fighterId)?.position ?? { x: -1, y: -1 };
      const dest = m.dest ?? (m.path && m.path.length > 0 ? m.path[m.path.length - 1] : start);
      return { fighterId: m.fighterId, dest: { x: dest.x, y: dest.y } };
    }),
  };
}

// ---------------------------------------------------------------------------
// Reference expectations (canonical-path) — MS-AT-01
// ---------------------------------------------------------------------------

export type ComputedExpect = Required<
  Pick<MoveFixtureExpect, 'reach' | 'paths' | 'status' | 'requiredBoost'>
>;

export function evaluateFixtureDraft(
  fx: MoveFixture,
  state = buildMoveFixtureState(fx),
): DraftEval {
  return evaluateDraft(state, draftInputOf(fx, state), fixtureHand(fx), fixtureActor(fx));
}

export function computeFixtureExpect(fx: MoveFixture): ComputedExpect {
  const state = buildMoveFixtureState(fx);
  const out: ComputedExpect = { reach: {}, paths: {}, status: {}, requiredBoost: {} };
  if (fx.draft) {
    for (const m of evaluateFixtureDraft(fx, state).moves) {
      if (m.fighterId in out.status) continue; // a repeated fighter keeps its first entry
      out.reach[m.fighterId] = {
        base: m.reach.base.map(toCell2),
        boost: m.reach.boost.map(toCell2),
      };
      out.paths[m.fighterId] = m.path ? m.path.map(toCell2) : null;
      out.status[m.fighterId] = m.status;
      out.requiredBoost[m.fighterId] = m.requiredBoost;
    }
  } else if (fx.pending?.type === 'MOVE') {
    const p = fx.pending;
    const allowance = p.value ?? 1;
    const reach = computeReach(state, p.fighterId, allowance, {
      passThroughEnemies: p.canPassThroughEnemies === true,
    });
    const tiers = reachTiers(state, reach, allowance, allowance);
    const path = canonicalPath(reach, state, p.target);
    out.reach[p.fighterId] = { base: tiers.base.map(toCell2), boost: [] };
    out.paths[p.fighterId] = path ? path.map(toCell2) : null;
    out.status[p.fighterId] = path ? 'ok' : 'conflict';
    out.requiredBoost[p.fighterId] = 0;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Server layers — MS-AT-02
// ---------------------------------------------------------------------------

/** Code of a failed ActionResult: its own `code` (MS-T-06); NO_CODE: <text> otherwise. */
export function serverCodeOf(result: { success: boolean; error?: string; code?: string }): string {
  if (result.success) return 'ok';
  if (result.code) return result.code;
  return `NO_CODE: ${result.error ?? ''}`;
}

export interface CommandMove {
  fighterId: string;
  path: XY[];
}

/**
 * maneuver.moves[] the client would send for the draft: the forced path when
 * given, otherwise the canonical path; "stay" moves are dropped (MS-D-08).
 * A Conflict move has no canonical path — such a fixture must force one.
 */
export function commandMovesOf(fx: MoveFixture, evaluation: DraftEval): CommandMove[] {
  const out: CommandMove[] = [];
  (fx.draft?.moves ?? []).forEach((m, i) => {
    if (m.path) {
      out.push({ fighterId: m.fighterId, path: m.path.map((p) => ({ x: p.x, y: p.y })) });
      return;
    }
    const e = evaluation.moves[i];
    if (!e.path) {
      throw new Error(
        `${fx.name}: move ${i} (${m.fighterId}) is a Conflict — give it an explicit "path"`,
      );
    }
    if (e.path.length > 0)
      out.push({ fighterId: m.fighterId, path: e.path.map((p) => ({ x: p.x, y: p.y })) });
  });
  return out;
}

export interface LayerOutcome {
  server: string;
  error?: string;
  /** command that was sent (dto / validator / executor) */
  moves?: CommandMove[];
  /** positions after a successful executor / resolvePending run */
  positions?: Record<string, XY>;
}

let engine: ReturnType<typeof s03Engine> | null = null;
const engineOnce = () => (engine ??= s03Engine());

const flattenErrors = (errors: ValidationError[], prefix = ''): string[] =>
  errors.flatMap((e) => [
    ...Object.keys(e.constraints ?? {}).map((c) => `${prefix}${e.property}:${c}`),
    ...flattenErrors(e.children ?? [], `${prefix}${e.property}.`),
  ]);

function positionsOf(state: GameState | undefined): Record<string, XY> | undefined {
  if (!state) return undefined;
  return Object.fromEntries(
    state.fighters.map((f) => [f.id, { x: f.position.x, y: f.position.y }]),
  );
}

/** Runs the fixture through the layer of expect.layer and reports the server outcome. */
export async function runFixtureLayer(fx: MoveFixture): Promise<LayerOutcome> {
  const state = buildMoveFixtureState(fx);
  const actor = fixtureActor(fx);
  const ctx = { gameId: state.gameId, userId: actor, currentState: state };

  if (fx.expect.layer === 'resolvePending') {
    const p = fx.pending;
    if (!p) throw new Error(`${fx.name}: layer resolvePending needs "pending"`);
    const r = await engineOnce().executor.executeResolvePendingEffect(
      {
        gameId: state.gameId,
        effectId: `pending:${fx.name}`,
        fighterId: p.fighterId,
        x: p.target.x,
        y: p.target.y,
      },
      ctx,
    );
    return { server: serverCodeOf(r), error: r.error, positions: positionsOf(r.gameState) };
  }

  if (!fx.draft) throw new Error(`${fx.name}: layer ${fx.expect.layer} needs "draft"`);
  const moves = commandMovesOf(fx, evaluateFixtureDraft(fx, state));
  const boostCardId = fx.draft.boostCardId ?? undefined;
  const maneuverId = state.metadata.pendingManeuver.id;

  if (fx.expect.layer === 'dto') {
    const input = {
      gameId: state.gameId,
      maneuverId,
      moves,
      ...(boostCardId ? { boostCardId } : {}),
    };
    const dto = plainToInstance(ManeuverDto, input, { enableImplicitConversion: true });
    const errors = await validate(dto, { whitelist: true, forbidNonWhitelisted: true });
    return errors.length
      ? { server: DTO_REJECTED, error: flattenErrors(errors).join(', '), moves }
      : { server: 'ok', moves };
  }

  if (fx.expect.layer === 'validator') {
    const validator = new GameRulesValidator(new AdjacencyService());
    let work: GameState = state;
    for (const mv of moves) {
      const v = validator.validateManeuver(work, mv.fighterId, boostCardId, mv.path, actor);
      if (!v.valid) return { server: v.code ?? `UNMAPPED: ${v.error}`, error: v.error, moves };
      const dest = mv.path[mv.path.length - 1];
      work = {
        ...work,
        fighters: work.fighters.map((f) => (f.id === mv.fighterId ? { ...f, position: dest } : f)),
      };
    }
    return { server: 'ok', moves, positions: positionsOf(work) };
  }

  if (fx.expect.layer === 'executor') {
    const dto = { gameId: state.gameId, maneuverId, moves, boostCardId } as ManeuverDto;
    const r = await engineOnce().executor.executeManeuver(dto, ctx);
    return { server: serverCodeOf(r), error: r.error, moves, positions: positionsOf(r.gameState) };
  }

  throw new Error(`${fx.name}: unknown layer ${String(fx.expect.layer)}`);
}
