// ============================================================
// FIGHTER ANIMATIONS - Базовые анимации бойцов
// ============================================================

import * as Phaser from 'phaser';
import type { FighterSprite } from '../sprites/FighterSprite';

// ------------------------------------------------------------
// Конфигурация параметров анимации
// ------------------------------------------------------------

export interface AnimationConfig {
  duration?: number;
  ease?: string | ((v: number) => number);
  delay?: number;
  holdDelay?: number;
  repeat?: number;
  yoyo?: boolean;
}

export interface FighterAnimationConfig {
  idle: AnimationConfig;
  walk: AnimationConfig;
  attack: AnimationConfig;
  hit: AnimationConfig;
  block: AnimationConfig;
  special?: AnimationConfig;
}

// ------------------------------------------------------------
// Конфигурации анимации по умолчанию
// ------------------------------------------------------------

export const DEFAULT_FIGHTER_ANIMATION_CONFIG: FighterAnimationConfig = {
  idle: {
    duration: 800,
    ease: Phaser.Math.Easing.Sine.InOut,
    yoyo: true,
    repeat: -1,
  },
  walk: {
    duration: 200,
    ease: Phaser.Math.Easing.Sine.InOut,
    repeat: 1,
    yoyo: true,
  },
  attack: {
    duration: 150,
    ease: Phaser.Math.Easing.Quadratic.Out,
    holdDelay: 50,
  },
  hit: {
    duration: 100,
    ease: Phaser.Math.Easing.Back.Out,
  },
  block: {
    duration: 200,
    ease: Phaser.Math.Easing.Quadratic.InOut,
    holdDelay: 100,
  },
  special: {
    duration: 500,
    ease: Phaser.Math.Easing.Cubic.Out,
  },
};

// ------------------------------------------------------------
// FighterAnimations - управляет анимациями бойца
// ------------------------------------------------------------

export class FighterAnimations {
  private scene: Phaser.Scene;
  private config: FighterAnimationConfig;
  private activeTweens: Map<string, Phaser.Tweens.Tween> = new Map();

  constructor(scene: Phaser.Scene, config?: Partial<FighterAnimationConfig>) {
    this.scene = scene;
    this.config = {
      ...DEFAULT_FIGHTER_ANIMATION_CONFIG,
      ...config,
    };
  }

  // ------------------------------------------------------------
  // Idle - Анимация покоя (дыхание)
  // ------------------------------------------------------------

  /**
   * Запускает idle анимацию - "дыхание" бойца
   */
  public async playIdle(sprite: FighterSprite): Promise<void> {
    return new Promise((resolve) => {
      // Останавливаем предыдущие tweens
      this.stopFighterTweens(sprite);

      const { duration, ease } = this.config.idle;

      const tween = this.scene.tweens.add({
        targets: sprite,
        y: sprite.y - 3,
        duration,
        ease: ease as any,
        yoyo: true,
        repeat: -1,
        onComplete: () => resolve(),
      });

      this.activeTweens.set(`idle-${sprite.fighterId}`, tween);
    });
  }

  // ------------------------------------------------------------
  // Walk - Анимация ходьбы
  // ------------------------------------------------------------

  /**
   * Запускает анимацию ходьбы при перемещении
   * @param sprite Спрайт бойца
   * @param targetX Конечная позиция X
   * @param targetY Конечная позиция Y
   * @param speed Скорость перемещения (пикселей в мс)
   */
  public async playWalk(
    sprite: FighterSprite,
    targetX: number,
    targetY: number,
    speed: number = 200
  ): Promise<void> {
    return new Promise((resolve) => {
      this.stopFighterTweens(sprite);

      const distance = Phaser.Math.Distance.Between(sprite.x, sprite.y, targetX, targetY);
      const duration = (distance / speed) * 1000;

      // Анимация покачивания при ходьбе
      const bobTween = this.scene.tweens.add({
        targets: sprite,
        y: sprite.y - 5,
        duration: this.config.walk.duration,
        ease: this.config.walk.ease as any,
        yoyo: true,
        repeat: Math.floor(duration / (this.config.walk.duration! * 2)),
      });

      // Основное перемещение
      const moveTween = this.scene.tweens.add({
        targets: sprite,
        x: targetX,
        y: targetY,
        duration,
        ease: Phaser.Math.Easing.Quadratic.InOut,
        onComplete: () => {
          bobTween.stop();
          // Возвращаемся к idle анимации
          this.playIdle(sprite);
          resolve();
        },
      });

      this.activeTweens.set(`walk-${sprite.fighterId}`, moveTween);
      this.activeTweens.set(`walk-bob-${sprite.fighterId}`, bobTween);
    });
  }

  // ------------------------------------------------------------
  // Attack - Анимация атаки
  // ------------------------------------------------------------

  /**
   * Запускает анимацию атаки - выпад вперёд
   * @param sprite Атакующий боец
   * @param targetX Целевая позиция X (для направления)
   * @param targetY Целевая позиция Y
   */
  public async playAttack(
    sprite: FighterSprite,
    targetX: number,
    targetY: number
  ): Promise<void> {
    return new Promise((resolve) => {
      this.stopFighterTweens(sprite);

      const direction = targetX > sprite.x ? 1 : -1;
      const originalX = sprite.x;
      const lungeDistance = 30 * direction;
      const { duration, ease, holdDelay } = this.config.attack;

      // Фаза 1: Замах назад
      this.scene.tweens.add({
        targets: sprite,
        x: originalX - (10 * direction),
        duration: duration! / 2,
        ease: Phaser.Math.Easing.Quadratic.In,
      });

      // Фаза 2: Выпад вперёд
      setTimeout(() => {
        const lungeTween = this.scene.tweens.add({
          targets: sprite,
          x: originalX + lungeDistance,
          duration: duration!,
          ease: ease as any,
          onComplete: () => {
            // Удержание позиции удара
            setTimeout(() => {
              // Фаза 3: Возврат
              this.scene.tweens.add({
                targets: sprite,
                x: originalX,
                duration: duration! * 0.7,
                ease: Phaser.Math.Easing.Quadratic.Out,
                onComplete: () => {
                  this.playIdle(sprite);
                  resolve();
                },
              });
            }, holdDelay || 50);
          },
        });

        this.activeTweens.set(`attack-${sprite.fighterId}`, lungeTween);
      }, duration! / 2);
    });
  }

  // ------------------------------------------------------------
  // Hit - Анимация получения урона
  // ------------------------------------------------------------

  /**
   * Запускает анимацию получения удара
   * @param sprite Пострадавший боец
   * @param fromX Позиция, откуда пришёл удар (для направления отброса)
   * @param fromY Позиция, откуда пришёл удар
   */
  public async playHit(
    sprite: FighterSprite,
    fromX: number,
    fromY: number
  ): Promise<void> {
    return new Promise((resolve) => {
      this.stopFighterTweens(sprite);

      const angle = Phaser.Math.Angle.Between(fromX, fromY, sprite.x, sprite.y);
      const knockbackDistance = 15;
      const knockbackX = Math.cos(angle) * knockbackDistance;
      const knockbackY = Math.sin(angle) * knockbackDistance;
      const { duration, ease } = this.config.hit;

      // Мигание красным
      sprite.bodySprite?.setTint(0xff0000);

      // Отброс назад
      const knockbackTween = this.scene.tweens.add({
        targets: sprite,
        x: sprite.x + knockbackX,
        y: sprite.y + knockbackY,
        duration: duration!,
        ease: ease as any,
        onComplete: () => {
          // Возврат на место
          this.scene.tweens.add({
            targets: sprite,
            x: sprite.x - knockbackX,
            y: sprite.y - knockbackY,
            duration: duration! * 1.5,
            ease: Phaser.Math.Easing.Elastic.Out,
            onComplete: () => {
              sprite.bodySprite?.clearTint();
              this.playIdle(sprite);
              resolve();
            },
          });
        },
      });

      // Лёгкое вращение при ударе
      this.scene.tweens.add({
        targets: sprite,
        angle: knockbackX > 0 ? 5 : -5,
        duration: duration! / 2,
        yoyo: true,
        ease: Phaser.Math.Easing.Sine.InOut,
      });

      this.activeTweens.set(`hit-${sprite.fighterId}`, knockbackTween);
    });
  }

  // ------------------------------------------------------------
  // Block - Анимация блока
  // ------------------------------------------------------------

  /**
   * Запускает анимацию блока/парирования
   * @param sprite Защищающийся боец
   */
  public async playBlock(sprite: FighterSprite): Promise<void> {
    return new Promise((resolve) => {
      this.stopFighterTweens(sprite);

      const { duration, holdDelay } = this.config.block;

      // Эффект щита - быстрое сжатие и возврат
      this.scene.tweens.add({
        targets: sprite,
        scaleX: 0.85,
        scaleY: 1.1,
        duration: duration! / 2,
        ease: Phaser.Math.Easing.Back.In,
        onComplete: () => {
          // Удержание позы блока
          setTimeout(() => {
            this.scene.tweens.add({
              targets: sprite,
              scaleX: 1,
              scaleY: 1,
              duration: duration! / 2,
              ease: Phaser.Math.Easing.Back.Out,
              onComplete: () => {
                this.playIdle(sprite);
                resolve();
              },
            });
          }, holdDelay || 100);
        },
      });
    });
  }

  // ------------------------------------------------------------
  // Special - Специальные анимации
  // ------------------------------------------------------------

  /**
   * Запускает специальную анимацию (для уникальных способностей)
   * @param sprite Боец
   * @param type Тип специальной анимации
   */
  public async playSpecial(sprite: FighterSprite, type: string): Promise<void> {
    return new Promise((resolve) => {
      this.stopFighterTweens(sprite);

      const { duration, ease } = this.config.special || { duration: 500, ease: 'Cubic.Out' };

      switch (type) {
        case 'charge':
          this.playChargeAnimation(sprite, duration!, ease as any, resolve);
          break;

        case 'teleport':
          this.playTeleportAnimation(sprite, resolve);
          break;

        case 'heal':
          this.playHealAnimation(sprite, duration!, resolve);
          break;

        case 'buff':
          this.playBuffAnimation(sprite, duration!, resolve);
          break;

        default:
          this.playDefaultSpecialAnimation(sprite, duration!, resolve);
      }
    });
  }

  private playChargeAnimation(
    sprite: FighterSprite,
    duration: number,
    ease: string,
    resolve: () => void
  ): void {
    // Накопление энергии - пульсация
    const originalScale = sprite.scale;
    const chargeTween = this.scene.tweens.add({
      targets: sprite,
      scale: originalScale * 1.3,
      alpha: 0.8,
      duration,
      ease: ease as any,
      yoyo: true,
      repeat: 1,
      onComplete: () => {
        this.playIdle(sprite);
        resolve();
      },
    });

    // Создаём кольца энергии
    for (let i = 0; i < 3; i++) {
      setTimeout(() => {
        const ring = this.scene.add.graphics();
        ring.lineStyle(3, 0xffff00, 0.8);
        ring.strokeCircle(sprite.x, sprite.y, 30);
        this.scene.add.existing(ring);

        this.scene.tweens.add({
          targets: ring,
          scale: 2,
          alpha: 0,
          duration: duration * 0.8,
          onComplete: () => ring.destroy(),
        });
      }, i * 150);
    }

    this.activeTweens.set(`special-${sprite.fighterId}`, chargeTween);
  }

  private playTeleportAnimation(sprite: FighterSprite, resolve: () => void): void {
    // Исчезновение
    this.scene.tweens.add({
      targets: sprite,
      alpha: 0,
      scale: 0.1,
      duration: 300,
      ease: Phaser.Math.Easing.Back.In,
      onComplete: () => {
        // (Позиция должна быть обновлена извне)
        // Появление
        this.scene.tweens.add({
          targets: sprite,
          alpha: 1,
          scale: 1,
          duration: 300,
          ease: Phaser.Math.Easing.Back.Out,
          onComplete: () => {
            this.playIdle(sprite);
            resolve();
          },
        });
      },
    });
  }

  private playHealAnimation(sprite: FighterSprite, duration: number, resolve: () => void): void {
    // Зелёное свечение
    const glow = this.scene.add.graphics();
    glow.fillStyle(0x4ecca3, 0.3);
    glow.fillCircle(sprite.x, sprite.y, 50);
    this.scene.add.existing(glow);

    this.scene.tweens.add({
      targets: glow,
      scale: 1.5,
      alpha: 0,
      duration,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => {
        glow.destroy();
        this.playIdle(sprite);
        resolve();
      },
    });

    // Поднятие спрайта
    this.scene.tweens.add({
      targets: sprite,
      y: sprite.y - 10,
      duration: duration / 2,
      yoyo: true,
      ease: Phaser.Math.Easing.Sine.InOut,
    });
  }

  private playBuffAnimation(sprite: FighterSprite, duration: number, resolve: () => void): void {
    // Золотое свечение для бафа
    const aura = this.scene.add.graphics();
    aura.lineStyle(5, 0xffd700, 0.6);
    aura.strokeCircle(sprite.x, sprite.y, 45);
    this.scene.add.existing(aura);

    this.scene.tweens.add({
      targets: aura,
      rotation: Math.PI * 2,
      scale: 1.2,
      duration: duration * 2,
      ease: Phaser.Math.Easing.Linear,
      onComplete: () => {
        aura.destroy();
        this.playIdle(sprite);
        resolve();
      },
    });

    // Несколько искорок
    for (let i = 0; i < 8; i++) {
      const angle = (Math.PI * 2 * i) / 8;
      const spark = this.scene.add.circle(
        sprite.x + Math.cos(angle) * 40,
        sprite.y + Math.sin(angle) * 40,
        3,
        0xffd700
      );

      this.scene.tweens.add({
        targets: spark,
        x: sprite.x + Math.cos(angle) * 60,
        y: sprite.y + Math.sin(angle) * 60,
        alpha: 0,
        duration: duration * 1.5,
        onComplete: () => spark.destroy(),
      });
    }
  }

  private playDefaultSpecialAnimation(sprite: FighterSprite, duration: number, resolve: () => void): void {
    // Стандартная анимация - вращение и свечение
    this.scene.tweens.add({
      targets: sprite,
      angle: 360,
      duration,
      ease: Phaser.Math.Easing.Cubic.InOut,
      onComplete: () => {
        sprite.angle = 0;
        this.playIdle(sprite);
        resolve();
      },
    });
  }

  // ------------------------------------------------------------
  // Утилиты
  // ------------------------------------------------------------

  /**
   * Останавливает все активные tweens для указанного бойца
   */
  private stopFighterTweens(sprite: FighterSprite): void {
    const keys = Array.from(this.activeTweens.keys()).filter(k => k.includes(sprite.fighterId));
    keys.forEach(key => {
      const tween = this.activeTweens.get(key);
      if (tween && tween.isActive()) {
        tween.stop();
      }
      this.activeTweens.delete(key);
    });
  }

  /**
   * Останавливает все активные tweens
   */
  public stopAll(): void {
    this.activeTweens.forEach(tween => {
      if (tween && tween.isActive()) {
        tween.stop();
      }
    });
    this.activeTweens.clear();
  }

  /**
   * Уничтожает объект и очищает ресурсы
   */
  public destroy(): void {
    this.stopAll();
  }
}
