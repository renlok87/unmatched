/**
 * DeckRenderer
 *
 * Визуализирует колоду и сброс игрока.
 * Показывает количество карт и предоставляет анимации вытягивания/сброса.
 */

import Phaser from 'phaser';

/**
 * Конфигурация отображения колоды
 */
export interface DeckConfig {
  cardWidth: number;
  cardHeight: number;
  spacing: number;
  yOffset: number;
  xOffset: number;
}

/**
 * Рендерер колоды и сброса
 */
export class DeckRenderer extends Phaser.GameObjects.Container {
  private deckGraphics: Phaser.GameObjects.Graphics;
  private discardGraphics: Phaser.GameObjects.Graphics;
  private deckCountText: Phaser.GameObjects.Text;
  private discardCountText: Phaser.GameObjects.Text;
  private deckCount: number = 0;
  private discardCount: number = 0;

  constructor(
    scene: Phaser.Scene,
    public readonly playerId: string,
    private config: DeckConfig = {
      cardWidth: 60,
      cardHeight: 84,
      spacing: 20,
      yOffset: 150,
      xOffset: -150,
    },
  ) {
    super(scene, scene.scale.width / 2 + config.xOffset, scene.scale.height - config.yOffset);
    scene.add.existing(this);

    this.createDeckVisuals();
    this.createDiscardVisuals();
  }

  /**
   * Создаёт визуальное отображение колоды
   */
  private createDeckVisuals(): void {
    const { cardWidth, cardHeight } = this.config;

    this.deckGraphics = new Phaser.GameObjects.Graphics(this.scene);

    // Рисуем "стопку" карт
    for (let i = 0; i < 3; i++) {
      const offset = i * 2;
      this.deckGraphics.fillStyle(0x2c3e50, 1);
      this.deckGraphics.fillRoundedRect(
        -cardWidth / 2 - offset,
        -cardHeight / 2 - offset,
        cardWidth,
        cardHeight,
        4,
      );
    }

    // Верхняя карта с рубашкой
    this.deckGraphics.fillStyle(0x34495e, 1);
    this.deckGraphics.fillRoundedRect(
      -cardWidth / 2,
      -cardHeight / 2,
      cardWidth,
      cardHeight,
      4,
    );

    // Узор на рубашке
    this.drawDeckPattern(this.deckGraphics, cardWidth, cardHeight);

    // Рамка
    this.deckGraphics.lineStyle(2, 0x4ecca3, 0.8);
    this.deckGraphics.strokeRoundedRect(
      -cardWidth / 2,
      -cardHeight / 2,
      cardWidth,
      cardHeight,
      4,
    );

    this.add(this.deckGraphics);

    // Текст с количеством карт
    this.deckCountText = new Phaser.GameObjects.Text(this.scene, 0, cardHeight / 2 + 20, '0', {
      fontSize: '18px',
      color: '#ffffff',
      fontStyle: 'bold',
    });
    this.deckCountText.setOrigin(0.5);
    this.add(this.deckCountText);

    // Делаем колоду интерактивной
    this.deckGraphics.setInteractive(
      new Phaser.Geom.Rectangle(
        -cardWidth / 2,
        -cardHeight / 2,
        cardWidth,
        cardHeight,
      ),
      Phaser.Geom.Rectangle.Contains,
    );

    this.deckGraphics.on('pointerdown', () => {
      this.emit('deck-clicked', this.playerId);
    });

    this.deckGraphics.on('pointerover', () => {
      this.scene.tweens.add({
        targets: this.deckGraphics,
        scale: 1.05,
        duration: 100,
      });
    });

    this.deckGraphics.on('pointerout', () => {
      this.scene.tweens.add({
        targets: this.deckGraphics,
        scale: 1,
        duration: 100,
      });
    });
  }

  /**
   * Создаёт визуальное отображение сброса
   */
  private createDiscardVisuals(): void {
    const { cardWidth, cardHeight, spacing } = this.config;

    // Контейнер для сброса
    this.discardGraphics = new Phaser.GameObjects.Graphics(this.scene);
    this.discardGraphics.setPosition(cardWidth + spacing, 0);

    // Контур (пустой сброс)
    this.discardGraphics.lineStyle(2, 0x6c5ce7, 0.3);
    this.discardGraphics.strokeRoundedRect(
      -cardWidth / 2,
      -cardHeight / 2,
      cardWidth,
      cardHeight,
      4,
    );

    this.add(this.discardGraphics);

    // Текст с количеством карт в сбросе
    this.discardCountText = new Phaser.GameObjects.Text(this.scene, cardWidth + spacing, cardHeight / 2 + 20, '0', {
      fontSize: '18px',
      color: '#6c5ce7',
      fontStyle: 'bold',
    });
    this.discardCountText.setOrigin(0.5);
    this.add(this.discardCountText);
  }

  /**
   * Рисует узор на рубашке колоды
   */
  private drawDeckPattern(graphics: Graphics, width: number, height: number): void {
    // Логотип Unmatched - упрощённый U
    graphics.lineStyle(3, 0x4ecca3, 0.5);

    const centerX = 0;
    const centerY = 0;
    const size = Math.min(width, height) * 0.4;

    // Рисуем U
    graphics.strokeRect(
      centerX - size / 2,
      centerY - size / 2,
      size,
      size,
    );

    // Добавляем декоративные элементы
    for (let i = 0; i < 4; i++) {
      const angle = (Math.PI / 4) * i;
      const x1 = centerX + Math.cos(angle) * size * 0.6;
      const y1 = centerY + Math.sin(angle) * size * 0.6;
      const x2 = centerX + Math.cos(angle) * size * 0.8;
      const y2 = centerY + Math.sin(angle) * size * 0.8;

      graphics.lineStyle(1, 0x4ecca3, 0.3);
      graphics.lineBetween(x1, y1, x2, y2);
    }
  }

  /**
   * Отрисовывает колоду и сброс
   */
  renderDeck(deckCount: number, discardCount: number): void {
    this.updateDeckCount(deckCount);
    this.updateDiscardCount(discardCount);
    this.updateDiscardVisual(discardCount > 0);
  }

  /**
   * Обновляет количество карт в колоде
   */
  updateDeckCount(count: number): void {
    this.deckCount = count;
    this.deckCountText.setText(count.toString());

    // Анимация изменения
    this.scene.tweens.add({
      targets: this.deckCountText,
      scale: 1.3,
      alpha: 0.5,
      duration: 100,
      yoyo: true,
    });
  }

  /**
   * Обновляет количество карт в сбросе
   */
  updateDiscardCount(count: number): void {
    this.discardCount = count;
    this.discardCountText.setText(count.toString());

    // Анимация изменения
    this.scene.tweens.add({
      targets: this.discardCountText,
      scale: 1.3,
      alpha: 0.5,
      duration: 100,
      yoyo: true,
    });
  }

  /**
   * Обновляет визуальное отображение сброса
   */
  private updateDiscardVisual(hasCards: boolean): void {
    const { cardWidth, cardHeight } = this.config;

    this.discardGraphics.clear();

    if (hasCards) {
      // Показываем верхнюю карту сброса (лицом вниз, так как сброс скрыт)
      this.discardGraphics.fillStyle(0x6c5ce7, 0.8);
      this.discardGraphics.fillRoundedRect(
        -cardWidth / 2,
        -cardHeight / 2,
        cardWidth,
        cardHeight,
        4,
      );

      this.discardGraphics.lineStyle(2, 0x9b59b6, 0.8);
      this.discardGraphics.strokeRoundedRect(
        -cardWidth / 2,
        -cardHeight / 2,
        cardWidth,
        cardHeight,
        4,
      );

      // Показываем, что там несколько карт
      for (let i = 0; i < Math.min(this.discardCount, 3); i++) {
        const offset = i * 1;
        this.discardGraphics.lineStyle(1, 0x9b59b6, 0.3);
        this.discardGraphics.strokeRoundedRect(
          -cardWidth / 2 - offset,
          -cardHeight / 2 - offset,
          cardWidth,
          cardHeight,
          4,
        );
      }
    } else {
      // Пустой контур
      this.discardGraphics.lineStyle(2, 0x6c5ce7, 0.3);
      this.discardGraphics.strokeRoundedRect(
        -cardWidth / 2,
        -cardHeight / 2,
        cardWidth,
        cardHeight,
        4,
      );
    }
  }

  /**
   * Анимация вытягивания карты
   */
  async animateDraw(): Promise<void> {
    return new Promise(resolve => {
      // Создаём временную карту
      const tempCard = new Phaser.GameObjects.Graphics(this.scene);
      const { cardWidth, cardHeight } = this.config;

      tempCard.fillStyle(0x4ecca3, 1);
      tempCard.fillRoundedRect(-cardWidth / 2, -cardHeight / 2, cardWidth, cardHeight, 4);

      this.add(tempCard);

      // Анимация вылета из колоды
      this.scene.tweens.add({
        targets: tempCard,
        y: -100,
        alpha: 0,
        scale: 0.5,
        duration: 300,
        ease: 'Power2.easeIn',
        onComplete: () => {
          tempCard.destroy();
          resolve();
        },
      });
    });
  }

  /**
   * Анимация сброса карты
   */
  async animateDiscard(): Promise<void> {
    return new Promise(resolve => {
      // Создаём временную карту
      const tempCard = new Phaser.GameObjects.Graphics(this.scene);
      const { cardWidth, cardHeight, spacing } = this.config;

      tempCard.setPosition(cardWidth + spacing, -50);
      tempCard.fillStyle(0x6c5ce7, 1);
      tempCard.fillRoundedRect(-cardWidth / 2, -cardHeight / 2, cardWidth, cardHeight, 4);

      this.add(tempCard);

      // Анимация падения в сброс
      this.scene.tweens.add({
        targets: tempCard,
        y: 0,
        alpha: 0.8,
        duration: 300,
        ease: 'Bounce.easeOut',
        onComplete: () => {
          tempCard.destroy();
          resolve();
        },
      });
    });
  }

  /**
   * Обновляет позицию при изменении размера экрана
   */
  updatePosition(): void {
    this.setPosition(
      this.scene.scale.width / 2 + this.config.xOffset,
      this.scene.scale.height - this.config.yOffset,
    );
  }

  /**
   * Получает текущее количество карт в колоде
   */
  getDeckCount(): number {
    return this.deckCount;
  }

  /**
   * Получает текущее количество карт в сбросе
   */
  getDiscardCount(): number {
    return this.discardCount;
  }

  /**
   * Уничтожает рендерер
   */
  destroy(): void {
    this.deckGraphics?.destroy();
    this.discardGraphics?.destroy();
    this.deckCountText?.destroy();
    this.discardCountText?.destroy();
    super.destroy();
  }
}
