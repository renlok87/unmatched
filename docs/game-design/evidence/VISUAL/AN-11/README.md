# AN-11 — лист приёмки клипа (AN-18, ВР-17)

**Решение:** художественно принято, по делегированию (ВР-17, ВР-60), 2026-10-09. Черновик на editor-build `-Bench`
(шаг A2 VS-8); шаг Frames переснимает листы в пакете той же командой `clip_review_sheet.py run --packaged`.
**Флаг отката:** — (клип принят как есть; откат фигур целиком — `-S08HeroesLegacy`)
**Ревью:** один проход, арт и рамки задачи вместе (02 §13.3)

## Клип

| поле | значение |
|---|---|
| клип | `MED-HitReact` (AM_Medusa_HitReact.fbx, коммит `16d0bd69`) |
| длина | 417 мс = 10 к. при 24 fps — совпадает с clip-manifest.json (`duration_s.measured` 0.4167) и `len=` трассы `clippose` |
| контакт | — (клип стартует в кадр контакта удара или петля) |
| rootDeltaUU | max 0.00 по всем строкам и фигурам (порог 0,5) |
| строки листа | f00, f02, f04, f07, f10 (ключевые кадры карточки; Idle — четверти цикла) |
| сборка | editor build (UnrealEditor -game), worktree HEAD 057c9936 — черновик, Frames пересоберёт в пакете |

## Листы

- `sheet-color.jpg`, `sheet-gray.jpg` (Rec.709 luma), `sheet-deutan.jpg` (Machado 2009, 1,0) — столбцы Marmoreal K1
  (кроп по `figrect` + 25 %), Marmoreal K2×1,6 (окно 640×360 1:1 у фигуры, ВР-VS8-08), Sarpedon K1, Sarpedon K2×1,6.
- `frames.json` — 20 исходных PNG (пути вне git, sha256), строки RENDER (reference=1 у 20 из 20),
  ARTLOOK (`heroes=v2`), `clippose` и `figrect` фигуры, трассы задника (concept-paste Marmoreal по умолчанию, lit3d
  Sarpedon). Проблем сборщика: 0.

## Осмотр (Read, цвет и серый, поштучно все ячейки)

- к.0 rest
- к.2 отдача корпуса и головы назад
- к.4 руки и лук взлетают
- к.7 затухание, к.10 rest

- Фигура: Medusa v2
- Поворот (ВР-06): вполоборота к камере; спиной нет
- Серый / дейтеранопия: различимо на K2×1,6; на K1 фигура мала (около 40 px), поза читается по луку
- G-LOOK: обе доски настоящие — Marmoreal original `c121b47f8d6eb28daccb76d05` с нарисованным задником (вклейка по
  умолчанию, ENV-U16), Sarpedon original `c7fa64a26c29a0835f2383e63` lit3d; шесть фигур v2 в кадрах.

## WARN clip-manifest (clip_contact_check)

- WARN у клипа нет (clip_contact_check PASS без замечаний).

## Что не прошло / хвосты

- Нет.
