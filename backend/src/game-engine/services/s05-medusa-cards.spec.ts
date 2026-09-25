/** GD-020: all 11 Medusa deck-card records driven through the REAL executor
 * (production ingest: capture → normalizeCardEffects/SCHEME fullText → hand →
 * playScheme / attack+defense+resolveCombat → pending resolution). Positive,
 * negative and edge cases per literal printed text (S01 rules-oracle R-14,
 * Medusa card exceptions). */
import * as fs from 'fs';
import * as path from 'path';
import { GameState, PendingEffect } from '../models';
import { Card, CardType, FighterType, GamePhase } from '../models';
import { normalizeCardEffects } from '../models';
import { parseCardEffectTexts } from '../effects/effect-text-parser';
import { s03Engine } from '../../test/fixtures/s03-engine.fixture';

const { executor } = s03Engine();
const ctx = (state: GameState, userId = 'm') =>
  ({ userId, gameId: state.gameId, currentState: state }) as any;

const capture = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../../../..', 'docs/game-design/evidence/S01/content-medusa.json'),
    'utf8',
  ),
) as { cards: Array<Record<string, any>> };

/** Production ingest (mirrors GameInitializationService.resolveCardEffects). */
function ingest(card: Record<string, any>): Card {
  const effects = normalizeCardEffects(card.effects, card.id);
  const resolved =
    effects.length > 0
      ? effects
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

const medusaCard = (name: string): Card =>
  ingest(capture.cards.find((c) => c.name === name)!);

// --- Medusa board: 8×2, x 0..3 = zone 'west' (Medusa's zone), x 4..7 = 'east'
// У 'b' РОВНО ОДИН HERO (terminal-state смотрит первого HERO владельца).
function medusaState(opts?: { deadHarpy?: string; enemyFar?: boolean; bheroAt?: { x: number; y: number } }): GameState {
  const cells = Array.from({ length: 2 }, (_, y) =>
    Array.from({ length: 8 }, (_, x) => ({ x, y, type: 'normal', zones: x <= 3 ? ['west'] : ['east'] })));
  const fighters = [
    { id: 'medusa', ownerId: 'm', heroId: 'm', heroSlug: 'medusa', name: 'Medusa', type: FighterType.HERO,
      health: 16, maxHealth: 16, position: { x: 2, y: 0 }, effects: [], hasSidekick: true, movement: 3 },
    { id: 'harpy1', ownerId: 'm', heroId: 'm', heroSlug: 'medusa', name: 'Harpies 1', type: FighterType.MINION,
      health: 1, maxHealth: 1, position: { x: 1, y: 0 }, effects: [], hasSidekick: false, movement: 3 },
    { id: 'harpy2', ownerId: 'm', heroId: 'm', heroSlug: 'medusa', name: 'Harpies 2', type: FighterType.MINION,
      health: 1, maxHealth: 1, position: { x: 2, y: 1 }, effects: [], hasSidekick: false, movement: 3 },
    { id: 'harpy3', ownerId: 'm', heroId: 'm', heroSlug: 'medusa', name: 'Harpies 3', type: FighterType.MINION,
      health: 1, maxHealth: 1, position: { x: 0, y: 0 }, effects: [], hasSidekick: false, movement: 3 },
    { id: 'bhero', ownerId: 'b', heroId: 'b', name: 'Enemy Hero', type: FighterType.HERO,
      health: 12, maxHealth: 12, position: { x: 3, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
    { id: 'bfar', ownerId: 'b', heroId: 'b', name: 'Enemy Far', type: FighterType.MINION,
      health: 10, maxHealth: 10, position: { x: opts?.enemyFar ? 7 : 6, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
  ].map((f) =>
    f.id === opts?.deadHarpy ? { ...f, health: 0, isDefeated: true } : f,
  ).map((f) =>
    f.id === 'bhero' && opts?.bheroAt ? { ...f, position: opts.bheroAt } : f,
  ) as GameState['fighters'];
  return {
    gameId: 's05m', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER,
    turnCount: 1, currentTurnPlayerId: 'm',
    players: ['m', 'b'].map((userId) => ({ userId, heroId: userId, health: 16, maxHealth: 16, fighterIds: [], isAlive: true })),
    fighters,
    decks: {
      m: { cards: [], drawPile: [] },
      b: { cards: [], drawPile: [] },
    },
    handZones: { m: { cards: [], maxSize: 7 }, b: { cards: [], maxSize: 7 } },
    discardPiles: { m: [], b: [] },
    boardState: { width: 8, height: 2, cells, doors: {}, fog: {}, tokens: {} } as any,
    metadata: { lastActionAt: new Date(0), lastActionBy: 'm', version: 1, actionsRemaining: 2 },
  } as GameState;
}

const inHand = (state: GameState, card: Card): GameState => ({
  ...state,
  handZones: { ...state.handZones, m: { cards: [{ ...card, isVisible: true }], maxSize: 7 } },
});

/** Несколько карт в руку 'm' (для выбора сброса нужен выбор из ≥1 карты). */
const mHand = (state: GameState, cards: Card[]): GameState => ({
  ...state,
  handZones: { ...state.handZones, m: { cards: cards.map((c) => ({ ...c, isVisible: true })), maxSize: 7 } },
});

/** Карты в руку защитника 'b'. */
const bHand = (state: GameState, cards: Card[]): GameState => ({
  ...state,
  handZones: { ...state.handZones, b: { cards: cards.map((c) => ({ ...c, isVisible: true })), maxSize: 7 } },
});

/** Seed drawPile игрока 'm' (пустая колода = exhaustion damage, добор не пройдёт). */
const withDraw = (state: GameState, pile: Card[]): GameState => ({
  ...state,
  decks: { ...state.decks, m: { cards: [], drawPile: pile } },
});

const filler = (id: string, boostValue = 0): Card => ({
  id, cardId: id.replace(/::\d+$/, ''), name: id, nameEn: id, nameRu: id,
  cardType: CardType.SCHEME, boostValue, effects: [],
} as Card);

const head = (state: GameState): PendingEffect => state.metadata.pendingEffects![0];

describe('GD-020: A Momentary Glance (SCHEME x2)', () => {
  const glanceId = (): string => medusaCard('A Momentary Glance').id;
  it('positive: TARGET_FIGHTER pending lists every living fighter in Medusa\'s zone (incl. own + Medusa)', async () => {
    const state = inHand(medusaState(), medusaCard('A Momentary Glance'));
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: glanceId() } as any, ctx(state));
    expect(played.success).toBe(true);
    const pending = head(played.gameState!);
    expect(pending.type).toBe('TARGET_FIGHTER');
    expect(pending.damage).toBe(2);
    // R-таблица: «any one fighter in Medusa's zone» включает СВОИХ бойцов и саму Medusa
    expect([...pending.targetFighterIds!].sort()).toEqual(['bhero', 'harpy1', 'harpy2', 'harpy3', 'medusa']);
    // enemyFar (east-зона) НЕ легальная цель
    expect(pending.targetFighterIds).not.toContain('bfar');
  });

  it('positive: resolve enemy target → 2 damage; queue drains, deferred turn transfer completes', async () => {
    const state = inHand(medusaState(), medusaCard('A Momentary Glance'));
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: glanceId() } as any, ctx(state));
    const resolved = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: head(played.gameState!).id, fighterId: 'bhero' }, ctx(played.gameState!));
    expect(resolved.success).toBe(true);
    expect(resolved.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(10);
    expect(resolved.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
    // Scheme потратил ПЕРВОЕ из 2 действий → ход остаётся у 'm' с 1 действием
    expect(resolved.gameState!.currentTurnPlayerId).toBe('m');
    expect(resolved.gameState!.metadata.actionsRemaining).toBe(1);
  });

  it('negative: target outside the pending list is rejected; mandatory choice cannot be declined', async () => {
    const state = inHand(medusaState(), medusaCard('A Momentary Glance'));
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: glanceId() } as any, ctx(state));
    const foreign = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: head(played.gameState!).id, fighterId: 'bfar' }, ctx(played.gameState!));
    expect(foreign.success).toBe(false);
    expect(foreign.error).toContain('допустимые цели');
    const declined = await executor.executeDeclinePendingEffect(
      { gameId: 's05m', effectId: head(played.gameState!).id }, ctx(played.gameState!));
    expect(declined.success).toBe(false); // mandatory — decline запрещён
  });

  it('edge: revalidation — target that died before the choice is rejected', async () => {
    const state = inHand(medusaState(), medusaCard('A Momentary Glance'));
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: glanceId() } as any, ctx(state));
    const pending = head(played.gameState!);
    // ручная порча: цель была в списке, но пала к моменту выбора.
    // (harpy1 — MINION: её гибель не завершает игру, очередь продолжает ждать.)
    const poisoned: GameState = {
      ...played.gameState!,
      fighters: played.gameState!.fighters.map((f) => (f.id === 'harpy1' ? { ...f, health: 0, isDefeated: true } : f)),
    };
    const resolved = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, fighterId: 'harpy1' }, ctx(poisoned));
    expect(resolved.success).toBe(false);
    expect(resolved.error).toContain('повержена');
  });

  it('edge: enemy leaves the zone — still own fighters are legal targets («any one fighter»)', async () => {
    const state = inHand(medusaState({ enemyFar: true }), medusaCard('A Momentary Glance'));
    const emptied: GameState = {
      ...state,
      fighters: state.fighters.map((f) =>
        f.id === 'bhero' ? { ...f, position: { x: 6, y: 0 } } : f),
    };
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: glanceId() } as any, ctx(emptied));
    expect(played.success).toBe(true);
    const ids = head(played.gameState!).targetFighterIds!;
    expect(ids).toContain('medusa'); // свои остаются легальными (oracle)
    expect(ids).not.toContain('bhero');
    expect(ids).not.toContain('bfar');
  });
});

describe('GD-020: Winged Frenzy (SCHEME x2)', () => {
  it('positive: sequential MOVE per living own fighter, then optional revive-PLACE of the defeated Harpy', async () => {
    const state = inHand(medusaState({ deadHarpy: 'harpy2' }), medusaCard('Winged Frenzy'));
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: medusaCard('Winged Frenzy').id } as any, ctx(state));
    expect(played.success).toBe(true);
    const queue = played.gameState!.metadata.pendingEffects!;
    // 3 живых своих бойца (Medusa, harpy1, harpy3) — по одному MOVE, затем revive
    expect(queue.map((p) => p.type)).toEqual(['MOVE', 'MOVE', 'MOVE', 'PLACE']);
    expect(queue.map((p) => p.fighterIds![0])).toEqual(['medusa', 'harpy1', 'harpy3', 'harpy2']);
    expect(queue[0].canPassThroughEnemies).toBe(true);
    expect(queue[0].value).toBe(3);
    const revive = queue[3];
    expect(revive.optional).toBe(true);
    expect(revive.zoneFighterName).toBe('Medusa');
    expect(revive.restoreFullHealth).toBe(true);
  });

  it('positive: MOVE passes THROUGH an opposing fighter to a legal free endpoint', async () => {
    const state = inHand(medusaState({ deadHarpy: 'harpy2' }), medusaCard('Winged Frenzy'));
    // bhero на (3,0) блокирует прямой коридор; harpy1 (1,0) идёт за ним: (4,0)
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: medusaCard('Winged Frenzy').id } as any, ctx(state));
    let cur = played.gameState!;
    // нулевые шаги для Medusa и harpy1 ещё не делаем — двигаем harpy1 СКВОЗЬ врага
    const moveMedusa = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: head(cur).id, fighterId: 'medusa', x: 2, y: 0 }, ctx(cur));
    expect(moveMedusa.success).toBe(true);
    cur = moveMedusa.gameState!;
    const through = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: head(cur).id, fighterId: 'harpy1', x: 4, y: 0 }, ctx(cur));
    expect(through.success).toBe(true); // путь через (3,0) с врагом — легален
    expect(through.gameState!.fighters.find((f) => f.id === 'harpy1')!.position).toEqual({ x: 4, y: 0 });
  });

  it('negative: endpoint occupied by a living fighter is still illegal (pass-through ≠ landing)', async () => {
    const state = inHand(medusaState({ deadHarpy: 'harpy2' }), medusaCard('Winged Frenzy'));
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: medusaCard('Winged Frenzy').id } as any, ctx(state));
    let cur = played.gameState!;
    const moveMedusa = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: head(cur).id, fighterId: 'medusa', x: 2, y: 0 }, ctx(cur));
    cur = moveMedusa.gameState!;
    const ontoEnemy = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: head(cur).id, fighterId: 'harpy1', x: 3, y: 0 }, ctx(cur));
    expect(ontoEnemy.success).toBe(false);
    expect(ontoEnemy.error).toContain('занята');
  });

  it('positive: revive returns the SAME defeated Harpy at full health inside Medusa\'s zone only', async () => {
    const state = inHand(medusaState({ deadHarpy: 'harpy2' }), medusaCard('Winged Frenzy'));
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: medusaCard('Winged Frenzy').id } as any, ctx(state));
    let cur = played.gameState!;
    for (const fid of ['medusa', 'harpy1', 'harpy3']) {
      const p = head(cur);
      const step = await executor.executeResolvePendingEffect(
        { gameId: 's05m', effectId: p.id, fighterId: fid, x: cur.fighters.find((f) => f.id === fid)!.position.x,
          y: cur.fighters.find((f) => f.id === fid)!.position.y }, ctx(cur));
      expect(step.success).toBe(true);
      cur = step.gameState!;
    }
    expect(head(cur).type).toBe('PLACE');
    const outsideZone = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: head(cur).id, fighterId: 'harpy2', x: 6, y: 0 }, ctx(cur));
    expect(outsideZone.success).toBe(false); // east — не зона Medusa
    const revive = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: head(cur).id, fighterId: 'harpy2', x: 0, y: 1 }, ctx(cur));
    expect(revive.success).toBe(true);
    const revived = revive.gameState!.fighters.find((f) => f.id === 'harpy2')!;
    expect(revived.health).toBe(1); // maxHealth восстановлен
    expect(revived.isDefeated).toBe(false);
    expect(revived.name).toBe('Harpies 2'); // identity сохранён
    expect(revive.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('edge: no defeated Harpy («if any») → revive pending is not created', async () => {
    const state = inHand(medusaState(), medusaCard('Winged Frenzy'));
    const played = await executor.executePlayScheme({ gameId: 's05m', cardId: medusaCard('Winged Frenzy').id } as any, ctx(state));
    const queue = played.gameState!.metadata.pendingEffects!;
    expect(queue.map((p) => p.type)).toEqual(['MOVE', 'MOVE', 'MOVE', 'MOVE']); // 4 живых своих, revive нет
  });
});

describe('GD-020: The Hounds of Mighty Zeus (VERSATILE x2)', () => {
  const hounds = (): Card => ({ ...medusaCard('The Hounds of Mighty Zeus'), id: 'hounds::0' });
  it('positive: after combat, one sequential MOVE per LIVING Harpy (not Medusa)', async () => {
    // bhero придвигаем к harpy1 для melee-смежности (1,1)-(1,0)
    const state = inHand(medusaState({ deadHarpy: 'harpy3', bheroAt: { x: 1, y: 1 } }), hounds());
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'harpy1', targetId: 'bhero', cardId: 'hounds::0' } as any, ctx(state));
    expect(attack.success).toBe(true);
    // у защитника пустая рука — защита невозможна; резолвим бой напрямую
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(attack.gameState!, 'm'));
    expect(resolved.success).toBe(true);
    const after = resolved.gameState!;
    const moves = (after.metadata.pendingEffects ?? []).filter((p) => p.type === 'MOVE');
    // живые Harpies: harpy1, harpy2 (harpy3 повержена) — каждая по своему pending
    expect(moves.map((p) => p.fighterIds![0]).sort()).toEqual(['harpy1', 'harpy2']);
  });

  it('negative: single living Harpy attacks → exactly one MOVE pending (dead Harpies excluded)', async () => {
    const state = inHand(
      medusaState({ deadHarpy: 'harpy2', bheroAt: { x: 1, y: 1 } }),
      hounds(),
    );
    // harpy3 убираем: остаётся единственная живая harpy1 (атакующий)
    const fewer: GameState = { ...state,
      fighters: state.fighters.map((f) => (f.id === 'harpy3' ? { ...f, health: 0, isDefeated: true } : f)) };
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'harpy1', targetId: 'bhero', cardId: 'hounds::0' } as any, ctx(fewer));
    expect(attack.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(attack.gameState!, 'm'));
    const moves = (resolved.gameState!.metadata.pendingEffects ?? []).filter((p) => p.type === 'MOVE');
    expect(moves.map((p) => p.fighterIds![0])).toEqual(['harpy1']);
  });
});

describe('GD-020: Gaze of Stone / Second Shot / Feint (combat cards)', () => {
  it('Gaze of Stone positive: WON combat → 8 damage to the opposing fighter', async () => {
    const state = inHand(medusaState(), { ...medusaCard('Gaze of Stone'), id: 'gaze::0' });
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'gaze::0' } as any, ctx(state));
    expect(attack.success).toBe(true);
    // защита не сыграна (пустая рука b) → резолв: attack 2 vs defense 0 → победа
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(attack.gameState!, 'm'));
    expect(resolved.success).toBe(true);
    const bhero = resolved.gameState!.fighters.find((f) => f.id === 'bhero')!;
    // 12 - (2-0 боевой урон) - 8 (Gaze) = 2
    expect(bhero.health).toBe(2);
  });

  it('Gaze of Stone negative: LOST combat → no extra damage', async () => {
    const state = inHand(medusaState(), { ...medusaCard('Gaze of Stone'), id: 'gaze::0' });
    // даём защитнику сильную карту в руку (defense 5 > attack 2)
    const defCard: Card = { id: 'bigdef::0', cardId: 'bigdef', name: 'Big Defense', nameEn: 'Big Defense',
      nameRu: 'Big Defense', cardType: CardType.DEFENSE, defenseValue: 5, effects: [] } as Card;
    const withDef: GameState = {
      ...state,
      handZones: { ...state.handZones,
        m: state.handZones.m,
        b: { cards: [{ ...defCard, isVisible: true }], maxSize: 7 } },
    };
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'gaze::0' } as any, ctx(withDef));
    const defended = await executor.executePlayDefense(
      { gameId: 's05m', cardId: 'bigdef::0' } as any, ctx(attack.gameState!, 'b'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);
    const bhero = resolved.gameState!.fighters.find((f) => f.id === 'bhero')!;
    expect(bhero.health).toBe(12); // 8 не нанесены (бой проигран)
  });

  it('Second Shot positive: BOOST-карта НЕ коммитится при атаке; выбор после reveal добавляет значение', async () => {
    const boostCard: Card = { id: 'boost::0', cardId: 'boost', name: 'Boost', nameEn: 'Boost', nameRu: 'Boost',
      cardType: CardType.VERSATILE, boostValue: 4, effects: [] } as Card;
    const hand: GameState = mHand(medusaState(), [
      { ...medusaCard('Second Shot'), id: 'shot::0' }, boostCard,
    ]);
    // при объявлении атаки НЕТ boostCardId — карта-буст остаётся в руке
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'shot::0' } as any, ctx(hand));
    expect(attack.success).toBe(true);
    const afterAttack = attack.gameState!;
    // до reveal: boost-карта всё ещё В РУКЕ, в combatInfo нет её следов
    expect(afterAttack.handZones.m.cards.map((c) => c.id)).toContain('boost::0');
    expect(afterAttack.metadata.combatInfo!.cardBoostCardId).toBeUndefined();
    expect(afterAttack.metadata.combatInfo!.boostValue ?? 0).toBe(0);

    // резолв: reveal прошёл → DURING_COMBAT создаёт BOOST_CHOICE и ПАУЗИТ бой
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(afterAttack));
    expect(resolved.success).toBe(true);
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('BOOST_CHOICE');
    expect(pending.playerId).toBe('m');
    expect(pending.optional).toBe(true);
    // урон ещё НЕ посчитан — бой на паузе до выбора
    expect(resolved.gameState!.metadata.combatResolutionProgress!.damage).toBeUndefined();

    const boosted = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, cardIds: ['boost::0'] } as any, ctx(resolved.gameState!));
    expect(boosted.success).toBe(true);
    const final = boosted.gameState!;
    // карта ушла в сброс, значение учтено: 12 − (3 + 4 − 0) = 5
    expect(final.discardPiles.m.map((c) => c.id)).toContain('boost::0');
    expect(final.fighters.find((f) => f.id === 'bhero')!.health).toBe(5);
    expect(final.metadata.combatInfo).toBeUndefined();
    expect(final.metadata.combatResolutionProgress).toBeUndefined();
  });

  it('Second Shot decline: отказа достаточно — урон от печатного значения', async () => {
    const hand = mHand(medusaState(), [
      { ...medusaCard('Second Shot'), id: 'shot::0' }, filler('keep::0', 5),
    ]);
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'shot::0' } as any, ctx(hand));
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(attack.gameState!));
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('BOOST_CHOICE');
    const declined = await executor.executeDeclinePendingEffect(
      { gameId: 's05m', effectId: pending.id } as any, ctx(resolved.gameState!));
    expect(declined.success).toBe(true);
    // 12 − (3 − 0) = 9; карта осталась в руке
    expect(declined.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(9);
    expect(declined.gameState!.handZones.m.cards.map((c) => c.id)).toContain('keep::0');
  });

  it('Second Shot + Feint (defender): CANCEL на reveal — выбора НЕТ, урон от печатного значения', async () => {
    const hand = mHand(medusaState(), [
      { ...medusaCard('Second Shot'), id: 'shot::0' }, filler('keep::0', 5),
    ]);
    const withDef = bHand(hand, [{ ...medusaCard('Feint'), id: 'feint::0' }]);
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'shot::0' } as any, ctx(withDef));
    const defended = await executor.executePlayDefense(
      { gameId: 's05m', cardId: 'feint::0' } as any, ctx(attack.gameState!, 'b'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);
    // BOOST-эффект отменён вместе с картой: pending не создан, карта в руке
    const boostPendings = (resolved.gameState!.metadata.pendingEffects ?? []).filter((p) => p.type === 'BOOST_CHOICE');
    expect(boostPendings).toHaveLength(0);
    // 12 − (3 − 2) = 11
    expect(resolved.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(11);
    expect(resolved.gameState!.handZones.m.cards.map((c) => c.id)).toContain('keep::0');
  });

  it('Feint (Medusa) + Snipe: defender reveal CANCELS attacker card effects — no draw', async () => {
    // Snipe: attack 3, after combat «Draw 1 card.» Feint (def 2): ON_REVEAL
    // «Cancel all effects on your opponent's card.» → Snipe-эффекты отменены,
    // печатное значение атаки сохранено (R-16), добора НЕТ.
    const d1 = filler('draw1::0');
    const snipe = { ...medusaCard('Snipe'), id: 'snipe::0' };
    const state = bHand(withDraw(inHand(medusaState(), snipe), [d1]), [{ ...medusaCard('Feint'), id: 'feint::0' }]);
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'snipe::0' } as any, ctx(state));
    expect(attack.success).toBe(true);
    const defended = await executor.executePlayDefense(
      { gameId: 's05m', cardId: 'feint::0' } as any, ctx(attack.gameState!, 'b'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);
    const after = resolved.gameState!;
    // 3 (печатное) - 2 = 1 урон: отмена эффектов НЕ отменяет значение карты
    expect(after.fighters.find((f) => f.id === 'bhero')!.health).toBe(11);
    // DRAW_CARD отменён: карта не добрана, осталась в колоде
    expect(after.handZones.m.cards.map((c) => c.id)).not.toContain('draw1::0');
    expect(after.decks.m.drawPile.map((c) => c.id)).toContain('draw1::0');
  });
});

describe('GD-020: Dash / Regroup / Snipe — real combat execution', () => {
  it('Dash: attacker win → optional MOVE 3 pending; resolve moves, decline stays', async () => {
    const state = inHand(medusaState(), { ...medusaCard('Dash'), id: 'dash::0' });
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'dash::0' } as any, ctx(state));
    expect(attack.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(attack.gameState!, 'm'));
    expect(resolved.success).toBe(true);
    const pending = head(resolved.gameState!);
    // «Move your fighter up to 3 spaces.» — optional («You may»-семантика текста Dash)
    expect(pending.type).toBe('MOVE');
    expect(pending.value).toBe(3);
    expect(pending.optional).toBe(true);
    expect(pending.playerId).toBe('m');

    const moved = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, fighterId: 'medusa', x: 1, y: 1 }, ctx(resolved.gameState!));
    expect(moved.success).toBe(true);
    expect(moved.gameState!.fighters.find((f) => f.id === 'medusa')!.position).toEqual({ x: 1, y: 1 });
    expect(moved.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
    // бой завершён, ход продолжается у атакатора (2-е действие)
    expect(moved.gameState!.metadata.combatInfo).toBeUndefined();
    expect(moved.gameState!.currentTurnPlayerId).toBe('m');
    expect(moved.gameState!.metadata.actionsRemaining).toBe(1);
  });

  it('Dash: decline (optional) — боец остаётся на месте', async () => {
    const state = inHand(medusaState(), { ...medusaCard('Dash'), id: 'dash::0' });
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'dash::0' } as any, ctx(state));
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(attack.gameState!, 'm'));
    const declined = await executor.executeDeclinePendingEffect(
      { gameId: 's05m', effectId: head(resolved.gameState!).id }, ctx(resolved.gameState!));
    expect(declined.success).toBe(true);
    expect(declined.gameState!.fighters.find((f) => f.id === 'medusa')!.position).toEqual({ x: 2, y: 0 });
    expect(declined.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('Regroup: WON → draw 2', async () => {
    const d1 = filler('r1::0');
    const d2 = filler('r2::0');
    const state = withDraw(inHand(medusaState(), { ...medusaCard('Regroup'), id: 'regroup::0' }), [d1, d2]);
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'regroup::0' } as any, ctx(state));
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(attack.gameState!, 'm'));
    expect(resolved.success).toBe(true);
    // attack 1 vs defense 0 → 1 damage → WON; «If you won the combat, draw 2»
    expect(resolved.gameState!.fighters.find((f) => f.id === 'bhero')!.health).toBe(11);
    expect(resolved.gameState!.handZones.m.cards.map((c) => c.id).sort()).toEqual(['r1::0', 'r2::0']);
  });

  it('Regroup: LOST → draw 1', async () => {
    const d1 = filler('r1::0');
    const d2 = filler('r2::0');
    const defCard: Card = { id: 'bigdef::0', cardId: 'bigdef', name: 'Big Defense', nameEn: 'Big Defense',
      nameRu: 'Big Defense', cardType: CardType.DEFENSE, defenseValue: 5, effects: [] } as Card;
    const state = bHand(
      withDraw(inHand(medusaState(), { ...medusaCard('Regroup'), id: 'regroup::0' }), [d1, d2]), [defCard]);
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'regroup::0' } as any, ctx(state));
    const defended = await executor.executePlayDefense(
      { gameId: 's05m', cardId: 'bigdef::0' } as any, ctx(attack.gameState!, 'b'));
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);
    // attack 1 vs defense 5 → LOST; «Draw 1 card.»
    expect(resolved.gameState!.handZones.m.cards.map((c) => c.id)).toEqual(['r1::0']);
    expect(resolved.gameState!.decks.m.drawPile.map((c) => c.id)).toEqual(['r2::0']);
  });

  it('Snipe: after combat attacker draws exactly 1', async () => {
    const d1 = filler('draw1::0');
    const state = withDraw(inHand(medusaState(), { ...medusaCard('Snipe'), id: 'snipe::0' }), [d1]);
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'medusa', targetId: 'bhero', cardId: 'snipe::0' } as any, ctx(state));
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(attack.gameState!, 'm'));
    expect(resolved.success).toBe(true);
    expect(resolved.gameState!.handZones.m.cards.map((c) => c.id)).toEqual(['draw1::0']);
    expect(resolved.gameState!.decks.m.drawPile).toHaveLength(0);
  });
});

describe('GD-020: Hiss and Slither / Clutching Claws — opponent-CHOICE discard (P1)', () => {
  /** Печатный текст «Your opponent discards 1 card.» — БЕЗ «random»:
   *  сбрасывающий выбирает карту сам. Pending принадлежит ОППОНЕНТУ
   *  игрока карты; боевая цепочка паузится до его выбора.
   *  Hiss — banner «Medusa»: защититься может только Медуза, поэтому
   *  сценарий: ход 'b', bhero атакует Medusa слабой картой, Medusa играет
   *  Hiss (def 4) → АТАКАТОР 'b' (оппонент игрока Hiss) сбрасывает по выбору. */
  const hissFight = async (attackerExtra: Card[]) => {
    const weakAttack: Card = { id: 'weak::0', cardId: 'weak', name: 'Weak Attack', nameEn: 'Weak Attack',
      nameRu: 'Weak Attack', cardType: CardType.ATTACK, attackValue: 2, effects: [] } as Card;
    const state: GameState = {
      ...bHand(mHand(medusaState(), [{ ...medusaCard('Hiss and Slither'), id: 'hiss::0' }]),
        [weakAttack, ...attackerExtra]),
      currentTurnPlayerId: 'b',
    };
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'bhero', targetId: 'medusa', cardId: 'weak::0' } as any, ctx(state, 'b'));
    expect(attack.success).toBe(true);
    const defended = await executor.executePlayDefense(
      { gameId: 's05m', cardId: 'hiss::0' } as any, ctx(attack.gameState!, 'm'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(defended.gameState!, 'm'));
    expect(resolved.success).toBe(true);
    return resolved.gameState!;
  };

  it('positive: pending DISCARD_CARDS принадлежит АТАКАТОРУ (оппоненту игрока Hiss); точный выбор → карта в сброс, бой и ход продолжаются', async () => {
    const after = await hissFight([filler('keep::0', 3), filler('junk::0', 1)]);
    // у 'b' после weak::0 остались keep/junk; победа защитника (2 < 4) не гейтит
    // эффект — текст Hiss без won/lost условия
    const pending = head(after);
    expect(pending.type).toBe('DISCARD_CARDS');
    expect(pending.playerId).toBe('b'); // владелец выбора = атакатор
    expect(pending.value).toBe(1);
    // боевая цепочка на паузе: резолв отложен до выбора
    expect(after.metadata.combatResolutionProgress).toBeTruthy();
    // privacy: pending не содержит содержимого ничьей руки
    const wire = JSON.stringify(pending);
    expect(wire).not.toContain('keep::0');
    expect(wire).not.toContain('junk::0');

    const chosen = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, cardIds: ['junk::0'] }, ctx(after, 'b'));
    expect(chosen.success).toBe(true);
    const done = chosen.gameState!;
    // ровно ВЫБРАННАЯ карта ушла в сброс, вторая осталась в руке
    expect(done.handZones.b.cards.map((c) => c.id)).toEqual(['keep::0']);
    expect(done.discardPiles.b.map((c) => c.id)).toContain('junk::0');
    // очередь пуста, бой завершён, ход продолжается у атакатора
    expect(done.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(done.metadata.combatInfo).toBeUndefined();
    expect(done.currentTurnPlayerId).toBe('b');
    expect(done.metadata.actionsRemaining).toBe(1);
  });

  it('negative: чужой игрок, неверное число/чужие карты, decline — отклоняются атомарно', async () => {
    const after = await hissFight([filler('keep::0', 3), filler('junk::0', 1)]);
    const pending = head(after);
    // выбор принадлежит другому игроку
    const foreign = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, cardIds: ['junk::0'] }, ctx(after, 'm'));
    expect(foreign.success).toBe(false);
    expect(foreign.error).toContain('другому игроку');
    // 0 карт — не ровно 1
    const zero = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, cardIds: [] }, ctx(after, 'b'));
    expect(zero.success).toBe(false);
    // карты нет в руке
    const outside = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, cardIds: ['nope::0'] }, ctx(after, 'b'));
    expect(outside.success).toBe(false);
    // mandatory — decline запрещён
    const declined = await executor.executeDeclinePendingEffect(
      { gameId: 's05m', effectId: pending.id }, ctx(after, 'b'));
    expect(declined.success).toBe(false);
    // ничего не изменилось
    expect(after.handZones.b.cards.map((c) => c.id).sort()).toEqual(['junk::0', 'keep::0']);
    expect((after.metadata.pendingEffects ?? []).length).toBe(1);
  });

  it('edge: пустая рука атакатора — no-op без pending, бой завершается сразу', async () => {
    const after = await hissFight([]);
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.metadata.combatResolutionProgress).toBeFalsy();
    expect(after.metadata.combatInfo).toBeUndefined();
    expect(after.handZones.b.cards).toHaveLength(0);
    expect(after.currentTurnPlayerId).toBe('b');
  });

  it('edge: replay того же effectId после резолва — протух', async () => {
    const after = await hissFight([filler('junk::0', 1)]);
    const pending = head(after);
    const chosen = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, cardIds: ['junk::0'] }, ctx(after, 'b'));
    expect(chosen.success).toBe(true);
    const replay = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, cardIds: ['junk::0'] }, ctx(chosen.gameState!, 'b'));
    expect(replay.success).toBe(false);
    expect(replay.error).toContain('протух');
  });

  it('positive: Clutching Claws как АТАКА Harpy — pending принадлежит ЗАЩИТНИКУ, он выбирает свою карту', async () => {
    // banner «Harpy»: атакует harpy1; bhero придвигаем для melee-смежности
    const state = bHand(
      inHand(medusaState({ bheroAt: { x: 1, y: 1 } }), { ...medusaCard('Clutching Claws'), id: 'claw::0' }),
      [filler('bkeep1::0', 4), filler('bkeep2::0', 2)]);
    const attack = await executor.executeAttack(
      { gameId: 's05m', attackerId: 'harpy1', targetId: 'bhero', cardId: 'claw::0' } as any, ctx(state));
    expect(attack.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's05m' } as any, ctx(attack.gameState!, 'm'));
    expect(resolved.success).toBe(true);
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('DISCARD_CARDS');
    expect(pending.playerId).toBe('b'); // оппонент игрока Clutching Claws
    // защитник выбирает карту к сбросу САМ — движок не решает за него
    const chosen = await executor.executeResolvePendingEffect(
      { gameId: 's05m', effectId: pending.id, cardIds: ['bkeep2::0'] }, ctx(resolved.gameState!, 'b'));
    expect(chosen.success).toBe(true);
    expect(chosen.gameState!.handZones.b.cards.map((c) => c.id)).toEqual(['bkeep1::0']);
    expect(chosen.gameState!.discardPiles.b.map((c) => c.id)).toContain('bkeep2::0');
    expect(chosen.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('все 11 записей: ingest produces at least one non-UNSUPPORTED effect (никакой не молчаливый no-op)', () => {
    for (const c of capture.cards) {
      const card = ingest(c);
      expect(card.effects!.length).toBeGreaterThan(0);
      expect(card.effects!.some((e) => e.type !== 'UNSUPPORTED')).toBe(true);
    }
  });
});
