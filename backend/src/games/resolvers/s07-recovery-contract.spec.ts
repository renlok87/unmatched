/** GD-027 / ACC-011 + ACC-012: snapshot/WS/since recovery-контракт.
 *  - connection barrier: подписка стартует с барьер-снапшотом — окно
 *    «HTTP snapshot ещё не пришёл / уже пришёл» не теряет и не дублирует
 *    состояние (дубликат отсекает клиентский guard по seq);
 *  - since НЕ обещает replay: события до подписки не восстанавливаются,
 *    барьер-снапшот закрывает свежесть;
 *  - sequenceNumber строго монотонен (+1 на мутацию) по всему журналу;
 *  - приватность per-viewer сохраняется в барьер-снапшоте;
 *  - реконнект в pending/defense/game-over фазах восстанавливает корректную
 *    стадию из персистентного состояния. */
import { GameSubscriptionService } from '../game-subscription.service';
import { GameSubscriptionResolver } from './game-subscription.resolver';
import { GameStateService } from '../game-state.service';
import { GamePhase, CardType, FighterType } from '../../game-engine/models';
import { s03Engine } from '../../test/fixtures/s03-engine.fixture';
import type { GameState } from '../game-state.service';

const atkCard = { id: 'atk-1', cardId: 'cat-atk', name: 'Spike', nameEn: 'Spike', nameRu: 'Шип', cardType: CardType.VERSATILE, attackValue: 4, effects: [] } as any;

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
      b: { cards: [{ ...atkCard, id: 'b-hand-secret', name: 'Secret', isVisible: true }], maxSize: 7 },
    },
    boardState: { width: 4, height: 1, cells: [[{ x: 0, y: 0, type: 'normal' }, { x: 1, y: 0, type: 'normal' }, { x: 2, y: 0, type: 'normal' }, { x: 3, y: 0, type: 'normal' }]], doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date(), lastActionBy: 'a', version: 1, actionsRemaining: 2 },
  } as any;
}

function makeWorld(participants = ['a', 'b']) {
  const states = new Map<string, GameState>();
  const prisma: any = {
    gamePlayer: {
      findUnique: async ({ where }: any) =>
        participants.includes(where.gameId_userId.userId) ? { id: 'p' } : null,
    },
    gameState: { findUnique: async () => null, upsert: async ({ create }: any) => create },
    game: { update: async () => ({}) },
    $transaction: async (run: (tx: unknown) => unknown) => run(prisma),
  };
  const redis: any = { subscribe: () => undefined, publish: async () => undefined };
  const redisSubs: ((msg: string) => void)[] = [];
  redis.subscribe = (_ch: string, cb: (msg: string) => void) => redisSubs.push(cb);
  const gameStateService = new GameStateService(prisma, {
    ...redis,
    getJson: async () => null,
    setJsonex: async () => 'OK',
    del: async () => 1,
  } as any);
  (gameStateService as any).loadState = async (gameId: string) => {
    const st = states.get(gameId);
    if (!st) throw new Error('not found');
    return st;
  };
  (gameStateService as any).saveState = async (gameId: string, st: GameState) => { states.set(gameId, st); };
  const subscriptionService = new GameSubscriptionService({ publish: async (_c: string, msg: string) => redisSubs.forEach(cb => cb(msg)) } as any);
  const resolver = new GameSubscriptionResolver(subscriptionService, gameStateService);
  const ctx = (userId: string) => ({ req: { user: { id: userId } } });
  return { states, gameStateService, subscriptionService, resolver, ctx };
}

async function firstNext(iter: AsyncIterableIterator<any>): Promise<any> {
  return (await iter.next()).value;
}

describe('S07 GD-027 snapshot/WS/since recovery contract', () => {
  it('connection barrier: подписка стартует с барьер-снапшотом текущего состояния', async () => {
    const w = makeWorld();
    const st = fixture();
    w.states.set('g1', st);

    const iter = await w.resolver.gameStateUpdated('g1', undefined, undefined, w.ctx('a'));
    const first = await firstNext(iter);

    expect(first.eventType).toBe('STATE_UPDATED');
    expect(first.sequenceNumber).toBe(st.sequenceNumber);
    expect(first.payload).toMatchObject({ gameId: 'g1', phase: GamePhase.ACTION_MANEUVER });
    await iter.return!();
  });

  it('барьер закрывает окно пропуска: событие между snapshot и подпиской приходит барьером', async () => {
    const w = makeWorld();
    const st1 = fixture();
    w.states.set('g1', st1);
    // клиент взял HTTP-snapshot (seq 10); ПОКА он подписывался, состояние ушло на 11
    const st2 = { ...st1, sequenceNumber: 11, currentTurnPlayerId: 'b' };
    w.states.set('g1', st2);

    const iter = await w.resolver.gameStateUpdated('g1', 10, undefined, w.ctx('a'));
    const first = await firstNext(iter);
    // барьер доставляет АКТУАЛЬНОЕ состояние (11), а не устаревший HTTP-снимок
    expect(first.sequenceNumber).toBe(11);
    expect(first.payload.currentTurnPlayerId).toBe('b');
    await iter.return!();
  });

  it('since не обещает replay: при актуальном since барьер молчит, первое событие — live', async () => {
    const w = makeWorld();
    const st = fixture();
    w.states.set('g1', st);

    const iter = await w.resolver.gameStateUpdated('g1', st.sequenceNumber, undefined, w.ctx('a'));
    const pending = firstNext(iter);
    // никаких старых событий не «воспроизводится» — ждём только live
    await w.subscriptionService.publishGameUpdate('g1', 'STATE_UPDATED', { ...st, sequenceNumber: 12 } as GameState);
    const live = await pending;
    expect(live.sequenceNumber).toBe(12);
    await iter.return!();
  });

  it('spectator не получает ни барьер-снапшот, ни события', async () => {
    const w = makeWorld();
    w.states.set('g1', fixture());
    await expect(
      w.resolver.gameStateUpdated('g1', undefined, undefined, w.ctx('z')),
    ).rejects.toThrow('Not a game participant');
  });

  it('барьер-снапшот проходит ту же per-viewer проекцию (resolver)', async () => {
    const w = makeWorld();
    const { executor } = s03Engine();
    const attacked = (await executor.executeAttack(
      { gameId: 'g1', attackerId: 'fA', targetId: 'fB', cardId: 'atk-1' } as any,
      { userId: 'a', gameId: 'g1', currentState: fixture() },
    )).gameState!;
    w.states.set('g1', attacked);

    const iter = await w.resolver.gameStateUpdated('g1', undefined, undefined, w.ctx('b'));
    const first = await firstNext(iter);
    // resolve-функция резолвера применяет filterPrivateData по JWT-юзеру
    const resolvedView = (w.resolver as any).resolveGameState(first, {}, w.ctx('b'));
    const raw = JSON.stringify(resolvedView);
    expect(raw).not.toContain('"attackValue":4');
    expect(raw).not.toContain('atk-1');
    await iter.return!();
  });

  it('ранняя отписка до первого upstream-события отпускает underlying-подписку немедленно', async () => {
    const w = makeWorld();
    const st = fixture();
    w.states.set('g1', st);

    // Оборачиваем upstream: считаем вызовы return() (реальный release подписки)
    const originalIterator = w.subscriptionService.asyncIteratorForGame.bind(w.subscriptionService);
    let upstreamReturns = 0;
    w.subscriptionService.asyncIteratorForGame = (gameId: string) => {
      const up = originalIterator(gameId);
      const wrapped: AsyncIterableIterator<any> = {
        next: (...a: any[]) => up.next(...(a as [])),
        return: async (v?: any) => {
          upstreamReturns++;
          await up.return?.(v);
          return { done: true as const, value: v };
        },
        throw: (e?: any) => up.throw?.(e) ?? Promise.resolve({ done: true as const, value: undefined }),
        [Symbol.asyncIterator]: () => wrapped,
      };
      return wrapped;
    };

    // since = текущий seq → барьер-снапшот не выдаётся, первый next() ждёт
    // firstUpstream; PubSub молчит (никаких событий не публикуем)
    const iter = await w.resolver.gameStateUpdated('g1', st.sequenceNumber, undefined, w.ctx('a'));
    const pendingNext = iter.next();

    await iter.return!();
    // underlying-подписка отпущена СРАЗУ, не дожидаясь первого PubSub-события
    expect(upstreamReturns).toBe(1);
    // ожидающий next() завершается promptly — без вечного зависания
    await expect(pendingNext).resolves.toEqual({ done: true, value: undefined });
    const after = await iter.next();
    expect(after.done).toBe(true);
  });

  it('genuine отказ loadState в барьере: логируется и пробрасывается, upstream освобождается', async () => {
    const w = makeWorld();
    w.states.set('g1', fixture());
    (w.gameStateService as any).loadState = async () => {
      throw new Error('redis connection refused');
    };

    const iter = await w.resolver.gameStateUpdated('g1', undefined, undefined, w.ctx('a'));
    await expect(iter.next()).rejects.toThrow('redis connection refused');
  });

  it('лобби-фаза (NotFound) в барьере: снапшот пропускается, live-события идут', async () => {
    const w = makeWorld();
    const st = fixture();
    w.states.set('g1', st);
    (w.gameStateService as any).loadState = async () => {
      const { NotFoundException } = await import('@nestjs/common');
      throw new NotFoundException('Состояние игры g1 не найдено');
    };

    const iter = await w.resolver.gameStateUpdated('g1', undefined, undefined, w.ctx('a'));
    const pending = firstNext(iter);
    await w.subscriptionService.publishGameUpdate('g1', 'STATE_UPDATED', { ...st, sequenceNumber: 12 } as GameState);
    const live = await pending;
    expect(live.sequenceNumber).toBe(12);
    await iter.return!();
  });

  it('sequenceNumber строго монотонен (+1) по цепочке мутаций и таймаут-резолва', async () => {
    const w = makeWorld();
    const { executor } = s03Engine();
    const seqs: number[] = [];
    let st = fixture();
    w.states.set('g1', st);
    seqs.push(st.sequenceNumber);

    const record = (next: GameState) => { st = next; w.states.set('g1', next); seqs.push(next.sequenceNumber); };

    const attack = await executor.executeAttack(
      { gameId: 'g1', attackerId: 'fA', targetId: 'fB', cardId: 'atk-1' } as any,
      { userId: 'a', gameId: 'g1', currentState: st },
    );
    record(attack.gameState!);
    expect(st.phase).toBe(GamePhase.COMBAT); // реконнект в pending defense

    // «оба клиента отключились»: дедлайн истёк → серверный резолв
    const expired = { ...st, metadata: { ...st.metadata, combatInfo: { ...st.metadata.combatInfo!, timeoutAt: new Date(Date.now() - 1000) } } };
    w.states.set('g1', expired);
    const resolved = await executor.executeResolveCombat(
      { gameId: 'g1' } as any,
      { userId: 'b', gameId: 'g1', currentState: expired, systemInitiator: true },
    );
    record(resolved.gameState!);

    for (let i = 1; i < seqs.length; i++) {
      expect(seqs[i]).toBe(seqs[i - 1] + 1);
    }
    // после резолва реконнект видит action-фазу (не зависший COMBAT)
    expect(st.phase).toBe(GamePhase.ACTION_MANEUVER);
    expect(st.metadata.combatInfo).toBeUndefined();
  });

  it('реконнект в game-over: фаза и победитель пережили serialize/deserialize', async () => {
    const w = makeWorld();
    const st = fixture();
    const over: GameState = {
      ...st,
      phase: GamePhase.GAME_OVER,
      sequenceNumber: 42,
      metadata: { ...st.metadata, winnerId: 'b' },
    };
    const serialized = w.gameStateService.serialize(over as any);
    const restored = w.gameStateService.deserialize(serialized);
    expect(restored.phase).toBe(GamePhase.GAME_OVER);
    expect(restored.metadata.winnerId).toBe('b');
    expect(restored.sequenceNumber).toBe(42);
  });
});
