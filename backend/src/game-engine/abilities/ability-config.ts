/**
 * Ability Config — декларативное описание способностей героев
 *
 * Data-driven фреймворк: вместо отдельного handler-класса на каждого героя
 * способность описывается набором правил (AbilityRule). GenericHeroAbilityHandler
 * интерпретирует эти правила против GameState.
 *
 * Сейчас ABILITY_CONFIGS пуст — конкретные герои добавляются в следующей фазе.
 */

/**
 * Когда срабатывает правило способности.
 *  - 'combat-passive' — пассивный модификатор атаки/защиты во время боя
 *  - 'turn-start'     — эффект в начале хода игрока
 *  - 'turn-end'       — эффект в конце хода игрока
 */
export type AbilityTrigger = 'combat-passive' | 'turn-start' | 'turn-end';

/**
 * Условие срабатывания правила (декларативное, проверяется против GameState).
 *
 * Строковые условия — для простых случаев; объектные — для параметризованных.
 * Дизайн с union'ом подобран так, чтобы добавление новых условий было дешёвым:
 * новый литерал/объект + ветка в evaluate-функции хендлера.
 *
 *  - 'always'                      — всегда истинно (условие можно опустить)
 *  - 'attacking'                   — боец является атакующим в текущем бою
 *  - 'defending'                   — боец является защищающимся в текущем бою
 *  - 'self-health-below-defender'  — health бойца < health защитника боя
 *  - 'all-own-sidekicks-defeated'  — все НЕ-герои владельца повержены
 *  - { handSizeEquals: N }         — в руке игрока ровно N карт
 *  - 'no-enemy-in-own-zone'        — в зоне героя игрока нет вражеских бойцов
 */
export type AbilityCondition =
  | 'always'
  | 'attacking'
  | 'defending'
  | 'self-health-below-defender'
  | 'all-own-sidekicks-defeated'
  | 'no-enemy-in-own-zone'
  | { readonly handSizeEquals: number };

/**
 * Боевой эффект: добавка к атаке/защите (всегда ADD-семантика).
 */
export interface CombatModifierEffect {
  readonly kind: 'combat-modifier';
  /** К чему применяется: атака, защита или обе стороны боя */
  readonly appliesTo: 'attack' | 'defense' | 'both';
  /** Величина (ADD) */
  readonly value: number;
}

/**
 * Эффект хода: добор/лечение/доп. действие.
 * Любое поле опционально — применяются только заданные.
 */
export interface TurnEffect {
  readonly kind: 'turn-effect';
  /** Добрать ровно N карт */
  readonly draw?: number;
  /** Добирать карты, пока в руке не станет N (с учётом текущего размера) */
  readonly drawToHandSize?: number;
  /** Восстановить N здоровья герою (не выше maxHealth) */
  readonly heal?: number;
  /** Прибавить N к оставшимся действиям хода */
  readonly gainAction?: number;
}

/**
 * Эффект правила — дискриминируется по kind.
 */
export type AbilityEffect = CombatModifierEffect | TurnEffect;

/**
 * Одно правило способности: триггер + (опц.) условие + эффект.
 */
export interface AbilityRule {
  readonly trigger: AbilityTrigger;
  /** Условие; если опущено — считается 'always' */
  readonly condition?: AbilityCondition;
  readonly effect: AbilityEffect;
}

/**
 * Полная декларативная конфигурация способности героя.
 */
export interface AbilityConfig {
  /**
   * Ключ реестра — СЛАГ героя (slugifyHeroName), например 'king-arthur',
   * 'ms-marvel'. НЕ Prisma cuid.
   */
  readonly heroId: string;
  readonly abilityName: string;
  readonly description: string;
  readonly rules: readonly AbilityRule[];
}

/**
 * Реестр data-driven способностей. Регистрируется циклом в
 * GameEngineModule.onModuleInit (по одному GenericHeroAbilityHandler на конфиг).
 *
 * heroId здесь — СЛАГ героя (slugifyHeroName(name)), он же ключ реестра и
 * fighter.heroSlug на game-init. Подтверждённые слаги:
 *  'Luke Cage'→luke-cage, 'Annie Christmas'→annie-christmas, 'Eredin'→eredin,
 *  'Bloody Mary'→bloody-mary, 'Philippa'→philippa, 'T. Rex'→t-rex,
 *  'Bigfoot'→bigfoot.
 */
export const ABILITY_CONFIGS: readonly AbilityConfig[] = [
  {
    // Luke Cage — «Skin Like Titanium»: получает на 2 урона меньше = +2 к защите.
    heroId: 'luke-cage',
    abilityName: 'Skin Like Titanium',
    description: 'Постоянно: Luke Cage получает на 2 урона меньше (+2 к защите).',
    rules: [
      {
        trigger: 'combat-passive',
        condition: 'always',
        effect: { kind: 'combat-modifier', appliesTo: 'defense', value: 2 },
      },
    ],
  },
  {
    // Annie Christmas — «Long Shot»: +2 к атаке, когда её здоровье ниже защитника.
    heroId: 'annie-christmas',
    abilityName: 'Long Shot',
    description: 'Когда здоровье Annie ниже здоровья защитника, её атака получает +2.',
    rules: [
      {
        trigger: 'combat-passive',
        condition: 'self-health-below-defender',
        effect: { kind: 'combat-modifier', appliesTo: 'attack', value: 2 },
      },
    ],
  },
  {
    // Eredin — «Unyielding hordes»: +1 к атаке И защите, когда все его сайдкики
    // (Red Rider'ы) повержены.
    heroId: 'eredin',
    abilityName: 'Unyielding Hordes',
    description: 'Когда все сайдкики Eredin повержены, его атака и защита получают +1.',
    rules: [
      {
        trigger: 'combat-passive',
        condition: 'all-own-sidekicks-defeated',
        effect: { kind: 'combat-modifier', appliesTo: 'both', value: 1 },
      },
    ],
  },
  {
    // Bloody Mary — «Infinity Mirror»: +1 действие в начале хода, если в руке
    // ровно 3 карты.
    heroId: 'bloody-mary',
    abilityName: 'Infinity Mirror',
    description: 'В начале хода: если в руке ровно 3 карты — +1 действие.',
    rules: [
      {
        trigger: 'turn-start',
        condition: { handSizeEquals: 3 },
        effect: { kind: 'turn-effect', gainAction: 1 },
      },
    ],
  },
  {
    // Philippa — добор до 4 карт в конце хода.
    heroId: 'philippa',
    abilityName: 'Spellbreaker',
    description: 'В конце хода Philippa добирает карты до 4 в руке.',
    rules: [
      {
        trigger: 'turn-end',
        condition: 'always',
        effect: { kind: 'turn-effect', drawToHandSize: 4 },
      },
    ],
  },
  {
    // T. Rex — добор 1 карты в конце хода.
    heroId: 't-rex',
    abilityName: 'Reckless Lunge',
    description: 'В конце хода T. Rex добирает 1 карту.',
    rules: [
      {
        trigger: 'turn-end',
        condition: 'always',
        effect: { kind: 'turn-effect', draw: 1 },
      },
    ],
  },
  {
    // Bigfoot — «It's Just Your Imagination»: добор 1 карты в конце хода, если в
    // зоне Bigfoot нет вражеских бойцов.
    heroId: 'bigfoot',
    abilityName: "It's Just Your Imagination",
    description: 'В конце хода: если в зоне Bigfoot нет врагов — добор 1 карты.',
    rules: [
      {
        trigger: 'turn-end',
        condition: 'no-enemy-in-own-zone',
        effect: { kind: 'turn-effect', draw: 1 },
      },
    ],
  },
];
