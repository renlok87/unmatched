// ============================================================
// COMBAT UI - Пользовательский интерфейс боевой системы
// ============================================================

import * as Phaser from 'phaser';

// ------------------------------------------------------------
// Типы записей в логе боя
// ------------------------------------------------------------

export enum CombatLogEntryType {
  ATTACK = 'attack',
  DEFEND = 'defend',
  DAMAGE = 'damage',
  HEAL = 'heal',
  EFFECT = 'effect',
  DEATH = 'death',
  SPECIAL = 'special',
  GAME_EVENT = 'game_event',
}

export interface CombatLogEntry {
  id: string;
  type: CombatLogEntryType;
  message: string;
  timestamp: number;
  playerId?: string;
  fighterId?: string;
  value?: number;
  icon?: string;
}

// ------------------------------------------------------------
// Конфигурация всплывающих чисел
// ------------------------------------------------------------

export interface FloatingNumberConfig {
  x: number;
  y: number;
  value: number;
  isHeal?: boolean;
  isCritical?: boolean;
  isBlock?: boolean;
  fontSize?: number;
  color?: number;
}

// ------------------------------------------------------------
// CombatUI - управление UI элементами боя
// ------------------------------------------------------------

export class CombatUI {
  private scene: Phaser.Scene;
  private damageNumbers: Phaser.GameObjects.Container;
  private combatLog: CombatLogPanel;
  private healthBars: Map<string, HealthBar> = new Map();
  private statusIcons: Map<string, Phaser.GameObjects.Container> = new Map();

  // Слой depth для UI элементов
  private static readonly UI_DEPTH = 1000;
  private static readonly DAMAGE_NUMBER_DEPTH = 1001;

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
    this.damageNumbers = scene.add.container(0, 0);
    this.damageNumbers.setDepth(CombatUI.DAMAGE_NUMBER_DEPTH);
    this.combatLog = new CombatLogPanel(scene);
  }

  // ------------------------------------------------------------
  // Damage Numbers - Всплывающие числа урона/лечения
  // ------------------------------------------------------------

  /**
   * Создаёт всплывающее число
   * @param config Конфигурация числа
   */
  public showFloatingNumber(config: FloatingNumberConfig): void {
    const number = this.createFloatingNumber(config);
    this.damageNumbers.add(number);

    // Анимация всплывания
    const targetY = config.y - 60;

    this.scene.tweens.add({
      targets: number,
      y: targetY,
      alpha: 0,
      duration: 800,
      ease: Phaser.Math.Easing.Quadratic.Out,
      onComplete: () => {
        this.damageNumbers.remove(number);
        number.destroy();
      },
    });
  }

  private createFloatingNumber(config: FloatingNumberConfig): Phaser.GameObjects.Container {
    const container = this.scene.add.container(config.x, config.y);

    let color = '#ff6666';
    let fontSize = config.fontSize || 32;
    let prefix = '';
    let suffix = '';
    let icon = '';

    // Определяем стиль по типу
    if (config.isHeal) {
      color = config.color ? `#${config.color.toString(16).padStart(6, '0')}` : '#4ecca3';
      prefix = '+';
      icon = '✚';
    } else if (config.isBlock) {
      color = '#88ccff';
      icon = '🛡️';
    } else if (config.isCritical) {
      color = '#ff0000';
      fontSize = Math.floor(fontSize * 1.3);
      suffix = '!';
    } else {
      color = '#ff6666';
    }

    // Основное число
    const text = this.scene.add.text(0, 0, `${prefix}${config.value}${suffix}`, {
      fontSize: `${fontSize}px`,
      color,
      fontStyle: config.isCritical ? 'bold' : 'normal',
      stroke: '#000000',
      strokeThickness: 4,
      shadow: {
        offsetX: 2,
        offsetY: 2,
        color: '#000000',
        blur: 4,
        stroke: true,
        fill: true,
      },
    });
    text.setOrigin(0.5);
    container.add(text);

    // Иконка если есть
    if (icon) {
      const iconText = this.scene.add.text(0, -fontSize, icon, {
        fontSize: `${Math.floor(fontSize * 0.8)}px`,
      });
      iconText.setOrigin(0.5);
      container.add(iconText);
    }

    // Для крита добавляем эффект пульсации
    if (config.isCritical) {
      this.scene.tweens.add({
        targets: container,
        scale: { from: 0.5, to: 1.5 },
        duration: 200,
        ease: Phaser.Math.Easing.Back.Out,
        yoyo: true,
      });
    }

    return container;
  }

  /**
   * Показывает множественные числа (для AOE атак)
   * @param positions Массив позиций и значений
   */
  public showMultipleFloatingNumbers(positions: Array<{
    x: number;
    y: number;
    value: number;
    isHeal?: boolean;
    isCritical?: boolean;
  }>): void {
    positions.forEach((pos, index) => {
      this.scene.time.delayedCall(index * 50, () => {
        this.showFloatingNumber(pos);
      });
    });
  }

  // ------------------------------------------------------------
  // Health Bars - Полоски здоровья
  // ------------------------------------------------------------

  /**
   * Создаёт полоску здоровья для бойца
   * @param fighterId ID бойца
   * @param x Позиция X
   * @param y Позиция Y
   * @param width Ширина полоски
   * @param maxHealth Максимальное здоровье
   */
  public createHealthBar(
    fighterId: string,
    x: number,
    y: number,
    width: number = 100,
    maxHealth: number = 10
  ): HealthBar {
    const healthBar = new HealthBar(this.scene, x, y, width, maxHealth);
    this.healthBars.set(fighterId, healthBar);
    return healthBar;
  }

  /**
   * Обновляет здоровье бойца
   * @param fighterId ID бойца
   * @param currentHealth Текущее здоровье
   * @param maxHealth Максимальное здоровье
   * @param animate Анимировать изменение
   */
  public updateHealth(
    fighterId: string,
    currentHealth: number,
    maxHealth: number,
    animate: boolean = true
  ): void {
    const healthBar = this.healthBars.get(fighterId);
    if (healthBar) {
      healthBar.update(currentHealth, maxHealth, animate);
    }
  }

  /**
   * Удаляет полоску здоровья
   * @param fighterId ID бойца
   */
  public removeHealthBar(fighterId: string): void {
    const healthBar = this.healthBars.get(fighterId);
    if (healthBar) {
      healthBar.destroy();
      this.healthBars.delete(fighterId);
    }
  }

  // ------------------------------------------------------------
  // Status Icons - Иконки статусных эффектов
  // ------------------------------------------------------------

  /**
   * Добавляет иконку статусного эффекта к бойцу
   * @param fighterId ID бойца
   * @param effectId ID эффекта
   * @param icon Иконка (emoji или текст)
   * @param duration Длительность в ходах (опционально)
   * @param x Позиция X относительно бойца
   * @param y Позиция Y относительно бойца
   */
  public addStatusIcon(
    fighterId: string,
    effectId: string,
    icon: string,
    duration?: number,
    x: number = 30,
    y: number = -30
  ): void {
    let container = this.statusIcons.get(fighterId);

    if (!container) {
      container = this.scene.add.container(x, y);
      container.setDepth(CombatUI.UI_DEPTH);
      this.statusIcons.set(fighterId, container);
    }

    const statusItem = this.createStatusIcon(icon, duration);
    const offsetX = (container.length % 4) * 20;
    const offsetY = Math.floor(container.length / 4) * 20;
    statusItem.setPosition(offsetX, offsetY);
    container.add(statusItem);
  }

  private createStatusIcon(icon: string, duration?: number): Phaser.GameObjects.Container {
    const container = this.scene.add.container(0, 0);

    // Фон иконки
    const bg = this.scene.add.circle(0, 0, 12, 0x333333, 0.8);
    container.add(bg);

    // Иконка/текст
    const iconText = this.scene.add.text(0, 0, icon, {
      fontSize: '16px',
    });
    iconText.setOrigin(0.5);
    container.add(iconText);

    // Текст длительности если есть
    if (duration !== undefined && duration > 0) {
      const durationText = this.scene.add.text(10, -10, duration.toString(), {
        fontSize: '10px',
        color: '#ffffff',
        fontStyle: 'bold',
        stroke: '#000000',
        strokeThickness: 2,
      });
      durationText.setOrigin(0.5);
      durationText.setName('duration');
      container.add(durationText);
    }

    return container;
  }

  /**
   * Обновляет длительность статусного эффекта
   * @param fighterId ID бойца
   * @param effectId ID эффекта
   * @param newDuration Новая длительность
   */
  public updateStatusDuration(
    fighterId: string,
    effectId: string,
    newDuration: number
  ): void {
    const container = this.statusIcons.get(fighterId);
    if (container) {
      container.each((child: Phaser.GameObjects.GameObject) => {
        if ('name' in child && child.name === 'duration') {
          const text = child as Phaser.GameObjects.Text;
          text.setText(newDuration.toString());
        }
      });
    }
  }

  /**
   * Удаляет иконку статусного эффекта
   * @param fighterId ID бойца
   * @param effectId ID эффекта
   */
  public removeStatusIcon(fighterId: string, effectId: string): void {
    const container = this.statusIcons.get(fighterId);
    if (container) {
      // Удаляем конкретную иконку (будет доработано с системой ID)
      container.removeAll();
    }
  }

  /**
   * Очищает все иконки статусных эффектов бойца
   * @param fighterId ID бойца
   */
  public clearStatusIcons(fighterId: string): void {
    const container = this.statusIcons.get(fighterId);
    if (container) {
      container.removeAll();
    }
  }

  // ------------------------------------------------------------
  // Combat Log - Лог боя
  // ------------------------------------------------------------

  /**
   * Добавляет запись в лог боя
   * @param entry Запись для добавления
   */
  public addLogEntry(entry: Omit<CombatLogEntry, 'id' | 'timestamp'>): void {
    this.combatLog.addEntry({
      ...entry,
      id: `log-${Date.now()}-${Math.random()}`,
      timestamp: Date.now(),
    });
  }

  /**
   * Добавляет запись об атаке
   */
  public logAttack(attackerName: string, targetName: string, damage: number): void {
    this.addLogEntry({
      type: CombatLogEntryType.ATTACK,
      message: `${attackerName} атакует ${targetName}`,
      value: damage,
    });
  }

  /**
   * Добавляет запись о защите
   */
  public logBlock(defenderName: string, blockedAmount: number): void {
    this.addLogEntry({
      type: CombatLogEntryType.DEFEND,
      message: `${defenderName} блокирует`,
      value: blockedAmount,
      icon: '🛡️',
    });
  }

  /**
   * Добавляет запись о лечении
   */
  public logHeal(targetName: string, healAmount: number): void {
    this.addLogEntry({
      type: CombatLogEntryType.HEAL,
      message: `${targetName} восстанавливает здоровье`,
      value: healAmount,
      icon: '✚',
    });
  }

  /**
   * Добавляет запись о смерти
   */
  public logDeath(fighterName: string): void {
    this.addLogEntry({
      type: CombatLogEntryType.DEATH,
      message: `${fighterName} повержен!`,
      icon: '💀',
    });
  }

  /**
   * Добавляет запись о специальном эффекте
   */
  public logEffect(message: string, icon?: string): void {
    this.addLogEntry({
      type: CombatLogEntryType.EFFECT,
      message,
      icon,
    });
  }

  /**
   * Показывает/скрывает панель лога
   */
  public toggleLog(show?: boolean): void {
    this.combatLog.setVisible(show ?? !this.combatLog.isVisible());
  }

  /**
   * Очищает лог
   */
  public clearLog(): void {
    this.combatLog.clear();
  }

  // ------------------------------------------------------------
  // Turn Indicator - Индикатор хода
  // ------------------------------------------------------------

  /**
   * Создаёт индикатор текущего хода
   * @param playerName Имя игрока
   */
  public showTurnIndicator(playerName: string): Phaser.GameObjects.Container {
    const width = this.scene.cameras.main.width;
    const height = this.scene.cameras.main.height;

    const container = this.scene.add.container(width / 2, height / 4);
    container.setDepth(CombatUI.UI_DEPTH + 100);

    // Фон
    const bg = this.scene.add.rectangle(0, 0, 300, 60, 0x1a1a2e, 0.9);
    bg.setStrokeStyle(3, 0x4ecca3);
    container.add(bg);

    // Текст
    const text = this.scene.add.text(0, 0, `Ход: ${playerName}`, {
      fontSize: '28px',
      color: '#ffffff',
      fontStyle: 'bold',
      stroke: '#000000',
      strokeThickness: 4,
    });
    text.setOrigin(0.5);
    container.add(text);

    // Анимация появления
    container.setScale(0);
    this.scene.tweens.add({
      targets: container,
      scale: 1,
      duration: 400,
      ease: Phaser.Math.Easing.Back.Out,
    });

    // Автоматическое исчезновение
    this.scene.time.delayedCall(2000, () => {
      this.scene.tweens.add({
        targets: container,
        alpha: 0,
        y: container.y - 50,
        duration: 500,
        ease: Phaser.Math.Easing.Quadratic.Out,
        onComplete: () => container.destroy(),
      });
    });

    return container;
  }

  // ------------------------------------------------------------
  // Action Prompts - Подсказки действий
  // ------------------------------------------------------------

  /**
   * Показывает подсказку действия
   * @param message Текст подсказки
   * @param duration Длительность показа (0 = бесконечно)
   */
  public showActionPrompt(message: string, duration: number = 0): Phaser.GameObjects.Container {
    const width = this.scene.cameras.main.width;
    const height = this.scene.cameras.main.height;

    const container = this.scene.add.container(width / 2, height - 100);
    container.setDepth(CombatUI.UI_DEPTH + 50);

    // Фон
    const bg = this.scene.add.rectangle(0, 0, 400, 50, 0x1a1a2e, 0.9);
    bg.setStrokeStyle(2, 0x4ecca3);
    container.add(bg);

    // Текст
    const text = this.scene.add.text(0, 0, message, {
      fontSize: '20px',
      color: '#ffffff',
      stroke: '#000000',
      strokeThickness: 3,
    });
    text.setOrigin(0.5);
    container.add(text);

    // Появление
    container.setAlpha(0);
    this.scene.tweens.add({
      targets: container,
      alpha: 1,
      duration: 200,
    });

    // Автоматическое скрытие если указана длительность
    if (duration > 0) {
      this.scene.time.delayedCall(duration, () => {
        this.hideActionPrompt(container);
      });
    }

    return container;
  }

  private hideActionPrompt(container: Phaser.GameObjects.Container): void {
    this.scene.tweens.add({
      targets: container,
      alpha: 0,
      duration: 200,
      onComplete: () => container.destroy(),
    });
  }

  // ------------------------------------------------------------
  // Очистка и уничтожение
  // ------------------------------------------------------------

  /**
   * Очищает все UI элементы
   */
  public clearAll(): void {
    // Очищаем числа урона
    this.damageNumbers.removeAll(true);

    // Очищаем полоски здоровья
    this.healthBars.forEach(bar => bar.destroy());
    this.healthBars.clear();

    // Очищаем иконки статусов
    this.statusIcons.forEach(container => container.destroy());
    this.statusIcons.clear();

    // Очищаем лог
    this.combatLog.clear();
  }

  /**
   * Уничтожает UI
   */
  public destroy(): void {
    this.clearAll();
    this.damageNumbers.destroy();
    this.combatLog.destroy();
  }
}

// ------------------------------------------------------------
// HealthBar - Полоска здоровья
// ------------------------------------------------------------

class HealthBar {
  private scene: Phaser.Scene;
  private background: Phaser.GameObjects.Rectangle;
  private fill: Phaser.GameObjects.Rectangle;
  private border: Phaser.GameObjects.Rectangle;
  private text: Phaser.GameObjects.Text;
  private container: Phaser.GameObjects.Container;
  private width: number;
  private maxHealth: number;
  private currentHealth: number;

  constructor(scene: Phaser.Scene, x: number, y: number, width: number, maxHealth: number) {
    this.scene = scene;
    this.width = width;
    this.maxHealth = maxHealth;
    this.currentHealth = maxHealth;

    this.container = scene.add.container(x, y);
    this.container.setDepth(CombatUI.UI_DEPTH);

    this.createComponents();
  }

  private createComponents(): void {
    const height = 12;

    // Рамка
    this.border = this.scene.add.rectangle(0, 0, this.width + 4, height + 4, 0x000000, 1);
    this.container.add(this.border);

    // Фон
    this.background = this.scene.add.rectangle(0, 0, this.width, height, 0x333333, 1);
    this.container.add(this.background);

    // Заполнение
    this.fill = this.scene.add.rectangle(
      -this.width / 2,
      0,
      this.width,
      height,
      0x4ecca3,
      1
    );
    this.fill.setOrigin(0, 0.5);
    this.container.add(this.fill);

    // Текст
    this.text = this.scene.add.text(0, -height - 8, `${this.currentHealth}/${this.maxHealth}`, {
      fontSize: '12px',
      color: '#ffffff',
      stroke: '#000000',
      strokeThickness: 3,
    });
    this.text.setOrigin(0.5);
    this.container.add(this.text);
  }

  public update(currentHealth: number, maxHealth: number, animate: boolean = true): void {
    const oldHealth = this.currentHealth;
    this.currentHealth = Math.max(0, Math.min(currentHealth, maxHealth));
    this.maxHealth = maxHealth;

    // Определяем цвет по проценту здоровья
    const healthPercent = this.currentHealth / this.maxHealth;
    let color = 0x4ecca3; // Зелёный
    if (healthPercent <= 0.3) {
      color = 0xff4444; // Красный
    } else if (healthPercent <= 0.6) {
      color = 0xffaa44; // Оранжевый
    }

    const newWidth = Math.max(0, this.width * healthPercent);

    if (animate) {
      // Анимация изменения
      this.scene.tweens.add({
        targets: this.fill,
        width: newWidth,
        duration: 300,
        ease: Phaser.Math.Easing.Quadratic.Out,
      });

      // Меняем цвет
      this.scene.tweens.add({
        targets: this.fill,
        fillStyle: { color },
        duration: 200,
      });
    } else {
      this.fill.width = newWidth;
      this.fill.setFillStyle(color);
    }

    // Обновляем текст
    this.text.setText(`${this.currentHealth}/${this.maxHealth}`);
  }

  public setVisible(visible: boolean): void {
    this.container.setVisible(visible);
  }

  public setPosition(x: number, y: number): void {
    this.container.setPosition(x, y);
  }

  public destroy(): void {
    this.container.destroy();
  }
}

// ------------------------------------------------------------
// CombatLogPanel - Панель лога боя
// ------------------------------------------------------------

class CombatLogPanel {
  private scene: Phaser.Scene;
  private container: Phaser.GameObjects.Container;
  private background: Phaser.GameObjects.Rectangle;
  private entries: Phaser.GameObjects.Text[] = [];
  private maxEntries: number = 8;
  private entryHeight: number = 24;

  // Позиция и размеры
  private x: number = 20;
  private y: number = 20;
  private width: number = 350;
  private height: number = 250;

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
    this.createPanel();
  }

  private createPanel(): void {
    this.container = this.scene.add.container(this.x, this.y);
    this.container.setDepth(CombatUI.UI_DEPTH + 10);

    // Фон
    this.background = this.scene.add.rectangle(
      0, 0,
      this.width,
      this.height,
      0x1a1a2e,
      0.85
    );
    this.background.setStrokeStyle(2, 0x4ecca3);
    this.container.add(this.background);

    // Заголовок
    const header = this.scene.add.text(
      -this.width / 2 + 10,
      -this.height / 2 + 10,
      'Бой',
      {
        fontSize: '16px',
        color: '#4ecca3',
        fontStyle: 'bold',
      }
    );
    header.setOrigin(0, 0.5);
    this.container.add(header);
  }

  public addEntry(entry: CombatLogEntry): void {
    // Форматируем текст записи
    let text = entry.message;
    if (entry.icon) {
      text = `${entry.icon} ${text}`;
    }
    if (entry.value !== undefined) {
      text += ` (${entry.value})`;
    }

    // Создаём текстовый объект
    const entryText = this.scene.add.text(0, 0, text, {
      fontSize: '14px',
      color: this.getEntryColor(entry.type),
      wordWrap: { width: this.width - 20 },
    });
    entryText.setOrigin(0, 0);

    // Добавляем в контейнер
    this.container.add(entryText);
    this.entries.push(entryText);

    // Перемещаем все записи
    this.updateEntryPositions();

    // Удаляем старые записи если превышен лимит
    if (this.entries.length > this.maxEntries) {
      const oldEntry = this.entries.shift();
      oldEntry?.destroy();
    }

    this.updateEntryPositions();
  }

  private getEntryColor(type: CombatLogEntryType): string {
    switch (type) {
      case CombatLogEntryType.ATTACK:
        return '#ff6666';
      case CombatLogEntryType.DEFEND:
        return '#88ccff';
      case CombatLogEntryType.HEAL:
        return '#4ecca3';
      case CombatLogEntryType.DEATH:
        return '#ff0000';
      case CombatLogEntryType.SPECIAL:
        return '#ffd700';
      case CombatLogEntryType.EFFECT:
        return '#aa88ff';
      default:
        return '#ffffff';
    }
  }

  private updateEntryPositions(): void {
    let y = -this.height / 2 + 40;

    // Идём снизу вверх (новейшие записи снизу)
    for (let i = this.entries.length - 1; i >= 0; i--) {
      const entry = this.entries[i];
      entry.setPosition(-this.width / 2 + 10, y);
      y += this.entryHeight;
    }
  }

  public clear(): void {
    this.entries.forEach(entry => entry.destroy());
    this.entries = [];
  }

  public setVisible(visible: boolean): void {
    this.container.setVisible(visible);
  }

  public isVisible(): boolean {
    return this.container.visible;
  }

  public destroy(): void {
    this.clear();
    this.container.destroy();
  }
}
