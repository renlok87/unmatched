/**
 * Game Subscription Resolver (Enhanced)
 *
 * GraphQL подписки для real-time обновлений игры.
 * Поддерживает:
 * - since параметр для реконнекта
 * - Специфичные события (attackInitiated, defensePlayed, combatResolved)
 * - Фильтрация приватных данных для каждого подписчика
 *
 * ВАЖНО: из @Subscription нужно возвращать AsyncIterator (PubSub.asyncIterableIterator),
 * НЕ rxjs Observable — Nest заворачивает Observable в lastValueFrom и подписка
 * виснет навсегда, не доставляя ни одного события.
 */

import { Resolver, Args, Subscription, Context } from '@nestjs/graphql';
import { ForbiddenException, Logger, NotFoundException, UseGuards } from '@nestjs/common';
import { GqlAuthGuard } from '../../auth/guards/gql-auth.guard';
import { GameSubscriptionService, GamePubSubEvent } from '../game-subscription.service';
import { GameStateService, GameState } from '../game-state.service';
import {
  GameEvent,
  TurnState,
  GameEventType,
  GameState as GameStateGQL,
} from '../dto/gameplay.dto';
import { GamePhase } from '../dto';

/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-argument */
/* eslint-disable @typescript-eslint/no-unsafe-assignment */

/**
 * Состояние игры для публикации в подписках
 * (форма события, которую publishGameUpdate кладёт в PubSub — GamePubSubEvent)
 */
interface GameEventPayload {
  gameId: string;
  sequenceNumber: number;
  timestamp: number;
  eventType: GameEventType | string;
  payload: any;
}

/** Структурный вид GQL-контекста для извлечения userId из JWT. */
interface SubscriptionAuthContext {
  req?: { user?: { id?: string } };
  user?: { id?: string };
}

const resolveGameStateFn =
  (gameStateService: GameStateService, getUserIdFn: (context: any) => string) =>
  (value: GameEventPayload | null, args: any, context: any): GameStateGQL | null => {
    if (!value) return null;

    // Фильтрация по userId из JWT-контекста (НЕ из спуфаемого Args userId)
    const userId = getUserIdFn(context);
    const filteredState = gameStateService.filterPrivateData(value.payload, userId);

    return {
      gameId: value.gameId,
      sequenceNumber: value.sequenceNumber,
      phase: filteredState.phase,
      turnCount: filteredState.turnCount,
      currentTurnPlayerId: filteredState.currentTurnPlayerId,
      players: JSON.stringify(filteredState.players),
      fighters: JSON.stringify(filteredState.fighters),
      handZones: JSON.stringify(filteredState.handZones),
      // S05: discardPiles несут reveal-личины committed-карт боя (правила
      // p.12-13: обе карты открыты после reveal, включая паузы BOOST_CHOICE)
      discardPiles: JSON.stringify(filteredState.discardPiles ?? {}),
      boardState: JSON.stringify(filteredState.boardState),
      metadata: JSON.stringify(filteredState.metadata),
    };
  };

const resolveGameEventFn =
  () =>
  (value: GameEventPayload | null): GameEvent => {
    if (!value) {
      return {
        type: GameEventType.FIGHTER_MOVED,
        gameId: '',
        sequenceNumber: 0,
        timestamp: new Date(),
        payload: null,
      };
    }

    // В payload — только безопасное подмножество состояния (без рук игроков!).
    // Полное состояние клиент получает через gameStateUpdated с per-user фильтрацией.
    // Лобби-события (PLAYER_JOINED/PLAYER_LEFT) несут компактный объект без phase —
    // его отдаём как есть (userId/username, приватных данных там нет).
    const state = value.payload as GameState | null;
    const safePayload = state
      ? state.phase != null
        ? JSON.stringify({
            phase: state.phase,
            turnCount: state.turnCount,
            currentTurnPlayerId: state.currentTurnPlayerId,
          })
        : JSON.stringify(state)
      : null;

    return {
      type: value.eventType as GameEventType,
      gameId: value.gameId,
      sequenceNumber: value.sequenceNumber,
      timestamp: new Date(value.timestamp),
      payload: safePayload,
    };
  };

const resolveTurnStateFn =
  () =>
  (value: GameEventPayload | null): TurnState => {
    if (!value) {
      return {
        playerId: '',
        turnCount: 0,
        phase: GamePhase.SETUP,
      };
    }

    const state = value.payload as GameState;

    return {
      playerId: state.currentTurnPlayerId || '',
      turnCount: state.turnCount,
      phase: state.phase,
    };
  };

@Resolver(() => GameStateGQL)
export class GameSubscriptionResolver {
  private readonly logger = new Logger(GameSubscriptionResolver.name);

  private resolveGameState!: (
    value: GameEventPayload | null,
    args: any,
    context: any,
  ) => GameStateGQL | null;
  private resolveGameEvent!: (value: GameEventPayload | null) => GameEvent;
  private resolveTurnState!: (value: GameEventPayload | null) => TurnState;

  constructor(
    private readonly subscriptionService: GameSubscriptionService,
    private readonly gameStateService: GameStateService,
  ) {
    this.resolveGameState = resolveGameStateFn(this.gameStateService, (context) =>
      this.getUserId(context),
    );

    this.resolveGameEvent = resolveGameEventFn();

    this.resolveTurnState = resolveTurnStateFn();
  }

  /**
   * GD-025/ACC-009: гейт участия — неучастник (spectator) не получает
   * НИКАКОГО игрового состояния, включая события.
   */
  private async requireParticipant(gameId: string, context: any): Promise<string> {
    const userId = this.getUserId(context);
    if (!(await this.gameStateService.isParticipant(gameId, userId))) {
      throw new ForbiddenException('Not a game participant');
    }
    return userId;
  }

  /**
   * S08: повторная авторизация В МОМЕНТ доставки. requireParticipant доказал
   * участие только при подписке; игрок, покинувший лобби (leaveGame/замена),
   * не должен получать ПОСЛЕДУЮЩЕЕ состояние. Apollo driver вызывает filter
   * через filterFn.call(instanceRef, payload, variables, context) — то есть
   * с JWT-контекстом конкретного подписчика на каждое опубликованное событие.
   * Ошибка проверки (DB-сбой) безопасно трактуется как «не доставлять».
   */
  private async isDeliveryAuthorized(gameId: string, context: any): Promise<boolean> {
    try {
      const userId = this.getUserId(context);
      return await this.gameStateService.isParticipant(gameId, userId);
    } catch {
      return false;
    }
  }

  /**
   * GD-027 (ACC-011/012): connection barrier. Подписка на gameStateUpdated
   * стартует с текущим снапшотом состояния: окно между HTTP-запросом
   * gameState и установкой WS-подписки закрывается сервером — событие,
   * произошедшее «между», придёт либо барьер-снапшотом (уже с новым seq),
   * либо live-событием после него. Дубликат невозможен: клиент применяет
   * снапшоты строго по возрастанию sequenceNumber.
   */
  // PubSubAsyncIterableIterator подписывается лениво (subscribeAll на первом
  // next()) — события, опубликованные ДО первого next(), терялись бы. Поэтому
  // upstream.next() дёргается ДО await loadState: подписка регистрируется
  // немедленно, а барьер-снапшот строится параллельно.
  //
  // Реализация — ручной async iterator (НЕ async generator): генератор,
  // зависший в await firstUpstream, не входит в finally до settlement
  // in-flight next(), а PubSub-итератор не отменяет его при return() —
  // ранняя отписка при тишине держала бы underlying-подписку до первого
  // события. Здесь ожидание firstUpstream гонкуется с сигналом отписки:
  // return() немедленно отпускает upstream и завершает ожидающий next().
  private withSnapshotBarrier(
    gameId: string,
    since: number | null | undefined,
    upstream: AsyncIterableIterator<GamePubSubEvent>,
  ): AsyncIterableIterator<GamePubSubEvent> {
    const DONE: IteratorResult<GamePubSubEvent> = { done: true, value: undefined };
    let returned = false;
    let releaseReturnWaiter: ((value: 'returned') => void) | undefined;
    // Резолвится ровно один раз — первым return()/throw(); ждущий firstUpstream
    // next() видит его в Promise.race и завершается done без ожидания PubSub.
    const returnWaiter = new Promise<'returned'>((resolve) => {
      releaseReturnWaiter = resolve;
    });
    let firstUpstreamStarted = false;
    // Независимо от того, вернул ли первый next() барьер-снапшот, прочитанное
    // firstUpstream надо ОТДАТЬ клиенту: событие, опубликованное между
    // регистрацией подписки и построением снапшота, уже изъято из PubSub и
    // будет молча проглочено, если второй next() снова дёрнет upstream.next().
    let firstUpstream: Promise<IteratorResult<GamePubSubEvent>> | null = null;

    const iterator: AsyncIterableIterator<GamePubSubEvent> = {
      [Symbol.asyncIterator]: () => iterator,
      next: async (): Promise<IteratorResult<GamePubSubEvent>> => {
        if (returned) return DONE;
        if (!firstUpstreamStarted) {
          firstUpstreamStarted = true;
          // Регистрирует PubSub-подписку немедленно (см. комментарий выше).
          const firstPromise = upstream.next();
          // Гонка не отменяет сам firstUpstream — глушим возможный поздний
          // отказ, чтобы не получить unhandled rejection.
          firstPromise.catch(() => undefined);
          firstUpstream = firstPromise;
          let state: GameState | null = null;
          try {
            state = await this.gameStateService.loadState(gameId);
          } catch (e) {
            if (e instanceof NotFoundException) {
              // Лобби-фаза: состояние ещё не создано — отдаём только live-события
              this.logger.debug(`Barrier snapshot skipped (lobby phase) for ${gameId}`);
            } else {
              // Genuine outage (DB/Redis): логируем и пробрасываем — молчаливый
              // live-only поток лгал бы клиенту о свежести состояния.
              this.logger.error(`Barrier snapshot failed for ${gameId}: ${e}`);
              await upstream.return?.().catch(() => undefined);
              throw e;
            }
          }
          if (state && (since == null || state.sequenceNumber > since)) {
            return {
              done: false,
              value: {
                gameId,
                sequenceNumber: state.sequenceNumber,
                timestamp: Date.now(),
                eventType: 'STATE_UPDATED',
                payload: state,
              },
            };
          }
          // Барьер-снапшот не понадобился (state актуален): fallthrough —
          // firstUpstream потребляется блоком ниже в ЭТОМ же вызове.
        }
        if (firstUpstream !== null) {
          const pending = firstUpstream;
          firstUpstream = null;
          if (returned) return DONE;
          const first = await Promise.race([pending, returnWaiter]);
          if (first === 'returned') return DONE;
          return first.done ? DONE : { done: false, value: first.value };
        }
        const next = await upstream.next();
        return next.done ? DONE : { done: false, value: next.value };
      },
      return: async (value?: any): Promise<IteratorResult<GamePubSubEvent>> => {
        returned = true;
        releaseReturnWaiter?.('returned');
        try {
          await upstream.return?.();
        } catch (e) {
          this.logger.warn(`Barrier upstream unsubscribe failed for ${gameId}: ${e}`);
        }
        return { done: true, value };
      },
      throw: async (error?: any): Promise<IteratorResult<GamePubSubEvent>> => {
        returned = true;
        releaseReturnWaiter?.('returned');
        try {
          await upstream.throw?.(error);
        } catch {
          // upstream сам обработал/не имеет throw — подписка уже снята
        }
        return DONE;
      },
    };
    return iterator;
  }

  /**
   * Подписка на обновления состояния игры
   * Поддерживает since параметр для реконнекта
   *
   * Фильтр по 'STATE_UPDATED': каждая мутация публикует ДВА события —
   * 'STATE_UPDATED' из saveState и специфичный eventType из executeMutation;
   * фильтр даёт ровно одно срабатывание на мутацию.
   * Проверка since — тоже в filter (resolve с null упал бы на non-nullable типе).
   * since НЕ обещает replay пропущенных событий: фильтруются только future.
   */
  @Subscription(() => GameStateGQL, {
    name: 'gameStateUpdated',
    filter: async function (
      this: GameSubscriptionResolver,
      payload: any,
      variables: any,
      context: any,
    ) {
      if (!payload || !variables) return false;
      if (
        payload.gameId !== variables.gameId ||
        payload.eventType !== 'STATE_UPDATED' ||
        (variables.since != null && payload.sequenceNumber <= variables.since)
      ) {
        return false;
      }
      return this.isDeliveryAuthorized(payload.gameId, context);
    },
    resolve: function (this: GameSubscriptionResolver, value: any, args: any, context: any) {
      return this.resolveGameState(value || null, args, context);
    },
  })
  @UseGuards(GqlAuthGuard)
  async gameStateUpdated(
    @Args('gameId') gameId: string,
    @Args('since', { nullable: true }) since?: number,
    // userId оставлен в сигнатуре для совместимости схемы, но ИГНОРИРУЕТСЯ:
    // фильтрация приватных данных идёт по context.req.user.id (JWT)
    @Args('userId', { nullable: true }) userId?: string,
    @Context() context?: any,
  ): Promise<AsyncIterableIterator<GamePubSubEvent>> {
    await this.requireParticipant(gameId, context);
    const upstream = this.subscriptionService.asyncIteratorForGame(gameId);
    return this.withSnapshotBarrier(gameId, since, upstream);
  }

  /**
   * Подписка на события атак
   */
  @Subscription(() => GameEvent, {
    name: 'attackInitiated',
    filter: async function (this: GameSubscriptionResolver, payload: any, variables: any, context: any) {
      if (!payload || !variables) return false;
      if (payload.gameId !== variables.gameId || payload.eventType !== GameEventType.ATTACK_INITIATED) {
        return false;
      }
      return this.isDeliveryAuthorized(payload.gameId, context);
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  @UseGuards(GqlAuthGuard)
  async attackInitiated(
    @Args('gameId') gameId: string,
    @Context() context: any,
  ): Promise<AsyncIterableIterator<GamePubSubEvent>> {
    await this.requireParticipant(gameId, context);
    return this.subscriptionService.asyncIteratorForGame(gameId);
  }

  /**
   * Подписка на события защиты
   */
  @Subscription(() => GameEvent, {
    name: 'defensePlayed',
    filter: async function (this: GameSubscriptionResolver, payload: any, variables: any, context: any) {
      if (!payload || !variables) return false;
      if (payload.gameId !== variables.gameId || payload.eventType !== GameEventType.DEFENSE_PLAYED) {
        return false;
      }
      return this.isDeliveryAuthorized(payload.gameId, context);
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  @UseGuards(GqlAuthGuard)
  async defensePlayed(
    @Args('gameId') gameId: string,
    @Context() context: any,
  ): Promise<AsyncIterableIterator<GamePubSubEvent>> {
    await this.requireParticipant(gameId, context);
    return this.subscriptionService.asyncIteratorForGame(gameId);
  }

  /**
   * Подписка на события разрешения боя
   */
  @Subscription(() => GameEvent, {
    name: 'combatResolved',
    filter: async function (this: GameSubscriptionResolver, payload: any, variables: any, context: any) {
      if (!payload || !variables) return false;
      if (payload.gameId !== variables.gameId || payload.eventType !== GameEventType.COMBAT_RESOLVED) {
        return false;
      }
      return this.isDeliveryAuthorized(payload.gameId, context);
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  @UseGuards(GqlAuthGuard)
  async combatResolved(
    @Args('gameId') gameId: string,
    @Context() context: any,
  ): Promise<AsyncIterableIterator<GamePubSubEvent>> {
    await this.requireParticipant(gameId, context);
    return this.subscriptionService.asyncIteratorForGame(gameId);
  }

  /**
   * Подписка на события смены хода
   * Никто не публикует 'TURN_CHANGED' — реальный eventType мутации endTurn
   * это 'TURN_ENDED', принимаем оба
   */
  @Subscription(() => TurnState, {
    name: 'turnChanged',
    filter: async function (this: GameSubscriptionResolver, payload: any, variables: any, context: any) {
      if (!payload || !variables) return false;
      if (
        payload.gameId !== variables.gameId ||
        (payload.eventType !== GameEventType.TURN_ENDED &&
          payload.eventType !== GameEventType.TURN_CHANGED)
      ) {
        return false;
      }
      return this.isDeliveryAuthorized(payload.gameId, context);
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveTurnState(value || null);
    },
  })
  @UseGuards(GqlAuthGuard)
  async turnChanged(
    @Args('gameId') gameId: string,
    @Context() context: any,
  ): Promise<AsyncIterableIterator<GamePubSubEvent>> {
    await this.requireParticipant(gameId, context);
    return this.subscriptionService.asyncIteratorForGame(gameId);
  }

  /**
   * Подписка на события присоединения игроков
   * Known gap: 'PLAYER_JOINED' пока никто не публикует (joinGame происходит в лобби,
   * где нет GameState для publishGameUpdate) — подписка не виснет, но молчит
   */
  @Subscription(() => GameEvent, {
    name: 'playerJoined',
    filter: async function (this: GameSubscriptionResolver, payload: any, variables: any, context: any) {
      if (!payload || !variables) return false;
      if (payload.gameId !== variables.gameId || payload.eventType !== GameEventType.PLAYER_JOINED) {
        return false;
      }
      return this.isDeliveryAuthorized(payload.gameId, context);
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  @UseGuards(GqlAuthGuard)
  async playerJoined(
    @Args('gameId') gameId: string,
    @Context() context: any,
  ): Promise<AsyncIterableIterator<GamePubSubEvent>> {
    await this.requireParticipant(gameId, context);
    return this.subscriptionService.asyncIteratorForGame(gameId);
  }

  /**
   * Подписка на события выхода игроков
   * Known gap: 'PLAYER_LEFT' пока никто не публикует (см. playerJoined)
   */
  @Subscription(() => GameEvent, {
    name: 'playerLeft',
    filter: async function (this: GameSubscriptionResolver, payload: any, variables: any, context: any) {
      if (!payload || !variables) return false;
      if (payload.gameId !== variables.gameId || payload.eventType !== GameEventType.PLAYER_LEFT) {
        return false;
      }
      return this.isDeliveryAuthorized(payload.gameId, context);
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  @UseGuards(GqlAuthGuard)
  async playerLeft(
    @Args('gameId') gameId: string,
    @Context() context: any,
  ): Promise<AsyncIterableIterator<GamePubSubEvent>> {
    await this.requireParticipant(gameId, context);
    return this.subscriptionService.asyncIteratorForGame(gameId);
  }

  /**
   * Подписка на события окончания игры
   * 'GAME_ENDED' публикуется из executeMutation при phase === GAME_OVER
   */
  @Subscription(() => GameEvent, {
    name: 'gameEnded',
    filter: async function (this: GameSubscriptionResolver, payload: any, variables: any, context: any) {
      if (!payload || !variables) return false;
      if (payload.gameId !== variables.gameId || payload.eventType !== GameEventType.GAME_ENDED) {
        return false;
      }
      return this.isDeliveryAuthorized(payload.gameId, context);
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  @UseGuards(GqlAuthGuard)
  async gameEnded(
    @Args('gameId') gameId: string,
    @Context() context: any,
  ): Promise<AsyncIterableIterator<GamePubSubEvent>> {
    await this.requireParticipant(gameId, context);
    return this.subscriptionService.asyncIteratorForGame(gameId);
  }

  // ============================================
  // Private Helper Methods
  // ============================================

  /**
   * Получить userId из контекста
   */
  private getUserId(context: SubscriptionAuthContext): string {
    const userId = context?.req?.user?.id || context?.user?.id;

    if (!userId) {
      throw new ForbiddenException('User not authenticated');
    }

    return userId;
  }
}
