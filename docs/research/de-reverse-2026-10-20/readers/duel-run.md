## duel-run: DuelEngine, проверенный запуском

Ниже `$DR` = `C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unmached-unmached/2b6a7e70-a9a9-4f0e-bd48-9f26a5894d1b/scratchpad/duel-run`, а `$DE` = `C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine`. В репозитории и в DuelEngine-transfer ничего не менял. Все исходники скопированы в `$DR/harness/src`.

### 1. Что собралось
- Консольный проект `$DR/harness/DuelHarness.csproj`: net10.0, LangVersion 9, ImplicitUsings выключены. В него вошли копии Core (13 файлов), AI (3), Content (2) и Networking (5). Сборка прошла с 0 ошибок и 0 предупреждений за ~4 с.
- От Unity вне Runtime/Editor зависит только `Content/HeroJson.cs`: он берёт `UnityEngine.JsonUtility` (`$DE/Content/HeroJson.cs:4,73`). Я заменил его заглушкой на System.Text.Json в 20 строк: `$DR/harness/stubs/UnityEngineStub.cs`. Core, AI и Networking собираются без Unity, так что заявление README о «чистом C#» подтвердилось.
- Загрузились все 16 героев: 14 «real» и 2 собственных (ashka, twin_wraiths).
- Harness: `$DR/harness/Program.cs`. Режимы: all, det, detrev, scan, trace, tour, vs.

### 2. Прогоны ИИ против ИИ (`$DR/out/harness-all.log`, `$DR/out/summary.txt`)
В основном прогоне 1360 матчей с проверкой инвариантов после каждого шага: HP в диапазоне, сохранение и владелец каждой карты (deck+hand+discard), согласованность Winner и GameOver.

| Пакет | Матчей | Исключений | Не доиграно (5000 шагов) | Нарушений инвариантов | мс/матч, ср./p95 |
|---|---|---|---|---|---|
| L2 vs L2, все пары из 16 героев | 240 | 0 | 2 | 0 | 2.70 / 4.31 |
| L2 vs Random и обратная рассадка | 64 | 0 | 0 | 0 | ~0.9 |
| L2 vs Valuation | 32 | 0 | 1 | 0 | 1.72 |
| L0 vs L1 | 32 | 0 | 0 | 0 | 0.14 |
| Valuation vs Valuation | 32 | 0 | 0 | 0 | 0.12 |
| Random vs Random, фазз, 4 сида на пару | 960 | 0 | 5 | **6** | 0.21 / 0.33 |

Дополнительные прогоны:
- `scan`: ещё 3840 матчей Random и 960 матчей L2 vs L2.
- `vs`: 6×364 матча на 14 настоящих героях, обе рассадки.
- `tour`: 182 матча.

Всего около 8,5 тыс. разных матчей, **ни одного исключения**. Карты не терялись, не дублировались и не переходили к другому игроку.

Сила уровней ИИ, 14 настоящих героев, обе рассадки (`$DR/out/vs-summary.txt`):

| Пара | Счёт |
|---|---|
| L2 vs L0 | 360:4 |
| L2 vs L1 | 364:0 |
| L2 vs Random | 361:3 |
| L2 vs Valuation | 364:0 |
| L1 vs L0 | 179:185 — L0 и L1 по силе не различаются |
| Valuation vs Random | 277:87 |

README обещал «L2 vs Random 19/20, L2 vs L0 16/20». На деле L2 сильнее заявленного, а L0 и L1 — один и тот же уровень.

В L2 vs L2 первый ход выигрывает 141 из 238 решённых матчей (59%). Сильнее всех Bigfoot, Medusa и RobinHood (по 24W-6L), слабее всех Sinbad (5W-24L).

### 3. Детерминизм — да
- **В одном процессе.** 20 фиксированных конфигураций (разные герои, ИИ и сиды) сыграны до и после 1360 других матчей, а также с заново загруженными HeroDef. Совпали 20/20 по SHA256 полного состояния, ActionLog и MatchReport.Build.
- **Между процессами.** Четыре отдельных запуска, в том числе в обратном порядке, дали одинаковые файлы (md5 `10fe18ed…`): `$DR/out/det-hashes-*.txt`.
- **Между рантаймами.** Я повторил `Editor/TournamentTests` (seedBase 50000, L2 vs L2, 182 матча) на .NET 10. Совпали все 14 строк W/L, avgTurns 7.2 и avgExchanges 109.5, а образец телеметрии совпал побайтно с `duel-engine/docs/telemetry-sample.json` (`$DR/out/harness-tour.log`). Значит, результаты Unity Mono и CoreCLR одинаковы. Опора — `SeededRng` поверх `System.Random(seed)` (`$DE/Core/IRng.cs:15-27`).
- **Ограничение.** Состояние RNG — закрытый внутри `System.Random` объект, его нельзя сохранить посреди партии. Возобновить партию можно только повтором с начала. `StateClone` для ИИ создаёт новый RNG (`$DE/Core/StateClone.cs:16-25`).

### 4. Повтор партии
- **(c1) По (герои, seed, список SelectionResponse): 120/120 совпадений** состояния и журнала. Партию воспроизводит именно этот журнал ответов.
- **(c2) По (seed, ActionLog): не работает.** Префикс NewMatch совпадает 120/120.
  - Если применить все записи: полное состояние совпало 0/120, «материальное» (HP, зоны, колоды) — 27/120, RulesException в 56 матчах (например, «Эта карта не может защищать»).
  - Если пропустить `AbilityEffectAction`: 1/120, 46/120 и 17 исключений.
- Причин две:
  - `Engine.Submit` сам меняет Phase и Pending*-поля, минуя действия (`$DE/Core/Engine.cs:395-470`).
  - Эффекты способностей применяются внутри родительского действия и ещё раз пишутся в журнал обёрткой (`$DE/Core/Events.cs:93-96`, `$DE/Core/Engine.cs:114-127`).
- Поэтому принцип README «Партия = (seed, список действий)» и «любое изменение — через IGameAction» на практике не выполняется. ActionLog годится как протокол для отображения, но не как запись для воспроизведения.

### 5. Найденные баги

**Б1 (серьёзный). Победа затирается, матч продолжается с мёртвым героем или достаётся не тому игроку.**
- Где видно: `$DR/out/trace-gameover-bug-dracula-160245.log`, `$DR/out/harness-scan-random4.log`, `harness-scan-random16.log`, `harness-scan-l2x4.log`.
- Механизм:
  1. В `GetSelection` на PostSchemePhase или StartOfTurnEffectsPhase движок доигрывает очередь отложенных эффектов (`$DE/Core/Engine.cs:148-175`).
  2. Задача `DamageAllAdjacentAtAnchor` применяет урон без выбора игрока (`Engine.cs:725-743`). Его дают TPAndDamageSchemeAbility и RaveningSeductionAbility.
  3. Урон убивает героя, `DamageFighterAction` ставит Winner и GameOver.
  4. `PendingEffectSelection` проверяет GameOver только в начале итерации (`Engine.cs:570`). Если очередь опустела, она возвращает null.
  5. Ветка else в `Engine.cs:168-172` ставит SchemePhase, а та тут же переходит в MainPhase (`Engine.cs:236-239`).
- В трассе: шаг 270, переход PostSchemePhase → MainPhase. HP Beowulf 2 → 0, Winner=P0, но игроку выдан ChooseMainOptionRequest.
- Частота и исходы:

| Прогон | Аномалий | Застряли до лимита | Позже объявлен другой победитель |
|---|---|---|---|
| Random, 960 матчей | 6 (0.63%) | 5 | 1 |
| Random, 3840 матчей | 15 (0.39%) | 12 | 3 |
| L2 vs L2, 960 матчей | 1 (0.10%) | 0 | 1 (Dracula победил на шаге 67, а на шаге 1597 победителем объявлен Invisible Man) |

- Собственные тесты DuelEngine этого не ловят: они гоняют только L2, а детерминизм турнира проверяют лишь по ActionLog.Count и Winner (`Assets/Editor/TournamentTests.cs:105-109`).

**Б2. Бесконечные партии.**
- Урона от истощения нет, сброс замешивается обратно в колоду (`$DE/Core/Actions.cs:33-41`). У партии нет «часов».
- 3 матча с L2 упёрлись в 5000 шагов, все с самодельным героем Ashka (колода 10 карт). Пример: Jekyll vs Ashka, 788 ходов и **0 атак** (`$DR/out/trace-stalemate-jekyll-ashka-100103.log`). На 14 настоящих героях в 2184 матчах vs ни одной ничьей.

**Б3. `docs/tournament-report.json` — невалидный JSON.**
- Внутри `"avgTurns":7,2` и `"winRate":0,846`. Причина — `ToString("0.0")` под ru-культурой в TournamentTests.

**Б4. ИИ L2 видит скрытую информацию.**
- `StateClone` копирует руку и порядок колоды противника. `Evaluate` учитывает содержимое руки врага (`$DE/AI/ScoringPlayer.cs:288-295`). Доигрывание отвечает за противника его настоящей рукой (`ScoringPlayer.cs:213-233`). Оценка соперника — «на открытых картах».

### 6. Производительность
- Решение L2 в среднем 22.8 мкс: 733 решения за 17 мс.
- L2 vs L2: в среднем 2.7 мс на матч (p95 4.3 мс; максимум 91 мс — это 788-ходовая ничья).
- Турнир из 182 матчей: 473 мс на .NET 10 против 2653–2986 мс в Unity Editor (`sprint6-tournament.log`, `docs/tournament-report.json`). Это примерно в 6 раз быстрее.
- Весь основной прогон (1360 матчей, проверки повтора и детерминизма) занял около 1.8 с.

### 7. Покрытие способностей
- В колодах 156 имён способностей. В `AbilityCatalog` зарегистрировано 149 обработчиков.
- 12 имён объявлены, но без обработчика — это ровно список README: Beastform, BigEars, CloseAndClinch, DoMyBidding, ForeverHyde, GoldenDrinkingHorn, LadyLake, LookingGlass, Lurking, NeverLeaveThePath, Prophecy, RestlessSpirits (`$DR/out/declared-not-registered.txt`). Незарегистрированные имена движок молча игнорирует (`Events.cs`, комментарий к AbilityCatalog).
- В журнале обёрткой AbilityEffectAction хотя бы раз отметились 108 имён.
- Ещё 37 зарегистрированных не появились ни разу. Многие из них (Cancel, модификаторы значения) меняют CombatState без обёртки, поэтому «не сработала» из этого не следует (`$DR/out/abilities-*.txt`).

### 8. Пространственная модель (важно для сравнения с нашими картами-графами)
- Доска — линейная цепочка из 8 «зон» с соседством ±1 (`$DE/Core/Board.cs:8-40`, `Engine.cs:14`). Дальний бой бьёт по «зоне-группе» zone/3.
- В одной зоне может стоять несколько бойцов: на старте все сайдкики в одной зоне (`Engine.cs:24-25`), в прогонах я видел до 7 живых бойцов в одной зоне.
- Ни с клетками, ни с зонами реальных карт Unmatched (Marmoreal, Sarpedon) это не совпадает.

### 9. Расхождения с правилами, найденные попутно (проверил по файлам оригинала, глубину оставляю агенту по правилам)
- **Истощение в оригинале есть.**
  - `test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt`: стр. 1547 — строка "exhausted_draw", 1552 — `typeof(duel.canis.actions.Damage)`, 1670 — "log.exhaust".
  - В DiffableCs `actions/Draw.cs:54` есть поле `<exhaustedFighters>`.
  - Локализация (`unmatched-data/localization.txt:4428,4804,4814`) говорит о 2 уроне каждому бойцу за каждую карту, которую нельзя добрать.
  - `duel-engine/docs/rules-diff.md:81` утверждает, что в этом файле вызовов Damage нет, — это неверно.
- **Добор 2 карт в начале хода** (`$DE/Core/Actions.cs:587`). В `BeginPlayerTurn_NestedType__InitializeTurn_d__5.txt` нет ни одной ссылки на тип Draw, только атрибуты и FogToken. Уверенность средняя.
- **Схема сделана бесплатной (1 за ход).** При этом их же rules-diff.md:95 указывает, что в оригинале `ActionTypes` содержит Scheme, то есть схема — действие.

### 10. Exe (`$DR/exe-start.png`, `$DR/player.log`, скрипт `$DR/run-exe.ps1`)
- **Запуск.** Аргументы `-screen-fullscreen 0 -screen-width 1280 -screen-height 720 -logFile …`, PID 2676. Окно появилось через ~1 с: 1296×759, заголовок «UnityProject» (имя продукта не задано). Через 10 с: CPU 1.2 с, рабочий набор 376 МБ. Скриншот снят через PrintWindow только этого окна, затем процесс остановлен по PID (exited=True). Мышь и клавиатуру не трогал.
- **player.log.** 36 строк, исключений нет. Единственное — дважды «d3d12: failed to query info queue interface (0x80004002)», это безвредно. Unity 6000.6.6f1, DX12, RTX 4090.
- **Что на экране.** Тёмно-серый фон и заголовок «Выберите героя для игрока I, затем для игрока II» с метками «I: —» и «II: —». Кнопок героев **только две**: «Ashka, the Emberblade (16 HP, ход 2)» и «The Twin Wraiths (10 HP, ход 2, +2 союзн.)». Внизу кнопка «ИГРАТЬ». Это стандартный процедурный UI Unity без арта.
- **Почему не 16 героев, как обещает HANDOFF.** `$DE/Runtime/MatchSetup.cs:22-23` ищет JSON в `Application.dataPath/DuelEngine/Content/Heroes/real`. Такая папка есть только в редакторе. В `Builds/DuelEngineWin/DuelEngine_Data` её нет: из JSON там только RuntimeInitializeOnLoads и ScriptingAssemblies. Поэтому проверка `Directory.Exists` молча возвращает false.
- **Другие особенности билда:**
  - сид всегда 42 (`StartupFlow.cs:102`), так что каждая партия раздаётся одинаково;
  - отдельного бота-соперника нет: кнопка «Ход за бота» отвечает RandomPlayer'ом на текущий запрос (`HumanShell.cs:35,120-121`), ИИ L2 в exe не подключён;
  - бэкенд скриптов — Mono (папка MonoBleedingEdge, `Managed/Assembly-CSharp.dll`, 195 КБ, 2026-10-20 08:43);
  - их собственная проверка exe смотрит только, что файл существует (`Assets/Editor/BuildGame.cs:55-61`).

### 11. Итог для вердикта (только наблюдения запуска)
**Стоит перенять как приёмы:**
- единый протокол «запрос → ответ» плюс seed: дешёвый headless-прогон и полное воспроизведение партии по журналу ответов;
- самоигру и фазз-прогоны со случайными ходами и проверкой инвариантов. Такой фазз за секунды нашёл баг Б1, который их 25 зелёных маркеров пропустили.

**Не стоит переносить:**
- 8-зонную линейную доску;
- модель «журнал действий = запись партии»: она не работает (c2);
- ИИ, подглядывающий в скрытые карты;
- Unity-оболочку;
- правила без истощения и с добором 2 в начале хода.

Мой прогон этого не проверял: сетевой сервер (MatchServer/LobbyServer) не запускал; насколько наш бэкенд детерминирован и воспроизводим, не сравнивал.

Процессы: DuelEngine.exe (PID 2676) завершён. Сервер компиляции VBCSCompiler (PID 41804), который запустил мой `dotnet build`, тоже остановлен. Его родитель уже вышел.

--- keyFacts
[F1](high) Core/AI/Content/Networking собираются в .NET 10 (C# 9) с 0 ошибок и 0 предупреждений. Единственная связь с Unity вне Runtime/Editor — JsonUtility в HeroJson.cs, её заменяет заглушка на System.Text.Json в 20 строк. {$DR/harness/DuelHarness.csproj; $DR/harness/stubs/UnityEngineStub.cs; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Content/HeroJson.cs:4,73}
[F2](high) Около 8,5 тыс. матчей ИИ против ИИ (L2/L1/L0/Valuation/Random, 16 героев) — 0 исключений, карты не терялись, не дублировались и не меняли владельца. {$DR/out/harness-all.log; $DR/out/summary.txt; $DR/out/vs-summary.txt; $DR/out/harness-scan-random16.log; $DR/out/harness-scan-l2x4.log}
[F3](high) Детерминизм подтверждён: 20/20 совпадений в одном процессе после 1360 других матчей и со свежими HeroDef; 4 отдельных процесса дали одинаковые хеши; турнир Unity (182 матча, seedBase 50000) на .NET 10 повторился точно — W/L, avgTurns 7.2, avgExchanges 109.5 и побайтно образец телеметрии. {$DR/out/det-hashes-*.txt; $DR/out/harness-tour.log; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/duel-engine/docs/telemetry-sample.json; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/duel-engine/docs/tournament-report.json}
[F4](high) Повтор по (seed, список SelectionResponse) работает 120/120. Повтор по (seed, ActionLog) не работает: полное состояние совпадает 0/120 (1/120 без AbilityEffectAction), в 56/120 RulesException. Причины: Submit меняет Phase и Pending* в обход действий, а эффекты способностей применяются внутри действия и ещё раз пишутся в журнал. {$DR/out/harness-all.log (строки c1/c2); $DE/Core/Engine.cs:395-470; $DE/Core/Engine.cs:114-127; $DE/Core/Events.cs:93-96}
[F5](high) Баг: урон из очереди отложенных эффектов на PostSchemePhase (TPAndDamageScheme/RaveningSeduction через DamageAllAdjacentAtAnchor) убивает героя, но ветка else в GetSelection перезаписывает GameOver на SchemePhase→MainPhase. Матч идёт дальше с мёртвым героем: доходит до лимита шагов или позже объявляется ДРУГОЙ победитель. Частота: 6/960 и 15/3840 в Random, 1/960 в L2 vs L2 (там итоговый победитель неверный). {$DR/out/trace-gameover-bug-dracula-160245.log; $DR/out/harness-scan-random4.log; $DR/out/harness-scan-random16.log; $DR/out/harness-scan-l2x4.log; $DE/Core/Engine.cs:148-175; $DE/Core/Engine.cs:566-570; $DE/Core/Engine.cs:725-743; $DE/Core/Engine.cs:229-239}
[F6](high) Производительность на .NET 10: решение L2 около 22.8 мкс, матч L2 vs L2 около 2.7 мс в среднем (p95 4.3 мс); турнир из 182 матчей за 473 мс против 2653–2986 мс в Unity Editor. {$DR/out/harness-all.log (строка perf); $DR/out/summary.txt; $DR/out/harness-tour.log; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/duel-engine/sprint6-tournament.log}
[F7](high) Сила ИИ на 14 настоящих героях, обе рассадки: L2 выигрывает 360/364 у L0, 364/364 у L1, 361/364 у Random, 364/364 у Valuation; L1 против L0 — 179:185 (разницы нет); Valuation против Random — 277:87. В L2 vs L2 первый ход выигрывает 59%. {$DR/out/vs-summary.txt; $DR/out/harness-all.log}
[F8](high) ИИ L2 играет на открытых картах: клон копирует руку и колоду противника, Evaluate учитывает содержимое руки врага, доигрывание идёт его настоящей рукой. {$DE/AI/ScoringPlayer.cs:169; $DE/AI/ScoringPlayer.cs:213-233; $DE/AI/ScoringPlayer.cs:288-295; $DE/Core/StateClone.cs:16-60}
[F9](high) Урона от истощения нет, а сброс замешивается в колоду, поэтому возможны бесконечные партии: 3 матча с L2 (все с самодельной Ashka) дошли до 5000 шагов, например Jekyll vs Ashka — 788 ходов и 0 атак. {$DR/out/trace-stalemate-jekyll-ashka-100103.log; $DR/out/harness-all.log (раздел Unfinished); $DE/Core/Actions.cs:33-41}
[F10](high) В оригинале DE истощение есть: Draw.execute ссылается на typeof Damage, строку 'exhausted_draw' и 'log.exhaust'; локализация говорит о 2 уроне каждому бойцу. Утверждение rules-diff.md §7 «вызовов Damage нет» неверно. {C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt:1547,1552,1670; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/actions/Draw.cs:54; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4428,4804,4814; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/duel-engine/docs/rules-diff.md:81}
[F11](medium) DuelEngine добирает 2 карты в начале хода. В InitializeTurn оригинала нет ни одной ссылки на тип Draw. {$DE/Core/Actions.cs:587; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/BeginPlayerTurn_NestedType__InitializeTurn_d__5.txt}
[F12](high) Доска — линейная цепочка из 8 зон с соседством ±1, в одной зоне стоит несколько бойцов (в прогонах до 7 живых). С клетками и зонами реальных карт Marmoreal/Sarpedon это не совпадает. {$DE/Core/Board.cs:8-40; $DE/Core/Engine.cs:14,24-25; $DR/out/summary.txt (maxZoneOccupancy=7)}
[F13](high) Exe запускается без исключений: окно 1296×759 появилось через ~1 с, заголовок 'UnityProject', рабочий набор 376 МБ. В player.log только безвредная строка d3d12 про info queue. Процесс остановлен по PID. {$DR/player.log; $DR/exe-start.png; $DR/run-exe.ps1}
[F14](high) В exe на экране выбора только 2 героя (Ashka и Twin Wraiths), а не 16: MatchSetup ищет JSON в Application.dataPath/DuelEngine/Content/Heroes/real, а в билде этой папки нет. Кроме того, сид всегда 42, а «бот» — только кнопка случайного хода (RandomPlayer), L2 в exe не подключён. {$DR/exe-start.png; $DE/Runtime/MatchSetup.cs:22-23; $DE/Runtime/StartupFlow.cs:102; $DE/Runtime/HumanShell.cs:35,120-121; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/duel-engine/UnityProject/Builds/DuelEngineWin/DuelEngine_Data}
[F15](high) Способности: в колодах 156 имён, обработчиков 149. 12 без обработчика — ровно список README (Beastform, BigEars, CloseAndClinch, DoMyBidding, ForeverHyde, GoldenDrinkingHorn, LadyLake, LookingGlass, Lurking, NeverLeaveThePath, Prophecy, RestlessSpirits); такие имена движок молча игнорирует. {$DR/out/declared-not-registered.txt; $DR/out/registered.txt; $DR/out/declared.txt; $DE/Core/Events.cs:121}
[F16](high) docs/tournament-report.json — невалидный JSON: десятичная запятая ('avgTurns':7,2) из-за культурозависимого ToString('0.0'). {C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/duel-engine/docs/tournament-report.json:1; C:/Users/ren/WebstormProjects/unmached/unmached/DuelEngine-transfer/duel-engine/UnityProject/Assets/Editor/TournamentTests.cs}
[F17](high) Состояние RNG (System.Random внутри SeededRng) нельзя сохранить посреди партии: возобновление возможно только повтором с начала. Выдача одинакова в Unity Mono и в CoreCLR. {$DE/Core/IRng.cs:15-27; $DR/out/harness-tour.log}

--- open
Сетевой путь (MatchServer/LobbyServer по loopback) я не запускал. Утверждение, что сетевой матч побитово совпадает с локальным, не проверено.
UI exe после выбора героев (сам матч, BoardView, экран итога) не проверен: кликать по условиям задачи было нельзя.
Добор 2 в начале хода и бесплатная схема (1 за ход) против правил DE/настолки: нужен разбор агента по правилам (ISIL PlayerTurnScript, ActionTypes); здесь уверенность средняя.
Нет ли у нашего движка (backend/src/game-engine) аналогов Б1: перезаписи GameOver в очередях эффектов. Стоит прогнать такой же фазз со случайными ходами и инвариантами на нашем движке — не делал, Docker остановлен.
Что делает DE после истощения при пустой колоде: замешивает сброс или нет (в ISIL Draw есть ShuffleWithLogs, стр. 1407, но к чему он относится, не разбирал).