import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';
import { QueueManagerService } from '../matchmaking/services/queue-manager.service';
import {
  CreateHeroInput,
  UpdateHeroInput,
  CreateCardInput,
  UpdateCardInput,
  CreateBoardInput,
  UpdateBoardInput,
  UpdateUserInput,
  AdminStatsDto,
  ImportResultDto,
} from './dto/admin.dto';
import { GameMode, GameStatus, UserRole } from '@prisma/client';

/**
 * Admin Service
 * Handles CRUD operations for admin panel
 */
@Injectable()
export class AdminService {
  // JSON-поля моделей, сериализуемые в строки для GraphQL
  private static readonly HERO_JSON_FIELDS = [
    'ability',
    'deckCards',
    'properties',
    'sidekicks',
    'additionalMinis',
  ];
  private static readonly CARD_JSON_FIELDS = ['effects'];
  private static readonly BOARD_JSON_FIELDS = ['cells', 'features'];

  // Whitelist полей сортировки (реальные колонки моделей)
  private static readonly HERO_SORT_FIELDS = [
    'createdAt',
    'updatedAt',
    'name',
    'nameEn',
    'nameRu',
    'set',
    'health',
    'fighterType',
    'movement',
  ];
  private static readonly CARD_SORT_FIELDS = [
    'createdAt',
    'updatedAt',
    'name',
    'nameEn',
    'nameRu',
    'cardType',
    'subType',
    'attackValue',
    'defenseValue',
    'boostValue',
    'count',
  ];
  private static readonly BOARD_SORT_FIELDS = [
    'createdAt',
    'updatedAt',
    'name',
    'nameEn',
    'nameRu',
    'set',
    'width',
    'height',
  ];
  private static readonly USER_SORT_FIELDS = [
    'createdAt',
    'updatedAt',
    'username',
    'email',
    'role',
  ];
  private static readonly GAME_SORT_FIELDS = ['createdAt', 'status', 'code', 'mode'];

  constructor(
    private readonly prisma: PrismaService,
    private readonly queueManager: QueueManagerService,
  ) {}

  // ============================================
  // HELPERS
  // ============================================

  private serializeJsonFields<T extends Record<string, any>>(
    entity: T,
    fields: string[],
  ): T {
    const result: Record<string, any> = { ...entity };
    for (const field of fields) {
      if (!(field in result)) continue;
      const value = result[field];
      if (value === null || value === undefined) {
        result[field] = null;
      } else if (typeof value !== 'string') {
        result[field] = JSON.stringify(value);
      }
    }
    return result as T;
  }

  private serializeHero<T extends Record<string, any>>(hero: T): T {
    const result: Record<string, any> = this.serializeJsonFields(
      hero,
      AdminService.HERO_JSON_FIELDS,
    );
    if (Array.isArray(result.cards)) {
      result.cards = result.cards.map((card: Record<string, any>) =>
        this.serializeCard(card),
      );
    }
    return result as T;
  }

  private serializeCard<T extends Record<string, any>>(card: T): T {
    return this.serializeJsonFields(card, AdminService.CARD_JSON_FIELDS);
  }

  private serializeBoard<T extends Record<string, any>>(board: T): T {
    return this.serializeJsonFields(board, AdminService.BOARD_JSON_FIELDS);
  }

  private safeSort(
    sortBy: string | undefined,
    allowed: string[],
    fallback = 'createdAt',
  ): string {
    return sortBy && allowed.includes(sortBy) ? sortBy : fallback;
  }

  private buildOrderBy(
    sortBy: string | undefined,
    sortOrder: 'asc' | 'desc' | undefined,
    allowed: string[],
  ): Record<string, 'asc' | 'desc'> {
    if (!sortBy) {
      return { createdAt: 'desc' };
    }
    return {
      [this.safeSort(sortBy, allowed)]: sortOrder === 'desc' ? 'desc' : 'asc',
    };
  }

  // ============================================
  // STATS
  // ============================================

  async getStats(): Promise<AdminStatsDto> {
    const [totalUsers, totalHeroes, totalCards, totalBoards, totalGames] =
      await Promise.all([
        this.prisma.user.count(),
        this.prisma.hero.count(),
        this.prisma.card.count(),
        this.prisma.board.count(),
        this.prisma.game.count(),
      ]);

    return {
      totalUsers,
      totalHeroes,
      totalCards,
      totalBoards,
      totalGames,
    };
  }

  // ============================================
  // HEROES CRUD
  // ============================================

  async getHero(id: string) {
    const hero = await this.prisma.hero.findUnique({
      where: { id },
      include: {
        cards: true,  // Включаем связанные карты
      },
    });

    if (!hero) {
      throw new NotFoundException('Герой не найден');
    }

    // Преобразуем JSON-поля в строки для GraphQL
    return this.serializeHero(hero);
  }

  async createHero(input: CreateHeroInput) {
    try {
      const hero = await this.prisma.hero.create({
        data: {
          name: input.name,
          nameEn: input.nameEn,
          nameRu: input.nameRu,
          set: input.set,
          health: input.health,
          fighterType: input.fighterType,
          movement: input.movement ?? 2,
          color: input.color,
          ability: input.ability ? JSON.parse(input.ability) : null,
          deckCards: input.deckCards ? JSON.parse(input.deckCards) : [],
          properties: input.properties ? JSON.parse(input.properties) : null,
          hasTokens: input.hasTokens ?? false,
          sidekicks: input.sidekicks ? JSON.parse(input.sidekicks) : null,
          additionalMinis: input.additionalMinis ? JSON.parse(input.additionalMinis) : null,
          imageUrl: input.imageUrl,
          avatarUrl: input.avatarUrl,
          characterCardUrl: input.characterCardUrl,
          miniModelUrl: input.miniModelUrl,
        },
      });
      return this.serializeHero(hero);
    } catch (error) {
      if (error.code === 'P2002') {
        throw new ConflictException('Герой с таким именем уже существует');
      }
      throw error;
    }
  }

  async updateHero(id: string, input: UpdateHeroInput) {
    const hero = await this.prisma.hero.findUnique({
      where: { id },
    });

    if (!hero) {
      throw new NotFoundException('Герой не найден');
    }

    const updateData: any = {};

    if (input.name !== undefined) updateData.name = input.name;
    if (input.nameEn !== undefined) updateData.nameEn = input.nameEn;
    if (input.nameRu !== undefined) updateData.nameRu = input.nameRu;
    if (input.set !== undefined) updateData.set = input.set;
    if (input.health !== undefined) updateData.health = input.health;
    if (input.fighterType !== undefined) updateData.fighterType = input.fighterType;
    if (input.movement !== undefined) updateData.movement = input.movement;
    if (input.color !== undefined) updateData.color = input.color;
    if (input.ability !== undefined) updateData.ability = JSON.parse(input.ability);
    if (input.deckCards !== undefined) updateData.deckCards = JSON.parse(input.deckCards);
    if (input.properties !== undefined)
      updateData.properties = JSON.parse(input.properties);
    if (input.hasTokens !== undefined) updateData.hasTokens = input.hasTokens;
    if (input.sidekicks !== undefined) updateData.sidekicks = JSON.parse(input.sidekicks);
    if (input.additionalMinis !== undefined) updateData.additionalMinis = JSON.parse(input.additionalMinis);
    if (input.imageUrl !== undefined) updateData.imageUrl = input.imageUrl;
    if (input.avatarUrl !== undefined) updateData.avatarUrl = input.avatarUrl;
    if (input.characterCardUrl !== undefined) updateData.characterCardUrl = input.characterCardUrl;
    if (input.miniModelUrl !== undefined) updateData.miniModelUrl = input.miniModelUrl;

    const updated = await this.prisma.hero.update({
      where: { id },
      data: updateData,
    });

    return this.serializeHero(updated);
  }

  async deleteHero(id: string): Promise<boolean> {
    const hero = await this.prisma.hero.findUnique({
      where: { id },
      include: { cards: true },
    });

    if (!hero) {
      throw new NotFoundException('Герой не найден');
    }

    // Удаляем связанные карты
    await this.prisma.card.deleteMany({
      where: { heroId: id },
    });

    // Удаляем героя
    await this.prisma.hero.delete({
      where: { id },
    });

    return true;
  }

  // ============================================
  // CARDS CRUD
  // ============================================

  async getCard(id: string) {
    const card = await this.prisma.card.findUnique({
      where: { id },
    });

    if (!card) {
      throw new NotFoundException('Карта не найдена');
    }

    // Преобразуем JSON-поля в строки для GraphQL
    return this.serializeCard(card);
  }

  async createCard(input: CreateCardInput) {
    // Проверяем существование героя
    const hero = await this.prisma.hero.findUnique({
      where: { id: input.heroId },
    });

    if (!hero) {
      throw new NotFoundException('Герой не найден');
    }

    const card = await this.prisma.card.create({
      data: {
        name: input.name,
        nameEn: input.nameEn,
        nameRu: input.nameRu,
        heroId: input.heroId,
        cardType: input.cardType,
        subType: input.subType,
        attackValue: input.attackValue,
        defenseValue: input.defenseValue,
        boostValue: input.boostValue,
        bannerName: input.bannerName,
        effects: input.effects ? JSON.parse(input.effects) : [],
        text: input.text,
        textEn: input.textEn,
        textRu: input.textRu,
        effectAfter: input.effectAfter,
        effectDuring: input.effectDuring,
        effectBoost: input.effectBoost,
        effectImmediately: input.effectImmediately,
        effectOngoing: input.effectOngoing,
        count: input.count ?? 1,
      },
    });

    return this.serializeCard(card);
  }

  async updateCard(id: string, input: UpdateCardInput) {
    const card = await this.prisma.card.findUnique({
      where: { id },
    });

    if (!card) {
      throw new NotFoundException('Карта не найдена');
    }

    const updateData: any = {};

    if (input.heroId !== undefined) {
      const hero = await this.prisma.hero.findUnique({
        where: { id: input.heroId },
      });

      if (!hero) {
        throw new NotFoundException('Герой не найден');
      }

      updateData.heroId = input.heroId;
    }

    if (input.name !== undefined) updateData.name = input.name;
    if (input.nameEn !== undefined) updateData.nameEn = input.nameEn;
    if (input.nameRu !== undefined) updateData.nameRu = input.nameRu;
    if (input.cardType !== undefined) updateData.cardType = input.cardType;
    if (input.subType !== undefined) updateData.subType = input.subType;
    if (input.attackValue !== undefined) updateData.attackValue = input.attackValue;
    if (input.defenseValue !== undefined) updateData.defenseValue = input.defenseValue;
    if (input.boostValue !== undefined) updateData.boostValue = input.boostValue;
    if (input.bannerName !== undefined) updateData.bannerName = input.bannerName;
    if (input.effects !== undefined) updateData.effects = JSON.parse(input.effects);
    if (input.text !== undefined) updateData.text = input.text;
    if (input.textEn !== undefined) updateData.textEn = input.textEn;
    if (input.textRu !== undefined) updateData.textRu = input.textRu;
    if (input.effectAfter !== undefined) updateData.effectAfter = input.effectAfter;
    if (input.effectDuring !== undefined) updateData.effectDuring = input.effectDuring;
    if (input.effectBoost !== undefined) updateData.effectBoost = input.effectBoost;
    if (input.effectImmediately !== undefined) updateData.effectImmediately = input.effectImmediately;
    if (input.effectOngoing !== undefined) updateData.effectOngoing = input.effectOngoing;
    if (input.count !== undefined) updateData.count = input.count;
    if (input.imageUrl !== undefined) updateData.imageUrl = input.imageUrl;
    if (input.imageUrlRu !== undefined) updateData.imageUrlRu = input.imageUrlRu;

    const updated = await this.prisma.card.update({
      where: { id },
      data: updateData,
    });

    return this.serializeCard(updated);
  }

  async deleteCard(id: string): Promise<boolean> {
    const card = await this.prisma.card.findUnique({
      where: { id },
    });

    if (!card) {
      throw new NotFoundException('Карта не найдена');
    }

    await this.prisma.card.delete({
      where: { id },
    });

    return true;
  }

  // ============================================
  // BOARDS CRUD
  // ============================================

  async getBoard(id: string) {
    const board = await this.prisma.board.findUnique({
      where: { id },
    });

    if (!board) {
      throw new NotFoundException('Доска не найдена');
    }

    // Преобразуем JSON-поля в строки для GraphQL
    return this.serializeBoard(board);
  }

  async createBoard(input: CreateBoardInput) {
    try {
      const board = await this.prisma.board.create({
        data: {
          name: input.name,
          nameEn: input.nameEn,
          nameRu: input.nameRu,
          set: input.set,
          width: input.width,
          height: input.height,
          cells: JSON.parse(input.cells),
          features: input.features ? JSON.parse(input.features) : null,
          imageUrl: input.imageUrl,
          imageUrlDark: input.imageUrlDark,
        },
      });
      return this.serializeBoard(board);
    } catch (error) {
      if (error.code === 'P2002') {
        throw new ConflictException('Доска с таким именем уже существует');
      }
      throw error;
    }
  }

  async updateBoard(id: string, input: UpdateBoardInput) {
    const board = await this.prisma.board.findUnique({
      where: { id },
    });

    if (!board) {
      throw new NotFoundException('Доска не найдена');
    }

    const updateData: any = {};

    if (input.name !== undefined) updateData.name = input.name;
    if (input.nameEn !== undefined) updateData.nameEn = input.nameEn;
    if (input.nameRu !== undefined) updateData.nameRu = input.nameRu;
    if (input.set !== undefined) updateData.set = input.set;
    if (input.width !== undefined) updateData.width = input.width;
    if (input.height !== undefined) updateData.height = input.height;
    if (input.cells !== undefined) updateData.cells = JSON.parse(input.cells);
    if (input.features !== undefined) updateData.features = JSON.parse(input.features);
    if (input.imageUrl !== undefined) updateData.imageUrl = input.imageUrl;
    if (input.imageUrlDark !== undefined) updateData.imageUrlDark = input.imageUrlDark;

    const updated = await this.prisma.board.update({
      where: { id },
      data: updateData,
    });

    return this.serializeBoard(updated);
  }

  async deleteBoard(id: string): Promise<boolean> {
    const board = await this.prisma.board.findUnique({
      where: { id },
    });

    if (!board) {
      throw new NotFoundException('Доска не найдена');
    }

    await this.prisma.board.delete({
      where: { id },
    });

    return true;
  }

  // ============================================
  // USERS CRUD
  // ============================================

  async getUser(id: string) {
    const user = await this.prisma.user.findUnique({
      where: { id },
      select: {
        id: true,
        email: true,
        username: true,
        avatar: true,
        role: true,
        createdAt: true,
        updatedAt: true,
        deletedAt: true,
        emailVerified: true,
        stats: {
          select: {
            gamesPlayed: true,
            gamesWon: true,
            currentElo: true,
          },
        },
      },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

    return user;
  }

  async getUsers(
    page: number = 1,
    limit: number = 20,
    search?: string,
    sortBy?: string,
    sortOrder?: 'asc' | 'desc',
  ) {
    const where = search
      ? {
          OR: [
            { email: { contains: search, mode: 'insensitive' as const } },
            { username: { contains: search, mode: 'insensitive' as const } },
          ],
        }
      : {};

    const orderBy = this.buildOrderBy(sortBy, sortOrder, AdminService.USER_SORT_FIELDS);

    const [users, total] = await Promise.all([
      this.prisma.user.findMany({
        where,
        skip: (page - 1) * limit,
        take: limit,
        orderBy,
        select: {
          id: true,
          email: true,
          username: true,
          avatar: true,
          role: true,
          createdAt: true,
          updatedAt: true,
          deletedAt: true,
          emailVerified: true,
          stats: {
            select: {
              gamesPlayed: true,
              gamesWon: true,
              currentElo: true,
            },
          },
        },
      }),
      this.prisma.user.count({ where }),
    ]);

    return {
      users,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  async updateUser(id: string, input: UpdateUserInput) {
    const user = await this.prisma.user.findUnique({
      where: { id },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

    const updateData: any = {};

    if (input.username !== undefined) updateData.username = input.username;
    if (input.avatar !== undefined) updateData.avatar = input.avatar;
    if (input.email !== undefined) updateData.email = input.email;
    if (input.role !== undefined) updateData.role = input.role;

    return await this.prisma.user.update({
      where: { id },
      data: updateData,
      select: {
        id: true,
        email: true,
        username: true,
        avatar: true,
        role: true,
        createdAt: true,
        updatedAt: true,
        deletedAt: true,
        emailVerified: true,
      },
    });
  }

  async banUser(id: string): Promise<boolean> {
    const user = await this.prisma.user.findUnique({
      where: { id },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

    // Soft delete = бан
    await this.prisma.user.update({
      where: { id },
      data: { deletedAt: new Date() },
    });

    return true;
  }

  async unbanUser(id: string): Promise<boolean> {
    const user = await this.prisma.user.findUnique({
      where: { id },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

    await this.prisma.user.update({
      where: { id },
      data: { deletedAt: null },
    });

    return true;
  }

  // ============================================
  // CARDS LIST
  // ============================================

  async getAllCards(
    page: number = 1,
    limit: number = 20,
    heroId?: string,
    search?: string,
    sortBy?: string,
    sortOrder?: 'asc' | 'desc',
  ) {
    const where: any = {};
    if (heroId) where.heroId = heroId;
    if (search) {
      where.OR = [
        { name: { contains: search, mode: 'insensitive' as const } },
        { nameEn: { contains: search, mode: 'insensitive' as const } },
        { nameRu: { contains: search, mode: 'insensitive' as const } },
      ];
    }

    const orderBy = this.buildOrderBy(sortBy, sortOrder, AdminService.CARD_SORT_FIELDS);

    const [cards, total] = await Promise.all([
      this.prisma.card.findMany({
        where,
        skip: (page - 1) * limit,
        take: limit,
        orderBy,
        select: {
          id: true,
          name: true,
          nameEn: true,
          nameRu: true,
          cardType: true,
          subType: true,
          attackValue: true,
          defenseValue: true,
          boostValue: true,
          bannerName: true,
          count: true,
          heroId: true,
          imageUrl: true,
          imageUrlRu: true,
          createdAt: true,
        },
      }),
      this.prisma.card.count({ where }),
    ]);

    return {
      items: cards.map((card) => this.serializeCard(card)),
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  // ============================================
  // GAMES LIST
  // ============================================

  async getAllGames(
    page: number = 1,
    limit: number = 20,
    search?: string,
    sortBy?: string,
    sortOrder?: 'asc' | 'desc',
  ) {
    const where: any = {};
    if (search) {
      const searchConditions: any[] = [
        { id: { contains: search, mode: 'insensitive' as const } },
        { code: { contains: search, mode: 'insensitive' as const } },
      ];
      // status — enum, contains по нему роняет запрос; ищем точным совпадением
      const statusCandidate = search.toUpperCase();
      if ((Object.values(GameStatus) as string[]).includes(statusCandidate)) {
        searchConditions.push({ status: statusCandidate as GameStatus });
      }
      where.OR = searchConditions;
    }

    const orderBy = this.buildOrderBy(sortBy, sortOrder, AdminService.GAME_SORT_FIELDS);

    const [games, total] = await Promise.all([
      this.prisma.game.findMany({
        where,
        skip: (page - 1) * limit,
        take: limit,
        orderBy,
        include: {
          host: {
            select: { id: true, username: true, avatar: true },
          },
          opponent: {
            select: { id: true, username: true, avatar: true },
          },
        },
      }),
      this.prisma.game.count({ where }),
    ]);

    // Get game players and board names for each game
    const gameIds = games.map((g) => g.id);
    const boardIds = [...new Set(games.map((g) => g.boardId))];
    const [gamePlayers, boards] = await Promise.all([
      this.prisma.gamePlayer.findMany({
        where: { gameId: { in: gameIds } },
        include: {
          user: { select: { id: true, username: true, avatar: true } },
        },
      }),
      this.prisma.board.findMany({
        where: { id: { in: boardIds } },
        select: { id: true, name: true },
      }),
    ]);

    const boardNameById = new Map(boards.map((b) => [b.id, b.name]));

    const items = games.map((game) => {
      const players = gamePlayers.filter((gp) => gp.gameId === game.id);
      return {
        id: game.id,
        code: game.code,
        mode: game.mode,
        status: game.status,
        createdAt: game.createdAt,
        boardId: game.boardId,
        boardName: boardNameById.get(game.boardId) ?? null,
        gamePlayers: players.map((gp) => ({
          id: gp.id,
          playerId: gp.userId,
          heroId: gp.heroId || undefined,
          status: gp.isReady ? 'READY' : 'PENDING',
          username: gp.user?.username,
          avatar: gp.user?.avatar,
        })),
      };
    });

    return {
      items,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  async getGameById(id: string) {
    const game = await this.prisma.game.findUnique({
      where: { id },
    });

    if (!game) {
      throw new NotFoundException('Игра не найдена');
    }

    const [gamePlayers, board] = await Promise.all([
      this.prisma.gamePlayer.findMany({
        where: { gameId: id },
        include: {
          user: { select: { id: true, username: true, avatar: true } },
        },
      }),
      this.prisma.board.findUnique({
        where: { id: game.boardId },
        select: { name: true },
      }),
    ]);

    return {
      id: game.id,
      code: game.code,
      mode: game.mode,
      status: game.status,
      createdAt: game.createdAt,
      startedAt: game.startedAt,
      finishedAt: game.endedAt,
      boardId: game.boardId,
      boardName: board?.name ?? null,
      gamePlayers: gamePlayers.map((gp) => ({
        id: gp.id,
        playerId: gp.userId,
        heroId: gp.heroId || undefined,
        status: gp.isReady ? 'READY' : 'PENDING',
        username: gp.user?.username,
        avatar: gp.user?.avatar,
      })),
    };
  }

  // ============================================
  // HEROES LIST
  // ============================================

  async getAllHeroes(
    page: number = 1,
    limit: number = 20,
    search?: string,
    sortBy?: string,
    sortOrder?: 'asc' | 'desc',
  ) {
    const where: any = {};
    if (search) {
      where.OR = [
        { name: { contains: search, mode: 'insensitive' as const } },
        { nameEn: { contains: search, mode: 'insensitive' as const } },
        { nameRu: { contains: search, mode: 'insensitive' as const } },
        { set: { contains: search, mode: 'insensitive' as const } },
      ];
    }

    const orderBy = this.buildOrderBy(sortBy, sortOrder, AdminService.HERO_SORT_FIELDS);

    const [heroes, total] = await Promise.all([
      this.prisma.hero.findMany({
        where,
        skip: (page - 1) * limit,
        take: limit,
        orderBy,
        select: {
          id: true,
          name: true,
          nameEn: true,
          nameRu: true,
          set: true,
          health: true,
          fighterType: true,
          ability: true,
          imageUrl: true,
          avatarUrl: true,
          createdAt: true,
        },
      }),
      this.prisma.hero.count({ where }),
    ]);

    return {
      items: heroes.map((hero) => this.serializeHero(hero)),
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  // ============================================
  // BOARDS LIST
  // ============================================

  async getAllBoards(
    page: number = 1,
    limit: number = 20,
    search?: string,
    sortBy?: string,
    sortOrder?: 'asc' | 'desc',
  ) {
    const where: any = {};
    if (search) {
      where.OR = [
        { name: { contains: search, mode: 'insensitive' as const } },
        { nameEn: { contains: search, mode: 'insensitive' as const } },
        { nameRu: { contains: search, mode: 'insensitive' as const } },
        { set: { contains: search, mode: 'insensitive' as const } },
      ];
    }

    const orderBy = this.buildOrderBy(sortBy, sortOrder, AdminService.BOARD_SORT_FIELDS);

    const [boards, total] = await Promise.all([
      this.prisma.board.findMany({
        where,
        skip: (page - 1) * limit,
        take: limit,
        orderBy,
        select: {
          id: true,
          name: true,
          nameEn: true,
          nameRu: true,
          set: true,
          width: true,
          height: true,
          imageUrl: true,
          imageUrlDark: true,
          createdAt: true,
        },
      }),
      this.prisma.board.count({ where }),
    ]);

    return {
      items: boards.map((board) => this.serializeBoard(board)),
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  // ============================================
  // MATCHMAKING QUEUE
  // ============================================

  async getMatchmakingQueue() {
    const modes = Object.values(GameMode);
    const entriesByMode = await Promise.all(
      modes.map((mode) => this.queueManager.getAllEntries(mode)),
    );

    const userIds = [
      ...new Set(entriesByMode.flat().map((entry) => entry.userId)),
    ];
    const users = userIds.length
      ? await this.prisma.user.findMany({
          where: { id: { in: userIds } },
          select: { id: true, username: true, avatar: true },
        })
      : [];
    const userById = new Map(users.map((user) => [user.id, user]));

    const items = entriesByMode.flatMap((entries, modeIndex) => {
      const mode = modes[modeIndex];
      // Позиция в очереди — по рейтингу (как в QueueManagerService.getUserPosition)
      const sorted = [...entries].sort((a, b) => a.rating - b.rating);
      return sorted.map((entry, index) => {
        const user = userById.get(entry.userId);
        return {
          id: `${mode}:${entry.userId}`,
          userId: entry.userId,
          username: user?.username ?? entry.userId,
          avatar: user?.avatar ?? null,
          mode,
          elo: entry.rating,
          joinedAt: entry.joinedAt,
          position: index + 1,
        };
      });
    });

    return {
      items,
      total: items.length,
      activeQueues: entriesByMode.filter((entries) => entries.length > 0)
        .length,
    };
  }
}
