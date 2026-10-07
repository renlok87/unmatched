# IC-69 — лист приёмки `zone-yellow` (значок зоны «yellow», глиф: три точки «∴»)

Лист собран 2026-10-07 (VS-4, шаг V3): `draw_icons.py --sheet accept zone-yellow,zone-yellow-sarpedon` (мастер и 18 / 24 / 32 / 48 px ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py --v3zones` (пункты acceptance карточки: 8 ключей рядом в сером, фоны кадров, ×8 при 24 px, контрасты). Финал нарисован движком `draw_icons.py` по числам принятого пакета Codex IC-37 (вариант A, `art/imagegen/zone-icons-codex/`); ImageGen и Codex финал не рисовали.

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` — вид по умолчанию.
**Дата решения:** 2026-10-07
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-4 шаг V3.
**Флаг отката:** значка — нет (прежнего вида не было); носитель FX-38 — `-S08SlateHud=zone` (значков зон у клетки нет, как до FX-38).
**Решения по делегированию:** ВР-VS4-50, ВР-VS4-51, ВР-VS4-52, ВР-VS4-53, ВР-VS4-54 (art/imagegen/hud-icons-v3/README.md, раздел «Набор VR44 (VS-4 шаг V3)»).

## Что сделано

- Плашка shape.state_badge (30 u, r 1,5 u, keyline 1 u, кромка card.cream 1,25 u, тело card.navy), диск r 11 u с ободком card.cream 0,5 u, глиф «три точки «∴»» в боксе 13 u — числа пакета IC-37 один в один (снэп каждой координаты); keyline глифа mark.keyline ровно 1 px наружу (расширение маски 3 × 3, как в пакете).
- Слои UMG: `_glyph` (`_body` и `_disc` — общие из zone-gray); диск и глиф — белые маски, тон даёт игра: диск — `boards[].zoneIconSrgb.yellow` профиля доски (`Config/ArtBoards/S08ArtBoardProfiles.json`), глиф — card.navy или card.glyph, у кого контраст к диску выше (контракт движения: `tint` слоёв `zone` и `ink`).
- Мастер и размеры — диск цветом кадра Marmoreal, вариант `zone-yellow-sarpedon` — Sarpedon (Marmoreal #D5BD8A, Sarpedon #DCC88E). Размеры 16, 18, 21, 24, 32, 36, 48, 64, 72, 96; UE — 24, 32, 36, 48, 64 (`/Game/S08/UI/IconsV3/T_IV3_zone_yellow_{24,32,36,48,64}` и слои, `ue-import-report.json`).

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-zone-yellow.png`, `accept-zone-yellow-sarpedon.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-zone-yellow.png`, `accept-zone-yellow-sarpedon.png`, `sheet-01-zone-yellow-24.png`, `sheet-02-zone-yellow-32.png`, `sheet-03-zone-yellow-48.png` | да |
| 3 | 8 ключей рядом при 24 и 32 px ×4 в сером — попарно различимы | `../IC-62/check-zone-keys.png` (общий лист восьми ключей); замеры `checks.json` (`pairs`) | да |
| 4 | Контекст: фоны кадров (светлое пространство Marmoreal #DEDEE0, палуба Sarpedon #A43839, panel.bg), ×8 при 24 px | `check-zone-context.png`, `check-zone-24x8.png` | да |
| 5 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | лист носителя FX-38 (галерея, вне git — доска на кадре): `docs/game-design/evidence/VISUAL/FX-38/README.md`; packaged `-Bench` — шаг «Кадры» | галерея: да; packaged: нет |
| 6 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (ревизия `icon-motion-2026-10-07-vr44-zones`, эталон `icon-motion-golden.json`): appear 180 / leave 120 мс, reduced — opacity 100 мс | да |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/zone-yellow-24.png` | 24×24 | abfe9b3e49113ed417e0eee8b0918645538ad57be69591c2115cb1d1e201d6a7 |
| `art/imagegen/hud-icons-v3/sizes/zone-yellow-32.png` | 32×32 | bf2001b6ed52a80384e4724e806452466f78ac4649c7ca6eb4152b72ba8f0ee6 |
| `art/imagegen/hud-icons-v3/sizes/zone-yellow-48.png` | 48×48 | 559b3268929d9835ed341913c2f1a4417d0a6c35e428fbb2306fbb7c46228414 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-zone-yellow-sarpedon.png`, `accept-zone-yellow.png`, `check-zone-24x8.png`, `check-zone-context.png`, `sheet-01-zone-yellow-24.png`, `sheet-02-zone-yellow-32.png`, `sheet-03-zone-yellow-48.png`, `sheet-sizes.png`; общий `../IC-62/check-zone-keys.png`.
- Marmoreal: диск #D5BD8A, глиф card.navy 10,01 : 1 (другой цвет — 1,72 : 1), диск к плашке navy 10,01 : 1 — как в строке карточки.
- Sarpedon: диск #DCC88E, глиф card.navy 11,07 : 1 (другой цвет — 1,56 : 1), диск к плашке navy 11,07 : 1 — как в строке карточки.
- Три точки r 2 u: при 24 px точка — 1 px глифа внутри квадрата keyline 3 × 3, знак читается как три тёмных квадрата треугольником; при 32 px keyline точек смыкается в пирамиду из трёх; при 48 px — три точки. От остальных ключей отличается числом элементов (минимум — пара с purple, 24 px различий).
- Ближайшая пара ключа в сером: при 24 px — purple / yellow, 24 px различий бинарной маски глифа (67% объединения), средняя |Δ серого| по окну диска 104,3; при 32 px — purple / yellow, 40 px. Минимум набора — gray / brown, 8 px при 24 px (обратная полярность, |Δ серого| 114).
- audit: `zone-yellow` margin_px [32, 32, 32, 32], seam_px 0; `zone-yellow-sarpedon` margin_px [32, 32, 32, 32], seam_px 0 (seam набора v3 — до 21).
- sha1 принятых файлов набора в `manifest.json` не изменились: 1389 из 1389 те же, добавлено 264 (зоны).
- Перенос форм проверен pytest `test_zone_forms_match_codex_proposal` (`tools/s08/hud_contract/test_icon_motion.py`): бинарная альфа цельного значка равна пакету на всех размерах, маска глифа отличается только в полосе 1 px сглаживания (ВР-VS4-50), 16 px — вне HUD.

## Что не прошло или отложено

- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 %, с отпечатком RENDER — шаг «Кадры» VS-4 (в V3 без упаковки по заданию); кадры галереи носителя — FX-38.
- G-ICON |Δ| ≤ 0,45 (IC-70) — в прогоне гейта шага «Кадры».
- Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
