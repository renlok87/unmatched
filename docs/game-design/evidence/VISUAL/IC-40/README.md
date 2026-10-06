# IC-40 — лист приёмки `badge-refuse` (отказ «так нельзя» (X на плашке))

Лист собран 2026-10-06: `draw_icons.py --sheet accept badge-refuse` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** нет (прежнего вида не было)
**Решения по делегированию:** ВР-VS2-18, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Плашка shape.state_badge (квадрат 30 u, r 1,5, keyline 1, кромка 1,25, тело navy) — слой `_body`; X state.error полуразмах 6,75 u, штрих 3 u (16 / 18 px — 2 px), прямые концы, keyline 1 u — слой `_glyph`.
- Контракт: appear 200 мс — тело opacity 0 → 1 за 120, X как marker-x-stamp (0,15 → 1 за 150, scale 0 → 1,08 → 1, удар 120); leave 120; игра ставит leave через 230 мс — всего 350 = motion.refuse.ms; reduced — opacity 100; тряски нет. ue_sizes 16…64 (с 21).

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-badge-refuse.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-badge-refuse.png`, `sheet-01-badge-refuse-24.png`, `sheet-02-badge-refuse-32.png`, `sheet-03-badge-refuse-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (бейджи L6 и блок TOASTS, MS-T-06 / MS-T-10 / 04 §2.12) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png`, `check-red-zones.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/badge-refuse-24.png` | 24×24 | 25d35180b44c005cb14f05e7992cfda67604d5dbe2923d835e1e0ac8e918e4e5 |
| `art/imagegen/hud-icons-v3/sizes/badge-refuse-32.png` | 32×32 | 913c00ced32eba13840ae6f50a350f86e9b27d8825f8cb2b15ec970addd2e10d |
| `art/imagegen/hud-icons-v3/sizes/badge-refuse-48.png` | 48×48 | 78a9c32f41da3ef0fb6e320626c5fc250e4c758c99fa2b090320d0d8b98da72b |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-badge-refuse.png`, `check-neighbours.png`, `check-red-zones.png`, `sheet-01-badge-refuse-24.png`, `sheet-02-badge-refuse-32.png`, `sheet-03-badge-refuse-48.png`, `sheet-sizes.png`.
- X читается при 16 px в цвете и в сером (штрих 2 px); X/navy 4,3 : 1.
- `check-red-zones.png`: на красной палубе Sarpedon #A43839 и розовой зоне Marmoreal #D39BA5 границу держит плашка (кромка cream 5,6 : 1 к палубе, keyline 8,0 : 1 к розовой).
- `check-neighbours.png`: в сером квадрат против ленты badge-conflict и тело 20 против 100 у state-pending-move.
- audit: margin_px 32 со всех сторон, seam_px 0.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Полный показ 350 ± 17 мс на трассе G-CUE — после подключения носителя (код V-08).
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (бейджи L6 и блок TOASTS, MS-T-06 / MS-T-10 / 04 §2.12); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
