import { ConflictException, Injectable, Logger, NotFoundException, Optional } from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { RatingService } from '../users/rating.service';
import { GameSubscriptionService } from './game-subscription.service';
import { GamePhase, GameEvent, GameEventType, GameStatus } from './dto';
import { ConcurrentModificationException } from './exceptions/game.exceptions';
// Единое семейство моделей состояния — engine-модели (P3: убрано дублирование
// games/engine; раньше здесь жили параллельные интерфейсы, стыкуемые "as any")
import type {
  GameState,
  GameStatePlayer,
  GameStateMetadata,
  Fighter,
  FighterEffect,
  Card,
  DeckState,
  HandZone,
  HandCard,
  BoardState,
} from '../game-engine/models';
import { FighterType, CardType, createEmptyBoardState } from '../game-engine/models';

/* eslint-disable @typescript-eslint/no-unsafe-assignment */
/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-call */
/* eslint-disable @typescript-eslint/no-redundant-type-constituents */
/* eslint-disable @typescript-eslint/no-unsafe-argument */

// Re-export для существующих импортёров (resolvers, guards, services и др.)
export type {
  GameState,
  GameStatePlayer,
  GameStateMetadata,
  Fighter,
  FighterEffect,
  Card,
  DeckState,
  HandZone,
  HandCard,
  BoardState,
};
export { FighterType, CardType };

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
  dp?: Readonly<Record<string, readonly Card[]>>; // discard piles
  h: Record<string, SerializedHand>; // hands
  b: SerializedBoard; // board
  m: {
    la: string; // lastActionAt
    lb: string; // lastActionBy
    v: number; // version
    ar?: number; // actionsRemaining — оставшиеся действия в ходу (легаси-сейвы без поля → дефолт в getActionsRemaining)
    // Раньше ТЕРЯЛИСЬ при save/load — бой выживал только в Redis-кеше (TTL!):
    ci?: SerializedCombatInfo; // combatInfo — текущий бой
    cc?: GameStateMetadata['combatEffectContinuation'];
    cp?: GameStateMetadata['combatResolutionProgress'];
    pc?: number; // passCount
    wi?: string; // winnerId
    tsp?: Record<string, { x: number; y: number }>; // turnStartPositions (MOVED_THIS_TURN)
    pe?: readonly unknown[]; // pendingEffects — выборы игрока (C2)
    pm?: GameStateMetadata['pendingManeuver'];
    phd?: GameStateMetadata['pendingHandDiscard'];
    // Per-turn флаги действий (TASK): сбрасываются в advanceTurn, читаются
    // combat-условиями способностей. Раньше отсутствовали — round-trip обязателен.
    mt?: boolean; // maneuveredThisTurn
    at?: boolean; // attackedThisTurn
    lc?: boolean; // lostCombatThisTurn
    hs?: Record<string, string>; // heroStances — текущая стойка героя по userId (STANCE)
    fp?: string; // firstPlayerId — явный первый игрок матча (GD-016)
    pte?: GameStateMetadata['pendingTurnEnd']; // GD-018: отложенная передача хода
  };
}

export interface SerializedPlayer {
  uid: string;
  hid: string;
  hp: number;
  mhp: number;
  fid: readonly string[];
  alv: boolean;
}

export interface SerializedFighter {
  id: string;
  oid: string;
  hid: string;
  n: string;
  ty: FighterType; // Wire-формат прежний: те же строки HERO/MINION/HUGE
  hp: number;
  mhp: number;
  pos: { x: number; y: number };
  e: readonly any[];
  hs: boolean;
  si?: readonly string[];
  df?: boolean; // isDefeated — раньше терялся при save/load
  mv?: number; // movement — очки движения (легаси-сейвы без поля → дефолт в getFighterMovement)
  at?: string; // attackType — 'melee'|'ranged' (легаси-сейвы без поля → дефолт в getFighterAttackType)
  sl?: string; // heroSlug — ключ HeroAbilityRegistry (легаси-сейвы без поля → способности молчат)
}

/** Сериализованный CombatState (даты — ISO-строки) */
export interface SerializedCombatInfo {
  aid: string; // attackerId (fighter id)
  did: string; // defenderId (userId защитника)
  tf?: string; // targetFighterId — атакованный боец (легаси без поля → первый боец защитника)
  ac: string; // attackerCardId
  dc?: string; // defenderCardId
  av: number; // attackValue — ТОЛЬКО печатное значение атакующей карты
  bv?: number; // boostValue — сумма boost (face-down до reveal; см. filterPrivateData)
  cbc?: string; // cardBoostCardId — instance id карты-BOOST (Second Shot)
  abc?: string; // abilityBoostCardId — instance id ability-boost карты (Arthur)
  dv: number; // defenseValue
  sa: string; // startedAt ISO
  ta?: string; // timeoutAt ISO
}

export interface SerializedDeck {
  c: number; // Количество карт в колоде
  tc?: Card; // Верхняя карта (только для владельца)
  // Полное содержимое — без него состояние терялось при load (колода обнулялась)
  cards?: readonly Card[];
  pile?: readonly Card[];
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
  // Сетка клеток для game-engine (movement/adjacency читают cells[y][x])
  cells?: readonly (readonly any[])[];
  w?: number;
  h?: number;
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
    // ELO-формула для applyFinishStats; чистый stateless-сервис. @Optional:
    // тест-модули собирают GameStateService без users-провайдеров — тогда
    // работает дефолтный инстанс (Nest передаёт undefined → default вступает)
    @Optional() private ratingService: RatingService = new RatingService(prisma),
  ) {}

  /**
   * Сохранить состояние игры в БД
   */
  async saveState(gameId: string, state: GameState): Promise<void> {
    const serialized = this.serialize(state);

    await this.prisma.$transaction(async (tx) => {
      // startGame commits IN_PROGRESS before its initial save. Claim that row
      // for every phase so an action/timeout cannot persist after an abort or
      // a finish. The conditional write serializes with abortGame's update.
      const isTerminal = state.phase === GamePhase.GAME_OVER;
      const transition = await tx.game.updateMany({
        where: { id: gameId, status: GameStatus.IN_PROGRESS },
        data: isTerminal
          ? {
              status: GameStatus.FINISHED,
              winnerId: state.metadata.winnerId ?? null,
              endedAt: new Date(),
              version: state.sequenceNumber,
            }
          : { version: state.sequenceNumber },
      });
      if (transition.count !== 1) {
        throw new ConflictException('Only an in-progress game can save state');
      }

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

      // Статистика (gamesPlayed/won/lost + ELO) применяется в той же
      // транзакции, что и переход IN_PROGRESS → FINISHED: ровно один вызов
      // проходит условный updateMany выше, поэтому победа начисляется ровно
      // один раз, а гонка с abortGame откатывает статус и статистику вместе.
      if (isTerminal) {
        await this.applyFinishStats(tx, gameId, state);
      }
    });

    // Once committed, a later action may already have advanced the row.
    // Supersession is a delivery decision, never a failed mutation.
    if (!(await this.isCurrentSavedState(gameId, state))) {
      this.logger.debug(`Skipping superseded state ${gameId} seq ${state.sequenceNumber}`);
      return;
    }

    // Terminal writes invalidate the cached game response and both myGames
    // lists; otherwise game(id) can show IN_PROGRESS/winner null for 5 minutes.
    if (state.phase === GamePhase.GAME_OVER) {
      const keys = [
        `game:${gameId}`,
        ...state.players.flatMap((p) => [
          `games:list:${p.userId}:all`,
          `games:list:${p.userId}:PENDING`,
          `games:list:${p.userId}:LOBBY`,
          `games:list:${p.userId}:IN_PROGRESS`,
          `games:list:${p.userId}:FINISHED`,
          `games:list:${p.userId}:ABORTED`,
        ]),
      ];
      // Per-key eviction: transient Redis failure on one key must not abandon
      // the remaining deletes (getGame re-checks terminal status, but list
      // caches rely solely on these). Failures stay logged, never swallowed.
      for (const key of keys) {
        try {
          await this.redis.del(key);
        } catch (e) {
          this.logger.warn(`Game cache invalidation failed for ${key}: ${e}`);
        }
      }
    }

    // The terminal FINISHED transition committed with the state above. Abort
    // cannot change FINISHED, so GAME_OVER remains authoritative while this
    // external delivery runs. Keep Redis/WS outside a database transaction.
    try {
      await this.cacheState(gameId, state);
    } catch (error) {
      this.logger.warn(`Game state cache write failed after commit: ${error}`);
    }
    if (!(await this.isCurrentSavedState(gameId, state))) {
      this.logger.debug(`Skipping superseded state publication ${gameId} seq ${state.sequenceNumber}`);
      return;
    }
    if (this.gameSubscriptionService) {
      try {
        await this.gameSubscriptionService.publishGameUpdate(gameId, 'STATE_UPDATED', state);
      } catch (error) {
        this.logger.warn(`Game state publication failed after commit: ${error}`);
      }
    }
    // A nonterminal event may be delivered after abort's seq-0 GAME_ENDED.
    // This read records the race; it cannot retract an event already sent.
    if (state.phase !== GamePhase.GAME_OVER) {
      if (!(await this.isCurrentSavedState(gameId, state))) {
        this.logger.warn(`State ${gameId} seq ${state.sequenceNumber} was superseded during publication`);
      }
    }
  }

  private async isCurrentSavedState(gameId: string, state: GameState): Promise<boolean> {
    try {
      const game = await this.prisma.game.findUnique({
        where: { id: gameId },
        select: { status: true, version: true },
      });
      const expectedStatus = state.phase === GamePhase.GAME_OVER
        ? GameStatus.FINISHED
        : GameStatus.IN_PROGRESS;
      return game?.status === expectedStatus && game.version === state.sequenceNumber;
    } catch (error) {
      this.logger.warn(`Game status check failed after state commit: ${error}`);
      return false;
    }
  }

  /**
   * GD-036 (stats): терминальная партия обновляет статистику обоих игроков
   * внутри транзакции финиша. Состав state.players/winnerId сверяется с
   * persisted Game (hostId/opponentId): на рассинхроне транзакция откатывается
   * целиком — FINISHED не фиксируется, статистика посторонним не начисляется.
   * Ничья (winnerId отсутствует) при корректном составе начисляет gamesPlayed/
   * lastPlayedAt/winRate обоим и сдвигает ELO на S=0.5 (RatingService считает
   * только победу/поражение, поэтому draw-формула локальна и переиспользует
   * его K-фактор): при равных рейтингах изменение нулевое, при неравных —
   * рейтинги сходятся.
   */
  private async applyFinishStats(
    tx: Prisma.TransactionClient,
    gameId: string,
    state: GameState,
  ): Promise<void> {
    const winnerId = state.metadata.winnerId;

    // Транзакция уже перекрыла строку game условным updateMany выше, поэтому
    // host/opponent стабильны под проверкой.
    const game = await tx.game.findUnique({
      where: { id: gameId },
      select: { hostId: true, opponentId: true },
    });
    const persisted = game?.opponentId && game.opponentId !== game.hostId
      ? [game.hostId, game.opponentId]
      : null;
    const stateIds = state.players.map((p) => p.userId);
    const compositionMatches =
      !!persisted &&
      stateIds.length === 2 &&
      new Set(stateIds).size === 2 &&
      persisted.every((id) => stateIds.includes(id));
    if (!compositionMatches || (!!winnerId && !persisted!.includes(winnerId))) {
      throw new ConflictException(
        `Terminal state of game ${gameId} does not match persisted participants ` +
          `(state: [${stateIds.join(', ')}], winner: ${winnerId ?? 'draw'}, ` +
          `game: [${persisted?.join(', ') ?? 'incomplete duel'}])`,
      );
    }
    // Вставка строго в отсортированном порядке: одновременные первые финиши
    // двух игр одной пары (включая ничьи с противоположными победителями)
    // вставляют одни и те же строки в одном порядке — цикл ожидания на
    // unique(userId) невозможен. skipDuplicates (ON CONFLICT DO NOTHING):
    // конкурентный upsert падал бы на unique(userId) в READ COMMITTED
    const seatIds = [...stateIds].sort();
    await tx.userStats.createMany({
      data: seatIds.map((userId) => ({ userId })),
      skipDuplicates: true,
    });

    // FOR UPDATE в детерминированном порядке сериализует одновременные
    // финиши разных игр одного игрока: оба считают ELO от актуального снимка
    const locked = await tx.$queryRaw<
      { userId: string; gamesPlayed: number; gamesWon: number; gamesLost: number; currentElo: number; peakElo: number }[]
    >(Prisma.sql`
      SELECT "userId", "gamesPlayed", "gamesWon", "gamesLost", "currentElo", "peakElo"
      FROM "UserStats"
      WHERE "userId" IN (${seatIds[0]}, ${seatIds[1]})
      ORDER BY "userId"
      FOR UPDATE
    `);
    const statsById = new Map(locked.map((s) => [s.userId, s]));

    if (!winnerId) {
      const firstStats = statsById.get(seatIds[0]);
      const secondStats = statsById.get(seatIds[1]);
      if (!firstStats || !secondStats) {
        throw new Error(`UserStats rows missing after upsert for game ${gameId}`);
      }
      const ratings = this.calculateDrawRatings(firstStats.currentElo, secondStats.currentElo);
      for (const [stats, newElo] of [
        [firstStats, ratings.first],
        [secondStats, ratings.second],
      ] as const) {
        await tx.userStats.update({
          where: { userId: stats.userId },
          data: {
            gamesPlayed: stats.gamesPlayed + 1,
            winRate: this.winRatePercent(stats.gamesWon, stats.gamesPlayed + 1),
            currentElo: newElo,
            peakElo: Math.max(stats.peakElo, newElo),
            lastPlayedAt: new Date(),
          },
        });
      }
      this.logger.log(
        `Game ${gameId}: draw stats updated — ${firstStats.userId} ${firstStats.currentElo} -> ${ratings.first}, ` +
          `${secondStats.userId} ${secondStats.currentElo} -> ${ratings.second}`,
      );
      return;
    }
    const loserId = stateIds.find((id) => id !== winnerId)!;
    const winnerStats = statsById.get(winnerId);
    const loserStats = statsById.get(loserId);
    if (!winnerStats || !loserStats) {
      throw new Error(`UserStats rows missing after upsert for game ${gameId}`);
    }
    const ratings = this.ratingService.calculateNewRatings(
      winnerStats.currentElo,
      loserStats.currentElo,
    );

    await tx.userStats.update({
      where: { userId: winnerId },
      data: {
        gamesPlayed: winnerStats.gamesPlayed + 1,
        gamesWon: winnerStats.gamesWon + 1,
        winRate: this.winRatePercent(winnerStats.gamesWon + 1, winnerStats.gamesPlayed + 1),
        currentElo: ratings.winner,
        peakElo: Math.max(winnerStats.peakElo, ratings.winner),
        lastPlayedAt: new Date(),
      },
    });
    await tx.userStats.update({
      where: { userId: loserId },
      data: {
        gamesPlayed: loserStats.gamesPlayed + 1,
        gamesLost: loserStats.gamesLost + 1,
        winRate: this.winRatePercent(loserStats.gamesWon, loserStats.gamesPlayed + 1),
        currentElo: ratings.loser,
        lastPlayedAt: new Date(),
      },
    });
    this.logger.log(
      `Game ${gameId}: stats updated — winner ${winnerId} ${winnerStats.currentElo} -> ${ratings.winner}, loser ${loserId} ${loserStats.currentElo} -> ${ratings.loser}`,
    );
  }

  private winRatePercent(won: number, total: number): number {
    if (total === 0) return 0;
    return Math.round((won / total) * 100 * 100) / 100;
  }

  /**
   * ELO при ничьей (Sa = 0.5 у обоих) — та же формула и K-фактор, что у
   * RatingService.calculateNewRatings; там draw-случая нет. Равные рейтинги
   * не меняются, неравные сходятся.
   */
  private calculateDrawRatings(firstElo: number, secondElo: number): { first: number; second: number } {
    const k = this.ratingService.getKFactor();
    const firstExpected = 1 / (1 + Math.pow(10, (secondElo - firstElo) / 400));
    return {
      first: Math.round(firstElo + k * (0.5 - firstExpected)),
      second: Math.round(secondElo + k * (0.5 - (1 - firstExpected))),
    };
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
   *
   * Redis сериализует через JSON: Date-поля (metadata.lastActionAt,
   * combatInfo.startedAt/timeoutAt) возвращаются ISO-строками. Executor и
   * guard'ы зовут .getTime() напрямую — без revival здесь cache-hit ронял
   * playDefense/resolveCombat ('timeoutAt.getTime is not a function').
   * DB-путь оживляет через deserialize; кеш-путь обязан быть эквивалентен.
   */
  async getCachedState(gameId: string): Promise<GameState | null> {
    const cacheKey = `${this.STATE_CACHE_PREFIX}${gameId}`;
    const cached = await this.redis.getJson<GameState>(cacheKey);
    if (!cached) return null;
    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      select: { status: true, version: true },
    });
    const expectedStatus = cached.phase === GamePhase.GAME_OVER
      ? GameStatus.FINISHED
      : GameStatus.IN_PROGRESS;
    if (game?.status !== expectedStatus || game.version !== cached.sequenceNumber) {
      return null;
    }
    const ci = cached.metadata?.combatInfo;
    return {
      ...cached,
      metadata: {
        ...cached.metadata,
        lastActionAt: new Date(cached.metadata.lastActionAt),
        combatInfo: ci
          ? {
              ...ci,
              startedAt: new Date(ci.startedAt),
              ...(ci.timeoutAt ? { timeoutAt: new Date(ci.timeoutAt) } : {}),
            }
          : undefined,
      },
    };
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
        df: f.isDefeated,
        mv: f.movement,
        at: f.attackType,
        sl: f.heroSlug,
      })),
      d: Object.entries(state.decks).reduce(
        (acc, [userId, deck]) => {
          acc[userId] = {
            c: deck.drawPile.length,
            tc: deck.topCard,
            cards: deck.cards,
            pile: deck.drawPile,
          };
          return acc;
        },
        {} as Record<string, SerializedDeck>,
      ),
      dp: state.discardPiles,
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
        cells: state.boardState.cells,
        w: state.boardState.width,
        h: state.boardState.height,
      },
      m: {
        la: state.metadata.lastActionAt.toISOString(),
        lb: state.metadata.lastActionBy,
        v: state.metadata.version,
        ar: state.metadata.actionsRemaining,
        ci: state.metadata.combatInfo
          ? {
              aid: state.metadata.combatInfo.attackerId,
              did: state.metadata.combatInfo.defenderId,
              tf: state.metadata.combatInfo.targetFighterId,
              ac: state.metadata.combatInfo.attackerCardId,
              dc: state.metadata.combatInfo.defenderCardId,
              av: state.metadata.combatInfo.attackValue,
              bv: state.metadata.combatInfo.boostValue,
              cbc: state.metadata.combatInfo.cardBoostCardId,
              abc: state.metadata.combatInfo.abilityBoostCardId,
              dv: state.metadata.combatInfo.defenseValue,
              sa: new Date(state.metadata.combatInfo.startedAt).toISOString(),
              ta: state.metadata.combatInfo.timeoutAt
                ? new Date(state.metadata.combatInfo.timeoutAt).toISOString()
                : undefined,
            }
          : undefined,
        pc: state.metadata.passCount,
        wi: state.metadata.winnerId,
        tsp: state.metadata.turnStartPositions as Record<string, { x: number; y: number }> | undefined,
        pe: state.metadata.pendingEffects,
        pm: state.metadata.pendingManeuver,
        phd: state.metadata.pendingHandDiscard,
        cc: state.metadata.combatEffectContinuation,
        cp: state.metadata.combatResolutionProgress,
        // Per-turn флаги действий (TASK)
        mt: state.metadata.maneuveredThisTurn,
        at: state.metadata.attackedThisTurn,
        lc: state.metadata.lostCombatThisTurn,
        // STANCE: текущие стойки героев по userId (легаси-сейвы без поля → undefined)
        hs: state.metadata.heroStances as Record<string, string> | undefined,
        // GD-016: явный первый игрок матча (легаси-сейвы без поля → undefined)
        fp: state.metadata.firstPlayerId,
        // GD-018: отложенная передача хода (легаси-сейвы без поля → undefined)
        pte: state.metadata.pendingTurnEnd,
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

    // Легаси-состояния могли быть сохранены без cells/w/h, а engine-BoardState
    // требует их обязательно — fallback на пустую сетку 20×20
    const hasCells = Array.isArray(data.b?.cells) && data.b.cells.length > 0;
    const fallbackBoard = hasCells ? null : createEmptyBoardState(20, 20);

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
        isDefeated: f.df,
        // БЕЗ дефолта: undefined прозрачно проходит, дефолтит getFighterMovement
        movement: f.mv,
        // БЕЗ дефолта: undefined прозрачно проходит, дефолтит getFighterAttackType
        attackType: f.at as Fighter['attackType'],
        heroSlug: f.sl,
      })),
      decks: Object.entries(data.d).reduce(
        (acc, [userId, deck]: [string, any]) => {
          acc[userId] = {
            cards: deck.cards ?? [],
            drawPile: deck.pile ?? [],
            topCard: deck.tc,
          };
          return acc;
        },
        {} as Record<string, DeckState>,
      ),
      discardPiles: data.dp ?? {},
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
        cells: hasCells ? data.b.cells : fallbackBoard.cells,
        width: data.b.w ?? 20,
        height: data.b.h ?? 20,
      },
      metadata: {
        lastActionAt: new Date(data.m.la),
        lastActionBy: data.m.lb,
        version: data.m.v,
        // БЕЗ дефолта: undefined прозрачно проходит, дефолтит getActionsRemaining
        actionsRemaining: data.m.ar,
        combatInfo: data.m.ci
          ? {
              attackerId: data.m.ci.aid,
              defenderId: data.m.ci.did,
              targetFighterId: data.m.ci.tf,
              attackerCardId: data.m.ci.ac,
              defenderCardId: data.m.ci.dc,
              attackValue: data.m.ci.av,
              boostValue: data.m.ci.bv,
              cardBoostCardId: data.m.ci.cbc,
              abilityBoostCardId: data.m.ci.abc,
              defenseValue: data.m.ci.dv,
              startedAt: new Date(data.m.ci.sa),
              timeoutAt: data.m.ci.ta ? new Date(data.m.ci.ta) : undefined,
            }
          : undefined,
        passCount: data.m.pc,
        winnerId: data.m.wi,
        turnStartPositions: data.m.tsp,
        pendingEffects: data.m.pe,
        pendingManeuver: data.m.pm,
        pendingHandDiscard: data.m.phd,
        combatEffectContinuation: data.m.cc,
        combatResolutionProgress: data.m.cp,
        // Per-turn флаги действий (TASK): undefined прозрачно проходит (легаси)
        maneuveredThisTurn: data.m.mt,
        attackedThisTurn: data.m.at,
        lostCombatThisTurn: data.m.lc,
        // STANCE: текущие стойки героев (undefined прозрачно проходит — легаси)
        heroStances: data.m.hs,
        // GD-016: явный первый игрок (undefined прозрачно проходит — легаси)
        firstPlayerId: data.m.fp,
        // GD-018: отложенная передача хода (легаси-сейвы без поля → undefined)
        pendingTurnEnd: data.m.pte,
      },
    };
  }

  /**
   * GD-025/ACC-009: является ли viewer участником игры (GamePlayer).
   * Единственная проверка для гейта «spectator не получает состояние».
   */
  async isParticipant(gameId: string, userId: string): Promise<boolean> {
    const player = await this.prisma.gamePlayer.findUnique({
      where: { gameId_userId: { gameId, userId } },
      select: { id: true },
    });
    return player !== null;
  }

  /**
   * Отфильтровать приватные данные для конкретного игрока
   * - Скрывает карты в руке соперника
   * - Скрывает порядок и верхнюю карту обеих колод, сохраняя их размеры
   */
  filterPrivateData(state: GameState, playerId: string): GameState {
    // Иммутабельно: собираем новые handZones/decks спредами (engine-GameState readonly)
    // An allowlist avoids leaking instance/catalog IDs, type, banner or future fields.
    const hiddenCard = (_card: Card, index: number): Card => ({
      id: `hidden-${index}`,
      cardId: 'hidden',
      name: '???',
      nameEn: 'Hidden',
      nameRu: 'Скрыто',
      cardType: CardType.UNIVERSAL,
    });

    // Фильтруем руки других игроков
    const handZones = Object.fromEntries(
      Object.entries(state.handZones).map(([userId, hand]) => {
        if (userId === playerId) {
          return [userId, hand] as const;
        }
        return [
          userId,
          {
            ...hand,
            cards: hand.cards.map((card, index) => ({
              ...hiddenCard(card, index),
              isVisible: false,
            })),
          },
        ] as const;
      }),
    );

    // Even the owner cannot know the next card before beginning a maneuver.
    // Keep array lengths for existing clients; placeholders contain no card identity.
    const decks = Object.fromEntries(
      Object.entries(state.decks).map(([userId, deck]) =>
        [userId, {
          ...deck,
          cards: deck.cards.map(hiddenCard),
          drawPile: deck.drawPile.map(hiddenCard),
          topCard: undefined,
        }] as const,
      ),
    );

    // Execution queues are server-only; player choices remain in pendingEffects.
    const publicMetadata = { ...state.metadata };
    delete publicMetadata.combatEffectContinuation;
    delete publicMetadata.combatResolutionProgress;

    // S06 (GD-021, Prophecy): карты, снятые с верха колоды в DECK_TOP_PICK,
    // видны ТОЛЬКО владельцу выбора; соперник получает счётчик без личин.
    if (publicMetadata.pendingEffects?.some((p) => p.revealedCards?.length)) {
      publicMetadata.pendingEffects = publicMetadata.pendingEffects.map((p) =>
        p.revealedCards && p.playerId !== playerId
          ? { ...p, revealedCards: undefined, revealedCount: p.revealedCards.length }
          : p,
      );
    }

    // GD-017 (R-15) + GD-020: до reveal (executeResolveCombat) бой скрыт.
    // Физическая игра: committed-карты лежат лицом вниз — факт коммита виден,
    // ЛИЧИНА нет. Reveal = запуск executeResolveCombat: обе карты вскрываются
    // ВМЕСТЕ до DURING_COMBAT-выборов (rulebook BoL Vol.1, p.12-13), поэтому
    // паузы ПОСЛЕ reveal (BOOST_CHOICE, during-эффекты) уже не секрет —
    // источник истины: живой combatResolutionProgress (пишется первым же
    // pause() внутри резолва; после завершения боя очищается вместе с
    // combatInfo). Скрываем, пока reveal не начался: phase COMBAT (защитник
    // выбирает карту) или COMBAT_RESOLVE без прогресса (защита сыграна,
    // резолв не запущен):
    // 1) boost-поля combatInfo — от не-атакатора;
    // 2) committed-карты в discardPiles ВЛАДЕЛЬЦА карт — от другого игрока
    //    (атакующая+boost-карты от защитника; защитная карта от атакатора).
    const combatInfo = publicMetadata.combatInfo;
    const combatHidden =
      !!combatInfo &&
      !state.metadata.combatResolutionProgress &&
      (state.phase === GamePhase.COMBAT || state.phase === GamePhase.COMBAT_RESOLVE);

    let discardPiles = state.discardPiles;
    if (combatInfo && combatHidden) {
      const attackerOwner = state.fighters.find((f) => f.id === combatInfo.attackerId)?.ownerId;
      const committedByOwner = new Map<string, ReadonlySet<string>>();
      if (attackerOwner) {
        committedByOwner.set(
          attackerOwner,
          new Set(
            [combatInfo.attackerCardId, combatInfo.cardBoostCardId, combatInfo.abilityBoostCardId].filter(
              (id): id is string => !!id,
            ),
          ),
        );
      }
      if (combatInfo.defenderCardId) {
        const existing = committedByOwner.get(combatInfo.defenderId) ?? new Set<string>();
        committedByOwner.set(
          combatInfo.defenderId,
          new Set([...existing, combatInfo.defenderCardId]),
        );
      }
      discardPiles = Object.fromEntries(
        Object.entries(state.discardPiles).map(([owner, pile]) => {
          const committed = committedByOwner.get(owner);
          // Владелец видит свои committed-карты; чужие — скрыты плейсхолдером
          // (длина сохранена, личины нет).
          if (!committed || committed.size === 0 || owner === playerId) {
            return [owner, pile] as const;
          }
          return [
            owner,
            pile.map((card, index) => (committed.has(card.id) ? hiddenCard(card, index) : card)),
          ] as const;
        }),
      );

      if (combatInfo.boostValue !== undefined && attackerOwner !== playerId) {
        publicMetadata.combatInfo = {
          ...combatInfo,
          boostValue: undefined,
          cardBoostCardId: undefined,
          abilityBoostCardId: undefined,
        };
      }

      // GD-025 (ACC-009, «hidden defense»): до reveal обе committed-карты
      // лежат лицом вниз — их ПЕЧАТНЫЕ ЗНАЧЕНИЯ и instance-id не видны
      // другой стороне. attackValue/attackerCardId — только владельцу
      // атакующей карты; defenseValue/defenderCardId — только защитнику.
      // После reveal (combatResolutionProgress записан первым pause()
      // резолва) значения публичны, как в физической игре (p.12-13).
      const projectedCombat = publicMetadata.combatInfo ?? combatInfo;
      const isAttackOwner = attackerOwner === playerId;
      const isDefender = combatInfo.defenderId === playerId;
      const hiddenCombat: Record<string, unknown> = { ...projectedCombat };
      if (!isAttackOwner) {
        hiddenCombat.attackValue = undefined;
        hiddenCombat.attackerCardId = undefined;
      }
      if (!isDefender && combatInfo.defenderCardId) {
        hiddenCombat.defenseValue = undefined;
        hiddenCombat.defenderCardId = undefined;
      }
      publicMetadata.combatInfo = hiddenCombat as unknown as GameStateMetadata['combatInfo'];
    }

    return { ...state, handZones, decks, discardPiles, metadata: publicMetadata };
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
          [uid]: { cards: [], maxSize: 7 },
        }),
        {},
      ),
      // Engine-BoardState требует cells/width/height — пустая сетка 20×20
      boardState: createEmptyBoardState(20, 20),
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

        // Иммутабельно (engine-GameState readonly): один спред вместо присваиваний
        const updated = updateFn(currentState);
        const newState: GameState = {
          ...updated,
          sequenceNumber: expectedSequence + 1,
          metadata: {
            ...updated.metadata,
            lastActionAt: new Date(),
          },
        };

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
   * Получить события игры с указанного sequence number (для catch-up при реконнекте).
   * GD-025 (ACC-009): журнал хранит server-side метаданные (включая input
   * мутаций с instance-id карт) — в ответ уходит только viewer-безопасное
   * подмножество: input остаётся лишь у СОБСТВЕННЫХ действий зрителя.
   * eventsSince — журнал событий, а НЕ replay состояния (см. сетевой
   * контракт GD-027): full snapshot — отдельный gameState-запрос.
   */
  async getEventsSince(
    gameId: string,
    sinceSequence: number,
    viewerId?: string,
  ): Promise<(GameEvent & { playerId: string | null })[]> {
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

    return actions.map((action) => {
      const stored = (action.payload ?? {}) as Record<string, unknown>;
      const safePayload: Record<string, unknown> = { action: stored.action };
      if (viewerId && action.playerId === viewerId && stored.input != null) {
        safePayload.input = stored.input;
      }
      return {
        sequenceNumber: action.sequenceNumber,
        // Prisma GameActionType и DTO GameEventType — зеркальные строковые enum'ы
        type: action.type as GameEventType,
        gameId: action.gameId,
        playerId: action.playerId,
        // GameEvent.payload — String в GraphQL-схеме, Prisma отдаёт Json-объект
        payload: JSON.stringify(safePayload),
        timestamp: action.timestamp,
      };
    });
  }
}
