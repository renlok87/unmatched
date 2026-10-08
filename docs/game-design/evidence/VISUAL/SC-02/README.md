# SC-02 — фон экранов меню: живая сцена Marmoreal K1 без фигур (`UUmMenuBackdrop`)

VS-7, шаг S1, 2026-10-08, ветка `feat/visual-vs7` (worktree `C:/tmp/wt-visual`). Карточка — `screens.csv` SC-02; 04 §1
(фон BOOT…ROOM), §7.4; 02 §10.1, §10.5; ВР-53…ВР-56, ВР-75; AGENTS.md «Board scenes and heroes».

**Статус:** UE-часть готова, живая проверка одним клиентом editor-build, по делегированию. Кадры LOGIN без UI packaged с
отпечатком `RENDER` (1920×1080 и 1280×720) и лист приёмки — шаг «Кадры» (упаковка одна на спринт). **Откат:**
`-S08SlateHud=menubg` или `-S08SlateHud` — прежний чёрный фон.

## Что сделано

| Пункт | Где и как |
|---|---|
| Сцена | `S08/UI/UmMenuBackdrop.h/.cpp` (фикстура, трасса, ключи отката) + игровая сторона `S08/S08FlowGameModeUmScreens.cpp`. Доска — `boardState` фикстуры `-Bench` `Config/Bench/S08BenchMarmoreal.json` (Board `c121b47f8d6eb28daccb76d05`, бойцы фикстуры не читаются), тот же `AS08BoardActor` и путь `SetRoomBoardId` → `Rebuild`, что у доски партии: профиль `marmoreal-original`, нарисованный задник по умолчанию (`ARTLOOK board=marmoreal-original backdrop=paste(default)`), свет и анимации вклейки как в партии. Бойцов нет — нет подложек, тегов, плашек. |
| Камера | K1 `SetupCameraForBoard` (pitch −55, yaw −90, FOV 35, `k1DistanceMul` профиля) на `BoardCamera`, риг зума в обзоре; без строк `CAMERA` (гейты партии читают свои). |
| Жизнь | строится в первом тике после BOOT и живёт при смене экранов; первый снапшот партии: Marmoreal — те же акторы становятся доской партии (`state=handover`, второй копии нет), другая доска — доска меню уходит в том же кадре, где появляется доска партии (`state=swap to=<id>`, Sarpedon); после партии (доска партии снята) — строится снова. |
| Трасса | `SCREEN-BG board=marmoreal-original boardId=c121b47f8d6eb28daccb76d05 profile=marmoreal-original fighters=0 veil=0.60 backdrop=paste stage=<Boot|Login|Failed|Started…> state=menu|handover|swap|off` на каждой смене стадии; `ARTLOOK` не менялся. |
| Хуки | `S08FlowGameMode.cpp`: 1 строка в BeginPlay (`BuildUmFlowScreens`), 1 в Tick, 5 в `SyncBoardFromApplied` (передача доски), 1 в `UpdateLegacyRootVisibility`; объявления в `.h`. |
| Музыка | `MUS-MENU` звучит сама (аудио-чат, 08-screen-audio-hooks), экран её не вызывает. |

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-04 | Фон меню — отдельный актор доски из фикстуры `-Bench`; на Marmoreal он передаётся партии, на другой доске заменяется в кадре первого снапшота; после партии строится заново | «тот же путь, что `-Bench`», без второй копии; доска партии в `BoardActor` трогает 134 места режима — фон меню там не живёт |
| ВР-VS7-11 | Ключи отката независимы: `menubg` — только сцена, `boot` / `login` — только экраны (Slate-панель потока тогда лежит над сценой) | ВР-SC04: каждый ключ возвращает свой прежний вид |
| ВР-VS7-12 | Цена фона мерится сценой K1 фикстуры с бойцами `health 0` (скрыты) против той же фикстуры с шестью фигурами; пустой массив бойцов `-Bench` не принимает (`BENCH FAILED fighters/board decode`) | один прогон, та же сцена, что видит меню |

## Цена (одно измерение, правило «без оптимизаций»)

`render_bench.py run --variant dx12-lumen-high-v2 --views K1 --repeats 1`, упаковка VS-6 `bcaf737b` (сцена не зависит от кода
шага), RTX 4090, без лимита FPS: **K1 партии с фигурами — GPU 2,14 мс (p95 2,27), фон меню — 1,95 мс (p95 2,13): ΔGPU
−0,19 мс** — в бюджете «не выше K1 партии». Кадр — `menu-bg-bench-K1-1920x1080.jpg` (packaged `-Bench`, `RENDER`).
Прогоны: `C:/tmp/visual/VS7/bench/out/k1-figures`, `k1-menubg` (вне git).

## Проверка

- Живые прогоны (UnrealEditor `-game` worktree, 30 FPS, offscreen, основной бэкенд :3000): `a2` — `SCREEN-BG … stage=Boot
  state=menu`, `stage=Failed`, `stage=Login` (`fighters=0` во всех стадиях до партии); `c2` — возврат в живую партию VS_AI на
  Sarpedon: `stage=Started state=swap to=c7fa64a26c29a0835f2383e63`, в той же секунде `ARTPREVIEW board profile=sarpedon-original`,
  `ARTLOOK board=sarpedon-original backdrop=lit3d(default)`, `FIGHTERS synced n=6` — кадра Marmoreal с фигурами нет; `r1` —
  `-S08SlateHud=menubg`: `SCREEN-BG … state=off reason=-S08SlateHud`, чёрный фон; `r2` — `-S08SlateHud=boot,login`: сцена есть,
  экраны Slate.
- Открыты (Read): `menu-bg` (`a1`, `a2`) — Marmoreal original, нарисованный задник, фигур 0; кадр `-Bench` без фигур; кадр отката
  `r1`.
- Тест `Unmatched.S08.Hud.Screens.MenuBg` — фикстура, строка `SCREEN-BG`, ключи отката — PASS.

## Кадры в git (editor-build, не приёмка)

`menu-bg-1920x1080-editor.jpg`, `menu-bg-bench-K1-1920x1080.jpg`, `rollback-menubg-login-1920x1080.jpg` (сканов и аватаров нет).

## Не сделано в этом шаге

- Кадры LOGIN без UI packaged 1920×1080 и 1280×720 с `RENDER` (заменяют фон-заглушку макетов, ВР-SC03), G-LOOK на них,
  статус в реестре 03 — шаг «Кадры».
- Экран загрузки SC-19 (под ним смена доски) — шаг LOADING; до него смена идёт в кадре первого снапшота.
