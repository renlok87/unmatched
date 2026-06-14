/**
 * Hero Ability Registry
 *
 * Реестр способностей героев Unmatched.
 * Позволяет регистрировать и применять способности героев без хардкода в CombatResolverService.
 */

import { Injectable, Logger } from '@nestjs/common';
import { Fighter, Position } from '../models';
import type { GameState } from '../models/game-state.model';

// Реэкспорт для использования в handler'ах
export type { Fighter } from '../models';

/**
 * Роль в бою
 */
export type CombatRole = 'attacker' | 'defender';

/**
 * Модификатор значения
 */
export interface ValueModifier {
  readonly type: ValueModifierType;
  readonly value: number;
  readonly source: string;
  readonly timestamp: number;
  readonly ownerId: string;
}

/**
 * Тип модификатора
 */
export enum ValueModifierType {
  ADD = 'ADD',
  SET = 'SET',
  IGNORE = 'IGNORE',
  MULTIPLY = 'MULTIPLY',
}

/**
 * Событие игры
 */
export interface GameEvent {
  readonly type: string;
  readonly description: string;
  readonly sourceId: string;
}

/**
 * Состояние боя (упрощённое)
 */
export interface CombatState {
  readonly attackerId: string;
  /** id ЗАЩИЩАЮЩЕГОСЯ ИГРОКА (combatInfo.defenderId), НЕ бойца. */
  readonly defenderId: string;
  /** id бойца-цели атаки (combatInfo.targetFighterId) — это и есть боец-защитник
   *  (атака по сайдкику ранит сайдкика). Для способностей, которым нужен именно
   *  защищающийся БОЕЦ (напр. self-health-below-defender), брать его, а не defenderId. */
  readonly targetFighterId?: string;
  readonly attackCardId?: string;
  readonly defenseCardId?: string;
  readonly round?: number;
}

/**
 * Обработчик способности героя (классический интерфейс)
 */
export interface HeroAbilityHandler {
  readonly heroId: string;
  readonly name: string;
  readonly description: string;

  /** Ability разрешает BOOST атаки/защиты картой из руки (King Arthur —
   *  атака), даже если на играемой карте нет BOOST-эффекта */
  readonly allowsAttackBoost?: boolean;
  readonly allowsDefenseBoost?: boolean;

  /**
   * Применить модификаторы к бою
   */
  applyCombatModifier?(
    combatState: CombatState,
    fighter: Fighter,
    role: CombatRole,
  ): readonly ValueModifier[];

  /**
   * Обработать перемещение
   */
  onMove?(fighter: Fighter, from: Position, to: Position): readonly GameEvent[];

  /**
   * Обработать поражение
   */
  onDefeat?(fighter: Fighter): readonly GameEvent[];

  /**
   * В начале хода
   */
  onTurnStart?(fighter: Fighter): readonly GameEvent[];

  /**
   * В конце хода
   */
  onTurnEnd?(fighter: Fighter): readonly GameEvent[];
}

/**
 * Модификатор боя
 */
export interface CombatModifier {
  readonly type: 'add' | 'set' | 'multiply';
  readonly value: number;
  readonly source: string;
  readonly appliesTo: 'attack' | 'defense' | 'both';
}

/**
 * Контекст after-combat хука (TASK): данные завершившегося боя для
 * способности АТАКУЮЩЕГО героя. Передаётся в onAfterCombat ПОСЛЕ применения
 * урона/флагов поражения, но ДО передачи хода (advanceTurn).
 */
export interface AfterCombatContext {
  /** Владелец атакующего бойца (атакующий игрок) */
  readonly playerId: string;
  /**
   * Владелец защищающегося бойца (защищающийся игрок). Для defender-side
   * способностей (триггер 'after-defense', напр. Spider-Sense): turn-effect
   * правила 'after-defense' применяются именно к этому игроку, а не к
   * атакующему playerId. Опционально для обратной совместимости со старыми
   * вызовами, не заполнявшими поле.
   */
  readonly defenderPlayerId?: string;
  /** id атакующего бойца (combatInfo.attackerId) */
  readonly attackerFighterId: string;
  /** id атакованного бойца */
  readonly defenderFighterId: string;
  /** Атакующий победил (finalAttack > finalDefense; ничья → false) */
  readonly won: boolean;
  /** Урон, нанесённый атакующим в этом бою */
  readonly damageDealt: number;
  /** Это ПЕРВЫЙ проигранный бой атакующего в текущем ходу (TASK). Считается ДО
   *  установки lostCombatThisTurn: при won===true всегда false; при won===false —
   *  true только если в этом ходу ещё не было проигрышей. Позволяет способности
   *  реагировать на первый проигрыш хода (а не на каждый). */
  readonly firstLossThisTurn: boolean;
}

/**
 * Расширенный интерфейс обработчика способностей
 * Поддерживает работу с состоянием игры и новыми типами способностей
 */
export interface ExtendedHeroAbilityHandler {
  readonly heroId: string;
  readonly abilityName: string;
  readonly abilityDescription: string;

  /**
   * Вызывается в начале хода игрока
   */
  onTurnStart?(state: GameState, playerId: string): Promise<GameState>;

  /**
   * Вызывается в конце хода игрока
   */
  onTurnEnd?(state: GameState, playerId: string): Promise<GameState>;

  /**
   * Вызывается во время боя
   */
  onCombat?(state: GameState, context: CombatState & { isBlindBoostAvailable?: boolean }): Promise<GameState>;

  /**
   * Вызывается ПОСЛЕ резолва боя — для способности АТАКУЮЩЕГО героя
   * (после применения урона/флагов поражения, ДО передачи хода). Позволяет
   * способности отреагировать на исход боя (добор/лечение/доп. действие и т.п.).
   */
  onAfterCombat?(state: GameState, ctx: AfterCombatContext): Promise<GameState>;

  /**
   * Вызывается, когда боец помечен повергнутым (РЕАНИМИРОВАННЫЙ on-defeat хук).
   * В отличие от мёртвого классического onDefeat(fighter): GameEvent[] (никогда
   * не вызывался в проде), этот EXTENDED-хук мутирует GameState и реально
   * дёргается executor'ом после установки isDefeated (ДО game-over/передачи
   * хода). Диспетчеризуется на героя ВЛАДЕЛЬЦА повергнутого бойца, чтобы герой
   * мог отреагировать на гибель своего сайдкика (Achilles → discard 2). Чистый
   * no-op для героев без реакции (тот же state).
   */
  onFighterDefeated?(state: GameState, defeatedFighter: Fighter): Promise<GameState>;

  /**
   * Проверяет, может ли боец атаковать на определённой дистанции
   */
  canAttackAtRange?(attackerId: string, defenderId: string, range: number): boolean;

  /**
   * Получить модификаторы боя
   */
  getCombatModifiers?(
    context: CombatState & { isBlindBoostAvailable?: boolean },
    fighter: Fighter,
    role: 'attacker' | 'defender',
  ): readonly CombatModifier[];

  /**
   * STATEFUL боевые модификаторы (доступ к GameState).
   *
   * В отличие от классического applyCombatModifier (CombatState+fighter+role,
   * без GameState), этот хук получает полный GameState — способность может
   * вычислять модификатор по условиям состояния игры (позиции, здоровье,
   * эффекты, ход и т.п.). Суммируется по той же ADD-семантике, что и
   * классический путь, и добавляется к итоговым атаке/защите боя.
   */
  getStatefulCombatModifiers?(
    state: GameState,
    context: CombatState,
    fighter: Fighter,
    role: 'attacker' | 'defender',
  ): readonly ValueModifier[];

  /**
   * АУРНЫЕ боевые модификаторы (Oda-style): ЭТОТ герой как ГРАНИТЕЛЬ ауры
   * баффает ДРУГОГО дружественного бойца (beneficiary), делящего его зону, во
   * время боя бенефициара. В отличие от getStatefulCombatModifiers (own-handler
   * бойца боя), этот хук консультирует КАЖДОГО зарегистрированного героя — аура
   * исходит от героя, ОТЛИЧНОГО от героя бенефициара. ADD-семантика, как у
   * остальных combat-модификаторов.
   */
  getAuraCombatModifiers?(
    state: GameState,
    beneficiary: Fighter,
    role: 'attacker' | 'defender',
  ): readonly ValueModifier[];
}

/**
 * Registry для способностей героев
 */
@Injectable()
export class HeroAbilityRegistry {
  private readonly logger = new Logger(HeroAbilityRegistry.name);
  private readonly handlers = new Map<string, HeroAbilityHandler>();
  private readonly extendedHandlers = new Map<string, ExtendedHeroAbilityHandler>();

  /**
   * Зарегистрировать классический обработчик способности героя
   */
  register(handler: HeroAbilityHandler): void {
    if (this.handlers.has(handler.heroId)) {
      this.logger.warn(`Hero ${handler.heroId} ability already registered, overwriting`);
    }
    this.handlers.set(handler.heroId, handler);
    this.logger.debug(`Registered ability for hero: ${handler.heroId} - ${handler.name}`);
  }

  /**
   * Зарегистрировать расширенный обработчик способности героя
   */
  registerExtended(handler: ExtendedHeroAbilityHandler): void {
    if (this.extendedHandlers.has(handler.heroId)) {
      this.logger.warn(`Hero ${handler.heroId} extended ability already registered, overwriting`);
    }
    this.extendedHandlers.set(handler.heroId, handler);
    this.logger.debug(`Registered extended ability for hero: ${handler.heroId} - ${handler.abilityName}`);
  }

  /**
   * Получить классический обработчик способности героя
   */
  get(heroId: string): HeroAbilityHandler | undefined {
    return this.handlers.get(heroId);
  }

  /**
   * Получить расширенный обработчик способности героя
   */
  getExtended(heroId: string): ExtendedHeroAbilityHandler | undefined {
    return this.extendedHandlers.get(heroId);
  }

  /**
   * Получить любой доступный обработчик (классический или расширенный)
   */
  getAny(heroId: string): HeroAbilityHandler | ExtendedHeroAbilityHandler | undefined {
    return this.extendedHandlers.get(heroId) ?? this.handlers.get(heroId);
  }

  /**
   * Проверить, есть ли зарегистрированная способность
   */
  has(heroId: string): boolean {
    return this.handlers.has(heroId) || this.extendedHandlers.has(heroId);
  }

  /**
   * Получить все зарегистрированные герои
   */
  getRegisteredHeroes(): readonly string[] {
    const classicHeroes = Array.from(this.handlers.keys());
    const extendedHeroes = Array.from(this.extendedHandlers.keys());
    return Array.from(new Set([...classicHeroes, ...extendedHeroes]));
  }

  /**
   * Применить боевые модификаторы от способности героя
   */
  applyCombatModifiers(
    heroId: string,
    combatState: CombatState,
    fighter: Fighter,
    role: CombatRole,
  ): readonly ValueModifier[] {
    const handler = this.get(heroId);
    if (!handler?.applyCombatModifier) {
      return [];
    }

    try {
      return handler.applyCombatModifier(combatState, fighter, role);
    } catch (error) {
      this.logger.error(`Error applying combat modifier for hero ${heroId}:`, error);
      return [];
    }
  }

  /**
   * Вызвать событие перемещения
   */
  triggerOnMove(
    heroId: string,
    fighter: Fighter,
    from: Position,
    to: Position,
  ): readonly GameEvent[] {
    const handler = this.get(heroId);
    if (!handler?.onMove) {
      return [];
    }

    try {
      return handler.onMove(fighter, from, to);
    } catch (error) {
      this.logger.error(`Error in onMove for hero ${heroId}:`, error);
      return [];
    }
  }

  /**
   * Вызвать событие поражения
   */
  triggerOnDefeat(heroId: string, fighter: Fighter): readonly GameEvent[] {
    const handler = this.get(heroId);
    if (!handler?.onDefeat) {
      return [];
    }

    try {
      return handler.onDefeat(fighter);
    } catch (error) {
      this.logger.error(`Error in onDefeat for hero ${heroId}:`, error);
      return [];
    }
  }

  /**
   * Вызвать событие начала хода (классический путь, ТОЛЬКО логирование).
   *
   * TASK A: продакшен-поток начала хода (GameActionExecutor.advanceTurn) зовёт
   * расширенный диспетчер triggerOnTurnStartExtended (он мутирует GameState).
   * Этот GameEvent[]-метод оставлен для логирования/совместимости и в
   * продакшен-передаче хода больше не вызывается.
   */
  triggerOnTurnStart(heroId: string, fighter: Fighter): readonly GameEvent[] {
    const handler = this.get(heroId);
    if (!handler?.onTurnStart) {
      return [];
    }

    try {
      return handler.onTurnStart(fighter);
    } catch (error) {
      this.logger.error(`Error in onTurnStart for hero ${heroId}:`, error);
      return [];
    }
  }

  /**
   * Вызвать событие конца хода
   */
  triggerOnTurnEnd(heroId: string, fighter: Fighter): readonly GameEvent[] {
    const handler = this.get(heroId);
    if (!handler?.onTurnEnd) {
      return [];
    }

    try {
      return handler.onTurnEnd(fighter);
    } catch (error) {
      this.logger.error(`Error in onTurnEnd for hero ${heroId}:`, error);
      return [];
    }
  }

  /**
   * Проверить, может ли герой атаковать на определённой дистанции
   * Использует расширенные обработчики
   */
  canAttackAtRange(heroId: string, attackerId: string, defenderId: string, range: number): boolean {
    const handler = this.getExtended(heroId);
    if (!handler?.canAttackAtRange) {
      return false;
    }

    try {
      return handler.canAttackAtRange(attackerId, defenderId, range);
    } catch (error) {
      this.logger.error(`Error in canAttackAtRange for hero ${heroId}:`, error);
      return false;
    }
  }

  /**
   * Вызвать обработчик начала хода (расширенный)
   */
  async triggerOnTurnStartExtended(
    heroId: string,
    state: GameState,
    playerId: string,
  ): Promise<GameState> {
    const handler = this.getExtended(heroId);
    if (!handler?.onTurnStart) {
      return state;
    }

    try {
      return await handler.onTurnStart(state, playerId);
    } catch (error) {
      this.logger.error(`Error in onTurnStart for hero ${heroId}:`, error);
      return state;
    }
  }

  /**
   * Вызвать обработчик конца хода (расширенный)
   */
  async triggerOnTurnEndExtended(
    heroId: string,
    state: GameState,
    playerId: string,
  ): Promise<GameState> {
    const handler = this.getExtended(heroId);
    if (!handler?.onTurnEnd) {
      return state;
    }

    try {
      return await handler.onTurnEnd(state, playerId);
    } catch (error) {
      this.logger.error(`Error in onTurnEnd for hero ${heroId}:`, error);
      return state;
    }
  }

  /**
   * Вызвать after-combat обработчик АТАКУЮЩЕГО героя (расширенный).
   *
   * Зеркало triggerOnTurnEndExtended: getExtended(heroId), вызов
   * handler.onAfterCombat если есть, try/catch → возврат исходного state.
   * Отсутствие хука/ошибка — состояние без изменений.
   */
  async triggerOnAfterCombat(
    heroId: string,
    state: GameState,
    ctx: AfterCombatContext,
  ): Promise<GameState> {
    const handler = this.getExtended(heroId);
    if (!handler?.onAfterCombat) {
      return state;
    }

    try {
      return await handler.onAfterCombat(state, ctx);
    } catch (error) {
      this.logger.error(`Error in onAfterCombat for hero ${heroId}:`, error);
      return state;
    }
  }

  /**
   * Вызвать on-defeat хук героя (расширенный, РЕАНИМИРОВАННЫЙ).
   *
   * Зеркало triggerOnAfterCombat: getExtended(heroId), вызов
   * handler.onFighterDefeated если есть, try/catch → возврат исходного state.
   * heroId — слаг героя ВЛАДЕЛЬЦА повергнутого бойца (executor резолвит его с
   * HERO-бойца владельца). Отсутствие хука/ошибка — состояние без изменений.
   */
  async triggerOnFighterDefeated(
    heroId: string,
    state: GameState,
    defeatedFighter: Fighter,
  ): Promise<GameState> {
    const handler = this.getExtended(heroId);
    if (!handler?.onFighterDefeated) {
      return state;
    }

    try {
      return await handler.onFighterDefeated(state, defeatedFighter);
    } catch (error) {
      this.logger.error(`Error in onFighterDefeated for hero ${heroId}:`, error);
      return state;
    }
  }

  /**
   * Вызвать обработчик боя (расширенный)
   */
  async triggerOnCombat(
    heroId: string,
    state: GameState,
    context: CombatState & { isBlindBoostAvailable?: boolean },
  ): Promise<GameState> {
    const handler = this.getExtended(heroId);
    if (!handler?.onCombat) {
      return state;
    }

    try {
      return await handler.onCombat(state, context);
    } catch (error) {
      this.logger.error(`Error in onCombat for hero ${heroId}:`, error);
      return state;
    }
  }

  /**
   * Получить боевые модификаторы (расширенные)
   */
  getExtendedCombatModifiers(
    heroId: string,
    context: CombatState & { isBlindBoostAvailable?: boolean },
    fighter: Fighter,
    role: 'attacker' | 'defender',
  ): readonly CombatModifier[] {
    const handler = this.getExtended(heroId);
    if (!handler?.getCombatModifiers) {
      return [];
    }

    try {
      return handler.getCombatModifiers(context, fighter, role);
    } catch (error) {
      this.logger.error(`Error in getCombatModifiers for hero ${heroId}:`, error);
      return [];
    }
  }

  /**
   * Получить STATEFUL боевые модификаторы способности героя (с доступом к
   * GameState). Lookup через getAny (extended ИЛИ classic); вызывает
   * handler.getStatefulCombatModifiers, если он есть. Отсутствие хука —
   * пустой массив; ошибка — пустой массив (как остальные диспетчеры).
   */
  getStatefulCombatModifiers(
    heroId: string,
    state: GameState,
    combatState: CombatState,
    fighter: Fighter,
    role: CombatRole,
  ): readonly ValueModifier[] {
    const handler = this.getAny(heroId) as ExtendedHeroAbilityHandler | undefined;
    if (!handler?.getStatefulCombatModifiers) {
      return [];
    }

    try {
      return handler.getStatefulCombatModifiers(state, combatState, fighter, role);
    } catch (error) {
      this.logger.error(`Error in getStatefulCombatModifiers for hero ${heroId}:`, error);
      return [];
    }
  }

  /**
   * Получить АУРНЫЕ боевые модификаторы для бойца-БЕНЕФИЦИАРА (с доступом к
   * GameState). В отличие от getStatefulCombatModifiers (lookup по героя
   * КОНКРЕТНОГО бойца), аура исходит от ДРУГОГО героя-гранителя — поэтому
   * консультируем ВСЕ зарегистрированные extended-handler'ы и конкатенируем их
   * вклад. try/catch на каждом handler'е (ошибка одного не валит остальных).
   * Отсутствие хука у handler'а — пропуск. ADD-семантика, как у остальных.
   */
  getAuraCombatModifiers(
    state: GameState,
    beneficiary: Fighter,
    role: CombatRole,
  ): readonly ValueModifier[] {
    const modifiers: ValueModifier[] = [];

    for (const handler of this.extendedHandlers.values()) {
      if (!handler.getAuraCombatModifiers) continue;

      try {
        const mods = handler.getAuraCombatModifiers(state, beneficiary, role);
        if (mods && mods.length > 0) {
          modifiers.push(...mods);
        }
      } catch (error) {
        this.logger.error(
          `Error in getAuraCombatModifiers for hero ${handler.heroId}:`,
          error,
        );
      }
    }

    return modifiers;
  }
}
