// ============================================================
// INPUT HANDLER - Обработка ввода пользователя
// ============================================================

import Phaser from 'phaser';
import type { GameScene } from '../renderers/BoardRenderer';
import type { Position } from '../../core/models/types';

/**
 * События ввода, передаваемые в React
 */
export interface InputEvent {
  eventType: 'fighter:selected' | 'cell:clicked' | 'door:clicked' | 'cell:hovered';
  data: {
    fighterId?: string;
    position?: Position;
    doorId?: string;
  };
}

/**
 * Конфигурация обработчика ввода
 */
export interface InputHandlerConfig {
  enableHoverEffects?: boolean;
  clickThreshold?: number; // Максимальное смещение для считывания клика
  doubleClickDelay?: number; // Задержка для двойного клика
}

/**
 * Обработчик ввода пользователя
 *
 * Отвечает за:
 * - Обработку кликов по бойцам
 * - Обработку кликов по клеткам поля
 * - Эффекты при наведении
 * - Эмитацию событий для React
 * - Управление курсором
 */
export class InputHandler {
  private scene: GameScene;
  private config: Required<InputHandlerConfig>;

  // Состояние
  private isEnabled: boolean = true;
  private fighterSelectionEnabled: boolean = false;
  private cellClickEnabled: boolean = false;

  // Отслеживание указателя
  private pointerDownPosition: { x: number; y: number } | null = null;
  private lastClickTime: number = 0;

  // Текущее наведение
  private hoveredCell: Position | null = null;
  private hoveredFighterId: string | null = null;

  // Колбэки для событий
  private fighterSelectedCallback?: (fighterId: string) => void;
  private onCellClicked?: (position: Position) => void;
  private onDoorClicked?: (doorId: string, position: Position) => void;
  private onCellHovered?: (position: Position | null) => void;

  // Ссылки на объекты
  private fighterSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  private cellHighlighters: Map<string, Phaser.GameObjects.Rectangle> = new Map();

  // Графика для подсветки наведения
  private hoverGraphics: Phaser.GameObjects.Graphics;

  constructor(scene: GameScene, config?: InputHandlerConfig) {
    this.scene = scene;

    this.config = {
      enableHoverEffects: true,
      clickThreshold: 5,
      doubleClickDelay: 300,
      ...config
    };

    // Создаём графику для эффектов наведения
    this.hoverGraphics = new Phaser.GameObjects.Graphics(scene);
    scene.add.existing(this.hoverGraphics);
    this.hoverGraphics.setDepth(90);

    // Настраиваем глобальные обработчики
    this.setupGlobalHandlers();
  }

  /**
   * Настраивает глобальные обработчики событий сцены
   */
  private setupGlobalHandlers(): void {
    // Отслеживаем нажатие мыши
    this.scene.input.on('pointerdown', this.handlePointerDown.bind(this));

    // Отслеживаем отпускание мыши
    this.scene.input.on('pointerup', this.handlePointerUp.bind(this));

    // Отслеживаем движение мыши
    this.scene.input.on('pointermove', this.handlePointerMove.bind(this));

    // Подписываемся на события от бойцов
    this.scene.events.on('fighter:click', this.handleFighterClick.bind(this));
    this.scene.events.on('fighter:hover', this.handleFighterHover.bind(this));

    // Подписываемся на события от дверей
    this.scene.events.on('door:clicked', this.handleDoorClick.bind(this));
  }

  /**
   * Обрабатывает нажатие кнопки мыши
   */
  private handlePointerDown(pointer: Phaser.Input.Pointer): void {
    if (!this.isEnabled) return;

    this.pointerDownPosition = { x: pointer.x, y: pointer.y };
  }

  /**
   * Обрабатывает отпускание кнопки мыши
   */
  private handlePointerUp(pointer: Phaser.Input.Pointer): void {
    if (!this.isEnabled || !this.pointerDownPosition) return;

    // Проверяем, что это был клик (не перетаскивание)
    const distance = Phaser.Math.Distance.Between(
      this.pointerDownPosition.x,
      this.pointerDownPosition.y,
      pointer.x,
      pointer.y
    );

    if (distance <= this.config.clickThreshold) {
      // Определяем, на что кликнули
      this.handleClickAtPosition(pointer.x, pointer.y);
    }

    // Проверяем двойной клик
    const timeSinceLastClick = Date.now() - this.lastClickTime;
    if (timeSinceLastClick < this.config.doubleClickDelay) {
      this.handleDoubleClickAtPosition(pointer.x, pointer.y);
    }

    this.lastClickTime = Date.now();
    this.pointerDownPosition = null;
  }

  /**
   * Обрабатывает движение мыши
   */
  private handlePointerMove(pointer: Phaser.Input.Pointer): void {
    if (!this.isEnabled || !this.cellClickEnabled) return;

    // Преобразуем экранные координаты в координаты клетки
    const cellPosition = this.screenToCellPosition(pointer.x, pointer.y);

    if (cellPosition) {
      // Проверяем, изменилась ли клетка
      if (!this.hoveredCell ||
          this.hoveredCell.x !== cellPosition.x ||
          this.hoveredCell.y !== cellPosition.y) {

        // Убираем подсветку с предыдущей клетки
        if (this.hoveredCell && this.config.enableHoverEffects) {
          this.clearCellHover();
        }

        // Устанавливаем новую клетку
        this.hoveredCell = cellPosition;

        // Подсвечиваем новую клетку
        if (this.config.enableHoverEffects) {
          this.showCellHover(cellPosition);
        }

        // Эмитим событие
        this.emitCellHovered(cellPosition);
      }
    } else if (this.hoveredCell) {
      // Ушли с поля
      this.clearCellHover();
      this.emitCellHovered(null);
      this.hoveredCell = null;
    }
  }

  /**
   * Определяет объект под курсором и обрабатывает клик
   */
  private handleClickAtPosition(x: number, y: number): void {
    // Проверяем, кликнули ли на клетку
    if (this.cellClickEnabled) {
      const cellPosition = this.screenToCellPosition(x, y);
      if (cellPosition && this.isCellInteractive(cellPosition)) {
        this.emitCellClicked(cellPosition);
        return;
      }
    }
  }

  /**
   * Обрабатывает двойной клик
   */
  private handleDoubleClickAtPosition(x: number, y: number): void {
    // Двойной клик может использоваться для быстрого действия
    const cellPosition = this.screenToCellPosition(x, y);
    if (cellPosition && this.cellClickEnabled) {
      this.scene.events.emit('cell:double-clicked', { position: cellPosition });
    }
  }

  /**
   * Обрабатывает клик по бойцу
   */
  private handleFighterClick(data: { fighterId: string }): void {
    if (!this.isEnabled || !this.fighterSelectionEnabled) return;

    this.emitFighterSelected(data.fighterId);
  }

  /**
   * Обрабатывает наведение на бойца
   */
  private handleFighterHover(data: { fighterId: string }): void {
    if (!this.isEnabled) return;

    this.hoveredFighterId = data.fighterId;
  }

  /**
   * Обрабатывает клик по двери
   */
  private handleDoorClick(data: { doorId: string; position: Position }): void {
    if (!this.isEnabled) return;

    this.emitDoorClicked(data.doorId, data.position);
  }

  /**
   * Преобразует экранные координаты в координаты клетки
   */
  private screenToCellPosition(screenX: number, screenY: number): Position | null {
    // Получаем конфигурацию поля из сцены
    const boardConfig = (this.scene as any).boardConfig;
    if (!boardConfig) return null;

    // Преобразуем экранные координаты в мировые
    const worldPoint = this.scene.cameras.main.getWorldPoint(screenX, screenY);

    // Вычисляем клетку
    const cellX = Math.floor(worldPoint.x / boardConfig.cellSize);
    const cellY = Math.floor(worldPoint.y / boardConfig.cellSize);

    // Проверяем, что клетка в пределах поля
    if (cellX < 0 || cellX >= boardConfig.width ||
        cellY < 0 || cellY >= boardConfig.height) {
      return null;
    }

    return { x: cellX, y: cellY };
  }

  /**
   * Проверяет, является ли клетка интерактивной
   */
  private isCellInteractive(_position: Position): boolean {
    // TODO: Добавить проверку на препятствия, зоны и т.д.
    return true;
  }

  /**
   * Показывает подсветку клетки при наведении
   */
  private showCellHover(position: Position): void {
    const boardConfig = (this.scene as any).boardConfig;
    if (!boardConfig) return;

    // Рисуем подсветку
    this.hoverGraphics.clear();
    this.hoverGraphics.lineStyle(2, 0x6c5ce7, 0.8);
    this.hoverGraphics.strokeRect(
      position.x * boardConfig.cellSize + 2,
      position.y * boardConfig.cellSize + 2,
      boardConfig.cellSize - 4,
      boardConfig.cellSize - 4
    );
  }

  /**
   * Убирает подсветку клетки
   */
  private clearCellHover(): void {
    this.hoverGraphics.clear();
  }

  // ============================================================
  // МЕТОДЫ ЭМИТТАЦИИ СОБЫТИЙ
  // ============================================================

  private emitFighterSelected(fighterId: string): void {
    this.fighterSelectedCallback?.(fighterId);
    this.scene.events.emit('input:event', {
      eventType: 'fighter:selected',
      data: { fighterId }
    } as InputEvent);
  }

  private emitCellClicked(position: Position): void {
    this.onCellClicked?.(position);
    this.scene.events.emit('input:event', {
      eventType: 'cell:clicked',
      data: { position }
    } as InputEvent);
  }

  private emitCellHovered(position: Position | null): void {
    this.onCellHovered?.(position);
    this.scene.events.emit('input:event', {
      eventType: 'cell:hovered',
      data: { position: position || undefined }
    } as InputEvent);
  }

  private emitDoorClicked(doorId: string, position: Position): void {
    this.onDoorClicked?.(doorId, position);
    this.scene.events.emit('input:event', {
      eventType: 'door:clicked',
      data: { doorId, position }
    } as InputEvent);
  }

  // ============================================================
  // ПУБЛИЧНЫЕ МЕТОДЫ
  // ============================================================

  /**
   * Включает выбор бойцов
   */
  enableFighterSelection(): void {
    this.fighterSelectionEnabled = true;
  }

  /**
   * Выключает выбор бойцов
   */
  disableFighterSelection(): void {
    this.fighterSelectionEnabled = false;
  }

  /**
   * Включает клики по клеткам
   */
  enableCellClick(): void {
    this.cellClickEnabled = true;
  }

  /**
   * Выключает клики по клеткам
   */
  disableCellClick(): void {
    this.cellClickEnabled = false;
    this.clearCellHover();
    this.hoveredCell = null;
  }

  /**
   * Полностью отключает обработчик ввода
   */
  disable(): void {
    this.isEnabled = false;
    this.fighterSelectionEnabled = false;
    this.cellClickEnabled = false;
    this.clearCellHover();
  }

  /**
   * Включает обработчик ввода
   */
  enable(): void {
    this.isEnabled = true;
  }

  /**
   * Регистрирует спрайт бойца для отслеживания
   */
  registerFighterSprite(fighterId: string, sprite: Phaser.GameObjects.Container): void {
    this.fighterSprites.set(fighterId, sprite);
  }

  /**
   * Убирает спрайт бойца из отслеживания
   */
  unregisterFighterSprite(fighterId: string): void {
    this.fighterSprites.delete(fighterId);
  }

  /**
   * Устанавливает колбэк для выбора бойца
   */
  onFighterSelected(callback: (fighterId: string) => void): void {
    this.fighterSelectedCallback = callback;
  }

  /**
   * Устанавливает колбэк для клика по клетке
   */
  onCellClick(callback: (position: Position) => void): void {
    this.onCellClicked = callback;
  }

  /**
   * Устанавливает колбэк для клика по двери
   */
  onDoorClick(callback: (doorId: string, position: Position) => void): void {
    this.onDoorClicked = callback;
  }

  /**
   * Устанавливает колбэк для наведения на клетку
   */
  onCellHover(callback: (position: Position | null) => void): void {
    this.onCellHovered = callback;
  }

  /**
   * Получает текущую наведённую клетку
   */
  getHoveredCell(): Position | null {
    return this.hoveredCell;
  }

  /**
   * Получает ID наведённого бойца
   */
  getHoveredFighterId(): string | null {
    return this.hoveredFighterId;
  }

  /**
   * Уничтожает обработчик и освобождает ресурсы
   */
  destroy(): void {
    this.disable();

    this.scene.input.off('pointerdown', this.handlePointerDown.bind(this));
    this.scene.input.off('pointerup', this.handlePointerUp.bind(this));
    this.scene.input.off('pointermove', this.handlePointerMove.bind(this));

    this.scene.events.off('fighter:click', this.handleFighterClick.bind(this));
    this.scene.events.off('fighter:hover', this.handleFighterHover.bind(this));
    this.scene.events.off('door:clicked', this.handleDoorClick.bind(this));

    this.hoverGraphics.destroy();
    this.fighterSprites.clear();
    this.cellHighlighters.clear();
  }
}
