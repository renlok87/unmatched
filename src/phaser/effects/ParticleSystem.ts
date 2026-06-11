// ============================================================
// PARTICLE SYSTEM - Система визуальных эффектов частиц
// ============================================================

import * as Phaser from 'phaser';

// ------------------------------------------------------------
// Конфигурация частиц
// ------------------------------------------------------------

export interface ParticleConfig {
  x: number;
  y: number;
  speed?: number;
  scale?: { min: number; max: number };
  alpha?: { start: number; end: number };
  lifespan?: number;
  color?: number;
  quantity?: number;
  blendMode?: number;
}

export interface DamageParticleConfig extends ParticleConfig {
  damageAmount: number;
  isCritical?: boolean;
}

export interface HealParticleConfig extends ParticleConfig {
  healAmount: number;
}

// ------------------------------------------------------------
// ParticleSystem - управление визуальными эффектами частиц
// ------------------------------------------------------------

export class ParticleSystem {
  private scene: Phaser.Scene;
  private emitters: Map<string, Phaser.GameObjects.Particles.ParticleEmitter> = new Map();
  private manualParticles: Set<Phaser.GameObjects.GameObject> = new Set();

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  // ------------------------------------------------------------
  // Damage Particles - Частицы урона
  // ------------------------------------------------------------

  /**
   * Создаёт эффект частиц при получении урона
   * @param x Позиция X
   * @param y Позиция Y
   * @param amount Количество урона (определяет количество частиц)
   */
  public emitDamage(x: number, y: number, amount: number): void {
    const particleCount = Math.min(Math.max(Math.floor(amount / 2) + 5, 8), 30);

    // Используем встроенный particle emitter если доступен
    if (this.scene.add.particles) {
      this.createDamageEmitter(x, y, particleCount);
    } else {
      // Fallback на ручное создание частиц
      this.createManualDamageParticles(x, y, particleCount);
    }

    // Дополнительные искры
    this.createSparks(x, y, 0xff4444, particleCount);
  }

  private createDamageEmitter(x: number, y: number, count: number): void {
    const texture = this.createParticleTexture(0xff4444);

    const emitter = this.scene.add.particles(x, y, texture, {
      speed: { min: 50, max: 150 },
      angle: { min: 180, max: 360 },
      scale: { start: 0.8, end: 0 },
      alpha: { start: 1, end: 0 },
      lifespan: 400,
      quantity: count,
      blendMode: Phaser.BlendModes.ADD,
      emitting: false,
    }) as Phaser.GameObjects.Particles.ParticleEmitter;

    emitter.explode(count);
    this.registerEmitter(`damage-${Date.now()}`, emitter);

    // Очищаем через время
    this.scene.time.delayedCall(500, () => {
      this.destroyEmitter(emitter);
      if (texture && texture !== 'damage-particle') {
        // Текстура будет очищена автоматически при уничтожении сцены
      }
    });
  }

  private createManualDamageParticles(x: number, y: number, count: number): void {
    for (let i = 0; i < count; i++) {
      const angle = Phaser.Math.FloatBetween(0, Math.PI * 2);
      const speed = Phaser.Math.FloatBetween(50, 150);
      const distance = Phaser.Math.FloatBetween(30, 80);

      const particle = this.scene.add.circle(x, y, Phaser.Math.FloatBetween(2, 5), 0xff4444);
      particle.setAlpha(1);
      this.manualParticles.add(particle);

      const targetX = x + Math.cos(angle) * distance;
      const targetY = y + Math.sin(angle) * distance;

      this.scene.tweens.add({
        targets: particle,
        x: targetX,
        y: targetY,
        alpha: 0,
        scale: 0,
        duration: Phaser.Math.FloatBetween(300, 500),
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => {
          this.manualParticles.delete(particle);
          particle.destroy();
        },
      });
    }
  }

  // ------------------------------------------------------------
  // Heal Particles - Частицы лечения
  // ------------------------------------------------------------

  /**
   * Создаёт эффект частиц при лечении
   * @param x Позиция X
   * @param y Позиция Y
   * @param amount Количество лечения
   */
  public emitHeal(x: number, y: number, amount: number): void {
    const particleCount = Math.min(Math.max(Math.floor(amount / 2) + 5, 8), 25);

    // Зелёные частицы, поднимающиеся вверх
    for (let i = 0; i < particleCount; i++) {
      const offsetX = Phaser.Math.FloatBetween(-30, 30);
      const startX = x + offsetX;
      const startY = y;
      const endY = y - Phaser.Math.FloatBetween(60, 100);

      // Создаём частицу (крест или круг)
      const particle = this.scene.add.circle(startX, startY, Phaser.Math.FloatBetween(3, 6), 0x4ecca3);
      particle.setAlpha(0.8);
      this.manualParticles.add(particle);

      this.scene.tweens.add({
        targets: particle,
        y: endY,
        x: startX + offsetX * 0.5,
        alpha: 0,
        duration: Phaser.Math.FloatBetween(600, 1000),
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => {
          this.manualParticles.delete(particle);
          particle.destroy();
        },
      });
    }

    // Добавляем несколько "сердечек" или крестов
    for (let i = 0; i < 3; i++) {
      setTimeout(() => {
        const heart = this.createHeart(x + Phaser.Math.FloatBetween(-20, 20), y);
        this.manualParticles.add(heart);

        this.scene.tweens.add({
          targets: heart,
          y: y - 80,
          alpha: 0,
          scale: 1.5,
          duration: 1200,
          ease: Phaser.Math.Easing.Quadratic.Out,
          onComplete: () => {
            this.manualParticles.delete(heart);
            heart.destroy();
          },
        });
      }, i * 150);
    }
  }

  private createHeart(x: number, y: number): Phaser.GameObjects.Container {
    const container = this.scene.add.container(x, y);

    // Создаём форму сердца из двух кругов и треугольника
    const leftCircle = this.scene.add.circle(-5, 0, 6, 0x44ff88);
    const rightCircle = this.scene.add.circle(5, 0, 6, 0x44ff88);
    const triangle = this.scene.add.triangle(0, 5, 0, 0, -12, 15, 12, 15, 0x44ff88);

    container.add([leftCircle, rightCircle, triangle]);
    container.setScale(0.8);

    return container;
  }

  // ------------------------------------------------------------
  // Card Draw Particles - Частицы вытягивания карт
  // ------------------------------------------------------------

  /**
   * Создаёт эффект при вытягивании карты
   * @param x Позиция X
   * @param y Позиция Y
   */
  public emitCardDraw(x: number, y: number): void {
    // Голубые искры
    this.createSparks(x, y, 0x4488ff, 12);

    // Свечение вокруг позиции
    const glow = this.scene.add.graphics();
    glow.lineStyle(3, 0x4488ff, 0.6);
    glow.strokeCircle(x, y, 25);

    this.scene.tweens.add({
      targets: glow,
      scale: 2,
      alpha: 0,
      duration: 400,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => glow.destroy(),
    });

    // Летающие частицы
    for (let i = 0; i < 8; i++) {
      const angle = (Math.PI * 2 * i) / 8;
      const particle = this.scene.add.circle(
        x + Math.cos(angle) * 10,
        y + Math.sin(angle) * 10,
        2,
        0x88ccff
      );
      particle.setAlpha(0.8);

      this.scene.tweens.add({
        targets: particle,
        x: x + Math.cos(angle) * 40,
        y: y + Math.sin(angle) * 40,
        alpha: 0,
        duration: 500,
        delay: i * 30,
        onComplete: () => particle.destroy(),
      });
    }
  }

  // ------------------------------------------------------------
  // Card Play Particles - Частицы розыгрыша карты
  // ------------------------------------------------------------

  /**
   * Создаёт эффект при розыгрыше карты
   * @param x Позиция X
   * @param y Позиция Y
   */
  public emitCardPlay(x: number, y: number): void {
    // Всплеск золотых частиц
    this.emitBurst(x, y, 0xffd700, 20);

    // Кольцевая волна
    const ring = this.scene.add.graphics();
    ring.lineStyle(4, 0xffd700, 0.8);
    ring.strokeCircle(x, y, 20);

    this.scene.tweens.add({
      targets: ring,
      scale: 3,
      alpha: 0,
      duration: 500,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onUpdate: () => {
        ring.clear();
        ring.lineStyle(4, 0xffd700, ring.alpha);
        ring.strokeCircle(x, y, 20 * ring.scaleX);
      },
      onComplete: () => ring.destroy(),
    });

    // Звёздочки
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI * 2 * i) / 6;
      const star = this.createStar(
        x + Math.cos(angle) * 15,
        y + Math.sin(angle) * 15
      );

      this.scene.tweens.add({
        targets: star,
        x: x + Math.cos(angle) * 60,
        y: y + Math.sin(angle) * 60,
        alpha: 0,
        rotation: Math.PI,
        duration: 600,
        ease: Phaser.Math.Easing.Back.Out,
        onComplete: () => star.destroy(),
      });
    }
  }

  private createStar(x: number, y: number): Phaser.GameObjects.Graphics {
    const star = this.scene.add.graphics();
    star.fillStyle(0xffff00, 1);

    // Рисуем простую звезду
    star.beginPath();
    for (let i = 0; i < 5; i++) {
      const angle = (Math.PI * 2 * i) / 5 - Math.PI / 2;
      const innerAngle = angle + Math.PI / 5;
      const outerX = x + Math.cos(angle) * 8;
      const outerY = y + Math.sin(angle) * 8;
      const innerX = x + Math.cos(innerAngle) * 4;
      const innerY = y + Math.sin(innerAngle) * 4;

      if (i === 0) {
        star.moveTo(outerX, outerY);
      } else {
        star.lineTo(outerX, outerY);
      }
      star.lineTo(innerX, innerY);
    }
    star.closePath();
    star.fillPath();

    return star;
  }

  // ------------------------------------------------------------
  // Zone Activation - Активация зоны
  // ------------------------------------------------------------

  /**
   * Создаёт эффект активации зоны на поле
   * @param x Позиция X центра зоны
   * @param y Позиция Y центра зоны
   * @param zoneColor Цвет зоны (blue, green, yellow, red, purple)
   */
  public emitZoneActivation(x: number, y: number, zoneColor: string): void {
    const colorMap: Record<string, number> = {
      blue: 0x4488ff,
      green: 0x4ecca3,
      yellow: 0xffcc00,
      red: 0xff4444,
      purple: 0x9966ff,
    };

    const color = colorMap[zoneColor] || 0xffffff;

    // Пульсирующий круг
    const circle = this.scene.add.graphics();
    circle.lineStyle(3, color, 0.8);
    circle.strokeCircle(x, y, 35);

    this.scene.tweens.add({
      targets: circle,
      alpha: { from: 0.8, to: 0.2 },
      scale: 1.2,
      duration: 800,
      yoyo: true,
      repeat: 1,
      onUpdate: () => {
        circle.clear();
        circle.lineStyle(3, color, circle.alpha);
        circle.strokeCircle(x, y, 35 * circle.scaleX);
      },
      onComplete: () => circle.destroy(),
    });

    // Частицы по краям зоны
    for (let i = 0; i < 12; i++) {
      const angle = (Math.PI * 2 * i) / 12;
      const particle = this.scene.add.circle(
        x + Math.cos(angle) * 35,
        y + Math.sin(angle) * 35,
        3,
        color
      );

      this.scene.tweens.add({
        targets: particle,
        x: x + Math.cos(angle) * 50,
        y: y + Math.sin(angle) * 50,
        alpha: 0,
        duration: 500,
        delay: i * 30,
        onComplete: () => particle.destroy(),
      });
    }
  }

  // ------------------------------------------------------------
  // Burst - Общий эффект всплеска частиц
  // ------------------------------------------------------------

  /**
   * Создаёт общий эффект всплеска частиц заданного цвета
   * @param x Позиция X
   * @param y Позиция Y
   * @param color Цвет частиц
   * @param count Количество частиц
   */
  public emitBurst(x: number, y: number, color: number, count: number = 15): void {
    for (let i = 0; i < count; i++) {
      const angle = Phaser.Math.FloatBetween(0, Math.PI * 2);
      const speed = Phaser.Math.FloatBetween(80, 180);
      const distance = Phaser.Math.FloatBetween(40, 90);
      const size = Phaser.Math.FloatBetween(2, 5);

      const particle = this.scene.add.circle(x, y, size, color);
      particle.setAlpha(1);

      const targetX = x + Math.cos(angle) * distance;
      const targetY = y + Math.sin(angle) * distance;

      this.scene.tweens.add({
        targets: particle,
        x: targetX,
        y: targetY,
        alpha: 0,
        scale: 0.3,
        duration: Phaser.Math.FloatBetween(300, 600),
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => particle.destroy(),
      });
    }
  }

  // ------------------------------------------------------------
  // Status Effect Particles - Частицы статусных эффектов
  // ------------------------------------------------------------

  /**
   * Создаёт эффект для статусного эффекта (например, отравление, горение)
   * @param x Позиция X
   * @param y Позиция Y
   * @param statusType Тип статуса (poison, burn, shield, etc.)
   */
  public emitStatusEffect(x: number, y: number, statusType: string): void {
    switch (statusType) {
      case 'poison':
        this.createPoisonEffect(x, y);
        break;
      case 'burn':
        this.createBurnEffect(x, y);
        break;
      case 'shield':
        this.createShieldEffect(x, y);
        break;
      case 'stun':
        this.createStunEffect(x, y);
        break;
      case 'buff':
        this.createBuffEffect(x, y);
        break;
    }
  }

  private createPoisonEffect(x: number, y: number): void {
    // Зелёные пузырьки, поднимающиеся вверх
    for (let i = 0; i < 5; i++) {
      const bubble = this.scene.add.circle(
        x + Phaser.Math.FloatBetween(-15, 15),
        y + Phaser.Math.FloatBetween(0, 20),
        Phaser.Math.FloatBetween(2, 5),
        0x44ff44
      );
      bubble.setAlpha(0.6);

      this.scene.tweens.add({
        targets: bubble,
        y: y - Phaser.Math.FloatBetween(30, 60),
        alpha: 0,
        duration: Phaser.Math.FloatBetween(800, 1200),
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => bubble.destroy(),
      });
    }
  }

  private createBurnEffect(x: number, y: number): void {
    // Огненные частицы
    for (let i = 0; i < 8; i++) {
      const spark = this.scene.add.circle(
        x + Phaser.Math.FloatBetween(-10, 10),
        y + Phaser.Math.FloatBetween(-10, 10),
        Phaser.Math.FloatBetween(2, 4),
        0xff6600
      );
      spark.setAlpha(1);

      this.scene.tweens.add({
        targets: spark,
        y: y - Phaser.Math.FloatBetween(40, 80),
        x: x + Phaser.Math.FloatBetween(-20, 20),
        alpha: 0,
        duration: Phaser.Math.FloatBetween(400, 700),
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => spark.destroy(),
      });
    }
  }

  private createShieldEffect(x: number, y: number): void {
    // Синё свечение щита
    const shield = this.scene.add.graphics();
    shield.lineStyle(3, 0x4488ff, 0.6);
    shield.beginPath();
    shield.arc(x, y, 30, Math.PI, 0);
    shield.strokePath();

    this.scene.tweens.add({
      targets: shield,
      alpha: 0,
      scale: 1.3,
      duration: 600,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => shield.destroy(),
    });
  }

  private createStunEffect(x: number, y: number): void {
    // Жёлтые звёздочки вокруг головы
    for (let i = 0; i < 4; i++) {
      const angle = (Math.PI * 2 * i) / 4;
      const star = this.createStar(
        x + Math.cos(angle) * 25,
        y - 30 + Math.sin(angle) * 10
      );

      this.scene.tweens.add({
        targets: star,
        y: star.y - 20,
        alpha: 0,
        rotation: Math.PI * 2,
        duration: 800,
        delay: i * 100,
        onComplete: () => star.destroy(),
      });
    }
  }

  private createBuffEffect(x: number, y: number): void {
    // Золотое свечение вверх
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2;
      const ray = this.scene.add.graphics();
      ray.fillStyle(0xffd700, 0.4);
      ray.fillRect(x, y, 4, 30);
      ray.setPosition(x, y);
      ray.setRotation(angle);

      this.scene.tweens.add({
        targets: ray,
        y: y - 30,
        alpha: 0,
        duration: 500,
        delay: i * 50,
        onComplete: () => ray.destroy(),
      });
    }
  }

  // ------------------------------------------------------------
  // Utility Methods
  // ------------------------------------------------------------

  /**
   * Создаёт искры в заданной позиции
   */
  private createSparks(x: number, y: number, color: number, count: number): void {
    for (let i = 0; i < count; i++) {
      const spark = this.scene.add.circle(
        x + (Math.random() - 0.5) * 20,
        y + (Math.random() - 0.5) * 20,
        Math.random() * 2 + 1,
        color
      );
      spark.setAlpha(1);

      this.scene.tweens.add({
        targets: spark,
        alpha: 0,
        scale: 0,
        duration: 100 + Math.random() * 200,
        onComplete: () => spark.destroy(),
      });
    }
  }

  /**
   * Создаёт текстуру для частицы (для emitter)
   */
  private createParticleTexture(color: number): string {
    // Используем простой круг как текстуру
    // В Phaser 3 можно использовать встроенные текстуры
    return '__WHITE';
  }

  /**
   * Регистрирует emitter для последующего удаления
   */
  private registerEmitter(id: string, emitter: Phaser.GameObjects.Particles.ParticleEmitter): void {
    this.emitters.set(id, emitter);
  }

  /**
   * Уничтожает emitter
   */
  private destroyEmitter(emitter: Phaser.GameObjects.Particles.ParticleEmitter): void {
    if (emitter) {
      emitter.destroy();
    }
  }

  // ------------------------------------------------------------
  // Очистка и уничтожение
  // ------------------------------------------------------------

  /**
   * Останавливает все активные эммитеры
   */
  public stopAll(): void {
    this.emitters.forEach(emitter => {
      if (emitter && emitter.scene) {
        emitter.stop();
      }
    });
  }

  /**
   * Удаляет все частицы
   */
  public clearAll(): void {
    // Удаляем все эммитеры
    this.emitters.forEach(emitter => {
      if (emitter && emitter.scene) {
        emitter.destroy();
      }
    });
    this.emitters.clear();

    // Удаляем все ручные частицы
    this.manualParticles.forEach(particle => {
      if (particle && particle.scene) {
        particle.destroy();
      }
    });
    this.manualParticles.clear();
  }

  /**
   * Уничтожает систему частиц
   */
  public destroy(): void {
    this.clearAll();
  }
}
