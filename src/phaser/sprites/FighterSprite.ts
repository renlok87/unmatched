// ============================================================
// FIGHTER SPRITE - Визуальное представление бойца на игровом поле
// ============================================================

import * as Phaser from 'phaser';
import type { Fighter } from '../../core/models/types';

// ------------------------------------------------------------
// Интерфейс для конфигурации спрайта бойца
// ------------------------------------------------------------

export interface FighterSpriteConfig {
  fighter: Fighter;
  x: number;
  y: number;
  scale?: number;
  frameWidth?: number;
  frameHeight?: number;
}

// ------------------------------------------------------------
// Типы состояний анимации бойца
// ------------------------------------------------------------

export enum FighterAnimationState {
  IDLE = 'idle',
  WALK = 'walk',
  ATTACK = 'attack',
  HIT = 'hit',
  BLOCK = 'block',
  DEATH = 'death',
  SPECIAL = 'special',
}

// ------------------------------------------------------------
// FighterSprite - расширенный спрайт бойца с дополнительной функциональностью
// ------------------------------------------------------------

export class FighterSprite extends Phaser.GameObjects.Container {
  // Основные данные
  public readonly fighterId: string;
  public readonly ownerId: string;
  public health: number;
  public readonly maxHealth: number;

  // Визуальные компоненты (публичные для использования в анимациях)
  public bodySprite: Phaser.GameObjects.Sprite;
  public shadowSprite: Phaser.GameObjects.Ellipse;
  private healthBarBackground: Phaser.GameObjects.Rectangle;
  private healthBarFill: Phaser.GameObjects.Rectangle;
  private healthText: Phaser.GameObjects.Text;
  private selectionRing: Phaser.GameObjects.Graphics;
  private statusIcons: Phaser.GameObjects.Container;

  // Состояние анимации
  private currentAnimationState: FighterAnimationState = FighterAnimationState.IDLE;
  private isAnimating: boolean = false;

  // Модификаторы
  private damageBoostModifier: number = 0;
  private damageReductionModifier: number = 0;

  // Колбэки
  public onClick?: (sprite: FighterSprite) => void;

  constructor(
    scene: Phaser.Scene,
    config: FighterSpriteConfig
  ) {
    super(scene, config.x, config.y);

    this.fighterId = config.fighter.id;
    this.ownerId = config.fighter.ownerId;
    this.health = config.fighter.health;
    this.maxHealth = config.fighter.maxHealth;

    // Создаём визуальные компоненты
    this.createComponents(config);

    // Добавляем интерактивность
    this.setupInteractivity();

    // Добавляем контейнер на сцену
    scene.add.existing(this);

    // Запускаем idle анимацию
    this.playAnimation(FighterAnimationState.IDLE);
  }

  // ------------------------------------------------------------
  // Создание визуальных компонентов
  // ------------------------------------------------------------

  private createComponents(config: FighterSpriteConfig): void {
    const scale = config.scale || 1;

    // Тень под бойцом
    this.shadowSprite = this.scene.add.ellipse(0, 20, 40 * scale, 15 * scale, 0x000000, 0.3);
    this.add(this.shadowSprite);

    // Основной спрайт бойца
    const spriteKey = `fighter-${config.fighter.definitionId}`;
    this.bodySprite = this.scene.add.sprite(0, 0, spriteKey || 'fighter-placeholder');
    this.bodySprite.setScale(scale);
    this.add(this.bodySprite);

    // Кольцо выделения (изначально скрыто)
    this.selectionRing = this.scene.add.graphics();
    this.selectionRing.setVisible(false);
    this.add(this.selectionRing);

    // Панель здоровья
    this.createHealthBar(scale);

    // Контейнер для иконок статусов
    this.statusIcons = this.scene.add.container(30 * scale, -30 * scale);
    this.add(this.statusIcons);
  }

  private createHealthBar(scale: number): void {
    const barWidth = 50 * scale;
    const barHeight = 6 * scale;
    const yOffset = -40 * scale;

    // Фон полоски здоровья
    this.healthBarBackground = this.scene.add.rectangle(
      0, yOffset, barWidth, barHeight, 0x333333
    );
    this.healthBarBackground.setOrigin(0.5);
    this.add(this.healthBarBackground);

    // Заполнение полоски здоровья
    this.healthBarFill = this.scene.add.rectangle(
      -barWidth / 2, yOffset, barWidth, barHeight, 0x4ecca3
    );
    this.healthBarFill.setOrigin(0, 0.5);
    this.add(this.healthBarFill);

    // Текст здоровья
    this.healthText = this.scene.add.text(
      0, yOffset - 12 * scale,
      `${this.health}/${this.maxHealth}`,
      {
        fontSize: `${12 * scale}px`,
        color: '#ffffff',
        fontStyle: 'bold',
        stroke: '#000000',
        strokeThickness: 3,
      }
    );
    this.healthText.setOrigin(0.5);
    this.add(this.healthText);
  }

  // ------------------------------------------------------------
  // Настройка интерактивности
  // ------------------------------------------------------------

  private setupInteractivity(): void {
    // Делаем контейнер интерактивным
    this.setSize(60, 80);
    this.setInteractive();

    // Обработчики событий
    this.on('pointerdown', this.handleClick.bind(this));
    this.on('pointerover', this.handleHover.bind(this));
    this.on('pointerout', this.handleHoverEnd.bind(this));
  }

  private handleClick(): void {
    if (this.onClick) {
      this.onClick(this);
    }
  }

  private handleHover(): void {
    this.setSelectionTint(0xffff00);
  }

  private handleHoverEnd(): void {
    this.setSelectionTint(0xffffff);
  }

  // ------------------------------------------------------------
  // Методы обновления состояния
  // ------------------------------------------------------------

  /**
   * Обновляет отображение здоровья
   */
  public updateHealth(newHealth: number, animate: boolean = true): void {
    const oldHealth = this.health;
    this.health = Math.max(0, Math.min(newHealth, this.maxHealth));

    // Анимация изменения полоски здоровья
    if (animate && this.scene) {
      this.scene.tweens.add({
        targets: this.healthBarFill,
        width: (50 * (this.health / this.maxHealth)),
        duration: 300,
        ease: Phaser.Math.Easing.Quadratic.Out,
      });
    } else {
      this.healthBarFill.width = 50 * (this.health / this.maxHealth);
    }

    // Обновляем текст
    this.healthText.setText(`${this.health}/${this.maxHealth}`);

    // Меняем цвет при низком здоровье
    if (this.health <= this.maxHealth * 0.3) {
      this.healthBarFill.setFillStyle(0xff4444);
    } else if (this.health <= this.maxHealth * 0.6) {
      this.healthBarFill.setFillStyle(0xffaa44);
    } else {
      this.healthBarFill.setFillStyle(0x4ecca3);
    }
  }

  /**
   * Показывает/скрывает кольцо выделения
   */
  public setSelected(selected: boolean, color: number = 0x4ecca3): void {
    this.selectionRing.setVisible(selected);
    if (selected) {
      this.drawSelectionRing(color);
    }
  }

  private drawSelectionRing(color: number): void {
    this.selectionRing.clear();
    this.selectionRing.lineStyle(3, color, 1);
    this.selectionRing.strokeCircle(0, 0, 40);
  }

  private setSelectionTint(color: number): void {
    this.bodySprite.setTint(color);
  }

  // ------------------------------------------------------------
  // Методы анимации
  // ------------------------------------------------------------

  /**
   * Проигрывает указанную анимацию
   */
  public playAnimation(state: FighterAnimationState, onComplete?: () => void): void {
    this.currentAnimationState = state;
    this.isAnimating = true;

    switch (state) {
      case FighterAnimationState.IDLE:
        this.playIdleAnimation();
        break;
      case FighterAnimationState.WALK:
        this.playWalkAnimation(onComplete);
        break;
      case FighterAnimationState.ATTACK:
        this.playAttackAnimation(onComplete);
        break;
      case FighterAnimationState.HIT:
        this.playHitAnimation(onComplete);
        break;
      case FighterAnimationState.BLOCK:
        this.playBlockAnimation(onComplete);
        break;
      case FighterAnimationState.DEATH:
        this.playDeathAnimation(onComplete);
        break;
      case FighterAnimationState.SPECIAL:
        this.playSpecialAnimation(onComplete);
        break;
    }
  }

  private playIdleAnimation(): void {
    // Небольшое "дыхание" - покачивание вверх-вниз
    this.scene.tweens.add({
      targets: this.bodySprite,
      y: -2,
      duration: 1000,
      yoyo: true,
      repeat: -1,
      ease: Phaser.Math.Easing.Sine.InOut,
      onComplete: () => {
        this.isAnimating = false;
      },
    });
  }

  private playWalkAnimation(onComplete?: () => void): void {
    // Покачивание при ходьбе
    this.scene.tweens.add({
      targets: this.bodySprite,
      y: -5,
      rotation: 0.1,
      duration: 200,
      yoyo: true,
      repeat: 2,
      ease: Phaser.Math.Easing.Sine.InOut,
      onComplete: () => {
        this.isAnimating = false;
        if (onComplete) onComplete();
      },
    });
  }

  private playAttackAnimation(onComplete?: () => void): void {
    const originalX = this.bodySprite.x;

    this.scene.tweens.add({
      targets: this.bodySprite,
      x: originalX + 20,
      duration: 100,
      ease: Phaser.Math.Easing.Quadratic.Out,
      yoyo: true,
      onComplete: () => {
        this.bodySprite.x = originalX;
        this.isAnimating = false;
        if (onComplete) onComplete();
      },
    });
  }

  private playHitAnimation(onComplete?: () => void): void {
    // Мигание красным и отскок назад
    this.bodySprite.setTint(0xff0000);

    this.scene.tweens.add({
      targets: this.bodySprite,
      x: this.bodySprite.x - 10,
      duration: 100,
      ease: Phaser.Math.Easing.Back.Out,
      yoyo: true,
      onComplete: () => {
        this.bodySprite.clearTint();
        this.isAnimating = false;
        if (onComplete) onComplete();
      },
    });
  }

  private playBlockAnimation(onComplete?: () => void): void {
    // Небольшой подъём щита (покачивание назад)
    this.scene.tweens.add({
      targets: this.bodySprite,
      scaleX: 0.9,
      duration: 150,
      yoyo: true,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => {
        this.isAnimating = false;
        if (onComplete) onComplete();
      },
    });
  }

  private playDeathAnimation(onComplete?: () => void): void {
    // Падение и исчезновение
    this.bodySprite.setTint(0x666666);

    this.scene.tweens.add({
      targets: [this.bodySprite, this.shadowSprite],
      alpha: 0,
      rotation: Math.PI / 4,
      y: 20,
      duration: 1000,
      ease: Phaser.Math.Easing.Quadratic.In,
      onComplete: () => {
        this.isAnimating = false;
        if (onComplete) onComplete();
      },
    });
  }

  private playSpecialAnimation(onComplete?: () => void): void {
    // Свечение для специальной атаки
    const glow = this.scene.add.graphics();
    glow.lineStyle(4, 0xffff00, 0.8);
    glow.strokeCircle(0, 0, 45);
    this.add(glow);

    this.scene.tweens.add({
      targets: glow,
      alpha: 0,
      scale: 1.5,
      duration: 500,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => {
        glow.destroy();
        this.isAnimating = false;
        if (onComplete) onComplete();
      },
    });
  }

  // ------------------------------------------------------------
  // Модификаторы и эффекты
  // ------------------------------------------------------------

  /**
   * Добавляет временный модификатор урона
   */
  public addDamageBoost(amount: number): void {
    this.damageBoostModifier += amount;
    this.updateStatusIcons();
  }

  /**
   * Добавляет модификатор защиты
   */
  public addDamageReduction(amount: number): void {
    this.damageReductionModifier += amount;
    this.updateStatusIcons();
  }

  /**
   * Очищает все модификаторы
   */
  public clearModifiers(): void {
    this.damageBoostModifier = 0;
    this.damageReductionModifier = 0;
    this.updateStatusIcons();
  }

  private updateStatusIcons(): void {
    this.statusIcons.removeAll(true);

    // Иконка бонуса урона (меч)
    if (this.damageBoostModifier > 0) {
      const swordIcon = this.scene.add.text(0, 0, '⚔️', { fontSize: '16px' });
      swordIcon.setText(`+${this.damageBoostModifier}`);
      this.statusIcons.add(swordIcon);
    }

    // Иконка защиты (щит)
    if (this.damageReductionModifier > 0) {
      const shieldIcon = this.scene.add.text(0, 20, '🛡️', { fontSize: '16px' });
      shieldIcon.setText(`-${this.damageReductionModifier}`);
      this.statusIcons.add(shieldIcon);
    }
  }

  // ------------------------------------------------------------
  // Утилиты
  // ------------------------------------------------------------

  /**
   * Получает текущую позицию в координатах мира
   */
  public getWorldPosition(): Phaser.Math.Vector2 {
    return new Phaser.Math.Vector2(this.x, this.y);
  }

  /**
   * Проверяет, анимируется ли боец в данный момент
   */
  public isPlayingAnimation(): boolean {
    return this.isAnimating;
  }

  /**
   * Останавливает все анимации
   */
  public stopAllAnimations(): void {
    this.scene.tweens.killTweensOf(this.bodySprite);
    this.scene.tweens.killTweensOf(this.shadowSprite);
    this.bodySprite.clearTint();
    this.bodySprite.setPosition(0, 0);
    this.bodySprite.setRotation(0);
    this.bodySprite.setAlpha(1);
    this.shadowSprite.setAlpha(0.3);
    this.isAnimating = false;
  }

  /**
   * Уничтожает спрайт и все его компоненты
   */
  public destroy(fromScene?: boolean): void {
    this.stopAllAnimations();
    super.destroy(fromScene);
  }
}
