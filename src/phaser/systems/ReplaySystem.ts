// ============================================================
// REPLAY SYSTEM - Система записи и воспроизведения игр
// ============================================================

import type { GameScene } from '../scenes/GameScene';
import type { GameState } from '../../core/models/types';
import type { GameAction } from '../state/GameStateBridge';

// ------------------------------------------------------------
// Типы для системы replay
// ------------------------------------------------------------

/**
 * Записанное событие игры
 */
export interface ReplayEvent {
  readonly timestamp: number;           // Время события (мс от начала)
  readonly type: ReplayEventType;       // Тип события
  readonly sequenceNumber: number;       // Порядковый номер
  readonly data: unknown;                // Данные события
}

/**
 * Типы событий для записи
 */
export enum ReplayEventType {
  // Состояние
  STATE_SNAPSHOT = 'state_snapshot',
  STATE_DIFF = 'state_diff',

  // Действия игрока
  MANEUVER = 'maneuver',
  ATTACK = 'attack',
  PLAY_DEFENSE = 'play_defense',
  RESOLVE_COMBAT = 'resolve_combat',
  END_TURN = 'end_turn',
  PASS = 'pass',
  TOGGLE_DOOR = 'toggle_door',

  // Игровые события
  FIGHTER_MOVED = 'fighter_moved',
  DAMAGE_DEALT = 'damage_dealt',
  FIGHTER_DEFEATED = 'fighter_defeated',
  CARD_PLAYED = 'card_played',
  CARD_DISCARDED = 'card_discarded',

  // Фазы игры
  PHASE_CHANGED = 'phase_changed',
  TURN_CHANGED = 'turn_changed',

  // Системные события
  GAME_STARTED = 'game_started',
  GAME_ENDED = 'game_ended',
}

/**
 * Запись игры (полный replay)
 */
export interface GameReplay {
  readonly id: string;
  readonly gameId: string;
  readonly startTime: number;
  readonly endTime?: number;
  readonly duration?: number;          // Длительность в мс
  readonly players: ReplayPlayerInfo[];
  readonly winnerId?: string;
  readonly events: ReplayEvent[];
  readonly metadata?: ReplayMetadata;
}

/**
 * Информация об игроке в replay
 */
export interface ReplayPlayerInfo {
  readonly userId: string;
  readonly userName?: string;
  readonly heroId: string;
  readonly heroName?: string;
}

/**
 * Метаданные replay
 */
export interface ReplayMetadata {
  readonly boardId?: string;
  readonly gameMode?: string;
  readonly turnCount?: number;
  readonly totalActions?: number;
  readonly version?: string;           // Версия движка для совместимости
}

/**
 * Состояние воспроизведения
 */
export interface ReplayState {
  readonly isPlaying: boolean;
  readonly isPaused: boolean;
  readonly isReversed: boolean;        // Воспроизведение назад
  readonly currentTime: number;        // Текущее время в мс
  readonly playbackSpeed: number;      // Скорость воспроизведения (1x, 2x, etc)
  readonly currentEventIndex: number;
  readonly direction: 'forward' | 'backward'; // Направление воспроизведения
  readonly duration: number;           // Общая длительность
  readonly progress: number;           // Прогресс 0-1
}

/**
 * Конфигурация ReplaySystem
 */
export interface ReplayConfig {
  readonly autoRecord?: boolean;       // Автоматически записывать события
  readonly maxEvents?: number;         // Максимум событий перед началом оптимизации
  readonly compressionEnabled?: boolean; // Сжимать события
  readonly onReplayEvent?: (event: ReplayEvent) => void;
}

// ------------------------------------------------------------
// ReplaySystem - основная система
// ------------------------------------------------------------

export class ReplaySystem {
  private scene: GameScene;
  private config: Required<ReplayConfig>;

  // Запись
  private isRecording: boolean = false;
  private recordingStartTime: number = 0;
  private currentReplay: Partial<GameReplay> | null = null;
  private eventBuffer: ReplayEvent[] = [];
  private lastSequenceNumber: number = 0;

  // Воспроизведение
  private isPlaying: boolean = false;
  private isPaused: boolean = false;
  private isReversed: boolean = false;    // Флаг обратного воспроизведения
  private playbackReplay: GameReplay | null = null;
  private playbackTimer: Phaser.Time.TimerEvent | null = null;
  private playbackSpeed: number = 1;
  private currentEventIndex: number = 0;
  private playbackStartTime: number = 0;
  private currentTime: number = 0;        // Текущее время воспроизведения
  private direction: 'forward' | 'backward' = 'forward';

  // Снимки состояния (для быстрого перемотки)
  private stateSnapshots: Map<number, GameState> = new Map();
  private snapshotInterval: number = 5000; // Каждые 5 секунд

  // Слушатели
  private listeners: {
    onRecordingStarted?: () => void;
    onRecordingStopped?: (replay: GameReplay) => void;
    onPlaybackStarted?: (replay: GameReplay) => void;
    onPlaybackStopped?: () => void;
    onPlaybackEnded?: () => void;
    onEventPlayed?: (event: ReplayEvent) => void;
  } = {};

  constructor(scene: GameScene, config: ReplayConfig = {}) {
    this.scene = scene;

    this.config = {
      autoRecord: config.autoRecord ?? true,
      maxEvents: config.maxEvents ?? 1000,
      compressionEnabled: config.compressionEnabled ?? true,
      onReplayEvent: config.onReplayEvent ?? (() => {}),
    };
  }

  // ------------------------------------------------------------
  // Запись игры
  // ------------------------------------------------------------

  /**
   * Начать запись игры
   */
  startRecording(players: ReplayPlayerInfo[], gameId: string, metadata?: Partial<ReplayMetadata>): void {
    this.isRecording = true;
    this.recordingStartTime = Date.now();
    this.eventBuffer = [];
    this.lastSequenceNumber = 0;
    this.stateSnapshots.clear();

    this.currentReplay = {
      id: this.generateReplayId(),
      gameId,
      startTime: this.recordingStartTime,
      players,
      events: [],
      metadata: {
        ...metadata,
        version: '1.0.0',
      },
    };

    // Записываем событие начала игры
    this.recordEvent({
      timestamp: 0,
      type: ReplayEventType.GAME_STARTED,
      sequenceNumber: 0,
      data: {
        players,
        gameId,
      },
    });

    // Создаём периодический снимок состояния
    this.scheduleSnapshot();

    this.listeners.onRecordingStarted?.();

    console.log('[ReplaySystem] Запись начата:', this.currentReplay.id);
  }

  /**
   * Остановить запись
   */
  stopRecording(winnerId?: string): GameReplay | null {
    if (!this.isRecording || !this.currentReplay) {
      return null;
    }

    const endTime = Date.now();
    const duration = endTime - this.recordingStartTime;

    // Записываем событие конца игры
    this.recordEvent({
      timestamp: duration,
      type: ReplayEventType.GAME_ENDED,
      sequenceNumber: this.lastSequenceNumber++,
      data: { winnerId },
    });

    // Финализируем replay
    const replay: GameReplay = {
      ...this.currentReplay,
      endTime,
      duration,
      winnerId,
      events: [...this.eventBuffer],
    } as GameReplay;

    this.isRecording = false;
    this.currentReplay = null;

    // Сжимаем события если включено
    const finalReplay = this.config.compressionEnabled
      ? this.compressEvents(replay)
      : replay;

    this.listeners.onRecordingStopped?.(finalReplay);

    console.log('[ReplaySystem] Запись остановлена. Всего событий:', finalReplay.events.length);

    return finalReplay;
  }

  /**
   * Записать игровое действие
   */
  recordAction(action: GameAction, sequenceNumber: number): void {
    if (!this.isRecording) return;

    const timestamp = Date.now() - this.recordingStartTime;

    let eventType: ReplayEventType;
    switch (action.type) {
      case 'MANEUVER':
        eventType = ReplayEventType.MANEUVER;
        break;
      case 'ATTACK':
        eventType = ReplayEventType.ATTACK;
        break;
      case 'PLAY_DEFENSE':
        eventType = ReplayEventType.PLAY_DEFENSE;
        break;
      case 'RESOLVE_COMBAT':
        eventType = ReplayEventType.RESOLVE_COMBAT;
        break;
      case 'END_TURN':
        eventType = ReplayEventType.END_TURN;
        break;
      case 'PASS':
        eventType = ReplayEventType.PASS;
        break;
      case 'TOGGLE_DOOR':
        eventType = ReplayEventType.TOGGLE_DOOR;
        break;
      default:
        return;
    }

    this.recordEvent({
      timestamp,
      type: eventType,
      sequenceNumber,
      data: action.params,
    });
  }

  /**
   * Записать изменение состояния
   */
  recordStateChange(state: GameState, diff?: unknown): void {
    if (!this.isRecording) return;

    const timestamp = Date.now() - this.recordingStartTime;

    // Создаём снимок состояния периодически
    if (timestamp % this.snapshotInterval < 100) {
      this.stateSnapshots.set(timestamp, { ...state });
    }

    // Записываем дифф
    this.recordEvent({
      timestamp,
      type: diff ? ReplayEventType.STATE_DIFF : ReplayEventType.STATE_SNAPSHOT,
      sequenceNumber: this.lastSequenceNumber++,
      data: diff || state,
    });
  }

  /**
   * Записать произвольное событие
   */
  recordEvent(event: Omit<ReplayEvent, 'sequenceNumber'> & { sequenceNumber?: number }): void {
    if (!this.isRecording) return;

    const replayEvent: ReplayEvent = {
      ...event,
      sequenceNumber: event.sequenceNumber ?? this.lastSequenceNumber++,
    };

    this.eventBuffer.push(replayEvent);
    this.config.onReplayEvent(replayEvent);
  }

  // ------------------------------------------------------------
  // Воспроизведение игры
  // ------------------------------------------------------------

  /**
   * Загрузить replay для воспроизведения
   */
  loadReplay(replay: GameReplay): void {
    this.playbackReplay = replay;
    this.currentEventIndex = 0;
    this.playbackSpeed = 1;
    this.isPaused = false;
    this.isReversed = false;
    this.currentTime = 0;
    this.direction = 'forward';

    // Восстанавливаем снимки состояния из метаданных
    this.stateSnapshots.clear();
    // Загружаем сохранённые снимки если они есть в replay

    console.log('[ReplaySystem] Replay загружен:', replay.id, 'длительность:', replay.duration, 'мс');
  }

  /**
   * Начать воспроизведение
   */
  play(): void {
    if (!this.playbackReplay || this.isPlaying) {
      return;
    }

    this.isPlaying = true;
    this.isPaused = false;
    this.playbackStartTime = Date.now();

    this.listeners.onPlaybackStarted?.(this.playbackReplay);

    // Запускаем таймер воспроизведения
    this.scheduleNextEvent();

    console.log('[ReplaySystem] Воспроизведение начато');
  }

  /**
   * Пауза воспроизведения
   */
  pause(): void {
    if (!this.isPlaying) return;

    this.isPaused = true;

    if (this.playbackTimer) {
      this.playbackTimer.destroy();
      this.playbackTimer = null;
    }

    console.log('[ReplaySystem] Воспроизведение на паузе');
  }

  /**
   * Продолжить воспроизведение
   */
  resume(): void {
    if (!this.isPlaying || !this.isPaused) return;

    this.isPaused = false;
    this.scheduleNextEvent();

    console.log('[ReplaySystem] Воспроизведение продолжено');
  }

  /**
   * Остановить воспроизведение
   */
  stop(): void {
    if (!this.isPlaying) return;

    this.isPlaying = false;
    this.isPaused = false;
    this.isReversed = false;
    this.currentEventIndex = 0;
    this.currentTime = 0;
    this.direction = 'forward';

    if (this.playbackTimer) {
      this.playbackTimer.destroy();
      this.playbackTimer = null;
    }

    this.listeners.onPlaybackStopped?.();

    console.log('[ReplaySystem] Воспроизведение остановлено');
  }

  /**
   * Воспроизвести в обратном направлении
   */
  reverse(): void {
    if (!this.isPlaying) {
      // Если не воспроизводится, начинаем с обратным направлением
      this.play();
    }

    this.isReversed = true;
    this.direction = 'backward';

    // Перезапускаем планировщик с обратным направлением
    if (this.playbackTimer) {
      this.playbackTimer.destroy();
      this.playbackTimer = null;
    }

    this.scheduleNextEvent();

    console.log('[ReplaySystem] Обратное воспроизведение');
  }

  /**
   * Перемотать к определённому времени
   */
  seekTo(time: number): void {
    if (!this.playbackReplay) return;

    // Ограничиваем время
    const duration = this.playbackReplay.duration ?? 0;
    time = Math.max(0, Math.min(time, duration));
    this.currentTime = time;

    // Находим ближайший снимок состояния перед запрошенным временем
    const snapshotTimes = Array.from(this.stateSnapshots.keys())
      .filter(t => t <= time)
      .sort((a, b) => b - a);

    if (snapshotTimes.length > 0) {
      const snapshotState = this.stateSnapshots.get(snapshotTimes[0]);
      if (snapshotState) {
        // Применяем снимок к сцене
        this.applyState(snapshotState);
      }
    }

    // Находим индекс события ближайшего к запрошенному времени
    this.currentEventIndex = this.playbackReplay.events.findIndex(
      e => e.timestamp >= time
    );

    if (this.currentEventIndex < 0) {
      this.currentEventIndex = this.playbackReplay.events.length;
    }

    // Применяем все события до указанного времени
    this.applyEventsUntilTime(time);

    console.log('[ReplaySystem] Перемотка к времени:', time, 'progress:', (time / duration * 100).toFixed(1) + '%');
  }

  /**
   * Перемотать к определённому прогрессу (0-1)
   */
  seekToProgress(progress: number): void {
    if (!this.playbackReplay) return;

    const duration = this.playbackReplay.duration ?? 1;
    const time = Math.max(0, Math.min(1, progress)) * duration;

    this.seekTo(time);
  }

  /**
   * Перемотать к следующему/предыдущему ключевому событию
   */
  stepToEvent(eventType?: ReplayEventType): void {
    if (!this.playbackReplay) return;

    if (this.direction === 'forward' || !this.isReversed) {
      // Ищем следующее событие
      const searchFrom = this.currentEventIndex;
      const nextIndex = eventType
        ? this.playbackReplay.events.findIndex((e, i) => i > searchFrom && e.type === eventType)
        : this.currentEventIndex + 1;

      if (nextIndex >= 0 && nextIndex < this.playbackReplay.events.length) {
        const event = this.playbackReplay.events[nextIndex];
        this.seekTo(event.timestamp);
        this.currentEventIndex = nextIndex;
      }
    } else {
      // Ищем предыдущее событие
      const searchFrom = this.currentEventIndex;
      const prevIndex = eventType
        ? this.playbackReplay.events.findLastIndex((e, i) => i < searchFrom && e.type === eventType)
        : this.currentEventIndex - 1;

      if (prevIndex >= 0) {
        const event = this.playbackReplay.events[prevIndex];
        this.seekTo(event.timestamp);
        this.currentEventIndex = prevIndex;
      }
    }
  }

  /**
   * Перемотать к следующему/предыдущему событию
   */
  step(direction: 'next' | 'previous' = 'next'): void {
    if (!this.playbackReplay) return;

    if (direction === 'next') {
      if (this.currentEventIndex < this.playbackReplay.events.length) {
        const event = this.playbackReplay.events[this.currentEventIndex];
        this.playEvent(event);
        this.currentEventIndex++;
      }
    } else {
      if (this.currentEventIndex > 0) {
        this.currentEventIndex--;
        // Для перемотки назад нужно перезагрузить состояние
        // Это упрощённая реализация
        this.seekTo(this.playbackReplay.events[this.currentEventIndex].timestamp);
      }
    }
  }

  /**
   * Установить скорость воспроизведения
   */
  setPlaybackSpeed(speed: number): void {
    this.playbackSpeed = Math.max(0.25, Math.min(4, speed));
    console.log('[ReplaySystem] Скорость воспроизведения:', this.playbackSpeed);
  }

  /**
   * Получить текущее состояние воспроизведения
   */
  getPlaybackState(): ReplayState {
    const duration = this.playbackReplay?.duration ?? 0;
    const currentTime = this.getCurrentTime();

    return {
      isPlaying: this.isPlaying,
      isPaused: this.isPaused,
      isReversed: this.isReversed,
      currentTime,
      playbackSpeed: this.playbackSpeed,
      currentEventIndex: this.currentEventIndex,
      direction: this.direction,
      duration,
      progress: duration > 0 ? currentTime / duration : 0,
    };
  }

  // ------------------------------------------------------------
  // Слушатели
  // ------------------------------------------------------------

  setListeners(listeners: Partial<typeof ReplaySystem.prototype.listeners>): void {
    this.listeners = { ...this.listeners, ...listeners };
  }

  // ------------------------------------------------------------
  // Приватные методы
  // ------------------------------------------------------------

  /**
   * Запланировать следующее событие
   */
  private scheduleNextEvent(): void {
    if (!this.playbackReplay || !this.isPlaying || this.isPaused) return;

    if (this.isReversed && this.direction === 'backward') {
      // Обратное воспроизведение
      if (this.currentEventIndex <= 0) {
        this.endPlayback();
        return;
      }

      const event = this.playbackReplay.events[this.currentEventIndex - 1];
      const prevEvent = this.playbackReplay.events[this.currentEventIndex - 2];
      const delayToPrev = prevEvent ? event.timestamp - prevEvent.timestamp : event.timestamp;

      // Для обратного воспроизведения откатываем состояние
      this.revertEvent(event);
      this.currentEventIndex--;

      this.currentTime = event.timestamp;

      // Планируем следующее событие с учётом скорости
      const adjustedDelay = delayToPrev / this.playbackSpeed;

      this.playbackTimer = this.scene.time.delayedCall(adjustedDelay, () => {
        this.scheduleNextEvent();
      });
    } else {
      // Прямое воспроизведение
      if (this.currentEventIndex >= this.playbackReplay.events.length) {
        this.endPlayback();
        return;
      }

      const event = this.playbackReplay.events[this.currentEventIndex];
      const nextEvent = this.playbackReplay.events[this.currentEventIndex + 1];
      const delayToNext = nextEvent ? nextEvent.timestamp - event.timestamp : 0;

      // Применяем событие
      this.playEvent(event);

      this.currentTime = event.timestamp;

      // Планируем следующее событие с учётом скорости воспроизведения
      const adjustedDelay = delayToNext / this.playbackSpeed;

      this.playbackTimer = this.scene.time.delayedCall(adjustedDelay, () => {
        this.currentEventIndex++;
        this.scheduleNextEvent();
      });
    }
  }

  /**
   * Воспроизвести событие
   */
  private playEvent(event: ReplayEvent): void {
    console.log('[ReplaySystem] Воспроизведение события:', event.type, event.timestamp);

    // Применяем событие к сцене
    this.scene.events.emit('replay:event', event);

    this.listeners.onEventPlayed?.(event);
  }

  /**
   * Откатить событие (для обратного воспроизведения)
   */
  private revertEvent(event: ReplayEvent): void {
    console.log('[ReplaySystem] Откат события:', event.type, event.timestamp);

    // Отправляем событие отката в сцену
    this.scene.events.emit('replay:revert', event);
  }

  /**
   * Применить события до указанного времени
   */
  private applyEventsUntilTime(time: number): void {
    if (!this.playbackReplay) return;

    // Применяем все события до указанного времени
    for (let i = 0; i < this.playbackReplay.events.length; i++) {
      const event = this.playbackReplay.events[i];
      if (event.timestamp <= time) {
        this.playEvent(event);
        this.currentEventIndex = i + 1;
      } else {
        break;
      }
    }
  }

  /**
   * Применить состояние к сцене
   */
  private applyState(state: GameState): void {
    this.scene.events.emit('replay:state', state);
  }

  /**
   * Завершить воспроизведение
   */
  private endPlayback(): void {
    this.isPlaying = false;
    this.isPaused = false;

    if (this.playbackTimer) {
      this.playbackTimer.destroy();
      this.playbackTimer = null;
    }

    this.listeners.onPlaybackEnded?.();

    console.log('[ReplaySystem] Воспроизведение завершено');
  }

  /**
   * Получить текущее время воспроизведения
   */
  private getCurrentTime(): number {
    if (!this.playbackReplay || this.currentEventIndex === 0) {
      return 0;
    }

    return this.playbackReplay.events[this.currentEventIndex - 1]?.timestamp ?? 0;
  }

  /**
   * Запланировать создание снимка состояния
   */
  private scheduleSnapshot(): void {
    if (!this.isRecording) return;

    this.scene.time.addEvent({
      delay: this.snapshotInterval,
      callback: () => {
        if (this.isRecording) {
          // Снимок создаётся через recordStateChange
          this.scheduleSnapshot();
        }
      },
      loop: true,
    });
  }

  /**
   * Сжать события (удалить промежуточные состояния)
   */
  private compressEvents(replay: GameReplay): GameReplay {
    // В упрощённой версии просто оставляем ключевые события
    const criticalEvents = new Set([
      ReplayEventType.GAME_STARTED,
      ReplayEventType.GAME_ENDED,
      ReplayEventType.MANEUVER,
      ReplayEventType.ATTACK,
      ReplayEventType.PLAY_DEFENSE,
      ReplayEventType.RESOLVE_COMBAT,
      ReplayEventType.END_TURN,
      ReplayEventType.FIGHTER_DEFEATED,
    ]);

    const filteredEvents = replay.events.filter(e =>
      criticalEvents.has(e.type)
    );

    return {
      ...replay,
      events: filteredEvents,
    };
  }

  /**
   * Сгенерировать ID для replay
   */
  private generateReplayId(): string {
    return `replay_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // ------------------------------------------------------------
  // Экспорт/импорт
  // ------------------------------------------------------------

  /**
   * Экспортировать replay в JSON
   */
  exportToJSON(replay: GameReplay): string {
    return JSON.stringify(replay);
  }

  /**
   * Импортировать replay из JSON
   */
  importFromJSON(json: string): GameReplay | null {
    try {
      return JSON.parse(json) as GameReplay;
    } catch (e) {
      console.error('[ReplaySystem] Ошибка импорта replay:', e);
      return null;
    }
  }

  /**
   * Уничтожить систему
   */
  destroy(): void {
    this.stop();
    this.stopRecording();
    this.stateSnapshots.clear();
  }
}

// ------------------------------------------------------------
// Фабричная функция
// ------------------------------------------------------------

export function createReplaySystem(scene: GameScene, config?: ReplayConfig): ReplaySystem {
  return new ReplaySystem(scene, config);
}

// ------------------------------------------------------------
// Экспорт типов
// ------------------------------------------------------------

export type {
  ReplayEvent,
  GameReplay,
  ReplayPlayerInfo,
  ReplayMetadata,
  ReplayState,
  ReplayConfig,
};
