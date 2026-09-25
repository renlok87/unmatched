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
 *  - 'sidekick-defeated' — реакция на гибель СВОЕГО сайдкика (Achilles-style:
 *                       «When Patroclus is defeated, discard 2 random cards»).
 *                       Диспетчеризуется через РЕАНИМИРОВАННЫЙ on-defeat хук:
 *                       executor дёргает onFighterDefeated владельца повергнутого
 *                       бойца ПОСЛЕ установки isDefeated, но ДО game-over/передачи
 *                       хода. Handler реагирует, только если defeatedFighter —
 *                       НЕ-HERO боец владельца ЭТОГО героя (свой сайдкик).
 *  - 'enemy-hero-left-my-zone' — РЕАКТИВНЫЙ кросс-героевый триггер (Tomoe-style:
 *                       «When an opposing hero leaves Tomoe Gozen's zone, deal 1
 *                       damage to that hero»). Диспетчеризуется через
 *                       РЕАНИМИРОВАННЫЙ on-move хук: executor проходит по диффу
 *                       позиций ПОСЛЕ перемещения и дёргает onFighterMoved у
 *                       КАЖДОГО зарегистрированного героя (реагирует ГЕРОЙ,
 *                       ОТЛИЧНЫЙ от двигающегося). Handler реагирует, только если
 *                       сдвинувшийся боец — вражеский HERO, который БЫЛ в зоне
 *                       этого героя (fromPos) и ПОКИНУЛ её (toPos вне зоны).
 *                       Используется с эффектом reactive-damage.
 */
export type AbilityTrigger =
  | 'combat-passive'
  | 'turn-start'
  | 'turn-end'
  | 'after-attack'
  | 'after-defense'
  | 'sidekick-defeated'
  | 'enemy-hero-left-my-zone';

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
 *  - 'won-combat-and-all-sidekicks-defeated' — [after-attack] КОМПАУНД-условие
 *                                    (Achilles-style): атакующий победил
 *                                    (ctx.won===true) И все сайдкики действующего
 *                                    героя (ctx.playerId) повержены
 *                                    (all-own-sidekicks-defeated против ctx.playerId).
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
  | 'won-combat-and-all-sidekicks-defeated'
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
 * ДИНАМИЧЕСКИЙ боевой модификатор: добавка к атаке/защите, чья величина
 * МАСШТАБИРУЕТСЯ от подсчёта на доске (Raptors-style: «+1 к атаке за каждого
 * ДРУГОГО дружественного бойца, СМЕЖНОГО с защитником»). Всегда ADD-семантика.
 *
 * Итоговое значение = valuePer * count, где count определяется countOf.
 * Валиден ТОЛЬКО для триггера 'combat-passive' (как и CombatModifierEffect):
 * считается против пары боец/контекст боя в getStatefulCombatModifiers.
 *
 * countOf — стратегия подсчёта:
 *  - 'own-fighters-adjacent-to-defender-excl-self' — число бойцов, принадлежащих
 *    fighter.ownerId (СВОИ), НЕ повергнутых, ИСКЛЮЧАЯ самого бойца (excl-self),
 *    чья позиция СМЕЖНА с бойцом-защитником боя
 *    (deps.zone.manhattanDistance(pos, defenderPos) === 1). Защитник-боец
 *    резолвится как state.fighters[targetFighterId ?? defenderId]; если боец не
 *    найден — count считается отсутствующим (модификатор не выдаётся).
 *
 * Модификатор выдаётся ТОЛЬКО когда count > 0 (нулевой бонус не порождает
 * ValueModifier — чистый no-op). appliesTo vs role и condition гейтятся так же,
 * как у обычного CombatModifierEffect.
 */
export interface CombatModifierPerCountEffect {
  readonly kind: 'combat-modifier-per-count';
  /** К чему применяется: атака, защита или обе стороны боя */
  readonly appliesTo: 'attack' | 'defense' | 'both';
  /** Прибавка ЗА ЕДИНИЦУ count (итог = valuePer * count, ADD) */
  readonly valuePer: number;
  /** Стратегия подсчёта (что именно считаем на доске) */
  readonly countOf: 'own-fighters-adjacent-to-defender-excl-self';
}

/**
 * АУРНЫЙ боевой модификатор (Oda-style): герой-ГРАНИТЕЛЬ ауры баффает ДРУГИХ
 * дружественных бойцов, делящих ЕГО зону, во время ИХ боя.
 *
 * ВАЖНО — отличие от CombatModifierEffect: обычный combat-modifier консультирует
 * own-handler КОНКРЕТНОГО бойца боя (его собственного героя). Аура же исходит от
 * ДРУГОГО героя (гранителя), поэтому она диспетчеризуется отдельным путём
 * (HeroAbilityRegistry.getAuraCombatModifiers + GenericHeroAbilityHandler.
 * getAuraCombatModifiers), который консультирует ВСЕХ зарегистрированных героев,
 * а не только героя бойца-бенефициара.
 *
 * Семантика: модификатор применяется к ДРУГИМ бойцам гранителя
 * (ИСКЛЮЧАЯ самого HERO-бойца гранителя), которые делят зону HERO-бойца
 * гранителя (deps.zone.isInSameZone), во время боя ЭТИХ бойцов (бенефициаров).
 * appliesTo гейтит сторону боя бенефициара (attack/defense/both). Всегда
 * ADD-семантика. Используется с триггером 'combat-passive' (это правило
 * героя-ГРАНИТЕЛЯ ауры). НЕ использует контекст защитника боя — баффает именно
 * бойца-бенефициара.
 *
 * scope — область действия ауры:
 *  - 'allies-in-my-zone' — дружественные бойцы (тот же ownerId, что у HERO-бойца
 *    гранителя), ИСКЛЮЧАЯ самого HERO-бойца гранителя, делящие его зону.
 */
export interface AuraCombatModifierEffect {
  readonly kind: 'aura-combat-modifier';
  /** К чему применяется у бенефициара: атака, защита или обе стороны боя */
  readonly appliesTo: 'attack' | 'defense' | 'both';
  /** Величина (ADD) */
  readonly value: number;
  /** Область действия ауры (кого баффает гранитель) */
  readonly scope: 'allies-in-my-zone';
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
 * Эффект «сброс карт» (discard-random): способность сбрасывает N карт из руки
 * ДЕЙСТВУЮЩЕГО игрока (Achilles-style: «discard 2 random cards» при гибели
 * Patroclus). Карты уходят в discardPile владельца (если он есть), иначе просто
 * удаляются из руки.
 *
 * ПРИБЛИЖЕНИЕ / ДЕТЕРМИНИЗМ: печатное «random» НЕ моделируется случайным выбором
 * (нет источника энтропии в движке и нет выбора игроком) — детерминированно
 * сбрасываем ПЕРВЫЕ count карт руки. Если в руке меньше count — сбрасываем
 * сколько есть (пустая рука → чистый no-op).
 *
 * Используется с триггером 'sidekick-defeated' (handler гейтит: defeatedFighter —
 * свой НЕ-HERO боец).
 */
export interface DiscardRandomEffect {
  readonly kind: 'discard-random';
  /** Сколько карт сбросить из руки (детерминированный стенд-ин для «random») */
  readonly count: number;
}

/**
 * Эффект «реактивный урон» (reactive-damage): способность наносит value урона
 * бойцу, КОТОРЫЙ ТОЛЬКО ЧТО ПЕРЕМЕСТИЛСЯ и тем самым активировал триггер
 * (Tomoe-style: «When an opposing hero leaves Tomoe Gozen's zone, deal 1 damage
 * to that hero»). В отличие от turn-damage (которое САМО авто-выбирает цель в
 * зоне/смежно с героем в turn-start/turn-end), здесь цель ЗАДАНА извне —
 * движком — это movedFighter, переданный в onFighterMoved.
 *
 * Валиден ТОЛЬКО для триггера 'enemy-hero-left-my-zone' (handler гейтит: цель —
 * вражеский HERO, который ПОКИНУЛ зону героя-владельца способности).
 *
 * Семантика урона зеркалит turn-damage: health = max(0, health - value); при
 * достижении 0 боец помечается isDefeated, владельцу пересчитывается isAlive.
 * Game-over здесь НЕ ставится — это делает WIRE recheck (applyMoveReactions →
 * checkAndApplyGameOver) ПОСЛЕ всех on-move реакций; seq не бампится.
 */
export interface ReactiveDamageEffect {
  readonly kind: 'reactive-damage';
  /** Сколько урона нанести сдвинувшемуся бойцу, активировавшему триггер */
  readonly value: number;
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
 * Эффект «сменить стойку» (set-stance, STANCE-подсистема): авто-смена текущей
 * стойки ДЕЙСТВУЮЩЕГО героя (metadata.heroStances[playerId]).
 *
 *  - to: '<id>'   — поставить стойку с этим id (должна существовать в
 *                   config.stances);
 *  - to: 'toggle' — для 2-стоечных героев перейти в ДРУГУЮ стойку
 *                   (альтернация). При >2 стойках 'toggle' эквивалентен 'next'
 *                   (следующая по порядку с переносом).
 *
 * Используется с триггерами after-attack/after-defense (Muhammad Ali —
 * «After you attack, if you won the combat, change stances» — флип gated
 * условием won-combat) и turn-start/turn-end. Эффект применяется к стойке
 * героя ctx.playerId (для after-*) либо playerId (для turn-*).
 */
export interface SetStanceEffect {
  readonly kind: 'set-stance';
  /** id целевой стойки ИЛИ 'toggle' (другая стойка для 2-стоечных героев) */
  readonly to: string | 'toggle';
}

/**
 * Эффект «следующая стойка по циклу» (cycle-stance, STANCE-подсистема):
 * продвигает стойку героя на СЛЕДУЮЩУЮ в порядке config.stances с переносом
 * (wrap на первую после последней). Для будущего Moon Knight (3-стоечный
 * авто-цикл MoonKnight→Khonshu→MrKnight в конце хода). Применяется к стойке
 * действующего игрока; обычно с триггером turn-end.
 */
export interface CycleStanceEffect {
  readonly kind: 'cycle-stance';
}

/**
 * Эффект «выбор цели урона» (pending-target-damage, S05): способность в начале
 * хода ПОРОЖДАЕТ optional TARGET_FIGHTER PendingEffect — игрок сам выбирает
 * врага ИЗ легальных целей или отклоняет выбор (declinePendingEffect, «you may»).
 *
 * В отличие от turn-damage (авто-выбор первого врага, нет UI) здесь НЕТ
 * авто-таргета: цели сериализуются в pending.targetFighterIds (ревалидация на
 * резолве), optional=true — отказ легален. GD-017/R-14: Medusa «At the start of
 * your turn, you may deal 1 damage to an opposing fighter in Medusa's zone.»
 *
 * Валиден ТОЛЬКО для триггера 'turn-start'. Нет легальных целей → чистый no-op
 * (pending не создаётся — игрок не «зависает» на пустом выборе).
 */
export interface PendingTargetDamageEffect {
  readonly kind: 'pending-target-damage';
  /** Область выбора цели: вражеский боец в зоне героя действующего игрока */
  readonly targetScope: 'enemy-in-zone';
  /** Сколько урона нанести выбранному врагу */
  readonly value: number;
}

/**
 * Эффект правила — дискриминируется по kind.
 */
export type AbilityEffect =
  | CombatModifierEffect
  | CombatModifierPerCountEffect
  | AuraCombatModifierEffect
  | TurnEffect
  | PendingMoveEffect
  | TurnDamageEffect
  | PendingTargetDamageEffect
  | DiscardRandomEffect
  | ReactiveDamageEffect
  | SetStanceEffect
  | CycleStanceEffect;

/**
 * Одно правило способности: триггер + (опц.) условие + эффект.
 */
export interface AbilityRule {
  readonly trigger: AbilityTrigger;
  /** Условие; если опущено — считается 'always' */
  readonly condition?: AbilityCondition;
  readonly effect: AbilityEffect;
  /**
   * (Опц., STANCE) Правило АКТИВНО только когда ТЕКУЩАЯ стойка героя равна
   * этому id (Alice: attack-бонус — только в BIG, defense-бонус — только в
   * SMALL). Текущая стойка читается из metadata.heroStances[ownerId] с
   * фолбэком на стойку config.stances с default:true (или первую). Если поле
   * не задано — правило не гейтится стойкой (срабатывает как обычно).
   */
  readonly whenStance?: string;
}

/**
 * Одна стойка героя (STANCE-подсистема).
 *
 *  - attackRange — (опц.) пассивная дальность атаки В ЭТОЙ стойке
 *    (Muhammad Ali FLOAT: range 2; STING — поля нет → дальняя атака запрещена).
 *    Стойковая дальность ПЕРЕОПРЕДЕЛЯЕТ базовую config.attackRange:
 *    canAttackAtRange читает дальность ТЕКУЩЕЙ стойки, фолбэк на config.attackRange.
 *  - combat — (опц.) фиксированный combat-modifier, активный пока стойка текущая
 *    (альтернатива whenStance-правилу; обе формы поддержаны).
 */
export interface StanceConfig {
  readonly id: string;
  readonly label: string;
  /** Стойка по умолчанию при размещении (если ни одна не помечена — берётся первая) */
  readonly default?: boolean;
  /** Пассивная дальность атаки в этой стойке (см. canAttackAtRange) */
  readonly attackRange?: number;
  /** Фиксированный combat-modifier, активный пока стойка текущая */
  readonly combat?: {
    readonly appliesTo: 'attack' | 'defense' | 'both';
    readonly value: number;
  };
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
  /**
   * (Опц.) ПАССИВНАЯ дальность атаки: максимальная Manhattan-дистанция, на
   * которой герой может атаковать цель, ИГНОРИРУЯ зональные ограничения боя
   * (напр. Ms. Marvel «растяжимые конечности» — может бить на расстоянии до 2).
   *
   * Это СВОЙСТВО конфига (не AbilityRule): дальность — характеристика бойца, а
   * не триггерный эффект. Реализуется через GenericHeroAbilityHandler.
   * canAttackAtRange (диспетчеризуется реестром в executeAttack как additive-
   * хук: может разрешить дальнюю атаку, но НИКОГДА не запрещает обычную). Если
   * поле не задано — canAttackAtRange всегда возвращает false (хук не влияет).
   *
   * STANCE: если у героя есть stances со стоечным attackRange (Ali FLOAT),
   * canAttackAtRange читает дальность ТЕКУЩЕЙ стойки, а это поле — фолбэк для
   * стоек без собственного attackRange.
   */
  readonly attackRange?: number;
  /**
   * (Опц., STANCE) Стойки героя. Если задано — герой stance-aware:
   *  - текущая стойка хранится в metadata.heroStances[ownerId] (id из stances);
   *  - дефолт при размещении — стойка с default:true (или первая);
   *  - правила можно гейтить по whenStance; combat/attackRange можно вынести в
   *    StanceConfig; смену стойки делают setStance / set-stance / cycle-stance.
   * Примеры: Alice (big/small), Muhammad Ali (float/sting).
   */
  readonly stances?: readonly StanceConfig[];
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
    // T. Rex — добор 1 карты в конце хода + пассивная дальность атаки 2
    // (Large fighter, attacks up to 2 spaces) через config.attackRange.
    heroId: 't-rex',
    abilityName: 'Reckless Lunge',
    description: 'Large fighter, attacks up to 2 spaces. В конце хода T. Rex добирает 1 карту.',
    attackRange: 2,
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
    // Medusa — старт-хода урон: в начале хода может нанести 1 урон вражескому
    // бойцу в ЗОНЕ Medusa (R-14, GD-017).
    // S05: печать «you may» моделируется честно — optional TARGET_FIGHTER
    // pending (owner-bound, decline разрешён, auto-target НЕТ). Цели — живые
    // вражеские бойцы в зоне Medusa; ревалидация на резолве. Нет легальных
    // целей в зоне → pending не создаётся (no-op).
    // abilityName — ВНУТРЕННИЙ provisional-лейбл: в захвате (content-medusa.json)
    // у способности НЕТ поля name, канонического имени не существует.
    // NB: King Arthur (allowsAttackBoost) живёт ОТДЕЛЬНЫМ classic-handler'ом
    // arthurAbilityHandler (heroes/arthur.handler.ts) — не дублируем здесь.
    heroId: 'medusa',
    abilityName: 'Medusa turn-start damage (provisional)',
    description:
      'At the start of your turn, you may deal 1 damage to an opposing fighter in Medusa\'s zone. ' +
      '(S05: интерактивный выбор цели или отказ — pending TARGET_FIGHTER, без auto-target.)',
    rules: [
      {
        trigger: 'turn-start',
        condition: 'always',
        effect: { kind: 'pending-target-damage', targetScope: 'enemy-in-zone', value: 1 },
      },
    ],
  },
  {
    // Bullseye — пассивная дальнобойность: может атаковать на расстоянии до 5
    // клеток, игнорируя зональные ограничения. Других простых combat/turn
    // эффектов у Bullseye здесь не моделируется, поэтому rules пуст —
    // способность целиком выражена через config.attackRange (canAttackAtRange).
    heroId: 'bullseye',
    abilityName: 'Bullseye',
    description: 'Can attack from up to 5 spaces away ignoring zones.',
    attackRange: 5,
    rules: [],
  },
  {
    // Bruce Lee — «Be Like Water»-стиль репозиционирования: в конце хода может
    // переместить себя (HERO-бойца) на величину до 1 клетки. Порождает MOVE
    // PendingEffect (C2), который игрок может резолвить ИЛИ отклонить («you may»).
    heroId: 'bruce-lee',
    abilityName: 'Be Like Water',
    description:
      'В конце хода Bruce Lee может переместиться на 1 клетку. Создаёт отложенный MOVE-эффект (C2), ' +
      'который игрок может отклонить (печатное «you may»).',
    rules: [
      {
        trigger: 'turn-end',
        condition: 'always',
        effect: { kind: 'pending-move', target: 'own-hero', maxSpaces: 1 },
      },
    ],
  },
  {
    // Raptors — «Pack Tactics»: +1 к атаке за каждого ДРУГОГО raptor, смежного с
    // защитником. Все raptor'ы — свои бойцы; per-count подсчёт исключает самого
    // атакующего raptor (excl-self) и считает только живых союзников, смежных с
    // бойцом-защитником боя. Бонус только на стороне АТАКИ (condition attacking).
    heroId: 'raptors',
    abilityName: 'Pack Tactics',
    description:
      'Raptors получают +1 к атаке за каждого ДРУГОГО Raptor, смежного с защитником.',
    rules: [
      {
        trigger: 'combat-passive',
        condition: 'attacking',
        effect: {
          kind: 'combat-modifier-per-count',
          appliesTo: 'attack',
          valuePer: 1,
          countOf: 'own-fighters-adjacent-to-defender-excl-self',
        },
      },
    ],
  },
  {
    // Oda Nobunaga — аура-командир: ДРУГИЕ дружественные бойцы в зоне Oda
    // получают +1 к значению своих боевых карт (атака и защита). Сам Oda бонус
    // НЕ получает. Реализуется через aura-combat-modifier (отдельный путь
    // диспетчеризации getAuraCombatModifiers — аура исходит от ДРУГОГО героя,
    // не от собственного героя бойца-бенефициара).
    // Слаг подтверждён через slugifyHeroName('Oda Nobunaga') → 'oda-nobunaga'.
    heroId: 'oda-nobunaga',
    abilityName: 'Banner of the Demon King',
    description:
      'Other friendly fighters in Oda\'s zone add +1 to the value of their combat cards; ' +
      'Oda himself does not benefit.',
    rules: [
      {
        trigger: 'combat-passive',
        condition: 'always',
        effect: {
          kind: 'aura-combat-modifier',
          appliesTo: 'both',
          value: 1,
          scope: 'allies-in-my-zone',
        },
      },
    ],
  },
  {
    // Achilles — «Grief of Achilles»: пока Patroclus (единственный сайдкик)
    // повержен — +2 к атаке Achilles; при ПОБЕДЕ в бою (когда сайдкик повержен)
    // добор 1 карты. В момент гибели Patroclus — сброс 2 карт из руки Achilles
    // (детерминированный стенд-ин для «discard 2 random cards»).
    // Печатный текст: «When Patroclus is defeated, discard 2 random cards.
    //   While Patroclus is defeated: +2 to the value of all Achilles' attacks;
    //   if Achilles wins combat, draw 1 card.»
    // Слаг подтверждён через slugifyHeroName('Achilles') → 'achilles'.
    heroId: 'achilles',
    abilityName: 'Grief of Achilles',
    description:
      "While Patroclus is defeated: +2 to all Achilles' attacks; if Achilles wins combat, draw 1 card. " +
      'When Patroclus is defeated, discard 2 cards. ' +
      'Примечание (приближение MVP): «random» сброс детерминирован — сбрасываются первые 2 карты руки.',
    rules: [
      {
        trigger: 'combat-passive',
        condition: 'all-own-sidekicks-defeated',
        effect: { kind: 'combat-modifier', appliesTo: 'attack', value: 2 },
      },
      {
        trigger: 'after-attack',
        condition: 'won-combat-and-all-sidekicks-defeated',
        effect: { kind: 'turn-effect', draw: 1 },
      },
      {
        trigger: 'sidekick-defeated',
        effect: { kind: 'discard-random', count: 2 },
      },
    ],
  },
  {
    // Tomoe Gozen — «Unwavering Resolve»-подобный заслон: когда вражеский герой
    // ПОКИДАЕТ зону Tomoe, она наносит ему 1 урон. Реактивный кросс-героевый
    // триггер (enemy-hero-left-my-zone): диспетчеризуется через on-move хук
    // (onFighterMoved) — реагирует Tomoe, а двигается вражеский герой.
    // Печатный текст: «When an opposing hero leaves Tomoe Gozen's zone, deal 1
    //   damage to that hero.»
    // Слаг подтверждён через slugifyHeroName('Tomoe Gozen') → 'tomoe-gozen'.
    heroId: 'tomoe-gozen',
    abilityName: 'Unwavering Resolve',
    description:
      "When an opposing hero leaves Tomoe Gozen's zone, deal 1 damage to that hero.",
    rules: [
      {
        trigger: 'enemy-hero-left-my-zone',
        effect: { kind: 'reactive-damage', value: 1 },
      },
    ],
  },
  {
    // Alice (Battle of Legends Vol.1) — «Big / Small» (STANCE).
    // Печатный текст (scraped, verbatim): «When you place Alice, choose whether
    //   she starts the game BIG or SMALL. When Alice is BIG, add 2 to the value
    //   of her attack cards. When Alice is SMALL, add 1 to the value of her
    //   defense cards.»
    // BIG: +2 к значению карт атаки Alice. SMALL: +1 к значению карт защиты.
    // Стойка — РУЧНАЯ: выбор при размещении (setStance) и «Change size»-карты
    // (Mad as a Hatter / Drink Me / Eat Me / …) — авто-флипа НЕТ.
    // Слаг подтверждён через slugifyHeroName('Alice') → 'alice'.
    heroId: 'alice',
    abilityName: 'Big / Small',
    description:
      'Place BIG or SMALL. BIG: +2 to the value of Alice\'s attack cards. ' +
      'SMALL: +1 to the value of her defense cards. Toggled manually ' +
      '(placement choice / «Change size» cards via setStance).',
    stances: [
      { id: 'big', label: 'Big', default: true },
      { id: 'small', label: 'Small' },
    ],
    rules: [
      {
        trigger: 'combat-passive',
        whenStance: 'big',
        effect: { kind: 'combat-modifier', appliesTo: 'attack', value: 2 },
      },
      {
        trigger: 'combat-passive',
        whenStance: 'small',
        effect: { kind: 'combat-modifier', appliesTo: 'defense', value: 1 },
      },
    ],
  },
  {
    // Muhammad Ali (Lee vs Ali) — «Float Like a Butterfly / Sting Like a Bee»
    // (STANCE). Печатный текст (scraped, verbatim): «Begin the game with your
    //   stance on Float Like a Butterfly. After you attack, if you won the
    //   combat, change stances. FLOAT LIKE A BUTTERFLY: You can attack from 2
    //   spaces away. STING LIKE A BEE: Add +2 to your attacks.»
    // FLOAT: пассивная дальность атаки 2 (stance.attackRange). STING: +2 к
    // атакам (combat-modifier, whenStance sting). Старт на FLOAT (default).
    // АВТО-ФЛИП: после атаки, ЕСЛИ выиграл бой (won-combat) — сменить стойку
    // (set-stance toggle), переиспользуя after-attack/won-combat машинерию.
    // Слаг подтверждён через slugifyHeroName('Muhammad Ali') → 'muhammad-ali'.
    heroId: 'muhammad-ali',
    abilityName: 'Float Like a Butterfly / Sting Like a Bee',
    description:
      'Start on FLOAT. After you attack, if you won the combat, change stances. ' +
      'FLOAT: may attack from up to 2 spaces away. STING: +2 to attacks.',
    stances: [
      { id: 'float', label: 'Float Like a Butterfly', default: true, attackRange: 2 },
      { id: 'sting', label: 'Sting Like a Bee' },
    ],
    rules: [
      {
        // STING: +2 к атаке — только пока стойка sting
        trigger: 'combat-passive',
        whenStance: 'sting',
        effect: { kind: 'combat-modifier', appliesTo: 'attack', value: 2 },
      },
      {
        // Авто-флип после выигранной атаки (альтернация float↔sting)
        trigger: 'after-attack',
        condition: 'won-combat',
        effect: { kind: 'set-stance', to: 'toggle' },
      },
    ],
  },
  // NB: триггер 'after-defense' + AfterCombatContext.defenderPlayerId — инфра
  // для defender-side способностей (зеркало 'after-attack'), пока без героя:
  // реальный Spider-Man = info-reveal («оппонент раскрывает значение карты до
  // защиты»), это COMPLEX-механика, не draw — намеренно НЕ реализован здесь.
];
