# Прогон I — живая приёмка (2026-10-05)

Журнал — [I-2026-10-05.md](../../../../de-footage/task/runs/I-2026-10-05.md), раздел «Живая приёмка». Задачи:
- I-01 — принятые глифы DE-012 в форме Codex;
- I-02 — вид AB-5…AB-8 по умолчанию: тёплое кольцо хода, ореол сердца, трекер DE, сердце павшего с крестом и штамп;
- I-03 — очередь кадров доказательств.

## Упаковка

```
node tools/s08/build-editor.cjs Unmatched Win64 Development -Project=<repo>/unreal/Unmatched/Unmatched.uproject -WaitMutex -NoXGE -MaxParallelActions=4
node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development -Project=… -WaitMutex -NoXGE -MaxParallelActions=6
tools/s08/package-client.ps1 -SkipBuild
```

Вышло три упаковки вместо одной. Каждая следующая нужна была из-за правки, найденной на предыдущей:

| Упаковка | Что нашла | Правка |
|---|---|---|
| `2bc4280c` (код I-01…I-03) | В партии Marmoreal `check-trace` упал на гейте DS5 у обоих клиентов (дефект Д-1 ниже) | `e011e00c` |
| `e011e00c` | Обе партии прошли (PASS / PASS). Но ни один кадр не попал на штамп «нет защиты»: в трассе `HUD-STAMP` есть, кадра нет | `6627333e` — кадр `s09-no-defense-stamp.png` |
| **`6627333e`** — итоговая | Доказательства ниже сняты на ней | — |

Про итоговую упаковку:
- UAT: `BUILD SUCCESSFUL`, `UAT_EXIT=0`.
- `BuildStamp.json`: `commit 6627333e…`, `sourceHash 4187d73d…`, `skipBuild true`.
- sha256 внутреннего exe (`Unmatched/Binaries/Win64/Unmatched.exe`) — `7fa0505f…`.
- Бэкенд не пересобирался: после R-01 в `backend/` поменялся только комментарий (`066646b6`). `/health` ok.

Партии на первых двух упаковках в доказательства не взяты. Их цифры есть в журнале.

## Живые бои двух клиентов до GAME_OVER

Ключи — как в [CLOSEOUT §6](../../../../de-footage/task/runs/CLOSEOUT-2026-10-04.md) и в [прогоне H](../H/README.md).

Аккаунты — засеянные `pro@` (хост) и `veteran@` (соперник) из `backend/prisma/seed.ts`. Пароли передавались только через
окружение процесса (`S09_DEMO_*`). В трассах строк аккаунтов нет: это проверено.

```powershell
tools/s09/run-combat-demo.ps1 -Api http://localhost:3000/graphql -ArtPreview -FullHd `
  -ArtPreviewBoardId <board> -ArtPreviewHeroesV2 -ArtPreviewDiorama -ClientFps 30 `
  -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf -RequireGameOver `
  -RunSeconds 480 -JoinerAttack -HostScheme -ClientExtraArgs '<extra>' -EvidenceDir docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/<map>
# Marmoreal: <board>=c121b47f8d6eb28daccb76d05, <extra>=-ConceptPaste+-S08MovePlates+-S09SchemeQuiet=3.5
# Sarpedon:  <board>=c7fa64a26c29a0835f2383e63, <extra>=-S08MovePlates+-S09SchemeQuiet=3.5
python tools/s08/cue_contract/cue_contract.py check-trace <trace> --min-ms-cue 1 --min-combat 1 --min-death 1 --min-sound 1
```

Флагов вида HUD в командах нет: всё, что проверено ниже, — вид по умолчанию.

| Партия | Папка | Итог | check-trace (хост / соперник) | Боёв | `HUD-STAMP` | Ореол (`anim=damage glow=1`) | Сердце павшего | Удар → экран |
|---|---|---|---|---|---|---|---|---|
| Marmoreal original, `-ConceptPaste` | [marmoreal/combat-20261005-235827](marmoreal/combat-20261005-235827/manifest.json) | GAME_OVER seq 62, Medusa | PASS / PASS | 10 | seq 54, 62 | 10 / 9 | `HUD-HEART … anim=fallen glyph=cross`, `CUE death … heart=crossed` | 3167 / 3167 мс |
| Sarpedon original | [sarpedon/combat-20261005-235948](sarpedon/combat-20261005-235948/manifest.json) | GAME_OVER seq 31, Medusa | PASS / PASS | 7 | seq 19, 29, 31 | 6 / 6 | то же | 3167 / 3167 мс |

Что ещё показывают трассы обоих клиентов:
- `HUD-TURN config portraits=1 ring=marker-turn-ring heartGlow=1 tracker=de cross=1`.
- `ARTLOOK art=1 source=default heroes=v2 … hud=ring:marker-turn-ring,glow:on,tracker:de,cross:on`.
- `ARTPREVIEW heroesV2 summary fighters=6 mapped=6 v2=6`.
- Строк `legacy(` нет.

### I-03 — очередь кадров

Каждому `SHOT request file=X` соответствует `SHOT captured file=X … saved=1`: Marmoreal 22 / 21, Sarpedon 17 / 19.

Совпадение двух кадров в одном кадре движка очередь разрешила вживую. Соперник в Sarpedon:
`SHOT queued file=s09-combat-result.png frame=529 ahead=0 reason=same-frame` → `SHOT dequeued … frame=530`, кадр
записан. На упаковке `e011e00c` то же случилось у обоих клиентов Sarpedon (кадры 775→776, 603→604).

## Галерея значков (без бэкенда)

```
Saved/StagedBuilds/Windows/Unmatched.exe -windowed -ResX=1920 -ResY=1080 -ForceRes -RenderOffScreen -nosound
  -S08IconGallery -S08IconGallerySize=64 [-S08IconGalleryPortraits]
  -S08IconGalleryShots=<dir> -S08IconGalleryTimes=<ms,...> -S08Trace=<dir>/gallery.trace.log
```

- **[gallery/portraits](gallery/portraits)** — портреты хода поверх галереи, моменты 0 / 120 / 300 / 600 / 1000 / 2000 мс,
  без флагов. Трасса: `ICONGALLERY portraits=2 … ring=marker-turn-ring heartGlow=1 tracker=de cross=1`.
- **[gallery/g-icon-64](gallery/g-icon-64)** — G-ICON (хвост I-01). Галерея сравнивалась с эталоном Python скриптом
  `compare_ue_gallery.py`: 12 моментов × 28 значков = 336 пар.
  - Средняя |Δ| = **0,384** при пороге 0,45. После DE-023 было 0,393.
  - По значкам DE-012: `marker-turn-ring` 0,025, `resource-hp-fallen` 0,072, `marker-x-stamp` 0,077,
    `marker-action-slot-de` 0,371, кандидат `marker-turn-ring-team` 0,126.
  - Подробности — `compare.json`, лист — `compare.png`.

PNG галереи оставлены как есть: на них считается G-ICON, а весят они всего 3 МБ.

## Что просмотрено глазами

Все кадры открыты до отчёта. Сводные листы:
- [sheets/live-portraits.jpg](sheets/live-portraits.jpg) — портреты из живых кадров: первые шесть — Marmoreal, последние
  четыре — Sarpedon;
- [sheets/gallery-portraits.jpg](sheets/gallery-portraits.jpg) — портреты галереи по времени;
- [sheets/live-fallen-heart-stamp-zoom.jpg](sheets/live-fallen-heart-stamp-zoom.jpg) — сердце павшего и штамп в живом
  кадре, ×8 по пикселям.

**Сцена.**
- Доски — Marmoreal original и Sarpedon original.
- У Marmoreal нарисованный задник из концепта: дворец, сакуры, фонари. У Sarpedon — lit3d: остров, водопад, пушки,
  фонари.
- Шесть фигур v2: три гарпии, Медуза, Король Артур, Мерлин.
- Экран результата — VICTORY / DEFEAT, MEDUSA WINS. Финальная доска — FINAL BOARD.

**Вид по умолчанию: всё видно, флагов нет.**
- **Кольцо хода (AB-5).** У портрета ходящего — тёплая вспышка обода. В галерее она идёт жёлтым на 120 мс, оранжевым на
  300 мс и красным на 600 мс. Потом остаётся тлеющий коричневый обод: в галерее с 1000 мс, вживую — в
  `s09-damage-combat`, `s09-damage-number`, `s09-no-defense-stamp` Sarpedon. Кадр начала хода —
  `s09-turn-banner` (обе карты, оба клиента).
- **Трекер DE (AB-7).** Пустой слот — тёмный диск с оранжевым ободом и серым диском-призраком, как в форме Codex.
  Заполненный слот берёт глиф действия: манёвр (фиолетовые следы) и атаку (красная вспышка). Трекер соперника в его ход
  показывает его действия (`s09-damage-combat` хоста Marmoreal: две атаки). Трекер соперника в мой ход скрыт.
- **Ореол сердца (AB-6).** Красный ореол вокруг сердца при уроне: в галерее на 300 и 600 мс, вживую — `s09-turn-banner`
  хоста Sarpedon (14/16) и `s09-no-defense-stamp` хоста Sarpedon (8/18).
- **Сердце павшего (AB-8).** На `s09-result-board` у павшего Короля Артура (0/18) почерневшее сердце: серый
  контур, тёмная середина и малый красный X. Это форма Codex. Значок занимает поле 24 px, сам глиф около 20 px. Крест и
  контур читаются. Хвост I-01 «проверить в живом виджете меньше 24 px» закрыт: поле 24 px.
- **Штамп «нет защиты» (AB-8).** Компактный красный X с тёмным контуром над подписью NO DEFENSE в панели защиты боя.
  Кадры: `joiner/s09-no-defense-stamp` Marmoreal, `host/` и `joiner/s09-no-defense-stamp` Sarpedon. У хоста
  Marmoreal в этот момент открыта панель колоды соперника, она закрывает правый край; штампа на этом кадре не видно.

Сравнение с листом Codex (`art/imagegen/hud-icons-de012-codex/comparison/overview-1024-color.png`, колонка CODEX): кольцо,
сердце павшего, штамп и слот совпадают по форме и цвету. Расхождений нет.

## Файлы

PNG живых партий пересохранены в JPG (q88). Трассы `.log` переименованы в `.trace.txt`: `*.log` лежит в `.gitignore`.
Хэши в `manifest.json` относятся к исходным PNG.
