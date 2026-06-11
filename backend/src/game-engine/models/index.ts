/**
 * Game Engine Models
 *
 * Единый модуль типов для game-engine.
 * Все типыGameState, Fighter, Card, Board и др.
 */

// GameState
export * from './game-state.model';

// Fighter
export * from './fighter.model';

// Card
export * from './card.model';

// Board
export * from './board.model';

// Player
export * from './player.model';

// Re-export commonly used types for convenience
export type { GameState, GameStatePlayer, GameStateMetadata } from './game-state.model';
export type { Fighter, FighterEffect, Position } from './fighter.model';
export type { Card, HandCard, DeckState, HandZone } from './card.model';
export type { BoardState, Cell, Door } from './board.model';

// Re-export enums as values
export { GamePhase } from './game-state.model';
export { FighterType } from './fighter.model';
export { CardType } from './card.model';

// Re-export helper functions
export { createEmptyBoardState, cellKey, parseCellKey } from './board.model';
