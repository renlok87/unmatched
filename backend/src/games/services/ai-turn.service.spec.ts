import { AiTurnService } from './ai-turn.service';
import { AiDecisionService, AiAction } from '../../game-engine/services/ai-decision.service';
import { GameActionExecutorService } from '../../game-engine/services/game-action-executor.service';
import { CardEffectExecutorService } from '../../game-engine/effects/card-effect-executor.service';
import { DeckManagementService } from '../../game-engine/services/deck-management.service';
import { GameRulesValidator } from '../../game-engine/validators/game-rules.validator';
import { CombatResolverService } from '../../game-engine/engine/combat-resolver.service';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { ValueModifierService } from '../../game-engine/engine/value-modifier.service';
import { HeroAbilityRegistry } from '../../game-engine/abilities/hero-ability-registry';
import { HandCard, CardType, FighterType, GamePhase, GameState, createEmptyBoardState, DEFENSE_TIMEOUT_SECONDS } from '../../game-engine/models';
import { ABILITY_CONFIGS, AbilityConfig } from '../../game-engine/abilities/ability-config';
import { GenericHeroAbilityHandler } from '../../game-engine/abilities/generic-hero-ability.handler';

const card = (id: string): HandCard => ({ id, cardId: 'defense', name: id, nameEn: id, nameRu: id,
  cardType: CardType.DEFENSE, defenseValue: 2, isVisible: true });

// JSON-клон с восстановлением Date-полей боя (executor зовёт timeoutAt.getTime())
const clone = (state: GameState): GameState =>
  JSON.parse(JSON.stringify(state), (key, value) =>
    key === 'timeoutAt' || key === 'startedAt' || key === 'lastActionAt'
      ? new Date(value as string)
      : value,
  ) as GameState;

function fixture(): GameState {
  return {
    gameId: 'ai-s03', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER,
    turnCount: 1, currentTurnPlayerId: 'ai',
    players: ['ai', 'human'].map(userId => ({ userId, heroId: userId,
      health: 10, maxHealth: 10, fighterIds: [`${userId}-hero`], isAlive: true })),
    fighters: ['ai', 'human'].map((ownerId, index) => ({ id: `${ownerId}-hero`, ownerId,
      heroId: ownerId, name: ownerId, type: FighterType.HERO, health: 10, maxHealth: 10,
      movement: 2, position: { x: index * 9, y: 0 }, effects: [], hasSidekick: false })),
    decks: { ai: { cards: [], drawPile: [card('draw-1'), card('draw-2')] },
      human: { cards: [], drawPile: [card('human-top')] } },
    handZones: { ai: { cards: [], maxSize: 7 }, human: { cards: [], maxSize: 7 } },
    discardPiles: { ai: [], human: [] }, boardState: createEmptyBoardState(10, 2),
    metadata: { lastActionAt: new Date(), lastActionBy: 'ai', version: 1, actionsRemaining: 2 },
  } as GameState;
}

function harness(initial: GameState, aiUserId = 'ai', overrides: {
  publish?: (gameId: string, event: string, state: GameState) => Promise<void>;
  save?: (gameId: string, state: GameState) => Promise<void>;
  record?: (dto: { gameId: string; sequenceNumber: number; type: string; playerId: string; metadata: any }) => Promise<string>;
  /** AI-03: подменить эвристику (расхождение с валидатором, null на своём выборе). */
  decide?: (state: GameState, aiUserId: string) => AiAction | null;
} = {}, opts: { withAbilityConfigs?: boolean; extraAbilityConfigs?: readonly AbilityConfig[] } = {}) {
  let saved = initial;
  const snapshots: GameState[] = [];
  const events: string[] = [];
  const publishCalls: Array<{ event: string; seq: number }> = [];
  const combatTimeoutCalls: Array<{ op: string; args: unknown[] }> = [];
  const combatTimeout = {
    scheduleAutoResolve: async (...args: unknown[]) => { combatTimeoutCalls.push({ op: 'schedule', args }); },
    cancelAutoResolve: async (...args: unknown[]) => { combatTimeoutCalls.push({ op: 'cancel', args }); },
  };
  const journal: Array<{ gameId: string; sequenceNumber: number; type: string; playerId: string; metadata: any }> = [];
  const gameActionService = {
    recordAction: async (dto: any) => {
      if (overrides.record) return overrides.record(dto);
      journal.push(dto);
      return 'id';
    },
  };
  const metrics = { measureServiceDuration: async (_a: string, _b: string, run: () => unknown) => run(),
    measureValidation: async (_a: string, run: () => unknown) => run(),
    incrementGameAction: () => {}, incrementError: () => {} } as any;
  const adjacency = new AdjacencyService();
  const values = new ValueModifierService();
  const decks = new DeckManagementService();
  const registry = new HeroAbilityRegistry();
  if (opts.withAbilityConfigs) {
    // зеркало GameEngineModule.onModuleInit: generic-хендлеры героев
    for (const config of ABILITY_CONFIGS) {
      registry.registerExtended(new GenericHeroAbilityHandler(config, { deck: decks, zone: adjacency }));
    }
  }
  for (const config of opts.extraAbilityConfigs ?? []) {
    registry.registerExtended(new GenericHeroAbilityHandler(config, { deck: decks, zone: adjacency }));
  }
  const executor = new GameActionExecutorService(new GameRulesValidator(adjacency),
    new CombatResolverService(registry, metrics), undefined as any, values, adjacency, metrics,
    decks, new CardEffectExecutorService(values, metrics, adjacency, decks), registry);
  const service = new AiTurnService(
    { game: { findUnique: async () => ({ mode: 'VS_AI', status: 'IN_PROGRESS', opponentId: aiUserId }) } } as any,
    { withLockOptions: async (_key: string, run: () => Promise<boolean>) => run() } as any,
    { loadState: async () => clone(saved), saveState: async (id: string, state: GameState) => {
      if (overrides.save) return overrides.save(id, state);
      saved = clone(state);
      snapshots.push(saved);
    } } as any,
    { publishGameUpdate: async (id: string, event: string, state: GameState) => {
      if (overrides.publish) return overrides.publish(id, event, state);
      publishCalls.push({ event, seq: state.sequenceNumber });
      events.push(event);
    } } as any,
    executor, overrides.decide ? ({ decide: overrides.decide } as any) : new AiDecisionService(adjacency),
    combatTimeout as any,
    gameActionService as any,
  );
  return { run: () => service.maybeRunAiTurns(initial.gameId), state: () => saved, snapshots, events, publishCalls, combatTimeoutCalls, journal, executor, service };
}

describe('AiTurnService with the S03 production executor', () => {
  it('completes two begin/complete maneuvers without repeating draws or stalling on a distant path', async () => {
    const game = harness(fixture());
    await game.run();
    const state = game.state();
    expect(state.currentTurnPlayerId).toBe('human');
    expect(state.handZones.ai.cards.map(c => c.id)).toEqual(['draw-1', 'draw-2']);
    expect(state.handZones.human.cards).toEqual([]);
    expect(state.fighters[0].position).toEqual({ x: 4, y: 0 });
    expect(state.metadata.pendingManeuver).toBeUndefined();
    expect(game.snapshots).toHaveLength(4);
    expect(game.events).toEqual(['MANEUVER', 'MANEUVER', 'MANEUVER', 'MANEUVER']);
  });

  it('resumes a stored last-action maneuver without drawing again when movement is impossible', async () => {
    const initial = fixture();
    const game = harness({ ...initial,
      fighters: initial.fighters.map(f => f.ownerId === 'ai' ? { ...f, effects: [{ type: 'immobilized' }] } : f),
      handZones: { ...initial.handZones, ai: { cards: [card('already-drawn')], maxSize: 7 } },
      metadata: { ...initial.metadata, actionsRemaining: 0, pendingManeuver: { id: 'm1', playerId: 'ai' } } as any,
    });
    await game.run();
    expect(game.state().currentTurnPlayerId).toBe('human');
    expect(game.state().handZones.ai.cards.map(c => c.id)).toEqual(['already-drawn']);
    expect(game.state().decks.ai.drawPile).toHaveLength(2);
    expect(game.state().metadata.pendingManeuver).toBeUndefined();
    expect(game.snapshots).toHaveLength(1);
    expect(game.events).toEqual(['MANEUVER']);
  });

  it('resumes the owned discard choice and transfers the turn exactly once', async () => {
    const initial = fixture();
    const game = harness({ ...initial, phase: GamePhase.TURN_END,
      handZones: { ...initial.handZones, ai: { cards: Array.from({ length: 9 }, (_, i) => card(`instance-${i}`)), maxSize: 7 } },
      metadata: { ...initial.metadata, actionsRemaining: 0, pendingHandDiscard: { id: 'd1', playerId: 'ai', count: 2 } } as any,
    });
    await game.run();
    expect(game.state().currentTurnPlayerId).toBe('human');
    expect(game.state().handZones.ai.cards).toHaveLength(7);
    expect(game.state().discardPiles.ai.map(c => c.id)).toEqual(['instance-0', 'instance-1']);
    expect(game.state().metadata.pendingHandDiscard).toBeUndefined();
    expect(game.snapshots).toHaveLength(1);
    expect(game.events).toEqual(['CARD_DISCARDED']);
  });

  it('stops after lethal exhaustion at maneuver start', async () => {
    const initial = fixture();
    const game = harness({ ...initial,
      decks: { ...initial.decks, ai: { cards: [], drawPile: [] } },
      fighters: initial.fighters.map(f => f.ownerId === 'ai' ? { ...f, health: 1 } : f),
    });
    await game.run();
    expect(game.state().phase).toBe(GamePhase.GAME_OVER);
    expect(game.state().metadata.winnerId).toBe('human');
    expect(game.snapshots).toHaveLength(1);
    expect(game.events).toEqual(['MANEUVER', 'GAME_ENDED']);
  });
});

/** GD-039 Sol6: named-CUE публикация — best-effort ПОСЛЕ коммита saveState.
 *  Отказ Redis/PubSub не должен прерывать дрейн небоевого хода бота (иначе
 *  VS_AI-матч виснет до чужой мутации); отказ САМОГО saveState — обязан. */
describe('AiTurnService GD-039: публикация отказала после успешного save', () => {
  it('вторая публикация падает mid-turn → дрейн продолжает с закоммиченного состояния, seq идёт дальше', async () => {
    let calls = 0;
    const game = harness(fixture(), 'ai', {
      publish: async (_id, _event) => {
        calls += 1;
        if (calls === 2) throw new Error('pubsub down');
      },
    });
    await game.run();
    // дрейн дошёл до конца хода бота, а не оборвался на втором шаге
    expect(game.state().currentTurnPlayerId).toBe('human');
    expect(game.snapshots).toHaveLength(4);
    // шаг после упавшей публикации реально засейвлен и двинул seq
    expect(game.snapshots[2].sequenceNumber).toBeGreaterThan(game.snapshots[1].sequenceNumber);
    expect(calls).toBe(4);
  });

  it('отказ saveState всё ещё прерывает дрейн (не глотаем потерю персистентности)', async () => {
    const game = harness(fixture(), 'ai', {
      save: async () => { throw new Error('db down'); },
    });
    await expect(game.run()).resolves.toBeUndefined(); // сам drain не бросает
    expect(game.state().currentTurnPlayerId).toBe('ai'); // ход не завершён
    expect(game.snapshots).toHaveLength(0);
  });
});

/** GD-039 review: терминальные публикации/журналы независимы от судьбы
 *  соседней записи — отказ publish/recordAction самого действия НЕ глотает
 *  GAME_ENDED. И endTurn бота журналируется TURN_ENDED (GameActionType), а
 *  не TURN_CHANGED, который выпадал из enum → ход бота невидим eventsSince. */
describe('AiTurnService GD-039 review: терминал не глотается соседним отказом + endTurn-журнал', () => {
  /** Летальная exhaustion на старте манёвра — терминальный MANEUVER-шаг. */
  const lethalFixture = (): GameState => {
    const initial = fixture();
    return {
      ...initial,
      decks: { ...initial.decks, ai: { cards: [], drawPile: [] } },
      fighters: initial.fighters.map((f) => (f.ownerId === 'ai' ? { ...f, health: 1 } : f)),
    } as GameState;
  };

  it('publish действия падает на терминальном шаге → GAME_ENDED всё равно публикуется', async () => {
    const published: string[] = [];
    const game = harness(lethalFixture(), 'ai', {
      publish: async (_id, event) => {
        if (event !== 'GAME_ENDED') throw new Error('pubsub down');
        published.push(event);
      },
    });
    await game.run();
    expect(game.state().phase).toBe(GamePhase.GAME_OVER);
    expect(published).toEqual(['GAME_ENDED']);
  });

  it('recordAction действия падает на терминальном шаге → GAME_ENDED всё равно записан', async () => {
    const journaled: string[] = [];
    const game = harness(lethalFixture(), 'ai', {
      record: async (dto) => {
        if (dto.type !== 'GAME_ENDED') throw new Error('queue down');
        journaled.push(dto.type);
        return 'id';
      },
    });
    await game.run();
    expect(game.state().phase).toBe(GamePhase.GAME_OVER);
    expect(journaled).toEqual(['GAME_ENDED']);
  });

  it('обычный endTurn бота: событие и журнал TURN_ENDED, ход передан человеку', async () => {
    const initial = fixture();
    const game = harness({ ...initial,
      metadata: { ...initial.metadata, actionsRemaining: 0 } as any,
    });
    await game.run();
    expect(game.state().phase).not.toBe(GamePhase.GAME_OVER);
    expect(game.state().currentTurnPlayerId).toBe('human');
    expect(game.events).toEqual(['TURN_ENDED']);
    expect(game.journal.map((j) => j.type)).toEqual(['TURN_ENDED']);
    expect(game.journal[0].playerId).toBe('ai');
    expect(game.journal[0].metadata.action).toBe('ai:endTurn');
    expect(game.journal[0].sequenceNumber).toBe(game.state().sequenceNumber);
  });

  it('терминальный endTurn бота (авто turn-start урон смежному добивает героя бота): журнал TURN_ENDED + GAME_ENDED', async () => {
    // Dracula с RULE-02 бьёт только по выбору игрока — автоматический
    // turn-start урон даёт тестовый конфиг turn-damage
    const biter: AbilityConfig = {
      heroId: 'test-biter', abilityName: 'Test bite', description: 'turn-start: 1 урон смежному врагу',
      rules: [{ trigger: 'turn-start', effect: { kind: 'turn-damage', targetScope: 'enemy-adjacent', value: 1 } }],
    };
    const initial = fixture();
    const game = harness({ ...initial,
      metadata: { ...initial.metadata, actionsRemaining: 0 } as any,
      fighters: [
        { ...initial.fighters[0], health: 1, position: { x: 4, y: 0 } },
        { ...initial.fighters[1], heroSlug: 'test-biter', position: { x: 5, y: 0 } },
      ],
    } as GameState, 'ai', {}, { extraAbilityConfigs: [biter] });
    await game.run();
    expect(game.state().phase).toBe(GamePhase.GAME_OVER);
    expect(game.state().metadata.winnerId).toBe('human');
    expect(game.events).toEqual(['TURN_ENDED', 'GAME_ENDED']);
    expect(game.journal.map((j) => j.type)).toEqual(['TURN_ENDED', 'GAME_ENDED']);
    const [turn, end] = game.journal;
    expect(turn.metadata.action).toBe('ai:endTurn');
    expect(end.metadata).toMatchObject({ action: 'ai:endTurn', winnerId: 'human' });
    expect(end.sequenceNumber).toBe(game.state().sequenceNumber);
  });
});

/** GD-039: production VS_AI через полный матч. Оба сидa играются дрейном
 *  AiTurnService (детерминированные greedy-политики) на РЕАЛЬНОМ executor'е:
 *  фиксированные колоды (ATTACK 5 / DEFENSE 2), доска 12×2, без admin-правок.
 *  Критерии: матч доходит до GAME_OVER, раунд без прогресса seq = зависание. */
describe('AiTurnService GD-039: полный матч VS_AI без зависаний', () => {
  const atkCard = (id: string): HandCard => ({ id, cardId: 'atk', name: id, nameEn: id, nameRu: id,
    cardType: CardType.ATTACK, attackValue: 5, isVisible: true });
  const defCard = (id: string): HandCard => ({ id, cardId: 'def', name: id, nameEn: id, nameRu: id,
    cardType: CardType.DEFENSE, defenseValue: 2, isVisible: true });
  const deck = (prefix: string) =>
    Array.from({ length: 40 }, (_, i) => (i % 2 === 0 ? atkCard(`${prefix}-a${i}`) : defCard(`${prefix}-d${i}`)));

  function matchFixture(first: 'ai' | 'human'): GameState {
    return {
      gameId: 'ai-s10', sequenceNumber: 1, phase: GamePhase.ACTION_MANEUVER,
      turnCount: 1, currentTurnPlayerId: first,
      players: ['ai', 'human'].map(userId => ({ userId, heroId: userId,
        health: userId === 'ai' ? 8 : 6, maxHealth: userId === 'ai' ? 8 : 6,
        fighterIds: [`${userId}-hero`], isAlive: true })),
      fighters: [
        { id: 'ai-hero', ownerId: 'ai', heroId: 'ai', name: 'ai', type: FighterType.HERO,
          health: 8, maxHealth: 8, movement: 2, position: { x: 0, y: 0 }, effects: [],
          hasSidekick: false, attackType: 'melee' },
        { id: 'human-hero', ownerId: 'human', heroId: 'human', name: 'human', type: FighterType.HERO,
          health: 6, maxHealth: 6, movement: 2, position: { x: 11, y: 1 }, effects: [],
          hasSidekick: false, attackType: 'melee' },
      ],
      decks: { ai: { cards: [], drawPile: deck('ai') }, human: { cards: [], drawPile: deck('hu') } },
      handZones: { ai: { cards: [], maxSize: 7 }, human: { cards: [], maxSize: 7 } },
      discardPiles: { ai: [], human: [] }, boardState: createEmptyBoardState(12, 2),
      metadata: { lastActionAt: new Date(), lastActionBy: first, version: 1, actionsRemaining: 2 },
    } as GameState;
  }

  /** Два drain-сервиса (по одному на сид) над одним сохраняемым состоянием. */
  function matchHarness(initial: GameState) {
    let saved = initial;
    const metrics = { measureServiceDuration: async (_a: string, _b: string, run: () => unknown) => run(),
      measureValidation: async (_a: string, run: () => unknown) => run(),
      incrementGameAction: () => {}, incrementError: () => {} } as any;
    const adjacency = new AdjacencyService();
    const values = new ValueModifierService();
    const decks = new DeckManagementService();
    const registry = new HeroAbilityRegistry();
    const executor = new GameActionExecutorService(new GameRulesValidator(adjacency),
      new CombatResolverService(registry, metrics), undefined as any, values, adjacency, metrics,
      decks, new CardEffectExecutorService(values, metrics, adjacency, decks), registry);
    const mk = (uid: string) => new AiTurnService(
      { game: { findUnique: async () => ({ mode: 'VS_AI', status: 'IN_PROGRESS', opponentId: uid }) } } as any,
      { withLockOptions: async (_key: string, run: () => Promise<boolean>) => run() } as any,
      { loadState: async () => clone(saved),
        saveState: async (_id: string, state: GameState) => { saved = clone(state); } } as any,
      { publishGameUpdate: async () => {} } as any,
      executor, new AiDecisionService(adjacency),
    );
    return { run: (uid: string) => mk(uid).maybeRunAiTurns(initial.gameId), state: () => saved };
  }

  const playFullMatch = async (first: 'ai' | 'human') => {
    const m = matchHarness(matchFixture(first));
    for (let round = 0; round < 60; round++) {
      const before = m.state().sequenceNumber;
      await m.run('ai');
      if (m.state().phase === GamePhase.GAME_OVER) return m.state();
      await m.run('human');
      if (m.state().phase === GamePhase.GAME_OVER) return m.state();
      // целый раунд обоих дрейнов без движения seq при незавершённой игре = зависание
      expect(m.state().sequenceNumber).not.toBe(before);
    }
    throw new Error(`match did not finish: phase ${m.state().phase}, seq ${m.state().sequenceNumber}`);
  };

  it('бот ходит первым (seat 0): матч доходит до GAME_OVER, все обязательные выборы закрыты', async () => {
    const final = await playFullMatch('ai');
    expect(final.metadata.winnerId).toBeDefined();
    expect(final.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(final.metadata.pendingManeuver).toBeUndefined();
    expect(final.metadata.pendingHandDiscard).toBeUndefined();
  });

  it('бот вторым (seat 1, человек ходит первым): матч доходит до GAME_OVER', async () => {
    const final = await playFullMatch('human');
    expect(final.metadata.winnerId).toBeDefined();
    expect(final.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(final.metadata.pendingManeuver).toBeUndefined();
    expect(final.metadata.pendingHandDiscard).toBeUndefined();
  });

  it('окно защиты человека не отнимается: бот-атакующий ждёт защиты, резолвит только после неё', async () => {
    const initial = {
      ...matchFixture('ai'),
      fighters: [
        { ...matchFixture('ai').fighters[0], position: { x: 5, y: 0 } },
        { ...matchFixture('ai').fighters[1], position: { x: 6, y: 0 } },
      ],
      handZones: { ai: { cards: [atkCard('ai-a0')], maxSize: 7 }, human: { cards: [defCard('hu-d1')], maxSize: 7 } },
    } as GameState;
    const game = harness(initial);
    await game.run(); // бот атакует (смежно) и останавливается в ожидании защиты

    let st = game.state();
    expect(st.phase).toBe(GamePhase.COMBAT);
    expect(st.metadata.combatInfo?.defenderId).toBe('human');
    expect(st.metadata.combatInfo?.defenderCardId).toBeUndefined();

    // повторный дрейн НЕ резолвит бой и НЕ двигает seq — окно защиты человека
    const seqAtWindow = st.sequenceNumber;
    await game.run();
    expect(game.state().phase).toBe(GamePhase.COMBAT);
    expect(game.state().sequenceNumber).toBe(seqAtWindow);

    // человек сыграл защиту → следующий дрейн бота резолвит бой
    const defended = await game.executor.executePlayDefense(
      { gameId: 'ai-s10', cardId: 'hu-d1' },
      { userId: 'human', gameId: 'ai-s10', currentState: game.state() },
    );
    expect(defended.success).toBe(true);
    const res = await game.executor.executeResolveCombat(
      { gameId: 'ai-s10' },
      { userId: 'ai', gameId: 'ai-s10', currentState: defended.gameState! },
    );
    expect(res.success).toBe(true);
    expect(res.gameState!.phase).not.toBe(GamePhase.COMBAT);
    expect(res.gameState!.sequenceNumber).toBeGreaterThan(seqAtWindow);
  });

  /** GD-039 Sol6: атака бота обязана получать СВОЙ 30с DEFENSE-дедлайн
   *  (человек-защитник может отключиться), как и атака человека в
   *  game-actions.resolver; защита бота — RESOLVE-дедлайн, резолв — отмена. */
  it('атака бота планирует 30с DEFENSE-дедлайн по combatInfo.timeoutAt', async () => {
    const initial = {
      ...matchFixture('ai'),
      fighters: [
        { ...matchFixture('ai').fighters[0], position: { x: 5, y: 0 } },
        { ...matchFixture('ai').fighters[1], position: { x: 6, y: 0 } },
      ],
      handZones: { ai: { cards: [atkCard('ai-a0')], maxSize: 7 }, human: { cards: [], maxSize: 7 } },
    } as GameState;
    const game = harness(initial);
    await game.run(); // бот атакует и останавливается в окне защиты человека

    expect(game.events).toEqual(['ATTACK_INITIATED']);
    expect(game.state().phase).toBe(GamePhase.COMBAT);
    const sched = game.combatTimeoutCalls.filter((c) => c.op === 'schedule');
    expect(sched).toHaveLength(1);
    const [gameId, delaySeconds, seq, stage] = sched[0].args as [string, number, number, string];
    expect(gameId).toBe('ai-s10');
    expect(stage).toBe('DEFENSE');
    expect(delaySeconds).toBeGreaterThanOrEqual(29);
    expect(delaySeconds).toBeLessThanOrEqual(30);
    expect(seq).toBe(game.state().sequenceNumber);
  });

  it('защита бота планирует RESOLVE-дедлайн, резолв боя ботом отменяет расписания', async () => {
    const base = matchFixture('human');
    const initial = {
      ...base,
      phase: GamePhase.COMBAT,
      fighters: [
        { ...base.fighters[0], position: { x: 5, y: 0 } },
        { ...base.fighters[1], position: { x: 6, y: 0 } },
      ],
      handZones: { ai: { cards: [defCard('ai-d1')], maxSize: 7 }, human: { cards: [], maxSize: 7 } },
      metadata: {
        lastActionAt: new Date(), lastActionBy: 'human', version: 1, actionsRemaining: 1,
        combatInfo: {
          attackerId: 'human-hero', defenderId: 'ai', targetFighterId: 'ai-hero',
          attackValue: 3, attackerCardId: 'hu-a0',
          startedAt: new Date(Date.now() - 1000),
          timeoutAt: new Date(Date.now() + DEFENSE_TIMEOUT_SECONDS * 1000),
        },
      } as any,
    } as GameState;
    const game = harness(initial);
    await game.run(); // защита бота → RESOLVE-окно → бот сам резолвит

    expect(game.events).toEqual(['DEFENSE_PLAYED', 'COMBAT_RESOLVED']);
    const sched = game.combatTimeoutCalls.filter((c) => c.op === 'schedule');
    expect(sched).toHaveLength(1);
    const [, delaySeconds, seq, stage] = sched[0].args as [string, number, number, string];
    expect(stage).toBe('RESOLVE');
    expect(delaySeconds).toBeGreaterThanOrEqual(9);
    expect(delaySeconds).toBeLessThanOrEqual(10);
    expect(seq).toBe(game.snapshots[0].sequenceNumber);
    const cancels = game.combatTimeoutCalls.filter((c) => c.op === 'cancel');
    expect(cancels).toHaveLength(1);
    expect(game.state().phase).toBe(GamePhase.ACTION_MANEUVER);
  });

  /** GD-039 Sol6: действия бота обязаны попадать в журнал GameAction —
   *  иначе eventsSince-катчап человека пропускает весь ход бота. Input бота
   *  (id карт) приватен: getEventsSince отдаёт input только владельцу действия. */
  it('терминальный ход бота журналируется: действие + GAME_ENDED с winnerId', async () => {
    const initial = fixture();
    const game = harness({
      ...initial,
      decks: { ...initial.decks, ai: { cards: [], drawPile: [] } },
      fighters: initial.fighters.map((f) => (f.ownerId === 'ai' ? { ...f, health: 1 } : f)),
    });
    await game.run();

    expect(game.state().phase).toBe(GamePhase.GAME_OVER);
    expect(game.journal.map((j) => j.type)).toEqual(['MANEUVER', 'GAME_ENDED']);
    const [step, end] = game.journal;
    expect(step.playerId).toBe('ai');
    // летальная exhaustion завершает игру тем же seq, что и сам шаг манёвра
    expect(step.sequenceNumber).toBe(game.state().sequenceNumber);
    expect(step.metadata.action).toBe('ai:beginManeuver');
    expect(end.metadata).toMatchObject({ action: 'ai:beginManeuver', winnerId: 'human' });
    expect(end.sequenceNumber).toBe(game.state().sequenceNumber);
  });
});

/** GD-039 Sol6: проекция eventsSince для журнала бота — человек не видит
 *  input бота (id карт), бот видит свой. */
describe('AiTurnService GD-039: приватность bot-журнала в eventsSince', () => {
  const { GameStateService } = require('../game-state.service');

  it('человек-зритель не получает input записей бота, бот — получает', async () => {
    const botEntry = {
      gameId: 'g', sequenceNumber: 5, type: 'DEFENSE_PLAYED', playerId: 'ai',
      timestamp: new Date(),
      payload: { action: 'ai:defense', input: { cardId: 'secret-instance-9' } },
    };
    const humanEntry = {
      gameId: 'g', sequenceNumber: 6, type: 'MANEUVER', playerId: 'human',
      timestamp: new Date(),
      payload: { action: 'maneuver', input: { moves: [] } },
    };
    const prisma: any = {
      gameAction: { findMany: async () => [botEntry, humanEntry] },
    };
    const service = new GameStateService(prisma, {} as any, undefined);

    const humanView = await service.getEventsSince('g', 0, 'human');
    const botView = await service.getEventsSince('g', 0, 'ai');

    const humanBotEntry = JSON.parse(humanView.find((e) => e.sequenceNumber === 5)!.payload);
    expect(humanBotEntry).toEqual({ action: 'ai:defense' }); // без input/карт
    expect(JSON.stringify(humanView)).not.toContain('secret-instance-9');

    const botOwnEntry = JSON.parse(botView.find((e) => e.sequenceNumber === 5)!.payload);
    expect(botOwnEntry.input).toEqual({ cardId: 'secret-instance-9' });
  });
});

// AI-03 / SEL-04 (docs/research/de-reverse-2026-10-20): вне боя у VS_AI нет
// дедлайна — если эвристика вернула null на собственном выборе бота или
// executor отверг её ответ, бот молча вставал. Теперь — запасной легальный
// ответ (системный фолбэк таймаута или перебор) и громкий лог AI_FALLBACK.
describe('AiTurnService AI-03: запасной легальный ответ бота', () => {
  const real = new AiDecisionService(new AdjacencyService());
  const withHead = (head: Record<string, unknown>): GameState => {
    const base = fixture();
    return { ...base, metadata: { ...base.metadata, pendingEffects: [head] } } as unknown as GameState;
  };
  const spyLogs = (service: AiTurnService) => {
    const logger = (service as any).logger;
    return { warn: jest.spyOn(logger, 'warn').mockImplementation(() => {}),
      error: jest.spyOn(logger, 'error').mockImplementation(() => {}) };
  };
  const logged = (spy: jest.SpyInstance) => spy.mock.calls.map((c) => String(c[0]));

  it('executor отверг ответ эвристики на своём mandatory CHOOSE_ONE → системный фолбэк, матч идёт дальше', async () => {
    const game = harness(
      withHead({ id: 'ch-1', type: 'CHOOSE_ONE', playerId: 'ai', chooseCount: 1, text: 'Choose one',
        options: [{ index: 0, label: 'A' }, { index: 1, label: 'B' }], optionEffects: [[], []] }),
      'ai',
      { decide: (s, ai) => s.metadata.pendingEffects?.[0]?.id === 'ch-1'
        ? { kind: 'resolveChoose', effectId: 'ch-1', optionIndex: 99 } : real.decide(s, ai) },
    );
    const logs = spyLogs(game.service);
    await game.run();
    expect(game.snapshots[0].sequenceNumber).toBe(11);
    expect(game.snapshots[0].metadata.pendingEffects ?? []).toHaveLength(0);
    expect(logged(logs.warn)).toContainEqual(expect.stringContaining(
      'AI_FALLBACK game=ai-s03 seq=10 reason=rejected:resolveChoose head=CHOOSE_ONE/ch-1 -> resolveChoose'));
    expect(game.events[0]).toBe('CARD_PLAYED');
    expect(game.state().currentTurnPlayerId).toBe('human');
  });

  it('эвристика вернула null на своём mandatory MOVE → нулевой шаг системного фолбэка', async () => {
    const game = harness(
      withHead({ id: 'mv-1', type: 'MOVE', playerId: 'ai', value: 2, text: 'Move up to 2', fighterIds: ['ai-hero'] }),
      'ai',
      { decide: (s, ai) => (s.metadata.pendingEffects?.[0]?.id === 'mv-1' ? null : real.decide(s, ai)) },
    );
    const logs = spyLogs(game.service);
    await game.run();
    expect(game.snapshots[0].metadata.pendingEffects ?? []).toHaveLength(0);
    expect(game.snapshots[0].fighters.find((f) => f.id === 'ai-hero')!.position).toEqual({ x: 0, y: 0 });
    expect(logged(logs.warn)).toContainEqual(expect.stringContaining(
      'reason=no-decision head=MOVE/mv-1 -> resolveMove'));
  });

  it('выбор человека в голове очереди: бот ждёт без фолбэка и без шума в логе', async () => {
    const initial = withHead({ id: 'h-1', type: 'MOVE', playerId: 'human', value: 1, text: 'Move', fighterIds: ['human-hero'] });
    const game = harness({ ...initial, currentTurnPlayerId: 'human' });
    const logs = spyLogs(game.service);
    await game.run();
    expect(game.snapshots).toHaveLength(0);
    expect([...logged(logs.warn), ...logged(logs.error)].filter((l) => l.includes('AI_FALLBACK'))).toEqual([]);
  });

  it('запасного ответа нет: громкий AI_FALLBACK error, состояние не тронуто', async () => {
    const game = harness(
      withHead({ id: 'ch-0', type: 'CHOOSE_ONE', playerId: 'ai', chooseCount: 1, text: 'Choose one', options: [] }),
      'ai',
      { decide: () => ({ kind: 'resolveChoose', effectId: 'ch-0', optionIndex: 0 }) },
    );
    const logs = spyLogs(game.service);
    await game.run();
    expect(game.snapshots).toHaveLength(0);
    expect(logged(logs.error)).toContainEqual(expect.stringContaining(
      'AI_FALLBACK game=ai-s03 seq=10 reason=rejected:resolveChoose head=CHOOSE_ONE/ch-0: запасного ответа нет'));
  });
});
