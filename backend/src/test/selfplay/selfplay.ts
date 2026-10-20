/**
 * DET-3 (docs/research/de-reverse-2026-10-20/VERDICT.md §3 P1.3): headless
 * self-play on the real maps with a random legal policy and invariants after
 * every accepted command.
 *
 * - Boards: Marmoreal · original map and Sarpedon · original map only (real
 *   topology rows, decision 2026-10-04 «only real boards»).
 * - Heroes: Medusa and King Arthur from the frozen S01 content captures, dealt
 *   by the production GameInitializationService with a seeded RNG; the
 *   executor is s03Engine with the production hero abilities registered.
 * - Policy: random over the commands a client can send — including schemes,
 *   stances, doors and direct moves, which the AI policy never plays — and the
 *   server-side fallbacks (system combat resolve after the deadline, the
 *   deterministic choice fallback). A rejected candidate is simply the next try.
 * - Invariants (checkInvariants): card instances conserved and in one zone,
 *   HP in bounds, seq +1 per command, a defeated hero means GAME_OVER, the
 *   winner never changes, no command accepted after GAME_OVER, an out-of-turn
 *   probe is rejected, someone always has an accepted command (liveness),
 *   serialize round-trip is lossless, no projection leaks hidden cards or the
 *   RNG state, and the executor never mutates its input (deep freeze).
 * - Determinism: the accepted commands replay from the start snapshot with the
 *   same canonical hash on every step (games/replay).
 *
 * A failure reports the seed; the same seed replays the same game.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { GameInitializationService } from '../../games/services/game-initialization.service';
import { GameStateService, deserializeGameState, serializeGameState } from '../../games/game-state.service';
import { FighterType, GamePhase, getFighterMovement } from '../../game-engine/models';
import type { Fighter, GameState, PendingEffect, Position } from '../../game-engine/models';
import { rngFromSeed, rngInt, rngNext, type RngState } from '../../game-engine/engine/rng';
import { executeGameCommand, type GameCommand, type GameCommandKind } from '../../game-engine/services/game-command';
import type { GameActionExecutorService } from '../../game-engine/services/game-action-executor.service';
import { canonicalPath, computeReach, reachableEndpoints } from '../../game-engine/movement/canonical-path';
import { neighbours } from '../../game-engine/engine/board-topology';
import { ABILITY_CONFIGS } from '../../game-engine/abilities/ability-config';
import { canonicalStateHash, engineVersion, REPLAY_FORMAT_VERSION, type StartSnapshot } from '../../games/replay/replay-format';
import { replayGame, type ReplayCommandRow, type ReplayResult } from '../../games/replay/replay';
import { s03Engine } from '../fixtures/s03-engine.fixture';
import { marmorealBoardRow, sarpedonBoardRow } from '../fixtures/real-board';

// ---------------------------------------------------------------------------
// Content: real maps, S01 hero captures
// ---------------------------------------------------------------------------

export type SelfPlayBoard = 'marmoreal' | 'sarpedon';
export type SelfPlayHero = 'medusa' | 'arthur';

const root = resolve(__dirname, '../../../..');
const capture = (file: string) =>
  JSON.parse(readFileSync(resolve(root, 'docs/game-design/evidence/S01', file), 'utf8'));

function heroRow(c: any, attackType: 'melee' | 'ranged') {
  return {
    id: c.id, name: c.name, health: c.health, movement: c.movement, fighterType: 'HERO',
    properties: { attackType },
    sidekicks: c.sidekicks,
    cards: c.cards.map((card: any) => ({ ...card, text: card.textEn })),
  };
}

let heroCache: Record<SelfPlayHero, ReturnType<typeof heroRow>> | undefined;
/** Hero rows (Prisma Hero + cards) of the S01 captures */
export function heroes(): Record<SelfPlayHero, ReturnType<typeof heroRow>> {
  heroCache ??= {
    medusa: heroRow(capture('content-medusa.json'), 'ranged'),
    arthur: heroRow(capture('content-king-arthur.json'), 'melee'),
  };
  return heroCache;
}

export interface SelfPlayOptions {
  readonly seed: number;
  readonly board: SelfPlayBoard;
  /** heroes of u1 and u2 */
  readonly heroes: readonly [SelfPlayHero, SelfPlayHero];
  /** who sits at seatOrder 0 and moves first */
  readonly first: 'u1' | 'u2';
  /** cap on accepted commands; a game still running at the cap is reported, not failed */
  readonly maxCommands?: number;
}

/** Production deal (GameInitializationService) on a real map, RNG seeded from the fuzz seed. */
export function boardRowOf(board: SelfPlayBoard) {
  return board === 'marmoreal' ? marmorealBoardRow() : sarpedonBoardRow();
}

export async function startSelfPlayGame(opts: SelfPlayOptions): Promise<GameState> {
  const board = boardRowOf(opts.board);
  const rows = heroes();
  const seat = (userId: 'u1' | 'u2') => (userId === opts.first ? 0 : 1);
  const players = [
    { userId: 'u1', heroId: rows[opts.heroes[0]].id, seatOrder: seat('u1') },
    { userId: 'u2', heroId: rows[opts.heroes[1]].id, seatOrder: seat('u2') },
  ].sort((a, b) => a.seatOrder - b.seatOrder);
  const prisma = {
    game: { findUnique: async () => ({ boardId: board.id }) },
    board: { findUnique: async () => board },
    gamePlayer: { findMany: async () => players },
    hero: { findUnique: async ({ where }: any) => Object.values(rows).find((h) => h.id === where.id) ?? null },
  };
  const init = new GameInitializationService(prisma as any, { saveState: async () => undefined } as any);
  init.rngSeed = () => rngFromSeed(opts.seed);
  return init.initializeGameState(`selfplay-${opts.board}-${opts.seed}`);
}

// ---------------------------------------------------------------------------
// Dice: the policy's own RNG stream (never the game RNG)
// ---------------------------------------------------------------------------

export class Dice {
  constructor(private s: RngState) {}
  float(): number {
    const [v, next] = rngNext(this.s);
    this.s = next;
    return v;
  }
  int(n: number): number {
    const [v, next] = rngInt(this.s, n);
    this.s = next;
    return v;
  }
  chance(p: number): boolean {
    return this.float() < p;
  }
  pick<T>(items: readonly T[]): T | undefined {
    return items.length ? items[this.int(items.length)] : undefined;
  }
  shuffle<T>(items: readonly T[]): T[] {
    const out = [...items];
    for (let i = out.length - 1; i > 0; i--) {
      const j = this.int(i + 1);
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }
  sample<T>(items: readonly T[], n: number): T[] {
    return this.shuffle(items).slice(0, n);
  }
}

// ---------------------------------------------------------------------------
// Random legal policy: candidate commands for a state
// ---------------------------------------------------------------------------

export interface Candidate {
  readonly kind: GameCommandKind;
  readonly userId: string;
  readonly input: Record<string, unknown>;
  readonly system?: boolean;
  readonly weight: number;
  readonly label: string;
}

const living = (f: Fighter) => !f.isDefeated && f.health > 0;
const playersOf = (s: GameState) => s.players.map((p) => p.userId);
const otherPlayer = (s: GameState, userId: string) => playersOf(s).find((u) => u !== userId)!;

function boardCells(state: GameState): Position[] {
  const cells: Position[] = [];
  state.boardState.cells.forEach((row, y) =>
    row.forEach((cell: any, x) => {
      // topology maps mark the lattice holes between spaces as obstacles
      if (cell && cell.type !== 'wall' && cell.type !== 'obstacle') {
        cells.push({ x: cell.x ?? x, y: cell.y ?? y });
      }
    }),
  );
  return cells;
}

function freeCells(state: GameState, exceptFighter?: string): Position[] {
  const taken = new Set(
    state.fighters.filter((f) => f.id !== exceptFighter && living(f)).map((f) => `${f.position.x}:${f.position.y}`),
  );
  return boardCells(state).filter((p) => !taken.has(`${p.x}:${p.y}`));
}

function stanceIdsOf(state: GameState, userId: string): string[] {
  const hero = state.fighters.find((f) => f.ownerId === userId && f.type === FighterType.HERO);
  const slug = hero?.heroSlug ?? hero?.heroId;
  const config = ABILITY_CONFIGS.find((c) => c.heroId === slug) as { stances?: ReadonlyArray<{ id: string }> } | undefined;
  return (config?.stances ?? []).map((s) => s.id);
}

/** Random endpoints of a fighter within `steps`; [] when it cannot move. */
function endpointsOf(state: GameState, fighterId: string, steps: number, passThroughEnemies = false): Position[] {
  try {
    const reach = computeReach(state, fighterId, steps, { passThroughEnemies });
    return reachableEndpoints(state, reach, steps);
  } catch {
    return [];
  }
}

function pathTo(state: GameState, fighterId: string, steps: number, dest: Position): Position[] | null {
  try {
    const reach = computeReach(state, fighterId, steps, {});
    return canonicalPath(reach, state, dest);
  } catch {
    return null;
  }
}

function pendingCandidates(state: GameState, head: PendingEffect, dice: Dice, fallback: object | null): Candidate[] {
  const out: Candidate[] = [];
  const owner = head.playerId;
  const add = (input: Record<string, unknown>, weight: number, label: string, kind: GameCommandKind = 'resolvePendingEffect') =>
    out.push({ kind, userId: owner, input: { gameId: state.gameId, effectId: head.id, ...input }, weight, label });
  add({}, head.optional ? 1 : 0.2, `decline:${head.type}`, 'declinePendingEffect');
  if (fallback) add(fallback as Record<string, unknown>, 1, `fallback:${head.type}`);
  const hand = state.handZones[owner]?.cards ?? [];
  switch (head.type) {
    case 'CHOOSE_ONE':
      (head.options ?? []).forEach((o) => add({ optionIndex: o.index }, 1, `choose:${o.index}`));
      break;
    case 'TARGET_FIGHTER': {
      const ids = head.targetFighterIds?.length ? head.targetFighterIds : state.fighters.filter(living).map((f) => f.id);
      ids.forEach((id) => add({ fighterId: id }, 1, 'target'));
      break;
    }
    case 'DISCARD_CARDS':
    case 'BOOST_CHOICE': {
      const n = head.type === 'BOOST_CHOICE' ? 1 : head.value ?? 1;
      for (let i = 0; i < 3; i++) add({ cardIds: dice.sample(hand, n).map((c) => c.id) }, 1, `cards:${head.type}`);
      break;
    }
    case 'DECK_TOP_PICK': {
      const revealed = (head.revealedCards ?? []).map((c) => c.id);
      for (let i = 0; i < 3; i++) {
        const ids = (head.mode ?? 'PICK') === 'PICK' ? dice.sample(revealed, head.value ?? 2) : dice.shuffle(revealed);
        add({ cardIds: ids }, 1, `deck:${head.mode ?? 'PICK'}`);
      }
      break;
    }
    case 'CHOOSE_SPACE': {
      const pool = head.stage === 2 && head.anchor
        ? [...neighbours(state.boardState, head.anchor), ...dice.sample(boardCells(state), 2)]
        : dice.sample(boardCells(state), 6);
      pool.forEach((p) => add({ x: p.x, y: p.y }, 1, `space:${head.stage ?? 1}`));
      break;
    }
    case 'MOVE': {
      const ids = head.fighterIds?.length
        ? head.fighterIds
        : state.fighters.filter((f) => living(f) && (head.targetsOpponent ? f.ownerId !== owner : f.ownerId === owner)).map((f) => f.id);
      for (const id of dice.sample(ids, 3)) {
        const f = state.fighters.find((x) => x.id === id);
        if (!f) continue;
        add({ fighterId: id, x: f.position.x, y: f.position.y }, 1, 'move:stay');
        for (const p of dice.sample(endpointsOf(state, id, head.value ?? 1, head.canPassThroughEnemies), 3)) {
          add({ fighterId: id, x: p.x, y: p.y }, 1, 'move');
        }
      }
      break;
    }
    case 'PLACE': {
      const id = head.fighterIds?.[0] ?? state.fighters.find((f) => f.ownerId === owner)?.id;
      if (id) dice.sample(freeCells(state, id), 6).forEach((p) => add({ fighterId: id, x: p.x, y: p.y }, 1, 'place'));
      break;
    }
  }
  return out;
}

function maneuverCandidates(state: GameState, maneuverId: string, owner: string, dice: Dice): Candidate[] {
  const out: Candidate[] = [];
  const hand = state.handZones[owner]?.cards ?? [];
  const boostable = hand.filter((c) => (c.boostValue ?? 0) > 0);
  const base = { gameId: state.gameId, maneuverId };
  out.push({ kind: 'maneuver', userId: owner, input: { ...base, moves: [] }, weight: 0.5, label: 'maneuver:stay' });
  for (let variant = 0; variant < 4; variant++) {
    const boost = dice.chance(0.35) ? dice.pick(boostable) : undefined;
    let scratch = state;
    const moves: Array<{ fighterId: string; path: Position[] }> = [];
    for (const f of dice.shuffle(state.fighters.filter((x) => x.ownerId === owner && living(x)))) {
      if (dice.chance(0.3)) continue;
      const steps = getFighterMovement(f) + (boost?.boostValue ?? 0);
      const dest = dice.pick(endpointsOf(scratch, f.id, steps));
      if (!dest) continue;
      const path = pathTo(scratch, f.id, steps, dest);
      if (!path?.length) continue;
      moves.push({ fighterId: f.id, path });
      scratch = { ...scratch, fighters: scratch.fighters.map((x) => (x.id === f.id ? { ...x, position: dest } : x)) };
    }
    out.push({
      kind: 'maneuver', userId: owner, weight: 1, label: boost ? 'maneuver:boost' : 'maneuver',
      input: { ...base, moves, ...(boost ? { boostCardId: boost.id } : {}) },
    });
  }
  return out;
}

function combatCandidates(state: GameState, clockMs: number): Candidate[] {
  const ci = state.metadata.combatInfo!;
  const g = state.gameId;
  const attacker = state.fighters.find((f) => f.id === ci.attackerId)?.ownerId ?? otherPlayer(state, ci.defenderId);
  const out: Candidate[] = [];
  const deadline = ci.timeoutAt ? new Date(ci.timeoutAt).getTime() : Infinity;
  if (state.phase === GamePhase.COMBAT && !ci.defenderCardId) {
    for (const c of state.handZones[ci.defenderId]?.cards ?? []) {
      const defensive = c.cardType === 'DEFENSE' || c.cardType === 'VERSATILE';
      out.push({ kind: 'playDefense', userId: ci.defenderId, input: { gameId: g, cardId: c.id }, weight: defensive ? 1 : 0.1, label: 'defense' });
    }
    out.push({ kind: 'resolveCombat', userId: ci.defenderId, input: { gameId: g }, weight: 1, label: 'resolve:no-defense' });
    out.push({ kind: 'resolveCombat', userId: attacker, input: { gameId: g }, weight: 0.1, label: 'resolve:attacker-early' });
  } else {
    out.push({ kind: 'resolveCombat', userId: ci.defenderId, input: { gameId: g }, weight: 1, label: 'resolve:defender' });
    out.push({ kind: 'resolveCombat', userId: attacker, input: { gameId: g }, weight: 1, label: 'resolve:attacker' });
  }
  out.push({
    kind: 'resolveCombat', userId: ci.defenderId, input: { gameId: g }, system: true,
    weight: clockMs >= deadline ? 3 : 0.1, label: 'resolve:system',
  });
  return out;
}

function actionCandidates(state: GameState, dice: Dice): Candidate[] {
  const me = state.currentTurnPlayerId;
  const g = state.gameId;
  const out: Candidate[] = [];
  const add = (kind: GameCommandKind, input: Record<string, unknown>, weight: number, label: string = kind) =>
    out.push({ kind, userId: me, input: { gameId: g, ...input }, weight, label });
  const hand = state.handZones[me]?.cards ?? [];
  const mine = state.fighters.filter((f) => f.ownerId === me && living(f));
  const enemies = state.fighters.filter((f) => f.ownerId !== me && living(f));
  add('beginManeuver', { expectedSequenceNumber: state.sequenceNumber }, 3);
  const attacks: Array<Record<string, unknown>> = [];
  for (const f of mine) {
    for (const t of enemies) {
      for (const c of hand) {
        if (c.cardType === 'ATTACK' || c.cardType === 'VERSATILE') attacks.push({ attackerId: f.id, targetId: t.id, cardId: c.id });
      }
    }
  }
  dice.sample(attacks, 12).forEach((a) => add('attack', a, 5 / Math.max(1, Math.min(12, attacks.length)) * 3));
  hand.filter((c) => c.cardType === 'SCHEME').forEach((c) => add('playScheme', { cardId: c.id }, 2, 'scheme'));
  add('endTurn', {}, (state.metadata.actionsRemaining ?? 0) > 0 ? 0.3 : 5);
  [...stanceIdsOf(state, me), 'no-such-stance'].forEach((id) => add('setStance', { stanceId: id }, 0.3, 'stance'));
  const cell = dice.pick(boardCells(state));
  if (cell) add('toggleDoor', { x: cell.x, y: cell.y }, 0.2, 'door');
  const mover = dice.pick(mine);
  const step = mover ? dice.pick(neighbours(state.boardState, mover.position)) : undefined;
  if (mover && step) add('moveFighter', { fighterId: mover.id, x: step.x, y: step.y }, 0.2, 'moveFighter');
  add('pass', {}, 0.1);
  return out;
}

export async function candidatesFor(
  state: GameState,
  dice: Dice,
  executor: GameActionExecutorService,
  clockMs: number,
): Promise<Candidate[]> {
  const meta = state.metadata;
  const head = meta.pendingEffects?.[0];
  if (head) {
    const fallback = await executor.buildSystemPendingFallback(head, state);
    return pendingCandidates(state, head, dice, fallback);
  }
  if (meta.pendingHandDiscard) {
    const { id, playerId, count } = meta.pendingHandDiscard;
    const hand = state.handZones[playerId]?.cards ?? [];
    return [0, 1, 2].map(() => ({
      kind: 'discardToLimit' as const, userId: playerId, weight: 1, label: 'discardToLimit',
      input: { gameId: state.gameId, pendingId: id, cardIds: dice.sample(hand, count).map((c) => c.id) },
    }));
  }
  if (meta.pendingManeuver) {
    return maneuverCandidates(state, meta.pendingManeuver.id, meta.pendingManeuver.playerId, dice);
  }
  if (meta.combatInfo && (state.phase === GamePhase.COMBAT || state.phase === GamePhase.COMBAT_RESOLVE)) {
    return combatCandidates(state, clockMs);
  }
  return actionCandidates(state, dice);
}

/** Weighted order without replacement (Efraimidis–Spirakis keys). */
export function weightedOrder(cands: readonly Candidate[], dice: Dice): Candidate[] {
  return cands
    .map((c) => ({ c, key: Math.log(Math.max(dice.float(), 1e-12)) / Math.max(c.weight, 1e-6) }))
    .sort((a, b) => b.key - a.key)
    .map((x) => x.c);
}

// ---------------------------------------------------------------------------
// Invariants
// ---------------------------------------------------------------------------

export class SelfPlayViolation extends Error {}

const projector = new GameStateService({} as any, {} as any);

function liveZones(state: GameState): Array<{ owner: string; zone: string; ids: string[] }> {
  const zones: Array<{ owner: string; zone: string; ids: string[] }> = [];
  for (const [uid, hand] of Object.entries(state.handZones)) zones.push({ owner: uid, zone: 'hand', ids: hand.cards.map((c) => c.id) });
  for (const [uid, deck] of Object.entries(state.decks)) zones.push({ owner: uid, zone: 'drawPile', ids: deck.drawPile.map((c) => c.id) });
  for (const [uid, pile] of Object.entries(state.discardPiles)) zones.push({ owner: uid, zone: 'discard', ids: (pile ?? []).map((c) => c.id) });
  for (const p of state.metadata.pendingEffects ?? []) {
    if (p.revealedCards?.length) zones.push({ owner: p.playerId, zone: `pending(${p.id})`, ids: p.revealedCards.map((c) => c.id) });
  }
  return zones;
}

export function cardBaseline(state: GameState): Map<string, number> {
  const baseline = new Map<string, number>();
  for (const z of liveZones(state)) for (const id of z.ids) baseline.set(id, (baseline.get(id) ?? 0) + 1);
  return baseline;
}

function violation(where: string, message: string): never {
  throw new SelfPlayViolation(`[${where}] ${message}`);
}

/** Cards: each instance once per zone, in one zone, the multiset of the deal conserved. */
export function checkCards(state: GameState, baseline: Map<string, number>, where: string): void {
  const seen = new Map<string, string[]>();
  for (const z of liveZones(state)) {
    const inZone = new Set<string>();
    for (const id of z.ids) {
      if (inZone.has(id)) violation(where, `card '${id}' twice in ${z.owner}/${z.zone}`);
      inZone.add(id);
      seen.set(id, [...(seen.get(id) ?? []), `${z.owner}/${z.zone}`]);
    }
  }
  for (const [id, at] of seen) if (at.length > 1) violation(where, `card '${id}' in ${at.length} zones: ${at.join(' + ')}`);
  for (const id of seen.keys()) if (!baseline.has(id)) violation(where, `card '${id}' appeared from nowhere`);
  for (const id of baseline.keys()) if (!seen.has(id)) violation(where, `card '${id}' vanished`);
}

/** Every invariant of one state; `prev` is the state before the accepted command. */
export function checkInvariants(state: GameState, prev: GameState | null, baseline: Map<string, number>, where: string): void {
  checkCards(state, baseline, where);
  for (const f of state.fighters) {
    if (!(f.health >= 0 && f.health <= f.maxHealth)) violation(where, `fighter ${f.id} hp ${f.health}/${f.maxHealth}`);
  }
  if (prev && state.sequenceNumber !== prev.sequenceNumber + 1) {
    violation(where, `seq ${prev.sequenceNumber} -> ${state.sequenceNumber}, expected +1`);
  }
  const deadHero = state.fighters.find((f) => f.type === FighterType.HERO && f.health <= 0);
  if (deadHero && state.phase !== GamePhase.GAME_OVER) {
    violation(where, `hero ${deadHero.id} is defeated but phase is ${state.phase}`);
  }
  if (prev?.metadata.winnerId && state.metadata.winnerId !== prev.metadata.winnerId) {
    violation(where, `winner changed ${prev.metadata.winnerId} -> ${state.metadata.winnerId}`);
  }

  // storage round-trip (Postgres path) is lossless
  const once = JSON.stringify(serializeGameState(state));
  const twice = JSON.stringify(serializeGameState(deserializeGameState(JSON.parse(once))));
  if (once !== twice) violation(where, 'serialize/deserialize round-trip changed the state');

  // projections: no RNG state, no hidden card of the other side, no deck order
  for (const viewer of playersOf(state)) {
    const projected = projector.filterPrivateData(state, viewer);
    if ('rng' in projected.metadata) violation(where, `projection for ${viewer} carries metadata.rng`);
    // metadata.lastCombat and metadata.lastMovement are public records of the
    // last combat and the last maneuver: they keep the instance ids of the
    // cards revealed face up there (combat cards, the discarded BOOST card),
    // also after a later public effect returns such a card to a hidden zone
    // (The Lady of the Lake takes Excalibur from the discard pile back to the
    // hand — seeds 9039, 9121, 9127, 9159, 9203, 9527, 9774 of 9000..9999).
    // By the rules that tells the opponent nothing new; the owner-only
    // `hidden` part of lastCombat is checked by the R-01 specs. Everything
    // else in the projection is scanned strictly.
    const metadata: Record<string, unknown> = { ...projected.metadata };
    delete metadata.lastCombat;
    delete metadata.lastMovement;
    const json = JSON.stringify({ ...projected, metadata });
    const hidden = new Set<string>();
    for (const [uid, hand] of Object.entries(state.handZones)) if (uid !== viewer) hand.cards.forEach((c) => hidden.add(c.id));
    for (const deck of Object.values(state.decks)) deck.drawPile.forEach((c) => hidden.add(c.id));
    for (const p of state.metadata.pendingEffects ?? []) {
      if (p.playerId !== viewer) (p.revealedCards ?? []).forEach((c) => hidden.add(c.id));
    }
    for (const id of hidden) {
      if (json.includes(JSON.stringify(id))) violation(where, `projection for ${viewer} reveals hidden card '${id}'`);
    }
  }
}

function deepFreeze<T>(value: T): T {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const v of Object.values(value as Record<string, unknown>)) deepFreeze(v);
  }
  return value;
}

// ---------------------------------------------------------------------------
// The game loop
// ---------------------------------------------------------------------------

export interface SelfPlayResult {
  readonly start: GameState;
  readonly state: GameState;
  /** accepted commands with the seq and canonical hash of their result */
  readonly journal: ReplayCommandRow[];
  /** accepted / rejected attempts per candidate label */
  readonly coverage: Record<string, { accepted: number; rejected: number }>;
  readonly finished: boolean;
}

/** Virtual clock: a fixed start, 1 s per command, an occasional jump over the combat deadlines. */
const CLOCK_START = Date.parse('2026-10-20T12:00:00.000Z');

export async function runSelfPlay(opts: SelfPlayOptions): Promise<SelfPlayResult> {
  const { executor } = s03Engine({ abilities: true });
  const dice = new Dice(rngFromSeed(`policy:${opts.seed}`));
  const maxCommands = opts.maxCommands ?? 3000;
  const tag = `seed ${opts.seed} ${opts.board} ${opts.heroes.join('/')} first=${opts.first}`;
  const coverage: Record<string, { accepted: number; rejected: number }> = {};
  const count = (label: string, ok: boolean) => {
    const row = (coverage[label] ??= { accepted: 0, rejected: 0 });
    if (ok) row.accepted++;
    else row.rejected++;
  };

  const start = await startSelfPlayGame(opts);
  const baseline = cardBaseline(start);
  checkInvariants(start, null, baseline, `${tag} deal`);
  let state = deepFreeze(start);
  let clock = CLOCK_START;
  const journal: ReplayCommandRow[] = [];
  const tail: string[] = [];

  const run = async (cand: Candidate, at: GameState) => {
    const command: GameCommand = {
      kind: cand.kind, userId: cand.userId, input: cand.input, now: new Date(clock).toISOString(),
      ...(cand.system ? { system: true } : {}),
    };
    try {
      return { command, result: await executeGameCommand(executor, command, at) };
    } catch (error) {
      return violation(`${tag} step ${journal.length} ${cand.label}`, `executor threw: ${(error as Error).stack ?? error}`);
    }
  };

  while (journal.length < maxCommands && state.phase !== GamePhase.GAME_OVER) {
    if (dice.chance(0.04)) clock += 31_000; // past the defense / resolve deadline
    const where = `${tag} step ${journal.length} seq ${state.sequenceNumber}`;

    // out-of-turn probe: the player not on turn can neither begin a maneuver nor end the turn
    if (!state.metadata.combatInfo && !state.metadata.pendingEffects?.length) {
      const idle = otherPlayer(state, state.currentTurnPlayerId);
      const probe: Candidate = dice.chance(0.5)
        ? { kind: 'endTurn', userId: idle, input: { gameId: state.gameId }, weight: 1, label: 'probe:endTurn' }
        : { kind: 'beginManeuver', userId: idle, input: { gameId: state.gameId, expectedSequenceNumber: state.sequenceNumber }, weight: 1, label: 'probe:beginManeuver' };
      const { result } = await run(probe, state);
      if (result.success) violation(where, `out-of-turn ${probe.kind} by ${idle} was accepted`);
    }

    let accepted = false;
    const tried: string[] = [];
    for (const cand of weightedOrder(await candidatesFor(state, dice, executor, clock), dice)) {
      const { command, result } = await run(cand, state);
      count(cand.label, result.success);
      if (!result.success || !result.gameState) {
        tried.push(`${cand.userId}:${cand.label} → ${result.error}`);
        continue;
      }
      const next = result.gameState;
      checkInvariants(next, state, baseline, `${where} ${cand.label}`);
      journal.push({ seq: next.sequenceNumber, command, hash: canonicalStateHash(serializeGameState(next)) });
      tail.push(`${cand.userId}:${cand.label}`);
      if (tail.length > 12) tail.shift();
      state = deepFreeze(next);
      clock += 1000;
      accepted = true;
      break;
    }
    if (!accepted) {
      violation(where, `liveness: no candidate accepted (phase ${state.phase}). Tried: ${tried.slice(0, 20).join(' | ')}. Tail: ${tail.join(' ; ')}`);
    }
  }

  if (state.phase === GamePhase.GAME_OVER) {
    // GAME_OVER is final: nothing a client or the server could send is accepted
    const after = [
      ...(await candidatesFor(state, dice, executor, clock + 120_000)),
      ...playersOf(state).flatMap((u) => [
        { kind: 'endTurn' as const, userId: u, input: { gameId: state.gameId }, weight: 1, label: 'post:endTurn' },
        { kind: 'beginManeuver' as const, userId: u, input: { gameId: state.gameId, expectedSequenceNumber: state.sequenceNumber }, weight: 1, label: 'post:beginManeuver' },
      ]),
    ];
    for (const cand of after) {
      const { result } = await run(cand, state);
      if (result.success) violation(`${tag} after GAME_OVER`, `${cand.userId}:${cand.label} was accepted`);
    }
  }
  return { start, state, journal, coverage, finished: state.phase === GamePhase.GAME_OVER };
}

/** Replay a self-play game from its start snapshot with a fresh executor. */
export async function replaySelfPlay(game: SelfPlayResult): Promise<ReplayResult> {
  const start: StartSnapshot = { format: REPLAY_FORMAT_VERSION, engine: engineVersion(), state: serializeGameState(game.start) };
  return replayGame(s03Engine({ abilities: true }).executor, start, game.journal);
}
