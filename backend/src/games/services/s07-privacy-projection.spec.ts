/** GD-025 / ACC-009 + ACC-018: единая viewer-aware projection.
 *  Негативные проверки СЫРОГО JSON для обеих сторон, spectator-гейта,
 *  событий журнала и стадий до/после reveal. Никаких test-only обходов:
 *  ровно те функции, что стоят в query/mutation/subscription путях. */
import { GameStateService } from '../game-state.service';
import { GamePhase, CardType, FighterType } from '../../game-engine/models';
import { s03Engine } from '../../test/fixtures/s03-engine.fixture';
import type { GameState, Fighter } from '../game-state.service';

// --- Минимальные моки инфраструктуры (как в s06-full-games) ---
function makeDeps(participants: string[] = ['a', 'b']) {
  const gameActions: any[] = [];
  const prisma: any = {
    gamePlayer: {
      findUnique: async ({ where }: any) =>
        participants.includes(where.gameId_userId.userId)
          ? { id: `p-${where.gameId_userId.userId}` }
          : null,
    },
    gameState: { findUnique: async () => null, upsert: async ({ create }: any) => create },
    game: { update: async () => ({}) },
    gameAction: { findMany: async () => gameActions },
    $transaction: async (run: (tx: unknown) => unknown) => run(prisma),
  };
  const redis: any = { getJson: async () => null, setJsonex: async () => 'OK', del: async () => 1 };
  const published: any[] = [];
  const service = new GameStateService(prisma, redis, {
    publishGameUpdate: async (gameId: string, eventType: string, state: GameState) => {
      published.push({ gameId, eventType, sequenceNumber: state.sequenceNumber });
    },
  } as any);
  return { prisma, service, published, gameActions };
}

// --- Fixture: смежные бойцы, атакующая/защитная карты в руках ---
const atkCard = { id: 'atk-1', cardId: 'cat-atk', name: 'Spike Growth', nameEn: 'Spike Growth', nameRu: 'Шипы', cardType: CardType.VERSATILE, attackValue: 4, effects: [] } as any;
const defCard = { id: 'def-1', cardId: 'cat-def', name: 'Shadow Slip', nameEn: 'Shadow Slip', nameRu: 'Тень', cardType: CardType.VERSATILE, defenseValue: 2, effects: [] } as any;
const bHandCard = { id: 'b-secret-1', cardId: 'cat-scheme', name: 'Secret Scheme', nameEn: 'Secret Scheme', nameRu: 'Секрет', cardType: CardType.SCHEME, effects: [] } as any;
// публичные «старые» карты сброса — БЕЗ значений боя фикстуры (иначе raw-JSON
// ассерты ловят значения из публичного сброса, а не из скрытой проекции)
const aOldPublic = { id: 'a-old-public', cardId: 'cat-old-a', name: 'Old Feint', nameEn: 'Old Feint', nameRu: 'Старый финт', cardType: CardType.SCHEME, effects: [] } as any;
const bOldPublic = { id: 'b-old-public', cardId: 'cat-old-b', name: 'Old Scheme', nameEn: 'Old Scheme', nameRu: 'Старый план', cardType: CardType.SCHEME, effects: [] } as any;

function combatFixture(): GameState {
  const fighters: Fighter[] = [
    { id: 'fA', ownerId: 'a', heroId: 'ha', name: 'HeroA', type: FighterType.HERO, health: 10, maxHealth: 10, position: { x: 0, y: 0 }, effects: [], hasSidekick: false, attackType: 'melee' },
    { id: 'fB', ownerId: 'b', heroId: 'hb', name: 'HeroB', type: FighterType.HERO, health: 10, maxHealth: 10, position: { x: 1, y: 0 }, effects: [], hasSidekick: false, attackType: 'melee' },
  ] as any;
  return {
    gameId: 'g1', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER, turnCount: 1, currentTurnPlayerId: 'a',
    players: ['a', 'b'].map(userId => ({ userId, heroId: userId, health: 10, maxHealth: 10, fighterIds: [userId], isAlive: true })),
    fighters,
    decks: {
      a: { cards: [atkCard], drawPile: [{ ...atkCard, id: 'a-deck-1' }, { ...atkCard, id: 'a-deck-2' }] },
      b: { cards: [defCard], drawPile: [{ ...defCard, id: 'b-deck-1' }] },
    },
    discardPiles: {
      a: [aOldPublic],
      b: [bOldPublic],
    },
    handZones: {
      a: { cards: [{ ...atkCard, isVisible: true }], maxSize: 7 },
      b: { cards: [{ ...defCard, isVisible: true }, { ...bHandCard, isVisible: true }], maxSize: 7 },
    },
    boardState: { width: 4, height: 1, cells: [[{ x: 0, y: 0, type: 'normal' }, { x: 1, y: 0, type: 'normal' }, { x: 2, y: 0, type: 'normal' }, { x: 3, y: 0, type: 'normal' }]], doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date(), lastActionBy: 'a', version: 1, actionsRemaining: 2 },
  } as any;
}

describe('S07 GD-025 viewer-aware projection (raw JSON)', () => {
  it('attacker view pre-reveal: own attack value, NO defender value/identity/deck order', async () => {
    const { service } = makeDeps();
    const state = await declaredAttackRaw();
    // защита сыграна, резолв ещё не запущен (COMBAT_RESOLVE без progress)
    const defended = await playedDefenseRaw(state);
    const attackerView = service.filterPrivateData(defended, 'a');
    const raw = JSON.stringify(attackerView);

    expect(raw).toContain('"attackValue":4');
    expect(raw).toContain('atk-1'); // своя committed-карта
    expect(raw).not.toContain('"defenseValue":2');
    expect(raw).not.toContain('def-1');
    // порядок/личины колод скрыты обеим сторонам
    expect(raw).not.toContain('a-deck-1');
    expect(raw).not.toContain('b-deck-1');
    expect(attackerView.decks.a.drawPile.length).toBe(2);
    expect(attackerView.decks.a.topCard).toBeUndefined();
    // чужая рука — плейсхолдеры без личин
    expect(raw).not.toContain('Secret Scheme');
    expect(raw).toContain('hidden-');
    // собственная рука видна
    expect(raw).toContain('Spike Growth');
    // публичный сброс доступен (ACC-018)
    expect(raw).toContain('b-old-public');
  });

  it('defender view pre-reveal: own defense, NO attacker value/identity', async () => {
    const { service } = makeDeps();
    const state = await declaredAttackRaw();
    const defended = await playedDefenseRaw(state);
    const defenderView = service.filterPrivateData(defended, 'b');
    const raw = JSON.stringify(defenderView);

    expect(raw).toContain('"defenseValue":2');
    expect(raw).toContain('def-1');
    expect(raw).not.toContain('"attackValue":4');
    expect(raw).not.toContain('atk-1');
    // собственная committed-карта защитника видна ему в сбросе
    expect(raw).toContain('Shadow Slip');
    // чужая (атакующая) committed-карта — плейсхолдер в сбросе атакующего
    const attackerPile = defenderView.discardPiles.a;
    expect(attackerPile.some(c => c.cardId === 'hidden')).toBe(true);
    expect(JSON.stringify(attackerPile)).not.toContain('Spike Growth');
    // своя рука видна, чужая — нет
    expect(raw).toContain('Secret Scheme');
  });

  it('post-reveal: обе стороны видят значения и личины обеих карт', async () => {
    const { service } = makeDeps();
    const state = await declaredAttackRaw();
    const defended = await playedDefenseRaw(state);
    // reveal = первый pause() резолва пишет combatResolutionProgress
    const revealed: GameState = {
      ...defended,
      metadata: { ...defended.metadata, combatResolutionProgress: { defeatedBefore: [] } as any },
    };
    for (const viewer of ['a', 'b']) {
      const raw = JSON.stringify(service.filterPrivateData(revealed, viewer));
      expect(raw).toContain('"attackValue":4');
      expect(raw).toContain('"defenseValue":2');
      expect(raw).toContain('Spike Growth');
      expect(raw).toContain('Shadow Slip');
    }
  });

  it('spectator не получает состояние: isParticipant=false гейтит подписки/журнал', async () => {
    const { service } = makeDeps(['a', 'b']);
    await expect(service.isParticipant('g1', 'z')).resolves.toBe(false);
    await expect(service.isParticipant('g1', 'a')).resolves.toBe(true);
  });

  it('eventsSince: input мутаций виден только владельцу действия', async () => {
    const { service, gameActions } = makeDeps();
    gameActions.push(
      { sequenceNumber: 11, type: 'DEFENSE_PLAYED', gameId: 'g1', playerId: 'b', timestamp: new Date(), payload: { action: 'playDefense', input: { gameId: 'g1', cardId: 'def-1' } } },
      { sequenceNumber: 12, type: 'ATTACK_INITIATED', gameId: 'g1', playerId: 'a', timestamp: new Date(), payload: { action: 'attack', input: { gameId: 'g1', cardId: 'atk-1' } } },
    );
    const forAttacker = await service.getEventsSince('g1', 10, 'a');
    expect(JSON.stringify(forAttacker)).not.toContain('def-1');
    expect(JSON.stringify(forAttacker)).toContain('atk-1'); // своё
    const forDefender = await service.getEventsSince('g1', 10, 'b');
    expect(JSON.stringify(forDefender)).toContain('def-1');
    expect(JSON.stringify(forDefender)).not.toContain('atk-1');
    // каждое событие остаётся журналом, не состоянием
    for (const e of forAttacker) {
      const parsed = JSON.parse(e.payload);
      expect(parsed).toHaveProperty('action');
      expect(parsed).not.toHaveProperty('handZones');
    }
  });

  it('serialization roundtrip проекции не ломает состояние (lossy-регрессия)', async () => {
    const { service } = makeDeps();
    const state = await declaredAttackRaw();
    const defended = await playedDefenseRaw(state);
    const view = service.filterPrivateData(defended, 'a');
    const serialized = service.serialize(view as any);
    const restored = service.deserialize(serialized);
    expect(restored.sequenceNumber).toBe(defended.sequenceNumber);
    expect(restored.phase).toBe(GamePhase.COMBAT_RESOLVE);
    expect(restored.fighters.length).toBe(2);
  });
});

// --- Хелперы реального executor-пути (attack → defense) ---
async function declaredAttackRaw(): Promise<GameState> {
  const { executor } = s03Engine();
  const base = combatFixture();
  const result = await executor.executeAttack(
    { gameId: 'g1', attackerId: 'fA', targetId: 'fB', cardId: 'atk-1' } as any,
    { userId: 'a', gameId: 'g1', currentState: base },
  );
  expect(result.success).toBe(true);
  return result.gameState!;
}

async function playedDefenseRaw(state: GameState): Promise<GameState> {
  const { executor } = s03Engine();
  const result = await executor.executePlayDefense(
    { gameId: 'g1', cardId: 'def-1' } as any,
    { userId: 'b', gameId: 'g1', currentState: state },
  );
  expect(result.success).toBe(true);
  return result.gameState!;
}
