# VS-5: ENV-U16 — нарисованный Marmoreal по умолчанию, остатки HUD VS-4 (итог спринта)

Итог спринта VS-5 из [05-production-plan.md §3](../../../visual/05-production-plan.md). Работа шла в worktree
`C:/tmp/wt-visual`, ветка `feat/visual-vs5`. Файл написан 2026-10-08 на шаге E5 «упаковка, цена, приёмка, кадры выхода»
(EN-15, EN-16, EN-17, EN-18 и проверка остатков VS-4). Решения — по делегированию пользователя 2026-10-06 («Все решения
принимай»); приёмка — по делегированию и так помечена.

Ветка в `fix/admin-panel` **не интегрирована** (шаг E5 — только коммит в ветке). Перед `safe-integrate.sh` (сухой
прогон, затем `--apply`): основная копия держит игнорируемые копии `M_ConceptPaste.uasset` и
`T_Marmoreal_ConceptPlateA/B.uasset` — сохранить в `C:/tmp/visual-backup/<дата>/` (заметка E1); после интеграции —
пересборка UnmatchedEditor и `tools/s08/sync-staged-build.ps1 -From C:/tmp/wt-visual` (штамп `b68e21b4`). Статусы
карточек в `06-tasks/*.csv` правит основная копия после интеграции (ВР-PL09).

## Карточки

| Карточка | Коммиты | Что | Итог |
|---|---|---|---|
| EN-06, EN-07 | E1 `4114fe91`, `91d87537` | анимация вклейки, reduced motion; плита ×2 с фонарями | технически готово |
| EN-08…EN-12 | E2 `c248d3ae`, `815de6b7` | мерцание, лепестки, ветер, светлячки, туман | EN-10, EN-11, EN-12 PASS (EN-10 после ВР-VS5-47); EN-08 п. 2 частично; **EN-09 FAIL (видимость)** |
| EN-13 | E3 `8ea9c6c9`, `55dad187` | вклейка — вид Marmoreal по умолчанию, откат `-NoConceptPaste`, AGENTS.md | сделано |
| AN-36 + EN-14 | E3 `7ca326ad` | свет героев P9c | D2–D6, H2 PASS; **D1 FAIL** 0,93–0,97 |
| остатки VS-4 (HB-49) | E4 `a77bec62`, `cbd0dfb6`, `e5c72129` | кэш HUD, Slate-остатки, CONN, журнал, теги, панели, заголовок, MOVE, LEET | подтверждено на упаковке (ниже) |
| EN-15 | E5 `b4938cab` (упаковка) | цена render_bench | **PASS** по всем порогам ([README](../../ENV-MAPS/env-u16-marmoreal-2026-10-08/bench/README.md)) |
| EN-16 | E5 | лист приёмки, синхронизация документов | технически PASS; **художественно не принято** (G-READ кромки, EN-09, EN-08 п. 2, D1) ([лист](../ENV-U16/README.md)) |
| EN-17 | E5 | дополнение к акту GD-058 | принято по делегированию (без личного просмотра) ([акт](../../GD-058/marmoreal-paste-2026-10-08/README.md)) |
| EN-18 | E5 | правило задника и шаблон `paste.json` | сделано ([ENV-BACKDROP-RULES.md](../../../../art-pipeline/ENV-BACKDROP-RULES.md), [_template.paste.json](../../../../../tools/art/concept_paste/_template.paste.json)) |

## Шаг E5

### Упаковки

- `git merge fix/admin-panel` → `e9769a8c`. Новых / переименованных `Config/**.json` после упаковки VS-4 нет (ловушка
  makefile не сработала).
- До упаковки — проверка вида в editor-build клиенте (live tune, Marmoreal без флагов: K1, K1×0,65, Fitx1,45, K2×1,6,
  K2×2,5) — нарисованный задник, шесть v2, слоя отладки нет.
- Упаковка 1: `b4938cab` (тест `ArtTuner.Registry` под 5 огней вклейки Marmoreal и комментарии `-NoConceptPaste`);
  на ней бенч, все гейты, кадры выхода и эталон.
- Упаковка 2 (финальная): `b68e21b4` = тест `ArtTuner.Registry` (23 строки: у свечения портала нет блока мерцания) +
  ветер `ampPx` 0,4 (ВР-VS5-47). Проверена: свежий `-Bench` K1 / K2×1,6 совпадает с `b4938cab` (0,25 / 0,55, отличия
  только в позах фигур), ветер G7 15,7–19,2 % (ВР-VS5-46).

### Цена (EN-15, ПК разработки, не D-07)

Marmoreal GPU avg K1 / K1×0,65 / K2×1,6 / K2×2,5: вклейка 2,137 / 2,093 / 2,203 / 2,230 мс, откат P5c 2,483 / 2,417 /
2,423 / 2,413, вклейка без fx 2,070 / 2,030 / 2,143 / 2,163; шум ≤ 0,02 мс; VRAM 3764 против 3917 МиБ; ACC-022
60,00 FPS, p95 16,67 мс на 3 видах. Все пороги PASS.

### Гейты

| Гейт | Итог |
|---|---|
| `run-combat-demo` (Marmoreal 1080p 100 % и 720p 150 %, Sarpedon 1080p 100 %, LEET 720p 150 %, HB-14 через прокси, набор H) | PASS с первой попытки, SHOT widget (HB-48) — окно защиты, закрытое окно до раскрытия, результат на краях и в центре, приватность |
| `run-pending-demo` (Marmoreal 1080p 100 %, Sarpedon 720p 100 %) | PASS: 8 / 9 кадров выбора по видам, 3 заблокированных, приватность |
| `run-duel-demo` (Marmoreal, Sarpedon) | PASS (HUD_SHOTS rules 2, privacy on) |
| `run-hud-probe` | PASS (rules 3) |
| `run-hud-demo` (Marmoreal, Sarpedon; серый стенд на Slate по ВР-36) | PASS |
| `run-vs-ai-demo`, `run-vs-ai-abort-demo` (доска бэкенда по умолчанию = Marmoreal) | PASS |
| Все прогоны Marmoreal **без** `-ConceptPaste` | `ARTLOOK board=marmoreal-original backdrop=paste(default)` в каждом (16 строк), Sarpedon `lit3d(default)` (7) |
| Бюджет HUD П8 (packaged, один клиент без лимита, 1080p 100 %, `-S08HudPerf`) | Marmoreal ΔGT p95 **0,128 мс**, ΔGPU p95 0,005 (34 пары); Sarpedon ΔGT p95 −0,002 (спокойные пары 0,060), ΔGPU p95 0,032 (25 пар). ≤ 0,5 / ≤ 0,3 — **PASS** |
| `env_gates.py` G4–G7 | Marmoreal: G5 зоны K1 23,65 (K2 26,6 / 27,8), кольцо 33,4–53,9, G7 ветра (своя метрика крон EN-10) 15,7–19,2 %; G4 / G6 — метрики Sarpedon (P10 патчи и фонари), на Sarpedon: SSIM ¼ 0,490, G6 4 / 6, зоны 25,41 — как P10 |
| G-LOOK | PASS (лист ENV-U16, кадры HUD) |
| G-READ (EN-16) | текст в панелях — медианы 6,2–15,7 (LOG 4,11 по приближённой мерке); **кромка к заднику < 3 : 1 у 9 из 11 панелей — FAIL** (ВР-VS5-48) |
| Reduced motion | живая партия: `concept-paste anim … frozen=1 reason=reduced`, частицы off, кроны 0–0,009 % за 2,5 с (без флага 4,7–8,7 %) — PASS |
| UE-тесты | `Unmatched.S08 + S09 + S10`: 520 из 521 на коде `b4938cab` (единственный отказ — `ArtTuner.Registry` 25 → 23 строки), после правки `ArtTuner` 10 / 10; после ветра `ConceptPaste + EnvLayout + LiveTune + ArtTuner + ArtLook + Hud` — 162 / 162 |
| pytest | `tools/art/tests` 593 passed, 4 skipped; `tools/s08/hud_contract` 74 passed; `--check`: `env_gates`, `live_tune`, `cp_layout`, `ue_concept_material`; `cp_bake.py check marmoreal` ok |

### Остатки VS-4 на упаковке (кадры открыты, вне git — индекс [ENV-U16/data/visual-evidence-index.json](../ENV-U16/data/visual-evidence-index.json))

| Остаток (HB-49 «Открыто» / E4) | Кадр | Итог |
|---|---|---|
| 3. бюджет П8 | `-S08HudPerf`, packaged | 0,128 / −0,002 мс — закрыт |
| 4. Slate «ATTACK (Enter) / CLOSE DRAFT» | `pv-marm-1080-100 host s09-exit-attack-selected` | STATUS «Атакуйте King Arthur Enter», Slate нет |
| 4. Slate «RESOLVE COMBAT (R)» | `pv-marm-720-150 joiner s09-combat-resolve-window` | кнопка «ЗАВЕРШИТЬ БОЙ», STATUS «Завершите бой» |
| 4 / 6. «RECONNECTING…», вспышка в начале партии | `pv-marm-1080-100 host s09-exit-conn-syncing` | значок `syncing` нарисован, STATUS «Синхронизация…» |
| 4. Slate-окно защиты при постановке | окна защиты всех прогонов боя | UMG («Вас атакуют: выберите карту защиты или «Без защиты»») |
| 5. HB-14 `syncing` | тот же кадр | закрыт; в прогоне через прокси (HB-14) кадр `conn-syncing` не снят (подписка короче окна кадра), трасса `HUD-CONN state=syncing → online` |
| 14. журнал: «→» | `s09-exit-attack-selected` | «Medusa M13→M25», «King Arthur M31→M26, и ещё 1» — стрелка видна |
| 7. заголовок текстовой карты T. Rex | `vsaipv-marm-1080 human s09-card-slot-opp` | «Terrifying Roar» в рамке |
| 9. STATUS MOVE | `pend-marm-1080-100 host s09-pending-MOVE` | «Выберите клетку для Medusa» |
| 10. LEET класса S | `ileet-marm-720-150 host s09-exit-own-t3.0` | HP «…» до трекера; фишки DECKS «25 · 2» не наезжают |
| наборы A и C на Marmoreal (04 §7.4) | `pv-marm-1080-100`, `pv-marm-720-150` (13 кадров A / C в индексе) | пересняты с нарисованным задником по умолчанию |

**Английские Slate-блоки в виде по умолчанию:** на открытых кадрах (A: own-t3.0, attack-selected 1080p; C: окно защиты и «Завершить бой» 720p 150 %; D: MOVE; LEET; VS_AI; CONN) не найдено ни одного; трассы всех прогонов игрока — `hudImpl=umg`. Остаётся
английский текст из данных (не Slate): тексты эффектов карт в центре боя и в PENDING («Hiss and Slither: Your opponent
discards 1 card.», «deal 1 damage to an opposing fighter in Medusa's zone»), имена карт в журнале («Noble Sac…»), имена
героев в панелях, у бота T. Rex — «Unknown» и текстовые карты «EN» — бэкенд / данные (HB-49 п. 9, ВР-VS4-84).

## Решения шага (по делегированию)

| № | Решение | Почему |
|---|---|---|
| ВР-VS5-46 | Две упаковки: `b4938cab` — бенч, гейты, кадры, эталон; `b68e21b4` — финальная (тест + ветер), проверена бенчем K1 / K2×1,6 и ветром | полный прогон тестов нашёл устаревшее ожидание `ArtTuner.Registry`, packaged-кадры — ветер > 20 %; правки собраны вместе в одну финальную упаковку |
| ВР-VS5-47 | Ветер `ampPx` 0,4 | [лист ENV-U16](../ENV-U16/README.md) |
| ВР-VS5-48 | G-READ кромки — FAIL записан, правка HUD — отдельная карточка | [лист ENV-U16](../ENV-U16/README.md) |
| ВР-VS5-49 | Reduced motion — живой партией | live tune `--live` снимает заморозку |
| ВР-VS5-50 | Статусы реестра 03 не повышаются до «художественно принято» | FAIL в листе EN-16 |
| ВР-EN.13 | Объём EN-17 — K1 / K2 обеих карт и ACC-022 Marmoreal, лёгкий режим | карточка EN-17 |
| ВР-EN.16 | Числа K2-теста будущих карт — T1–T5 ENV-BACKDROP-RULES §2 | карточка EN-18 |

## Открыто

1. **Интеграция** `feat/visual-vs5` (см. начало) и статусы карточек EN-06…EN-18, AN-36 в `env.csv` / `anim.csv`.
2. **G-READ кромки панелей HUD** на нарисованном Marmoreal (ВР-VS5-48): тёмный внешний кант или прозрачность
   `panel.edge` ≥ 0,65, затем упаковка и пересъёмка A / C.
3. **EN-09:** лепестки почти не видны (падают на фоне крон) — ниже точка спавна, на тёмный фон.
4. **EN-08 п. 2:** размах мерцания у фонарей w / ne 5,8 / 4,6 % < 6 % (амплитуда выше 0,08 — вне лёгкого режима).
5. **EN-14 D1** 0,93–0,97 (как P9b) — Р-34 в акте GD-058 остаётся FAIL.
6. **Полосы движения** сняты через 0,5–0,8 с, не через 100 мс (предел инструмента кадра).
7. **validate_registry.py** падает и в основной копии на `art/um-materials/um-masters.json` (sha256) — не связано с
   этим шагом; в worktree добавляются ошибки отсутствующих игнорируемых GLB / PNG.
8. Данные: RU-тексты карт и имена героев (бэкенд), «ИИ думает» не снимается (бот ходит быстрее кадра).

## Ревью VS-5 (один проход, арт + объём; 2026-10-08, по делегированию)

- **Объём:** 21 коммит `fix/admin-panel..0a09c9b6` (243 файла) — всё относится к EN-06…EN-18, AN-36 и остаткам VS-4
  (HB-49 / E4). AGENTS.md — только флаг `-NoConceptPaste` в списке откатов и замена записи «Known gap» на «ENV-U16
  fixed». Горячие файлы малы: `S08BoardActor.cpp` +19, `S08FlowGameMode.cpp` +8, `S08FlowGameModeUmHud.cpp` +31.
- **Вид по умолчанию:** `marmoreal-original.conceptPaste` default on / mode paste / offVariant p5c; в слое концепта
  `props.add` пуст — поверх нарисованного задника 3D-моделей не добавлено (только Niagara: лепестки, светлячки). Профиль
  Sarpedon не менялся; `manifest.sarpedon.json` — только хеш `cp_bake.py`; `cp_bake check sarpedon` ok.
- **Откаты:** `-NoConceptPaste` (тесты ResolveMode + `ARTLOOK p5c(flag-off)`, packaged-кадр отката), `-NoHeroLight`,
  ключи `-S08SlateHud` — покрыты UE-тестами; полный прогон S08/S09/S10 520/521 (единственный отказ исправлен, 10/10),
  финальные наборы 162/162 — логи `C:/tmp/visual/E5/logs/` проверены.
- **Повтор ревьюером:** pytest `tools/art/tests` 593 passed / 4 skipped, `tools/s08/hud_contract` 74 passed;
  `cp_bake check marmoreal|sarpedon`, `cp_layout --check`, `live_tune --check`, `env_gates --check` — ok.
- **Штамп:** `Saved/StagedBuilds/Windows/BuildStamp.json` commit `b68e21b4`, sourceHash `7af75f21…` = хеш исходников
  ветки на `0a09c9b6` (после `b68e21b4` менялись только docs).
- **Правило доказательств (ВР-VS4-01):** 65 новых изображений в `docs/` — кадры доски / окружения без HUD, листы и
  полосы движения; кадры HUD со сканами и аватарами — вне git (17 файлов, хеши индекса
  `ENV-U16/data/visual-evidence-index.json` совпали).
- **Кадры открыты ревьюером (31):** bench K1, K1×0,65, K2×1,6, K2×2,5 по умолчанию; откат `-NoConceptPaste` K1; Sarpedon
  K1 и GD-058 K2×1,6; лист ENV-U16 (цвет); полосы мерцания, лепестков, ветра 0,4, reduced motion; крупный план P9c;
  HUD A / C на нарисованном Marmoreal (own-t3.0 1080p, attack-selected, окно защиты 720p 150 %, «Завершить бой»),
  CONN syncing, MOVE, T. Rex, LEET. Заявления README подтверждены, в том числе FAIL: лепестки на полосе не видны,
  мерцание едва заметно, разница P9b / P9c на глаз не видна (D1).
- **Уточнения:** строк `ARTLOOK … backdrop=paste(default)` в трассах прогонов гейтов — 18 (в таблице выше «16»);
  Sarpedon `lit3d(default)` — 7.
- **Замечания (в VS-6, не блокеры):**
  1. Свет героев P9c (`lightProfiles.marmoreal-night.heroLight`) общий для вклейки и отката `-NoConceptPaste` — откат
     P5c тоже получает P9c. Откат касается задника, но это не записано; записать или развести профили.
  2. Кадр `conn-syncing` в начале партии: поле доски — низкий мип (крупные блоки) под вуалью синхронизации; проверить
     стриминг текстур плиты в первые секунды.
  3. Кадры `-Bench` (и крупные планы P9c) несут старые подписи над фигурами («Harpies 1 1/1», «Medusa 16/16») —
     по ВР-07 постоянных табличек имён нет; проверить слой подписей в режиме bench.
  4. Кадры HUD вне git лежат в `scraped-data` worktree: после интеграции скопировать `VS-5-E5/` и `HB-49-E4/` в
     `scraped-data/derived/visual-evidence/` основной копии (индексы ссылаются на путь «относительно копии»).
  5. Объём доказательств в git: ~16 PNG по 3,6–4 МБ (кадры live / P9c); новые кадры такого типа — JPEG.
- **Интеграция:** сухой прогон `safe-integrate.sh feat/visual-vs5` из основной копии — PREFLIGHT OK (fast-forward, ветка
  содержит `3548255a`). `safe-integrate` не видит игнорируемые файлы: перед `--apply` сохранить игнорируемые
  `M_ConceptPaste.uasset`, `T_Marmoreal_ConceptPlateA/B.uasset` основной копии в `C:/tmp/visual-backup/2026-10-08/`.
- **Вердикт:** EN-06, EN-07, EN-10, EN-11, EN-12, EN-13, EN-15, EN-17, EN-18, остатки VS-4 — PASS (по делегированию);
  EN-08 — PASS с частичным п. 2; EN-09 — FAIL (видимость); AN-36 + EN-14 — PASS кроме D1; EN-16 — технически PASS,
  художественно не принято. Ветка готова к интеграции.
