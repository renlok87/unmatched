import { GameActionExecutorService } from '../../game-engine/services/game-action-executor.service';
import { DeckManagementService } from '../../game-engine/services/deck-management.service';
import { CardEffectExecutorService } from '../../game-engine/effects/card-effect-executor.service';
import { GameRulesValidator } from '../../game-engine/validators/game-rules.validator';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { ValueModifierService } from '../../game-engine/engine/value-modifier.service';
import { CombatResolverService } from '../../game-engine/engine/combat-resolver.service';
import { HeroAbilityRegistry } from '../../game-engine/abilities/hero-ability-registry';
import { MovementService } from '../../game-engine/engine/movement.service';
import { AStarService, PathCacheService } from '../../game-engine/movement';
import { Card, CardType, FighterType, GamePhase, GameState } from '../../game-engine/models';

export function s03Card(id: string): Card {
  return { id, cardId: 'definition', name: id, nameEn: id, nameRu: id,
    cardType: CardType.VERSATILE, boostValue: 3, effects: [] } as Card;
}
export function s03Fixture(hand = 0, actions = 2): GameState {
  return {
    gameId: 's03', sequenceNumber: 10, phase: GamePhase.ACTION_MANEUVER,
    turnCount: 1, currentTurnPlayerId: 'a',
    players: ['a', 'b'].map(userId => ({ userId, heroId: userId, health: 10,
      maxHealth: 10, fighterIds: [userId], isAlive: true })),
    fighters: ['a', 'b', 'helper'].map((id, i) => ({ id, ownerId: i === 1 ? 'b' : 'a',
      heroId: i === 1 ? 'b' : 'a', name: id, type: i === 2 ? FighterType.MINION : FighterType.HERO,
      health: 10, maxHealth: 10, position: { x: i === 1 ? 7 : 0, y: i === 2 ? 1 : 0 },
      effects: [], hasSidekick: false, movement: 2 })),
    decks: Object.fromEntries(['a', 'b'].map(id => [id, { cards: [], drawPile: [s03Card(id + '-new'), s03Card(id + '-next')] }])),
    handZones: { a: { cards: Array.from({ length: hand }, (_, i) => ({ ...s03Card('h' + i), isVisible: true })), maxSize: 7 },
      b: { cards: [], maxSize: 7 } }, discardPiles: { a: [], b: [] },
    boardState: { width: 8, height: 2, cells: Array.from({ length: 2 }, (_, y) =>
      Array.from({ length: 8 }, (_, x) => ({ x, y, type: 'normal' }))), doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date(0), lastActionBy: 'a', version: 1, actionsRemaining: actions },
  } as GameState;
}
export function s03Engine() {
  const metrics = { measureServiceDuration: async (_a: string, _b: string, run: () => unknown) => run(),
    measureValidation: async (_a: string, run: () => unknown) => run(), incrementGameAction: () => {}, incrementError: () => {} } as any;
  const adjacency = new AdjacencyService();
  const values = new ValueModifierService();
  const decks = new DeckManagementService();
  const registry = new HeroAbilityRegistry();
  const effects = new CardEffectExecutorService(values, metrics, adjacency, decks);
  const executor = new GameActionExecutorService(new GameRulesValidator(adjacency),
    new CombatResolverService(registry, metrics), new MovementService(new AStarService(), new PathCacheService()), values, adjacency, metrics, decks, effects, registry);
  return { executor, effects, registry };
}
