// ============================================================
// MAIN GAME SCENE - Главная сцена игры с использованием новых компонентов
// ============================================================

import Phaser from 'phaser';
import { BoardRenderer } from '../renderers/BoardRenderer';
import { FighterSprite } from '../entities/FighterSprite';
import { InputHandler } from '../input/InputHandler';
import { CameraController, CameraMode } from '../camera/CameraController';
import type { BoardConfig, GameScene as IGameScene } from '../types';
import type { Fighter, Position } from '../../core/models/types';

/**
 * Конфигурация игровой сцены
 */
export interface MainGameSceneConfig {
  boardConfig: BoardConfig;
  fighters: Fighter[];
}

/**
 * Главная сцена игры
 *
 * Объединяет все компоненты Phaser:
 * - BoardRenderer для отображения поля
 * - FighterSprite для бойцов
 * - InputHandler для обработки ввода
 * - CameraController для управления камерой
 */
export class MainGameScene extends Phaser.Scene {
  // Компоненты
  private boardRenderer: BoardRenderer | null = null;
  private inputHandler: InputHandler | null = null;
  private cameraController: CameraController | null = null;

  // Спрайты бойцов
  private fighterSprites: Map<string, FighterSprite> = new Map();

  // Конфигурация
  public boardConfig: BoardConfig | undefined;

  // Состояние сцены
  private isInitialized: boolean = false;

  constructor() {
    super({ key: 'MainGameScene', active: true });
  }

  create(data?: MainGameSceneConfig): void {
    console.log('MainGameScene: инициализация');

    // Сохраняем конфигурацию
    if (data?.boardConfig) {
      this.boardConfig = data.boardConfig;
    }

    // Инициализируем компоненты
    this.initializeComponents();

    // Создаём поле если есть конфигурация
    if (this.boardConfig) {
      this.createBoard(this.boardConfig);
    }

    // Создаём бойцов если они есть
    if (data?.fighters) {
      data.fighters.forEach(fighter => this.addFighter(fighter));
    }

    // Настраиваем события
    this.setupEvents();

    this.isInitialized = true;

    // Эмитим событие готовности
    this.events.emit('scene:ready');
    this.game.events.emit('phaser-ready', { scene: 'MainGameScene' });
  }

  update(): void {
    // Обновляем камеру каждый кадр
    this.cameraController?.update();
  }

  /**
   * Инициализирует компоненты сцены
   */
  private initializeComponents(): void {
    // Создаём дефолтную конфигурацию поля если не задана
    if (!this.boardConfig) {
      this.boardConfig = {
        width: 10,
        height: 10,
        cellSize: 64,
        zones: [],
        doors: []
      };
    }

    // Создаём рендерер поля
    this.boardRenderer = new BoardRenderer(this as unknown as IGameScene, this.boardConfig);

    // Создаём обработчик ввода
    this.inputHandler = new InputHandler(this as unknown as IGameScene);

    // Создаём контроллер камеры
    this.cameraController = new CameraController(this as unknown as IGameScene);

    // Устанавливаем границы камеры
    const boardWidth = this.boardConfig.width * this.boardConfig.cellSize;
    const boardHeight = this.boardConfig.height * this.boardConfig.cellSize;
    this.cameraController.setBoardBounds(boardWidth, boardHeight);
  }

  /**
   * Создаёт игровое поле
   */
  createBoard(config: BoardConfig): void {
    this.boardConfig = config;
    this.boardRenderer?.renderBoard(this as unknown as IGameScene, config);

    // Обновляем границы камеры
    const boardWidth = config.width * config.cellSize;
    const boardHeight = config.height * config.cellSize;
    this.cameraController?.setBoardBounds(boardWidth, boardHeight);

    // Центрируем камеру на поле
    this.cameraController?.resetView();
  }

  /**
   * Настраивает события сцены
   */
  private setupEvents(): void {
    // События от InputHandler
    this.inputHandler?.onFighterSelected((fighterId: string) => {
      this.handleFighterSelected(fighterId);
    });

    this.inputHandler?.onCellClick((position: Position) => {
      this.handleCellClicked(position);
    });

    this.inputHandler?.onDoorClick((doorId: string, position: Position) => {
      this.handleDoorClicked(doorId, position);
    });
  }

  /**
   * Обрабатывает выбор бойца
   */
  private handleFighterSelected(fighterId: string): void {
    console.log('MainGameScene: выбран боец', fighterId);

    // Снимаем выделение с предыдущего бойца
    this.fighterSprites.forEach(sprite => {
      if (sprite.getFighterId() !== fighterId) {
        sprite.setSelected(false);
      }
    });

    // Выделяем выбранного бойца
    const fighterSprite = this.fighterSprites.get(fighterId);
    if (fighterSprite) {
      fighterSprite.setSelected(true);

      // Перемещаем камеру к бойцу
      this.cameraController?.followFighter(fighterId);
    }

    // Эмитим событие для React
    this.game.events.emit('game-event', {
      type: 'fighter:selected',
      fighterId
    });
  }

  /**
   * Обрабатывает клик по клетке
   */
  private handleCellClicked(position: Position): void {
    console.log('MainGameScene: клик по клетке', position);

    // Эмитим событие для React
    this.game.events.emit('game-event', {
      type: 'cell:clicked',
      position
    });
  }

  /**
   * Обрабатывает клик по двери
   */
  private handleDoorClicked(doorId: string, position: Position): void {
    console.log('MainGameScene: клик по двери', doorId);

    // Переключаем состояние двери
    const currentState = this.boardRenderer?.isDoorOpen(doorId);
    if (currentState !== undefined) {
      this.boardRenderer?.updateDoorState(doorId, !currentState);
    }

    // Эмитим событие для React
    this.game.events.emit('game-event', {
      type: 'door:clicked',
      doorId,
      position
    });
  }

  // ============================================================
  // ПУБЛИЧНЫЕ МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ ИГРОЙ
  // ============================================================

  /**
   * Добавляет бойца на сцену
   */
  addFighter(fighter: Fighter): FighterSprite | null {
    if (!this.boardConfig) return null;

    const cellX = fighter.position.x * this.boardConfig.cellSize + this.boardConfig.cellSize / 2;
    const cellY = fighter.position.y * this.boardConfig.cellSize + this.boardConfig.cellSize / 2;

    const fighterSprite = new FighterSprite(
      this as unknown as IGameScene,
      cellX,
      cellY,
      fighter
    );

    this.fighterSprites.set(fighter.id, fighterSprite);

    // Регистрируем спрайт в компонентах
    this.inputHandler?.registerFighterSprite(fighter.id, fighterSprite);
    this.cameraController?.registerFighterSprite(fighter.id, fighterSprite);

    return fighterSprite;
  }

  /**
   * Удаляет бойца со сцены
   */
  removeFighter(fighterId: string): void {
    const fighterSprite = this.fighterSprites.get(fighterId);
    if (fighterSprite) {
      this.inputHandler?.unregisterFighterSprite(fighterId);
      this.cameraController?.unregisterFighterSprite(fighterId);
      fighterSprite.destroy();
      this.fighterSprites.delete(fighterId);
    }
  }

  /**
   * Перемещает бойца в указанную клетку
   */
  async moveFighter(fighterId: string, position: Position): Promise<void> {
    const fighterSprite = this.fighterSprites.get(fighterId);
    if (!fighterSprite || !this.boardConfig) return;

    const targetX = position.x * this.boardConfig.cellSize + this.boardConfig.cellSize / 2;
    const targetY = position.y * this.boardConfig.cellSize + this.boardConfig.cellSize / 2;

    await fighterSprite.moveTo(targetX, targetY);
  }

  /**
   * Проигрывает анимацию атаки
   */
  async playAttackAnimation(fighterId: string): Promise<void> {
    const fighterSprite = this.fighterSprites.get(fighterId);
    if (!fighterSprite) return;

    await fighterSprite.playAttackAnimation();
  }

  /**
   * Проигрывает анимацию получения урона
   */
  async playDamageAnimation(fighterId: string, amount: number): Promise<void> {
    const fighterSprite = this.fighterSprites.get(fighterId);
    if (!fighterSprite) return;

    await fighterSprite.playDamageAnimation(amount);
  }

  /**
   * Обновляет здоровье бойца
   */
  updateFighterHealth(fighterId: string, current: number, max?: number): void {
    const fighterSprite = this.fighterSprites.get(fighterId);
    if (!fighterSprite) return;

    fighterSprite.updateHealth(current, max);
  }

  /**
   * Проигрывает анимацию смерти бойца
   */
  async killFighter(fighterId: string): Promise<void> {
    const fighterSprite = this.fighterSprites.get(fighterId);
    if (!fighterSprite) return;

    // Останавливаем следование камеры за этим бойцом
    if (this.cameraController) {
      const mode = this.cameraController.getMode();
      if (mode === CameraMode.FOLLOW) {
        this.cameraController.stopFollowing();
      }
    }

    await fighterSprite.playDeathAnimation();
  }

  /**
   * Подсвечивает валидные цели для перемещения
   */
  highlightMoveTargets(cells: Position[]): void {
    this.boardRenderer?.highlightMoveTargets(cells);
  }

  /**
   * Подсвечивает валидные цели для атаки
   */
  highlightAttackTargets(cells: Position[]): void {
    this.boardRenderer?.highlightAttackTargets(cells);
  }

  /**
   * Снимает всю подсветку
   */
  clearHighlights(): void {
    this.boardRenderer?.clearHighlights();
  }

  /**
   * Включает режим выбора бойца
   */
  enableFighterSelection(): void {
    this.inputHandler?.enableFighterSelection();
  }

  /**
   * Выключает режим выбора бойца
   */
  disableFighterSelection(): void {
    this.inputHandler?.disableFighterSelection();
  }

  /**
   * Включает клики по клеткам
   */
  enableCellClick(): void {
    this.inputHandler?.enableCellClick();
  }

  /**
   * Выключает клики по клеткам
   */
  disableCellClick(): void {
    this.inputHandler?.disableCellClick();
  }

  /**
   * Перемещает камеру к позиции
   */
  panCameraTo(x: number, y: number): void {
    this.cameraController?.panTo(x, y);
  }

  /**
   * Устанавливает зум камеры
   */
  setCameraZoom(zoom: number): void {
    this.cameraController?.setZoom(zoom);
  }

  /**
   * Заставляет камеру следовать за бойцом
   */
  followFighter(fighterId: string): void {
    this.cameraController?.followFighter(fighterId);
  }

  /**
   * Останавливает следование камеры
   */
  stopCameraFollow(): void {
    this.cameraController?.stopFollowing();
  }

  /**
   * Встряхивает камеру
   */
  shakeCamera(intensity?: number, duration?: number): void {
    this.cameraController?.shake(intensity, duration);
  }

  /**
   * Получает спрайт бойца по ID
   */
  getFighterSprite(fighterId: string): FighterSprite | undefined {
    return this.fighterSprites.get(fighterId);
  }

  /**
   * Получает всех бойцов
   */
  getAllFighters(): FighterSprite[] {
    return Array.from(this.fighterSprites.values());
  }

  /**
   * Очищает сцену
   */
  shutdown(): void {
    this.fighterSprites.forEach(sprite => sprite.destroy());
    this.fighterSprites.clear();

    this.boardRenderer?.destroy();
    this.inputHandler?.destroy();
    this.cameraController?.destroy();

    this.isInitialized = false;
  }
}

// ============================================================
// ЭКСПОРТ ТИПОВ
// ============================================================

export type { MainGameSceneConfig };
