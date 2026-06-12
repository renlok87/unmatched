/**
 * Value Modifier Service
 *
 * Управляет модификаторами значений (урон, защита, радиус и т.д.).
 * Применяет модификаторы от карт, способностей и эффектов.
 */

import { Injectable, Logger } from '@nestjs/common';
import type { Fighter } from '../models';

export type ModifierType = 'attack' | 'defense' | 'damage' | 'range' | 'speed';
export type ModifierOperation = 'add' | 'multiply' | 'set' | 'min' | 'max';

export interface ValueModifier {
  readonly type: ModifierType;
  readonly operation: ModifierOperation;
  readonly value: number;
  readonly source: string;
  readonly expiresAt?: number;
}

export interface ModifierResult {
  readonly baseValue: number;
  readonly modifiedValue: number;
  readonly modifiers: readonly ValueModifier[];
}

@Injectable()
export class ValueModifierService {
  private readonly logger = new Logger(ValueModifierService.name);

  // Хранилище активных модификаторов
  private readonly fighterModifiers = new Map<string, ValueModifier[]>();

  /**
   * Применить модификаторы к базовому значению
   */
  applyModifiers(fighterId: string, type: ModifierType, baseValue: number): ModifierResult {
    const modifiers = this.fighterModifiers.get(fighterId) ?? [];
    const typeModifiers = modifiers.filter((m) => m.type === type);

    let modifiedValue = baseValue;

    // Сначала операции set
    for (const modifier of typeModifiers) {
      if (modifier.operation === 'set') {
        modifiedValue = modifier.value;
      }
    }

    // Затем операции multiply
    for (const modifier of typeModifiers) {
      if (modifier.operation === 'multiply') {
        modifiedValue *= modifier.value;
      }
    }

    // Затем операции add
    for (const modifier of typeModifiers) {
      if (modifier.operation === 'add') {
        modifiedValue += modifier.value;
      }
    }

    // Наконец операции min/max
    for (const modifier of typeModifiers) {
      if (modifier.operation === 'min') {
        modifiedValue = Math.min(modifiedValue, modifier.value);
      } else if (modifier.operation === 'max') {
        modifiedValue = Math.max(modifiedValue, modifier.value);
      }
    }

    return {
      baseValue,
      modifiedValue,
      modifiers: typeModifiers,
    };
  }

  /**
   * Добавить модификатор бойцу
   */
  addModifier(fighterId: string, modifier: ValueModifier): void {
    const current = this.fighterModifiers.get(fighterId) ?? [];
    this.fighterModifiers.set(fighterId, [...current, modifier]);

    this.logger.debug(
      `Added ${modifier.type} modifier to fighter ${fighterId}: ${modifier.operation} ${modifier.value}`,
    );
  }

  /**
   * Удалить модификатор
   */
  removeModifier(fighterId: string, modifierSource: string): void {
    const current = this.fighterModifiers.get(fighterId) ?? [];
    const filtered = current.filter((m) => m.source !== modifierSource);

    if (filtered.length < current.length) {
      this.fighterModifiers.set(fighterId, filtered);
    }
  }

  /**
   * Очистить все модификаторы бойца
   */
  clearModifiers(fighterId: string): void {
    this.fighterModifiers.delete(fighterId);
  }

  /**
   * Удалить истёкшие модификаторы
   */
  pruneExpiredModifiers(fighterId: string, now: number): void {
    const current = this.fighterModifiers.get(fighterId) ?? [];
    const active = current.filter((m) => !m.expiresAt || m.expiresAt > now);

    this.fighterModifiers.set(fighterId, active);
  }

  /**
   * Получить все модификаторы бойца
   */
  getModifiers(fighterId: string): readonly ValueModifier[] {
    return this.fighterModifiers.get(fighterId) ?? [];
  }

  /**
   * Создать модификатор
   */
  createModifier(
    type: ModifierType,
    operation: ModifierOperation,
    value: number,
    source: string,
    duration?: number,
  ): ValueModifier {
    return {
      type,
      operation,
      value,
      source,
      ...(duration ? { expiresAt: Date.now() + duration } : {}),
    };
  }

  // applyCardEffects удалён: был мёртвым стабом (возвращал state как есть);
  // эффекты карт исполняет CardEffectExecutorService (A3/A4)
}
