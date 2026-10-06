# IC-38 — лист приёмки `badge-order` (бейдж порядка хода у клетки (P1))

Лист собран 2026-10-06: `draw_icons.py --sheet accept badge-order` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** нет (прежнего вида не было)
**Решения по делегированию:** ВР-VS2-13, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Лента 24 × 30 u (x 4…28, y 1…31), keyline 1 u, кромка card.cream 1,25 u, верх r 0,75, хвосты r 0,4, вырез 0,28 w = 6,72 u, апекс внутренних слоёв — офсет полигона; бока на пиксельных колонках.
- Блок команды 0,32 высоты тела от кромки до апекса (5,9 u в мастере; 2 / 4 / 6 px при 16 / 24 / 32), плоский низ на пиксельном ряду; в мастере team.p1.screen, слой `_team` — белая маска (И-5).
- Цифра — runtime font.card cap 10,5 u (9,5 u при двух знаках, трекинг −0,15), центр — середина поля (низ блока…апекс тела) + 0,25 u; при < 24 px цифры нет (лента и блок).
- Слои `badge-order_body`, `badge-order_team`; ue_sizes 16, 18, 21, 24, 32, 36, 48, 64; контракт: appear 220 (scale_y от верха), tap 150, leave 120; reduced — opacity 100.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-badge-order.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-badge-order.png`, `sheet-01-badge-order-24.png`, `sheet-02-badge-order-32.png`, `sheet-03-badge-order-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок бейджей L6, MS-T-10) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-digits.png`, `check-p1-p2.png`, `check-zones.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/badge-order-24.png` | 24×24 | 3dbb5e9bbb91317ca5055789a794471972e29a61ca09892ec37a2770d4789125 |
| `art/imagegen/hud-icons-v3/sizes/badge-order-32.png` | 32×32 | ded526f9062ca4f91c828b7562c4d1ff4ede85dc5527a44f09072e04a0ba4fcf |
| `art/imagegen/hud-icons-v3/sizes/badge-order-48.png` | 48×48 | bf5a75a6d19903e79137d8add9726af86f7116ab64b397f47d8412e2e7b4c576 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-badge-order.png`, `check-digits.png`, `check-p1-p2.png`, `check-zones.png`, `sheet-01-badge-order-24.png`, `sheet-02-badge-order-32.png`, `sheet-03-badge-order-48.png`, `sheet-sizes.png`.
- `check-digits.png`: «1»…«9» и «10» при 24 и 32 px ×4 читаются в цвете и в сером; цифра не задевает блок и апекс выреза.
- `check-zones.png`: на жёлтой и синей зонах обеих карт (Marmoreal #E6CDB2 / #C4CDD4, Sarpedon #FEFFB9 / #BFCFD9) границу держит keyline (11,5–17,9 : 1).
- `check-p1-p2.png`: P1 (блок 196 в сером) и P2 (126) различимы при 16–32 px.
- audit: margin_px [128, 32, 128, 41] (≥ 32), seam_px 2 (набор v3 — до 21).
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Карточка задаёт цифру cap 13 u (11 u при двух знаках): в поле тела 12,5 u она заходила на блок и в вырез — уменьшено до 10,5 / 9,5 u (ВР-VS2-13).
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок бейджей L6, MS-T-10); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
