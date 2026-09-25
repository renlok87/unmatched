/**
 * Game Action Executor Service
 *
 * Единая точка входа для выполнения всех игровых действий в Unmatched.
 * Инкапсулирует логику выполнения действий с валидацией и изменением состояния.
 *
 * Все действия следуют единому паттерну:
 * 1. Валидация через GameRulesValidator
 * 2. Выполнение через соответствующий engine service
 * 3. Возврат результата с обновлённым состоянием
 */

import { Injectable, Logger, BadRequestException } from '@nestjs/common';
import { MetricsService } from '../../metrics/metrics.service';
// P3: единые engine-модели (GameState/GamePhase/CombatState) — value-импорт
// engine→games убран, рантайм-цикла модулей больше нет
import type { GameState, CombatState, HandCard, Card, PendingEffect } from '../models';
import {
  GamePhase,
  CardType,
  FighterType,
  createEmptyBoardState,
  ACTIONS_PER_TURN,
  getActionsRemaining,
  getFighterAttackType,
} from '../models';
import {
  HeroAbilityRegistry,
  ValueModifierType,
  type ValueModifier,
  type AfterCombatContext,
} from '../abilities/hero-ability-registry';
import {
  CardEffectExecutorService,
  fighterNameMatches,
  type EffectResult,
} from '../effects/card-effect-executor.service';
import { GameRulesValidator, bannerAllows } from '../validators/game-rules.validator';
import { CombatResolverService } from '../engine/combat-resolver.service';
import { MovementService } from '../engine/movement.service';
import { isCellPassable, isLivingFighter } from '../movement/traversal';
import { ValueModifierService } from '../engine/value-modifier.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { DeckManagementService } from './deck-management.service';
import { applyTerminalState } from '../engine/terminal-state';
import type { CombatResolutionProgress } from '../engine/combat-progress';
// Residual-импорт engine→games: DTO-классы мутаций (runtime-импорт, но уже не
// value-критичный цикл — состояние/фазы идут из ../models). Перенос DTO — вне скоупа F3.
import {
  ManeuverDto,
  MoveFighterDto,
  AttackDto,
  PlayDefenseDto,
  PlaySchemeDto,
  ResolveCombatDto,
  EndTurnDto,
  PassDto,
  ToggleDoorDto,
} from '../../games/dto/gameplay.dto';

/**
 * Результат выполнения игрового действия
 */
export interface ActionResult {
  readonly success: boolean;
  readonly gameState?: GameState;
  readonly error?: string;
  readonly metadata?: {
    readonly action: string;
    readonly performedAt: Date;
    readonly performedBy: string;
    readonly sequenceNumber: number;
    // playScheme: текст эффекта карты (для ручного применения в Game Tester)
    readonly effectText?: string;
    // playScheme: авто-применённые эффекты карты (best-effort, обычно пусто)
    readonly appliedEffects?: readonly EffectResult[];
    // Эффекты, требующие ручного применения (MOVE/PLACE/UNSUPPORTED) —
    // Game Tester печатает их в лог
    readonly manualEffects?: readonly string[];
    // resolveCombat: итог боя для лога
    readonly combatSummary?: {
      readonly finalAttack: number;
      readonly finalDefense: number;
      readonly attackerDamage: number;
      readonly defenderDamage: number;
      readonly attackerWon: boolean;
      readonly attackerCardCancelled: boolean;
      readonly defenderCardCancelled: boolean;
    };
  };
}

/**
 * Контекст выполнения действия
 */
export interface ActionContext {
  readonly userId: string;
  readonly gameId: string;
  readonly currentState: GameState;
}

/**
 * Параметры создания начального состояния игры
 */
export interface InitialGameStateParams {
  readonly gameId: string;
  readonly players: readonly {
    readonly userId: string;
    readonly heroId: string;
    readonly health: number;
    readonly maxHealth: number;
  }[];
  readonly boardId: string;
}

// Состояние боя (CombatState) перенесено в ../models/game-state.model —
// единый типизированный контракт metadata.combatInfo для executor'а и guard'ов

@Injectable()
export class GameActionExecutorService {
  private readonly logger = new Logger(GameActionExecutorService.name);

  constructor(
    private readonly rulesValidator: GameRulesValidator,
    private readonly combatResolver: CombatResolverService,
    private readonly movementService: MovementService,
    private readonly valueModifier: ValueModifierService,
    private readonly adjacencyService: AdjacencyService,
    private readonly metrics: MetricsService,
    private readonly deckManagement: DeckManagementService,
    private readonly cardEffectExecutor: CardEffectExecutorService,
    private readonly abilityRegistry: HeroAbilityRegistry,
  ) {}

  /**
   * Способность героя разрешает BOOST атаки (R-15: King Arthur) — только если
   * играющий боец является HERO-бойцом этого героя (heroSlug/heroId совпадает
   * с ключом handler'а). Атака сайдкика (Merlin) способность не активирует.
   */
  private abilityBoostAllowed(
    fighter: { heroSlug?: string; heroId: string; type?: string } | undefined,
  ): boolean {
    if (!fighter) return false;
    const slug = fighter.heroSlug ?? fighter.heroId;
    const handler = this.abilityRegistry.getAny(slug) as
      | { allowsAttackBoost?: boolean; heroId?: string }
      | undefined;
    if (!handler?.allowsAttackBoost) return false;
    if (fighter.type !== undefined && fighter.type !== 'HERO') return false;
    return handler.heroId === slug;
  }

  /**
   * Передать ход следующему живому игроку.
   *
   * Фаза TURN_START исключена из продакшен-потока: ход сразу начинается
   * с ACTION_MANEUVER без автоматического добора карты.
   * Используется в executeEndTurn, executeResolveCombat и consumeAction
   * (авто-завершение хода после 2-го действия).
   *
   * ВАЖНО (контракт saveState): +1 к sequenceNumber только при incrementSeq=true —
   * тогда входное состояние должно приходить БЕЗ собственного инкремента.
   * incrementSeq=false — для вызова из consumeAction, где +1 уже сделало само действие.
   */
  /** GD-018: отложить передачу хода — очередь выборов ещё открыта. */
  private deferTurnEnd(
    state: GameState,
    incrementSeq: boolean,
    endEffectsApplied: boolean,
  ): GameState {
    return {
      ...state,
      sequenceNumber: state.sequenceNumber + (incrementSeq ? 1 : 0),
      metadata: {
        ...state.metadata,
        actionsRemaining: 0,
        pendingTurnEnd: { playerId: state.currentTurnPlayerId, endEffectsApplied },
      },
    };
  }

  /**
   * GD-018: общая точка дренирования после resolve/decline последнего выбора.
   * Очередь пуста →
   *  a) бой на паузе (combatResolutionProgress) → ре-вход в executeResolveCombat
   *     (seq базового резолва уже учтён через baseSeq);
   *  b) отложенная передача хода (pendingTurnEnd) → advanceTurn с
   *     incrementSeq=false (+1 уже сделала сама мутация резолва) и
   *     endEffectsApplied из marker'а (не повторять TURN_END-хуки);
   *  c) иначе — состояние как есть (ход продолжается).
   */
  private async drainAfterChoice(
    resolved: GameState,
    userId: string,
    gameId: string,
    baseSeq: number,
  ): Promise<GameState> {
    if (resolved.phase === GamePhase.GAME_OVER) return resolved;
    if ((resolved.metadata.pendingEffects?.length ?? 0) > 0) return resolved;
    if (resolved.metadata.combatResolutionProgress) {
      const resumed = await this.executeResolveCombat({ gameId }, {
        userId, gameId, currentState: { ...resolved, sequenceNumber: baseSeq },
      });
      return resumed.success ? resumed.gameState! : resolved;
    }
    if (resolved.metadata.pendingTurnEnd) {
      return this.advanceTurn(resolved, userId,
        /* incrementSeq */ false,
        resolved.metadata.pendingTurnEnd.endEffectsApplied ?? true);
    }
    return resolved;
  }

  private async advanceTurn(
    state: GameState,
    userId: string,
    incrementSeq = true,
    endEffectsApplied = false,
  ): Promise<GameState> {
    // GD-018 (ACC-008): открытая очередь выборов блокирует передачу хода —
    // истечение круга НЕ заменяет решение. Откладываем передачу через
    // persisted-marker pendingTurnEnd; hooks ещё не выполнялись.
    if ((state.metadata.pendingEffects?.length ?? 0) > 0) {
      return this.deferTurnEnd(state, incrementSeq, false);
    }

    // TURN_END-способности героя выполняются перед возможным выбором сброса,
    // поэтому extended-хук onTurnEnd встраивается ЗДЕСЬ — у
    // ЗАВЕРШАЮЩЕГО игрока, ДО снятия duration:'turn' эффектов и ДО
    // переключения currentTurnPlayerId. seq НЕ бампим отдельно: хук
    // «прицеплен» к той же передаче хода (+1 ниже), контракт saveState как у
    // turn-start. No-op для героев без onTurnEnd.
    const endingPlayerId = state.currentTurnPlayerId;
    if (!endEffectsApplied) state = await this.triggerHeroTurnEnd(state, endingPlayerId);
    state = applyTerminalState(state);
    if (state.phase === GamePhase.GAME_OVER) {
      return { ...state, sequenceNumber: state.sequenceNumber + (incrementSeq ? 1 : 0) };
    }

    // GD-018: TURN_END-хук сам создал выборы — передача снова отложена,
    // но хуки уже выполнены (не повторять при возобновлении).
    if ((state.metadata.pendingEffects?.length ?? 0) > 0) {
      return this.deferTurnEnd(state, incrementSeq, true);
    }

    // Seven is an end-of-turn limit, never a draw limit. Keep the turn until
    // its owner selects exact instances; resume without replaying end effects.
    const excess = (state.handZones[endingPlayerId]?.cards.length ?? 0) - 7;
    if (excess > 0) {
      return { ...state, phase: GamePhase.TURN_END,
        sequenceNumber: state.sequenceNumber + (incrementSeq ? 1 : 0),
        metadata: { ...state.metadata, actionsRemaining: 0,
          pendingHandDiscard: { id: `discard:${state.turnCount}:${state.sequenceNumber}`, playerId: endingPlayerId, count: excess },
          lastActionAt: new Date(), lastActionBy: userId } };
    }

    // Находим следующего живого игрока по кругу
    const currentPlayerIndex = state.players.findIndex(
      (p) => p.userId === state.currentTurnPlayerId,
    );

    let nextPlayerIndex = (currentPlayerIndex + 1) % state.players.length;
    let attempts = 0;

    while (!state.players[nextPlayerIndex].isAlive && attempts < state.players.length) {
      nextPlayerIndex = (nextPlayerIndex + 1) % state.players.length;
      attempts++;
    }

    const nextPlayerId = state.players[nextPlayerIndex].userId;
    const isSamePlayer = nextPlayerId === state.currentTurnPlayerId;

    // Turn transfer itself never draws. Explicit hero hooks still may draw.
    const next = state;

    // Эффекты «до конца хода» (immobilized и т.п.) снимаются на передаче хода
    const fightersCleaned = next.fighters.map((f) =>
      f.effects.some((e) => e.duration === 'turn')
        ? { ...f, effects: f.effects.filter((e) => e.duration !== 'turn') }
        : f,
    );

    // Снапшот позиций на начало нового хода — условие MOVED_THIS_TURN
    // («started this turn in a different space»)
    const turnStartPositions = Object.fromEntries(
      fightersCleaned.map((f) => [f.id, { x: f.position.x, y: f.position.y }]),
    );

    let started: GameState = {
      ...next,
      fighters: fightersCleaned,
      phase: GamePhase.ACTION_MANEUVER,
      currentTurnPlayerId: nextPlayerId,
      turnCount: isSamePlayer ? state.turnCount : state.turnCount + 1,
      sequenceNumber: incrementSeq ? state.sequenceNumber + 1 : state.sequenceNumber,
      metadata: {
        ...next.metadata,
        lastActionAt: new Date(),
        lastActionBy: userId,
        actionsRemaining: ACTIONS_PER_TURN, // новый ход — 2 действия
        pendingManeuver: undefined,
        pendingHandDiscard: undefined,
        turnStartPositions,
        // Per-turn флаги действий сбрасываются при передаче хода (TASK): у нового
        // активного игрока свежий ход — ещё не манёврил, не атаковал, не проигрывал.
        // Один общий набор флагов (за ход действует только один игрок).
        maneuveredThisTurn: false,
        attackedThisTurn: false,
        lostCombatThisTurn: false,
        // GD-018: отложенная передача выполнена — marker снят. Выборы больше
        // не протухают при передаче/возврате хода (удалённый circle-expiry
        // фильтр молча заменял решение игрока).
        pendingTurnEnd: undefined,
      },
    };

    // TURN_START-способности героя (TASK A): фаза TURN_START исключена из
    // потока, поэтому extended-хук onTurnStart встраивается ЗДЕСЬ — в
    // единственной точке, где у игрока реально начинается ход. Дизайн:
    //  - продакшен-поток зовёт ТОЛЬКО extended-диспетчер (мутирует GameState);
    //  - GameEvent[]-путь (triggerOnTurnStart) остаётся за логированием.
    // No-op-контракт: handler без onTurnStart (или вернувший state без
    // изменений — напр. ms-marvel, резерв) ничего не меняет и поток хода цел
    // (фаза остаётся ACTION_MANEUVER). seq НЕ инкрементируется отдельно —
    // мутация-хук «прицеплена» к той же передаче хода (контракт saveState).
    started = await this.triggerHeroTurnStart(started, nextPlayerId);

    // TURN_START-способность могла нанести смертельный урон (damage-эффект):
    // герой противника повержен, его игрок isAlive=false. Пере-проверяем
    // game-over ПОСЛЕ хука — иначе игра «зависла» бы в ACTION_MANEUVER при
    // фактически побеждённом сопернике. No-op, если никто не умер (живых > 1):
    // обычный turn-start героев без урона оставляет фазу ACTION_MANEUVER.
    // seq НЕ бампим: «прицеплено» к той же передаче хода (+1 выше).
    started = this.checkAndApplyGameOver(started);

    return started;
  }

  /**
   * Вызвать extended-хук onTurnStart героя текущего игрока (TASK A, infra).
   *
   * Слаг для реестра берём с бойца-героя игрока (heroSlug ?? heroId) — тот же
   * предикат, что в combat/turn-end путях. Возвращает (возможно) мутированный
   * GameState; для героев без хука — исходное состояние без изменений.
   * sequenceNumber не трогаем: вызывающий advanceTurn уже сделал свой +1.
   */
  private async triggerHeroTurnStart(
    state: GameState,
    playerId: string,
  ): Promise<GameState> {
    const heroFighter = state.fighters.find((f) => f.ownerId === playerId);
    if (!heroFighter) {
      return state;
    }
    const slug = heroFighter.heroSlug ?? heroFighter.heroId;
    return this.abilityRegistry.triggerOnTurnStartExtended(slug, state, playerId);
  }

  /**
   * Вызвать extended-хук onTurnEnd героя ЗАВЕРШАЮЩЕГО игрока (TASK, infra).
   *
   * Зеркало triggerHeroTurnStart: слаг бойца-героя игрока (heroSlug ?? heroId),
   * await extended-диспетчера triggerOnTurnEndExtended, замена state результатом.
   * Для героев без хука — исходное состояние без изменений. sequenceNumber не
   * трогаем: вызывающий advanceTurn делает свой +1 на передаче хода.
   */
  private async triggerHeroTurnEnd(
    state: GameState,
    playerId: string,
  ): Promise<GameState> {
    const heroFighter = state.fighters.find((f) => f.ownerId === playerId);
    if (!heroFighter) {
      return state;
    }
    const slug = heroFighter.heroSlug ?? heroFighter.heroId;
    return this.abilityRegistry.triggerOnTurnEndExtended(slug, state, playerId);
  }

  /**
   * Вызвать after-combat хук АТАКУЮЩЕГО героя (TASK, infra).
   *
   * Зеркало triggerHeroTurnEnd: слаг берём с АТАКУЮЩЕГО бойца
   * (heroSlug ?? heroId) — combatInfo.attackerId, даже если боец уже повержен
   * (объект остаётся в state.fighters с isDefeated=true). Если бойца в state
   * вовсе нет — no-op. await extended-диспетчера triggerOnAfterCombat, замена
   * state результатом. Для героев без хука — исходное состояние без изменений.
   * sequenceNumber не трогаем: «прицеплено» к инкременту резолва боя.
   */
  private async triggerHeroAfterCombat(
    state: GameState,
    ctx: AfterCombatContext,
  ): Promise<GameState> {
    const attackerFighter = state.fighters.find((f) => f.id === ctx.attackerFighterId);
    if (!attackerFighter) {
      return state;
    }
    const slug = attackerFighter.heroSlug ?? attackerFighter.heroId;
    return this.abilityRegistry.triggerOnAfterCombat(slug, state, ctx);
  }

  /**
   * Вызвать after-combat хук ЗАЩИЩАЮЩЕГОСЯ героя (defender-side, напр.
   * Spider-Sense). Зеркало triggerHeroAfterCombat, но слаг берём с
   * ЗАЩИЩАЮЩЕГОСЯ бойца (ctx.defenderFighterId). Тот же ctx (несёт
   * defenderPlayerId — цель defender-side эффектов). Generic-handler
   * обрабатывает 'after-defense' правила, применяя эффект к ctx.defenderPlayerId;
   * правила 'after-attack' защитника здесь не сработают (нет смысла). Если
   * защищающегося бойца в state нет — no-op. seq не трогаем.
   */
  private async triggerHeroAfterDefense(
    state: GameState,
    ctx: AfterCombatContext,
  ): Promise<GameState> {
    const defenderFighter = state.fighters.find((f) => f.id === ctx.defenderFighterId);
    if (!defenderFighter) {
      return state;
    }
    const slug = defenderFighter.heroSlug ?? defenderFighter.heroId;
    return this.abilityRegistry.triggerOnAfterCombat(slug, state, ctx);
  }

  /**
   * Вызвать on-defeat хук героя ВЛАДЕЛЬЦА повергнутого бойца (TASK, РЕАНИМАЦИЯ).
   *
   * Зеркало triggerHeroAfterCombat: боец-герой ищется по ownerId повергнутого
   * бойца (HERO-боец владельца), слаг = ownerHeroFighter.heroSlug ?? heroId —
   * чтобы герой мог отреагировать на гибель своего САЙДКИКА (у сайдкика свой
   * heroSlug, поэтому слаг берём именно с HERO-бойца владельца). Если бойца в
   * state нет или у владельца нет HERO-бойца — no-op. seq не трогаем:
   * «прицеплено» к инкременту резолва боя.
   */
  private async triggerHeroFighterDefeated(
    state: GameState,
    defeatedFighterId: string,
  ): Promise<GameState> {
    const fallen = state.fighters.find((f) => f.id === defeatedFighterId);
    if (!fallen) {
      return state;
    }
    const ownerHero = state.fighters.find(
      (f) => f.ownerId === fallen.ownerId && f.type === FighterType.HERO,
    );
    if (!ownerHero) {
      return state;
    }
    const slug = ownerHero.heroSlug ?? ownerHero.heroId;
    return this.abilityRegistry.triggerOnFighterDefeated(slug, state, fallen);
  }

  /**
   * Применить РЕАКТИВНЫЕ on-move хуки героев после перемещения бойцов
   * (РЕАНИМИРОВАННЫЙ on-move через дифф позиций).
   *
   * Диффит позиции бойцов между stateBefore и stateAfter: для каждого бойца,
   * присутствующего в ОБОИХ состояниях, чья позиция изменилась (x или y) И
   * который НЕ повержен (в состоянии ПОСЛЕ), дёргает кросс-героевый
   * triggerOnFighterMoved (реагирует ДРУГОЙ герой, не двигающийся), протягивая
   * state через каждого сдвинувшегося бойца. ПОСЛЕ всех движений — единый
   * checkAndApplyGameOver (реактивный пинг мог добить героя). seq отдельно НЕ
   * бампим: «прицеплено» к инкременту вызывающего движения. No-op, если никто
   * не сдвинулся или ни один герой не реагирует.
   */
  private async applyMoveReactions(
    stateBefore: GameState,
    stateAfter: GameState,
  ): Promise<GameState> {
    // Снимок позиций ДО движения по id бойца
    const beforePos = new Map(
      stateBefore.fighters.map((f) => [f.id, { x: f.position.x, y: f.position.y }]),
    );

    let next = stateAfter;
    // Список сдвинувшихся фиксируем по stateAfter (актуальные позиции/флаги)
    const movedIds = stateAfter.fighters
      .filter((f) => {
        const from = beforePos.get(f.id);
        if (!from) return false; // боец появился — не «движение»
        if (f.isDefeated) return false; // повержен — не реагируем на его движение
        return from.x !== f.position.x || from.y !== f.position.y;
      })
      .map((f) => f.id);

    for (const id of movedIds) {
      next = applyTerminalState(next);
      if (next.phase === GamePhase.GAME_OVER) break;
      const moved = next.fighters.find((f) => f.id === id);
      if (!moved) continue; // мог исчезнуть из-за реакции предыдущего бойца
      const from = beforePos.get(id)!;
      const to = { x: moved.position.x, y: moved.position.y };
      next = await this.abilityRegistry.triggerOnFighterMoved(next, moved, from, to);
    }

    // Реактивный пинг мог нанести смертельный урон — пере-проверяем game-over.
    return this.checkAndApplyGameOver(next);
  }

  /**
   * Резолв отложенного эффекта (C2): игрок выбирает бойца/клетку для
   * MOVE/PLACE-эффекта карты (metadata.pendingEffects).
   * Действие НЕ тратится (эффект уже оплачен картой), seq +1.
   */
  async executeResolvePendingEffect(
    dto: {
      gameId: string;
      effectId: string;
      fighterId?: string;
      x?: number;
      y?: number;
      optionIndex?: number;
      cardIds?: string[];
    },
    context: ActionContext,
  ): Promise<ActionResult> {
    if (context.currentState.metadata.pendingManeuver || context.currentState.metadata.pendingHandDiscard) {
      return { success: false, error: 'Resolve the pending resource choice first' };
    }
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    try {
      const { userId, currentState } = context;
      const pending = (currentState.metadata.pendingEffects ?? []).find(
        (p) => p.id === dto.effectId,
      );
      if (!pending) {
        return { success: false, error: 'Отложенный эффект не найден (протух или уже резолвлен)' };
      }
      // GD-018: голова очереди — ВСЕГДА (не только в бою): выборы
      // выполняются строго последовательно, out-of-order отклоняется.
      if (currentState.metadata.pendingEffects?.[0]?.id !== pending.id) {
        return { success: false, error: 'Resolve the first pending choice first' };
      }
      if (pending.playerId !== userId) {
        return { success: false, error: 'Этот выбор принадлежит другому игроку' };
      }

      // --- CHOOSE_ONE: исполняем эффекты выбранной опции (без бойца/клетки) ---
      if (pending.type === 'CHOOSE_ONE') {
        return this.resolveChooseOne(pending, dto.optionIndex, userId, currentState);
      }

      // --- TARGET_FIGHTER (S05): выбор цели для прямого урона («any one
      //     fighter in X's zone», способность Medusa). Клетка не нужна. ---
      if (pending.type === 'TARGET_FIGHTER') {
        return this.resolveTargetFighter(pending, dto.fighterId, userId, currentState, context.gameId);
      }

      // --- DISCARD_CARDS (S05, Hiss and Slither / Clutching Claws): печатный
      //     сброс без «random» — карту выбирает СБРАСЫВАЮЩИЙ (владелец выбора).
      //     Ровно value instance id из СВОЕЙ руки; mandatory (decline запрещён). ---
      if (pending.type === 'DISCARD_CARDS') {
        return this.resolveDiscardCards(pending, dto.cardIds, userId, currentState, context.gameId);
      }

      // --- BOOST_CHOICE (S05, Second Shot / Noble Sacrifice): optional буст
      //     боя картой из руки ПОСЛЕ reveal. Ровно ОДНА своя карта; её
      //     boostValue добавляется в боевую цепочку (DURING_COMBAT) и
      //     combatInfo; отказ — declinePendingEffect. ---
      if (pending.type === 'BOOST_CHOICE') {
        return this.resolveBoostChoice(pending, dto.cardIds, userId, currentState, context.gameId);
      }

      // MOVE/PLACE требуют бойца и клетку
      if (!dto.fighterId || dto.x === undefined || dto.y === undefined) {
        return { success: false, error: 'MOVE/PLACE требует fighterId, x, y' };
      }

      const fighter = currentState.fighters.find((f) => f.id === dto.fighterId);
      if (pending.fighterIds && !pending.fighterIds.includes(dto.fighterId)) {
        return { success: false, error: 'This fighter is not a target of the pending effect' };
      }
      // Revive-PLACE (Winged Frenzy: return a defeated Harpy) возвращает
      // ПОВЕРЖЕННОГО бойца — defeated разрешён ровно для этого pending-типа.
      if (!fighter || (fighter.health <= 0 && pending.restoreFullHealth !== true) || (fighter.isDefeated && pending.restoreFullHealth !== true)) {
        return { success: false, error: 'Боец не найден или повержен' };
      }

      // Чей боец двигается: свой (обычные MOVE) или противника
      // («Place the opposing fighter…»)
      if (pending.targetsOpponent ? fighter.ownerId === userId : fighter.ownerId !== userId) {
        return { success: false, error: 'Эффект двигает не этого бойца' };
      }

      // Именное ограничение из текста карты («Move Daredevil…», «each Harpy»)
      if (pending.fighterName && !bannerAllows(pending.fighterName, fighter)) {
        return {
          success: false,
          error: `Эффект двигает только «${pending.fighterName}» (выбран ${fighter.name})`,
        };
      }

      const target = { x: dto.x, y: dto.y };
      if (
        target.x < 0 ||
        target.y < 0 ||
        target.x >= currentState.boardState.width ||
        target.y >= currentState.boardState.height
      ) {
        return { success: false, error: 'Клетка вне доски' };
      }
      const cell = currentState.boardState.cells[target.y]?.[target.x];
      // GD-015-семантика isCellPassable: стены/препятствия/закрытые двери И
      // дыры сетки (undefined внутри границ) — непроходимы для MOVE/PLACE.
      if (!isCellPassable(cell)) {
        return { success: false, error: 'Клетка непроходима' };
      }
      const occupied = currentState.fighters.some(
        (f) => f.id !== fighter.id && isLivingFighter(f) && f.position.x === target.x && f.position.y === target.y,
      );
      if (occupied) {
        return { success: false, error: 'Клетка занята' };
      }

      if (pending.type === 'MOVE') {
        // Нулевой шаг легален для «up to N»: остаться на месте — валидный
        // резолв (mandatory-MOVE без достижимых свободных клеток не strand'ит).
        const staysInPlace = target.x === fighter.position.x && target.y === fighter.position.y;
        if (!staysInPlace) {
          // Дистанция эффекта (не movement бойца): союзники проходимы,
          // враги блокируют путь, занятое назначение уже проверено выше.
          // Winged Frenzy: canPassThroughEnemies — враги НЕ блокируют путь
          // (проход сквозь них разрешён), конечная клетка всё равно свободна.
          const allowance = pending.value ?? 1;
          const blockedPositions = pending.canPassThroughEnemies
            ? new Set<string>()
            : new Set(
                currentState.fighters
                  .filter((f) => f.id !== fighter.id && isLivingFighter(f) && f.ownerId !== fighter.ownerId)
                  .map((f) => `${f.position.x}:${f.position.y}`),
              );
          const reachable = this.adjacencyService.getReachableCells(
            currentState.boardState,
            fighter.position,
            allowance,
            { blockedPositions },
          );
          if (!reachable.has(`${target.x}:${target.y}`)) {
            return {
              success: false,
              error: `До клетки (${target.x}, ${target.y}) не добраться за ${allowance} шаг(ов)`,
            };
          }
        }
      }
      // PLACE: любая валидная свободная клетка. Зонное ограничение
      // (Winged Frenzy: «to any space in Medusa's zone») — клетка обязана
      // делить зону с указанным бойцом.
      if (pending.zoneFighterName) {
        const zoneAnchor = currentState.fighters.find((f) =>
          fighterNameMatches(f.name, pending.zoneFighterName!),
        );
        if (!zoneAnchor || !this.adjacencyService.isInSameZone(currentState, zoneAnchor.position, target)) {
          return { success: false, error: `Клетка должна быть в зоне «${pending.zoneFighterName}»` };
        }
      }

      let newState: GameState = {
        ...currentState,
        sequenceNumber: currentState.sequenceNumber + 1,
        fighters: currentState.fighters.map((f) =>
          f.id === fighter.id
            ? pending.restoreFullHealth === true && f.isDefeated
              // Revive (return a defeated Harpy): identity сохраняется,
              // здоровье восстанавливается до maxHealth.
              ? { ...f, position: target, health: f.maxHealth, isDefeated: false }
              : { ...f, position: target }
            : f,
        ),
        metadata: {
          ...currentState.metadata,
          lastActionAt: new Date(),
          lastActionBy: userId,
          pendingEffects: (currentState.metadata.pendingEffects ?? []).filter(
            (p) => p.id !== pending.id,
          ),
        },
      };

      // РЕАКТИВНЫЕ on-move хуки (РЕАНИМАЦИЯ): MOVE/PLACE-эффект сдвинул бойца —
      // диффим позиции (currentState ДО vs newState ПОСЛЕ) и даём ДРУГИМ героям
      // отреагировать. seq НЕ бампим: «прицеплено» к +1 резолва эффекта выше.
      newState = await this.applyMoveReactions(currentState, newState);
      newState = await this.drainAfterChoice(newState, userId, context.gameId, currentState.sequenceNumber);

      return {
        success: true,
        gameState: newState,
        metadata: {
          action: 'resolvePendingEffect',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
          effectText: pending.text,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка resolvePendingEffect: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * GD-018 (ACC-008): отказ от OPTIONAL-выбора («You may …»).
   * Только голова очереди, только владелец, только optional — mandatory
   * отклонить нельзя. Убирает выбор, seq +1, затем общая точка дренирования
   * (продолжение боя / отложенная передача хода).
   */
  async executeDeclinePendingEffect(
    dto: { gameId: string; effectId: string },
    context: ActionContext,
  ): Promise<ActionResult> {
    const { currentState, userId } = context;
    if (currentState.metadata.pendingManeuver || currentState.metadata.pendingHandDiscard) {
      return { success: false, error: 'Resolve the pending resource choice first' };
    }
    if (applyTerminalState(currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    const pending = (currentState.metadata.pendingEffects ?? []).find(
      (p) => p.id === dto.effectId,
    );
    if (!pending) {
      return { success: false, error: 'Отложенный эффект не найден (протух или уже резолвлен)' };
    }
    if (currentState.metadata.pendingEffects?.[0]?.id !== pending.id) {
      return { success: false, error: 'Resolve the first pending choice first' };
    }
    if (pending.playerId !== userId) {
      return { success: false, error: 'Этот выбор принадлежит другому игроку' };
    }
    if (!pending.optional) {
      return { success: false, error: 'Этот выбор обязателен — его нельзя отклонить' };
    }

    let newState: GameState = {
      ...currentState,
      sequenceNumber: currentState.sequenceNumber + 1,
      metadata: {
        ...currentState.metadata,
        lastActionAt: new Date(),
        lastActionBy: userId,
        pendingEffects: (currentState.metadata.pendingEffects ?? []).filter(
          (p) => p.id !== pending.id,
        ),
      },
    };
    newState = await this.drainAfterChoice(newState, userId, context.gameId, currentState.sequenceNumber);

    return {
      success: true,
      gameState: newState,
      metadata: {
        action: 'declinePendingEffect',
        performedAt: new Date(),
        performedBy: userId,
        sequenceNumber: newState.sequenceNumber,
        effectText: pending.text,
      },
    };
  }

  /**
   * Резолв CHOOSE_ONE: исполняет эффекты выбранной опции через
   * cardEffectExecutor (вне боя). При chooseCount > 1 («choose 2 different
   * effects») pending остаётся с оставшимися опциями (выбранная удалена —
   * «different»). Действие НЕ тратится, seq +1.
   */
  private async resolveChooseOne(
    pending: PendingEffect,
    optionIndex: number | undefined,
    userId: string,
    currentState: GameState,
  ): Promise<ActionResult> {
    const options = pending.options ?? [];
    if (optionIndex === undefined || optionIndex < 0 || optionIndex >= options.length) {
      return {
        success: false,
        error: `Нужен валидный optionIndex (0..${Math.max(0, options.length - 1)})`,
      };
    }

    const chosenEffects = pending.optionEffects?.[optionIndex] ?? [];
    const applied = await this.cardEffectExecutor.executeChosenEffects(
      currentState,
      chosenEffects,
      userId,
      pending.card,
      pending.effectContext,
    );

    const remainingCount = (pending.chooseCount ?? 1) - 1;
    const restPending: PendingEffect[] =
      remainingCount > 0
        ? [
            {
              ...pending,
              chooseCount: remainingCount,
              options: options
                .filter((_, i) => i !== optionIndex)
                .map((o, i) => ({ index: i, label: o.label })),
              optionEffects: (pending.optionEffects ?? []).filter((_, i) => i !== optionIndex),
            },
          ]
        : [];

    let newState: GameState = {
      ...applied.state,
      sequenceNumber: currentState.sequenceNumber + 1,
      metadata: {
        ...applied.state.metadata,
        lastActionAt: new Date(),
        lastActionBy: userId,
        // выполненный CHOOSE_ONE убираем; вложенные pending (MOVE/PLACE из
        // опции) и остаток chooseCount сохраняем
        pendingEffects: applied.state.phase === GamePhase.GAME_OVER ? [] : [
          ...(applied.state.metadata.pendingEffects ?? []).filter((p) => p.id !== pending.id),
          ...restPending,
        ],
      },
    };

    const combatProgress = newState.metadata.combatResolutionProgress;
    const stage = newState.metadata.combatEffectContinuation?.stage;
    if (combatProgress && stage) {
      const field = stage === 'ON_REVEAL' ? 'reveal' : stage === 'DURING_COMBAT' ? 'calculation' : 'after';
      const saved = combatProgress[field];
      if (saved) newState = { ...newState, metadata: { ...newState.metadata,
        combatResolutionProgress: { ...combatProgress, [field]: {
          ...saved, appliedEffects: [...saved.appliedEffects, ...applied.appliedEffects],
          manualEffects: [...saved.manualEffects, ...applied.manualEffects],
        } },
      } };
    }

    newState = await this.drainAfterChoice(newState, userId, currentState.gameId, currentState.sequenceNumber);

    return {
      success: true,
      gameState: newState,
      metadata: {
        action: 'resolvePendingEffect',
        performedAt: new Date(),
        performedBy: userId,
        sequenceNumber: newState.sequenceNumber,
        effectText: options[optionIndex].label,
        appliedEffects: applied.appliedEffects,
        manualEffects: applied.manualEffects,
      },
    };
  }

  /**
   * Резолв TARGET_FIGHTER (S05): выбор цели для прямого урона — «any one
   * fighter in X's zone» (A Momentary Glance), способность Medusa.
   * Цель РЕВАЛИДИРУЕТСЯ на резолве (могла пасть между созданием и выбором).
   * Урон применяется иммутабельно, terminal-состояние пересчитывается,
   * pending снимается, затем drainAfterChoice.
   */
  private async resolveTargetFighter(
    pending: PendingEffect,
    fighterId: string | undefined,
    userId: string,
    currentState: GameState,
    gameId: string,
  ): Promise<ActionResult> {
    if (!fighterId) {
      return { success: false, error: 'Нужен fighterId — цель урона' };
    }
    // РеVALIDATION: список целей и жива ли цель СЕЙЧАС
    if (pending.targetFighterIds && !pending.targetFighterIds.includes(fighterId)) {
      return { success: false, error: 'Боец не входит в допустимые цели' };
    }
    const target = currentState.fighters.find((f) => f.id === fighterId);
    if (!target || !isLivingFighter(target)) {
      return { success: false, error: 'Цель не найдена или повержена' };
    }
    const damage = pending.damage ?? 0;

    let newState: GameState = applyTerminalState({
      ...currentState,
      sequenceNumber: currentState.sequenceNumber + 1,
      fighters: currentState.fighters.map((f) => {
        if (f.id !== fighterId) return f;
        const health = Math.max(0, f.health - damage);
        return { ...f, health, isDefeated: health <= 0 ? true : f.isDefeated };
      }),
      metadata: {
        ...currentState.metadata,
        lastActionAt: new Date(),
        lastActionBy: userId,
        pendingEffects: (currentState.metadata.pendingEffects ?? []).filter(
          (p) => p.id !== pending.id,
        ),
      },
    });

    newState = await this.drainAfterChoice(newState, userId, gameId, currentState.sequenceNumber);

    return {
      success: true,
      gameState: newState,
      metadata: {
        action: 'resolvePendingEffect',
        performedAt: new Date(),
        performedBy: userId,
        sequenceNumber: newState.sequenceNumber,
        effectText: pending.text,
        appliedEffects: [
          {
            success: true,
            effectId: pending.id,
            targetIds: [fighterId],
            valueApplied: damage,
            message: `DAMAGE ${damage} → ${target.name}`,
          },
        ],
      },
    };
  }

  /** Shared hero-based terminal boundary; does not advance sequence. */
  private checkAndApplyGameOver(state: GameState): GameState {
    return applyTerminalState(state);
  }

  /**
   * Резолв DISCARD_CARDS (S05): владелец выбора («Your opponent discards 1
   * card.» — сбрасывающий оппонент) называет ровно value instance id из СВОЕЙ
   * руки. Карты уходят в его сброс, pending снимается, seq +1, боевая цепочка
   * (если выбор родился в AFTER_COMBAT) продолжается через drainAfterChoice.
   */
  private async resolveDiscardCards(
    pending: PendingEffect,
    cardIds: string[] | undefined,
    userId: string,
    currentState: GameState,
    gameId: string,
  ): Promise<ActionResult> {
    const count = pending.value ?? 1;
    const hand = currentState.handZones[userId]?.cards ?? [];
    if (
      !Array.isArray(cardIds) ||
      cardIds.length !== count ||
      new Set(cardIds).size !== count ||
      cardIds.some((id) => !hand.some((c) => c.id === id))
    ) {
      return {
        success: false,
        error: `Выберите ровно ${count} карты (по instance id) из своей руки`,
      };
    }

    let next = currentState;
    for (const id of cardIds) {
      next = await this.deckManagement.discardCard(next, userId, id);
    }

    let newState: GameState = {
      ...next,
      sequenceNumber: currentState.sequenceNumber + 1,
      metadata: {
        ...next.metadata,
        lastActionAt: new Date(),
        lastActionBy: userId,
        pendingEffects: (next.metadata.pendingEffects ?? []).filter(
          (p) => p.id !== pending.id,
        ),
      },
    };

    newState = await this.drainAfterChoice(newState, userId, gameId, currentState.sequenceNumber);

    return {
      success: true,
      gameState: newState,
      metadata: {
        action: 'resolvePendingEffect',
        performedAt: new Date(),
        performedBy: userId,
        sequenceNumber: newState.sequenceNumber,
        effectText: pending.text,
        appliedEffects: [
          {
            success: true,
            effectId: pending.id,
            targetIds: [userId],
            valueApplied: count,
            message: `DISCARD ${count} (выбор сбрасывающего)`,
          },
        ],
      },
    };
  }

  /**
   * Резолв BOOST_CHOICE (S05): optional буст боя («You may BOOST this
   * attack/defense», Second Shot / Noble Sacrifice) — владелец называет ровно
   * ОДНУ карту СВОЕЙ руки. Ревалидация атомарна (валидация ДО мутаций):
   * чужая карта / не из руки / не одна → отказ без изменений состояния.
   * Применение: карта → в сброс владельца; её boostValue — в
   * combatEffectContinuation (finalAttack атакующего / finalDefense
   * защитника — сторона по combatInfo) и в combatInfo (boostValue +
   * cardBoostCardId). pending снимается, seq +1, приостановленный расчёт
   * урона продолжается через drainAfterChoice.
   */
  private async resolveBoostChoice(
    pending: PendingEffect,
    cardIds: string[] | undefined,
    userId: string,
    currentState: GameState,
    gameId: string,
  ): Promise<ActionResult> {
    const combatInfo = currentState.metadata.combatInfo;
    const continuation = currentState.metadata.combatEffectContinuation;
    if (!combatInfo) {
      return { success: false, error: 'Нет боя — BOOST-выбор протух' };
    }
    const hand = currentState.handZones[userId]?.cards ?? [];
    if (
      !Array.isArray(cardIds) ||
      cardIds.length !== 1 ||
      new Set(cardIds).size !== 1 ||
      !hand.some((c) => c.id === cardIds[0])
    ) {
      return { success: false, error: 'Выберите ровно одну карту (instance id) из своей руки' };
    }
    const card = hand.find((c) => c.id === cardIds[0])!;
    const boost = card.boostValue ?? 0;

    let next = await this.deckManagement.discardCard(currentState, userId, card.id);

    // Сторона выбора: владелец атакующего бойца бустит attack, иначе defense.
    // BOOST_CHOICE рождается только в paused-стадии боевой цепочки, поэтому
    // continuation для живого выбора гарантированно существует (guard убран).
    const attackerOwner = currentState.fighters.find((f) => f.id === combatInfo.attackerId)?.ownerId;
    const isAttackerSide = attackerOwner === userId;

    const field = isAttackerSide ? 'finalAttack' : 'finalDefense';
    next = {
      ...next,
      metadata: {
        ...next.metadata,
        combatEffectContinuation: {
          ...continuation!,
          [field]: continuation![field] + boost,
        },
      },
    };

    next = {
      ...next,
      metadata: {
        ...next.metadata,
        combatInfo: {
          ...next.metadata.combatInfo!,
          boostValue: (next.metadata.combatInfo!.boostValue ?? 0) + boost,
          cardBoostCardId: card.id,
        },
      },
    };

    let newState: GameState = {
      ...next,
      sequenceNumber: currentState.sequenceNumber + 1,
      metadata: {
        ...next.metadata,
        lastActionAt: new Date(),
        lastActionBy: userId,
        pendingEffects: (next.metadata.pendingEffects ?? []).filter(
          (p) => p.id !== pending.id,
        ),
      },
    };

    newState = await this.drainAfterChoice(newState, userId, gameId, currentState.sequenceNumber);

    return {
      success: true,
      gameState: newState,
      metadata: {
        action: 'resolvePendingEffect',
        performedAt: new Date(),
        performedBy: userId,
        sequenceNumber: newState.sequenceNumber,
        effectText: pending.text,
        appliedEffects: [
          {
            success: true,
            effectId: pending.id,
            targetIds: [userId],
            valueApplied: boost,
            message: `BOOST +${boost} («${card.name}» ${isAttackerSide ? '→ атака' : 'защита'})`,
          },
        ],
      },
    };
  }

  /**
   * Списать 1 действие текущего хода (экономика «2 действия за ход»).
   *
   * ВЫЗЫВАТЬ ПОСЛЕ того, как действие сделало свой +1 к sequenceNumber.
   * При остатке 0 — авто-завершение хода через advanceTurn БЕЗ инкремента seq
   * (суммарно за мутацию ровно +1, контракт saveState соблюдён).
   */
  private async consumeAction(state: GameState, userId: string): Promise<GameState> {
    state = applyTerminalState(state);
    if (state.phase === GamePhase.GAME_OVER) return state;
    const remaining = getActionsRemaining(state) - 1;
    if (remaining <= 0) {
      return this.advanceTurn(
        { ...state, metadata: { ...state.metadata, actionsRemaining: 0 } },
        userId,
        /* incrementSeq */ false,
      );
    }
    return { ...state, metadata: { ...state.metadata, actionsRemaining: remaining } };
  }

  /**
   * Создаёт начальное состояние игры
   */
  async createInitialState(params: InitialGameStateParams): Promise<GameState> {
    const { gameId, players, boardId } = params;

    // Создаём начальное состояние
    const state: GameState = {
      gameId,
      sequenceNumber: 0,
      phase: GamePhase.TURN_START,
      turnCount: 1,
      currentTurnPlayerId: players[0].userId,

      // Игроки
      players: players.map((p) => ({
        userId: p.userId,
        heroId: p.heroId,
        health: p.health,
        maxHealth: p.maxHealth,
        fighterIds: [], // Заполняется при размещении бойцов
        isAlive: true,
      })),

      // Бойцы (пока нет)
      fighters: [],

      // Колоды
      decks: {},
      discardPiles: {},

      // Зоны ручек
      handZones: {},

      // Состояние доски - используем вспомогательную функцию
      boardState: createEmptyBoardState(20, 20),

      // Метаданные
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: 'system',
        version: 1,
        actionsRemaining: ACTIONS_PER_TURN,
      },
    };

    this.logger.debug(`Создано начальное состояние для игры ${gameId}`);
    return state;
  }

  /** Begin a maneuver atomically: spend one action and draw before any decision. */
  async executeBeginManeuver(
    dto: { gameId: string; expectedSequenceNumber: number }, context: ActionContext,
  ): Promise<ActionResult> {
    const { currentState: state, userId } = context;
    const validation = this.rulesValidator.canPlayerAct(state, userId);
    if (!validation.valid) return { success: false, error: validation.error };
    if (applyTerminalState(state).phase === GamePhase.GAME_OVER ||
        ![GamePhase.ACTION_MANEUVER, GamePhase.ACTION_ATTACK].includes(state.phase) ||
        state.metadata.combatResolutionProgress || state.metadata.pendingManeuver || state.metadata.pendingHandDiscard ||
        (state.metadata.pendingEffects?.length ?? 0) > 0 ||
        getActionsRemaining(state) <= 0) return { success: false, error: 'Cannot begin maneuver in current state' };
    if (!Number.isInteger(dto.expectedSequenceNumber) || dto.expectedSequenceNumber !== state.sequenceNumber) {
      return { success: false, error: 'State changed; reload before beginning maneuver' };
    }
    try {
      let next = await this.deckManagement.drawCards({ ...state, metadata: { ...state.metadata,
        actionsRemaining: getActionsRemaining(state) - 1, maneuveredThisTurn: true } }, userId, 1);
      next = { ...next, sequenceNumber: state.sequenceNumber + 1,
        metadata: { ...next.metadata, lastActionAt: new Date(), lastActionBy: userId,
          pendingManeuver: next.phase === GamePhase.GAME_OVER ? undefined :
            { id: `maneuver:${state.turnCount}:${state.sequenceNumber}`, playerId: userId } } };
      return { success: true, gameState: next };
    } catch (e) { return { success: false, error: e instanceof Error ? e.message : 'Maneuver draw failed' }; }
  }

  /** Resolve the exact excess instances, then resume the already-started turn end. */
  async executeDiscardToLimit(
    dto: { gameId: string; pendingId: string; cardIds: string[] }, context: ActionContext,
  ): Promise<ActionResult> {
    const { currentState: state, userId } = context;
    const pending = state.metadata.pendingHandDiscard;
    if (state.phase !== GamePhase.TURN_END || !pending || pending.id !== dto.pendingId ||
        pending.playerId !== userId || state.currentTurnPlayerId !== userId) {
      return { success: false, error: 'No matching discard choice for this player' };
    }
    const cards = state.handZones[userId]?.cards ?? [];
    if (!Array.isArray(dto.cardIds) || dto.cardIds.length !== pending.count ||
        new Set(dto.cardIds).size !== pending.count || cards.length - 7 !== pending.count ||
        dto.cardIds.some(id => !cards.some(c => c.id === id))) {
      return { success: false, error: 'Choose exactly the excess card instances from your hand' };
    }
    let next = state;
    for (const id of dto.cardIds) next = await this.deckManagement.discardCard(next, userId, id);
    next = { ...next, metadata: { ...next.metadata, pendingHandDiscard: undefined } };
    return { success: true, gameState: await this.advanceTurn(next, userId, true, true) };
  }

  /** Complete the persisted maneuver without another draw or action charge. */
  async executeManeuver(
    dto: ManeuverDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    if ((context.currentState.metadata.pendingEffects?.length ?? 0) > 0) {
      return { success: false, error: 'Resolve the pending choice first' };
    }
    if (context.currentState.metadata.combatResolutionProgress) {
      return { success: false, error: 'Resolve the pending combat effect first' };
    }
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    return this.metrics.measureServiceDuration('executeManeuver', 'GameActionExecutor', async () => {
      try {
        const { userId, currentState, gameId } = context;
        const pending = currentState.metadata.pendingManeuver;
        if (!pending || pending.id !== dto.maneuverId || pending.playerId !== userId ||
            currentState.currentTurnPlayerId !== userId || currentState.metadata.pendingHandDiscard) {
          return { success: false, error: 'Begin maneuver first, then resolve its matching choice' };
        }

        // BOOST-карта манёвра: явный boostCardId, либо legacy cardId
        // (старые клиенты слали cardId — трактуем как boost). Манёвр без
        // карты валиден: чистые «добор 1 + движение» (правила Unmatched).
        const boostCardId = dto.boostCardId ?? dto.cardId;
        if (boostCardId && !currentState.handZones[userId]?.cards.some(c => c.id === boostCardId)) {
          return { success: false, error: 'Boost must be a card instance in your hand' };
        }

        // Манёвр двигает ВСЕХ своих бойцов (C3): moves[] — несколько ходов,
        // legacy fighterId+path — один. BOOST добавляется каждому бойцу.
        const moves: Array<{ fighterId: string; path: Array<{ x: number; y: number }> }> =
          dto.moves && dto.moves.length > 0
            ? dto.moves
            : dto.fighterId && dto.path
              ? [{ fighterId: dto.fighterId, path: dto.path }]
              : [];
        const uniqueFighters = new Set(moves.map((m) => m.fighterId));
        if (uniqueFighters.size !== moves.length) {
          this.metrics.incrementGameAction('maneuver', undefined, 'error');
          return { success: false, error: 'Каждый боец двигается в манёвре не более одного раза' };
        }

        // Ходы применяются ПОСЛЕДОВАТЕЛЬНО: валидация каждого — на состоянии
        // после предыдущего (освободившиеся/занятые клетки учитываются)
        let workState: GameState = currentState;
        for (const mv of moves) {
          const validation = await this.metrics.measureValidation('maneuver', () =>
            this.rulesValidator.validateManeuver(
              workState,
              mv.fighterId,
              boostCardId,
              mv.path,
              userId,
            ),
          );
          if (!validation.valid) {
            this.metrics.incrementGameAction('maneuver', undefined, 'error');
            return {
              success: false,
              error: validation.error || 'Maneuver validation failed',
            };
          }

          // Конечная клетка пути свободна от живых бойцов (промежуточные
          // можно проходить; правила занятости — movement/traversal.ts)
          const dest = mv.path[mv.path.length - 1];
          const occupied = workState.fighters.some(
            (f) =>
              f.id !== mv.fighterId &&
              isLivingFighter(f) &&
              f.position.x === dest.x &&
              f.position.y === dest.y,
          );
          if (occupied) {
            this.metrics.incrementGameAction('maneuver', undefined, 'error');
            return { success: false, error: `Клетка (${dest.x}, ${dest.y}) занята` };
          }

          workState = {
            ...workState,
            fighters: workState.fighters.map((f) =>
              f.id === mv.fighterId ? { ...f, position: { x: dest.x, y: dest.y } } : f,
            ),
          };
        }

        // Единый +1 к seq за весь манёвр (контракт saveState)
        let newState: GameState = {
          ...workState,
          sequenceNumber: currentState.sequenceNumber + 1,
        };

        if (boostCardId) {
          newState = await this.deckManagement.discardCard(newState, userId, boostCardId);
        }

        // РЕАКТИВНЫЕ on-move хуки (РЕАНИМАЦИЯ): диффим позиции (currentState ДО
        // мутации vs newState ПОСЛЕ) и даём ДРУГИМ героям отреагировать на
        // сдвинувшихся бойцов. seq отдельно НЕ бампим — «прицеплено» к +1
        // манёвра выше. No-op, если никто не реагирует.
        newState = await this.applyMoveReactions(currentState, newState);


        // Фазу НЕ переключаем (экономика «2 действия за ход»): манёвр — одно из
        // двух действий, после него можно манёврить/атаковать снова из той же фазы.
        // Единый +1 к seq уже сделан выше (за весь мульти-ход манёвра).
        newState = {
          ...newState,
          metadata: {
            ...newState.metadata,
            lastActionAt: new Date(),
            lastActionBy: userId,
            // Per-turn флаг (TASK): игрок сделал манёвр в этом ходу. Сбрасывается
            // в advanceTurn при передаче хода. Ставим один раз за манёвр —
            // даже если manёвр двигал нескольких бойцов (moves[]).
            maneuveredThisTurn: true,
            pendingManeuver: undefined,
          },
        };

        // Действие уже списано на begin; последний манёвр завершает ход после выбора.
        if (newState.phase !== GamePhase.GAME_OVER && getActionsRemaining(newState) === 0) {
          newState = await this.advanceTurn(newState, userId, false);
        }

        this.metrics.incrementGameAction('maneuver', undefined, 'success');

        return {
          success: true,
          gameState: newState,
          metadata: {
            action: 'maneuver',
            performedAt: new Date(),
            performedBy: userId,
            sequenceNumber: newState.sequenceNumber,
          },
        };
      } catch (error) {
        this.logger.error(
          `Ошибка при выполнении манёвра [gameId=${context.gameId}]: ${error}`,
          { gameId: context.gameId, userId: context.userId, dto },
        );
        this.metrics.incrementError('GameActionExecutor', 'executeManeuver', error instanceof Error ? error.name : 'unknown');
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    });
  }

  /**
   * Legacy endpoint: ordinary movement requires the persisted maneuver flow.
   */
  async executeMoveFighter(
    dto: MoveFighterDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    return { success: false, error: 'Use beginManeuver and maneuver to move fighters' };
  }

  /**
   * Выполнить атаку
   */
  async executeAttack(
    dto: AttackDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    if (context.currentState.metadata.pendingManeuver || context.currentState.metadata.pendingHandDiscard) {
      return { success: false, error: 'Resolve the pending resource choice first' };
    }
    if ((context.currentState.metadata.pendingEffects?.length ?? 0) > 0) {
      return { success: false, error: 'Resolve the pending choice first' };
    }
    if (context.currentState.metadata.combatResolutionProgress) {
      return { success: false, error: 'Resolve the pending combat effect first' };
    }
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    const actionState = context.currentState;
    if (actionState.currentTurnPlayerId !== context.userId || getActionsRemaining(actionState) <= 0 ||
        ![GamePhase.ACTION_MANEUVER, GamePhase.ACTION_ATTACK].includes(actionState.phase)) {
      return { success: false, error: 'No action available for this player in the current phase' };
    }
    return this.metrics.measureServiceDuration('executeAttack', 'GameActionExecutor', async () => {
      try {
        const { userId, currentState, gameId } = context;

        // Валидация с замером времени
        const validation = await this.metrics.measureValidation('attack', () =>
          this.rulesValidator.validateAttackWithParams(
            currentState,
            dto.attackerId,
            dto.targetId,
            dto.cardId,
            userId,
          ),
        );

        if (!validation.valid) {
          this.metrics.incrementGameAction('attack', undefined, 'error');
          return {
            success: false,
            error: validation.error || 'Attack validation failed',
          };
        }

        // Проверяем смежность позиций
        const attacker = currentState.fighters.find((f) => f.id === dto.attackerId);
        const target = currentState.fighters.find((f) => f.id === dto.targetId);

        if (!attacker || !target) {
          this.metrics.incrementGameAction('attack', undefined, 'error');
          return { success: false, error: 'Attacker or target not found' };
        }

        // Дистанция атаки: melee — только смежная цель; ranged — смежная
        // ИЛИ в той же зоне доски (Cell.zone клеток атакующего и цели совпадают)
        const adjacent = await this.adjacencyService.isAdjacent(
          currentState,
          attacker.position,
          target.position,
        );
        const attackType = getFighterAttackType(attacker);
        let inRange = adjacent;
        if (!inRange && attackType === 'ranged') {
          inRange = this.adjacencyService.isInSameZone(
            currentState,
            attacker.position,
            target.position,
          );
        }

        // Extended-range способность героя (например Ms. Marvel, range<=2):
        // если обычные melee/ranged-правила цель НЕ достают — спрашиваем реестр.
        // Хук ТОЛЬКО добавляет разрешение, никогда не отнимает уже выданное.
        if (!inRange) {
          const range = this.adjacencyService.manhattanDistance(
            attacker.position,
            target.position,
          );
          const attackerSlug = attacker.heroSlug ?? attacker.heroId;
          // STANCE: текущая стойка атакующего — для stance-aware дальности
          // (Muhammad Ali FLOAT: range 2; STING — нет дальней атаки).
          const attackerStance = currentState.metadata.heroStances?.[attacker.ownerId];
          if (
            this.abilityRegistry.canAttackAtRange(
              attackerSlug,
              attacker.id,
              target.id,
              range,
              attackerStance,
            )
          ) {
            inRange = true;
          }
        }

        if (!inRange) {
          this.metrics.incrementGameAction('attack', undefined, 'error');
          return {
            success: false,
            error:
              attackType === 'ranged'
                ? 'Ranged attack: target must be adjacent or in the same zone as attacker'
                : 'Melee attack: target must be adjacent to attacker',
          };
        }

        // Сыгранная карта: реальное значение атаки + сброс из руки.
        // В combatInfo пишем instance id (`${cardId}::n`) — по нему resolveCombat
        // найдёт карту в decks[].cards даже после сброса (cards — полный список).
        const playedCard = this.findHandCard(currentState, userId, dto.cardId);

        // BOOST-эффект КАРТЫ («You may BOOST this attack», Second Shot /
        // Noble Sacrifice) НЕ коммитится здесь: по rulebook (Battle of Legends
        // Vol.1, p.12-13) выбор карты происходит после reveal обеих карт и
        // отмены Feint — движок создаёт BOOST_CHOICE pending на стадии
        // DURING_COMBAT (card-effect-executor). Защитник до reveal не видит
        // даже факта второй карты. Способность Arthur (R-15) — наоборот,
        // печатным текстом коммитится вместе с атакой, face-down.
        let abilityBoostCard: HandCard | undefined;
        if (dto.abilityBoostCardId) {
          abilityBoostCard = this.findHandCard(currentState, userId, dto.abilityBoostCardId);
          if (!abilityBoostCard) {
            this.metrics.incrementGameAction('attack', undefined, 'error');
            return { success: false, error: 'Ability boost card not in hand' };
          }
          if (abilityBoostCard.id === playedCard?.id) {
            this.metrics.incrementGameAction('attack', undefined, 'error');
            return { success: false, error: 'Нельзя BOOST-ить атаку той же картой' };
          }
          if (!this.abilityBoostAllowed(attacker)) {
            this.metrics.incrementGameAction('attack', undefined, 'error');
            return {
              success: false,
              error: 'Способность героя не разрешает BOOST этой атаки (только атака самого героя)',
            };
          }
        }

        let nextState = currentState;
        if (playedCard) {
          nextState = await this.deckManagement.discardCard(nextState, userId, playedCard.id);
        }
        if (abilityBoostCard) {
          nextState = await this.deckManagement.discardCard(nextState, userId, abilityBoostCard.id);
        }

        // Сохраняем состояние боя в metadata: attackValue — ТОЛЬКО печатное
        // значение; ability boost Arthur — отдельно в boostValue (карта-BOOST
        // добавит своё значение позже, на резолве BOOST_CHOICE).
        // Отмена эффектов карты (Feint, R-16) не прибавит boost к расчёту.
        const combatState: CombatState = {
          attackerId: dto.attackerId,
          defenderId: target.ownerId,
          targetFighterId: target.id,
          attackerCardId: playedCard?.id ?? dto.cardId,
          attackValue: playedCard?.attackValue ?? 0,
          boostValue: abilityBoostCard?.boostValue ?? 0,
          abilityBoostCardId: abilityBoostCard?.id,
          defenseValue: 0,
          startedAt: new Date(),
        };

        const newState: GameState = {
          ...nextState,
          phase: GamePhase.COMBAT,
          sequenceNumber: currentState.sequenceNumber + 1,
          metadata: {
            ...nextState.metadata,
            lastActionAt: new Date(),
            lastActionBy: userId,
            combatInfo: combatState,
            // Атака тратит действие в момент объявления (НЕ consumeAction — ход
            // не завершаем, бой не разрешён). Остаток смотрит executeResolveCombat.
            actionsRemaining: Math.max(0, getActionsRemaining(currentState) - 1),
          },
        };

        this.metrics.incrementGameAction('attack', undefined, 'success');

        return {
          success: true,
          gameState: newState,
          metadata: {
            action: 'attack',
            performedAt: new Date(),
            performedBy: userId,
            sequenceNumber: newState.sequenceNumber,
          },
        };
      } catch (error) {
        this.logger.error(
          `Ошибка при выполнении атаки [gameId=${context.gameId}]: ${error}`,
          { gameId: context.gameId, userId: context.userId, dto },
        );
        this.metrics.incrementError('GameActionExecutor', 'executeAttack', error instanceof Error ? error.name : 'unknown');
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    });
  }

  /**
   * Выполнить защиту
   */
  async executePlayDefense(
    dto: PlayDefenseDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    if (context.currentState.metadata.pendingManeuver || context.currentState.metadata.pendingHandDiscard) {
      return { success: false, error: 'Resolve the pending resource choice first' };
    }
    if ((context.currentState.metadata.pendingEffects?.length ?? 0) > 0) {
      return { success: false, error: 'Resolve the pending choice first' };
    }
    if (context.currentState.metadata.combatResolutionProgress) {
      return { success: false, error: 'Resolve the pending combat effect first' };
    }
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    try {
      const { userId, currentState } = context;

      // Проверяем фазу
      if (currentState.phase !== GamePhase.COMBAT) {
        return { success: false, error: 'Not in combat phase' };
      }

      // Проверяем, что пользователь - защищающийся
      const combatInfo = currentState.metadata.combatInfo;
      if (!combatInfo) {
        return { success: false, error: 'No combat in progress' };
      }

      if (combatInfo.defenderId !== userId) {
        return { success: false, error: 'Only defender can play defense' };
      }

      // Валидация карты защиты
      const validation = this.rulesValidator.validateDefense(
        currentState,
        dto.cardId,
        userId,
      );

      if (!validation.valid) {
        return {
          success: false,
          error: validation.error || 'Defense validation failed',
        };
      }

      // bannerName: защитную карту играет АТАКОВАННЫЙ боец (targetFighterId
      // из A0; легаси-сейвы без поля → первый боец защитника)
      const defendingFighter =
        (combatInfo.targetFighterId
          ? currentState.fighters.find((f) => f.id === combatInfo.targetFighterId)
          : undefined) ??
        currentState.fighters.find((f) => f.ownerId === combatInfo.defenderId);
      const defenseCardForBanner = this.findHandCard(currentState, userId, dto.cardId);
      if (defendingFighter && defenseCardForBanner) {
        const bannerCheck = this.rulesValidator.validateBanner(
          currentState,
          defenseCardForBanner,
          defendingFighter,
        );
        if (!bannerCheck.valid) {
          return { success: false, error: bannerCheck.error };
        }
      }

      // Сыгранная карта защиты: реальное значение + сброс из руки
      // (instance id в combatInfo — см. комментарий в executeAttack).
      // BOOST-эффект карты защиты («You may BOOST this defense») здесь НЕ
      // коммитится — как и у атаки, выбор идёт после reveal через
      // BOOST_CHOICE pending на стадии DURING_COMBAT (rulebook p.12-13).
      const playedCard = this.findHandCard(currentState, userId, dto.cardId);

      let nextState = currentState;
      if (playedCard) {
        nextState = await this.deckManagement.discardCard(nextState, userId, playedCard.id);
      }

      // Обновляем состояние боя
      const updatedCombatInfo: CombatState = {
        ...combatInfo,
        defenderCardId: playedCard?.id ?? dto.cardId,
        defenseValue: playedCard?.defenseValue ?? 0,
      };

      const newState: GameState = {
        ...nextState,
        phase: GamePhase.COMBAT_RESOLVE,
        sequenceNumber: currentState.sequenceNumber + 1,
        metadata: {
          ...nextState.metadata,
          lastActionAt: new Date(),
          lastActionBy: userId,
          combatInfo: updatedCombatInfo,
        },
      };

      return {
        success: true,
        gameState: newState,
        metadata: {
          action: 'playDefense',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка при игре защиты: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Разыграть scheme-карту из руки текущего игрока (тратит 1 действие).
   *
   * Фаза/ход закрыты ActionPhaseGuard на мутации — здесь только карта:
   * 1. Карта должна быть в руке вызвавшего и иметь cardType SCHEME
   *    (VERSATILE сознательно не принимаем — играется как атака/защита).
   * 2. Авто-эффекты best-effort через CardEffectExecutorService (в БД у карт
   *    effects почти всегда [] — ветка фактически спящая, ошибки не фатальны).
   * 3. Карта ВСЕГДА уходит в сброс; текст эффекта едет в metadata результата
   *    для ручного применения в Game Tester.
   * 4. consumeAction: после 2-го действия — авто-завершение хода
   *    (суммарно за мутацию ровно +1 к seq — контракт saveState).
   */
  async executePlayScheme(
    dto: PlaySchemeDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    if (context.currentState.metadata.pendingManeuver || context.currentState.metadata.pendingHandDiscard) {
      return { success: false, error: 'Resolve the pending resource choice first' };
    }
    if ((context.currentState.metadata.pendingEffects?.length ?? 0) > 0) {
      return { success: false, error: 'Resolve the pending choice first' };
    }
    if (context.currentState.metadata.combatResolutionProgress) {
      return { success: false, error: 'Resolve the pending combat effect first' };
    }
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    const actionState = context.currentState;
    if (actionState.currentTurnPlayerId !== context.userId || getActionsRemaining(actionState) <= 0 ||
        ![GamePhase.ACTION_MANEUVER, GamePhase.ACTION_ATTACK].includes(actionState.phase)) {
      return { success: false, error: 'No action available for this player in the current phase' };
    }
    return this.metrics.measureServiceDuration('executePlayScheme', 'GameActionExecutor', async () => {
      try {
        const { userId, currentState } = context;

        // Карта в руке (принимает и instance id `${cardId}::n`, и базовый cardId)
        const playedCard = this.findHandCard(currentState, userId, dto.cardId);
        if (!playedCard) {
          this.metrics.incrementGameAction('playScheme', undefined, 'error');
          return { success: false, error: 'Card not found in hand' };
        }

        if (playedCard.cardType !== CardType.SCHEME) {
          this.metrics.incrementGameAction('playScheme', undefined, 'error');
          return {
            success: false,
            error: `Card is not a SCHEME card (got ${playedCard.cardType})`,
          };
        }

        // bannerName: именная scheme требует живого бойца с этим именем
        const schemeOwnFighters = currentState.fighters.filter(
          (f) => f.ownerId === userId && f.health > 0,
        );
        if (schemeOwnFighters.length > 0) {
          const bannerOk = schemeOwnFighters.some(
            (f) => this.rulesValidator.validateBanner(currentState, playedCard, f).valid,
          );
          if (!bannerOk) {
            this.metrics.incrementGameAction('playScheme', undefined, 'error');
            return {
              success: false,
              error: `Карту с банером «${playedCard.bannerName}» нельзя разыграть: боец не в игре`,
            };
          }
        }

        // Авто-эффекты best-effort: ошибки эффектов не блокируют розыгрыш
        let nextState: GameState = currentState;
        let appliedEffects: readonly EffectResult[] = [];
        if (playedCard.effects && playedCard.effects.length > 0) {
          try {
            const effectsResult = await this.cardEffectExecutor.executeOnPlayEffects(
              nextState,
              playedCard,
              userId,
            );
            nextState = effectsResult.state;
            appliedEffects = effectsResult.appliedEffects;
          } catch (e) {
            this.logger.warn(
              `executePlayScheme: card effects skipped for ${playedCard.id}: ${e}`,
            );
          }
        }

        // Карта всегда уходит в сброс (instance id; discardCard не трогает seq)
        nextState = await this.deckManagement.discardCard(nextState, userId, playedCard.id);

        // Свой +1 к seq — у scheme нет movementService, инкрементим сами
        let newState: GameState = {
          ...nextState,
          sequenceNumber: currentState.sequenceNumber + 1,
          metadata: {
            ...nextState.metadata,
            lastActionAt: new Date(),
            lastActionBy: userId,
          },
        };

        // Списываем 1 действие (после 2-го — авто-завершение хода без доп. +1 к seq)
        newState = await this.consumeAction(newState, userId);

        this.metrics.incrementGameAction('playScheme', undefined, 'success');

        return {
          success: true,
          gameState: newState,
          metadata: {
            action: 'playScheme',
            performedAt: new Date(),
            performedBy: userId,
            sequenceNumber: newState.sequenceNumber,
            // Текст эффекта — для ручного применения в тестере (fallback на имя)
            effectText: playedCard.text ?? playedCard.name,
            appliedEffects,
          },
        };
      } catch (error) {
        this.logger.error(
          `Ошибка при розыгрыше scheme-карты [gameId=${context.gameId}]: ${error}`,
          { gameId: context.gameId, userId: context.userId, dto },
        );
        this.metrics.incrementError('GameActionExecutor', 'executePlayScheme', error instanceof Error ? error.name : 'unknown');
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    });
  }

  /**
   * Разрешить бой
   */
  async executeResolveCombat(
    dto: ResolveCombatDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    if (context.currentState.metadata.pendingManeuver || context.currentState.metadata.pendingHandDiscard) {
      return { success: false, error: 'Resolve the pending resource choice first' };
    }
    if ((context.currentState.metadata.pendingEffects?.length ?? 0) > 0) {
      return { success: false, error: 'Resolve the pending choice first' };
    }
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    return this.metrics.measureServiceDuration('executeResolveCombat', 'GameActionExecutor', async () => {
      try {
        const { userId, currentState, gameId } = context;
        if (currentState.metadata.combatResolutionProgress && currentState.metadata.pendingEffects?.length) {
          return { success: false, error: 'Resolve the pending combat effect first' };
        }
        const progress: CombatResolutionProgress = {
          defeatedBefore: currentState.fighters.filter(f => f.isDefeated).map(f => f.id),
          ...currentState.metadata.combatResolutionProgress,
        };
        const pause = (state: GameState): ActionResult => ({
          success: true,
          gameState: { ...state, phase: GamePhase.COMBAT_RESOLVE,
            sequenceNumber: currentState.sequenceNumber + 1,
            metadata: { ...state.metadata, combatResolutionProgress: progress,
              lastActionAt: new Date(), lastActionBy: userId } },
          metadata: { action: 'resolveCombat', performedAt: new Date(), performedBy: userId,
            sequenceNumber: currentState.sequenceNumber + 1 },
        });
        const withoutState = <T extends { state: GameState }>(result: T): Omit<T, 'state'> => {
          const { state: _state, ...rest } = result;
          return rest;
        };


        // Проверяем фазу
        if (currentState.phase !== GamePhase.COMBAT && currentState.phase !== GamePhase.COMBAT_RESOLVE) {
          this.metrics.incrementGameAction('resolveCombat', undefined, 'error');
          return { success: false, error: 'Not in combat phase' };
        }

        const combatInfo = currentState.metadata.combatInfo;
        if (!combatInfo) {
          this.metrics.incrementGameAction('resolveCombat', undefined, 'error');
          return { success: false, error: 'No combat in progress' };
        }

        // Цель — атакованный боец из combatInfo.targetFighterId (атака по
        // сайдкику ранит сайдкика); легаси-сейвы без поля → fallback на
        // первого бойца защитника (старое поведение)
        const attacker = currentState.fighters.find((f) => f.id === combatInfo.attackerId);
        const defenderFighter =
          (combatInfo.targetFighterId
            ? currentState.fighters.find((f) => f.id === combatInfo.targetFighterId)
            : undefined) ??
          currentState.fighters.find((f) => f.ownerId === combatInfo.defenderId);

        if (!attacker || !defenderFighter) {
          this.metrics.incrementGameAction('resolveCombat', undefined, 'error');
          return { success: false, error: 'Combat participants not found' };
        }

        // Сыгранные карты (обе уже в сбросе — ищем везде по instance id)
        const attackerCard = this.findCardAnywhere(currentState, combatInfo.attackerCardId);
        const defenderCard = combatInfo.defenderCardId
          ? this.findCardAnywhere(currentState, combatInfo.defenderCardId)
          : null;

        const combatCtx = {
          attackerFighterId: attacker.id,
          targetFighterId: defenderFighter.id,
          attackerPlayerId: attacker.ownerId,
          defenderPlayerId: combatInfo.defenderId,
          attackCardId: combatInfo.attackerCardId,
          defenseCardId: combatInfo.defenderCardId,
          attackValue: combatInfo.attackValue,
          defenseValue: combatInfo.defenseValue,
        };

        // === Пайплайн боя (правила Unmatched) ===
        // 1. ON_REVEAL (вскрытие): защитник → атакующий, cancel-флаги
        const savedReveal = progress.reveal;
        let reveal = savedReveal
          ? savedReveal.paused
            ? await this.cardEffectExecutor.resumeCombatEffects(currentState)
            : { ...savedReveal, state: currentState }
          : await this.cardEffectExecutor.executeRevealEffects(currentState, attackerCard, defenderCard, combatCtx);
        if (savedReveal?.paused) {
          reveal = { ...reveal, appliedEffects: [...savedReveal.appliedEffects, ...reveal.appliedEffects],
            manualEffects: [...savedReveal.manualEffects, ...reveal.manualEffects] };
        }
        progress.reveal = withoutState(reveal);
        if (reveal.paused) return pause(reveal.state);
        const cancelled = {
          attacker: reveal.attackerCardCancelled,
          defender: reveal.defenderCardCancelled,
        };

        // 2. DURING_COMBAT: эффекты карт → финальные значения
        const savedCalculation = progress.calculation;
        let calc = savedCalculation
          ? savedCalculation.paused
            ? await this.cardEffectExecutor.resumeCombatEffects(reveal.state)
            : { ...savedCalculation, state: reveal.state }
          : await this.cardEffectExecutor.executeCombatEffects(reveal.state, attackerCard, defenderCard, {
              ...combatCtx,
              // R-16: отменённая карта (Feint) сохраняет печатное значение, но
              // boost (карта + способность Arthur) сбрасывается без эффекта.
              attackValue: cancelled.attacker
                ? (attackerCard?.attackValue ?? combatCtx.attackValue)
                : combatCtx.attackValue + (combatInfo.boostValue ?? 0),
              defenseValue: cancelled.defender ? (defenderCard?.defenseValue ?? combatCtx.defenseValue) : combatCtx.defenseValue,
            }, cancelled);
        if (savedCalculation?.paused) {
          calc = { ...calc, appliedEffects: [...savedCalculation.appliedEffects, ...calc.appliedEffects],
            manualEffects: [...savedCalculation.manualEffects, ...calc.manualEffects] };
        }
        progress.calculation = withoutState(calc);
        if (calc.paused) return pause(calc.state);
        if ('attackerCardCancelled' in calc) cancelled.attacker = calc.attackerCardCancelled === true;
        if ('defenderCardCancelled' in calc) cancelled.defender = calc.defenderCardCancelled === true;


        // Модификаторы способностей героев — ПОСЛЕ карточных SET/MODIFY
        // (set value заменяет значение карты, ability добавляется поверх)
        const heroMods = this.combatResolver.getHeroCombatModifiers(attacker, defenderFighter, {
          attackerId: attacker.id,
          defenderId: defenderFighter.id,
          attackCardId: combatInfo.attackerCardId,
          defenseCardId: combatInfo.defenderCardId,
        });

        // STATEFUL-модификаторы способностей (доступ к GameState): классический
        // applyCombatModifier видит только CombatState+fighter+role и не может
        // оценивать условия на состоянии игры. Этот хук читает GameState.
        // ADD-семантика та же — суммируем ТОЛЬКО ADD и добавляем поверх heroMods.
        // Аддитивно: математику heroMods не трогаем. Slug — heroSlug ?? heroId.
        const statefulAttack = this.sumAddModifiers(
          this.abilityRegistry.getStatefulCombatModifiers(
            attacker.heroSlug ?? attacker.heroId,
            calc.state,
            combatInfo,
            attacker,
            'attacker',
          ),
        );
        const statefulDefense = this.sumAddModifiers(
          this.abilityRegistry.getStatefulCombatModifiers(
            defenderFighter.heroSlug ?? defenderFighter.heroId,
            calc.state,
            combatInfo,
            defenderFighter,
            'defender',
          ),
        );

        // АУРНЫЕ модификаторы (Oda-style): аура исходит от ДРУГОГО героя
        // (гранителя), а не от героя бойца боя — поэтому консультируем ВСЕ
        // зарегистрированные handler'ы для каждого бойца-бенефициара.
        // Аддитивно: математику heroMods/stateful не трогаем.
        const auraAttack = this.sumAddModifiers(
          this.abilityRegistry.getAuraCombatModifiers(calc.state, attacker, 'attacker'),
        );
        const auraDefense = this.sumAddModifiers(
          this.abilityRegistry.getAuraCombatModifiers(calc.state, defenderFighter, 'defender'),
        );

        const finalAttack = progress.damage?.finalAttack ??
          Math.max(0, calc.finalAttack + heroMods.attackModifier + statefulAttack + auraAttack);
        const finalDefense = progress.damage?.finalDefense ??
          Math.max(0, calc.finalDefense + heroMods.defenseModifier + statefulDefense + auraDefense);

        // Only the attack deals combat damage; prevention determines the winner.
        const attackerDamage = 0;
        const participantsAlive = [attacker.id, defenderFighter.id].every(id =>
          calc.state.fighters.some(f => f.id === id && f.health > 0 && !f.isDefeated));
        const defenderDamage = progress.damage?.defenderDamage ?? (calc.state.phase === GamePhase.GAME_OVER || !participantsAlive || calc.preventDamageToDefender
          ? 0 : Math.max(0, finalAttack - finalDefense));
        const attackerWon = defenderDamage > 0;

        let workState: GameState = {
          ...calc.state,
          fighters: progress.damage ? calc.state.fighters : calc.state.fighters.map((f) => {
            if (f.id === attacker.id && attackerDamage > 0) {
              return { ...f, health: Math.max(0, f.health - attackerDamage) };
            }
            if (f.id === defenderFighter.id && defenderDamage > 0) {
              return { ...f, health: Math.max(0, f.health - defenderDamage) };
            }
            return f;
          }),
        };

        workState = applyTerminalState(workState);
        progress.damage = { finalAttack, finalDefense, attackerDamage, defenderDamage, attackerWon };

        // 4. AFTER_COMBAT: defender first, unless the duel has ended.
        const savedAfter = progress.after;
        let after = workState.phase === GamePhase.GAME_OVER
          ? { state: workState, appliedEffects: [], manualEffects: [], paused: false }
          : savedAfter?.paused
            ? await this.cardEffectExecutor.resumeCombatEffects(workState)
            : await this.cardEffectExecutor.executeAfterCombatEffects(workState, attackerCard, defenderCard,
                combatCtx, { attackerWon, attackerDamage, defenderDamage }, cancelled);
        if (savedAfter?.paused) {
          after = { ...after, appliedEffects: [...savedAfter.appliedEffects, ...after.appliedEffects],
            manualEffects: [...savedAfter.manualEffects, ...after.manualEffects] };
        }
        progress.after = withoutState(after);
        if (after.paused) return pause(after.state);
        workState = after.state;

        const appliedEffects = [
          ...reveal.appliedEffects,
          ...calc.appliedEffects,
          ...after.appliedEffects,
        ];
        const manualEffects = [
          ...reveal.manualEffects,
          ...calc.manualEffects,
          ...after.manualEffects,
        ];

        // 5. Итоги: павшие бойцы и живость игроков (after-эффекты могли добить)
        // Снимок id повергнутых ДО этого боя — чтобы вычислить НОВО-павших
        // (для on-defeat хука: дёргаем только тех, кто пал ИМЕННО в этом бою).
        const defeatedBefore = new Set(
          progress.defeatedBefore,
        );
        const updatedFighters = workState.fighters.map((f) =>
          f.health <= 0 && !f.isDefeated ? { ...f, isDefeated: true } : f,
        );
        const newlyDefeated = updatedFighters.filter(
          (f) => f.isDefeated === true && !defeatedBefore.has(f.id),
        );
        let resolvedState = applyTerminalState({ ...workState, fighters: updatedFighters });

        // Per-turn флаги действий (TASK). ВАЖНО про порядок:
        //  - stateful combat-модификаторы ЭТОЙ атаки уже собраны выше (видели
        //    attackedThisTurn в значении ДО этой атаки — первая атака видит
        //    false, вторая true);
        //  - firstLossThisTurn считаем ДО установки lostCombatThisTurn: при
        //    проигрыше (won===false) это первый проигрыш хода, если флаг ещё
        //    не стоял; при победе — всегда false;
        //  - attackedThisTurn ставим в true в КОНЦЕ резолва (после сбора
        //    модификаторов), чтобы СЛЕДУЮЩАЯ атака того же хода видела true.
        const firstLossThisTurn = !attackerWon && !resolvedState.metadata.lostCombatThisTurn;
        resolvedState = {
          ...resolvedState,
          metadata: {
            ...resolvedState.metadata,
            attackedThisTurn: true,
            lostCombatThisTurn: resolvedState.metadata.lostCombatThisTurn || !attackerWon,
          },
        };

        // AFTER-COMBAT хуки способностей: защитник первым; урон применён,
        // флаги поражения проставлены, combat-модификаторы собраны. Бьём ДО
        // передачи хода (advanceTurn), чтобы любой добор/лечение/доп. действие
        // легли в ТОТ ЖЕ резолв — и независимо от того, авто-завершается ли ход.
        // Слаг резолвится с атакующего бойца (combatInfo.attackerId) внутри
        // helper'а — даже если боец повержен (он остаётся в state.fighters).
        // seq отдельно НЕ бампим: «прицеплено» к инкременту резолва ниже.
        const afterCombatCtx: AfterCombatContext = {
          playerId: attacker.ownerId,
          defenderPlayerId: defenderFighter.ownerId,
          attackerFighterId: combatInfo.attackerId,
          defenderFighterId: defenderFighter.id,
          won: attackerWon,
          damageDealt: defenderDamage,
          firstLossThisTurn,
        };
        if (resolvedState.phase !== GamePhase.GAME_OVER) {
          resolvedState = applyTerminalState(await this.triggerHeroAfterDefense(resolvedState, afterCombatCtx));
        }
        // Затем after-attack хук атакующего героя.
        // Бьём тем же ctx, ДО передачи хода, теми же seq-правилами.
        if (resolvedState.phase !== GamePhase.GAME_OVER) {
          resolvedState = applyTerminalState(await this.triggerHeroAfterCombat(resolvedState, afterCombatCtx));
        }

        // ON-DEFEAT хук (TASK, РЕАНИМАЦИЯ): для каждого НОВО-павшего бойца дёргаем
        // onFighterDefeated героя ВЛАДЕЛЬЦА бойца — чтобы он отреагировал на гибель
        // своего сайдкика (Achilles → discard 2). Бьём ПОСЛЕ after-combat хуков и
        // установки isDefeated, но ДО game-over/передачи хода. seq не бампим:
        // «прицеплено» к инкременту резолва. No-op для героев без хука.
        for (const fallen of newlyDefeated) {
          if (resolvedState.phase === GamePhase.GAME_OVER) break;
          resolvedState = applyTerminalState(await this.triggerHeroFighterDefeated(resolvedState, fallen.id));
        }

        // Конец игры (правило «остался один живой игрок») — единый helper.
        // checkAndApplyGameOver no-op при живых > 1 (фаза/metadata не тронуты);
        // при game-over ставит GAME_OVER + winnerId + чистит combatInfo.
        const afterGameOver = this.checkAndApplyGameOver(resolvedState);
        const gameEnded = afterGameOver.phase === GamePhase.GAME_OVER;

        let newState: GameState;
        if (gameEnded) {
          newState = {
            ...afterGameOver,
            sequenceNumber: currentState.sequenceNumber + 1,
            metadata: {
              ...afterGameOver.metadata,
              lastActionAt: new Date(),
              lastActionBy: userId,
            },
          };
        } else {
          // Бой завершён. Действие списано при объявлении атаки (executeAttack),
          // поэтому здесь только смотрим остаток: >0 — ход ПРОДОЛЖАЕТСЯ (атака
          // могла быть первым действием), 0 — авто-завершение хода.
          // GAIN_ACTION/END_TURN из after-эффектов уже изменили actionsRemaining.
          // Промежуточное состояние БЕЗ инкремента seq — +1 делает advanceTurn
          // или ветка продолжения хода. Остаток/следующий игрок считаются от
          // currentTurnPlayerId (атакующего), даже если мутацию вызвал защитник
          // (CombatResolveGuard).
          const intermediate: GameState = {
            ...resolvedState,
            metadata: {
              ...resolvedState.metadata,
              combatInfo: undefined,
              combatResolutionProgress: undefined,
              combatEffectContinuation: undefined,
            },
          };
          if (getActionsRemaining(intermediate) > 0) {
            // У атакующего остались действия — возвращаем ему ход (свой +1 к seq)
            newState = {
              ...intermediate,
              phase: GamePhase.ACTION_MANEUVER,
              sequenceNumber: currentState.sequenceNumber + 1,
              metadata: {
                ...intermediate.metadata,
                lastActionAt: new Date(),
                lastActionBy: userId,
              },
            };
          } else {
            newState = await this.advanceTurn(intermediate, userId);
          }
        }

        this.metrics.incrementGameAction('resolveCombat', undefined, 'success');

        return {
          success: true,
          gameState: newState,
          metadata: {
            action: 'resolveCombat',
            performedAt: new Date(),
            performedBy: userId,
            sequenceNumber: newState.sequenceNumber,
            // Лог эффектов для Game Tester: применённые + требующие рук
            appliedEffects,
            manualEffects,
            combatSummary: {
              finalAttack,
              finalDefense,
              attackerDamage,
              defenderDamage,
              attackerWon,
              attackerCardCancelled: cancelled.attacker,
              defenderCardCancelled: cancelled.defender,
            },
          },
        };
      } catch (error) {
        this.logger.error(
          `Ошибка при разрешении боя [gameId=${context.gameId}]: ${error}`,
          { gameId: context.gameId, userId: context.userId, dto },
        );
        this.metrics.incrementError('GameActionExecutor', 'executeResolveCombat', error instanceof Error ? error.name : 'unknown');
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    });
  }

  /**
   * Завершить ход
   */
  async executeEndTurn(
    dto: EndTurnDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    if (context.currentState.metadata.pendingManeuver || context.currentState.metadata.pendingHandDiscard) {
      return { success: false, error: 'Resolve the pending resource choice first' };
    }
    if ((context.currentState.metadata.pendingEffects?.length ?? 0) > 0) {
      return { success: false, error: 'Resolve the pending choice first' };
    }
    if (context.currentState.metadata.combatResolutionProgress) {
      return { success: false, error: 'Resolve the pending combat effect first' };
    }
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    try {
      const { userId, currentState } = context;

      // Валидация
      const validation = this.rulesValidator.validateEndTurn(currentState, userId);
      if (!validation.valid) {
        return {
          success: false,
          error: validation.error || 'End turn validation failed',
        };
      }

      // Передаём ход следующему игроку: сразу ACTION_MANEUVER без добора карты
      // (фаза TURN_START пропускается — см. advanceTurn)
      const newState = await this.advanceTurn(currentState, userId);

      return {
        success: true,
        gameState: newState,
        metadata: {
          action: 'endTurn',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка при завершении хода: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Legacy endpoint: passing cannot replace a mandatory action.
   */
  async executePass(
    dto: PassDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    return { success: false, error: 'Passing is not a legal action; use maneuver even without movement' };
  }

  /**
   * Переключить дверь (специальная способность Bjorn)
   */
  async executeToggleDoor(
    dto: ToggleDoorDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    if (context.currentState.metadata.pendingManeuver || context.currentState.metadata.pendingHandDiscard) {
      return { success: false, error: 'Resolve the pending resource choice first' };
    }
    if ((context.currentState.metadata.pendingEffects?.length ?? 0) > 0) {
      return { success: false, error: 'Resolve the pending choice first' };
    }
    if (context.currentState.metadata.combatResolutionProgress) {
      return { success: false, error: 'Resolve the pending combat effect first' };
    }
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    try {
      const { userId, currentState } = context;

      // Валидация
      const validation = this.rulesValidator.validateToggleDoor(
        currentState,
        dto.x,
        dto.y,
        userId,
      );

      if (!validation.valid) {
        return {
          success: false,
          error: validation.error || 'Toggle door validation failed',
        };
      }

      const doorKey = `${dto.x}:${dto.y}`;
      const currentOpen = currentState.boardState.doors?.[doorKey] ?? false;

      const newState: GameState = {
        ...currentState,
        sequenceNumber: currentState.sequenceNumber + 1,
        boardState: {
          ...currentState.boardState,
          doors: {
            ...currentState.boardState.doors,
            [doorKey]: !currentOpen,
          },
        },
        metadata: {
          ...currentState.metadata,
          lastActionAt: new Date(),
          lastActionBy: userId,
        },
      };

      return {
        success: true,
        gameState: newState,
        metadata: {
          action: 'toggleDoor',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка при переключении двери: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Сменить стойку героя (STANCE-подсистема).
   *
   * Мутация-аналог toggleDoor/pass, но НЕ тратит действие (выбор стойки
   * бесплатен — размещение / начало хода / «Change size»-карты). Валидация:
   *  - у вызвавшего игрока есть HERO-боец (его герой);
   *  - этот герой stance-aware (registry.getStances непустой);
   *  - dto.stanceId существует среди стоек героя.
   * Эффект: metadata.heroStances[userId] = stanceId, seq +1, no-op для действий.
   */
  async executeSetStance(
    dto: { gameId: string; stanceId: string },
    context: ActionContext,
  ): Promise<ActionResult> {
    if (context.currentState.metadata.pendingManeuver || context.currentState.metadata.pendingHandDiscard) {
      return { success: false, error: 'Resolve the pending resource choice first' };
    }
    if ((context.currentState.metadata.pendingEffects?.length ?? 0) > 0) {
      return { success: false, error: 'Resolve the pending choice first' };
    }
    if (context.currentState.metadata.combatResolutionProgress) {
      return { success: false, error: 'Resolve the pending combat effect first' };
    }
    if (applyTerminalState(context.currentState).phase === GamePhase.GAME_OVER) {
      return { success: false, error: 'Game is already over' };
    }
    try {
      const { userId, currentState } = context;

      // HERO-боец вызвавшего (его герой) — источник слага для реестра стоек.
      const hero = currentState.fighters.find(
        (f) => f.ownerId === userId && f.type === FighterType.HERO,
      );
      if (!hero) {
        return { success: false, error: 'У игрока нет героя на доске' };
      }

      const slug = hero.heroSlug ?? hero.heroId;
      const stanceIds = this.abilityRegistry.getStances(slug);
      if (stanceIds.length === 0) {
        return { success: false, error: 'У этого героя нет стоек' };
      }
      if (!stanceIds.includes(dto.stanceId)) {
        return {
          success: false,
          error: `Неизвестная стойка «${dto.stanceId}» (доступны: ${stanceIds.join(', ')})`,
        };
      }

      const newState: GameState = {
        ...currentState,
        sequenceNumber: currentState.sequenceNumber + 1,
        metadata: {
          ...currentState.metadata,
          lastActionAt: new Date(),
          lastActionBy: userId,
          heroStances: {
            ...(currentState.metadata.heroStances ?? {}),
            [userId]: dto.stanceId,
          },
        },
      };

      return {
        success: true,
        gameState: newState,
        metadata: {
          action: 'setStance',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка при смене стойки: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Найти сыгранную карту в руке игрока.
   * Принимает и instance id (`${cardId}::n`), и базовый cardId —
   * тот же предикат, что в GameRulesValidator (validateAttackWithParams и др.).
   */
  private findHandCard(state: GameState, userId: string, cardId: string): HandCard | undefined {
    return state.handZones[userId]?.cards.find(
      (c) => c.id === cardId || c.cardId === cardId,
    );
  }

  /**
   * Сумма ADD-модификаторов (та же семантика, что в CombatResolverService.
   * sumValueModifiers — приватен там, поэтому считаем здесь). SET/MULTIPLY/
   * IGNORE сознательно игнорируются: stateful-хук аддитивен к итогам боя.
   */
  private sumAddModifiers(modifiers: readonly ValueModifier[]): number {
    return modifiers.reduce(
      (sum, m) => (m.type === ValueModifierType.ADD ? sum + m.value : sum),
      0,
    );
  }

  /**
   * Найти карту по instance id где угодно: руки, сбросы, полные списки колод.
   * Нужен resolveCombat — сыгранные карты боя уже в сбросе.
   */
  private findCardAnywhere(state: GameState, cardId: string): Card | null {
    for (const handZone of Object.values(state.handZones)) {
      const card = handZone.cards.find((c) => c.id === cardId);
      if (card) return card;
    }
    for (const pile of Object.values(state.discardPiles)) {
      const card = pile.find((c) => c.id === cardId);
      if (card) return card;
    }
    for (const deck of Object.values(state.decks)) {
      const card = deck.cards.find((c) => c.id === cardId);
      if (card) return card;
    }
    return null;
  }
}
