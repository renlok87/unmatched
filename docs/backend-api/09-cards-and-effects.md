# 09. Карты и система эффектов

> Источники: `backend/src/game-engine/models/card.model.ts`, `backend/src/game-engine/effects/` (`card-effect-executor.service.ts`, `effect-text-parser.ts`), `backend/src/content/data/heroes/` (daredevil, ms-marvel), `backend/prisma/` (`seed-scraped.ts`, `backfill-card-effects.ts`), `backend/scraped-data/api/heroes/*.json` (полные деки всех героев).

---

## 1. Модель карты

### 1.1. CardType (`card.model.ts`)

| Тип | Описание |
|---|---|
| `ATTACK` | Атака; значение в `attackValue` |
| `DEFENSE` | Защита; значение в `defenseValue` |
| `SCHEME` | Scheme; разыгрывается как действие (эффекты `ON_PLAY`) |
| `VERSATILE` | Играется и как атака, и как защита; значение пишется в оба поля (`attackValue` + `defenseValue`) |
| `MANEUVER` | Карта движения (`subType: 'Movement'`); играется ради передвижения, бустится другой картой |
| `UNIVERSAL` | Универсальный тип из старых данных enum |

### 1.2. Интерфейс `Card`

| Поле | Тип | Описание |
|---|---|---|
| `id` / `cardId` | `string` | Идентификаторы экземпляра / шаблона |
| `name`, `nameEn`, `nameRu` | `string` | Имя карты (en/ru) |
| `cardType` | `CardType` | Тип карты |
| `attackValue` | `number?` | Печатное значение атаки |
| `defenseValue` | `number?` | Печатное значение защиты |
| `boostValue` | `number?` | BOOST-значение (прибавляется при сбросе карты как буста / BLIND BOOST) |
| `effects` | `CardEffect[]?` | Структурированные эффекты |
| `text` | `string?` | Текст эффекта из БД — для отображения и ручного применения (Game Tester) |
| `bannerName` | `string?` | Кто может играть карту: `'Any'`/пусто — любой боец, иначе имя бойца (`'Medusa'`, `'Harpy'`); валидация `bannerAllows` в `game-rules.validator` |

### 1.3. Интерфейс `CardEffect`

| Поле | Тип | Описание |
|---|---|---|
| `id` | `string` | Идентификатор эффекта |
| `type` | `EffectType` | Тип (раздел 2) |
| `timing` | `EffectTiming` | Когда применяется |
| `target` | `EffectTarget?` | Цель |
| `value` | `number?` | Числовое значение (+N, количество карт и т.п.) |
| `condition` | `string?` | Legacy-условие (`'low_health'` = здоровье < 50% макс.) |
| `when` | `EffectCondition?` | Структурное условие (`kind` + `value`) |
| `count` | `CountSpec?` | Счётчик для `VALUE_PER_COUNT` / draw-per-damage |
| `optional` | `boolean?` | «You may …» (MVP: авто-применение выгодных) |
| `fighterName` | `string?` | Имя бойца для `target: NAMED_FIGHTER` |
| `boostSource` | `BoostSource?` | Откуда берётся BOOST-карта (для `type: BOOST`) |
| `blind` | `boolean?` | BLIND BOOST — карта вскрывается с верха колоды (Daredevil) |
| `options` | `ChooseOption[]?` | Варианты для `CHOOSE_ONE` (label + effects) |
| `chooseCount` | `number?` | Сколько опций выбирается (default 1) |
| `text` | `string?` | Исходное предложение — для лога / `manualEffects` |
| `source` | `'parser' \| 'manual'?` | Происхождение; парсер не перезаписывает `manual` при backfill |
| `parserVersion` | `number?` | Версия парсера, сгенерировавшего эффект |

`normalizeCardEffects(raw, cardId)` — нормализация Prisma `Card.effects` (Json): двойная сериализация → повторный parse; любой мусор → один `UNSUPPORTED`-эффект с сырым текстом; никогда не бросает.

### 1.4. EffectConditionKind (условия `when`)

| Kind | Значение |
|---|---|
| `WON_COMBAT` / `LOST_COMBAT` | Сторона выиграла/проиграла бой; ничья = победа защитника (правило Unmatched). В during-стадии исход неизвестен → false (сработает в AFTER_COMBAT) |
| `IS_ATTACKING` / `IS_DEFENDING` | Сторона атакует / защищается в текущем бою |
| `ADJACENT_TO_OPPONENT` / `NOT_ADJACENT_TO_OPPONENT` | Смежность с противником (`AdjacencyService.isAdjacent`) |
| `DECK_EMPTY` | Колода игрока пуста |
| `HAND_COUNT_AT_MOST` / `HAND_COUNT_AT_LEAST` | Карт в руке ≤ / ≥ `value` |
| `HEALTH_AT_MOST` | Здоровье бойца ≤ `value` |
| `MOVED_THIS_TURN` | Позиция ≠ снапшоту `metadata.turnStartPositions` («started this turn in a different space») |
| `OPPONENT_IS_HERO` | Противник — тип `HERO` |
| `SHARES_ZONE_WITH_OPPONENT` / `NOT_SHARES_ZONE_WITH_OPPONENT` | Мультизонность (C1): пересечение зон клеток (`isInSameZone`; Ms. Marvel) |

### 1.5. CountSpec / CountSource

`{ source, namePrefix?, per? }`; `per` — множитель за единицу (default 1).

| Source | Считает |
|---|---|
| `FRIENDLY_ADJACENT_TO_OPPONENT` | Другие (не сам играющий) живые союзные бойцы, смежные с противником |
| `CARDS_IN_HAND` | Карты в руке игрока |
| `DISCARD_NAME_PREFIX` | Карты в своём сбросе с именем на `namePrefix`, кроме самой карты («for each other VOYAGE card…») |
| `DAMAGE_DEALT` | Урон, нанесённый этой стороной (AFTER_COMBAT-контекст) |
| `DAMAGE_TAKEN` | Урон, полученный этой стороной |

### 1.6. BoostSource

| Source | Откуда карта |
|---|---|
| `PLAYER_CHOICE_HAND` | Игрок сбрасывает карту из руки по выбору (`boostCardId` в мутации, эпик A7) |
| `SELF_DECK_TOP` | Верх своей колоды — BLIND BOOST, автоматически (Daredevil) |
| `OPPONENT_RANDOM_HAND` | Случайная карта из руки оппонента («opponent discards 1 random card. Add its BOOST…») |

---

## 2. EffectType — полная семантика (21 значение)

Исполнение — `CardEffectExecutorService.applyOneEffect`. Стадии боя: **ON_REVEAL** (вскрытие; первым атакующий) → **DURING_COMBAT** (модификаторы; внутри стороны порядок: `SET_VALUE` → `MODIFY_*` → `VALUE_PER_COUNT` → прочее) → урон (`combat-resolver`) → **AFTER_COMBAT** (сначала все эффекты атакующего, затем защитника). Scheme-карты: `ON_PLAY` + `AFTER_COMBAT`-тексты («после розыгрыша»). `TURN_START`/`TURN_END` — по всем картам в руке.

| # | EffectType | Что делает | Типовой timing | Цель / особенности |
|---|---|---|---|---|
| 1 | `MODIFY_ATTACK` (legacy) | +`value` к значению атаки | `DURING_COMBAT` | Возвращает `valueDelta` |
| 2 | `MODIFY_DEFENSE` (legacy) | +`value` к значению защиты | `DURING_COMBAT` | Возвращает `valueDelta` |
| 3 | `MODIFY_VALUE` | +N к значению СВОЕЙ карты; роль (атака/защита) решается стороной боя — для VERSATILE | `DURING_COMBAT` | `valueDelta` |
| 4 | `SET_VALUE` | «the value of this card is N instead» — значение := N | `DURING_COMBAT` | Порядок 0; при нескольких последний выигрывает; комбо `SET_VALUE 0` + `VALUE_PER_COUNT CARDS_IN_HAND` |
| 5 | `VALUE_PER_COUNT` | +`per × count`, count из `CountSpec` | `DURING_COMBAT` | Порядок 2; счётчики см. 1.5 |
| 6 | `BOOST` | +`boostValue` карты из `boostSource` к значению | `DURING_COMBAT` | `SELF_DECK_TOP` — авто-сброс верха колоды (BLIND BOOST), пустая колода → fail; `OPPONENT_RANDOM_HAND` — оппонент сбрасывает случайную карту, += её boost (нет карт у оппонента → fail); `PLAYER_CHOICE_HAND` — executor ничего не делает, выбор в мутации `boostCardId` |
| 7 | `DAMAGE` | Наносит `value` урона целям (health clamp ≥ 0) | `AFTER_COMBAT` / `ON_PLAY` | Нет валидных целей → `success: false 'No valid targets'` |
| 8 | `HEAL` | Восстанавливает `value` HP (≤ maxHealth) | любой | Цели через `resolveTargets` |
| 9 | `MOVE` | Движение бойца на `value` клеток | любой | Требует выбора игрока → `metadata.pendingEffects` (MOVE), резолв `resolvePendingEffect`; текст также в `manualEffects`; протухает в `advanceTurn` |
| 10 | `PLACE` | Размещение бойца в клетку | любой | Аналогично MOVE → pendingEffect (PLACE); `target: OPPOSING_FIGHTER` → `targetsOpponent` |
| 11 | `DRAW_CARD` | Добрать `value` (default 1) карт | любой | Цель — сам игрок |
| 12 | `DISCARD` | Сбросить `value` (default 1) случайных карт своей руки | любой | Пустая рука — не ошибка |
| 13 | `OPPONENT_DISCARD` | Оппонент сбрасывает `value` случайных карт | любой | target `OPPONENT_PLAYER`; нет оппонента → fail |
| 14 | `CANCEL_EFFECTS` | «Cancel all effects on your opponent's card» | `ON_REVEAL` | `cancelOpposingCard`: отменённая карта не исполняет reveal/during/after-эффекты, но ПЕЧАТНОЕ значение сохраняется; отменённый защитник не отменяет в ответ |
| 15 | `RETURN_TO_HAND` | Вернуть ЭТУ карту из своего сброса в руку | любой | Карты нет в сбросе или рука полна (`maxSize`) → fail |
| 16 | `IMMOBILIZE` | «cannot leave their space this turn» | любой | Вешает `{ type: 'immobilized', duration: 'turn' }` на цели |
| 17 | `GAIN_ACTION` | +`value` (default 1) к `metadata.actionsRemaining` | `ON_PLAY` | — |
| 18 | `PREVENT_DAMAGE` | «Prevent all damage» | `DURING_COMBAT` | `preventDamage` для своей роли (атакующий/защитник) |
| 19 | `END_TURN` | Завершает ход (`actionsRemaining = 0`) | `ON_PLAY` | — |
| 20 | `CHOOSE_ONE` | «Choose one: …» — интерактивный выбор `chooseCount` опций из `options` | `ON_PLAY` | pendingEffect `CHOOSE_ONE`; резолв `resolvePendingEffect(optionIndex)` → `executeChosenEffects` (боевые эффекты опций вне боя уходят в manualEffects; вложенный MOVE/PLACE порождает новый pendingEffect); нет распознанных опций → manualEffects |
| 21 | `UNSUPPORTED` | Маркер нераспознанного текста; НЕ исполняется | — | Текст в `manualEffects`, warn-лог, метрика `unsupported-effect`; игра не блокируется |

### 2.1. EffectTiming

| Timing | Когда исполняется |
|---|---|
| `ON_REVEAL` | При вскрытии карт в `COMBAT_RESOLVE` (до during; первым атакующий; отменённая карта не исполняет) |
| `DURING_COMBAT` | Расчёт финальных attack/defense (модификаторы, BOOST, PREVENT_DAMAGE) |
| `AFTER_COMBAT` | После урона; для scheme-карт — «после розыгрыша» (исполняется и при `ON_PLAY`) |
| `ON_PLAY` | Розыгрыш scheme-карты (вместе с `AFTER_COMBAT`-текстами) |
| `BEFORE_COMBAT` | Значение enum; отдельной стадии исполнения в executor нет |
| `ON_DISCARD` | Значение enum; отдельной стадии исполнения в executor нет |
| `TURN_START` / `TURN_END` | По всем картам в руке игрока (`executeTurnStartEffects` / `executeTurnEndEffects`) |

### 2.2. EffectTarget

| Target | Разрешение |
|---|---|
| `SELF` (default) | Играющий боец (или первый живой боец игрока) |
| `OPPOSING_FIGHTER` | Противник в текущем бою |
| `ATTACKER` / `DEFENDER` | Роли в текущем бою |
| `ALL_ENEMIES` | Все живые чужие бойцы |
| `ALL_ALLIES` | Все живые свои бойцы |
| `ENEMIES_ADJACENT_TO_SELF` | «each opposing fighter adjacent to your fighter» |
| `ADJACENT_ENEMY` | Один смежный враг; MVP: при нескольких кандидатах — первый валидный + warn; якорь — `fighterName` («a fighter adjacent to Daredevil») |
| `NAMED_FIGHTER` | По `fighterName` среди своих бойцов («Dr. Watson recovers…»); матч «Harpy 2» ↔ «Harpy», регистронезависимо |
| `OPPONENT_PLAYER` | Игрок-оппонент (для `OPPONENT_DISCARD`) |

### 2.3. Контракты executor

- Эффекты НИКОГДА не меняют `sequenceNumber` — ровно +1 на мутацию делает executor действий (`game-action-executor`).
- Нераспознанное/неподдержанное (UNSUPPORTED, MOVE/PLACE с выбором игрока) не блокирует игру: текст в `manualEffects`, warn + метрика.
- Бойцы и игроки — РАЗНЫЕ id: `*FighterId` из fighters, `*PlayerId` — userId.
- Урон/лечение — иммутабельные обновления; ничья в бою = победа защитника.

### 2.4. Парсер текстов и backfill

`effect-text-parser.ts` (`PARSER_VERSION`) разбирает текстовые поля Prisma-карты: `effectImmediately → ON_REVEAL`, `effectDuring → DURING_COMBAT`, `effectAfter → AFTER_COMBAT` (+ `effectBoost`, `effectOngoing`); нераспознанные предложения → `UNSUPPORTED` (игра не блокируется). `prisma/backfill-card-effects.ts` — идемпотентный backfill: карты с эффектами `source: 'manual'` не перезаписываются (ручная правка через админку `updateCard` приоритетна); флаги `--dry-run`, `--hero=<name>`; отчёт покрытия по героям.

---

## 3. Правила BOOST

**Когда разрешён BOOST** (`game-action-executor.service.ts → boostAllowed`):
- Играемая карта (атака/защита) имеет эффект `type: BOOST` с `boostSource: PLAYER_CHOICE_HAND` (или без источника), **или**
- Способность героя разрешает (`abilityRegistry`: `allowsAttackBoost` / `allowsDefenseBoost`; например King Arthur — буст атаки).

**Механика (эпик A7):**
- Игрок передаёт `boostCardId` в мутации атаки/защиты; карта обязана быть в его руке, иначе `Boost card not in hand`.
- Нельзя бустить той же самой разыгранной картой (`boostCard.id === playedCard.id` → ошибка).
- BOOST-карта сбрасывается; её `boostValue` прибавляется к `attackValue` / `defenseValue`; после сброса буст-карты — добор 1 карты (правила Unmatched).
- Лимит — одна BOOST-карта на разыгранную карту (одно поле `boostCardId`); дальнейший стакинг — только через эффекты `BOOST` на самой карте (SELF_DECK_TOP / OPPONENT_RANDOM_HAND).

**BOOST манёвра (передвижение):** MANEUVER играется как действие движения; `boostCardId` (legacy — `cardId`) даёт +`boostValue` к очкам движения (`getFighterMovement(fighter) + boostValue`, проверка в `game-rules.validator`); буст добавляется каждому передвигаемому бойцу; буст-карта в сброс + добор 1.

**BLIND BOOST (Daredevil):** способность героя — при бое с ≤2 картами в руке можно сбросить верхнюю карту своей колоды и прибавить её `boostValue` (эффект `BOOST` + `boostSource: SELF_DECK_TOP`).

**BOOST за счёт оппонента:** `OPPONENT_RANDOM_HAND` — оппонент сбрасывает случайную карту из руки, её `boostValue` прибавляется к вашему значению.

---

## 4. Полный реестр карт (70 героев, 880 карт из scraped-data / сидов)

Формат: **Название** — тип, значение, BOOST, ×копий; эффекты словами (поля effect / immediately / during / after / boost / ongoing из scraped-данных). Типы: `attack`, `defense`, `scheme`, `versatile`, `maneuver`.

Эталонные деки в коде (`src/content/data/heroes/`): **Daredevil** ( Billy Club, Radar Sense, Mania, Grappling Hook, Daredevil) и **Ms. Marvel** (Embiggen, Big Wind Up, Easy Peasy, Feint, Groovy) — см. scraped-таблицы ниже; там же тексты их эффектов.

### Achilles (Battle of Legends, Volume Two) — здоровье 18, движение 2

Способность: When Patroclus is defeated, discard 2 random cards.  While Patroclus is defeated: - Add +2 to the value of all Achilles' attacks. - If Achilles wins combat, draw 1 card.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Achilles' Heel** | defense | 4 | 2 | 3 | **after:**  If you lost the combat, your opponent gains 1 action. |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Brothers In Arms** (Patroclus) | attack | 4 | 2 | 3 | **after:**  If Patroclus is not defeated, gain 1 action. |
| **Under Achilles' Helm** | defense | 2 | 4 | 3 | **immediately:**  If Patroclus is not defeated, Achilles may swap spaces with him. If he does, Patroclus is now the defender. |
| **Skirmish** (Any) | versatile | 4 | 1 | 3 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **Test For Weakness** (Any) | attack | 1 | 3 | 3 | **after:**  RELENTLESS ASSAULT: 3 ATK |
| **Battle Frenzy** (Patroclus) | attack | 3 | 2 | 2 | **after:**  Deal 2 damage to both fighters in the combat. |
| **Spear Throw** | scheme | — | 1 | 2 | **effect:** Deal 2 damage to an opposing fighter in Achilles' zone. |
| **The Day of Your Doom** (Patroclus) | attack | 3 | 2 | 2 | **during:**  You may deal 2 damage to Patroclus. If you do, the value of this attack is 5 instead. |
| **Wily Fighting** (Any) | versatile | 3 | 1 | 2 | **after:** Deal 1 damage to each opposing fighter adjacent to your fighter. |
| **Battle Hardened** (Any) | versatile | 2 | 2 | 2 | **after:**  Choose a card in your discard pile and return it to your hand. |
| **Blessed By Hermes** (Any) | versatile | 3 | 1 | 2 | **after:**  Move each of your fighters up to 3 spaces. They may move through opposing fighters. |

### Alice (Battle of Legends, Volume One) — здоровье 13, движение 2

Способность: When you place Alice, choose whether she starts the game BIG or SMALL. When Alice is BIG, add 2 to the value of her attack cards. When Alice is SMALL, add 1 to the value of her defense cards.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Mad as a Hatter** (Allice) | versatile | 3 | 1 | 2 | **after:**  Move each of your fighters up to 2 spaces. Change size. |
| **Drink Me** (Allice) | scheme | — | 2 | 2 | **effect:** Draw 2 cards. Change size. |
| **Skirmish** (Any) | versatile | 4 | 1 | 2 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **Jaws That Bite** (The Jabberwock) | attack | 4 | 2 | 2 | **after:**  Deal 2 damage to any one fighter adjacent to the Jabberwock. |
| **Momentous Shift** (Any) | versatile | 3 | 1 | 2 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Regroup** (Any) | versatile | 1 | 2 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **The Other Side of the Mushroom** (Allice) | attack | 3 | 4 | 1 | **after:**  Move Alice up to 3 spaces. Change size. |
| **Eat Me** (Allice) | scheme | — | 3 | 2 | **effect:** Move Alice up to 3 spaces. Change size. |
| **Claws That Catch** (The Jabberwock) | attack | 3 | 2 | 2 | **during:**  If the opposing fighter is a hero, this card's value is 5 instead. |
| **I'm Late, I'm Late** (Allice) | versatile | 2 | 3 | 3 | **after:**  Move Alice up to 5 spaces. Change size. |
| **Looking Glass** (Allice) | defense | 2 | 4 | 2 | **after:**  Choose 2 different effects: - draw 2 cards - Alice recovers 3 health - place Alice in any other space |
| **O Frabjous Day!** (Allice) | attack | 4 | 4 | 1 | **after:**  Change size. |
| **Snicker-Snack** (Allice) | attack | 3 | 4 | 1 | **after:**  If you won the combat, look at your opponent's hand and choose 1 card for them to discard. |
| **Manxome Foe** (Any) | versatile | 3 | 2 | 2 | **during:**  Discard the top card of your deck. Add its BOOST value to this card's value. |

### Ancient Leshen (The Witcher - Steel & Silver) — здоровье 13, движение 1

Способность: HEART OF THE FOREST Add +3 to the value of the Leshen's attacks if it already attacked this turn. Your Wolves have a move value of 3.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Disturbing howls** (Wolf) | attack | 1 | 1 | 3 | **after:** Move the opposing fighter up to 2 spaces. Gain 1 action. |
| **Flock of birds** (Leshen) | attack | 5 | 1 | 2 | **after:** You may place the Leshen in any space. |
| **Harrying strike** (Wolf) | versatile | 2 | 2 | 3 | **during:** Add +2 to this card's value for each of your fighters adjacent to the opposing fighter. |
| **Nature abounds** (Any) | attack | 2 | 2 | 3 | **after:** Draw 1 card for each of your fighters adjacent to the opposing fighter. |
| **Planted feet** (Any) | versatile | 4 | 3 | 3 | **after:** If your fighter hasn't left their space this turn, draw 1 card. |
| **Primeval guardian** (Leshen) | defense | 5 | 2 | 3 | **during:** Your opponent discards the top card of their deck. Add its BOOST value to their card's value. · **after:** Move each Wolf up to 3 spaces. |
| **Primeval slam** (Leshen) | attack | 4 | 3 | 3 | **after:** Summon a Wolf in the Leshen's zone. Then, move each Wolf up to 3 spaces. |
| **Strength of the pack** (Leshen) | scheme | — | 1 | 3 | **effect:** Summon a Wolf in the Leshen's zone. · **ongoing:** At the start of your turn, the Leshen recovers 1 health. Discard this card at the end of your turn if there are no Wolves in the Leshen's zone. |
| **Vanish into murder** (Leshen) | scheme | — | 3 | 2 | **effect:** Deal 1 damage to each opposing fighter in the Leshen's zone. Remove the Leshen from the board. At the start of your next turn, place the Leshen in any space. Then, draw 1 card. |
| **Wily Fighting** (Any) | versatile | 3 | 1 | 3 | **after:** Deal 1 damage to each opposing fighter adjacent to your fighter. |
| **Command the forest** (Any) | attack | 4 | 2 | 2 | **after:** If you won the combat, your opponent discards 1 card. |

### Angel (Buffy the Vampire Slayer) — здоровье 16, движение 2

Способность: After Angel or Faith attacks, if you lost the combat, draw 1 card.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Regroup** (Any) | versatile | 1 | 1 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Brooding** | versatile | 3 | 2 | 2 | **after:**  If you lost the combat, the opposing fighter takes 1 damage. |
| **Haunted by the Faces** | defense | 3 | 2 | 2 | **after:**  If you lost the combat, you may place Angel in any space in his zone. |
| **Angelus, Scourge of Europe** | attack | 5 | 3 | 3 | — |
| **Disengage** (Any) | attack | 4 | 2 | 3 | **after:**  Choose an empty space in this fighter's zone. Place this fighter in that space. |
| **The Rogue Slayer** (Faith) | versatile | 3 | 3 | 2 | **after:**  Deal 1 damage to each opposing fighter adjacent to Faith. |
| **Cursed with a Soul** | attack | 4 | 3 | 2 | **after:**  If you lost the combat, recover 1 health. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Five by Five** (Faith) | attack | 5 | 3 | 2 | **after:**  Move Faith up to 5 spaces. She may move through opposing fighters. |
| **Killer of the Dead** (Faith) | scheme | — | 3 | 3 | **effect:** Deal 2 damage to one opposing fighter adjacent to Faith. |
| **Momentous Shift** (Any) | versatile | 3 | 1 | 3 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Wisdom of Ages** | attack | 3 | 2 | 2 | **after:**  Draw 1 card. |

### Annie Christmas (Adventures: Tales to Amaze) — здоровье 14, движение 2

Способность: NECKLACE OF PEARLS Add +2 to the value of Annie's attacks if she has less health than the defender.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Captain's Orders** (Annie) | scheme | — | 2 | 2 | **effect:** Place Annie in any space in her zone. Then, place another friendly fighter in any space in Annie's zone. Gain 1 action. |
| **Lagniappe** (Annie) | attack | 5 | 2 | 3 | **immediately:**  Deal up to 2 damage to Annie to draw that many cards. (This may cause her special ability to apply.) |
| **A Few More Pearls** (Annie) | scheme | — | 2 | 3 | **effect:** Deal 2 damage to each opposing fighter adjacent to Annie. |
| **Long Shot** (Any) | versatile | 3 | 1 | 2 | **during:**  If the opposing fighter is not adjacent to your fighter, this card's value is 5 instead. |
| **Slick Talker** (Any) | defense | 3 | 3 | 2 | **immediately:**  Annie and Charlie may swap spaces. If they do, your other fighter is now the defender. |
| **The Turn and the River** (Charlie) | versatile | 2 | 3 | 2 | **after:**  Draw 2 cards. |
| **Quite a Pair** (Any) | versatile | 3 | 2 | 2 | **immediately:**  You may reveal two cards from your hand with the same name. If you do, cancel all effects on your opponent's card. |
| **Better Together** (Any) | versatile | 4 | 1 | 4 | **after:**  If your fighter is adjacent to a friendly fighter, your fighter and each friendly fighter adjacent to them recover 1 health. |
| **Bottom Dealing** (Charlie) | attack | 3 | 2 | 2 | **during:**  Reveal the bottom card of your deck. Increase the value of this card by the BOOST value of the revealed card, then put the revealed card on the top or the bottom of your deck. |
| **Keep Your Hands to Yourself** (Annie) | versatile | 3 | 2 | 3 | **after:**  Move each fighter in the combat up to 2 spaces. |
| **Mississippi Queen** (Annie) | defense | 2 | 3 | 3 | **immediately:**  Damage cannot reduce Annie's health below 1 this turn. |
| **Striking Beauty** (Annie) | versatile | 1 | 3 | 2 | **after:**  Deal 1 damage to the opposing fighter. If you won the combat, deal 2 damage instead. |

### Beowulf (Little Red Riding Hood vs. Beowulf) — здоровье 17, движение 2

Способность: Beowulf starts with 1 Rage. When Beowulf is dealt damage, he gains 1 Rage. Beowulf has a maximum of 3 rage.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Remnant of Valor** (Wiglaf) | scheme | — | 2 | 2 | **effect:** Wiglaf deals 1 damage to each adjacent fighter. If Beowulf was dealt damage this way, gain 1 action. |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **The Ancient Heirloom** | attack | 3 | 1 | 2 | **effect:** This card's effects cannot be canceled.  · **during:**  You may spend 2 Rage to make this card's value 5 instead. You may spend 1 Rage to BOOST this card. (You may do both.) |
| **The War-King** | versatile | 1 | 3 | 3 | **during:**  Spend any amount of Rage. This card's value is +2 for each Rage spent. |
| **Hot for the Battle** (Wiglaf) | attack | 3 | 3 | 2 | **after:**  Wiglaf may swap spaces with Beowulf. |
| **Skirmish** (Any) | versatile | 4 | 1 | 3 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **Fatal Struggle** (Any) | attack | 4 | 2 | 3 | **after:**  If you won the combat, draw 2 cards. If you lost the combat, your opponent draws 2 cards. |
| **Epic Poem** | attack | 2 | 2 | 2 | **immediately:**  Gain 1 Rage.  · **during:**  This card's value is +1 for each Rage you have. (You do not spend Rage for this effect.) |
| **Golden Drinking Horn** | scheme | — | 3 | 2 | **effect:** Spend any amount of Rage. Choose a different effect for each Rage spent: - draw 2 cards - move Beowulf up to 4 spaces - Beowulf recovers 2 health. |
| **No Contest Expecteth** | attack | 3 | 3 | 2 | **after:**  If you attacked a sidekick and won the combat, you may spend 3 Rage to defeat that sidekick. |
| **The Equal of Grendel** | defense | 3 | 1 | 3 | **immediately:**  You may spend 2 Rage to deal damage to the opposing fighter equal to the printed value of their card. |
| **Vigor and Courage** | scheme | — | 2 | 3 | **effect:** Choose an opponent. They discard 1 random card. Gain rage equal to its BOOST value. |

### Bigfoot (Robin Hood vs Bigfoot) — здоровье 16, движение 3

Способность: At the end of your turn, if there are no opposing fighters in Bigfoot's zone, you may draw 1 card.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Savagery** | attack | 4 | 3 | 3 | **after:**  If you won the combat, deal 1 damage to each fighter adjacent to Bigfoot. |
| **It's Just Your Imagination** (Any) | defense | 3 | 3 | 2 | **immediately:**  Cancel all effects on your opponent's card. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Momentous Shift** (Any) | versatile | 3 | 1 | 3 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Jackalope Horns** (The Jackalope) | scheme | — | 2 | 3 | **effect:** Move the Jackalope up to 5 spaces. You may move the Jackalope through spaces containing opposing fighters. Then deal 2 damage to any one fighter adjacent to the Jackalope. |
| **Crash Through the Trees** | scheme | — | 3 | 2 | **effect:** Move Bigfoot up to 5 spaces. You may move Bigfoot through spaces containing opposing fighters. |
| **Hoax** (Any) | versatile | 4 | 2 | 3 | **after:**  Move your fighter up to 5 spaces. You may move that fighter through spaces containing opposing fighters. |
| **Skirmish** (Any) | versatile | 4 | 1 | 3 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **Disengage** (Any) | attack | 4 | 2 | 2 | **after:**  Choose an empty space in this fighter's zone. Place this fighter in that space. |
| **Larger Than Life** | attack | 6 | 3 | 3 | — |
| **Regroup** (Any) | versatile | 1 | 2 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |

### Black Panther (For King and Country) — здоровье 14, движение 2

Способность: VIBRANIUM SUIT Whenever you BOOST, draw 1 card. Cards stored in your VIBRANIUM SUIT can only be used to BOOST.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Cat-Like Reflexes** (Any) | versatile | 3 | 2 | 2 | **after:**  If you won the combat, move one of the fighters in the combat up to 3 spaces. |
| **Feint** (Any) | versatile | 2 | 1 | 2 | **immediately:** Cancel all effects on your opponent's card. |
| **Evade** (Any) | defense | 3 | 2 | 2 | **after:**  Draw 1 card. |
| **Nanotriage Processor** (Shuri) | versatile | 2 | 2 | 2 | **after:**  Shuri recovers 1 health. If Black Panther is in the same zone as Shuri, he also recovers 1 health. |
| **Ancestral Insight** | versatile | 4 | 1 | 3 | **after:**  If you won the combat, reveal the top card of your opponent's deck and store it in your Vibranium Suit. |
| **Microweave Mesh** | defense | 2 | 2 | 2 | **during:**  You may BOOST this card. |
| **Tactical Remote Scanning** (Shuri) | scheme | — | 3 | 2 | **effect:** Choose an opponent. Reveal the top 2 cards of their deck and store them in your Vibranium Suit. |
| **Analyze and Adjust** (Any) | attack | 3 | 3 | 3 | **after:**  Reveal the top card of your opponent's deck and store it in your Vibranium Suit. |
| **Anti-Metal Claws** | versatile | 1 | 2 | 2 | **during:**  Add the BOOST value of the opposing fighter's card to this card's value. Then, You may BOOST this card. |
| **Regroup** (Any) | versatile | 1 | 2 | 2 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Stalking Panther** (Any) | scheme | — | 2 | 3 | **effect:** Move each of your fighters up to 3 spaces. They may move through opposing fighters. Gain 1 action. |
| **Vibranium Shockwave** | attack | 2 | 2 | 2 | **during:**  You may BOOST this card. |
| **Wakanda Forever!** | versatile | 3 | 3 | 3 | **during:**  You may BOOST this card up to two times. (Draw a card for Black Panther's special ability each time you BOOST.) |

### Black Widow (For King and Country) — здоровье 13, движение 2

Способность: MISSION READY Before drawing your starting hand, add THE MOSCOW PROTOCOL card to your hand. Then, shuffle your deck and draw 5 cards. (Your starting hand is 6 cards instead of 5.)

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **The Budapest Gambit** | scheme | — | 4 | 1 | **effect:** Mission: You have 2 or fewer other cards in your hand. Draw 5 cards. Each opponent discards 1 random card. Acquire a new mission. |
| **The Moscow Protocol** | scheme | — | 4 | 1 | **effect:** Mission: An opposing fighter took damage this turn. Draw 1 card and gain 1 action. Acquire a new mission. |
| **Widow's Line** | versatile | 3 | 2 | 3 | **after:**  Move the opposing fighter up to 2 spaces. |
| **Acting Director of S.H.I.E.L.D.** (Maria Hill) | versatile | 4 | 3 | 3 | **after:**  Move each of your fighters up to 3 spaces. They may move through opposing fighters. Then, shuffle 1 scheme from your discard pile into your deck. |
| **Widow's Sting** | attack | 5 | 2 | 2 | **after:**  Move Black Widow up to 3 spaces. |
| **Caught in a Web** | versatile | 3 | 2 | 3 | **during:**  Cancel all AFTER COMBAT effects on your opponent's card. |
| **Life Model Decoy** (Maria Hill) | defense | — | 2 | 2 | **after:**  If Maria Hill was defeated, place her adjacent to Black Widow. If you do, set Maria Hill's health to 3. |
| **Widow's Bite** | attack | 4 | 1 | 3 | **after:**  If you won the combat, your opponent discards 1 card. |
| **Double Identity** (Any) | defense | 3 | 2 | 3 | **immediately:**  Black Widow and Maria Hill may swap spaces. If they do, your other fighter is now the defender. |
| **Fake Out** (Any) | attack | 1 | 1 | 2 | **after:**  If you lost the combat, draw 1 card and gain 1 action. |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **The Firenze Agenda** | scheme | — | 4 | 1 | **effect:** Mission: Black Widow is adjacent to an opposing hero. Deal 2 damage to each opposing fighter in Black Widow's zone. Acquire a new mission. |
| **The Kinshasa Directive** | scheme | — | 4 | 1 | **effect:** Mission: Black Widow is in your starting space. Choose an opponent. They discard 2 cards. Acquire a new mission. |
| **The Madripoor Sanction** | scheme | — | 4 | 1 | **effect:** Mission: Black Widow is in an opponent's starting space. Deal 2 damage to each of that opponent's fighters. Acquire a new mission. |
| **Widow's Kiss** | versatile | 4 | 2 | 2 | **immediately:**  The opposing fighter may not leave their space for the rest of the turn. |

### Blackbeard (Battle of Legends, Volume Three) — здоровье 13, движение 2

Способность: PRIVATEER TURNED PIRATE Start the game with 1 doubloon in the treasury, you have the other 2. - At the start of your turn, you may pay 1 doubloon to gain 1 action. - When Blackbeard takes combat damage, pay 1 doubloon.  BLACKBEARD'S DOUBLOONS Doubloons that Blackbeard doesn't have are kept in the Treasury.  Blackbeard pays a doubloon to the Treasury when he takes combat damage. He may also pay a doubloon at the start of his turn to gain an extra action.  The effects on many of Blackbeard's cards can be ignored by paying a ransom. Any opponent can pay the amount of doubloons shown at the end of an effect to ignore that effect. These doubloons are taken from the Treasury and given to Blackbeard.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Light the fuse** (Sea dog) | attack | 2 | 3 | 3 | **after:** Move your fighter up to 2 spaces. Then, deal 1 damage to each fighter adjacent to them. |
| **Plunder** | scheme | 0 | 2 | 3 | **effect:** Move each of your fighters up to 3 spaces. They may move through opposing fighters. Steal 1 doubloon from the treasury. |
| **A brace of primed pistols** | attack | 2 | 2 | 2 | **after:** Deal 3 damage to an opposing fighter in Blackbeard's zone unless 🪙 🪙.  |
| **Scourge of the seven seas** | scheme | 0 | 2 | 2 | **effect:** Blackbeard recovers 2 health unless 🪙. Summon a Sea Dog in any space unless 🪙. Gain 1 action unless 🪙. |
| **Avast Ye!** | attack | 5 | 3 | 2 | **immediately:** Your opponent discards 1 random card unless 🪙. · **after:** Deal 1 damage to each opposing fighter in Blackbeard's zone unless 🪙. |
| **Give no quarter** (Any) | attack | 3 | 1 | 3 | **during:** If another friendly fighter is adjacent to the opposing fighter, this card's value is 5 instead. · **after:** Gain 1 action unless 🪙. |
| **Parley** (Any) | versatile | 3 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card unless🪙 🪙. |
| **Fearsome and calculating** | versatile | 3 | 1 | 3 | **immediately:** Look at your opponent's hand and choose 1 card for them to discard unless 🪙. |
| **Intimidating visage** | defense | 4 | 1 | 2 | **after:** If Blackbeard is adjacent to an opposing fighter, he recovers 2 health. |
| **Show a leg!** (Any) | versatile | 2 | 2 | 2 | **after:** Summon a Sea Dog in Blackbeard's zone. |
| **No prey, no pay** (Any) | versatile | 2 | 2 | 3 | **during:** You may BOOST this card. · **after:** If you won the combat, draw 1 card. |
| **Queen Anne's revenge** | versatile | 7 | 3 | 2 | **effect:** This card's effects cannot be canceled. · **during:** Subtract 2 from this card's value for each doubloon your opponent pays. |

### Bloody Mary (Battle of Legends, Volume Two) — здоровье 16, движение 3

Способность: At the start of your turn, if you have exactly 3 cards in hand, gain 1 action.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Speak Three Times** | attack | 3 | 2 | 2 | **during:**  If this is your third action this turn, this card's value is 7 instead. |
| **Stolen Memories** | scheme | — | 3 | 2 | **effect:** Look at an opponent's hand and choose a card. Your opponent may discard it. If they don't, their hero takes damage equal to its BOOST value. |
| **Feint** | versatile | 2 | 2 | 2 | **immediately:** Cancel all effects on your opponent's card. |
| **Bloody Requiem** | attack | 3 | 4 | 3 | **after:**  BLOODY REPRISE: 0 ATK /  If your opponent played a card against BLOODY REQUIEM, this attack's value is that card's printed value. |
| **Infinity Mirror** | versatile | 4 | 2 | 2 | **after:**  Choose one of the fighters in the combat and move them up to 4 spaces. |
| **Out Of The Mirror** | attack | 1 | 2 | 2 | **during:**  Your opponent discards 1 random card. Add its BOOST value to this card's value.  · **after:**  If this is your third action, draw 1 card. |
| **Broken Glass** | versatile | 3 | 2 | 3 | **during:**  You may increase or decrease the value of this card by 1.  · **after:**  If the value of this card matches your opponent's card, draw 1 card and the opposing fighter takes 2 damage. |
| **Closer Than She Appears** | scheme | — | 2 | 2 | **effect:** Move your fighter up to 1 space. Draw 1 card. Gain 1 action. |
| **Evade** | defense | 3 | 1 | 3 | **after:**  Draw 1 card. |
| **Ghostly Touch** | attack | 1 | 2 | 2 | **during:**  You may BOOST this attack.  · **after:**  If this is your third action this turn, recover 3 health. |
| **Jump Scare** | versatile | 3 | 2 | 2 | **during:**  If Bloody Mary shares no zones with the space she started in this turn, this card's value is 6 instead. |
| **Mirror Image** | defense | 0 | 2 | 2 | **during:**  The value of this card is equal to the printed value of your opponent's card. |
| **Trick of the Light** | versatile | 2 | 3 | 3 | **after:**  You may place Bloody Mary in any empty space adjacent to the opposing fighter. |

### Bruce Lee (Bruce Lee) — здоровье 14, движение 3

Способность: At the end of your turn, you may move Bruce Lee 1 space.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Be Like Water** | defense | 3 | 4 | 4 | **after:**  Choose a JEET KUNE DO card in your discard pile and add it to your hand. |
| **Jeet Kune Do: Corkscrew Finger Jab** | attack | 3 | 2 | 1 | **after:**  Deal 1 damage to the opposing fighter. Gain 1 action. |
| **Taste of Blood** | defense | 3 | 3 | 1 | **after:**  If Bruce Lee has 5 or less health, draw 3 cards. |
| **Jeet Kune Do: Downward Side Kick** | attack | 3 | 2 | 1 | **after:**  Your opponent discards 1 random card. Gain 1 action. |
| **Jeet Kune Do: Intercepting Fist** | attack | 3 | 2 | 1 | **immediately:**  Cancel all effects on your opponent's card.  · **after:**  Gain 1 action. |
| **One-Inch Punch** | scheme | 0 | 3 | 1 | **effect:** Deal 2 damage to an adjacent fighter. If this defeats that fighter, return this card to your hand instead of discarding it. |
| **Jeet Kune Do: Wrist Lock** | attack | 3 | 2 | 1 | **after:**  Draw 1 card. Gain 1 action. |
| **Little Dragon** | versatile | 2 | 3 | 2 | **during:**  If your hand is empty, the value of this card is 6 instead.  · **after:**  Draw 2 cards. |
| **Momentous Shift** | versatile | 3 | 1 | 3 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **"HOO! WHAAAAAA!"** | scheme | 0 | 3 | 1 | **effect:** Choose a JEET KUNE DO card in your discard pile and add it to your hand. Gain 1 action. |
| **Bring It On** | scheme | 0 | 3 | 1 | **effect:** Choose an opposing fighter in Bruce Lee's zone. Place them in any space adjacent to Bruce Lee. Gain 1 action. |
| **Feint** | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Jeet Kune Do: High Straight Lead** | attack | 3 | 3 | 1 | **during:**  If either fighter started this turn in a different space, this card's value is 5 instead.  · **after:**  Gain 1 action. |
| **Jeet Kune Do: Short Lead Hook** | attack | 3 | 3 | 1 | **after:**  Bruce Lee may swap spaces with the opposing fighter. Gain 1 action. |
| **Nunchaku** | scheme | 0 | 3 | 2 | **effect:** All of Bruce Lee's attacks this turn are +1 value. Gain 1 action. |
| **Regroup** | versatile | 1 | 2 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Skirmish** | versatile | 4 | 1 | 3 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |

### Buffy (Buffy the Vampire Slayer) — здоровье 14, движение 3

Способность: Buffy may move through spaces containing opposing fighters (including when she is moved by effects).

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Cartwheel Kick** | defense | 2 | 2 | 2 | **after:**  You may move Buffy up to 3 spaces. Then, deal 1 damage to each opposing fighter adjacent to her. |
| **Insight** (Giles) | scheme | — | 3 | 3 | **effect:** Choose an opponent and look at their hand. Choose 1 card in their hand for them to discard. |
| **Mr. Pointy** | attack | 5 | 4 | 2 | — |
| **Training** (Giles) | scheme | — | 3 | 2 | **effect:** Draw 3 cards. |
| **Daring Strike** (Any) | attack | 4 | 3 | 3 | **after:**  If you won the combat, draw 2 cards. Otherwise, take 1 damage. |
| **Regroup** (Any) | versatile | 1 | 1 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Skirmish** (Any) | versatile | 4 | 3 | 3 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **Slayer's Strength** | versatile | 4 | 3 | 3 | **after:**  You may move all fighters adjacent to Buffy to another space in their zone. Then, deal 1 damage to each fighter you moved. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Military Knowledge** (Xander) | attack | 4 | 3 | 3 | **after:**  Draw 1 card. |
| **Rapid Recovery** | versatile | 3 | 3 | 3 | **after:**  Buffy recovers 1 health. |
| **Right-hand Man** (Xander) | versatile | 2 | 3 | 2 | **during:**  if Xander is adjacent to Buffy, the value of this card is 6 instead. |
| **Swift Strike** (Any) | attack | 3 | 2 | 3 | **after:**  Move your fighter up to 4 spaces. |

### Bullseye (Hell's Kitchen) — здоровье 14, движение 2

Способность: Bullseye can attack from up to 5 spaces away (ignoring zones).

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **I'm Better And I'll Prove It** | versatile | 2 | 2 | 2 | **during:**  If you already won a combat this turn, the value of this card is 6 instead. |
| **Arrogant But Effective** | versatile | 2 | 2 | 3 | **after:**  You are considered to have won this combat. Move Bullseye up to 2 spaces. |
| **World's Greatest Assassin** | attack | 4 | 3 | 2 | **immediately:**  If you already won a combat this turn, ignore the value of your opponent's card. |
| **Tactical Retreat** | defense | 3 | 2 | 3 | **after:**  Place Bullseye in a space that shares no zones with his current space. |
| **For My Next Trick** | attack | 2 | 2 | 3 | **after:**  Move one of your fighters up to 1 space. Draw 1 card. Gain 1 action. |
| **Feint** | versatile | 2 | 2 | 2 | **immediately:** Cancel all effects on your opponent's card. |
| **I Never Miss** | attack | 3 | 2 | 4 | **during:**  You may BOOST this attack. If you don't BOOST this attack, draw 1 card. |
| **I Planned To Be Here** | attack | 2 | 3 | 2 | **during:**  If you started your turn in your current space, the value of this card is 5 instead. |
| **Ricochet** | versatile | 3 | 2 | 3 | **after:**  If the opposing fighter was not defeated, deal 1 damage to a fighter in the opposing fighter's zone. |
| **Master Strategist** | versatile | 3 | 3 | 2 | **after:**  Move Bullseye exactly 4 spaces. You may move through opposing fighters. |
| **Right Between The Eyes** | versatile | 3 | 3 | 2 | **immediately:**  If you already won a combat this turn, your opponent discards 1 card. |
| **Study The Target** | scheme | — | 3 | 2 | **effect:** Draw 2 cards.If you won a combat this turn, draw 1 additional card and gain 1 action. |

### Chupacabra (Battle of Legends, Volume Three) — здоровье 14, движение 3

Способность: THE HUNGER After you attack, you may draw a card.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Ambush** | attack | 2 | 3 | 2 | **during:**  Your opponent discards 1 random card. Add its BOOST value to this card's attack value. |
| **Wounded beast** | versatile | 3 | 1 | 3 | **during:** If Chupacabra has 7 or less health, this card's value is 5 instead. |
| **Blood in the air** | attack | 4 | 4 | 3 | **during:** If you already won a combat this turn, you may BOOST this card. |
| **Feeding** | attack | 4 | 2 | 3 | **after:** If Chupacabra has 7 or less health, gain 1 action and it recovers 1 health. |
| **Feint** | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Natural toughness** | defense | 3 | 3 | 2 | **after:** If you lost the combat, return this card to your hand. |
| **Ravenous lunge** | versatile | 3 | 2 | 3 | **after:** Chupacabra recovers 1 health. If you won the combat, it recovers 2 instead. |
| **Traveler of the night** | scheme | 0 | 3 | 3 | **effect:** Move your fighter up to 4 spaces. They may move through opposing fighters. Gain 1 action. |
| **The more they struggle** | attack | 0 | 3 | 3 | **during:** The value of this card is equal to twice the printed value of your opponent's card. |
| **Unsettle** | scheme | 0 | 2 | 2 | **effect:** Choose an opponent with a fighter in Chupacabra's zone. They discard 1 card. You may deal 2 damage to Chupacabra to make them discard 2 cards instead. |
| **Tooth and tail** | versatile | 2 | 2 | 3 | **after:** Deal 1 damage to up to 2 fighters adjacent to Chupacabra. Chupacabra recovers 1 health for each fighter damaged this way. |

### Ciri (The Witcher - Steel & Silver) — здоровье 15, движение 2

Способность: UNCONTAINABLE POWER 🔵 x7 | Effects on Ciri's cards cannot be canceled.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Pushed to the brink** | versatile | 3 | 2 | 3 | **after:** 🔵 x2 Deal 1 damage to the opposing fighter. 🔵 x7 Deal 2 damage to an opposing fighter within 3 spaces of Ciri. |
| **Zireael** | versatile | 2 | 2 | 3 | **during:** 🔵 x3 This card's value is 4 instead. 🔵 x5 This card's value is 4 instead, and your opponent discards 1 random card. |
| **Child of the Elder Blood** | scheme | — | 2 | 2 | **effect:** 🔵 x4 Deal 1 damage to each other fighter in Ciri's zone. 🔵 x9 Deal 3 damage to each other fighter in Ciri's zone. |
| **Lion cub of Cintra** | attack | 2 | 2 | 3 | **during:** 🔵 x1 This card's value is 4 instead. 🔵 x5 This card's value is 7 instead. |
| **Bane of the Aen Elle** (Ihuarraquax) | attack | 4 | 4 | 3 | **after:** Move Ihuarraquax up to 4 spaces. He may move through opposing fighters. Then, deal 1 damage to an opposing fighter he moved through. |
| **Blink** | versatile | 4 | 1 | 3 | **after:** Move Ciri up to 3 spaces. She may move through opposing fighters. |
| **Channel the source** | attack | 2 | 3 | 3 | **during:** You may discard any number of 🔵 cards from your hand. Add +2 to this card's value for each 🔵 card you discarded. |
| **Parry** (Any) | defense | 3 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Searching strike** (Ihuarraquax) | versatile | 3 | 3 | 3 | **after:** If you won the combat, you may search your deck for a 🔵 card, reveal it, and add it to your hand. |
| **The lady of space and time** | versatile | 2 | 2 | 2 | **after:** 🔵 x3 Return a card from your discard pile to the top of your deck. 🔵 x8 Return a card from your discard pile to your hand. Draw 1 card. |
| **Unicorn ally** (Any) | scheme | — | 2 | 2 | **effect:** Ciri recovers 2 health. · **ongoing:** After each combat your fighter is in, draw 1 card. Discard this card at the end of your turn if you have 5 or more cards in your hand. |

### Cloak Dagger (Teen Spirit) — здоровье 8, движение 2

Способность: UMBRA After you attack, if Cloak dealt at least 2 combat damage, your opponent discards 1 card.  REFRACTION After you attack, if Dagger dealt at least 2 combat damage, gain 1 action.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Channel the Dark** (Any) | attack | 2 | 2 | 3 | **after:**  If Cloak played this card, place the opposing fighter adjacent to Dagger and gain 1 action. |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Perfect Balance** (Any) | versatile | 4 | 2 | 2 | **during:**  If Cloak and Dagger are both adjacent to the opposing fighter, the value of this card is 6 instead. |
| **Traverse the Darkforce** (Any) | versatile | 2 | 1 | 2 | **after:**  Move each of your fighters up to 2 spaces. |
| **Chosen Fate** (Any) | scheme | — | 1 | 2 | **effect:** Deal up to 4 damage to one of your fighters. Your other fighter recovers that amount of health. Draw 2 cards |
| **Darkforce Dimension** (Cloak) | attack | 4 | 3 | 2 | **after:**  Place the opposing fighter in any space. Your opponent discards 1 card. |
| **Into the Void** (Any) | attack | 2 | 1 | 3 | **during:**  You may BOOST this attack. |
| **The Living Light** (Any) | versatile | 3 | 2 | 2 | **after:**  If Cloak played this to defend, Dagger recovers 2 health. If Dagger played this to attack, Cloak recovers 2 health. |
| **Commanding Impact** (Any) | attack | 5 | 2 | 3 | **after:**  Draw 1 card. |
| **Into Darkness** (Any) | versatile | 3 | 2 | 3 | **after:**  Choose one of the fighters in the combat and move them up to 3 spaces. |
| **Lightforce Barrage** (Dagger) | attack | 7 | 3 | 2 | **effect:** This card's effects cannot be canceled.  · **after:**  If you won the combat, your fighter takes damage equal to the amount of damage you dealt. |
| **Living Shadow** (Any) | defense | 2 | 2 | 3 | **during:**  If Dagger played this card, she swaps spaces with Cloak, Cloak is now the defender, and the value of this card is 4 instead. |

### Daredevil (Hell's Kitchen) — здоровье 17, движение 3

Способность: DURING COMBAT: If you have 2 or fewer cards in your hand, you may BLIND BOOST your attack or defense. (If you have other DURING COMBAT effects, choose the order.)

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Take A Knee** | versatile | 3 | 2 | 3 | **after:**  Discard the top card of your deck. Recover health equal to its BOOST value. |
| **Man Without Fear** | attack | 2 | 3 | 2 | **during:**  You may BLIND BOOST this attack. (This is in addition to any BLIND BOOST from Daredevil's special ability.) |
| **Son Of A Boxer** | defense | 3 | 2 | 3 | **after:**  If you lost the combat, deal 2 damage to a fighter adjacent to Daredevil. |
| **Breather** | scheme | — | 2 | 3 | **effect:** Choose an attack, defense, or versatile card from your discard pile and return it to your hand. |
| **Devil of Hell's Kitchen** | attack | 4 | 3 | 2 | **during:**  If you have no cards in your deck, the value of this card is 8 instead.  · **after:**  Shuffle this card and the top four cards of your discard pile into your deck. |
| **Feint** | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Grappling Hook** | versatile | 3 | 2 | 3 | **after:**  Move Daredevil up to 2 spaces. |
| **Through Adversity** | scheme | — | 2 | 3 | **effect:** Move Daredevil up to 4 spaces. He may move through opposing fighters. Deal 1 damage to each opposing fighter Daredevil moves through. |

### Deadpool (Deadpool) — здоровье 10, движение 2

Способность: After you attack, Deadpool recovers 1 health. Also, if your opponent's real name is Logan, all your attacks are +5.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Non-Retinal Scan Access to Danger Room** | versatile | 3 | 4 | 1 | **after:**  Look at your opponent's hand. Recover 1 health. |
| **And For My Next Move...** | versatile | 2 | 1 | 1 | **after:**  Deal 2 damage to the opposing fighter OR move your fighter up to 3 spaces. |
| **Chimichanga Break!** | versatile | 2 | 2 | 1 | **during:**  If there is food on the table, the value of this card is 5 instead. |
| **Exploding Card!** | attack | 1 | 4 | 1 | **during:**  If you made an exploding noise when you revealed the card the value of this card is 4. |
| **Gimme Gimme Chimichanga** | versatile | 3 | 1 | 1 | **after:**  Draw a card. Recover 1 health. |
| **I Always Get The Last Word** | versatile | 3 | 1 | 1 | **after:**  If you attacked, deal 1 damage to the opposing fighter. |
| **Sweeet!** | scheme | — | 2 | 1 | **effect:** Move to a space in a yellow-ish zone. Then move to a different space in a yellow-ish zone. |
| **Time out time out time out!** | versatile | — | 3 | 1 | **immediately:**  Call time out. Look through your deck and pick a card you could play. Discard this card and play that one instead. |
| **Rob's Pouch & Shoe Emporium** | attack | 4 | 1 | 1 | **after:**  Move the opposing fighter one space. Just one. |
| **Transit Card** | defense | 2 | 1 | 1 | **after:**  Move to any space in your zone. |
| **Passwords** | defense | 5 | 1 | 1 | **after:**  Your opponent looks at your hand and chooses a card for you to discard. |
| **They Have An Amazing Buffet** | defense | 3 | 2 | 1 | **after:**  Recover 2 health. Then, if you are at full health, take 2 damage. |
| **Underrated Super Heroes** | attack | 6 | 2 | 1 | — |
| **Wanna bet?** | attack | 2 | 1 | 1 | **after:**  If you won the game your opponent buys you a drink. If you lost the game, you buy them a drink. |
| **Xavier Institute Faculty** | attack | 3 | 2 | 1 | **effect:** You may play this card as a ranged attack. |
| **3 of Hearts** | attack | 3 | 4 | 1 | **after:**  Draw 1 card. |
| **Call Me** | versatile | 3 | 2 | 1 | **during:**  If your opponent's name is on this card, its value is 4.  · **after:**  Your opponent writes their name on this card if it's not there already. |
| **Cha-Ching!** | attack | 1 | 3 | 1 | **during:**  You may BOOST this card. |
| **Deadpool™ Merc For Hire, LLC** | attack | 5 | 1 | 1 | **after:**  Deal 1 damage to the opposing fighter if you own the Deadpool Unmatched set. |
| **Dumpster Divin' Deadpool** | scheme | — | 1 | 1 | **effect:** Shuffle 5 cards from your discard pile into your deck. Recover 1 health. |
| **Eat Me** | defense | 2 | 2 | 1 | **effect:** Tee-hee!    · **immediately:**  Say "eat me" to your opponent. · **during:**  Say "eat me" to your opponent. · **after:**  If you lost combat, say "eat me" to your opponent. |
| **Excuse me while I grow some limbs.** | attack | 3 | 1 | 1 | **after:**  Your opponent discards a card. If you won the combat, they discard two instead. |
| **Faint** | scheme | — | 2 | 1 | **effect:** Tip your figure over. Make a fainting noise. Recover 2 health. Reset your figure. |
| **Feint** | versatile | 2 | 1 | 1 | **immediately:** Cancel all effects on your opponent's card. |
| **Gaze of Stone** | attack | 2 | 1 | 1 | **after:**  If you won the combat, deal 8 damage to the opposing fighter. |
| **Holy Mackerel!** | scheme | — | 2 | 1 | **effect:** Guess the name of a card in your opponent's hand. Your opponent must discard all cards with that name. Otherwise they say "go fish" and you draw a card. |
| **I'm Not Wearing Pants** | versatile | 2 | 1 | 1 | **during:**  If this card isn't sleeved, its value is 5.  · **after:**  If you're not wearing any pants, go put some on. |
| **Klunkin' Heads** | attack | 4 | 2 | 1 | **after:**  If you won the combat, deal 3 damage to each other opposing fighter adjacent to the opposing fighter. |
| **Push to Teleport** | versatile | 2 | 6 | 1 | **after:**  Draw 1 card. |
| **Super Feint** | versatile | 4 | 2 | 1 | **effect:** This card can't be canceled!   · **immediately:**  Cancel all effects on your opponent's card. · **after:**  Draw 1 card. |

### Doctor Strange (Brains and Brawn) — здоровье 14, движение 2

Способность: DARK PACT After each combat, if Doctor Strange played a card, you may deal 1 damage to him. If you do, put that card on the bottom of your deck and draw 1 card.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Feint** (Any) | versatile | 2 | 1 | 2 | **immediately:** Cancel all effects on your opponent's card. |
| **The Mists of Munnopor** | defense | 2 | 2 | 3 | **immediately:**  Discard your opponent's card. They reveal cards from their deck until they reveal an attack or versatile card they can play. They play that card and randomly put the rest of the revealed cards on the bottom of their deck. |
| **Seven Suns of Cinnibus** | versatile | 3 | 2 | 3 | **effect:** If the value of this card is above 7, ignore its value.  · **during:**  You may BLIND BOOST this card up to two times. |
| **Eye of Agamotto** | scheme | — | 2 | 2 | **effect:** Shuffle your hand into your deck. Draw 5 cards. Gain 1 action. |
| **Steadfast Disciple** (Wong) | versatile | 2 | 2 | 3 | **after:**  If Wong is adjacent to the opposing fighter, deal 1 damage to the opposing fighter and draw 1 card. |
| **The Winds of Watoomb** | attack | 4 | 1 | 3 | **after:**  Your opponent places Dr. Strange in a starting space. Place the opposing fighter in another starting space. All players shuffle their decks. |
| **Bolts of Balthakk** (Any) | attack | 2 | 3 | 4 | **during:**  You may BLIND BOOST this card.  · **after:**  If you won the combat, gain 1 action. |
| **Cloak of Levitation** | versatile | 2 | 1 | 2 | **during:**  If Dr. Strange is adjacent to the opposing fighter, ignore the value of your opponent's card. |
| **Master of Kamar-Taj** (Any) | versatile | 2 | 2 | 3 | **during:**  If Dr. Strange and Wong are adjacent, this card's value is 4 instead. |
| **No Really, I'm a Doctor** | scheme | — | 3 | 2 | **effect:** Reveal a card from your hand and put it on top of your deck. Dr. Strange or a friendly fighter adjacent to him recovers health equal to that card's boost value. |
| **The Rings of Raggadorr** (Any) | attack | 4 | 1 | 3 | **after:**  You may BOOST this card up to two times. (Draw a card for Black Panther's special ability each time you BOOST.) |

### Donatello (Adventures: Teenage Mutant Ninja Turtles) — здоровье 14, движение 2

Способность: INVENTIVE When you maneuver, you may draw 2 cards instead of 1. If you do, put a card in your hand on the bottom of your deck. After you play an invention, tuck it under this card. For the rest of the game, its invention bonus applies.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Party wagon!** | scheme | — | 2 | 2 | **effect:** Move a friendly fighter up to 5 spaces. They may move through opposing fighters. Then, deal 2 damage to an opposing fighter they moved through. |
| **Heroes in a half shell** | defense | 5 | 1 | 2 | — |
| **Smoke bomb** | scheme | — | 3 | 1 | **effect:** Remove up to 4 scheme cards in your discard pile from the game. Gain that many actions. PERMANENT. When you play a scheme, gain 1 action. |
| **Self defense grid** | defense | 2 | 3 | 1 | **effect:** PERMANENT. Add +1 to the value of your defenses. · **after:** Remove up to 4 defense or versatile cards in your descard pile from the game. Donatello recovers that much health. |
| **Quick strike** (Any) | versatile | 3 | 1 | 3 | **after:** Draw 1 card. |
| **Shift focus** | versatile | 2 | 2 | 3 | **after:** Move another fighter in Donatello's zone up to 3 spaces. They may move through oothe fighters. |
| **Short circuit** (Any) | versatile | 3 | 2 | 3 | **immediately:** Cancel all effects AFTER COMBAT effects on your opponent's card. |
| **Untested enhancements** (Metalhead) | versatile | 3 | 2 | 3 | **during:** Discard the bottom card of your deck. Add its BOOST value to this card's value. |
| **Donatello does machines** | scheme | — | 3 | 2 | **effect:** You and each other friendly player may return an attack, versatile, or defense card in their discard pile to their hand. Draw 1 card. |
| **The future of Ninjutsu** (Metalhead) | scheme | — | 1 | 2 | **effect:** Look at the top card of any deck. You may put it on the bottom. Draw 1 card. Gain 1 action. |
| **Electro grenade** | attack | 2 | 3 | 1 | **effect:** PERMANENT. Add +1 to the value of your attacks. · **during:** Remove up to 4 attack or versatile cards in your discard pile from the game. Add +1 to this card's value for each card removed. |
| **Thinking ahead** (Any) | attack | 3 | 2 | 3 | **after:** If you won the combat, you may put a card in your discard pile on the bottom of your deck. |
| **Turtle power!** (Any) | attack | 3 | 3 | 2 | **during:** You may BOOST this card. |
| **Bo staff** | defense | 3 | 2 | 2 | **after:** Deal 1 damage to an opposing fighter adjacent to Donatello. Draw 1 card. |

### Dr. Jill Trent (Adventures: Tales to Amaze) — здоровье 13, движение 2

Способность: GADGETOLOGY At the start of your turn, activate one of your gadgets. Whenever Jill Trent attacks, resolve the active gadget's effect.  Hypnoray Blaster DURING COMBAT: If your card's printed value is lower than your opponent's, reveal the top card of your opponent's deck. Increase the value of your attack by the BOOST value of the revealed card.  Ultrabiotic Tonic AFTER COMBAT: If your card's printed value is higher than your opponent's, Jill Trent Recovers 1 health.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Battle of Wits** (Jill Trent) | attack | 2 | 4 | 3 | **after:**  Reveal the top card of your deck and your opponent's deck. If your card has a higher BOOST value, deal 3 damage to the opposing fighter. |
| **Energizing Spray** (Any) | attack | 5 | 1 | 2 | **after:**  Gain 1 action. |
| **Hypnotist** (Jill Trent) | defense | 3 | 1 | 2 | **immediately:**  If your active gadget is Hypnoray Blaster, cancel all effects on your opponent's card. |
| **Utility Belt** (Jill Trent) | versatile | 3 | 3 | 3 | **after:**  Choose one: -Jill Trent recovers 1 health, -Move Jill Trent 1 space, -Draw 1 card |
| **Helpful Assistant** (Daisy) | scheme | — | 3 | 2 | **effect:** Shuffle up to 3 Jill Trent cards in your discard pile back into your deck. Draw 1 card. |
| **Insightful Deduction** (Any) | versatile | 3 | 2 | 2 | **after:**  Reveal the top 3 cards of your opponent's deck. Put one of them on the bottom of the deck and the rest on top in any order. |
| **Sisters in Arms** (Daisy) | versatile | 3 | 1 | 2 | **effect:** This card's effects cannot be canceled. If Daisy and Jill Trent are adjacent and Daisy is attacking, Daisy gains the effect of Jill Trent's gadget. |
| **Ace Fighter** (Daisy) | versatile | 5 | 3 | 2 | **after:**  Draw 1 card. |
| **Caught Red-Handed** (Any) | versatile | 1 | 2 | 2 | **after:**  Your opponent discards 1 card. If you won the combat, they discard 2 cards instead. |
| **Gyroscopic Jetpack** (Any) | versatile | 4 | 2 | 3 | **after:**  Move your fighter up to 2 spaces. They may move through opposing fighters. |
| **Indestructible Cloth** (Any) | defense | 5 | 2 | 2 | **immediately:**  This combat, your fighter does not take damage from effects other than combat damage. |
| **Laser Pen** (Any) | versatile | 2 | 2 | 3 | **after:**  Deal 1 damage to the opposing fighter. |
| **Stasis Diffuser** (Any) | versatile | 3 | 1 | 2 | **immediately:**  The value of your opponent's card is equal to its printed value and cannot be changed. |

### Dr. Sattler (Jurassic Park - Sattler vs. T-Rex) — здоровье 13, движение 2

Способность: After Dr. Sattler or Dr. Malcolm move, place an insight token in their new space. You have 5 insight tokens. Whenever either of your fighters moves to a new space, place and insight token in their new space. Tokens may be placed in spaces with other tokens, including other insight tokens. There tokens have no effect themselves but any of your cards interact with them. When you remove insight tokens from the board, return them to your supply. You can place them on the board again in the future. If you would place an insight token but don't have any in your supply, nothing happens.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Regroup** (Any) | versatile | 1 | 1 | 2 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **The Concept of Attraction** (Any) | defense | 2 | 2 | 3 | **after:**  You may place your fighter on any space with an insight token. |
| **You Never Had Control, That's the Illusion** | attack | 2 | 2 | 3 | **during:**  Increase the value of this card by the number of insight tokens on the board. Remove all insight tokens from the board. |
| **Chaotician** (Dr. Malcolm) | versatile | 2 | 3 | 1 | **after:**  Place an insight token in any space. |
| **Hey! Hey! Hey!** (Any) | versatile | 3 | 3 | 1 | **after:**  Move your other fighter up to 4 spaces. |
| **I Think We're Back In Business** | versatile | — | 3 | 3 | **during:**  The value of this card is equal to the number of cards in your hand. |
| **Life Finds a Way** (Dr. Malcolm) | versatile | 2 | 3 | 2 | **after:**  Your opponent discards the top card of their deck. Dr. Malcolm and Dr. Sattler recover health equal to that card's BOOST value. |
| **Lock The Doors!** (Any) | defense | 2 | 2 | 2 | **after:**  Deal 2 damage to the opposing fighter. Move your fighter up to 2 spaces. |
| **Must Go Faster** (Any) | versatile | 3 | 2 | 1 | **after:**  If you won the combat, you may place Dr. Malcolm and Dr. Sattler in any space. |
| **Sexism in Survival Situations** | versatile | 1 | 2 | 2 | **during:**  If the opposing fighter is a hero, the value of this card is 4 instead.  · **after:**  You may move Dr. Sattler 1 space. |
| **The Future Ex-Mrs. Malcolm** (Dr. Malcolm) | scheme | — | 2 | 1 | **effect:** Draw 2 cards. Place an insight token in Dr. Malcolm's space. Gain 1 action. |
| **Violently, If Necessary** | versatile | 3 | 3 | 3 | **after:**  Deal 2 damage to each opposing fighter on or adjacent to a space with an insight token. |
| **Woman Inherits the Earth** | versatile | 2 | 3 | 3 | **immediately:**  Draw 1 card. Dr Sattler recovers health equal to the number of insight tokens on the board. Remove all insight tokens from the board. |

### Dracula (Cobble & Fog) — здоровье 13, движение 2

Способность: At the start of your turn, you may deal 1 damage to a fighter adjacent to Dracula. If you do, draw a card.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Prey Upon** | scheme | — | 4 | 2 | **effect:** Deal 1 damage to all opposing fighters adjacent to Dracula. Dracula recovers 1 health for each damage dealt. |
| **Thirst for Sustenance** (Sister) | attack | 3 | 3 | 3 | **after:**  If you won the combat, place Dracula in any space adjacent to the opposing fighter. |
| **Beastform** | attack | 6 | 4 | 2 | **during:**  You may discard any number of cards from your hand. This card's value is +1 for each card you discard. |
| **Dash** (Any) | versatile | 3 | 1 | 3 | **after:**  Move your fighter up to 3 spaces. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Exploit** (Any) | versatile | 4 | 1 | 2 | **after:**  Draw 1 card. |
| **Mistform** | scheme | — | 2 | 2 | **effect:** Place Dracula in any space. Gain 1 action. |
| **Ambush** (Any) | attack | 2 | 3 | 2 | **during:**  Your opponent discards 1 random card. Add its BOOST value to this card's attack value. |
| **Baptism of Blood** | scheme | — | 2 | 2 | **effect:** Recover 2 health. Return a defeated Sister (if any) to any space in Dracula's zone. |
| **Do My Bidding** | defense | 3 | 3 | 2 | **immediately:**  Return your opponent's attack card to their hand. Look at their hand and choose an attack or versatile card for them to play. (It may be the same card.) |
| **Feeding Frenzy** | attack | 2 | 3 | 2 | **during:**  This card's value is +1 for each Sister in the same zone as the opposing fighter. |
| **Look Into My Eyes** | defense | 1 | 2 | 2 | **during:**  Add the BOOST value from your opponent's attack card to the defense value of this card. |
| **Ravening Seduction** (Sister) | scheme | — | 2 | 3 | **effect:** Move any fighter up to 2 spaces. After moving, deal 1 damage to the moved fighter for each Sister adjacent to them. |

### Elektra (Hell's Kitchen) — здоровье 7, движение 2

Способность: The first time Elektra would be defeated, remove her and all Hand from the board. She is not defeated. At the start of your next turn, Resurrect her. (Ignore effects with the RESURRECTED symbol.) When Elektra Resurrects: Flip your health dial. Shuffle your discard pile into your deck. Place Elektra and all Hand back onto the board with each fighter in a different zone. (You must resolve effects with the RESURRECTED symbol.)

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Mystic Assassin** | attack | 6 | 1 | 2 | **after:**  Elektra takes 3 damage.RESURRECTED: Elektra takes no damage instead. |
| **The Fist** | attack | 3 | 3 | 2 | **after:**  You may deal 1 damage to your attacking fighter. If you do, return this card to your hand and gain 1 action. |
| **Hands of Red** | attack | 4 | 2 | 2 | **after:**  Return a defeated Hand to a space in Elektra's zone. |
| **Snakeroot Clan** | defense | 1 | 2 | 2 | **immediately:**  Elektra may swap spaces with a Hand. If she does, that Hand is now the defender. |
| **Cloaked In Shadow** | versatile | 2 | 1 | 2 | **immediately:**  Cancel all effects on your opponent's card.  · **after:**  RESURRECTED: Move Elektra up to 3 spaces. |
| **Intercept** | defense | 3 | 4 | 2 | **during:**  RESURRECTED: You may reveal a card named SAI from your hand. If you do, the value of this card is 5 instead. |
| **Mesmerize** | scheme | — | 2 | 2 | **effect:** Choose an opponent and look at their hand. Gain 1 action.RESURRECTED: Choose 1 card for them to discard. |
| **Ninjitsu** | versatile | 3 | 2 | 2 | **after:**  Place your fighter in any space. |
| **Sai** | versatile | 4 | 3 | 2 | — |
| **Whirlwind** | versatile | 2 | 1 | 2 | **after:**  RESURRECTED: Deal 1 damage to each adjacent opposing fighter. |

### Eredin (The Witcher - Realms Fall) — здоровье 14, движение 2

Способность: KING OF THE WILD HUNT While all of your Red Riders are defeated, Eredin is ENRAGED. If Eredin is ENRAGED, add +1 to the value of your combat cards, and your move value is 3.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Brutal strike** | attack | 2 | 3 | 3 | **effect:** This card's effects cannot be canceled. · **during:** If your opponent's card has an IMMEDIATELY effect, ignore their card's value. |
| **Unyielding hordes** (Red Rider) | attack | 1 | 2 | 3 | **immediately:** Return a defeated Red Rider to any space. · **during:** Add +1 to this card's value for each other friendly fighter adjacent to the opposing fighter. |
| **Portal defense** | defense | 0 | 1 | 2 | **immediately:** Eredin swaps spaces with an adjacent friendly fighter. That fighter is ow the defender. · **after:** If Eredin is ENRAGED, draw 2 cards. |
| **Icy guile** (Any) | versatile | 2 | 1 | 3 | **immediately:** If Eredin is ENRAGED, cancel all effects on your opponent's card. · **during:** You may defeat a Red Riper to ignore the value of your opponent's card. |
| **Close for the kill** (Any) | scheme | — | 4 | 3 | **effect:** Draw 2 cards. Move each of your fighters up to 3 spaces. They may move through opposing fighters. |
| **Backhand** | attack | 4 | 3 | 3 | **after:** Your opponent puts 1 random card from their hand on top of their deck. If Eredin is ENRAGED, they discard it instead. |
| **Foul purpose** (Any) | attack | 3 | 2 | 2 | **effect:** If Eredin is ENRAGED, you may play this card face-up to target a fighter in any space. · **after:** You may defeat a Red Rider to return this card to your hand. |
| **Implacable** | defense | 3 | 3 | 3 | **effect:** If Eredin is ENRAGED, you may play this card as an attack. · **during:** You may BOOST this card. |
| **Might of the Aen Elle** | scheme | — | 2 | 2 | **effect:** Draw 1 card. Gain 1 action. · **ongoing:** Eredin does not take damage except combat damage or from exhaustion. Discard this card at the end of your turn if you didn't attack. |
| **Skirmish** (Any) | versatile | 4 | 1 | 3 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **Wild hunt** (Any) | versatile | 3 | 2 | 3 | **after:** Deal 1 damage to each opposing fighter that is adjacent to at least one of your fighters. If Eredin is ENRAGED, deal 2 damage instead. |

### Geralt of Rivia (The Witcher - Steel & Silver) — здоровье 16, движение 2

Способность: ALWAYS PREPARED At the start of the game, choose your gear. Select a POTION, ARMOR, and SWORD, and shuffle 2 copies of each into your deck.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Witcher Senses** (Geralt) | scheme | — | 3 | 2 | **effect:** Search your deck or discard pile for a GEAR card and add it to your hand. If you took it from your deck, shuffle this card back into your deck. |
| **Disciplined Duelist** (Geralt) | versatile | 4 | 2 | 3 | **after:** If the printed value of your opponent's card is ... 2: you may draw 1 card 3: deal 1 damage to the opposing fighter 4: your opponent discards 1 card |
| **Gear: Armor of the Forgotten Wolf** (Geralt) | defense | 2 | 3 | 2 | **during:** Add +1 to this card's value for each fighter adjacent to Geralt. · **after:** End the turn. |
| **Gear: Blizzard** (Geralt) | scheme | — | 3 | 2 | **effect:** Draw 1 card. Move Geralt up to 3 spaces. · **ongoing:** Opponents can't gain actions. Discard this card at the end of your turn if you didn't attack. |
| **Gear: Sword of silver** (Geralt) | attack | 4 | 3 | 2 | **immediately:** If your opponent's card has a printed value of 4 or more, ignore its value. |
| **Gear: Tawny Owl** (Geralt) | scheme | — | 3 | 2 | **effect:** Draw 2 cards. Gain 1 action. · **ongoing:** If an effect would cause you to discard a card from your hand, you may choose to ignore it. Discard this card at the end of your turn if you didn't attack. |
| **Igni** (Geralt) | attack | 0 | 3 | 2 | **after:** Deal 2 damage to the opposing fighter and 1 damage to each other fighter adjacent to Geralt. |
| **Plot twist** (Dandelion) | versatile | 2 | 2 | 3 | **after:** Look at your opponent's hand and choose 1 card for them to discard. Draw 1 card. |
| **Riposte** (Geralt) | versatile | 2 | 2 | 2 | **after:** Choose one: - deal 1 damage to an adjacent fighter - Geralt swaps spaces with an adjacent fighter |
| **Yrden** (Geralt) | versatile | 2 | 2 | 3 | **immediately:** The opposing fighter cannot leave their space this turn. · **after:** Move Geralt up to 2 spaces. |
| **Annoying tune** (Dandelion) | versatile | 3 | 3 | 3 | **after:** Move the opposing fighter up yo 4 spaces. |
| **Gear: Sword of steel** (Geralt) | attack | 4 | 3 | 2 | **after:** Gain 1 action. If the opposing fighter has 8 or more health, gain 2 actions instead. |
| **Rend** (Geralt) | versatile | 3 | 2 | 3 | **during:** You may BOOST this card. |
| **Damn, you're ugly** (Geralt) | versatile | 5 | 4 | 3 | — |
| **Gear: Wolf Medallion** (Geralt) | defense | 3 | 3 | 2 | **immediately:** Cancel all effects on your opponent's card · **during:** If the opposing fighter is not adjacent to Geralt, ignore the value of your opponent's card. |

### Ghost Rider (Redemption Row) — здоровье 17, движение 2

Способность: Ghost Rider starts the game with 5 Hellfire. When you maneuver you may spend 1 Hellfire. If you do, increase Ghost Rider's move value to 4, and he mave move through opposing fighters. Then deal 1 damage to each opposing fighter he moved through.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Control The Demon** | versatile | — | 1 | 3 | **during:**  This card's value is +1 for each Hellfire you have. (You do not spend Hellfire for this effect.) |
| **I Brought The Devil With Me** | attack | 3 | 2 | 3 | **after:**  You may spend 2 Hellfire to gain 1 action. |
| **Penance Stare** | versatile | 3 | 2 | 2 | **during:**  Add the BOOST value of the opposing fighter's card to this card's value. You may spend 2 Hellfire to do it a second time. |
| **Deal With The Devil** | defense | 2 | 1 | 2 | **during:**  You may spend any amount of Hellfire. Increase the value of this card by that amount. |
| **Hell Rides With Me** | scheme | — | 3 | 2 | **effect:** Move Ghost Rider and up to one adjacent fighter up to 4 spaces each. Gain 2 Hellfire. Gain 1 action. |
| **Spirit Of Vengeance** | attack | 5 | 2 | 3 | **after:**  You may spend 1 Hellfire to draw 2 cards. |
| **Blaze of Glory** | attack | 2 | 3 | 2 | **after:**  Spend any amount of Hellfire, Deal that much damage to each fighter in Ghost Rider's zone (including Ghost Rider). |
| **Chains of Hellfire** | scheme | — | 2 | 2 | **effect:** Set your Hellfire to 5. |
| **Feint** | versatile | 2 | 1 | 2 | **immediately:** Cancel all effects on your opponent's card. |
| **I Finally Escaped Hell** | versatile | 3 | 1 | 3 | **after:**  You may spend 1 Hellfire to move Ghost Rider up to 2 spaces. |
| **Stoke The Flames** | defense | 2 | 2 | 3 | **after:**  If you lost the combat, gain Hellfire equal to the combat damage you took. |
| **The Wicked Will Burn** | versatile | 3 | 2 | 3 | **after:**  If Ghost Rider started this turn in a different space, gain 2 Hellfire. |

### Golden Bat (Adventures: Tales to Amaze) — здоровье 18, движение 3

Способность: THE FIRST SUPERHERO If you haven't taken a Maneuver action this turn, add +2 to the value of Golden Bat's attacks.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Terrifying Roar** | versatile | 3 | 1 | 3 | **immediately:**  Fighters cannot leave their spaces for the rest of the turn. |
| **Vaporizing Eyebeams** | attack | 2 | 2 | 3 | **after:**  Your opponent discards 1 random card. |
| **Alpine Fortress** | scheme | — | 3 | 3 | **effect:** Choose a card in your discard pile and shuffle it into your deck. Draw 2 cards. Move Golden Bat up to 4 spaces. |
| **He Laughs at Your Feebleness** | defense | 5 | 3 | 2 | — |
| **Imposing Presence** | defense | 3 | 2 | 2 | **immediately:**  Cancel all effects on your opponent's card. |
| **Like a Flash of Golden Light** | versatile | 2 | 2 | 3 | **during:**  If Golden Bat shares no zones with the space he started this turn in, this card's value is 4 instead.  · **after:**  Move Golden Bat up to 5 spaces. |
| **Skirmish** | versatile | 4 | 1 | 2 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **A Punch to Shake the Earth** | attack | 1 | 1 | 3 | **after:**  Deal 1 damage to each opposing fighter in Golden Bat's zone. If you won the combat, deal 2 damage instead. |
| **Arrive Just in Time** | scheme | — | 2 | 2 | **effect:** Place Golden Bat in any space. |
| **Insight of the Ancients** | versatile | 3 | 2 | 2 | **after:**  If you won the combat, return a random card in your discard pile to your hand. |
| **Sight Beyond Sight** | versatile | 2 | 1 | 3 | **after:**  Look at the top 3 cards of your opponent's deck. Put them back in any order. |
| **Super Strength** | attack | 5 | 1 | 2 | — |

### Hamlet (Slings and Arrows) — здоровье 15, движение 2

Способность: THE QUESTION At the start of your turn, choose TO BE or NOT TO BE. If you choose NOT TO BE, deal 2 damage to one of your fighters. TO BE: When you maneuver, draw 1 additional card. NOT TO BE: Add +2 to the value of Hamlet's attacks.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **The Ghost** | scheme | — | 1 | 2 | **effect:** Choose one: - Hamlet recovers 2 health, - place Hamlet in any space in his zone and gain 1 action |
| **The Readiness Is All** (Any) | versatile | 2 | 2 | 2 | **after:** Place one of the fighters in the combat in any space. The cannot leave that space this turn. |
| **To Sleep, Perchance To Dream** (Any) | attack | 3 | 2 | 3 | **after:** If you won the combat, move the opposing fighter a number of spaces up to the amount of combat damage dealt. If you lost the combat, Hamlet recovers 1 health. |
| **Blood Will Have Blood** | versatile | 2 | 1 | 3 | **after:** If Hamlet took damage this turn, deal 1 damage to the opposing fighter. |
| **Maddening Insight** (Any) | defense | 0 | 1 | 2 | **during:** The value of this card is equal to the number of cards in your hand. · **after:** If you won the combat, your opponent discards 1 card. |
| **Nothing Either Good Or Bad** (Any) | defense | 2 | 1 | 3 | **after:** If your opponent played a versatile card, deal 2 damage to the opposing fighter. |
| **Outrageous Fortune** | versatile | 1 | 2 | 2 | **during:** Discard the top card of your deck. Add its BOOST value to this card's value. · **after:** If you lost the combat, return the card you discarded to your hand. |
| **The Play's The Thing** (Any) | versatile | 3 | 2 | 3 | **after:** Your opponent discards 1 random card. If you won the combat, Hamlet recovers health equal to its BOOST value. |
| **The Rest Is Silence** | defense | 2 | 3 | 2 | **after:** End the turn. |
| **Uncertain Doom** (Any) | attack | 2 | 3 | 3 | **during:** If your opponent played a versatile card, ignore its value. |
| **Cruel To Be Kind** | attack | 2 | 4 | 2 | **during:** You may BOOST this card. |
| **Method In The Madness** | scheme | — | 3 | 3 | **effect:** Put any number of cards in your hand on the bottom of your deck. Then, draw up to that many cards. Gain 1 action. |

### Harry Houdini (Houdini vs. The Genie) — здоровье 14, движение 2

Способность: ESCAPE ARTIST When you take the maneuver action and BOOST, you may place Houdini in any space instead of moving. (Bess moves as normal.)

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **A Magician Never Reveals His Secrets** (Houdini) | scheme | — | 4 | 1 | **effect:** Draw 2 cards. Gain 1 action. If an effect would let an opponent look at your hand, you may reveal this card and cancel that effect. |
| **And the Beautiful Bess!** (Bess) | versatile | 3 | 1 | 2 | **effect:** If you discard this card as a result of an opponent's effect, draw 1 card.  · **boost:** BOOSTED WITH: If it's your turn, gain 1 action. |
| **All Part of the Show** (Any) | defense | 2 | 2 | 2 | **effect:** This card's effect cannot be canceled.   · **after:**  If your fighter was defeated, set their health to 4 instead and place them in any space. (This effect happens even if Houdini was defeated.) · **boost:** BOOSTED WITH: Houdini recovers 2 health. |
| **An Illusion of My Own Design** (Houdini) | attack | 4 | 2 | 2 | **immediately:**  Your opponent may BOOST their card.  · **during:**  You may BOOST this card. |
| **Flourish** (Any) | attack | 3 | 2 | 4 | **during:**  You may BOOST this card. · **boost:** BOOSTED WITH: Draw 1 card.  |
| **Grand Escape** (Houdini) | defense | 2 | 3 | 3 | **during:**  You may BOOST this card.  · **after:**  If you won the combat, place your fighter in any space. |
| **Set the Stage** (Bess) | scheme | — | 2 | 2 | **effect:** Draw 3 cards. Then, put a card in your hand on top of your deck.  · **boost:** BOOSTED WITH: Look at an opponent's hand and choose a card for them to discard. |
| **Sleight of Hand** (Any) | attack | 1 | 3 | 2 | **immediately:**  You may return this card to your hand and choose a different card to play. Resolve all effects on that card as normal. · **boost:** BOOSTED WITH: Draw 1 card.  |
| **The Big Reveal** (Houdini) | attack | 2 | 3 | 2 | **during:**  You may BOOST this card twice.  · **after:**  Return one card you boosted with to your hand. |
| **For My Next Trick** (Any) | attack | 2 | 2 | 2 | **after:**  Move one of your fighters up to 1 space. Draw 1 card. Gain 1 action. |
| **Misdirection** (Any) | versatile | 2 | 1 | 3 | **immediately:**  Cancel all effects on your opponent's card. · **boost:** BOOSTED WITH: Deal 2 damage to any fighter.  |
| **Smoke and Mirrors** (Any) | versatile | 3 | 1 | 2 | **immediately:**  Houdini and Bess may swap spaces. If they do, your other fighter is now in the combat. |
| **Vanishing Act** (Houdini) | versatile | 2 | 2 | 3 | **after:**  Choose one of the fighters in the combat and move them up to 3 spaces. They may move through their opposing fighters. |

### Invisible Man (Cobble & Fog) — здоровье 15, движение 2

Способность: At the start of the game, after you place Invisible Man, place 3 fog tokens in separate spaces in his zone. When Invisible Man is on a space with a fog token, add 1 to the value of his defense cards. Invisible Man may move between two spaces with fog tokens as if they were adjacent.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Into Thin Air** | defense | 4 | 1 | 2 | **after:**  Move Invisible Man up to 1 space. Your opponent then moves a fog token up to 3 spaces. |
| **Confound** | versatile | 3 | 2 | 2 | **after:**  Your opponent may choose to discard 1 card. If they do not, you may move each fog token to any other space. |
| **Dreaming of Revenge** | versatile | 3 | 1 | 2 | **after:**  If Invisible Man is on a space with a fog token, all opposing fighters on spaces with fog tokens take 1 damage. |
| **Impossible to See** | versatile | 2 | 2 | 2 | **immediately:**  The value of your opponent's attack or defense is 0 and cannot be changed by card effects. (Other card effects still happen.) |
| **Rolling Fog** | scheme | — | 1 | 2 | **effect:** Move 1 fog token to another space. Gain 1 action. |
| **Step Lightly** | scheme | — | 1 | 2 | **effect:** Deal 1 damage to one adjacent fighter. If Invisible Man is on a space with a fog token, deal 3 damage instead. Your opponent then moves a fog token up to 2 spaces. |
| **Surprise Attack** | attack | 5 | 1 | 2 | **immediately:**  Cancel all effects on your opponent's card.  · **after:**  If Invisible Man is on a space with a fog token, move that fog token to another space. |
| **Coded Notes** | defense | 3 | 2 | 2 | **after:**  Draw 3 cards, then choose 2 cards from your hand and put them on top of your deck in any order. |
| **Covert Preparation** | versatile | 2 | 1 | 3 | **after:**  Draw 1 card. Move 1 fog token up to 2 spaces, then your opponent moves a different fog token up to 2 spaces. |
| **Emerge From Mist** | attack | 3 | 2 | 2 | **during:**  If Invisible Man started this turn on a space with a fog token, this card's value is 5 instead. |
| **Lurking** | defense | 2 | 2 | 2 | **after:**  Draw 1 card and choose 1 effect: - move Invisible Man to a space with a fog token - move 1 fog token up to 3 spaces |
| **Vanish** | scheme | — | 3 | 2 | **effect:** Recover 1 health. Remove Invisible Man from the board. At the start of your next turn, place Invisible Man in any space. (If you played this as your first action, end your turn.) |
| **Reign of Terror** | scheme | — | 1 | 2 | **effect:** If Invisible Man is on a space with a fog token, deal 2 damage to any one opposing fighter. |
| **Slip Away** | attack | 3 | 2 | 3 | **after:**  Move 1 fog token to a space without a fighter, then place Invisible Man on that space. |

### Jekyll & Hyde (Cobble & Fog) — здоровье 16, движение 2

Способность: Start the game as Dr. Jekyll. At the start of your turn, you may transform into Dr. Jekyll or Mr. Hyde. While Mr. Hyde, after you maneuver, take 1 damage.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Forever Hyde** (Mr. Hyde) | attack | 5 | 2 | 2 | **during:**  You may discard Dr. Jekyll cards. Add 2 to this card's value for each card discarded. |
| **Skirmish** (Any) | versatile | 4 | 1 | 3 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **Pure Evil** (Mr. Hyde) | scheme | — | 3 | 3 | **effect:** Place Mr. Hyde in any space in his zone. Mr. Hyde deals 2 damage to all adjacent fighters. |
| **Distracted Triage** (Dr. Jekyll) | versatile | 3 | 3 | 2 | **after:**  If you won the combat, recover 2 health. |
| **Strange Case** (Mr. Hyde) | scheme | — | 2 | 2 | **effect:** Reveal the top card of your deck. Deal damage equal to its BOOST value to one adjacent fighter. Put the card in your hand. |
| **Succumb to Compulsion** (Dr. Jekyll) | versatile | 2 | 2 | 3 | **after:**  Move up to 2 spaces. Transform to Mr. Hyde. |
| **Calming Research** (Dr. Jekyll) | scheme | — | 3 | 2 | **effect:** Recover 2 health. Draw up to 3 cards. Keep one and put any others on the bottom of your deck in any order. |
| **Madness Relents** (Mr. Hyde) | versatile | 4 | 2 | 2 | **after:**  Transform to Dr. Jekyll. |
| **Recoiling Blow** (Mr. Hyde) | attack | 5 | 2 | 2 | **after:**  Place Mr. Hyde in any space in his zone. Transform to Dr. Jekyll. |
| **With Haste!** (Dr. Jekyll) | defense | 4 | 3 | 2 | **after:**  Move Dr. Jekyll up to 4 spaces. |
| **Scientific Method** (Dr. Jekyll) | defense | 2 | 2 | 2 | **after:**  Draw a number of cards equal to the damage you were dealt. |
| **Duality of Man** (Any) | versatile | 3 | 1 | 2 | **during:**  If you are Dr. Jekyll and playing this card to defend, this card's value is 6 instead. If you are Mr. Hyde and playing this card to attack, this card's value is 6 instead. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |

### King Arthur (Battle of Legends, Volume One) — здоровье 18, движение 2

Способность: When King Arthur attacks, you may BOOST that attack, Play the BOOST card, face down, along with your attack card. If your opponent cancels the effects on your attack card, the BOOST is discarded without effect.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **The Lady of the Lake** (Arthur) | scheme | — | 2 | 1 | **effect:** Search your deck and discard pile for the EXCALIBUR card. Add it to your hand. If you searched your deck, shuffle it. |
| **The Aid of Morgana** (Arthur) | attack | 4 | 2 | 1 | **after:**  Draw 2 cards. |
| **Prophecy** (Merlin) | scheme | — | 2 | 1 | **effect:** Look at the top 4 cards of your deck. Add 2 of them to your hand and put the other 2 back on top of your deck, in any order. |
| **Excalibur** (Arthur) | attack | 6 | 3 | 1 | — |
| **Momentous Shift** (Any) | versatile | 3 | 1 | 3 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Bewilderment** (Merlin) | defense | 0 | 2 | 2 | **during:**  Prevent all damage  · **after:**  You may place your fighter in any space. |
| **Command the Storms** (Merlin) | scheme | — | 2 | 2 | **effect:** Move each fighter up to 3 spaces. (This includes opposing fighters.) |
| **Regroup** (Any) | versatile | 1 | 1 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Swift Strike** (Any) | attack | 3 | 2 | 2 | **after:**  Move your fighter up to 4 spaces. |
| **Aid the Chosen One** (Merlin) | attack | 4 | 2 | 1 | **after:**  If you won the combat, draw 2 cards. |
| **Divine Intervention** (Arthur) | versatile | 3 | 2 | 2 | **after:**  Move King Arthur up to 5 spaces. |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Noble Sacrifice** (Arthur) | attack | 2 | 3 | 3 | **during:**  You may BOOST this attack. (This is in addition to any boost from King Arthur's special ability.) |
| **Restless Spirits** (Merlin) | scheme | — | 2 | 1 | **effect:** Choose any space in Merlin's zone. Deal 2 damage to each opposing fighter in that space and in one adjacent space. If at least one fighter is defeated this way, draw 1 card. |
| **Skirmish** (Any) | versatile | 4 | 1 | 3 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **The Holy Grail** (Arthur) | defense | 1 | 2 | 1 | **after:**  If King Arthur has 4 or less health but is not defeated, set his health to 8. |

### Krang (TMNT: Shredder vs Krang) — здоровье 16, движение 1

Способность: DOOOOOM! Krang has 3 doomsday machines. Start with one machine active.  After you roll the Dice of Ultimate Destruction, you can deactivate an active machine to reroll the die.  Add +1 to your move value for each active machine.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Android arms: Wings** | scheme | — | 3 | 3 | **effect:** Move Krang up to ? spaces. Krang may move through opposing fighters. Then, deal 1 damage to each opposing fighter Krang moved through. Gain 1 action. |
| **Molecular Amplification Unit** | versatile | 2 | 2 | 4 | **immediately:** Activate a machine. · **during:** Increase this card's value by?. |
| **Android arms: Missiles** | attack | 1 | 1 | 3 | **effect:** You may play this card face up as a ranged attack. · **during:** Increase this card's value by ?. |
| **Warlord of Dimension X** | versatile | 3 | 3 | 3 | **after:** Reveal the top card of your deck and your opponent's deck. If your card's name is longer, draw it. |
| **Android arms: Chain Flail** | attack | 2 | 3 | 3 | **after:** If the printed value of your opponent's card is less than ?, or they didn't play a card, they discard 2 cards. |
| **Android arms: Powerbomb** | attack | 3 | 2 | 3 | **during:** You may BOOST this card. · **after:** Move the opposing fighter a number of spaces up to the amount of combat damage dealt. |
| **IQ of 968** | scheme | — | — | 3 | **effect:** Activate all machines. Draw ? cards. Krang recovers ? health |
| **Minimizer** | defense | 0 | 1 | 3 | **immediately:** Decrease the value of your opponent's card by 4. · **after:** End the turn. |
| **Pan-dimensional Portal** | versatile | 3 | — | 2 | **after:** Place a fighter in the combat in any space. They can't leave that space this turn. Both players put ? random cards from their hands on the bottom of their decks, then both draw 2 cards. |
| **Welcome to the Technodrome!** | versatile | 2 | 2 | 3 | **immediately:** Choose one: - cancel all effects on your opponent's card - activate a machine |

### Leonardo (Adventures: Teenage Mutant Ninja Turtles) — здоровье 16, движение 2

Способность: TEAM TACTICS At the start of your turn, move any fighter up to 1 space.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Protective father** (Splinter) | scheme | — | 2 | 2 | **effect:** Splinter may swap spaces with another friendly fighter. If he does, they both recover 2 health. Gain 1 action. |
| **Quick strike** (Any) | versatile | 3 | 3 | 3 | **after:** Draw 1 card. |
| **Spatial awareness** (Splinter) | versatile | 3 | 3 | 3 | **after:** If the opposing fighter is in fewer zones than Splinter, deal 1 damage to the opposing fighter and draw 1 card. |
| **Turtle power!** | attack | 3 | 2 | 2 | **during:** You may BOOST this card. |
| **Wise beyond his years** | versatile | 2 | 2 | 3 | **after:** If the opposing fighter is in fewer zones than Leonardo, deal 2 damage to the opposing fighter. |
| **Eat, sleep, and breath ninjutsu** (Any) | versatile | 3 | 1 | 3 | **after:** Place each fighter adjacent to your fighter in another space in their zone. |
| **Fearless leader** (Any) | attack | 3 | 2 | 3 | **during:** Add +2 to this card value for each other friendly fighter adjacent to the opposing fighter. |
| **For Sensei** (Any) | attack | 4 | 1 | 2 | **after:** Move both fighters in the combat up to 1 space each. You may discard 1 card to gain 1 action. |
| **Heroes in a half shell** | defense | 5 | 3 | 2 | — |
| **I have a plan** (Any) | versatile | 2 | 1 | 3 | **immediately:** You may discard 1 card. Of you do, cancel all effects on your opponent's card and ignore its value. |
| **Katana** | attack | 6 | 2 | 2 | — |
| **Leonardo leads** | scheme | — | 4 | 2 | **effect:** Move each friendly fighter up to 3 spaces. Draw 1 card. |

### Little Red (Little Red Riding Hood vs. Beowulf) — здоровье 14, движение 2

Способность: Resolve an effect on a card you play if the symbol next to the effect matches the item in your basket. At the start of the game, place LITTLE RED's BASKET in your discard pile. Little Red's Basket: This starts in your discard pile. It does not count as a card. 🌟 counts as any one 🐺🌹⚔️ symbol.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Never Leave the Path 🐺** | scheme | — | 1 | 2 | **effect:** 🐺 Place Little Red in any space. Gain 1 action. ⚔️ Deal 2 damage to each opposing fighter in Little Red's zone. 🌹 Draw 3 cards. |
| **A Grimm Tale 🌹** (Huntsman) | scheme | — | 3 | 2 | **effect:** Little Red Recovers 2 health. 🐺 Little Red recovers 4 health instead. |
| **Once Upon a Time 🌹** (Any) | versatile | 2 | 1 | 2 | **after:**  ⚔️ Deal 3 damage to the opposing fighter. |
| **Stones in the Belly 🌹** (Any) | versatile | — | 1 | 3 | **during:**  ⚔️ Your opponent discards 1 random card. Add its BOOST value to this card's value. |
| **What Big Eyes You Have 🐺** | versatile | 2 | 2 | 2 | **immediately:**  Cancel all effects on your opponent's card. 🌹 Also ignore the value of your opponent's card. |
| **What Big Ears You Have 🐺** | attack | 4 | 2 | 2 | **effect:** ⚔️ You may play this card as a defense card. |
| **The Wolf's Skin ⚔️** (Any) | defense | 2 | 2 | 3 | **after:**  🐺 Draw 2 cards. |
| **Into the Woods 🐺🌹⚔️** | scheme | — | 2 | 3 | **effect:** Move Little Red up to 3 spaces. Gain 1 action. |
| **Long Have I Sought You ⚔️** (Huntsman) | attack | 4 | 2 | 3 | **during:**  If the Huntsman is adjacent to the opposing fighter, the value of this card is 6 instead. |
| **What a Terrible Big Mouth You Have ⚔️** | defense | 2 | 2 | 2 | **after:**  🐺 Deal damage to the opposing fighter equal to the printed value of their card. |
| **What Large Hands You Have 🐺** | attack | 2 | 3 | 2 | **after:**  You may return this card to your hand. 🌹 Instead, you may return the top card of your discard pile to your hand. |
| **What's That In My Basket? 🌟** | versatile | 4 | 3 | 4 | **effect:** (🌟 counts as any one 🐺🌹⚔️ symbol.) |

### Loki (Battle of Legends, Volume Three) — здоровье 16, движение 2

Способность: MISCHIEF-MONGER After you play a TRICK, put that card into your opponent's hand instead of your discard pile. If an opponent discards a TRICK from their hand, return that card to your hand or the top of your deck. Add +1 to your move value for each TRICK in your opponents hands.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Trick: Baldr's downfall** (Any) | attack | 4 | 0 | 3 | **after:** Loki. Draw 1 card. Not Loki. Deal 2 damage to your hero. |
| **TRICK: FREYJA'S RESCUE** (Any) | versatile | 2 | 0 | 2 | **during:** Loki. Swap the values of your card and your opponent's card. · **after:** Not Loki. Loki recovers 3 health. |
| **Shapershifter** | attack | 0 | 3 | 4 | **during:** Choose one effect: - add +1 to this card's value for each card in your opponent's hand - gain 1 action |
| **GOD OF MISCHIEF** | versatile | 2 | 3 | 3 | **immediately:** If your opponent played a TRICK, ignore that card's value. Otherwise, cancel all effects on your opponent's card. |
| **LAEVATEINN** | versatile | 2 | 3 | 3 | **during:** Reveal a card in your opponent's hand. Add its BOOST value to this card's value. If you reveal a TRICK, put it in your hand. |
| **Looking for trouble** | attack | 4 | 3 | 3 | **immediately:** If your opponent played a card, return it to their hand, look at their hand, and choose a card for them to play. |
| **MALICIOUS FLYTING** | versatile | 3 | 3 | 3 | **after:** Draw 1 card. If your opponent played a TRICK, draw 2 cards instead. |
| **RAGNARÖK** (Any) | attack | 0 | 3 | 2 | **effect:** This card's effects cannot be canceled. · **during:** Add +3 to this card's value for each TRICK in your opponent's hand. |
| **TRICK: SINDRI'S BET** (Any) | defense | 3 | 0 | 2 | **during:** Loki. Your opponent may discard a card. If they don't, subtract 3 from their card's value. · **after:** Not Loki. Loki returns the top card of their discard pile to their hand. |
| **TRICK: SVADILFARI'S LURE** (Any) | scheme | 0 | 0 | 2 | **effect:** Loki. Place an opposing fighter adjacent to Loki. Not Loki. Loki reveals a card in your hand. Discard that card. |
| **UNDERHANDED** | versatile | 3 | 2 | 3 | **during:** If your opponent has more cards in their hand than you, this card's value is 6 instead. |

### Luke Cage (Redemption Row) — здоровье 13, движение 2

Способность: Luke Cage takes 2 less combat damage from attacks.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Pushback** (Misty Knight) | versatile | 2 | 3 | 2 | **after:**  Move the opposing fighter up to 3 spaces. |
| **Skin Like Titanium** | defense | — | 1 | 2 | **after:**  If you lost the combat, deal damage to the opposing fighter equal to the amount of combat damage you took. |
| **Where's My Money?** | scheme | — | 1 | 2 | **effect:** Place Luke Cage adjacent to the nearest opposing fighter. Gain 1 action. |
| **Got My Back?** (Misty Knight) | defense | 1 | 2 | 2 | **immediately:**  Misty Knight may swap spaces with Luke Cage. If she does, Luke Cage is now the defender. |
| **Regroup** (Any) | versatile | 1 | 3 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Trash Talk** (Any) | defense | 2 | 1 | 3 | **immediately:**  Cancel all effects on your opponent's card.  · **after:**  If you won the combat, end the turn. |
| **Daughter of the Dragon** (Misty Knight) | versatile | 2 | 2 | 2 | **during:**  If Misty Knight is adjacent to the opposing fighter, the value of this card is 6 instead. |
| **Commanding Impact** (Any) | attack | 5 | 1 | 3 | **after:**  Draw 1 card. |
| **Get Paid** | attack | 4 | 2 | 2 | **after:**  If you won the combat, draw 2 cards. |
| **Hero For Hire** | attack | 3 | 1 | 3 | **during:**  You may BOOST this attack. |
| **Sweet Christmas!** | attack | 6 | 1 | 2 | — |
| **Power Man** | defense | 2 | 1 | 2 | **after:**  Move the opposing fighter up to 3 spaces. You may move them through other opposing fighters. Deal 1 damage to them and each opposing fighter they moved through. |
| **Still Standing** (Any) | attack | 4 | 2 | 2 | **after:**  If you won the combat, choose 2 cards in your discard pile and shuffle them into your deck. |

### Medusa (Battle of Legends, Volume One) — здоровье 16, движение 3

Способность: At the start of your turn, you may deal 1 damage to an opposing fighter in Medusa's zone.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Second Shot** | attack | 3 | 3 | 3 | **during:**  You may BOOST this attack. |
| **A Momentary Glance** | scheme | — | 4 | 2 | **effect:** Deal 2 damage to any one fighter in Medusa's zone. |
| **Winged Frenzy** (Any) | scheme | — | 2 | 2 | **effect:** Move each of your fighters up to 3 spaces. You may move them through spaces containing opposing fighters. Then, return a defeated Harpy (if any) to any space in Medusa's zone. |
| **Gaze of Stone** | attack | 2 | 4 | 3 | **after:**  If you won the combat, deal 8 damage to the opposing fighter. |
| **Hiss and Slither** | defense | 4 | 3 | 3 | **after:**  Your opponent discards 1 card. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Regroup** (Any) | versatile | 1 | 2 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Snipe** (Any) | versatile | 3 | 1 | 3 | **after:**  Draw 1 card. |
| **The Hounds of Mighty Zeus** (Harpy) | versatile | 4 | 3 | 2 | **after:**  Move each Harpy up to 3 spaces. |
| **Clutching Claws** (Harpy) | versatile | 3 | 2 | 3 | **after:**  Your opponent discards 1 card. |
| **Dash** (Any) | versatile | 3 | 1 | 3 | **after:**  Move your fighter up to 3 spaces. |

### Michelangelo (Adventures: Teenage Mutant Ninja Turtles) — здоровье 14, движение 3

Способность: PIZZA PARTY After you attack or scheme, draw 1 card. Your starting and maximum hand size is 3.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Heroes in a half shell** (Michelangelo ) | defense | 5 | 2 | 2 | — |
| **Back for seconds** (Any) | defense | 2 | 1 | 2 | **after:** Shuffle 2 random cards from your discard pile back into your deck. |
| **Hi-yaaaaah!!** (Michelangelo ) | attack | 4 | 3 | 3 | **after:** Deal 1 damage to an adjacent opposing fighter. You may put a card from your hand on the bottom of your deck to gain 1 action. |
| **Boisterous beatdown** (Michelangelo ) | attack | 2 | 1 | 3 | **after:** Gain 1 action. If you won the combat, gain 2 actions instead. |
| **Let's go** (Any) | versatile | 3 | 2 | 3 | **after:** Move a friendly fighter up to 3 spaces. |
| **Michelangelo is a party dude!!** (Michelangelo ) | scheme | — | 2 | 2 | **effect:** Each friendly fighter recovers 1 health. |
| **Cowabunga!!** (Michelangelo ) | versatile | 3 | 2 | 3 | **during:** Add +1 to this card's value for each other card you played this turn. |
| **Nunchaku** (Michelangelo ) | scheme | — | 2 | 2 | **effect:** All of Bruce Lee's attacks this turn are +1 value. Gain 1 action. |
| **Guaranteed delivery** (Any) | versatile | 3 | 1 | 3 | **immediately:** You may put a card from your hand on the bottom of your deck to cancel all effects on your opponent's card. · **after:** If your hand is empty, draw 2 cards. |
| **Shell insertion** (April) | scheme | — | 3 | 2 | **effect:** Chose two different effects: - each opponent discards 1 card - move a friendly fighter up to 2 spaces - put a card from your hand on the bottom of your deck to gain 1 action - shuffle 2 random cards from your discard pile back into your deck |
| **Turtle power!** (Michelangelo ) | attack | 3 | 3 | 2 | **during:** You may BOOST this attack. |
| **Hard-hitting investigation** (April) | attack | 0 | 3 | 3 | **after:** Deal 1 damage to the opposing fighter. Gain 1 action. |

### Moon Knight (Redemption Row) — здоровье 16, движение 3

Способность: Moon Knight At the start of your turn, move up to 2 spaces.  Khonshu Khonshu adds +2 to the value of his attack cards. He does not take damage from effects other than combat damage.  Mr. Knight Mr. Knight adds +1 to all his defense values.  At the end of your turn, change to your next identity (In order, Moon Knight -> Khonshu -> Mr. Knight, repeating).

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Let Your Insanity Guide You** (Any) | versatile | 1 | 2 | 2 | **after:**  Discard the top card of your deck. Draw cards equal to that card's BOOST value. |
| **Travelers of The Night** (Any) | scheme | — | 3 | 2 | **effect:** Move your fighter up to 4 spaces. They may move through opposing fighters. Gain 1 action. |
| **That's The Part I Like** (Any) | versatile | 3 | 2 | 2 | **after:**  If you won the combat, you may look at the top 3 cards of your opponent's deck and discard one of them. Place the other 2 back in any order. |
| **We're All In This Together** (Any) | defense | 3 | 2 | 3 | **after:**  If you won the combat, draw 1 card. |
| **I'm Not Real** (Any) | attack | 4 | 2 | 3 | **after:**  You may change to your next identity. |
| **That's Why I Always Win** (Any) | attack | 3 | 2 | 3 | **during:**  You may BOOST this attack. |
| **Madness Will Keep You Alive** (Any) | scheme | — | 3 | 2 | **effect:** Recover 2 health. If you started your turn in a different space, gain 1 action. |
| **A Totally Sane Thing To Do** (Any) | versatile | 2 | 1 | 3 | **after:**  You may deal 2 damage to both fighters in the combat. |
| **Fist of Khonshu** (Any) | versatile | 3 | 2 | 2 | **after:**  If you won the combat, move the opposing fighter up to 4 spaces. |
| **Past and Present Intermingle** (Any) | versatile | 2 | 2 | 3 | **during:**  Add the BOOST value of the top card of your discard pile to this card's value. |
| **Good Enough For Us** (Any) | versatile | 4 | 1 | 2 | **after:**  You may draw 2 cards. If you do, take 2 damage. |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |

### Ms. Marvel (Teen Spirit) — здоровье 14, движение 2

Способность: STRETCHY At the start of your turn, you may move Ms. Marvel 1 space. Ms. Marvel can attack from up to 2 spaces away (ignoring zones).

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Fangirl** | attack | 0 | 2 | 3 | **during:**  The value of this card is equal to the number of cards in your hand. |
| **Momentous Shift** | versatile | 3 | 2 | 3 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Slingshot** | defense | 3 | 2 | 3 | **after:**  Place Ms. Marvel in any space in her zone. |
| **Big Wind Up** | attack | 4 | 2 | 3 | **during:**  If Ms. Marvel's space shares no zones with the opposing fighter, you may BOOST this card. |
| **Feint** | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Easy Peasy** | versatile | 3 | 2 | 3 | **after:**  Draw 1 card. Then, if you have 4 or more cards in your hand, deal 1 damage to an adjacent fighter. |
| **Embiggen** | versatile | 3 | 3 | 3 | **during:**  If Ms. Marvel is in more zones than the opposing fighter, the value of this card is 6 instead. |
| **Friends and Family** | scheme | — | 4 | 1 | **effect:** Draw 2 cards. Then, you may spend an additional action to draw until you have 7 cards in your hand. |
| **Gyro and Fries** | scheme | — | 2 | 2 | **effect:** Recover 2 health. Then, if you have 4 or more cards in your hand, gain 1 action. |
| **I'm Not Touching You** | attack | 4 | 1 | 3 | **after:**  If Ms. Marvel's space shares no zones with the opposing fighter, draw 2 cards. |
| **Shrink! Shrink! Shrink!** | versatile | 2 | 2 | 3 | **after:**  Choose one effect. If Ms. Marvel's space shares no zones with the opposing fighter, do both: - your opponent discards 1 card - move the opposing fighter up to 3 spaces |

### Muhammad Ali (Muhammad Ali vs Bruce Lee) — здоровье 16, движение 3

Способность: Begin the game with your stance on Float Like a Butterfly. After you attack, if you won the combat, change stances.  FLOAT LIKE A BUTTERFLY You can attack from 2 spaces away.  STING LIKE A BEE Add +2 to your attacks.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Jab** (Ali) | attack | 1 | 3 | 2 | **after:** Draw 1 card. Gain 1 action. [Butterfly] Move your fighter up to 2 spaces. |
| **Answer the bell** (Ali) | scheme | — | 2 | 2 | **effect:** Move Ali up to 3 spaces. Ali recovers 2 health. Gain 1 action. |
| **Stick and move** (Ali) | versatile | 2 | 1 | 3 | **during:** [Butterfly] The value of your opponent's card becomes its printed value and cannot change. · **after:** Deal 1 damage to an adjacent fighter. |
| **Ali Shuffle** (Ali) | attack | 2 | 2 | 3 | **during:** [Butterfly] You may BOOST this card. · **after:** If you won the combat, shuffle a non-scheme card from your discard pile into your deck. |
| **Close and clinch** (Ali) | versatile | 3 | 1 | 3 | **immediately:** Place Ali adjacent to the opposing fighter. Neither fighter can leave their space this turn. |
| **Momentous Shift** (Ali) | versatile | 3 | 1 | 2 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Fancy footwork** (Ali) | versatile | 1 | 3 | 2 | **immediately:** Move Ali up to 1 space. · **during:** If Ali shares no zones with the opposing fighter, ignore the value of the opponent's card. |
| **Hard to be humble** (Ali) | defense | 2 | 2 | 3 | **during:** [Butterfly] Look at your opponent's hand. · **after:** Move Ali up to 2 spaces. |
| **Louisville lip** (Ali) | scheme | — | 2 | 2 | **effect:** Ali recovers 1 health. Draw 2 cards. If you won a combat this turn, each opponent discards 1 random card. |
| **Rope-a-dope** (Ali) | defense | 2 | 3 | 2 | **after:** [Butterfly] If you lost the combat, Ali recovers 3 health. |
| **Champion of the world** (Ali) | versatile | 4 | 3 | 2 | **after:** Move a fighter in the combat up to 2 spaces. [Butterfly] Draw 1 card. |
| **Stronger than the skill** (Ali) | attack | 3 | 1 | 2 | **after:** Look at your opponent's hand. If you won the combat, shuffle one of their cards into their deck. |
| **The greatest** (Ali) | attack | 4 | 3 | 2 | **after:** If you dealt 6 or more combat damage this turn, gain 2 actions. |

### Nikola Tesla (Adventures: Tales to Amaze) — здоровье 14, движение 2

Способность: ELECTRICAL OVERFLOW Start the game with 1 coil charged. At the end of your turn, charge 1 coil. At the start of your turn, if both coils are charged, deal 1 damage to each opposing fighter adjacent to Tesla and move them up to 1 space.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Death Ray** (Tesla) | attack | 3 | 4 | 3 | **during:**  You may discharge coils: - 1 Coil: This card's value is 5. - 2 Coils: Instead, this card's value is 7. |
| **Intense Experimentation** (Tesla) | defense | 3 | 2 | 3 | **after:**  Draw 1 card. You may discharge coils: - 1 Coil: Instead, draw 2 cards. - 2 Coils: Instead, draw 3 cards and Tesla recovers 1 health. |
| **Lightning Storm** (Tesla) | versatile | 3 | 1 | 3 | **after:**  You may discharge coils: - 1 Coil: Deal 1 damage to each opposing fighter in your zone. - 2 Coils: Instead, deal 2 damage. |
| **Polyphase Coils** (Tesla) | versatile | 3 | 1 | 3 | **immediately:**  You may discharge coils: - 1 Coil: Cancel all effects on your opponent's card. - 2 Coils: Also, ignore that card's value. |
| **X-Ray Radiation** (Tesla) | versatile | 4 | 1 | 3 | **during:**  Reveal the top card of your opponent's deck. You may discharge coils: - 1 Coil: Discard that card. - 2 Coils: Also, add its boost value to this card's value. |
| **7 Hertz** (Tesla) | attack | 4 | 3 | 3 | **after:**  You may discharge coils: - 1 Coil: Gain 1 action. - 2 Coils: Also, draw 1 card. |
| **Repulsion Blast** (Tesla) | versatile | 2 | 2 | 3 | **after:**  Move the opposing fighter up to 2 spaces. You may discharge coils: - 1 Coil: Also, move Tesla up to 2 spaces. - 2 Coils: Also, your opponent discards 1 random card. |
| **Fully Charged** (Tesla) | scheme | — | 1 | 2 | **effect:** Charge both coils. Gain 1 action. |
| **Kinetic Induction** (Tesla) | versatile | 2 | 1 | 3 | **after:**  Charge one coil. If you won the combat, charge both. |
| **Remote Control** (Tesla) | scheme | — | 3 | 2 | **effect:** Move all opposing fighters up to 2 spaces. Gain 1 action. |
| **The Alternating Current** (Tesla) | attack | 5 | 3 | 2 | **after:**  Choose one: - Charge both coils - Discharge both coils to have Tesla recover 2 health |

### Oda Nobunaga (Sun's Origin) — здоровье 13, движение 2

Способность: MASTER STRATEGIST Other friendly fighters in Oda Nobunaga's zone add +1 to the value of their played combat cards. (Oda Nobunaga does not benefit from this ability.)

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Fire and Flames** (Any) | attack | 3 | 3 | 3 | **during:**  If the opposing fighter is flanked, this card's value is 5 instead. |
| **Momentous Shift** (Any) | versatile | 3 | 2 | 2 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Pragmatism** | defense | 3 | 1 | 3 | **immediately:**  Cancel all effects on your opponent's card. |
| **Reinforce** (Any) | scheme | — | 2 | 3 | **effect:** Choose 2 different effects: - each friendly fighter recovers 1 health - draw 2 cards - gain 1 action |
| **Student of War** | attack | 5 | 2 | 2 | **after:**  Draw a number of cards equal to the amount of combat damage dealt to the opposing fighter. |
| **Battle Maneuvers** (Any) | versatile | 2 | 2 | 4 | **after:**  Draw 1 card. Then, move each of your fighters up to 2 spaces. |
| **Demon King of the Sixth Heaven** | scheme | — | 3 | 2 | **effect:** Deal 2 damage to each opposing flanked fighter. |
| **Lightning and Thunder** (Honor Guard) | attack | 4 | 1 | 3 | **immediately:**  If the opposing fighter is flanked, cancel all effects on your opponent's card.  · **after:**  Move your fighter up to 2 spaces. |
| **Patience and Strategy** (Any) | versatile | 1 | 1 | 3 | **after:**  If the opposing fighter is flanked, your fighter recovers 2 health. |
| **Spring the Trap** (Any) | defense | 2 | 2 | 3 | **immediately:**  Your fighter may swap spaces with an adjacent friendly fighter. If they do, the other fighter is now the defender.  · **after:**  Deal 1 damage to the opposing fighter. |
| **Sun and Moon** (Honor Guard) | attack | 2 | 1 | 2 | **during:**  If the opposing fighter is flanked, ignore the value of your opponent's card. |

### Pandora (Battle of Legends, Volume Three) — здоровье 14, движение 2

Способность: PANDORA'S BOX Do not start with any Kakodamons on the board. At the start of your turn, open Pandora's Box.  Pandora's Box is a deck of seven cards called MISERIES. When you open Pandora's Box, reveal the top card and resolve its effect if any). You may keep revealing and resolving additional cards, one at a time, until you choose to stop. If there are three or more total feathers on revealed cards, you must stop revealing, then Pandora takes 1 damage for each revealed MISERY. At the end of your turn, shuffle all revealed MISERIES back into Pandora's Box.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **DIVINE INTERVENTION** | versatile | 3 | 1 | 2 | **after:** Move Pandora up to 5 spaces. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **FORGED BY HEPHAESTUS** (Any) | scheme | 0 | 1 | 3 | **effect:** Place your fighter in any space. Gain 1 action. |
| **HERA'S CURIOSITY** | attack | 3 | 4 | 3 | **during:** Add +1 to this card's value for each revealed MISERY. · **after:** Look at your opponent's hand. |
| **Spite** (Kakodaemon) | attack | 3 | 2 | 2 | **after:** Deal 1 damage to each fighter adjacent to your fighter. |
| **HINDSIGHT** | attack | 3 | 2 | 3 | **after:** If you won the combat, return a card from your discard pile to the top of your deck. |
| **Malice** (Kakodaemon) | versatile | 2 | 2 | 2 | **after:** Your opponent discards 1 card. |
| **OFFERING TO THE GODS** | defense | 2 | 1 | 2 | **during:** You may BOOST this card. · **after:** If you won the combat, deal 2 damage to the opposing fighter. |
| **ZEUS'S MISCHIEF** | scheme | 0 | 1 | 2 | **effect:** Draw 1 card for each revealed MISERY. Move an opposing fighter up to 1 space. Gain 1 action. |
| **APHRODITE'S BEAUTY** | attack | 3 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. · **after:** Pandora recovers 1 health for each revealed MISERY. |
| **GUIDED BY THE FATES** (Any) | versatile | 2 | 3 | 3 | **during:** Discard the top card of your deck. Add its BOOST value to this card's value. · **after:** If you won the combat, Pandora recovers 2 health. |
| **CELESTIAL RAIMENTS** | defense | 0 | 3 | 2 | **during:** Ignore the value of your opponent's card. |

### Philippa (The Witcher - Realms Fall) — здоровье 12, движение 2

Способность: TWO STEPS AHEAD At the end of your turn, you may draw until you have a hand of 4 cards.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Owlform** | attack | 3 | 3 | 3 | **during:** Discard any number of cards from your hand. Add +1 to this card's value for each card discarded. |
| **Lightning bolt** | attack | 3 | 1 | 3 | **after:** If you haven't taken a maneuver action this turn, deal 1 damage to each opposing fighter in Philippa's zone. |
| **Paralyzing fetters** | defense | 2 | 3 | 2 | **immediately:** The value of your opponent's card is equal to its printed value and cannot be changed. |
| **Spellbreaker** | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. · **after:** End the turn. |
| **Redanian plot** (Any) | versatile | 2 | 1 | 3 | **immediately:** Your opponent may discard 1 card. If they don't, ignore their card's value. |
| **Regicide** (Any) | attack | 4 | 2 | 2 | **during:** If the opposing fighter is a hero, this card's value is 6 instead. |
| **Spymaster's ruse** (Djkstra) | scheme | — | 2 | 2 | **effect:** Choose an opponent. They reveal 4 cards from their hand. Choose 2 of those cards for them to discard. Then, they draw 2 cards. |
| **Backup plan** | scheme | — | 2 | 2 | **effect:** Choose one: - set Philippa's health to 5 - draw 3 cards |
| **Blinding dust** | defense | 2 | 2 | 2 | **after:** You may discard 1 card. If you do, deal damage to the opposing fighter equal to its BOOST value. |
| **Chain lightning** | attack | 2 | 3 | 2 | **after:** Choose a zone Philippa is in. Deal 1 damage to each opposing fighter in that zone. |
| **Cunning** (Any) | versatile | 4 | 1 | 2 | **after:** Your opponent may discard 1 card. If they don't, deal 2 damage to the opposing fighter. |
| **Do my bidding** (Any) | defense | 3 | 3 | 2 | **immediately:** Return your opponent's card to their hand. Look at their hand and choose a card for them to play. (It may be the same card.) |
| **Polymorphy** | scheme | — | 3 | 2 | **effect:** Place Philippa in any space. · **ongoing:** Philippa's move value is 5. Discard this card at the end of your turn if Philippa it not in a zone with an opposing fighter. |

### Raphael (Adventures: Teenage Mutant Ninja Turtles) — здоровье 17, движение 2

Способность: ANGER ISSUES On each of your turns, the first time you lose combat, gain 1 action.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Batter up!** (Casey) | attack | 3 | 2 | 3 | **after:** If you won the combat, move the opposing fighter up to 3 spaces. |
| **Break something** | versatile | 2 | 1 | 3 | **immediately:** Cancel all DURING COMBAT and AFTER COMBAR effects on your opponent's card. · **after:** If no effects were canceled this way, deal 2 damage to an adjacent opposing fighter. |
| **Crowd control** (Any) | attack | 2 | 1 | 3 | **after:** Draw 1 card for each adjacent opposing fighter. Deal 1 damage to each of those fighters. |
| **Heroes in a half shell** | defense | 5 | 2 | 2 | — |
| **Let's do this!** | attack | 1 | 3 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Payback time!** (Any) | versatile | 2 | 1 | 3 | **during:** If you lost a combat this turn, this card's value is 5 instead. |
| **Raphael is cool but rude** | scheme | — | 2 | 2 | **effect:** Deal 1 damage to each opposing fighter adjacent to at least one friendly fighter. Draw 1 card |
| **Relentless** (Any) | versatile | 3 | 1 | 2 | **after:** Shuffle this card in your deck. Then, draw 1 card. |
| **Sai** | versatile | 4 | 2 | 2 | — |
| **Slapshot** (Casey) | versatile | 2 | 2 | 3 | **during:** If Casey is adjacent to the opposing fighter, this card's value is 6 instead. |
| **Turtle power!** | attack | 3 | 3 | 2 | **during:** You may BOOST this attack. |
| **Unbridled rage** | attack | 3 | 4 | 2 | **during:** Discard any number of defense or versatile cards. Add +2 to this card's value for each card discarded this way. |

### Raptors (Jurassic Park - Ingen vs. Raptors) — здоровье 7, движение 3

Способность: Raptors add 1 to the value of their attack cards for each of your other Raptors adjacent to the defender.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Disengage** (Any) | attack | 4 | 2 | 2 | **after:**  Choose an empty space in this fighter's zone. Place this fighter in that space. |
| **Eviscerate** (Any) | attack | 5 | 3 | 2 | — |
| **Pack Hunters** (Any) | attack | 4 | 2 | 2 | **after:**  If you won the combat, deal 1 damage to the opposing fighter for each of your Raptors adjacent to them. |
| **Working Things Out** (Any) | scheme | — | 2 | 2 | **effect:** Move each of your Raptors up to 3 spaces. You may move them through spaces containing opposing fighters. Gain 1 action. |
| **Coordinated Attack Pattern** (Any) | scheme | — | 2 | 2 | **effect:** Choose one of your Raptors. You may place each of your other Raptors in any space in the chosen Raptor's zone. |
| **Decoy** (Any) | defense | 3 | 1 | 4 | **immediately:**  Choose one of your other undefeated Raptors. You may place her adjacent to the opposing fighter. |
| **Eaten Alive** (Any) | versatile | 4 | 2 | 3 | **after:**  If you won the combat, deal 1 damage to one adjacent opposing fighter. |
| **They Remember** (Any) | attack | 2 | 2 | 4 | **after:**  Gain 1 action. |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Ambush** (Any) | attack | 2 | 3 | 3 | **during:**  Your opponent discards 1 random card. Add its BOOST value to this card's attack value. |
| **Clever Girl** (Any) | attack | 3 | 3 | 3 | **after:**  If one or more of your Raptors is adjacent to the opposing fighter, gain 1 action. |

### Robert Muldoon (Jurassic Park - Ingen vs. Raptors) — здоровье 14, движение 3

Способность: At the start of your turn, you may place a trap. Whenever one of your traps is returned to the box, draw a card. Muldoon starts with 8 traps.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Call for Backup** (Muldoon) | scheme | — | 3 | 2 | **effect:** Choose 2 different effects: - place up to 3 traps - place all of your defeated InGen Workers (if any) in Muldoon's zone - draw 2 cards |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Shoot Her!** (Muldoon) | attack | 3 | 1 | 2 | **during:**  If this is your first action this turn, this card's value is 5 instead. |
| **Regroup** (Any) | versatile | 1 | 1 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Remote Detonation** (Any) | scheme | — | 2 | 3 | **effect:** Choose a trap in the same zone as one of your Ingen Workers. Deal 1 damage to each opposing fighter adjacent to that trap. Return that trap. |
| **Second Shot** (Any) | attack | 2 | 3 | 2 | **during:**  You may BOOST this attack. |
| **They Should All Be Destroyed** (Muldoon) | attack | 4 | 3 | 3 | **during:**  +1 to this attack for each trap token adjacent to the opposing fighter. |
| **I've Hunted Most Things That Can Hunt You** (Muldoon) | defense | 4 | 1 | 2 | **after:**  Move each of your fighters up to 5 spaces. You may move them through spaces containing opposing fighters. |
| **Leap Away** (Any) | versatile | 4 | 2 | 3 | **after:**  If you won the combat, choose one of the fighters in the combat and move them up to 4 spaces. |
| **Rending Shot** (Any) | attack | 3 | 1 | 4 | **after:**  Move the opposing fighter up to 3 spaces. |
| **Tactical Advance** (InGen Worker) | versatile | 3 | 3 | 3 | **after:**  Move each of your InGen Workers up to 2 spaces. |

### Robin Hood (Robin Hood vs Bigfoot) — здоровье 13, движение 2

Способность: After you attack, you may move your attacking fighter up to 2 spaces.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Snark** (Any) | versatile | 3 | 1 | 3 | **after:**  If your fighter is adjacent to the opposing fighter, draw 1 card. |
| **Highway Robbery** (Outlaw) | attack | 2 | 2 | 4 | **immediately:**  Cancel all effects on your opponent's card and ignore its defense value. |
| **Wily Fighting** (Any) | versatile | 3 | 1 | 3 | **after:** Deal 1 damage to each opposing fighter adjacent to your fighter. |
| **Disarming Shot** | attack | 4 | 3 | 2 | **after:**  Draw a number of cards equal to the amount of damage dealt to the opposing fighter. |
| **Regroup** (Any) | versatile | 1 | 2 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **A Hunter's Eye** | attack | 5 | 4 | 3 | — |
| **Ambush** (Any) | attack | 2 | 3 | 2 | **during:**  Your opponent discards 1 random card. Add its BOOST value to this card's attack value. |
| **Steal From the Rich** | scheme | — | 3 | 3 | **effect:** Draw 1 card, then choose an opponent. They may choose to discard 1 card. If they do not, draw 1 more card. |
| **Defenders of Sherwood** (Any) | defense | 3 | 2 | 2 | **after:**  Draw 1 card. Return a defeated Outlaw (if any) to any space in Robin Hood's zone. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Piercing Shot** | attack | 2 | 3 | 2 | **after:**  Draw 2 cards. |

### Shakespeare (Slings and Arrows) — здоровье 13, движение 2

Способность: Iambic Pentameter After you attack or defend, add your card to your line. When your line has 10 or more syllables, discard your line. If there are exactly 10 syllables, resolve the completion effect on the last card.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Horror** | attack | 4 | 3 | 1 | **during:** Increase the value of this card by +1 for each HORROR card in your line. Completion: Deal 1 damage to the opposing fighter for each other card in your line. |
| **Once More Unto The Breach** | versatile | 3 | 2 | 2 | **after:** Return a defeated Actor to any space in Shakespeare's zone. Completion: Return all defeated Actors to spaces in Shakespeare's zone. |
| **Deceive** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. Completion: Return this card to your hand. |
| **Horror** | attack | 4 | 3 | 1 | **during:** Increase the value of this card by +1 for each HORROR card in your line. Completion: Deal 1 damage to the opposing fighter for each other card in your line. |
| **Revise** (Any) | versatile | 1 | 2 | 2 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. Completion: Move each fighter up to 2 spaces. (This includes opposing fighters.) |
| **Horror** | attack | 4 | 3 | 1 | **during:** Increase the value of this card by +1 for each HORROR card in your line. Completion: Deal 1 damage to the opposing fighter for each other card in your line. |
| **Horror** | attack | 4 | 3 | 1 | **during:** Increase the value of this card by +1 for each HORROR card in your line. Completion: Deal 1 damage to the opposing fighter for each other card in your line. |
| **My Kingdom For a Horse** | attack | 5 | 3 | 3 | **effect:** Completion: Gain 2 actions. |
| **Again** (Actor) | versatile | 3 | 2 | 3 | **after:** You may return the first card in your line to your hand (before you add this to your line). Completion: Draw 1 card. |
| **Alas** | versatile | 2 | 2 | 2 | **after:** If you lost the combat, Shakespeare recovers 1 health. Completion: Draw 2 cards. Shakespeare recovers 2 health. |
| **Places, Places!** (Any) | attack | 3 | 1 | 2 | **after:** Move each Actor up to 3 spaces. Completion: Place Shakespeare in a zone with no Actors. |
| **The Ides Of March** | versatile | 2 | 2 | 2 | **effect:** Completion: Deal 2 damage to any opposing fighter. |
| **All Are Punished** (Any) | attack | 4 | 2 | 2 | **after:** Deal 1 damage to each other fighter in your zone. Completion: Draw 1 card. |
| **Et Tu, Brute?** (Any) | versatile | 3 | 3 | 2 | **during:** Increase the value of this card by +1 for each of your fighters adjacent to the opposing fighter. Completion: Place each of your fighters in any space. |
| **Horror** | attack | 4 | 3 | 1 | **during:** Increase the value of this card by +1 for each HORROR card in your line. Completion: Deal 1 damage to the opposing fighter for each other card in your line. |
| **Such Sweet Sorrow** (Actor) | versatile | 4 | 2 | 2 | **after:** Move your fighter up to 2 spaces. Completion: Draw 1 card. |

### She Hulk (Brains and Brawn) — здоровье 20, движение 2

Способность: JUST THROW SOMETHING At the start of your turn, you may discard a card to deal damage equal to its BOOST value to a fighter in your zone.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Jennifer Walters, Esq.** | scheme | — | 1 | 2 | **effect:** Place She-Hulk in a starting space. Draw 1 card. Gain 1 action. |
| **Leap Toward** | scheme | — | 1 | 2 | **effect:** Move She-Hulk up to 4 spaces. She may move through opposing fighters. Then, if she is adjacent to an opposing fighter, gain 1 action. |
| **Nerve Cluster Strike** | versatile | 3 | 1 | 3 | **immediately:**  If She-Hulk is adjacent to the opposing fighter, the opposing fighter may not leave their space this turn. |
| **Lady Justice** | defense | — | 2 | 3 | **during:**  Discard the top card of your opponent's deck. Increase the value of this card by twice that card's boost value. |
| **Omega-Level Threat** | attack | 5 | 2 | 2 | **after:**  If you dealt 2 or more combat damage, your opponent discards 2 random cards. |
| **Sensational** | attack | 4 | 2 | 3 | **after:**  If you won the combat, you may choose a card in your discard pile and shuffle it into your deck. |
| **Cease and Desist** | versatile | 1 | 2 | 3 | **immediately:**  Cancel all effects on your opponent's card.  · **during:**  If you are attacking, the value of this card is 4 instead. |
| **Double Jeopardy** | scheme | — | 2 | 2 | **effect:** Draw 2 cards and recover 2 health. |
| **Green Energy** | versatile | 4 | 1 | 3 | **after:**  If you won the combat, deal 1 damage to each fighter adjacent to She-Hulk. |
| **Legalese** | versatile | 2 | 1 | 3 | **after:**  If you won the combat, your opponent chooses whether you both draw a card or both discard a card. If you lost the combat, you make the choice instead (see above). |
| **The Defense Rests** | defense | 2 | 2 | 2 | **after:**  Draw cards equal to the amount of combat damage you took. |
| **The Savage She-Hulk** | attack | 3 | 3 | 2 | **during:**  You may spend an additional action to make this card's value 9 instead. |

### Sherlock Holmes (Cobble & Fog) — здоровье 16, движение 2

Способность: Effects on HOLMES and DR. WATSON cards cannot be canceled by an opponent. Effects on ANY cards can be canceled.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Counterpunch** (Holmes) | versatile | 3 | 1 | 3 | **after:**  If Holmes is adjacent to the opposing fighter, deal 2 damage to that fighter. |
| **Eliminate the Impossible** (Holmes) | scheme | — | 2 | 2 | **effect:** Choose an opponent. Look at their hand and choose 1 card for them to discard. |
| **Fixed Point in a Changing Age** (Dr. Watson) | versatile | 3 | 1 | 2 | **after:**  If Dr. Watson is adjacent to Holmes, they each recover 1 health. |
| **Confirm Suspicion** (Holmes) | scheme | — | 1 | 3 | **effect:** Choose an opponent and name a value. Your opponent must choose and discard one card matching that attack or defense value. Their hero takes damage equal to the BOOST value of the discarded card. If they do not have a card of the named value, they must reveal their hand instead. |
| **Elementary** (Holmes) | defense | 3 | 3 | 2 | **effect:** Play this card face up. Predict the printed attack value of the opponent's card.  · **during:**  If you predicted the correct value, cancel all effects on your opponent's card and ignore its attack value. |
| **Master of Disguise** (Holmes) | scheme | — | 2 | 2 | **effect:** Choose an opponent. Holmes swaps spaces with their hero. Deal 1 damage to that hero. |
| **Service Revolver** (Dr. Watson) | attack | 5 | 3 | 2 | — |
| **Administer Aid** (Dr. Watson) | scheme | — | 2 | 2 | **effect:** Place Dr. Watson in a space adjacent to Holmes. Holmes recovers 1 health. Draw 1 card. |
| **Education Never Ends** (Any) | versatile | 3 | 1 | 2 | **after:**  If you won the combat, your opponent draws 1 card. If you lost the combat, you draw 2 cards. |
| **The Game is Afoot** (Holmes) | attack | 5 | 2 | 2 | **after:**  Move Holmes up to 3 spaces. |
| **Deduce Strategy** (Holmes) | versatile | 3 | 1 | 3 | **during:**  You may change the printed value of the opponent's card to its BOOST value. (If a card does not have a BOOST value, it is treated as 0.) |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Study Methods** (Any) | versatile | 3 | 2 | 2 | **after:**  If you won the combat, look at your opponent's hand. |

### Shredder (TMNT: Shredder vs Krang) — здоровье 15, движение 3

Способность: MASTER OF THE CLAN At the start of your turn, deploy a Foot soldier to a path adjacent to a friendly fighter.  You may attack opposing fighters adjacent to Foot soldiers.  If an opponents boosts their maneuver, they may remove any Foot soldier their hero moves through.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Gruff Escort** (Bebop & Rocksteady) | attack | 4 | 2 | 2 | **after:** Deploy 2 Foot soldiers anywhere. Move Shredder up to 2 spaces. |
| **Master of the Foot** | versatile | 2 | 2 | 2 | **after:** Deal 1 damage to each opposing fighter adjacent to a Foot soldier. |
| **Disrupting Strike** | versatile | 3 | 1 | 2 | **immediately:** The value of your opponent's card is equal to its printed value and cannot be changed. |
| **Obedient Subjects** | scheme | — | 3 | 2 | **effect:** Gain 1 action for each Foot soldier adjacent to Shredder. |
| **All According to Plan** | defense | 3 | 2 | 2 | **after:** Your opponent gains 1 action. At the end of this turn, if they didn't play a scheme, they discard 2 cards. |
| **Swarming Strike** | attack | 5 | 3 | 3 | **during:** Add +1 to this card's value for each adjacent Foot soldier. |
| **Think Hard** (Bebop & Rocksteady) | versatile | 3 | 2 | 2 | **after:** Draw 1 card for each Foot soldier adjacent to the opposing fighter. |
| **Back to work!** | scheme | — | 2 | 2 | **effect:** Bebop & Rocksteady recover 3 health, even if they are defeated. Place them in a space as close as possible to Shredder. |
| **Gang Up** (Bebop & Rocksteady) | attack | 3 | 2 | 2 | **during:** If the opposing fighter is adjacent to 2 or more Foot soldiers, this card's value is 6 instead. |
| **Long Shot** (Any) | versatile | 3 | 1 | 3 | **during:**  If the opposing fighter is not adjacent to your fighter, this card's value is 5 instead. |
| **Masterful Defense** | defense | 2 | 3 | 2 | **after:** Shredder recovers 1 health for each adjacent Foot soldier. |
| **Perplexing Tactics** | versatile | 2 | 3 | 3 | **immediately:** Cancel all effects on your opponent's card. If 10 or more Foot soldiers are deployed, also ignore that card's value. |
| **Savagery** (Any) | attack | 4 | 2 | 3 | **after:** If you won the combat, deal 1 damage to each fighter adjacent to your fighter. |

### Sinbad (Battle of Legends, Volume One) — здоровье 15, движение 2

Способность: When you maneuver, you may move fighters +1 space for each VOYAGE card in your discard pile.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Exploit** (Any) | versatile | 4 | 1 | 2 | **after:**  Draw 1 card. |
| **Feint** (Any) | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Momentous Shift** (Any) | versatile | 3 | 1 | 3 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Toil and Danger** | versatile | 3 | 1 | 4 | **after:**  Move Sinbad up to 3 spaces. |
| **Voyage to the Cannibals With the Root of Madness** | attack | 2 | — | 1 | **during:**  This card's value is +1 for each other VOYAGE card in your discard pile.  · **after:**  You may move Sinbad up to 2 spaces. |
| **Voyage to the Creature With Eyes Like Coals of Fire** | attack | 2 | — | 1 | **during:**  This card's value is +1 for each other VOYAGE card in your discard pile.  · **after:**  Your opponent discards 1 random card. |
| **Voyage to the City of the King of Serendib** | attack | 2 | — | 1 | **during:**  This card's value is +1 for each other VOYAGE card in your discard pile.  · **after:**  Draw 1 card. |
| **Voyage to the Valley of the Giant Snakes** | attack | 2 | — | 1 | **during:**  This card's value is +1 for each other VOYAGE card in your discard pile.  · **after:**  Look at your opponent's hand. |
| **Regroup** (Any) | versatile | 1 | 1 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **By Fortune and Fate** (The Potter) | attack | 3 | 1 | 3 | **after:**  Draw 2 cards. |
| **Commanding Impact** (Any) | attack | 5 | 2 | 1 | **after:**  Draw 1 card. |
| **Leap Away** (Any) | versatile | 4 | 1 | 2 | **after:**  If you won the combat, choose one of the fighters in the combat and move them up to 4 spaces. |
| **Riches Beyond Compare** | scheme | — | 1 | 2 | **effect:** Draw 3 cards. |
| **Voyage Home** | attack | 2 | 1 | 1 | **during:**  This card's value is +1 for each other VOYAGE card in your discard pile.  · **after:**  Take all other VOYAGE cards from your discard pile and add them to your hand. |
| **Voyage to the City of the Man-Eating Apes** | attack | 2 | — | 1 | **during:**  This card's value is +1 for each other VOYAGE card in your discard pile.  · **after:**  Deal 2 damage to the opposing fighter. |
| **Voyage to the Island That Was a Whale** | attack | 2 | — | 1 | **during:**  This card's value is +1 for each other VOYAGE card in your discard pile.  · **after:**  Sinbad recovers 2 health. |

### Spiderman (Brains and Brawn) — здоровье 15, движение 3

Способность: SPIDEY-SENSE When an opponent attacks Spider-Man, before you play a defense card, they must tell you the printed value of their card.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Friendly Neighborhood Spider-Man** (Spider Man) | scheme | — | 3 | 2 | **effect:** Recover 3 Health. Place Spider-Man in any space in his zone. |
| **Spider-Sense Tingling!** (Spider Man) | versatile | 2 | 1 | 3 | **after:**  If the value of your opponent's card is 4 or higher, draw 2 cards. |
| **Thwip!** (Spider Man) | attack | 4 | 1 | 3 | **after:**  If you won the combat, place Spider-Man in any space in his zone. |
| **Disarming Shot** (Spider Man) | attack | 4 | 3 | 2 | **after:**  Draw a number of cards equal to the amount of damage dealt to the opposing fighter. |
| **Snark** (Spider Man) | versatile | 3 | 1 | 2 | **after:**  If your fighter is adjacent to the opposing fighter, draw 1 card. |
| **Wall Crawler** (Spider Man) | versatile | 3 | 1 | 2 | **after:**  Place Spider-Man in any space in his zone. |
| **With Great Power** (Spider Man) | scheme | — | 3 | 2 | **effect:** All of Spider-Man's attacks this turn are +1 value. Draw 1 card. Gain 1 action. |
| **Counter-Attack** (Spider Man) | defense | 3 | 1 | 3 | **after:**  If the value of your opponent's card is 4 or higher, deal 2 damage to the opposing fighter. |
| **Momentous Shift** (Spider Man) | versatile | 3 | 2 | 3 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Right in the Face!** (Spider Man) | versatile | 4 | 2 | 2 | **immediately:**  Your opponent can't draw cards this turn. |
| **Swinging Kick** (Spider Man) | attack | 6 | 2 | 3 | **after:**  You may move the opposing fighter a number of spaces up to the amount of combat damage dealt. |
| **Web Shooters** (Spider Man) | defense | 3 | 2 | 3 | **during:**  Spider-Man cannot take more than 2 combat damage this combat. |

### Spike (Buffy the Vampire Slayer) — здоровье 15, движение 2

Способность: At the start of your turn, you may place a Shadow token in any space adjacent to Spike or Drusilla.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Always Surprising** (Drusilla) | versatile | 1 | 2 | 3 | **during:**  BLIND BOOST this card. If Drusilla's space has a shadow token, double the BOOST value. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Regroup** (Any) | versatile | 1 | 1 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Bloody Hell!** | versatile | 3 | 2 | 3 | **after:**  Deal 1 damage to the opposing fighter, then deal an additional 1 damage for each space with a shadow token adjacent to them. |
| **Leap Away** (Any) | versatile | 4 | 1 | 2 | **after:**  If you won the combat, choose one of the fighters in the combat and move them up to 4 spaces. |
| **Skirmish** (Any) | versatile | 4 | 1 | 2 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **The Sight** (Drusilla) | scheme | — | 2 | 2 | **effect:** Choose an opponent and look at their hand. Choose a card for them to discard. If any of their fighters are in a space with a shadow token, choose 2 cards for them to discard instead. |
| **Arrogance** | attack | 4 | 2 | 1 | **during:**  You may discard your hand (even if your hand is empty). If you do, the value of this card is 6 instead. |
| **Empathy** (Drusilla) | versatile | 3 | 3 | 2 | **after:**  Draw 1 card. If the opposing fighter is in a space with a shadow token, draw 3 cards instead. |
| **Let's Dance** | versatile | 4 | 3 | 3 | **during:**  If Spike or the opposing fighter is in a space with a shadow token, you may BOOST this card. |
| **Seek the Shadows** | scheme | — | 2 | 4 | **effect:** Draw 2 cards. Place a shadow token in Spike's space and each space adjacent to it. |
| **The Rush** | attack | 3 | 3 | 2 | **during:**  If Spike or the opposing fighter is in a space with a shadow token, the value of this card is 5 instead. |

### Squirrel Girl (Teen Spirit) — здоровье 13, движение 2

Способность: GO NUTS! At the start of your turn, summon a squirrel in a space adjacent to Squirrel Girl. Squirrels are small fighters. Do not start with any squirrels on the board.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Eat Nuts** | scheme | — | 2 | 2 | **effect:** Squirrel Girl recovers 2 health. Summon a squirrel in a space adjacent to Squirrel Girl. |
| **Horde of Squirrels** | scheme | — | 2 | 2 | **effect:** Choose a space with four or more squirrels adjacent to it. Deal 2 damage to a fighter in that space. |
| **Squirmish** | versatile | 4 | 1 | 2 | **after:**  Summon a squirrel in Squirrel Girl's space. Then, you place Squirrel Girl in any space in her zone. |
| **Dash** | versatile | 3 | 2 | 2 | **after:**  Move your fighter up to 3 spaces. |
| **Get 'Em Tippy-Toe!** | versatile | 3 | 1 | 3 | **after:**  Summon two squirrels in any space. |
| **Squirgility** | defense | 3 | 2 | 3 | **after:**  Move Squirrel Girl up to 3 spaces. She may move through sidekicks. Do not count movement for spaces containing sidekicks. |
| **Bite of Steel** (Squirrel) | attack | 2 | 2 | 3 | **during:**  If there are four or more squirrels in the opposing fighter's zone, the value of this card is 5 instead. |
| **Call of the Mild** (Any) | versatile | 2 | 2 | 3 | **during:**  If there are four or more squirrels in your fighter's zone, the value of this card is 4 instead.  · **after:**  If you won the combat, draw 2 cards. |
| **Feint** | versatile | 2 | 1 | 2 | **immediately:** Cancel all effects on your opponent's card. |
| **Fuzzball Special** | attack | 3 | 1 | 2 | **after:**  Move each squirrel up to 3 spaces. |
| **Kick Butts** | attack | 1 | 1 | 3 | **during:**  Increase the value of this card by +1 for each squirrel adjacent to the opposing fighter. |
| **Nutwork of Spies** | scheme | — | 2 | 1 | **effect:** Look at an opponent's hand and choose 1 card for them to discard. If one of their fighters is adjacent to four or more squirrels, choose 2 cards instead. |
| **Unbeatable Squirrel Girl** | versatile | 4 | 1 | 2 | **immediately:**  If there are four or more squirrels adjacent to the opposing fighter, cancel all effects on your opponent's card and ignore its value. |

### Sun Wukong (Battle of Legends, Volume Two) — здоровье 17, движение 2

Способность: At the start of your turn, you may take 1 damage to summon a Clone in an empty space adjacent to Sun Wukong. Do not start with any Clones on the board.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Ruyi Jingo Bang** (Any) | attack | 0 | 3 | 3 | **after:**  If your opponent played a defense card, TRICKED YOU. TRICKED YOU: 4 ATK |
| **Ox Form** (Any) | attack | 7 | 2 | 2 | **effect:** This card's effects cannot be canceled.  · **during:**  If your opponent played a card, they may BOOST it. |
| **Taunting Laughter** (Any) | attack | 3 | 2 | 3 | **immediately:**  Your opponent may discard 1 card from their hand. If they don't, ignore their card's value. |
| **Tortoise Form** (Any) | defense | 5 | 2 | 2 | **during:**  Your opponent may BOOST their attack. |
| **Fiery Eyes That See** (Any) | scheme | — | 1 | 2 | **effect:** Look at an opponent's hand and choose a card. Put that card on the bottom of their deck. You each draw 1 card. |
| **Golden Chain Mail** (Any) | defense | 4 | 2 | 2 | **during:**  Any combat damage you would take is dealt to the opposing fighter instead. |
| **72 Transformations** (Any) | versatile | 2 | 2 | 3 | **after:**  Take an OX FORM, TORTOISE FORM, or PHOENIX FORM from your discard pile and return it to your hand. |
| **Bewilderment** (Any) | defense | 0 | 2 | 2 | **during:**  Prevent all damage  · **after:**  You may place your fighter in any space. |
| **Infinite Strikes** (Any) | attack | 2 | 2 | 3 | **during:**  For each other friendly fighter adjacent to the opposing fighter, increase the value of this card by +1.  · **after:**  Gain 1 action. |
| **Phoenix Form** (Any) | scheme | — | 1 | 1 | **effect:** Sun Wukong recovers 1 health for each Clone on the board. |
| **Sly Monkey** (Any) | versatile | 2 | 3 | 4 | **after:**  If Sun Wukong played this card, summon a Clone in Sun Wukong's space, then place Sun Wukong in a space in his zone. |
| **Wily Fighting** (Any) | versatile | 3 | 1 | 3 | **after:** Deal 1 damage to each opposing fighter adjacent to your fighter. |

### T. Rex (Jurassic Park - Sattler vs. T-Rex) — здоровье 27, движение 1

Способность: T-Rex is a large fighter. (She can attack up to 2 spaces away.) At the end of your turn, draw a card. Large fighters have an extended base that can occupy up to two spaces. Large fighters may start moving from any space they are in. When they do, rotate them so that the head is moving into the new space. Their tail always follows behind their head, entering the space the left. Large fighters also ignore one-way arrows on maps and cannot use secret passages. Large fighters can attack up to 2 spaces away, even over fighters that occupy one of those spaces.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Momentous Shift** (T-Rex) | versatile | 3 | 2 | 3 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Ripples in the Water** (T-Rex) | scheme | — | 2 | 3 | **effect:** Place T-Rex in any space in her zone. Then, each opponent with a fighter adjacent to T-Rex discards 1 random card. |
| **You're Just Making Her Angry** (T-Rex) | defense | 1 | 1 | 2 | **during:**  You may BOOST this card.  · **after:**  If you won the combat, return this card to your hand. |
| **65 Million Years of Gut Instinct** (T-Rex) | scheme | — | 3 | 2 | **effect:** Choose a card in your discard pile other than "65 Million Years of Gut Instinct" and return it to your hand. |
| **15,000 Pounds of Muscle** (T-Rex) | attack | 3 | 3 | 2 | **during:**  Ignore the value of your opponent's card.  · **after:**  Take 2 damage. |
| **Closer Than She Appears** (T-Rex) | scheme | — | 2 | 3 | **effect:** Move your fighter up to 1 space. Draw 1 card. Gain 1 action. |
| **Commanding Impact** (T-Rex) | attack | 5 | 2 | 3 | **after:**  Draw 1 card. |
| **Reckless Lunge** (T-Rex) | attack | 3 | 4 | 3 | **after:**  Deal 3 damage to the opposing fighter. Then, take 3 damage. |
| **Terrifying Roar** (T-Rex) | versatile | 3 | 3 | 2 | **immediately:**  Fighters cannot leave their spaces for the rest of the turn. |
| **Thrash** (T-Rex) | versatile | 2 | 2 | 3 | **during:**  You may BOOST this card.  · **after:**  If you won the combat, deal 1 damage to each opposing fighter in T-Rex's zone. |
| **When Dinosaurs Ruled the Earth** (T-Rex) | attack | 2 | 3 | 4 | **during:**  You may BOOST this card.  · **after:**  If you won the combat, draw 1 card, gain 1 action, and take 2 damage. |

### The Genie (Houdini vs. The Genie) — здоровье 16, движение 3

Способность: INFINITE POWER At the start of your turn, you may discard 1 card to gain 1 action.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **I've Made Sultans Out of Less** | versatile | 2 | 1 | 2 | **after:**  Look at your opponent's hand and choose a card for them to discard. |
| **Prisoner's Torment** | defense | 1 | 2 | 2 | **after:**  Draw cards equal to the amount of combat damage you took. |
| **I Am Freed** | attack | 3 | 2 | 2 | **after:**  Place the Genie in any empty space. Then, deal 1 damage to each adjacent fighter. |
| **Feint** | versatile | 2 | 1 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **This is No Parlor Trick** | versatile | 1 | 2 | 2 | **during:**  The value of your opponent's card is equal to its BOOST value. |
| **Wishing For More Wishes** | versatile | 3 | 2 | 3 | **after:**  Your opponent draws 1 card. Draw 3 cards. |
| **Back In The Lamp** | defense | 0 | 1 | 3 | **immediately:**  The Genie recovers 4 health. |
| **Careful What You Wish For** | attack | 4 | 2 | 3 | **after:**  If you lost the combat, deal 1 damage to an adjacent opposing fighter. |
| **I Grant You Death** | versatile | 2 | 1 | 3 | **after:**  You may deal 1 damage to an adjacent fighter. |
| **Imprisoned Wrath** | attack | 3 | 1 | 2 | **after:**  You may discard 2 cards to deal 2 damage to an adjacent opposing fighter. |
| **Three Wishes** | scheme | — | 3 | 3 | **effect:** Gain 1 action and choose one effect: - draw 5 cards - for the rest of your turn, your cards' values are 4 and cannot be changed - each opponent discards 2 cards |
| **Your Wish is My Command** | attack | 3 | 1 | 2 | **after:**  If you won the combat, you may discard 2 cards to gain 1 action. |

### The Wayward Sisters (Slings and Arrows) — здоровье 6, движение 2

Способность: Bubbling Brew Your cards go into your cauldron instead of your discard pile. After you attack, you may cast one spell that you have the ingredients for If you do, discard all the cards in your cauldron.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Fire Burn And Cauldron Bubble** (Any) | versatile | 3 | 2 | 3 | **immediately:** Return a card in your discard pile to your cauldron. |
| **Something Wicked This Way Comes** (Any) | scheme | — | 3 | 2 | **effect:** Cast any spell. Then, cast a different spell. (Do not discard any cards from your cauldron to cast these spells.)) |
| **Ward** (Any) | versatile | 3 | 2 | 3 | **after:** Place the opposing fighter in any space in your fighter's zone. |
| **Curious Familiar** (Any) | versatile | 2 | 3 | 2 | **after:** Return a card in your cauldron to your hand. |
| **Pricking Of My Thumbs** (Any) | defense | 2 | 1 | 2 | **after:** Deal damage to the opposing fighter equal to the amount of combat damage your fighter took. |
| **Toil And Trouble** (Any) | defense | 2 | 3 | 3 | **during:** Increase the value of this card by +1 for each different ingredient symbol in your cauldron. |
| **Double, Double** (Any) | attack | 3 | 2 | 3 | **during:** Increase the value of this card by +1 for each different ingredient symbol in your cauldron. |
| **Prophecy** (Any) | scheme | — | 2 | 2 | **effect:** Look at the top 4 cards of your deck. Add 2 of them to your hand and put the other 2 back on top of your deck, in any order. |
| **Unnatural Remedy** (Any) | defense | 1 | 2 | 2 | **immediately:** Discard up to 3 cards from your cauldron. For each one, choose a fighter to recover 1 health. (You may choose the same fighter more than once) |
| **Hurly-Burly** (Any) | attack | 3 | 1 | 3 | **during:** Reveal the top card of your deck. Your opponent chooses one: - put that card in your hand, - put that card in your cauldron and add its BOOST value to this card's value |
| **All-Seeing Familiar** (Any) | attack | 4 | 2 | 2 | **immediately:** Return a card in your discard pile to your cauldron. · **after:** If you won the combat, look at the top card of your deck and put it in your hand or cauldron. |
| **The Stars Align** (Any) | versatile | 0 | 1 | 3 | **during:** The value of this card is equal to the number of different zones all of your fighters are in. |

### Titania (Slings and Arrows) — здоровье 12, движение 2

Способность: Fairy Magic If you do not have a face-up glamour at the start of your turn, flip the top card of your glamour deck face-up. Its effect is ongoing while it remains face-up.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **As Wise As Beautiful** | versatile | 2 | 2 | 3 | **after:** Draw 1 card. You may discard your glamour to draw 2 cards instead. |
| **Met By Moonlight** (Oberon) | attack | 5 | 2 | 3 | **after:** Place Oberon in a space adjacent to Titania. |
| **Protection Of The Fairy Woods** (Any) | defense | 2 | 1 | 3 | **immediately:** You may discard your glamour. If you do, cancel all effects on your opponent's card. |
| **The Moon Looks Down** | versatile | 3 | 2 | 2 | **after:** Put a discarded glamour on the bottom of your glamour deck. |
| **What Fools These Mortals Be** (Oberon) | scheme | — | 2 | 2 | **effect:** Choose an opponent, look at their hand, and choose a card. They shuffle that card into their deck. |
| **Fairy Song** (Any) | versatile | 3 | 2 | 3 | **during:** You may discard your glamour. If you do, the value of this card is 5 instead. |
| **A Momentary Glance** | scheme | — | 4 | 2 | **effect:** Deal 2 damage to any fighter in Titania's zone. |
| **But A Dream** | defense | 0 | 2 | 2 | **immediately:** Cancel all effects on your opponent's card, ignore its value, and return it to your opponent's hand. · **after:** Draw 1 card. |
| **Gift Of The Fair Folk** (Any) | scheme | — | 2 | 3 | **effect:** Choose 2 different effects: - one fighter recovers 2 health, - draw 2 cards, - move two fighters up to 2 spaces each |
| **Parting Gift** (Any) | versatile | 2 | 1 | 2 | **after:** You may deal 2 damage to each fighter in the combat. |
| **Queen Of The Fairies** | attack | 2 | 3 | 2 | **during:** Increase the value of this card by +1 for each glamour in your glamour discard pile. |
| **Whisked Away** (Any) | versatile | 4 | 1 | 3 | **after:** Move your fighter up to 2 spaces. You may discard your glamour. If you do, place your fighter in any space. |

### Tomoe Gozen (Sun's Origin) — здоровье 14, движение 2

Способность: ATTACK OF OPPORTUNITY When an opposing hero leaves Tomoe Gozen's zone, deal 1 damage to that hero. If only I could find a worthy foe.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Deeds of Valor** | defense | 2 | 2 | 3 | **during:**  Tomoe Gozen cannot take more than 2 combat damage this combat. |
| **A Worthy Opponent** | versatile | 3 | 3 | 3 | **during:**  If the opposing fighter is a hero, this card's value is 5 instead. |
| **Fearsome Strength** | attack | 3 | 1 | 2 | **immediately:**  Tomoe Gozen may swap spaces with an adjacent fighter.  · **after:**  Deal 1 damage to an adjacent fighter. |
| **Five Against Thousands** | attack | 4 | 1 | 2 | **after:**  If Tomoe Gozen is adjacent to the opposing fighter, you may discard a card to put this card back into your hand. |
| **Lord Kiso's Final Stand** | scheme | — | 2 | 3 | **effect:** Move Tomoe Gozen up to 3 spaces. She may move through sidekicks. Then, choose one: - Tomoe Gozen recovers 2 health - gain 1 action |
| **Refuse to Retreat** | defense | 3 | 2 | 2 | **immediately:**  Tomoe Gozen cannot leave her space for the rest of the turn.  · **after:**  If the opposing fighter is adjacent, your opponent discards 1 card. |
| **Witness My Last Battle** | attack | 7 | 4 | 2 | **effect:** This attack can only target a fighter adjacent to Tomoe Gozen. Play it face up.  · **after:**  End the turn. |
| **A Warrior's Way** | attack | 2 | 1 | 2 | **after:**  Move the opposing fighter up to 3 spaces. Then, if they are a hero, place Tomoe Gozen in a space adjacent to them. |
| **Confront Any Demon or God** | versatile | 3 | 3 | 2 | **after:**  Draw 1 card. Then, if you lost the combat, look at your opponent's hand and choose 1 card for them to discard. |
| **Flash of Steel** | versatile | 2 | 1 | 3 | **immediately:**  If the opposing fighter is a hero, cancel all effects on your opponent's card.  · **after:**  If the opposing fighter is adjacent, deal 1 damage to them. |
| **Piercing Shot** | attack | 2 | 1 | 3 | **after:**  Draw 2 cards. |
| **Skirmish** | versatile | 4 | 1 | 3 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |

### Willow (Buffy the Vampire Slayer) — здоровье 14, движение 2

Способность: When Willow or Tara is dealt damage, Willow becomes Dark Willow. At the end of your turn, if Dark Willow is adjacent to Tara, she becomes Willow.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Black Magic** | versatile | 3 | 3 | 3 | **during:**  (DARK) BLIND BOOST this card. |
| **Flayed Alive** | attack | 4 | 3 | 3 | **during:**  (DARK) BLIND BOOST this attack. |
| **Hacker** (Any) | versatile | 2 | 2 | 2 | **after:**  Look at the top card of your deck, then choose to put it on the top of your deck or the bottom of your deck. |
| **Love and Loss** | scheme | — | 3 | 2 | **effect:** Draw 2 cards. (DARK) Discard the top 2 cards of your deck. Deal 3 damage to a sidekick in your zone (even if it's your own). |
| **Regroup** (Any) | versatile | 1 | 1 | 3 | **after:** Draw 1 card. If you won the combat, draw 2 cards instead. |
| **Resurrect** | scheme | — | 2 | 2 | **effect:** Choose a friendly fighter who has been defeated. Place that fighter in any space in Willow's zone and set their health to 3. |
| **When Good Magic Fails** | attack | 4 | 3 | 2 | **after:**  (DARK) Move Willow to any space in her zone. Discard the top card of your deck. |
| **Revoke** (Tara) | versatile | 3 | 2 | 2 | **immediately:**  Cancel any abilities on your opponent's card. |
| **Feint** (Any) | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Knowledge of the Craft** (Tara) | versatile | 4 | 2 | 2 | **after:**  If you won the combat, choose a card in your discard pile and add it to your hand. |
| **Meditation** | defense | 5 | 2 | 2 | **after:**  (DARK) Become Willow. |
| **Rending Shot** (Any) | attack | 3 | 1 | 2 | **after:**  Move the opposing fighter up to 3 spaces. |
| **Swift Strike** (Any) | attack | 3 | 2 | 2 | **after:**  Move your fighter up to 4 spaces. |

### Winter Soldier (For King and Country) — здоровье 15, движение 2

Способность: BRAINWASHED Effects on Winter Soldier's cards cannot be canceled.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **A Boy Named Bucky** | scheme | — | 3 | 2 | **effect:** Ignore any {RED ROOM} effects on your cards for the rest of your turn. Gain 1 action. |
| **Programmed to Kill** | attack | 4 | 2 | 2 | **after:**  {RED ROOM} If you won the combat, take 2 damage. |
| **Feint** | versatile | 2 | 2 | 3 | **immediately:** Cancel all effects on your opponent's card. |
| **Complete the Mission** | defense | 3 | 2 | 3 | **during:**  You may BOOST this card.  · **after:**  Deal damage to the opposing fighter equal to the amount of combat damage you took. |
| **Reflex Memories** | versatile | 5 | 2 | 2 | **after:**  {RED ROOM} Discard 2 random cards, then draw 2 cards |
| **Reprogram** | versatile | 2 | 2 | 3 | **after:**  Choose 3 cards in your discard pile and shuffle them into your deck. |
| **Bionic Arm** | attack | 2 | 1 | 3 | **during:**  If Winter Soldier is adjacent to the opposing fighter, the value of this card is 6 instead.  · **after:**  {RED ROOM} Your opponent moves each of their fighters up to 5 spaces. |
| **Born in the Barracks** | versatile | 3 | 2 | 2 | **after:**  If you won the combat, Winter Soldier recovers 2 health. |
| **Manipulation** | scheme | — | 3 | 2 | **effect:** Draw until you have 5 cards in your hand. {RED ROOM} Each opponent may draw until they have 5 cards in their hand. |
| **Marksman** | attack | 1 | 1 | 3 | **during:**  Add +1 to this card's value for each space between you and the opposing fighter along the shortest path. |
| **Wily Fighting** | versatile | 3 | 1 | 2 | **after:** Deal 1 damage to each opposing fighter adjacent to your fighter. |
| **Without Remorse** | attack | 6 | 2 | 3 | **after:**  {RED ROOM} Your opponent may draw 1 card. |

### Yennefer & Triss (The Witcher - Realms Fall) — здоровье 14, движение 2

Способность: At the beginning of the game, choose Yennefer or Triss to be your hero.  Sorceress of Vengerberg IMMEDIATELY: If Yennefer is attacking, you may BOOST her attack. (This effect cannot be canceled.)  Merigold the Fearless After Triss plays a scheme, deal 2 damage to a fighter adjacent to Triss.

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Merigold's Hailstorm** (Triss) | attack | 4 | 3 | 2 | **after:** Your opponent chooses one: - they discard 2 cards - deal 3 damage to their hero - they discard the top 4 cards of their deck |
| **Quick and ready** (Any) | versatile | 2 | 2 | 2 | **after:** Place your fighter in any space in their zone. Draw 1 card. |
| **Paralyzing fetters** (Any) | defense | 2 | 2 | 3 | **immediately:** The value of your opponent's card is equal to its printed value and cannot be changed. |
| **Incinerate** (Yennefer) | attack | 7 | 2 | 3 | **effect:** This card's effect cannot be canceled. · **during:** Your opponent may discard 2 cards to ignore this card's value. |
| **Magical barrier** (Any) | defense | 4 | 3 | 3 | **immediately:** Your fighter recovers 1 health. |
| **Portal to anywhere** (Any) | attack | 1 | 2 | 3 | **after:** Place a fighter in the combat in any space. Gain 1 action. |
| **Ball lightning** (Any) | versatile | 3 | 1 | 3 | **after:** If you won the combat, your opponent discards 1 card. Otherwise, both players discard 1 card. |
| **Echoing blast** (Any) | attack | 3 | 1 | 3 | **after:** If you won the combat, return this card to your hand. |
| **Lodge of sorceresses** (Any) | scheme | — | 2 | 2 | **effect:** Each player simultaneously reveals a card from their hand and draws cards equal to their card's BOOST value. Then, the player(s) who drew the most cards deals that much damage to their hero. |
| **Advisor to the king** (Any) | scheme | — | 2 | 3 | **effect:** Each of your fighters recovers 1 health. Draw 1 card. · **ongoing:** Your BOOST values are +1. Discard this card at the end of your turn if you didn't attack. |
| **Telepathy** (Any) | versatile | 3 | 1 | 3 | **immediately:** Your opponent may discard 1 card. If they don't cancel all effects on their card. |

### Yennenga (Battle of Legends, Volume Two) — здоровье 15, движение 2

Способность: If Yennenga would take damage, you may assign any amount of that damage to one or more Archers in her zone instead. (You may not assign more damage to an Archer that their remaining health.)

| Карта | Тип | Значение | BOOST | × | Эффект |
|---|---|---|---|---|---|
| **Skirmish** (Any) | versatile | 4 | 2 | 2 | **after:** If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces. |
| **Surprise Volley** (Any) | attack | 3 | 3 | 3 | **immediately:**  You may return a defeated Archer to a space in the opposing fighter's zone. If you do, that Archer is now the attacker. If not, gain 1 action. |
| **Rain of Arrows** | attack | 3 | 3 | 3 | **after:**  VOLLEY: 3 ATK |
| **Master of the Hunt** | scheme | — | 3 | 2 | **effect:** Gain 2 actions. |
| **Pin the Prey** (Archer) | versatile | 1 | 2 | 2 | **after:**  Move the opposing fighter up to 4 spaces. Your opponent discards 1 card. |
| **One With The Land** | scheme | — | 2 | 2 | **effect:** Move each of your fighters up to 2 spaces. Each of your fighters recovers 1 health. Draw 1 card. |
| **Divide and Conquer** (Archer) | versatile | 2 | 1 | 2 | **during:**  If your fighter is not in Yennenga's zone, the value of this card is a 4 instead. |
| **Jaws of the Beast** | versatile | 3 | 3 | 3 | **during:**  For each zone the opposing fighter is in, increase the value of this card by +1. |
| **Momentous Shift** (Any) | versatile | 3 | 2 | 3 | **during:** If your fighter started this turn in a different space, this card's value is 5 instead. |
| **Point Blank** | versatile | 2 | 2 | 3 | **after:**  If the opposing fighter is adjacent to Yennenga, deal them 2 damage. |
| **Shield Formation** | defense | 3 | 3 | 2 | **immediately:**  Your opponent may discard a card. If they don't, return a defeated Archer to a space in Yennenga's zone. |
| **Stallion Charge** | versatile | 3 | 3 | 3 | **after:**  Move Yennenga up to 5 spaces. She may move through opposing fighters. Then, deal 1 damage to each opposing fighter she moved through. |
