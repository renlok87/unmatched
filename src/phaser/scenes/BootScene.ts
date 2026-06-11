// ============================================================
// BOOT SCENE - Предзагрузка активов
// ============================================================

import Phaser from 'phaser';

export class BootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BootScene' });
  }

  preload(): void {
    this.createLoadScreen();

    // Загружаем базовые графические активы (placeholders)
    this.loadPlaceholderAssets();

    // Загружаем активы для игрового поля
    this.loadBoardAssets();

    // Загружаем активы для бойцов
    this.loadFighterAssets();

    // Загружаем активы для карт
    this.loadCardAssets();

    // Загружаем UI элементы
    this.loadUIAssets();

    // Отображаем прогресс загрузки
    this.load.on('progress', this.updateLoadProgress, this);
    this.load.on('complete', this.onLoadComplete, this);
  }

  create(): void {
    // Создаём глобальные события для коммуникации между сценами
    this.setupGlobalEvents();

    // Переходим к главной сцене игры
    this.scene.start('GameScene', { scene: 'UIScene' });
  }

  /**
   * Создаёт экран загрузки с прогресс баром
   */
  private createLoadScreen(): void {
    const width = this.cameras.main.width;
    const height = this.cameras.main.height;

    // Фон
    this.add.rectangle(width / 2, height / 2, width, height, 0x1a1a2e);

    // Текст загрузки
    const loadingText = this.add.text(width / 2, height / 2 - 50, 'Загрузка...', {
      fontSize: '32px',
      color: '#ffffff',
    });
    loadingText.setOrigin(0.5);

    // Прогресс бар фон
    const progressBarBg = this.add.rectangle(width / 2, height / 2, 400, 30, 0x333333);
    progressBarBg.setOrigin(0.5);

    // Прогресс бар
    this.registry.set('progressBar', this.add.rectangle(
      width / 2 - 200,
      height / 2,
      0,
      30,
      0x4ecca3
    ));
    this.registry.get('progressBar').setOrigin(0, 0.5);
  }

  /**
   * Обновляет прогресс бар загрузки
   */
  private updateLoadProgress(progress: number): void {
    const progressBar = this.registry.get('progressBar');
    if (progressBar) {
      progressBar.width = 400 * progress;
    }
  }

  /**
   * Вызывается при завершении загрузки
   */
  private onLoadComplete(): void {
    console.log('Асеты загружены');
  }

  /**
   * Загружает placeholder активы для разработки
   */
  private loadPlaceholderAssets(): void {
    // Фон игрового поля
    this.load.image('board-bg', 'assets/phaser/board-placeholder.png');

    // Placeholder для бойцов
    this.load.image('fighter-placeholder', 'assets/phaser/fighter-placeholder.png');

    // Placeholder для карт
    this.load.image('card-placeholder', 'assets/phaser/card-placeholder.png');
    this.load.image('card-back', 'assets/phaser/card-back-placeholder.png');

    // Placeholder для зон на поле
    this.load.image('zone-blue', 'assets/phaser/zones/blue.png');
    this.load.image('zone-green', 'assets/phaser/zones/green.png');
    this.load.image('zone-yellow', 'assets/phaser/zones/yellow.png');
    this.load.image('zone-red', 'assets/phaser/zones/red.png');
    this.load.image('zone-purple', 'assets/phaser/zones/purple.png');
  }

  /**
   * Загружает активы для игрового поля
   */
  private loadBoardAssets(): void {
    // TODO: Загрузка реальных спрайтов для полей
    // this.load.image('board-forum', 'assets/boards/forum.png');
    // this.load.image('board-cornfield', 'assets/boards/cornfield.png');
  }

  /**
   * Загружает активы для бойцов
   */
  private loadFighterAssets(): void {
    // TODO: Загрузка спрайтов для героев
    // this.load.spritesheet('ms-marvel', 'assets/fighters/ms-marvel.png', {
    //   frameWidth: 64,
    //   frameHeight: 64,
    // });
    // this.load.spritesheet('daredevil', 'assets/fighters/daredevil.png', {
    //   frameWidth: 64,
    //   frameHeight: 64,
    // });
  }

  /**
   * Загружает активы для карт
   */
  private loadCardAssets(): void {
    // TODO: Загрузка изображений карт
    // this.load.image('card-rapid-punch', 'assets/cards/ms-marvel/rapid-punch.png');
  }

  /**
   * Загружает UI элементы
   */
  private loadUIAssets(): void {
    // TODO: Загрузка UI спрайтов
    // Кнопки, иконки, индикаторы и т.д.
  }

  /**
   * Настраивает глобальные события для коммуникации
   */
  private setupGlobalEvents(): void {
    // События от React к Phaser
    this.game.events.on('react-to-phaser', (event: unknown) => {
      console.log('BootScene: событие от React', event);
    });
  }
}
