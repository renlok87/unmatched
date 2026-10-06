# IC-58 — лист приёмки `cursor-default` (обычный курсор)

Лист собран 2026-10-06: `draw_icons.py --sheet accept cursor-default` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08SlateHud=cursor` — системный курсор (HB-12)
**Решения по делегированию:** ВР-VS2-19, ВР-VS2-20, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Полигон стрелки (3; 3), (3; 24), (8; 19), (11,75; 27,5), (15,25; 26), (11,5; 17,5), (18,5; 17,5) u; тело card.glyph, keyline mark.keyline 2 u снаружи (2 px при 24 и 32, 3 px при 48, 4 px при 64), стык miter с лимитом 2 — остриё срезано. Без тени.
- Горячая точка — `art/imagegen/hud-icons-v3/cursor-hotspots.json`: 24 px (2, 1), 32 px (2, 2), 48 px (4, 3), 64 px (5, 4) — середина среза острия внешней кромки, первый пиксель α ≥ 128.
- В контракт движения и в IconsV3 курсоры не идут; T_Cursor_* импортирует HB-12.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-cursor-default.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-cursor-default.png`, `sheet-01-cursor-default-24.png`, `sheet-02-cursor-default-32.png`, `sheet-03-cursor-default-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок курсоров HB-12 (UUmCursor, шаг H3)) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-cursor.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | курсоры вне контракта |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/cursor-default-24.png` | 24×24 | 0fa82f63f0bf7680330be7f30b11dcc3d2366661020c2b5d0fa0a86633a90ced |
| `art/imagegen/hud-icons-v3/sizes/cursor-default-32.png` | 32×32 | 4f7cda029e0b63040a9c8f97e4e81e88fea641841651dd005c6add6e056b5bb9 |
| `art/imagegen/hud-icons-v3/sizes/cursor-default-48.png` | 48×48 | adb69186650f5ea0eb87801b54e297a1e6fc5a83ff439c78e4df4327a4019605 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-cursor-default.png`, `check-cursor.png`, `sheet-01-cursor-default-24.png`, `sheet-02-cursor-default-32.png`, `sheet-03-cursor-default-48.png`, `sheet-sizes.png`.
- `check-cursor.png`: виден на светлом пространстве Marmoreal #DEDEE0 (keyline 13,8 : 1), на красной палубе Sarpedon #A43839 (белое тело и keyline) и на panel.bg; в сером читается везде; горячая точка отмечена пикселем.
- audit: margin_px [32, 49, 388, 60], seam_px 3.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- UE: T_Cursor_Default (32, _x2 64, _24, _48), трасса HUD-CURSOR и клик остриём по краю клетки — HB-12.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок курсоров HB-12 (UUmCursor, шаг H3)); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
