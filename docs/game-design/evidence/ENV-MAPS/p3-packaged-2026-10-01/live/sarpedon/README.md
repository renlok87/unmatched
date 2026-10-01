# ENV-MAPS P3 · живые packaged-прогоны на оригинальной карте **Sarpedon** (2026-10-01)

**Статус: измерено.** Два packaged-клиента играли по реальному бэкенду на доске Sarpedon, на её графе пространств и с окружением. Сыграны:
- K1 — старт, обрыв WS у присоединившегося и кадры;
- K3 — дуэль до GAME_OVER, два прогона.

Все гейты скриптов пройдены во всех трёх прогонах.

В первом прогоне K3 ходы шли по связям и итог совпал с сервером, но дальней атаки по несмежной цели не было (§5.1). Второй прогон K3 доказал все три пункта, и оба проверяльщика графа это подтвердили:
- ходы шли по связям;
- Medusa четыре раза атаковала несмежную цель в общей зоне;
- итог совпадает с сервером.

Правок C++ и принуждения драйвера не понадобилось.

Все 18 опубликованных кадров — `packaged-live` / `strict` на эталоне рендера. Производительность записана для справки и **не является заявкой ACC-022**. Художественная приёмка этим актом не выставляется: «художественно принято» решает только пользователь.

**Полномочия** (пользователь, дословно):
- порядок шагов, ENV-U11: «Сначала packaged + live, потом правки (Recommended)»;
- свет луны, ENV-U12: «Оставить как есть (Recommended)». Ключ (−55, 30, 0) не трогался;
- параллельные окна: «мне нужно чтобы два окна не сломались при мержде в ветку fix/admin-panel».

Платных шагов не было, коммитов тоже: коммитит оркестратор. На этом этапе не правились ни C++, ни Config, ни скрипты.

## 1. Условия

- **Сборка.** Тот же бинарник этапа PACKAGE, что и на Marmoreal: worktree `C:/tmp/wt-envmaps`, ветка `feat/env-original-maps`, HEAD 9f1c66c4.
  - Внутренний `Unmatched/Binaries/Win64/Unmatched.exe`: sha256 `d0b49f8c3bbee39b59685756a8e5954e56c71b5458e386edcd38ae459c99057a`. Он совпадает с `Binaries/Win64` и пересчитан перед прогонами.
  - Пак `Unmatched-Windows.pak`: `17cb484f…a0d6`.
  - Запись сборки: [package-record.json](package-record.json). Логи `build-g.out.log` («Result: Succeeded») и `uat.log` («BUILD SUCCESSFUL», кук «0 error(s)») лежат вне git в `C:/tmp/envmaps-research/p3/package/`.
  - Хэши exe и паков записаны ещё и в каждом `run-record.json`.
  - Профили читались из пака: `ARTPREVIEW board profiles source=pak sha256=aae181a4…4230`, revision 9.
- **Бэкенд.**
  - `:3120`, PID 56068: `node -r dotenv/config dist/src/main.js` из `C:/tmp/wt-envmaps/backend`. Запущен этапом STACK и не перезапускался. Перед прогонами отвечал на `{ __typename }`, и это единственный слушатель порта.
  - Изолированная БД `codex-s09-postgres` (:55434) и Redis `codex-s09-redis` (:6381).
  - Доска `c7fa64a26c29a0835f2383e63` «Sarpedon · original map»: решётка 9×6, 38 пространств, 61 связь, 4 старта.
- **Учётные данные** берутся из `backend/.env` через `tools/s09/run-with-env.cjs`. Они передаются только в окружение дочернего процесса, в argv их нет.
- **GPU-токен** `C:/tmp/unmatched-gpu.lock`: взят в 08:35:29, снят в 08:41:24 ([gpu-lock.txt](gpu-lock.txt)). До нас токен был свободен. Процессов Unmatched, UnrealEditor, UBT и UAT не было.
- **Рендер.** На каждом клиенте High, SP 100, 1920×1080, offscreen, по 30 FPS на клиента (`-ClientFps 30`), `-RequireRenderReference -RequireShotCaptured -ClientPerf`. Оба клиента получали флаги `-ArtPreviewHeroesV2 -ArtPreviewDiorama`.
- **Фон GPU** без наших клиентов, 20 с перед прогонами ([gpu-baseline-20s.csv](gpu-baseline-20s.csv), 43 выборки): p50 29 %, p95 32 %, макс 34 %. Открыты 4 процесса `mcp-for-blender` (MCP-серверы), Blender GUI и UnrealEditor не запущены.
- **Обёртка прогонов** та же, что на Marmoreal, вне git:
  - `C:/tmp/envmaps-research/p3/live/live_run.py` (sha256 `0da2723a…c80f`);
  - `sidecars.py` (`348efc83…6c1c`) — боковые файлы `*.evidence.json`;
  - `secret_scan.py` (`eb02e2a7…b20a`).

  Обёртка снимает nvidia-smi (GPU раз в 500 мс и pmon), копирует логи клиентов с заменой кода комнаты на `<redacted>` и пишет `perf.json` и `run-record.json`.

## 2. Команды

Все команды запускались из `C:\tmp\wt-envmaps\backend`. Обёртка вызывает `node ..\tools\s09\run-with-env.cjs powershell -NoProfile -ExecutionPolicy Bypass -File <скрипт> -EvidenceDir <каталог> …`.

```
# K1 (один прогон)
python C:/tmp/envmaps-research/p3/live/live_run.py --kind phase2 --label k1-sarpedon --evidence-dir <этот каталог>\k1 -- \
  -Api http://localhost:3120/graphql -ArtPreviewBoardId c7fa64a26c29a0835f2383e63 -ArtPreviewHeroesV2 -ArtPreviewDiorama \
  -ArtPreviewShotAfter 36 -RunSeconds 50 -ClientFps 30 -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf
# K3 до GAME_OVER (дважды, одни и те же аргументы; метки k3-sarpedon и k3-sarpedon-r2)
python C:/tmp/envmaps-research/p3/live/live_run.py --kind combat --label k3-sarpedon --evidence-dir <этот каталог>\k3 -- \
  -Api http://localhost:3120/graphql -ArtPreview -FullHd -ArtPreviewBoardId c7fa64a26c29a0835f2383e63 -ArtPreviewHeroesV2 \
  -ArtPreviewDiorama -ClientFps 30 -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf \
  -RequireGameOver -RunSeconds 480
# проверка графа (без GPU), из корня репозитория, для каждого K3
python tools/s09/verify_graph_duel.py --host-trace <K3>/combat-client-host.trace.log --joiner-trace <K3>/combat-client-joiner.trace.log \
  --require-moves --require-ranged --require-result --json <K3>/graph-duel-check.json
python tools/s09/xcheck_graph_duel.py --host-trace <K3>/combat-client-host.trace.log --joiner-trace <K3>/combat-client-joiner.trace.log \
  --json <K3>/graph-duel-xcheck.json
# классификация кадров
python tools/art/classify_evidence.py --require packaged-live --strict --render-reference --require-captured <K1> <K3 r1> <K3 r2>
```

## 3. Прогоны

| Прогон | Каталог | Длит., с | Комната | seq хост / присоед. | RENDER ref=1 (SHOT) хост · присоед. | Кадры | Граф (a/b/c) |
|---|---|---|---|---|---|---|---|
| **K1** | [k1/run-20261001-083604](k1/run-20261001-083604/) | 66,5 | ABORTED (проверено) | 1 / 1 | 1/1 · 1/1 | 2 | — |
| K3, прогон 1 | [k3/combat-20261001-083733](k3/combat-20261001-083733/) | 102,0 | FINISHED, победа хоста (Medusa) | 96 / 96 | 9/9 · 13/13, вне эталона 0 | 8 | да / **нет** / да ([attempt.json](k3/combat-20261001-083733/attempt.json)) |
| **K3, прогон 2** | [k3/combat-20261001-083933](k3/combat-20261001-083933/) | 102,0 | FINISHED, победа хоста (Medusa) | 122 / 122 | 13/13 · 14/14, вне эталона 0 | 8 | да / да / да |

- `k3/latest-combat.json` указывает на прогон 2.
- Статусы строк `Game` в изолированной БД, только чтение: K1 `cmuozfayg00bzwi9g5834tw5p` ABORTED, K3 r1 `cmuozh82100cvwi9gwjgl1hf8` FINISHED, K3 r2 `cmuozjsll00jbwi9ga7o9h9v5` FINISHED. У всех трёх `boardId=c7fa64a26c29a0835f2383e63`.
- В K3 есть по одному кадру `s09-lobby-return.png` на клиента после выхода из комнаты (`RENDER tag=SHOT … profile=- … reference=0`). Скрипт их не гейтит и не публикует, как в прецеденте GD-058 и на Marmoreal.
- В K1 у каждого клиента по одной строке `RENDER tag=PERF … reference=0`. Это лобби до загрузки доски; все строки `tag=SHOT` имеют `reference=1`.

### 3.1 K1: гейты (хост и присоединившийся, строки трассы)

Вывод скрипта:
```
art board: profile=sarpedon-original size=9x6 light=sarpedon-night legacyCobble=False map=True
art-preview boardId verified against the authoritative game row
convergence: host max applied seq=1 joiner max applied seq=1
cleanup: aborted THIS run's game id=cmuozfayg00bzwi9g5834tw5p status=ABORTED (verified)
```

Строки трассы (хост; у присоединившегося те же):
```
ARTPREVIEW map-image assets map=Sarpedon mi=MI_Sarpedon_MapBoard material=M_MapBoard bc=T_Sarpedon_Map_BC_4K mask=T_Sarpedon_Map_GameMask_4K boundBc=1 boundMask=1 sdf=-1 id=-1
ARTPREVIEW board profile=sarpedon-original match=boardId board=9x6 boardId=c7fa64a26c29a0835f2383e63 surface=map-image light=sarpedon-night artFixture=0 map=Sarpedon
ARTPREVIEW lights applied profile=sarpedon-night directional=1 shadow=1 points=1 pointShadows=0 budgetOk=1
ARTPREVIEW board active profile=sarpedon-original 9x6 surface=map-image map=Sarpedon spaces=38 links=61 starts=4 zoneKeys=6 multizone=4 triple=2 obstacles=16 ... zoneMarks=0 lattice=0 ... expectOk=1
ARTPREVIEW board map zone key=blue spaces=6 (painted, no zone marks)        # + brown 5, green 8, purple 11, red 6, yellow 8
ARTPREVIEW envlayout ground map=sarpedon mode=runtime strips=4 material=MI_EnvGround_Sarpedon ... splatCovers=1 areaUU2=885246 status=ok
ARTPREVIEW envlayout map=sarpedon props=18 lights=5 missingMeshes=0 ... intrusions=0 outsideTray=0 outsideKit=0 shadowCasters=18 profilePoints=1 combinedPoints=6 combinedBudgetOk=1 tray=layout trayApronMismatch=0 ... status=ok
ARTPREVIEW envlayout tray map=sarpedon source=layout outerHalf=780.0x470.0 offsetY=-45.0 frameHalf=469.7x312.7 mesh=T2 t2Top=780.0x470.0 mismatchUU=0.0
ARTPREVIEW diorama tray=/Game/PipelineCandidates/TableBase/T2/SM_TableBase_T2.SM_TableBase_T2 mi=MI_TableBase_T2 surface=map-image ... kind=T2 ...
CAMERA extents source=map-image half=445.7x288.7 dist=2340.2 fit=1872.2 k1Mul=1.250
BOARD 9x6 cells | ...
BOARD topology spaces=38 links=61 starts=3:S03,4:S14,1:S20,2:S32 frame=1337x866px uuPerPx=0.6667 radius=42.0uu (default)
ARTPREVIEW heroesV2 summary fighters=6 mapped=6 v2=6
ARTPREVIEW reachable rings cells=19 placed=1 radiusUU=36 segments=12                       # хост
ARTPREVIEW selection ownHero=1 selected=1 fighter=Medusa reachable=20 fighterId=f-0-hero   # хост
RENDER tag=SHOT rhi=D3D12 featureLevel=SM6 ... gi=lumen ... refl=lumen ... preset=High screenPct=100.0 ... profile=sarpedon-night ... tMaxFPS=30.0 ... reference=1
SHOT camera dist=2340.2 target=2340.2 overview=2340.2 errPct=0.000 focusErr=0.00 settled=1 zoom=1.00
SHOT captured file=phase2-board-host-1920x1080.png frame=1079 px=1920x1080 sha256=7402e25a… order=BGRA saved=1
```

- **Обе трассы.** На каждой стороне по одной строке профиля, активной доски, `BOARD 9x6`, топологии, света, окружения, земли, подноса T2, `CAMERA extents` и `heroesV2`. Строк зон карты по 6.
- **Присоединившийся.** `WS DROPPED (test-initiated transport loss)` → `WS reconnected - refetching gameState`, `FIGHTERS synced n=6`, сходимость `seq=1`.
- **Строки `missing`** — только `missing=-` и `missingMeshes=0` / `missingKeys=0`. `sdf=-1 id=-1`: текстуры `/Game/EnvMaps/Data` не куются по замыслу (`DirectoriesToNeverCook`).
- **Пиксельный гейт** `artcheck`: хост и присоединившийся `pass`, освещённая доска 0,9856 / 0,9857 при пороге 0,75.
- **Кадры:** [хост](k1/run-20261001-083604/phase2-board-host-1920x1080.png), [присоединившийся](k1/run-20261001-083604/phase2-board-joiner-1920x1080.png). Оба 1920×1080. Видны карта Sarpedon (берег, река, корабль), периметр окружения (деревья, костры, пушки, борт корабля), поднос T2 и 6 фигур.

### 3.2 K3: дуэль до GAME_OVER

Гейты доски в обоих прогонах на обоих клиентах (по одной строке каждого вида, подсчёт по трассам):
- `BOARD 9x6`;
- `BOARD topology spaces=38 links=61`;
- активная строка карты с `expectOk=1`;
- `lights applied profile=sarpedon-night … budgetOk=1`;
- гейт окружения `envlayout map=sarpedon props=18 … status=ok` и `envlayout ground map=sarpedon … status=ok`;
- `CAMERA extents … dist=2340.2 … k1Mul=1.250`.

Строк `missing` с ненулевым значением 0. Во всех кадрах доски `SHOT camera dist=2340.2`: r1 9 + 13, r2 13 + 14.

| | Прогон 1 | Прогон 2 |
|---|---|---|
| Герои v2 (одинаково у обоих клиентов) | 6/6, Idle 6/6; клипы Idle 21, LungeAttack 5, HitReact 12, DeathSettle 1 | 6/6, Idle 6/6; клипы Idle 29, LungeAttack 11, HitReact 14, DeathSettle 1 |
| Маркеры у присоединившегося | defense, resolve, result, reveal (`rvl=3129`) | defense, resolve, result, reveal (`rvl=3048`) |
| Сходимость | `host maxSeq=96 joiner maxSeq=96` | `host maxSeq=122 joiner maxSeq=122` |
| GAME_OVER | `GAME_OVER gate ok: row FINISHED, winner seat=host (host VICTORY, joiner DEFEAT), result seq host=96 joiner=96` | то же, `result seq host=122 joiner=122` |
| Уборка | `cleanup: game … already terminal (FINISHED)` | то же |

- Поле `gameOver` в манифесте заполнено в обоих прогонах. `WARN: scheme not played this run` — не гейт, как в прецеденте.
- **Кадры** каждого прогона:
  - хост: `s09-combat-result.png`, `s09-damage-combat.png`;
  - присоединившийся: `s09-combat-defense-open.png`, `-resolve-window`, `-resolve-revealed`, `-result`, `s09-damage-number.png`, `s09-damage-combat.png`.

## 4. Доказательство игры по графу

Топология: `backend/prisma/fixtures/boards/sarpedon.topology.json`, 38 пространств, 61 связь, зоны blue, brown, green, purple, red, yellow. Фикстура выбрана по `boardId` строки GAME_CREATED. Серверный журнал `GameAction` читался через `docker exec codex-s09-postgres psql`, только чтение, без учётных данных. `fixtureProblems=[]`, расхождений CUE между клиентами 0.

| Проверка | K3 r1 `verify` / `xcheck` | **K3 r2** `verify` ([json](k3/combat-20261001-083933/graph-duel-check.json)) | **K3 r2** `xcheck` ([json](k3/combat-20261001-083933/graph-duel-xcheck.json)) |
|---|---|---|---|
| (a) ходы манёвра по связям | 16 ходов, 18 шагов, `allLinked=true` / нарушений 0 | 23 хода, 26 шагов, `allLinked=true` | 23 хода, 26 шагов, нарушений 0, конец пути = CUE у всех |
| перемещения не манёвром | 0 | 0 | 0 |
| (b) дальняя атака по несмежной цели в общей зоне | **0** из 5 атак | 4 (`attackDoneSeq` 4, 14, 17, 35) | 4 из 11 атак: seq 4, 14, 17, 35 |
| атаки, похожие на нелегальные | — / 0 | — | 0 |
| (c) итог | VICTORY / DEFEAT, GAME_ENDED | VICTORY / DEFEAT, строка GAME_ENDED | `RESULT seq=122` VICTORY (хост) / DEFEAT (присоед.), GAME_ENDED 1 |
| код выхода | `verify` печатает `GATES FAILED: ranged` | 0, гейты `moves/ranged/result = true` | 0, `ok=true` |

### 4.1 (a) Ходы

Каждый путь серверного `maneuver` проверен шаг за шагом от позиции бойца (по строкам `CUE move` обоих клиентов) по рёбрам фикстуры. Примеры из r2:
- seq 3, Medusa: S20 → S21 → S31 → S35;
- seq 40, Medusa: S35 → S36 → S32;
- seq 30, Merlin: S25 → S22;
- King Arthur ходит S25 ↔ S26 и S32 ↔ S36.

CUE-перемещений 23, оба клиента видели 22 из них. Перемещение seq 3 есть только у хоста: присоединившийся вошёл позже, его первый снимок уже `seq=3`. Перемещений эффектами карт (PLACE и толчков) в этих дуэлях не было.

### 4.2 (b) Дальняя атака (GAP-023 / ENV-O6)

Атакующий — Medusa (`f-0-hero`, ranged) на S35. Цель — King Arthur (`f-1-hero`) на S32 (seq 4, 14, 17), затем на S25 (seq 35).
- По фикстуре: `S35–S32` **не связаны**, общая зона **purple** (S35: purple; S32: purple). `S35–S25` **не связаны**, общая зона **purple** (S25: yellow, brown, purple).
- Трасса хоста, r2:
  ```
  S09AUTO ranged target attacker=f-0-hero at=S35 target=f-1-hero at=S32 via=shared-zone (not linked)
  S09AUTO attack (attacker=f-0-hero target-set card-set)
  ATTACK done seq=4 (apply) phase=COMBAT
  ```
  Те же строки повторяются для seq 14 и 17, затем `… target=f-1-hero at=S25 via=shared-zone (not linked)` → `ATTACK done seq=35`.
- Сервер принял все четыре: строки `ATTACK_INITIATED` с `attackerId=f-0-hero`, `targetId=f-1-hero` (`serverRow=true` в обоих JSON).
- Пятый кандидат в `graph-duel-check.json` (`attackDoneSeq=null`, `ok=false`) — строка выбора цели S35→S25 в 03:40:14 без немедленной атаки. Medusa затем сходила S35 → S36 → S32 (seq 40) и атаковала уже по связи S32–S25 (seq 49). Это не нарушение: кандидат просто не исполнен, гейт считает только исполненные.
- Остальные 7 атак r2 (seq 49–120) — Medusa с S32 на S25, по связи.

**Почему не хватило прогона 1.** Драйвер дважды выбрал цель через общую зону: `at=S35 … at=S32` и `at=S36 … at=S25`. Оба раза атаку он отложил, в трассе `S09AUTO attack deferred - no may-boost card in hand`, и подошёл по связям. Все 5 атак r1 (seq 55–94) шли с S32 на S25, по связи. Это зависит от раздачи и добора. В r2 позиция та же (после манёвра S20 → S35, цель на S32), но после манёвра драйвер атаковал сразу, уже на первом ходу (03:39:56, seq 4). По плану live-run второй прогон K3 запускается без изменений, а правка C++ (токен `ranged` в `-S09Combat`) — только если и он не даст (b). Правка не понадобилась.

Merlin в этих дуэлях не атаковал: присоединившийся по плану только защищается и разрешает бой. Дальняя атака доказана на Medusa, как и на Marmoreal.

### 4.3 (c) Итог

В обоих прогонах хост VICTORY, присоединившийся DEFEAT, `RESULT seq` одинаковый на обоих клиентах (96 и 122). Строка игры FINISHED, `winnerId` — место хоста, `boardId` Sarpedon. Есть одна строка `GAME_ENDED`.

## 5. Производительность (запись, не ACC-022)

Пометка: **dev-PC (RTX 4090), не D-07; пара клиентов по 30 FPS; машина не полностью тихая (фон 29–34 %)**. FPS — из `PERF window` (окна по 5 с) в трассах клиентов. GPU — nvidia-smi раз в 500 мс в окне, когда живы оба клиента (`perf.json` каждого прогона, CSV `nvidia-smi-gpu.csv`).

| Прогон | Клиент | Окон | FPS, медиана / мин. по окнам | Кадр p95 (макс. по окнам), мс | gpuMs p50 (медиана) / p95 (макс.) | hitches > 50 мс | SHOT captured | Итог `afterWarmup` |
|---|---|---|---|---|---|---|---|---|
| K1 | хост | 9 | 30,00 / 28,41 | 33,34 | 2,17 / 3,98 | 2 | 1 | 29,78 FPS, p95 33,33, gpuMs p50 2,23 |
| K1 | присоед. | 9 | 30,00 / 28,72 | 33,33 | 2,20 / 2,61 | 2 | 1 | 29,82 FPS, p95 33,33, gpuMs p50 2,23 |
| K3 r1 | хост | 16 | 30,00 / 26,30 | 33,35 | 2,25 / 3,86 | 10 | 10 | — * |
| K3 r1 | присоед. | 15 | 29,97 / 24,90 | 33,34 | 2,29 / 2,85 | 14 | 14 | — * |
| K3 r2 | хост | 16 | 28,77 / 24,61 | 33,34 | 2,25 / 3,91 | 14 | 14 | — * |
| K3 r2 | присоед. | 15 | 28,76 / 24,50 | 33,34 | 2,26 / 3,05 | 15 | 15 | — * |

\* После GAME_OVER бой выходит сразу, итоговой строки нет (как в GD-058 и на Marmoreal).

**GPU пары (вся видеокарта, nvidia-smi):**

| Прогон | Выборок | p50 / p95 / макс., % | VRAM макс., МиБ |
|---|---|---|---|
| K1 | 88 | 39 / 42 / 56 | 5543 |
| K3 r1 | 155 | 39 / 43 / 48 | 5530 |
| K3 r2 | 155 | 39 / 43 / 54 | 5555 |

Для сравнения: Marmoreal K1/K3 — 38 / 43 и 38 / 42; Cobble в GD-058 — 38 / 43. Прирост над фоном около 10 п.п. на пару.

**Провалы.** Число hitches > 50 мс на каждом клиенте K3 совпадает с числом `SHOT captured` (10/14 и 14/15). Это цена съёмки кадров-доказательств, а не игры. В K1 по 2 провала на клиента: окно построения доски после старта и окно t=35–40 с, где снят кадр (max 299,5 / 246,6 мс).

## 6. Классификация, приватность, процессы

- **Классификация:** `classify_evidence.py --require packaged-live --strict --render-reference --require-captured` → EXIT 0. Все 18 кадров (K1 2, K3 r1 8, K3 r2 8) `packaged-live`, grade `strict`, `rejected=false` ([classify-strict.json](classify-strict.json)).
- **Скан секретов** ([secret-scan.json](secret-scan.json)): 79 файлов, 0 совпадений. Проверялось:
  - значения `backend/.env`: пароли и e-mail S08/S09 demo, `JWT_SECRET`, `JWT_REFRESH_SECRET`, `DATABASE_URL`;
  - JWT-подобные строки, `Bearer …` и URL postgres;
  - коды комнат всех трёх игр этого этапа, взятые из `Game.code` изолированной БД (каталоги staging скрипты уже удалили).

  Скан шёл по всему каталогу, включая этот README. Сами значения нигде не печатались.
- **Приватность:** гейты скриптов `run-combat-demo` пройдены (идентичности карт не в трассах, маркеры раскрытия только после раскрытия). Коды комнат в трассах, логах клиентов и `demo.stdout.txt` — `<redacted>`.
- **Ошибки бэкенда** за окно прогонов 08:35–08:42: только ежеминутное `CombatTimeoutService … reading 'combatInfo'` — 11 старых комнат IN_PROGRESS от 27.09, известно по GD-058 и Marmoreal.
- **Процессы клиентов** — по 2 на клиента: корневой стаб `Saved/StagedBuilds/Windows/Unmatched.exe` от PowerShell скрипта и внутренний `Unmatched/Binaries/Win64/Unmatched.exe` от стаба. PID (стаб / внутренний, родитель — PowerShell скрипта):
  - K1: 13084 / 45924, 50156 / 59588 (родитель 41092);
  - K3 r1: 37112 / 49392, 7528 / 59164 (родитель 33344);
  - K3 r2: 46124 / 52588, 57824 / 58296 (родитель 6004).

  Все завершились сами, проверено по `Win32_Process`: процессов Unmatched и nvidia-smi после этапа нет. Сэмплеры nvidia-smi остановлены обёрткой.
- **Оставлены работать** для следующего этапа: бэкенд PID 56068, Docker Desktop и контейнеры S09.
- **Строки падения** в логах клиентов: 0.

## 7. Открытые вопросы

- Дальнюю атаку **Merlin** живой драйвер не производит: у присоединившегося план «защита + разрешение». Для доказательства на Merlin нужен план атаки присоединившегося, отдельная задача.
- Дальняя атака Medusa на Sarpedon зависит от раздачи. В r1 драйвер отложил атаку без карты усиления, и (b) не случилась, в r2 случилась 4 раза. Для детерминированного доказательства в будущих прогонах можно сделать opt-in токен `ranged` в `-S09Combat` (план live-run, шаг 4, fallback). Сейчас он не понадобился.
- Провалы около 250 мс при каждом `SHOT captured` на K3 — цена съёмки кадров-доказательств. Для замера ACC-022 нужен прогон без серии кадров или бенч `render_bench.py`.
- Обёртка `live_run.py`, `sidecars.py` и `secret_scan.py` лежат вне git в `C:/tmp/envmaps-research/p3/live/`. При необходимости их можно перенести в `tools/`.
