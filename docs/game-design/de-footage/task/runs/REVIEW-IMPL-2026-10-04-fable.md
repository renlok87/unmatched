# Финальное адверсариальное ревью реализации набора DE (Fable, effort high, один проход, 2026-10-05)

Входы: [IMPL-2026-10-04.md](IMPL-2026-10-04.md), журналы A…G, [CLOSEOUT-2026-10-04.md](CLOSEOUT-2026-10-04.md),
`git log 3b68957f..c17a34fb` (107 коммитов), доказательства `evidence/DE-FOOTAGE/2026-10-04/`. Полномочия — IMPL
«Полномочия» (сообщение пользователя от 2026-10-04, «Спорное решение принимай сам»). Споры решены здесь, без вопросов
пользователю.

## Вердикт

**Принято с тремя исправлениями кода, сделанными этим ревью.** Блокеров нет. Реализация соответствует окончательным
решениям 01 (F-01…F-12, «Резолюция ревью» п. 1–9) и дельтам 02; принятый арт по умолчанию не тронут; статусы «done»
подтверждены гейтами и кадрами; чужие файлы не тронуты. Исправлено: бот VS_AI брал героя человека (баг спайка
DE-027), ворота экрана результата не ждали ещё играющую постановку боя (хвост DE-019), очистка `run-vs-ai-demo`
падала на пустом `ExecutablePath` (хвост DE-031).

## 1. Соответствие 01 и 02 (числа, умолчания, флаги отката)

Проверено по коду HEAD, не по журналам:

| Решение 01 | Код | Итог |
|---|---|---|
| F-01: CUE-008 600, CUE-010 800, `readHoldMs` 1000 только при тексте, строка 600 (400 + 200), пауза «счёт» 300, CUE-011 900 от контакта; удержания не масштабируются | `FS09CombatTiming` (`S09CombatStage.h:34-51`): те же числа; `ReadMs = bHasEffectText ? 1000 : 0`, `PauseMs` и удержания без `Scaled()`, выпад `1/SpeedMul`, «−N» 900 × speed | совпадает |
| F-03/F-04: заливка 450/550 в кадр контакта, «−N» +60, HP +80, контакт Notify → профиль → 292 | `HitTintMs/HitTintLethalMs/MinusDelayMs/HpDelayMs/DefaultContactMs`; `ContactSource` notify/profile/default | совпадает |
| F-02: 280 мс/ребро, подскок 0, наклон 10° за 60, разворот ≤ 50, доворот 120, Idle 150, ease выкл | `FS08MoveAnimParams` (`S08MoveAnim.h:44-50`); A/B-ключи `-S08MoveHop/-S08MoveLean/-S08MoveEase` только меняют параметры | совпадает |
| F-09: 450 → DeathSettle → неподвижно 300/0 → растворение 500/400 → +1000 экран; крест +1100 | `FS09DeathTiming` (`S09DeathStage.h:28-36`), `GoneAfterContactMs` 2125/1725; сердце `Dark` до приёмки глифа | совпадает |
| F-07: вспышка 1000, баннер 600 свой, ввод не блокирует | `FS09TurnCue::RingFlashMs 1000`, `BannerMs 600`; кольцо `ring=none` до AB-5 (ревью E; глиф — кандидат DE-012) | совпадает; кольцо — сознательное отложение до арт-приёмки, записано в 01 «Лист A/B» |
| F-10: прилёт 200 → удержание 1500 → эффект; своя 500; буст соперника ≥ 1000, фейд 250 | `FS09CardSlot` (`S09CardSlot.h:109-117`) | совпадает |
| F-05/SD-29: боковая панель, открытие ≤ 100, закрытие 150, «осталось» только у своей | `S09DeckPanel` (OpenMs 80 / 150), кадр F `s09-deck-own.jpg`: IN HAND / DISCARD / LEFT, у соперника только DISCARD + HAND n | совпадает |
| F-06/SD-24: заголовок по герою-победителю, без автозакрытия, кроссфейд 250, вход 500 | `S09ResultScreen` | совпадает |
| SD-42/43: лимит 7, тост один раз за партию | `FS09HandLimitHint::DefaultLimit 7`, `OnApplied` по `GameId` | совпадает |
| Настройки: громкости «Общая» 100 / «Окружение» 60, `-S08RuleHints` только перекрывает сохранённое | `FS08AudioSettings`, `ResolveRuleHints` | совпадает |

Флаги: `-S08HeartGlow`, `-S08TurnRingIcon=`, `-S08DissolveAsh`, `-S08MoveHop/Lean/Ease` — кандидаты, по умолчанию
выключены; `-S08HeroesLegacy`, `-S08GreyBoard` и прочие — откаты. Слой `glow` в `resource-hp-full` скрыт в HUD
(`S08TurnPortraitWidget.cpp:147`), хотя записан в `icon-motion.json` — HUD по умолчанию играет damage без ореола, как
решено в ревью A04. `cue-table.json`: CUE-008 600 без клипа, CUE-010 800, CUE-011 900 (`clip: present`), CUE-013 950,
CUE-015 600, CUE-016 1500 — `validate-table PASS cues 18`.

**Спорное, решено:** `-S08MovePlates` (MS-T-08) остаётся opt-in, хотя все живые кадры приёмки сняты с ним. Это не
принятый арт, а новая подсветка до арт-приёмки MS-T-27 с незакрытым MS-AT-41, поэтому правило AGENTS.md «принятый
арт по умолчанию» на неё не распространяется. Кольца V-17 (DE-017) и всё поведение DE идут по умолчанию.

## 2. Регрессии принятого арта и AGENTS.md «Board scenes and heroes»

Кадры открыты и просмотрены этим ревью (не по трассам): F `host/s09-result-screen.jpg` (Marmoreal), F
`joiner/s09-deck-own.jpg` (Sarpedon), F `phase2 … host-maneuver-draft.jpg` (Marmoreal), C
`s09-combat-resolve-revealed.jpg`, G `s09-turn-banner.jpg` (Marmoreal), G `s09-hand-limit-hint.jpg` (Sarpedon),
`AB-SHEET/00-ab-sheet.jpg`. На всех: настоящая карта (Marmoreal original 7×6 / Sarpedon original 9×6); Marmoreal —
нарисованный задник концепта (дворец, колонны, фонари, сакура; `-ConceptPaste`, ENV-U16 открыт по IMPL п. 3);
Sarpedon — остров `lit3d` (корабль, пушки, огонь); шесть фигур v2 (на итоговой доске — пять, павший растворён).
`DefaultGameUserSettings.ini` `FrameRateLimit=60` не тронут; в `Config/` набор менял только `S08IconMotion.json` и
профиль досок (rev 22, подложки). Регрессий арта нет.

**Наблюдение (не дефект набора):** в кадре C `s09-combat-resolve-revealed.jpg` крупные карты у краёв показывают
бой seq 11 (постановка ещё играет, `CUE combat seq=11 stage=end t=23383`), а служебная панель слева уже печатает
раскрытые карты seq 15. При игре людей такое наложение маловероятно, при автоклиенте — обычно. Очередь постановок
AFTER COMBAT / следующего боя — GD-044 (хвост DE-018), здесь не трогал.

## 3. Честность статусов и доказательств

- 32 `done` / 7 `planned` в [07-sprint-backlog.csv](../07-sprint-backlog.csv) — совпадает с CLOSEOUT; все хеши из
  CLOSEOUT §2 есть в git (проверял `git log`); `done` без живого гейта помечены в строках (DE-020 буст-подсказка,
  DE-022 «ваш боец», DE-026 лента DISCARDED, DE-032 CUE-002/003) — честно.
- `check-trace` перезапущен на 8 опубликованных трассах F и G `combat-client-*`: 8 PASS, `combat_totals` 3933,
  `hit_to_screen` 3167/3171, `death_sets 1`.
- «Упаковка `f4d77d98` актуальна» — верно на момент CLOSEOUT (`git diff --stat f4d77d98..c17a34fb` по коду: только
  `cue_contract.py`/тест и документы). **После этого ревью это уже не так:** исправление ворот экрана результата
  меняет клиент (`S09DeathStage.cpp`, `S08FlowGameMode.cpp`); следующая упаковка нужна перед новой живой приёмкой
  DE-019. Намеренно не упаковывал: правило «одна упаковка на изменение» и отсутствие живого прогона в этом ревью.
- `validate_package.py` падает только на старом `GD-017: progress requires evidence index` (до прогона A).

## 4. Тесты: поведение, а не константы

- `S09CombatStage`, `S09DeathStage.ResultGate`, `S09SchemeUi`, `S09HandLimit`, `S09DeckPanel`, `S09ResultTests` —
  гоняют модели по тикам и проверяют моменты событий, пропуск, повтор seq, порядок; «код = cue-table» в
  `S08MoveCueTests` — контрактный тест таблицы, это уместно.
- Слабое место, оставлено как в CLOSEOUT: в `HudPress.SyntheticClicks` строка `A.ReleaseFrame == A.PressFrame`
  (`S09HudPressTests.cpp:314`) всегда истинна — хелпер `Click` не двигает кадр между нажатием и отпусканием. Сами
  потери кликов (1440/0) и причины `why.*` проверяются честно. Исправлять не стал: нужен счётчик кадров в `FHud`,
  это отдельная правка теста, а не набора.
- Новый тест этого ревью: `Unmatched.S09.DeathStage.ResultGate` — блок «смерть staged=0 при ещё играющей
  постановке»: ждёт конец постановки, не меняет обычный путь, страховка 10 с побеждает; python
  `test_snapshot_death_waits_for_the_staging_still_playing` (PASS / DS5 раньше конца / лишний токен).
- Новый jest: `de027-rematch-spike.spec.ts` «the bot never takes the hero the human picked».

## 5. Границы

- Ни один из 107 коммитов не трогает `.claude/settings.local.json` и `evidence/S06/*.json`
  (`git log 3b68957f..HEAD -- <пути>` пуст); у всех 107 есть `Co-Authored-By`. Это ревью запускало jest только
  по спекам `de016|de027|de030|s07-privacy|game.service` — файлы S06 сверены побайтно с копией до запуска, не изменились.
- Текстов и ассетов DE нет: имена карт в панели колоды и слоте — из БД бэкенда; список звуков DE-013 — лицензируемые
  кандидаты с источником; значки — свои глифы v3/DE-012.
- Коммиты этого ревью — `--no-verify`, только свои пути. Подпись коммитов этого ревью — `Claude Fable 5.1` (модель
  ревьюера, по системному правилу атрибуции); у коммитов прогонов — `Claude Opus 5.5`.

## 6. Пересборка и перемеры этим ревью

| Гейт | Результат |
|---|---|
| `build-editor.cjs UnmatchedEditor` до правок | `Target is up to date`, `Result: Succeeded` |
| UE `Unmatched.S08+Unmatched.S09` до правок | 310/310 Success, `EXIT CODE: 0` |
| `build-editor.cjs` после правок (дважды: код, затем тест) | `Result: Succeeded`, ошибок компиляции 0 |
| UE `Unmatched.S08+Unmatched.S09` после правок | 310/310 Success, `EXIT CODE: 0` (первый прогон поймал мою ошибку в тесте страховки — исправлена) |
| `cue_contract.py validate-table` / unittest / `check-trace` 8 трасс F+G | PASS cues 18 / 49 OK / 8 PASS |
| `hud_contract.py validate` | PASS |
| jest `de016 de027 de030 s07-privacy game.service.spec`; `tsc --noEmit` | 28 + 17 passed; 0 ошибок |
| `run-vs-ai-demo.ps1 -SelfTest` | 0 failures |
| `validate_package.py` | только старый GD-017 (после правки CSV — проверено, строки читаются) |

Процессы: сборки UBT (3), UE-тесты (4), jest (2), PowerShell self-test — все завершились сами; `tasklist` без
UnrealEditor/Unmatched/UBT. Окно Unmatched: Digital Edition не трогалось.

## 7. Замечания → решение → коммит

| № | Замечание | Решение | Где |
|---|---|---|---|
| 1 (major, сервер) | `setupAiOpponent` берёт сильнейшего героя с колодой без учёта героя человека: если человек выбрал его же, `startGame` падает «Два игрока не могут играть одного героя». Это и причина T. Rex у бота в демо | Исключать героев, уже занятых людьми в комнате; среди свободных — прежнее правило. Спека: человек берёт Arthur (18) → бот берёт Medusa (16), не безколодного 20 | `backend/src/games/game.service.ts`, `de027-rematch-spike.spec.ts` |
| 2 (minor, DE-019) | Смерть `staged=0` при ещё играющей постановке предыдущего seq: экран результата открылся на 233 мс раньше конца постановки (F, Marmoreal №1) | `FS09ResultGate::Update(…, StagingEndMs)`: если активная постановка кончается позже обычного `due`, экран ждёт её (страховка 10 с сохранена); трасса `RESULT screen … staging=<ms>` только когда это сдвинуло `due`; гейт DS5 и CUE-DISPATCHER.md §5/§6 обновлены | `S09DeathStage.h/.cpp`, `S08FlowGameMode.cpp`, `S09ResultTests.cpp`, `cue_contract.py` + тест, `CUE-DISPATCHER.md` |
| 3 (minor, сценарий) | `Stop-ThisRunClient` в `run-vs-ai-demo.ps1` вызывал `GetFullPath("")` для лаунчера без `ExecutablePath`; комната оставалась `IN_PROGRESS` | Пустой путь = «unverified, left running» (fail closed), без исключения | `tools/s10/run-vs-ai-demo.ps1` |
| 4 (doc) | CLOSEOUT и строки DE-019/DE-027 называли эти хвосты открытыми | Помечены сделанными с ссылкой сюда; CLOSEOUT §8 | `CLOSEOUT-2026-10-04.md`, `07-sprint-backlog.csv` |

Не исправлял (остаётся хвостами, владельцы — CLOSEOUT §7): MS-AT-41 (+8 draw calls при пороге 7 — нужен перемер
бенчем после снятия окклюзии ISM, это живой прогон с GPU), `appliedEffects` боя в снапшоте (сервер), тост статуса
против ленты `MS-LOG`, `fighter_clip` явной картой, `S08TraceLog` «trace gap», ворота `HudPress` по кадрам.

## 8. Что остаётся пользователю

Без изменений против CLOSEOUT §5: арт-приёмка глифов DE-012 (G-ART), ответы AB-1…AB-8 по листу DE-028, выбор и
покупка звуков DE-013, плейтест GD-050 (50 ручных кликов, «ваш боец»), ENV-U16. Плюс одно новое: **перед следующей
живой приёмкой упаковать клиент заново** (ворота экрана результата изменены после `f4d77d98`).
