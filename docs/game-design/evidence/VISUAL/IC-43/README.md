# IC-43 — лист приёмки `badge-attack-from` («отсюда можно атаковать: N»)

Лист собран 2026-10-06: `draw_icons.py --sheet accept badge-attack-from` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** нет (прежнего вида не было)
**Решения по делегированию:** ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Плашка shape.title_plate как state-hint (62 × 30 u, слот 25,5 u, линейка cream 0,5 × 13,75 u при x 30,25, поле числа x 32…60,75) — `_body`; звезда g_burst action-attack R 7,75 u (14 / 11 / 8 лучей) card.glyph — `_glyph`; число — runtime font.card cap 14 u. Экспорт 2048 × 1024, в UE ширина ×2; ue_sizes 18…64; appear как state-threat (scale_x от левого края 200), tap 150, leave 120.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-badge-attack-from.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-badge-attack-from.png`, `sheet-01-badge-attack-from-24.png`, `sheet-02-badge-attack-from-32.png`, `sheet-03-badge-attack-from-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (бейджи L6, MS-T-10 / HI-12) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-digits.png`, `check-neighbours.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/badge-attack-from-24.png` | 48×24 | 8c8585a806dfa27439fbda2e6ad69ff7d66acf63df38739afb58c413f6dd1404 |
| `art/imagegen/hud-icons-v3/sizes/badge-attack-from-32.png` | 64×32 | eb4c414a026584f04687c0b99319b8b75151b10707a94d4ca36c762bc33e324d |
| `art/imagegen/hud-icons-v3/sizes/badge-attack-from-48.png` | 96×48 | 0cf8775da63d79fdbd98579d5858a807286251fce143455cfe72d52970bf4d70 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-badge-attack-from.png`, `check-digits.png`, `check-neighbours.png`, `sheet-01-badge-attack-from-24.png`, `sheet-02-badge-attack-from-32.png`, `sheet-03-badge-attack-from-48.png`, `sheet-sizes.png`.
- Число «1»…«4» при 24 и 32 px читается (`check-digits.png`).
- Звезда в слоте отличается от лампы state-hint и глаза state-threat в сером (`check-neighbours.png`); звезда белая, красного диска нет (И-3).
- audit: margin_px 32, seam_px 10 (v3 — до 21).
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (бейджи L6, MS-T-10 / HI-12); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
