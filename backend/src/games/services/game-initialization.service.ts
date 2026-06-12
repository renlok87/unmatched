/**
 * Game Initialization Service
 *
 * Создаёт начальное GameState при старте игры:
 * - бойцы (герой + sidekicks) с реальными HP из БД, стартовые позиции
 * - колоды из реальных карт героя (развёрнутые по count, перетасованные)
 * - стартовая рука 5 карт
 * - фаза ACTION_MANEUVER, первым ходит хост (seatOrder 0)
 *
 * До этого сервиса startGame только менял статус игры — GameState не
 * создавался вообще, и все игровые мутации падали на loadState.
 */

import { BadRequestException, Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../../database/prisma.service';
import {
  Card,
  DeckState,
  Fighter,
  GameState,
  GameStatePlayer,
  GameStateService,
  HandCard,
  HandZone,
} from '../game-state.service';
import { GamePhase } from '../dto';
import {
  ACTIONS_PER_TURN,
  CardType,
  FighterType,
  createEmptyBoardState,
  normalizeAttackType,
  normalizeCardEffects,
  slugifyHeroName,
} from '../../game-engine/models';
import type { AttackType, BoardState, Cell } from '../../game-engine/models';
import type { Board } from '@prisma/client';

const STARTING_HAND_SIZE = 5;
const MAX_HAND_SIZE = 7;

/** Размеры fallback-сетки (поведение до фикса геометрии) */
const FALLBACK_BOARD_SIZE = 20;
/** Sanity-границы сетки: отсекают пиксельные координаты (картинки 400×230 и т.п.) */
const MIN_GRID_SIZE = 2;
const MAX_GRID_SIZE = 50;

/** Смещения для размещения sidekick'ов вокруг героя */
const SIDEKICK_OFFSETS: { x: number; y: number }[] = [
  { x: 1, y: 0 },
  { x: 0, y: 1 },
  { x: 1, y: 1 },
  { x: -1, y: 0 },
  { x: 0, y: -1 },
];

function shuffle<T>(array: readonly T[]): T[] {
  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

function clampCoord(v: number, max: number): number {
  return Math.max(0, Math.min(max, v));
}

@Injectable()
export class GameInitializationService {
  private readonly logger = new Logger(GameInitializationService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly gameStateService: GameStateService,
  ) {}

  /**
   * Создать и сохранить начальное состояние игры.
   * Вызывается из startGame после перевода статуса в IN_PROGRESS.
   */
  async initializeGameState(gameId: string): Promise<GameState> {
    // --- Доска: реальная геометрия из БД (Board.cells), fallback — пустая 20×20 ---
    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      select: { boardId: true },
    });
    const board = game?.boardId
      ? await this.prisma.board.findUnique({ where: { id: game.boardId } })
      : null;
    const boardState = this.buildBoardState(board);

    const players = await this.prisma.gamePlayer.findMany({
      where: { gameId },
      orderBy: { seatOrder: 'asc' },
    });

    if (players.length < 2) {
      throw new BadRequestException('Для инициализации игры нужно минимум 2 игрока');
    }

    // Мутабельные локальные коллекции — engine-GameState readonly,
    // в литерал state они попадают уже готовыми (mutable → readonly OK)
    const statePlayers: GameStatePlayer[] = [];
    const fighters: Fighter[] = [];
    const decks: Record<string, DeckState> = {};
    const discardPiles: Record<string, Card[]> = {};
    const handZones: Record<string, HandZone> = {};

    // Стартовые углы от фактических размеров доски + занятые клетки
    const startPositions = this.computeStartPositions(boardState);
    const occupied = new Set<string>();

    for (let seat = 0; seat < players.length; seat++) {
      const player = players[seat];
      if (!player.heroId) {
        throw new BadRequestException(`Игрок ${player.userId} не выбрал героя`);
      }

      const hero = await this.prisma.hero.findUnique({
        where: { id: player.heroId },
        include: { cards: true },
      });
      if (!hero) {
        throw new BadRequestException(`Герой ${player.heroId} не найден`);
      }
      if (hero.cards.length === 0) {
        throw new BadRequestException(`У героя «${hero.name}» нет карт в БД — играть нечем`);
      }

      // --- Бойцы: герой + sidekicks ---
      // Если угол занят/obstacle — findFreeCell ищет ближайшую свободную клетку
      const basePos = this.findFreeCell(
        boardState,
        occupied,
        startPositions[seat] ?? startPositions[0],
      );
      occupied.add(`${basePos.x}:${basePos.y}`);
      const heroFighterId = `f-${seat}-hero`;
      const sidekicks = this.parseSidekicks(hero.sidekicks);
      // Слаг для HeroAbilityRegistry: handlers ключуются 'daredevil'/'ms-marvel',
      // heroId — cuid. Пишем и герою, и сайдкикам (handler ищет бойцов героя)
      const heroSlug = slugifyHeroName(hero.name);

      const sidekickFighters: Fighter[] = sidekicks.map((sk, i) => {
        const offset = SIDEKICK_OFFSETS[i % SIDEKICK_OFFSETS.length] ?? { x: 1, y: 1 };
        const position = this.findFreeCell(boardState, occupied, {
          x: clampCoord(basePos.x + offset.x, boardState.width - 1),
          y: clampCoord(basePos.y + offset.y, boardState.height - 1),
        });
        occupied.add(`${position.x}:${position.y}`);
        return {
          id: `f-${seat}-sk${i}`,
          ownerId: player.userId,
          heroId: hero.id,
          name: sk.name || `${hero.name} Sidekick ${i + 1}`,
          type: FighterType.MINION,
          health: sk.health ?? 1,
          maxHealth: sk.health ?? 1,
          position,
          effects: [],
          hasSidekick: false,
          // Мусор в БД (0/null/NaN/строка) → дефолт 2
          movement: Number.isInteger(sk.movement) && sk.movement! >= 1 ? sk.movement : 2,
          // 'range' из БД уже нормализован в parseSidekicks → 'ranged'
          attackType: sk.attackType,
          heroSlug,
        };
      });

      const heroFighter: Fighter = {
        id: heroFighterId,
        ownerId: player.userId,
        heroId: hero.id,
        name: hero.name,
        type: (hero.fighterType as FighterType) || FighterType.HERO,
        health: hero.health,
        maxHealth: hero.health,
        position: basePos,
        effects: [],
        hasSidekick: sidekickFighters.length > 0,
        sidekickIds: sidekickFighters.map((f) => f.id),
        // Мусор в БД (0/null/NaN/строка) → дефолт 2
        movement: Number.isInteger(hero.movement) && hero.movement >= 1 ? hero.movement : 2,
        // attackType героя лежит в Hero.properties (backfill-attack-type.ts);
        // отсутствие/мусор → 'melee' (поведение как до фикса)
        attackType: normalizeAttackType((hero.properties as any)?.attackType),
        heroSlug,
      };

      fighters.push(heroFighter, ...sidekickFighters);

      // --- Колода: реальные карты героя, развёрнутые по count ---
      const deckCards: Card[] = hero.cards.flatMap((card) =>
        Array.from({ length: Math.max(1, card.count) }, (_, copy) => ({
          id: `${card.id}::${copy}`,
          cardId: card.id,
          name: card.name,
          nameEn: card.nameEn,
          nameRu: card.nameRu,
          cardType: card.cardType as CardType,
          attackValue: card.attackValue ?? undefined,
          defenseValue: card.defenseValue ?? undefined,
          boostValue: card.boostValue ?? undefined,
          // Структурная валидация Json (мусор → UNSUPPORTED-эффект, не падаем)
          effects: normalizeCardEffects(card.effects, card.id),
          // Текст эффекта — едет в state (рука/колода/сброс) для playScheme
          text: card.text ?? undefined,
          // Кто может играть карту ('Any'/имя бойца) — bannerAllows-валидация
          bannerName: card.bannerName ?? undefined,
        })),
      );

      const drawPile = shuffle(deckCards);
      const hand: HandCard[] = drawPile
        .splice(0, STARTING_HAND_SIZE)
        .map((c) => ({ ...c, isVisible: false }));

      decks[player.userId] = {
        cards: deckCards,
        drawPile,
        topCard: drawPile[0],
      };
      discardPiles[player.userId] = [];
      handZones[player.userId] = { cards: hand, maxSize: MAX_HAND_SIZE };

      statePlayers.push({
        userId: player.userId,
        heroId: hero.id,
        health: hero.health,
        maxHealth: hero.health,
        fighterIds: [heroFighter.id, ...sidekickFighters.map((f) => f.id)],
        isAlive: true,
      });
    }

    const state: GameState = {
      gameId,
      sequenceNumber: 1,
      phase: GamePhase.ACTION_MANEUVER,
      turnCount: 1,
      currentTurnPlayerId: players[0].userId,
      players: statePlayers,
      fighters,
      decks,
      discardPiles,
      handZones,
      // Реальная геометрия доски из БД (или fallback-сетка 20×20) —
      // game-engine (movement/adjacency) читает cells[y][x]
      boardState,
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: 'system',
        version: 1,
        actionsRemaining: ACTIONS_PER_TURN,
      },
    };

    await this.gameStateService.saveState(gameId, state);
    this.logger.log(
      `Инициализировано состояние игры ${gameId}: ${fighters.length} бойцов, ` +
        `${statePlayers.length} игроков, первым ходит ${state.currentTurnPlayerId}`,
    );

    return state;
  }

  /**
   * Собрать BoardState движка из Board.cells (БД).
   *
   * Ожидаемый формат данных: плоский массив [{x, y, isObstacle?, zones?: string[]}, ...]
   * в grid-координатах. Любая невалидность (нет доски, cells=[], кривой JSON,
   * пиксельные координаты) → fallback на пустую сетку 20×20 — поведение
   * бит-в-бит как до фикса, регресса нет.
   */
  private buildBoardState(board: Board | null): BoardState {
    if (!board) {
      return createEmptyBoardState(FALLBACK_BOARD_SIZE, FALLBACK_BOARD_SIZE);
    }

    const rawCells = this.parseBoardCells(board.cells);
    if (rawCells.length === 0) {
      // Штатная ситуация для текущих данных (у всех досок cells=[]) — не warn
      this.logger.log(
        `Доска «${board.name}»: cells пусты — используется пустая сетка ${FALLBACK_BOARD_SIZE}×${FALLBACK_BOARD_SIZE}`,
      );
      return createEmptyBoardState(FALLBACK_BOARD_SIZE, FALLBACK_BOARD_SIZE);
    }

    // Валидация: целые неотрицательные координаты у каждой клетки
    let maxX = -1;
    let maxY = -1;
    for (const cell of rawCells) {
      const x = (cell as any)?.x;
      const y = (cell as any)?.y;
      if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0) {
        this.logger.warn(
          `Доска «${board.name}»: невалидная клетка в cells (${JSON.stringify(cell)?.slice(0, 100)}) — fallback на пустую сетку ${FALLBACK_BOARD_SIZE}×${FALLBACK_BOARD_SIZE}`,
        );
        return createEmptyBoardState(FALLBACK_BOARD_SIZE, FALLBACK_BOARD_SIZE);
      }
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }

    const width = maxX + 1;
    const height = maxY + 1;
    // Sanity: Board.width/height в БД — пиксели картинок (напр. 400×230);
    // если в cells оказались пиксельные координаты — это не игровая сетка
    if (width < MIN_GRID_SIZE || height < MIN_GRID_SIZE || width > MAX_GRID_SIZE || height > MAX_GRID_SIZE) {
      this.logger.warn(
        `Доска «${board.name}»: размер сетки ${width}×${height} вне диапазона ${MIN_GRID_SIZE}..${MAX_GRID_SIZE} — fallback на пустую сетку ${FALLBACK_BOARD_SIZE}×${FALLBACK_BOARD_SIZE}`,
      );
      return createEmptyBoardState(FALLBACK_BOARD_SIZE, FALLBACK_BOARD_SIZE);
    }

    // Полная матрица h×w: дыры в данных заполняем normal —
    // движок читает cells[y][x] и не переживёт undefined-строк/клеток
    const cells: Cell[][] = [];
    for (let y = 0; y < height; y++) {
      const row: Cell[] = [];
      for (let x = 0; x < width; x++) {
        row.push({ type: 'normal', x, y });
      }
      cells.push(row);
    }
    for (const cell of rawCells as any[]) {
      cells[cell.y][cell.x] = {
        type: cell.isObstacle ? 'obstacle' : 'normal',
        x: cell.x,
        y: cell.y,
        // Мультизонность (C1): полный список зон + legacy-zone (первая)
        // для старых сейвов; ranged/зонные эффекты работают по пересечению
        zones:
          Array.isArray(cell.zones) && cell.zones.length > 0
            ? cell.zones.map(String)
            : undefined,
        zone:
          Array.isArray(cell.zones) && cell.zones.length > 0
            ? String(cell.zones[0])
            : undefined,
      };
    }

    this.logger.log(
      `Доска «${board.name}»: загружена сетка ${width}×${height} из БД (${rawCells.length} клеток в данных)`,
    );
    return { width, height, cells, doors: {}, fog: {}, tokens: {} };
  }

  /**
   * Толерантный парс Board.cells (по образцу content.mapper.parsePrismaCells):
   * строка → JSON.parse (терпит баг двойной сериализации import-content),
   * массив → как есть, всё прочее → [].
   */
  private parseBoardCells(raw: unknown): unknown[] {
    if (!raw) return [];
    let value: unknown = raw;
    if (typeof value === 'string') value = this.tryParse(value);
    // Двойная сериализация: после первого parse снова строка — парсим ещё раз
    if (typeof value === 'string') value = this.tryParse(value);
    return Array.isArray(value) ? value : [];
  }

  /** Стартовые позиции по seatOrder от фактических размеров доски (углы с отступом) */
  private computeStartPositions(boardState: BoardState): { x: number; y: number }[] {
    const w = boardState.width;
    const h = boardState.height;
    return [
      { x: 2, y: 2 },
      { x: w - 3, y: h - 3 },
      { x: w - 3, y: 2 },
      { x: 2, y: h - 3 },
    ].map((p) => ({
      x: clampCoord(p.x, w - 1),
      y: clampCoord(p.y, h - 1),
    }));
  }

  /**
   * Найти свободную проходимую клетку, ближайшую к preferred (манхэттен-скан).
   * Свободная = в границах, не obstacle/wall, не занята другим бойцом.
   *
   * TODO: если в Board.cells когда-нибудь появятся startingPositions или
   * зона "start" — брать спавны оттуда (точка расширения именно здесь).
   */
  private findFreeCell(
    boardState: BoardState,
    occupied: ReadonlySet<string>,
    preferred: { x: number; y: number },
  ): { x: number; y: number } {
    const isFree = (x: number, y: number): boolean => {
      if (x < 0 || y < 0 || x >= boardState.width || y >= boardState.height) return false;
      if (occupied.has(`${x}:${y}`)) return false;
      const cell = boardState.cells[y]?.[x];
      return !cell || (cell.type !== 'obstacle' && cell.type !== 'wall');
    };

    if (isFree(preferred.x, preferred.y)) return preferred;

    // Скан по возрастанию манхэттен-дистанции до первой свободной клетки
    const maxDist = boardState.width + boardState.height;
    for (let d = 1; d <= maxDist; d++) {
      for (let dx = -d; dx <= d; dx++) {
        const dy = d - Math.abs(dx);
        for (const sign of dy === 0 ? [1] : [1, -1]) {
          const x = preferred.x + dx;
          const y = preferred.y + sign * dy;
          if (isFree(x, y)) return { x, y };
        }
      }
    }

    // Вся доска занята/непроходима (не должно случаться) — кламп preferred
    this.logger.warn(
      `findFreeCell: нет свободных клеток рядом с (${preferred.x},${preferred.y}) — возвращаю кламп`,
    );
    return {
      x: clampCoord(preferred.x, boardState.width - 1),
      y: clampCoord(preferred.y, boardState.height - 1),
    };
  }

  private parseSidekicks(
    raw: unknown,
  ): { name?: string; health?: number; movement?: number; attackType: AttackType }[] {
    if (!raw) return [];
    const value = typeof raw === 'string' ? this.tryParse(raw) : raw;
    if (!Array.isArray(value)) return [];
    // Разворачиваем записи с count/quantity в отдельных бойцов
    return value.flatMap((sk: any) => {
      const count = Math.min(4, Math.max(1, Number(sk?.count ?? sk?.quantity ?? 1) || 1));
      return Array.from({ length: count }, (_, i) => ({
        name: count > 1 && sk?.name ? `${sk.name} ${i + 1}` : sk?.name,
        health: sk?.health != null ? Number(sk.health) : undefined,
        movement: sk?.movement != null ? Number(sk.movement) : undefined,
        // В БД sidekicks несут 'range'|'melee' — нормализуем в канон движка
        attackType: normalizeAttackType(sk?.attackType),
      }));
    });
  }

  private tryParse(value: string): unknown {
    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  }
}
