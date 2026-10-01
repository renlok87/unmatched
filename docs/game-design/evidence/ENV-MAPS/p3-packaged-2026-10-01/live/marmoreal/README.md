# ENV-MAPS P3 · живые packaged-прогоны на оригинальной карте **Marmoreal** (2026-10-01)

**Статус: измерено.** Два packaged-клиента играли по реальному бэкенду на доске Marmoreal, на её графе пространств и с окружением. Сыграны два прогона:
- K1 — старт, обрыв WS у присоединившегося и кадры;
- K3 — дуэль до GAME_OVER.

Все гейты скриптов пройдены. Оба проверяльщика графа подтвердили:
- ходы шли по связям;
- была атака дальнобойной Medusa по несмежной цели в общей зоне;
- итог совпадает с сервером.

Все 10 опубликованных кадров — `packaged-live` / `strict` на эталоне рендера. Производительность записана для справки и **не является заявкой ACC-022**. Художественная приёмка этим актом не выставляется: «художественно принято» решает только пользователь.

**Полномочия** (пользователь, дословно):
- порядок шагов, ENV-U11: «Сначала packaged + live, потом правки (Recommended)»;
- свет луны, ENV-U12: «Оставить как есть (Recommended)». Ключ (−55, 30, 0) не трогался;
- параллельные окна: «мне нужно чтобы два окна не сломались при мержде в ветку fix/admin-panel».

Платных шагов не было, коммитов тоже: коммитит оркестратор.

## 1. Условия

- **Сборка.** Один бинарник этапа PACKAGE: worktree `C:/tmp/wt-envmaps`, ветка `feat/env-original-maps`, HEAD 9f1c66c4.
  - Внутренний `Unmatched/Binaries/Win64/Unmatched.exe`: sha256 `d0b49f8c3bbee39b59685756a8e5954e56c71b5458e386edcd38ae459c99057a`. Он совпадает с `Binaries/Win64` и пересчитан перед прогонами.
  - Пак `Unmatched-Windows.pak`: `17cb484f…a0d6`.
  - Запись сборки: [package-record.json](package-record.json). Логи `build-g.out.log` («Result: Succeeded») и `uat.log` («BUILD SUCCESSFUL», кук «0 error(s)») лежат вне git в `C:/tmp/envmaps-research/p3/package/`.
  - Хэши exe и паков записаны ещё и в каждом `run-record.json`.
- **Бэкенд.**
  - `:3120`, PID 56068: `node -r dotenv/config dist/src/main.js` из `C:/tmp/wt-envmaps/backend`. Запущен этапом STACK, перед прогонами отвечал на `{ __typename }`.
  - Изолированная БД `codex-s09-postgres` (:55434) и Redis `codex-s09-redis` (:6381).
  - Доска `c121b47f8d6eb28daccb76d05` «Marmoreal · original map»: решётка 7×6, 31 пространство, 42 связи.
- **Учётные данные** берутся из `backend/.env` через `tools/s09/run-with-env.cjs`. Они передаются только в окружение дочернего процесса, в argv их нет.
- **GPU-токен** `C:/tmp/unmatched-gpu.lock`: взят в 08:21:58, снят в 08:30:31 ([gpu-lock.txt](gpu-lock.txt)). До нас токен был свободен. Процессов Unmatched, UnrealEditor и UBT не было.
- **Рендер.** На каждом клиенте High, SP 100, 1920×1080, offscreen, по 30 FPS на клиента (`-ClientFps 30`), `-RequireRenderReference -RequireShotCaptured -ClientPerf`. Оба клиента получали флаги `-ArtPreviewHeroesV2 -ArtPreviewDiorama`.
- **Фон GPU** без наших клиентов, 20 с перед прогонами ([gpu-baseline-20s.csv](gpu-baseline-20s.csv)): p50 32 %, p95 34 %, макс 35 %. Открыты 5 процессов `mcp-for-blender` (MCP-серверы), Blender GUI и UnrealEditor не запущены.
- **Обёртка прогонов** — вне git, `C:/tmp/envmaps-research/p3/live/live_run.py` (sha256 `0da2723a…c80f`). Она делает то же, что `t52_art3_live.py k3`:
  - снимает nvidia-smi: GPU раз в 500 мс и pmon;
  - копирует логи клиентов с заменой кода комнаты на `<redacted>`;
  - пишет `perf.json` и `run-record.json`;
  - для неудачной попытки пишет `attempt.json`.

  Боковые файлы `*.evidence.json` для строгой классификации пишет `C:/tmp/envmaps-research/p3/live/sidecars.py` (`348efc83…6c1c`).

## 2. Правки скриптов на этом этапе (рабочее дерево, не закоммичены)

1. **`tools/s08/run-phase2-demo.ps1`.** Первая попытка K1 ([k1/failed-20261001-082328/attempt.json](k1/failed-20261001-082328/attempt.json)) упала на гейте скрипта, а не клиента: `host zone '' expected  cells: no zone line`.
   - Причина: у профиля карты нет `match.zoneKeys`, и `@($null)` в PowerShell даёт один пустой ключ. Цикл сеточных зон стал `@($ArtBoard.match.zoneKeys | Where-Object { $_ })`. Зоны карты гейтятся своими строками `board map zone key=… (painted`.
   - Итоговая строка вывода для карты теперь печатает пространства и связи вместо пустого «zone cells».
   - Клиентские трассы этой попытки полные: все строки карты на месте, комната ABORTED.
2. **`tools/s09/run-combat-demo.ps1`.** На доске-карте с `-ArtPreviewDiorama` добавлен тот же гейт окружения, что в phase2: `ARTPREVIEW envlayout map=<map> … missingMeshes=0 … combinedBudgetOk=1 … boardId=<id> … status=ok` и `envlayout ground … status=ok` на обоих клиентах.
3. **Новый `tools/s09/xcheck_graph_duel.py`** — независимая перекрёстная проверка дуэли, только чтение (§5).
   - `verify_graph_duel.py` ищет дальние атаки по строкам драйвера S09AUTO.
   - Этот инструмент классифицирует **каждую** серверную строку `ATTACK_INITIATED` по позициям атакующего и цели.

Парсер PowerShell: 0 ошибок в обоих скриптах.

## 3. Команды

Все команды запускались из `C:\tmp\wt-envmaps\backend`. Обёртка вызывает `node ..\tools\s09\run-with-env.cjs powershell -NoProfile -ExecutionPolicy Bypass -File <скрипт> -EvidenceDir <каталог> …`.

```
# K1 (дважды: первая попытка упала на гейте скрипта, §2)
python C:/tmp/envmaps-research/p3/live/live_run.py --kind phase2 --label k1-marmoreal --evidence-dir <этот каталог>\k1 -- \
  -Api http://localhost:3120/graphql -ArtPreviewBoardId c121b47f8d6eb28daccb76d05 -ArtPreviewHeroesV2 -ArtPreviewDiorama \
  -ArtPreviewShotAfter 36 -RunSeconds 50 -ClientFps 30 -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf
# K3 до GAME_OVER (один прогон)
python C:/tmp/envmaps-research/p3/live/live_run.py --kind combat --label k3-marmoreal --evidence-dir <этот каталог>\k3 -- \
  -Api http://localhost:3120/graphql -ArtPreview -FullHd -ArtPreviewBoardId c121b47f8d6eb28daccb76d05 -ArtPreviewHeroesV2 \
  -ArtPreviewDiorama -ClientFps 30 -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf \
  -RequireGameOver -RunSeconds 480
# проверка графа (без GPU), из корня репозитория
python tools/s09/verify_graph_duel.py --host-trace <K3>/combat-client-host.trace.log --joiner-trace <K3>/combat-client-joiner.trace.log \
  --require-moves --require-ranged --require-result --json <K3>/graph-duel-check.json
python tools/s09/xcheck_graph_duel.py --host-trace <K3>/combat-client-host.trace.log --joiner-trace <K3>/combat-client-joiner.trace.log \
  --json <K3>/graph-duel-xcheck.json
# классификация кадров
python tools/art/classify_evidence.py --require packaged-live --strict --render-reference --require-captured <K1> <K3>
```

## 4. Прогоны

| Прогон | Каталог | Длит., с | Комната | seq хост / присоед. | RENDER ref=1 (SHOT) хост · присоед. | Кадры |
|---|---|---|---|---|---|---|
| K1, попытка 1 | [k1/failed-20261001-082328](k1/failed-20261001-082328/) | 64,3 | ABORTED (проверено) | — | — | не опубликованы (гейт скрипта, §2) |
| **K1** | [k1/run-20261001-082404](k1/run-20261001-082404/) | 64,4 | ABORTED (проверено) | 1 / 1 | 1/1 · 1/1 | 2 |
| **K3 + GAME_OVER** | [k3/combat-20261001-082546](k3/combat-20261001-082546/) | 107,4 | FINISHED, победа хоста (Medusa) | 129 / 129 | 14/14 · 15/15, вне эталона 0 | 8 опубл. |

В K3 есть по одному кадру `s09-lobby-return.png` на клиента после выхода из комнаты (`profile=-`). Скрипт их не гейтит и не публикует, как в прецеденте GD-058.

### 4.1 K1: гейты (хост и присоединившийся, строки трассы)

```
ARTPREVIEW board profile=marmoreal-original match=boardId board=7x6 boardId=c121b47f8d6eb28daccb76d05 surface=map-image light=marmoreal-night artFixture=0 map=Marmoreal
ARTPREVIEW map-image assets map=Marmoreal mi=MI_Marmoreal_MapBoard material=M_MapBoard bc=T_Marmoreal_Map_BC_4K mask=T_Marmoreal_Map_GameMask_4K boundBc=1 boundMask=1 sdf=-1 id=-1
ARTPREVIEW board active profile=marmoreal-original 7x6 surface=map-image map=Marmoreal spaces=31 links=42 starts=4 zoneKeys=8 multizone=21 triple=7 obstacles=11 ... zoneMarks=0 lattice=0 ... expectOk=1
ARTPREVIEW board map zone key=blue spaces=14 (painted, no zone marks)        # + brown 7, gray 6, green 14, purple 5, red 4, violet 4, yellow 5
BOARD 7x6 cells | ...
BOARD topology spaces=31 links=42 starts=3:M03,4:M11,1:M13,2:M31 frame=1337x866px uuPerPx=0.6667 radius=42.0uu (default)
ARTPREVIEW lights applied profile=marmoreal-night directional=1 shadow=1 points=1 pointShadows=0 budgetOk=1
ARTPREVIEW envlayout ground map=marmoreal mode=runtime strips=4 material=MI_EnvGround_Marmoreal ... splatCovers=1 areaUU2=885246 status=ok
ARTPREVIEW envlayout map=marmoreal props=17 lights=5 missingMeshes=0 ... intrusions=0 outsideTray=0 outsideKit=0 shadowCasters=17 profilePoints=1 combinedPoints=6 combinedBudgetOk=1 ... status=ok
ARTPREVIEW envlayout tray map=marmoreal source=layout outerHalf=780.0x470.0 offsetY=-45.0 frameHalf=469.7x312.7 mesh=T2 t2Top=780.0x470.0 mismatchUU=0.0
ARTPREVIEW diorama tray=/Game/PipelineCandidates/TableBase/T2/SM_TableBase_T2.SM_TableBase_T2 mi=MI_TableBase_T2 surface=map-image ... kind=T2 ...
CAMERA extents source=map-image half=445.7x288.7 dist=2340.2 fit=1872.2 k1Mul=1.250
SHOT camera dist=2340.2 target=2340.2 overview=2340.2 errPct=0.000 focusErr=0.00 settled=1 zoom=1.00
ARTPREVIEW heroesV2 summary fighters=6 mapped=6 v2=6
ARTPREVIEW reachable rings cells=8 placed=1 radiusUU=36 segments=12                     # хост
ARTPREVIEW selection ownHero=1 selected=1 fighter=Medusa reachable=9 fighterId=f-0-hero  # хост
RENDER tag=SHOT rhi=D3D12 featureLevel=SM6 ... gi=lumen ... refl=lumen ... preset=High screenPct=100.0 ... profile=marmoreal-night ... reference=1
SHOT captured file=phase2-board-host-1920x1080.png frame=1078 px=1920x1080 sha256=c5a79db0… order=BGRA saved=1
```

- **Обе трассы.** На каждой стороне по одной строке профиля, активной доски, `BOARD 7x6`, топологии, света, окружения, земли, подноса T2, `CAMERA extents`, `heroesV2` и `SHOT captured`. Строк зон карты по 8.
- **Присоединившийся.** `WS DROPPED` → `WS reconnected`, `FIGHTERS synced n=6`, сходимость `seq=1`.
- **Строки `missing`** — только `missing=-` и `missingMeshes=0` / `missingKeys=0`. `sdf=-1 id=-1`: текстуры `/Game/EnvMaps/Data` не куются по замыслу (`DirectoriesToNeverCook`), как в бенче.
- **Пиксельный гейт** `artcheck`: хост и присоединившийся `pass`, освещённая доска 0,988 / 0,988 при пороге 0,75.
- **Кадры:** [хост](k1/run-20261001-082404/phase2-board-host-1920x1080.png), [присоединившийся](k1/run-20261001-082404/phase2-board-joiner-1920x1080.png). Оба 1920×1080, видны карта, периметр окружения, поднос и 6 фигур.

### 4.2 K3: дуэль до GAME_OVER

- **Гейты доски** на обоих клиентах: `BOARD 7x6`, `BOARD topology spaces=31 links=42`, активная строка карты с `expectOk=1`, свет, а также новый гейт окружения и земли (§2). Камера во всех 29 кадрах эталона `dist=2340.2 … zoom=1.00`.
- **Герои v2 и клипы** у обоих клиентов одинаковые: 6/6 фигур, Idle на 6/6, LungeAttack 9, HitReact 13, DeathSettle 1. CUE урона: по 14 у каждого клиента.
- **Маркеры боя** у присоединившегося: окна защиты и разрешения, раскрытие, результат. Вывод скрипта: `revealProof: present` (приватность до раскрытия: 0 пикселей раскрытия).
- **Сходимость:** `host maxSeq=129 joiner maxSeq=129`.
- **GAME_OVER:** `GAME_OVER gate ok: row FINISHED, winner seat=host (host VICTORY, joiner DEFEAT), result seq host=129 joiner=129`, у строки игры правильный `boardId`. `cleanup: game … already terminal (FINISHED)`, поле `gameOver` в манифесте заполнено.
- **Кадры:**
  - хост: `s09-combat-result.png`, `s09-damage-combat.png`;
  - присоединившийся: `s09-combat-defense-open.png`, `-resolve-window`, `-resolve-revealed`, `-result`, `s09-damage-number.png`, `s09-damage-combat.png`.

## 5. Доказательство игры по графу

Топология: `backend/prisma/fixtures/boards/marmoreal.topology.json`. Фикстура выбрана по `boardId` строки GAME_CREATED. Серверный журнал `GameAction` игры `cmuoz228f003pwi9gpheqn7fx` (132 строки) читался через `docker exec codex-s09-postgres psql`, только чтение, без учётных данных.

| Проверка | `verify_graph_duel.py` ([json](k3/combat-20261001-082546/graph-duel-check.json)) | `xcheck_graph_duel.py` ([json](k3/combat-20261001-082546/graph-duel-xcheck.json)) |
|---|---|---|
| (a) ходы манёвра по связям | 28 ходов, 32 шага, `allLinked=true` | 28 ходов, 32 шага, нарушений 0; рёбра фикстуры = `spaces[].links` |
| перемещения не манёвром | 1: seq 39 `f-1-sk0` (Merlin) M24 → M02, граф. расстояние 7 | то же, `linked=false` |
| (b) дальняя атака по несмежной цели в общей зоне | 3 (`attackDoneSeq` 57, 60, 69) | 3 из 9 атак: seq 57, 60, 69 |
| атаки, похожие на нелегальные | — | 0 |
| (c) итог | VICTORY / DEFEAT, строка GAME_ENDED | `RESULT seq=129` VICTORY (хост) / DEFEAT (присоед.), GAME_ENDED 1 |
| код выхода с `--require-*` | 0 | 0 |

**(a) Ходы.** Каждый путь серверного `maneuver` проверен шаг за шагом от позиции бойца (по строкам `CUE move` обоих клиентов) по рёбрам фикстуры. Конец каждого пути совпадает с CUE этого seq.
- Пример: seq 3, Medusa M13 → M20 → M21 → M25.
- CUE-перемещений 29. Оба клиента видели 28 из них, расхождений в общих 0.
- Перемещение seq 3 есть только у хоста: присоединившийся вошёл в комнату позже, и его первый снимок уже `seq=3`.

**Перемещение не манёвром** (seq 39) — эффект карты. Строка `GameAction` 39: `CARD_PLAYED` / `resolvePendingEffect` с `effectId` карты защиты `cmuhgvgi000omwi9gbn3wr8kb-after-0-p0`, `fighterId=f-1-sk0`, `x=1, y=0`. Эта карта — **Bewilderment** (King Arthur, DEFENSE), её сыграли в seq 36. Это PLACE после боя, а не ход по графу, поэтому нарушением не считается.

**(b) Дальняя атака (GAP-023 / ENV-O6).** Атакующий во всех трёх случаях — Medusa (`f-0-hero`, ranged) на M22, цель — King Arthur (`f-1-hero`) на M14.
- M22 и M14 **не связаны** в фикстуре, но делят зоны **blue** и **green**.
- Трасса хоста:
  ```
  S09AUTO ranged target attacker=f-0-hero at=M22 target=f-1-hero at=M14 via=shared-zone (not linked)
  S09AUTO attack (attacker=f-0-hero target-set card-set)
  ATTACK sent
  ATTACK done seq=57 (merge) phase=COMBAT
  ```
  Те же строки повторяются для seq 60 и 69.
- Сервер принял все три: строки `ATTACK_INITIATED` 57 / 60 / 69, `attackerId=f-0-hero`, `targetId=f-1-hero`.
- Остальные 6 атак шли по связи: seq 35 M23–M24, seq 45 гарпия M08–M14, seq 81–118 M17–M14.
- Merlin в этой дуэли не атаковал: присоединившийся по плану только защищается и разрешает бой. Дальняя атака доказана на Medusa.
- Драйвер к дальней атаке не принуждался, правок C++ не понадобилось.

**(c) Итог.** Хост VICTORY, присоединившийся DEFEAT, `RESULT seq=129` на обоих. Строка игры FINISHED, `winnerId` — место хоста, `boardId` Marmoreal. Есть строка `GAME_ENDED`.

## 6. Производительность (запись, не ACC-022)

Пометка: **dev-PC (RTX 4090), не D-07; пара клиентов по 30 FPS; машина не полностью тихая (фон 28–35 %)**. FPS — из `PERF window` (окна по 5 с) в трассах клиентов. GPU — nvidia-smi раз в 500 мс в окне, когда живы оба клиента (`perf.json` каждого прогона, CSV `nvidia-smi-gpu.csv`).

| Прогон | Клиент | Окон | FPS, медиана / мин. по окнам | Кадр p95 (макс. по окнам), мс | gpuMs p50 (медиана) / p95 (макс.) | hitches > 50 мс | Итог `afterWarmup` |
|---|---|---|---|---|---|---|---|
| K1 | хост | 9 | 30,00 / 28,68 | 33,33 | 2,25 / 3,87 | 2 | 29,80 FPS, p95 33,33, gpuMs p50 2,26 |
| K1 | присоед. | 9 | 30,00 / 28,71 | 33,33 | 2,25 / 2,80 | 2 | 29,82 FPS, p95 33,33, gpuMs p50 2,26 |
| K3 | хост | 17 | 28,77 / 24,28 | 33,34 | 2,32 / 4,05 | 15 | — * |
| K3 | присоед. | 16 | 29,39 / 24,76 | 33,34 | 2,30 / 3,65 | 16 | — * |

\* После GAME_OVER бой выходит сразу, итоговой строки нет (как в GD-058).

**GPU пары (вся видеокарта, nvidia-smi):**

| Прогон | Выборок | p50 / p95 / макс., % | VRAM макс., МиБ |
|---|---|---|---|
| K1 | 90 | 38 / 43 / 52 | 5537 |
| K3 | 168 | 38 / 42 / 69 | 5543 |

Прецедент Cobble в GD-058: 38 / 43. Прирост над фоном около 6 п.п. на пару.

**Провалы K3** совпадают со съёмкой кадров-доказательств. У хоста 15 `SHOT captured`, у присоединившегося 16; hitches > 50 мс — 15 и 16. Каждый провал около 250 мс и приходится на окно с кадром. Окна без кадров дают ровно 30,00 FPS. В K1 по 2 провала на клиента: окно t=15–20 с (построение доски после старта игры) и окно t=35–40 с, где снят кадр.

## 7. Классификация, приватность, процессы

- **Классификация:** `classify_evidence.py --require packaged-live --strict --render-reference --require-captured` → EXIT 0. Все 10 кадров `packaged-live`, grade `strict`, `rejected=false` ([classify-strict.json](classify-strict.json)).
- **Скан секретов** ([secret-scan.json](secret-scan.json)), 0 совпадений. Проверялось:
  - значения `backend/.env`: пароли и e-mail S08/S09 demo, `JWT_SECRET`, `JWT_REFRESH_SECRET`, `DATABASE_URL`;
  - JWT-подобные строки, `Bearer …` и URL postgres;
  - коды комнат всех трёх игр этого этапа (взяты из `Game.code` изолированной БД) и код из каталога staging неудачной попытки.

  Скан шёл по всему каталогу, включая этот README. Сами значения нигде не печатались.
- **Приватность:** гейты скриптов `run-combat-demo` (идентичности карт не в трассах, нулевые пиксели раскрытия до раскрытия) пройдены. Коды комнат в трассах и логах — `<redacted>`.
- **Ошибки бэкенда** за окно прогонов 08:22–08:31: только ежеминутное `CombatTimeoutService … reading 'combatInfo'` — 11 старых комнат IN_PROGRESS от 27.09, известно по GD-058. Ошибки GraphQL в логе относятся к 07:27, это smoke-тест этапа STACK.
- **Процессы клиентов** — по 2 на прогон: корневой стаб от PowerShell скрипта и внутренний exe от стаба. Их PID в `run-record.json`:
  - K1: 40320 / 36764, 55372 / 47808;
  - K3: 39608 / 43376, 22536 / 38580.

  Все завершились сами, проверено по `Win32_Process`. Сэмплеры nvidia-smi остановлены обёрткой. Бэкенд PID 56068, Docker и контейнеры S09 оставлены работать для следующего этапа.
- **Строки падения** в логах клиентов: 0.

## 8. Открытые вопросы

- Дальнюю атаку **Merlin** живой драйвер не производит: у присоединившегося план «защита + разрешение». Для доказательства на Merlin нужен план атаки присоединившегося, отдельная задача. Правило дальности на сервере одно для обоих героев.
- Провалы около 250 мс при каждом `SHOT captured` на K3 — цена съёмки кадров-доказательств, не игры. Для замера ACC-022 нужен прогон без серии кадров или бенч `render_bench.py`.
- Обёртка `live_run.py`, `sidecars.py` и `secret_scan.py` лежат вне git в `C:/tmp/envmaps-research/p3/live/`. При необходимости их можно перенести в `tools/`.
