# CP-21 — розыгрыш карты (CUE-006): вспышка рамки

VS-4, шаг V4, 2026-10-07, ветка `feat/visual-vs4` (worktree `C:/tmp/wt-visual`), код — `d668f0e5`. Карточка —
`cards-portraits.csv` CP-21; 02 §6.3, §9.2; 04 §2.6 (дельта), §2.8; CUE-006 (`cue-table.json`: UI-HUD-SLOT, 500 мс,
reduced shorten 100); F-10; ВР-73, ВР-74.

**Статус:** вспышка, трасса G-CUE, тест и лист 0 / 100 / 250 / 500 мс — по делегированию. Кадры своей схемы и схемы
соперника в слоте packaged `-Bench` на обеих досках — шаг «Кадры». **Откат:** `-S08SlateHud=hand,slot`.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Вспышка | `UUmCardWidget::PlayPlayedFlash(float SpeedScale)`: второй слой рамки `card.frame.flash` (кромка `fx.flash` 2 su) поверх idle, прозрачность 1 → 0 линейно за 500 мс × скорость UI-ACC-013 (0,5 — 250, 1,5 — 750; «Нет» — без вспышки), reduced motion — 100 мс. Без света, без Niagara, без 3D-карты (ВР-73, ВР-74). `PlayFlash()` = `PlayPlayedFlash(1)`. |
| Где | рука: уходящая карта (атака / защита в бой, сброс) — `PlayPlayedFlash(Frame.SpeedMul)`; своя схема уходит в SLOT без вспышки в руке (HB-37) и вспыхивает при посадке в слот; схема соперника — при посадке в слот после прилёта 200 мс (`UUmHudSourceSlot::FlashLanded`, только лента СХЕМА лицом вверх). |
| G-CUE | `CUE fx id=CUE-006 subject=card seq=<seq> t=<игровые часы> vfx=none sfx=none clip=none mat=none socket=- reduced=0|1 result=spawned` и `CUE fx done … ms=<n> cut=0|replace` — одна показ-строка на seq (рука или слот), новая игра карты обрывает идущую (`replace`). |
| Тест | `Unmatched.S08.Hud.Card.PlayedFlash`: 500 / 250 / 750 / 0 мс по скорости, reduced 100; ключи 0 → 1, 100 → 0,8, 250 → 0,5, 500 → 0; виджет: состояние `flash` и его конец, reduced половина на 50 мс, «Нет» — без слоя; строки G-CUE побайтно. |

## Решения по делегированию (шаг V4)

| № | Решение | Почему |
|---|---|---|
| ВР-VS4-60 | Линейное затухание 1 → 0 за 500 мс × скорость; reduced 100 мс тем же затуханием; «Нет» — вспышки нет. Схема вспыхивает при посадке в SLOT (своя и чужая), прочие карты — уходя из руки. В G-CUE `subject=card`, одна показ-строка на seq, `sfx=none` — звук `CRD-PLAY` / `CRD-SCHEME` пишет свою строку `CUE sound` (AU-S4) | ключевые кадры карточки (0 мс — 1, 500 — 0); reduced — «только прозрачность ≤ 100 мс» (04 §3.5); `cue_contract` G2 требует один показ на (id, subject, seq) |

## Лист и проверки

- Лист `-S08IconGalleryCards=16` (ячейка flash) при 0 / 100 / 250 / 500 мс и reduced 0 / 50 / 100 мс рядом с idle, ×3:
  вне git (скан) — `scraped-data/derived/visual-evidence/CP-21/` — [`visual-evidence-index.json`](visual-evidence-index.json)
  (цвет, серый, дейтеранопия). Read `flash-colour.png`: 0 мс — белая кромка, 100 — светлее idle, 250 — половина, 500 —
  idle; reduced: 0 — кромка, 50 — половина, 100 — idle.
- Живые трассы (одна клиентская партия VS_AI, `C:/tmp/visual/vs4-v4/live/l4…l7`): `cue_contract.py check-trace` — PASS на
  трёх трассах (20–21 показ, столько же done); строки CUE-006 по 500 мс, кроме первой партии `l1` (675 мс: кадры начала партии с
  записью доказательств).
- Тесты, сборки — общие с [SC-21](../SC-21/README.md#лист-и-проверки).

## Что не сделано

- Кадры своей схемы и схемы соперника в слоте на Marmoreal (`-ConceptPaste`) и Sarpedon original, 1080p 100 %, packaged
  `-Bench` с `RENDER`, шесть фигур v2, и G-CUE «500 ± 1 кадр» на них — шаг «Кадры».

## Кадры выхода VS-4 (HB-49, упаковка `5a74a81e`, 2026-10-07)

Живые партии приёмочной упаковки, Marmoreal original (`-ConceptPaste` до EN-13, пометка) и Sarpedon original, шесть фигур v2, слоя отладки нет; прогоны, гейты и листы — [HB-49](../HB-49/README.md) (картинки со сканами и доской — вне git, `scraped-data/derived/visual-evidence/HB-49/`, ВР-VS4-01).

Вспышка сыгранной карты: строки G-CUE `CUE fx id=CUE-006 subject=card` во всех трассах; G-CUE PASS (кроме трёх AU5 после кадра доказательств, ВР-VS3-78). Отдельного кадра вспышки нет (500 мс между кадрами).
