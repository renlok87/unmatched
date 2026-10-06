# IC-47 — лист приёмки `state-warning` (предупреждение (треугольник «!»))

Лист собран 2026-10-06: `draw_icons.py --sheet accept state-warning` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08SlateHud=toast` (носитель — UUmToast)
**Решения по делегированию:** ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Треугольник (16; 3,5), (29; 27,5), (3; 27,5), скругление 1 u; keyline 1 u снаружи, кромка card.cream 1,25 u внутрь, тело state.warning (#E8812C, алиас turn.flash.orange, ВР-66); «!» card.navy — планка 2,75 × 9 u (y 11…20), зазор 1,75, точка 2,75 u; основание снэпнуто к ряду. Одна текстура; ue_sizes 18…64; appear 180 / leave 120, без цикла и мигания.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-state-warning.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-state-warning.png`, `sheet-01-state-warning-24.png`, `sheet-02-state-warning-32.png`, `sheet-03-state-warning-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блоки TOASTS и COMBAT (UUmToast, UUmHudCombatEdge)) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/state-warning-24.png` | 24×24 | c12a5ec1008e494da7d1ab7f097e492e4dc7dd8b9deaabb0ddf7f4734ed9cc17 |
| `art/imagegen/hud-icons-v3/sizes/state-warning-32.png` | 32×32 | cf0e4cdf757b36c127e39e949b497bb5a5b3c934425cf2f5bed3a272374f73b4 |
| `art/imagegen/hud-icons-v3/sizes/state-warning-48.png` | 48×48 | 8b3e5ff2cd5a713b9f2fc527bc01f8129264a1fcf1a9f91461e2d42efeb36470 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-state-warning.png`, `check-neighbours.png`, `sheet-01-state-warning-24.png`, `sheet-02-state-warning-32.png`, `sheet-03-state-warning-48.png`, `sheet-sizes.png`.
- «!» читается при 18 px; navy/warning 6,6 : 1.
- В сером треугольник (145) с «!» и кромкой отличается от голого ▲ ui-step и светлого диска action-scheme (`check-neighbours.png`).
- audit: margin_px [85, 115, 85, 112], seam_px 0.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блоки TOASTS и COMBAT (UUmToast, UUmHudCombatEdge)); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
