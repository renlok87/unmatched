# 5c-B1, шаг B1-7: 12 packaged-прогонов трёх досок на пакете 5c-B2 (2026-09-30)

**Статус.** Измерено: прогоны прошли гейты скриптов, все 42 кадра — `packaged-live`, grade `strict`, на эталоне
рендера и со строкой `SHOT captured`. Это технические доказательства. Художественная приёмка не выставляется.
Анализ читаемости по зарегистрированным порогам (B1-8: `t53 analyze`, `rings-rev3`, `t5cb1_exposure_sim validate`,
qa010) — следующий этап, здесь не выполнялся.

**Полномочие.** Пользователь, дословно: 2026-09-28 «Принимай решния сам И делай проект по задачам пока полностью не
доделаешь»; 2026-09-29 «делай все без меня»; 2026-09-30, цель п. 3: «Волна 5c-B: свет доски под фигуры: многие зоны
попадают в допуск только на ступень темнее яркости доски; поворот фигур в игре на +X; новые герои с клипами в игре;
пересъёмка досок с тремя оставшимися неудачами; длинный прогон K2.»

## 1. Что запускалось

- **Checkout:** главный, `fix/admin-panel`, HEAD 11445e7e плюс незакоммиченные правки 5c-B/B1.
- **Один бинарник на все прогоны.** Staged inner `Unmatched/Binaries/Win64/Unmatched.exe`: sha256
  `8d228fae4f60c78002d6009b4fef1c0ec308275146fad5b6244c7a1b846d3b35`. Он совпадает с `Binaries/Win64` и с этапом
  PACKAGE ([package-5cb2.json](package-5cb2.json)). Пак `Unmatched-Windows.pak` — `84e68fbe…347b`.
- **Запись сборки** [build/G1-build.json](build/G1-build.json) составлена на этом этапе по логу этапа BUILD, сама
  сборка не повторялась. Лог: [build/G1-game-build.log](build/G1-game-build.log), `Result: Succeeded`,
  `WITH_LIVE_CODING 1`.
- **Флаги те же, что в r3.** `argv` r3 и новых прогонов совпадают, кроме каталога доказательств. Сверены K1 и K3 Cobble.
  - K1 и зонды: `run-phase2-demo.ps1 -ClientFps 30 -ArtPreviewShotAfter 36 -RunSeconds 50 -ClientPerf
    -ClientCsvFrames 1200 -ArtPreviewMedusaVariant face-neck-v2 -RequireRenderReference -RequireShotCaptured`;
    для зондов добавлены `-ArtPreviewIconProbe -ArtPreviewIconSize 24|48`.
  - K3: `run-combat-demo.ps1 -ArtPreview -FullHd -ClientFps 30 -ArtPreviewMedusaVariant face-neck-v2 -RunSeconds 240
    -ClientRenderPreset High -RequireRenderReference -ClientPerf -RequireShotCaptured`.
  - Флагов героев v2 и подноса нет: так прогоны сопоставимы с r3.
- **Бэкенд — по процедуре прошлых актов.**
  - Docker Desktop запущен скрыто. Перед этим устаревшие AF_UNIX-сокеты отодвинуты переименованием, ничего не удалено:
    `%LOCALAPPDATA%\Docker\run` → `run.stale-5cb2`, `docker-secrets-engine` → `.stale-5cb2`.
  - Контейнеры `codex-s09-postgres` и `codex-s09-redis` были в состоянии Exited и запущены через `docker start`.
  - Бэкенд `:3120` (PID 42656): `node -r dotenv/config dist/src/main.js` из `backend/` арт-worktree. Worktree
    только читается.
  - Демо-учётки `S08_DEMO_*` передаются из того же `.env` через `UNMATCHED_BACKEND_ENV`, только в окружение
    дочернего процесса. В `.env` главного checkout их нет.
- **Пороги не менялись.** [t5cb-thresholds.json](t5cb-thresholds.json) по содержимому равен коммиту acc97aee: sha256
  блоба с LF `6eb9b750…fe0a`, рабочая копия с CRLF — `33c6155e…6203`. Реестр досок `S08ArtBoardProfiles.json` rev 5
  (`1ecc1e92…`) — тот же, что `profilesSha256` в строке RENDER каждого кадра.

## 2. Итог по прогонам

Сводка: [packaged/runs-summary.json](packaged/runs-summary.json) (`tools/art/t5cb2_live_summary.py`). Классификация:
[packaged/classify-live-strict-render-captured.json](packaged/classify-live-strict-render-captured.json).

| Прогон | Каталог | Комната | Длит., с | RENDER ref=1 хост · присоед. | SHOT captured | seq хост/присоед. | CUE урона | FPS хост / присоед. | GPU nvidia-smi пары p50 / p95, % |
|---|---|---|---|---|---|---|---|---|---|
| K1 Cobble | [run-161733](packaged/k1/cobble-5x6/run-20260930-161733/) | ABORTED | 66,6 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,90 / 29,85 | 38 / 42 |
| K3 Cobble | [combat-161855](packaged/k3/cobble-5x6/combat-20260930-161855/) | FINISHED | 101,1 | 13/14 · 13/14 | 14 · 14 | 122/122 | 15 | 29,93 / 30,00 | 39 / 46 |
| зонд 24 Cobble | [run-162037](packaged/k1-probe24/cobble-5x6/run-20260930-162037/) | ABORTED | 66,6 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,91 / 29,92 | 39 / 46 |
| зонд 48 Cobble | [run-162144](packaged/k1-probe48/cobble-5x6/run-20260930-162144/) | ABORTED | 65,9 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,88 / 29,87 | 38 / 41 |
| K1 Sherwood | [run-162251](packaged/k1/sherwood-forest-8x5/run-20260930-162251/) | ABORTED | 67,1 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,85 / 29,82 | 40 / 45 |
| K3 Sherwood | [combat-162400](packaged/k3/sherwood-forest-8x5/combat-20260930-162400/) | FINISHED | 112,3 | 13/14 · 15/16 | 14 · 16 | 136/136 | 20 | 29,98 / 29,99 | 38 / 44 |
| зонд 24 Sherwood | [run-162554](packaged/k1-probe24/sherwood-forest-8x5/run-20260930-162554/) | ABORTED | 66,6 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,84 / 29,85 | 38 / 43 |
| зонд 48 Sherwood | [run-162701](packaged/k1-probe48/sherwood-forest-8x5/run-20260930-162701/) | ABORTED | 66,8 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,84 / 29,86 | 37 / 43 |
| K1 T. Rex | [run-162809](packaged/k1/t-rex-paddock-7x5/run-20260930-162809/) | ABORTED | 65,8 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,86 / 29,88 | 39 / 43 |
| K3 T. Rex | [combat-162916](packaged/k3/t-rex-paddock-7x5/combat-20260930-162916/) | FINISHED | 96,0 | 9/10 · 12/13 | 10 · 13 | 89/89 | 10 | 29,99 / 29,96 | 39 / 45 |
| зонд 24 T. Rex | [run-163053](packaged/k1-probe24/t-rex-paddock-7x5/run-20260930-163053/) | ABORTED | 65,3 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,86 / 29,86 | 38 / 43 |
| зонд 48 T. Rex | [run-163200](packaged/k1-probe48/t-rex-paddock-7x5/run-20260930-163200/) | ABORTED | 67,0 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,82 / 29,89 | 38 / 44 |

Пояснения:
- **RENDER.** Каждый кадр доски: `reference=1`, `preset=High`, `screenPct=100.0`, `rhi=D3D12`,
  `shaderPlatform=PCD3D_SM6`, Lumen GI/отражения, `exposure=fixed-histogram expMin=4.14106 expMax=4.14106 ev100=2.05`
  (критерий B1-8 «RENDER expMin = 4,14106» по трассам выполнен), профили `cobble-probe` / `forest-probe` /
  `paddock-probe`. В K3 один SHOT на клиента вне эталона: это `s09-lobby-return.png` после выхода из комнаты. Доски и
  профиля на нём нет (`noArtProfile`), скрипт его не гейтит и не публикует, как в r3.
- **Бой.** Все три K3 доиграны до GAME_OVER (FINISHED), победила Medusa. seq сошёлся у обоих клиентов. Валидация
  `check_art003`: Cobble — `pass_with_note` (урон применён в COMBAT_RESOLVE, результат закрыт следующим снимком — та же
  заметка, что в r3); Sherwood и T. Rex — `pass_technical_evidence_only`. Гейты маркеров защиты / резолва / результата,
  контроль перестановки и приватности прошли. Схема в этих партиях не сыграна — это WARN скрипта, не гейт.
- **Комнаты.** K1 и зонды: `cleanup: aborted THIS run's game … status=ABORTED (verified)`. K3: `already terminal
  (FINISHED)`.
- **Логи клиентов.** `Unmatched.log` и `Unmatched_2.log` скопированы в `client-logs/` каждого прогона; код комнаты
  заменён на `<redacted>`. Строк падения нет ни в одном прогоне.

## 3. Классификация кадров

`python tools/art/classify_evidence.py <42 PNG> --strict --render-reference --require-captured --require packaged-live`
→ код 0, **42/42 `packaged-live` / `strict`**, отклонённых нет. Состав: 9 прогонов K1/зондов × 2 кадра
(`phase2-board-host/joiner-1920x1080.png`) и 3 K3 × 8 кадров (хост: `s09-damage-combat`, `s09-combat-result`;
присоединившийся: `s09-combat-defense-open`, `-resolve-window`, `-resolve-revealed`, `s09-damage-number`,
`s09-damage-combat`, `s09-combat-result`).

## 4. Производительность (записано, не оценивалось)

- Статус в каждом `perf.json`: «измерено; dev-PC (RTX 4090), не D-07; машина не тихая».
- **Фон машины.** Замер фона без клиентов: [packaged/gpu-baseline.json](packaged/gpu-baseline.json), 20 с, GPU p50 28 %,
  p95 32 %. Основные потребители — `claude.exe` ≈ 20 % SM и `dwm.exe` ≈ 14 %. Были открыты Blender GUI :9876/:9877
  (без рендера), параллельно шла только работа с документами (ENV-0). Редактор UE закрыт.
- **Нагрузка пары клиентов** по 30 FPS: GPU пары по nvidia-smi — p50 37–40 %, p95 41–46 %. Это вместе с фоном.
- **FPS клиентов** 29,8–30,0 (ограничение `t.MaxFPS 30`). Кадр p50 и p95 — 33,3 мс.
- **gpuMs в трассах** (1,8–2,5 мс, в бою отдельные окна до 4 мс) сняты при ограничении FPS. По AGENTS.md их нельзя
  использовать для сравнения стоимости рендера: для этого есть `render_bench.py`.
- **ACC-022 этими числами не закрывается.**

## 5. Что не сделано на этом этапе

- B1-8 (анализ): доли и форма колец rev 3, край против плитки, зоны rev 3, мультизоны, теги, число урона, иконка и
  K1 p50 по `t5cb-thresholds.json` — следующий этап на этих кадрах.
- Производные gray и deuteranopia не строились.

## 6. Воспроизведение

Вспомогательные функции `k1` и `k3` из `C:/tmp/5cb2-runs/common.sh` (вне git) вызывают:
```text
python tools/art/art004_live_k2.py run --label K1-<board> --evidence-dir <этот каталог>/packaged/k1/<board> \
  --board-id <id> --variant face-neck-v2 --shot-after 36 --run-seconds 50 --client-fps 30 --csv-frames 1200 \
  --build-record <этот каталог>/build/G1-build.json --package-record <этот каталог>/package-5cb2.json \
  --demo-arg=-RequireRenderReference --demo-arg=-RequireShotCaptured [--demo-arg=-ArtPreviewIconProbe \
  --demo-arg=-ArtPreviewIconSize --demo-arg=24|48] --perf-status "…" --concurrent-gpu-users "…"
python tools/art/t52_art3_live.py k3 --label K3-<board> --evidence-dir <этот каталог>/packaged/k3/<board> \
  --board-id <id> --run-seconds 240 --client-fps 30 --build-record … --package-record … \
  --extra-demo-arg=-RequireShotCaptured --perf-status "…" --concurrent-gpu-users "…"
```
Нужны переменная окружения `UNMATCHED_BACKEND_ENV=<арт-worktree>/backend/.env` и один бэкенд на `:3120`.

Вне git: CSV профилировщика и pmon — `unreal/Unmatched/Artifacts/ART004Face/t11-raw/run-2026093016*`,
`t52-combat-2026093016*`. Рабочие каталоги прогонов и лог бэкенда — `C:/tmp/5cb2-runs/`.
