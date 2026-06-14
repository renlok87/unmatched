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
  AfterCombatContext,
} from './hero-ability-registry';
import {
  AbilityConfig,
  AbilityCondition,
  AbilityRule,
  CombatModifierEffect,
  PendingMoveEffect,
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

  // ===================== AFTER-ATTACK =====================

  /**
   * Эффект ПОСЛЕ резолва боя. Обслуживает ДВЕ симметричные стороны:
   *  - 'after-attack'  — способность АТАКУЮЩЕГО героя; turn-effect применяется
   *                      к атакующему игроку (ctx.playerId);
   *  - 'after-defense' — способность ЗАЩИЩАЮЩЕГОСЯ героя (напр. Spider-Sense);
   *                      turn-effect применяется к защитнику (ctx.defenderPlayerId).
   * В обоих случаях after-combat условие проверяется против исхода боя
   * (ctx.won) теми же примитивами, что turn-start/turn-end (draw/heal/
   * gainAction/drawToHandSize). Чистый no-op (тот же объект state), если ни
   * одно правило не подошло (в т.ч. 'after-defense' без ctx.defenderPlayerId).
   */
  async onAfterCombat(state: GameState, ctx: AfterCombatContext): Promise<GameState> {
    let current = state;

    for (const rule of this.rules) {
      if (rule.trigger !== 'after-attack' && rule.trigger !== 'after-defense') continue;
      if (rule.effect.kind !== 'turn-effect' && rule.effect.kind !== 'pending-move') continue;

      if (!this.evalAfterCombatCondition(rule.condition ?? 'always', ctx)) {
        continue;
      }

      // Цель эффекта: атакующий для 'after-attack', защитник для 'after-defense'.
      const targetPlayerId =
        rule.trigger === 'after-defense' ? ctx.defenderPlayerId : ctx.playerId;
      // 'after-defense' без известного защитника — нечего применять (no-op).
      if (!targetPlayerId) continue;

      if (rule.effect.kind === 'pending-move') {
        current = this.applyPendingMove(current, targetPlayerId, rule.effect, ctx);
        continue;
      }

      current = await this.applyTurnEffect(current, targetPlayerId, rule.effect as TurnEffect);
    }

    return current;
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
      if (rule.effect.kind !== 'turn-effect' && rule.effect.kind !== 'pending-move') continue;

      if (!this.evalTurnCondition(rule.condition ?? 'always', current, playerId)) {
        continue;
      }

      if (rule.effect.kind === 'pending-move') {
        // turn-контекст не несёт боя → target 'attacker' здесь невалиден (no-op).
        current = this.applyPendingMove(current, playerId, rule.effect);
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
   * Порождает MOVE PendingEffect (C2) для способности и иммутабельно
   * дописывает его в metadata.pendingEffects. Сам ход НЕ исполняется — резолв
   * остаётся за общим C2 (мутация resolvePendingEffect; протухает в advanceTurn).
   * Форма PendingEffect зеркалит card-effect-executor (id/type/playerId/value/
   * fighterName/targetsOpponent/text). sequenceNumber НЕ бампим (pendingEffects
   * никогда не двигают seq).
   *
   * Разрешение бойца (fighterName) по target:
   *  - 'attacker' — имя бойца из ctx.attackerFighterId (валидно лишь при наличии
   *                 after-combat ctx). Без ctx/бойца → no-op (тот же state).
   *  - 'own-hero' — имя HERO-бойца игрока. Без героя → no-op.
   *  - 'any-own'  — fighterName опускается (игрок выберет любого своего бойца).
   */
  private applyPendingMove(
    state: GameState,
    playerId: string,
    effect: PendingMoveEffect,
    ctx?: AfterCombatContext,
  ): GameState {
    let fighterName: string | undefined;

    switch (effect.target) {
      case 'attacker': {
        // 'attacker' имеет смысл ТОЛЬКО для after-attack (нужен ctx с бойцом).
        if (!ctx) return state;
        const attacker = state.fighters.find((f) => f.id === ctx.attackerFighterId);
        if (!attacker) return state;
        fighterName = attacker.name;
        break;
      }
      case 'own-hero': {
        const hero = this.findHeroFighter(state, playerId);
        if (!hero) return state;
        fighterName = hero.name;
        break;
      }
      case 'any-own':
        // fighterName опускается — игрок двигает любого своего бойца.
        fighterName = undefined;
        break;
      default:
        return state;
    }

    const len = state.metadata.pendingEffects?.length ?? 0;
    // Зеркалит форму pending из card-effect-executor (~619-637): включаем
    // fighterName только когда он задан (executor для MOVE всегда пишет ключ,
    // но для 'any-own' семантика — «без ограничения» → ключ опускаем).
    const pending = {
      id: `ability-${this.heroId}-move-p${len}`,
      type: 'MOVE' as const,
      playerId,
      value: effect.maxSpaces,
      ...(fighterName !== undefined ? { fighterName } : {}),
      targetsOpponent: false,
      text: `${this.abilityName} — move`,
    };

    return {
      ...state,
      metadata: {
        ...state.metadata,
        pendingEffects: [...(state.metadata.pendingEffects ?? []), pending],
      },
    };
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
      // Per-turn флаги активного игрока. combat-passive имеет смысл для
      // АТАКУЮЩЕГО (флаги — текущего активного игрока, он же атакующий).
      case 'has-not-maneuvered-this-turn':
        return !state.metadata.maneuveredThisTurn;
      case 'has-attacked-this-turn':
        return !!state.metadata.attackedThisTurn;
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

  /**
   * Условия after-attack правил. Оцениваются ТОЛЬКО против исхода боя:
   *  - 'always'                      → всегда
   *  - 'won-combat'                  → ctx.won === true
   *  - 'lost-combat'                 → ctx.won === false
   *  - 'first-lost-combat-this-turn' → ctx.won === false && ctx.firstLossThisTurn
   * Любое иное условие (боевое/ходовое/{handSizeEquals}) для after-attack не
   * валидно и безопасно игнорируется (правило не срабатывает).
   */
  private evalAfterCombatCondition(
    condition: AbilityCondition,
    ctx: AfterCombatContext,
  ): boolean {
    if (typeof condition === 'object') {
      // { handSizeEquals } не применимо к after-attack → no-op
      return false;
    }

    switch (condition) {
      case 'always':
        return true;
      case 'won-combat':
        return ctx.won === true;
      case 'lost-combat':
        return ctx.won === false;
      case 'first-lost-combat-this-turn':
        return ctx.won === false && ctx.firstLossThisTurn === true;
      // combat-only / turn-only условия вне after-attack контекста → no-op
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
