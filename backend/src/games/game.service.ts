import {
  Injectable,
  Logger,
  NotFoundException,
  ForbiddenException,
  BadRequestException,
  Optional,
} from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { GameInitializationService } from './services/game-initialization.service';
import { GameActionService } from './services/game-action.service';
import { GameSubscriptionService } from './game-subscription.service';
import { AiTurnService } from './services/ai-turn.service';
import { GameActionType } from './models/game-action.model';
import { GameStatus, GameMode } from './dto';
import { GameResponse } from './models';
import { GameAccessDeniedException, MaxActiveGamesException } from './exceptions/game.exceptions';
import { DEFAULT_BOARD_ID, DEFAULT_BOARD_NAME } from './default-board';
import * as crypto from 'node:crypto';

/* eslint-disable @typescript-eslint/no-unsafe-assignment */
/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-call */
/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable @typescript-eslint/no-unsafe-enum-comparison */

@Injectable()
export class GameService {
  private readonly logger = new Logger(GameService.name);
  private readonly CACHE_TTL = 300; // 5 минут
  private readonly GAME_CACHE_PREFIX = 'game:';
  private readonly GAMES_LIST_CACHE_PREFIX = 'games:list:';
  private readonly MAX_ACTIVE_GAMES = 5; // Максимум активных игр на пользователя
  private readonly AI_USER_EMAIL = 'ai@unmached.local'; // системный юзер-бот (VS_AI)
  private aiUserIdCache: string | null = null;

  constructor(
    private prisma: PrismaService,
    private redis: RedisService,
    private gameInitialization: GameInitializationService,
    private gameActionService: GameActionService,
    private gameSubscriptionService: GameSubscriptionService,
    @Optional() private readonly aiTurnService?: AiTurnService,
  ) {}

  /**
   * Опубликовать лобби-событие в ws-подписки (best-effort, не роняет операцию)
   */
  private async publishLobby(
    gameId: string,
    eventType: string,
    payload: Record<string, unknown>,
  ): Promise<void> {
    try {
      await this.gameSubscriptionService.publishLobbyEvent(gameId, eventType, payload);
    } catch (e) {
      this.logger.warn(`Failed to publish lobby event ${eventType} for game ${gameId}: ${e}`);
    }
  }

  /**
   * Записать лобби-событие в журнал GameAction (best-effort, не роняет операцию)
   */
  private async recordLobbyAction(
    gameId: string,
    playerId: string,
    type: GameActionType,
    sequenceNumber: number,
    metadata: Record<string, unknown> = {},
  ): Promise<void> {
    try {
      await this.gameActionService.recordAction({
        gameId,
        sequenceNumber,
        type,
        playerId,
        metadata,
      });
    } catch (e) {
      // Журнал не должен влиять на основную операцию (например, Redis недоступен)
      this.logger.warn(`Failed to record lobby action ${type} for game ${gameId}: ${e}`);
    }
  }

  /**
   * Создать новую игру
   */
  async createGame(
    dto: { mode?: GameMode; boardId?: string },
    userId: string,
    idempotencyKey?: string,
  ): Promise<GameResponse> {
    // Идемпотентность: если передан ключ, проверяем, не была ли уже создана игра
    if (idempotencyKey) {
      const existingGame = await this.findGameByIdempotencyKey(idempotencyKey, userId);
      if (existingGame) {
        return await this.getGame(existingGame.id);
      }
    }

    // Проверяем количество активных игр пользователя
    const activeGamesCount = await this.prisma.game.count({
      where: {
        OR: [{ hostId: userId }, { opponentId: userId }],
        status: { in: [GameStatus.PENDING, GameStatus.LOBBY, GameStatus.IN_PROGRESS] },
      },
    });

    if (activeGamesCount >= this.MAX_ACTIVE_GAMES) {
      throw new MaxActiveGamesException(activeGamesCount, this.MAX_ACTIVE_GAMES);
    }

    // НД-1: без boardId — Marmoreal · original map; доска обязана существовать
    // (у Game.boardId нет внешнего ключа — несуществующий id стал бы игрой без доски)
    const boardId = dto.boardId || DEFAULT_BOARD_ID;
    const board = await this.prisma.board.findUnique({
      where: { id: boardId },
      select: { id: true },
    });
    if (!board) {
      throw new BadRequestException(
        dto.boardId
          ? `Доска ${boardId} не найдена`
          : `Доска по умолчанию «${DEFAULT_BOARD_NAME}» (${DEFAULT_BOARD_ID}) отсутствует в БД: ` +
            'засейте её prisma/seed-env-map-boards.ts',
      );
    }

    // Генерируем уникальный код для приглашения
    const code = await this.generateGameCode();

    // Создаем игру в транзакции
    const game = await this.prisma.$transaction(async (tx) => {
      const newGame = await tx.game.create({
        data: {
          hostId: userId,
          boardId,
          mode: dto.mode || GameMode.ONE_V_ONE,
          status: GameStatus.LOBBY,
          code,
          ...(idempotencyKey && { idempotencyKey }),
        },
      });

      // Добавляем хоста как игрока
      await tx.gamePlayer.create({
        data: {
          gameId: newGame.id,
          userId,
          seatOrder: 0,
        },
      });

      return newGame;
    });

    // Инвалидируем кеш списка игр
    await this.invalidateGamesListCache(userId);

    // Журналируем создание игры (state ещё нет — seq 0)
    await this.recordLobbyAction(game.id, userId, GameActionType.GAME_CREATED, 0, {
      mode: dto.mode || GameMode.ONE_V_ONE,
      boardId,
    });

    return await this.getGame(game.id);
  }

  /**
   * GD-029: безопасный code→gameId resolution для входа в приватную комнату
   * по отображаемому коду. Возвращает игру ТОЛЬКО если она в LOBBY и ещё не
   * заполнена; несуществующий/занятый/стартовавший код неотличимы (null) —
   * комната не раскрывается. Дальнейший доступ гейтится joinGame как обычно.
   */
  async getGameByCode(code: string): Promise<GameResponse | null> {
    const game = await this.prisma.game.findUnique({
      where: { code },
      include: {
        host: { select: { id: true, username: true, avatar: true } },
        opponent: { select: { id: true, username: true, avatar: true } },
        players: {
          include: { user: { select: { id: true, username: true, avatar: true } } },
          orderBy: { seatOrder: 'asc' },
        },
        state: true,
      },
    });

    if (!game || game.status !== GameStatus.LOBBY || game.opponentId) {
      return null;
    }
    return this.mapToGameResponse(game);
  }

  /**
   * Найти игру по idempotencyKey
   */
  private async findGameByIdempotencyKey(
    idempotencyKey: string,
    userId: string,
  ): Promise<{ id: string } | null> {
    return await this.prisma.game.findFirst({
      where: {
        idempotencyKey,
        hostId: userId,
      },
      select: { id: true },
    });
  }

  /**
   * Сгенерировать уникальный короткий код для игры
   * Формат: XXXXXX (6 символов, только заглавные буквы)
   */
  private async generateGameCode(): Promise<string> {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // без I, O, 0, 1 для читаемости
    let code: string;
    let attempts = 0;
    const maxAttempts = 10;

    do {
      code = Array.from({ length: 6 }, () =>
        chars[Math.floor(Math.random() * chars.length)],
      ).join('');
      attempts++;

      const existing = await this.prisma.game.findUnique({
        where: { code },
        select: { id: true },
      });

      if (!existing) {
        return code;
      }
    } while (attempts < maxAttempts);

    // Если не удалось сгенерировать уникальный код, используем CUID + префикс
    return `GM-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
  }

  /**
   * Получить игру по ID
   */
  async getGame(gameId: string, bypassCache = false): Promise<GameResponse> {
    // Сначала проверяем кеш
    const cacheKey = `${this.GAME_CACHE_PREFIX}${gameId}`;
    const cached = bypassCache ? null : await this.redis.getJson<GameResponse>(cacheKey);
    if (cached) {
      // Терминальные строки иммутабельны — кеш авторитетен. Живой статус
      // сверяется с БД (как getCachedState в GameStateService): терминальная
      // инвалидация в saveState может не пройти (сбой Redis), и закоммиченный
      // FINISHED не должен отдаваться как IN_PROGRESS до истечения TTL.
      if (cached.status === GameStatus.FINISHED || cached.status === GameStatus.ABORTED) {
        return cached;
      }
      const row = await this.prisma.game.findUnique({
        where: { id: gameId },
        select: { status: true, version: true },
      });
      if (!row) {
        throw new NotFoundException('Игра не найдена');
      }
      if (row.status === cached.status && row.version === cached.version) {
        return cached;
      }
      // Кеш просрочен (терминальный переход/сдвиг version) — перечитываем ниже.
    }

    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      include: {
        host: {
          select: {
            id: true,
            username: true,
            avatar: true,
          },
        },
        opponent: {
          select: {
            id: true,
            username: true,
            avatar: true,
          },
        },
        players: {
          include: {
            user: {
              select: {
                id: true,
                username: true,
                avatar: true,
              },
            },
          },
          orderBy: {
            seatOrder: 'asc',
          },
        },
        state: true,
      },
    });

    if (!game) {
      throw new NotFoundException('Игра не найдена');
    }

    const response = this.mapToGameResponse(game);

    // Кешируем результат
    try {
      await this.redis.setJsonex(cacheKey, this.CACHE_TTL, response);
    } catch (error) {
      this.logger.warn(`Game cache write failed for ${gameId}: ${error}`);
    }

    return response;
  }

  /**
   * Проверить доступ пользователя к игре
   * @throws GameAccessDeniedException если пользователь не участвует в игре
   */
  async checkGameAccess(gameId: string, userId: string): Promise<void> {
    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      select: {
        hostId: true,
        opponentId: true,
        status: true,
      },
    });

    if (!game) {
      throw new NotFoundException('Игра не найдена');
    }

    // Для завершённых игр разрешаем просмотр всем
    if (game.status === GameStatus.FINISHED || game.status === GameStatus.ABORTED) {
      return;
    }

    // Для активных игр проверяем участие
    if (game.hostId !== userId && game.opponentId !== userId) {
      throw new GameAccessDeniedException(gameId);
    }
  }

  /**
   * Проверить, что пользователь участвует в игре (строже чем checkGameAccess)
   */
  async requireParticipation(gameId: string, userId: string): Promise<void> {
    const player = await this.prisma.gamePlayer.findUnique({
      where: {
        gameId_userId: { gameId, userId },
      },
    });

    if (!player) {
      throw new GameAccessDeniedException(gameId);
    }
  }

  /**
   * Валидация heroId
   */
  async validateHeroId(heroId: string): Promise<void> {
    if (!heroId) {
      throw new BadRequestException('Hero ID обязателен');
    }

    const hero = await this.prisma.hero.findUnique({
      where: { id: heroId },
    });

    if (!hero) {
      throw new NotFoundException('Герой не найден');
    }
  }

  /**
   * Получить список игр пользователя
   */
  async myGames(
    userId: string,
    filters?: { status?: GameStatus; limit?: number },
  ): Promise<GameResponse[]> {
    // Списки всегда читаются из авторитетного Postgres — list-кеш не читается
    // и не пишется. Сверка элементов кеша с БД не видит появления НОВЫХ членов:
    // пустой закешированный список (например, [] по фильтру FINISHED) считался
    // бы свежим и скрывал только что завершённый матч, если терминальная
    // инвалидация Redis в saveState не прошла. Legacy-инвалидация ключей
    // games:list:* остаётся в saveState/мутациях для старых записей.
    const games = await this.prisma.game.findMany({
      where: {
        OR: [{ hostId: userId }, { opponentId: userId }],
        ...(filters?.status && { status: filters.status }),
      },
      include: {
        host: {
          select: {
            id: true,
            username: true,
            avatar: true,
          },
        },
        opponent: {
          select: {
            id: true,
            username: true,
            avatar: true,
          },
        },
        players: {
          include: {
            user: {
              select: {
                id: true,
                username: true,
                avatar: true,
              },
            },
          },
          orderBy: {
            seatOrder: 'asc',
          },
        },
        state: true,
      },
      orderBy: {
        updatedAt: 'desc',
      },
      take: filters?.limit || 50,
    });

    const response = games.map((g) => this.mapToGameResponse(g));

    return response;
  }

  /**
   * Получить список доступных для присоединения игр
   */
  async availableGames(filters?: { mode?: GameMode; limit?: number }): Promise<GameResponse[]> {
    const cacheKey = `games:available:${filters?.mode || 'all'}`;
    const cached = await this.redis.getJson<GameResponse[]>(cacheKey);
    if (cached) {
      return cached;
    }

    const games = await this.prisma.game.findMany({
      where: {
        status: GameStatus.LOBBY,
        opponentId: null,
        ...(filters?.mode && { mode: filters.mode }),
      },
      include: {
        host: {
          select: {
            id: true,
            username: true,
            avatar: true,
          },
        },
        opponent: {
          select: {
            id: true,
            username: true,
            avatar: true,
          },
        },
        players: {
          include: {
            user: {
              select: {
                id: true,
                username: true,
                avatar: true,
              },
            },
          },
          orderBy: {
            seatOrder: 'asc',
          },
        },
        state: true,
      },
      orderBy: {
        createdAt: 'desc',
      },
      take: filters?.limit || 20,
    });

    const response = games.map((g) => this.mapToGameResponse(g));

    // Кешируем на короткое время
    await this.redis.setJsonex(cacheKey, 30, response);

    return response;
  }

  /**
   * Присоединиться к игре
   */
  async joinGame(gameId: string, userId: string, heroId?: string): Promise<GameResponse> {
    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      include: {
        players: true,
      },
    });

    if (!game) {
      throw new NotFoundException('Игра не найдена');
    }

    // Проверяем статус игры
    if (game.status !== GameStatus.LOBBY && game.status !== GameStatus.PENDING) {
      throw new BadRequestException(
        'Нельзя присоединиться к игре, которая уже началась или завершилась',
      );
    }

    // Проверяем, что пользователь не является хостом
    if (game.hostId === userId) {
      throw new BadRequestException('Вы уже являетесь хостом этой игры');
    }

    // Проверяем, что нет opponent
    if (game.opponentId) {
      // Проверяем, может пользователь уже в игре
      if (game.opponentId === userId) {
        return await this.getGame(gameId);
      }
      throw new BadRequestException('Игра уже заполнена');
    }

    // Проверяем, что пользователь не уже в игре как игрок
    const existingPlayer = game.players.find((p) => p.userId === userId);
    if (existingPlayer) {
      throw new BadRequestException('Вы уже участвуете в этой игре');
    }

    // Присоединяем к игре в транзакции
    await this.prisma.$transaction(async (tx) => {
      // Добавляем как opponent
      await tx.game.update({
        where: { id: gameId },
        data: {
          opponentId: userId,
        },
      });

      // Добавляем запись в GamePlayer
      await tx.gamePlayer.create({
        data: {
          gameId,
          userId,
          heroId,
          seatOrder: 1,
        },
      });
    });

    // Инвалидируем кеш (и списка хоста тоже — иначе он до 60с не видит оппонента)
    await this.invalidateGameCache(gameId);
    await this.invalidateGamesListForBoth(game.hostId, userId);
    await this.invalidateAvailableGamesCache();

    // Журналируем присоединение (state ещё нет — seq 0)
    await this.recordLobbyAction(gameId, userId, GameActionType.GAME_JOINED, 0);

    // Уведомляем подписчиков лобби (хост видит вошедшего без поллинга)
    const joinedUser = await this.prisma.user.findUnique({
      where: { id: userId },
      select: { username: true },
    });
    await this.publishLobby(gameId, 'PLAYER_JOINED', {
      userId,
      username: joinedUser?.username,
    });

    return await this.getGame(gameId);
  }

  /**
   * Покинуть игру
   * - Если хост покидает игру и есть opponent -> opponent становится новым хостом
   * - Если хост покидает игру и opponent нет -> игра удаляется
   * - Если opponent покидает игру -> просто очищается opponentId
   * - Если игра уже началась -> прерывается
   */
  async leaveGame(gameId: string, userId: string): Promise<void> {
    const outcome = await this.prisma.$transaction(async (tx) => {
      // Match startGame's row lock: never remove a roster after the match starts
      // or finishes between an unlocked read and the lobby mutation.
      await tx.$queryRaw`SELECT id FROM "Game" WHERE id = ${gameId} FOR UPDATE`;
      const game = await tx.game.findUnique({
        where: { id: gameId },
        select: { hostId: true, opponentId: true, status: true },
      });
      if (!game) throw new NotFoundException('Игра не найдена');
      if (game.hostId !== userId && game.opponentId !== userId) {
        throw new ForbiddenException('Вы не участвуете в этой игре');
      }

      const participants = { hostId: game.hostId, opponentId: game.opponentId };
      if (game.status === GameStatus.FINISHED || game.status === GameStatus.ABORTED) {
        return { kind: 'terminal' as const, ...participants };
      }
      if (game.status === GameStatus.IN_PROGRESS) {
        return { kind: 'abort' as const, ...participants };
      }

      if (game.hostId === userId) {
        if (game.opponentId) {
          await tx.game.update({
            where: { id: gameId },
            data: { hostId: game.opponentId, opponentId: null },
          });
          await tx.gamePlayer.deleteMany({ where: { gameId, userId } });
          await tx.gamePlayer.updateMany({
            where: { gameId, userId: game.opponentId },
            data: { seatOrder: 0 },
          });
        } else {
          await tx.gamePlayer.deleteMany({ where: { gameId } });
          await tx.game.delete({ where: { id: gameId } });
        }
      } else {
        await tx.game.update({ where: { id: gameId }, data: { opponentId: null } });
        await tx.gamePlayer.deleteMany({ where: { gameId, userId } });
      }
      return { kind: 'left' as const, ...participants };
    });

    // Leaving a terminal game only navigates the client away; its result and
    // both seats remain available for history and recovery.
    if (outcome.kind === 'terminal') return;
    if (outcome.kind === 'abort') {
      try {
        await this.abortGame(gameId, userId, 'player_left');
      } catch (error) {
        // A finishing action may win after we release the row lock.
        if (!(error instanceof BadRequestException)) throw error;
        const current = await this.prisma.game.findUnique({ where: { id: gameId } });
        if (current?.status !== GameStatus.FINISHED && current?.status !== GameStatus.ABORTED) {
          throw error;
        }
      }
      return;
    }

    await this.invalidateGameCache(gameId);
    await this.invalidateGamesListForBoth(outcome.hostId, outcome.opponentId);
    await this.invalidateAvailableGamesCache();

    // Уведомляем оставшегося подписчика лобби
    await this.publishLobby(gameId, 'PLAYER_LEFT', { userId });
  }

  /**
   * Начать игру
   */
  async startGame(gameId: string, userId: string): Promise<GameResponse> {
    let game = await this.prisma.game.findUnique({
      where: { id: gameId },
      include: {
        players: true,
      },
    });

    if (!game) {
      throw new NotFoundException('Игра не найдена');
    }

    // Только хост может начать игру
    if (game.hostId !== userId) {
      throw new ForbiddenException('Только хост может начать игру');
    }

    // Проверяем статус
    if (game.status !== GameStatus.LOBBY) {
      throw new BadRequestException('Игру можно начать только из лобби');
    }

    // VS_AI: автодобавление бота вторым игроком (выбор героя + ready) перед стартом
    if (game.mode === GameMode.VS_AI && !game.opponentId) {
      await this.setupAiOpponent(gameId);
      game = await this.prisma.game.findUnique({
        where: { id: gameId },
        include: { players: true },
      });
      if (!game) throw new NotFoundException('Игра не найдена');
    }

    // Проверяем наличие opponent для режимов с несколькими игроками
    if (game.mode !== GameMode.VS_AI && !game.opponentId) {
      throw new BadRequestException('Для начала игры нужен opponent');
    }

    // Проверяем, что все игроки готовы
    const allReady = game.players.every((p) => p.isReady);
    if (!allReady) {
      throw new BadRequestException('Не все игроки готовы');
    }

    // GD-016: страховка от гонки выбора — матч не стартует с дубликатом героя
    const heroIds = game.players.map((p) => p.heroId);
    if (heroIds.some((id) => !id)) {
      throw new BadRequestException('Каждый игрок должен выбрать героя');
    }
    if (new Set(heroIds).size !== heroIds.length) {
      throw new BadRequestException('Два игрока не могут играть одного героя');
    }

    // Атомарный LOBBY→IN_PROGRESS переход: строка игры лочится FOR UPDATE,
    // статус/готовность/состав перепроверяются по данным ПОД локом —
    // конкурентный selectHero (или второй startGame) сериализуется с этим
    // блоком, стартовавший матч уже не мутируется выбором героя.
    await this.prisma.$transaction(async (tx) => {
      await tx.$queryRaw`SELECT id FROM "Game" WHERE id = ${gameId} FOR UPDATE`;
      const locked = await tx.game.findUnique({
        where: { id: gameId },
        select: { status: true },
      });
      if (!locked || locked.status !== GameStatus.LOBBY) {
        throw new BadRequestException('Игру можно начать только из лобби');
      }
      const roster = await tx.gamePlayer.findMany({
        where: { gameId },
        orderBy: { seatOrder: 'asc' },
      });
      if (!roster.every((p) => p.isReady)) {
        throw new BadRequestException('Не все игроки готовы');
      }
      const lockedHeroIds = roster.map((p) => p.heroId);
      if (lockedHeroIds.some((id) => !id)) {
        throw new BadRequestException('Каждый игрок должен выбрать героя');
      }
      if (new Set(lockedHeroIds).size !== lockedHeroIds.length) {
        throw new BadRequestException('Два игрока не могут играть одного героя');
      }
      await tx.game.update({
        where: { id: gameId },
        data: {
          status: GameStatus.IN_PROGRESS,
          startedAt: new Date(),
        },
      });
    });

    // Создаём начальное игровое состояние (бойцы, колоды, руки).
    // При ошибке откатываем статус, чтобы лобби осталось рабочим.
    try {
      await this.gameInitialization.initializeGameState(gameId);
    } catch (error) {
      // Initialization can lose a race to abort/finish. Only roll back the
      // IN_PROGRESS transition that still belongs to this start attempt.
      const rollback = await this.prisma.game.updateMany({
        where: { id: gameId, status: GameStatus.IN_PROGRESS },
        data: { status: GameStatus.LOBBY, startedAt: null },
      });
      if (rollback.count === 1) await this.invalidateGameCache(gameId);
      throw error instanceof BadRequestException
        ? error
        : new BadRequestException(
            `Не удалось инициализировать состояние игры: ${(error as Error).message}`,
          );
    }

    // Инвалидируем кеш (списки обоих участников — у оппонента игра тоже должна стать IN_PROGRESS)
    await this.invalidateGameCache(gameId);
    await this.invalidateGamesListForBoth(game.hostId, game.opponentId);
    await this.invalidateAvailableGamesCache();

    // Журналируем старт игры (createInitialState ставит sequenceNumber: 1)
    await this.recordLobbyAction(gameId, userId, GameActionType.GAME_STARTED, 1);

    // GD-039 (ACC-019): бот должен уметь стартовать с любого сидa — если
    // первым ходит бот (или его ждёт обязательный выбор), дрейним немедленно.
    // Fire-and-forget: no-op, когда ход человека.
    if (game.mode === GameMode.VS_AI) {
      void this.aiTurnService?.maybeRunAiTurns(gameId).catch((e) =>
        this.logger.warn(`AI turn error after start (${gameId}): ${e}`),
      );
    }

    return await this.getGame(gameId);
  }

  /**
   * id системного юзера-бота (VS_AI). Кэшируется. Бот должен быть засеян
   * (prisma/seed-ai.ts) — иначе VS_AI-игру нельзя начать.
   */
  private async getAiUserId(): Promise<string> {
    if (this.aiUserIdCache) return this.aiUserIdCache;
    const ai = await this.prisma.user.findUnique({
      where: { email: this.AI_USER_EMAIL },
      select: { id: true },
    });
    if (!ai) {
      throw new BadRequestException(
        `ИИ-оппонент не сидирован (${this.AI_USER_EMAIL}) — запустите prisma/seed-ai.ts`,
      );
    }
    this.aiUserIdCache = ai.id;
    return ai.id;
  }

  /**
   * VS_AI: добавляет бота вторым игроком — opponentId + GamePlayer(seat 1) с
   * сильнейшим героем (только из героев с картами, иначе колода пустая) и
   * isReady=true. «Сильнейший» = максимальный health; тай-брейк среди равных
   * по health — произвольный (первый по итерации). Идемпотентно: если бот уже
   * игрок — ничего не делает.
   */
  private async setupAiOpponent(gameId: string): Promise<void> {
    const aiUserId = await this.getAiUserId();

    const existing = await this.prisma.gamePlayer.findFirst({
      where: { gameId, userId: aiUserId },
      select: { id: true },
    });
    if (existing) return;

    const allHeroes = await this.prisma.hero.findMany({
      where: { cards: { some: {} } },
      select: { id: true, health: true },
    });
    // DE-027 spike (review IMPL 2026-10-05): the human's hero is excluded, otherwise
    // startGame rejects the room ("Два игрока не могут играть одного героя") whenever
    // the human picked the strongest hero.
    const seated = await this.prisma.gamePlayer.findMany({
      where: { gameId },
      select: { userId: true, heroId: true },
    });
    const taken = new Set(
      seated.filter((p) => p.userId !== aiUserId && p.heroId).map((p) => p.heroId as string),
    );
    const heroes = allHeroes.filter((h) => !taken.has(h.id));
    if (heroes.length === 0) {
      throw new BadRequestException('Нет героев с картами для ИИ-оппонента');
    }
    // Сильнейший по health среди свободных; при равенстве — первый (тай-брейк произвольный).
    const heroId = heroes.reduce((best, h) => ((h.health ?? 0) > (best.health ?? 0) ? h : best)).id;

    await this.prisma.$transaction(async (tx) => {
      await tx.game.update({ where: { id: gameId }, data: { opponentId: aiUserId } });
      await tx.gamePlayer.create({
        data: { gameId, userId: aiUserId, heroId, seatOrder: 1, isReady: true },
      });
    });

    this.logger.log(`VS_AI: бот добавлен в игру ${gameId} (hero ${heroId})`);
  }

  /**
   * Прервать игру
   */
  async abortGame(gameId: string, userId: string, reason = 'aborted'): Promise<GameResponse> {
    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
    });

    if (!game) {
      throw new NotFoundException('Игра не найдена');
    }

    // Только хост или текущий игрок могут прервать игру
    if (game.hostId !== userId && game.opponentId !== userId) {
      throw new ForbiddenException('Вы не можете прервать эту игру');
    }

    if (game.status === GameStatus.FINISHED || game.status === GameStatus.ABORTED) {
      throw new BadRequestException('Завершённую игру нельзя прервать');
    }

    // A conditional write serializes with saveState's FINISHED transition.
    // A stale read cannot overwrite a result committed by another request.
    const transition = await this.prisma.game.updateMany({
      where: {
        id: gameId,
        status: { in: [GameStatus.PENDING, GameStatus.LOBBY, GameStatus.IN_PROGRESS, GameStatus.PAUSED] },
      },
      data: {
        status: GameStatus.ABORTED,
        endedAt: new Date(),
      },
    });
    if (transition.count !== 1) {
      throw new BadRequestException('Завершённую игру нельзя прервать');
    }

    // Инвалидируем кеш (включая списки игр обоих участников — иначе myGames до 60с отдаёт stale статус)
    const invalidations = await Promise.allSettled([
      this.invalidateGameCache(gameId),
      this.redis.del(`gamestate:${gameId}`),
      this.invalidateGamesListForBoth(game.hostId, game.opponentId),
      this.invalidateAvailableGamesCache(),
    ]);
    for (const result of invalidations) {
      if (result.status === 'rejected') {
        this.logger.warn(`Game cache invalidation failed after abort: ${result.reason}`);
      }
    }

    // Журналируем прерывание игры с текущим sequence number состояния (если есть)
    let abortSeq = 0;
    try {
      abortSeq = (
        await this.prisma.gameState.findUnique({
          where: { gameId },
          select: { sequenceNumber: true },
        })
      )?.sequenceNumber ?? 0;
    } catch (error) {
      this.logger.warn(`Could not read abort sequence for ${gameId}: ${error}`);
    }
    await this.recordLobbyAction(gameId, userId, GameActionType.GAME_ABORTED, abortSeq, {
      reason,
    });

    // Уведомляем подписчиков gameEnded (прерывание = конец игры без победителя)
    await this.publishLobby(gameId, 'GAME_ENDED', { reason, abortedBy: userId });

    return await this.getGame(gameId, true);
  }

  /**
   * Обновить готовность игрока
   */
  async toggleReady(gameId: string, userId: string): Promise<GameResponse> {
    const player = await this.prisma.gamePlayer.findUnique({
      where: {
        gameId_userId: {
          gameId,
          userId,
        },
      },
    });

    if (!player) {
      throw new NotFoundException('Вы не участвуете в этой игре');
    }

    await this.prisma.gamePlayer.update({
      where: { id: player.id },
      data: {
        isReady: !player.isReady,
      },
    });

    await this.invalidateGameCache(gameId);

    return await this.getGame(gameId);
  }

  /**
   * Выбрать героя
   */
  async selectHero(gameId: string, userId: string, heroId: string): Promise<GameResponse> {
    // Валидируем heroId
    await this.validateHeroId(heroId);

    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
    });

    if (!game) {
      throw new NotFoundException('Игра не найдена');
    }

    if (game.status !== GameStatus.LOBBY) {
      throw new BadRequestException('Героя можно выбрать только в лобби');
    }

    const player = await this.prisma.gamePlayer.findUnique({
      where: {
        gameId_userId: {
          gameId,
          userId,
        },
      },
    });

    if (!player) {
      throw new NotFoundException('Вы не участвуете в этой игре');
    }

    // GD-016: состав без дубликатов — проверка и запись атомарны в транзакции.
    // Строка игры лочится SELECT … FOR UPDATE: конкурентные selectHero и
    // startGame одной игры сериализуются (READ COMMITTED достаточно —
    // check-then-act целиком под локом), иначе две транзакции читают ростер
    // до коммита соперника и оба выбора проходят.
    await this.prisma.$transaction(async (tx) => {
      await tx.$queryRaw`SELECT id FROM "Game" WHERE id = ${gameId} FOR UPDATE`;
      const locked = await tx.game.findUnique({
        where: { id: gameId },
        select: { status: true },
      });
      if (!locked || locked.status !== GameStatus.LOBBY) {
        throw new BadRequestException('Героя можно выбрать только в лобби');
      }
      const roster = await tx.gamePlayer.findMany({ where: { gameId } });
      const rival = roster.find((p) => p.userId !== userId && p.heroId === heroId);
      if (rival) {
        throw new BadRequestException('Герой уже выбран другим игроком этой игры');
      }
      await tx.gamePlayer.update({
        where: { id: player.id },
        data: { heroId },
      });
    });

    await this.invalidateGameCache(gameId);

    return await this.getGame(gameId);
  }

  /**
   * Инвалидация кеша игры
   */
  private async invalidateGameCache(gameId: string): Promise<void> {
    await this.redis.del(`${this.GAME_CACHE_PREFIX}${gameId}`);
  }

  /**
   * Инвалидация кеша списка игр пользователя
   */
  private async invalidateGamesListCache(userId: string): Promise<void> {
    await this.redis.del(`${this.GAMES_LIST_CACHE_PREFIX}${userId}:PENDING`);
    await this.redis.del(`${this.GAMES_LIST_CACHE_PREFIX}${userId}:LOBBY`);
    await this.redis.del(`${this.GAMES_LIST_CACHE_PREFIX}${userId}:IN_PROGRESS`);
    await this.redis.del(`${this.GAMES_LIST_CACHE_PREFIX}${userId}:FINISHED`);
    await this.redis.del(`${this.GAMES_LIST_CACHE_PREFIX}${userId}:ABORTED`);
    await this.redis.del(`${this.GAMES_LIST_CACHE_PREFIX}${userId}:all`);
  }

  /**
   * Инвалидация кеша списков игр обоих участников (хост + оппонент, если есть)
   */
  private async invalidateGamesListForBoth(
    hostId: string,
    opponentId: string | null,
  ): Promise<void> {
    await this.invalidateGamesListCache(hostId);
    if (opponentId && opponentId !== hostId) {
      await this.invalidateGamesListCache(opponentId);
    }
  }

  /**
   * Инвалидация кеша доступных игр
   */
  private async invalidateAvailableGamesCache(): Promise<void> {
    await this.redis.del('games:available:ONE_V_ONE');
    await this.redis.del('games:available:TWO_V_TWO');
    await this.redis.del('games:available:FREE_FOR_ALL');
    await this.redis.del('games:available:VS_AI');
    await this.redis.del('games:available:all');
  }

  /**
   * Маппинг Prisma модели в Response DTO
   */
  private mapToGameResponse(game: any): GameResponse {
    return {
      id: game.id,
      code: game.code,
      status: game.status as GameStatus,
      mode: game.mode as GameMode,
      hostId: game.hostId,
      host: {
        id: game.host.id,
        userId: game.host.id,
        username: game.host.username,
        avatar: game.host.avatar,
        isReady: game.players.find((p: any) => p.userId === game.hostId)?.isReady ?? false,
        hasPassed: false,
        seatOrder: 0,
        heroId: game.players.find((p: any) => p.userId === game.hostId)?.heroId ?? null,
      },
      opponentId: game.opponentId,
      opponent: game.opponent
        ? {
            id: game.opponent.id,
            userId: game.opponent.id,
            username: game.opponent.username,
            avatar: game.opponent.avatar,
            isReady: game.players.find((p: any) => p.userId === game.opponentId)?.isReady ?? false,
            hasPassed: false,
            seatOrder: 1,
            heroId: game.players.find((p: any) => p.userId === game.opponentId)?.heroId ?? null,
          }
        : null,
      boardId: game.boardId,
      boardState: game.boardState,
      createdAt: game.createdAt,
      updatedAt: game.updatedAt,
      startedAt: game.startedAt,
      endedAt: game.endedAt,
      winnerId: game.winnerId,
      version: game.version,
      players: game.players.map((p: any) => ({
        id: p.id,
        userId: p.user.id,
        username: p.user.username,
        avatar: p.user.avatar,
        heroId: p.heroId,
        isReady: p.isReady,
        hasPassed: p.hasPassed,
        seatOrder: p.seatOrder,
      })),
      phase: game.state?.phase ? game.state.phase : null,
      currentTurn: game.state?.turnCount ?? null,
    };
  }
}
