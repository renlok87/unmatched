// ============================================================
// SUBSCRIPTION HANDLER - WebSocket подписки на игровые события
// ============================================================

import { ApolloClient } from '@apollo/client';
import * as gql from '@/gql/graphql';
import type { GameScene } from '../scenes/GameScene';

// ------------------------------------------------------------
// Типы для подписок
// ------------------------------------------------------------

/**
 * Обновление игрового состояния от сервера
 */
export interface GameStateUpdate {
  gameId: string;
  sequenceNumber: number;
  phase: string;
  turnCount: number;
  currentTurnPlayerId: string;
  players?: string;
  fighters?: string;
  handZones?: string;
  boardState?: string;
  metadata?: {
    lastUpdatedAt: number;
  };
}

/**
 * Игровое событие
 */
export interface GameEvent {
  type: string;
  gameId: string;
  sequenceNumber: number;
  timestamp: Date;
  payload?: string;
}

/**
 * Обновление хода
 */
export interface TurnUpdate {
  playerId: string;
  turnCount: number;
  phase: string;
}

/**
 * Callbacks для обработки событий подписки
 */
export interface SubscriptionCallbacks {
  onStateUpdate?: (update: GameStateUpdate) => void;
  onGameEvent?: (event: GameEvent) => void;
  onTurnChanged?: (turn: TurnUpdate) => void;
  onPlayerJoined?: (event: GameEvent) => void;
  onPlayerLeft?: (event: GameEvent) => void;
  onAttackInitiated?: (event: GameEvent) => void;
  onDefensePlayed?: (event: GameEvent) => void;
  onCombatResolved?: (event: GameEvent) => void;
  onGameEnded?: (event: GameEvent) => void;
  onError?: (error: Error) => void;
  onConnecting?: () => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
  onReconnecting?: () => void;
}

// ------------------------------------------------------------
// SubscriptionHandler класс
// ------------------------------------------------------------

/**
 * SubscriptionHandler управляет WebSocket подписками на игровые события
 *
 * Функционал:
 * - Подписка на обновления gameState
 * - Подписка на игровые события (атака, защита, и т.д.)
 * - Автоматическое переподключение при разрыве
 * - Применение обновлений к Phaser сцене
 * - Обработка sequence numbers для обнаружения пропущенных событий
 */
export class SubscriptionHandler {
  private scene: GameScene;
  private gameId: string;
  private apolloClient: ApolloClient<object>;
  private callbacks: SubscriptionCallbacks;

  // Активные подписки
  private stateSubscription: ZenObservable.Subscription | null = null;
  private eventSubscriptions: Map<string, ZenObservable.Subscription> = new Map();

  // Состояние подключения
  private isSubscribed = false;
  private lastSequenceNumber = 0;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // мс
  private reconnectTimeout: NodeJS.Timeout | null = null;

  // Флаг для предотвращения множественных переподключений
  private isReconnecting = false;

  constructor(
    scene: GameScene,
    gameId: string,
    apolloClient: ApolloClient<object>,
    callbacks: SubscriptionCallbacks = {}
  ) {
    this.scene = scene;
    this.gameId = gameId;
    this.apolloClient = apolloClient;
    this.callbacks = callbacks;
  }

  /**
   * Подписаться на все игровые события
   *
   * Создаёт подписки на:
   * - gameStateUpdated (основное состояние)
   * - attackInitiated (атака)
   * - defensePlayed (защита)
   * - combatResolved (разрешение боя)
   * - turnChanged (смена хода)
   * - playerJoined (игрок присоединился)
   * - playerLeft (игрок вышел)
   * - gameEnded (конец игры)
   */
  subscribe(): void {
    if (this.isSubscribed) {
      console.warn('[SubscriptionHandler] Уже подписан на игру');
      return;
    }

    console.log('[SubscriptionHandler] Подписка на игровые события:', this.gameId);
    this.callbacks.onConnecting?.();

    // Подписываемся на обновление состояния
    this.subscribeToGameState();

    // Подписываемся на конкретные события
    this.subscribeToEvents();

    this.isSubscribed = true;
    this.callbacks.onConnected?.();
  }

  /**
   * Отписаться от всех событий
   */
  unsubscribe(): void {
    console.log('[SubscriptionHandler] Отписка от игровых событий');

    // Очищаем таймер переподключения
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    // Отписываемся от обновления состояния
    if (this.stateSubscription) {
      this.stateSubscription.unsubscribe();
      this.stateSubscription = null;
    }

    // Отписываемся от всех событий
    this.eventSubscriptions.forEach(sub => sub.unsubscribe());
    this.eventSubscriptions.clear();

    this.isSubscribed = false;
    this.isReconnecting = false;
    this.reconnectAttempts = 0;

    this.callbacks.onDisconnected?.();
  }

  /**
   * Подписка на обновление gameState
   */
  private subscribeToGameState(): void {
    const observable = this.apolloClient.subscribe<{
      gameStateUpdated: gql.GameState;
    }>({
      query: gql.GameStateUpdatedDocument,
      variables: {
        gameId: this.gameId,
        since: this.lastSequenceNumber,
      },
    });

    this.stateSubscription = observable.subscribe({
      next: ({ data, errors }) => {
        if (errors?.length) {
          this.handleSubscriptionError(new Error(errors[0].message));
          return;
        }

        if (data?.gameStateUpdated) {
          this.onStateUpdate(data.gameStateUpdated);
        }
      },
      error: (error) => {
        this.handleSubscriptionError(error);
      },
      complete: () => {
        console.warn('[SubscriptionHandler] GameState подписка закрыта');
        this.handleDisconnection();
      },
    });
  }

  /**
   * Подписка на игровые события
   */
  private subscribeToEvents(): void {
    // Атака инициирована
    this.createEventSubscription(
      'attackInitiated',
      gql.AttackInitiatedDocument,
      this.callbacks.onAttackInitiated
    );

    // Защита сыграна
    this.createEventSubscription(
      'defensePlayed',
      gql.DefensePlayedDocument,
      this.callbacks.onDefensePlayed
    );

    // Бой разрешён
    this.createEventSubscription(
      'combatResolved',
      gql.CombatResolvedDocument,
      this.callbacks.onCombatResolved
    );

    // Ход изменён
    const turnObservable = this.apolloClient.subscribe<{
      turnChanged: gql.TurnState;
    }>({
      query: gql.TurnChangedDocument,
      variables: { gameId: this.gameId },
    });

    const turnSub = turnObservable.subscribe({
      next: ({ data, errors }) => {
        if (errors?.length) {
          this.handleSubscriptionError(new Error(errors[0].message));
          return;
        }

        if (data?.turnChanged) {
          this.onTurnChanged(data.turnChanged);
        }
      },
      error: (error) => {
        this.handleSubscriptionError(error);
      },
    });
    this.eventSubscriptions.set('turnChanged', turnSub);

    // Игрок присоединился
    this.createEventSubscription(
      'playerJoined',
      gql.PlayerJoinedDocument,
      this.callbacks.onPlayerJoined
    );

    // Игрок вышел
    this.createEventSubscription(
      'playerLeft',
      gql.PlayerLeftDocument,
      this.callbacks.onPlayerLeft
    );

    // Игра завершена
    this.createEventSubscription(
      'gameEnded',
      gql.GameEndedDocument,
      this.callbacks.onGameEnded
    );
  }

  /**
   * Создаёт подписку на событие
   */
  private createEventSubscription(
    key: string,
    query: any,
    callback?: (event: GameEvent) => void
  ): void {
    const observable = this.apolloClient.subscribe({
      query,
      variables: { gameId: this.gameId },
    });

    const subscription = observable.subscribe({
      next: ({ data, errors }) => {
        if (errors?.length) {
          this.handleSubscriptionError(new Error(errors[0].message));
          return;
        }

        const eventData = data?.[key];
        if (eventData) {
          const event: GameEvent = {
            type: eventData.type || key,
            gameId: eventData.gameId,
            sequenceNumber: eventData.sequenceNumber,
            timestamp: new Date(eventData.timestamp),
            payload: eventData.payload ?? undefined,
          };

          this.onGameEvent(event);
          callback?.(event);
        }
      },
      error: (error) => {
        this.handleSubscriptionError(error);
      },
    });

    this.eventSubscriptions.set(key, subscription);
  }

  /**
   * Обработчик обновления состояния игры
   */
  private onStateUpdate(update: gql.GameState): void {
    console.log('[SubscriptionHandler] State update:', update.sequenceNumber);

    // Проверяем sequence number
    if (update.sequenceNumber <= this.lastSequenceNumber) {
      console.warn(
        `[SubscriptionHandler] Пропуск устаревшего обновления: ${update.sequenceNumber} <= ${this.lastSequenceNumber}`
      );
      return;
    }

    // Проверяем на gap (пропущенные события)
    const expectedSeq = this.lastSequenceNumber + 1;
    if (update.sequenceNumber > expectedSeq) {
      console.warn(
        `[SubscriptionHandler] Обнаружен gap: ожидали ${expectedSeq}, получили ${update.sequenceNumber}`
      );
      // TODO: Запросить пропущенные события через eventsSince
    }

    this.lastSequenceNumber = update.sequenceNumber;

    const stateUpdate: GameStateUpdate = {
      gameId: update.gameId,
      sequenceNumber: update.sequenceNumber,
      phase: update.phase,
      turnCount: update.turnCount,
      currentTurnPlayerId: update.currentTurnPlayerId,
      players: update.players ?? undefined,
      fighters: update.fighters ?? undefined,
      handZones: update.handZones ?? undefined,
      boardState: update.boardState ?? undefined,
      metadata: update.metadata ? { lastUpdatedAt: Date.now() } : undefined,
    };

    // Применяем обновление к сцене
    this.applyStateUpdate(stateUpdate);

    // Вызываем callback
    this.callbacks.onStateUpdate?.(stateUpdate);
  }

  /**
   * Обработчик игрового события
   */
  private onGameEvent(event: GameEvent): void {
    console.log('[SubscriptionHandler] Game event:', event.type);

    // Применяем событие к сцене
    this.applyGameEvent(event);

    // Вызываем callback
    this.callbacks.onGameEvent?.(event);
  }

  /**
   * Обработчик изменения хода
   */
  private onTurnChanged(turn: gql.TurnState): void {
    console.log('[SubscriptionHandler] Turn changed:', turn.playerId);

    const turnUpdate: TurnUpdate = {
      playerId: turn.playerId,
      turnCount: turn.turnCount,
      phase: turn.phase,
    };

    // Применяем к сцене
    if (this.scene && this.scene.events) {
      this.scene.events.emit('turnChanged', turnUpdate);
    }

    // Вызываем callback
    this.callbacks.onTurnChanged?.(turnUpdate);
  }

  /**
   * Применить обновление состояния к Phaser сцене
   */
  private applyStateUpdate(update: GameStateUpdate): void {
    if (!this.scene || !this.scene.events) {
      console.warn('[SubscriptionHandler] Сцена не доступна');
      return;
    }

    // Отправляем событие в сцену для обновления
    this.scene.events.emit('stateUpdate', update);

    // Обновляем фазы игры
    this.scene.events.emit('phaseChanged', update.phase);

    // Обновляем счётчик ходов
    this.scene.events.emit('turnCountChanged', update.turnCount);
  }

  /**
   * Применить игровое событие к Phaser сцене
   */
  private applyGameEvent(event: GameEvent): void {
    if (!this.scene || !this.scene.events) {
      console.warn('[SubscriptionHandler] Сцена не доступна');
      return;
    }

    // Отправляем событие в сцену
    this.scene.events.emit('gameEvent', event);

    // Специфичные обработчики для типов событий
    switch (event.type) {
      case 'FIGHTER_MOVED':
        this.scene.events.emit('fighterMoved', event);
        break;
      case 'ATTACK_INITIATED':
        this.scene.events.emit('attackInitiated', event);
        break;
      case 'DEFENSE_PLAYED':
        this.scene.events.emit('defensePlayed', event);
        break;
      case 'COMBAT_RESOLVED':
        this.scene.events.emit('combatResolved', event);
        break;
      case 'CARD_PLAYED':
        this.scene.events.emit('cardPlayed', event);
        break;
      case 'TURN_ENDED':
        this.scene.events.emit('turnEnded', event);
        break;
      case 'GAME_ENDED':
        this.scene.events.emit('gameEnded', event);
        break;
      case 'DOOR_TOGGLED':
        this.scene.events.emit('doorToggled', event);
        break;
    }
  }

  /**
   * Обработчик ошибки подписки
   */
  private handleSubscriptionError(error: Error): void {
    console.error('[SubscriptionHandler] Ошибка подписки:', error);

    this.callbacks.onError?.(error);

    // Пытаемся переподключиться
    this.handleDisconnection();
  }

  /**
   * Обработчик разрыва соединения
   */
  private handleDisconnection(): void {
    if (this.isReconnecting) {
      return;
    }

    this.isReconnecting = true;
    this.callbacks.onReconnecting?.();

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[SubscriptionHandler] Превышено максимальное количество попыток переподключения');
      this.callbacks.onError?.(new Error('Не удалось восстановить соединение'));
      return;
    }

    this.reconnectAttempts++;

    // Задержка перед переподключением с экспоненциальным ростом
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`[SubscriptionHandler] Переподключение через ${delay}мс (попытка ${this.reconnectAttempts})`);

    this.reconnectTimeout = setTimeout(() => {
      this.unsubscribe();
      this.subscribe();
      this.isReconnecting = false;
    }, delay);
  }

  /**
   * Получить последний sequence number
   */
  getLastSequenceNumber(): number {
    return this.lastSequenceNumber;
  }

  /**
   * Установить последний sequence number
   * (используется при начальной загрузке состояния)
   */
  setLastSequenceNumber(seq: number): void {
    this.lastSequenceNumber = seq;
  }

  /**
   * Проверить активность подписки
   */
  isActive(): boolean {
    return this.isSubscribed;
  }

  /**
   * Обновить callbacks
   */
  updateCallbacks(callbacks: Partial<SubscriptionCallbacks>): void {
    this.callbacks = { ...this.callbacks, ...callbacks };
  }
}

// ------------------------------------------------------------
// Типы для ZenObservable (возвращается Apollo subscribe)
// ------------------------------------------------------------

declare namespace ZenObservable {
  interface Observer<T> {
    next?(value: T): void;
    error?(error: any): void;
    complete?(): void;
  }

  interface Subscription {
    unsubscribe(): void;
  }

  interface Observable<T> {
    subscribe(observer: Observer<T>): Subscription;
    subscribe(
      onNext?: (value: T) => void,
      onError?: (error: any) => void,
      onComplete?: () => void
    ): Subscription;
  }
}
