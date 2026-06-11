/**
 * CardSprite
 *
 * Визуальное представление карты в игре.
 * Поддерживает анимации розыгрыша, hover эффекты и подсветку.
 */

import Phaser from 'phaser';
import type { CardInstance } from '../../core/models/types';

/**
 * Конфигурация визуального стиля карты
 */
export interface CardStyleConfig {
  width: number;
  height: number;
  borderRadius: number;
  borderWidth: number;
  fontSize: number;
}

/**
 * Цвета для разных типов карт
 */
export enum CardTypeColors {
  ATTACK = 0xff6b6b,      // Красный
  DEFENSE = 0x4ecdc4,     // Голубой
  MANEUVER = 0x95e1d3,    // Зелёный
  SCHEME = 0x9b59b6,      // Фиолетовый
  UNIVERSAL = 0xf39c12,   // Оранжевый
  BOOST = 0xf1c40f,       // Золотой
}

/**
 * Sprite карты с интерактивными эффектами
 */
export class CardSprite extends Phaser.GameObjects.Container {
  private cardBg: Phaser.GameObjects.Graphics;
  private cardBorder: Phaser.GameObjects.Graphics;
  private titleText: Phaser.GameObjects.Text;
  private valueText: Phaser.GameObjects.Text | null = null;
  private glowEffect: Phaser.GameObjects.Graphics;
  private isHovered: boolean = false;
  private isSelected: boolean = false;
  private baseScale: number = 1;

  constructor(
    scene: Phaser.Scene,
    x: number,
    y: number,
    public readonly card: CardInstance,
    private style: CardStyleConfig = {
      width: 120,
      height: 170,
      borderRadius: 8,
      borderWidth: 3,
      fontSize: 14,
    },
  ) {
    super(scene, x, y);

    this.baseScale = 1;
    this.createCardVisuals();
    this.setupInteractions();
    scene.add.existing(this);
  }

  /**
   * Создаёт визуальные элементы карты
   */
  private createCardVisuals(): void {
    const { width, height, borderRadius } = this.style;

    // Фон карты
    this.cardBg = new Phaser.GameObjects.Graphics(this.scene);
    this.drawCardBackground(this.cardBg, this.getCardColor());
    this.add(this.cardBg);

    // Рамка карты
    this.cardBorder = new Phaser.GameObjects.Graphics(this.scene);
    this.drawCardBorder(this.cardBorder, 0xffffff);
    this.add(this.cardBorder);

    // Название карты
    this.titleText = new Phaser.GameObjects.Text(this.scene, 0, -height / 2 + 25, this.card.name, {
      fontSize: `${this.style.fontSize}px`,
      color: '#ffffff',
      fontStyle: 'bold',
      align: 'center',
      wordWrap: { width: width - 20 },
    });
    this.titleText.setOrigin(0.5);
    this.add(this.titleText);

    // Значения атаки/защиты
    if (this.card.attackValue !== undefined || this.card.defenseValue !== undefined) {
      const valueText = this.formatCardValues();
      this.valueText = new Phaser.GameObjects.Text(this.scene, 0, 0, valueText, {
        fontSize: '24px',
        color: '#ffffff',
        fontStyle: 'bold',
      });
      this.valueText.setOrigin(0.5);
      this.add(this.valueText);
    }

    // Эффект подсветки (изначально скрыт)
    this.glowEffect = new Phaser.GameObjects.Graphics(this.scene);
    this.glowEffect.setVisible(false);
    this.add(this.glowEffect);

    // Размер контейнера
    this.setSize(width, height);
  }

  /**
   * Рисует фон карты
   */
  private drawCardBackground(graphics: Phaser.GameObjects.Graphics, color: number): void {
    const { width, height, borderRadius } = this.style;

    graphics.clear();
    graphics.fillStyle(color, 1);

    // Рисуем скруглённый прямоугольник
    graphics.fillRoundedRect(
      -width / 2,
      -height / 2,
      width,
      height,
      borderRadius,
    );
  }

  /**
   * Рисует рамку карты
   */
  private drawCardBorder(graphics: Phaser.GameObjects.Graphics, color: number): void {
    const { width, height, borderRadius, borderWidth } = this.style;

    graphics.clear();
    graphics.lineStyle(borderWidth, color, 1);
    graphics.strokeRoundedRect(
      -width / 2,
      -height / 2,
      width,
      height,
      borderRadius,
    );
  }

  /**
   * Получает цвет карты по её типу
   */
  private getCardColor(): number {
    switch (this.card.cardType) {
      case 'ATTACK':
        return CardTypeColors.ATTACK;
      case 'DEFENSE':
        return CardTypeColors.DEFENSE;
      case 'MANEUVER':
        return CardTypeColors.MANEUVER;
      case 'SCHEME':
        return CardTypeColors.SCHEME;
      case 'UNIVERSAL':
        return CardTypeColors.UNIVERSAL;
      default:
        return 0x34495e;
    }
  }

  /**
   * Форматирует значения карты для отображения
   */
  private formatCardValues(): string {
    const parts: string[] = [];

    if (this.card.attackValue !== undefined) {
      parts.push(`⚔${this.card.attackValue}`);
    }
    if (this.card.defenseValue !== undefined) {
      parts.push(`🛡${this.card.defenseValue}`);
    }
    if (this.card.boostValue !== undefined) {
      parts.push(`⚡${this.card.boostValue}`);
    }

    return parts.join(' / ');
  }

  /**
   * Настраивает интерактивность карты
   */
  private setupInteractions(): void {
    // Делаем карту интерактивной
    this.cardBg.setInteractive(
      new Phaser.GameObjects.Rectangle(
        this.scene,
        -this.style.width / 2,
        -this.style.height / 2,
        this.style.width,
        this.style.height,
      ),
      Phaser.GameObjects.Rectangle.Shape,
    );

    // Hover эффекты
    this.cardBg.on('pointerover', this.onHoverStart.bind(this));
    this.cardBg.on('pointerout', this.onHoverEnd.bind(this));
    this.cardBg.on('pointerdown', this.onClick.bind(this));
  }

  /**
   * Начало hover эффекта
   */
  private onHoverStart(): void {
    if (this.isHovered) return;
    this.isHovered = true;

    this.scene.tweens.add({
      targets: this,
      scale: this.baseScale * 1.1,
      duration: 150,
      ease: 'Power2',
    });
  }

  /**
   * Конец hover эффекта
   */
  private onHoverEnd(): void {
    if (!this.isHovered) return;
    this.isHovered = false;

    if (!this.isSelected) {
      this.scene.tweens.add({
        targets: this,
        scale: this.baseScale,
        duration: 150,
        ease: 'Power2',
      });
    }
  }

  /**
   * Клик по карте
   */
  private onClick(): void {
    this.emit('card-clicked', this.card.id);
  }

  /**
   * Устанавливает выбранное состояние карты
   */
  setSelected(selected: boolean): void {
    this.isSelected = selected;

    if (selected) {
      this.scene.tweens.add({
        targets: this,
        scale: this.baseScale * 1.15,
        y: this.y - 20,
        duration: 200,
        ease: 'Back.easeOut',
      });

      // Показываем свечение
      this.glowEffect.setVisible(true);
      this.glowEffect.clear();
      this.glowEffect.lineStyle(4, 0xffd700, 0.8);
      this.glowEffect.strokeRoundedRect(
        -this.style.width / 2 - 4,
        -this.style.height / 2 - 4,
        this.style.width + 8,
        this.style.height + 8,
        this.style.borderRadius + 4,
      );
    } else {
      this.scene.tweens.add({
        targets: this,
        scale: this.baseScale,
        y: this.y,
        duration: 200,
        ease: 'Power2',
      });

      this.glowEffect.setVisible(false);
    }
  }

  /**
   * Устанавливает базовый масштаб
   */
  setBaseScale(scale: number): void {
    this.baseScale = scale;
    if (!this.isSelected && !this.isHovered) {
      this.setScale(scale);
    }
  }

  /**
   * Анимация добавления карты в руку
   */
  async playToHandAnimation(index: number): Promise<void> {
    const targetX = this.x;
    const startY = this.y - 200;

    this.setPosition(targetX, startY);
    this.setAlpha(0);

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: this,
        y: targetX,
        alpha: 1,
        duration: 300,
        delay: index * 100,
        ease: 'Power2.easeOut',
        onComplete: () => resolve(),
      });
    });
  }

  /**
   * Анимация розыгрыша карты
   */
  async playPlayAnimation(): Promise<void> {
    return new Promise(resolve => {
      // Увеличиваем и fade out
      this.scene.tweens.add({
        targets: this,
        scale: this.baseScale * 1.5,
        alpha: 0,
        duration: 400,
        ease: 'Power2.easeIn',
        onComplete: () => {
          this.destroy();
          resolve();
        },
      });

      // Создаём частицы
      this.createPlayParticles();
    });
  }

  /**
   * Создаёт частицы при розыгрыше
   */
  private createPlayParticles(): void {
    const particles = this.scene.add.particles(0, 0, 'particle', {
      speed: { min: 50, max: 150 },
      scale: { start: 0.5, end: 0 },
      alpha: { start: 1, end: 0 },
      lifespan: 500,
      quantity: 20,
      tint: this.getCardColor(),
    });

    setTimeout(() => particles.destroy(), 500);
  }

  /**
   * Обновляет данные карты
   */
  updateCardData(card: CardInstance): void {
    (this.card as any) = card;

    this.titleText.setText(card.name);

    if (this.valueText) {
      this.valueText.setText(this.formatCardValues());
    }
  }

  /**
   * Затеняет карту (недоступна для игры)
   */
  setDisabled(disabled: boolean): void {
    if (disabled) {
      this.setAlpha(0.5);
      this.cardBg.disableInteractive();
    } else {
      this.setAlpha(1);
      this.cardBg.setInteractive();
    }
  }

  /**
   * Уничтожает спрайт
   */
  destroy(): void {
    this.cardBg?.destroy();
    this.cardBorder?.destroy();
    this.titleText?.destroy();
    this.valueText?.destroy();
    this.glowEffect?.destroy();
    super.destroy();
  }
}
