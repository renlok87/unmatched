/**
 * Card Effect Executor Service
 *
 * Выполняет эффекты карт в нужные моменты времени.
 * Обрабатывает ON_PLAY, DURING_COMBAT, AFTER_COMBAT, TURN_START, TURN_END.
 */

import { Injectable, Logger } from '@nestjs/common';
import { MetricsService } from '../../metrics/metrics.service';
import type { GameState, Fighter, Card } from '../models';
import {
  CardEffect,
  EffectTiming,
  EffectType,
  EffectTarget,
} from '../models/card.model';
import { ValueModifierService } from '../engine/value-modifier.service';

/**
 * Результат выполнения эффекта
 */
export interface EffectResult {
  readonly success: boolean;
  readonly effectId: string;
  readonly targetIds: readonly string[];
  readonly valueApplied?: number;
  readonly message?: string;
}

/**
 * Контекст выполнения эффекта
 */
export interface EffectContext {
  readonly playerId: string;
  readonly card: Card;
  readonly fighterId?: string;
  readonly targetFighterId?: string;
  readonly combat?: CombatContext;
}

/**
 * Контекст боя
 */
export interface CombatContext {
  readonly attackerId: string;
  readonly defenderId: string;
  readonly attackCardId: string;
  readonly defenseCardId?: string;
  readonly attackValue: number;
  readonly defenseValue: number;
}

/**
 * Результат вычисления боя
 */
export interface CombatCalculation {
  readonly finalAttack: number;
  readonly finalDefense: number;
  readonly attackerDamage: number;
  readonly defenderDamage: number;
  readonly appliedEffects: readonly EffectResult[];
}

/**
 * Результат после боя
 */
export interface AfterCombatResult {
  readonly state: GameState;
  readonly appliedEffects: readonly EffectResult[];
}

/**
 * Результат выполнения эффектов при розыгрыше
 */
export interface OnPlayResult {
  readonly state: GameState;
  readonly appliedEffects: readonly EffectResult[];
}

@Injectable()
export class CardEffectExecutorService {
  private readonly logger = new Logger(CardEffectExecutorService.name);

  constructor(
    private readonly valueModifierService: ValueModifierService,
    private readonly metrics: MetricsService,
  ) {}

  /**
   * Выполнить эффект карты
   */
  async executeEffect(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): Promise<EffectResult> {
    return this.metrics.measureCardEffect(
      effect.type,
      effect.timing,
      async () => {
        // 1. Проверяем тайминг (оптимизированная проверка)
        if (!this.isTimingValid(state, effect.timing)) {
          this.logger.debug(
            `Effect timing invalid: ${effect.timing} for phase ${state.phase}`,
            { effectId: effect.id, timing: effect.timing, phase: state.phase },
          );
          return {
            success: false,
            effectId: effect.id,
            targetIds: [],
            message: `Invalid timing: ${effect.timing} for phase ${state.phase}`,
          };
        }

        // 2. Проверяем условие если есть
        if (effect.condition && !this.evaluateCondition(state, effect.condition, context)) {
          this.logger.debug(`Effect condition not met`, { effectId: effect.id, condition: effect.condition });
          return {
            success: false,
            effectId: effect.id,
            targetIds: [],
            message: 'Condition not met',
          };
        }

        // 3. Определяем цели (оптимизированное разрешение)
        const targets = this.resolveTargets(state, effect, context);
        if (targets.length === 0) {
          this.logger.debug(`No valid targets for effect`, { effectId: effect.id, effectType: effect.type });
          return {
            success: false,
            effectId: effect.id,
            targetIds: [],
            message: 'No valid targets',
          };
        }

        // 4. Выполняем эффект
        return this.applyEffect(state, effect, targets, context);
      },
    );
  }

  /**
   * Выполнить все эффекты ON_PLAY для карты
   */
  async executeOnPlayEffects(
    state: GameState,
    card: Card,
    playerId: string,
  ): Promise<OnPlayResult> {
    const onPlayEffects = (card.effects ?? []).filter(
      (e) => e.timing === EffectTiming.ON_PLAY,
    );

    let currentState = state;
    const appliedEffects: EffectResult[] = [];

    for (const effect of onPlayEffects) {
      const context: EffectContext = {
        playerId,
        card,
      };

      const result = await this.executeEffect(currentState, effect, context);
      appliedEffects.push(result);

      if (result.success) {
        // Обновляем состояние на основе результата
        currentState = this.updateStateAfterEffect(currentState, effect, result);
      }
    }

    return {
      state: currentState,
      appliedEffects,
    };
  }

  /**
   * Выполнить эффекты DURING_COMBAT и вычислить итоговые значения
   */
  async executeCombatEffects(
    state: GameState,
    attackerCard: Card,
    defenderCard: Card | null,
    combat: CombatContext,
  ): Promise<CombatCalculation> {
    return this.metrics.measureServiceDuration('executeCombatEffects', 'CardEffectExecutor', async () => {
      let attackValue = combat.attackValue;
      let defenseValue = combat.defenseValue;
      const appliedEffects: EffectResult[] = [];

      // Эффекты атакующей карты
      const attackerCombatEffects = (attackerCard.effects ?? []).filter(
        (e) => e.timing === EffectTiming.DURING_COMBAT,
      );

      // Выполняем эффекты атакующего параллельно если возможно
      const attackerResults = await Promise.all(
        attackerCombatEffects.map(async (effect) => {
          const context: EffectContext = {
            playerId: combat.attackerId,
            card: attackerCard,
            fighterId: combat.attackerId,
            targetFighterId: combat.defenderId,
            combat,
          };
          return this.executeEffect(state, effect, context);
        }),
      );

      for (const result of attackerResults) {
        appliedEffects.push(result);
        if (result.success && result.valueApplied !== undefined) {
          const effect = attackerCombatEffects[attackerResults.indexOf(result)];
          if (effect.type === EffectType.MODIFY_ATTACK) {
            attackValue += result.valueApplied;
          }
        }
      }

      // Эффекты защищающейся карты
      if (defenderCard) {
        const defenderCombatEffects = defenderCard.effects.filter(
          (e) => e.timing === EffectTiming.DURING_COMBAT,
        );

        const defenderResults = await Promise.all(
          defenderCombatEffects.map(async (effect) => {
            const context: EffectContext = {
              playerId: combat.defenderId,
              card: defenderCard,
              fighterId: combat.defenderId,
              targetFighterId: combat.attackerId,
              combat,
            };
            return this.executeEffect(state, effect, context);
          }),
        );

        for (const result of defenderResults) {
          appliedEffects.push(result);
          if (result.success && result.valueApplied !== undefined) {
            const effect = defenderCombatEffects[defenderResults.indexOf(result)];
            if (effect.type === EffectType.MODIFY_DEFENSE) {
              defenseValue += result.valueApplied;
            }
          }
        }
      }

      // Вычисляем урон
      let attackerDamage = 0;
      let defenderDamage = 0;

      if (attackValue > defenseValue) {
        defenderDamage = attackValue - defenseValue;
      } else if (defenseValue > attackValue) {
        attackerDamage = defenseValue - attackValue;
      }

      this.logger.debug(
        `Combat calculation: ATK ${attackValue} vs DEF ${defenseValue} -> ` +
          `Attacker DMG: ${attackerDamage}, Defender DMG: ${defenderDamage}`,
        { attackValue, defenseValue, attackerDamage, defenderDamage },
      );

      return {
        finalAttack: attackValue,
        finalDefense: defenseValue,
        attackerDamage,
        defenderDamage,
        appliedEffects,
      };
    });
  }

  /**
   * Выполнить эффекты AFTER_COMBAT
   */
  async executeAfterCombatEffects(
    state: GameState,
    combat: CombatContext,
    damage: { attackerDamage: number; defenderDamage: number },
  ): Promise<AfterCombatResult> {
    const attacker = state.fighters.find((f) => f.id === combat.attackerId);
    const defender = state.fighters.find((f) => f.id === combat.defenderId);

    if (!attacker || !defender) {
      return { state, appliedEffects: [] };
    }

    let currentState = state;
    const appliedEffects: EffectResult[] = [];

    // Применяем урон
    if (damage.attackerDamage > 0) {
      currentState = this.applyDamage(currentState, attacker.id, damage.attackerDamage);
    }
    if (damage.defenderDamage > 0) {
      currentState = this.applyDamage(currentState, defender.id, damage.defenderDamage);
    }

    // Эффекты AFTER_COMBAT от атакующей карты
    const attackerCard = this.findCardById(currentState, combat.attackCardId);
    if (attackerCard) {
      const afterCombatEffects = (attackerCard.effects ?? []).filter(
        (e) => e.timing === EffectTiming.AFTER_COMBAT,
      );

      for (const effect of afterCombatEffects) {
        const context: EffectContext = {
          playerId: combat.attackerId,
          card: attackerCard,
          fighterId: combat.attackerId,
          targetFighterId: combat.defenderId,
          combat,
        };

        const result = await this.executeEffect(currentState, effect, context);
        appliedEffects.push(result);

        if (result.success) {
          currentState = this.updateStateAfterEffect(currentState, effect, result);
        }
      }
    }

    // Эффекты AFTER_COMBAT от защищающейся карты
    if (combat.defenseCardId) {
      const defenderCard = this.findCardById(currentState, combat.defenseCardId);
      if (defenderCard) {
        const afterCombatEffects = defenderCard.effects.filter(
          (e) => e.timing === EffectTiming.AFTER_COMBAT,
        );

        for (const effect of afterCombatEffects) {
          const context: EffectContext = {
            playerId: combat.defenderId,
            card: defenderCard,
            fighterId: combat.defenderId,
            targetFighterId: combat.attackerId,
            combat,
          };

          const result = await this.executeEffect(currentState, effect, context);
          appliedEffects.push(result);

          if (result.success) {
            currentState = this.updateStateAfterEffect(currentState, effect, result);
          }
        }
      }
    }

    return {
      state: currentState,
      appliedEffects,
    };
  }

  /**
   * Выполнить эффекты TURN_START для карты
   */
  async executeTurnStartEffects(
    state: GameState,
    playerId: string,
  ): Promise<GameState> {
    const handZone = state.handZones[playerId];
    if (!handZone) return state;

    let currentState = state;

    for (const card of handZone.cards) {
      const turnStartEffects = (card.effects ?? []).filter(
        (e) => e.timing === EffectTiming.TURN_START,
      );

      for (const effect of turnStartEffects) {
        const context: EffectContext = {
          playerId,
          card,
        };

        const result = await this.executeEffect(currentState, effect, context);
        if (result.success) {
          currentState = this.updateStateAfterEffect(currentState, effect, result);
        }
      }
    }

    return currentState;
  }

  /**
   * Выполнить эффекты TURN_END для карты
   */
  async executeTurnEndEffects(
    state: GameState,
    playerId: string,
  ): Promise<GameState> {
    const handZone = state.handZones[playerId];
    if (!handZone) return state;

    let currentState = state;

    for (const card of handZone.cards) {
      const turnEndEffects = (card.effects ?? []).filter(
        (e) => e.timing === EffectTiming.TURN_END,
      );

      for (const effect of turnEndEffects) {
        const context: EffectContext = {
          playerId,
          card,
        };

        const result = await this.executeEffect(currentState, effect, context);
        if (result.success) {
          currentState = this.updateStateAfterEffect(currentState, effect, result);
        }
      }
    }

    return currentState;
  }

  // === Приватные методы ===

  /**
   * Проверить, подходит ли тайминг для текущей фазы
   */
  private isTimingValid(state: GameState, timing: EffectTiming): boolean {
    switch (timing) {
      case EffectTiming.ON_PLAY:
      case EffectTiming.BEFORE_COMBAT:
        return true; // Всегда можно выполнить
      case EffectTiming.DURING_COMBAT:
        return state.phase === 'COMBAT' || state.phase === 'COMBAT_RESOLVE';
      case EffectTiming.AFTER_COMBAT:
        return state.phase === 'COMBAT_RESOLVE';
      case EffectTiming.TURN_START:
        return state.phase === 'TURN_START';
      case EffectTiming.TURN_END:
        return state.phase === 'TURN_END';
      case EffectTiming.ON_DISCARD:
        return true;
      default:
        return false;
    }
  }

  /**
   * Оценить условие эффекта
   */
  private evaluateCondition(
    state: GameState,
    condition: string,
    context: EffectContext,
  ): boolean {
    // TODO: Реализовать язык условий или использовать простые предопределённые
    // Для простых условий:
    // - "low_health": здоровье бойца < 50%
    // - "alone": нет союзников рядом
    // - "enemy_nearby": противник на соседней клетке

    if (condition === 'low_health' && context.fighterId) {
      const fighter = state.fighters.find((f) => f.id === context.fighterId);
      return fighter ? fighter.health < fighter.maxHealth * 0.5 : false;
    }

    // По умолчанию условие считается выполненным
    return true;
  }

  /**
   * Определить цели эффекта
   */
  private resolveTargets(
    state: GameState,
    effect: CardEffect,
    context: EffectContext,
  ): string[] {
    const target = effect.target ?? EffectTarget.SELF;
    const targets: string[] = [];

    // Для некоторых эффектов цель не обязательна (DRAW_CARD, DISCARD)
    if (effect.type === EffectType.DRAW_CARD || effect.type === EffectType.DISCARD) {
      // Используем playerId как цель для эффектов, действующих на игрока
      return [context.playerId];
    }

    switch (target) {
      case EffectTarget.SELF:
        if (context.fighterId) {
          targets.push(context.fighterId);
        } else if (context.combat?.attackerId === context.playerId) {
          // Если нет fighterId, используем attacker из контекста боя
          targets.push(context.combat.attackerId);
        } else if (context.combat?.defenderId === context.playerId) {
          targets.push(context.combat.defenderId);
        } else {
          // Ищем бойца по playerId
          const fighter = state.fighters.find((f) => f.ownerId === context.playerId);
          if (fighter) {
            targets.push(fighter.id);
          }
        }
        break;

      case EffectTarget.ATTACKER:
        if (context.combat?.attackerId) {
          targets.push(context.combat.attackerId);
        }
        break;

      case EffectTarget.DEFENDER:
        if (context.combat?.defenderId) {
          targets.push(context.combat.defenderId);
        }
        break;

      case EffectTarget.ALL_ENEMIES: {
        const playerId = context.playerId;
        const enemyFighters = state.fighters.filter(
          (f) => f.ownerId !== playerId,
        );
        targets.push(...enemyFighters.map((f) => f.id));
        break;
      }

      case EffectTarget.ALL_ALLIES: {
        const playerId = context.playerId;
        const allyFighters = state.fighters.filter(
          (f) => f.ownerId === playerId,
        );
        targets.push(...allyFighters.map((f) => f.id));
        break;
      }
    }

    return targets;
  }

  /**
   * Применить эффект к целям
   */
  private applyEffect(
    state: GameState,
    effect: CardEffect,
    targetIds: string[],
    context: EffectContext,
  ): EffectResult {
    const value = effect.value ?? 0;

    switch (effect.type) {
      case EffectType.MODIFY_ATTACK:
        return {
          success: true,
          effectId: effect.id,
          targetIds,
          valueApplied: value,
          message: `Modified attack by ${value}`,
        };

      case EffectType.MODIFY_DEFENSE:
        return {
          success: true,
          effectId: effect.id,
          targetIds,
          valueApplied: value,
          message: `Modified defense by ${value}`,
        };

      case EffectType.DAMAGE: {
        for (const targetId of targetIds) {
          this.valueModifierService.addModifier(targetId, {
            type: 'damage',
            operation: 'add',
            value,
            source: `effect_${effect.id}`,
          });
        }
        return {
          success: true,
          effectId: effect.id,
          targetIds,
          valueApplied: value,
          message: `Dealt ${value} damage`,
        };
      }

      case EffectType.HEAL: {
        // Если нет целей, пытаемся найти бойца игрока
        const healTargets = targetIds.length > 0
          ? targetIds
          : [context.playerId]; // Используем playerId как цель

        for (const targetId of healTargets) {
          this.valueModifierService.addModifier(targetId, {
            type: 'attack', // Используем доступный тип
            operation: 'add',
            value: -value, // Отрицательное значение = лечение
            source: `effect_${effect.id}`,
          });
        }
        return {
          success: true,
          effectId: effect.id,
          targetIds: healTargets,
          valueApplied: value,
          message: `Healed for ${value}`,
        };
      }

      case EffectType.MOVE:
        return {
          success: true,
          effectId: effect.id,
          targetIds,
          valueApplied: value,
          message: `Can move ${value} additional spaces`,
        };

      case EffectType.DRAW_CARD:
        return {
          success: true,
          effectId: effect.id,
          targetIds,
          valueApplied: value,
          message: `Draw ${value} card(s)`,
        };

      case EffectType.DISCARD:
        return {
          success: true,
          effectId: effect.id,
          targetIds,
          valueApplied: value,
          message: `Discard ${value} card(s)`,
        };

      case EffectType.PLACE:
        return {
          success: true,
          effectId: effect.id,
          targetIds,
          message: 'Place effect applied',
        };

      default:
        return {
          success: false,
          effectId: effect.id,
          targetIds,
          message: `Unknown effect type: ${effect.type}`,
        };
    }
  }

  /**
   * Обновить состояние после применения эффекта
   */
  private updateStateAfterEffect(
    state: GameState,
    effect: CardEffect,
    result: EffectResult,
  ): GameState {
    // Для эффектов, которые изменяют состояние напрямую
    // TODO: Реализовать полную иммутабельную обработку

    switch (effect.type) {
      case EffectType.DAMAGE:
        // Урон применяется через ValueModifierService
        break;

      case EffectType.HEAL:
        // Лечение аналогично
        break;

      case EffectType.DRAW_CARD:
        if (result.valueApplied) {
          state = this.drawCards(state, result.targetIds[0], result.valueApplied);
        }
        break;

      case EffectType.DISCARD:
        if (result.valueApplied) {
          state = this.discardCards(state, result.targetIds[0], result.valueApplied);
        }
        break;
    }

    return state;
  }

  /**
   * Применить урон к бойцу (иммутабельно)
   */
  private applyDamage(state: GameState, fighterId: string, damage: number): GameState {
    const fighter = state.fighters.find((f) => f.id === fighterId);
    if (!fighter) return state;

    const newHealth = Math.max(0, fighter.health - damage);

    return {
      ...state,
      fighters: state.fighters.map((f) =>
        f.id === fighterId ? { ...f, health: newHealth } : f,
      ),
    };
  }

  /**
   * Найти карту по ID в состоянии
   */
  private findCardById(state: GameState, cardId: string): Card | null {
    // Поиск в руках всех игроков
    for (const handZone of Object.values(state.handZones)) {
      const card = handZone.cards.find((c) => c.id === cardId);
      if (card) return card;
    }

    // Поиск в сбросах
    for (const discardPile of Object.values(state.discardPiles)) {
      const card = discardPile.find((c) => c.id === cardId);
      if (card) return card;
    }

    return null;
  }

  /**
   * Взять карты из колоды
   */
  private drawCards(state: GameState, playerId: string, count: number): GameState {
    // TODO: Реализовать логику взятия карт
    return state;
  }

  /**
   * Сбросить карты из руки
   */
  private discardCards(state: GameState, playerId: string, count: number): GameState {
    // TODO: Реализовать логику сброса карт
    return state;
  }
}
