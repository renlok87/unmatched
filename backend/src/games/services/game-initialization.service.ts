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
  getCellZones,
  normalizeAttackType,
  normalizeCardEffects,
  slugifyHeroName,
} from '../../game-engine/models';
import type { AttackType, BoardState, CardEffect, Cell, Position } from '../../game-engine/models';
import { parseCardEffectTexts, upgradeStaleParserEffects } from '../../game-engine/effects/effect-text-parser';
import { distancesFrom, hasTopology, posKey } from '../../game-engine/engine/board-topology';
import type { Board } from '@prisma/client';

const STARTING_HAND_SIZE = 5;
const MAX_HAND_SIZE = 7;

/** Sanity-границы сетки: отсекают пиксельные координаты (картинки 400×230 и т.п.) */
const MIN_GRID_SIZE = 2;
const MAX_GRID_SIZE = 50;

function shuffle<T>(array: readonly T[]): T[] {
  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

/** Клетка Board.cells как она лежит в БД (JSON): поля топологии не доверенные */
interface RawTopologyCell {
  readonly spaceId?: unknown;
  readonly layout?: { readonly x?: unknown; readonly y?: unknown } | null;
  readonly start?: unknown;
  readonly links?: unknown;
}

const isInt = (v: unknown): v is number => typeof v === 'number' && Number.isInteger(v);

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
    // --- Доска: реальная геометрия из БД (Board.cells); без годной доски игра не стартует (НД-2) ---
    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      select: { boardId: true },
    });
    const board = game?.boardId
      ? await this.prisma.board.findUnique({ where: { id: game.boardId } })
      : null;
    const boardState = this.buildBoardState(board, game?.boardId);

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
    // A catalog card can appear in both players' decks in a mirror match.
    // Allocate copy numbers for the entire game, not separately per player.
    const nextCardCopy = new Map<string, number>();

    // Стартовые углы от фактических размеров доски + занятые клетки
    const startPositions = this.computeStartPositions(boardState);
    // ENV-MAPS: доска оригинальной карты (граф клеток со связями) — старты из
    // пронумерованных стартовых пространств (Cell.start), а не из углов сетки
    const topology = hasTopology(boardState);
    const topologyStarts = topology ? this.computeTopologyStarts(boardState, players.length) : [];
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
      // Если угол занят/obstacle — findFreeCell ищет ближайшую свободную клетку.
      // Топология: стартовое пространство seat+1; нет такого номера на карте —
      // прежний угол (документированный fallback).
      const basePos = this.findFreeCell(
        boardState,
        occupied,
        topologyStarts[seat] ?? startPositions[seat] ?? startPositions[0],
      );
      occupied.add(`${basePos.x}:${basePos.y}`);
      const heroFighterId = `f-${seat}-hero`;
      const sidekicks = this.parseSidekicks(hero.sidekicks);
      // Слаг для HeroAbilityRegistry: handlers ключуются 'daredevil'/'ms-marvel',
      // heroId — cuid. Пишем и герою, и сайдкикам (handler ищет бойцов героя)
      const heroSlug = slugifyHeroName(hero.name);
      // Топология: сайдкики не занимают стартовые пространства героев
      // следующих мест (их герои ещё не выставлены)
      const reservedStarts = topology
        ? new Set(
            topologyStarts
              .slice(seat + 1)
              .filter((p): p is Position => p !== undefined)
              .map(posKey),
          )
        : null;

      const sidekickFighters: Fighter[] = sidekicks.map((sk, i) => {
        // GD-016: легальная серверная расстановка — сайдкик на отдельной
        // свободной клетке, разделяющей хотя бы одну зону с героем
        const position = reservedStarts
          ? this.findTopologySidekickSpace(
              boardState,
              new Set([...occupied, ...reservedStarts]),
              basePos,
            )
          : this.findSidekickCell(boardState, occupied, basePos);
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
      const deckCards: Card[] = hero.cards.flatMap((card) => {
        const count = Math.max(1, card.count);
        const firstCopy = nextCardCopy.get(card.id) ?? 0;
        nextCardCopy.set(card.id, firstCopy + count);
        return Array.from({ length: count }, (_, copy) => ({
          id: `${card.id}::${firstCopy + copy}`,
          cardId: card.id,
          name: card.name,
          nameEn: card.nameEn,
          nameRu: card.nameRu,
          cardType: card.cardType as CardType,
          attackValue: card.attackValue ?? undefined,
          defenseValue: card.defenseValue ?? undefined,
          boostValue: card.boostValue ?? undefined,
          // Структурная валидация Json (мусор → UNSUPPORTED-эффект, не падаем).
          // S05 (GD-019): SCHEME-карты с пустым effects, но печатным текстом
          // (Card.text = textEn: A Momentary Glance, Winged Frenzy, …) —
          // парсим fullText на инжесте, чтобы матч не играл их как молчаливый
          // no-op без бэкфилла БД.
          effects: this.resolveCardEffects(card),
          // Текст эффекта — едет в state (рука/колода/сброс) для playScheme
          text: card.text ?? undefined,
          // Кто может играть карту ('Any'/имя бойца) — bannerAllows-валидация
          bannerName: card.bannerName ?? undefined,
        }));
      });

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
      // Реальная геометрия доски из БД (без годной доски старт не проходит) —
      // game-engine (movement/adjacency) читает cells[y][x]
      boardState,
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: 'system',
        version: 1,
        actionsRemaining: ACTIONS_PER_TURN,
        // GD-016: явный первый игрок матча — seatOrder 0, виден клиентам
        firstPlayerId: players[0].userId,
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
   * S05 (GD-019): эффекты карты при инжесте колоды.
   * Структурная валидация Json (normalizeCardEffects: мусор → UNSUPPORTED).
   * Fallback: SCHEME-карта с ПУСТЫМ effects, но непустым печатным текстом
   * (Card.text = textEn: A Momentary Glance, Winged Frenzy, …) — парсим
   * fullText, чтобы матч исполнял эффект без ожидания backfill БД.
   * S09: DEFENSE/VERSATILE-карты с ПУСТЫМ effects и печатным effectAfter
   * (Hiss and Slither, Clutching Claws: «Your opponent discards 1 card») —
   * парсим after-текст (AFTER_COMBAT), как SCHEME fullText.
   * Нераспознанный текст честно даёт UNSUPPORTED (не молчаливый no-op).
   * S06: устаревшие parser-эффекты (parserVersion < текущей) апгрейдятся
   * повторным разбором (upgradeStaleParserEffects) — как backfill, но без
   * ожидания деплоя; замена только при ПОЛНОМ распознании.
   */
  private resolveCardEffects(card: {
    id: string;
    cardType: string;
    effects: unknown;
    text?: string | null;
    effectImmediately?: string | null;
    effectDuring?: string | null;
    effectAfter?: string | null;
    effectBoost?: string | null;
    effectOngoing?: string | null;
  }): CardEffect[] {
    const effects = normalizeCardEffects(card.effects, card.id);
    const fullText = card.cardType === 'SCHEME' && card.text?.trim() ? card.text : undefined;
    // ATTACK-карты несут боевой текст в effectDuring («You may BOOST this
    // attack», Second Shot / Noble Sacrifice): без этого fallback их эффекты
    // терялись и сервер никогда не ставил пост-reveal BOOST_CHOICE паузу.
    const duringText =
        card.cardType === 'ATTACK' && card.effectDuring?.trim() ? card.effectDuring : undefined;
    // DEFENSE/VERSATILE-карты несут пост-эффект боя в effectAfter (Hiss and
    // Slither / Clutching Claws: «Your opponent discards 1 card») — парсим
    // на инжесте, иначе DISCARD_CARDS-хеды никогда не ставятся в рантайме.
    const afterText =
        (card.cardType === 'DEFENSE' || card.cardType === 'VERSATILE') && card.effectAfter?.trim()
          ? card.effectAfter
          : undefined;
    if (effects.length > 0) {
      return upgradeStaleParserEffects(
        effects,
        {
          immediately: card.effectImmediately,
          during: card.effectDuring,
          after: card.effectAfter,
          boost: card.effectBoost,
          ongoing: card.effectOngoing,
          fullText,
        },
        card.id,
      );
    }
    if (!fullText && !duringText && !afterText) return [];
    const { effects: parsed } = parseCardEffectTexts(
      { fullText, during: duringText, after: afterText },
      card.id,
    );
    return parsed;
  }

  /**
   * Собрать BoardState движка из Board.cells (БД).
   *
   * Ожидаемый формат данных: плоский массив [{x, y, isObstacle?, zones?: string[]}, ...]
   * в grid-координатах. Любая невалидность (нет доски, cells=[], кривой JSON,
   * пиксельные координаты) → BadRequestException: старт игры не проходит,
   * startGame откатывает статус в LOBBY. Пустая сетка 20×20 больше не
   * подставляется (НД-2, docs/game-design/decisions/2026-10-04-real-boards-only.md).
   *
   * ENV-MAPS (контракт unmatched.board-topology/1): клетка может нести
   * spaceId / layout / start / links — они копируются ЯВНО (только если есть,
   * у сеточных досок клетки остаются {type,x,y,zones,zone} бит-в-бит).
   * Доска «топологическая», если хотя бы одна клетка несёт массив links
   * (правила смежности — game-engine/engine/board-topology.ts). У такой доски
   * позиция решётки БЕЗ данных — дыра между пространствами, её нельзя
   * заполнять 'normal' (движок/AI могли бы поставить туда бойца):
   * она становится 'obstacle'.
   */
  private buildBoardState(board: Board | null, boardId?: string): BoardState {
    if (!board) {
      throw new BadRequestException(
        `Доска игры ${boardId ? `«${boardId}» ` : ''}не найдена — игру на ней начать нельзя`,
      );
    }

    const rawCells = this.parseBoardCells(board.cells);
    if (rawCells.length === 0) {
      throw new BadRequestException(`Доска «${board.name}»: cells пусты — игру на ней начать нельзя`);
    }

    // Валидация: целые неотрицательные координаты у каждой клетки
    let maxX = -1;
    let maxY = -1;
    for (const cell of rawCells) {
      const x = (cell as any)?.x;
      const y = (cell as any)?.y;
      if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0) {
        throw new BadRequestException(
          `Доска «${board.name}»: невалидная клетка в cells (${JSON.stringify(cell)?.slice(0, 100)}) — игру на ней начать нельзя`,
        );
      }
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }

    const width = maxX + 1;
    const height = maxY + 1;
    // Sanity: Board.width/height в БД — пиксели картинок (напр. 400×230);
    // если в cells оказались пиксельные координаты — это не игровая сетка
    if (width < MIN_GRID_SIZE || height < MIN_GRID_SIZE || width > MAX_GRID_SIZE || height > MAX_GRID_SIZE) {
      throw new BadRequestException(
        `Доска «${board.name}»: размер сетки ${width}×${height} вне диапазона ${MIN_GRID_SIZE}..${MAX_GRID_SIZE} — игру на ней начать нельзя`,
      );
    }

    // Топология оригинальной карты: хотя бы одна клетка несёт массив links
    const topology = (rawCells as (RawTopologyCell | null)[]).some((cell) =>
      Array.isArray(cell?.links),
    );

    // Полная матрица h×w: дыры в данных заполняем normal (сеточные доски —
    // как было) или obstacle (топология: дыра — не пространство) —
    // движок читает cells[y][x] и не переживёт undefined-строк/клеток
    const holeType: Cell['type'] = topology ? 'obstacle' : 'normal';
    const cells: Cell[][] = [];
    for (let y = 0; y < height; y++) {
      const row: Cell[] = [];
      for (let x = 0; x < width; x++) {
        row.push({ type: holeType, x, y });
      }
      cells.push(row);
    }
    let droppedLinks = 0;
    for (const cell of rawCells as any[]) {
      const extra = this.topologyCellFields(cell as RawTopologyCell, width, height);
      droppedLinks += extra.droppedLinks;
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
        ...extra.fields,
      };
    }

    if (topology) {
      const spaces = cells.flat().filter((c) => c.type !== 'obstacle' && c.type !== 'wall');
      const badTargets = cells
        .flat()
        .flatMap((c) => (c.links ?? []).map((l) => cells[l.y][l.x]))
        .filter((t) => t.type === 'obstacle' || t.type === 'wall').length;
      if (droppedLinks > 0 || badTargets > 0) {
        this.logger.warn(
          `Доска «${board.name}»: ${droppedLinks} связей вне решётки отброшено, ` +
            `${badTargets} связей ведут в непроходимую клетку`,
        );
      }
      this.logger.log(
        `Доска «${board.name}»: топология оригинальной карты, решётка ${width}×${height}, ` +
          `${spaces.length} пространств`,
      );
    } else {
      this.logger.log(
        `Доска «${board.name}»: загружена сетка ${width}×${height} из БД (${rawCells.length} клеток в данных)`,
      );
    }
    return { width, height, cells, doors: {}, fog: {}, tokens: {} };
  }

  /**
   * ENV-MAPS: поля топологии клетки из Board.cells — копируются явно и
   * только при валидном значении (иначе ключа нет вовсе: клетки сеточных
   * досок не меняются):
   *  - spaceId: непустая строка (M01..M31, S01..S38);
   *  - layout: центр пространства в пикселях иллюстрации карты {x, y};
   *  - start: номер стартового пространства 1..4;
   *  - links: позиции решётки связанных клеток; массив сохраняется даже
   *    пустым (он и делает доску топологической), записи вне решётки
   *    отбрасываются (счётчик droppedLinks → warn).
   */
  private topologyCellFields(
    cell: RawTopologyCell,
    width: number,
    height: number,
  ): {
    fields: Pick<Cell, 'spaceId' | 'layout' | 'start' | 'links'>;
    droppedLinks: number;
  } {
    const fields: { spaceId?: string; layout?: Position; start?: number; links?: Position[] } = {};
    let droppedLinks = 0;
    if (typeof cell.spaceId === 'string' && cell.spaceId.length > 0) {
      fields.spaceId = cell.spaceId;
    }
    const lx = cell.layout?.x;
    const ly = cell.layout?.y;
    const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
    if (finite(lx) && finite(ly)) {
      fields.layout = { x: lx, y: ly };
    }
    if (isInt(cell.start) && cell.start >= 1 && cell.start <= 4) {
      fields.start = cell.start;
    }
    if (Array.isArray(cell.links)) {
      fields.links = [];
      for (const link of cell.links as ({ x?: unknown; y?: unknown } | null)[]) {
        const x = link?.x;
        const y = link?.y;
        if (isInt(x) && isInt(y) && x >= 0 && y >= 0 && x < width && y < height) {
          fields.links.push({ x, y });
        } else {
          droppedLinks++;
        }
      }
    }
    return { fields, droppedLinks };
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
   * ENV-MAPS: стартовые пространства топологической доски по местам.
   * Место seat (seatOrder) ставит героя на пространство со start = seat + 1:
   * дуэль — хост (seat 0, ходит первым) на 1, соперник (seat 1) на 2; при
   * 3–4 игроках — 1..4 в порядке мест. Непроходимые клетки и повторы номера
   * игнорируются (первое по порядку решётки). Нет номера — undefined, тогда
   * вызывающий берёт прежний угол сетки (computeStartPositions).
   */
  private computeTopologyStarts(boardState: BoardState, seats: number): (Position | undefined)[] {
    const byNumber = new Map<number, Position>();
    for (const row of boardState.cells) {
      for (const cell of row) {
        if (cell.start == null || cell.type === 'obstacle' || cell.type === 'wall') continue;
        if (byNumber.has(cell.start)) {
          this.logger.warn(`Стартовое пространство ${cell.start} повторяется — беру первое`);
          continue;
        }
        byNumber.set(cell.start, { x: cell.x, y: cell.y });
      }
    }
    return Array.from({ length: seats }, (_, seat) => {
      const start = byNumber.get(seat + 1);
      if (!start) {
        this.logger.warn(
          `На карте нет стартового пространства ${seat + 1} — место ${seat} ставится в угол сетки`,
        );
      }
      return start;
    });
  }

  /**
   * ENV-MAPS: пространство для сайдкика на топологической доске (правила
   * BoL Vol.1: отдельное свободное пространство в зоне героя; герой на
   * многозонном пространстве — в ЛЮБОЙ из его зон).
   * Порядок детерминирован: BFS-дистанция по линиям от героя (бойцы не
   * мешают подсчёту), при равенстве — spaceId (затем y, x).
   * Fallback (в зонах героя нет свободного пространства, или у героя нет
   * зон): ближайшее по тому же порядку свободное пространство вне зоны +
   * warn; вообще нет свободных — прежний findFreeCell (кламп).
   * `blocked` — занятые бойцами клетки и зарезервированные старты.
   */
  private findTopologySidekickSpace(
    boardState: BoardState,
    blocked: ReadonlySet<string>,
    heroPos: Position,
  ): Position {
    const heroZones = new Set(getCellZones(boardState.cells[heroPos.y]?.[heroPos.x]));
    const dist = distancesFrom(boardState, heroPos);
    const free: { cell: Cell; d: number }[] = [];
    for (const row of boardState.cells) {
      for (const cell of row) {
        if (cell.type === 'obstacle' || cell.type === 'wall') continue;
        if (blocked.has(posKey(cell))) continue;
        free.push({ cell, d: dist.get(posKey(cell)) ?? Infinity });
      }
    }
    const order = (a: { cell: Cell; d: number }, b: { cell: Cell; d: number }): number => {
      if (a.d !== b.d) return a.d < b.d ? -1 : 1;
      const ia = a.cell.spaceId ?? '';
      const ib = b.cell.spaceId ?? '';
      if (ia !== ib) return ia < ib ? -1 : 1;
      return a.cell.y - b.cell.y || a.cell.x - b.cell.x;
    };
    free.sort(order);
    const inZone = free.find(({ cell }) => getCellZones(cell).some((z) => heroZones.has(z)));
    if (inZone) return { x: inZone.cell.x, y: inZone.cell.y };
    this.logger.warn(
      `findTopologySidekickSpace: у героя (${heroPos.x},${heroPos.y}) нет свободного пространства его зоны — ближайшее свободное`,
    );
    if (free.length > 0) return { x: free[0].cell.x, y: free[0].cell.y };
    return this.findFreeCell(boardState, blocked, heroPos);
  }

  /**
   * GD-016: клетка для сайдкика — отдельная свободная проходимая клетка,
   * разделяющая хотя бы одну зону с клеткой героя (скан по возрастанию
   * манхэттен-дистанции от героя). Доски без зон у клетки героя (нет zone-
   * данных) не имеют зонного ограничения → прежний proximity-fallback
   * (findFreeCell от героя). Деградация: если во всей зоне героя нет свободных
   * клеток — тоже proximity-fallback + warn (расстановка не должна ронять старт).
   */
  private findSidekickCell(
    boardState: BoardState,
    occupied: ReadonlySet<string>,
    heroPos: { x: number; y: number },
  ): { x: number; y: number } {
    const heroZones = new Set(getCellZones(boardState.cells[heroPos.y]?.[heroPos.x]));
    if (heroZones.size > 0) {
      const isFree = (x: number, y: number): boolean => {
        if (x < 0 || y < 0 || x >= boardState.width || y >= boardState.height) return false;
        if (occupied.has(`${x}:${y}`)) return false;
        const cell = boardState.cells[y]?.[x];
        return !cell || (cell.type !== 'obstacle' && cell.type !== 'wall');
      };
      const sharesZone = (x: number, y: number): boolean =>
        getCellZones(boardState.cells[y]?.[x]).some((z) => heroZones.has(z));

      const maxDist = boardState.width + boardState.height;
      for (let d = 1; d <= maxDist; d++) {
        for (let dx = d; dx >= -d; dx--) {
          const dy = d - Math.abs(dx);
          for (const sign of dy === 0 ? [1] : [1, -1]) {
            const x = heroPos.x + dx;
            const y = heroPos.y + sign * dy;
            if (isFree(x, y) && sharesZone(x, y)) return { x, y };
          }
        }
      }
      this.logger.warn(
        `findSidekickCell: у героя (${heroPos.x},${heroPos.y}) нет свободной клетки его зоны — proximity-fallback`,
      );
    }
    return this.findFreeCell(boardState, occupied, heroPos);
  }

  /**
   * Найти свободную проходимую клетку, ближайшую к preferred (манхэттен-скан).
   * Свободная = в границах, не obstacle/wall, не занята другим бойцом.
   *
   * Старты оригинальных карт (Board.cells[].start) выбирает
   * computeTopologyStarts; сюда они приходят как preferred.
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
