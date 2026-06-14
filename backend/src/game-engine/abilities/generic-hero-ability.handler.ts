/**
 * Generic Hero Ability Handler
 *
 * Интерпретатор декларативных AbilityConfig: один класс обслуживает любого
 * героя, чья способность описана правилами (AbilityRule[]). Реализует
 * ExtendedHeroAbilityHandler — extended-карта реестра обслуживает turn-хуки
 * И stateful combat (через getAny).
 *
 * ВАЖНО: это plain-класс (НЕ Nest-провайдер) — зависимости передаются через
 * deps в конструкторе из цикла регистрации модуля.
 */

import type { GameState } from '../models/game-state.model';
import { getActionsRemaining } from '../models/game-state.model';
import type { Fighter } from '../models/fighter.model';
import { FighterType } from '../models/fighter.model';
import type { BoardState } from '../models/board.model';
import {
  ExtendedHeroAbilityHandler,
  ValueModifier,
  ValueModifierType,
  CombatState,
} from './hero-ability-registry';
import {
  AbilityConfig,
  AbilityCondition,
  AbilityRule,
  CombatModifierEffect,
  TurnEffect,
} from './ability-config';

/**
 * Зависимости handler'а. Передаются плоским объектом из цикла регистрации
 * модуля (НЕ Nest DI, т.к. handler — обычный класс).
 */
export interface GenericHeroAbilityDeps {
  /** Для draw/drawToHandSize — реальный DeckManagementService */
  readonly deck: {
    drawCards(state: GameState, userId: string, count: number): Promise<GameState>;
  };
  /** Проверка зон для 'no-enemy-in-own-zone' (AdjacencyService.isInSameZone) */
  readonly zone: {
    isInSameZone(
      state: { boardState: BoardState },
      a: { x: number; y: number },
      b: { x: number; y: number },
    ): boolean;
  };
}

/**
 * Generic data-driven handler способности героя.
 */
export class GenericHeroAbilityHandler implements ExtendedHeroAbilityHandler {
  readonly heroId: string;
  readonly abilityName: string;
  readonly abilityDescription: string;

  private readonly rules: readonly AbilityRule[];

  constructor(
    private readonly config: AbilityConfig,
    private readonly deps: GenericHeroAbilityDeps,
  ) {
    this.heroId = config.heroId;
    this.abilityName = config.abilityName;
    this.abilityDescription = config.description;
    this.rules = config.rules;
  }

  // ===================== COMBAT (stateful) =====================

  /**
   * STATEFUL боевые модификаторы. Проходит по 'combat-passive' правилам,
   * проверяет сторону (appliesTo vs role) и условие против GameState.
   * Возвращает ТОЛЬКО здесь (классический applyCombatModifier не реализуем —
   * во избежание двойного учёта; все combat-моды идут через этот путь).
   */
  getStatefulCombatModifiers(
    state: GameState,
    context: CombatState,
    fighter: Fighter,
    role: 'attacker' | 'defender',
  ): readonly ValueModifier[] {
    const modifiers: ValueModifier[] = [];

    for (const rule of this.rules) {
      if (rule.trigger !== 'combat-passive') continue;
      if (rule.effect.kind !== 'combat-modifier') continue;

      const effect = rule.effect as CombatModifierEffect;

      // Сторона: appliesTo должен совпадать с ролью бойца ('both' — всегда)
      if (!this.sideMatchesRole(effect.appliesTo, role)) continue;

      // Условие против GameState
      if (!this.evalCombatCondition(rule.condition ?? 'always', state, context, fighter, role)) {
        continue;
      }

      modifiers.push({
        type: ValueModifierType.ADD,
        value: effect.value,
        source: `hero-ability:${this.heroId}:${this.abilityName}`,
        ownerId: fighter.ownerId,
        timestamp: Date.now(),
      });
    }

    return modifiers;
  }

  // ===================== TURN-START / TURN-END =====================

  async onTurnStart(state: GameState, playerId: string): Promise<GameState> {
    return this.applyTurnRules(state, playerId, 'turn-start');
  }

  async onTurnEnd(state: GameState, playerId: string): Promise<GameState> {
    return this.applyTurnRules(state, playerId, 'turn-end');
  }

  // ===================== ВНУТРЕННЕЕ =====================

  /**
   * Применяет все правила указанного turn-триггера. Возвращает state
   * НЕИЗМЕНЁННЫМ, если ни одно правило не подошло (чистый no-op — поток хода
   * остаётся ACTION_MANEUVER, seq не трогаем).
   */
  private async applyTurnRules(
    state: GameState,
    playerId: string,
    trigger: 'turn-start' | 'turn-end',
  ): Promise<GameState> {
    let current = state;

    for (const rule of this.rules) {
      if (rule.trigger !== trigger) continue;
      if (rule.effect.kind !== 'turn-effect') continue;

      if (!this.evalTurnCondition(rule.condition ?? 'always', current, playerId)) {
        continue;
      }

      current = await this.applyTurnEffect(current, playerId, rule.effect as TurnEffect);
    }

    return current;
  }

  /**
   * Применяет один turn-effect к состоянию (draw / drawToHandSize / heal /
   * gainAction). Порядок: добор → лечение → действие.
   */
  private async applyTurnEffect(
    state: GameState,
    playerId: string,
    effect: TurnEffect,
  ): Promise<GameState> {
    let current = state;

    // draw N
    if (typeof effect.draw === 'number' && effect.draw > 0) {
      current = await this.deps.deck.drawCards(current, playerId, effect.draw);
    }

    // drawToHandSize N — добираем по дефициту (drawCards сам стопнется на пустой колоде)
    if (typeof effect.drawToHandSize === 'number') {
      const handSize = current.handZones[playerId]?.cards.length ?? 0;
      const deficit = effect.drawToHandSize - handSize;
      if (deficit > 0) {
        current = await this.deps.deck.drawCards(current, playerId, deficit);
      }
    }

    // heal N — иммутабельный bump здоровья героя (min(maxHealth, health+N))
    if (typeof effect.heal === 'number' && effect.heal > 0) {
      current = this.healHero(current, playerId, effect.heal);
    }

    // gainAction N — +N к оставшимся действиям хода
    if (typeof effect.gainAction === 'number' && effect.gainAction > 0) {
      current = this.gainActions(current, playerId, effect.gainAction);
    }

    return current;
  }

  /**
   * Иммутабельно повышает здоровье героя игрока (не выше maxHealth).
   */
  private healHero(state: GameState, playerId: string, amount: number): GameState {
    const hero = this.findHeroFighter(state, playerId);
    if (!hero) return state;

    const newHealth = Math.min(hero.maxHealth, hero.health + amount);
    if (newHealth === hero.health) return state;

    const fighters = state.fighters.map((f) =>
      f.id === hero.id ? { ...f, health: newHealth } : f,
    );
    return { ...state, fighters };
  }

  /**
   * Иммутабельно прибавляет действия к ходу (через getActionsRemaining helper).
   */
  private gainActions(state: GameState, _playerId: string, amount: number): GameState {
    const current = getActionsRemaining(state);
    return {
      ...state,
      metadata: {
        ...state.metadata,
        actionsRemaining: current + amount,
      },
    };
  }

  // ===================== УСЛОВИЯ =====================

  /** appliesTo стороны эффекта против роли бойца в бою */
  private sideMatchesRole(
    appliesTo: 'attack' | 'defense' | 'both',
    role: 'attacker' | 'defender',
  ): boolean {
    if (appliesTo === 'both') return true;
    if (appliesTo === 'attack') return role === 'attacker';
    return role === 'defender';
  }

  /**
   * Условия боевых правил.
   */
  private evalCombatCondition(
    condition: AbilityCondition,
    state: GameState,
    context: CombatState,
    fighter: Fighter,
    role: 'attacker' | 'defender',
  ): boolean {
    if (typeof condition === 'object') {
      // { handSizeEquals } — применимо и в бою (рука владельца бойца)
      return this.evalHandSize(state, fighter.ownerId, condition.handSizeEquals);
    }

    switch (condition) {
      case 'always':
        return true;
      case 'attacking':
        return role === 'attacker';
      case 'defending':
        return role === 'defender';
      case 'self-health-below-defender': {
        const defender = state.fighters.find((f) => f.id === context.defenderId);
        return defender ? fighter.health < defender.health : false;
      }
      case 'all-own-sidekicks-defeated':
        return this.allOwnSidekicksDefeated(state, fighter.ownerId);
      case 'no-enemy-in-own-zone':
        return this.noEnemyInOwnZone(state, fighter.ownerId);
      default:
        return false;
    }
  }

  /**
   * Условия turn-правил.
   */
  private evalTurnCondition(
    condition: AbilityCondition,
    state: GameState,
    playerId: string,
  ): boolean {
    if (typeof condition === 'object') {
      return this.evalHandSize(state, playerId, condition.handSizeEquals);
    }

    switch (condition) {
      case 'always':
        return true;
      case 'all-own-sidekicks-defeated':
        return this.allOwnSidekicksDefeated(state, playerId);
      case 'no-enemy-in-own-zone':
        return this.noEnemyInOwnZone(state, playerId);
      // боевые условия вне боя не имеют смысла → не срабатывают
      case 'attacking':
      case 'defending':
      case 'self-health-below-defender':
        return false;
      default:
        return false;
    }
  }

  private evalHandSize(state: GameState, playerId: string, n: number): boolean {
    const handSize = state.handZones[playerId]?.cards.length ?? 0;
    return handSize === n;
  }

  /** Все НЕ-герои владельца повержены (isDefeated). */
  private allOwnSidekicksDefeated(state: GameState, ownerId: string): boolean {
    const sidekicks = state.fighters.filter(
      (f) => f.ownerId === ownerId && f.type !== FighterType.HERO,
    );
    if (sidekicks.length === 0) return false;
    return sidekicks.every((f) => f.isDefeated === true);
  }

  /** В зоне героя игрока нет ни одного вражеского бойца. */
  private noEnemyInOwnZone(state: GameState, ownerId: string): boolean {
    const hero = this.findHeroFighter(state, ownerId);
    if (!hero) return false;

    const enemies = state.fighters.filter(
      (f) => f.ownerId !== ownerId && f.isDefeated !== true,
    );

    for (const enemy of enemies) {
      if (this.deps.zone.isInSameZone(state, hero.position, enemy.position)) {
        return false;
      }
    }
    return true;
  }

  /** Найти бойца-героя игрока (type === HERO). */
  private findHeroFighter(state: GameState, ownerId: string): Fighter | undefined {
    return state.fighters.find(
      (f) => f.ownerId === ownerId && f.type === FighterType.HERO,
    );
  }
}
