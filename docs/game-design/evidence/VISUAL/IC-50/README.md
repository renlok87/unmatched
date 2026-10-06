# IC-50 — лист приёмки `marker-slot-scheme` (лента слота «схема»)

Лист собран 2026-10-06: `draw_icons.py --sheet accept marker-slot-scheme` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08SlateHud=slot` (носитель — UUmHudSourceSlot)
**Решения по делегированию:** ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Геометрия marker-status (20,6 × 30 u, вырез 0,28 w) без блока команды, бока на пиксельных колонках; тело card.type.scheme; молния action-scheme ×0,8 card.navy в центре поля −0,3 u. Одна текстура; ue_sizes 18…64; appear 220 (scale_y), leave 120.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-marker-slot-scheme.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-marker-slot-scheme.png`, `sheet-01-marker-slot-scheme-24.png`, `sheet-02-marker-slot-scheme-32.png`, `sheet-03-marker-slot-scheme-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок SLOT (WBP_UI_HUD_SLOT)) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/marker-slot-scheme-24.png` | 24×24 | 2a1c50b08d3c6c100f3a850fb465c8295ab04c26332a524e8b59a36fa4d231a7 |
| `art/imagegen/hud-icons-v3/sizes/marker-slot-scheme-32.png` | 32×32 | bbbdd6977018f05387626015e0bf9a736de2d91aa34de8a6b5d1277fb4547916 |
| `art/imagegen/hud-icons-v3/sizes/marker-slot-scheme-48.png` | 48×48 | cfc0d83fe94d0231193fea6f8950957ba73e35a91ada4e02594b6a7148e788a6 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-marker-slot-scheme.png`, `check-neighbours.png`, `sheet-01-marker-slot-scheme-24.png`, `sheet-02-marker-slot-scheme-32.png`, `sheet-03-marker-slot-scheme-48.png`, `sheet-sizes.png`.
- navy/scheme 11,1 : 1; в сером тело 198 с тёмной молнией против тела 20 с белым кольцом у IC-51 (`check-neighbours.png`).
- audit: margin_px [182, 32, 182, 41], seam_px 4.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Третья лента (IC-52 «сброс») — после IC-48 / CX-04; «не закрывает значения скана» — проверка на рамке карты после блока SLOT.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок SLOT (WBP_UI_HUD_SLOT)); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
