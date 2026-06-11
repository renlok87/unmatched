// ============================================================
// HOOKS MODULE - Экспорт всех React хуков
// ============================================================

export { useGameState } from './useGameSync';
export { useGameActions } from './useGameActions';

export type {
  SyncStatus,
  ServerGameState,
  UseGameStateOptions,
  UseGameStateReturn,
} from './useGameSync';

export type {
  ActionResult,
  ManeuverParams,
  AttackParams,
  DefenseParams,
  MoveFighterParams,
  UseGameActionsOptions,
  UseGameActionsReturn,
} from './useGameActions';
