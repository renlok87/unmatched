// ============================================================
// UI SCENE - Сцена для координации с React UI
// ============================================================

import Phaser from 'phaser';

export class UIScene extends Phaser.Scene {
  // UI элементы
  private turnIndicator: Phaser.GameObjects.Text | null = null;
  private actionPointsText: Phaser.GameObjects.Text | null = null;
  private phaseIndicator: Phaser.GameObjects.Text | null = null;

  constructor() {
    super({ key: 'UIScene', active: false });
  }

  create(): void {
    console.log('UIScene: создана');

    // Создаём UI элементы
    this.createTurnIndicator();
    this.createActionPoints();
    this.createPhaseIndicator();

    // Подписываемся на события из GameScene
    const gameScene = this.scene.get('GameScene');
    if (gameScene) {
      gameScene.events.on('turn-changed', this.updateTurn, this);
      gameScene.events.on('phase-changed', this.updatePhase, this);
      gameScene.events.on('actions-changed', this.updateActions, this);
    }
  }

  /**
   * Создаёт индикатор хода
   */
  private createTurnIndicator(): void {
    this.turnIndicator = this.add.text(20, 20, 'Ход: Игрок 1', {
      fontSize: '20px',
      color: '#ffffff',
      backgroundColor: '#333333',
      padding: { x: 10, y: 5 },
    });
    this.turnIndicator.setScrollFactor(0);
    this.turnIndicator.setDepth(1000);
  }

  /**
   * Создаёт индикатор очков действий
   */
  private createActionPoints(): void {
    this.actionPointsText = this.add.text(20, 60, 'Действия: 2/2', {
      fontSize: '18px',
      color: '#4ecca3',
      backgroundColor: '#333333',
      padding: { x: 10, y: 5 },
    });
    this.actionPointsText.setScrollFactor(0);
    this.actionPointsText.setDepth(1000);
  }

  /**
   * Создаёт индикатор фазы
   */
  private createPhaseIndicator(): void {
    this.phaseIndicator = this.add.text(
      this.cameras.main.width - 20,
      20,
      'Фаза: Выбор действия',
      {
        fontSize: '18px',
        color: '#ffffff',
        backgroundColor: '#333333',
        padding: { x: 10, y: 5 },
      }
    );
    this.phaseIndicator.setOrigin(1, 0);
    this.phaseIndicator.setScrollFactor(0);
    this.phaseIndicator.setDepth(1000);
  }

  /**
   * Обновляет индикатор хода
   */
  private updateTurn(playerName: string): void {
    if (this.turnIndicator) {
      this.turnIndicator.setText(`Ход: ${playerName}`);
    }
  }

  /**
   * Обновляет индикатор фазы
   */
  private updatePhase(phase: string): void {
    if (this.phaseIndicator) {
      const phaseNames: Record<string, string> = {
        setup: 'Настройка',
        start_of_turn: 'Начало хода',
        action_selection: 'Выбор действия',
        card_play: 'Играть карту',
        movement: 'Движение',
        combat: 'Бой',
        combat_defense: 'Защита',
        resolution: 'Разрешение',
        end_of_turn: 'Конец хода',
        game_over: 'Игра окончена',
      };
      this.phaseIndicator.setText(`Фаза: ${phaseNames[phase] || phase}`);
    }
  }

  /**
   * Обновляет индикатор действий
   */
  private updateActions(current: number, max: number): void {
    if (this.actionPointsText) {
      this.actionPointsText.setText(`Действия: ${max - current}/${max}`);
    }
  }

  /**
   * Показывает уведомление
   */
  showNotification(message: string, duration: number = 2000): void {
    const notification = this.add.text(
      this.cameras.main.width / 2,
      100,
      message,
      {
        fontSize: '24px',
        color: '#ffffff',
        backgroundColor: 'rgba(0,0,0,0.8)',
        padding: { x: 20, y: 10 },
      }
    );
    notification.setOrigin(0.5);
    notification.setScrollFactor(0);
    notification.setDepth(1001);

    this.tweens.add({
      targets: notification,
      alpha: 0,
      y: 50,
      duration: duration,
      delay: 500,
      onComplete: () => {
        notification.destroy();
      },
    });
  }

  /**
   * Показывает модальное окно подтверждения
   */
  showConfirmDialog(message: string, onConfirm: () => void, onCancel: () => void): void {
    // TODO: Создать полноценное модальное окно
    console.log('UIScene: confirm dialog', message);
  }
}
