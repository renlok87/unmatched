# Прогон C (S11c — бой и смерть): живая приёмка G-LIVE (2026-10-05)

**Итог: пройдено после одного исправления.**
- DE-018 и DE-019 приняты целиком.
- MS-T-12 и DE-020 приняты в той части, которую воспроизводит живой бой двух клиентов. Что не воспроизводится, перечислено в таблице приёмки ниже.

Как проверяли:
- два клиента в упакованной сборке, 30 FPS на клиент, оба offscreen;
- партии до GAME_OVER на Marmoreal original и Sarpedon original;
- `check-trace --min-combat 1 --min-death 1` прошёл на всех четырёх трассах итогового пакета;
- кадры просмотрены глазом до отчёта.

Первый прогон Sarpedon нашёл дефект DE-018: CUE-011 постановки отбрасывался как `stale`. Дефект исправлен в `018c04c7`, клиент перепакован, обе карты прогнаны заново.

- Полномочия и решения оркестратора — [IMPL-2026-10-04.md](../../../../de-footage/task/runs/IMPL-2026-10-04.md).
- Журнал прогона — [C-2026-10-04.md](../../../../de-footage/task/runs/C-2026-10-04.md), раздел «Живая приёмка G-LIVE».
- Гейт — [07-sprint-plan.md](../../../../de-footage/task/07-sprint-plan.md) §8: G-LIVE, а также G-COST для DE-019.

## Коммиты агента приёмки

| Коммит | Что |
|---|---|
| `96a73e78` | `tools/s09/run-combat-demo.ps1 -ClientExtraArgs` — дополнительные аргументы обоим клиентам, как в `run-phase2-demo`. Нужен `-ConceptPaste` для Marmoreal (IMPL п. 3; правило задника AGENTS.md). Гейты не менялись |
| `018c04c7` | **Исправление DE-018 (и DE-019).** `FS08CueDispatcher::Feed(…, bStaged)`. CUE-011 из кадра контакта и CUE-013 из падения боя идут с seq своего боя. Более новые снапшоты, пришедшие за время постановки, больше не делают их `stale`: правило D3 к ним не применяется, D2 и D4 применяются. Синхронно обновлены эталонная модель `cue_contract.py`, схема фикстур, фикстура `staged-hit-after-newer-seq`, тест `Unmatched.S08.CueDispatcher.Hold` и правило D3 в CUE-DISPATCHER.md |
| `01edba4d` | `run-combat-demo.ps1` с `-RequireGameOver` публикует кадр экрана результата `s09-result-screen.png` обоих мест. Это свидетельство DE-019: экран появляется после исчезновения героя + 1000 мс |

Гейты после исправления:

| Гейт | Результат |
|---|---|
| Сборка редактора и игровой цели | `Result: Succeeded`, новых предупреждений нет |
| UE `Unmatched.S08.CueDispatcher+Unmatched.S09.CombatStage+Unmatched.S09.DeathStage` | 8/8 Success |
| UE `Unmatched.S08+Unmatched.S09+Unmatched.S10` | 325/325 Success |
| `cue_contract.py validate-table` | `CUE_TABLE PASS 18` |
| `cue_contract.py run-fixtures` | `CUE_FIXTURES PASS fixtures 18 bad 0` |
| pytest `tools/s08/cue_contract` | 35 passed |

## Окружение

- **Бэкенд** — основной стек `:3000`: postgres, redis и backend были подняты до агента и оставлены. `/health` отвечает database up, redis up.
- **Найдено.** Контейнер исполнял старый `dist` от 2026-10-04 04:25. В нём не было DE-016 (`metadata.skippedEffects`, коммит `4153bd2f`). Причина в том, что контейнер запускает `dist` с хоста через bind mount, а после прогона A′ `dist` не пересобирали.
- **Что сделано.** `docker exec unmatched-backend npm run build`, затем `docker compose restart backend`. После этого `/health` ok. Незакоммиченных правок в `backend/` не было.
- **Аккаунты.** Использованы демо-аккаунты `S08_DEMO_*` из `C:/tmp/wt-envmaps/backend/.env`. Они передавались только в окружение процесса, как `S09_DEMO_*`, и нигде не печатались.
  - Аккаунтов `S09_DEMO_*` из `backend/.env` в основной БД нет: логин отвечает «неверный email или пароль».
- **GPU.** Демо и бенч шли под замком `C:/tmp/unmatched-gpu.lock`, владельцы `C-LIVE` и `C-LIVE-BENCH`. Steam-игры пользователя на машине не было.

## Сборка и упаковка

| Шаг | Результат |
|---|---|
| Упаковка 1 — `package-client.ps1 -SkipBuild` | `UAT_EXIT=0`, `LogCook: Warning/Error` — 0. Штамп `8b1dbd2d` (конец прогона C). Внутренний exe `46f7beb5…` совпадает с `Binaries/Win64` |
| Упаковка 2, вынужденная, после исправления `018c04c7` | `UAT_EXIT=0`, cook без предупреждений. Штамп [BuildStamp.json](BuildStamp.json): commit `01edba4d`, sourceHash `6acc3f3b…`, 161 файл. Внутренний exe `371871f5…` совпадает с `Binaries/Win64` |

Новых `Config/**.json` в прогоне C нет, поэтому регенерация makefile не нужна.

## Живой прогон двух клиентов (итоговый пакет `01edba4d`)

Обёртка `C:\tmp\c-live\run-combat.ps1` лежит вне репозитория. Команда:

```
run-combat-demo.ps1 -Api http://localhost:3000/graphql -ArtPreview -FullHd -ArtPreviewBoardId <board>
  -ArtPreviewHeroesV2 -ArtPreviewDiorama -ClientFps 30 -ClientRenderPreset High -RequireRenderReference
  -RequireShotCaptured -ClientPerf -RequireGameOver -RunSeconds 480 -JoinerAttack
  [-ClientExtraArgs -ConceptPaste]   # только Marmoreal (IMPL п. 3, ENV-U16 открыт)
python tools/s08/cue_contract/cue_contract.py check-trace <trace> --min-combat 1 --min-death 1
```

Роли: хост — Medusa с тремя Harpy, план `attack+defend+ownresult`. Джойнер — King Arthur с Merlin, план `attack+ranged+defend+resolve`.

### Marmoreal · original map — [demo/marmoreal/combat-20261005-073908](demo/marmoreal/combat-20261005-073908/)

| Проверка | Хост / джойнер |
|---|---|
| Доска | `c121b47f8d6eb28daccb76d05`, `marmoreal-original`, 7×6, 31 пространство / 42 связи. Сверено с записью игры на сервере |
| `ARTLOOK` | `art=1 source=default heroes=v2 tray=on env=on review=1 legacyRender=0` на обоих |
| Фигуры | `heroesV2 summary fighters=6 mapped=6 v2=6`. Клипы: Idle 24, LungeAttack 6, HitReact 12, DeathSettle 1 |
| Задник | `envlayout variant=concept … status=ok propsRemoved=64`, `concept-paste status=ok`, поднос скрыт |
| Партия | 17 ходов, seq 96, FINISHED. Хост VICTORY, джойнер DEFEAT. 15 боёв: атак хоста 8, атак джойнера 7. Сходимость seq 96/96 |
| `check-trace` | `CUE_TRACE PASS` на обоих: presented 44, stale 0, `combat_sets 15`, `combat_cut 9`, `combat_totals` 6 × 3933, `death_sets 1`, `result_screens 1`, `hit_to_screen [3167]` |
| Смерть King Arthur (seq 96) | Этапы `fall` → `mark heart=dark` (+650) → `dissolve` (+1175, 500 мс, fade) → `gone` (+1675). `death hidden=1 afterFall=1.700 plan=1.675`, расхождение +25 мс при допуске ±50 |
| Экран результата | `RESULT screen seq=96 … due=61193 heroGone=60193` — показан в t=61218 |
| FPS | Кап 30, `fps=30.00` в окнах без рывков, gpuMs 1,5–3 |

### Sarpedon · original map — [demo/sarpedon/combat-20261005-074029](demo/sarpedon/combat-20261005-074029/)

| Проверка | Хост / джойнер |
|---|---|
| Доска | `c7fa64a26c29a0835f2383e63`, `sarpedon-original`, 9×6, 38 пространств / 61 связь. Сверено с сервером |
| `ARTLOOK` / фигуры | То же, что на Marmoreal. `v2=6`. Клипы: Idle 29, LungeAttack 7, HitReact 16, DeathSettle 1 |
| Задник | `concept-paste mode=on reason=default`, `concept-scene status=ok mode=lit3d` (путь 1), 5 огней |
| Партия | 19 ходов, seq 103, FINISHED. Хост VICTORY. 13 боёв: атак хоста 7, атак джойнера 6. Сходимость seq 103/103 |
| `check-trace` | `CUE_TRACE PASS` на обоих: presented 41, stale 0, `combat_sets 13`, `combat_cut 7`, 6 × 3933, `death_sets 1`, `hit_to_screen [3167]` |
| Смерть / экран | Те же этапы и числа: `afterFall=1.700 plan=1.675`, `RESULT screen … due=71385`, показан в 71410 |

### Прогоны до исправления (пакет `8b1dbd2d`), только трассы

Кадры этих прогонов не публиковались: PNG удалены, sha256 остались в `manifest.json` и в строках `SHOT captured` трасс.

- **[Sarpedon, combat-20261005-072841](demo/sarpedon/combat-20261005-072841/).** Демо-скрипт прошёл, но `check-trace` упал на обеих трассах: `GATE C5 seq 24: CUE-011 не из кадра контакта`. Пока ставился бой seq 24, ход соперника успел объявить атаку (`CUE-008 seq 28`, `CUE-009 seq 29`). В кадре контакта вышло `CUE fx id=CUE-011 subject=f-0-hero seq=24 … result=stale`: вспышки удара и звука нет. Исправлено в `018c04c7`.
- **[Marmoreal, combat-20261005-072511](demo/marmoreal/combat-20261005-072511/).** `CUE_TRACE PASS`, но в трассе тот же `CUE-011 seq=28 … result=stale`. Гейт его не поймал, потому что постановку seq 28 оборвал следующий бой.

## Кадры (просмотрены глазом до отчёта)

Все кадры — итоговый пакет, 1920×1080, сохранены в JPG шириной 1600 (q88).

**Marmoreal.** Настоящая карта Marmoreal. Вокруг нарисованный задник из концепта: лестница дворца, колонны, фонари, сакура. 3D-окружения P5c нет.
- [Хост, удар](demo/marmoreal/combat-20261005-073908/host/s09-damage-combat.jpg) (постановка боя seq 11, у хоста уже открыт черновик атаки):
  - карта атаки у левого края поля («ATTACK — Merlin, Swift Strike, ATTACK 3»), карта защиты у правого («DEFENSE — Medusa, Regroup, DEFENSE 1»);
  - пару бойцов в центре карты не закрывают;
  - «−1» у плашки King Arthur — от способности Medusa.
- [Хост, результат боя seq 17](demo/marmoreal/combat-20261005-073908/host/s09-combat-result.jpg): карты у краёв поля («ATTACK — Medusa, Second Shot, ATTACK 3 + boost 2» / «DEFENSE — King Arthur, Divine Intervention, DEFENSE 3»), «−2» над плашкой King Arthur 15/18.
- [Джойнер, «−N» и выбор после боя](demo/marmoreal/combat-20261005-073908/joiner/s09-damage-number.jpg) — живой кадр MS-T-12 / DE-020.
  - Панель «PENDING CHOICE — MOVE [optional — X declines]».
  - Текст панели: «step 2/2: Choose a target (up to 4)», «YOUR CHOICE: Effect choice: move Merlin up to 4», «fighter: Merlin destination: stays in place».
  - Кнопки CONFIRM (Enter), STAY IN PLACE, DECLINE (X), COLLAPSE (C).
  - CONFIRM, STAY и DECLINE приглушены: автодрайвер только что отправил ответ (`PEND-RESOLVE sent` в том же кадре, команда в полёте). Это верно.
  - 16 допустимых пространств обведены. Клиент запущен без `-S08MovePlates`, поэтому обводка — прежние золотые кольца; V-11 показан на бенч-кадрах ниже.
  - Medusa в красной заливке удара (CUE-011), «−2» над её плашкой 14/16.
- [Хост, экран результата](demo/marmoreal/combat-20261005-073908/host/s09-result-screen.jpg) и [джойнер](demo/marmoreal/combat-20261005-073908/joiner/s09-result-screen.jpg):
  - «VICTORY / DEFEAT — Medusa won the duel»;
  - King Arthur на доске уже нет: растворился до экрана;
  - Merlin, Medusa и три Harpy стоят — это верно;
  - экран временный, отладочного вида: финальный вид — DE-029.

**Sarpedon.** Настоящая карта Sarpedon. Вокруг `lit3d`: остров, корабль с пушками, костры, фонари.
- [Хост, результат боя seq 7](demo/sarpedon/combat-20261005-074029/host/s09-combat-result.jpg): шесть фигур v2; карты у краёв поля; плашка King Arthur ещё 18/18 — HP удерживается до контакта + 80 (`FS09CombatHold`).
- [Джойнер, удар](demo/sarpedon/combat-20261005-074029/joiner/s09-damage-combat.jpg):
  - «A2 vs D0 · Merlin WINS — Medusa −2»;
  - слот защиты «NO DEFENSE» с крестом;
  - «−2» над плашкой Medusa 11/16.
- [Хост, экран результата](demo/sarpedon/combat-20261005-074029/host/s09-result-screen.jpg): King Arthur исчез, остальные пять фигур на местах.
- Остальные кадры обеих карт тоже просмотрены: окно защиты, окно резолва, раскрытие, результат у джойнера.

## G-COST DE-019 (растворение) и сцены pending MS-T-12 в пакете

Условия: `render_bench.py run` на итоговом пакете, без капа FPS, 2 повтора, виды K1 и K2x1,6. Варианты `dx12-lumen-high-v2`, `…-dissolve-fade`, `…-dissolve-ash` на `S08BenchMarmoreal.json` и `S08BenchSarpedon.json`. В каждом прогоне растворение применено на половину (0,5) ко всем шести фигурам v2 (`dissolve bench … progress=0.50 style=fade|ash mi=MI_<Hero>_H2LD_P<n>_Dissolve`) — это худший случай.

Сводка — [bench/g-cost-views.json](bench/g-cost-views.json). Записи — `bench/*-bench-run.json`, трассы — `bench/*.trace.txt`.

| Карта, вид | GPU, мс: база | fade | Δ | ash | Δ |
|---|---|---|---|---|---|
| Marmoreal K1 | 2,500 | 2,505 | +0,005 | 2,495 | −0,005 |
| Marmoreal K2x1,6 | 2,455 | 2,455 | 0,000 | 2,450 | −0,005 |
| Sarpedon K1 | 2,620 | 2,615 | −0,005 | 2,610 | −0,010 |
| Sarpedon K2x1,6 | 2,510 | 2,520 | +0,010 | 2,510 | 0,000 |

- **G-COST: пройдено.** |Δ| ≤ 0,010 мс при шуме повторов 0,00–0,03 мс. Растворение шести фигур сразу по цене неотличимо от базы.
- **Кадры растворения в пакете:**
  - Marmoreal: [база K2](bench/marmoreal-base-K2x1p6.jpg), [fade K2](bench/marmoreal-fade-K2x1p6.jpg), [ash K2](bench/marmoreal-ash-K2x1p6.jpg);
  - Sarpedon: [база](bench/sarpedon-base-K2x1p6.jpg), [fade](bench/sarpedon-fade-K2x1p6.jpg), [ash](bench/sarpedon-ash-K2x1p6.jpg);
  - fade — фигуры полупрозрачны, ash — фигуры сгорают с золотым фронтом.
  - Бенч Marmoreal идёт без `-ConceptPaste`, поэтому вокруг поля 3D-окружение P5c. Это известный разрыв ENV-U16. Кадры подтверждают только растворение и стоимость, вид Marmoreal они не подтверждают.
- **Сцены pending MS-T-12** (`dx12-lumen-high-v2-moveplates`, `--move-draft tools/s08/fixtures/move-draft/<map>-3-pending-*.json`):
  - Marmoreal: [K1](bench/marmoreal-pending-K1.jpg), [K2](bench/marmoreal-pending-K2x1p6.jpg); трасса `MS-PENDING open … type=MOVE value=3 … stay=1`, `MS-HL view source=bench plates=9 ring=8 paths=1`;
  - Sarpedon, чужой боец: [K1](bench/sarpedon-pending-K1.jpg), [K2](bench/sarpedon-pending-K2x1p6.jpg); трасса `owner=opponent … stay=1 decline=1`, `plates=6 ring=6`;
  - на кадрах видны пунктирные подложки V-11 на допустимых пространствах; под двигаемой фигурой подложки нет;
  - упакованный клиент принял сцену по абсолютному пути вне `Config/Bench` (`-BenchMoveDraft=<repo>\tools\s08\fixtures\…`). Вопрос MS-T-27 из хвоста MS-T-12 закрыт;
  - в режиме бенча HUD не рисуется, поэтому панели «YOUR CHOICE» на этих кадрах нет. Панель есть на живом кадре джойнера Marmoreal (выше).

## Приёмка задач прогона

| Задача | Что проверено в пакете | Статус |
|---|---|---|
| DE-018 | Постановка боя на 28 боях в итоговом пакете. C1–C7 прошли на четырёх трассах. `total=3933` в каждом бою без обрыва (текст на карте, строк эффекта 0) — цель ≈3,9 с ±10 %. HP удерживается до контакта (кадр Sarpedon seq 7). Карты у краёв и метка исхода не закрывают пару. После исправления `018c04c7` CUE-011 выходит из кадра контакта и не бывает `stale` | **принято** (G-LIVE) после исправления. Не видели вживую: бой без текста (≈2,9 с) и строки эффекта (`lines=0`: нет серверного поля — хвост DE-031) |
| MS-T-12 | Живые трассы: `MS-PENDING open … type=MOVE … stay=1 decline=1` (свой герой и чужой ход), двухшаговый выбор `step=object 1/2` → `step=target 2/2`. Выбор после боя открывается после `CUE combat … stage=end`. Живой кадр панели: «YOUR CHOICE … move Merlin up to 4», «destination: stays in place», кнопки STAY IN PLACE / DECLINE / COLLAPSE, 16 обведённых пространств. В пакете есть сцены pending с V-11 на обеих картах | **принято** (G-LIVE). Контраст V-11 — MS-T-13 / MS-T-27 |
| DE-019 | Смерть героя на обеих картах, этапы F-09: `afterFall` 1,700 при плане 1,675 (+25 мс). `hit_to_screen` 3167 при цели ≈3125 (+42 мс, допуск ±50). Экран результата приходит после исчезновения + 1000 мс, на кадре героя нет. G-COST пройден | **принято** (G-LIVE, G-COST). Смерть помощника (гарпия не открывает экран) вживую не выпала, её покрывает тест `Unmatched.S09.DeathStage.ResultGate` |
| DE-020 | Первое открытие своей головы очереди — `MS-PENDING present=modal`. Повтор необязательного триггера — `present=toast … remembered=fighter=f-1-hero` (способность Medusa, 9 и 8 раз). Двухшаговый «объект → цель» в трассах. Кнопка COLLAPSE (C) на живом кадре панели | **принято частично** (G-LIVE). Вживую не воспроизводилось: подсказка способности King Arthur (`ATTACK ability.prompt`), потому что King Arthur ни разу не атаковал, а автодрайвер подсказку не открывает; `MS-SKIP` и тост «No legal targets», потому что сервер ни разу не снял эффект; компактная панель; свернуть/развернуть. Всё это покрыто тестами `Unmatched.S09.PENDING DE-020 *` |
| DE-014 (хвост из B) | ACC-020 — нажатие на HUD в окне боя с отсчётом | **не воспроизведено**: в `run-combat-demo` нет шагов ввода по HUD. Остаётся на тесте `SyntheticClicks` и ручных 50 кликах пользователя |

## Замечания и дефекты

1. **Дефект DE-018 / DE-019, исправлен** (`018c04c7`). Сценарий: соперник объявляет следующую атаку, пока предыдущий бой ещё ставится. Тогда CUE-011 из кадра контакта (и CUE-013 падения) отбрасывался по правилу D3. В живом бою пропадали вспышка удара, HitReact-канал CUE и звук.
2. **Автодрайвер действует во время постановки.** 9 боёв из 15 на Marmoreal и 7 из 13 на Sarpedon оборваны следующим боем (`cut=replace`, правило D6 работает как задумано). Это темп автодрайвера, у людей так бывает редко. В итоге полная постановка видна только в 6 боях на карту.
3. **Рывки игрового потока ~240 мс в фазе боёв** у обоих клиентов: `hitches50` 1–5 за окно 5 с, `gameMs p95` до 25 мс. Так было и до прогона: в ENV-MAPS P3 (2026-10-01) — 15 рывков, max 310 мс. Это не регрессия прогона C, но кандидат на отдельную задачу производительности.
4. **Бэкенд работал на устаревшем `dist`** без DE-016 — см. «Окружение». Пересобран и перезапущен; проверьте этот шаг в процедуре после серверных задач.
5. Экран результата пока отладочного вида — DE-029. Карты у краёв и HUD пока на английском — GD-047 / GD-048.
6. Бенч-кадры Marmoreal показывают 3D P5c — известный разрыв ENV-U16, в этот прогон не входит.

## Процессы

- **Запускал агент:** сборки UBT, UE-тесты (UnrealEditor-Cmd), RunUAT ×2, пары клиентов демо (4 прогона: по 2 на карту), 14 клиентов `-Bench` под замком. Все процессы завершились сами, замки сняты.
- **Docker-стек** был поднят до агента и оставлен. Бэкенд пересобран и перезапущен (см. «Окружение»).
- **Приватность.** Коды комнат в трассах заменены на `<redacted>` самим скриптом. Email в трассах нет. Файлы `*.log` переименованы в `*.txt` (`*.log` в gitignore), байты не менялись.
