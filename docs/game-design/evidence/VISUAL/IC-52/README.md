# IC-52 — лист приёмки `marker-slot-discard` (лента слота карты-источника «сброс»)

Лист собран 2026-10-06 (VS-2 шаг A3): `draw_icons.py --sheet accept marker-slot-discard` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py --a3` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py`; форма — по числам карточки и глифу IC-48.

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A3.
**Флаг отката:** `-S08SlateHud=slot` (носитель — UUmHudSourceSlot, FS09SlotCard Ribbon)
**Решения по делегированию:** ВР-IC12; ВР-VS2-26 (art/imagegen/hud-icons-v3/README.md, раздел VR44 A3).

## Что сделано

- Геометрия marker-status без блока команды (лента 20,6 × 30 u, бока на пиксельных колонках, вырез 0,28 w, keyline 1 u, кромка card.cream 1,25 u), тело text.secondary; глиф — глиф card-drop (IC-48) ×0,8, card.navy, центр поля −0,3 u. Глиф ×0,8 рисуется в своей сетке Spec(size × 0,8), как песочные часы cursor-busy: толщины и кромки на пикселях холста (ВР-VS2-26).
- Одна текстура без слоёв; контракт `marker-slot-discard` — appear 220 (scale_y 0,1 → 1, как marker-status) / leave 120.
- UE: T_IV3_marker_slot_discard_{18,24,32,36,48,64} — в `ue-import-report.json`.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-marker-slot-discard.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-marker-slot-discard.png`, `sheet-01-marker-slot-discard-24.png`, `sheet-02-marker-slot-discard-32.png`, `sheet-03-marker-slot-discard-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок SLOT (UUmHudSourceSlot, WBP_UI_HUD_SLOT)) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/marker-slot-discard-24.png` | 24×24 | 7eb0f3f616840b95aabe86f4aeeda950ebd9f807da5ef22ee60954bfe73fed7e |
| `art/imagegen/hud-icons-v3/sizes/marker-slot-discard-32.png` | 32×32 | 72beec494270d69561ed78a8eefffacd74c91f4f9dbe063cad584c518d84c27d |
| `art/imagegen/hud-icons-v3/sizes/marker-slot-discard-48.png` | 48×48 | d25c369330876791c5e3679fd513c023b1cbcd4175b399b78efb49885ee3f8fd |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-marker-slot-discard.png`, `check-neighbours.png`, `sheet-01-marker-slot-discard-24.png`, `sheet-02-marker-slot-discard-32.png`, `sheet-03-marker-slot-discard-48.png`, `sheet-sizes.png`.
- `check-neighbours.png`: три ленты слота рядом в цвете и в сером при 18 / 24 / 32 / 48 px: схема (тело 159,8, молния), BOOST (тело 77,8, кольцо), сброс (тело 143,6, стрелка в стопку). В сером схема и сброс близки по тону (Δ 16) — различаются глифом; BOOST — тоном и глифом.
- Глиф navy к text.secondary 8,7 : 1 (≥ 3 : 1). При 24 px (720p) наконечник 3–4 px и грубеет — читается силуэтом «стрелка + стопка» рядом с подписью «СБРОС» (type.tag); при 32 px (1080p) — чисто.
- Ленты справа сверху на рамке карты (32 su, лист вне git `scraped-data/derived/visual-evidence/IC-52/check-scans.png`): значения скана (тип и число слева сверху, круг защиты справа снизу) не закрыты.
- audit мастера: margin_px [182, 32, 182, 41], seam_px 8 (набор v3 — до 21).
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат и 17 строк VR44 шага A2) в `manifest.json` не изменились: 1290 из 1290 те же, добавлено 99 (пять id шага A3).
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок SLOT (UUmHudSourceSlot, WBP_UI_HUD_SLOT)); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
