/**
 * Card Model
 *
 * Типы для карт в игре Unmatched
 */

/**
 * Тип карты
 */
export enum CardType {
  ATTACK = 'ATTACK',
  DEFENSE = 'DEFENSE',
  SCHEME = 'SCHEME',
  UNIVERSAL = 'UNIVERSAL',
  // Реальные значения Card.cardType из БД (см. prisma/seed-scraped.ts):
  // VERSATILE играется и как атака, и как защита (value в оба поля),
  // MANEUVER — карта движения (subType 'Movement')
  VERSATILE = 'VERSATILE',
  MANEUVER = 'MANEUVER',
}

/**
 * Базовый интерфейс карты
 */
export interface Card {
  readonly id: string;
  readonly cardId: string;
  readonly name: string;
  readonly nameEn: string;
  readonly nameRu: string;
  readonly cardType: CardType;
  readonly attackValue?: number;
  readonly defenseValue?: number;
  readonly boostValue?: number;
  readonly effects?: readonly CardEffect[];
  // Текст эффекта карты из БД (Card.text) — для отображения/ручного применения
  // в Game Tester при розыгрыше scheme-карт (авто-эффекты best-effort)
  readonly text?: string;
  /** Кто может играть карту: 'Any'/пусто — любой боец, иначе имя бойца
   *  ('Medusa', 'Harpy'). Валидация — bannerAllows в game-rules.validator */
  readonly bannerName?: string;
}

/**
 * Эффект карты.
 * Источник: Prisma Card.effects (Json) — заполняется парсером текстов
 * (effect-text-parser) и ручной правкой через админку (admin updateCard).
 * Все новые поля optional — обратная совместимость старых сейвов.
 */
export interface CardEffect {
  readonly id: string;
  readonly type: EffectType;
  readonly timing: EffectTiming;
  readonly target?: EffectTarget;
  readonly value?: number;
  /** Legacy-строковое условие ('low_health') — остаётся для старых данных */
  readonly condition?: string;
  /** Структурное условие применения */
  readonly when?: EffectCondition;
  /** Счётчик для VALUE_PER_COUNT / draw-per-damage */
  readonly count?: CountSpec;
  /** «You may …» — игрок может отказаться (MVP: авто-применение выгодных) */
  readonly optional?: boolean;
  /** Имя бойца для target NAMED_FIGHTER ('Dr. Watson') */
  readonly fighterName?: string;
  /** Откуда берётся BOOST-карта (для type BOOST) */
  readonly boostSource?: BoostSource;
  /** BLIND BOOST — карта вскрывается с верха колоды (Daredevil) */
  readonly blind?: boolean;
  /** Исходное предложение текста — для лога/manualEffects */
  readonly text?: string;
  /** Происхождение: парсер не перезаписывает manual при повторном backfill */
  readonly source?: 'parser' | 'manual';
  readonly parserVersion?: number;
}

/**
 * Структурное условие эффекта.
 * WON/LOST_COMBAT: атакующий выиграл при finalAttack > finalDefense,
 * ничья — за защитником (правило Unmatched).
 */
export type EffectConditionKind =
  | 'WON_COMBAT'
  | 'LOST_COMBAT'
  | 'IS_ATTACKING'
  | 'IS_DEFENDING'
  | 'ADJACENT_TO_OPPONENT'
  | 'NOT_ADJACENT_TO_OPPONENT'
  | 'DECK_EMPTY'
  | 'HAND_COUNT_AT_MOST'
  | 'HAND_COUNT_AT_LEAST'
  | 'HEALTH_AT_MOST'
  // «started this turn in a different space» (Momentous Shift и др.)
  | 'MOVED_THIS_TURN'
  | 'OPPONENT_IS_HERO'
  // зонные условия (C1, мультизонность): пересечение зон клеток бойцов
  | 'SHARES_ZONE_WITH_OPPONENT'
  | 'NOT_SHARES_ZONE_WITH_OPPONENT';

export interface EffectCondition {
  readonly kind: EffectConditionKind;
  readonly value?: number;
}

/**
 * Источник счётчика для VALUE_PER_COUNT и draw-per-damage
 */
export type CountSource =
  // «for each other friendly fighter adjacent to the opposing fighter»
  | 'FRIENDLY_ADJACENT_TO_OPPONENT'
  // «equal to the number of cards in your hand» (вместе с SET_VALUE 0)
  | 'CARDS_IN_HAND'
  // «for each other VOYAGE card in your discard pile» (namePrefix)
  | 'DISCARD_NAME_PREFIX'
  | 'DAMAGE_DEALT'
  | 'DAMAGE_TAKEN';

export interface CountSpec {
  readonly source: CountSource;
  readonly namePrefix?: string;
  /** Множитель за единицу счётчика (default 1) */
  readonly per?: number;
}

/**
 * Откуда берётся карта для BOOST
 */
export type BoostSource =
  // игрок сбрасывает карту из руки по выбору (передаётся boostCardId в мутации)
  | 'PLAYER_CHOICE_HAND'
  // верх своей колоды (BLIND BOOST — авто)
  | 'SELF_DECK_TOP'
  // случайная карта из руки оппонента («opponent discards 1 random card. Add its BOOST...»)
  | 'OPPONENT_RANDOM_HAND';

/**
 * Тип эффекта
 */
export enum EffectType {
  // legacy — остаются для старых данных
  MODIFY_ATTACK = 'MODIFY_ATTACK',
  MODIFY_DEFENSE = 'MODIFY_DEFENSE',
  DAMAGE = 'DAMAGE',
  HEAL = 'HEAL',
  MOVE = 'MOVE',
  PLACE = 'PLACE',
  DRAW_CARD = 'DRAW_CARD',
  DISCARD = 'DISCARD',
  // +N к значению СВОЕЙ карты; роль (атака/защита) решается в бою — для VERSATILE
  MODIFY_VALUE = 'MODIFY_VALUE',
  // «the value of this card is N instead»
  SET_VALUE = 'SET_VALUE',
  // +per за каждую сущность из count
  VALUE_PER_COUNT = 'VALUE_PER_COUNT',
  // добавить BOOST-значение карты из boostSource
  BOOST = 'BOOST',
  // «Cancel all effects on your opponent's card»
  CANCEL_EFFECTS = 'CANCEL_EFFECTS',
  OPPONENT_DISCARD = 'OPPONENT_DISCARD',
  // вернуть ЭТУ карту из сброса в руку
  RETURN_TO_HAND = 'RETURN_TO_HAND',
  // «cannot leave their space this turn»
  IMMOBILIZE = 'IMMOBILIZE',
  GAIN_ACTION = 'GAIN_ACTION',
  // «Prevent all damage»
  PREVENT_DAMAGE = 'PREVENT_DAMAGE',
  END_TURN = 'END_TURN',
  // маркер нераспознанного текста: не исполняется, едет в manualEffects + warn
  UNSUPPORTED = 'UNSUPPORTED',
}

/**
 * Время применения эффекта
 */
export enum EffectTiming {
  BEFORE_COMBAT = 'BEFORE_COMBAT',
  DURING_COMBAT = 'DURING_COMBAT',
  AFTER_COMBAT = 'AFTER_COMBAT',
  ON_PLAY = 'ON_PLAY',
  ON_DISCARD = 'ON_DISCARD',
  TURN_START = 'TURN_START',
  TURN_END = 'TURN_END',
  // effectImmediately — при вскрытии карт в COMBAT_RESOLVE (до during)
  ON_REVEAL = 'ON_REVEAL',
}

/**
 * Цель эффекта
 */
export enum EffectTarget {
  ATTACKER = 'ATTACKER',
  DEFENDER = 'DEFENDER',
  SELF = 'SELF',
  ALL_ENEMIES = 'ALL_ENEMIES',
  ALL_ALLIES = 'ALL_ALLIES',
  // противник в текущем бою
  OPPOSING_FIGHTER = 'OPPOSING_FIGHTER',
  // «each opposing fighter adjacent to your fighter»
  ENEMIES_ADJACENT_TO_SELF = 'ENEMIES_ADJACENT_TO_SELF',
  // один смежный враг (MVP: первый валидный + warn, до pendingEffects)
  ADJACENT_ENEMY = 'ADJACENT_ENEMY',
  // «Move Daredevil…» / «Dr. Watson recovers…» — по fighterName
  NAMED_FIGHTER = 'NAMED_FIGHTER',
  // игрок-оппонент (для OPPONENT_DISCARD)
  OPPONENT_PLAYER = 'OPPONENT_PLAYER',
}

/**
 * Нормализация Prisma Card.effects (Json) → CardEffect[].
 * Никогда не бросает: валидный массив → как есть (с дефолтом id),
 * строка с двойной сериализацией → повторный parse,
 * любой мусор → один UNSUPPORTED-эффект с сырым текстом.
 */
export function normalizeCardEffects(raw: unknown, cardId: string): CardEffect[] {
  if (raw == null) return [];
  let value: unknown = raw;
  if (typeof value === 'string') {
    const s = value.trim();
    if (s === '' || s === '[]' || s === 'null') return [];
    try {
      value = JSON.parse(s);
    } catch {
      return [unsupportedEffect(cardId, s)];
    }
  }
  if (!Array.isArray(value)) {
    // одиночный объект-эффект тоже принимаем
    if (typeof value === 'object') value = [value];
    else return [unsupportedEffect(cardId, String(value))];
  }
  return (value as unknown[]).flatMap((e, i) => {
    if (e == null || typeof e !== 'object') {
      return [unsupportedEffect(`${cardId}-${i}`, String(e))];
    }
    const eff = e as Record<string, unknown>;
    if (typeof eff.type !== 'string' || typeof eff.timing !== 'string') {
      return [unsupportedEffect(`${cardId}-${i}`, JSON.stringify(eff))];
    }
    return [
      {
        ...(eff as object),
        id: typeof eff.id === 'string' ? eff.id : `${cardId}-e${i}`,
        type: (Object.values(EffectType) as string[]).includes(eff.type)
          ? (eff.type as EffectType)
          : EffectType.UNSUPPORTED,
        timing: (Object.values(EffectTiming) as string[]).includes(eff.timing)
          ? (eff.timing as EffectTiming)
          : EffectTiming.AFTER_COMBAT,
      } as CardEffect,
    ];
  });
}

function unsupportedEffect(id: string, text: string): CardEffect {
  return {
    id: `${id}-unsupported`,
    type: EffectType.UNSUPPORTED,
    timing: EffectTiming.AFTER_COMBAT,
    text,
  };
}

/**
 * Карта в руке (с видимостью)
 */
export interface HandCard extends Card {
  readonly isVisible: boolean;
}

/**
 * Состояние колоды
 */
export interface DeckState {
  readonly cards: readonly Card[];
  readonly drawPile: readonly Card[];
  readonly topCard?: Card;
}

/**
 * Зона руки
 */
export interface HandZone {
  readonly cards: readonly HandCard[];
  readonly maxSize: number;
}
