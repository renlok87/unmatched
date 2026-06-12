/**
 * @deprecated B5: параллельный черновик интеграции с бэком; единый источник
 * истины — remoteGameStore + gameStateAdapter (B2). Кандидат на удаление.
 */
// ============================================================
// NETWORK MODULE - Экспорт всех сетевых компонентов
// ============================================================

export { GameActions, gameActions } from './GameActions';
export { SubscriptionHandler } from './SubscriptionHandler';

export type {
  ActionResult,
  ManeuverActionParams,
  AttackActionParams,
  DefenseActionParams,
  EndTurnActionParams,
  PassActionParams,
  ToggleDoorActionParams,
  MoveFighterActionParams,
} from './GameActions';

export type {
  GameStateUpdate,
  GameEvent,
  TurnUpdate,
  SubscriptionCallbacks,
} from './SubscriptionHandler';
