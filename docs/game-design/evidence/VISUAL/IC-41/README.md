# IC-41 — лист приёмки `badge-conflict` (конфликт хода («!» на ленте))

Лист собран 2026-10-06: `draw_icons.py --sheet accept badge-conflict` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** нет (прежнего вида не было)
**Решения по делегированию:** ВР-VS2-14, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Геометрия и блок команды badge-order; в поле цифры «!» state.error: планка 2,75 × 5,75 u, зазор 1,5 u, точка 2,75 u (16 px: планка 3 px, точка 2 px, зазор 1 px); центр — середина поля.
- Слои: тело и блок — `badge-order_body` / `badge-order_team` (контракт), свой `badge-conflict_glyph`; appear 220 как marker-status, leave 120, без мигания.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-badge-conflict.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-badge-conflict.png`, `sheet-01-badge-conflict-24.png`, `sheet-02-badge-conflict-32.png`, `sheet-03-badge-conflict-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (бейджи L6, MS-T-05 / MS-T-10 / MS-T-11) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png`, `check-zones.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/badge-conflict-24.png` | 24×24 | 44c3a6e89cb6e075cc093ae9ab4f63189a449edc6a84b46f831775321f1d499a |
| `art/imagegen/hud-icons-v3/sizes/badge-conflict-32.png` | 32×32 | ff94e34f0f3bde35abac8e482229d79f146d25d2e7b3e3d6eea290d461943a01 |
| `art/imagegen/hud-icons-v3/sizes/badge-conflict-48.png` | 48×48 | 05fdd1486ef9ca7532367d338466f1791b4ee38577c4374333997ffd6d354f8d |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-badge-conflict.png`, `check-neighbours.png`, `check-zones.png`, `sheet-01-badge-conflict-24.png`, `sheet-02-badge-conflict-32.png`, `sheet-03-badge-conflict-48.png`, `sheet-sizes.png`.
- «!» читается при 16 px (`accept-badge-conflict.png`); рядом с IC-38 и IC-40 все три различимы в сером (`check-neighbours.png`); на жёлтой и синей зонах обеих карт держит keyline (`check-zones.png`).
- Лента не красная (И-3): красный только «!»; audit: margin_px [128, 32, 128, 41], seam_px 2.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Карточка: планка 9,5 u и зазор 1,75 u — «!» 14 u с keyline 16 u не входит в поле 12,5 u; keyline у «!» снят (на navy 1,1 : 1, при 48 px наезжал на блок) — ВР-VS2-14.
- «!» не закрыт фигурой на кадре V-09 — проверка кадром после MS-T-10.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (бейджи L6, MS-T-05 / MS-T-10 / MS-T-11); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
