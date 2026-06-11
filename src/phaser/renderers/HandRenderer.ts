/**
 * HandRenderer
 *
 * Отрисовывает руку игрока с картами.
 * Управляет расположением, анимациями и интерактивностью карт.
 */

import Phaser from 'phaser';
import type { CardInstance } from '../../core/models/types';
import { CardSprite, CardTypeColors } from '../sprites/CardSprite';

/**
 * Конфигурация руки
 */
export interface HandConfig {
  maxSize: number;
  cardWidth: number;
  cardHeight: number;
  cardOverlap: number;
  yOffset: number;
  spacing: number;
}

/**
 * Рендерер руки игрока
 */
export class HandRenderer extends Phaser.GameObjects.Container {
  private cards: Map<string, CardSprite> = new Map();
  private cardSprites: CardSprite[] = [];
  private background: Phaser.GameObjects.Graphics;
  private playableCards: Set<string> = new Set();

  constructor(
    scene: Phaser.Scene,
    public readonly playerId: string,
    private config: HandConfig = {
      maxSize: 5,
      cardWidth: 120,
      cardHeight: 170,
      cardOverlap: 80,
      yOffset: 0,
      spacing: 10,
    },
  ) {
    super(scene, 0, scene.scale.height - config.yOffset);
    scene.add.existing(this);

    this.createBackground();
  }

  /**
   * Создаёт фон руки
   */
  private createBackground(): void {
    this.background = new Phaser.GameObjects.Graphics(this.scene);
    this.add(this.background);
    this.updateBackground();
  }

  /**
   * Обновляет фон в зависимости от количества карт
   */
  private updateBackground(): void {
    const { cardWidth, cardOverlap, maxSize } = this.config;
    const totalWidth = (maxSize - 1) * (cardWidth - cardOverlap) + cardWidth;
    const height = this.config.cardHeight + 20;

    this.background.clear();
    this.background.fillStyle(0x1a1a2e, 0.8);
    this.background.fillRoundedRect(
      -totalWidth / 2 - 20,
      -height / 2,
      totalWidth + 40,
      height,
      15,
    );

    this.background.lineStyle(2, 0x4ecca3, 0.5);
    this.background.strokeRoundedRect(
      -totalWidth / 2 - 20,
      -height / 2,
      totalWidth + 40,
      height,
      15,
    );
  }

  /**
   * Отрисовывает руку с картами
   */
  renderHand(cards: readonly CardInstance[]): void {
    // Удаляем старые карты
    this.clearHand();

    // Добавляем новые карты
    cards.forEach((card, index) => {
      this.addCard(card, index);
    });
  }

  /**
   * Добавляет карту в руку
   */
  async addCard(card: CardInstance, index?: number): Promise<void> {
    if (this.cards.has(card.id)) {
      return;
    }

    const cardSprite = new CardSprite(this.scene, 0, 0, card);
    this.cards.set(card.id, cardSprite);
    this.cardSprites.push(cardSprite);
    this.add(cardSprite);

    // Подписываемся на события карты
    cardSprite.on('card-clicked', (cardId: string) => {
      this.emit('card-clicked', cardId);
    });

    // Если указан индекс, перемещаем карту
    if (index !== undefined) {
      await this.arrangeCards();
    } else {
      await this.arrangeCards();
    }
  }

  /**
   * Удаляет карту из руки
   */
  async removeCard(cardId: string): Promise<void> {
    const cardSprite = this.cards.get(cardId);
    if (!cardSprite) return;

    // Анимация удаления
    await this.animateCardRemoval(cardSprite);

    // Удаляем из контейнера
    this.cards.delete(cardId);
    this.cardSprites = this.cardSprites.filter(c => c.card.id !== cardId);
    cardSprite.destroy();

    // Пересобираем карты
    await this.arrangeCards();
  }

  /**
   * Анимация удаления карты
   */
  private async animateCardRemoval(cardSprite: CardSprite): Promise<void> {
    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: cardSprite,
        scale: 0.5,
        alpha: 0,
        y: cardSprite.y - 100,
        duration: 200,
        ease: 'Power2.easeIn',
        onComplete: () => resolve(),
      });
    });
  }

  /**
   * Обновляет данные карты
   */
  updateCard(card: CardInstance): void {
    const cardSprite = this.cards.get(card.id);
    if (cardSprite) {
      cardSprite.updateCardData(card);
    }
  }

  /**
   * Подсвечивает играбельные карты
   */
  highlightPlayableCards(playable: readonly string[]): void {
    this.playableCards = new Set(playable);

    this.cardSprites.forEach(cardSprite => {
      const isPlayable = this.playableCards.has(cardSprite.card.id);
      cardSprite.setDisabled(!isPlayable);
    });
  }

  /**
   * Устанавливает кликабельность карт
   */
  setCardClickable(clickable: boolean): void {
    this.cardSprites.forEach(cardSprite => {
      if (clickable) {
        cardSprite.setInteractive();
      } else {
        cardSprite.disableInteractive();
      }
    });
  }

  /**
   * Выбирает карту
   */
  selectCard(cardId: string): void {
    // Снимаем выбор со всех карт
    this.cardSprites.forEach(card => card.setSelected(false));

    // Выбираем указанную карту
    const cardSprite = this.cards.get(cardId);
    if (cardSprite) {
      cardSprite.setSelected(true);
      this.emit('card-selected', cardId);
    }
  }

  /**
   * Снимает выбор с карт
   */
  deselectAll(): void {
    this.cardSprites.forEach(card => card.setSelected(false));
  }

  /**
   * Получает выбранную карту
   */
  getSelectedCard(): CardInstance | null {
    const selected = this.cardSprites.find(c => c.isSelected);
    return selected?.card || null;
  }

  /**
   * Располагает карты в ряд с перекрытием
   */
  private async arrangeCards(): Promise<void> {
    const { cardWidth, cardOverlap } = this.config;
    const totalWidth = (this.cardSprites.length - 1) * (cardWidth - cardOverlap);
    const startX = -totalWidth / 2;

    const promises = this.cardSprites.map((cardSprite, index) => {
      const targetX = startX + index * (cardWidth - cardOverlap);
      return new Promise<void>(resolve => {
        this.scene.tweens.add({
          targets: cardSprite,
          x: targetX,
          duration: 200,
          ease: 'Power2.easeOut',
          onComplete: () => resolve(),
        });
      });
    });

    await Promise.all(promises);
  }

  /**
   * Очищает руку
   */
  private clearHand(): void {
    this.cardSprites.forEach(card => card.destroy());
    this.cards.clear();
    this.cardSprites = [];
  }

  /**
   * Обновляет позицию руки при изменении размера экрана
   */
  updatePosition(): void {
    this.setPosition(0, this.scene.scale.height - this.config.yOffset);
  }

  /**
   * Получает количество карт в руке
   */
  getCardCount(): number {
    return this.cards.size;
  }

  /**
   * Проверяет, заполнена ли рука
   */
  isFull(): boolean {
    return this.cards.size >= this.config.maxSize;
  }

  /**
   * Уничтожает рендерер
   */
  destroy(): void {
    this.clearHand();
    this.background?.destroy();
    super.destroy();
  }
}
