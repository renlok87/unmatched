/** GD-026 / ACC-010: серверный defense timeout и финализация боя.
 *  Все исходы — через ТОТ ЖЕ executeResolveCombat, что и ручной путь:
 *  ровно один исход, один инкремент sequenceNumber, одна audit-запись.
 *  P1-дрейн: истёкший дедлайн при запаузенном выборе (BOOST/mandatory)
 *  прогрессивается сервером через ПРОИЗВОДСТВЕННЫЕ pending-резолверы.
 *  Часы инъектируются (service.now + прямые timeoutAt в состояниях) —
 *  без sleep-пелей и fake timers. */
import * as fs from 'fs';
import * as path from 'path';
import { CombatTimeoutService } from './combat-timeout.service';
import { AiTurnService } from './ai-turn.service';
import { AiDecisionService } from '../../game-engine/services/ai-decision.service';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { GameStateService } from '../game-state.service';
import { GamePhase, CardType, FighterType, EffectType, EffectTiming } from '../../game-engine/models';
import { normalizeCardEffects } from '../../game-engine/models';
import { parseCardEffectTexts } from '../../game-engine/effects/effect-text-parser';
import { s03Engine } from '../../test/fixtures/s03-engine.fixture';
import type { GameState } from '../game-state.service';
import type { Card, PendingEffect } from '../../game-engine/models';

const atkCard = { id: 'atk-1', cardId: 'cat-atk', name: 'Spike', nameEn: 'Spike', nameRu: 'Шип', cardType: CardType.VERSATILE, attackValue: 4, effects: [] } as any;
const defCard = { id: 'def-1', cardId: 'cat-def', name: 'Slip', nameEn: 'Slip', nameRu: 'Тень', cardType: CardType.VERSATILE, defenseValue: 2, effects: [] } as any;

function fixture(): GameState {
  return {
    gameId: 'g1', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER, turnCount: 1, currentTurnPlayerId: 'a',
    players: ['a', 'b'].map(userId => ({ userId, heroId: userId, health: 10, maxHealth: 10, fighterIds: [userId], isAlive: true })),
    fighters: [
      { id: 'fA', ownerId: 'a', heroId: 'ha', name: 'A', type: FighterType.HERO, health: 10, maxHealth: 10, position: { x: 0, y: 0 }, effects: [], hasSidekick: false, attackType: 'melee' },
      { id: 'fB', ownerId: 'b', heroId: 'hb', name: 'B', type: FighterType.HERO, health: 10, maxHealth: 10, position: { x: 1, y: 0 }, effects: [], hasSidekick: false, attackType: 'melee' },
    ],
    decks: { a: { cards: [], drawPile: [] }, b: { cards: [], drawPile: [] } },
    discardPiles: { a: [], b: [] },
    handZones: {
      a: { cards: [{ ...atkCard, isVisible: true }], maxSize: 7 },
      b: { cards: [{ ...defCard, isVisible: true }], maxSize: 7 },
    },
    boardState: { width: 4, height: 1, cells: [[{ x: 0, y: 0, type: 'normal' }, { x: 1, y: 0, type: 'normal' }, { x: 2, y: 0, type: 'normal' }, { x: 3, y: 0, type: 'normal' }]], doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date(), lastActionBy: 'a', version: 1, actionsRemaining: 2 },
  } as any;
}

function makeHarness(executorOverride?: Record<string, unknown>, aiTurnOverride?: { maybeRunAiTurns: jest.Mock }) {
  const { executor } = s03Engine();
  const states = new Map<string, GameState>();
  const saved: GameState[] = [];
  const audits: any[] = [];
  const queueAdds: any[] = [];
  // Map-based queue с семантикой BullMQ: getJob по id; add дедуплицирует по
  // jobId (существующая джоба возвращается молча); remove() активной джобы
  // бросает — как реальный BullMQ.
  const jobs = new Map<string, any>();
  const prisma: any = {
    gameState: {
      findUnique: async ({ where }: any) => (states.has(where.gameId) ? { state: null } : null),
      findMany: async () =>
        [...states.entries()].map(([gameId, st]) => ({ gameId, state: null, _state: st, sequenceNumber: st.sequenceNumber })),
      upsert: async ({ where, create }: any) => { states.set(where.gameId, create as any); return create; },
    },
    gamePlayer: { findUnique: async () => ({ id: 'p' }) },
    game: { update: async () => ({}) },
    $transaction: async (run: (tx: unknown) => unknown) => run(prisma),
  };
  const redis: any = { getJson: async () => null, setJsonex: async () => 'OK', del: async () => 1 };
  const gameStateService: any = new GameStateService(prisma, redis, undefined);
  // подменяем хранилище на прямое (минуя serialize/deserialize мока prisma)
  gameStateService.loadState = async (gameId: string) => {
    const st = states.get(gameId);
    if (!st) throw new Error('not found');
    return st;
  };
  gameStateService.saveState = async (gameId: string, st: GameState) => {
    states.set(gameId, st);
    saved.push(st);
  };
  const lock: any = { withLockOptions: async (_k: string, fn: () => Promise<unknown>) => fn() };
  const queue: any = {
    getJob: async (jobId: string) => jobs.get(jobId) ?? null,
    getJobs: async (statuses: string[]) => {
      const result = [];
      for (const job of jobs.values()) {
        if (statuses.includes(await job.getState())) result.push(job);
      }
      return result;
    },
    add: async (_name: string, data: any, opts: any) => {
      queueAdds.push({ data, opts });
      if (!jobs.has(opts.jobId)) {
        const jobId = opts.jobId;
        jobs.set(jobId, {
          id: jobId, data, delay: opts.delay, timestamp: Date.now(),
          getState: async () => 'delayed',
          remove: async () => { jobs.delete(jobId); },
        });
      }
      return jobs.get(opts.jobId);
    },
    close: async () => undefined,
  };
  const published: any[] = [];
  const service = new CombatTimeoutService(
    queue,
    gameStateService,
    lock,
    prisma,
    (executorOverride ?? executor) as any,
    { publishGameUpdate: async (gameId: string, eventType: string, st: GameState) => published.push({ gameId, eventType, seq: st.sequenceNumber }) } as any,
    { recordAction: async (dto: any) => { audits.push(dto); return 'id'; } } as any,
    aiTurnOverride as any,
  );
  return { executor, service, states, saved, audits, queueAdds, published, gameStateService, jobs, queue, lock, gameStateServiceRef: gameStateService };
}

async function attack(h: ReturnType<typeof makeHarness>, cardId = 'atk-1'): Promise<GameState> {
  const result = await h.executor.executeAttack(
    { gameId: 'g1', attackerId: 'fA', targetId: 'fB', cardId } as any,
    { userId: 'a', gameId: 'g1', currentState: h.states.get('g1')! },
  );
  expect(result.success).toBe(true);
  const st = result.gameState!;
  h.states.set('g1', st);
  return st;
}

async function defend(h: ReturnType<typeof makeHarness>, cardId = 'def-1'): Promise<GameState> {
  const result = await h.executor.executePlayDefense(
    { gameId: 'g1', cardId } as any,
    { userId: 'b', gameId: 'g1', currentState: h.states.get('g1')! },
  );
  expect(result.success).toBe(true);
  const st = result.gameState!;
  h.states.set('g1', st);
  return st;
}

const expireDeadline = (h: ReturnType<typeof makeHarness>) => {
  const st = h.states.get('g1')!;
  h.states.set('g1', { ...st, metadata: { ...st.metadata, combatInfo: { ...st.metadata.combatInfo!, timeoutAt: new Date(Date.now() - 1000) } } });
};
const futureDeadline = (h: ReturnType<typeof makeHarness>) => {
  const st = h.states.get('g1')!;
  h.states.set('g1', { ...st, metadata: { ...st.metadata, combatInfo: { ...st.metadata.combatInfo!, timeoutAt: new Date(Date.now() + 60_000) } } });
};

describe('S07 GD-026 server-side defense timeout', () => {
  let h: ReturnType<typeof makeHarness>;
  beforeEach(() => {
    h = makeHarness();
    h.states.set('g1', fixture());
  });

  it('attack персистит deadline (timeoutAt) в combatInfo', async () => {
    const st = await attack(h);
    expect(st.phase).toBe(GamePhase.COMBAT);
    expect(st.metadata.combatInfo?.timeoutAt).toBeInstanceOf(Date);
    expect(st.metadata.combatInfo!.timeoutAt!.getTime()).toBeGreaterThan(Date.now() + 25_000);
  });

  it('timeout финализирует бой без обоих клиентов: урон, один seq, одна audit', async () => {
    const harn = h;
    const before = await attack(harn);
    expireDeadline(harn);

    const result = await harn.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });

    expect(result.success).toBe(true);
    expect(result.reason).toBe('defense-timeout');
    const after = harn.states.get('g1')!;
    // ровно один инкремент sequenceNumber
    expect(after.sequenceNumber).toBe(before.sequenceNumber + 1);
    // урон от атаки без защиты применён ровно один раз
    expect(after.fighters.find(f => f.id === 'fB')!.health).toBe(6);
    expect(after.metadata.combatInfo).toBeUndefined();
    expect(after.phase).toBe(GamePhase.ACTION_MANEUVER); // у атакующего осталось действие
    expect(harn.audits).toHaveLength(1);
    expect(harn.audits[0].type).toBe('COMBAT_RESOLVED');
    expect(harn.audits[0].metadata.reason).toBe('defense-timeout');
    expect(harn.published.map(p => p.eventType)).toEqual(['COMBAT_RESOLVED']);
  });

  it('timeout побеждает последнего бойца → COMBAT_RESOLVED + GAME_ENDED (gameEnded-подписка видит итог)', async () => {
    const harn = h;
    // защитник при 4 hp: атака 4 без защиты роняет последнего героя
    const st = harn.states.get('g1')!;
    harn.states.set('g1', {
      ...st,
      fighters: st.fighters.map((f) => (f.id === 'fB' ? { ...f, health: 4 } : f)),
    });

    const before = await attack(harn);
    expireDeadline(harn);

    const result = await harn.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });
    expect(result.success).toBe(true);
    expect(result.reason).toBe('defense-timeout');

    const after = harn.states.get('g1')!;
    expect(after.phase).toBe(GamePhase.GAME_OVER);
    expect(after.metadata.winnerId).toBe('a');
    // GAME_ENDED идёт сразу после COMBAT_RESOLVED с итоговым состоянием —
    // тот же порядок, что у ручного пути в game-actions.resolver
    expect(harn.published.map((p) => p.eventType)).toEqual(['COMBAT_RESOLVED', 'GAME_ENDED']);
    expect(harn.published[1].seq).toBe(after.sequenceNumber);
    // аудит: исход + GAME_ENDED с победителем (catch-up через eventsSince)
    expect(harn.audits.map((a) => a.type)).toEqual(['COMBAT_RESOLVED', 'GAME_ENDED']);
    expect(harn.audits[1].metadata).toMatchObject({ action: 'autoResolve', reason: 'defense-timeout', winnerId: 'a' });
  });

  it('GD-039: успешный auto-resolve триггерит дрейн бота (VS_AI) — ход атакующего продолжается', async () => {
    // Бот атаковал, человек не защитился → таймаут финализирует бой, но у
    // бота осталось действие: БЕЗ триггера матч виснет (мутаций человека нет).
    const aiTurn = { maybeRunAiTurns: jest.fn().mockResolvedValue(undefined) };
    const local = makeHarness(undefined, aiTurn);
    local.states.set('g1', fixture());
    const before = await attack(local);
    expireDeadline(local);

    const result = await local.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });

    expect(result.success).toBe(true);
    expect(aiTurn.maybeRunAiTurns).toHaveBeenCalledWith('g1');
  });

  /** GD-039 Sol6: атака БОТА обязана получать собственную джобу дедлайна —
   *  путь человека (game-actions.resolver) тут не участвует. Человек-защитник
   *  отключился: джоба, поставленная самим ботом, финализирует бой. */
  it('GD-039 Sol6: бот-атака планирует джобу дедлайна; человек офлайн → она финализирует бой и дергает дрейн', async () => {
    const aiTurn = { maybeRunAiTurns: jest.fn().mockResolvedValue(undefined) };
    const local = makeHarness(undefined, aiTurn);
    local.states.set('g1', fixture());
    const adjacency = new AdjacencyService();
    const botTurn = new AiTurnService(
      { game: { findUnique: async () => ({ mode: 'VS_AI', status: 'IN_PROGRESS', opponentId: 'a' }) } } as any,
      local.lock,
      local.gameStateServiceRef,
      { publishGameUpdate: async () => {} } as any,
      local.executor,
      new AiDecisionService(adjacency),
      local.service,
    );

    await botTurn.maybeRunAiTurns('g1'); // смежные бойцы + атак-карта в руке: бот атакует

    const st = local.states.get('g1')!;
    expect(st.phase).toBe(GamePhase.COMBAT);
    expect(st.metadata.combatInfo?.defenderId).toBe('b'); // человек-защитник
    // САМА атака бота поставила джобу DEFENSE-стадии (~30с)
    const jobAdds = local.queueAdds.filter((add: any) => add.data.stage === 'DEFENSE');
    expect(jobAdds).toHaveLength(1);
    expect(jobAdds[0].opts.delay).toBeGreaterThanOrEqual(29_000);
    expect(jobAdds[0].opts.delay).toBeLessThanOrEqual(30_000);
    expect(local.jobs.has('combat-scheduled-g1-DEFENSE')).toBe(true);

    // человек отключился: дедлайн истёк, worker дергает processor
    expireDeadline(local);
    const result = await local.service.processAutoResolve(jobAdds[0].data);

    expect(result.success).toBe(true);
    expect(result.reason).toBe('defense-timeout');
    const after = local.states.get('g1')!;
    expect(after.metadata.combatInfo).toBeUndefined();
    expect(after.phase).toBe(GamePhase.ACTION_MANEUVER); // у бота-атакующего осталось действие
    expect(after.sequenceNumber).toBe(st.sequenceNumber + 1);
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(6);
    expect(aiTurn.maybeRunAiTurns).toHaveBeenCalledWith('g1');
  });

  it('GD-039: неистёкший дедлайн НЕ дергает дрейн бота', async () => {
    const aiTurn = { maybeRunAiTurns: jest.fn().mockResolvedValue(undefined) };
    const local = makeHarness(undefined, aiTurn);
    local.states.set('g1', fixture());
    await attack(local);
    futureDeadline(local);

    const result = await local.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'DEFENSE' });

    expect(result.success).toBe(false);
    expect(result.reason).toBe('Deadline not reached');
    expect(aiTurn.maybeRunAiTurns).not.toHaveBeenCalled();
  });

  it('поздняя джоба после защиты безвредна: deadline стадии резолва не истёк', async () => {
    const harn = h;
    await attack(harn);
    await defend(harn); // timeoutAt = now + 10s

    const result = await harn.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'DEFENSE' });
    expect(result.success).toBe(false);
    expect(result.reason).toBe('Deadline not reached');
    expect(harn.states.get('g1')!.phase).toBe(GamePhase.COMBAT_RESOLVE);
    expect(harn.audits).toHaveLength(0);
  });

  it('resolve-timeout завершает бой после защиты, когда оба клиента ушли', async () => {
    const harn = h;
    await attack(harn);
    await defend(harn);
    expireDeadline(harn);

    const result = await harn.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);
    expect(result.reason).toBe('resolve-timeout');
    const after = harn.states.get('g1')!;
    expect(after.metadata.combatInfo).toBeUndefined();
    // 4 − 2 защиты = 2 урона защитнику
    expect(after.fighters.find(f => f.id === 'fB')!.health).toBe(8);
  });

  it('ранний resolve запрещён: атакующий не может закрыть окно защиты', async () => {
    const harn = h;
    await attack(harn);
    const attackerTry = await harn.executor.executeResolveCombat(
      { gameId: 'g1' } as any,
      { userId: 'a', gameId: 'g1', currentState: harn.states.get('g1')! },
    );
    expect(attackerTry.success).toBe(false);
    expect(attackerTry.error).toContain('Defender has not responded');

    // защитник МОЖЕТ отказаться от карты («Без защиты») — легальный путь
    const defenderTry = await harn.executor.executeResolveCombat(
      { gameId: 'g1' } as any,
      { userId: 'b', gameId: 'g1', currentState: harn.states.get('g1')! },
    );
    expect(defenderTry.success).toBe(true);
    // executor возвращает новое состояние, не мутируя входное
    expect(defenderTry.gameState!.fighters.find(f => f.id === 'fB')!.health).toBe(6);
  });

  it('системный ранний вызов отклоняется до истечения дедлайна', async () => {
    const harn = h;
    await attack(harn);
    futureDeadline(harn);
    const result = await harn.executor.executeResolveCombat(
      { gameId: 'g1' } as any,
      { userId: 'b', gameId: 'g1', currentState: harn.states.get('g1')!, systemInitiator: true },
    );
    expect(result.success).toBe(false);
    expect(result.error).toContain('deadline has not expired');
  });

  it('опоздавшая защита после дедлайна отклоняется', async () => {
    const harn = h;
    await attack(harn);
    expireDeadline(harn);
    const result = await harn.executor.executePlayDefense(
      { gameId: 'g1', cardId: 'def-1' } as any,
      { userId: 'b', gameId: 'g1', currentState: harn.states.get('g1')! },
    );
    expect(result.success).toBe(false);
    expect(result.error).toContain('Defense window has expired');
  });

  it('гонка defense/timeout/resolve/retry → ровно один исход и один инкремент', async () => {
    const harn = h;
    const before = await attack(harn);
    expireDeadline(harn);

    // 1) джоба финализирует
    const first = await harn.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });
    expect(first.success).toBe(true);

    // 2) повтор джобы (retry) — no-op, без второго инкремента
    const second = await harn.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });
    expect(second.success).toBe(false);
    expect(second.reason).toBe('No combat in progress');

    // 3) защита прилетает после финализации — no-op
    const lateDefense = await harn.executor.executePlayDefense(
      { gameId: 'g1', cardId: 'def-1' } as any,
      { userId: 'b', gameId: 'g1', currentState: harn.states.get('g1')! },
    );
    expect(lateDefense.success).toBe(false);
    expect(lateDefense.error).toContain('Not in combat phase');

    // 4) ручной резолв после финализации — no-op
    const manual = await harn.executor.executeResolveCombat(
      { gameId: 'g1' } as any,
      { userId: 'a', gameId: 'g1', currentState: harn.states.get('g1')! },
    );
    expect(manual.success).toBe(false);

    const after = harn.states.get('g1')!;
    expect(after.sequenceNumber).toBe(before.sequenceNumber + 1);
    expect(after.fighters.find(f => f.id === 'fB')!.health).toBe(6);
    expect(harn.audits).toHaveLength(1);
  });

  it('recovery после рестарта: истёкший бой финализируется, будущий перепланируется', async () => {
    const harn = h;

    // истёкший
    await attack(harn);
    expireDeadline(harn);
    // будущий во второй игре
    harn.states.set('g2', { ...fixture(), gameId: 'g2' });
    const g2 = harn.states.get('g2')!;
    harn.states.set('g2', {
      ...g2,
      phase: GamePhase.COMBAT,
      metadata: {
        ...g2.metadata,
        combatInfo: {
          attackerId: 'fA', defenderId: 'b', targetFighterId: 'fB', attackerCardId: 'atk-1',
          attackValue: 4, defenseValue: 0, startedAt: new Date(),
          timeoutAt: new Date(Date.now() + 5000),
        } as any,
      },
    });

    // recovery видит сериализованные состояния (как в БД)
    const prismaRows = [...harn.states.entries()].map(([gameId, st]) => ({ gameId, state: harn.gameStateService.serialize(st as any), sequenceNumber: st.sequenceNumber }));
    const findManyMock = async () => prismaRows;
    (harn.service as any).prisma.gameState.findMany = findManyMock;

    const { recovered, rescheduled } = await harn.service.recoverScheduledWork();
    expect(recovered).toBe(1);
    expect(rescheduled).toBe(1);
    // g1 финализирован сервером
    expect(harn.states.get('g1')!.metadata.combatInfo).toBeUndefined();
    // g2 перепланирован на остаток дедлайна
    const add = harn.queueAdds.at(-1)!;
    expect(add.opts.delay).toBe(5000);
    expect(add.data.stage).toBe('DEFENSE');
  });

  it('recovery: легаси-бой без timeoutAt получает дедлайн от startedAt', async () => {
    const harn = h;
    const legacy: GameState = {
      ...fixture(),
      phase: GamePhase.COMBAT_RESOLVE,
      metadata: {
        ...fixture().metadata,
        combatInfo: {
          attackerId: 'fA', defenderId: 'b', targetFighterId: 'fB', attackerCardId: 'atk-1',
          attackValue: 4, defenseValue: 2, defenderCardId: 'def-1', startedAt: new Date(Date.now() - 60_000),
        } as any,
      },
    };
    harn.states.set('g3', legacy);
    const rows = [{ gameId: 'g3', state: harn.gameStateService.serialize(legacy as any), sequenceNumber: legacy.sequenceNumber }];
    (harn.service as any).prisma.gameState.findMany = async () => rows;

    const { recovered } = await harn.service.recoverScheduledWork();
    expect(recovered).toBe(1);
    expect(harn.states.get('g3')!.metadata.combatInfo).toBeUndefined();
  });
});

// --- P1: серверная прогрессия запаузенных выборов (GD-026 mid-combat) ---

const arthurCapture = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../../../..', 'docs/game-design/evidence/S01/content-king-arthur.json'),
    'utf8',
  ),
) as { cards: Array<Record<string, any>> };

/** Production ingest (зеркалит GameInitializationService.resolveCardEffects). */
function ingest(card: Record<string, any>): Card {
  const parsed = normalizeCardEffects(card.effects, card.id);
  const resolved =
    parsed.length > 0
      ? parsed
      : card.cardType === 'SCHEME' && card.textEn?.trim()
        ? parseCardEffectTexts({ fullText: card.textEn }, card.id).effects
        : [];
  return {
    id: `${card.id}::0`,
    cardId: card.id,
    name: card.name,
    nameEn: card.nameEn,
    nameRu: card.nameRu,
    cardType: card.cardType,
    attackValue: card.attackValue ?? undefined,
    defenseValue: card.defenseValue ?? undefined,
    boostValue: card.boostValue ?? undefined,
    effects: resolved,
    text: card.textEn ?? undefined,
    bannerName: card.bannerName ?? undefined,
  } as Card;
}

const arthurCard = (nameEn: string): Card =>
  ingest(arthurCapture.cards.find((c) => c.nameEn === nameEn)!);

const fillerCard = (id: string, boostValue = 0, defenseValue?: number): Card => ({
  id, cardId: id.replace(/::\d+$/, ''), name: id, nameEn: id, nameRu: id,
  cardType: CardType.VERSATILE, boostValue, defenseValue, effects: [],
} as Card);

/** Защитная карта с DURING_COMBAT OPPONENT_DISCARD (как печатные карты S05):
 *  создаёт mandatory DISCARD_CARDS в боевой цепочке ДО BOOST-выбора. */
const discardDefense = (id: string): Card => ({
  ...fillerCard(id, 0, 2),
  cardType: CardType.DEFENSE,
  effects: [{
    id: `${id}-during-0`,
    type: EffectType.OPPONENT_DISCARD,
    value: 1,
    target: 'OPPONENT_PLAYER',
    timing: EffectTiming.DURING_COMBAT,
    source: 'parser',
    text: 'Your opponent discards 1 card.',
  }] as Card['effects'],
});

function fixtureWith(handA: Card[], handB: Card[] = []): GameState {
  const base = fixture();
  return {
    ...base,
    handZones: {
      a: { cards: handA.map((c) => ({ ...c, isVisible: true })), maxSize: 7 },
      b: { cards: handB.map((c) => ({ ...c, isVisible: true })), maxSize: 7 },
    },
  } as GameState;
}

describe('S07 GD-026 P1: серверная прогрессия mid-combat выборов по таймауту', () => {
  let h: ReturnType<typeof makeHarness>;
  beforeEach(() => {
    h = makeHarness();
  });

  it('запаузенный optional BOOST_CHOICE + оба офлайн + истёкший дедлайн → авто-decline, бой завершён один раз', async () => {
    const noble = { ...arthurCard('Noble Sacrifice'), id: 'noble::0' };
    const boost = fillerCard('boost::0', 4);
    h.states.set('g1', fixtureWith([noble, boost]));

    const before = await attack(h, 'noble::0'); // seq 11, COMBAT, очередь пуста
    expireDeadline(h);

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });
    expect(result.success).toBe(true);
    expect(result.reason).toBe('defense-timeout');

    const after = h.states.get('g1')!;
    // системный резолв запаузил бой на BOOST (attacker 'a') → дрейн отклонил → resume
    expect(after.metadata.combatInfo).toBeUndefined();
    expect(after.phase).toBe(GamePhase.ACTION_MANEUVER);
    // печатные 2 без буста и без защиты: 10 − 2
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(8);
    // карта-буст НЕ потрачена за офлайн-владельца (decline, не fabricated boost)
    expect(after.handZones.a.cards.map((c) => c.id)).toContain('boost::0');
    // легальные промежуточные seq: attack(11) → pause(12) → decline+resume(13)
    expect(after.sequenceNumber).toBe(before.sequenceNumber + 2);
    // аудит: один авто-выбор + один исход
    expect(h.audits.map((a) => a.type)).toEqual(['CARD_PLAYED', 'COMBAT_RESOLVED']);
    expect(h.audits[0].metadata.action).toBe('autoResolveChoice');
    expect(h.audits[0].metadata.method).toBe('decline');
    expect(h.audits[1].metadata.reason).toBe('defense-timeout');
    // публикация: пауза + шаг дрейна + исход
    expect(h.published.map((p) => p.eventType)).toEqual(['STATE_UPDATED', 'STATE_UPDATED', 'COMBAT_RESOLVED']);
    // retry той же джобы — no-op
    const retry = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });
    expect(retry.success).toBe(false);
    expect(retry.reason).toBe('No combat in progress');
    expect(h.states.get('g1')!.sequenceNumber).toBe(after.sequenceNumber);
  });

  it('mandatory CHOOSE_ONE chooseCount=2 (multi-step, тот же id) + оба офлайн → оба шага дрейнятся, один исход, без дублей и утечек', async () => {
    h.states.set('g1', fixtureWith([structuredClone(atkCard)], [structuredClone(defCard)]));
    await attack(h);
    await defend(h);
    // синтетическая пауза на mandatory multi-step CHOOSE_ONE (production-тип
    // Looking Glass: «Choose 2 different effects»): resolveChooseOne снимает
    // по одной опции, сохраняя id и длину очереди — прогресс виден только по
    // chooseCount/options.length
    const defended = h.states.get('g1')!;
    const drawOpt = (id: string) => ({
      id, type: EffectType.DRAW_CARD, value: 1, timing: EffectTiming.AFTER_COMBAT,
    });
    const seqBefore = defended.sequenceNumber;
    h.states.set('g1', {
      ...defended,
      decks: { ...defended.decks, a: { ...defended.decks.a, drawPile: ['r1', 'r2', 'r3'].map((id) => fillerCard(id)) as any } },
      metadata: {
        ...defended.metadata,
        combatResolutionProgress: { defeatedBefore: [] } as any,
        pendingEffects: [{
          id: 'pe-choose', type: 'CHOOSE_ONE', playerId: 'a', optional: false, chooseCount: 2,
          options: [
            { index: 0, label: 'draw 1' },
            { index: 1, label: 'draw 1 more' },
            { index: 2, label: 'nothing' },
          ],
          optionEffects: [[drawOpt('o1')], [drawOpt('o2')], []],
          text: 'Choose 2 different effects',
        } as PendingEffect],
      },
    });
    expireDeadline(h);

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);
    expect(result.reason).toBe('resolve-timeout');

    const after = h.states.get('g1')!;
    // оба шага прошли фолбэком optionIndex 0 (второй шаг — переиндексированный
    // 0 = бывшая опция 1): каждая опция применена РОВНО один раз, третья — нет
    expect(after.handZones.a.cards.map((c) => c.id)).toEqual(['r1', 'r2']);
    expect(after.decks.a.drawPile.map((c: any) => c.id)).toEqual(['r3']);
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.metadata.combatInfo).toBeUndefined();
    // 4 − 2 защиты = 2 урона защитнику
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(8);
    // строго возрастающий seq: attack → defend → шаг1 → шаг2+resume
    expect(after.sequenceNumber).toBe(seqBefore + 2);
    const savedSeqs = h.saved.map((s) => s.sequenceNumber);
    for (let i = 1; i < savedSeqs.length; i++) {
      expect(savedSeqs[i]).toBeGreaterThan(savedSeqs[i - 1]);
    }
    // один финальный исход: одна COMBAT_RESOLVED-публикация, одна audit
    expect(h.published.map((p) => p.eventType)).toEqual(['STATE_UPDATED', 'STATE_UPDATED', 'COMBAT_RESOLVED']);
    expect(h.published.filter((p) => p.eventType === 'COMBAT_RESOLVED')).toHaveLength(1);
    expect(h.audits.map((a) => a.type)).toEqual(['CARD_PLAYED', 'CARD_PLAYED', 'COMBAT_RESOLVED']);
    expect(h.audits.filter((a) => a.type === 'COMBAT_RESOLVED')).toHaveLength(1);
    expect(h.audits[0].metadata.method).toBe('deterministic-fallback');
    expect(h.audits[1].metadata.method).toBe('deterministic-fallback');
    // приватность: аудит авто-выбора без id карт руки/колоды
    const auditJson = JSON.stringify(h.audits);
    expect(auditJson).not.toContain('r1');
    expect(auditJson).not.toContain('r2');
    expect(auditJson).not.toContain('r3');
    // retry той же джобы — no-op
    const retry = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(retry.success).toBe(false);
    expect(retry.reason).toBe('No combat in progress');
  });

  it('mandatory очередь [DISCARD_CARDS → BOOST_CHOICE] + оба офлайн → детерминированный фолбэк + decline, без fabricated карт', async () => {
    const noble = { ...arthurCard('Noble Sacrifice'), id: 'noble::0' };
    const victim = fillerCard('victim::0', 6);
    const boost = fillerCard('boost::0', 4);
    const dd = discardDefense('dd::0');
    h.states.set('g1', fixtureWith([noble, victim, boost], [dd]));

    await attack(h, 'noble::0');
    await defend(h, 'dd::0'); // очередь ещё пуста, RESOLVE-стадия
    expireDeadline(h);

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);
    expect(result.reason).toBe('resolve-timeout');

    const after = h.states.get('g1')!;
    // mandatory DISCARD_CARDS резолвнут production-резолвером: первая карта руки
    // (детерминизм — хранимый порядок руки) ушла в публичный сброс владельца
    expect(after.discardPiles.a.map((c) => c.id)).toContain('victim::0');
    expect(after.handZones.a.cards.map((c) => c.id)).toEqual(['boost::0']);
    // урон: 2 − 2 защиты − 0 буст = 0
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(10);
    expect(after.metadata.combatInfo).toBeUndefined();
    // seq: attack(11) → defend(12) → pause(13) → discard(14) → decline+resume(15)
    expect(after.sequenceNumber).toBe(15);
    // два авто-выбора + один исход
    expect(h.audits.map((a) => a.type)).toEqual(['CARD_PLAYED', 'CARD_PLAYED', 'COMBAT_RESOLVED']);
    expect(h.audits[0].metadata.method).toBe('deterministic-fallback');
    expect(h.audits[1].metadata.method).toBe('decline');
    // приватность аудита: без id карт
    for (const a of h.audits) {
      expect(a.metadata.cardIds).toBeUndefined();
      expect(JSON.stringify(a.metadata)).not.toContain('victim::0');
    }
  });

  it('mandatory DECK_TOP_PICK PICK→ORDER + оба офлайн → детерминированный порядок, порядок колоды сохранён', async () => {
    h.states.set('g1', fixtureWith([structuredClone(atkCard)], [structuredClone(defCard)]));
    const revealed = ['r1', 'r2', 'r3', 'r4'].map((id) =>
      structuredClone({ ...fillerCard(id), isVisible: true }),
    );
    await attack(h);
    await defend(h);
    // синтетическая пауза на mandatory DECK_TOP_PICK (production pending-тип):
    // PICK(value 2) из 4 revealed → ORDER остатка — настоящий multi-step choice
    const defended = h.states.get('g1')!;
    const paused: GameState = {
      ...defended,
      decks: { ...defended.decks, a: { ...defended.decks.a, drawPile: ['old1', 'old2'].map((id) => fillerCard(id)) as any } },
      metadata: {
        ...defended.metadata,
        combatResolutionProgress: { defeatedBefore: [] } as any,
        pendingEffects: [{
          id: 'deck-1', type: 'DECK_TOP_PICK', playerId: 'a', mode: 'PICK', value: 2,
          revealedCards: revealed, optional: false, text: 'Take 2, return the rest',
        } as PendingEffect],
      },
    };
    h.states.set('g1', paused);
    expireDeadline(h);

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);

    const after = h.states.get('g1')!;
    // PICK взял первые 2 в порядке reveal (детерминизм)
    expect(after.handZones.a.cards.map((c) => c.id)).toEqual(['r1', 'r2']);
    // ORDER — тождественная перестановка: остаток ложится в исходном порядке,
    // скрытый порядок колоды не переворачивается и не раскрывается
    expect(after.decks.a.drawPile.map((c: any) => c.id)).toEqual(['r3', 'r4', 'old1', 'old2']);
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.metadata.combatInfo).toBeUndefined();
    expect(h.audits.map((a) => a.type)).toEqual(['CARD_PLAYED', 'CARD_PLAYED', 'COMBAT_RESOLVED']);
  });

  it('mandatory TARGET_FIGHTER + оба офлайн → первый живой из допустимых целей, урон ровно один', async () => {
    h.states.set('g1', fixtureWith([structuredClone(atkCard)], [structuredClone(defCard)]));
    await attack(h);
    await defend(h);
    const defended = h.states.get('g1')!;
    h.states.set('g1', {
      ...defended,
      metadata: {
        ...defended.metadata,
        combatResolutionProgress: { defeatedBefore: [] } as any,
        pendingEffects: [{
          id: 'pe-target', type: 'TARGET_FIGHTER', playerId: 'b', optional: false,
          targetFighterIds: ['fA', 'fB'], damage: 2, text: 'Choose any one fighter',
        } as PendingEffect],
      },
    });
    expireDeadline(h);

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);

    const after = h.states.get('g1')!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.metadata.combatInfo).toBeUndefined();
    // детерминизм фолбэка: первый живой по порядку targetFighterIds = fA
    expect(after.fighters.find((f) => f.id === 'fA')!.health).toBe(8);
    // fB: только боевой урон 4 − 2 защиты
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(8);
    expect(h.audits.map((a) => a.type)).toEqual(['CARD_PLAYED', 'COMBAT_RESOLVED']);
    expect(h.published.at(-1)!.eventType).toBe('COMBAT_RESOLVED');
  });

  it('mandatory PLACE + оба офлайн → первая свободная проходимая клетка (row-major)', async () => {
    h.states.set('g1', fixtureWith([structuredClone(atkCard)], [structuredClone(defCard)]));
    await attack(h);
    await defend(h);
    const defended = h.states.get('g1')!;
    h.states.set('g1', {
      ...defended,
      metadata: {
        ...defended.metadata,
        combatResolutionProgress: { defeatedBefore: [] } as any,
        pendingEffects: [{
          id: 'pe-place', type: 'PLACE', playerId: 'a', fighterIds: ['fA'], optional: false,
          text: 'Place your fighter on any free space',
        } as PendingEffect],
      },
    });
    expireDeadline(h);

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);

    const after = h.states.get('g1')!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.metadata.combatInfo).toBeUndefined();
    // fA(0,0), fB(1,0) заняты → первая свободная row-major = (2,0)
    const fA = after.fighters.find((f) => f.id === 'fA')!;
    expect(fA.position).toEqual({ x: 2, y: 0 });
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(8);
    expect(h.audits.map((a) => a.type)).toEqual(['CARD_PLAYED', 'COMBAT_RESOLVED']);
  });

  it('mandatory CHOOSE_SPACE stage1→stage2 (тот же id) + оба офлайн → обе стадии дрейнятся, одна клетка на стадию', async () => {
    h.states.set('g1', fixtureWith([structuredClone(atkCard)], [structuredClone(defCard)]));
    await attack(h);
    await defend(h);
    const defended = h.states.get('g1')!;
    h.states.set('g1', {
      ...defended,
      // production-доска несёт зоны в клетках (getCellZones); дефолтный
      // fixture без зон → зонный предикат stage 1 всегда false
      boardState: {
        ...defended.boardState,
        cells: [[0, 1, 2, 3].map((x) => ({ x, y: 0, type: 'normal', zone: 'row' }))] as any,
      },
      metadata: {
        ...defended.metadata,
        combatResolutionProgress: { defeatedBefore: [] } as any,
        pendingEffects: [{
          id: 'pe-space', type: 'CHOOSE_SPACE', playerId: 'a', stage: 1, zoneFighterName: 'B',
          damage: 1, optional: false, text: 'Choose a space in B zone, then an adjacent one',
        } as PendingEffect],
      },
    });
    expireDeadline(h);

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);

    const after = h.states.get('g1')!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.metadata.combatInfo).toBeUndefined();
    // stage1: зона B (fB 1,0) → первая свободная (2,0); stage2: смежная с
    // anchor (2,0) → (3,0). Обе клетки свободны → урона нет (фолбэк честно
    // не бьёт своих/пустые клетки), бой завершён одним исходом.
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(8);
    // обе стадии прошли как отдельные шаги: два авто-выбора + один исход
    expect(h.audits.map((a) => a.type)).toEqual(['CARD_PLAYED', 'CARD_PLAYED', 'COMBAT_RESOLVED']);
    expect(h.published.at(-1)!.eventType).toBe('COMBAT_RESOLVED');
  });

  it('mandatory CHOOSE_SPACE stage2 + оба офлайн → смежная клетка, урон врагу в клетках применяется', async () => {
    h.states.set('g1', fixtureWith([structuredClone(atkCard)], [structuredClone(defCard)]));
    await attack(h);
    await defend(h);
    const defended = h.states.get('g1')!;
    h.states.set('g1', {
      ...defended,
      metadata: {
        ...defended.metadata,
        combatResolutionProgress: { defeatedBefore: [] } as any,
        pendingEffects: [{
          id: 'pe-space2', type: 'CHOOSE_SPACE', playerId: 'a', stage: 2, anchor: { x: 1, y: 0 },
          damage: 1, optional: false, text: 'Choose a space adjacent to the chosen one',
        } as PendingEffect],
      },
    });
    expireDeadline(h);

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);

    const after = h.states.get('g1')!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    // фолбэк: первая свободная смежная с anchor (1,0) = (2,0); клетки
    // {(1,0),(2,0)}: враг fB(1,0) получает 1 урон + боевые 4−2 → 10−1−2
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(7);
    expect(h.audits.map((a) => a.type)).toEqual(['CARD_PLAYED', 'COMBAT_RESOLVED']);
  });

  it('mandatory без безопасного фолбэка (synthetic mandatory BOOST) → блокер, очередь нетронута, без аудита', async () => {
    h.states.set('g1', fixtureWith([structuredClone(atkCard)], [structuredClone(defCard)]));
    await attack(h);
    await defend(h);
    const defended = h.states.get('g1')!;
    h.states.set('g1', {
      ...defended,
      metadata: {
        ...defended.metadata,
        combatResolutionProgress: { defeatedBefore: [] } as any,
        pendingEffects: [{ id: 'pe-mb', type: 'BOOST_CHOICE', playerId: 'a', optional: false } as PendingEffect],
      },
    });
    expireDeadline(h);

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(false);
    expect(result.reason).toContain('no safe deterministic fallback');
    const after = h.states.get('g1')!;
    expect(after.phase).toBe(GamePhase.COMBAT_RESOLVE);
    expect(after.metadata.pendingEffects).toHaveLength(1); // очередь не тронута
    expect(after.metadata.pendingEffects![0].id).toBe('pe-mb');
    expect(h.audits).toHaveLength(0);
    expect(h.published).toHaveLength(0);
  });

  it('непустая очередь + НЕистёкший дедлайн → очередь нетронута, без аудита и публикаций', async () => {
    const noble = { ...arthurCard('Noble Sacrifice'), id: 'noble::0' };
    const boost = fillerCard('boost::0', 4);
    h.states.set('g1', fixtureWith([noble, boost], [structuredClone(defCard)]));
    await attack(h, 'noble::0');
    await defend(h);
    // ручной резолв защитника запаузил бой на BOOST (production-путь)
    const manual = await h.executor.executeResolveCombat(
      { gameId: 'g1' } as any,
      { userId: 'b', gameId: 'g1', currentState: h.states.get('g1')! },
    );
    expect(manual.success).toBe(true);
    h.states.set('g1', manual.gameState!);
    expect(h.states.get('g1')!.metadata.pendingEffects ?? []).toHaveLength(1);

    // дедлайн RESOLVE-стадии ещё в будущем
    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(false);
    expect(result.reason).toBe('Deadline not reached');
    expect(h.states.get('g1')!.metadata.pendingEffects).toHaveLength(1);
    expect(h.audits).toHaveLength(0);
    expect(h.published).toHaveLength(0);
  });

  it('restart recovery доводит запаузенный BOOST-бой до конца по сериализованному состоянию', async () => {
    const noble = { ...arthurCard('Noble Sacrifice'), id: 'noble::0' };
    const boost = fillerCard('boost::0', 4);
    h.states.set('g1', fixtureWith([noble, boost], [structuredClone(defCard)]));
    await attack(h, 'noble::0');
    await defend(h);
    const manual = await h.executor.executeResolveCombat(
      { gameId: 'g1' } as any,
      { userId: 'b', gameId: 'g1', currentState: h.states.get('g1')! },
    );
    h.states.set('g1', manual.gameState!); // запаузлен на BOOST, дедлайн от defend (+10с)
    expireDeadline(h);

    // recovery читает сериализованные строки, как из БД после рестарта
    const rows = [...h.states.entries()].map(([gameId, st]) => ({
      gameId, state: h.gameStateService.serialize(st as any), sequenceNumber: st.sequenceNumber,
    }));
    (h.service as any).prisma.gameState.findMany = async () => rows;

    const { recovered } = await h.service.recoverScheduledWork();
    expect(recovered).toBe(1);
    const after = h.states.get('g1')!;
    expect(after.metadata.combatInfo).toBeUndefined();
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(10); // 2 − 2 защиты = 0 урона
    expect(h.audits[h.audits.length - 1].type).toBe('COMBAT_RESOLVED');
  });
});

describe('S07 GD-026 P2: stage-специфичные job id (race защиты в момент срабатывания DEFENSE-джобы)', () => {
  let h: ReturnType<typeof makeHarness>;
  beforeEach(() => {
    h = makeHarness();
  });

  it('scheduleAutoResolve(RESOLVE) при АКТИВНОЙ DEFENSE-джобе планирует RESOLVE, не теряя её', async () => {
    // DEFENSE-джоба активирована воркером: remove() бросает, add со старым
    // общим id молча вернул бы её — RESOLVE-дедлайн оказывался бы потерян
    const activeDefense = {
      id: 'combat-scheduled-g1-DEFENSE',
      data: { gameId: 'g1', stage: 'DEFENSE' },
      remove: async () => { throw new Error('Active job cannot be removed'); },
    };
    h.jobs.set('combat-scheduled-g1-DEFENSE', activeDefense);

    await h.service.scheduleAutoResolve('g1', 10, 12, 'RESOLVE');

    // RESOLVE-джоба реально добавлена с собственным id
    const resolveJob = h.jobs.get('combat-scheduled-g1-RESOLVE');
    expect(resolveJob).toBeDefined();
    expect(resolveJob.data.stage).toBe('RESOLVE');
    expect(h.queueAdds.at(-1)!.opts.jobId).toBe('combat-scheduled-g1-RESOLVE');
    // DEFENSE-джоба не потеряна и не заменена
    expect(h.jobs.get('combat-scheduled-g1-DEFENSE')).toBe(activeDefense);
  });

  it('защита в момент срабатывания DEFENSE-джобы, оба офлайн → RESOLVE доводит бой, ровно один исход', async () => {
    h.states.set('g1', fixture());
    await attack(h);
    await defend(h); // RESOLVE-стадия, дедлайн +10с — как если защита успела в момент активации

    // опоздавшая DEFENSE-джоба безвредна
    const late = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'DEFENSE' });
    expect(late.success).toBe(false);
    expect(late.reason).toBe('Deadline not reached');

    expireDeadline(h);
    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);
    expect(result.reason).toBe('resolve-timeout');
    const after = h.states.get('g1')!;
    expect(after.metadata.combatInfo).toBeUndefined();
    expect(after.fighters.find((f) => f.id === 'fB')!.health).toBe(8); // 4 − 2
    expect(h.audits).toHaveLength(1);
  });

  it('cancelAutoResolve снимает джобы обеих стадий', async () => {
    await h.service.scheduleAutoResolve('g1', 30, 5, 'DEFENSE');
    await h.service.scheduleAutoResolve('g1', 10, 6, 'RESOLVE');
    expect(await h.service.hasScheduledAutoResolve('g1')).toBe(true);

    await h.service.cancelAutoResolve('g1');
    expect(await h.service.hasScheduledAutoResolve('g1')).toBe(false);
    expect(h.jobs.get('combat-scheduled-g1-DEFENSE')).toBeUndefined();
    expect(h.jobs.get('combat-scheduled-g1-RESOLVE')).toBeUndefined();
  });
});

// --- P2: honest round cap — контролируемая executor-последовательность ---
// Каждый круг = decline одного паузы-выбора + системный резолв, который снова
// запаузлен: 8+ последовательных пауз без фальшивого COMBAT_RESOLVED.

interface PauseStubMode {
  mode: 'pause' | 'complete';
}

function makePauseStubExecutor(): { stub: Record<string, unknown>; control: PauseStubMode; calls: { resolve: number; decline: number } } {
  const control: PauseStubMode = { mode: 'pause' };
  const calls = { resolve: 0, decline: 0 };
  const stub = {
    executeResolveCombat: async (_dto: any, ctx: any) => {
      const st = ctx.currentState as GameState;
      calls.resolve++;
      if (control.mode === 'complete') {
        return {
          success: true,
          gameState: {
            ...st,
            sequenceNumber: st.sequenceNumber + 1,
            phase: GamePhase.ACTION_MANEUVER,
            metadata: { ...st.metadata, combatInfo: undefined, pendingEffects: [] },
          },
        };
      }
      // легальная пауза: optional BOOST_CHOICE с +1 seq (как production-pause)
      return {
        success: true,
        gameState: {
          ...st,
          sequenceNumber: st.sequenceNumber + 1,
          phase: GamePhase.COMBAT_RESOLVE,
          metadata: {
            ...st.metadata,
            pendingEffects: [{ id: 'pe-boost', type: 'BOOST_CHOICE', playerId: 'a', optional: true } as PendingEffect],
          },
        },
      };
    },
    executeDeclinePendingEffect: async (_dto: any, ctx: any) => {
      const st = ctx.currentState as GameState;
      calls.decline++;
      // голова снята (+1 seq), бой всё ещё в COMBAT_RESOLVE — ждёт резолва
      return {
        success: true,
        gameState: {
          ...st,
          sequenceNumber: st.sequenceNumber + 1,
          phase: GamePhase.COMBAT_RESOLVE,
          metadata: { ...st.metadata, pendingEffects: [] },
        },
      };
    },
  };
  return { stub, control, calls };
}

describe('S07 GD-026 P2: honest round cap (8+ последовательных пауз резолва)', () => {
  function setup() {
    const { stub, control, calls } = makePauseStubExecutor();
    const h = makeHarness(stub);
    h.states.set('g1', {
      ...fixture(),
      phase: GamePhase.COMBAT_RESOLVE,
      metadata: {
        ...fixture().metadata,
        combatInfo: {
          attackerId: 'fA', defenderId: 'b', targetFighterId: 'fB', attackerCardId: 'atk-1',
          attackValue: 4, defenseValue: 2, defenderCardId: 'def-1', startedAt: new Date(),
          timeoutAt: new Date(Date.now() - 1000),
        } as any,
        combatResolutionProgress: { defeatedBefore: [] } as any,
        pendingEffects: [{ id: 'pe-boost', type: 'BOOST_CHOICE', playerId: 'a', optional: true } as PendingEffect],
      },
    });
    return { h, control, calls };
  }

  it('исчерпание round-cap при открытом бое → честный отказ, БЕЗ COMBAT_RESOLVED и без аудита исхода', async () => {
    const { h } = setup();
    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });

    expect(result.success).toBe(false);
    expect(result.reason).toContain('round cap');
    expect(result.reason).toContain('left open');
    // состояние честно открыто: фаза и очередь на месте, каждый шаг легален
    const after = h.states.get('g1')!;
    expect(after.phase).toBe(GamePhase.COMBAT_RESOLVE);
    expect(after.metadata.pendingEffects).toHaveLength(1);
    expect(after.metadata.combatInfo).toBeDefined();
    // НИ одной фальшивой финализации
    expect(h.published.filter((p) => p.eventType === 'COMBAT_RESOLVED')).toHaveLength(0);
    expect(h.audits.filter((a) => a.type === 'COMBAT_RESOLVED')).toHaveLength(0);
    // шаги легальны: seq строго растёт, по шагу на каждый decline
    const savedSeqs = h.saved.map((s) => s.sequenceNumber);
    for (let i = 1; i < savedSeqs.length; i++) {
      expect(savedSeqs[i]).toBeGreaterThan(savedSeqs[i - 1]);
    }
    // 8 кругов × (шаг дрейна + пауза резолва) — только промежуточные
    expect(h.published.filter((p) => p.eventType === 'STATE_UPDATED')).toHaveLength(16);
  });

  it('recovery-прогон после cap доводит бой: ровно один COMBAT_RESOLVED и одна audit исхода', async () => {
    const { h, control } = setup();
    const capped = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(capped.success).toBe(false);

    // очередь/Redis восстановились: следующий прогон (sweep/повтор джобы) завершает
    control.mode = 'complete';
    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: 0, stage: 'RESOLVE' });
    expect(result.success).toBe(true);

    const after = h.states.get('g1')!;
    expect(after.phase).toBe(GamePhase.ACTION_MANEUVER);
    expect(after.metadata.combatInfo).toBeUndefined();
    // по всей цепочке — ровно одна финализация и один аудит исхода
    expect(h.published.filter((p) => p.eventType === 'COMBAT_RESOLVED')).toHaveLength(1);
    expect(h.audits.filter((a) => a.type === 'COMBAT_RESOLVED')).toHaveLength(1);
  });
});

describe('S07 GD-026 P2: enqueue-failure и periodic recovery sweep', () => {
  let h: ReturnType<typeof makeHarness>;
  beforeEach(() => {
    h = makeHarness();
  });

  function persistFutureCombat(phase: GamePhase, sequenceNumber = 10) {
    const state: GameState = {
      ...fixture(), sequenceNumber, phase,
      metadata: {
        ...fixture().metadata,
        combatInfo: {
          attackerId: 'fA', defenderId: 'b', targetFighterId: 'fB', attackerCardId: 'atk-1',
          attackValue: 4, defenseValue: phase === GamePhase.COMBAT ? 0 : 2,
          startedAt: new Date(), timeoutAt: new Date(Date.now() + 5000),
        } as any,
      },
    };
    h.states.set('g1', state);
    (h.service as any).prisma.gameState.findMany = async () => [{
      gameId: 'g1', state: h.gameStateService.serialize(state as any), sequenceNumber,
    }];
  }

  it('recovers current DEFENSE after enqueue failure despite a completed old RESOLVE job', async () => {
    persistFutureCombat(GamePhase.COMBAT);
    h.jobs.set('combat-scheduled-g1-RESOLVE', {
      data: { gameId: 'g1', stage: 'RESOLVE', attackSequenceNumber: 8 },
      getState: async () => 'completed',
    });
    const originalAdd = h.queue.add;
    h.queue.add = async () => { throw new Error('ECONNREFUSED redis'); };
    await expect(h.service.scheduleAutoResolve('g1', 5, 10, 'DEFENSE')).rejects.toThrow('ECONNREFUSED');
    h.queue.add = originalAdd;

    expect(await h.service.recoverScheduledWork()).toEqual({ recovered: 0, rescheduled: 1 });
    expect(h.jobs.get('combat-scheduled-g1-DEFENSE')?.data).toEqual({
      gameId: 'g1', stage: 'DEFENSE', attackSequenceNumber: 10,
    });
    expect(await h.service.recoverScheduledWork()).toEqual({ recovered: 0, rescheduled: 0 });
  });

  it.each(['waiting', 'failed'] as const)('replaces a %s same-stage job from an earlier attack', async (status) => {
    persistFutureCombat(GamePhase.COMBAT, 12);
    const jobId = 'combat-scheduled-g1-DEFENSE';
    h.jobs.set(jobId, {
      data: { gameId: 'g1', stage: 'DEFENSE', attackSequenceNumber: 10 },
      getState: async () => status,
      remove: async () => { h.jobs.delete(jobId); },
    });

    expect(await h.service.recoverScheduledWork()).toEqual({ recovered: 0, rescheduled: 1 });
    expect(h.jobs.get(jobId)?.data.attackSequenceNumber).toBe(12);
  });

  it('uses a sequence id when an active old same-stage job cannot be removed', async () => {
    persistFutureCombat(GamePhase.COMBAT, 12);
    h.jobs.set('combat-scheduled-g1-DEFENSE', {
      data: { gameId: 'g1', stage: 'DEFENSE', attackSequenceNumber: 10 },
      getState: async () => 'active',
      remove: async () => { throw new Error('Active job cannot be removed'); },
    });

    expect(await h.service.recoverScheduledWork()).toEqual({ recovered: 0, rescheduled: 1 });
    expect(h.jobs.get('combat-scheduled-g1-DEFENSE-12')?.data.attackSequenceNumber).toBe(12);
    expect(await h.service.recoverScheduledWork()).toEqual({ recovered: 0, rescheduled: 0 });
  });

  it('cancels a sequence fallback while leaving the old active job untouched', async () => {
    persistFutureCombat(GamePhase.COMBAT, 12);
    const baseId = 'combat-scheduled-g1-DEFENSE';
    const fallbackId = 'combat-scheduled-g1-DEFENSE-12';
    const oldActive = {
      id: baseId,
      data: { gameId: 'g1', stage: 'DEFENSE', attackSequenceNumber: 10 },
      getState: async () => 'active',
      remove: jest.fn(async () => { throw new Error('Active job cannot be removed'); }),
    };
    h.jobs.set(baseId, oldActive);
    const otherId = 'combat-scheduled-g2-DEFENSE';
    const otherPending = {
      id: otherId,
      data: { gameId: 'g2', stage: 'DEFENSE', attackSequenceNumber: 3 },
      getState: async () => 'delayed',
      remove: jest.fn(async () => { h.jobs.delete(otherId); }),
    };
    h.jobs.set(otherId, otherPending);
    await h.service.scheduleAutoResolve('g1', 5, 12, 'DEFENSE');
    expect(h.jobs.get(fallbackId)?.data.attackSequenceNumber).toBe(12);
    expect(await h.service.hasScheduledAutoResolve('g1')).toBe(true);
    expect(await h.service.getTimeUntilResolve('g1')).not.toBeNull();

    await h.service.cancelAutoResolve('g1');

    expect(h.jobs.has(fallbackId)).toBe(false);
    expect(h.jobs.get(baseId)).toBe(oldActive);
    expect(h.jobs.get(otherId)).toBe(otherPending);
    expect(oldActive.remove).toHaveBeenCalledTimes(1); // only scheduling attempted removal
    expect(otherPending.remove).not.toHaveBeenCalled();
    expect(await h.service.hasScheduledAutoResolve('g1')).toBe(false);
    expect(await h.service.getTimeUntilResolve('g1')).toBeNull();
  });

  it('reports a current active job as scheduled without treating an old active job as current', async () => {
    persistFutureCombat(GamePhase.COMBAT, 12);
    h.jobs.set('combat-scheduled-g1-DEFENSE', {
      id: 'combat-scheduled-g1-DEFENSE',
      data: { gameId: 'g1', stage: 'DEFENSE', attackSequenceNumber: 12 },
      getState: async () => 'active',
    });
    expect(await h.service.hasScheduledAutoResolve('g1')).toBe(true);
  });

  it('enqueue-failure честно репортится; sweep перепланирует после восстановления очереди БЕЗ рестарта', async () => {
    // бой с будущим дедлайном (атака персистена состояние, очередь легла)
    h.states.set('g1', {
      ...fixture(),
      phase: GamePhase.COMBAT,
      metadata: {
        ...fixture().metadata,
        combatInfo: {
          attackerId: 'fA', defenderId: 'b', targetFighterId: 'fB', attackerCardId: 'atk-1',
          attackValue: 4, defenseValue: 0, startedAt: new Date(),
          timeoutAt: new Date(Date.now() + 5000),
        } as any,
      },
    });

    // очередь недоступна в момент планирования
    const originalAdd = h.queue.add;
    h.queue.add = async () => {
      throw new Error('ECONNREFUSED redis');
    };
    await expect(h.service.scheduleAutoResolve('g1', 5, 10, 'DEFENSE')).rejects.toThrow('ECONNREFUSED');

    // очередь восстановилась: sweep (tick) находит бой без джобы и перепланирует
    h.queue.add = originalAdd;
    const rows = [...h.states.entries()].map(([gameId, st]) => ({
      gameId, state: h.gameStateService.serialize(st as any), sequenceNumber: st.sequenceNumber,
    }));
    (h.service as any).prisma.gameState.findMany = async () => rows;

    const { rescheduled } = await h.service.recoverScheduledWork();
    expect(rescheduled).toBe(1);
    const add = h.queueAdds.at(-1)!;
    expect(add.opts.delay).toBe(5000);
    expect(add.data.stage).toBe('DEFENSE');
    expect(h.jobs.get('combat-scheduled-g1-DEFENSE')).toBeDefined();
  });

  it('onModuleInit ставит periodic sweep (60 c), onModuleDestroy снимает таймер', async () => {
    const setIntervalSpy = jest.spyOn(globalThis, 'setInterval');
    const clearIntervalSpy = jest.spyOn(globalThis, 'clearInterval');

    await h.service.onModuleInit();
    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 60_000);

    await h.service.onModuleDestroy();
    expect(clearIntervalSpy).toHaveBeenCalled();

    setIntervalSpy.mockRestore();
    clearIntervalSpy.mockRestore();
  });
});

// --- P2: post-commit CUE-публикации независимы (16-network-contract §4) ---
// gameEnded — lossy named-CUE: авторитетный исход = закоммиченное состояние
// (gameStateUpdated-барьер + HTTP). Redis publish может бросить ПОСЛЕ
// локального deliver уже закоммиченного резолва — это не должно проваливать
// джобу, обрывать оставшиеся CUE/аудиты или плодить второй терминальный исход.

describe('S07 GD-026 P2: post-commit CUE — best-effort и независимы', () => {
  it('publish COMBAT_RESOLVED бросает после коммита → GAME_ENDED всё равно попытан, аудиты записаны, результат success, retry безвреден', async () => {
    const h = makeHarness();
    h.states.set('g1', fixture());
    // защитник при 4 hp: таймаут-атака 4 роняет последнего героя → GAME_OVER
    const st = h.states.get('g1')!;
    h.states.set('g1', {
      ...st,
      fighters: st.fighters.map((f) => (f.id === 'fB' ? { ...f, health: 4 } : f)),
    });
    const before = await attack(h);
    expireDeadline(h);

    const attempts: string[] = [];
    (h.service as any).gameSubscriptionService = {
      publishGameUpdate: async (gameId: string, eventType: string, s: GameState) => {
        attempts.push(eventType);
        if (eventType === 'COMBAT_RESOLVED') {
          // Redis publish бросил после локального deliver — состояние закоммичено
          throw new Error('ECONNRESET after local delivery');
        }
        h.published.push({ gameId, eventType, seq: s.sequenceNumber });
      },
    };

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });

    // закоммиченный FINISHED не репортится как провал джобы
    expect(result.success).toBe(true);
    expect(result.reason).toBe('defense-timeout');

    // авторитетный исход доступен через снапшот/query: GAME_OVER + победитель
    const committed = await h.gameStateService.loadState('g1');
    expect(committed.phase).toBe(GamePhase.GAME_OVER);
    expect(committed.metadata.winnerId).toBe('a');

    // второй CUE попытан несмотря на отказ первого; успешный доставлен
    expect(attempts).toEqual(['COMBAT_RESOLVED', 'GAME_ENDED']);
    expect(h.published.map((p) => p.eventType)).toEqual(['GAME_ENDED']);
    expect(h.published[0].seq).toBe(committed.sequenceNumber);

    // аудиты независимы от публикации: исход + GAME_ENDED записаны
    expect(h.audits.map((a) => a.type)).toEqual(['COMBAT_RESOLVED', 'GAME_ENDED']);
    expect(h.audits[1].metadata).toMatchObject({ action: 'autoResolve', reason: 'defense-timeout', winnerId: 'a' });

    // retry той же джобы — no-op: терминальный исход не дублируется
    const retry = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });
    expect(retry.success).toBe(false);
    expect(retry.reason).toBe('No combat in progress');
    expect(attempts.filter((e) => e === 'COMBAT_RESOLVED')).toHaveLength(1);
    expect(h.audits.filter((a) => a.type === 'COMBAT_RESOLVED')).toHaveLength(1);
    expect((await h.gameStateService.loadState('g1')).sequenceNumber).toBe(committed.sequenceNumber);
  });

  it('publish GAME_ENDED тоже бросает → исход всё равно success: закоммиченное состояние авторитетно', async () => {
    const h = makeHarness();
    h.states.set('g1', fixture());
    const st = h.states.get('g1')!;
    h.states.set('g1', {
      ...st,
      fighters: st.fighters.map((f) => (f.id === 'fB' ? { ...f, health: 4 } : f)),
    });
    const before = await attack(h);
    expireDeadline(h);

    (h.service as any).gameSubscriptionService = {
      publishGameUpdate: async () => {
        throw new Error('ECONNRESET after local delivery');
      },
    };

    const result = await h.service.processAutoResolve({ gameId: 'g1', attackSequenceNumber: before.sequenceNumber, stage: 'DEFENSE' });
    expect(result.success).toBe(true);

    const committed = await h.gameStateService.loadState('g1');
    expect(committed.phase).toBe(GamePhase.GAME_OVER);
    expect(committed.metadata.winnerId).toBe('a');
    // аудиты всё равно записаны — публикация не владеет исходом
    expect(h.audits.map((a) => a.type)).toEqual(['COMBAT_RESOLVED', 'GAME_ENDED']);
  });
});
