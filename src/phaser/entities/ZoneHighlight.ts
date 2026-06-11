// ============================================================
// ZONE HIGHLIGHT - Визуальная подсветка зон на игровом поле
// ============================================================

import Phaser from 'phaser';
import type { GameScene } from '../renderers/BoardRenderer';

// ------------------------------------------------------------
// Типы зон для подсветки
// ------------------------------------------------------------

/**
 * Тип зоны для подсветки
 */
export enum ZoneHighlightType {
  ATTACK = 'attack',       // Зона атаки (красная)
  MOVEMENT = 'movement',   // Зона перемещения (зелёная)
  ABILITY = 'ability',     // Зона способности (синяя)
  EFFECT = 'effect',       // Зона эффектов (фиолетовая)
  DANGER = 'danger',       // Опасная зона (оранжевая)
  SAFE = 'safe',           // Безопасная зона (голубая)
}

// ------------------------------------------------------------
// Конфигурация подсветки
// ------------------------------------------------------------

/**
 * Конфигурация цвета для типа зоны
 */
interface ZoneColorConfig {
  color: number;           // Основной цвет
  borderColor: number;     // Цвет границы
  alpha: number;           // Прозрачность заливки
  borderAlpha: number;     // Прозрачность границы
}

/**
 * Карта цветов для разных типов зон
 */
const ZONE_COLOR_MAP: Record<ZoneHighlightType, ZoneColorConfig> = {
  [ZoneHighlightType.ATTACK]: {
    color: 0xff6b6b,
    borderColor: 0xff4444,
    alpha: 0.35,
    borderAlpha: 0.8,
  },
  [ZoneHighlightType.MOVEMENT]: {
    color: 0x4ecca3,
    borderColor: 0x44ddaa,
    alpha: 0.3,
    borderAlpha: 0.7,
  },
  [ZoneHighlightType.ABILITY]: {
    color: 0x4488ff,
    borderColor: 0x3366ee,
    alpha: 0.3,
    borderAlpha: 0.7,
  },
  [ZoneHighlightType.EFFECT]: {
    color: 0x9966ff,
    borderColor: 0x8855ee,
    alpha: 0.25,
    borderAlpha: 0.6,
  },
  [ZoneHighlightType.DANGER]: {
    color: 0xff9933,
    borderColor: 0xff6600,
    alpha: 0.35,
    borderAlpha: 0.8,
  },
  [ZoneHighlightType.SAFE]: {
    color: 0x66ccff,
    borderColor: 0x44aadd,
    alpha: 0.2,
    borderAlpha: 0.6,
  },
};

// ------------------------------------------------------------
// Конфигурация анимации
// ------------------------------------------------------------

/**
 * Конфигурация анимации подсветки
 */
export interface ZoneAnimationConfig {
  duration: number;        // Длительность появления
  ease?: string;           // Функция easing
  scale?: { from: number; to: number };  // Масштабирование
  pulse?: boolean;         // Пульсация после появления
  pulseSpeed?: number;     // Скорость пульсации
}

/**
 * Конфигурация зоны
 */
export interface ZoneConfig {
  cells: Array<{ x: number; y: number }>;  // Клетки зоны
  type: ZoneHighlightType;                  // Тип подсветки
  id?: string;                              // Опциональный ID зоны
}

// ------------------------------------------------------------
// Класс подсветки отдельной клетки
// ------------------------------------------------------------

/**
 * Спрайт подсветки отдельной клетки
 */
class CellHighlight extends Phaser.GameObjects.Container {
  private background: Phaser.GameObjects.Rectangle;
  private border: Phaser.GameObjects.Rectangle;
  private corners: Phaser.GameObjects.Graphics[] = [];
  private pulseTween?: Phaser.Tweens.Tween;
  private config: ZoneColorConfig;

  constructor(
    scene: GameScene,
    x: number,
    y: number,
    cellSize: number,
    colorConfig: ZoneColorConfig
  ) {
    super(scene, x, y);
    this.config = colorConfig;

    // Создаём фон подсветки
    const padding = 2;
    this.background = new Phaser.GameObjects.Rectangle(
      scene,
      0,
      0,
      cellSize - padding * 2,
      cellSize - padding * 2,
      colorConfig.color,
      0 // Начальная alpha для анимации
    );
    this.add(this.background);

    // Создаём границу
    this.border = new Phaser.GameObjects.Rectangle(
      scene,
      0,
      0,
      cellSize - padding * 2,
      cellSize - padding * 2
    );
    this.border.setStrokeStyle(2, colorConfig.borderColor, 0);
    this.add(this.border);

    // Создаём угловые маркеры для более стильного вида
    this.createCorners(cellSize, colorConfig.borderColor);

    // Устанавливаем глубину
    this.setDepth(90);
  }

  /**
   * Создаёт угловые маркеры
   */
  private createCorners(cellSize: number, color: number): void {
    const cornerSize = 6;
    const offset = (cellSize - 4) / 2 - cornerSize / 2;

    const corners = [
      { x: -offset, y: -offset, rotation: 0 },
      { x: offset, y: -offset, rotation: Math.PI / 2 },
      { x: offset, y: offset, rotation: Math.PI },
      { x: -offset, y: offset, rotation: -Math.PI / 2 },
    ];

    corners.forEach(corner => {
      const graphics = new Phaser.GameObjects.Graphics(this.scene);
      graphics.lineStyle(2, color, 0);
      graphics.beginPath();
      graphics.moveTo(-cornerSize / 2, -cornerSize / 4);
      graphics.lineTo(-cornerSize / 2, -cornerSize / 2);
      graphics.lineTo(-cornerSize / 4, -cornerSize / 2);
      graphics.strokePath();
      graphics.setPosition(corner.x, corner.y);
      graphics.setRotation(corner.rotation);
      this.add(graphics);
      this.corners.push(graphics);
    });
  }

  /**
   * Показывает подсветку с анимацией
   */
  show(animationConfig?: ZoneAnimationConfig): Promise<void> {
    return new Promise(resolve => {
      const config = animationConfig || {
        duration: 200,
        scale: { from: 0.8, to: 1 },
        ease: 'Back.Out',
      };

      // Анимируем появление фона
      this.scene.tweens.add({
        targets: this.background,
        alpha: this.config.alpha,
        scaleX: config.scale?.from ?? 0.8,
        scaleY: config.scale?.from ?? 0.8,
        duration: 0,
      });

      this.scene.tweens.add({
        targets: this.background,
        alpha: this.config.alpha,
        scaleX: config.scale?.to ?? 1,
        scaleY: config.scale?.to ?? 1,
        duration: config.duration,
        ease: config.ease as Phaser.Types.Tweens.EaseFunction || Phaser.Math.Easing.Back.Out,
      });

      // Анимируем появление границы
      this.scene.tweens.add({
        targets: this.border,
        alpha: this.config.borderAlpha,
        duration: config.duration,
        delay: 50,
        ease: config.ease as Phaser.Types.Tweens.EaseFunction || Phaser.Math.Easing.Back.Out,
      });

      // Анимируем появление углов
      this.corners.forEach((corner, index) => {
        this.scene.tweens.add({
          targets: corner,
          alpha: this.config.borderAlpha,
          duration: config.duration,
          delay: 50 + index * 20,
          ease: config.ease as Phaser.Types.Tweens.EaseFunction || Phaser.Math.Easing.Back.Out,
        });
      });

      // Запускаем пульсацию если нужно
      if (config.pulse) {
        this.startPulse(config.pulseSpeed ?? 1000);
      }

      this.scene.time.delayedCall(config.duration, () => resolve());
    });
  }

  /**
   * Скрывает подсветку с анимацией
   */
  hide(duration: number = 150): Promise<void> {
    return new Promise(resolve => {
      // Останавливаем пульсацию
      if (this.pulseTween) {
        this.pulseTween.destroy();
        this.pulseTween = undefined;
      }

      // Анимируем исчезновение
      this.scene.tweens.add({
        targets: [this.background, this.border, ...this.corners],
        alpha: 0,
        scale: 0.8,
        duration: duration,
        ease: Phaser.Math.Easing.Quadratic.In,
        onComplete: () => {
          this.destroy();
          resolve();
        },
      });
    });
  }

  /**
   * Запускает пульсацию
   */
  private startPulse(speed: number): void {
    if (this.pulseTween) {
      this.pulseTween.destroy();
    }

    this.pulseTween = this.scene.tweens.add({
      targets: this.background,
      alpha: { from: this.config.alpha, to: this.config.alpha * 0.5 },
      scale: { from: 1, to: 1.05 },
      duration: speed,
      yoyo: true,
      repeat: -1,
      ease: Phaser.Math.Easing.Sine.InOut,
    });
  }

  /**
   * Останавливает пульсацию
   */
  stopPulse(): void {
    if (this.pulseTween) {
      this.pulseTween.destroy();
      this.pulseTween = undefined;
    }
  }

  /**
   * Обновляет цвет подсветки
   */
  updateColor(colorConfig: ZoneColorConfig): void {
    this.config = colorConfig;
    this.background.fillColor = colorConfig.color;
    this.background.alpha = colorConfig.alpha;
    this.border.strokeColor = colorConfig.borderColor;
    this.border.alpha = colorConfig.borderAlpha;

    this.corners.forEach(corner => {
      corner.clear();
      corner.lineStyle(2, colorConfig.borderColor, colorConfig.borderAlpha);
      corner.beginPath();
      corner.moveTo(-3, -1.5);
      corner.lineTo(-3, -3);
      corner.lineTo(-1.5, -3);
      corner.strokePath();
    });
  }
}

// ------------------------------------------------------------
// Основной класс ZoneHighlight
// ------------------------------------------------------------

/**
 * Компонент подсветки зон на игровом поле
 *
 * Используется для визуального отображения:
 * - Зон атаки (красным)
 * - Зон перемещения (зелёным)
 * - Зон способностей (синим)
 * - Других типов зон
 *
 * Интегрируется с BoardRenderer для отображения
 * валидных действий и областей действия способностей.
 */
export class ZoneHighlight {
  private scene: GameScene;
  private cellSize: number;
  private highlights: Map<string, CellHighlight> = new Map();
  private zoneGroups: Map<string, Set<string>> = new Map();

  // Конфигурация анимации по умолчанию
  private defaultAnimationConfig: ZoneAnimationConfig = {
    duration: 200,
    ease: 'Back.Out',
    scale: { from: 0.8, to: 1 },
    pulse: false,
  };

  constructor(scene: GameScene, cellSize: number = 64) {
    this.scene = scene;
    this.cellSize = cellSize;
  }

  // ============================================================
  // ОСНОВНЫЕ МЕТОДЫ
  // ============================================================

  /**
   * Показывает подсветку для указанных клеток
   *
   * @param cells - Массив клеток для подсветки
   * @param type - Тип зоны (определяет цвет)
   * @param zoneId - Опциональный ID группы зон
   * @param animationConfig - Опциональная конфигурация анимации
   */
  async showZone(
    cells: Array<{ x: number; y: number }>,
    type: ZoneHighlightType,
    zoneId?: string,
    animationConfig?: Partial<ZoneAnimationConfig>
  ): Promise<void> {
    const config = { ...this.defaultAnimationConfig, ...animationConfig };
    const colorConfig = ZONE_COLOR_MAP[type];
    const groupKey = zoneId || `zone-${Date.now()}`;
    const cellKeys: Set<string> = new Set();

    // Удаляем существующую подсветку для этих клеток
    cells.forEach(cell => {
      const key = this.getCellKey(cell.x, cell.y);
      this.removeCellHighlight(key);
      cellKeys.add(key);
    });

    // Сохраняем группу
    this.zoneGroups.set(groupKey, cellKeys);

    // Создаём новую подсветку
    const promises = cells.map(cell => {
      const key = this.getCellKey(cell.x, cell.y);
      const worldX = cell.x * this.cellSize + this.cellSize / 2;
      const worldY = cell.y * this.cellSize + this.cellSize / 2;

      const highlight = new CellHighlight(
        this.scene,
        worldX,
        worldY,
        this.cellSize,
        colorConfig
      );

      this.scene.add.existing(highlight);
      this.highlights.set(key, highlight);

      return highlight.show(config);
    });

    await Promise.all(promises);
  }

  /**
   * Показывает зоны атаки (красные)
   */
  async showAttackZone(
    cells: Array<{ x: number; y: number }>,
    zoneId?: string,
    pulse: boolean = true
  ): Promise<void> {
    await this.showZone(cells, ZoneHighlightType.ATTACK, zoneId, {
      pulse,
      pulseSpeed: 800,
    });
  }

  /**
   * Показывает зоны перемещения (зелёные)
   */
  async showMovementZone(
    cells: Array<{ x: number; y: number }>,
    zoneId?: string
  ): Promise<void> {
    await this.showZone(cells, ZoneHighlightType.MOVEMENT, zoneId);
  }

  /**
   * Показывает зоны способностей (синие)
   */
  async showAbilityZone(
    cells: Array<{ x: number; y: number }>,
    zoneId?: string,
    pulse: boolean = false
  ): Promise<void> {
    await this.showZone(cells, ZoneHighlightType.ABILITY, zoneId, {
      pulse,
      pulseSpeed: 1200,
    });
  }

  /**
   * Показывает зоны эффектов (фиолетовые)
   */
  async showEffectZone(
    cells: Array<{ x: number; y: number }>,
    zoneId?: string,
    pulse: boolean = true
  ): Promise<void> {
    await this.showZone(cells, ZoneHighlightType.EFFECT, zoneId, {
      pulse,
      pulseSpeed: 1000,
    });
  }

  /**
   * Показывает опасные зоны (оранжевые)
   */
  async showDangerZone(
    cells: Array<{ x: number; y: number }>,
    zoneId?: string,
    pulse: boolean = true
  ): Promise<void> {
    await this.showZone(cells, ZoneHighlightType.DANGER, zoneId, {
      pulse,
      pulseSpeed: 600,
    });
  }

  /**
   * Показывает безопасные зоны (голубые)
   */
  async showSafeZone(
    cells: Array<{ x: number; y: number }>,
    zoneId?: string
  ): Promise<void> {
    await this.showZone(cells, ZoneHighlightType.SAFE, zoneId);
  }

  /**
   * Показывает несколько зон одновременно
   */
  async showMultipleZones(zones: ZoneConfig[]): Promise<void> {
    const promises = zones.map(zone =>
      this.showZone(zone.cells, zone.type, zone.id)
    );
    await Promise.all(promises);
  }

  // ============================================================
  // МЕТОДЫ СКРЫТИЯ
  // ============================================================

  /**
   * Скрывает подсветку указанной группы зон
   */
  async hideZone(zoneId: string, duration: number = 150): Promise<void> {
    const cellKeys = this.zoneGroups.get(zoneId);
    if (!cellKeys) return;

    const promises: Promise<void>[] = [];

    cellKeys.forEach(key => {
      const highlight = this.highlights.get(key);
      if (highlight) {
        promises.push(highlight.hide(duration));
        this.highlights.delete(key);
      }
    });

    this.zoneGroups.delete(zoneId);
    await Promise.all(promises);
  }

  /**
   * Скрывает подсветку для конкретной клетки
   */
  async hideCell(x: number, y: number, duration: number = 150): Promise<void> {
    const key = this.getCellKey(x, y);
    const highlight = this.highlights.get(key);
    if (highlight) {
      await highlight.hide(duration);
      this.highlights.delete(key);

      // Удаляем из всех групп
      this.zoneGroups.forEach(cellKeys => cellKeys.delete(key));
    }
  }

  /**
   * Скрывает всю подсветку
   */
  async hideAll(duration: number = 150): Promise<void> {
    const promises: Promise<void>[] = [];

    this.highlights.forEach(highlight => {
      promises.push(highlight.hide(duration));
    });

    this.highlights.clear();
    this.zoneGroups.clear();

    await Promise.all(promises);
  }

  // ============================================================
  // МЕТОДЫ ОБНОВЛЕНИЯ
  // ============================================================

  /**
   * Обновляет тип подсветки для группы зон
   */
  async updateZoneType(
    zoneId: string,
    newType: ZoneHighlightType
  ): Promise<void> {
    const cellKeys = this.zoneGroups.get(zoneId);
    if (!cellKeys) return;

    const colorConfig = ZONE_COLOR_MAP[newType];

    cellKeys.forEach(key => {
      const highlight = this.highlights.get(key);
      if (highlight) {
        highlight.updateColor(colorConfig);
      }
    });
  }

  /**
   * Добавляет пульсацию к зоне
   */
  addPulseToZone(zoneId: string, speed: number = 1000): void {
    const cellKeys = this.zoneGroups.get(zoneId);
    if (!cellKeys) return;

    cellKeys.forEach(key => {
      const highlight = this.highlights.get(key);
      if (highlight && highlight instanceof CellHighlight) {
        // Пересоздаём подсветку с пульсацией
        highlight.stopPulse();
        // Для простоты используем встроенные методы
        this.scene.tweens.add({
          targets: (highlight as any).background,
          alpha: { from: 0.5, to: 0.2 },
          scale: { from: 1, to: 1.05 },
          duration: speed,
          yoyo: true,
          repeat: -1,
          ease: Phaser.Math.Easing.Sine.InOut,
        });
      }
    });
  }

  /**
   * Убирает пульсацию с зоны
   */
  removePulseFromZone(zoneId: string): void {
    const cellKeys = this.zoneGroups.get(zoneId);
    if (!cellKeys) return;

    cellKeys.forEach(key => {
      const highlight = this.highlights.get(key);
      if (highlight && highlight instanceof CellHighlight) {
        highlight.stopPulse();
      }
    });
  }

  // ============================================================
  // УТИЛИТЫ
  // ============================================================

  /**
   * Генерирует ключ для клетки
   */
  private getCellKey(x: number, y: number): string {
    return `${x},${y}`;
  }

  /**
   * Удаляет подсветку клетки
   */
  private removeCellHighlight(key: string): void {
    const existing = this.highlights.get(key);
    if (existing) {
      existing.destroy();
      this.highlights.delete(key);
    }
  }

  /**
   * Проверяет, подсвечена ли клетка
   */
  isCellHighlighted(x: number, y: number): boolean {
    return this.highlights.has(this.getCellKey(x, y));
  }

  /**
   * Получает ID группы зоны по клетке
   */
  getZoneIdByCell(x: number, y: number): string | undefined {
    const cellKey = this.getCellKey(x, y);

    for (const [zoneId, cellKeys] of this.zoneGroups.entries()) {
      if (cellKeys.has(cellKey)) {
        return zoneId;
      }
    }

    return undefined;
  }

  /**
   * Получает все активные зоны
   */
  getActiveZones(): string[] {
    return Array.from(this.zoneGroups.keys());
  }

  /**
   * Получает количество подсвеченных клеток
   */
  getHighlightedCellCount(): number {
    return this.highlights.size;
  }

  // ============================================================
  // ИНТЕГРАЦИЯ С BoardRenderer
  // ============================================================

  /**
   * Обновляет размер клетки при изменении конфигурации доски
   */
  updateCellSize(newCellSize: number): void {
    this.cellSize = newCellSize;
  }

  /**
   * Создаёт подсветку из конфигурации зон BoardRenderer
   */
  async showZonesFromConfig(
    zones: Array<{ cells: Array<{ x: number; y: number }>; type: ZoneHighlightType; id?: string }>
  ): Promise<void> {
    await this.showMultipleZones(zones);
  }

  // ============================================================
  // ОЧИСТКА
  // ============================================================

  /**
   * Уничтожает компонент и освобождает ресурсы
   */
  destroy(): void {
    this.highlights.forEach(highlight => {
      if (highlight && highlight.scene) {
        highlight.destroy();
      }
    });

    this.highlights.clear();
    this.zoneGroups.clear();
  }
}

// ============================================================
// ЭКСПОРТ ТИПОВ
// ============================================================

export type { ZoneColorConfig, ZoneAnimationConfig, ZoneConfig };
export { CellHighlight };
