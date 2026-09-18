import { AiTurnService } from './ai-turn.service';
import { AiDecisionService } from '../../game-engine/services/ai-decision.service';
import { GameActionExecutorService } from '../../game-engine/services/game-action-executor.service';
import { CardEffectExecutorService } from '../../game-engine/effects/card-effect-executor.service';
import { DeckManagementService } from '../../game-engine/services/deck-management.service';
import { GameRulesValidator } from '../../game-engine/validators/game-rules.validator';
import { CombatResolverService } from '../../game-engine/engine/combat-resolver.service';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { ValueModifierService } from '../../game-engine/engine/value-modifier.service';
import { HeroAbilityRegistry } from '../../game-engine/abilities/hero-ability-registry';
import { HandCard, CardType, FighterType, GamePhase, GameState, createEmptyBoardState } from '../../game-engine/models';

const card = (id: string): HandCard => ({ id, cardId: 'defense', name: id, nameEn: id, nameRu: id,
  cardType: CardType.DEFENSE, defenseValue: 2, isVisible: true });

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

function harness(initial: GameState) {
  let saved = initial;
  const snapshots: GameState[] = [];
  const events: string[] = [];
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
  const service = new AiTurnService(
    { game: { findUnique: async () => ({ mode: 'VS_AI', status: 'IN_PROGRESS', opponentId: 'ai' }) } } as any,
    { withLockOptions: async (_key: string, run: () => Promise<boolean>) => run() } as any,
    { loadState: async () => JSON.parse(JSON.stringify(saved)), saveState: async (_id: string, state: GameState) => {
      saved = JSON.parse(JSON.stringify(state));
      snapshots.push(saved);
    } } as any,
    { publishGameUpdate: async (_id: string, event: string) => { events.push(event); } } as any,
    executor, new AiDecisionService(adjacency),
  );
  return { run: () => service.maybeRunAiTurns(initial.gameId), state: () => saved, snapshots, events };
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
