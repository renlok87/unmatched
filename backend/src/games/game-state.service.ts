import { Injectable, Logger, NotFoundException, Optional } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { GameSubscriptionService } from './game-subscription.service';
import { GamePhase } from './dto';
import { ConcurrentModificationException } from './exceptions/game.exceptions';

/* eslint-disable @typescript-eslint/no-unsafe-assignment */
/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-call */
/* eslint-disable @typescript-eslint/no-redundant-type-constituents */
/* eslint-disable @typescript-eslint/no-unsafe-argument */

/**
 * Интерфейс игрового состояния
 * Это основная структура состояния игры
 */
export interface GameState {
  // Основная информация
  gameId: string;
  sequenceNumber: number;
  phase: GamePhase;
  turnCount: number;
  currentTurnPlayerId: string;

  // Игроки
  players: GameStatePlayer[];

  // Бойцы на доске
  fighters: Fighter[];

  // Колоды и сброс
  decks: Record<string, DeckState>;
  discardPiles: Record<string, Card[]>;

  // Зоны ручек
  handZones: Record<string, HandZone>;

  // Двери и туман войны
  boardState: BoardState;

  // Метаданные
  metadata: GameStateMetadata;
}

export interface GameStatePlayer {
  userId: string;
  heroId: string;
  health: number;
  maxHealth: number;
  fighterIds: string[];
  isAlive: boolean;
}

export interface Fighter {
  id: string;
  ownerId: string;
  heroId: string;
  name: string;
  type: 'HERO' | 'MINION' | 'HUGE';
  health: number;
  maxHealth: number;
  position: { x: number; y: number };
  effects: FighterEffect[];
  hasSidekick: boolean;
  sidekickIds?: string[];
}

export interface FighterEffect {
  type: string;
  value?: number;
  duration?: 'permanent' | 'turn' | 'round';
  expiresAt?: number;
  source?: string;
}

export interface DeckState {
  cards: Card[];
  drawPile: Card[];
  // Карта сверху колоды (видна только владельцу)
  topCard?: Card;
}

export interface Card {
  id: string;
  cardId: string;
  name: string;
  nameEn: string;
  nameRu: string;
  cardType: 'ATTACK' | 'DEFENSE' | 'SCHEME' | 'UNIVERSAL';
  attackValue?: number;
  defenseValue?: number;
  boostValue?: number;
  effects?: any[];
}

export interface HandZone {
  cards: HandCard[];
  maxSize: number;
}

export interface HandCard extends Card {
  isVisible: boolean; // Видно ли другим игрокам
}

export interface BoardState {
  doors: Record<string, boolean>; // ID двери -> открыта/закрыта
  fog: Record<string, boolean>; // ID клетки -> туман/нет
  tokens: Record<string, any>; // ID клетки -> жетоны
}

export interface GameStateMetadata {
  lastActionAt: Date;
  lastActionBy: string;
  version: number;
  // Опционально: compressed для оптимизации
  compressed?: boolean;
}

/**
 * Сериализованное состояние для передачи клиенту
 */
export interface SerializedGameState {
  v: number; // Версия формата сериализации
  g: string; // gameId
  s: number; // sequenceNumber
  p: GamePhase; // phase
  t: number; // turnCount
  c: string; // currentTurnPlayerId
  pl: SerializedPlayer[]; // players
  f: SerializedFighter[]; // fighters
  d: Record<string, SerializedDeck>; // decks
  h: Record<string, SerializedHand>; // hands
  b: SerializedBoard; // board
  m: {
    la: string; // lastActionAt
    lb: string; // lastActionBy
    v: number; // version
  };
}

export interface SerializedPlayer {
  uid: string;
  hid: string;
  hp: number;
  mhp: number;
  fid: string[];
  alv: boolean;
}

export interface SerializedFighter {
  id: string;
  oid: string;
  hid: string;
  n: string;
  ty: 'HERO' | 'MINION' | 'HUGE';
  hp: number;
  mhp: number;
  pos: { x: number; y: number };
  e: any[];
  hs: boolean;
  si?: string[];
}

export interface SerializedDeck {
  c: number; // Количество карт в колоде
  tc?: Card; // Верхняя карта (только для владельца)
}

export interface SerializedHand {
  c: SerializedHandCard[]; // Карты в руке
  ms: number; // Максимальный размер
}

export interface SerializedHandCard extends Card {
  v: boolean; // isVisible
}

export interface SerializedBoard {
  dr: Record<string, boolean>; // doors
  fg: Record<string, boolean>; // fog
  tk: Record<string, any>; // tokens
}

/**
 * GameStateService управляет состоянием игры:
 * - Сохранение/загрузка из БД
 * - Кеширование в Redis
 * - Сериализация/десериализация
 * - Фильтрация приватных данных
 */
@Injectable()
export class GameStateService {
  private readonly logger = new Logger(GameStateService.name);
  private readonly STATE_CACHE_TTL = 600; // 10 минут
  private readonly STATE_CACHE_PREFIX = 'gamestate:';
  private readonly SERIALIZATION_VERSION = 1;

  constructor(
    private prisma: PrismaService,
    private redis: RedisService,
    @Optional() private gameSubscriptionService?: GameSubscriptionService,
  ) {}

  /**
   * Сохранить состояние игры в БД
   */
  async saveState(gameId: string, state: GameState): Promise<void> {
    const serialized = this.serialize(state);

    await this.prisma.$transaction(async (tx) => {
      // Проверяем текущий sequence number для optimistic locking
      const existing = await tx.gameState.findUnique({
        where: { gameId },
      });

      if (existing && existing.sequenceNumber !== state.sequenceNumber - 1) {
        throw new ConcurrentModificationException(existing.sequenceNumber, state.sequenceNumber);
      }

      // Upsert состояния
      await tx.gameState.upsert({
        where: { gameId },
        create: {
          gameId,
          state: serialized as any,
          sequenceNumber: state.sequenceNumber,
          currentTurnPlayerId: state.currentTurnPlayerId,
          phase: state.phase,
          turnCount: state.turnCount,
        },
        update: {
          state: serialized as any,
          sequenceNumber: state.sequenceNumber,
          currentTurnPlayerId: state.currentTurnPlayerId,
          phase: state.phase,
          turnCount: state.turnCount,
        },
      });

      // Обновляем version в Game
      await tx.game.update({
        where: { id: gameId },
        data: { version: state.sequenceNumber },
      });
    });

    // Обновляем кеш
    await this.cacheState(gameId, state);

    // Публикуем обновление для подписчиков (WebSocket)
    if (this.gameSubscriptionService) {
      await this.gameSubscriptionService.publishGameUpdate(gameId, 'STATE_UPDATED', state);
    }
  }

  /**
   * Загрузить состояние игры из БД
   */
  async loadState(gameId: string): Promise<GameState> {
    // Сначала проверяем кеш
    const cached = await this.getCachedState(gameId);
    if (cached) {
      return cached;
    }

    const gameState = await this.prisma.gameState.findUnique({
      where: { gameId },
    });

    if (!gameState) {
      throw new NotFoundException(`Состояние игры ${gameId} не найдено`);
    }

    const state = this.deserialize(gameState.state as any);

    // Кешируем
    await this.cacheState(gameId, state);

    return state;
  }

  /**
   * Сохранить состояние в кеш Redis
   */
  async cacheState(gameId: string, state: GameState): Promise<void> {
    const cacheKey = `${this.STATE_CACHE_PREFIX}${gameId}`;
    await this.redis.setJsonex(cacheKey, this.STATE_CACHE_TTL, state);
  }

  /**
   * Получить состояние из кеша Redis
   */
  async getCachedState(gameId: string): Promise<GameState | null> {
    const cacheKey = `${this.STATE_CACHE_PREFIX}${gameId}`;
    const cached = await this.redis.getJson<GameState>(cacheKey);
    return cached;
  }

  /**
   * Удалить состояние из кеша
   */
  async invalidateStateCache(gameId: string): Promise<void> {
    const cacheKey = `${this.STATE_CACHE_PREFIX}${gameId}`;
    await this.redis.del(cacheKey);
  }

  /**
   * Сериализовать состояние для передачи клиенту
   * Убирает приватные данные для указанного игрока
   */
  serialize(state: GameState): SerializedGameState {
    return {
      v: this.SERIALIZATION_VERSION,
      g: state.gameId,
      s: state.sequenceNumber,
      p: state.phase,
      t: state.turnCount,
      c: state.currentTurnPlayerId,
      pl: state.players.map((p) => ({
        uid: p.userId,
        hid: p.heroId,
        hp: p.health,
        mhp: p.maxHealth,
        fid: p.fighterIds,
        alv: p.isAlive,
      })),
      f: state.fighters.map((f) => ({
        id: f.id,
        oid: f.ownerId,
        hid: f.heroId,
        n: f.name,
        ty: f.type,
        hp: f.health,
        mhp: f.maxHealth,
        pos: f.position,
        e: f.effects,
        hs: f.hasSidekick,
        si: f.sidekickIds,
      })),
      d: Object.entries(state.decks).reduce(
        (acc, [userId, deck]) => {
          acc[userId] = {
            c: deck.drawPile.length,
            tc: deck.topCard,
          };
          return acc;
        },
        {} as Record<string, SerializedDeck>,
      ),
      h: Object.entries(state.handZones).reduce(
        (acc, [userId, hand]) => {
          acc[userId] = {
            c: hand.cards.map((card) => ({
              ...card,
              v: card.isVisible,
            })),
            ms: hand.maxSize,
          };
          return acc;
        },
        {} as Record<string, SerializedHand>,
      ),
      b: {
        dr: state.boardState.doors,
        fg: state.boardState.fog,
        tk: state.boardState.tokens,
      },
      m: {
        la: state.metadata.lastActionAt.toISOString(),
        lb: state.metadata.lastActionBy,
        v: state.metadata.version,
      },
    };
  }

  /**
   * Десериализовать состояние из формата передачи
   */
  deserialize(data: SerializedGameState | any): GameState {
    // Если это не наша сериализованная структура, возвращаем как есть
    if (!data.v || !data.g) {
      return data as GameState;
    }

    return {
      gameId: data.g,
      sequenceNumber: data.s,
      phase: data.p,
      turnCount: data.t,
      currentTurnPlayerId: data.c,
      players: data.pl.map((p: SerializedPlayer) => ({
        userId: p.uid,
        heroId: p.hid,
        health: p.hp,
        maxHealth: p.mhp,
        fighterIds: p.fid,
        isAlive: p.alv,
      })),
      fighters: data.f.map((f: SerializedFighter) => ({
        id: f.id,
        ownerId: f.oid,
        heroId: f.hid,
        name: f.n,
        type: f.ty,
        health: f.hp,
        maxHealth: f.mhp,
        position: f.pos,
        effects: f.e,
        hasSidekick: f.hs,
        sidekickIds: f.si,
      })),
      decks: Object.entries(data.d).reduce(
        (acc, [userId, deck]: [string, any]) => {
          acc[userId] = {
            cards: [],
            drawPile: [],
            topCard: deck.tc,
          };
          return acc;
        },
        {} as Record<string, DeckState>,
      ),
      discardPiles: {},
      handZones: Object.entries(data.h).reduce(
        (acc, [userId, hand]: [string, any]) => {
          acc[userId] = {
            cards: hand.c.map((card: SerializedHandCard) => ({
              ...card,
              isVisible: card.v,
            })),
            maxSize: hand.ms,
          };
          return acc;
        },
        {} as Record<string, HandZone>,
      ),
      boardState: {
        doors: data.b.dr,
        fog: data.b.fg,
        tokens: data.b.tk,
      },
      metadata: {
        lastActionAt: new Date(data.m.la),
        lastActionBy: data.m.lb,
        version: data.m.v,
      },
    };
  }

  /**
   * Отфильтровать приватные данные для конкретного игрока
   * - Скрывает карты в руке соперника
   * - Скрывает верхнюю карту колоды соперника
   * - Скрывает содержимое сброса соперника
   */
  filterPrivateData(state: GameState, playerId: string): GameState {
    const filtered = JSON.parse(JSON.stringify(state)) as GameState;

    // Фильтруем руки других игроков
    Object.entries(filtered.handZones).forEach(([userId, hand]) => {
      if (userId !== playerId) {
        hand.cards = hand.cards.map((card) => ({
          ...card,
          id: card.id,
          cardType: card.cardType,
          // Скрываем детали карты
          name: '???',
          nameEn: 'Hidden',
          nameRu: 'Скрыто',
          attackValue: undefined,
          defenseValue: undefined,
          boostValue: undefined,
          effects: undefined,
          isVisible: false,
        }));
      }
    });

    // Фильтруем колоды других игроков
    Object.entries(filtered.decks).forEach(([userId, deck]) => {
      if (userId !== playerId) {
        deck.topCard = undefined;
      }
    });

    return filtered;
  }

  /**
   * Создать начальное состояние игры
   */
  async createInitialState(gameId: string, playerIds: string[]): Promise<GameState> {
    const players = await this.prisma.gamePlayer.findMany({
      where: { gameId },
      include: {
        user: true,
      },
    });

    const initialState: GameState = {
      gameId,
      sequenceNumber: 1,
      phase: GamePhase.SETUP,
      turnCount: 0,
      currentTurnPlayerId: players[0]?.userId || '',
      players: players.map((p) => ({
        userId: p.userId,
        heroId: p.heroId || '',
        health: 100, // Будет перезаписано на основе героя
        maxHealth: 100,
        fighterIds: [],
        isAlive: true,
      })),
      fighters: [],
      decks: playerIds.reduce(
        (acc, uid) => ({
          ...acc,
          [uid]: { cards: [], drawPile: [] },
        }),
        {},
      ),
      discardPiles: {},
      handZones: playerIds.reduce(
        (acc, uid) => ({
          ...acc,
          [uid]: { cards: [], maxSize: 5 },
        }),
        {},
      ),
      boardState: {
        doors: {},
        fog: {},
        tokens: {},
      },
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: players[0]?.userId || '',
        version: 1,
      },
    };

    return initialState;
  }

  /**
   * Применить optimistic lock при обновлении состояния
   */
  async updateWithLock(
    gameId: string,
    expectedSequence: number,
    updateFn: (state: GameState) => GameState,
  ): Promise<GameState> {
    const lockKey = `gamestate:lock:${gameId}`;

    return await this.redis.withLock(
      lockKey,
      async () => {
        const currentState = await this.loadState(gameId);

        if (currentState.sequenceNumber !== expectedSequence) {
          throw new ConcurrentModificationException(expectedSequence, currentState.sequenceNumber);
        }

        const newState = updateFn(currentState);
        newState.sequenceNumber = expectedSequence + 1;
        newState.metadata.lastActionAt = new Date();

        await this.saveState(gameId, newState);

        return newState;
      },
      5000,
    );
  }

  /**
   * Получить текущий sequence number игры
   */
  async getSequenceNumber(gameId: string): Promise<number> {
    const gameState = await this.prisma.gameState.findUnique({
      where: { gameId },
      select: { sequenceNumber: true },
    });

    return gameState?.sequenceNumber ?? 0;
  }

  /**
   * Проверить валидность состояния
   */
  validateState(state: GameState): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Проверяем базовые поля
    if (!state.gameId) {
      errors.push('Missing gameId');
    }
    if (state.sequenceNumber < 0) {
      errors.push('Invalid sequenceNumber');
    }
    if (!state.currentTurnPlayerId) {
      errors.push('Missing currentTurnPlayerId');
    }

    // Проверяем игроков
    if (!state.players || state.players.length === 0) {
      errors.push('No players in state');
    }

    // Проверяем, что текущий игрок существует
    if (
      state.currentTurnPlayerId &&
      !state.players?.find((p) => p.userId === state.currentTurnPlayerId)
    ) {
      errors.push('Current player not found in players list');
    }

    // Проверяем бойцов
    if (state.fighters) {
      state.fighters.forEach((f) => {
        if (!f.id) errors.push(`Fighter missing id`);
        if (!f.ownerId) errors.push(`Fighter ${f.id} missing ownerId`);
        if (f.health < 0) errors.push(`Fighter ${f.id} has negative health`);
      });
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * Получить дифф состояний для optimistic updates
   */
  getStateDiff(oldState: GameState, newState: GameState): any {
    // Упрощенная реализация - возвращаем полное новое состояние
    // В продакшене можно использовать более сложный diff алгоритм
    return {
      oldSequence: oldState.sequenceNumber,
      newSequence: newState.sequenceNumber,
      changes: {
        phase: oldState.phase !== newState.phase ? newState.phase : undefined,
        turnCount: oldState.turnCount !== newState.turnCount ? newState.turnCount : undefined,
        currentTurnPlayerId:
          oldState.currentTurnPlayerId !== newState.currentTurnPlayerId
            ? newState.currentTurnPlayerId
            : undefined,
      },
    };
  }

  /**
   * Получить события игры с указанного sequence number (для catch-up при реконнекте)
   */
  async getEventsSince(gameId: string, sinceSequence: number): Promise<any[]> {
    const actions = await this.prisma.gameAction.findMany({
      where: {
        gameId,
        sequenceNumber: {
          gt: sinceSequence,
        },
      },
      orderBy: {
        sequenceNumber: 'asc',
      },
      take: 100,
    });

    return actions.map((action) => ({
      sequenceNumber: action.sequenceNumber,
      type: action.type,
      gameId: action.gameId,
      playerId: action.playerId,
      payload: action.payload,
      timestamp: action.timestamp,
    }));
  }
}
