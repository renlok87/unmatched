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
 * - В manualEffects едет ТОЛЬКО реально неподдержанное (UNSUPPORTED,
 *   CHOOSE_ONE без опций): текст для ручного применения (Game Tester),
 *   warn-лог + метрика. Легитимные pendingEffects (MOVE/PLACE/CHOOSE_ONE/
 *   RETURN_DEFEATED/…) резолвятся мутацией resolvePendingEffect и в
 *   manualEffects НЕ попадают.
 * - CANCEL_EFFECTS: отменённая карта не исполняет ни reveal-, ни during-,
 *   ни after-эффекты; её ПЕЧАТНОЕ значение сохраняется; отменённый атакующий
 *   не отменяет в ответ (его reveal уже не исполняется).
 */

import { Injectable, Logger } from '@nestjs/common';
import { MetricsService } from '../../metrics/metrics.service';
import type { GameState, Card, CombatContext, EffectContext, CombatEffectContinuation, PendingEffect } from '../models';
import { GamePhase } from '../models';
import { applyTerminalState } from '../engine/terminal-state';
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
import { fighterNameMatches } from './fighter-name';
import {
  NO_VALID_TARGETS_MESSAGE,
  pruneHeadPendingsWithoutTargets,
  withSkippedEffect,
} from './pending-targets';

/**
 * Результат выполнения одного эффекта
 */
export interface EffectResult {
  readonly success: boolean;
  readonly effectId: string;
  readonly targetIds: readonly string[];
  readonly valueApplied?: number;
  readonly message?: string;
  /** Эффект требует ручного применения (только UNSUPPORTED-семантика) */
  readonly manual?: boolean;
}

export { fighterNameMatches } from './fighter-name';
export type { CombatContext, EffectContext } from '../models';

/** Результат стадии ON_REVEAL */
export interface RevealResult {
  readonly paused?: boolean;
  readonly state: GameState;
  readonly appliedEffects: readonly EffectResult[];
  readonly manualEffects: readonly string[];
  readonly attackerCardCancelled: boolean;
  readonly defenderCardCancelled: boolean;
}

/** Результат стадии DURING_COMBAT */
export interface CombatCalculation {
  readonly paused?: boolean;
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
  readonly paused?: boolean;
  readonly state: GameState;
  readonly appliedEffects: readonly EffectResult[];
  readonly manualEffects: readonly string[];
}

export interface OnPlayResult {
  readonly state: GameState;
  readonly appliedEffects: readonly EffectResult[];
  readonly manualEffects: readonly string[];
}

export interface CombatStageResumeResult extends RevealResult, CombatCalculation, AfterCombatResult {
  readonly stage: CombatEffectContinuation['stage'];
  readonly paused: boolean;
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

  async executeRevealEffects(
    state: GameState,
    attackerCard: Card | null,
    defenderCard: Card | null,
    combat: CombatContext,
  ): Promise<RevealResult> {
    return this.runCombatQueue(state, this.createCombatQueue(
      'ON_REVEAL', attackerCard, defenderCard, combat,
    ));
  }

  async executeCombatEffects(
    state: GameState,
    attackerCard: Card | null,
    defenderCard: Card | null,
    combat: CombatContext,
    cancelled: { attacker: boolean; defender: boolean } = { attacker: false, defender: false },
  ): Promise<CombatCalculation> {
    return this.metrics.measureServiceDuration('executeCombatEffects', 'CardEffectExecutor', () =>
      this.runCombatQueue(state, this.createCombatQueue(
        'DURING_COMBAT', attackerCard, defenderCard, combat, cancelled,
      )),
    );
  }

  async executeAfterCombatEffects(
    state: GameState,
    attackerCard: Card | null,
    defenderCard: Card | null,
    combat: CombatContext,
    outcome: { attackerWon: boolean; attackerDamage: number; defenderDamage: number },
    cancelled: { attacker: boolean; defender: boolean } = { attacker: false, defender: false },
  ): Promise<AfterCombatResult> {
    return this.runCombatQueue(state, this.createCombatQueue(
      'AFTER_COMBAT', attackerCard, defenderCard, combat, cancelled, outcome,
    ));
  }

  /** Continue only after the action executor has applied/declined the pending choice. */
  async resumeCombatEffects(state: GameState): Promise<CombatStageResumeResult> {
    const continuation = state.metadata.combatEffectContinuation;
    if (!continuation) throw new Error('No combat effect continuation');
    if (state.metadata.pendingEffects?.length) throw new Error('Combat choice is still pending');
    return this.runCombatQueue(state, continuation);
  }

  private createCombatQueue(
    stage: CombatEffectContinuation['stage'],
    attackerCard: Card | null,
    defenderCard: Card | null,
    combat: CombatContext,
    cancelled = { attacker: false, defender: false },
    outcome?: { attackerWon: boolean; attackerDamage: number; defenderDamage: number },
  ): CombatEffectContinuation {
    // Defender first at every timing. Retain card order within each side, except
    // the established numeric modifier precedence during combat.
    const remaining: CombatEffectContinuation['remaining'][number][] = [];
    for (const role of ['defender', 'attacker'] as const) {
      const card = role === 'attacker' ? attackerCard : defenderCard;
      if (!card) continue;
      const isAttacker = role === 'attacker';
      const context: EffectContext = {
        ...this.combatSideContext(card, combat, role),
        ...(outcome ? {
          wonCombat: isAttacker ? outcome.attackerWon : !outcome.attackerWon,
          damageDealt: isAttacker ? outcome.defenderDamage : outcome.attackerDamage,
          damageTaken: isAttacker ? outcome.attackerDamage : outcome.defenderDamage,
        } : {}),
      };
      const effects = (card.effects ?? []).filter(e => e.timing === stage);
      if (stage === 'DURING_COMBAT') {
        const order = (e: CardEffect): number => e.type === EffectType.SET_VALUE ? 0
          : [EffectType.MODIFY_VALUE, EffectType.MODIFY_ATTACK, EffectType.MODIFY_DEFENSE].includes(e.type) ? 1
            : e.type === EffectType.VALUE_PER_COUNT ? 2 : 3;
        effects.sort((a, b) => order(a) - order(b));
      }
      remaining.push(...effects.map(effect => ({ effect, context, isAttacker })));
    }
    return { stage, remaining, attackerCardCancelled: cancelled.attacker,
      defenderCardCancelled: cancelled.defender, finalAttack: combat.attackValue,
      finalDefense: combat.defenseValue, preventDamageToAttacker: false, preventDamageToDefender: false };
  }

  private async runCombatQueue(state: GameState, queue: CombatEffectContinuation): Promise<CombatStageResumeResult> {
    let currentState = applyTerminalState({
      ...state, metadata: { ...state.metadata, combatEffectContinuation: undefined },
    });
    const appliedEffects: EffectResult[] = [];
    const manualEffects: string[] = [];
    let progress = { ...queue, remaining: [] as CombatEffectContinuation['remaining'][number][] };
    let paused = false;
    for (let index = 0; index < queue.remaining.length; index++) {
      if (currentState.phase === GamePhase.GAME_OVER) break;
      const { effect, context, isAttacker } = queue.remaining[index];
      if (isAttacker ? progress.attackerCardCancelled : progress.defenderCardCancelled) continue;
      if (!(await this.passesWhen(currentState, effect, context))) continue;
      const pendingBefore = currentState.metadata.pendingEffects?.length ?? 0;
      const outcome = await this.applyOneEffect(currentState, effect, context);
      currentState = applyTerminalState(outcome.state);
      appliedEffects.push(outcome.result);
      if (outcome.manual) manualEffects.push(outcome.manual);
      progress = { ...this.updateCombatProgress(progress, outcome, isAttacker), remaining: progress.remaining };
      if (currentState.phase !== GamePhase.GAME_OVER &&
          (currentState.metadata.pendingEffects?.length ?? 0) > pendingBefore) {
        // Even an empty remainder pauses: the choice precedes the next combat stage.
        progress = { ...progress, remaining: queue.remaining.slice(index + 1) };
        currentState = { ...currentState, metadata: {
          ...currentState.metadata, combatEffectContinuation: progress,
        } };
        paused = true;
        break;
      }
    }
    return { ...progress, state: currentState, appliedEffects, manualEffects, paused };
  }

  private updateCombatProgress(
    queue: CombatEffectContinuation, outcome: ApplyOutcome, isAttacker: boolean,
  ): CombatEffectContinuation {
    const next = { ...queue };
    if (outcome.cancelOpposingCard) {
      if (isAttacker) next.defenderCardCancelled = true;
      else next.attackerCardCancelled = true;
    }
    if (queue.stage === 'DURING_COMBAT') {
      const field = isAttacker ? 'finalAttack' : 'finalDefense';
      if (outcome.setValue !== undefined) next[field] = outcome.setValue;
      if (outcome.valueDelta) next[field] += outcome.valueDelta;
      if (outcome.preventDamage) {
        if (isAttacker) next.preventDamageToAttacker = true;
        else next.preventDamageToDefender = true;
      }
    }
    return next;
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

    let currentState = applyTerminalState(state);
    const appliedEffects: EffectResult[] = [];
    const manualEffects: string[] = [];
    const fighter = currentState.fighters.find((f) => f.ownerId === playerId && !f.isDefeated);

    for (const effect of onPlayEffects) {
      if (currentState.phase === GamePhase.GAME_OVER) break;
      const context: EffectContext = { playerId, card, fighterId: fighter?.id };
      if (!(await this.passesWhen(currentState, effect, context))) continue;
      const outcome = await this.applyOneEffect(currentState, effect, context);
      currentState = applyTerminalState(outcome.state);
      appliedEffects.push(outcome.result);
      if (outcome.manual) manualEffects.push(outcome.manual);
    }

    return { state: currentState, appliedEffects, manualEffects };
  }

  // =========================================================================
  // CHOOSE_ONE: исполнение эффектов выбранной игроком опции (вне боя)
  // =========================================================================

  /**
   * Применяет эффекты ОДНОЙ выбранной опции CHOOSE_ONE (резолв
   * resolvePendingEffect). Combat choices preserve their original participants,
   * cancellation and numeric flags. Nested choices pause the remaining effects.
   */
  async executeChosenEffects(
    state: GameState,
    effects: readonly CardEffect[],
    playerId: string,
    card?: Card,
    contextOverride?: EffectContext,
  ): Promise<OnPlayResult> {
    let currentState = applyTerminalState(state);
    const appliedEffects: EffectResult[] = [];
    const manualEffects: string[] = [];
    const fighter = currentState.fighters.find((f) => f.ownerId === playerId && !f.isDefeated);
    const ctxCard = card ?? ({ id: 'choose-one', effects: [] } as unknown as Card);

    for (let index = 0; index < effects.length; index++) {
      const effect = effects[index];
      if (currentState.phase === GamePhase.GAME_OVER) break;
      const context: EffectContext = contextOverride ?? { playerId, card: ctxCard, fighterId: fighter?.id };
      if (!(await this.passesWhen(currentState, effect, context))) continue;
      const pendingBefore = currentState.metadata.pendingEffects?.length ?? 0;
      const outcome = await this.applyOneEffect(currentState, effect, context);
      currentState = applyTerminalState(outcome.state);
      appliedEffects.push(outcome.result);
      if (outcome.manual) manualEffects.push(outcome.manual);
      const continuation = currentState.metadata.combatEffectContinuation;
      if (continuation && context.combat && currentState.phase !== GamePhase.GAME_OVER) {
        const isAttacker = context.playerId === context.combat.attackerPlayerId;
        let progress = this.updateCombatProgress(continuation, outcome, isAttacker);
        const paused = (currentState.metadata.pendingEffects?.length ?? 0) > pendingBefore;
        if (paused) progress = { ...progress, remaining: [
          ...effects.slice(index + 1).map(effect => ({ effect, context, isAttacker })),
          ...progress.remaining,
        ] };
        currentState = { ...currentState, metadata: { ...currentState.metadata, combatEffectContinuation: progress } };
        if (paused) break;
      }
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

    let currentState = applyTerminalState(state);
    for (const card of handZone.cards) {
      if (currentState.phase === GamePhase.GAME_OVER) break;
      const effects = (card.effects ?? []).filter((e) => e.timing === timing);
      for (const effect of effects) {
        if (currentState.phase === GamePhase.GAME_OVER) break;
        const context: EffectContext = { playerId, card };
        if (!(await this.passesWhen(currentState, effect, context))) continue;
        const outcome = await this.applyOneEffect(currentState, effect, context);
        currentState = applyTerminalState(outcome.state);
      }
    }
    return currentState;
  }

  // =========================================================================
  // Применение одного эффекта (единая точка)
  // =========================================================================

  /**
   * DE-016 (D-DE-11): a choice this effect opens on an EMPTY queue becomes its
   * head at once — if it has no legal target it is dropped here with a
   * SkippedEffect note, so nothing waits for input. On an open queue the new
   * choice is checked when it reaches the head (pruneHeadPendingsWithoutTargets
   * from the drain after every resolve/decline).
   */
  private async applyOneEffect(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): Promise<ApplyOutcome> {
    const outcome = await this.applyOneEffectRaw(state, effect, context);
    if ((state.metadata.pendingEffects?.length ?? 0) > 0) return outcome;
    const pruned = pruneHeadPendingsWithoutTargets(outcome.state, this.adjacencyService);
    if (pruned === outcome.state) return outcome;
    const kept = pruned.metadata.pendingEffects?.length ?? 0;
    return {
      ...outcome,
      state: pruned,
      result: kept > 0
        ? outcome.result
        : { success: false, effectId: effect.id, targetIds: [], message: NO_VALID_TARGETS_MESSAGE },
    };
  }

  private async applyOneEffectRaw(
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
    // DE-016: an automatic effect without targets is skipped with a note too
    // (the client explains it with why.effect.no.targets).
    const noTargets = (): ApplyOutcome => ({
      state: withSkippedEffect(state, {
        playerId: context.playerId, effectId: effect.id, kind: effect.type, text: effect.text,
      }),
      result: { success: false, effectId: effect.id, targetIds: [], message: NO_VALID_TARGETS_MESSAGE },
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
        // Авто-источники: блинд-буст и random-буст оппонента
        if (effect.boostSource === 'SELF_DECK_TOP') {
          return this.applyDeckTopBoost(state, effect, context);
        }
        if (effect.boostSource === 'OPPONENT_RANDOM_HAND') {
          return this.applyOpponentRandomBoost(state, effect, context);
        }
        // PLAYER_CHOICE_HAND («You may BOOST this attack/defense», Second Shot /
        // Noble Sacrifice): карта НЕ коммитится при объявлении — выбор
        // происходит ЗДЕСЬ, на стадии DURING_COMBAT после reveal и отмены
        // Feint (rulebook Battle of Legends Vol.1, p.12-13). Пауза боевой
        // цепочки через pendingEffects; резолв — resolvePendingEffect(cardIds).
        if (!context.combat) {
          return { state, result: ok({ message: 'BOOST вне боя не поддерживается' }) };
        }
        const hand = state.handZones[context.playerId]?.cards ?? [];
        if (hand.length === 0) {
          // «You may …» — пустая рука = легальный no-op, выбора нет
          return { state, result: ok({ message: 'Рука пуста — BOOST недоступен' }) };
        }
        const pending: PendingEffect = {
          id: `${effect.id}-boost-${state.sequenceNumber}`,
          type: 'BOOST_CHOICE',
          playerId: context.playerId,
          optional: true,
          text: effect.text ?? 'You may BOOST this attack',
        };
        const next: GameState = {
          ...state,
          metadata: {
            ...state.metadata,
            pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
          },
        };
        return {
          state: next,
          result: ok({ targetIds: [context.playerId], message: 'Ожидает выбора BOOST-карты (после reveal)' }),
        };
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
        // «any one fighter in X's zone» (A Momentary Glance): цель выбирает
        // владелец из ВСЕХ живых бойцов зоны X (свои и враги) — TARGET_FIGHTER.
        if (effect.target === EffectTarget.ANY_FIGHTER_IN_ZONE) {
          const zoneTargets = this.fightersInZoneOf(state, effect.fighterName ?? '');
          if (zoneTargets.length === 0) {
            return noTargets();
          }
          const pending = {
            id: `${effect.id}-p${state.metadata.pendingEffects?.length ?? 0}`,
            type: 'TARGET_FIGHTER' as const,
            playerId: context.playerId,
            targetFighterIds: zoneTargets,
            damage: value,
            text: effect.text ?? `Deal ${value} damage to any one fighter in ${effect.fighterName}'s zone`,
          };
          const next: GameState = {
            ...state,
            metadata: {
              ...state.metadata,
              pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
            },
          };
          return {
            state: next,
            result: ok({ targetIds: zoneTargets, message: `Ожидает выбора цели: ${pending.text}` }),
          };
        }
        const targets = await this.resolveTargets(state, effect, context);
        if (targets.length === 0) {
          return noTargets();
        }
        let next = state;
        for (const t of targets) next = this.applyDamage(next, t, value);
        return { state: next, result: ok({ targetIds: targets, valueApplied: value }) };
      }

      case EffectType.HEAL: {
        const targets = await this.resolveTargets(state, effect, context);
        if (targets.length === 0) {
          return noTargets();
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
        // Печатный текст без слова «random» («Your opponent discards 1 card.»):
        // сбрасывающий ОППОНЕНТ выбирает карту сам (правила Unmatched — выбор
        // карт всегда за владельцем руки, если явно не сказано «random»).
        // Карты с «random» парсятся в BOOST/OPPONENT_RANDOM_HAND, сюда не попадают.
        const count = value || 1;
        const hand = state.handZones[opponentId]?.cards ?? [];
        if (hand.length === 0) {
          // Пустая рука — легальный no-op (сбрасывать нечего)
          return {
            state,
            result: ok({ targetIds: [opponentId], valueApplied: 0, message: 'У оппонента пустая рука — сброс не выполняется' }),
          };
        }
        const pending: PendingEffect = {
          id: `discard-choice-${effect.id}-${state.sequenceNumber}`,
          type: 'DISCARD_CARDS',
          playerId: opponentId,
          value: count,
          text: effect.text,
        };
        const next: GameState = {
          ...state,
          metadata: {
            ...state.metadata,
            pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
          },
        };
        // Рост pendingEffects в runCombatQueue/executeChosenEffects паузит
        // боевую цепочку (combatEffectContinuation); резолв выбора продолжит
        // её через drainAfterChoice → resumeCombatEffects.
        return {
          state: next,
          result: ok({ targetIds: [opponentId], valueApplied: count, message: `Оппонент выбирает ${count} карт(у) для сброса` }),
        };
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

      // --- CHOOSE_ONE: «Choose one: …» → pendingEffect с вариантами;
      //     резолвится resolvePendingEffect(optionIndex) → executeChosenEffects ---
      case EffectType.CHOOSE_ONE: {
        const options = effect.options ?? [];
        const text = effect.text ?? 'Choose one';
        if (options.length === 0) {
          // нет распознанных опций — в manualEffects (как UNSUPPORTED)
          return {
            state,
            result: { success: false, effectId: effect.id, targetIds: [], manual: true, message: text },
            manual: text,
          };
        }
        const pending = {
          id: `${effect.id}-p${state.metadata.pendingEffects?.length ?? 0}`,
          type: 'CHOOSE_ONE' as const,
          playerId: context.playerId,
          chooseCount: effect.chooseCount ?? 1,
          options: options.map((o, i) => ({ index: i, label: o.label })),
          optionEffects: options.map((o) => o.effects),
          card: context.card,
          effectContext: context.combat ? context : undefined,
          optional: effect.optional,
          text,
        };
        const next: GameState = {
          ...state,
          metadata: {
            ...state.metadata,
            pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
          },
        };
        // Легитимный pending (резолв optionIndex → executeChosenEffects) —
        // НЕ manual: аудит manualEffects только для неподдержанного.
        return {
          state: next,
          result: ok({ message: `Ожидает выбора: ${text}` }),
        };
      }

      // --- требуют выбора игрока → metadata.pendingEffects (C2):
      // резолвятся мутацией resolvePendingEffect, протухают в advanceTurn ---
      case EffectType.MOVE:
      case EffectType.PLACE: {
        const fighterIds = await this.resolveTargets(state, effect, context);
        // A defeated combatant cannot move or provide an old board position.
        // PLACE may explicitly return a defeated sidekick, so keep its own flow.
        if (effect.type === EffectType.MOVE && fighterIds.length === 0) {
          return noTargets();
        }
        const text = effect.text ?? `${effect.type} ${value || ''}`.trim();

        // «Move each of your fighters…» / «Move each Harpy…»: EACH — отдельное
        // решение на каждого живого бойца, строго последовательно (голова
        // очереди). Нулевой шаг легален — очередь не strand'ится.
        // S06 (GD-022, Command the Storms): EACH_FIGHTER — все живые бойцы
        // ОБЕИХ сторон; владелец эффекта двигает и чужих (targetsOpponent по
        // фактическому владельцу бойца; «up to» → optional, 0 шагов легален).
        const isEach =
          effect.type === EffectType.MOVE &&
          (effect.target === EffectTarget.EACH_OWN_FIGHTER ||
            effect.target === EffectTarget.EACH_FIGHTER ||
            (effect.target === EffectTarget.NAMED_FIGHTER && Boolean(effect.fighterName)));
        if (isEach && fighterIds.length > 0) {
          const pendings = fighterIds.map((fid, i) => {
            const fighter = state.fighters.find((f) => f.id === fid);
            return {
              id: `${effect.id}-p${(state.metadata.pendingEffects?.length ?? 0) + i}`,
              type: 'MOVE' as const,
              playerId: context.playerId,
              fighterIds: [fid],
              value: value || undefined,
              fighterName: effect.target === EffectTarget.NAMED_FIGHTER ? effect.fighterName : undefined,
              targetsOpponent: fighter ? fighter.ownerId !== context.playerId : false,
              optional: effect.target === EffectTarget.EACH_FIGHTER ? true : effect.optional,
              canPassThroughEnemies: effect.canPassThroughEnemies === true,
              text,
            };
          });
          const next: GameState = {
            ...state,
            metadata: {
              ...state.metadata,
              pendingEffects: [...(state.metadata.pendingEffects ?? []), ...pendings],
            },
          };
          return {
            state: next,
            result: ok({ targetIds: fighterIds, message: `Ожидает выбора: ${text} (×${pendings.length})` }),
          };
        }

        // Skirmish (GD-023): «choose one of the fighters in the combat» —
        // ОДИН pending с выбором ЛЮБОГО живого участника боя (anyOwner).
        if (effect.type === EffectType.MOVE && effect.target === EffectTarget.COMBAT_FIGHTER) {
          const participants = context.combat
            ? [context.combat.attackerFighterId, context.combat.targetFighterId]
            : [];
          const living = participants.filter((id) =>
            state.fighters.some((f) => f.id === id && !f.isDefeated && f.health > 0),
          );
          if (living.length === 0) {
            return { state, result: { success: false, effectId: effect.id, targetIds: [], message: 'Нет живых участников боя' } };
          }
          const pending = {
            id: `${effect.id}-p${(state.metadata.pendingEffects?.length ?? 0)}`,
            type: 'MOVE' as const,
            playerId: context.playerId,
            fighterIds: living,
            value: value || undefined,
            anyOwner: true,
            optional: effect.optional,
            text,
          };
          const next: GameState = {
            ...state,
            metadata: {
              ...state.metadata,
              pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
            },
          };
          return {
            state: next,
            result: ok({ targetIds: living, message: `Ожидает выбора: ${text}` }),
          };
        }

        const pending = {
          id: `${effect.id}-p${(state.metadata.pendingEffects?.length ?? 0)}`,
          type: effect.type === EffectType.MOVE ? ('MOVE' as const) : ('PLACE' as const),
          playerId: context.playerId,
          fighterIds: context.combat && fighterIds.length ? fighterIds : undefined,
          value: value || undefined,
          fighterName: effect.fighterName,
          targetsOpponent: effect.target === EffectTarget.OPPOSING_FIGHTER,
          optional: effect.optional,
          canPassThroughEnemies: effect.canPassThroughEnemies === true,
          text,
        };
        const next: GameState = {
          ...state,
          metadata: {
            ...state.metadata,
            pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
          },
        };
        // Легитимный pending (резолв fighterId+x+y) — НЕ manual.
        return {
          state: next,
          result: ok({ message: `Ожидает выбора: ${text}` }),
        };
      }

      // «Then, return a defeated Harpy (if any) to any space in Medusa's zone»
      // (Winged Frenzy): побеждённые бойцы владельца с этим именем; есть —
      // optional PLACE-pending (revive, full health, зона named-бойца), нет —
      // skip («if any»).
      case EffectType.RETURN_DEFEATED: {
        const candidates = state.fighters.filter(
          (f) =>
            f.ownerId === context.playerId &&
            f.isDefeated === true &&
            this.nameMatches(f.name, effect.fighterName ?? ''),
        );
        if (candidates.length === 0) {
          return { state, result: ok({ message: 'Нет поверженных бойцов для возврата' }) };
        }
        const text = effect.text ?? `Return a defeated ${effect.fighterName}`;
        const pending = {
          id: `${effect.id}-p${(state.metadata.pendingEffects?.length ?? 0)}`,
          type: 'PLACE' as const,
          playerId: context.playerId,
          fighterIds: candidates.map((f) => f.id),
          zoneFighterName: effect.zoneFighterName,
          restoreFullHealth: true,
          optional: true,
          text,
        };
        const next: GameState = {
          ...state,
          metadata: {
            ...state.metadata,
            pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
          },
        };
        // Легитимный optional revive-pending (резолв/decline как PLACE) — НЕ manual.
        return {
          state: next,
          result: ok({ message: `Ожидает выбора: ${text}` }),
        };
      }

      // The Lady of the Lake (GD-021): «Search your deck and discard pile for
      // the EXCALIBUR card. Add it to your hand. If you searched your deck,
      // shuffle it.» — выбора игрока НЕТ: авто-поиск в СВОИХ зонах. Колода
      // просматривается всегда → всегда shuffle (порядок после — неизвестен
      // даже владельцу). Excalibur единственна (count 1); детерминированный
      // порядок зон: discard, затем drawPile.
      case EffectType.SEARCH_ADD_TO_HAND: {
        const want = effect.searchCardName ?? '';
        if (!want) {
          return { state, result: { success: false, effectId: effect.id, targetIds: [], message: 'Не задано имя искомой карты' } };
        }
        const playerId = context.playerId;
        const hand = state.handZones[playerId];
        const deck = state.decks[playerId];
        if (!hand || !deck) {
          return { state, result: { success: false, effectId: effect.id, targetIds: [], message: 'Нет колоды/руки у владельца' } };
        }
        // Печатный текст капсит имя («the EXCALIBUR card») — сравнение
        // регистронезависимо, иначе карта «Excalibur» не находится.
        const matches = (c: Card): boolean =>
          (c.nameEn ?? c.name).toUpperCase() === want.toUpperCase() ||
          c.name.toUpperCase() === want.toUpperCase();
        const pile = state.discardPiles[playerId] ?? [];
        const inDiscardIdx = pile.findIndex(matches);
        let next: GameState = state;
        let foundIn: 'discard' | 'drawPile' | null = null;
        if (inDiscardIdx !== -1) {
          const card = pile[inDiscardIdx];
          next = {
            ...next,
            discardPiles: {
              ...next.discardPiles,
              [playerId]: pile.filter((_, i) => i !== inDiscardIdx),
            },
            handZones: {
              ...next.handZones,
              [playerId]: { ...hand, cards: [...hand.cards, { ...card, isVisible: true }] },
            },
          };
          foundIn = 'discard';
        } else {
          const drawIdx = deck.drawPile.findIndex(matches);
          if (drawIdx !== -1) {
            const card = deck.drawPile[drawIdx];
            const remaining = deck.drawPile.filter((_, i) => i !== drawIdx);
            next = {
              ...next,
              decks: { ...next.decks, [playerId]: { ...deck, drawPile: remaining, topCard: remaining[0] } },
              handZones: {
                ...next.handZones,
                [playerId]: { ...hand, cards: [...hand.cards, { ...card, isVisible: true }] },
              },
            };
            foundIn = 'drawPile';
          }
        }
        // Deck searched → shuffle it (order unknown to everyone afterwards).
        const shuffled = this.shuffleDrawPile(next.decks[playerId].drawPile);
        next = {
          ...next,
          decks: {
            ...next.decks,
            [playerId]: { ...next.decks[playerId], drawPile: shuffled, topCard: shuffled[0] },
          },
        };
        const message = foundIn
          ? `«${want}» найдена в ${foundIn === 'discard' ? 'сбросе' : 'колоде'} и добавлена в руку; колода перемешана`
          : `«${want}» не найдена (колода/сброс); колода перемешана`;
        return { state: next, result: ok({ targetIds: [playerId], message }) };
      }

      // Prophecy (GD-021): «Look at the top 4 cards… Add 2… other 2 back on
      // top, in any order.» — снимаем верхние min(view, pile) карт в pending
      // (атомарно: колода уже без них), выбор 2 + порядок возврата — владелец.
      // Малый остаток: берём что есть; pickCount = min(pick, revealed).
      case EffectType.DECK_TOP_PICK: {
        const playerId = context.playerId;
        const hand = state.handZones[playerId];
        const deck = state.decks[playerId];
        if (!hand || !deck) {
          return { state, result: { success: false, effectId: effect.id, targetIds: [], message: 'Нет колоды/руки у владельца' } };
        }
        const view = Math.min(effect.viewCount ?? 4, deck.drawPile.length);
        if (view === 0) {
          // Колода пуста: смотреть нечего. Это НЕ требуемый добор — истощение
          // не применяется (R-04 касается required draws).
          return { state, result: ok({ targetIds: [playerId], valueApplied: 0, message: 'Колода пуста — смотреть нечего' }) };
        }
        const revealed = deck.drawPile.slice(0, view);
        const restPile = deck.drawPile.slice(view);
        const pending: PendingEffect = {
          id: `${effect.id}-p${state.metadata.pendingEffects?.length ?? 0}`,
          type: 'DECK_TOP_PICK',
          mode: 'PICK',
          playerId,
          value: Math.min(effect.pickCount ?? 2, view),
          revealedCards: revealed,
          text: effect.text ?? `Look at the top ${view} cards of your deck`,
        };
        const next: GameState = {
          ...state,
          decks: { ...state.decks, [playerId]: { ...deck, drawPile: restPile, topCard: restPile[0] } },
          metadata: {
            ...state.metadata,
            pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
          },
        };
        return {
          state: next,
          result: ok({ targetIds: [playerId], message: `Ожидает выбора ${pending.value} из ${view} карт` }),
        };
      }

      // Restless Spirits (GD-022): двухстадийный выбор клетки — pending
      // CHOOSE_SPACE; урон/добор применяются на резолве stage 2 (executor).
      case EffectType.ZONE_AREA_DAMAGE: {
        const anchor = state.fighters.find((f) =>
          this.nameMatches(f.name, effect.zoneFighterName ?? ''),
        );
        if (!anchor) {
          return { state, result: { success: false, effectId: effect.id, targetIds: [], message: `Боец «${effect.zoneFighterName}» не на доске — зона не определена` } };
        }
        const pending: PendingEffect = {
          id: `${effect.id}-p${state.metadata.pendingEffects?.length ?? 0}`,
          type: 'CHOOSE_SPACE',
          stage: 1,
          playerId: context.playerId,
          zoneFighterName: effect.zoneFighterName,
          damage: value,
          drawIfDefeated: effect.drawIfDefeated,
          text: effect.text ?? `Choose any space in ${effect.zoneFighterName}'s zone`,
        };
        const next: GameState = {
          ...state,
          metadata: {
            ...state.metadata,
            pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
          },
        };
        return { state: next, result: ok({ targetIds: [context.playerId], message: `Ожидает выбора: ${pending.text}` }) };
      }

      // The Holy Grail (GD-022): «If King Arthur has 4 or less health but is
      // not defeated, set his health to 8.» — УСТАНОВКА, не heal: hp <= 4 →
      // ровно 8; выше порога/повержён — без изменений.
      case EffectType.SET_HEALTH: {
        const target = state.fighters.find((f) =>
          this.nameMatches(f.name, effect.fighterName ?? ''),
        );
        if (!target) {
          return { state, result: { success: false, effectId: effect.id, targetIds: [], message: `Боец «${effect.fighterName}» не найден` } };
        }
        const threshold = effect.threshold ?? 0;
        if (target.isDefeated || target.health <= 0) {
          return { state, result: ok({ targetIds: [target.id], message: `«${target.name}» повержён — здоровье не устанавливается` }) };
        }
        if (target.health > threshold) {
          return { state, result: ok({ targetIds: [target.id], valueApplied: 0, message: `HP ${target.health} > ${threshold} — без изменений` }) };
        }
        const next: GameState = {
          ...state,
          fighters: state.fighters.map((f) =>
            f.id === target.id ? { ...f, health: value } : f,
          ),
        };
        return { state: next, result: ok({ targetIds: [target.id], valueApplied: value, message: `HP установлен: ${value}` }) };
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
        const self = state.fighters.find((f) => f.id === context.fighterId && !f.isDefeated && f.health > 0);
        const opp = state.fighters.find((f) => f.id === context.opposingFighterId && !f.isDefeated && f.health > 0);
        if (!self || !opp) return when.kind === 'NOT_ADJACENT_TO_OPPONENT';
        const adjacent = await this.adjacencyService.isAdjacent(
          state,
          self.position,
          opp.position,
        );
        return when.kind === 'ADJACENT_TO_OPPONENT' ? adjacent : !adjacent;
      }
      case 'SHARES_ZONE_WITH_OPPONENT':
      case 'NOT_SHARES_ZONE_WITH_OPPONENT': {
        // мультизонность (C1): пересечение зон клеток (Ms. Marvel
        // «shares no zones with the opposing fighter»)
        const self = state.fighters.find((f) => f.id === context.fighterId && !f.isDefeated && f.health > 0);
        const opp = state.fighters.find((f) => f.id === context.opposingFighterId && !f.isDefeated && f.health > 0);
        if (!self || !opp) return when.kind === 'NOT_SHARES_ZONE_WITH_OPPONENT';
        const shares = this.adjacencyService.isInSameZone(state, self.position, opp.position);
        return when.kind === 'SHARES_ZONE_WITH_OPPONENT' ? shares : !shares;
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
        const opp = state.fighters.find((f) => f.id === context.opposingFighterId && !f.isDefeated && f.health > 0);
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
        const opp = state.fighters.find((f) => f.id === context.opposingFighterId && !f.isDefeated && f.health > 0);
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
    const liveTarget = (id?: string): string[] =>
      state.fighters.some((f) => f.id === id && !f.isDefeated && f.health > 0) ? [id!] : [];

    switch (target) {
      case EffectTarget.SELF: {
        if (context.fighterId) return liveTarget(context.fighterId);
        const fighter = state.fighters.find(
          (f) => f.ownerId === context.playerId && !f.isDefeated && f.health > 0,
        );
        return fighter ? [fighter.id] : [];
      }

      case EffectTarget.OPPOSING_FIGHTER:
        return liveTarget(context.opposingFighterId);

      case EffectTarget.ATTACKER:
        return liveTarget(context.combat?.attackerFighterId);

      case EffectTarget.DEFENDER:
        return liveTarget(context.combat?.targetFighterId);

      case EffectTarget.ALL_ENEMIES:
        return state.fighters
          .filter((f) => f.ownerId !== context.playerId && !f.isDefeated && f.health > 0)
          .map((f) => f.id);

      case EffectTarget.ALL_ALLIES:
        return state.fighters
          .filter((f) => f.ownerId === context.playerId && !f.isDefeated && f.health > 0)
          .map((f) => f.id);

      case EffectTarget.ENEMIES_ADJACENT_TO_SELF: {
        const self = state.fighters.find((f) => f.id === context.fighterId && !f.isDefeated && f.health > 0);
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
                !f.isDefeated && f.health > 0 &&
                this.nameMatches(f.name, effect.fighterName!),
            )
          : state.fighters.find((f) => f.id === context.fighterId && !f.isDefeated && f.health > 0);
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

      case EffectTarget.EACH_OWN_FIGHTER: {
        return state.fighters
          .filter((f) => f.ownerId === context.playerId && !f.isDefeated && f.health > 0)
          .map((f) => f.id);
      }

      // Command the Storms (GD-022): ВСЕ живые бойцы, обе стороны
      case EffectTarget.EACH_FIGHTER: {
        return state.fighters
          .filter((f) => !f.isDefeated && f.health > 0)
          .map((f) => f.id);
      }

      // Skirmish (GD-023): живые участники текущего боя
      case EffectTarget.COMBAT_FIGHTER: {
        if (!context.combat) return [];
        return [context.combat.attackerFighterId, context.combat.targetFighterId]
          .filter((id) => state.fighters.some((f) => f.id === id && !f.isDefeated && f.health > 0));
      }

      case EffectTarget.OPPONENT_PLAYER: {
        const opp = this.opponentPlayerId(state, context);
        return opp ? [opp] : [];
      }

      default:
        return [];
    }
  }

  /** «Harpy 2» матчит «Harpy»; «Harpies» матчит «Harpy» (мн. число); регистронезависимо */
  private nameMatches(fighterName: string, effectName: string): boolean {
    return fighterNameMatches(fighterName, effectName);
  }

  /**
   * Живые бойцы в зоне бойца с именем fighterName (пересечение зон клеток).
   * Якорь-боец ищется по имени независимо от isDefeated — «Medusa's zone»
   * остаётся определённой, пока Медуза стоит на доске. Нет якоря → пусто.
   */
  private fightersInZoneOf(state: GameState, fighterName: string): string[] {
    const anchor = state.fighters.find((f) => this.nameMatches(f.name, fighterName));
    if (!anchor) return [];
    return state.fighters
      .filter((f) => !f.isDefeated && f.health > 0)
      .filter((f) => this.adjacencyService.isInSameZone(state, anchor.position, f.position))
      .map((f) => f.id);
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

  /** Fisher-Yates (тот же алгоритм, что DeckManagementService.shuffle) */
  private shuffleDrawPile<T>(pile: readonly T[]): T[] {
    const result = [...pile];
    for (let i = result.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [result[i], result[j]] = [result[j], result[i]];
    }
    return result;
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

  /** Вернуть ЭТУ карту из сброса в руку; лимит руки проверяется в конце хода. */
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
