/** S05: официальный тайминг optional BOOST-эффекта КАРТЫ (rulebook Battle of
 * Legends Vol.1, p.12-13): обе стороны выбирают карты → одновременный reveal →
 * IMMEDIATELY-эффекты → DURING_COMBAT-эффекты (защитник первым) → расчёт.
 * «You may BOOST this attack» (Second Shot / Noble Sacrifice) — выбор карты
 * из руки происходит в ПАУЗЕ DURING_COMBAT (persisted BOOST_CHOICE), а НЕ при
 * объявлении атаки. Способность Arthur (R-15) — исключение, коммит при
 * объявлении как напечатано. Проверяются: пауза расчёта урона, Feint-отмена,
 * порядок defender-first, потеря карты до выбора, атомарные отказы,
 * приватность до/после reveal, сериализация, ИИ-продолжение. */
import * as fs from 'fs';
import * as path from 'path';
import { GameState, PendingEffect, Card, CardType, FighterType, GamePhase, EffectType, EffectTiming } from '../models';
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
import { AiDecisionService } from './ai-decision.service';
import { GameStateService } from '../../games/game-state.service';

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
const ai = new AiDecisionService(adjacency);
const stateService = new GameStateService({} as any, {} as any);

const ctx = (state: GameState, userId: string) =>
  ({ userId, gameId: state.gameId, currentState: state }) as any;

const arthurCapture = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../../../..', 'docs/game-design/evidence/S01/content-king-arthur.json'),
    'utf8',
  ),
) as { cards: Array<Record<string, any>> };

const medusaCapture = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../../../..', 'docs/game-design/evidence/S01/content-medusa.json'),
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
const medusaCard = (name: string): Card =>
  ingest(medusaCapture.cards.find((c) => c.nameEn === name || c.name === name)!);

const filler = (id: string, boostValue = 0, defenseValue?: number): Card => ({
  id, cardId: id.replace(/::\d+$/, ''), name: id, nameEn: id, nameRu: id,
  cardType: CardType.VERSATILE, boostValue, defenseValue, effects: [],
} as Card);

/** Защитная карта с DURING_COMBAT OPPONENT_DISCARD: «сначала защитник» —
 * сброс из руки атакующего происходит ДО его BOOST-выбора. Реальный тип
 * эффекта, тот же executor-путь, что у печатных карт. */
const discardDefense = (id: string): Card => ({
  ...filler(id, 0, 2),
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

// --- board: 8×2 — Arthur ('a') слева, защитник ('b') справа
function boostState(cardsA: Card[], cardsB: Card[] = []): GameState {
  const cells = Array.from({ length: 2 }, (_, y) =>
    Array.from({ length: 8 }, (_, x) => ({ x, y, type: 'normal' })));
  const fighters = [
    { id: 'arthur', ownerId: 'a', heroId: 'a', heroSlug: 'king-arthur', name: 'King Arthur',
      type: FighterType.HERO, health: 18, maxHealth: 18, position: { x: 3, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
    { id: 'bhero', ownerId: 'b', heroId: 'b', name: 'Enemy Hero', type: FighterType.HERO,
      health: 12, maxHealth: 12, position: { x: 2, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
  ] as GameState['fighters'];
  return {
    gameId: 's05b', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER,
    turnCount: 1, currentTurnPlayerId: 'a',
    players: ['a', 'b'].map((userId) => ({ userId, heroId: userId, health: 18, maxHealth: 18, fighterIds: [], isAlive: true })),
    fighters,
    decks: { a: { cards: [], drawPile: [] }, b: { cards: [], drawPile: [] } },
    handZones: {
      a: { cards: cardsA.map((c) => ({ ...c, isVisible: true })), maxSize: 7 },
      b: { cards: cardsB.map((c) => ({ ...c, isVisible: true })), maxSize: 7 },
    },
    discardPiles: { a: [], b: [] },
    boardState: { width: 8, height: 2, cells, doors: {}, fog: {}, tokens: {} } as any,
    metadata: { lastActionAt: new Date(0), lastActionBy: 'a', version: 1, actionsRemaining: 2 },
  } as GameState;
}

const head = (state: GameState): PendingEffect => state.metadata.pendingEffects![0];

async function attackResolve(cardId: string, state: GameState) {
  const attack = await executor.executeAttack(
    { gameId: 's05b', attackerId: 'arthur', targetId: 'bhero', cardId } as any, ctx(state, 'a'));
  expect(attack.success).toBe(true);
  return attack.gameState!;
}

describe('S05 rulebook p.12-13: карточный BOOST — выбор ПОСЛЕ reveal (Noble Sacrifice)', () => {
  it('positive: DURING_COMBAT пауза создаёт optional BOOST_CHOICE владельца; урон ждёт выбора', async () => {
    const state = boostState([arthurCard('Noble Sacrifice'), filler('boost::0', 4)]);
    const afterAttack = await attackResolve(state.handZones.a.cards[0].id, state);
    // карта-буст НЕ покинула руку при объявлении
    expect(afterAttack.handZones.a.cards.map((c) => c.id)).toContain('boost::0');
    expect(afterAttack.metadata.combatInfo!.cardBoostCardId).toBeUndefined();

    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(afterAttack, 'b'));
    expect(resolved.success).toBe(true);
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('BOOST_CHOICE');
    expect(pending.playerId).toBe('a');
    expect(pending.optional).toBe(true);
    // бой на паузе ДО расчёта урона и after-combat
    expect(resolved.gameState!.phase).toBe(GamePhase.COMBAT_RESOLVE);
    expect(resolved.gameState!.metadata.combatResolutionProgress!.damage).toBeUndefined();

    const boosted = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: pending.id, cardIds: ['boost::0'] } as any, ctx(resolved.gameState!, 'a'));
    expect(boosted.success).toBe(true);
    // 12 − (2 печатное + 4 буст − 0 защита) = 6
    expect(boosted.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(6);
    expect(boosted.gameState!.discardPiles.a.map((c) => c.id)).toContain('boost::0');
    expect(boosted.gameState!.metadata.combatInfo).toBeUndefined();
  });

  it('decline: урон от печатного значения, карта-буст остаётся в руке', async () => {
    const state = boostState([arthurCard('Noble Sacrifice'), filler('boost::0', 4)]);
    const afterAttack = await attackResolve(state.handZones.a.cards[0].id, state);
    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(afterAttack, 'b'));
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('BOOST_CHOICE');

    const declined = await executor.executeDeclinePendingEffect(
      { gameId: 's05b', effectId: pending.id } as any, ctx(resolved.gameState!, 'a'));
    expect(declined.success).toBe(true);
    expect(declined.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(12 - 2);
    expect(declined.gameState!.handZones.a.cards.map((c) => c.id)).toContain('boost::0');
  });

  it('Feint защитника отменяет BOOST-эффект карты: выбора нет, НО ability-карта Arthur уже в сбросе без ценности', async () => {
    const noble = { ...arthurCard('Noble Sacrifice'), id: 'noble::0' };
    const ability = { ...arthurCard('Excalibur'), id: 'exc::0' };
    const feint = { ...arthurCard('Feint'), id: 'feint::0' };
    const state = boostState([noble, ability, filler('keep::0', 5)], [feint]);
    const attack = await executor.executeAttack(
      { gameId: 's05b', attackerId: 'arthur', targetId: 'bhero', cardId: 'noble::0',
        abilityBoostCardId: 'exc::0' } as any, ctx(state, 'a'));
    expect(attack.success).toBe(true);
    // ability-коммит при объявлении (как напечатано R-15): обе карты в сбросе
    expect(attack.gameState!.discardPiles.a.map((c) => c.id)).toContain('exc::0');

    const defended = await executor.executePlayDefense(
      { gameId: 's05b', cardId: 'feint::0' } as any, ctx(attack.gameState!, 'b'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);

    // CANCEL отменяет и BOOST-эффект карты, и значение ability-буста:
    // урон = печатное 2 − Feint 2 = 0; выбора не было
    expect((resolved.gameState!.metadata.pendingEffects ?? []).filter((p) => p.type === 'BOOST_CHOICE')).toHaveLength(0);
    expect(resolved.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(12);
    // карта-кандидат НЕ потрачена; ability-карта потрачена впустую (правило)
    expect(resolved.gameState!.handZones.a.cards.map((c) => c.id)).toContain('keep::0');
    expect(resolved.gameState!.discardPiles.a.map((c) => c.id)).toContain('exc::0');
  });

  it('Arthur ability + Noble Sacrifice — НЕЗАВИСИМЫЕ бусты (способность при объявлении, карта после reveal)', async () => {
    const noble = { ...arthurCard('Noble Sacrifice'), id: 'noble::0' };
    const ability = { ...arthurCard('Excalibur'), id: 'exc::0' };
    const boostCard = filler('boost::0', 4);
    const plainDefense = { ...filler('plaindef::0', 0, 2), cardType: CardType.DEFENSE };
    const withDef = boostState([noble, ability, boostCard], [plainDefense]);

    const attack = await executor.executeAttack(
      { gameId: 's05b', attackerId: 'arthur', targetId: 'bhero', cardId: 'noble::0',
        abilityBoostCardId: 'exc::0' } as any, ctx(withDef, 'a'));
    expect(attack.success).toBe(true);
    expect(attack.gameState!.metadata.combatInfo!.boostValue).toBe(3); // только ability (Excalibur)

    const defended = await executor.executePlayDefense(
      { gameId: 's05b', cardId: 'plaindef::0' } as any, ctx(attack.gameState!, 'b'));
    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(defended.gameState!, 'b'));
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('BOOST_CHOICE');
    expect(pending.playerId).toBe('a');

    const boosted = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: pending.id, cardIds: ['boost::0'] } as any, ctx(resolved.gameState!, 'a'));
    expect(boosted.success).toBe(true);
    const ci = boosted.gameState!.metadata; // бой завершён
    expect(ci.combatInfo).toBeUndefined();
    // 12 − (2 + 3 ability + 4 карта − 2 защита) = 5
    expect(boosted.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(5);
  });

  it('ordering: DURING-эффект ЗАЩИТНИКА резолвится раньше BOOST-выбора атакующего (defender first)', async () => {
    const noble = { ...arthurCard('Noble Sacrifice'), id: 'noble::0' };
    const victim = filler('victim::0', 6); // то, что съест сброс защитника
    const boostCard = filler('boost::0', 4);
    const state = boostState([noble, victim, boostCard], [discardDefense('dd::0')]);

    const attack = await executor.executeAttack(
      { gameId: 's05b', attackerId: 'arthur', targetId: 'bhero', cardId: 'noble::0' } as any, ctx(state, 'a'));
    const defended = await executor.executePlayDefense(
      { gameId: 's05b', cardId: 'dd::0' } as any, ctx(attack.gameState!, 'b'));
    expect(defended.success).toBe(true);

    // очередь: DISCARD_CARDS (защитник's during-эффект, владелец-цель = атакатор)
    // создан ПЕРВЫМ — выбор буста ждёт его резолва
    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);
    const first = head(resolved.gameState!);
    expect(first.type).toBe('DISCARD_CARDS');
    expect(first.playerId).toBe('a');

    const discarded = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: first.id, cardIds: ['victim::0'] } as any, ctx(resolved.gameState!, 'a'));
    expect(discarded.success).toBe(true);
    // сброс резолвнут → очередь двигается к BOOST_CHOICE
    const second = head(discarded.gameState!);
    expect(second.type).toBe('BOOST_CHOICE');
    expect(second.playerId).toBe('a');

    const boosted = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: second.id, cardIds: ['boost::0'] } as any, ctx(discarded.gameState!, 'a'));
    expect(boosted.success).toBe(true);
    // 12 − (2 + 4 − 2) = 8
    expect(boosted.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(8);
  });

  it('edge: рука опустела ДО выбора буста (сброс защитника съел последнюю карту) — pending не создаётся', async () => {
    const noble = { ...arthurCard('Noble Sacrifice'), id: 'noble::0' };
    const victim = filler('victim::0', 6);
    const state = boostState([noble, victim], [discardDefense('dd::0')]);
    const attack = await executor.executeAttack(
      { gameId: 's05b', attackerId: 'arthur', targetId: 'bhero', cardId: 'noble::0' } as any, ctx(state, 'a'));
    const defended = await executor.executePlayDefense(
      { gameId: 's05b', cardId: 'dd::0' } as any, ctx(attack.gameState!, 'b'));
    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(defended.gameState!, 'b'));
    const first = head(resolved.gameState!);
    expect(first.type).toBe('DISCARD_CARDS');

    const discarded = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: first.id, cardIds: ['victim::0'] } as any, ctx(resolved.gameState!, 'a'));
    expect(discarded.success).toBe(true);
    // рука пуста → BOOST-эффект — легальный no-op: без pending, бой ДОРАБОТАЛ
    expect(discarded.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
    // 12 − (2 − 2) = 12
    expect(discarded.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(12);
    expect(discarded.gameState!.metadata.combatInfo).toBeUndefined();
  });

  it('negative: чужой игрок / карта не из руки / не голова очереди / replay — атомарные отказы', async () => {
    const state = boostState([arthurCard('Noble Sacrifice'), filler('boost::0', 4), filler('other::0', 1)]);
    const afterAttack = await attackResolve(state.handZones.a.cards[0].id, state);
    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(afterAttack, 'b'));
    const pending = head(resolved.gameState!);

    // чужой игрок не резолвит чужой выбор
    const foreign = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: pending.id, cardIds: ['boost::0'] } as any, ctx(resolved.gameState!, 'b'));
    expect(foreign.success).toBe(false);
    expect(foreign.error).toContain('другому игроку');

    // карта не из руки / не своя — отказ, pending жив
    const notInHand = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: pending.id, cardIds: ['nonexistent::0'] } as any, ctx(resolved.gameState!, 'a'));
    expect(notInHand.success).toBe(false);
    // две карты вместо одной
    const two = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: pending.id, cardIds: ['boost::0', 'other::0'] } as any, ctx(resolved.gameState!, 'a'));
    expect(two.success).toBe(false);
    expect(head(notInHand.gameState ?? resolved.gameState!).id).toBe(pending.id);

    // replay: после резолва тот же effectId в НОВОМ состоянии протух
    const boosted = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: pending.id, cardIds: ['boost::0'] } as any, ctx(resolved.gameState!, 'a'));
    expect(boosted.success).toBe(true);
    const replay = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: pending.id, cardIds: ['other::0'] } as any, ctx(boosted.gameState!, 'a'));
    expect(replay.success).toBe(false);
    expect(replay.error).toContain('протух');
    // бой завершился корректно: 12 − (2 + 4) = 6
    expect(boosted.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(6);
  });

  it('privacy: BOOST_CHOICE не раскрывает руку; boostValue скрыт от защитника до конца боя, сброс открыт после', async () => {
    const state = boostState([arthurCard('Noble Sacrifice'), filler('boost::0', 4)]);
    const afterAttack = await attackResolve(state.handZones.a.cards[0].id, state);

    // до reveal: у защитника нет ни boost-полей, ни факта второй карты
    const defenderView = stateService.filterPrivateData(afterAttack, 'b');
    expect(defenderView.metadata.combatInfo!.boostValue ?? 0).toBe(0);
    expect(defenderView.metadata.combatInfo!.cardBoostCardId).toBeUndefined();
    expect(defenderView.handZones.a!.cards.every((c) => c.name === '???')).toBe(true);
    // в сбросе атакатора только атакующая карта — второй карты НЕ ЗАЯВЛЕНО
    expect(afterAttack.discardPiles.a).toHaveLength(1);

    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(afterAttack, 'b'));
    const pending = head(resolved.gameState!);
    // pending не содержит содержимого руки атакующего
    expect(JSON.stringify(pending)).not.toContain('boost::0');

    const boosted = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: pending.id, cardIds: ['boost::0'] } as any, ctx(resolved.gameState!, 'a'));
    expect(boosted.success).toBe(true);
    // после боя (combatInfo снят) сброс атакатора виден обоим — личина открыта
    const openView = stateService.filterPrivateData(boosted.gameState!, 'b');
    const revealed = openView.discardPiles.a.find((c) => c.id === 'boost::0');
    expect(revealed?.name).toBe('boost::0');
  });

  it('serialization: пауза BOOST_CHOICE переживает serialize/deserialize и дорешивает бой', async () => {
    const state = boostState([arthurCard('Noble Sacrifice'), filler('boost::0', 4)]);
    const afterAttack = await attackResolve(state.handZones.a.cards[0].id, state);
    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(afterAttack, 'b'));
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('BOOST_CHOICE');

    const roundtrip = stateService.deserialize(JSON.parse(JSON.stringify(stateService.serialize(resolved.gameState!))));
    const rtPending = roundtrip.metadata.pendingEffects![0];
    expect(rtPending.type).toBe('BOOST_CHOICE');
    expect(rtPending.id).toBe(pending.id);
    expect(roundtrip.metadata.combatEffectContinuation?.stage).toBe('DURING_COMBAT');
    expect(roundtrip.metadata.combatResolutionProgress?.calculation?.paused).toBe(true);

    const boosted = await executor.executeResolvePendingEffect(
      { gameId: 's05b', effectId: rtPending.id, cardIds: ['boost::0'] } as any, ctx(roundtrip, 'a'));
    expect(boosted.success).toBe(true);
    expect(boosted.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(6);
    expect(boosted.gameState!.metadata.combatInfo).toBeUndefined();
  });

  it('AI: бустит МИНИмальной достаточной картой; ненужный буст отклоняет; пустая рука — decline', async () => {
    const noble = { ...arthurCard('Noble Sacrifice'), id: 'noble::0' };
    // 2 (атака) vs 5 (защита): нужен буст ≥ 4 → выберет ровно 4, не 6
    const strong = filler('strong::0', 6);
    const exact = filler('exact::0', 4);
    const weak = filler('weak::0', 1);
    const state = boostState([noble, strong, exact, weak], [{ ...filler('bigdef::0', 0, 5), cardType: CardType.DEFENSE }]);

    const attack = await executor.executeAttack(
      { gameId: 's05b', attackerId: 'arthur', targetId: 'bhero', cardId: 'noble::0' } as any, ctx(state, 'a'));
    const defended = await executor.executePlayDefense(
      { gameId: 's05b', cardId: 'bigdef::0' } as any, ctx(attack.gameState!, 'b'));
    const resolved = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(defended.gameState!, 'b'));
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('BOOST_CHOICE');

    const decision = ai.decide(resolved.gameState!, 'a');
    expect(decision).toEqual({ kind: 'resolveBoost', effectId: pending.id, cardIds: ['exact::0'] });

    // исход уже благоприятен (2 > 0 без защиты) → decidePending = null,
    // optional → decide() возвращает declinePending (карту не тратим)
    const wonState = boostState([arthurCard('Noble Sacrifice'), strong]);
    const afterAttack2 = await attackResolve(wonState.handZones.a.cards[0].id, wonState);
    const resolved2 = await executor.executeResolveCombat({ gameId: 's05b' } as any, ctx(afterAttack2, 'b'));
    const pending2 = head(resolved2.gameState!);
    expect(ai.decide(resolved2.gameState!, 'a')).toEqual({ kind: 'declinePending', effectId: pending2.id });
    // optional → decide() сам возвращает declinePending
    const declined = await executor.executeDeclinePendingEffect(
      { gameId: 's05b', effectId: pending2.id } as any, ctx(resolved2.gameState!, 'a'));
    expect(declined.success).toBe(true);
    expect(declined.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(12 - 2);
  });
});

describe('S05: Second Shot (Medusa) — тот же тайминг через реальную колоду Medusa', () => {
  it('BOOST_CHOICE после reveal у Medusa (не Arthur) — без ability-слота', async () => {
    const cells = Array.from({ length: 2 }, (_, y) =>
      Array.from({ length: 8 }, (_, x) => ({ x, y, type: 'normal' })));
    const fighters = [
      { id: 'medusa', ownerId: 'm', heroId: 'm', heroSlug: 'medusa', name: 'Medusa', type: FighterType.HERO,
        health: 16, maxHealth: 16, position: { x: 2, y: 0 }, effects: [], hasSidekick: true, movement: 3 },
      { id: 'bhero', ownerId: 'b', heroId: 'b', name: 'Enemy Hero', type: FighterType.HERO,
        health: 12, maxHealth: 12, position: { x: 3, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
    ] as GameState['fighters'];
    const shot = { ...medusaCard('Second Shot'), id: 'shot::0' };
    const state: GameState = {
      gameId: 's05sm', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER,
      turnCount: 1, currentTurnPlayerId: 'm',
      players: ['m', 'b'].map((userId) => ({ userId, heroId: userId, health: 16, maxHealth: 16, fighterIds: [], isAlive: true })),
      fighters,
      decks: { m: { cards: [], drawPile: [] }, b: { cards: [], drawPile: [] } },
      handZones: { m: { cards: [{ ...shot, isVisible: true }, { ...filler('mb::0', 2), isVisible: true }], maxSize: 7 },
        b: { cards: [], maxSize: 7 } },
      discardPiles: { m: [], b: [] },
      boardState: { width: 8, height: 2, cells, doors: {}, fog: {}, tokens: {} } as any,
      metadata: { lastActionAt: new Date(0), lastActionBy: 'm', version: 1, actionsRemaining: 2 },
    } as GameState;

    const attack = await executor.executeAttack(
      { gameId: 's05sm', attackerId: 'medusa', targetId: 'bhero', cardId: 'shot::0' } as any, ctx(state, 'm'));
    expect(attack.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05sm' } as any, ctx(attack.gameState!, 'b'));
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('BOOST_CHOICE');
    expect(pending.playerId).toBe('m');
    const boosted = await executor.executeResolvePendingEffect(
      { gameId: 's05sm', effectId: pending.id, cardIds: ['mb::0'] } as any, ctx(resolved.gameState!, 'm'));
    // 12 − (3 + 2) = 7
    expect(boosted.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(7);
  });
});
