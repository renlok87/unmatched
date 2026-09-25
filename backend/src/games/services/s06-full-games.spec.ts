/** GD-024: two deterministic FULL server games, Medusa vs King Arthur,
 * 30+30 real cards (frozen S01 captures → production startGame), scripted
 * policies, swapped heroes AND swapped first player between the games.
 * No admin corrections: every mutation goes through the REAL executor
 * (attack / defense / resolveCombat / scheme / maneuver / endTurn /
 * resolvePendingEffect for EVERY pending type the decks can produce).
 * Reproducible: seeded LCG replaces Math.random (shuffles are deterministic);
 * transcripts (seed, per-step actions, seq, HP snapshots) are written to
 * docs/game-design/evidence/S06/. */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { GameService } from '../game.service';
import { GameInitializationService } from './game-initialization.service';
import { GameState } from '../game-state.service';
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
      update: async ({ where, data }: any) => {
        const key = where.id
          ? [...players.entries()].find(([, p]) => p.id === where.id)?.[0]
          : `${where.gameId_userId.gameId}:${where.gameId_userId.userId}`;
        const player = players.get(key!);
        players.set(key!, { ...player, ...data });
        return players.get(key!);
      },
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

/** Реальный production-старт с заданным первым игроком (seatOrder 0). */
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

// --- Seeded RNG: детерминированные shuffle (init + все эффекты движка) ---
function lcg(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

// --- Policy helpers ---
const living = (st: GameState, uid: string): Fighter[] =>
  st.fighters.filter((f) => f.ownerId === uid && !f.isDefeated && f.health > 0);
const manhattan = (a: { x: number; y: number }, b: { x: number; y: number }) =>
  Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
const zonesOf = (st: GameState, p: { x: number; y: number }) =>
  new Set(getCellZones(st.boardState.cells[p.y]?.[p.x]));
/** Приближение легальности атаки (движок провалидирует сам; fail → fallback). */
function canReachTarget(st: GameState, atk: Fighter, tgt: Fighter): boolean {
  const d = manhattan(atk.position, tgt.position);
  if (d === 1) return true;
  if (getFighterAttackType(atk) === 'melee') return false;
  const za = zonesOf(st, atk.position);
  return [...zonesOf(st, tgt.position)].some((z) => za.has(z));
}
/** Жадный путь бойца к ближайшему врагу (≤ movement шагов; каждая клетка
 * свободна от живых бойцов — иначе executor отвергнет endpoint/траверсал). */
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

interface StepLog { step: number; seq: number; actor: string; action: string; ok: boolean; err?: string; note?: string }

export async function runFullGame(opts: {
  label: string; seed: number; heroU1: 'medusa' | 'arthur'; first: 'u1' | 'u2';
}): Promise<{ state: GameState; transcript: StepLog[]; hpLog: Array<{ turn: number; seq: number; hp: Record<string, number> }> }> {
  const { executor } = s03Engine();
  const rng = lcg(opts.seed);
  const origRandom = Math.random;
  Math.random = rng;
  const transcript: StepLog[] = [];
  const hpLog: Array<{ turn: number; seq: number; hp: Record<string, number> }> = [];
  let fails = 0;
  let lastAction = '';
  try {
    let state = await startFullGame(opts.heroU1, opts.first);
    const exec = async (actor: string, action: string, run: () => Promise<{ success: boolean; gameState?: GameState; error?: string }>, note?: string) => {
      const res = await run();
      if (res.success && res.gameState) {
        state = res.gameState;
        fails = 0;
      } else {
        fails++;
      }
      transcript.push({ step: transcript.length, seq: state.sequenceNumber, actor, action, ok: res.success, err: res.error, note });
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
            // stage 1: клетка named-бойца (его зона — по определению валидна)
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
          return exec(me, `resolveMove ${fid} stay`, () => executor.executeResolvePendingEffect(
            { ...base, fighterId: fid, x: pos.x, y: pos.y }, { userId: me, gameId: 'g1', currentState: state } as any));
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

      // 1) отложенные выборы — строго голова очереди (GD-018)
      const pending = state.metadata.pendingEffects?.[0];
      if (pending) {
        lastAction = `pending:${pending.type}`;
        await resolvePending(pending);
        continue;
      }
      // 2) избыточная рука в конце хода
      const discard = state.metadata.pendingHandDiscard;
      if (discard) {
        lastAction = 'discardToLimit';
        const hand = state.handZones[discard.playerId]?.cards ?? [];
        await exec(discard.playerId, `discardToLimit ${discard.count}`, () => executor.executeDiscardToLimit(
          { gameId: 'g1', pendingId: discard.id, cardIds: hand.slice(0, discard.count).map((c) => c.id) },
          { userId: discard.playerId, gameId: 'g1', currentState: state } as any));
        continue;
      }
      // 3) манёвр в процессе: довести движение
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
      // 4) бой: защита (если ещё не сыграна), затем резолв
      const combat = state.metadata.combatInfo;
      if (combat) {
        const attacker = combat.attackerId;
        const defender = combat.defenderId;
        if (!combat.defenderCardId) {
          const defHand = state.handZones[defender]?.cards ?? [];
          // banner: защитную карту играет АТАКОВАННЫЙ боец
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
        await exec(attacker, 'resolveCombat', () => executor.executeResolveCombat(
          { gameId: 'g1' }, { userId: attacker, gameId: 'g1', currentState: state } as any));
        continue;
      }

      // 5) обычный ход текущего игрока
      const me = state.currentTurnPlayerId;
      const actionsLeft = state.metadata.actionsRemaining ?? 0;
      if (actionsLeft <= 0) {
        const before = state.turnCount;
        lastAction = 'endTurn';
        await exec(me, 'endTurn', () => executor.executeEndTurn(
          { gameId: 'g1' } as any, { userId: me, gameId: 'g1', currentState: state } as any));
        hpLog.push({
          turn: before, seq: state.sequenceNumber,
          hp: Object.fromEntries(state.players.map((p) => {
            const hero = state.fighters.find((f) => f.ownerId === p.userId && f.type === 'HERO');
            return [p.userId, hero?.health ?? 0];
          })),
        });
        continue;
      }

      // 5a) атака: боец с картой, чей баннер ему разрешён (bannerAllows), + легальная цель
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

      // 5b) схема с живым banner-бойцом (scheme-гвардей: именной боец в игре)
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

      // 5c) манёвр: сблизиться
      lastAction = 'beginManeuver';
      const begun = await exec(me, 'beginManeuver', () => executor.executeBeginManeuver(
        { gameId: 'g1', expectedSequenceNumber: state.sequenceNumber },
        { userId: me, gameId: 'g1', currentState: state } as any));
      if (!begun.success) {
        // манёвр уже делали (maneuveredThisTurn?) или нельзя — закончить ход
        await exec(me, 'endTurn(noMoves)', () => executor.executeEndTurn(
          { gameId: 'g1' } as any, { userId: me, gameId: 'g1', currentState: state } as any));
      }
    }

    return { state, transcript, hpLog };
  } finally {
    Math.random = origRandom;
  }
}

describe('GD-024: two deterministic full server games (hero + first-player swap)', () => {
  it('game 1: u1=Medusa first vs u2=Arthur — reaches GAME_OVER with a winner and no stranded state', async () => {
    const game = await runFullGame({ label: 'game1', seed: 20260925, heroU1: 'medusa', first: 'u1' });
    const { state, transcript } = game;
    expect(state.phase).toBe(GamePhase.GAME_OVER);
    expect(state.metadata.winnerId).toBeDefined();
    // никаких stranded pending/боёв
    expect(state.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(state.metadata.pendingManeuver).toBeUndefined();
    expect(state.metadata.pendingHandDiscard).toBeUndefined();
    expect(state.metadata.combatInfo).toBeUndefined();
    expect(state.metadata.combatResolutionProgress).toBeUndefined();
    expect(state.metadata.combatEffectContinuation).toBeUndefined();
    // seq монотонен, шагов в пределах бюджета
    const seqs = transcript.map((t) => t.seq);
    for (let i = 1; i < seqs.length; i++) expect(seqs[i]).toBeGreaterThanOrEqual(seqs[i - 1]);
    expect(transcript.length).toBeLessThan(2000);
    // победитель жив, проигравший мёртв
    const winnerHero = state.fighters.find((f) => f.ownerId === state.metadata.winnerId && f.type === 'HERO')!;
    expect(winnerHero.health).toBeGreaterThan(0);
    const loser = state.players.find((p) => p.userId !== state.metadata.winnerId)!;
    const loserHero = state.fighters.find((f) => f.ownerId === loser.userId && f.type === 'HERO')!;
    expect(loserHero.health).toBe(0);
    // все 30+30 карт учтены (рука+колода+сброс, кроме ушедших в бой — их нет: карты не исчезают)
    for (const uid of ['u1', 'u2']) {
      const total = (state.decks[uid].drawPile.length ?? 0)
        + (state.handZones[uid]?.cards.length ?? 0)
        + (state.discardPiles[uid]?.length ?? 0);
      expect(total).toBe(30);
    }
    writeTranscript('s06-full-game-1', { label: 'game1', seed: 20260925, heroes: { u1: 'Medusa', u2: 'King Arthur' }, first: 'u1' }, game);
  }, 120_000);

  it('game 2: u1=Arthur, FIRST PLAYER SWAPPED to u2=Medusa — reaches GAME_OVER with a winner and no stranded state', async () => {
    const game = await runFullGame({ label: 'game2', seed: 1337, heroU1: 'arthur', first: 'u2' });
    const { state, transcript } = game;
    expect(state.phase).toBe(GamePhase.GAME_OVER);
    expect(state.metadata.winnerId).toBeDefined();
    expect(state.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(state.metadata.combatInfo).toBeUndefined();
    expect(state.metadata.combatResolutionProgress).toBeUndefined();
    expect(state.metadata.pendingManeuver).toBeUndefined();
    expect(state.metadata.pendingHandDiscard).toBeUndefined();
    // первый игрок был u2: firstPlayerId зафиксирован init'ом
    expect(state.metadata.firstPlayerId).toBe('u2');
    const seqs = transcript.map((t) => t.seq);
    for (let i = 1; i < seqs.length; i++) expect(seqs[i]).toBeGreaterThanOrEqual(seqs[i - 1]);
    expect(transcript.length).toBeGreaterThan(0);
    for (const uid of ['u1', 'u2']) {
      const total = (state.decks[uid].drawPile.length ?? 0)
        + (state.handZones[uid]?.cards.length ?? 0)
        + (state.discardPiles[uid]?.length ?? 0);
      expect(total).toBe(30);
    }
    writeTranscript('s06-full-game-2', { label: 'game2', seed: 1337, heroes: { u1: 'King Arthur', u2: 'Medusa' }, first: 'u2' }, game);
  }, 120_000);

  function writeTranscript(file: string, header: Record<string, unknown>, game: Awaited<ReturnType<typeof runFullGame>>) {
    const dir = resolve(root, 'docs/game-design/evidence/S06');
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    const { state, transcript, hpLog } = game;
    writeFileSync(resolve(dir, `${file}.json`), JSON.stringify({
      ...header,
      engine: 'GameService.startGame → GameActionExecutorService (scripted deterministic policy)',
      rng: 'LCG seed (Math.random override; вся перетасовка детерминирована)',
      result: {
        phase: state.phase,
        winnerId: state.metadata.winnerId,
        turns: state.turnCount,
        sequenceNumber: state.sequenceNumber,
        heroHp: Object.fromEntries(state.players.map((p) => [p.userId, state.fighters.find((f) => f.ownerId === p.userId && f.type === 'HERO')?.health])),
        deckSizes: Object.fromEntries(['u1', 'u2'].map((u) => [u, {
          draw: state.decks[u].drawPile.length, hand: state.handZones[u]?.cards.length, discard: state.discardPiles[u]?.length,
        }])),
      },
      steps: transcript.length,
      hpByTurn: hpLog,
      transcript,
    }, null, 2));
  }
});
