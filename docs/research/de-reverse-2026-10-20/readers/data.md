## Данные из оригинала Unmatched DE и сверка с нашими: вердикт

**Коротко.** Извлечённые из DE данные точные: числа взяты из `.ctor` классов IL2CPP. Но они покрывают только 14 базовых героев (~17% нашего ростера) и дают только английский текст. По этим 14 героям наши данные совпадают с DE почти на 100%. Сверка нашла 4 бага данных и 1 баг кода. Делать общий импортёр не стоит. Хватит одноразового fix-скрипта и, по желанию, теста-сверки только по числам. Отдельный и самый ценный результат: из ISIL оригинала я вынул графы досок Marmoreal и Sarpedon. Они изоморфны нашим фикстурам с учётом зон.

### 1. Что лежит в `unmatched-data`
- `cards-full.json` содержит 189 записей карт, это привязанная версия. `cards.json` — сырые immediate-константы ISIL, промежуточный шаг. Сводки: `cards-full-summary.txt`, `cards_summary.txt`, `cards_from_code.txt`.
- `heroes-stats.json` — 14 героев и их сайдкики. Метод описан в `_meta` (`heroes-stats.json:1-27`).
- `textassets/*.txt` — локализации, 15 языков. `textassets/*Normal|Heroic.json` — сценарии челленджей (`AScreechofHarpiesNormal.json`: Battlefield Sarpedon, колоды Medusa и KingArthur, abilityArchetypes). `DuelAIConstants-0..2.json` — веса ИИ.
- `inventory.json` и `parts/*.bundle.json` — только опись объектов Addressables-бандлов (тип, имя, размер, path_id). Поля MonoBehaviour в них не сняты. Это 220 бандлов, 1771 Texture2D, 145 AudioClip, 53k MonoBehaviour (`scan_stdout.txt`, `driver_log.txt`). Игровых данных там нет.
- `catalog_strings.txt` и `metadata_strings.txt` — строки каталога и метаданных, в том числе префабы `battlefield_*`. `scripts/` — питон-скрипты извлечения (`bind_cards.py`, `bind_heroes.py`, `extract_localization.py` и др.).

### 2. Поля героев и карт DE
**Герой и сайдкик** (`heroes-stats.json`, `_meta.attributeOffsets`):
- Health, Move, AttackType (enum Melee=1 / Ranged=2, `.../data/enums/AttackTypes.cs`), Copies (число одинаковых фигурок: Harpy 3, Outlaw 4, Sister 3), EntityType (Hero=2 / Sidekick=3 / Token=8), Set, ArchID/GUID, AbilityIDs.
- У Jekyll и Hyde два архетипа героя, DrJekyll и MrHyde, оба HP16, связаны через `ReferencedArchetypeIDs`. У Sherlock есть токен `ClueToken`.
- Лимит руки как константа не найден. Стартовая рука — `StartingDrawAmount`, по умолчанию 5 (`heroes-stats.json:27`).
- Текст способности героя есть только в локализации (`fighter.<x>.abilitydescription`).

**Карта** (`cards-full.json`):
- `card_type`: Attack 58 / Defense 21 / Versatile 69 / Scheme 40 / 1 неизвестная (`cards-full-summary.txt:4`).
- Значение (`AttackDefenseValue`), `BoostValue`, `Copies`, `Set`.
- `Fighter` — у 133 карт. Это ссылка на класс бойца, то есть баннер; если поля нет, карта играется любым бойцом.
- `abilities` — список классов способностей.
- Тексты по таймингам: CombatImmediate 22, CombatDuring 39, CombatAfter 98, Scheme 40, CardEffect 4.
- Служебные поля: `Tags` (41, значения не разрешены), `SchemeWarningKey` (20; например NoAdjacentEnemyFightersToHero), `AIArchetypeValue` (29, значение unknown), `ModifyPositionValue`, `Uncancellable`, `OverrideMoveEvaluator`.

### 3. Объёмы и наборы
- Числа есть для 14 героев: Alice, Beowulf, Bigfoot, Bruce Lee, Dracula, Invisible Man, Jekyll&Hyde, King Arthur, Little Red, Medusa, Muhammad Ali, Robin Hood, Sherlock Holmes, Sinbad.
- Это 189 карт-архетипов на 418 копий. Ещё 2 копии Crash Through the Trees потеряны: «дамп оборван» (`cards-full-summary.txt:17-18`).
- У DLC-героев есть только папки с ачивками и строками, 0 карт и 0 способностей в коде (`cards_from_code.txt`, например Yennenga, Achilles, Sun Wukong).
- Enum `Sets` (`.../data/enums/Sets.cs`) содержит коробки 2–10, поля битвы 100–110 и колоды героев 200–229.

### 4. Есть ли структурированное описание эффектов
Только частично. Каждая карта ссылается на классы способностей: 156 разных на 189 карт, из них 36 общих в `Shared` (`cards_from_code.txt`, раздел Shared). Например CancelAbility×16, Draw1AfterAbility×10, Gain1ActionAfter/Scheme×8. Числа иногда зашиты в имя класса (Draw2, MoveFighter3, VictorDamage8). Параметры уникальных способностей — это код в ISIL, в данные они не вынесены («значения НЕ выдуманы, лежат в .ctor способностей», `cards-full-summary.txt:13-14`). Декларативного описания эффектов, как наш `Card.effects`, нет.

### 5. Локализации
| Язык | Строк | Тексты карт |
|---|---|---|
| en, de, fr, ja, ko, pl, zh_CN | 2226 | есть (842 строки `action.*` в en_US) |
| cs, es, it, pt, **ru**, tr, uk, zh_TW | 415 | нет, только UI |

Русского текста карт в DE нет (`grep ^action. ru_RU.txt` = 0). Тексты en есть и для DLC: 35 abilitydescription, 33 `deck.*` (`textassets/en_US.txt`). DE переписал тексты под цифру; смысл в проверенных примерах тот же, что у печатных карт.

### 6. Генератор DuelEngine
`duel-engine/generate_real_content.py`:
- Берёт числа из `cards-full.json` и `heroes-stats.json`.
- Имена и тексты анонимизирует («Дуэлянт I», `:80`; «Союзник», `:71`).
- **Теряет баннер `Fighter`**, то есть ограничение «какой боец играет карту».
- Пропускает Crash Through the Trees (`:35`), из-за этого у Bigfoot колода 28 карт.
- Не создаёт MrHyde.
- Жёстко прописывает handLimit 7 (`:83`) и три флага героев (`:88`).

`patch_content.py` — одноразовый патчер C#-исходников Unity с абсолютным путём к чужой машине (`patch_content.py:3`). Для нас ни тот, ни другой не пригодны.

### 7. Сверка с нашими данными
**Метод.** Парсер devalue-JSON повторяет логику `backend/prisma/seed-scraped.ts:61-173`. Источник — `scraped-data/api/heroes/<slug>.json` (the-unmatched.club). Сверены все 14 общих героев, а не только 8. Учтены правки `backend/prisma/fix-card-gaps.ts`. Docker остановлен, поэтому живую БД я не читал. Состояние БД сверено косвенно: по `docs/backend-api/09-cards-and-effects.md` и `docs/game-design/evidence/DE-FOOTAGE/2026-10-04/F/de030/de030-decklists-marmoreal.json` (живой ответ API по Medusa и Arthur).

**Совпало полностью (14/14):**
- HP, Move и тип атаки героя.
- Число, HP, Move и тип атаки сайдкиков: Jabberwock 8/2, Wiglaf 9/2, Jackalope 6/3, Sister×3 1/2, Merlin 7/2 ranged, Huntsman 9/2 ranged, Harpy×3 1/3, Outlaw×4 1/2, Watson 8/2 ranged, Porter 6/2.
- Размер колоды 30.
- Тип всех карт и копии всех карт.
- Бусты, кроме Voyage (ниже). Разный буст Feint у разных героев тоже совпал.
- Тайминги у 184 из 188 карт. Остальные 4 — DE CardEffect против нашего общего `effect`.

**Расхождения — потенциальные баги наших данных:**

1. **What Big Eyes You Have (Little Red):** значение у нас 2, в DE 3. Третий источник, UmDb (`.playwright-mcp/cards_database_snapshot.md:2173`), тоже даёт 3. Наш скрейп: `scraped-data/api/heroes/little-red.json:306`, в документации БД значение 2 (`docs/backend-api/09-cards-and-effects.md:916`). Скорее всего это баг.
2. **Баннер «Allice»** у 8 карт Alice (`scraped-data/api/heroes/alice.json:150`, `docs/backend-api/09-cards-and-effects.md:212-222`). `bannerAllows` его не узнаёт, а `validateBanner` при неизвестном баннере пишет warn и разрешает карту (`backend/src/game-engine/validators/game-rules.validator.ts:574-587`). В итоге Jabberwock может играть карты, которые должна играть только Alice.
3. **Баннер «The Potter»** вместо The Porter у By Fortune and Fate (`scraped-data/api/heroes/sinbad.json:521`). Механизм тот же: карту помощника может играть Sinbad.
4. **Voyage-карты Sinbad (6 шт.):** буст у нас null, в DE 0.
5. **Банер обычных карт:** у Bruce Lee (Feint, Momentous Shift, Regroup, Skirmish) и у Ali (Momentous Shift) баннер — имя героя, а в DE «Any». В источнике нет «Any», и seed подставляет имя героя (`seed-scraped.ts:143`). На игру почти не влияет, потому что сайдкиков у них нет.
6. **Stones in the Belly:** в источнике значение null, `fix-card-gaps.ts:44` ставит 2. DE даёт 2 — правка подтверждена.
7. **Только написание, на игру не влияет:**
   - регистр имён у 10 карт Ali («Answer the bell» и т.п.) и мелкие Aid the/The, Steal From/from;
   - эмодзи-символы корзины в именах 12 карт Little Red;
   - «Corkscrew Finger Jab» у нас и в UmDb против «…Fan» в DE;
   - сайдкики во множественном числе (Harpies, Outlaws, The Sisters) и Huntsman против The Huntsman. Это `bannerAllows` нормализует (`game-rules.validator.ts:603-613`).
8. **Jekyll&Hyde:** баннеры «Dr. Jekyll» и «Mr. Hyde» не совпадают с бойцом «Jekyll & Hyde», поэтому ограничение по форме не работает. У DE это два архетипа. Это пробел движка, а не данных: grep jekyll/hyde по `backend/src` ничего не находит.
9. **Баг кода, не данных:** `backend/src/content/mappers/content.mapper.ts:94` и `:230` жёстко отдают `movement: 3` в каталожных DTO. Партия при этом берёт Move из БД (`games/services/game-initialization.service.ts:209`). DE подтверждает Move 2 у 10 из 14 героев, то есть каталог врёт для них.
10. **Русский язык:** seed пишет в `nameRu` английское имя (`seed-scraped.ts:296-297, 341-342`). В скрейпе ru-перевод есть только у 62 из 880 карт, исправлены вручную 27 карт ростера (`fix-roster-ru.ts`). DE тут ничем не поможет.

**Доски — главное подтверждение.** Определения полей битвы лежат в коде оригинала: класс `DuelSpaceDefinition(index, zones[])`, `DuelLineDefinition(indexA, indexB)` (`cpp2il-cs/.../data/battlefield/*.cs`), тело — в `cpp2il-isil/.../data/Battlefields/Marmoreal/Marmoreal.txt`. Мой одноразовый парсер ISIL (временные скрипты, в репозиторий не записаны) показал:
- Marmoreal: 31 клетка и 42 связи, зоны Green14/Blue14/Brown7/Gray6/Yellow5/Purple5/Violet4/Red4;
- Sarpedon: 38 клеток и 61 связь, зоны Purple11/Yellow8/Green8/Red6/Blue6/Brown5.

Это ровно совпадает со `summary` в `backend/prisma/fixtures/boards/{marmoreal,sarpedon}.topology.json`. Найден изоморфизм графов с совпадением набора зон у каждой клетки. Номера клеток разные. Стартовые клетки и тайные проходы я не сверял.

### 8. Стоит ли делать импортёр
**Нет**, как постоянный импортёр в БД.

Почему:
- охват 14 из ~84 героев;
- по ним совпадение и так ~99%;
- нет ru, нет чисел DLC-героев, нет параметров эффектов;
- у самого извлечения есть дыры (Crash Through the Trees).

Что дать вместо этого:
- одноразовый идемпотентный fix-скрипт: Big Eyes = 3, Allice → Alice, The Potter → The Porter, по желанию Voyage boost 0 и Any у обычных карт Bruce Lee и Ali;
- исправить `movement: 3` в mapper;
- по желанию — тест-сверку только по числам (HP, move, value, boost, copies, banner) как эталон, без текстов;
- если понадобится точная проверка досок, сохранить графы Marmoreal и Sarpedon из DE как эталон.

**Архитектурные уроки из данных DE:**
- Баннер в DE — типизированная ссылка на бойца. У нас строка с нечётким сравнением и разрешением по умолчанию, поэтому опечатки молча проходят. Стоит валидировать баннер при seed и падать на неизвестном.
- Копии, которые отличаются символом, DE хранит отдельными архетипами (Into the Woods A/B/C) плюс enum `BasketItems` (`.../enums/BasketItems.cs`). У нас символы зашиты эмодзи в имени, и 3 копии склеены в одну строку. Это помешает, если реализовывать корзину Little Red.
- `SchemeWarningKey` — ключ «схема ничего не сделает» прямо на карте.
- Список ability-ID на карту годится как разметка для проверки нашего `effect-text-parser` (например Draw1AfterAbility ↔ DRAW 1 AFTER).

**IP коротко.** Тексты, арт и код принадлежат правообладателю, как и наш текущий скрейп. Тащить в репозиторий декомпилированное и тексты DE не стоит. Числа и топология — игровые факты, риск ниже.

--- keyFacts
[F1](high) В DE-данных числа есть ровно для 14 героев (189 карт-архетипов, 418 копий); у DLC-героев (Yennenga, Achilles, Sun Wukong и др.) в коде 0 карт и 0 способностей — только локализация. {DuelEngine-transfer/test-targets/unmatched-data/heroes-stats.json:1;DuelEngine-transfer/test-targets/unmatched-data/cards-full-summary.txt:3-4;DuelEngine-transfer/test-targets/unmatched-data/cards_from_code.txt}
[F2](high) Bigfoot/Crash Through the Trees в DE не извлечена (тип/значение/копии неизвестны, дамп ISIL оборван) — колода Bigfoot в DE и в DuelEngine 28 карт вместо 30. {DuelEngine-transfer/test-targets/unmatched-data/cards-full-summary.txt:17-18;DuelEngine-transfer/test-targets/unmatched-data/cards-full.json:5296;DuelEngine-transfer/duel-engine/generate_real_content.py:35}
[F3](high) Структурированных параметров эффектов в данных нет: на карту — список классов способностей (156 разных, 36 общих в Shared), числа уникальных способностей остаются в коде ISIL. {DuelEngine-transfer/test-targets/unmatched-data/cards-full-summary.txt:13-14;DuelEngine-transfer/test-targets/unmatched-data/cards_from_code.txt}
[F4](high) ru_RU в DE — 415 строк только UI, тексты карт и героев есть лишь в en/de/fr/ja/ko/pl/zh_CN (2226 строк). {DuelEngine-transfer/test-targets/unmatched-data/textassets/ru_RU.txt;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:15037}
[F5](high) У всех 14 общих героев совпадают с DE HP, Move, тип атаки героя, число/HP/Move/тип атаки сайдкиков, размер колоды, типы и копии всех карт. {DuelEngine-transfer/test-targets/unmatched-data/heroes-stats.json:300-2851;scraped-data/api/heroes/*.json;backend/prisma/seed-scraped.ts:61-173}
[F6](medium) What Big Eyes You Have (Little Red): у нас значение 2, в DE 3 и в UmDb 3 — вероятный баг наших данных. {DuelEngine-transfer/test-targets/unmatched-data/cards-full.json:23297;scraped-data/api/heroes/little-red.json:306;docs/backend-api/09-cards-and-effects.md:916;.playwright-mcp/cards_database_snapshot.md:2173}
[F7](high) Баннер 'Allice' у 8 карт Alice и 'The Potter' у By Fortune and Fate (Sinbad): validateBanner при неизвестном баннере пишет warn и разрешает карту, поэтому ограничение «карту играет только свой боец» для них не работает. {scraped-data/api/heroes/alice.json:150;scraped-data/api/heroes/sinbad.json:521;docs/backend-api/09-cards-and-effects.md:212;backend/src/game-engine/validators/game-rules.validator.ts:574-587}
[F8](high) Stones in the Belly: в источнике значение null, fix-card-gaps.ts ставит 2; DE подтверждает 2. {backend/prisma/fix-card-gaps.ts:44;DuelEngine-transfer/test-targets/unmatched-data/cards-full.json:22540}
[F9](high) 6 Voyage-карт Sinbad: буст у нас null, в DE 0; у обычных карт Bruce Lee (4) и Ali (Momentous Shift) баннер = герой вместо Any (seed подставляет имя героя). {backend/prisma/seed-scraped.ts:143;DuelEngine-transfer/test-targets/unmatched-data/cards-full.json:35776}
[F10](high) Каталожные DTO героя жёстко отдают movement 3 и не читают Hero.movement; DE подтверждает Move 2 у 10 из 14 героев (партия при этом берёт move из БД). {backend/src/content/mappers/content.mapper.ts:94;backend/src/content/mappers/content.mapper.ts:230;backend/src/games/services/game-initialization.service.ts:209}
[F11](high) Графы Marmoreal (31 клетка/42 связи) и Sarpedon (38/61) из ISIL оригинала изоморфны нашим фикстурам с учётом зон; поштучные числа клеток в зонах совпадают. {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/data/Battlefields/Marmoreal/Marmoreal.txt;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/battlefield/DuelLineDefinition.cs:6-12;backend/prisma/fixtures/boards/marmoreal.topology.json;backend/prisma/fixtures/boards/sarpedon.topology.json}
[F12](high) Генератор DuelEngine теряет баннер Fighter, пропускает Crash Through the Trees, не создаёт MrHyde, анонимизирует имена; patch_content.py — одноразовый патчер с абсолютным путём к чужой машине. {DuelEngine-transfer/duel-engine/generate_real_content.py:35;DuelEngine-transfer/duel-engine/generate_real_content.py:37;DuelEngine-transfer/duel-engine/generate_real_content.py:80;DuelEngine-transfer/duel-engine/patch_content.py:3}
[F13](high) Наш seed пишет английское имя в nameRu героев и карт; ru-перевод в скрейпе есть только у 62 из 880 карт; DE русских текстов карт не даёт. {backend/prisma/seed-scraped.ts:296-297;backend/prisma/seed-scraped.ts:341-342;backend/prisma/fix-roster-ru.ts:1-12}
[F14](medium) DE хранит различающиеся копии отдельными архетипами (Into the Woods A/B/C) и enum символов корзины BasketItems; у нас символы — эмодзи в имени, 3 копии в одной строке; обработки корзины Little Red в backend нет. {DuelEngine-transfer/test-targets/unmatched-data/cards-full.json:21374;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/enums/BasketItems.cs;scraped-data/api/heroes/little-red.json}
[F15](medium) Стартовая рука 5 и лимит руки 7 у нас совпадают с DE (StartingDrawAmount по умолчанию 5; лимит в DE как константа не найден). {backend/src/games/services/game-initialization.service.ts:41;backend/src/games/game-state.service.ts:1097;DuelEngine-transfer/test-targets/unmatched-data/heroes-stats.json:27}

--- open
Живую БД (:5433) я не читал, потому что Docker остановлен: остались ли в ней 'Allice', 'The Potter' и значение 2 у What Big Eyes, или их уже поправили вручную через админку? Сейчас это подтверждено только скрейпом и docs/backend-api/09-cards-and-effects.md.
What Big Eyes You Have = 3 подтверждают DE и UmDb. Стоит ещё сверить со сканом карты (imageUrl в БД / scraped-data/images/decks).
Corkscrew Finger Jab (у нас и в UmDb) против Corkscrew Finger Fan (DE): это опечатка или переименование в DE, или наша ошибка?
Bewilderment: у нас и в UmDb 'Prevent all damage', в DE 'Prevent all combat damage'. Какую формулировку реализует наш движок?
Как движок трактует boostValue = null у Voyage-карт: как 0 или как карту, которую нельзя бустить?
Стартовые клетки, двери и тайные проходы досок из ISIL (DuelSpaceDefinition.StartPlayer, DuelLineDefinition.IsSecretPassage) не сверены; сверены только клетки, связи и зоны.
Нужна ли тест-сверка числовых данных DE в репозитории? Это вопрос IP: предлагается хранить только числа, без текстов, и, возможно, вне репозитория.