/**
 * Card Effect Executor Service
 *
 * Исполняет структурированные эффекты карт (Card.effects) по таймингам:
 * ON_REVEAL (вскрытие в COMBAT_RESOLVE) → DURING_COMBAT (модификаторы
 * значений) → урон (combat-resolver) → AFTER_COMBAT; плюс ON_PLAY (scheme),
 * TURN_START/TURN_END.
 *
 * Контракты:
 * - Эффекты НИКОГДА не меняют sequenceNumber — ровно +1 на мутацию делает
 *   executor действия (game-action-executor).
 * - Нераспознанное/неподдержанное (UNSUPPORTED, MOVE/PLACE с выбором игрока)
 *   не блокирует игру: текст уезжает в manualEffects для ручного применения
 *   (Game Tester), warn-лог + метрика.
 * - CANCEL_EFFECTS: отменённая карта не исполняет ни reveal-, ни during-,
 *   ни after-эффекты; её ПЕЧАТНОЕ значение сохраняется; отменённый защитник
 *   не отменяет в ответ (его reveal уже не исполняется).
 */

import { Injectable, Logger } from '@nestjs/common';
import { MetricsService } from '../../metrics/metrics.service';
import type { GameState, Card } from '../models';
import {
  CardEffect,
  EffectCondition,
  EffectTiming,
  EffectType,
  EffectTarget,
} from '../models/card.model';
import { ValueModifierService } from '../engine/value-modifier.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { DeckManagementService } from '../services/deck-management.service';

/**
 * Результат выполнения одного эффекта
 */
export interface EffectResult {
  readonly success: boolean;
  readonly effectId: string;
  readonly targetIds: readonly string[];
  readonly valueApplied?: number;
  readonly message?: string;
  /** Эффект требует ручного применения (MOVE/PLACE/UNSUPPORTED) */
  readonly manual?: boolean;
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

/** Результат стадии ON_REVEAL */
export interface RevealResult {
  readonly state: GameState;
  readonly appliedEffects: readonly EffectResult[];
  readonly manualEffects: readonly string[];
  readonly attackerCardCancelled: boolean;
  readonly defenderCardCancelled: boolean;
}

/** Результат стадии DURING_COMBAT */
export interface CombatCalculation {
  readonly state: GameState;
  readonly finalAttack: number;
  readonly finalDefense: number;
  readonly preventDamageToAttacker: boolean;
  readonly preventDamageToDefender: boolean;
  readonly appliedEffects: readonly EffectResult[];
  readonly manualEffects: readonly string[];
}

/** Результат стадии AFTER_COMBAT */
export interface AfterCombatResult {
  readonly state: GameState;
  readonly appliedEffects: readonly EffectResult[];
  readonly manualEffects: readonly string[];
}

export interface OnPlayResult {
  readonly state: GameState;
  readonly appliedEffects: readonly EffectResult[];
  readonly manualEffects: readonly string[];
}

/** Внутренний результат применения одного эффекта */
interface ApplyOutcome {
  state: GameState;
  result: EffectResult;
  manual?: string;
  cancelOpposingCard?: boolean;
  preventDamage?: boolean;
  valueDelta?: number;
  setValue?: number;
}

@Injectable()
export class CardEffectExecutorService {
  private readonly logger = new Logger(CardEffectExecutorService.name);

  constructor(
    private readonly valueModifierService: ValueModifierService,
    private readonly metrics: MetricsService,
    private readonly adjacencyService: AdjacencyService,
    private readonly deckManagement: DeckManagementService,
  ) {}

  // =========================================================================
  // Стадия 1: ON_REVEAL (вскрытие карт) — сначала атакующий, затем защитник
  // =========================================================================

  async executeRevealEffects(
    state: GameState,
    attackerCard: Card | null,
    defenderCard: Card | null,
    combat: CombatContext,
  ): Promise<RevealResult> {
    let currentState = state;
    const appliedEffects: EffectResult[] = [];
    const manualEffects: string[] = [];
    let attackerCardCancelled = false;
    let defenderCardCancelled = false;

    const sides: Array<{ card: Card | null; ctx: EffectContext; isAttacker: boolean }> = [
      {
        card: attackerCard,
        isAttacker: true,
        ctx: this.combatSideContext(attackerCard, combat, 'attacker'),
      },
      {
        card: defenderCard,
        isAttacker: false,
        ctx: this.combatSideContext(defenderCard, combat, 'defender'),
      },
    ];

    for (const side of sides) {
      if (!side.card) continue;
      // Отменённая карта не исполняет reveal (защитник, отменённый атакующим,
      // НЕ отменяет в ответ)
      if (side.isAttacker ? attackerCardCancelled : defenderCardCancelled) continue;

      const effects = (side.card.effects ?? []).filter(
        (e) => e.timing === EffectTiming.ON_REVEAL,
      );
      for (const effect of effects) {
        if (!(await this.passesWhen(currentState, effect, side.ctx))) continue;
        const outcome = await this.applyOneEffect(currentState, effect, side.ctx);
        currentState = outcome.state;
        appliedEffects.push(outcome.result);
        if (outcome.manual) manualEffects.push(outcome.manual);
        if (outcome.cancelOpposingCard) {
          if (side.isAttacker) defenderCardCancelled = true;
          else attackerCardCancelled = true;
        }
      }
    }

    return {
      state: currentState,
      appliedEffects,
      manualEffects,
      attackerCardCancelled,
      defenderCardCancelled,
    };
  }

  // =========================================================================
  // Стадия 2: DURING_COMBAT — финальные значения атаки/защиты
  // Порядок внутри стороны: SET_VALUE → MODIFY_* → VALUE_PER_COUNT → BOOST
  // =========================================================================

  async executeCombatEffects(
    state: GameState,
    attackerCard: Card | null,
    defenderCard: Card | null,
    combat: CombatContext,
    cancelled: { attacker: boolean; defender: boolean } = { attacker: false, defender: false },
  ): Promise<CombatCalculation> {
    return this.metrics.measureServiceDuration(
      'executeCombatEffects',
      'CardEffectExecutor',
      async () => {
        let currentState = state;
        const appliedEffects: EffectResult[] = [];
        const manualEffects: string[] = [];
        let preventDamageToAttacker = false;
        let preventDamageToDefender = false;

        const compute = async (
          card: Card | null,
          base: number,
          role: 'attacker' | 'defender',
          isCancelled: boolean,
        ): Promise<number> => {
          if (!card || isCancelled) return base; // печатное значение сохраняется
          const ctx = this.combatSideContext(card, combat, role);
          const effects = (card.effects ?? []).filter(
            (e) => e.timing === EffectTiming.DURING_COMBAT,
          );

          // 1) SET_VALUE (последний выигрывает), 2) MODIFY, 3) PER_COUNT, 4) прочее
          const order = (e: CardEffect): number =>
            e.type === EffectType.SET_VALUE
              ? 0
              : e.type === EffectType.MODIFY_VALUE ||
                  e.type === EffectType.MODIFY_ATTACK ||
                  e.type === EffectType.MODIFY_DEFENSE
                ? 1
                : e.type === EffectType.VALUE_PER_COUNT
                  ? 2
                  : 3;
          const sorted = [...effects].sort((a, b) => order(a) - order(b));

          let value = base;
          for (const effect of sorted) {
            if (!(await this.passesWhen(currentState, effect, ctx))) continue;
            const outcome = await this.applyOneEffect(currentState, effect, ctx);
            currentState = outcome.state;
            appliedEffects.push(outcome.result);
            if (outcome.manual) manualEffects.push(outcome.manual);
            if (outcome.setValue !== undefined) value = outcome.setValue;
            if (outcome.valueDelta) value += outcome.valueDelta;
            if (outcome.preventDamage) {
              if (role === 'attacker') preventDamageToAttacker = true;
              else preventDamageToDefender = true;
            }
          }
          return value;
        };

        const finalAttack = await compute(
          attackerCard,
          combat.attackValue,
          'attacker',
          cancelled.attacker,
        );
        const finalDefense = await compute(
          defenderCard,
          combat.defenseValue,
          'defender',
          cancelled.defender,
        );

        return {
          state: currentState,
          finalAttack,
          finalDefense,
          preventDamageToAttacker,
          preventDamageToDefender,
          appliedEffects,
          manualEffects,
        };
      },
    );
  }

  // =========================================================================
  // Стадия 4: AFTER_COMBAT — сначала ВСЕ эффекты атакующего, затем защитника
  // (правило Unmatched). Ничья = победа защитника.
  // =========================================================================

  async executeAfterCombatEffects(
    state: GameState,
    attackerCard: Card | null,
    defenderCard: Card | null,
    combat: CombatContext,
    outcome: { attackerWon: boolean; attackerDamage: number; defenderDamage: number },
    cancelled: { attacker: boolean; defender: boolean } = { attacker: false, defender: false },
  ): Promise<AfterCombatResult> {
    let currentState = state;
    const appliedEffects: EffectResult[] = [];
    const manualEffects: string[] = [];

    const sides: Array<{ card: Card | null; role: 'attacker' | 'defender'; isCancelled: boolean }> =
      [
        { card: attackerCard, role: 'attacker', isCancelled: cancelled.attacker },
        { card: defenderCard, role: 'defender', isCancelled: cancelled.defender },
      ];

    for (const side of sides) {
      if (!side.card || side.isCancelled) continue;
      const won = side.role === 'attacker' ? outcome.attackerWon : !outcome.attackerWon;
      const ctx: EffectContext = {
        ...this.combatSideContext(side.card, combat, side.role),
        wonCombat: won,
        damageDealt: side.role === 'attacker' ? outcome.defenderDamage : outcome.attackerDamage,
        damageTaken: side.role === 'attacker' ? outcome.attackerDamage : outcome.defenderDamage,
      };

      const effects = (side.card.effects ?? []).filter(
        (e) => e.timing === EffectTiming.AFTER_COMBAT,
      );
      for (const effect of effects) {
        if (!(await this.passesWhen(currentState, effect, ctx))) continue;
        const applied = await this.applyOneEffect(currentState, effect, ctx);
        currentState = applied.state;
        appliedEffects.push(applied.result);
        if (applied.manual) manualEffects.push(applied.manual);
      }
    }

    return { state: currentState, appliedEffects, manualEffects };
  }

  // =========================================================================
  // ON_PLAY (scheme-карты)
  // =========================================================================

  async executeOnPlayEffects(
    state: GameState,
    card: Card,
    playerId: string,
  ): Promise<OnPlayResult> {
    const onPlayEffects = (card.effects ?? []).filter(
      // scheme-карта: исполняем и ON_PLAY, и AFTER_COMBAT-тексты (effectAfter
      // у scheme-карт описывает «после розыгрыша»)
      (e) => e.timing === EffectTiming.ON_PLAY || e.timing === EffectTiming.AFTER_COMBAT,
    );

    let currentState = state;
    const appliedEffects: EffectResult[] = [];
    const manualEffects: string[] = [];
    const fighter = currentState.fighters.find((f) => f.ownerId === playerId && !f.isDefeated);

    for (const effect of onPlayEffects) {
      const context: EffectContext = { playerId, card, fighterId: fighter?.id };
      if (!(await this.passesWhen(currentState, effect, context))) continue;
      const outcome = await this.applyOneEffect(currentState, effect, context);
      currentState = outcome.state;
      appliedEffects.push(outcome.result);
      if (outcome.manual) manualEffects.push(outcome.manual);
    }

    return { state: currentState, appliedEffects, manualEffects };
  }

  // =========================================================================
  // TURN_START / TURN_END (карты в руке игрока)
  // =========================================================================

  async executeTurnStartEffects(state: GameState, playerId: string): Promise<GameState> {
    return this.executeHandTimingEffects(state, playerId, EffectTiming.TURN_START);
  }

  async executeTurnEndEffects(state: GameState, playerId: string): Promise<GameState> {
    return this.executeHandTimingEffects(state, playerId, EffectTiming.TURN_END);
  }

  private async executeHandTimingEffects(
    state: GameState,
    playerId: string,
    timing: EffectTiming,
  ): Promise<GameState> {
    const handZone = state.handZones[playerId];
    if (!handZone) return state;

    let currentState = state;
    for (const card of handZone.cards) {
      const effects = (card.effects ?? []).filter((e) => e.timing === timing);
      for (const effect of effects) {
        const context: EffectContext = { playerId, card };
        if (!(await this.passesWhen(currentState, effect, context))) continue;
        const outcome = await this.applyOneEffect(currentState, effect, context);
        currentState = outcome.state;
      }
    }
    return currentState;
  }

  // =========================================================================
  // Применение одного эффекта (единая точка)
  // =========================================================================

  private async applyOneEffect(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): Promise<ApplyOutcome> {
    const value = effect.value ?? 0;
    const ok = (
      partial: Partial<EffectResult> & { targetIds?: readonly string[] },
    ): EffectResult => ({
      success: true,
      effectId: effect.id,
      targetIds: partial.targetIds ?? [],
      valueApplied: partial.valueApplied,
      message: partial.message,
      manual: partial.manual,
    });

    switch (effect.type) {
      // --- модификаторы значений (применяет вызывающая стадия) ---
      case EffectType.SET_VALUE:
        return { state, result: ok({ valueApplied: value }), setValue: value };

      case EffectType.MODIFY_VALUE:
      case EffectType.MODIFY_ATTACK:
      case EffectType.MODIFY_DEFENSE:
        return { state, result: ok({ valueApplied: value }), valueDelta: value };

      case EffectType.VALUE_PER_COUNT: {
        const count = await this.computeCount(state, effect, context);
        const per = effect.count?.per ?? 1;
        const delta = count * per;
        return {
          state,
          result: ok({ valueApplied: delta, message: `+${per}×${count}` }),
          valueDelta: delta,
        };
      }

      case EffectType.BOOST: {
        // PLAYER_CHOICE_HAND обрабатывается мутацией (boostCardId, A7) — здесь
        // только авто-источники
        if (effect.boostSource === 'SELF_DECK_TOP') {
          return this.applyDeckTopBoost(state, effect, context);
        }
        if (effect.boostSource === 'OPPONENT_RANDOM_HAND') {
          return this.applyOpponentRandomBoost(state, effect, context);
        }
        // PLAYER_CHOICE_HAND: ничего не делаем (выбор игрока в мутации)
        return { state, result: ok({ message: 'BOOST: выбор карты — через boostCardId' }) };
      }

      case EffectType.CANCEL_EFFECTS:
        return {
          state,
          result: ok({ message: 'Эффекты карты противника отменены' }),
          cancelOpposingCard: true,
        };

      case EffectType.PREVENT_DAMAGE:
        return { state, result: ok({ message: 'Урон предотвращён' }), preventDamage: true };

      // --- изменения состояния ---
      case EffectType.DAMAGE: {
        const targets = await this.resolveTargets(state, effect, context);
        if (targets.length === 0) {
          return { state, result: { success: false, effectId: effect.id, targetIds: [], message: 'No valid targets' } };
        }
        let next = state;
        for (const t of targets) next = this.applyDamage(next, t, value);
        return { state: next, result: ok({ targetIds: targets, valueApplied: value }) };
      }

      case EffectType.HEAL: {
        const targets = await this.resolveTargets(state, effect, context);
        if (targets.length === 0) {
          return { state, result: { success: false, effectId: effect.id, targetIds: [], message: 'No valid targets' } };
        }
        let next = state;
        for (const t of targets) next = this.applyHeal(next, t, value);
        return { state: next, result: ok({ targetIds: targets, valueApplied: value }) };
      }

      case EffectType.DRAW_CARD: {
        const next = await this.deckManagement.drawCards(state, context.playerId, value || 1);
        return { state: next, result: ok({ targetIds: [context.playerId], valueApplied: value || 1 }) };
      }

      case EffectType.DISCARD: {
        const next = await this.discardRandomCards(state, context.playerId, value || 1);
        return { state: next, result: ok({ targetIds: [context.playerId], valueApplied: value || 1 }) };
      }

      case EffectType.OPPONENT_DISCARD: {
        const opponentId = this.opponentPlayerId(state, context);
        if (!opponentId) {
          return { state, result: { success: false, effectId: effect.id, targetIds: [], message: 'No opponent' } };
        }
        const next = await this.discardRandomCards(state, opponentId, value || 1);
        return { state: next, result: ok({ targetIds: [opponentId], valueApplied: value || 1 }) };
      }

      case EffectType.GAIN_ACTION: {
        const next: GameState = {
          ...state,
          metadata: {
            ...state.metadata,
            actionsRemaining: (state.metadata.actionsRemaining ?? 0) + (value || 1),
          },
        };
        return { state: next, result: ok({ valueApplied: value || 1 }) };
      }

      case EffectType.END_TURN: {
        const next: GameState = {
          ...state,
          metadata: { ...state.metadata, actionsRemaining: 0 },
        };
        return { state: next, result: ok({ message: 'Ход завершается' }) };
      }

      case EffectType.RETURN_TO_HAND:
        return this.applyReturnToHand(state, effect, context);

      case EffectType.IMMOBILIZE: {
        const targets = await this.resolveTargets(state, effect, context);
        let next = state;
        for (const t of targets) {
          next = {
            ...next,
            fighters: next.fighters.map((f) =>
              f.id === t
                ? {
                    ...f,
                    effects: [
                      ...f.effects,
                      { type: 'immobilized', duration: 'turn' as const, source: effect.id },
                    ],
                  }
                : f,
            ),
          };
        }
        return { state: next, result: ok({ targetIds: targets }) };
      }

      // --- требуют выбора игрока → manualEffects (MVP, до pendingEffects) ---
      case EffectType.MOVE:
      case EffectType.PLACE: {
        const text = effect.text ?? `${effect.type} ${value || ''}`.trim();
        return {
          state,
          result: ok({ manual: true, message: text }),
          manual: text,
        };
      }

      case EffectType.UNSUPPORTED:
      default: {
        const text = effect.text ?? `Неподдержанный эффект: ${effect.type}`;
        this.logger.warn(`UNSUPPORTED effect executed manually: ${text}`, {
          effectId: effect.id,
          cardId: context.card.id,
        });
        this.metrics.incrementError('CardEffectExecutor', 'unsupported-effect', effect.type);
        return {
          state,
          result: {
            success: false,
            effectId: effect.id,
            targetIds: [],
            manual: true,
            message: text,
          },
          manual: text,
        };
      }
    }
  }

  // =========================================================================
  // Условия (when) и счётчики (count)
  // =========================================================================

  private async passesWhen(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): Promise<boolean> {
    // legacy-строковое условие
    if (effect.condition && !this.evaluateLegacyCondition(state, effect.condition, context)) {
      return false;
    }
    if (!effect.when) return true;
    return this.evaluateWhen(state, effect.when, context);
  }

  private async evaluateWhen(
    state: GameState,
    when: EffectCondition,
    context: EffectContext,
  ): Promise<boolean> {
    switch (when.kind) {
      case 'WON_COMBAT':
        // в during-стадии исход неизвестен → false (эффект сработает в after)
        return context.wonCombat === true;
      case 'LOST_COMBAT':
        return context.wonCombat === false;
      case 'IS_ATTACKING':
        return context.combat?.attackerPlayerId === context.playerId;
      case 'IS_DEFENDING':
        return context.combat?.defenderPlayerId === context.playerId;
      case 'DECK_EMPTY': {
        const deck = state.decks[context.playerId];
        return !deck || deck.drawPile.length === 0;
      }
      case 'HAND_COUNT_AT_MOST': {
        const hand = state.handZones[context.playerId];
        return (hand?.cards.length ?? 0) <= (when.value ?? 0);
      }
      case 'HAND_COUNT_AT_LEAST': {
        const hand = state.handZones[context.playerId];
        return (hand?.cards.length ?? 0) >= (when.value ?? 0);
      }
      case 'HEALTH_AT_MOST': {
        const fighter = state.fighters.find((f) => f.id === context.fighterId);
        return fighter != null && fighter.health <= (when.value ?? 0);
      }
      case 'ADJACENT_TO_OPPONENT':
      case 'NOT_ADJACENT_TO_OPPONENT': {
        const self = state.fighters.find((f) => f.id === context.fighterId);
        const opp = state.fighters.find((f) => f.id === context.opposingFighterId);
        if (!self || !opp) return when.kind === 'NOT_ADJACENT_TO_OPPONENT';
        const adjacent = await this.adjacencyService.isAdjacent(
          state,
          self.position,
          opp.position,
        );
        return when.kind === 'ADJACENT_TO_OPPONENT' ? adjacent : !adjacent;
      }
      case 'MOVED_THIS_TURN': {
        // снапшот позиций пишет advanceTurn → metadata.turnStartPositions
        const startPositions = (state.metadata as { turnStartPositions?: Record<string, { x: number; y: number }> })
          .turnStartPositions;
        const fighter = state.fighters.find((f) => f.id === context.fighterId);
        if (!fighter || !startPositions) return false;
        const start = startPositions[fighter.id];
        return start != null && (start.x !== fighter.position.x || start.y !== fighter.position.y);
      }
      case 'OPPONENT_IS_HERO': {
        const opp = state.fighters.find((f) => f.id === context.opposingFighterId);
        return opp?.type === 'HERO';
      }
      default:
        this.logger.warn(`Unknown when.kind: ${(when as { kind: string }).kind}`);
        return false;
    }
  }

  private evaluateLegacyCondition(
    state: GameState,
    condition: string,
    context: EffectContext,
  ): boolean {
    if (condition === 'low_health' && context.fighterId) {
      const fighter = state.fighters.find((f) => f.id === context.fighterId);
      return fighter ? fighter.health < fighter.maxHealth * 0.5 : false;
    }
    return true;
  }

  private async computeCount(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): Promise<number> {
    const spec = effect.count;
    if (!spec) return 0;
    switch (spec.source) {
      case 'CARDS_IN_HAND':
        return state.handZones[context.playerId]?.cards.length ?? 0;
      case 'FRIENDLY_ADJACENT_TO_OPPONENT': {
        const opp = state.fighters.find((f) => f.id === context.opposingFighterId);
        if (!opp) return 0;
        let count = 0;
        for (const f of state.fighters) {
          if (f.ownerId !== context.playerId || f.isDefeated || f.health <= 0) continue;
          if (f.id === context.fighterId) continue; // «other friendly fighter»
          if (await this.adjacencyService.isAdjacent(state, f.position, opp.position)) count++;
        }
        return count;
      }
      case 'DISCARD_NAME_PREFIX': {
        const prefix = (spec.namePrefix ?? '').toLowerCase();
        if (!prefix) return 0;
        const pile = state.discardPiles[context.playerId] ?? [];
        return pile.filter(
          (c) =>
            c.id !== context.card.id &&
            (c.nameEn ?? c.name ?? '').toLowerCase().startsWith(prefix),
        ).length;
      }
      case 'DAMAGE_DEALT':
        return context.damageDealt ?? 0;
      case 'DAMAGE_TAKEN':
        return context.damageTaken ?? 0;
      default:
        return 0;
    }
  }

  // =========================================================================
  // Цели
  // =========================================================================

  private async resolveTargets(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): Promise<string[]> {
    const target = effect.target ?? EffectTarget.SELF;

    switch (target) {
      case EffectTarget.SELF: {
        if (context.fighterId) return [context.fighterId];
        const fighter = state.fighters.find(
          (f) => f.ownerId === context.playerId && !f.isDefeated && f.health > 0,
        );
        return fighter ? [fighter.id] : [];
      }

      case EffectTarget.OPPOSING_FIGHTER:
        return context.opposingFighterId ? [context.opposingFighterId] : [];

      case EffectTarget.ATTACKER:
        return context.combat ? [context.combat.attackerFighterId] : [];

      case EffectTarget.DEFENDER:
        return context.combat ? [context.combat.targetFighterId] : [];

      case EffectTarget.ALL_ENEMIES:
        return state.fighters
          .filter((f) => f.ownerId !== context.playerId && !f.isDefeated && f.health > 0)
          .map((f) => f.id);

      case EffectTarget.ALL_ALLIES:
        return state.fighters
          .filter((f) => f.ownerId === context.playerId && !f.isDefeated && f.health > 0)
          .map((f) => f.id);

      case EffectTarget.ENEMIES_ADJACENT_TO_SELF: {
        const self = state.fighters.find((f) => f.id === context.fighterId);
        if (!self) return [];
        const result: string[] = [];
        for (const f of state.fighters) {
          if (f.ownerId === context.playerId || f.isDefeated || f.health <= 0) continue;
          if (await this.adjacencyService.isAdjacent(state, self.position, f.position)) {
            result.push(f.id);
          }
        }
        return result;
      }

      case EffectTarget.ADJACENT_ENEMY: {
        // несколько кандидатов → первый валидный + warn (MVP до pendingEffects)
        // якорь — fighterName, если задан («a fighter adjacent to Daredevil»)
        const anchor = effect.fighterName
          ? state.fighters.find(
              (f) =>
                f.ownerId === context.playerId &&
                this.nameMatches(f.name, effect.fighterName!),
            )
          : state.fighters.find((f) => f.id === context.fighterId);
        if (!anchor) return [];
        const candidates: string[] = [];
        for (const f of state.fighters) {
          if (f.ownerId === context.playerId || f.isDefeated || f.health <= 0) continue;
          if (await this.adjacencyService.isAdjacent(state, anchor.position, f.position)) {
            candidates.push(f.id);
          }
        }
        if (candidates.length > 1) {
          this.logger.warn(
            `ADJACENT_ENEMY: ${candidates.length} кандидатов, выбран первый (MVP)`,
            { effectId: effect.id },
          );
        }
        return candidates.slice(0, 1);
      }

      case EffectTarget.NAMED_FIGHTER: {
        const name = effect.fighterName ?? '';
        return state.fighters
          .filter(
            (f) =>
              f.ownerId === context.playerId &&
              !f.isDefeated &&
              f.health > 0 &&
              this.nameMatches(f.name, name),
          )
          .map((f) => f.id);
      }

      case EffectTarget.OPPONENT_PLAYER: {
        const opp = this.opponentPlayerId(state, context);
        return opp ? [opp] : [];
      }

      default:
        return [];
    }
  }

  /** «Harpy 2» матчит «Harpy»; регистронезависимо */
  private nameMatches(fighterName: string, effectName: string): boolean {
    const base = fighterName.replace(/\s+\d+$/, '').trim().toLowerCase();
    return base === effectName.trim().toLowerCase() || fighterName.trim().toLowerCase() === effectName.trim().toLowerCase();
  }

  private opponentPlayerId(state: GameState, context: EffectContext): string | null {
    if (context.combat) {
      return context.playerId === context.combat.attackerPlayerId
        ? context.combat.defenderPlayerId
        : context.combat.attackerPlayerId;
    }
    const other = state.players.find((p) => p.userId !== context.playerId && p.isAlive);
    return other?.userId ?? null;
  }

  // =========================================================================
  // Хелперы изменения состояния (иммутабельно, seq НЕ трогаем)
  // =========================================================================

  /** N случайных сбросов; пустая рука — не ошибка (сколько есть) */
  private async discardRandomCards(
    state: GameState,
    playerId: string,
    count: number,
  ): Promise<GameState> {
    let next = state;
    for (let i = 0; i < count; i++) {
      if ((next.handZones[playerId]?.cards.length ?? 0) === 0) break;
      const { gameState } = await this.deckManagement.discardRandomCard(next, playerId);
      next = gameState;
    }
    return next;
  }

  private applyDamage(state: GameState, fighterId: string, damage: number): GameState {
    return {
      ...state,
      fighters: state.fighters.map((f) =>
        f.id === fighterId ? { ...f, health: Math.max(0, f.health - damage) } : f,
      ),
    };
  }

  private applyHeal(state: GameState, fighterId: string, amount: number): GameState {
    return {
      ...state,
      fighters: state.fighters.map((f) =>
        f.id === fighterId ? { ...f, health: Math.min(f.maxHealth, f.health + amount) } : f,
      ),
    };
  }

  /** BLIND BOOST: сброс верха СВОЕЙ колоды, += его boostValue */
  private applyDeckTopBoost(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): ApplyOutcome {
    const deck = state.decks[context.playerId];
    const top = deck?.drawPile[0];
    if (!top) {
      return {
        state,
        result: { success: false, effectId: effect.id, targetIds: [], message: 'Колода пуста — BOOST невозможен' },
      };
    }
    const boost = top.boostValue ?? 0;
    const next: GameState = {
      ...state,
      decks: {
        ...state.decks,
        [context.playerId]: {
          ...deck,
          drawPile: deck.drawPile.slice(1),
          topCard: deck.drawPile[1],
        },
      },
      discardPiles: {
        ...state.discardPiles,
        [context.playerId]: [...(state.discardPiles[context.playerId] ?? []), top],
      },
    };
    return {
      state: next,
      result: {
        success: true,
        effectId: effect.id,
        targetIds: [context.playerId],
        valueApplied: boost,
        message: `BLIND BOOST: «${top.name}» (+${boost})`,
      },
      valueDelta: boost,
    };
  }

  /** «Your opponent discards 1 random card. Add its BOOST value…» */
  private applyOpponentRandomBoost(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): ApplyOutcome {
    const opponentId = this.opponentPlayerId(state, context);
    const hand = opponentId ? state.handZones[opponentId] : undefined;
    if (!opponentId || !hand || hand.cards.length === 0) {
      return {
        state,
        result: { success: false, effectId: effect.id, targetIds: [], message: 'У оппонента нет карт' },
      };
    }
    const idx = Math.floor(Math.random() * hand.cards.length);
    const card = hand.cards[idx];
    const boost = card.boostValue ?? 0;
    const next: GameState = {
      ...state,
      handZones: {
        ...state.handZones,
        [opponentId]: { ...hand, cards: hand.cards.filter((_, i) => i !== idx) },
      },
      discardPiles: {
        ...state.discardPiles,
        [opponentId]: [...(state.discardPiles[opponentId] ?? []), card],
      },
    };
    return {
      state: next,
      result: {
        success: true,
        effectId: effect.id,
        targetIds: [opponentId],
        valueApplied: boost,
        message: `Оппонент сбросил «${card.name}» (+${boost})`,
      },
      valueDelta: boost,
    };
  }

  /** Вернуть ЭТУ карту из сброса в руку (если влезает) */
  private applyReturnToHand(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): ApplyOutcome {
    const playerId = context.playerId;
    const pile = state.discardPiles[playerId] ?? [];
    const idx = pile.findIndex((c) => c.id === context.card.id);
    const hand = state.handZones[playerId];
    if (idx === -1 || !hand) {
      return {
        state,
        result: { success: false, effectId: effect.id, targetIds: [], message: 'Карта не в сбросе' },
      };
    }
    if (hand.cards.length >= hand.maxSize) {
      return {
        state,
        result: { success: false, effectId: effect.id, targetIds: [], message: 'Рука полна' },
      };
    }
    const card = pile[idx];
    const next: GameState = {
      ...state,
      discardPiles: {
        ...state.discardPiles,
        [playerId]: pile.filter((_, i) => i !== idx),
      },
      handZones: {
        ...state.handZones,
        [playerId]: {
          ...hand,
          cards: [...hand.cards, { ...card, isVisible: true }],
        },
      },
    };
    return {
      state: next,
      result: {
        success: true,
        effectId: effect.id,
        targetIds: [playerId],
        message: `«${card.name}» возвращена в руку`,
      },
    };
  }

  /** Контекст стороны боя: бойцы/игроки по ролям */
  private combatSideContext(
    card: Card | null,
    combat: CombatContext,
    role: 'attacker' | 'defender',
  ): EffectContext {
    return {
      playerId: role === 'attacker' ? combat.attackerPlayerId : combat.defenderPlayerId,
      card: card as Card,
      fighterId: role === 'attacker' ? combat.attackerFighterId : combat.targetFighterId,
      opposingFighterId: role === 'attacker' ? combat.targetFighterId : combat.attackerFighterId,
      combat,
    };
  }
}
