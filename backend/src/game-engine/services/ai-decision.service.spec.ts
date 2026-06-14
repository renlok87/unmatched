import { AiDecisionService } from './ai-decision.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { CardType, FighterType, GamePhase, createEmptyBoardState } from '../models';
import type { GameState, Card } from '../models';

const AI = 'ai';
const HUMAN = 'human';

// манхэттен — для ассертов «строго ближе к врагу»
const manhattan = (a: { x: number; y: number }, b: { x: number; y: number }): number =>
  Math.abs(a.x - b.x) + Math.abs(a.y - b.y);

const card = (id: string, type: CardType, extra: Partial<Card> = {}): any =>
  ({ id, cardId: id, name: id, nameEn: id, nameRu: id, cardType: type, isVisible: true, ...extra });

const fighter = (id: string, ownerId: string, x: number, y: number, extra: any = {}) => ({
  id, ownerId, heroId: `${ownerId}-h`, name: id, type: FighterType.HERO,
  health: 10, maxHealth: 12, position: { x, y }, effects: [], hasSidekick: false, ...extra,
});

const makeState = (over: Partial<GameState> = {}): GameState =>
  ({
    gameId: 'g', sequenceNumber: 1, phase: GamePhase.ACTION_MANEUVER, turnCount: 1,
    currentTurnPlayerId: AI,
    players: [
      { userId: HUMAN, heroId: 'hh', health: 10, maxHealth: 10, fighterIds: ['h1'], isAlive: true },
      { userId: AI, heroId: 'ah', health: 10, maxHealth: 10, fighterIds: ['a1'], isAlive: true },
    ],
    fighters: [fighter('h1', HUMAN, 0, 0), fighter('a1', AI, 5, 5, { attackType: 'melee' })],
    decks: {}, discardPiles: {},
    handZones: { [AI]: { cards: [], maxSize: 7 }, [HUMAN]: { cards: [], maxSize: 7 } },
    boardState: createEmptyBoardState(10, 10),
    metadata: { lastActionAt: new Date(), lastActionBy: AI, version: 1, actionsRemaining: 2 },
    ...over,
  }) as GameState;

describe('AiDecisionService', () => {
  const svc = new AiDecisionService(new AdjacencyService());

  it('ход бота, враг смежно + атак-карта → attack', () => {
    const st = makeState({
      fighters: [fighter('h1', HUMAN, 0, 0), fighter('a1', AI, 1, 0, { attackType: 'melee' })],
      handZones: { [AI]: { cards: [card('atk', CardType.ATTACK, { attackValue: 4 })], maxSize: 7 }, [HUMAN]: { cards: [], maxSize: 7 } },
    });
    const d = svc.decide(st, AI);
    expect(d).toEqual({ kind: 'attack', attackerId: 'a1', targetId: 'h1', cardId: 'atk' });
  });

  it('ход бота, выбирает атаку с бо́льшим attackValue', () => {
    const st = makeState({
      fighters: [fighter('h1', HUMAN, 0, 0), fighter('a1', AI, 1, 0, { attackType: 'melee' })],
      handZones: { [AI]: { cards: [card('w', CardType.ATTACK, { attackValue: 2 }), card('s', CardType.VERSATILE, { attackValue: 5 })], maxSize: 7 }, [HUMAN]: { cards: [], maxSize: 7 } },
    });
    expect(svc.decide(st, AI)).toMatchObject({ kind: 'attack', cardId: 's' });
  });

  it('атака: равный attackValue (ATTACK vs VERSATILE) → выбран ATTACK (не тратим VERSATILE)', () => {
    const st = makeState({
      fighters: [fighter('h1', HUMAN, 0, 0), fighter('a1', AI, 1, 0, { attackType: 'melee' })],
      handZones: {
        [AI]: {
          cards: [
            card('vers', CardType.VERSATILE, { attackValue: 4 }),
            card('atk', CardType.ATTACK, { attackValue: 4 }),
          ],
          maxSize: 7,
        },
        [HUMAN]: { cards: [], maxSize: 7 },
      },
    });
    expect(svc.decide(st, AI)).toMatchObject({ kind: 'attack', cardId: 'atk' });
  });

  it('ход бота, враг далеко → manoeuvre на всю дальность движения к врагу', () => {
    const d = svc.decide(makeState(), AI);
    expect(d?.kind).toBe('maneuver');
    if (d?.kind === 'maneuver') {
      expect(d.fighterId).toBe('a1');
      const start = { x: 5, y: 5 };
      const enemy = { x: 0, y: 0 };
      const cell = d.path[0];
      // клетка СТРОГО ближе к врагу, чем старт…
      expect(manhattan(cell, enemy)).toBeLessThan(manhattan(start, enemy));
      // …и в пределах movement (дефолт 2): BFS-стоимость от старта ≤ 2
      expect(manhattan(cell, start)).toBeGreaterThanOrEqual(1);
      expect(manhattan(cell, start)).toBeLessThanOrEqual(2);
    }
  });

  it('actionsRemaining 0 → endTurn', () => {
    const st = makeState({ metadata: { actionsRemaining: 0 } as any });
    expect(svc.decide(st, AI)).toEqual({ kind: 'endTurn' });
  });

  it('не ход бота → null', () => {
    expect(svc.decide(makeState({ currentTurnPlayerId: HUMAN }), AI)).toBeNull();
  });

  it('GAME_OVER → null', () => {
    expect(svc.decide(makeState({ phase: GamePhase.GAME_OVER }), AI)).toBeNull();
  });

  it('бой, бот-защитник без сыгранной защиты + есть DEFENSE → defense', () => {
    const st = makeState({
      phase: GamePhase.COMBAT,
      handZones: { [AI]: { cards: [card('def', CardType.DEFENSE, { defenseValue: 3 })], maxSize: 7 }, [HUMAN]: { cards: [], maxSize: 7 } },
      metadata: { combatInfo: { attackerId: 'h1', defenderId: AI }, actionsRemaining: 2 } as any,
    });
    expect(svc.decide(st, AI)).toEqual({ kind: 'defense', cardId: 'def' });
  });

  it('бой, защита: равный defenseValue (DEFENSE vs VERSATILE) → выбран DEFENSE', () => {
    const st = makeState({
      phase: GamePhase.COMBAT,
      handZones: {
        [AI]: {
          cards: [
            card('vers', CardType.VERSATILE, { defenseValue: 3 }),
            card('def', CardType.DEFENSE, { defenseValue: 3 }),
          ],
          maxSize: 7,
        },
        [HUMAN]: { cards: [], maxSize: 7 },
      },
      metadata: { combatInfo: { attackerId: 'h1', defenderId: AI }, actionsRemaining: 2 } as any,
    });
    expect(svc.decide(st, AI)).toEqual({ kind: 'defense', cardId: 'def' });
  });

  it('бой, бот-защитник уже сыграл защиту → resolveCombat', () => {
    const st = makeState({
      phase: GamePhase.COMBAT,
      metadata: { combatInfo: { attackerId: 'h1', defenderId: AI, defenderCardId: 'def' }, actionsRemaining: 2 } as any,
    });
    expect(svc.decide(st, AI)).toEqual({ kind: 'resolveCombat' });
  });

  it('бой, бот-защитник без карт защиты → resolveCombat (без защиты)', () => {
    const st = makeState({
      phase: GamePhase.COMBAT,
      metadata: { combatInfo: { attackerId: 'h1', defenderId: AI }, actionsRemaining: 2 } as any,
    });
    expect(svc.decide(st, AI)).toEqual({ kind: 'resolveCombat' });
  });

  it('бой, бот — атакующий (защищается человек) → null (ждём)', () => {
    const st = makeState({
      phase: GamePhase.COMBAT,
      metadata: { combatInfo: { attackerId: 'a1', defenderId: HUMAN }, actionsRemaining: 1 } as any,
    });
    expect(svc.decide(st, AI)).toBeNull();
  });

  it('CHOOSE_ONE pending бота → resolveChoose выгодной опции (HEAL > DRAW)', () => {
    const st = makeState({
      metadata: {
        actionsRemaining: 2,
        pendingEffects: [
          {
            id: 'pe1', type: 'CHOOSE_ONE', playerId: AI, chooseCount: 1,
            options: [{ index: 0, label: 'Draw 1 card' }, { index: 1, label: 'Recover 2 health' }],
            optionEffects: [[{ type: 'DRAW_CARD' }], [{ type: 'HEAL' }]],
          },
        ],
      } as any,
    });
    expect(svc.decide(st, AI)).toEqual({ kind: 'resolveChoose', effectId: 'pe1', optionIndex: 1 });
  });

  it('MOVE pending бота → resolveMove клеткой ближе к врагу (в пределах value)', () => {
    const st = makeState({
      fighters: [fighter('h1', HUMAN, 0, 0), fighter('a1', AI, 5, 5)],
      metadata: {
        actionsRemaining: 2,
        pendingEffects: [{ id: 'pe2', type: 'MOVE', playerId: AI, value: 3 }],
      } as any,
    });
    const d = svc.decide(st, AI);
    expect(d?.kind).toBe('resolveMove');
    if (d?.kind === 'resolveMove') {
      expect(d.fighterId).toBe('a1');
      const start = { x: 5, y: 5 };
      const enemy = { x: 0, y: 0 };
      const cell = { x: d.x, y: d.y };
      // клетка СТРОГО ближе к врагу, чем старт…
      expect(manhattan(cell, enemy)).toBeLessThan(manhattan(start, enemy));
      // …и не дальше pending.value (3) от старта
      expect(manhattan(cell, start)).toBeGreaterThanOrEqual(1);
      expect(manhattan(cell, start)).toBeLessThanOrEqual(3);
    }
  });
});
