# Прогон H — живая приёмка (2026-10-05)

Журнал — [H-2026-10-05.md](../../../../de-footage/task/runs/H-2026-10-05.md), раздел «Живая приёмка». Задачи R-01…R-05
(журнал эффектов боя на сервере, строки эффектов в постановке боя, догоняние очереди показа, плашки ходов в одной
ISM, проверка кадра в тесте кликов).

## Упаковка

Одна упаковка на HEAD `e35c69f1` (R-01…R-05 внутри):

```
node tools/s08/build-editor.cjs Unmatched Win64 Development -Project=<repo>/unreal/Unmatched/Unmatched.uproject -WaitMutex -NoXGE -MaxParallelActions=4
node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development -Project=… -WaitMutex -NoXGE -MaxParallelActions=6
tools/s08/package-client.ps1 -SkipBuild
```

- Игровая цель — `Result: Succeeded`; редактор уже был собран (R-05). UAT — `BUILD SUCCESSFUL`, `UAT_EXIT=0`, ошибок в
  логе нет. `-SkipBuild` после отдельной сборки игровой цели на 4 потоках — из-за ловушки PCH, на которую попал R-04.
- `BuildStamp.json`: `commit e35c69f1…`, `sourceHash 9f78cd93…`, `skipBuild true`. sha256 внутреннего exe
  (`Unmatched/Binaries/Win64/Unmatched.exe`) — `91bb5c4e…`.
- Бэкенд: в контейнере `unmatched-backend` уже стоял `dist` с R-01 (`combat-effect-log.js`, `lastCombat` в
  `game-action-executor.service.js`); после R-01 бэкенд не менялся. `/health` ok.

## Живые бои двух клиентов до GAME_OVER

Ключи — как в [CLOSEOUT §6](../../../../de-footage/task/runs/CLOSEOUT-2026-10-04.md) и
[FINAL-PKG](../../2026-10-04/FINAL-PKG/README.md). Аккаунты — засеянные `pro@` (хост) и `veteran@` (соперник) из
`backend/prisma/seed.ts`, только через окружение процесса (`S09_DEMO_*`), в файлы не попадали (трассы проверены).

```powershell
tools/s09/run-combat-demo.ps1 -Api http://localhost:3000/graphql -ArtPreview -FullHd `
  -ArtPreviewBoardId <board> -ArtPreviewHeroesV2 -ArtPreviewDiorama -ClientFps 30 `
  -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf -RequireGameOver `
  -RunSeconds 480 -JoinerAttack -HostScheme -ClientExtraArgs '<extra>' -EvidenceDir docs/game-design/evidence/DE-FOOTAGE/2026-10-05/H/<map>
# Marmoreal: <board>=c121b47f8d6eb28daccb76d05, <extra>=-ConceptPaste+-S08MovePlates+-S09SchemeQuiet=3.5
# Sarpedon:  <board>=c7fa64a26c29a0835f2383e63, <extra>=-S08MovePlates+-S09SchemeQuiet=3.5
# контроль без догоняния: Marmoreal, <extra> + '+-S09CatchupQueued=0+-S09CatchupLagMs=0'
python tools/s08/cue_contract/cue_contract.py check-trace <trace> --min-ms-cue 1 --min-combat 1 --min-death 1 --min-sound 1 [--min-effect-lines 1]
```

| Прогон | Папка | Итог | check-trace (хост / соперник) | Бои | Строк эффектов (журнал) | Догоняние | Удар → экран результата |
|---|---|---|---|---|---|---|---|
| Marmoreal original, `-ConceptPaste` | [marmoreal/combat-20261005-221837](marmoreal/combat-20261005-221837/manifest.json) | GAME_OVER seq 58, Medusa | PASS / PASS | 8 | 12, `src=log` у всех 8 | hurry 6, cut 3, replace 4; max queued 4 | смерть от схемы (не бой): `staged=0`, GAME_OVER → экран 2667 мс |
| Sarpedon original | [sarpedon/combat-20261005-222331](sarpedon/combat-20261005-222331/manifest.json) | GAME_OVER seq 73, Medusa | PASS / PASS | 12 | 14, `src=log` у всех 12 | hurry 9, cut 6, replace 5; max queued 4 | **3167 мс** на обоих (`hit_to_screen`) |
| Marmoreal, догоняние K/T = 0 | [marmoreal-catchup-off/combat-20261005-222614](marmoreal-catchup-off/combat-20261005-222614/manifest.json) | GAME_OVER seq 42 | PASS / PASS, `--min-effect-lines 1` PASS | 7 | 11 | `config queued=0 lagMs=0`; hurry 6 (`reason=combat`), cut 0 | **3167 / 3168 мс** |

Первая попытка Sarpedon (`s09-combat-20261005-222108`, во временной папке, в доказательства не взята) упала на
гейте скрипта: в трассе соперника нет `SHOT captured file=s09-damage-number.png`. Два кадра запрошены в одном кадре
движка (frame 530: `s09-damage-number` и `s09-combat-resolve-window`), второй `FScreenshotRequest` заменил первый.
Это гонка обвязки кадров, не код прогона (см. дефект Д-1 в журнале). check-trace той попытки — PASS на обоих
(13 боёв). Повтор прошёл.

### R-01 / R-02 — строки эффектов боя

- `COMBAT-LOG … src=log` у каждого боя всех трёх партий, и строки `COMBAT-LOG` хоста и соперника совпадают (12 / 14 / 11
  строк). C8 зелёный на всех шести трассах.
- **F-01 вживую.** Смертельный бой Sarpedon seq 73 (`lines=1`, догоняние после GAME_OVER выключено) на обоих клиентах:
  `flip 620 → read 1000 → effect i=1 600 → pause 300 → lunge`, `total=4533` = 3933 + 600. То же в контрольной партии
  (seq 42, `total=4533`).
- **Кадр блока EFFECTS на обоих клиентах:** [marmoreal host](marmoreal/combat-20261005-221837/host/s09-damage-combat.jpg)
  и [marmoreal joiner](marmoreal/combat-20261005-221837/joiner/s09-damage-number.jpg) — бой seq 7, одна и та же строка под
  картой атаки. [sarpedon joiner](sarpedon/combat-20261005-222331/joiner/s09-damage-number.jpg) — бой seq 12, строки под
  картой атаки и под картой защиты соперника. Служебных заметок движка нет.
- **Приватность на сервере** (GraphQL `gameState` готовой партии Sarpedon от лица каждого места): `metadata.lastCombat`
  одинаков у обоих (seq 73, n 12, одна запись `AFTER/DAMAGE/APPLIED`), поля `hidden` нет ни у одного.

### R-03 — догоняние

- `CATCHUP config queued=3 lagMs=1500` в обеих трассах по умолчанию; C10 зелёный на всех шести трассах.
- Карточки боя не отстают от строки статуса больше допуска: максимум 4 более новых снимка (тогда `cut reason=queue`),
  наибольшее отставание на момент действия — 2902 мс (Sarpedon seq 17, cut) при `MaxLeadMs` 3592 мс.
  Кадры: [marmoreal host](marmoreal/combat-20261005-221837/host/s09-damage-combat.jpg) — постановка seq 7 при строке
  статуса seq 9; [sarpedon joiner](sarpedon/combat-20261005-222331/joiner/s09-damage-number.jpg) — постановка seq 12,
  а сверху уже окно защиты seq 14 (короткая версия, `reason=combat`).
- С автоклиентами догоняние укорачивает почти каждый бой (Marmoreal 8 из 8, Sarpedon 11 из 12; полный только смертельный).
  Наблюдение О-1 в журнале.

### DE-019 — экран результата

Удар → экран результата 3167 мс (Sarpedon, оба клиента) и 3167 / 3168 мс (контроль), как в FINAL-PKG (3167 мс). В
партии Marmoreal героя добила схема хоста (1 урон, вне боя): `CUE death … staged=0`, `RESULT screen wait=2667`.

## MS-AT-41 — draw calls плашек на этой упаковке

Тем же способом, что в B и R-04 ([ms-at41-one-ism-2026-10-05](../../ms-at41-one-ism-2026-10-05/README.md)):
`render_bench.py run`, варианты `dx12-lumen-high-v2` (×2) и `dx12-lumen-high-v2-moveplates` (сцена 2 ×2, сцена 0 ×1),
виды K1 и K2x1,6, Marmoreal без `-ConceptPaste`, под замком `C:/tmp/unmatched-gpu.lock`. Вывод — `C:/tmp/h-accept/bench`,
сводка — [ms-at41/ms-at-41-acceptance.json](ms-at41/ms-at-41-acceptance.json) (скрипт [ms-at41/dc_summary.py](ms-at41/dc_summary.py)).

| Карта, вид | Draw calls: база → плашки | Δ приёмка | Δ R-04 (`9c8f92b7`) | Δ B (до R-04) | Δ GPU, мс |
|---|---|---|---|---|---|
| Marmoreal K1 | 435,5 → 437,5 | **+2,0** | +1,7 | +8 | −0,005 |
| Marmoreal K2x1,6 | 347,8 → 313,4 | −34,4 | −34,1 | −28,5 | +0,005 |
| Sarpedon K1 | 480,8 → 482,8 | **+2,0** | +2,0 | +8 | +0,015 |
| Sarpedon K2x1,6 | 474,2 → 394,8 | −79,4 | −77,1 | −74,0 | −0,005 |

- Порог 7 + 4 × S (S = 0) — **пройдено**. В проходах: Translucency +1,0, `BeginOcclusionTests` +1,0…+1,4.
- Обе повторности базы Sarpedon K1 дали 480,77: шума r1 из R-04 нет.
- 10 запусков, все `done`, кадры `reference: true`. До замера фоновые приложения держали GPU на 10–45 %; draw calls от
  этого не зависят, дельты GPU в шуме (порог +0,30 мс).
- Кадры K1 сцены 2: [marmoreal](ms-at41/marmoreal-plates2-K1.jpg), [sarpedon](ms-at41/sarpedon-plates2-K1.jpg).
  Трасса: `MS-HL build … channels=4 isms=1 instances=124|152`.

## Что просмотрено глазами

Все кадры открыты до отчёта. Доски — Marmoreal original и Sarpedon original. У Marmoreal в живых партиях — нарисованный
задник из концепта (`-ConceptPaste`), у Sarpedon — lit3d (3D-остров, фонари, пушки, водопад). Бенч Marmoreal идёт без
`-ConceptPaste`, как у B, поэтому там 3D P5c (ENV-U16 открыт). Шесть фигур v2: `ARTPREVIEW heroesV2 summary fighters=6
mapped=6 v2=6`, `ARTLOOK art=1 source=default heroes=v2` на всех клиентах. Экран результата «VICTORY / MEDUSA WINS» с
VIEW BOARD и RETURN TO LOBBY.

## Файлы

PNG клиента пересохранены в JPG (q88), трассы `.log` переименованы в `.trace.txt` (`*.log` в `.gitignore`). Хэши в
`manifest.json` относятся к исходным PNG. В контрольной партии оставлены трассы и два кадра; остальные кадры там
такие же, как в основных партиях.
