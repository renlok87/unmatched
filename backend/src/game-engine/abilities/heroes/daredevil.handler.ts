/**
 * Daredevil Hero Ability Handler
 *
 * Обработчик способности Daredevil: "Blind Boost"
 * Во время боя с 2 или менее картами в руке: может сбросить верхнюю карту колоды
 * и добавить её значение BOOST к атаке или защите.
 */

import { Injectable, Logger } from '@nestjs/common';
import type { GameState } from '../../models/game-state.model';
import type { Fighter } from '../../models/fighter.model';
import type { Card } from '../../models/card.model';
import {
  IHeroAbilityHandler,
  ExtendedCombatContext,
  AbilityChecker,
} from '../hero-ability.interface';
import type { CombatModifier } from '../hero-ability-registry';

/**
 * Результат Blind Boost
 */
export interface BlindBoostResult {
  readonly success: boolean;
  readonly boostValue: number;
  readonly discardedCard?: Card;
  readonly remainingDeck: readonly Card[];
}

/**
 * Максимальное количество карт в руке для активации Blind Boost
 */
const BLIND_BOOST_MAX_CARDS = 2;

/**
 * Обработчик способности Daredevil
 */
@Injectable()
export class DaredevilHandler implements IHeroAbilityHandler, AbilityChecker {
  private readonly logger = new Logger(DaredevilHandler.name);

  readonly heroId = 'daredevil';
  readonly abilityName = 'Blind Boost';
  readonly abilityDescription =
    'Во время боя с 2 или менее картами в руке: может сбросить верхнюю карту колоды и добавить её значение BOOST к атаке или защите.';

  /**
   * Проверить, может ли быть активирован Blind Boost
   * @param state Текущее состояние игры
   * @param playerId ID игрока
   * @param context Контекст боя
   * @returns true, если условие выполнено
   */
  canTrigger(state: GameState, playerId: string, context?: ExtendedCombatContext): boolean {
    // Проверяем, что это бой Daredevil
    if (context) {
      const player = state.players.find((p) => p.userId === playerId);
      if (!player || player.heroId !== this.heroId) {
        return false;
      }

      // Проверяем количество карт в руке
      const handZone = state.handZones[playerId];
      if (!handZone) {
        return false;
      }

      const cardCount = handZone.cards.length;
      if (cardCount > BLIND_BOOST_MAX_CARDS) {
        return false;
      }

      // Проверяем, что в колоде есть карты
      const deck = state.decks[playerId];
      if (!deck || deck.drawPile.length === 0) {
        return false;
      }

      return true;
    }

    return false;
  }

  /**
   * Проверить условие для боя
   * @param context Контекст боя
   */
  canTriggerInCombat(context: ExtendedCombatContext): boolean {
    return context.isBlindBoostAvailable;
  }

  /**
   * Получить BOOST значение с верхней карты колоды
   * Не сбрасывает карту, только возвращает значение
   * @param state Состояние игры
   * @param playerId ID игрока
   * @returns Значение BOOST верхней карты
   */
  getBoostValue(state: GameState, playerId: string): number {
    const deck = state.decks[playerId];
    if (!deck || deck.drawPile.length === 0) {
      this.logger.warn(`No cards in deck for player ${playerId}`);
      return 0;
    }

    const topCard = deck.drawPile[0];
    const boostValue = topCard.boostValue ?? 0;

    this.logger.debug(
      `Daredevil (${playerId}) blind boost value: ${boostValue} from ${topCard.name}`,
    );

    return boostValue;
  }

  /**
   * Получить верхнюю карту колоды (для превью)
   * @param state Состояние игры
   * @param playerId ID игрока
   * @returns Верхняя карта или undefined
   */
  peekTopCard(state: GameState, playerId: string): Card | undefined {
    const deck = state.decks[playerId];
    if (!deck || deck.drawPile.length === 0) {
      return undefined;
    }
    return deck.drawPile[0];
  }

  /**
   * Выполнить Blind Boost - сбросить верхнюю карту и получить значение
   * @param state Текущее состояние игры
   * @param playerId ID игрока
   * @param forAttack true для атаки, false для защиты
   * @returns Результат Blind Boost
   */
  executeBlindBoost(
    state: GameState,
    playerId: string,
    forAttack: boolean,
  ): BlindBoostResult {
    if (!this.canTrigger(state, playerId)) {
      return {
        success: false,
        boostValue: 0,
        remainingDeck: state.decks[playerId]?.drawPile ?? [],
      };
    }

    const deck = state.decks[playerId];
    if (!deck || deck.drawPile.length === 0) {
      return {
        success: false,
        boostValue: 0,
        remainingDeck: [],
      };
    }

    // Достаём верхнюю карту
    const topCard = deck.drawPile[0];
    const boostValue = topCard.boostValue ?? 0;

    // Новая колода без верхней карты
    const newDrawPile = deck.drawPile.slice(1);
    const remainingDeck = newDrawPile;

    this.logger.log(
      `Daredevil (${playerId}) executes Blind Boost for ${forAttack ? 'attack' : 'defense'}: ` +
        `discarded ${topCard.name}, got +${boostValue} boost`,
    );

    return {
      success: true,
      boostValue,
      discardedCard: topCard,
      remainingDeck,
    };
  }

  /**
   * Получить боевые модификаторы от способности
   * Blind Boost добавляет модификатор после сброса карты
   * @param context Контекст боя
   * @param fighter Боец
   * @param role Роль в бою
   * @returns Массив модификаторов
   */
  getCombatModifiers(
    context: ExtendedCombatContext,
    fighter: Fighter,
    role: 'attacker' | 'defender',
  ): readonly CombatModifier[] {
    // Blind Boost применяется только для Daredevil
    if (fighter.heroId !== this.heroId) {
      return [];
    }

    // Модификатор будет добавлен динамически при вызове executeBlindBoost
    // Здесь возвращаем пустой массив - фактическое значение будет передано через context
    return [];
  }

  /**
   * Обработать событие боя
   * Применяет Blind Boost если он был активирован
   * @param state Состояние игры
   * @param context Контекст боя
   * @returns Обновлённое состояние
   */
  async onCombat(state: GameState, context: ExtendedCombatContext): Promise<GameState> {
    // Blind Boost активируется через отдельный mutation, не здесь
    // Этот метод预留 для будущих расширений
    return state;
  }

  /**
   * Создать модификатор Blind Boost
   * @param boostValue Значение буста
   * @param forAttack Для атаки или защиты
   * @returns Модификатор
   */
  createBlindBoostModifier(boostValue: number, forAttack: boolean): CombatModifier {
    return {
      type: 'add',
      value: boostValue,
      source: `hero-ability-${this.heroId}-blind-boost`,
      appliesTo: forAttack ? 'attack' : 'defense',
    };
  }

  /**
   * Получить описание условия способности
   * @returns Описание условия
   */
  getConditionDescription(): string {
    return `Активируется когда в руке ${BLIND_BOOST_MAX_CARDS} или менее карт и в колоде есть карты.`;
  }
}

/**
 * Экспорт обработчика как singleton для использования в registry
 */
export const daredevilHandler = new DaredevilHandler();
