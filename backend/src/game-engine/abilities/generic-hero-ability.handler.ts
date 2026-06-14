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
  AuraCombatModifierEffect,
  CombatModifierEffect,
  CombatModifierPerCountEffect,
  CycleStanceEffect,
  DiscardRandomEffect,
  PendingMoveEffect,
  ReactiveDamageEffect,
  SetStanceEffect,
  StanceConfig,
  TurnDamageEffect,
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
  /**
   * Зоны/смежность (AdjacencyService). Модуль передаёт сюда весь
   * AdjacencyService, поэтому достаточно объявить нужные методы:
   *  - isInSameZone    — для 'no-enemy-in-own-zone' и turn-damage 'enemy-in-zone'
   *  - manhattanDistance — для turn-damage 'enemy-adjacent' (смежность == 1)
   */
  readonly zone: {
    isInSameZone(
      state: { boardState: BoardState },
      a: { x: number; y: number },
      b: { x: number; y: number },
    ): boolean;
    manhattanDistance(a: { x: number; y: number }, b: { x: number; y: number }): number;
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
  /** Стойки героя (STANCE); пусто, если герой не stance-aware. */
  private readonly stances: readonly StanceConfig[];

  constructor(
    private readonly config: AbilityConfig,
    private readonly deps: GenericHeroAbilityDeps,
  ) {
    this.heroId = config.heroId;
    this.abilityName = config.abilityName;
    this.abilityDescription = config.description;
    this.rules = config.rules;
    this.stances = config.stances ?? [];
  }

  // ===================== STANCE (общее) =====================

  /** Список id стоек героя (для валидации setStance в executor'е). Пусто, если
   *  герой не stance-aware. */
  getStanceIds(): readonly string[] {
    return this.stances.map((s) => s.id);
  }

  /** Стойка по умолчанию: помеченная default:true, иначе первая. undefined для
   *  не-stance героев. */
  private defaultStanceId(): string | undefined {
    if (this.stances.length === 0) return undefined;
    return (this.stances.find((s) => s.default) ?? this.stances[0]).id;
  }

  /** Текущая стойка героя владельца: metadata.heroStances[ownerId] с фолбэком на
   *  дефолтную. undefined для не-stance героев или неизвестного владельца. */
  private currentStanceId(state: GameState, ownerId: string): string | undefined {
    const explicit = state.metadata.heroStances?.[ownerId];
    if (explicit !== undefined) return explicit;
    return this.defaultStanceId();
  }

  /** StanceConfig текущей стойки владельца (или undefined). */
  private currentStance(state: GameState, ownerId: string): StanceConfig | undefined {
    const id = this.currentStanceId(state, ownerId);
    return id !== undefined ? this.stances.find((s) => s.id === id) : undefined;
  }

  /**
   * Иммутабельно ставит стойку героя игрока в metadata.heroStances[playerId].
   * Поддерживает явный id и 'toggle' (другая стойка для 2-стоечных; при >2 —
   * следующая по циклу). Неизвестный id / отсутствие стоек → no-op (тот же state).
   */
  private setStanceForPlayer(state: GameState, playerId: string, to: string): GameState {
    if (this.stances.length === 0) return state;

    let targetId: string | undefined;
    if (to === 'toggle') {
      const cur = this.currentStanceId(state, playerId);
      const idx = this.stances.findIndex((s) => s.id === cur);
      const base = idx >= 0 ? idx : 0;
      targetId = this.stances[(base + 1) % this.stances.length].id;
    } else {
      targetId = this.stances.find((s) => s.id === to)?.id;
    }
    if (targetId === undefined) return state; // неизвестная стойка → no-op

    return {
      ...state,
      metadata: {
        ...state.metadata,
        heroStances: {
          ...(state.metadata.heroStances ?? {}),
          [playerId]: targetId,
        },
      },
    };
  }

  /** Продвинуть стойку героя игрока на следующую по циклу (wrap). No-op для
   *  не-stance героев. */
  private cycleStanceForPlayer(state: GameState, playerId: string): GameState {
    if (this.stances.length === 0) return state;
    const cur = this.currentStanceId(state, playerId);
    const idx = this.stances.findIndex((s) => s.id === cur);
    const base = idx >= 0 ? idx : 0;
    const nextId = this.stances[(base + 1) % this.stances.length].id;
    return {
      ...state,
      metadata: {
        ...state.metadata,
        heroStances: { ...(state.metadata.heroStances ?? {}), [playerId]: nextId },
      },
    };
  }

  /** Правило АКТИВНО по стойке: либо whenStance не задан, либо равен текущей
   *  стойке владельца. */
  private stanceRuleActive(rule: AbilityRule, state: GameState, ownerId: string): boolean {
    if (rule.whenStance === undefined) return true;
    return this.currentStanceId(state, ownerId) === rule.whenStance;
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

    // STANCE: combat-modifier текущей стойки (StanceConfig.combat) — выдаётся
    // независимо от правил, пока стойка текущая. Сторона гейтится appliesTo.
    const stance = this.currentStance(state, fighter.ownerId);
    if (stance?.combat && this.sideMatchesRole(stance.combat.appliesTo, role)) {
      modifiers.push({
        type: ValueModifierType.ADD,
        value: stance.combat.value,
        source: `hero-ability:${this.heroId}:${this.abilityName}:stance:${stance.id}`,
        ownerId: fighter.ownerId,
        timestamp: Date.now(),
      });
    }

    for (const rule of this.rules) {
      if (rule.trigger !== 'combat-passive') continue;
      // STANCE: правило с whenStance активно только в своей стойке.
      if (!this.stanceRuleActive(rule, state, fighter.ownerId)) continue;

      // --- Статический combat-modifier (фиксированное value) ---
      if (rule.effect.kind === 'combat-modifier') {
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
        continue;
      }

      // --- Динамический combat-modifier-per-count (value = valuePer * count) ---
      if (rule.effect.kind === 'combat-modifier-per-count') {
        const effect = rule.effect as CombatModifierPerCountEffect;

        // Сторона и условие гейтятся так же, как у статического модификатора.
        if (!this.sideMatchesRole(effect.appliesTo, role)) continue;
        if (!this.evalCombatCondition(rule.condition ?? 'always', state, context, fighter, role)) {
          continue;
        }

        const count = this.evalCombatCount(effect.countOf, state, context, fighter);
        const value = effect.valuePer * count;
        // Нулевой бонус не порождает ValueModifier (count === 0 → no-op).
        if (value === 0) continue;

        modifiers.push({
          type: ValueModifierType.ADD,
          value,
          source: `hero-ability:${this.heroId}:${this.abilityName}`,
          ownerId: fighter.ownerId,
          timestamp: Date.now(),
        });
        continue;
      }
    }

    return modifiers;
  }

  /**
   * Подсчёт для combat-modifier-per-count. Резолвит бойца-защитника боя как
   * state.fighters[targetFighterId ?? defenderId] (см. CombatState: защитник-боец
   * лежит в targetFighterId, defenderId — id ИГРОКА-защитника; фолбэк на
   * defenderId — на случай caller'а, передающего id бойца напрямую). Если боец
   * не найден — возвращает 0 (модификатор не выдаётся).
   *
   * 'own-fighters-adjacent-to-defender-excl-self' — число бойцов владельца
   * (fighter.ownerId), НЕ повергнутых, ИСКЛЮЧАЯ самого бойца, смежных с
   * защитником (deps.zone.manhattanDistance(pos, defenderPos) === 1).
   */
  private evalCombatCount(
    countOf: CombatModifierPerCountEffect['countOf'],
    state: GameState,
    context: CombatState,
    fighter: Fighter,
  ): number {
    const defenderFighterId = context.targetFighterId ?? context.defenderId;
    const defender = state.fighters.find((f) => f.id === defenderFighterId);
    if (!defender) return 0;

    switch (countOf) {
      case 'own-fighters-adjacent-to-defender-excl-self':
        return state.fighters.filter(
          (f) =>
            f.ownerId === fighter.ownerId && // только свои
            f.id !== fighter.id && // excl-self
            f.isDefeated !== true && // живые
            this.deps.zone.manhattanDistance(f.position, defender.position) === 1, // смежные
        ).length;
      default:
        return 0;
    }
  }

  // ===================== AURA (combat-modifier от ДРУГОГО героя) =====================

  /**
   * АУРНЫЕ боевые модификаторы (Oda-style). В отличие от
   * getStatefulCombatModifiers (который консультирует own-handler КОНКРЕТНОГО
   * бойца боя), этот хук вызывается реестром для КАЖДОГО зарегистрированного
   * героя с бойцом-БЕНЕФИЦИАРОМ: если ЭТОТ handler — герой-гранитель ауры, и
   * beneficiary удовлетворяет условиям ауры, он получает ADD-модификатор во
   * время СВОЕГО боя.
   *
   * Для каждого 'combat-passive' правила с effect.kind === 'aura-combat-modifier':
   *  - находим HERO-бойца ЭТОГО handler'а (FighterType.HERO, ownerId ===
   *    beneficiary.ownerId, heroSlug === this.heroId) — герой-гранитель;
   *  - требуем: гранитель существует, жив (!isDefeated);
   *  - beneficiary.id !== granterHeroFighter.id (гранитель НЕ баффает сам себя);
   *  - beneficiary.ownerId === ownerId гранителя (только СВОИ — гарантировано
   *    выбором гранителя по beneficiary.ownerId, но проверяем явно);
   *  - deps.zone.isInSameZone(state, granterPos, beneficiaryPos) (общая зона);
   *  - appliesTo совпадает с ролью бенефициара (sideMatchesRole; 'both' — всегда).
   * При выполнении всех условий — ADD value (НЕ использует контекст защитника
   * боя; баффает именно бойца-бенефициара). Иначе — пусто (чистый no-op).
   */
  getAuraCombatModifiers(
    state: GameState,
    beneficiary: Fighter,
    role: 'attacker' | 'defender',
  ): readonly ValueModifier[] {
    const modifiers: ValueModifier[] = [];

    for (const rule of this.rules) {
      if (rule.trigger !== 'combat-passive') continue;
      if (rule.effect.kind !== 'aura-combat-modifier') continue;

      const effect = rule.effect as AuraCombatModifierEffect;

      // Сторона боя бенефициара ('both' — всегда).
      if (!this.sideMatchesRole(effect.appliesTo, role)) continue;

      // Герой-гранитель ауры = HERO-боец ЭТОГО handler'а у владельца бенефициара.
      const granter = state.fighters.find(
        (f) =>
          f.type === FighterType.HERO &&
          f.ownerId === beneficiary.ownerId &&
          f.heroSlug === this.heroId,
      );
      // Гранитель должен существовать и быть живым.
      if (!granter || granter.isDefeated === true) continue;
      // Гранитель НЕ баффает сам себя.
      if (beneficiary.id === granter.id) continue;
      // Только СВОИ бойцы (явная проверка, хотя granter уже выбран по ownerId).
      if (beneficiary.ownerId !== granter.ownerId) continue;
      // scope 'allies-in-my-zone' — бенефициар делит зону гранителя.
      if (effect.scope === 'allies-in-my-zone') {
        if (!this.deps.zone.isInSameZone(state, granter.position, beneficiary.position)) {
          continue;
        }
      } else {
        continue;
      }

      modifiers.push({
        type: ValueModifierType.ADD,
        value: effect.value,
        source: `hero-ability:${this.heroId}:${this.abilityName}`,
        ownerId: beneficiary.ownerId,
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
      if (
        rule.effect.kind !== 'turn-effect' &&
        rule.effect.kind !== 'pending-move' &&
        rule.effect.kind !== 'set-stance'
      ) {
        continue;
      }

      if (!this.evalAfterCombatCondition(rule.condition ?? 'always', ctx, current)) {
        continue;
      }

      // Цель эффекта: атакующий для 'after-attack', защитник для 'after-defense'.
      const targetPlayerId =
        rule.trigger === 'after-defense' ? ctx.defenderPlayerId : ctx.playerId;
      // 'after-defense' без известного защитника — нечего применять (no-op).
      if (!targetPlayerId) continue;

      // STANCE: правило с whenStance активно только в своей стойке цели.
      if (!this.stanceRuleActive(rule, current, targetPlayerId)) continue;

      if (rule.effect.kind === 'pending-move') {
        current = this.applyPendingMove(current, targetPlayerId, rule.effect, ctx);
        continue;
      }

      if (rule.effect.kind === 'set-stance') {
        // Авто-флип/смена стойки (Muhammad Ali: флип после выигранной атаки).
        current = this.setStanceForPlayer(
          current,
          targetPlayerId,
          (rule.effect as SetStanceEffect).to,
        );
        continue;
      }

      current = await this.applyTurnEffect(current, targetPlayerId, rule.effect as TurnEffect);
    }

    return current;
  }

  // ===================== ON-DEFEAT (РЕАНИМИРОВАННЫЙ on-defeat хук) =====================

  /**
   * Реакция на гибель бойца (триггер 'sidekick-defeated'). Дёргается executor'ом
   * для героя ВЛАДЕЛЬЦА повергнутого бойца ПОСЛЕ установки isDefeated.
   *
   * Для правил trigger === 'sidekick-defeated' с effect.kind === 'discard-random':
   * срабатывает ТОЛЬКО если defeatedFighter — НЕ-HERO боец владельца ЭТОГО героя
   * (т.е. наш сайдкик). Тогда иммутабельно сбрасывает count карт из руки владельца
   * (детерминированно — первые count; уходят в discardPile, если он есть).
   * Чистый no-op (тот же state) во всех прочих случаях: чужой/HERO-боец, нет
   * 'sidekick-defeated' правила, пустая рука.
   */
  async onFighterDefeated(state: GameState, defeatedFighter: Fighter): Promise<GameState> {
    let current = state;

    for (const rule of this.rules) {
      if (rule.trigger !== 'sidekick-defeated') continue;
      if (rule.effect.kind !== 'discard-random') continue;

      // Реагируем только на гибель СВОЕГО сайдкика (НЕ-HERO боец нашего владельца).
      if (defeatedFighter.type === FighterType.HERO) continue;
      const granter = this.findHeroFighter(current, defeatedFighter.ownerId);
      // Боец-владелец должен иметь HERO-бойца ИМЕННО ЭТОГО героя (слаг совпадает).
      if (!granter || (granter.heroSlug ?? granter.heroId) !== this.heroId) continue;

      current = this.discardCardsFromHand(
        current,
        defeatedFighter.ownerId,
        (rule.effect as DiscardRandomEffect).count,
      );
    }

    return current;
  }

  // ===================== ON-MOVE (РЕАКТИВНЫЙ on-move хук) =====================

  /**
   * РЕАКТИВНЫЙ on-move хук (Tomoe-style). Дёргается executor'ом для КАЖДОГО
   * зарегистрированного героя проходом по диффу позиций ПОСЛЕ перемещения
   * (реагирующий герой ОТЛИЧЕН от двигающегося — кросс-героевый реактив).
   *
   * Для правил trigger === 'enemy-hero-left-my-zone' с effect.kind ===
   * 'reactive-damage':
   *  - находим HERO-бойца ЭТОГО handler'а (FighterType.HERO, heroSlug ===
   *    this.heroId) — герой-реактор; требуем: существует И жив (!isDefeated);
   *  - реагируем ТОЛЬКО если сдвинувшийся боец:
   *      • вражеский (movedFighter.ownerId !== реактор.ownerId),
   *      • это HERO (movedFighter.type === FighterType.HERO — «opposing hero»),
   *      • БЫЛ в зоне реактора (deps.zone.isInSameZone(state, реакторPos, fromPos)),
   *      • ПОКИНУЛ её (deps.zone.isInSameZone(state, реакторPos, toPos) === false);
   *  - тогда наносим value урона movedFighter иммутабельно (health = max(0,
   *    health - value); при 0 → isDefeated + пересчёт isAlive владельца).
   * Game-over здесь НЕ ставим — WIRE recheck (applyMoveReactions) пере-проверит.
   * Чистый no-op (тот же объект state) во всех прочих случаях.
   */
  async onFighterMoved(
    state: GameState,
    movedFighter: Fighter,
    fromPos: { x: number; y: number },
    toPos: { x: number; y: number },
  ): Promise<GameState> {
    let current = state;

    for (const rule of this.rules) {
      if (rule.trigger !== 'enemy-hero-left-my-zone') continue;
      if (rule.effect.kind !== 'reactive-damage') continue;

      // Сдвинувшийся боец должен быть вражеским HERO («opposing hero»).
      if (movedFighter.type !== FighterType.HERO) continue;

      // Герой-реактор = HERO-боец ЭТОГО handler'а (по слагу). Должен существовать и жить.
      const reactor = current.fighters.find(
        (f) => f.type === FighterType.HERO && (f.heroSlug ?? f.heroId) === this.heroId,
      );
      if (!reactor || reactor.isDefeated === true) continue;

      // Вражеский: владелец сдвинувшегося != владельцу реактора.
      if (movedFighter.ownerId === reactor.ownerId) continue;

      // БЫЛ в зоне реактора (fromPos) И ПОКИНУЛ её (toPos вне зоны).
      const wasInZone = this.deps.zone.isInSameZone(current, reactor.position, fromPos);
      const stillInZone = this.deps.zone.isInSameZone(current, reactor.position, toPos);
      if (!wasInZone || stillInZone) continue;

      current = this.applyReactiveDamage(
        current,
        movedFighter.id,
        (rule.effect as ReactiveDamageEffect).value,
      );
    }

    return current;
  }

  /**
   * Иммутабельно наносит `value` урона бойцу `targetId` (зеркалит turn-damage):
   * health = max(0, health - value); при 0 ставит isDefeated и пересчитывает
   * isAlive владельца по обновлённым fighters. Game-over НЕ ставит. Если боец не
   * найден — чистый no-op (тот же объект state).
   */
  private applyReactiveDamage(state: GameState, targetId: string, value: number): GameState {
    const target = state.fighters.find((f) => f.id === targetId);
    if (!target) return state;

    const newHealth = Math.max(0, target.health - value);
    const becomesDefeated = newHealth === 0;

    let current: GameState = {
      ...state,
      fighters: state.fighters.map((f) =>
        f.id === target.id
          ? { ...f, health: newHealth, ...(becomesDefeated ? { isDefeated: true } : {}) }
          : f,
      ),
    };

    if (becomesDefeated) {
      const ownerStillAlive = current.fighters.some(
        (f) => f.ownerId === target.ownerId && f.isDefeated !== true,
      );
      current = {
        ...current,
        players: current.players.map((p) =>
          p.userId === target.ownerId ? { ...p, isAlive: ownerStillAlive } : p,
        ),
      };
    }

    return current;
  }

  /**
   * Иммутабельно сбрасывает первые `count` карт из руки игрока (детерминированный
   * стенд-ин для «random»). Карты уходят в discardPiles[playerId] (если структура
   * есть), иначе просто удаляются из руки. Пустая рука / count<=0 → чистый no-op
   * (тот же объект state).
   */
  private discardCardsFromHand(
    state: GameState,
    playerId: string,
    count: number,
  ): GameState {
    if (count <= 0) return state;

    const hand = state.handZones[playerId];
    const cards = hand?.cards ?? [];
    if (cards.length === 0) return state;

    const toDiscard = cards.slice(0, count);
    const remaining = cards.slice(toDiscard.length);

    const newState: GameState = {
      ...state,
      handZones: {
        ...state.handZones,
        [playerId]: { ...hand, cards: remaining },
      },
    };

    // discardPiles может отсутствовать у легаси-состояний — пишем только если
    // структура присутствует (move to discard pile if one exists).
    if (state.discardPiles) {
      const currentDiscard = state.discardPiles[playerId] ?? [];
      return {
        ...newState,
        discardPiles: {
          ...state.discardPiles,
          [playerId]: [...currentDiscard, ...toDiscard.map((c) => ({ ...c, isVisible: false }))],
        },
      };
    }

    return newState;
  }

  // ===================== ПАССИВНАЯ ДАЛЬНОСТЬ АТАКИ =====================

  /**
   * Пассивная дальность атаки (декларативный config.attackRange). Реестр
   * диспетчеризует этот хук в executeAttack как ADDITIVE-only: он может
   * РАЗРЕШИТЬ дальнюю атаку (range <= attackRange), но НИКОГДА не запрещает
   * обычную (melee/ranged) — те гейты остаются в силе.
   *
   * Семантика: true ⟺ config.attackRange задан И range не превышает его.
   * Если attackRange не задан — всегда false (хук не влияет на бой).
   * attackerId/defenderId не используются (дальность — пассивное свойство
   * героя, не зависит от конкретной пары бойцов), но входят в сигнатуру
   * ExtendedHeroAbilityHandler.canAttackAtRange.
   *
   * STANCE: опциональный 4-й параметр stance — id ТЕКУЩЕЙ стойки атакующего
   * (executor резолвит его из metadata.heroStances). Если у стойки задан
   * attackRange (Ali FLOAT: 2) — используем ЕГО (стойка переопределяет базу);
   * иначе фолбэк на config.attackRange. Если stance не передан (легаси-вызовы
   * с 3 аргументами) — берётся дефолтная стойка героя (или config.attackRange
   * для не-stance героев). У стойки без attackRange (Ali STING) дальняя атака
   * запрещена, ЕСЛИ нет базового config.attackRange.
   */
  canAttackAtRange(
    _attackerId: string,
    _defenderId: string,
    range: number,
    stance?: string,
  ): boolean {
    const stanceId = stance ?? this.defaultStanceId();
    const stanceCfg =
      stanceId !== undefined ? this.stances.find((s) => s.id === stanceId) : undefined;
    const effectiveRange = stanceCfg?.attackRange ?? this.config.attackRange;
    return effectiveRange != null && range <= effectiveRange;
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
      if (
        rule.effect.kind !== 'turn-effect' &&
        rule.effect.kind !== 'pending-move' &&
        rule.effect.kind !== 'turn-damage' &&
        rule.effect.kind !== 'set-stance' &&
        rule.effect.kind !== 'cycle-stance'
      ) {
        continue;
      }

      if (!this.evalTurnCondition(rule.condition ?? 'always', current, playerId)) {
        continue;
      }

      // STANCE: правило с whenStance активно только в своей стойке.
      if (!this.stanceRuleActive(rule, current, playerId)) continue;

      if (rule.effect.kind === 'pending-move') {
        // turn-контекст не несёт боя → target 'attacker' здесь невалиден (no-op).
        current = this.applyPendingMove(current, playerId, rule.effect);
        continue;
      }

      if (rule.effect.kind === 'turn-damage') {
        current = await this.applyTurnDamage(current, playerId, rule.effect);
        continue;
      }

      if (rule.effect.kind === 'set-stance') {
        current = this.setStanceForPlayer(current, playerId, (rule.effect as SetStanceEffect).to);
        continue;
      }

      if (rule.effect.kind === 'cycle-stance') {
        // Авто-цикл стоек (будущий Moon Knight: 3-стоечный цикл в конце хода).
        const _cycle = rule.effect as CycleStanceEffect;
        void _cycle;
        current = this.cycleStanceForPlayer(current, playerId);
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
   * Применяет turn-damage: авто-выбирает ПЕРВОГО подходящего вражеского бойца
   * (по targetScope) и иммутабельно наносит ему value урона. При летальном
   * исходе помечает бойца isDefeated и пересчитывает isAlive его владельца.
   * После успешного попадания (опц.) добирает thenDraw карт действующему игроку.
   *
   * MVP: auto-target первого кандидата — без выбора цели / opt-out игроком.
   * Game-over здесь НЕ ставится (это делает WIRE recheck в advanceTurn); seq
   * не бампится. Нет цели → чистый no-op (тот же state, без добора).
   */
  private async applyTurnDamage(
    state: GameState,
    playerId: string,
    effect: TurnDamageEffect,
  ): Promise<GameState> {
    const hero = this.findHeroFighter(state, playerId);
    if (!hero) return state;

    // Первый подходящий враг в порядке state.fighters.
    const target = state.fighters.find((f) => {
      if (f.ownerId === playerId) return false; // только вражеские
      if (f.isDefeated === true) return false; // живые
      if (effect.targetScope === 'enemy-in-zone') {
        return this.deps.zone.isInSameZone(state, hero.position, f.position);
      }
      // 'enemy-adjacent' — смежность (Manhattan distance === 1)
      return this.deps.zone.manhattanDistance(hero.position, f.position) === 1;
    });

    if (!target) return state; // нет цели → no-op (без добора)

    const newHealth = Math.max(0, target.health - effect.value);
    const becomesDefeated = newHealth === 0;

    let current: GameState = {
      ...state,
      fighters: state.fighters.map((f) =>
        f.id === target.id
          ? { ...f, health: newHealth, ...(becomesDefeated ? { isDefeated: true } : {}) }
          : f,
      ),
    };

    // Пересчёт isAlive владельца повергнутого бойца (по обновлённым fighters).
    if (becomesDefeated) {
      const ownerStillAlive = current.fighters.some(
        (f) => f.ownerId === target.ownerId && f.isDefeated !== true,
      );
      current = {
        ...current,
        players: current.players.map((p) =>
          p.userId === target.ownerId ? { ...p, isAlive: ownerStillAlive } : p,
        ),
      };
    }

    // thenDraw — только после реального попадания.
    if (typeof effect.thenDraw === 'number' && effect.thenDraw > 0) {
      current = await this.deps.deck.drawCards(current, playerId, effect.thenDraw);
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
        // combatInfo.defenderId — id ИГРОКА-защитника; боец-защитник лежит в
        // targetFighterId (атака по сайдкику ранит сайдкика). Фолбэк на
        // defenderId — на случай caller'а, передающего id бойца напрямую.
        const defenderFighterId = context.targetFighterId ?? context.defenderId;
        const defender = state.fighters.find((f) => f.id === defenderFighterId);
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
   * Условия after-attack правил. Оцениваются против исхода боя (+ при компаунд-
   * условии — против GameState):
   *  - 'always'                      → всегда
   *  - 'won-combat'                  → ctx.won === true
   *  - 'lost-combat'                 → ctx.won === false
   *  - 'first-lost-combat-this-turn' → ctx.won === false && ctx.firstLossThisTurn
   *  - 'won-combat-and-all-sidekicks-defeated' → ctx.won === true И все сайдкики
   *    действующего героя (ctx.playerId) повержены (allOwnSidekicksDefeated).
   * Любое иное условие (боевое/ходовое/{handSizeEquals}) для after-attack не
   * валидно и безопасно игнорируется (правило не срабатывает).
   */
  private evalAfterCombatCondition(
    condition: AbilityCondition,
    ctx: AfterCombatContext,
    state: GameState,
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
      case 'won-combat-and-all-sidekicks-defeated':
        return ctx.won === true && this.allOwnSidekicksDefeated(state, ctx.playerId);
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
