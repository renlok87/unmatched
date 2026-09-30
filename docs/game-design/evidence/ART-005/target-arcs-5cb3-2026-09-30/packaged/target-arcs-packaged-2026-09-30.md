# ART-005 · 5c-B3 в packaged: дуги прицела 0,92 на трёх досках, форма колец rev 3 (2026-09-30)

**Статус.** Измерено на packaged-сборке волны 6 (промежуточная приёмка GD-058). Форма колец по зарегистрированному
классификатору — **54/54 во всех вариантах** (цвет, серый, deuteranopia). В 5c-B2 было 52/54. Край кольца против
плитки и доля заливки остаются выше порогов, их минимумы не упали ниже значений 5c-B2 больше чем на 0,01 доли.
Пороги [t5cb-thresholds.json](../../art3-live-3boards-r3-2026-09-30/t5cb-thresholds.json) не менялись. Художественная
приёмка этим актом не выставляется.

**Полномочие.** Пользователь, дословно: 2026-09-28 «Принимай решния сам И делай проект по задачам пока полностью не
доделаешь»; 2026-09-29 «делай все без меня»; 2026-09-30 цель: «4. Приёмка (волна 6) и закрытие (волна 7).»; про
приёмку выбрано «Промежуточная здесь (Recommended)».

## 1. Что запускалось

- **Бинарник.** Сборка этапа BUILD волны 6 ([package.json](../../../GD-058/interim-2026-09-30/package.json)):
  staged inner exe `f8accb3d…9178` = `Binaries/Win64`, пак `Unmatched-Windows.pak` `84e68fbe…347b`. В 5c-B2 был exe
  `8d228fae…3b35`. Хэш сверен перед прогонами.
- **Флаги — как в B1-7 5c-B2**, без героев v2 и подноса, чтобы кадры были сопоставимы:
  - K3: `t52_art3_live.py k3` → `run-combat-demo.ps1 -ArtPreview -FullHd -ClientFps 30 -ClientRenderPreset High
    -RequireRenderReference -ClientPerf -RequireShotCaptured`, `-RunSeconds 240`;
  - K1: `art004_live_k2.py run` → `run-phase2-demo.ps1 -ClientFps 30 -ArtPreviewShotAfter 36 -RunSeconds 50 -ClientPerf
    -ClientCsvFrames 1200 -RequireRenderReference -RequireShotCaptured`.
- **Бэкенд — HEAD ветки `fix/admin-panel`** (1d0e6f20, с графовой топологией Marmoreal/Sarpedon из 8dbc823f).
  - `dist` собран в главном checkout (`nest build`, 21:02).
  - Запуск: `node -r dotenv/config dist/src/main.js` на `:3120`. Окружение взято из `.env` арт-worktree через
    `DOTENV_CONFIG_PATH`, файл только читался. Там БД `codex-s09-postgres` и демо-учётки.
  - Подробности — [акт прогонов GD-058](../../../GD-058/interim-2026-09-30/packaged/runs-2026-09-30.md) §1.
- **Пороги.** Анализ читает `t5cb-thresholds.json` из каталога доказательств. Поэтому сюда положена
  [копия](t5cb-thresholds.json), байт в байт как оригинал:
  - sha256 рабочей копии `33c6155e…6203`;
  - содержимое без CR `6eb9b750…fe0a` = коммит acc97aee;
  - оригинал против HEAD не изменён.

## 2. Прогоны

Сводка трасс: [runs-summary.json](runs-summary.json) (`tools/art/t5cb2_live_summary.py`).

| Прогон | Каталог | Комната | Длит., с | RENDER ref=1 хост · присоед. | SHOT captured | seq хост/присоед. | CUE урона | FPS хост / присоед. | GPU nvidia-smi пары p50 / p95, % |
|---|---|---|---|---|---|---|---|---|---|
| A-K1-cobble-5x6 | [run-20260930-210906](k1/cobble-5x6/run-20260930-210906/) | ABORTED | 65,9 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,90 / 29,88 | 38 / 44 |
| A-K1-sherwood-forest-8x5 | [run-20260930-211211](k1/sherwood-forest-8x5/run-20260930-211211/) | ABORTED | 66,0 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,88 / 29,87 | 39 / 43 |
| A-K1-t-rex-paddock-7x5 | [run-20260930-211514](k1/t-rex-paddock-7x5/run-20260930-211514/) | ABORTED | 66,1 | 1/1 · 1/1 | 1 · 1 | 1/1 | — | 29,86 / 29,88 | 39 / 44 |
| A-K3-cobble-5x6 | [combat-20260930-210705](k3/cobble-5x6/combat-20260930-210705/) | FINISHED | 120,0 | 12/13 · 15/16 | 13 · 16 | 139/139 | 19 | 30,0 / 30,0 * | 38 / 43 |
| A-K3-sherwood-forest-8x5 | [combat-20260930-211014](k3/sherwood-forest-8x5/combat-20260930-211014/) | FINISHED | 117,1 | 14/15 · 16/17 | 15 · 17 | 146/146 | 22 | 30,0 / 29,97 * | 40 / 46 |
| A-K3-t-rex-paddock-7x5 | [combat-20260930-211319](k3/t-rex-paddock-7x5/combat-20260930-211319/) | FINISHED | 114,0 | 12/13 · 14/15 | 13 · 15 | 142/142 | 18 | 30,0 / 30,0 * | 39 / 44 |

\* медиана 5-секундных окон `PERF window`: бой завершается сразу после GAME_OVER, итоговой строки нет.

- **SHOT вне эталона.** В K3 один такой кадр на клиента — `s09-lobby-return.png` после выхода из комнаты (`profile=-`).
  Он не гейтится и не публикуется, как в 5c-B2.
- **Бои.** Все три доиграны до FINISHED, победила Medusa, seq у клиентов сошёлся. `check_art003`: Cobble и T. Rex —
  `pass_technical_evidence_only`, Sherwood — `pass_with_note` (урон применён в COMBAT_RESOLVE, результат закрыт
  следующим снимком — известная заметка).
- **Трасса дуг.** В строке `ARTPREVIEW combat marker` стоит `targetArcScaleXY=0.920` у героев и `0.718` у Merlin
  (помощник) — как задумано в 5c-B3 §3.

## 3. Итог по зарегистрированным методам

Команды: `t53_readability.py analyze` (K1 + K3 на доску, без зондов) → `rings-rev3` → `t5cb2_b18.py`. Файлы:
[analysis/](analysis/), [analysis/b18-summary.json](analysis/b18-summary.json), сравнение с 5c-B2 —
[analysis/compare-5cb2.json](analysis/compare-5cb2.json). Производные в сером и deuteranopia полного размера лежат вне
git (`C:/tmp/gd058-analysis/derived-A`), их sha256 — в `derive-manifest.json` каждой доски.

| Критерий (t5cb-thresholds → acceptance) | Порог | 5c-B2 (B1-8) | Сейчас Cobble | Сейчас Sherwood | Сейчас T. Rex | Вердикт |
|---|---|---|---|---|---|---|
| **Форма кольца, классификатор rev 2, все варианты** | 100 % | **52/54** (FAIL, K3 Cobble и T. Rex в сером) | 18/18 | 18/18 | 18/18 | **pass 54/54** |
| Край кольца против плитки rev 3 (≥ 10 px ядра), мин. | ≥ 3 у 100 % | 4,143 / 5,462 / 5,597 | 18/18, **4,266** (ободок) | 18/18, **5,707** | 18/18, **5,737** | **pass**, минимумы выше 5c-B2 |
| Доля заливки, герой, мин. | ≥ 0,60 | 0,634 / 0,752 / 0,734 | 0,673 | 0,749 | 0,727 | **pass** (−0,003 и −0,007 на фикстурах) |
| Доля заливки, помощник, мин. | ≥ 0,45 | 0,527 / 0,672 / 0,652 | 0,561 | 0,672 | 0,642 | **pass** (−0,010 на T. Rex) |
| Чип = кольцо (цвет и форма) | 100 % | 19/19, 18/18, 18/18 | 19/19, ΔE ≤ 3,47 | 18/18 | 18/18 | **pass** |
| Зоны: слоты / мультизоны | 100 % | pass | blue 11/11, red 13/13 | 14/14 | 13/13 | **pass** |
| Кромка зон против плитки, мин. | ≥ 3 | 3,20 / 6,14 / 7,13 | 3,20 | 6,14 | 7,13 | **pass** (без изменений) |
| Команды в сером \|ΔY′\| | ≥ 40 | 64,5–77,0 | 67,0–69,0 | 70,5–73,5 | 68,5–69,5 | **pass** |
| Теги: текст, привязка | ≥ 4,5; 100 % | 14,70; 100 % | 14,70; 150/150 | 14,70; 161/161 | 14,70; 142/142 | **pass** |
| Число урона: текст, привязка, 0 px² | ≥ 4,5 | 13,56–14,02 | 13,56–14,02, все | то же | то же | **pass** |
| Иконка K3 32 px: край (цвет/серый/deut.) | ≥ 3 | 5,66–5,77 / 6,33–6,34 / 6,88–6,93 | 5,57–5,62 | 4,78–5,42 | 5,24–5,32 | **pass** (ниже 5c-B2, см. §4) |
| Панели K3 против ключевых клеток | 0 px² | 0 | 0 | 0 | 0 | **pass** |
| K1 p50 проходимых (запись) | 96–108 / 150–164 | 100,0 / 152,3 / 154,4 | 100,0 | 152,3 | 154,4 | **в коридоре** |

### 3.1 Цель атаки на K3 (шестигранник P2)

`hexOverCircle` в сером при пороге ≤ 0,75 (меньше — лучше):

| Доска | Кольцо P2 на K3 | 5c-B2: цель? форма в сером, `hexOverCircle` | Сейчас: цель? форма цвет / серый / deut., `hexOverCircle` серый | Прогноз перерисовки 0,92 (5c-B3 §4) |
|---|---|---|---|---|
| Cobble | King Arthur | **цель**, **unclassified**, 0,823, «прочих разрывов» 18 | **цель**, hexagon ×3, **0,599**, разрывов 0 | 0,552 |
| Cobble | Merlin | —, hexagon, 0,562 | —, hexagon ×3, 0,571 | — |
| Sherwood | King Arthur | —, hexagon, 0,455 | **цель**, hexagon ×3, **0,489** | — |
| Sherwood | Merlin | **цель**, hexagon, 0,734 | —, hexagon ×3, 0,406 | 0,358 (цель Merlin) |
| T. Rex | King Arthur | **цель**, **unclassified**, 0,844, разрывов 20 | —, hexagon ×3, 0,291 | 0,579 (цель Arthur) |
| T. Rex | Merlin | —, hexagon, 0,424 | **цель**, hexagon ×3, **0,354** | — |

Цель в K3-кадре — последняя строка `ARTPREVIEW combat marker … target=1` перед `SHOT request` кадра
`s09-combat-resolve-revealed.png` в трассе присоединившегося.

- **Причина FAIL 5c-B2 устранена на Cobble.** King Arthur — снова цель, как в 5c-B2. В сером форма распознана, «прочих
  разрывов» 0: дуги больше не сливаются с серебряной заливкой.
- **Герой P2 как цель проверен на двух досках** — Cobble и Sherwood (0,599 и 0,489), помощник P2 как цель — на
  T. Rex (Merlin, 0,354, дуги 0,718).
- **Честная оговорка по T. Rex.** Бой другой, и в кадре цель — Merlin, а не King Arthur, как в 5c-B2. Сам случай
  «King Arthur — цель на T. Rex» в этом прогоне не повторился. Кольцо Arthur в том же кадре распознано (0,291), но дуг
  вокруг него нет.
- **Запас до порога** у всех целей 0,15–0,40. Прогноз перерисовки обещал 0,17–0,39.
- **Сопоставимость.** Фигуры стоят в других клетках, поэтому прогноз и факт сравниваются по вердикту, а не по сотым.

## 4. Что изменилось и почему это не регрессия порогов

- **Иконка K3.** Край против фона: Sherwood 4,78–5,42 (было 6,33–6,34), T. Rex 5,24–5,32 (было 6,88–6,93).
  - Иконка экранная (32 px, справа от цели). Фон под ней зависит от того, где стоит цель в кадре
    `s09-combat-resolve-revealed`, а бои в этих прогонах другие.
  - Дуги прицела до иконки не доходят (5c-B3 §4). Порог ≥ 3 выдержан с запасом ≥ 1,78.
  - Причина снижения отдельно не проверялась. Версия про фон — не доказана.
- **Доля заливки на фикстурах** ниже 5c-B2 на 0,003–0,010. Заливка начинается дальше дуг и дугами не закрывается
  (TeamRing, 5c-B3 §3). Минимумы берутся из K1, где дуг нет, поэтому разница — из позиций фигур и теней.
- **Классификатор rev 1** (не гейт, для непрерывности) по-прежнему не распознаёт часть колец гарпий и Merlin. Это
  строки `shapeFail` в `summary.json`; зарегистрированный rev 2 даёт 54/54.

## 5. Классификация кадров

`python tools/art/classify_evidence.py <30 PNG> --strict --render-reference --require-captured --require packaged-live`
→ код 0, **30/30 `packaged-live` / `strict`**:
- 3 K1 × 2 кадра;
- 3 K3 × 8 кадров: хост — 2, присоединившийся — 6.

Файл: [classify-live-strict-render-captured.json](classify-live-strict-render-captured.json).

## 6. Воспроизведение

Функции `k1` и `k3` из `C:/tmp/gd058-runs/common.sh` (вне git), цепочка `C:/tmp/gd058-runs/chain-ab.sh`:
```text
python tools/art/t52_art3_live.py k3 --label A-K3-<доска> --evidence-dir <этот каталог>/k3/<доска> --board-id <id> \
  --run-seconds 240 --client-fps 30 --build-record docs/game-design/evidence/GD-058/interim-2026-09-30/build/G1-build.json \
  --package-record docs/game-design/evidence/GD-058/interim-2026-09-30/packaged/package-record.json \
  --extra-demo-arg=-RequireShotCaptured --perf-status "…" --concurrent-gpu-users "…"
python tools/art/art004_live_k2.py run --label A-K1-<доска> --evidence-dir <этот каталог>/k1/<доска> --board-id <id> \
  --variant face-neck-v2 --shot-after 36 --run-seconds 50 --client-fps 30 --csv-frames 1200 <те же записи> \
  --demo-arg=-RequireRenderReference --demo-arg=-RequireShotCaptured
python tools/art/t53_readability.py analyze --board <доска> --evidence <этот каталог> --k1-run … --k3-run … \
  --derived-root C:/tmp/gd058-analysis/derived-A
python tools/art/t53_readability.py rings-rev3 --board <доска> --evidence <этот каталог> --out analysis/<доска>/rings-rev3.json
python tools/art/t5cb2_b18.py --evidence <этот каталог> --out analysis/b18-summary.json
```
Нужен `UNMATCHED_BACKEND_ENV=<арт-worktree>/backend/.env` и один бэкенд на `:3120`. Процессы и их остановка — в акте
прогонов GD-058, §7.
