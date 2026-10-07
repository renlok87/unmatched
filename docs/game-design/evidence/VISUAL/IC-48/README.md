# IC-48 — лист приёмки `card-drop` (карта уйдёт в сброс)

Лист собран 2026-10-06 (VS-2 шаг A3): `draw_icons.py --sheet accept card-drop` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py --a3` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py`; форма — числа принятого вектора A пакета Codex IC-36 (ImageGen и Codex финал не рисовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A3.
**Флаг отката:** `-S08SlateHud=hand` (носитель — UUmCardWidget DropIcon, CP-15 / HB-24)
**Решения по делегированию:** ВР-IC13; ВР-VS2-23, ВР-VS2-25 (art/imagegen/hud-icons-v3/README.md, раздел VR44 A3).

## Что сделано

- Форма — вектор A пакета Codex IC-36, числа один в один: плашка shape.state_badge (тело card.navy, кромка card.cream, keyline), стрелка вниз (древко 2,25 u от y −9,5, наконечник 7 × 4 u, остриё y −0,5) над стопкой из двух скошенных плашек 15 × 3 u, скос 3,5 u, зазор 1 px (язык resource-card); при detail 0 плашки по 1 px. Без лотка и коробки.
- Альфа побайтно равна `vector/<px>/card-drop.png` пакета на 1024 / 16 / 21 / 24 / 32 / 48 / 64 / 96 (pytest `test_vr44_forms_match_codex_proposal`).
- Слои `_body` и `_glyph`; контракт `card-drop` — appear 180 («кладут на стол») / leave 120.
- UE: T_IV3_card_drop_{18,24,32,36,48,64}, _body_*, _glyph_* — в `ue-import-report.json`.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-card-drop.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-card-drop.png`, `sheet-01-card-drop-24.png`, `sheet-02-card-drop-32.png`, `sheet-03-card-drop-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | лист галереи HAND (`-S08IconGalleryHand`, состояние drop — сброс по лимиту) — вне git (кадр доски, ВР-VS4-01): `scraped-data/derived/visual-evidence/IC-48/` (k1-gallery-drop-*.png), [`visual-evidence-index.json`](visual-evidence-index.json) | галерея: да (VS-4 V3); packaged `-Bench`: шаг «Кадры» |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | трассы галереи (`SHOT widget` носителя), `check-trace` PASS | да (галерея) |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/card-drop-24.png` | 24×24 | 97726ea7b07275f64f3fc7e5857b6a69ab1aad50ff39765b59c1374c5fea828b |
| `art/imagegen/hud-icons-v3/sizes/card-drop-32.png` | 32×32 | 33574a3b45a135b94483b6d331590e6554149e64d3f4bd610ab9f02cb86db352 |
| `art/imagegen/hud-icons-v3/sizes/card-drop-48.png` | 48×48 | 708c6386a528aad44ccd8320146023bc4489bf6277b7b91682ddee3fc61fc106 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-card-drop.png`, `check-neighbours.png`, `sheet-01-card-drop-24.png`, `sheet-02-card-drop-32.png`, `sheet-03-card-drop-48.png`, `sheet-sizes.png`.
- `check-neighbours.png`: в сером плашка navy (тело 45,8) со стрелкой и стопкой отличается от state-pending-place (тело 105,9, эллипс) и от голой стопки resource-card при 18 / 24 / 32 px.
- Сканы карт руки — лист вне git `scraped-data/derived/visual-evidence/IC-48/check-scans.png` (ВР-CP12): Medusa (gaze-of-stone, dash) и King Arthur (excalibur, feint), значок 24 su на карте 150 × 208 su при 18 / 24 / 36 px, справа сверху, справа снизу и в центре, цвет и серый. На светлом (зелёный и красный арт) и на тёмном (navy-поле текста) скане значок отделён кремовой кромкой и keyline (keyline к крему 15,88 : 1); читается как «стрелка в стопку», а не «скачать» — лотка нет. Яркость скана под значком — `checks.json` → `scan_patch_luma`.
- audit мастера: margin_px [32, 32, 32, 32], seam_px 6 (набор v3 — до 21).
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат и 17 строк VR44 шага A2) в `manifest.json` не изменились: 1290 из 1290 те же, добавлено 99 (пять id шага A3).
- VS-4 V3 (2026-10-07): лист галереи HAND открыт (Read: `k1-gallery-drop-colour.png`, вырезка 720p 100 % ×4): значок 16 px над двумя картами сброса при «Рука 9/7» на 8 холстах — стрелка вниз на стопку читается и на 720p; рядом скан карты (вне git). Доска — Marmoreal с нарисованным задником / Sarpedon lit3d, шесть фигур v2.

## Что не прошло или отложено

- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок HAND (сброс по лимиту: UUmCardWidget DropIcon, CP-15 / HB-24)); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
