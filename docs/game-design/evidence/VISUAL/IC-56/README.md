# IC-56 — лист приёмки `ui-step` (глиф «▲» (и «▼») выбора числа)

Лист собран 2026-10-06: `draw_icons.py --sheet accept ui-step` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08SlateHud=pending` (UUmHudPending)
**Решения по делегированию:** ВР-VS2-17, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Треугольник вершиной вверх: основание 12 u, высота 7,5 u, центр масс (16; 16), скругление 0,75 u, keyline 1 u снаружи; белая маска. «▼» — RenderTransform 180° в UMG, своей текстуры нет. Основание не снэпнуто (ВР-VS2-17). ue_sizes 18…64.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-ui-step.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-ui-step.png`, `sheet-01-ui-step-24.png`, `sheet-02-ui-step-32.png`, `sheet-03-ui-step-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок PENDING) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-up-down.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/ui-step-24.png` | 24×24 | 92588d6e5d437cc20e2bb2de6b9c10a9d3a346b62877dfdb9e6e50fba6d838e8 |
| `art/imagegen/hud-icons-v3/sizes/ui-step-32.png` | 32×32 | 310a6d2ff6f34fffdbdddc1401a7674e6ebc9c04f0bad31aff322178562deae9 |
| `art/imagegen/hud-icons-v3/sizes/ui-step-48.png` | 48×48 | 0d7b2ffbbdeb3ad0e1b258043b2d5b94f017b9b7f6321c9e95e085eeef5e9e8a |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-ui-step.png`, `check-up-down.png`, `sheet-01-ui-step-24.png`, `sheet-02-ui-step-32.png`, `sheet-03-ui-step-48.png`, `sheet-sizes.png`.
- `check-up-down.png`: вверх и вниз при 18–48 px — тот же значок, повёрнутый вокруг центра холста.
- Поворот на 180° сдвигает центр масс альфы не больше чем на 0,06 px при 16–64 px (`checks.json` rotation_shift_alpha_px: 0,04 / 0,03 / 0,01 / 0,01 / 0,06 / 0,01 / 0,05 / 0,03).
- Без «!» и кромки — не путается с state-warning.
- audit: margin_px ≥ 313, seam_px 0.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок PENDING); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
