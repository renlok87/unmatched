// ============================================================
// PHASER MODULE - Главный файл экспорта
// ============================================================

export { PhaserGame } from './PhaserGame';
export { GameScene } from './scenes/GameScene';
export { MainGameScene } from './scenes/MainGameScene';
export { BootScene } from './scenes/BootScene';
export { UIScene } from './scenes/UIScene';

// Рендереры
export { BoardRenderer, HighlightColors } from './renderers/BoardRenderer';

// Сущности
export { FighterSprite } from './entities/FighterSprite';

// Обработка ввода
export { InputHandler } from './input/InputHandler';

// Камера
export { CameraController, CameraMode } from './camera/CameraController';

export type {
  PhaserGameConfig,
  PhaserGameState,
  FighterAssetConfig,
  CardAssetConfig,
  BoardAssetConfig,
  BoardSpaceAsset,
  PhaserGameEvent,
  ReactToPhaserEvent,
  SceneConfig,
  AnimationConfig,
  FighterAnimation,
  BoardConfig,
  Zone,
  Door,
  GameScene as IGameScene,
} from './types';

export {
  getFighterAsset,
  getCardAsset,
  getBoardAsset,
  loadHeroAssets,
  loadMultipleHeroAssets,
  loadBoardAssets,
  createFighterAnimations,
  FIGHTER_ASSETS,
  CARD_ASSETS,
  BOARD_ASSETS,
} from './assets/AssetLoader';

// Network - Backend Integration (Phase 4)
export { GameActions, gameActions, SubscriptionHandler } from './network';
export type {
  ActionResult,
  GameStateUpdate,
  GameEvent,
  TurnUpdate,
  SubscriptionCallbacks,
  ManeuverActionParams,
  AttackActionParams,
  DefenseActionParams,
} from './network';

// State - Backend Integration (Phase 4)
export { GameStateBridge } from './state';
export type {
  StateDiff,
  FighterDiff,
  CardDiff,
  GameAction,
  BridgeConfig,
} from './state';

// Hooks - Backend Integration (Phase 4)
export { useGameState, useGameActions } from './hooks';
export type {
  SyncStatus,
  ServerGameState,
  UseGameStateOptions,
  UseGameStateReturn,
  UseGameActionsOptions,
  UseGameActionsReturn,
} from './hooks';

// Systems - Replay System
export {
  ReplaySystem,
  createReplaySystem,
} from './systems';
export type {
  ReplayEvent,
  GameReplay,
  ReplayPlayerInfo,
  ReplayMetadata,
  ReplayState,
  ReplayConfig,
  ReplayEventType,
} from './systems';

// ============================================================
// COMBAT & EFFECTS - Phase 3
// ============================================================

// Анимации
export {
  FighterAnimations,
  CombatAnimations,
  AttackType,
  DEFAULT_FIGHTER_ANIMATION_CONFIG,
} from './animations';
export type {
  AnimationConfig as FighterAnimConfig,
  FighterAnimationConfig,
  CombatAnimationResult,
} from './animations';

// Эффекты
export {
  ParticleSystem,
  ScreenEffects,
} from './effects';
export type {
  ParticleConfig,
  DamageParticleConfig,
  HealParticleConfig,
  ShakeConfig,
  FlashConfig,
  FadeConfig,
  SlowMotionConfig,
} from './effects';

// UI
export {
  CombatUI,
  CombatLogEntryType,
} from './ui';
export type {
  CombatLogEntry,
  FloatingNumberConfig,
} from './ui';

// Расширенные спрайты
export { FighterSprite as EnhancedFighterSprite, FighterAnimationState } from './sprites';
export type { FighterSpriteConfig } from './sprites';
