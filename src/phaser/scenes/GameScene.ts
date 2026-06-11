// ============================================================
// GAME SCENE - Основная игровая сцена
// ============================================================

import * as Phaser from 'phaser';
import type { GameState, Fighter, Position, CardInstance } from '../../core/models/types';
import type { PhaserGameEvent, PhaserGameState } from '../types';
import { ReplaySystem, type GameReplay } from '../systems';

export class GameScene extends Phaser.Scene {
  // Состояние игры
  private gameState: PhaserGameState;

  // Контейнеры для игровых объектов
  private boardContainer: Phaser.GameObjects.Container | null = null;
  private fightersContainer: Phaser.GameObjects.Container | null = null;
  private cardsContainer: Phaser.GameObjects.Container | null = null;
  private highlightsContainer: Phaser.GameObjects.Container | null = null;
  private effectsContainer: Phaser.GameObjects.Container | null = null;

  // Ссылки на игровые объекты
  private fighterSprites: Map<string, Phaser.GameObjects.Sprite> = new Map();
  private spaceHighlights: Map<string, Phaser.GameObjects.Rectangle> = new Map();
  private cardSprites: Map<string, Phaser.GameObjects.Sprite> = new Map();

  // Конфигурация
  private readonly SPACE_SIZE = 64;
  private readonly GRID_OFFSET_X = 100;
  private readonly GRID_OFFSET_Y = 100;

  // Callback для отправки событий в React
  private onGameEvent: (event: PhaserGameEvent) => void;

  // Replay система
  private replaySystem: ReplaySystem | null = null;
  private isReplayMode: boolean = false;

  constructor(onGameEvent: (event: PhaserGameEvent) => void) {
    super({ key: 'GameScene', active: true });
    this.onGameEvent = onGameEvent;
    this.gameState = {
      gameState: null,
      selectedFighterId: null,
      selectedCardId: null,
      highlightedSpaces: [],
      showGrid: true,
      showZones: true,
      debugMode: false,
    };
  }

  create(): void {
    console.log('GameScene: создана');

    // Настраиваем камеру
    this.setupCamera();

    // Создаём контейнеры для слоёв
    this.createContainers();

    // Создаём игровое поле
    this.createBoard();

    // Настраиваем обработчики событий
    this.setupEvents();

    // Инициализируем ReplaySystem
    this.setupReplaySystem();

    // Запускаем UI сцену как оверлей
    this.scene.launch('UIScene');

    // Отправляем событие о готовности
    this.onGameEvent({ type: 'PHASER_READY' });
  }

  update(): void {
    // Обновление анимаций и эффектов
  }

  // ============================================================
  // ИНИЦИАЛИЗАЦИЯ
  // ============================================================

  /**
   * Настраивает камеру сцены
   */
  private setupCamera(): void {
    const cam = this.cameras.main;
    cam.setBackgroundColor(0x1a1a2e);

    // Центрируем камеру
    cam.centerOn(400, 300);
  }

  /**
   * Создаёт контейнеры для организации слоёв
   */
  private createContainers(): void {
    this.boardContainer = this.add.container(0, 0);
    this.boardContainer.setDepth(0);

    this.highlightsContainer = this.add.container(0, 0);
    this.highlightsContainer.setDepth(1);

    this.fightersContainer = this.add.container(0, 0);
    this.fightersContainer.setDepth(2);

    this.cardsContainer = this.add.container(0, 0);
    this.cardsContainer.setDepth(3);

    this.effectsContainer = this.add.container(0, 0);
    this.effectsContainer.setDepth(4);
  }

  /**
   * Настраивает обработчики событий
   */
  private setupEvents(): void {
    // Обработка кликов по сцене
    this.input.on('pointerdown', this.handleSceneClick, this);

    // Глобальные события от React
    this.game.events.on('react-to-phaser', this.handleReactEvent, this);
  }

  // ============================================================
  // СОЗДАНИЕ ИГРОВЫХ ОБЪЕКТОВ
  // ============================================================

  /**
   * Создаёт игровое поле
   */
  createBoard(): void {
    if (!this.boardContainer) return;

    // TODO: Загрузить реальное поле из GameState
    // Сейчас создаём placeholder поле 8x8

    const boardWidth = 8;
    const boardHeight = 8;

    // Фон поля
    const bg = this.add.rectangle(
      this.GRID_OFFSET_X + (boardWidth * this.SPACE_SIZE) / 2,
      this.GRID_OFFSET_Y + (boardHeight * this.SPACE_SIZE) / 2,
      boardWidth * this.SPACE_SIZE,
      boardHeight * this.SPACE_SIZE,
      0x2d2d44
    );
    bg.setStrokeStyle(2, 0x4ecca3);
    this.boardContainer.add(bg);

    // Создаём клетки
    for (let x = 0; x < boardWidth; x++) {
      for (let y = 0; y < boardHeight; y++) {
        this.createSpace(x, y);
      }
    }
  }

  /**
   * Создаёт отдельную клетку на поле
   */
  private createSpace(x: number, y: number): void {
    const posX = this.GRID_OFFSET_X + x * this.SPACE_SIZE + this.SPACE_SIZE / 2;
    const posY = this.GRID_OFFSET_Y + y * this.SPACE_SIZE + this.SPACE_SIZE / 2;

    // Заливка клетки
    const rect = this.add.rectangle(posX, posY, this.SPACE_SIZE - 2, this.SPACE_SIZE - 2, 0x3d3d5c);
    rect.setStrokeStyle(1, 0x4a4a6a);

    if (this.boardContainer) {
      this.boardContainer.add(rect);
    }

    // Зоны (placeholder - все клетки синие)
    if (this.gameState.showZones) {
      const zoneSize = 8;
      const zone = this.add.circle(posX - this.SPACE_SIZE / 2 + zoneSize, posY - this.SPACE_SIZE / 2 + zoneSize, zoneSize, 0x4e9aff);
      if (this.boardContainer) {
        this.boardContainer.add(zone);
      }
    }
  }

  /**
   * Создаёт бойцов на поле
   */
  createFighters(fighters: Fighter[]): void {
    // Очищаем старых бойцов
    this.fighterSprites.forEach(sprite => sprite.destroy());
    this.fighterSprites.clear();

    fighters.forEach(fighter => {
      this.createFighter(fighter);
    });
  }

  /**
   * Создаёт отдельного бойца
   */
  private createFighter(fighter: Fighter): void {
    const posX = this.GRID_OFFSET_X + fighter.position.x * this.SPACE_SIZE + this.SPACE_SIZE / 2;
    const posY = this.GRID_OFFSET_Y + fighter.position.y * this.SPACE_SIZE + this.SPACE_SIZE / 2;

    // Placeholder спрайт
    const sprite = this.add.rectangle(posX, posY, 48, 48, 0xff6b6b);
    sprite.setStrokeStyle(2, 0xffffff);

    // Добавляем индикатор здоровья
    const healthBg = this.add.rectangle(posX, posY - 30, 50, 8, 0x333333);
    const healthBar = this.add.rectangle(posX - 25 + (fighter.health / fighter.maxHealth) * 25, posY - 30, (fighter.health / fighter.maxHealth) * 50, 6, 0x4ecca3);

    if (this.fightersContainer) {
      this.fightersContainer.add(sprite);
      this.fightersContainer.add(healthBg);
      this.fightersContainer.add(healthBar);
    }

    // Делаем спрайт интерактивным
    sprite.setInteractive({ useHandCursor: true });
    sprite.on('pointerdown', () => {
      this.handleFighterClick(fighter.id);
    });

    this.fighterSprites.set(fighter.id, sprite);
  }

  /**
   * Создаёт карты на руках игроков
   */
  createCards(cards: CardInstance[]): void {
    // Очищаем старые карты
    this.cardSprites.forEach(sprite => sprite.destroy());
    this.cardSprites.clear();

    cards.forEach((card, index) => {
      this.createCard(card, index);
    });
  }

  /**
   * Создаёт отдельную карту
   */
  private createCard(card: CardInstance, index: number): void {
    const startX = 50;
    const y = this.cameras.main.height - 100;
    const x = startX + index * 70;

    // Placeholder спрайт карты
    const sprite = this.add.rectangle(x, y, 60, 90, 0x6bcbff);
    sprite.setStrokeStyle(2, 0xffffff);

    if (this.cardsContainer) {
      this.cardsContainer.add(sprite);
    }

    // Делаем спрайт интерактивным
    sprite.setInteractive({ useHandCursor: true });
    sprite.on('pointerdown', () => {
      this.handleCardClick(card.id);
    });

    this.cardSprites.set(card.id, sprite);
  }

  // ============================================================
  // ОБРАБОТКА СОБЫТИЙ
  // ============================================================

  /**
   * Обрабатывает клик по сцене
   */
  private handleSceneClick(pointer: Phaser.Input.Pointer): void {
    const worldPoint = this.cameras.main.getWorldPoint(pointer.x, pointer.y);

    // Конвертируем в координаты сетки
    const gridX = Math.floor((worldPoint.x - this.GRID_OFFSET_X) / this.SPACE_SIZE);
    const gridY = Math.floor((worldPoint.y - this.GRID_OFFSET_Y) / this.SPACE_SIZE);

    if (gridX >= 0 && gridX < 8 && gridY >= 0 && gridY < 8) {
      this.onGameEvent({
        type: 'SPACE_CLICKED',
        position: { x: gridX, y: gridY },
      });
    }
  }

  /**
   * Обрабатывает клик по бойцу
   */
  private handleFighterClick(fighterId: string): void {
    console.log('GameScene: клик по бойцу', fighterId);

    // Подсвечиваем выбранного бойца
    this.fighterSprites.forEach((sprite, id) => {
      if (id === fighterId) {
        sprite.setStrokeStyle(4, 0xffeb3b);
      } else {
        sprite.setStrokeStyle(2, 0xffffff);
      }
    });

    this.onGameEvent({
      type: 'FIGHTER_CLICKED',
      fighterId,
    });
  }

  /**
   * Обрабатывает клик по карте
   */
  private handleCardClick(cardId: string): void {
    console.log('GameScene: клик по карте', cardId);

    this.onGameEvent({
      type: 'CARD_CLICKED',
      cardId,
    });
  }

  /**
   * Обрабатывает события от React
   */
  private handleReactEvent(event: unknown): void {
    console.log('GameScene: событие от React', event);
    // TODO: Обработка разных типов событий
  }

  // ============================================================
  // ВИЗУАЛЬНЫЕ ЭФФЕКТЫ
  // ============================================================

  /**
   * Подсвечивает клетки на поле
   */
  highlightSpaces(positions: Position[]): void {
    // Очищаем старое выделение
    this.spaceHighlights.forEach(rect => rect.destroy());
    this.spaceHighlights.clear();

    positions.forEach(pos => {
      const posX = this.GRID_OFFSET_X + pos.x * this.SPACE_SIZE + this.SPACE_SIZE / 2;
      const posY = this.GRID_OFFSET_Y + pos.y * this.SPACE_SIZE + this.SPACE_SIZE / 2;

      const highlight = this.add.rectangle(posX, posY, this.SPACE_SIZE - 2, this.SPACE_SIZE - 2, 0x4ecca3, 0.3);

      if (this.highlightsContainer) {
        this.highlightsContainer.add(highlight);
      }

      this.spaceHighlights.set(`${pos.x},${pos.y}`, highlight);
    });
  }

  /**
   * Очищает выделение клеток
   */
  clearHighlights(): void {
    this.spaceHighlights.forEach(rect => rect.destroy());
    this.spaceHighlights.clear();
  }

  /**
   * Показывает урон
   */
  showDamage(fighterId: string, amount: number): void {
    const sprite = this.fighterSprites.get(fighterId);
    if (!sprite) return;

    // Создаём текст урона
    const damageText = this.add.text(sprite.x, sprite.y - 50, `-${amount}`, {
      fontSize: '32px',
      color: '#ff4444',
      fontStyle: 'bold',
    });
    damageText.setOrigin(0.5);

    if (this.effectsContainer) {
      this.effectsContainer.add(damageText);
    }

    // Анимация всплывания
    this.tweens.add({
      targets: damageText,
      y: sprite.y - 100,
      alpha: 0,
      duration: 1000,
      onComplete: () => {
        damageText.destroy();
      },
    });
  }

  // ============================================================
  // PUBLIC API
  // ============================================================

  /**
   * Обновляет состояние игры
   */
  updateGameState(state: GameState): void {
    this.gameState.gameState = state;

    // Обновляем бойцов
    if (state.players) {
      state.players.forEach(player => {
        this.createFighters(player.fighters);
      });
    }

    // Обновляем карты текущего игрока
    // TODO: Определить текущего игрока
  }

  /**
   * Перемещает бойца анимированно
   */
  moveFighter(fighterId: string, position: Position): Promise<void> {
    return new Promise(resolve => {
      const sprite = this.fighterSprites.get(fighterId);
      if (!sprite) {
        resolve();
        return;
      }

      const targetX = this.GRID_OFFSET_X + position.x * this.SPACE_SIZE + this.SPACE_SIZE / 2;
      const targetY = this.GRID_OFFSET_Y + position.y * this.SPACE_SIZE + this.SPACE_SIZE / 2;

      this.tweens.add({
        targets: sprite,
        x: targetX,
        y: targetY,
        duration: 300,
        onComplete: () => resolve(),
      });
    });
  }

  // ============================================================
  // REPLAY SYSTEM INTEGRATION
  // ============================================================

  /**
   * Настраивает систему реплея
   */
  private setupReplaySystem(): void {
    this.replaySystem = new ReplaySystem(this, {
      autoRecord: true,
      maxSnapshots: 100,
      snapshotInterval: 5000,
    });

    // Подписываемся на события реплея
    this.events.on('replay:event', this.handleReplayEvent, this);
    this.events.on('replay:state', this.handleReplayState, this);
    this.events.on('replay:revert', this.handleReplayRevert, this);

    console.log('[GameScene] ReplaySystem инициализирована');
  }

  /**
   * Начать запись игры
   */
  startRecording(players: Array<{ userId: string; userName?: string; heroId: string; heroName?: string }>, gameId: string): void {
    if (!this.replaySystem) return;

    this.replaySystem.startRecording(players, gameId, {
      boardId: 'default',
      gameMode: 'standard',
    });

    console.log('[GameScene] Начата запись игры');
  }

  /**
   * Остановить запись игры
   */
  stopRecording(winnerId?: string): GameReplay | null {
    if (!this.replaySystem) return null;
    return this.replaySystem.stopRecording(winnerId);
  }

  /**
   * Загрузить реплей для воспроизведения
   */
  loadReplay(replay: GameReplay): void {
    if (!this.replaySystem) return;

    this.isReplayMode = true;
    this.replaySystem.loadReplay(replay);

    console.log('[GameScene] Загружен реплей:', replay.id);
  }

  /**
   * Начать воспроизведение реплея
   */
  playReplay(): void {
    if (!this.replaySystem) return;
    this.replaySystem.play();
  }

  /**
   * Пауза воспроизведения
   */
  pauseReplay(): void {
    if (!this.replaySystem) return;
    this.replaySystem.pause();
  }

  /**
   * Остановить воспроизведение
   */
  stopReplay(): void {
    if (!this.replaySystem) return;
    this.replaySystem.stop();
    this.isReplayMode = false;
  }

  /**
   * Перемотать к определённому времени
   */
  seekReplay(time: number): void {
    if (!this.replaySystem) return;
    this.replaySystem.seekTo(time);
  }

  /**
   * Установить скорость воспроизведения
   */
  setReplaySpeed(speed: number): void {
    if (!this.replaySystem) return;
    this.replaySystem.setPlaybackSpeed(speed);
  }

  /**
   * Обработчик события воспроизведения
   */
  private handleReplayEvent(event: unknown): void {
    console.log('[GameScene] Воспроизведение события:', event);
    // TODO: Применить событие к игровым объектам
  }

  /**
   * Обработчик состояния воспроизведения
   */
  private handleReplayState(state: Partial<GameState>): void {
    console.log('[GameScene] Применение состояния:', state);
    this.updateGameState(state as GameState);
  }

  /**
   * Обработчик отката события (для обратного воспроизведения)
   */
  private handleReplayRevert(event: unknown): void {
    console.log('[GameScene] Откат события:', event);
    // TODO: Откатить изменения в игровых объектах
  }

  /**
   * Получить текущую систему реплея
   */
  getReplaySystem(): ReplaySystem | null {
    return this.replaySystem;
  }
}
