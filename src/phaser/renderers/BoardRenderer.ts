// ============================================================
// BOARD RENDERER - Рендеринг игрового поля
// ============================================================

import Phaser from 'phaser';
import type { BoardConfig, Zone, Door } from '../types';
import { ZoneHighlight, ZoneHighlightType } from '../entities/ZoneHighlight';

/**
 * Основная сцена игры
 */
interface GameScene extends Phaser.Scene {
  boardConfig?: BoardConfig;
}

/**
 * Цвета для подсветки клеток
 */
enum HighlightColors {
  VALID_MOVE = 0x4ecca3,    // Зелёный для валидных ходов
  ATTACK_TARGET = 0xff6b6b, // Красный для целей атаки
  SELECTED = 0xffd93d,      // Жёлтый для выбранного
  HOVER = 0x6c5ce7,         // Фиолетовый для наведения
}

/**
 * Конфигурация двери для рендеринга
 */
interface DoorSprite extends Phaser.GameObjects.Container {
  doorId: string;
  isOpen: boolean;
  orientation: 'horizontal' | 'vertical';
}

/**
 * Рендерер игрового поля
 *
 * Отвечает за:
 * - Отрисовку сетки и зон
 * - Управление дверями
 * - Подсветку клеток (для перемещения и атаки)
 * - Отображение границ зон
 */
export class BoardRenderer {
  private scene: GameScene;
  private config: BoardConfig;
  private cellSize: number;
  private gridGraphics: Phaser.GameObjects.Graphics;
  private zoneGraphics: Phaser.GameObjects.Graphics;
  private highlightGraphics: Phaser.GameObjects.Graphics;
  private doorGroup: Phaser.GameObjects.Group;
  private highlights: Map<string, Phaser.GameObjects.Rectangle> = new Map();
  private doorSprites: Map<string, DoorSprite> = new Map();
  private zoneHighlight?: ZoneHighlight;

  constructor(scene: GameScene, config: BoardConfig) {
    this.scene = scene;
    this.config = config;
    this.cellSize = config.cellSize;

    // Создаём графические контейнеры для разных слоёв
    this.gridGraphics = new Phaser.GameObjects.Graphics(scene);
    this.zoneGraphics = new Phaser.GameObjects.Graphics(scene);
    this.highlightGraphics = new Phaser.GameObjects.Graphics(scene);

    scene.add.existing(this.gridGraphics);
    scene.add.existing(this.zoneGraphics);
    scene.add.existing(this.highlightGraphics);

    // Группа для дверей
    this.doorGroup = new Phaser.GameObjects.Group(scene);

    // Инициализируем ZoneHighlight для расширенной подсветки зон
    this.zoneHighlight = new ZoneHighlight(scene, this.cellSize);
  }

  /**
   * Рендерит игровое поле с клетками и зонами
   */
  renderBoard(scene: GameScene, config: BoardConfig): void {
    this.config = config;
    this.cellSize = config.cellSize;

    this.clearBoard();

    // Рисуем фон поля
    this.drawBackground();

    // Рисуем сетку
    this.drawGrid();

    // Рисуем зоны
    this.drawZones();

    // Рисуем двери
    this.config.doors?.forEach(door => this.drawDoor(door));
  }

  /**
   * Рисует фон игрового поля
   */
  private drawBackground(): void {
    const width = this.config.width * this.cellSize;
    const height = this.config.height * this.cellSize;

    // Основной фон
    const bg = this.scene.add.rectangle(
      width / 2,
      height / 2,
      width,
      height,
      0x1a1a2e
    );
    bg.setDepth(0);

    // Граница поля
    const border = this.scene.add.graphics();
    border.lineStyle(4, 0x4a4a6a);
    border.strokeRect(0, 0, width, height);
    border.setDepth(1);
  }

  /**
   * Рисует сетку клеток
   */
  private drawGrid(): void {
    this.gridGraphics.clear();

    const gridColor = 0x3a3a5a;
    const lineWidth = 1;

    this.gridGraphics.lineStyle(lineWidth, gridColor);

    // Вертикальные линии
    for (let x = 0; x <= this.config.width; x++) {
      this.gridGraphics.moveTo(x * this.cellSize, 0);
      this.gridGraphics.lineTo(x * this.cellSize, this.config.height * this.cellSize);
    }

    // Горизонтальные линии
    for (let y = 0; y <= this.config.height; y++) {
      this.gridGraphics.moveTo(0, y * this.cellSize);
      this.gridGraphics.lineTo(this.config.width * this.cellSize, y * this.cellSize);
    }

    this.gridGraphics.strokePath();
    this.gridGraphics.setDepth(2);
  }

  /**
   * Рисует цветные зоны на поле
   */
  private drawZones(): void {
    this.zoneGraphics.clear();

    this.config.zones.forEach(zone => {
      const color = zone.color || 0x444444;
      const alpha = zone.blocksMovement ? 0.4 : 0.2;

      this.zoneGraphics.fillStyle(color, alpha);

      zone.cells.forEach(cell => {
        const x = cell.x * this.cellSize;
        const y = cell.y * this.cellSize;

        this.zoneGraphics.fillRect(
          x + 2,
          y + 2,
          this.cellSize - 4,
          this.cellSize - 4
        );
      });
    });

    this.zoneGraphics.setDepth(3);
  }

  /**
   * Подсвечивает клетку указанным цветом
   *
   * @param x - Координата X клетки
   * @param y - Координата Y клетки
   * @param color - Цвет подсветки (из enum HighlightColors или произвольный)
   * @param alpha - Прозрачность (по умолчанию 0.5)
   */
  highlightCell(x: number, y: number, color: number, alpha: number = 0.5): void {
    const key = `${x},${y}`;

    // Удаляем существующую подсветку если есть
    if (this.highlights.has(key)) {
      this.highlights.get(key)!.destroy();
    }

    // Создаём новую подсветку
    const highlight = this.scene.add.rectangle(
      x * this.cellSize + this.cellSize / 2,
      y * this.cellSize + this.cellSize / 2,
      this.cellSize - 4,
      this.cellSize - 4,
      color,
      alpha
    );
    highlight.setDepth(100);
    highlight.setStrokeStyle(2, color);

    this.highlights.set(key, highlight);

    // Добавляем анимацию появления
    this.scene.tweens.add({
      targets: highlight,
      alpha: alpha,
      scale: { from: 0.8, to: 1 },
      duration: 150,
      ease: Phaser.Math.Easing.Back.Out
    });
  }

  /**
   * Подсвечивает несколько клеток
   */
  highlightCells(cells: Array<{ x: number; y: number }>, color: number, alpha: number = 0.5): void {
    cells.forEach(cell => {
      this.highlightCell(cell.x, cell.y, color, alpha);
    });
  }

  /**
   * Снимает подсветку с конкретной клетки
   */
  clearCellHighlight(x: number, y: number): void {
    const key = `${x},${y}`;
    if (this.highlights.has(key)) {
      this.highlights.get(key)!.destroy();
      this.highlights.delete(key);
    }
  }

  /**
   * Снимает всю подсветку
   */
  clearHighlights(): void {
    this.highlights.forEach(highlight => {
      this.scene.tweens.add({
        targets: highlight,
        alpha: 0,
        scale: 0.8,
        duration: 100,
        onComplete: () => highlight.destroy()
      });
    });
    this.highlights.clear();
  }

  /**
   * Рисует дверь на поле
   *
   * @param door - Конфигурация двери
   */
  drawDoor(door: Door): void {
    const { x, y } = door.position;
    const centerX = x * this.cellSize + this.cellSize / 2;
    const centerY = y * this.cellSize + this.cellSize / 2;

    // Создаём контейнер для двери
    const doorContainer = this.scene.add.container(centerX, centerY) as DoorSprite;
    doorContainer.doorId = door.id;
    doorContainer.isOpen = door.isOpen;
    doorContainer.orientation = door.orientation;

    // Рисуем раму двери
    const frameSize = door.orientation === 'horizontal' ? this.cellSize : this.cellSize * 0.3;
    const frameThickness = 4;

    const frame = this.scene.add.rectangle(0, 0, frameSize, frameSize, 0x8b4513);
    frame.setStrokeStyle(frameThickness, 0x5c3317);

    // Рисуем саму дверь
    const doorSize = door.orientation === 'horizontal'
      ? this.cellSize - 8
      : this.cellSize * 0.3 - 4;

    const doorRect = this.scene.add.rectangle(
      0,
      0,
      doorSize,
      doorSize,
      door.isOpen ? 0x2d2d2d : 0x654321
    );

    // Добавляем детализацию (дверная ручка)
    const handleSize = 4;
    const handleOffset = doorSize / 4;
    const handle = this.scene.add.circle(
      door.orientation === 'horizontal' ? handleOffset : 0,
      door.orientation === 'horizontal' ? 0 : handleOffset,
      handleSize,
      0xffd700
    );

    doorContainer.add([frame, doorRect, handle]);
    doorContainer.setDepth(50);

    this.doorGroup.add(doorContainer);
    this.doorSprites.set(door.id, doorContainer);

    // Добавляем интерактивность
    doorContainer.setSize(frameSize, frameSize);
    doorContainer.setInteractive();

    doorContainer.on('pointerover', () => {
      this.scene.tweens.add({
        targets: doorContainer,
        scale: 1.1,
        duration: 100
      });
      this.scene.input.setDefaultCursor('pointer');
    });

    doorContainer.on('pointerout', () => {
      this.scene.tweens.add({
        targets: doorContainer,
        scale: 1,
        duration: 100
      });
      this.scene.input.setDefaultCursor('default');
    });

    doorContainer.on('pointerdown', () => {
      // Эмитим событие клика по двери
      this.scene.events.emit('door:clicked', {
        doorId: door.id,
        position: { x, y }
      });
    });
  }

  /**
   * Обновляет состояние двери (открыта/закрыта)
   */
  updateDoorState(doorId: string, isOpen: boolean): void {
    const doorSprite = this.doorSprites.get(doorId);
    if (!doorSprite) return;

    doorSprite.isOpen = isOpen;

    // Находим прямоугольник двери и меняем его цвет
    const doorRect = doorSprite.getAt(1) as Phaser.GameObjects.Rectangle;

    this.scene.tweens.add({
      targets: doorRect,
      alpha: 0.5,
      duration: 150,
      yoyo: true,
      onYoyo: () => {
        doorRect.fillColor = isOpen ? 0x2d2d2d : 0x654321;
      },
      onComplete: () => {
        doorRect.alpha = 1;
      }
    });
  }

  /**
   * Переключает состояние двери
   */
  toggleDoor(doorId: string): void {
    const doorSprite = this.doorSprites.get(doorId);
    if (!doorSprite) return;

    this.updateDoorState(doorId, !doorSprite.isOpen);
  }

  /**
   * Получает состояние двери
   */
  isDoorOpen(doorId: string): boolean {
    const doorSprite = this.doorSprites.get(doorId);
    return doorSprite?.isOpen ?? false;
  }

  /**
   * Подсвечивает валидные цели для перемещения
   */
  highlightMoveTargets(cells: Array<{ x: number; y: number }>): void {
    this.highlightCells(cells, HighlightColors.VALID_MOVE);
  }

  /**
   * Подсвечивает валидные цели для атаки
   */
  highlightAttackTargets(cells: Array<{ x: number; y: number }>): void {
    this.highlightCells(cells, HighlightColors.ATTACK_TARGET, 0.6);
  }

  // ============================================================
  // ИНТЕГРАЦИЯ С ZoneHighlight
  // ============================================================

  /**
   * Получает компонент ZoneHighlight для расширенного управления подсветкой
   */
  getZoneHighlight(): ZoneHighlight | undefined {
    return this.zoneHighlight;
  }

  /**
   * Показывает зону атаки с анимацией и пульсацией
   */
  async showAttackZone(cells: Array<{ x: number; y: number }>, zoneId?: string): Promise<void> {
    if (this.zoneHighlight) {
      await this.zoneHighlight.showAttackZone(cells, zoneId, true);
    }
  }

  /**
   * Показывает зону перемещения с анимацией
   */
  async showMovementZone(cells: Array<{ x: number; y: number }>, zoneId?: string): Promise<void> {
    if (this.zoneHighlight) {
      await this.zoneHighlight.showMovementZone(cells, zoneId);
    }
  }

  /**
   * Показывает зону способности с анимацией
   */
  async showAbilityZone(cells: Array<{ x: number; y: number }>, zoneId?: string): Promise<void> {
    if (this.zoneHighlight) {
      await this.zoneHighlight.showAbilityZone(cells, zoneId);
    }
  }

  /**
   * Скрывает подсветку зоны по ID
   */
  async hideZoneHighlight(zoneId: string): Promise<void> {
    if (this.zoneHighlight) {
      await this.zoneHighlight.hideZone(zoneId);
    }
  }

  /**
   * Скрывает всю подсветку зон
   */
  async hideAllZoneHighlights(): Promise<void> {
    if (this.zoneHighlight) {
      await this.zoneHighlight.hideAll();
    }
  }

  /**
   * Очищает всё и удаляет объекты
   */
  private clearBoard(): void {
    this.gridGraphics.clear();
    this.zoneGraphics.clear();
    this.highlightGraphics.clear();

    this.doorGroup.clear(true, true);
    this.doorSprites.clear();
    this.highlights.clear();

    // Очищаем ZoneHighlight
    if (this.zoneHighlight) {
      this.zoneHighlight.destroy();
      this.zoneHighlight = undefined;
    }
  }

  /**
   * Удаляет рендерер и освобождает ресурсы
   */
  destroy(): void {
    this.clearBoard();
    this.gridGraphics.destroy();
    this.zoneGraphics.destroy();
    this.highlightGraphics.destroy();
    this.doorGroup.destroy();

    // Уничтожаем ZoneHighlight
    if (this.zoneHighlight) {
      this.zoneHighlight.destroy();
      this.zoneHighlight = undefined;
    }
  }
}

// ============================================================
// ЭКСПОРТ ТИПОВ
// ============================================================

export type { GameScene };
export { HighlightColors };
export { ZoneHighlightType };
