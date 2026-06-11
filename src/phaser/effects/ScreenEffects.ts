// ============================================================
// SCREEN EFFECTS - Эффекты экрана (тряска, вспышки, затемнение)
// ============================================================

import * as Phaser from 'phaser';

// ------------------------------------------------------------
// Конфигурация эффектов экрана
// ------------------------------------------------------------

export interface ShakeConfig {
  intensity?: number;      // Интенсивность тряски (0.01 - 0.1)
  duration?: number;       // Длительность в мс
  x?: boolean;             // Тряска по X
  y?: boolean;             // Тряска по Y
}

export interface FlashConfig {
  color?: number;          // Цвет вспышки
  duration?: number;       // Длительность в мс
  alpha?: number;          // Максимальная прозрачность
}

export interface FadeConfig {
  duration?: number;       // Длительность в мс
  color?: number;          // Цвет затемнения
  delay?: number;          // Задержка перед началом
}

export interface SlowMotionConfig {
  enabled: boolean;        // Включить/выключить
  factor?: number;         // Коэффициент замедления (0.1 - 1.0)
  duration?: number;       // Длительность в мс (для временного замедления)
}

// ------------------------------------------------------------
// ScreenEffects - управление эффектами экрана
// ------------------------------------------------------------

export class ScreenEffects {
  private scene: Phaser.Scene;
  private camera: Phaser.Cameras.Scene2D.Camera;
  private isShaking: boolean = false;
  private isFading: boolean = false;
  private originalTimeScale: number = 1;
  private slowMotionTween?: Phaser.Tweens.Tween;
  private flashOverlay?: Phaser.GameObjects.Rectangle;

  // Для эффекта тряски
  private shakeTween?: Phaser.Tweens.Tween;
  private originalCameraPosition: { x: number; y: number };

  constructor(scene: Phaser.Scene, camera?: Phaser.Cameras.Scene2D.Camera) {
    this.scene = scene;
    this.camera = camera || scene.cameras.main;
    this.originalCameraPosition = { x: this.camera.scrollX, y: this.camera.scrollY };
  }

  // ------------------------------------------------------------
  // Shake - Тряска экрана
  // ------------------------------------------------------------

  /**
   * Запускает тряску экрана
   * @param intensity Интенсивность тряски (0.01 - 0.1)
   * @param duration Длительность в мс
   * @param config Дополнительная конфигурация
   */
  public shake(config?: ShakeConfig): void;
  public shake(intensity?: number, duration?: number): void;
  public shake(
    intensityOrConfig?: number | ShakeConfig,
    duration?: number
  ): void {
    if (this.isShaking) {
      return; // Уже трясётся
    }

    let intensity: number;
    let shakeDuration: number;
    let shakeX: boolean = true;
    let shakeY: boolean = true;

    if (typeof intensityOrConfig === 'object' && intensityOrConfig !== null) {
      intensity = intensityOrConfig.intensity ?? 0.01;
      shakeDuration = intensityOrConfig.duration ?? 200;
      shakeX = intensityOrConfig.x ?? true;
      shakeY = intensityOrConfig.y ?? true;
    } else {
      intensity = intensityOrConfig ?? 0.01;
      shakeDuration = duration ?? 200;
    }

    // Приводим к числу для безопасности
    intensity = Number(intensity);
    shakeDuration = Number(shakeDuration);

    this.isShaking = true;
    this.originalCameraPosition = { x: this.camera.scrollX, y: this.camera.scrollY };

    // Количество колебаний
    const shakeCount = Math.floor(shakeDuration / 16);
    let currentShake = 0;

    // Создаём эффект тряски через повторяющиеся tween
    const shake = (): void => {
      if (currentShake >= shakeCount) {
        // Завершаем тряску
        this.camera.setScroll(this.originalCameraPosition.x, this.originalCameraPosition.y);
        this.isShaking = false;
        return;
      }

      // Случайное смещение
      const offsetX = shakeX ? (Math.random() - 0.5) * intensity * this.camera.width : 0;
      const offsetY = shakeY ? (Math.random() - 0.5) * intensity * this.camera.height : 0;

      this.camera.setScroll(
        this.originalCameraPosition.x + offsetX,
        this.originalCameraPosition.y + offsetY
      );

      currentShake++;
      this.scene.time.delayedCall(16, shake);
    };

    shake();

    // Автоматическое восстановление через указанное время
    this.scene.time.delayedCall(shakeDuration, () => {
      this.isShaking = false;
      this.camera.setScroll(this.originalCameraPosition.x, this.originalCameraPosition.y);
    });
  }

  /**
   * Останавливает тряску экрана
   */
  public stopShake(): void {
    this.isShaking = false;
    this.camera.setScroll(this.originalCameraPosition.x, this.originalCameraPosition.y);
  }

  // ------------------------------------------------------------
  // Flash - Вспышка экрана
  // ------------------------------------------------------------

  /**
   * Создаёт вспышку экрана заданного цвета
   * @param color Цвет вспышки
   * @param duration Длительность в мс
   * @param config Дополнительная конфигурация
   */
  public flash(config?: FlashConfig): void;
  public flash(color?: number, duration?: number): void;
  public flash(
    colorOrConfig?: number | FlashConfig,
    duration?: number
  ): void {
    let color: number;
    let flashDuration: number;
    let alpha: number = 0.5;

    if (typeof colorOrConfig === 'object' && colorOrConfig !== null) {
      color = Number(colorOrConfig.color ?? 0xffffff);
      flashDuration = Number(colorOrConfig.duration ?? 100);
      alpha = Number(colorOrConfig.alpha ?? 0.5);
    } else {
      color = Number(colorOrConfig ?? 0xffffff);
      flashDuration = Number(duration ?? 100);
    }

    // Создаём оверлей для вспышки
    if (!this.flashOverlay || !this.flashOverlay.scene) {
      this.flashOverlay = this.scene.add.rectangle(
        this.camera.width / 2,
        this.camera.height / 2,
        this.camera.width,
        this.camera.height,
        color
      );
      this.flashOverlay.setOrigin(0.5);
      this.flashOverlay.setAlpha(0);
      this.flashOverlay.setDepth(10000); // Поверх всего
    } else {
      this.flashOverlay.setFillStyle(color);
      this.flashOverlay.setVisible(true);
    }

    // Анимация вспышки
    this.scene.tweens.add({
      targets: this.flashOverlay,
      alpha: alpha,
      duration: flashDuration * 0.3,
      yoyo: true,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => {
        this.flashOverlay?.setVisible(false);
      },
    });
  }

  /**
   * Создаёт множественные вспышки (например, для молний)
   * @param count Количество вспышек
   * @param interval Интервал между вспышками в мс
   * @param color Цвет вспышек
   */
  public multiFlash(count: number, interval: number = 100, color: number = 0xffffff): void {
    for (let i = 0; i < count; i++) {
      this.scene.time.delayedCall(i * interval, () => {
        this.flash(color, 50);
      });
    }
  }

  // ------------------------------------------------------------
  // Fade - Затемнение/осветление экрана
  // ------------------------------------------------------------

  /**
   * Затемняет экран (fade out)
   * @param duration Длительность в мс
   * @param color Цвет затемнения
   * @returns Promise, который резолвится по завершении
   */
  public fadeOut(config?: FadeConfig): Promise<void>;
  public fadeOut(duration?: number, color?: number): Promise<void>;
  public fadeOut(
    durationOrConfig?: number | FadeConfig,
    color?: number
  ): Promise<void> {
    return new Promise((resolve) => {
      if (this.isFading) {
        resolve();
        return;
      }

      let fadeDuration: number;
      let fadeColor: number;
      let delay: number = 0;

      if (typeof durationOrConfig === 'object' && durationOrConfig !== null) {
        fadeDuration = Number(durationOrConfig.duration ?? 500);
        fadeColor = Number(durationOrConfig.color ?? 0x000000);
        delay = Number(durationOrConfig.delay ?? 0);
      } else {
        fadeDuration = Number(durationOrConfig ?? 500);
        fadeColor = Number(color ?? 0x000000);
      }

      this.isFading = true;

      const onFadeStart = () => {
        this.camera.fade(fadeDuration, fadeColor, false, undefined);
        this.camera.once('camerafadeoutcomplete', () => {
          this.isFading = false;
          resolve();
        });
      };

      if (delay > 0) {
        this.scene.time.delayedCall(delay, onFadeStart);
      } else {
        onFadeStart();
      }
    });
  }

  /**
   * Осветляет экран (fade in)
   * @param duration Длительность в мс
   * @param color Цвет из которого выходим
   * @returns Promise, который резолвится по завершении
   */
  public fadeIn(config?: FadeConfig): Promise<void>;
  public fadeIn(duration?: number, color?: number): Promise<void>;
  public fadeIn(
    durationOrConfig?: number | FadeConfig,
    color?: number
  ): Promise<void> {
    return new Promise((resolve) => {
      if (this.isFading) {
        resolve();
        return;
      }

      let fadeDuration: number;
      let fadeColor: number;
      let delay: number = 0;

      if (typeof durationOrConfig === 'object' && durationOrConfig !== null) {
        fadeDuration = Number(durationOrConfig.duration ?? 500);
        fadeColor = Number(durationOrConfig.color ?? 0x000000);
        delay = Number(durationOrConfig.delay ?? 0);
      } else {
        fadeDuration = Number(durationOrConfig ?? 500);
        fadeColor = Number(color ?? 0x000000);
      }

      this.isFading = true;

      // Сначала устанавливаем затемнение
      // this.camera.setFlash(fadeColor); // Может не работать в некоторых версиях

      const onFadeStart = () => {
        this.camera.fadeFrom(fadeDuration, fadeColor, false, undefined);
        this.camera.once('camerafadeincomplete', () => {
          this.isFading = false;
          resolve();
        });
      };

      if (delay > 0) {
        this.scene.time.delayedCall(delay, onFadeStart);
      } else {
        onFadeStart();
      }
    });
  }

  /**
   * Последовательный fade out затем fade in (для переходов)
   * @param duration Длительность каждого fade
   * @param holdTime Время удержания полностью затемнённого экрана
   * @returns Promise, который резолвится по завершении
   */
  public async fadeTransition(duration: number = 500, holdTime: number = 200): Promise<void> {
    await this.fadeOut(duration);
    await new Promise(resolve => this.scene.time.delayedCall(holdTime, resolve));
    await this.fadeIn(duration);
  }

  /**
   * Останавливает все активные fade эффекты
   */
  public stopFade(): void {
    this.camera.resetFX();
    this.isFading = false;
  }

  // ------------------------------------------------------------
  // Slow Motion - Замедление времени
  // ------------------------------------------------------------

  /**
   * Включает или выключает замедление времени
   * @param enabled Включить/выключить
   * @param factor Коэффициент замедления (0.1 - 1.0)
   * @param duration Длительность в мс (если указано, автоматическое выключение)
   */
  public setSlowMotion(
    enabled: boolean,
    factor: number = 0.5,
    duration?: number
  ): void {
    if (enabled) {
      // Сохраняем оригинальный scale
      if (this.originalTimeScale === 1 && this.scene.time.timeScale !== 1) {
        this.originalTimeScale = this.scene.time.timeScale;
      }

      // Устанавливаем замедление
      this.scene.time.timeScale = Math.max(0.1, Math.min(1, factor));

      // Если указана длительность, автоматически отключаем
      if (duration) {
        if (this.slowMotionTween) {
          this.slowMotionTween.destroy();
        }

        this.slowMotionTween = this.scene.tweens.add({
          targets: { dummy: 0 },
          dummy: 1,
          duration: duration,
          onComplete: () => {
            this.setSlowMotion(false);
          },
        });
      }
    } else {
      // Восстанавливаем оригинальную скорость
      this.scene.time.timeScale = this.originalTimeScale;
      this.originalTimeScale = 1;

      if (this.slowMotionTween) {
        this.slowMotionTween.destroy();
        this.slowMotionTween = undefined;
      }
    }
  }

  /**
   * Плавно переходит к указанному timeScale
   * @param targetTimeScale Целевой scale
   * @param duration Длительность перехода в мс
   */
  public tweenTimeScale(targetTimeScale: number, duration: number = 500): Promise<void> {
    return new Promise((resolve) => {
      const startScale = this.scene.time.timeScale;

      if (startScale === targetTimeScale) {
        resolve();
        return;
      }

      this.scene.tweens.addCounter({
        from: startScale,
        to: targetTimeScale,
        duration,
        ease: Phaser.Math.Easing.Quadratic.InOut,
        onUpdate: (tween) => {
          this.scene.time.timeScale = tween.getValue();
        },
        onComplete: () => {
          this.originalTimeScale = targetTimeScale;
          resolve();
        },
      });
    });
  }

  /**
   * Создаёт эффект "bullet time" - резкое замедление с последующим ускорением
   * @param slowFactor Коэффициент замедления
   * @param slowDuration Длительность замедления
   * @param recoveryDuration Длительность восстановления скорости
   */
  public async bulletTime(
    slowFactor: number = 0.2,
    slowDuration: number = 500,
    recoveryDuration: number = 1000
  ): Promise<void> {
    // Замедляем
    await this.tweenTimeScale(slowFactor, 200);

    // Удерживаем
    await new Promise(resolve => this.scene.time.delayedCall(slowDuration, resolve));

    // Восстанавливаем
    await this.tweenTimeScale(1, recoveryDuration);
  }

  // ------------------------------------------------------------
  // Zoom - Эффекты масштабирования
  // ------------------------------------------------------------

  /**
   * Плавно изменяет масштаб камеры
   * @param zoom Целевой масштаб
   * @param duration Длительность в мс
   * @returns Promise, который резолвится по завершении
   */
  public zoom(zoom: number, duration: number = 500): Promise<void> {
    return new Promise((resolve) => {
      this.scene.tweens.add({
        targets: this.camera,
        zoom: Math.max(0.1, zoom),
        duration,
        ease: Phaser.Math.Easing.Quadratic.InOut,
        onComplete: () => resolve(),
      });
    });
  }

  /**
   * Эффект "удара" - быстрое увеличение и возврат
   * @param intensity Интенсивность (1.0 - 1.5)
   */
  public impactZoom(intensity: number = 1.1): void {
    const originalZoom = this.camera.zoom;

    this.scene.tweens.add({
      targets: this.camera,
      zoom: originalZoom * intensity,
      duration: 100,
      ease: Phaser.Math.Easing.Quadratic.Out,
      yoyo: true,
    });
  }

  // ------------------------------------------------------------
  // Camera Effects - Дополнительные эффекты камеры
  // ------------------------------------------------------------

  /**
   * Эффект линейного перемещения камеры к точке
   * @param x Целевая позиция X
   * @param y Целевая позиция Y
   * @param duration Длительность в мс
   */
  public panTo(x: number, y: number, duration: number = 1000): Promise<void> {
    return new Promise((resolve) => {
      this.scene.tweens.add({
        targets: this.camera,
        scrollX: x,
        scrollY: y,
        duration,
        ease: Phaser.Math.Easing.Quadratic.InOut,
        onComplete: () => resolve(),
      });
    });
  }

  /**
   * Следование за объектом
   * @param target Объект для следования
   * @param config Конфигурация следования (используется упрощённая версия)
   */
  public startFollow(
    target: Phaser.GameObjects.GameObject,
    config?: Record<string, unknown>
  ): void {
    this.camera.startFollow(target, false, 0.1, 0.1);
  }

  /**
   * Остановка следования
   */
  public stopFollow(): void {
    this.camera.stopFollow();
  }

  // ------------------------------------------------------------
  // Color Effects - Цветовые эффекты (через оверлей)
  // ------------------------------------------------------------
  // Примечание: В Phaser 3 нет прямых методов setTint на камере.
  // Для цветовых эффектов можно использовать оверлеи или пост-эффекты.

  /**
   * Применяет цветовой фильтр через оверлей
   * @param color Цвет (0xRRGGBB)
   * @param intensity Интенсивность (0-1)
   */
  public setColorTint(color: number, intensity: number = 0.5): void {
    // Создаём постоянный оверлей с цветом
    const overlay = this.scene.add.rectangle(
      this.camera.width / 2,
      this.camera.height / 2,
      this.camera.width,
      this.camera.height,
      color,
      intensity
    );
    overlay.setDepth(9999);
    overlay.setScrollFactor(0, 0);
    // Сохраняем ссылку для последующего удаления
    (this as any)._tintOverlay = overlay;
  }

  /**
   * Сбрасывает цветовой фильтр
   */
  public clearColorTint(): void {
    const overlay = (this as any)._tintOverlay;
    if (overlay) {
      overlay.destroy();
      (this as any)._tintOverlay = null;
    }
  }

  /**
   * Эффект сепии через оверлей
   * @param intensity Интенсивность (0-1)
   */
  public setSepia(intensity: number = 0.5): void {
    // Сепия: коричневатый оттенок (RGB: 240, 230, 140)
    this.setColorTint(0xf0e68c, intensity * 0.3);
  }

  /**
   * Чёрно-белый эффект через оверлей
   * @param intensity Интенсивность (0-1)
   */
  public setGrayscale(intensity: number = 1): void {
    // Серый оверлей для десатурирования
    const overlay = this.scene.add.rectangle(
      this.camera.width / 2,
      this.camera.height / 2,
      this.camera.width,
      this.camera.height,
      0x808080,
      intensity * 0.5
    );
    overlay.setBlendMode(Phaser.BlendModes.SATURATION);
    overlay.setDepth(9999);
    overlay.setScrollFactor(0, 0);
    (this as any)._grayscaleOverlay = overlay;
  }

  // ------------------------------------------------------------
  // Combo Effects - Комбинированные эффекты
  // ------------------------------------------------------------

  /**
   * Эффект сильного удара - тряска + вспышка + zoom
   * @param intensity Интенсивность (0-1)
   */
  public heavyHit(intensity: number = 0.5): void {
    this.shake(0.03 + intensity * 0.03, 300);
    this.flash(0xff0000, 150);
    this.impactZoom(1 + intensity * 0.2);
  }

  /**
   * Эффект критического удара - более мощная версия
   */
  public criticalHit(): void {
    this.shake(0.05, 400);
    this.multiFlash(3, 80, 0xff0000);
    this.impactZoom(1.3);
  }

  /**
   * Эффект победы - яркая вспышка и конфетти
   */
  public victoryEffect(): void {
    this.flash(0xffff00, 300);
    this.multiFlash(5, 100, 0xffd700);
  }

  /**
   * Эффект поражения - затемнение
   */
  public defeatEffect(): Promise<void> {
    return this.fadeOut(1000, 0x330000);
  }

  // ------------------------------------------------------------
  // Очистка и уничтожение
  // ------------------------------------------------------------

  /**
   * Сбрасывает все активные эффекты
   */
  public resetAll(): void {
    this.stopShake();
    this.stopFade();
    this.setSlowMotion(false);
    this.clearColorTint();
    this.camera.setZoom(1);

    if (this.flashOverlay) {
      this.flashOverlay.destroy();
      this.flashOverlay = undefined;
    }
  }

  /**
   * Уничтожает объект эффектов
   */
  public destroy(): void {
    this.resetAll();
  }
}
