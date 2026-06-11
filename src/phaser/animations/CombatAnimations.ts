// ============================================================
// COMBAT ANIMATIONS - Анимации боевых действий
// ============================================================

import * as Phaser from 'phaser';
import type { FighterSprite } from '../sprites/FighterSprite';
import type { ScreenEffects } from '../effects/ScreenEffects';
import type { ParticleSystem } from '../effects/ParticleSystem';

// ------------------------------------------------------------
// Типы атак для визуализации
// ------------------------------------------------------------

export enum AttackType {
  MELEE = 'melee',           // Ближний бой
  RANGED = 'ranged',         // Дальний бой
  MAGIC = 'magic',           // Магическая атака
  EXPLOSIVE = 'explosive',   // Взрывная атака
  HEAVY = 'heavy',           // Тяжёлая атака
  CRITICAL = 'critical',     // Критический удар
}

// ------------------------------------------------------------
// Интерфейс для результата анимации атаки
// ------------------------------------------------------------

export interface CombatAnimationResult {
  wasBlocked: boolean;
  damageDealt: number;
  wasCritical: boolean;
}

// ------------------------------------------------------------
// CombatAnimations - управляет боевыми анимациями
// ------------------------------------------------------------

export class CombatAnimations {
  private scene: Phaser.Scene;
  private screenEffects: ScreenEffects;
  private particles: ParticleSystem;
  private activeAnimations: Set<string> = new Set();

  constructor(
    scene: Phaser.Scene,
    screenEffects: ScreenEffects,
    particles: ParticleSystem
  ) {
    this.scene = scene;
    this.screenEffects = screenEffects;
    this.particles = particles;
  }

  // ------------------------------------------------------------
  // Attack - Анимация атаки
  // ------------------------------------------------------------

  /**
   * Проигрывает полную анимацию атаки от одного бойца к другому
   * @param attacker Атакующий боец
   * @param target Цель атаки
   * @param attackType Тип атаки
   * @param result Результат атаки (урон, блок и т.д.)
   */
  public async playAttack(
    attacker: FighterSprite,
    target: FighterSprite,
    attackType: AttackType = AttackType.MELEE,
    result?: CombatAnimationResult
  ): Promise<void> {
    const animationId = `${attacker.fighterId}-${target.fighterId}-${Date.now()}`;
    this.activeAnimations.add(animationId);

    try {
      // Фаза 1: Подготовка к атаке
      await this.playAttackPreparation(attacker, target);

      // Фаза 2: Выполнение атаки
      await this.playAttackExecution(attacker, target, attackType);

      // Фаза 3: Реакция цели
      if (result) {
        if (result.wasBlocked) {
          await this.playBlock(target);
        } else {
          await this.playHit(target, result.damageDealt, result.wasCritical);
        }
      } else {
        // Если результат не передан, просто проигрываем hit
        await this.playHit(target, 0, false);
      }

      // Фаза 4: Завершение
      await this.playAttackCompletion(attacker);
    } finally {
      this.activeAnimations.delete(animationId);
    }
  }

  private async playAttackPreparation(
    attacker: FighterSprite,
    target: FighterSprite
  ): Promise<void> {
    return new Promise((resolve) => {
      // Разворот к цели
      const direction = target.x > attacker.x ? 1 : -1;

      this.scene.tweens.add({
        targets: attacker.bodySprite,
        scaleX: Math.abs(attacker.bodySprite.scaleX) * direction,
        duration: 100,
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => resolve(),
      });
    });
  }

  private async playAttackExecution(
    attacker: FighterSprite,
    target: FighterSprite,
    attackType: AttackType
  ): Promise<void> {
    return new Promise((resolve) => {
      const direction = target.x > attacker.x ? 1 : -1;
      const originalX = attacker.x;
      const originalY = attacker.y;
      const distance = Phaser.Math.Distance.Between(attacker.x, attacker.y, target.x, target.y);
      const lungeDistance = Math.min(distance * 0.4, 40);

      let duration = 150;
      let effectY = 0;

      // Настройка параметров по типу атаки
      switch (attackType) {
        case AttackType.HEAVY:
          duration = 250;
          effectY = -5; // Низкий старт
          break;
        case AttackType.CRITICAL:
          duration = 120; // Быстрая
          break;
        case AttackType.RANGED:
          // Для дальнобойной атаки не двигаем бойца
          this.playRangedAttackEffect(attacker, target);
          resolve();
          return;
        case AttackType.MAGIC:
          this.playMagicAttackEffect(attacker, target);
          resolve();
          return;
        case AttackType.EXPLOSIVE:
          this.playExplosiveAttackEffect(attacker, target);
          resolve();
          return;
      }

      // Анимация выпада
      this.scene.tweens.add({
        targets: attacker,
        x: originalX + lungeDistance * direction,
        y: originalY + effectY,
        duration,
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => {
          // Удержание в точке удара
          setTimeout(() => {
            // Возврат
            this.scene.tweens.add({
              targets: attacker,
              x: originalX,
              y: originalY,
              duration: duration * 0.8,
              ease: Phaser.Math.Easing.Back.Out,
              onComplete: () => resolve(),
            });
          }, 50);
        },
      });
    });
  }

  private playRangedAttackEffect(attacker: FighterSprite, target: FighterSprite): void {
    // Создаём снаряд
    const projectile = this.scene.add.circle(attacker.x, attacker.y - 20, 5, 0xffff00);

    // Траектория полёта
    this.scene.tweens.add({
      targets: projectile,
      x: target.x,
      y: target.y - 20,
      duration: 300,
      ease: Phaser.Math.Easing.Quadratic.In,
      onComplete: () => {
        // Эффект попадания
        this.particles.emitBurst(target.x, target.y - 20, 0xffff00, 10);
        projectile.destroy();
      },
    });

    // Оставляем след
    const trail = this.scene.add.graphics();
    this.scene.time.addEvent({
      delay: 20,
      repeat: 15,
      callback: () => {
        trail.fillStyle(0xffff00, 0.3);
        trail.fillCircle(projectile.x, projectile.y, 3);
        this.scene.time.delayedCall(200, () => trail.clear());
      },
    });
  }

  private playMagicAttackEffect(attacker: FighterSprite, target: FighterSprite): void {
    // Магический снаряд с искрами
    const projectile = this.scene.add.graphics();
    projectile.fillStyle(0x9966ff, 1);
    projectile.fillCircle(0, 0, 8);
    projectile.setPosition(attacker.x, attacker.y - 20);

    // Свечение вокруг снаряда
    const glow = this.scene.add.graphics();
    glow.lineStyle(2, 0x9966ff, 0.5);
    glow.strokeCircle(attacker.x, attacker.y - 20, 15);

    // Анимация полёта
    this.scene.tweens.add({
      targets: [projectile, glow],
      x: target.x,
      y: target.y - 20,
      duration: 400,
      ease: Phaser.Math.Easing.Sine.InOut,
      onUpdate: () => {
        // Искры за снарядом
        if (Math.random() > 0.5) {
          this.particles.emitBurst(
            projectile.x + (Math.random() - 0.5) * 20,
            projectile.y + (Math.random() - 0.5) * 20,
            0x9966ff,
            3
          );
        }
      },
      onComplete: () => {
        // Взрыв при попадании
        this.particles.emitBurst(target.x, target.y - 20, 0x9966ff, 20);
        this.screenEffects.flash(0x9966ff, 200);
        projectile.destroy();
        glow.destroy();
      },
    });
  }

  private playExplosiveAttackEffect(attacker: FighterSprite, target: FighterSprite): void {
    // Начальный взрыв у атакующего
    this.particles.emitBurst(attacker.x, attacker.y - 20, 0xff6600, 15);

    // Волна огня
    const wave = this.scene.add.graphics();
    wave.fillStyle(0xff6600, 0.6);
    wave.fillCircle(attacker.x, attacker.y - 20, 20);

    this.scene.tweens.add({
      targets: wave,
      x: target.x,
      y: target.y - 20,
      scale: 2,
      duration: 400,
      ease: Phaser.Math.Easing.Quadratic.In,
      onComplete: () => {
        // Финальный взрыв
        this.particles.emitBurst(target.x, target.y - 20, 0xff6600, 30);
        this.particles.emitBurst(target.x, target.y - 20, 0xffff00, 20);
        this.screenEffects.shake(0.02, 300);
        wave.destroy();
      },
    });
  }

  // ------------------------------------------------------------
  // Block - Анимация блока
  // ------------------------------------------------------------

  /**
   * Проигрывает анимацию блока/парирования
   * @param defender Защищающийся боец
   */
  public async playBlock(defender: FighterSprite): Promise<void> {
    return new Promise((resolve) => {
      // Звуковой эффект (визуальный - "клинк")
      const spark = this.scene.add.graphics();

      // Рисуем искру щита
      spark.lineStyle(3, 0x88ccff, 1);
      spark.beginPath();
      spark.moveTo(defender.x - 20, defender.y - 30);
      spark.lineTo(defender.x + 20, defender.y - 20);
      spark.strokePath();

      this.scene.tweens.add({
        targets: spark,
        alpha: 0,
        y: defender.y - 40,
        duration: 300,
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => spark.destroy(),
      });

      // Эффект щита - полукруг
      const shield = this.scene.add.graphics();
      shield.lineStyle(4, 0x4ecca3, 0.8);
      shield.beginPath();
      shield.arc(defender.x, defender.y, 35, Math.PI, 0);
      shield.strokePath();

      this.scene.tweens.add({
        targets: shield,
        alpha: 0,
        scale: 1.2,
        duration: 400,
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => shield.destroy(),
      });

      // Небольшой отскок защитника
      const originalX = defender.x;
      this.scene.tweens.add({
        targets: defender,
        x: originalX - 5,
        duration: 100,
        yoyo: true,
        ease: Phaser.Math.Easing.Quadratic.InOut,
        onComplete: () => resolve(),
      });

      // Несколько мелких частиц от удара о щит
      for (let i = 0; i < 5; i++) {
        const angle = Math.PI + (Math.random() * Math.PI);
        const particle = this.scene.add.circle(defender.x, defender.y - 25, 2, 0x88ccff);

        this.scene.tweens.add({
          targets: particle,
          x: defender.x + Math.cos(angle) * 30,
          y: defender.y - 25 + Math.sin(angle) * 30,
          alpha: 0,
          duration: 300 + Math.random() * 200,
          onComplete: () => particle.destroy(),
        });
      }
    });
  }

  // ------------------------------------------------------------
  // Hit - Анимация получения урона
  // ------------------------------------------------------------

  /**
   * Проигрывает анимацию получения урона
   * @param target Пострадавший боец
   * @param damage Нанесённый урон
   * @param isCritical Критический удар
   */
  public async playHit(
    target: FighterSprite,
    damage: number,
    isCritical: boolean = false
  ): Promise<void> {
    return new Promise((resolve) => {
      // Мигание красным
      target.bodySprite?.setTint(0xff0000);

      // Отброс
      const knockbackDistance = isCritical ? 20 : 10;
      const originalX = target.x;
      const originalY = target.y;

      this.scene.tweens.add({
        targets: target,
        x: originalX - knockbackDistance,
        y: originalY + 5,
        duration: isCritical ? 150 : 100,
        ease: Phaser.Math.Easing.Back.Out,
        onComplete: () => {
          // Возврат
          this.scene.tweens.add({
            targets: target,
            x: originalX,
            y: originalY,
            duration: 200,
            ease: Phaser.Math.Easing.Elastic.Out,
            onComplete: () => {
              target.bodySprite?.clearTint();
              resolve();
            },
          });
        },
      });

      // Вращение при ударе
      this.scene.tweens.add({
        targets: target,
        angle: isCritical ? 15 : 8,
        duration: 100,
        yoyo: true,
        ease: Phaser.Math.Easing.Sine.InOut,
      });

      // Частицы крови/искр
      this.particles.emitDamage(target.x, target.y - 20, damage);

      // Тряска экрана для критического удара
      if (isCritical) {
        this.screenEffects.shake(0.02, 200);
        this.screenEffects.flash(0xff0000, 100);
      }

      // Создаём всплывающее число урона
      this.createDamageNumber(target.x, target.y - 40, damage, isCritical);
    });
  }

  private createDamageNumber(x: number, y: number, damage: number, isCritical: boolean): void {
    const text = this.scene.add.text(x, y, damage.toString(), {
      fontSize: isCritical ? '48px' : '32px',
      color: isCritical ? '#ff0000' : '#ff6666',
      fontStyle: isCritical ? 'bold' : 'normal',
      stroke: '#000000',
      strokeThickness: 4,
    });

    text.setOrigin(0.5);

    // Анимация всплывания
    this.scene.tweens.add({
      targets: text,
      y: y - 50,
      alpha: 0,
      scale: isCritical ? 1.5 : 1,
      duration: 800,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => text.destroy(),
    });

    // Для крита добавляем дополнительный эффект
    if (isCritical) {
      const critText = this.scene.add.text(x, y - 20, 'CRIT!', {
        fontSize: '24px',
        color: '#ffff00',
        fontStyle: 'bold',
        stroke: '#000000',
        strokeThickness: 3,
      });
      critText.setOrigin(0.5);

      this.scene.tweens.add({
        targets: critText,
        y: y - 60,
        alpha: 0,
        duration: 1000,
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => critText.destroy(),
      });
    }
  }

  // ------------------------------------------------------------
  // Death - Анимация смерти
  // ------------------------------------------------------------

  /**
   * Проигрывает анимацию смерти/поражения бойца
   * @param fighter Умирающий боец
   */
  public async playDeath(fighter: FighterSprite): Promise<void> {
    return new Promise((resolve) => {
      // Меняем цвет на серый
      fighter.bodySprite?.setTint(0x666666);

      // Падение
      this.scene.tweens.add({
        targets: [fighter.bodySprite, fighter.shadowSprite],
        alpha: 0,
        y: fighter.y + 30,
        angle: 90,
        duration: 1000,
        ease: Phaser.Math.Easing.Quadratic.In,
        onComplete: () => {
          // Эффект исчезновения в дымку
          this.particles.emitBurst(fighter.x, fighter.y, 0x888888, 15);
          resolve();
        },
      });

      // Частицы при падении
      for (let i = 0; i < 10; i++) {
        setTimeout(() => {
          this.particles.emitBurst(
            fighter.x + (Math.random() - 0.5) * 40,
            fighter.y + (Math.random() - 0.5) * 20,
            0x666666,
            3
          );
        }, i * 100);
      }

      // Тряска экрана
      this.screenEffects.shake(0.015, 500);
    });
  }

  // ------------------------------------------------------------
  // Special Attack - Специальные атаки
  // ------------------------------------------------------------

  /**
   * Проигрывает анимацию специальной атаки
   * @param attackType Тип специальной атаки
   * @param attacker Атакующий
   * @param target Цель
   */
  public async playSpecialAttack(
    attackType: string,
    attacker: FighterSprite,
    target: FighterSprite
  ): Promise<void> {
    switch (attackType) {
      case 'combo':
        await this.playComboAttack(attacker, target);
        break;

      case 'area':
        await this.playAreaAttack(attacker, target);
        break;

      case 'finisher':
        await this.playFinisherAttack(attacker, target);
        break;

      case 'summon':
        await this.playSummonAttack(attacker, target);
        break;

      default:
        await this.playDefaultSpecialAttack(attacker, target);
    }
  }

  private async playComboAttack(attacker: FighterSprite, target: FighterSprite): Promise<void> {
    // Множественные быстрые удары
    for (let i = 0; i < 3; i++) {
      await new Promise(r => setTimeout(r, 200));

      // Быстрый выпад
      const direction = target.x > attacker.x ? 1 : -1;
      const originalX = attacker.x;

      this.scene.tweens.add({
        targets: attacker,
        x: originalX + 15 * direction,
        duration: 80,
        yoyo: true,
        ease: Phaser.Math.Easing.Quadratic.Out,
      });

      // Искры на цели
      this.particles.emitBurst(
        target.x + (Math.random() - 0.5) * 20,
        target.y - 20 + (Math.random() - 0.5) * 20,
        0xffaa00,
        5
      );
    }

    // Финальный удар
    await this.playAttack(attacker, target, AttackType.MELEE, { wasBlocked: false, damageDealt: 0, wasCritical: false });
  }

  private async playAreaAttack(attacker: FighterSprite, target: FighterSprite): Promise<void> {
    // Круговая волна
    const wave = this.scene.add.graphics();
    wave.lineStyle(5, 0xff4400, 0.8);
    wave.strokeCircle(attacker.x, attacker.y, 10);

    this.scene.tweens.add({
      targets: wave,
      scale: 5,
      alpha: 0,
      duration: 600,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onUpdate: () => {
        wave.clear();
        wave.lineStyle(5, 0xff4400, wave.alpha);
        wave.strokeCircle(attacker.x, attacker.y, 10 * wave.scale);
      },
      onComplete: () => wave.destroy(),
    });

    // Частицы по кругу
    for (let i = 0; i < 16; i++) {
      const angle = (Math.PI * 2 * i) / 16;
      const startX = attacker.x + Math.cos(angle) * 30;
      const startY = attacker.y + Math.sin(angle) * 30;

      const particle = this.scene.add.circle(startX, startY, 4, 0xff4400);

      this.scene.tweens.add({
        targets: particle,
        x: attacker.x + Math.cos(angle) * 150,
        y: attacker.y + Math.sin(angle) * 150,
        alpha: 0,
        duration: 500,
        delay: i * 20,
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => particle.destroy(),
      });
    }

    await new Promise(r => setTimeout(r, 600));
  }

  private async playFinisherAttack(attacker: FighterSprite, target: FighterSprite): Promise<void> {
    // Драматичная пауза - замедление
    this.screenEffects.setSlowMotion(true, 0.2);

    await new Promise(r => setTimeout(r, 500));

    // Мощный удар с сильной тряской
    const direction = target.x > attacker.x ? 1 : -1;
    const originalX = attacker.x;

    // Замах
    await new Promise<void>(resolve => {
      this.scene.tweens.add({
        targets: attacker,
        x: originalX - 30 * direction,
        duration: 300,
        ease: Phaser.Math.Easing.Back.In,
        onComplete: () => resolve(),
      });
    });

    // Удар
    this.screenEffects.shake(0.05, 300);
    this.screenEffects.flash(0xffffff, 100);

    this.scene.tweens.add({
      targets: attacker,
      x: originalX + 50 * direction,
      duration: 100,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => {
        // Множество частиц
        for (let i = 0; i < 30; i++) {
          this.particles.emitBurst(
            target.x + (Math.random() - 0.5) * 50,
            target.y - 20 + (Math.random() - 0.5) * 50,
            0xff0000,
            3
          );
        }
      },
    });

    await new Promise(r => setTimeout(r, 400));

    // Возврат к нормальной скорости
    this.screenEffects.setSlowMotion(false);
  }

  private async playSummonAttack(attacker: FighterSprite, target: FighterSprite): Promise<void>
{
    // Появление союзника/сущности
    const summonX = (attacker.x + target.x) / 2;
    const summonY = attacker.y;

    // Круг вызова на земле
    const summonCircle = this.scene.add.graphics();
    summonCircle.lineStyle(3, 0x9966ff, 0.8);
    summonCircle.strokeCircle(summonX, summonY + 20, 30);

    this.scene.tweens.add({
      targets: summonCircle,
      scale: 0,
      alpha: 0,
      duration: 500,
      ease: Phaser.Math.Easing.Quadratic.In,
      onComplete: () => summonCircle.destroy(),
    });

    // Сияние сверху
    const beam = this.scene.add.graphics();
    beam.fillStyle(0x9966ff, 0.3);
    beam.fillRect(summonX - 25, -100, 50, 200);

    this.scene.tweens.add({
      targets: beam,
      alpha: 0,
      duration: 400,
      delay: 200,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => beam.destroy(),
    });

    // Частицы вызова
    for (let i = 0; i < 20; i++) {
      const particle = this.scene.add.circle(
        summonX + (Math.random() - 0.5) * 60,
        summonY + 20,
        3,
        0x9966ff
      );

      this.scene.tweens.add({
        targets: particle,
        y: summonY - 50,
        alpha: 0,
        duration: 600 + Math.random() * 400,
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => particle.destroy(),
      });
    }

    await new Promise(r => setTimeout(r, 800));
  }

  private async playDefaultSpecialAttack(
    attacker: FighterSprite,
    target: FighterSprite
  ): Promise<void> {
    // Стандартная спец-атака с свечением
    const aura = this.scene.add.graphics();
    aura.lineStyle(4, 0xffff00, 0.6);
    aura.strokeCircle(attacker.x, attacker.y, 50);

    this.scene.tweens.add({
      targets: aura,
      scale: 2,
      alpha: 0,
      duration: 500,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => aura.destroy(),
    });

    await this.playAttack(attacker, target, AttackType.MELEE);
  }

  // ------------------------------------------------------------
  // Завершение атаки
  // ------------------------------------------------------------

  private async playAttackCompletion(attacker: FighterSprite): Promise<void> {
    return new Promise((resolve) => {
      // Небольшая пауза перед возвратом в idle
      setTimeout(() => {
        attacker.bodySprite?.clearTint();
        resolve();
      }, 100);
    });
  }

  // ------------------------------------------------------------
  // Утилиты
  // ------------------------------------------------------------

  /**
   * Проверяет, есть ли активные анимации
   */
  public hasActiveAnimations(): boolean {
    return this.activeAnimations.size > 0;
  }

  /**
   * Останавливает все активные анимации
   */
  public stopAll(): void {
    this.activeAnimations.clear();
  }

  /**
   * Уничтожает объект и очищает ресурсы
   */
  public destroy(): void {
    this.stopAll();
  }
}
