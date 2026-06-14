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
 *  - 'after-attack'   — эффект ПОСЛЕ резолва боя, применяется к АТАКУЮЩЕМУ
 *                       игроку (использует тот же TurnEffect: draw/heal/
 *                       gainAction/drawToHandSize). Оценивается против исхода
 *                       боя (AfterCombatContext) — см. won-combat/lost-combat.
 *  - 'after-defense'  — эффект ПОСЛЕ резолва боя, применяется к ЗАЩИЩАЮЩЕМУСЯ
 *                       игроку (ctx.defenderPlayerId). Зеркало 'after-attack'
 *                       для defender-side способностей (напр. Spider-Sense:
 *                       «After an attacker reveals a card during combat with
 *                       Spider-Man, you may draw a card»). Тот же TurnEffect и
 *                       те же after-combat условия (won/lost), но цель —
 *                       защитник. Если ctx.defenderPlayerId не задан — no-op.
 */
export type AbilityTrigger =
  | 'combat-passive'
  | 'turn-start'
  | 'turn-end'
  | 'after-attack'
  | 'after-defense';

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
 *  - 'won-combat'                  — [after-attack] атакующий победил (ctx.won)
 *  - 'lost-combat'                 — [after-attack] атакующий НЕ победил (!ctx.won)
 *  - 'has-not-maneuvered-this-turn'— [combat-passive] активный игрок ещё НЕ делал
 *                                    манёвр в этом ходу (state.metadata.
 *                                    maneuveredThisTurn falsy). Имеет смысл для
 *                                    АТАКУЮЩЕГО (per-turn флаги — активного игрока).
 *  - 'has-attacked-this-turn'      — [combat-passive] активный игрок уже завершил
 *                                    хотя бы одну атаку в этом ходу (state.metadata.
 *                                    attackedThisTurn). Имеет смысл для АТАКУЮЩЕГО.
 *  - 'first-lost-combat-this-turn' — [after-attack] это ПЕРВЫЙ проигранный бой
 *                                    атакующего в этом ходу (ctx.won===false &&
 *                                    ctx.firstLossThisTurn).
 *
 * ВАЖНО: 'won-combat'/'lost-combat'/'first-lost-combat-this-turn' имеют смысл
 * ТОЛЬКО для триггера 'after-attack' (оцениваются против AfterCombatContext);
 * 'has-not-maneuvered-this-turn'/'has-attacked-this-turn' — ТОЛЬКО для
 * 'combat-passive' (читают per-turn флаги активного игрока). Несоответствующее
 * триггеру условие безопасно игнорируется (правило не срабатывает).
 */
export type AbilityCondition =
  | 'always'
  | 'attacking'
  | 'defending'
  | 'self-health-below-defender'
  | 'all-own-sidekicks-defeated'
  | 'no-enemy-in-own-zone'
  | 'won-combat'
  | 'lost-combat'
  | 'has-not-maneuvered-this-turn'
  | 'has-attacked-this-turn'
  | 'first-lost-combat-this-turn'
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
 * Эффект «отложенный ход» (pending-move): способность порождает MOVE
 * PendingEffect (C2), который игрок резолвит мутацией resolvePendingEffect
 * (как «You may move…» с карт). Сам ход не исполняется здесь — лишь создаётся
 * pending в metadata.pendingEffects; исполнение/резолв остаётся за общим C2.
 *
 * target определяет, какого бойца можно двигать:
 *  - 'attacker' — боец, ТОЛЬКО ЧТО атаковавший (валидно ЛИШЬ для триггера
 *                 'after-attack'; имя берётся из ctx.attackerFighterId). Для
 *                 turn-start/turn-end этот target — no-op (нет контекста боя).
 *  - 'own-hero' — HERO-боец действующего игрока (fighterName = имя героя).
 *  - 'any-own'  — любой свой боец (fighterName опускается на pending).
 * Во всех случаях targetsOpponent === false (двигается СВОЙ боец), value =
 * maxSpaces (макс. число клеток перемещения).
 */
export interface PendingMoveEffect {
  readonly kind: 'pending-move';
  /** Кого можно двигать: атаковавшего бойца / своего героя / любого своего */
  readonly target: 'attacker' | 'own-hero' | 'any-own';
  /** Максимальное число клеток перемещения (value на MOVE PendingEffect) */
  readonly maxSpaces: number;
}

/**
 * Эффект «урон в ход» (turn-damage): способность сама, БЕЗ участия игрока,
 * наносит value урона ОДНОМУ авто-выбранному вражескому бойцу и (опц.) после
 * успешного попадания добирает thenDraw карт. В отличие от pending-move здесь
 * нет PendingEffect/UI — урон применяется напрямую в onTurnStart/onTurnEnd.
 *
 * Валиден ТОЛЬКО для триггеров 'turn-start' | 'turn-end' (для них есть
 * playerId-контекст действующего игрока; вне их — игнорируется).
 *
 * targetScope определяет, какой враг попадает под удар:
 *  - 'enemy-in-zone'  — вражеский боец в той же ЗОНЕ доски, что и HERO-боец
 *                       действующего игрока (deps.zone.isInSameZone).
 *  - 'enemy-adjacent' — вражеский боец, СМЕЖНЫЙ с HERO-бойцом действующего
 *                       игрока (deps.zone.manhattanDistance === 1).
 *
 * MVP / ПРИБЛИЖЕНИЕ: auto-target — выбирается ПЕРВЫЙ подходящий враг в порядке
 * state.fighters; выбора цели игроком и opt-out НЕТ (печатные «you may» здесь
 * не моделируются — бьём детерминированно по первому кандидату).
 *
 * Семантика урона: health = max(0, health - value); при достижении 0 боец
 * помечается isDefeated, владельцу пересчитывается isAlive. thenDraw добирается
 * ТОЛЬКО если цель реально была найдена и получила урон; нет цели → чистый
 * no-op (и без добора).
 */
export interface TurnDamageEffect {
  readonly kind: 'turn-damage';
  /** Область авто-выбора цели: враг в зоне героя / смежный с героем */
  readonly targetScope: 'enemy-in-zone' | 'enemy-adjacent';
  /** Сколько урона нанести выбранному врагу */
  readonly value: number;
  /** (Опц.) добрать N карт ПОСЛЕ успешного попадания (если цель найдена) */
  readonly thenDraw?: number;
}

/**
 * Эффект правила — дискриминируется по kind.
 */
export type AbilityEffect =
  | CombatModifierEffect
  | TurnEffect
  | PendingMoveEffect
  | TurnDamageEffect;

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
 *  'Bigfoot'→bigfoot, 'Golden Bat'→golden-bat, 'Ancient Leshen'→ancient-leshen,
 *  'Raphael'→raphael.
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
  {
    // Chupacabra — после своей атаки добирает 1 карту (вне зависимости от исхода).
    heroId: 'chupacabra',
    abilityName: 'Blood Frenzy',
    description: 'После своей атаки Chupacabra добирает 1 карту (независимо от исхода боя).',
    rules: [
      {
        trigger: 'after-attack',
        condition: 'always',
        effect: { kind: 'turn-effect', draw: 1 },
      },
    ],
  },
  {
    // Deadpool — после своей атаки восстанавливает 1 здоровье (регенерация).
    heroId: 'deadpool',
    abilityName: 'Regeneration',
    description: 'После своей атаки Deadpool восстанавливает 1 здоровье (независимо от исхода боя).',
    rules: [
      {
        trigger: 'after-attack',
        condition: 'always',
        effect: { kind: 'turn-effect', heal: 1 },
      },
    ],
  },
  {
    // Michelangelo — после своей атаки добирает 1 карту.
    // ПРИБЛИЖЕНИЕ: печатный лимит руки в 3 карты НЕ моделируется (см. notes).
    heroId: 'michelangelo',
    abilityName: 'Party Dude',
    description:
      'После своей атаки Michelangelo добирает 1 карту (независимо от исхода боя). ' +
      'Примечание: печатный лимит руки в 3 карты не моделируется.',
    rules: [
      {
        trigger: 'after-attack',
        condition: 'always',
        effect: { kind: 'turn-effect', draw: 1 },
      },
    ],
  },
  {
    // Angel — после ПРОИГРАННОЙ атаки добирает 1 карту (компенсация неудачи).
    heroId: 'angel',
    abilityName: 'Fallen Grace',
    description: 'Когда Angel проигрывает свою атаку (бой не выигран) — добирает 1 карту.',
    rules: [
      {
        trigger: 'after-attack',
        condition: 'lost-combat',
        effect: { kind: 'turn-effect', draw: 1 },
      },
    ],
  },
  {
    // Golden Bat — «The First Superhero»: +2 к атаке, если в этом ходу ещё НЕ
    // делал манёвр (state.metadata.maneuveredThisTurn falsy).
    heroId: 'golden-bat',
    abilityName: 'The First Superhero',
    description:
      'Если Golden Bat ещё не делал манёвр в этом ходу — его атаки получают +2.',
    rules: [
      {
        trigger: 'combat-passive',
        condition: 'has-not-maneuvered-this-turn',
        effect: { kind: 'combat-modifier', appliesTo: 'attack', value: 2 },
      },
    ],
  },
  {
    // Ancient Leshen — «Heart of the Forest»: +3 к атаке, если в этом ходу уже
    // атаковал (state.metadata.attackedThisTurn).
    // ПРИБЛИЖЕНИЕ: вторая часть способности — «Wolves move value 3» (стат
    // сайдкика) — НЕ моделируется (см. notes).
    heroId: 'ancient-leshen',
    abilityName: 'Heart of the Forest',
    description:
      'Если Ancient Leshen уже атаковал в этом ходу — его атаки получают +3. ' +
      'Примечание: «Wolves move value 3» (стат сайдкика) не моделируется.',
    rules: [
      {
        trigger: 'combat-passive',
        condition: 'has-attacked-this-turn',
        effect: { kind: 'combat-modifier', appliesTo: 'attack', value: 3 },
      },
    ],
  },
  {
    // Raphael — «Anger Issues»: при ПЕРВОМ проигрыше боя в каждом своём ходу
    // получает +1 действие (ctx.won===false && ctx.firstLossThisTurn).
    heroId: 'raphael',
    abilityName: 'Anger Issues',
    description:
      'В каждый свой ход при первом проигрыше боя Raphael получает +1 действие.',
    rules: [
      {
        trigger: 'after-attack',
        condition: 'first-lost-combat-this-turn',
        effect: { kind: 'turn-effect', gainAction: 1 },
      },
    ],
  },
  {
    // Robin Hood — «Trick Shot»-подобное репозиционирование: после своей атаки
    // может сдвинуть атаковавшего бойца на величину до 2 клеток. Порождает MOVE
    // PendingEffect (C2), который игрок резолвит мутацией resolvePendingEffect.
    heroId: 'robin-hood',
    abilityName: 'Trick Shot',
    description:
      'После своей атаки Robin Hood может переместить атаковавшего бойца на величину до 2 клеток ' +
      '(независимо от исхода боя). Создаёт отложенный MOVE-эффект (C2).',
    rules: [
      {
        trigger: 'after-attack',
        condition: 'always',
        effect: { kind: 'pending-move', target: 'attacker', maxSpaces: 2 },
      },
    ],
  },
  {
    // Leonardo — в начале хода может сдвинуть любого бойца на величину до 1.
    // ПРИБЛИЖЕНИЕ: печатная способность двигает ЛЮБОГО бойца, включая вражеского,
    // но PendingEffect.targetsOpponent бинарен, а перемещение чужих фигур моделью
    // не поддержано — MVP ограничивает выбор СВОИМИ бойцами (target 'any-own',
    // targetsOpponent === false). Документируем это упрощение здесь.
    heroId: 'leonardo',
    abilityName: 'Tactical Genius',
    description:
      'В начале хода Leonardo может переместить любого СВОЕГО бойца на величину до 1 клетки. ' +
      'Создаёт отложенный MOVE-эффект (C2). Примечание (приближение MVP): печатная способность ' +
      'двигает ЛЮБОГО бойца, включая вражеского, но перемещение чужих фигур не моделируется — ' +
      'выбор ограничен своими бойцами.',
    rules: [
      {
        trigger: 'turn-start',
        condition: 'always',
        effect: { kind: 'pending-move', target: 'any-own', maxSpaces: 1 },
      },
    ],
  },
  {
    // Dracula — «Children of the Night»-подобный укус: в начале хода может нанести
    // 1 урон бойцу, СМЕЖНОМУ с Dracula; если урон нанесён — добирает 1 карту.
    // ПРИБЛИЖЕНИЕ (MVP): печатное «you may» (выбор/opt-out игроком) не моделируется
    // — авто-бьём ПЕРВОГО смежного вражеского бойца (порядок state.fighters);
    // thenDraw срабатывает ТОЛЬКО при реальном попадании (нет цели → no-op без добора).
    heroId: 'dracula',
    abilityName: 'Children of the Night',
    description:
      'В начале хода Dracula может нанести 1 урон смежному бойцу; если урон нанесён — добрать 1 карту. ' +
      'Примечание (приближение MVP): выбор цели/opt-out игроком не моделируется — авто-удар по первому ' +
      'смежному врагу; добор только при реальном попадании.',
    rules: [
      {
        trigger: 'turn-start',
        condition: 'always',
        effect: { kind: 'turn-damage', targetScope: 'enemy-adjacent', value: 1, thenDraw: 1 },
      },
    ],
  },
  {
    // Medusa — «Petrifying Gaze»-подобный взгляд: в начале хода может нанести 1 урон
    // вражескому бойцу в ЗОНЕ Medusa.
    // ПРИБЛИЖЕНИЕ (MVP): печатное «you may» (выбор/opt-out игроком) не моделируется
    // — авто-бьём ПЕРВОГО вражеского бойца в зоне героя (порядок state.fighters).
    // Без добора (thenDraw отсутствует); нет цели в зоне → чистый no-op.
    heroId: 'medusa',
    abilityName: 'Petrifying Gaze',
    description:
      'В начале хода Medusa может нанести 1 урон вражескому бойцу в своей зоне. ' +
      'Примечание (приближение MVP): выбор цели/opt-out игроком не моделируется — авто-удар по первому ' +
      'врагу в зоне героя.',
    rules: [
      {
        trigger: 'turn-start',
        condition: 'always',
        effect: { kind: 'turn-damage', targetScope: 'enemy-in-zone', value: 1 },
      },
    ],
  },
  // NB: триггер 'after-defense' + AfterCombatContext.defenderPlayerId — инфра
  // для defender-side способностей (зеркало 'after-attack'), пока без героя:
  // реальный Spider-Man = info-reveal («оппонент раскрывает значение карты до
  // защиты»), это COMPLEX-механика, не draw — намеренно НЕ реализован здесь.
];
