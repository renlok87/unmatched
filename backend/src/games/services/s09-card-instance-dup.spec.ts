/**
 * S09 regression: can live GameState hold the SAME card instance id twice in
 * one hand, or in two zones at once? Evidence trigger: capture-pending-fixtures
 * observed 'A Momentary Glance ::1' twice in one hand (2026-09-27).
 *
 * Harness = GD-024 (s06-full-games) with an invariant checker invoked after
 * EVERY successful mutation, driven across many seeded duels (Medusa vs
 * King Arthur, hero + first-player swaps). Invariants:
 *   A) no instance id repeats inside one zone array (hand/drawPile/discard);
 *   B) no instance id lives in two different zones at once (pendings with
 *      revealedCards count as their own zone — creation removes them from
 *      drawPile, resolution returns them);
 *   C) multiset of instance ids is conserved from the initial deal
 *      (no reshuffle/exile exists — cards never vanish or multiply).
 * decks[].cards is a full-deck catalog, NOT a live zone — excluded.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { GameService } from '../game.service';
import { GameInitializationService } from './game-initialization.service';
import { GameState, GameStateService } from '../game-state.service';
import { GamePhase } from '../../game-engine/models';
import { getCellZones, getFighterAttackType, getFighterMovement } from '../../game-engine/models';
import { bannerAllows } from '../../game-engine/validators/game-rules.validator';
import { s03Engine } from '../../test/fixtures/s03-engine.fixture';
import type { Fighter, PendingEffect } from '../../game-engine/models';

const root = resolve(__dirname, '../../../..');
const source = JSON.parse(
  readFileSync(resolve(root, 'docs/game-design/evidence/S01/content-board.json'), 'utf8'),
).adminBoard;
const medusaCapture = JSON.parse(
  readFileSync(resolve(root, 'docs/game-design/evidence/S01/content-medusa.json'), 'utf8'),
);
const arthurCapture = JSON.parse(
  readFileSync(resolve(root, 'docs/game-design/evidence/S01/content-king-arthur.json'), 'utf8'),
);

const dbCards = (cards: any[]) => cards.map((c) => ({ ...c, text: c.textEn }));
const heroes: Record<string, any> = {
  medusa: {
    id: medusaCapture.id, name: medusaCapture.name, health: medusaCapture.health,
    movement: medusaCapture.movement, fighterType: 'HERO',
    properties: { attackType: 'ranged' },
    sidekicks: [{ name: 'Harpy', count: 3, health: 1 }],
    cards: dbCards(medusaCapture.cards),
  },
  arthur: {
    id: arthurCapture.id, name: arthurCapture.name, health: arthurCapture.health,
    movement: arthurCapture.movement, fighterType: 'HERO',
    properties: { attackType: 'ranged' },
    sidekicks: [{ name: 'Merlin', health: 7, attackType: 'ranged' }],
    cards: dbCards(arthurCapture.cards),
  },
};

function makeDb() {
  const games = new Map<string, any>();
  const players = new Map<string, any>();
  const states = new Map<string, any>();
  const user = (id: string) => ({ id, username: `user-${id}`, avatar: null });
  const gameRow = (id: string) => {
    const game = games.get(id);
    if (!game) return null;
    const roster = [...players.values()].filter(p => p.gameId === id).sort((a, b) => a.seatOrder - b.seatOrder);
    return {
      ...game, host: user(game.hostId), opponent: game.opponentId ? user(game.opponentId) : null,
      players: roster.map(p => ({ ...p, user: user(p.userId) })), state: states.get(id) ?? null,
    };
  };
  let txTail = Promise.resolve();
  const serializeTx = (run: (tx: unknown) => unknown) => {
    const previous = txTail;
    let done!: () => void;
    txTail = new Promise<void>(yes => { done = yes; });
    return previous.then(() => Promise.resolve(run(prisma))).finally(() => done());
  };
  const prisma: any = {
    game: {
      findUnique: async ({ where }: any) => (where.id ? gameRow(where.id) : games.get(where.code) ?? null),
      update: async ({ where, data }: any) => {
        const game = games.get(where.id);
        games.set(where.id, { ...game, ...data });
        return games.get(where.id);
      },
    },
    gamePlayer: {
      findMany: async ({ where }: any) =>
        [...players.values()].filter(p => p.gameId === where.gameId)
          .sort((a, b) => a.seatOrder - b.seatOrder),
      create: async ({ data }: any) => { players.set(`${data.gameId}:${data.userId}`, data); return data; },
      update: async () => ({}),
      updateMany: async () => ({}),
      deleteMany: async () => ({ count: 0 }),
    },
    hero: { findUnique: async ({ where }: any) => heroes[where.id] ?? null },
    board: { findUnique: async ({ where }: any) => (where.id === source.id ? source : null) },
    gameState: {
      findUnique: async ({ where }: any) => states.get(where.gameId) ?? null,
      upsert: async ({ where, create }: any) => { states.set(where.gameId, create); return create; },
    },
    $transaction: serializeTx,
    $queryRaw: async () => [],
  };
  const redis = { getJson: async () => null, setJsonex: async () => 'OK', del: async () => 1 };
  return { prisma, redis, games, players, states };
}

function startFullGame(heroU1: 'medusa' | 'arthur', firstUserId: 'u1' | 'u2'): Promise<GameState> {
  const db = makeDb();
  const heroU2 = heroU1 === 'medusa' ? 'arthur' : 'medusa';
  db.games.set('g1', { id: 'g1', hostId: 'u1', opponentId: 'u2', boardId: source.id,
    mode: 'ONE_V_ONE', status: 'LOBBY', code: 'AAAAAA', version: 0 });
  const seat = (userId: string) => (userId === firstUserId ? 0 : 1);
  db.players.set('g1:u1', { id: 'p1', gameId: 'g1', userId: 'u1', seatOrder: seat('u1'), heroId: heroU1, isReady: true });
  db.players.set('g1:u2', { id: 'p2', gameId: 'g1', userId: 'u2', seatOrder: seat('u2'), heroId: heroU2, isReady: true });
  const saveState = jest.fn(async (_gameId: string, _state: GameState) => undefined);
  const service = new GameService(
    db.prisma,
    db.redis as any,
    new GameInitializationService(db.prisma, { saveState } as any),
    { recordAction: async () => 'id' } as any,
    { publishLobbyEvent: async () => ({}) } as any,
  );
  return service.startGame('g1', 'u1').then(() => saveState.mock.calls[0][1] as GameState);
}

function lcg(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

// --- Invariants -------------------------------------------------------------
interface ZoneRef { owner: string; zone: string; ids: string[] }

function liveZones(state: GameState): ZoneRef[] {
  const zones: ZoneRef[] = [];
  for (const uid of Object.keys(state.handZones)) {
    zones.push({ owner: uid, zone: 'hand', ids: state.handZones[uid].cards.map((c) => c.id) });
  }
  for (const uid of Object.keys(state.decks)) {
    zones.push({ owner: uid, zone: 'drawPile', ids: state.decks[uid].drawPile.map((c) => c.id) });
  }
  for (const uid of Object.keys(state.discardPiles)) {
    zones.push({ owner: uid, zone: 'discard', ids: (state.discardPiles[uid] ?? []).map((c) => c.id) });
  }
  for (const p of (state.metadata.pendingEffects ?? []) as PendingEffect[]) {
    if (p.revealedCards?.length) {
      zones.push({ owner: p.playerId ?? '?', zone: `pending(${p.id})`, ids: p.revealedCards.map((c) => c.id) });
    }
  }
  return zones;
}

function checkInvariants(
  state: GameState,
  baseline: Map<string, number>,
  where: string,
) {
  const zones = liveZones(state);
  const seen = new Map<string, string[]>();
  for (const z of zones) {
    const inZone = new Set<string>();
    for (const id of z.ids) {
      if (inZone.has(id)) {
        throw new Error(`[${where}] INVARIANT A: instance id '${id}' twice in ${z.owner}/${z.zone}`);
      }
      inZone.add(id);
      seen.set(id, [...(seen.get(id) ?? []), `${z.owner}/${z.zone}`]);
    }
  }
  for (const [id, at] of seen) {
    if (at.length > 1) {
      throw new Error(`[${where}] INVARIANT B: instance id '${id}' in ${at.length} zones at once: ${at.join(' + ')}`);
    }
  }
  const counts = new Map<string, number>();
  for (const z of zones) for (const id of z.ids) counts.set(id, (counts.get(id) ?? 0) + 1);
  for (const [id, n] of counts) {
    if (!baseline.has(id)) {
      throw new Error(`[${where}] INVARIANT C: unknown instance id '${id}' appeared from nowhere`);
    }
    if (n !== baseline.get(id)) {
      throw new Error(`[${where}] INVARIANT C: instance id '${id}' count ${n} != baseline ${baseline.get(id)}`);
    }
  }
  for (const [id] of baseline) {
    if (!counts.has(id)) {
      throw new Error(`[${where}] INVARIANT C: instance id '${id}' vanished`);
    }
  }
}

// --- Policy helpers (GD-024 policies, unchanged semantics) -------------------
const living = (st: GameState, uid: string): Fighter[] =>
  st.fighters.filter((f) => f.ownerId === uid && !f.isDefeated && f.health > 0);
const manhattan = (a: { x: number; y: number }, b: { x: number; y: number }) =>
  Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
const zonesOf = (st: GameState, p: { x: number; y: number }) =>
  new Set(getCellZones(st.boardState.cells[p.y]?.[p.x]));
function canReachTarget(st: GameState, atk: Fighter, tgt: Fighter): boolean {
  const d = manhattan(atk.position, tgt.position);
  if (d === 1) return true;
  if (getFighterAttackType(atk) === 'melee') return false;
  const za = zonesOf(st, atk.position);
  return [...zonesOf(st, tgt.position)].some((z) => za.has(z));
}
function greedyPath(st: GameState, f: Fighter): Array<{ x: number; y: number }> {
  const enemies = st.fighters.filter((e) => e.ownerId !== f.ownerId && !e.isDefeated && e.health > 0);
  if (enemies.length === 0) return [];
  const target = enemies.reduce((best, e) => (manhattan(f.position, e.position) < manhattan(f.position, best.position) ? e : best));
  const occupied = new Set(
    st.fighters
      .filter((e) => e.id !== f.id && !e.isDefeated && e.health > 0)
      .map((e) => `${e.position.x}:${e.position.y}`),
  );
  const board = st.boardState;
  const free = (p: { x: number; y: number }) =>
    p.x >= 0 && p.y >= 0 && p.x < board.width && p.y < board.height && !occupied.has(`${p.x}:${p.y}`);
  let pos = { ...f.position };
  const path: Array<{ x: number; y: number }> = [];
  for (let s = 0; s < getFighterMovement(f); s++) {
    if (manhattan(pos, target.position) <= 1) break;
    const dx = Math.sign(target.position.x - pos.x);
    const dy = Math.sign(target.position.y - pos.y);
    const cands: Array<{ x: number; y: number }> = [];
    if (Math.abs(target.position.x - pos.x) >= Math.abs(target.position.y - pos.y)) {
      if (dx !== 0) cands.push({ x: pos.x + dx, y: pos.y });
      if (dy !== 0) cands.push({ x: pos.x, y: pos.y + dy });
    } else {
      if (dy !== 0) cands.push({ x: pos.x, y: pos.y + dy });
      if (dx !== 0) cands.push({ x: pos.x + dx, y: pos.y });
    }
    const step = cands.find(free);
    if (!step) break;
    pos = step;
    path.push(step);
  }
  return path;
}

interface StepLog { step: number; seq: number; actor: string; action: string; ok: boolean; err?: string }

async function runFullGame(opts: { seed: number; heroU1: 'medusa' | 'arthur'; first: 'u1' | 'u2' }): Promise<{ state: GameState; transcript: StepLog[] }> {
  const { executor } = s03Engine();
  const rng = lcg(opts.seed);
  const origRandom = Math.random;
  Math.random = rng;
  const transcript: StepLog[] = [];
  let fails = 0;
  let lastAction = '';
  try {
    let state = await startFullGame(opts.heroU1, opts.first);

    const baseline = new Map<string, number>();
    for (const z of liveZones(state)) for (const id of z.ids) baseline.set(id, (baseline.get(id) ?? 0) + 1);
    checkInvariants(state, baseline, `seed ${opts.seed} initial deal`);

    const exec = async (actor: string, action: string, run: () => Promise<{ success: boolean; gameState?: GameState; error?: string }>) => {
      const res = await run();
      if (res.success && res.gameState) {
        state = res.gameState;
        checkInvariants(state, baseline, `seed ${opts.seed} step ${transcript.length} ${action} (seq ${state.sequenceNumber})`);
        fails = 0;
      } else {
        fails++;
      }
      transcript.push({ step: transcript.length, seq: state.sequenceNumber, actor, action, ok: res.success, err: res.error });
      return res;
    };
    const uid = (p: PendingEffect) => p.playerId!;
    const resolvePending = async (p: PendingEffect) => {
      const base = { gameId: 'g1', effectId: p.id } as any;
      const me = uid(p);
      const myHand = state.handZones[me]?.cards ?? [];
      switch (p.type) {
        case 'CHOOSE_ONE':
          return exec(me, 'resolveChooseOne', () => executor.executeResolvePendingEffect(
            { ...base, optionIndex: 0 }, { userId: me, gameId: 'g1', currentState: state } as any));
        case 'TARGET_FIGHTER': {
          const ids = p.targetFighterIds ?? [];
          if (ids.length === 0) {
            return exec(me, 'decline', () => executor.executeDeclinePendingEffect(base, { userId: me, gameId: 'g1', currentState: state } as any));
          }
          return exec(me, `resolveTarget ${ids[0]}`, () => executor.executeResolvePendingEffect(
            { ...base, fighterId: ids[0] }, { userId: me, gameId: 'g1', currentState: state } as any));
        }
        case 'BOOST_CHOICE': {
          const boostable = myHand.filter((c) => (c.boostValue ?? 0) > 0);
          if (boostable.length > 0) {
            return exec(me, `resolveBoost ${boostable[0].id}`, () => executor.executeResolvePendingEffect(
              { ...base, cardIds: [boostable[0].id] }, { userId: me, gameId: 'g1', currentState: state } as any));
          }
          return exec(me, 'declineBoost', () => executor.executeDeclinePendingEffect(base, { userId: me, gameId: 'g1', currentState: state } as any));
        }
        case 'DISCARD_CARDS': {
          const n = p.value ?? 1;
          const ids = myHand.slice(0, n).map((c) => c.id);
          return exec(me, `resolveDiscard ${n}`, () => executor.executeResolvePendingEffect(
            { ...base, cardIds: ids }, { userId: me, gameId: 'g1', currentState: state } as any));
        }
        case 'DECK_TOP_PICK': {
          const revealed = p.revealedCards ?? [];
          if ((p.mode ?? 'PICK') === 'PICK') {
            const ids = revealed.slice(0, p.value ?? 2).map((c) => c.id);
            return exec(me, `resolveDeckPick ${ids.length}`, () => executor.executeResolvePendingEffect(
              { ...base, cardIds: ids }, { userId: me, gameId: 'g1', currentState: state } as any));
          }
          return exec(me, `resolveDeckOrder ${revealed.length}`, () => executor.executeResolvePendingEffect(
            { ...base, cardIds: revealed.map((c) => c.id) }, { userId: me, gameId: 'g1', currentState: state } as any));
        }
        case 'CHOOSE_SPACE': {
          const ctx = { userId: me, gameId: 'g1', currentState: state } as any;
          if (p.stage !== 2) {
            const anchor = state.fighters.find((f) => f.name.includes(p.zoneFighterName ?? '###'));
            const pt = anchor ? anchor.position : { x: 1, y: 1 };
            return exec(me, `chooseSpace1 ${pt.x},${pt.y}`, () => executor.executeResolvePendingEffect(
              { ...base, x: pt.x, y: pt.y }, ctx));
          }
          const a = p.anchor!;
          for (const cand of [
            { x: a.x + 1, y: a.y }, { x: a.x - 1, y: a.y }, { x: a.x, y: a.y + 1 }, { x: a.x, y: a.y - 1 },
          ]) {
            const res = await executor.executeResolvePendingEffect({ ...base, x: cand.x, y: cand.y }, ctx);
            if (res.success && res.gameState) {
              state = res.gameState;
              checkInvariants(state, baseline, `seed ${opts.seed} step ${transcript.length} chooseSpace2 (seq ${state.sequenceNumber})`);
              transcript.push({ step: transcript.length, seq: state.sequenceNumber, actor: me, action: `chooseSpace2 ${cand.x},${cand.y}`, ok: true });
              return res;
            }
          }
          return { success: false, error: 'no adjacent cell' };
        }
        case 'MOVE':
        case 'PLACE': {
          const fid = p.fighterIds?.[0];
          if (!fid) {
            return exec(me, 'decline', () => executor.executeDeclinePendingEffect(base, { userId: me, gameId: 'g1', currentState: state } as any));
          }
          const f = state.fighters.find((x) => x.id === fid);
          const pos = f?.position ?? { x: 0, y: 0 };
          const ctx = { userId: me, gameId: 'g1', currentState: state } as any;
          // stay-in-place first (legal for mandatory MOVE without free cells)
          const stay = await executor.executeResolvePendingEffect(
            { ...base, fighterId: fid, x: pos.x, y: pos.y }, ctx);
          if (stay.success && stay.gameState) {
            state = stay.gameState;
            checkInvariants(state, baseline, `seed ${opts.seed} step ${transcript.length} resolveMove stay (seq ${state.sequenceNumber})`);
            transcript.push({ step: transcript.length, seq: state.sequenceNumber, actor: me, action: `resolveMove ${fid} stay`, ok: true });
            return stay;
          }
          // PLACE/revive needs a genuinely free cell (Winged Frenzy revives a
          // defeated Harpy whose old cell may be taken): scan the whole board,
          // honouring zone restrictions when the pending names one.
          const anchor = p.zoneFighterName
            ? state.fighters.find((x) => x.name.includes(p.zoneFighterName!))
            : undefined;
          const anchorZones = anchor ? zonesOf(state, anchor.position) : null;
          const takenBy = new Set(
            state.fighters
              .filter((x) => x.id !== fid && !x.isDefeated && x.health > 0)
              .map((x) => `${x.position.x}:${x.position.y}`),
          );
          for (let y = 0; y < state.boardState.height; y++) {
            for (let x = 0; x < state.boardState.width; x++) {
              const cell = state.boardState.cells[y]?.[x];
              if (!cell || cell.type === 'obstacle' || cell.type === 'wall') continue;
              if (takenBy.has(`${x}:${y}`)) continue;
              if (anchorZones && anchorZones.size > 0) {
                const cz = new Set(getCellZones(cell));
                if (![...anchorZones].some((z) => cz.has(z))) continue;
              }
              const res = await executor.executeResolvePendingEffect(
                { ...base, fighterId: fid, x, y }, ctx);
              if (res.success && res.gameState) {
                state = res.gameState;
                checkInvariants(state, baseline, `seed ${opts.seed} step ${transcript.length} resolveMove ${fid}->${x},${y} (seq ${state.sequenceNumber})`);
                transcript.push({ step: transcript.length, seq: state.sequenceNumber, actor: me, action: `resolveMove ${fid}->${x},${y}`, ok: true });
                return res;
              }
            }
          }
          transcript.push({ step: transcript.length, seq: state.sequenceNumber, actor: me, action: `resolveMove ${fid} nowhere`, ok: false, err: stay.error });
          fails++;
          return stay;
        }
        default:
          return exec(me, `decline:${p.type}`, () => executor.executeDeclinePendingEffect(base, { userId: me, gameId: 'g1', currentState: state } as any));
      }
    };

    const MAX_STEPS = 2000;
    for (let i = 0; i < MAX_STEPS; i++) {
      if (state.phase === GamePhase.GAME_OVER) break;
      if (fails > 40) {
        throw new Error(`policy stuck after "${lastAction}" (40 consecutive fails). Tail: ${JSON.stringify(transcript.slice(-14), null, 1)}`);
      }

      const pending = state.metadata.pendingEffects?.[0];
      if (pending) {
        lastAction = `pending:${pending.type}`;
        await resolvePending(pending);
        continue;
      }
      const discard = state.metadata.pendingHandDiscard;
      if (discard) {
        lastAction = 'discardToLimit';
        const hand = state.handZones[discard.playerId]?.cards ?? [];
        await exec(discard.playerId, `discardToLimit ${discard.count}`, () => executor.executeDiscardToLimit(
          { gameId: 'g1', pendingId: discard.id, cardIds: hand.slice(0, discard.count).map((c) => c.id) },
          { userId: discard.playerId, gameId: 'g1', currentState: state } as any));
        continue;
      }
      const manPending = state.metadata.pendingManeuver;
      if (manPending) {
        lastAction = 'maneuver';
        const me = manPending.playerId;
        const moves = living(state, me)
          .map((f) => ({ fighterId: f.id, path: greedyPath(state, f) }))
          .filter((m) => m.path.length > 0);
        await exec(me, `maneuver moves=${moves.length}`, () => executor.executeManeuver(
          { gameId: 'g1', maneuverId: manPending.id, moves } as any,
          { userId: me, gameId: 'g1', currentState: state } as any));
        continue;
      }
      const combat = state.metadata.combatInfo;
      if (combat) {
        const attacker = combat.attackerId;
        const defender = combat.defenderId;
        if (!combat.defenderCardId) {
          const defHand = state.handZones[defender]?.cards ?? [];
          const defendingFighter =
            state.fighters.find((f) => f.id === combat.targetFighterId) ??
            state.fighters.find((f) => f.ownerId === defender && !f.isDefeated);
          const defCard = defHand.find((c) =>
            (c.cardType === 'DEFENSE' || (c.cardType === 'VERSATILE' && (c.defenseValue ?? 0) > 0)) &&
            defendingFighter && bannerAllows(c.bannerName ?? 'Any', defendingFighter));
          if (defCard) {
            lastAction = 'defense';
            await exec(defender, `defense ${defCard.name}`, () => executor.executePlayDefense(
              { gameId: 'g1', cardId: defCard.id }, { userId: defender, gameId: 'g1', currentState: state } as any));
            continue;
          }
        }
        lastAction = 'resolveCombat';
        await exec(defender, 'resolveCombat', () => executor.executeResolveCombat(
          { gameId: 'g1' }, { userId: defender, gameId: 'g1', currentState: state } as any));
        continue;
      }

      const me = state.currentTurnPlayerId;
      const actionsLeft = state.metadata.actionsRemaining ?? 0;
      if (actionsLeft <= 0) {
        lastAction = 'endTurn';
        await exec(me, 'endTurn', () => executor.executeEndTurn(
          { gameId: 'g1' } as any, { userId: me, gameId: 'g1', currentState: state } as any));
        continue;
      }

      const myFighters = living(state, me);
      const hand = state.handZones[me]?.cards ?? [];
      let attacked = false;
      outer:
      for (const f of myFighters) {
        const card = hand.find(
          (c) => (c.cardType === 'ATTACK' || (c.cardType === 'VERSATILE' && c.attackValue)) &&
            bannerAllows(c.bannerName ?? 'Any', f));
        if (!card) continue;
        for (const tgt of state.fighters.filter((e) => e.ownerId !== me && !e.isDefeated && e.health > 0)) {
          if (!canReachTarget(state, f, tgt)) continue;
          lastAction = `attack ${card.name}`;
          await exec(me, `attack ${f.id}->${tgt.id} ${card.name}`, () => executor.executeAttack(
            { gameId: 'g1', attackerId: f.id, targetId: tgt.id, cardId: card.id } as any,
            { userId: me, gameId: 'g1', currentState: state } as any));
          attacked = true;
          break outer;
        }
      }
      if (attacked) continue;

      const scheme = hand.find((c) => c.cardType === 'SCHEME' && c.bannerName);
      if (scheme) {
        const banner = scheme.bannerName!;
        const bannerOk =
          banner.toLowerCase() === 'any' ||
          state.fighters.some((x) => x.ownerId === me && !x.isDefeated && bannerAllows(banner, x));
        if (bannerOk) {
          lastAction = `scheme ${scheme.name}`;
          await exec(me, `scheme ${scheme.name}`, () => executor.executePlayScheme(
            { gameId: 'g1', cardId: scheme.id }, { userId: me, gameId: 'g1', currentState: state } as any));
          continue;
        }
      }

      lastAction = 'beginManeuver';
      const begun = await exec(me, 'beginManeuver', () => executor.executeBeginManeuver(
        { gameId: 'g1', expectedSequenceNumber: state.sequenceNumber },
        { userId: me, gameId: 'g1', currentState: state } as any));
      if (!begun.success) {
        await exec(me, 'endTurn(noMoves)', () => executor.executeEndTurn(
          { gameId: 'g1' } as any, { userId: me, gameId: 'g1', currentState: state } as any));
      }
    }

    checkInvariants(state, baseline, `seed ${opts.seed} final`);
    return { state, transcript };
  } finally {
    Math.random = origRandom;
  }
}

describe('S09: card instance id uniqueness across zones in full driven duels', () => {
  it.each(
    Array.from({ length: 60 }, (_, i) => ({ seed: 9000 + i, heroU1: (i % 2 ? 'arthur' : 'medusa') as 'arthur' | 'medusa', first: (i % 3 ? 'u1' : 'u2') as 'u1' | 'u2' })),
  )('seed $seed ($heroU1 first=$first): every mutation keeps instance ids unique per zone, single-zone and conserved', async ({ seed, heroU1, first }) => {
    const { state, transcript } = await runFullGame({ seed, heroU1, first });
    expect(state.phase).toBe(GamePhase.GAME_OVER);
    expect(transcript.length).toBeGreaterThan(0);
  }, 120_000);

  // Hypothesis under test (capture-pending-fixtures comment + operator notes):
  // "the live state can hold the SAME instance id on two hand entries"
  // ('A Momentary Glance ::1' twice in one hand, allegedly stable). The
  // GraphQL gameState response = loadState (DB deserialize or Redis) →
  // filterPrivateData → JSON.stringify. This test walks the exact same
  // layers with both Glance copies in one hand and after every storage
  // round-trip: the serialized → deserialized → projected → serialized →
  // deserialized hand must keep exactly the two DISTINCT instance ids.
  it('serialize/deserialize/projection round-trips never duplicate instance ids in a projected hand', async () => {
    const glanceCard = {
      id: 'glance', name: 'A Momentary Glance', nameEn: 'A Momentary Glance',
      nameRu: 'A Momentary Glance', cardType: 'SCHEME', count: 2, effects: [],
    };
    const prisma = {
      game: { findUnique: jest.fn().mockResolvedValue({ boardId: null }) },
      gamePlayer: { findMany: jest.fn().mockResolvedValue([
        { userId: 'first', heroId: 'glance-hero', seatOrder: 0 },
        { userId: 'second', heroId: 'other-hero', seatOrder: 1 },
      ]) },
      hero: { findUnique: jest.fn()
        .mockResolvedValueOnce({ id: 'glance-hero', name: 'Glance Hero', health: 10, movement: 2, sidekicks: [], cards: [glanceCard] })
        .mockResolvedValueOnce({ id: 'other-hero', name: 'Other Hero', health: 10, movement: 2, sidekicks: [], cards: [{ ...glanceCard, id: 'filler' }] }) },
    };
    const saveState = jest.fn();
    const initializer = new GameInitializationService(prisma as any, { saveState } as any);
    const initial = await initializer.initializeGameState('round-trip');
    // Force both Glance copies into one hand deterministically.
    const handIds = initial.decks.first.cards.filter((c) => c.cardId === 'glance').map((c) => c.id);
    expect(handIds).toHaveLength(2);
    expect(new Set(handIds).size).toBe(2);
    const forced: GameState = {
      ...initial,
      handZones: {
        first: { cards: initial.decks.first.cards.filter((c) => c.cardId === 'glance').map((c) => ({ ...c, isVisible: true })), maxSize: 7 },
        second: initial.handZones.second,
      },
      decks: {
        first: { ...initial.decks.first, drawPile: [], topCard: undefined },
        second: initial.decks.second,
      },
    };

    const svc = new GameStateService({} as any, {} as any, {} as any);
    let current = forced;
    for (let hop = 0; hop < 3; hop++) {
      const persisted = svc.serialize(current);           // DB column shape (compact keys)
      current = svc.deserialize(JSON.parse(JSON.stringify(persisted))); // transport round-trip
      for (const viewer of ['first', 'second']) {
        const projected = svc.filterPrivateData(current, viewer);
        const ownHand = projected.handZones[viewer].cards.map((c) => c.id).sort();
        if (viewer === 'first') {
          expect(ownHand).toEqual([...handIds].sort());
          expect(new Set(ownHand).size).toBe(2);
        } else {
          expect(projected.handZones.first.cards.map((c) => c.id)).toHaveLength(2);
          expect(new Set(projected.handZones.first.cards.map((c) => c.id)).size).toBe(2);
        }
      }
    }
  });
});
