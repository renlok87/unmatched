/**
 * Game Engine Models
 *
 * Единый модуль типов для game-engine.
 * Все типыGameState, Fighter, Card, Board и др.
 *
 * P3 (унификация моделей): это КАНОНИЧЕСКОЕ семейство типов состояния.
 * games/game-state.service.ts и games/dto (GamePhase) только ре-экспортируют их.
 *
 * Осознанно ВНЕ скоупа унификации (задокументировано, не чинилось):
 * - Дубли моделей на фронте: src/store/remoteGameStore.ts (ждёт spaces[],
 *   бэк шлёт cells-сетку), src/phaser/types.ts, src/core/models/Board.ts;
 * - Cell.zone одиночный — мультизонность zones[1..] из Board.cells теряется
 *   (см. buildBoardState в games/services/game-initialization.service.ts);
 * - CombatResult без attackerDamage/defenderDamage — 2 TODO-каста в
 *   game-action-executor.service.ts (пробел типа, не стыковки моделей);
 * - serialize() не сохраняет metadata.combatInfo/passCount/winnerId в wire-формат
 *   (m: la/lb/v/ar — actionsRemaining сериализуется) — бой переживает рестарт
 *   только через Redis-кеш (легаси-поведение).
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
export type { GameState, GameStatePlayer, GameStateMetadata, CombatState } from './game-state.model';
export type { Fighter, FighterEffect, Position } from './fighter.model';
export type { Card, HandCard, DeckState, HandZone } from './card.model';
export type { BoardState, Cell, Door } from './board.model';

// Re-export enums as values
export { GamePhase } from './game-state.model';
export { FighterType } from './fighter.model';
export { CardType } from './card.model';

// Re-export helper functions
export { createEmptyBoardState, cellKey, parseCellKey } from './board.model';
