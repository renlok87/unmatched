# IC-63 — лист приёмки `zone-green` (значок зоны «green», глиф: лист)

Лист собран 2026-10-07 (VS-4, шаг V3): `draw_icons.py --sheet accept zone-green,zone-green-sarpedon` (мастер и 18 / 24 / 32 / 48 px ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py --v3zones` (пункты acceptance карточки: 8 ключей рядом в сером, фоны кадров, ×8 при 24 px, контрасты). Финал нарисован движком `draw_icons.py` по числам принятого пакета Codex IC-37 (вариант A, `art/imagegen/zone-icons-codex/`); ImageGen и Codex финал не рисовали.

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` — вид по умолчанию.
**Дата решения:** 2026-10-07
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-4 шаг V3.
**Флаг отката:** значка — нет (прежнего вида не было); носитель FX-38 — `-S08SlateHud=zone` (значков зон у клетки нет, как до FX-38).
**Решения по делегированию:** ВР-VS4-50, ВР-VS4-51, ВР-VS4-52, ВР-VS4-53, ВР-VS4-54 (art/imagegen/hud-icons-v3/README.md, раздел «Набор VR44 (VS-4 шаг V3)»).

## Что сделано

- Плашка shape.state_badge (30 u, r 1,5 u, keyline 1 u, кромка card.cream 1,25 u, тело card.navy), диск r 11 u с ободком card.cream 0,5 u, глиф «лист» в боксе 13 u — числа пакета IC-37 один в один (снэп каждой координаты); keyline глифа mark.keyline ровно 1 px наружу (расширение маски 3 × 3, как в пакете).
- Слои UMG: `_glyph` (`_body` и `_disc` — общие из zone-gray); диск и глиф — белые маски, тон даёт игра: диск — `boards[].zoneIconSrgb.green` профиля доски (`Config/ArtBoards/S08ArtBoardProfiles.json`), глиф — card.navy или card.glyph, у кого контраст к диску выше (контракт движения: `tint` слоёв `zone` и `ink`).
- Мастер и размеры — диск цветом кадра Marmoreal, вариант `zone-green-sarpedon` — Sarpedon (Marmoreal #5EA66F, Sarpedon #2F8564). Размеры 16, 18, 21, 24, 32, 36, 48, 64, 72, 96; UE — 24, 32, 36, 48, 64 (`/Game/S08/UI/IconsV3/T_IV3_zone_green_{24,32,36,48,64}` и слои, `ue-import-report.json`).

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-zone-green.png`, `accept-zone-green-sarpedon.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-zone-green.png`, `accept-zone-green-sarpedon.png`, `sheet-01-zone-green-24.png`, `sheet-02-zone-green-32.png`, `sheet-03-zone-green-48.png` | да |
| 3 | 8 ключей рядом при 24 и 32 px ×4 в сером — попарно различимы | `../IC-62/check-zone-keys.png` (общий лист восьми ключей); замеры `checks.json` (`pairs`) | да |
| 4 | Контекст: фоны кадров (светлое пространство Marmoreal #DEDEE0, палуба Sarpedon #A43839, panel.bg), ×8 при 24 px | `check-zone-context.png`, `check-zone-24x8.png` | да |
| 5 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | лист носителя FX-38 (галерея, вне git — доска на кадре): `docs/game-design/evidence/VISUAL/FX-38/README.md`; packaged `-Bench` — шаг «Кадры» | галерея: да; packaged: нет |
| 6 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (ревизия `icon-motion-2026-10-07-vr44-zones`, эталон `icon-motion-golden.json`): appear 180 / leave 120 мс, reduced — opacity 100 мс | да |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/zone-green-24.png` | 24×24 | cfa5099561b04bdaf3b6f42dcf3222f9f7fb43fbe298476f6198a91a1c3187b6 |
| `art/imagegen/hud-icons-v3/sizes/zone-green-32.png` | 32×32 | 5ec06bdd538607cebb87a5e2dcbfa5ef5dfd6b42bf595b1ed0a0dfbb5a58f424 |
| `art/imagegen/hud-icons-v3/sizes/zone-green-48.png` | 48×48 | d7b95f66bc1165a3fdf7af9f77a1457db6c7abda156d1c23c1c449b337d9d9b6 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-zone-green-sarpedon.png`, `accept-zone-green.png`, `check-zone-24x8.png`, `check-zone-context.png`, `sheet-01-zone-green-24.png`, `sheet-02-zone-green-32.png`, `sheet-03-zone-green-48.png`, `sheet-sizes.png`; общий `../IC-62/check-zone-keys.png`.
- Marmoreal: диск #5EA66F, глиф card.navy 6,24 : 1 (другой цвет — 2,76 : 1), диск к плашке navy 6,24 : 1 — как в строке карточки.
- Sarpedon: диск #2F8564, глиф card.glyph 4,24 : 1 (другой цвет — 4,06 : 1), диск к плашке navy 4,06 : 1 — как в строке карточки.
- Лист (линза): прожилка-вырез рисуется только при детализации 2 (≥ 41 px). При 48 px она тонкая (1 px сглаженной линии), при 24 / 32 px — сплошная линза; силуэт листа читается на всех размерах.
- Sarpedon #2F8564: глиф card.glyph 4,24 : 1 (правило контраста выбирает белый), диск к плашке 4,06 : 1.
- Ближайшая пара ключа в сером: при 24 px — gray / green, 12 px различий бинарной маски глифа (33% объединения), средняя |Δ серого| по окну диска 56,4; при 32 px — gray / green, 23 px. Минимум набора — gray / brown, 8 px при 24 px (обратная полярность, |Δ серого| 114).
- audit: `zone-green` margin_px [32, 32, 32, 32], seam_px 0; `zone-green-sarpedon` margin_px [32, 32, 32, 32], seam_px 0 (seam набора v3 — до 21).
- sha1 принятых файлов набора в `manifest.json` не изменились: 1389 из 1389 те же, добавлено 264 (зоны).
- Перенос форм проверен pytest `test_zone_forms_match_codex_proposal` (`tools/s08/hud_contract/test_icon_motion.py`): бинарная альфа цельного значка равна пакету на всех размерах, маска глифа отличается только в полосе 1 px сглаживания (ВР-VS4-50), 16 px — вне HUD.

## Что не прошло или отложено

- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 %, с отпечатком RENDER — шаг «Кадры» VS-4 (в V3 без упаковки по заданию); кадры галереи носителя — FX-38.
- G-ICON |Δ| ≤ 0,45 (IC-70) — в прогоне гейта шага «Кадры».
- Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
