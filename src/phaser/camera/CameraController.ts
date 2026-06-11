// ============================================================
// CAMERA CONTROLLER - Управление камерой
// ============================================================

import Phaser from 'phaser';
import type { GameScene } from '../renderers/BoardRenderer';
import type { Position } from '../../core/models/types';

/**
 * Пределы камеры
 */
export interface CameraBounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/**
 * Конфигурация камеры
 */
export interface CameraConfig {
  zoomMin: number;
  zoomMax: number;
  zoomStep: number;
  panDuration: number;
  followSmoothness: number;
  followOffset: { x: number; y: number };
}

/**
 * Режимы камеры
 */
export enum CameraMode {
  FREE = 'free',           // Свободное управление
  FOLLOW = 'follow',       // Следование за бойцом
  LOCKED = 'locked',       // Зафиксирована
  CINEMATIC = 'cinematic'  // Кинематографический режим
}

/**
 * Контроллер камеры
 *
 * Отвечает за:
 * - Следование за выбранным бойцом
 * - Плавное перемещение к позиции
 * - Зумming (приближение/отдаление)
 * - Ограничение границами поля
 * - Плавные переходы между режимами
 */
export class CameraController {
  private scene: GameScene;
  private camera: Phaser.Cameras.Scene2D.Camera;
  private config: CameraConfig;

  // Состояние камеры
  private currentMode: CameraMode = CameraMode.FREE;
  private followedFighterId: string | null = null;
  private targetPosition: { x: number; y: number } | null = null;
  private targetZoom: number = 1;

  // Референсы на спрайты бойцов
  private fighterSprites: Map<string, Phaser.GameObjects.Container> = new Map();

  // Обработчики событий клавиатуры
  private keys?: {
    up: Phaser.Input.Keyboard.Key;
    down: Phaser.Input.Keyboard.Key;
    left: Phaser.Input.Keyboard.Key;
    right: Phaser.Input.Keyboard.Key;
    zoomIn: Phaser.Input.Keyboard.Key;
    zoomOut: Phaser.Input.Keyboard.Key;
    reset: Phaser.Input.Keyboard.Key;
  };

  // Границы камеры
  private bounds: CameraBounds | null = null;

  constructor(scene: GameScene, camera?: Phaser.Cameras.Scene2D.Camera, config?: Partial<CameraConfig>) {
    this.scene = scene;
    this.camera = camera || scene.cameras.main;

    this.config = {
      zoomMin: 0.5,
      zoomMax: 2,
      zoomStep: 0.1,
      panDuration: 500,
      followSmoothness: 0.1,
      followOffset: { x: 0, y: 100 },
      ...config
    };

    // Настраиваем камеру
    this.setupCamera();

    // Настраиваем управление
    this.setupControls();
  }

  /**
   * Настраивает начальные параметры камеры
   */
  private setupCamera(): void {
    // Устанавливаем центр камеры
    this.camera.setOrigin(0.5, 0.5);

    // Включаем плавность следования
    this.camera.setLerp(this.config.followSmoothness, this.config.followSmoothness);
  }

  /**
   * Настраивает управление камерой с клавиатуры
   */
  private setupControls(): void {
    // Проверяем наличие клавиатуры
    if (!this.scene.input.keyboard) return;

    // Создаём клавиши
    this.keys = {
      up: this.scene.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.W),
      down: this.scene.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.S),
      left: this.scene.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.A),
      right: this.scene.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.D),
      zoomIn: this.scene.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.Q),
      zoomOut: this.scene.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.E),
      reset: this.scene.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.R)
    };

    // Добавляем обработчики для зума колёсиком мыши
    this.scene.input.on('wheel', this.handleMouseWheel.bind(this));

    // Добавляем обработчик для перетаскивания средней кнопкой
    this.setupMiddleMousePan();
  }

  /**
   * Настраивает перетаскивание камеры средней кнопкой мыши
   */
  private setupMiddleMousePan(): void {
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let cameraStartX = 0;
    let cameraStartY = 0;

    this.scene.input.on('pointerdown', (pointer: Phaser.Input.Pointer) => {
      if (pointer.middleButtonDown()) {
        isDragging = true;
        dragStartX = pointer.x;
        dragStartY = pointer.y;
        cameraStartX = this.camera.scrollX;
        cameraStartY = this.camera.scrollY;
      }
    });

    this.scene.input.on('pointerup', (pointer: Phaser.Input.Pointer) => {
      if (!pointer.middleButtonDown()) {
        isDragging = false;
      }
    });

    this.scene.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
      if (isDragging) {
        const zoom = this.camera.zoom;
        const deltaX = (pointer.x - dragStartX) / zoom;
        const deltaY = (pointer.y - dragStartY) / zoom;

        this.camera.setScroll(
          cameraStartX - deltaX,
          cameraStartY - deltaY
        );
      }
    });
  }

  /**
   * Обрабатывает вращение колёсика мыши для зума
   */
  private handleMouseWheel(pointer: Phaser.Input.Pointer, gameObjects: any, deltaX: number, deltaY: number): void {
    const zoomDelta = deltaY > 0 ? -this.config.zoomStep : this.config.zoomStep;
    const newZoom = Phaser.Math.Clamp(
      this.camera.zoom + zoomDelta,
      this.config.zoomMin,
      this.config.zoomMax
    );

    // Зум к позиции курсора
    this.zoomToPoint(pointer.worldX, pointer.worldY, newZoom);
  }

  /**
   * Обновляет состояние камеры каждый кадр
   */
  update(): void {
    // Обрабатаем управление клавиатурой
    this.handleKeyboardInput();

    // Обрабатаем следование за бойцом
    if (this.currentMode === CameraMode.FOLLOW && this.followedFighterId) {
      this.updateFollow();
    }

    // Плавный зум
    if (this.targetZoom !== this.camera.zoom) {
      const zoomDiff = this.targetZoom - this.camera.zoom;
      if (Math.abs(zoomDiff) < 0.01) {
        this.camera.setZoom(this.targetZoom);
      } else {
        this.camera.setZoom(this.camera.zoom + zoomDiff * 0.1);
      }
    }
  }

  /**
   * Обрабатывает ввод с клавиатуры
   */
  private handleKeyboardInput(): void {
    if (!this.keys || this.currentMode === CameraMode.LOCKED) return;

    const panSpeed = 10 / this.camera.zoom;

    if (this.keys.up.isDown) {
      this.camera.setScroll(this.camera.scrollX, this.camera.scrollY - panSpeed);
    }
    if (this.keys.down.isDown) {
      this.camera.setScroll(this.camera.scrollX, this.camera.scrollY + panSpeed);
    }
    if (this.keys.left.isDown) {
      this.camera.setScroll(this.camera.scrollX - panSpeed, this.camera.scrollY);
    }
    if (this.keys.right.isDown) {
      this.camera.setScroll(this.camera.scrollX + panSpeed, this.camera.scrollY);
    }

    // Зум
    if (Phaser.Input.Keyboard.JustDown(this.keys.zoomIn)) {
      this.adjustZoom(this.config.zoomStep);
    }
    if (Phaser.Input.Keyboard.JustDown(this.keys.zoomOut)) {
      this.adjustZoom(-this.config.zoomStep);
    }

    // Сброс
    if (Phaser.Input.Keyboard.JustDown(this.keys.reset)) {
      this.resetView();
    }
  }

  /**
   * Обновляет слежение за бойцом
   */
  private updateFollow(): void {
    const fighterSprite = this.fighterSprites.get(this.followedFighterId!);
    if (fighterSprite) {
      this.camera.startFollow(fighterSprite, true, this.config.followSmoothness, this.config.followSmoothness);
    }
  }

  // ============================================================
  // ПУБЛИЧНЫЕ МЕТОДЫ
  // ============================================================

  /**
   * Заставляет камеру следовать за бойцом
   */
  followFighter(fighterId: string): void {
    this.followedFighterId = fighterId;
    this.currentMode = CameraMode.FOLLOW;

    const fighterSprite = this.fighterSprites.get(fighterId);
    if (fighterSprite) {
      this.camera.startFollow(
        fighterSprite,
        true,
        this.config.followSmoothness,
        this.config.followSmoothness,
        this.config.followOffset
      );
    }
  }

  /**
   * Перестаёт следовать за бойцом
   */
  stopFollowing(): void {
    this.followedFighterId = null;
    this.currentMode = CameraMode.FREE;
    this.camera.stopFollow();
  }

  /**
   * Плавно перемещает камеру к указанной позиции
   */
  panTo(x: number, y: number, duration?: number): void {
    const panDuration = duration ?? this.config.panDuration;

    this.scene.tweens.add({
      targets: this.camera,
      scrollX: x - this.camera.width / 2,
      scrollY: y - this.camera.height / 2,
      duration: panDuration,
      ease: Phaser.Math.Easing.Quadratic.InOut
    });
  }

  /**
   * Плавно перемещает камеру к позиции на поле
   */
  panToCell(cellX: number, cellY: number, cellSize: number, duration?: number): void {
    const worldX = cellX * cellSize + cellSize / 2;
    const worldY = cellY * cellSize + cellSize / 2;
    this.panTo(worldX, worldY, duration);
  }

  /**
   * Устанавливает мгновенную позицию камеры
   */
  setPosition(x: number, y: number): void {
    this.camera.setScroll(
      x - this.camera.width / 2,
      y - this.camera.height / 2
    );
  }

  /**
   * Устанавливает уровень зума
   */
  setZoom(level: number): void {
    this.targetZoom = Phaser.Math.Clamp(level, this.config.zoomMin, this.config.zoomMax);
  }

  /**
   * Плавно изменяет зум
   */
  adjustZoom(delta: number): void {
    this.setZoom(this.camera.zoom + delta);
  }

  /**
   * Зумит к точке на мире
   */
  zoomToPoint(worldX: number, worldY: number, zoomLevel: number): void {
    const currentZoom = this.camera.zoom;
    const newZoom = Phaser.Math.Clamp(zoomLevel, this.config.zoomMin, this.config.zoomMax);

    // Вычисляем новую позицию чтобы точка осталась на месте
    const zoomRatio = newZoom / currentZoom;
    const newX = worldX - (worldX - this.camera.midPoint.x) * zoomRatio;
    const newY = worldY - (worldY - this.camera.midPoint.y) * zoomRatio;

    this.camera.setZoom(newZoom);
    this.camera.centerOn(newX, newY);
  }

  /**
   * Устанавливает границы камеры
   */
  setBounds(bounds: CameraBounds): void {
    this.bounds = bounds;
    this.camera.setBounds(bounds.minX, bounds.minY, bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
  }

  /**
   * Устанавливает границы по размеру поля
   */
  setBoardBounds(width: number, height: number): void {
    this.setBounds({
      minX: 0,
      minY: 0,
      maxX: width,
      maxY: height
    });
  }

  /**
   * Сбрасывает вид к начальному состоянию
   */
  resetView(): void {
    this.stopFollowing();
    this.currentMode = CameraMode.FREE;

    const boardConfig = (this.scene as any).boardConfig;
    if (boardConfig) {
      const centerX = boardConfig.width * boardConfig.cellSize / 2;
      const centerY = boardConfig.height * boardConfig.cellSize / 2;
      this.panTo(centerX, centerY, 300);
    }

    this.setZoom(1);
  }

  /**
   * Устанавливает режим камеры
   */
  setMode(mode: CameraMode): void {
    this.currentMode = mode;

    switch (mode) {
      case CameraMode.FREE:
        this.stopFollowing();
        break;
      case CameraMode.LOCKED:
        this.stopFollowing();
        break;
      case CameraMode.CINEMATIC:
        this.stopFollowing();
        this.setZoom(0.8);
        break;
    }
  }

  /**
   * Получает текущий режим камеры
   */
  getMode(): CameraMode {
    return this.currentMode;
  }

  /**
   * Регистрирует спрайт бойца для слежения
   */
  registerFighterSprite(fighterId: string, sprite: Phaser.GameObjects.Container): void {
    this.fighterSprites.set(fighterId, sprite);
  }

  /**
   * Убирает спрайт бойца из слежения
   */
  unregisterFighterSprite(fighterId: string): void {
    this.fighterSprites.delete(fighterId);
    if (this.followedFighterId === fighterId) {
      this.stopFollowing();
    }
  }

  /**
   * Создаёт кинематографический панорамный shot
   */
  async playCinematicMove(positions: Array<{ x: number; y: number; zoom?: number; duration?: number }>): Promise<void> {
    const previousMode = this.currentMode;
    this.setMode(CameraMode.CINEMATIC);

    for (const pos of positions) {
      await new Promise<void>((resolve) => {
        const duration = pos.duration ?? 1000;

        if (pos.zoom !== undefined) {
          this.setZoom(pos.zoom);
        }

        this.scene.tweens.add({
          targets: this.camera,
          scrollX: pos.x - this.camera.width / 2,
          scrollY: pos.y - this.camera.height / 2,
          duration: duration,
          ease: Phaser.Math.Easing.Quadratic.InOut,
          onComplete: () => resolve()
        });
      });

      // Небольшая пауза между движениями
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    this.setMode(previousMode);
  }

  /**
   * Встряхивает камеру (эффект удара)
   */
  shake(intensity: number = 0.01, duration: number = 300): void {
    this.camera.shake(intensity, duration);
  }

  /**
   * Вспышка камеры (эффект удара/взрыва)
   */
  flash(color: number = 0xffffff, duration: number = 200): void {
    this.camera.flash(duration, color);
  }

  /**
   * Получает текущий зум
   */
  getZoom(): number {
    return this.camera.zoom;
  }

  /**
   * Получает текущую позицию центра камеры
   */
  getCenter(): { x: number; y: number } {
    return {
      x: this.camera.midPoint.x,
      y: this.camera.midPoint.y
    };
  }

  /**
   * Уничтожает контроллер
   */
  destroy(): void {
    this.stopFollowing();

    if (this.scene.input) {
      this.scene.input.off('wheel', this.handleMouseWheel.bind(this));
    }

    this.fighterSprites.clear();
  }
}

// ============================================================
// ЭКСПОРТ ТИПОВ
// ============================================================

export type { CameraConfig, CameraBounds };
