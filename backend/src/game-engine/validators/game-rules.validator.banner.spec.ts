/**
 * bannerName-валидация (A6): именная карта играется только своим бойцом.
 * Реальный кейс: Medusa с гарпиями — Clutching Claws (banner Harpy) играет
 * только гарпия; банер 'Arthur' матчит бойца 'King Arthur'.
 */

import { GameRulesValidator, bannerAllows } from './game-rules.validator';
import { AdjacencyService } from '../engine/adjacency.service';
import { FighterType, GamePhase } from '../models';
import type { Fighter, GameState } from '../models';

const fighter = (id: string, name: string, ownerId = 'p1'): Fighter => ({
  id,
  ownerId,
  heroId: 'h1',
  name,
  type: FighterType.HERO,
  health: 10,
  maxHealth: 10,
  position: { x: 0, y: 0 },
  effects: [],
  hasSidekick: false,
});

const state = (fighters: Fighter[]): GameState =>
  ({
    gameId: 'g1',
    sequenceNumber: 1,
    phase: GamePhase.ACTION_MANEUVER,
    turnCount: 1,
    currentTurnPlayerId: 'p1',
    players: [],
    fighters,
    decks: {},
    discardPiles: {},
    handZones: {},
    boardState: { width: 5, height: 5, cells: [], doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date(), lastActionBy: 'p1', version: 1 },
  }) as unknown as GameState;

describe('bannerAllows', () => {
  it('точное имя и срез числового суффикса', () => {
    expect(bannerAllows('Harpy', fighter('f1', 'Harpy'))).toBe(true);
    expect(bannerAllows('Harpy', fighter('f1', 'Harpy 2'))).toBe(true);
    expect(bannerAllows('Harpy', fighter('f1', 'Medusa'))).toBe(false);
  });

  it("банер 'Arthur' матчит бойца 'King Arthur' (слово в имени)", () => {
    expect(bannerAllows('Arthur', fighter('f1', 'King Arthur'))).toBe(true);
    expect(bannerAllows('Merlin', fighter('f1', 'King Arthur'))).toBe(false);
  });

  it("нормализация числа: банер 'Harpy' матчит сайдкика 'Harpies' (реальные данные БД)", () => {
    expect(bannerAllows('Harpy', fighter('f1', 'Harpies'))).toBe(true);
    expect(bannerAllows('Harpy', fighter('f1', 'Harpies 2'))).toBe(true);
    expect(bannerAllows('Wolf', fighter('f1', 'Wolves'))).toBe(true);
  });

  it('регистронезависимо', () => {
    expect(bannerAllows('medusa', fighter('f1', 'Medusa'))).toBe(true);
  });
});

describe('GameRulesValidator.validateBanner', () => {
  const validator = new GameRulesValidator({} as AdjacencyService);
  const medusa = fighter('f-hero', 'Medusa');
  const harpy = fighter('f-sk0', 'Harpy 1');
  const gameState = state([medusa, harpy]);

  it("'Any'/пусто — играет любой боец", () => {
    expect(validator.validateBanner(gameState, { bannerName: 'Any' }, medusa).valid).toBe(true);
    expect(validator.validateBanner(gameState, {}, harpy).valid).toBe(true);
  });

  it('Clutching Claws (Harpy): Медуза — отказ BANNER_MISMATCH, гарпия — ок', () => {
    const card = { bannerName: 'Harpy', name: 'Clutching Claws' };
    const denied = validator.validateBanner(gameState, card, medusa);
    expect(denied.valid).toBe(false);
    expect(denied.code).toBe('BANNER_MISMATCH');
    expect(validator.validateBanner(gameState, card, harpy).valid).toBe(true);
  });

  it('неизвестный банер (грязные данные) — разрешить + warn', () => {
    const card = { bannerName: 'Nonexistent Dude', name: 'Weird Card' };
    expect(validator.validateBanner(gameState, card, medusa).valid).toBe(true);
  });
});
