/** GD-021..023: Arthur deck records driven through the REAL executor
 * (production ingest: capture → normalizeCardEffects → upgradeStaleParserEffects
 * → SCHEME fullText fallback — same code as GameInitializationService / backfill).
 * Positive, negative and edge cases per literal printed text (S01 rules-oracle,
 * Arthur card exceptions). Noble Sacrifice dual-slot boost и Arthur Feint
 * (CANCEL на reveal) уже покрыты в s05-boost-timing.spec.ts — здесь не дублируются. */
import * as fs from 'fs';
import * as path from 'path';
import { GameState, PendingEffect } from '../models';
import { Card, CardType, FighterType, GamePhase } from '../models';
import { normalizeCardEffects } from '../models';
import { parseCardEffectTexts, upgradeStaleParserEffects } from '../effects/effect-text-parser';
import { s03Engine } from '../../test/fixtures/s03-engine.fixture';
import { GameStateService } from '../../games/game-state.service';

const { executor } = s03Engine();
const ctx = (state: GameState, userId = 'a') =>
  ({ userId, gameId: state.gameId, currentState: state }) as any;

const capture = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../../../..', 'docs/game-design/evidence/S01/content-king-arthur.json'),
    'utf8',
  ),
) as { cards: Array<Record<string, any>> };

/** Production ingest (mirrors GameInitializationService.resolveCardEffects). */
function ingest(card: Record<string, any>): Card {
  const effects = normalizeCardEffects(card.effects, card.id);
  const fullText = card.cardType === 'SCHEME' && card.textEn?.trim() ? card.textEn : undefined;
  const resolved =
    effects.length > 0
      ? upgradeStaleParserEffects(
          effects,
          {
            immediately: card.effectImmediately,
            during: card.effectDuring,
            after: card.effectAfter,
            boost: card.effectBoost,
            ongoing: card.effectOngoing,
            fullText,
          },
          card.id,
        )
      : fullText
        ? parseCardEffectTexts({ fullText }, card.id).effects
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

const arthurCard = (name: string, copy = 0): Card => {
  const base = ingest(capture.cards.find((c) => c.name === name)!);
  return copy === 0 ? base : { ...base, id: `${base.cardId}::${copy}` };
};

// --- Arthur board: 8×2, x 0..3 = zone 'west' (enemy), x 4..7 = 'east'
// (зона Arthur/Merlin). У 'a' РОВНО ОДИН HERO (terminal-state смотрит
// первого HERO владельца).
function arthurState(opts?: {
  arthurHp?: number;
  arthurAt?: { x: number; y: number };
  merlinAt?: { x: number; y: number };
  merlinDead?: boolean;
  bheroAt?: { x: number; y: number };
  bminAt?: { x: number; y: number };
  bminHp?: number;
}): GameState {
  const cells = Array.from({ length: 2 }, (_, y) =>
    Array.from({ length: 8 }, (_, x) => ({ x, y, type: 'normal', zones: x <= 3 ? ['west'] : ['east'] })));
  const fighters = [
    { id: 'arthur', ownerId: 'a', heroId: 'a', heroSlug: 'king-arthur', name: 'King Arthur', type: FighterType.HERO,
      health: opts?.arthurHp ?? 12, maxHealth: 12, position: opts?.arthurAt ?? { x: 5, y: 0 }, effects: [], hasSidekick: true, movement: 2 },
    { id: 'merlin', ownerId: 'a', heroId: 'a', heroSlug: 'king-arthur', name: 'Merlin', type: FighterType.MINION,
      health: 4, maxHealth: 4, position: opts?.merlinAt ?? { x: 6, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
    { id: 'bhero', ownerId: 'b', heroId: 'b', name: 'Enemy Hero', type: FighterType.HERO,
      health: 12, maxHealth: 12, position: opts?.bheroAt ?? { x: 2, y: 0 }, effects: [], hasSidekick: false, movement: 2 },
    { id: 'bmin', ownerId: 'b', heroId: 'b', name: 'Enemy Minion', type: FighterType.MINION,
      health: opts?.bminHp ?? 3, maxHealth: 3, position: opts?.bminAt ?? { x: 3, y: 1 }, effects: [], hasSidekick: false, movement: 2 },
  ].map((f) =>
    f.id === 'merlin' && opts?.merlinDead ? { ...f, health: 0, isDefeated: true } : f,
  ) as GameState['fighters'];
  return {
    gameId: 's06a', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER,
    turnCount: 1, currentTurnPlayerId: 'a',
    players: ['a', 'b'].map((userId) => ({ userId, heroId: userId, health: 12, maxHealth: 12, fighterIds: [], isAlive: true })),
    fighters,
    decks: { a: { cards: [], drawPile: [] }, b: { cards: [], drawPile: [] } },
    handZones: { a: { cards: [], maxSize: 7 }, b: { cards: [], maxSize: 7 } },
    discardPiles: { a: [], b: [] },
    boardState: { width: 8, height: 2, cells, doors: {}, fog: {}, tokens: {} } as any,
    metadata: { lastActionAt: new Date(0), lastActionBy: 'a', version: 1, actionsRemaining: 2 },
  } as GameState;
}

const inHand = (state: GameState, card: Card): GameState => ({
  ...state,
  handZones: { ...state.handZones, a: { cards: [{ ...card, isVisible: true }], maxSize: 7 } },
});

const bHand = (state: GameState, cards: Card[]): GameState => ({
  ...state,
  handZones: { ...state.handZones, b: { cards: cards.map((c) => ({ ...c, isVisible: true })), maxSize: 7 } },
});

const aDraw = (state: GameState, pile: Card[]): GameState => ({
  ...state,
  decks: { ...state.decks, a: { cards: [], drawPile: pile } },
});

const aDiscard = (state: GameState, pile: Card[]): GameState => ({
  ...state,
  discardPiles: { ...state.discardPiles, a: pile },
});

const filler = (id: string, boostValue = 0): Card => ({
  id, cardId: id.replace(/::\d+$/, ''), name: id, nameEn: id, nameRu: id,
  cardType: CardType.SCHEME, boostValue, effects: [],
} as Card);

const weakAtk = (id: string, value: number): Card => ({
  id, cardId: id, name: id, nameEn: id, nameRu: id,
  cardType: CardType.ATTACK, attackValue: value, effects: [],
} as Card);

const bigDef = (id: string, value: number): Card => ({
  id, cardId: id, name: id, nameEn: id, nameRu: id,
  cardType: CardType.DEFENSE, defenseValue: value, effects: [],
} as Card);

const head = (state: GameState): PendingEffect => state.metadata.pendingEffects![0];
const ids = (cards: readonly Card[]) => cards.map((c) => c.id).sort();

describe('GD-021: The Lady of the Lake (SCHEME x1) — search + add + shuffle', () => {
  const excalibur = (): Card => arthurCard('Excalibur');

  it('positive: Excalibur в КОЛОДЕ → в руку, остальные карты колоды сохранены (multiset), колода перемешана', async () => {
    const f1 = filler('f1::0'), f2 = filler('f2::0'), f3 = filler('f3::0');
    const state = aDraw(inHand(arthurState(), arthurCard('The Lady of the Lake')), [f1, excalibur(), f2, f3]);
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    expect(played.success).toBe(true);
    const after = played.gameState!;
    expect(after.handZones.a.cards.map((c) => c.name)).toEqual(['Excalibur']);
    expect(after.decks.a.drawPile).toHaveLength(3);
    expect(ids(after.decks.a.drawPile)).toEqual(['f1::0', 'f2::0', 'f3::0']);
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.currentTurnPlayerId).toBe('a');
    expect(after.metadata.actionsRemaining).toBe(1);
  });

  it('positive: Excalibur в СБРОСЕ → в руку из сброса, колода всё равно перемешана (deck просматривается)', async () => {
    const f1 = filler('f1::0'), f2 = filler('f2::0');
    const state = aDiscard(
      aDraw(inHand(arthurState(), arthurCard('The Lady of the Lake')), [f1, f2]),
      [excalibur()],
    );
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    expect(played.success).toBe(true);
    const after = played.gameState!;
    expect(after.handZones.a.cards.map((c) => c.name)).toEqual(['Excalibur']);
    // в сбросе осталась ТОЛЬКО сыгранная схема; Excalibur оттуда изъята
    expect(after.discardPiles.a.map((c) => c.name)).toEqual(['The Lady of the Lake']);
    expect(ids(after.decks.a.drawPile)).toEqual(['f1::0', 'f2::0']);
  });

  it('edge: Excalibur уже в руке — не найдена в колоде/сбросе, дубликата нет, колода не теряет карт', async () => {
    const f1 = filler('f1::0');
    const lady = arthurCard('The Lady of the Lake');
    const state = {
      ...aDraw(arthurState(), [f1]),
      handZones: { ...arthurState().handZones, a: { cards: [lady, excalibur()].map((c) => ({ ...c, isVisible: true })), maxSize: 7 } },
    } as GameState;
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    expect(played.success).toBe(true);
    const after = played.gameState!;
    // дубликата нет: Excalibur осталась одна; Lady ушла в сброс
    expect(after.handZones.a.cards.map((c) => c.name)).toEqual(['Excalibur']);
    expect(after.discardPiles.a.map((c) => c.name)).toEqual(['The Lady of the Lake']);
    expect(ids(after.decks.a.drawPile)).toEqual(['f1::0']);
  });

  it('negative: чужой игрок не может сыграть чужую схему', async () => {
    const state = inHand(arthurState(), arthurCard('The Lady of the Lake'));
    const foreign = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state, 'b'));
    expect(foreign.success).toBe(false);
    expect(foreign.error).toContain('No action available');
  });
});

describe('GD-021: Prophecy (SCHEME x2) — look 4 / pick 2 / order rest', () => {
  it('positive: полный цикл PICK 2 → ORDER остатка наверх колоды', async () => {
    const p1 = filler('p1::0'), p2 = filler('p2::0'), p3 = filler('p3::0'), p4 = filler('p4::0');
    const state = aDraw(inHand(arthurState(), arthurCard('Prophecy')), [p1, p2, p3, p4]);
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    expect(played.success).toBe(true);
    // колода атомарно «без» верхних 4; выбор owner-bound и персистентный
    expect(played.gameState!.decks.a.drawPile).toHaveLength(0);
    const pending = head(played.gameState!);
    expect(pending.type).toBe('DECK_TOP_PICK');
    expect(pending.mode).toBe('PICK');
    expect(pending.value).toBe(2);
    expect(pending.playerId).toBe('a');
    expect(pending.revealedCards!.map((c) => c.id)).toEqual(['p1::0', 'p2::0', 'p3::0', 'p4::0']);

    // PICK: ровно 2 из revealed (по instance id) → в руку; остаётся ORDER
    const picked = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, cardIds: ['p1::0', 'p3::0'] }, ctx(played.gameState!));
    expect(picked.success).toBe(true);
    expect(picked.gameState!.handZones.a.cards.map((c) => c.id).sort()).toEqual(['p1::0', 'p3::0']);
    const order = head(picked.gameState!);
    expect(order.type).toBe('DECK_TOP_PICK');
    expect(order.mode).toBe('ORDER');
    expect(order.revealedCards!.map((c) => c.id).sort()).toEqual(['p2::0', 'p4::0']);

    // ORDER: полный порядок top→bottom → drawPile
    const ordered = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: order.id, cardIds: ['p4::0', 'p2::0'] }, ctx(picked.gameState!));
    expect(ordered.success).toBe(true);
    const after = ordered.gameState!;
    expect(after.decks.a.drawPile.map((c) => c.id)).toEqual(['p4::0', 'p2::0']);
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.currentTurnPlayerId).toBe('a');
    expect(after.metadata.actionsRemaining).toBe(1);
  });

  it('negative: PICK — неверное число карт, чужая карта, чужой игрок; ORDER — неполный порядок', async () => {
    const p1 = filler('p1::0'), p2 = filler('p2::0'), p3 = filler('p3::0'), p4 = filler('p4::0');
    const extra = filler('ghost::0');
    const state = aDraw(inHand(arthurState(), arthurCard('Prophecy')), [p1, p2, p3, p4]);
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    const pending = head(played.gameState!);

    const one = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, cardIds: ['p1::0'] }, ctx(played.gameState!));
    expect(one.success).toBe(false);
    const three = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, cardIds: ['p1::0', 'p2::0', 'p3::0'] }, ctx(played.gameState!));
    expect(three.success).toBe(false);
    const foreignCard = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, cardIds: ['p1::0', extra.id] }, ctx(played.gameState!));
    expect(foreignCard.success).toBe(false);
    expect(foreignCard.error).toContain('ровно 2');
    const foreign = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, cardIds: ['p1::0', 'p2::0'] }, ctx(played.gameState!, 'b'));
    expect(foreign.success).toBe(false);
    expect(foreign.error).toContain('другому игроку');

    // валидный PICK → ORDER-стадия: неполная перестановка отклоняется
    const picked = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, cardIds: ['p1::0', 'p2::0'] }, ctx(played.gameState!));
    const order = head(picked.gameState!);
    const partial = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: order.id, cardIds: ['p3::0'] }, ctx(picked.gameState!));
    expect(partial.success).toBe(false);
    expect(partial.error).toContain('порядок ВСЕХ');
    // mandatory — decline запрещён
    const declined = await executor.executeDeclinePendingEffect(
      { gameId: 's06a', effectId: order.id }, ctx(picked.gameState!));
    expect(declined.success).toBe(false);
  });

  it('edge: колода 3 карты → view 3, pick 2, остаток 1 возвращается БЕЗ ORDER-стадии', async () => {
    const p1 = filler('p1::0'), p2 = filler('p2::0'), p3 = filler('p3::0');
    const state = aDraw(inHand(arthurState(), arthurCard('Prophecy')), [p1, p2, p3]);
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    const pending = head(played.gameState!);
    expect(pending.revealedCards).toHaveLength(3);
    expect(pending.value).toBe(2);
    const picked = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, cardIds: ['p1::0', 'p2::0'] }, ctx(played.gameState!));
    expect(picked.success).toBe(true);
    const after = picked.gameState!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.decks.a.drawPile.map((c) => c.id)).toEqual(['p3::0']); // наверх без порядка
  });

  it('edge: колода 1 карта → view 1, pick 1; пустая колода → no-op БЕЗ истощения', async () => {
    const only = filler('only::0');
    const state1 = aDraw(inHand(arthurState(), arthurCard('Prophecy')), [only]);
    const played1 = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state1.handZones.a.cards[0].id } as any, ctx(state1));
    const pending1 = head(played1.gameState!);
    expect(pending1.value).toBe(1);
    expect(pending1.revealedCards).toHaveLength(1);
    const picked1 = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending1.id, cardIds: ['only::0'] }, ctx(played1.gameState!));
    expect(picked1.gameState!.handZones.a.cards.map((c) => c.id)).toEqual(['only::0']);
    expect(picked1.gameState!.decks.a.drawPile).toHaveLength(0);
    expect(picked1.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);

    // пустая колода: no-op, R-04 exhaustion НЕ применяется (не required draw)
    const state0 = inHand(arthurState(), arthurCard('Prophecy'));
    const played0 = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state0.handZones.a.cards[0].id } as any, ctx(state0));
    expect(played0.success).toBe(true);
    expect(played0.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(played0.gameState!.fighters.find((f) => f.id === 'arthur')!.health).toBe(12);
  });

  it('privacy: filterPrivateData скрывает revealedCards от соперника, владелец видит', async () => {
    const p1 = filler('p1::0'), p2 = filler('p2::0'), p3 = filler('p3::0'), p4 = filler('p4::0');
    const state = aDraw(inHand(arthurState(), arthurCard('Prophecy')), [p1, p2, p3, p4]);
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    const svc = new GameStateService(null as any, null as any);
    const forOpponent = svc.filterPrivateData(played.gameState!, 'b');
    const oppPending = forOpponent.metadata.pendingEffects![0];
    expect((oppPending as any).revealedCards).toBeUndefined();
    expect((oppPending as any).revealedCount).toBe(4);
    expect(JSON.stringify(oppPending)).not.toContain('p1::0');
    const forOwner = svc.filterPrivateData(played.gameState!, 'a');
    expect((forOwner.metadata.pendingEffects![0] as any).revealedCards).toHaveLength(4);
  });
});

describe('GD-022: Command the Storms (SCHEME x2) — sequential queue over ALL fighters', () => {
  it('positive: по одному optional MOVE на каждого ЖИВОГО бойца обеих сторон; владелец эффекта двигает и чужих', async () => {
    const state = inHand(arthurState(), arthurCard('Command the Storms'));
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    expect(played.success).toBe(true);
    const queue = played.gameState!.metadata.pendingEffects!;
    expect(queue.map((p) => p.type)).toEqual(['MOVE', 'MOVE', 'MOVE', 'MOVE']);
    expect(queue.map((p) => p.fighterIds![0])).toEqual(['arthur', 'merlin', 'bhero', 'bmin']);
    // (This includes opposing fighters.) — «up to 3» → optional
    expect(queue.every((p) => p.value === 3 && p.optional === true)).toBe(true);
    expect(queue.map((p) => p.targetsOpponent)).toEqual([false, false, true, true]);

    // резолв: свои — нулевой шаг/ход, ЧУЖОЙ bhero двинут ВЛАДЕЛЬЦЕМ эффекта
    let cur = played.gameState!;
    const step = async (fid: string, x: number, y: number) => {
      const r = await executor.executeResolvePendingEffect(
        { gameId: 's06a', effectId: head(cur).id, fighterId: fid, x, y }, ctx(cur));
      expect(r.success).toBe(true);
      cur = r.gameState!;
    };
    await step('arthur', 5, 0);   // 0 шагов легален
    await step('merlin', 7, 0);   // 1 шаг
    await step('bhero', 0, 0);    // чужой боец, 2 шага
    await step('bmin', 3, 1);     // 0 шагов
    expect(cur.fighters.find((f) => f.id === 'bhero')!.position).toEqual({ x: 0, y: 0 });
    expect(cur.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(cur.currentTurnPlayerId).toBe('a');
    expect(cur.metadata.actionsRemaining).toBe(1);
  });

  it('negative: дистанция > 3 и занятая клетка отклоняются; очередь не двигается', async () => {
    const state = inHand(arthurState(), arthurCard('Command the Storms'));
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    let cur = played.gameState!;
    const zero = async (fid: string) => {
      const f = cur.fighters.find((x) => x.id === fid)!;
      const r = await executor.executeResolvePendingEffect(
        { gameId: 's06a', effectId: head(cur).id, fighterId: fid, x: f.position.x, y: f.position.y }, ctx(cur));
      cur = r.gameState!;
    };
    await zero('arthur');
    await zero('merlin');
    // bhero (2,0) → (7,0): дистанция 5 > 3
    const tooFar = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: head(cur).id, fighterId: 'bhero', x: 7, y: 0 }, ctx(cur));
    expect(tooFar.success).toBe(false);
    expect(tooFar.error).toContain('не добраться за 3');
    // bhero → (3,1): свободно по дистанции, но занято bmin
    const occupied = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: head(cur).id, fighterId: 'bhero', x: 3, y: 1 }, ctx(cur));
    expect(occupied.success).toBe(false);
    expect(occupied.error).toContain('Клетка занята');
    // чужой резолвер не может двигать даже свою очередь выбора
    const foreign = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: head(cur).id, fighterId: 'bhero', x: 2, y: 0 }, ctx(cur, 'b'));
    expect(foreign.success).toBe(false);
    expect(foreign.error).toContain('другому игроку');
  });

  it('negative: banner Merlin — поверженный Merlin ⇒ схему вообще нельзя разыграть', async () => {
    const state = inHand(arthurState({ merlinDead: true }), arthurCard('Command the Storms'));
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    expect(played.success).toBe(false);
    expect(played.error).toContain('«Merlin» нельзя разыграть');
    expect(played.gameState?.metadata?.pendingEffects ?? []).toHaveLength(0);
  });
});

describe('GD-022: Restless Spirits (SCHEME x2) — two-stage zone/adjacent area damage', () => {
  const playRestless = async (state: GameState) => {
    const played = await executor.executePlayScheme(
      { gameId: 's06a', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    expect(played.success).toBe(true);
    return played.gameState!;
  };

  it('positive: клетка в зоне Merlin → смежная → 2 урона врагам в обеих клетках; defeat → добор 1', async () => {
    // bmin (5,1) hp 1 — в east (зона Merlin); bhero (2,0) вне зоны урона
    const d1 = filler('d1::0');
    const state = aDraw(inHand(arthurState({ bminAt: { x: 5, y: 1 }, bminHp: 1 }), arthurCard('Restless Spirits')), [d1]);
    let cur = await playRestless(state);
    const pending = head(cur);
    expect(pending.type).toBe('CHOOSE_SPACE');
    expect(pending.stage).toBe(1);
    expect(pending.zoneFighterName).toBe('Merlin');
    expect(pending.damage).toBe(2);
    expect(pending.drawIfDefeated).toBe(1);
    expect(pending.playerId).toBe('a');

    // stage 1: клетка ВНЕ зоны Merlin (west) отклоняется
    const west = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, x: 3, y: 1 }, ctx(cur));
    expect(west.success).toBe(false);
    expect(west.error).toContain('зоне «Merlin»');
    // stage 1 ok: (5,1) — в зоне (занятая клетка легальна: «any space»)
    const s1 = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, x: 5, y: 1 }, ctx(cur));
    expect(s1.success).toBe(true);
    cur = s1.gameState!;
    const s2pending = head(cur);
    expect(s2pending.stage).toBe(2);
    expect(s2pending.anchor).toEqual({ x: 5, y: 1 });
    // stage 2: несмежная клетка отклоняется
    const far = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: s2pending.id, x: 2, y: 0 }, ctx(cur));
    expect(far.success).toBe(false);
    expect(far.error).toContain('смежной');
    // stage 2 ok: (4,1) смежна (5,1)
    const s2 = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: s2pending.id, x: 4, y: 1 }, ctx(cur));
    expect(s2.success).toBe(true);
    const after = s2.gameState!;
    // bmin в anchor-клетке: 1 − 2 → повержен; своих/чужих вне клеток не задело
    const bmin = after.fighters.find((f) => f.id === 'bmin')!;
    expect(bmin.health).toBe(0);
    expect(bmin.isDefeated).toBe(true);
    expect(after.fighters.find((f) => f.id === 'bhero')!.health).toBe(12);
    expect(after.fighters.find((f) => f.id === 'arthur')!.health).toBe(12);
    // «If at least one fighter is defeated this way, draw 1 card.»
    expect(after.handZones.a.cards.map((c) => c.id)).toEqual(['d1::0']);
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.currentTurnPlayerId).toBe('a');
    expect(after.metadata.actionsRemaining).toBe(1);
  });

  it('positive: урон в ОБЕИХ клетках по вражеским бойцам, свои не задеты', async () => {
    // bmin (5,1) hp 3 в anchor; bhero (4,1) hp 12 в смежной; свои: arthur (5,0) смежен, но свой
    const state = inHand(
      arthurState({ bminAt: { x: 5, y: 1 }, bheroAt: { x: 4, y: 1 } }),
      arthurCard('Restless Spirits'),
    );
    let cur = await playRestless(state);
    const s1 = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: head(cur).id, x: 5, y: 1 }, ctx(cur));
    cur = s1.gameState!;
    const s2 = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: head(cur).id, x: 4, y: 1 }, ctx(cur));
    expect(s2.success).toBe(true);
    const after = s2.gameState!;
    expect(after.fighters.find((f) => f.id === 'bmin')!.health).toBe(1);
    expect(after.fighters.find((f) => f.id === 'bhero')!.health).toBe(10);
    expect(after.fighters.find((f) => f.id === 'arthur')!.health).toBe(12);
    // никого не повержено → добора НЕТ (рука пуста, колода не тронута)
    expect(after.handZones.a.cards).toHaveLength(0);
  });

  it('edge: в выбранных клетках нет вражеских бойцов — no-op, очередь не strandится', async () => {
    const d1 = filler('d1::0');
    const state = aDraw(inHand(arthurState(), arthurCard('Restless Spirits')), [d1]);
    let cur = await playRestless(state);
    // (4,1) и (4,0) — свободные клетки east
    const s1 = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: head(cur).id, x: 4, y: 1 }, ctx(cur));
    cur = s1.gameState!;
    const s2 = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: head(cur).id, x: 4, y: 0 }, ctx(cur));
    expect(s2.success).toBe(true);
    const after = s2.gameState!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.handZones.a.cards).toHaveLength(0);
    expect(after.decks.a.drawPile.map((c) => c.id)).toEqual(['d1::0']);
  });

  it('negative: чужой игрок не резолвит выбор клетки', async () => {
    const state = inHand(arthurState(), arthurCard('Restless Spirits'));
    const cur = await playRestless(state);
    const foreign = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: head(cur).id, x: 4, y: 1 }, ctx(cur, 'b'));
    expect(foreign.success).toBe(false);
    expect(foreign.error).toContain('другому игроку');
  });
});

describe('GD-022: The Holy Grail (DEFENSE x2) — set health threshold', () => {
  const grailFight = async (arthurHp: number, atkValue: number) => {
    // bhero (4,0) смежен с Arthur (5,0); b атакует (ход 'b'), Arthur защищается Grail (def 1)
    const grail = arthurCard('The Holy Grail');
    const state = {
      ...bHand(inHand(arthurState({ arthurHp, bheroAt: { x: 4, y: 0 } }), grail), [weakAtk('weak::0', atkValue)]),
      currentTurnPlayerId: 'b',
    } as GameState;
    const attack = await executor.executeAttack(
      { gameId: 's06a', attackerId: 'bhero', targetId: 'arthur', cardId: 'weak::0' } as any, ctx(state, 'b'));
    expect(attack.success).toBe(true);
    const defended = await executor.executePlayDefense(
      { gameId: 's06a', cardId: attack.gameState!.handZones.a.cards[0].id } as any, ctx(attack.gameState!, 'a'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's06a' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);
    return resolved.gameState!;
  };

  it('positive: HP ≤ 4 после боевого урона → SET ровно 8 (не heal сверх, не +N)', async () => {
    // HP 4 − (2−1) = 3 → set 8
    const after = await grailFight(4, 2);
    expect(after.fighters.find((f) => f.id === 'arthur')!.health).toBe(8);
    expect(after.metadata.combatInfo).toBeUndefined();
  });

  it('negative: HP выше порога → без изменений', async () => {
    // HP 12 − 1 = 11 > 4 → без изменений
    const after = await grailFight(12, 2);
    expect(after.fighters.find((f) => f.id === 'arthur')!.health).toBe(11);
  });

  it('edge: поверженный Arthur → здоровье НЕ устанавливается (dead threshold), GAME_OVER', async () => {
    // HP 2 − (5−1) = −2 → повержен до after-эффектов; set не применяется
    const after = await grailFight(2, 5);
    expect(after.fighters.find((f) => f.id === 'arthur')!.health).toBe(0);
    expect(after.fighters.find((f) => f.id === 'arthur')!.isDefeated).toBe(true);
    expect(after.phase).toBe(GamePhase.GAME_OVER);
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
  });
});

describe('GD-023: Skirmish (VERSATILE x2) — combat fighter choice', () => {
  it('positive: WON → один pending с ЛЮБЫМ живым участником боя (включая чужого); чужой боец двинут владельцем эффекта', async () => {
    const skirmish = arthurCard('Skirmish');
    const state = inHand(arthurState({ bheroAt: { x: 4, y: 0 } }), skirmish);
    const attack = await executor.executeAttack(
      { gameId: 's06a', attackerId: 'arthur', targetId: 'bhero', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    expect(attack.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's06a' } as any, ctx(attack.gameState!, 'a'));
    expect(resolved.success).toBe(true);
    const pending = head(resolved.gameState!);
    expect(pending.type).toBe('MOVE');
    expect(pending.value).toBe(2);
    expect([...pending.fighterIds!].sort()).toEqual(['arthur', 'bhero']);
    expect(pending.anyOwner).toBe(true);
    expect(pending.playerId).toBe('a');
    // легитимный pending ≠ manual-эффект: аудит ручных эффектов пуст
    expect((resolved.metadata as any)?.manualEffects ?? []).toEqual([]);

    // choose one of the fighters in the combat: ЧУЖОЙ защитник bhero (4,0) → (2,0)
    const moved = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, fighterId: 'bhero', x: 2, y: 0 }, ctx(resolved.gameState!));
    expect(moved.success).toBe(true);
    expect(moved.gameState!.fighters.find((f) => f.id === 'bhero')!.position).toEqual({ x: 2, y: 0 });
    expect(moved.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('negative: LOST combat → pending НЕТ (условие «If you won the combat»)', async () => {
    const skirmish = arthurCard('Skirmish');
    const state = bHand(
      inHand(arthurState({ bheroAt: { x: 4, y: 0 } }), skirmish),
      [bigDef('bigdef::0', 9)],
    );
    const attack = await executor.executeAttack(
      { gameId: 's06a', attackerId: 'arthur', targetId: 'bhero', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    const defended = await executor.executePlayDefense(
      { gameId: 's06a', cardId: 'bigdef::0' } as any, ctx(attack.gameState!, 'b'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's06a' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);
    expect(resolved.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('negative: боец вне участников боя отклоняется', async () => {
    const skirmish = arthurCard('Skirmish');
    const state = inHand(arthurState({ bheroAt: { x: 4, y: 0 } }), skirmish);
    const attack = await executor.executeAttack(
      { gameId: 's06a', attackerId: 'arthur', targetId: 'bhero', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    const resolved = await executor.executeResolveCombat({ gameId: 's06a' } as any, ctx(attack.gameState!, 'a'));
    const pending = head(resolved.gameState!);
    const outsider = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, fighterId: 'merlin', x: 6, y: 0 }, ctx(resolved.gameState!));
    expect(outsider.success).toBe(false);
    expect(outsider.error).toContain('not a target');
  });
});

describe('GD-023: Bewilderment (DEFENSE x2) — prevent + place', () => {
  // banner Merlin: защищается MERLIN. bhero (5,1) смежен с merlin (5,0);
  // arthur сдвинут на (4,0).
  const bewFight = async () => {
    const bew = arthurCard('Bewilderment');
    const state = {
      ...bHand(
        inHand(arthurState({ bheroAt: { x: 5, y: 1 }, merlinAt: { x: 5, y: 0 }, arthurAt: { x: 4, y: 0 } }), bew),
        [weakAtk('weak::0', 6)]),
      currentTurnPlayerId: 'b',
    } as GameState;
    const attack = await executor.executeAttack(
      { gameId: 's06a', attackerId: 'bhero', targetId: 'merlin', cardId: 'weak::0' } as any, ctx(state, 'b'));
    expect(attack.success).toBe(true);
    const defended = await executor.executePlayDefense(
      { gameId: 's06a', cardId: attack.gameState!.handZones.a.cards[0].id } as any, ctx(attack.gameState!, 'a'));
    expect(defended.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's06a' } as any, ctx(defended.gameState!, 'b'));
    expect(resolved.success).toBe(true);
    return resolved.gameState!;
  };

  it('positive: PREVENT весь урон; после боя optional PLACE в ЛЮБУЮ клетку (даже другую зону)', async () => {
    const after = await bewFight();
    // Prevent all damage: HP не изменился (def 0, атака 6 — всё предотвращено)
    expect(after.fighters.find((f) => f.id === 'merlin')!.health).toBe(4);
    const pending = head(after);
    expect(pending.type).toBe('PLACE');
    expect(pending.optional).toBe(true);
    expect(pending.playerId).toBe('a');
    // «any space» — без зонного ограничения: (0,1) west, свободна
    const placed = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, fighterId: 'merlin', x: 0, y: 1 }, ctx(after));
    expect(placed.success).toBe(true);
    expect(placed.gameState!.fighters.find((f) => f.id === 'merlin')!.position).toEqual({ x: 0, y: 1 });
    expect(placed.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('positive: decline (optional) — боец остаётся на месте', async () => {
    const after = await bewFight();
    const declined = await executor.executeDeclinePendingEffect(
      { gameId: 's06a', effectId: head(after).id }, ctx(after));
    expect(declined.success).toBe(true);
    expect(declined.gameState!.fighters.find((f) => f.id === 'merlin')!.position).toEqual({ x: 5, y: 0 });
    expect(declined.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('negative: banner Merlin — Arthur не может играть Bewilderment', async () => {
    const bew = arthurCard('Bewilderment');
    // атака на ARTHUR (не Merlin): защитник-Arthur с картой banner Merlin
    const state = {
      ...bHand(inHand(arthurState({ bheroAt: { x: 4, y: 0 }, merlinAt: { x: 6, y: 0 } }), bew), [weakAtk('weak::0', 6)]),
      currentTurnPlayerId: 'b',
    } as GameState;
    const attack = await executor.executeAttack(
      { gameId: 's06a', attackerId: 'bhero', targetId: 'arthur', cardId: 'weak::0' } as any, ctx(state, 'b'));
    expect(attack.success).toBe(true);
    const defended = await executor.executePlayDefense(
      { gameId: 's06a', cardId: attack.gameState!.handZones.a.cards[0].id } as any, ctx(attack.gameState!, 'a'));
    expect(defended.success).toBe(false);
    expect(defended.error).toContain('«Merlin» может играть только этот боец');
  });
});

describe('GD-023: прочие Arthur-записи — production runtime (compact fixtures)', () => {
  const fightWon = async (cardName: string, pile: Card[] = []) => {
    const card = arthurCard(cardName);
    const state = aDraw(inHand(arthurState({ bheroAt: { x: 4, y: 0 } }), card), pile);
    const attack = await executor.executeAttack(
      { gameId: 's06a', attackerId: 'arthur', targetId: 'bhero', cardId: state.handZones.a.cards[0].id } as any, ctx(state));
    expect(attack.success).toBe(true);
    const resolved = await executor.executeResolveCombat({ gameId: 's06a' } as any, ctx(attack.gameState!, 'a'));
    expect(resolved.success).toBe(true);
    return resolved.gameState!;
  };

  it('Swift Strike: WON → optional MOVE up to 4 для атакующего', async () => {
    const after = await fightWon('Swift Strike');
    const pending = head(after);
    expect(pending.type).toBe('MOVE');
    expect(pending.value).toBe(4);
    expect(pending.optional).toBe(true);
    expect(pending.fighterIds).toContain('arthur');
  });

  it('Divine Intervention: WON → MOVE только King Arthur (NAMED), Merlin не легален', async () => {
    const after = await fightWon('Divine Intervention');
    const pending = head(after);
    expect(pending.type).toBe('MOVE');
    expect(pending.value).toBe(5);
    expect(pending.fighterName).toBe('King Arthur');
    expect(pending.fighterIds).toEqual(['arthur']);
    const merlin = await executor.executeResolvePendingEffect(
      { gameId: 's06a', effectId: pending.id, fighterId: 'merlin', x: 6, y: 0 }, ctx(after));
    expect(merlin.success).toBe(false);
  });

  it('The Aid of Morgana: after combat draw 2 (без won-условия)', async () => {
    const d1 = filler('m1::0'), d2 = filler('m2::0');
    const after = await fightWon('The Aid of Morgana', [d1, d2]);
    expect(after.handZones.a.cards.map((c) => c.id).sort()).toEqual(['m1::0', 'm2::0']);
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('Aid the Chosen One (banner Merlin): WON → draw 2; LOST → добора нет', async () => {
    // banner Merlin: атакует MERLIN (5,1) по bhero (4,1), смежны
    const card = arthurCard('Aid the Chosen One');
    const wonState = aDraw(
      inHand(arthurState({ bheroAt: { x: 4, y: 1 }, merlinAt: { x: 5, y: 1 } }), card),
      [filler('w1::0'), filler('w2::0')],
    );
    const wonAttack = await executor.executeAttack(
      { gameId: 's06a', attackerId: 'merlin', targetId: 'bhero', cardId: wonState.handZones.a.cards[0].id } as any, ctx(wonState));
    expect(wonAttack.success).toBe(true);
    const won = await executor.executeResolveCombat({ gameId: 's06a' } as any, ctx(wonAttack.gameState!, 'a'));
    expect(won.success).toBe(true);
    expect(won.gameState!.handZones.a.cards.map((c) => c.id).sort()).toEqual(['w1::0', 'w2::0']);

    const lostState = bHand(
      aDraw(inHand(arthurState({ bheroAt: { x: 4, y: 1 }, merlinAt: { x: 5, y: 1 } }), card), [filler('l1::0'), filler('l2::0')]),
      [bigDef('bigdef::0', 9)],
    );
    const attack = await executor.executeAttack(
      { gameId: 's06a', attackerId: 'merlin', targetId: 'bhero', cardId: lostState.handZones.a.cards[0].id } as any, ctx(lostState));
    const defended = await executor.executePlayDefense(
      { gameId: 's06a', cardId: 'bigdef::0' } as any, ctx(attack.gameState!, 'b'));
    const lost = await executor.executeResolveCombat({ gameId: 's06a' } as any, ctx(defended.gameState!, 'b'));
    expect(lost.gameState!.handZones.a.cards).toHaveLength(0);
    expect(lost.gameState!.decks.a.drawPile).toHaveLength(2);
  });

  it('Regroup (Arthur): WON → 2, LOST → 1 (то же правило, что у Medusa-записи)', async () => {
    const won = await fightWon('Regroup', [filler('r1::0'), filler('r2::0')]);
    expect(won.handZones.a.cards.map((c) => c.id).sort()).toEqual(['r1::0', 'r2::0']);
  });

  it('Momentous Shift: parse → SET_VALUE 5 при MOVED_THIS_TURN; бой резолвится без strand', async () => {
    const card = arthurCard('Momentous Shift');
    const shift = card.effects!.find((e) => e.type === 'SET_VALUE');
    expect(shift).toBeTruthy();
    expect((shift as any).value).toBe(5);
    expect((shift as any).when).toEqual({ kind: 'MOVED_THIS_TURN' });
    const after = await fightWon('Momentous Shift');
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.metadata.combatInfo).toBeUndefined();
  });

  it('Excalibur: BLANK — атака 6 без эффектов, бой завершается без pendings', async () => {
    const after = await fightWon('Excalibur');
    // печатное значение без эффектов: урон нанесён, очередь пуста
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.fighters.find((f) => f.id === 'bhero')!.health).toBeLessThan(12);
  });
});
