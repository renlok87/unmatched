# 08 — Герои и способности: полная документация

> Источники кода:
> - `backend/src/game-engine/abilities/hero-ability-registry.ts` — реестр `HeroAbilityRegistry`, интерфейсы хуков
> - `backend/src/game-engine/abilities/ability-config.ts` — DSL `AbilityConfig` / `ABILITY_CONFIGS` (26 декларативных героев)
> - `backend/src/game-engine/abilities/generic-hero-ability.handler.ts` — интерпретатор правил `GenericHeroAbilityHandler`
> - `backend/src/game-engine/abilities/heroes/` — hand-written обработчики: `daredevil.handler.ts`, `ms-marvel.handler.ts`, `arthur.handler.ts`
> - `backend/src/game-engine/services/game-action-executor.service.ts` — точки диспетчеризации хуков движком
> - `backend/src/game-engine/game-engine.module.ts` — регистрация (2 hand-written extended + 1 classic + цикл по `ABILITY_CONFIGS`)
> - Статы героёв/дек: `scraped-data/api/heroes/*.json` (сеется в БД через `backend/prisma/seed-scraped.ts`); контент-модуль: `backend/src/content/data/heroes/{daredevil,ms-marvel}.ts`
>
> **Итого героев со способностями в реестре: 29** = 26 декларативных (`ABILITY_CONFIGS`) + 2 extended hand-written (daredevil, ms-marvel) + 1 classic hand-written (king-arthur).

---

## 1. Общая система способностей

### 1.1 Архитектура

Существует два типа обработчиков (оба регистрируются в `HeroAbilityRegistry`):

| Тип | Интерфейс | Регистрация | Кто |
|---|---|---|---|
| Классический | `HeroAbilityHandler` (`registry.register`) | `handlers: Map` | king-arthur (`arthur.handler.ts`) |
| Расширенный | `ExtendedHeroAbilityHandler` (`registry.registerExtended`) | `extendedHandlers: Map` | daredevil, ms-marvel + все 26 `GenericHeroAbilityHandler` |

`GenericHeroAbilityHandler` — data-driven интерпретатор: каждый герой описывается декларативным `AbilityConfig` (массив правил `rules: AbilityRule[]`, опц. `attackRange`, опц. `stances`), и один generic-класс исполняет их против `GameState`.

### 1.2 Хуки и точки вызова движком

| Хук (интерфейс) | Когда вызывается движком | Метод реестра | Точка в executor |
|---|---|---|---|
| `onTurnStart(state, playerId)` | В начале хода игрока — встраивается в `advanceTurn` в момент фактической передачи хода (фаза ACTION_MANEUVER); после хука пере-проверяется game-over (turn-damage мог убить) | `triggerOnTurnStartExtended(slug,…)` | `advanceTurn → triggerHeroTurnStart` (~стр. 288) |
| `onTurnEnd(state, playerId)` | В конце хода завершающего игрока, до передачи хода | `triggerOnTurnEndExtended` | `advanceTurn → triggerHeroTurnEnd` (~стр. 308) |
| `onCombat(state, ctx)` | Во время резолва боя (в проде фактически no-op у всех героев; Daredevil/Ms.Marvel активируются отдельными мутациями) | `triggerOnCombat` | combat-путь executor |
| `onAfterCombat(state, ctx: AfterCombatContext)` | ПОСЛЕ применения урона/флагов поражения, ДО передачи хода. `AfterCombatContext`: `playerId` (атакующий), `defenderPlayerId`, `attackerFighterId/defenderFighterId`, `won` (finalAttack > finalDefense; ничья → false), `damageDealt`, `firstLossThisTurn`. Диспетчеризуется дважды: для атакующего героя (триггер `after-attack`) и для защитника (`after-defense`, по `defenderPlayerId`) | `triggerOnAfterCombat` | ~стр. 317–351 |
| `onFighterDefeated(state, defeatedFighter)` | Когда боец помечен `isDefeated` — ПОСЛЕ установки флага, ДО game-over/передачи хода. Диспетчеризуется герою ВЛАДЕЛЬЦА повергнутого бойца (реакция на гибель своего сайдкика) | `triggerOnFighterDefeated` | ~стр. 379 |
| `onFighterMoved(state, movedFighter, fromPos, toPos)` | РЕАКТИВНЫЙ кросс-героевый: после применения движения executor проходит по диффу позиций (`applyMoveReactions`) и дёргает **каждый** зарегистрированный handler по цепочке (state протягивается) | `triggerOnFighterMoved` | `applyMoveReactions` (~стр. 395–420, вызовы на 546/829/945) |
| `canAttackAtRange(attackerId, defenderId, range, stance?)` | При валидации атаки (`executeAttack`): additive-хук — может РАЗРЕШИТЬ дальнюю атаку, но НИКОГДА не запрещает обычную (range 1). 4-й параметр `stance` — id текущей стойки атакующего | `canAttackAtRange` | ~стр. 1038 |
| `getStanceIds()` | Валидация мутации `setStance`; непустой результат ⇒ герой stance-aware | `getStances` | ~стр. 1914 |
| `getCombatModifiers(ctx, fighter, role)` | Во время расчёта боя — простые модификаторы без GameState | `getExtendedCombatModifiers` | combat-расчёт |
| `getStatefulCombatModifiers(state, ctx, fighter, role)` | Во время расчёта боя — модификаторы с доступом к GameState (условия по доске/флагам хода). ADD-семантика, суммируются с классическим путём | `getStatefulCombatModifiers` | ~стр. 1483–1492 (для attacker и defender) |
| `getAuraCombatModifiers(state, beneficiary, role)` | Во время боя бенефициара: консультируются **все** extended-handler'ы — аура исходит от героя, ОТЛИЧНОГО от героя бойца (Oda-style) | `getAuraCombatModifiers` | ~стр. 1506–1509 |
| `applyCombatModifier / onMove / onDefeat / onTurnStart / onTurnEnd` (классические, `GameEvent[]`) | Легаси: `onMove/onDefeat` в проде никогда не вызывались (мёртвые); `triggerOnTurnStart` — только логирование | `applyCombatModifiers`, `triggerOnMove`, … | — |
| `allowsAttackBoost` / `allowsDefenseBoost` (флаги) | Разрешают BOOST атаки/защиты картой из руки, даже если на играемой карте нет BOOST-эффекта (King Arthur) | читается CombatResolver | — |

### 1.3 Декларативный DSL (`AbilityRule = trigger + condition? + effect`)

**Триггеры** (`AbilityTrigger`):
- `combat-passive` — пассивный модификатор атаки/защиты во время боя (через `getStatefulCombatModifiers`);
- `turn-start` / `turn-end` — эффект в начале/конце хода;
- `after-attack` — после резолва боя, применяется к атакующему игроку;
- `after-defense` — зеркало для защищающегося игрока (по `ctx.defenderPlayerId`; инфра готова, героя пока нет — Spider-Sense намеренно не реализован);
- `sidekick-defeated` — реакция на гибель своего сайдкика (через `onFighterDefeated`);
- `enemy-hero-left-my-zone` — реактивный кросс-героевый on-move триггер (через `onFighterMoved`).

**Условия** (`AbilityCondition`): `always` (default), `attacking`, `defending`, `self-health-below-defender`, `all-own-sidekicks-defeated`, `{handSizeEquals: N}`, `no-enemy-in-own-zone`, `won-combat`, `lost-combat`, `has-not-maneuvered-this-turn`, `has-attacked-this-turn`, `first-lost-combat-this-turn`, `won-combat-and-all-sidekicks-defeated`.

**Эффекты** (`AbilityEffect`, различаются по `kind`):
| kind | Что делает |
|---|---|
| `combat-modifier` | ADD к атаке/защите/обеим (`appliesTo`, `value`) |
| `combat-modifier-per-count` | ADD = `valuePer × count`; count-стратегия: `own-fighters-adjacent-to-defender-excl-self` (живые союзники кроме себя, смежные с защитником, manhattan = 1). Выдаётся только при count > 0 |
| `aura-combat-modifier` | Герой-гранитель баффает ДРУГИХ дружественных бойцов в своей зоне (`scope: allies-in-my-zone'`) во время ИХ боя; сам герой бонус не получает |
| `turn-effect` | `draw` N / `drawToHandSize` N / `heal` N (герою, не выше max) / `gainAction` N |
| `pending-move` | Порождает MOVE `PendingEffect` (C2), резолвится мутацией `resolvePendingEffect`; target: `attacker` / `own-hero` / `any-own` (свои бойцы — модель не поддерживает движение чужих) |
| `turn-damage` | Авто-урон `value` первому подходящему врагу: `enemy-in-zone` (в зоне героя) или `enemy-adjacent` (смежному); опц. `thenDraw` — добор только при реальном попадании. Цель: `health = max(0, health - value)`, при 0 — `isDefeated` + recheck game-over |
| `discard-random` | Сброс `count` карт из руки действующего игрока (детерминированно первые N; «random» не моделируется) |
| `reactive-damage` | Урон `value` бойцу, который только что переместился (цель задаёт движок — `movedFighter`) |
| `set-stance` | Смена стойки: `to: '<id>'` или `'toggle'` (для 2-стоечных) |
| `cycle-stance` | Следующая стойка по циклу (для будущих 3-стоечных, напр. Moon Knight) |

**Гейтинг по стойке**: правило с полем `whenStance: '<id>'` активно только в текущей стойке (читается из `metadata.heroStances[ownerId]`, фолбэк — стойка `default:true` или первая).

**Стойки** (`StanceConfig`): `id`, `label`, `default?`, `attackRange?` (дальность атаки в этой стойке — ПЕРЕОПРЕДЕЛЯЕТ `config.attackRange`, читается `canAttackAtRange`), `combat?` (фиксированный модификатор пока стойка активна).

**Дальность атаки** (`config.attackRange`): максимальная Manhattan-дистанция атаки, игнорируя зональные ограничения (базовая дальность всех — 1).

---

## 2. Герои реестра (29)

Формат: **slug** — Имя; атака (melee/range); health; movement; сайдкики (hp/move/атака). Затем — способность как реализована в коде, затем деки.

### 2.1. luke-cage — Luke Cage
Melee; 13 HP; move 2; сайдкик Misty Knight (6 HP, move 2, range).
- **Способность «Skin Like Titanium»**: `combat-passive`, условие `always`, эффект `combat-modifier` **+2 к защите** постоянно (т.е. получает на 2 урона меньше). Печатный текст «takes 2 less combat damage» смоделирован как постоянный +2 defense.
- **Дека**: 30 карт, 13 уникальных: Pushback (передвинуть противника до 3), Skin Like Titanium (при проигрыше — урон атакующему = полученному урону), Where's My Money? (телепорт к ближайшему врагу +1 действие), Got My Back? (def 1), Regroup ×3 (добор 1/2), Trash Talk ×3 (при победе — конец хода), Daughter of the Dragon (если Misty смежна с противником — значение 6), Commanding Impact ×3 (атака 5 + добор), Get Paid (при победе добор 2), Hero For Hire ×3 (можно BOOST), Sweet Christmas! (атака 6), Power Man (протащить противника через своих — урон всем), Still Standing (при победе — шаффл 2 карт из сброса в колоду).

### 2.2. annie-christmas — Annie Christmas
Melee; 14 HP; move 2; сайдкик Charlie (8 HP, move 2, range).
- **«Long Shot»** (в коде abilityName): `combat-passive`, условие `self-health-below-defender` (health атакующего < health бойца-защитника), эффект **+2 к атаке**. Печатное имя «Necklace of Pearls».
- **Дека**: 30 карт, 12 уникальных: Captain's Orders, Lagniappe (атака 5) ×3, A Few More Pearls ×3 (2 урона всем смежным с Annie), Long Shot (если противник не смежен — значение 5), Slick Talker, The Turn and the River (добор 2), Quite a Pair, Better Together ×4 (лечение себя+союзников), Bottom Dealing (+BOOST нижней карты), Keep Your Hands to Yourself ×3 (двигать обоих бойцов боя до 2), Mississippi Queen ×3, Striking Beauty (1 урон; при победе 2).

### 2.3. eredin — Eredin
Melee; 14 HP; move 2; сайдкики 4× Red Rider (1 HP, move 2, melee).
- **«Unyielding Hordes»**: `combat-passive`, условие `all-own-sidekicks-defeated` (все Red Rider'ы повержены), эффект **+1 к атаке И защите**. Приближение: печатный ENRAGED-бонус «+1 к value карт» смоделирован на обе стороны боя; «move value 3 при ENRAGED» НЕ моделируется.
- **Дека**: 30 карт, 11 уникальных: Brutal strike ×3 (нельзя отменить), Unyielding hordes ×3 (+1 за каждого союзника у противника), Portal defense (при ENRAGED добор 2), Icy guile ×3 (пожертвовать Rider'ом — игнор значения карты противника), Close for the kill ×3 (добор 2 + движение всех своих до 3), Backhand ×3 (враг кладёт карту наверх колоды / сбрасывает при ENRAGED), Foul purpose (при ENRAGED играть в открытую по любой цели), Implacable ×3 (при ENRAGED — как атака), Might of the Aen Elle (добор +1 действие), Skirmish ×3, Wild hunt ×3 (1 урон всем врагам у своих; 2 при ENRAGED).

### 2.4. bloody-mary — Bloody Mary
Melee; 16 HP; move 3; без сайдкиков.
- **«Infinity Mirror»**: `turn-start`, условие `{handSizeEquals: 3}` (ровно 3 карты в руке), эффект `turn-effect` **+1 действие** (gainAction: 1).
- **Дека**: 30 карт, 13 уникальных: Speak Three Times (третье действие — значение 7), Stolen Memories, Feint ×2, Bloody Requiem ×3 (value = value карты противника), Infinity Mirror (двигать бойца боя до 4), Out Of The Mirror (третье действие — добор), Broken Glass ×3, Closer Than She Appears (движение+добор+действие), Evade ×3 (добор 1), Ghostly Touch (третье действие — лечение 3), Jump Scare (нет общих зон со стартом — значение 6), Mirror Image (value = value карты противника), Trick of the Light ×3 (телепорт к противнику).

### 2.5. philippa — Philippa
Range; 12 HP; move 2; сайдкик Dijkstra (6 HP, move 2, melee).
- **«Spellbreaker»** (в коде; печатное «Two Steps Ahead»): `turn-end`, условие `always`, эффект `turn-effect` **drawToHandSize: 4** — добор до 4 карт в руке в конце хода.
- **Дека**: 30 карт, 13 уникальных: Owlform ×3 (сброс карт → +1 за карту), Lightning bolt ×3 (без манёвра — 1 урон всем в зоне), Paralyzing fetters, Spellbreaker ×3 (закончить ход), Redanian plot ×3, Regicide (против героя — значение 6), Spymaster's ruse, Backup plan (health=5 или добор 3), Blinding dust (сброс карты → урон = её BOOST), Chain lightning (1 урон всем врагам зоны), Cunning, Do my bidding, Polymorphy (телепорт).

### 2.6. t-rex — T. Rex
Melee; 27 HP; move 1; без сайдкиков.
- **«Reckless Lunge»**: (а) `config.attackRange: 2` — пассивная дальность атаки 2 (Large fighter), игнорируя зоны; (б) `turn-end` + `always` → `turn-effect` **draw: 1** в конце хода. «Большая база/хвост» физически не моделируется.
- **Дека**: 30 карт, 11 уникальных: Momentous Shift ×3, Ripples in the Water ×3, You're Just Making Her Angry (при победе — вернуть в руку), 65 Million Years of Gut Instinct, 15,000 Pounds of Muscle (атака + 2 урона себе), Closer Than She Appears ×3, Commanding Impact ×3, Reckless Lunge ×3 (3 урона противнику, 3 себе), Terrifying Roar, Thrash ×3 (при победе — 1 урон всем в зоне), When Dinosaurs Ruled the Earth ×4 (при победе добор+действие+2 урона себе).

### 2.7. bigfoot — Bigfoot
Melee; 16 HP; move 3; сайдкик The Jackalope (6 HP, move 3, melee).
- **«It's Just Your Imagination»**: `turn-end`, условие `no-enemy-in-own-zone` (в зоне Bigfoot нет вражеских бойцов), эффект `turn-effect` **draw: 1**.
- **Дека**: 30 карт, 11 уникальных: Savagery ×3, It's Just Your Imagination, Feint ×3, Momentous Shift ×3, Jackalope Horns ×3, Crash Through the Trees, Hoax ×3 (движение до 5 сквозь врагов), Skirmish ×3, Disengage, Larger Than Life ×3 (атака 6), Regroup ×3.

### 2.8. chupacabra — Chupacabra
Melee; 14 HP; move 3; без сайдкиков.
- **«Blood Frenzy»** (печатное «The Hunger»): `after-attack`, условие `always`, эффект `turn-effect` **draw: 1** после каждой своей атаки независимо от исхода.
- **Дека**: 30 карт, 11 уникальных: Ambush ×2, Wounded beast ×3 (≤7 HP — значение 5), Blood in the air ×3, Feeding ×3, Feint ×3, Natural toughness (проигрыш — вернуть в руку), Ravenous lunge ×3 (лечение 1/2), Traveler of the night ×3, The more they struggle ×3 (value = 2×value карты противника), Unsettle, Tooth and tail ×3.

### 2.9. deadpool — Deadpool
Melee; 10 HP; move 2; без сайдкиков.
- **«Regeneration»**: `after-attack`, `always`, `turn-effect` **heal: 1** после своей атаки. Шуточная часть «+5 против Логана» не моделируется.
- **Дека**: 30 карт, 30 уникальных ×1 (юмористическая дека: Take A Knee-подобных нет — от Non-Retinal Scan… до Super Feint; вкл. Underrated Super Heroes (атака 6), Cha-Ching! (BOOST), Klunkin' Heads, Gaze of Stone (при победе 8 урона) и т.д. — полный список в doc 09).

### 2.10. michelangelo — Michelangelo
Melee; 14 HP; move 3; сайдкик April O'Neil (6 HP, move 3, range).
- **«Party Dude»**: `after-attack`, `always`, `turn-effect` **draw: 1** после своей атаки. Печатный лимит руки 3 не моделируется.
- **Дека**: 30 карт, 12 уникальных: Heroes in a half shell, Back for seconds, Hi-yaaaaah!! ×3, Boisterous beatdown ×3, Let's go ×3, Michelangelo is a party dude!!, Cowabunga!! ×3, Nunchaku ×2, Guaranteed delivery ×3, Shell insertion, Turtle power! ×2 (BOOST), Hard-hitting investigation ×3.

### 2.11. angel — Angel
Melee; 16 HP; move 2; сайдкик Faith (8 HP, move 2, melee).
- **«Fallen Grace»**: `after-attack`, условие `lost-combat` (бой не выигран — `ctx.won === false`; ничья тоже считается проигрышем), эффект `turn-effect` **draw: 1**.
- **Дека**: 30 карт, 12 уникальных: Regroup ×3, Brooding, Haunted by the Faces, Angelus Scourge of Europe ×3 (атака 5), Disengage ×3, The Rogue Slayer, Cursed with a Soul, Feint ×3, Five by Five, Killer of the Dead ×3, Momentous Shift ×3, Wisdom of Ages (атака + добор).

### 2.12. golden-bat — Golden Bat
Melee; 18 HP; move 3; сайдкик Daisy (6 HP, move 2, melee).
- **«The First Superhero»**: `combat-passive`, условие `has-not-maneuvered-this-turn` (`state.metadata.maneuveredThisTurn` falsy у активного игрока), эффект **+2 к атаке**.
- **Дека**: 30 карт, 12 уникальных: Terrifying Roar ×3, Vaporizing Eyebeams ×3, Alpine Fortress ×3, He Laughs at Your Feebleness, Imposing Presence, Like a Flash of Golden Light ×3 (движение 5), Skirmish ×2, A Punch to Shake the Earth ×3, Arrive Just in Time, Insight of the Ancients, Sight Beyond Sight ×3, Super Strength (атака 5) ×2.

### 2.13. ancient-leshen — Ancient Leshen
Range; 13 HP; move 1; сайдкики 2× Wolf (1 HP, move 3, melee).
- **«Heart of the Forest»**: `combat-passive`, условие `has-attacked-this-turn` (`state.metadata.attackedThisTurn`), эффект **+3 к атаке**. «Wolves move value 3» (стат сайдкика) НЕ моделируется.
- **Дека**: 30 карт, 11 уникальных: Disturbing howls ×3, Flock of birds ×2, Harrying strike ×3, Nature abounds ×3, Planted feet ×3, Primeval guardian ×3, Primeval slam ×3 (призыв Wolf), Strength of the pack ×3 (scheme: призыв Wolf), Vanish into murder ×2, Wily Fighting ×3, Command the forest ×2.

### 2.14. raphael — Raphael
Melee; 17 HP; move 2; сайдкик Casey Jones (8 HP, move 2, range).
- **«Anger Issues»**: `after-attack`, условие `first-lost-combat-this-turn` (`ctx.won===false && ctx.firstLossThisTurn` — первый проигрыш боя в этом ходу), эффект `turn-effect` **gainAction: 1**.
- **Дека**: 30 карт, 12 уникальных: Batter up! ×3, Break something ×3, Crowd control ×3, Heroes in a half shell, Let's do this! ×3, Payback time! ×3 (проиграл бой в этом ходу — значение 5), Raphael is cool but rude, Relentless, Sai, Slapshot ×3 (Casey смежен — значение 6), Turtle power! ×2 (BOOST), Unbridled rage (сброс защиты → +2 за карту).

### 2.15. robin-hood — Robin Hood
Range; 13 HP; move 2; сайдкики 4× Outlaws (1 HP, move 2, melee).
- **«Trick Shot»**: `after-attack`, `always`, эффект `pending-move` **target: 'attacker', maxSpaces: 2** — после своей атаки порождается MOVE PendingEffect (C2): игрок резолвит перемещение атаковавшего бойца до 2 клеток (или отклоняет).
- **Дека**: 30 карт, 11 уникальных: Snark ×3, Highway Robbery ×4, Wily Fighting ×3, Disarming Shot ×2 (добор = нанесённому урону), Regroup ×3, A Hunter's Eye ×3 (атака 5), Ambush ×2, Steal From the Rich ×3, Defenders of Sherwood ×2 (добор + воскрешение Outlaw), Feint ×3, Piercing Shot ×2 (добор 2).

### 2.16. leonardo — Leonardo
Melee; 16 HP; move 2; сайдкик Splinter (9 HP, move 2, melee).
- **«Tactical Genius»** (печатное «Team Tactics»): `turn-start`, `always`, эффект `pending-move` **target: 'any-own', maxSpaces: 1** — в начале хода можно двинуть любого СВОЕГО бойца на 1 клетку. Приближение MVP: печатная способность двигает любого бойца включая чужих — движение чужих фигур моделью не поддержано.
- **Дека**: 30 карт, 12 уникальных: Protective father ×2, Quick strike ×3, Spatial awareness ×3, Turtle power! ×2 (BOOST), Wise beyond his years ×3, Eat sleep and breath ninjutsu ×3, Fearless leader ×3 (+2 за каждого союзника у противника), For Sensei ×2, Heroes in a half shell, I have a plan ×3, Katana ×2 (атака 6), Leonardo leads ×2.

### 2.17. dracula — Dracula
Melee; 13 HP; move 2; сайдкики 3× The Sisters (1 HP, move 2, melee).
- **«Children of the Night»**: `turn-start`, `always`, эффект `turn-damage` **targetScope: 'enemy-adjacent', value: 1, thenDraw: 1** — в начале хода авто-удар 1 по ПЕРВОМУ смежному врагу (порядок `state.fighters`); при попадании — добор 1. Приближение: «you may»/выбор цели не моделируется; нет цели → no-op без добора.
- **Дека**: 30 карт, 13 уникальных: Prey Upon ×2, Thirst for Sustenance ×3, Beastform ×2 (сброс карт → +1 за карту), Dash ×3, Feint ×3, Exploit ×2 (добор), Mistform ×2 (телепорт + действие), Ambush ×2, Baptism of Blood ×2 (лечение + воскрешение Sister), Do My Bidding ×2, Feeding Frenzy ×2 (+1 за Sister в зоне противника), Look Into My Eyes ×2 (+BOOST карты атаки противника к защите), Ravening Seduction ×3.

### 2.18. medusa — Medusa
Range; 16 HP; move 3; сайдкики 3× Harpies (1 HP, move 3, melee).
- **«Petrifying Gaze»**: `turn-start`, `always`, эффект `turn-damage` **targetScope: 'enemy-in-zone', value: 1** (без thenDraw) — авто-удар 1 по первому вражескому бойцу в зоне Medusa. Приближение то же (без «you may»).
- **Дека**: 30 карт, 11 уникальных: Second Shot ×3 (BOOST), A Momentary Glance ×2 (scheme: 2 урона в зоне), Winged Frenzy ×2, Gaze of Stone ×3 (при победе — 8 урона), Hiss and Slither ×3 (сброс у противника), Feint ×3, Regroup ×3, Snipe ×3 (добор), The Hounds of Mighty Zeus ×2, Clutching Claws ×3, Dash ×3.

### 2.19. bullseye — Bullseye
Range; 14 HP; move 2; без сайдкиков.
- **«Bullseye»**: способность целиком выражена через `config.attackRange: 5` — **может атаковать с расстояния до 5 клеток, игнорируя зоны** (`canAttackAtRange`). `rules` пуст.
- **Дека**: 30 карт, 12 уникальных: I'm Better And I'll Prove It ×2 (уже победил бой — значение 6), Arrogant But Effective ×3 (считается победой + движение 2), World's Greatest Assassin ×2, Tactical Retreat ×3 (телепорт вне общих зон), For My Next Trick ×3 (движение+добор+действие), Feint ×2, I Never Miss ×4 (BOOST или добор), I Planned To Be Here ×2, Ricochet ×3, Master Strategist ×2 (ровно 4 клетки сквозь врагов), Right Between The Eyes ×2, Study The Target ×2.

### 2.20. bruce-lee — Bruce Lee
Melee; 14 HP; move 3; без сайдкиков.
- **«Be Like Water»**: `turn-end`, `always`, эффект `pending-move` **target: 'own-hero', maxSpaces: 1** — в конце хода Bruce Lee может сдвинуться на 1 клетку (MOVE PendingEffect, можно отклонить).
- **Дека**: 30 карт, 17 уникальных: Be Like Water ×4, 5× Jeet Kune Do (Corkscrew Finger Jab, Downward Side Kick, Intercepting Fist, Wrist Lock, High Straight Lead, Short Lead Hook — все «+1 действие»), One-Inch Punch, Taste of Blood, Little Dragon ×2, Momentous Shift ×3, «HOO! WHAAAAAA!», Bring It On, Feint ×3, Nunchaku ×2 (атаки +1 за ход + действие), Regroup ×3, Skirmish ×3.

### 2.21. raptors — Raptors
Melee; 7 HP (за каждого raptor'а); move 3; герой = стая из нескольких бойцов-рапторов, сайдкиков нет.
- **«Pack Tactics»**: `combat-passive`, условие `attacking`, эффект `combat-modifier-per-count` **appliesTo: 'attack', valuePer: 1, countOf: 'own-fighters-adjacent-to-defender-excl-self'** — +1 к атаке за каждого ДРУГОГО живого раптора, смежного с бойцом-защитником (manhattan = 1). Бонус выдаётся только при count > 0.
- **Дека**: 30 карт, 11 уникальных: Disengage ×2, Eviscerate ×2 (атака 5), Pack Hunters ×2 (при победе — 1 урон за раптора у противника), Working Things Out ×2, Coordinated Attack Pattern ×2, Decoy ×4, Eaten Alive ×3, They Remember ×4 (+1 действие), Feint ×3, Ambush ×3, Clever Girl ×3.

### 2.22. oda-nobunaga — Oda Nobunaga
Melee; 13 HP; move 2; сайдкики 2× Honor Guard (6 HP, move 2, melee).
- **«Banner of the Demon King»** (печатное «Master Strategist»): `combat-passive`, `always`, эффект `aura-combat-modifier` **appliesTo: 'both', value: 1, scope: 'allies-in-my-zone'** — ДРУГИЕ дружественные бойцы в зоне Oda получают +1 к значению своих боевых карт (атака и защита); сам Oda бонус НЕ получает. Диспетчеризация через `getAuraCombatModifiers` (консультируются все герои, т.к. аура исходит от другого героя, чем герой бойца).
- **Дека**: 30 карт, 11 уникальных (механика flanked — «во фланке»): Fire and Flames ×3 (фланк — значение 5), Momentous Shift ×2, Pragmatism ×3, Reinforce ×3, Student of War ×2, Battle Maneuvers ×4, Demon King of the Sixth Heaven ×2 (2 урона всем фланк-врагам), Lightning and Thunder ×3, Patience and Strategy ×3, Spring the Trap ×3, Sun and Moon ×2.

### 2.23. achilles — Achilles
Melee; 18 HP; move 2; сайдкик Patroclus (6 HP, move 2, melee). Единственный герой с ТРЕМЯ правилами:
1. `combat-passive` + `all-own-sidekicks-defeated` → `combat-modifier` **+2 к атаке**, пока Patroclus повержен;
2. `after-attack` + `won-combat-and-all-sidekicks-defeated` → `turn-effect` **draw: 1** (победа в бою при поверженном сайдкике);
3. `sidekick-defeated` → `discard-random` **count: 2** — в момент гибели Patroclus сброс 2 карт из руки (через `onFighterDefeated`; «random» детерминированно — первые 2 карты руки).
- **Дека**: 30 карт, 12 уникальных: Achilles' Heel ×3, Feint ×3, Brothers In Arms ×3 (Patroclus жив — +1 действие), Under Achilles' Helm ×3, Skirmish ×3, Test For Weakness ×3, Battle Frenzy ×2 (2 урона обоим), Spear Throw ×2 (scheme: 2 урона в зоне), The Day of Your Doom ×2 (2 урона Patroclus → значение 5), Wily Fighting ×2, Battle Hardened ×2, Blessed By Hermes ×2.

### 2.24. tomoe-gozen — Tomoe Gozen
Range; 14 HP; move 2; без сайдкиков.
- **«Unwavering Resolve»** (печатное «Attack of Opportunity»): триггер `enemy-hero-left-my-zone` → эффект `reactive-damage` **value: 1** — когда вражеский ГЕРОЙ покидает зону Tomoe (был в `fromPos` её зоны, `toPos` вне), она наносит ему 1 урон. Диспетчеризация через кросс-героевый `onFighterMoved`; при 0 HP — isDefeated + game-over recheck после всех реакций.
- **Дека**: 30 карт, 12 уникальных: Deeds of Valor ×3 (макс 2 урона за бой), A Worthy Opponent ×3 (против героя — значение 5), Fearsome Strength ×2, Five Against Thousands ×2, Lord Kiso's Final Stand ×3, Refuse to Retreat ×2, Witness My Last Battle ×2 (атака 7, только по смежному), A Warrior's Way ×2, Confront Any Demon or God ×2, Flash of Steel ×3, Piercing Shot ×3 (добор 2), Skirmish ×3.

### 2.25. alice — Alice (СТОЙКИ)
Melee; 13 HP; move 2; сайдкик The Jabberwock (8 HP, move 2, melee).
- **«Big / Small»**: stance-герой. Стойки: `big` (default), `small`. Правила:
  - `combat-passive` + `whenStance: 'big'` → **+2 к атаке**;
  - `combat-passive` + `whenStance: 'small'` → **+1 к защите**.
  Стойка РУЧНАЯ: выбор при размещении (setStance) и карты «Change size» (Mad as a Hatter / Drink Me / Eat Me / …). Авто-флипа нет.
- **Дека**: 30 карт, 15 уникальных (4 карты «Change size»): Mad as a Hatter ×2, Drink Me ×2, Skirmish ×2, Jaws That Bite ×2, Momentous Shift ×2, Feint ×3, Regroup ×3, The Other Side of the Mushroom, Eat Me ×2, Claws That Catch ×2 (против героя — 5), I'm Late, I'm Late ×3 (движение 5 + смена), Looking Glass ×2, O Frabjous Day!, Snicker-Snack, Manxome Foe ×2.

### 2.26. muhammad-ali — Muhammad Ali (СТОЙКИ)
Melee; 16 HP; move 3; без сайдкиков.
- **«Float Like a Butterfly / Sting Like a Bee»**: stance-герой. Стойки: `float` (default, **attackRange: 2**), `sting`. Правила:
  - `combat-passive` + `whenStance: 'sting'` → **+2 к атаке**;
  - `after-attack` + условие `won-combat` → `set-stance to: 'toggle'` — **авто-флип стойки после каждой выигранной атаки** (float ↔ sting).
  В FLOAT герой может атаковать с 2 клеток (`canAttackAtRange` читает `stance.attackRange`), в STING — только обычная дальность 1, но +2 атака.
- **Дека**: 30 карт, 13 уникальных (эффекты [Butterfly] — только в FLOAT): Jab ×2, Answer the bell ×2, Stick and move ×3, Ali Shuffle ×3, Close and clinch ×3, Momentous Shift ×2, Fancy footwork ×2, Hard to be humble ×3, Louisville lip ×2, Rope-a-dope ×2, Champion of the world ×2, Stronger than the skill ×2, The greatest ×2.

### 2.27. king-arthur — King Arthur (classic handler)
Melee; 18 HP; move 2; сайдкик Merlin (7 HP, move 2, range).
- **«Holy Avenger»** (`arthur.handler.ts`, классический `HeroAbilityHandler`): флаг **`allowsAttackBoost: true`** — King Arthur может BOOST-ить свои атаки картой из руки (в дополнение к BOOST-эффектам карт), даже если на играемой карте нет BOOST-эффекта. `applyCombatModifier` возвращает `[]` (старый выдуманный «+1 к атаке всегда» удалён).
- **Дека**: 30 карт, 16 уникальных: The Lady of the Lake (поиск Excalibur), The Aid of Morgana (добор 2), Prophecy, Excalibur (атака 6) ×1, Momentous Shift ×3, Bewilderment ×2 (телепорт), Command the Storms ×2 (двигать ВСЕХ бойцов), Regroup ×3, Swift Strike ×2, Aid the Chosen One, Divine Intervention ×2 (движение 5), Feint ×3, Noble Sacrifice ×3 (BOOST сверх способности), Restless Spirits, Skirmish ×3, The Holy Grail (≤4 HP → health 8).

### 2.28. daredevil — Daredevil (extended hand-written)
Melee; 17 HP; move 3; без сайдкиков.
- **«Blind Boost»** (`daredevil.handler.ts`, singleton `daredevilHandler`): условие (`canTrigger`): рука ≤ 2 карт (`BLIND_BOOST_MAX_CARDS = 2`) И в колоде есть карты. Активация — отдельной мутацией (не через onCombat): `executeBlindBoost(state, playerId, forAttack)` сбрасывает ВЕРХНЮЮ карту колоды (`drawPile[0]`) и добавляет её **boostValue** к атаке или защите (`createBlindBoostModifier`: ADD-модификатор `source: 'hero-ability-daredevil-blind-boost'`). Вспомогательные методы: `getBoostValue` (превью значения), `peekTopCard` (превью карты), `canTriggerInCombat` (по флагу `isBlindBoostAvailable` в контексте боя).
- Контент-модуль (`backend/src/content/data/heroes/daredevil.ts`): дека из 5 уникальных ×3 = 15 карт: Billy Club (vers 3/буст 2; ровно 1 карта в руке → BOOST), Radar Sense (atk 4/б1; нет общих зон с противником → BOOST), Mania (atk 2/б3; если наносит урон — добор 2), Grappling Hook (vers 2/б2; после боя движение 2), Daredevil (def 4/б1; ≤2 карт в руке → BOOST). Полный печатный скрап-дек — 22 карты / 8 уникальных (вкл. Man Without Fear, Son Of A Boxer, Breather, Devil of Hell's Kitchen, Through Adversity) — см. doc 09.

### 2.29. ms-marvel — Ms. Marvel (extended hand-written)
Melee; 14 HP; move 2; без сайдкиков.
- **«Stretchy»** (`ms-marvel.handler.ts`, singleton `msMarvelHandler`), две части:
  1. **Дальность 2**: `canAttackAtRange` возвращает `range <= 2` (`MS_MARVEL_EXTENDED_RANGE = 2`) — атака с до 2 клеток, игнорируя зоны; `canAttackTarget` проверяет дистанцию по позициям бойцов.
  2. **Движение в начале хода**: `executeTurnStartMove(state, playerId, targetPosition)` — сдвиг на 1 клетку (`TURN_START_MOVE_BONUS = 1`), только на валидную позицию (границы 6×6, не занята бойцом; препятствия/двери — TODO). `getAvailableTurnStartPositions` возвращает 4 соседние клетки. Авто-хук `onTurnStart` зарезервирован и возвращает state без изменений — активация отдельной мутацией.
- Контент-модуль (`backend/src/content/data/heroes/ms-marvel.ts`): дека из 5 уникальных ×3 = 15 карт: Embiggen (atk 3/б3; Ms. Marvel в большем числе зон — значение 6), Big Wind Up (atk 4/б2; нет общих зон — BOOST), Easy Peasy (atk 3/б2; добор 1, при руке ≥4 — 1 урон смежному), Feint (vers 2/б1; отмена эффектов карты противника), Groovy (def 3/б2). Полный скрап-дек — 30 карт / 11 уникальных (вкл. Fangirl, Slingshot, Friends and Family, Gyro and Fries, I'm Not Touching You, Shrink! Shrink! Shrink!, Momentous Shift) — см. doc 09.

---

## 3. Замечания о приближениях (задокументированы в коде)

1. **«you may» не моделируется** для `turn-damage` (Dracula, Medusa) — авто-удар по первому кандидату.
2. **«random» discard** (Achilles) — детерминированный сброс первых N карт.
3. **Движение чужих бойцов** не поддержано моделью PendingEffect (Leonardo — только свои).
4. **Eredin**: ENRAGED «move value 3» и **Ancient Leshen**: «Wolves move 3» — статы сайдкиков не моделируются в способности.
5. **Michelangelo**: лимит руки 3 не моделируется.
6. **`after-defense`-инфра** готова (defenderPlayerId в AfterCombatContext), но героя-пользователя нет; Spider-Sense (info-reveal) — COMPLEX-механика, намеренно не реализована.
7. **T. Rex**: «large fighter» моделируется только атакой с 2 клеток; большая база/хвост — нет.

---

## 4. Чеклист: герои × используемые хуки/механики

✓ = используется. «CP» = combat-passive; «TS» = turn-start; «TE» = turn-end; «AA» = after-attack; «SD» = sidekick-defeated (onFighterDefeated); «MZ» = enemy-hero-left-my-zone (onFighterMoved); «RNG» = canAttackAtRange/attackRange; «Aura» = getAuraCombatModifiers; «PerCount» = combat-modifier-per-count; «Stance» = стойки/getStanceIds; «Boost» = allowsAttackBoost.

| Герой (slug) | CP | TS | TE | AA | SD | MZ | RNG | Aura | PerCount | Stance | Boost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| luke-cage | ✓ | | | | | | | | | | |
| annie-christmas | ✓ | | | | | | | | | | |
| eredin | ✓ | | | | | | | | | | |
| bloody-mary | | ✓ | | | | | | | | | |
| philippa | | | ✓ | | | | | | | | |
| t-rex | | | ✓ | | | | ✓(2) | | | | |
| bigfoot | | | ✓ | | | | | | | | |
| chupacabra | | | | ✓ | | | | | | | |
| deadpool | | | | ✓ | | | | | | | |
| michelangelo | | | | ✓ | | | | | | | |
| angel | | | | ✓ | | | | | | | |
| golden-bat | ✓ | | | | | | | | | | |
| ancient-leshen | ✓ | | | | | | | | | | |
| raphael | | | | ✓ | | | | | | | |
| robin-hood | | | | ✓ | | | | | | | |
| leonardo | | ✓ | | | | | | | | | |
| dracula | | ✓ | | | | | | | | | |
| medusa | | ✓ | | | | | | | | | |
| bullseye | | | | | | | ✓(5) | | | | |
| bruce-lee | | | ✓ | | | | | | | | |
| raptors | ✓ | | | | | | | | ✓ | | |
| oda-nobunaga | | | | | | | | ✓ | | | |
| achilles | ✓ | | | ✓ | ✓ | | | | | | |
| tomoe-gozen | | | | | | ✓ | | | | | |
| alice | ✓ | | | | | | | | | ✓ | |
| muhammad-ali | ✓ | | | ✓ | | | ✓(stance) | | | ✓ | |
| king-arthur | | | | | | | | | | | ✓ |
| daredevil | (onCombat*, отдельная мутация Blind Boost) | | | | | | | | | | |
| ms-marvel | (onCombat — no-op) | (onTurnStart — no-op, движение отдельной мутацией) | | | | | ✓(2) | | | | |

\* Daredevil использует `canTrigger`/`executeBlindBoost`/`getCombatModifiers` своего handler'а (int-механика BOOST из верха колоды), вызываемые из combat-пути executor'а; его `onCombat` — no-op-заглушка.

### Сводка
- **Всего героев в реестре: 29** (26 из `ABILITY_CONFIGS` + daredevil + ms-marvel + king-arthur).
- **Всего описанных механик (правил способностей): 33** — 31 правило в `ABILITY_CONFIGS` (26 героев; у Achilles 3 правила, у Muhammad Ali 2) + Blind Boost (daredevil) + Stretchy (ms-marvel) + Holy Avenger/allowsAttackBoost (king-arthur).
- Деки: все по 30 карт (Deadpool — 30 уникальных ×1; Daredevil — 15 в контент-модуле / 22 в скрапе; Ms. Marvel — 15 в контент-модуле / 30 в скрапе).
