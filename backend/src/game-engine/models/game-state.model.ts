/**
 * GameState Model
 *
 * Основная структура состояния игры Unmatched.
 * Используется во всём game-engine модуле.
 */

import type { Fighter, Position } from './fighter.model';
import type { Card, CardEffect, DeckState, HandZone } from './card.model';
import type { BoardState } from './board.model';
import type { CombatResolutionProgress } from '../engine/combat-progress';

/**
 * GD-026: серверные дедлайны боя (секунды). Единственный источник значений
 * для executor'а (combatInfo.timeoutAt), планировщика BullMQ и recovery.
 * timeoutAt в combatInfo — дедлайн ТЕКУЩЕЙ стадии: COMBAT = окно защиты,
 * COMBAT_RESOLVE = окно ручного резолва после защиты.
 */
export const DEFENSE_TIMEOUT_SECONDS = 30;
export const RESOLVE_TIMEOUT_SECONDS = 10;

/**
 * Фазы игры
 */
export enum GamePhase {
  SETUP = 'SETUP', // Подготовка (размещение бойцов)
  TURN_START = 'TURN_START', // Начало хода (способности в начале хода)
  ACTION_MANEUVER = 'ACTION_MANEUVER', // Манёвр
  ACTION_ATTACK = 'ACTION_ATTACK', // Атака
  COMBAT = 'COMBAT', // Бой (ожидание защиты)
  COMBAT_RESOLVE = 'COMBAT_RESOLVE', // Разрешение боя
  TURN_END = 'TURN_END', // Конец хода
  GAME_OVER = 'GAME_OVER', // Игра окончена, победитель определён
}

/**
 * Полное состояние игры
 * Использует readonly для иммутабельности
 */
export interface GameState {
  readonly gameId: string;
  readonly sequenceNumber: number;
  readonly phase: GamePhase;
  readonly turnCount: number;
  readonly currentTurnPlayerId: string;

  // Игроки
  readonly players: readonly GameStatePlayer[];

  // Бойцы на доске
  readonly fighters: readonly Fighter[];

  // Колоды и сброс
  readonly decks: Readonly<Record<string, DeckState>>;
  readonly discardPiles: Readonly<Record<string, readonly Card[]>>;

  // Зоны ручек
  readonly handZones: Readonly<Record<string, HandZone>>;

  // Двери и туман войны
  readonly boardState: BoardState;

  // Метаданные
  readonly metadata: GameStateMetadata;
}

/**
 * Игрок в состоянии игры
 */
export interface GameStatePlayer {
  readonly userId: string;
  readonly heroId: string;
  readonly health: number;
  readonly maxHealth: number;
  readonly fighterIds: readonly string[];
  readonly isAlive: boolean;
}

/**
 * Состояние текущего боя (атака объявлена, ждём защиту/разрешение).
 * Живёт в metadata.combatInfo между executeAttack и executeResolveCombat.
 */
export interface CombatState {
  readonly attackerId: string;
  readonly defenderId: string;
  /** Атакованный боец (id из fighters). Optional — легаси-сейвы без поля:
   *  fallback на первого бойца защитника (старое поведение). */
  readonly targetFighterId?: string;
  readonly attackerCardId: string;
  readonly defenderCardId?: string;
  /** ТОЛЬКО печатное значение атакующей карты (без boost). Легаси-сейвы,
   *  писавшие printed+boost сюда, остаются корректными для расчёта: boost
   *  передаётся отдельно и по умолчанию 0. */
  readonly attackValue: number;
  /** Сумма boost значений (карта-BOOST + ability boost Arthur). Скрыто от
   *  защитника до reveal (filterPrivateData); отменённая карта (Feint, R-16)
   *  не добавляет его к расчёту. Карта-BOOST доигрывается в combatInfo на
   *  резолве BOOST_CHOICE (rulebook p.12-13: выбор ПОСЛЕ reveal). */
  readonly boostValue?: number;
  /** Instance id карты, израсходованной как BOOST-эффект карты (Second Shot);
   *  заполняется на резолве BOOST_CHOICE, НЕ при объявлении атаки */
  readonly cardBoostCardId?: string;
  /** Instance id карты ability-буста Arthur (отдельный слот от cardBoostCardId) */
  readonly abilityBoostCardId?: string;
  readonly defenseValue: number;
  readonly startedAt: Date;
  readonly timeoutAt?: Date;
}

/**
 * Контекст боя для эффектов. Бойцы и игроки — РАЗНЫЕ id:
 * attackerFighterId/targetFighterId — из fighters, *PlayerId — userId.
 */
export interface CombatContext {
  readonly attackerFighterId: string;
  readonly targetFighterId: string;
  readonly attackerPlayerId: string;
  readonly defenderPlayerId: string;
  readonly attackCardId: string;
  readonly defenseCardId?: string;
  readonly attackValue: number;
  readonly defenseValue: number;
}

/**
 * Контекст выполнения эффекта (одна сторона)
 */
export interface EffectContext {
  readonly playerId: string;
  readonly card: Card;
  /** Боец, который играет карту (атакующий или цель атаки) */
  readonly fighterId?: string;
  /** Боец-противник в бою */
  readonly opposingFighterId?: string;
  readonly combat?: CombatContext;
  /** Исход боя (известен только в AFTER_COMBAT): победила ли ЭТА сторона */
  readonly wonCombat?: boolean;
  /** Урон, нанесённый/полученный этой стороной (для count DAMAGE_*) */
  readonly damageDealt?: number;
  readonly damageTaken?: number;
}

/** A serializable, ordered combat stage paused for a player choice. */
export interface CombatEffectContinuation {
  readonly stage: 'ON_REVEAL' | 'DURING_COMBAT' | 'AFTER_COMBAT';
  readonly remaining: readonly { effect: CardEffect; context: EffectContext; isAttacker: boolean }[];
  readonly attackerCardCancelled: boolean;
  readonly defenderCardCancelled: boolean;
  readonly finalAttack: number;
  readonly finalDefense: number;
  readonly preventDamageToAttacker: boolean;
  readonly preventDamageToDefender: boolean;
}

/**
 * MS-T-14 (move-selection 04 §4.3): the BOOST card of a maneuver in the
 * public trail. All fields are public: the card is already in its owner's
 * discard pile, which filterPrivateData shows to the opponent with its
 * instance id (MS-Q-05).
 */
export interface LastMovementBoost {
  /** Instance id of the discarded card (the same id as in discardPiles) */
  readonly cardId: string;
  /** Catalog id (Card.cardId) */
  readonly catalogId: string;
  readonly name: string;
  /** Printed BOOST; null when the card has none */
  readonly value: number | null;
}

/** One movement in the trail, in the order it was applied. */
export interface LastMovementMove {
  readonly order: number;
  readonly fighterId: string;
  /** MOVE: step by step along `path`; PLACE: a jump to the single cell of `path` */
  readonly kind: 'MOVE' | 'PLACE';
  /** Position before this movement (after the previous moves of the same maneuver) */
  readonly from: Position;
  /** Cells WITHOUT the start (the maneuver wire format); PLACE — the target only */
  readonly path: readonly Position[];
}

/**
 * MS-T-14 (04 §4.3, MS-D-11): public trail of the last recorded movement.
 * Written by executeManeuver (source MANEUVER) and by the resolution of a
 * pending MOVE/PLACE effect (source EFFECT); hero abilities and reactions do
 * not write it. It lives until the next recorded movement replaces it: the
 * client uses it only when `seq` equals the applied snapshot's sequenceNumber.
 * Stored in the DB under the short key `lm`; saves without it read as "no trail".
 */
export interface LastMovement {
  /** sequenceNumber of the state this movement produced */
  readonly seq: number;
  /** Player whose command or choice moved the fighters */
  readonly playerId: string;
  readonly source: 'MANEUVER' | 'EFFECT';
  /** MANEUVER — the maneuverId; EFFECT — the id of the resolved pending effect */
  readonly sourceRef: string;
  /** MANEUVER with a BOOST card only; null otherwise */
  readonly boost: LastMovementBoost | null;
  /** In the order applied; fighters that stayed are not listed ([] = nothing moved) */
  readonly moves: readonly LastMovementMove[];
}

/** DE-016: why an effect was skipped without waiting for input (why.effect.no.targets on the client). */
export type SkippedEffectReason = 'NO_VALID_TARGETS';

/**
 * DE-016 (D-DE-11, SD-10, SD-16): an effect the server skipped because it had
 * no legal target — a choice is never left waiting without a highlighted
 * target. Kept in metadata.skippedEffects (the last SKIPPED_EFFECTS_KEPT
 * notes, oldest first). Stored in the DB under the short key `se`.
 */
export interface SkippedEffect {
  /** Monotonic within the game (1, 2, …): the client explains every note whose n is above the last it has seen */
  readonly n: number;
  /** sequenceNumber of the state the skip was made on; the snapshot that first carries the note has seq >= it */
  readonly seq: number;
  readonly reason: SkippedEffectReason;
  /** Owner of the effect (the player who would have chosen) */
  readonly playerId: string;
  /** PendingEffect.id of a dropped choice, CardEffect.id of an automatic effect */
  readonly effectId: string;
  /** PendingEffect.type of a dropped choice, EffectType of an automatic effect */
  readonly kind: string;
  /** Printed effect text, when known */
  readonly text?: string;
}

/** How many SkippedEffect notes metadata keeps */
export const SKIPPED_EFFECTS_KEPT = 8;

/**
 * Метаданные состояния
 */
export interface GameStateMetadata {
  /** Maneuver has drawn and spent its action; movement/boost still await the owner. */
  readonly pendingManeuver?: { readonly id: string; readonly playerId: string };
  /** MS-T-14: public trail of the last maneuver or MOVE/PLACE effect (see LastMovement) */
  readonly lastMovement?: LastMovement;
  /** DE-016: effects skipped for lack of a legal target (see SkippedEffect) */
  readonly skippedEffects?: readonly SkippedEffect[];
  /** End-turn effects have completed; selected excess instances must be discarded. */
  readonly pendingHandDiscard?: { readonly id: string; readonly playerId: string; readonly count: number };
  readonly lastActionAt: Date;
  readonly lastActionBy: string;
  readonly version: number;
  readonly compressed?: boolean; // Опционально: сжатие для оптимизации
  // Фактический контракт executor'а/guard'ов (раньше писался через "as any"):
  readonly combatResolutionProgress?: CombatResolutionProgress;
  readonly combatEffectContinuation?: CombatEffectContinuation;
  readonly combatInfo?: CombatState; // Текущий бой (между attack и resolveCombat)
  readonly passCount?: number; // Счётчик pass-действий
  readonly winnerId?: string; // Победитель (заполняется при GAME_OVER)
  /** Оставшиеся действия текущего игрока в этом ходу (легаси-сейвы без поля → дефолт в getActionsRemaining) */
  readonly actionsRemaining?: number;
  /** Позиции бойцов на начало хода (пишет advanceTurn) — для условия
   *  MOVED_THIS_TURN («started this turn in a different space») */
  readonly turnStartPositions?: Readonly<Record<string, { x: number; y: number }>>;
  /** Эффекты, ждущие выбора игрока (MOVE/PLACE из карт) — резолвятся
   *  мутацией resolvePendingEffect; протухают при передаче хода */
  readonly pendingEffects?: readonly PendingEffect[];
  /** Per-turn флаги действий текущего игрока (TASK): нужны combat-условиям
   *  способностей («сделал ли манёвр / атаковал ли / первый ли проигрыш в этом
   *  ходу»). Выставляются в executor'е, сбрасываются в advanceTurn при передаче
   *  хода. Легаси-сейвы без полей → undefined (трактуется как false). */
  /** Игрок выполнил MANEUVER в этом ходу (executeManeuver) */
  readonly maneuveredThisTurn?: boolean;
  /** Игрок завершил хотя бы одну атаку в этом ходу (конец executeResolveCombat) */
  readonly attackedThisTurn?: boolean;
  /** Игрок проиграл хотя бы один бой в этом ходу (executeResolveCombat, won===false) */
  readonly lostCombatThisTurn?: boolean;
  /**
   * STANCE-подсистема: текущая стойка героя КАЖДОГО игрока (id стойки из
   * AbilityConfig.stances), ключ — userId. Меняется мутацией setStance
   * (выбор при размещении / «Change size»-карты) и авто-эффектами способностей
   * (set-stance/cycle-stance). Легаси-сейвы без поля → undefined: handler
   * фолбэчит на стойку с default:true (или первую в config.stances).
   */
  readonly heroStances?: Readonly<Record<string, string>>;
  /** Явный первый игрок матча (GD-016): ставится при инициализации,
   *  не меняется после; currentTurnPlayerId двигается по ходу игры. */
  readonly firstPlayerId?: string;
  /** GD-018: передача хода отложена до дренирования очереди выборов
   *  (pendingEffects). endEffectsApplied — были ли уже выполнены TURN_END-хуки
   *  завершающего игрока (true — не повторять при возобновлении). */
  readonly pendingTurnEnd?: { readonly playerId: string; readonly endEffectsApplied?: boolean };
}

/**
 * Эффект карты, требующий выбора игрока (C2).
 * During combat the pending choice blocks the remaining combat chain and actions.
 * Other legacy pending effects retain their existing turn-expiry behavior.
 */
export interface PendingEffect {
  readonly id: string;
  /** Combat choices retain exact participants and effect context across resume. */
  readonly fighterIds?: readonly string[];
  readonly effectContext?: EffectContext;
  /**
   * 'MOVE' (до value шагов) | 'PLACE' (любая свободная клетка) |
   * 'CHOOSE_ONE' (игрок выбирает chooseCount опций из options) |
   * 'TARGET_FIGHTER' (выбор бойца-цели из targetFighterIds; damage применяется сразу) |
   * 'DISCARD_CARDS' (владелец выбора сбрасывает ровно value своих карт из руки;
   * печатный сброс БЕЗ слова «random» — карту выбирает сбрасывающий, не движок) |
   * 'BOOST_CHOICE' (S05: optional BOOST this attack/defense — «You may BOOST…»
   * карты эффекта; владелец СВОЕЙ руки выбирает ОДНУ карту как буст ПОСЛЕ
   * reveal, в паузе DURING_COMBAT; резолв — cardIds[0], отказ — decline) |
   * 'CHOOSE_SPACE' (S06 GD-022, Restless Spirits: stage 1 — клетка в зоне
   * zoneFighterName; stage 2 — клетка, смежная с anchor; затем damage урона
   * каждому вражескому бойцу обеих клеток + условный добор drawIfDefeated) |
   * 'DECK_TOP_PICK' (S06 GD-021, Prophecy: mode 'PICK' — cardIds ровно
   * pickCount из revealedCards уходят в руку; mode 'ORDER' — cardIds задают
   * порядок возврата остатка НАВЕРХ колоды; revealedCards видны ТОЛЬКО
   * владельцу выбора — filterPrivateData прячет их от соперника)
   */
  readonly type: 'MOVE' | 'PLACE' | 'CHOOSE_ONE' | 'TARGET_FIGHTER' | 'DISCARD_CARDS' | 'BOOST_CHOICE' | 'CHOOSE_SPACE' | 'DECK_TOP_PICK';
  /** Кому принадлежит выбор */
  readonly playerId: string;
  /** Дистанция для MOVE; количество карт для DISCARD_CARDS */
  readonly value?: number;
  /** Ограничение бойца: имя из текста карты («Move Daredevil…») */
  readonly fighterName?: string;
  /** Двигается боец противника («Place the opposing fighter…») */
  readonly targetsOpponent?: boolean;
  /** TARGET_FIGHTER: допустимые цели (живые бойцы, revalidated на резолве) */
  readonly targetFighterIds?: readonly string[];
  /** TARGET_FIGHTER: урон выбранной цели */
  readonly damage?: number;
  /** MOVE: путь может проходить через врагов (Winged Frenzy) */
  readonly canPassThroughEnemies?: boolean;
  /** PLACE: клетка обязана делить зону с этим бойцом (return Harpy в зону Medusa) */
  readonly zoneFighterName?: string;
  /** PLACE: revive — боец может быть defeated, возвращается с maxHealth */
  readonly restoreFullHealth?: boolean;
  /** MOVE (Skirmish): разрешён ЛЮБОЙ боец из fighterIds — свой или чужой
   *  («choose one of the fighters in the combat»); ownership-check выключен */
  readonly anyOwner?: boolean;
  /** CHOOSE_SPACE: стадия 1 (клетка в зоне) | 2 (клетка, смежная с anchor) */
  readonly stage?: 1 | 2;
  /** CHOOSE_SPACE stage 2: выбранная в stage 1 клетка-якорь смежности */
  readonly anchor?: { readonly x: number; readonly y: number };
  /** CHOOSE_SPACE: условный добор при ≥1 повержённом уроном эффекта */
  readonly drawIfDefeated?: number;
  /** DECK_TOP_PICK: карты, снятые с верха колоды (только для владельца выбора) */
  readonly revealedCards?: readonly Card[];
  /** DECK_TOP_PICK: сколько карт открыто — ВИДНО сопернику (без личин) */
  readonly revealedCount?: number;
  /** DECK_TOP_PICK: стадия выбора — PICK (взять в руку) | ORDER (порядок возврата) */
  readonly mode?: 'PICK' | 'ORDER';
  /** Исходный текст — для лога/тестера */
  readonly text?: string;

  // --- CHOOSE_ONE («Choose one: …») ---
  /** Варианты выбора для UI: индекс + текст опции */
  readonly options?: ReadonlyArray<{ readonly index: number; readonly label: string }>;
  /** Сколько опций выбрать (default 1; «choose 2 different effects» = 2) */
  readonly chooseCount?: number;
  /** Эффекты каждой опции (параллельно options) — исполняются при резолве */
  readonly optionEffects?: ReadonlyArray<readonly CardEffect[]>;
  /** Карта-источник CHOOSE_ONE — контекст для исполнения эффектов опции */
  readonly card?: Card;
  /** GD-018: «You may …» — выбор можно отклонить (declinePendingEffect).
   *  Mandatory-выборы отклонять нельзя. */
  readonly optional?: boolean;
}

/**
 * Действий за ход по правилам Unmatched: ровно 2
 * (манёвр / атака / scheme в любой комбинации, атаковать можно дважды).
 */
export const ACTIONS_PER_TURN = 2;

/**
 * Оставшиеся действия текущего игрока. Единственная точка дефолта
 * (паттерн getFighterMovement): легаси-сейвы/мусор (null, NaN, отрицательное,
 * строка) → ACTIONS_PER_TURN.
 */
export function getActionsRemaining(state: GameState): number {
  const n = Number(state.metadata.actionsRemaining);
  return Number.isInteger(n) && n >= 0 ? n : ACTIONS_PER_TURN;
}
