/**
 * Combat Resolver Service
 *
 * Разрешает боевые столкновения в Unmatched.
 * Вычисляет урон, применения эффектов карт и способностей героев.
 */

import { Injectable, Logger } from '@nestjs/common';
import { MetricsService } from '../../metrics/metrics.service';
import type { GameState, Fighter } from '../models';
import { HeroAbilityRegistry, type ValueModifier } from '../abilities/hero-ability-registry';

export interface CombatResult {
  readonly attackerDamage: number;
  readonly defenderDamage: number;
  readonly attackerEffectsApplied: readonly string[];
  readonly defenderEffectsApplied: readonly string[];
  readonly nextState: GameState;
}

@Injectable()
export class CombatResolverService {
  private readonly logger = new Logger(CombatResolverService.name);

  constructor(
    private readonly abilityRegistry: HeroAbilityRegistry,
    private readonly metrics: MetricsService,
  ) {}

  /**
   * Разрешить бой между атакующим и защитником
   */
  async resolveCombat(
    state: GameState,
    attackerId: string,
    defenderId: string,
    attackCardId: string,
    defenseCardId?: string,
  ): Promise<CombatResult> {
    return this.metrics.measureServiceDuration('resolveCombat', 'CombatResolver', async () => {
      // Получаем бойцов
      const attacker = state.fighters.find((f) => f.id === attackerId);
      const defender = state.fighters.find((f) => f.id === defenderId);

      if (!attacker || !defender) {
        this.logger.error(`Combat failed: attacker or defender not found`, { attackerId, defenderId });
        throw new Error('Invalid combat: fighter not found');
      }

      // Получаем модификаторы от способностей героев с замером времени
      const registryCombatState = {
        attackerId,
        defenderId,
        attackCardId,
        defenseCardId,
      };

      // Handlers зарегистрированы по слагам ('daredevil'), heroId — Prisma cuid:
      // без heroSlug lookup никогда не находил handler (способности были мертвы)
      const attackerModifiers = await this.metrics.measureServiceDuration(
        'applyCombatModifiers',
        'HeroAbilityRegistry',
        () => Promise.resolve(
          this.abilityRegistry.applyCombatModifiers(
            attacker.heroSlug ?? attacker.heroId,
            registryCombatState,
            attacker,
            'attacker',
          ),
        ),
      );

      const defenderModifiers = await this.metrics.measureServiceDuration(
        'applyCombatModifiers',
        'HeroAbilityRegistry',
        () => Promise.resolve(
          this.abilityRegistry.applyCombatModifiers(
            defender.heroSlug ?? defender.heroId,
            registryCombatState,
            defender,
            'defender',
          ),
        ),
      );

      // Вычисляем итоговые значения с кэшированием поиска карт
      const [baseAttackValue, baseDefenseValue] = await Promise.all([
        this.getCardAttackValueOptimized(state, attackCardId),
        defenseCardId ? this.getCardDefenseValueOptimized(state, defenseCardId) : Promise.resolve(0),
      ]);

      const attackModifier = this.sumValueModifiers(attackerModifiers);
      const defenseModifier = this.sumValueModifiers(defenderModifiers);

      const finalAttack = baseAttackValue + attackModifier;
      const finalDefense = baseDefenseValue + defenseModifier;

      // Вычисляем урон
      let attackerDamage = 0;
      let defenderDamage = 0;

      if (finalAttack > finalDefense) {
        defenderDamage = finalAttack - finalDefense;
      } else if (finalDefense > finalAttack) {
        attackerDamage = finalDefense - finalAttack;
      }

      // Структурированное логирование результата
      this.logger.debug(
        `Combat resolved: ${attacker.name} (${finalAttack}) vs ${defender.name} (${finalDefense}) -> ` +
          `Attacker DMG: ${attackerDamage}, Defender DMG: ${defenderDamage}`,
        {
          attackerId: attacker.id,
          defenderId: defender.id,
          attackerHero: attacker.heroId,
          defenderHero: defender.heroId,
          finalAttack,
          finalDefense,
          attackerDamage,
          defenderDamage,
        },
      );

      // Применяем урон к состоянию
      const nextState = this.applyDamage(state, attackerId, defenderId, attackerDamage, defenderDamage);

      return {
        attackerDamage,
        defenderDamage,
        attackerEffectsApplied: attackerModifiers.map(m => m.source),
        defenderEffectsApplied: defenderModifiers.map(m => m.source),
        nextState,
      };
    });
  }

  /**
   * Применяет урон к бойцам и возвращает обновлённое состояние
   */
  private applyDamage(
    state: GameState,
    attackerId: string,
    defenderId: string,
    attackerDamage: number,
    defenderDamage: number,
  ): GameState {
    const updatedFighters = state.fighters.map(fighter => {
      if (fighter.id === attackerId) {
        const newHealth = Math.max(0, fighter.health - attackerDamage);
        return {
          ...fighter,
          health: newHealth,
        };
      }
      if (fighter.id === defenderId) {
        const newHealth = Math.max(0, fighter.health - defenderDamage);
        return {
          ...fighter,
          health: newHealth,
        };
      }
      return fighter;
    });

    // Обновляем статус проигравших игроков
    const updatedPlayers = state.players.map(player => {
      const playerFighters = updatedFighters.filter(f => f.ownerId === player.userId);
      const allDefeated = playerFighters.every(f => f.health === 0);
      return {
        ...player,
        isAlive: !allDefeated,
      };
    });

    return {
      ...state,
      fighters: updatedFighters,
      players: updatedPlayers,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
        lastActionBy: attackerId,
      },
    };
  }

  /**
   * Проверяет условие окончания игры
   */
  checkGameOver(state: GameState): { isOver: boolean; winnerId?: string } {
    const alivePlayers = state.players.filter(p => p.isAlive);

    if (alivePlayers.length <= 1) {
      return {
        isOver: true,
        winnerId: alivePlayers[0]?.userId,
      };
    }

    return { isOver: false };
  }

  /**
   * Получить базовую силу атаки карты (оптимизировано)
   */
  private getCardAttackValue(state: GameState, cardId: string): number {
    // Ищем карту среди всех рук игроков
    for (const playerId of Object.keys(state.handZones)) {
      const hand = state.handZones[playerId];
      const card = hand.cards.find(c => c.id === cardId);
      if (card && card.attackValue !== undefined) {
        return card.attackValue;
      }
    }
    // Ищем в колодах
    for (const playerId of Object.keys(state.decks)) {
      const deck = state.decks[playerId];
      const card = deck.cards.find(c => c.id === cardId);
      if (card && card.attackValue !== undefined) {
        return card.attackValue;
      }
    }
    return 0;
  }

  /**
   * Получить базовую силу защиты карты (оптимизировано)
   */
  private getCardDefenseValue(state: GameState, cardId: string): number {
    // Ищем карту среди всех рук игроков
    for (const playerId of Object.keys(state.handZones)) {
      const hand = state.handZones[playerId];
      const card = hand.cards.find(c => c.id === cardId);
      if (card && card.defenseValue !== undefined) {
        return card.defenseValue;
      }
    }
    // Ищем в колодах
    for (const playerId of Object.keys(state.decks)) {
      const deck = state.decks[playerId];
      const card = deck.cards.find(c => c.id === cardId);
      if (card && card.defenseValue !== undefined) {
        return card.defenseValue;
      }
    }
    return 0;
  }

  /**
   * Оптимизированный поиск значения атаки карты с кэшем
   * Кэширует найденные карты для быстрого повторного доступа
   */
  private cardValueCache = new Map<string, { attackValue?: number; defenseValue?: number; timestamp: number }>();
  private readonly CACHE_TTL = 1000; // 1 секунда

  private async getCardAttackValueOptimized(state: GameState, cardId: string): Promise<number> {
    // Проверяем кэш
    const cached = this.cardValueCache.get(cardId);
    if (cached && Date.now() - cached.timestamp < this.CACHE_TTL) {
      if (cached.attackValue !== undefined) {
        return cached.attackValue;
      }
    }

    // Ищем значение
    const value = this.getCardAttackValue(state, cardId);

    // Обновляем кэш
    const existing = this.cardValueCache.get(cardId);
    this.cardValueCache.set(cardId, {
      ...existing,
      attackValue: value,
      timestamp: Date.now(),
    });

    return value;
  }

  /**
   * Оптимизированный поиск значения защиты карты с кэшем
   */
  private async getCardDefenseValueOptimized(state: GameState, cardId: string): Promise<number> {
    // Проверяем кэш
    const cached = this.cardValueCache.get(cardId);
    if (cached && Date.now() - cached.timestamp < this.CACHE_TTL) {
      if (cached.defenseValue !== undefined) {
        return cached.defenseValue;
      }
    }

    // Ищем значение
    const value = this.getCardDefenseValue(state, cardId);

    // Обновляем кэш
    const existing = this.cardValueCache.get(cardId);
    this.cardValueCache.set(cardId, {
      ...existing,
      defenseValue: value,
      timestamp: Date.now(),
    });

    return value;
  }

  /**
   * Очистить кэш значений карт
   */
  clearCardValueCache(): void {
    this.cardValueCache.clear();
  }

  /**
   * Инвалидировать устаревшие записи кэша
   */
  private cleanupCardValueCache(): void {
    const now = Date.now();
    for (const [key, value] of this.cardValueCache.entries()) {
      if (now - value.timestamp > this.CACHE_TTL) {
        this.cardValueCache.delete(key);
      }
    }
  }

  /**
   * Суммировать модификаторы значений
   */
  private sumValueModifiers(modifiers: readonly ValueModifier[]): number {
    return modifiers.reduce((sum, m) => {
      if (m.type === 'ADD') {
        return sum + m.value;
      }
      return sum;
    }, 0);
  }
}
