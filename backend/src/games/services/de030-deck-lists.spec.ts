/** DE-030 (W-19; 01 F-05, D-DE-05; 02 SD-29, SD-41; QA-005): публичный состав колод для панели «Колода».
 *  - состав сгруппирован по каталожному cardId, копии — count; instance-id и порядок добора не выдаются;
 *  - ответ одинаков для любого порядка drawPile и не зависит от руки/сброса;
 *  - запрос только для участника; проекция снапшота по-прежнему не отдаёт порядок колоды и id карт руки соперника. */
import { GameStateService } from '../game-state.service';
import { GameResolver } from '../game.resolver';
import { GamePhase, CardType, FighterType } from '../../game-engine/models';
import type { GameState } from '../game-state.service';

function makeService() {
  const prisma: any = {
    gamePlayer: { findUnique: async () => null },
    gameState: { findUnique: async () => null, upsert: async ({ create }: any) => create },
  };
  const redis: any = { getJson: async () => null, setJsonex: async () => 'OK', del: async () => 1 };
  return new GameStateService(prisma, redis, { publishGameUpdate: async () => undefined } as any);
}

const catalog = {
  gaze: { cardId: 'cat-gaze', name: 'Gaze of Stone', nameEn: 'Gaze of Stone', nameRu: 'Взгляд', cardType: CardType.SCHEME, text: 'Deal 8 damage.', bannerName: 'Medusa' },
  hiss: { cardId: 'cat-hiss', name: 'Hiss', nameEn: 'Hiss', nameRu: 'Шипение', cardType: CardType.VERSATILE, attackValue: 3, defenseValue: 3, boostValue: 2, bannerName: 'Any' },
  snipe: { cardId: 'cat-snipe', name: 'Snipe', nameEn: 'Snipe', nameRu: 'Выстрел', cardType: CardType.ATTACK, attackValue: 4, boostValue: 1, bannerName: 'Medusa' },
  feint: { cardId: 'cat-feint', name: 'Feint', nameEn: 'Feint', nameRu: 'Финт', cardType: CardType.VERSATILE, attackValue: 2, defenseValue: 2, boostValue: 2 },
  block: { cardId: 'cat-block', name: 'Block', nameEn: 'Block', nameRu: 'Блок', cardType: CardType.DEFENSE, defenseValue: 4, boostValue: 'X' as any },
};

/** Copies as the server deals them: `<cardId>::<copy>` instance ids. */
function copies(card: any, n: number, first = 0): any[] {
  return Array.from({ length: n }, (_, i) => ({ ...card, id: `${card.cardId}::${first + i}`, effects: [] }));
}

function fixture(drawOrder: 'a' | 'b'): GameState {
  const aCards = [...copies(catalog.gaze, 1), ...copies(catalog.hiss, 3), ...copies(catalog.snipe, 2)];
  const bCards = [...copies(catalog.feint, 3, 10), ...copies(catalog.block, 2)];
  const aDraw = drawOrder === 'a' ? [aCards[1], aCards[4], aCards[2]] : [aCards[2], aCards[1], aCards[4]];
  const bDraw = drawOrder === 'a' ? [bCards[0], bCards[3]] : [bCards[3], bCards[0]];
  return {
    gameId: 'g-de030', sequenceNumber: 7, phase: GamePhase.ACTION_MANEUVER, turnCount: 2, currentTurnPlayerId: 'a',
    players: ['a', 'b'].map((userId) => ({ userId, heroId: userId, health: 10, maxHealth: 10, fighterIds: [userId], isAlive: true })),
    fighters: [
      { id: 'fA', ownerId: 'a', heroId: 'ha', name: 'Medusa', type: FighterType.HERO, health: 16, maxHealth: 16, position: { x: 0, y: 0 }, effects: [], hasSidekick: false },
      { id: 'fB', ownerId: 'b', heroId: 'hb', name: 'King Arthur', type: FighterType.HERO, health: 18, maxHealth: 18, position: { x: 1, y: 0 }, effects: [], hasSidekick: false },
    ] as any,
    decks: {
      a: { cards: aCards, drawPile: aDraw, topCard: aDraw[0] },
      b: { cards: bCards, drawPile: bDraw, topCard: bDraw[0] },
    },
    discardPiles: { a: [aCards[0]], b: [bCards[1]] },
    handZones: {
      a: { cards: [{ ...aCards[3], isVisible: false }, { ...aCards[5], isVisible: false }], maxSize: 7 },
      b: { cards: [{ ...bCards[2], isVisible: false }, { ...bCards[4], isVisible: false }], maxSize: 7 },
    },
    boardState: { width: 2, height: 1, cells: [[{ x: 0, y: 0, type: 'normal' }, { x: 1, y: 0, type: 'normal' }]], doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date(), lastActionBy: 'a', version: 1, actionsRemaining: 2 },
  } as any;
}

describe('DE-030 gameDeckLists: public deck composition', () => {
  it('groups copies by catalog id with count, both players, no instance ids', () => {
    const lists = makeService().publicDeckLists(fixture('a'));
    expect(lists.map((l) => l.playerId)).toEqual(['a', 'b']);
    const a = lists[0];
    expect(a.total).toBe(6);
    expect(a.cards.map((c) => [c.cardId, c.count])).toEqual([
      ['cat-snipe', 2], // ATTACK
      ['cat-hiss', 3], // VERSATILE
      ['cat-gaze', 1], // SCHEME
    ]);
    const hiss = a.cards.find((c) => c.cardId === 'cat-hiss')!;
    expect(hiss).toMatchObject({ name: 'Hiss', nameRu: 'Шипение', cardType: 'VERSATILE', attackValue: 3, defenseValue: 3, boostValue: 2, bannerName: 'Any' });
    expect(a.cards.find((c) => c.cardId === 'cat-gaze')!.text).toBe('Deal 8 damage.');
    const b = lists[1];
    expect(b.total).toBe(5);
    expect(b.cards.map((c) => [c.cardId, c.count])).toEqual([['cat-feint', 3], ['cat-block', 2]]);
    // a non-numeric printed value is "no value", never a broken Int
    expect(b.cards.find((c) => c.cardId === 'cat-block')!.boostValue).toBeNull();
    const raw = JSON.stringify(lists);
    expect(raw).not.toContain('::'); // no instance id of any copy
    expect(raw).not.toContain('isVisible');
  });

  it('is the same for any draw order and carries no hand / discard state (QA-005)', () => {
    const service = makeService();
    const one = service.publicDeckLists(fixture('a'));
    const two = service.publicDeckLists(fixture('b'));
    expect(two).toEqual(one);
    const moved = fixture('a');
    const drained: GameState = {
      ...moved,
      decks: { ...moved.decks, a: { ...moved.decks.a, drawPile: [], topCard: undefined } },
      discardPiles: { a: [...moved.decks.a.cards], b: [] },
      handZones: { ...moved.handZones, a: { cards: [], maxSize: 7 } },
    } as any;
    expect(service.publicDeckLists(drained)).toEqual(one);
  });

  it('the snapshot projection still hides the deck order and the opponent hand ids', () => {
    const service = makeService();
    const state = fixture('a');
    const viewB = JSON.stringify(service.filterPrivateData(state, 'b'));
    for (const card of state.handZones.a.cards) expect(viewB).not.toContain(card.id);
    for (const card of state.decks.a.drawPile) expect(viewB).not.toContain(card.id);
    for (const card of state.decks.b.drawPile) expect(viewB).not.toContain(card.id);
    // the deck list adds no instance id the projection hides
    const lists = JSON.stringify(service.publicDeckLists(state));
    for (const card of [...state.handZones.a.cards, ...state.decks.a.drawPile]) expect(lists).not.toContain(card.id);
  });

  it('the query answers participants only', async () => {
    const service = makeService();
    const state = fixture('a');
    (service as any).loadState = async () => state;
    const gameService: any = {
      requireParticipation: async (_gameId: string, userId: string) => {
        if (userId !== 'a' && userId !== 'b') throw new Error('Access denied');
      },
    };
    const resolver = new GameResolver(gameService, service);
    const lists = await resolver.gameDeckLists('g-de030', { id: 'b' });
    expect(lists.map((l) => l.playerId)).toEqual(['a', 'b']);
    await expect(resolver.gameDeckLists('g-de030', { id: 'z' })).rejects.toThrow('Access denied');
  });
});
