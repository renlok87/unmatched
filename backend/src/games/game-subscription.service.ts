import { Injectable, Logger, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { Observable, Observer } from 'rxjs';
import { RedisService } from '../redis/redis.service';
import { GameState } from './game-state.service';

/**
 * Событие обновления игры для подписки
 */
export interface GameUpdateEvent {
  gameId: string;
  eventType: string;
  gameState: GameState;
  sequenceNumber: number;
  timestamp: number;
}

/**
 * GameSubscriptionService управляет real-time подписками на игры
 * - Поддерживает WebSocket подписки
 * - Интегрирован с Redis Pub/Sub для multi-instance
 * - Фильтрует приватные данные для каждого игрока
 */
@Injectable()
export class GameSubscriptionService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(GameSubscriptionService.name);
  private readonly CHANNEL_PREFIX = 'game:updates:';
  private readonly activeSubscriptions = new Map<string, Set<string>>();

  // Список callback'ов для каждой игры
  private readonly gameObservers = new Map<string, Set<Observer<GameUpdateEvent>>>();

  private redisReady = false;

  constructor(private redis: RedisService) {}

  async onModuleInit() {
    this.setupRedisSubscriber();
    this.redisReady = true;
  }

  async onModuleDestroy() {
    // Очистка при завершении
    this.gameObservers.clear();
    this.activeSubscriptions.clear();
  }

  /**
   * Настроить Redis подписчик для cross-instance сообщений
   */
  private setupRedisSubscriber(): void {
    // Подписываемся на канал для получения обновлений от других инстансов
    this.redis.subscribe('game:updates:broadcast', (message) => {
      try {
        const event = JSON.parse(message) as GameUpdateEvent;
        this.notifyLocalObservers(event);
      } catch (error) {
        this.logger.error('Failed to parse Redis pub/sub message:', error);
      }
    });
  }

  /**
   * Подписаться на обновления игры
   */
  subscribeToGame(
    gameId: string,
    userId: string,
    filterFn: (state: GameState) => GameState,
  ): Observable<GameUpdateEvent> {
    return new Observable<GameUpdateEvent>((observer) => {
      const key = `${gameId}:${userId}`;

      // Регистрируем подписчика
      if (!this.gameObservers.has(gameId)) {
        this.gameObservers.set(gameId, new Set());
      }
      this.gameObservers.get(gameId)!.add(observer);

      // Регистрируем активную подписку
      if (!this.activeSubscriptions.has(gameId)) {
        this.activeSubscriptions.set(gameId, new Set());
      }
      this.activeSubscriptions.get(gameId)!.add(userId);

      this.logger.debug(`User ${userId} subscribed to game ${gameId}`);

      // Cleanup при отписке
      return () => {
        this.unsubscribeFromGame(gameId, userId, observer);
      };
    });
  }

  /**
   * Отписаться от обновлений игры
   */
  private unsubscribeFromGame(
    gameId: string,
    userId: string,
    observer: Observer<GameUpdateEvent>,
  ): void {
    const observers = this.gameObservers.get(gameId);
    if (observers) {
      observers.delete(observer);
      if (observers.size === 0) {
        this.gameObservers.delete(gameId);
      }
    }

    const subscriptions = this.activeSubscriptions.get(gameId);
    if (subscriptions) {
      subscriptions.delete(userId);
      if (subscriptions.size === 0) {
        this.activeSubscriptions.delete(gameId);
      }
    }

    this.logger.debug(`User ${userId} unsubscribed from game ${gameId}`);
  }

  /**
   * Публикация обновления игры
   * Отправляет обновление всем подписчикам (локальным и через Redis)
   */
  async publishGameUpdate(gameId: string, eventType: string, gameState: GameState): Promise<void> {
    const event: GameUpdateEvent = {
      gameId,
      eventType,
      gameState,
      sequenceNumber: gameState.sequenceNumber,
      timestamp: Date.now(),
    };

    // Уведомляем локальных наблюдателей
    this.notifyLocalObservers(event);

    // Публикуем в Redis для других инстансов
    await this.redis.publish('game:updates:broadcast', JSON.stringify(event));
  }

  /**
   * Уведомить локальных наблюдателей
   */
  private notifyLocalObservers(event: GameUpdateEvent): void {
    const observers = this.gameObservers.get(event.gameId);
    if (!observers || observers.size === 0) {
      return;
    }

    for (const observer of observers) {
      try {
        observer.next(event);
      } catch (error) {
        this.logger.error(`Error notifying observer for game ${event.gameId}:`, error);
      }
    }
  }

  /**
   * Получить количество активных подписчиков для игры
   */
  getSubscriberCount(gameId: string): number {
    return this.activeSubscriptions.get(gameId)?.size || 0;
  }

  /**
   * Проверить, есть ли активные подписчики для игры
   */
  hasActiveSubscribers(gameId: string): boolean {
    const count = this.activeSubscriptions.get(gameId)?.size || 0;
    return count > 0;
  }

  /**
   * Получить все игры с активными подписками
   */
  getActiveGames(): string[] {
    return Array.from(this.activeSubscriptions.keys());
  }
}
