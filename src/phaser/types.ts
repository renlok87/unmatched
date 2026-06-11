// ============================================================
// TIPИ ДЛЯ PHASER ИНТЕГРАЦИИ
// ============================================================

import type { GameState, Fighter, CardInstance, Position } from '../core/models/types';

// ------------------------------------------------------------
// Конфигурация игры
// ------------------------------------------------------------

export interface PhaserGameConfig {
  gameId: string;
  width: number;
  height: number;
  parent: string;
  backgroundColor?: number;
}

// ------------------------------------------------------------
// Состояние Phaser игры
// ------------------------------------------------------------

export interface PhaserGameState {
  // Ссылка на GameState из движка
  gameState: GameState | null;

  // UI состояние
  selectedFighterId: string | null;
  selectedCardId: string | null;
  highlightedSpaces: Position[];

  // Настройки рендеринга
  showGrid: boolean;
  showZones: boolean;
  debugMode: boolean;
}

// ------------------------------------------------------------
// Конфигурация визуальных активов
// ------------------------------------------------------------

export interface FighterAssetConfig {
  id: string;
  name: string;
  spriteKey: string;
  portraitKey: string;
  scale: number;
  frameWidth: number;
  frameHeight: number;
}

export interface CardAssetConfig {
  id: string;
  name: string;
  spriteKey: string;
  backSpriteKey: string;
  width: number;
  height: number;
}

export interface BoardAssetConfig {
  id: string;
  name: string;
  backgroundKey: string;
  gridKey?: string;
  spaces: BoardSpaceAsset[];
}

export interface BoardSpaceAsset {
  position: Position;
  zones: string[];
  spriteKey?: string;
}

// ------------------------------------------------------------
// События между React и Phaser
// ------------------------------------------------------------

export type PhaserGameEvent =
  | { type: 'FIGHTER_CLICKED'; fighterId: string }
  | { type: 'SPACE_CLICKED'; position: Position }
  | { type: 'CARD_CLICKED'; cardId: string }
  | { type: 'ATTACK_CLICKED'; attackerId: string; targetId: string }
  | { type: 'PHASER_READY' }
  | { type: 'ANIMATION_COMPLETE'; animationId: string };

export type ReactToPhaserEvent =
  | { type: 'SELECT_FIGHTER'; fighterId: string | null }
  | { type: 'SELECT_CARD'; cardId: string | null }
  | { type: 'HIGHLIGHT_SPACES'; spaces: Position[] }
  | { type: 'MOVE_FIGHTER'; fighterId: string; position: Position }
  | { type: 'ATTACK'; attackerId: string; targetId: string; cardId: string }
  | { type: 'DEFEND'; cardId: string }
  | { type: 'UPDATE_STATE'; state: GameState }
  | { type: 'SHOW_DAMAGE'; fighterId: string; amount: number }
  | { type: 'PLAY_CARD_ANIMATION'; cardId: string };

// ------------------------------------------------------------
// Конфигурация сцены
// ------------------------------------------------------------

export interface SceneConfig {
  key: string;
  active?: boolean;
  visible?: boolean;
}

// ------------------------------------------------------------
// Анимации
// ------------------------------------------------------------

export interface AnimationConfig {
  key: string;
  frameRate?: number;
  repeat?: number;
  duration?: number;
}

export interface FighterAnimation {
  idle: string;
  walk: string;
  attack: string;
  hit: string;
  defeat: string;
}

// ------------------------------------------------------------
// Конфигурация игрового поля
// ------------------------------------------------------------

export interface BoardConfig {
  width: number;           // Ширина в клетках
  height: number;          // Высота в клетках
  cellSize: number;        // Размер клетки в пикселях
  zones: Zone[];           // Цветные зоны на поле
  doors: Door[];           // Двери на поле
}

export interface Zone {
  id: string;
  name: string;
  cells: Array<{ x: number; y: number }>;
  color: number;
  blocksMovement?: boolean;
}

export interface Door {
  id: string;
  position: { x: number; y: number };
  orientation: 'horizontal' | 'vertical';
  isOpen: boolean;
}

// ------------------------------------------------------------
// Типы для рендеринга
// ------------------------------------------------------------

export interface GameScene extends Phaser.Scene {
  boardConfig?: BoardConfig;
}

// ------------------------------------------------------------
// Цвета подсветки
// ------------------------------------------------------------

export enum HighlightColors {
  VALID_MOVE = 0x4ecca3,    // Зелёный для валидных ходов
  ATTACK_TARGET = 0xff6b6b, // Красный для целей атаки
  SELECTED = 0xffd93d,      // Жёлтый для выбранного
  HOVER = 0x6c5ce7,         // Фиолетовый для наведения
}

// ------------------------------------------------------------
// Типы для эффектов
// ------------------------------------------------------------

export interface ParticleEffectConfig {
  x: number;
  y: number;
  color: number;
  count: number;
  duration?: number;
}

export interface ScreenEffectConfig {
  shake?: {
    intensity: number;
    duration: number;
  };
  flash?: {
    color: number;
    duration: number;
  };
}

// ------------------------------------------------------------
// Расширенные события между React и Phaser для фазы 3
// ------------------------------------------------------------

export type ExtendedPhaserGameEvent = PhaserGameEvent |
  { type: 'COMBAT_ANIMATION_COMPLETE'; combatId: string }
  | { type: 'DAMAGE_APPLIED'; fighterId: string; damage: number }
  | { type: 'FIGHTER_DEFEATED'; fighterId: string }
  | { type: 'ZONE_ACTIVATED'; zoneId: string };

export type ExtendedReactToPhaserEvent = ReactToPhaserEvent |
  { type: 'PLAY_ATTACK_ANIMATION'; attackerId: string; targetId: string; attackType?: string; result?: CombatResult }
  | { type: 'PLAY_DEFEND_ANIMATION'; defenderId: string; blocked: boolean }
  | { type: 'PLAY_DEATH_ANIMATION'; fighterId: string }
  | { type: 'EMIT_PARTICLES'; config: ParticleEffectConfig }
  | { type: 'SCREEN_EFFECT'; config: ScreenEffectConfig }
  | { type: 'SHOW_FLOATING_NUMBER'; fighterId: string; value: number; isHeal?: boolean; isCritical?: boolean }
  | { type: 'ADD_LOG_ENTRY'; type: string; message: string; icon?: string };

export interface CombatResult {
  wasBlocked: boolean;
  damageDealt: number;
  wasCritical: boolean;
  attackerDied?: boolean;
  defenderDied?: boolean;
}
