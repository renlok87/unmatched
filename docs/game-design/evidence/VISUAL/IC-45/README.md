# IC-45 — лист приёмки `team-chip-p2` (чип команды P2 (шестигранник))

Лист собран 2026-10-06: `draw_icons.py --sheet accept team-chip-p2` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08IconLegacy` → T_UI_TeamShape_Hex_12 (mvp-v1); трасса ARTLOOK `chips=v3|legacy(-S08IconLegacy)`
**Решения по делегированию:** ВР-VS2-15, ВР-VS2-16, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Шестигранник: вершины на 0°, 60° … 300° от +X (слева и справа), плоские грани сверху и снизу на пиксельных рядах, описанный радиус тела 14 u (площадь −4 % к кругу P1), углы r 0,5 u, keyline 1 u снаружи; тело белое в текстуре, мастер — team.p2.screen. При мелких размерах оба чипа уменьшаются одним множителем (keyline 1 px и поле 1 px входят в холст).
- UE — как IC-44 (Style.TeamChipColor(1)).

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-team-chip-p2.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-team-chip-p2.png`, `sheet-01-team-chip-p2-24.png`, `sheet-02-team-chip-p2-32.png`, `sheet-03-team-chip-p2-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (тег бойца HB-45 (24 su) и плашка HB-46, шаг H12) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-chips-x8.png`, `check-p1-p2.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | `HUD team chips ready=1 chips=v3 su=12 px=18`, ARTLOOK `chips=v3` (UE-тест) | частично |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/team-chip-p2-24.png` | 24×24 | 36d6db59bbb586e0363ff0fb549f2b63292773f476fc3e65f401585532eb36ae |
| `art/imagegen/hud-icons-v3/sizes/team-chip-p2-32.png` | 32×32 | ef460123b3182e43b6795bea581a8c1744f409fdfa10a4e65a3fea8f0e05f3d6 |
| `art/imagegen/hud-icons-v3/sizes/team-chip-p2-48.png` | 48×48 | 37c17a38e36638f9e13320f1dc3074c722381146e87fb0268f04404b608b3dcd |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-team-chip-p2.png`, `check-chips-x8.png`, `check-p1-p2.png`, `sheet-01-team-chip-p2-24.png`, `sheet-02-team-chip-p2-32.png`, `sheet-03-team-chip-p2-48.png`, `sheet-sizes.png`.
- `check-chips-x8.png`: шестигранник при 12 px читается гранями (плоский верх и низ), при 9 px — граница формы на пределе (лист проверки, в HUD не ставится, ВР-42).
- `check-p1-p2.png`: P1 / P2 различимы формой в сером при 18–48 px.
- UE-тесты — как IC-44.
- audit: margin_px [34, 92, 34, 92], seam_px 0.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Как IC-44: бокс 12 su до HB-45 / HB-46 (ВР-VS2-16).
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (тег бойца HB-45 (24 su) и плашка HB-46, шаг H12); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
