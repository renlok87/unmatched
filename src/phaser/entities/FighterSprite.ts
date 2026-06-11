// ============================================================
// FIGHTER SPRITE - Спрайт бойца с анимациями и здоровьем
// ============================================================

import Phaser from 'phaser';
import type { Fighter } from '../../core/models/types';
import type { GameScene } from '../renderers/BoardRenderer';

/**
 * Конфигурация отображения бойца
 */
export interface FighterDisplayConfig {
  scale: number;
  healthBarWidth: number;
  healthBarHeight: number;
  healthBarOffset: number;
  selectionColor: number;
  damageFlashDuration: number;
  animationDuration: number;
}

/**
 * События бойца
 */
export interface FighterEvents {
  'fighter:click': { fighterId: string };
  'fighter:hover': { fighterId: string };
  'fighter:animation-complete': { fighterId: string; animation: string };
}

/**
 * Спрайт бойца с панелью здоровья и анимациями
 *
 * Особенности:
 * - Пульсирующая анимация "дыхания" в idle
 * - Плавное перемещение с tween
 * - Анимация атаки (выпад вперёд)
 * - Мигание красным при получении урона
 * - Исчезновение при смерти
 * - Подсветка при выборе
 */
export class FighterSprite extends Phaser.GameObjects.Container {
  // Данные бойца
  private fighter: Fighter;
  private fighterId: string;

  // Визуальные элементы
  private sprite: Phaser.GameObjects.Sprite;
  private healthBarBg: Phaser.GameObjects.Rectangle;
  private healthBarFill: Phaser.GameObjects.Rectangle;
  private healthText: Phaser.GameObjects.Text;
  private selectionRing: Phaser.GameObjects.Rectangle;
  private shadow: Phaser.GameObjects.Ellipse;

  // Конфигурация
  private config: FighterDisplayConfig;

  // Состояние
  private isSelected: boolean = false;
  private isDead: boolean = false;
  private currentHealth: number;
  private maxHealth: number;

  // Анимации
  private idleTween?: Phaser.Tweens.Tween;
  private breathingScale: number = 1;

  constructor(scene: GameScene, x: number, y: number, fighter: Fighter, config?: Partial<FighterDisplayConfig>) {
    super(scene, x, y);

    this.fighter = fighter;
    this.fighterId = fighter.id;
    this.currentHealth = fighter.health;
    this.maxHealth = fighter.maxHealth;

    // Конфигурация по умолчанию
    this.config = {
      scale: 1,
      healthBarWidth: 60,
      healthBarHeight: 8,
      healthBarOffset: 40,
      selectionColor: 0xffd93d,
      damageFlashDuration: 300,
      animationDuration: 300,
      ...config
    };

    // Создаём визуальные элементы
    this.createShadow();
    this.createSprite();
    this.createHealthBar();
    this.createSelectionRing();

    // Устанавливаем размер контейнера для交互
    this.setSize(64, 64);
    this.setInteractive();

    // Настраиваем обработчики событий
    this.setupEvents();

    // Запускаем idle анимацию
    this.startIdleAnimation();

    // Добавляем в сцену
    scene.add.existing(this);
    this.setDepth(200); // Бойцы поверх сетки
  }

  /**
   * Создаёт тень под бойцом
   */
  private createShadow(): void {
    this.shadow = new Phaser.GameObjects.Ellipse(
      this.scene,
      0,
      25,
      40,
      15,
      0x000000,
      0.3
    );
    this.add(this.shadow);
  }

  /**
   * Создаёт спрайт бойца
   */
  private createSprite(): void {
    // Используем placeholder или загруженный спрайт
    const spriteKey = `fighter-${this.fighter.definitionId}`;
    const hasSprite = this.scene.textures.exists(spriteKey);

    this.sprite = new Phaser.GameObjects.Sprite(
      this.scene,
      0,
      0,
      hasSprite ? spriteKey : 'fighter-placeholder'
    );

    this.sprite.setScale(this.config.scale);
    this.sprite.setOrigin(0.5, 0.8); // Якorry внизу для позиционирования на клетке

    this.add(this.sprite);

    // Если есть спрайт лист, создаём анимации
    if (hasSprite) {
      this.createAnimations();
    }
  }

  /**
   * Создаёт анимации из sprite sheet
   */
  private createAnimations(): void {
    const animKey = `fighter-${this.fighter.definitionId}`;

    if (!this.scene.anims.exists(animKey)) {
      this.scene.anims.create({
        key: `${animKey}-idle`,
        frames: this.scene.anims.generateFrameNumbers(animKey, { start: 0, end: 3 }),
        frameRate: 8,
        repeat: -1
      });

      this.scene.anims.create({
        key: `${animKey}-walk`,
        frames: this.scene.anims.generateFrameNumbers(animKey, { start: 4, end: 7 }),
        frameRate: 12,
        repeat: -1
      });

      this.scene.anims.create({
        key: `${animKey}-attack`,
        frames: this.scene.anims.generateFrameNumbers(animKey, { start: 8, end: 11 }),
        frameRate: 16,
        repeat: 0
      });
    }
  }

  /**
   * Создаёт панель здоровья
   */
  private createHealthBar(): void {
    const barY = -this.config.healthBarOffset;

    // Фон панели здоровья
    this.healthBarBg = new Phaser.GameObjects.Rectangle(
      this.scene,
      0,
      barY,
      this.config.healthBarWidth,
      this.config.healthBarHeight,
      0x333333
    );
    this.healthBarBg.setStrokeStyle(1, 0x000000);
    this.add(this.healthBarBg);

    // Заполнитель здоровья
    const healthPercent = this.currentHealth / this.maxHealth;
    this.healthBarFill = new Phaser.GameObjects.Rectangle(
      this.scene,
      -this.config.healthBarWidth / 2 + 1,
      barY,
      (this.config.healthBarWidth - 2) * healthPercent,
      this.config.healthBarHeight - 2,
      this.getHealthColor(healthPercent)
    );
    this.healthBarFill.setOrigin(0, 0.5);
    this.add(this.healthBarFill);

    // Текст здоровья
    this.healthText = new Phaser.GameObjects.Text(
      this.scene,
      0,
      barY - 12,
      `${this.currentHealth}/${this.maxHealth}`,
      {
        fontSize: '12px',
        color: '#ffffff',
        fontStyle: 'bold',
        stroke: '#000000',
        strokeThickness: 3
      }
    );
    this.healthText.setOrigin(0.5);
    this.add(this.healthText);
  }

  /**
   * Создаёт кольцо выделения
   */
  private createSelectionRing(): void {
    this.selectionRing = new Phaser.GameObjects.Rectangle(
      this.scene,
      0,
      10,
      70,
      70,
      this.config.selectionColor,
      0
    );
    this.selectionRing.setStrokeStyle(3, this.config.selectionColor);
    this.selectionRing.setVisible(false);
    this.selectionRing.setDepth(-1);
    this.add(this.selectionRing);
  }

  /**
   * Настраивает обработчики событий мыши
   */
  private setupEvents(): void {
    this.on('pointerover', () => {
      if (!this.isDead) {
        this.scene.input.setDefaultCursor('pointer');
        this.scene.tweens.add({
          targets: this,
          scale: { from: 1, to: 1.1 },
          duration: 100
        });
        this.scene.events.emit('fighter:hover', { fighterId: this.fighterId });
      }
    });

    this.on('pointerout', () => {
      this.scene.input.setDefaultCursor('default');
      if (!this.isSelected && !this.isDead) {
        this.scene.tweens.add({
          targets: this,
          scale: 1,
          duration: 100
        });
      }
    });

    this.on('pointerdown', () => {
      if (!this.isDead) {
        this.scene.events.emit('fighter:click', { fighterId: this.fighterId });
      }
    });
  }

  /**
   * Запускает idle анимацию "дыхания"
   */
  private startIdleAnimation(): void {
    if (this.idleTween) {
      this.idleTween.destroy();
    }

    this.idleTween = this.scene.tweens.add({
      targets: this.sprite,
      scaleY: { from: 1, to: 1.03 },
      duration: 1500,
      yoyo: true,
      repeat: -1,
      ease: Phaser.Math.Easing.Sine.InOut
    });
  }

  /**
   * Останавливает idle анимацию
   */
  private stopIdleAnimation(): void {
    if (this.idleTween) {
      this.idleTween.destroy();
      this.idleTween = undefined;
    }
  }

  /**
   * Возвращает цвет здоровья в зависимости от процента
   */
  private getHealthColor(percent: number): number {
    if (percent > 0.6) return 0x4ecca3; // Зелёный
    if (percent > 0.3) return 0xffd93d; // Жёлтый
    return 0xff6b6b; // Красный
  }

  // ============================================================
  // ПУБЛИЧНЫЕ МЕТОДЫ
  // ============================================================

  /**
   * Обновляет отображение здоровья
   */
  updateHealth(current: number, max?: number): void {
    this.currentHealth = Math.max(0, current);
    if (max !== undefined) {
      this.maxHealth = max;
    }

    const healthPercent = this.currentHealth / this.maxHealth;

    // Анимируем изменение полоски здоровья
    this.scene.tweens.add({
      targets: this.healthBarFill,
      width: (this.config.healthBarWidth - 2) * healthPercent,
      duration: 200,
      onUpdate: () => {
        this.healthBarFill.fillColor = this.getHealthColor(
          this.healthBarFill.width / (this.config.healthBarWidth - 2)
        );
      }
    });

    // Обновляем текст
    this.healthText.setText(`${this.currentHealth}/${this.maxHealth}`);
  }

  /**
   * Перемещает бойца в указанную позицию
   */
  async moveTo(targetX: number, targetY: number): Promise<void> {
    return new Promise((resolve) => {
      // Останавливаем idle анимацию
      this.stopIdleAnimation();

      // Запускаем анимацию ходьбы если есть
      const animKey = `fighter-${this.fighter.definitionId}-walk`;
      if (this.scene.anims.exists(animKey)) {
        this.sprite.play(animKey);
      }

      // Вычисляем дистанцию для определения длительности
      const distance = Phaser.Math.Distance.Between(this.x, this.y, targetX, targetY);
      const duration = Math.max(200, distance * 10);

      this.scene.tweens.add({
        targets: this,
        x: targetX,
        y: targetY,
        duration: duration,
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => {
          // Останавливаем анимацию ходьбы
          if (this.scene.anims.exists(animKey)) {
            this.sprite.stop();
          }

          // Возобновляем idle
          if (!this.isDead) {
            this.startIdleAnimation();
          }

          resolve();
        }
      });
    });
  }

  /**
   * Проигрывает анимацию атаки
   */
  async playAttackAnimation(): Promise<void> {
    return new Promise((resolve) => {
      this.stopIdleAnimation();

      const animKey = `fighter-${this.fighter.definitionId}-attack`;

      if (this.scene.anims.exists(animKey)) {
        // Используем sprite sheet анимацию
        this.sprite.play(animKey);
        this.sprite.once('animationcomplete', () => {
          this.startIdleAnimation();
          resolve();
        });
      } else {
        // Процедурная анимация - выпад вперёд
        const originalX = this.sprite.x;

        this.scene.tweens.add({
          targets: this.sprite,
          x: originalX + 20,
          scaleY: 0.9,
          duration: this.config.animationDuration / 2,
          ease: Phaser.Math.Easing.Quadratic.Out,
          onComplete: () => {
            this.scene.tweens.add({
              targets: this.sprite,
              x: originalX,
              scaleY: 1,
              duration: this.config.animationDuration / 2,
              ease: Phaser.Math.Easing.Quadratic.In,
              onComplete: () => {
                this.startIdleAnimation();
                resolve();
              }
            });
          }
        });
      }
    });
  }

  /**
   * Проигрывает анимацию получения урона
   */
  async playDamageAnimation(amount?: number): Promise<void> {
    return new Promise((resolve) => {
      // Мигание красным
      const originalTint = this.sprite.tintTopLeft;

      this.scene.tweens.add({
        targets: this.sprite,
        tint: 0xff0000,
        duration: 50,
        yoyo: true,
        repeat: 3,
        onComplete: () => {
          this.sprite.setTint(originalTint);
          resolve();
        }
      });

      // Тряска
      this.scene.tweens.add({
        targets: this,
        x: `+=${Phaser.Math.Between(-5, 5)}`,
        y: `+=${Phaser.Math.Between(-5, 5)}`,
        duration: 50,
        repeat: 5,
        yoyo: true
      });

      // Показываем количество урона
      if (amount !== undefined && amount > 0) {
        this.showDamageNumber(amount);
      }
    });
  }

  /**
   * Показывает всплывающее число урона
   */
  private showDamageNumber(amount: number): void {
    const damageText = new Phaser.GameObjects.Text(
      this.scene,
      0,
      -30,
      `-${amount}`,
      {
        fontSize: '24px',
        color: '#ff0000',
        fontStyle: 'bold',
        stroke: '#000000',
        strokeThickness: 4
      }
    );
    damageText.setOrigin(0.5);

    // Добавляем текст к сцене, а не к контейнеру
    const worldPos = this.getWorldPosition();
    damageText.setPosition(worldPos.x, worldPos.y - 30);
    this.scene.add.existing(damageText);

    // Анимируем всплывание и исчезновение
    this.scene.tweens.add({
      targets: damageText,
      y: damageText.y - 50,
      alpha: 0,
      duration: 1000,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => damageText.destroy()
    });
  }

  /**
   * Проигрывает анимацию смерти
   */
  async playDeathAnimation(): Promise<void> {
    return new Promise((resolve) => {
      this.isDead = true;
      this.stopIdleAnimation();

      // Останавливаем交互
      this.disableInteractive();

      // Анимация исчезновения
      this.scene.tweens.add({
        targets: [this, this.sprite],
        alpha: 0.3,
        scale: 0.8,
        duration: 500,
        ease: Phaser.Math.Easing.Quadratic.In,
        onComplete: () => {
          // Превращаем в "могилу"
          this.sprite.setTint(0x666666);
          this.sprite.setAlpha(0.5);
          this.healthBarBg.setVisible(false);
          this.healthBarFill.setVisible(false);
          this.healthText.setVisible(false);

          resolve();
        }
      });
    });
  }

  /**
   * Устанавливает состояние выделения
   */
  setSelected(selected: boolean): void {
    this.isSelected = selected;
    this.selectionRing.setVisible(selected);

    if (selected) {
      // Анимация пульсации кольца
      this.scene.tweens.add({
        targets: this.selectionRing,
        alpha: { from: 1, to: 0.5 },
        scale: { from: 1, to: 1.1 },
        duration: 500,
        yoyo: true,
        repeat: -1
      });

      // Увеличиваем спрайт
      this.scene.tweens.add({
        targets: this,
        scale: 1.1,
        duration: 150
      });
    } else {
      // Убираем пульсацию
      this.scene.tweens.killTweensOf(this.selectionRing);
      this.selectionRing.setAlpha(1);
      this.selectionRing.setScale(1);

      // Возвращаем нормальный размер
      this.scene.tweens.add({
        targets: this,
        scale: 1,
        duration: 150
      });
    }
  }

  /**
   * Переключает состояние выделения
   */
  toggleSelection(): void {
    this.setSelected(!this.isSelected);
  }

  /**
   * Получает ID бойца
   */
  getFighterId(): string {
    return this.fighterId;
  }

  /**
   * Получает объект бойца
   */
  getFighter(): Fighter {
    return this.fighter;
  }

  /**
   * Проверяет, жив ли боец
   */
  isAlive(): boolean {
    return !this.isDead;
  }

  /**
   * Восстанавливает бойца (для возрождения)
   */
  revive(): void {
    this.isDead = false;
    this.currentHealth = this.maxHealth;

    this.sprite.setTint(0xffffff);
    this.sprite.setAlpha(1);
    this.healthBarBg.setVisible(true);
    this.healthBarFill.setVisible(true);
    this.healthText.setVisible(true);

    this.setInteractive();
    this.startIdleAnimation();

    // Анимация возрождения
    this.scene.tweens.add({
      targets: this,
      alpha: { from: 0.3, to: 1 },
      scale: { from: 0.8, to: 1 },
      duration: 300,
      ease: Phaser.Math.Easing.Back.Out
    });
  }
}

// ============================================================
// ЭКСПОРТ ТИПОВ
// ============================================================

export type { FighterDisplayConfig, FighterEvents };
