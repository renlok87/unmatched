/** GD-017 end-to-end: Medusa turn-start TARGET_FIGHTER pending (owner-bound,
 * optional, no auto-target) + Arthur ability-BOOST атак (R-15: только сам
 * King Arthur; R-16: Feint-CANCEL сбрасывает boost, печатное значение
 * остаётся). Реальный executor + реальный registry/adjacency/decks. */
import * as fs from 'fs';
import * as path from 'path';
import { GameState, PendingEffect } from '../models';
import { Card, CardType, FighterType, GamePhase } from '../models';
import { normalizeCardEffects } from '../models';
import { parseCardEffectTexts } from '../effects/effect-text-parser';
import { GameActionExecutorService } from './game-action-executor.service';
import { DeckManagementService } from './deck-management.service';
import { CardEffectExecutorService } from '../effects/card-effect-executor.service';
import { GameRulesValidator } from '../validators/game-rules.validator';
import { AdjacencyService } from '../engine/adjacency.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { CombatResolverService } from '../engine/combat-resolver.service';
import { HeroAbilityRegistry } from '../abilities/hero-ability-registry';
import { GenericHeroAbilityHandler } from '../abilities/generic-hero-ability.handler';
import { ABILITY_CONFIGS } from '../abilities/ability-config';
import { arthurAbilityHandler } from '../abilities/heroes';
import { MovementService } from '../engine/movement.service';
import { AStarService, PathCacheService } from '../movement';

const metrics = {
  measureServiceDuration: async (_a: string, _b: string, run: () => unknown) => run(),
  measureValidation: async (_a: string, run: () => unknown) => run(),
  incrementGameAction: () => {},
  incrementError: () => {},
} as any;

const adjacency = new AdjacencyService();
const decks = new DeckManagementService();
const values = new ValueModifierService();
const registry = new HeroAbilityRegistry();
registry.registerExtended(
  new GenericHeroAbilityHandler(
    ABILITY_CONFIGS.find((c) => c.heroId === 'medusa')!,
    { zone: adjacency, deck: decks },
  ),
);
registry.register(arthurAbilityHandler);
const effects = new CardEffectExecutorService(values, metrics, adjacency, decks);
const executor = new GameActionExecutorService(
  new GameRulesValidator(adjacency),
  new CombatResolverService(registry, metrics),
  new MovementService(new AStarService(), new PathCacheService()),
  values,
  adjacency,
  metrics,
  decks,
  effects,
  registry,
);

const ctx = (state: GameState, userId: string) =>
  ({ userId, gameId: state.gameId, currentState: state }) as any;

const arthurCapture = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../../../..', 'docs/game-design/evidence/S01/content-king-arthur.json'),
    'utf8',
  ),
) as { cards: Array<Record<string, any>> };

/** Production ingest (mirrors GameInitializationService.resolveCardEffects). */
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

// --- board: 8×2, x 0..3 = 'west', x 4..7 = 'east'
function s05State(opts?: { bheroAt?: { x: number; y: number } }): GameState {
  const cells = Array.from({ length: 2 }, (_, y) =>
    Array.from({ length: 8 }, (_, x) => ({ x, y, type: 'normal', zones: x <= 3 ? ['west'] : ['east'] })));
  const fighters = [
    { id: 'medusa', ownerId: 'm', heroId: 'm', heroSlug: 'medusa', name: 'Medusa', type: FighterType.HERO,
      health: 16, maxHealth: 16, position: { x: 2, y: 0 }, effects: [], hasSidekick: true, movement: 3 },
    { id: 'harpy1', ownerId: 'm', heroId: 'm', heroSlug: 'medusa', name: 'Harpies 1', type: FighterType.MINION,
      health: 1, maxHealth: 1, position: { x: 1, y: 0 }, effects: [], hasSidekick: false, movement: 3 },
    { id: 'bhero', ownerId: 'b', heroId: 'b', name: 'Enemy Hero', type: FighterType.HERO,
      health: 12, maxHealth: 12, position: { x: 3, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
    { id: 'bfar', ownerId: 'b', heroId: 'b', name: 'Enemy Far', type: FighterType.MINION,
      health: 10, maxHealth: 10, position: { x: 6, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
  ].map((f) => (f.id === 'bhero' && opts?.bheroAt ? { ...f, position: opts.bheroAt } : f)) as GameState['fighters'];
  return {
    gameId: 's05h', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER,
    turnCount: 1, currentTurnPlayerId: 'b',
    players: ['m', 'b'].map((userId) => ({ userId, heroId: userId, health: 16, maxHealth: 16, fighterIds: [], isAlive: true })),
    fighters,
    decks: { m: { cards: [], drawPile: [] }, b: { cards: [], drawPile: [] } },
    handZones: { m: { cards: [], maxSize: 7 }, b: { cards: [], maxSize: 7 } },
    discardPiles: { m: [], b: [] },
    boardState: { width: 8, height: 2, cells, doors: {}, fog: {}, tokens: {} } as any,
    metadata: { lastActionAt: new Date(0), lastActionBy: 'b', version: 1, actionsRemaining: 0 },
  } as GameState;
}

describe('GD-017: Medusa — turn-start pending (owner-bound, optional, no auto-target)', () => {
  it('positive: конец хода b → ход m → TARGET_FIGHTER pending на врага В ЗОНЕ Medusa', async () => {
    const result = await executor.executeEndTurn({ gameId: 's05h' } as any, ctx(s05State(), 'b'));

    expect(result.success).toBe(true);
    expect(result.gameState!.currentTurnPlayerId).toBe('m');
    // авто-урона НЕТ — выбор за владельцем
    const bhero = result.gameState!.fighters.find((f) => f.id === 'bhero')!;
    expect(bhero.health).toBe(12);
    const pendings = (result.gameState!.metadata.pendingEffects ?? []) as PendingEffect[];
    expect(pendings).toHaveLength(1);
    expect(pendings[0].type).toBe('TARGET_FIGHTER');
    expect(pendings[0].targetFighterIds).toEqual(['bhero']); // bfar вне зоны, harpy1 свой
    expect(pendings[0].damage).toBe(1);
    expect(pendings[0].optional).toBe(true);
    expect(pendings[0].playerId).toBe('m');
  });

  it('positive: resolveTargetFighter через executor → 1 урон, очередь пуста', async () => {
    const afterTurn = await executor.executeEndTurn({ gameId: 's05h' } as any, ctx(s05State(), 'b'));
    const pending = afterTurn.gameState!.metadata.pendingEffects![0];

    const resolved = await executor.executeResolvePendingEffect(
      { gameId: 's05h', effectId: pending.id, fighterId: 'bhero' } as any,
      ctx(afterTurn.gameState!, 'm'));

    expect(resolved.success).toBe(true);
    expect(resolved.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(11);
    expect(resolved.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('negative: владелец pending — только m; b отклонён («принадлежит другому игроку»)', async () => {
    const afterTurn = await executor.executeEndTurn({ gameId: 's05h' } as any, ctx(s05State(), 'b'));
    const pending = afterTurn.gameState!.metadata.pendingEffects![0];

    const resolved = await executor.executeResolvePendingEffect(
      { gameId: 's05h', effectId: pending.id, fighterId: 'bhero' } as any,
      ctx(afterTurn.gameState!, 'b'));

    expect(resolved.success).toBe(false);
    expect(resolved.error).toContain('принадлежит другому игроку');
  });

  it('positive: decline optional-выбора («you may») → без урона, очередь пуста', async () => {
    const afterTurn = await executor.executeEndTurn({ gameId: 's05h' } as any, ctx(s05State(), 'b'));
    const pending = afterTurn.gameState!.metadata.pendingEffects![0];

    const declined = await executor.executeDeclinePendingEffect(
      { gameId: 's05h', effectId: pending.id } as any,
      ctx(afterTurn.gameState!, 'm'));

    expect(declined.success).toBe(true);
    expect(declined.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(12);
    expect(declined.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('negative: врагов в зоне нет → pending не создаётся (no-op)', async () => {
    // bhero уходит в east (6,1); bfar уже в east — в зоне Medusa врагов нет
    const result = await executor.executeEndTurn(
      { gameId: 's05h' } as any, ctx(s05State({ bheroAt: { x: 6, y: 1 } }), 'b'));

    expect(result.success).toBe(true);
    expect(result.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(12);
    expect(result.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });
});

describe('GD-017/R-15: Arthur ability-BOOST (только атака самого King Arthur)', () => {
  function arthurState(): GameState {
    const cells = Array.from({ length: 2 }, (_, y) =>
      Array.from({ length: 8 }, (_, x) => ({ x, y, type: 'normal' })));
    const fighters = [
      { id: 'arthur', ownerId: 'a', heroId: 'a', heroSlug: 'king-arthur', name: 'King Arthur',
        type: FighterType.HERO, health: 18, maxHealth: 18, position: { x: 3, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
      { id: 'merlin', ownerId: 'a', heroId: 'a', heroSlug: 'merlin', name: 'Merlin',
        type: FighterType.HERO, health: 14, maxHealth: 14, position: { x: 1, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
      { id: 'bhero', ownerId: 'b', heroId: 'b', name: 'Enemy Hero', type: FighterType.HERO,
        health: 12, maxHealth: 12, position: { x: 2, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
    ] as GameState['fighters'];
    return {
      gameId: 's05a', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER,
      turnCount: 1, currentTurnPlayerId: 'a',
      players: ['a', 'b'].map((userId) => ({ userId, heroId: userId, health: 18, maxHealth: 18, fighterIds: [], isAlive: true })),
      fighters,
      decks: { a: { cards: [], drawPile: [] }, b: { cards: [], drawPile: [] } },
      handZones: {
        a: { cards: [
          { ...arthurCard('Swift Strike'), isVisible: true },
          { ...arthurCard('Excalibur'), isVisible: true },
        ], maxSize: 7 },
        b: { cards: [], maxSize: 7 },
      },
      discardPiles: { a: [], b: [] },
      boardState: { width: 8, height: 2, cells, doors: {}, fog: {}, tokens: {} } as any,
      metadata: { lastActionAt: new Date(0), lastActionBy: 'a', version: 1, actionsRemaining: 2 },
    } as GameState;
  }

  it('positive: Arthur атакует Swift Strike(3) + Excalibur как ability-BOOST(3) → attackValue печатное, boostValue отдельно, обе карты в сброс', async () => {
    const state = arthurState();
    const attack = await executor.executeAttack(
      { gameId: 's05a', attackerId: 'arthur', targetId: 'bhero', cardId: state.handZones.a.cards[0].id, abilityBoostCardId: state.handZones.a.cards[1].id } as any,
      ctx(state, 'a'));

    expect(attack.success).toBe(true);
    const ci = attack.gameState!.metadata.combatInfo!;
    expect(ci.attackValue).toBe(3);          // печатное значение Swift Strike
    expect(ci.boostValue).toBe(3);           // Excalibur boost, ability-слот
    expect(ci.cardBoostCardId).toBeUndefined();
    expect(ci.abilityBoostCardId).toBe(state.handZones.a.cards[1].id);
    const discarded = attack.gameState!.discardPiles.a.map((c) => c.id);
    expect(discarded).toContain(state.handZones.a.cards[0].id);
    expect(discarded).toContain(state.handZones.a.cards[1].id);
  });

  it('negative: Merlin с abilityBoostCardId → отказ (только атака самого героя)', async () => {
    const state = arthurState();
    const attack = await executor.executeAttack(
      { gameId: 's05a', attackerId: 'merlin', targetId: 'bhero', cardId: state.handZones.a.cards[0].id, abilityBoostCardId: state.handZones.a.cards[1].id } as any,
      ctx(state, 'a'));

    expect(attack.success).toBe(false);
    expect(attack.error).toContain('Способность героя не разрешает BOOST');
  });

  it('negative: ability-boost той же картой, что атака → отказ', async () => {
    const state = arthurState();
    const attack = await executor.executeAttack(
      { gameId: 's05a', attackerId: 'arthur', targetId: 'bhero', cardId: state.handZones.a.cards[0].id, abilityBoostCardId: state.handZones.a.cards[0].id } as any,
      ctx(state, 'a'));

    expect(attack.success).toBe(false);
    expect(attack.error).toContain('Нельзя BOOST-ить атаку той же картой');
  });
});

describe('GD-017/R-16: отменённый Feint-ом boost сбрасывается без эффекта', () => {
  function combatState(defense: Card): GameState {
    const cells = Array.from({ length: 2 }, (_, y) =>
      Array.from({ length: 8 }, (_, x) => ({ x, y, type: 'normal' })));
    const fighters = [
      { id: 'arthur', ownerId: 'a', heroId: 'a', heroSlug: 'king-arthur', name: 'King Arthur',
        type: FighterType.HERO, health: 18, maxHealth: 18, position: { x: 3, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
      { id: 'bhero', ownerId: 'b', heroId: 'b', name: 'Enemy Hero', type: FighterType.HERO,
        health: 12, maxHealth: 12, position: { x: 2, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
    ] as GameState['fighters'];
    return {
      gameId: 's05r', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER,
      turnCount: 1, currentTurnPlayerId: 'a',
      players: ['a', 'b'].map((userId) => ({ userId, heroId: userId, health: 18, maxHealth: 18, fighterIds: [], isAlive: true })),
      fighters,
      decks: { a: { cards: [], drawPile: [] }, b: { cards: [], drawPile: [] } },
      handZones: {
        a: { cards: [
          { ...arthurCard('Swift Strike'), isVisible: true },
          { ...arthurCard('Excalibur'), isVisible: true },
        ], maxSize: 7 },
        b: { cards: [{ ...defense, isVisible: true }], maxSize: 7 },
      },
      discardPiles: { a: [], b: [] },
      boardState: { width: 8, height: 2, cells, doors: {}, fog: {}, tokens: {} } as any,
      metadata: { lastActionAt: new Date(0), lastActionBy: 'a', version: 1, actionsRemaining: 2 },
    } as GameState;
  }

  const plainDefense: Card = { id: 'plaindef::0', cardId: 'plaindef', name: 'Plain Defense', nameEn: 'Plain Defense',
    nameRu: 'Plain Defense', cardType: CardType.DEFENSE, defenseValue: 2, effects: [] } as Card;

  it('без отмены: урон = печатное(3) + boost(3) − защита(2) = 4; эффекты Swift Strike живут (MOVE pending)', async () => {
    const state = combatState(plainDefense);
    const attack = await executor.executeAttack(
      { gameId: 's05r', attackerId: 'arthur', targetId: 'bhero', cardId: state.handZones.a.cards[0].id, abilityBoostCardId: state.handZones.a.cards[1].id } as any,
      ctx(state, 'a'));
    expect(attack.success).toBe(true);
    const defended = await executor.executePlayDefense(
      { gameId: 's05r', cardId: 'plaindef::0' } as any, ctx(attack.gameState!, 'b'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05r' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);

    expect(resolved.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(12 - 4);
    // эффекты атакующей карты НЕ отменены → Swift Strike «Move up to 4» создаёт MOVE pending
    const moves = (resolved.gameState!.metadata.pendingEffects ?? []).filter((p) => p.type === 'MOVE');
    expect(moves).toHaveLength(1);
  });

  it('R-16: защитник сыграл Feint (CANCEL_EFFECTS) → boost сброшен без эффекта, урон = печатное(3) − защита(2) = 1; эффекты атакующей карты отменены', async () => {
    const feint = arthurCard('Feint'); // defenseValue 2 + CANCEL_EFFECTS на ON_REVEAL
    const state = combatState(feint);
    const attack = await executor.executeAttack(
      { gameId: 's05r', attackerId: 'arthur', targetId: 'bhero', cardId: state.handZones.a.cards[0].id, abilityBoostCardId: state.handZones.a.cards[1].id } as any,
      ctx(state, 'a'));
    expect(attack.success).toBe(true);
    expect(attack.gameState!.metadata.combatInfo!.boostValue).toBe(3); // boost заявлен…
    const defended = await executor.executePlayDefense(
      { gameId: 's05r', cardId: feint.id } as any, ctx(attack.gameState!, 'b'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05r' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);

    // …но отменён: 12 − (3 − 2) = 11 (boost +3 НЕ прибавлен)
    expect(resolved.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(11);
    // эффекты Swift Strike отменены → MOVE pending не создаётся
    const moves = (resolved.gameState!.metadata.pendingEffects ?? []).filter((p) => p.type === 'MOVE');
    expect(moves).toHaveLength(0);
  });
});
