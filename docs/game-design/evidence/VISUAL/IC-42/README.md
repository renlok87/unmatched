# IC-42 — лист приёмки `badge-ally` (союзник проходим (шеврон «сквозь»))

Лист собран 2026-10-06: `draw_icons.py --sheet accept badge-ally` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** нет (прежнего вида не было)
**Решения по делегированию:** ВР-VS2-21, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Плашка shape.state_badge (тело navy) — `_body`; двойной шеврон «»» card.glyph — `_glyph`: штрих 2,25 u, плечи ±5,5 u, глубина 4,75 u, между остриём первого и спинкой второго 4,75 u (бокс осевых 14,25 × 11 u), стык miter, концы плоские; 16 / 18 px — один шеврон 2 px. ue_sizes 18…64; appear 180 / leave 120.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-badge-ally.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-badge-ally.png`, `sheet-01-badge-ally-24.png`, `sheet-02-badge-ally-32.png`, `sheet-03-badge-ally-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (бейджи L6, MS-T-08 / MS-T-10) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/badge-ally-24.png` | 24×24 | 5a4d0ff13b5f0b7217b23b529a972c3351087d6b9f1b8d81eed7c76f429edd72 |
| `art/imagegen/hud-icons-v3/sizes/badge-ally-32.png` | 32×32 | 4825eec344aca6d94e89fcc0c44917af07aaa6fc2995f0e6d4cbc204503dace7 |
| `art/imagegen/hud-icons-v3/sizes/badge-ally-48.png` | 48×48 | 370cb58915baa17f6c1ee8c4f8256327a16aa7caf6057d718fee4cac5900aaa5 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-badge-ally.png`, `check-neighbours.png`, `sheet-01-badge-ally-24.png`, `sheet-02-badge-ally-32.png`, `sheet-03-badge-ally-48.png`, `sheet-sizes.png`.
- При 24 px две отдельные «галочки», не стрелка (`sheet-01-badge-ally-24.png`); глиф/navy 17,2 : 1.
- В сером отличается от state-pending-move (крест стрелок на теле 100) и action-maneuver (диск) — `check-neighbours.png`.
- audit: margin_px 32, seam_px 4.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Сравнение с action-end-turn (IC-46) — после переноса формы CX-04 в движок (IC-46 не в этом шаге).
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (бейджи L6, MS-T-08 / MS-T-10); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
