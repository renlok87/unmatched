# IC-39 — лист приёмки `badge-order-p2` (бейдж порядка хода у клетки (P2))

Лист собран 2026-10-06: `draw_icons.py --sheet accept badge-order-p2` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** нет (прежнего вида не было)
**Решения по делегированию:** ВР-VS2-13, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Вариант badge-order (VARIANTS_VR44): та же геометрия, блок team.p2.screen; слои общие с IC-38, в UMG вариант не нужен — текстуры T_IV3_badge_order_p2_* для галереи и запасного вида без тона.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-badge-order-p2.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-badge-order-p2.png`, `sheet-01-badge-order-p2-24.png`, `sheet-02-badge-order-p2-32.png`, `sheet-03-badge-order-p2-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок бейджей L6, MS-T-10) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-digits.png`, `check-p1-p2.png`, `check-zones.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/badge-order-p2-24.png` | 24×24 | bb2ade4506db4e35b92e9d48afb71235b7cd6974ad3fb967e34deb25dd16debb |
| `art/imagegen/hud-icons-v3/sizes/badge-order-p2-32.png` | 32×32 | 243a6269f51e9f2cb477e5f1c5f08ab5c056623a58fdf8e7d6ec5407e165722a |
| `art/imagegen/hud-icons-v3/sizes/badge-order-p2-48.png` | 48×48 | 417fee6ca5840b234a8c981aa09387ef17413ecc90bdc394c08e22b8f8dfe123 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-badge-order-p2.png`, `check-digits.png`, `check-p1-p2.png`, `check-zones.png`, `sheet-01-badge-order-p2-24.png`, `sheet-02-badge-order-p2-32.png`, `sheet-03-badge-order-p2-48.png`, `sheet-sizes.png`.
- `check-digits.png`: цифры при 24 и 32 px читаются; `check-zones.png`: на синей зоне Marmoreal (#C4CDD4) и Sarpedon (#BFCFD9) держат keyline и форма; блок P2 4,7 : 1 к navy, 126 в сером против 196 у P1 (`check-p1-p2.png`).
- Совпадает с IC-38, умноженным на team.p2.screen (общие слои; отличается только цвет блока).
- audit: margin_px [128, 32, 128, 41], seam_px 2.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Цифра — как в IC-38 (ВР-VS2-13).
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок бейджей L6, MS-T-10); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
