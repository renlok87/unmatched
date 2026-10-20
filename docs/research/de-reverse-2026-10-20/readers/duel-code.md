## Итог (часть duel-code)

DuelEngine — прототип на Unity/C#, который другой агент написал примерно за сутки: Unity-проект создан 2026-10-19 09:27 (`duel-engine/unity-create.log`), последний прогон 2026-10-20 08:42 (`sprint6-fullsuite.log`). Вся кодовая база Assets — около 19 тыс. строк C#, из них ядро Core около 7 тыс. Каркас аккуратный: чистое ядро без UnityEngine, протокол «запрос → ответ», ГПСЧ с сидом, клон состояния для ИИ. Но **модель игры игрушечная, и в базовых правилах есть грубые ошибки**: ряд правил прямо противоречит локализации самого оригинала. Наш бэкенд по правилам и данным уже заметно точнее. **Переводить проект на этот движок не нужно.** Брать стоит только 3–4 идеи, а не код: сид-ГПСЧ в состоянии, ИИ через симуляцию с общими случайными числами, self-play турниры с телеметрией, и как справку — веса `DuelAIConstants` и привязку карт к классам способностей.

---

## 1. Архитектура: что заявлено и что на деле

**Хорошо:**
- Ядро `Assets/DuelEngine/Core` не ссылается на UnityEngine. UnityEngine есть только в `Content/HeroJson.cs:4` (JsonUtility). Изоляция держится на договорённости: файлов `.asmdef` в проекте нет.
- Протокол Selection (`Core/Selection.cs`): движок выдаёт типизированный запрос со списком допустимых вариантов (`HandIndices`, `Targets`, `Zones`, `Options`). Человек, ИИ и сеть отвечают одинаково. Сервер проверяет ответ одним правилом: значение должно входить в список вариантов (`Networking/MatchServer.cs:534-636`, `RequireHand/RequireTarget/RequireZone`). Тот же перечень вариантов использует ИИ (`AI/ScoringPlayer.cs:376`, `EnumerateCandidates`). Это чистый приём.
- Детерминизм: `IRng`/`SeededRng` хранится в `GameState.Rng` (`Core/IRng.cs`), тасовка Фишера–Йетса.
- Отложенные эффекты: очередь `PendingEffects` (объекты `PendingAbilityTask`), их доигрывают в фазах `PostCombatPhase/PostSchemePhase` (`Engine.cs:148-176`).

**Заявления расходятся с кодом:**
- «Партия = (seed, список действий)» не реализовано. Функции replay по журналу нет. «Детерминизм» в тестах — это повторный прогон всей партии с теми же сидами и сравнение счётчиков (`Editor/SmokeTest.cs:31-35`, `Editor/TournamentTests.cs:105-108`).
- Журнал неполный. Вложенные действия, вызванные через `new X().Apply(s)`, в него не попадают: добор 2 в начале хода (`Actions.cs:587`), добор при манёвре (`Actions.cs:645`), урон внутри резолва. Переходы фаз и поля `PendingAttack*` `Engine.Submit` меняет напрямую, без действий (`Engine.cs:399-470`).
- `GetSelection` — запрос с побочными эффектами: он сам применяет действия и прокручивает фазы (`Engine.cs:133-393`).
- `MatchReport.cs` (1063 строки) — отдельная «теневая» копия правил для восстановления хода партии из журнала. Это второй источник правды. Сам файл признаёт, что окна Immediate/During по журналу не воспроизвести (`MatchReport.cs:7-31`).
- `StateClone.cs` копирует поля вручную. Каждое новое поле состояния надо не забыть добавить сюда: в комментарии упомянуты прошлые баги с `IsRanged` (`StateClone.cs:29-30`).

## 2. Насколько модель упрощена против реальной игры

**Доска.** `Board` — линия из 8 клеток, соседство ±1, `Distance = |a−b|` (`Core/Board.cs:19-29`, `Engine.cs:14`). «Зоны» для дальнего боя жёстко заданы как `zone / 3` (`Board.cs:38`), хотя в `docs/ranged-spec.md` R.3 сам агент предлагал сделать их данными. В клетке может стоять сколько угодно бойцов: все сайдкики стартуют в одной клетке (`Engine.cs:101`). Занятость при движении не проверяется: манёвр учитывает только дистанцию (`Engine.cs:364`). Проход сквозь врагов свободен (признано в `Events.cs:460`). Стартовые клетки фиксированы (`Engine.cs:26-27`). Дверей, клеток в нескольких зонах и потайных ходов нет, хотя в `ranged-spec.md` §1–2 они описаны по оригиналу. Наш `backend/src/game-engine/engine/board-topology.ts:1-25` и `models/board.model.ts` (zones[], doors, fog) работают с реальным графом карт Marmoreal/Sarpedon.

**Правила, противоречащие локализации оригинала** (`test-targets/unmatched-data/localization.txt`):
1. **Схема — это действие.** В оригинале выбор хода — манёвр, атака или схема (`localization.txt:4322`), туториал называет схему третьим видом действия (4752, 4763). В DuelEngine схема бесплатна, одна за ход, до или после действия (`Engine.cs:236`, `rules-diff.md:95`). У нас это сделано верно: `game-state.model.ts:460`.
2. **Бесплатные бусты в бою.** В DuelEngine обе стороны могут бустить любым числом любых карт (`Engine.cs:1447-1466`, фазы `DefenderBoostPhase/AttackerBoostPhase`). В оригинале буст — это манёвр (`localization.txt:4772`) или эффект конкретной карты (`prompt.boostattack` 4169, `prompt.conviction` 4200). Агент принял порядок окон `DefenderDuring<AttackerDuring` за «порядок бустов» (`rules-diff.md:18`). У нас буст в бою появляется только как `BOOST_CHOICE` от эффекта карты (`game-action-executor.service.ts:611-616`).
3. **Истощение убрано.** DuelEngine пишет, что урона нет, и замешивает сброс обратно в колоду (`Actions.cs:30-41`, `rules-diff.md:81` с вердиктом «самодеятельный 2 урона убран»). Оригинал прямо описывает 2 урона каждому бойцу за каждый недобор (`localization.txt:4804, 4814`, `log.exhaust` 4428). Наш `deck-management.service.ts:75-83` делает правильно.
4. **Добор 2 в начале хода** (`Actions.cs:587`). Туториал называет добор при манёвре главным источником карт (`localization.txt:4725`), в настольных правилах добора в начале хода нет. Ссылку агента на ISIL (`BeginPlayerTurn…InitializeTurn_d__5`, ISIL 198) я не перепроверял: вызовы там по адресам.
5. **Карту может сыграть любой боец.** Ограничения по персонажу нет: `CardDef` (`Cards.cs:30-58`), `AttackCardPhase` (`Engine.cs:301-309`). Оригинал его описывает (`localization.txt:4730`). В `cards-full.json` такого поля нет, то есть это дыра в извлечении данных. У нас есть `Card.bannerName` (`prisma/schema.prisma:463`) и `bannerAllows` (`game-rules.validator.ts:603`).
6. **Буст манёвра отсутствует** (`rules-diff.md:63`, открыт).
7. **Способности героев почти не реализованы.** Есть только Rage, Fog и неотменяемость Шерлока. Размер Алисы переключается флагом `IsBig`, но в бою не используется (grep `IsBig` в Core: только `Actions.cs:712` и `MatchReport`). Бонусы +2/+1 из `localization.txt:4836` не применяются. Способностей Медузы, Дракулы (4859), корзинки Красной Шапочки и других нет.
8. **Порядок эффектов.** В окнах Immediate и AfterCombat первой идёт карта атаки, потом защиты (`Events.cs:1848-1863`, `1901-1918`). В оригинале при одновременных эффектах первым ходит защитник (`localization.txt:4738`; `CombatSteps` в `rules-diff.md:17`). У нас защитник первый: `card-effect-executor.service.ts:180`, `game-action-executor.service.ts:2689`.
9. Необязательные «may» решаются автоматически, «any fighter» сужено до врагов (`Events.cs:155, 395, 1216, 1414`).

**Найденный баг.** `Engine.CanReach` считает через `Board.Distance` без проверки `zone >= 0`. Невидимка после Vanish (`Zone=-1`, `Actions.cs:1209`) оказывается «смежным» с клеткой 0 и его можно атаковать (`Engine.cs:1523-1530`, `Board.cs:26-29`). Тесты это не ловят: soak идёт на синтетических героях.

Следствие ошибок в правилах: партии очень короткие. В турнире `avgTurns` = 7.2, причём `TurnNumber` считает ходы обоих игроков (`docs/tournament-report.json`, `Actions.cs` StartTurn). В образце телеметрии 11 бустов и 17 урона по герою за 5 ходов (`docs/telemetry-sample.json`). Поэтому винрейты турнира для баланса реальной игры ничего не значат.

## 3. Качество кода
- `Events.cs` — 2036 строк, 113 КБ. По сути это один `Dictionary<string, Action<GameEventContext>>` примерно из 150 лямбд (`"] = ctx =>"` — 150 вхождений), ключи — имена классов способностей оригинала. Большинство «семейств» относятся к одной карте (`docs/sprint2-family-freq.txt`: 156 семейств на 188 карт, почти все встречаются 1 раз). Это хардкод под каждую карту, а не каталог переиспользуемых блоков. DSL оригинала (`FromPhraseGrammar`, `DuelPropertiesPhrases`, упомянутые в `ranged-spec.md`) не воспроизведён.
- `PendingAbilityTask` (`GameState.cs:245-309`) — god-object с полями под отдельные карты, например `FollowUpMode` 0/1/2 (`GameState.cs:302`). `PendingAbilityKind` содержит около 20 видов, в `Engine.cs` 37 веток `case PendingAbilityKind` (`PendingEffectSelection` 566-1012, `ResolvePendingEffect` 1012-1427). Новый вид эффекта требует правок в enum, двух switch, `StateClone`, `MatchReport`, `NetMessages` и ИИ.
- Флаги конкретных героев лежат прямо в `Fighter`/`PlayerState`: `HydeForm`, `FogWalker`, `GainsRageWhenHit`, `Rage`, `StartedTurnOnFog` (`Entities.cs:27-33`, `GameState.cs:363-373`). Для 84 героев это не масштабируется.
- Бой хранит индексы карт в руке, поэтому понадобился костыль `CombatHandSync` (`Actions.cs:748`). Сам `rules-diff.md:21` рекомендует отдельную зону active pile.
- Глобальные статические реестры `AbilityCatalog.Map` и `EventWindows.EndOfTurnSubscribers` (`Events.cs:121-1459`, `1832`) общие для всех матчей процесса. Сейчас их меняют только тесты (`Editor/AbilityTests.cs:100-121`).

## 4. Тесты и логи
- Маркеры: 25 `_OK` есть в `sprint6-fullsuite.log` (SMOKE…FULLSUITE, полный список в keyFacts). Корневой `fullsuite.log` — старый (2026-10-19), в нём 14 маркеров, хотя HANDOFF ссылается именно на это имя. Исключений нет. В логе встречается `DrawLog_FAIL` (`sprint6-fullsuite.log:1265`) — это негативный тест, который прошёл, но имя ломает grep по `_FAIL`. Лицензионный шум Unity и `abort_threads` при выходе на результат не влияют.
- Самописный стенд на throw и маркерах в логе, без NUnit и Unity Test Framework (`Editor/AllTests.cs`, `FullSuite.cs`).
- Что проверяют на самом деле:
  - soak — 30 матчей случайных игроков только на двух синтетических героях с колодами по 10 карт (`SmokeTest.cs:22-50, 90-97`);
  - детерминизм — равенство счётчиков turns/steps/actions/winner, а не хеша состояния;
  - NET и RECONNECT — совпадение победителя (`NetworkTests.cs:20-63`, `NetReconnectTests.cs:235`). Слово «побитово» в README преувеличение;
  - «94% карт полным эффектом» — это лишь факт, что все имена способностей карты зарегистрированы в каталоге, причём карта без способностей засчитывается автоматически (`Sprint3AbilityTests.cs:53-80`). Правильность эффекта гейт не проверяет;
  - юнит-тесты способностей сверяют код с собственной трактовкой агента. Эталонных трасс из оригинала нет.
- `TOURNAMENT_OK` проходит, хотя `docs/tournament-report.json` — невалидный JSON: дробные числа записаны с запятой из-за культуры, `ToString("0.0")` без InvariantCulture (`TournamentTests.cs:145,156`). Python json.load падает.
- README расходится с логом: ИИ «60/60 vs Random» против `AI_OK: 30+25 из 60` (`sprint6-fullsuite.log:1748`), L2 «19/20, 16/20» против `20/20, 20/20` (строка 1143).

## 5. Телеметрия (`Core/Telemetry.cs`)
- Весь боевой урон записывается как урон по герою, даже если защищался сайдкик (строка 66).
- `BoostsPlayed` считается по стороне атаки или защиты, а не по игроку (строка 81).
- `CardsDrawn` не видит доборы хода и манёвра, потому что они вложенные (`Actions.cs:587, 645`). В образце у P1 ровно стартовые 5 карт.

Сама идея годится, реализация — нет.

## 6. Сеть
TCP на `IPAddress.Loopback` (`MatchServer.cs:129`, `LobbyServer.cs:84`), то есть работает только на одной машине. На каждый матч — свой поток с блокирующими сокетами и опросом через `Thread.Sleep`, и свой порт из пула. JSON сериализуется вручную (`NetMessages.cs:9-220`). Авторизации, хранения и TLS нет. В публичное состояние входят только бойцы и счётчики карт (`NetMessages.cs:605-680`), без сброса, фогов, ярости и фазы. Удачные мелочи — токен места для reconnect и grace-окно. Против нашего NestJS + GraphQL + Postgres + Redis + BullMQ переносить нечего.

## 7. ИИ
- `ScoringPlayer`: перебор легальных ответов → клон состояния → доигрывание детерминированной политикой `ValuationPlayer` до первого решения своего следующего хода → оценка весами. Для всех кандидатов одного решения клон берёт один сид (common random numbers) (`ScoringPlayer.cs:6-33, 127-232`). Сама схема хорошая.
- ИИ видит скрытую информацию: клон копирует руку и порядок колоды противника (`StateClone.cs:74-75`), оценка использует руку противника (`ScoringPlayer.cs:288, 294, 313`).
- Из 180 ключей `DuelAIConstants-2.json` используется около 5 (`ScoringPlayer.cs:97-102`), остальное — ad-hoc константы. Скорость 6–17 мс на матч объясняется доской из 8 клеток.
- Наш `game-engine/services/ai-decision.service.ts:10-17` — жадная эвристика без симуляции. Идея симуляции для нас ценна.

## 8. Контент
- 14 героев оригинала: числа (HP, ход, значения и бусты карт, копии, AttackType) взяты из реверса, имена нейтральные, тексты-заглушки (`generate_real_content.py`, `Content/Heroes/real/*.json`).
- 2 героя собственные (`ashka.json`, `twin_wraiths.json`).
- У нас около 84 героев и 880 карт с текстами и баннерами.

## 9. Что забрать (идеи и алгоритмы, не код)
1. **Сид-ГПСЧ в состоянии игры** — главный плюс, дёшево. У нас 5 вызовов `Math.random` (`deck-management.service.ts:33,192`, `card-effect-executor.service.ts:1383,1446`, `games/services/game-initialization.service.ts:51`). Состояние ГПСЧ (сид и счётчик) можно хранить в `GameState.metadata`. Это даст воспроизводимые реплеи поверх уже существующего журнала `replay.service.ts`, фикстуры регрессий и симуляции.
2. **ИИ на симуляции** (перебор вариантов → клон → доигрывание → оценка, общие случайные числа). Делать честно: детерминизировать руку и колоду противника из неизвестных карт, не подглядывать. Наш движок без I/O и с иммутабельным состоянием (`readonly`), клон почти бесплатный.
3. **Self-play турниры с телеметрией** на реальных картах: винрейты, средняя длина партии, зависания. Сначала исправить три ошибки подсчёта из §5.
4. **Справочные данные:** `docs/original-ai/DuelAIConstants-*.json` (какие факторы учитывает ИИ оригинала) и привязка «карта → классы способностей» из `test-targets/unmatched-data/cards-full.json` (188 карт). По ней можно сверить классификацию нашего `effect-text-parser.ts`. Юридическую сторону стоит уточнить отдельно.
5. Приём «запрос несёт список легальных вариантов, а UI, ИИ и сервер работают с одним и тем же перечнем». У нас это частично есть: `PendingEffect.targetFighterIds`, `pending-targets.ts`.

**Не брать:** доску, правила хода, боя и добора, каталог лямбд под каждую карту, `PendingAbilityTask`, ручной `StateClone`, `MatchReport`, сеть, Unity-оболочку.

## 10. Переводить ли проект на DuelEngine? Нет
- Правила ядра ошибочны в базовых вещах (§2.1–2.8), доска — линия из 8 клеток, а у нас реальные графы карт.
- 14 героев против наших 84, причём способности героев почти не сделаны.
- Расширение под новую карту = новая лямбда плюс правки в 5–6 местах. Данных с именами классов для остальных 70 героев нет.
- Другой стек (C#/Unity) против нашего TS-бэкенда и клиента на UE5. Сеть без хранения и авторизации, только loopback.
- Тесты проверяют регистрацию и счётчики, а не соответствие оригиналу. У нас 101 spec-файл в `backend/src` (39 в game-engine) и правила, сверенные с DE.

--- keyFacts
[F1](high) Доска DuelEngine — линия из 8 клеток с соседством ±1 и Distance=|a-b|; зона дальнего боя жёстко задана как zone/3; вместо графа клеток с зонами, дверями и потайными ходами {DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Board.cs:19-38; Core/Engine.cs:14; docs/ranged-spec.md (раздел R.3)}
[F2](high) Занятость клеток не учитывается: все сайдкики стартуют в одной клетке, манёвр проверяет только дистанцию, проход сквозь врагов свободен, стартовые клетки фиксированы {Core/Engine.cs:26-27; Core/Engine.cs:101; Core/Engine.cs:364; Core/Events.cs:460}
[F3](high) Схема в DuelEngine бесплатная, одна за ход; в оригинале схема — одно из трёх действий хода {Core/Engine.cs:236; docs/rules-diff.md:95; test-targets/unmatched-data/localization.txt:4322; localization.txt:4752; localization.txt:4763}
[F4](high) В бою обе стороны могут бустить любым числом любых карт; в оригинале буст — это манёвр или эффект конкретной карты {Core/Engine.cs:1447-1466; Core/Actions.cs:364-420; localization.txt:4772; localization.txt:4169; localization.txt:4200; docs/rules-diff.md:18}
[F5](high) Истощения нет, сброс замешивается в колоду; оригинал описывает 2 урона каждому бойцу за недобор; наш бэкенд реализует истощение правильно {Core/Actions.cs:30-41; docs/rules-diff.md:81; localization.txt:4804; localization.txt:4814; backend/src/game-engine/services/deck-management.service.ts:75-83}
[F6](medium) В начале хода DuelEngine добирает 2 карты; это противоречит туториалу (добор при манёвре — главный источник карт) и настольным правилам; ссылку агента на ISIL не перепроверял {Core/Actions.cs:587; localization.txt:4725; docs/rules-diff.md:70}
[F7](high) Ограничения карты по персонажу нет: любой боец играет любую атаку; у нас есть Card.bannerName и bannerAllows {Core/Cards.cs:30-58; Core/Engine.cs:301-309; localization.txt:4730; backend/prisma/schema.prisma:463; backend/src/game-engine/validators/game-rules.validator.ts:603}
[F8](high) Размер Алисы (IsBig) переключается, но в бою не применяется; из способностей героев есть только Rage, Fog и неотменяемость Шерлока {Core/Actions.cs:712; Core/Actions.cs:422-555 (SideTotal без IsBig); localization.txt:4836; generate_real_content.py (hasRage/hasFog/uncancelableEffects)}
[F9](high) Порядок эффектов в окнах Immediate и AfterCombat: сначала карта атаки, потом защиты; в оригинале и у нас первым идёт защитник {Core/Events.cs:1848-1863; Core/Events.cs:1901-1918; localization.txt:4738; backend/src/game-engine/effects/card-effect-executor.service.ts:180; backend/src/game-engine/services/game-action-executor.service.ts:2689}
[F10](high) Баг: CanReach не проверяет zone>=0, поэтому Невидимку вне доски (Zone=-1) можно атаковать из клетки 0 {Core/Engine.cs:1523-1530; Core/Board.cs:26-29; Core/Actions.cs:1199-1210}
[F11](high) Events.cs (2036 строк) — словарь примерно из 150 лямбд с ключами-именами классов оригинала; большинство семейств относятся к одной карте; DSL оригинала не воспроизведён {Core/Events.cs:121-1459; docs/sprint2-family-freq.txt}
[F12](high) PendingAbilityTask — god-object с полями под отдельные карты; в Engine 37 веток case PendingAbilityKind; флаги героев (HydeForm, FogWalker, Rage) лежат в общих классах {Core/GameState.cs:119-309; Core/Engine.cs:566-1427; Core/Entities.cs:27-33}
[F13](high) Replay по журналу не реализован: вложенные действия и переходы фаз в журнал не пишутся; детерминизм проверяется повторным прогоном с сравнением счётчиков {Core/Actions.cs:587; Core/Actions.cs:645; Core/Engine.cs:395-470; Editor/SmokeTest.cs:31-35; Core/MatchReport.cs:7-31}
[F14](high) В sprint6-fullsuite.log есть все 25 маркеров _OK и нет исключений; корневой fullsuite.log старый, с 14 маркерами; DrawLog_FAIL — негативный тест, который прошёл {duel-engine/sprint6-fullsuite.log:325-1807; duel-engine/sprint6-fullsuite.log:1265; duel-engine/fullsuite.log}
[F15](high) Гейт «94% карт полным эффектом» проверяет только регистрацию имён способностей в каталоге; карта без способностей засчитывается автоматически {Editor/Sprint3AbilityTests.cs:53-80}
[F16](high) Сетевые тесты и тест reconnect сравнивают только победителя; soak идёт только на двух синтетических героях с колодами по 10 карт {Editor/NetworkTests.cs:20-63; Editor/NetReconnectTests.cs:235; Editor/SmokeTest.cs:22-50; Editor/SmokeTest.cs:90-97}
[F17](high) tournament-report.json — невалидный JSON (дробные числа с запятой из-за культуры), при этом TOURNAMENT_OK зелёный {duel-engine/docs/tournament-report.json; Editor/TournamentTests.cs:145; Editor/TournamentTests.cs:156}
[F18](high) Ошибки телеметрии: весь боевой урон записан как урон по герою, бусты считаются по стороне атаки/защиты, а не по игроку, доборы хода и манёвра не учитываются {Core/Telemetry.cs:66; Core/Telemetry.cs:81; Core/Actions.cs:587; Core/Actions.cs:645; docs/telemetry-sample.json}
[F19](high) ScoringPlayer: перебор вариантов → клон → доигрывание → оценка, общий сид на решение; при этом ИИ видит руку и колоду противника; из 180 констант DuelAIConstants-2 используется около 5 {AI/ScoringPlayer.cs:6-33; AI/ScoringPlayer.cs:97-102; AI/ScoringPlayer.cs:127-232; AI/ScoringPlayer.cs:288-313; Core/StateClone.cs:74-75; docs/original-ai/DuelAIConstants-2.json}
[F20](high) Сеть: TCP только на loopback, поток и порт на каждый матч, JSON вручную, нет авторизации и хранения, публичное состояние урезано {Networking/MatchServer.cs:129; Networking/LobbyServer.cs:84; Networking/NetMessages.cs:9-220; Networking/NetMessages.cs:605-680}
[F21](high) Наш движок использует Math.random в 5 местах, поэтому партии невоспроизводимы; seeded RNG — главная переносимая идея {backend/src/game-engine/services/deck-management.service.ts:33; deck-management.service.ts:192; backend/src/game-engine/effects/card-effect-executor.service.ts:1383; card-effect-executor.service.ts:1446; backend/src/games/services/game-initialization.service.ts:51}
[F22](medium) Наш ИИ — жадная эвристика без симуляции; движок без I/O и с readonly-состоянием, поэтому ИИ на симуляции переносим {backend/src/game-engine/services/ai-decision.service.ts:10-17; backend/src/game-engine/services/game-action-executor.service.ts:159-169}
[F23](high) Проект DuelEngine сделан примерно за сутки, около 19 тыс. строк C#; README расходится с логами по результатам ИИ {duel-engine/unity-create.log (2026-10-19 09:27); duel-engine/sprint6-fullsuite.log (2026-10-20 08:42; строки 1143, 1748); duel-engine/README.md}

--- open
Есть ли в DE добор 2 карт в начале хода: ссылку агента на ISIL BeginPlayerTurn.InitializeTurn (вызовы по адресам) я не проверял; локализация и настольные правила говорят, что такого добора нет.
Не смотрит ли наш ai-decision.service.ts на руку соперника — для сравнения честности ИИ это не проверялось.
Насколько дорого сделать клон и доигрывание нашего асинхронного GameActionExecutorService (56 await) для ИИ на симуляции — нужна отдельная оценка.
Юридическая допустимость использовать DuelAIConstants-*.json и cards-full.json (данные, извлечённые из бинарника оригинала) как справку для наших весов и проверки парсера.
Exe и UI-оболочку DuelEngine я не запускал: Player.log подтверждает только старт; играбельность билда не проверена.